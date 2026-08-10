"""ui/tab6_manual.py — 系統說明書 Tab（v18.117 B-C.1）

從 app.py 抽出 Tab6（系統說明書）的渲染邏輯 — 純靜態 markdown / 表格內容、零 runtime
狀態依賴（不讀 session_state、不呼叫 services），是驗證「with tab: → render_xxx()」
重構 pattern 最理想的 PoC 對象。

對外 API：
- render_manual_tab() -> None

設計：
- 純函式（無參數）：完全自包含
- 內部使用 streamlit + pandas（caller 端 `with tab6:` context 之內被呼叫）
- 10 個 sub-tab：Macro Score / 景氣天氣 / 健診評等 4D / 吃本金 / 再平衡 /
  核心衛星 / 汰弱留強 / Sheet 資料結構 / 全局指標關聯地圖 / 宏觀教學文獻

⚠️ **本檔的鐵律：只寫「畫面上真的跑得出來」的算法。**
說明書寫了但系統沒實作的章節，會讓使用者拿著對不上的公式回頭懷疑自己的判讀，
比沒有說明書更糟。原「台股市場轉折點水溫」整章已移除（權重常數存在但零計算零渲染）；
原「六因子評等 / 系統性風險係數分類 / 汰弱 60 分公式」已改寫成實際生效的算法。
新增章節前請先 grep 確認該公式在 production 有 caller。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from shared.colors import GH_BG_HOVER, GH_BG_PRIMARY, GH_BORDER, GH_FG_PRIMARY, GRAY_BB, MATERIAL_ORANGE, MATERIAL_RED, MD_BLUE_300, STREAMLIT_BG, TRAFFIC_NEUTRAL


def render_manual_tab() -> None:
    """渲染系統說明書 Tab — 10 sub-tab 公式與判斷標準完整說明。"""
    st.markdown("## 📖 系統說明書 — 公式與判斷標準完整說明")
    st.caption("📖 故事附錄・公式聖經：拆解前 4 站每個評分模型、公式與指標的算法，讓進階使用者看懂決策邏輯。")

    # ════════════════════════════════════════════════════════════
    # v19.131 Section ⓪ — 📊 資料來源完整地圖
    # User 2026-06-25 反饋:「說明書要把前面所用到的資料,作完整的說明」
    # 一張總表列出每筆資料 → 用在哪個 Tab → 來源 endpoint → refresh 頻率 → fallback chain
    # ════════════════════════════════════════════════════════════
    # 摺疊處置(原則 1):這張總表是說明書的第一張「資料在哪裡」對照表,原本包在一層
    # 永遠展開的摺疊殼裡 —— 殼不承載資訊,只多一圈邊框和「可以收起來」的假暗示。
    # 改成標題 + container,表格直接攤平。
    st.markdown("### ⓪ 📊 資料來源完整地圖(每筆資料→Tab→endpoint→refresh→fallback)")
    with st.container():
        st.caption(
            "本系統 4 個資料 Tab 用到的所有資料來源,按「**資料項目 → 用在哪個 Tab → 來源 / endpoint "
            "→ refresh / 發布延遲 → 失敗 fallback**」整理。**任一筆失敗都會在 🔭 資料診斷(「參考 / 診斷」分頁內) "
            "用紅燈標出**。對照 `CLAUDE.md §2.1 SSOT` 5-Tier 權威分級。"
        )

        _data_map = [
            # (資料項目, 用在 Tab, 來源 / endpoint, refresh / 延遲, Fallback chain)
            ("📈 美國總經 12 指標", "🌐 Tab1",
             "FRED API(NAPM/DGS10/DGS2/DGS3MO/BAMLH0A0HYM2/M2SL/WALCL/CPIAUCSL/FEDFUNDS/UNRATE/PPIACO/UMCSENT)",
             "FRED:1800s / 月後 ~13 天(CPI/NFP 有修正風險)",
             "FRED 失敗 → DBnomics → MacroMicro HTML"),
            ("📊 市場行情 4 項",   "🌐 Tab1",
             "Yahoo Chart REST (^VIX / RSP / SPY / DX-Y.NYB / HG=F)",
             "Yahoo:3600s / EOD 16:00 ET ≈ 翌日 04:00 TW",
             "Yahoo 失敗 → FRED VIXCLS"),
            ("🚨 拐點 5 指標",     "🌐 Tab1",
             "FRED(SAHMREALTIME / DRTSCILM / ICSA / HSN1F / PERMIT)",
             "週/月頻 ｜ 月後 ~5-30 天",
             "FRED 主源,無備援(失敗會在拐點偵測 ⚠️ 卡顯示)"),
            ("🇨🇳 中國拖累 modifier", "🌐 Tab1",
             "FRED(CNCPIALLMINMEI / IRLTCT01CNM156N / MYAGM3CNM189N / XTEXVA01CNM664S)",
             "月頻,90 天 cache fallback",
             "全敗 → modifier = 1.0 中性"),
            ("📰 RSS 新聞(5 source)", "🌐 Tab1 + Tab3",
             "MarketWatch / Yahoo Finance / CNBC × 2 / BBC World",  # v19.295: FT/Investing.com/Bloomberg removed (blocked/subscription)
             "即時(數秒-分鐘)",
             "個別 RSS 失敗 → 其他源繼續"),
            ("💰 基金 NAV 歷史",   "🔍 Tab2 + 💊 Tab3 + 📊 Tab4",
             "MoneyDJ NAV 頁(yp401000 / tcbbankfund / chubb 子網域)",
             "T+1 ~ T+3,30min cache",
             "MoneyDJ 子網域 → TDCC openapi → FundClear → cnyes"),
            ("📝 基金 Meta(經理 / 規模 / TER)", "🔍 Tab2",
             "MoneyDJ wb01 / wb05 / wb07 + SITCA / Morningstar",
             "1 hour",
             "wb01 失敗 → wb05 → cnyes meta"),
            ("💵 基金配息歷史",     "🔍 Tab2 + 💊 Tab3 + 📊 Tab4",
             "MoneyDJ wh06_4 配息明細頁",
             "1 hour",
             "MoneyDJ 失敗 → cnyes dividend API"),
            ("📦 基金前 10 大持股",  "🔍 Tab2 + 💊 Tab3",
             "MoneyDJ wh06_3 持股明細頁",
             "1 day",
             "MoneyDJ 失敗 → fund meta 內 holdings.top_holdings 欄"),
            ("💱 USDTWD 匯率",      "📊 Tab4",
             "Yahoo USDTWD=X + FRED USDTWD",
             "10 min(intraday)",
             "Yahoo → FRED → manual cache"),
            ("📋 Google Sheet 政策", "📊 Tab4",
             "Google Sheets API(policy_funds 分頁)",
             "1 min cache(寫後立即讀)",
             "OAuth 失敗 → 需 Tab4 重連授權"),
            ("🤖 AI 摘要",           "🌐 Tab1 + 💊 Tab3 + 📊 Tab4",
             "Google Gemini API(EX-AI-1 例外,回 str 而非 dataclass)",
             "On-demand(無 cache)",
             "GEMINI_KEY 未設 → AI 區塊跳過(不擋畫面)"),
            ("🇹🇼 FinMind macro",    "🌐 Tab1(輔助)",
             "NDC 景氣燈號:FinMind TaiwanBusinessIndicator｜TW PMI:9 源賽跑",  # v19.387 V1:更正 — TaiwanMacroEconomics 不存在(v19.342)
             "月後 5-10 天",
             "FinMind quota 用罄 → 跳過(非主源)"),
            ("📊 AAII Sentiment",    "🌐 Tab1(F-H1)",
             "AAII 官網 HTML(bull/bear ratio)",
             "週頻",
             "AAII 失敗 → 拐點桶不參考此項"),
        ]

        _dm_th = (f"font-size:10px;color:{TRAFFIC_NEUTRAL};font-weight:700;padding:8px 10px;"
                  f"border-bottom:1px solid {GH_BORDER}")
        _dm_td = "font-size:11px;padding:8px 10px;line-height:1.4"
        _dm_html = (
            f"<div style='display:grid;grid-template-columns:1.5fr 1.2fr 2.5fr 1.5fr 2.3fr;"
            f"background:{GH_BG_PRIMARY};border-radius:6px 6px 0 0'>"
            f"<span style='{_dm_th}'>資料項目</span>"
            f"<span style='{_dm_th}'>用在 Tab</span>"
            f"<span style='{_dm_th}'>來源 / endpoint</span>"
            f"<span style='{_dm_th}'>Refresh / 延遲</span>"
            f"<span style='{_dm_th}'>Fallback chain</span>"
            f"</div>"
        )
        for _item, _tab, _src, _ref, _fb in _data_map:
            _dm_html += (
                f"<div style='display:grid;grid-template-columns:1.5fr 1.2fr 2.5fr 1.5fr 2.3fr;"
                f"background:{GH_BG_PRIMARY};border-bottom:1px solid {GH_BG_HOVER}'>"
                f"<span style='{_dm_td};color:{GH_FG_PRIMARY};font-weight:600'>{_item}</span>"
                f"<span style='{_dm_td};color:#79c0ff'>{_tab}</span>"
                f"<span style='{_dm_td};color:{GRAY_BB};font-family:monospace;font-size:10px'>{_src}</span>"
                f"<span style='{_dm_td};color:{TRAFFIC_NEUTRAL}'>{_ref}</span>"
                f"<span style='{_dm_td};color:#a5d6ff;font-size:10px'>{_fb}</span>"
                f"</div>"
            )
        st.markdown(
            f"<div style='border:1px solid {GH_BORDER};border-radius:6px;overflow:hidden'>"
            f"{_dm_html}</div>", unsafe_allow_html=True,
        )
        st.caption(
            "**📖 對應憲法**:`CLAUDE.md §2.1 SSOT`(5-Tier 權威分級)、`§2.3 PIT`(發布延遲表)、"
            "`§2.4 Freshness`(TTL 對照)、`§4.6` 領域邊界(基金特有狀態)。"
            " **任一筆紅燈 → 🔭 資料診斷(「參考 / 診斷」分頁內)找對應 fetcher 修。**"
        )
    # ════════════════════════════════════════════════════════════

    # ── v18.272: 📋 曾經查過的基金清單（Tab2 + Tab3 自動記錄）─
    # ── v18.280: 加 CSV 上傳還原（reboot 後從備份 CSV merge 回來）─
    # ── v18.282: 加預設常用基金 + 手動新增表單 ─
    # 摺疊處置(原則 1):同上 —— 這是一份**清單資料**(含手動新增表單與 CSV 還原),
    # 永遠展開的殼等於沒有殼。改成標題 + container。
    st.markdown("### 📋 曾經查過的基金標的清單（Tab2 / Tab3 自動記錄 + 預設）")
    with st.container():
        from services.fund_history import (
            clear_history as _clear_fh,
            export_preset_funds_json as _export_preset_json,
            get_history_df as _hist_df,
            import_from_csv as _import_fh,
            is_preset as _is_preset,
            promote_to_preset as _promote_preset,
            record_fund as _rec_fh_manual,
        )

        # 手動新增表單
        with st.form("_fh_add_form", clear_on_submit=True):
            _add_c1, _add_c2, _add_c3 = st.columns([1, 2, 1])
            _new_code = _add_c1.text_input(
                "基金代號", placeholder="例：ACCP138",
                key="_fh_new_code",
            )
            _new_name = _add_c2.text_input(
                "基金名稱（可選）", placeholder="例：聯博全球高收益基金",
                key="_fh_new_name",
            )
            _add_c3.markdown("&nbsp;", unsafe_allow_html=True)  # 對齊
            _submitted = _add_c3.form_submit_button(
                "➕ 加入清單", use_container_width=True,
            )
            if _submitted and _new_code.strip():
                _rec_fh_manual(_new_code.strip(), _new_name.strip(), source="manual")
                st.success(f"✅ 已加入 {_new_code.strip().upper()}")
                st.rerun()

        _df_fh = _hist_df()
        _fh_up = st.file_uploader(
            "📥 上傳之前下載的 fund_history.csv 還原紀錄（reboot 後第一件事）",
            type=["csv"],
            key="_fh_upload",
            help="紀錄會與當前清單 merge：同代號疊代次數 + 聯集來源 + 取較早 first / 較晚 last",
        )
        if _fh_up is not None:
            _ret = _import_fh(_fh_up.getvalue())
            if _ret["errors"]:
                st.error("、".join(_ret["errors"]))
            else:
                st.success(
                    f"✅ 還原成功：新增 {_ret['imported']} 檔、merge {_ret['merged']} 檔。"
                )
            _df_fh = _hist_df()
        if _df_fh.empty:
            st.info(
                "尚未查過任何基金。在「🔍 個基深掘」抓取後 / 「📦 組合基金」載入後，"
                "代號與名稱會自動寫入此清單。"
            )
        else:
            _fh_c1, _fh_c2, _fh_c3 = st.columns([2, 1, 1])
            _fh_c1.caption(f"📊 共 **{len(_df_fh)}** 檔唯一基金（依最近查詢時間排序）")
            _fh_csv = _df_fh.to_csv(index=False).encode("utf-8-sig")
            _fh_c2.download_button(
                "💾 下載 CSV",
                _fh_csv,
                file_name="fund_history.csv",
                mime="text/csv",
                use_container_width=True,
                key="_fh_dl_csv",
            )
            if _fh_c3.button("🗑️ 清空紀錄", use_container_width=True, key="_fh_clear"):
                _clear_fh()
                st.rerun()
            st.dataframe(_df_fh, use_container_width=True, hide_index=True)

            # ── v18.290: 點代碼自動複製（手機 tap 即複製）─
            # v18.293 hotfix: get_history_df() 欄名是中文「代號/名稱」非英文 code/name
            # 容錯：兩個欄名都接受（避免未來改 schema 再炸）
            _code_col = "代號" if "代號" in _df_fh.columns else (
                "code" if "code" in _df_fh.columns else None
            )
            _name_col = "名稱" if "名稱" in _df_fh.columns else (
                "name" if "name" in _df_fh.columns else None
            )
            if _code_col is None:
                st.caption(f"⚠️ 找不到代號欄（df columns: {list(_df_fh.columns)}）")
                _codes_list = []
            else:
                st.markdown("**📋 點下方任一代號的右側 📋 icon 即可複製**")
                _codes_list = _df_fh[_code_col].astype(str).str.upper().tolist()
                # 多欄並排省空間（每 4 個一排）
                _per_row = 4
                for _i in range(0, len(_codes_list), _per_row):
                    _cols = st.columns(_per_row)
                    for _j, _code in enumerate(_codes_list[_i:_i + _per_row]):
                        with _cols[_j]:
                            st.code(_code, language=None)

            # ── v18.290: ⭐ 升等為預設（寫回 config/preset_funds.json）─
            st.markdown("---")
            st.markdown("**⭐ 升等為預設清單**（reboot 後仍存在）")
            _promo_c1, _promo_c2, _promo_c3 = st.columns([2, 2, 1])
            _candidates = [c for c in _codes_list if not _is_preset(c)]
            if not _candidates:
                _promo_c1.caption("✅ 清單裡所有基金都已是預設了")
            else:
                _sel_code = _promo_c1.selectbox(
                    "選一檔基金",
                    options=_candidates,
                    key="_fh_promote_sel",
                    label_visibility="collapsed",
                )
                # 取對應 name（從 df 找最新一筆）
                _sel_name = ""
                if _code_col and _name_col:
                    _row_match = _df_fh[
                        _df_fh[_code_col].astype(str).str.upper() == _sel_code
                    ]
                    if not _row_match.empty:
                        _sel_name = str(_row_match.iloc[0].get(_name_col, "") or "")
                _promo_c2.text_input(
                    "基金名稱（會寫進 JSON）",
                    value=_sel_name,
                    key="_fh_promote_name",
                    label_visibility="collapsed",
                )
                if _promo_c3.button(
                    "⭐ 升等", use_container_width=True, key="_fh_promote_btn",
                ):
                    _r = _promote_preset(
                        _sel_code,
                        st.session_state.get("_fh_promote_name", _sel_name),
                    )
                    if _r["errors"]:
                        st.error("、".join(_r["errors"]))
                    elif _r["already"]:
                        st.info(f"ℹ️ {_sel_code} 已在預設清單，名稱已更新")
                    else:
                        st.success(
                            f"✅ 已升等 {_sel_code} → 預設清單共 {_r['total']} 檔。"
                            "**記得下方按「💾 下載 preset_funds.json」並 commit 回 repo，"
                            "否則 Cloud reboot 後會消失！**"
                        )
                    st.rerun()

            # 下載最新 preset_funds.json 給 user commit
            _preset_json_bytes = _export_preset_json()
            st.download_button(
                "💾 下載 preset_funds.json（reboot 持久化必做）",
                _preset_json_bytes,
                file_name="preset_funds.json",
                mime="application/json",
                use_container_width=True,
                key="_fh_dl_preset_json",
                help="升等後務必下載此檔 → 取代 repo 的 config/preset_funds.json → git commit + push",
            )
        st.caption(
            "💡 **內建預設常用基金永遠在**（即使 cache 被清空也會看到，來源標 `preset`）。"
            "user 抓過 / 手動加的紀錄存於容器內 `cache/fund_history.json`，"
            "**Streamlit Cloud 重啟容器時這部分會清空** → 用「下載 CSV → reboot 後上傳 CSV」雙保險。"
        )

    # ── v18.288：🗄️ NAV 歷史資料管理（CSV 匯入 / 匯出 / 增量更新）─
    with st.expander("🗄️ NAV 歷史資料管理（CSV 上傳當基底 + 系統增量更新）", expanded=False):
        from services.nav_history_store import (
            clear_cache as _nh_clear,
            export_nav_csv as _nh_export,
            get_cache_status as _nh_status,
            import_nav_csv as _nh_import,
            incremental_update as _nh_update,
        )
        st.caption(
            "💡 **架構**：user 從 CnYES / MoneyDJ 手動下載完整歷史 CSV → 上傳這裡 → "
            "系統存進 `cache/nav_history/{code}.json`。**系統計算長期報酬 / 健診時會優先讀 cache**，"
            "確保歷史完整。後續按「🔄 增量更新」只抓最新幾天疊代上去（不重抓 5 年）。"
        )
        st.caption(
            "⚠️ 不同網站基金代碼不同！MoneyDJ 用內部碼（ACTI94）、CnYES 可能用 ISIN（LU0xxx）。"
            "上傳後此 cache 用你自己的 code 為 key，不依賴爬蟲。"
        )

        _nh_c1, _nh_c2 = st.columns([1, 2])
        _nh_code = _nh_c1.text_input(
            "基金代號", placeholder="ACTI94", key="_nh_code",
            help="這個 code 同時是 cache key + 對應 fetch_nav 增量更新時的 MoneyDJ 代碼",
        ).strip().upper()
        _nh_file = _nh_c2.file_uploader(
            "📥 上傳 NAV CSV（欄位：date + nav，支援西元/民國 + 中英文欄名）",
            type=["csv"], key="_nh_upload_csv",
        )

        if _nh_code:
            _status = _nh_status(_nh_code)
            if _status["exists"]:
                st.success(
                    f"✅ Cache 已有 {_status['count']:,} 筆 "
                    f"({_status['date_min']} ~ {_status['date_max']}，"
                    f"涵蓋 {_status['years_covered']} 年)"
                )
            else:
                st.info(f"ℹ️ {_nh_code} 尚無 cache，請上傳 CSV 建立基底")

            if _nh_file is not None:
                _r = _nh_import(_nh_code, _nh_file.getvalue())
                if _r["errors"]:
                    st.error("、".join(_r["errors"]))
                else:
                    st.success(
                        f"✅ 匯入成功：新增 {_r['imported']:,} 筆、覆蓋 {_r['merged']:,} 筆 "
                        f"→ 總 {_r['total']:,} 筆 ({_r['date_min']} ~ {_r['date_max']})"
                    )
                    # v19.365 ④ 儲存收斂:磁碟 cache 在 Streamlit Cloud 重啟會清空 →
                    # 雙寫進 Google Sheet nav_history((code,date) 去重,重啟不丟;非致命)。
                    try:
                        from services.nav_history_gs import import_csv_text as _gs_import
                        _g = _gs_import(
                            _nh_code,
                            _nh_file.getvalue().decode("utf-8-sig", errors="replace"),
                            source="tab6_csv")
                        if _g["enabled"] and _g["written"]:
                            st.caption(f"🗂️ 已同步 {_g['written']} 筆到雲端 nav_history(重啟不丟)")
                        elif not _g["enabled"]:
                            st.caption("⬜ 雲端 nav_history 未啟用(缺 secrets)→ 本次僅存本機,"
                                       "容器重啟會清空(詳見 Tab5 狀態燈)")
                    except Exception as _e_gs:  # 雲端同步失敗不影響本機匯入結果
                        st.caption(f"⬜ 雲端同步失敗(本機已存):[{type(_e_gs).__name__}] "
                                   f"{str(_e_gs)[:60]}")
                    st.rerun()

            _act_c1, _act_c2, _act_c3 = st.columns(3)
            if _act_c1.button("🔄 從 MoneyDJ 增量更新", use_container_width=True,
                              key="_nh_update_btn", disabled=not _status["exists"]):
                with st.spinner("抓最新幾天 NAV 疊代到 cache..."):
                    _u = _nh_update(_nh_code)
                if _u["errors"]:
                    st.error("、".join(_u["errors"]))
                else:
                    st.success(
                        f"✅ fetch_nav 抓 {_u['fetched']} 筆，"
                        f"merge 新增 {_u['new_rows']} 筆，總 {_u['total']:,} 筆"
                    )
                    st.rerun()

            if _status["exists"]:
                _csv_bytes = _nh_export(_nh_code)
                _act_c2.download_button(
                    "📤 下載當前 cache 為 CSV", _csv_bytes,
                    file_name=f"nav_{_nh_code}.csv", mime="text/csv",
                    use_container_width=True, key="_nh_dl_btn",
                )
                if _act_c3.button("🗑️ 清除 cache", use_container_width=True,
                                  key="_nh_clear_btn"):
                    _nh_clear(_nh_code)
                    st.rerun()

        st.caption(
            "🔧 **工作流程**：① 第一次去 [CnYES](https://fund.cnyes.com) 或 "
            "[MoneyDJ](https://www.moneydj.com/funddj/) 找到該基金 → 下載完整歷史 CSV → "
            "上傳到此 → ② 之後每週按「🔄 增量更新」自動抓最新疊代 → "
            "③ reboot 前按「📤 下載」備份 → reboot 後重新上傳即還原。"
        )

    st.divider()

    _t6 = st.tabs([
        "🧮 1. Macro Score",
        "🌤️ 2. 景氣天氣",
        "🏆 3. 健診評等 4D",
        "🔴 4. 吃本金診斷",
        "⚖️ 5. 再平衡公式",
        "🛡️⚡ 6. 核心衛星",
        "🔄 7. 汰弱留強",
        "📋 8. Sheet 資料結構",
        "🗺️ 9. 全局指標關聯地圖",
        "📚 10. 宏觀教學文獻",
    ])

    # ── 1. Macro Score ────────────────────────────────────────────
    with _t6[0]:
        st.markdown("### ① 🧮 AI Macro Score — 加權景氣評分")
        st.markdown("""
