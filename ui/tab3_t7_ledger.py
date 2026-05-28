"""ui/tab3_t7_ledger.py — T7 帳務與再平衡試算（從 ui/tab3_portfolio.py 抽出）

包含 T7 區段（A/B/C 三種落帳情境 + 帳本面板 + MK 老師深度組合建議 AI），
原為 ui/tab3_portfolio.py 內 render_portfolio_tab 末段 1978 行（佔 46%）。

設計：
- render_t7_section() -> None 零閉包依賴（與其他 render fn 同設計）
- GEMINI_KEY 從 env 即時取，不靠 caller 注入
- ui.helpers 一律函式內部 lazy import，沿用 render_portfolio_tab 設計
- Ledger / Switch class 維持原邏輯：函式內部 lazy import 自 services.ledger_service

對外 API:
- render_t7_section() -> None
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from infra.oauth import (
    OAuthError,
    build_credentials_from_tokens,
    ensure_fresh_tokens,
)
from models.policy import (
    PK_SEP,
    fund_pk_str,
    make_pk,
    migrate_ledger_dict,
    parse_pk,
)
from repositories.fund_repository import fetch_fund_from_moneydj_url
from repositories.ledger_repository import (
    append_ledger_row,
    replace_ledgers_for_policy,
)
from repositories.news_repository import fetch_market_news
from repositories.policy_repository import (
    PolicySheetError,
    get_gspread_client_from_oauth,
    list_policy_worksheets,
    upsert_fund_in_policy,
)
from repositories.snapshot_repository import (
    load_all_ledgers_snapshot,
    save_all_ledgers_snapshot,
    save_holdings_overview,
)
from services.ai_service import analyze_portfolio_mk_advisor
from services.macro_service import (
    backtest_sub_cycle_lights,
    rank_macro_drivers,
)
from ui.helpers.session import (
    calc_data_health as _calc_data_health_pure,
    is_core_fund as _is_core_fund,
)
from ui.helpers.tw_time import tw_now_str


def _calc_data_health(indicators=None):
    """總經資料健康度 wrapper（與 tab3_portfolio.py 同邏輯，供 MK AI 區段使用）。"""
    ind = indicators if indicators is not None else st.session_state.get("indicators", {})
    return _calc_data_health_pure(ind)


# ── v18.230：股數/單位分配模式 helper（A/B/C 共用） ─────────────────────────
def _t7_has_position(pk: str) -> bool:
    """檢查 pk 是否已在主帳本有持倉。新標的 → False → 預設「目標單位數」模式。"""
    _l = st.session_state.get("t7_ledgers", {}).get(pk)
    return bool(_l and getattr(getattr(_l, "position", None), "units", 0) > 0)


def _t7_units_to_twd(units: float, nav: float, fx: float) -> float:
    """單位數 × NAV × FX → TWD 等值金額（混搭模式換算共通量）。"""
    return float(units) * float(nav) * float(fx)


def render_t7_section() -> None:
    """渲染 T7 帳務試算 + MK 深度組合建議 AI 子區。

    從 render_portfolio_tab 末段抽出。Caller 不需傳參數，全部狀態透過 st.session_state。
    """
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

    # v18.140 同 render_portfolio_tab — helper 改正規 import，徹底脫離 sys.modules['__main__'] hack
    from ui.helpers.oauth_state import (
        _gsa_secret,
        _get_oauth_client,
        _oauth_configured,
        _resolve_oauth_cfg,
        _sheet_id_secret,
    )
    from ui.helpers.holdings import _zh_holding
    from ui.helpers.data_registry import (
        _sync_invest_twd_from_ledgers,
        _update_data_registry,
    )

    # ── T7: 帳務與再平衡試算 (Universal Fund Ledger v1.0) ─────────────────────
    st.divider()

    # v18.150 PR B：T7 改唯讀模擬器警告 — 偵測到 v2 schema 時提示 user
    # 真實加碼/贖回請至 Tab3「保單管理」v2 編輯介面或直接改 Sheet
    try:
        from ui.helpers.oauth_state import _oauth_configured as _oc_v2
        _sid_v2_chk = st.session_state.get("policy_sheet_id", "")
        if _oc_v2 and _sid_v2_chk and \
           st.session_state.get("_schema_ver") == "v2":
            st.warning(
                "⚠️ **T7 為純模擬器**：v18.149 起 schema v2 下 T7 不再寫回 Sheet。\n\n"
                "下方贖回 / 轉換 / 加碼模擬**只算損益、不更新持倉**。"
                "真實加碼/贖回請至 Tab3「📋 保單管理」**v2 編輯介面**"
                "（in-line 改 units / avg_nav / avg_fx 後按「💾 存到雲端」）"
                "或直接到 Google Sheet 內手動修改。"
            )
    except Exception:
        pass   # noqa: smoke-allow-pass — UI 提示失敗不影響後續 T7 主邏輯

    st.markdown("### 💰 T7 帳務與再平衡試算（A / B / C）")
    st.caption(
        "v1.0 加權平均會計引擎。NAV / FX 一律由 yfinance 即時抓取，"
        "使用者只填「投入金額」與「目標權重」。帳本以記憶體保留至重新整理頁面為止——"
        "本工具定位為「先試算、後落帳」。"
    )

    _pf_t7 = [f for f in st.session_state.portfolio_funds if f.get("loaded")]
    if not _pf_t7:
        st.info("ℹ️ 請先在上方「組合管理」載入至少一檔基金後，再使用 A/B/C 試算。")
    else:
        try:
            from services.ledger_service import Ledger as _LedT7, Switch as _SwT7
            from fund_fetcher import get_latest_fx as _fx_now, get_latest_nav as _nav_now
            _T7_OK = True
        except ImportError as _e:
            _T7_OK = False
            st.error(f"⚠️ T7 引擎尚未就緒：{_e}")

        if _T7_OK:
            from datetime import date as _d_t7

            if "t7_ledgers" not in st.session_state:
                st.session_state.t7_ledgers = {}

            # ── P2 一次性遷移：舊 session 中 code-only 鍵 → (policy_id, code) ──
            _t7_migrated = migrate_ledger_dict(
                st.session_state.t7_ledgers, st.session_state.portfolio_funds
            )
            if _t7_migrated != st.session_state.t7_ledgers:
                st.session_state.t7_ledgers = _t7_migrated

            # ── v18.29 helper：T7 帳本 ↔ Google Sheets `_T7_State` 雙向直連 ──
            def _t7_get_gsheet_client_sid():
                """回傳 (client, sheet_id)；OAuth 未配/未登入/sheet_id 未設 → (None, None)。"""
                _cfg_s = _resolve_oauth_cfg()
                _toks_s = st.session_state.get("gsheet_tokens")
                _sid_s = st.session_state.get("policy_sheet_id")
                if not (_cfg_s and _toks_s and _sid_s):
                    return None, None
                try:
                    _t_s = ensure_fresh_tokens(dict(_toks_s),
                        _cfg_s["client_id"], _cfg_s["client_secret"])
                    st.session_state["gsheet_tokens"] = _t_s
                    _creds_s = build_credentials_from_tokens(_t_s,
                        _cfg_s["client_id"], _cfg_s["client_secret"])
                    return get_gspread_client_from_oauth(_creds_s), _sid_s
                except (PolicySheetError, OAuthError):
                    return None, None
                except Exception:
                    return None, None

            def _t7_save_snapshot_to_sheets() -> str:
                """落帳完成後呼叫：把目前 t7_ledgers 全表寫進 _T7_State。
                回傳 status 字串給 success message 附在後面（成功 ' + State N 筆' / 失敗 ' ⚠️ ...'）。"""
                _c_s, _sid_s = _t7_get_gsheet_client_sid()
                if not _c_s:
                    return ""
                try:
                    _funds_lookup = {fund_pk_str(f): f
                                     for f in st.session_state.get("portfolio_funds", [])}
                    _n = save_all_ledgers_snapshot(
                        _c_s, _sid_s,
                        st.session_state.t7_ledgers, _funds_lookup)
                    # v18.182：同步寫人看得懂的完整成本帳本 _持倉總覽
                    _n_ov = save_holdings_overview(
                        _c_s, _sid_s,
                        st.session_state.t7_ledgers, _funds_lookup)
                    return f" + _T7_State 寫 {_n} 筆 + _持倉總覽 {_n_ov} 筆"
                except (PolicySheetError, OAuthError) as _e_ss:
                    return f" ⚠️ _T7_State 同步失敗：{str(_e_ss)[:200]}"
                except Exception as _e_ss:
                    return f" ⚠️ _T7_State 例外：[{type(_e_ss).__name__}] {str(_e_ss)[:200]}"

            def _t7_load_snapshot_from_sheets() -> tuple:
                """從 _T7_State 還原 t7_ledgers。回傳 (count, error_msg)。"""
                _c_s, _sid_s = _t7_get_gsheet_client_sid()
                if not _c_s:
                    return 0, "OAuth 未登入或 sheet_id 未設"
                try:
                    _restored = load_all_ledgers_snapshot(_c_s, _sid_s, _LedT7)
                    if _restored:
                        st.session_state.t7_ledgers = _restored
                        _sync_invest_twd_from_ledgers()
                    return len(_restored), ""
                except (PolicySheetError, OAuthError) as _e_ld:
                    return 0, str(_e_ld)[:120]
                except Exception as _e_ld:
                    return 0, str(_e_ld)[:120]

            # ── v18.29: T7 entry 自動還原 — 只當 t7_ledgers 為空且 OAuth 已登入時 ──
            if (not st.session_state.t7_ledgers
                    and st.session_state.get("gsheet_tokens")
                    and st.session_state.get("policy_sheet_id")
                    and not st.session_state.get("_t7_auto_restore_done")):
                _n_r, _err_r = _t7_load_snapshot_from_sheets()
                st.session_state["_t7_auto_restore_done"] = True
                if _n_r > 0:
                    st.info(f"☁️ 已從 `_T7_State` 自動還原 {_n_r} 筆 ledger（重整頁面後雲端帳本仍在）")

            # v18.70: T7「💾 帳本存檔...」整段已移到上方「📋 保單管理」expander，
            #         避免「上下兩個存讀位置」的混亂。Sheets 直連登入也合併到上方。

            # ── 反查表：pk_str → fund dict（同 code 跨保單不衝突） ───────────
            _fund_by_pk = {fund_pk_str(f): f for f in _pf_t7}

            # v18.76: 幣別保底匯率（yfinance / Yahoo 在某些網路被擋時最終 fallback）
            #         手動微調可在「📝 編輯持倉」expander 改 fx_at_buy；此處只求數字「不歸 0」。
            _FX_FALLBACK = {
                "USD": 32.0, "EUR": 34.5, "HKD": 4.1, "JPY": 0.21,
                "AUD": 21.0, "GBP": 40.0, "CNY": 4.45, "CHF": 36.0,
                "SGD": 24.0, "CAD": 23.5, "NZD": 19.5, "ZAR": 1.75,
            }

            # v18.80: 幣別中英對照 — 使用者帳本常存中文（美元/台幣...），
            #         _FX_FALLBACK key 是 ISO，若不先正規化 .get("美元") 永遠回 None
            #         → 整批 fx=0 全部 skip auto-estimate。修正以後 USD/EUR/HKD/JPY 等
            #         中文名也能命中保底匯率。
            _CCY_NORMALIZE = {
                "美元": "USD", "美金": "USD",
                "歐元": "EUR",
                "港幣": "HKD", "港元": "HKD",
                "日圓": "JPY", "日元": "JPY",
                "澳幣": "AUD", "澳元": "AUD",
                "英鎊": "GBP",
                "人民幣": "CNY", "CNH": "CNY",
                "台幣": "TWD", "新台幣": "TWD", "新臺幣": "TWD",
                "瑞郎": "CHF", "瑞士法郎": "CHF",
                "新幣": "SGD", "新加坡幣": "SGD", "星幣": "SGD",
                "加幣": "CAD", "加元": "CAD",
                "紐幣": "NZD", "紐元": "NZD",
                "蘭特": "ZAR", "南非幣": "ZAR",
            }

            def _norm_ccy(_raw: str) -> str:
                """幣別正規化：中文 / ISO 都統一回 ISO 3 碼。未知則回原值大寫。"""
                _u = str(_raw or "USD").upper().strip()
                return _CCY_NORMALIZE.get(_u, _u)

            def _latest_nav_fx_t7(_fund: dict) -> tuple:
                _code = str(_fund.get("code", "")).strip()
                _ccy  = _norm_ccy(_fund.get("currency", "USD"))
                _nav  = _nav_now(_code)
                if _nav is None:
                    _s = _fund.get("series")
                    if _s is not None and len(_s.dropna()):
                        _nav = float(_s.dropna().iloc[-1])
                _fx = _fx_now(f"{_ccy}TWD") if _ccy != "TWD" else 1.0
                if _fx is None or _fx <= 0:
                    _fx = float(_fund.get("fx_rate", 0) or 0) or 0.0
                # v18.26: 最後一道 FX fallback — 用 ledger 的平均買入匯率
                #         （否則最新 FX 抓不到時市值整個歸 0 → -100% 報酬假象）
                if _fx <= 0:
                    try:
                        _pk_f = fund_pk_str(_fund)
                        _l_fb = st.session_state.t7_ledgers.get(_pk_f)
                        if _l_fb is not None:
                            _fx = float(getattr(_l_fb.position, "fx_avg", 0) or 0)
                    except Exception:
                        pass   # noqa: smoke-allow-pass — fallback 靜默：留 _fx=0 給上層 if 守
                # v18.76: 幣別保底匯率（YF 被擋 + 無 ledger 歷史時的最終救援）
                #         讓自動估算「不再因 FX 抓不到全部 skip」；
                #         準確匯率使用者可手動改 fx_at_buy。
                if _fx <= 0 and _ccy in _FX_FALLBACK:
                    _fx = _FX_FALLBACK[_ccy]
                return float(_nav or 0.0), float(_fx or 0.0)


            def _ledger_for(_pk: str) -> "_LedT7":
                """_pk 為 pk_str(make_pk(fund))。"""
                _led = st.session_state.t7_ledgers.get(_pk)
                if _led is None:
                    _f = _fund_by_pk.get(_pk)
                    _, _code = parse_pk(_pk)
                    _ccy = _norm_ccy((_f or {}).get("currency", "USD"))
                    _led = _LedT7(fund_code=_code, currency=_ccy)
                    st.session_state.t7_ledgers[_pk] = _led
                return _led

            # ── v18.68/v18.69: T7 entry 自動估算 — 進帳本就同步上方 invest_twd → 下方 ledger
            #            根因：上方 KPI 用 invest_twd（Sheet 直接讀），下方 T7 KPI 用
            #            ledger.units × NAV × FX。ledger 缺則下方歸 0，造成上下不一致。
            #            自動估算 units = invest_twd / (NAV × FX)，使用者進入 T7 即可看到
            #            完整數據；保留「📝 編輯初始持倉」expander 給手動微調。
            # v18.69 改進：移除 session-level flag（卡住問題），改 fund-level 自然冪等
            #              ledger.units > 0 → skip（守護手動值 + 防重複）；
            #              每次 rerun 重檢，NAV/FX 後續抓到也能估算
            # v18.81: 估算用「投資日期當天 NAV」做 cost，否則 cost = current → P&L 永遠 0
            def _nav_at_date_t7(_fund: dict, _date_str: str) -> float:
                """從 fund.series 取 _date_str <= 的最後一筆 NAV（asof），缺則回 0。"""
                if not _date_str:
                    return 0.0
                _s = _fund.get("series")
                if _s is None:
                    return 0.0
                try:
                    _s2 = _s.dropna().sort_index()
                    if len(_s2) == 0:
                        return 0.0
                    _dt = pd.Timestamp(_date_str)
                    _v = _s2.asof(_dt)
                    if pd.notna(_v) and float(_v) > 0:
                        return float(_v)
                except Exception:
                    pass   # noqa: smoke-allow-pass — asof 失敗回 0 讓上層走 fallback
                return 0.0

            _auto_est_count = 0
            _auto_est_skip_no_nav = 0
            _auto_est_skip_no_twd = 0
            for _f_ae in _pf_t7:
                _pk_ae = fund_pk_str(_f_ae)
                _twd_ae = float(_f_ae.get("invest_twd", 0) or 0)
                _ex_ae = st.session_state.t7_ledgers.get(_pk_ae)
                # 已有單位（手動值或上次自動估算）→ skip 守護
                if _ex_ae is not None and float(_ex_ae.position.units) > 0:
                    continue
                if _twd_ae <= 0:
                    _auto_est_skip_no_twd += 1
                    continue
                _nav_today, _fx_ae = _latest_nav_fx_t7(_f_ae)
                # v18.81: 優先用投資日期當天 NAV 做 cost；缺則 fallback 今天
                _invest_date_ae = str(_f_ae.get("invest_date", "") or "").strip()
                _nav_hist_ae = _nav_at_date_t7(_f_ae, _invest_date_ae) if _invest_date_ae else 0.0
                if _nav_hist_ae > 0:
                    _nav_for_cost = _nav_hist_ae
                    try:
                        _date_for_buy = pd.Timestamp(_invest_date_ae).date()
                    except Exception:
                        _date_for_buy = _d_t7.today()
                else:
                    _nav_for_cost = _nav_today   # fallback：series 缺或日期無解
                    _date_for_buy = _d_t7.today()
                if _nav_for_cost <= 0 or _fx_ae <= 0:
                    _auto_est_skip_no_nav += 1
                    continue
                _u_ae = round(_twd_ae / (_nav_for_cost * _fx_ae), 4)
                if _u_ae <= 0:
                    continue
                _c_ae = _f_ae.get("code", "?")
                _ccy_ae = _norm_ccy(_f_ae.get("currency", "USD"))
                _new_led_ae = _LedT7(fund_code=_c_ae, currency=_ccy_ae)
                _amt_ae = _u_ae * _nav_for_cost * _fx_ae
                _new_led_ae.subscribe(_amt_ae, _fx_ae, _nav_for_cost, _date_for_buy)
                st.session_state.t7_ledgers[_pk_ae] = _new_led_ae
                _auto_est_count += 1
            if _auto_est_count > 0:
                _sync_invest_twd_from_ledgers()
                try:
                    _t7_save_snapshot_to_sheets()
                except Exception:
                    pass   # noqa: smoke-allow-pass — dump 失敗不擋顯示
                _msg_skip = ""
                if _auto_est_skip_no_nav > 0:
                    _msg_skip = (f"（{_auto_est_skip_no_nav} 檔因 NAV 仍抓不到跳過 — "
                                 f"按「🗑️ 清空抓取快取」後重新載入再試）")
                st.success(
                    f"⚡ **自動估算 {_auto_est_count} 檔持倉** — "
                    f"`units = invest_twd ÷ (NAV_at_buy × FX)`；"
                    f"**cost NAV 用「投資日期當天 NAV」**（v18.81，可顯真實 P&L）"
                    f"若 yfinance 抓不到 FX 會用幣別保底匯率（USD≈32 / EUR≈34.5 / HKD≈4.1 ...）。"
                    f"已有 ledger 不會被覆寫；若要重估請按下方「🗑️ 重置帳本」清空後重進 T7。{_msg_skip}"
                )
            elif _auto_est_skip_no_nav > 0 and _auto_est_skip_no_twd == 0:
                # v18.76: 加了幣別保底匯率後，這條路徑通常只剩「NAV 真的抓不到」
                st.warning(
                    f"⚠️ **{_auto_est_skip_no_nav} 檔基金需自動估算但 NAV 抓不到** — "
                    f"請至「📋 保單管理」按「🗑️ 清空抓取快取」後重新載入基金。"
                    f"FX 已加幣別保底匯率，不該是擋點。"
                )

            def _sync_actions_to_sheet(rows_by_pid: dict) -> str:
                """v18.27: 把 T7 落帳交易（A/B/C/初始）同步寫進 _Ledgers tab。
                rows_by_pid: {policy_id: [{date, code, action, units, nav_at_action,
                                            twd, fee, note}, ...]}
                OAuth 未登入 / sheet_id 未設 → 靜默略過（本地 ledger 仍生效）。
                失敗不擋本地落帳，回傳警告字串給呼叫端附在 success message 上。"""
                if not rows_by_pid:
                    return ""
                _cfg_w = _resolve_oauth_cfg()
                _toks_w = st.session_state.get("gsheet_tokens")
                _sid_w = st.session_state.get("policy_sheet_id")
                if not (_cfg_w and _toks_w and _sid_w):
                    return ""
                try:
                    _t_w = ensure_fresh_tokens(dict(_toks_w),
                        _cfg_w["client_id"], _cfg_w["client_secret"])
                    st.session_state["gsheet_tokens"] = _t_w
                    _creds_w = build_credentials_from_tokens(_t_w,
                        _cfg_w["client_id"], _cfg_w["client_secret"])
                    _client_w = get_gspread_client_from_oauth(_creds_w)
                    _total_w = 0
                    for _pid_w, _rows_w in rows_by_pid.items():
                        if not _pid_w:
                            continue
                        for _r_w in _rows_w:
                            append_ledger_row(_client_w, _sid_w,
                                dict(_r_w, policy_id=_pid_w))
                            _total_w += 1
                    return (f" + Sheets `_Ledgers` +{_total_w} 筆"
                            if _total_w > 0 else "")
                except (PolicySheetError, OAuthError) as _e_w:
                    return f" ⚠️ Sheets 同步失敗：{str(_e_w)[:60]}"
                except Exception as _e_w:
                    return f" ⚠️ Sheets 例外：{str(_e_w)[:60]}"

            def _get_dy_t7(_fund: dict) -> float:
                """取得基金年化配息率 (%)，fallback：moneydj_div_yield → metrics.annual_div_rate → 0。"""
                _mj = _fund.get("moneydj_raw", {}) or {}
                try:
                    _v = (_mj.get("moneydj_div_yield")
                          or _fund.get("metrics", {}).get("annual_div_rate", 0)
                          or 0)
                    return float(_v)
                except Exception:
                    return 0.0

            # P2: 字典以 pk_str 為鍵，避免跨保單同代碼覆蓋
            _dy_lookup_t7 = {fund_pk_str(f): _get_dy_t7(f) for f in _pf_t7}
            _name_lookup_t7 = {fund_pk_str(f): (f.get("name") or f.get("code", "?"))
                               for f in _pf_t7}

            def _label_for_pk(_pk: str) -> str:
                """選單顯示用：「保單/代碼 – 基金名」；無保單顯示「(未綁)/代碼」。"""
                _pid, _code = parse_pk(_pk)
                _name = _name_lookup_t7.get(_pk, _code)[:24]
                _pid_disp = _pid if _pid else "(未綁)"
                return f"{_pid_disp}/{_code} – {_name}"

            # v18.52: _sync_invest_twd_from_ledgers 已 hoist 到模組層（line 358），
            # 此處 T7 區呼叫者透過 Python global scope 解析（NameError 修復）

            # ── v18.70: 「編輯持倉」改成預設展開的主視圖（不再藏 expander）
            # ── v18.154：欄位對齊 v2 schema — 砍「持有單位數」輸入（自動算），
            #             加「淨投資金額(NT)」+「平均買入含息單位成本(10)」。
            #             units 從 invest_twd / (avg_nav × avg_fx) 公式算出。
            with st.expander("✏️ 編輯持倉（手動微調 — 從 CHUBB 對帳單抄入精確值）",
                             expanded=True):
                st.caption(
                    "📝 從對帳單抄 5 個欄位：**淨投資金額(NT) / 平均買入淨值 / "
                    "平均買入匯率 / 平均買入含息單位成本(10) / 保單號碼**。"
                    "**持有單位數系統自動算**（= 淨投資金額 ÷ (淨值 × 匯率)）。"
                    "基金名稱/幣別/級別 從 MoneyDJ 自動帶。"
                    "OAuth 已登入會同步寫進對應保單分頁。"
                )
                # v18.59: ledger ↔ fund 匹配診斷 — 救「重新 loading 後欄位變 0」困惑
                # (v18.56 改用複合鍵 pk_str = "pid::code"；若 _T7_State 是 v18.56 前
                #  存的 7 條 ledger，新 19 條 fund 中只有 7 條能匹配，剩 12 條顯 0)
                _t7_dbg_ledgers = st.session_state.get("t7_ledgers", {}) or {}
                _t7_dbg_fund_pks = {fund_pk_str(_f) for _f in _pf_t7}
                _t7_dbg_match    = _t7_dbg_fund_pks & set(_t7_dbg_ledgers.keys())
                _t7_dbg_orphan_l = set(_t7_dbg_ledgers.keys()) - _t7_dbg_fund_pks
                _t7_dbg_empty_f  = _t7_dbg_fund_pks - set(_t7_dbg_ledgers.keys())
                _t7_dbg_color = (
                    "#00c853" if len(_t7_dbg_match) == len(_pf_t7)
                    else "#ff9800" if _t7_dbg_match
                    else "#f44336"
                )
                st.markdown(
                    f"<div style='font-size:11px;color:{_t7_dbg_color};margin:4px 0'>"
                    f"🔍 持倉診斷：{len(_pf_t7)} 個 fund 條目 / "
                    f"{len(_t7_dbg_ledgers)} 個 ledger / "
                    f"<b>{len(_t7_dbg_match)} 條匹配</b>"
                    + (f" / ⚠️ {len(_t7_dbg_empty_f)} 個 fund 顯 0（無對應 ledger）"
                       if _t7_dbg_empty_f else "")
                    + (f" / 🗑 {len(_t7_dbg_orphan_l)} 個 ledger 找不到 fund（v18.56 前舊鍵）"
                       if _t7_dbg_orphan_l else "")
                    + "</div>",
                    unsafe_allow_html=True
                )
                if _t7_dbg_orphan_l:
                    st.caption(
                        "💡 **v18.56 鍵升級提示**：v18.56 前 ledger 用 fund_code 單鍵儲存，"
                        "若您之前是這樣存的，現在跨多保單同 code 只有第一筆能對到。"
                        "請手動補填其他保單條目的單位數，並按下方「💾 套用為起始部位」存檔；"
                        "或可去掉「🗑 ledger 找不到 fund」那些舊鍵（執行下方 🧹 清理孤立 ledger）。"
                    )
                    if st.button("🧹 清理孤立 ledger（無對應 fund 條目）",
                                 key="btn_clean_orphan_ledger_v18_59",
                                 help="把那些 ledger 鍵不在當前 portfolio_funds 的條目刪掉（v18.56 前舊鍵）"):
                        _n_clean = 0
                        for _k_orph in list(_t7_dbg_orphan_l):
                            st.session_state.t7_ledgers.pop(_k_orph, None)
                            _n_clean += 1
                        st.success(f"✅ 已清掉 {_n_clean} 個孤立 ledger，下次「📦 全部寫入」會覆寫 _T7_State")
                        st.rerun()

                # v18.66: ⚡ 從 invest_twd + 最新 NAV/FX 反推單位 — 救「上方有資料下方空」
                # 使用者在保單分頁輸入「投資金額」後，這裡可一鍵填出 ledger position
                # 估算公式: units = invest_twd / (latest_nav × latest_fx)
                _t7_can_estimate = []
                for _f_est in _pf_t7:
                    _pk_est = fund_pk_str(_f_est)
                    _twd_est = float(_f_est.get("invest_twd", 0) or 0)
                    if _twd_est <= 0:
                        continue
                    _nav_est, _fx_est = _latest_nav_fx_t7(_f_est)
                    if _nav_est <= 0 or _fx_est <= 0:
                        continue
                    _ex_est = st.session_state.t7_ledgers.get(_pk_est)
                    if _ex_est is not None and float(_ex_est.position.units) > 0:
                        continue   # 已有手動輸入值，不覆蓋
                    _u_est = round(_twd_est / (_nav_est * _fx_est), 4)
                    _t7_can_estimate.append((_pk_est, _f_est, _u_est, _nav_est, _fx_est))

                if _t7_can_estimate:
                    _est_c1, _est_c2 = st.columns([3, 1])
                    with _est_c1:
                        st.info(
                            f"⚡ **{len(_t7_can_estimate)} 檔基金有 invest_twd 但 ledger 為空**，"
                            f"可從「投資金額 ÷ 最新 NAV × FX」反推估算單位。\n"
                            f"按右側按鈕一鍵填入；估算值與實際對帳單可能有 0.1~1% 偏差，"
                            f"再依需要手動修正後按「💾 套用為起始部位」存檔。"
                        )
                    with _est_c2:
                        if st.button("⚡ 自動估算填入",
                                     key="btn_t7_auto_est_v18_66",
                                     type="primary",
                                     use_container_width=True):
                            for _pk_e, _f_e, _u_e, _nav_e, _fx_e in _t7_can_estimate:
                                _c_e = _f_e.get("code", "?")
                                _ccy_e = str(_f_e.get("currency", "USD")).upper()
                                _new_led_e = _LedT7(fund_code=_c_e, currency=_ccy_e)
                                _amt_e = _u_e * _nav_e * _fx_e
                                _new_led_e.subscribe(_amt_e, _fx_e, _nav_e, _d_t7.today())
                                st.session_state.t7_ledgers[_pk_e] = _new_led_e
                            _sync_invest_twd_from_ledgers()
                            # 自動 dump _T7_State
                            try:
                                _msg_dump_e = _t7_save_snapshot_to_sheets()
                            except Exception:
                                _msg_dump_e = ""
                            st.success(
                                f"✅ 已自動估算 {len(_t7_can_estimate)} 檔的單位數 "
                                f"（用最新 NAV × FX 反推）。{_msg_dump_e}"
                            )
                            st.rerun()

                # v18.154：import compute_units 給單位數即時預覽
                from repositories.policy_repository import compute_units as _t7_compute_units
                with st.form("t7_init_pos_form", clear_on_submit=False):
                    _init_inputs = {}
                    for _f in _pf_t7:
                        _pk_f = fund_pk_str(_f)
                        _c = _f.get("code", "?")
                        _name = _name_lookup_t7.get(_pk_f, _c)
                        _ccy = str(_f.get("currency", "USD")).upper()
                        _pid_cur = _f.get("policy_id") or ""
                        _pid_disp = _pid_cur or "(未綁)"
                        _exist = st.session_state.t7_ledgers.get(_pk_f)
                        _u_default = float(_exist.position.units) if _exist else 0.0
                        _cu_default = float(_exist.position.cost_unit) if _exist else 0.0
                        _fx_default = float(_exist.position.fx_avg) if _exist else 0.0
                        # v18.154：invest_twd 優先從 portfolio_funds 取；缺則用 units × nav × fx 反算
                        _inv_default = float(_f.get("invest_twd", 0) or 0)
                        if _inv_default <= 0 and _u_default > 0 and _cu_default > 0 and _fx_default > 0:
                            _inv_default = round(_u_default * _cu_default * _fx_default)
                        # v18.154：avg_nav_with_div 從 portfolio_funds 取（與 v2 schema 同欄名）
                        _anw_default = float(_f.get("avg_nav_with_div", 0) or 0)
                        st.markdown(f"**[{_pid_disp}] {_c} — {_name[:35]}**")
                        ic1, ic2, ic3, ic4, ic5, ic6 = st.columns([1, 1, 1, 1, 1, 1])
                        _inv = ic1.number_input(
                            "🟨 淨投資金額 (NT)", min_value=0, max_value=1_000_000_000,
                            value=int(_inv_default), step=1000, format="%d",
                            key=f"t7_init_inv_{_pk_f}",
                            help="對帳單欄(4) — 系統會用此值自動算「持有單位數」"
                        )
                        _cu = ic2.number_input(
                            f"🟨 平均買入淨值 ({_ccy})", min_value=0.0, max_value=10000.0,
                            value=_cu_default,
                            step=0.01, format="%.4f", key=f"t7_init_cu_{_pk_f}",
                            help="對帳單欄(1) — 平均買入單位成本"
                        )
                        _fx = ic3.number_input(
                            f"🟨 平均買入匯率 ({_ccy}→TWD)", min_value=0.0, max_value=200.0,
                            value=_fx_default,
                            step=0.01, format="%.4f", key=f"t7_init_fx_{_pk_f}",
                            help="對帳單欄(3)"
                        )
                        # v18.157：對帳單兩種格式 — type A 有「平均買入含息單位成本」；
                        # type B 沒此欄但有「累積現金配息金額 (NT)」可反推。
                        _div_mode = ic4.radio(
                            "📋 含息來源", ["A. 含息單位成本", "B. 累積配息(NT)"],
                            key=f"t7_init_div_mode_{_pk_f}", horizontal=False,
                            help="A：直接抄欄(10)；B：用配息金額反推"
                        )
                        if _div_mode.startswith("A"):
                            _anw = ic4.number_input(
                                f"🟨 平均買入含息單位成本 ({_ccy})",
                                min_value=0.0, max_value=10000.0,
                                value=_anw_default,
                                step=0.01, format="%.4f",
                                key=f"t7_init_anw_{_pk_f}",
                                help="對帳單欄(10) — 直接抄；沒有填 0"
                            )
                            _cumul_div = 0.0
                        else:
                            _anw = 0.0
                            _cumul_div = ic4.number_input(
                                "🟨 累積現金配息金額 (NT)",
                                min_value=0.0, max_value=1_000_000_000.0,
                                value=0.0,
                                step=100.0, format="%.0f",
                                key=f"t7_init_cumul_div_{_pk_f}",
                                help="存檔時自動換算成含息成本存進去"
                            )
                        _pid_new = ic5.text_input(
                            "🟨 保單號碼", value=_pid_cur,
                            key=f"t7_init_pid_{_pk_f}",
                            placeholder="可選，e.g. PL-2024-001",
                            help="留空 = 不綁保單；若改變，會遷移 ledger 鍵與同步寫入新保單分頁"
                        )
                        # v18.170：T7 表單暴露 div_cash_pct（配息現金給付%）
                        # 0 = 全部轉換單位數（配股）／100 = 全部現金給付；介於兩者 = 部分配股
                        _dcp_default = float(_f.get("div_cash_pct", 100) or 100)
                        _dcp = ic6.number_input(
                            "🟨 現金給付 %",
                            min_value=0.0, max_value=100.0,
                            value=_dcp_default,
                            step=5.0, format="%.0f",
                            key=f"t7_init_dcp_{_pk_f}",
                            help="保險公司 APP 設定的「配息現金給付%」。"
                                 "100=全現金、0=全部轉單位（配股）、介於兩者=部分配股。"
                                 "存檔後同步寫回保單分頁；月配息估算依此拆分。",
                        )
                        # v18.154：read-only 自動算單位數預覽（公式 (4) 反推）
                        if _inv > 0 and _cu > 0 and _fx > 0:
                            _u_calc = _t7_compute_units(_inv, _cu, _fx)
                            st.caption(
                                f"⬜ 持有單位數（自動算）≈ **{_u_calc:.4f}**　"
                                f"·　{_inv:,} / ({_cu:.4f} × {_fx:.4f})"
                            )
                        else:
                            _u_calc = _u_default
                        _init_inputs[_pk_f] = (_c, _u_calc, _cu, _fx, _ccy,
                                               _pid_cur, _pid_new.strip(),
                                               _inv, _anw, _cumul_div, _dcp)
                    _init_submit = st.form_submit_button(
                        "💾 套用為起始部位（覆蓋 T7 帳本）", type="primary"
                    )
                if _init_submit:
                    _applied = 0
                    _per_policy_rows: dict[str, list[dict]] = {}
                    _pid_changes: list[tuple] = []   # v18.28: (old_pid, new_pid, code, fund)
                    # v18.179：每一檔已套用且有保單號碼的基金 (pid, code, fund_obj)，
                    # 存檔時全量 upsert 回保單分頁（不再只寫 pid 變更的）
                    _funds_to_sheet: list[tuple] = []
                    for _pk_f, (_c, _u, _cu, _fx, _ccy,
                                _pid_old, _pid_new, _inv, _anw,
                                _cumul_div, _dcp) in _init_inputs.items():
                        # v18.154：用 invest_twd 作為「有意義輸入」門檻；units 由公式算
                        if _inv <= 0 or _cu <= 0 or _fx <= 0:
                            continue
                        # v18.157：type B 對帳單 → 從累積配息反推 avg_nav_with_div
                        if _anw <= 0 and _cumul_div > 0 and _u > 0:
                            from repositories.policy_repository import (
                                avg_nav_with_div_from_cumul_div_twd as _anwd_calc)
                            _anw = _anwd_calc(_cu, _fx, _u, _cumul_div)
                        # v18.28: pid 變更 → 更新 fund.policy_id + 紀錄遷移
                        _f_obj = _fund_by_pk.get(_pk_f) or {}
                        if _pid_new != _pid_old:
                            _f_obj["policy_id"]   = _pid_new
                            _f_obj["policy_name"] = _pid_new or _f_obj.get("policy_name", "")
                            _pid_changes.append((_pid_old, _pid_new, _c, _f_obj))
                            _new_pk = fund_pk_str(_f_obj)
                            if _new_pk != _pk_f:
                                st.session_state.t7_ledgers.pop(_pk_f, None)
                                _pk_f = _new_pk
                        # v18.154：amount_twd 直接用 user 給的 invest_twd（不是 units × nav × fx
                        # 反算 — 因為 user 給的 invest_twd 是 source of truth，units 是 derived）
                        _amount_twd = float(_inv)
                        _new_led = _LedT7(fund_code=_c, currency=_ccy)
                        _new_led.subscribe(_amount_twd, _fx, _cu, _d_t7.today())
                        # v18.180：對帳單欄(10) 含息成本是「已歷經配息調整」的歷史成本，
                        # subscribe() 首買會把 cost_unit_with_div 設成 = _cu（淨值），
                        # 覆蓋掉 user 抄入的含息成本 → 含息成本永遠等於淨值、看起來沒變。
                        # 這裡用 user 給的 _anw 校正讓含息成本真正生效（_anw<=0 維持預設）。
                        if _anw > 0:
                            _new_led.position.cost_unit_with_div = float(_anw)
                        st.session_state.t7_ledgers[_pk_f] = _new_led
                        # v18.154：把 user 給的 invest_twd / avg_nav_with_div 也存進
                        # portfolio_funds，給 v2 編輯介面同步使用
                        # v18.170：div_cash_pct 也同步寫回（配息現金給付%）
                        _f_obj["invest_twd"]       = int(_inv)
                        _f_obj["avg_nav_with_div"] = float(_anw)
                        _f_obj["div_cash_pct"]     = max(0.0, min(100.0, float(_dcp)))
                        # v18.198：完整成本基礎也存進 portfolio_funds（供保單分頁寫全 + JSON）
                        _f_obj["avg_nav"]          = float(_cu)
                        _f_obj["fx_avg"]           = float(_fx)
                        _f_obj["units"]            = float(_u)
                        _applied += 1
                        # v18.179：記下有保單號碼的基金，存檔時全量回寫保單分頁
                        if _pid_new:
                            _funds_to_sheet.append((_pid_new, _c, _f_obj))
                        # 雙寫到 _Ledgers（用 new pid）
                        _pid_w = _pid_new
                        if _pid_w:
                            _per_policy_rows.setdefault(_pid_w, []).append({
                                "date":          _d_t7.today().isoformat(),
                                "code":          _c,
                                "action":        "buy",
                                "units":         _u,
                                "nav_at_action": _cu,
                                "twd":           _amount_twd,
                                "fee":           0.0,
                                "note":          "T7 init position",
                            })
                    _sync_invest_twd_from_ledgers()

                    # P4 D2: dual-write to Google Sheets `_Ledgers` tab（OAuth 模式）
                    _gsheet_sync_msg = ""
                    _pid_migrate_msg = ""
                    _sheet_upsert_msg = ""
                    if _per_policy_rows or _pid_changes or _funds_to_sheet:
                        _cfg = _resolve_oauth_cfg()
                        _tokens = st.session_state.get("gsheet_tokens")
                        _sid = st.session_state.get("policy_sheet_id")
                        if _cfg and _tokens and _sid:
                            try:
                                _t = ensure_fresh_tokens(dict(_tokens),
                                    _cfg["client_id"], _cfg["client_secret"])
                                st.session_state["gsheet_tokens"] = _t
                                _creds = build_credentials_from_tokens(_t,
                                    _cfg["client_id"], _cfg["client_secret"])
                                _client = get_gspread_client_from_oauth(_creds)
                                _total = 0
                                for _pid_w2, _rows_w2 in _per_policy_rows.items():
                                    _total += replace_ledgers_for_policy(
                                        _client, _sid, _pid_w2, _rows_w2)
                                _gsheet_sync_msg = (
                                    f" + Sheets `_Ledgers` 寫入 {_total} 筆")
                                # v18.179：全量回寫 — 每一檔有保單號碼的基金都 upsert 進
                                # 保單分頁。原本只寫 pid 變更的（_pid_changes），導致同保單內
                                # 編輯/新增的淨投資金額不會回寫到使用者實際讀寫的分頁，被迫每次
                                # 下載手改。改成寫 _funds_to_sheet（涵蓋新增 + 同保單編輯）。
                                _changed_codes = {
                                    (_pn, _code) for _po, _pn, _code, _fobj in _pid_changes}
                                _upserted = 0
                                for _pid_w3, _code_w3, _fobj_w3 in _funds_to_sheet:
                                    try:
                                        upsert_fund_in_policy(_client, _sid, _pid_w3, {
                                            "fund_url":     _code_w3,
                                            "policy_name":  _pid_w3,
                                            "invest_twd":   int(_fobj_w3.get("invest_twd", 0) or 0),
                                            "invest_date":  "",
                                            "currency":     str(_fobj_w3.get("currency", "")),
                                            "fx_at_buy":    0.0,
                                            "notes":        ("T7 pid migrate"
                                                             if (_pid_w3, _code_w3) in _changed_codes
                                                             else "T7 套用起始部位"),
                                            "policy_tier":  ("core" if _fobj_w3.get("is_core")
                                                             else "satellite"
                                                             if _fobj_w3.get("is_core") is False
                                                             else ""),
                                            # v18.183：現金給付% + 含息成本也寫進保單分頁
                                            "div_cash_pct":     float(_fobj_w3.get("div_cash_pct", 100) or 0),
                                            "avg_nav_with_div": float(_fobj_w3.get("avg_nav_with_div", 0) or 0),
                                            # v18.198：完整成本基礎（平均買入淨值/匯率/單位數）
                                            "avg_nav":          float(_fobj_w3.get("avg_nav", 0) or 0),
                                            "fx_avg":           float(_fobj_w3.get("fx_avg", 0) or 0),
                                            "units":            float(_fobj_w3.get("units", 0) or 0),
                                        })
                                        _upserted += 1
                                    except (PolicySheetError, OAuthError) as _e_mi:
                                        _pid_migrate_msg = f" ⚠️ 保單分頁同步失敗：{str(_e_mi)[:60]}"
                                if _upserted:
                                    _sheet_upsert_msg = f" + 保單分頁回寫 {_upserted} 檔"
                                if _funds_to_sheet:
                                    # 刷新 policy_tabs cache（可能新建分頁）
                                    try:
                                        st.session_state["policy_tabs"] = (
                                            list_policy_worksheets(_client, _sid))
                                    except Exception:
                                        pass   # noqa: smoke-allow-pass — cache 刷失敗不擋
                            except (PolicySheetError, OAuthError) as _e_sy:
                                _gsheet_sync_msg = (
                                    f" ⚠️ Sheets 同步失敗：{str(_e_sy)[:60]}")
                            except Exception as _e_sy:
                                _gsheet_sync_msg = (
                                    f" ⚠️ Sheets 例外：{str(_e_sy)[:60]}")

                    if _applied > 0:
                        _pid_chg_summary = (
                            f"  • 保單號碼變更 {len(_pid_changes)} 檔"
                            if _pid_changes else ""
                        )
                        _msg_init_state = _t7_save_snapshot_to_sheets()
                        st.success(
                            f"✅ 已套用 {_applied} 檔起始部位{_pid_chg_summary}，T7 帳本已更新。"
                            f"{_gsheet_sync_msg}{_sheet_upsert_msg}{_pid_migrate_msg}{_msg_init_state}"
                        )
                        st.rerun()
                    else:
                        st.warning("⚠️ 持有/NAV/匯率三欄都填 > 0 才會套用該檔基金。")

            # ── v18.4 方案 (scenario) 基礎建設 ───────────────────────────────
            if "t7_scenarios" not in st.session_state:
                st.session_state.t7_scenarios = []
            _T7_SCENARIO_LIMIT = 5

            def _t7_snapshot_ledgers() -> dict:
                """序列化成 dict[pk_str -> Ledger.to_dict()]（P2 後 key 為 "policy_id::code"）。"""
                return {pk: l.to_dict()
                        for pk, l in st.session_state.t7_ledgers.items()}

            def _t7_restore_ledgers(snap: dict) -> None:
                """把 snapshot 還原成主帳本（覆蓋 t7_ledgers）；接受 pk_str 鍵。"""
                st.session_state.t7_ledgers = {
                    pk: _LedT7.from_dict(d) for pk, d in snap.items()
                }

            def _t7_summary_from_ledgers(ledgers: dict,
                                          nav_fx_cache: dict | None = None) -> dict:
                """以給定 ledgers 計算總體 summary（市值/成本/未實現損益/月配息）。

                P2：ledgers 鍵改為 pk_str = "policy_id::code"。
                nav_fx_cache 仍以 pk_str 為鍵；落帳當下抓得到 NAV/FX，
                避免 panel 渲染時抓不到 → summary 抓到 0 的 bug（v18.5 行為延續）。
                """
                _v_total = _cost_total = _ann_total = 0.0
                _cache = nav_fx_cache or {}
                for _pk, _l in ledgers.items():
                    if _l.position.units <= 0:
                        continue
                    if _pk in _cache:
                        _nav, _fx = _cache[_pk]
                    else:
                        _f = _fund_by_pk.get(_pk)
                        if _f is None:
                            # fallback：用 ledger 自己的 cost basis 當保守估值
                            _nav = _l.position.cost_unit
                            _fx  = _l.position.fx_avg
                        else:
                            _nav, _fx = _latest_nav_fx_t7(_f)
                            if not (_nav and _fx):
                                _nav = _l.position.cost_unit
                                _fx  = _l.position.fx_avg
                    _dy = _dy_lookup_t7.get(_pk, 0.0)
                    _v = _l.position.value_twd(_nav, _fx) if (_nav and _fx) else 0
                    _cost = _l.position.net_investment_twd
                    _v_total += _v
                    _cost_total += _cost
                    _ann_total += _v * _dy / 100.0
                _pl = _v_total - _cost_total
                _pl_pct = (_pl / _cost_total * 100.0) if _cost_total > 0 else 0.0
                return {
                    "total_value_twd": round(_v_total, 0),
                    "total_cost_twd": round(_cost_total, 0),
                    "unrealized_pl_twd": round(_pl, 0),
                    "unrealized_pl_pct": round(_pl_pct, 2),
                    "monthly_cashflow_twd": round(_ann_total / 12, 0),
                    "annual_cashflow_twd": round(_ann_total, 0),
                }

            def _t7_save_scenario(name: str, action_type: str, details: str,
                                   nav_fx_cache: dict | None = None) -> None:
                """落帳完後把目前 t7_ledgers 快照存進 scenarios。超過上限覆蓋最舊。

                v18.5 修正：nav_fx_cache 用於 summary 計算 + 存進 scenario 供之後重算。
                """
                from datetime import datetime as _dt_now
                _snap = _t7_snapshot_ledgers()
                _ledgers_now = {c: _LedT7.from_dict(d) for c, d in _snap.items()}
                _summary = _t7_summary_from_ledgers(_ledgers_now, nav_fx_cache)
                _scenario = {
                    "id": f"sc_{int(_dt_now.now().timestamp() * 1000)}",
                    "name": name or f"{action_type} 方案",
                    "action_type": action_type,
                    "details": details[:200],
                    "snapshot": _snap,
                    "summary": _summary,
                    "nav_fx_cache": dict(nav_fx_cache or {}),
                    "created_at": tw_now_str("%H:%M:%S"),
                }
                st.session_state.t7_scenarios.append(_scenario)
                if len(st.session_state.t7_scenarios) > _T7_SCENARIO_LIMIT:
                    st.session_state.t7_scenarios = (
                        st.session_state.t7_scenarios[-_T7_SCENARIO_LIMIT:]
                    )

            def _t7_build_navfx_cache() -> dict:
                """為所有 _pf_t7 預抓一次 NAV/FX，鍵為 pk_str（同 code 跨保單不衝突）。"""
                _cache = {}
                for _f in _pf_t7:
                    _pk_f = fund_pk_str(_f)
                    if not _pk_f or _pk_f == PK_SEP:
                        continue
                    _n, _x = _latest_nav_fx_t7(_f)
                    if _n and _x:
                        _cache[_pk_f] = (_n, _x)
                return _cache

            def _t7_run_in_scenario(action_callable) -> dict:
                """在 deepcopy 的 ledgers 上跑 action（避免污染主帳本），回傳 (snapshot, ledgers)。"""
                _backup_snap = _t7_snapshot_ledgers()
                try:
                    action_callable()
                    _new_snap = _t7_snapshot_ledgers()
                    _new_ledgers = {c: _LedT7.from_dict(d)
                                    for c, d in _new_snap.items()}
                    # 還原主帳本
                    _t7_restore_ledgers(_backup_snap)
                    return {"snapshot": _new_snap, "ledgers": _new_ledgers}
                except Exception as _e:
                    _t7_restore_ledgers(_backup_snap)
                    raise

            # 占位：tabs 處理完才渲染最新帳本，避免 1 cycle 過期
            _panel_ph = st.empty()

            _tA, _tB, _tC = st.tabs(
                ["A 新投入", "B 投入再平衡", "C 轉換再平衡 (Switch)"]
            )

            # ── A. 新投入 ───────────────────────────────────────────────────
            with _tA:
                st.caption("拿一筆新台幣加碼某檔（或多檔）基金。NAV / FX 即時自動抓取，使用者只填金額。")
                _a_mode = st.radio(
                    "加碼模式",
                    options=["既有基金", "新增基金"],
                    horizontal=True, key="t7a_mode",
                    help="既有基金 = 從目前組合中選；新增基金 = 直接輸入新代碼，submit 時自動載入 + 落帳"
                )
                # v18.81: A 新投入改為「保單先選 → 多選標的 → 各檔金額」
                #         policy + multiselect 必須在 form 外，否則 form 內無法即時 reactive
                _aopts = {fund_pk_str(f): f for f in _pf_t7}
                _a_selected_pks: list = []
                _a_sel_pid = ""
                if _a_mode == "既有基金":
                    def _pid_of_pk_a(_pk: str) -> str:
                        _ff = _aopts.get(_pk) or {}
                        return str(_ff.get("policy_id") or "").strip() or "(未綁)"
                    _a_policies = sorted({_pid_of_pk_a(p) for p in _aopts.keys()})
                    if _a_policies:
                        _a_sel_pid = st.selectbox(
                            "1️⃣ 先選保單號碼",
                            _a_policies, key="t7a_policy_pid",
                            help="同保單內可一次加碼多檔；跨保單請分次操作。",
                        )
                        _a_cands_pk = [p for p in _aopts.keys()
                                       if _pid_of_pk_a(p) == _a_sel_pid]
                        _a_selected_pks = st.multiselect(
                            "2️⃣ 選一檔或多檔標的（同一保單內）",
                            _a_cands_pk,
                            key=f"t7a_codes__{_a_sel_pid}",
                            format_func=lambda p: f"{_label_for_pk(p)}（{_aopts[p].get('currency','?')}）",
                            help="每檔下面會出現一個金額輸入框，可獨立填",
                        )
                    else:
                        st.caption("⚠️ 目前無基金可選 — 請先到 Tab3 上方加入基金 / 載入保單")

                # v18.230：A 既有基金 — 每檔分配模式（form 外，即時切換 widget）
                _a_modes: dict = {}
                if _a_mode == "既有基金" and _a_selected_pks:
                    st.markdown("**分配模式**（新標的自動帶「目標單位數」，可手動切換）")
                    _mode_cols = st.columns(min(len(_a_selected_pks), 4))
                    for _idx_m, _pk_m in enumerate(_a_selected_pks):
                        _has_pos_m = _t7_has_position(_pk_m)
                        _mode_disp_m = _mode_cols[_idx_m % len(_mode_cols)].selectbox(
                            f"{parse_pk(_pk_m)[1]}",
                            options=["💵 TWD 金額", "🎯 目標單位數"],
                            index=0 if _has_pos_m else 1,
                            key=f"t7a_mode__{_pk_m}",
                            help=("既有持倉 → 預設 TWD" if _has_pos_m
                                   else "新標的（無持倉）→ 預設目標單位數"),
                        )
                        _a_modes[_pk_m] = ("units" if _mode_disp_m.startswith("🎯")
                                            else "twd")

                # v18.230：A 新增基金 — 投入方式（form 外，即時切換 widget）
                _a_new_mode_key = "units"   # 預設單位（新標的）
                if _a_mode == "新增基金":
                    _a_new_mode_disp = st.selectbox(
                        "投入方式",
                        options=["🎯 目標單位數", "💵 TWD 金額"],
                        index=0,
                        key="t7a_new_mode",
                        help="新標的常按單位配（例：安達 100 單位）；也可改回按 TWD",
                    )
                    _a_new_mode_key = ("units" if _a_new_mode_disp.startswith("🎯")
                                        else "twd")

                with st.form("t7_form_a", clear_on_submit=False):
                    _apk = ""
                    _acode = ""
                    _a_new_code = ""
                    _aamt = 0
                    _aamt_unit_new = 0.0
                    _a_new_mode_key = "twd"
                    _a_amounts: dict = {}
                    if _a_mode == "既有基金":
                        if not _a_selected_pks:
                            st.caption("👆 先在上方選一檔以上的標的")
                        for _pk_a in _a_selected_pks:
                            _code_a_lbl = parse_pk(_pk_a)[1]
                            _name_a_full = str((_aopts.get(_pk_a) or {}).get("name", "")).strip()
                            _name_a_short = (_name_a_full[:14] + "…") if len(_name_a_full) > 14 else _name_a_full
                            _mode_a_pk = _a_modes.get(_pk_a, "twd")
                            if _mode_a_pk == "units":
                                _label_amt = (f"🎯 {_code_a_lbl}｜{_name_a_short} 目標單位數"
                                              if _name_a_short else f"🎯 {_code_a_lbl} 目標單位數")
                                _val_a = st.number_input(
                                    _label_amt, min_value=0.0, value=100.0, step=10.0,
                                    key=f"t7a_amt_unit__{_pk_a}",
                                    help="按單位數買進；提交時換算 TWD = 單位 × NAV × FX",
                                )
                                _a_amounts[_pk_a] = ("units", float(_val_a))
                            else:
                                _label_amt = (f"💵 {_code_a_lbl}｜{_name_a_short} 投入 (NTD)"
                                              if _name_a_short else f"💵 {_code_a_lbl} 投入 (NTD)")
                                _val_a = st.number_input(
                                    _label_amt, min_value=0, step=10000, value=300000,
                                    key=f"t7a_amt__{_pk_a}",
                                )
                                _a_amounts[_pk_a] = ("twd", float(_val_a))
                        if _a_selected_pks:
                            _a_total_twd = sum(v for m, v in _a_amounts.values() if m == "twd")
                            _a_total_units = sum(v for m, v in _a_amounts.values() if m == "units")
                            _summary_bits = []
                            if _a_total_twd > 0:
                                _summary_bits.append(f"💵 NT${_a_total_twd:,.0f}")
                            if _a_total_units > 0:
                                _summary_bits.append(f"🎯 {_a_total_units:,.2f} 單位（待 submit 換算 TWD）")
                            if _summary_bits:
                                st.caption(f"📊 合計投入：{'｜'.join(_summary_bits)} "
                                           f"（{len(_a_selected_pks)} 檔）")
                    else:
                        _a_new_code = st.text_input(
                            "新基金代碼或 MoneyDJ URL",
                            placeholder="例：TLZF9 / ACTI71 / ...",
                            key="t7a_new_code",
                        )
                        if _a_new_mode_key == "units":
                            _aamt_unit_new = st.number_input(
                                "🎯 目標單位數",
                                min_value=0.0, value=100.0, step=10.0,
                                key="t7a_amt_unit_new",
                                help="提交時抓 NAV/FX 換算 TWD = 單位 × NAV × FX",
                            )
                            _aamt = 0
                        else:
                            _aamt = st.number_input(
                                "💵 預計投入台幣 (NTD)",
                                min_value=0, step=10000, value=300000,
                                key="t7a_amt_new",
                            )
                            _aamt_unit_new = 0.0
                    if _a_mode == "新增基金":
                        st.info(
                            "ℹ️ 新增基金模式必須直接套用主帳本（會永久把該檔加入組合管理清單）。"
                            "若要試算多方案，請先在 Tab3 上方「組合管理」加入基金後，回此用「既有基金」模式。"
                        )
                        _a_commit_mode = "✅ 直接套用主帳本"
                        _a_scenario_name = ""
                    else:
                        _a_commit_mode = st.radio(
                            "落帳目標",
                            options=["💡 暫存為方案（不動主帳本）", "✅ 直接套用主帳本"],
                            horizontal=True, key="t7a_commit_mode",
                            help="暫存方案可同時保留多個（最多 5 個）並排比較；確認最佳方案後再「鎖定為主帳本」"
                        )
                        _a_scenario_name = st.text_input(
                            "方案名稱（暫存模式才用）",
                            placeholder="如：A 方案-加碼 TLZF9+ACCP138 各 30 萬",
                            key="t7a_scenario_name",
                        )
                    _asubmit = st.form_submit_button("💰 試算", type="primary")

                if _asubmit:
                    # ── 新增基金模式：fetch + append + 單檔 subscribe（原 flow）──
                    if _a_mode == "新增基金":
                        _new_code_clean = _a_new_code.strip().upper()
                        if not _new_code_clean:
                            st.error("❌ 請輸入新基金代碼或 URL。")
                            st.stop()
                        if any(f["code"] == _new_code_clean for f in
                               st.session_state.portfolio_funds):
                            st.warning(
                                f"⚠️ {_new_code_clean} 已在組合中，"
                                "請改用「既有基金」模式或先重新整理頁面。"
                            )
                            st.stop()
                        try:
                            with st.spinner(f"📡 抓取 {_new_code_clean}..."):
                                _new_raw = fetch_fund_from_moneydj_url(_new_code_clean)
                            if _new_raw.get("error"):
                                st.error(f"❌ 抓取失敗：{_new_raw['error']}")
                                st.stop()
                            _new_pf = {
                                "code":       _new_code_clean,
                                "invest_twd": 0,
                                "name":       _new_raw.get("fund_name") or _new_code_clean,
                                "series":     _new_raw.get("series"),
                                "dividends":  _new_raw.get("dividends", []),
                                "metrics":    _new_raw.get("metrics", {}),
                                "moneydj_raw":_new_raw,
                                "risk_metrics":_new_raw.get("risk_metrics", {}),
                                "is_core":    _is_core_fund(
                                    _new_raw.get("fund_name") or _new_code_clean),
                                "currency":   _new_raw.get("currency","")
                                              or _new_raw.get("metrics",{}).get("currency",""),
                                "loaded":     True, "load_error": None,
                            }
                            st.session_state.portfolio_funds.append(_new_pf)
                            _pf_t7.append(_new_pf)
                            _new_pk = fund_pk_str(_new_pf)
                            _aopts[_new_pk] = _new_pf
                            _fund_by_pk[_new_pk] = _new_pf
                            _name_lookup_t7[_new_pk] = (
                                _new_pf["name"] or _new_code_clean
                            )
                            _dy_lookup_t7[_new_pk] = _get_dy_t7(_new_pf)
                            _apk = _new_pk
                            _acode = _new_code_clean
                        except Exception as _e_new:
                            st.error(f"❌ 抓取例外：{_e_new}")
                            st.stop()

                        _afund = _aopts[_apk]
                        _anav, _afx = _latest_nav_fx_t7(_afund)
                        # v18.230：依 mode 換算 TWD（單位模式 → units × NAV × FX）
                        if _a_new_mode_key == "units":
                            _aamt_effective = _t7_units_to_twd(
                                _aamt_unit_new, _anav, _afx)
                            _mode_note_new = f"單位 {_aamt_unit_new:,.2f}"
                        else:
                            _aamt_effective = float(_aamt)
                            _mode_note_new = f"TWD {_aamt_effective:,.0f}"
                        if _anav <= 0 or _afx <= 0:
                            st.error("❌ 無法取得最新 NAV 或 FX，請確認網路。")
                        elif _aamt_effective <= 0:
                            st.error("❌ 投入金額（或單位數）必須大於 0。")
                        else:
                            _led = _ledger_for(_apk)
                            _new_u = _led.subscribe(
                                _aamt_effective, _afx, _anav, _d_t7.today()
                            )
                            _sync_invest_twd_from_ledgers()
                            _pid_a_sync = parse_pk(_apk)[0]
                            _msg_a = _sync_actions_to_sheet({_pid_a_sync: [{
                                "date":          _d_t7.today().isoformat(),
                                "code":          _acode,
                                "action":        "buy",
                                "units":         _new_u,
                                "nav_at_action": _anav,
                                "twd":           _aamt_effective,
                                "fee":           0.0,
                                "note":          f"T7 A 加碼（新增基金｜{_mode_note_new}）",
                            }]} if _pid_a_sync else {})
                            _msg_a_state = _t7_save_snapshot_to_sheets()
                            st.success(
                                f"✅ {_acode} 已加碼 NT${_aamt_effective:,.0f} → "
                                f"+{_new_u:,.4f} 單位（{_mode_note_new}｜已套用主帳本）"
                                f"{_msg_a}{_msg_a_state}"
                            )
                            c1, c2, c3 = st.columns(3)
                            c1.metric("即時 NAV", f"{_anav:.4f}")
                            c2.metric("即時 FX", f"{_afx:.4f}")
                            c3.metric("買入後總單位", f"{_led.position.units:,.4f}",
                                      delta=f"+{_new_u:,.4f}")

                    # ── 既有基金模式：多檔 batch（v18.81 新流程；v18.230 支援單位模式）──
                    else:
                        _a_n_valid = sum(1 for _, _v in _a_amounts.values() if _v > 0)
                        if _a_n_valid == 0:
                            st.error("❌ 請至少選一檔基金 + 填投入金額（或目標單位數）> 0")
                            st.stop()
                        _is_scenario = _a_commit_mode.startswith("💡")
                        _baseline_snap_a = (_t7_snapshot_ledgers()
                                             if _is_scenario else None)
                        _bundled_lines: list = []
                        _sheet_rows_by_pid: dict = {}
                        _navfx_cache_a = _t7_build_navfx_cache()
                        _total_amt = 0.0
                        _total_div_twd = 0.0
                        _n_ok = 0
                        _skipped: list = []
                        for _pk_a in _a_selected_pks:
                            _entry_a = _a_amounts.get(_pk_a, ("twd", 0.0))
                            _mode_a, _val_a = _entry_a
                            if _val_a <= 0:
                                continue
                            _f_a = _aopts.get(_pk_a)
                            _nav_a, _fx_a = _latest_nav_fx_t7(_f_a)
                            _code_a = parse_pk(_pk_a)[1]
                            if _nav_a <= 0 or _fx_a <= 0:
                                _skipped.append(f"`{_code_a}`（NAV/FX 抓不到）")
                                continue
                            if _mode_a == "units":
                                _amt_a = _t7_units_to_twd(_val_a, _nav_a, _fx_a)
                                _mode_tag = f"🎯 {_val_a:,.4f} 單位"
                            else:
                                _amt_a = float(_val_a)
                                _mode_tag = f"💵 NT${_amt_a:,.0f}"
                            _led_a = _ledger_for(_pk_a)
                            _new_u_a = _led_a.subscribe(
                                _amt_a, _fx_a, _nav_a, _d_t7.today()
                            )
                            _navfx_cache_a[_pk_a] = (_nav_a, _fx_a)
                            _total_amt += _amt_a
                            _dy_pk_a = _dy_lookup_t7.get(_pk_a, 0.0)
                            _total_div_twd += _amt_a * _dy_pk_a / 100.0
                            _n_ok += 1
                            _bundled_lines.append(
                                f"• `{_code_a}` {_mode_tag} → NT${_amt_a:,.0f} → "
                                f"+{_new_u_a:.4f} 單位 @ NAV {_nav_a:.4f} / FX {_fx_a:.4f}"
                            )
                            _pid_a = parse_pk(_pk_a)[0]
                            if _pid_a:
                                _sheet_rows_by_pid.setdefault(_pid_a, []).append({
                                    "date":          _d_t7.today().isoformat(),
                                    "code":          _code_a,
                                    "action":        "buy",
                                    "units":         _new_u_a,
                                    "nav_at_action": _nav_a,
                                    "twd":           _amt_a,
                                    "fee":           0.0,
                                    "note":          f"T7 A 加碼（{_mode_tag}）",
                                })
                        if _skipped:
                            st.warning("⚠️ 跳過：" + "、".join(_skipped))
                        if _n_ok == 0:
                            st.error("❌ 沒有成功加碼任何標的")
                        else:
                            if _is_scenario:
                                _t7_save_scenario(
                                    name=_a_scenario_name or
                                          f"A 加碼 {_n_ok} 檔 NT${_total_amt:,.0f}",
                                    action_type="A",
                                    details="\n".join(_bundled_lines),
                                    nav_fx_cache=_navfx_cache_a,
                                )
                                _t7_restore_ledgers(_baseline_snap_a)
                                st.info(
                                    f"💡 已暫存方案「"
                                    f"{_a_scenario_name or f'A 加碼 {_n_ok} 檔'}"
                                    f"」，主帳本未變動。"
                                )
                            else:
                                _sync_invest_twd_from_ledgers()
                                _msg_a = _sync_actions_to_sheet(_sheet_rows_by_pid)
                                _msg_a_state = _t7_save_snapshot_to_sheets()
                                st.success(
                                    f"✅ 已加碼 **{_n_ok} 檔**（合計 "
                                    f"**NT${_total_amt:,.0f}**）— 已套用主帳本"
                                    + _msg_a + _msg_a_state
                                )
                            st.markdown("\n".join(_bundled_lines))
                            _c1, _c2, _c3 = st.columns(3)
                            _c1.metric("加碼檔數", f"{_n_ok}")
                            _c2.metric("合計投入", f"NT${_total_amt:,.0f}")
                            _c3.metric(
                                "本次新增預估年配息",
                                f"NT${_total_div_twd:,.0f}",
                                help=f"≈ 月均 NT${_total_div_twd/12:,.0f}"
                            )

            # ── B. 投入再平衡 ────────────────────────────────────────────────
            with _tB:
                st.caption(
                    "拿一筆新台幣按目標權重攤分到多檔基金。"
                    "依「投入後總市值 × 目標權重 − 目前市值」缺口比例分配；"
                    "**v18.230 起支援「目標單位數」**（新標的常用，例：安達 100 單位）。"
                )

                # v18.230：B 每檔分配模式（form 外，即時切換 widget；新標的預設單位）
                _b_modes: dict = {}
                if _pf_t7:
                    with st.expander(
                        "🎛️ 各檔分配模式（預設 % 權重；新標的會自動帶單位，可手動切）",
                        expanded=False,
                    ):
                        _mode_cols_b = st.columns(min(len(_pf_t7), 4))
                        for _idx_bm, _f_bm in enumerate(_pf_t7):
                            _pk_bm = fund_pk_str(_f_bm)
                            _has_pos_bm = _t7_has_position(_pk_bm)
                            _md_bm = _mode_cols_b[_idx_bm % len(_mode_cols_b)].selectbox(
                                f"{_f_bm.get('code', '?')}",
                                options=["📊 % 權重", "🎯 目標單位"],
                                index=0 if _has_pos_bm else 1,
                                key=f"t7b_mode__{_pk_bm}",
                                help=("既有持倉" if _has_pos_bm else "新標的"),
                            )
                            _b_modes[_pk_bm] = ("units"
                                if _md_bm.startswith("🎯") else "pct")

                with st.form("t7_form_b", clear_on_submit=False):
                    _btot = st.number_input(
                        "預計投入總台幣 (NTD)", min_value=0, step=10000,
                        value=300000, key="t7b_amt"
                    )
                    st.markdown(
                        "**分配欄位**（% 模式檔需總和 ≈ 100%；單位模式檔先吃固定金額）"
                    )
                    _bweights: dict = {}
                    _b_entries: dict = {}
                    _n_pct_b = sum(1 for m in _b_modes.values() if m == "pct")
                    _w_default = round(100.0 / max(_n_pct_b, 1), 2)
                    _wcols = st.columns(min(len(_pf_t7), 4))
                    for _idx, _f in enumerate(_pf_t7):
                        _pk_f = fund_pk_str(_f)
                        _code = _f.get("code", "?")
                        _pid_disp = _f.get("policy_id") or "(未綁)"
                        # v18.73: 標籤加基金名稱，避免一片代碼看不出是哪檔
                        _name_full = str(_f.get("name") or "").strip()
                        _name_short = (_name_full[:10] + "…") if len(_name_full) > 10 else _name_full
                        _mode_f = _b_modes.get(_pk_f, "pct")
                        _help = (f"保單 {_pid_disp}｜{_name_full or _code}"
                                 f"｜代碼 {_code}")
                        if _mode_f == "units":
                            _label = (f"🎯 {_pid_disp}/{_code}｜{_name_short} 單位"
                                      if _name_short else f"🎯 {_pid_disp}/{_code} 單位")
                            _u_b = _wcols[_idx % len(_wcols)].number_input(
                                _label, min_value=0.0, value=10.0, step=1.0,
                                key=f"t7b_wu_{_pk_f}", help=_help,
                            )
                            _b_entries[_pk_f] = ("units", float(_u_b))
                        else:
                            _label = (f"📊 {_pid_disp}/{_code}｜{_name_short} 權重 %"
                                      if _name_short else f"📊 {_pid_disp}/{_code} 權重 %")
                            _w = _wcols[_idx % len(_wcols)].number_input(
                                _label, min_value=0.0, max_value=100.0,
                                value=_w_default, step=1.0, key=f"t7b_w_{_pk_f}",
                                help=_help,
                            )
                            _bweights[_pk_f] = float(_w)
                            _b_entries[_pk_f] = ("pct", float(_w))
                    _b_commit_mode = st.radio(
                        "落帳目標",
                        options=["💡 暫存為方案（不動主帳本）", "✅ 直接套用主帳本"],
                        horizontal=True, key="t7b_commit_mode",
                    )
                    _b_scenario_name = st.text_input(
                        "方案名稱（暫存模式才用）",
                        placeholder="如：B 方案-30 萬攤至 5 檔",
                        key="t7b_scenario_name",
                    )
                    _bsubmit = st.form_submit_button(
                        "🧮 試算分配", type="primary"
                    )

                if _bsubmit:
                    # v18.230：混搭模式 — 拆 % vs 單位
                    _pct_pks_b = [pk for pk, (m, _) in _b_entries.items() if m == "pct"]
                    _units_pks_b = [pk for pk, (m, _) in _b_entries.items() if m == "units"]
                    _wsum = sum(_b_entries[pk][1] for pk in _pct_pks_b) if _pct_pks_b else 0.0

                    if _btot <= 0:
                        st.error("❌ 投入總額必須大於 0。")
                    elif _pct_pks_b and abs(_wsum - 100.0) > 0.5:
                        st.error(f"❌ % 模式檔權重總和 = {_wsum:.2f}%，超出 ± 0.5% 容忍度。")
                    else:
                        _is_scenario_b = _b_commit_mode.startswith("💡")
                        _baseline_snap_b = (_t7_snapshot_ledgers()
                                             if _is_scenario_b else None)
                        # 抓全部基金的 NAV/FX 與目前市值
                        _navfx = {}
                        _v_curr = {}
                        for _f in _pf_t7:
                            _pk_f = fund_pk_str(_f)
                            _n, _x = _latest_nav_fx_t7(_f)
                            _navfx[_pk_f] = (_n, _x, str(_f.get("currency", "USD")).upper())
                            _l = _ledger_for(_pk_f)
                            _v_curr[_pk_f] = (
                                _l.position.value_twd(_n, _x) if (_n and _x) else 0.0
                            )

                        # 單位模式檔：固定金額 = units × NAV × FX（先吃投入額）
                        _units_fixed: dict = {}
                        _units_amt_sum = 0.0
                        _bad_units: list = []
                        for _pk_u in _units_pks_b:
                            _u_b = _b_entries[_pk_u][1]
                            if _u_b <= 0:
                                continue
                            _n_u, _x_u, _ = _navfx[_pk_u]
                            if _n_u <= 0 or _x_u <= 0:
                                _bad_units.append(parse_pk(_pk_u)[1])
                                continue
                            _amt_u = _t7_units_to_twd(_u_b, _n_u, _x_u)
                            _units_fixed[_pk_u] = _amt_u
                            _units_amt_sum += _amt_u

                        if _bad_units:
                            st.warning(
                                f"⚠️ 單位模式跳過：{'、'.join(_bad_units)}（NAV/FX 抓不到）"
                            )

                        _remaining = float(_btot) - _units_amt_sum
                        if _remaining < -1.0:
                            st.error(
                                f"❌ 單位模式檔總額 NT${_units_amt_sum:,.0f} > "
                                f"投入 NT${float(_btot):,.0f}（多 "
                                f"NT${-_remaining:,.0f}）"
                            )
                            st.stop()
                        _remaining = max(_remaining, 0.0)

                        # % 模式檔：按缺口比例分配 _remaining
                        _wn = {pk: _b_entries[pk][1] for pk in _pct_pks_b}
                        if _pct_pks_b:
                            _last = _pct_pks_b[-1]
                            _wn[_last] += (100.0 - _wsum)
                            _v_post = sum(_v_curr.values()) + float(_btot)
                            _gaps = {
                                pk: max(_v_post * _wn[pk] / 100.0 - _v_curr[pk], 0.0)
                                for pk in _pct_pks_b
                            }
                            _g_sum = sum(_gaps.values())
                        else:
                            _gaps = {}
                            _g_sum = 0.0
                        _rows = []
                        _b_ann_total = 0.0
                        _b_rows_by_pid: dict[str, list[dict]] = {}   # v18.27 dual-write 收集

                        def _b_book(pk: str, share_twd: float, mode_tag: str) -> None:
                            """共用：subscribe + 收集 sheet rows + result row。"""
                            _n, _x, _ccy = _navfx[pk]
                            _orig = share_twd / _x if _x > 0 else 0
                            _units = _orig / _n if _n > 0 else 0
                            if share_twd > 0 and _n > 0 and _x > 0:
                                _ledger_for(pk).subscribe(
                                    share_twd, _x, _n, _d_t7.today()
                                )
                                _pid_g_b = parse_pk(pk)[0]
                                if _pid_g_b:
                                    _b_rows_by_pid.setdefault(_pid_g_b, []).append({
                                        "date":          _d_t7.today().isoformat(),
                                        "code":          parse_pk(pk)[1],
                                        "action":        "buy",
                                        "units":         _units,
                                        "nav_at_action": _n,
                                        "twd":           share_twd,
                                        "fee":           0.0,
                                        "note":          f"T7 B 再平衡（{mode_tag}）",
                                    })
                            _dy_b = _dy_lookup_t7.get(pk, 0.0)
                            _ann_b = share_twd * _dy_b / 100.0
                            _ann_acc["ann_total"] += _ann_b
                            _pid_b, _code_b = parse_pk(pk)
                            _rows.append({
                                "保單": _pid_b or "(未綁)",
                                "基金": _code_b,
                                "模式": mode_tag,
                                "配置": (f"{_wn.get(pk, 0):.2f}%"
                                         if pk in _wn else
                                         f"🎯 {_b_entries[pk][1]:,.2f} U"),
                                "目前市值 TWD": f"{_v_curr[pk]:,.0f}",
                                "缺口 TWD": (f"{_gaps.get(pk, 0):,.0f}"
                                             if pk in _gaps else "—"),
                                "應買 TWD": f"{share_twd:,.0f}",
                                f"應買 {_ccy}": f"{_orig:,.2f}",
                                "預估單位": f"{_units:,.4f}",
                                "配息率": f"{_dy_b:.2f}%",
                                "本次加碼年配息(TWD)": f"NT${_ann_b:,.0f}",
                            })

                        _ann_acc = {"ann_total": 0.0}   # 解 nonlocal 限制
                        # 先記錄單位模式檔
                        for _pk_u, _amt_u in _units_fixed.items():
                            _b_book(_pk_u, _amt_u, "🎯 單位")
                        # 再分配 % 模式檔（缺口比例）
                        for _pk_g in _pct_pks_b:
                            _gap = _gaps.get(_pk_g, 0.0)
                            _share_twd = (
                                _remaining * _gap / _g_sum if _g_sum > 0 else 0.0
                            )
                            _b_book(_pk_g, _share_twd, "📊 %")
                        _b_ann_total = _ann_acc["ann_total"]
                        st.dataframe(
                            pd.DataFrame(_rows),
                            use_container_width=True, hide_index=True
                        )
                        bh1, bh2, bh3 = st.columns(3)
                        bh1.metric("本次投入 TWD", f"NT${float(_btot):,.0f}")
                        bh2.metric(
                            "💵 預估年配息（本次加碼）",
                            f"NT${_b_ann_total:,.0f}",
                            help="= Σ 各檔 應買 TWD × 配息率"
                        )
                        bh3.metric(
                            "📅 月均（÷12）",
                            f"NT${_b_ann_total/12:,.0f}"
                        )
                        if _is_scenario_b:
                            # 從 _navfx 已收集的資料 build cache（_navfx[pk] = (n, x, ccy)）
                            _navfx_cache_b = {p: (v[0], v[1])
                                              for p, v in _navfx.items()
                                              if v[0] and v[1]}
                            _t7_save_scenario(
                                name=_b_scenario_name or
                                     f"B 投入再平衡 NT${float(_btot):,.0f}",
                                action_type="B",
                                details=(
                                    f"投入 NT${float(_btot):,.0f} 攤至 "
                                    f"{len(_wn)} 檔（總和 {sum(_wn.values()):.2f}%）"
                                ),
                                nav_fx_cache=_navfx_cache_b,
                            )
                            _t7_restore_ledgers(_baseline_snap_b)
                            st.info(
                                f"💡 已暫存方案「"
                                f"{_b_scenario_name or 'B 投入再平衡'}"
                                "」，主帳本未變動。可下方面板比較或鎖定。"
                            )
                        else:
                            _sync_invest_twd_from_ledgers()
                            _msg_b = _sync_actions_to_sheet(_b_rows_by_pid)
                            _msg_b_state = _t7_save_snapshot_to_sheets()
                            st.success(
                                f"✅ 已落帳（已套用主帳本），組合權重已朝目標靠攏（總和 "
                                f"{sum(_wn.values()):.2f}%）{_msg_b}{_msg_b_state}"
                            )

            # ── C. 轉換再平衡 [核心，M→N action-driven，v18.5] ──────────────
            with _tC:
                st.caption(
                    "**多賣方組 + 各自買方組** 複合轉換。例：A 賣 10% 配 C / "
                    "B 賣 20% 配 D, E。同幣別 → fx_avg 嚴格繼承；跨幣別 → 即期立帳。"
                )
                # 候選清單（pk_str 為主鍵，跨保單同代碼可區分）：必須有正單位數
                _c_candidates = [
                    fund_pk_str(f) for f in _pf_t7
                    if (st.session_state.t7_ledgers.get(fund_pk_str(f)) is not None
                        and st.session_state.t7_ledgers[fund_pk_str(f)].position.units > 0)
                ]
                _c_all_pks = [fund_pk_str(f) for f in _pf_t7]

                # v18.74: 保單卡控 — 同一保單號碼才能互相轉換（同合約內基金互換才合法）
                def _pid_of_pk(_pk: str) -> str:
                    _ff = _fund_by_pk.get(_pk) or {}
                    return str(_ff.get("policy_id") or "").strip() or "(未綁)"

                if not _c_candidates:
                    st.info(
                        "ℹ️ 目前帳本無任何持倉部位，"
                        "請先用「📝 編輯初始持倉」或 A / B 落帳建立部位後再轉換。"
                    )
                else:
                    # 1️⃣ 先選保單號碼（同保單內互轉才合法；跨保單轉換要走贖回+申購）
                    _c_policies = sorted({_pid_of_pk(p) for p in _c_candidates})
                    _sel_pid = st.selectbox(
                        "1️⃣ 先選保單號碼（同保單內才能互轉，避免跨保單錯帳）",
                        _c_policies,
                        key="t7c_policy_pid",
                        help="跨保單的資金搬移需先贖回再申購、不能用 switch；此處只列同保單內互轉。",
                    )
                    # 同保單下：賣方候選 = 該保單下有部位的基金；
                    # 買方候選 = 該保單下所有基金（不限有部位，可加碼新標的）
                    _c_cands_pid = [p for p in _c_candidates if _pid_of_pk(p) == _sel_pid]
                    _c_all_pks_pid = [p for p in _c_all_pks if _pid_of_pk(p) == _sel_pid]
                    if len(_c_cands_pid) < 1:
                        st.warning(f"⚠️ 保單 `{_sel_pid}` 下無任何持倉部位，無法執行轉換。")
                        _sell_pks = []
                    elif len(_c_all_pks_pid) < 2:
                        st.warning(
                            f"⚠️ 保單 `{_sel_pid}` 下只有 {len(_c_all_pks_pid)} 檔基金，"
                            "無法執行轉換（至少需 2 檔，買賣不能同檔）。"
                        )
                        _sell_pks = []
                    else:
                        # 用保單號碼當 widget key 後綴，切換保單時自動重置選擇，
                        # 避免殘留跨保單的 pk 觸發 StreamlitAPIException。
                        _sell_pks = st.multiselect(
                            "2️⃣ 賣方組（**可多選**，最多 5 檔；每個賣方下面會有自己的買方組與權重）",
                            _c_cands_pid,
                            default=_c_cands_pid[:1] if _c_cands_pid else [],
                            max_selections=5,
                            key=f"t7c_sell_codes__{_sel_pid}",
                            format_func=lambda p: _label_for_pk(p),
                            help=(
                                "M→N 複合轉換：一次選 1~5 個賣方，每個賣方各自設定賣 % "
                                "+ 對應的 1~5 個買方 + 各買方權重 — 比例獨立計算。\n"
                                "例：A 賣 10% → C 100% / B 賣 20% → D 60% E 40%"
                            ),
                        )
                    if not _sell_pks:
                        if _c_candidates and _c_cands_pid:
                            st.warning("⚠️ 請至少選一檔賣方。")
                    else:
                        # v18.84: 已選賣方數量即時提示，提醒使用者可繼續加
                        _n_sel = len(_sell_pks)
                        st.caption(
                            f"📋 已選 **{_n_sel} 個賣方** — 下方每個賣方獨立設定買方組 "
                            f"+ 比例個別計算（最多可再加 {5 - _n_sel} 個）"
                            if _n_sel < 5 else
                            f"📋 已選滿 5 個賣方（上限）"
                        )
                        # v18.82: 賣方 / 買方 視覺分區 — 紅區（賣）+ 綠區（買）
                        # 使用者反饋「賣方與買方分開區塊 放在一起會看錯」
                        # 用色塊 header + divider 強化視覺分離
                        _sell_configs = {}  # sell_pk -> {sell_pct, buy_weights}
                        for _idx_s, _spk in enumerate(_sell_pks):
                            _slabel = _label_for_pk(_spk)
                            with st.expander(
                                f"🔁 #{_idx_s+1}　賣方 {_slabel}",
                                expanded=(_idx_s == 0),
                            ):
                                # ─── 紅區：賣方設定 ───
                                st.markdown(
                                    "<div style='background:linear-gradient(90deg,#3a1a1a,#2a1010);"
                                    "border-left:4px solid #f44336;border-radius:0 6px 6px 0;"
                                    "padding:8px 14px;margin-bottom:8px'>"
                                    "<span style='color:#ff7043;font-weight:700;font-size:13px'>"
                                    "📉 賣方設定</span>"
                                    f"<span style='color:#888;font-size:11px;margin-left:8px'>"
                                    f"{_slabel}</span></div>",
                                    unsafe_allow_html=True,
                                )
                                # v18.230：賣方支援「賣出 %」或「賣出單位數」
                                _sl_units = float(
                                    getattr(
                                        getattr(
                                            st.session_state.t7_ledgers.get(_spk),
                                            "position", None),
                                        "units", 0.0) or 0.0
                                )
                                _sm_cols = st.columns([1, 3])
                                _sell_mode_disp = _sm_cols[0].selectbox(
                                    "賣方模式",
                                    options=["💱 賣出 %", "🎯 賣出單位數"],
                                    index=0,
                                    key=f"t7c2_sm_{_spk}",
                                    label_visibility="collapsed",
                                )
                                _sell_mode_key = ("units"
                                    if _sell_mode_disp.startswith("🎯") else "pct")
                                if _sell_mode_key == "pct":
                                    _sp = _sm_cols[1].number_input(
                                        "賣出 % 部位（從此檔當前持有單位賣出多少）",
                                        min_value=1.0, max_value=100.0,
                                        value=10.0, step=5.0,
                                        key=f"t7c2_sp_{_spk}",
                                        help="此部位目前持有單位中賣出多少 %",
                                    )
                                    _sp_units_val = 0.0
                                else:
                                    _max_u_s = max(_sl_units, 0.001)
                                    _default_u_s = (round(_sl_units * 0.1, 4)
                                                    if _sl_units > 0 else 1.0)
                                    _sp_units_val = _sm_cols[1].number_input(
                                        f"🎯 賣出單位數（最大 {_sl_units:,.4f}）",
                                        min_value=0.0, max_value=_max_u_s,
                                        value=min(_default_u_s, _max_u_s),
                                        step=max(round(_sl_units * 0.05, 4), 0.01),
                                        key=f"t7c2_spu_{_spk}",
                                        help="從此部位贖回多少「單位」（U）",
                                    )
                                    _sp = 0.0   # 純單位模式：% 不參與計算

                                st.markdown(
                                    "<div style='height:1px;background:linear-gradient(90deg,"
                                    "transparent,#30363d 30%,#30363d 70%,transparent);"
                                    "margin:14px 0'></div>",
                                    unsafe_allow_html=True,
                                )

                                # ─── 綠區：買方設定 ───
                                st.markdown(
                                    "<div style='background:linear-gradient(90deg,#0d2a1a,#0a1f12);"
                                    "border-left:4px solid #00c853;border-radius:0 6px 6px 0;"
                                    "padding:8px 14px;margin-bottom:8px'>"
                                    "<span style='color:#69f0ae;font-weight:700;font-size:13px'>"
                                    "📈 買方組（此賣款導向以下標的）</span>"
                                    f"<span style='color:#888;font-size:11px;margin-left:8px'>"
                                    f"同保單 {_sel_pid} 下，最多 5 檔</span></div>",
                                    unsafe_allow_html=True,
                                )
                                # v18.74: 買方候選限制在同保單（_c_all_pks_pid）
                                _b_opts = [p for p in _c_all_pks_pid if p != _spk]
                                _bcs = st.multiselect(
                                    "買方標的（複選）",
                                    _b_opts,
                                    default=_b_opts[:1] if _b_opts else [],
                                    max_selections=5,
                                    key=f"t7c2_bcs_{_spk}",
                                    format_func=lambda p: _label_for_pk(p),
                                )
                                _bweights: dict = {}
                                _buy_entries: dict = {}   # v18.230: pk -> ("pct"|"units", val)
                                if _bcs:
                                    # v18.230：每個買方一行 mode selectbox（新標的自動帶單位）
                                    st.caption(
                                        "**買方分配模式**（新標的自動帶單位；可與 % 混搭——"
                                        "單位模式檔先吃固定金額，剩餘按 % 攤分）"
                                    )
                                    _bmode_cols = st.columns(min(len(_bcs), 5))
                                    _buy_modes: dict = {}
                                    for _j, _bpk in enumerate(_bcs):
                                        _has_pos_b = _t7_has_position(_bpk)
                                        _bmd = _bmode_cols[_j % len(_bmode_cols)].selectbox(
                                            f"{_label_for_pk(_bpk)}",
                                            options=["📊 % 權重", "🎯 目標單位"],
                                            index=0 if _has_pos_b else 1,
                                            key=f"t7c2_bm_{_spk}_{_bpk}",
                                            help=("既有持倉" if _has_pos_b else "新標的"),
                                        )
                                        _buy_modes[_bpk] = ("units"
                                            if _bmd.startswith("🎯") else "pct")

                                    # 渲染 value widgets
                                    _n_pct = sum(1 for m in _buy_modes.values() if m == "pct")
                                    _wd = round(100.0 / max(_n_pct, 1), 2)
                                    _wcols = st.columns(min(len(_bcs), 5))
                                    for _j, _bpk in enumerate(_bcs):
                                        _bm = _buy_modes[_bpk]
                                        if _bm == "pct":
                                            _w = _wcols[_j % len(_wcols)].number_input(
                                                f"📊 {_label_for_pk(_bpk)} %",
                                                min_value=0.0, max_value=100.0,
                                                value=_wd, step=1.0,
                                                key=f"t7c2_w_{_spk}_{_bpk}",
                                            )
                                            _bweights[_bpk] = float(_w)
                                            _buy_entries[_bpk] = ("pct", float(_w))
                                        else:
                                            _u_b = _wcols[_j % len(_wcols)].number_input(
                                                f"🎯 {_label_for_pk(_bpk)} 單位",
                                                min_value=0.0, value=100.0, step=10.0,
                                                key=f"t7c2_wu_{_spk}_{_bpk}",
                                                help="按單位數買進；提交時換算 TWD 並從賣方贖回金額扣除",
                                            )
                                            _buy_entries[_bpk] = ("units", float(_u_b))
                                    # 顯示權重合計（只計 % 模式檔）
                                    if _n_pct > 0:
                                        _wsum_disp = sum(_bweights.values())
                                        _wsum_color = ("#00c853"
                                            if abs(_wsum_disp - 100.0) <= 0.5 else "#f44336")
                                        st.markdown(
                                            f"<div style='text-align:right;font-size:12px;"
                                            f"color:{_wsum_color};margin-top:4px'>"
                                            f"% 模式買方權重合計：<b>{_wsum_disp:.2f}%</b>"
                                            f" / {_n_pct} 檔</div>",
                                            unsafe_allow_html=True,
                                        )
                                    else:
                                        st.markdown(
                                            "<div style='text-align:right;font-size:12px;"
                                            "color:#888;margin-top:4px'>"
                                            "（全部買方使用 🎯 單位模式）</div>",
                                            unsafe_allow_html=True,
                                        )
                                _sell_configs[_spk] = {
                                    "sell_mode": _sell_mode_key,
                                    "sell_pct": float(_sp),
                                    "sell_units": float(_sp_units_val),
                                    "buy_weights": _bweights,
                                    "buy_entries": _buy_entries,
                                }

                        _c_commit_mode = st.radio(
                            "落帳目標",
                            options=["💡 暫存為方案（不動主帳本）",
                                     "✅ 直接套用主帳本"],
                            horizontal=True, key="t7c_commit_mode",
                        )
                        _c_scenario_name = st.text_input(
                            "方案名稱（暫存模式才用）",
                            placeholder=f"如：C 方案-複合轉換 {len(_sell_pks)} 賣方",
                            key="t7c_scenario_name",
                        )
                        _csubmit = st.button("🔁 試算 M→N 複合轉換", type="primary",
                                             key="t7c_submit_btn")

                        if _csubmit:
                            # v18.230：混搭模式校驗 — % 模式檔權重和必須 ≈ 100%（如有）
                            # 全部單位模式則略過 % 校驗
                            _bad_sells = []
                            for _spk, _cfg in _sell_configs.items():
                                _bes = _cfg.get("buy_entries") or {}
                                if not _bes:
                                    _bad_sells.append(f"{_label_for_pk(_spk)}（無買方）")
                                    continue
                                _pct_only = [v for m, v in _bes.values() if m == "pct"]
                                if _pct_only:
                                    _wsum = sum(_pct_only)
                                    if abs(_wsum - 100.0) > 0.5:
                                        _bad_sells.append(
                                            f"{_label_for_pk(_spk)}（% 模式檔權重 "
                                            f"{_wsum:.2f}% ≠ 100%）"
                                        )
                                # 賣方單位模式：校驗 ≤ 持倉
                                if _cfg.get("sell_mode") == "units":
                                    _u_in = float(_cfg.get("sell_units", 0.0))
                                    _u_have = float(getattr(getattr(
                                        st.session_state.t7_ledgers.get(_spk),
                                        "position", None), "units", 0.0) or 0.0)
                                    if _u_in <= 0:
                                        _bad_sells.append(
                                            f"{_label_for_pk(_spk)}（賣出單位 = 0）")
                                    elif _u_in > _u_have + 1e-6:
                                        _bad_sells.append(
                                            f"{_label_for_pk(_spk)}（賣出單位 "
                                            f"{_u_in:.4f} > 持倉 {_u_have:.4f}）")
                            if _bad_sells:
                                st.error(
                                    "❌ 配置錯誤：" + "／".join(_bad_sells)
                                    + "（混搭時 % 模式檔需 = 100% ± 0.5%；"
                                    "單位模式需 ≤ 持倉）"
                                )
                            else:
                                _is_scenario_c = _c_commit_mode.startswith("💡")
                                _baseline_snap_c = (_t7_snapshot_ledgers()
                                                     if _is_scenario_c else None)
                                # 預先抓所有涉及基金的 NAV/FX，存進 cache（鍵：pk_str）
                                _navfx_cache_c = {}
                                _all_pks_c = set(_sell_pks) | {
                                    bp for cfg in _sell_configs.values()
                                    for bp in (cfg.get("buy_entries") or {}).keys()
                                }
                                for _pk_x in _all_pks_c:
                                    _f = _fund_by_pk.get(_pk_x)
                                    if _f:
                                        _n, _x = _latest_nav_fx_t7(_f)
                                        if _n and _x:
                                            _navfx_cache_c[_pk_x] = (_n, _x)
                                # baseline cost basis 守恆計算
                                _baseline_costs = {}
                                for _spk in _sell_pks:
                                    _l = st.session_state.t7_ledgers[_spk]
                                    _baseline_costs[_spk] = {
                                        "cost_unit": _l.position.cost_unit,
                                        "fx_avg": _l.position.fx_avg,
                                        "units_total": _l.position.units,
                                    }
                                _result_rows = []  # 全域 (sell_pk, buy_pk) 明細
                                _c_rows_by_pid: dict[str, list[dict]] = {}   # v18.27 dual-write
                                _twd_total_moved = 0.0
                                _ann_gain_total = 0.0
                                _ann_lost_total = 0.0
                                _expected_total = 0.0
                                try:
                                    for _spk, _cfg in _sell_configs.items():
                                        _Sf = _fund_by_pk.get(_spk)
                                        _na, _xa = _navfx_cache_c.get(
                                            _spk, _latest_nav_fx_t7(_Sf)
                                        )
                                        _S = {
                                            "nav": _na, "fx": _xa,
                                            "ccy": str(_Sf.get("currency", "USD")
                                                       ).upper(),
                                            "ledger": _ledger_for(_spk),
                                        }
                                        # v18.230：賣方支援 pct/units 兩種模式
                                        if _cfg.get("sell_mode") == "units":
                                            _u_redeem_s = float(_cfg.get("sell_units", 0.0))
                                        else:
                                            _u_redeem_s = (
                                                _baseline_costs[_spk]["units_total"]
                                                * _cfg["sell_pct"] / 100.0
                                            )
                                        _u_redeem_s = min(
                                            _u_redeem_s,
                                            _baseline_costs[_spk]["units_total"]
                                        )
                                        if _u_redeem_s <= 0 or _S["nav"] <= 0:
                                            raise ValueError(
                                                f"賣方 {_label_for_pk(_spk)}：賣出 units = 0 或 NAV 抓不到"
                                            )
                                        _expected_total += (
                                            _u_redeem_s
                                            * _baseline_costs[_spk]["cost_unit"]
                                            * _baseline_costs[_spk]["fx_avg"]
                                        )
                                        # 失去 A 配息
                                        _dy_S = _dy_lookup_t7.get(_spk, 0.0)
                                        _ann_lost_total += (
                                            _u_redeem_s * _S["nav"] * _S["fx"]
                                            * _dy_S / 100.0
                                        )
                                        # v18.230：混搭分配 — 先算每買方目標 TWD
                                        _R_total = _u_redeem_s * _S["nav"] * _S["fx"]
                                        _bes_c = _cfg.get("buy_entries") or {}
                                        _target_amt: dict = {}
                                        _units_amt_sum = 0.0
                                        for _bpk_x, (_bm_x, _bv_x) in _bes_c.items():
                                            if _bm_x == "units":
                                                _Bf_x = _fund_by_pk.get(_bpk_x)
                                                _nb_x, _xb_x = _navfx_cache_c.get(
                                                    _bpk_x,
                                                    _latest_nav_fx_t7(_Bf_x)
                                                )
                                                if _nb_x <= 0 or _xb_x <= 0:
                                                    raise ValueError(
                                                        f"買方 {_label_for_pk(_bpk_x)} "
                                                        "NAV/FX 抓不到"
                                                    )
                                                _amt_x = _t7_units_to_twd(
                                                    _bv_x, _nb_x, _xb_x)
                                                _target_amt[_bpk_x] = _amt_x
                                                _units_amt_sum += _amt_x
                                            else:
                                                _target_amt[_bpk_x] = None  # 待分剩餘
                                        _remaining = _R_total - _units_amt_sum
                                        if _remaining < -1.0:   # 容忍 1 TWD 浮點
                                            raise ValueError(
                                                f"賣方 {_label_for_pk(_spk)}：買方單位"
                                                f"模式總額 NT${_units_amt_sum:,.0f} "
                                                f"> 贖回 NT${_R_total:,.0f}（多 "
                                                f"NT${-_remaining:,.0f}）"
                                            )
                                        _remaining = max(_remaining, 0.0)
                                        _pct_total = sum(
                                            v for m, v in _bes_c.values() if m == "pct")
                                        if _pct_total > 0:
                                            for _bpk_p, (_bm_p, _bv_p) in _bes_c.items():
                                                if _bm_p == "pct":
                                                    _target_amt[_bpk_p] = (
                                                        _remaining * _bv_p / _pct_total)
                                        # 反推每買方賣方贖回單位 _u_chunk
                                        # 用 list 保序，最後一檔吃殘量保證守恆
                                        _bpk_list = list(_bes_c.keys())
                                        _last_bpk = _bpk_list[-1]
                                        _used_units = 0.0
                                        _u_chunk_map: dict = {}
                                        for _bpk_o in _bpk_list:
                                            if _bpk_o == _last_bpk:
                                                _u_chunk_map[_bpk_o] = (
                                                    _u_redeem_s - _used_units)
                                            else:
                                                _amt_o = float(
                                                    _target_amt.get(_bpk_o, 0.0) or 0.0)
                                                _u_chunk_o = (_amt_o
                                                    / (_S["nav"] * _S["fx"])
                                                    if (_S["nav"] > 0 and _S["fx"] > 0)
                                                    else 0.0)
                                                _u_chunk_map[_bpk_o] = _u_chunk_o
                                                _used_units += _u_chunk_o
                                        # 構建（_bpk, _w_or_units）迭代列表給下面 switch
                                        _wn = {bpk: (_bes_c[bpk][1])
                                               for bpk in _bpk_list}
                                        for _bpk, _w in _wn.items():
                                            _u_chunk = _u_chunk_map[_bpk]
                                            _Bf = _fund_by_pk.get(_bpk)
                                            _nb, _xb = _navfx_cache_c.get(
                                                _bpk, _latest_nav_fx_t7(_Bf)
                                            )
                                            if _nb <= 0:
                                                raise ValueError(
                                                    f"買方 {_label_for_pk(_bpk)} NAV 抓不到"
                                                )
                                            _Bd = {
                                                "nav": _nb, "fx": _xb,
                                                "ccy": str(_Bf.get("currency", "USD")
                                                           ).upper(),
                                                "ledger": _ledger_for(_bpk),
                                            }
                                            if _S["ccy"] == _Bd["ccy"]:
                                                _sr = _SwT7.switch_same_currency(
                                                    ledger_from=_S["ledger"],
                                                    ledger_to=_Bd["ledger"],
                                                    units_to_redeem=_u_chunk,
                                                    nav_from_redeem=_S["nav"],
                                                    nav_to_buy=_Bd["nav"],
                                                    fee_orig=0.0,
                                                    txn_date=_d_t7.today(),
                                                )
                                                _mode_b = "同幣別"
                                            else:
                                                _fxA_t = (
                                                    _fx_now(f"{_S['ccy']}TWD")
                                                    or _S["fx"]
                                                )
                                                _fxB_t = (
                                                    _fx_now(f"{_Bd['ccy']}TWD")
                                                    or _Bd["fx"]
                                                )
                                                if _fxB_t <= 0:
                                                    raise ValueError(
                                                        f"{_bc} 對 TWD 匯率為 0"
                                                    )
                                                _cross_t = _fxA_t / _fxB_t
                                                _sr = _SwT7.switch_cross_currency(
                                                    ledger_from=_S["ledger"],
                                                    ledger_to=_Bd["ledger"],
                                                    units_to_redeem=_u_chunk,
                                                    nav_from_redeem=_S["nav"],
                                                    nav_to_buy=_Bd["nav"],
                                                    cross_rate=_cross_t,
                                                    fx_to_at_switch_twd=_fxB_t,
                                                    fee_orig=0.0,
                                                    txn_date=_d_t7.today(),
                                                )
                                                _mode_b = (
                                                    f"跨幣別 (cross={_cross_t:.4f})"
                                                )
                                            _twd_total_moved += (
                                                _sr.twd_cost_basis_transferred
                                            )
                                            _dy_b_loop = _dy_lookup_t7.get(_bpk, 0.0)
                                            _ann_b = (
                                                _sr.units_added_to * _Bd["nav"]
                                                * _Bd["fx"] * _dy_b_loop / 100.0
                                            )
                                            _ann_gain_total += _ann_b
                                            _spid, _scode_disp = parse_pk(_spk)
                                            _bpid, _bcode_disp = parse_pk(_bpk)
                                            # v18.27: dual-write 收集 (sell + buy 各一筆)
                                            _today_iso = _d_t7.today().isoformat()
                                            if _spid:
                                                _c_rows_by_pid.setdefault(_spid, []).append({
                                                    "date":          _today_iso,
                                                    "code":          _scode_disp,
                                                    "action":        "sell",
                                                    "units":         float(_sr.units_redeemed_from),
                                                    "nav_at_action": float(_S["nav"]),
                                                    "twd":           float(_sr.twd_cost_basis_transferred),
                                                    "fee":           0.0,
                                                    "note":          f"T7 C 轉換 → {_bcode_disp}",
                                                })
                                            if _bpid:
                                                _c_rows_by_pid.setdefault(_bpid, []).append({
                                                    "date":          _today_iso,
                                                    "code":          _bcode_disp,
                                                    "action":        "buy",
                                                    "units":         float(_sr.units_added_to),
                                                    "nav_at_action": float(_Bd["nav"]),
                                                    "twd":           float(_sr.twd_cost_basis_transferred),
                                                    "fee":           0.0,
                                                    "note":          f"T7 C 轉換 ← {_scode_disp}",
                                                })
                                            # v18.230：依模式顯示「賣端」「買端配置」
                                            if _cfg.get("sell_mode") == "units":
                                                _sell_disp = (
                                                    f"🎯 {_cfg.get('sell_units', 0.0):,.2f} U"
                                                )
                                            else:
                                                _sell_disp = f"{_cfg['sell_pct']:.1f}%"
                                            _bm_disp = _bes_c.get(_bpk, ("pct", 0.0))[0]
                                            if _bm_disp == "units":
                                                _buy_alloc_disp = f"🎯 {_w:,.2f} U"
                                            else:
                                                _buy_alloc_disp = f"📊 {_w:.2f}%"
                                            _result_rows.append({
                                                "賣方保單": _spid or "(未綁)",
                                                "賣方": _scode_disp,
                                                "賣端": _sell_disp,
                                                "買方保單": _bpid or "(未綁)",
                                                "買方": _bcode_disp,
                                                "買方名稱": (
                                                    _name_lookup_t7.get(_bpk, _bcode_disp)[:18]
                                                ),
                                                "買端配置": _buy_alloc_disp,
                                                "賣出單位": (
                                                    f"{_sr.units_redeemed_from:,.4f}"
                                                ),
                                                "買進單位": (
                                                    f"{_sr.units_added_to:,.4f}"
                                                ),
                                                "TWD 成本搬移": (
                                                    f"NT${_sr.twd_cost_basis_transferred:,.0f}"
                                                ),
                                                "B 新 NAV 成本": (
                                                    f"{_sr.cost_unit_to_basis:.4f}"
                                                ),
                                                "B 新 FX": (
                                                    f"{_sr.fx_avg_inherited:.4f}"
                                                ),
                                                "模式": _mode_b,
                                                "預估年配息": f"NT${_ann_b:,.0f}",
                                            })
                                    # 顯示結果
                                    st.success(
                                        f"✅ 複合轉換：{len(_sell_pks)} 賣方 → "
                                        f"{len(_result_rows)} 筆 switch 完成"
                                    )
                                    _df_c = pd.DataFrame(_result_rows)
                                    st.dataframe(
                                        _df_c, use_container_width=True,
                                        hide_index=True,
                                    )
                                    # 全域 hero
                                    _ann_diff = _ann_gain_total - _ann_lost_total
                                    hh1, hh2, hh3 = st.columns(3)
                                    hh1.metric(
                                        "📉 失去年配息（賣方組合計）",
                                        f"NT${_ann_lost_total:,.0f}/年",
                                    )
                                    hh2.metric(
                                        "📈 取得年配息（買方組合計）",
                                        f"NT${_ann_gain_total:,.0f}/年",
                                    )
                                    hh3.metric(
                                        "🔁 換倉後月配息變化",
                                        f"NT${_ann_diff/12:+,.0f}/月",
                                        delta=f"NT${_ann_diff:+,.0f}/年",
                                        help="正值 = 換倉後現金流增加；負值 = 為了成長換取配息",
                                    )
                                    tt1, tt2 = st.columns(2)
                                    tt1.metric(
                                        "TWD 成本基礎總搬移",
                                        f"NT${_twd_total_moved:,.0f}",
                                        help="Σ 各對 (sell_i, buy_j) 的 TWD 成本搬移",
                                    )
                                    _delta = _twd_total_moved - _expected_total
                                    tt2.metric(
                                        "守恆檢查（賣方組 baseline）",
                                        f"NT${_expected_total:,.0f}",
                                        delta=f"差 NT${_delta:+,.0f}",
                                        help=(
                                            "Σ 各賣方 (units_redeemed × cost_unit × fx_avg)；"
                                            "與『TWD 總搬移』差距應 < N NTD（浮點累積）"
                                        ),
                                    )
                                    if _is_scenario_c:
                                        _t7_save_scenario(
                                            name=_c_scenario_name or
                                                 f"C 複合轉換 {len(_sell_pks)}→{len(_result_rows)}",
                                            action_type="C",
                                            details=(
                                                f"{len(_sell_pks)} 賣方 → "
                                                f"{len(_result_rows)} 筆 switch；"
                                                f"TWD 搬移 NT${_twd_total_moved:,.0f}"
                                            ),
                                            nav_fx_cache=_navfx_cache_c,
                                        )
                                        _t7_restore_ledgers(_baseline_snap_c)
                                        st.info(
                                            f"💡 已暫存方案「"
                                            f"{_c_scenario_name or 'C 複合轉換'}"
                                            "」，主帳本未變動。"
                                        )
                                    else:
                                        _sync_invest_twd_from_ledgers()
                                        _msg_c = _sync_actions_to_sheet(_c_rows_by_pid)
                                        _msg_c_state = _t7_save_snapshot_to_sheets()
                                        st.caption(
                                            "💡 已套用主帳本：完成 "
                                            f"{len(_result_rows)} 筆複合 switch。{_msg_c}{_msg_c_state}"
                                        )
                                except Exception as _e_sw:
                                    if _is_scenario_c and _baseline_snap_c is not None:
                                        _t7_restore_ledgers(_baseline_snap_c)
                                    st.error(f"❌ 複合轉換失敗：{_e_sw}")

            # ── 帳本即時面板（最後渲染，永遠拿到最新 session_state） ────────
            with _panel_ph.container():
                # ── 方案比較區（v18.4 新增，僅在有 scenarios 時顯示）─────────
                if st.session_state.t7_scenarios:
                    with st.expander(
                        f"📊 方案比較（{len(st.session_state.t7_scenarios)} / "
                        f"{_T7_SCENARIO_LIMIT}）",
                        expanded=True,
                    ):
                        _live_navfx_cache = _t7_build_navfx_cache()
                        _live_summary = _t7_summary_from_ledgers(
                            st.session_state.t7_ledgers,
                            nav_fx_cache=_live_navfx_cache,
                        )
                        _cmp_rows = [{
                            "方案": "🟢 主帳本 (Live)",
                            "類型": "—",
                            "建立時間": "—",
                            "總市值 TWD": f"NT${_live_summary['total_value_twd']:,.0f}",
                            "成本 TWD": f"NT${_live_summary['total_cost_twd']:,.0f}",
                            "未實現損益 TWD": f"NT${_live_summary['unrealized_pl_twd']:+,.0f}",
                            "報酬 %": f"{_live_summary['unrealized_pl_pct']:+.2f}%",
                            "月配息 TWD": f"NT${_live_summary['monthly_cashflow_twd']:,.0f}",
                            "說明": "目前實際帳本",
                        }]
                        for _sc in st.session_state.t7_scenarios:
                            _s = _sc["summary"]
                            _diff_pl = (_s["unrealized_pl_twd"]
                                        - _live_summary["unrealized_pl_twd"])
                            _diff_cf = (_s["monthly_cashflow_twd"]
                                        - _live_summary["monthly_cashflow_twd"])
                            _cmp_rows.append({
                                "方案": f"💡 {_sc['name'][:24]}",
                                "類型": _sc["action_type"],
                                "建立時間": _sc["created_at"],
                                "總市值 TWD": f"NT${_s['total_value_twd']:,.0f}",
                                "成本 TWD": f"NT${_s['total_cost_twd']:,.0f}",
                                "未實現損益 TWD": (
                                    f"NT${_s['unrealized_pl_twd']:+,.0f}"
                                ),
                                "報酬 %": f"{_s['unrealized_pl_pct']:+.2f}%",
                                "月配息 TWD": (
                                    f"NT${_s['monthly_cashflow_twd']:,.0f} "
                                    f"({_diff_cf:+,.0f})"
                                ),
                                "說明": _sc["details"][:60],
                            })
                        st.dataframe(
                            pd.DataFrame(_cmp_rows),
                            use_container_width=True, hide_index=True,
                        )
                        st.caption(
                            "💡 月配息欄括號 = 與主帳本差距；未實現損益反映各方案買進後預估價位（NAV 不變假設）。"
                        )
                        # 每個 scenario 對應 commit/delete 按鈕
                        for _idx, _sc in enumerate(st.session_state.t7_scenarios):
                            _bcol1, _bcol2, _bcol3 = st.columns([4, 1, 1])
                            _bcol1.markdown(
                                f"**{_sc['name']}** "
                                f"<span style='color:#888;font-size:11px'>"
                                f"({_sc['action_type']} @ {_sc['created_at']})"
                                f"</span>",
                                unsafe_allow_html=True,
                            )
                            if _bcol2.button(
                                "📌 鎖定為主帳本",
                                key=f"t7_commit_sc_{_sc['id']}",
                                help="把此方案套用為主帳本（其他方案保留）"
                            ):
                                _t7_restore_ledgers(_sc["snapshot"])
                                _sync_invest_twd_from_ledgers()
                                st.success(
                                    f"✅ 已鎖定「{_sc['name']}」為主帳本。"
                                )
                                st.rerun()
                            if _bcol3.button(
                                "🗑️", key=f"t7_del_sc_{_sc['id']}",
                                help="刪除此方案"
                            ):
                                st.session_state.t7_scenarios = [
                                    s for s in st.session_state.t7_scenarios
                                    if s["id"] != _sc["id"]
                                ]
                                st.rerun()
                        if st.button("🗑️ 清空全部方案", key="t7_clear_all_scenarios"):
                            st.session_state.t7_scenarios = []
                            st.rerun()

                with st.expander("📒 目前帳本 + 以息養股現金流（in-memory，隨頁面重整清空）",
                                 expanded=True):
                    _snap_rows = []
                    _v_total_twd = 0.0
                    _ann_total_twd = 0.0
                    # v18.172：依各檔 div_cash_pct 拆「現金 / 配股(再投入)」兩個累計
                    _cash_total_twd = 0.0
                    _reinvest_total_twd = 0.0
                    _cost_total_twd = 0.0
                    # v18.31: 追蹤未計入的基金，給 KPI 卡顯示差額來源
                    _uncounted_funds: list[str] = []
                    for _f in _pf_t7:
                        _pk_f = fund_pk_str(_f)
                        _c = _f.get("code", "?")
                        _pid_disp = _f.get("policy_id") or "(未綁)"
                        _name_short = (_name_lookup_t7.get(_pk_f, _c))[:28]
                        _l = st.session_state.t7_ledgers.get(_pk_f)
                        _nav, _fx = _latest_nav_fx_t7(_f)
                        _dy = _dy_lookup_t7.get(_pk_f, 0.0)
                        if _l is None or _l.position.units <= 0:
                            _uncounted_funds.append(f"{_c}({_pid_disp})")
                            _snap_rows.append({
                                "保單": _pid_disp,
                                "代碼": _c, "基金名稱": _name_short,
                                "幣別": _f.get("currency", "USD"),
                                "持有單位": "—",
                                "平均買入淨值 NAV": "—", "含息成本": "—",
                                "平均買入匯率": "—",
                                "最新 NAV": f"{_nav:.4f}" if _nav else "—",
                                "最新 FX": f"{_fx:.4f}" if _fx else "—",
                                "成本基礎 (TWD)": "—",
                                "市值 (TWD)": "—",
                                "未實現損益 (TWD)": "—",
                                "未實現損益 %": "—",
                                "累積已配息率": "—",
                                "配息率": f"{_dy:.2f}%" if _dy else "—",
                                "預估月配息 (TWD)": "—",
                                # v18.172：與 normal branch 對齊欄位
                                "預估月配股 (TWD)": "—",
                            })
                            continue
                        _v = _l.position.value_twd(_nav, _fx) if (_nav and _fx) else 0
                        _cost = _l.position.net_investment_twd
                        _pl_twd = _v - _cost
                        _pl_pct = (_pl_twd / _cost * 100.0) if _cost > 0 else 0.0
                        _v_total_twd += _v
                        _cost_total_twd += _cost
                        _ann = _v * _dy / 100.0
                        _ann_total_twd += _ann
                        # v18.172：依該檔 div_cash_pct 拆現金 / 配股，預設 100=全現金
                        _dcp_f = max(0.0, min(100.0, float(_f.get("div_cash_pct", 100) or 100)))
                        _ann_cash = _ann * _dcp_f / 100.0
                        _ann_reinv = _ann - _ann_cash
                        _cash_total_twd += _ann_cash
                        _reinvest_total_twd += _ann_reinv
                        _pl_str = f"NT${_pl_twd:+,.0f}"
                        _pl_pct_str = f"{_pl_pct:+.2f}%"
                        # v18.184：累積已配息率 = (平均買入淨值 − 含息成本)/平均買入淨值，
                        # 代表成本已透過配息回收幾%（含息成本 < 淨值成本時才有意義）。
                        _cu0 = _l.position.cost_unit
                        _cuwd = _l.position.cost_unit_with_div
                        _div_rec_pct = (((_cu0 - _cuwd) / _cu0 * 100.0)
                                        if (_cu0 > 0 and 0 < _cuwd < _cu0) else None)
                        _snap_rows.append({
                            "保單": _pid_disp,
                            "代碼": _c, "基金名稱": _name_short,
                            "幣別": _l.currency,
                            "持有單位": f"{_l.position.units:,.4f}",
                            "平均買入淨值 NAV": f"{_l.position.cost_unit:.4f}",
                            "含息成本": (f"{_cuwd:.4f}"
                                       if (_cuwd and _cuwd < _cu0) else "—"),
                            "平均買入匯率": f"{_l.position.fx_avg:.4f}",
                            "最新 NAV": f"{_nav:.4f}" if _nav else "—",
                            "最新 FX": f"{_fx:.4f}" if _fx else "—",
                            "成本基礎 (TWD)": f"NT${_cost:,.0f}",
                            "市值 (TWD)": f"NT${_v:,.0f}",
                            "未實現損益 (TWD)": _pl_str,
                            "未實現損益 %": _pl_pct_str,
                            "累積已配息率": (f"{_div_rec_pct:.2f}%"
                                          if _div_rec_pct is not None else "—"),
                            "配息率": f"{_dy:.2f}%",
                            # v18.172：拆「月現金 / 月配股」兩欄；舊「預估月配息」改用現金部分
                            # v18.173：配股欄位再加「可換單位數」= TWD ÷ FX ÷ NAV
                            "預估月配息 (TWD)": f"NT${_ann_cash/12:,.0f}",
                            "預估月配股 (TWD)": (
                                f"NT${_ann_reinv/12:,.0f} ({(_ann_reinv/12)/(_fx*_nav):,.4f} 單位)"
                                if (_ann_reinv > 0 and _nav and _fx) else
                                f"NT${_ann_reinv/12:,.0f}"
                            ),
                        })
                    if _snap_rows:
                        # 紅虧綠賺：用 pandas Styler 著色（純 CSS 不依賴 matplotlib）
                        _df_snap = pd.DataFrame(_snap_rows)
                        def _color_pl(val):
                            if not isinstance(val, str) or val == "—":
                                return ""
                            try:
                                # 抽出第一個正/負號旁的數字
                                v = val.replace("NT$", "").replace(",", "").replace("%", "")
                                f = float(v)
                                if f > 0:  return "color:#00c853;font-weight:600"
                                if f < 0:  return "color:#f44336;font-weight:600"
                            except Exception:
                                return ""
                            return ""
                        try:
                            _styled = _df_snap.style.map(
                                _color_pl,
                                subset=["未實現損益 (TWD)", "未實現損益 %",
                                        "累積已配息率"]
                            )
                            st.dataframe(_styled, use_container_width=True,
                                         hide_index=True)
                        except Exception:
                            st.dataframe(_df_snap, use_container_width=True,
                                         hide_index=True)
                    # v18.70: 市值 = 0 時用 invest_twd 顯示估算值，避免「上下不同步」視覺斷層
                    _pl_total = _v_total_twd - _cost_total_twd
                    _pl_total_pct = (_pl_total / _cost_total_twd * 100.0
                                      if _cost_total_twd > 0 else 0.0)
                    # 計算 invest_twd 總和（fallback 用）
                    _invest_total_twd = sum(
                        float(_f.get("invest_twd", 0) or 0)
                        for _f in _pf_t7
                    )
                    # v18.172：5→6 cols；新增「年配股 (TWD)」KPI，預估年配息改現金部分
                    _pc1, _pc2, _pc3, _pc4, _pc5, _pc6 = st.columns([2, 2, 2, 2, 2, 1])
                    if _v_total_twd > 0:
                        _pc1.metric("組合當前市值 (TWD)", f"NT${_v_total_twd:,.0f}")
                    elif _invest_total_twd > 0:
                        # 沒 ledger 但有 invest_twd → 顯示投資金額作為近似
                        _pc1.metric(
                            "組合當前市值 (TWD) ⚠️ 近似",
                            f"NT${_invest_total_twd:,.0f}",
                            help="目前帳本無持倉細節，以保單投資金額（invest_twd）作為近似。"
                                 "進「✏️ 編輯持倉」用「⚡ 自動估算」填入持倉，或手動輸入精確值。"
                        )
                    else:
                        _pc1.metric("組合當前市值 (TWD)", "NT$0",
                                    help="尚無持倉資料 — 請加入基金 + 設定單位/NAV/匯率")
                    _pc2.metric(
                        "💸 整體未實現損益 (TWD)",
                        f"NT${_pl_total:+,.0f}",
                        delta=f"{_pl_total_pct:+.2f}% 報酬率",
                        delta_color="normal",   # v18.26: 損益恆用 normal（虧損紅、賺綠）
                    )
                    # v18.172：年配息拆「現金」+「配股」兩格；每月現金流改 cash-only
                    _pc3.metric(
                        "💵 預估年現金配息 (TWD)",
                        f"NT${_cash_total_twd:,.0f}",
                        help=f"年總配息 NT${_ann_total_twd:,.0f} 中**現金給付**部分。\n"
                             f"= Σ 各檔 市值 × 配息率 × (div_cash_pct/100)。\n"
                             f"div_cash_pct=100 → 全現金；<100 → 部分轉新單位（配股）。"
                    )
                    _pc4.metric(
                        "📅 每月被動現金流",
                        f"NT${_cash_total_twd/12:,.0f}",
                        help="只算現金、不含再投入配股；= 預估年現金配息 / 12"
                    )
                    _pc5.metric(
                        "🪙 預估年配股 (TWD)",
                        f"NT${_reinvest_total_twd:,.0f}",
                        help=f"年總配息 NT${_ann_total_twd:,.0f} 中**再投入轉新單位**部分。\n"
                             "= Σ 各檔 市值 × 配息率 × ((100-div_cash_pct)/100)。\n"
                             "此金額不會進現金流、會以新單位累加進部位（提升未來市值）。"
                    )
                    if _pc6.button("🗑️ 重置帳本", key="t7_reset"):
                        st.session_state.t7_ledgers = {}
                        st.rerun()
                    # v18.31: KPI vs 表格差額來源說明
                    _counted = len(_pf_t7) - len(_uncounted_funds)
                    if _uncounted_funds:
                        st.caption(
                            f"ℹ️ KPI 已計入 **{_counted} / {len(_pf_t7)} 檔**；"
                            f"未計入 {len(_uncounted_funds)} 檔（"
                            f"{', '.join(_uncounted_funds[:5])}"
                            f"{'…' if len(_uncounted_funds) > 5 else ''}）"
                            f"— 請在「📝 編輯初始持倉」填入持有單位/NAV/匯率"
                        )
                    else:
                        st.caption(
                            f"✅ KPI 已計入全部 **{len(_pf_t7)} 檔**基金；"
                            "若上方表格列數與 KPI 不符，請檢查 ledger 狀態（「📝 編輯初始持倉」）"
                        )


            # ── v18.82 MK 老師深度組合建議（AI）—— 放 _panel_ph 之外才會在 A/B/C 下方 ──
            # 使用者反饋「組合基金下方缺乏 AI 組合分析」：v18.81 expander 寫在
            # _panel_ph.container() 裡，那個 placeholder 在 A/B/C tabs 上方創建，
            # 渲染進去 = 顯示在 tabs 上方，使用者在 C tab 往下看當然看不到。
            # 搬出 placeholder 後 expander 渲染在 if _T7_OK 區段最末，即 A/B/C 下方。
            st.divider()
            st.markdown(
                "<div style='background:linear-gradient(135deg,#2a1845,#1a0d2a);"
                "border-left:4px solid #b388ff;border-radius:8px;"
                "padding:10px 14px;margin:8px 0'>"
                "<span style='color:#b388ff;font-size:15px;font-weight:900'>"
                "📜 策略3 深度組合建議</span>"
                "<span style='color:#888;font-size:11px;margin-left:8px'>"
                "AI 4 節結構：3 大缺點 / 換股建議 / 配置比例 / 高賣低買 vs 跌就買</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            if not GEMINI_KEY:
                st.info("ℹ️ 需設置 Gemini API key 才能使用此功能")
            elif not _pf_t7:
                st.info("ℹ️ 請先載入基金（上方「📡 載入所有未載入基金」）")
            else:
                _mk_ai_phase = (st.session_state.get("phase_info_global")
                                or st.session_state.get("phase_info") or {})
                _mk_ai_ind = st.session_state.get("indicators") or {}
                _mk_data_ok, _ = _calc_data_health(_mk_ai_ind)
                if _mk_data_ok < 50:
                    st.warning(
                        f"🔴 總經完整率 **{_mk_data_ok}%**（&lt;50%）— "
                        "建議先到「🌐 總經」按「📡 全量抓取」載入指標後再生成，"
                        "AI 才能給景氣位階對應的換股建議。仍可勾選下方略過按鈕直接生成基礎組合分析。"
                    )
                # v18.87: 資料來源透明化 — 明確說 AI 只看主帳本（不含 A/B/C 暫存方案）
                # 使用者反饋「MK 老師的判斷不能抓取重新配置的資料，因為這資料只是給我
                # 想要重新配置的參考值」— 程式碼確實已隔離，但 UI 沒講清楚使用者會擔心
                _mk_n_funds = sum(1 for f in _pf_t7 if f.get("loaded"))
                _mk_total_inv = sum(int(f.get("invest_twd", 0) or 0)
                                     for f in _pf_t7 if f.get("loaded"))
                _mk_n_scenarios = len(st.session_state.get("t7_scenarios", []) or [])
                st.markdown(
                    "<div style='background:#0d1117;border:1px solid #30363d;"
                    "border-radius:6px;padding:8px 12px;margin:6px 0;font-size:12px'>"
                    "<span style='color:#69f0ae;font-weight:700'>🔍 分析範圍：</span>"
                    f"<span style='color:#c9d1d9'>主帳本 <b>{_mk_n_funds} 檔</b>"
                    f"，合計投入 <b>NT${_mk_total_inv:,}</b></span>"
                    + (f"<span style='color:#ff9800;margin-left:12px'>"
                       f"（A/B/C 暫存方案 {_mk_n_scenarios} 個 — <b>不</b>納入分析）"
                       "</span>" if _mk_n_scenarios > 0 else "")
                    + "</div>",
                    unsafe_allow_html=True,
                )
                _mk_cols = st.columns([2, 1, 1])
                _mk_btn = _mk_cols[0].button(
                    "🤖 生成 策略3 深度建議",
                    key="btn_mk_advisor",
                    type="primary",
                    use_container_width=True,
                    help="只分析主帳本（已落帳的實際持倉），A/B/C 暫存方案不會被納入",
                )
                if _mk_cols[1].button("🗑️ 清除上次結果",
                                       key="btn_mk_advisor_clear",
                                       use_container_width=True):
                    st.session_state.pop("mk_advisor_txt", None)
                    st.rerun()
                if _mk_btn:
                    # v18.87: 防禦性 — 呼叫 AI 前 deep-copy 主帳本 + portfolio_funds，
                    # 確保 spinner 期間其他 callback 或 rerun side-effect 都不影響 AI 看到的資料
                    import copy as _cp_mk
                    _mk_pf_snapshot = _cp_mk.deepcopy(_pf_t7)
                    _mk_ledger_snapshot = _t7_snapshot_ledgers()
                    # v18.85/86: 抓 RSS 新聞給 AI 判斷系統性風險
                    _mk_news: list = []
                    with st.spinner("📰 抓取近期國際財經新聞 + 系統性風險事件 (RSS)..."):
                        try:
                            _mk_news = fetch_market_news(max_per_feed=4) or []
                        except Exception as _e_news:
                            st.caption(f"⚠️ 新聞抓取失敗（{str(_e_news)[:60]}），"
                                       f"AI 將在無新聞背景下分析")
                    if _mk_news:
                        _n_sys = sum(1 for h in _mk_news if h.get("is_systemic"))
                        if _n_sys > 0:
                            st.warning(
                                f"🚨 偵測到 **{_n_sys} 條系統性風險新聞**"
                                f"（戰爭 / 銀行倒閉 / 黑天鵝事件）— 已餵給 AI 優先判讀"
                            )
                        st.caption(
                            f"✅ 已抓 {len(_mk_news)} 條近期新聞"
                            + (f"（含 {_n_sys} 條 🚨 系統性風險）" if _n_sys > 0 else "")
                            + " — 將餵給 AI 判斷系統性風險"
                        )
                    # 重建 ledgers dict 給 AI（避免 AI 內部任何 mutate 污染主帳本）
                    _mk_ledger_for_ai = {
                        pk: _LedT7.from_dict(d) for pk, d in _mk_ledger_snapshot.items()
                    }
                    # v18.110: 預先計算 Phase 4 driver 排名 + Phase 3-B 燈號回測
                    # → 讓 AI prompt 有量化證據可以引用，建議不再空談
                    _mk_drv: dict | None = None
                    _mk_sub: list | None = None
                    if _mk_ai_ind:
                        try:
                            _mk_drv = rank_macro_drivers(
                                _mk_ai_ind, target_key="LEI", lag_months=3, min_overlap=24,
                            )
                        except Exception as _e_drv:
                            print(f"[MK AI] rank_macro_drivers 失敗：{_e_drv}")
                        try:
                            _mk_sub = backtest_sub_cycle_lights(
                                _mk_ai_ind, target_key="LEI", window=60, forward_months=3,
                            )
                        except Exception as _e_sub:
                            print(f"[MK AI] backtest_sub_cycle_lights 失敗：{_e_sub}")
                    with st.spinner("🤖 Gemini 分析組合中...（約 15-30 秒）"):
                        try:
                            _mk_txt = analyze_portfolio_mk_advisor(
                                GEMINI_KEY,
                                _mk_pf_snapshot,    # v18.87 deep-copy snapshot
                                _mk_ai_phase,
                                ledgers=_mk_ledger_for_ai,   # v18.87 重建副本
                                indicators=_mk_ai_ind,
                                news_headlines=_mk_news,   # v18.85
                                driver_ranking=_mk_drv,    # v18.110 Phase 4
                                subcycle_lights=_mk_sub,   # v18.110 Phase 3-B
                            )
                            # v18.88: _gemini 失敗時回傳 "❌ ..." 或 "⚠️ ..." 字串而非 raise
                            #         之前直接存進 session 結果區會顯示成功訊息但內容是錯誤
                            if isinstance(_mk_txt, str) and _mk_txt.startswith(("❌", "⚠️")):
                                st.error(
                                    f"❌ 策略3 AI 回傳錯誤訊息：\n\n{_mk_txt[:400]}\n\n"
                                    "**可能原因**：\n"
                                    "- Gemini API 配額用完（HTTP 429）→ 等 1-2 分鐘\n"
                                    "- Prompt 太大被拒（HTTP 400/413）→ v18.88 已大幅瘦身\n"
                                    "- 網路超時 → 重按按鈕"
                                )
                            else:
                                st.session_state["mk_advisor_txt"] = _mk_txt
                                st.session_state["mk_advisor_news_n"] = len(_mk_news)
                                st.session_state["mk_advisor_news_sys_n"] = sum(
                                    1 for h in _mk_news if h.get("is_systemic"))
                        except Exception as _e_mk:
                            # v18.88: 直接顯示真實錯誤 + 異常類型，不藏在 friendly_error 裡
                            st.error(
                                f"❌ 策略3 AI 生成失敗：**[{type(_e_mk).__name__}]** "
                                f"{str(_e_mk)[:300]}\n\n"
                                "**常見原因**：\n"
                                "- HTTP 429 配額 → 等 1-2 分鐘\n"
                                "- HTTP 400 prompt 超限 → v18.88 已瘦身（19→7 unique codes + news 30→8 條）\n"
                                "- 網路逾時 → 重試"
                            )
                if st.session_state.get("mk_advisor_txt"):
                    st.markdown("---")
                    _n_news_used = st.session_state.get("mk_advisor_news_n", 0)
                    _n_sys_used = st.session_state.get("mk_advisor_news_sys_n", 0)
                    if _n_news_used > 0:
                        st.caption(
                            f"📰 本次分析已納入 **{_n_news_used} 條近期新聞** "
                            + (f"（含 **{_n_sys_used} 條 🚨 系統性風險**：戰爭/銀行倒閉/黑天鵝） "
                                if _n_sys_used > 0 else "")
                            + "判斷系統性風險"
                        )
                    st.markdown(st.session_state["mk_advisor_txt"])
                    st.caption("⚠️ AI 建議僅供參考，最終決策需自行判斷市場與風險承受度")
