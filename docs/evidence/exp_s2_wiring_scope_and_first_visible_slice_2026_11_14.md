# 🔍 找基金：S2 最小資料接線範圍審核＋第一個可見切片申請（2026-11-14）

> **基準**：main `09227f408932c94b1c278fc99efe9335bc963bc5`（#1245 merge；push CI run `43570786781` success）。docs-only。
> **性質**：**審核稿與申請，不是授權**。S2（`ui_v3` 重用既有 L2 的資料接線）依 `DEC-2026-11-14-04` 須另行審核，S0 通過不自動核准 S2；**未獲授權前不開工、不掛頁、不修改 registry**。不改 `ui_v2`、Old UI、frozen 44、Schema、FX、DG2、公式；BL-0545 BLOCKED；不新增來源／Agent／MCP／付費項目。
> **事實來源**：2026-11-14 兩份獨立唯讀讀碼盤點（L2 契約；`ui_v3` 規範與守衛），皆單組、**未跑任何測試**、「轉紅」類判斷皆 NOT VERIFIED。〔事〕＝讀碼可核；〔推〕＝作者推論；〔Gate〕＝需客戶裁示。檔案引用為「檔案::符號」，不寫行號。
> **品質狀態**：單組作者草稿；非作者 QA（2026-11-14，subagent，三組意見由總管轉述整併，其中各組只能核實自己的那份）對前一版皆回 NEEDS-FIX，本版為依其必修項整併後的修正版，**尚待增量複驗**（依 `DEC-2026-10-16-05`，涉 data semantics 與身份）。
> **標記補充**：〔推〕含「單組讀碼／字面搜尋所得的全稱句」，未經第二組驗證者一律標〔推〕，不標〔事〕。

---

## 一、結論先講

1. **對 🔍 EXP 路徑而言，L2 裡沒有「D2 已核准且可接值」的資料值欄位**〔推：單組讀碼與字面搜尋所得的全稱句，未經第二組驗證；下列兩項已核准內容是〔事〕〕。已核准的只有 R-ID-1（`fund_code`，**僅限 Google Sheet 持倉「基金代號」欄**，明文不含 EXP 選股池代碼）與 R-NAV-1（`nav_orig_ccy`），且 `DEC-2026-11-13-06` 明示**契約文字核准 ≠ 接線授權**；`nav_orig_ccy` 必須與同列 `ccy`、`nav_date` 一起解讀，而兩者（R-NAV-5、R-NAV-2）仍 Pending。（持倉路徑的 `fund_code` 另有用途，不在本稿範圍。）
2. 因此〔推〕今天**唯一同時滿足「不碰 Pending 欄位」「不新增來源／Schema／公式」「有真實行為」**的接線深度是 **T0＝只取選股池代碼，再用既有三態篩選器對代碼做篩選**。它真實但很薄，且 **T0 的 M 恆為 0**（見第四部分）。
3. 要讓下區真正有用（T1：基本資料欄位可篩選），必須先過兩關：選股池代碼命名空間裁示、profile 各欄的 D2 契約。這兩關不是本稿能解的。
4. 〔推〕**今天沒有零 Gate 的可見切片。** 本稿提出**一則請示**（第五部分），它綁定數個明列的決定，不是單一決定。

---

## 二、S2 最小接線邊界

### 2.1 可重用的既有 L2（`ui_v3` 只能在 `adapters/` 層 lazy import `services.v2_tables*`，`services.v2_domain*` 可在模組層）

| L2 | 回傳與狀態〔事〕 | S2-T0 是否使用 |
|---|---|---|
| `exp_universe::load_pool_codes(secret_values, ...)` | dict：`status ∈ {ok, pool_not_cloud, failed}`、`codes`、`message`（已遮蔽但含例外型別名等，**不得上畫面**）、`cooling`；只快取 ok（TTL 1 小時）；失敗冷卻 | **是**（母體） |
| `services/v2_domain/rule_filter::apply_rules_tristate` | 回 `(steps, alive, undet)`；`steps` 為**四元組** `(rule, 套用前, 符合, 無法判定)` | **是**（N／M／EXP-7） |
| `rule_filter::rule_is_effective` | 值去空白後非空才生效 | **是**（定義 `conditions_count`） |
| `fund_keys::resolve_full_keys` | 逐檔 full_key；受 R-ID-2／3 Pending（D2-A=B 已知落差） | **否** |
| `exp_profile::build_profiles` | 基本資料；對三個外部來源發網路；欄位逐欄受 D2 Pending | **否**（T1 才用） |
| `exp_nav::load_nav_dividend` | 淨值／配息；`nav_date`／`ccy`／`fetched_at`／`source_tier` 受 R-NAV-2／3／4／5／6 Pending | **否** |
| `settings_store::load_user_settings` | 讀 `user_setting` | **否**（Q-B＝A：不讀歷史設定當初值） |

