"""services/fund_calc_currency.py — 正式計算用幣別判定(純函式,無 streamlit、無 I/O)。

2026-10-13 客戶裁示(LINE 推播與舊 UI 解耦):每週換檔推播 `scripts/weekly_switch_notify.py`
經 `services.fund_grp_health.capture.capture_by_code` 需要 `fund_currency_for_calc`;
該函式原住 `ui/helpers/portfolio/load.py`(該檔 module 頂層 `import streamlit`),
排程因此被迫載入 UI 層。本檔把**判定邏輯原封搬來**(一字未改),
`ui/helpers/portfolio/load.py` 改為從這裡 import 同名物件 —— 全站仍只有這一份實作(SSOT)。

搬來的只有 `fund_currency_for_calc` 與它直接用到的三個名字
(`_iso_ccy` / `source_currency_of` / `SHEET_CCY_CONFLICT_KEY`);
`sheet_currency_by_code` / `with_sheet_currency` 只有舊 UI 用,留在原檔。
"""
from __future__ import annotations


def _iso_ccy(raw) -> str:
    """幣別 → ISO 三碼;空 / 非三碼 → `""`(未知)。中文別名先過 L2 正規化。"""
    from services.currency import normalize_ccy
    from shared.data_quality import normalize_iso_ccy
    return normalize_iso_ccy(normalize_ccy(raw, default=""))


def source_currency_of(fund: dict) -> str:
    """抓取結果(`moneydj_raw`)宣告的幣別(原字串,未正規化);沒有 → `""`。"""
    _mj = (fund or {}).get("moneydj_raw")
    if not isinstance(_mj, dict):
        return ""
    return str(_mj.get("currency") or (_mj.get("metrics") or {}).get("currency") or "").strip()


#: 2026-10-10 客戶裁示二 B(C2-3):同一 code 在客戶 Sheet 上被設成 ≥2 種幣別時,
#: 由 `with_sheet_currency` 掛在**記憶體內**的 fund dict 上的衝突標記(不寫回 Sheet、
#: 不是資料欄位);`fund_currency_for_calc` 見到它一律回 `""`(fail closed)。
SHEET_CCY_CONFLICT_KEY = "_sheet_ccy_conflict"


def fund_currency_for_calc(fund: dict) -> str:
    """需要「正確幣別」的正式計算(換匯 / 單位數 / 換股)該用的幣別 → ISO 三碼或 `""`。

    2026-10-10 客戶裁示(A 級資料正確性缺陷):
      - **未知幣別 ≠ USD**:Sheet 與來源都沒有可辨識的幣別 → `""`(呼叫端 fail closed)。
      - **Q4 currency conflict**:Sheet(`fund["currency"]`)與來源(`moneydj_raw`)
        都有值但不一致 → `""`(不得靜默選一個繼續算;呼叫端 fail closed)。
        ~~衝突狀態**不另存欄位**(現有 schema 無處保存出處),每次由這兩個既有值即時判定。~~
        → 2026-10-10 稽核回修 R3(敘述對齊現況,行為不變):Sheet／來源衝突仍是每次由這兩個
        既有值即時判定,**不寫進 Sheet、不另存欄位**;另有一種衝突(同一 code 在不同保單列
        被設成不同幣別)無法由單一 dict 判定,由 `with_sheet_currency` 在重組出的**記憶體內**
        dict 上掛 `SHEET_CCY_CONFLICT_KEY`,本函式見到即回 `""`。該標記不是 Sheet 欄位,
        `with_sheet_currency` 與本函式都不會把它寫回 Sheet 或備份。
    """
    if (fund or {}).get(SHEET_CCY_CONFLICT_KEY):   # 2026-10-10 C2-3:Sheet 同 code 多幣別
        return ""
    _sheet = _iso_ccy((fund or {}).get("currency"))
    _src = _iso_ccy(source_currency_of(fund))
    if _sheet and _src and _sheet != _src:
        return ""
    return _sheet or _src


__all__ = ["SHEET_CCY_CONFLICT_KEY", "fund_currency_for_calc", "source_currency_of"]
