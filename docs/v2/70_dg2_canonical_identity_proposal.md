# 70 — DG-2 canonical identity：Decision Gate 提案（~~待客戶裁示，未核准~~ → 2026-10-28 客戶已裁示 C+ shadow first，`DEC-2026-10-28-05`）

> ⚠️ **2026-10-28 狀態更新（有意識的更正，不是漏刪；決策者：客戶，`DEC-2026-10-28-05`）**：客戶已裁示 DG-2 採 **C+**、先 Shadow Mode，見第 11～14 節。第 1～10 節為裁示前的提案原文，保留不改；其中第 3 節 INFERENCE「後綴代表不同通路的 NAV 序列」與第 9 節問題 1「本文假設是」**被客戶裁示推翻**（後綴預設＝通路 metadata；有證據才走例外）。

> ~~**狀態：待客戶裁示，未核准，不開始 production refactor。**~~ **（裁示前原文）** 本文是 `docs/v2/69` 第 9 節 DG-2 的具體 contract 提案，依客戶 `DEC-2026-10-28-03` 第 5、6 項（先做 C1～C9 與獨立稽核，再提 DG-2；DG-2 核准前不動 canonical identity production 程式）撰寫。
> 不改任何 `.py`、不改 `CLAUDE.md`、不改 `docs/v2/44_fund_ui_ssot.md`、不動 `INDICATOR_SPECS`。登記不構成動工授權（`CLAUDE.md` §-1）。
> **基準**：main `e05ae3a4` 加本分支（BL-0520 測試已落地，見 `docs/v2/69` 附錄 B）。會漂移的結論引用前請重查。
> ⚠️ **驗證狀態**：本文由實作組單組寫成，**未經第二組獨立驗證**。第 9 節列出我自己重驗過的承重宣稱；其餘一律標「引用自研究報告，未重驗」。「建議」只是推論，客戶可推翻。
> 標籤：FACT＝讀碼或執行純函式；INFERENCE＝推論；UNVERIFIED＝未查證。

## 1. 要解決什麼（來自客戶規則與已量測的分歧）

客戶核心規則（`DEC-2026-10-28-01`）：同一個 canonical instrument、同一 metric、同一 as-of、同一幣別／級別，在所有 view 必須得到同一個 canonical 值。目前程式裡沒有「canonical instrument」這個物件（FACT：production `.py` 沒有 `canonical_id`／`share_class` 符號，`tests/test_xview_characterization.py` 有守衛），身分只靠基金代碼字串，推導規則散在多處。BL-0520 已量到的相關分歧：

- policy 抽取器對含 `#fragment` 的網址得 `ACDD01#FRAG`、對 `?area=TW&a=ACDD01` 得 `TW`，其餘推導得 `ACDD01`（人工構造輸入；真實政策列是否出現未驗）。
- 同一檔以裸碼、小寫、不同網址呼叫，L1 快取各一個條目（來源瀑布各跑一次）。
- `get_latest_nav` 與 A 鏈各自挑來源（機制已證實）。

## 2. 現況：身分推導與比較點（FACT，除非標註）

**2.0 計數口徑**：本文與 `docs/v2/69` G-ID-1、`BL-0521` 一致，採「**六種從原始輸入推導基金代碼的規則**」：(1) `parse_moneydj_input`、(2) `canonicalize_moneydj_url`、(3) `fetch_fund_from_moneydj_url` 內的 fallback regex、(4) policy `_extract_code_from_url`、(5) cache key 正規化 `_normalize_moneydj_url_for_cache`、(6) `fund_keys`（`resolve_full_keys`）。
下表另列的 mapping、`_BANK_PLATFORM_CODES`、選股池、`nav_history`、FundClear、晨星等是「**使用或儲存**身分的位置」，不計入這六種；六是下界（沿用 69 的「至少」），不是窮舉。

| 位置 | 接受 | 輸出 | 平台後綴 | ISIN／幣別／級別 |
|---|---|---|---|---|
| `repositories/fund/sources.py::parse_moneydj_input` | 網址（`a=` 參數）或裸碼；不合格式的裸碼走 `upper()[:30]` 截斷兜底 | `code`（大寫）、`page_type`、`full_url` | 保留 | 無 |
| `sources.py::canonicalize_moneydj_url` | 只處理行動版網址（`m.moneydj.com`、`/mobile/`、`a1.aspx`、`b1.aspx`）；其餘原樣回傳；裸碼不轉大寫 | `www.moneydj.com/funddj/ya/yp01000X.djhtm?a=BASE` | **剝除**（取 `-` 前） | 無 |
| `sources.py::load_fund_code_mapping`／`_DEFAULT_MAPPING` | 代碼 | `public_code`、`page_type`（內建 12 筆別名，引用自研究報告，未重驗筆數） | n/a | 無 |
| `sources.py::_BANK_PLATFORM_CODES` | 基本代碼 | 各平台完整代碼與頁型（例如 `TLZF9-…`） | 後綴＝不同通路 NAV（`canonicalize` 檔內註解） | 無 |
| `repositories/fund/fund_orchestration.py::fetch_fund_from_moneydj_url` | canonicalize → parse → 內部 fallback regex → mapping → `_is_domestic_code` | 結果 `full_key`＝`fund_code`＝code | 保留（行動版網址除外） | 無 |
| `repositories/policy/v1.py::_extract_code_from_url` | 裸碼（轉大寫）或任何「key 以 a／code 結尾」的參數，否則取路徑最後一段 | 大寫代碼；持倉鍵 `"{policy_id}::{CODE}"` | 保留 | 無 |
| `infra/cache.py::_normalize_moneydj_url_for_cache` | 網址 `a=` | `fetch_fund\|CODE\|page_type` | 保留 | 無；FACT：production 無呼叫者（只有定義與 docstring 提及）；裸碼與**小寫 `a=` 網址**都得到空代碼鍵 `fetch_fund\|\|default`（執行確認：`a=acdd01` 得空鍵、`a=ACDD01` 得 `ACDD01`；成因＝其解析不處理小寫，僅為執行結果推論） |
| `services/v2_tables/fund_keys.py` | 僅 ASCII；strip／upper；parse；mapping；最後再驗格式 | `full_key`、`portal=""`；格式不合 fail loud | 保留 | 無 |
| `repositories/fund/declared_profile.py` | 代碼 | 來源自報幣別（MoneyDJ／TDCC／FundClear）| 保留 | 只有幣別（引用自研究報告，未重驗） |
| `repositories/pool_repository.py::PoolEntry` | 選股池列 | 欄位 `code,name,category,type_override,note,added_at,status,isin,currency,morningstar_secid` | 照填 | **ISIN、幣別、晨星 secId 為選填手填**（欄位名 FACT；「僅此處有 ISIN」引用自研究報告） |
| `repositories/fundclear_offshore.py` | `(organizeCode, fundCode, fundClassCode)` 三碼；級別碼不可傳 `all` | NAV 與幣別 | n/a | FundClear 端的級別碼（FACT：`all` 會 raise） |
| `sources.py::_MORNINGSTAR_SECID_MAP`、`_resolve_ms_secid`、`_morningstar_search_secid` | 代碼；優先序為選股池 secId、ISIN 篩選、硬編表（5 筆）、以名稱搜尋取 `results[0]` | secId | n/a | 搜尋路徑不驗 ISIN／名稱／幣別／級別（`results[0]` FACT；寫回選股池引用自 `docs/v2/69` G-ID-3，未重驗） |
| `services/nav_history_gs.py`／`nav_history_store.py` | 代碼（strip／upper） | Sheet `nav_history` 與本機 `<CODE>.json` | 保留 | 有 `currency` 欄；`_rescue_by_isin` 只存在於 `services/nav_history_store.py`（`git grep` 確認），其幣別閘的內容引用自研究報告，未重驗 |
| `services/portfolio_csv.py`、`models/ledger.py` | `code`／`fund_code` | 持倉鍵 | 保留 | 幣別預設值見 `FundPosition`（預設 `"USD"`，與「未知幣別不得當 USD」的 2026-10-10 裁示須對照，UNVERIFIED 是否有實際路徑吃到預設） |

