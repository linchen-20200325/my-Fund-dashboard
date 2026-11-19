# 最小正式契約裁示範圍（Gate-D 路徑 B 單檔查詢五欄；2026-11-19）

> **稽核狀態更新（落檔時補）**：單組作者（B 線執行組）＋一組非作者稽核（含增量複審；Must-Fix 0；subagent，非 GitHub review；來源：總管轉述，稽核原始報告不在 repo、無逐字報告）。全稱句皆單組讀檔，未經第二組驗證。**本檔為候選，非客戶裁示、非核准、不授權施工。** 下方『未經獨立稽核』為撰寫時狀態，以本段為準。

> 狀態：**執行組草稿，非客戶裁示、非授權**。單組作者，未經獨立稽核；全稱句皆單組讀檔，非窮舉。基準 main `96771a58`（使用前須重查）。
> 方向來源：客戶經 ChatGPT 轉達〔待核〕，**非逐字**，repo 無逐字存檔（NOT VERIFIED）。下列「方向」皆為轉述，不得當原話。
> **核准契約文字 ≠ 核准 Schema／Provider／L1／L2／真實資料接線／取數／頁面例外處理。** 逐字核准後仍須另行施工 Gate（`CLAUDE.md` §-1；`DEC-2026-10-16-05`）。
> 標記：FACT＝讀現檔核對；INFERENCE＝推論；REC＝執行組推薦。

## A　可請客戶「一次逐字核准」的條款（候選逐字；未獲核准前不得升格）

編號語意：A1～A8 為本檔候選條款序號，B1～B7 為 Pending 序號，與 evidence 的 G／Q 編號、DEC 條號無對應關係。
**S2：A 欄為『條款級』核准；組合後的五欄正式契約依 `DEC-2026-11-19-02` 區分欄 3(3) 仍須再經最小 Decision Gate。A 欄未涵蓋配息值域（`accum`／`dist` 與 `DIVIDEND_FREQ_TO_POLICY`）、輸入回顯規則（Q6）、型別與限制聲明，這些列入 B8／B9。**
**僅引用（非本批請核）：Q2 八點鍵語意沿用 `DEC-2026-11-19-02` 區分欄 1，路徑 B 專屬、不升格 R-ID-2／R-ID-3。**

核准形式建議：客戶對 A1～A8 逐條回覆「核准／修改為…／不核准」。未回覆者視為未核准。

