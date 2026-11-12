# D2 資料契約核准準備：Required 17 列逐列清單（2026-11-12）

> **本檔是「核准準備」，不是客戶裁示、不是核准欄位、不是授權施工。** 基準 `origin/main` `d82a711d3bb7f4939952bdebae1441e99a8704f5`（#1225 merge）；產生日 2026-11-12（Asia/Taipei）。
> **單組作者（專案 AI 研究作者）；尚待非作者獨立 QA。** 方法為唯讀讀碼＋讀文件＋字面 `git grep`；**未執行任何測試**（「有測試」＝測試檔存在且斷言可讀，不是跑綠；是否綠只能由 CI 驗）、未連網、未碰憑證與 Sheet。
> **現行事實不變**：D2 正式核准欄位數＝**0**（`DEC-2026-11-11-04` D2-G1）；本檔不新增 Schema、provider、資料來源、金融公式、門檻，亦不提議任何程式施工。
> 文中「推薦／擬議」一律是**總管讀法，可被客戶推翻**；A／B／C 方案是為了縮短客戶決策而擬的問法，**不是已核准選項**。
> 缺值／無法判定一律寫「⬜ 資料未取得／無法判定」，**不得讀成 0 或正常**（`PROJECT_RULES.md` §13.1）。路徑一律「檔案::符號」，不寫行號。全稱句（「0 命中」「只有 N 處」）皆為**單組字面 grep、未經第二組驗證**，指令見附錄 A。

---

## 0. 結論先行

1. **D2 逐列待審表（候選檔末節）為 17 列，去除 3 組重複後是 14 個不同欄位**（身份 3、NAV 6、績效 5 個獨立欄；`R-PERF-1／3／6` 分別重複 `R-ID-1`／`R-NAV-5`／`R-NAV-2`）。列數與編號與候選檔一致，**未增刪列**。
2. **沒有任何一列在 D2 層級已核准**。最新相關正式 DEC 是 `DEC-2026-11-11-04`（核准欄位數＝0）；其後唯一晚於它的 `DEC-2026-11-12-01` 僅調整優先序，其「影響範圍」明寫**不修改 D2 Required 審核**。掃 `docs/DECISIONS.md` 全檔，未找到更新的 D2 欄位核准。
3. **「部分核准」只有 5 列，而且核准的都是相鄰事項，不是 D2 欄位本身**：`R-ID-1`（命名空間＋契約文字方向）、`R-PERF-1`（同上，重複）、`R-PERF-2`／`R-PERF-4`／`R-PERF-8`（`DEC-2026-10-23-02` 1B 的舊站算法範圍）。其餘 12 列＝未核准。
4. **證據成熟度**：17 列中 14 列「有 code＋有測試」，但**其中 `R-PERF-2／4／5／7／8` 只存在於舊站（`ui_v2`／`ui_v3`／`services/v2_tables`／`services/v2_domain` 對 1Y 含息函式 0 命中）**；`R-PERF-3／6` 在 1Y 輸出**根本沒有該欄**（無 code）；`R-ID-1` 的 D2-A＝B 格式檢查**僅有文件、production 無輸出**。
5. **本輪新發現（候選檔與昨日稽核都沒有）**：
   - **N1**：`services/fund_service.py::calc_metrics` 建 1Y 窗口時有**非量測的估算／預設值路徑**（例外時 `window_days`＝365；日期跨度不足或解析失敗時用 `len(s)×1.4` 估跨度），且只有 stderr print、無旗標、現有測試未鎖。見 `R-PERF-5`。屬 §1 Fail Loud 疑慮，**讀碼推得、未實跑、不是結論**。
   - **N2**：候選檔末節把「與 D2-B 衝突」套用到 NAV 域的 `nav_date`／`ccy`，**比 `DEC-2026-11-09-01` D2-B 的字面更嚴**（D2-B 的標題與內容是「1Y 含息證據欄位」）。結果同為 Pending，但**會改變要問客戶的問題**。見 §4 Q0。
   - **N3**：三種不同的「source」並存（1Y 的 `source`＝計算口徑標籤、NAV 的 `source_tier`＝表類別且 nav 列恆為「淨值」、`provenance.source`＝資料供應者），契約若不分名會互相誤讀。
   - **N4**：`ok` 旗標只表示「代碼通過解析鏈」，**不代表基金存在、也不代表取得 NAV**，候選檔的「區分沒取到與沒有這檔」描述不準。
6. **建議的客戶裁示順序**見 §4（總管讀法）：先裁 `R-ID-1`＋`R-NAV-1`（證據最強、不涉公式與 FX）→ 再問一題「D2-B 射程」（Q0，可解鎖 NAV 域 4 個欄位）→ S7（解鎖 `full_key`／`ok`）→ 最後才是 1Y 含息（綁 BL-0427）。

---

## 1. 權威鏈與讀法（逐列「是否已有核准」依此判定）

### 1.1 判定規則

- 「已核准」＝有客戶裁示（DEC）**明文核准該欄位進入 D2 正式契約**。目前 0 列符合。
- 「部分核准」＝有客戶裁示核准**該欄位的某個範圍**（例如命名空間、舊站算法），但 D2 契約列入 Required 仍未核准。**要點轉述的裁示一律標明，客戶可推翻。**
- 「未核准」＝只有候選／相鄰裁示，或僅有 frozen UI SSOT 的表欄位規格（那不是 D2 核准）。
- 依 `DEC-2026-11-11-04`：每列須核對既有 DEC、正式契約、New UI2 適用範圍；**未明確核准、證據不足或有衝突者維持 Pending**。

### 1.2 上位決策與它「核准了什麼／沒核准什麼」

| 決策／文件 | 與 D2 的關係 | 沒核准的事（對本檔的限制） |
|---|---|---|
| `DEC-2026-11-11-04`（D2-G1／G2／G3；ChatGPT 轉達要點，非逐字） | G1＝B 修正版：逐列審核、不得整欄升格、**核准欄位數＝0**；G2＝A：D2 逐域契約與 Digest schema 是兩個獨立 Gate；G3＝A：首批只限基金身份、NAV、績效 | 任何正式契約欄位升格、Digest schema、其餘六域、`DG2_SHADOW_ENABLED`、改 NAV source precedence、FX 開閘、動 BL-0545 |
| `DEC-2026-11-12-01`（最新 DEC；要點轉述） | 優先序：資料／契約優先、New UI2 安全部分並行 | 「影響範圍」明寫不修改 D2 Required 審核、FX Gate、金融契約；不授權 Schema／provider／來源／公式／門檻 |
| `DEC-2026-11-09-01` D2-A＝B／D2-B＝收緊後 C／D2-C＝B | D2-A：Sheet「基金代號」欄契約文字（標示違反、保留原值、不改寫），**尚未實作**；D2-B：`as_of`、幣別**不直接列為新 Required**，須四項同源證據（身份取數鍵一致、NAV 序列與計算一致、日期幣別來源可追溯、無未解釋衝突）同時成立才可當 1Y 含息的同源證據；D2-C：只收既有 `mapping_source` 作追溯，別名表內容與 `page_type` 不升格 | 1Y 含息算法延伸至 New UI2、BL-0427、窗口起訖日／取得時間／算法版本（維持 Pending）、補欄任何施工 |
| `DEC-2026-11-08-05`（報酬 A／身份 A／持倉占比 C） | 三類 Required／Optional／Excluded／Pending 為**作者候選，逐類核可前不具效力** | 1Y 含息跨新版適用仍需正式核准；標準化代碼升格；補欄 |
| `DEC-2026-11-08-04`（Q1–Q5） | Q4：缺資料沿用「資料未備／無法判定」，不新增「過期／衝突」正式詞、不改門檻；Q5：FX 閘門關閉，非台幣可整理原幣，不得整檔判不可用 | **不直接核准** `ok`／`unavailable` 兩值（候選檔 R-PERF-7 已引） |
| `DEC-2026-11-08-02`（D1 方案 C、FX 閘門關、D3(a)） | 資料契約先行；`FX_OBS_DATE_RULE_VERIFIED` 維持 `False` | D2 逐域契約與 Digest schema 未核准、D3(b)／D7 |
| `DEC-2026-10-23-02` 1B（要點轉述，落地範圍限舊站 `services/`、`ui/`，**不改 `ui_v2/`**） | 1Y 含息唯一算法＝配息還原淨值法；官方值只對帳；資料不足顯示「資料未備／無法判定」，不得 fallback 為純 NAV／0／中性／估算 | 對 New UI2 契約是否適用**未定**；BL-0427 公式層五題 |
| `DEC-2026-10-28-05`、`DEC-2026-10-29-01`／`-03`（身份，客戶裁示；原文逐字存檔於 `docs/evidence/decisions/`） | Sheet「基金代號」欄＝MoneyDJ 基本代碼命名空間（只限該欄）；基金身份與持倉身份分開；Unknown 不猜；後綴只在已驗證 mapping 命中才視為通路資訊；shadow flag 預設關 | Stage-2（啟用 resolver 影響任何鍵或顯示）須另一次 Gate；ISIN 非 canonical key |
| `DEC-2026-11-05-03`（NAV 10 日規則） | 既有實作事實保留、**不得升格**為正式全頁產品規則 | 待決 (a)台灣日期、(b)跨頁範圍、(c)未來日期 NAV、(d)`>` 或 `>=`、(e)擁有者位置 |
| `DEC-2026-11-07-03`（BL-0545 唯讀探針） | 主分組鍵沿用 `resolve_full_keys`；canonical 僅作平行差異 | live Active Sheet、stale／conflict 門檻、正式准入 |
| `docs/v2/44_fund_ui_ssot.md` §4.2（frozen UI SSOT） | 定義 `nav` 表七欄（`fund_code`、`nav_date`、`nav_orig_ccy`、`ccy`、`source_tier`、`is_estimated`、`fetched_at`）；測試 `tests/test_v2_tables_nav_dividend.py::test_契約_nav與44逐欄相同_source_tier值域相同` 鎖 `contract.NAV_FIELDS` 等於 44 §4.2 | **這是 UI 資料表規格，不是 D2 核准**；44 凍結（`DEC-2026-10-27-02` 僅有限解凍五頁頁序等） |
| `PROJECT_RULES.md` §13.1／§4 | Missing 不得轉成 0／中性／HOLD／安全／未觸發；停下條件含 data identity、正式公式、正式 threshold | — |

