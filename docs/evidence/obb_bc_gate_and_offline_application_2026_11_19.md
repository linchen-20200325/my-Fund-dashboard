# OB-B (b)(c) 最小 Decision Gate ＋「離線 Typed Interface／Fake Provider」施工申請草稿

> **單組作者（執行組）草稿，尚待非作者獨立稽核。** 屬 AI behavior boundary／治理等級（`DEC-2026-10-16-05`；`PROJECT_RULES.md` 第 4 節「會改變投資判斷的 AI 行為」＝停下問客戶；第 8 節＝至少 1 組真正獨立稽核）。
> **docs-only 候選；不是客戶裁示、不是施工授權、不是 DEC**（`CLAUDE.md` §-1）。基準 `origin/main` `eb08c5fc`（2026-11-19，唯讀 `git show`）。路徑寫「檔案::符號」不寫行號。
> 標記：**[F]**＝可由檔案／文件重現；**[I]**＝推論；**[R]**＝推薦，可被客戶推翻。全稱句一律「單組未驗」。
> **方向來源**：「OneBrain 另走 OB-B、沿用 `DEC-2026-11-18-03`、優先收斂 (b)(c)、僅限離線 Typed Interface／Fake Provider、不等待全部 D2、不實作 Digest／正式 Provider／LLM runtime／投資行動」為 ChatGPT 總管裁示（客戶經 ChatGPT 轉達〔待核〕，非逐字，repo 無對應 DEC）。**本卡不把它寫成客戶逐字規格；它本身也是又一則轉述，不能當作 (a)(b)(c) 的客戶確認。**

## 0. 結論先行
1. **[F] (b)(c) 各是一句話**：(b)＝`DEC-2026-10-31-03` 的 fake provider 階段是否已被另行裁示；(c)＝`DEC-2026-11-08-02` 的「Phase 7／Provider／Claude API runtime＝未授權」是否涵蓋離線型別與 Fake。見 §1。
2. **[F] 兩份文字並陳（請客戶看全貌）**：
   - 客戶 2026-10-31 逐字存檔第 16 點：「未來順序：Architecture/Governance → Provider abstraction + fake provider → Claude shadow → … → production enablement；**production enablement 必須另行裁示**」；同檔抬頭寫「**性質：Architecture / Governance；不是 runtime 動工授權**」，「本輪禁止」列：不做大規模 runtime implementation、不改 UI／公式／Risk Cap／資料層、不新增外部資料來源／付費服務／SDK／shared service、不 commit secrets、不將 Claude Primary 直接切到 production（未點名 fake provider）。
   - `DEC-2026-10-31-03` 影響範圍欄：「OneBrain 僅為未來架構，沒有任何 runtime 工作被授權；任一後續階段（fake provider、shadow、整合、production）都須另行裁示」——此句為 DEC 整理文字，逐字存檔**沒有**同句。
   - **[I] 推論**：(b) 的字面張力可能比 DEC 摘要小（逐字檔只明寫 production enablement 須另行裁示），但「不是 runtime 動工授權」同樣是逐字檔的話；兩者孰重由客戶定。`DEC-2026-11-18-03` 自己已把 (b) 列為客戶才能解的題。
   - **同向證據**：`docs/v2/75` 第 18.2 節：「等本架構文件合併並完成 canonical index sync 後，下一個 OneBrain 工作只能是 OB-B Provider abstraction 的設計／fake provider batch；不得直接接正式 Claude API」（並加註「上位 blocker 先處理」，見 §1 末兩列）。
3. **[R] 最小 Gate＝客戶一次、用自己的話確認一句限縮文字（候選文字見 §2-D）**，涵蓋 (a)(b)(c)(d)；確認的形式須能被 repo 逐字存檔（沿 `-10-31-03` 先例），否則 (a) 的來源疑慮不消。
4. **[I] OB-B 離線切片不需要任何 D2 契約**（§4；這是設計主張：型別刻意不含 Digest 內容，尚無實作可驗）。施工申請草稿見 §3；**所有「待使用者核准」項目集中列於 §5。**

## 1. (b)(c) 與其餘待確認項到底是什麼（[F]；讀 `DEC-2026-11-18-03` 待確認欄、`DEC-2026-10-31-03` 與其逐字存檔、`DEC-2026-11-08-02`、BL-0557／HANDOFF）

