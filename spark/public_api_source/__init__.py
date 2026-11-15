"""공공데이터 페이징 API 용 Spark Python Data Source 패키지.

pyspark 의존 클래스는 지연 import 하여, 순수 로직(http_client, partitioning)은 pyspark 없이 테스트할 수 있다.
"""


def __getattr__(name):
    if name in ("PublicApiDataSource", "PublicApiReader", "PageRangePartition"):
        from . import datasource

        return getattr(datasource, name)
    raise AttributeError(name)


__all__ = ["PublicApiDataSource", "PublicApiReader", "PageRangePartition"]
