# D2 R-NAV-4／R-NAV-6 候選研究與最小 Decision Gate 核准包（2026-11-17）

> **性質：候選，不構成核准。** 本檔只整理 R-NAV-4（`source_tier`／供應者）與 R-NAV-6（`ccy_source`）的現況、選項與最小問法；兩列在 D2 **維持 Pending**，不升格、不新增 DEC、不改任何程式／測試／Schema。登記不構成動工授權（`CLAUDE.md` §-1）。
> 基準：main `0ac6c086`（2026-11-17 `git fetch` 實查）。**單組作者整理，未經獨立 QA；全稱句一律標「單組未驗」。**
> 讀碼環境：本沙箱，僅 grep／讀檔，**未跑任何測試或 live**。

## 1　先講結論（總管推薦寫最前面）

- **R-NAV-4 推薦方案 A：只核 `source_tier`**（表欄，四值值域，`nav` 列恆為「淨值」）。補不到 Provider 名稱，這是已知限制，不是遺漏。
- **R-NAV-6 推薦方案 A：維持 Pending。** 理由是它與 `DEC-2026-11-14-07` 對 R-NAV-5 的限制 (iii)(iv) 有張力（見 §4）。
- **最小問法（見 §7）**：「R-NAV-4 只核 `source_tier`（A）、R-NAV-6 維持 Pending」。
- **重要限制**：`onebrain_evidence_coverage_gap_audit_2026_11_08.md` §3 的缺口 1「Provider 名稱與 `ccy_source`」**無法靠上述最小核准解決**——需要新承載欄位（Schema 變更），不在 D2 現有授權內（§6）。

## 2　現況事實（已對現檔核對）

### 2.1　三個容易混淆的「source」

| 名稱 | 住處 | 值／值域 | 實測依據 |
|---|---|---|---|
| `source_tier`（表欄） | `services/v2_tables/contract.py::SOURCE_TIER_VALUES` ＝ `("淨值", "配息", "市場指標", "其他")`；`nav` 列由 `services/v2_tables/nav_dividend.py` 的 `SOURCE_TIER_NAV = "淨值"` 賦值 | 封閉四值；**nav 列恆為「淨值」** | 讀 `contract.py:40`、`nav_dividend.py:83`、`contract.py` 值域檢查（不在值域→該列不寫）。**對 NAV 列資訊量為零**：不辨識供應者 |
| `provenance[fund_code].source`（旁路，非表欄） | `nav_dividend.py` 組 `out["provenance"]` 時取 `attrs.get("source")`（符號式引用：`nav_dividend.py::_rows_from_segment`、`_chain_ccy_gate` 等組 `out["provenance"]` 處；不寫行號，行號會漂移） | L1 `attrs["source"]` 字串，格式「供應者前綴:細節」，例 `FundClear:GetFundNAV`、`AllianzGI:JSON_API`、`Cnyes:fund_nav_api`（`repositories/fund/sources.py` 多處）；**無封閉值域** | `grep 'attrs\["source"\]' repositories/fund/` 見到上列字面。**缺值不阻擋寫列**（`d2_contract_approval_prep_2026_11_12.md` R-NAV-4 ④ 讀碼結論；本組複查 `nav_dividend.py` 組 provenance 處未見對 `source` 設閘，單組未驗） |
| `chain.data_source`（A 鏈旁路） | `attrs["v2_chain"]["data_source"]`（`nav_dividend.py:664` 定義 `CHAIN_ATTR`、`:1031` 賦值），值來自 `fund_orchestration.py` 的 `result["data_source"]`（例 `moneydj_legacy_scrape`） | **另一套小寫字彙**，與上列「供應者前綴:細節」格式不同 | 讀 `nav_dividend.py:1031`、`fund_orchestration.py:1957`。完整值域 **NOT VERIFIED** |

另：1Y 報酬的 `source`（`R-PERF-4`）是**第四種不同東西**，不在本檔範圍（`d2_contract_approval_prep_2026_11_12.md` N3）。

### 2.2　`ccy_source`（R-NAV-6）

