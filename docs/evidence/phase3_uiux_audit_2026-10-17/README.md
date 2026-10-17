# Phase 3 UI/UX 稽核報告存檔（2026-10-17）

2026-10-17 建立。本目錄存放客戶 2026-10-17 Phase 3 UI/UX 提示語（`docs/DECISIONS.md` `DEC-2026-10-17-02`）之下，三組唯讀稽核的**原始報告**，作為 `docs/v2/58_ui_ux_constitution.md` 與 `docs/v2/59_b_line_390_wireframes.md` 的證據來源。性質與 `docs/evidence/` 其他子目錄不同：這裡存的是**本 repo 內部稽核組的報告**，不是客戶原文、也不是分支內容；報告裡的【讀法】【推論】都是稽核組判斷，**不是客戶裁示**。

## 存檔清單

| 檔名 | 內容 | 產出組 | 量測基準 |
|---|---|---|---|
| `ux_inventory.md` | B 線 `ui_v2/` 五頁現況 UX 盤點（A 現況 inventory、B Data Health 重複、C 工程用語、D Controls／CTA、E 四態、H 390px） | 品管與紅隊稽核組（唯讀） | main `57f03c9`（全長 `57f03c9188f35cf0aaee147625e159aaa002b6ad`） |
| `oauth_rw_audit.md` | F OAuth → Sheet → worksheet 能力盤點、G READ／WRITE 邊界稽核 | 資料工程組（安全邊界稽核，唯讀） | 同上 |
| `governance_audit.md` | 新提示語與凍結 44、子法 1＋57、既有裁示的衝突；文件落點建議 | 架構與文件組（治理衝突稽核，唯讀） | 同上 |

三份皆**單組產出、未經第二組獨立複驗**（各報告自陳）。

## 雜湊（2026-10-17 實跑）

| 檔名 | 原始報告（scratchpad 轉存檔）bytes／sha256 | 本目錄存檔 bytes／sha256 |
|---|---|---|
| `ux_inventory.md` | 33712 ／ `6459676036f4e559b8de545636f17ecfd9223f6a0a3d1075562f5cb9d869c406` | 同左（逐位元組未改） |
| `oauth_rw_audit.md` | 41203 ／ `574441b59c422970a9bfbd2d1d20cae10ea402f72545a486881643b368cb22bc` | 41209 ／ `f9697ea4daaf1719fd38c3bb65432d822cdd7472a01420fb17609fd559010f1a` |
| `governance_audit.md` | 31658 ／ `0b871e097217a38c7ead863b3dbae133411f41db25ad112ebb8893501747e8d6` | 31682 ／ `fb2a6efd348ea5fda98bb45aa23c9e82d9dc9f2d596d2bd1667a684da316a918` |

- 原始報告在 scratchpad、不入 repo，第二欄在 repo 內只能用下方指令從存檔推回。

## 撞字登記

- `oauth_rw_audit.md` 第 245 行、`governance_audit.md` 第 32、107、109、119 行含交接本第 7 節〈客戶 2026-10-05 接手訊息：禁詞〉詞表的**第 3 個詞**（第 32 行是轉引 44 第 1.2 節「禁排名為…」那一句，其餘四處是稽核組自己的用語）。依該節〈禁詞〉體例改寫成 Unicode 跳脫碼 `\u63a8\u85a6`，其餘一字未改。
- 其餘七個詞：三份以碼位組字掃描 0 命中（2026-10-17 實跑）。
- 已實測：三份無行尾空白、結尾單一換行、無 session 識別碼、無合併衝突標記。

## 報告內引用的暫存檔（已不可取得）

- 三份報告引用的 `dumps/`、`m390/`、`m390b/`、`tools/`、`scripts/`、`grep_*.txt`、`ast_*.txt`、`*.py` 掃描腳本與截圖，都放在稽核當下的 scratchpad，**已不可取得、未存入 repo**（只複製 `.md` 報告；venv、截圖、dumps 刻意不收）。報告裡「見 `dumps/...`」之類的指標，讀作「稽核當下有這份輸出」，不是 repo 內可回查的檔。
- `ux_inventory.md` 的 AppTest／390px 實測環境是 scratchpad 內另建的 venv（CPython 3.13.16、streamlit 1.59.2），**不是 CI 環境**。

## 驗證

repo 根目錄執行；兩行輸出應分別等於上表 `oauth_rw_audit.md`、`governance_audit.md` 的原始報告 sha256（以碼位組字還原，不用 `unicode_escape` 解碼）：

~~~~
python3 - <<'PY'
import hashlib
for f in ('oauth_rw_audit.md', 'governance_audit.md'):
    t = open('docs/evidence/phase3_uiux_audit_2026-10-17/' + f, encoding='utf-8').read()
    d = t.replace('\\u63a8\\u85a6', chr(0x63a8) + chr(0x85a6))
    print(hashlib.sha256(d.encode()).hexdigest())
PY
~~~~

存檔本身：`sha256sum docs/evidence/phase3_uiux_audit_2026-10-17/*.md`（應等於上表第三欄；`ux_inventory.md` 等於第二欄）。
