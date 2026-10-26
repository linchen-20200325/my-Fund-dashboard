"""repositories/personal_drive_repository.py — 假 requests，不連網、不用任何真 token。"""
from __future__ import annotations

import pytest
import requests

from repositories import personal_drive_repository as repo
from shared import ui_v2_error_codes as ec

TOKEN = "fake-access-token-SECRET-123"
SID = "1AbCdEfGhIjKlMnOpQrStUv"


class FakeResp:
    def __init__(self, status=200, body=None, bad_json=False):
        self.status_code = status
        self._body = body
        self._bad = bad_json

    def json(self):
        if self._bad:
            raise ValueError("boom " + TOKEN)  # 刻意把 token 放進內部例外，驗證不外漏
        return self._body


@pytest.fixture
def calls(monkeypatch):
    class Log(list):
        queue: list

    log = Log()
    queue = []

    def fake_get(url, params=None, headers=None, timeout=None, allow_redirects=True):
        log.append({"url": url, "params": dict(params or {}), "headers": headers, "timeout": timeout,
                    "allow_redirects": allow_redirects})
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(repo.requests, "get", fake_get)
    log.queue = queue
    return log


def _meta(title="我的保單", tabs=("A保單", "_持倉補充")):
    return {"properties": {"title": title}, "sheets": [{"properties": {"title": t}} for t in tabs]}


def test_list_分頁排序且token只在header(calls):
    calls.queue += [
        FakeResp(body={"files": [{"id": "b", "name": "B"}, {"id": "a2", "name": "A"}], "nextPageToken": "p2"}),
        FakeResp(body={"files": [{"id": "a1", "name": "A"}]}),
    ]
    out = repo.list_spreadsheets(TOKEN)
    assert out == [{"id": "a1", "name": "A"}, {"id": "a2", "name": "A"}, {"id": "b", "name": "B"}]
    assert len(calls) == 2 and calls[1]["params"]["pageToken"] == "p2"
    for c in calls:
        assert TOKEN not in c["url"] and TOKEN not in repr(c["params"])
        assert c["headers"] == {"Authorization": f"Bearer {TOKEN}"}
        assert c["timeout"] == repo.HTTP_TIMEOUT
        assert "trashed=false" in c["params"]["q"] and "spreadsheet" in c["params"]["q"]


def test_list_空清單是合法的空(calls):
    calls.queue.append(FakeResp(body={}))
    assert repo.list_spreadsheets(TOKEN) == []
    calls.queue.append(FakeResp(body={"files": []}))
    assert repo.list_spreadsheets(TOKEN) == []


@pytest.mark.parametrize("status,code", [
    (401, ec.AUTH_EXPIRED), (403, ec.PERMISSION_DENIED), (404, ec.SHEET_NOT_FOUND),
    (429, ec.UPSTREAM_ERROR), (500, ec.UPSTREAM_ERROR), (503, ec.UPSTREAM_ERROR), (418, ec.UPSTREAM_ERROR),
])
def test_list_與verify_狀態碼對應(calls, status, code):
    calls.queue.append(FakeResp(status=status, body={"error": {"message": "echo " + TOKEN}}))
    with pytest.raises(repo.PersonalDriveError) as ei:
        repo.list_spreadsheets(TOKEN)
    assert ei.value.code == code and TOKEN not in str(ei.value) and "echo" not in str(ei.value)
    calls.queue.append(FakeResp(status=status, body={}))
    r = repo.verify_spreadsheet(TOKEN, SID)
    assert (r.ok, r.error_code) == (False, code)


@pytest.mark.parametrize("exc,code", [
    (requests.Timeout("t " + TOKEN), ec.NETWORK_ERROR),
    (requests.ConnectionError("c " + TOKEN), ec.NETWORK_ERROR),
    (requests.RequestException("x " + TOKEN), ec.UPSTREAM_ERROR),
])
def test_網路例外對應且不外漏token(calls, exc, code):
    calls.queue.append(exc)
    with pytest.raises(repo.PersonalDriveError) as ei:
        repo.list_spreadsheets(TOKEN)
    assert ei.value.code == code
    assert TOKEN not in str(ei.value) and TOKEN not in repr(ei.value)
    calls.queue.append(exc)
    assert repo.verify_spreadsheet(TOKEN, SID).error_code == code


@pytest.mark.parametrize("body", [
    {"files": "nope"}, {"files": [{"id": "a"}]}, {"files": [None]}, {"files": [{"name": "x"}]},
])
def test_list_形狀異常是UPSTREAM(calls, body):
    calls.queue.append(FakeResp(body=body))
    with pytest.raises(repo.PersonalDriveError) as ei:
        repo.list_spreadsheets(TOKEN)
    assert ei.value.code == ec.UPSTREAM_ERROR


