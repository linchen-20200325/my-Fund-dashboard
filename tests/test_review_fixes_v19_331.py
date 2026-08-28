"""v19.331 — 外部 code review 修正守衛測試。

對應 dashboard_code_review.md 建議（user 2026-07-10 指派）:
1. P1 us_indicators per-series 隔離:單一 FRED series 例外(pandera SchemaError /
   IO error)原本炸掉 fetch_all_indicators → 該指標之後全滅。_fred_iso/_yf_iso
   把 v19.171 pool 慣例擴及其餘 16+2 處 sequential 呼叫。
2. P1 CPI `.iloc[-2]`:守衛檢查原始 df 長度,但 shift(12)+dropna 後 s24 可能
   <2 筆 → IndexError。補 len(s24) 雙守衛(對齊同檔 PPI 模式)。
3. perf RRP/TGA 補進 fetch_fred_batch 預熱清單(原冷啟動 2 次串行往返)。
4. P1 tab2 `float(nav_latest)`:MoneyDJ 占位字串("—"/"N/A")→ ValueError 炸
   partial 視圖 → safe_float(SSOT shared/converters)。
5. 次要 tab5 `_div_n` 對同 key or 自身(dead fallback 筆誤)→ 對齊雙路徑語意。
"""
from __future__ import annotations

import unittest

import pandas as pd


def _mk_fred_df(n=200, freq="MS", start="2008-01-01", base=100.0):
    """合成 fetch_fred 契約 df(date/value/realtime_start/source/fetched_at)。"""
    dates = pd.date_range(start, periods=n, freq=freq)
    vals = [base + i * 0.3 for i in range(n)]
    return pd.DataFrame({
        "date": dates,
        "value": pd.array(vals, dtype="float64"),
        "realtime_start": dates,
        "source": "FRED:TEST",
        "fetched_at": "2026-07-10T00:00:00+00:00",
    })


class _PatchedIndicators(unittest.TestCase):
    """共用 patch 底座:網路層全 fake,只測 orchestration 行為。"""

    def _run(self, fred_fake, yf_fake=None, batch_capture=None):
        import services.macro.us_indicators as us

        _orig = {
            "_fred": us._fred, "_yf_s": us._yf_s,
            "fetch_ism_pmi": us.fetch_ism_pmi,
            "fetch_fred_batch": us.fetch_fred_batch,
        }
        try:
            us._fred = fred_fake
            us._yf_s = yf_fake or (lambda t, p="2y": pd.Series(dtype=float))
            us.fetch_ism_pmi = lambda key: {"value": None}
            us.fetch_fred_batch = (batch_capture
                                   or (lambda pairs, key, max_workers=8: None))
            return us.fetch_all_indicators("dummy-key")
        finally:
            for k, v in _orig.items():
                setattr(us, k, v)


class TestPerSeriesIsolation(_PatchedIndicators):

    def test_single_series_exception_does_not_cascade(self):
        """UNRATE 炸(模擬 pandera SchemaError)→ 只犧牲失業率格,
        其後 PPI / 消費者信心等指標照常產出(原行為:全滅)。"""
        from shared.fred_series import FRED_UNRATE

        def _fred_fake(sid, key, n=250):
            if sid == FRED_UNRATE:
                raise RuntimeError("simulated SchemaError")
            return _mk_fred_df()

        R = self._run(_fred_fake)
        self.assertNotIn("UNEMPLOYMENT", R)
        self.assertIn("PPI", R, "UNRATE 之後的指標不得連坐")
        self.assertIn("CONSUMER_CONF", R)

    def test_fred_iso_returns_empty_on_raise(self):
        import services.macro.us_indicators as us
        _orig = us._fred
        try:
            def _boom(sid, key, n=250):
                raise ValueError("boom")
            us._fred = _boom
            out = us._fred_iso("ANY", "k", 10)
            self.assertTrue(out.empty)
        finally:
            us._fred = _orig

    def test_yf_iso_returns_empty_on_raise(self):
        import services.macro.us_indicators as us
        _orig = us._yf_s
        try:
            def _boom(t, p="2y"):
                raise ValueError("boom")
            us._yf_s = _boom
            out = us._yf_iso("^VIX", "5y")
            self.assertTrue(out.empty)
        finally:
            us._yf_s = _orig


class TestCpiShortSeriesGuard(_PatchedIndicators):

    def test_cpi_degenerate_series_no_indexerror(self):
        """CPI 原始 df 過守衛(len>=14)但 shift(12)+dropna 後 0~1 筆 →
        原 `s24.iloc[-2]` IndexError 且中斷其後全部;修後跳過該格不炸。"""
        from shared.fred_series import FRED_CPI

        def _fred_fake(sid, key, n=250):
            if sid == FRED_CPI:
                # 14 筆但中段 NaN → yoy dropna 後 0 筆(病態輸入)
                df = _mk_fred_df(n=14)
                df.loc[1:12, "value"] = float("nan")
                return df
            return _mk_fred_df()

        R = self._run(_fred_fake)  # 不得 raise
        self.assertNotIn("CPI", R, "退化序列不得產出 CPI 假值")
        self.assertIn("FED_RATE", R, "CPI 之後的指標不得連坐")

    def test_cpi_normal_series_still_produced(self):
        """正常 CPI 序列 → 指標照常產出(fix 不誤傷正常路徑)。"""
        R = self._run(lambda sid, key, n=250: _mk_fred_df())
        self.assertIn("CPI", R)
        self.assertIsNotNone(R["CPI"]["value"])
        self.assertIsNotNone(R["CPI"]["prev"])