### 2.2 欄位分類（T0 之外一律不接值）

| 欄位／功能 | 分類 | 依據 |
|---|---|---|
| 選股池 `code` 字串 | **身份阻擋（部分）**：R-ID-1 明文不含 EXP 路徑；T0 只把它當**不透明字串**顯示與篩選，**不宣稱它是 MoneyDJ 基金代碼或已確認身份** | `DEC-2026-11-13-06` (4)、附三；Q3＝A「身份維持 ◇ 尚未確認」（Q3 原針對上區結果卡，此處為類推，非直接依據） |
| `full_key`／`ok`／`portal` | D2 Pending（R-ID-2／3） | 同上 |
| `fund_name`、`ccy`、`inception_on`、`dividend_policy` | D2 Pending；其中 `inception_on`／`dividend_policy` 作者未找到對應 R- 列 | 盤點；NOT VERIFIED |
| `mgmt_fee_rate_pct` | 恆 `None`（不以最高經理費冒充）→ 真實的「資料未備」來源 | `exp_profile` |
| `nav_date`／`nav_orig_ccy`／`fetched_at`／`source_tier`／dividend 各欄 | D2 Pending；6b 數值接線未核 | `DEC-2026-11-14-02` Q6＝6a |
| `div_ratio_pct` | **非 L2 產物**，算式在 `ui_v2/exp/live.py`；ui_v3 重做＝新增公式；作者推論：配息比屬報酬／績效類，C9 禁顯示未核准此類數值（DEC-02 (8) 未逐字點名此欄） | 盤點；`DEC-2026-11-14-02` (8) |
| 歸一化 NAV、報酬 | L2 無基金版；Q5 Formula Gate | 盤點 |
| 跨幣別合計 | 被阻擋：FX 閘門關、ccy Pending | `DEC-2026-11-13-06` 附三 |

### 2.3 狀態區分（讓取數失敗不會變成「尚未設定條件」）〔S2 必驗〕

adapter 回傳**單一 view model**，其 `state` 為**四個互斥值**；「部分檔無法判定」（M>0）是 `OK` 的附帶旗標，**不是第五個狀態**。`exp0_conclusion` **只有在 `state==OK` 時才被呼叫**：

| state | 來源（L2 事實） | 畫面（只帶原因代碼，不帶原文） | 呼叫 `exp0_conclusion` |
|---|---|---|---|
| `OK` | `status=="ok"` 且 `codes` 非空；`has_undetermined = (M>0)` 為附帶旗標 | 正常；M>0 時文案接「；另有 M 檔無法判定」 | **是** |
| `EMPTY_POOL` | `status=="ok"` 且 `codes==[]`（L2 無獨立狀態，adapter 自行判斷；`_fund_pool` 分頁尚未建立時 L2 亦回空清單，也落在這裡） | 選股池是空的（**不併入「沒有符合」**，字樣待定） | 否 |
| `UNAVAILABLE` | `status=="pool_not_cloud"`（未設定選股池或憑證） | **依請示 (5) 的選擇**：候選 1 `◇ 資料未備`／候選 2 `⛔ 尚未設定：選股池`（作者推薦）／候選 3 `⛔ 取數失敗：…`，見下；皆只帶原因代碼，不帶原文 | 否 |
| `ERROR` | `status=="failed"`（含 `cooling==True`）；**或 adapter 呼叫 L2 時拋出例外**（QA 讀碼：`get_pool_store`、`should_skip_gspread`、`_codes_of` 等在 L2 的 `try` 之外，例外會直接往上拋，不會變成 `failed`）；**或 fail-closed 觸發**（見下） | `⛔ … 取數失敗`＋原因代碼；**原文不上畫面** | **否**（絕不傳 `conditions_count=0`） |

