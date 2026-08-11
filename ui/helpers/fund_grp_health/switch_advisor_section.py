"""ui/helpers/fund_grp_health/switch_advisor_section.py — 🎯 換股池顧問區塊(v19.428)。

L3 orchestrator:選股池 CRUD(L1 `pool_repository`,EX-CRUD-1)+ 讀已載入持倉 → 逐檔換股建議
(L2 `switch_advisor`)。震盪型高基期→池中低基期健康配對;成長型總經看衰+跌破雙確認賣出。

取數走既有 L2/L3:持倉列用 `fund_grp_health.rotation._assemble_rows`;池中未載入標的用
`services.fund_row.process_one_fund` 補抓(L2);總經 composite 讀 session;匯率位階走
`fx_regime.fx_regime_by_ccy`。**教學非保證**:缺條件誠實回持有/資料不足(§1),不硬給動作。
"""
from __future__ import annotations

import streamlit as st

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
        from ui.helpers.fund_grp_health.fx_regime import fx_regime_by_ccy
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
        r["type_override"] = (pool_by_code.get(_c) or {}).get("type_override", "")
        if not r.get("基金類別"):
            r["基金類別"] = (pool_by_code.get(_c) or {}).get("category")
    return rows


def _fetch_rich(code: str) -> "dict | None":
    """池中未載入標的 → 走健診管線補抓成 rich dict(L2 process_one_fund + L3 _build_fund_dict)。"""
    try:
        from services.fund_row import process_one_fund
        from ui.helpers.fund_grp_health_extras import _build_fund_dict
        r = process_one_fund(code, _PRINCIPAL)
        if r.get("ok") and r.get("_fund_raw"):
            return _build_fund_dict(r["_fund_raw"], code, _PRINCIPAL)
    except Exception as _e:  # noqa: BLE001
        st.caption(f"⬜ 池中標的 {code} 補抓失敗,略過:[{type(_e).__name__}] {str(_e)[:60]}")
    return None


def _pool_rows(pool: list, funds: list) -> list:
    """選股池 → 候選列。已載入的重用;未載入的補抓。附 nav_series + type_override + 類別。"""
    from ui.helpers.fund_grp_health.rotation import _assemble_rows
    _loaded = {f.get("code"): f for f in funds}
    out = []
    for e in pool:
        _rich = _loaded.get(e.code) or _fetch_rich(e.code)
        if _rich is None:
            continue
        _row = _assemble_rows([_rich])[0]
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


def _redlight_by_code(funds: list, excess_by_code: dict) -> dict:
    """逐檔絕對虧損紅燈(重用 switch_strategy SSOT:含息1Y × Sharpe × 最大跌幅 × vs大盤)。

    § 與大表同源:走 `switch_score` + `switch_signal`(RED = 含息1Y<0 且 Sharpe<0,或嚴重吃本金)。
    本層不接吃本金字串(避免字串比對脆弱),故為大表紅燈的**保守子集**;缺料 → None(§1 不臆測)。
    """
    import sys
    out: dict = {}
    for f in funds:
        _code = f.get("code")
        try:
            from services.fund_total_return import compute_1y_total_return
            from services.switch_strategy import RED, switch_score, switch_signal
            _tr, _ = compute_1y_total_return(f)
            _m = f.get("metrics") or {}
            _rm = f.get("risk_metrics") or {}
            _sh = _m.get("sharpe")
            _dd = _rm.get("max_drawdown")
            if _dd is None:
                _dd = _m.get("max_drawdown")
            _vm = excess_by_code.get(_code)
            _cov: dict = {}
            _sc = switch_score(_tr, _sh, _dd, _vm, coverage_out=_cov)
            out[_code] = (switch_signal(_tr, _sh, "", _sc, coverage=_cov) == RED)
        except Exception as _e:  # noqa: BLE001 — 單檔失敗不拖垮整組;誠實 None
            print(f"[switch_advisor_section] {_code} 紅燈判定失敗:{type(_e).__name__}: {_e}",
                  file=sys.stderr)
            out[_code] = None
    return out


