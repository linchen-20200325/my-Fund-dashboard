# OneBrain Decision Gate 路線（D1～D10）與三風險最小影響查核（2026-11-08）

> **性質**：docs-only 研究整理。基準 `origin/main` `7ac7c935`。**全文所有「建議／一鍵問法」皆為提案，非客戶裁示、非施工授權**（`CLAUDE.md` §-1：登記不構成動工授權）。
> **來源**：承接 `docs/evidence/onebrain_evidence_coverage_gap_audit_2026_11_08.md`（下稱 AUD）§8 的 D1～D10；底稿為兩份單組唯讀產出，經總管抽樣核對，本文再由文件組對承重宣稱重跑 `git grep`／`git show`（見 §6）。
> **揭露（`CLAUDE.md` §-2 規則 6）**：單組整理，**未經第二組獨立驗證**；標「NOT VERIFIED」者為未查證或原文即如此；全稱句（「0 caller」「不可達」）為 `git grep` 結果，動態 import 未驗。
> **不做的事**：不改公式、不刪功能、不啟動 Phase 7／Digest／Provider、不改 code／workflow／frozen／`CLAUDE.md`、不改任何 BL 狀態。

---

## 0. 結論先行

| # | 結論 | 類別 |
|---|---|---|
| 1 | Decision Gate 共 10 題，**無一題是施工授權**；推薦路線 C（先定資料規則、暫不寫 Digest 程式）延續 AUD §7 | RECOMMENDATION |
| 2 | 建議問客戶的順序：**批次 0**（D8 有時效最先，D1、D10、D3(a)）→ 批次 1（D3(b)+D7、D5、D4-3）→ 批次 2（D2）→ 批次 3（D6）；D4 的 Risk Cap／減碼 trigger 可延後且不阻擋其他題 | RECOMMENDATION |
| 3 | **R1**（`nav_metrics` 遇 NaN 靜默）：純技術修補；**僅 Preview（`ui_v2`）與測試可達，`app.py` 不可達**；正式組表路徑已在上游擋掉非有限值。本批**未授權施工** | FACT＋INFERENCE |
| 4 | **R2**（未設定級別→「持有」）：字面與 `PROJECT_RULES.md` 13.1／`docs/v2/67` §5.4 衝突，但該線 **`app.py` 不可達**（legacy／dead code 候選，已登記 BL-0428／BL-0445）；屬**金融語意 Decision Gate**（退役或改為「無法判定」） | FACT＋INFERENCE |
| 5 | **R3**（過期 NAV 計入市值）：`ui_v2` 已有 10 日降級、`ui_v3` 市值基準 blocked；**Old UI T7「組合當前市值」未見任何 NAV 日期檢查，且 `app.py` 可達**；屬**金融語意／門檻 Decision Gate** | FACT＋INFERENCE |
| 6 | 「純文件同步」有一項可自行處理：`DEC-2026-11-05-04` 實作狀態過期句（已於本 PR 更正，不需客戶決定；見 §5） | FACT |

---

## 1. Decision Gate 路線 D1～D10（提案）

### 1.1 一眼總表

| Gate | 原名（AUD §8） | 類別 | 前置 | 批次 | 可平行／依賴 | 裁示後施工階段是否觸發 Model／Effort Gate |
|---|---|---|---|---|---|---|
| D1 | 方案方向（A／B／C）與是否啟動 Digest 施工 | 產品方向 | 無 | 0 | 可平行 | 視裁示；見 §4 |
| D2 | 各域 Required／Optional 與 Digest schema 版本／fingerprint | 資料契約＋Schema | D1、D3(a)、D4-3、D5（軟） | 2 | 依賴 | 是（資料契約） |
| D3(a) | 狀態字彙**純對照表** | 資料契約文件 | 無 | 0 | 可平行 | 否（文件） |
| D3(b) | `stale_after`／conflict 判定／是否新增 `stale` 狀態 | 門檻＋金融語意 | 與 D7 合併 | 1 | 與 D7 合併 | 是（門檻、PIT） |
| D4-1 | Risk Cap 正式定義 | 金融語意 | 無（擋六行動詞中五詞） | 3（可延） | 獨立 | 是（投資核心語意） |
| D4-2 | 「減碼」deterministic trigger | 金融語意 | D4-1 | 3（可延） | 依賴 D4-1 | 是 |
| D4-3 | Rule ID／`rule_version`／門檻引用格式 | Schema（格式，不涉投資語意） | 無 | 1 | 可平行 | 視是否改契約 |
| D5 | 反證（counter-evidence）定義 | 金融語意 | 無（生產者另需 D4） | 1 | 可平行 | 是（若設計生產者） |
| D6 | 💼 G-1／G-3／G-4／G-5＋11 項 open gate | 金融語意／資料契約／UI 字樣 | D7、D8、D10；G-5 靠 D3(a)；G-3 靠 BL-0534 | 3 | 依賴多題 | 是 |
| D7 | NAV 10 日規則跨頁語意 (a)～(e) | 門檻＋金融語意 | 與 D3(b) 合併 | 1 | 與 D3(b) 合併 | 是 |
| D8 | FX 閘門開放證據軌＋冬令探測 | 資料契約（驗證證據） | 無；**有時效** | 0（最先） | 可平行 | 探測＝否；開閘＝是（PIT／FX cutoff） |
| D9 | BL-0545 合法輸入與分母口徑 | 治理＋資料契約 | 輸入端獨立；准入判定靠 D3(b) | 外部驅動 | 獨立 | 取輸入＝否；定義准入＝是 |
| D10 | 重確認 `DEC-2026-11-05-02／-04` 授權鏈＋同步 `-04` 實作狀態 | 治理 | 無 | 0 | 可平行 | 同步＝否；確認＝否 |

