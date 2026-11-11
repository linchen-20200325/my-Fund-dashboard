# New UI2 ☀️／🌙 雙模式 B 方案：唯讀技術研究與 Decision Gate（2026-11-11）

> **文件定位**：docs-only 候選研究；不是新設計 SSOT、不是施工授權，也未覆蓋客戶既有的淺色主內容＋深色側欄裁示。研究時 main = `47417a975635b9bbda8f9bec877a24897dcc6240`，Open PR = 0。此為歷史觀測，接手必須重查 GitHub。本批沒有修改 `ui_v3`／`.streamlit/config.toml`／`ui_v2`／正式入口／資料／公式。
>
> **依據**：`DEC-2026-11-11-01`、`docs/evidence/fund_newui2_dual_theme_followup_requirement_2026_11_11.md`、#1207 合併施工證據、現行 `ui_v3/design/tokens.py`、`design/theme.py`、`pages/mkt.py`、`shell/nav.py`、`shell/registry.py`、`app_preview.py`、`.streamlit/config.toml`、`requirements.txt`。外部 Streamlit 文件僅作技術研究參考，實際已鎖定版本的功能兼容性仍須 PoC，不能以最新文件代替實測。
>
> 標記：FACT＝從 repo 讀到或有原始文件；INFERENCE＝推論；NOT VERIFIED＝尚未在 repo pin 的 Streamlit 1.59.x + Cloud／WebView／真機驗證。

## 一、已確認的阻礙（FACT）

1. `ui_v3` 目前只有 `mkt`（🌍 市場與趨勢）`registered=True`；⚙️ 設定頁 `set` 還沒有獲准實作的 renderer。**不得為了切換模式建立空殼設定頁或新增第六頁**。因此「切換放設定頁」仍是**期望位置**，不具備立即施工前提。
2. `ui_v3/design/tokens.py` 已有 G3 核准淺色調色盤（B 色票＋A 尺寸），`design/theme.py` 會把 token 轉成 CSS；`pages/mkt.py` 與 `shell/nav.py` 使用它。現況不是雙套 token；現有 `color.tone.grey` 與 `neutral` 值相同，`STATUS_TONES` 不得改。
3. `.streamlit/config.toml` 是 repo 共用的 Streamlit 全站 theme，仍為舊 light palette；`ui_v3` 用頁面自有 CSS 覆寫，而舊 UI／`ui_v2` 仍使用共用設定。**直接增加或替換全站 `theme.light`／`theme.dark` 會影響尚未授權的舊介面**。
4. `requirements.txt` 的 Streamlit 範圍為 `>=1.59.1,<1.60.0`。最新版官方文件描述的 API／行為不能直接當作 1.59.x 已驗證功能；須在與 repo 相同版本環境驗證。
5. `mkt.py` 有 Streamlit 原生 `st.radio` 與具名 `st.container`，自繪 HTML + native 控件都需要同步套色；不能只換 `body` 背景、不能用顏色作唯一狀態訊號。
6. G3／G6 已由 #1207 合併，三寬度和首屏現況有瀏覽器（Playwright）測試；雙模式尚未獲客戶授權施工。原始股票 HTML 參考側在 Claude 工作環境仍 NOT VERIFIED。

## 二、三種實施路徑

本節的路徑 A／B／C 與 `docs/evidence/fund_newui2_dual_theme_followup_requirement_2026_11_11.md` 的方案 A／B／C（A 固定淺色、B 手動切換、C 跟隨系統加手動覆蓋）是**不同的分類**，請勿混用。

| 路徑 | 做法 | 正確性／範圍風險 | 速度／Token | 研究建議 |
|---|---|---|---|---|
| A 全站原生雙 theme | 把 `.streamlit/config.toml` 變成 `theme.light`／`theme.dark`，沿用 Streamlit app menu 切換 | **高**：共用 config 影響舊 UI／`ui_v2`／正式入口，且與 `ui_v3` 自繪 CSS 可能不一致；需另行跨產品裁示 | 寫碼少、驗收與回滾成本高 | **本階段不選** |
| **B `ui_v3` scoped token + 明確選擇** | 保持原 light token 不變，增加經核准的 dark token 候選，`ui_v3` 局部按選擇編譯 CSS；原生控件、邊線與 hover/focus 同驗；切換入口須待設定頁 Gate | **中**：須對原生 Streamlit 元件/重跑同步做 PoC，但可隔離舊 UI、回滾簡單 | **中／中** | **推薦技術方向（未授權施工）** |
| C 自訂前端 JS + browser storage | 以 browser JS 或 custom component 切 theme 並保存偏好 | **中高**：JS/CSS 狀態雙來源、跨 WebView 相容性／XSS 安全／CSP／跨版本風險；增加依賴或前端契約 | 中慢／高 | 僅作 B 無法滿足「重載保持」時的後備 |

