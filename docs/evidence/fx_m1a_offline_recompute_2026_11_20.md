# D8 FX 補證 M1-a 離線重算與 M1-b 文字核對（2026-11-20，docs-only）

> **單組、未經第二組複驗。** 唯讀、離線；未觸發 workflow、未連網取新資料；`FX_OBS_DATE_RULE_VERIFIED` 未動（FX Gate 維持關閉，本檔不推薦開閘）。基準：main `747c7585`（本檔原稿以 main `c7a1349f` 撰寫，2026-11-20 保存 11-08 報告時改讀已保存檔重跑並修訂，見 §1.1）。
> 標籤：FACT＝本組本批實跑／實讀；INFERENCE＝推論可被推翻；RECOMMENDATION＝建議，不構成裁示；NOT VERIFIED＝未驗。

## 0. 結論先行

| # | 結論 | 標籤 |
|---|---|---|
| 1 | M1-a 所指「既有報告」＝ `results/20261108T063652Z_run42455423910/report.json`（補證表 §1(1) 與 E1174 §1）。本組在本機取得（commit 物件 `6b180d6f` 在本機 git 中可 `git show`），sha256 與 E1174 §1 記載一致 | FACT |
| 2 | 以 E1174 附錄腳本（原樣抽出）加一支本組自寫腳本重算，E1174 §3.2／§3.4／§4／§6 的數字**全部可重現**，無不一致項（見 §2）。但這是同一份資料的**算術重現**，不證明 Yahoo 的語意，也不是獨立資料來源 | FACT／INFERENCE |
| 3 | M1-b＝**NO-RUN**（Work 獨立結論，ChatGPT 總管轉述〔待核〕，非 DEC、非逐字；原作者推論亦為視同相同方法）。預設參數重跑與 11-08 那次的**參數完全相同**，僅變更日期不構成新方法；新取數須另行授權；FX Gate 維持關閉（見 §3） | FACT／INFERENCE |
| 4 | 在不觸發 workflow、不取新資料的前提下，窗口內**沒有任何能新增觀測的路徑**；只剩「離線重讀已保存報告」，且 11-08 報告保存至 main 已於本批完成（見 §4） | INFERENCE／FACT |
| 5 | 2026-11-20 改讀**保存檔**（`gzip -dc` 後 sha256 與原檔一致）重跑附錄腳本與獨立腳本，輸出與原稿一致；原稿「無法重算」兩項（fixed_offset_scan 逐 k、各期最大差值）已補算，**無不一致項**（見 §2） | FACT |

## 1. 輸入與可重現性

| 項目 | 內容 | 標籤 |
|---|---|---|
| 11-08 報告取得 | `git show 6b180d6fd3d77f255df8bcebbcf470027abf79c3:results/20261108T063652Z_run42455423910/report.json`（commit 時間 2026-11-08T06:36:53Z）；`sha256sum` ＝ `8fe1aca5de4236847ee24c9c8abc736b828c4d25a81f7074948a4c9d001be5a9`，與 E1174 §1 同；大小 908102 bytes | FACT |
| 本機 ref 狀態（原稿撰寫時） | `origin/probe/fx-obs-date-results` 在撰寫當時的本機**不存在**；報告只靠該 commit 物件在本機存活，**當時不在 main**。**此狀態已於 2026-11-20 本批改變**：報告已保存至 main（見 §1.1） | FACT（已被 §1.1 取代） |
| 10-14 舊報告 | `docs/evidence/probe_fx_obs_date/20261014T064729Z_run38524215912_report.json.gz`（`gzip -dc` 後使用） | FACT |
| 腳本 | 四支皆唯讀、離線、純標準庫，全文收錄於本檔附錄 A：`recompute_appendix.py`（E1174 附錄原樣抽出）、`indep_recompute.py`（原作者自寫，不沿用附錄邏輯）、`scan_recompute.py`（逐 k 重算 fixed_offset_scan，2026-11-20 新增）、`maxdiff_recompute.py`（各期最大絕對差，2026-11-20 新增）。用法皆為 `python3 -I <腳本> <11-08 報告.json> [<10-14 報告.json>]`。暫存目錄中的副本不是持久證據，以附錄 A 為準 | FACT |

### 1.1 保存 11-08 報告至 main，且重算改讀保存檔（2026-11-20，FACT）

| 項目 | 內容 |
|---|---|
| 保存檔 | `docs/evidence/probe_fx_obs_date/20261108T063652Z_run42455423910_report.json.gz`（大小 136739 bytes；依該目錄 `README.md` 既有慣例：`git show` 輸出逐位元組不改、`gzip -9 -n`） |
| 原檔 sha256 | `8fe1aca5de4236847ee24c9c8abc736b828c4d25a81f7074948a4c9d001be5a9`（開頭 `8fe1aca5`；原大小 908102 bytes） |
| 保存檔 `gzip -dc` 後 sha256 | `8fe1aca5de4236847ee24c9c8abc736b828c4d25a81f7074948a4c9d001be5a9`，**與原檔一致**（2026-11-20 實跑） |
| 保存檔本身 sha256 | `031c3bba04658c98de5f5162e0141d51fef87d4802c966412cb937cfd2689531` |
| 重算輸入 | 本批所有重算的 11-08 輸入皆為「`gzip -dc` 該保存檔」所得；10-14 輸入為同目錄既有 `20261014T064729Z_run38524215912_report.json.gz`（`gzip -dc` 後 sha256 `fd1be036…`，與該目錄 `README.md` 記載一致） |
| 範圍 | 只保存既有檔：未觸發 workflow、未連網、未取新資料、未改任何 `.py`／workflow／`FX_OBS_DATE_RULE_VERIFIED` |

