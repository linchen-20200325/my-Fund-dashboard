"""ui/helpers/fund_grp_health/rotation.py — 🔄 輪動配對建議表(v19.415)。

賣「高基期」→ 買「低基期 + 體質健康」的**不同類別**基金(跨產業/性質輪動),賺均值回歸差價。

兩個入口共用同一張配對表 UI(`_render_pairs_ui`):
- **組合健診** `render_rotation_section(funds)`:由 rich fund 物件重組每檔資料
  (`build_merged_extra_columns` σ/距HWM/操盤評分 + `build_health_analysis_row` 類別/4D
  + `check_eating_principal_1y_mk` 吃本金)。
- **批次分頁** `render_rotation_section_from_df(df)`:直接讀已算好的組合健診大表 df
  (σ rank / 距 HWM % / 操盤評分 / 基金類別 / 4D Grade / 吃本金燈號 皆在表內)—— **不重抓**,
  另附獨立 CSV 下載(配對表與大表形狀不同,無法併進同一張 CSV)。

L3 orchestrator → L2(rotation / health.report / health.dividend)+ L3(unified),全下行。
"""
from __future__ import annotations

import streamlit as st

from ui.helpers.render_state import system_error


def _assemble_rows(funds: list) -> list:
    """每檔組成 suggest_rotation_pairs 需要的欄位 dict。"""
    from services.health.report import build_health_analysis_row
    from ui.helpers.fund_grp_health.unified import build_merged_extra_columns

    _pi = st.session_state.get("phase_info") if hasattr(st, "session_state") else None
    _, _extra = build_merged_extra_columns(
        funds, (_pi or {}).get("phase") or "", (_pi or {}).get("score"))

    # Layer 3-C:第 5 維(匯率風險)會改變分數 → 必須與大表拿同一份匯率資料,
    # 否則同一檔在輪動配對與健診大表會出現不同等第(§2.1)。
    from services.fx_regime_service import fx_regime_by_ccy as _fxr_rot
    _fx_map_rot = _fxr_rot() or {}

    rows = []
    for _f in funds:
        _code = _f.get("code", "?")
        _fd = _f.get("moneydj_raw") or _f
        try:
            _h = build_health_analysis_row(_fd, _code, fx_cv_by_ccy=_fx_map_rot)
        except Exception:  # noqa: BLE001
            _h = {}
        try:
            from services.health.dividend import check_eating_principal_1y_mk
            _eat = (check_eating_principal_1y_mk(_fd) or {}).get("status", "")
        except Exception:  # noqa: BLE001
            _eat = ""
        _e = _extra.get(_code, {})
        rows.append({
            "code": _code, "name": _f.get("name") or _code,
            "基金類別": _h.get("基金類別"), "4D Grade": _h.get("4D Grade"),
            "σ rank": _e.get("σ rank"), "距 HWM %": _e.get("距 HWM %"),
            "操盤評分": _e.get("操盤評分"), "吃本金燈號": _eat,
            "currency": _f.get("currency"),   # v19.484:跨幣別換股標註(§4.1)用
        })
    return rows


# 2026-08-31 計算下沉:批次大表 df → rows 的輸入契約對映(原本檔 `_cell` + `rows_from_batch_df`)
# 已**逐字**搬至 services/rotation.py(與配對核心同住,全站單一份)。此處 re-export 保持
# 既有 import 路徑(`from ui.helpers.fund_grp_health.rotation import rows_from_batch_df`)不變。
from services.rotation import rows_from_batch_df  # noqa: F401