- 來源：`nav_dividend.py::resolve_nav_ccy`（`:439`），回傳 `(ccy, ccy_source, withheld_code, reason)`。
- 值：`holding_user_input`（`LABEL_SOURCE_HOLDING`，持倉手填）／`source_reported`（序列自報，`:470`）／`meta:<來源>`（🔍 入口，`declared_ccy_source`）。白名單 `_RESERVED_CCY_SOURCES = (LABEL_SOURCE_HOLDING, "source_reported")` 防撞名（`:154`、`:173`）。
- **衝突或缺值 → `ccy_source` 為 `None`**（`resolve_nav_ccy` 於衝突／缺值時回 `None, None, WITHHELD_CCY_*`；A 鏈閘擋下時 provenance 亦寫 `ccy_source: None`，`:739`）。
- **A 鏈路徑上 `source_reported` 不出現**：`build_nav_table` 的 A 鏈刻意**不採用** A 鏈回的幣別，序列 attrs 的 `currency` 一律拿掉、只用持倉手填（`nav_dividend.py:972-973`、`:1013`）。本組讀此兩處**支持**核可包 §3.2 的推論（`d2_next_batch_r_nav_2_5_3_approval_pack_2026_11_14.md` §3.2 已知落差 (2)）；但「所有生產入口皆如此」是全稱句，**單組未驗**；直接呼叫 `rows_from_nav_series` 路徑仍可能產出 `source_reported`。**須重驗後才可寫進契約文字。**
- **範圍**：R-NAV-6 本次僅就 **nav 列**討論，配息路徑不在範圍。補充事實：`ccy_source: "source_reported"` 也會在**配息路徑**寫入（`nav_dividend.py::rows_from_dividends` 內組 provenance 處，有列時固定寫 `source_reported`；2026-11-17 grep 確認），所以「`source_reported` 只在直接呼叫 `rows_from_nav_series` 時出現」僅對 nav 成立。
- 位置：旁路 `provenance[fund_code].ccy_source`，**不在 frozen 44 §4.2 表欄內**；`ui_v2` 三頁不渲染（核可包 §五；單組未驗）。

### 2.3　已核准的相鄰限制（`DEC-2026-11-14-07`，已逐字核對）

R-NAV-5（`T-NAV5`）已核准，並附客戶限制：(iii)「序列自報幣別僅作衝突比對，不可誤寫成正式標籤優先來源」；(iv)「**不核准 `ccy_source` 獨立契約**、FX 方向、TWD 換算、跨幣別聚合或正式資料准入」。該 DEC 授權範圍並明列**不授權** R-NAV-3／4／6。→ R-NAV-4／6 仍在 Pending，核准欄位數為 4（R-ID-1、R-NAV-1、R-NAV-2、R-NAV-5）。

## 3　R-NAV-4 選項

| 方案 | 內容 | 好處 | 風險／代價 | 風險等級 |
|---|---|---|---|---|
| **A（推薦）** | 只核 `source_tier`：契約註明「恆為淨值、不辨識供應者」；供應者名稱**不進契約** | 不碰供應者名稱規則；與已核 R-NAV-2／5 同為「契約文字」層級 | 補不到 Provider 名稱（gap audit 缺口 1 不解） | 低 |
| B | A ＋ 核旁路 `provenance.source` | 契約多一條來源描述 | 牽動「供應者缺值不阻擋寫列」是否可接受；且 `source` 常含取得時間／路徑語意，與 `DEC-2026-11-14-07` 暫緩的 R-NAV-3（來源時間語意）相近，**不建議同批** | 中 |
| C | 全 Pending | 零新增語意 | UI 與 Evidence 仍無法引用「來源」的契約依據 | 低 |

不論選哪個，**都不新增 provider、不改 NAV source precedence、不新增 `source` 表欄**（沿用 `d2_contract_approval_prep_2026_11_12.md` R-NAV-4 ⑧）。「三種 source 不可合併」是新語意，另案（核可包 §五）。

## 4　R-NAV-6 選項

| 方案 | 內容 | 與限制 (iii)(iv) 的關係 | 風險等級 |
|---|---|---|---|
| **A（推薦）** | 維持 Pending | 不與任何已核限制衝突 | 低 |
| B | 作為 R-NAV-5 的一句附註（核可包 §3.2 表中的 C 方案概念） | 附註即新語意，須獨立 QA；若文字把 `source_reported` 寫成「優先來源」會直接違反 (iii) | 中 |
| C | 獨立核准 `ccy_source` 契約 | **與 (iv)「不核准 `ccy_source` 獨立契約」的精神衝突**；若要走此路，須客戶明示推翻或修正該限制 | 高 |

