import os
import math
import redis
from redis import ConnectionPool
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, window, avg, count, lit,
    max as spark_max, to_timestamp, from_unixtime,
    sum as spark_sum, approx_count_distinct
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType,
    FloatType, DoubleType, BooleanType
)
from pyspark.sql.streaming import GroupStateTimeout, GroupState

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC             = os.getenv("KAFKA_TOPIC", "buswaypoint_json")
REDIS_HOST              = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT              = int(os.getenv("REDIS_PORT", 6379))
KAFKA_GROUP_ID          = os.getenv("KAFKA_GROUP_ID", "buswaypoint-spark-group")

# Window sizes — tuned for 10–20s dashboard latency.
#
# Rule of thumb applied here:
#   window_size  >= 4–6× message_interval (5–10s) → min 30–60s for stable avg
#   slide_interval = target_latency = 20s
#   watermark    = 2× slide to tolerate minor GPS jitter without dropping events
#
WIN_FAST   = "2 minutes"   # lookback for speed / peak / idle / fleet metrics
SLIDE_FAST = "20 seconds"  # emit interval → Grafana sees fresh data every ~20s
WIN_DIST   = "10 minutes"  # longer lookback for distance (stateful accumulation)
SLIDE_DIST = "20 seconds"
WIN_DENS   = "1 minute"    # tumbling for density: clear per-minute buckets
WATERMARK  = "40 seconds"  # 2× slide; short enough to not delay results

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
bus_waypoint_schema = StructType([
    StructField("vehicle",   StringType(),  True),
    StructField("driver",    StringType(),  True),
    StructField("speed",     FloatType(),   True),
    StructField("datetime",  IntegerType(), True),
    StructField("x",         DoubleType(),  True),
    StructField("y",         DoubleType(),  True),
    StructField("z",         FloatType(),   True),
    StructField("heading",   FloatType(),   True),
    StructField("ignition",  BooleanType(), True),
    StructField("aircon",    BooleanType(), True),
    StructField("door_up",   BooleanType(), True),
    StructField("door_down", BooleanType(), True),
    StructField("sos",       BooleanType(), True),
    StructField("working",   BooleanType(), True),
    StructField("analog1",   FloatType(),   True),
    StructField("analog2",   FloatType(),   True),
])

root_schema = StructType([
    StructField("msgType",         StringType(),       True),
    StructField("msgBusWayPoint",  bus_waypoint_schema, True),
])

# ---------------------------------------------------------------------------
# Haversine distance (km)
# ---------------------------------------------------------------------------
def haversine(lon1, lat1, lon2, lat2):
    if None in (lon1, lat1, lon2, lat2):
        return 0.0
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * math.asin(math.sqrt(a)) * 6371  # km

# ---------------------------------------------------------------------------
# Stateful operator — delta distance per vehicle ping
#
# Bug fix vs original:  state.get() is a method call, not a property.
# State schema stores (last_x DOUBLE, last_y DOUBLE) as a named tuple.
# ---------------------------------------------------------------------------
def update_vehicle_state(vehicle_id, inputs, state: GroupState):
    """Emit (vehicle, timestamp, delta_distance_km) for every incoming ping."""
    if state.hasTimedOut:
        state.remove()
        return iter([])

    # FIX: state.get() not state.get
    last_pos = state.get() if state.exists else None
    results  = []

    for row in sorted(inputs, key=lambda r: r.timestamp):   # process in time order
        curr_x, curr_y, curr_ts = row.x, row.y, row.timestamp
        delta = haversine(last_pos[0], last_pos[1], curr_x, curr_y) if last_pos else 0.0
        last_pos = (curr_x, curr_y)
        results.append((vehicle_id, curr_ts, delta))

    state.update(last_pos)
    state.setTimeoutDuration("5 minutes")   # evict ghost vehicles after 5 min silence
    return iter(results)

# ---------------------------------------------------------------------------
# Redis connection pool — one pool per executor JVM, reused across partitions
# ---------------------------------------------------------------------------
_redis_pool = None

def get_redis_pool():
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = ConnectionPool(
            host=REDIS_HOST, port=REDIS_PORT,
            decode_responses=True, max_connections=10
        )
    return _redis_pool

