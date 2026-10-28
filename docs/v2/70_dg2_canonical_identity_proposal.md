# 70 — DG-2 canonical identity：Decision Gate 提案（待客戶裁示，未核准）

> **狀態：待客戶裁示，未核准，不開始 production refactor。** 本文是 `docs/v2/69` 第 9 節 DG-2 的具體 contract 提案，依客戶 `DEC-2026-10-28-03` 第 5、6 項（先做 C1～C9 與獨立稽核，再提 DG-2；DG-2 核准前不動 canonical identity production 程式）撰寫。
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
