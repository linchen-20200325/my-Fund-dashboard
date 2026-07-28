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


def _assemble_rows(funds: list) -> list:
    """每檔組成 suggest_rotation_pairs 需要的欄位 dict。"""
    from services.health.report import build_health_analysis_row
    from ui.helpers.fund_grp_health.unified import build_merged_extra_columns

    _pi = st.session_state.get("phase_info") if hasattr(st, "session_state") else None
    _, _extra = build_merged_extra_columns(
        funds, (_pi or {}).get("phase") or "", (_pi or {}).get("score"))

    rows = []
    for _f in funds:
        _code = _f.get("code", "?")
        _fd = _f.get("moneydj_raw") or _f
        try:
            _h = build_health_analysis_row(_fd, _code)
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
        })
    return rows


def _cell(row, col):
    """從 pandas Series / dict 取值,NaN → None(避免 str(nan)='nan' 混入類別/σ)。"""
    import pandas as pd
    v = row.get(col)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def rows_from_batch_df(df) -> list:
    """批次「組合健診大表」df → suggest_rotation_pairs 所需 rows。

    所有欄位(σ rank / 距 HWM % / 操盤評分 / 基金類別 / 4D Grade / 吃本金燈號)已在大表內,
    **直接讀、不重抓**。σ rank / 距 HWM % 為預格式化字串(如 '-2.00σ'/'‑18%'),
    services.rotation 的 _sigma / _num 會自行剝除單位。
    """
    rows = []
    for _, r in df.iterrows():
        _code = _cell(r, "code")
        rows.append({
            "code": _code,
            "name": _cell(r, "基金名") or _code,
            "基金類別": _cell(r, "基金類別"),
            "4D Grade": _cell(r, "4D Grade"),
            "σ rank": _cell(r, "σ rank"),
            "距 HWM %": _cell(r, "距 HWM %"),
            "操盤評分": _cell(r, "操盤評分"),
            "吃本金燈號": _cell(r, "吃本金燈號 (1Y · MK)"),
        })
    return rows


def _render_pairs_ui(rows: list, *, key_prefix: str, offer_download: bool = False) -> None:
    """divider + 標題 + σ/評分滑桿 + 配對表(+ 選配獨立 CSV 下載)。rows 已組好。

    key_prefix 讓組合健診 / 批次兩處滑桿的 session_state key 不衝突。
    """
    from services.rotation import suggest_rotation_pairs

    st.divider()
    st.markdown("### 🔄 輪動配對建議(賣高基期 → 買**別類**低基期健康)")
    st.caption("跨產業/性質輪動:賣掉貼近高點的基金,換進**不同類別**、深跌但體質健康的基金"
               "(分散 + 賺回歸差價)。⚠️ 低基期**不一定**回漲 —— 買方已過濾"
               "(4D∈A/B/C + 非吃本金 + 操盤評分達標)避免接刀。")

    c1, c2, c3 = st.columns(3)
    _sell = c1.slider("高基期門檻(σ rank ≥)", -2.0, 0.5, -0.5, 0.1, key=f"{key_prefix}sell",
                      help="現價貼近高點幾 σ 內算高基期(賣方候選)")
    _buy = c2.slider("低基期門檻(σ rank ≤)", -3.0, -0.5, -1.5, 0.1, key=f"{key_prefix}buy",
                     help="跌破高點幾 σ 算低基期(買方候選)")
    _minsc = c3.slider("買方操盤評分 ≥", 0, 100, 50, 5, key=f"{key_prefix}score",
                       help="買方經理人操盤評分門檻(避免換進操作差的)")

    try:
        _pairs = suggest_rotation_pairs(rows, sell_sigma=_sell, buy_sigma=_buy,
                                        min_score=float(_minsc))
    except Exception as e:  # noqa: BLE001
        st.caption(f"⬜ 輪動配對計算失敗:[{type(e).__name__}] {str(e)[:80]}")
        return

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
        return

    import pandas as pd
    _disp = [{
        "賣出(高基期)": f"{p['sell_name']} ({p['sell_code']})",
        "賣方類別": p["sell_cat"] or "—",
        "賣方 σ": p["sell_sigma"],
        "建議換進(別類低基期健康)": (f"{p['buy_name']} ({p['buy_code']})"
                                     if p["buy_code"] else "⚪ 無不同類健康低基期標的"),
        "買方類別": p.get("buy_cat") or "—",
        "買方 σ": p["buy_sigma"],
        "買方 4D": p["buy_grade"],
        "買方操盤評分": p["buy_score"],
        "潛在差價%": p["potential_pct"],
    } for p in _pairs]

    _out = pd.DataFrame(_disp)
    st.dataframe(_out, use_container_width=True, hide_index=True)
    _n_ok = sum(1 for p in _pairs if p["buy_code"])
    st.caption(f"共 {len(_pairs)} 檔高基期;其中 **{_n_ok}** 檔有**不同類別**健康低基期可換。"
               "「潛在差價%」= 買方回到自己期間高點的漲幅(僅參考,非保證)。")

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
        st.caption(f"⬜ 輪動配對資料組建失敗:[{type(e).__name__}] {str(e)[:80]}")
        return
    _render_pairs_ui(rows, key_prefix=key_prefix, offer_download=False)


def render_rotation_section_from_df(df) -> None:
    """🔄 批次分頁:用已算好的組合健診大表 df 渲染輪動配對(不重抓)+ 獨立 CSV 下載。"""
    if df is None or getattr(df, "empty", True):
        return
    _render_pairs_ui(rows_from_batch_df(df), key_prefix="batch_rot_", offer_download=True)
