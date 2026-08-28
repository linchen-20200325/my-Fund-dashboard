"""ui/helpers/fund_grp_health/switch_advisor_section.py — 🎯 換股池顧問區塊(v19.428)。

L3 orchestrator:選股池 CRUD(L1 `pool_repository`,EX-CRUD-1)+ 讀已載入持倉 → 逐檔換股建議
(L2 `switch_advisor`)。震盪型高基期→池中低基期健康配對;成長型總經看衰+跌破雙確認賣出。

取數走既有 L2/L3:持倉列用 `fund_grp_health.rotation._assemble_rows`;池中未載入標的用
`services.fund_row.process_one_fund` 補抓(L2);總經 composite 讀 session;匯率位階走
`fx_regime.fx_regime_by_ccy`。**教學非保證**:缺條件誠實回持有/資料不足(§1),不硬給動作。
"""
from __future__ import annotations

import streamlit as st

from ui.helpers.render_state import system_error

_TYPE_OPTS = ["自動(ER 判定)", "震盪", "成長"]
_PRINCIPAL = 1_000_000.0     # 補抓池中標的用的名目本金(僅為走健診管線,不影響型態/基期)


# ───────────────────────── 取數 helper ─────────────────────────

def _macro_composite() -> "float | None":
    """讀 session 的 macro composite 總分(§1:取不到 → None,成長型分支誠實不觸發)。"""
    v = st.session_state.get("composite_score")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        for k in ("score", "total", "composite", "value"):
            if isinstance(v.get(k), (int, float)):
                return float(v[k])
    return None


def _fx_label() -> "str | None":
    try:
        from services.fx_regime_service import fx_regime_by_ccy
        return (fx_regime_by_ccy().get("USD") or {}).get("regime")
    except Exception:  # noqa: BLE001
        return None


def _rows_with_nav(funds: list, pool_by_code: dict) -> list:
    """持倉 rich dict → switch_advisor 需要的列(rotation 欄位 + nav_series + type_override)。"""
    from ui.helpers.fund_grp_health.rotation import _assemble_rows
    rows = _assemble_rows(funds)
    _nav = {f.get("code"): f.get("series") for f in funds}
    for r in rows:
        _c = r.get("code")
        r["nav_series"] = _nav.get(_c)
        # v19.432 稽核修:pool_by_code 的值是 PoolEntry dataclass(**沒有 .get()**)。
        # 原 `(pool_by_code.get(_c) or {}).get(...)` 在「持倉檔同時也在選股池」時會拋
        # AttributeError → 被外層 except 吞掉 → 整張換股建議表靜默消失。改 getattr。
        _pe = pool_by_code.get(_c)
        r["type_override"] = (getattr(_pe, "type_override", "") if _pe else "") or ""
        if not r.get("基金類別"):
            r["基金類別"] = getattr(_pe, "category", None) if _pe else None
    return rows


def _fetch_rich(code: str, name: str = "") -> "dict | None":
    """池中未載入標的 → 走健診管線補抓成 rich dict(L2 process_one_fund + L3 _build_fund_dict)。

    name:選股池自填名 → 當作 name_hint 傳下去,線上抓不到真名(如 ALZF9)時顯示池名,
    而非代號(v19.497)。
    """
    try:
        from services.fund_row import process_one_fund
        from ui.helpers.fund_grp_health_extras import _build_fund_dict
        # v19.509:SA 缺時用登入者 OAuth 讀雲端 nav_history(與健診同一本 → 補抓也看得到累積)。
        r = process_one_fund(code, _PRINCIPAL, name_hint=name, oauth_client=_pool_oauth_client())
        if r.get("ok") and r.get("_fund_raw"):
            return _build_fund_dict(r["_fund_raw"], code, _PRINCIPAL, name_hint=name)
    except Exception as _e:  # noqa: BLE001
        # 「略過」= 這一檔會從換股建議裡靜靜消失 —— 使用者看不出少了它,
        # 正是線框 §03 點名的「示警不足」,故走系統紅燈。
        system_error(f"選股池標的 {code} 補抓失敗,已從候選中排除", _e,
                     hint="下方換股建議未涵蓋這一檔,不代表它不值得換。")
    return None