**依賴圖（建議，非裁示；單組自 AUD §3.2 與各 BL 依賴欄推得，NOT VERIFIED）**

```
批次0（可平行）: D8(最先)  D1  D10  D3(a)   [D9 外部驅動]
批次1（可平行）: D3(b)+D7   D5   D4-3
批次2:           D2   （吃 D1 結論、D3(a) 字彙、D4-3、D5）
批次3:           D6 [G-1 → G-4 → G-3 → G-5]（吃 D7、D8、D10、D3(a)；G-3 另吃 BL-0534）
延後:            D4-1 → D4-2（Risk Cap／trigger，不阻擋 C 路線）
```

軟耦合的建議拆法：D2↔D4-1 以「Required 但未定義＝Missing→無法判定」處理（`docs/v2/67` §5.4／§8.6），D2 不等 D4-1；D2↔D4-3 先裁 D4-3；D3(b)↔D7 合併為一題；D6 內 G-1 先於 G-4；D2 對 💼 域標「待 D6」不阻擋其他域。

### 1.2 各 Gate 內容與一鍵問法

（縮寫：67／75／79＝`docs/v2/` 同號檔；PR＝`PROJECT_RULES.md`；BL＝`docs/BACKLOG.md`；DEC＝`docs/DECISIONS.md`。**一鍵問法皆為提案，非客戶裁示、非施工授權；不含任何門檻數值。**）

**D1｜A／B／C 路線**

| 方案 | 內容 | 缺點 |
|---|---|---|
| A 最小 Evidence Adapter | 唯讀轉接層把各域現有輸出包成統一外型 | 先有外型後有契約，欄位集合事實上成為未核准 schema |
| B 先完善各域 Complete Evidence 生產者 | 把 💼 `allocation_evidence` 模式擴到其他域 | 工作量最大、每域卡未裁項 |
| C 等契約收斂再組 Digest | 先走 D2～D10，不新增程式 | 無可跑產出，進度取決於客戶裁示 |

推薦 C（AUD §7 稱研究建議、非施工授權）；`docs/HANDOFF.md` 唯一 NEXT 仍是 BL-0545 合法輸入 Gate。
**一鍵問法**：「Digest（AI 的完整決策輸入）要現在動工，還是先把資料規則定清楚？**建議選 C：先定規則、暫不寫程式**。原因：目前九類資料中八類還沒有『必備／選備』清單，也沒有新鮮度與衝突的判定標準；現在先做外殼，等於替您預設答案，之後要拆掉重做。代價是短期看不到新畫面。請回覆 A／B／C。」

**D2｜Required／Optional／Excluded（僅整理「已核准」與「差額」，不創造新清單）**

已核准的跨域通則（67 §8.6，`DEC-2026-11-02-07`）：Required（例）＝identity、value、as_of、health、rule result、System Action State，缺時輸出「無法判定」並列缺什麼；Optional（例）＝歷史序列、補充 provenance；Excluded＝widget 展開狀態、scroll、container 順序、cosmetic color、session-only display metadata；confidence 不納入（67 §5.3）。「例」字表示非封閉清單；Missing 不得變 0／neutral／safe／HOLD（67 §5.4；PR 13.1）。

