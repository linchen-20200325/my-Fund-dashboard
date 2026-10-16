# 客戶裁示逐字存檔

2026-10-16 建立。本目錄存放**客戶在對話中正式裁示、由總管逐字轉存**的全文，讓 `docs/DECISIONS.md` 條目的 provenance 可以標「逐字」並指回 repo 內的原文。性質與 `docs/evidence/` 其他子目錄（分支成果保存）不同：這裡存的是裁示原文，不是分支內容；**本目錄建立時沒有刪除任何分支**。

## 存檔清單

| 檔名 | 內容 | 來源 | 存檔日 | base | 大小（bytes） | 整檔 sha256 |
|---|---|---|---|---|---|---|
| `2026-10-16_governance_11_rulings.md` | 客戶 2026-10-16 治理十一項裁示全文（`docs/DECISIONS.md` `DEC-2026-10-16-03`～`DEC-2026-10-16-13`） | 客戶 2026-10-16 對話中正式裁示，經總管逐字轉存 | 2026-10-16 | main `ab30239`（全長 `ab302390886e1818f0d9a56afccdf3ba9dd7a41b`） | 9439 | `77ca3b636a590706eaea07016a279003feb25dfd3b2f5480fad1bdce566497f5` |
| `2026-10-16_proposal8_approval.md` | 客戶 2026-10-16 提案單 #8 核准裁示全文（`docs/DECISIONS.md` `DEC-2026-10-16-14`；落地為 `docs/v2/57_amendment_8_directional_judgment.md`） | 客戶 2026-10-16 對話中正式核准，經總管逐字轉存 | 2026-10-16 | main `66b6033`（全長 `66b60336589b7fe04bce051f629bb76ff41c692f`） | 6170 | `21c5e3843d76aa21ca53223f505f5a6583025cc066719ea450197fa423cebb06` |

### `2026-10-16_governance_11_rulings.md` 的三個雜湊

| 對象 | 大小（bytes） | sha256 |
|---|---|---|
| 整檔（檔頭說明＋圍欄） | 9439 | `77ca3b636a590706eaea07016a279003feb25dfd3b2f5480fad1bdce566497f5` |
| 圍欄內文（跳脫碼形式，即檔內實際位元組） | 7422 | `992cc0646117cd5e67ac3811ae9d92799db46e68e63a82b06672411a4c5c438b` |
| 圍欄內文把兩組跳脫碼換回原字後（＝總管轉存的原文） | 7404 | `33ccac342291af5511a84a1268b18dfbf69e7e5a3be55d0c0d2f29deca12f9c0` |

- 第三列與總管轉存給文件實作組的原文檔逐位元組相同（文件實作組 2026-10-16 以 `sha256sum` 對兩者實跑比對）。總管轉存的原文檔在 scratchpad、不入 repo，所以第三列在 repo 內只能用下方指令從本檔推回。
- 雜湊為 2026-10-16 實跑。

### `2026-10-16_proposal8_approval.md` 的三個雜湊

| 對象 | 大小（bytes） | sha256 |
|---|---|---|
| 整檔（檔頭說明＋圍欄） | 6170 | `21c5e3843d76aa21ca53223f505f5a6583025cc066719ea450197fa423cebb06` |
| 圍欄內文（跳脫碼形式，即檔內實際位元組） | 3626 | `8a0ab952b71f09142e7277243d994fe111de2a44efc763c98d23aaf8a237e0e2` |
| 圍欄內文把兩組跳脫碼換回原字後（＝總管轉存的原文） | 3608 | `81fa7da3edd0289e8172e4950d517d4c9f86c918e32407b66f275eedb80ed770` |

- 第三列與總管轉存給文件實作組的原文檔逐位元組相同（文件實作組 2026-10-16 以 `sha256sum` 對轉存檔實跑，並以本目錄驗證指令從存檔推回，兩值相同）。總管轉存的原文檔在 scratchpad、不入 repo。
- 第二、三列也寫在該檔檔頭；整檔那一列涵蓋檔頭，只能登記在本表。
- 雜湊為 2026-10-16 實跑。

## 撞字登記

全文含交接本第 7 節〈客戶 2026-10-05 接手訊息：禁詞〉詞表的**第 7、8 個詞**，共 3 處，都在治理第 6 項「未來允許的方向」列舉內（圍欄內第 114、116、117 行）。依該節〈禁詞〉體例以 Unicode 跳脫碼書寫（`\u52a0\u78bc`、`\u6e1b\u78bc`），其餘一字未改。第 1～6 個詞以 2026-10-16 碼位組字掃描 0 命中。依客戶 2026-10-15 Phase 1.5（A+ 修正版）裁示，第 5～8 個詞已不是永久禁詞；本批新增行仍以 0 命中為目標，故改用跳脫碼並在此登記（與 `branch_archive/pr838/README.md` 不同：那裡是逐字摘錄照字面保留、只做登記）。

`2026-10-16_proposal8_approval.md`：裁示全文同樣含詞表的**第 7、8 個詞**，共 3 處，都在「新正式政策邊界」一段允許的方向性狀態列舉內（圍欄內第 62、64、65 行）：第 7 個詞單獨一列一次、「暫停」後接第 7 個詞一次、第 8 個詞單獨一列一次。依同一體例以 Unicode 跳脫碼書寫，其餘一字未改；第 1～6 個詞以 2026-10-16 碼位組字掃描 0 命中。

已實測：無行尾空白、結尾單一換行、無 session 識別碼、無合併衝突標記。

## 驗證

repo 根目錄執行；第一行應等於上表第二列，第二行應等於第三列（以碼位組字還原，不用 `unicode_escape` 解碼，避免把其餘中文一起弄壞）：

~~~~
python3 - <<'PY'
import hashlib, re
t = open('docs/evidence/decisions/2026-10-16_governance_11_rulings.md', encoding='utf-8').read()
b = re.search(r'```text\n(.*)```\n\Z', t, re.S).group(1)
print(hashlib.sha256(b.encode()).hexdigest())
d = b.replace('\\u52a0\\u78bc', chr(0x52a0) + chr(0x78bc)).replace('\\u6e1b\\u78bc', chr(0x6e1b) + chr(0x78bc))
print(hashlib.sha256(d.encode()).hexdigest())
PY
~~~~

整檔：`sha256sum docs/evidence/decisions/2026-10-16_governance_11_rulings.md`。

`2026-10-16_proposal8_approval.md`：把上方指令裡的檔名換成 `docs/evidence/decisions/2026-10-16_proposal8_approval.md` 再跑一次；第一行應等於 `2026-10-16_proposal8_approval.md` 雜湊表第二列，第二行應等於第三列。整檔：`sha256sum docs/evidence/decisions/2026-10-16_proposal8_approval.md`。