def _underperf_by_code(funds: list) -> dict:
    """{code → assess_underperformance(...)}。跑輸大盤走 capture_by_code 的「vs 大盤%」,
    絕對虧損走 `_redlight_by_code`。兩者任一 → 表現差(§C OR)。"""
    from services.switch_advisor import assess_underperformance
    from ui.helpers.fund_grp_health.capture import capture_by_code

    _cap = capture_by_code(funds)                       # {code: {vs 大盤%, vs 大盤期間, …}}
    _excess = {c: (_cap.get(c) or {}).get("vs 大盤%") for c in (_cap or {})}
    _red = _redlight_by_code(funds, _excess)
    out: dict = {}
    for f in funds:
        _code = f.get("code")
        _c = _cap.get(_code) or {}
        out[str(_code)] = assess_underperformance(      # str 鍵對齊 advise_switches 的 str(code) 查詢
            excess_pct=_c.get("vs 大盤%"),
            full_period=str(_c.get("vs 大盤期間", "")).startswith("⚠️ 全期"),
            benchmark_label=_benchmark_label_for(f),
            redlight=_red.get(_code),
        )
    return out


# ───────────────────────── 組合績效追蹤(走勢 + 永久快照)─────────────────────────

def _maybe_snapshot(nav_by_code: dict, weights: dict, is_equal: bool, funds: list) -> None:
    """本 session 首次進入 → 寫一筆組合績效快照(往前累積;repo 依 date 去重,每天最多一列)。"""
    if st.session_state.get("_perf_snapshot_done"):
        return
    try:
        from repositories.portfolio_perf_repository import PerfSnapshot, append_snapshot
        from services.portfolio_tracking import build_snapshot_row
        _cost = sum(float(f.get("invest_twd") or 0) for f in funds) or None
        _row = build_snapshot_row(nav_by_code, weights, total_cost_twd=_cost, is_equal_weight=is_equal)
        if _row is None:
            return                                       # 資料不足 → 不寫、不設旗標(下次資料夠再試)
        st.session_state["_perf_snapshot_done"] = True   # 已嘗試寫入即設(避免 GS 錯誤時每次 rerun 重打)
        append_snapshot(PerfSnapshot(**_row))
    except Exception as _e:  # noqa: BLE001 — 快照失敗不影響走勢顯示;誠實提示
        st.caption(f"⬜ 績效快照未寫入(不影響走勢):[{type(_e).__name__}] {str(_e)[:80]}")


def render_portfolio_tracking(funds: list) -> None:
    """📈 投資組合績效追蹤:用已累積 NAV × 目前權重重建走勢 + 永久快照(§req 1)。"""
    from ui.helpers.portfolio_perf import _nav_weights_from_funds
    from services.portfolio_tracking import reconstruct_trend

    _nav, _w, _equal = _nav_weights_from_funds(funds)
    if len(_nav) < 1:
        return

    st.markdown("#### 📈 投資組合績效追蹤(走勢 + 快照)")
    _t = reconstruct_trend(_nav, _w)
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
        st.caption(f"⬜ 快照歷史讀取略過:[{type(_e).__name__}] {str(_e)[:60]}")


# ───────────────────────── 選股池 CRUD UI ─────────────────────────