| 資料域 | 已核准項 | 差額＝待 Gate |
|---|---|---|
| 市場與總體 | 無逐鍵已核准項 | 逐鍵 R／O；regime 聚合規則另走 Formula Gate；BL-0501 EPS／PE |
| 基金基本資料／NAV／績效 | 通則 | 逐項 R／O；報酬口徑（BL-0524）；NAV 新鮮度（見 D7） |
| 持倉／資產配置 | Missing≠0、covered-only≠完整 100%（引 AUD §3.2，本次未逐條重驗）；缺 FX 不顯示誤導性 100%（`DEC-2026-11-04-02`） | G-1 分母、G-3～G-5、11 項 open gate（見 D6） |
| 配息／事件 | Excluded：delivery metadata、Notification Preference；`is_actual`≠`confirmed` | 事件欄位納入 R 或 O（67 §8.11 第 2 點）；`pay_date` amendment（BL-0534） |
| FX／利率／景氣 | 通則 | 逐鍵 R／O；FX 閘門（D8） |
| 基金身份與跨源對應 | shadow 階段規則（`DEC-2026-10-28-05`，僅確認存在） | canonical key 採用時點（BL-0527 第 5 項） |
| 資料健康／Freshness | 三軸分開、不得出現 passed／safe／eligible 類結論詞（`DEC-2026-11-06-02`） | 字彙（D3a）、門檻（D3b）、准入（D9） |
| Rules／Risk Cap／Action State | 六行動詞語意與通則（67 §2、§8.2）；未定義前恆為「無法判定」 | Rule ID（D4-3）；Risk Cap、trigger（D4-1／2） |
| Supporting／Counter-evidence | 「最大反證」輸出方向（67 §8.7、§8.9） | 反證定義（D5） |

Digest schema 版本／fingerprint：75 §6 明寫不在本輪拍死。
**一鍵問法**：「請問 AI 的決策輸入要不要採『先逐類定清單再建資料』？**建議採：由我們依已核准通則，先為每一類資料列出『必備／選備／不納入』草案，您逐類核可，缺的資料一律標示『無法判定』而不是補值**。原因：這樣不會把沒核准的欄位當成規格；代價是需要您逐類過一次。請回覆：同意，或指定先做哪幾類。」

**D3｜狀態字彙與 stale／conflict 門檻（拆 (a)／(b)）**

(a) 純對照表：只對齊既有字彙名稱（67 §5.3 的四態、Cell status `not_ready`／`fetch_failed`／`inconsistent`、設定頁四類、`market_view` `reason_code`、`NAV_STATES`／`SRC_*`／`VAL_*`、`threshold_pending`、「⬜ 無法判定」「未定義」），**不新增狀態、不改任何判定**；凡無法一對一者（例：NAV 過期併入「資料未備」，無獨立 stale）一律列入 (b)，不替客戶決定。AUD R6 稱至少 5 套並存，「恰好 5 套」未逐一點算（NOT VERIFIED）。
(b) 需裁示：`stale_after` 逐來源值（67 §8.5「仍待」；79 §7.2）；`expected_lag`／`frequency`；conflict 判定（容差、何謂同 as-of 不一致）；是否新增獨立 `stale` 狀態（新字樣另受 `APPROVED_WORDING` Gate，`DEC-2026-11-03-07`）；PIT 取哪一欄（`CLAUDE.md` §2.3）；月度 `[STALE: XXd]` 標籤沿用與否（79 §7.2）；NAV 10 日併入 D7。BL-0369（`◷` 徽章色調）是另一件事，不併入。
**一鍵問法**：(a)「請問可否由我們把各處不同說法的資料狀態做一張對照表給您看，**不新增任何狀態、不改判定**？建議同意。原因：目前至少五套說法並存，不對齊就無法統一顯示。」(b)「過期與不一致的判斷標準要怎麼定？**建議按來源逐一定（日報、月報、基金淨值各自依其發布週期論證），而非一個全站數字；不一致時不顯示任何一方的值，並保留被捨棄的來源與差異**。原因：各來源更新週期差很多，統一數字會誤判。我們會先附各來源實際發布延遲的事實，再請您定天數。」

**D4｜Risk Cap、減碼 trigger、Rule ID（拆三項）**