| # | 候選逐字條款 | 出處 | 狀態 |
|---|---|---|---|
| A1 | 本契約僅適用 Gate-D 路徑 B 單檔查詢的五欄：輸入代碼、基金名稱、配息方式、成立日期、經理費率；不含幣別、淨值、報酬、績效、取得時間、供應者名稱。 | `DEC-2026-11-19-02` 區分欄 1；契約包 §8.1 | 方向已轉述核准；**逐字待核** |
| A2（G2） | **【規範句】** 欄位級狀態集為 `VALUE`｜`MISSING`｜`CONFLICT`（追契約包 §6.2／§6.3 與現行 `FieldStatus`）；基金名稱於 `RESULT` 必為 `VALUE`；經理費率恆 `MISSING`。<br>**【現況註記（非規範）】** 現行 L2 對基金名稱、配息方式、成立日期、經理費率四欄不可達 `CONFLICT`（L2 只對幣別用 `inconsistent`）；「來源沒提供」與「同標籤不同值」目前皆落 `MISSING`，區分需 L2 結構化旗標（目前沒有）。 | `DEC-2026-11-19-02` 區分欄 2／4；`exp_profile.py::STATUS_INCONSISTENT`（FACT）；VM 檔頭 | 校文已授權準備；**逐字待核** |
| A3（G3） | 成立日期格式 `YYYY-MM-DD`、無時區。ViewModel 只驗格式、日期存在、年份 ≥ 1900；「不晚於台灣今天」由 L2 執行（`exp_profile::_check_inception`／`taiwan_today`）；ViewModel 無時鐘，不重複驗，亦不得宣稱已實作。 | 同上；`fund_lookup.py::_is_iso_date`、`MIN_INCEPTION_YEAR`（FACT） | 校文已授權準備；**逐字待核** |
| A4（G1 方向） | **【方向（轉述）】** 維持 fail-closed 現況：基金名稱不合格時 ViewModel raise `LookupContractError`（訊息不含收到的值）；頁面層例外處理另行決定。<br>**【實際判準（FACT）】** 長度 ≤ `NAME_MAX`；不含 `unicodedata.category` 以 `C` 開頭的字元；小寫後不含 `http`、`www.`（**不含 `moneydj`**，與入口 `looks_like_url` 的判準不同）。`NAME_MAX`=200 為執行組保守值，**未經客戶裁示**。<br>**【執行組推薦，非核准方向】** 佔位字檢查由 L2 負責（`declared_profile.name_is_blank`／`_fund_name_cell`），ViewModel 不重複維護第二份清單——此句在 evidence 收斂表 §2 為 RECOMMENDATION，**轉達是否含此句 NOT VERIFIED**；DEC-02 待確認 (b) 的佔位字歸屬半句**不因此視為已解**。 | 客戶方向 G1 選 A（轉述，僅『維持 raise』）；evidence §2；VM `_is_safe_name`、`ProfileFields.__post_init__`（FACT） | 『維持 raise』方向轉述；佔位字歸屬＝推薦；**逐字待核**；頁面處理見 B2 |
| A5（G4 方向） | 路徑 B 現有資料鏈對經理費率恆缺值，契約只寫「本鏈無此來源」。不得以 0、空字串、「無費用」、「最高經理費」或任何推估值替代；L2 若回非缺值，視為契約違反（fail-closed）。畫面不得複用 L2 `TEXT_MGMT_FEE` 原文（其含「來源未提供」「最高經理費」等字樣，非已核准畫面文字）。<br>**G4-A 原案（evidence §3）含「固定標記＋`◇ 資料未備`」；本筆不登記字樣部分，轉達是否含字樣 NOT VERIFIED。** | 客戶方向 G4 選 A 契約語意（轉述）；契約包 §8.1；`exp_profile.py::build_profiles`、`TEXT_MGMT_FEE`（FACT）；VM `mgmt_fee_rate_pct` 必 `MISSING`（FACT） | 方向轉述；**逐字待核**；標記與字樣見 B1／B3 |
| A6（Q4 方向） | 來源描述分兩句：①欄位值採信 MoneyDJ 基本資料頁（**僅基金名稱、配息方式、成立日期三格**；adapter 只讀 MoneyDJ 來源狀態）；②現行 L2 一次查詢實際涉及 MoneyDJ、TDCC、FundClear 三來源。契約不得據此宣稱 production 或現行 L2 為單一來源。 | 客戶方向 Q4 選 A（轉述）；契約包 §3、§8.1 P-B 規則 1；evidence E11 | 方向轉述；**逐字待核**；O1／O2 見 B4 |
| A7（Q5 狀態層） | 狀態層可辨識「取數失敗」（`SOURCE_FAILED`）與「頁面無法確認」（`PAGE_UNMATCHED`）；兩者皆不得推論為基金不存在或查無。**現況註記三點：**①`SOURCE_FAILED` 只反映 MoneyDJ 來源狀態（TDCC／FundClear 失敗不影響）；②L2 `_call` 把 fetcher 的**任何例外**轉成 `failed`，端到端可能把程式錯誤呈現為 `SOURCE_FAILED`（FACT：`exp_profile.py::_call` 有 `except Exception`）；③`no_page`（兩頁型皆 404，adapter 映 `REASON_NO_PAGE`）屬 `PAGE_UNMATCHED`，**不得渲染成「查無」**。 | 客戶方向 Q5 選 D（轉述）；`DEC-2026-11-13-06` (6)；VM／adapter（FACT） | 方向轉述；**逐字待核** |
| A8（Q5 欄位層） | L2 內部以自由文字 `reason` 與 `INCEPTION_*` 列舉（成立日期的 unrecognized／too_early／future）區分部分原因，但**沒有對外機器可讀的原因碼**，ViewModel／adapter 不讀 `reason`；故欄位層 `MISSING` 對畫面不區分子原因，契約不得宣稱已能細分。 | 同上；`exp_profile.py::INCEPTION_*`（FACT）；`reason_code` 三檔字面 0 命中（單組搜尋） | 方向轉述；**逐字待核** |

## B　必須保持 Pending 的文字（不得寫成已裁）