## 2. M1-a 逐項比對（E1174／補證表 宣稱 vs 本組重算）

| # | 宣稱（出處） | 本組重算結果 | 判定 |
|---|---|---|---|
| 1 | USD 23 個可比日分 P1／P2／P3＝13／5／5（E1174 §3.2） | 獨立腳本 n＝13／5／5 | 一致 |
| 2 | USD 與 UTC 當日 00:00 起點小時價中位數絕對差 P1 0.0034%、P2 0.0028%、P3 0.0037%（§3.2） | 獨立腳本：0.0034／0.0028／0.0037 | 一致 |
| 3 | 各期最大絕對差 0.0249／0.0624／0.0251%；全期 0.0624%（§3.2、補證表 §1(1)） | 附錄腳本 S4：0.0249／0.0624／0.0251（全期 0.0624）。2026-11-20 補：`maxdiff_recompute.py`（不沿用附錄邏輯）USD P1 0.0249（10-14）、P2 0.0624（10-29）、P3 0.0251（11-06），全期 23 日最大 0.0624（10-29）；同腳本 EUR 最大 0.2173／3.3853／2.9709、JPY 1.1809／1.1594／1.1719 與附錄 S4 同 | 一致（兩支不同腳本；仍同一份輸入） |
| 4 | 值對應時刻不隨倫敦夏令移動：以倫敦當地 00:00 比，P1 0.0323%、P2 0.0028%、P3 0.0037%（§3.2） | 獨立腳本以 UTC 00:00 為基準掃 −3～+3 小時：三期最佳皆為 offset 0（P1 offset −1＝倫敦 00:00 為 0.0323%）。附錄 S4 同 | 一致 |
| 5 | 報告自帶合併掃描 USD 最佳 k＝+1、0.0051%、n＝22（§3.2、§3.4） | 2026-11-20 補算：`scan_recompute.py` 對 USD／EUR／JPY 各 33 個 k（−6～+26）、`by_end` 與 `by_start` 兩版，共 **198 組（n、中位數、中位絕對值）與報告自帶 `fixed_offset_scan` 逐組比對，0 不一致**；日 K 根數 22＝報告 `daily_bars`。USD 兩版最小中位\|差\|皆 **0.0051%、k＝+1、n＝22**；EUR 終點版 0.1148%（k＝+0，n＝17）、起點版 0.1120%（k＝−1，n＝17）；JPY 終點版 0.7827%、起點版 0.6338%，皆在 k＝+26 | 一致（原稿「無法重算」已補算；演算法為依該函式註解的獨立重寫，與報告同一份輸入） |
| 6 | 「UTC 00:00」與「台北 08:00」本資料分不出（§3.2、§8-4） | 數學上同一瞬間，無新資料可分 | 一致（邏輯，非資料） |
| 7 | EUR 日 K 523 根中 45 根 `\|close/open−1\|>1%`，42 根週一，週一 close 比 open 低 1.66%～3.41%（§4 疑點 1） | 獨立腳本：45／42、週一範圍 −3.41～−1.66；USD 0、JPY 3 且皆非週一 | 一致 |
| 8 | 週一異常冬令集中：週一共 103 根（GMT 44、BST 59），>1% 者 GMT 40、BST 2（§4） | 本組計數：Mon GMT 44、BST 59、>1% GMT 40、BST 2 | 一致 |
| 9 | EUR 10-26 日 K 35.388 對 UTC 00:00 小時價 36.586；11-02 35.377 對 36.428（§4） | 同值（35.388／36.586、35.377／36.428） | 一致 |
| 10 | EUR 小時價對日 K 系統差 +0.1324%、JPY −1.0788%（§3.4） | 附錄 S4「all」：EUR +0.1324、JPY −1.0788；獨立腳本分期中位數與之相容（EUR 0.1197／0.136／0.1312；JPY 1.0412／1.075／1.0938） | 一致 |
| 11 | JPY 固定位移最小值落在掃描邊界 k＝+26（§3.4） | 2026-11-20 補算（同 #5）：JPY 終點版與起點版最小中位\|差\|皆落在 k＝+26（0.7827%／0.6338%），即掃描上界；k 範圍 −6～+26 內無內部最小值。獨立腳本在 offset −3～+3 內 JPY 最佳偏向較大 offset（P1＋2、P2＋3、P3＋2），方向相容 | 一致（k＝+26 邊界已驗；「為何如此」的成因仍不可由本報告確認） |
| 12 | 新舊報告重疊根：USD／EUR／JPY 日 K 共 505 根無改值，唯一變化是 10-14 那根 null 變有值（§4） | 獨立腳本：重疊 506 根、不同 1 根（USD／EUR／JPY 各 1）；VIX 505 根、0 不同。附錄 S10 的 505 為「同值」計數，506 含該 1 根 null→有值 | 一致（505＋1＝506） |
| 13 | CNY／CNH 日 K 只回 1 根、`status=ok`（§6；補證表 §1(7)：四次取數皆 1 根） | 2026-11-20 讀 main 上 `docs/evidence/probe_fx_obs_date/` 的 4 份保存檔（10-13、10-14 兩份、11-08），CNY 與 CNH 皆 `raw_bar_count`＝1、`status`＝ok | 一致（4 份全部已讀） |
| 14 | null close：匯率 5 根、VIX 19 根（§2、§3.5） | 本組：USD／EUR／JPY 5、VIX 19 | 一致 |
| 15 | prev_weekday 重現：518 列、2024-11-05～2026-11-05、漏平日 5 個（2024-12-31、2025-04-17、04-18、12-24、12-31）、被寫成觀測日但當天無收盤 4 個（§5） | 附錄 S7 輸出同（`appendix_out.txt`）；為重現邏輯，**非**呼叫正式 `rows_from_daily_close` | 一致（重現邏輯，非正式函式） |
| 16 | 10-14 舊報告小時 K 起於 2026-09-14T06:00Z；末三根 05:00Z、06:00Z、06:47:27Z；末根 O＝H＝L＝C＝32.14＝`regularMarketPrice`，`regularMarketTime`＝06:47:27Z（補證表 §1(2)(5)） | 本組讀同檔：起點 2026-09-14 06:00:00Z；末三根時間戳同；末根四價 32.14；rmp 32.14、rmt 06:47:27Z；06:00Z 根 H 32.217／L 32.108／C 32.134 | 一致 |

