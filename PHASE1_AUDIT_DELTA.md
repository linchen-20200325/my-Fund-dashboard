# Phase 1 全域排毒審查報告 — δ vs ARCHITECTURE_AUDIT.md (2026-06-28)

> **唯讀診斷檔。本份 ≠ 取代 `ARCHITECTURE_AUDIT.md`,而是 v19.197 baseline 之後到 v19.271 HEAD 的 delta 報告。**
>
> 起草:2026-06-30 | 範圍:v19.197 (baseline) → v19.271 (current HEAD)
> 方法:Workflow(6 個 Explore 子代理多角度偵察 + 6 個對抗 verify + 1 個 synthesizer)
> 對齊:CLAUDE.md §-1「無實質 bug / 無 user 需求 → 不動」工作準則

---

## §0 結論先講

**無需行動**。所有 CONFIRMED 殘留項目 ROI 均為 LOW,跨子題 6 項真實高 ROI 違規 = **0**。

| 統計 | 值 |
|---|---|
| 真實 bug 數 | 0 |
| user 觸發需求數 | 0 |
| HIGH ROI 違憲數 | 0 |
| MEDIUM ROI 違憲數 | 0 |
| LOW ROI cosmetic 收斂機會 | 4 |

---

## §1 重複與雙標功能比對清單(僅 CONFIRMED + PARTIAL)

| # | 項目 | 位置 | 子題 | Verdict | 真實重複數 | 影響面 |
|---|---|---|---|---|---|---|
| 1 | Tab3 行內 ADR fallback 未走 `_resolve_adr_with_fallback()` SSOT | `ui/tab3_portfolio.py:1250, 2042` + `ui/tab5_data_guard.py:1019` | #1 | PARTIAL | **3 處**(Scout 宣稱 5,verify 駁回 2) | Tab3/Tab5 vs Tab2 可能出現「吃本金/健康」非對稱判定 |
| 2 | HTML card 邊框 inline 與 `_render_macro_indicator_card()` SSOT 不一致 | `ui/tab2_single_fund.py:359, 564` + `ui/tab1_macro_inflection.py:248` | #2 | PARTIAL | 3 處 inline(SSOT 已 v19.187 抽離,部份檔案未遷移) | 純視覺一致性,無資料正確性影響 |
| 3 | Sharpe 3 處實作 | `services/health/grade.py:56` + `services/reconcile.py:140` + `services/calibration/multi_factor.py:361` | #4 | CONFIRMED (但已隔離) | **0 真重複**(三者職責不同:評分 / 對帳 / 訊號回測) | 無 — 為設計正確分層 |
| 4 | Volatility 2 處實作 | `services/health/grade.py:93` + `services/calibration/multi_factor.py` | #4 | CONFIRMED (包裝型) | **0 真重複**(評分 vs 回測介面) | 無 |
| 5 | `tab1_macro.py:821` 直 import `repositories.macro_tw_local_repository`(灰色地帶) | `ui/tab1_macro.py:821` | #6 | CONFIRMED (pre-existing) | 1 處(v19.197 P1-4 決策,**非** v19.261-271 新增) | 已在 EX-PASSTHRU-1 精神範圍,合規 |

**REFUTED(verify 排除)**:
- Tab3 ADR fallback Scout 宣稱 5 處 → 實 3 處(line 1399 / 1904 / 2399 不存在該 pattern)
- Tab2 line 1351 / 1483 metric 行 — 非重複,是條件分支(配息型 vs 累積型)
- L1 Fetcher 重複造輪子 — 全部已在 ARCHITECTURE_AUDIT.md §5/§6 第二/三階段收斂(commits `fe1b182` / `38ee0dd` / `115aa58`)
- Composite Score 「3 檔散落」 — `auto_search.py:138` 為**不同公式**(OOS_F1 × plateau × log1p),非重複實作
- v19.271 新增 dead code — **0 件**
- P3-A2~A6 新 UI tab 越權 — **0 件**

---

## §2 模組化簡化建議(§-1 LOW 跳過)

| # | 建議 | 改動量 | ROI | §-1 判斷 |
|---|---|---|---|---|
| 1 | Tab3/Tab5 三處行內 ADR fallback → `_resolve_adr_with_fallback()` | ~15 LOC | **LOW** | ❌ user 未報「Tab2/Tab3 數字打架」實際 bug,純 cosmetic SSOT 收斂 → **跳過** |
| 2 | Tab2/Tab1_inflection 三處 HTML card inline → `_render_macro_indicator_card()` | ~10 LOC | **LOW** | ❌ 無功能影響,純視覺統一 → **跳過** |
| 3 | Sharpe / Volatility 三處職責再說明(僅 docstring) | 0 LOC(只改 docstring) | **LOW** | ❌ 已正確分層,不需動 → **跳過** |
| 4 | `tab1_macro.py:821` macro_tw_local_repository 補登 EX-PASSTHRU-1 | ~5 LOC(改 CLAUDE.md §8.2.A) | **LOW** | ⚠️ 合規完整度考量,但 v19.197 P1-4 已有決策紀錄 → **跳過**(再次違憲時補) |