**公式：**
```
Macro_Score = Σ(wᵢ × sᵢ) / Σ(wᵢ)  →  正規化到 0~10

score_normalized = (earned_score + total_weight) / (2 × total_weight) × 10
```
""")
        st.dataframe(pd.DataFrame([
            ["殖利率利差 10Y-2Y", "DGS10-DGS2",   2,   "±2",   "倒掛(<0)=-2，翻正=+2，>0.5=+1"],
            ["殖利率利差 10Y-3M", "DGS10-DGS3MO", 2,   "±2",   "倒掛=-2，翻正=+3（降息確認）"],
            ["PMI 製造業",        "NAPM",          2,   "±2",   ">50=+2，45~50=-1，<45=-2"],
            ["HY 信用利差",       "BAMLH0A0HYM2", 2,   "±2",   "<4%=+2，4~6%=0，>6%=-2"],
            ["M2 流動性",         "M2SL",          1,   "±1",   ">5%=+1，<0%=-1"],
            ["市場廣度 RSP/SPY",  "RSP/SPY",       1,   "±1",   "月漲>0.5%=+1，月跌>1%=-1"],
            ["DXY 美元指數",      "DX-Y.NYB",      1,   "±1",   "月跌>1%=+1（弱美元利多），月漲>2%=-1"],
            ["Fed 資產負債表",    "WALCL",          1,   "±1",   "擴表>5%=+1，縮表<-5%=-1"],
            ["VIX 恐慌指數",      "^VIX",           1,   "±1",   "<18=+1（平靜），>30=-1（恐慌）"],
            ["CPI 通膨率",        "CPIAUCSL",      0.5, "±0.5", "1~2.5%=+0.5，>4%=-0.5"],
            ["Fed Rate",          "FEDFUNDS",      0.5, "±0.5", "降息=+0.5，>5%=-0.5"],
            ["失業率",             "UNRATE",        0.5, "±0.5", "<4.5%=+0.5，>6%=-1"],
            ["PPI 生產者物價",    "PPIACO",         0.5, "±0.5", "0~3%=+0.5，>5%=-0.5"],
            ["銅博士",             "HG=F",           0.5, "±0.5", "月漲>2%=+0.5，月跌>5%=-0.5"],
        ], columns=["指標", "FRED/Ticker", "權重(w)", "分值範圍", "評分邏輯"]),
            use_container_width=True, hide_index=True,
            column_config={
                "指標": st.column_config.TextColumn("指標", width="medium"),
                "FRED/Ticker": st.column_config.TextColumn(
                    "FRED/Ticker", width="small", help="FRED series ID 或 Yahoo ticker"),
                "權重(w)": st.column_config.NumberColumn(
                    "權重(w)", format="%.1f",
                    help="加權分子/分母都用它；可被校準檔覆寫，實際值以 Tab1 明細為準"),
                "分值範圍": st.column_config.TextColumn("分值範圍", width="small"),
                "評分邏輯": st.column_config.TextColumn("評分邏輯", width="large"),
            })
        st.warning(
            "⚠️ **上表是「主要指標」節選，不是完整清單，也不要拿它自己加總對答案。**\n\n"
            "實際參與計分的指標數比上表多（包含權重最高的 **薩姆規則 SAHM** 與 "
            "**SLOOS 銀行放貸標準** 兩個衰退預警因子），而且每項權重可以被校準檔覆寫。\n\n"
            "👉 **要對帳請看 Tab1 的「完整指標加扣分明細」**"
            "（本說明書最後一個分頁「📚 宏觀教學文獻」的 § D 也有同一份），"
            "那裡是**當下實際生效**的指標、權重與加扣分，會隨資料與校準即時變動。"
        )
        st.markdown("""