**仍無法重算／不可由本報告確認的項目**（2026-11-20 修訂後；原稿另列的 fixed_offset_scan 逐 k 與各期最大差值、舊報告 CNY／CNH 根數已補算，不再列此）：(a) Yahoo 日 K close 欄位的官方定義（E1174 §8-5；報告內無此資訊）；(b) 小時 K 時間戳＝區間起點之假設，本報告僅能給旁證，不能證明（§3.4 自述 INFERENCE）；(c) EUR 週一異常與 JPY 水位差的成因；(d) 10-14 原稽核報告（X／Y／P／Q）內容與其假日清單（本倉無原文）；(e) 補證表 §1(1)「23 個可比日」中 10-07 一日由附錄補算（報告 `compared`＝22）：`maxdiff_recompute.py` 與 `indep_recompute.py` 皆得 n＝23（P1 13／P2 5／P3 5），與 E1174 一致；`fixed_offset_scan` 的 22 根是另一個口徑（觀測日唯一且在 31 日窗內者，不含 10-07），兩者並不矛盾。

**重算性質的限制（INFERENCE）**：附錄腳本與報告同源（E1174 §8-1 自述不構成獨立驗證）；本組另寫的腳本與其共用同一份輸入資料。2026-11-20 補算的兩支腳本（`scan_recompute.py`、`maxdiff_recompute.py`）亦然。因此本節只證明「由該報告可算出這些數字、E1174 的算術與計數無誤」，**不能**證明「Yahoo 日 K close 對應 UTC 當日 00:00」是一條可寫成正式收盤規則的事實（樣本 P2、P3 各僅 5 日、小時解析度）。

## 3. M1-b 文字核對（只讀文字，未重跑任何探測）

### 3.1 條文原句（FACT，出處 `docs/DECISIONS.md` `### DEC-2026-11-08-02`）

| 位置 | 原句 |
|---|---|
| 決策者／原話欄 | 「客戶指示經總管轉交的要點轉述，非逐字」；要點 (2)「不使用相同方法立即重跑 FX 探測」 |
| 決策內容摘要 | 「不以與 2026-11-08 探測相同的方法立即重跑；先產出缺口與補證方法文件。本筆只照客戶字面，**不**推論補證方法是什麼、是否補跑、何時補跑」 |
| 現行效果欄 (4) | 「補證表 M1-b 等是否算『以相同方法立即重跑』待客戶／總管判定，判定前不得執行」 |
| 仍未授權欄 | 「D8 補跑：本次未授權（客戶僅明示不以相同方法立即重跑）」；「FX 開閘＝未核准」 |

### 3.2 工具預設參數 vs 11-08 那次（FACT，讀自報告欄位與 main 上腳本、workflow）

| 參數 | 11-08 那次（報告欄位） | 既有工具預設（main） | 差異 |
|---|---|---|---|
| 觸發 | `event_name`＝workflow_dispatch | 同入口（dispatch 或按鈕分支 push） | 無 |
| 執行版本 | `executed_sha`＝`15538a57…`；workflow 一律 `ref: main` | `git diff 15538a57 HEAD -- scripts/probe_fx_obs_date.py .github/workflows/fx_obs_date_probe.yml` **無輸出**（本組實跑）＝腳本與 workflow 自該 SHA 起未變（2026-11-20 於 main `747c7585` 再跑一次，仍無輸出） | 無 |
| 代號 | 報告含 USD、VIX、EUR、JPY、CNY、CNH 六個、`rejected_tickers`＝[] | `DEFAULT_TICKERS`＝USD、VIX、EUR、JPY、CNY、CNH（腳本 :108）；workflow `tickers` 留空走預設 | 無 |
| 日 K | `range`＝2y、`interval`＝1d | `RANGE="2y"`、`INTERVAL="1d"`（:112-113，檔內常數，無輸入可改） | 無 |
| 小時 K | `hourly.range`＝1mo、`interval`＝60m，僅 USD／EUR／JPY | `HOURLY_RANGE="1mo"`、`HOURLY_INTERVAL="60m"`、`HOURLY_TICKERS` 同（:552-555） | 無 |
| 取數時刻 | 2026-11-08T06:36Z（週日） | 重跑時刻 | **唯一差異**；`1mo` 窗口隨之後移（11-08 窗口 2026-10-06T23Z～11-06T23Z） |
| 來源／端點 | 同一 Yahoo chart 端點 | 同 | 無 |

