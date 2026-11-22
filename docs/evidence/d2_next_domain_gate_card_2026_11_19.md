# D2 下一個最小逐域契約 Gate 卡（OneBrain 前置契約線；第二版，修非作者稽核 Must-Fix 3）

> **單組作者（執行組）草稿，尚待非作者獨立稽核（第二版為回修稿）。** 屬 data identity／AI decision semantics 等級（`DEC-2026-10-16-05`）。**docs-only；不是客戶裁示、不是 Digest Schema／Provider／prompt／Risk Cap、不是施工授權**（`CLAUDE.md` §-1）。
> 基準 `origin/main` `9473a76f`（2026-11-19，重核；唯讀 `git show`）。路徑寫「檔案::符號」不寫行號；引用既有證據不複製。
> 標記：**[F]**＝可由文件／指令重現；**[I]**＝推論；**[R]**＝推薦，可被客戶推翻。全稱句一律「單組未驗」。
> 方向來源：「OneBrain 前置契約改推正式 D2、不再重做 Digest 研究」為客戶經 ChatGPT 轉達〔待核〕；`DEC-2026-11-19-01`～`-07` 皆查無此方向（`-06`／`-07` 為 Gate-D 條款級核准與 BL-0551 G1 登記，同樣無 OneBrain 轉 D2）。本卡只當研究題目，不改任何 Gate。

## 0. 結論先行
1. **[R] 下一個最小逐域 Gate＝身份域收尾（R-ID-2 `full_key`／R-ID-3 `ok`）。** 依下方方案 2，身份域是首批三域中**最不依賴正式公式／正式門檻／Schema 新欄**的一域（非「唯一」）；必要題 1 題。
2. **[F] 上一版推薦「列為 Digest Excluded」已撤回**：其前提（Digest 不需 `full_key`）被反證，見 2-A。
3. **[F] 這一個 Gate 不會讓 OneBrain 動工**：首個碰 Digest 內容的批次仍被 NAV（R-NAV-3＝D3(b)、R-NAV-6＝Schema 位置）、績效（BL-0427／0524 公式）、「D2 完成」判準未定義，以及第 3 節各 Gate 擋住。OB-B（離線 interface＋Fake）不需 D2 契約，卡在 `DEC-2026-11-18-03` 待確認 (b)(c)，與本卡獨立。

## 1. D2 逐域契約現況（只列必要域；[F] 讀自 `docs/DECISIONS.md` 原文與 D2 候選／prep 檔，provenance 照錄）

| 域／列 | 狀態 | 出處（DEC；provenance） | 擋住它的是什麼 |
|---|---|---|---|
| 身份 R-ID-1 `fund_code` | **契約文字已核**（`T-ID1`，含第 5 點「已知落差」：帶後綴輸入現行 `ok=True`、無違反標記，`test_mapping_miss_passes_through` 釘住）；Required 升格／New UI2 適用「仍未核」 | `-11-13-06`（客戶經總管轉達，要點轉述，非逐字） | Required 地位未確認（較嚴讀法；單組）；D2-A＝B 標示未實作 |
| 身份 R-ID-2 `full_key`、R-ID-3 `ok`（候選檔 K2／K3） | **Pending**（無專屬 DEC） | 相鄰：`-11-09-01` D2-C＝B；`-11-18-01` B 線＝只授權「最小必要內部取數鍵語意」**研究**，明列不核准 R-ID-2／3；`-11-19-02` Q2(4)(6)（僅路徑 B，不升格，〔待核〕） | **S7**：`full_key` 可否帶通路後綴。prep ⑦：僅「契約禁止後綴」（新行為）屬 identity Stop Gate 且需改程式；「如實描述現況」與「維持 Pending」不是 |
| NAV R-NAV-1／2／4／5 | **契約文字已核**；Required／New UI2 適用未核 | `-13-06`；`-14-07`（來源是否客戶本人〔待核〕）；`-17-06`（自稱客戶〔待核〕，**不新增 Provider 欄**） | 只缺 Required 確認 |
| NAV R-NAV-3 `fetched_at` | **暫緩（B），維持 Pending** | `-14-07`〔待核〕；`-18-01` 不授權清單再列 | **D3(b)＋D7**（`stale_after`、10 日 (a)–(e)、PIT）＝正式 threshold |
| NAV R-NAV-6 `ccy_source` | **Pending** | `-17-06` 末段〔待核〕；`-18-01` 不授權清單 | 是否進契約欄＝新欄位位置（Schema Gate）；候選檔自述目前不建議主動問 |
| 績效 R-PERF-2／4／5／7／8（1／3／6 為重複列） | **全 Pending**；1B 只在舊站已裁（`DEC-2026-10-23-02`） | `-11-11-04`；`-11-09-01` D2-B | 正式公式 BL-0427／0524、BL-0547、狀態字彙 D3(a)／(b) |
| 其餘六資料域 | **延後**；「延後」≠ Excluded | `-11-11-04` D2-G3＝A（ChatGPT 轉達，非逐字） | 持倉域另有 D6／D9 |
| Digest schema | **另一個 Gate**，D2 逐域契約完成後才提 | `-11-11-04` D2-G2＝A | — |
| **「D2 完成」判準** | **repo 內未見定義**（對 DECISIONS／HANDOFF／BACKLOG 關鍵字 grep「完成判準／定義／標準」0 命中；單組、有限） | — | 見 3-⑥ |

**[F] 計數**：已核契約文字 5 列；其餘 12 列待審中 3 列為重複列。**[I]** 5 列只核文字，逐列 R／O／E 分類未做。

**缺口補列（[F]，以上表之外的 Digest 層承接缺口；皆為單組讀文件）**
| 缺口 | 內容 | 出處 |
|---|---|---|
| Digest **Identity 群無現存 resolution 來源** | 67 §8.6／79 §8.2 的 Identity 群含 canonical identifier、類別、identity resolution 狀態（resolved／unresolved），且 Required 例含 identity；repo 內 canonical identity 仍為 DG-2 Shadow（flag 預設關，`DEC-2026-10-29-01` 影響範圍），D2 的 R-ID-1／2／3 都不是它。**不論 Q-ID 選哪案，這個缺口不會被關閉。** | 67 §8.6；79 §8.2；BL-0527 第 5 項（跨類別 identifier，隨 DG-2） |
| 市場指標逐項 provider | 市場域延後，Source 群的 provider 無契約；NAV 域已明定不新增 Provider 欄 | BL-0527 第 2 項；`-17-06` |
| OB-B 待確認 (a)(d)(e)(f) | (a) 客戶是否本人要求「平行完成 UI＋OneBrain」及涵蓋 OB-B；(d) 切片範圍與放置位置（E1）；(e) 程式 PR 後是否核准後續 OB 階段；(f) Digest 決策包的裁示方式。連同 (b)(c)，皆未答 | `DEC-2026-11-18-03` |

