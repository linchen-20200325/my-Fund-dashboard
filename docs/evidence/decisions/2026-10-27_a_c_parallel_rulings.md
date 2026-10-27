# 客戶 2026-10-27 「A＋C 並行」正式裁示（逐字）

- **來源**：客戶 2026-10-27 正式裁示，經總管於派工單內逐字轉存；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-27-41`（客戶裁示）；`DEC-2026-10-27-42`（執行組讀法，非客戶裁示）。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為派工單內客戶原文，去掉最外層引號；字句未改。
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
正式裁示：A + C 並行。
A｜BL-0509 多日 probe
請再跑 3～5 個交易日的唯讀 probe，用來補齊：update frequency、publication lag、revision behavior、openapi / rwd 資料時間差、schema stability、Missing behavior
可以沿用既有 trigger branch / workflow 模式。
若需要新增「固定每日排程」才能有效取得多日證據，可以做，但限制：僅 BL-0509 shadow probe；checkout main；不接正式 signal；不接 AI Brain；不寫正式資料層；不暴露 secret；不新增付費來源；結果仍落到 probe results branch / evidence
不需要每天回報客戶；累積到足夠樣本後一次回報。
授權／條款
不要因 TWSE 條款頁 redirect 沒讀到，就永久卡住整個頁面。請先：1. 研究 TWSE OpenAPI / Open Data 官方公開說明與資料使用條款。2. 若 workflow 能安全跟隨到官方同網域／官方條款頁，可另做最小唯讀研究。3. 若仍無法取得正式條款內容，明確標：「⬜ 授權條款尚未完成驗證」。不要自行推定「可商用」或「不可商用」。若真的需要客戶人工閱讀特定條款頁，請最後只提供：精確頁面；要確認的條款項目；為什麼它會影響正式接入。不要現在因此阻塞 C。
C｜同步開始 🌍 不依賴 EPS 的內容
可以先進行 🌍 市場與趨勢頁中「不需要 forward EPS / g」的部分。優先盤點並重用舊 UI 已存在且可追溯的資料取得邏輯，但必須重新驗證 B 線 Data Contract。
可先做的範圍：1. 台股市場資料：TAIEX；期間走勢；市場成交／市場統計；已驗證的 trailing / actual 指標；資料日期與 freshness。2. 國際市場：只使用 repo 已存在且有可靠來源的資料。例如若既有 source 已有：S&P 500、美債殖利率、VIX、其他正式 macro / market series，可以盤點並接入新的 Data View。但：不新增未核准 API；NASDAQ / MSCI World / MSCI EM 若目前沒有正式來源，維持 Missing / Data Gap；不為了符合藍圖而補假資料。3. 圖表層：TAIEX 3M / 6M / 1Y / 3Y；已有國際市場指數／風險指標圖；freshness / source / Missing 顯示。4. 市場結論：目前只能顯示 deterministic / rule-supported 的局部狀態。若完整「中性偏多／中性偏空」尚缺正式 aggregation rule：不要讓 AI 自行判斷。可以顯示：各 domain 狀態；資料不足；暫無完整市場綜合判定。
EPS×PE 區塊：目前維持：「⬜ EPS 預估資料未取得，無法計算正式指數情境」。不要因 actual / trailing EPS 已取得就把它升格成 forward EPS。也不要：用歷史成長率當 g；AI 外推 g；用教材案例值當永久預估；反推教材矩陣作正式模型。未來正式 forward EPS / g 必須再走 Data Source Decision Gate。
implied_trailing_index_earnings：目前維持：「⬜ 無法判定」，因為缺：官方市場整體 trailing PE；可驗證 denominator / universe；股本權重或等價方法。不要把個股 1084 筆 PE 做簡單平均來代替市場 PE。若後續研究找到官方市場 PE 或正式計算口徑，再另行驗證。
下一個里程碑：A 與 C 可平行，但請分開 PR / evidence：BL-0509 = data source evidence / shadow research；🌍 page batch = UI / Data View implementation。不要混成一個大 PR。每批仍遵守：targeted tests → independent audit → CI → Auto-Ship → HANDOFF / BACKLOG sync。
Model / Effort：目前：Sonnet 5.5 + Medium。若開始涉及：正式市場綜合判斷公式；forward EPS model；Risk Cap；investment-core semantics，再走 Model / Effort Change Gate。維持 Silent Autonomous Cruise。
```
