"""v19.505:健診抓取接上池 ISIN/secid + 幣別修正(user 2026-08-21 回報 週資料不足 + 台幣當美元)。

A:_pool_secid_or_isin —— 池有 secid/isin → 開 Morningstar 全歷史閘門(不限保單前綴)。
B:_correct_currency —— 境內基金矇 USD 死預設 → 用名稱/池/台灣推定修回台幣;真美元/EUR 不動。
"""
import pytest
import repositories.fund.fund_orchestration as O
import repositories.pool_repository as PR


# ── A:_pool_secid_or_isin 閘門 ─────────────────────────────────────────────
def test_pool_secid_opens_gate(monkeypatch):
    monkeypatch.setattr(PR, "resolve_secid", lambda c: ("F00000XXXX", "USD"))
    monkeypatch.setattr(PR, "resolve_isin", lambda c: None)
    assert O._pool_secid_or_isin("ACDD19") is True


def test_pool_isin_opens_gate_when_no_secid(monkeypatch):
    monkeypatch.setattr(PR, "resolve_secid", lambda c: None)
    monkeypatch.setattr(PR, "resolve_isin", lambda c: "LU0766462157")
    assert O._pool_secid_or_isin("ALZF9") is True


def test_no_pool_secid_or_isin_gate_closed(monkeypatch):
    monkeypatch.setattr(PR, "resolve_secid", lambda c: None)
    monkeypatch.setattr(PR, "resolve_isin", lambda c: None)
    assert O._pool_secid_or_isin("PYZW3") is False


def test_empty_code_gate_closed():
    assert O._pool_secid_or_isin("") is False
    assert O._pool_secid_or_isin(None) is False


def test_pool_read_raises_gate_conservative_false(monkeypatch):
    def _boom(c):
        raise RuntimeError("GS down")
    monkeypatch.setattr(PR, "resolve_secid", _boom)
    monkeypatch.setattr(PR, "resolve_isin", _boom)
    assert O._pool_secid_or_isin("ACDD19") is False   # 池炸不得擋抓取 → False


# ── B:_correct_currency ────────────────────────────────────────────────────
def _no_pool(monkeypatch):
    monkeypatch.setattr(PR, "resolve_currency", lambda c: "")


def test_name_taiwan_dollar_token_to_twd(monkeypatch):
    _no_pool(monkeypatch)
    # 名稱含「台幣」→ TWD(_ccy_from_fund_name 命中)
    assert O._correct_currency("USD", "安聯台灣大壩基金-A累積型(台幣)", "ACDD01") == "TWD"


def test_name_taiwan_only_infers_twd(monkeypatch):
    _no_pool(monkeypatch)
    # 名稱只有「台灣」無外幣字樣 → 台股基金推定 TWD(修 ACDD19 的關鍵)
    assert O._correct_currency("USD", "安聯台灣智慧基金", "ACDD19") == "TWD"


def test_name_usd_token_stays_usd(monkeypatch):
    _no_pool(monkeypatch)
    # 名稱明確「美元」的組合基金 → 名稱幣別=USD == cur → 不動,不誤判台幣
    assert O._correct_currency("USD", "瀚亞多重收益優化組合基金B配息(美元)", "ACCP138") == "USD"


def test_pool_currency_used_when_name_silent(monkeypatch):
    # 名稱無幣別無台灣 → 用池 currency
    monkeypatch.setattr(PR, "resolve_currency", lambda c: "TWD")
    assert O._correct_currency("USD", "某某基金", "XY01") == "TWD"


def test_explicit_eur_untouched(monkeypatch):
    _no_pool(monkeypatch)
    # 已是明確非空非 USD 幣別 → 完全不動(不覆蓋真幣別)
    assert O._correct_currency("EUR", "PIMCO GIS Income EUR", "PIMEUR") == "EUR"


def test_usd_no_signal_stays_usd(monkeypatch):
    _no_pool(monkeypatch)
    # cur=USD、名稱/池/台灣都無訊號 → 保守維持 USD(不拿 TWD 猜可能的真美元)
    assert O._correct_currency("USD", "Some Global Bond Fund", "GBOND") == "USD"