def _render_pairs_ui(rows: list, *, key_prefix: str, offer_download: bool = False) -> None:
    """divider + 標題 + σ/評分滑桿 + 配對表(+ 選配獨立 CSV 下載)。rows 已組好。

    key_prefix 讓組合健診 / 批次兩處滑桿的 session_state key 不衝突。
    """
    from services.rotation import suggest_rotation_pairs
    # 三個滑桿的**預設值**走 SSOT(與健診大表「基期」欄、選基金篩選器同一組門檻),
    # 不在 UI 另外寫死一組數字 —— 寫死等於在畫面上多養一把尺(§3.3)。
    from shared.signal_thresholds import (
        ROTATION_BUY_MIN_SCORE,
        ROTATION_BUY_SIGMA,
        ROTATION_SELL_SIGMA,
    )

    st.divider()
    st.markdown("### 🔄 輪動配對建議(賣高基期 → 買**別類**低基期健康)")
    st.caption("跨產業 / 性質輪動:賣掉已經漲到貼近高點的基金,換進**不同類別**、跌得深"
               "但體質仍健康的基金(順便分散,賺價格回歸的差價)。"
               "⚠️ 跌深**不保證**會漲回來 —— 買方這邊已經先過濾過"
               "(健康等第 A/B/C + 沒有在吃本金 + 操盤評分達標),避免接到下墜的刀。")

    c1, c2, c3 = st.columns(3)
    _sell = c1.slider("高基期門檻(σ rank ≥)", -2.0, 0.5, ROTATION_SELL_SIGMA, 0.1,
                      key=f"{key_prefix}sell",
                      help="現價離期間高點多近就算「太貴、可以賣」。"
                           "σ 是波動的倍數,數字愈接近 0 代表愈貼近高點。")
    _buy = c2.slider("低基期門檻(σ rank ≤)", -3.0, -0.5, ROTATION_BUY_SIGMA, 0.1,
                     key=f"{key_prefix}buy",
                     help="現價要跌到離高點多遠才算「夠便宜、可以買」。"
                          "數字愈負代表跌得愈深。")
    _minsc = c3.slider("買方操盤評分 ≥", 0, 100, int(ROTATION_BUY_MIN_SCORE), 5,
                       key=f"{key_prefix}score",
                       help="要換進來的基金,經理人操盤評分至少要幾分(避免換到操作更差的)。")

    try:
        _pairs = suggest_rotation_pairs(rows, sell_sigma=_sell, buy_sigma=_buy,
                                        min_score=float(_minsc))
    except Exception as e:  # noqa: BLE001
        system_error("輪動配對計算失敗", e)
        return

    _render_pairs_body(rows, _pairs, _sell, _buy,
                       key_prefix=key_prefix, offer_download=offer_download)


