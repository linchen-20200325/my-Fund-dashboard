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
    code_cache: dict = {}
    n_uniq = len(uniq_codes_load)
    ld_label = st.empty()
    ld_label.info(f"📡 開始載入 {n_uniq} 個 unique codes（每檔約 30s）...")
    ld_prog = st.progress(0.0)
    for cnt_c, code in enumerate(uniq_codes_load):
        ld_label.info(f"📡 載入 {code} ({cnt_c+1}/{n_uniq})")
        try:
            code_cache[code] = fetch_fund_from_moneydj_url(code)
            _nm_ok = (code_cache[code].get("fund_name") or "")[:18]
            st.write(f"✅ `{code}` {_nm_ok}")
        except Exception as _le:
            code_cache[code] = {"error": str(_le)[:80]}
            st.write(f"❌ `{code}` 失敗：{str(_le)[:80]}")
        ld_prog.progress((cnt_c + 1) / n_uniq)
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