### 1.3 名詞對照（避免同名 G 編號混用）

| 名詞 | 指什麼（出處） |
|---|---|
| D2-G1／G2／G3 | `DEC-2026-11-11-04` 的三項 D2 Gate 裁示 |
| D2-A／D2-B／D2-C | `DEC-2026-11-09-01`：格式檢查／1Y 含息證據欄位／別名來源。⚠️ `docs/v2/82` 多處用「D2-C」指「類別占比契約延後」（出自 `DEC-2026-11-08-05` 持倉占比 C），**與此處 D2-C 不同**（見 §5 項 9） |
| 題一／題二／題三 | 候選檔「下一批最值得核准事項」三題，分別對應 D2-A／D2-B／D2-C |
| 稽核 G1–G13 | `docs/evidence/ui_data_contract_audit_2026_11_12.md` §5；與 D2 直接相關者：**G8**（D2 首批逐列核可＋ISIN＋🔍 wireframe）、G4（新鮮度門檻）、G6（NAV 10 日規則）、G11（FX 閘門） |
| D1–D10、D3(a)／(b)、D7 | `docs/evidence/onebrain_decision_gate_route_and_risk_check_2026_11_08.md`；D3(b)＝`stale_after`／conflict 判定、D7＝NAV 10 日跨頁語意 |
| S7、K11／K12 | 候選檔第二部（`full_key` 可否帶通路後綴／別名表／頁型） |

---

## 2. 17 列逐列清單

> 每列八項：①列／欄位／面向 ②欄位與金融語意 ③目前資料來源 ④驗證證據及缺漏 ⑤Missing／Unavailable 處理 ⑥是否已有核准 ⑦所需客戶 Decision Gate ⑧若核准後的最小實施範圍（**僅 D2 契約文件層**）。
> 「Preview」＝`ui_v2` 預覽路徑（`app.py` 不 import `ui_v2`／`ui_v3`，非正式入口、Cloud 已驗＝NOT VERIFIED）。

### 2.1 身份域（3 列）

#### R-ID-1｜`fund_code`

| 項 | 內容 |
|---|---|
| ① | 身份域；原列 K1／A1 A1；績效域 `R-PERF-1` 與其重複 |
| ② | 基金代碼字串；Sheet「基金代號」欄固定為 MoneyDJ 基本代碼命名空間，**只限該欄**（`DEC-2026-10-29-01` 第 1 項）。為 `nav`／`dividend`／`fund_profile` 列鍵（`nav` 主鍵＝`fund_code`＋`nav_date`，44 §4.2）。無單位、**無日期語意**（身份鍵沒有 as_of）。基金身份≠保單持倉身份（`DEC-2026-10-29-01` 第 2 項）。不是 ISIN、不是通路後綴碼 |
| ③ | 使用者 Active Sheet「基金代號」欄 → `ui_v2/{alo,exp,hld}/source.py` → `services/v2_tables/fund_keys.py::resolve_full_keys`；列契約 `services/v2_tables/contract.py::NAV_FIELDS`（字串、不可空）。**Preview live；`ui_v3` 未接線（`git grep` 0）；Old UI 另有自己的代碼處理，不是本欄的產出者** |
| ④ | 有測試：`tests/test_v2_tables_nav_dividend.py::test_契約_nav與44逐欄相同_source_tier值域相同`（`NAV_FIELDS`＝44 §4.2）、`tests/test_v2_tables_fund_keys.py`（44 個 `def test_`，讀碼計數）。**缺漏**：D2-A＝B 要求的「違反欄位契約須標示、原值保留」**production 無任何輸出**——`sheet_code_contract_violation` 字面只出現在 `services/fund_identity.py`、`services/fund_identity_shadow.py`、`shared/fund_identity.py`（皆 shadow）；`log_shadow_for_fund_keys` 簽名無 `input_source` 參數（無法證明輸入取自該欄）；`DG2_SHADOW_ENABLED = False`。讀碼，未跑 |
| ⑤ | 空字串／None／非字串→該列不寫（`contract._fields_problems`）；`resolve_full_keys` 解析失敗→`ok=False`、`full_key=None`、帶 `error`，**不截斷、不猜、不補值**。違規輸入（網址／後綴／格式異常）依 D2-A＝B 應「標示＋保留原值」，**目前未實作，契約須明標此落差** |
| ⑥ | **部分核准**：(i) 命名空間——`DEC-2026-10-29-01` 第 1 項、`-03` 第 1 項；(ii) 契約文字方向——`DEC-2026-11-09-01` ①(1) D2-A＝B（僅契約文字、**尚未實作**）。**列入 D2 Required：未核准**（`DEC-2026-11-11-04` D2-G1） |
| ⑦ | 稽核 **G8**（D2 逐列核可）。擬議 A＝核可為身份域 Required，並在契約同列明標「格式檢查尚未實作」；B＝先不核可，待 D2-A＝B 實作另授權後再審；C＝不列 Required，只當 join key。**推薦 A**（證據最強、不涉公式；總管讀法，可推翻） |
| ⑧ | 候選檔末節 `R-ID-1`「本次狀態」改記核准日與 DEC 編號（舊句劃線保留）；`docs/DECISIONS.md` 登記一筆；契約文字附「格式檢查尚未實作」。**不啟用 DG2 Shadow、不改 resolver／consumer、不改 Sheet schema** |

#### R-ID-2｜`full_key`（`resolve_full_keys` 輸出）

