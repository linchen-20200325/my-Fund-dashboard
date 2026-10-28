# 客戶 2026-10-28 DG-2 合併裁示：C+ canonical fund identity、先 Shadow Mode（逐字）

- **來源**：客戶 2026-10-28 對話中對 DG-2（canonical identity）的合併裁示，經總管於派工單內轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-28-05`（客戶裁示）。落地：`docs/v2/70_dg2_canonical_identity_proposal.md`〈客戶裁示〉〈舊 UI reuse matrix〉〈Stage-1 C+ shadow 設計與實作〉、`shared/fund_identity.py`、`services/fund_identity.py`、`services/fund_identity_shadow.py`、`docs/BACKLOG.md` BL-0521。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行）。
- **存檔日期**：2026-10-28
- **圍欄內文 sha256**：`b3b132ca3a8a42cb13465fdfeccc2a7fa72ff3204b8067576b3527677bdda355`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
DG-2 合併裁示如下。

目標

解決同一檔基金因為：

- 不同 URL
- 不同平台／通路後綴
- 不同頁面
- 不同 identity parser
- 不同 NAV 路徑

而被誤判成不同標的，或造成單一基金頁／持股頁／資產配置頁顯示不同 NAV、價格、報酬或估值的問題。

核心原則仍是：

Same canonical fund + same metric + same as-of + same currency = same canonical value across all views.

---

1. 基金代號與平台後綴的業務語意

客戶已明確更正：

以：

"TLZF9-AL001"

為例：

- "TLZF9" = 基金本身的基金代號
- "AL001" = 不同銷售通路／平台／保經／保險公司等附加識別

因此：

- "TLZF9"
- "TLZF9-AL001"
- "TLZF9-24A7"

目前原則上視為同一檔核心基金，不是三檔不同基金。

Canonical fund identity 第一階段應以：

"base_fund_code = TLZF9"

為核心。

平台資訊另外保存：

- "original_code"
- "platform_suffix"
- "channel_code"
- "source_url"

不得直接把平台後綴當成新的基金身份。

---

2. 但不得盲目剝除後綴

雖然預設後綴是通路識別，但仍要保留證據與例外能力。

如果實際證據顯示某個平台後綴真的對應：

- 不同 share class
- 不同幣別
- 不同配息型態
- 不同避險型態
- 不同 NAV series

則不得強制合併。

這種情況要產生 Exception / Decision Gate，再決定是否拆成不同 canonical identity。

因此正確模型是：

"base fund identity"
+
"channel/platform metadata"

而不是：

"完整原始代碼字串 = canonical identity"

---

3. ISIN 本階段不依賴

ISIN 目前：

- 不作 canonical key
- 不作必要欄位
- 不要求 Sheet 補 ISIN
- 缺 ISIN 不顯示警告
- 缺 ISIN 不影響一般基金 matching
- 不以 ISIN 作為 DG-2 第一階段的必要條件

若既有來源自然提供 ISIN，可保留為 optional verification attribute。

但目前不採：

"ISIN = 唯一基金身份"

---

4. share class／配息／避險不得猜

以下概念必須分開：

- currency
- share class
- platform suffix
- distribution type
- hedge status

禁止：

"currency = share class"

禁止：

"platform_suffix = share class"

禁止由基金名稱、後綴或幣別自行推測：

- 配息型
- 累積型
- 避險
- 未避險

沒有可靠資料時：

- "share_class = Unknown"
- "distribution_type = Unknown"
- "hedge_status = Unknown"

Unknown 不得視為相同、不同、安全或已確認。

---

5. 在實作 resolver 前，先查舊 UI

不要直接重新發明新的 identity 邏輯。

先做 targeted audit，查舊 UI 已實際使用過、長期跑過的基金 identity / NAV 邏輯。

依 Context Efficiency：

Search first → targeted read → only expand when needed

優先檢查：

- "ui/tab2"
- "ui/tab3"
- 舊單一基金頁
- 舊持股／portfolio 頁
- "repositories/fund/"
- policy / portfolio 對基金 code 的解析
- NAV、fund_url、MoneyDJ URL、平台後綴相關 caller
- nav_history
- fund_keys
- cache normalization

不要全 repo 大掃描。

---

6. 舊 UI 必須回答的問題

請明確回答：

A. 基金身份

舊 UI 遇到：

- "TLZF9"
- "TLZF9-AL001"
- "TLZF9-24A7"

最後是否都會收斂成：

"base_fund_code = TLZF9"

還是仍保留完整代碼？

B. 平台後綴用途

舊 UI 中後綴到底只是：

- 找平台頁面的 URL 資訊
- 通路識別

還是會實際影響：

- NAV
- currency
- share class
- valuation

C. URL parsing

舊 UI 是否已有穩定的：

"URL → base fund code → platform metadata"

邏輯？

如果有，優先復用或收斂，不另造第二套。

D. NAV

同一 base fund code 從不同平台 URL 取得 NAV 時：

- 是否最後一致？
- 是否已有 fallback？
- 是否已有 mapping？
- 是否會剝後綴後再抓？
- 是否有來源優先序差異？

E. 跨頁

舊 UI 的：

- 單一基金頁
- 我的持股
- portfolio
- 資產配置

是否共用同一 identity / NAV 邏輯？

還是過去數值不一致正是因為各頁各走不同 path？

---

7. 舊 UI 查證結果分類

每個舊邏輯標成：

- "REUSE"：已驗證，可直接沿用
- "ADAPT"：概念正確，但需包成新 Data Contract
- "LEGACY_COMPAT"：只為歷史相容
- "REJECT"：已知會造成 identity / NAV 錯配，不可沿用
- "UNVERIFIED"：尚未有足夠證據

不要因為「是舊 UI」就自動沿用，也不要因為「是舊 UI」就全部重寫。

---

8. 新 resolver 採 C+，先 Shadow Mode

舊 UI targeted audit 完成後，若沒有新的反證，第一階段採：

C+ canonical resolver

結構至少預留：

- "base_fund_code"
- "original_code"
- "platform_suffix"
- "channel_code"
- "currency"
- "share_class"
- "distribution_type"
- "hedge_status"
- "isin"（optional）
- "source"
- "as_of"
- "verification_status"

但沒有可靠來源的欄位保持 Unknown。

---

9. Shadow Mode 原則

第一階段：

- 不改 Sheet schema
- 不改 production 顯示
- 不改既有 NAV source precedence
- 不改 valuation
- 不改 FX
- 不改 return formula
- feature flag 預設關
- resolver 與現況並排運行
- 只記錄差異

至少產出：

"raw input"
→ "current parser result"
→ "new resolver result"
→ "difference"
→ "reason"

---

10. 必須新增／調整的測試

至少驗證：

Identity

- "TLZF9"
- "TLZF9-AL001"
- "TLZF9-24A7"
- 小寫
- MoneyDJ 不同 URL

能正確得到同一：

"base_fund_code = TLZF9"

同時保留不同 channel/platform metadata。

Platform suffix

預設後綴不建立第二個 canonical fund。

但若 evidence 顯示後綴對應不同 NAV series，必須能產生 exception，而不是硬合併。

Unknown

- 缺 ISIN不失敗
- 缺 share class 不猜
- 缺 currency 不猜 USD
- distribution / hedge unknown 不補值

External source validation

Morningstar／其他外部來源：

不得因為 "results[0]" 就直接接受。

若已知 identity attribute 明確衝突：

- 拒收
- 留 evidence
- 顯示：

"⬜ 資料來源不一致，暫無法判定"

Cross-View

同：

- base fund code
- NAV date
- currency

不同 view 的 NAV 必須一致。

如果不一致：

產生 source conflict，不得偷偷建立第二個 canonical fund。

---

11. NAV 與 Identity 分開處理

Identity resolver 的任務是回答：

「這是哪一檔基金？」

NAV resolver 的任務是回答：

「這檔基金在這個 as-of 的 canonical NAV 是多少？」

兩者不要混在一起。

所以即使：

"TLZF9"
"TLZF9-AL001"
"TLZF9-24A7"

被判定為同一核心基金，

仍需另外驗證：

同一日期／同一幣別的 NAV 是否一致。

若來源不一致：

進 source conflict。

不要用「不同平台」直接合理化不同 NAV。

---

12. 本階段禁止順帶修改

目前不要順便改：

- "get_latest_nav"
- NAV primary/fallback precedence
- FundClear / MoneyDJ / Yahoo 排序
- valuation methodology
- FX cutoff
- return formula
- Sheet migration
- One AI Brain

這些仍各自走 Decision Gate。

---

13. 舊 UI 是 Evidence，不是新的 SSOT

原則：

舊 UI 已驗證過的正確資料取得與 identity 邏輯，優先復用。

但：

- 舊 UI 不是自動 SSOT
- 需經測試／實際 caller／歷史使用證據確認
- 舊 UI 與現行治理衝突時，以現行正式規格與客戶裁示為準

不要把舊 UI 整套搬進新 UI。

只取：

- 已驗證的 Data Logic
- Identity Logic
- Source Logic
- Calculation Logic

UI 呈現仍依 vNext。

---

14. Cross-View 核心規則維持

最終一定要做到：

Same base fund + same metric + same as-of + same currency = same canonical value across all views.

頁面不得自行：

- 選 source
- 拆 identity
- 建平行公式
- 建自己的 NAV cache semantics

UI 與 AI 都只能消費 canonical data result。

---

15. 實作順序

本輪順序：

1. GitHub Verification Gate
2. targeted audit 舊 UI
3. 更新 DG-2 提案
4. 形成 old UI logic reuse matrix
5. 實作 C+ Shadow resolver
6. automated tests
7. 1 組必要獨立 audit
8. CI
9. 同 PR 同步必要 docs / HANDOFF
10. batch 完成才回報

維持 Anti-Bloat：

- 不派多餘 audit
- 不拆多餘 PR
- 不新增大量 BL
- 能同批就同批
- evidence 採 Minimum Sufficient Evidence

---

16. 工作模式

維持：

Silent Autonomous Cruise。

除了：

- 完整 batch 完成
- 真正 Stop / Decision Gate
- Model / Effort Change Gate
- 真正 blocker

其餘一律靜默。

不要回報：

- audit 派出
- 正在讀舊 UI
- 正在跑測試
- CI 還在跑
- 文件同步中

---

17. Model / Effort

這一批已涉及：

- canonical identity
- Cross-View consistency
- data contract
- 舊 UI identity logic consolidation

建議：

Model：Opus 5.5
Effort：High

但只對上述範圍使用 High；不要因此擴大讀取範圍或重掃整個 repo。
```