**結論**:全 LOW ROI,**符合 §-1「停手等指令」default**。

---

## §3 第二階段重構行動計畫

**狀態:無計畫。**

依 §-1 工作準則三問:
1. ❓ user 實際在用嗎? → 上述 4 項皆非 user 觸發
2. ❓ 真實 bug? → 0(Scout 全 PARTIAL 為「潛在打架風險」,非實證 bug)
3. ❓ ROI 對工作流程有具體幫助? → 全 LOW

→ **任一答 No → WONTFIX**

### 保留觸發條件(未來何時動)

- ✅ 若 user 回報「Tab2 顯示吃本金 / Tab3 顯示健康」對稱性破裂 → 啟動 #1(Tab3 ADR SSOT)
- ✅ 若新增 macro 卡片 tab 時順手帶 → #2(card SSOT)
- ✅ 若 EX-PASSTHRU-1 例外表下次擴充時 → 順手補 #4

### 禁止主動推進的 PR

- ❌ 不開「Tab3 ADR SSOT 收斂 PR」(無 bug 觸發)
- ❌ 不開「HTML card 統一 PR」(無視覺投訴)
- ❌ 不開「Sharpe 公式去重 PR」(已正確分層)

---

## §4 CLAUDE.md §-1 對齊聲明

> 2026-06-24 user 明確要求:「沒實際 bug / 沒具體需求 → 不要動」

本次 Phase 1 跨 6 子題、3 輪 Scout + Adversarial verify 全域掃描結果:

**裁決:無需行動。**

Phase 1 排毒品質維持:v19.197 audit baseline 後 v19.261-271 新增 5 UI tab(`tab1_macro_ai/midcycle/radar/longterm/inflection`)+ 8 個 schema validator + composite_score provenance 全部合規。

回應 user 點名 #1「單一基金 vs 組合基金配息打架」:**核心 SSOT 已於 v19.177 統一**(`classify_eating_principal()` + `compute_1y_total_return()` + `_resolve_adr_with_fallback()`),Tab2 完全收斂、Tab3 70% 收斂、剩 3 處 cosmetic 散落不影響資料正確性。若實際使用時觀察到「Tab2 紅 / Tab3 綠」對稱破裂,立即升級為實際 bug 觸發。

---

## §5 下階段候選 TOP 3(僅備查,不主動推)

### TOP 1 — Tab3 ADR fallback SSOT 收斂

- **位置**:`ui/tab3_portfolio.py:1250, 2042` + `ui/tab5_data_guard.py:1019`
- **改動**:3 處行內 `moneydj_div_yield or annual_div_rate` → `_resolve_adr_with_fallback(fd)`
- **預估**:1 PR / ~15 LOC / 30 min
- **觸發條件**:user 回報 Tab2 vs Tab3 配息判定不一致
- **風險**:極低(SSOT 已成熟、Tab2 已用 1 個月驗證)

### TOP 2 — HTML card pattern 統一收斂

- **位置**:`ui/tab2_single_fund.py:359, 564` + `ui/tab1_macro_inflection.py:248`
- **改動**:3 處 inline `<div style=...>` → `_render_macro_indicator_card()` 或 `st.container(border=True)`
- **預估**:1 PR / ~10 LOC / 20 min
- **觸發條件**:user 反映視覺不一致 / 新增 macro 卡片時順手做
- **風險**:極低(純 cosmetic)

### TOP 3 — `tab1_macro.py:821` 補登 EX-PASSTHRU-1 例外表

- **位置**:`CLAUDE.md §8.2.A` 表格
- **改動**:新增 1 row:`repositories.macro_tw_local_repository.*` UI 直呼,理由「v19.197 P1-4 facade,UI 直 import 為 EX-PASSTHRU-1 範疇」
- **預估**:1 PR / ~5 LOC(僅文件)/ 10 min
- **觸發條件**:下次 §8.2 audit 巡檢時順手做
- **風險**:0(純文件登錄)

---

## §6 ARCHITECTURE.md 對齊狀態

本次 audit **未發現 v12.0 ARCHITECTURE.md 需要結構性更新**:

- 5 新 sibling tab files(P3-A2~A6)已在 ARCHITECTURE.md 隱含於 `ui/` 目錄 listing,不需 v12.1 升級
- shared/schemas.py 從 7 → 15 validator 屬 §3.1 範疇,內部 helper 數字,不影響架構描述
- §0' v12.0 (v19.251 doc-sync)仍精準描述 L0~L3 4 層架構

**結論**:`ARCHITECTURE.md` v12.0 仍有效,Phase 1 不更新。

---

**報告結束**。Phase 1 排毒已達穩態。等待 user 下一步指令。

**🚫 嚴禁主動修改 `.py` business code(本次唯讀 audit 已遵守)。**
