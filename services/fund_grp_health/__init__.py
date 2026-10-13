"""services/fund_grp_health — 組合健診逐檔欄位的純計算(L2,零 streamlit、零 `ui.*`)。

2026-10-13 客戶裁示(LINE 推播與舊 UI 解耦):「兩支 LINE 推播保留……核准把它們目前借用的
`ui/helpers` 必要函式搬到適當共用層。要求:不讓排程依賴 UI;不改推播業務語意;不新增資料來源;
搬移後建立回歸測試;舊 UI 刪除後兩支排程仍可獨立運作。」

本子套件收的是每週換檔推播 `scripts/weekly_switch_notify.py` 借用、原住
`ui/helpers/fund_grp_health/` 的**純資料函式**(子模組名與原 UI 子模組一一對應):

- `_utils`   —— `_build_fund_dict` / `BASE_LABELS`(整檔搬來)
- `capture`  —— `capture_by_code`(整檔搬來)
- `quality`  —— `quality_score_by_code`(整檔搬來)
- `risk`     —— `hwm_sigma_by_code` / `risk_compare_by_code`(只搬資料函式;表格渲染留 UI)
- `signals`  —— `mk_signal_by_code`(只搬資料函式;讀 `st.session_state` 的 `mk_fund_signal`
                 留在 UI,由 UI 端注入 —— 見該檔說明)
- `unified`  —— `build_merged_extra_columns` 與它直接用到的兩個 by_code(只搬這些)

邏輯一律原封搬移、一字未改;原 UI 路徑保留別名或 re-export,舊 UI 呼叫點不必改(SSOT)。
⚠️ 刻意不在本 `__init__` 做 eager import —— 呼叫端各自 import 子模組,避免連帶載入用不到的模組。
"""