未涵蓋（UNVERIFIED）：`ui/tab2`／`ui/tab3` 內的就地推導、`ui_v2/alo` 的 `holding_id` 組法與 `alo_holdings` 比對、TDCC／FundClear 數字代碼與 MoneyDJ 代碼的對應。「沒有其他推導點」是非窮舉敘述。

### 2.1 實際輸入的結果（本組執行 `parse_moneydj_input`／`canonicalize_moneydj_url` 與 BL-0520 測試，FACT）

| 輸入 | `parse` 代碼 | `canonicalize` 結果 | 觀察 |
|---|---|---|---|
| `ACDD01` / `acdd01` | `ACDD01` | 原樣（小寫不轉大寫） | parse 轉大寫、canonicalize 不轉 |
| `TLZF9-AL001`（裸碼） | `TLZF9-AL001` | 原樣 | 後綴保留 |
| `LU0766462157`、`0P0001J5YG`、`12345678` | 原樣當成「代碼」接受 | 原樣 | ISIN、晨星 secId、純數字都被當基金代碼，不驗形態 |
| `m.moneydj.com/a1.aspx?a=acdd01` | `ACDD01` | `…/yp010000.djhtm?a=ACDD01` | 行動版網址被轉成標準形式 |
| `taishinlife.moneydj.com/mobile/b1.aspx?a=TLZF9-AL001` | `TLZF9-AL001` | `…/yp010001.djhtm?a=TLZF9`（後綴被剝除） | **同一頁，parse 給有後綴、canonicalize 給無後綴** |
| `tcbbankfund.moneydj.com/w/wb/wb01.djhtm?a=TLZF9-24A7` | `TLZF9-24A7` | 原樣（平台桌面頁保留後綴） | 剝除只發生在行動版網址 |

結論（FACT）：同一個實體頁，依網址形態可能得到基本碼或帶後綴碼；在 `canonicalize_moneydj_url` 之內，只有行動版網址路徑會剝後綴（其他推導點是否剝後綴見第 2 節表，未逐一驗證）。

## 3. 身分被存在哪裡（migration surface）

- **保單 Sheet**：鍵 `(policy_id, fund_url)`，由 `fund_url` 推導代碼；沒有 ISIN／幣別／級別欄（`docs/v2/69` G-ID-2）。持倉鍵字串 `"{policy_id}::{CODE}"`（FACT，`repositories/policy/v1.py`）。
- **選股池 Sheet**：以 `code` 為主鍵，`isin`／`currency`／`morningstar_secid` 為選填欄，舊的 7 欄列補空字串（引用自研究報告，未重驗）。
- **`nav_history` Sheet**：鍵 `(code, date)`；`currency` 後來才加（引用自研究報告，未重驗）。本機快取與 `cache/nav/<CODE>.json` 以檔名＝代碼存放。
- **L1 `@_ttl_cache`**：鍵是呼叫端傳入的原始字串（`docs/v2/69` G-CACHE-2；BL-0520 C4／C5 已量）。
- **持倉 CSV、帳本模型、快照**：以大寫代碼為鍵（引用自研究報告，未重驗）。

INFERENCE：後綴代表不同通路的 NAV 序列，若 canonical 化時把 `TLZF9` 與 `TLZF9-AL001` 靜默合併，會混用兩條序列。最低風險的 migration 是不改任何既有 `code` 欄，只新增欄位與唯讀的 resolver。UNVERIFIED：實際 Sheet 內容（本環境無存取）。

## 4. 已有的相關文件與決策

- `docs/v2/54_phase7_design_backlog.md` §3：身分鏈 **Fund Identity → Share Class → ISIN → Currency → Dist／Acc → Hedged／Unhedged → Channel Holding Identity**；「ISIN 重要，但不寫成唯一 SSOT」；現在不改 production schema；該檔的「股份級別」不是本 repo 的「級別」（核心／衛星 tier）。
- `docs/v2/69`：G-ID-1～G-ID-4、G-NAV-5、G-SHEET-1、G-CACHE-2；第 9 節 DG-2；X3（持股估值 NAV＝單一基金 NAV，需 canonical id）。
- `DEC-2026-10-28-01`（Cross-View Gate 核心規則）、`DEC-2026-10-28-03`（DG-1 方案 B、DG-2 於測試與稽核後提出）、`DEC-2026-10-16-03`（Stop／Decision Gate，data identity 規則為停下條件）、`DEC-2026-10-16-05`（治理與 data semantics 類變更至少一組真正獨立稽核）。
- UNVERIFIED：其他 evidence 檔是否已有身分相關裁示（只查了 `DECISIONS.md`、54、69）。
- 命名注意：本文的「契約 A／B／C」與 `docs/v2/69` 第 9 節的「方案 A／B」是不同的東西。

