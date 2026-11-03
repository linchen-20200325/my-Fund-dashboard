# #1136 合併後被取代的 HANDOFF／BACKLOG 片段（歷史；2026-11-03）

> ⛔ **NOT CURRENT — Historical evidence only — not current contract.** 本檔是 2026-11-03 整合 PR #1135（ChatGPT New UI2 文字設計修訂；`DEC-2026-11-03-12`）時，把 main `f07acd44`（含 #1136）的 `docs/HANDOFF.md` Resume Checkpoint、第 2 節三列、第 5 節首條，與 `docs/BACKLOG.md` BL-0536 整列**逐字**搬出的內容；現行區已改寫為 #1136 合併後的現況。**不是現行規則或現況，不得引用為 implementation authority。**
> 取代關係與原因：見 `docs/DECISIONS.md` `DEC-2026-11-03-12`；原位置現行區只留現況與指標。

## H3｜docs/HANDOFF.md 的 resume-checkpoint

<!-- MOVED-BEGIN id=H3 source=docs/HANDOFF.md#resume-checkpoint@f07acd44 sha256=f89c11e0bc5394b750a4f154d712cc35d5d2dedff5554dd6972c6138d593925a bytes=1860 -->
> **⏯ Resume Checkpoint**（總管提供；接手先依 `PROJECT_RULES.md` 6.1.2 比對 GitHub，不一致以 GitHub 為準；本區塊覆蓋舊版）
> - **查詢時點**：2026-11-03；**工作樹基底 main＝`875b1955`**（Merge #1134：Navigation Shell＋H5；含 #1131～#1134）；本批**未重查 GitHub**，接手先 `git fetch origin main`。
> - **Open／Draft PR**：以 GitHub 為準（本批 Shell 定字與降級首屏收尾批的分支尚未 push、尚未開 PR；由總管處理）。
> - **唯一下一接手點（單一）**：Shell 定字與降級首屏收尾批（`DEC-2026-11-03-11`）的獨立稽核 → CI → 合併；之後才做 💼 線框草稿（尚未開始，本批不做）。
> - **本批已落地**：Shell 字樣已正式定字，單一 SSOT 在 `shared/ui_semantics/rules.py` 的 `shell_*` 鍵；Status Bar 與側欄狀態區維持純文字、不放 chip／核心數字元素；全取得不寫「正常」；降級情境第一屏由 7 個名額收斂為 5（方案比較與前後計數見 `docs/v2/81` 第 10.2 節，量測 `docs/evidence/bl0536_shell_h5_2026-11-03/`）。
> - **仍待驗證（不得宣稱已通過；`docs/BACKLOG.md` BL-0536 逐條）**：iOS／Android 實機、Safari、深色模式、Yahoo／FRED 真實連線、Streamlit 升版後導覽相容性、安全的資料更新入口（更新資料 CTA 停用中；不得為完成 Shell 開新 refresh pipeline）。**待客戶確認**：狀態句內的「n／m 項已取得」不算頁級核心數字的讀法（若整句要算一個名額，降級會是 6，須回 Gate）。其後 wireframe Gate 順序仍是 💼 → 🔍 → ⚙️。
> - **已裁示、不再待裁**：🌍 首屏採 C 與用字統一（`DEC-2026-11-03-09`）；Shell 字樣、Status Bar 讀法、資料全取得不寫「正常」、降級首屏須 ≤5（`DEC-2026-11-03-11`）。

<!-- MOVED-END id=H3 -->

## H4｜docs/HANDOFF.md 的 section2-rows

<!-- MOVED-BEGIN id=H4 source=docs/HANDOFF.md#section2-rows@f07acd44 sha256=8aaef06542d386353afa2b510044eb922de118f6a56610e5be11c78754225335 bytes=743 -->
| 現行五頁 | 🌍 市場與趨勢／💼 我的資產／🔍 找基金／🤖 AI 投資總結（Phase 7 前不掛導覽）／⚙️ 設定（`PROJECT_RULES.md` 13.2 第 1 點；程式側 `ui_v3/shell/registry.py`） |
| 🌍 | wireframe 已裁示（`DEC-2026-11-03-01`）；歸一化 A2／B2／C2、H1b／H2／H3、Preview rendering、九項正式字樣、首屏採 C 與用字統一、Navigation Shell＋H5 已合併（#1125～#1134；`DEC-2026-11-03-07`、`-09`、`-10`）；Shell 定字與降級首屏收尾為本批（`-11`）。詳情看 `docs/BACKLOG.md` BL-0536 與 `docs/v2/81` |
| 💼／🔍／⚙️／🤖 | wireframe 尚未起草（順序 💼 → 🔍 → ⚙️；🤖 依 Phase 7）；核准前不寫該頁 `ui_v3` 代碼 |
<!-- MOVED-END id=H4 -->