def _pool_rows(pool: list, funds: list) -> list:
    """選股池 → 候選列。已載入的重用;未載入的補抓。附 nav_series + type_override + 類別。"""
    from ui.helpers.fund_grp_health.rotation import _assemble_rows
    _loaded = {f.get("code"): f for f in funds}
    out = []
    for e in pool:
        _rich = _loaded.get(e.code) or _fetch_rich(e.code, e.name)
        if _rich is None:
            continue
        _row = _assemble_rows([_rich])[0]
        # v19.497:選股池自填名優先於「抓不到真名 → 代號」(ALZF9 類)。已載入路徑的
        # _rich 來自 portfolio_funds(name 可能是代號),故在列組好後統一覆蓋。
        if e.name and str(_row.get("name") or "").strip().upper() in ("", str(e.code).upper()):
            _row["name"] = e.name
        _row["nav_series"] = _rich.get("series")
        _row["type_override"] = e.type_override
        if not _row.get("基金類別"):
            _row["基金類別"] = e.category
        out.append(_row)
    return out


# ───────────────────────── 表現差(跑輸大盤 OR 絕對虧損)取數 ─────────────────────────

def _benchmark_label_for(f: dict) -> "str | None":
    """依幣別選對應大盤(TWD→TWII / USD→SPX / 其餘→None,§4.1 不錯配)。"""
    try:
        from services.capture_ratio import benchmark_for_currency
        from services.currency import normalize_ccy
        return benchmark_for_currency(normalize_ccy(f.get("currency"), default=""))
    except Exception:  # noqa: BLE001
        return None


def _redlight_by_code(funds: list, excess_by_code: dict, eat_by_code: "dict | None" = None) -> dict:
    """逐檔絕對虧損紅燈(重用 switch_strategy SSOT:含息1Y × Sharpe × 最大跌幅 × vs大盤)。

    § 與大表同源:走 `switch_score` + `switch_signal`(RED = 含息1Y<0 且 Sharpe<0,或嚴重吃本金)。
    v19.441:接吃本金燈號(`eat_by_code`)→ 與 NAS 週報同一套 —— switch_signal 只認「嚴重」紅,
    正報酬但配息侵蝕本金(plain 🔴 吃本金)靠 `eat_is_red` 補上,避免 App 預覽與實送分歧(稽核 MEDIUM)。
    缺 eat_by_code(舊 caller)→ eat="" 保守子集;缺料 → None(§1 不臆測)。
    """
    import sys
    _eat_map = eat_by_code or {}
    out: dict = {}
    for f in funds:
        _code = f.get("code")
        try:
            from services.fund_total_return import compute_1y_total_return
            from services.switch_advisor import eat_is_red
            from services.switch_strategy import RED, switch_score, switch_signal
            _tr, _ = compute_1y_total_return(f)
            _m = f.get("metrics") or {}
            _rm = f.get("risk_metrics") or {}
            _sh = _m.get("sharpe")
            _dd = _rm.get("max_drawdown")
            if _dd is None:
                _dd = _m.get("max_drawdown")
            _vm = excess_by_code.get(_code)
            _eat = _eat_map.get(_code, "")
            _cov: dict = {}
            _sc = switch_score(_tr, _sh, _dd, _vm, coverage_out=_cov)
            out[_code] = (switch_signal(_tr, _sh, _eat, _sc, coverage=_cov) == RED) or eat_is_red(_eat)
        except Exception as _e:  # noqa: BLE001 — 單檔失敗不拖垮整組;誠實 None
            print(f"[switch_advisor_section] {_code} 紅燈判定失敗:{type(_e).__name__}: {_e}",
                  file=sys.stderr)
            out[_code] = None
    return out


