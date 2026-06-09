"""ui/tab6_manual.py — 系統說明書 Tab（v18.117 B-C.1）

從 app.py 抽出 Tab6（系統說明書）的渲染邏輯 — 純靜態 markdown / 表格內容、零 runtime
狀態依賴（不讀 session_state、不呼叫 services），是驗證「with tab: → render_xxx()」
重構 pattern 最理想的 PoC 對象。

對外 API：
- render_manual_tab() -> None

設計：
- 純函式（無參數）：完全自包含
- 內部使用 streamlit + pandas（caller 端 `with tab6:` context 之內被呼叫）
- 9 個 sub-tab：Macro Score / 景氣天氣 / 六因子 / 吃本金 / 再平衡 / 台股TPI /
  核心衛星 / 汰弱留強 / Sheet 資料結構（v18.169 新增）
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


def render_manual_tab() -> None:
    """渲染系統說明書 Tab — 9 sub-tab 公式與判斷標準完整說明。"""
    st.markdown("## 📖 系統說明書 — 公式與判斷標準完整說明")
    st.caption("📖 故事附錄・公式聖經：拆解前 3 站每個評分模型、公式與指標的算法，讓進階使用者看懂決策邏輯。")

    # ── v18.272: 📋 曾經查過的基金清單（Tab2 + Tab3 自動記錄）─
    # ── v18.280: 加 CSV 上傳還原（reboot 後從備份 CSV merge 回來）─
    # ── v18.282: 加預設常用基金 + 手動新增表單 ─
    with st.expander("📋 曾經查過的基金標的清單（Tab2 / Tab3 自動記錄 + 預設）", expanded=True):
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
                "尚未查過任何基金。在「🔍 單一基金」抓取後 / 「📦 組合基金」載入後，"
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
            "系統存進 `cache/nav_history/{code}.json`。**之後危機回測等功能會優先讀 cache**，"
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
        "🏆 3. 六因子評分",
        "🔴 4. 吃本金診斷",
        "⚖️ 5. 再平衡公式",
        "🇹🇼 6. 台股TPI",
        "🛡️⚡ 7. 核心衛星",
        "🔄 8. 汰弱留強",
        "📋 9. Sheet 資料結構",
        "🗺️ 10. 全局指標關聯地圖",
        "📚 11. 宏觀教學文獻",
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
            use_container_width=True, hide_index=True)
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

    # ── 3. 六因子評分 ─────────────────────────────────────────────
    with _t6[2]:
        st.markdown("### ③ 🏆 基金六因子評分（Fund Factor Model）")
        st.markdown("""
**公式：**
```
Fund_Score = Σ(因子得分ᵢ × 權重ᵢ) / Σ(權重ᵢ)    範圍：0~100
```
""")
        st.dataframe(pd.DataFrame([
            ["1. Sharpe Ratio",  "每單位風險的超額報酬",       "25%",
             "min(max((Sharpe+1)/2×100, 0), 100)", "Sharpe=-1→0分；=0→50分；=+1→100分",  "MoneyDJ wb07"],
            ["2. Sortino Ratio", "只懲罰下行波動",             "15%",
             "min(max((Sortino+1)/2×100, 0), 100)", "同 Sharpe 但只計負報酬標準差",       "calc_metrics()"],
            ["3. Max Drawdown",  "歷史最慘跌幅（越小越好）",   "20%",
             "min(max((1-|MaxDD|/30)×100, 0), 100)", "MaxDD=0%→100分；=-30%→0分",        "淨值歷史計算"],
            ["4. Calmar Ratio",  "年化報酬/最大回撤",          "10%",
             "min(max(Calmar/2×100, 0), 100)", "Calmar=0→0分；=2→100分",                 "calc_metrics()"],
            ["5. Alpha",         "含息報酬率 - 配息年化率",    "20%",
             "min(max((Alpha+10)/20×100, 0), 100)", "Alpha=-10%→0分；=0→50分；=+10%→100分", "wb01-wb05"],
            ["6. 費用率",        "年度管理費用（越低越好）",   "10%",
             "min(max((3-費用率)/3×100, 0), 100)", "0%→100分；3%→0分",                   "MoneyDJ 基金資料"],
        ], columns=["因子", "說明", "權重", "計算公式", "數值對應", "資料來源"]),
            use_container_width=True, hide_index=True)
        st.markdown("""
