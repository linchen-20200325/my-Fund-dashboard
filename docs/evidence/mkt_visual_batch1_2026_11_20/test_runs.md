單組作者端實跑紀錄，未經獨立複驗；CI 結果 NOT VERIFIED（尚未推送、無 CI）。
# 測試實跑原文證據（🌍 市場頁視覺批 1，QA M1）
- **被測 head SHA：`eaec528e7192a70bbe6737c4746bcf5836965228`**（分支 feat/ui-v3-mkt-visual-batch1；此 SHA 之後本檔所在 commit 只新增文件，不動程式與測試）。
- 環境：scratchpad venv（streamlit 1.59.2、pytest、playwright）、`UI_V2_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`、`-p no:cacheprovider`、`PYTHONDONTWRITEBYTECODE=1`、本機 Linux；起迄 2026-11-20T05:05:06Z → 2026-11-20T05:26:48Z。
- 指令（逐檔／整目錄各一次；pytest 結尾行原文照錄）：`python -m pytest <目標> -p no:cacheprovider -q --junitxml=…`；poc 檔每檔 `timeout 1500`，**沒有任何檔逾時**。
## 首輪失敗與修正（據實）
首輪（head `d2b21536`）poc 組的 `tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_guards.py` **1 failed, 85 passed**：`test_registry_app_preview_pages_and_shell_do_not_mention_the_preview_and_ui_v3_never_mentions_poc`，
原因＝我新寫的 `theme.pill_css` docstring 字面含 `poc/` 路徑（`AssertionError: ui_v3/design/theme.py … 'poc/' is contained here`）。
已改註解（commit `eaec528e`，只動 docstring），並**全部重跑**（含 ui_v3 全部）；以下全為重跑後的結果。首輪中途為了重跑而終止，未跑完的檔不在首輪記錄內。
## 結果總表（head eaec528e7192a70bbe6737c4746bcf5836965228）
| 目標 | 指令結束碼／耗時 | pytest 結尾行（原文） |
|---|---|---|
| tests/ui_v3（全部，含兩支瀏覽器） | exit 0／264s | `3086 passed, 769 warnings in 262.79s (0:04:22)` |
| tests/poc_assets_preview/test_assets_preview_apptest.py | exit 0／8s | `86 passed in 7.34s` |
| tests/poc_assets_preview/test_assets_preview_browser.py | exit 0／466s | `247 passed, 11 warnings in 464.11s (0:07:44)` |
| tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_apptest.py | exit 0／5s | `29 passed in 4.37s` |
| tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_browser.py | exit 0／76s | `74 passed in 74.62s (0:01:14)` |
| tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_guards.py | exit 0／1s | `86 passed in 0.43s` |
| tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_mutations.py | exit 0／2s | `38 passed in 0.48s` |
| tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_renderer.py | exit 0／1s | `44 passed in 0.25s` |
| tests/poc_fund_search_preview/test_fund_search_apptest.py | exit 0／17s | `47 passed in 16.29s` |
| tests/poc_fund_search_preview/test_fund_search_browser.py | exit 0／288s | `72 passed in 286.39s (0:04:46)` |
| tests/poc_fund_search_preview/test_fund_search_contrast_browser.py | exit 0／63s | `37 passed in 61.66s (0:01:01)` |
| tests/poc_fund_search_preview/test_fund_search_guards.py | exit 0／1s | `87 passed in 0.43s` |
| tests/poc_fund_search_preview/test_fund_search_logic_and_renderer.py | exit 0／2s | `250 passed in 0.52s` |
| tests/poc_nas_diag_preview/test_nas_diag_preview_apptest.py | exit 0／6s | `68 passed in 4.97s` |
| tests/poc_nas_diag_preview/test_nas_diag_preview_browser.py | exit 0／102s | `107 passed in 101.10s (0:01:41)` |

