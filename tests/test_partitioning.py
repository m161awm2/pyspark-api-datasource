import pytest

from public_api_source.partitioning import split_page_ranges, total_pages


def test_total_pages():
    assert total_pages(100_000, 1000) == 100
    assert total_pages(100_001, 1000) == 101
    assert total_pages(0, 1000) == 0


def test_split_100_pages_into_3():
    assert split_page_ranges(100, 3) == [(1, 34), (35, 67), (68, 100)]


@pytest.mark.parametrize("pages,n", [(1, 3), (2, 3), (7, 3), (100, 1), (101, 7), (10, 10)])
def test_split_covers_all_pages_contiguously(pages, n):
    ranges = split_page_ranges(pages, n)
    assert len(ranges) == min(pages, n)
    covered = [p for s, e in ranges for p in range(s, e + 1)]
    assert covered == list(range(1, pages + 1))
    sizes = [e - s + 1 for s, e in ranges]
    assert max(sizes) - min(sizes) <= 1


def test_split_empty():
    assert split_page_ranges(0, 3) == []