**景氣位階對應：**
| Score | 位階 | 建議股債現金 |
|-------|------|------------|
| 8~10  | 🔴 高峰 | 股 35% / 債 45% / 現金 20% |
| 5~7   | 🟢 擴張 | 股 60% / 債 30% / 現金 10% |
| 3~4   | 🔵 復甦 | 股 40% / 債 40% / 現金 20% |
| 0~2   | 🟡 衰退 | 股 20% / 債 50% / 現金 30% |
""")

    # ── 2. 景氣天氣 ───────────────────────────────────────────────
    with _t6[1]:
        st.markdown("### ② 🌤️ 總經天氣預報 — Score → 天氣映射")
        st.markdown("""
**公式：**
```
Score ≥ 7  → ☀️ 晴天（建議股票為主）
4 ≤ Score < 7 → ⛅ 多雲（均衡配置）
Score < 4  → ⛈️ 暴雨（防禦為主）
```

| 天氣 | Score 範圍 | 建議配置 | 行動 |
|------|----------|---------|------|
| ☀️ 晴天 | ≥ 7 | 股多債少 | 增加衛星部位，持有成長型基金 |
| ⛅ 多雲 | 4~6 | 股債均衡 | 維持核心配置，輕倉衛星 |
| ⛈️ 暴雨 | < 4 | 債多現金多 | 啟動防禦，核心配息資產優先 |
""")

    # ── 3. 健診評等 4D（實際生效的評等模型）────────────────────────
    with _t6[2]:
        st.markdown("### ③ 🏆 基金健診評等（4 維健康度）")
        st.info(
            "📌 **你在 Tab2 / Tab3 看到的 A/B/C/D/F 評等，就是這一套。**"
            "說明書舊版寫的「六因子評分（Sharpe / Sortino / MaxDD / Calmar / Alpha / 費用率）"
            "→ 0~100 分 → A/B/C/D」**已不再用於評等**，見下方「六因子現在的角色」。"
        )
        st.markdown("""
