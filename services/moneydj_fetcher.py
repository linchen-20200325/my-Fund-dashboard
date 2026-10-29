"""v19.76 K3：MoneyDJ 自動偵測 + URL 構造 SSOT helper。

Phase 1 audit：`_auto_fetch_moneydj` 在 `tab2_single_fund.py:86`（38 行）與
`tab_fund_grp_health.py:95`（32 行）各自定義一份，邏輯近似但有差異：
- tab2 版回 `(res, page_type)` tuple、支援 URL 直傳、fallback chain 更完整
- tab5 版只回 `res` dict、不支援 URL、fallback chain 缺「partial-no-series」中間層

統一後 tab2/tab5 共用同一份偵測邏輯，避免「兩 Tab 對同一基金 fallback 路徑不同
→ 結果不一致」的事故源。

對外 API：
- `build_moneydj_url(raw_input, page_type)` — URL 構造（直 http 短路 / 純代碼拼接）
- `auto_fetch_moneydj(raw_input, *, return_page_type=False)` — 統一 fallback chain
  - return_page_type=False（預設）→ 回 dict（tab5 場景）
  - return_page_type=True → 回 (dict, page_type) tuple（tab2 場景）

fallback 偏好順序（複用 tab2 較完整版本）：
1. 任一 page_type 拿到 complete → 立刻 return（最佳）
2. 都不 complete → 偏好 has_series 的 partial（境外基金真實 case）
3. 全部 partial 但都無 series → 回第一個 partial（至少有 metadata）
4. 全 failed → 回最後一個（境外結果優先曝露）
"""
from __future__ import annotations

from typing import Union

# 2026-10-13 總管技術裁定第 3 條：純代碼走兩個頁型時，每一次嘗試的狀態與逐來源失敗原文
# 以這個**新增鍵**掛在回傳的 dict 上（schema-additive；頁型迴圈與停止條件一字未動）。
# 用途：B 線（`services/v2_tables/nav_dividend.py`）全來源失敗時，兩個頁型的原文都呈現得出來
# —— 回傳值只有最後選中的那一次，前一次的原文原本就丟了。
NAV_ATTEMPTS_KEY = "nav_page_type_attempts"


def nav_history_shared_reads(*, skip_reads: bool = False):
    """A 鏈的 nav_history 讀取共用範圍（`services.nav_history_gs.shared_reads`，2026-10-13 總管技術裁定第 6 條）。

    批次呼叫 `auto_fetch_moneydj` 的一方（B 線 `build_nav_table`）在這個範圍內逐檔取數，整張累積表只讀一次。
    範圍外不影響任何行為。放在本模組，是因為 B 線的 import 守衛只放行 `services.moneydj_fetcher` 這一個名字。
    `skip_reads=True`：範圍內不讀累積表、一律當作沒有累積點（B 線出處閘門關閉時用，見 `shared_reads`）。
    """
    from services.nav_history_gs import shared_reads
    return shared_reads(skip_reads=skip_reads)


def build_moneydj_url(raw_input: str, page_type: str) -> str:
    """構造 MoneyDJ URL：http(s) 直傳短路；純代碼拼接 yp010000/yp010001 端點。"""
    _raw = (raw_input or "").strip()
    if _raw.startswith("http"):
        return _raw
    return f"https://www.moneydj.com/funddj/ya/{page_type}.djhtm?a={_raw.upper()}"


def normalize_manual_fund_input(text: str) -> str:
    """手動加入基金的輸入 → 代碼（DG-2 §10 缺陷 A；docs/v2/70 §14 第 1 點）。

    原 UI 先 `.strip().upper()` 才判斷是否為網址 → 貼上的網址被轉成 `HTTPS://…`，
    `build_moneydj_url` 的 `startswith("http")` 不成立 → 組出 `?a=HTTPS://…`。
    改為**先判斷網址、再轉大寫**：
    - 網址（`http` 開頭，大小寫不拘）→ 由既有 `parse_moneydj_input` 取 `?a=`／`&a=` 代碼（已大寫）；
      抽不出代碼 → 回 `""`（呼叫端依「空輸入」處理，不猜、不回傳網址本身）。
    - 其餘（裸碼）→ `.strip().upper()`，與修正前逐字相同。
    """
    s = (text or "").strip()
    if s.lower().startswith("http"):
        from repositories.fund.sources import parse_moneydj_input
        return parse_moneydj_input(s).get("code", "") or ""
    return s.upper()