## 2. 唯一建議的 Gate：身份域收尾

### 2-A 為何撤回「Excluded」並重估風險（[F]，已實讀 `9473a76f` 檔案）
- 身份耦合在**上游**：`services/v2_tables/nav_dividend.py` 要求呼叫端明確給 `full_key` 並原樣交 L1；A 鏈回傳的 `full_key` 與 `fund_keys` 的不同或缺失時，該檔淨值不寫（`TEXT_KEY_MISMATCH`／`TEXT_KEY_MISSING`）。故「`services/v2_domain/` 對 `full_key` 0 命中」**不具證明力**（身份在更上游被用掉了）。
- `contract.py::NAV_FIELDS` 七欄無 `full_key`／mapping 欄：**NAV 列看不到它是怎麼從輸入代碼映到取數鍵的**。
- `ui_v3/viewmodels/fund_lookup.py`、`ui_v3/adapters/fund_lookup.py` 檔頭自述：L2 `resolve_full_keys` 可能經別名表把輸入映為不同 `full_key`，`RESULT` 欄位屬 `full_key`、**不保證等於輸入代碼**，adapter 看不到它。
- `T-ID1` 第 5 點自述：帶後綴輸入現行 `ok=True`、無違反標記。
- `-19-02` Q2(5)「內部取數鍵不上畫面」限路徑 B（Q2(6)）；**不得延伸為「Digest 不需要 `full_key`」的佐證**。上一版這樣用是錯的。
- 與 67 §8.6／79 §8.2–8.3 矛盾：Identity 群含 identity resolution 狀態且 Required；「Excluded」在該處定義為 UI 呈現／session 類，**不是**「內部鍵」；且 Digest 層分類受 D2-G2（不得因 D2 方向核准就啟動 Digest schema 研究）約束。

### 2-B 與既有文件的關係（沿用／縮小／取代）
| 既有文件 | 關係 |
|---|---|
| 決策包 `onebrain_digest_decision_pack_2026_11_18.md` **Q5**（R-ID-2／3、R-NAV-6、R-PERF；推薦只推身份／NAV 剩餘列，R-ID-3 同批） | **縮小**：只取其中 R-ID-2／3；R-NAV-6 拆出（Schema 題、候選檔建議不主動問）；R-NAV-3 隨 Q4；績效暫緩——沿用 Q5 自己的「績效暫緩」判斷 |
| 決策包 **Q6**（Digest schema Gate 是否提出） | **沿用**：現在不問 |
| `d2_contract_approval_prep_2026_11_12.md` ⑦（S7 先裁、R-ID-3 隨 R-ID-2 同批、推薦「C 起手」）；候選檔 K2／K3 | **沿用 R-ID-3 隨 R-ID-2 同批**；對「C 起手」見下方推薦理由（**部分不採**） |

### 2-C Q-ID：需客戶裁示的題目（必要 1 題）
**白話問法**：系統內部有兩個身份相關欄位——「取數用的基金代碼」`full_key`、「這個代碼格式能不能解析」`ok`——目前都還沒有被客戶核准成正式契約。要怎麼收尾，才算「基金身份」這一域處理完？（下表共 **5 案**，編號 1～5。）
**執行組推薦方案 2：把現況如實寫成契約、並明標已知問題，讓這一域先過關。代價是：它不修任何問題，而且會把「帶通路後綴的代碼目前會被放行」寫進正式文字，可能被讀成客戶接受了這個行為。** 若客戶想先把後綴規則定清楚再說，選方案 1（即 prep 原推薦）。
（內部術語：S7＝取數用代碼可否帶通路後綴；「prep 對照」欄＝`d2_contract_approval_prep` ⑦ 的 A／B／C 三案，與本卡 1～5 編號是兩套，不要混讀。）

| 本卡方案 | 內容 | prep ⑦ 對照 | 優點／缺點 | 風險（[I]） |
|---|---|---|---|---|
| **1** | 先裁 S7（允許／禁止 `full_key` 帶後綴），再回頭核可 | **C（prep 推薦）** | +身份規則一次講清；−題目最重，若選「禁止」是新行為、須改程式，非純契約題 | 高 |
| **2（[R]）** | 核准契約文字：`full_key`＝MoneyDJ 取數鍵，**可能經別名表映射（僅留 `mapping_source` 追溯，`-11-09-01` D2-C＝B）、現行接受通路後綴（寫明為已知缺口）**；`ok`＝僅表示格式通過，不表示基金存在；後綴規則（S7）明寫「未裁」留給 Gate-D／DG-2。〔另：若要求 NAV 取用時載明「`full_key` 與來源回傳不一致則不寫」，那是在已核 `T-NAV1` 之外**新增條款，另須經 Gate**，不含在方案 2 內〕 | **A** | +零程式。−**(a) 與 `T-ID1` §5 方向相反，不是同款**：`T-ID1` §5 是「契約要求標示違反、程式尚未做到」，方案 2 卻是把「現行接受後綴、`ok=True`」寫成現況；同一個 Sheet 輸入若帶後綴，R-ID-1 視為**違反**、R-ID-2／3 卻視為**可解析**，契約內部矛盾，須明寫並由客戶接受。−**(b) 可能被讀成採信後綴**：`-13-06`／`-19-02` 的不授權範圍含「後綴碼語意」，把現行後綴行為寫進正式文字有此風險。−**(c) 跨部署非確定性**：prep ④ 記載別名表隨部署不同，同一輸入可得不同 `full_key`（且 NAV 列沒有 mapping 欄、無逐筆記錄），方案 2 只能寫明、不能消除。−**(d) 與 prep（約 §333「S7＝唯一擋 `full_key`／`ok`」）直接衝突**：方案 2 主張 S7 可不先裁，這是客戶要知道的取捨。−(e) `ok` 句與 `-19-02` Q2(4) 近乎同文，但那是路徑 B 專屬；擴到全域 R-ID-3 是**〔I〕新問題**，不是已答 | **中至高**（(a)(b)(c) 皆未處理；不得寫成低或中） |
| 3 | 契約規定不得帶後綴 | **B** | +規則明確；−identity Stop Gate、需程式 | 高 |
| 4 | D2 層**不納入／Optional**：R-ID-2／3 不列 D2 必備，Digest 取用 NAV 時須附「身份不確定」標記或 Missing（**該標記只是『來源缺身份依據』的揭露，不是新狀態詞，且須沿 `DEC-2026-11-08-04` Q4 既有「資料未備／無法判定」，不得新增正式詞；格式屬 Digest 層**） | 不在 prep（新增） | +不必先裁 S7；−**跨 D2／Digest 兩 Gate**：須客戶先確認「是否允許 D2 先預判 Digest 範圍」；與 67 §8.6 Identity 群 Required 張力未解 | **高（不建議本輪裁示）**：牽涉未啟動的 Digest 層分類，且張力未解；上一版 Excluded 版本已被反證 |
| 5 | 維持 Pending | — | +零動作；−D2 身份域不算處理完，卡 D2-G2 順序 | 低但無進展 |

