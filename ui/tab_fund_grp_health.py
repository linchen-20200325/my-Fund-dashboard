"""v19.37 ui — 💊 基金組合健診 Tab。

對 100 萬 TWD 為基準，模擬持有 N 檔境外保單基金，計算每次配息折回 TWD 金額並判定吃本金。

UI 結構：
  1. text_area 多碼貼上（上限 10 檔，鏡像 stock_grp）
  2. 本金 / 警示閾值參數
  3. 按鈕觸發 → progress + 抓 NAV / 配息 / FX → 純函式運算
  4. KPI metric + 健診總表 + 逐期配息明細 expander

🧮 標示：所有自行計算欄位（份額 / TWD 配息 / 含息報酬率 / 吃本金判定）
原始欄位（MoneyDJ/Cnyes 直給）：除息日 / 原幣配息 / NAV
"""
from __future__ import annotations

import streamlit as st

from ui.helpers.render_state import business_alert, not_ready, system_error
# 指路文案的分頁名 SSOT（理由見下方 `_EQUAL_MODE_HEALTH_TAB_HINT` /
# `_CS_WHERE_HEALTH` 兩處的 2026-08-31 註記）。
from ui.helpers.story_nav import tab_label as _tab_label

from shared.colors import GH_BG_PRIMARY, GH_FG_SECONDARY, GRAY_55, INFO_BLUE, TRAFFIC_GREEN
from shared.converters import safe_num  # v19.387 V1 §1:缺值保留 None(不畫成 0% 假柱)

_MAX_CODES = 10

# 稽核 C2:原「吃本金閾值 %」滑桿拆除後,下游仍需要一個值。走 SSOT 常數,
# 不在這裡寫死 2.0(§3.3);它只影響 production 0 consumer 的 `div_health_light_🧮`,
# 但既然還在傳,就不該傳一個來路不明的數字。
from services.health.dividend_calc import DEFAULT_WARN_GAP_PCT as _DEFAULT_WARN_GAP  # noqa: E402
_DEFAULT_CCY = "USD"


def _pick_comparison_basis(rows: "list[dict]") -> str:
    """v19.304: 多基金績效比較圖的「基準」選擇 SSOT（純函式，可單元測試）。

    背景（user 2026-07-04「多檔比較資料都是 0」）：v19.180 把績效欄拆成
    「(年化)」+「(全期實際)」兩套。年化欄在持有 < 0.5 年時依
    `dividend_calc.MIN_YEARS_FOR_ANNUALIZE`（SSOT = shared/signal_thresholds.py）
    一律回 None（防「短期配息 × 倍數」年化幻象，§1 Fail Loud）。同保單同期買進的
    多檔常整排短歷史 → 年化全 None → 圖表 `float(None or 0)` 畫成全 0 空圖。

    規則：全檔都有年化值（皆 ≥ 0.5 年）→ 用「年化」(跨檔可比、原設計)；
    任一檔短歷史（年化為 None）→ 全圖退「全期實際」(100% 真實累計、永遠有值、
    不年化故無造假)。回傳基準字串，caller 用 f"X% ({basis})" 組欄位鍵，
    確保同一張圖各檔基準一致（不混基準）。
    """
    _all_annual = all(
        r.get("配息率% (年化)") is not None
        and r.get("含息% (年化)") is not None
        and r.get("淨值% (年化)") is not None
        for r in rows
    )
    return "年化" if _all_annual else "全期實際"


_SHARPE_SRC_COL = "Sharpe 來源"


# ── 健診大表標題 SSOT(2026-09-02 T19)────────────────────────────────────────
# 這一頁**只有一張表**,但原本印了**兩個 h4 標題**在它上面:
#   `#### 📊 健診大表（①②③ 已去重複合併成一張;橫向可滾動）`(由 `_render_health_3tables` 印)
#   `#### 健診總表（🧮 = 自行換算欄位）`              (由 `_render_health_table` 印)
# 兩句在講同一張 dataframe,中間還隔著新鮮度 banner 與 KPI —— 使用者會以為底下有兩張表,
# 捲到最後只找得到一張。合併成一句,兩邊原本各自帶的資訊(合併去重複 / 🧮 自行換算 /
# 橫向可滾動)一項不減。
# 走常數而不是各自寫字面值:全失敗 early-return 也要印同一個標題(D2),
# 兩處手抄正是這次要修的病。
_BIG_TABLE_HEADING = (
    "#### 📊 健診大表（①②③ 已去重複合併成一張;🧮 = 自行換算欄位;橫向可滾動）"
)


def _fold_uniform_sharpe_source(df):
    """本批「Sharpe 來源」全同 → 從 df 剔除該欄,回 `(df, 唯一來源標籤)`;否則 `(df, None)`。

    背景(2026-08-05 稽核 🟢 選作 6):健診大表 48+ 欄,`Sharpe 來源` 逐列都印,
    10 檔全是 `wb07 1Y(官方)` 時整欄零資訊量,卻佔掉一個欄寬。

    **刻意只做在呈現層**:
    - 不動 `ui/helpers/fund_grp_health/unified._UNIFIED_FRONT` 欄序常數
      (`tests/test_risk_metric_disclosure.py:329-330` 斷言旗標欄必須緊貼被標註欄),
      也不動批次大表 `BATCH_UNIFIED_COLUMNS`(固定欄序 → checkpoint 相容)。
    - 不加側車 dict:唯一 consumer 就是本檔表下的 caption,多包一層 = `CLAUDE.md`
      §8.1 step 6 的「用不到的抽象」,且會踩 `PROCESS.md §4` 的 0-consumer 陷阱。

    **保守條件**(§2.2 揭露不得被折疊掉):任一列缺值 / 出現 >1 種來源 → 原樣保留。
    混期(wb07 6M 混 1Y)正是本欄存在的理由,絕不可收合。
    """
    # ⚠️ 不可寫 `list(getattr(df, "columns", []) or [])` —— pandas `Index` 沒有定義
    #    __bool__,`Index or []` 會 raise
    #    `ValueError: The truth value of a Index is ambiguous`。
    #    (空 df 一樣會炸,因為 `or` 先對 Index 求真值才輪到短路。)
    if df is None:
        return df, None
    if _SHARPE_SRC_COL not in list(getattr(df, "columns", [])):
        return df, None
    _vals = list(df[_SHARPE_SRC_COL])
    if not _vals:
        return df, None
    if any(v is None or str(v).strip() == "" or str(v) == "nan" for v in _vals):
        return df, None            # 有缺值 = 不是「全同」,照常常駐
    _uniq = {str(v) for v in _vals}
    if len(_uniq) != 1:
        return df, None            # 真混期 → 逐列顯示
    return df.drop(columns=[_SHARPE_SRC_COL]), _uniq.pop()


def _dedup_upper(seq) -> "list[str]":
    """代號清單 order-preserving 去重 + 大寫正規化 —— SSOT:本 Tab 代號唯一化只此一處。

    背景(user 2026-07-05「配息事件（多檔合併）有重複」):同一基金若被多張保單持有,
    `portfolio_funds` 會出現同 code 多筆;「🔗 從我的組合帶入」後代號清單即帶重複 →
    `_run_batch_health` 逐檔各算一次 → 持有 meta / 配息事件 / 比較圖三表全部重複列。
    本 Tab 輸入僅「代號 + 單一本金」,同 code = 完全相同計算 = 真重複,去重安全。
    """
    out: "list[str]" = []
    seen: set[str] = set()
    for x in seq:
        c = str(x).strip().upper()
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _dedup_rows_by_code(rows: "list[dict]") -> "list[dict]":
    """row list order-preserving 去重(以 code 為鍵)—— SSOT 顯示層 chokepoint。

    `_render_health_3tables` 同時被健診 Tab 與 Tab3 組合 embed 呼叫;任一路徑若傳入
    同 code 多筆(多保單持同檔),持有 meta / 配息事件 / 比較圖三表都會重複列。在渲染
    入口一次去重覆蓋所有 caller(補「代號輸入端 `_dedup_upper`」的另一半,兩者互補)。
    空 code 的 row 視為各自唯一(不丟、不去重),避免誤刪合法列。
    """
    out: "list[dict]" = []
    seen: set[str] = set()
    for r in rows:
        c = str(r.get("code", "")).strip().upper()
        if c and c in seen:
            continue
        if c:
            seen.add(c)
        out.append(r)
    return out