**公式：**
```
四維各自 0~100 分 → 綜合分 = 算得出來的維度取「算術平均」（不加權）

Grade：A ≥ 80 ／ B ≥ 65 ／ C ≥ 50 ／ D ≥ 35 ／ F < 35
```
""")
        st.dataframe(pd.DataFrame([
            ["💵 1. 配息健康度（Coverage）", "含息總報酬 ÷ 年化配息率 —— 配息是不是「賺來的」",
             "≥1.5→95　≥1.2→80　≥1.0→65　≥0.5→40　<0.5→15",
             "MoneyDJ wb01 含息報酬 ÷ wb05 年化配息率"],
            ["📈 2. 風險調整報酬（Sharpe）", "每承擔一單位波動換到多少超額報酬",
             "≥1.5→95　≥1.0→80　≥0.5→60　≥0→40　<0→15",
             "MoneyDJ wb07 風險表；缺則本地淨值自算"],
            ["📊 3. 走勢健康（MA 方向 + 報酬）", "60 日均線在走升還是走跌，搭配 1Y 報酬正負",
             "均線升+正報酬→85　只有均線升→70　只有均線跌→45　均線跌+負報酬→25",
             "淨值序列 60 日移動平均"],
            ["🛡️ 4. 低波動性（σ）", "年化標準差，越低越穩（**不是**越低越好賺）",
             "<10%→90　<15%→75　<20%→55　<30%→35　≥30%→15",
             "近一年日報酬年化標準差"],
        ], columns=["維度", "在問什麼", "分數對應", "資料來源"]),
            use_container_width=True, hide_index=True,
            column_config={
                "維度": st.column_config.TextColumn("維度", width="medium"),
                "在問什麼": st.column_config.TextColumn("在問什麼", width="large"),
                "分數對應": st.column_config.TextColumn("分數對應", width="large"),
                "資料來源": st.column_config.TextColumn("資料來源", width="medium"),
            })
        st.markdown("""
