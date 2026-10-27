# 68｜BL-0509 EPS Data Source Probe：第一次真跑結果

> **性質**：研究結果文件（probe／spec）。**不是 Data Source Decision Gate 裁示，不授權接任何正式資料來源，不接正式 signal、不接 AI Brain。** actual／trailing 資料不得冒充 forward。
> **日期**：2026-10-27。**登記**：`docs/BACKLOG.md` BL-0509（研究）、BL-0501（Data Source Decision Gate，本文件供其評估用）。
> **法源**：`DEC-2026-10-27-37`（研究範圍與限制）、`DEC-2026-10-27-40`（BL-0509 為下一優先）；公式背景 `docs/v2/66_market_trend_spec.md` 4.7。
> **標記**：本文件以 FACT（報告內有的事實）／INFERENCE（由事實推出，可能錯）／RECOMMENDATION（建議，可推翻）三種標籤區分。
> **provenance**：由執行組單組寫成，未經第二組獨立驗證；本文件屬 data source 研究，依 `PROJECT_RULES.md` 第 8 節須至少 1 組真正獨立稽核（由總管安排，本組未做）。

---

## 0. 結論先行

| 項 | 結論 |
|---|---|
| 這條路能取到 TWSE 公開資料嗎 | ✅ FACT：以 Actions probe workflow 取數，TWSE 公開端點有 13 個回 200（含 TAIEX、個股本益比、單季 EPS、月營收、swagger）。 |
| 需要客戶開雲端 sandbox Network access 嗎 | INFERENCE：**不需要**，成立範圍僅限「用 Actions probe workflow 取數」這條路。開發沙箱本身仍連不到 TWSE（FACT：`docs/evidence/probe_twse_eps/README.md`）。 |
| NAS proxy 路徑 | ✅ FACT：與直連結果逐端點相同。⬜ **未證明**流量實際經過 NAS（報告沒有出口 IP 證據）。 |
| 市場整體 trailing PE | ✅ FACT：官方端點**沒有**提供市場整體欄位；只有個股本益比。 |
| `implied_trailing_index_earnings` | ⬜ 無法判定：分母（市場 trailing PE）本次沒有來源。**這是「輸入不齊備」，尚非「驗證不成立」。** 維持 research metric。 |
| forward EPS 與成長率 `g` | ⬜ 未取得；維持畫面文字 `⬜ EPS 預估資料未取得，無法計算正式指數情境`。 |
| 授權／更新頻率／發布延遲／修正行為 | ⬜ 全數未驗證（見第 6 節）。 |

---

## 1. 背景（來源為客戶對話指示，repo 內無逐字原文）

以下三點為總管轉達客戶本輪對話指示，**未新增 DEC 編號**：

1. 客戶要求先用既有 NAS 中繼路徑做探測。
2. 客戶撤回「開雲端 sandbox Network access」的要求。
3. 客戶授權推送按鈕分支 `probe/twse-eps-trigger` 來觸發 probe workflow。

本次執行：GitHub Actions run `40521810949`，由 `probe/twse-eps-trigger`（內容等於 main `eb272e9`）觸發；報告內 `trigger_sha` ＝ `executed_sha` ＝ `eb272e931446f95109ea0d44e31ddbda8de6cb80`；報告產生時間 2026-10-27T14:30:58Z（台北 22:30）；`proxy.enabled` ＝ true。

---

## 2. 十項研究逐項狀態

證據出處一律為 `docs/evidence/probe_twse_eps/20261027T143156Z_run40521810949_report.json.gz`（run `40521810949`），以下簡稱「本報告」。