def render_fund_grp_health_tab() -> None:
    """渲染 ② 持倉體檢 Tab（v19.37 新增；2026-09-01 隨客戶拍板線框改名）。"""
    # ⚠️ 頁面標題**必須**走 `tab_label('health')`，不得寫死中文字面值。
    #    2026-09-01 改名（組合健診 → 持倉體檢）時，這裡原本寫死「### 💊 基金組合健診」
    #    —— 分頁列已經改成「💊 持倉體檢」，點進來卻還是舊標題，**同一頁兩個名字**。
    #    這是本 repo 第三次發生死指路（前兩次見 `ui/helpers/story_nav.py` docstring），
    #    也是唯一一次「使用者一打開分頁就看得到」的。走 SSOT 之後它不可能再漂。
    from ui.helpers.story_nav import render_flow_nav, render_story_nav, tab_label
    st.markdown(f"### {tab_label('health')}")
    render_flow_nav("health")   # 巨觀:第 ③ 層 監控與評分
    render_story_nav("health")  # v19.405 Phase 4:健診為決策動線第 2 站
    st.caption(
        "對 **100 萬 TWD** 為基準，模擬持有期間每次配息折算 TWD 金額並判定吃本金。"
        "🧮 = 本系統自行換算（非 MoneyDJ/Cnyes 直給）。"
    )

    # v19.303: 總經 Phase 對照橫幅 — 提供健診結果的市場環境上下文
    _phase_info = st.session_state.get("phase_info") or {}
    _phase_name = _phase_info.get("phase", "")
    if _phase_name:
        _phase_lower = _phase_name.lower()
        if any(k in _phase_lower for k in ("多頭", "擴張", "bull", "expansion")):
            _phase_icon, _phase_tip = "🟢", "多頭期：健診標準可適度放寬，重點看含息報酬能否跑贏通膨。"
        elif any(k in _phase_lower for k in ("衰退", "防禦", "bear", "recession")):
            _phase_icon, _phase_tip = "🔴", "防禦期：吃本金判定應從嚴看待；股票型基金承壓，配息穩定性更重要。"
        else:
            _phase_icon, _phase_tip = "🟡", "過渡期：健診結果請搭配個別基金趨勢判斷。"
        # v19.403 Phase 2 DUP-3:景氣位階字卡走 format_phase_score SSOT。
        # 原「評分 {_score:+.1f}」(如 +6.5)誤用正負號 —— phase score 恆 0-10,
        # 與 hero 的 23 指標淨分(genuinely signed)撞臉;改「{phase} {score}/10」統一。
        from ui.helpers.macro_helpers import format_phase_score
        st.info(
            f"📊 當前總經 Phase：{_phase_icon} **{format_phase_score(_phase_info)}**"
            f"　{_phase_tip}"
        )
    else:
        # 2026-08-05 稽核 必修 2:指路文案的分頁名走 story_nav SSOT,分頁改名時
        # 這行自動跟著改(原先三處同型文案寫死舊名 → 指到不存在的分頁)。
        from ui.helpers.story_nav import tab_label as _tab_label
        st.caption(f"💡 先至「{_tab_label('macro')}」Tab 載入資料，健診結果將顯示對應市場環境說明。")

    # v19.302: 從組合配置帶入基金代號（讀 portfolio_funds session_state）
    _pf_raw = st.session_state.get("portfolio_funds") or []
    # v19.322 SSOT 去重:同基金跨多保單會出現同 code 多筆,帶入前先唯一化(否則三表重複列)
    _pf_codes = _dedup_upper(f.get("code", "") for f in _pf_raw)
    if _pf_codes:
        if st.button(f"🔗 從我的組合帶入（{len(_pf_codes)} 檔）", key="grp_health_import_from_pf"):
            st.session_state["fund_grp_health_codes"] = "\n".join(_pf_codes)
            st.rerun()

    # ── 診斷條件表單(2026-09-02 T1;拍板線框 Tab 02「Form ─ 診斷條件」)──────────
    # 為什麼一定要包 `st.form`:本頁**每一次 rerun 都會重抓淨值、並打一次 Google Sheets**
    # (`_run_batch_health` → MoneyDJ/FundClear 逐檔取數;`record_batch_nav_points` →
    # nav_history 分頁 append)。沒有 form 時,使用者在「本金」上按一下上下鍵、
    # 或在代號框改一個字,Streamlit 就整頁重跑一輪 —— 對外部來源等於一次白打的轟炸
    # (§02「失敗時退避,不連續轟炸來源」的同一個成本面)。
    # 包進 form 之後,widget 的值只在**按下送出鈕**時才提交一次。
    #
    # ⚠️ 「🔗 從我的組合帶入」**刻意留在 form 外**:它會寫 session_state 後 `st.rerun()`,
    #    而 `st.button` 在 form 內是被 Streamlit 明文禁止的(只能有 form_submit_button)。
    #    它本來就不是「診斷條件」,是一個獨立的帶入動作。
    from ui.helpers.ia import applied_form as _applied_form  # noqa: PLC0415
    with _applied_form("fund_grp_health_form",
                       submit_label="🩺 開始健診") as _health_gate:
        codes_raw = st.text_area(
            f"基金代號（每行一檔，最多 {_MAX_CODES} 檔；例：ACCP138）",
            key="fund_grp_health_codes",
            height=130,
            placeholder="ACCP138\nACUSI23\n...",
        )
        # v19.59：移除「原幣別 fallback」selectbox — 幣別嚴格走 MoneyDJ wb05「計價幣別」欄抓網路。
        # MoneyDJ 抓不到 → 該檔回 error「幣別未知」（不再用人工選的 fallback 矇混）。
        principal_twd = st.number_input(
            "本金（TWD）",
            min_value=10_000.0, max_value=10_000_000.0,
            value=1_000_000.0, step=100_000.0,
            key="fund_grp_health_principal",
            help="所有基金都假設投入這個金額，才能把「每月配息」「累積配息」放在同一個尺度上比較。",
        )

    # ── 稽核 C2（2026-08-14）：拆掉「吃本金閾值 %」滑桿 ────────────────────────
    # 它的 help 寫著「配息率 − 含息報酬率 > 此值 → 標 🔴 吃本金」，但畫面上那個 🔴
    # 根本不是它決定的：
    #   - 滑桿的值 → `process_one_fund(warn_gap)` → `compute_dividend_twd_series`
    #     → 產出 `div_health_light_🧮` —— 這個欄位**全 production 0 consumer**
    #     （只有測試在讀），沒有任何一張表、任何一個燈號用到它。
    #   - 表上真正的「吃本金燈號 (1Y·)」走 `check_eating_principal_1y_mk`，
    #     門檻取自 `shared/signal_thresholds`，與滑桿完全無關。
    # 也就是說：使用者拖動它、以為自己在調整判定標準，畫面上一個像素都不會變。
    #
    # 為什麼是拆掉而不是接上：吃本金是 老師的既定方法論，門檻是 SSOT 常數，
    # 開放成滑桿等於讓使用者自己調出一個「沒有紅燈」的組合（§8.1 step 6：
    # 用不到的抽象不留；一個騙人的控制項比沒有控制項更糟）。
    # 下游 `warn_gap` 參數保留不動（有預設值、有測試），只是不再由 UI 餵。
    warn_gap = _DEFAULT_WARN_GAP

    # v19.504:健診已跑狀態存 session_state,不再吃 st.button 的「僅本次 rerun 為 True」語意。
    # 原 `if not st.button(...): return` 的致命 bug(user 2026-08-21 回報「壓一下就回到這」):
    # 出結果後,一按任何逐檔按鈕(三率穿透 / 個股新聞)就觸發 rerun → 開始健診鈕回 False →
    # return → 整張健診結果塌回輸入表單。改存旗標:點過一次就持續渲染,逐檔按鈕不再弄丟結果。
    # 2026-09-02 T1:原 `st.button("🩺 開始健診", key="fund_grp_health_btn")` 已改為上方
    # `applied_form()` 的送出鈕(`st.button` 不得放在 form 內)。旗標語意不變:
    # gate 只在「按下送出的那一輪」為 True,長期狀態仍由 session_state 旗標持有。
    if _health_gate:
        st.session_state["_fund_grp_health_ran"] = True
    if not st.session_state.get("_fund_grp_health_ran"):
        return

    # v19.322:代號去重(SSOT _dedup_upper)—— 防同檔被多保單/手動貼多次 → 逐檔明細三表重複列
    codes = _dedup_upper(codes_raw.splitlines())[:_MAX_CODES]
    if not codes:
        st.warning("請至少輸入 1 個基金代號")
        return

    rows = _run_batch_health(codes, principal_twd, "", warn_gap)

    # v19.464 深化 #2:同類四分位(3Y 年化)。所有基金都在手才算得出 → 這裡 post-pass。
    # 邏輯在 L2 `peer_rank.peer_quartile_labels`:asset_bucket 粗桶分組 + NAV 序列重算年化
    # (一致基礎)+ §1 樣本誠實(<4 不硬分四分位)。加值欄:非底線 key `同類四分位` 隨
    # base_df 自動進寬表末段;失敗不擋健診表。
    try:
        from services.peer_rank import peer_quartile_labels
        _peer_labels = peer_quartile_labels(rows, window_years=3.0)
        for _pr in rows:
            if _pr.get("ok"):
                _pr["同類四分位"] = _peer_labels.get(_pr["code"], "無同類可比(未分類)")
    except Exception as _e_peer:  # noqa: BLE001 — 四分位為加值欄,失敗不擋健診表
        import sys as _sys_peer
        print(f"[grp_health] 同類四分位計算略過:{type(_e_peer).__name__}: {_e_peer}",
              file=_sys_peer.stderr)

    # v19.465 深化:235 加碼水位(老師「235 精準加碼」基金版)。VIX 整組抓一次,每檔用
    # 週 NAV 算 20週布林 + 4/13/52週均線 → 三取一 Max 燈。加值欄 `加碼水位` 隨寬表;失敗不擋表。
    _ladder_details: list = []   # v19.484 稽核 M1:收集每檔判定理由 → 表下方可展開對照
    try:
        from services.fund_service import get_latest_vix
        from services.ladder235 import ladder_signal
        _vix_now = get_latest_vix()          # None → ladder 退兩維判燈(誠實)
        for _pr in rows:
            if not _pr.get("ok"):
                continue
            _fr235 = _pr.get("_fund_raw") or {}
            _ser235 = _fr235.get("series")
            _cat235 = (_fr235.get("moneydj_raw") or {}).get("category") or _fr235.get("category")
            _lad = ladder_signal(_ser235, vix=_vix_now, category=_cat235)
            if _lad.get("lamp") is None:
                _pr["加碼水位"] = {"core": "⚪ 不適用(內建配置)",
                                   "lowvol": "⬜ 低波不判"}.get(_lad.get("status"), "⬜ 週資料不足")
            else:
                _pct = int(round(_lad["deploy_pct"] * 100))
                _pct_txt = f"(+{_pct}%)" if _pct > 0 else ""
                _pr["加碼水位"] = f"{_lad['emoji']} {_lad['lamp']}{_pct_txt}"
            _ladder_details.append({
                "name": _pr.get("基金名") or _pr.get("name") or _pr.get("code"),
                "water": _pr.get("加碼水位", ""),
                "reasons": list(_lad.get("reasons") or []),
                "note": _lad.get("note") or "",
            })
    except Exception as _e_lad:  # noqa: BLE001 — 加碼水位為加值欄,失敗不擋健診表
        import sys as _sys_lad
        print(f"[grp_health] 235 加碼水位計算略過:{type(_e_lad).__name__}: {_e_lad}",
              file=_sys_lad.stderr)

    # v19.484 稽核 M1:235 每檔判定理由(reasons/note 原本算完即丟)→ 收合展開,對照寬表「加碼水位」欄。
    if _ladder_details:
        with st.expander("🔎 235 加碼水位:各檔判定理由(對照下方寬表「加碼水位」欄)", expanded=False):
            st.caption("三取一 Max(最嚴重燈優先);停利獨立且優先。⚪巡航 / 🟢燈一(小跌) / "
                       "🟡燈二(急跌) / 🔴燈三(深水) / 💰停利。缺 VIX 時僅用均線+布林兩維(誠實標註)。")
            for _d in _ladder_details:
                st.markdown(f"**{_d['name']}** — {_d['water'] or '—'}")
                if _d["reasons"]:
                    st.caption("　· " + "　· ".join(str(_r) for _r in _d["reasons"]))
                if _d["note"]:
                    st.caption("　" + str(_d["note"]))

    # v19.359 Track 2:健診批次抓成功 → 把各檔當日最新 NAV append 進 Google Sheet
    # nav_history 分頁(一鍵累積全部持倉,從現在累積歷史序列)。冪等 + 非致命。
    try:
        from ui.helpers.nav_history_hook import record_batch_nav_points
        record_batch_nav_points(
            [(r["code"], r["_fund_raw"]) for r in rows
             if r.get("ok") and r.get("_fund_raw")],
            source="健診",
        )
    except Exception:
        pass  # 記錄失敗不影響主流程(helper 內已顯示提示)

    # v19.189：逐檔財務健診（4 大功能 + 健診摘要表 PK + 健診卡）移到「健診總表」上方
    #（user 要求：易讀的摘要 PK + 健診卡應先看到，逐欄 🧮 總表移其下）。
    # _funds_extra 由 _build_fund_dict 包裝，下方「健診總表」與「進階分析」共用同一份。
    _funds_extra: list = []
    try:
        from ui.helpers.fund_grp_health_extras import _build_fund_dict
        _funds_extra = [
            _build_fund_dict(r["_fund_raw"], r["code"], principal_twd)
            for r in rows
            if r.get("ok") and r.get("_fund_raw")
        ]
    except Exception as _e_build:
        system_error("進階資料建構失敗", _e_build,
                     hint="下方「進階分析」整區會因此不可用。")
        _funds_extra = []

    # v19.181:模組化 3 表 wrapper(健康分析 / 配息相關 / 實際購買結果)。
    # funds_extra 透給 _render_health_table 內部用(基金體檢 PK + 健診卡)。
    # v19.347：健檢 Tab 開「🎯 選基金（低基期）」;Tab3 持倉健診不開(預設 False)。
    # source_tab="health"：等權 caption 的「請到組合配置 Tab 逐檔填金額」導引只在本 Tab
    # 成立(本 Tab 只有單一本金欄位);Tab3 embed 不傳 → 不印(見 _weight_basis_note)。
    _render_health_3tables(rows, funds_extra=_funds_extra, show_screener=True,
                           source_tab="health")

    # ── 一檔都沒抓成功時,下游整串靜默消失 ──────────────────────────────────
    # 2026-08-28 客戶拍板 Q1「三問判準」在本頁的落點。三問各自的答案:
    #   問一 這個區塊該不該在這裡,是固定的還是取決於資料?
    #        → **固定**。「配置回測」「進階分析」是本頁骨架,不是「每檔一個」的展開區。
    #   問二 使用者為了看到它,已經做過那個動作了嗎?
    #        → **已經按過 🩺 開始健診、也等過**。他付出了等待卻整串消失,
    #          而且無從分辨「這個功能不存在」「這次沒算出來」「我的基金不適用」。
    #          → 判準命中:**一律留灰色占位 + 缺什麼 + 去哪裡補**。
    #   問三 它為什麼沒東西? → **還沒給資料**(不是結構上不適用),故用 ⬜ 不是 ➖。
    #
    # ⚠️ **為什麼只印一句,而不是在下面每一塊各印一句**:線框 §07 自己預警過
    #    「7 塊同時空 → 使用者會看到連續 7 條灰字」,而客戶 Q1 的第二句正是
    #    「按鈕前不加冗餘占位」。這一句在**因**的位置講完(0 檔可用),
    #    下游那幾塊是**果**,不再各講一次 —— 灰字的份量跟紅字一樣會被稀釋。
    #
    # ⚠️ **顏色**:真正的失敗已經在上面印成紅的了(逐檔的「❌ 抓取失敗」清單,
    #    或 `_build_fund_dict` 那個 `system_error`)。這一句講的是**那個失敗的下游後果**
    #    ——「這兩塊因此沒有輸入」,它本身不是一個新的故障,所以是 ⬜ 不是 🔴。
    #    (稽核提醒:不要把這一句當成「真失敗被畫成灰字」的違規 —— 真失敗在上面,是紅的。)
    if not _funds_extra:
        not_ready(
            f"「🔁 配置回測」與「🔬 進階分析」需要至少 1 檔的完整資料 —— "
            f"本次 {len(rows)} 檔裡可用 0 檔,故這兩塊沒有內容可算",
            where="本頁上方的失敗說明(逐檔原因)")

    # v19.427:🔁 配置回測(哪套配置效益最高 + 三輸出)。重用 _funds_extra(原幣 NAV + 幣別),
    # 走 L2 services.allocation_backtest;抓失敗/資料不足由 section 內誠實顯示,不拖垮整頁(§1)。
    if _funds_extra:
        try:
            from ui.helpers.fund_grp_health.backtest_section import render_allocation_backtest_section
            render_allocation_backtest_section(_funds_extra)
        except Exception as _e_bt:
            system_error("配置回測區塊渲染失敗", _e_bt)

    # ── 🎯 換股顧問:2026-09-01 已搬到 ④ 資產配置 ─────────────────────────────
    # ~~v19.428:🎯 換股池顧問(選股池 + 依持倉×池的換股建議)。選股池 CRUD 永遠可用;~~
    # ~~換股建議按鈕觸發(避免每次重整補抓池中標的)。缺 macro/FX 由 section 內誠實降級(§1)。~~
    # ~~render_switch_advisor_section(_funds_extra)~~
    # **有意識的政策變更,不是漏刪** · 日期 **2026-09-01** · 決策者:**客戶拍板線框**
    # (`docs/wireframes/ia-wireframe.html`)。
    #
    # **客戶給的理由(逐字,不是本組的判斷)**:線框 Tab 02「這裡不放什麼」寫著
    # 「換股建議與再平衡試算 → **04**(那是決策,不是診斷)」;Tab 04「從哪裡搬來」寫著
    # 「換股顧問 ─ 自 02 的健診段切出」。② 全篇**只診斷、不建議**,而換股顧問產出的是
    # **要執行的動作**。
    # **舊寫法的理由仍然成立**(換股建議確實需要「持倉 × 選股池」,而 ② 手上剛好有
    # 一份健診完的持倉);被權衡掉的是**它放在哪一頁** —— ④ 同樣有一份持倉健診結果
    # (`_funds_extra`),不必為了搬家重抓一次。
    #
    # ⚠️ **這一行指路是必要的,不是客套**:使用者原本在本頁找得到的東西被搬走了。
    #    本 repo 前例:一批 UI 重整打壞 6 處使用者可見的指路,由紅隊擋下。
    #    分區名走 `story_nav.where_to_find('switch')` SSOT —— **不得**手抄
    #    「④ 資產配置」或「🎯 換股顧問」,那正是本 repo 已經指錯三次的寫法。
    # ⚠️ **顏色**:功能搬到別頁**不是系統故障**,用灰色 caption(三態顏色分離),
    #    不得用 st.error / st.warning。同 `ui/tab3_portfolio.py` WP-G 那一行指路的處置。
    from ui.helpers.story_nav import where_to_find as _where_to_find_sw  # noqa: PLC0415

    st.caption(
        f"🎯 換股顧問(依你的持倉 × 選股池產生換股建議)請看 {_where_to_find_sw('switch')} —— "
        "本頁只回答「哪一檔出問題了」,要換什麼、怎麼配是決策,集中在那一頁。"
    )

    # v19.58 — 其餘進階貼圖區塊（真實收益矩陣 + 投資試算 + 持股 + 多檔比較 + AI…）。
    # 基金體檢 PK + 4 大健診卡已上移至健診總表之前，不再由此區塊渲染（避免上下重複）。
    if _funds_extra:
        try:
            from ui.helpers.fund_grp_health_extras import render_fund_grp_health_extras
            render_fund_grp_health_extras(_funds_extra, principal_twd)
        except Exception as _e_extra:
            system_error("進階分析區塊渲染失敗", _e_extra)