## 5. 三個契約選項（皆為提案，未核准）

**共同規則**（三者都適用）：
1. 缺值不等於猜值：ISIN、幣別、級別、配息型態、避險標記缺時填空並附原因碼，不從名稱推定、不預設 USD（對齊 2026-10-10 客戶裁示）。
2. 不同平台後綴不自動合併：後綴是通路維度，不是別名。
3. 身分衝突時，不採用該筆外部資料、寫一筆 conflict record（欄位形態見 `docs/v2/69` 第 7 節），畫面顯示 **「⬜ 資料來源不一致，暫無法判定」**，不靜默擇一。例：晨星 `results[0]` 的幣別或 ISIN 與已知身分不符時屬於此類。
4. 先 shadow mode（算出 canonical id 並與現行推導並排記錄差異，不改行為），再以 feature flag 決定是否讓閘門生效；任何階段都可關閉回到現況。

| 欄位 | 契約 A：ISIN 為主 | 契約 B：複合鍵 | 契約 C：最小（代碼為主＋驗證閘） |
|---|---|---|---|
| `canonical_id` | 有 ISIN 時＝ISIN（12 碼並驗校驗碼）；否則 `LEGACY:<含後綴代碼>` 佔位 | `BASE｜SUFFIX｜CCY｜CLASS`（大寫，缺項以明確佔位符，不留空猜測） | `UPPER(含後綴代碼)`，由單一 `resolve_instrument(raw)` 產生 |
| `fund_code` | 別名表的一欄 | 拆成 `BASE`＋`SUFFIX` | 即 `canonical_id` 本身 |
| `isin` | 主鍵（缺則 LEGACY） | 驗證用屬性：與別名表的幣別／級別衝突即記 conflict | 選填屬性，不進鍵；已知時用於驗證外部資料 |
| `share_class` | 別名表屬性 | 鍵的一部分；無可靠機器來源時為 `?`（INFERENCE：目前只有名稱／幣別啟發式，不可用） | 選填屬性，不進鍵 |
| `currency` | 別名表屬性 | 鍵的一部分；來源自報（MoneyDJ／TDCC／FundClear 已取）優先，缺則 `?` | 選填屬性；外部來源須與其相符才採用 |
| `platform_suffix` | 屬別名表的通路欄；不同後綴＝不同別名列 | 鍵的一部分（空字串明示「無通路」） | 保留在代碼內，不拆 |
| `dist_acc`、`hedged` | 別名表屬性（缺＝空） | 可選鍵段或屬性（缺＝`?`） | 選填屬性，不進鍵 |
| mapping 規則 | 內建別名（如 `ACTI171→ACTI71`）改種子進別名表 | 同左，並先拆後綴再查 | 沿用 `fund_keys` 嚴格規則（ASCII、格式、無截斷） |
| 缺 ISIN | 該筆 `canonical_id` 為 `LEGACY:…`，畫面標「識別未確認」 | ISIN 只是驗證用，缺不影響鍵，但鍵內含 `?` 者視為「部分身分」，不跨來源合併 | 屬性為空，不影響鍵 |
| 衝突 | 拒收該筆外部命中，記 conflict | 同左；ISIN 與鍵內幣別／級別不符＝衝突 | 驗證閘拒收（幣別不符；ISIN 已知且不符） |
| 歷史相容／migration | 別名表以選股池 `isin`、硬編晨星表、人工補種；舊 `code` 欄不動，resolver 唯讀查表 | 由現有代碼拆後綴；以 declared_profile 幣別補；Policy／選股池**加欄**（additive） | 儲存資料不動；只有「原本被截斷的不合格輸入」改為 fail loud |
| 影響面（blast radius） | 新 resolver＋六種推導規則（見 §2.0）的呼叫點改走它；別名表維護成本高 | 同 A 加 Sheet 加欄；中大 | 收斂六種推導規則成 1 個；小到中 |
| 對應測試 | `fund_keys`／policy／orchestration 既有測試；X3 | 同左；另需欄位缺值矩陣測試 | 既有 C5b 特徵化測試轉為斷言；X3 部分 |

### 5.1 優缺點與風險

| | 優點 | 缺點 | 風險 |
|---|---|---|---|
| A | 業界慣用主鍵；可跨來源（晨星／FundClear／TDCC）join | 保單平台代碼多數沒有 ISIN（選股池為手填）；ISIN 不區分通路 NAV（後綴）；與 54「ISIN 不是唯一 SSOT」有張力 | **高**：覆蓋率不足，多數持倉會落在 `LEGACY` |
| B | 最貼近 54 的身分鏈；保留後綴語意；ISIN 不當唯一 SSOT | 級別、配息型態、避險目前沒有可靠機器來源；欄位多，維護成本高 | **中**：後綴處理錯誤＝取到錯的 NAV 序列 |
| C | 可逆、不動 Sheet、最快讓各 view 對同一鍵一致 | 不把級別與 ISIN 建模成身分；同一檔基金的兩個代碼仍視為兩個標的；客戶規則中的「同一級別」只能靠幣別屬性近似 | **低**，但之後可能需要升級到 B |

## 6. 可逆性與分階段（所有選項共通）

1. **階段 0（已完成）**：BL-0520 特徵化測試與附錄 B。
2. **階段 1（shadow）**：新增 resolver，與現行各推導並排記錄差異，不改任何顯示或取數。
3. **階段 2（閘門，feature flag）**：外部資料採用前套驗證閘；flag 預設關。
4. **階段 3**：視階段 1 的差異報告，再決定是否升級到 B 的欄位。
每階段可單獨回退。Production refactor 不在階段 1 以前進行，且須先有客戶核准。

## 7. 對應測試（X 案例與新增）

- 既有：`tests/test_xview_characterization.py` 的 C5／C5b 特徵化測試（目前斷言現況分歧，實作後改為斷言一致）；X3（`get_latest_nav`＝A 鏈）需要「同一 canonical instrument」的定義才有意義。
- 實作時需新增：晨星 `results[0]` 幣別／ISIN 不符拒收測試；平台後綴不合併測試；缺 ISIN／缺幣別不猜測試；shadow 差異報告測試；flag 關閉時行為與現況逐位元組相同的測試。
- 依 `DEC-2026-10-16-05`，本件屬 data identity 語意變更，至少一組真正獨立稽核。