**[R] 推薦方案 2（力度偏弱），且為何不採 prep 的「C 起手」**：(i) 方案 1 把最重的 S7 身份規則放在前面，其「禁止後綴」分支才是 Stop Gate 與程式題，會讓首題變成重題；(ii) 方案 2 不預判 S7，S7 仍可由 Gate-D GD-Q3②／DG-2 另走；(iii) 客戶在 `-13-06` 對 R-ID-1 接受過「契約文字＋明標已知落差」的處理〔轉述／待核，非逐字〕，但**方向不同於方案 2**（見方案 2 欄 (a)），故此點只能當格式先例、不能當同款授權。**代價（須據實告知客戶）**：方案 2 不縮小任何現行風險，只是寫明，且帶 (a)(b)(c)(d) 四項取捨；若客戶偏好先把身份規則收乾淨，方案 1 才是 prep 原推薦，本組不堅持方案 2。方案 2 與 4 的取捨即「是否讓 D2 先預判 Digest」，建議本輪不選 4。

**Q-REQ（選填，可併句）**：已核的 R-ID-1 是否同時定為 Required？**[R] 是；理由僅為「與已核通則（67 §8.6 Required 含 identity）方向相容，仍待逐列確認」**，不得當成已涵蓋。答案會成為 NAV 4 列的先例，本卡不替 NAV 問。

**本 Gate 不做**：不核准 S7 結論、ISIN／別名表／後綴碼語意、不改 resolver／Schema／程式、不碰 FX、不升格 DG2、不動 BL-0545；逐字文字另經最小 Decision Gate（方向 ≠ 文字，`-19-05`）。

## 3. OneBrain 距離「第一個合法實作批」尚缺哪些不可省略的 D2 契約

**先定義「第一個合法實作批」（[I]，兩種讀法，須客戶確認終點線）**
- **批 α＝OB-B（75 第 15 節：離線 typed interface＋Fake Provider）**。**[F]** 不含 Digest 內容，75 第 16 節 OB-01 前置只寫「本檔」→ **需要 0 個 D2 契約**；擋它的是 `DEC-2026-11-18-03`（來源〔待核〕）：程式 PR 前客戶須先確認 (b)(c)，並完成獨立稽核且 Must-Fix 清零。D2 完成與否都不解鎖它。
- **批 β＝首個吃 Digest 內容的批次（OB-02／Digest schema）**。**[F]** `-11-11-04` D2-G2＝A。下表針對 β。

**β 前的 D2 缺口（依賴順序；「不可省略」＝必須有明示處置，不能默默略過）**
| 序 | 缺什麼 | 現況 | 阻擋關係 | 即使處置完仍不解鎖 |
|---|---|---|---|---|
| ① | 身份 R-ID-2／3 處置 | Pending | 本卡 Q-ID；**〔I〕**S7 僅在選方案 1／3 時成為前置（prep 另有「S7 先裁」相反讀法，見 2-C 方案 2 (d)） | Digest Identity 群 resolution 來源（見 §1 缺口表） |
| ② | 已核 5 列 R／O／E 分類 | 未核 | 一個跨域澄清（Q-REQ 先例） | Digest schema |
| ③ | NAV R-NAV-6 | Pending | Schema Gate（欄位位置）；非門檻題 | 市場域 provider（BL-0527 第 2 項） |
| ④ | NAV R-NAV-3 `fetched_at` | 暫緩 | **D3(b)＋D7**＝正式 threshold，客戶裁；專案 AI 只可先備各來源發布延遲「事實」，不訂值 | stale 判定值本身 |
| ⑤ | 績效 R-PERF-2／4／5／7／8 | Pending | **正式公式** BL-0427／0524；BL-0547 N1 查證；狀態字彙 D3(a)→契約（N1 同題） | 1M／3M／6M 無核准算法 |
| ⑥ | **「D2 完成」終點線** | 未定義 | **[R] 另問 1 題**：首批三域逐列處置完即視為 D2 完成（其餘域在 Digest 初版不涵蓋），或九域全完成才算；後者會把 D6、BL-0545 拉進來 | 無 |

**[I] 對 ⑥ 的說明（已降級為推論）**：67 §5.4 只規範「Missing 不得→0／neutral／safe／HOLD」與「本期行動在 Risk Cap 定義前只輸出『無法判定』」，**不涵蓋持倉／配息／配置域**；故「延後域在 Digest 初版一律 Missing」是本組推論，非 67 的規定，須客戶確認。「Missing-by-design」只是本卡的**流程用語**，不是 Digest 狀態詞（狀態詞受 `DEC-2026-11-08-04` Q4 約束）。若採首批三域終點，v-b 六段中「我的資產與配置」「持股」兩項的資料域仍延後，初版覆蓋面會小。

**即使 D2 全完成仍被其他 Gate 阻擋（[F]，各自獨立）**
| Gate | 擋什麼 | 出處 |
|---|---|---|
| Digest schema Gate（D2-G2）；N1–N5 | OB-02、fingerprint、trace | `-11-11-04`；BL-0527 |
| Digest Identity 群 canonical identifier／resolution 狀態（DG-2 Shadow 未轉正） | Digest 身份欄 | BL-0527 第 5 項；BL-0521 |
| Rule ID／`rule_version`／門檻引用格式（D4-3） | `rule_ref`、Evidence trace | 79 UI-10 |
| **Risk Cap（BL-0495）、減碼 trigger（BL-0496）、System Action State 實值** | 「本期行動」只能「⬜ 無法判定」 | 67 §5.4／§8.2 |
| 反證定義（D5）、四區對映（BL-0540） | 🤖 Maximum Falsification 區 | 決策包 Q7；BL-0540 |
| **OB-B (a)–(f)**；`DEC-2026-10-31-03` 逐階段另裁 | 任何 Provider 程式、後續 OB-C 起 | `-11-18-03`；`-10-31-03` |
| BL-0528 G1～G6 | OB-09 舊線遷移 | BL-0528 |
| Phase 7／🤖 頁、UI-14 線框 | 🤖 頁面掛載 | 67 §8.9 |
| BL-0545（BLOCKED）、BL-0551、D8 FX 閘門 | 正式資料准入、真實取數、非 TWD 市值 | HANDOFF；`-11-08-02` |
| Model／Effort Change Gate（`PROJECT_RULES.md` 第 5.1 節） | OneBrain 施工等級 | 本組未評估 |

