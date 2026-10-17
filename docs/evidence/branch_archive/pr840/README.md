# #840 全文保存：`docs/v2/UI_SPEC.md` 與 `docs/v2/UI_WIREFRAME_DRAFT.md`（草稿、未核准）

保存日 2026-10-17（總管 2026-10-17 派工；體例照本目錄 `pr838/`、`pr799/` 與 `docs-handover-latest/`）。本目錄保存兩份**整檔原文**，不是摘錄。**分支本身仍在、未刪。**

- 來源 PR／分支：#840，`origin/claude/v2-ui-spec-b`（PR 狀態「已關閉、未合併」為總管派工單轉述；本組以 GitHub API 查詢被拒，未自行確認）
- 分支 head（保存當下）：`e38c7dd5fee50adffe32fe8feb30c8b7f2156222`，commit 時間 2026-09-14T16:01:49+00:00；與 main 的 merge-base `9cbf03776f2a0ee6bdb5a649efb93352c40baba6`，分支上不在 main 的 commit 共 24 顆（最早 `64bcceea81881934c307c0a33dd83222f0f31b37`，2026-09-14T10:26:16+00:00）
- 原路徑：`docs/v2/UI_SPEC.md`、`docs/v2/UI_WIREFRAME_DRAFT.md`（main 皆無此二檔）

⛔ **效力**：兩份是 #840 分支上的草稿，**未經客戶核准，不是 main 的正式規格**。其中的提案單、W-3 等規則一律不得當成現行規格引用；保存只為讓 main 上「以 `e38c7dd` 為出處」的引用不必依賴分支。

## 為什麼保存

main 上有兩處以 `e38c7dd` 的 `UI_SPEC.md` 為出處，原本只能 `git show e38c7dd:...` 讀，分支一旦被刪就得先取回 PR ref：

- `EXCEPTIONS.md` `P-WHERECONTENT-1` 的 2026-10-10 續記（#840 提案單 #B-4、W-3、V3）—— 已於該句行內補保存位置。
- `docs/BACKLOG.md` BL-0237（提案單 #B-5 的 T-1～T-3，本檔約 :1000～:1004）—— 出處欄已改指本目錄。

## 保存的檔（2026-10-17 實跑）

| 本目錄檔名 | 原路徑 | 行數 | 大小（bytes） | sha256 |
|---|---|---|---|---|
| `e38c7dd_UI_SPEC.md` | `docs/v2/UI_SPEC.md` | 1910 | 159432 | `d35e6ca7f872901feb39c853138dd6c1a836f3c255efed3c7d7685eb0b8b9cac` |
| `e38c7dd_UI_WIREFRAME_DRAFT.md` | `docs/v2/UI_WIREFRAME_DRAFT.md` | 1334 | 103995 | `867224a9d750ff7c222dae705209487324511704b54958b91b73aee0121cad2d` |

保存格式：`git show e38c7dd5fee50adffe32fe8feb30c8b7f2156222:<原路徑>` 的輸出原樣寫入，未壓縮。兩份皆已實測：無行尾空白、無 CR、結尾單一換行、無合併衝突標記樣式的行、無 session 識別碼、無署名行、無 `claude.ai` 字樣 —— 故 `trailing-whitespace`／`end-of-file-fixer`／`check-merge-conflict` 不會改動內容，逐位元組與來源相同；單檔皆低於 `check-added-large-files` 的 500 KB 上限。原檔行號在保存檔中不變。

驗證（repo 根目錄執行；兩行輸出應相同，且等於上表 sha256）：

```
sha256sum docs/evidence/branch_archive/pr840/e38c7dd_UI_SPEC.md
git show e38c7dd5fee50adffe32fe8feb30c8b7f2156222:docs/v2/UI_SPEC.md | sha256sum
```

`UI_WIREFRAME_DRAFT.md` 同理。

## 署名行與 session 網址：不需處理

兩份檔案內容本身不含署名行、session 網址或 session 識別碼（上述實測）。分支 commit 的訊息含署名行（例如 `e38c7dd` 訊息末尾的工具署名），但本目錄**只存檔案內容、不存 commit 訊息**，故沒有任何署名行或網址進入 main；commit 訊息原文以上列 SHA 在 GitHub 查。體例同 `wip-exp-c2-ui-wiring-round2-unaudited/`（略去署名行與 session 網址）。

## 撞字登記

兩份是逐字原文，含交接本第 7 節〈客戶 2026-10-05 接手訊息：禁詞〉詞表中的詞（2026-10-17 以碼位組字掃描；「劃線裡的字也算」照算；依該節體例只寫第幾個詞、不寫字面）：

| 檔 | 第 1 個 | 第 2 個 | 第 3 個 | 第 4 個 | 第 5 個 | 第 6 個 | 第 7 個 | 第 8 個 |
|---|---|---|---|---|---|---|---|---|
| `e38c7dd_UI_SPEC.md`（出現次數） | 4 | 8 | 43 | 0 | 9 | 3 | 18 | 6 |
| `e38c7dd_UI_WIREFRAME_DRAFT.md`（出現次數） | 4 | 2 | 6 | 0 | 2 | 1 | 7 | 2 |

命中行號（第 1～3 個詞，即 2026-10-15 裁示後仍是禁詞的那幾個；第 4 個 0 命中）：

- `e38c7dd_UI_SPEC.md` 第 1 個：261、429、1007、1857；第 2 個：336、450、813、848、908、1007、1037、1662；第 3 個（42 行）：82、85、86、87、336、337、339、450、451、813、848、849、852、906、908、1007、1070、1099、1418、1419、1422、1450、1451、1507、1509、1519、1520、1524、1552、1553、1599、1600、1604、1627、1642、1643、1662、1706、1731、1736、1737、1764。
- `e38c7dd_UI_WIREFRAME_DRAFT.md` 第 1 個：179、500、1068、1188；第 2 個：912、1245；第 3 個：821、912、1207、1245、1259、1278。

第 5～8 個詞依客戶 2026-10-15 Phase 1.5（A+ 修正版）裁示已不是永久禁詞，只列次數。依逐字原則不改字、不改寫成跳脫碼，就地登記於此（體例同 `pr838/` 的撞字登記）。本 README 自身以 0 命中為目標。

掃描方式（以碼位組字，不把詞表字面寫進本檔）：取交接本第 7 節的 `W=[...]` 詞表，對兩份檔逐行做 `str.count`。

## 未同步處（刻意不動）

- `docs/handover_2026_09_26_latest.md` 〈登記待辦〉第六十六次更新 (d)（約 :3595）仍寫「分支若被刪，需先 `git fetch origin refs/pull/840/head` 取回」。該檔自 2026-10-16 起凍結為歷史紀錄、不再續寫（`docs/DECISIONS.md` 2026-10-16 客戶治理裁示），故未改；現行指標見 `docs/BACKLOG.md` BL-0237。
- `docs/v2/35_branch_strategy_check.md` 第 1 節表格的 #840 列是 2026-09-16 的盤點快照，未改。

## 本組未做的事

- 未比對 #840 草稿與 main 現行規格（44 等）的差異；BL-0237「已被取代」仍是總管推論、未驗。
- 「main 上以 `e38c7dd` 為出處的只有上列兩處」本組以 `git grep -n e38c7dd` 於 `906cd92` 查得（另一處在凍結的交接本），只搜 7 碼縮寫，不宣稱窮舉。
