# 客戶 2026-11-02「Final UI／Decision System Contract Freeze」任務指示與同日兩則追加指示（逐字摘錄）

- **來源**：客戶 2026-11-02 在對話中的「Final UI／Decision System Contract Freeze」任務指示，以及同日兩則追加指示（Durable GitHub Persistence／Progress Integrity；恢復 Silent Autonomous Cruise／No Progress Narration）；經總管逐字轉存為文字檔。執行組未見客戶對話本身，只依派工單抄入。
- **摘錄範圍**：任務指示全文 61 節（第 61 節為同日第一則追加指示）過長，只摘錄與後續落盤有關的段落：第 3、4、8、9、30、48、51、52、55、57、61 節，以及同日第二則追加指示的摘錄（圍欄內「……」為總管轉存時的省略，不是本檔省略）。**未摘錄**：第 1、2、5～7、10～29、31～47、49、50、53、54、56、58～60 節。
- **補抄**：第 57 節開頭「請把以下五條視為本輪最高優先 Proposal：」一句為客戶原文，由總管於獨立稽核後補抄（2026-11-02）。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-02-01`。落地：`docs/v2/79_final_ui_contract_freeze.md`（proposal）、`docs/BACKLOG.md`（BL-0531、BL-0532 與相關列尾指標）、`docs/HANDOFF.md` Resume Checkpoint。
- **存檔日期**：2026-11-02
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
（第 3 節）本輪任務主軸：執行 Final UI / Decision System Contract Freeze。這一輪的目的不是繼續增加功能。目的是：在 Batch E、Batch F、Decision Digest、Risk Cap、OneBrain runtime 繼續實作前，把基金儀表板最終 UI、圖表語意、資料契約、規則層與 AI 邊界一次收斂。核心目標：先把規格定清楚，再做 production，避免邊做邊改浪費 Token。
（第 4 節）本輪只允許：repo audit、docs-only、architecture proposal、contract proposal、gap matrix、wireframe / textual wireframe、Decision Gate、BACKLOG / DECISIONS / HANDOFF 的必要同步。本輪禁止：production UI implementation、新資料來源接入、Risk Cap runtime、OneBrain runtime、Provider runtime、新公式 production、修改舊 UI、直接修改 frozen SSOT（除非既有治理規則明確允許且經過 Gate）、自行發明 threshold、自行發明 Risk Cap 數值、自行發明 AI 機率、自行發明 action trigger、自行把草稿數字升格為產品常數。
（第 8 節）Final IA — 只接受基金版五頁：1. 🌍 市場與趨勢 2. 💼 我的資產 3. 🔍 找基金 4. 🤖 AI 投資總結 5. ⚙️ 設定。不新增第六個主要頁面。
（第 9 節）全站正式方向：圖表 > 數字 > 短句 > 長文字。但：Presentation Simplification ≠ Data Simplification。UI 可以簡潔。Data / Domain / Decision Digest 不能因 UI 收合而被刪除。
（第 30 節）找基金 Primary Visual 建議：Normalized NAV，Base = 100。必須顯示：base date、date range、frequency、missing treatment、each fund as_of、source。
（第 48 節）Missing Contract：沿用正式基金專案語彙。缺資料時：「◇ 資料未備」，不要新造另一套詞。並遵守：missing ≠ 0、unavailable ≠ neutral、not evaluated ≠ safe、unknown ≠ HOLD。
（第 51 節）本輪可以建立類似 docs/v2/79_final_ui_contract_freeze.md，但定位必須是：Proposal / Decision Gate / Migration Contract，不是第二套 UI 憲法。不得凌駕：PROJECT_RULES、frozen 44、67、正式 DECISIONS。
（第 52 節）Final UI Contract 客戶核准後：正式規則應回寫到既有 canonical SSOT：docs/DECISIONS.md、docs/BACKLOG.md、docs/HANDOFF.md、docs/v2/67、必要時正式 amendment。79 保留：rationale、migration map、visual contract rationale。避免 SSOT duplication。
（第 55 節）建議實作順序：Step 1 收斂 #1117。Step 2 Final UI Contract Freeze。Step 3 客戶一次性裁示。Step 4 Batch E production：🔍 找基金。Step 5 Batch F：⚙️ 設定 / audit / source health。Step 6 Decision Digest production。Step 7 Risk Cap / deterministic action rules。Step 8 OneBrain Provider / Cache / Trace / Budget。Step 9 OneBrain controlled integration。不要未經客戶裁示自行開始 Step 4 以後。
（第 57 節）請把以下五條視為本輪最高優先 Proposal：最重要的五條鐵則：1. Single Action Authority：唯一 action authority：Deterministic Engine + Risk Cap → System Action State，OneBrain 不另發 action。2. No Uncalibrated Probability：沒有 calibration contract：禁止 AI 百分比機率。3. Constraint Precedence：Hard Constraint 優先於 AI interpretation。4. Field-Level Provenance：每一個影響決策的資料，都有自己：source、as_of、retrieved_at、freshness、missing。5. Auditability：每一個 action / AI conclusion：UI → Decision Digest → Rule → Canonical Data → Source 必須可追溯。
（第 61 節，同日追加指示）Durable GitHub Persistence / Progress Integrity：本輪所有經客戶核准、可影響後續 implementation 的內容，不能只留在聊天、PR description 或單一 proposal 文件中。必須依性質同步回 GitHub 的正式治理文件。A. 正式客戶裁示 → docs/DECISIONS.md＋必要的 evidence。B. 尚未完成工作 → docs/BACKLOG.md，每一項至少標示：ID、狀態、blocker / dependency、所屬 Phase / Batch、是否 Decision Gate、是否 Data / Rule / UI / AI 類、完成條件；不得只在 docs/v2/79 裡提到卻沒有正式 backlog tracking。C. 最新接手狀態 → docs/HANDOFF.md（latest verified main SHA、Open / Draft PR、current active batch、已完成項目、未完成 Decision Gate、唯一下一安全接手點、已核准但尚未實作的 Contract、blocked / deferred 項）；HANDOFF 仍只是 secondary evidence。D. 正式 AI / Decision Digest 語意若客戶核准後屬於正式語意 → 同步到 docs/v2/67，不要讓 79 成為第二套 AI 憲法。E. Frozen UI SSOT 若需改動 docs/v2/44 不得直接修改，必須依既有 amendment / Decision Gate 流程。Progress Integrity Guard：本輪結束前核對 DECISIONS／BACKLOG／HANDOFF／Proposal pending-completed 與 GitHub 一致；已完成項不得仍標 pending；未完成項不得被誤寫 closed；superseded 規格必須標示來源與取代範圍；不得依聊天記憶補狀態；自動排程 commit 若推進 main，需更新 handoff 的 verified SHA；PR 合併後要再做一次 post-merge GitHub Verification Gate。原則：Chat is not SSOT. GitHub is the durable project memory.
（同日第二則追加指示，摘錄）你目前違反 Silent Autonomous Cruise / No Progress Narration Gate。……從現在起恢復完全靜默自主巡航。只有以下 4 種情況才允許主動回報：1. 🔴 真正需要客戶裁示的 Decision Gate 2. 🔴 無法自行解決的 blocker 3. 🟡 Model / Effort Change Gate，需要客戶知道或切換 4. 🟢 整個 Batch / Phase 完成後，一次性收尾回報。以下全部禁止：正在讀檔、正在 audit、audit 剩幾項、CI 正在跑、slow lane 正在跑、等待 CI、PR 等待合併、合併後準備做什麼、下一個 PR 準備提交、worktree / scratchpad / agent 狀態、任何「目前做到哪裡」但不需要客戶行動的訊息。……這條規則也必須維持既有 PROJECT_RULES.md / DECISIONS 中的 No Progress Narration Gate，不得因新對話、模型切換、長任務或 CI 等待而失效。
```
