import pytest
import requests

from public_api_source.http_client import PageClient, PageFetchError, RetryPolicy


class FakeResp:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self._body = body or {}
        self.headers = headers or {}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


OK = FakeResp(200, {"totalCount": 1, "items": [{"id": 1}]})


def make_client(script, max_retries=5):
    sleeps = []
    client = PageClient(
        "http://x/api/items",
        policy=RetryPolicy(max_retries=max_retries, backoff_base=0.01, backoff_cap=0.05),
        sleep=sleeps.append,
        session=FakeSession(script),
    )
    return client, sleeps


def test_success_first_try():
    client, sleeps = make_client([OK])
    assert client.fetch(1, 10)["items"] == [{"id": 1}]
    assert sleeps == [] and client.retries_used == 0


def test_retries_on_5xx_and_connection_errors():
    client, sleeps = make_client([FakeResp(500), requests.ConnectionError("boom"), FakeResp(503), OK])
    assert client.fetch(1, 10)["totalCount"] == 1
    assert client.retries_used == 3 and len(sleeps) == 3


def test_respects_retry_after_on_429():
    client, sleeps = make_client([FakeResp(429, headers={"Retry-After": "2"}), OK])
    client.fetch(1, 10)
    assert sleeps[0] >= 2


def test_gives_up_after_max_retries():
    client, sleeps = make_client([FakeResp(503)] * 4, max_retries=3)
    with pytest.raises(PageFetchError, match="gave up after 4 attempts"):
        client.fetch(7, 10)
    assert client.session.calls == 4 and len(sleeps) == 3


def test_non_retryable_status_fails_fast():
    client, sleeps = make_client([FakeResp(400)])
    with pytest.raises(PageFetchError, match="non-retryable"):
        client.fetch(1, 10)
    assert sleeps == []


def test_malformed_body_is_retried():
    client, _ = make_client([FakeResp(200, {"oops": 1}), OK])
    assert client.fetch(1, 10)["totalCount"] == 1