| 子項 | 類別 | 依賴 | 出處 |
|---|---|---|---|
| D4-1 Risk Cap 正式定義（作用層級、輸入、與配置風險位階及持股行動關係、Missing 時行為；本列不提數值） | 金融語意 | 無，但擋六行動詞中五詞 | BL-0495；`DEC-2026-10-27-14`、`-22` |
| D4-2 「減碼」deterministic trigger（客戶原話：trigger 未定前 AI 不得自行決定減碼） | 金融語意 | D4-1 | BL-0496；67 §2.4 |
| D4-3 Rule ID 編碼、`rule_version`、門檻引用格式 | Schema（格式） | 無 | 67 §5.6-4、§8.7；79 UI-10；BL-0527 第 4 項 |

現況：Rules／Risk Cap 未定義前 System Action State 恆為「無法判定」，不阻擋 C 路線其他 Gate。
**一鍵問法**：D4-3「規則編號與版本的寫法請先定下來好嗎？**建議先定，這不涉及投資判斷，只是命名格式**。原因：之後每一條規則、每一句 AI 結論要回溯到規則都靠它。」D4-1／2「風險上限與『何時該減碼』**建議這一輪不定**，系統持續顯示『無法判定』並列出缺什麼。原因：這兩項是投資判斷，不應由系統預設，且不影響先把資料規則定完。」

**D5｜反證定義**
現況：`counter_evidence`／`supporting_evidence` 全 repo 0 檔（AUD V4）；`EvidenceSupport` 是證據充足性，不是反證分類。已核准方向：67 §8.7、§8.9「最大反證（Falsification Condition）」。待裁：投資語意定義（BL-0542 G-1 新待決題 (b)）。
**一鍵問法**：「AI 說『最大反證』時，應指的是什麼？**建議定義為：『若出現某個可客觀檢查的事實，就會推翻本次判讀』，且該事實必須來自已記錄的資料，不能是 AI 的看法或市場傳聞**。原因：與已核准的方向一致，且可被檢查。請回覆同意或調整。」

**D6｜💼 G-1／G-3／G-4／G-5＋11 項 open gate**

| 子項 | 內容 | 類別 | 依賴 |
|---|---|---|---|
| G-1 | 配置、偏離、市值、β 分類、淨值過期門檻、`is_no_active` 的 PORT 與**分母公式**（UI 方案 A 已核准，PORT／分母承接未裁） | 金融語意 | D7、D8、D10 |
| G-3 | 配息推估引擎如何進 `ui_v3`（基準日 vs 除息日） | 資料契約／金融語意 | BL-0534；`DIV_DATE_IS_EX_DATE_VERIFIED=False` |
| G-4 | 摘要四格口徑（UI 順序已核准） | 金融語意 | G-1 |
| G-5 | 狀態詞對映與 `no_holding`／`partial`／`normal` 字樣 | UI 字樣＋對照 | D3(a)；`APPROVED_WORDING` |
| 11 項 open gate | `_CHART_AFFECTING_GATES` 8 碼＋註解另列 3 碼；本質是「未裁示判斷」登記 | 混合（逐碼分流） | 逐碼依所屬 Gate |

G-2 已於 2026-11-05 授權（`DEC-2026-11-05-02`），不在本 Gate；該 DEC 明文不授權 G-3～G-5、NAV 組裝 PORT、NAV 10 日、FX 閘門、正式 UI 接線、OneBrain。
**一鍵問法**：「我的資產頁還差四個決定（資產分母怎麼算、配息日期怎麼定、摘要四格怎麼算、狀態用語怎麼寫）。**建議按 G-1 → G-4 → G-3 → G-5 的順序逐題問，且先不接上線，只先寫資料契約與測試樣本（B0 切片）**。原因：四題互相牽動，一次問會答不準。每題我會附推薦與代價。」

**D7｜NAV 10 日規則跨頁語意**
事實：常數 10 天，唯一字面值 `ui_v2/thresholds.py::NAV_NOT_READY_DAYS`；三頁皆嚴格 `>`；NAV 日期晚於今天時 hld／exp 拒絕，alo 的 `assemble_nav` 無此防線；無專屬 DEC id（`DEC-2026-11-05-03`：不授權重新定義或搬遷）。待裁五項（答案未選）：(a) 「今天」是否台灣日期；(b) 跨頁適用範圍；(c) 未來日期 NAV 語意；(d) `>` 或 `>=`；(e) 若搬遷的中立擁有者。即 D3(b) 中 NAV 的 `stale_after`，合併處理。
**一鍵問法**：「基金淨值『超過幾天算過期』目前只是程式裡的既有做法。**建議把它升格為全站統一規則，但要您先確認五個細節：以台灣日期計、三頁都適用、未來日期的淨值視為異常、恰好 10 天算過期或不算、規則集中放在哪**。原因：目前三頁處理不一致，不統一，資產頁與 AI 會得到不同結論。若您想改天數，請直接說。」（(d) 只列選項，推薦待補 PIT 影響分析，NOT VERIFIED。）