- **fail-closed（必驗）**：adapter 收到 **未知 `status`**，或回傳**形狀不符**（`codes` 不是 list、缺必要鍵、`codes` 含非字串）時，一律轉 `ERROR`，**不得**當成 `OK`、也不得當成「無資料」；日後 L2 新增狀態值時不得落入表外。須有測試鎖定（未知 status、`codes=None`、缺鍵各一）。
- **原因代碼要可區分**（避免把程式錯誤畫成資料取數失敗，參考 `ui_v3/adapters/assets_source.py` 檔頭 (b)「不得 catch-all 後畫成空白或『完整』」的立場）：`ERROR` 的原因代碼至少分「L2 回報失敗（`failed`／冷卻）」「L2 呼叫拋例外」「契約不符（fail-closed）」三類；後兩類除畫面上的原因代碼外，須留遮蔽後的 log，**不得靜默**。畫面文案是否細分屬新字樣（請示 (4)）。
- 「尚未設定條件」**只在 `state==OK` 且生效條件數為 0 時**出現；`UNAVAILABLE`／`ERROR`／`EMPTY_POOL` 即使條件為空也不顯示。
- **零條件時的 EXP-2／EXP-7**：〔推〕與 ui_v2 一致——`matched` 視為空，EXP-2 不列任何檔、EXP-7 無列；此時 L4（列數＝N＋M）不適用（N、M 不展示）。需客戶在 Gate 內確認（第五部分第 (7) 項）。
- **燈色**〔推，並標明未核對處〕：

  | 狀態 | 燈 | 依據 |
  |---|---|---|
  | `OK` 且生效條件數 0 | 灰（「尚未設定條件」） | ui_v2 `conclusion_light` 在 count==0 給灰；44 `EXP-0`：N＝0 灰 |
  | `OK` 且 N>0 | 黃 | 44 `EXP-0` |
  | `OK` 且 N＝0、M>0 | 灰；**無法判定不給紅** | 44 `EXP-0`、客戶要點 |
  | `ERROR` | 紅，文案列出失敗的那一段 | 44 `EXP-0` 取數失敗那一路 |
  | `UNAVAILABLE`（`pool_not_cloud`） | **依請示 (5) 的選擇而定**，見下 | — |
  | `EMPTY_POOL` | **未定**：L2 無此狀態，44 未寫；暫列請示 (4) 新字樣與燈色一併待定 | 作者未找到對應規則，NOT VERIFIED |

- **`pool_not_cloud` 的顯示：三個候選（客戶 Gate 之一，見第五部分 (5)）**：
  1. **`◇ 資料未備`**（作者原擬）：與 `DEC-2026-11-13-06` (6)「確實未提供或未建立來源」語意相近；不亮紅。**與 44 之十二 其二的寫法不同，44 內部對此題並無單一說法（見下）。**（之二十 其四第 4 條對**搜尋區**〔搜尋資料來源目前未核准〕用 `◇ 資料未備`，但同條明文要求不得拿候選清單缺失冒充搜尋來源缺失、兩種缺失各寫各的原因，故**不能直接類推**到選股池，亦不構成對候選 1 的支持。）
  2. **`⛔ 尚未設定：選股池`**：**44 之十二 其二的寫法（非定論，見下）**——第七節第三小節之十二（`DEC-2026-10-19-05`，批次 3-A）其二第 1、2 條：成因是設定沒設（沒有執行取數）→ `⛔ 尚未設定：<哪一項>`，標的探索結論燈改「狀態：尚未設定」、結果清單標題寫 `⛔ 尚未設定：<哪一項>`，不掛取數失敗的原因。〔事：作者 2026-11-14 讀 44 約 4920～4922 行〕此條**晚於**下一個候選所引的登記。
  3. **`⛔ 取數失敗：選股池未設定雲端來源…`**：ui_v2 現行文字（`ui_v2/exp/live.py::TEXT_POOL_NOT_CLOUD`）；44 第七節第三小節之三 其六（2026-10-13，決策者 AI 總管）曾登記「選股池未設定雲端來源該不該從取數失敗拆出、改灰」為**待另案**，並寫燈色與 `EXP-0` 文案照取數失敗那一路。
  - 〔推〕候選 2 是 44 之十二（2026-10-19）的現行寫法，**但 44 內部對此題有張力，不能直接說「不需要新的 amendment」**：同一個「選股池未設定」，之三 其六（約 4331 行，2026-10-13 登記，且該行帶 2026-10-29 `DEC-2026-10-29-06` 加註：候選清單不是找基金的前提，未連接時不得整頁鎖死，本行只屬候選清單自己的狀態、不得冒充搜尋資料來源缺失）與之二十 其四 第 3～5 條（2026-10-29，約 5637～5639 行：候選清單缺時照現行空狀態寫**候選清單自己的原因**，並明言「之三其六登記的分類題照舊待另案」；其六第 4 項把之三 其六選股池未設定那一行列為被 supersede）都比之十二晚，且說法與之十二 其二不完全一致。**作者無法判斷何者優先，須客戶（或獨立規格審查）裁示**；因此請示 (5) 的推薦候選 2 只是作者推論，不得讀成「44 已有定論」。候選 1 與之十二 其二的寫法不同、候選 3 為 ui_v2 現況。
  - **燈的改寫規則出處待查**：之十二 其二第 2 條只寫「燈怎麼改寫照批次 1 已定的規則」，**並未**指向之十二 其一（其一講的是 `EXP-1`／`EXP-2`／`EXP-3` 卡片層級來源與新鮮度改 `⬜ 不適用`，與燈無關；前稿誤指，此處更正）。批次 1 的規則出處施工前須查出，並注意 44 在同區（如 `SET-0` 燈）有過改寫又撤回，候選 2 是否也受影響 NOT VERIFIED。
  - **「整頁鎖死」張力**：之二十 其四第 3 條「候選清單未連接時不得整頁鎖死」；T0 以選股池為母體，母體讀不到時（`UNAVAILABLE`／`ERROR`）下區沒有可調條件。這是母體失敗而非候選清單缺，但是否算「整頁鎖死」需客戶判斷，列入請示 (5) 一併裁示。
  - 候選 2 的字面「尚未設定：選股池」與 S0 的「尚未設定條件」字面相近，呈現層可能混淆（建議，非事實錯誤），字樣屬請示 (4)。
  - **L2 的限制**：`pool_not_cloud` 同時涵蓋「從沒設定」與「憑證已設但格式無法解析（`_sa_present()` 解析失敗回 False）」，L2 **分不出這兩種**；無論選哪個候選，這兩種情境會顯示同一句。這是選擇時要知道的代價。
