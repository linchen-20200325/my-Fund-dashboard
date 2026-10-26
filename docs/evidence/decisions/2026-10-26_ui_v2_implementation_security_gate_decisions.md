# 2026-10-26｜新 B UI Implementation / Security Gate 正式裁示

> provenance：**客戶裁示（要點轉述）**。客戶於 2026-10-26 明確要求將本批規劃寫入 GitHub；下列內容由 ChatGPT 協作助手依既有 SSOT、Long-term UI & Logic Sustainability Principles 與 GitHub 現況收斂後，經客戶確認落盤。
>
> 本檔是本批裁示的可追溯 evidence；正式索引應在下一個必要文件批次同步到 `docs/DECISIONS.md` / `docs/HANDOFF.md`，但不得因此解凍 `docs/v2/44_fund_ui_ssot.md`。

## 0. 適用範圍

適用於新 B UI 第一階段的：
- Personal OAuth
- Google Sheet 唯讀接線
- Active Sheet runtime state
- SET-5 重新取數
- error taxonomy
- 尚未選定 Active Sheet 的 UX

既有長期原則不變：
- 五頁資訊架構長期穩定。
- 資料層、Domain/Rule、AI、UI、Infrastructure 分層。
- Missing 不得改寫成 0／False／HOLD／中性／正常／安全／未觸發。
- 新 B UI 第一階段全部唯讀。
- `SET-4` 第一階段不顯示。
- 不因本裁示解凍 44。

---

## 1. J-1｜OAuth scope 採最小權限

第一階段目標 scope：
- `spreadsheets.readonly`
- `drive.metadata.readonly`
- `openid`
- `userinfo.email`

規則：
- 現行 `spreadsheets` 讀寫 scope 改為 readonly。
- `drive.file` 若無讀碼證明為第一階段必要，移除。
- 不使用 `include_granted_scopes=true` 繼承歷史較大授權。
- 不新增任何寫入 scope。
- 若 Google API 實際流程證明仍需額外 scope，只准最小新增，不得直接恢復廣泛寫入權限。

## 2. J-2｜OAuth state / PKCE

正式 Personal OAuth 必須 fail closed：
- state missing → callback 失敗。
- state mismatch → callback 失敗。
- state expired → callback 失敗。
- session state 遺失不得放行。
- 失敗後重新開始 OAuth。

加入 PKCE S256：
- `code_verifier` 只短期存在 server/session runtime。
- authorize request 帶 `code_challenge`。
- token exchange 使用對應 verifier。
- verifier 不寫 log／Sheet／repo。

## 3. J-3｜Token / Logout / Account switch

第一階段：
- token / refresh token 只存在 server-side/session runtime。
- 不寫 Google Sheet。
- 不寫 repo。
- 不寫 plaintext file。
- 不放 browser-visible query parameter。
- 不建立新的長期 token database。

Logout：
1. 嘗試 revoke Google token。
2. 不論 revoke API 是否成功，都清除本地 OAuth session state。
3. UI 回到未登入狀態。

切換帳號：
- 清理舊登入狀態。
- 不沿用舊 Active 驗證狀態。
- 重新走 OAuth。
- 舊 token 不得作為新帳號 fallback。

跨 session 記住登入若未來有需要，另設 secure per-user store；第一階段不做。

## 4. J-10｜Streamlit Cloud 與 Personal OAuth 狀態隔離

- Personal OAuth 與 Streamlit identity/auth state 必須 namespace 分離。
- 不重用彼此 state key。
- 不做 token fallback。
- 不做 account identity fallback。
- callback 失敗不得借另一登入狀態視為成功。
- OAuth callback 仍以自己的 state + PKCE + account identity 驗證為準。

## 5. J-11｜護欄 4 放寬範圍

只准放寬：
- Settings 建立／選擇／驗證 Active Sheet。
- Holdings 與其他已核准 consumer 對 Active Sheet 的**唯讀**接線。

不得藉此放寬：
- Sheet 寫入。
- credential storage。
- token persistence。
- 自動 fallback。
- 新資料來源。
- service account 冒充 personal OAuth。
- 其他未核准 domain/data contract。

## 6. SET-5｜第一階段 Google Sheet 零寫入

第一階段唯讀採嚴格解釋：**Google Sheet = 零寫入**。

SET-5「重新取數」可：
- 重新讀取來源。
- 更新 memory/cache。
- 更新畫面 freshness。

但若現行流程會寫入：
- `fetch_log`
- `market_indicator`
- 或任何其他 Google Sheet

第一階段必須停止該持久化寫入，或改成不寫 Google Sheet 的 runtime telemetry。

不建立「診斷寫入例外」。Missing／freshness 必須如實顯示。

## 7. UI_V2_READ_ONLY｜改成預設唯讀

不要等最終上線才開啟唯讀。

