"""第一波 資料真實性：**同源假訊號**盤點的漂移鎖（只記錄事實，不改判定邏輯）。

背景
----
「同源假訊號」＝ 多顆指標看起來互相印證，實際上共用同一個上游序列，
等於同一個數字被數了很多次。本 repo **已經**有兩套去重機制：
  * `superseded_by`（主/備同源，例：M2SL 月頻 vs WM2NS 週頻）
  * `turning_points.indicator_key`（訊號層 ↔ 拐點層跨層去重）
本檔鎖的是**這兩套都沒有涵蓋到**的殘餘同源群組（2026-08-27 盤點）。

⚠️ 本檔**不主張**這些一定要去重 —— 去重會改變客戶收到的建議（權重/判定），
屬業務規則，需另案請示。本檔只確保：**這些事實一旦改變，有人會被迫更新盤點。**
若你已把某一組去重了 → 請一併更新本檔與交付報告，不要只把 assert 改掉。
"""
import re
from pathlib import Path

import pytest

_SRC = (Path(__file__).resolve().parent.parent
        / "services" / "macro" / "us_indicators.py").read_text(encoding="utf-8")
_TP = (Path(__file__).resolve().parent.parent
       / "services" / "macro" / "turning_points.py").read_text(encoding="utf-8")


# ── 群組 A：兩條殖利率利差共用 DGS10 這條腿 ───────────────────────
def test_two_yield_spreads_share_the_dgs10_leg():
    """10Y-2Y 與 10Y-3M 的被減數是同一個 df10（DGS10）。"""
    assert "sp22 = _spread_series(df10, df2," in _SRC
    assert "sp3m = _spread_series(df10, df3m," in _SRC
    assert '_safe_fred_result(_f_d10, "DGS10")' in _SRC


def test_two_yield_spreads_are_not_deduped():
    """兩顆都沒掛 superseded_by，且權重都是 2 → 同向時對總分貢獻 ±4。"""
    for key in ("YIELD_10Y2Y", "YIELD_10Y3M"):
        blk = _SRC.split(f'R["{key}"] = dict(')[1].split("R[")[0]
        assert "superseded_by" not in blk, f"{key} 已被去重 → 請更新盤點"
        assert re.search(r"weight\s*=\s*2\b", blk), f"{key} 權重已變 → 請更新盤點"


# ── 群組 B：SAHM 是 UNRATE 的確定性轉換 ───────────────────────────
def test_sahm_and_unemployment_share_unrate_upstream():
    """SAHMREALTIME = MA3(U3) − min(前12期)，與 UNRATE 同一個上游變數。"""
    from shared.fred_series import FRED_SAHM, FRED_UNRATE
    assert FRED_SAHM == "SAHMREALTIME"
    assert FRED_UNRATE == "UNRATE"
    for key in ("SAHM", "UNEMPLOYMENT"):
        blk = _SRC.split(f'R["{key}"] = dict(')[1].split("R[")[0]
        assert "superseded_by" not in blk, f"{key} 已被去重 → 請更新盤點"


# ── 群組 C：就業子循環把同一份週報的兩個欄位當兩票 ────────────────
def test_employment_subcycle_averages_two_series_from_one_release():
    """ICSA（初領）與 CCSA（持續）出自同一份 DOL 週報，且機制上前者流入後者。"""
    assert '("就業",     "💼", [("JOBLESS", True), ("CONT_CLAIMS", True)]' in _TP
    from shared.fred_series import FRED_CCSA, FRED_ICSA
    assert (FRED_ICSA, FRED_CCSA) == ("ICSA", "CCSA")


# ── 反向鎖：既有的兩套去重機制必須還在 ────────────────────────────
def test_existing_dedup_mechanisms_still_present():
    """M2 主/備去重與跨層 indicator_key 去重是既有防線，不得被移除。"""
    assert 'superseded_by=("M2" if _m2_monthly_hit else None)' in _SRC
    assert '"indicator_key": "YIELD_10Y2Y"' in _TP
    assert '"indicator_key": "SAHM"' in _TP


@pytest.mark.parametrize("key", ["YIELD_10Y2Y", "YIELD_10Y3M", "SAHM",
                                 "UNEMPLOYMENT", "JOBLESS", "CONT_CLAIMS"])
def test_inventory_keys_still_exist(key):
    """盤點指涉的指標仍存在；被改名/移除時強制回頭更新盤點。"""
    assert f'R["{key}"] = dict(' in _SRC
