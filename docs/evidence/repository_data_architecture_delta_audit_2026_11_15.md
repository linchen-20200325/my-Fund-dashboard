# 基金 Repo 資料新鮮度／規格現行性／架構差異稽核（2026-11-15）

> **性質：受客戶 2026-11-15「檢查 GitHub 資料缺漏／過期與架構，能安全修正就修正或刪除」授權的抽樣 delta 稽核證據；NOT SSOT、NOT 新金融契約、NOT production 驗收。**
> GitHub 驗證基準：`main=816e6c816ceeb2d58c46e450351cd1de3419cf04`；主線無未結 PR，**另有規劃存檔 Draft PR #1251**（僅一份 `docs/evidence/new_ui2_five_optimizations_checkpoint_2026_11_15.md`）。此 SHA 與 PR 數是**觀測當時快照**，使用前必須再次查 GitHub。
> 範圍：Git tree 全量路徑／大小清單（1,571 個 blob，其中 `docs/` 358 個、Python `.py` 1,126 個）；root 核心規格檔頭與選定段落、`PROJECT_RULES.md` 文件地圖、`ui_v3` 預覽入口／registry／VM、`data_cache/metadata.json`、`cache/nav/TLZF9.json`、`snap.json` 日期、指定工作流程與最新 Actions 摘要、先前已合併的 2026-11-12 資料層稽核。**未逐行審查 1,571 檔、未跑本地 Python／Streamlit、未讀取真實 Google Sheets／Cloud、未核對 live provider。不得把這份報告當「全 repo／資料品質全部 PASS」。**
> **專案既有權威不變**：`CLAUDE.md` → `PROJECT_RULES.md`／`PROCESS.md` → 子法 1＋正式修正案 #8、frozen `docs/v2/44_fund_ui_ssot.md`、`docs/v2/79_final_ui_contract_freeze.md`、`docs/v2/80_new_ui2_architecture_proposal.md`、正式 `docs/DECISIONS.md`；`docs/BACKLOG.md`／`docs/HANDOFF.md` 為待辦／導航。不得由本稽核報告覆寫正式效力。

## A. 已核實的不一致與這次安全修正

| 編號 | 來源／查到的問題 | 結果與證據 | 本批處置 |
|---|---|---|---|
| D-01 | root `Requirements.md`（2026-04-13）首行自稱「系統需求真理來源」，但實際要求股票策略選股、ETF、股債比自動建議、個股財報與 K 線；與目前共同基金 New UI2 五頁（`PROJECT_RULES.md`、80）不能共作一套現行規格 | **CONFIRMED 文件現行性衝突**；不是證明 legacy code 已刪 | 在 root 原檔首段**追加 NOT CURRENT 導覽註記**，指回正式 New UI2 SSOT；保留原文與既有檔名 |
| D-02 | root `SPEC.md` 舊版日期 2026-05-05，含一律 `df.ffill()` 對齊等強制說法；若直接套用到 New UI2 可能抹除來源缺項或真實日期 | **CONFIRMED 舊文字存在、New UI2 契約不等於原本 blanket rule**；不因此宣稱所有 legacy ffill 都是 bug | 僅追加規格現行性註記，要求以正式資料／日期／缺值 Gate 為準，不修改任何公式、data cleaning 或現有程式 |
| D-03 | root `ARCHITECTURE.md` 標示 v12.0、2026-06-30 與「至今有效」，不能完整代表 2026-11 的 `ui_v3/` New UI2 遷移架構 | **CONFIRMED 完整性／版本落差**；仍可作 legacy 程式歷史與分層參考 | 僅追加歷史架構導覽註記，引用 79、80、DEC 與現行程式；不重寫架構，不刪任何模組 |

以上三份原文及排序保持不變，僅於檔頭增加說明；不是以文件名或建立日期判定所有內容無效。root `STATE.md`、`BACKLOG.md`、`TODO.md` 已明示歷史用途，**不再重做標記，也不刪除**（`PROJECT_RULES.md` §0.4）。

## B. 過期／缺漏／未驗資料（不能以填值或刪檔解決）

