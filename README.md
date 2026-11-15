# 공공데이터 병렬 수집 ETL (Kind + Spark 4.0 Python Data Source)

FastAPI Mock 공공데이터 API(10만 건, 페이징)를 Spark 4.0 **Python Data Source API**(`pyspark.sql.datasource`)로
Executor 3개에서 병렬 수집하고, `dropDuplicates()` 후 AWS S3에 Parquet으로 적재합니다.

```
Mock API (FastAPI, 2 replicas)          Spark (Kubeflow Spark Operator, SparkApplication)
  GET /api/items?pageNo&numOfRows         Driver : totalCount → 100페이지 → 3구간 [1-34][35-67][68-100]
  {totalCount, duplicateCount,     ◀───── Executor×3 : 구간별 페이지 호출 (지수 백오프 + Retry-After, 최대 5회)
   pageNo, numOfRows, items}              → dropDuplicates() → 건수 검증 → s3a://<bucket>/public-data/facilities/ingest_date=YYYY-MM-DD/
  장애주입: 5% 500/503, 2% 429                                         (dynamic partition overwrite, 멱등)
```

## 폴더 구조

```
mock-api/                    FastAPI Mock 서버 (app.py, Dockerfile)
spark/
  Dockerfile                 apache/spark:4.0.1 + hadoop-aws 3.4.1 + AWS SDK v2 bundle 2.24.6 + pyarrow/pandas
  public_api_source/
    datasource.py            DataSource / DataSourceReader / InputPartition 구현 (format "public_api")
    http_client.py           재시도 클라이언트 (pyspark 비의존)
    partitioning.py          페이지 구간 분할 (pyspark 비의존)
  jobs/ingest_to_s3.py       수집 → 중복제거 → 검증 → S3 적재
k8s/                         kind-config, namespace, RBAC, mock-api, SparkApplication 템플릿, Secret 예시
scripts/                     setup-kind / build-and-load / deploy-mock-api / s3-bootstrap / refresh-aws-secret / run-job / s3-destroy
tests/                       pytest (구간 분할, 재시도, Mock API 결정성·중복 건수)
```

## 사전 준비

- Docker Desktop (메모리 8GB, CPU 4개 이상), `kind`, `kubectl`, `helm`, `aws` CLI, `jq`, `envsubst`
- `aws login` 등으로 유효한 AWS 세션

## 실행 순서

```bash
./scripts/setup-kind.sh         # Kind(cp 1 + worker 2) + Spark Operator 2.6.0 + namespace/RBAC
./scripts/build-and-load.sh     # 이미지 빌드 → kind load
./scripts/deploy-mock-api.sh    # Mock API 배포 + 스모크 테스트

./scripts/run-job.sh --dry-run  # S3 없이 수집·중복제거·건수 검증만

./scripts/s3-bootstrap.sh       # 버킷 생성 (ap-northeast-2, 퍼블릭 차단, SSE-S3, 30일 만료) → .env.local
./scripts/refresh-aws-secret.sh # 현재 세션 자격 증명 → Secret aws-s3-credentials
./scripts/run-job.sh            # 실제 S3 적재
```

검증 규칙 (실패 시 Job FAILED):

| 항목 | 기대값 |
|---|---|
| 수집 건수 | `totalCount` (100,000) |
| 중복 제거 후 | `totalCount - duplicateCount` (98,000) |
| S3 재조회 건수 | 중복 제거 후 건수 |

상태 확인: `kubectl get sparkapplication -n spark-jobs`, 로그: `kubectl logs public-api-ingest-driver -n spark-jobs`

## 데이터 확인

**Mock 원본 데이터** (클러스터 내부 ClusterIP라 port-forward 필요. 장애 주입 때문에 가끔 429/5xx가 나오면 다시 호출)

```bash
kubectl port-forward -n spark-jobs svc/mock-api 18000:8000
curl -s "localhost:18000/api/items?pageNo=1&numOfRows=50" | jq '{totalCount, duplicateCount, dup: .items[47:50]}'
# 50행마다 직전 행이 한 번 더 나옴 (id 49가 두 번)
open http://localhost:18000/docs   # Swagger UI
```

**변환 후 데이터 (S3 Parquet)**

```bash
source .env.local
aws s3 ls --recursive --human-readable s3://$S3_BUCKET/public-data/facilities/
aws s3 cp --recursive s3://$S3_BUCKET/public-data/facilities/ ./out/
docker run --rm -v $PWD/out:/data:ro --entrypoint python3 public-api-spark:0.1.0 -c '
import pyarrow.dataset as ds
t = ds.dataset("/data", format="parquet", partitioning="hive").to_table().to_pandas()
print(len(t), t["id"].nunique()); print(t.head())'
```

AWS 콘솔: S3 → 버킷 → `public-data/facilities/ingest_date=YYYY-MM-DD/` 에서 파일 목록·크기 확인 및 다운로드.
SQL로 보고 싶으면 Athena에서 이 경로로 외부 테이블을 만들어 조회 (S3 Select는 신규 계정에서 사용 불가).

## 주의 사항

- **자격 증명**: `refresh-aws-secret.sh`는 현재 `aws` CLI 세션의 임시 자격 증명을 그대로 Secret에 넣습니다.
  루트 계정 세션이면 루트 권한이 클러스터에 들어가므로 로컬 테스트 용도로만 쓰세요.
  운영에서는 버킷 한정 IAM 정책의 전용 자격 증명(또는 IRSA 등)을 사용하세요.
- 임시 자격 증명은 만료됩니다. Job 실행 전 `refresh-aws-secret.sh`를 다시 실행하세요.
- 정리: `./scripts/s3-destroy.sh` (버킷명 재입력 확인), `kind delete cluster --name spark-etl`

## 단위 테스트

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```