| 項 | `DEC-2026-11-18-03` 原文意思 | 相關原文事實 | 本卡處理 |
|---|---|---|---|
| **(a)** | 客戶是否**本人**要求「平行作業完成 UI + OneBrain」，及該方向是否涵蓋 OB-B 離線切片 | DEC-18-03 的來源＝ChatGPT 派工單轉述〔待核〕；現又有一則 ChatGPT 轉述（本批方向來源），仍無逐字 | 併入 Q-OB1（形式問題：要有可存檔的客戶本人文字） |
| **(b)** | `DEC-2026-10-31-03` 寫「Provider abstraction + fake provider」階段須客戶另行裁示——**本筆的轉述來源是否足以構成該另行裁示** | 逐字存檔第 16 點：順序含 Provider abstraction + fake provider，**僅 production enablement 明寫須另行裁示**；`-10-31-03` 影響範圍欄較寬（執行組整理）。同日逐字存檔「本輪禁止」只禁大規模 runtime、改 UI／公式、新增 SDK／付費服務等，**未點名禁 fake provider** | Q-OB1（b） |
| **(c)** | `DEC-2026-11-08-02` 仍未授權欄含「Phase 7／Provider／Claude API runtime」——**離線 Fake Provider 與型別是否落在該句之外** | 該 DEC 為客戶經總管派工單轉達的**要點轉述**（非逐字）；「Provider」可讀作修飾 runtime（Provider runtime），也可讀作獨立項目 | Q-OB1（c） |
| (d) | 切片 (1)～(5) 的範圍與檔案位置（E1）是否同意 | E1＝`services/onebrain/` 為執行組讀法；本卡 §3 補一個依賴方向風險 | Q-OB2 |
| (e) | 程式 PR 完成後是否核准任何後續 OB 階段 | OB-C（Claude shadow）起依 75 第 15 節另行裁示 | **不問**：本卡明寫不授權 |
| (f) | Digest 決策包產出後的裁示方式 | 決策包已有（`docs/evidence/onebrain_digest_decision_pack_2026_11_18.md`）；其 Q 系列與 OB-B 獨立 | **不問**：與 OB-B 無關 |
| 另：67 第 5.7 節 Stop Gate 1 | 「Decision Digest 契約定義前，不寫 prompt 或 LLM glue」 | OB-B 不含 prompt／Digest；但「typed interface 的 request／response」是否算 LLM glue 的前置，文字未明說 | 併入 Q-OB1 (c′)，一句確認 |
| 另：BL-0527／BL-0528 | 決策包 Q2：是否為 OB-B 的 blocker | 75 第 16 節 OB-01 前置只寫「本檔」；BL-0527 掛 OB-02、BL-0528 掛 OB-09；75 第 18.2 節另寫「上位 blocker 先處理」 | 併入 Q-OB1 (c″)，一句確認「不是 OB-B 離線切片的 blocker」 |

## 2. 最小 Decision Gate（客戶需裁示；推薦為執行組讀法，可被推翻）

**Q-OB1（必要，一次問完 (a)(b)(c)(c′)(c″)）**：「是否明示開啟 OB-B 離線切片？」

| 方案 | 內容 | 優點 | 缺點 | 風險（[I]） |
|---|---|---|---|---|
| **A（[R]）** | 客戶以**自己的文字**一次確認 §2-D 候選句：離線型別＋Fake 屬 10-31 順序第二步、不屬 11-08-02 所禁、不受 BL-0527／0528 阻擋、不需等 D2；並同意該文字被逐字存進 `docs/evidence/decisions/`（沿 `-10-31-03` 先例） | 一次消除 (a)(b)(c) 與 Stop Gate 1 疑慮；不再依賴轉述；範圍可寫得很窄、可逆（僅新增檔、可整檔移除） | 需客戶表態一次 | 低至中：成立前提是文字夠窄且明寫「不得被任何頁面渲染、不得進 production 路徑」 |
| B | 接受 ChatGPT 轉述為 (a)(b)(c) 的確認，不另要客戶本人文字 | 最快 | DEC-18-03 自己已說轉述來源不足以構成 (b)；來源〔待核〕無法稽核，等於由專案 AI 單方解讀客戶 Gate | **高**（違反 DEC-18-03 自設條件；不建議） |
| C | 不確認；OB-B 等到 D2 完成與 Digest schema Gate 之後（決策包讀法 2） | 完全避開 Stop Gate 1 與 Fake 疑慮 | 與「不等待全部 D2」方向相反；OneBrain 線閒置 | 低；進度風險 |
| D | 只確認 (c)（11-08-02 不涵蓋離線型別）、(b) 另案 | 範圍最小 | 仍卡在 10-31 的 Gate，等於沒解 | 低但無進展 |