def auto_fetch_moneydj(
    raw_input: str,
    *,
    return_page_type: bool = False,
    oauth_client=None,
) -> Union[dict, tuple[dict, str]]:
    """自動偵測境內/境外：URL 明確指定直接用；純代碼累計嘗試所有 page_type 挑最佳。

    v18.120 issue 2 修法核心：原邏輯 partial 也立即 short-circuit；對境外基金 TLZF9
    試 yp010000 → partial 直接 return → 不會試正確的 yp010001。新邏輯：partial 但
    series 完全空 → 繼續試下一個 page_type；累計後選最佳。

    Args:
        raw_input: 純代碼（如 ACCP138）或完整 MoneyDJ URL
        return_page_type: True → 回 (dict, page_type)；False → 只回 dict

    Returns:
        若 return_page_type=True：(result_dict, page_type) tuple
        若 return_page_type=False：result_dict
        無效輸入回 ({}, "") 或 {}

    v19.509:`oauth_client` 選填 —— 透傳給 enriched wrapper → finalize → nav_history 讀取。
    SA 缺(手機無 Service Account)時,由上層(健診 UI 主執行緒捕獲)傳入,讓健診讀得到 OAuth
    寫進雲端的補回歷史。None → 純 SA/空,行為與改動前一致(cron / 其餘 caller 零影響)。
    """
    from fund_fetcher import classify_fetch_status, normalize_result_state
    # v19.240 R8 EX-L1ORCH-1 退役:走 L2 enriched wrapper(含 metrics + reconcile)
    from services.fund_service import fetch_fund_from_moneydj_url_enriched as fetch_fund_from_moneydj_url

    _raw = (raw_input or "").strip()
    if not _raw:
        return ({}, "") if return_page_type else {}

    # URL 直傳：page_type 從 URL 字面探測
    if "yp010000" in _raw:
        _res = fetch_fund_from_moneydj_url(_raw, oauth_client=oauth_client)
        return (_res, "yp010000") if return_page_type else _res
    if "yp010001" in _raw:
        _res = fetch_fund_from_moneydj_url(_raw, oauth_client=oauth_client)
        return (_res, "yp010001") if return_page_type else _res

    # 純代碼：累計嘗試所有 page_type，挑最佳結果
    _attempts: list = []
    _attempt_log: list = []   # 2026-10-13：只記錄（見 NAV_ATTEMPTS_KEY），不參與任何判斷

    def _log_attempt(_r: dict, _p: str, _s: str) -> None:
        from repositories.fund.fund_orchestration import NAV_SOURCE_FAILURES_KEY
        _attempt_log.append({"page_type": _p, "status": _s, "error": _r.get("error"),
                             "nav_source_failures": list(_r.get(NAV_SOURCE_FAILURES_KEY) or ())})

    def _done(_r: dict, _p: str):
        if isinstance(_r, dict):
            _r[NAV_ATTEMPTS_KEY] = list(_attempt_log)
        return (_r, _p) if return_page_type else _r
    for _pt in ("yp010000", "yp010001"):
        _url = build_moneydj_url(_raw, _pt)
        try:
            _res = normalize_result_state(fetch_fund_from_moneydj_url(_url, oauth_client=oauth_client))
        except Exception as _e:
            _err_res = {"error": f"{type(_e).__name__}: {_e}"}
            _attempts.append((_err_res, _pt, False, "failed"))
            _log_attempt(_err_res, _pt, "failed")
            continue
        _st = _res.get("status", classify_fetch_status(_res))
        _ser = _res.get("series")
        _has_series = (
            _ser is not None and hasattr(_ser, "__len__") and len(_ser) >= 10
        )
        _log_attempt(_res, _pt, _st)
        # complete 直接 return（最佳結果）
        if not _res.get("error") and _st == "complete":
            return _done(_res, _pt)
        _attempts.append((_res, _pt, _has_series, _st))

    # 沒有 complete → 偏好 has_series 的 partial（境外基金真實 case）
    _with_series = [t for t in _attempts if t[2]]
    if _with_series:
        _res, _pt = _with_series[0][0], _with_series[0][1]
        return _done(_res, _pt)

    # 全部 partial 但無 series → 回第一個 partial（至少有 metadata）
    _partials = [t for t in _attempts if t[3] == "partial"]
    if _partials:
        _res, _pt = _partials[0][0], _partials[0][1]
        return _done(_res, _pt)

    # 全 failed → 回最後一個
    if _attempts:
        _res, _pt = _attempts[-1][0], _attempts[-1][1]
        return _done(_res, _pt)

    return ({}, "") if return_page_type else {}