**Grade 等級：**
| Score | Grade | 評語 |
|-------|-------|------|
| ≥ 80 | **A** | ✅ 健康優質基金 |
| 65~79 | **B** | 🟢 表現穩健 |
| 50~64 | **C** | 🟡 中性，持續觀察 |
| 35~49 | **D** | 🟠 警示偏弱 |
| < 35 | **F** | 🔴 多項警示 |
| — | **—** | ⬜ 資料不足以評等 |

**⬜「資料不足以評等」的判準（重要）：**
四維裡**算得出來的維度數不足**，或**配息健康度與 Sharpe 兩個核心維度都缺**時，
系統**不給評等**，顯示「—」。
> 為什麼要這條：只靠單一維度（例如只有 σ 算得出來 → 90 分）就評 A「健康優質」，
> 會把資料稀疏的基金排在資料完整的基金**之上**。寧可誠實說不知道，也不給假評等。

**六因子現在的角色：**
Sortino（只罰下行波動）／ Calmar（報酬÷最大回撤）／ Alpha（含息報酬−配息率）／
費用率 這四項，4D 沒有涵蓋，仍會在「健診詳表」當**對照欄**單獨顯示，
但**不參與 A/B/C/D 評等**。
""")

    # ── 4. 吃本金診斷 ─────────────────────────────────────────────
    with _t6[3]:
        st.markdown("### ④ 🔴 吃本金診斷（Capital Return Detection）")
        st.markdown("""
**策略3 以息養股核心公式：**
```
吃本金判斷：含息總報酬(wb01 1Y) < 年化配息率(wb05)
```

**資料來源優先序：**
| 數據 | 優先來源 | 備援 |
|------|---------|------|
| 含息報酬率 | MoneyDJ **wb01**（含息實績） | 淨值漲跌% + 配息率 |
| 年化配息率 | MoneyDJ **wb05**（官方值） | 自算：近12月配息/平均淨值 |

**燈號：**
- 🟢 **健康**：含息報酬率 ≥ 配息率（有淨值成長作支撐）
- 🟡 **警示**：含息報酬率略低於配息率（正在侵蝕本金）
- 🔴 **吃本金**：含息報酬率 << 配息率（配息主要來自本金返還）

**實例：**
```
安聯收益成長：含息1Y = +5.2%，配息率 = 9.6%
  → 差距 -4.4%，代表每年淨值被侵蝕 4.4%
  → 繼續持有10年後，本金將大幅減損
```
""")

    # ── 5. 再平衡公式 ─────────────────────────────────────────────
    with _t6[4]:
        st.markdown("### ⑤ ⚖️ 再平衡公式（One-Click Rebalance）")
        st.markdown("""
**策略3 再平衡差額計算：**
```
Action_i = (Total_Portfolio × Target_Weight_i) - Current_Value_i
```

**觸發條件（策略3 標準）：**
| 偏離程度 | 動作 |
|---------|------|
| < 5%   | ✅ 配置正常，無需再平衡 |
| 5~10%  | ⚠️ 建議再平衡（下次配息時執行） |
| > 10%  | 🚨 必須執行再平衡 |

**白話文行動指南生成邏輯：**
```
偏移方向 = 目前核心% - 目標核心%

> 0 → 核心太多：從「最大衛星基金」贖回 ΔNT$，轉入「最小核心基金」
< 0 → 衛星太多：從「最大核心基金」獲利了結 ΔNT$，轉入「最小衛星基金」
```
偏離金額 = |偏移%| × 總投入金額
""")

    # ⚠️ 原第 6 章「台股市場轉折點水溫」整章已移除（詳見本檔 module docstring 鐵律）。
    # 移除理由（原則 3「一直抓不到又不影響判斷的 → 移除」）：
    #   (a) 全站零計算零渲染 —— 該指標的三個權重常數只有「定義 → import →
    #       re-export」三處，沒有任何函式算出它，也沒有任何畫面顯示水溫，
    #       使用者讀完整章回畫面找不到對應顯示；
    #   (b) 常數的語意（business / financial / monetary）與原章寫的
    #       市場寬度 / 外資淨買 / 貨幣動能三因子對不起來，就算日後實作也不會是
    #       那個公式，留著等於保證錯誤；
    #   (c) 標「規劃中」會佔掉一個 sub-tab 的版面卻零資訊量。
    # 若日後真要做，請先確定資料源與公式，再重新寫章節（不要直接還原原文）。

    # ── 6. 核心衛星分類 ──────────────────────────────────────────
    with _t6[5]:
        st.markdown("### ⑥ 🛡️⚡ 核心/衛星分類邏輯")
        st.markdown("**優先序：手動設定 > 關鍵字比對 > 預設（衛星）**")
        st.dataframe(pd.DataFrame([
            ["🛡️ 核心", "債、收益、配息、平衡、高息、公用、多元、income、bond、dividend、balanced"],
            ["⚡ 衛星", "AI、科技、半導體、成長、主題、印度、越南、生技、醫療、能源、tech、growth"],
        ], columns=["分類", "觸發關鍵字（基金名稱含有任一）"]),
            use_container_width=True, hide_index=True,
            column_config={
                "分類": st.column_config.TextColumn("分類", width="small"),
                "觸發關鍵字（基金名稱含有任一）": st.column_config.TextColumn(
                    "觸發關鍵字（基金名稱含有任一）", width="large",
                    help="基金名稱只要含有其中任一詞就歸該類；核心關鍵字優先比對"),
            })
        st.markdown("""
**優先序細節（Tab3「① 配置總覽」「Hero 甜甜圈」「保單分組」三處同一把尺）：**
1. Google Sheet 保單分頁的 **`policy_tier`** 欄（填 `core` / `satellite`）—— 最高優先
2. 沒填 `policy_tier` → 用**基金名稱關鍵字**推定（上表）
3. 都不命中 → 歸「衛星」

**⚠️ 比例分母是「金額」不是「檔數」：**
```
核心資產比例 = Σ(核心基金投入本金 TWD) ÷ Σ(全部基金投入本金 TWD) × 100%
```
3 檔核心 / 5 檔總計 = 檔數 60%，但那 3 檔若持有 90% 的錢 → **配置比例是 90%**。
畫面上「⚖️ 核心/衛星檔數」那格是檔數口徑（只回答幾檔），
「🛡️ 核心資產比例」與甜甜圈才是金額口徑（決定要不要再平衡）。