# v19.413:_auto_fetch_moneydj 隨 process_one_fund 下沉 services/fund_row.py 後,本檔已無 caller,
# 死 import 移除(fallback chain 仍集中於 services.moneydj_fetcher.auto_fetch_moneydj)。


# v19.413:process_one_fund 下沉 L2(services/fund_row.py),健診 + 批次共用同引擎。
from services.fund_row import process_one_fund  # noqa: E402

# backward-compat alias(舊呼叫者 / 測試直接 import 老名)
_process_one_fund = process_one_fund


def _run_batch_health(
    codes: list[str],
    principal_twd: float,
    ccy_hint: str,
    warn_gap: float,
) -> list[dict]:
    """v19.68 H：N 檔基金並行健診（原逐檔序列 → ThreadPoolExecutor）。

    瓶頸：每檔序列 _auto_fetch_moneydj（MoneyDJ 2-30s）+ get_latest_fx 累加，
    10 檔可達數十秒。改並行（max 4 worker，鏡像 Tab3 portfolio_load + macro
    4-way）。worker 無 st 呼叫；進度條在主執行緒以 as_completed 更新；by-index
    收集保留輸入順序與重複代碼。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    n = len(codes)
    if n == 0:
        return []
    # v19.497:選股池自填名 → name_hint。貼上的代號若是池成員(如 ALZF9,線上抓不到真名),
    # 主健診表顯示池名而非代號。§1:池讀失敗不擋健診(guard → 空 map,退代號)。EX-CRUD-1 允許 L3 直呼。
    _name_map: dict = {}
    try:
        from repositories.pool_repository import list_pool
        _name_map = {str(e.code).upper(): (e.name or "") for e in (list_pool() or []) if e.name}
    except Exception as _e_pool:  # noqa: BLE001
        print(f"[grp_health] 選股池名稱查詢略過:{type(_e_pool).__name__}: {_e_pool}")
    # v19.509:SA 缺(手機無 Service Account)時,**主執行緒**捕獲登入者 OAuth gspread client,
    # 傳入各 worker → 讓健診讀得到 OAuth 寫進雲端的補回歷史。worker 在 ThreadPoolExecutor
    # 執行緒內取不到 session_state,故 client 必須由主執行緒先取好再傳(拿不到 → None → 退 SA/空)。
    _oauth = None
    try:
        from ui.helpers.io.oauth_state import _get_oauth_client
        _oauth = _get_oauth_client()
    except Exception:  # noqa: BLE001 — 未登入 / 建置失敗 → None
        _oauth = None
    prog = st.progress(0.0, text="📥 並行抓取資料中…")
    _results: list = [None] * n
    _workers = min(n, 4)
    try:
        with ThreadPoolExecutor(max_workers=_workers) as _ex:
            _futs = {
                _ex.submit(process_one_fund, _c, principal_twd, ccy_hint, warn_gap,
                           None, _name_map.get(str(_c).upper(), ""),
                           oauth_client=_oauth): _i
                for _i, _c in enumerate(codes)
            }
            _done = 0
            for _fut in as_completed(_futs):
                _i = _futs[_fut]
                try:
                    _results[_i] = _fut.result()
                except Exception as e:
                    _results[_i] = {"code": codes[_i], "ok": False,
                                    "error": f"{type(e).__name__}: {e}"}
                _done += 1
                prog.progress(_done / n, text=f"📥 已完成 {_done}/{n} 檔…")
    finally:
        prog.empty()
    # 防呆：任一 slot 未填（理論上不會）→ 補錯誤列
    return [(_r if _r is not None
             else {"code": codes[_idx], "ok": False, "error": "未取得結果"})
            for _idx, _r in enumerate(_results)]


def _render_mj_freshness_banner(ok_rows: list[dict]) -> None:
    """v19.62 E3：改 call 共用 helper（向後相容包裝；原 60 行邏輯抽至 ui/helpers/freshness）。"""
    from ui.helpers.freshness import render_mj_freshness_banner
    _items = [
        {"code": _r.get("code", "?"), "name": _r.get("基金名", ""),
         "nav_date": _r.get("_nav_date", ""), "fetched_at": _r.get("_fetched_at", "")}
        for _r in ok_rows
    ]
    render_mj_freshness_banner(_items)


def _eats_principal_flag(fd: dict) -> "bool | None":
    """v19.347：從 吃本金 verdict 取乾淨布林（True=吃本金 / False=不吃 / None=未知）。

    走 `dividend_safety` 的 `alert_level`（red/yellow/green/grey）語意欄位,
    不解析 emoji：red→吃本金；green/yellow→不吃（黃=margin 薄但未吃）；其餘→未知。
    """
    try:
        from services.health.dividend import check_eating_principal_1y_mk
        _v = check_eating_principal_1y_mk(fd)
        if isinstance(_v, dict):
            _lvl = _v.get("alert_level")
            if _lvl == "red":
                return True
            if _lvl in ("green", "yellow"):
                return False
    except Exception:
        pass
    return None


def _render_low_base_screener(ok_rows: list[dict]) -> None:
    """🎯 選基金（低基期進場點）。

    在「已載入的基金」裡找進場候選：σ rank ≤ 買點門檻（低基期）且不吃本金，
    可依幣別/類別篩。**重用組合健診已抓的 NAV**，不新增外部抓取。
    L3 render；篩選邏輯全在 `services.fund_screening`（L2 純函式）。

    2026-08-07 user 拍板「低基期全站統一用 HWM σ rank」後本區的三個變化：
      1. σ 改**負數**（σ rank，愈負愈低基期），不再是舊的「低幾σ」正數深度；
      2. σ 倍數選擇器（1 / 2σ）拿掉 —— 門檻走 `ROTATION_BUY_SIGMA` SSOT。
         使用者仍看得到每檔的 σ rank 數值與 4 級 HWM 位階，資訊沒有變少，
         少的只是「在 UI 裡另外寫一組門檻數字」的機會（§3.3 / §8.1 step 6）；
      3. 回看期選擇器（1/2/3 年）拿掉 —— σ_abs 隨 √n 縮放，換窗口就換一把尺，
         留著等於把剛消滅的分歧原樣搬回來。窗口固定 = 大表口徑。
    """
    from services.fund_screening import (  # L2 純函式
        LOW_BASE_MIN_POINTS,
        screen_funds,
    )

    # 1) 由已載入 row 的 _fund_raw 組 items（series/幣別/類別 + 吃本金布林）
    items = []
    for _r in ok_rows:
        fd = _r.get("_fund_raw") or {}
        _mj = fd.get("moneydj_raw") or {}
        items.append({
            "code": _r.get("code", ""),
            "name": (fd.get("fund_name") or _r.get("基金名") or "")[:24],
            "series": fd.get("series"),
            "currency": (fd.get("currency") or _r.get("ccy") or "").strip().upper(),
            "category": (_mj.get("category") or fd.get("category") or "").strip(),
            "eats_principal": _eats_principal_flag(fd),
        })

    from shared.signal_thresholds import ROTATION_BUY_SIGMA, ROTATION_SELL_SIGMA

    st.markdown("#### 🎯 選基金（低基期進場點 · HWM σ rank）")
    st.caption(
        f"在已載入的基金裡，找 **σ rank ≤ {ROTATION_BUY_SIGMA:+.1f}σ**（現價落在期間"
        "高點下方那麼多個 σ）且不吃本金的**進場候選**。σ rank 是**負數**，"
        "**愈負 = 離高點愈深 = 基期愈低**。"
    )
    # 門檻走 shared/signal_thresholds SSOT;caption 只講「同一把尺」,不對使用者報檔名。
    st.caption(
        f"✅ **與健診大表「基期」欄用同一把尺**：同一套算法、同一組門檻"
        f"（買點 {ROTATION_BUY_SIGMA:+.1f}σ / 賣點 {ROTATION_SELL_SIGMA:+.1f}σ）、"
        "同一段回看期間。本區標 🟢 低基期的，大表「基期」欄一定也是 🟢。"
    )

    # σ 倍數 / 回看期兩個 radio 已移除（見 docstring 2、3）→ 這裡只剩維度濾鏡，
    # 不再需要三欄排版。
    _all_ccy = sorted({it["currency"] for it in items if it["currency"]})
    _all_cat = sorted({it["category"] for it in items if it["category"]})
    # ── 篩選條件包進 form(2026-09-02 T3;拍板線框 Rule 02)───────────────────
    # 這四個控制項原本是**裸 widget**:動一個就觸發整頁 rerun,而本頁的 rerun 會把
    # `_run_batch_health()`(逐檔 MoneyDJ / FundClear 取數)整輪重跑一次。四個控制項
    # 各撥一下 = 四輪。包進 form 之後,值只在按「套用」時提交一次。
    # ⚠️ 篩選本身(`screen_funds`)是 L2 純函式、很便宜 —— 這裡省的**不是它**,
    #    是它上游那一整輪頁面重跑。
    # ⚠️ 這裡**刻意不接 gate 的回傳值**,與上方主表單不同,理由據實寫下來:
    #    `gated_form` 的 docstring 提醒「回傳值沒被拿去 gate 運算 = 假 form」——
    #    那條提醒針對的是**貴的重運算**。本區被 gate 的候選只有 `screen_funds`
    #    (L2 純函式、輸入已在記憶體、零 I/O)。若拿 gate 去擋它,使用者第一次看到的
    #    會是一張空區塊、非得先按一次「套用」才有東西 —— 那是把便宜的東西擋掉、
    #    換來一個多餘的點擊。真正貴的那一輪(整頁 rerun → `_run_batch_health`)
    #    **已經被 form 本身擋住了**(form 內的 widget 互動不觸發 rerun)。
    from ui.helpers.ia import applied_form as _applied_form  # noqa: PLC0415
    with _applied_form("lb_screener_filters"):
        _sel_ccy = st.multiselect("幣別（外幣/台幣）", _all_ccy, default=_all_ccy, key="lb_ccy")
        _sel_cat = st.multiselect("基金類別", _all_cat, default=_all_cat, key="lb_cat")
        _cc1, _cc2 = st.columns(2)
        _only_eat = _cc1.checkbox("只留不吃本金（綠/黃燈）", value=True, key="lb_noeat")
        _only_low = _cc2.checkbox("只留低基期", value=True, key="lb_onlylow")

    # 2) L2 純函式篩選（多選清空 → None = 不篩該維度，避免空表困惑）
    #    lookback / 門檻一律走 L2 預設 = SSOT，UI 不再持有第二組數字（§3.3）。
    rows = screen_funds(
        items,
        only_low_base=_only_low, only_no_eat=_only_eat,
        currencies=(set(_sel_ccy) or None),
        categories=(set(_sel_cat) or None),
    )
    if not rows:
        st.info("目前沒有符合條件的基金——可取消『只留低基期』看全部基期分布，"
                "或放寬幣別 / 類別篩選。")
        return

    import pandas as pd
    from streamlit import column_config as _cc
    _eat_map = {True: "🔴 吃本金", False: "🟢 不吃", None: "❓ 未知"}
    # 與健診大表的「基期」欄**同一份**標籤(2026-09-02 T29 起走 SSOT,不再手抄)。
    # 下方 caption 宣稱「本區標 🟢 低基期的,大表『基期』欄一定也是 🟢」——
    # 那句話的前提就是這兩處用同一組字;靠手抄的話,改一邊就會讓那句宣稱變成假的。
    from ui.helpers.fund_grp_health._utils import BASE_LABELS as _base_map
    _df = pd.DataFrame([{
        "代號": r["code"], "基金名": r["name"],
        "類別": r["category"] or "—", "幣別": r["currency"] or "—",
        "現價": r["current"], "期間高點(HWM)": r["hwm"],
        "距 HWM %": r["dist_to_hwm_pct"],
        "σ rank": r["sigma_rank"],
        f"買點門檻({ROTATION_BUY_SIGMA:+.1f}σ)": r["buy_threshold_nav"],
        "基期": _base_map.get(r["base"], "⬜ 資料不足"),
        "HWM 位階": r["hwm_label"],
        "吃本金": _eat_map.get(r["eats_principal"], "❓ 未知"),
        "樣本數": r["n_points"],
        "可信度": "✅" if r["reliable"] else "⚠️ 低",
    } for r in rows])
    st.dataframe(
        _df, use_container_width=True, hide_index=True,
        column_config={
            "現價": _cc.NumberColumn(format="%.2f"),
            "期間高點(HWM)": _cc.NumberColumn(format="%.2f"),
            "距 HWM %": _cc.NumberColumn(format="%+.2f%%"),
            "σ rank": _cc.NumberColumn(
                format="%+.2f σ",
                help="負數；愈負 = 現價離期間高點愈深 = 基期愈低。"),
            f"買點門檻({ROTATION_BUY_SIGMA:+.1f}σ)": _cc.NumberColumn(format="%.2f"),
        },
    )
    st.caption(
        f"共 {len(rows)} 檔（依 σ rank 由**負到正**排序 = 跌最深的排最上面）。"
        "停售、或淨值完全不動的基金算不出位階，標『⬜ 資料不足』並**排除在低基期候選之外**，"
        f"不會被推薦（缺資料就誠實說缺，不硬給建議）；"
        f"可用的淨值筆數少於 {LOW_BASE_MIN_POINTS} 筆會標『可信度低』。"
    )
    st.download_button(
        "⬇️ 下載選基金清單 CSV", _df.to_csv(index=False).encode("utf-8-sig"),
        "low_base_funds.csv", "text/csv", key="lb_dl",
    )


# ── 🧭 配置檢查 caption「加權方式」措辭 SSOT ──────────────────────────
# §1 Fail Loud, Never Fake:原 caption 寫死「依各檔投入本金加權」,但健診 Tab 只有
# **單一本金欄位**(`principal_twd`)broadcast 給全部基金 → 每檔 weight 相同 → 實際是
# **等權**(≈ 檔數佔比)。持有 90 萬核心 + 10 萬衛星會被顯示成「核心 50% / 衛星 50%」,
# 且總計金額 = 本金 × 檔數,配置評估燈號完全失真。組合 Tab3 傳各檔 invest_twd 才是真
# 金額加權,但 user 全未填時也會退成等權 —— 故加權方式**不可由 caller 自稱**,一律讀
# L2 `summarize_core_satellite_allocation()` 依實際權重推斷的 `weight_mode` 照實說。
# ⚠️ 本輪只修「說法」,不改等權行為本身(健診 Tab 逐檔金額輸入屬 UX 變更,需 user 拍板)。
#
# ⚠️ equal 措辭的第二層誠實性(2026-08-04 QA 條件 4):原版在 equal 尾巴接了兩句 ——
# 一句否定金額加權的因果宣稱，一句叫 user 去「組合配置」Tab 逐檔填金額。這在
# 「user 已在 Tab3 逐檔填完、只是每檔金額恰好相同(平均配置是常見策略)」時**兩句都假**：
#   (1) 否定金額加權 → 錯：它就是金額加權，只是金額相同 = 修掉一個謊又種一個(§1)。
#   (2) 叫他去填 → 對已填完的 user 下錯誤指示；且本 render 被 Tab3 共用，
#       在 Tab3 渲染時等於叫 user 去他當下所在的地方。
# → equal 只留數學上恆真的那半（金額相同 ⟹ 比例 = 檔數佔比，與 caller 是誰無關）；
#   「去填金額」導引拆成 `_EQUAL_MODE_HEALTH_TAB_HINT`，僅健診 Tab 分支才接。
_WEIGHT_MODE_NOTE: dict[str, str] = {
    "amount": "依各檔投入本金加權，總計 {total:,.0f} TWD",
    "equal": "⚠️ 各檔投入金額相同（每檔 {per:,.0f} TWD × {n} 檔）→ 上列比例等同**檔數佔比**",
    "single": "僅 1 檔（{total:,.0f} TWD），加權方式不影響比例",
    "none": "無有效投入金額，無法計算比例",
}

# 只在健診 Tab 成立的補充導引:健診 Tab 只有**單一本金欄位**(`principal_twd` broadcast
# 給全部基金)，結構上不可能逐檔填 → 指向 Tab3 是正確且唯一的出路。Tab3 自己渲染時
# **不得**印此句(user 已在該 Tab，且他可能只是各檔金額恰好相同)。
# ⚠️ 2026-08-31 WP-F 修正（**有意識的政策變更，不是漏改** · 決策者：AI 總管）。
# 舊寫法 ~~「組合配置」Tab~~ 的理由**仍然成立**：健診只有單一本金欄位，結構上不可能
# 逐檔填，指向 ④ 是正確且唯一的出路 —— 這個**指路方向**沒有錯。
# 被權衡掉的是那個**名字**：④ 在七→五之前叫「📊 配置 & 帳本」、之後叫「📊 我的配置」，
# **兩個時期都沒有**一個叫「組合配置」的分頁。
# ⚠️ **歸因**：這不是七→五打壞的，它在 main 上就已經指向一個不存在的名字（既有債）。
# 因為它從來沒進過 `_TAB_LABELS`，任何「比對歷史分頁名」的守衛都掃不到它 ——
# 這正是本批把守衛加上「形態向」那一條的理由。
_EQUAL_MODE_HEALTH_TAB_HINT = (
    f"；本 Tab 只有單一本金欄位，要依實際金額配置請到「{_tab_label('portfolio')}」"
    "逐檔填投入金額"
)


def _weight_basis_note(csa: dict, source_tab: str | None = None) -> str:
    """把 L2 `weight_mode` 轉成給 user 看的加權方式說明（純函式，可單元測試）。

    未知 / 缺 `weight_mode` → 退 "none" 措辭（不猜、不宣稱金額加權，§1）。

    Args:
        source_tab: 呼叫端身分。僅 `"health"`（💊 基金組合健診 Tab）會在 equal 措辭
            後接「去 Tab3 逐檔填金額」導引 —— 其餘 caller（Tab3 embed / 未宣告）一律
            不接，避免對「已逐檔填完、只是金額相同」的 user 下錯誤指示。
    """
    _mode = str(csa.get("weight_mode") or "none")
    _tmpl = _WEIGHT_MODE_NOTE.get(_mode, _WEIGHT_MODE_NOTE["none"])
    _total = float(csa.get("total_weight") or 0.0)
    _n = (int(csa.get("n_core") or 0) + int(csa.get("n_satellite") or 0)
          + int(csa.get("n_undetermined") or 0))
    _per = (_total / _n) if _n else 0.0
    _note = _tmpl.format(total=_total, per=_per, n=_n)
    if _mode == "equal" and source_tab == "health":
        _note += _EQUAL_MODE_HEALTH_TAB_HINT
    return _note


# ── 🧭 配置檢查「這是哪一把尺」措辭 SSOT ────────────────────────────────
# 2026-08-06 稽核 🔴 必修 3：Tab3「組合配置」同一次捲動內會出現**兩個核心%**，
# 而且結論方向相反（上方「核心 90%、目標 75% → 核心過重可減」vs 下方「核心 40%
# < 50% → 衛星過重要加」）。三項口徑全不同：
#
# 當時（=已修掉的舊狀態）三項口徑全不同：
#   |      | 上半頁（ui/tab3_portfolio.py hero / KPI）        | 本區（Tab3 embed）                       |
#   | 分母 | Σ invest_twd，未填本金者計 0                    | Σ _principal_twd，未填 / ≤0 補模擬本金    |
#   | 分類 | resolve_core_flag：policy_tier → is_core（二態）| classify_core_satellite：類別 + 3-3-3（三態）|
#   | 目標 | session portfolio_core_pct（⚙️ 組合設定 slider）| L2 的建議核心區間（固定）                 |
#
# 分母那條尤其致命：只要有一檔沒填本金，兩個百分比在**數學上就不可能相等**。
#
# 它們回答的其實是不同問題 —— 上方是「這筆錢的配置定位」（使用者自己在 Google
# Sheet 標的），本區是「這檔基金的資產屬性」（系統依 MoneyDJ 類別 + 3-3-3 判的）。
# 兩者都有價值，**合併成單一分類器是架構決策**（§8.1），user 裁決是不合併、但降級。
#
# 現況（2026-08-07 後）：分母兩邊都只計實際填過的本金（模擬本金 weight=0 擋掉），
# 目標值本區已無，只剩「分類依據」一項差異 —— 那一項正是兩區各自的存在理由。
#
# 2026-08-07 user 拍板（本輪把上一輪只做在 Tab3 的降級推到**兩個 Tab**）：
#   「你在 Sheet 標的級別是唯一真相。健診那份（依基金屬性判定）降為純資訊，
#     不再給『核心不足 / 過重』的配置建議。」
# 上一輪只在 Tab3 embed 降級，健診 Tab 仍照輸出 L2 的行動建議 —— 那等於同一套
# 屬性分類器在 A 頁是「建議」、在 B 頁是「參考」，使用者換個 Tab 就換一套結論。
# 現在無論哪個 caller，這一區一律只陳述比例 + 指向唯一有行動建議的那一格。
# 連帶把 L2 的建議核心區間常數整組移除（見 services/health/asset_class.py），
# 因為只要那組目標還在，下一個人就會再把它接回畫面。
_CS_RULER_NOTE = (
    "📏 **本表這一欄的尺**：核心 / 衛星依**基金本身的資產屬性**判定"
    "（MoneyDJ 基金類別關鍵字 +  3-3-3；判不出來的誠實留「待定」，不硬塞），"
    "是系統推的，**不是**你在 Google Sheet 標的 `policy_tier`。"
    "本表**不設**建議核心佔比、也不評價你的配置 —— 它只回答「我手上這幾檔，"
    "本質上偏穩健還是偏主題」。"
)

_CS_PORTFOLIO_CONTRAST_NOTE = (
    "⚖️ **本區與本頁上方的「🛡️ 核心資產比例」不是同一把尺，數字不一樣是正常的**：\n"
    "1. **分類依據** — 上方用你在 Google Sheet 標的 `policy_tier`（缺才退基金名稱"
    "關鍵字），只有核心 / 衛星兩態；本區用 MoneyDJ 基金類別 +  3-3-3，多一個「待定」。\n"
    "2. **分母** — 兩邊都是 Σ 你實際填過的投入本金：**沒填本金的那幾檔兩邊都不進比例**"
    "（本區為了試算配息會給它們 100 萬 TWD 的模擬本金，但那個金額**不進**這裡的百分比）。\n"
    "3. **目標值** — 上方是「⚙️ 組合設定」的核心比例 slider；本區**沒有**目標值，不做達標判定。\n"
    "→ **要不要再平衡一律以上方那一處為準**；本區純資訊。"
)


def _core_satellite_ruler_note() -> str:
    """🧭 屬性分布的「這是哪一把尺」說明。

    本表已無任何門檻 / 目標值可帶（見上方註解），故為固定字串；保留函式形式是因為
    render 端與測試都以呼叫點接線，改成常數會讓接線測試失去著力點。
    """
    return _CS_RULER_NOTE


# 兩個 Tab 共用的唯讀措辭；差別只在「唯一有行動建議的那一格」在哪裡。
_CS_READONLY_TMPL = (
    "{status} 本表口徑下：核心 {core:.0f}% / 衛星 {sat:.0f}% / 待定 {und:.0f}%"
    "（依**基金資產屬性**判定）。**本區為唯讀對照、純資訊，不提供再平衡建議**"
    " —— 核心 / 衛星要不要調整，{where}"
)
_CS_WHERE_PORTFOLIO = (
    "看本頁上方「🛡️ 核心資產比例 / 目標偏差」那一格（那裡吃你在 Google Sheet "
    "標的 `policy_tier` + ⚙️ 組合設定的目標）。"
)
# ⚠️ 2026-08-31 WP-F 修正（同上一處：舊寫法 ~~「組合配置」Tab~~ 是憑印象手寫、
# 兩個時期都不存在的名字；既有債，不是七→五打壞的）。
_CS_WHERE_HEALTH = (
    f"看「{_tab_label('portfolio')}」的「🛡️ 核心資產比例 / 目標偏差」那一格"
    "（那裡吃你在 Google Sheet 標的 `policy_tier`）—— "
    "本 Tab 只有代號與單一本金，讀不到你標的配置定位。"
)


def _core_satellite_items(health_rows: list, ok_rows: list) -> tuple:
    """把 (① 健康分析 row, 健診 row) 配對成 L2 需要的 `[{label, weight}]`（純函式）。

    回傳 `(items, n_simulated_principal)`。

    ⚠️ **模擬本金不進配置比例**（2026-08-07 user 裁決第 4 點）：
    呼叫端（`ui/tab3_portfolio.py` 持倉健診）對「使用者從未填過 `invest_twd`」的
    基金會補一筆 100 萬 TWD，好讓逐檔配息試算算得出「每月配息 TWD」——
    那個金額**是模擬值**，不是他的錢。若讓它進百分比分母：
      (a) 一檔沒填就能把屬性比例整個帶偏；
      (b) 混合情況下 `weight_mode` 會推斷成 "amount"，caption 於是會宣稱這是依各檔
          實際金額算出來的、並印出一個含模擬金額的總計 —— 用捏造的數字背書一句
          假陳述（§1）。
    故這裡一律傳 weight=0；L2 `summarize_core_satellite_allocation` 對 weight ≤ 0
    的項目直接略過（不計分母、不參與加權方式推斷）。

    健診 Tab 走的是使用者自己輸入的單一本金 broadcast，**不帶**這個旗標，
    行為與過去完全相同（全等權，caption 照 `weight_mode` 說是等權）。
    """
    items: list = []
    n_sim = 0
    for _hr, _r in zip(health_rows or [], ok_rows or []):
        _lbl = ((_hr or {}).get("核心/衛星") or "").split()
        _is_sim = bool((_r or {}).get("_principal_is_default"))
        if _is_sim:
            n_sim += 1
        items.append({
            "label": _lbl[-1] if _lbl else "待定",
            "weight": 0 if _is_sim else ((_r or {}).get("_principal_twd") or 0),
        })
    return items, n_sim


def _core_satellite_verdict_caption(csa: dict,
                                    source_tab: str | None = None) -> str:
    """🧭 屬性分布的結論句（純函式，可單元測試）—— **兩個 Tab 都唯讀**。

    只陳述本表口徑下的三態比例，永遠不輸出「核心不足 / 衛星過重 / 偏保守」這類
    行動語氣。`source_tab` 現在只決定「唯一有行動建議的那一格在哪裡」的指路措辭
    （Tab3 embed → 本頁上方；健診 Tab → 「組合配置」Tab），不再決定給不給建議。

    分類涵蓋不足（待定佔比過高）時，把 L2 的 `coverage_note` 接出來 —— 那是**資料
    品質**陳述（「補上基金分類才讀得準」），不是配置建議，屬 §1 必須講的缺料揭露。
    """
    from services.health.asset_class import COVERAGE_UNRELIABLE

    _status = str(csa.get("status") or COVERAGE_UNRELIABLE)

    def _pct(key: str) -> float:
        try:
            return float(csa.get(key) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    _out = _CS_READONLY_TMPL.format(
        status=_status,
        core=_pct("core_pct"), sat=_pct("satellite_pct"),
        und=_pct("undetermined_pct"),
        where=(_CS_WHERE_HEALTH if source_tab == "health" else _CS_WHERE_PORTFOLIO),
    )
    if _status == COVERAGE_UNRELIABLE:
        _note = str(csa.get("coverage_note") or "").strip()
        if _note:
            _out += f"（⚠️ {_note}）"
    return _out


def _render_health_summary(rows: list[dict]) -> None:
    """5 格結論摘要（檢查檔數 / 健康 / 警示 / 吃本金 / 累積配息）＋ 前置的失敗摘要。

    2026-09-02 T20:本區塊原本住在 `_render_health_table` 裡,也就是**排在**
    核心/衛星分布、選基金、淘汰候選紅區、持倉互斥避險**之後**才出現 ——
    使用者要先捲過四個區塊才看得到「這次總共幾檔、幾檔在吃本金」。
    拍板線框 Tab 02 的順序是「Form → 組合健康總分 + 警示卡 → 逐檔體檢表」,
    也就是**結論先講**。抽成獨立函式後由 `_render_health_3tables` 在最前面呼叫。

    ⚠️ **失敗摘要與 5 格是一起搬的,不能只搬其中一半。**
    2026-08-05 稽核「必修 4」把「❌ 有 N 檔抓取失敗」刻意排在 KPI **正上方**,
    理由是「檢查檔數」只算成功數 —— 使用者看到「1」時必須當場知道另一檔怎麼了。
    只把 5 格搬到最上面、失敗摘要留在原地,等於把那個修正打回去。
    """
    ok_rows = [r for r in rows if r.get("ok")]
    err_rows = [r for r in rows if not r.get("ok")]
    if ok_rows:
        # v19.148:SSOT 統一改用 老師 1Y 標準(「吃本金燈號 (1Y · )」),
        # 與下方「健診摘要表」同源,不再與全期自算 verdict 不一致。
        _mk_col = "吃本金燈號 (1Y · )"
        n_eat = sum(1 for r in ok_rows if "吃本金" in str(r.get(_mk_col, "")))
        n_warn = sum(1 for r in ok_rows if ("警示" in str(r.get(_mk_col, ""))
                                            or "邊緣" in str(r.get(_mk_col, ""))))
        n_good = sum(1 for r in ok_rows if "健康" in str(r.get(_mk_col, "")))
        total_twd = sum(float(r.get("累積 TWD 配息 🧮", 0) or 0) for r in ok_rows)

        # 2026-08-05 稽核 🟡 必修 4:失敗摘要前置。
        # 原本「❌ 抓取失敗」區在本行之後 **226 行**(中間隔淘汰候選 / 48+ 欄健診大表 /
        # PK / 換標決策 / 景氣適配 / 相關性矩陣 / 比較圖 / 逐檔配息明細),而 KPI
        # 「檢查檔數」只算成功數 —— 輸入 2 檔只成功 1 檔時,畫面顯示「1」且完全不提
        # 另一檔怎麼了,要捲很久才看得到原因(§1 缺料必須當場講清楚)。
        # 下方「#### ❌ 抓取失敗」明細區保留不動,此處只做「先講一句」。
        if err_rows:
            st.error(
                f"❌ 有 {len(err_rows)} / {len(ok_rows) + len(err_rows)} 檔抓取失敗，"
                f"**未納入下方所有統計與表格**：\n\n"
                + "\n".join(
                    f"- **{r.get('code', '?')}**：{r.get('error', '?')}"
                    for r in err_rows
                )
            )

        k1, k2, k3, k4, k5 = st.columns(5)
        # delta 顯示本次少掉幾檔,讓「1」不再像是全部成功。
        # ⚠️ 這裡**刻意使用 Streamlit 預設的 normal 配色**(不傳 delta_color):
        #   normal(預設) → 負值紅、正值綠
        #   反轉模式     → 負值**綠**、正值紅   ← 那是給「成本下降是好事」用的
        # 抓取失敗是壞消息,必須是紅色。前一版誤用反轉模式,把「少掉一檔」渲染成
        # 綠色好消息,方向與本修正目的完全相反。
        # 📌 本註解**刻意不寫出反轉模式的參數字面值** ——
        #    `tests/test_grp_health_failure_summary.py::test_failed_delta_is_not_rendered_green`
        #    對整檔做子字串掃描,註解裡出現該字串等於自己讓自己紅
        #    (同 PROCESS.md §4「測試把錯誤制度化」的鄰近陷阱)。
        k1.metric("檢查檔數", len(ok_rows),
                  delta=(f"-{len(err_rows)}" if err_rows else None))
        k2.metric("🟢 健康", n_good)
        k3.metric("🟡 警示", n_warn)
        k4.metric("🔴 吃本金", n_eat)
        k5.metric("累積 TWD 配息 🧮", f"{total_twd:,.0f}")


def _render_health_3tables(rows: list[dict],
                           funds_extra: list | None = None,
                           show_screener: bool = False,
                           source_tab: str | None = None) -> None:
    """v19.181 3 表模組化渲染:① 健康分析 ② 配息相關 ③ 實際購買結果(既有 _render_health_table)。

    共用 SSOT row builder(`services.health.report`)讓 Tab3 也能同源渲染。
    每張表獨立 dataframe,user 可選關注的維度。

    Args:
        rows: process_one_fund 回傳的 row list
        funds_extra: v19.189 基金體檢 PK + 健診卡資料(透給 _render_health_table 用,
                     Tab3 caller 不傳則 None)
        source_tab: 呼叫端身分,目前只認 `"health"`(💊 基金組合健診 Tab)。用於決定
                    「等權 → 請去逐檔填金額」導引該不該印 —— 該句只在健診 Tab 成立
                    (該 Tab 結構上只有單一本金欄位);Tab3 embed **不傳**(預設 None),
                    因為 user 已在組合配置 Tab,且可能只是各檔金額恰好相同。
                    預設 None = 不印導引,既有 caller 零行為變化。
    """
    if not rows:
        return
    # v19.322 SSOT 去重(顯示層 chokepoint):健診 Tab + Tab3 embed 皆經此;同 code 多筆
    # (多保單持同檔)只留第一筆 → 持有 meta / 配息事件 / 比較圖三表不再重複列。
    rows = _dedup_rows_by_code(rows)
    from services.health.report import (
        build_dividend_summary_row,
        build_health_analysis_row,
    )

    ok_rows = [r for r in rows if r.get("ok")]
    if not ok_rows:
        # ══ D1 + D2(2026-08-28 批次三之一)══════════════════════════════
        # 全部抓取失敗時,本頁**十幾個區塊會無聲消失**。原本使用者只看得到最後面
        # 那段「#### ❌ 抓取失敗 + 逐檔紅字」—— 知道「抓失敗了」,但不知道
        # **因此少看到了什麼**,也就無從判斷「是這個功能沒了,還是這次沒資料」。
        #
        # 為什麼講在這裡(「因」的位置),而不是在每個下游區塊各講一次:
        #   `ok_rows` 空是**唯一的因**,它在這一行就已經確定;下游那些區塊全部被
        #   同一個條件關掉。在 10+ 個下游各印一句灰字 = 滿版灰字,那是客戶 2026-08-28
        #   Q1 第二句明確否掉的方向(「保持畫面極簡乾淨」)。**在因的位置講一次。**
        #
        # D2(線框 §04①「標題照印」):`#### 📊 健診大表` 這個標題原本**只**印在本
        # early-return 之後(本函式後段,`_health_by_code` 那一段的開頭)→ 全失敗時
        # 連標題都不出現,使用者看不到任何痕跡。把它提到守衛之前印,他至少看得到
        # 「這裡本來有一張表」+ 一句說明。
        # (刻意不寫行號:行號保證會過期,§8.2.A.0 規則 1。要定位就 grep 那個標題字串。)
        #
        # 顏色(render_state 五態):**全部抓取失敗是系統真失敗 → 🔴**,不是 ⬜
        # 「還沒載入」——用灰字印真失敗,使用者會以為「按一下就好」,但他按幾次都一樣
        # (render_state 檔頭點名的反向 bug)。
        # 刻意**不走 `system_error()`**:那個入口的簽名要求一個 BaseException,
        # 而這裡手上沒有 —— 每一檔的失敗原因是 `r["error"]` **字串**(由批次層攔下後
        # 存進 row),不是活的例外物件;硬造一個 Exception 只為了滿足簽名,traceback
        # 會是假的。此處改用 `st.error`,與 `_render_health_table` 內既有的「部分失敗」
        # 摘要**同一族寫法** —— 那一段長在 `if ok_rows:` 裡面,所以**全失敗時反而
        # 印不出來**,本段補的正是它漏掉的那一半。
        #
        # ⚠️ 下面這份清單是**量測值,量測日 2026-08-28,會漂移**(§8.2.A.0 規則 4)。
        # 重新產生(照抄可跑):
        #   $ python3 -c "import ast,pathlib;s=pathlib.Path('ui/tab_fund_grp_health.py').read_text();t=ast.parse(s);f=[n for n in ast.walk(t) if isinstance(n,ast.FunctionDef) and n.name in ('_render_health_3tables','_render_health_table')];print([ (c.lineno, ast.unparse(c.func), ast.unparse(c.args[0])[:40] if c.args else '') for n in f for c in ast.walk(n) if isinstance(c,ast.Call) and (ast.unparse(c.func) in ('st.markdown','st.subheader') and c.args and '###' in ast.unparse(c.args[0]) or ast.unparse(c.func).startswith(('render_','_render_')))])"
        st.markdown(_BIG_TABLE_HEADING)
        _gone = ["🧭 核心 / 衛星資產屬性分布"]
        if show_screener:
            _gone.append("🎯 選基金（低基期進場點）")
        _gone += [
            "🔴 淘汰候選紅區",
            "📊 健診大表**的表身**（含 4D Grade、σ 位階、買賣點）"
            "——標題上面還印著，但底下沒有表",
            "🩺 基金體檢 PK", "🔀 換標決策", "🧭 景氣位階適配",
            "📈 多基金績效比較圖", "📋 逐檔配息明細（含「持有 meta」與「配息事件」兩張表）",
            "5 格 KPI 摘要（檢查檔數 / 健康 / 警示 / 吃本金 / 累積配息）",
            "MoneyDJ 資料新鮮度 banner",
        ]
        # 逐檔原因**寫在這裡**(不只指向下方),沿用本檔 2026-08-05 稽核「必修 4:
        # 失敗摘要前置」的同一個理由 —— 使用者要先知道為什麼,再知道少了什麼。
        # ⚠️ 已知冗餘,據實登記:`_render_health_table()` 結尾的「#### ❌ 抓取失敗」
        # 會把同一份原因再印一次。修掉它要動 `_render_health_table` 的失敗區塊
        # (它同時服務「部分失敗」路徑),不在本批範圍(§8.4 step 4);
        # 而且「部分失敗」路徑本來就是同樣的前置+詳列兩段式,此處與它一致。
        st.error(
            f"❌ 這次輸入的 {len(rows)} 檔**全部抓取失敗**：\n\n"
            + "\n".join(f"- **{r.get('code', '?')}**：{r.get('error', '?')}"
                        for r in rows)
            + "\n\n因此本頁以下區塊**本次都不會出現**"
              "（是這次沒抓到資料，不是功能被拿掉）：\n\n"
            + "\n".join(f"- {_g}" for _g in _gone)
        )
        _render_health_table(rows, funds_extra=funds_extra)
        return

    # ── 5 格結論摘要(＋前置失敗摘要)── 2026-09-02 T20:結論先講 ──────────────
    # 拍板線框 Tab 02 的順序是「Form → 總分/警示 → 逐檔體檢表」。原本這一塊住在
    # `_render_health_table` 內,要捲過核心/衛星、選基金、淘汰紅區、持倉互斥四個區塊
    # 才看得到。搬上來之後它是這一頁 ok 路徑的**第一個**輸出。
    _render_health_summary(rows)

    # v19.330:① 健康分析 rows 提前建(核心/衛星 label 來源)—— 供「配置檢查」+ ① 表共用,不重算。
    # Layer 3-C:健康度第 5 維(匯率風險)需要匯率資料。**全站同一份**(L2 fetch-once),
    # 否則同一檔基金在這裡是 5/5 的 B、在個基深掘卻是 4/5 的 C(§2.1 跨畫面一致)。
    from services.fx_regime_service import fx_regime_by_ccy as _fxr_gh
    _fx_map_gh = _fxr_gh() or {}
    _health_rows = [
        build_health_analysis_row(_r.get("_fund_raw") or {}, _r.get("code", ""),
                                  fx_cv_by_ccy=_fx_map_gh)
        for _r in ok_rows
    ]

    # ── 🧭 核心/衛星「資產屬性分布」── v19.330 起兩 tab 共用最上方 ──
    # 健檢 Tab 全檔同一本金 = 等權(≈ 檔數佔比);組合 Tab3 為各檔實際 invest_twd 加權
    # (但各檔皆未填時亦退等權)。→ caption 的加權方式走 `_weight_basis_note(...)`
    # 讀 L2 `weight_mode` 照實說,**禁止寫死**「依各檔投入本金加權」(§1)。
    # source_tab 現在只決定兩件事:(1)「等權 → 去 Tab3 填金額」導引印不印;
    # (2) 指路句要指向哪一格。**給不給行動建議已不再是選項** —— 兩個 Tab 一律唯讀
    # (見 `_core_satellite_verdict_caption` 上方註解的 2026-08-07 拍板)。
    try:
        from services.health.asset_class import summarize_core_satellite_allocation
        # label × weight 配對 + 模擬本金剔除全在 `_core_satellite_items`(純函式,
        # 可單元測試);本 render 只負責畫。
        _cs_items, _n_sim_princ = _core_satellite_items(_health_rows, ok_rows)
        _csa = summarize_core_satellite_allocation(_cs_items)
        st.markdown("#### 🧭 核心 / 衛星資產屬性分布（純資訊，不評價配置）")
        # 先講「這是哪一把尺」再給數字 —— 兩個 Tab 都印（見上方 _CS_RULER_NOTE）。
        st.caption(_core_satellite_ruler_note())
        _ca1, _ca2, _ca3, _ca4 = st.columns(4)
        _ca1.metric("🟦 核心", f"{_csa['core_pct']:.0f}%", f"{_csa['n_core']} 檔")
        _ca2.metric("🟠 衛星", f"{_csa['satellite_pct']:.0f}%", f"{_csa['n_satellite']} 檔")
        _ca3.metric("⬜ 待定", f"{_csa['undetermined_pct']:.0f}%", f"{_csa['n_undetermined']} 檔")
        _ca4.metric("分類涵蓋度", _csa["status"],
                    help="只回答「待定佔比是否低到讓上列比例讀得準」，"
                         "**不是**配置好壞評價 —— 本表不評價配置。")
        st.caption(
            f"{_core_satellite_verdict_caption(_csa, source_tab)}"
            f"（{_weight_basis_note(_csa, source_tab)}；"
            f"核心=穩健長線 / 衛星=主題追報酬 / 待定=分類不足）"
        )
        if _n_sim_princ:
            st.caption(
                f"ℹ️ 另有 **{_n_sim_princ} 檔未填投入本金**，系統給了模擬本金以便"
                "試算配息，但**未計入上列比例分母**（捏造的金額不進百分比）。"
            )
        # Tab3「組合配置」embed：同一頁上方另有一個分類依據不同的核心%，
        # 不講清楚差在哪，兩個數字會被讀成「其中一個算錯了」。
        if source_tab != "health":
            st.caption(_CS_PORTFOLIO_CONTRAST_NOTE)
    except Exception as _e_csa:
        system_error("核心/衛星資產屬性分布計算失敗", _e_csa)

    # ── 🎯 選基金（低基期進場點）── v19.347：僅健檢 Tab 顯示(show_screener),
    #    Tab3 持倉健診不放(避免互動 widget key 與健檢 Tab 撞 + §8.1 不過度設計)。
    if show_screener:
        try:
            _render_low_base_screener(ok_rows)
        except Exception as _e_lb:
            system_error("選基金（低基期）渲染失敗", _e_lb)

    # ── 🔴 淘汰候選紅區( 4 規則 verdict=replace)── v19.315:提到最上面,一眼看見要換的 ──
    # 先建 ② 配息 rows(內含 _verdict),紅區與下方表 ② 共用同一份、不重算(SSOT,避免雙倍計算)。
    _div_rows = [
        build_dividend_summary_row(_r.get("_fund_raw") or {}, _r.get("code", ""),
                                   principal_twd=_r.get("_principal_twd"),
                                   fx=_r.get("fx_spot"))
        for _r in ok_rows
    ]
    _replace = [r for r in _div_rows if r.get("_verdict") == "replace"]
    if _replace:
        # 2026-08-28 客戶拍板:業務紅燈 ≠ 系統紅燈(線框 §03)。
        # 這一塊是**分析成功了**、答案是「這幾檔該換」—— 那是成果,不是故障。
        # 原本用 st.error,和「系統崩潰」共用同一個紅框:使用者無法從顏色分辨
        # 「系統壞了、別信畫面上的數字」還是「數字可信、去換基金」——
        # 兩者要他做的事**完全相反**。改為紅字卡片(紅色留著,錯誤框拿掉)。
        business_alert(
            f"🔴 淘汰候選 {len(_replace)} 檔（4 規則觸發，建議換標的）",
            [f"• <b>{r.get('code', '')}</b> "
             f"{str(r.get('基金名', '') or '')[:20]}："
             f"{r.get('_換標的 detail', '') or r.get('換標的建議', '')}"
             for r in _replace],
            footer="↓ 完整指標見下方健診大表。",
        )

    # ── 🛡️ 持倉互斥避險(元件 A)── 2026-08-31 客戶拍板 Q1:緊接「結論摘要」
    # (淘汰候選紅區)之後、健診大表之前 ——「哪幾檔在吃本金」與「哪幾對會一起跌」
    # 是同一層級的行動答案。完整相關性矩陣**不搬家**,仍在下方 🔬 進階分析。
    # 僅 ② 健診 Tab(source_tab == "health"):Q1 拍板的是 ② 組合健診頁;
    # Tab3 持倉健診 embed 不在拍板範圍,版面異動未經草稿不夾帶(§-1.5 v3 §03-2 ①)。
    # funds_extra 缺(進階資料建構失敗)→ 不渲染:上游已有 system_error 講因,
    # 這裡不再各印一句(「在因的位置講一次」,同本檔 D1 慣例)。
    if source_tab == "health" and funds_extra:
        try:
            from ui.components.mutual_exclusion import (
                render_mutual_exclusion_section,
            )
            render_mutual_exclusion_section(funds_extra)
        except Exception as _e_me:  # noqa: BLE001 — 區塊隔離,失敗不擋健診大表
            system_error("持倉互斥避險區塊渲染失敗", _e_me)

    # v19.411:①② 表不再單獨渲染,欄位已併入「健診大表」。
    # 2026-08-06 必修 4:原本 90 行 inline dict 抽至
    # `ui/helpers/fund_grp_health/columns.py`,讓**批次大表(Tab③)沿用同一份設定**
    # —— 兩張表欄位相同卻只有一張有 help/寬度,是原則 2(重複)與原則 4(多做說明)雙違。
    from ui.helpers.fund_grp_health.columns import (
        dividend_column_config,
        health_column_config,
    )
    _health_cfg = health_column_config()
    _div_cfg = dividend_column_config()

    # ── 📊 健診大表(①②③ + σ/風險/去重複合併成一張)── v19.411 ──
    # 2026-09-02 T19:標題與說明**不在這裡印** —— 它們已合併成單一標題,由
    # `_render_health_table` 在**緊貼 dataframe 的位置**印出(見 `_BIG_TABLE_HEADING`)。
    # 原本印在這裡的話,標題與表身中間會隔著新鮮度 banner、失敗摘要、KPI 與體檢 PK。
    # ①② by-code 資料 + σ/風險/,全部傳給 _render_health_table 併成一張大表。
    _health_by_code = {str(r.get("code")): r for r in _health_rows if r.get("code")}
    _div_by_code = {str(r.get("code")): {k: v for k, v in r.items() if not str(k).startswith("_")}
                    for r in _div_rows if r.get("code")}
    _extra_by_code: dict = {}
    if funds_extra:
        try:
            from ui.helpers.fund_grp_health.unified import build_merged_extra_columns
            _pi3 = st.session_state.get("phase_info") if hasattr(st, "session_state") else None
            _, _extra_by_code = build_merged_extra_columns(
                funds_extra, (_pi3 or {}).get("phase") or "", (_pi3 or {}).get("score"))
        except Exception as _e_extra:  # noqa: BLE001 — σ/風險/併入失敗不擋大表
            # §1:原本靜默 → 大表整組 σ/HWM//捕捉/換標約 20 欄一次消失,
            # `build_unified_health_df` 的「來源整組沒供資料就不出現該批欄」設計會讓
            # 畫面看起來「本來就沒這些欄」,user 以為功能被拿掉。改為 log + 當場說明。
            _extra_by_code = {}
            system_error("σ 位階 / 風險 / 買賣點 / 捕捉率 / 換標欄整組計算失敗", _e_extra,
                         hint="本次健診大表不含這幾欄 —— 是算不出來,不是這些基金沒有資料。")
    # ⚠️ funds_extra **必須透傳**(2026-09-02 T4)。原本這裡寫死 `funds_extra=None`,
    # 而 `_render_health_table` 內「🩺 基金體檢 PK + 4 大健診卡」整段長在
    # `if funds_extra:` 裡面 → **production 路徑恆不觸發,該區塊從來沒有畫出來過**。
    # 另一個呼叫點(全失敗 early-return)雖然有傳 funds_extra,但那條路 `ok_rows` 為空、
    # 走不到 `if ok_rows:` 區塊 —— 兩條路加起來就是「這個功能對使用者不存在」。
    # 而畫面文案(全失敗時的 `_gone` 清單列著「🩺 基金體檢 PK」)、本檔上方註解
    # (「v19.189：基金體檢 PK + 4 大健診卡已上移至健診總表之前」)、以及拍板線框
    # 都說它在這裡 —— **三處都在描述一個不存在的畫面**。
    # 舊守衛 `tests/test_grp_health_checkup_order.py` 用的是子字串比對
    # (`"_render_health_table(rows, funds_extra=" in src`),而 `funds_extra=None`
    # **正好命中那個子字串** → 守衛全綠、功能全無。新的可達性守衛見
    # `tests/test_grp_health_checkup_reachable.py`(實跑本函式、看真正收到的引數)。
    _render_health_table(rows, funds_extra=funds_extra,
                         health_by_code=_health_by_code,
                         div_by_code=_div_by_code,
                         extra_by_code=_extra_by_code,
                         extra_cfg={**_health_cfg, **_div_cfg})


def _render_health_table(rows: list[dict], funds_extra: list | None = None, *,
                         health_by_code: dict | None = None,
                         div_by_code: dict | None = None,
                         extra_by_code: dict | None = None,
                         extra_cfg: dict | None = None) -> None:
    if not rows:
        return
    import pandas as pd

    ok_rows = [r for r in rows if r.get("ok")]
    err_rows = [r for r in rows if not r.get("ok")]

    if ok_rows:
        # v19.61 E1：MoneyDJ 資料新鮮度 banner（NAV 日期 / 抓取於 / 延遲天數 / 燈號）
        # 鏡像 Stock v18.201 D2 「FinMind last_update」設計，但 Fund 端用 banner 而非 hover
        _render_mj_freshness_banner(ok_rows)

        df = pd.DataFrame([
            {k: v for k, v in r.items() if not k.startswith("_")}
            for r in ok_rows
        ])
        # v19.411:① 健康分析 + ② 配息相關 + ③ 本表 + σ/風險/「去重複合併」成一張大表
        # (user 2026-07-27 要求)。原 ①② 分散表移除,一律併入本表。相關性矩陣 / 真實收益圖 /
        # Bollinger / 持股維持獨立。缺欄留 None(§1 不偽造)。
        if health_by_code or div_by_code or extra_by_code:
            try:
                from ui.helpers.fund_grp_health.unified import build_unified_health_df
                _regime = (st.session_state.get("phase_info") or {}).get("phase") \
                    if hasattr(st, "session_state") else None       # v19.425 當前景氣位階
                df = build_unified_health_df(
                    df, health_by_code or {}, div_by_code or {}, extra_by_code or {},
                    current_regime=_regime)
            except Exception as _e_merge:  # noqa: BLE001 — 合併失敗不擋健診總表
                # 與 :909 同型:失敗時大表會**靜靜少掉數十欄**,而不是整張消失
                # → 使用者看到的是一張「看起來完整」的窄表(2026-08-28 稽核 B3 補 hint)。
                system_error("①②③ 合併大表失敗", _e_merge,
                             hint="下方健診總表會少掉①②③合併進來的數十個欄位 —— "
                                  "是併不進去,不是這些基金沒有那些資料。")
        # 2026-08-05 稽核 🟢 選作 6:本批 Sharpe 來源全同 → 該欄逐列重複、零資訊量,
        # 由 df 收合成表下一行 caption(§2.2 揭露不減少,只是從 48 欄裡挪出來講一次)。
        df, _sharpe_src_uniform = _fold_uniform_sharpe_source(df)
        # v19.189：逐檔財務健診（4 大功能 + 健診摘要表 PK + 健診卡）插在健診總表上方。
        # user 要求易讀的摘要 PK + 健診卡先看到（原在下方「進階分析」區塊）。
        if funds_extra:
            try:
                from ui.helpers.fund_checkup import render_fund_checkup
                # expanded=True：上移到健診總表之上後直接展開，避免 user 以為「沒有」。
                render_fund_checkup(funds_extra, expanded=True)
            except Exception as _e_chk:
                system_error("基金體檢 PK 表渲染失敗", _e_chk)

        # 2026-09-02 T19:單一標題(原「📊 健診大表」+「健診總表（🧮 = 自行換算欄位）」兩句)。
        st.markdown(_BIG_TABLE_HEADING)
        st.caption("原「① 健康分析 / ② 配息相關 / ③ 實際購買結果」三表已合併去重複。"
                   "評分(4D Grade)/ 每月配息 / σ 位階 / 買賣點皆在此一張表內。")
        # v19.180:全期實際 / 年化兩軸並陳。短歷史也顯示真實累計值,不再 None。
        st.caption(
            "🩺 **吃本金燈號 (1Y · )** 採老師的體檢邏輯:"
            "**近一年含息報酬 < 年化配息率 → 🔴 吃本金**"
            "(意思是配給你的錢有一部分其實是把本金退還給你;年化配息率用 MoneyDJ 官方公布值)。"
            "「**(全期實際)**」欄是你持有這段期間的累計真實值(不換算成每年),持有很短也照顯示;"
            "「**(年化)**」欄要持有滿 0.5 年才有數字(太短就換算成每年,會產生誇大的假象)。"
            "這兩欄**只供你回看歷史**,不參與燈號判定。"
            "📊 **想挑長線核心資產**請另看 3-3-3 原則:成立滿 3 年 + 過去 3 年平均每年賺 > 7%。"
        )
        if _sharpe_src_uniform:
            st.caption(
                f"📎 本批基金的 **Sharpe 全部來自同一個地方**:「{_sharpe_src_uniform}」"
                "—— 整欄逐列都一樣、沒有資訊量,所以先收起來;"
                "只要出現期間不一致的情況(例如有些檔只有六個月期),這一欄會自動回到表內逐列顯示。"
            )
        # v19.77 L1：column_config 數值格式化（百分號 / 千分位）+ 欄寬調整
        # 2026-08-06 必修 4:設定抽至 `ui/helpers/fund_grp_health/columns.py`,
        # 與批次大表(Tab③)同源;順道補齊 σ/買賣點那批原本**完全沒有** help 的欄。
        from streamlit import column_config as _cc
        from ui.helpers.fund_grp_health.columns import (
            base_column_config,
            extra_column_config,
        )
        _col_cfg = {**base_column_config(), **extra_column_config()}
        # v19.411:合併表 column_config = ③ 本表 + ①② 傳入格式(extra_cfg)。
        _full_cfg = {**_col_cfg, **(extra_cfg or {})}
        st.dataframe(
            df, use_container_width=True, hide_index=True,
            column_config={k: v for k, v in _full_cfg.items() if k in df.columns},
        )

        # v19.423 — 🔀 換標決策(大盤 regime banner + 紅燈檔一對一替換);組合/持倉共用此表
        try:
            from ui.helpers.fund_grp_health.switch_section import render_switch_section
            render_switch_section(df.to_dict("records"))
        except Exception as _e_sw:  # noqa: BLE001 — 換標區塊失敗不擋大表
            system_error("換標決策區塊失敗", _e_sw)

        # v19.425 — 🧭 景氣位階適配摘要
        try:
            from ui.helpers.fund_grp_health.regime_section import render_regime_fit_section
            # 2026-09-02 T16:`show_current_regime=False` —— 本頁最上方已有一條
            # 「📊 當前總經 Phase：…」橫幅,讀的是**同一個** `phase_info["phase"]`。
            # 原本這裡會把同一個字串再宣告一次,而且措辭不同(「當前總經 Phase」vs
            # 「當前景氣位階」),讀起來像兩個不同的東西。位階這句話併回頁首那一行,
            # 本區塊只講適配結果。
            # ⚠️ 只關本頁的重複宣告:`ui/tab_batch_analysis.py` 沒有那條橫幅,
            #    它走預設 True、行為不變(詳見該函式 docstring)。
            render_regime_fit_section(df.to_dict("records"),
                                      show_current_regime=False)
        except Exception as _e_rf:  # noqa: BLE001
            system_error("景氣適配區塊失敗", _e_rf)

        # v19.69 J1：多基金績效比較圖
        if len(ok_rows) >= 2:
            try:
                import plotly.graph_objects as _go
                _codes = [r["code"] for r in ok_rows]
                # v19.190 fix + v19.194 merge reconcile：key 對齊 process_one_fund 實際輸出。
                # 並行線 v19.180 把欄位拆成「(全期實際)」+「(年化)」兩套。
                # v19.304 FIX（user 2026-07-04「多檔比較資料都是 0」根治）:
                #   年化欄在持有 < 0.5 年時依 dividend_calc.MIN_YEARS_FOR_ANNUALIZE guard
                #   一律為 None（防「短期配息 × 倍數」年化幻象，§1 Fail Loud）。同保單同期
                #   買進的多檔常整排短歷史 → 年化全 None → 圖表 float(None or 0) 畫成全 0 空圖。
                #   修法:全檔都有年化值才用「年化」(跨檔可比、原設計);任一檔短歷史 →
                #   全圖改用「全期實際」(100% 真實累計、永遠有值、不年化故無造假風險),
                #   基準統一避免同圖混基準,並在標題 / 圖例 / caption 明示當前基準。
                _basis = _pick_comparison_basis(ok_rows)
                _all_annual = _basis == "年化"
                _div_key = f"配息率% ({_basis})"
                _ret_key = f"含息% ({_basis})"
                _nav_key = f"淨值% ({_basis})"
                # v19.387 V1 §1:缺值保留 None → Plotly 該柱留缺口(誠實),不再 `or 0` 畫成
                # 與「真實 0%」無法區分的假柱。基準切換(v19.304)已解全 0,此處補單檔 None。
                _div_r  = [safe_num(r.get(_div_key)) for r in ok_rows]
                _ret_r  = [safe_num(r.get(_ret_key)) for r in ok_rows]
                _nav_r  = [safe_num(r.get(_nav_key)) for r in ok_rows]
                _fig = _go.Figure()
                _fig.add_trace(_go.Bar(x=_codes, y=_div_r, name=f"配息率%({_basis})🧮", marker_color="#f0883e"))
                _fig.add_trace(_go.Bar(x=_codes, y=_ret_r, name=f"含息%({_basis})🧮",  marker_color=TRAFFIC_GREEN))
                _fig.add_trace(_go.Bar(x=_codes, y=_nav_r, name=f"淨值%({_basis})🧮",  marker_color=INFO_BLUE))
                _fig.add_hline(y=0, line_dash="dot", line_color=GRAY_55)
                _fig.update_layout(
                    barmode="group",
                    title=f"📊 多基金績效比較 🧮（{_basis}:配息率 / 含息報酬 / 淨值漲跌）",
                    height=360,
                    paper_bgcolor=GH_BG_PRIMARY, plot_bgcolor=GH_BG_PRIMARY,
                    font=dict(color=GH_FG_SECONDARY),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                    margin=dict(l=20, r=20, t=70, b=20),
                    # v19.395 V3:3 序列分組長條 → unified hover,同基金三值一次讀
                    # (audit DEFECT-NOHOVER);原無 hovermode。
                    hovermode="x unified",
                )
                st.plotly_chart(_fig, use_container_width=True)
                if not _all_annual:
                    st.caption(
                        "ℹ️ 部分基金持有 < 0.5 年，年化值會失真（短期配息 × 倍數的幻象），"
                        "故本圖改以「全期實際」(持有期累計、未年化) 呈現真實數據，各檔基準一致。"
                    )
                # v19.77 L1：精簡比較表（對照圖看精確值，基準同上圖 v19.304）
                _cmp_df = pd.DataFrame([
                    {
                        "代號": r["code"],
                        "基金名": r.get("基金名", ""),
                        _ret_key: safe_num(r.get(_ret_key)),  # v19.387 §1:缺值 → 空格(NumberColumn),非 0
                        _div_key: safe_num(r.get(_div_key)),
                        _nav_key: safe_num(r.get(_nav_key)),
                    }
                    for r in ok_rows
                ])
                st.dataframe(
                    _cmp_df, use_container_width=True, hide_index=True,
                    column_config={
                        "代號": _cc.TextColumn("代號", width="small"),
                        "基金名": _cc.TextColumn("基金名", width="medium"),
                        _ret_key: _cc.NumberColumn(_ret_key, format="%.2f %%"),
                        _div_key: _cc.NumberColumn(_div_key, format="%.2f %%"),
                        _nav_key: _cc.NumberColumn(_nav_key, format="%.2f %%"),
                    },
                )
            except Exception as _e_chart:
                system_error("多基金績效比較圖渲染失敗", _e_chart)

        # v19.77 L1：逐檔 expander → 兩張多檔合併表（持有 meta + 配息事件）
        st.markdown("#### 📋 逐檔配息明細 🧮")
        _meta_rows = []
        _ev_rows: list[dict] = []
        for r in ok_rows:
            detail = r.get("_detail", {}) or {}
            summary = detail.get("summary", {}) or {}
            _meta_rows.append({
                "代號": r["code"],
                "基金名": r.get("基金名", ""),
                "買進日": detail.get("buy_date"),
                "買進 NAV": detail.get("buy_nav"),
                "買進 FX": detail.get("buy_fx"),
                "FX 源": detail.get("buy_fx_source"),
                "原幣本金 🧮": detail.get("principal_ccy_🧮"),
                "持有單位 🧮": detail.get("units_held_🧮"),
                "末日": summary.get("last_date"),
                "末日 NAV": summary.get("last_nav"),
                "持有年數 🧮": summary.get("holding_years_🧮"),
            })
            for _ev in (detail.get("events") or []):
                if isinstance(_ev, dict):
                    _ev_rows.append({"代號": r["code"], **_ev})

        _meta_df = pd.DataFrame(_meta_rows)
        st.markdown("##### 持有 meta")
        st.dataframe(
            _meta_df, use_container_width=True, hide_index=True,
            column_config={
                "代號": _cc.TextColumn("代號", width="small"),
                "基金名": _cc.TextColumn("基金名", width="medium"),
                "買進 NAV": _cc.NumberColumn("買進 NAV", format="%.4f"),
                "買進 FX": _cc.NumberColumn("買進 FX", format="%.4f"),
                "原幣本金 🧮": _cc.NumberColumn("原幣本金 🧮", format="%,.0f"),
                "持有單位 🧮": _cc.NumberColumn("持有單位 🧮", format="%,.2f"),
                "末日 NAV": _cc.NumberColumn("末日 NAV", format="%.4f"),
                "持有年數 🧮": _cc.NumberColumn("持有年數 🧮", format="%.2f"),
            },
        )
        st.markdown("##### 配息事件（多檔合併）")
        if _ev_rows:
            # 整頁其餘欄名都是中文,只有這張表直出 `compute_dividend_twd_series` 的
            # 英文 key(units_at_event_🧮 / ccy_div_per_unit …)。補中文標籤 + help,
            # 不改資料鍵(避免動到 L2 schema 與其他 caller)。
            st.dataframe(
                pd.DataFrame(_ev_rows),
                use_container_width=True, hide_index=True,
                column_config={
                    "代號": _cc.TextColumn("代號", width="small"),
                    "ex_date": _cc.TextColumn("除息日", width="small",
                        help="MoneyDJ 記錄的除息日(配息當天);只列出你買進日之後的配息。"),
                    "ccy_div_per_unit": _cc.NumberColumn("每單位配息(原幣)", format="%.4f",
                        help="那一次每持有 1 個單位,可以配到多少原幣。"),
                    "units_at_event_🧮": _cc.NumberColumn("當時持有單位 🧮", format="%,.4f",
                        help="除息當下你手上有幾個單位。本表預設配息不再投入,所以各次都一樣。"),
                    "ccy_div_total_🧮": _cc.NumberColumn("該次配息(原幣) 🧮", format="%,.2f",
                        help="每單位配息 × 當時持有單位 = 那一次總共配到多少原幣。"),
                    "fx_at_ex": _cc.NumberColumn("除息日匯率", format="%.4f",
                        help="那一天 1 元原幣可以換到幾元台幣。"
                             "**刻意用當天的匯率,不是拿今天的匯率回頭套** —— "
                             "否則會把後來的匯率變動算進過去的績效裡。"),
                    "fx_source": _cc.TextColumn("匯率來源", width="small",
                        help="這個匯率是從歷史匯率序列查到的,還是查不到、退而用現在的即期匯率 —— "
                             "標出來讓你知道這一格有多可靠。"),
                    "twd_div_🧮": _cc.NumberColumn("該次配息(TWD) 🧮", format="%,.0f",
                        help="那一次配到的原幣金額 × 除息日匯率 = 換成台幣是多少。"),
                    "nav_at_ex": _cc.NumberColumn("除息日 NAV", format="%.4f",
                        help="除息當天(或之前最近一個有報價的日子)的淨值;"
                             "基金淨值週末假日不更新是正常的。"),
                    "single_event_div_pct_🧮": _cc.NumberColumn("該次配息率 % 🧮", format="%.3f %%",
                        help="每單位配息 ÷ 除息日淨值 × 100 = 那**一次**配了幾 %"
                             "(單次的,不是一年的)。"),
                },
            )
        else:
            st.info("所有檔於買進日後皆無配息事件")

    if err_rows:
        st.markdown("#### ❌ 抓取失敗")
        for r in err_rows:
            st.error(f"{r['code']}: {r.get('error', '?')}")