- 與 ui_v2 的另一個分歧〔事〕：ui_v2 的 `has_rules = bool(rules)`（`saved_only` 時 `settings_error` 為真則規則為空、否則取已存列；非 `saved_only` 時有草稿就用草稿、否則退回已存列；皆不過濾「生效」），S0 的 `conditions_count` 是**生效條件數**（`rule_is_effective` 為真的列數）。分歧情境＝所有條件列值皆空：ui_v2 視為有條件且 N＝全部母體；S0 顯示「尚未設定條件」。**本稿採 S0 定義**，測試須鎖定此差異。
- **條件值正規化**（QA 讀碼）：`rule_is_effective` 對 `value=None` 回 True（`str(None)` 非空），且 `eq`／`ne` 以 `str` 全等比較、**區分大小寫**、不去空白；adapter 組條件時須把 `None` 正規化為 `""`，並明訂輸入前後空白的處理（〔推〕去前後空白後再比對，與 `rule_is_effective` 一致），均需測試鎖定。
- **同一份正規化 rules**：`conditions_count` 與餵給 `apply_rules_tristate` 的條件必須來自**同一份**正規化後的 rules，不得各自處理（否則 `None` 會造成 count＝1 但比對成 `""`）；`field` 白名單僅 `fund_code`、`op` 白名單僅 `eq`／`ne`——放寬到非 `fund_code` 欄位，或放寬到 `gt`／`lt`（遇非數字代碼回無法判定），「T0 的 M 恆為 0」即不成立（`on_or_before`／`after` 為字串比較仍恆可判定，但 T0 不開放）。
- **代碼大小寫**（身份面細節，QA 讀碼）：`load_pool_codes` 只依精確字串去重、大小寫原樣保留，`AB1` 與 `ab1` 在 T0 會是兩列；是否合併屬選股池代碼命名空間待裁問題，T0 不處理。

### 2.4 N／M 型別驗證（不得用 `int()` 掩蓋）

- adapter 的 N／M **只能由 `len()`、計數與整數相減得出**（Python `int`），**禁止**對來源值做 `int(x)` 轉型：`float`、`None`、`bool`、`numpy` 整數一律讓 `require_count` 拒絕（`ValueError`），由 adapter 轉成 `ERROR` 狀態而非靜默截斷。
- 測試條件：傳 `3.0`、`None`、`True`、`numpy.int64` 進 adapter 的計數入口，都必須失敗（不得被轉成 3、0、1）。

### 2.5 EXP-7 末列適配 S0（不改 L2）

