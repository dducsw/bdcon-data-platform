kubectl exec postgres-0 -n data-platform -- sh -c "PGPASSWORD=postgres_password_123 psql -U postgres -c 'CREATE DATABASE airflow;'"

