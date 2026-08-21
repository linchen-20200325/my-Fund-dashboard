"""v19.508:選股池 SA→OAuth 寫入回退(手機免設 Service Account)。

user 2026-08-21「都用手機 沒有電腦」:SA 缺時,UI 注入登入者的 OAuth gspread client,
選股池即用使用者身分讀寫 Google Sheet(跨 reboot 永久保存,不再只落會被清空的本地暫存)。

守住的關鍵不變量(mirror task #43 Tab3 SA→OAuth 回退):
  - **SA 優先**:SA 在 → 用 SA,完全不碰注入的 OAuth。
  - **429/配額不降級**:SA 開表遇配額錯 → 往上拋(§1),不誤判成 SA 壞掉而降級。
  - **SA 未分享(403)且有注入 OAuth** → 改用使用者身分。
  - **兩者皆無** → 明確 raise(不靜默假裝空)。
  - headless/cron(不傳 oauth_client)→ 純 SA / 本地,零 regression。
"""
import pytest

import repositories.pool_repository as P


class _FakeClient:
    """假 gspread client:記錄 open_by_key 呼叫;可設定拋特定例外。"""
    def __init__(self, name, exc=None):
        self.name = name
        self.exc = exc
        self.opened = []

    def open_by_key(self, sid):
        self.opened.append(sid)
        if self.exc:
            raise self.exc
        return f"SHEET::{self.name}::{sid}"


def _sa(monkeypatch, present):
    monkeypatch.setattr(P, "_sa_present", lambda: present)
    monkeypatch.setattr(P, "_pool_sheet_id", lambda: "BOOK1")


def _wire_sa_client(monkeypatch, client):
    monkeypatch.setattr("infra.config.require_secret", lambda k: {"client_email": "sa@x.iam"})
    monkeypatch.setattr("repositories.policy_repository.get_gspread_client", lambda creds: client)


# ── SA-first 不變量 ──────────────────────────────────────────
def test_sa_present_uses_sa_and_ignores_oauth(monkeypatch):
    sa, oauth = _FakeClient("SA"), _FakeClient("OAUTH")
    _sa(monkeypatch, True)
    _wire_sa_client(monkeypatch, sa)
    assert P._get_sheet(oauth_client=oauth) == "SHEET::SA::BOOK1"
    assert oauth.opened == []                       # ★ SA 在 → OAuth 完全沒被碰


# ── SA 缺 → 用注入的 OAuth ───────────────────────────────────
def test_sa_absent_uses_injected_oauth(monkeypatch):
    oauth = _FakeClient("OAUTH")
    _sa(monkeypatch, False)
    assert P._get_sheet(oauth_client=oauth) == "SHEET::OAUTH::BOOK1"


# ── 429/配額不降級(§1 往上拋,不誤判 SA 壞)────────────────────
def test_sa_quota_error_does_not_fall_back(monkeypatch):
    quota = RuntimeError("429 quota exceeded")
    sa, oauth = _FakeClient("SA", exc=quota), _FakeClient("OAUTH")
    _sa(monkeypatch, True)
    _wire_sa_client(monkeypatch, sa)
    monkeypatch.setattr("infra.gspread_retry.is_quota_error", lambda e: True)
    with pytest.raises(RuntimeError, match="429"):
        P._get_sheet(oauth_client=oauth)
    assert oauth.opened == []                       # ★ 配額錯不可降級


# ── SA 未分享(403 非配額)且有 OAuth → 降級到使用者身分 ──────────
def test_sa_403_falls_back_to_oauth(monkeypatch):
    sa, oauth = _FakeClient("SA", exc=PermissionError("403 not shared")), _FakeClient("OAUTH")
    _sa(monkeypatch, True)
    _wire_sa_client(monkeypatch, sa)
    monkeypatch.setattr("infra.gspread_retry.is_quota_error", lambda e: False)
    assert P._get_sheet(oauth_client=oauth) == "SHEET::OAUTH::BOOK1"
    assert sa.opened == ["BOOK1"] and oauth.opened == ["BOOK1"]   # SA 先試、失敗才換 OAuth