**核心/衛星比例目標：**
```
核心資產：提供穩定現金流（每月配息），作為「養」衛星的資金來源
衛星資產：追求價差成長，由核心配息「養」，不動用本金
```
目標值**由你自己決定** —— Tab3 下方「⚙️ 組合設定」的核心比例 slider
（`portfolio_core_pct`，初始值 75%）。全站所有「目標偏差」都讀這一個值，
說明書不另訂數字。
偏離 >5% → ⚠️ 建議再平衡　|　偏離 >10% → 🚨 必須執行
""")

    # ── 7. 汰弱留強評分 ──────────────────────────────────────────
    with _t6[6]:
        st.markdown("### ⑦ 🔄 汰弱留強（同類 PK）")
        st.info(
            "📌 這一章對應 Tab3「🩺 基金體檢表」的「體檢判定」欄，"
            "以及 Tab2 個基深掘的「四分位」燈號。**兩者判準不同、資料源不同**，"
            "下面分開講。舊版說明書寫的「汰弱分數 = 含息報酬×40% + Sharpe×30% + 費用率×30%，"
            "低於 60 分汰換」**系統從未實作**，已移除。"
        )
        st.markdown("""
#### A. 組合體檢表的「汰弱候選」— 超額報酬（pp）

**這是 Tab3 實際亮 ⚠️ 的判準：**
```
超額(pp) = 該基金近 1Y 含息報酬(%) − 同類型平均近 1Y 報酬(%)

超額 ≥ +2 pp  → 🏆 優等生（抱緊滾雪球）
−2 < 超額 < +2 → 🟡 普通生
超額 ≤ −2 pp  → ⚠️ 汰弱候選
同類平均抓不到 → ⬜ 不評（不猜、不給假判定）
```
| 欄位 | 資料源 |
|------|--------|
| 近 1Y 含息報酬 | MoneyDJ wb01（含息實績）；缺則淨值漲跌% + 配息率 |
| 同類型平均 | MoneyDJ 績效評比頁「同類型平均」欄；**約 3 成基金抓不到** |

> **pp（percentage point）不是 %**：兩個百分比相減的差額用 pp。
> 報酬 8% vs 同類 5% → 超額 **+3 pp**（不是 +60%）。

#### B. 個基深掘的「四分位」— Sharpe vs 同類

Tab2 對單一基金另有一組四分位燈號，比的是**風險調整後報酬（Sharpe）**，
不是報酬本身：

| 等級 | 判準 | 含義 |
|------|------|------|
| 第 1 四分位 🏆 | Sharpe ≥ 同類 75 百分位 | 同類最強 |
| 第 2 四分位 ✅ | Sharpe ≥ 同類平均 | 中上 |
| 第 3 四分位 ⚠️ | Sharpe ≥ 同類 25 百分位 | 中下，開始觀察 |
| 第 4 四分位 🔴 | Sharpe < 同類 25 百分位 | 後 25%，警戒 |

#### C. 系統**不會**幫你做的事（要人工判斷）

- **「連續 2 季落後」不會被自動追蹤** —— 系統沒有存季度歷史，
  每次看到的都是「當下這一期」。要判斷是否連續，請自己記錄或看 Tab6 的歷史紀錄。
- **費用率不參與汰弱判定** —— 費用率有抓（MoneyDJ），但只在健診詳表當對照欄顯示。
- **吃本金（含息報酬 < 配息率）是獨立的紅燈**，見第 ④ 章；它不併進超額 pp 分數。

#### D. 實際操作原則（人工）
1. 每季看一次同類 PK 與四分位
2. 連續 2 季落後 → 啟動汰換計畫（給它一次機會）
3. 找好替換標的後，在「買點」時換（避免在高點換進）
4. 核心資產不輕易換（穩定配息 > 短期績效排名）
""")

    # ── 8. Sheet 資料結構（v18.169：從 Tab3 expander 搬移過來）─────────
    with _t6[7]:
        st.markdown("### ⑧ 📋 Sheet 資料結構（這本 Google Sheet 內的分頁長相）")
        st.error(
            "🚨 **刪分頁前先看這裡**：系統會用到的分頁**不是全部都以底線開頭**。"
            "特別是 **`nav_history`（沒有底線）存的是逐日累積的歷史淨值**，"
            "刪掉等於毀掉數年份的長期報酬 / 3Y / 5Y / 低基期判斷基礎，"
            "而且**無法從任何來源重建**（外部只抓得到近期淨值）。"
        )
        st.markdown("""
系統目前會讀寫**這 6 種分頁**，平時各動作（批次加入、T7 套用、CSV 匯入）會自動同步到對應分頁。
若不確定哪個按鈕同步什麼，請改用 Tab3 頂部「🚀 快速存讀面板」。

| 分頁 | 命名規則 | 用途 | 同步來源 | 可以刪嗎 |
|---|---|---|---|---|
| 📋 **保單分頁** | 自訂保單名稱 | 一張保單 = 一個分頁，放該保單下的基金清單 / 級別 / 幣別 / 本金 | Tab3「保單管理」批次加入 | ✅ 可自由增減（刪掉 = 刪掉那張保單） |
| 📄 **`Policies`** | 固定名稱、**無底線** | 舊版（v1）平面 schema：一列 = 一組（保單, 基金）。升級 v2 後仍保留供對照 | 舊版寫入路徑 | ⚠️ 已升級 v2 才可刪；不確定就別動 |
| 🗂️ **`nav_history`** | 固定名稱、**無底線** | **逐日累積的歷史淨值**（主鍵 = 代碼 + 日期）。長期報酬 / 3Y / 5Y / 低基期全靠它 | 每日自動累積 + Tab5「NAV 歷史匯入」+ Tab6 CSV 匯入 | 🚨 **絕對不要刪** |
| 📸 **`_T7_State`** | 固定底線開頭 | T7 持倉的單位數 / 平均成本 / 匯率快照，重啟 app 用此還原部位 | Tab3「T7 套用」自動寫入 | ❌ 不要刪 |
| 📜 **`_Ledgers`** | 固定底線開頭 | 所有 buy / sell / dividend 事件的流水帳（append-only） | Tab3 所有交易動作 | ❌ 不要刪 |
| 📊 **`_持倉總覽`** | 固定底線開頭 | 給**人看**的完整成本帳本（`_T7_State` 是機器格式，這張是可讀版） | 與 `_T7_State` 同時寫入 | ❌ 不要刪 |

**保護規則（更正版）：**
- ❌ 舊說明寫「只有底線開頭的分頁是系統保留」是**錯的** ——
  `Policies` 與 `nav_history` 都沒有底線，但都是系統分頁。
- ✅ **正確的判準**：只有「你自己命名的保單分頁」可以自由增減；
  上表其他 5 種一律不要手動改名或刪除。
- ✅ 想清資料時，請用 App 內的按鈕（Tab3「🗑️ 重置帳本」、Tab6「🗑️ 清空紀錄」），
  不要直接在 Google Sheet 上刪分頁 —— App 的按鈕知道哪些是衍生資料、哪些是原始紀錄。
- **`_T7_State` 是快照**：app 啟動時讀回來重建部位，是「最新狀態」。
- **`_Ledgers` 是流水**：所有交易事件按時序追加，永不刪改，是「歷史記錄」。
- **`nav_history` 是唯一不可再生的資料**：其他分頁的內容都能從 App 重新產生一次，
  只有歷史淨值一旦刪除就只能靠手動匯入對帳單 CSV 慢慢補。

**多帳本管理：** 不同人 / 帳戶（本人 / 配偶 / 父母 / 退休帳戶）建議各自獨立一本 Sheet，
透過 Tab3「📁 多帳本管理」面板隨時建立 / 切換 / 改名。
""")

    # ── 9. 全局指標關聯地圖（v18.174：從 Tab1 expander 搬移過來 — 純教學圖）──
    with _t6[8]:
        st.markdown("### ⑨ 🗺️ 全局指標關聯地圖 — 一眼看懂大環境如何影響基金")
        st.markdown("""