| # | `DEC-2026-10-27-37` 研究項 | 狀態 | 證據與限制 |
|---|---|---|---|
| 1 | TWSE TAIEX | ✅ 有證據 | FACT：`openapi_MI_INDEX` 有「發行量加權股價指數」收盤列；`rwd_MI_INDEX_IND`、`rwd_FMTQIK`、`openapi_FMTQIK`（欄 `TAIEX`）也含指數；`openapi_MI_5MINS_HIST`（O／H／L／C）INFERENCE：報告該端點 `contains_taiex_row`＝false，是否為加權指數只由欄名與 swagger 摘要「發行量加權股價指數歷史資料」推斷。這只證明「可取得」，不是正式 signal。 |
| 2 | TWSE 市場 trailing P/E | ⬜ 市場層欄位未提供；✅ 個股層有 | FACT：`research_metric.market_level_trailing_pe_field_provided` ＝ false。個股本益比在 `openapi_BWIBBU_ALL`（欄 `PEratio`）與 `rwd_BWIBBU_d`（欄 `本益比`）。 |
| 3 | MOPS／TWSE earnings、EPS 實際值 | ✅（TWSE OpenAPI 側）／⬜（MOPS 明細） | FACT：`openapi_t187ap14_L`、`openapi_t187ap06_L_ci` 有已公布 actual 單季 EPS 與損益欄位。`mopsov_index` 只驗可達，**未探 MOPS 財報明細**。 |
| 4 | 能否建立 `implied_trailing_index_earnings = TAIEX / trailing_market_PE` | ⬜ 無法判定 | 分母無官方市場層來源；自行由個股聚合需股本或市值權重與 universe 對齊，本 probe 未取得，口徑未驗證。報告內該值恆為 null。 |
| 5 | universe 是否一致 | ⬜ 未驗證 | FACT：各端點列數不同（第 4 節）；金融類公司損益表在另外端點。尚未做代號對齊。 |
| 6 | 更新頻率 | ⬜ 未驗證 | 單次快照，無法推頻率。 |
| 7 | 發布延遲 | ⬜ 未驗證 | 同上；只有單次觀察（第 5 節）。 |
| 8 | 修正行為 | ⬜ 未驗證 | 需跨日比對 `body_sha256` 與值。 |
| 9 | Missing／stale 政策 | ⬜ 政策未訂；已見到的缺值樣態 ✅ | FACT：`openapi_BWIBBU_ALL` 樣本第 1 筆（1101 台泥）的 `PEratio` 為空字串，`rwd_BWIBBU_d` 同一代號同欄為 `-`（為何缺值，例如是否虧損，報告沒有損益資料，INFERENCE，未驗證）。**必須視為 missing，不是 0**。`出表日期` 是發布日而非財報期間，報告對此類端點標 `publication_date_not_period`，不判 stale。 |
| 10 | 授權／使用限制 | ⬜ 未驗證 | 見第 6 節。 |

---

## 3. direct vs NAS proxy 對照

**報告共 16 個端點**（總管轉述為 15 個；以報告為準）。每個端點各量 `direct`（runner IP 直連，不設 proxy）與 `nas_proxy` 兩條，互不降級。

| 項 | 結果 |
|---|---|
| 兩路徑 `outcome`／`http_status` | FACT：16 個端點兩路徑逐一相同。 |
| 兩路徑 `body_sha256` | FACT：有回應本文的 13 個端點，兩路徑 sha256 相同（報告標 `direct_vs_nas_same_body` ＝ true）。3 個 302 端點未跟隨轉址，本文長度 0，無 sha 可比，只比 outcome 與狀態碼。 |
| 延遲 | FACT：兩路徑分佈不同，例如 `openapi_t187ap06_L_ci` direct 314.4 ms、nas_proxy 2129.9 ms；`openapi_MI_INDEX` direct 1368.7 ms、nas_proxy 1181.5 ms。 |
| 出口 IP | ⬜ 未證明。報告沒有記錄出口 IP。 |

INFERENCE（可能錯）：

- 標記為 `nas_proxy` 的路徑，其回應與直連相同；是否實際經過 NAS 未證明（報告只證明 `PROXY_URL` 已設、`proxy.enabled`＝true）。
- Actions runner 直連目前也能取得這些端點，**目前沒有證據顯示 TWSE 擋 Actions IP**（僅單次快照）。
- 延遲分佈不同只是旁證，不能當作「流量經 NAS」的證明。
- 若未來 production 端需要依賴 NAS 才能取得資料，需另行取證。

---

## 4. 端點清單（FACT，取自本報告）

日期型態：openapi 系列為民國年字串（例：`1151022`）；rwd 系列表內日期為民國斜線字串（例：`115/10/01`），另有頂層 `date` 欄（報告只記其解析後的日期，未存原字串樣本）；t187 系列的 `出表日期` 為民國年字串。