def _render_pairs_body(rows: list, _pairs: list, _sell: float, _buy: float, *,
                       key_prefix: str, offer_download: bool) -> None:
    """配對表本體:σ 不足名單 + 空態 + 9 欄表 + 誠實 caption(+ 選配 CSV)。

    2026-08-31 元件 B(互補配對探索)自 `_render_pairs_ui` 抽出**逐字共用**:
    ②/Tab3 的既有輪動配對區與 ③ 批次的收合 Expander 渲染同一份表身,
    不留兩份(§2.1)。呼叫端已算好 _pairs(含失敗處理),本函式只畫。
    """
    # v19.484 稽核 #5:σ 資料不足(淨值史太短 / 停售 → σ rank 回不了值)的檔會被排除在
    # 買方候選外。原本靜默剔除 → 明確標名,讓使用者知道「不是漏了它,是它現在無法評估」(§1)。
    # (2026-08-31 判斷式逐字下沉 services.rotation.insufficient_sigma_names,UI 只呼叫。)
    from services.rotation import insufficient_sigma_names
    _insuff_names = insufficient_sigma_names(rows, _sell, _buy)

    def _render_insufficient_note() -> None:
        if _insuff_names:
            st.caption("⬜ 未納入買方候選(σ 資料不足,通常是淨值歷史太短 / 停售 → 無法定位階):"
                       + "、".join(_insuff_names) + "。先補足淨值歷史再評估,不硬推(§1)。")

    if not _pairs:
        # 誠實揭露「為何無配對」+ 每檔目前基期,讓使用者知道現況、可調滑桿(§1)
        from services.rotation import classify_base
        _lbl = {"high": "🔴 高基期(可賣)", "low": "🟢 低基期(可買)",
                "mid": "⚪ 中性", "unknown": "⬜ σ 資料不足"}
        _status = [
            f"{r.get('name') or r.get('code')} {r.get('σ rank') or '—'}"
            f"({_lbl.get(classify_base(r.get('σ rank'), _sell, _buy), '?')})"
            for r in rows
        ]
        if len(rows) < 2:
            st.info("輪動配對需要**至少 2 檔**基金(要有可賣的高基期 + 可買的別類低基期);"
                    "目前這組不足 2 檔。")
        else:
            st.info("目前**沒有貼近高點的「高基期」持有基金** → 沒有需要輪動賣出的標的。"
                    "可把上方「高基期門檻」滑桿**往左放寬**(納入更多賣方候選);"
                    "若仍無,代表現在沒有適合換出的標的(這是正常的誠實結果)。")
        st.caption("目前各檔基期:" + "　·　".join(_status))
        _render_insufficient_note()
        return

    import pandas as pd
    _disp = [{
        "賣出(高基期)": f"{p['sell_name']} ({p['sell_code']})",
        "賣方類別": p["sell_cat"] or "—",
        "賣方 σ": p["sell_sigma"],
        "建議換進(別類低基期健康)": (
            f"{p['buy_name']} ({p['buy_code']})" + (" ⚠️跨幣別" if p.get("cross_ccy") else "")
            if p["buy_code"] else "⚪ 無不同類健康低基期標的"),
        "買方類別": p.get("buy_cat") or "—",
        "買方 σ": p["buy_sigma"],
        "買方 4D": p["buy_grade"],
        "買方操盤評分": p["buy_score"],
        "潛在差價%": p["potential_pct"],
    } for p in _pairs]

    _out = pd.DataFrame(_disp)
    from streamlit import column_config as _cc
    st.dataframe(
        _out, use_container_width=True, hide_index=True,
        column_config={
            "賣出(高基期)": _cc.TextColumn("賣出(高基期)", width="medium",
                help="σ rank 貼近期間高點的持有基金 = 換出候選。"),
            "賣方類別": _cc.TextColumn("賣方類別", width="small"),
            "賣方 σ": _cc.NumberColumn("賣方 σ", format="%.2f",
                help="賣方的 σ rank(愈接近 0 或正值 = 愈貼近高點)。"),
            "建議換進(別類低基期健康)": _cc.TextColumn("建議換進(別類低基期健康)", width="medium",
                help="**跨類別**輪動:只配不同基金類別、σ 跌最深、且通過健康過濾"
                     "(4D A/B/C + 吃本金健康 + 操盤評分達門檻)的標的;沒有就誠實留 ⚪。"),
            "買方類別": _cc.TextColumn("買方類別", width="small"),
            "買方 σ": _cc.NumberColumn("買方 σ", format="%.2f",
                help="買方的 σ rank(愈負 = 跌愈深 = 回歸差價空間愈大)。"),
            "買方 4D": _cc.TextColumn("買方 4D", width="small",
                help="買方 4D 健康等級;D/F/缺值一律不推薦(fail-closed,避免接刀)。"),
            "買方操盤評分": _cc.NumberColumn("買方操盤評分", format="%d",
                help="上/下檔捕捉率換算的經理人操作評分;**缺值不擋**(短歷史常缺),"
                     "由 4D 與吃本金燈號把關。"),
            "潛在差價%": _cc.NumberColumn("潛在差價%", format="%.1f %%",
                help="買方回到**自己期間高點**的漲幅 —— 只是幾何回推,"
                     "**不是預測**,低基期也可能是價值陷阱。"),
        },
    )
    _n_ok = sum(1 for p in _pairs if p["buy_code"])
    st.caption(f"共 {len(_pairs)} 檔高基期;其中 **{_n_ok}** 檔有**不同類別**健康低基期可換。"
               "「潛在差價%」= 買方回到自己期間高點的漲幅(僅參考,非保證)。")
    # v19.484 稽核 #3(user「標註匯差但保留」):跨幣別配對只提醒、不砍(§4.1)
    if any(p.get("cross_ccy") for p in _pairs):
        st.caption("⚠️ 標「跨幣別」者:賣、買計價幣別不同,換股時會**被動吃到匯率變動**;"
                   "「潛在差價%」是買方**自身幣別**的回歸幅度,未含匯差。仍保留此配對(分散價值),"
                   "由你自行決定是否承受匯率風險。")
    _render_insufficient_note()

    if offer_download:
        st.download_button(
            "⬇️ 下載輪動配對建議 CSV",
            _out.to_csv(index=False).encode("utf-8-sig"),
            file_name="輪動配對建議.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{key_prefix}download",
        )