**📖 怎麼讀：** 跟著箭頭從**左→右**讀。冷色（藍/橘）= 源頭指標，暖色（紅）= 承壓資產。

**升息劇本（正向讀）：**
```
PMI 強勁 → 通膨升溫 → 央行維持高利率 → 殖利率飆升
                                         ├─→ ⓐ 借貸成本增 → 科技/成長股承壓
                                         └─→ ⓑ 債券下跌
```

**降息劇本（逆向讀）：** 逆轉每個節點即可
```
PMI 走弱 → 通膨降溫 → 降息 → 殖利率下行 → 債券上漲、科技股回神
```
""")
        # 復用 Tab1 同一個 render_indicator_map() 函數，避免重複定義
        try:
            from ui.tab1_macro import render_indicator_map
            render_indicator_map()
        except Exception as _e_map:
            st.caption(f"⚠️ 地圖載入失敗：{str(_e_map)[:80]}")
        st.markdown("""
**🎯 投資應用：**
1. **看到 PMI 強勁** → 通常領先 1-2 季出現通膨升溫 → 央行升息預期升高 → 提前減碼利率敏感資產（長債、科技股）
2. **看到 PMI 走弱** → 通膨壓力緩和 → 央行轉鴿派預期 → 加碼利率敏感資產（長債、REITs、成長股）
3. **觀察分歧**：若 PMI 走弱但通膨仍高 = 停滯性通膨（Stagflation）警訊 — 防禦類股（必需消費、公用事業）優於成長股

