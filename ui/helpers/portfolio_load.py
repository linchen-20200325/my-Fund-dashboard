"""ui/helpers/portfolio_load.py — v18.151 PR B.1：批次載入未載入基金 helper

把原本散在 `ui/tab3_portfolio.py:1656` 那段 ~70 行 fetch 邏輯抽成 module-level helper。
讓「保單分組視圖頂部」、「未綁保單區塊」、「原批次加入下方」三處都能呼叫同一邏輯，
避免重複按鈕（Streamlit widget key 不能重複）+ 避免 fetch 邏輯散裝。

設計原則（與 CLAUDE.md §2 一致）：
- 純 helper，依賴只透過 lazy import（避免 module load 時拖入 fund_fetcher）
- session_state 直寫直讀；不收 caller 參數
- UI side-effects（status / progress / write / rerun）內聚於本函式
"""
from __future__ import annotations

import streamlit as st


def count_unloaded_funds() -> tuple[int, int]:
    """回傳 (未載入 entry 數, 去重 code 數)。給 caller 決定要不要顯示按鈕。"""
    pf = st.session_state.get("portfolio_funds", []) or []
    not_loaded = [i for i, f in enumerate(pf) if not f.get("loaded")]
    uniq_codes = sorted({
        str(pf[i].get("code", "")).strip() for i in not_loaded
    } - {""})
    return len(not_loaded), len(uniq_codes)


# fund-info 欄位：只跟 fund_code 有關（NAV 歷史/指標/名稱與保單無關），可跨帳本共用。
# 與 batch_load_unloaded_funds() broadcast 寫入的鍵對齊（loaded/load_error 另外處理）。
_FUND_INFO_KEYS = (
    "name", "series", "dividends", "metrics", "moneydj_raw",
    "risk_metrics", "is_core", "currency",
)


def reuse_fund_info_by_code(
    merged: list[dict], previous_funds: list[dict] | None,
) -> list[str]:
    """跨帳本共用基金資訊：同 fund_code 上一本帳本已載入過 → 直接沿用、免重抓。

    切換帳本後 sync 以 `(policy_id, fund_code)` 為鍵 → 換人/換保單時同一檔基金
    被當成全新（loaded=False）。但 NAV 歷史/指標只跟 fund_code 有關、與保單無關，
    故可從上一本帳本已 `loaded=True` 的條目依 code 補回，只剩真正新標的待抓。

    就地修改 merged（持倉仍走新帳本的 policy/units/invest_twd，只補基金資訊）；
    回傳被沿用（免重抓）的 code 清單（大寫去重排序）。
    """
    info_by_code: dict[str, dict] = {}
    for _f in list(previous_funds or []):
        if not _f.get("loaded") or _f.get("load_error"):
            continue
        _c = str(_f.get("code", "") or "").strip().upper()
        if _c and _c not in info_by_code:
            info_by_code[_c] = _f

    reused: set[str] = set()
    for entry in merged:
        if entry.get("loaded"):
            continue
        _c = str(entry.get("code", "") or "").strip().upper()
        src = info_by_code.get(_c)
        if not src:
            continue
        for k in _FUND_INFO_KEYS:
            if k not in src:
                continue
            v = src[k]
            # v18.197：不可用 `v not in (None, "")` —— series 是 pandas Series，
            # 對它做相等判斷會回傳 Series → bool() 觸發「truth value ambiguous」。
            # 改：None 跳過；只有「空字串」才跳過（如保單帶來的 currency）；
            # series/dict/list 一律直接複製。
            if v is None:
                continue
            if isinstance(v, str) and v == "":
                continue
            entry[k] = v
        entry["loaded"] = True
        entry["load_error"] = None
        reused.add(_c)
    return sorted(reused)


def reconcile_funds_with_ledgers(funds, t7_ledgers) -> tuple:
    """讀取齊全：保證每個 t7_ledgers 部位都有對應的 portfolio_funds spine 條目，
    並把帳本的成本基礎（avg_nav / fx_avg / units / avg_nav_with_div）回填到
    portfolio_funds（**缺值才補、不覆蓋既有**）。

    動機（user：「讀取資料時帳本一直缺資料」）：表單與帳本表都以 portfolio_funds
    為主軸（spine）迭代、再用 `fund_pk_str(f)` 去 t7_ledgers 取成本。若保單分頁
    （→portfolio_funds）與 _T7_State（→t7_ledgers）內容漂移，帳本只有快照的基金
    會「看不到」。本函式以 t7_ledgers（成本權威）補齊 spine，讓讀回後帳本齊全。

    就地修改 funds list；回傳 (funds, n_added)。
    """
    from models.policy import fund_pk_str, parse_pk
    funds = list(funds or [])
    by_pk: dict = {}
    for _f in funds:
        by_pk.setdefault(fund_pk_str(_f), _f)

    n_added = 0
    for _pk, _led in (t7_ledgers or {}).items():
        _pos = getattr(_led, "position", None)
        if _pos is None:
            continue
        _cu   = float(getattr(_pos, "cost_unit", 0) or 0)
        _fx   = float(getattr(_pos, "fx_avg", 0) or 0)
        _cuwd = float(getattr(_pos, "cost_unit_with_div", 0) or 0)
        _u    = float(getattr(_pos, "units", 0) or 0)

        _f = by_pk.get(_pk)
        if _f is None:
            _pid, _code = parse_pk(_pk)
            _f = {
                "code":        _code or str(getattr(_led, "fund_code", "") or ""),
                "policy_id":   _pid,
                "policy_name": _pid,
                "currency":    str(getattr(_led, "currency", "") or ""),
                "loaded":      False, "load_error": None,
            }
            funds.append(_f)
            by_pk[_pk] = _f
            n_added += 1

        # 回填成本基礎（缺值才補，不覆蓋使用者既有設定）
        if not _f.get("avg_nav") and _cu:
            _f["avg_nav"] = _cu
        if not _f.get("fx_avg") and _fx:
            _f["fx_avg"] = _fx
        if not _f.get("units") and _u:
            _f["units"] = _u
        if not _f.get("avg_nav_with_div") and _cuwd:
            _f["avg_nav_with_div"] = _cuwd
    return funds, n_added