## 8. 建議（RECOMMENDATION，推論，可被客戶推翻）

**階段 1 採契約 C，並讓資料結構（`isin`、`currency`、`share_class`、`platform_suffix` 為獨立屬性，不塞進代碼字串）預留日後以加欄方式升級到契約 B 的空間；不建議以契約 A 為主。**
理由（INFERENCE）：ISIN 目前只在選股池手填、覆蓋率不足；ISIN 不區分通路後綴 NAV，且 54 已寫明不當唯一 SSOT；契約 C 不動儲存資料、可關閉、最快讓 view 之間對同一鍵一致，並為 X3 等不變量提供鍵。代價是「同一級別」只能先用幣別屬性近似，這點需客戶接受。

## 9. 客戶需要回答的問題

1. 平台後綴（例如 `TLZF9` 與 `TLZF9-AL001`）是否一律視為不同標的、永不自動合併？（本文假設是。）
2. 缺 ISIN 的持倉，畫面要顯示「識別未確認」，還是維持現狀不標示？
3. 外部來源（如晨星搜尋）與已知身分衝突時，顯示 **「⬜ 資料來源不一致，暫無法判定」** 並排除該筆，是否同意？
4. 階段 1 採契約 C（shadow mode、不動 Sheet）是否同意？還是要直接做契約 B（需要在保單／選股池加欄）？
5. 「同一級別」在客戶規則中，階段 1 是否可先以幣別＋後綴近似，級別／配息型態／避險標記留待資料來源明確後再補？
6. 實作時的 Model Gate：本件涉及 data identity 規則，建議實作走 Opus＋High（`PROJECT_RULES.md` 第 5 節 Model／Effort Change Gate）；是否同意？

## 10. 揭露：這份提案怎麼來的、哪裡沒驗

- 來源：單一作者的唯讀研究報告（無網路、不連線）加本組重驗。**本組重驗過的承重宣稱與可重跑的指令**（repo 根目錄執行；Python 部分需 `PYTHONPATH=.`，本機沒有 pandera 時以空操作外掛取代 `shared.schemas`，不影響下列函式）：

```text
# 腳本（存成 v.py 執行）
from repositories.fund import sources as s
p, c = s.parse_moneydj_input, s.canonicalize_moneydj_url
for i in ["LU0766462157", "0P0001J5YG", "12345678", "acdd01"]: print("1", i, p(i)["code"], c(i))
for i in ["https://taishinlife.moneydj.com/mobile/b1.aspx?a=TLZF9-AL001",
          "https://tcbbankfund.moneydj.com/w/wb/wb01.djhtm?a=TLZF9-24A7"]: print("2", p(i)["code"], c(i))
print("4", len(s._MORNINGSTAR_SECID_MAP))
from repositories.pool_repository import PoolEntry; import dataclasses
print("5", [f.name for f in dataclasses.fields(PoolEntry)][-3:])
from infra.cache import _normalize_moneydj_url_for_cache as f
print("3", f("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=acdd01"), f("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=ACDD01"))
```

  1. ISIN、晨星 secId、純數字被當代碼原樣接受；小寫裸碼 parse 轉大寫、canonicalize 不轉：輸出 `1 LU0766462157 LU0766462157`、`1 0P0001J5YG 0P0001J5YG`、`1 12345678 12345678`、`1 acdd01 ACDD01 acdd01`。
  2. 行動版網址剝後綴、平台桌面頁不剝：`2 TLZF9-AL001 https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9`；`2 TLZF9-24A7 https://tcbbankfund.moneydj.com/w/wb/wb01.djhtm?a=TLZF9-24A7`。
  3. cache 鍵函式：小寫 `a=` 得 `fetch_fund||default`、大寫得 `fetch_fund|ACDD01|default`（輸出行 `3 …`）。
  4. `_MORNINGSTAR_SECID_MAP` 恰 5 筆：輸出 `4 5`。
  5. `PoolEntry` 末三欄：輸出 `5 ['isin', 'currency', 'morningstar_secid']`。
  6. `git grep -n _normalize_moneydj_url_for_cache -- '*.py'` → 只有 `infra/cache.py` 三行（模組 docstring、定義、錯誤訊息字串），沒有其他檔案、沒有 import 或呼叫。
  7. `git grep -n "results\[0\]" -- repositories/fund/sources.py` → `sources.py` 內兩行（取 `i` 與 `n`）。
  8. `git grep -n "fundClassCode" -- repositories/fundclear_offshore.py` → 檔頭 docstring 寫「`fundClassCode` 不可傳 "all"…明確 raise ValueError」（以讀 docstring 為準，raise 本身未另行執行）。
  9. `git grep -n '"{policy_id}::{fund_code}"' -- repositories/policy/v1.py` → 命中 `sync_policies_to_portfolio_funds` docstring（`repositories/policy/v1.py:232`），內部 `_pk` 以 `policy_id::CODE` 組字串（讀碼）。
  10. `git grep -n "^### DEC-2026-10-16-0[35]" -- docs/DECISIONS.md` → 兩行；`git grep -n "身分鏈" -- docs/v2/54_phase7_design_backlog.md` → §3 內身分鏈一行。
  11. production 無 `canonical_id`／`share_class` 符號：由 `tests/test_xview_characterization.py::test_char_agreement_c5b_no_canonical_id_or_share_class_symbol_exists_in_production_python` 的 AST 掃描（字面名稱；不證明沒有其他名稱表達同一概念）。
- **其餘一律「引用自研究報告，未重驗」**，包含：內建別名 12 筆、`declared_profile` 細節、`nav_history` 欄位演進與 `_rescue_by_isin` 幣別閘、持倉 CSV／快照鍵、各 Sheet 的實際內容。
- 本文沒有任何網路查證，也沒有查證真實基金代碼與 ISIN／級別的對應。

## 11. 客戶裁示（`DEC-2026-10-28-05`）

逐字原文：`docs/evidence/decisions/2026-10-28_dg2_identity_ruling.md`（本節是摘要，以原文為準）。