| 項 | 內容 |
|---|---|
| ① | 身份域；原列 K2／A1 A2 |
| ② | MoneyDJ 取數用鍵字串。處理鏈（`fund_keys.py` 檔頭）：非 ASCII 先擋→`strip`→`upper`→`parse_moneydj_input`→別名表→最終 `_is_pure_code`，格式 `PURE_CODE_PATTERN`＝主碼 3–30 碼大寫英數＋可選 `-` 後綴 2–20 碼。`portal` 恆為空字串。無日期語意。**現行會接受通路後綴**：`tests/test_v2_tables_fund_keys.py::test_mapping_miss_passes_through` 釘住 `acdd01-eqtal005`→`ACDD01-EQTAL005`（即 S7）。**注意同名欄有兩個產出者**：Old UI／L1 的 `repositories/fund/fund_orchestration.py` 另自行產 `result["full_key"]`，規則與本函式不同（`fund_keys.py` 檔頭自列差異，如少 `canonicalize_moneydj_url`），契約須指明以哪個為準 |
| ③ | `services/v2_tables/fund_keys.py::resolve_full_keys`；呼叫者：`services/v2_tables/{exp_profile,settings_store}.py`、`ui_v2/{alo,exp,hld}/source.py`、`scripts/bl0545_coverage_probe.py`；`app.py`／`ui/`／`ui_v3` 0 命中（附錄 A-1）。別名表＝`repositories/fund/sources.py::_DEFAULT_MAPPING`（讀碼計 12 筆）＋可選 `fund_code_mapping.csv`（`git ls-files` 無此檔；部署端有無＝NOT VERIFIED）。**Preview live** |
| ④ | 有測試：`tests/test_v2_tables_fund_keys.py`（與 L1 正則同構、非 ASCII、網址 `a=` 各變體、別名表注入、兜底不截斷）。**缺漏**：S7 未裁；不同部署別名表→同輸入可得不同 `full_key`；`DG2` canonical 仍 shadow、production consumer 0；真實 Active Sheet 覆蓋率 NOT VERIFIED（BL-0545）。讀碼，未跑 |
| ⑤ | 失敗→`ok=False`、`full_key=None`、中文 `error`；不補值、不猜。下游「資料未備」字樣由呈現層決定（本檔不判符號，D3(a)） |
| ⑥ | **未核准**。相鄰裁示：`DEC-2026-11-09-01` D2-C＝B（別名內容與 `page_type` 不升格、僅 `mapping_source` 追溯）；`DEC-2026-10-29-01` 第 4 項（Sheet 欄遇後綴須標違反）與現行行為並存 |
| ⑦ | **S7**（`full_key` 可否帶通路後綴；關聯 `DEC-2026-10-29-01` 第 4 項、BL-0521(h)、BL-0527 第 5 項）；稽核 G8。擬議 A＝契約如實描述「現行接受後綴，為已知缺口」並核可；B＝契約規定 `full_key` 不得帶後綴（**新行為、屬 data identity 規則＝Stop Gate，且需改程式**）；C＝維持 Pending 待 S7 先裁。**推薦 C 起手**（先問 S7，再回頭核可本列；總管讀法） |
| ⑧ | 若 S7 選 A：本列改「已核准（含已知缺口註）」＋登記 DEC；若選 B：D2 文件層只記規則，**實作屬另案程式施工，不在本檔範圍**。均不改別名表、不新增 ISIN／share class mapping |

#### R-ID-3｜`ok`（`results[].ok`）

| 項 | 內容 |
|---|---|
| ① | 身份域；原列 K3 |
| ② | 布林：**該輸入是否通過解析鏈並得到合格 `full_key`**。⚠️ **不等於基金存在、不等於取得 NAV**（`fund_keys.py` 不取數）。候選檔 K3 描述的「區分沒取到與沒有這檔」不準確（N4），契約應改述為「代碼可解析／不可解析」 |
| ③ | 同 `R-ID-2` |
| ④ | 測試同 `R-ID-2`（`r["ok"] is True／False` 斷言散見 `tests/test_v2_tables_fund_keys.py`，如 `test_fallback_is_error`）。缺漏：`ok` 與下游「資料未備」的對映無契約文件 |
| ⑤ | `ok=False`→`full_key`／`portal` 為 None、`error` 有字串；**不得因 `ok=False` 補預設鍵** |
| ⑥ | **未核准**（無專屬 DEC） |
| ⑦ | 隨 `R-ID-2`（S7）；稽核 G8。擬議：與 `R-ID-2` 同批問，不單獨核可 |
| ⑧ | 隨 `R-ID-2`；同時把語意註改為「僅表示代碼可解析」 |

### 2.2 NAV 域（6 列；候選檔註明 NAV 域在本檔無獨立 Required 候選，由 A1 草案「必備」歸併而來——該歸併讀法可被客戶推翻）

#### R-NAV-1｜`nav_orig_ccy`

| 項 | 內容 |
|---|---|
| ① | NAV 域；原列 A1 B1 |
| ② | 當日單位淨值，**原幣／單位**，浮點，大於 0，不可空（44 §4.2）。**無 TWD 欄**；不改寫、不換算；公式：無（來源值 `float()` 後原樣）。日期語意由 `nav_date` 帶 |
| ③ | A 鏈 `services/moneydj_fetcher.py::auto_fetch_moneydj`→`services/v2_tables/nav_dividend.py::build_nav_table`（**每次開頁即時抓、不持久化**，稽核 §1.2 引客戶 2026-10-13 Q-A）；列契約 `contract.NAV_FIELDS`。**Preview live**（`ui_v2/alo/{live,source}.py`、`ui_v2/hld/{live,source}.py`）；`ui_v3` 0 命中 |
| ④ | 有測試：`test_nav_零與負淨值不寫`、`test_nav_全NaN_一列都不寫_理由寫明`、`test_nav_部分NaN_只略過那幾筆_不ffill`、`test_nav_週末與假日沒有列_不補列`、`test_小修4_4_溢位數值不寫_理由寫明`（皆 `tests/test_v2_tables_nav_dividend.py`）；黃金檔 `tests/test_nav_table_golden_c3a.py`、`tests/test_nav_dividend_golden_c3a.py`。**缺漏**：各 NAV adapter 的 live 可達性 NOT VERIFIED；舊 UI 另有第二條淨值路徑（`get_latest_nav`，引 `docs/v2/69` G-NAV-3，未重驗）；`NAV_HISTORY_PROVENANCE_VERIFIED = False` 使累積點不讀。讀碼，未跑 |
| ⑤ | 非有限／非正／布林／溢位→該筆不寫；同日有無效值整天不寫；同日不同值全不寫；**週末假日不補列、不 ffill、不補 0**；整檔無列→呈現層「資料未備」 |
| ⑥ | **未核准**。相鄰：`DEC-2026-11-08-04` Q5（非台幣可整理原幣）；44 §4.2 frozen 表規格（非 D2 核准） |
| ⑦ | 稽核 G8；無額外 Gate。**不得推及 TWD 換算**（G11／`DEC-2026-11-08-02` FX 閘門關）。擬議 A＝核可為 NAV 域 Required（僅原幣、明寫無 TWD 欄）；B＝暫不核可；**推薦 A** |
| ⑧ | 候選檔末節本列改已核准＋DEC 登記；契約字面註「原幣、無 TWD 欄、FX 閘門維持關閉」。不新增 schema |

#### R-NAV-2｜`nav_date`

| 項 | 內容 |
|---|---|
| ① | NAV 域；原列 A1 B2；`R-PERF-6`（as_of）與其同源 |
| ② | 日期；該筆淨值對應的日期（44 §4.2）＝**來源序列的資料日**，不是抓取日、也不是公布日（T+1～T+3 的發布延遲沒有進入欄位）。邊界：早於 1900-01-01 或晚於「台灣今天」（UTC+8）不寫。**PIT 取哪一欄未定**（`docs/v2/67`§5.3 引） |
| ③ | 來源序列索引→`nav_dividend.py::_dated`／`_date_bounds_reason`。Preview live；`ui_v3` 未接線 |
| ④ | 有測試：`test_3_nav_date未來或1900以前不寫_台灣當日照收`、黃金檔。**缺漏**：舊 UI 純量 `nav_date` 與序列末日不同源、無 reconcile（G-NAV-6，引）；`alo` 的 `assemble_nav` 無未來日期防線（`DEC-2026-11-05-03` 事實 (3)，稽核推論，本組未重驗）；NAV 10 日規則待決 (a)–(e) |
| ⑤ | 無日期／非日期→該筆不寫；整檔無列→呈現層「資料未備」；**不以 `fetched_at` 或今天代替** |
| ⑥ | **未核准**。候選檔標「與 D2-B 衝突」——見 N2／§4 Q0（D2-B 字面是 1Y 含息證據，是否也約束 NAV 域本身，**未裁**） |
| ⑦ | **Q0**（D2-B 射程）＋ `DEC-2026-11-05-03` (a)–(e)（稽核 G6）＋ 新鮮度門檻（稽核 G4／D3(b)／D7）。擬議 A＝只核「資料日」欄位定義，不含新鮮度門檻、不含 PIT 取欄；B＝維持 Pending，待 D7 一併裁；C＝核可並同時裁定 PIT 取 `nav_date`。**推薦 A（若 Q0 選「D2-B 僅約束 1Y 證據」），否則 B** |
| ⑧ | 若 A：本列改已核准（僅欄位定義）＋DEC；契約註「不含新鮮度、不含 PIT、不含 10 日規則」。**不新增 10 日門檻、不改 `NAV_NOT_READY_DAYS = 10`** |

