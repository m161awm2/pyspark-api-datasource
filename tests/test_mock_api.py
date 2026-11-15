import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mock-api"))


@pytest.fixture()
def api(monkeypatch):
    monkeypatch.setenv("FAIL_RATE", "0")
    monkeypatch.setenv("RATE_LIMIT_RATE", "0")
    monkeypatch.setenv("LATENCY_MS", "0")
    import app

    importlib.reload(app)
    return app, TestClient(app.app)


def _all_rows(client, num_rows=1000):
    rows, page = [], 1
    while True:
        body = client.get("/api/items", params={"pageNo": page, "numOfRows": num_rows}).json()
        if not body["items"]:
            return body, rows
        rows.extend(body["items"])
        page += 1


def test_counts_and_duplicates(api):
    _, client = api
    body, rows = _all_rows(client)
    assert body["totalCount"] == 100_000 and body["duplicateCount"] == 2_000
    assert len(rows) == 100_000
    unique = {tuple(sorted(r.items())) for r in rows}
    assert len(unique) == 98_000


def test_deterministic(api):
    _, client = api
    a = client.get("/api/items", params={"pageNo": 37, "numOfRows": 500}).json()
    b = client.get("/api/items", params={"pageNo": 37, "numOfRows": 500}).json()
    assert a == b


def test_fault_injection(monkeypatch):
    monkeypatch.setenv("FAIL_RATE", "0.5")
    monkeypatch.setenv("RATE_LIMIT_RATE", "0.5")
    monkeypatch.setenv("LATENCY_MS", "0")
    import app

    importlib.reload(app)
    codes = {TestClient(app.app).get("/api/items").status_code for _ in range(50)}
    assert codes <= {429, 500, 503} and 429 in codes
