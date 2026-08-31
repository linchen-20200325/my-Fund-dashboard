"""ui/helpers/settings_diag —— 「⑤ ⚙️ 設定與診斷」合併頁的共用機件。

本套件只放**合併頁自己需要、而各個既有分頁都不該知道細節**的東西：

- `merge_context`      —— 所有權旗標（誰負責畫哪一塊；WP-C `fund_research` 同型，
                          **名稱空間刻意分開**，兩個合併頁互不牽動）。
- `fetch_diag_section` —— 「🔍 抓取診斷細節」區塊本體（原封抽自
                          `ui/tab2_single_fund.py`，⑤ 與個基頁共用同一份）。
- `policy_admin_bridge`—— ⑤ 承接「保單管理（Google Sheets）」的橋接層
                          （本批預設由旗標關閉，只有接線批次會打開）。

⚠️ 這裡**不放**任何計算 —— 合併是版面動作，不是計算改動。
"""
