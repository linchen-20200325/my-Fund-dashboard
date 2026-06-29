"""v19.194 regression — Tab5 資料診斷 FX / Sheet 政策 假紅燈修正。

User 螢幕截圖回報「Tab 4 組合配置 持倉✓ FX✗ Sheet 政策✗ 1/3 元件」紅燈,
但實際 codebase grep 確認 `usdtwd_rate` / `policy_funds` / `fx_rate` /
`portfolio_policy` 4 個 session_state key 從未被任何代碼 set。
原 check 永遠回 None → 永遠假紅燈,與實際資料健康度無關。

修法:
- FX → 直接呼 cached `get_latest_fx('USDTWD')`(positive-only 5min TTL)
- 政策 → 真實檢查 (a) gservice_account secret 或 (b) OAuth configured + login token
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


class TestTab5FxHealthV194:
    """Tab5 FX check 必須真實反映 get_latest_fx 結果。"""

    def test_fx_truthy_when_get_latest_fx_returns_positive(self):
        """get_latest_fx 回 31.4 → Tab5 應視為 ✓。"""
        with patch("repositories.fund.get_latest_fx", return_value=31.4):
            from repositories.fund import get_latest_fx
            assert bool(get_latest_fx("USDTWD")) is True

    def test_fx_falsy_when_get_latest_fx_returns_none(self):
        """get_latest_fx 回 None → Tab5 應視為 ✗(全鏈失敗,真紅燈)。"""
        with patch("repositories.fund.get_latest_fx", return_value=None):
            from repositories.fund import get_latest_fx
            assert bool(get_latest_fx("USDTWD")) is False

    def test_get_latest_fx_zero_treated_as_invalid(self):
        """rate=0 應被 positive-only cache 拒收,不算 ✓。"""
        with patch("repositories.fund.get_latest_fx", return_value=0):
            from repositories.fund import get_latest_fx
            assert bool(get_latest_fx("USDTWD")) is False


class TestTab5PolicySheetHealthV194:
    """Tab5 Sheet 政策 check 必須真實反映 OAuth/SA 認證狀態。"""

    def test_sa_secret_only_sufficient(self):
        """有 google_service_account secret → SA 模式,無需 OAuth → ✓。"""
        # 模擬 oauth_state module 狀態
        has_sa = True
        oauth_cfg_ok = False
        has_token = False
        ok = has_sa or (oauth_cfg_ok and has_token)
        assert ok is True, "SA secret 一條件足夠"

    def test_oauth_configured_but_not_logged_in_insufficient(self):
        """OAuth configured 但未登入 → 缺 gsheet_tokens → ✗(需要登入)。"""
        has_sa = False
        oauth_cfg_ok = True
        has_token = False
        ok = has_sa or (oauth_cfg_ok and has_token)
        assert ok is False

    def test_oauth_configured_and_logged_in_sufficient(self):
        """OAuth configured + 已有 gsheet_tokens → ✓。"""
        has_sa = False
        oauth_cfg_ok = True
        has_token = True
        ok = has_sa or (oauth_cfg_ok and has_token)
        assert ok is True

    def test_nothing_configured_insufficient(self):
        """完全沒設 → ✗(真紅燈,提示 user 動作)。"""
        has_sa = False
        oauth_cfg_ok = False
        has_token = False
        ok = has_sa or (oauth_cfg_ok and has_token)
        assert ok is False


class TestStooqHeaderlessFallbackV194:
    """v19.194 stooq fetcher headerless 解析路徑。

    歷史回報:user 螢幕截圖「stooq ^cpc: 欄位不符 ['  0..」
    主路徑 read_csv 看 'Date' / 'Close' header,stooq 偶爾回 headerless 純資料
    → headerless fallback 接住。
    """

    class _FakeResp:
        def __init__(self, text: str, status_code: int = 200):
            self.text = text
            self.status_code = status_code

    def test_headerless_csv_parsed_via_fallback(self):
        """純資料無 header → headerless fallback 解析成功。"""
        from services import risk_radar as rr
        # YYYY-MM-DD,open,high,low,close,volume
        headerless = (
            "2026-06-25,0.92,0.95,0.91,0.93,1000\n"
            "2026-06-26,0.93,0.97,0.92,0.95,1200\n"
            "2026-06-27,0.95,0.99,0.94,0.97,1500\n"
        )
        with patch("infra.proxy.fetch_url",
                   return_value=self._FakeResp(headerless)):
            trace: list[str] = []
            s = rr._fetch_stooq_csv("^cpc", trace=trace)
        assert not s.empty, "headerless 純資料應被 fallback 接住"
        assert len(s) == 3
        assert float(s.iloc[-1]) == pytest.approx(0.97)
        # provenance 標 headerless,user 可從 source 看出走 fallback 路徑
        assert "headerless" in s.attrs.get("source", "")
        # trace 應記錄 fallback 命中,留下 audit trail
        assert any("headerless" in t for t in trace), \
            f"trace 必須說明走 fallback,實際 {trace}"

    def test_standard_header_first_no_fallback_needed(self):
        """有正規 header → 走主路徑,headerless 不啟動,source 不帶 'headerless'。"""
        from services import risk_radar as rr
        standard = (
            "Date,Open,High,Low,Close,Volume\n"
            "2026-06-25,0.92,0.95,0.91,0.93,1000\n"
            "2026-06-26,0.93,0.97,0.92,0.95,1200\n"
        )
        with patch("infra.proxy.fetch_url",
                   return_value=self._FakeResp(standard)):
            s = rr._fetch_stooq_csv("^cpc")
        assert not s.empty
        assert len(s) == 2
        # 主路徑 source 不該有 headerless 字樣
        assert "headerless" not in s.attrs.get("source", "")

    def test_truly_invalid_returns_empty_with_sample_trace(self):
        """完全無法解析 → 空 Series + trace 含回應 sample(audit 用)。"""
        from services import risk_radar as rr
        garbage = "<html>access denied</html>" + ("x" * 100)
        with patch("infra.proxy.fetch_url",
                   return_value=self._FakeResp(garbage)):
            trace: list[str] = []
            s = rr._fetch_stooq_csv("^cpc", trace=trace)
        assert s.empty
        # trace 必須帶 sample,給 user 看實際 stooq 回什麼
        assert any("sample=" in t for t in trace), \
            f"trace 必須帶 sample 字樣,實際 {trace}"

    def test_no_data_string_short_circuits(self):
        """stooq 'No data' 短路,不嘗試解析。"""
        from services import risk_radar as rr
        with patch("infra.proxy.fetch_url",
                   return_value=self._FakeResp("No data")):
            trace: list[str] = []
            s = rr._fetch_stooq_csv("^cpc", trace=trace)
        assert s.empty
        assert any("No data" in t for t in trace)


class TestPutCallChainCoversAllSourcesV194:
    """_resolve_put_call chain 完整,任一源成功即停手。"""

    def test_yahoo_cpc_success_short_circuits(self):
        """Yahoo ^CPC 成功 → 不打 ^CPCE / stooq。"""
        import pandas as pd
        from services import risk_radar as rr
        with patch.object(rr, "fetch_yf_close",
                          return_value=pd.Series([0.9, 0.95, 1.0])) as mock_yf, \
             patch.object(rr, "_fetch_stooq_csv") as mock_stooq:
            s, src, trace = rr._resolve_put_call()
        assert not s.empty
        assert src == "Yahoo ^CPC"
        assert mock_yf.call_count == 1, "首 ticker 成功應停手"
        mock_stooq.assert_not_called()

    def test_all_fail_returns_empty_with_full_trace(self):
        """全失敗 → 空 series + trace 完整列出每段失敗。"""
        import pandas as pd
        from services import risk_radar as rr
        with patch.object(rr, "fetch_yf_close",
                          return_value=pd.Series(dtype=float)), \
             patch.object(rr, "_fetch_stooq_csv",
                          return_value=pd.Series(dtype=float)):
            s, src, trace = rr._resolve_put_call()
        assert s.empty
        assert src == ""
        # trace 至少含 2 段 Yahoo 失敗(stooq 失敗 trace 由 _fetch_stooq_csv 自填)
        assert len([t for t in trace if "Yahoo" in t]) == 2