- `apply_rules_tristate` 的 `steps` 為四元組 `(rule, 套用前, 符合, 無法判定)`；adapter 取 `[(s[2], s[3]) for s in steps]` 組成兩元素列給 `verify_exp7_last_row`。
- **只在 `state==OK` 且生效條件數>0 時呼叫**；無條件或失敗時 `rows` 為空，不呼叫（空列會 `ValueError`）。
- 不使用 EXP-7 block 的 `before_text`／`after_text`（那是千分位字串，不可解析）。

### 2.5b secrets 取得（施工前補）

- `load_pool_codes` 需呼叫端提供 `secret_values`（**僅供遮蔽**）；ui_v2 用 `services.v2_tables.masking.secret_values([st.secrets, os.environ], ...)`。
- `ui_v3` 的 `adapters/` 不 import `shared.*`。**既有先例是 `ui_v3/adapters/market_page.py::load(sources)`**：由 `ui_v3/app_preview.py::_render_mkt` 把 `[st.secrets, os.environ]` 注入，adapter 內才 lazy import L2。（先前稿引的 `assets_source.py::load` 簽名是 `load(state, secret_values, ...)`，收的是已讀好的秘密值清單，**不是**注入先例，且無 production 呼叫端——此處更正。）
- 「adapter 收 `sources`、內部 lazy import `masking.secret_values(sources)`」在 `ui_v3` **沒有現成先例，是新模式**（可行：`masking` 屬 `services.v2_tables`，adapters 層允許，lazy import 符合 `app_preview` 做法）。
- 選股池的憑證與試算表 ID **不經 `secret_values`**：由 L1 `repositories/pool_repository.py` 透過 `infra.config.get_secret` 自行讀取（`st.secrets`，缺才讀 `os.environ`）。Preview 部署端必須自己放齊（見第五部分先決事實）。

### 2.6 呈現層約束（讀碼所得，S2 施工時必守）

- 失敗原文（`exp_universe.message` 含例外型別名與試算表錯誤文字）**不得進 view model／畫面**（44 P0-①；`no_engineering_leak` 守衛會紅）。
- 「選股池」資料類名、`⬜ 無法判定（資料未備）`、`EMPTY_POOL`、`ERROR` 文案在 `ui_v3` 現有字樣表**沒有**；屬新字樣，已決者（W1、W15、W16、W19 等）走 viewmodel 常數＋「等於核准稿原文」測試，未決者走 `preview_wording` 的 pending 並帶虛線標示。
- 可在 `adapters/` lazy import 的僅 `services.v2_tables*`；`adapters/` **不得 import `shared.*`**；`repositories`／`infra` 不准。

---

## 三、Amendment P1～P4 收斂（本批）

- 依後續指示（使用者帳號訊息，建議性）**X1（之十八其八標題行）擬併入 P2 同節關聯修正**，註記範圍由五處增為六處；**但 X1 納入尚無正式 DEC，必須維持待客戶確認；未確認則仍為五處**。**X2～X6 保留待核，不擴大 frozen 44 修改**。草稿 `exp_amendment_p1_p4_verbatim_draft_2026_11_14.md` 已同步（草稿不具效力）。
- **X2（手機首屏結論燈）列入正式 UI 掛頁前的版面驗收，不得忽略**：驗收落點＝新增 browser（slow）測試，量 390px 寬時 `EXP-0` 燈的 `bottom` 不超過視窗高度、燈在條件輸入區之前、無橫向溢出，並附變異驗證。
  - **重要限制**〔事／推〕：只含下區的最小頁會因「沒有上區」而通過此驗收，**不代表完整頁通過**；完整頁（含上區）做出來時必須重量。
  - **完整頁首屏驗收失敗時的處置**：不得自動放寬 390px 首屏門檻、也不得改驗收條件使其通過；須**另經 Decision Gate**（調整版面，或針對 X2 走 amendment）。X2 不在 P1～P4＋X1 範圍內，故 P1～P4＋X1 的 amendment 完成不等於 X2 已解。
- **逐字註記仍須再一輪針對定稿註記句的獨立 QA 與客戶確認，才能修改 44**；本批 44 零修改。

---

## 四、第一個可見的 New UI2 切片（申請稿）：S2-T0「下區最小頁」

### 4.1 可做 ／ 不可做