## H5｜docs/HANDOFF.md 的 section5-first-bullet

<!-- MOVED-BEGIN id=H5 source=docs/HANDOFF.md#section5-first-bullet@f07acd44 sha256=cba814f4256653d315730a5d652b62b6ae3a884dab262f3c3d4f44329f46f1a1 bytes=327 -->
- main `875b1955` 為工作樹基底，**未重查 GitHub／CI**；#1134 已合併為 git log 所見，CI 結果未查。本批的量測為 Chromium＋注入的人造資料，真實連線、Safari、實機、深色模式未驗；降級名額守衛是 DOM 計數（AppTest 不載入 CSS），可視計數以 Playwright 為準。
<!-- MOVED-END id=H5 -->

## B3｜docs/BACKLOG.md 的 BL-0536

<!-- MOVED-BEGIN id=B3 source=docs/BACKLOG.md#BL-0536@f07acd44 sha256=4362f8a049a829f9d5b65f3bfd0a092e3daee47395ed0034f16dc5e220212e07 bytes=5678 -->
| BL-0536 | in progress（New UI2 `ui_v3` 多批實作；現況與唯一下一接手點見 `docs/HANDOFF.md`；舊狀態敘事已移歷史檔，不是現行狀態） | UX debt（New UI2 `ui_v3` presentation implementation；多批） | 2026-11-02 | **`ui_v3` presentation implementation（New UI2）**：依 `docs/v2/80_new_ui2_architecture_proposal.md` 第 13 節順序實作 —— 批 1：PORT 領域計算到共同層（＋ui_v2 re-export shim、import 守衛白名單、golden 不變）、`ui_v3` 骨架、Preview 入口、New UI2 import／readonly／頁序守衛、fake scenario fixtures 與 view model 骨架；批 2：呈現規則資料表＋Design token 命名；批 3～：逐頁先出 New UI2 wireframe 送客戶（`CLAUDE.md` §-1.5.4）→ view model → page → adapters → Visual Fidelity；後續 Digest／Risk Cap／Action State／OneBrain 接口另走 Gate。輸入：architecture／Reuse Matrix／migration boundary 已凍結、五頁 wireframe 為 implementation input、79 語意 contract（`DEC-2026-11-02-05`、`-07`）。⚠️ **PORT 批屬 formula／data semantics 等級**：須至少 1 組真正獨立稽核（`DEC-2026-10-16-05`），並依 `PROJECT_RULES.md` 5.1 第 10、11 點於開工前重新評估 Model／Effort（可能需另一次 Gate）。 | `DEC-2026-11-02-05`、`DEC-2026-11-02-06`、`DEC-2026-11-02-07`；`docs/v2/80` 第 10、13 節；`docs/v2/79`；`DEC-2026-11-03-01`～`-11`；`docs/v2/81` | 否（本身是下一階段主線） | 規則收斂批的獨立稽核增量、CI、合併（以 GitHub 為準） | **現況（2026-11-03）**：批 1 骨架（#1122）、批 2a PORT＋2b 呈現規則資料表（#1123）、🌍 wireframe（#1124；`DEC-2026-11-03-01`）、H1（#1125）、H1b（#1127）、H2（#1128）、H3（#1130）、🌍 Preview rendering（#1131）、🌍 九項正式字樣＋首屏採 C＋用字統一（#1132；`DEC-2026-11-03-07`、`-09`；首屏 Gate 已裁示結案、BL-0539 closed）已合併。Navigation Shell＋H5（#1134；`DEC-2026-11-03-10`）已合併。**Shell 定字與降級首屏收尾批（本批；`DEC-2026-11-03-11`；PR 待開，獨立稽核待做）**：客戶 2026-11-03 驗收裁示已落地——Shell 字樣已正式定字（單一 SSOT 在規則表 `shell_*` 鍵，`preview_wording` 舊暫擬定義退役）；Status Bar 維持純文字且不放 chip／核心數字元素；全取得不寫「正常」；降級情境第一屏由 7 個名額收斂為 5（圖下逐序列非 ok 狀態改一行文字摘要，方案比較與前後計數見 `docs/v2/81` 第 10.2 節，量測 `docs/evidence/bl0536_shell_h5_2026-11-03/`）。**仍待驗證（客戶裁示第五項；保留、不得宣稱已通過）**：(a) iOS／Android 實機；(b) Safari；(c) 深色模式（底部導覽配色）；(d) Yahoo／FRED 真實連線；(e) Streamlit 升版後導覽相容性（CSS 依賴內部 `data-testid`；想法：以 Playwright 量測做自動守衛，尚未實作）；(f) 安全的資料更新入口（更新資料 CTA 目前停用；須有正式 refresh 流程，不得為完成 Shell 而開始新 refresh pipeline）。**待客戶確認**：Status Bar 與側欄狀態句內的「n／m 項已取得」不算頁級核心數字的讀法（若整句算一個名額，降級會是 6，須回 Gate；總管讀法，不裁決）。另待客戶確認：圖下摘要行逐序列仍各列一項狀態，只是外觀由 chip 改為純文字，資訊量未減少；稽核指出若把任何帶 `data-status-key` 的狀態元素都算名額，降級情境 390px 比較檢視仍為 7（總管讀法，不裁決）；客戶若不接受此讀法（要求真正彙總），須回 Decision Gate，替代方案＝彙總句（已核准字樣「其中 {n} 項取數失敗」）＋逐序列移入「各項資料狀態」展開區（見 `docs/v2/81` 第 10.2 節）。**非阻塞追蹤（只登記，不修）**：Streamlit 內部 data-testid 依賴無自動守衛；evidence 的 `launch_injected_data.py` ROOT 寫死。**現行下一步**：(1) Shell 定字與降級首屏收尾批的獨立稽核、CI、合併（見 `docs/HANDOFF.md`）；之後才是 💼 線框草稿（尚未開始；本批不做）；(2) 待客戶裁示：BL-0369／H4（freshness 門檻；未裁示前首屏只顯示 `⬜ 門檻待裁示`）、仍為暫時字樣者（`docs/v2/81` 10.1 末段清單）、依據卡塊代號 `MKT-n` 是否顯示、依據卡資料日落點（D3 (i)）、匯率閘門開啟前 `業務例外`／方向文字（81 10.3）；(3) wireframe Gate 順序 💼（G2；連同 β 頁級字樣 W2 與 `chart_empty` 字樣問題 W1 一併提）→ 🔍（G3）→ ⚙️（G4）；🤖 依 Phase 7；各頁核准前不寫該頁 `ui_v3` 代碼；(4) ~~H5 首屏預算實測~~（→ 已完成：常態與降級情境第一屏皆為 5，見 `docs/v2/80` 17.5 與 `docs/v2/81` 10.2；狀態更新，不是漏刪）；(5) cutover 前 BL-0535。**未做／殘餘**：期間按鈕標明資料不足（81 3.3）；真實 Yahoo／FRED 連線未驗（環境限制）；週末起點殘留邊界維持 A2 contract（`DEC-2026-11-03-06`，需真實資料證明有語意錯誤才重開）。**之後**：~~Navigation Shell＋H5 390px 驗收（尚未開始）~~（→ 已實作，見上；狀態更新，不是漏刪）。**規則**：每個 `ui_v3` 實作批至少 1 組真正獨立稽核（客戶 2026-11-02 逐字；`DEC-2026-11-03-02` G3）；登記不構成動工授權（`CLAUDE.md` §-1）。**舊敘事全文**（批 1～Preview rendering 實作細節、獨立稽核紀錄、Minimum-Cost 比較依據；NOT CURRENT）：`docs/evidence/history/2026-11-03_backlog_bl0536_row.md`。 | 是（各頁 wireframe 核准；上列待裁示項）
<!-- MOVED-END id=B3 -->