def _render_pool_editor() -> None:
    from repositories.pool_repository import (
        PoolEntry,
        add_or_update,
        list_pool,
        remove_from_pool,
        set_type_override,
    )
    st.markdown("#### 📁 選股池(候選基金)")
    try:
        pool = list_pool()
    except Exception as _e:  # noqa: BLE001
        st.caption(f"⬜ 選股池讀取失敗:[{type(_e).__name__}] {str(_e)[:80]}")
        return

    if pool:
        import pandas as pd
        from streamlit import column_config as _cc
        _df = pd.DataFrame([{"代號": e.code, "名稱": e.name, "類別": e.category,
                             "手動型態": e.type_override or "自動", "備註": e.note,
                             "加入日": e.added_at} for e in pool])
        st.dataframe(
            _df, use_container_width=True, hide_index=True,
            column_config={
                "代號": _cc.TextColumn("代號", width="small",
                    help="基金代號 —— 產生換股建議時,沒載入過的會自動補抓一次。"),
                "名稱": _cc.TextColumn("名稱", width="medium",
                    help="選填。留白時只會看到代號。"),
                "類別": _cc.TextColumn("類別", width="small",
                    help="選填。填了可以幫助配對「同類別」的替換標的;留白時改用抓到的基金類別。"),
                "手動型態": _cc.TextColumn("手動型態", width="small",
                    help="你手動指定這檔要用哪一套規則:「震盪」= 走高低基期來回操作;"
                         "「成長」= 看總經與趨勢決定去留;「自動」= 由系統依波動判定。"),
                "備註": _cc.TextColumn("備註", width="large",
                    help="給自己看的筆記(例如為什麼把它放進候選),不參與任何計算。"),
                "加入日": _cc.TextColumn("加入日", width="small",
                    help="加進選股池的日期,不是基金成立日。"),
            },
        )
    else:
        st.caption("選股池目前是空的 —— 用下方表單加入候選基金。")

    with st.form("pool_add_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 1.5, 1])
        _code = c1.text_input("基金代號", key="pool_code")
        _name = c2.text_input("名稱(選填)", key="pool_name")
        _cat = c3.text_input("類別(選填)", key="pool_cat")
        _ov = st.selectbox("型態(可留自動)", _TYPE_OPTS, key="pool_type")
        _note = st.text_input("備註(選填)", key="pool_note")
        if st.form_submit_button("➕ 加入 / 更新選股池", use_container_width=True):
            _c = (_code or "").strip()
            if not _c:
                st.warning("請輸入基金代號。")
            else:
                _ovv = "" if _ov.startswith("自動") else _ov
                try:
                    add_or_update(PoolEntry(code=_c, name=_name.strip(), category=_cat.strip(),
                                            type_override=_ovv, note=_note.strip()))
                    st.success(f"已加入 / 更新:{_c}")
                    st.rerun()
                except Exception as _e:  # noqa: BLE001
                    st.error(f"寫入失敗:[{type(_e).__name__}] {str(_e)[:80]}")

    if pool:
        cc1, cc2 = st.columns(2)
        _codes = [e.code for e in pool]
        _sel = cc1.selectbox("改型態 / 移除", _codes, key="pool_sel")
        _newt = cc2.selectbox("設型態", _TYPE_OPTS, key="pool_newtype")
        b1, b2 = st.columns(2)
        if b1.button("✏️ 套用型態", use_container_width=True, key="pool_setbtn"):
            try:
                set_type_override(_sel, "" if _newt.startswith("自動") else _newt)
                st.rerun()
            except Exception as _e:  # noqa: BLE001
                st.error(f"設定失敗:[{type(_e).__name__}] {str(_e)[:60]}")
        if b2.button("🗑️ 從池移除", use_container_width=True, key="pool_delbtn"):
            try:
                remove_from_pool(_sel)
                st.rerun()
            except Exception as _e:  # noqa: BLE001
                st.error(f"移除失敗:[{type(_e).__name__}] {str(_e)[:60]}")


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
        return f"{_c['name']}(σ{_c['buy_sigma']})" if _c else "—"

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

    _render_pool_editor()

    if not funds:
        st.info("尚未載入持倉基金 → 先在上方載入基金,再回來產生換股建議。")
        return

    render_portfolio_tracking(funds)                    # 📈 績效追蹤(走勢 + 快照)

    st.markdown("#### 🔁 換股建議(依你目前持倉 × 選股池 × 表現差)")
    if not st.button("🔍 產生換股建議(會補抓池中未載入標的)", use_container_width=True,
                     key="switch_advise_btn"):
        st.caption("按上方按鈕產生建議(避免每次重整都補抓池中標的)。")
        return

    try:
        pool = list_pool()
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
        st.caption(f"⬜ 換股建議產生失敗:[{type(_e).__name__}] {str(_e)[:100]}")