**D8｜FX 閘門開放證據軌與冬令探測（最先問）**
現況：`FX_OBS_DATE_RULE_VERIFIED=False`（`services/v2_tables/market_indicator.py`，AUD V10）→ 非 TWD 基金市值 `fx_absent`。時效：冬令錯位期重跑約 2026-11-02～11-24 有效，錯過等明年 3 月；結果須經獨立稽核才開閘（BL-0217）。repo 內有無重跑結果 NOT VERIFIED。另需 EUR／JPY／CNY 各自驗證。
**一鍵問法**：「匯率『哪一天的收盤價算當天』的規則，需要在冬令時段（到約 11 月 24 日）用真實資料再測一次，錯過要等明年三月。**建議現在授權重跑探測並由獨立複核者看結果，先不開閘；結果出來再問您是否開放**。原因：有期限，且重跑只取證據、不改任何顯示或公式。」

**D9｜BL-0545 合法輸入與分母口徑**
現況：Phase 1 唯讀探針已合併（#1168，`DEC-2026-11-07-03`）；live 模式 NOT IMPLEMENTED；真實覆蓋率 NOT VERIFIED；使用者暫不提供輸入。待裁：合法輸入（A 本人合法登入 session／B 自願匿名基金代碼清單）、分母口徑（`resolve_full_keys` vs DG2 canonical）。不得虛構覆蓋率、請求憑證或自行實作 live。
**一鍵問法**：「要量測您實際持倉的資料覆蓋率，需要您擇一提供：A 您自己的登入，或 B 一份匿名基金代碼清單。**建議 B（只要代碼，不涉帳號）；分母建議沿用現行正式分組，新的身份分組只作對照**。原因：B 不碰憑證；分母沿用現行才能和線上畫面對得上。目前您選擇暫不提供，所以此項維持『未驗證』，不影響其他 Gate。」

**D10｜授權鏈重確認與 `-04` 實作狀態同步**
兩半：(i) 同步實作狀態＝純文件事實更正（已於本 PR 處理，見 §5）；(ii) 重新確認 `DEC-2026-11-05-02` 授權鏈（僅要點轉述、無逐字 evidence、「不補造」）＝需客戶表態。
**一鍵問法**：「資產頁『完整證據』元件開工當時的授權只留下摘要紀錄，沒有您的原話。**建議兩步：我們先把文件裡已過期的『實作狀態』更正（不需您決定，已做）；另請您用一句話確認當時三項授權（配置核心下沉、完整證據生產者、預覽載入端）確實是您同意的**。原因：這個元件已被後續工作引用，授權鏈若有缺口，之後改動無法回頭追溯。」

---

## 2. 三風險最小影響查核

> 基準 `origin/main` `7ac7c935`。FACT＝本次 `git grep`／`git show`／實跑可重現；INFERENCE＝由 FACT 推得。

| 風險 | 一句結論 | 可達性 | 現有降級 | 影響等級 | 裁示類型 |
|---|---|---|---|---|---|
| R1 `nav_metrics` 遇 NaN 靜默 | 函式本身對 NaN 靜默；正式組表路徑上游已擋非有限值 | **僅 Preview（`ui_v2`）與測試；`app.py` 不可達** | 上游 `nav_dividend` `math.isfinite`＋`contract` 拒非有限 | 低（防線缺口，靠上游擋） | **純技術修補**（不改公式、不涉門檻）；**本批未授權施工** |
| R2 未設定級別→「持有」 | 與 13.1／67 §5.4 字面衝突；該線不可達 | **`app.py` 不可達**（僅測試可達） | 角色欄「⬜ 未設定」＋底註揭露 | 不可達 legacy；若重新掛載才流入 | **金融語意 Decision Gate**（BL-0428／BL-0445 承接） |
| R3 過期 NAV 計入市值 | 新路徑已降級；**Old UI T7 未見日期檢查** | Old UI＝**`app.py` 可達**；`ui_v2`／`ui_v3`＝Preview | `ui_v2` >10 日不納入；`ui_v3` 市值基準 blocked | Old UI 可能流入正式路徑；其餘 Preview | **金融語意／門檻 Decision Gate** |

