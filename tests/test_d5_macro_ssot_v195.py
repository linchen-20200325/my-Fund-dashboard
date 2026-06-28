"""v19.195 SSOT — D5_FRED_KEYS / D5_YF_KEYS / D5_KEYS 統一一致性。

歷史病灶:同一份 12 FRED + 4 Yahoo = 16 macro keys 在 3 處重複硬編:
  - `ui/helpers/session.py:21-23` `_D5_KEYS`
  - `ui/tab5_data_guard.py:135-138` 第 ⓪ 區 _FRED_REQUIRED + _YF_REQUIRED
  - `ui/tab5_data_guard.py:347-349` 第 ② 區 _FRED_INTERNAL + _YF_KEYS

任一處 drift(增/減指標)會讓 Tab5 顯示與實際 indicator 數量不同步 →
user 看到「16/16」誤判全綠,實則漏算。

修法:抽 `D5_FRED_KEYS` / `D5_YF_KEYS` / `D5_KEYS` 為 public SSOT
       (`ui/helpers/session.py`),Tab5 兩處改 import 同源。

本測試守:
1. union = sum 不變(D5_KEYS == D5_FRED_KEYS + D5_YF_KEYS)
2. 12 + 4 = 16 數量不變(若未來要加指標,先改 SSOT 再 propagate)
3. backward compat `_D5_KEYS` alias 仍指 D5_KEYS(不破壞既有 caller)
4. Tab5 module body 不再 hardcode 同一份 list(grep 防回潮)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


class TestD5KeysSSotUnionV195:
    def test_d5_keys_is_fred_plus_yf(self):
        from ui.helpers.session import D5_FRED_KEYS, D5_YF_KEYS, D5_KEYS
        assert D5_KEYS == D5_FRED_KEYS + D5_YF_KEYS, (
            "D5_KEYS 必須 = D5_FRED_KEYS + D5_YF_KEYS(SSOT union)"
        )

    def test_fred_keys_count_is_12(self):
        from ui.helpers.session import D5_FRED_KEYS
        assert len(D5_FRED_KEYS) == 12, (
            f"FRED 指標數固定為 12;若要改先 propagate 到 Tab5 顯示 / "
            f"AI prompt / SCORE_RULES,實際 {len(D5_FRED_KEYS)}"
        )

    def test_yf_keys_count_is_4(self):
        from ui.helpers.session import D5_YF_KEYS
        assert len(D5_YF_KEYS) == 4, (
            f"Yahoo 指標數固定為 4(VIX/DXY/ADL/COPPER);實際 {len(D5_YF_KEYS)}"
        )

    def test_total_count_is_16(self):
        from ui.helpers.session import D5_KEYS
        assert len(D5_KEYS) == 16, (
            f"Data Guard 5 燈源固定 16 個;實際 {len(D5_KEYS)}"
        )

    def test_no_duplicate_keys_across_subsets(self):
        from ui.helpers.session import D5_FRED_KEYS, D5_YF_KEYS
        assert not (set(D5_FRED_KEYS) & set(D5_YF_KEYS)), (
            "FRED / Yahoo 指標 set 不該交集(避免 union 多算)"
        )

    def test_no_duplicate_within_keys(self):
        from ui.helpers.session import D5_FRED_KEYS, D5_YF_KEYS
        assert len(D5_FRED_KEYS) == len(set(D5_FRED_KEYS)), \
            "D5_FRED_KEYS 內不該重複"
        assert len(D5_YF_KEYS) == len(set(D5_YF_KEYS)), \
            "D5_YF_KEYS 內不該重複"


class TestBackwardCompatAliasV195:
    def test_underscore_d5_keys_alias_equals_d5_keys(self):
        from ui.helpers.session import _D5_KEYS, D5_KEYS
        assert _D5_KEYS == D5_KEYS, "_D5_KEYS 必為 D5_KEYS 的 alias"

    def test_calc_data_health_still_uses_16_keys(self):
        """calc_data_health 對 16 keys 都有資料 → 100% / 🟢。"""
        from ui.helpers.session import calc_data_health, D5_KEYS
        ind = {k: {"value": 1.0} for k in D5_KEYS}
        pct, traffic = calc_data_health(ind)
        assert pct == 100
        assert traffic == "🟢"


class TestTab5UsesSSotImportV195:
    """grep 守 Tab5 module body 不再 hardcode 同一份 16 keys。

    若有人未來不小心又寫 `["PMI", "YIELD_10Y2Y", ...]` inline,
    本測試會立刻拒絕。"""

    TAB5_PATH = (Path(__file__).resolve().parents[1]
                 / "ui" / "tab5_data_guard.py")

    def test_tab5_imports_d5_fred_keys(self):
        assert self.TAB5_PATH.exists(), "tab5_data_guard.py 必須存在"
        text = self.TAB5_PATH.read_text(encoding="utf-8")
        assert "D5_FRED_KEYS" in text, (
            "Tab5 必須 import D5_FRED_KEYS;若改名請同步本 test"
        )
        assert "D5_YF_KEYS" in text, "Tab5 必須 import D5_YF_KEYS"

    def test_no_inline_fred_keys_list_in_tab5(self):
        """Tab5 不該再 hardcode 同一份 PMI / YIELD_10Y2Y / HY_SPREAD list。

        若有人 inline 寫 `["PMI", "YIELD_10Y2Y", ...]` 的 list literal,
        regex 會抓到 → 拒絕(SSOT 漂移防衛)。
        """
        text = self.TAB5_PATH.read_text(encoding="utf-8")
        # 抓 list literal 含 PMI + YIELD_10Y2Y(SSOT 的明顯特徵)
        # 排除註解行(以 # 開頭)、docstring 內、字串拼接
        offending_patterns = [
            r'\[\s*"PMI"\s*,\s*"YIELD_10Y2Y"',
            r"\[\s*'PMI'\s*,\s*'YIELD_10Y2Y'",
        ]
        for pat in offending_patterns:
            matches = re.findall(pat, text)
            assert not matches, (
                f"Tab5 不該再 hardcode 12 FRED list(SSOT 漂移),"
                f"找到 inline pattern {pat!r}: {matches}"
            )

    def test_no_inline_yf_keys_list_in_tab5(self):
        """Tab5 不該再 hardcode 同一份 VIX / DXY / ADL / COPPER list。"""
        text = self.TAB5_PATH.read_text(encoding="utf-8")
        offending = re.findall(
            r'\[\s*"VIX"\s*,\s*"DXY"\s*,\s*"ADL"\s*,\s*"COPPER"\s*\]',
            text,
        )
        assert not offending, (
            f"Tab5 不該再 hardcode YF list(SSOT 漂移),找到 {offending}"
        )
