"""ui/components/allocation_donut_card.py — 核心／衛星圓環 + 動態配比卡（T7，UI3b）。

一句話：**把「核心佔幾成」畫成一個看一眼就懂的圓環**，
同時**不讓那個圓環在資料不夠時說謊**。

資料來源：**直接吃 `ui/helpers/portfolio/allocation.summarize_core_satellite()` 的原樣回傳。**
本元件**不自行加總、不自行分類**（級別怎麼判、金額怎麼加，那是 allocation.py 的事；
在這裡再算一次 = 第二份 SSOT，然後兩邊開始漂移）。

⚠️ **恆 2 片，絕不做多切片**（既有裁決）
----------------------------------------
曾經的寫法是「N 檔 = N 片」，但只有核心／衛星兩種顏色 → **同色 wedge 糊成一整片**，
既看不出檔數也看不出比例，是一張比沒有還糟的圖。故本元件永遠只有
**核心 / 衛星 兩片**；檔數改用 legend 文字表達。

⚠️ `is_amount_weighted=False` → **不畫圓環**
--------------------------------------------
`core_pct` 在「全數沒填本金」時是 `None`。畫下去只會得到一個 **0% / 0% 的假圓環**，
而使用者看到的是「我的核心部位是 0」—— 那和事實（**不知道**）差很遠。
故改畫 ⬜ 空態卡，並且明講：「**這不代表真的沒有核心資產**」。

⚠️ 全核心／全衛星時，0% 那片**仍然保留在圖上**
----------------------------------------------
把 0% 的那片刪掉，legend 就只剩一個分類 —— 「**沒有衛星**」會被讀成
「**這個系統沒有衛星這個分類**」。故 0 值的那片保留（`GRAY_44`），legend 標「衛星 0 檔」。

⚠️ **不塞假的 epsilon 值去換一條可見的細環**（判斷，已回報總管）：
規格寫「0% 那片用 `GRAY_44` **極細環**」。plotly 對 `value=0` 的扇形不會畫出弧，
要讓它「看得到一條細環」只能餵一個假的極小值 —— 那是 §1 明文禁止的捏造
（畫面上會出現一段不存在的部位）。本元件的處置：**保留切片與 legend（規則的目的達成），
但值維持真實的 0**。若客戶要的是視覺上一定要有一圈灰線，那屬版面設計變更，走草稿 gate。

§1 其餘邊界
-----------
- `n_missing_amount > 0` → 圓環照畫，**腳註必列「N 檔不在比例裡」**（它們不在分母中）。
- `target_pct is None` → 偏差 tile 顯示 `—` + sublabel「未設定目標」，**不假設一個目標**。

⚠️ 偏差門檻 `warn_pct` / `crit_pct` 為**必填參數**，刻意不給預設
---------------------------------------------------------------
`<5% ok／5~10% warn／>10% bad` 目前**只存在於說明書文字，不是常數 SSOT**。
在本元件寫死等於憑空造出一份門檻 SSOT。故一律由呼叫端傳入。
**已登記建議後端具名化為 `REBALANCE_WARN_PCT` / `REBALANCE_CRIT_PCT`。**

`degraded` 的用法
-----------------
✅ **圓環繪製失敗**可 `system_error(..., degraded=True)` —— 三個 tile 照常渲染，掉的只有圖。
⛔ **`summarize_core_satellite` 本身拋錯** → `degraded=False`：那時連數字都沒有。

純函式邊界
----------
`deviation_level()` / `build_allocation_donut()` 零 streamlit、零 session_state、
零 cache、零 repository/service import、零網路。
"""
from __future__ import annotations

from typing import Any, Mapping

import plotly.graph_objects as go

from shared.colors import GRAY_44, MATERIAL_ORANGE, MD_BLUE_300, STREAMLIT_BG
from ui.components.chart_factory import PLOTLY_CONFIG, apply_dark_template
from ui.components.stat_tile import stat_tile

DONUT_HOLE: float = 0.65


def deviation_level(diff_pct: Any, *, warn_pct: float, crit_pct: float) -> str:
    """`|核心% − 目標%|` → status level。`None` → `"unknown"`（不猜）。

    門檻由呼叫端傳入（見模組 docstring：目前無後端常數 SSOT）。
    """
    if diff_pct is None:
        return "unknown"
    try:
        d = abs(float(diff_pct))
    except (TypeError, ValueError):
        return "unknown"
    if d < float(warn_pct):
        return "ok"
    if d <= float(crit_pct):
        return "warn"
    return "bad"


