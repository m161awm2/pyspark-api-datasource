#!/usr/bin/env bash
# 현재 aws CLI 세션의 (임시) 자격 증명으로 K8s Secret 생성/갱신. 값은 화면에 출력하지 않는다.
# 임시 자격 증명은 만료되므로 Job 실행 전에 다시 실행할 것.
set -euo pipefail
cd "$(dirname "$0")/.."

[[ -f .env.local ]] && source .env.local
export AWS_REGION=${S3_REGION:-ap-northeast-2}  # CLI 기본 리전과 무관하게 서울 고정

CREDS=$(aws configure export-credentials --format process)
AK=$(jq -r .AccessKeyId <<<"$CREDS")
SK=$(jq -r .SecretAccessKey <<<"$CREDS")
ST=$(jq -r '.SessionToken // empty' <<<"$CREDS")
EXP=$(jq -r '.Expiration // "none"' <<<"$CREDS")

args=(--from-literal=AWS_ACCESS_KEY_ID="$AK" --from-literal=AWS_SECRET_ACCESS_KEY="$SK" --from-literal=AWS_REGION="$AWS_REGION")
[[ -n $ST ]] && args+=(--from-literal=AWS_SESSION_TOKEN="$ST")

kubectl create secret generic aws-s3-credentials -n spark-jobs "${args[@]}" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

echo "secret spark-jobs/aws-s3-credentials updated (session token: $([[ -n $ST ]] && echo yes || echo no), expires: $EXP)"