class TestRrpTgaBatchPrefetch(_PatchedIndicators):

    def test_batch_list_contains_rrp_tga(self):
        from shared.fred_series import FRED_RRP, FRED_TGA
        captured: dict = {}

        def _batch_capture(pairs, key, max_workers=8):
            captured["sids"] = [p[0] for p in pairs]

        self._run(lambda sid, key, n=250: _mk_fred_df(),
                  batch_capture=_batch_capture)
        self.assertIn(FRED_RRP, captured.get("sids", []))
        self.assertIn(FRED_TGA, captured.get("sids", []))


class TestTab2NavPlaceholderGuard(unittest.TestCase):

    def test_safe_float_handles_moneydj_placeholders(self):
        """SSOT safe_float:MoneyDJ 失敗占位字串 → None(不炸不造假)。"""
        from shared.converters import safe_float
        for junk in ("—", "N/A", "查無資料", "", None):
            self.assertIsNone(safe_float(junk))
        self.assertEqual(safe_float("12.34"), 12.34)
        self.assertEqual(safe_float(9.5), 9.5)

    def test_tab2_no_bare_float_on_nav(self):
        """源碼守衛:買賣點段不得再裸 float() MoneyDJ 值。

        ⚠️ **2026-08-28 Q4 更新:拿掉了一條要求「死碼必須存在」的斷言。**
        原本還有一句 `assertIn("_safe_float(_p_nav)", src)` —— `_p_nav` 是
        **partial 資料視圖**的區域變數,而那個視圖長在一條 production 恆不觸發的
        分支上,Q4 已把該分支的 body 換成 2 行誠實訊息,`_p_nav` 隨之消失。
        繼續留著那句 = **要求一段死碼必須存在**,任何人想清掉它都會被本測試擋下來。
        **拿掉的是「必須有」,不是「不准有」** —— 上面兩條 `assertFalse`
        (不准出現裸 `float(_p_nav` / 裸 `float(m.get("nav")`)**一字未動**。

        ⚠️ **2026-08-28 補正:上一版在這裡寫「所以 partial 視圖若哪天回來,
        裸 float 一樣會被擋」—— 那句話說太滿。** 它成立**有前提**:
        兩條 assertFalse 是**逐字綁死變數名**的正規表示式(見下方原始碼:
        負向後查 `(?<!_safe_)` 之後直接接死 `_p_nav` 與 `m.get("nav"` 兩個字面),
        所以只在**partial 視圖回來時仍沿用 `_p_nav` 這個名字**的情況下才擋得住。
        實證:把該分支改寫成 `_nav_raw = ...` + 裸 `float(_nav_raw)` 之後,
        兩條 assertFalse **都不會 fire**(實跑本檔 → 9 passed)。
        也就是說本檔守的是「**這兩個既有寫法不准回歸**」,**不是**
        「任何裸 float 都擋得住」。要守後者需要 AST 規則(誰對 MoneyDJ 取來的值
        呼叫 `float`),不是逐字 regex —— 已登記為待辦,本輪不做(§8.4 step 4)。
        (v19.331 原本要防的 bug 是「MoneyDJ 失敗時 nav_latest 是 "—"/"N/A" 字串,
         裸 float() 直接 ValueError 炸頁」;那條防線靠的是 assertFalse,不是 assertIn。)
        """
        import re
        with open("ui/tab2_single_fund.py", encoding="utf-8") as f:
            src = f.read()
        # 裸 float( 呼叫(排除 _safe_float 子字串)不得再作用於 MoneyDJ 值
        self.assertFalse(re.search(r"(?<!_safe_)float\(_p_nav", src),
                         "partial 視圖仍有裸 float(_p_nav…)")
        self.assertFalse(re.search(r"(?<!_safe_)float\(m\.get\(\"nav\"", src),
                         "買賣點段仍有裸 float(m.get(\"nav\")…)")
        self.assertIn("_safe_float(m.get(\"nav\"))", src)


class TestTab5DivDeadFallback(unittest.TestCase):

    def test_div_n_no_or_self(self):
        """源碼守衛:`_src_cf.get("dividends") or _src_cf.get("dividends")`
        (對同 key or 自身 = dead fallback)已改 moneydj_raw 雙路徑。"""
        with open("ui/tab5_data_guard.py", encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn(
            '_src_cf.get("dividends") or _src_cf.get("dividends")', src)
        self.assertIn(
            '(_src_cf.get("moneydj_raw") or {}).get("dividends")', src)


if __name__ == "__main__":
    unittest.main()
