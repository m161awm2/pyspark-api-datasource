#!/usr/bin/env bash
# Mock API / Spark 이미지 빌드 후 Kind 노드에 적재
set -euo pipefail
cd "$(dirname "$0")/.."

CLUSTER=spark-etl
MOCK_IMAGE=mock-public-api:0.1.0
SPARK_IMAGE=public-api-spark:0.1.0

docker build -t "$MOCK_IMAGE" mock-api
docker build -t "$SPARK_IMAGE" spark

kind load docker-image "$MOCK_IMAGE" --name "$CLUSTER"
kind load docker-image "$SPARK_IMAGE" --name "$CLUSTER"
