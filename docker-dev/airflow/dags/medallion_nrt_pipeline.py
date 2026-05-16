import docker
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup

default_args = {
    'owner': 'admin',
    'depends_on_past': False,
    'start_date': datetime(2025, 5, 16),
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

def run_spark_job(script_path):
    client = docker.from_env()
    try:
        container = client.containers.get("spark-master")
        exit_code, output = container.exec_run(
            cmd=f"python {script_path}",
            environment={"PYTHONPATH": "/opt/spark/apps/pipelines"}
        )
        print(output.decode())
        if exit_code != 0:
            raise Exception(f"Spark job failed with exit code {exit_code}")
    except Exception as e:
        raise e

# =============================================================================
# 1. NRT EVENTS PIPELINE (Every 5 Minutes)
# =============================================================================
with DAG(
    'lakehouse_nrt_events_pipeline',
    default_args=default_args,
    description='Near Real-time Pipeline for Clickstream Events (5m)',
    schedule='*/5 * * * *',
    catchup=False,
    max_active_runs=1,
<<<<<<< HEAD
    tags=['dev', 'events', 'iceberg'],
=======
    tags=['nrt', 'events', 'iceberg'],
>>>>>>> 9933772 (update .gitignore)
) as dag_nrt:

    # Bronze: Streaming Batch from Kafka
    ingest_events = PythonOperator(
        task_id="bronze_ingest_events",
        python_callable=run_spark_job,
        op_kwargs={'script_path': '/opt/spark/apps/pipelines/bronze/bronze_events_streaming.py'},
        pool='spark_pool'
    )

    # Silver: Transform Events
    transform_events = PythonOperator(
        task_id="silver_transform_events",
        python_callable=run_spark_job,
        op_kwargs={'script_path': '/opt/spark/apps/pipelines/silver/silver_events.py'},
        pool='spark_pool'
    )

    with TaskGroup("gold_layer_nrt") as gold_nrt:
        # Sessions analysis
        gold_sessions = PythonOperator(
            task_id="sessions",
            python_callable=run_spark_job,
            op_kwargs={'script_path': '/opt/spark/apps/pipelines/gold/gold_sessions.py'},
            pool='spark_pool'
        )

        # User Engagement (Depends on Events and latest Users)
        gold_engagement = PythonOperator(
            task_id="user_engagement",
            python_callable=run_spark_job,
            op_kwargs={'script_path': '/opt/spark/apps/pipelines/gold/gold_user_engagement.py'},
            pool='spark_pool'
        )

    ingest_events >> transform_events >> gold_nrt
