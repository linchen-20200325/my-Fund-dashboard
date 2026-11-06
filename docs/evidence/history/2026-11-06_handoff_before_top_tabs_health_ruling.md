# NOT CURRENT｜2026-11-06 B 上方頁籤裁示前 HANDOFF Resume Checkpoint（逐字歷史）

> 這份是過期 Resume Checkpoint 的原文備份；最新狀態只看 `docs/HANDOFF.md` 並重新核對 GitHub。原始 `docs/HANDOFF.md` 基準 main `861628cc377352c4f651ddc1172e13ab07e4d90d`，日期 2026-11-06。不能把舊 G-2 進度或舊 SHA 冒充最新。

> **⏯ Resume Checkpoint**（總管提供；接手先依 `PROJECT_RULES.md` 6.1.2 比對 GitHub，不一致以 GitHub 為準；本區塊覆蓋舊版）
> - **查詢時點**：2026-11-05；最新 main 為 `81827057`（G1-③ #1148 已合併，本批基底；#1147 為 `d4eabb35`、#1146 為 `1f260bfc`、#1144 為 `b9595833`、#1139 為 `66a09ed2`）；#1136（Shell 定字與降級首屏）先前合併為 `f07acd44`；main 現況與 Open／Draft PR 以 GitHub 為準；本批**未重查 GitHub**，接手先 `git fetch origin main`。
> - **Open／Draft PR**：以 GitHub 為準；接手先 `git fetch origin main` 並查 `gh pr list`。
> - **唯一下一接手點（單一）**：G-2 以 GitHub 實況為準；之後：等客戶另批授權（市值基準的 NAV／匯率組裝與 NAV 10 日門檻歸屬 Gate、⚙️ 登入／Active 入口、或 💼 頁 wireframe 與 ui_v3 接線；需 Effort Gate 與獨立稽核）。G-2 為最小 Preview 資料載入轉接層（`ui_v3/adapters/assets_source.py`；未接任何頁面或 renderer、守衛零變更），授權依據為客戶 2026-11-05 於對話中的指示（要點轉述、非逐字）；G-3～G-5、OneBrain／Phase 7 與 💼 程式照舊未授權。
> - **2026-11-05 G-2 批**：G1-③ 已合併（#1148，main `81827057`）；G-2 最小 Preview 資料載入轉接層（`ui_v3/adapters/assets_source.py`；模組層只匯入 `services.v2_domain.*`、L2 惰性匯入；不接頁面／renderer；市值基準組裝未移植、回阻擋結果）的 PR 以 GitHub 為準；被覆寫的舊接手點句逐字搬至 `docs/evidence/history/2026-11-05_after_1148_handoff_superseded.md`（H13；NOT CURRENT）；基底 main `81827057`，未重查 GitHub／CI。
> - **2026-11-05 G1-③ 批**：G1-② 已合併（#1147，main `d4eabb35`）；G1-③ Complete Evidence 產生器（`services/v2_domain/allocation_evidence.py`，純 Domain；`fx_row_as_of` 重構、`fx_rate_as_of` 委派且逐位元組一致）的 PR 以 GitHub 為準；被覆寫的舊接手點句逐字搬至 `docs/evidence/history/2026-11-05_after_1147_handoff_superseded.md`（H12；NOT CURRENT）；基底 main `d4eabb35`，未重查 GitHub／CI。
> - **2026-11-05 G1-② 批**：G1-① 已合併（#1146，main `1f260bfc`）；G1-② 最小共用核心 PORT 的 PR 以 GitHub 為準；被覆寫的舊接手點句逐字搬至 `docs/evidence/history/2026-11-05_after_1146_handoff_superseded.md`（H11；NOT CURRENT）；基底 main `1f260bfc`，未重查 GitHub／CI。
> - **2026-11-04 G-1 方向登記批**：`DEC-2026-11-04-03`（客戶方向裁示，要點轉述、非逐字）＋ BL-0542 G-1 狀態備註；被覆寫的舊接手點句逐字搬至 `docs/evidence/history/2026-11-04_after_1145_handoff_superseded.md`（H10；NOT CURRENT）；基底 main `e6ff1902`，未重查 GitHub／CI。
> - **2026-11-04 #1144 整合批**：客戶核准的 💼 U1～U5 全部 UI 設計與缺 FX 方案 A（`DEC-2026-11-04-02`；82 §9.8）已併入；#1142／#1143 已合併；僅 UI 設計核准，不授權 G-1～G-5 或 💼 程式；被覆寫的舊接手點句逐字搬至 `docs/evidence/history/2026-11-04_after_1144_handoff_superseded.md`（H9；NOT CURRENT）；基底 main `b9595833`，未重查 GitHub／CI。
> - **2026-11-04 #1140 整合批**：客戶核准的 💼 版面方向（主圖在前、四格摘要在後、缺值如實 Missing；僅 UI 順序，不授權 G-1～G-5 或 💼 程式）已併入 `DEC-2026-11-04-01`／82 §0.1；被覆寫的舊接手點句逐字搬至 `docs/evidence/history/2026-11-04_after_1139_handoff_superseded.md`（H8；NOT CURRENT）；基底 main `66a09ed2`，未重查 GitHub／CI。
> - **本批已落地**：#1135 的有效成果併入 `docs/v2/80`（第 7.4 節 🤖 導覽可見但不可點、不註冊頁面；第 16.1 節 Chart SPEC 位置）；#1135 的第 17.3／17.4 節與 HANDOFF 改動不併入（正式字樣只在 `shared/ui_semantics/rules.py::APPROVED_WORDING`）。Shell 定字、Status Bar 純文字、降級情境第一屏 ≤5 已隨 #1136 合併（`DEC-2026-11-03-11`；量測 `docs/evidence/bl0536_shell_h5_2026-11-03/`）。
> - **2026-11-04 #1138 整合批**：ChatGPT 的 💼 施工前草案 `docs/v2/82` 已併入（~~待客戶核准、非規格~~ 現況：U1～U5 UI 設計已核准〔`DEC-2026-11-04-02`〕、僅 UI；其餘仍待裁示；非規格）；三組獨立稽核（單組各自）已核實 §2／§4 並回修，結果在 82 第 8 節；稽核新增的待客戶問題與 Decision Gate 候選（G-1～G-5）登記於 `docs/BACKLOG.md` BL-0542；基底 main `21296a0d`，未重查 GitHub／CI。
> - **仍待驗證（不得宣稱已通過；`docs/BACKLOG.md` BL-0536 逐條）**：iOS／Android 實機、Safari、深色模式、Yahoo／FRED 真實連線、Streamlit 升版後導覽相容性、安全的資料更新入口（更新資料 CTA 停用中；不得為完成 Shell 開新 refresh pipeline）。
> - **待客戶確認（總管讀法，不裁決）**：圖下摘要行逐序列仍各列一項狀態，若稽核把帶 `data-status-key` 的元素都算名額，降級 390px 比較檢視仍為 7；替代方案＝彙總句加逐序列移入展開區（`docs/v2/81` 第 10.2 節）。Status Bar 與側欄狀態句內的「n／m 項已取得」不算頁級核心數字的讀法（若整句算一個名額，降級會是 6，須回 Gate）。
> - **已裁示、不再待裁**：🌍 首屏採 C 與用字統一（`DEC-2026-11-03-09`）；Shell 字樣、Status Bar 讀法、全取得不寫「正常」、降級首屏須 ≤5（`DEC-2026-11-03-11`）；#1135 文字修訂授權與 💼 階段分工（`DEC-2026-11-03-12`）。
> - **舊 Checkpoint 全文**（#1136 合併前版本；NOT CURRENT）：`docs/evidence/history/2026-11-04_after_1136_handoff_backlog_superseded.md`（H3）。

