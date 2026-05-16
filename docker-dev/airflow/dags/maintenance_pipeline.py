import docker
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'admin',
    'depends_on_past': False,
    'start_date': datetime(2025, 5, 16),
    'retries': 1,
    'retry_delay': timedelta(minutes=10),
}

def run_spark_job(script_path):
    """Executes a Python Spark script inside the existing spark-master container."""
    client = docker.from_env()
    try:
        container = client.containers.get("spark-master")
        print(f"Starting Maintenance job: {script_path}")
        
        exit_code, output = container.exec_run(
            cmd=f"python {script_path}",
            environment={"PYTHONPATH": "/opt/spark/apps/pipelines"}
        )
        
        print(output.decode())
        if exit_code != 0:
            raise Exception(f"Maintenance job failed with exit code {exit_code}")
            
        print(f"Finished Maintenance job: {script_path}")
    except Exception as e:
        print(f"Error: {str(e)}")
        raise e

# =============================================================================
# MONTHLY MAINTENANCE DAG
# =============================================================================
with DAG(
    'lakehouse_monthly_maintenance',
    default_args=default_args,
    description='Monthly Iceberg maintenance: Compaction, Snapshot Expiration, and Orphan File Cleanup',
    schedule='@monthly', # Chạy vào ngày 1 hàng tháng
    catchup=False,
    tags=['maintenance', 'iceberg'],
) as dag:

    iceberg_maintenance = PythonOperator(
        task_id='run_iceberg_maintenance',
        python_callable=run_spark_job,
        op_kwargs={'script_path': '/opt/spark/apps/pipelines/maintenance/iceberg_maintenance.py'}
    )