- `TLZF9`／`TLZF9-AL001`／`TLZF9-24A7` 原則上同一核心基金：`base_fund_code = TLZF9`；`original_code`／`platform_suffix`／`channel_code`／`source_url` 另存；後綴不得直接當新身份。
- 不得盲目剝後綴：證據顯示後綴是不同 share class／幣別／配息／避險／NAV series → Exception／Decision Gate，不硬合併。
- ISIN 本階段不依賴（不作 key、不必要、缺了不警告）；currency／share class／配息／避險不得猜，沒有可靠資料一律 Unknown，Unknown 不視為相同、不同、安全或已確認。
- 先 Shadow Mode：不改 Sheet schema、production 顯示、NAV precedence、valuation、FX、return formula；flag 預設關；只記差異。
- 外部來源不得因 `results[0]` 接受；已知屬性衝突 → 拒收、留 evidence、顯示「⬜ 資料來源不一致，暫無法判定」。
- NAV 與 identity 分開；同 base＋同日＋同幣別 NAV 不一致 → source conflict，不建第二個 canonical fund。
- 本階段禁止順帶修改：`get_latest_nav`、NAV precedence、FundClear／MoneyDJ／Yahoo 排序、valuation、FX cutoff、return formula、Sheet migration、One AI Brain。

## 12. 舊 UI reuse matrix

來源：舊 UI targeted audit（單組、唯讀、無網路，2026-10-28，基準 main `5e5048d5`）。「重驗」欄：✅＝本實作組以純函式執行或讀碼重驗（多數已由 `tests/test_fund_identity_dg2.py` 釘住）；—＝**引用自稽核報告，未重驗**。

| # | 邏輯（file::symbol） | 分類 | 重點 | 重驗 |
|---|---|---|---|---|
| 1 | `repositories/fund/sources.py::parse_moneydj_input` 頁型辨識 | ADAPT | resolver 取其 `page_type` 作 metadata | ✅ |
| 2 | 同上代碼文法 `主碼(-後綴)?` | ADAPT | 經 `fund_keys` 關卡使用，不單獨用（`a=` 未錨定、兜底收 `#FRAG`） | ✅ |
| 3 | `canonicalize_moneydj_url` 內 `split("-", 1)[0]` | ADAPT | ~~resolver 對**所有**輸入一致套用第一個 `-` 前＝base~~ → 只在 MoneyDJ／平台代碼命名空間套用（反例見第 14 節第 7 點；2026-10-28 獨立稽核 MUST 1，有意識的更正，不是漏刪）；→ 2026-10-29 再收窄：只剝**已驗證 mapping** 命中的後綴（`DEC-2026-10-29-01`，第 15 節） | ✅ |
| 4 | `canonicalize_moneydj_url` 整體（只改寫行動版網址） | LEGACY_COMPAT | 舊 tab2 行為維持；resolver 不依賴它 | ✅ |
| 5 | `services/v2_tables/fund_keys.py::_resolve_one`／`_is_pure_code` | ADAPT（驗證≈REUSE） | resolver 的輸入關卡；`#frag`／`area=` 正確 | ✅ |
| 6 | `repositories/policy/v1.py::_extract_code_from_url` | REJECT（身分）／LEGACY_COMPAT（保單同步） | `#frag`→`TLZF9-AL001#FRAG`、`area=TW`→`TW`；2026-10-29 讀碼：**也在 vNext 持倉路徑上**——v1 格式保單分頁（無 `基金代號`／`fund_code` 欄）經 `repositories/policy_supplement_repository.py::_process_policy_tab` → `repositories/policy/v2.py::_v1_frame_to_v2` 以它從 `fund_url` 推 `fund_code`（第 15 節〈hook 呼叫鏈〉） | ✅ |
| 7 | 持倉主鍵 `policy_id::CODE`、`migrate_ledger_dict` | LEGACY_COMPAT | 不改存放鍵 | — |
| 8 | `infra/cache.py::_normalize_moneydj_url_for_cache` | REJECT | 小寫與裸碼得空鍵、頁型恆 `default` | ✅ |
| 9 | `fetch_fund_from_moneydj_url` 內 fallback regex | LEGACY_COMPAT | 函式內嵌、不可單獨呼叫，shadow 未納入 | ✅（讀碼） |
| 10 | `_DEFAULT_MAPPING`／`load_fund_code_mapping` | LEGACY_COMPAT（別名可 ADAPT） | resolver 預設不套別名（`alias_mapping={}`）；shadow hook 傳入 production `resolve_full_keys` 已載入的同一份表（不另讀檔） | ✅（`ACTI171`／`ACTI7`／`ACTI71` → `ACTI71`） |
| 11 | `sources.py::_BANK_PLATFORM_CODES` | ADAPT（channel 種子；2026-10-29 起為「已驗證 mapping」之一） | 6 個 base、鍵全是 base；shadow 綁定後注入 resolver 當 `channel_table`；客戶 2026-10-29 舉的 `TLZF9-AL001`／`TLZF9-24A7` 都在表內，`ACDD01-EQTAL005` 不在（改列 L0 客戶確認表） | ✅ |
| 12 | `_src_bank_platform_nav`（第一個成功通路即用） | UNVERIFIED | 不比對各通路是否一致；不可當「同 NAV」證據 | ✅（讀碼） |
| 13 | `fund_fetcher.py::PORTAL_CFG` | LEGACY_COMPAT | 只有 URL 樣板 | — |
| 14 | `fund_fetcher.py::_INSURANCE_SUBDOMAIN_HINTS` | REJECT（通路證據）／LEGACY_COMPAT（取數） | 以 base 前綴猜子網域，不可填 `channel_code` | — |
| 15 | `get_page_types_to_try`、`_is_domestic_code` | LEGACY_COMPAT（取數路由）／REJECT（身分或頁型證據） | 純頁面路由；2026-10-29 重驗：網址頁型優先、其次對照表、再前綴、預設境外；首選失敗即互換，推斷不可當證據（第 15 節） | ✅（讀碼＋測試） |
| 16 | `nav_metrics.py::fetch_nav`／`fetch_div` 的 `split("-")[-1]` | REJECT | 以後綴當代碼重抓（`TLZF9-AL001`→`AL001`）；見第 14 節 | ✅ |
| 17 | `_morningstar_search_secid`／`_resolve_ms_secid` 的 `results[0]` | REJECT | 改由 `validate_external_candidate` 驗（本階段只 shadow） | — |
| 18 | `_MORNINGSTAR_SECID_MAP`、`_ALLIANZ_INSURANCE_CODES`、`cache/nav/TLZF9.json` | LEGACY_COMPAT（C+ 佐證） | 全以 base 為鍵 | — |
| 19 | `_span_extend_expected_ccy`／`_declared_or_table_ccy` | LEGACY_COMPAT | 帶後綴得未知幣別；resolver 不從它推 currency | — |
| 20 | `nav_history_gs` 鍵、`nav_history_store._path` | LEGACY_COMPAT | 以完整代碼存序列；不 rekey | — |
| 21 | `services/moneydj_fetcher.py::auto_fetch_moneydj`／`build_moneydj_url` | LEGACY_COMPAT；大寫化網址 REJECT | 見第 14 節 | ✅ |
| 22 | `ui/tab3_portfolio.py` 手動加入、`ui/tab3_t7_ledger.py` 新基金整行 `.upper()` | REJECT（網址輸入） | 見第 14 節 | ✅ |
| 23 | `ui/helpers/portfolio/load.py::batch_load_unloaded_funds` | LEGACY_COMPAT | 裸碼呼叫、去重不轉大寫 | — |
| 24 | Step 1 平台頁 `nav_latest` 受保護、不與序列對帳 | UNVERIFIED | 見第 14 節 | ✅（既有特徵測試） |
| 25 | `fx_and_main.py::get_latest_nav` 來源鏈 | UNVERIFIED（不碰） | NAV Gate | — |
| 26 | `ui/helpers/portfolio/allocation.py::summarize_core_satellite` | REUSE（對身分議題） | 不依代碼、不用 NAV | — |