def test_非JSON與非dict是UPSTREAM(calls):
    calls.queue.append(FakeResp(bad_json=True))
    with pytest.raises(repo.PersonalDriveError) as ei:
        repo.list_spreadsheets(TOKEN)
    assert ei.value.code == ec.UPSTREAM_ERROR and TOKEN not in str(ei.value)
    calls.queue.append(FakeResp(body=[1, 2]))
    assert repo.verify_spreadsheet(TOKEN, SID).error_code == ec.UPSTREAM_ERROR


def test_list_頁數上限不靜默截斷(calls):
    for _ in range(repo.MAX_PAGES):
        calls.queue.append(FakeResp(body={"files": [], "nextPageToken": "more"}))
    with pytest.raises(repo.PersonalDriveError) as ei:
        repo.list_spreadsheets(TOKEN)
    assert ei.value.code == ec.UPSTREAM_ERROR and len(calls) == repo.MAX_PAGES


def test_空token是AUTH_REQUIRED不發請求(calls):
    with pytest.raises(repo.PersonalDriveError) as ei:
        repo.list_spreadsheets("  ")
    assert ei.value.code == ec.AUTH_REQUIRED and calls == []


def test_verify_成功回名稱(calls):
    calls.queue.append(FakeResp(body=_meta("退休規劃")))
    r = repo.verify_spreadsheet(TOKEN, SID)
    assert r.ok and r.name == "退休規劃"
    c = calls[0]
    assert c["url"].endswith("/" + SID) and TOKEN not in c["url"]
    assert c["params"]["fields"] == "properties.title,sheets.properties.title"
    assert c["headers"] == {"Authorization": f"Bearer {TOKEN}"}


@pytest.mark.parametrize("tabs", [(), ("Policies",), ("_持倉補充", "_保單資料"), ("Policies", "_x")])
def test_verify_缺保單分頁是SCHEMA_INVALID(calls, tabs):
    calls.queue.append(FakeResp(body=_meta(tabs=tabs)))
    r = repo.verify_spreadsheet(TOKEN, SID)
    assert (r.ok, r.error_code) == (False, ec.SCHEMA_INVALID)


@pytest.mark.parametrize("body", [
    {}, {"properties": {}, "sheets": []}, {"properties": {"title": "x"}},
    {"properties": {"title": "x"}, "sheets": [{"properties": {}}]},
])
def test_verify_中繼資料異常是UPSTREAM(calls, body):
    calls.queue.append(FakeResp(body=body))
    assert repo.verify_spreadsheet(TOKEN, SID).error_code == ec.UPSTREAM_ERROR


@pytest.mark.parametrize("bad", [
    "", "a/b", "../x", "short", SID + "?x=1", None,
    "a" * 10 + "/../x", "abc%2F..%2Fabcdefg", "a" * 10 + "\n", "." * 12, "a" * 201,
])
def test_verify_壞ID不發請求(calls, bad):
    r = repo.verify_spreadsheet(TOKEN, bad)
    assert (r.ok, r.error_code) == (False, ec.SHEET_NOT_FOUND) and calls == []


def test_錯誤碼都在九個之內():
    for code in repo._SAFE_MESSAGES:
        assert code in ec.ALL_ERROR_CODES
    with pytest.raises(ValueError):
        repo.PersonalDriveError("MADE_UP")


def test_保單分頁定義與持倉讀取一致():
    H = pytest.importorskip("repositories.policy._helpers")
    assert repo._DEFAULT_POLICY_TAB == H.DEFAULT_WORKSHEET


@pytest.mark.parametrize("exc", [requests.Timeout("t " + TOKEN), requests.ConnectionError("c"), requests.RequestException("x")])
def test_例外鏈不可達_cause與context皆None且suppress(calls, exc):
    exc.request = type("R", (), {"headers": {"Authorization": f"Bearer {TOKEN}"}})()
    calls.queue.append(exc)
    with pytest.raises(repo.PersonalDriveError) as ei:
        repo.list_spreadsheets(TOKEN)
    e = ei.value
    assert e.__cause__ is None and e.__suppress_context__ is True and e.__context__ is None


def test_不跟轉址(calls):
    calls.queue.append(FakeResp(body={}))
    repo.list_spreadsheets(TOKEN)
    assert calls[0]["allow_redirects"] is False
