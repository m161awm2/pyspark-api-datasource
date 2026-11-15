"""공공데이터 API → (커스텀 DataSource 병렬 수집) → dropDuplicates → S3 Parquet.

검증 규칙 (불일치 시 exit 1 → SparkApplication FAILED):
    raw_count     == totalCount
    deduped_count == totalCount - duplicateCount
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from pyspark import StorageLevel
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from public_api_source import PublicApiDataSource
from public_api_source.http_client import PageClient


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", required=True)
    p.add_argument("--output", required=True, help="예: s3a://bucket/public-data/facilities")
    p.add_argument("--num-rows", type=int, default=1000)
    p.add_argument("--num-partitions", type=int, default=3)
    p.add_argument("--ingest-date", default=datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat())
    p.add_argument("--dry-run", action="store_true", help="S3 쓰기를 건너뛰고 검증만 수행")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    spark = SparkSession.builder.appName("public-api-ingest").getOrCreate()
    spark.dataSource.register(PublicApiDataSource)

    meta = PageClient(args.api_url).fetch(page_no=1, num_rows=1)
    total, dup = int(meta["totalCount"]), int(meta.get("duplicateCount", 0))
    print(f"[meta] totalCount={total} duplicateCount={dup} expected_unique={total - dup}")

    raw = (
        spark.read.format("public_api")
        .option("url", args.api_url)
        .option("numOfRows", args.num_rows)
        .option("numPartitions", args.num_partitions)
        .load()
        .persist(StorageLevel.MEMORY_AND_DISK)  # API 재호출 방지
    )
    print(f"[read] partitions={raw.rdd.getNumPartitions()}")

    raw_count = raw.count()
    deduped = raw.dropDuplicates()
    deduped_count = deduped.count()
    print(f"[count] raw={raw_count} deduped={deduped_count} removed={raw_count - deduped_count}")

    errors = []
    if raw_count != total:
        errors.append(f"raw_count {raw_count} != totalCount {total}")
    if deduped_count != total - dup:
        errors.append(f"deduped_count {deduped_count} != totalCount - duplicateCount {total - dup}")
    if errors:
        print("[validate] FAILED: " + "; ".join(errors), file=sys.stderr)
        spark.stop()
        return 1
    print("[validate] OK")

    out = deduped.withColumn("ingest_date", F.lit(args.ingest_date))
    if args.dry_run:
        print("[write] dry-run: skipped")
        out.orderBy("id").show(5, truncate=False)
    else:
        (
            out.write.mode("overwrite")
            .option("partitionOverwriteMode", "dynamic")
            .partitionBy("ingest_date")
            .parquet(args.output)
        )
        written = spark.read.parquet(args.output).where(F.col("ingest_date") == args.ingest_date).count()
        print(f"[write] {args.output}/ingest_date={args.ingest_date} rows={written}")
        if written != deduped_count:
            print(f"[write] FAILED: written {written} != deduped {deduped_count}", file=sys.stderr)
            spark.stop()
            return 1

    raw.unpersist()
    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