**[R] 推薦 A。理由**：(i) 逐字存檔顯示 (b) 的字面障礙比 DEC 摘要小，客戶確認成本低；(ii) A 是唯一同時消除「專案 AI 單方解讀客戶 DEC」與「OneBrain 線整段閒置」兩種壞結果的方案；(iii) 範圍窄到不碰 Digest／D2。**代價**：需客戶本人一次表態；OB-B 完成後仍無使用者可見成果；Fake 若被誤接到 UI 會變成「假的 AI 輸出」，故文字須寫死 §3 的不得項。

**Q-OB2（選填，可併入 Q-OB1）— (d) 放置位置**
| 方案 | 內容 | 優點 | 缺點 | 風險（[I]） |
|---|---|---|---|---|
| **A（[R]，沿 DEC-18-03 E1）** | `services/onebrain/`（L2），僅新增檔 | 純度守衛（`tests/test_services_purity_contract.py` 白名單，掃 `services/**.py`）自動涵蓋；`ui_v3` 層本就擋 `services` | **依賴方向隱憂（[I]，本卡新增）**：日後真實 provider transport 依 75／E1 屬 L0 `infra/`，若它要實作定義在 L2 的 interface／型別，會形成 L0→L2 上行 import，違反 `CLAUDE.md` §8.2 硬規則 3 | 低（本批）／中（OB-C 前須解決，可用 `typing.Protocol` 結構型別或改搬型別到 L0）；檔案全新增、未被引用，搬動成本小 |
| B | 型別＋Protocol 放 L0（`shared/` 或 `infra/` 子模組），Fake 放 L2 或測試輔助 | 依賴方向一次到位 | `shared/` 慣例是「純常數」；`infra/` 是 I/O 層，放純型別語意不貼；purity 白名單對 infra 採子模組粒度，需要另行放行 | 中（可能需動守衛白名單，超出「只新增檔」） |
| C | 頂層新目錄 `onebrain/` | 隔離最強 | 不屬 §8.2 任一層、不在純度守衛母體，易成未登錄軟例外（DEC-18-03 E1 已不建議） | 高 |
**[R] A，並要求 OB-C 之前另提「依賴方向」解法；若客戶／總管偏好一次到位則選 B，但本批就會多一項守衛白名單變動，須另核。**

**§2-D 候選確認文字（供客戶改寫；非客戶逐字、非已核准；僅為降低往返）**
> 「OB-B 限縮確認（候選）：(1) 明示開啟 OB-B 離線切片＝Provider-neutral 型別、離線 Fake Provider、結構化錯誤／不可用狀態、注入式測試；(2) 此切片視為 2026-10-31 `DEC-2026-10-31-03` 順序第二步『Provider abstraction + fake provider』的另行裁示（僅限此離線範圍）；(3) 此切片不屬 `DEC-2026-11-08-02` 所禁『Phase 7／Provider／Claude API runtime』，亦不屬 67 第 5.7 節 Stop Gate 1 所禁『prompt 或 LLM glue』；(4) BL-0527／BL-0528 不是此切片的 blocker；(5) 不需等 D2 全部完成；(6) 不含任何真實 provider、SDK、金鑰、環境變數讀取、prompt、Digest、UI、Claude shadow、Risk Cap、投資行動輸出；(7) Fake 輸出必須明標 FAKE，不得被任何頁面渲染、不得進入 production 路徑。」

## 3. 施工申請草稿（**候選；待 §5 各項核准後才可開程式 PR**；DEC-18-03 另要求「本 DEC 已落 main、獨立治理稽核 Must-Fix 清零」再開程式 PR——本卡不替它們作答）

**3-1 層級與放置**：L2，`services/onebrain/`（見 Q-OB2 A）。**僅新增檔，不改任何既有檔。**

