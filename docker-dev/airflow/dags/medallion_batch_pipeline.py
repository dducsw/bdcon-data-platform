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
    'retry_delay': timedelta(minutes=5),
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
# 2. BATCH TRANSACTIONAL PIPELINE (Every 30 Minutes)
# =============================================================================
with DAG(
    'lakehouse_batch_transactional_pipeline',
    default_args=default_args,
    description='Batch Pipeline for Transactional Data (30m)',
    schedule='*/30 * * * *',
    catchup=False,
    max_active_runs=1,
    tags=['batch', 'transactional', 'iceberg'],
) as dag_batch:

    tables = [
        'users', 'orders', 'order_items', 'products', 
        'distribution_centers', 'inventory_items'
    ]

    # 1. Bronze Layer Group
    with TaskGroup("bronze_layer") as bronze_group:
        bronze_tasks = {}
        for table in tables:
            bronze_tasks[table] = PythonOperator(
                task_id=f"ingest_{table}",
                python_callable=run_spark_job,
                op_kwargs={'script_path': f'/opt/spark/apps/pipelines/bronze/bronze_{table}.py'},
                pool='spark_pool'
            )

    # 2. Silver Layer Group
    with TaskGroup("silver_layer") as silver_group:
        silver_tasks = {}
        for table in tables:
            silver_tasks[table] = PythonOperator(
                task_id=f"transform_{table}",
                python_callable=run_spark_job,
                op_kwargs={'script_path': f'/opt/spark/apps/pipelines/silver/silver_{table}.py'},
                pool='spark_pool'
            )
            # Table-level dependency: Bronze -> Silver
            bronze_tasks[table] >> silver_tasks[table]

    # 3. Gold Layer Group
    with TaskGroup("gold_layer_batch") as gold_batch:
        # Sales Performance: Needs Orders, Items, Products, Users
        gold_sales = PythonOperator(
            task_id="sales_performance",
            python_callable=run_spark_job,
            op_kwargs={'script_path': '/opt/spark/apps/pipelines/gold/gold_sales_performance.py'},
            pool='spark_pool'
        )
        [silver_tasks['orders'], silver_tasks['order_items'], 
         silver_tasks['products'], silver_tasks['users']] >> gold_sales

        # User Statistics: Needs Users
        gold_stats = PythonOperator(
            task_id="user_statistics",
            python_callable=run_spark_job,
            op_kwargs={'script_path': '/opt/spark/apps/pipelines/gold/gold_user_statistics.py'},
            pool='spark_pool'
        )
        silver_tasks['users'] >> gold_stats