### 2.1 R1｜`nav_metrics` 遇 NaN 靜默

- **FACT（實跑，乾淨 `git archive` 副本）**：`drawdown_pct([1,nan,2])=0.0`、`drawdown_pct([1,2,nan])=0.0`、`return_pct([1,nan,2])=100.0`、`return_pct([1,2,nan])=nan`（非 `None`）、`vol_pct([1,nan,2,3])=nan`。函式內無 `isfinite` 檢查（`services/v2_domain/nav_metrics.py`）。
- **入口與可達性（FACT）**：`services/v2_domain/nav_metrics.py` 僅經 `ui_v2/v2_domain_shim.py` 再匯出 → `ui_v2/hld/logic.py` re-export（`return_pct`／`drawdown_pct`／`vol_pct`）→ **唯一計算呼叫點**同檔 `_build_page_model` 內 `return_pct(navs)`／`vol_pct(navs)`／`drawdown_pct(navs)`。`ui_v3` 無 caller；Old UI（`ui/`、`app.py`）0 caller。測試 `tests/test_v2_domain_port.py`、`tests/ui_v2/test_hld_logic.py` 皆無 NaN 案例。`app.py` 無 `ui_v2`／`ui_v3` import；僅能經 `ui_v2/app_preview.py`、`ui_v3/app_preview.py` 以 `streamlit run` 啟動（Preview）。
- **現有降級（FACT）**：`services/v2_tables/nav_dividend.py` 逐值 `float()`＋`math.isfinite`，非有限計入「非有限數值」skipped 且該日不寫；`services/v2_tables/contract.py` 對「浮點」欄拒非有限（`nav_row_problems`）。→ 經 hld source 的正式組表＝已被擋（INFERENCE）。
- **影響等級**：僅 Preview／測試；函式契約層面「靜默」屬防線缺口。
- **裁示類型**：純技術修補（函式內對 NaN 回 `None` 或 fail loud）；`return_pct` 末值 NaN 回 `nan` 與「算不出來回 `None`」不一致，屬契約對齊，不涉公式與門檻。**純技術、無金融語意裁示需求，但本批未授權施工**；若日後施工，屬 Preview 範圍。
- **未驗**：Preview 注入式資料（`docs/evidence/*/launch_injected_data.py`）不經 `nav_dividend`；`hld/live.py` 之後是否改寫 nav 值未逐行驗；`return_pct` 回 `nan` 後 UI 格式化行為未驗；未跑 hld 全流程；未查 `cache/nav` 預存序列是否經其他路徑進表。

### 2.2 R2｜未設定級別→「持有」

- **FACT（可達性）**：`services/decision_matrix.py` 唯一 production import 為 `services/realtime_signal.py`（`compute_realtime_dashboard`）← `ui/tab1_macro.py`（`_render_realtime_decision_dashboard`，行 1613 定義、2711 呼叫；1626 import）← `render_macro_tab`（行 1787）。`app.py` 行 156 import、行 636 呼叫的是 `ui.views.page_01_macro.render_market_overview`，**不是** `render_macro_tab`；`git grep "render_macro_tab("` 於非測試檔僅命中 `ui/tab1_macro.py` 自身定義與註解。該頁檔頭明言決策矩陣「搬去 ②、本頁不畫」。`mcp_server`／`scripts`／`ui_v2`／`ui_v3` 0 caller。
- **行為（底稿，本次未重跑）**：tier 非 core／satellite 時回 `ACTION_HOLD`（「持有」）；未知 verdict→「預設持有」；`summarize_actions([])` 的 `core_hold_pct=0.0`。若該頁被掛載：角色欄「⬜ 未設定」、建議欄「持有」、底註寫「配置級別未設定時，系統維持持有」——以「持有」呈現而非「無法判定」。
- **條文逐字**：PR 13.1 禁止「不得把 Missing 轉成 0／中性／HOLD／安全／未觸發」；67 §5.4(1)「不得 Missing → 0；Missing → neutral；not evaluated → safe；unavailable → HOLD（客戶原話）」；67 §8.3「資料未備時不得出現續抱」；`DEC-2026-10-24-09`「Missing／Unknown 不得被另一個單軸訊號繞過後重新產生行動」。
- **既有登記**：`decision_matrix` 註解稱「客戶 2026-10-12 裁示：未設定 fail-closed HOLD」（`DECISIONS.md` 未找到該逐字條目，**未驗**）；`DEC-2026-10-23-08` 載明決策矩陣「σ 無法判定時沿用預設動作」本批不改、交 BL-0428；BL-0428（待客戶裁示）、BL-0278、BL-0329、BL-0445（dead code retirement gate 候選）。`DEC-2026-10-24-12`（DG-6）僅擴及 `switch_advisor`／`check_replacement_recommendation`，決策矩陣屬「其餘平行引擎未核准」。
- **判定**：字面衝突＋現況不可達；非「語意不同」。影響等級＝不可達的 legacy 程式碼。**裁示類型＝金融語意 Decision Gate**（退役，或改為「無法判定」）；BL-0428／BL-0445 已承接。
- **未驗**：動態 import／session 路徑；2026-10-12 裁示原文；BL-0278「無 production 呼叫」僅 grep 複核一致。