### 3.3 結論（FACT／INFERENCE／RECOMMENDATION 分離）

- **FACT**：預設重跑在**工具參數、程式版本、代號集、端點、range／interval 上與 11-08 那次逐項相同**；唯一不同的是取數時刻（及因此後移的小時 K 窗口）。`DEC-2026-11-08-02` 全文沒有定義「相同方法」，也沒有指名判定人；BACKLOG BL-0217 與 `open_work_inventory_2026_11_19.md` X2 皆記「待判、repo 無具名承接人」（原作者讀取；本批未改這兩處）。
- **判定（M1-b＝NO-RUN）**：Work 已獨立判定 M1-b 為 NO-RUN，ChatGPT 總管轉述〔待核〕，**非 DEC、非客戶逐字**：同一 workflow、同一腳本、同一來源與同一預設取樣方式，僅變更日期不構成新方法；新取數須另行取得授權；FX Gate 維持關閉。本檔原作者的推論（見下）亦得到同向結論（視同相同方法）。依此，本批**不執行**任何探測重跑。
- **INFERENCE**：依字面，預設參數重跑屬「相同方法」；「立即」一詞的作用不明（可能指「不要現在馬上」也可能指「不要用這個方法」），文本無法分辨，故**不能**用「已過 12 天、不算立即」自行化解。若只縮減代號（例如 `tickers=USDTWD=X`，VIX 仍強制納入）：只改輸入、不改方法與端點，本組判讀仍近似同法，同樣不屬可自行放行的範圍。M1-b 唯一可增加的資料是 P3（兩地皆冬令）日數；P2（10-26～10-30）日數不會增加（補證表 §1(1)，轉引）。
- **RECOMMENDATION**（不構成裁示）：M1-b 不執行。若日後要取任何新 Yahoo 觀測，須另行取得客戶書面授權，授權內容需明列入口、代號與取樣方式；「變更日期」本身不得被當作新方法的理由。上述判定屬 Work／總管轉述，**客戶可推翻**。

## 4. 11-24／11-26 前的合法路徑（不觸發 workflow、不取新資料、FX Gate 維持關閉）

- **INFERENCE：沒有能「新增觀測」的路徑。** 新增任何 Yahoo 觀測都要執行探測（＝觸發 workflow 或按鈕分支）或另取資料來源，兩者皆被 DEC 與本批範圍排除；改探測常數（M3-b、M4-c、M5-b、M7-a）須合併 main 才能被 workflow 執行（workflow `ref: main`），且屬改探測設定，補證表建議先經授權。
- **可行且合法的只有離線重讀既有保存報告**（補證表 §2）：M2-a 第一路徑（10-14 報告末根，本組已於 §2 #16 重現）、M3-a、M4-a／b、M5-a、M6-a／b／c。這些**不受窗口限制**，窗口過後仍可做，因此「時間壓力」不能拿來當作省略授權的理由（補證表 §3 同意）。其限制：單一取數時刻、樣本小；M6-a 需 10-14 稽核假日清單（本倉無）；M6-b／c 要呼叫既有正式函式（離線運算，尚未有人判定是否算越界）。
- **窗口前合法路徑的範圍（FACT）**：窗口前唯一合法的動作是**離線重讀既有報告**；本批只做了這一件事，不觸發 workflow、不取新資料，`FX_OBS_DATE_RULE_VERIFIED` 與閘門維持關閉。
- **保存風險已於本批排除（FACT）**：原稿曾指出 11-08 報告（含不可再生的 P2 五日 10-26～10-30 小時 K）只存在於報告分支 commit 物件、不在 main，窗口約 11-26 後 `1mo` 小時窗口不再含 P2。**本批已依 `docs/evidence/probe_fx_obs_date/README.md` 既有做法把該報告保存到 main**：`docs/evidence/probe_fx_obs_date/20261108T063652Z_run42455423910_report.json.gz`，原檔 sha256 `8fe1aca5de4236847ee24c9c8abc736b828c4d25a81f7074948a4c9d001be5a9`，保存檔 `gzip -dc` 後 sha256 與原檔一致（見 §1.1）。此為保存既有檔、非取新資料。原報告分支 `probe/fx-obs-date-results` 本批未動。

## 5. 未能驗證項與揭露