**NOT RUN：無**（逾時 0 個；四個 poc 目錄的 15 個測試檔＋tests/ui_v3 全部皆已實跑）。
## tests/ui_v3 逐檔（junit 彙整；兩支瀏覽器檔為完整非子集）
| 檔 | passed | failed | skipped |
|---|---|---|---|
| test_ui_v3_assets_holding_id_identity | 55 | 0 | 0 |
| test_ui_v3_assets_page_adapter | 127 | 0 | 0 |
| test_ui_v3_assets_page_renderer | 330 | 0 | 0 |
| test_ui_v3_assets_page_viewmodel | 82 | 0 | 0 |
| test_ui_v3_assets_source_contract | 34 | 0 | 0 |
| test_ui_v3_assets_source_import_isolation | 22 | 0 | 0 |
| test_ui_v3_assets_source_mutations | 60 | 0 | 0 |
| test_ui_v3_assets_source_settings_differential | 9 | 0 | 0 |
| test_ui_v3_chart_disclosure_contract | 40 | 0 | 0 |
| test_ui_v3_degraded_first_screen_budget | 86 | 0 | 0 |
| test_ui_v3_design_tokens | 14 | 0 | 0 |
| test_ui_v3_exp_counts | 117 | 0 | 0 |
| test_ui_v3_exp_pool_adapter | 207 | 0 | 0 |
| test_ui_v3_exp_pool_mutations | 63 | 0 | 0 |
| test_ui_v3_exp_pool_viewmodel | 90 | 0 | 0 |
| test_ui_v3_first_screen_c_and_wording_unify | 49 | 0 | 0 |
| test_ui_v3_fixtures_are_fake_guard | 13 | 0 | 0 |
| test_ui_v3_fund_lookup_adapter | 511 | 0 | 0 |
| test_ui_v3_fund_lookup_mutations | 98 | 0 | 0 |
| test_ui_v3_fund_lookup_viewmodel | 170 | 0 | 0 |
| test_ui_v3_import_guard | 80 | 0 | 0 |
| test_ui_v3_market_chart_adapter | 37 | 0 | 0 |
| test_ui_v3_market_chart_svg | 10 | 0 | 0 |
| test_ui_v3_market_page_adapter | 40 | 0 | 0 |
| test_ui_v3_market_page_apptest | 17 | 0 | 0 |
| test_ui_v3_market_page_browser | 92 | 0 | 0 |
| test_ui_v3_mkt_evidence_alignment | 8 | 0 | 0 |
| test_ui_v3_nas_diag_renderer | 118 | 0 | 0 |
| test_ui_v3_nas_diag_viewmodel | 135 | 0 | 0 |
| test_ui_v3_navigation_shell | 43 | 0 | 0 |
| test_ui_v3_no_engineering_leak_guard | 42 | 0 | 0 |
| test_ui_v3_page_registry_guard | 8 | 0 | 0 |
| test_ui_v3_preview_navigation_pages_guard | 2 | 0 | 0 |
| test_ui_v3_preview_not_formal_guard | 25 | 0 | 0 |
| test_ui_v3_preview_wording_guard | 13 | 0 | 0 |
| test_ui_v3_readonly_guard | 61 | 0 | 0 |
| test_ui_v3_semantics_rules | 98 | 0 | 0 |
| test_ui_v3_token_contrast | 5 | 0 | 0 |
| test_ui_v3_top_nav_browser | 10 | 0 | 0 |
| test_ui_v3_viewmodel_contract | 46 | 0 | 0 |
| test_ui_v3_wording_fidelity | 19 | 0 | 0 |
| **合計** | **3086** | **0** | **0** |

## poc 四組逐檔（junit 彙整）
| 檔 | passed | failed | skipped |
|---|---|---|---|
| tests/poc_assets_preview/test_assets_preview_apptest.py | 86 | 0 | 0 |
| tests/poc_assets_preview/test_assets_preview_browser.py | 247 | 0 | 0 |
| tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_apptest.py | 29 | 0 | 0 |
| tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_browser.py | 74 | 0 | 0 |
| tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_guards.py | 86 | 0 | 0 |
| tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_mutations.py | 38 | 0 | 0 |
| tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_renderer.py | 44 | 0 | 0 |
| tests/poc_fund_search_preview/test_fund_search_apptest.py | 47 | 0 | 0 |
| tests/poc_fund_search_preview/test_fund_search_browser.py | 72 | 0 | 0 |
| tests/poc_fund_search_preview/test_fund_search_contrast_browser.py | 37 | 0 | 0 |
| tests/poc_fund_search_preview/test_fund_search_guards.py | 87 | 0 | 0 |
| tests/poc_fund_search_preview/test_fund_search_logic_and_renderer.py | 250 | 0 | 0 |
| tests/poc_nas_diag_preview/test_nas_diag_preview_apptest.py | 68 | 0 | 0 |
| tests/poc_nas_diag_preview/test_nas_diag_preview_browser.py | 107 | 0 | 0 |
| **合計** | **1272** | **0** | **0** |

## 首輪失敗原文（節錄）
```
........................................................................ [ 83%]
..........F...                                                           [100%]
=================================== FAILURES ===================================
_ test_registry_app_preview_pages_and_shell_do_not_mention_the_preview_and_ui_v3_never_mentions_poc _

    def test_registry_app_preview_pages_and_shell_do_not_mention_the_preview_and_ui_v3_never_mentions_poc():
        files = [ROOT / "ui_v3" / "shell" / "registry.py", ROOT / "ui_v3" / "app_preview.py"]
        files += sorted((ROOT / "ui_v3" / "pages").glob("*.py")) + sorted((ROOT / "ui_v3" / "shell").glob("*.py"))
        assert len(files) >= 8 and all(f.exists() for f in files)
        for f in files:
            assert not re.search(r"fund_lookup_component|FundLookupComponent", f.read_text(encoding="utf-8")), f.name
        for f in sorted((ROOT / "ui_v3").rglob("*.py")):
>           assert "poc/" not in f.read_text(encoding="utf-8"), f.relative_to(ROOT).as_posix()
E           AssertionError: ui_v3/design/theme.py
E           assert 'poc/' not in '# -*- codin...')}}}\n"""\n'
E             
E             'poc/' is contained here:
E                         poc/dual_theme_isolated 有同款先例）；(2) `label:has(input:focus-visible)`——標準偽類。任一生效即出環；
E             ?           ++++
E                   - 「檢視／期間／…」標籤與選項同列（標籤 `type.caption`、無額外上下距）。
E                   ⚠️ 依賴 Streamlit 內部 `data-testid`／`data-selected`／`data-focus-visible`（80 §17.1 已知限制）；升版若改 DOM，
E                   `test_ui_v3_market_page_browser.py` 的 pill 與焦點環守衛會轉紅。"""...
E             
E             ...Full output truncated, use '-vv' to show

tests/poc_fund_lookup_component_preview/test_fund_lookup_cmp_guards.py:434: AssertionError
=========================== short test summar
```

## 其他原文
- `tests/ui_v3` 完整 pytest 輸出（含警告）過長，未入庫；結尾行見上表、逐檔 junit 見上節。
- 瀏覽器兩支：`test_ui_v3_market_page_browser.py` 與 `test_ui_v3_top_nav_browser.py` 均在 `tests/ui_v3` 整目錄內實跑（上表逐檔）。
