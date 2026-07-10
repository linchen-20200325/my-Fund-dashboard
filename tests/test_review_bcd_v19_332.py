"""v19.332 — 外部 review B 類監控盲區收斂守衛(user 2026-07-10 核准「B+C+D 請繼續」)。

B6 tab5 Section ⑤ 補 Row 4 診斷格:最大回撤 / Sortino / Calmar / 基金規模
   (前三者 calc_metrics 一直有算只是診斷沒列格;規模為 MoneyDJ fund_scale 字串)
B7 持股物件統一取值路徑 `_get_holdings`(原 Section ⓪/①/⑤ 三處判定路徑不一致
   → 同一檔基金在不同 section 計數可能不同)
"""
from __future__ import annotations

import unittest


class TestGetHoldingsUnifiedPath(unittest.TestCase):
    """B7:頂層優先 → moneydj_raw 補位(對齊 dividends 雙路徑 fallback 精神)。"""

    def test_top_level_only(self):
        from ui.tab5_data_guard import _get_holdings
        fd = {"holdings": {"top_holdings": [1, 2, 3]}}
        self.assertEqual(len(_get_holdings(fd).get("top_holdings", [])), 3)

    def test_moneydj_raw_fallback(self):
        from ui.tab5_data_guard import _get_holdings
        fd = {"moneydj_raw": {"holdings": {"top_holdings": [1, 2]}}}
        self.assertEqual(len(_get_holdings(fd).get("top_holdings", [])), 2)

    def test_top_level_wins_over_moneydj(self):
        from ui.tab5_data_guard import _get_holdings
        fd = {"holdings": {"top_holdings": [1]},
              "moneydj_raw": {"holdings": {"top_holdings": [1, 2, 3, 4]}}}
        self.assertEqual(len(_get_holdings(fd).get("top_holdings", [])), 1)

    def test_empty_and_none_safe(self):
        from ui.tab5_data_guard import _get_holdings
        self.assertEqual(_get_holdings({}), {})
        self.assertEqual(_get_holdings(None), {})
        self.assertEqual(_get_holdings({"moneydj_raw": None}), {})

    def test_all_three_sites_use_helper(self):
        """源碼守衛:Section ⓪/①/⑤ 三處計數皆走 _get_holdings,不得再有
        直接 `.get("holdings")` 判定 top_holdings 的分歧路徑。"""
        with open("ui/tab5_data_guard.py", encoding="utf-8") as f:
            src = f.read()
        self.assertGreaterEqual(src.count("_get_holdings("), 4,
                                "def + 3 呼叫點")
        # 舊分歧寫法不得殘留(判定 top_holdings 的舊 inline 鏈)
        self.assertNotIn('((_src_cf.get("holdings") or {}).get("top_holdings"))', src)
        self.assertNotIn('((f.get("moneydj_raw") or {}).get("holdings") or {}).get("top_holdings")', src)


class TestTab5Row4DiagnosticCells(unittest.TestCase):
    """B6 源碼守衛:Row 4 四格存在且取自正確來源鍵。"""

    def test_row4_cells_present(self):
        with open("ui/tab5_data_guard.py", encoding="utf-8") as f:
            src = f.read()
        for label in ('"最大回撤"', '"Sortino"', '"Calmar"', '"基金規模"'):
            self.assertIn(label, src, f"Section ⑤ 應有 {label} 診斷格")
        # 來源鍵:metrics(max_drawdown/sortino/calmar)+ moneydj_raw(fund_scale)
        self.assertIn('_d5_m.get("max_drawdown")', src)
        self.assertIn('_d5_m.get("sortino")', src)
        self.assertIn('_d5_m.get("calmar")', src)
        self.assertIn('_d5_mj.get("fund_scale")', src)

    def test_metrics_keys_exist_in_fund_service_contract(self):
        """calc_metrics 契約鍵名對齊(改名會讓診斷格靜默變 N/A)。"""
        with open("services/fund_service.py", encoding="utf-8") as f:
            src = f.read()
        for key in ("max_drawdown=", "sortino=", "calmar="):
            self.assertIn(key, src, f"fund_service metrics 應有 {key.rstrip('=')} 欄")


if __name__ == "__main__":
    unittest.main()