def test_empty_stays_empty_when_unknown(monkeypatch):
    _no_pool(monkeypatch)
    # cur 空、完全無訊號 → 回空(交 fund_row 誠實報「幣別未知」§1,不矇 USD)
    assert O._correct_currency("", "Mystery Fund", "MYST") == ""


def test_pool_read_raises_currency_degrades(monkeypatch):
    def _boom(c):
        raise RuntimeError("GS down")
    monkeypatch.setattr(PR, "resolve_currency", _boom)
    # 池炸 → 名稱台灣推定仍生效,不整組炸
    assert O._correct_currency("USD", "安聯台灣智慧基金", "ACDD19") == "TWD"


# ── B2:_ensure_currency 外層收口(稽核 High 盲點:protect loop 蓋回假 USD 後再修)──
def test_ensure_currency_corrects_usd_taiwan_on_final_result(monkeypatch):
    """~~模擬:direct_url 注入 USD → protect loop 存回 → 收口 _ensure_currency 修成 TWD。~~

    → 2026-10-10 客戶裁示 C2-1(**有意識的政策變更,不是漏刪**):名稱 /「台灣」推定與
    選股池幣別不算可信證據,不得寫進 L1 結果 `currency`(下游當來源宣告、Tab3 會寫回 Sheet)。
    舊理由(direct_url 缺欄 USD 死預設)仍然成立,但已由取數源頭「缺欄 → 空白」處理;
    被權衡掉的是「用推定覆蓋宣告值」這個手段。來源宣告 USD → 保留 USD。"""
    monkeypatch.setattr(PR, "resolve_currency", lambda c: "TWD")       # 池有值也不採
    r = {"currency": "USD", "fund_name": "安聯台灣智慧基金"}
    O._ensure_currency(r, "ACDD19")
    assert r["currency"] == "USD"
    r2 = {"currency": "", "fund_name": "安聯台灣智慧基金"}               # 宣告空 → 不推定
    O._ensure_currency(r2, "ACDD19")
    assert r2["currency"] == ""


@pytest.mark.parametrize("raw, code, want", [
    ("美元", "ZZZE1", "USD"),     # 格式正規化
    ("日幣", "ZZZE1", "日幣"),     # L1 別名表沒收 → 保留來源原字(交 L2 正規化)
    ("", "TLZF9", "USD"),         # 宣告空 → 晨星硬編表
    ("", "ZZZE1", ""),            # 皆無 → 未知
])
def test_ensure_currency_declared_or_table_only(monkeypatch, raw, code, want):
    monkeypatch.setattr(PR, "resolve_currency", lambda c: "TWD")
    r = {"currency": raw, "fund_name": "某某台灣基金"}
    O._ensure_currency(r, code)
    assert r["currency"] == want


def test_ensure_currency_leaves_real_usd_untouched(monkeypatch):
    monkeypatch.setattr(PR, "resolve_currency", lambda c: "")
    r = {"currency": "USD", "fund_name": "瀚亞多重收益優化組合基金B配息(美元)"}
    O._ensure_currency(r, "ACCP138")
    assert r["currency"] == "USD"      # 名稱美元 → 維持 USD,不誤判


def test_ensure_currency_idempotent_on_twd(monkeypatch):
    monkeypatch.setattr(PR, "resolve_currency", lambda c: "")
    r = {"currency": "TWD", "fund_name": "安聯台灣智慧基金"}
    O._ensure_currency(r, "ACDD19")
    assert r["currency"] == "TWD"      # 已 TWD → 冪等不動


def test_ensure_currency_pool_read_raises_no_crash(monkeypatch):
    def _boom(c):
        raise RuntimeError("GS down")
    monkeypatch.setattr(PR, "resolve_currency", _boom)
    r = {"currency": "USD", "fund_name": "安聯台灣智慧基金"}
    O._ensure_currency(r, "ACDD19")     # 不得拋
    # ~~assert r["currency"] == "TWD"  # 名稱台灣推定仍生效~~ → C2-1:不推定,來源 USD 保留
    assert r["currency"] == "USD"
