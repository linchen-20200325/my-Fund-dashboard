# 歷史搬出區（NOT CURRENT）

> ⛔ **本目錄全部是「Historical evidence only — not current contract」。** 不得當現行規則、現行狀態、implementation authority 引用。現行規則入口：`PROJECT_RULES.md` 0.4「現行規則索引」；現行狀態：`docs/HANDOFF.md`。

2026-11-03 Canonical Rule Convergence 批（客戶 2026-11-03 指示「現行區只留最新規則；歷史移到 history／evidence」；`DEC-2026-11-03-08`）把已被取代、或屬過往現況紀錄的舊內容**逐字**從現行文件搬到這裡；原位置現行區改留 `superseded:`／「歷史見」指標。**Git 歷史未改寫、沒有刪除任何稽核證據。**

| 檔 | 內容 | 區塊 id | 原位置（搬出前基準 commit `82ba783f`） |
|---|---|---|---|
| `2026-11-03_handoff_pre_convergence.md` | 舊 `docs/HANDOFF.md` 全文 | H1 | `docs/HANDOFF.md` 整檔 |
| `2026-11-03_backlog_bl0536_row.md` | BL-0536 舊整列 | B1 | `docs/BACKLOG.md` BL-0536 |
| `2026-11-03_project_rules_and_v2_81_superseded.md` | 13.2 第 1 點舊五頁、0.5 舊 hygiene、81 線框 Q5 A 舊行與主判讀舊字樣 | P1、P2、W1、W2 | `PROJECT_RULES.md`、`docs/v2/81` |

**防遺失機制**：每個區塊在 `MOVED-BEGIN` 標記記 `sha256` 與位元組數；`tests/test_canonical_rule_consistency.py` 重算每個區塊的 sha256 比對標記，並在可取得 `82ba783f` 時與該 commit 的原文逐位元組比對。搬進來的文字**不准改**；要補註寫在區塊外。