## 4. 與 BL-0527 N1–N5、OB-B (b)(c) 的關係（不重複提問）
- **N1／N2／N3**：Digest 層，依 D2-G2 僅登記；Q-ID 與其無共同問句。N1 與 ⑤（R-PERF-7／8）、N5 與 ④ 會在後續 Gate 相遇。
- **N4＝OB-B (b)(c)**（決策包 Q1＋Q2）：與 D2 獨立，本卡不問、不依賴。
- **N5**（Rule ID 格式＋stale／conflict／10 日）：後半即 ④；排在身份 Gate 之後。
- **[R] 問客戶順序**：Q-ID（＋Q-REQ）→ ⑥ 終點線 →（備好各來源發布延遲事實後）D3(b)＋③ → 績效公式題；N1–N5 與 OB-B 照 `-19-02`／`-19-05` 維持待客戶，不插隊。

## 5. 已被 DEC 回答、不重提（provenance 見第 1 節；多為要點轉述）
R-ID-1／R-NAV-1／2／4／5 契約文字（`-13-06`、`-14-07`、`-17-06`）｜R-NAV-3 暫緩＝B（`-14-07`）｜Q0＝A（`-13-06`）｜D2-A＝B、D2-B＝收緊後 C、D2-C＝B（`-11-09-01`）｜D2-G1／G2／G3（`-11-11-04`）｜選股池（EXP）代碼命名空間另案（`-13-06` (4)）｜D1 方案 C、D8 FX 維持關閉（`-11-08-02`）｜不新增「過期」「衝突」正式詞（`-11-08-04` Q4）｜NAV 10 日規則不得升格（`-11-05-03`）｜1B 限舊站（`-10-23-02`）｜Missing 不得→0／neutral（67 §5.4）｜Gate-D Q1／Q2、G1／G4／Q4／Q5 方向（`-11-19-02`、`-19-05`；僅方向）；**補**：`-19-02` Q2(4)「`ok` 只代表格式通過」（僅路徑 B；方案 2 擴到全域屬新問題）、`-18-01` B 線對 R-ID-2／3「最小必要內部取數鍵語意」的**研究**授權（只授權研究，不核准 R-ID-2／3）、`-19-06` 條款級核准與 Q5-B 暫行（僅路徑 B 顯示契約，不涉 D2 列）。

## 6. 未查證項（誠實揭露）
1. **單組作者**；§1「Pending」「未見」「0 命中」為字面 `git grep`／文件讀取，改名、別名、動態組字串不在內。
2. 2-A 的耦合事實已實讀 `nav_dividend.py`、`contract.py`、兩個 `ui_v3/*fund_lookup.py` 檔頭，**未跑測試、未追完整呼叫鏈**；DG-2 Shadow flag 的現值取自 `DEC-2026-10-29-01` 文字，本次未重讀 `shared/fund_identity.py` 現值。
3. 各 DEC provenance 為讀 `DECISIONS.md` 原文所得；逐字存檔未讀；`-14-07`、`-17-06`、`-18-03`、`-19-02`、`-19-05`、`-19-06` 客戶來源均〔待核〕。
4. D2 17 列狀態取自候選檔／prep，未逐列重驗程式；未讀 `-19-06` 各條款逐字內容（僅確認其不涉 D2 列）。
5. 「Required 升格」較嚴讀法、「終點線未定義」、批 α／β 切分、「延後域在 Digest 初版為 Missing」皆為推論，客戶原意可能不同。
6. 方案風險等級為作者推論，未實作驗證；方案 4 的 D2／Digest 跨 Gate 歸屬須客戶確認，本組未判定。

## 7. 2026-11-21 補：R-ID-2 `full_key`／R-ID-3 `ok` 候選契約文字（Sheet A0 裁示後；本節 append-only，§0～§6 一字未改）