### 2.3 R3｜過期 NAV 計入市值

- **FACT（共用層）**：`services/v2_domain/holdings.py` 的 `latest_nav_row` 僅取 max(`nav_date`)，不看多舊；`basis_value_with_reason` 有 nav 列即 units×nav（×匯率），無 nav 列時才查 `stale_provider`（在過期名單→`MissingReason(nav_stale)`，市值 `None`）。
- **ui_v2 路徑（FACT）**：`ui_v2/alo/live.py` `NAV_MAX_AGE_DAYS = thresholds.NAV_NOT_READY_DAYS`（10）；`assemble_nav` 以 `(today - day).days > max_age_days` 判 `too_old`，過期者不交進 `nav`，`dataset["nav_not_ready"]` 帶最後淨值日 → 過期被擋、非計入。≤10 日者計入，無額外標示（`hld` 黃燈處理未逐項驗）。
- **ui_v3 路徑（FACT）**：`ui_v3/adapters/assets_source.py` `evaluate()` 市值基準 → `STATUS_BLOCKED`，不呼叫生產者；其餘分支傳 `nav_not_ready=None`、`nav_provenance=None`，故即使日後解除 blocked，`stale_provider` 無名單＝不會過濾舊 nav（INFERENCE）；`allocation_evidence` 的 gate `stale_nav_degradation_unjudged` 僅在「有 `nav_stale` 原因」時加入，舊 nav 仍被計入時不會觸發（底稿讀碼，行 1174 附近）。
- **Old UI（`app.py` 可達；FACT＋未驗）**：`ui/tab3_t7_ledger.py` 的 `_latest_nav_fx_t7` 取 `_nav_now`（`from fund_fetcher import get_latest_nav`），無則 fallback 序列最後值；`get_latest_nav`（`repositories/fund/fx_and_main.py`）前 50 行未見日期檢查；「組合當前市值 (TWD)」以 `st.metric` 直接顯示；該檔 grep `stale`／`nav_date`／`過期` 未見 NAV 老舊揭露（該檔 3000+ 行未逐行讀完）。→ **可能顯示未標過期的市值**（INFERENCE）。
- **影響等級**：Old UI＝可能流入正式路徑；`ui_v2`＝Preview（已有 10 日降級）；`ui_v3`＝Preview 且市值未啟用。
- **裁示類型**：金融語意／門檻 Gate（過期天數門檻、是否標示、降級樣式；`ui_v2` 的 10 日是既有客戶裁示 2026-10-13，Old UI 是否套用須裁示）；與 D7、D6 G-1 同源。
- **未驗**：Old UI `_nav_now` 資料來源是否本身已排除過期；`hld` 市值欄位是否另有顯示；`assets_source` 其他分支；2026-10-13 裁示原文本次未重讀。

---

## 3. 建議問客戶順序（提案）

1. **D8**（有時效，約 11 月 24 日前）→ 2. D1、D10(ii)、D3(a) → 3. D3(b)+D7（含 R3 的 Old UI 套用問題）、D5、D4-3 → 4. D2 → 5. D6 → 6. R2 的退役／改為「無法判定」可併入 BL-0428／BL-0445 既有登記；D4-1／D4-2 延後。D9 依客戶何時提供輸入。R1 若客戶同意可另列技術修補，與上述 Gate 無依賴。

## 4. Model／Effort 條件式提示