**Grade 等級：**
| Score | Grade | 說明 |
|-------|-------|------|
| 75~100 | **A** | 優秀：風險調整後表現卓越 |
| 55~74  | **B** | 良好：整體表現在平均以上 |
| 40~54  | **C** | 普通：考慮是否汰換 |
| 0~39   | **D** | 待改善：建議評估替代標的 |

⚠️ 缺乏資料的因子不計入加權總分，最少需 Sharpe + Alpha 兩項。
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

    # ── 6. 台股TPI ────────────────────────────────────────────────
    with _t6[5]:
        st.markdown("### ⑥ 🇹🇼 台灣市場轉折點指標（TPI v15.1）")
        st.markdown("""
**公式：**
```
TPI = Z(Breadth) × 0.4 + Z(FII) × 0.3 + Z(M1B/M2) × 0.3
```

| 因子 | 說明 | 資料來源 |
|------|------|---------|
| **Z(Breadth)** 市場寬度 | (上漲家數-下跌家數)/(上漲+下跌)×100 ÷20 | TWSE MI_INDEX |
| **Z(FII)** 外資淨買 | 外資買超-賣超（元）÷50億 | FinMind API |
| **Z(M1B/M2)** 貨幣動能 | M1B成長率 vs M2成長率交叉 | 央行 ms1.json |

**水溫對應：**
| TPI | 水溫 | 訊號 | 建議行動 |
|-----|------|------|---------|
| ≥ +1.5 | 🥵 沸點 | 🔴 | 上漲家數銳減，啟動獲利了結 |
| +0.5~+1.5 | 🌡️ 溫熱 | 🟡 | 持續觀察，衛星設停利 |
| -0.5~+0.5 | ⚖️ 常溫 | ⚪ | 維持配置，觀察變化 |
| -1.5~-0.5 | 🌡️ 偏冷 | 🟡 | 外資轉弱，降低台股部位 |
| ≤ -1.5 | 🥶 冰點 | 🟢 | 散戶絕望期，分批建倉訊號 |

⚠️ TPI 為輔助參考指標，需配合景氣位階綜合判斷。
""")

    # ── 7. 核心衛星分類 ──────────────────────────────────────────
    with _t6[6]:
        st.markdown("### ⑦ 🛡️⚡ 核心/衛星分類邏輯")
        st.markdown("**優先序：手動設定 > 關鍵字比對 > 預設（衛星）**")
        st.dataframe(pd.DataFrame([
            ["🛡️ 核心", "債、收益、配息、平衡、高息、公用、多元、income、bond、dividend、balanced"],
            ["⚡ 衛星", "AI、科技、半導體、成長、主題、印度、越南、生技、醫療、能源、tech、growth"],
        ], columns=["分類", "觸發關鍵字（基金名稱含有任一）"]),
            use_container_width=True, hide_index=True)
        st.markdown("""
**β 係數分類：**
| β 值 | 標籤 | 建議比重 |
|------|------|---------|
| < 0.8 | 🛡️ 定海神針 | 核心部位 60~80% |
| 0.8~1.2 | ⚖️ 市場同步 | 視景氣位階調整 |
| > 1.2 | 🚀 衝鋒陷陣 | 衛星部位 10~20% |

**策略3 核心/衛星比例目標（預設 80/20）：**
```
核心資產：提供穩定現金流（每月配息），作為「養」衛星的資金來源
衛星資產：追求價差成長，由核心配息「養」，不動用本金
```
偏離 >5% → ⚠️ 建議再平衡　|　偏離 >10% → 🚨 必須執行
""")

    # ── 8. 汰弱留強評分 ──────────────────────────────────────────
    with _t6[7]:
        st.markdown("### ⑧ 🔄 汰弱留強評分（Security Ranking）")
        st.markdown("""
**核心邏輯：定期汰換績效落後的基金，換入同類前段班**

**觸發條件（任一滿足即亮警示）：**
| 條件 | 建議行動 |
|------|---------|
| 同類四分位連續 ≥2季 第3或4分位 | ⚠️ 追蹤；第3季仍落後 → 換 |
| 同類四分位連續 ≥2季 第4分位（後25%）| 🚨 跨行轉存至前25%標的 |
| 吃本金連續發生（含息報酬 < 配息率）| 🔴 優先汰換 |
| MaxDrawdown 超過同類平均 1.5x | ⚠️ 評估是否替換 |

**汰弱留強評分公式（60分及格）：**
```
汰弱分數 = 含息報酬率 × 40%
         + Sharpe 比率 × 30%
         + (費用率 vs 同類均值) × 30%

< 60分 → 考慮汰換　|　≥ 75分 → 保留
```

**四分位等級：**
| 等級 | 排名 | 含義 |
|------|------|------|
| 第1四分位 | 前25% | 同類最強，優先持有 |
| 第2四分位 | 26~50% | 中上，繼續持有 |
| 第3四分位 | 51~75% | 中下，開始觀察 |
| 第4四分位 | 後25% | 最弱，考慮汰換 |

**實際操作原則：**
1. 每季（3個月）看一次同類排名
2. 連續2季後25% → 啟動汰換計畫（給它一次機會）
3. 找好替換標的後，在「買點」時換（避免在高點換進）
4. 核心資產不輕易換（穩定配息 > 短期績效排名）
""")

    # ── 9. Sheet 資料結構（v18.169：從 Tab3 expander 搬移過來）─────────
    with _t6[8]:
        st.markdown("### ⑨ 📋 Sheet 資料結構（這本 Google Sheet 內的分頁長相）")
        st.markdown("""
**同一張 Google Sheet 內共有 3 種 tab**，平時下方各動作（批次加入、T7 套用）會自動同步到對應 tab。
若不確定哪個按鈕同步什麼，請改用 Tab3 頂部「🚀 快速存讀面板」。

| Tab 類型 | 命名規則 | 用途 | 同步來源 |
|---------|---------|------|---------|
| 📋 **保單分頁** | 自訂保單名稱 | 一張保單 = 一個 tab，放該保單下的基金清單 / 級別 / 幣別 | Tab3「保單管理」批次加入 |
| 📸 **`_T7_State`** | 固定底線開頭 | T7 持倉的單位數 / 平均成本 / 匯率快照，重啟 app 用此還原部位 | Tab3「T7 套用」自動寫入 |
| 📜 **`_Ledgers`** | 固定底線開頭 | 所有 buy / sell / dividend 事件的 audit trail（append-only） | Tab3 所有交易動作 |

**重點觀念：**
- **底線開頭（`_`）的 tab 是系統保留**：請勿手動改名或刪除，否則 app 將無法還原部位。
- **保單分頁可自由增減**：每張保單獨立一個 tab，方便分人 / 分帳戶管理。
- **`_T7_State` 是快照**：app 啟動時讀回來重建部位，是「最新狀態」。
- **`_Ledgers` 是流水**：所有交易事件按時序追加，永不刪改，是「歷史記錄」。

**多帳本管理：** 不同人 / 帳戶（本人 / 配偶 / 父母 / 退休帳戶）建議各自獨立一本 Sheet，
透過 Tab3「📁 多帳本管理」面板隨時建立 / 切換 / 改名。
""")

    # ── 10. 全局指標關聯地圖（v18.174：從 Tab1 expander 搬移過來 — 純教學圖）──
    with _t6[9]:
        st.markdown("### ⑩ 🗺️ 全局指標關聯地圖 — 一眼看懂大環境如何影響基金")
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

    # ── 11. 宏觀教學文獻（v19.40 PR2：從 Tab1 搬遷）────────────────────────────
    with _t6[10]:
        st.markdown("### 📚 宏觀教學文獻")
        st.caption(
            "💡 以下面板需先在 **📊 總經** Tab 按「📡 載入總經資料」後方可顯示即時數據。"
            "未載入時各區塊顯示提示訊息。"
        )

        _edu_ind = st.session_state.get("_macro_ind", {})
        _no_data_msg = "📡 尚未載入總經資料 — 請先切至 **📊 總經** Tab 按「📡 載入總經資料」按鈕，本頁即可顯示即時指標教學。"

        # ── § A. 🎯 為什麼是這位階？（Top-8 貢獻 driver + 教學）──────────────────
        with st.expander("🎯 為什麼是這位階？（Top-8 貢獻 driver + 教學）", expanded=False):
            if not _edu_ind:
                st.info(_no_data_msg)
            else:
                try:
                    from services.macro_explain import build_beginner_payload as _bbp
                    from ui.components.macro_card_edu import MACRO_EDU as _ME_a
                    _pl = _bbp(_edu_ind, _ME_a, top_n=8)
                    if not _pl["ready"]:
                        st.info("⏳ 資料尚未就緒，請重新至總經 Tab 載入。")
                    else:
                        st.markdown("### 🎯 為什麼是這位階？")
                        st.caption("綜合分數是「每個指標 score × 權重」加總；以下 3 個是本期貢獻最大的 driver：")
                        for _bullet in _pl["why_bullets"]:
                            st.markdown(f"- {_bullet}")
                        st.markdown(
                            f"### 📚 本期使用 {_pl['n_displayed']} 個關鍵指標"
                            f"（按 |score × 權重| 排序，權重來自回測核可組合）"
                        )
                        st.caption(
                            "點開任一指標看：當前數值 / 自動判讀 / 💡 這指標是什麼 / 📐 怎麼讀（閾值對照）/ "
                            "🔗 搭配誰看 / 📊 歷史錨點。"
                        )
                        for _row in _pl["active_factors"]:
                            _label = (
                                f"{_row['name']}（{_row['freq_label']}）"
                                f"｜貢獻 **{_row['contribution']:+.2f}**"
                                f"｜score {_row['score']:+.2f} × 權重 {_row['weight']:.2f}"
                            )
                            with st.expander(_label, expanded=False):
                                _val = _row["value"]
                                _unit = _row["unit"] or ""
                                st.markdown(
                                    f"**目前數值**：`{_val} {_unit}`　"
                                    f"**類型**：{_row['type'] or '—'}"
                                )
                                st.markdown(f"**自動判讀**：{_row['interpretation']}")
                                st.divider()
                                st.markdown("**💡 這指標是什麼？**")
                                st.markdown(_row["edu_meaning"])
                                if _row["edu_how_to_read"]:
                                    st.markdown("**📐 怎麼讀？（閾值對照表）**")
                                    for _entry in _row["edu_how_to_read"]:
                                        if isinstance(_entry, (list, tuple)) and len(_entry) >= 2:
                                            st.markdown(f"  - `{_entry[0]}` → {_entry[1]}")
                                        else:
                                            st.markdown(f"  - {_entry}")
                                if _row["edu_pair_with"]:
                                    st.markdown(f"**🔗 搭配誰看？** {_row['edu_pair_with']}")
                                if _row["edu_historical_anchor"]:
                                    st.markdown(f"**📊 歷史錨點**：{_row['edu_historical_anchor']}")
                                if _row["edu_upstream"] or _row["edu_downstream"]:
                                    _cols = st.columns(2)
                                    with _cols[0]:
                                        if _row["edu_upstream"]:
                                            st.markdown(f"**⬆️ 上游因**：{_row['edu_upstream']}")
                                    with _cols[1]:
                                        if _row["edu_downstream"]:
                                            st.markdown(f"**⬇️ 下游果**：{_row['edu_downstream']}")
                except Exception as _e_a:
                    st.warning(f"⚠️ 為什麼是這位階？載入失敗：{_e_a}")

        # ── § B. 📊 23 指標教學手冊（含趨勢圖 + 白話教學）────────────────────────
        with st.expander("📊 23 指標教學手冊（含趨勢圖 + 完整白話教學）", expanded=False):
            if not _edu_ind:
                st.info(_no_data_msg)
            else:
                try:
                    from ui.components.macro_card import (
                        build_cards_from_indicators as _bci,
                        render_macro_card_grid as _rcg,
                    )
                    from ui.components.macro_card_edu import MACRO_EDU as _ME_b
                    st.markdown("#### 📊 23 指標教學手冊（含趨勢圖 + 完整白話教學｜⭐ = v16.1 高頻替代源）")
                    st.caption("⚠️ 黃線=警戒閾值｜紅線=危險閾值｜黃點=當前值｜Z-Score：紅(極端壞)/綠(極端好)/橘(偏離 1.5σ)/藍(正常)")
                    _card_spec = [
                        ("SAHM",          "薩姆規則（衰退風險）",          "pp", 2,  True,   0.3,   0.5),
                        ("SLOOS",         "SLOOS（銀行放貸意願）",          "%",  1,  True,   0,     20),
                        ("PMI",           "ISM PMI（製造業景氣）",          "",   1,  False,  50,    45),
                        ("LEI",           "⭐ CFNAI 領先指標（PMI 替代）",  "",   2,  False,  0,    -0.7),
                        ("YIELD_10Y2Y",   "殖利率利差 10Y-2Y",              "%",  3,  False,  0.5,   0),
                        ("YIELD_10Y3M",   "殖利率利差 10Y-3M",              "%",  2,  False,  0.5,   0),
                        ("PPI",           "PPI 生產者物價(YoY)",            "%",  2,  True,   3,     5),
                        ("COPPER",        "銅博士月漲跌",                   "%",  2,  False,  0,     -5),
                        ("ADL",           "RSP/SPY 市場廣度",               "",   4,  False,  None,  None),
                        ("JOBLESS",       "初領失業金（裁員領先指標）",     "萬", 1,  True,   27,    30),
                        ("CONT_CLAIMS",   "⭐ 持續失業金週頻（失業率替代）","萬", 0,  True,   180,   190),
                        ("CONSUMER_CONF", "消費者信心 (Michigan)",          "",   1,  False,  80,    60),
                        ("PERMIT_HOUSING","⭐ 建照核發（房市領先）",        "千", 0,  False,  1500,  1200),
                        ("CPI",           "CPI 通膨率（YoY）",              "%",  2,  True,   2.5,   4),
                        ("INFL_EXP_5Y",   "⭐ 5Y 通膨預期日頻（CPI 替代）","%",  2,  True,   2.8,   3.5),
                        ("FED_RATE",      "聯準會利率",                     "%",  2,  True,   2.5,   5),
                        ("UNEMPLOYMENT",  "失業率",                          "%", 1,  True,   4.5,   6),
                        ("M2",            "M2 貨幣供給（YoY）",             "%",  2,  False,  5,     0),
                        ("M2_WEEKLY",     "⭐ M2 週頻 YoY（M2 替代）",     "%",  2,  False,  5,     0),
                        ("FED_BS",        "Fed 資產負債表（YoY）",          "%",  2,  False,  0,     -5),
                        ("DXY",           "美元指數",                        "",  2,  True,   105,   110),
                        ("HY_SPREAD",     "HY 信用利差 (OAS)",              "%",  2,  True,   4,     6),
                        ("VIX",           "VIX 恐慌指數",                   "",   1,  True,   22,    30),
                    ]
                    _cards = _bci(_edu_ind, _card_spec, edu_map=_ME_b)
                    for _c in _cards:
                        _c["edu_default_open"] = True
                    with st.container(border=True):
                        st.markdown(
                            "<div style='color:#888;font-size:12px;margin:-4px 0 6px'>"
                            "點開每張卡片下方「📖 完整教學」可看：白話定義 / 怎麼判讀 / 搭配看誰 / "
                            "上游因 / 下游果 / 歷史錨點。"
                            "</div>", unsafe_allow_html=True)
                        _rcg(_cards, columns=2)
                except Exception as _e_b:
                    st.warning(f"指標教學手冊載入失敗：{_e_b}")

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
                        _l2fig = _msp_c(specs=[[{"secondary_y": True}]])
                        if _sahm_s is not None and len(_sahm_s) >= 5:
                            _sh = _sahm_s if isinstance(_sahm_s, _pd_c.Series) else _pd_c.Series(_sahm_s)
                            _sh = _sh.dropna().tail(120)
                            _l2fig.add_trace(_go_c.Scatter(
                                x=_sh.index, y=_sh.values, name="薩姆規則 (pp)",
                                line={"color": "#64b5f6", "width": 2},
                                hovertemplate="Sahm: %{y:.2f}pp<extra></extra>"),
                                secondary_y=False)
                            _l2fig.add_hline(y=0.5, line_dash="dash",
                                             line_color="#f44336", opacity=0.6,
                                             annotation_text="衰退觸發線 0.5",
                                             annotation_font_color="#f44336",
                                             secondary_y=False)
                        if _sloos_s is not None and len(_sloos_s) >= 5:
                            _sl = _sloos_s if isinstance(_sloos_s, _pd_c.Series) else _pd_c.Series(_sloos_s)
                            _sl = _sl.dropna().tail(120)
                            _l2fig.add_trace(_go_c.Scatter(
                                x=_sl.index, y=_sl.values, name="SLOOS (%)",
                                line={"color": "#ff9800", "width": 2, "dash": "dot"},
                                hovertemplate="SLOOS: %{y:.1f}%<extra></extra>"),
                                secondary_y=True)
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
                                annotation_font={"size": 9, "color": "#f44336"})
                        _l2fig.update_layout(
                            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                            font_color="#e6edf3", height=320,
                            margin=dict(t=30, b=20, l=50, r=50),
                            legend=dict(orientation="h", y=-0.15, font={"size": 10}),
                            hovermode="x unified")
                        _l2fig.update_yaxes(title_text="薩姆規則 (pp)",
                                            gridcolor="#21262d", secondary_y=False)
                        _l2fig.update_yaxes(title_text="SLOOS (%)",
                                            gridcolor="#21262d", secondary_y=True)
                        _l2fig.update_xaxes(gridcolor="#21262d")
                        st.plotly_chart(_l2fig, use_container_width=True)
                        st.caption("🔴 紅色陰影 = 歷史衰退/危機區間，藍線 = 薩姆規則，橘虛線 = SLOOS 銀行放貸標準")
                except Exception as _e_c:
                    st.warning(f"⚠️ 歷史對照圖載入失敗：{_e_c}")

        # ── § D. 👉 完整 23 項指標加扣分明細──────────────────────────────────────
        with st.expander("👉 完整 23 項指標加扣分明細（依 |score × weight| 由大至小）", expanded=False):
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
                    _rows_d = []
                    for _ik, _iv in _edu_ind.items():
                        if not isinstance(_iv, dict):
                            continue
                        _w_raw = _iv.get("weight", 1) or 1
                        try:
                            _w = float(_w_raw)
                        except (TypeError, ValueError):
                            _w = 1.0
                        _sc_raw = _iv.get("score", 0) or 0
                        try:
                            _sc_clamped = round(max(-_w, min(_w, float(_sc_raw))), 2)
                        except (TypeError, ValueError):
                            _sc_clamped = 0.0
                        _val_raw = _iv.get("value")
                        _val_str = f"{_val_raw:.2f}" if isinstance(_val_raw, (int, float)) else str(_val_raw or "")[:10]
                        _phrases = _CONTRIB_MAP_D.get(_ik)
                        if _phrases:
                            _semantic = _phrases[0] if _sc_clamped > 0 else (_phrases[1] if _sc_clamped < 0 else "現況中性")
                        else:
                            _semantic = "正面訊號" if _sc_clamped > 0 else ("負面訊號" if _sc_clamped < 0 else "現況中性")
                        _name = _iv.get("name", _ik)[:18]
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

        # ── § E. 📊 變數重要性 Top-N────────────────────────────────────────────────
        with st.expander("📊 變數重要性 Top-N（哪個指標最能預測景氣變化？）", expanded=False):
            if not _edu_ind:
                st.info(_no_data_msg)
            else:
                try:
                    from services.macro_service import rank_macro_drivers as _rmd_e
                    _imp_c1, _imp_c2 = st.columns(2)
                    with _imp_c1:
                        _imp_target = st.selectbox(
                            "target 指標", options=["LEI", "PMI", "VIX", "PERMIT_HOUSING"],
                            index=0, key="edu_imp_target",
                            help="計算各 driver 與 target lag 後變化的 lag-correlation",
                        )
                    with _imp_c2:
                        _imp_lag = st.slider("lag months",
                                             min_value=1, max_value=12, value=3,
                                             step=1, key="edu_imp_lag")
                    _imp = _rmd_e(_edu_ind, target_key=_imp_target,
                                   lag_months=_imp_lag, min_overlap=24)
                    if not _imp["ok"]:
                        st.info(f"📡 {_imp['note']}")
                    else:
                        _imp_rows = []
                        for _r in _imp["ranked"]:
                            _imp_rows.append({
                                "排名": "🏅",
                                "driver": _r["name"],
                                "lag-corr": f"{_r['corr']:+.3f}",
                                "|corr|": f"{_r['abs_corr']:.3f}",
                                "方向": ("📈 同向" if _r["direction"] == "+" else "📉 反向"),
                                "權重": _r["weight"],
                                "共同期": _r["n_overlap"],
                            })
                        for _i, _row in enumerate(_imp_rows[:3]):
                            _row["排名"] = ["🥇", "🥈", "🥉"][_i]
                        st.dataframe(pd.DataFrame(_imp_rows),
                                     use_container_width=True, hide_index=True)
                        st.caption(
                            f"📊 lag-corr 解讀：driver 在 t 月 vs target 在 t+{_imp_lag} 月變化的相關性；"
                            f"|corr|≥0.5「高」/ 0.3-0.5「中」/ <0.3「低」。"
                            f"正號 = 同向；負號 = 反向。{_imp['note']}。"
                        )
                        _top3 = _imp["ranked"][:3]
                        if _top3:
                            _lines_e = []
                            for _i, _r in enumerate(_top3):
                                _medal = ["🥇", "🥈", "🥉"][_i]
                                _dir_word = "同向（一起升降）" if _r["direction"] == "+" else "反向（升↔降）"
                                _sig_word = (
                                    "顯著" if _r["abs_corr"] >= 0.5
                                    else ("中等" if _r["abs_corr"] >= 0.3 else "微弱")
                                )
                                _lines_e.append(
                                    f"{_medal} **{_r['name']}** "
                                    f"與 {_imp_target} 未來 {_imp_lag} 個月變化呈 **{_dir_word}** "
                                    f"相關（|corr|={_r['abs_corr']:.2f}，{_sig_word}）"
                                )
                            _top1 = _top3[0]
                            _action = (
                                f"→ **應用**：當 **{_top1['name']}** 出現明顯變化時，"
                                f"預期 {_imp_lag} 個月後 {_imp_target} 將朝"
                                f"{'同方向' if _top1['direction']=='+' else '反方向'}"
                                f"移動（歷史資料 n={_top1['n_overlap']} 月）。"
                            )
                            st.info(
                                "💡 **Top 3 driver 解讀**\n\n"
                                + "\n\n".join("- " + _l for _l in _lines_e)
                                + "\n\n" + _action
                            )
                        # stash for AI snapshot
                        try:
                            st.session_state["_macro_var_importance"] = {
                                "target": _imp_target,
                                "lag_months": int(_imp_lag),
                                "top3": [{
                                    "name": _r.get("name", ""),
                                    "abs_corr": float(_r.get("abs_corr", 0) or 0),
                                    "direction": _r.get("direction", ""),
                                    "n_overlap": int(_r.get("n_overlap", 0) or 0),
                                } for _r in _top3],
                            }
                        except Exception:
                            pass
                except Exception as _e_e:
                    st.caption(f"⚠️ 變數重要性計算失敗：{str(_e_e)[:80]}")