#### R-NAV-3｜`fetched_at`

| 項 | 內容 |
|---|---|
| ① | NAV 域；原列 A1 B3 |
| ② | 世界協調時間（UTC，ISO 8601）的**取得時間**。取值依來源：即時列＝序列 `attrs["fetched_at"]`；A 鏈序列缺此屬性時改取 A 鏈的 `chain_started_at`（`_nav_from_chain`，程式註解自述「命中快取時是原本那一次的時間，不是當下」；來源記在 `provenance.chain.fetched_at_from`）；退回預存舊序列＝`attrs["cache_updated_at"]`（**語意變成「預存檔寫入時間」，不是本次取得**）；累積表點＝`recorded_at`（閘門關，不採）。缺／無時區／晚於當下超過 300 秒（`FETCHED_AT_MAX_FUTURE_SEC`）→整批不寫，不以當下補 |
| ③ | `nav_dividend.py::_fetched_at_check`。Preview live；`ui_v3` 未接線 |
| ④ | 有測試：`test_nav_fetched_at取不到或沒有時區_整批不寫_不以當下時間補`、`test_3_fetched_at晚於當下_整批不寫_代碼與理由正確`、`test_nav_預存舊序列_fetched_at改取cache_updated_at_stale照記`、`test_小修1_nav即時那一支_fetched_at未來容差`。**缺漏**：300 秒容差是否為客戶核准門檻 NOT VERIFIED；`stale_after` 值未裁（`docs/v2/67` §8.5、D3(b)）；預存退回時「取得時間」語意改變，契約若收須標 |
| ⑤ | 取不到→整批不寫（`withheld`＝`fetched_at_missing`／`fetched_at_in_future`），**不以讀取當下時間冒充**（D2-B 同向） |
| ⑥ | **未核准**。相鄰：`DEC-2026-11-09-01` D2-B（不以讀取時間冒充 `fetched_at`） |
| ⑦ | Q0＋新鮮度門檻（稽核 G4／D3(b)）。擬議 A＝核可欄位定義（UTC、取得時間、預存退回時取 `cache_updated_at` 須標），門檻另案；B＝維持 Pending 待 D3(b)。**推薦 B**（預存退回語意與新鮮度綁在一起，單獨核可易被誤讀為「資料新鮮」） |
| ⑧ | 若 A：本列改已核准＋DEC，契約註明語意分三種來源；**不新增 stale 狀態詞、不定門檻** |

#### R-NAV-4｜`source_tier`（表欄）／`provenance[fund_code].source`（旁路）

| 項 | 內容 |
|---|---|
| ① | NAV 域；原列 A1 B4 |
| ② | `source_tier`：字串，值域四個（淨值／配息／市場指標／其他，44 §4.2，客戶 2026-09-23 補值域）；**`nav` 列恆為「淨值」**（`nav_dividend.py` 唯一賦值處 `"source_tier": SOURCE_TIER_NAV`），所以它只標「表類別」，**不辨識供應者**。供應者在旁路 `provenance[fund_code]`：`source`（L1 `attrs["source"]`）與 A 鏈那一支的 `chain.data_source`（採用來源）、`cache_fallback`、`stale`、`latest_from`，皆不在表欄內。與 1Y 的 `source`（`R-PERF-4`）是**不同東西**（N3） |
| ③ | `nav_dividend.py`、`contract.SOURCE_TIER_VALUES`。Preview live |
| ④ | 有測試：`test_契約_nav與44逐欄相同_source_tier值域相同`、`test_nav正例_逐欄照44_幣別取持倉手填_provenance記來源`。**缺漏**：供應者名稱進契約的規則未核准；`provenance.source` 直接取 `attrs.get("source")`，`_rows_from_segment` 未對它設閘，**缺值不阻止寫列**（讀碼；`chain.data_source` 缺值是否阻擋＝NOT VERIFIED）→ 列層沒有供應者保證 |
| ⑤ | `source_tier` 不在值域→該列不寫；`provenance.source` 缺→旁路欄為 None，**不補名稱** |
| ⑥ | **未核准**（`source_tier` 值域是 44 的規格，非 D2 核准） |
| ⑦ | 稽核 G8。擬議 A＝只核 `source_tier`（表類別）；B＝同時核旁路 `provenance.source`（不進表欄）；C＝全 Pending。**推薦 A**（B 會牽動「供應者缺值不阻擋寫列」是否可接受，屬新問題；供應者名稱入契約規則須客戶裁；**不得因此新增 provider**） |
| ⑧ | 若 A：本列改已核准（註明「恆為淨值、不辨識供應者」）。**不新增 `source` 欄、不改 NAV source precedence** |

#### R-NAV-5｜`ccy`

| 項 | 內容 |
|---|---|
| ① | NAV 域；原列 A1 A9／K13；`R-PERF-3` 與其重複 |
| ② | 計價幣別，ISO 4217（44 §4.2）。取值：來源自報優先，否則持倉手填；**去空白大寫化後意思不同→整檔不寫（`ccy_conflict`）；缺→`ccy_missing`；不預設 USD**（`DEC-2026-10-28-05`）。currency 與 share class 分開。⚠️ 驗證是**形狀檢查**（三個大寫英文字母，`contract._is_iso_4217`；`CNH` 之類通過），**不驗是否在 ISO 4217 清單**；比對僅字串（無別名收斂，如 `人民幣` 與 `CNY` 不相等；`P-CNHALIAS-1` 登記於 `EXCEPTIONS.md`，屬舊站 `comparable_ccy`，與此檢查是否同源 NOT VERIFIED） |
| ③ | `nav_dividend.py::resolve_nav_ccy`／`_chain_ccy_gate`。Preview live |
| ④ | 有測試：`test_nav_幣別缺_整批不寫_不猜不預設USD`、`test_nav_持倉幣別不合ISO4217_不改大小寫_整批不寫`、`test_nav_同一檔多列持倉幣別互相不同_整批不寫`、`test_必修2_格式不對但意思不同_判衝突`；`tests/test_unknown_currency_fail_closed_20261010.py`。**缺漏**：契約寫 ISO 4217 但驗證只有形狀；非原生報價來源未宣告幣別一律擋（`TEXT_CCY_NON_NATIVE_UNDECLARED`）→真實覆蓋率 NOT VERIFIED |
| ⑤ | 缺／衝突→該檔淨值整批不寫→呈現層「資料未備」；**不補 USD**。Q5：非台幣基金不得整檔判不可用——此處整檔不寫是因「幣別不明」，不是因「非台幣」，契約須分清 |
| ⑥ | **未核准**。相鄰：`DEC-2026-10-28-05`（currency／share class 分開、不預設 USD）、`DEC-2026-11-08-04` Q5、D2-B（四項同源證據） |
| ⑦ | Q0＋稽核 G8。擬議 A＝核可為 NAV 域 Required，並如實標「驗證為形狀檢查」；B＝維持 Pending，待 D2-B 四項同源證據逐項證明；C＝核可並要求改為清單驗證（需程式，另案）。**推薦 A 或 B 視 Q0**（Q0 選「D2-B 僅約束 1Y」→A；選「也約束 NAV 域」→B） |
| ⑧ | 若 A：本列改已核准＋DEC；契約註「形狀檢查、無清單驗證、無別名收斂」。**不改 `ccy` 驗證碼、不補 share class** |

#### R-NAV-6｜`ccy_source`（`provenance[fund_code].ccy_source`）

