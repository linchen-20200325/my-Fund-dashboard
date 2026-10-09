"""MoneyDJ legacy 爬蟲 meta 段的基金類別 —— `fetch_fund_from_moneydj_url` 第三個寫入點。

病徵:多來源主路徑失敗、落到 legacy 爬蟲時,原寫法
`rows_map.get("投資標的", rows_map.get("基金類型", ""))` 會把「投資標的」的
公開說明書長描述整段寫進 category;下游 `services.regime_fit.asset_bucket`
是子字串首命中,於是台股股票型基金被判成「原物料資源」。
修法:改用同套件既有的 `_pick_fund_category`(另兩個寫入點早已使用)。

毒樣本從 repo 內 `snap.json` 讀取(真實資料,不手抄);全程替身,不打網路。
"""
from __future__ import annotations

import json
import pathlib

import pytest

import fund_fetcher  # noqa: F401 — conftest 同款 prime(循環 import)

from repositories.fund.sources import _pick_fund_category
from services.regime_fit import asset_bucket

_SNAP = pathlib.Path(__file__).resolve().parent.parent / "snap.json"


def _poison() -> str:
    """snap.json 中 ACDD01(台股股票基金)被寫進 category 的說明書長描述。"""
    data = json.loads(_SNAP.read_text(encoding="utf-8"))
    text = data["funds"]["ACDD01"]["category"]
    assert len(text) > 15, "毒樣本不是長描述,本檔的正例會空轉"
    return text


class _Resp:
    status_code = 200

    def __init__(self, text: str) -> None:
        self.text = text

    @property
    def content(self) -> bytes:
        return self.text.encode()


def _info_page(rows: list[tuple[str, str]]) -> str:
    trs = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)
    # 該路徑要求 len(r.text) > 500 才解析
    return "<html><body><table>" + trs + "</table></body></html>" + ("&nbsp;" * 400)


def _run(monkeypatch, extra_rows: list[tuple[str, str]]) -> dict:
    """主路徑回空 dict → 走 legacy 段;所有對外呼叫一律替身。"""
    import requests

    import repositories.fund.fund_orchestration as FO

    def _no_net(*a, **k):
        raise AssertionError("測試不得打網路")

    monkeypatch.setattr(requests, "get", _no_net)
    monkeypatch.setattr(requests, "post", _no_net)
    monkeypatch.setattr(requests.Session, "request", _no_net)

    rows = [("基金名稱", "測試基金A"), ("計價幣別", "TWD"),
            ("投資區域", "台灣"), ("風險報酬等級", "RR5")] + extra_rows
    page = _info_page(rows)
    monkeypatch.setattr(FO, "fetch_url_with_retry", lambda u, **k: _Resp(page))
    monkeypatch.setattr(FO, "fetch_fund_multi_source", lambda *a, **k: {})
    for n in ("fetch_holdings", "fetch_risk_metrics", "fetch_performance_wb01",
              "fetch_dividends", "fetch_nav"):
        monkeypatch.setattr(FO, n, lambda *a, **k: {}, raising=False)
    monkeypatch.setattr(FO, "_ensure_holdings", lambda *a, **k: None, raising=False)
    res = FO.fetch_fund_from_moneydj_url("ACDD01")
    # 反空轉:確認真的走進 legacy meta 段(該段才會寫 fund_name / fund_region)
    assert res.get("fund_name") == "測試基金A"
    assert res.get("fund_region") == "台灣"
    return res


# ── 正例 ──

def test_poison_is_actually_toxic():
    """反空轉:毒樣本本身確實會被 asset_bucket 判成原物料資源(即線上病徵)。"""
    assert asset_bucket(_poison())[0] == "原物料資源"


def test_long_target_with_fund_type_yields_short_category(monkeypatch):
    poison = _poison()
    res = _run(monkeypatch, [("投資標的", poison), ("基金類型", "股票型")])
    assert res["category"] == "股票型"
    assert asset_bucket(res["category"])[0] != "原物料資源"
    assert asset_bucket(res["category"])[0] == "股票"
    # 該行之後的 meta 仍寫入(若該行拋 NameError 會被外層 except 吞掉,整段消失)
    assert res.get("fund_type") == "股票型"
    assert res.get("fund_region") == "台灣"


def test_category_matches_helper_on_same_rows(monkeypatch):
    """與另兩個寫入點同一裁決:對同一份 rows_map 結果必須等於 helper。"""
    poison = _poison()
    res = _run(monkeypatch, [("投資標的", poison), ("基金類型", "股票型")])
    assert res["category"] == _pick_fund_category({"投資標的": poison, "基金類型": "股票型"})


# ── 反例 / 邊界 ──

def test_only_short_target_is_used(monkeypatch):
    res = _run(monkeypatch, [("投資標的", "全球股票")])
    assert res["category"] == "全球股票"


def test_both_missing_gives_empty_not_fake(monkeypatch):
    res = _run(monkeypatch, [])
    assert res["category"] == ""


@pytest.mark.parametrize("target,expected", [
    ("全球股票", "全球股票"),   # 短投資標的照用
    (None, ""),                 # 長描述 + 基金類型空 → 寧可空,不吐長文
])
def test_empty_fund_type(monkeypatch, target, expected):
    t = _poison() if target is None else target
    res = _run(monkeypatch, [("投資標的", t), ("基金類型", "")])
    assert res["category"] == expected
