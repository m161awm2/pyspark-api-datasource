#!/usr/bin/env bash
# S3 버킷 생성 (서울 리전, 퍼블릭 차단, SSE-S3, 30일 만료). 버킷명은 .env.local 에 저장.
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_FILE=.env.local
export AWS_REGION=${S3_REGION:-ap-northeast-2}  # CLI 기본 리전과 무관하게 서울 고정
[[ -f $ENV_FILE ]] && source "$ENV_FILE"

if [[ -z ${S3_BUCKET:-} ]]; then
  ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
  SUFFIX=$(openssl rand -hex 3)  # tr|head 는 pipefail 하에서 SIGPIPE 로 실패하므로 사용하지 않음
  S3_BUCKET="pyspark-api-ds-${ACCOUNT:0:4}-${SUFFIX}"
  printf 'S3_BUCKET=%s\nAWS_REGION=%s\n' "$S3_BUCKET" "$AWS_REGION" >"$ENV_FILE"
fi

if aws s3api head-bucket --bucket "$S3_BUCKET" 2>/dev/null; then
  echo "bucket exists: $S3_BUCKET"
else
  aws s3api create-bucket --bucket "$S3_BUCKET" --region "$AWS_REGION" \
    --create-bucket-configuration "LocationConstraint=$AWS_REGION" >/dev/null
  echo "bucket created: $S3_BUCKET ($AWS_REGION)"
fi

aws s3api put-public-access-block --bucket "$S3_BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws s3api put-bucket-encryption --bucket "$S3_BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3api put-bucket-lifecycle-configuration --bucket "$S3_BUCKET" --lifecycle-configuration '{
  "Rules":[{"ID":"expire-30d","Status":"Enabled","Filter":{"Prefix":""},
            "Expiration":{"Days":30},
            "AbortIncompleteMultipartUpload":{"DaysAfterInitiation":1}}]}'

echo "S3_BUCKET=$S3_BUCKET"