| 項 | 內容 |
|---|---|
| ① | NAV 域；原列 A1 A10／K14 |
| ② | 字串；標示幣別是誰說的：`source_reported`（來源自報）／`holding_user_input`（持倉手填）等（`nav_dividend.py::_RESERVED_CCY_SOURCES`、`LABEL_SOURCE_HOLDING`）。**旁路 provenance，不在 44 §4.2 表欄內**；若要「進契約欄」即牽涉新欄位位置，不在本檔授權（不增加新 Schema） |
| ③ | `nav_dividend.py::resolve_nav_ccy`。Preview live |
| ④ | 有測試：`test_nav正例_逐欄照44_幣別取持倉手填_provenance記來源`、`test_nav_來源自報幣別優先記出處_與持倉相同照寫`。缺漏：是否進契約欄未定 |
| ⑤ | 幣別整批不寫時，`ccy_source` 為 None（無幣別即無出處）；不補 |
| ⑥ | **未核准** |
| ⑦ | 隨 `R-NAV-5`；稽核 G8。擬議：與 `R-NAV-5` 同批；以「契約只描述其存在、位置維持旁路」為限 |
| ⑧ | 本列改已核准（旁路欄）＋DEC；**不新增表欄、不改 44** |

### 2.3 績效域（8 列；範圍僅「1Y 含息報酬」輸出，詳見 §5 項 2）

#### R-PERF-1｜`fund_code`（績效視角）

| 項 | 內容 |
|---|---|
| ① | 績效域；原列 #1；**與 `R-ID-1` 重複，不獨立計** |
| ② | 同 `R-ID-1`。⚠️ **`resolve_1y_total_return` 的輸出 dict 沒有 `fund_code`**（輸出鍵僅 `value_pct／status／reason／source／window_days／div_count_in_window／official_1y_pct／label`），它是呼叫端 fund 物件的 join key，不是績效輸出欄 |
| ③ | 舊站 fund 物件；New UI 路徑無 1Y 輸出（附錄 A-2） |
| ④ | 同 `R-ID-1` |
| ⑤ | 同 `R-ID-1`；無法掛到基金→結論只能「⬜ 資料未取得／無法判定」 |
| ⑥ | **部分核准**（同 `R-ID-1`） |
| ⑦ | 隨 `R-ID-1` |
| ⑧ | 隨 `R-ID-1`；契約註明為 join key |

#### R-PERF-2｜`value_pct`（1Y 含息報酬）

| 項 | 內容 |
|---|---|
| ① | 績效域；原列 #2 |
| ② | 百分點，`round(,2)`；公式＝配息還原淨值法 `(adj_end/adj_start−1)×100`（`fund_service.py::calc_metrics` 內；Adj_NAV＝NAV×累積因子，因子＝1＋配息/當日 NAV）；**原幣**、無 TWD 換算、不年化、不外推。窗口：列數≥252 取倒數第 252 列到末筆；<252 列且跨度≥30 天取整段。「1Y」名義下**窗口天數可大於一年**（稀疏序列，BL-0427 (4)）。日期語意：窗末＝序列最後一筆淨值日（**輸出不帶**）。離譜值（>150% 或 <−95%）值照回、僅在 `label` 加警語。必須收**解析後的** `value_pct`，不是原始鍵 `ret_1y_total`（原始鍵繞過 350 天門檻，候選檔 §3 第 2 點） |
| ③ | `services/fund_total_return.py::resolve_1y_total_return` ← `services/fund_service.py::calc_metrics`。消費者僅舊站：`services/{ai_service,fund_service,portfolio_service}.py`、`services/fund_grp_health/quality.py`、`services/health/{dividend,report}.py`。**`ui_v2`／`ui_v3`／`services/v2_tables`／`services/v2_domain` 0 命中**（附錄 A-2）。**舊站 live；New UI 未接線** |
| ④ | 有測試：`tests/test_compute_1y_total_return.py`（16 個 `def test_`）、`tests/test_ssot_1b_total_return_adr_eating.py::test_a_synthetic_series_restored_return_adr_and_eating_band`（與獨立重算 `_restored_expectation` 對拍，容差 0.01）、`tests/test_pr1a_audit_fixes.py`。**缺漏**：BL-0427 (1)(2)(3)(4)(5)＋BL-0524 公式／窗口／口徑未裁；同基金多套「1Y」並存（G-RET-2，引）；New UI 無對應輸出；`calc_metrics` 窗口有非量測路徑（N1，見 `R-PERF-5`）。讀碼，未跑 |
| ⑤ | `status="unavailable"`→`value_pct=None`、`label`＝`⬜ 資料未備／無法判定（原因）`；**不補 0、不退純 NAV、不外推、不以官方值頂替**（1B；測試 `test_official_perf_1y_never_used_as_value_even_when_present`、`test_pure_nav_ret_1y_is_never_used`、`test_nav_series_is_never_annualized_or_extrapolated`） |
| ⑥ | **部分核准**：算法唯一性、官方值只對帳、資料不足顯示⬜——`DEC-2026-10-23-02` 1B，**僅舊站範圍**。D2／New UI2 延伸：**未核准**（`DEC-2026-11-08-05` ①(1)、`DEC-2026-11-09-01` D2-B 末句明寫不代表延伸） |
| ⑦ | 稽核 G8＋BL-0427／BL-0524（formula Gate，D6 data gap）。擬議 A＝客戶先確認「1B 延伸至 New UI2 資料契約」，**契約同列明標 BL-0427 五題未決**；B＝延伸並同時裁 BL-0427（公式層，須獨立稽核）；C＝不延伸，D2 績效域維持 Pending。**推薦 A**（先裁延伸，公式題不綁在欄位核可上；總管讀法）。⚠️ A 等於把「已知公式層缺陷未裁」的算法放進契約，必須逐字標註 |
| ⑧ | 若 A：本列改「已核准（延伸範圍：D2 契約文字；公式層 BL-0427 未決）」＋DEC。**不改 350、不改公式、不新增 New UI 呼叫（接線屬 UI／接線 Gate）、不補欄** |

#### R-PERF-3｜`ccy`（報酬計價幣別）

| 項 | 內容 |
|---|---|
| ① | 績效域；原列 #3；**與 `R-NAV-5` 重複**（同源） |
| ② | 說明 `value_pct` 為原幣百分比（非 TWD 報酬）。**1Y 輸出沒有此欄**（無 `ccy` 鍵，附錄 A-3）；幣別只能取自 NAV 表同基金的 `nav.ccy`。D2-B 規定用 NAV 幣別當 1Y 證據須四項同源證據同時成立 |
| ③ | 輸出無；來源＝`nav.ccy`（`R-NAV-5`） |
| ④ | **無 code（輸出端）、無測試**。缺漏＝整個欄位；舊站 `calc_metrics` 不使用 `ccy`，故幣別缺時 1Y 仍可算出（與新版 nav 表整批不寫的行為不同） |
| ⑤ | 契約若要求而輸出無→⬜ 無法判定；**不自行補幣別** |
| ⑥ | **未核准** |
| ⑦ | Q0＋D2-B 四項同源證據；稽核 G8。擬議：隨 `R-NAV-5`；A＝維持 Pending，待四項證據；B＝列為「由 NAV 同基金 `ccy` 提供、契約註明來源」（正是 D2-B 收緊前的舊推薦 C，**已被客戶收緊，不建議重提**）。**推薦 A** |
| ⑧ | 維持 Pending：D2 文件層最小動作＝在契約註明「1Y 輸出無幣別欄」缺口；**不補欄** |

#### R-PERF-4｜`source`（計算口徑標識）