| # | 項目 | 狀態 |
|---|---|---|
| 1 | 單組產出，未經第二組複驗；重算與報告同源，不構成獨立資料驗證 | 單組揭露 |
| 2 | fixed_offset_scan 與各期最大差值：原稿未驗，2026-11-20 已補算（§2 #3、#5、#11），198 組逐 k 比對 0 不一致 | 已補（仍同源） |
| 3 | 舊報告 CNY／CNH 根數：原稿只驗兩份，2026-11-20 已讀 main 上 4 份保存檔，皆 1 根、status ok | 已補 |
| 4 | 10-14 原稽核 X／Y／P／Q、舊假日清單、Yahoo 欄位定義、成因類問題 | 無法驗（缺原文／原始資料） |
| 5 | 「相同方法」的客戶本意；DEC 要點為經總管轉述、非逐字；M1-b＝NO-RUN 為 Work 判定經 ChatGPT 總管轉述〔待核〕，非 DEC | 未驗（客戶可推翻） |
| 6 | 原稿稱撰寫時本機無 `origin/probe/fx-obs-date-results` ref；該分支是否另有備份未查（未連網）。11-08 報告本身已保存於 main，此項不再影響報告可得性 | 未驗（影響已降低） |
| 7 | 未呼叫任何正式函式（`rows_from_daily_close`、`_obs_date` 等）；未改任何閘門、門檻、公式、容差、`.py`、workflow | 聲明 |
| 8 | 保存檔為 gzip 壓縮；日後若有任何文字類 hook 改寫該檔，須以 README 載明的 sha256 驗證 | 聲明 |

## 附錄 A：重算腳本全文（皆唯讀、離線、純標準庫；用法 `python3 -I <腳本> <報告.json> [<舊報告.json>]`，報告先以 `gzip -dc` 解壓）

### A-recompute_appendix.py

