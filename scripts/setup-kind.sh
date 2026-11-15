#!/usr/bin/env bash
# Kind 클러스터 생성 + Spark Operator(Kubeflow) 설치 + 네임스페이스/RBAC 적용
set -euo pipefail
cd "$(dirname "$0")/.."

CLUSTER=spark-etl
OPERATOR_CHART_VERSION=2.6.0

if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --config k8s/kind-config.yaml
fi
kubectl config use-context "kind-$CLUSTER"

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/spark-rbac.yaml

helm repo add spark-operator https://kubeflow.github.io/spark-operator >/dev/null 2>&1 || true
helm repo update spark-operator >/dev/null
helm upgrade --install spark-operator spark-operator/spark-operator \
  --version "$OPERATOR_CHART_VERSION" \
  --namespace spark-operator --create-namespace \
  --set 'spark.jobNamespaces={spark-jobs}' \
  --set spark.serviceAccount.create=false \
  --set spark.rbac.create=false \
  --set webhook.enable=true \
  --wait --timeout 5m

kubectl get pods -n spark-operator
