# 獨立稽核紀錄：D8 FX 補證 M1-a 離線重算保存（docs-only）｜2026-11-20

- 稽核員：fund-independent-qa（非作者；唯讀 Read/Grep/Glob；無法執行指令、無法查 GitHub／CI、無法讀 .gz 內容）
- 對象：分支 docs/fx-m1a-evidence-preserve，commit 56904b75（base main 747c7585；SHA 來自主 session 派工文字，本組未自行核對）
- 審查檔案：docs/evidence/fx_m1a_offline_recompute_2026_11_20.md；docs/evidence/probe_fx_obs_date/README.md（追加節）；20261108T063652Z_run42455423910_report.json.gz（僅核對 README 登記）
- 交叉參照：scripts/probe_fx_obs_date.py、.github/workflows/fx_obs_date_probe.yml、DEC-2026-11-08-02、docs/evidence/fx_obs_date_winter_probe_2026_11_08.md（E1174）
- 獨立性限制：與主 session 共享派工來源，僅不同 context 與無寫入能力，不等同 PROJECT_RULES.md §8 人類層級獨立

## 總判：Must-Fix 0；Should-Fix 4；Nit 6

## FACT
- (a) 報告全文無授權或暗示重跑、開閘、改旗標；FX_OBS_DATE_RULE_VERIFIED 只在 L3、L34、L95 且皆為「未動、閘門維持關閉」。M1-b 於 L12、L87、L106 標「Work 獨立結論，ChatGPT 總管轉述〔待核〕，非 DEC、非逐字」，L89 寫「客戶可推翻」。DEC-2026-11-08-02 引文與 docs/DECISIONS.md L2497–2500 逐句一致。
- (b) 請示語氣字面搜尋 0 命中。
- 工具參數（DEFAULT_TICKERS、RANGE=2y、INTERVAL=1d、HOURLY_*）與報告表格一致；workflow 無排程，觸發僅 workflow_dispatch 與 push 按鈕分支。
- 附錄 A 與 E1174 L205–299 逐段比對（S1–S10、S4 公式）無差異。
- scan_recompute.py 與 fixed_offset_scan（probe_fx_obs_date.py L729–767）邏輯一一對應；33 個 k × 3 代號 × 2 版 ＝ 198，算術相符。
- README 追加節（commit 6b180d6f、run 42455423910、executed_sha 15538a57、908102／136739 bytes、sha256 8fe1aca5…／031c3bba…）與報告 §1.1／§2 完全相同，格式沿用既有慣例。
- 無偷渡 FX 業務結論、投資語意或新資料；md 與 README 無行尾空白。

## INFERENCE
- scan_recompute 0 不一致證明移植忠實、報告儲存值未被竄改，不證明掃描方法正確；maxdiff_recompute 與附錄 S4 公式實質相同，「兩支不同腳本一致」接近同義反覆；報告 L59 已承認同源。
- 「只證明算術不證明 Yahoo 語意」之限制清楚，但負面證據未明講（EUR 最小中位差約 0.11%、JPY 0.63–0.78% 且在掃描邊界 k=+26）。
- M1-b NO-RUN 最穩依據是 DEC-2026-11-08-02 效果欄 (4)「判定前不得執行」，不是轉述。

## Should-Fix
- S1 §0 #3 把 NO-RUN 標為 FACT／INFERENCE，但它是轉述〔待核〕；「Work」未定義；§3.3 補：repo 內 DEC 要求之判定尚無紀錄，故依效果欄 (4) 亦不執行，不依賴轉述。
- S2 重算輸出未留存；§2 #8（週一 GMT／BST 分組計數）、#13（CNY／CNH 根數）、#15（appendix_out.txt）無持久腳本或輸出，應標「手工計數，無腳本」或貼輸出。
- S3 措辭降級：「兩支不同腳本」「獨立重寫」→「同公式、同輸入的重算，驗算術與抄寫」；註明 0 不一致只涵蓋 198 組 n／中位數／中位絕對值，不含 daily_bars 根數比對。
- S4 L59 補負面證據：EUR、JPY 未呈現與 USD 相同貼合；UTC 00:00 假設僅 USD 小樣本支持；小時 K 時間戳＝區間起點亦為未實證假設。

