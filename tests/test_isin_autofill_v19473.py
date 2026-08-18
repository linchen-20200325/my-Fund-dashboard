"""v19.473:選股池「只填代號+ISIN,其餘自動」——晨星名稱自動判幣別 + 回存名稱。

- `_ccy_from_fund_name`:從晨星基金名稱後綴自動判計價幣別(免使用者填)。
- `pool_repository.set_secid(name=...)`:回存 secId 時順手補**空**名稱(不覆蓋使用者已填)。
"""
import pytest

import repositories.pool_repository as P
from repositories.fund.sources import _ccy_from_fund_name
from repositories.pool_repository import LocalJsonPoolStore, PoolEntry


# ── 幣別自動判定(晨星基金名稱後綴)──────────────────────────
@pytest.mark.parametrize("name,expect", [
    ("Allianz Income and Growth AMg7 USD", "USD"),
    ("JPMorgan Global Income A (icdiv) USD hedged", "USD"),
    ("PIMCO GIS Income Fund E EUR Hedged", "EUR"),
    ("某某環球收益基金 台幣避險", "TWD"),
    ("某某環球收益基金 人民幣 級別", "CNY"),
    ("Some Fund AUD", "AUD"),
    ("南非幣計價高收益債", "ZAR"),
    ("No currency token here", ""),          # 抓不到 → ""(呼叫端退 USD)
    ("", ""),
    ("FundName USDX", ""),                    # 詞邊界:USDX 不誤中 USD
])
def test_ccy_from_fund_name(name, expect):
    assert _ccy_from_fund_name(name) == expect


# ── set_secid 回存名稱(只補空名稱,不覆蓋)──────────────────
def test_set_secid_fills_empty_name_and_currency(monkeypatch, tmp_path):
    store = LocalJsonPoolStore(base_dir=tmp_path)
    store.upsert(PoolEntry(code="X", isin="LU0766462157"))   # 只有 ISIN,名稱/幣別空
    monkeypatch.setattr(P, "get_pool_store", lambda: store)
    monkeypatch.setattr(P, "_clear_pool_cache", lambda: None)
    P.set_secid("x", "F00000P8WB", currency="USD", name="Allianz Income USD")
    e = store.list_pool()[0]
    assert e.morningstar_secid == "F00000P8WB"
    assert e.currency == "USD"                                # 自動判到的幣別回填
    assert e.name == "Allianz Income USD"                     # 空名稱 → 補上


def test_set_secid_does_not_overwrite_user_name(monkeypatch, tmp_path):
    store = LocalJsonPoolStore(base_dir=tmp_path)
    store.upsert(PoolEntry(code="X", isin="LU1", name="我自己取的名字"))
    monkeypatch.setattr(P, "get_pool_store", lambda: store)
    monkeypatch.setattr(P, "_clear_pool_cache", lambda: None)
    P.set_secid("X", "SEC", name="Morningstar Auto Name")
    assert store.list_pool()[0].name == "我自己取的名字"        # 使用者已填 → 不覆蓋


def test_set_secid_empty_currency_preserves(monkeypatch, tmp_path):
    store = LocalJsonPoolStore(base_dir=tmp_path)
    store.upsert(PoolEntry(code="X", isin="TW1", currency="TWD"))
    monkeypatch.setattr(P, "get_pool_store", lambda: store)
    monkeypatch.setattr(P, "_clear_pool_cache", lambda: None)
    P.set_secid("X", "SEC")                                   # 沒傳幣別 → 沿用既有 TWD
    assert store.list_pool()[0].currency == "TWD"