def render_rotation_section(funds: list, *, key_prefix: str = "rot_") -> None:
    """🔄 輪動配對表 —— 由 rich fund 物件重組每檔資料(組合健診 + 持倉健診共用)。

    只要有基金就渲染區塊(標題永遠出現);組資料失敗 / 不足 2 檔 / 無高基期,
    都在區塊內顯示明確原因,**不靜默消失**(user 2026-07-28 回報「看不到配對表」)。

    key_prefix:兩個 tab 在同一 st.tabs run 都會執行 → 滑桿 widget key 須唯一,
    健診 Tab 用 'rot_'、Tab3 持倉健診用 'pf_rot_'(避免 StreamlitDuplicateElementKey)。
    """
    if not funds:
        return
    try:
        rows = _assemble_rows(funds)
    except Exception as e:  # noqa: BLE001
        st.divider()
        st.markdown("### 🔄 輪動配對建議(賣高基期 → 買**別類**低基期健康)")
        system_error("輪動配對資料組建失敗", e)
        return
    _render_pairs_ui(rows, key_prefix=key_prefix, offer_download=False)


def render_rotation_section_from_df(df) -> None:
    """🔄 批次分頁:用已算好的組合健診大表 df 渲染輪動配對(不重抓)+ 獨立 CSV 下載。

    ⚠️ 2026-08-31 起批次分頁改走 `render_complementary_explorer_from_df`(元件 B,
    客戶 Q3 拍板「改型為互補探索」);本函式保留供既有 import 路徑與回歸測試,
    production 端 `ui/tab_batch_analysis.py` 已不再呼叫它。
    """
    if df is None or getattr(df, "empty", True):
        return
    _render_pairs_ui(rows_from_batch_df(df), key_prefix="batch_rot_", offer_download=True)


# ═══════════════════════════════════════════════════════════════════════
# 元件 B:🧩 候選標的互補探索(2026-08-31 客戶拍板 Q3/Q4)
# ═══════════════════════════════════════════════════════════════════════

def _pair_card_html(p: dict) -> str:
    """單張「最佳互補配對卡」(Q4:每張只顯示最佳一檔買方;其餘候選看下方完整表)。

    視覺沿用 #726 六元件語彙(gh_card 外框 + status_chip 徽章),不另創第三套。
    無不同類健康低基期可換 → 買方側誠實顯示「⚪ 無標的」,不藏卡(§1)。
    """
    from shared.colors import GH_FG_MUTED, GH_FG_PRIMARY
    from ui.components.cards import gh_card
    from ui.components.status import status_chip

    def _sigma_txt(v):
        return "—" if v is None else f"{v:+.2f}σ"

    sell = (f"<div style='font-size:11px;color:{GH_FG_MUTED}'>賣出（高基期）</div>"
            f"<div style='font-size:13px;font-weight:700;color:{GH_FG_PRIMARY};"
            f"line-height:1.35'>{p['sell_name']}"
            f"<span style='color:{GH_FG_MUTED};font-size:11px'>（{p['sell_code']}）</span></div>"
            f"<div style='font-size:11.5px;color:{GH_FG_MUTED}'>"
            f"{p['sell_cat'] or '—'}　·　σ {_sigma_txt(p['sell_sigma'])}</div>")
    if p.get("buy_code"):
        _score = "—" if p.get("buy_score") is None else f"{p['buy_score']:.0f}"
        buy = (f"<div style='font-size:11px;color:{GH_FG_MUTED};margin-top:7px'>"
               f"⇄ 最佳互補買進（別類低基期健康）</div>"
               f"<div style='font-size:13px;font-weight:700;color:{GH_FG_PRIMARY};"
               f"line-height:1.35'>{p['buy_name']}"
               f"<span style='color:{GH_FG_MUTED};font-size:11px'>（{p['buy_code']}）</span></div>"
               f"<div style='font-size:11.5px;color:{GH_FG_MUTED}'>"
               f"{p.get('buy_cat') or '—'}　·　σ {_sigma_txt(p['buy_sigma'])}　·　"
               f"4D {p.get('buy_grade') or '—'}　·　操盤 {_score}</div>")
        _pot = p.get("potential_pct")
        foot_bits = []
        if _pot is not None:
            foot_bits.append(
                f"<span style='color:{GH_FG_PRIMARY};font-weight:700'>潛在差價 {_pot:+.1f}%</span>"
                f"<span style='color:{GH_FG_MUTED};font-size:10.5px'>（僅幾何回推,不是預測）</span>")
        if p.get("cross_ccy"):
            foot_bits.append(status_chip("跨幣別（含匯差）", "caution"))
        foot = (f"<div style='margin-top:6px;display:flex;gap:10px;align-items:center;"
                f"flex-wrap:wrap;font-size:12px'>{''.join(foot_bits)}</div>") if foot_bits else ""
    else:
        buy = (f"<div style='font-size:11px;color:{GH_FG_MUTED};margin-top:7px'>"
               f"⇄ 最佳互補買進</div>"
               f"<div style='font-size:12.5px;color:{GH_FG_MUTED}'>"
               f"⚪ 無不同類健康低基期標的（誠實留白,不硬湊）</div>")
        foot = ""
    return gh_card(sell + buy + foot, radius=9, padding="12px 14px",
                   extra="position:relative;overflow:hidden")