# ---------------------------------------------------------------------------
# Redis sink — foreachBatch writer
#
# Uses metric_type column (lit()) for routing instead of fragile "field in row"
# pattern. Each metric maps to a clear Redis hash key with TTL.
#
# Key design:
#   metric:avg_speed:{vehicle}          HSET window_start, window_end, value  TTL 5m
#   metric:peak_speed:{vehicle}         HSET window_end, value                TTL 5m
#   metric:msg_density:{vehicle}:{win}  HSET count                            TTL 10m
#   metric:distance:{vehicle}           HSET window_end, distance_km          TTL 15m
#   metric:fleet:active                 HSET window_end, count                TTL 5m
#   metric:fleet:idle                   HSET window_end, count                TTL 5m
# ---------------------------------------------------------------------------
def write_to_redis(batch_df, batch_id):
    def send_partition(partition):
        r    = redis.Redis(connection_pool=get_redis_pool())
        pipe = r.pipeline(transaction=False)

        for row in partition:
            mt = row.metric_type

            if mt == "avg_speed":
                key = f"metric:avg_speed:{row.vehicle}"
                pipe.hset(key, mapping={
                    "window_start": str(row.window.start),
                    "window_end":   str(row.window.end),
                    "value":        str(round(row.avg_speed, 2)),
                    "route":        str(row.route or ""),
                })
                pipe.expire(key, 300)   # 5 min TTL — 15× slide interval

            elif mt == "peak_speed":
                key = f"metric:peak_speed:{row.vehicle}"
                pipe.hset(key, mapping={
                    "window_end": str(row.window.end),
                    "value":      str(round(row.peak_speed, 2)),
                    "route":      str(row.route or ""),
                })
                pipe.expire(key, 300)

            elif mt == "msg_density":
                # Tumbling window key includes start for time-series in Grafana
                key = f"metric:msg_density:{row.vehicle}:{row.window.start.isoformat()}"
                pipe.hset(key, mapping={
                    "count":  str(row.msg_count),
                    "route":  str(row.route or ""),
                })
                pipe.expire(key, 600)   # 10 min TTL — 10× window size

            elif mt == "distance":
                key = f"metric:distance:{row.vehicle}"
                pipe.hset(key, mapping={
                    "window_end":   str(row.window.end),
                    "distance_km":  str(round(row.distance_km, 3)),
                    "route":        str(row.route or ""),
                })
                pipe.expire(key, 900)   # 15 min TTL

            elif mt == "active_fleet":
                pipe.hset("metric:fleet:active", mapping={
                    "window_end": str(row.window.end),
                    "count":      str(row.active_fleet),
                })
                pipe.expire("metric:fleet:active", 300)

            elif mt == "idle_fleet":
                pipe.hset("metric:fleet:idle", mapping={
                    "window_end": str(row.window.end),
                    "count":      str(row.idle_fleet),
                })
                pipe.expire("metric:fleet:idle", 300)

        pipe.execute()

    batch_df.foreachPartition(send_partition)

