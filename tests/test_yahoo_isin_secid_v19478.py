"""v19.478:ISIN → Yahoo secId 自動解析(免手填 secId)。

user 2026-08-19:「流程本來就該用代號+星辰自動查,為何要我手填」。晨星 SecuritySearch
從雲端搜不到 → 改用 Yahoo search(v1/finance/search)以 ISIN 對到唯一 `{0P…}.F` symbol
(無級別歧義、雲端可達),讓「代號+ISIN → 自動補 5 年」全自動並回填選股池。

驗證:
- `_yahoo_search_secid_by_isin`:從 quotes 取第一個 `{0P…}.F` → 回 `0P…`;空 ISIN / 無 `.F` /
  urlopen 拋錯 各自處理(§1 暫時失敗不入負快取);cache 命中不重打。
- `_src_yahoo_finance_nav`:池中無 secId → 走 ISIN 解析 + ~~回填 set_secid~~,再打 chart。

⚠️ **2026-09-06 政策變更(有意識的變更,不是漏刪)** · 決策者:**客戶**
(2026-09-06 永久授權:「凡是『查詢/搜尋』功能,一律強制走『純讀取(唯讀)』,
絕對禁止反向寫入我的 Google Sheet。不用問我,直接切斷寫入!」)。
**回填那一半已切除**,本檔對應的斷言隨之翻面(見下方該測試)。
**ISIN → secId 的自動解析、以及用它去抓 chart,一字未動、功能未消失。**
"""
import json

import pandas as pd
import pytest

from repositories.fund import sources as S


def _patch_urlopen(monkeypatch, payload):
    """把 urllib.request.urlopen 換成回傳固定 JSON 的 context manager。"""
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())


@pytest.fixture(autouse=True)
def _clear_cache():
    S._yf_isin_secid_cache.clear()
    yield
    S._yf_isin_secid_cache.clear()


# ── _yahoo_search_secid_by_isin ─────────────────────────────────────────
def test_extracts_0p_secid_from_dotF_symbol(monkeypatch):
    _patch_urlopen(monkeypatch, {"quotes": [
        {"symbol": "SOMEEQUITY", "quoteType": "EQUITY"},
        {"symbol": "0P0001J5YG.F", "quoteType": "MUTUALFUND"},
    ]})
    assert S._yahoo_search_secid_by_isin("LU2023250330") == "0P0001J5YG"
    assert S._yf_isin_secid_cache["LU2023250330"] == "0P0001J5YG"   # 正快取


def test_empty_isin_returns_empty(monkeypatch):
    assert S._yahoo_search_secid_by_isin("") == ""
    assert S._yahoo_search_secid_by_isin("   ") == ""


def test_no_dotF_symbol_negative_cached(monkeypatch):
    _patch_urlopen(monkeypatch, {"quotes": [{"symbol": "AAPL", "quoteType": "EQUITY"}]})
    assert S._yahoo_search_secid_by_isin("LU9999999999") == ""
    assert S._yf_isin_secid_cache["LU9999999999"] == ""              # 確定性查無 → 負快取


def test_transient_failure_not_negative_cached(monkeypatch):
    def _boom(*a, **k):
        raise TimeoutError("yahoo timeout")
    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert S._yahoo_search_secid_by_isin("LU2023250330") == ""
    assert "LU2023250330" not in S._yf_isin_secid_cache             # 暫時失敗不入負快取(可重試)


def test_cache_hit_skips_network(monkeypatch):
    S._yf_isin_secid_cache["LU2023250330"] = "0PCACHED"

    def _should_not_call(*a, **k):
        raise AssertionError("cache 命中不該再打 Yahoo")
    monkeypatch.setattr("urllib.request.urlopen", _should_not_call)
    assert S._yahoo_search_secid_by_isin("LU2023250330") == "0PCACHED"


def test_isin_normalized_upper(monkeypatch):
    _patch_urlopen(monkeypatch, {"quotes": [{"symbol": "0PABC1234X.F"}]})
    assert S._yahoo_search_secid_by_isin(" lu2023250330 ") == "0PABC1234X"
    assert "LU2023250330" in S._yf_isin_secid_cache                 # key 正規化為大寫


