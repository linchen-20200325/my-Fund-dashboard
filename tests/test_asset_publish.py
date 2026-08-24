"""v19.526:infra.asset_publish —— 發佈圖片到 GitHub 公開分支,取 SHA 釘死的 raw 網址。

LINE 圖片訊息只吃公開 HTTPS 網址,故月曆 PNG 需先上傳。本測用假 requester 驗:
分支自動建立、覆寫帶舊 blob sha、網址釘 commit SHA(非分支名,避 CDN 快取舊圖)、
§1 各失敗路徑一律 raise 不回猜的網址。零網路。
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infra.asset_publish import (  # noqa: E402
    AssetPublishError,
    publish_asset,
)

_REPO = "owner/repo"
_TOKEN = "tok"
_PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 200


class _Resp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


def _fake(routes, log=None):
    """routes: {(method, url_path_suffix): _Resp}。比對**去掉 query 後的路徑結尾**(精確,
    避免 `/repos/owner/repo` 誤吃 `/repos/owner/repo/git/ref/heads/main`)。未命中 → 404。"""
    def _req(method, url, *, headers=None, json=None, timeout=None):
        if log is not None:
            log.append({"method": method, "url": url, "json": json, "headers": headers})
        _path = url.split("?")[0]
        for (m, suffix), resp in routes.items():
            if m == method and _path.endswith(suffix):
                return resp(json) if callable(resp) else resp
        return _Resp(404, {"message": "Not Found"})
    return _req


_PATH = "a/b.png"


def _routes_branch_exists(commit_sha="abc123", file_exists=False, path=_PATH):
    r = {
        ("GET", "/git/ref/heads/push-assets"): _Resp(200, {"object": {"sha": "b0"}}),
        ("PUT", f"/contents/{path}"): _Resp(201, {"commit": {"sha": commit_sha}}),
    }
    r[("GET", f"/contents/{path}")] = (_Resp(200, {"sha": "oldblob"}) if file_exists
                                       else _Resp(404, {}))
    return r


# ── 正常路徑 ──────────────────────────────────────────────────────────────
def test_returns_sha_pinned_raw_url():
    _p = "dividend-calendar/2026-09.png"
    url = publish_asset(_PNG, _p, repo=_REPO, token=_TOKEN,
                        _requester=_fake(_routes_branch_exists(path=_p)))
    assert url == "https://raw.githubusercontent.com/owner/repo/abc123/dividend-calendar/2026-09.png"
    assert "push-assets" not in url          # 釘 commit SHA,不可用分支名(CDN 會給舊圖)


def test_uploads_base64_content_to_branch():
    log = []
    publish_asset(_PNG, "a/b.png", repo=_REPO, token=_TOKEN,
                  _requester=_fake(_routes_branch_exists(), log))
    put = [c for c in log if c["method"] == "PUT"][0]
    assert base64.b64decode(put["json"]["content"]) == _PNG    # 內容原樣送出
    assert put["json"]["branch"] == "push-assets"
    assert put["headers"]["Authorization"] == "Bearer tok"
    assert "[skip ci]" in put["json"]["message"]               # 發佈 commit 不觸發 CI


def test_overwrite_passes_existing_blob_sha():
    log = []
    publish_asset(_PNG, "a/b.png", repo=_REPO, token=_TOKEN,
                  _requester=_fake(_routes_branch_exists(file_exists=True), log))
    put = [c for c in log if c["method"] == "PUT"][0]
    assert put["json"]["sha"] == "oldblob"        # 同路徑覆寫必須帶舊 blob sha,否則 GitHub 422


def test_new_file_omits_sha():
    log = []
    publish_asset(_PNG, "a/b.png", repo=_REPO, token=_TOKEN,
                  _requester=_fake(_routes_branch_exists(file_exists=False), log))
    put = [c for c in log if c["method"] == "PUT"][0]
    assert "sha" not in put["json"]               # 新檔不可帶 sha


# ── 分支不存在 → 自動從預設分支建立 ────────────────────────────────────────
def test_creates_branch_when_missing():
    log = []
    routes = {
        ("GET", "/git/ref/heads/push-assets"): _Resp(404, {}),
        ("GET", "/repos/owner/repo"): _Resp(200, {"default_branch": "main"}),
        ("GET", "/git/ref/heads/main"): _Resp(200, {"object": {"sha": "mainsha"}}),
        ("POST", "/git/refs"): _Resp(201, {}),
        ("GET", f"/contents/{_PATH}"): _Resp(404, {}),
        ("PUT", f"/contents/{_PATH}"): _Resp(201, {"commit": {"sha": "newsha"}}),
    }
    url = publish_asset(_PNG, "a/b.png", repo=_REPO, token=_TOKEN,
                        _requester=_fake(routes, log))
    post = [c for c in log if c["method"] == "POST"][0]
    assert post["json"] == {"ref": "refs/heads/push-assets", "sha": "mainsha"}
    assert url.endswith("/newsha/a/b.png")


def test_branch_create_failure_raises():
    routes = {
        ("GET", "/git/ref/heads/push-assets"): _Resp(404, {}),
        ("GET", "/repos/owner/repo"): _Resp(200, {"default_branch": "main"}),
        ("GET", "/git/ref/heads/main"): _Resp(200, {"object": {"sha": "s"}}),
        ("POST", "/git/refs"): _Resp(403, {}, text="forbidden"),
    }
    with pytest.raises(AssetPublishError) as ei:
        publish_asset(_PNG, "a/b.png", repo=_REPO, token=_TOKEN, _requester=_fake(routes))
    assert "建立分支" in str(ei.value)


# ── §1 Fail-Loud:任一失敗都 raise,絕不回猜的網址 ──────────────────────────
def test_empty_data_raises():
    with pytest.raises(AssetPublishError):
        publish_asset(b"", "a/b.png", repo=_REPO, token=_TOKEN)


def test_empty_path_raises():
    with pytest.raises(AssetPublishError):
        publish_asset(_PNG, "   ", repo=_REPO, token=_TOKEN)


def test_missing_credentials_raises():
    import os
    _saved = {k: os.environ.pop(k, None) for k in ("GITHUB_REPOSITORY", "GITHUB_TOKEN")}
    try:
        with pytest.raises(AssetPublishError) as ei:
            publish_asset(_PNG, "a/b.png")
        assert "GITHUB_TOKEN" in str(ei.value)
    finally:
        for k, v in _saved.items():
            if v is not None:
                os.environ[k] = v


def test_put_non_2xx_raises():
    routes = dict(_routes_branch_exists())
    routes[("PUT", f"/contents/{_PATH}")] = _Resp(403, {}, text="permission denied")
    with pytest.raises(AssetPublishError) as ei:
        publish_asset(_PNG, "a/b.png", repo=_REPO, token=_TOKEN, _requester=_fake(routes))
    assert "403" in str(ei.value)


def test_missing_commit_sha_raises_not_branch_url():
    # §1 核心:拿不到 commit sha 就組不出不可變網址 —— 寧可失敗,也不可退用分支名(CDN 舊圖)
    routes = dict(_routes_branch_exists())
    routes[("PUT", f"/contents/{_PATH}")] = _Resp(201, {"commit": {}})
    with pytest.raises(AssetPublishError) as ei:
        publish_asset(_PNG, "a/b.png", repo=_REPO, token=_TOKEN, _requester=_fake(routes))
    assert "commit.sha" in str(ei.value)


def test_oversize_raises():
    with pytest.raises(AssetPublishError):
        publish_asset(b"x" * (26 * 1024 * 1024), "a/b.png", repo=_REPO, token=_TOKEN)


def test_token_not_leaked_in_error():
    routes = dict(_routes_branch_exists())
    routes[("PUT", f"/contents/{_PATH}")] = _Resp(500, {}, text="boom")
    with pytest.raises(AssetPublishError) as ei:
        publish_asset(_PNG, "a/b.png", repo=_REPO, token="SUPERSECRET", _requester=_fake(routes))
    assert "SUPERSECRET" not in str(ei.value)


# ── dry-run:不打 API,且回傳網址明顯是假的(呼叫端不可誤用去推播)──────────────
def test_dry_run_does_not_call_api():
    log = []
    url = publish_asset(_PNG, "a/b.png", repo=_REPO, token=_TOKEN, dry_run=True,
                        _requester=_fake({}, log))
    assert log == []
    assert "DRYRUN" in url