```python
# usage: python3 -I recompute.py REPORT.json [OLD_REPORT.json]   (read-only; no network)
import json,sys,statistics as st,collections
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
R=json.load(open(sys.argv[1])); T=R['tickers']; U=timezone.utc
L=ZoneInfo('Europe/London'); C=ZoneInfo('America/Chicago')
def ut(t): return datetime.fromtimestamp(t,U)
print('## S1 per-ticker summary')
for k,v in T.items():
    m=v['meta_summary']; s=v['subsets_exchange_tz']['non_null']; dd=v['obs_date_rule_diff']; p=v['production_rows']
    print(k,'status',v['status'],'raw',v['raw_bar_count'],'null',v['null_close_count'],'nonnull',s['bar_count'],'tz',m['exchangeTimezoneName'],
          'diff',dd['diff_count'],'/',dd['total'],'weekend(new)',s['obs_date_weekday']['weekend_count'],'dup(new)',s['obs_date_weekday']['duplicate_obs_date_count'],
          'rule',p['obs_date_rule'],'rows',p['row_count'],p['first_obs_date'],p['last_obs_date'],'skipped',len(p['skipped']),'hourly' in v)
for k in ('USDTWD=X','EURTWD=X','JPYTWD=X'):
    s=T[k]['subsets']['non_null']['obs_date_weekday']; print('legacy-UTC',k,'weekend',s['weekend_count'],'weeks missing Fri',s['iso_weeks_missing_friday_count'],'| new-rule weeks missing Fri',T[k]['subsets_exchange_tz']['non_null']['obs_date_weekday']['iso_weeks_missing_friday'])
print('## S2 DST transitions seen in daily stamps (UTC hh:mm change)')
for k,z in (('USDTWD=X',L),('^VIX',C)):
    r=T[k]['raw_daily_full']['t']; prev=None
    for t in r:
        h=ut(t).strftime('%H:%M')
        if prev and prev!=h: print(k,prev,'->',h,'first bar',datetime.fromtimestamp(t,z).strftime('%Y-%m-%d %a %H:%M %Z'))
        prev=h
print('## S3 hourly window / meta (USD)')
u=T['USDTWD=X']; dv=u['daily_value_check']; print(dv['hourly_first_utc'],dv['hourly_last_utc'],'compared',dv['compared'],'ties_gt_1',dv['match_precision']['ties_gt_1'],'within_tol(1e-6)',dv['match_precision']['within_tol'])
print('## S3b bar value vs Yahoo self-reported previous close (USD)')
r=T['USDTWD=X']['raw_daily_full']
for t,c in zip(r['t'],r['close']):
    if datetime.fromtimestamp(t,L).strftime('%Y-%m-%d')=='2026-10-14': print('bar 2026-10-14 close',c,'vs 32.124 (doc 49 cond. b) pct',round((c-32.124)/32.124*100,4))
v=T['USDTWD=X']['hourly']['meta_snapshot']['values']; print('bar 2026-11-06 close',r['close'][-1],'vs previousClose',v['previousClose'],'pct',round((r['close'][-1]-v['previousClose'])/v['previousClose']*100,4))
print('## S5b Monday bar close vs prior Friday last hourly close')
for k in ('USDTWD=X','EURTWD=X'):
    r=T[k]['raw_daily_full']; h=T[k]['hourly']['raw']; H=[(t,c) for t,c in zip(h['t'],h['close']) if c is not None]
    for t,c in zip(r['t'],r['close']):
        D=datetime.fromtimestamp(t,L)
        if c is None or D.strftime('%a')!='Mon' or D.strftime('%Y-%m-%d')<'2026-10-12': continue
        f=max(x for x in H if t-80*3600<x[0]<t-12*3600); print(k,D.date(),'Mon close',round(c,4),'Fri last hourly',ut(f[0]).strftime('%a %H:%M'),round(f[1],4),'pct',round((c-f[1])/f[1]*100,4))
print('## S4 daily close vs hourly open at UTC D 00:00 (signed %, hourly-daily), by period; and vs London-midnight open')
for k in ('USDTWD=X','EURTWD=X','JPYTWD=X'):
    r=T[k]['raw_daily_full']; h=T[k]['hourly']['raw']; Ho={t:o for t,o in zip(h['t'],h['open']) if o is not None}
    rows=[]
    for t,c in zip(r['t'],r['close']):
        if c is None: continue
        D=datetime.fromtimestamp(t,L)
        u0=int(datetime(D.year,D.month,D.day,tzinfo=U).timestamp()); l0=t
        if u0 in Ho and l0 in Ho: rows.append((D.strftime('%Y-%m-%d'),(Ho[u0]-c)/c*100,(Ho[l0]-c)/c*100))
    for lab,lo,hi in (('P1 Lon BST/NY EDT','2026-10-07','2026-10-23'),('P2 Lon GMT/NY EDT','2026-10-26','2026-10-30'),('P3 both std','2026-11-02','2026-11-06'),('all','2026-10-07','2026-11-06')):
        s=[x for x in rows if lo<=x[0]<=hi]
        print(k,lab,'n',len(s),'UTC00 med|%|',round(st.median(abs(x[1]) for x in s),4),'max|%|',round(max(abs(x[1]) for x in s),4),'med signed',round(st.median(x[1] for x in s),4),'| London00 med|%|',round(st.median(abs(x[2]) for x in s),4))
print('## S5 hourly weekly gaps USD (UTC)')
h=T['USDTWD=X']['hourly']['raw']; ts=[t for t,c in zip(h['t'],h['close']) if c is not None]
for a,b in zip(ts,ts[1:]):
    if b-a>3*3600: print('last',ut(a).strftime('%a %m-%d %H:%M'),'next',ut(b).strftime('%a %m-%d %H:%M'))
z=[ut(t).strftime('%a %m-%d %H:%M') for t,o,hi,lo,c in zip(h['t'],h['open'],h['high'],h['low'],h['close']) if c is not None and o==hi==lo==c]
print('zero-range bars',z)
for k in ('USDTWD=X','EURTWD=X','JPYTWD=X'):
    v=T[k]['hourly']['meta_snapshot']['values']; hh=T[k]['hourly']['raw']
    print(k,'rmp',v['regularMarketPrice'],'rmt',ut(v['regularMarketTime']).strftime('%m-%d %H:%M:%S'),'prevClose',v['previousClose'],'rmp-fulldayChange',round(v['regularMarketPrice']-v['fulldayChange'],4),'last hourly stamp',ut(hh['t'][-2]).strftime('%m-%d %H:%M'),hh['close'][-2],'last daily',T[k]['raw_daily_full']['close'][-1])
print('## S6 daily close vs open anomalies (|c/o-1|>1%)')
for k in ('USDTWD=X','EURTWD=X','JPYTWD=X'):
    r=T[k]['raw_daily_full']; w=collections.Counter(); n=0
    for t,o,c in zip(r['t'],r['open'],r['close']):
        if o is None or c is None: continue
        if abs(c/o-1)>0.01: n+=1; w[datetime.fromtimestamp(t,L).strftime('%a')]+=1
    print(k,n,dict(w))
print('## S7 obs dates by prev_weekday replication (not the production function)')
def pw(d):
    d-=timedelta(days=1)
    while d.weekday()>=5: d-=timedelta(days=1)
    return d
for k in ('USDTWD=X','EURTWD=X','JPYTWD=X'):
    r=T[k]['raw_daily_full']; nn=[];nl=[]
    for t,c in zip(r['t'],r['close']): (nl if c is None else nn).append(datetime.fromtimestamp(t,L).date())
    obs=sorted(pw(d) for d in nn); S=set(obs); d=obs[0]; miss=[]
    while d<=obs[-1]:
        if d.weekday()<5 and d not in S: miss.append(str(d))
        d+=timedelta(days=1)
    print(k,len(obs),obs[0],obs[-1],'gaps',miss,'null-D',[str(x) for x in nl],'written=nullD',[str(o) for o in obs if o in set(nl)])
print('## S8 VIX')
v=T['^VIX']; r=v['raw_daily_full']
print('last2 closes',[(datetime.fromtimestamp(t,C).strftime('%m-%d'),c) for t,c in list(zip(r['t'],r['close']))[-2:]],'rmp',v['meta_snapshot']['values']['regularMarketPrice'],'fulldayChange',v['meta_snapshot']['values']['fulldayChange'],'nulls',v['null_close_count'])
print('## S9 CNY/CNH')
for k in ('CNYTWD=X','CNHTWD=X'):
    v=T[k]; print(k,'raw',v['raw_bar_count'],'t',ut(v['raw_daily_full']['t'][0]).strftime('%Y-%m-%d %H:%M:%S'),'close',v['raw_daily_full']['close'][0],'last==rmt',v['last_bar']['equal'],'rows',v['production_rows']['row_count'],'skipped',v['production_rows']['skipped'])
if len(sys.argv)>2:
    O=json.load(open(sys.argv[2])); print('## S10 vs old report',O.get('generated_at_utc'))
    for k in ('USDTWD=X','^VIX','EURTWD=X','JPYTWD=X'):
        a=O['tickers'][k]['raw_daily_full']; b=T[k]['raw_daily_full']; N=dict(zip(b['t'],b['close'])); same=diff=flip=0
        for t,c in zip(a['t'],a['close']):
            if t not in N: continue
            if c is None or N[t] is None: flip+= (c is None)!=(N[t] is None); same+= (c is None and N[t] is None)
            elif abs(c-N[t])<=1e-9*abs(c): same+=1
            else: diff+=1
        print(k,'overlap same',same,'diff',diff,'null<->value',flip)
```