def build_allocation_donut(summary: Mapping[str, Any] | None) -> go.Figure | None:
    """圓環圖。**資料不足以算金額比例 → 回 `None`**（呼叫端改畫空態卡，不畫假圖）。"""
    if not summary:
        return None
    if not summary.get("is_amount_weighted") or summary.get("core_pct") is None:
        # 全數沒填本金：畫下去就是 0%/0% 的假圓環（§1）。
        return None

    core_twd = float(summary.get("core_twd") or 0.0)
    sat_twd = float(summary.get("sat_twd") or 0.0)
    n_core = int(summary.get("n_core") or 0)
    n_sat = int(summary.get("n_sat") or 0)

    # 恆 2 片。0 值的那片**保留**（見 docstring）：刪掉會讓「沒有衛星」
    # 看起來像「沒有衛星這個分類」。0 值不補假的 epsilon。
    colors = [MD_BLUE_300 if core_twd > 0 else GRAY_44,
              MATERIAL_ORANGE if sat_twd > 0 else GRAY_44]
    fig = go.Figure(go.Pie(
        labels=[f"核心 {n_core} 檔", f"衛星 {n_sat} 檔"],
        values=[core_twd, sat_twd],
        hole=DONUT_HOLE,
        sort=False,
        direction="clockwise",
        textinfo="percent",
        marker=dict(colors=colors, line=dict(color=STREAMLIT_BG, width=1)),
        hovertemplate="%{label}<br>%{value:,.0f} TWD（%{percent}）<extra></extra>",
    ))
    apply_dark_template(fig, height="standard", margin="tight", x_unified=False,
                        legend=True)
    return fig


def build_footnotes(summary: Mapping[str, Any] | None) -> list[str]:
    """腳註（純字串）。`n_missing_amount > 0` → **必列**「N 檔不在比例裡」。

    ⚠️ **2026 文案更正（有意識的變更，不是漏刪）**：第二條腳註原本是

        ``f"⬜ {n-k}/{n} 檔的核心／衛星級別**非 Sheet 明示**，由基金名稱關鍵字推定。"``

    完整理由見 :func:`ui.helpers.portfolio.allocation.format_core_satellite_caption`
    的 docstring（同一句假敘述在本 repo 有兩份，這是第二份）。一句話版本：
    ``n_tier_from_sheet`` 只數 **v1** 的 ``policy_tier`` 欄，
    而客戶填在 **v2** ``tier`` 欄的值會被歸進「其餘」—— 那一檔是客戶自己填的，
    **沒有被任何名稱關鍵字猜過**，舊腳註等於當著客戶的面把他填的東西說成系統猜的。

    **本圓環特別需要補的那一句**：這張圖**恆 2 片**（既有裁決，見 module docstring），
    所以「還沒決定級別」的部位**在圖上完全看不見** —— 它被算進衛星那一片。
    不講的話，客戶會把「衛星 X%」讀成「我有 X% 的衛星」。
    ⛔ 本批**不**把「未設定」做進第三片（那是版面結構異動，依 `CLAUDE.md §-1.5.4`
    須先出線框草稿給客戶拍板）；本批只做**誠實揭露**。

    ⚠️ **2026 第二輪回修（有意識的更正，不是漏刪）—— 第一版的替代腳註自己也在說謊**

    第一版寫「這 N 檔的級別**未在 Sheet 的級別欄明示**，由系統代為分類
    （來源可能是 Sheet 上的級別資料，也可能是系統推定）」。**兩個問題**：
    (1) **它否定客戶真的做過的事** —— ``repositories/policy/v2.py`` 寫進客戶分頁的
    表頭裡，``tier`` 欄在客戶眼裡就叫 **「級別」**；一個在那一欄填了 core 的客戶，
    會讀到系統點名他剛填的那一欄說他沒填。
    (2) **同一句自我矛盾** —— 前半斷言「未在級別欄明示」，後半又說「來源可能是
    Sheet 上的級別資料」；對任何一檔而言，兩半必有一半為假。

    現在的腳註**只陳述系統的無知**（「系統分不出是誰決定的」），把三種可能
    （你設過／系統依名稱判讀／還沒設定）並列，**不對任何一檔下斷言**。

    :func:`ui.helpers.portfolio.allocation.format_core_satellite_caption`
    的 docstring 有完整的驗證紀錄（49 組真實來源組合）與該驗證的已知盲點。

    ⚠️ **腳註正文刻意不寫出欄位名**（走「Sheet 的級別欄」這種使用者語言）：
    `tests/test_ui3b_components.py::TestAllocationDonutCard
    ::test_component_does_not_recompute_the_summary` 明令本元件的**程式碼**
    （docstring／註解已被 `_code_only` 塗白，字串常數**不會**）不得出現
    ``resolve_core_flag`` / ``invest_twd"`` / 級別欄位名 ——
    守的是「本元件不得自行加總／分類」。本批第一版把欄位名寫進腳註字串，
    **當場被那條守衛擋下來**（它是子字串比對，分不出「用這個欄位」與
    「在文案裡提到它」）。**守衛沒有錯，是文案該換句話說** ——
    要精確欄位名的讀者在
    :func:`ui.helpers.portfolio.allocation.format_core_satellite_caption`
    那一行看得到。
    """
    notes: list[str] = []
    if not summary:
        return notes
    miss = int(summary.get("n_missing_amount") or 0)
    if miss:
        notes.append(
            f"⬜ {miss} 檔未填投入本金 → **不在這個比例裡**（不在分母中）。"
            "圓環顯示的是「有填本金的那些」的配置，不是全部持倉。")
    n_sheet = int(summary.get("n_tier_from_sheet") or 0)
    n_funds = int(summary.get("n_funds") or 0)
    if n_funds and n_sheet < n_funds:
        notes.append(
            f"⬜ {n_funds - n_sheet}/{n_funds} 檔的核心／衛星級別，"
            "**系統分不出是誰決定的** —— 可能是你在 Sheet 的級別欄設定過，"
            "可能是系統依基金名稱代為判定，也可能**未設定**；"
            "規則上**未設定一律算進衛星**，"
            "而這張圖只有兩片，看不出哪些是「還沒決定」。")
    return notes