**特別提醒**：Streamlit 官方最新文件支援用 `[theme.light]`／`[theme.dark]` 供使用者在 App menu 選擇，但這是**全 app 層級**，且 repo pinned 1.59.x 的配置效果尚未做 PoC；不能把「官方支援」推導為「可無痛做 `ui_v3` 限定、且設定頁內切換」。`st.context.theme.type` 為**唯讀**，並且是依背景色推斷；以 scoped CSS 實作的深色（路徑 B）**不會**反映在它上面（它會持續回報設定的 theme，而不只是暫時不同），因此路徑 B 不得用它來偵測目前模式，也不可假設它是可寫的切換 API（已於 Streamlit 1.59.1／1.59.2 docstring 查證）。

外部參考（2026-11-11 查閱）：[Streamlit Theme overview](https://docs.streamlit.io/develop/concepts/configuration/theming)、[config.toml Theme](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)、[st.context theme 1.58](https://docs.streamlit.io/1.58.0/develop/api-reference/caching-and-state/st.context)、[Session State limitations](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state)。註：`st.context theme 1.58` 連結版本與 repo 鎖定的 `>=1.59.1,<1.60.0` 不一致；API docstring 已對照已安裝的 1.59.1／1.59.2（離線）檢查，外部頁面內容仍為 NOT VERIFIED。

## 三、偏好保存契約：不要把 session 當作永久記住

| 候選 | 切換後 rerun／同頁 | 瀏覽器重載／新分頁 | 跨裝置 | 額外風險 |
|---|---|---|---|---|
| `st.session_state` | 可（repo 既用 `session_state`） | **不可保證**：連線重建可重設 | 不可 | 最低；可做階段性 PoC，不可承諾「永久記住」 |
| URL query parameter | 可由 URL 傳遞 | 直接使用同 URL 時可重現；其他進站方式不保證 | 分享 URL 時可傳遞 | 分享會洩漏外觀選擇但非金融資料；URL 參數與既有 routing、頁切換、導航合同需驗。另：Streamlit 1.59.x 部分 widget（如 `st.radio`）有原生 `bind="query-params"` 選項，需 PoC，用於本用途 NOT VERIFIED |
| Browser storage + bridge/custom component | 若同步正確即可 | 理論可 | 不可 | 同源/CSP、WebView、元件生命週期與 Streamlit rerun 均 NOT VERIFIED |
| 會員設定／遠端 DB | 可以 | 可以 | 可以 | **超出本批範圍**，涉及登入、權限和新的儲存契約，必須另行裁示 |

**建議分段**：第一個技術驗證先用 session-only 證明切換不破壞資料/控件；真正要達到「關閉再開仍記住」再比較 browser-local 與未來既有使用者設定，**此二者均不能先當作已核准**。不得使用 `Active Sheet` 或共用系統 Sheet 偷存個人外觀偏好。

## 四、深色視覺候選（不是核准值）

以下僅為 **研究示例**，來自先前 #1204 token 文件 §A.9 的「深色研究備註」，不是核准色票，未在最新 G3 程式上重新渲染：

| 語意 | light（目前 G3 已核准） | dark（研究示例、未核准） |
|---|---|---|
| 頁面底 | `#f5f7fb` | `#0f1626` |
| 卡片面 | `#ffffff` | `#172036` |
| 主要文字 | `#172033` | `#e6edf3` |
| 次要文字 | `#4a5670` | `#a9b4c9` |
| primary | `#1a5fd0` | `#5b9dff` |
| 卡片邊 | `#7f8ca6` | `#5a6c94` |
| red 邊／文字 | `#c0392b`／`#8a1f12` | 不得直接沿用；候選 `#ff8a7a`（需依實際容器重算） |
| yellow 邊／文字 | `#b7791f`／`#6b4a0a` | 候選 `#e8b84a`（需驗） |

- 已有 #1204 §A.9 **單組**比值研究：深底下原來 red 邊接近／低於非文字 3:1，不能單靠換背景；需重新獨立複算文字（4.5:1）、非文字狀態邊界（依實際功能判定）、hover/focus、disabled、chart label 與 Streamlit 原生控件。
- 顏色依舊是資訊的第三重：文字＋符號優先；所有資料狀態 `STATUS_TONES`、缺值行為與圖表數列身分不得變。
- 限制：沒有 browser screenshot，也沒有真機證據。淺色卡片/側欄已核准的尺寸（圓角 8、caption 13、720px 圖寬等）原則上不因 dark 而動，具體是否保持同感須實測。

## 五、最小安全實作前置及 G7 驗收

1. **隔離 PoC（尚未授權）**：在不改正式 `ui_v3`／共用 config 的 sandbox 驗證 pinned Streamlit 1.59.x：scoped theme CSS 生效、原生 radio/expander hover/focus/disabled、session rerun、跨頁（頁面未掛載者不可造空殼）；測試先行，所有數字用合成 fixture，絕不取真實持倉。
2. **實作前 Decision Gate**：設定頁目前不可用，須決定先等 ⚙️ 頁線框與實作 Gate，或核准一個與既有五頁 IA 相容、非第六頁的最小入口。**不可自行新增設定頁**。
3. **性能與回歸**：390／768／1280px，各 light/dark 視覺量測；無橫溢；不降低已核准的主圖首屏可見量；頁首五格與桌機側欄不改；操作 radio/期間切換、顯示缺資料/failed/stale、chip 狀態不變；同 session 多次切換、重新整理、不同 session、返回頁面皆檢查。
4. **獨立 QA**：dark/light 對比重算、字級 12 vs 13px/neutral vs grey 先保留為獨立 Gate、沒有 fake 數值、token 單一真相源、fixture 僅測試。G7 Cloud／WebView／真機／螢幕閱讀器尚未授權／尚未驗證；正式採用前需要另外驗收。
5. **明確禁止**：`.streamlit/config.toml` 全域改動、`ui_v2`、正式 App 入口、金融算法、資料來源、FX Gate、OneBrain、`STATUS_TONES`、個人 Active Sheet／系統 Sheet 寫入；BL-0545 全域唯一 NEXT 不變。

## 六、待客戶裁示（**這份研究不代替裁示**）

- **T1（架構）**：是否採用 B「`ui_v3` scoped 雙 token、手動切換」做後續 PoC？推薦 B；建議不核准全域 config 改動。
- **T2（入口時機）**：等 ⚙️ 設定頁完成再顯示切換，或提前核准僅 Preview 使用的最小入口？推薦等設定頁，不做空殼。
- **T3（記住偏好）**：先僅 session，或本期就增加 browser-local persistence？推薦先 session PoC，永久保存另批裁示；客戶期望「記住」仍需後續達成，不得稱已完成。
- **T4（視覺）**：上述 dark 示例色票可否作 PoC 候選？推薦只授權在隔離 PoC 測試，不作正式色票，待雙模式對照截圖後核准。
- **T5（驗收）**：是否授權 G7 Cloud／WebView／真機驗收？推薦在真正有 dark 實作、且非作者 QA 完成後才驗收；現階段維持未執行。

**其他待客戶裁示**（分離）：#1207 的 `config.toml` 是否全域統一、12px 小字是否調 13px、`grey`／`neutral` 是否視覺分開；FRED P1 G2/G3/G4 未授權。不要把本方案推薦自動轉為以上問題的裁示。

**交接**：本 PR 以後續 commit 同步加入 BACKLOG／HANDOFF 索引指標；**未新增 DEC**，因 T1–T5 皆未決定，不得創造新的客戶決策，也未改動 DECISIONS。若發現重複的 PR／本檔過時，先在最新 GitHub main／diff 查核後修復或關閉。
