#!/usr/bin/env bash
# Mock API 배포 및 스모크 테스트
set -euo pipefail
cd "$(dirname "$0")/.."

kubectl apply -f k8s/mock-api.yaml
kubectl rollout restart deployment/mock-api -n spark-jobs >/dev/null
kubectl rollout status deployment/mock-api -n spark-jobs --timeout=120s

# 클러스터 내부에서 메타 정보 확인 (장애 주입 때문에 몇 번 재시도)
kubectl run mock-api-smoke -n spark-jobs --rm -i --restart=Never --image=curlimages/curl:8.11.1 -- \
  curl -s --retry 5 --retry-all-errors "http://mock-api:8000/api/items?pageNo=1&numOfRows=1"
echo