| 可做（真實行為） | 不可做（本切片不含） |
|---|---|
| 下區 `EXP-0`：依 S0 文案顯示 N／M／尚未設定條件 | 整個上區（單檔查詢、結果卡、歸一化圖、「比較」）：依賴 D2 R-NAV-2／5 與 Formula Gate |
| `EXP-1` 暫時條件輸入（本次瀏覽、不存檔、不讀歷史 `user_setting`）；**可選欄位僅 `fund_code`**（eq／ne） | `EXP-3`「對照」（需 `nav_date`／`nav_orig_ccy`／`div_ratio_pct`，皆 Pending） |
| `EXP-2` 清單：**只有「選股池代碼」一欄**（欄頭不得寫「基金代碼」以免暗示身份，頁面常駐「身份尚未確認」）；預設依代碼字面值升冪（〔推〕沿用 Q-C 的 deterministic 順序）；列數＝N＋M | **任何其他欄位的占位或值**（`ccy`、`nav_date`、最近淨值屬 6b，`DEC-2026-11-14-04` (6) 已決「暫不預留」；`fund_name`、`inception_on` 等 6a 占位是否適用於 EXP-2 清單無明文，T0 一律不放） |
| `EXP-7` 篩選軌跡（三數；末列＝N、M） | `EXP-4`（欄位勾選與排序）：T0 只有一欄，勾選與排序無意義，**不做假控制項** |
| 四種狀態互斥且原文不外洩 | `EXP-5`、候選清單、`EXP-6`、跨幣別合計、任何報酬／績效／排名語意；`div_ratio_pct` |
| 暫時狀態提示句（W19）、分隔小標題（W15）、頁尾句（W16 第 2 式） | 正式入口、`ui_v2`／Old UI 變更 |

〔推〕T0 **不顯示** `read_at`／`ttl_sec`／`dropped_blank`／`duplicates`（這些是選股池讀取的 lineage／統計，不是資料 as-of，也非本切片需要）；EXP-1 的可選欄位標籤**不得顯示 `fund_code`**（內部必要鍵，畫面用「選股池代碼」）。

〔事〕**T0 的 M 恆為 0**：每個選股池代碼都非空，`fund_code` 條件永遠可判定。所以 `has_undetermined`、`⬜ 無法判定（資料未備）`、EXP-7 的 M 欄在真實頁面上**不會觸發**，只能靠 stub 測試覆蓋。T0 **不能**「端到端驗證 S0 的 M 契約」，只能驗證接線、狀態區分、暫時條件與 N 的計數。

〔推〕**誠實評價**：T0 只能對「代碼字串」做等於／不等於，價值很低。作用是：(1) 驗證 `ui_v3` 接線、四狀態區分、暫時條件與 S0 的 N 路徑；(2) 讓版面與 X2 首屏驗收有真實頁可量。**它不是完整的 🔍 找基金，不得宣稱頁面功能完成**；`registry.py` 的 `registered` 語意是「已有核准 wireframe 且已實作的頁」並引用「不做空殼」，**把缺上區的 T0 設為 `registered=True` 與該語意有張力**，須由客戶明示接受（第五部分第 (1) 項）。

### 4.2 預計修改檔案〔推，未驗；來源：兩份讀碼盤點〕

| 類別 | 檔案 |
|---|---|
| 新增 | `ui_v3/adapters/exp_page.py`、`ui_v3/viewmodels/exp_page.py`、`ui_v3/pages/exp.py`、`tests/ui_v3/exp_stubs.py`、`tests/ui_v3/test_ui_v3_exp_page_{adapter,viewmodel,apptest,browser}.py` |
| 修改（production） | `ui_v3/shell/registry.py`（exp 改 `registered=True`，同時移除 `unregistered_reason`）、`ui_v3/app_preview.py`（加 `_render_exp` renderer）、`ui_v3/adapters/shell_status.py`（exp 的資料狀態來源）、`ui_v3/viewmodels/preview_wording.py`（新字樣） |
| 修改（既有測試；**掛載後會轉紅，須改成預期含 exp，不得放寬或刪斷言**） | `test_ui_v3_page_registry_guard.py`、`test_ui_v3_navigation_shell.py`（多處）、`test_ui_v3_assets_source_import_isolation.py`（**前稿預填清單漏列**）、`test_ui_v3_top_nav_browser.py`（slow，第 3 格由「開發中」變可進連結、頁首可聚焦者變 2 個）；另建議擴充 token／CJK／leak 三個守衛納入 exp 頁 |
| 不得動 | `ui_v2`、`ui/`、`services/`、`repositories/`、Schema、frozen 44、`.github/workflows/` |

### 4.3 資料來源與失敗狀態