| id | URL（主機＋路徑） | outcome／HTTP | 欄位（摘要） | 筆數 | 來源日期 |
|---|---|---|---|---|---|
| `openapi_MI_INDEX` | openapi.twse.com.tw `/v1/exchangeReport/MI_INDEX` | ok／200 | 日期、指數、收盤指數、漲跌、漲跌點數、漲跌百分比、特殊處理註記 | 267 | 最新 2026-10-22（age 5 日） |
| `rwd_MI_INDEX_IND` | www.twse.com.tw `/rwd/zh/afterTrading/MI_INDEX?type=IND&response=json` | ok／200 | tables（價格指數表 56 列：指數、收盤指數、漲跌、漲跌點數、漲跌百分比、特殊處理註記） | 巢狀 | 2026-10-27（age 0） |
| `openapi_MI_5MINS_HIST` | openapi `/v1/indicesReport/MI_5MINS_HIST` | ok／200 | Date、OpeningIndex、HighestIndex、LowestIndex、ClosingIndex | 15 | 最新 2026-10-22 |
| `openapi_FMTQIK` | openapi `/v1/exchangeReport/FMTQIK` | ok／200 | Date、TradeVolume、TradeValue、Transaction、TAIEX、Change | 15 | 最新 2026-10-22 |
| `rwd_FMTQIK` | www.twse.com.tw `/rwd/zh/afterTrading/FMTQIK?response=json` | ok／200 | 日期、成交股數、成交金額、成交筆數、發行量加權股價指數、漲跌點數 | 16 | 2026-10-27 |
| `openapi_BWIBBU_ALL` | openapi `/v1/exchangeReport/BWIBBU_ALL` | ok／200 | Date、Code、Name、PEratio、DividendYield、PBratio | 1084 | 最新 2026-10-22 |
| `rwd_BWIBBU_d` | www.twse.com.tw `/rwd/zh/afterTrading/BWIBBU_d?selectType=ALL&response=json` | ok／200 | 證券代號、證券名稱、收盤價、殖利率(%)、股利年度、本益比、股價淨值比、財報年/季 | 1087 | 2026-10-27 |
| `openapi_t187ap14_L` | openapi `/v1/opendata/t187ap14_L`（swagger 標題「上市公司各產業EPS統計資訊」） | ok／200 | 出表日期、年度、季別、公司代號、公司名稱、產業別、基本每股盈餘(元)、普通股每股面額、營業收入、營業利益、營業外收入及支出、稅後淨利 | 1086 | `出表日期` 2026-10-27（發布日，非財報期間） |
| `openapi_t187ap06_L_ci` | openapi `/v1/opendata/t187ap06_L_ci`（上市公司綜合損益表（一般業）） | ok／200 | 出表日期、年度、季別、公司代號、公司名稱與多項損益欄，含「基本每股盈餘（元）」 | 1051 | `出表日期` 2026-10-27（發布日） |
| `openapi_t187ap05_L` | openapi `/v1/opendata/t187ap05_L`（上市公司每月營業收入彙總表） | ok／200 | 出表日期、資料年月、公司代號、公司名稱、產業別與當月／上月／去年同月營收及增減 | 1088 | `出表日期` 2026-10-17（發布日） |
| `openapi_swagger` | openapi `/v1/swagger.json` | ok／200 | OpenAPI 規格，共 143 個 path；相關 path 36 個列入報告 | — | — |
| `openapi_swagger_ui` | openapi `/`（首頁） | reachable／200 | — | — | — |
| `mopsov_index` | mopsov.twse.com.tw `/mops/web/index` | reachable／200 | 只驗可達 | — | — |
| `openapi_t187ap06_L` | openapi `/v1/opendata/t187ap06_L` | redirect_not_followed／302 | — | — | — |
| `mops_index` | mops.twse.com.tw `/mops/web/index` | redirect_not_followed／302 | — | — | — |
| `twse_terms_candidate` | www.twse.com.tw `/zh/page/terms.html`（候選網址） | redirect_not_followed／302 | — | — | — |

補充 FACT：

- `openapi_t187ap06_L`（沒有尾碼）不在 swagger 的相關 path 清單內，302 的原因未查；一般業損益表的實際端點是 `t187ap06_L_ci`。
- swagger 另列各業別損益表與資產負債表端點：上市側有 `t187ap06_L_basi`（金融業）、`_bd`（證券期貨）、`_ci`（一般業）、`_fh`（金控）、`_ins`（保險）、`_mim`（異業）；公發公司（`X_`）側有對應同名業別。金融類公司 EPS 需另端點，universe 對齊未做。
- `t187ap14_L`、`t187ap06_L_ci`、`t187ap05_L` 都是已公布的 actual 單季或單月資料。

---

## 5. 觀察到的現象（單次快照）

- FACT：openapi 系列（MI_INDEX、FMTQIK、MI_5MINS_HIST、BWIBBU_ALL）最新來源日為 2026-10-22；rwd 系列同次取得的日期為 2026-10-27，差約 5 日。
- ⬜ 原因未驗證。可能性只有猜測，不寫入結論。
- INFERENCE：若日後要用 openapi 的指數與個股本益比做同日比對，日期對齊是必須先解決的問題（見第 7 節）。