**3-2 擬新增檔案白名單（共 7 檔；多於此即超範圍）**
| 檔 | 內容（候選設計；命名為建議） |
|---|---|
| `services/onebrain/__init__.py` | 僅 docstring，說明本套件為離線型別＋Fake、**不得被 production 路徑 import**；無執行期副作用 |
| `services/onebrain/provider_types.py` | `@dataclass(frozen=True)`／`Enum`：`ProviderRequest`（request_id、model〔僅識別字串〕、input_text〔不透明文字，本批不含 prompt 模板與 Digest〕、timeout_seconds／max_retries〔僅型別欄位，無重試實作〕）、`ProviderResponse`（request_id、provider_name、model、text、`is_fake`）、`ProviderErrorKind`（TIMEOUT／RATE_LIMIT／PROVIDER_UNAVAILABLE／DEGRADED，對應 75 第 4.1 節已列項）、`ProviderFailure`、`ProviderOutcome`（response 與 failure 恰一者非空，建構時檢查） |
| `services/onebrain/provider_interface.py` | `abc.ABC`（或 `typing.Protocol`，見 Q-OB2 的依賴方向）`AnalysisProvider`：`name`、`invoke(request) -> ProviderOutcome` |
| `services/onebrain/fake_provider.py` | `FakeProvider`（**類名含 Fake**）＋`FakeScenario`（MARKER／TIMEOUT／RATE_LIMIT／UNAVAILABLE／DEGRADED）；`name` 固定含 `FAKE`；成功回固定常數標記（含「FAKE」字樣，例：離線測試標記、非 AI 分析）；失敗情境回對應 `ProviderFailure`；**無隨機、無時鐘、無 I/O、無 logging 內容外洩** |
| `tests/test_onebrain_provider_types.py` | 型別不變式與**欄位集合釘死**（見 3-6） |
| `tests/test_onebrain_fake_provider.py` | Fake 行為、注入式呼叫、斷網測試 |
| `tests/test_onebrain_offline_guard.py` | import 白名單、禁用呼叫、孤立性（無外部 importer）守衛 |

**3-3 型別範圍（沿 DEC-18-03 E4，[F]）**：含 provider name、model（識別字串，無 routing 政策）、request、response、timeout／retry（僅型別欄位）、rate-limit error、provider unavailable、degradation／error classification。**不含**：token usage、cost、trace metadata（含 cache／trace schema）、structured-output capability、`confidence`、action、Risk Cap、System Action State、configuration policy（75 第 15 節 OB-B 列有，但 DEC-18-03 切片未含；**如要加須客戶另核**）。型別≠Decision Digest Schema，不得互相引用為核准依據。

**3-4 不得碰項（[F] 沿 DEC-18-03 E2 與不授權清單；本卡補列後三項為 [I]）**：`infra/llm.py`（現行 `_DEFAULT_CHAIN` 維持）、`services/ai_service.py`、`services/ai_prompts.py`、`EXCEPTIONS.md`、既有守衛（`test_services_purity_contract.py`、`test_doc_counters.py`、`tests/ui_v3/*`）、`ui_v3/**` 及所有 UI／`app.py`、`registry.py`／導覽、`shared/`、`repositories/`、`requirements.txt`、`.github/workflows`、`.pre-commit-config.yaml`、`tests/conftest.py`、舊線 AI（BL-0528）、`docs/DECISIONS.md`／`BACKLOG.md`／`HANDOFF.md`（索引同步由治理 owner 另批）；不新增 SDK、不安裝套件、不建 cache／trace／budget schema、不產出 Digest 生產者、不寫 prompt、不開 Shadow（OB-C）、不輸出機率／信心數字。