舊 UI 結論（稽核，FACT 部分已重驗 #1～#6、#8、#11、#16）：舊路徑**不**收斂成 base（只有行動版網址經 canonicalize 剝後綴）；後綴在程式中只用於組平台 URL；「後綴＝不同 NAV 序列」只是兩處註解宣稱，其宣稱的機制（後綴代碼走 `_BANK_PLATFORM_CODES`）在現行程式不成立（表以 base 為鍵，`TLZF9-AL001` 不在表內，本組重跑確認）。沒有反證推翻 C+；各通路 NAV 是否相同 **UNVERIFIED（需網路）**。

## 13. Stage-1 C+ shadow 設計與實作

| 檔案 | 層 | 內容 |
|---|---|---|
| `shared/fund_identity.py` | L0 | `DG2_SHADOW_ENABLED = False`（feature flag，無 env override：本 repo 無此慣例）、`UNKNOWN = "Unknown"`、verification status、候選／cross-view 狀態、`SOURCE_CONFLICT_TEXT`、`IDENTITY_EXCEPTIONS = frozenset()`（例外登記，預設空） |
| `services/fund_identity.py` | L2 純函式 | `CanonicalFundIdentity`（frozen dataclass：`base_fund_code`、`original_code`、`platform_suffix`、`channel_code`、`source_url`、`currency`、`share_class`、`distribution_type`、`hedge_status`、`isin`、`source`、`as_of`、`verification_status`，另加 metadata `page_type`／`raw_input`／`error`；`canonical_key` 只在 `base_resolved_attributes_unverified` 時有值）；`resolve_fund_identity`、`compare_attribute`／`same_canonical_fund`（Unknown＝未定）、`evaluate_suffix_evidence`（證據 → 例外紀錄，不合併）、`validate_external_candidate`（拒收／接受／unverified）、`check_cross_view_nav`（consistent／source_conflict／not_comparable） |
| `services/fund_identity_shadow.py` | L2 | `current_parser_results`、`shadow_compare`（raw → 五個現有 parser 結果 → resolver 結果 → difference → reason）、`log_shadow_for_fund_keys`（hook；只寫 `logging`，自身失敗只記 log） |
| `services/v2_tables/fund_keys.py::resolve_full_keys` | L2 | 唯一 hook：flag 為真才於函式內 import shadow 並記 log；回傳值不變 |

- **層級**：純 resolver 不 import `_BANK_PLATFORM_CODES`（通路表以 `channel_table` 參數注入，shadow 模組綁定）；它 import L1 `parse_moneydj_input` 與 L2 `fund_keys`（L2→L1 下行，`CLAUDE.md` §8.2 允許；`fund_keys` 既有同一 import）。v2_tables import 白名單加開 `fund_keys.py`→`services.fund_identity_shadow` 一個名字（`tests/test_v2_tables_market_indicator.py`）；`tests/test_services_purity_contract.py` 照舊綠。
- **命名空間（2026-10-28 獨立稽核 MUST 1）**：「第一個 `-` 前＝基金碼」只在 MoneyDJ／平台代碼命名空間成立。證據任一即可：`namespace="moneydj"`；網址被 `parse_moneydj_input` 認出 MoneyDJ 頁型；完整代碼在注入的通路表內。沒有證據的帶 `-` 代碼 → `namespace_unknown_suffix_not_stripped`（不剝、`canonical_key` 為空、`same_canonical_fund` 只在完整代碼逐字相同時為真）；明示其他命名空間 → `out_of_scope_namespace`。shadow hook 不替 Sheet 代碼擔保命名空間：不在通路表的裸帶後綴代碼照實記為命名空間未知（~~Sheet 代碼命名空間屬 Stage-2 Decision Gate~~ → 2026-10-29 客戶已裁定，`DEC-2026-10-29-01`，見第 15 節；有意識的狀態更新，不是漏刪）。
- **外部候選接受條件（MUST 2）**：`accepted` 必須 `base_fund_code` 或 `isin` 已確認；只有幣別等非身分鍵相符 → `unverified`。
- **例外登記不會自動更新（SHOULD d）**：`evaluate_suffix_evidence` 的輸出在 Stage-1 **不**寫進 `IDENTITY_EXCEPTIONS`；登記新增須 Decision Gate。在那之前 `same_canonical_fund` 的結果不因任何證據紀錄而改變。
- **hook 失敗隔離（SHOULD a）**：hook 的 import 與呼叫都包在 try 內，失敗只寫 `logging`（`fund_keys.py` 因此加開 `logging` 一個標準庫名字）；子程序測試確認 flag 關時 `services.fund_identity`／`services.fund_identity_shadow` 都不會被 import（SHOULD c）。
- **resolver 不做的事**：不從名稱、後綴或幣別推 currency／share class／配息／避險；不預設 USD；不要求 ISIN；不套別名表（除非呼叫端注入）；不 canonicalize 改寫網址；不取數。
- **本階段不改**：Sheet schema、production 顯示、`get_latest_nav`、NAV precedence、FundClear／MoneyDJ／Yahoo 排序、Morningstar `results[0]`（`validate_external_candidate` 未接入）、valuation、FX、return formula、One AI Brain、任何舊 UI 缺陷。
- **測試**：`tests/test_fund_identity_dg2.py`（無網路；含 flag-off 不呼叫 hook／結果不變、flag-on 只寫 log 結果不變、shadow 失敗不影響 production）。`tests/test_xview_characterization.py` C5b「production 無 `share_class` 符號」改為「僅 `services/fund_identity.py`」（有意識的更正，該檔已註明）。
- **Stage-2（啟用 resolver 影響任何鍵或顯示）須另一次 Decision Gate。** 待補證據：同一日 `TLZF9` vs `TLZF9-AL001`／`TLZF9-24A7` 的實際 NAV 比對（需網路；見 BL-0521）。