| 編號 | 實際證據 | 風險與結論 | 安全的下一步／禁止事項 |
|---|---|---|---|
| DATA-01 | `data_cache/metadata.json`：`updated_at=2026-11-08T04:07:01+00:00`；FRED `last_updated=2026-11-05`（13,829 列）、VIX／SPX／TWII 各最後觀測 2026-11-06。GitHub `commits?path=data_cache/metadata.json` 最後紀錄 2026-11-08，本次觀測為 2026-11-15；`update_macro_history.yml` 宣告每週日更新。 | **CONFIRMED 存檔時間落後、是否超過正式 freshness 規則 NOT VERIFIED**。本次查最近 100 筆 Actions 未見本週 `update_macro_history` 執行，**這個觀測不等於證明排程停用或失敗**。metadata 的 `last_error=null` 並不代表每個 series 無缺漏。 | 請按既有 workflow／授權檢查：最近排程是否 dispatch／cancel／skip、步驟日誌、有無最新 commit、上游是否提供新資料、每個 series 的完整度。**不得把新日期寫入 metadata 來假裝已更新；不得重建 parquet 或接 New UI2，除非另外取得正式 Gate。** |
| DATA-02 | 已合併 `docs/evidence/ui_data_contract_audit_2026_11_12.md` §1.2 與 `docs/evidence/reuse8_offline_evidence_2026_11_09.md` 指出：宣告的 FRED series 有未落地項（例：PPIACO、PCOPPUSDM），且歷史 SPX／VIX 某日期需再次對拍。 | **既有缺口、不是本批新的 live 驗證發現**。本次未打開 parquet 原始位元組或重跑 provider；不能擅稱今天仍是相同列數與問題。 | 避免重做原研究；先檢查既有 QA／修復決策與最新 source→cache 校驗，只補增量差異；不得用 `last_error=null` 冒充全部 series COVERED。 |
| DATA-03 | `cache/nav/TLZF9.json`：`updated_at=2026-07-22`，共 10 個稀疏歷史 NAV 點，觀測日期橫跨 2011～2026、最近點為 2026-04-23、`source=cache_only`；`tests/test_nav_history_quality_w1.py`／`tests/test_nav_cache_quality_gate.py` 對這種稀疏快取設防禦測試。 | **過期又稀疏的實物樣本，仍有 regression／歷史用途**；不能單憑舊日期判斷可以安全刪除，也不能宣稱這是當前 NAV。 | 保留作測試與問題追溯；後續核查所有 production fallback 是否有正式完整度／stale Gate；**本批不刪、不替換值**。 |
| DATA-04 | root `snap.json` 的 `dumped_at=2026-08-10`；`scripts/compare_inception_years.py` 與 `scripts/diagnose_ret_3y_fallback.py` 提供 `--snapshot` 離線重放。 | **歷史診斷快照**，不是今日基金全市場或最新持倉；不能直接覆寫或當 New UI2 producer。 | 保留其回放能力；若日後確認不再需要，須先做引用／測試／個資保護稽核再提出刪除 Gate。不要在本報告複製快照內基金清單。 |
| DATA-05 | 最近 GitHub Actions 中 `weekly_nav_backfill.yml` 有排程 run 成功（例如 2026-11-14 run `43622735342`），但本次沒有讀取最終 `nav_history` Sheet，也無真實 Active Sheet 分母。 | **workflow success ≠ NAV 筆數成功增加／Cloud 可用／真實持倉完成**。BL-0545 仍 BLOCKED（使用者已暫不提供真實輸入）。 | 遵循既有 NAV 品質與獨立 QA，不主動索要 secrets、ID 或真實持倉，不猜填空值。 |

## C. 架構現況與剩餘 Gate

| 編號 | 程式／正式文件 | 現況判斷 | 待處置（不代表已授權施工） |
|---|---|---|---|
| ARC-01 | `ui_v3/shell/registry.py`、`ui_v3/app_preview.py` | 五頁 IA 已存在，但只有 `mkt` 被註冊為 Preview renderer；`ast`／`exp`／`ai`／`set` 仍未掛頁。`ast` 的 S-VM 純函式在 #1248 已合併，**不等於畫面已完成**。 | 不修改 registry 或正式入口；下一個 💼 可見 fixture renderer 需獨立 UI／視覺 Gate。 |
| ARC-02 | `ui_v3/viewmodels/components.py`、`ui_v3/design/theme.py`、`shared/ui_semantics/rules.py` | 既有共用狀態 ViewModel、色票與字樣單一來源，不能推論完全沒有 shared primitives。 | 先重用，再判斷是否有可抽取的重複 UI Renderer；不建第二套狀態字樣表。相關規劃見另行進行中的 #1251 Draft。 |
| ARC-03 | `docs/HANDOFF.md` 基準仍指 `e07c6722`，main 本次查為 `816e6c81`；文件自身提醒為「觀測快照」而非即時狀態。 | **歷史 SHA 落差是真的，但不等於 HEAD 真的倒退／PR 未合併**。HANDOFF 每 merge 更新造成自我遞迴，正式政策待 Gate（#1250 已明示）。 | 先維持 GitHub-first，保留 last-verified SHA＋時間；是否調整更新規則與 PR 錨點，由客戶正式裁示後再修 `PROJECT_RULES.md`，不在本批擅改。 |
| ARC-04 | D2／FX／DG2／OneBrain | D2 的 17 列目前僅 4 列**契約文字**核准（R-ID-1、R-NAV-1、R-NAV-2、R-NAV-5），13 列 Pending；`FX_OBS_DATE_RULE_VERIFIED=False`（2026-11-12 既有讀碼稽核）；DG2 shadow 未轉正式。 | 不做 FX、正式 NAV identity／formula、OneBrain runtime 或 Digest schema；既有三方案 Gate 與 BL-0545 維持原樣。 |
| ARC-05 | root 歷史資料、`docs/evidence/history/` 與 `docs/BACKLOG.md`／`docs/DECISIONS.md` | 眾多歷史與現行資料共存，但既有規範要求保留 provenance／sha256；`docs/evidence/history/README.md` 有保全規則。 | **不做「日期舊就全刪」的危險清理**。後續如要瘦身只能列精確檔案、引用數、hash／可回滾路徑，做獨立 PR 和 QA。 |

