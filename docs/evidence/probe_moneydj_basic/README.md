# 探測報告保存：MoneyDJ 基本資料頁（`probe/moneydj-basic-results`）

保存日 2026-10-16（客戶 2026-10-16 核准「只保存、不刪除」）。推送保存用 tag 本環境被拒（HTTP 403），改把原始檔與來源資訊落盤到 main。**分支本身仍在、未刪。**

- 來源分支：`origin/probe/moneydj-basic-results`
- 分支 head（保存當下）：`39672f991b015b5996906ad8c4b24319d4690bfa`
- 該分支的檔案只有下表這一份報告（`git ls-tree -r --name-only 39672f991b015b5996906ad8c4b24319d4690bfa` 實跑，2026-10-16）。
- 產生方式：`.github/workflows/moneydj_basic_probe.yml` 執行 `scripts/probe_moneydj_basic_page.py`（#961），報告推到上述分支。
- 保存格式：`git show <引入 commit>:<原路徑>` 的輸出逐位元組不改，以 `gzip -9 -n` 壓縮。

## 檔案對照

| 本目錄檔名 | 原路徑（分支上） | 引入該檔的 commit | commit 時間 | GitHub run | 報告內 `generated_at_utc` | 報告內 `executed_sha` |
|---|---|---|---|---|---|---|
| `20261014T101710Z_run38548232056_report.json.gz` | `results/20261014T101710Z_run38548232056/report.json` | `39672f991b015b5996906ad8c4b24319d4690bfa` | 2026-10-14T10:17:10+00:00 | `38548232056` | 2026-10-14T10:15:44.812200+00:00 | `17840f312426a0251337790815d3ee072d03105e`（報告內 `trigger_sha` 同值；報告無 `github_sha` 欄） |

## 雜湊與大小（2026-10-16 實跑）

| 本目錄檔名 | 原始大小（bytes） | 原始 sha256 | gzip 後大小（bytes） | gzip 後 sha256 |
|---|---|---|---|---|
| `20261014T101710Z_run38548232056_report.json.gz` | 755719 | `a6b5a126f4f0bbc1b31930b9a5b259fe68577922e32365c454078f7c4dbaa3ce` | 493680 | `7d797f32f5557f969c76133fe0b5694752370a740db5bb30c63d8182b177ccb9` |

⚠️ gzip 後 493680 bytes，離 `check-added-large-files` 的 512000 bytes 上限約 18KB。日後若要再保存同類較大的報告，需先量。

## 驗證指令（repo 根目錄執行）

```
gzip -dc docs/evidence/probe_moneydj_basic/20261014T101710Z_run38548232056_report.json.gz | sha256sum
git show 39672f991b015b5996906ad8c4b24319d4690bfa:results/20261014T101710Z_run38548232056/report.json | sha256sum
```

兩行輸出應相同，且等於上表「原始 sha256」。

## 被 main 哪些地方引用（2026-10-16 以 `git grep` 查 run ID 與分支名，量測時 main ＝ `cac7c00`；不宣稱窮舉）

- `docs/v2/49_data_integration_plan.md` 第 (aa) 條（約 :727，已行內補「保存於 main：本檔路徑」）；第 (r) 條（約 :681）描述的是報告推送位置的格式，未改。
- `repositories/fund/declared_profile.py`（約 :35、:469）：引 `results/20261014T101710Z_run38548232056`。**production 檔，未改**，內容保存於本目錄。
- `tests/test_declared_profile.py`（約 :947）：引 `origin/probe/moneydj-basic-results:results/20261014T101710Z_run38548232056/report.json`。**測試檔，未改**。
- `tests/fixtures/moneydj_basic/manifest.json` 的 `source_report` ＝ `origin/probe/moneydj-basic-results:results/20261014T101710Z_run38548232056/report.json`：**測試資料未改**。對應關係：該欄指向的報告即本目錄 `20261014T101710Z_run38548232056_report.json.gz`；manifest 內各頁的 `report_raw_sha256` 是報告內各頁原始 HTML 的雜湊，不是報告檔本身的雜湊（本檔上表那一個才是）。
- 分支名另見 `.github/workflows/moneydj_basic_probe.yml`、`tests/test_moneydj_basic_probe.py`、`scripts/probe_moneydj_basic_page.py`（寫入目標設定，不是引用報告內容）。