## 14. 已知缺陷（本批不修，待後續）

以下皆於 2026-10-28 由本實作組重驗（純函式執行或讀碼；端到端 UI 未跑）；本批依裁示第 9／12 項**不改** production。

1. **T7／tab3 手動加入把網址整行轉大寫**：`ui/tab3_t7_ledger.py` 新基金 `_a_new_code.strip().upper()`、`ui/tab3_portfolio.py` 手動批次每行 `.upper()` → `build_moneydj_url` 的 `startswith("http")` 對 `HTTPS` 不成立 → 組出 `…?a=HTTPS://…` → `parse_moneydj_input` 得 code `HTTPS`（執行確認）。
2. **`nav_metrics.fetch_nav`／`fetch_div` 以後綴當代碼**：`full_key.split("-")[-1]`，`TLZF9-AL001` → 打 `?a=AL001`（讀碼＋執行 split）；可達於 legacy 最終備援與 `nav_history_store.incremental_update`。
3. **`policy/v1._extract_code_from_url`**：`#frag` → `TLZF9-AL001#FRAG`、`?area=TW&a=…` → `TW`（執行確認；`shadow_compare` 測試釘住）。
4. **cache 正規化**：小寫 `a=` 與裸碼都得 `fetch_fund||default`（空碼鍵；執行確認）；production 0 呼叫者（引用第 10 節第 6 點）。
5. **tab2 Step-1 `nav_latest` 不與序列對帳**：既有 `tests/test_xview_characterization.py::test_char_divergence_c5_scalar_nav_latest_and_series_last_are_not_reconciled` 綠（本批重跑）。
6. **銀行平台第一個成功即用**：`_src_bank_platform_nav` 依序試各通路，第一個抓到資料的就回傳（moneydj 頁型要 ≥10 筆；台灣人壽 mobile 分支只要非空），不比對其他通路（讀碼）；且只對 base 碼觸發（`fund_orchestration` `_code in _BANK_PLATFORM_CODES`）。

7. **反例：FundClear 級別碼也有 `-`**（2026-10-29 補註：下方「⚠️ 守門只擋…仍會被合併」已因 `DEC-2026-10-29-01` 不成立——後綴須命中已驗證 mapping 才剝，誤傳 `namespace="moneydj"` 也不合併；測試改名 `test_呼叫端誤標moneydj時_AGIF級別碼也不被合併`）（2026-10-28 獨立稽核 MUST 1，重驗 `tests/test_fundclear_offshore.py::test_parse_selection`）：`AGIF-HT5`＝IT 累積類股、`AGIF-HTG`＝A 配息類股，是同一基金的不同級別。原 commit `539e660c` 的 resolver 會把兩者剝成同一 base `AGIF`（`same_canonical_fund` 為 True）；已改為命名空間未知時不剝（見第 13 節），測試釘住兩者不合併。⚠️ 守門只擋「沒有命名空間證據」：呼叫端若對 FundClear 級別碼誤傳 `namespace="moneydj"`，兩者仍會被合併（測試 `test_呼叫端明示moneydj時_AGIF級別碼會被合併_守門靠呼叫端不誤標` 釘住此現況）。
8. **別名表缺口**：resolver 單獨呼叫時預設不套別名，`ACTI171`／`ACTI7`／`ACTI71`（內建表同一檔）會得到三個 base；shadow hook 已傳入 production 對照表，故 hook 記錄不受影響；Stage-2 啟用前須決定別名表是否為 resolver 的正式輸入。

以上已列入 `docs/BACKLOG.md` BL-0521 子項，不另開 BL。

## 15. 客戶最終裁示（`DEC-2026-10-29-01`）與 resolver 契約更新

逐字：`docs/evidence/decisions/2026-10-29_dg2_final_ruling.md`。取代 #1098 之後提出的 Sheet 代碼解析 A／B／C 問題。仍為 Shadow：flag 預設關、production 不變。四類解析缺陷（第 14 節第 1～4 點）由另一組處理，本節不動。

### 15.1 契約（`services/fund_identity.py::resolve_fund_identity`，L0 常數在 `shared/fund_identity.py`）