def render_allocation_donut_card(
    summary: Mapping[str, Any] | None,
    *,
    warn_pct: float,
    crit_pct: float,
) -> None:
    """薄殼：圓環（或空態卡）＋ 三個 tile ＋ 強制腳註。"""
    import streamlit as st  # lazy

    from ui.helpers.render_state import not_ready

    summary = summary or {}
    fig = build_allocation_donut(summary)

    if fig is None:
        n = int(summary.get("n_funds") or 0)
        not_ready(
            f"{n} 檔都沒填投入本金 → 無法算金額比例；**這不代表真的沒有核心資產**"
            if n else "尚無持倉可統計核心／衛星比例",
            # ⚠️ 2026-09-04 就地更正（**有意識的更正，不是漏刪** · 決策者：AI 總管 ·
            # 依據：實測 `git grep 編輯初始持倉` + 全 `ui/**` 的 `st.expander` 掃描）：
            # 舊文案指名 ~~「編輯初始持倉」~~ —— **全 repo 沒有任何控制項叫這個名字**。
            # 實際的收合區是 `ui/tab3_t7_ledger.py` 的
            # `st.expander("✏️ 編輯持倉（手動微調 — 從 CHUBB 對帳單抄入精確值）")`。
            # ⚠️ 這比派工單轉述的「只是掉了 emoji」嚴重：「初始」二字在畫面上根本
            # 不存在，加不加 📝 都找不到。同一個死字串在 repo 內另有 **8 處活字串**
            # （`ui/tab3_t7_ledger.py` ×5、`ui/tab3_portfolio.py` ×1、
            # `ui/helpers/portfolio/allocation.py` ×1、
            # `services/policy_advisor_service.py` ×1；量測日 2026-09-04，
            # 以 AST 只數活字串、排除註解與 docstring），**全部不在本批檔案邊界內** ——
            # 已登記進 `tests/test_batch2_top_card_grid.py::WHERE_NAME_EXEMPT` 的
            # 待修欄與 PR 描述，本批只修本檔這一處（§8.4 step 4：不擴大範圍）。
            where="Google Sheet 的 `invest_twd` 欄，或 T7 帳本的"
                  "「✏️ 編輯持倉（手動微調 — 從 CHUBB 對帳單抄入精確值）」")
    else:
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    core_twd = summary.get("core_twd")
    sat_twd = summary.get("sat_twd")
    diff = summary.get("diff_pct")
    target = summary.get("target_pct")

    # 未加權時金額本身也不可信（全 0）→ 一律顯示「—」而不是 0（§1）。
    weighted = bool(summary.get("is_amount_weighted"))
    core_val = f"{float(core_twd):,.0f}" if (weighted and core_twd is not None) else None
    sat_val = f"{float(sat_twd):,.0f}" if (weighted and sat_twd is not None) else None

    if target is None:
        dev_tile = stat_tile(None, "與目標偏差", sublabel="未設定目標")
    else:
        lvl = deviation_level(diff, warn_pct=warn_pct, crit_pct=crit_pct)
        dev_val = None if diff is None else f"{float(diff):+.1f}"
        dev_tile = stat_tile(dev_val, "與目標偏差", status=lvl, value_suffix="pp",
                             sublabel=f"目標核心 {float(target):.0f}%")

    for col, html in zip(st.columns(3), (
            stat_tile(core_val, "核心金額", value_suffix=" TWD"),
            stat_tile(sat_val, "衛星金額", value_suffix=" TWD"),
            dev_tile)):
        with col:
            st.markdown(html, unsafe_allow_html=True)

    for note in build_footnotes(summary):
        st.caption(note)
