"""Spark 4.0 Python Data Source: 페이징 공공데이터 API 병렬 수집.

사용법:
    spark.dataSource.register(PublicApiDataSource)
    df = (spark.read.format("public_api")
          .option("url", "http://mock-api.spark-jobs.svc.cluster.local:8000/api/items")
          .option("numOfRows", 1000)
          .option("numPartitions", 3)
          .load())

- partitions(): Driver 에서 1회 호출. totalCount 로 전체 페이지를 계산해 연속 구간 InputPartition 으로 분할.
- read():       Executor 에서 파티션마다 호출. 구간의 페이지를 재시도 포함으로 순차 조회해 행을 yield.
"""

from __future__ import annotations

import logging
from datetime import datetime

from pyspark.sql.datasource import DataSource, DataSourceReader, InputPartition
from pyspark.sql.types import StructType

from .http_client import PageClient, RetryPolicy
from .partitioning import split_page_ranges, total_pages

log = logging.getLogger(__name__)

SCHEMA_DDL = (
    "id LONG, facility_name STRING, category STRING, sido STRING, sigungu STRING, "
    "address STRING, lat DOUBLE, lon DOUBLE, capacity INT, updated_at TIMESTAMP"
)
FIELDS = ["id", "facility_name", "category", "sido", "sigungu", "address", "lat", "lon", "capacity", "updated_at"]


class PageRangePartition(InputPartition):
    def __init__(self, index: int, start_page: int, end_page: int):
        super().__init__((start_page, end_page))
        self.index = index
        self.start_page = start_page
        self.end_page = end_page

    def __repr__(self) -> str:
        return f"PageRangePartition(#{self.index}, pages {self.start_page}-{self.end_page})"


class PublicApiDataSource(DataSource):
    @classmethod
    def name(cls) -> str:
        return "public_api"

    def schema(self) -> str:
        return SCHEMA_DDL

    def reader(self, schema: StructType) -> DataSourceReader:
        return PublicApiReader(dict(self.options))


class PublicApiReader(DataSourceReader):
    def __init__(self, options: dict):
        opts = {k.lower(): v for k, v in options.items()}
        if "url" not in opts:
            raise ValueError("option 'url' is required")
        self.url: str = opts["url"]
        self.num_rows = int(opts.get("numofrows", 1000))
        self.num_partitions = int(opts.get("numpartitions", 3))
        self.policy = RetryPolicy(
            max_retries=int(opts.get("maxretries", 5)),
            backoff_base=float(opts.get("backoffbase", 0.5)),
            backoff_cap=float(opts.get("backoffcap", 10.0)),
            timeout=float(opts.get("timeout", 10.0)),
        )

    def _client(self) -> PageClient:
        return PageClient(self.url, policy=self.policy)

    # ---- Driver ----
    def partitions(self) -> list[InputPartition]:
        meta = self._client().fetch(page_no=1, num_rows=1)
        pages = total_pages(int(meta["totalCount"]), self.num_rows)
        ranges = split_page_ranges(pages, self.num_partitions)
        parts = [PageRangePartition(i, s, e) for i, (s, e) in enumerate(ranges)]
        log.warning("totalCount=%s numOfRows=%d pages=%d → %s", meta["totalCount"], self.num_rows, pages, parts)
        return parts

    # ---- Executor ----
    def read(self, partition: PageRangePartition):
        client = self._client()
        rows = 0
        for page_no in range(partition.start_page, partition.end_page + 1):
            body = client.fetch(page_no, self.num_rows)
            for item in body["items"]:
                rows += 1
                yield _to_row(item)
        log.warning("%r done: rows=%d retries=%d", partition, rows, client.retries_used)


def _to_row(item: dict) -> tuple:
    return (
        int(item["id"]),
        item["facility_name"],
        item["category"],
        item["sido"],
        item["sigungu"],
        item["address"],
        float(item["lat"]),
        float(item["lon"]),
        int(item["capacity"]),
        datetime.fromisoformat(item["updated_at"]),
    )