依據：`PROJECT_RULES.md` 第 5 節 **5.1 第 10 點**（`DEC-2026-10-25-03`）：「**每個完整工作階段開始前重新判斷 Model 與 Minimum Sufficient Effort**」；「**Model 或 Effort 任一項與目前不同 → 不論升級或降級，都在開始該完整工作階段前停手**」；5.1 **第 11 點** Hard-Stop（`DEC-2026-11-02-04`）：下一階段建議切換 Model、模式或 Effort（任一項）→ 先回報 Change Gate，然後「**立即停下**」，等客戶回覆「已切換／可以開始」。5.1 第 9 點（`DEC-2026-10-23-04`）：不因形式（如投資專案）預設升 High。

- **當下 Model／Effort 設定 NOT VERIFIED**，故下列一律為條件式：**若與當下設定不同則觸發 Change Gate**；若相同則靜默繼續。
- 「整理 Gate 問法」本身屬文件階段（Haiku～Sonnet 即可）；觸發點在**客戶裁示後的施工階段**。
- 候選配置（依 5.1 第 10 點矩陣，**僅候選**）：機械文件／狀態同步＝Haiku／Low（D10(i)）；D3(a)、D8 取證據、G-5＝Sonnet／Medium；D2 資料契約、D4-3＝Opus／Medium；D3(b)、D4-1／2、D5 生產者、D6 G-1／G-4、D7、D8 開閘、R2／R3 裁示後施工＝Opus／High（公式／門檻／PIT／Risk Cap）；R1 純技術修補＝Sonnet／Medium（規格明確的小跨模組）。
- 不得把產品、資料、投資語意裁示包裝成模式切換。

## 5. 同批文件同步

- `docs/DECISIONS.md` `DEC-2026-11-05-04`「實作狀態」：原寫「位於尚未合併的開放 PR」。**FACT**：`services/v2_domain/allocation_evidence.py` 已在 `origin/main`；merge `861628cc` 為 `origin/main` 祖先（`git merge-base --is-ancestor` 驗證）。本 PR 以劃線保留舊句、加 2026-11-08 更正，**不改其他欄位**；屬純事實更正（技術狀態，非裁示）。
- `docs/BACKLOG.md` 檔尾登記區加 1 條索引：**未新增 BL 列、未改任何 BL 狀態**。

## 6. 本文重驗清單（文件組，origin/main `7ac7c935`）

| # | 宣稱 | 重驗方式 | 結果 |
|---|---|---|---|
| 1 | R1 NaN 反例 | `git archive` 副本 `python3 -I` 載入 `nav_metrics.py` | 與底稿一致（0.0／0.0／100.0／nan／nan） |
| 2 | R1 唯一計算 caller | `git grep` `ui_v2/hld/logic.py`；`git grep nav_metrics -- ui_v2 ui_v3` | 唯一計算點 `hld/logic.py` 902–904；`ui_v3` 無 |
| 3 | `nav_dividend` isfinite | `git grep isfinite services/v2_tables/` | `nav_dividend.py:602`「非有限數值」；`contract.py:143` 拒非有限 |
| 4 | R2 鏈 | `git grep decision_matrix／realtime_signal／render_macro_tab(`；讀 `app.py` | 鏈成立；`app.py:156,636` 為 `render_market_overview`，**底稿寫 `:157`，實為 `:156` import／`:636` 呼叫**（行號小差，結論不變） |
| 5 | R3 `ui_v2` 降級 | 讀 `ui_v2/alo/live.py`、`ui_v2/thresholds.py:24` | `NAV_NOT_READY_DAYS=10`；`>` 判 `too_old` 成立 |
| 6 | R3 `ui_v3` blocked | 讀 `assets_source.py` `evaluate` | 市值基準→`STATUS_BLOCKED`；`nav_not_ready=None` 成立 |
| 7 | R3 Old UI | 讀 `ui/tab3_t7_ledger.py` `_latest_nav_fx_t7`、`get_latest_nav` 前 50 行 | 未見日期檢查（與底稿一致；未逐行讀完全檔，仍標未驗） |
| 8 | `DEC-2026-11-05-04` 實作狀態 | `git merge-base --is-ancestor 861628cc origin/main`；`git ls-files` | 為祖先；`allocation_evidence.py` 在 main |
| 9 | Change Gate 條文 | 讀 `PROJECT_RULES.md` 5.1 第 10、11 點 | 引文逐字成立 |

未重驗：底稿 §D 的 DEC 全文（僅讀本文引用處）、AUD V1～V15、`decision_matrix` 行為（底稿實測，本次未重跑）、R2「2026-10-12 裁示」原文、動態 import／session 路徑。