| # | 項目 | 為何 Pending | 出處 | 狀態 |
|---|---|---|---|---|
| B1 | **Q5 欄位層缺值字樣：`◇ 資料未備` vs `⬜ 無法判定`**（含 G4-A 原案的費率欄 `◇` 字樣，其與 Q5 欄位字樣的關係同屬 Pending） | 客戶未選 A 或 B；執行組不代選。`DEC-2026-11-13-06` (6)（不得一律 `◇`）與 `DEC-2026-11-18-01` C(5)（配息缺值 `◇ 資料未備`，轉述待核）緊張未解。規則表既有字樣不因本批變動。 | evidence §5；E9、E10 | Pending |
| B2 | **G1 頁面例外處理**（接住 `LookupContractError` 的位置與呈現） | 客戶方向為「仍待正式施工 Gate」。降級為 `name_unconfirmed`（方案 B）未採。 | evidence §2；VM 檔頭自陳 | Pending |
| B3 | **G4 固定標記名稱與字樣**（「契約上目前無來源」結構標記） | 標記尚未實作；規則表無此字樣（E9）；字樣與 B1 連動。 | evidence §3；VM 檔頭 | Pending；僅 `PendingWording` |
| B4 | **Q4 的 O1／O2**（沿用三來源 vs 新增 L2 單來源建構） | 留待正式接線 Gate；O2 為 L2 契約變更，需獨立稽核。 | 契約包 §3、§8.2 Q4 | Pending |
| B5 | **Q1 五欄正式契約本身的逐字核准** | 本文件 A 欄僅為候選；客戶未逐字核准。契約包 §8.1 原文（含輸入代碼、配息方式 `accum`／`dist` 用語、限制聲明）全部仍未核准。 | `DEC-2026-11-19-02` 區分欄 3 | Pending |
| B6 | Q2 的 `strip(' ')`（adapter）與 `str.strip()`（L2）定義不同是否需文字區分 | 實務等價為推論，未實測。 | `DEC-2026-11-19-02` F2 | Pending |
| B7 | 其他維持原狀：Q0、Q3、Q7～Q11、X1～X5、BL-0551、BL-0545、BL-0555 取數 | 不在本批。 | `DEC-2026-11-19-02` 區分欄 3(4) | 原狀 |
| B8 | 配息方式值域（`accum`／`dist`、`DIVIDEND_FREQ_TO_POLICY` 對照）、型別、限制聲明 | A 欄未涵蓋；契約包 §8.1 原文仍未核准；對照表左欄為推測（U7，未實測） | 契約包 §8.1、§9 | Pending |
| B9 | **Q6 輸入回顯規則**（`INPUT_ECHO_MAX`=64、ISIN 形分隔符處理、網址形攔截） | 未裁；輸入代碼欄文字依此 | 契約包 §8.2 Q6 | Pending（單列） |

## C　核准後仍不授權（皆須另行 Gate）

Schema；Provider；L1／L2 任何修改；ViewModel／adapter 程式變更（含頁面例外處理、降級、固定標記實作）；真實取數與探測（MoneyDJ／TDCC／FundClear）；NAS／Proxy／TLS／Secrets；ISIN resolver、別名表、後綴碼語意；frozen 44；公式；FX；Gate-D 正式接線；Gate-M 掛載；BL-0545／BL-0551／BL-0555 取數。

## D　FACT／INFERENCE／NOT VERIFIED

- FACT（本組讀碼）：VM 名稱不合格 raise；VM 費率必 `MISSING`；adapter 費率格非 `not_ready` 即 raise；adapter 傳 loader 為 `raw.strip(' ')`（保留大小寫）；L2 費率格寫死 `_cell(reason=TEXT_MGMT_FEE)`；`STATUS_INCONSISTENT` 定義於 `exp_profile.py`。
- INFERENCE：費率欄位層「取數失敗／無法確認」於現行鏈不可達（沒有取數）；欄位層子原因無法機械細分。
- NOT VERIFIED：客戶是否本人及轉達範圍；`reason_code`、「四欄不可達」等全稱句為單組搜尋；未跑任何測試；E3（VM 不 import 上層）只依檔頭、未核對守衛測試；A6 的「三來源」依 evidence 與契約包，本組未重跑 L2。
- REC：以 A1～A8 逐條徵詢；B 欄任何一項客戶若欲裁示，各開獨立 Gate，不與 A 欄混批。