### A-indep_recompute.py

```python
# 獨立重算（不沿用 E1174 附錄腳本）；唯讀、離線。用法: python3 -I indep_recompute.py r1108.json r1014.json
import json,sys,statistics as st
from datetime import datetime,timezone,date
from zoneinfo import ZoneInfo
R=json.load(open(sys.argv[1]));O=json.load(open(sys.argv[2]));T=R['tickers']
LON=ZoneInfo('Europe/London');UTC=timezone.utc
def pairs(v):
    d=v['raw_daily_full'];return list(zip(d['t'],d['open'],d['close']))
def hourly(v):
    h=v['hourly']['raw'];return {t:(o,hi,lo,c) for t,o,hi,lo,c in zip(h['t'],h['open'],h['high'],h['low'],h['close'])}
def period(d):
    return 'P1' if '2026-10-07'<=d<='2026-10-23' else 'P2' if '2026-10-26'<=d<='2026-10-30' else 'P3' if '2026-11-02'<=d<='2026-11-06' else None
print('R sha/gen',R.get('generated_at_utc'),'executed_sha',R.get('executed_sha'))
# (A) 日K close vs 同UTC日 00:00 小時K "open"(起點小時價) 與 "close" 兩種取法，及固定位移 k 掃描(以 UTC 00:00 為基準 k=-3..3 小時, 用 hourly close)
for k in ('USDTWD=X','EURTWD=X','JPYTWD=X'):
    v=T[k];H=hourly(v);res={}
    for t,o,c in pairs(v):
        if c is None: continue
        d=datetime.fromtimestamp(t,LON).strftime('%Y-%m-%d')   # 倫敦當地日
        p=period(d)
        if not p: continue
        u0=int(datetime(int(d[:4]),int(d[5:7]),int(d[8:]),tzinfo=UTC).timestamp())
        row={}
        for kk in range(-3,4):
            x=H.get(u0+kk*3600)
            if x and x[0] is not None: row[kk]=abs(x[0]-c)/c*100   # open 價
        res.setdefault(p,[]).append((d,row))
    for p in ('P1','P2','P3'):
        rows=res.get(p,[]);n=len(rows)
        med={kk:round(st.median([r[kk] for _,r in rows if kk in r]),4) for kk in range(-3,4) if all(kk in r for _,r in rows)}
        best=min(med,key=med.get) if med else None
        print(k,p,'n',n,'median|%| by UTC-hour offset from UTC00(open价):',med,'best',best)
# (B) 事實類
for k in T:
    v=T[k];print('B',k,'raw',v['raw_bar_count'],'null',v['null_close_count'],'status',v['status'])
for k in ('EURTWD=X','USDTWD=X','JPYTWD=X'):
    bad=[(datetime.fromtimestamp(t,LON).strftime('%Y-%m-%d %a'),round((c/o-1)*100,2)) for t,o,c in pairs(T[k]) if o and c and abs(c/o-1)>0.01]
    mon=[b for b in bad if 'Mon' in b[1-1]]
    print('C',k,'>1%',len(bad),'Mon',len(mon),'range of Mon pct',(min(b[1] for b in mon),max(b[1] for b in mon)) if mon else None)
# 週一 EUR: 10-26 / 11-02 日K vs 同日UTC00小時價
H=hourly(T['EURTWD=X'])
for t,o,c in pairs(T['EURTWD=X']):
    d=datetime.fromtimestamp(t,LON).strftime('%Y-%m-%d')
    if d in('2026-10-26','2026-11-02'):
        u0=int(datetime(int(d[:4]),int(d[5:7]),int(d[8:]),tzinfo=UTC).timestamp());print('D EUR Mon',d,'close',c,'hourly UTC00 open',H[u0][0])
# 重疊根 新舊報告
for k in ('USDTWD=X','EURTWD=X','JPYTWD=X','^VIX'):
    a=dict((t,c) for t,o,c in pairs(O['tickers'][k]));b=dict((t,c) for t,o,c in pairs(T[k]))
    com=[t for t in a if t in b];diff=[t for t in com if not((a[t] is None and b[t] is None) or (a[t] is not None and b[t] is not None and abs(a[t]-b[t])<=1e-9*abs(a[t])))]
    print('E overlap',k,len(com),'diff',len(diff))
# 10-14 舊報告: 小時K起點、末三根、meta
o=O['tickers']['USDTWD=X'];h=o['hourly']['raw']
print('F old hourly first',datetime.fromtimestamp(h['t'][0],UTC),'last3',[datetime.fromtimestamp(t,UTC).strftime('%H:%M:%S') for t in h['t'][-3:]],'last3 OHLC',list(zip(h['open'][-3:],h['high'][-3:],h['low'][-3:],h['close'][-3:])))
mv=o['hourly']['meta_snapshot']['values'];print('F old rmp',mv.get('regularMarketPrice'),'rmt',datetime.fromtimestamp(mv['regularMarketTime'],UTC))
for k in ('CNYTWD=X','CNHTWD=X'):
    print('G',k,[ (rr['tickers'][k]['raw_bar_count']) for rr in (R,O)])
```