| 項 | 內容 |
|---|---|
| ① | 績效域；原列 #4 |
| ② | 字串：有值＝`自算（還原含息淨值）`（`SRC_SELF_RESTORED`）、無值＝`—`（`SRC_NONE`）。**語意是「這個數字怎麼算的」，不是資料供應者**，與 NAV 的 `source_tier`／`provenance.source` 不同（N3，契約須分名）。舊標籤常數（`SRC_OFFICIAL`、`SRC_SELF_ANNUALIZED` 等）相容保留、已不產出（crosswalk M2） |
| ③ | `services/fund_total_return.py`。舊站 live；New UI 未接線 |
| ④ | 有測試：`test_restored_value_is_the_only_source`、`test_official_perf_1y_never_used_as_value_even_when_present`。缺漏：值域雖只有 2 個，但辨識函式（`is_*_1y_source`）以字串判斷，依賴 label 文字穩定 |
| ⑤ | 無值→`—`（不是空字串、不是 0） |
| ⑥ | **部分核准**：1B 禁令「純 NAV／外推不得掛含息名」（`DEC-2026-10-23-02`，舊站）；欄位進 D2：未核准 |
| ⑦ | 隨 `R-PERF-2`（1B 延伸）。擬議：與 `R-PERF-2` 同批 |
| ⑧ | 隨 `R-PERF-2`；契約註「口徑標識≠供應者」 |

#### R-PERF-5｜`window_days`（`ret_1y_window_days`）

| 項 | 內容 |
|---|---|
| ① | 績效域；原列 #6 |
| ② | 整數日曆天；列數≥252：倒數第 252 列淨值日到末筆的天數；<252 列且跨度≥30 天：整段跨度；否則不建窗。門檻 `RET_1Y_RESTORED_MIN_WINDOW_DAYS = 350`（`shared/signal_thresholds.py`；**核准依據 NOT VERIFIED**；`DEC-2026-11-11-04` 明禁改）：<350→`window_short`；有值但窗口缺→`window_unknown`。D2-B：**不由 `window_days` 推測窗口起日** |
| ③ | `services/fund_service.py::calc_metrics`→`resolve_1y_total_return`。舊站 live；New UI 未接線 |
| ④ | 有測試：`test_short_window_is_unavailable_not_a_partial_value`、`test_restored_value_without_window_days_is_window_unknown`（`tests/test_pr1a_audit_fixes.py`）、`test_a_synthetic_series_…`（正常路徑 `window_days ≥ 350`）。**缺漏 N1（讀碼，未實跑，NOT VERIFIED）**：`calc_metrics` 有非量測路徑——(i) 計算窗口天數例外時 `_window_actual_days = 365`，且 `_window_actual_days or 365`（0 天也變 365）；(ii) 日期跨度<7 天或索引解析失敗時 `_days_span = max(int(len(s) * 1.4), 14)` 以估算值當跨度，可成為 `ret_1y_window_days`；列數 250～251 時估算值 350～351 恰能過 350 門檻。這些路徑只有 stderr `print`、無旗標、現有測試未鎖（`tests/*.py` 內 `ret_1y_window_days` 的斷言未見針對 365 預設或 ×1.4 估算；附錄 A-4）。發生機率可能很低，**但屬 CLAUDE.md §1「禁止自行估一個合理值」疑慮**，修法屬公式層、不在授權內，只登記。另 BL-0427 (3)(4)：日頻序列恆 unavailable／350 只是下限擋不住稀疏序列 |
| ⑤ | `window_short`／`window_unknown`→⬜；窗口未建→`None`（非 0） |
| ⑥ | **未核准** |
| ⑦ | BL-0427 (3)(4)＋350 的核准依據＋N1 是否另案查證；稽核 G8。擬議 A＝核可為「報酬涵蓋日曆天數（診斷用，不作窗口起訖證據）」並標 BL-0427 (3)(4)；B＝維持 Pending；C＝核可並要求輸出窗口起訖日（需程式，另案）。**推薦 B**（N1 與 BL-0427 未解，且 D2-B 已禁止由它推起日） |
| ⑧ | 維持 Pending：文件層最小動作＝在契約註記「N1 未查證、350 依據 NOT VERIFIED」。N1 的獨立查證（讀碼＋實跑）建議另派獨立組，**本檔不判、不修** |

#### R-PERF-6｜`as_of`（資料末端日期）

| 項 | 內容 |
|---|---|
| ① | 績效域；原列 #8；**與 `R-NAV-2` 重複**（同源） |
| ② | 1Y 數字「截至哪一天」＝窗末最後一筆淨值日。**`resolve_1y_total_return` 輸出沒有此欄**（附錄 A-3）；NAV 列有 `nav_date`。`docs/v2/67` §8.6 的「as_of 為 Required 例」是 **Digest 層**文件（欄位群「不是 schema」，且 D2-G2 明定 Digest 另一個 Gate），**不應作為 D2 核准依據** |
| ③ | 輸出無；來源＝`nav_date`（`R-NAV-2`） |
| ④ | 無 code（輸出端）、無測試。缺漏＝整個欄位 |
| ⑤ | 契約若要求而輸出無→⬜ 無法判定；**不自行補資料末端日期、不用 `fetched_at` 代** |
| ⑥ | **未核准** |
| ⑦ | Q0＋D2-B 四項同源證據；稽核 G8。擬議：隨 `R-NAV-2`；A＝維持 Pending；B＝列為「由 NAV 同基金 `nav_date` 提供」（舊推薦，已被客戶收緊）。**推薦 A** |
| ⑧ | 維持 Pending：文件層註記「1Y 輸出無 as_of 欄」。**不補欄** |

#### R-PERF-7｜`status`（`ok`／`unavailable`）

| 項 | 內容 |
|---|---|
| ① | 績效域；原列 #10 |
| ② | 二值字串：`ok`／`unavailable`（`resolve_1y_total_return`）。全站另有四～五套狀態詞並行（稽核 §1.8；`shared/ui_semantics/rules.py`、`ui_v3/viewmodels/common.py` 等），**與本二值的對映未裁**（D3(a) crosswalk M1 收錄的是 `SRC_*` 顯示標籤，並說明舊站字面把「資料未備」與「無法判定」並成一句、New UI2 規則表分成 ◇／⬜ 兩符號；`status` 二值本身是否在對照表內＝NOT VERIFIED，本組未讀完 M 組全文） |
| ③ | `services/fund_total_return.py`。舊站 live |
| ④ | 有測試：`tests/test_compute_1y_total_return.py` 各案斷言 `status`。缺漏：狀態字彙歸 D3(a)／(b)，不在欄位核可內決定 |
| ⑤ | `unavailable`＝⬜ 資料未取得／無法判定，非 0 |
| ⑥ | **未核准**（`DEC-2026-11-08-04` Q4 管字樣、**明確不直接核准兩值**） |
| ⑦ | D3(a)／(b) 狀態字彙（OneBrain D3）。擬議 A＝D2 契約不採此二值為契約狀態字彙，只描述「有值／無值＋原因」，字彙交 D3；B＝採二值；C＝維持 Pending。**推薦 A**（避免在 D2 偷渡狀態字彙） |
| ⑧ | 本列改記「由 D3 決定」；**不新增狀態詞（Q4）** |

#### R-PERF-8｜`reason`（缺漏原因碼）

| 項 | 內容 |
|---|---|
| ① | 績效域；原列 #11 |
| ② | **只會輸出 5 種**：`no_series`、`no_restored_value`、`window_short`、`window_unknown`、`dividend_data_missing`。`dividend_data_missing_unaligned` 只是文字鍵（`UNAVAILABLE_REASON_TEXT` 共 6 鍵），`reason` 仍是 `dividend_data_missing`（`_unavailable(..., text_key=...)`）。白話原因屬呈現層 |
| ③ | `services/fund_total_return.py::_unavailable`。舊站 live |
| ④ | 5 種碼各有測試：`no_series`（`test_all_missing_is_no_series`）、`no_restored_value`（`test_official_only_without_restored_value_is_unavailable`、`test_non_numeric_restored_value_is_unavailable_not_ok`）、`window_short`、`window_unknown`（`tests/test_pr1a_audit_fixes.py`）、`dividend_data_missing`（`test_dividend_fund_with_zero_dividends_in_window_is_unavailable`）。**缺漏**：crosswalk M1 只列 3 種（`no_series`／`no_restored_value`／`window_short`），與實際 5 種不符（見 §5 項 10） |
| ⑤ | 有值時 `reason=None`；無值時必有 5 種之一，**無「未知原因」預設** |
| ⑥ | **部分核准**：1B「資料不足→資料未備／無法判定」（`DEC-2026-10-23-02`，舊站）；原因碼值域本身：未核准 |
| ⑦ | 隨 `R-PERF-7`（D3）。擬議：與 `R-PERF-7` 同批 |
| ⑧ | 隨 `R-PERF-7`；同步更正 crosswalk M1 的原因碼列表屬文件修正（不改碼） |