def batch_load_unloaded_funds() -> None:
    """v18.151：批次抓取所有 portfolio_funds 內 `loaded=False` 的基金。

    流程：
      1. clear fund_fetcher / macro_repository 的 TTL 快取（拿 fresh）
      2. dedupe code（同 code 跨多保單只 fetch 一次）
      3. 對每個 unique code 呼叫 fetch_fund_from_moneydj_url，with status/progress
      4. broadcast 結果到每個 portfolio_funds entry（同 code 共用同 raw）
      5. _update_data_registry + st.rerun

    無 side-effects 給 caller（除了 session_state 更新與 rerun）。
    """
    pf = st.session_state.get("portfolio_funds", []) or []
    not_loaded = [i for i, f in enumerate(pf) if not f.get("loaded")]
    if not not_loaded:
        return

    # dedupe code
    uniq_codes_load = sorted({
        str(pf[i].get("code", "")).strip() for i in not_loaded
    } - {""})
    if not uniq_codes_load:
        return

    # 清 fetch 快取（避免 hold 住 stale calc_metrics）
    try:
        from fund_fetcher import clear_all_caches as _cac
        import repositories.macro_repository  # noqa: F401 — 觸發 macro 快取註冊
        _cac()
    except Exception:
        pass   # noqa: smoke-allow-pass — clear 失敗不擋 loading

    # Step 1: 抓每個 unique code
    # v18.156: 不能用 st.status — 它本質是 expander，本 helper 會被
    # tab3「🗂️ 保單分組視圖」expander 內按鈕呼叫，巢狀違規會 crash。
    # 改用 st.empty placeholder（label）+ st.progress + st.write log 平面組合。
    from fund_fetcher import fetch_fund_from_moneydj_url
    from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: PLC0415
    code_cache: dict = {}
    n_uniq = len(uniq_codes_load)
    ld_label = st.empty()
    ld_label.info(f"📡 開始並行載入 {n_uniq} 個 unique codes（4 路並行，每檔約 30s）...")
    ld_prog = st.progress(0.0)
    # v18.219：序列 → ThreadPoolExecutor(4) 並行（比照 tab3 既有寫法）。
    # 只有 fetch 跑在 worker thread；所有 st.* 進度/log 留在主執行緒（as_completed）。
    _done = 0
    with ThreadPoolExecutor(max_workers=4) as _ex:
        _futs = {_ex.submit(fetch_fund_from_moneydj_url, code): code
                 for code in uniq_codes_load}
        for _fut in as_completed(_futs):
            code = _futs[_fut]
            try:
                code_cache[code] = _fut.result()
                _nm_ok = (code_cache[code].get("fund_name") or "")[:18]
                st.write(f"✅ `{code}` {_nm_ok}")
            except Exception as _le:
                code_cache[code] = {"error": str(_le)[:80]}
                st.write(f"❌ `{code}` 失敗：{str(_le)[:80]}")
            _done += 1
            ld_label.info(f"📡 並行載入中 {_done}/{n_uniq}（剛完成 {code}）")
            ld_prog.progress(_done / n_uniq)
    ld_label.success(f"✅ 完成 — 抓到 {n_uniq} 個 unique codes")

    # Step 2: broadcast 給每個 pf entry
    from ui.helpers.session import is_core_fund as _is_core
    from ui.helpers.data_registry import _update_data_registry

    errors: list[str] = []
    for i in not_loaded:
        pf_item = st.session_state.portfolio_funds[i]
        c_pf = str(pf_item.get("code", "")).strip()
        pf_raw = code_cache.get(c_pf, {"error": "no code"})
        if pf_raw.get("error"):
            errors.append(f"{pf_item['code']}: {pf_raw['error']}")
            st.session_state.portfolio_funds[i].update({
                "loaded": True, "load_error": pf_raw["error"],
            })
        else:
            st.session_state.portfolio_funds[i].update({
                "name":         pf_raw.get("fund_name") or pf_item["code"],
                "series":       pf_raw.get("series"),
                "dividends":    pf_raw.get("dividends", []),
                "metrics":      pf_raw.get("metrics", {}),
                "moneydj_raw":  pf_raw,
                "risk_metrics": pf_raw.get("risk_metrics", {}),
                "is_core":      _is_core(pf_raw.get("fund_name") or pf_item["code"]),
                "currency":     pf_raw.get("currency", "")
                                  or pf_raw.get("metrics", {}).get("currency", ""),
                "loaded":       True, "load_error": None,
            })

    if errors:
        st.warning("部分基金載入失敗：\n" + "\n".join(errors))
    _update_data_registry()
    st.rerun()