下一安全實作批次應：
1. 移除／隱藏新 B UI 第一階段所有寫入控制。
2. `SET-4` 維持完全不顯示。
3. SET-5 移除 Google Sheet 持久化寫入。
4. 測試證明 `ui_v2` 第一階段沒有 Google Sheet write surface。
5. 同一批或緊鄰批次把新 B UI 切為 **default read-only**。
6. 不再依賴「必須手動設定 `UI_V2_READ_ONLY=true` 才符合 J-6」。

若環境旗標保留，只能用作更嚴格控制／測試，不得讓 production B UI 預設重新變成可寫。

## 8. J-5｜Active Sheet runtime SSOT

第一階段：
- `st.session_state` = 使用者 runtime Active Sheet SSOT。
- Pending 與 Active 分開。
- 驗證成功後才更新 Active。
- 驗證失敗保留原 Active。
- 不做跨 session 持久化。
- 不為了「記住上次選擇」寫回 Google Sheet。

若未來確實需要 persistent Active Sheet，再另設 secure per-user storage。

## 9. J-7｜Personal OAuth / Service Account 共存但分工

### Personal OAuth
負責：
- 使用者可存取 Sheet 清單。
- 使用者選定的 Active holdings/policy Sheet。
- 新 B UI 的使用者資料讀取。

### Service Account
維持：
- 既有 deployment-owned/system-owned data source。
- 既有設定試算表等仍屬 deployment config 的來源。

禁止：
- Personal OAuth 失敗後偷偷改用 service account 讀同一本 Active Sheet。
- service account 失敗後偷偷切 personal OAuth。
- 任一來源缺失時自動換另一本 Sheet。

`POOL_SHEET_ID` 現行 baked default 屬隱式 fallback：
- 移除 baked default。
- 無明確設定 → Missing／Unavailable。
- 不新增替代 Sheet。

## 10. J-9｜正式 error taxonomy

至少建立以下 deterministic error categories：
- `AUTH_REQUIRED`
- `AUTH_EXPIRED`
- `AUTH_STATE_INVALID`
- `PERMISSION_DENIED`
- `SHEET_NOT_FOUND`
- `SCHEMA_INVALID`
- `NETWORK_ERROR`
- `UPSTREAM_ERROR`
- `UNAVAILABLE`

規則：
- error code 屬 domain/service contract。
- UI 再轉成人類可讀文字。
- 不以 exception string 作唯一邏輯。
- Missing 與 Error 分開。
- Error 不得轉成 0／正常／安全／中性。

## 11. J-13｜尚未選 Active Sheet

其他四頁若需要 Active Sheet 但尚未選定：

顯示：
`⬜ 尚未選定持倉資料來源`

提供：
`前往 ⚙️ 設定`

不得：
- 自動使用 `POLICY_SHEET_ID`。
- 自動選第一本 Sheet。
- 使用舊 session 過期值。
- fallback service account。
- fallback 其他 workbook。

## 12. 文件小瑕疵

`docs/DECISIONS.md` 在 `DEC-2026-10-25-04` 附近的既有殘缺斷行：
- 不獨立開 PR。
- 下一次必要文件修改順手修。
- 不改變任何決策語意。

## 13. 建議實作順序

依安全小批次推進：
1. OAuth security foundation。
2. readonly enforcement / SET-5 zero-write。
3. Active Sheet runtime SSOT + consumer wiring。
4. error taxonomy / no-active UX。
5. necessary docs sync。

順序可依 dependency 微調，但不得改變本裁示語意。

每批：
- tests
- 依既有 security audit 規則執行
- CI
- Auto-Ship
- 合併後繼續下一安全批

## 14. Model / Effort

此階段涉及：OAuth scope、state、PKCE、token/revoke、security boundary。

建議：
- **Model：Opus 5.5**
- **Effort：Medium**

依既有 Model × Effort Change Gate 執行；若配置不同，於 safe checkpoint 通知客戶手動切換。

## 15. 不停工規則

本檔已裁示事項不得再次升級成一般 Decision Gate。

一般實作疑問：
1. 先查 GitHub SSOT / DECISIONS / PROJECT_RULES。
2. 可由既有規則推導 → 直接執行。
3. 仍有疑義 → 整理 A/B + 推薦交 ChatGPT 協作助手判斷。
4. 只有真正 Stop Gate 才停給客戶本人。

真正 Stop Gate 仍限於既有規則，例如：
- 不可逆操作。
- 新資料來源／付費服務。
- 新投資核心語意／Risk Cap／重大 data contract。
- 新的重大 OAuth/credential/token/scope 安全取捨。
- 凍結 SSOT 解凍。
- 超出核准 roadmap。
- Model/Effort Change Gate。
- ChatGPT 協作助手仍判定需要客戶本人裁示。

---

## 16. 追溯基準

本裁示落盤時 GitHub 基準：
- main：`498494eedf6d1c5ae20a6ba053ab76068646e0fa`
- #1061 已合併：Long-term UI & Logic Sustainability Principles。
- 本批不修改 `docs/v2/44_fund_ui_ssot.md`。
