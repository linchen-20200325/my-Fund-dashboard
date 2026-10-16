# 探測報告保存：Yahoo 匯率日線觀測日（`probe/fx-obs-date-results`）

保存日 2026-10-16（客戶 2026-10-16 核准「只保存、不刪除」）。原本打算以保存用 tag 鎖住舊 commit，本環境推送 tag 被拒（HTTP 403），改把原始檔與來源資訊落盤到 main。**分支本身仍在、未刪。**

- 來源分支：`origin/probe/fx-obs-date-results`
- 分支 head（保存當下）：`6dd3e62646bf7f4c9498eae5deb0cac854f635a0`
- 該分支的檔案只有下表三份報告（`git ls-tree -r --name-only 6dd3e62646bf7f4c9498eae5deb0cac854f635a0` 實跑，2026-10-16）。
- 產生方式：`.github/workflows/fx_obs_date_probe.yml` 執行 `scripts/probe_fx_obs_date.py`，報告推到上述分支。
- 保存格式：`git show <引入 commit>:<原路徑>` 的輸出逐位元組不改，以 `gzip -9 -n` 壓縮（避免超過 `check-added-large-files` 的 500KB 上限，也避免文字類 hook 改寫內容）。

## 檔案對照

| 本目錄檔名 | 原路徑（分支上） | 引入該檔的 commit | commit 時間 | GitHub run | 報告內 `generated_at_utc` | 報告內 `executed_sha` |
|---|---|---|---|---|---|---|
| `20261013T185433Z_run38450455092_report.json.gz` | `results/20261013T185433Z_run38450455092/report.json` | `678812d10cb8d0dfd2c601f98f58242cb746e8f8` | 2026-10-13T18:54:35+00:00 | `38450455092` | 2026-10-13T18:54:31.263102+00:00 | `2488ffa6a1a95654ef3b860ae8efb36741360b8b` |
| `20261014T041819Z_run38510633247_report.json.gz` | `results/20261014T041819Z_run38510633247/report.json` | `92442ac326a69043f45392bf51419ac725a58356` | 2026-10-14T04:18:20+00:00 | `38510633247` | 2026-10-14T04:18:15.157678+00:00 | `1aa3f93c0e2830ad5f9b549fbf222499f350f52e` |
| `20261014T064729Z_run38524215912_report.json.gz` | `results/20261014T064729Z_run38524215912/report.json` | `6dd3e62646bf7f4c9498eae5deb0cac854f635a0` | 2026-10-14T06:47:30+00:00 | `38524215912` | 2026-10-14T06:47:25.588769+00:00 | `753d59ca69b58ae8ec28bba7e02818e70d4287f3` |

「引入該檔的 commit」以 `git log --format='%H %cI' origin/probe/fx-obs-date-results -- <原路徑>` 查得；三份各只有一筆 commit，即分支 head 上的內容與引入時相同。

## 雜湊與大小（2026-10-16 實跑）

| 本目錄檔名 | 原始大小（bytes） | 原始 sha256 | gzip 後 sha256 |
|---|---|---|---|
| `20261013T185433Z_run38450455092_report.json.gz` | 153458 | `e2a757216d4c008e60de8af55526a96e034575c089db5ca0b8bd016a9aebaaf7` | `86698a8a5139a3c5315cc31e2b5fa98d1b9b3f645b2e598c1428c75214349f10` |
| `20261014T041819Z_run38510633247_report.json.gz` | 199768 | `2029ae664b6555d019f4ae37648cb15b71dc013ea407c364035e20f5e34d9289` | `e2fad6e25e0bb09b371e29df4d0d257715766cb0e83dfb594800a0e80300c599` |
| `20261014T064729Z_run38524215912_report.json.gz` | 869097 | `fd1be036d56d1e4acba8eb160557f58304ea2e46fdb4e2e9122fa843163e4a14` | `ad1463a24459fdd1e17d5e6b764d0ee2b0026e329dd940cd0f35db8530bc4a68` |

## 驗證指令（repo 根目錄執行）

```
gzip -dc docs/evidence/probe_fx_obs_date/20261013T185433Z_run38450455092_report.json.gz | sha256sum
git show 678812d10cb8d0dfd2c601f98f58242cb746e8f8:results/20261013T185433Z_run38450455092/report.json | sha256sum
```

兩行輸出應相同，且等於上表「原始 sha256」。另兩份同理（換成各自的檔名、commit 與路徑）。分支若日後被刪，第二行改用 `git fetch origin <commit>` 取回物件後再跑；取不回時以上表的原始 sha256 為準。

## 被 main 哪些地方引用（2026-10-16 以 `git grep` 查 run ID 與分支名，量測時 main ＝ `cac7c00`；不宣稱窮舉）

- `run38450455092`：`docs/v2/49_data_integration_plan.md` 第 (i) 條（約 :429、:634、:640）與附錄第 10 輪（約 :894）；`scripts/probe_fx_obs_date.py`（約 :27）；`services/v2_tables/market_indicator.py`（約 :88）；`tests/test_v2_tables_market_indicator_exchange_tz.py`（約 :9-10，fixture 時間戳與收盤值逐字抄自本報告 `raw_excerpt`）。
- `run38510633247`：`docs/v2/49_data_integration_plan.md`（約 :640）；`scripts/probe_fx_obs_date.py`（約 :540）。
- `run38524215912`：`docs/v2/49_data_integration_plan.md`（約 :644、:647、:648）；`services/v2_tables/market_indicator.py`（約 :112-113）；`tests/test_v2_tables_market_indicator_fx_prev_day.py`（約 :7-8）。
- 分支名 `probe/fx-obs-date-results`：另見 `.github/workflows/fx_obs_date_probe.yml`、`tests/test_fx_obs_date_probe_workflow.py`（那兩處是寫入目標設定，不是引用報告內容）。

`docs/v2/49_data_integration_plan.md` 已於上列各處行內補「保存於 main：本目錄路徑」。production 程式、script 與測試檔的引用**未改**（本批不動程式），對應關係只記在本檔與交接本〈第六十六次更新〉。