# ── SA 未分享但無 OAuth 可退 → 明確 raise(§1 不靜默)─────────────
def test_sa_403_without_oauth_raises_loud(monkeypatch):
    sa = _FakeClient("SA", exc=PermissionError("403 not shared"))
    _sa(monkeypatch, True)
    _wire_sa_client(monkeypatch, sa)
    monkeypatch.setattr("infra.gspread_retry.is_quota_error", lambda e: False)
    with pytest.raises(PermissionError):
        P._get_sheet(oauth_client=None)


# ── 兩者皆無 → 明確 raise(防禦;正常 is_available 先擋)──────────
def test_no_creds_raises(monkeypatch):
    _sa(monkeypatch, False)
    with pytest.raises(RuntimeError, match="無可用憑證"):
        P._get_sheet(oauth_client=None)


# ── store.is_available:SA 或 OAuth 任一在即 True ─────────────────
def test_store_is_available_reflects_sa_or_oauth(monkeypatch):
    _sa(monkeypatch, False)
    assert P.GoogleSheetsPoolStore().is_available() is False            # 無 SA 無 OAuth
    assert P.GoogleSheetsPoolStore(oauth_client=object()).is_available() is True   # 有 OAuth
    _sa(monkeypatch, True)
    assert P.GoogleSheetsPoolStore().is_available() is True             # 有 SA


# ── get_pool_store:SA 缺 + 無 OAuth → 本地;SA 缺 + 有 OAuth → GS ──
def test_get_pool_store_local_when_no_creds(monkeypatch, tmp_path):
    _sa(monkeypatch, False)
    monkeypatch.setattr(P, "_CACHE_DIR", tmp_path)      # 別碰 repo 真 cache 夾
    assert isinstance(P.get_pool_store(oauth_client=None), P.LocalJsonPoolStore)


def test_get_pool_store_gs_when_oauth_injected(monkeypatch):
    oauth = _FakeClient("OAUTH")
    _sa(monkeypatch, False)
    store = P.get_pool_store(oauth_client=oauth)
    assert isinstance(store, P.GoogleSheetsPoolStore) and store._oauth_client is oauth


# ── 便利函式把 oauth_client 透傳到 get_pool_store ────────────────
def test_convenience_fns_thread_oauth(monkeypatch):
    captured = {}

    class _S:
        def list_pool(self):
            return ["POOL"]

        def upsert(self, e):
            captured["upserted"] = e

        def remove(self, c):
            captured["removed"] = c

    def _fake_store(oauth_client=None):
        captured.setdefault("oauth_seen", []).append(oauth_client)
        return _S()

    monkeypatch.setattr(P, "get_pool_store", _fake_store)
    monkeypatch.setattr(P, "_clear_pool_cache", lambda: None)
    s1, s2, s3 = object(), object(), object()
    assert P.list_pool(oauth_client=s1) == ["POOL"]
    P.add_or_update(P.PoolEntry(code="X"), oauth_client=s2)
    P.remove_from_pool("X", oauth_client=s3)
    assert captured["oauth_seen"] == [s1, s2, s3]       # 三個 write/read 都透傳


# ── pool_backend_status:UI 用來誠實提示落到哪個後端(§1 防靜默存本地)──────
def test_pool_backend_status(monkeypatch):
    monkeypatch.setattr(P, "_sa_present", lambda: True)
    assert P.pool_backend_status(None) == "service_account"        # SA 在 → 永久
    assert P.pool_backend_status(object()) == "service_account"    # SA 優先(即便有 OAuth)
    monkeypatch.setattr(P, "_sa_present", lambda: False)
    assert P.pool_backend_status(object()) == "oauth"              # SA 缺 + OAuth → 永久(雲端)
    assert P.pool_backend_status(None) == "local"                  # 兩者皆無 → 本地暫存(UI 須警告)


# ── headless 預設(不傳)→ oauth_client=None(零 regression)──────
def test_default_no_oauth_is_none(monkeypatch):
    seen = {}
    monkeypatch.setattr(P, "get_pool_store",
                        lambda oauth_client=None: seen.setdefault("v", oauth_client) or _Empty())

    class _Empty:
        def list_pool(self):
            return []

    P.list_pool()
    assert seen["v"] is None                            # 便利函式預設不注入 OAuth