def _underperf_by_code(funds: list) -> dict:
    """{code → assess_underperformance(...)}。跑輸大盤走 capture_by_code 的「vs 大盤%」,
    絕對虧損走 `_redlight_by_code`。兩者任一 → 表現差(§C OR)。"""
    from services.health.dividend import check_eating_principal_1y_mk
    from services.switch_advisor import assess_underperformance
    from ui.helpers.fund_grp_health.capture import capture_by_code

    _cap = capture_by_code(funds)                       # {code: {vs 大盤%, vs 大盤期間, …}}
    _excess = {c: (_cap.get(c) or {}).get("vs 大盤%") for c in (_cap or {})}
    # v19.441:吃本金燈號算一次,同時餵紅燈判定與 reason 標籤(與 NAS 週報同一套)
    _eat_map: dict = {}
    for f in funds:
        try:
            _eat_map[f.get("code")] = (check_eating_principal_1y_mk(f) or {}).get("status", "")
        except Exception:  # noqa: BLE001 — 單檔吃本金判定失敗不拖垮整組
            _eat_map[f.get("code")] = ""
    _red = _redlight_by_code(funds, _excess, eat_by_code=_eat_map)
    out: dict = {}
    for f in funds:
        _code = f.get("code")
        _c = _cap.get(_code) or {}
        out[str(_code)] = assess_underperformance(      # str 鍵對齊 advise_switches 的 str(code) 查詢
            excess_pct=_c.get("vs 大盤%"),
            full_period=str(_c.get("vs 大盤期間", "")).startswith("⚠️ 全期"),
            benchmark_label=_benchmark_label_for(f),
            eat_status=_eat_map.get(_code, ""),
            redlight=_red.get(_code),
        )
    return out


# ───────────────────────── 組合績效追蹤(走勢 + 永久快照)─────────────────────────

def _ccy_fx_for(funds: list):
    """組 ccy_by_code + 抓 USDTWD 歷史(L2 facade,§8.2 不直呼 L1),供組合追蹤換 TWD basis。

    v19.449 稽核 HIGH:組合走勢/快照原本用原幣報酬加權、漏匯率損益;此處備妥 ccy+fx 供換算。
    匯率抓取失敗 → fx=None(美元基金會被 L2 誠實排除,不靜默造假,§1)。
    """
    _ccy = {f.get("code"): (f.get("currency", "") or "") for f in (funds or []) if f.get("code")}
    _fx = None
    try:
        from shared.signal_thresholds import BACKTEST_FX_FETCH_DAYS
        from services.hot_money_service import fetch_usdtwd_frame
        _df, _err = fetch_usdtwd_frame(BACKTEST_FX_FETCH_DAYS)
        if _df is not None and not _df.empty:
            _fx = _df.set_index("date")["usdtwd"]
    except Exception:  # noqa: BLE001 — 匯率抓取失敗 → 美元基金排除,不靜默造假
        _fx = None
    return _ccy, _fx


def _maybe_snapshot(nav_by_code: dict, weights: dict, is_equal: bool, funds: list) -> None:
    """本 session 首次進入 → 寫一筆組合績效快照(往前累積;repo 依 date 去重,每天最多一列)。"""
    if st.session_state.get("_perf_snapshot_done"):
        return
    try:
        from repositories.portfolio_perf_repository import PerfSnapshot, append_snapshot
        from services.portfolio_tracking import build_snapshot_row
        _cost = sum(float(f.get("invest_twd") or 0) for f in funds) or None
        _ccy, _fx = _ccy_fx_for(funds)
        _row = build_snapshot_row(nav_by_code, weights, total_cost_twd=_cost,
                                  is_equal_weight=is_equal, ccy_by_code=_ccy, fx_series=_fx)
        if _row is None:
            return                                       # 資料不足 → 不寫、不設旗標(下次資料夠再試)
        st.session_state["_perf_snapshot_done"] = True   # 已嘗試寫入即設(避免 GS 錯誤時每次 rerun 重打)
        append_snapshot(PerfSnapshot(**_row))
    except Exception as _e:  # noqa: BLE001 — 快照失敗不影響走勢顯示;誠實提示
        system_error("組合績效快照未寫入", _e,
                     hint="本區顯示的走勢數字不受影響;但這一筆歷史沒有累積上去,"
                          "若持續失敗,「幾週後看變化」這件事會靜靜地不成立。")


