"""전체 페이지를 연속 구간으로 나누는 순수 로직 (Driver 에서 실행)."""

from __future__ import annotations

import math


def total_pages(total_count: int, num_rows: int) -> int:
    if num_rows <= 0:
        raise ValueError("num_rows must be positive")
    return math.ceil(total_count / num_rows) if total_count > 0 else 0


def split_page_ranges(pages: int, num_partitions: int) -> list[tuple[int, int]]:
    """1..pages 를 최대 num_partitions 개의 연속 구간 [start, end] (양끝 포함)으로 나눈다.

    구간 크기 차이는 최대 1. 예) pages=100, n=3 → [(1,34), (35,67), (68,100)]
    """
    if num_partitions <= 0:
        raise ValueError("num_partitions must be positive")
    if pages <= 0:
        return []
    n = min(num_partitions, pages)
    base, extra = divmod(pages, n)
    ranges, start = [], 1
    for idx in range(n):
        size = base + (1 if idx < extra else 0)
        ranges.append((start, start + size - 1))
        start += size
    return ranges