---

## 3. 總覽（a）：17 列

| 列 | 語意類別 | 證據成熟度 | 核准狀態 | 主要阻擋 Gate |
|---|---|---|---|---|
| R-ID-1 `fund_code` | 身份鍵 | 有 code＋test（欄位）；D2-A＝B 格式檢查僅文件 | 部分核准（命名空間＋契約文字方向） | 稽核 G8；D2-A 實作另授權 |
| R-ID-2 `full_key` | 取數鍵 | 有 code＋test（Preview） | 未核准 | S7（`DEC-2026-10-29-01` 第 4 項 vs 現行行為） |
| R-ID-3 `ok` | 解析旗標 | 有 code＋test | 未核准 | 隨 R-ID-2（語意須改述，N4） |
| R-NAV-1 `nav_orig_ccy` | 淨值（原幣） | 有 code＋test | 未核准 | 稽核 G8（單純；FX 不涉） |
| R-NAV-2 `nav_date` | 日期（資料日） | 有 code＋test | 未核准 | Q0；`DEC-2026-11-05-03` (a)–(e)／G6／D3(b)D7 |
| R-NAV-3 `fetched_at` | 日期（取得時間） | 有 code＋test | 未核准 | Q0；G4／D3(b)（`stale_after`） |
| R-NAV-4 `source_tier`／`provenance.source` | 來源 | 有 code＋test（tier）；供應者僅旁路 code | 未核准 | 稽核 G8（供應者名入契約須客戶裁） |
| R-NAV-5 `ccy` | 幣別 | 有 code＋test | 未核准 | Q0；D2-B 四項同源證據 |
| R-NAV-6 `ccy_source` | 幣別出處 | 有 code＋test（旁路） | 未核准 | 隨 R-NAV-5 |
| R-PERF-1 `fund_code` | 身份鍵（重複） | 輸出端無此欄（僅呼叫端 join key） | 部分核准（同 R-ID-1） | 隨 R-ID-1 |
| R-PERF-2 `value_pct` | 報酬值 | 有 code＋test（僅舊站） | 部分核准（1B 舊站算法） | 1B 延伸＋BL-0427／BL-0524 |
| R-PERF-3 `ccy` | 幣別（重複） | **無**（輸出無此欄） | 未核准 | 隨 R-NAV-5＋D2-B |
| R-PERF-4 `source` | 計算口徑 | 有 code＋test（僅舊站） | 部分核准（1B 禁令，舊站） | 隨 R-PERF-2 |
| R-PERF-5 `window_days` | 窗口 | 有 code＋部分 test（N1 路徑無測試） | 未核准 | BL-0427 (3)(4)；350 依據；N1 查證 |
| R-PERF-6 `as_of` | 日期（重複） | **無**（輸出無此欄） | 未核准 | 隨 R-NAV-2＋D2-B |
| R-PERF-7 `status` | 狀態 | 有 code＋test（僅舊站） | 未核准 | D3(a)／(b) 狀態字彙 |
| R-PERF-8 `reason` | 缺漏原因 | 有 code＋test（僅舊站） | 部分核准（1B 缺值表述，舊站） | 隨 R-PERF-7 |

統計：部分核准 5 列、未核准 12 列、**D2 層級已核准 0 列**；「無 code（輸出端）」2 列（`R-PERF-3`、`R-PERF-6`）；「僅文件」的子項 1 個（D2-A 格式檢查）。

---

## 4. 建議的客戶裁示順序（b）（**總管讀法，可被客戶推翻**）

| 順序 | 問什麼 | 涵蓋列 | 為何排在這裡 |
|---|---|---|---|
| 1 | **逐列核可 `R-ID-1`＋`R-NAV-1`**（各附明標落差：格式檢查尚未實作／無 TWD 欄） | R-ID-1、R-PERF-1、R-NAV-1 | 證據最強（有 code＋test）、不涉公式與 FX、核可後 D2 才有第一批非 0 的欄位，也能演練逐列流程 |
| 2 | **Q0：D2-B 的射程**——D2-B「`as_of`、幣別不直接列 Required」是否**只**約束「1Y 含息輸出引用 NAV 日期／幣別當證據」（A），還是**也**使 NAV 域自己的 `nav_date`／`ccy`／`fetched_at` 須先通過四項同源證據才可列 Required（B）？推薦 A（D2-B 標題與內容是「1Y 含息證據欄位」，且 NAV 表欄位已在 frozen 44 §4.2；但候選檔末節現行讀法接近 B，**需客戶確認**） | R-NAV-2、R-NAV-3、R-NAV-5、R-NAV-6、R-PERF-3、R-PERF-6 | 一題可決定 4 個獨立欄位走向；且不涉公式。選 A 後可逐欄核可（`R-NAV-3` 仍建議等 D3(b)） |
| 3 | **S7：`full_key` 可否帶通路後綴** | R-ID-2、R-ID-3 | 唯一擋 `full_key`／`ok` 的問題；B 方案屬 identity 規則（Stop Gate），先問才知道是否需要程式施工 |
| 4 | **R-NAV-4**：只核 `source_tier`（表類別）或同時核旁路供應者 | R-NAV-4 | 低風險但需客戶明示「供應者名稱入契約」的規則；可與 2 同批 |
| 5 | **1B 是否延伸至 New UI2 資料契約**（公式題 BL-0427 不綁在欄位上，但契約須標未決） | R-PERF-2、R-PERF-4、R-PERF-8 | 最大、最接近公式層；與 BL-0427／BL-0524 同源，故最後 |
| 6 | **狀態字彙與 N1**：`status`／`reason` 的字彙歸屬（D3）；N1 是否另派獨立查證 | R-PERF-7、R-PERF-5 | 依賴 D3(a)／(b)、BL-0427，屬外部依賴最多的兩列 |

不建議在 D2 階段同時問的事：FX 開閘、NAV 10 日規則 (a)–(e)、Digest schema（D2-G2 已明定另一個 Gate）、其餘六域（D2-G3 延後）。

---

## 5. 與昨日稽核（`docs/evidence/ui_data_contract_audit_2026_11_12.md`）§1／§5 及相鄰文件的不一致或需更正（c）

> 以下皆為單組讀碼／讀文件所得，**未經第二組驗證**；建議由非作者 QA 複驗後再決定是否修文。本檔**不改**任何既有檔。

