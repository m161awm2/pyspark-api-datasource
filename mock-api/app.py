"""Mock 공공데이터 API (전국 공공시설 정보).

- 결정적 데이터: 같은 (pageNo, numOfRows) 요청은 항상 같은 items 를 돌려준다.
- 의도적 중복: 행 인덱스 i 가 `i % DUP_EVERY == DUP_EVERY - 1` 이면 직전 행(i-1)의 완전한 복사본.
  TOTAL_COUNT=100000, DUP_EVERY=50 이면 duplicateCount=2000, 고유 건수=98000.
- 장애 주입: FAIL_RATE(500/503), RATE_LIMIT_RATE(429 + Retry-After), LATENCY_MS(min~max 지연).
"""

from __future__ import annotations

import asyncio
import os
import random
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

TOTAL_COUNT = int(os.getenv("TOTAL_COUNT", "100000"))
DUP_EVERY = int(os.getenv("DUP_EVERY", "50"))
SEED = int(os.getenv("SEED", "42"))
FAIL_RATE = float(os.getenv("FAIL_RATE", "0.05"))
RATE_LIMIT_RATE = float(os.getenv("RATE_LIMIT_RATE", "0.02"))
RETRY_AFTER_SECONDS = int(os.getenv("RETRY_AFTER_SECONDS", "1"))
_lat = os.getenv("LATENCY_MS", "50-200").split("-")
LATENCY_MIN_MS, LATENCY_MAX_MS = int(_lat[0]), int(_lat[-1])
MAX_ROWS_PER_PAGE = 10_000

DUPLICATE_COUNT = TOTAL_COUNT // DUP_EVERY if DUP_EVERY > 0 else 0

CATEGORIES = ["도서관", "체육관", "공원", "주민센터", "보건소", "박물관", "주차장", "어린이집"]
REGIONS = {
    "서울특별시": ["강남구", "종로구", "마포구", "송파구", "노원구"],
    "부산광역시": ["해운대구", "부산진구", "동래구", "사하구"],
    "대구광역시": ["수성구", "달서구", "중구"],
    "인천광역시": ["연수구", "남동구", "부평구"],
    "경기도": ["수원시", "성남시", "고양시", "용인시", "화성시"],
    "강원특별자치도": ["춘천시", "원주시", "강릉시"],
    "제주특별자치도": ["제주시", "서귀포시"],
}
SIDO_LIST = list(REGIONS)
BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)

app = FastAPI(title="Mock Public Data API")


def unique_index(i: int) -> int:
    """행 인덱스 i(0-based) → 고유 레코드 인덱스. 중복 행은 직전 행과 같은 값을 갖는다."""
    if DUP_EVERY <= 0:
        return i
    return i - (i + 1) // DUP_EVERY


def make_record(u: int) -> dict:
    rnd = random.Random(SEED * 1_000_003 + u)
    sido = rnd.choice(SIDO_LIST)
    sigungu = rnd.choice(REGIONS[sido])
    category = rnd.choice(CATEGORIES)
    return {
        "id": u + 1,
        "facility_name": f"{sigungu} {category} {u + 1:06d}",
        "category": category,
        "sido": sido,
        "sigungu": sigungu,
        "address": f"{sido} {sigungu} 공공로 {rnd.randint(1, 999)}",
        "lat": round(rnd.uniform(33.1, 38.6), 6),
        "lon": round(rnd.uniform(124.6, 131.9), 6),
        "capacity": rnd.randint(10, 5000),
        "updated_at": (BASE_TIME + timedelta(seconds=rnd.randint(0, 300 * 86400))).isoformat(),
    }


def page_items(page_no: int, num_rows: int) -> list[dict]:
    start = (page_no - 1) * num_rows
    end = min(start + num_rows, TOTAL_COUNT)
    return [make_record(unique_index(i)) for i in range(start, end)]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/items")
async def items(
    pageNo: int = Query(1, ge=1),
    numOfRows: int = Query(1000, ge=1, le=MAX_ROWS_PER_PAGE),
):
    await asyncio.sleep(random.uniform(LATENCY_MIN_MS, LATENCY_MAX_MS) / 1000)

    roll = random.random()
    if roll < FAIL_RATE:
        code = random.choice([500, 503])
        return JSONResponse(status_code=code, content={"resultCode": "99", "resultMsg": "INJECTED_FAILURE"})
    if roll < FAIL_RATE + RATE_LIMIT_RATE:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
            content={"resultCode": "22", "resultMsg": "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS"},
        )

    return {
        "totalCount": TOTAL_COUNT,
        "duplicateCount": DUPLICATE_COUNT,
        "pageNo": pageNo,
        "numOfRows": numOfRows,
        "items": page_items(pageNo, numOfRows),
    }