**3-5 離線／無網路／無 secrets 保證（候選機制；每條都要有「拿掉就轉紅」的守衛）**
1. **import 白名單（比 L2 通用白名單更窄）**：`services/onebrain/*.py` 只准 `__future__`、`abc`、`dataclasses`、`enum`、`typing` 與**絕對** `services.onebrain…` 自引（**不准相對 import**：`tests/test_services_purity_contract.py::_import_key` 對 `.` 開頭的 import 原樣保留、不在 `ALLOWED_IMPORTS` 內，會使 `test_services_imports_are_allowlisted` 轉紅；亦與 `DEC-2026-11-18-03` E1「用絕對 import」一致）；任何其他 import（含 `os`、`sys`、`logging`、`time`、`random`、`uuid`、`shared`、`infra`、`repositories`、`ui*`、網路套件）＝紅。AST 掃描含函式內巢狀 import。
2. **禁用呼叫**：AST 禁 `open`、`eval`、`exec`、`__import__`、`getattr(os, …)` 類形態、`environ`／`getenv` 的屬性存取。
3. **斷網測試**：Fake 測試期間以 `monkeypatch` 把 `socket.socket`、`socket.getaddrinfo` 換成會拋例外者，呼叫 Fake 仍須成功（證明不碰網路）。
4. **無 secrets**：1＋2 已使環境變數與檔案讀取不可達；另以 AST（非字面 grep）斷言套件內無字串常數形如金鑰樣式。負控字串**只在指令現編、不落文件**（`CLAUDE.md` §-2.A 第 8 款）。
5. **孤立性（Fake 不進 production 路徑）**：掃全 repo `*.py`，除 `services/onebrain/` 自身與 `tests/` 外，任何檔 import `services.onebrain` ＝紅（涵蓋 `app.py`、`ui*/`、`infra/`、`repositories/`、`mcp_server/`、`scripts/`）。

**3-6 測試與獨立 QA**
- **欄位集合釘死**：`ProviderRequest`／`ProviderResponse`／`ProviderFailure` 的欄位名集合 `==` 核准清單；出現 `confidence`、`action`、`risk_cap`、token／cost／trace 類欄位＝紅。
- **Fake 輸出斷言（沿 E3）**：固定標記含「FAKE」；不含 67 第 2 節行動詞的方向語意（續抱／觀察／降低曝險／減碼／替代比較）、不含機率或信心數字、不含 Risk Cap。〔[I] 「無法判定」同屬 67 第 2 節六詞，但 75 第 4.2 節與 `-10-31-03` 第 13 點要求全失敗時顯示「AI 分析暫不可用／無法判定」；斷言須明確區分「降級字樣」與「行動詞方向語意」，此細節待總管／QA 定。〕
- **注入式**：以一個接受 `AnalysisProvider` 的最小消費函式驗證可注入、錯誤分類可被處理；不得有預設 provider、工廠、config 選擇器。
- **突變驗證（`CLAUDE.md` v2 第一條 ‘拿掉修復必須轉紅燈’ 的沿用）**：QA 須現場證明：新增 `import requests`→import 守衛紅；新增 `confidence` 欄→欄位守衛紅；在 `ui/` 內 import `services.onebrain`→孤立性守衛紅；移除 Fake 標記的 FAKE 字樣→紅。
- **必跑既有守衛**：`tests/test_services_purity_contract.py`、`tests/test_doc_counters.py`（DEC-18-03 E1 指定，其稱「檔案計數類守衛」；**[F，單組讀 docstring／rglob 目標]** 該檔掃的是 `docs/` 下檔案，對新增 `services/` 檔影響應不大，E1 的描述不精確）；另須實跑確認 `tests/test_ssot_3a_333.py`（`ui/`＋`services/` 的 `rglob`）與 `tests/test_audit_20260805_evidence_notes.py`、`_tab1_summary.py`、`_tab1_ui.py`、`_tab1_wiring.py`（同樣 rglob `ui/`＋`services/`）不被新檔觸發。若被新檔觸發，**停下回報、不得改守衛**。另跑完整 fast lane 與 CI 四項；`pre-commit` 四個會處理新檔的 hook。
- **獨立 QA**：至少 1 組非作者（`DEC-2026-10-16-05`）；實作者不得自驗；本卡建議 QA 另審「依賴方向」與「FAKE 無法被誤接」兩點。**本機缺依賴時只能 `--noconftest` 跑新測試，完整守衛組合須由 CI 驗**（[I]，未實測）。

**3-7 Model／Effort 建議（[R]，可被推翻；依 `PROJECT_RULES.md` 第 5 節矩陣；本組**未評估** Change Gate 是否觸發，由總管／使用者依第 5.1 節決定）**
- 實作：**Sonnet 5.5／Medium**（規格已被本卡窄化、僅新增檔、無資料語意或投資語意決策；矩陣「規格清楚的跨少數模組」列）。
- 獨立 QA：**Opus 5.5／Medium**（要設計守衛逃逸與突變驗證、屬 AI 行為邊界稽核；若總管認為 Sonnet 足夠可不升）。
- 不建議 High：本批不含投資核心語意／Risk Cap／PIT。