| # | 位置 | 內容 | 性質 |
|---|---|---|---|
| 1 | 稽核 §1.3「代碼→MoneyDJ `full_key`（production 主鍵）」；`DEC-2026-11-07-03` 亦用「production」 | `resolve_full_keys` 在 `app.py`／`ui/`／`ui_v3` **0 命中**（附錄 A-1），只被 `ui_v2` 預覽、`services/v2_tables`、探針呼叫；Old UI 的 `full_key` 由 `repositories/fund/fund_orchestration.py` 另行產出。故「production」在此指「L2 v2 路徑」，**不是正式入口**。建議改寫為「L2 v2 路徑的取數鍵（Preview）」 | 措辭／範圍 |
| 2 | 稽核 §1.8、§3.2 D2、§5 G8「17 列 Pending」 | 17 列含 3 組重複＝14 個不同欄位（候選檔統計表有、稽核未提）；且績效域 8 列**只涵蓋 1Y 含息輸出**，A1 草案 C 區的價格報酬 `return_pct`、回撤、波動、窗口/期間（C1～C3、C8）**不在 17 列內**，而 D2-G3 的「績效」範圍比 17 列大 | 範圍 |
| 3 | 稽核 §1.7 引 BL-0427 | 稽核列 4 項（低估、窗不同、日頻恆 unavailable、日期口徑）；BL-0427 實有五題，漏列 (4) NAV 稀疏窗口（350 只是下限）。對應 `R-PERF-5` | 引用不全 |
| 4 | 候選檔末節 `R-NAV-2`／`R-NAV-5`「與 D2-B 衝突」 | D2-B 字面是「1Y 含息證據欄位」；套用到 NAV 域本身的 `nav_date`／`ccy` 是更嚴的讀法（N2）。狀態同為 Pending，但改變 §4 Q0 | 讀法差異 |
| 5 | 候選檔 K3／`R-ID-3` | `ok` 不代表基金存在或有 NAV（N4） | 描述不準 |
| 6 | 候選檔 `R-NAV-4`「`source_tier`（有值域）」 | nav 列恆為「淨值」，不辨識供應者；供應者缺值不阻止寫列（N3） | 補充 |
| 7 | 候選檔 `R-PERF-4`／NAV 域 | 三種「source」同名異義（N3） | 命名風險 |
| 8 | 候選檔 `R-PERF-5`（及稽核 §1.7） | 未提 `calc_metrics` 的非量測窗口路徑（N1） | 新發現（待獨立查證） |
| 9 | `docs/v2/82` 多處「D2-C」（13 處字面） | 82 用「D2-C」指「類別占比契約延後」；`DEC-2026-11-09-01` 的 D2-C 是「別名來源＝B」。類別占比延後出自 `DEC-2026-11-08-05` 持倉占比 C。是否同指＝NOT VERIFIED（作者意圖不明） | 命名重疊 |
| 10 | `docs/evidence/data_state_vocabulary_crosswalk_d3a_2026_11_08.md` M1 | `reason` 只列 3 種，函式 docstring 與實作是 5 種 | 文件過期 |
| 11 | `DEC-2026-11-09-01` ② | 稱 `mapping_source`「出自身份解析的 provenance（Shadow 路徑），不是每筆輸出都帶」；實際 `fund_keys.py::resolve_full_keys` 每次呼叫都回 `provenance.mapping_source`（**每次呼叫一個，不是每筆一個**），非 shadow 專屬 | 事實措辭（不影響 D2-C 裁示本身） |
| 12 | 稽核 §5 G8 | 推薦「先逐列審 D2 Required 17 列」成立；但未標依賴順序（見 §4）。無衝突 | 補充 |

**稽核與本檔一致、已重驗成立者**（留痕）：`nav` 表七欄且無 `source` 欄；`DG2_SHADOW_ENABLED = False`；D2-A＝B 尚未實作；`DIV_DATE_IS_EX_DATE_VERIFIED = False`；`NAV_HISTORY_PROVENANCE_VERIFIED = False`；`NAV_NOT_READY_DAYS = 10`；`FX_OBS_DATE_RULE_VERIFIED = False`；`sources.py` 內 `_src_*` 函式 25 個；TDCC 在 NAV 瀑布僅有 `_src_tdcc_meta`；New UI 路徑 1Y 含息 0 引用；預存舊序列退回時 `fetched_at` 取 `cache_updated_at`。

---

## 6. 盲點與未讀範圍（d）

1. **未跑任何測試**；本檔所有「有測試」＝測試檔存在且斷言可讀。CI 狀態與依賴齊全環境下是否綠 NOT VERIFIED。
2. **字面 grep 的限度**：附錄 A 的「0 命中」皆不含別名、動態組字、字串內嵌 import、非 `.py` 檔；不得讀成「全 repo 只有這幾處」。
3. **未讀／只讀頭部**：`docs/v2/44`（僅 §4.2）、`docs/v2/69`（G-NAV／G-RET 皆「引」）、`docs/v2/70`（僅經候選檔引用）、`docs/v2/82`（僅 grep 「D2-C」）、`docs/v2/67`（僅 §8.6 Required 例）；`d2_draft_A2`（持倉／配息，D2-G3 延後範圍）、`d2_draft_B`（僅經 C 引用）全文未讀；`probe/moneydj-nav-results` 分支未取得（無網路）；`services/v2_tables/{exp_nav,exp_profile,settings_store}.py` 僅 grep；`ui_v2` 各 consumer 僅 grep；`services/health/**`、Old UI `ui/**` 未讀。
4. **N1／N2／N3／N4 皆為單組讀碼推得**：N1 未實跑（建議另派獨立組讀碼＋實跑，且不得由本組自查）；N2 是文件讀法差異，需客戶確認；N3／N4 是命名／語意描述，低風險。
5. **DEC 多為要點轉述**（ChatGPT／總管轉達，非逐字，客戶可推翻）；`DEC-2026-10-28-05`／`-10-29-01` 原文逐字存檔於 `docs/evidence/decisions/`，本組只讀 `DECISIONS.md` 摘要，**未開逐字檔**（摘要與逐字檔若有出入以逐字檔為準）。
6. **真實資料／Cloud／Active Sheet 覆蓋率**一律 NOT VERIFIED（BL-0545 維持唯一全域 NEXT，合法輸入未提供）。
7. **「部分核准」的判定是作者讀法**：把相鄰裁示（命名空間、1B 舊站範圍）算作「範圍內部分核准」可被客戶推翻；若客戶認為這些不算，則 17 列全部＝未核准，不影響其餘結論。
8. 本檔是單組作者產出，**尚待非作者獨立 QA**；依 `PROJECT_RULES.md` §8，涉及 data identity／formula 語意的內容（`R-ID-2`、`R-PERF-*`）合併前至少需 1 組真正獨立稽核。

---

## 附錄 A：全稱句的驗證指令與輸出（repo 根目錄；基準 `d82a711d`；單組、未經第二組驗證）

| # | 指令 | 輸出 |
|---|---|---|
| A-1 | `git grep -n "resolve_full_keys" -- app.py ui ui_v3 \| wc -l` | `0` |
| A-1b | `git grep -ln "resolve_full_keys" -- '*.py'`（非測試部分） | `scripts/bl0545_coverage_probe.py`、`services/fund_identity.py`、`services/fund_identity_shadow.py`、`services/v2_tables/{exp_profile,fund_keys,settings_store}.py`、`shared/fund_identity.py`、`ui_v2/{alo,exp,hld}/source.py` |
| A-2 | `git grep -n "resolve_1y_total_return\|ret_1y_total\|compute_1y_total_return" -- ui_v2 ui_v3 services/v2_tables services/v2_domain \| wc -l` | `0` |
| A-2b | `git grep -ln "resolve_1y_total_return" -- '*.py'`（非測試） | `services/ai_service.py`、`services/fund_grp_health/quality.py`、`services/fund_service.py`、`services/fund_total_return.py`、`services/health/dividend.py`、`services/health/report.py`、`services/portfolio_service.py` |
| A-3 | 讀 `services/fund_total_return.py::_unavailable` 與 `resolve_1y_total_return` 回傳 dict 鍵 | 鍵僅 `value_pct／status／reason／source／window_days／div_count_in_window／official_1y_pct／label`；無 `ccy`、`as_of`、`fund_code` |
| A-4 | `git grep -n "or 365\|len(s) \* 1.4" -- services/fund_service.py` | `services/fund_service.py` 兩處：`_days_span = max(int(len(s) * 1.4), 14)`、`_ret_1y_window_days = _window_actual_days or 365`；另 `_window_actual_days = 365`（例外分支，同函式）。`tests/*.py` 內 `ret_1y_window_days` 斷言未見針對這兩路徑者（`grep -rn "ret_1y_window_days" tests/*.py` 人工判讀） |
| A-5 | `git grep -n "build_nav_table\|nav_dividend" -- ui_v3 \| wc -l` | `0` |
| A-6 | `git grep -ln "sheet_code_contract_violation\|STATUS_SHEET_CONTRACT_VIOLATION" -- '*.py'`（排除 `tests/`） | `services/fund_identity.py`、`services/fund_identity_shadow.py`、`shared/fund_identity.py` |
| A-7 | `git grep -n '"source_tier"' -- services/v2_tables/nav_dividend.py` | 僅 `"source_tier": SOURCE_TIER_NAV,`（一處賦值） |
| A-8 | `git ls-files \| grep -i fund_code_mapping` | 無輸出（exit 1） |
| A-9 | `git grep -nE "ffill\|bfill\|fillna\(0\|interpolate" -- repositories/fund services/v2_tables` | 僅 `services/v2_tables/nav_dividend.py` 檔頭說明「不補列、不 ffill、不以 0 補」的文字行（非程式呼叫） |

---

> **本檔限制重申**：核准準備、非客戶裁示；D2 核准欄位數＝0；未新增 Schema／provider／資料來源／公式；未改任何既有檔；單組作者、未實跑測試、尚待非作者獨立 QA。
