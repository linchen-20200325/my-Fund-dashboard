# 基金 New UI2「🌍 市場與趨勢」G3／G6 施工批證據（2026-11-11；作者自驗）

> **性質**：施工批證據歸檔；**不是**設計 SSOT；不新增 DEC、不改 `docs/DECISIONS.md`／`docs/BACKLOG.md`／`docs/HANDOFF.md`（由總管另行同步）。
>
> **授權來源（要點轉述，非逐字；經總管轉達，客戶可推翻；本批作者未見客戶對話本身，亦未見登記於 `docs/DECISIONS.md` 的條目）**：客戶核准 G3（採候選 **B 色票＋A 尺寸**，見 `docs/evidence/fund_newui2_market_token_and_wireframe_proposal_2026_11_10.md` §A.5）與 G6 限定範圍（首屏摘要＝`card.summary`、Primary 圖＝`card.chart`、Secondary 兩卡頂對齊且不強制等高；不改區塊順序、金融內容、chip 數量、首屏核心數字預算〔frozen 44／≤5〕、不新增 CTA）。範圍僅 `ui_v3` 的 🌍 市場頁與其 Shell。
>
> **標記**：FACT＝本批實測；INFERENCE＝推論，可被推翻；NOT VERIFIED＝本批未驗。**本檔所有結果皆為作者自驗；獨立 QA 由他人另行進行。**
>
> **證據限制**：資料＝`tests/ui_v3/market_stubs.py` 的**合成資料**（人造數值，非市場資料，不連 FRED／Yahoo／任何外部來源）；瀏覽器＝本機 headless Chromium（Playwright；Streamlit 1.59.2）。**不是** Streamlit Cloud、WebView 或真機證據（G7 另批）。股票 HTML 參考側**仍 NOT VERIFIED**，本批沒有採用也沒有核對它的任何色票或數值。

---

## 1. 改了什麼（檔案）

| 檔案 | 內容 |
|---|---|
| `ui_v3/design/tokens.py` | 核准值落地：色票（B）、tone 字／底／邊（B）、spacing／type／radius／card／chip（A）。`Token.value` 不再恆為 None：**只有核准清單內才有值**（`VALUED_NAMES`），其餘（`chart.*`、`state.*`、`cta.*`、`nav.*`，以及只指向別的 token 的 `color.status.*`／`meta.*`）仍 None（`UNVALUED_BY_DESIGN`）。新增 12 個色票 token（`color.page.bg` 等）。`proposed`（80 §5 建議尺度）**原樣保留**；`STATUS_TONES`、`color.status.*` 的 `refers_to` **一字未動**。新增 `value()`：沒有值就 raise，不給預設。 |
| `ui_v3/design/theme.py`（新） | token → CSS 的唯一出口（只用標準函式庫、零 streamlit import）：`card_css`、`tone_css`、`app_css`。CSS 不得另寫色碼。 |
| `ui_v3/shell/nav.py` | `shell_css()` 改由 token 取色與尺寸；注入 `app_css()`（覆寫 Streamlit theme 色，見 §4）。 |
| `ui_v3/pages/mkt.py` | `CSS` 改由 token 組成（含 ≤768 主圖卡內滿版、`card.chart` 標題上內距歸零）；摘要、Primary 圖、兩張 Secondary 卡改放 `st.container(key=…)`；利率卡的子序列單選移進卡內；移除三個 `st.divider()`。 |
| `tests/ui_v3/test_ui_v3_design_tokens.py` | **刻意改**：原「所有 token 值＝None」改為「核准清單逐值寫死、其餘恆 None」；新增「CSS 內沒有 token 表以外的色碼／rgba」「共用 `config.toml` 未被本批改動」。 |
| `tests/ui_v3/test_ui_v3_semantics_rules.py` | **刻意改**：`test_tone_keys_are_names_not_hex` 原本連 `tokens.py` 都要求無色碼（因為值為 None）；色值現在合法住在 token 表，改為「`rules.py` 無色碼；`color.status.*` 仍只有 `refers_to`、沒有值」。 |
| `tests/ui_v3/test_ui_v3_wording_fidelity.py` | 假 streamlit 物件補 `container`（頁現在用它）。其餘不動。 |
| `tests/ui_v3/test_ui_v3_market_page_browser.py`（#1205 的 V4） | 既有判定一律保留；選擇器改為跟新容器對應；新增容器／對齊／token 套用／圖寬≤720／控制項可操作／**首屏露出量不低於改前基線（G5 原「只記錄」改為斷言）**／圖不蓋卡片邊線的正向守衛與 8 組負控（見 §6）。 |
| `tests/ui_v3/test_ui_v3_token_contrast.py`（新） | 核准色票在實際用到的配對上的 WCAG 對比守衛（fast lane）。 |