def render_complementary_explorer_from_df(df) -> None:
    """🧩 元件 B:③ 批次結果區的「候選標的互補探索」(預設收合 Expander)。

    客戶 2026-08-31 拍板(線框 `docs/wireframes/rotation-components-wireframe.html`):
    - **Q3**:③ 的輪動配對由「攤開照抄 ②」改型為本元件(收合 + 卡片 + 完整表 + CSV),
      並覆蓋舊五頁線框「批次端輪動整段移除」該句。**資訊零損失,位置與型態改變。**
    - **Q4**:互補配對卡每張只顯示**最佳一檔**買方(計算層本來就只回一檔);
      想比較其他候選,往下就是完整配對表。
    - 一句話職責:**掃出來的這一批裡,誰跟誰互補。**(互補 = 不同類別 + 一高一低基期
      + 買方通過健康過濾 —— 即既有輪動配對定義,零新演算法。)

    直接讀已算好的批次大表 df(**不重抓**,沿用 rows_from_batch_df 資料路徑);
    df 不存在 → 不渲染(批次面板自己有「▶️ 開始」指路),首屏成本為零。
    收合標題帶計數 —— 計數本身就是答案的預覽(0 對 = 不用點開)。

    ✅ 2026-08-31 補齊(#738 延後項):線框揭露的「3 支滑桿包 `st.form`」防重繪手法
    **已落地**(區塊 1 + 「套用門檻」submit),並同步登記
    `tests/test_ui_rerun_contract.py::FORM_SITES`。#738 當時未做的唯一原因是該測試檔
    正由另一 PR(#736)佔用、明令禁改(File Boundary 防撞);該阻擋已解除。
    **滑桿 key 沿用 `batch_rot_*` 未改**,門檻預設值仍走 SSOT,計數行為不變(見區塊 1 註)。
    """
    if df is None or getattr(df, "empty", True):
        return
    from services.rotation import suggest_rotation_pairs
    from shared.signal_thresholds import (
        ROTATION_BUY_MIN_SCORE,
        ROTATION_BUY_SIGMA,
        ROTATION_SELL_SIGMA,
    )
    from ui.helpers.render_state import not_ready

    rows = rows_from_batch_df(df)

    # Expander 標題的計數要在 expander 建立**之前**算好 —— 門檻讀 session_state
    # (widget 互動後 rerun 時已是最新值;首跑用 SSOT 預設),與內部滑桿同一組 key,
    # 故標題計數與內容永遠同源,不會兩個數字打架(§2.1)。
    _sell = float(st.session_state.get("batch_rot_sell", ROTATION_SELL_SIGMA))
    _buy = float(st.session_state.get("batch_rot_buy", ROTATION_BUY_SIGMA))
    _minsc = float(st.session_state.get("batch_rot_score", int(ROTATION_BUY_MIN_SCORE)))
    _calc_err = None
    try:
        _pairs = suggest_rotation_pairs(rows, sell_sigma=_sell, buy_sigma=_buy,
                                        min_score=_minsc)
    except Exception as e:  # noqa: BLE001 — 進 expander 後以 system_error 呈現
        _pairs, _calc_err = [], e

    _n_ok = sum(1 for p in _pairs if p.get("buy_code"))
    with st.expander(f"🧩 互補配對探索（{_n_ok} 對可換 / {len(_pairs)} 檔高基期）",
                     expanded=False):
        st.caption("掃出來的這一批裡,**誰跟誰互補**:賣掉貼近高點的高基期候選,"
                   "換進**不同類別**、跌得深但體質健康的標的(分散 + 賺回歸差價)。"
                   "⚠️ 跌深**不保證**漲回來 —— 買方已先過濾"
                   "(健康等第 A/B/C + 沒有在吃本金 + 操盤評分達標),避免接刀。")

        # ── 區塊 1:門檻列(3 欄滑桿包 st.form,預設值走 SSOT,與 ② 同一組門檻)──
        # 鐵律 2(Form 防重繪):批次 df 動輒數百檔,沒有 form 時**每拉一格滑桿**就整頁
        # 重跑一次。包進 form 後拖動不觸發 rerun,按「套用門檻」才算。
        # (客戶已拍板線框 §03 區塊 1:「3 欄滑桿 ＋『套用門檻』鈕」—— 實作補上既有規格,
        #  不是新設計;#738 當時因 tests/test_ui_rerun_contract.py 防撞而延後,本批補齊。)
        # ⚠️ key 沿用 `batch_rot_*` **一字未改** —— 既有 session 值原地延續。
        # form 內的 widget 只在**按下送出時**才寫回 session_state,而標題計數與下方表身
        # 都在 expander 之前讀同一組 key → 送出前兩者一起維持「上一次套用」的門檻,
        # 不會出現「標題已變、表還沒變」的兩個數字打架(§2.1);首跑則同樣退 SSOT 預設。
        # ⚠️ 「送出前不寫回」是 Streamlit 的 form 語意,**沙箱驗不到**(AppTest 不模擬
        # 前端緩衝 —— streamlit 1.59.2 實測、量測日 2026-08-31,是版本相依行為不是永恆事實;
        # 見 tests/test_rotation_form_rerun_20260831.py 檔頭);守衛驗的是產生該行為的接線
        # (3 支滑桿與 submit 鈕同屬一個 form_id)。體感請在瀏覽器確認。
        with st.form("batch_rot_threshold_form", clear_on_submit=False):
            c1, c2, c3 = st.columns(3)
            c1.slider("高基期門檻(σ rank ≥)", -2.0, 0.5, ROTATION_SELL_SIGMA, 0.1,
                      key="batch_rot_sell",
                      help="現價離期間高點多近就算「太貴、可以賣」。"
                           "σ 是波動的倍數,數字愈接近 0 代表愈貼近高點。")
            c2.slider("低基期門檻(σ rank ≤)", -3.0, -0.5, ROTATION_BUY_SIGMA, 0.1,
                      key="batch_rot_buy",
                      help="現價要跌到離高點多遠才算「夠便宜、可以買」。"
                           "數字愈負代表跌得愈深。")
            c3.slider("買方操盤評分 ≥", 0, 100, int(ROTATION_BUY_MIN_SCORE), 5,
                      key="batch_rot_score",
                      help="要換進來的基金,經理人操盤評分至少要幾分(避免換到操作更差的)。")
            st.form_submit_button("套用門檻", use_container_width=True)

        if _calc_err is not None:
            # 🔴 系統真出錯(區塊隔離:上方批次大表與其 CSV 不受影響)
            system_error("互補配對計算失敗", _calc_err,
                         hint="上方批次大表與「⬇️ 下載分析結果 CSV」不受影響。")
            return

        if len(rows) < 2:
            not_ready("配對需至少 2 檔;目前批次結果不足 2 檔,還不能比對互補性")
            return

        # ── 區塊 2:最佳互補配對卡(3 欄自適應網格;Q4 每張只顯示最佳一檔買方)──
        if _pairs:
            for _i in range(0, len(_pairs), 3):
                _cols = st.columns(3)
                for _col, _p in zip(_cols, _pairs[_i:_i + 3]):
                    _col.markdown(_pair_card_html(_p), unsafe_allow_html=True)
            st.caption("卡片是答案、下表是依據:每張卡只給**最佳一檔**買方(σ 跌最深且"
                       "通過健康過濾);想比較其他候選請看下方完整配對表。")

        # ── 區塊 3+4:完整配對表(9 欄原樣)+ CSV + 誠實揭露列(與 ② 同一份表身)──
        _render_pairs_body(rows, _pairs, _sell, _buy,
                           key_prefix="batch_rot_", offer_download=True)