**💡 為何放在說明書？** 此圖為**靜態教學示意**，呈現升息/降息劇本的標準傳導路徑；
若想看「目前」哪條因果鏈最強，請去 **Tab1「總經因果鏈 Sankey」**（動態權重版，依實際相關係數調整邊粗細）。
""")

    # ── 10. 宏觀教學文獻（v19.40 PR2：從 Tab1 搬遷）────────────────────────────
    with _t6[9]:
        st.markdown("### 📚 宏觀教學文獻")
        st.caption(
            "💡 以下面板需先在 **📊 總經** Tab 按「📡 載入總經資料」後方可顯示即時數據。"
            "未載入時各區塊顯示提示訊息。"
        )

        _edu_ind = st.session_state.get("_macro_ind", {})
        _no_data_msg = "📡 尚未載入總經資料 — 請先切至 **📊 總經** Tab 按「📡 載入總經資料」按鈕，本頁即可顯示即時指標教學。"

        # ── § C. 📈 景氣循環歷史對照圖（危機紅區 × 指標趨勢）──────────────────────
        with st.expander("📈 景氣循環歷史對照圖（危機紅區 × 指標趨勢）", expanded=False):
            if not _edu_ind:
                st.info(_no_data_msg)
            else:
                try:
                    import plotly.graph_objects as _go_c
                    from plotly.subplots import make_subplots as _msp_c
                    import pandas as _pd_c
                    _sahm_s  = (_edu_ind.get("SAHM")  or {}).get("series")
                    _sloos_s = (_edu_ind.get("SLOOS") or {}).get("series")
                    _l2_has  = any(s is not None and len(s) >= 5 for s in [_sahm_s, _sloos_s])
                    if not _l2_has:
                        st.info("📡 請先載入總經資料以顯示歷史對照圖")
                    else:
                        # v19.391 V4a:拆雙軸違規(dataviz #2 硬規則)—— 薩姆(pp)與 SLOOS(%)不同
                        # 尺度不可共軸(交叉點會被任意扭曲);改上下兩個「共用 x 時間軸」的 subplot,
                        # 各自單位、資料值完全不變,只是不再共軸誤導。
                        _l2fig = _msp_c(rows=2, cols=1, shared_xaxes=True,
                                        vertical_spacing=0.09, row_heights=[0.55, 0.45])
                        if _sahm_s is not None and len(_sahm_s) >= 5:
                            _sh = _sahm_s if isinstance(_sahm_s, _pd_c.Series) else _pd_c.Series(_sahm_s)
                            _sh = _sh.dropna().tail(120)
                            _l2fig.add_trace(_go_c.Scatter(
                                x=_sh.index, y=_sh.values, name="薩姆規則 (pp)",
                                line={"color": MD_BLUE_300, "width": 2},
                                hovertemplate="Sahm: %{y:.2f}pp<extra></extra>"),
                                row=1, col=1)
                            _l2fig.add_hline(y=0.5, line_dash="dash",
                                             line_color=MATERIAL_RED, opacity=0.6,
                                             annotation_text="衰退觸發線 0.5",
                                             annotation_font_color=MATERIAL_RED,
                                             row=1, col=1)
                        if _sloos_s is not None and len(_sloos_s) >= 5:
                            _sl = _sloos_s if isinstance(_sloos_s, _pd_c.Series) else _pd_c.Series(_sloos_s)
                            _sl = _sl.dropna().tail(120)
                            _l2fig.add_trace(_go_c.Scatter(
                                x=_sl.index, y=_sl.values, name="SLOOS (%)",
                                line={"color": MATERIAL_ORANGE, "width": 2, "dash": "dot"},
                                hovertemplate="SLOOS: %{y:.1f}%<extra></extra>"),
                                row=2, col=1)
                        _crises = [
                            ("2007-12-01", "2009-06-01", "2008 金融海嘯"),
                            ("2020-02-01", "2020-06-01", "2020 COVID"),
                            ("2022-01-01", "2022-12-01", "2022 升息週期"),
                        ]
                        for _cs, _ce, _cn in _crises:
                            _l2fig.add_vrect(
                                x0=_cs, x1=_ce,
                                fillcolor="rgba(244,67,54,0.12)",
                                line_width=0,
                                annotation_text=_cn,
                                annotation_position="top left",
                                annotation_font={"size": 9, "color": MATERIAL_RED},
                                row="all", col=1)
                        _l2fig.update_layout(
                            paper_bgcolor=STREAMLIT_BG, plot_bgcolor=STREAMLIT_BG,
                            font_color=GH_FG_PRIMARY, height=360,
                            margin=dict(t=30, b=20, l=50, r=20),
                            legend=dict(orientation="h", y=-0.12, font={"size": 10}),
                            hovermode="x unified")
                        _l2fig.update_yaxes(title_text="薩姆規則 (pp)", gridcolor=GH_BG_HOVER, row=1, col=1)
                        _l2fig.update_yaxes(title_text="SLOOS (%)", gridcolor=GH_BG_HOVER, row=2, col=1)
                        _l2fig.update_xaxes(gridcolor=GH_BG_HOVER)
                        st.plotly_chart(_l2fig, use_container_width=True)
                        st.caption("🔴 紅色陰影 = 歷史衰退/危機區間;上圖藍線 = 薩姆規則(pp),下圖橘虛線 = SLOOS 銀行放貸標準(%)。上下共用時間軸,各自單位、不再共軸扭曲。")
                except Exception as _e_c:
                    st.warning(f"⚠️ 歷史對照圖載入失敗：{_e_c}")

        # ── § D. 👉 完整指標加扣分明細 ─────────────────────────────────────────
        # 標題不寫死項數：實際參與計分的指標數會隨資料抓取結果與校準檔變動，
        # 寫死數字等於保證某天對不上（原「23 項」即為此類漂移）。
        with st.expander(
            f"👉 完整指標加扣分明細（{len(_edu_ind)} 項已載入，依 |score × weight| 由大至小）"
            if _edu_ind else "👉 完整指標加扣分明細（依 |score × weight| 由大至小）",
            expanded=False,
        ):
            if not _edu_ind:
                st.info(_no_data_msg)
            else:
                try:
                    _CONTRIB_MAP_D = {
                        "PMI":           ("製造業擴張，有利股市",       "製造業收縮，景氣動能放緩"),
                        "LEI":           ("領先指標走升，景氣加速",     "領先指標走弱，景氣放緩"),
                        "SAHM":          ("勞動市場惡化，衰退預警",     "勞動市場穩健"),
                        "SLOOS":         ("銀行緊縮放貸，信用收斂",     "銀行寬鬆放貸，信用擴張"),
                        "YIELD_10Y2Y":   ("利差走闊，殖利率正常化",     "利差倒掛，衰退預警"),
                        "YIELD_10Y3M":   ("利差走闊，景氣健康",         "利差倒掛，紐約聯儲衰退模型啟動"),
                        "HY_SPREAD":     ("信用利差走闊，避險升溫",     "信用利差收斂，風險偏好上升"),
                        "VIX":           ("恐慌升溫，波動加大",          "市場平靜，風險偏好上升"),
                        "CPI":           ("通膨壓力升溫，緊縮風險",     "通膨回落，貨幣政策放鬆空間"),
                        "PPI":           ("上游成本升溫",                "上游成本回落"),
                        "INFL_EXP_5Y":   ("通膨預期升溫，債市壓力",     "通膨預期降溫，利率下行空間"),
                        "FED_RATE":      ("資金成本上升，估值承壓",     "資金成本下降，流動性寬鬆"),
                        "UNEMPLOYMENT":  ("失業率上升，景氣承壓",       "失業率下降，景氣健康"),
                        "JOBLESS":       ("初領失業金升溫，裁員壓力",   "初領失業金回落，就業改善"),
                        "CONT_CLAIMS":   ("持續失業金升溫",              "持續失業金回落"),
                        "CONSUMER_CONF": ("消費信心強，內需動能足",     "消費信心弱，內需放緩"),
                        "M2":            ("M2 寬鬆，流動性充沛",        "M2 緊縮，流動性收斂"),
                        "M2_WEEKLY":     ("M2 週頻寬鬆",                 "M2 週頻緊縮"),
                        "FED_BS":        ("Fed 擴表（QE）",              "Fed 縮表（QT）"),
                        "DXY":           ("美元走強，外幣資產承壓",     "美元走弱，外幣資產受益"),
                        "ADL":           ("市場廣度健康",                "大型股獨撐，廣度疲弱"),
                        "COPPER":        ("銅價走強，全球景氣轉熱",     "銅價走弱，全球景氣轉冷"),
                        "PERMIT_HOUSING":("建照核發強，房市領先",       "建照核發弱，房市領先疲弱"),
                    }
                    st.caption(
                        "📖 **怎麼看這張表**：「💡 貢獻說明」直接告訴你這檔指標目前如何影響景氣總分。"
                        "排序依 |score × weight| ＝ 對總分實際影響力，最重要的指標在最上方。"
                    )
                    # v19.405:weight=0 合法(去重後的備源,如月頻 M2 命中時的
                    # M2_WEEKLY)。原式 `_iv.get("weight", 1) or 1` 因 Python
                    # `0 or 1 == 1` 把刻意歸零的權重還原成 1 → 本表仍以
                    # |score × 1| 讓已去重的備源佔排序位。
                    # 契約 SSOT:services/macro/composite_score.coerce_weight
                    from services.macro.composite_score import coerce_weight as _cw
                    _rows_d = []
                    for _ik, _iv in _edu_ind.items():
                        if not isinstance(_iv, dict):
                            continue
                        try:
                            _w = _cw(_iv.get("weight", 1))
                        except (TypeError, ValueError):
                            _w = 1.0
                        _sc_raw = _iv.get("score", 0) or 0
                        try:
                            # `+ 0.0` 消 -0.0(w=0 時 clamp 會產生負零,顯示成 "-0.0")
                            _sc_clamped = round(max(-_w, min(_w, float(_sc_raw))), 2) + 0.0
                        except (TypeError, ValueError):
                            _sc_clamped = 0.0
                        _val_raw = _iv.get("value")
                        _val_str = f"{_val_raw:.2f}" if isinstance(_val_raw, (int, float)) else str(_val_raw or "")[:10]
                        _phrases = _CONTRIB_MAP_D.get(_ik)
                        if _phrases:
                            _semantic = _phrases[0] if _sc_clamped > 0 else (_phrases[1] if _sc_clamped < 0 else "現況中性")
                        else:
                            _semantic = "正面訊號" if _sc_clamped > 0 else ("負面訊號" if _sc_clamped < 0 else "現況中性")
                        # 2026-08-05 稽核 🔴 必修 1 順帶:原 [:18] 會把服務層的
                        # 代理值長名「ISM 製造業 PMI（Phil Fed 替代）」(20 字)
                        # 切成「…（Phil Fed 替」—— 剛好砍掉「替代」二字的下半,
                        # 讓代理值在 23 項明細表裡看起來像官方本尊(§1 反造假)。
                        # 放寬到 32 字(現行最長 name 為 24 字,留 8 字餘裕)。
                        _name = str(_iv.get("name", _ik) or _ik)[:32]
                        if _sc_clamped > 0:
                            _verdict = f"{_name} {_val_str} ➡️ {_semantic}，貢獻 +{_sc_clamped:.1f} 分"
                        elif _sc_clamped < 0:
                            _verdict = f"{_name} {_val_str} ➡️ {_semantic}，扣 {_sc_clamped:.1f} 分"
                        else:
                            _verdict = f"{_name} {_val_str} ➡️ {_semantic}（不加減分）"
                        _abs_contrib = abs(_sc_clamped * _w)
                        _rows_d.append({
                            "_abs": _abs_contrib,
                            "指標":      _name,
                            "數值":      _val_str,
                            "信號":      _iv.get("signal", "⬜"),
                            "貢獻分":    _sc_clamped,
                            "權重":      _w,
                            "💡 貢獻說明": _verdict,
                        })
                    if _rows_d:
                        _rows_d.sort(key=lambda r: r["_abs"], reverse=True)
                        # stash for AI snapshot
                        try:
                            _pos_d = [r for r in _rows_d if r["貢獻分"] > 0][:3]
                            _neg_d = [r for r in _rows_d if r["貢獻分"] < 0][:3]
                            st.session_state["_macro_23items"] = {
                                "n_total": len(_rows_d),
                                "n_pos": len([r for r in _rows_d if r["貢獻分"] > 0]),
                                "n_neg": len([r for r in _rows_d if r["貢獻分"] < 0]),
                                "top_pos": [{"name": r["指標"], "verdict": r["💡 貢獻說明"]} for r in _pos_d],
                                "top_neg": [{"name": r["指標"], "verdict": r["💡 貢獻說明"]} for r in _neg_d],
                            }
                        except Exception:
                            pass
                        for r in _rows_d:
                            r.pop("_abs", None)
                        st.dataframe(pd.DataFrame(_rows_d), use_container_width=True, hide_index=True,
                                     column_config={
                                         "指標":      st.column_config.TextColumn(width="small"),
                                         "數值":      st.column_config.TextColumn(width="small"),
                                         "信號":      st.column_config.TextColumn(width="small"),
                                         "貢獻分":    st.column_config.NumberColumn(format="%.2f", width="small"),
                                         "權重":      st.column_config.NumberColumn(format="%.0f", width="small"),
                                         "💡 貢獻說明": st.column_config.TextColumn(width="large"),
                                     })
                    else:
                        st.info("⬜ 沒有可用的指標資料")
                except Exception as _e_d:
                    st.warning(f"⚠️ 加扣分明細載入失敗：{_e_d}")
