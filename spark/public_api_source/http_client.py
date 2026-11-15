"""재시도(지수 백오프 + jitter, Retry-After 존중)를 포함한 페이지 조회 클라이언트."""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Callable

import requests

log = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class PageFetchError(RuntimeError):
    """최대 재시도 후에도 페이지 조회에 실패했을 때. Spark 태스크를 실패시키기 위해 그대로 전파한다."""


@dataclass
class RetryPolicy:
    max_retries: int = 5          # 최초 시도 이후 추가 시도 횟수
    backoff_base: float = 0.5     # 초
    backoff_cap: float = 10.0     # 초
    timeout: float = 10.0         # 요청당 타임아웃(초)

    def backoff(self, attempt: int, retry_after: float | None = None) -> float:
        """attempt 는 0부터. Retry-After 가 있으면 그 값과 지수 백오프 중 큰 값을 쓴다."""
        exp = min(self.backoff_cap, self.backoff_base * (2 ** attempt))
        delay = random.uniform(exp / 2, exp)  # equal jitter
        if retry_after is not None:
            delay = max(delay, retry_after)
        return delay


@dataclass
class PageClient:
    base_url: str
    policy: RetryPolicy = field(default_factory=RetryPolicy)
    sleep: Callable[[float], None] = time.sleep
    session: requests.Session = field(default_factory=requests.Session)
    retries_used: int = 0

    def fetch(self, page_no: int, num_rows: int) -> dict:
        params = {"pageNo": page_no, "numOfRows": num_rows}
        last_error: str = ""
        for attempt in range(self.policy.max_retries + 1):
            retry_after: float | None = None
            try:
                resp = self.session.get(self.base_url, params=params, timeout=self.policy.timeout)
                if resp.status_code == 200:
                    body = resp.json()
                    if "items" not in body or "totalCount" not in body:
                        raise ValueError(f"malformed response keys={sorted(body)}")
                    return body
                last_error = f"HTTP {resp.status_code}"
                if resp.status_code not in RETRYABLE_STATUS:
                    raise PageFetchError(f"page {page_no}: non-retryable {last_error}")
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
            except (requests.ConnectionError, requests.Timeout, ValueError) as e:
                last_error = f"{type(e).__name__}: {e}"

            if attempt == self.policy.max_retries:
                break
            delay = self.policy.backoff(attempt, retry_after)
            self.retries_used += 1
            log.warning("page %d attempt %d failed (%s); retry in %.2fs", page_no, attempt + 1, last_error, delay)
            self.sleep(delay)

        raise PageFetchError(
            f"page {page_no}: gave up after {self.policy.max_retries + 1} attempts (last: {last_error})"
        )


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
