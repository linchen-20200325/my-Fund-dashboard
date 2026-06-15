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


def build_moneydj_url(raw_input: str, page_type: str) -> str:
    """構造 MoneyDJ URL：http(s) 直傳短路；純代碼拼接 yp010000/yp010001 端點。"""
    _raw = (raw_input or "").strip()
    if _raw.startswith("http"):
        return _raw
    return f"https://www.moneydj.com/funddj/ya/{page_type}.djhtm?a={_raw.upper()}"


def auto_fetch_moneydj(
    raw_input: str,
    *,
    return_page_type: bool = False,
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
    """
    from fund_fetcher import classify_fetch_status, normalize_result_state
    from repositories.fund_repository import fetch_fund_from_moneydj_url

    _raw = (raw_input or "").strip()
    if not _raw:
        return ({}, "") if return_page_type else {}

    # URL 直傳：page_type 從 URL 字面探測
    if "yp010000" in _raw:
        _res = fetch_fund_from_moneydj_url(_raw)
        return (_res, "yp010000") if return_page_type else _res
    if "yp010001" in _raw:
        _res = fetch_fund_from_moneydj_url(_raw)
        return (_res, "yp010001") if return_page_type else _res

    # 純代碼：累計嘗試所有 page_type，挑最佳結果
    _attempts: list = []
    for _pt in ("yp010000", "yp010001"):
        _url = build_moneydj_url(_raw, _pt)
        try:
            _res = normalize_result_state(fetch_fund_from_moneydj_url(_url))
        except Exception as _e:
            _err_res = {"error": f"{type(_e).__name__}: {_e}"}
            _attempts.append((_err_res, _pt, False, "failed"))
            continue
        _st = _res.get("status", classify_fetch_status(_res))
        _ser = _res.get("series")
        _has_series = (
            _ser is not None and hasattr(_ser, "__len__") and len(_ser) >= 10
        )
        # complete 直接 return（最佳結果）
        if not _res.get("error") and _st == "complete":
            return (_res, _pt) if return_page_type else _res
        _attempts.append((_res, _pt, _has_series, _st))

    # 沒有 complete → 偏好 has_series 的 partial（境外基金真實 case）
    _with_series = [t for t in _attempts if t[2]]
    if _with_series:
        _res, _pt = _with_series[0][0], _with_series[0][1]
        return (_res, _pt) if return_page_type else _res

    # 全部 partial 但無 series → 回第一個 partial（至少有 metadata）
    _partials = [t for t in _attempts if t[3] == "partial"]
    if _partials:
        _res, _pt = _partials[0][0], _partials[0][1]
        return (_res, _pt) if return_page_type else _res

    # 全 failed → 回最後一個
    if _attempts:
        _res, _pt = _attempts[-1][0], _attempts[-1][1]
        return (_res, _pt) if return_page_type else _res

    return ({}, "") if return_page_type else {}
