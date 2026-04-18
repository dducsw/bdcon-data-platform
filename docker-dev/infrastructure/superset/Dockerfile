FROM apache/superset:latest

USER root

RUN pip install --no-cache-dir trino sqlalchemy-trino "sqlalchemy<2.0"

USER superset