- **Sheet「基金代號」欄**：呼叫端以 `input_source=INPUT_SOURCE_SHEET_FUND_CODE`（`"sheet_fund_code_column"`）宣告 → 命名空間固定 `moneydj`（`INPUT_SOURCE_NAMESPACES` 只有這一個鍵；未知來源、或與 `namespace` 衝突 → `ValueError`）。合格基本代碼（ASCII、非網址、不含 `-`、`[A-Z0-9]{3,30}`）原樣當 base。帶 `-`、網址、格式不符、非字串、空白 → `sheet_code_contract_violation`：`raw_input` 原物件保留，`base_fund_code`／`original_code`／`canonical_key` 皆空，不剝、不截、不改寫。大小寫與前後空白沿用 `fund_keys` 第 0～2 步（執行組讀法）。只限該欄，未宣告來源的輸入照舊走證據規則。
- **後綴**：只在 MoneyDJ 證據（宣告命名空間、MoneyDJ 網址頁型、或命中下列 mapping）**且**已驗證 mapping 命中時才剝；mapping＝注入的通路表（`suffix_provenance="channel_table"`）或 L0 `CUSTOMER_CONFIRMED_SUFFIXES`（目前只有 `("ACDD01","EQTAL005")`，`provenance="customer_confirmed_2026-10-29"`、`nav_equivalence="UNVERIFIED"`，不含通路名稱）。有 MoneyDJ 證據但後綴未驗 → `moneydj_suffix_unverified_not_stripped`（不剝、不合併；`same_canonical_fund` 只在完整代碼逐字相同時為真）。這是對裁示第 4 項第 3、4 點的**執行組讀法**：收窄了 `DEC-2026-10-28-05` 實作的「MoneyDJ 命名空間內第一個 `-` 前一律＝基金碼」；既有測試三處依此改寫（已註明）。
- **FundClear**：`AGIF-HT5`／`AGIF-HTG` 在任何 `namespace`（含誤標 `moneydj`）都不剝成 `AGIF`。不產生 FundClear 對照；沒有已驗證跨來源 mapping 時 resolver 不宣稱同一基金。
- **基金身份 vs 持倉身份**：resolver 只收單筆代碼，原始碼不含任何持倉欄位（測試以 AST 掃描釘住）；同基金多保單得同一 `canonical_key`，持倉列與 `(policy_id, fund_code)` 鍵不動、不彙總；hook 逐筆記錄、不去重。不改任何儲存鍵。
- **Unknown**：currency／share class／配息／避險一律 Unknown、不預設 USD、缺 ISIN 不警告不影響。
- `evaluate_suffix_evidence` 改用 MoneyDJ 文法的候選切分比對（只評估證據、不合併），新增 `channel_table` 參數。

### 15.2 hook 呼叫鏈（`services/v2_tables/fund_keys.py::resolve_full_keys`）——為何 hook 不宣告 Sheet 來源

hook 只拿到字串串列，`resolve_full_keys` 的呼叫端來源不一（讀碼，2026-10-29）：
- `ui_v2/hld/source.py`、`ui_v2/alo/source.py`、`services/v2_tables/settings_store.py::_refetch_nav_run`：`holding[*]["fund_code"]`，來自 `services/v2_tables/alo_holdings.py::build_alo_tables`（`_key_text` 只去前後空白）← `repositories/policy_supplement_repository.py::_process_policy_tab`（服務帳戶路徑與 `repositories/personal_policy_reader.py::load_workbook_tables` 共用）。分頁有 `基金代號`／`fund_code` 欄 → 取該欄；**沒有**（v1 格式）→ `repositories/policy/v2.py::_v1_frame_to_v2` 以 `repositories/policy/v1.py::_extract_code_from_url` 從 `fund_url` 推出。
- `ui_v2/exp/source.py::_load_funds`：`pool["codes"]`，來自 `services/v2_tables/exp_universe.py`（基金池分頁的 `code` 欄，`repositories/pool_repository.py::_HEADERS`），不是基金代號欄。

→ 逐筆來源無法在 hook 證明，故 hook 一律不傳 `input_source`（測試釘住）；`resolve_full_keys` 簽名不改。要標記，須由能證明來源的呼叫端（例如在 `_process_policy_tab` 知道是哪一欄時）往下帶——那會改 production 介面，未做。

### 15.3 MoneyDJ 境內／境外頁型（第 5 項；讀碼＋既有與新增測試）

- `yp010000`＝境內頁、`yp010001`＝境外頁（`repositories/fund/sources.py::_is_domestic_code` docstring 與分支、`parse_moneydj_input` 註解、`tests/test_fund_url_canonicalize.py`）。其他頁型（`wb01`／`wb02`／`wb05`／`wr01`／`wr02`／`a1_mobile`／`b1_mobile`）不表示境內外。
- **優先序**：`_is_domestic_code(code, page_type)`：網址明示的 `yp010000`／`yp010001` → 對照表（`load_fund_code_mapping`，csv 可覆寫）→ `_DOMESTIC_PREFIXES` 前綴 → 預設境外。`fund_orchestration` 只在 `page_type` 空白時推斷（`fetch_fund_from_moneydj_url`、`_fetch_fund_single`；網址或對照表給了頁型就照用），`canonicalize_moneydj_url` 只用前綴。
- **推斷不可靠**：首選失敗即 `get_page_types_to_try` 互換重試；`fund_orchestration` 註解自陳「ACTI71 mapping table 標境內 yp010000 但實際境外」（未驗證的註解）；BL-0520 特徵化輸入 `https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=ACDD01` 的明示頁型與前綴推斷（境內）衝突；前綴表只列部分投信、預設境外是取數保守值。
- **resolver**：網址明示頁型 → `page_type_source="url"`，`yp010000`／`yp010001` 另記 `url_page_market`＝`domestic`／`offshore`（MoneyDJ 頁面類別，不是基金屬性證明）；裸碼 → `page_type=""`、兩者皆 Unknown，不用前綴或對照表推斷。頁型不參與身分比較。

### 15.4 NAV 網路查證（第 9 項）

`TLZF9`、`TLZF9-AL001`、`TLZF9-24A7`、`ACDD01`、`ACDD01-EQTAL005` 的實際 NAV 等價性：**UNVERIFIED**。理由：本 container 對 MoneyDJ 的連線被網路政策擋下（proxy CONNECT 403，2026-10-29 查）；未嘗試繞過，未記任何數值。另：`tests/test_fund_url_canonicalize.py::test_canonicalize_chubb_wr01_passthrough` docstring 宣稱平台桌面頁 `ACDD01-EQTAL005` 是「扣手續費後的 NAV（與裸 ACDD01 不同）」——未經證據的註解，與客戶確認的身份語意不衝突（身份同一、NAV series 是否相同另驗），故客戶確認表標 `nav_equivalence="UNVERIFIED"`。

### 15.5 測試與揭露

`tests/test_fund_identity_dg2.py` 新增：Sheet 8 例（不注入／注入內建別名表）、命名空間只限該欄、契約違反 12 例、`ACDD01-EQTAL005` 裸碼與網址 4 例、通路表出處、`AGIF-HT5`／`AGIF-HTG` 三種命名空間、MoneyDJ 網址未驗後綴、頁型 5＋5 例與 L1 一致性、多保單身份分離、hook 逐筆不彙總、AST 無持倉欄位、Unknown 3 例；既有三處斷言依 `DEC-2026-10-29-01` 改寫並註明。單組寫成；identity 語意變更，合併前須至少 1 組真正獨立稽核（`PROJECT_RULES.md` 第 8 節）。