沒動：`.streamlit/config.toml`、`ui_v2`、正式入口、`services/`、`repositories/`、`shared/`、公式、資料契約、`STATUS_TONES` 與狀態語意、缺資料處理、workflow、`data_cache`。

## 2. Streamlit 可行性（先驗，FACT）

問題：原生單選（檢視／期間／利率子序列）能不能放進自訂卡片容器？

- **作法**：`st.container(key="uv3-card-…")`（Streamlit 給外層 `st-key-uv3-card-…` class），卡片外框由 token CSS 畫；卡內放原生 `st.radio`／`st.expander`／`st.markdown`。**沒有**用 HTML 把原生控制項包起來（做不到；`st.markdown` 的 HTML 不能包住原生 widget）。
- **實測結果（Chromium＋AppTest）**：
  - 滑鼠點選期間／檢視／利率子序列：圖與卡片標題跟著變（`aria-label` 帶期間；利率卡 `h4` 帶子序列）。
  - 鍵盤：焦點在利率單選已選項時按 `ArrowRight`，選到下一項（`政策利率`）。
  - 狀態跨重跑保留（切換檢視後，期間仍是 3M）；widget key（`uv3_mkt_period`／`_view`／`_rates`）**沒有改**，AppTest 以 key 取 radio 的既有測試全數照過。
  - 利率單選的可見標籤「利率與信用」與卡標題重複，改為 `label_visibility="collapsed"`；**無障礙名稱仍是「利率與信用」**（radiogroup 的 `aria-label`，守衛鎖）。這會使畫面少一行重複的可見字（字樣本身沒有改、沒有新增）；列在 §7 差異表。
- **判定**：可行，**不需要**退回「保留控制項位置＋視覺外框」的替代方案。
- **NOT VERIFIED**：螢幕閱讀器實測、Cloud／WebView／真機、其他瀏覽器引擎。

## 3. 量測（前後；同一腳本、同一合成資料、Chromium、視窗高 844／844／800）

「前」＝`origin/main`（`192848b`）；「後」＝本批。數字＝像素，`foldPx`＝主圖在視窗內的露出量。

### 3.1 首屏主圖（客戶規則：露出量不得明顯變差；因內距而下降時優先零額外內距）

「前」＝`origin/main`（`192848b`）；「後」＝本批**最終版**（含跟進 commit）。

| 寬度 | 主圖頂 y（前→後） | 首屏露出 foldPx／圖高（前→後） | 主圖寬×高（前→後） |
|---|---|---|---|
| 390 | 687.4 → 684.2 | 156.6／238.7 → **159.8**／237.3 | 358×238.7 → 356×237.3 |
| 768 | 662.6 → 634.6 | 181.4／480 → **209.4**／480 | 720×480 → 720×480 |
| 1280 | 601.6 → 573.6 | 198.4／480 → **226.4**／480 | 720×480 → 720×480 |

- 三個寬度的露出量都**不低於改前基線**（V4 瀏覽器守衛以「≥ 基線 − 1px」斷言；390 另斷言圖寬 ≥354）。
- **第一版（head `b709abf7`）曾在 390 變差**：露出 147.8px、圖 332×221.3（卡片左右內距縮小圖寬）。跟進處置（依客戶規則「優先零額外內距」，選項 a＋c）：
  (a) ≤768 時主圖在卡內左右滿版（圖本身左右各伸入卡片內距 12px，圖寬＝卡內寬 356；**不蓋過卡片邊線，標題／控制項／文字仍保留 10×12 內距**，守衛鎖「圖不蓋邊線」「卡內標題 x ≥ 卡左緣＋11」）；
  (c) `card.chart` 內標題的上內距歸零（卡片自己的 10px 內距就是上緣留白）。
  卡片本身、邊框、其餘內距、色票**一字未動**，故 §5 對比表不受影響（測試重跑仍綠）。
- 圖寬 356（非改前 358）：差的 2px 是卡片左右邊框；為不蓋過邊線而保留。比例 360:240、最大寬 720 不變。
- 移除三個 `st.divider()` 仍保留（反事實：卡片＋分隔線的組合在 390 只剩 82.8px 露出，不可行）。

### 3.2 Secondary 兩卡頂對齊