> **單組（C 線）草案，未經獨立複驗；候選文字，不是客戶核准、不是契約、不是施工授權**（`CLAUDE.md` §-1）。屬 data identity 等級，須至少 1 組獨立稽核（Work）與客戶逐字核准後才能成為契約。基準 main `33c0cae8c5204aba7cfc78b1aba1571d84498e6a`。標記：**[實測]**＝離線指令輸出；**[靜讀]**＝讀原始碼；**[推演]**＝模擬，非現況；**NV**＝NOT VERIFIED。
> **為什麼補這一節**：客戶 2026-11-21 裁示 Sheet「基金代號」欄採 **A0**（#1296 comment 7060465421）：限該欄；帶通路後綴時標示、保留原始代碼、沿既有流程送 resolver 嘗試取數；沿用既有回傳 key 核對，若回傳基本碼而與請求 key 不符，仍略過該筆 NAV；真實來源對後綴的支援仍未驗。**該裁示明列不涵蓋**：找基金／選股池、共用 resolver 規則、R-ID-2／3、D2／C-13、Digest、Provider、Phase 7。故本節只把 A0 的**行為**寫成 R-ID-2／3 的**候選文字**，供下一個逐字核准 Gate 使用；§2-C 的 Q-ID 五案**不因本節改變**（本節的寫法接近方案 2，但**分入口**，且與 §2-C 方案 2 欄 (a) 的「契約內部矛盾」顧慮的關係見 7-4）。
> 證據：[#1323](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1323) 的 `docs/evidence/d2_s7_two_entry_trace_2026_11_21/`（合成碼 `ZZ9999`／`ZZ9999-SFX01`，離線替身）；Work A0 驗收矩陣（#1296 comment 7060505473）。
> **第二版（2026-11-21）**：依 Work 獨立 QA（#1296 comment 7062763480，NEEDS FIX，2 組 Must-Fix）修正 7-1／7-2／7-3；舊句不保留在本節（§7 為草案、未核准）。修正點：①R-ID-2 分清 `input`／`parsed_code`／`full_key` 三種值與保留層級；②R-ID-3 的 `ok` 是既有 resolver 的解析結果，且 `PAGE_UNMATCHED/no_page` 不證明基金存在性；③7-3 補 `key_failed` 與配息的證據邊界。

### 7-1 三個必須分開的概念（候選契約的核心）
| 概念 | 在系統裡是什麼 | 由誰決定 | **不等於** |
|---|---|---|---|
| **傳入 resolver 的值（`input`）** | **傳入 `resolve_full_keys` 的那個字串**，原樣留在 `results[].input`（未 strip、未轉大寫）[靜讀：`fund_keys.py::_resolve_one` 的 `{"input": raw}`；實測]。⚠️ **這只證明 resolver 參數**：Sheet 上游組裝對鍵欄已先去前後空白（`alo_holdings.py::_key_text`），故它**不證明 Sheet 原始儲存格逐字往返**；Sheet 原欄位的「標示」與原碼保留＝**A0 實作項，尚未實作** | 呼叫端傳入的值 | `parsed_code`、`full_key`（兩者都已經過 strip、大寫） |
| **A 鏈取數碼（`parsed_code`）** | resolver 解析後、**查別名表之前**的代碼（`parse_moneydj_input` 的 code，已大寫）；既有呼叫端把它當 `chain_code` 交給 A 鏈，A 鏈自己再查別名表 [靜讀：`ui_v2/hld/source.py`、`ui_v2/alo/source.py`、`settings_store.py`，皆傳 `parsed_code` 作 `chain_code`；`nav_dividend.py::fetch_nav_chain_with_error`] | resolver＋A 鏈 | `full_key`（別名命中時兩者可不同） |
| **取數鍵（`full_key`）與格式通過（`ok`）** | 該輸入通過 resolver 鏈：字串→strip→非空→ASCII→`upper`→`parse_moneydj_input`→別名表→最終 `_is_pure_code`，得到合格 `full_key`（`ok=True`）；**`ok` 是這條既有解析鏈的結果，別名輸出也要過最終格式檢查**（例：別名的 `public_code` 為 `?` → `ok=False`、`full_key=None`）[靜讀＋實測] | `fund_keys.resolve_full_keys`（純函式，不取數） | **基金存在**、取得 NAV、後綴已被驗證 |
| **基金存在／取得資料** | 來源（MoneyDJ／TDCC／FundClear／A 鏈）對該 `full_key` 有回應與資料；🔍 以 `ok／not_found／not_listed／unrecognized_page／failed` 表示 [靜讀] | 取數層與來源（本檔不判） | `ok=True`（`ok=True` 只代表「可以拿去問來源」） |
實測（[#1323 輸出](https://github.com/linchen-20200325/my-Fund-dashboard/blob/841cb592bab04d82327b53fee249b8d50fbe5e5f/docs/evidence/d2_s7_two_entry_trace_2026_11_21/output.json)）：`ZZ9999-SFX01` → `ok=True`、`full_key=ZZ9999-SFX01`、`parsed_code=ZZ9999-SFX01`、`mapping_hit=False`；同一輸入在 🔍 的來源替身回覆後，adapter 的**首個可見結果**為 `PAGE_UNMATCHED／no_page`——它只表示**該次未匹配到頁面**，**不證明基金存在或不存在**；`ok=True` 與該結果並存，正是「格式通過」與「基金存在」必須分開的實例。
別名映射實測（離線，作者與 Work 皆重跑）：注入別名 `ZZ9999-SFX01 → QQ1234` 後，`input=ZZ9999-SFX01`、`parsed_code=ZZ9999-SFX01`（仍帶後綴）、`full_key=QQ1234`、`mapping_hit=True`、`ok=True`。

### 7-2 兩列候選契約（逐字為候選，PendingWording；括號內為待核）
| 列 | 候選契約文字（**草案**） | 適用入口 | 與現況的對照 | 待核邊界（Pending） |
|---|---|---|---|---|
| **R-ID-2 `full_key`** | (1) 三種值分開記：`input`＝傳入 resolver 的值（逐字保留，**僅 resolver 參數層級**）；`parsed_code`＝strip、大寫、`parse_moneydj_input` 後、查別名表前的代碼，**既有 A 鏈以它作 `chain_code`**；`full_key`＝別名表（若命中取其 `public_code`）與最終純代碼格式檢查後的字串，**既有 A 鏈回傳的 key 以它核對**。`full_key` 不是原碼。(2) **別名表命中時 `full_key` 可與輸入完全不同**（僅 `mapping_source` 可追溯，`DEC-2026-11-09-01` D2-C＝B）。(3) **Sheet「基金代號」欄帶通路後綴（`-` 加 2–20 碼）時（A0）**：該欄須**標示「帶後綴」、保留 Sheet 原欄位的原始代碼，並沿既有流程嘗試取數**（既有 A 鏈以 `parsed_code` 作 `chain_code`、以 `full_key` 核對回傳 key）；**不擅自剝除後綴**。「不剝、不截、不改寫」只適用於 **Sheet 原欄位的保留**與**不得擅剝後綴**，**不排除既有別名映射**（例：`ZZ9999-SFX01` 映射後 `parsed_code=ZZ9999-SFX01`、`full_key=QQ1234`，見 7-1）。(4) **下游核對（現況描述，非新條款）**：取數層（A 鏈）回傳的 `full_key` 與 resolver 的 `full_key` 不同或缺失時，該檔 NAV（及配息）**不寫**，原因文字照實保留（不猜哪一個對）。(5) 本列**不**宣稱後綴碼語意、NAV 等價性、通路頁是否存在。 | **僅 Sheet「基金代號」欄的取數入口**：`ui_v2/hld/source.py`、`ui_v2/alo/source.py`、`services/v2_tables/settings_store.py::refetch_nav`（皆呼叫 `resolve_full_keys`，[靜讀]）。**不含**：🔍 找基金（路徑 B，`-19-02` Q2(4)(6) 另行）、選股池 EXP（命名空間另案，`-13-06` (4)）、💼 `assets_source`（**不呼叫 resolver**，[實測]）。 | (1)(2)(5)＝現行行為描述 [實測／靜讀]（三種值與別名映射例：作者與 Work 離線重跑）；(3) 的 Sheet 原欄位**標示與原碼保留＝尚未實作**（Sheet 入口目前對後綴「不說話」，`DG2_SHADOW_ENABLED=False`，[實測]；`input` 逐字保留僅是 resolver 參數）；(4)＝現行行為，已有測試釘住：`tests/test_v2_tables_nav_chain_handover.py::test_A鏈回的full_key與fund_keys不同_照實標缺_原因讀得懂`（本輪離線跑 157 passed 含該檔與 `test_v2_tables_fund_keys.py`）。配息同守衛 [靜讀：`nav_dividend.py::_div_from_chain`]。 | **P1**「標示」的承載（resolver 回傳新欄位＝介面／Schema 變更；`resolve_full_keys` 無 `input_source` 參數，如何只限 Sheet 欄＝設計題）— A0 實作 Gate。**P2** (4) 是否寫成規範性條款（見 7-5 待裁點）。**P3** 配息：A0 裁示字面只提 NAV，配息同守衛為 [靜讀]，是否納入待核。**P4** 真實來源／真實 A 鏈對後綴碼回什麼＝NV。**P5** 別名表跨部署非確定性（`mapping_source` 分不出 csv 缺檔與讀取失敗，S7 卡 F9）＝已知缺口，須明寫。 |
| **R-ID-3 `ok`** | (1) `ok`＝**既有 resolver 的解析結果**：該輸入通過上述解析鏈（含別名輸出的最終格式檢查）並得到合格 `full_key` 的布林；**僅表示代碼格式可解析、可送交取數**。(2) **`ok=True` 不表示基金存在、不表示取得 NAV、不表示後綴已驗證**；`ok=False` 時 `full_key`／`portal` 為 None、`error` 為字串，**不得補預設鍵**、不截斷、不猜。(3) **A0 標示本身不改變 `ok` 的判定**：帶後綴輸入的 `ok` 仍由既有解析鏈與別名輸出檢查決定（例：合格的後綴碼 `ok=True`；別名輸出不合格則 `ok=False`），**本列不保證任何帶後綴輸入通過**（標示與 `ok` 是兩件事：標示不阻擋取數）；「基金存在」須由取數層另行判定。(4) 候選檔 K3 原述「區分沒取到與沒有這檔」**不準確**（`ok` 不取數），本列改述為「代碼可解析／不可解析」（S7 卡 N4）。 | 同 R-ID-2（Sheet 取數入口）。🔍 的 `ok` 語意僅路徑 B（`-19-02` Q2(4)：`ok` 只代表格式通過）；EXP 另案。 | (1)(2)(4)＝現行行為／描述修正 [靜讀＋實測]；(3)＝A0 後的**目標行為**：現況合格後綴碼 `ok=True`、尚無標示 [實測]；別名輸出不合格 → `ok=False` [實測]。 | **P6** 「基金存在」誰判、字樣為何＝Digest／呈現層，沿 `DEC-2026-11-08-04` Q4 既有「資料未備／無法判定」，**不新增正式詞**；本列只劃界、不給字樣。**P7** 與 R-ID-1 的關係：Sheet 欄帶後綴＝R-ID-1 視為「違反」並標示（A0），R-ID-3 照既有 resolver 判定（合格者 `ok=True`）——兩者**不矛盾**的寫法是「標示 ≠ 阻擋」，須客戶確認此寫法（§2-C 方案 2 欄 (a) 的顧慮在 A0 下改為「標示＋保留取數」而非「靜默放行」）。 |

### 7-3 key 不符時略過 NAV 的行為（A0 裁示明載；[實測／推演] 分列）
| 情境（合成碼 `ZZ9999-SFX01`） | 結果 | 依據 |
|---|---|---|
| 來源／A 鏈回相同 key | 取數、寫 NAV 列 | [實測]：#1323 `1b_hld_chain_current(echo)`：兩檔各寫 2 列 NAV |
| 來源／A 鏈回基本碼 `ZZ9999`（不同 key） | **該檔 NAV 不寫**，`nav_errors` 為「A 鏈回傳的 full_key 'ZZ9999' 與代碼對照（fund_keys）的 full_key 'ZZ9999-SFX01' 不同；不猜哪一個對，這一檔的淨值不寫」；基本碼檔照常寫入 | [實測，替身]：#1323 `1b_hld_chain_INFER`；既有測試釘住同一守衛 |
| 來源回傳缺 `full_key` | 該檔 NAV 不寫（`TEXT_KEY_MISSING`） | [靜讀：`nav_dividend.py::_nav_from_chain`] |
| 真實 A 鏈／真實來源實際回什麼 | **NV** | 需真取數（BL-0545／BL-0551 Gate） |
**要點**：這是**下游依賴 `full_key` 的現有守衛**，A0 沒有改它；契約若要把它寫成 R-ID-2 條款，是把一個 NAV 域行為提升為身份域文字（見 7-5）。**證據邊界（依 Work QA #7062763480；逐條分列，不混用）**：
1. **已驗 ALO 路徑（離線，Work）**：後綴碼、基本碼與 `?` 先交 resolver。只有通過解析的後綴碼與基本碼會進入 A 鏈替身；`?` 在 resolver 被拒絕，隨後由 `ui_v2/alo/live.py` 的 `assemble_nav` 列入 `notes.key_failed`。A 鏈替身回基本碼後**該檔 NAV 略過、有 NAV 錯誤文字**，基本碼對照仍有 NAV；`notes.key_failed` **只含被 resolver 拒絕的 `?`**（`key_failed` ＝ `results[].ok is False` 的輸入，[靜讀：`live.py`]）。**因此這條路徑上「回傳 key 不符」不會變成 Evidence 的 resolver `key_failed`**；它只以取數錯誤文字呈現。
2. **#1323 `3_evidence_probe`（直接注入）**：把 `key_failed=[code]` 直接交給 `build_allocation_evidence`，得 `nav_state=failed`、`nav_cause.key_failed=true`；未標則 `no_data`。這是**另一條證據**（生產者的輸入語意），**不是**「key 不符會產生 `key_failed`」的證據，也未證明真實來源或其他路徑。
3. **配息（三層分列）**：(a) **源碼靜讀**：`nav_dividend.py::_div_from_chain` 缺 key 或不符回錯誤並拒收 items；A0 客戶裁示只涵蓋 NAV，配息是既有守衛的觀察。(b) **離線實跑**：既有測試 `tests/test_v2_tables_dividend_chain.py` 的配息 key 不符測項 1 passed（作者與 Work 各跑）；Work 另用非空替身 payload 驗匹配 key 保留 items、不符／缺 key 經建列器得零列與錯誤。(c) **真實來源：NOT RUN**。
4. **真實 A 鏈／真實來源對後綴碼的支援：NOT VERIFIED。**

### 7-4 與既有卡內容的關係
- **沿用**：§2-C 的 Q-ID 五案、推薦與風險一字不改。A0 只回答 **Sheet 入口行為**，**不是** Q-ID 的答案；R-ID-2／3 仍 **Pending**。
- **縮小**：本節把「方案 2 式的契約文字」改為**分入口**寫法——Sheet 取數入口適用 A0；🔍／EXP／💼 各標「另案／不經 resolver」，避免把 A0 外推到共用 resolver（A0 裁示明列不涵蓋共用 resolver 規則）。
- **未解**：§1 缺口「Digest Identity 群無現存 resolution 來源」不因本節而關閉；C-13（`assets_source` 證據轉接）、NAV stale／FX missing 穿透維持原 Gate。
- **實作面（另案，不在本節）**：A0 標示需新增承載欄位與入口維度（S7 卡 §i 最小 Gate 草稿的「A0 實作面成本」），屬 resolver 介面／Schema 變更，須另授權；`fund_keys` 的漂移鎖（`test_pure_code_pattern_matches_l1_source`）若改 pattern 須同步 L1，本節不改 pattern。

### 7-5 一個待裁點（單題；總管送客戶前請 Work 獨立核對 7-1～7-3）
**問題**：「取數層回傳 key 與請求 key 不符時，略過該檔 NAV」這條行為，要不要**寫進 R-ID-2 契約文字成為規範性條款**？
| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **Y（推薦）只描述現況、規範留 NAV 域** | R-ID-2 僅以「現況描述」記載該守衛並指向 NAV 域；規範性條款留給 NAV 域後續逐字 Gate（`T-NAV1` 之外的新增條款本來就須另經 Gate，§2-C 方案 2 欄註） | 不擴大 A0 裁示範圍（A0 只提 NAV、只限 Sheet 欄）；不預判 NAV 域契約；身份域可先收尾 | Digest 層若要引用「key 不符」原因，須等 NAV 域條款到位；契約短期內「描述」與「規範」分兩處 | 低 |
| X 寫成 R-ID-2 規範性條款（NAV＋配息，Sheet 入口） | 把守衛升格為身份契約條款 | 契約自足；身份與 NAV 的耦合（§2-A）一處看齊 | 跨 NAV 域、超出 A0 字面（配息未獲裁）；須同批 Gate 與獨立稽核；與 `-11-13-06`／`-14-07` 已核 NAV 條款的整合未查 | 中 |
**AI 推薦：Y**。**已知答案不重問**：A0 規則本身（#1296 comment 7060465421）；R-ID-1／`T-ID1`；`DEC-2026-11-09-01` D2-C＝B；S7 的 Sheet 欄行為已裁，**共用 resolver／🔍／EXP 未裁**。

### 7-6 本節未查證與限制
1. 單組、未經獨立複驗；候選文字為草案，**逐字另經最小 Decision Gate**（方向 ≠ 文字，`-19-05`）。
2. 離線證據全為合成碼與替身；**真實來源／真實 A 鏈對後綴的行為＝NV**。
3. 7-2 的入口清單取自 `git grep resolve_full_keys` 的靜讀，**不宣稱窮舉**（動態呼叫、其他分支不在內）。
4. 「key 不符」守衛是否同時涵蓋所有 A 鏈回傳路徑、及其與 Evidence `key_failed` 的對映＝NV／待核（7-3）。
5. 配息：源碼靜讀、離線實跑（既有測試與 Work 替身 payload）、真實來源 NOT RUN 三層已在 7-3 分列；真實 A 鏈對後綴的支援 NOT VERIFIED。

## 8. 2026-11-22 補：R-ID-2／R-ID-3 客戶核准狀態（本節 append-only，§0～§7 一字未改）

> **客戶已正式核准** #1296 comment [`7072733923`](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7072733923) 的 R-ID-2 五項與 R-ID-3 三項完整逐字條款（方案 A）；正式紀錄見 `docs/DECISIONS.md` 的 `DEC-2026-11-22-01`（含逐字條文）。權威原文＝ #1296 comment [`7072112379`](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7072112379) §2。
> **與本卡 §7-2 的關係**：§7-2 是 2026-11-21 的**候選**表，保留作歷史，**不再是現行文字**。核准文字相對 §7-2 的差額：(a) R-ID-2(4) 收窄為「〔現況觀察，非規範〕」，只述 NAV、不述配息，規範性條款屬 NAV 域；(b) R-ID-2(3)、R-ID-3(3) 明標「〔目標行為；**尚未實作**〕」；(c) 原 R-ID-3(4)（K3 評註）已移出契約文字。
> **現行狀態**：R-ID-2、R-ID-3＝契約文字已核（**僅 Sheet「基金代號」欄取數入口**）；Required 升格／New UI2 適用仍未核。**未核准、仍 Pending**：A0 實作（P1，resolver 介面／Schema）、NAV 規範性條款（P2）、配息是否納入（P3）、存在性字樣（P6）、S7 對 Sheet 欄以外入口（P7「標示≠阻擋」的語意即 R-ID-3(3) 核准文字，屬目標行為、尚未實作）、R-NAV-3／R-NAV-6／R-PERF-1～8。真實來源／真實 A 鏈對後綴碼的行為與別名表跨部署一致性＝NOT VERIFIED。
> **§2-C 的 Q-ID 與第二題**：第二題（D2 首批流程完成判準）已由客戶於 #1296 comment [`7072760335`](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7072760335) **獨立**核准 Work 修正版單題，正式紀錄見 `DEC-2026-11-22-02`（與 `DEC-2026-11-22-01` 互不替代）；見下方 §8-2。本節**不**宣告首批三域完成，不啟動 Digest schema。
> 本節只是狀態同步，**不是**施工授權（`CLAUDE.md` §-1）。

### 8-2 首批流程完成判準（客戶核准，`DEC-2026-11-22-02`）與逐列盤點（登記時現況；重算，不照搬舊總數）

> **判準（客戶逐字核准的單題）**：「是否同意以「首批身份、NAV、績效逐列經客戶明示核准或暫緩，記錄適用範圍及未決依賴」作為首批 D2 **流程完成**判準，並接受它僅滿足 D2-G2 的**另行提案**前置？暫緩列維持 Pending，初版不以其作金融判讀；欄位納入、必要缺項揭露與狀態映射留 Digest Gate。其餘六域按 G3 延後。逐列正式契約、Required 分類、schema 研究／施工與發布仍各依原授權。」
> **效力**：僅是**完成條件**，**不是**宣告 D2 已完成；達成後僅取得**另行提出** D2-G2 Digest schema 決策案的資格（不等於 Digest schema 核准）。**暫緩仍 Pending，不是 Excluded、不是已核金融契約**；既有「Pending」標籤**不得自動視作客戶明示處置**。不得把暫緩列一律映射成「無法判定」，也不得把 `threshold_pending` 當全域 Digest 狀態碼（另案 Gate）。
> **標記**：**核**＝客戶明示核准（契約文字）；**暫**＝客戶明示暫緩；**未**＝尚無客戶明示處置（含「記載維持 Pending」但來源〔待核〕、或僅裁示不自動升格者，一律保守歸未）。provenance 照各原 DEC，多為要點轉述〔待核〕。

| 列 | 欄位 | 現況 | 依據 | 適用範圍／未決依賴 |
|---|---|---|---|---|
| R-ID-1 | `fund_code` | **核** | `DEC-2026-11-13-06` | 命名空間與契約文字；Required 升格／New UI2 適用未核；帶後綴落差（D2-A＝B 標示未實作） |
| R-ID-2 | `full_key` | **核** | `DEC-2026-11-22-01` | 僅 Sheet「基金代號」欄取數入口；第 3 項〔目標行為；尚未實作〕、第 4 項〔現況觀察，非規範〕；A0 實作（P1）、NAV 規範（P2）、配息（P3）、S7 其他入口另 Gate |
| R-ID-3 | `ok` | **核** | `DEC-2026-11-22-01` | 同上入口；第 3 項〔目標行為；尚未實作〕 |
| R-NAV-1 | `nav_orig_ccy`（NAV 原幣值；`T-NAV1`） | **核** | `DEC-2026-11-13-06` | 契約文字；Required 升格／New UI2 適用未核 |
| R-NAV-2 | `nav_date` | **核（附註 C）** | `DEC-2026-11-14-07` | 各 provider 日期語意未驗；日期合理範圍僅實作事實；不含 10 日規則、「今天」定義、未來日期、PIT、FX 對齊、1Y `as_of` |
| R-NAV-3 | `fetched_at` | **暫** | `DEC-2026-11-14-07`（B 暫緩） | 依賴 D3(b)＋D7：`stale_after` 逐來源值、NAV 10 日 (a)～(e)、PIT；正式 threshold 客戶裁 |
| R-NAV-4 | `source_tier` | **核** | `DEC-2026-11-17-06`（來源〔待核〕） | 僅 nav 表 `source_tier`；不新增 Provider 欄 |
| R-NAV-5 | `ccy` | **核（附嚴格限制 A）** | `DEC-2026-11-14-07` | 只檢三個 ASCII 大寫字母，≠ ISO 4217 驗證；手填幣別≠獨立證明；不含 `ccy_source`、FX、TWD 換算 |
| R-NAV-6 | `ccy_source` | **未** | `DEC-2026-11-17-06` 記載「維持 Pending」，來源〔待核〕，保守不計為明示暫緩 | 是否進契約欄＝Schema Gate；與 R-NAV-5 成對；FX 閘門（D8）仍關 |
| R-PERF-1 | `fund_code`（重複列＝R-ID-1） | **未** | `DEC-2026-11-13-06` (5)：不因母列核准自動升格 | 是否視同母列待客戶明示 |
| R-PERF-2 | `value_pct`（1Y 含息） | **未** | 舊站已裁（`DEC-2026-10-23-02` 1B），New UI2 未核 | BL-0427／0524／0547 正式公式；不改 350 天 |
| R-PERF-3 | `ccy`（重複列＝R-NAV-5） | **未** | `DEC-2026-11-14-07`：不自動升格 | 同 R-PERF-1 |
| R-PERF-4 | `source`（計算口徑） | **未** | 依附 R-PERF-2 | 隨 R-PERF-2 |
| R-PERF-5 | `window_days` | **未** | 350 天為實作常數，核准依據 NV | BL-0427 窗口定義 |
| R-PERF-6 | `as_of`（重複列＝R-NAV-2） | **未** | `DEC-2026-11-14-07`：不自動升格 | 績效輸出無此欄；不得猜 |
| R-PERF-7 | `status` | **未** | `DEC-2026-11-08-04` Q4：不新增正式詞 | 狀態字彙 D3(a)→契約 |
| R-PERF-8 | `reason`（5 個既有碼） | **未** | 值域核准性 NV | 值域盤點；呈現字另案 |

**計數（逐列重算）**：核 **7**（R-ID-1／2／3、R-NAV-1／2／4／5）；暫 **1**（R-NAV-3）；未 **9**（R-NAV-6、R-PERF-1～8）；合計 17。**結論：首批流程完成判準尚未達成；不得宣告 D2 或首批三域完成，不得據以提 Digest schema。** 要達成，須客戶對上列「未」9 列各自給出明示核准或暫緩（含適用範圍與未決依賴）。列內「依賴」欄僅是記錄，**不是**門檻或公式的建議值。
> 單組作者整理，尚待 Work 非作者差額 QA；上表依據欄多為要點轉述〔待核〕之 DEC，未重驗其來源。

## 9. 2026-11-22 補：九列方案 P 客戶明示暫緩（本節 append-only，§0～§8 一字未改）

> 客戶於 #1296 comment [`7074611352`](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7074611352) 正式選擇方案 P（候選卡 [`7074568235`](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7074568235)）：R-NAV-6 與 R-PERF-1～8 共九列**全部明示暫緩**；正式紀錄見 `docs/DECISIONS.md` 的 `DEC-2026-11-22-03`（獨立於 `-01`、`-02`，互不替代）。**暫緩仍 Pending，非 Excluded**，不作初版金融判讀，不得一律映射「無法判定」，`threshold_pending` 不當全域 Digest 狀態碼。

### 9-1 §8-2 九列狀態更新（§8-2 原表保留為登記當時歷史）

| 列 | 狀態 | 適用範圍（現況） | 未決依賴／保持 Stop |
|---|---|---|---|
| R-NAV-6 | **暫（明示暫緩）** | `provenance[fund_code]` 旁路，不在表欄內；與 R-NAV-5 成對且 R-NAV-5 已明示不含它 | 是否進契約欄＝Schema Gate；FX Gate D8 仍關 |
| R-PERF-1 | **暫（明示暫緩）** | 重複列＝R-ID-1 | 母列已核但「不自動升格」；本列不視同自動核准；不獨立計 |
| R-PERF-2 | **暫（明示暫緩）** | 僅舊站（`DEC-2026-10-23-02` 1B 已裁），New UI2 未核 | BL-0427／0524／0547 公式與窗口；不得改 350 天 |
| R-PERF-3 | **暫（明示暫緩）** | 重複列＝R-NAV-5；績效輸出本身不含 `ccy`，與 D2-B 衝突 | 母列限制 A；不得自行補幣別；不獨立計 |
| R-PERF-4 | **暫（明示暫緩）** | 計算口徑標識，依附 R-PERF-2 | 隨 R-PERF-2，不核公式 |
| R-PERF-5 | **暫（明示暫緩）** | 350 天是實作常數，核准依據 NOT VERIFIED | BL-0427 窗口定義 |
| R-PERF-6 | **暫（明示暫緩）** | 重複列＝R-NAV-2；績效輸出不含此欄 | 不猜資料末端日期；不獨立計 |
| R-PERF-7 | **暫（明示暫緩）** | `ok`／`unavailable` 為現有實作字彙 | D3(a)／(b) 狀態字彙；未核新正式詞 |
| R-PERF-8 | **暫（明示暫緩）** | 既有五碼；`UNAVAILABLE_REASON_TEXT` 屬呈現層 | 值域核准性 NOT VERIFIED，隨 R-PERF-7 |

### 9-2 分類算式（逐列重算）

**7 明示核准**（R-ID-1／2／3、R-NAV-1／2／4／5）＋**10 明示暫緩**（R-NAV-3〔`DEC-2026-11-14-07`〕＋上列九列）＋**0 未明示處置**＝17。**重複列（R-PERF-1／3／6）不自動升格、不獨立計。**

### 9-3 效力與未做

- 本節只是**決策登記**：不核准任何欄位契約文字，不授權公式、10 日或 350 天窗口、NAV freshness、Schema／Digest 欄位／狀態／reason、真來源、Sheet／Secrets／OAuth、NAS／Cloud、Prompt／SDK／Provider、OneBrain runtime、Phase 7、正式網址或上線。
- 依 `DEC-2026-11-22-02` 判準，17 列現況皆有客戶明示處置；**但「首批流程完成」須經 Work 非作者 QA 與總管登記後才成立，本節不自行宣告 D2 完成**；達成後至多取得**另行提出** D2-G2 Digest schema 決策案的資格，不是授權。其餘六域依 G3 延後。
- 單組作者整理，尚待 Work 非作者差額 QA。
