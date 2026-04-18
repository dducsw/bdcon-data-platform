#!/bin/sh
set -e

GRAVITINO_HOST="${GRAVITINO_HOST:-gravitino}"
GRAVITINO_PORT="${GRAVITINO_PORT:-8090}"
METALAKE_NAME="${METALAKE_NAME:-metalake_demo}"
CATALOG_NAME="${CATALOG_NAME:-iceberg}"

base_url="http://${GRAVITINO_HOST}:${GRAVITINO_PORT}/api/metalakes"

if ! curl -fsS "${base_url}/${METALAKE_NAME}" >/dev/null 2>&1; then
    curl -fsS -X POST "${base_url}" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"${METALAKE_NAME}\",\"comment\":\"Dev metalake\"}"
fi

catalog_url="${base_url}/${METALAKE_NAME}/catalogs/${CATALOG_NAME}"

if ! curl -fsS "${catalog_url}" >/dev/null 2>&1; then
    curl -fsS -X POST "${base_url}/${METALAKE_NAME}/catalogs" \
      -H "Content-Type: application/json" \
      -d "{
        \"name\": \"${CATALOG_NAME}\",
        \"type\": \"RELATIONAL\",
        \"provider\": \"lakehouse-iceberg\",
        \"comment\": \"Dev Iceberg catalog\",
        \"properties\": {
          \"uri\": \"jdbc:postgresql://postgres:5432/catalog_metastore_db\",
          \"jdbc-user\": \"${POSTGRES_USER}\",
          \"jdbc-password\": \"${POSTGRES_PASSWORD}\",
          \"warehouse\": \"s3a://warehouse/iceberg\",
          \"s3.endpoint\": \"http://minio:9000\",
          \"s3.access-key-id\": \"${MINIO_ACCESS_KEY}\",
          \"s3.secret-access-key\": \"${MINIO_SECRET_KEY}\",
          \"s3.region\": \"us-east-1\",
          \"s3.path-style-access\": \"true\"
        }
      }"
fi