- 來源：`exp_universe.load_pool_codes`（讀 Google Sheet 選股池）＋ `rule_filter.apply_rules_tristate`（純計算）。**不新增來源、Schema、公式。**
- 失敗狀態：見 §2.3。**Preview 的先決條件（三者須同時成立，缺一即落 `UNAVAILABLE` 或 `ERROR`，頁面實質是沒有可調條件的失敗頁，等同空殼）**：(a) `google_service_account` 有效（有 `client_email` 且可解析）；(b) `POOL_SHEET_ID` 已設定（現碼無預設值）；(c) 該服務帳戶對目標試算表具備**讀取權限**（否則為 `failed`）。**三者在 Preview 部署端是否成立，皆 NOT VERIFIED**（repo 內查無任何紀錄；亦無法從本環境查證）。施工前須先確認，否則第五部分的 Gate 應改選「暫緩」。

### 4.4 測試、非作者 QA、回滾

- 測試：adapter 純邏輯（stub 餵 L2 輸出，驗 N／M／N＋M、steps→EXP-7、四種狀態互斥、`int` 型別拒絕、原文不外洩、`services.v2_tables` 僅於 `load()` 內載入）；view model 建構驗證；AppTest（調條件後 N／M 改變、不出現「查無基金」「存檔」）；browser（390／768／1280：燈在首屏、DOM 順序、無橫向溢出、離開本頁再回來條件回初始〔L7〕、變異驗證）。
- 非作者 QA 重點：授權（Gate 是否已有客戶明示）；有無假控制項；失敗原文外洩；暫時狀態是否寫入／讀取 `user_setting`；M 不被當成符合／0；既有守衛是否被削弱；燈色對應；新字樣狀態；X2 結論燈是否因無上區而過；選股池代碼不得套用 R-ID-1 契約文字。
- 回滾：單一 PR 一般 merge，`revert` 整個 PR（連同被改的既有測試一起還原）；僅影響 Preview（守衛確保無正式入口引用 `ui_v3`）；暫時狀態不寫持久層，無資料回滾。

---

## 五、需要客戶核准的一則請示（綁定下列項目，並非單一決定）

**AI 總管推薦（先講）：方案 C，但須以「先決事實三項皆成立」為前提；任一不成立則改方案 B。** 另：請示 (5) 推薦候選 2（`⛔ 尚未設定：選股池`，即 44 之十二 其二的寫法；但 44 內部對此題說法不一致，優先序待客戶裁示，不得讀成 44 已有定論），而非作者原擬的 `◇`——見 §2.3。以上為作者推論，客戶可選任一，亦可逐項調整。

**先決事實（只問事實，不需裁示；皆 NOT VERIFIED）**：Preview 部署端同時具備 (a) 有效的 `google_service_account`、(b) `POOL_SHEET_ID`、(c) 該服務帳戶對目標試算表的讀取權限。缺任一項，T0 即落 `UNAVAILABLE`／`ERROR`，等同空殼，此時應選方案 B。

**請示標的（客戶選方案時視同逐項核准，未選者維持不授權）**：

| # | 授權標的 | 說明 |
|---|---|---|
| (0) | **新增檔案與接線**：新增 `ui_v3/adapters/exp_page.py`、`ui_v3/viewmodels/exp_page.py`、`ui_v3/pages/exp.py`；新增測試檔 `tests/ui_v3/exp_stubs.py`、`tests/ui_v3/test_ui_v3_exp_page_{adapter,viewmodel,apptest,browser}.py`（含 slow 的 browser 測試）；`app_preview` 把 secrets 來源注入 adapter；**`ui_v3` 首次從 Preview 讀真實選股池 Google Sheet（即 S2 資料接線本身）** | 前批 DEC 明文不授權新增／修改 tests（S0 除外）與 `ui_v3` 資料接線；本項是核心動作，不得被「視同逐項核准」模糊帶過 |
| (1) | 把 `exp` 掛入 Preview 導覽（`registry.py` 設 `registered=True`），並明示接受「缺上區的不完整頁」與 `registered` 語意（「已有核准 wireframe 且已實作的頁」、不做空殼）的張力 | 掛頁、registry 變更目前皆不在任何 DEC 的授權內 |
| (2) | `app_preview.py` 新增 `_render_exp`、`shell_status.py` 新增 exp 狀態來源、`preview_wording.py` 新增字樣條目 | 同上 |
| (3) | 修改 4 支既有測試（只把 exp 加進預期，**不放寬、不刪斷言**）：`test_ui_v3_page_registry_guard.py`、`test_ui_v3_navigation_shell.py`、`test_ui_v3_assets_source_import_isolation.py`、`test_ui_v3_top_nav_browser.py`，並建議擴充 token／CJK／leak 三守衛納入 exp 頁 | 前批 DEC 明文不授權新增／修改 tests（S0 除外） |
| (4) | 新字樣：「選股池」資料類名、`EMPTY_POOL`／`ERROR`（含三類原因）文案與燈色、欄頭「選股池代碼」、常駐「身份尚未確認」等 | 擬字，未決者維持 Pending（頁面帶虛線標示），不因本請示升格；`EMPTY_POOL` 的 44 規則本稿未找到 |
| (5) | **`pool_not_cloud` 的顯示語意（Gate）**：候選 1 `◇ 資料未備`／候選 2 `⛔ 尚未設定：選股池`／候選 3 `⛔ 取數失敗：…`（詳 §2.3） | 作者推薦候選 2（44 之十二 其二的寫法）；**44 內部對此題說法不一致**（之十二 其二 vs 之三 其六 2026-10-29 加註、之二十 其四第 3～5 條），優先序作者無法判斷，**須客戶裁示，不得讀成 44 已有定論**；並含「整頁鎖死」張力（之二十 其四第 3 條，母體讀不到時下區沒有可調條件）；候選 1 與之十二 其二的寫法不同、候選 3 為 ui_v2 現況。L2 無法區分「未設定」與「憑證格式錯誤」 |
| (6) | 選股池代碼僅作不透明字串顯示與篩選、不宣稱身份、不套 R-ID-1 | 命名空間仍另案 |
| (7) | 零條件時 EXP-2 不列任何檔、EXP-7 無列（與 ui_v2 一致） | 見 §2.3 |

| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| A　核准 S2-T0（(0)～(7)） | 依 §4 施工，獨立 PR、非作者 QA、exact-head CI | 最早有可見頁；驗證接線、狀態區分、X2 首屏；範圍最小 | 價值薄（只能篩代碼、M 恆為 0）；需改 4 支既有測試與 registry；先決條件未驗則等同空殼 | 中：先決條件未驗；被誤讀為「🔍 頁面完成」 |
| B　暫緩，先裁選股池代碼命名空間與 profile 欄位的 D2 契約，再做 T1 | 不做 T0 | 一次做出有用的頁；不產生薄頁 | 時間較長；D2 其餘列與命名空間仍待客戶 | 低 |
| C　核准 A，並同時另開選股池代碼命名空間裁示 | A＋平行推動 B 的前置 | 不浪費等待時間；T0 接線可被 T1 直接擴充 | 同時兩條線，客戶多做一個裁示；**繼承 A 的全部風險** | 中（不低於 A） |

不屬本請示、仍擋著：Q5 Formula Gate、R-NAV-2／5、EXP-6、BL-0545。frozen 44 的 amendment（P1～P4；X1 待確認）另走原 Gate，與本請示互不阻擋，但**完整頁（含上區）掛頁前必須完成**；X2 首屏驗收失敗另需 Gate（見 §三）。

---

## 六、我沒有驗證的部分

1. 兩份盤點皆為單組讀碼：L2 契約、守衛轉紅判斷、`ui_v3` 層規則、「ui_v3 無 text_input／multiselect 先例」等**未實跑任何測試**；`AppTest` 在 `st.navigation` 下切頁、Streamlit 切頁後 `session_state` 清除行為未驗證。
2. Preview 的三項先決條件（有效 `google_service_account`、`POOL_SHEET_ID`、服務帳戶對試算表可讀）：皆未驗證。
3. `inception_on`／`dividend_policy` 是否有對應 D2 R- 列：未找到，非「確定沒有」。
4. 空池在 `ui_v2/exp/page.py` 是否另有處理：單組字面搜尋。
5. 預填檔案與轉紅測試清單可能仍有遺漏；全稱句（「L2 沒有 D2 已核准且可接值的欄位」「ui_v3 沒有 text_input 先例」）皆單組搜尋，**未經第二組驗證，不得引用為已查證事實**。
6. 新字樣的核准狀態（W 各項）未逐一對照；批次 1 的燈改寫規則出處（前稿誤指之十二 其一）、`EMPTY_POOL` 的對應規則未讀。
7. 非作者 QA 於 2026-11-14 對前一版（head `215f117d`）的意見（由總管轉述，各組只能核實自己的報告）已整併；**修正版尚待增量複驗**。
8. 44 之三 其六、之十二 其二、之二十 其四 對「選股池未設定」的張力：作者無法判斷優先序，屬客戶裁示。
9. 本稿單組作者草稿，尚待非作者獨立 QA。