| 寬度 | 前：VIX 卡頂／利率卡頂（差） | 後：VIX 卡頂／利率卡頂（差）；高度 |
|---|---|---|
| 768 | 1345.2／1429.2（**84.0**） | 1263.2／1263.2（**0**）；192.1／250.1 |
| 1280 | 1284.2／1368.2（**84.0**） | 1202.2／1202.2（**0**）；192.1／250.1 |
| 390 | 單欄（不適用） | 單欄，依序往下排、不重疊 |

兩卡**不強制等高**（192.1 vs 250.1：利率卡多一組單選）。

### 3.3 其他

- 三寬度整頁／主內容**無橫向溢出**（`docScrollW`＝視窗寬）；圖寬 ≤720；頁首五格（≤768）與側欄（≥769）守衛照過。
- 區塊順序、chip 與核心數字預算（frozen 44／≤5）、缺資料字樣（`⬜`／`◇ 資料未備`，不畫零、不畫空座標軸）、失敗原文不外漏：#1205 既有守衛**全數照過、判定未放寬**。

## 4. 與 `.streamlit/config.toml` 的關係（**偏離說明；需客戶知悉**）

- `.streamlit/config.toml` 在 repo 根目錄，**全 repo 共用**：正式入口（Old UI）與 `ui_v2` 的預覽都讀它。改它會改變正式入口與 `ui_v2` 的外觀，超出本批授權 → **依指示未改**。
- 因此 B 色票只能由 ui_v3 自己的 CSS 覆寫（`design/theme.py::app_css()`，只在 ui_v3 頁面注入）。後果：**config.toml 的舊值（`#f6f8fa`／`#0e1117`／`#1f6feb`／`#1f2328`）與 token 表不一致，但只對 Old UI／`ui_v2` 生效**；ui_v3 頁面上沒有舊色殘留（瀏覽器守衛逐元素掃 computed color／background／border，三寬度皆 0 命中）。
- 覆寫用的是 Streamlit 的 `data-testid` 選擇器（含單選圓點的結構選擇器）。Streamlit 升版若改 DOM，「token 實際套用」守衛會轉紅，不會靜默退回舊色。
- 若客戶之後要讓 config.toml 與 token 一致，需另批（連動正式入口與 `ui_v2`），並同步改 `test_shared_streamlit_config_is_untouched_by_the_g3_batch`。

## 5. WCAG 對比（作者自算；公式與腳本方法見 #1204 §A.2）

兩組各自計算並互相對照：**(a)** 本批另寫的獨立腳本（色值抄自指示、不 import repo；alpha 合成＝逐通道四捨五入）；**(b)** `tests/ui_v3/test_ui_v3_token_contrast.py`（讀 token 表，鎖進 fast lane）。腳本健全性：黑對白＝21.00。兩組同一作者；**不是獨立第二組複算**。

| 配對（前景 on 背景） | 比值 | 門檻 | 結果 |
|---|---|---|---|
| 主文字 `#172033` on 主背景 `#f5f7fb`／卡面 `#ffffff` | 15.17／16.27 | 4.5 | 過 |
| 次要文字 `#4a5670` on 主背景／卡面 | 6.86／7.35 | 4.5 | 過 |
| chip 字 on 底：neutral＝grey／yellow／red | 13.50／7.10／7.67 | 4.5 | 過 |
| chip 邊 on 卡面：neutral＝grey／yellow／red | 3.38／3.64／5.44 | 3 | 過 |
| chip 邊 on 主背景（expander 內）：neutral＝grey／yellow／red | 3.16／3.39／5.07 | 3 | 過 |
| 側欄文字 `#e6edf3` on 側欄底 `#101a33`／secondary `#18254a` | 14.60／12.67 | 4.5 | 過 |
| 側欄次要文字 `#aab6cf` on 側欄底／secondary | 8.46／7.35 | 4.5 | 過 |
| 側欄強調 `#5fd3d0`（目前頁色條）on 側欄底／secondary | 9.62／8.35 | 3 | 過 |
| primary `#1a5fd0`（單選選取圓點）on 卡面／主背景；白內點 on primary | 5.85／5.45；5.85 | 3 | 過 |
| 卡片邊線 `#7f8ca6` on 主背景／卡面（含未選單選圓環、卡內 expander 邊） | 3.16／3.38 | 3 | 過 |
| 手機頁首：主文字 on 卡面；停用項次要文字 on 卡面；底邊線 on 主背景 | 16.27；7.35；3.16 | 4.5；4.5；3 | 過 |
| 圖：刻度文字（opacity .7 合成 `#5d6370`）on 卡面；線與端點標籤 on 卡面 | 6.03；16.27 | 4.5；3 | 過 |
| 側欄邊線 `#34466e` on 側欄底 | 1.85 | 不判 | **裝飾**（分隔線、停用按鈕框；#1204 已揭露，資訊不靠它傳達） |
| 圖座標軸底線（opacity .35 合成）on 卡面 | 2.15 | 不判 | **裝飾**（底線；資訊由刻度文字與資料線傳達） |

