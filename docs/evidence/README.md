# 證據保存目錄

2026-10-16 建立。客戶 2026-10-16 核准「只保存、不刪除」：只存在分支上、卻被 main 正式文件或程式當成出處的內容，原樣落盤到 main，讓那些引用不必依賴分支。原計畫以保存用 tag 鎖住舊 commit，本環境推送 tag 被拒（HTTP 403），改用本目錄；tag 由總管另向客戶說明。**本目錄建立時沒有刪除任何分支。**

| 子目錄 | 內容 | 來源 |
|---|---|---|
| `probe_fx_obs_date/` | Yahoo 匯率日線觀測日探測報告 3 份（`.json.gz`） | `probe/fx-obs-date-results` @ `6dd3e62` |
| `probe_moneydj_basic/` | MoneyDJ 基本資料頁探測報告 1 份（`.json.gz`） | `probe/moneydj-basic-results` @ `39672f9` |
| `branch_archive/docs-handover-latest/` | 舊交接本 4 個版本（`885b71a`、`fce9176`、`ddc5625`、`ed896e4`） | `docs/handover-latest` |
| `branch_archive/handover-2026-10-14/` | 2026-10-14 交接本；三份殘留 patch 只記雜湊 | `handover/2026-10-14` @ `efeee8a` |
| `branch_archive/wip-exp-c2-ui-wiring-round2-unaudited/` | WIP commit 的程式差異（`git diff`，`.patch.gz`；不含 commit message 署名行） | `wip/exp-c2-ui-wiring-round2-unaudited` @ `4d00b6b` |
| `branch_archive/pr838/` | #838 資料字典 §4.6 文案草稿與 §5 G-13 摘錄（草稿、未核准） | `claude/v2-data-dictionary-a` @ `78863c3` |
| `branch_archive/pr799/` | #799 舊 HANDOVER 工作原則摘錄（未重新核准） | `claude/fund-handover-sn42bh` @ `c6750e8` |
| `decisions/` | 客戶裁示逐字存檔（2026-10-16 加入；性質與上列不同：存的是對話中裁示的全文，不是分支內容）。首份：客戶 2026-10-16 治理十一項裁示，三個 sha256 見該目錄 `README.md` | 客戶 2026-10-16 對話，經總管逐字轉存；存檔時 base main `ab30239` |

每個子目錄的 `README.md` 記來源分支、全長 SHA、時間、原始與保存檔的 sha256、被 main 何處引用、驗證指令。

## 為什麼放在 `docs/evidence/`，不放 `docs/v2/evidence/`

`docs/v2/` 底下的 `.md`／`.html` 受 `tests/test_doc_counters.py` 守衛：射程由 `DOCS_GLOBS` 定義（非遞迴），並有一條正控要求 `docs/v2/` 底下不得有任何 `.md` 落在射程外。若放在 `docs/v2/evidence/`，這些 README 要嘛被那條正控擋下，要嘛必須改測試把它們納入規格文件的計數守衛。它們是證據說明、不是規格文件，故放在 `docs/v2/` 之外，測試一字未改。

## 格式規則

- 大檔與 JSON 報告以 `gzip -9 -n` 壓縮存放（逐位元組，避開 `check-added-large-files` 的 500KB 上限與文字類 hook 改寫）。
- 文字原文若已實測無行尾空白、結尾單一換行，則原樣存放、不壓縮，方便直接閱讀與對照行號。
- 逐字摘錄不改字；含禁詞時在該目錄 README 做撞字登記。
