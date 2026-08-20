"""指標清冊漂移鎖（2026-08-20 稽核）—— 讓「診斷看不見缺席」不會復發。

## 背景：被修掉的病

`fetch_all_indicators` 對每個指標都是「抓到才寫 key」：

    if pmi.get("value") is not None:
        R["PMI"] = dict(...)

抓失敗時 **key 直接不存在**。而 `data_registry._update_data_registry` 原本是
**列舉 `indicators` 裡既有的 key**，不是比對應有清單 ⇒ 抓失敗的指標
不會產生任何一列 ⇒ Tab5 異常清單印出
「✅ 已登錄的 N 個資料源狀態全數正常」。

    ⇒ 失敗越多、N 越小、畫面越綠。

修法是讓生產端顯式宣告契約（`EXPECTED_INDICATOR_KEYS`），診斷端做差集。

## 本檔釘什麼

契約一旦與實作分家，整個缺席偵測就會靜靜地失效——**而且失效的方向是變綠**，
沒有人會發現。所以這裡用 AST 直接掃 `us_indicators.py` 的 `R[...]` 賦值，
與宣告的契約逐一比對，兩邊任一方改動而沒同步就紅燈。

不用 import 後跑 `fetch_all_indicators()`（那需要網路與 API key），
改用靜態分析——這也讓本測試在 CI 的無網路環境可跑。
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import re

import pytest

from services.macro.us_indicators import EXPECTED_INDICATOR_KEYS

_SRC_PATH = pathlib.Path(__file__).resolve().parents[1] / "services" / "macro" / "us_indicators.py"


def _assigned_keys() -> set[str]:
    """AST 掃出 `R["KEY"] = ...` 的字面 key。"""
    tree = ast.parse(_SRC_PATH.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        if not (isinstance(node.value, ast.Name) and node.value.id == "R"):
            continue
        sl = node.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            out.add(sl.value)
    return out


def _dynamic_fx_keys() -> set[str]:
    """FX cross-rate 走 `R[_key] = ...` 迴圈，AST 抓不到字面值。

    這三個由一個 `("EURUSD=X", "EURUSD", ...)` 形式的 tuple list 驅動，
    故以該形狀的 regex 取第 2 欄。**刻意不寫死 {EURUSD, USDJPY, USDCNH}** ——
    寫死就等於在測試裡再抄一份清單，那正是本檔要防的東西。
    """
    src = _SRC_PATH.read_text(encoding="utf-8")
    return set(re.findall(r'\(\s*"[A-Z]+=X"\s*,\s*"([A-Z]+)"', src))


class TestContractMatchesImplementation:
    def test_no_produced_key_missing_from_contract(self):
        """實作會產出、但契約沒宣告 → 該指標的缺席永遠不會被偵測到。"""
        produced = (_assigned_keys() | _dynamic_fx_keys())
        produced = {k for k in produced if not k.startswith("_")}
        missing = produced - set(EXPECTED_INDICATOR_KEYS)
        assert not missing, (
            f"這些指標 `fetch_all_indicators` 會產出，但不在 EXPECTED_INDICATOR_KEYS："
            f"{sorted(missing)}。它們抓失敗時不會出現在資料診斷的缺席清單裡。")

    def test_no_contract_key_absent_from_implementation(self):
        """契約宣告、但實作根本不會產出 → 診斷會永久顯示一列假的 🔴。"""
        produced = _assigned_keys() | _dynamic_fx_keys()
        phantom = set(EXPECTED_INDICATOR_KEYS) - produced
        assert not phantom, (
            f"這些 key 在 EXPECTED_INDICATOR_KEYS 但實作不會產出：{sorted(phantom)}。"
            f"診斷頁會永遠顯示它們「未取得」，製造無法消除的紅燈。")

    def test_contract_has_no_meta_keys(self):
        """`_` 前綴是 internal bookkeeping，`data_registry` 會過濾掉。

        若混進契約，差集會永遠算它缺席（因為那一側被過濾），產生幽靈紅燈。
        """
        meta = [k for k in EXPECTED_INDICATOR_KEYS if k.startswith("_")]
        assert not meta, f"契約含 meta 鍵：{meta}"

    def test_contract_has_no_duplicates(self):
        assert len(EXPECTED_INDICATOR_KEYS) == len(set(EXPECTED_INDICATOR_KEYS))


class TestRegistrySurfacesAbsence:
    """行為面：缺席必須真的變成一列 🔴，而不只是常數對得起來。"""

    @staticmethod
    def _build(indicators: dict) -> dict:
        import streamlit as st
        from ui.helpers.io.data_registry import _update_data_registry
        st.session_state["indicators"] = indicators
        _update_data_registry()
        return st.session_state.get("data_registry") or {}

    def test_every_contract_key_gets_a_row_even_when_all_fetches_fail(self):
        reg = self._build({})
        for key in EXPECTED_INDICATOR_KEYS:
            row = reg.get(f"總經_{key}")
            assert row is not None, f"{key} 全部抓失敗時沒有產生列（缺席又變成隱形）"
            assert row["fresh_icon"] == "🔴", f"{key} 缺席但不是紅燈：{row['fresh_icon']}"
            assert row["count"] == 0

    def test_absent_row_carries_no_fabricated_date(self):
        """缺席列**不得**帶任何看起來合理的日期。

        填 today 會讓 `_freshness` 算出「0 天前 🟢」——那正是這次要修的病，
        只是換個地方發作。
        """
        reg = self._build({})
        for key in EXPECTED_INDICATOR_KEYS:
            assert reg[f"總經_{key}"]["latest_date"] == "N/A", (
                f"{key} 的缺席列帶了日期 {reg[f'總經_{key}']['latest_date']!r}")

    def test_present_indicator_is_not_marked_absent(self):
        """反向守衛：沒有它，把整段缺席偵測改成「全部標紅」也能讓上面兩條綠。"""
        reg = self._build({
            "VIX": {"name": "VIX", "date": "2026-08-19"},
            "CPI": {"name": "CPI", "date": "2026-08-01"},
        })
        for key in ("VIX", "CPI"):
            row = reg[f"總經_{key}"]
            assert row["fresh_label"] != "未取得（本次抓取未產生此指標）", \
                f"{key} 明明有值卻被標成未取得"

    def test_meta_key_does_not_become_a_row(self):
        reg = self._build({"_fred_sources": {"FRED_M2": "ok"}})
        assert "總經__fred_sources" not in reg


class TestFrequencyClassification:
    """診斷有列、但那一列說錯話 —— 與缺席同源的第二種病。"""

    @staticmethod
    def _freq_map() -> dict:
        from ui.helpers.io import data_registry as dr
        src = inspect.getsource(dr._update_data_registry)
        tree = ast.parse(src.strip())
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "_FREQ":
                return ast.literal_eval(node.value)
        pytest.fail("找不到 _FREQ")

    @pytest.mark.parametrize("key", ["EURUSD", "USDJPY", "USDCNH"])
    def test_cross_rates_are_daily(self, key):
        """yfinance 日頻匯率若落 `monthly` default，60 天沒更新仍顯示 🟢。"""
        assert self._freq_map().get(key) == "daily", (
            f"{key} 不在 _FREQ 或不是 daily —— 日頻資料會被用月頻門檻判讀")

    def test_every_contract_key_has_explicit_frequency(self):
        """契約內的每個指標都應顯式分類，不倚賴 default。

        default 恰好正確時看不出問題，但它同時意味著沒有 `_FRED_SERIES_MAP`
        條目可用 `next_release_date`——NFP 就是這樣長出週期性假黃燈的。
        """
        freq = self._freq_map()
        unclassified = [k for k in EXPECTED_INDICATOR_KEYS if k not in freq]
        assert not unclassified, (
            f"這些指標沒有顯式頻率分類，靠 default 兜著：{sorted(unclassified)}")