# ---------------------------------------------------------------------------
# Main — split into 3 independent streaming queries
#
# Why separate queries?
#   Q1 (fast)     — small sliding windows, low latency, no stateful ops
#   Q2 (stateful) — flatMapGroupsWithState can fail independently
#   Q3 (density)  — tumbling window, separate checkpoint
#
# This way a bug in the stateful job doesn't kill the live speed / fleet panels.
# ---------------------------------------------------------------------------
def main():
    spark = SparkSession.builder \
        .appName("BusGPS-LowLatency") \
        .config("spark.sql.shuffle.partitions", "4") \
        .config("spark.streaming.stopGracefullyOnShutdown", "true") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("ERROR")

    # ------------------------------------------------------------------
    # 1. Ingest & parse
    # ------------------------------------------------------------------
    raw = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("kafka.group.id", KAFKA_GROUP_ID) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()

    parsed = raw \
        .selectExpr("CAST(value AS STRING)") \
        .select(from_json(col("value"), root_schema).alias("d")) \
        .select("d.msgBusWayPoint.*") \
        .withColumn("timestamp", to_timestamp(from_unixtime("datetime"))) \
        .withWatermark("timestamp", WATERMARK)
        # Single watermark declaration on the source stream.
        # All downstream DataFrames inherit this watermark —
        # do NOT call .withWatermark() again on derived streams.

    # ------------------------------------------------------------------
    # Q1 — Fast metrics (avg_speed, peak_speed, active_fleet, idle_fleet)
    # All use the same WIN_FAST / SLIDE_FAST parameters.
    # Trigger every 20s so Grafana panels update within the latency target.
    # ------------------------------------------------------------------

    # M1: Average speed — sliding, per vehicle+route
    avg_speed_df = parsed \
        .groupBy(window("timestamp", WIN_FAST, SLIDE_FAST), "vehicle", "route") \
        .agg(avg("speed").alias("avg_speed")) \
        .select(
            lit("avg_speed").alias("metric_type"),
            "vehicle", "route", "window", col("avg_speed")
        )

    # M5: Peak speed — same window as avg_speed (replaces the useless 1h tumbling)
    peak_speed_df = parsed \
        .groupBy(window("timestamp", WIN_FAST, SLIDE_FAST), "vehicle", "route") \
        .agg(spark_max("speed").alias("peak_speed")) \
        .select(
            lit("peak_speed").alias("metric_type"),
            "vehicle", "route", "window", col("peak_speed")
        )

    # M6: Active vehicles fleet-wide — approximate distinct count
    active_fleet_df = parsed \
        .groupBy(window("timestamp", WIN_FAST, SLIDE_FAST)) \
        .agg(approx_count_distinct("vehicle", 0.05).alias("active_fleet")) \
        .select(
            lit("active_fleet").alias("metric_type"),
            "window", col("active_fleet")
        )

    # M7: Idle vehicles (speed < 1 km/h AND ignition on)
    idle_fleet_df = parsed \
        .filter((col("speed") < 1.0) & (col("ignition") == True)) \
        .groupBy(window("timestamp", WIN_FAST, SLIDE_FAST)) \
        .agg(approx_count_distinct("vehicle", 0.05).alias("idle_fleet")) \
        .select(
            lit("idle_fleet").alias("metric_type"),
            "window", col("idle_fleet")
        )

    fast_df = avg_speed_df \
        .unionByName(peak_speed_df,  allowMissingColumns=True) \
        .unionByName(active_fleet_df, allowMissingColumns=True) \
        .unionByName(idle_fleet_df,   allowMissingColumns=True)

    query_fast = fast_df.writeStream \
        .foreachBatch(write_to_redis) \
        .trigger(processingTime=SLIDE_FAST) \
        .option("checkpointLocation", "/tmp/ckpt/fast") \
        .outputMode("update") \
        .start()

    # ------------------------------------------------------------------
    # Q2 — Stateful distance (flatMapGroupsWithState → sliding window sum)
    #
    # FIX 1: state.get() is a method call.
    # FIX 2: watermark is NOT re-declared here — inherited from parsed.
    # FIX 3: inputs are sorted by timestamp before processing.
    # FIX 4: ghost vehicles are evicted after 5 min via setTimeoutDuration.
    # ------------------------------------------------------------------
    state_result_schema = "vehicle string, timestamp timestamp, delta_km double"

    delta_stream = parsed \
        .select("vehicle", "x", "y", "timestamp") \
        .groupByKey(lambda r: r.vehicle) \
        .flatMapGroupsWithState(
            update_vehicle_state,
            outputMode="append",
            timeoutConf=GroupStateTimeout.ProcessingTimeTimeout,
            stateSchema="last_x double, last_y double",
            resultSchema=state_result_schema,
        )

    distance_df = delta_stream \
        .groupBy(window("timestamp", WIN_DIST, SLIDE_DIST), "vehicle") \
        .agg(spark_sum("delta_km").alias("distance_km")) \
        .select(
            lit("distance").alias("metric_type"),
            "vehicle", "window", col("distance_km"),
            lit(None).cast("string").alias("route"),   # no route in stateful output
        )

    query_stateful = distance_df.writeStream \
        .foreachBatch(write_to_redis) \
        .trigger(processingTime=SLIDE_DIST) \
        .option("checkpointLocation", "/tmp/ckpt/stateful") \
        .outputMode("update") \
        .start()

    # ------------------------------------------------------------------
    # Q3 — Message density (tumbling 1 min per vehicle+route)
    # Tumbling windows never overlap → clean per-minute counts.
    # Useful for detecting GPS signal loss: if count == 0 in a bucket,
    # the vehicle went silent for that entire minute.
    # ------------------------------------------------------------------
    density_df = parsed \
        .groupBy(window("timestamp", WIN_DENS), "vehicle", "route") \
        .agg(count("*").alias("msg_count")) \
        .select(
            lit("msg_density").alias("metric_type"),
            "vehicle", "route", "window", col("msg_count")
        )

    query_density = density_df.writeStream \
        .foreachBatch(write_to_redis) \
        .trigger(processingTime="1 minute") \
        .option("checkpointLocation", "/tmp/ckpt/density") \
        .outputMode("update") \
        .start()

    # ------------------------------------------------------------------
    # Await all queries — if one crashes the others keep running.
    # Monitor via spark.streams.active in a separate thread if needed.
    # ------------------------------------------------------------------
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()