---

## 6. 風險與未解（逐項 ⬜）

1. ⬜ **授權／使用條款**：swagger `info` 有「使用條款」連結，但候選條款頁網址 302 未跟隨，**未讀到條款內文**。
2. ⬜ **更新頻率與發布延遲**：僅單次快照，需多日重複觀察。
3. ⬜ **修正行為**：需跨日比對 `body_sha256` 與值。
4. ⬜ **多日 stale 判定**：報告內的 `stale_after_days`（7 日）只是探測用啟發式，不是正式 freshness 規格。
5. ⬜ **MOPS 實際財報明細**：只驗 mopsov 首頁可達。
6. ⬜ **`t187ap06_L` 為何 302**。
7. ⬜ **兩路徑是否真的走不同出口**（第 3 節）。
8. ⬜ **TWSE 對 Actions IP 的長期可達性**。
9. ⬜ **日期對齊**：openapi 系列落後 rwd 系列約 5 日，與 TAIEX 的對齊口徑未定。
10. ⬜ **universe**：金融類端點、股本與市值權重、下市或暫停交易代號，均未對齊。
11. 風險（INFERENCE）：個股 `PEratio` 空字串或 `-` 若被當作 0 聚合，會扭曲市場層數字；missing 必須排除並揭露，不得補 0。

---

## 7. 對 `DEC-2026-10-27-37` 各限制的遵守說明

| 限制 | 本次如何遵守 |
|---|---|
| 只研究官方 actual／trailing | 只探 TWSE 公開端點與 MOPS 可達性。 |
| 不得把 TAIEX／市場 PE 命名為正式 forward `EPS_base` | 本文件與報告都未使用該命名；報告 `implied_trailing_index_earnings` 恆為 null。 |
| `implied_trailing_index_earnings` 在 universe alignment、PE methodology、denominator consistency、historical validation 完成前只是 research metric | 四項皆未完成（⬜）；本文件不輸出該數值。 |
| 驗證不成立就不用 | 本次屬「輸入不齊備」，**尚未判為驗證不成立**；如何處置待後續證據。 |
| 歷史 EPS 成長 ≠ forward `g` | 本次取得的是 actual 單季與月營收，未推算任何成長率，也不作為 `g`。 |
| 不接正式 signal、不接 AI Brain、不接 production 資料來源 | probe 腳本只做唯讀 GET；本文件不授權接線。 |
| 付費／授權預估源另回 Data Source Decision Gate | 本次未涉及，仍走 BL-0501。 |
| missing ≠ 0 | 腳本設計為無來源日期時標 `no_source_date`、不補值（本次報告無此狀態）；第 2 節第 9 項明記空字串與 `-` 為 missing。 |

---

## 8. 建議下一步（RECOMMENDATION，可推翻）

1. **多日重複 probe**（建議連續數個交易日，含財報季前後各至少一次），觀察更新頻率、發布延遲、修正行為，以及 openapi 與 rwd 系列日期差是否穩定。
2. **條款頁人工閱讀**：由人讀 swagger `info` 連結指向的條款內文，再判斷是否可作為正式來源；不要由自動化腳本跟隨轉址去讀。
3. **出口 IP 證據**：若之後仍要主張「走 NAS」，需另設可驗證出口 IP 的探測。
4. 以上資料備妥後，由 ChatGPT 協作助手評估，再進 Data Source Decision Gate（BL-0501）。

**本文件不是 Gate 裁示，不授權接任何正式資料來源。** 在 Gate 裁示前，畫面顯示 Missing。BL-0495、BL-0496 仍待客戶裁示，方向性 AI action 不得提前實作。

---

## 9. 這份文件沒有查證的部分

- 本文件的 16 個端點、欄位、筆數、日期與延遲，皆由讀本報告 JSON 取得；報告本身由 Actions 產生，本組無法在開發沙箱重現。
- 報告檔 `body_sha256` 只用於比對兩路徑，本組未下載 TWSE 原文獨立核對。
- 「openapi 落後 rwd 約 5 日」只有這一次快照。
- swagger 內是否有更新頻率或授權欄位，只看了報告摘要（`relevant_paths` 的 summary），**未逐字讀 swagger 全文**。
- 本文件由執行組單組寫成，未經第二組獨立驗證。
