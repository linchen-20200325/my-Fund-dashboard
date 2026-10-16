# WIP commit 保存：`wip/exp-c2-ui-wiring-round2-unaudited`

保存日 2026-10-16（客戶 2026-10-16 核准「只保存、不刪除」）。推送保存用 tag 本環境被拒（HTTP 403），改把該 commit 的 patch 落盤到 main。**分支本身仍在、未刪。**

- 來源分支：`origin/wip/exp-c2-ui-wiring-round2-unaudited`
- 分支 head（保存當下）：`4d00b6b4c5aa8b225c73675de3b209513832f041`，parent `d00365c9fbc561504bf9018e931fa74ddaf7ad3e`，commit 時間 2026-10-14T15:05:41+00:00，分支上只有這 1 顆 commit 相對 parent。
- 性質（該 commit 自陳）：#966 修正輪 2 進行中被暫停的工作樹內容，未完成、未跑全套測試、未經任何稽核，不得直接合併或 cherry-pick。
- 變更範圍（`git show --stat`）：`docs/v2/44_fund_ui_ssot.md`、`docs/v2/49_data_integration_plan.md`、`tests/ui_v2/_exp_wired_fixture.py`、`tests/ui_v2/test_alo_logic.py`、`tests/ui_v2/test_exp_live_wiring_logic.py`、`tests/ui_v2/test_exp_logic.py`、`ui_v2/exp/live.py`，7 檔 233 行增、22 行刪。

## 取代關係

#966 已以正式修正輪合併，設計與本 WIP 不同：main 改由資料層在 `div_ccy_differs` 那一支交出 `provenance["conflict_rejected_rows"]`（L2），畫面層讀這個計數決定顯示，見 `docs/v2/49_data_integration_plan.md` 第 (ab) 條「2026-10-15 #966 修正輪 2 補註」（約 :747）。本 WIP 的方向（Q7 tooltip 補 skipped／被剔除列分支、`plain_reason` 效能上限等）已被該設計取代；兩者逐行比對本組未做。

## 保存的檔（2026-10-16 改為只存程式差異）

| 本目錄檔名 | 產生指令 | 原始大小（bytes） | 原始 sha256 | gzip 後 sha256 |
|---|---|---|---|---|
| `4d00b6b_diff.patch.gz` | `git diff 4d00b6b^ 4d00b6b`，輸出以 `gzip -9 -n` 壓縮 | 32271 | `bb59da340e662a90c8073a17eb23c1bf1e68443d35a4018975e6514236053f19` | `7ed225ce271857fbc32d7a348a911cfafe6d3951e2090837edd2d317442ddfae` |

驗證：

```
gzip -dc docs/evidence/branch_archive/wip-exp-c2-ui-wiring-round2-unaudited/4d00b6b_diff.patch.gz | sha256sum
git diff 4d00b6b4c5aa8b225c73675de3b209513832f041^ 4d00b6b4c5aa8b225c73675de3b209513832f041 | sha256sum
```

兩行輸出應相同，且等於上表「原始 sha256」。

## commit 資訊（只存程式差異，commit message 另記於此）

- 全長 SHA：`4d00b6b4c5aa8b225c73675de3b209513832f041`
- 作者時間：2026-10-14T15:05:41+00:00
- 標題：WIP（未完成、未稽核）：#966 修正輪 2 進行中被暫停的工作樹內容
- 正文：

```text
客戶 2026-10-14 因額度暫停專案，實作組在半途被停止。本 commit 只為保存工作樹，
不代表完成、未跑全套測試、未經任何稽核，不得直接合併或 cherry-pick 進 #966。
內容方向：Q7 tooltip 補 skipped／被剔除列分支、plain_reason 效能上限等（見交接文件）。
```

已刻意略去署名行與 session 網址，原文以 SHA 在 GitHub 查。

> 沿革（有意識的更正，不是漏刪；2026-10-16；決策者：AI 總管）：本目錄第一版存的是 `git format-patch -1 --stdout` 的 gzip（`4d00b6b_format-patch.patch.gz`，原始 sha256 `1fa0522d8c9ec9ae3ea716af79e9733580da38c3a3e5d9b56b805f517674e3e0`），其中原樣帶著該 commit 的署名行與 session 網址。總管判定 main 不得新增 session 網址與署名行，該檔已在下一顆 commit 移除，改存上表的純程式差異；第一版 commit 本身未改寫。

## 被 main 哪些地方引用（2026-10-16 實查，main ＝ `cac7c00`；不宣稱窮舉）

`docs/handover_2026_09_26_latest.md` 約 :789、:1731、:1759（已於第六十六次更新行內補上本目錄路徑）。