## 4. 與 D2 的相依性（[F]／[I]）
- **不需要 D2（也不需要 Digest schema、Rule ID 格式、Risk Cap、N1–N5）的部分**：§3 全部。理由：型別不含 Digest 內容；75 第 16 節 OB-01 前置只寫「本檔」；DEC-18-03 切片 (1)～(4) 不含 Digest。
- **需要 D2／Digest 層 Gate 才能碰的（本卡**不含**）**：任何帶 Digest 欄位的 `request` 內容（OB-02）、fingerprint／cache（OB-03）、trace（OB-04）、prompt／policy（OB-06）、真實 provider、Claude shadow（OB-07）、🤖 頁面（Phase 7）。
- **[I]** `ProviderRequest.input_text` 為不透明文字：這是本卡刻意的最小設計，避免「型別預先決定了 Digest 形狀」。若客戶／總管認為連這個欄位也隱含 Digest 假設，可改成空殼 `payload: str`；屬設計細節，由 QA 檢視。

## 5. 仍待使用者（客戶）核准／確認的事項（候選≠核准）
1. **Q-OB1**：(a)(b)(c)(c′)(c″)——客戶本人以可存檔文字確認 §2-D（或其改寫版）。**未獲確認前不得開程式 PR**（`DEC-2026-11-18-03` 自設條件）。
2. **Q-OB2**：放置位置與依賴方向（(d)）。
3. **施工申請本身**：§3 的 7 檔白名單、型別欄位清單、不得項、守衛清單——需總管／使用者核准後才可開程式 PR；且依 DEC-18-03 須待其落 main 並完成獨立治理稽核。
4. **Model／Effort**（§3-7）：由總管／使用者依 `PROJECT_RULES.md` 第 5 節確認。
5. **不在本卡、維持不授權**：OB-C 起各階段（(e)）；真實 provider／SDK／金鑰／環境變數；Claude API runtime；Digest schema／生產者；prompt／LLM glue；Risk Cap、System Action State、投資行動；改 `infra/llm.py`；BL-0528 G1～G6；BL-0527 N1～N5；Phase 7／🤖 頁面／registry；configuration policy；BL-0545、BL-0551。

## 6. 未查證項
1. **單組作者**；全稱句（「僅此 7 檔」「無外部 importer」）是設計主張，**無現存程式可驗**；孤立性目前是否已成立（`services.onebrain` 尚不存在）屬 trivial。
2. 已讀：`DEC-2026-11-18-03` 全文、`DEC-2026-10-31-03` 與其逐字存檔、`DEC-2026-11-08-02`（要點轉述）、75 第 4／15／17／18 節、67 第 5.7 節、`tests/test_services_purity_contract.py` 的白名單與掃描範圍、`tests/ui_v3/ui_v3_guard_lib.py::LAYER_DEPS`、`PROJECT_RULES.md` 第 4／5 節；**未讀** 75 第 9／10 節全文、`test_doc_counters.py` 全文（只看到它掃 `docs/`，應不受 `services/` 新檔影響，單組）。**已知會 rglob `services/*.py` 的測試**：`test_ssot_3a_333.py`、四支 `test_audit_20260805_*`（evidence_notes／tab1_summary／tab1_ui／tab1_wiring）——**本組只看到 rglob 呼叫，未讀其斷言，是否被新檔影響未驗，須實跑**；是否另有其他測試掃 `services/` 未窮舉。
3. **未執行任何程式或測試**；§3-5 各機制為設計，尚無實作、無突變驗證。
4. 依賴方向隱憂（Q-OB2）是推論：未讀 75 第 9 節對實體目錄的完整說法，也未驗證 `typing.Protocol` 能否在不違反 purity 守衛下讓 L0 免 import L2。
5. 「逐字存檔第 16 點僅 production enablement 須另行裁示」是本組讀逐字存檔所得；`-10-31-03` 影響範圍欄的寬寫法是否另有客戶依據，本組未查。
6. Model／Effort 建議未評估 Change Gate；矩陣讀自 `PROJECT_RULES.md` 第 5 節單一段落，未通讀第 5.1 節全文。
7. 方案風險等級為作者推論。