def render_portfolio_tracking(funds: list) -> None:
    """📈 投資組合績效追蹤:用已累積 NAV × 目前權重重建走勢 + 永久快照(§req 1)。"""
    from ui.helpers.portfolio_perf import _nav_weights_from_funds
    from services.portfolio_tracking import reconstruct_trend

    _nav, _w, _equal = _nav_weights_from_funds(funds)
    if len(_nav) < 1:
        return

    st.markdown("#### 📈 投資組合績效追蹤(走勢 + 快照・TWD 計價)")
    _ccy, _fx = _ccy_fx_for(funds)
    _t = reconstruct_trend(_nav, _w, ccy_by_code=_ccy, fx_series=_fx)
    if not _t["ok"]:
        st.info(f"績效走勢資料不足 —— {_t['reason']}")
        return

    _m = _t["metrics"]

    def _pct(v):
        return f"{v:+.2f}%" if v is not None else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("期間累積報酬", _pct(_m.get("period_return_pct")))
    c2.metric("年化報酬", _pct(_m.get("cagr_pct")))
    c3.metric("年化波動 σ", f"{_m['ann_vol_pct']:.2f}%" if _m.get("ann_vol_pct") is not None else "—")
    c4.metric("最大回撤", _pct(_m.get("max_drawdown_pct")))

    _curve = _t["curve"]
    if _curve is not None and len(_curve) >= 2:
        import pandas as pd
        _base = float(_curve.iloc[0])
        if _base > 0:
            st.line_chart(pd.DataFrame({"組合累積(起點=100)": (_curve / _base) * 100.0}))

    _wsrc = "等權(無投入金額)" if _equal else "投入金額加權"
    _notes = []
    if _t["annualized_suppressed"]:
        _notes.append(f"⚠️ 共同交易日僅 {_t['n_days']} 天 < 門檻 → 只給累積報酬,**年化暫不計**(避免短序列失真,§4.6)")
    elif _t["low_confidence"]:
        _notes.append("⚠️ 不足 1 年 → 年化為**參考值**(low confidence)")
    st.caption(
        f"期間 {_t['coverage_start']} ~ {_t['coverage_end']}（{_t['n_days']} 交易日・"
        f"{_t['n_funds_used']} 檔・{_wsrc}）。**固定目前權重・日再平衡**假設;走勢長度 = 已累積 NAV 的長度。"
        + ("　·　" + "　·　".join(_notes) if _notes else "")
    )
    if _t["excluded"]:
        st.caption("⬜ 排除:" + "、".join(f"{e['code']}（{e['reason']}）" for e in _t["excluded"]))

    _maybe_snapshot(_nav, _w, _equal, funds)

    # 永久快照歷史(往前累積)
    try:
        from repositories.portfolio_perf_repository import load_snapshots
        _snaps = load_snapshots()
        if _snaps:
            _last = _snaps[-1]
            st.caption(f"🗂️ 已累積績效快照 {len(_snaps)} 筆(最新 {_last.date})。"
                       "每次開啟本區自動存一筆,幾週後可看組合績效隨時間的變化。")
            if len(_snaps) >= 2:
                import pandas as pd
                _sdf = pd.DataFrame({
                    "期間累積報酬%": [s.period_return_pct for s in _snaps],
                }, index=[s.date for s in _snaps]).dropna()
                if len(_sdf) >= 2:
                    st.line_chart(_sdf)
    except Exception as _e:  # noqa: BLE001
        system_error("組合績效快照歷史讀取失敗", _e,
                     hint="上方走勢圖以當下資料重建,不受影響;缺的是歷史累積筆數。")


# ───────────────────────── 選股池 CRUD UI ─────────────────────────

def _pool_oauth_client():
    """SA 缺時,取登入者的 OAuth gspread client 讓選股池讀寫走使用者身分(手機免設 SA)。

    v19.508:mirror task #43(Tab3 SA→OAuth 回退)。拿不到(未登入 / 建置失敗)→ None,
    `pool_repository` 收到 None 即退回純 SA / 本地行為(零 regression)。L3 在此取 client、
    注入 L1;L1 不碰 `st.session_state`,守 §8.2 硬規則。
    """
    try:
        from ui.helpers.io.oauth_state import _get_oauth_client
        return _get_oauth_client()
    except Exception:  # noqa: BLE001 — OAuth 未設 / 建置失敗 → None(退 SA / 本地)
        return None


