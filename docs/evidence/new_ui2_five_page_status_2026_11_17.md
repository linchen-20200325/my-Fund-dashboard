# New UI2 五頁完成度對照（2026-11-17）

> **導航快照，非核准、非完成證明。** 基準 main `0ac6c086`（2026-11-17 `git fetch` 實查）；使用前必須重查 GitHub。
> **單組作者整理，未經獨立 QA**；「無/只有」類全稱句皆標單組未驗。僅 grep／讀檔，未跑 UI、未跑瀏覽器。
> 證據符號：【碼】讀現行程式；【DEC】對照 `docs/DECISIONS.md`；【文】依既有 evidence／BACKLOG（本組未重驗）；【未驗】本組沒查。

## 1　逐頁對照

| 頁 | 已實作 | 僅 FAKE | 已核准未施工 | 資料接線待授權 | Cloud／真機未驗 | 下一個安全切片 |
|---|---|---|---|---|---|---|
| 🌍 市場與趨勢 | 已掛 `ui_v3/shell/registry.py`（`mkt` ＝ `registered=True`）與 `ui_v3/app_preview.py`；Preview-only，**不是**正式入口【碼】；資料走既有 L2→L1 `adapters.market_page.load()`【碼】 | 否（app_preview 明文不得 import fixtures）【碼】 | — | 見 BL-0536／0544 既有 Gate【文】 | 是：正式 Cloud 390／1280、真機、WebView、讀屏仍 NOT VERIFIED（BL-0544 列）【文】 | **候選：BL-0544 唯讀驗收**（取得 Cloud 證據、區分 PASS／NOT VERIFIED／NOT RUN）。**屬總管讀法，待客戶確認**（該項是否落在 BL-0544 授權字面，HANDOFF 已建議先確認） |
| 💼 我的資產 | 無正式頁；`ui_v3/pages/assets.py` renderer、`ui_v3/viewmodels/assets_page.py`、純函式 adapter `ui_v3/adapters/assets_page.py`【碼】 | **是**：隔離 Preview `poc/assets_fixture_preview/`，A00／A10／A20／A50／A60，**十一個 FAKE 情境**（`assets_fake_inputs.py::SCENARIOS`）【碼】；`ast` 仍 `registered=False`（`REASON_WIREFRAME_PENDING`）、未掛 `app_preview`【碼】 | A50（`DEC-2026-11-16-01`）、A60（`DEC-2026-11-17-01`）限 FAKE-only 隔離 Preview【DEC】 | 是：真資料接線、registry 掛載、金額／FX／可用列門檻／A51／T6 均未授權（同 DEC 不授權欄）【DEC】；載入端 adapter `ui_v3/adapters/assets_source.py` 註明「未接任何頁」【碼】 | 是：Preview 僅 fixture／Chromium 層，Cloud／真機未驗【文】 | **可在 FAKE 隔離範圍內補「待確認字樣」修整**（新字樣一律 `PendingWording`）；不掛頁、不接資料 |
| 🔍 找基金 | **僅 S0 純函式** `ui_v3/viewmodels/exp_counts.py`（#1244，非使用者可見）【碼】【文】；無 Shell 頁、無 registry 登錄（`exp` ＝ `registered=False`；poc 離線 FAKE 預覽見下欄）【碼】 | ~~無（沒有 FAKE 預覽頁；見 BL-0553 登記的待裁示題）~~ → 2026-11-17 更正：#1267／#1268 已有 `poc/fund_search_fixture_preview` 離線 FAKE 預覽（未掛 registry／`app_preview`）；掛載見 BL-0554 | 線框基準：`DEC-2026-11-14-04` 只授權線框基準與 S0 純函式【DEC】 | 是：S2 接線被 `DEC-2026-11-14-08` **暫緩**（不授權 S2-T0 施工、不掛 🔍 頁、不接 Sheet）【DEC】 | 不適用（無 Shell 頁） | **目前無「無新 Gate 且非空殼」的切片**（單組判斷）：任何可見頁需新裁示（BL-0553） |
| 🤖 AI 投資總結 | 無 | 無 | **否：無核准線框**（不得標為已核准）【文】 | Phase 7／OneBrain 前不可進【DEC】 | 不適用 | 無（Phase 7 前不可進；`registry.py::PageSlot.__post_init__` 於建構時擋 `ai` 且 `registered=True`，原因必須是 `REASON_PHASE7`）【碼】 |
| ⚙️ 設定 | 無正式頁；`ui_v3/pages/nas_diag.py`、`ui_v3/viewmodels/nas_diag*.py`【碼】 | **是**：`poc/nas_diag_preview/` 離線 FAKE（NAS 中繼站與資料連線診斷）；`set` ＝ `registered=False`【碼】 | 離線 FAKE Preview 依客戶指示授權（BL-0550 列「離線 FAKE Preview 已合併」）【文】 | 是：真實探測、⚙️ 掛載、探測目標／冷卻／授權待 **BL-0550** 裁示【文】 | 是 | **僅 FAKE 層小修**（不掛載、不探測）；掛載與探測等 BL-0550 |

## 2　一句話總覽

- **只有 🌍 真的掛在 registry 與 `app_preview`**（Preview-only）；其餘四頁 `registered` 皆為 False【碼，單組讀 `registry.py::IA_PAGES`】。
- 💼、⚙️ 有隔離 FAKE 預覽（`poc/`），**不是**使用者可見的正式畫面，也不代表資料接線。
- 🔍 目前只有內部純函式；🤖 完全未開始，且程式強制擋。

## 3　NOT VERIFIED

1. 各頁在 Streamlit Cloud／真機的實際表現（無證據）。
2. 「只有 🌍 掛載」為單組（~~「🔍 無 FAKE 預覽頁」~~ 已於 2026-11-17 更正：#1267／#1268 已有 poc 離線 FAKE 預覽，未掛 registry／`app_preview`） grep／讀檔結論，未獨立複驗。
3. 💼 十一情境與 A50／A60 的 UI 正確性本組未開啟瀏覽器驗證；以 main CI 與既有 evidence 為準（未重查）。
4. 「下一個安全切片」欄皆為作者建議，**非授權**；🌍 候選待客戶確認。

## 4　相關

`docs/HANDOFF.md`（§3 五頁現況單行）；`docs/BACKLOG.md` BL-0544／BL-0550／BL-0553；`docs/evidence/new_ui2_five_optimizations_checkpoint_2026_11_15.md`。
