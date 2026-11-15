#!/usr/bin/env bash
# 버킷(내용 포함)과 K8s Secret 삭제. 되돌릴 수 없으므로 버킷명을 다시 입력해야 진행된다.
set -euo pipefail
cd "$(dirname "$0")/.."

source .env.local
read -r -p "삭제할 버킷명을 입력하세요 ($S3_BUCKET): " CONFIRM
[[ $CONFIRM == "$S3_BUCKET" ]] || { echo "취소됨"; exit 1; }

aws s3 rb "s3://$S3_BUCKET" --force
kubectl delete secret aws-s3-credentials -n spark-jobs --ignore-not-found
rm -f .env.local
echo "deleted: $S3_BUCKET"