## D. 僅此 PR 執行的修改與未做的事

**本次已實作**：
1. Root `Requirements.md` 加「歷史需求、股票 ETF 不等於 New UI2」醒目導覽。
2. Root `SPEC.md` 加「legacy 規格，不能把 blanket ffill 當 New UI2 依據」醒目導覽。
3. Root `ARCHITECTURE.md` 加「v12.0 歷史架構，現行 New UI2 用 79／80／程式」醒目導覽。
4. 本稽核文件作「經觀測的差異清單」，不是平行 BACKLOG／DEC／HANDOFF。

**本次沒有改動**：任何實際 Parquet／JSON 資料、NAV／Sheet、snapshot、測試、Python／UI、workflow、凍結 44、正式 79／80、`PROJECT_RULES.md`、`CLAUDE.md`、`docs/BACKLOG.md`、`docs/DECISIONS.md`、`docs/HANDOFF.md`。**未刪除檔案**：找到的舊檔有 legacy、測試或歷史證據用途，現階段無足夠無依賴證據證明安全刪除。

## E. 驗收／接續，避免 audit 變成無止境施工

- **原則**：這是檔頭導覽最小修正，root 三檔既有本文內容需逐字不變；PR diff 不得擴張到別處。除文件現行性警示外，不能修改金融算法／權限。
- **非作者 QA**：獨立審查四檔，確認 ① 三個舊入口確實有誤導、② 沒有把其他文件地位自創為新的憲法、③ `ffill` 條款的措辭僅限 New UI2，不認定所有 legacy 用法錯誤、④ DATA-01～05 的已驗／待驗分類嚴謹且沒有虛構即時資料、⑤ PR #1251 未被覆蓋、沒有撞檔。
- **CI**：最新 exact-head Fast、Schema、Visual、Slow 逐項 success 才能宣稱 MERGE-READY；此文件不能替代 Run Logs 或獨立 QA。可在完成前維持 Draft，不直接合併 main。
- **接續**：如本 PR 尚未合併，應先核對本 PR head、diff、CI／QA，繼續完成其原 scope，不重做已合併的 #1246～#1250；下一個資料實務 Gate 是 DATA-01 的宏觀快取取數／排程原因核對，而非把時間戳直接往前改。
- **責任界線**：本輪為 ChatGPT 經 GitHub connector 的唯讀觀測＋文件修正；沒有完整本機執行環境與 live secrets，任何未觀測結果標 NOT VERIFIED，留給獨立專案 QA。

## F. 主要可回查的證據

- `Requirements.md`；`SPEC.md`；`ARCHITECTURE.md`；`PROJECT_RULES.md` §0.4。
- `ui_v3/shell/registry.py`；`ui_v3/app_preview.py`；`ui_v3/viewmodels/components.py`；`ui_v3/design/theme.py`。
- `data_cache/metadata.json`；`.github/workflows/update_macro_history.yml`；`scripts/update_macro_history.py`；GitHub `commits?path=data_cache/metadata.json`。
- `cache/nav/TLZF9.json`；`snap.json`；`tests/test_nav_cache_quality_gate.py`；`tests/test_nav_history_quality_w1.py`。
- `docs/evidence/ui_data_contract_audit_2026_11_12.md`；`docs/evidence/reuse8_offline_evidence_2026_11_09.md`；`docs/evidence/new_ui2_spec_supersession_data_capability_review_2026_11_06.md`。
- [Issue #1228](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1228) 為既有六項品質補強，不能重造相同工單；[PR #1251](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1251) 保存先前五項優化規劃；本 PR 只做此次資料／架構稽核。