def _render_pool_editor() -> None:
    from repositories.pool_repository import (
        PoolEntry,
        add_or_update,
        list_pool,
        remove_from_pool,
        set_type_override,
    )
    st.markdown("#### 📁 選股池(候選基金)")
    # v19.508:SA 缺(手機未設 Service Account)時,用登入者 OAuth 身分讀寫選股池 Sheet →
    # 跨 reboot 永久保存(不再只落會被清空的本地暫存)。SA 在 / 未登入 → None → 行為不變。
    _oauth = _pool_oauth_client()
    # §1 誠實揭露落到哪個後端 —— 防「OAuth 取不到 → 靜默存本地 → 顯示成功 → 重開消失」破口。
    from repositories.pool_repository import pool_backend_status
    _backend = pool_backend_status(_oauth)
    if _backend == "local":
        st.warning("⚠️ 未偵測到 Service Account,且 Google 未登入(或登入已過期)→ 選股池"
                   "**只會存本地暫存,App 重開就消失**。請先在上方登入 Google(或設定 "
                   "Service Account),再新增選股池,才能永久保存。")
    elif _backend == "oauth":
        st.caption("☁️ 目前以你的 Google 登入身分保存選股池到雲端(跨 App 重開不會消失)。")
    try:
        pool = list_pool(oauth_client=_oauth)
    except Exception as _e:  # noqa: BLE001
        system_error("選股池讀取失敗", _e,
                     hint="選股池顯示為空不代表它是空的,可能只是這次讀不到。")
        return

    if pool:
        import pandas as pd
        from streamlit import column_config as _cc

        def _navfill(e):
            if e.morningstar_secid:
                return "✅ 直接用 secId"
            if e.isin:
                return "🔎 用 ISIN 自動找"
            return "⬜ 缺 ISIN"
        # v19.473(user「只填代號+ISIN,其餘自動」):表格顯示自動抓到的 名稱/幣別 + 補淨值狀態。
        # 名稱/幣別在**能連外環境**首次補淨值時由晨星回傳自動回填(離線環境會先空著)。
        _df = pd.DataFrame([{"代號": e.code, "名稱(自動)": e.name or "—",
                             "ISIN": e.isin or "—", "幣別(自動)": e.currency or "—",
                             "補淨值": _navfill(e),
                             "手動型態": e.type_override or "自動", "狀態": e.status} for e in pool])
        st.dataframe(
            _df, use_container_width=True, hide_index=True,
            column_config={
                "代號": _cc.TextColumn("代號", width="small",
                    help="基金代號 —— 產生換股建議時,沒載入過的會自動補抓一次。"),
                "名稱(自動)": _cc.TextColumn("名稱(自動)", width="medium",
                    help="系統補淨值時由晨星自動抓回來填,不用手打。"),
                "ISIN": _cc.TextColumn("ISIN", width="small",
                    help="你唯一要填的補資料欄位。MoneyDJ 抓不到淨值時,系統用它去晨星串出淨值。"),
                "幣別(自動)": _cc.TextColumn("幣別(自動)", width="small",
                    help="系統從晨星基金名稱自動判定(如 USD/TWD),不用手填。"),
                "補淨值": _cc.TextColumn("補淨值", width="small",
                    help="這檔能不能靠晨星補淨值:✅ 已有 secId / 🔎 有 ISIN 可自動找 / ⬜ 缺 ISIN。"),
                "手動型態": _cc.TextColumn("手動型態", width="small",
                    help="預設「自動」由系統依波動判定;要手動指定用下方「套用型態」。"),
                "狀態": _cc.TextColumn("狀態", width="small",
                    help="換股狀態機:WATCHING 觀察 → TRIGGERED 訊號觸發 → HOLDING 持有 → CLOSED 出場。"),
            },
        )
    else:
        st.caption("選股池目前是空的 —— 用下方表單加入候選基金。")

    # v19.473(user 2026-08-18):表單**只留 基金代號 + ISIN**,其餘(名稱/類別/幣別/型態)全部
    # 由系統自動抓取 / 判定。ISIN 只有「MoneyDJ 抓不到淨值」的檔才需要填,其他留空即可。
    with st.form("pool_add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        _code = c1.text_input("基金代號", key="pool_code", placeholder="ALZF9")
        _isin = c2.text_input("ISIN(抓不到淨值的檔才要填)", key="pool_isin",
                              placeholder="LU0766462157")
        st.caption("💡 只要填**代號**;抓不到淨值的檔再填 **ISIN**。名稱、幣別、類別、型態都由系統自動抓/判。")
        if st.form_submit_button("➕ 加入 / 更新選股池", use_container_width=True):
            _c = (_code or "").strip()
            if not _c:
                st.warning("請輸入基金代號。")
            else:
                # code 已在池 → 只更新 ISIN,其餘(名稱/型態/狀態/幣別/secId/加入日)全保留(不清空)。
                _exist = next((e for e in pool if e.code == _c), None)
                if _exist is not None:
                    _entry = PoolEntry(
                        code=_c, name=_exist.name, category=_exist.category,
                        type_override=_exist.type_override, note=_exist.note,
                        added_at=_exist.added_at, status=_exist.status,
                        isin=_isin.strip() or _exist.isin,
                        currency=_exist.currency, morningstar_secid=_exist.morningstar_secid,
                    )
                else:
                    _entry = PoolEntry(code=_c, isin=_isin.strip())   # 其餘留空 → 系統自動補
                try:
                    add_or_update(_entry, oauth_client=_oauth)
                    st.success(f"已加入 / 更新:{_c}")
                    st.rerun()
                except Exception as _e:  # noqa: BLE001
                    st.error(f"寫入失敗:[{type(_e).__name__}] {str(_e)[:80]}")
                    if _backend == "oauth":
                        st.caption("💡 若是權限錯(403):請確認你登入的 Google 帳號,對選股池那本 "
                                   "Sheet 有『編輯』權限。")

    if pool:
        cc1, cc2 = st.columns(2)
        _codes = [e.code for e in pool]
        _sel = cc1.selectbox("改型態 / 移除", _codes, key="pool_sel")
        _newt = cc2.selectbox("設型態", _TYPE_OPTS, key="pool_newtype")
        b1, b2 = st.columns(2)
        if b1.button("✏️ 套用型態", use_container_width=True, key="pool_setbtn"):
            try:
                set_type_override(_sel, "" if _newt.startswith("自動") else _newt,
                                  oauth_client=_oauth)
                st.rerun()
            except Exception as _e:  # noqa: BLE001
                st.error(f"設定失敗:[{type(_e).__name__}] {str(_e)[:60]}")
        if b2.button("🗑️ 從池移除", use_container_width=True, key="pool_delbtn"):
            try:
                remove_from_pool(_sel, oauth_client=_oauth)
                st.rerun()
            except Exception as _e:  # noqa: BLE001
                st.error(f"移除失敗:[{type(_e).__name__}] {str(_e)[:60]}")

        # v19.476(user 2026-08-19「星辰不是用 isin 查,要用 isin 查 secId 回填後再去星辰查」):
        # 晨星 timeseries 是用 **secId(F 開頭)** 抓,不是 ISIN。ISIN→secId 的自動搜尋
        # (lt.morningstar SecuritySearch)對部分保單平台基金查不到 → 無 secId 可回填 →
        # 落回 MoneyDJ 30 天短窗。這裡讓使用者手動把查到的 secId 回填進池,補淨值即改走
        # secId 直抓(`_src_morningstar_nav` 內 resolve_secid 優先)。放 expander,保持表單精簡。
        with st.expander("🔧 進階:手動填晨星 secId(某檔抓不到 5 年淨值時用)", expanded=False):
            st.caption("流程:**你的代號 →(選股池)ISIN →(晨星)secId →(Yahoo chart)抓 NAV**。"
                       "到 [morningstar.co.uk](https://www.morningstar.co.uk) 用 ISIN 查到該檔,"
                       "複製 secId 填這裡。**優先填 `0P` 開頭**(如 `0P0001J5YG`,走 Yahoo chart,"
                       "美國 IP 最穩);`F` 開頭(如 `F000014R7W`,走晨星 timeseries)也吃。存檔後回"
                       "上方按『開始補抓全部缺淨值』,系統就用 secId 直抓 ~10 年(繞過失敗的 ISIN 搜尋)。")
            _sc1, _sc2, _sc3 = st.columns([2, 2, 1])
            _sid_code = _sc1.selectbox("基金", _codes, key="pool_secid_code")
            _sid_val = _sc2.text_input("晨星 secId(優先 0P 開頭)", key="pool_secid_val",
                                       placeholder="0P0001J5YG")
            _sid_ccy = _sc3.text_input("幣別", key="pool_secid_ccy", placeholder="USD")
            if st.button("💾 存晨星代碼", use_container_width=True, key="pool_secid_btn"):
                _sv = (_sid_val or "").strip()
                if not _sv:
                    st.warning("請填 secId(F 開頭)。")
                else:
                    try:
                        from repositories.pool_repository import set_secid
                        set_secid(_sid_code, _sv, currency=(_sid_ccy or "").strip(),
                                  oauth_client=_oauth)
                        st.success(f"已存:{_sid_code} → {_sv}。回上方按『開始補抓全部缺淨值』試抓,"
                                   "看『來源』欄是否變 🌐 晨星、跨度是否拉長。")
                        st.rerun()
                    except Exception as _e:  # noqa: BLE001
                        st.error(f"存入失敗:[{type(_e).__name__}] {str(_e)[:80]}")


# ───────────────────────── 建議渲染 ─────────────────────────

def _render_advice(res: dict, macro, fxlbl) -> None:
    import pandas as pd
    st.warning(res["caveat"])                       # §1 caveat 先於建議
    _fx_zh = {"strong_twd": "台幣強", "neutral": "匯率中性", "weak_twd": "台幣弱", None: "未知"}
    st.caption(f"總經 composite:{macro if macro is not None else '未取得(先跑總經分頁→成長型判斷才啟用)'}"
               f"　·　匯率位階:{_fx_zh.get(fxlbl, '未知')}")

    def _under_zh(a):
        u = a.get("underperformance") or {}
        if not u.get("is_underperforming"):
            return "—"
        _lbl = "・".join(u.get("reasons") or []) or "表現差"
        _ex = u.get("excess_pct")
        return f"⚠️ {_lbl}" + (f"(vs 大盤 {_ex:+.1f}pp)" if _ex is not None else "")

    def _cand_zh(a):
        _c = a.get("switch_to") or a.get("underperf_candidate")
        if not _c:
            return "—"
        _x = " ⚠️跨幣別" if _c.get("cross_ccy") else ""   # v19.484 §4.1:換股含匯差提醒(不砍建議)
        return f"{_c['name']}(σ{_c['buy_sigma']}){_x}"

    _adv = res["advices"]
    _rows = [{
        "基金": a["name"], "型態": (a["type"] or "無法判定") + (f"·{a['type_method']}" if a["type"] else ""),
        "ER": a["er"] if a["er"] is not None else "—",
        "建議": a["action_zh"],
        "表現差": _under_zh(a),
        "換入標的": _cand_zh(a),
        "理由": a["reason"],
    } for a in _adv]
    from streamlit import column_config as _cc
    st.dataframe(
        pd.DataFrame(_rows), use_container_width=True, hide_index=True,
        column_config={
            "基金": _cc.TextColumn("基金", width="medium",
                help="你目前持有的基金。"),
            "型態": _cc.TextColumn("型態", width="small",
                help="這檔用哪一套規則判定,以及是誰決定的:"
                     "「震盪」= 價格來回走,靠高低基期進出;"
                     "「成長」= 長期向上,靠總經與趨勢決定去留;"
                     "後面的小字是判定方式(你手動指定,或系統依波動自動判)。"),
            "ER": _cc.TextColumn("ER", width="small",
                help="效率比(Efficiency Ratio):這段期間的淨漲跌 ÷ 一路上上下下的總移動距離,"
                     "介於 0~1。**接近 1 = 一路直線往上(成長型)**,"
                     "**接近 0 = 上上下下走不出去(震盪型)**。"
                     "「—」= 淨值資料不足,算不出來。"),
            "建議": _cc.TextColumn("建議", width="medium",
                help="換股 / 賣出轉現金 / 警示 / 續抱 / 資料不足。"
                     "**教學參考,不是投資建議**;缺條件時一律回「續抱」或「資料不足」,不硬給動作。"),
            "表現差": _cc.TextColumn("表現差", width="medium",
                help="這檔是不是表現差(兩訊號任一成立):**跑輸大盤** = 近一年落後對應大盤逾 5 個百分點;"
                     "**絕對虧損** = 近一年含息報酬與 Sharpe 同時為負(實際在虧)。"
                     "表現差時,右邊「換入標的」會從你的選股池挑替代標的。「—」= 沒有表現差 / 資料不足。"),
            "換入標的": _cc.TextColumn("換入標的", width="medium",
                help="從你的選股池裡挑出的替換標的,括號裡是它現在離高點多遠(愈負 = 跌愈深)。"
                     "標「⚠️跨幣別」= 它與被換出的持倉計價幣別不同,換股會被動吃到匯差(仍保留,由你決定)。"
                     "「—」= 池子裡沒有合適的,不硬湊。"),
            "理由": _cc.TextColumn("理由", width="large",
                help="這個建議是依據哪幾個條件推出來的 —— 不同意就別照做,這欄的用途是讓你能反駁它。"),
        },
    )

    s = res["summary"]
    st.caption(f"持倉 {s['n_holdings']} 檔 → 換股 {s['n_switch']}・賣出轉現金 {s['n_sell_cash']}・"
               f"警示 {s['n_warn']}・續抱 {s['n_hold']}・資料不足 {s['n_insufficient']}"
               f"　·　⚠️ 表現差 {s.get('n_underperforming', 0)} 檔(跑輸大盤或絕對虧損)。")


def render_switch_advisor_section(funds: list) -> None:
    """🎯 換股池顧問 —— 選股池管理 + (按鈕觸發)換股建議。funds = 已載入持倉 rich dict。"""
    from repositories.pool_repository import list_pool
    from services.switch_advisor import advise_switches

    st.divider()
    st.markdown("### 🎯 換股池顧問(選股池 + 換股建議・教學非保證)")

    # v19.433:選股池的加/刪/改已移到「📋 我的管理室」分頁集中管理(避免同一 st.tabs run
    # 兩處都渲染 _render_pool_editor → DuplicateWidgetID)。本區仍讀選股池做配對(下方按鈕)。
    st.caption("💡 選股池的新增/刪除已搬到「📋 我的管理室」分頁集中管理;本區直接讀你的選股池做換股配對。")

    if not funds:
        st.info("尚未載入持倉基金 → 先在上方載入基金,再回來產生換股建議。")
        return

    render_portfolio_tracking(funds)                    # 📈 績效追蹤(走勢 + 快照)

    st.markdown("#### 🔁 換股建議(依你目前持倉 × 選股池 × 表現差)")
    # v19.504:同 tab_fund_grp_health「開始健診」修法 —— 換股建議是否已產生存 session_state,
    # 不吃 st.button 的「僅本次 rerun 為 True」語意。原 `if not st.button(...): return` 會在
    # 出建議後、user 一按同頁的逐檔「掃三率 / 個股新聞」鈕觸發 rerun 時回 False → 整塊換股
    # 建議塌回「按上方按鈕」提示(user 2026-08-21「壓一下就回到這」同型)。
    if st.button("🔍 產生換股建議(會補抓池中未載入標的)", use_container_width=True,
                 key="switch_advise_btn"):
        st.session_state["_switch_advise_done"] = True
    if not st.session_state.get("_switch_advise_done"):
        st.caption("按上方按鈕產生建議(避免每次重整都補抓池中標的)。")
        return

    try:
        # v19.508:SA 缺時用登入者 OAuth 讀選股池(與管理室編輯器同一本 → 手機加的檔這裡也看得到)。
        pool = list_pool(oauth_client=_pool_oauth_client())
        _pool_by_code = {e.code: e for e in pool}
        with st.spinner("計算換股建議中(補抓池中標的 + 判定表現差)…"):
            _held = _rows_with_nav(funds, _pool_by_code)
            _cands = _pool_rows(pool, funds)
            _macro = _macro_composite()
            _fx = _fx_label()
            _under = _underperf_by_code(funds)          # 表現差(跑輸大盤 OR 絕對虧損)
            _res = advise_switches(_held, _cands, fx_label=_fx, macro_composite=_macro,
                                   underperformance_by_code=_under)
        _render_advice(_res, _macro, _fx)
    except Exception as _e:  # noqa: BLE001
        system_error("換股建議產生失敗", _e)