### A-scan_recompute.py

```python
# 逐 k 重算 daily_value_check.fixed_offset_scan（獨立實作，不 import 探測腳本）。唯讀、離線。
# 用法: python3 -I scan_recompute.py REPORT.json
import json, sys, statistics as st
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

R = json.load(open(sys.argv[1]))
tot = bad = 0
summary = {}
for tk in ('USDTWD=X', 'EURTWD=X', 'JPYTWD=X'):
    v = R['tickers'][tk]
    chk = v['daily_value_check']
    tz = ZoneInfo(chk['exchange_tz'])
    cutoff = date.fromisoformat(chk['cutoff_day'])
    earliest = cutoff - timedelta(days=chk['window_days'])
    D = v['raw_daily_full']
    H = v['hourly']['raw']
    ho = {t: (o, c) for t, o, c in zip(H['t'], H['open'], H['close'])}
    # 觀測窗內、已收盤、close 非 null、且觀測日唯一的日 K
    cand = []
    for t, c in zip(D['t'], D['close']):
        od = datetime.fromtimestamp(t, tz).date()
        if od >= cutoff or od < earliest or c is None:
            continue
        cand.append((od, c))
    cnt = {}
    for od, _ in cand:
        cnt[od] = cnt.get(od, 0) + 1
    anchors = []
    for od, c in cand:
        if cnt[od] == 1:
            anchors.append((int(datetime(od.year, od.month, od.day, tzinfo=tz).timestamp()), c))
    stored = chk['fixed_offset_scan']
    ks = list(range(stored['k_hours'][0], stored['k_hours'][1] + 1))
    ok_all = (len(anchors) == stored['daily_bars'])
    best = {}
    for part in ('by_end', 'by_start'):
        mine = {}
        for k in ks:
            vals = []
            for a, c in anchors:
                at = a + k * 3600
                if part == 'by_end':
                    x = ho.get(at - 3600)
                    p = x[1] if x else None
                else:
                    x = ho.get(at)
                    p = x[0] if x else None
                if p is not None:
                    vals.append((p - c) / c * 100)
            med = st.median(vals) if vals else None
            mabs = st.median([abs(x) for x in vals]) if vals else None
            mine[k] = (len(vals), med, mabs)
        mism = 0
        for k in ks:
            s = stored[part][f'{k:+d}']
            n, med, mabs = mine[k]
            tot += 1
            same = (s['n'] == n) and all(
                (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= 1e-9 * max(1.0, abs(a)))
                for a, b in ((s['median_pct_diff'], med), (s['median_abs_pct_diff'], mabs)))
            if not same:
                mism += 1
                bad += 1
                print('MISMATCH', tk, part, k, s, mine[k])
        rows = [(mine[k][2], k, mine[k][0]) for k in ks if mine[k][2] is not None]
        b = min(rows)
        best[part] = b
        print(tk, part, 'k數', len(ks), '不一致', mism, '最小中位|差|%.4f' % b[0], 'k=%+d' % b[1], 'n=%d' % b[2])
    print(tk, 'daily_bars 重算', len(anchors), '報告', stored['daily_bars'], 'k範圍', stored['k_hours'])
    summary[tk] = best
print('逐 k 比對總數', tot, '不一致', bad)
```

### A-maxdiff_recompute.py

```python
# 獨立重算各期最大絕對差（UTC 當日 00:00 起點小時 open vs 日 K close）。唯讀離線。
# 用法: python3 -I maxdiff_recompute.py REPORT.json
import json, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

R = json.load(open(sys.argv[1]))
LON = ZoneInfo('Europe/London')
per = {'P1': ('2026-10-07', '2026-10-23'), 'P2': ('2026-10-26', '2026-10-30'), 'P3': ('2026-11-02', '2026-11-06')}
for tk in ('USDTWD=X', 'EURTWD=X', 'JPYTWD=X'):
    v = R['tickers'][tk]
    D = v['raw_daily_full']
    H = v['hourly']['raw']
    ho = {t: o for t, o in zip(H['t'], H['open'])}
    res = {p: [] for p in per}
    for t, c in zip(D['t'], D['close']):
        if c is None:
            continue
        d = datetime.fromtimestamp(t, LON).date()
        u0 = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())
        o = ho.get(u0)
        if o is None:
            continue
        for p, (a, b) in per.items():
            if a <= d.isoformat() <= b:
                res[p].append((abs(o - c) / c * 100, d.isoformat()))
    allv = [x for p in res for x in res[p]]
    print(tk, {p: (len(res[p]), round(max(res[p])[0], 4), max(res[p])[1]) for p in res},
          '全期', len(allv), round(max(allv)[0], 4), max(allv)[1])
```
