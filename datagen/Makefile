PYTHON ?= python
PG_HOST ?= localhost
PG_PORT ?= 5433
PG_DB ?= thelook_db
PG_USER ?= db_user
PG_PASSWORD ?= db_password
PG_SCHEMA ?= demo
YEAR_SHIFT ?= 3

.PHONY: seed-snapshot full-load-gcs gendata gendata-once gendata-events resume-gendata reset-seed-gendata register-incremental-cdc

seed-snapshot:
	$(PYTHON) seed_from_csv.py --host $(PG_HOST) --port $(PG_PORT) --database $(PG_DB) --user $(PG_USER) --password $(PG_PASSWORD) --schema $(PG_SCHEMA) --data-dir ./data --truncate-first --year-shift $(YEAR_SHIFT) --skip-events

full-load-gcs:
	$(PYTHON) ../src/etl/local_pg_to_gcs.py --pg-host $(PG_HOST) --pg-port $(PG_PORT) --pg-database $(PG_DB) --pg-user $(PG_USER) --pg-password $(PG_PASSWORD) --pg-schema $(PG_SCHEMA)

gendata:
	$(PYTHON) thelook-ecomm/generator.py --db-host $(PG_HOST) --db-port $(PG_PORT) --db-user $(PG_USER) --db-password $(PG_PASSWORD) --db-name $(PG_DB) --db-schema $(PG_SCHEMA) --avg-qps 5 --init-num-users 1000 --max-iter -1

resume-gendata:
	$(PYTHON) thelook-ecomm/generator.py --db-host $(PG_HOST) --db-port $(PG_PORT) --db-user $(PG_USER) --db-password $(PG_PASSWORD) --db-name $(PG_DB) --db-schema $(PG_SCHEMA) --avg-qps 5 --init-num-users 0 --max-iter -1

gendata-once:
	$(PYTHON) thelook-ecomm/generator.py --db-host $(PG_HOST) --db-port $(PG_PORT) --db-user $(PG_USER) --db-password $(PG_PASSWORD) --db-name $(PG_DB) --db-schema $(PG_SCHEMA) --avg-qps 5 --init-num-users 0 --max-iter 100

gendata-events:
	$(PYTHON) thelook-ecomm/generate_events_only.py --db-host $(PG_HOST) --db-port $(PG_PORT) --db-user $(PG_USER) --db-password $(PG_PASSWORD) --db-name $(PG_DB) --db-schema $(PG_SCHEMA) --avg-qps 5 --init-num-users 0 --max-iter -1

reset-seed-gendata:
	$(PYTHON) seed_from_csv.py --host $(PG_HOST) --port $(PG_PORT) --database $(PG_DB) --user $(PG_USER) --password $(PG_PASSWORD) --schema $(PG_SCHEMA) --data-dir ./data --truncate-first --year-shift $(YEAR_SHIFT) --skip-events
	$(PYTHON) thelook-ecomm/generator.py --db-host $(PG_HOST) --db-port $(PG_PORT) --db-user $(PG_USER) --db-password $(PG_PASSWORD) --db-name $(PG_DB) --db-schema $(PG_SCHEMA) --avg-qps 5 --init-num-users 1000 --max-iter -1

register-incremental-cdc:
	$(PYTHON) ../src/etl/debezium_incremental.py