- 本表**沒有**未通過的列。**未涵蓋（誠實揭露）**：Streamlit 原生元件自己衍生的色（本批未覆寫）——例如側欄停用「更新資料」按鈕的字（`rgba(230,237,243,.4)` 合成約 3.37：停用控制項，WCAG 免判，且與改前 3.41 相同）、展開圖示、焦點框顏色；這些**未逐一量測**。
- A 組三處低於門檻的問題（A5 primary 文字連結、A16 卡邊線、A17 neutral chip 邊）已由 B 值取代；本批並未發現 primary 被用作文字連結。

## 6. 測試（精確指令與結果在 PR 描述；摘要）

新增或調整的守衛與負控（全部在測試內對頁面注入、不改 production）：

- 正向：卡片容器存在且外框＝token（邊 1px、色、圓角 8、內距 10×12、無陰影）；摘要列／圖／檢視與期間單選／來源 expander 在 `card.chart`／`card.summary` 內；利率單選與卡標題在利率卡內；Secondary 並排時卡頂差 ≤1px 且高度不相等；token 實際套用（主背景、文字、側欄、單選選取點、chip tone）；無舊 theme 色殘留；圖寬 ≤720；三寬度無橫向溢出；單選滑鼠＋鍵盤可操作、狀態保留；降級情境（缺台股／兩條皆缺／S&P 取數失敗）同樣成立。
- 負控：把利率單選移出卡、卡頂錯位 84px、強制等高、圖放寬超過 720、剝掉卡片外框、還原舊 theme 色（背景與單選圓點）、首屏多加間距、主圖寬縮回——每一項都會被對應判定函式抓到。
- token：逐值鎖核准清單；CSS 內無 token 表以外的色碼或 `rgb(a)`；共用 `config.toml` 未被改；WCAG 對比守衛（含負控）。

## 7. 與線框（#1204 Part B）的差異

1. **移除三個 `st.divider()`**（線框沒有畫分隔線；理由見 §3.1）。
2. **利率單選的可見標籤收起**（與卡標題重複；無障礙名稱保留）。
3. 依據卡 MKT-1～3 仍是 HTML 卡（非具名容器），外框值與其他卡**同一組 token**；G6 範圍只點名三處容器，未擴大。
4. ≤768 主圖在卡內左右滿版（伸入內距、不蓋邊線；§3.1），標題上內距歸零。**線框 B.3 的圖寬決策點 A 照推薦**：維持比例與 720 上限，不改圖比例。
5. 其餘（區塊順序、內容、chip 數量、核心數字、CTA）**與線框一致、無改動**。

## 8. 需要客戶決定／知悉

1. ~~**390px 首屏**：主圖露出 157→148px、圖寬 358→332px~~ → **已由總管依客戶既有規則（優先零額外內距）處置，不需客戶決定**：跟進 commit 後 390 露出 159.8px（≥基線 156.6）、圖寬 356（§3.1）。（舊表述保留：它在第一版 head `b709abf7` 為真。）
2. **`config.toml` 與 token 不一致**（§4）：是否要另批統一（會連動正式入口與 `ui_v2` 的外觀）？
3. **12px 小字**：Status Bar、頁尾、手機頁首標籤、側欄 CTA 備註、「開發中」標籤仍是 12px，**低於**已核准的 `type.caption`＝13px（現況沿用、本批未動）。是否一併調整？
4. **`grey` 與 `neutral` 共用同一組值**（#1204 §A.6 第 5 點）：是否需要視覺區分？

## 9. 未驗項（NOT VERIFIED）

- Streamlit Cloud／WebView／真機、其他瀏覽器引擎、螢幕閱讀器、真實資料（本批全為合成資料）。
- 對比：Streamlit 原生衍生色未逐一量測（§5）；非獨立第二組複算。
- 股票 HTML 參考側：**NOT VERIFIED**；本批未採用其色票。
- 獨立 QA 未做（作者自驗）。
- 本批**沒有**保存「改後」截圖檔入庫（避免增大 repo；量測腳本的數字即證據）；需要時可另產。
