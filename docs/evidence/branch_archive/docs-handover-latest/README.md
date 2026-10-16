# 舊交接本版本保存：`docs/handover-latest` 分支

保存日 2026-10-16（客戶 2026-10-16 核准「只保存、不刪除」）。推送保存用 tag 本環境被拒（HTTP 403），改把 main 正式文件當作歷史證據引用的三個版本原樣落盤到 main。**分支本身仍在、未刪。**

- 來源分支：`origin/docs/handover-latest`（無 PR）
- 分支 head（保存當下）：`ddc5625df7b32ebace068df1ebc69b16318c76dd`
- 原路徑：`docs/handover_2026_09_26_latest.md`（與 main 上現行交接本同名，內容是 2026-09-27 當時的版本）
- 保存格式：`git show <commit>:docs/handover_2026_09_26_latest.md` 的輸出原樣寫入，未壓縮。三份皆已實測：無行尾空白、結尾單一換行、八個禁詞 0 命中、無 session 識別碼，故 `trailing-whitespace`／`end-of-file-fixer` 不會改動內容，逐位元組與來源相同。

## 檔案對照與雜湊（2026-10-16 實跑）

| 本目錄檔名 | 來源 commit（全長） | commit 時間 | 大小（bytes） | sha256 | 被 main 何處引用 |
|---|---|---|---|---|---|
| `885b71a_handover_2026_09_26_latest.md` | `885b71a3dcadc4e9fd063e437f31315d10a2a296` | 2026-09-27T04:23:25+00:00 | 10393 | `a85ccc57936d376fb49375b1073ba73d22996459d5a944a96626cddf79d8562e` | `ACCEPTANCE.md`（約 :517 出處表、:534），以該 SHA 的行號為出處 |
| `fce9176_handover_2026_09_26_latest.md` | `fce9176f407e572b33303a88d93ecf4a82712120` | 2026-09-27T03:27:41+00:00 | 13318 | `7b96bce087f90005326304372f95f41ae29cc1c3335c63a096dda9a7ab50f9c2` | `docs/v2/49_data_integration_plan.md`（約 :512 Q4、:656 (k)、附錄 :888、:889、:891、:892），引第 2、5 節與行號 :63、:65 |
| `ddc5625_handover_2026_09_26_latest.md` | `ddc5625df7b32ebace068df1ebc69b16318c76dd` | 2026-09-27T06:00:51+00:00 | 12138 | `ec0cba188adcce5ccafe9edfbd262cc3486e73f5c058272372e6c9e9efdf5c9c` | `services/v2_tables/alo_holdings.py`（約 :470 docstring，引 `ddc5625` :117「鍵含 BOM、零寬字元、NBSP 的處理」；本檔第 117 行即該句，2026-10-16 實讀） |

引用處以 `git grep -n "885b71a\|fce9176\|ddc5625"` 於 main `cac7c00` 查得（不宣稱窮舉；只搜全長前 7 碼）。`ACCEPTANCE.md` 與 `docs/v2/49` 已行內補「保存於 main：本目錄路徑」。`services/v2_tables/alo_holdings.py` 是 production 檔，**未改**；對應關係記於本檔與交接本〈第六十六次更新〉。

## 驗證指令（repo 根目錄執行）

```
sha256sum docs/evidence/branch_archive/docs-handover-latest/885b71a_handover_2026_09_26_latest.md
git show 885b71a3dcadc4e9fd063e437f31315d10a2a296:docs/handover_2026_09_26_latest.md | sha256sum
```

兩行輸出應相同。另兩份同理。原檔行號在保存檔中不變，可直接以 `sed -n '117p' <本目錄檔>` 對照引用處。