## Nit
- N1 §0 #2「全部可重現，無不一致項」「沒有任何能新增觀測的路徑」補「單組字面比對、未經第二組驗證」。
- N2 §5 #6 與 L21「本機無分支 ref」被 §1.1 取代，建議合併。
- N3 附錄 recompute_appendix.py 檔首註解檔名與標題不同。
- N4 README 追加節補備援句；gz sha256 取決於 gzip 實作，可攜驗證只有解壓後 sha256。
- N5 README 未更新「被 main 哪些地方引用」（10-16 快照，可忽略）。
- N6 §2 #5 EUR 終點版 k=0／起點版 k=−1 需對照 E1174（可忽略）。

## NOT VERIFIED
- 本組未實跑任何腳本；198 組、各期最大差值、16 項一致等數字僅能判斷與腳本邏輯相容。
- 兩個新增檔位元組大小與 gz／解壓 sha256；git show 6b180d6f 在本機是否可取；probe/fx-obs-date-results 分支是否另有備份。
- 全稱句皆單組字面搜尋、未經第二組驗證；diff 範圍採信派工描述。

---

## 處置狀態（2026-11-20，作者續修；以下為附加，上方稽核全文逐字未改）

> 處置位置皆在 `docs/evidence/fx_m1a_offline_recompute_2026_11_20.md`（下稱「報告」）。本表為作者自述，未經第二組複驗。

| 項目 | 處置 | 位置 |
|---|---|---|
| S1 | 已處理：§0 #3 拆為 3a（參數逐項相同＝FACT）與 3b（NO-RUN＝轉述〔待核〕／INFERENCE）；定義「Work」＝ChatGPT 總管轉述之獨立驗收；§3.3 新增「不依賴轉述的執行依據」——repo 內尚無 DEC 要求之判定紀錄，依 DEC-2026-11-08-02 效果欄 (4)「判定前不得執行」亦不執行 | 報告 §0 #3a／#3b、§3.3 |
| S2 | 已處理：新增 `monday_count.py`（#8，輸出 103／44／59／40／2 與原手工計數一致，另揭露 1 根週一 close 為 null 不計）與 `cn_check.py`（#13，4 份保存檔）；#15 改指 `recompute_appendix.py` 輸出；附錄 B 貼六支腳本最後輸出；已從報告抽出附錄腳本重跑，輸出與貼上內容一致 | 報告 §1 腳本列、§2 #8／#13／#15、附錄 A、附錄 B |
| S3 | 已處理：「兩支不同腳本」「獨立重寫」改為「同公式、同輸入的重算，驗算術與抄寫，非獨立驗證」；§2 #5 註明 0 不一致只涵蓋 198 組 n／中位數／中位絕對值，不含 `daily_bars` 根數（根數另於輸出並列，22／22）；全文「獨立腳本」改稱 `indep_recompute.py` | 報告 §2 #3、#5、其餘各列 |
| S4 | 已處理：限制段補負面證據（USD 貼合；EUR 約 0.11%；JPY 0.63～0.78% 且在 k＝+26 邊界；UTC 00:00 假設僅 USD 小樣本支持；小時 K 時間戳＝區間起點為未實證假設） | 報告 §2 末「重算性質的限制」 |
| N1 | 已處理：§0 #2、#4 加「單組字面比對／字面搜尋、未經第二組驗證」 | 報告 §0 #2、#4 |
| N2 | 已處理：§1 第 2 列併入「他處備份未查」；§5 #6 改為指向 §1，不重複敘述 | 報告 §1、§5 #6 |
| N3 | 已處理：`recompute_appendix.py` 檔首註解的檔名改為與標題一致（僅註解，輸出不變） | 報告附錄 A |
| N4 | 已處理：README 追加節補備援句（原始仍在報告分支）與「可攜驗證只有解壓後 sha256」 | `docs/evidence/probe_fx_obs_date/README.md` 末段 |
| N5 | 未處置：README「被 main 哪些地方引用」是 2026-10-16 快照，本批範圍為追加保存 11-08 報告，不重量測舊快照；稽核亦標可忽略 | — |
| N6 | 未處置：EUR 終點版 k＝0／起點版 k＝−1 與 E1174 的對照需讀 E1174 全文，稽核標可忽略；報告已標明數值來自腳本輸出（附錄 B） | — |