## 5　Gate 現況表（本檔涉及的 Gate；皆未因本檔改變）

| Gate | 現況 | 與本檔關係 |
|---|---|---|
| 正式 Schema | 未授權（D2 僅核契約文字，`DEC-2026-11-14-07` 授權範圍明寫不授權 Schema） | 新增承載欄位＝Schema 變更，**不可**借最小核准 |
| Identity（DG2／S7） | R-ID-2／3 擋在 S7；`DG2_SHADOW_ENABLED` 預設關 | 與 R-NAV-4／6 無直接關係 |
| 公式 | 無公式變動 | 本檔不涉及 |
| Provider | 不新增、不替換（`CLAUDE.md` Stop Gate） | 供應者名稱入契約是規則題，不是新增 provider |
| FX | 閘門關閉，`FX_OBS_DATE_RULE_VERIFIED` 為 False（`market_indicator.py`；`DEC-2026-11-08-02`） | `ccy_source` 與 FX 方向／TWD 換算無關，但勿混談 |
| Digest／OneBrain | 未授權 | gap audit 缺口 1 屬 Digest 層需求，非本檔授權 |

與已核各列關係：R-NAV-1（`fund_code`）、R-NAV-2（`nav_date`）、R-NAV-5（`ccy`）已核；R-NAV-3（`fetched_at`）暫緩；R-NAV-4／6 與 R-NAV-1／2／5 **不互相依賴**，可獨立決定。

## 6　gap audit 缺口 1 為何最小核准解不了

缺口 1（Provider 名稱與 `ccy_source`，`onebrain_evidence_coverage_gap_audit_2026_11_08.md` §3）要的是「UI／Evidence 能引用資料由誰說」。即使 R-NAV-4＝A、R-NAV-6 維持 Pending：表欄 `source_tier` 對 nav 恆為「淨值」，供應者名稱與 `ccy_source` 仍只在旁路 `provenance`，**沒有契約承載欄位**。要解需新增表欄或新結構＝Schema 變更，**不在 D2 現有授權內**，須另走正式 Schema Gate。本檔不建議此時提出。

## 7　最小問法（若客戶要處理這兩列）

> **R-NAV-4 只核 `source_tier`（A）、R-NAV-6 維持 Pending。**

選 A 的效果：R-NAV-4 改已核准（註明「恆為淨值、不辨識供應者」），核准欄位數 4 → 5；R-NAV-6 不變。**若客戶沒有明示，兩列維持 Pending。** 目前不建議主動向客戶發問（無下游阻塞；登記不構成動工授權）。

## 8　NOT VERIFIED

1. `chain.data_source` 完整字彙與是否可缺值（未窮舉）。
2. `provenance.source` 缺值不阻擋寫列：沿用 2026-11-12 prep 的讀碼結論，本組僅局部複查。
3. A 鏈以外所有生產入口是否都不出現 `source_reported`（全稱句，單組未驗）。
4. `ui_v2` 三頁是否皆不渲染 `ccy_source`（沿用核可包單組結論）。
5. 真實持倉資料下 `ccy_source` 各值的分布（BL-0545 BLOCKED，無從量測）。
6. 本檔未跑任何測試；引用的測試名稱（如 `test_nav正例_逐欄照44_幣別取持倉手填_provenance記來源`）沿用 prep 文件，**未重跑**。

## 9　來源

`docs/evidence/d2_contract_approval_prep_2026_11_12.md`（R-NAV-4／6 列）；`docs/evidence/d2_next_batch_r_nav_2_5_3_approval_pack_2026_11_14.md`；`docs/evidence/d2_min_approval_pack_r_id_1_r_nav_1_2026_11_13.md`；`docs/evidence/onebrain_evidence_coverage_gap_audit_2026_11_08.md`；`docs/DECISIONS.md` `DEC-2026-11-14-07`；`services/v2_tables/contract.py`、`services/v2_tables/nav_dividend.py`、`repositories/fund/sources.py`。