# ── _src_yahoo_finance_nav 走 ISIN 自動解析(2026-09-06 起**不再回填**)──────
def test_yahoo_nav_resolves_secid_via_isin_and_does_not_write_back(monkeypatch):
    """ISIN → secId 解析**照舊**;把 secId 回寫進使用者 Google Sheet 的那一半**已切除**。

    ⚠️ **有意識的政策變更,不是漏刪** · 日期 **2026-09-06** · 決策者:**客戶**
       (2026-09-06 永久授權,逐字:「凡是『查詢/搜尋』功能,一律強制走『純讀取(唯讀)』,
        絕對禁止反向寫入我的 Google Sheet。不用問我,直接切斷寫入!」)

    **舊斷言逐字保留於下,加刪除線**:
        ~~def test_yahoo_nav_resolves_secid_via_isin_and_writes_back(monkeypatch):~~
        ~~    _wb = {}~~
        ~~    monkeypatch.setattr(PR, "set_secid",~~
        ~~                        lambda code, secid, **k: _wb.update({"code": code, "secid": secid}))~~
        ~~    …~~
        ~~    assert _wb == {"code": "TLZF9", "secid": "0PFOUND"}   # 回填選股池~~

    **舊斷言的理由仍然成立**:v19.478 要解的是 user 2026-08-19 的
    「流程本來就該用代號+星辰自動查,為何要我手填」—— 第一次解析到 secId 就存回去,
    下次不必再搜一趟,⑤ 設定頁的表格也會自動長出晨星 ID。**那個目的一個字都沒有錯。**
    **被權衡掉的是它的形狀**:那個寫入**綁在「查詢成功」上,不綁在使用者的意圖上** ——
    沒有按鈕、沒有勾選框,而且外面包著 `except Exception: pass`,成功失敗都不上畫面。
    客戶 2026-09-06 禁的正是**查詢的副作用寫入**這個形狀本身,不是寫入的大小。

    **可達性**:2026-09-06 第三組仲裁判定**走得到**(離線寫入哨兵從
    `fetch_fund_from_moneydj_url` 往下實跑,`ws.update` 當場觸發且函式正常回傳)。

    ⚠️ **代價據實寫明**:secId 不再自動回填 → 往後每次符合閘門條件的查詢
    都會**重新解析一次 ISIN→secId**,對外部來源的呼叫次數上升。**這是刻意的代價。**
    📌 **登記(只登記,不動手)**:若要保留自動回填,**正解是改成使用者明示動作**
    (按鈕／表單送出才寫)—— 那會新增視覺元件,須先送客戶線框草稿,不在本批授權內。

    ⛔ 本測試**不刪除**,只翻面 —— 它現在守的是「**不准回寫**」,方向相反、覆蓋同一條路徑。
    """
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "resolve_secid", lambda code: ("", "USD"))   # 池中無 secId
    monkeypatch.setattr(PR, "resolve_isin", lambda code: "LU2023250330")
    _wb = {}
    def _must_not_be_called(code, secid, **k):        # noqa: ANN001 — 哨兵
        _wb.update({"code": code, "secid": secid})
        raise AssertionError(
            f"查詢路徑回寫了選股池:set_secid({code!r}, {secid!r}, **{k!r}) —— "
            f"客戶 2026-09-06:查詢一律唯讀。")
    monkeypatch.setattr(PR, "set_secid", _must_not_be_called)
    monkeypatch.setattr(S, "_yahoo_search_secid_by_isin", lambda isin: "0PFOUND")
    # chart 回 2 筆(secId 已解析 → 進 chart 抓取)
    _patch_urlopen(monkeypatch, {"chart": {"result": [{
        "timestamp": [1700000000, 1700086400],
        "indicators": {"quote": [{"close": [10.5, 11.0]}]},
    }]}})
    out = S._src_yahoo_finance_nav("TLZF9")
    # ⭐ 功能沒有消失:secId 仍由 ISIN 解析出來,而且**本次抓取照舊用它**
    assert len(out) == 2, "切掉回寫之後連 NAV 都抓不到了 → 那是砍功能,不是切副作用"
    # ⭐ 但一格都沒有寫回使用者的表
    assert _wb == {}, f"查詢路徑仍在回寫選股池:{_wb}"


def test_yahoo_nav_no_isin_no_secid_returns_empty(monkeypatch):
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "resolve_secid", lambda code: ("", "USD"))
    monkeypatch.setattr(PR, "resolve_isin", lambda code: "")          # 無 ISIN → 無從解析
    monkeypatch.setattr(S, "_yahoo_search_secid_by_isin",
                        lambda isin: (_ for _ in ()).throw(AssertionError("無 ISIN 不該呼叫")))
    out = S._src_yahoo_finance_nav("NOPE1")
    assert isinstance(out, pd.Series) and out.empty
