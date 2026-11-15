#!/usr/bin/env bash
# SparkApplication 렌더링 → 제출 → 완료 대기 → driver 로그 요약
#   ./scripts/run-job.sh            # S3 적재
#   ./scripts/run-job.sh --dry-run  # S3 쓰기 생략, 건수 검증만
set -euo pipefail
cd "$(dirname "$0")/.."

[[ -f .env.local ]] && source .env.local
export AWS_REGION=${AWS_REGION:-ap-northeast-2}
export S3_BUCKET=${S3_BUCKET:-dry-run-no-bucket}
export INGEST_DATE=${INGEST_DATE:-$(TZ=Asia/Seoul date +%F)}
export APP_NAME=public-api-ingest
export EXTRA_ARGS=""
if [[ ${1:-} == "--dry-run" ]]; then
  APP_NAME=public-api-ingest-dryrun
  EXTRA_ARGS=$'\n    - --dry-run'
fi

kubectl delete sparkapplication "$APP_NAME" -n spark-jobs --ignore-not-found --wait=true
envsubst '${APP_NAME} ${S3_BUCKET} ${AWS_REGION} ${INGEST_DATE} ${EXTRA_ARGS}' \
  <k8s/spark-application.yaml | kubectl apply -f -

echo "waiting for $APP_NAME ..."
for _ in $(seq 1 120); do
  STATE=$(kubectl get sparkapplication "$APP_NAME" -n spark-jobs -o jsonpath='{.status.applicationState.state}' 2>/dev/null || true)
  case $STATE in
    COMPLETED|FAILED|SUBMISSION_FAILED) break ;;
  esac
  sleep 5
done
echo "state: ${STATE:-UNKNOWN}"

DRIVER="${APP_NAME}-driver"
kubectl logs "$DRIVER" -n spark-jobs 2>/dev/null | grep -E '^\[(meta|read|count|validate|write)\]|PageRangePartition|Traceback|Error' || true

[[ $STATE == COMPLETED ]]
