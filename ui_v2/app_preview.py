# -*- coding: utf-8 -*-
"""B 線 UI 預覽入口（非正式站）：streamlit run ui_v2/app_preview.py

客戶 2026-10-12 核准新增：把 ui_v2 五頁放進同一個 Streamlit 程式（`st.navigation` ＋ `st.Page`），
供客戶實際操作、驗收 B 線 UI。**本檔不是正式入口**：

- ⛔ 不得被 `app.py`、`ui/**` 或任何正式程式 import（守衛：tests/ui_v2/test_preview_entry.py）。
  它也不 import 任何 `ui_v2/app_*.py`（進入點不是模組，被 import 就會執行整頁）。
- 頁序與頁名照 docs/v2/44_fund_ui_ssot.md 第三節（3.0 五頁總表與 3.1～3.5 的排序）：
  市場總覽 → 持倉體檢 → 標的探索 → 資產配置 → 設定與診斷。

五頁怎麼接（與各自的入口傳同名參數、同一物件；守衛同上）：

| 頁 | 模式 | 呼叫方式（與哪個入口同名參數、同一物件） |
|---|---|---|
| 市場總覽 | 真資料 | `page.render(load_live=source.load_live, save_live=source.save_setting)` ＝ `ui_v2/app_mkt_live.py`（2026-10-13 起接上存檔） |
| 持倉體檢 | 真資料 | `page.render(load_live=source.load_live, mask_error=source.mask_error, save_live=source.save_setting)` ＝ `ui_v2/app_hld_live.py`（2026-10-16 起接上存檔） |
| ~~標的探索~~ | ~~**示意資料**~~ | ~~`page.render()` ＝ `ui_v2/app_exp.py`（本頁還沒有真資料版）；頁首另加一條示意資料標示~~ |
| 標的探索 | 真資料（第一批） | `page.render(load_live=source.load_live, save_live=source.save_setting)` ＝ `ui_v2/app_exp_live.py`（2026-10-13 起；狀態更新，不是漏刪 —— 上一列在寫下當時為真）。母體＝選股池的基金代碼，~~其餘欄「⬜ 資料未備」~~（2026-10-15 狀態更新，不是漏刪：#966 起基本資料接 `exp_profile`、淨值與配息接 `exp_nav`）；不再加示意資料標示（正式資料不加示意，比照 hld 2026-10-02 前例） |
| 資產配置 | 真資料 | `page.render(load_live=source.load_live, save_live=source.save_setting, mask_error=source.mask_error)` ＝ `ui_v2/app_alo_live.py`（2026-10-16 起另傳遮蔽函式） |
| 設定與診斷 | 真資料 | `page.render(load_live=..., save_live=source.save_setting, refetch_live=source.refetch)` ＝ `ui_v2/app_set_live.py` |

2026-10-17 Phase 3 P0-②：市場總覽、持倉體檢、標的探索、資產配置四頁**另多傳一個** `settings_page=_settings_page()`
（設定與診斷那一頁的 `st.Page`，給頁首資料狀態行旁的「前往設定與診斷」；只換頁）。單頁的 live 入口沒有
`st.navigation`、換不了頁，不傳這一個；其餘參數照舊與 live 入口同名、同一物件（守衛同上，只容許多這一個）。

2026-10-17 Phase 3 P1-⑤（BL-0362）：市場總覽、標的探索、設定與診斷三頁**與各自的 live 入口一起**多傳
`mask_error=source.mask_error`（整頁載入失敗時，原文經遮蔽才收進進階診斷）；上表三列的呼叫方式在寫下當時為真，
現行以本段為準（狀態更新，不是漏刪）。持倉體檢、資產配置早已傳。

~~真資料四頁~~ 真資料五頁（2026-10-13 起標的探索也接上；狀態更新，不是漏刪）**不退回 fixtures**：本檔不 import 任何 `fixtures`；讀不到資料時由各頁既有的正式模式
錯誤路徑照實顯示（例如「未設定保單試算表 ID（POLICY_SHEET_ID），不讀取」），不補任何數字。

真資料四頁需要的設定（`st.secrets`，Streamlit Cloud 設在該 app 的 Secrets；本機放 `.streamlit/secrets.toml`；
沒有 `st.secrets` 時，`infra.config.get_secret` 退讀同名環境變數）—— 鍵名逐一讀自各頁 `source.py`
經 L2（`services/v2_tables`）到 L1 的實際讀取點：

- `SETTINGS_SHEET_ID`：設定試算表（`repositories/settings_sheet_repository.py`）。持倉體檢、資產配置、
  設定與診斷讀 `user_setting`；設定與診斷另讀 `fetch_log`、`market_indicator`；資產配置讀 `market_indicator`。
  ~~資產配置與設定與診斷的「存檔」、設定與診斷的「重新取數」寫回這一本。~~
  → 2026-10-16 更正（狀態更新，不是漏刪；上句寫於 2026-10-12，當時為真）：市場總覽、標的探索、資產配置、
  設定與診斷的「存檔」與設定與診斷的「重新取數」寫回這一本（市場總覽與標的探索 2026-10-13 起接上存檔，
  見本檔上方五頁表與 `ui_v2/mkt/page.py::render`、`ui_v2/exp/page.py::render` 的 `save_live` 說明）。
  沒有預設值，缺值照實顯示未設定。
- `POLICY_SHEET_ID`：保單試算表（`repositories/policy_supplement_repository.py`）。持倉體檢、資產配置讀持倉與保單。
  沒有預設值，不退回其他鍵。
- `POOL_SHEET_ID`（選填）：選股池試算表（`repositories/pool_repository.py`；不設則用該檔內建的預設那一本）。
  標的探索的母體（2026-10-13 起）只讀這一本 `_fund_pool` 分頁的**代碼欄**；**沒有服務帳戶時不讀本機暫存檔**，
  畫面照實寫「選股池未設定雲端來源」。
- `google_service_account`：服務帳戶憑證（TOML 表格或 JSON 字串）。上面兩本試算表都只走服務帳戶；
  設定試算表會被寫入（存檔、重新取數），該帳戶要有編輯權；保單試算表本預覽只讀。
- 選填 `PROXY_URL`（或 `[proxy]` 區段）：`infra/proxy.py` 的 NAS 代理。市場總覽（Yahoo）與持倉體檢的淨值
  （MoneyDJ）走 `infra.proxy.fetch_url`；不設就直連，雲端 IP 被擋時該頁照實顯示取數失敗。
- ~~市場總覽第一階段只取 Yahoo（`^VIX`），不需要金鑰；FRED 三鍵、國發會兩鍵、匯率鍵目前在 L2 是暫停取數
  （`services/v2_tables/market_indicator.py::INDICATOR_SPECS`），畫面寫「資料未備」與原因。~~
  → **2026-10-13 狀態更新（不是漏刪；上句在寫下當時為真）**：市場總覽取 Yahoo（`^VIX`）與 FRED 三鍵
  （高收益信用利差、期限利差、聯邦基金利率），**FRED 需要 secret `FRED_API_KEY`**；沒設時那三鍵照實顯示
  「取數失敗：未設定 FRED_API_KEY」。國發會兩鍵、匯率鍵仍在 L2 暫停取數
  （`services/v2_tables/market_indicator.py::INDICATOR_SPECS`），畫面寫「資料未備」與原因。
  設定與診斷的「重新取數」另清 FRED 那一支 L1 快取（`fetch_fred_vintages`）。

⚠️ 同一個程式跑五頁的兩個連帶（docs/v2/49_data_integration_plan.md 4.8）：
- L1 的快取與來源冷卻狀態住在行程記憶體裡，五頁在同一個行程內**共用**：一頁讓某來源進了冷卻，
  另一頁也照樣被擋；設定與診斷的「重新取數」清的 L1 快取（Yahoo 的 `fetch_yf_close`、淨值的
  `fetch_nav` 整批，見 `services/v2_tables/settings_store.py`）也就是市場總覽、持倉體檢在用的那幾支。
- 五頁共用同一份 `st.session_state`，但**輸入欄（widget）的狀態一頁一份**：streamlit 1.59.2 的
  `streamlit/elements/lib/utils.py::compute_and_register_element_id` 把目前頁的 script hash
  （`st.Page` 為 `calc_hash(url_path)`）算進 widget id，即使有指定 key 也一樣；離開一頁時，
  那一頁的 widget 狀態就被清掉。所以資產配置與設定與診斷正式模式同名的 `live_alo_*` 輸入欄
  不會互相帶值（回歸測試：tests/ui_v2/test_preview_page.py）。⚠️ 這個結論的依據是
  streamlit 1.59.2 的 widget id 算法；升版改了算法時，那條回歸測試會先紅。
  **會跨頁共用的只有各頁程式自己寫進 `st.session_state` 的 key**（不是輸入欄的那些）。
  其中~~兩份~~三份（2026-10-13 起；狀態更新，不是漏刪）會讓畫面與事實或與自己相反，本檔不改 `page.py`，改在**換頁那一次** pop 掉
  （`_on_page` ＋ `_PAGE_STATE_TO_DROP`）：
  1. 資產配置的存檔失敗帳（`ui_v2/alo/page.py::_SAVE_ERRORS_STATE`）：資產配置存某鍵失敗、
     到設定與診斷把同一鍵存成功、再回資產配置，畫面仍說失敗 —— 與事實相反。
     代價：離開資產配置再回來，上一次的存檔失敗提示會消失；但此時欄位本來就會重讀試算表的值，
     失敗那一次沒寫進去的內容也已不在欄位上。
  2. 市場總覽「套用」的值（`"_mkt_applied"`；`ui_v2/mkt/page.py` 沒有常數，只能寫字面值，
     守衛在 tests/ui_v2/test_preview_entry.py 讀該檔比對）：套用 30 日後換頁再回來，輸入欄已變回空白、
     MKT-4 寫尚未設定，三張核心卡卻仍用看不見的 30 日窗計算 —— 畫面自相矛盾。
     代價：離開市場總覽再回來，要重新按一次「套用」（與新開這一頁相同）。
     → 2026-10-13 狀態更新（不是漏刪）：客戶裁示「未儲存的暫存設定不得影響正式結果」後，
     正式模式的「套用」停用、三張核心卡只讀已存設定，`"_mkt_applied"` 在本預覽已不進任何計算；
     這一格照留（無害），上面那段描述的是當時的現象。
  3. 市場總覽「存檔」那一次的逐鍵結果（`ui_v2/mkt/page.py::_SAVE_RESULTS_STATE`，2026-10-13 起）：
     理由同第 1 項 —— 別頁把同一鍵存成功後回來，不能仍說失敗。
  4. 標的探索「存檔」那一次的逐鍵結果（`ui_v2/exp/page.py::_SAVE_RESULTS_STATE`，2026-10-13 起）：理由同第 3 項。
  5. 標的探索條件列的當下內容（`ui_v2/exp/page.py::_RULES_STATE`，2026-10-13 起）：條件列的輸入欄離開這一頁就被清掉
     （上面那條 widget id 規則），但這一份是頁面程式自己存的；不清的話，在設定與診斷改了 `exp_filter_rules` 再回來，
     條件列仍是舊的暫存內容。代價：離開標的探索再回來，沒存檔的條件列會回到已存值（未存的本來就不生效）。
  6. 標的探索「本 session 用哪一版已存值填過輸入欄」的指紋（`ui_v2/exp/page.py::_SEEDED_STATE`，2026-10-13 稽核 L 回修）：
     輸入欄離開這一頁就被清掉，指紋若留著，回來時不會重填，空白的勾選框按存檔就蓋掉雲端；清掉指紋就一定重填。
  7. 資產配置「寫入失敗那個鍵的輸入欄暫存」（`ui_v2/alo/page.py::_PENDING_INPUTS_STATE`，2026-10-16 客戶裁示方案 B）：
     存檔失敗後恰逢讀取冷卻、輸入欄沒畫出來時，靠它在輸入欄重新出現時帶回打的字。換頁回來時輸入欄一定是新建的
     （上面那條 widget id 規則），不清的話，離開本頁前沒存成功的字會被帶回，與第 1 項的失敗帳一起清掉才一致
     （第 1 項清掉後失敗行已不在，帶回的字就看不出是沒存進去的內容）。另本組 2026-10-16 實測：從設定與診斷
     換回來的第一輪，`live_alo_*` 這些鍵在 session 裡讀到的是設定與診斷那一頁同名欄的值，不清的話暫存會被它刷掉。
     代價同第 1 項：離開資產配置再回來，沒存成功的內容不再帶回，欄位改顯示試算表上的值。
  8. 持倉體檢「存檔」那一次的逐鍵結果（`ui_v2/hld/page.py::_SAVE_RESULTS_STATE`，2026-10-16 起）：理由同第 3 項。
  ⚠️ 其他頁程式自己寫的 key（例如持倉體檢的套用值）未逐一處理，見交付報告的登記。
  → 2026-10-15（Phase 2 批 1）持倉體檢的套用值（`ui_v2/hld/page.py::_APPLIED_KEY`）已重現查過：換頁回來時欄位還沒畫過，
    `ui_v2/hld/logic.py::_build_page_model` 以已套用的區間回填欄位，輸入欄與計算一致，**不加進換頁清單**
    （守衛：tests/ui_v2/test_preview_page.py 的「套用後換頁再回來」那一條）。其餘頁程式自己寫的 key 仍未逐一查。
  → 2026-10-16（客戶裁示第 2 點）：持倉體檢正式模式「套用」停用、計算只讀已存設定，套用值在本預覽已不進任何計算
    （同上面第 2 項市場總覽的情形）；上一段描述的是當時的現象。
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ui_v2.alo import page as alo_page  # noqa: E402
from ui_v2.alo import source as alo_source  # noqa: E402
from ui_v2.exp import page as exp_page  # noqa: E402
from ui_v2.exp import source as exp_source  # noqa: E402
from ui_v2.hld import page as hld_page  # noqa: E402
from ui_v2.hld import source as hld_source  # noqa: E402
from ui_v2.mkt import page as mkt_page  # noqa: E402
from ui_v2.mkt import source as mkt_source  # noqa: E402
from ui_v2.set import page as set_page  # noqa: E402
from ui_v2.set import source as set_source  # noqa: E402

PREVIEW_TITLE = "B 線 UI 預覽（非正式站）"
# ~~"B 線 UI 預覽（非正式站）。市場總覽、持倉體檢、資產配置、設定與診斷四頁讀真資料，"~~
# ~~"讀不到資料時照實顯示缺失；標的探索為示意資料。"~~
# → 2026-10-13 狀態更新（不是漏刪；客戶裁示 B 線標的探索正式模式第一批）：標的探索改讀真資料（選股池代碼），
#   其餘欄尚未接入、照實顯示「⬜ 資料未備」。舊兩句在寫下當時為真。
# ~~"…照實顯示缺失；標的探索目前只接上選股池的基金代碼，其餘欄位顯示資料未備。"~~
# → 2026-10-15 狀態更新（不是漏刪；Phase 2 批 1）：#966（merge `dbb629c`）起標的探索的基本資料接 L2 `exp_profile`、
#   淨值與配息接 L2 `exp_nav`（`ui_v2/exp/source.py::_load_funds`），那一句已與實況不符。只刪該子句、不新增文案
#   （新增字句屬 UI 文案變更，要客戶草稿）；刪後前一句的分號改由原句尾的句號收尾。在寫下當時為真。
PREVIEW_NOTE = (
    "B 線 UI 預覽（非正式站）。五頁皆讀真資料，讀不到資料時照實顯示缺失。"
    "預覽把五頁放在同一個程式裡跑，快取與取數暫停（冷卻）也五頁共用，"
    "和各頁單獨啟動時不同；在設定與診斷按「重新取數」，"
    "會一併影響市場總覽與持倉體檢顯示的資料。"
)
# ~~EXP_DEMO_BANNER = ("本頁為示意資料，不是真實資料：標的探索尚未接真資料。"~~
# ~~    "頁面上的基金名稱、數字與清單全部是假資料，不得據以判斷；本頁不連任何資料源、不寫入任何資料。")~~
# → 2026-10-13 撤下（狀態更新，不是漏刪）：標的探索接上正式模式（`page.render(load_live=..., save_live=...)`），
#   畫面上已無假資料；正式資料不加示意標示（比照 hld 2026-10-02、mkt／alo 的接法）。那一段在寫下當時為真。

_LAST_PAGE_KEY = "_preview_last_page"

# 換頁那一次要 pop 的、各頁程式自己寫進 session 的狀態（理由見檔頭）。
_PAGE_STATE_TO_DROP = (
    alo_page._SAVE_ERRORS_STATE,   # 資產配置的存檔失敗帳（取 page 的常數，不另寫字串）
    "_mkt_applied",                # 市場總覽「套用」的值（mkt/page.py 沒有常數；守衛讀該檔比對字面值）
    # 2026-10-13：市場總覽存檔接上 user_setting（客戶裁示）後多一份「按存檔那一次的逐鍵結果」，
    # 與資產配置的存檔失敗帳同一個理由（別頁存成功後回來仍說失敗 —— 與事實相反），換頁一併清。
    mkt_page._SAVE_RESULTS_STATE,
    # 2026-10-13：標的探索接上正式模式（客戶裁示）後的兩份，理由見檔頭第 4、5 項。
    exp_page._SAVE_RESULTS_STATE,
    exp_page._RULES_STATE,
    # 2026-10-13 稽核 L 回修：已存值指紋一併清 —— 不清的話回到本頁時指紋沒變、不重填，
    # 而條件列與勾選框已被清掉，按存檔會把空值蓋回雲端（理由見檔頭第 6 項）。
    exp_page._SEEDED_STATE,
    # 2026-10-16（客戶裁示方案 B）：資產配置寫入失敗那個鍵的輸入欄暫存，換頁一併清（理由見檔頭第 7 項）。
    alo_page._PENDING_INPUTS_STATE,
    # 2026-10-16：持倉體檢存檔接上 user_setting（客戶裁示第 2 點）後的「按存檔那一次的逐鍵結果」，理由同市場總覽（檔頭第 8 項）。
    hld_page._SAVE_RESULTS_STATE,
)


def _on_page(slug: str) -> None:
    """每一頁開頭呼叫一次。偵測到**換頁**時，pop 掉 `_PAGE_STATE_TO_DROP`（理由見檔頭）。

    只在換頁那一次動；同一頁內的重跑（按套用、存檔、重新取數）一個 key 都不碰。
    """
    last = st.session_state.get(_LAST_PAGE_KEY)
    if last is not None and last != slug:
        for key in _PAGE_STATE_TO_DROP:
            st.session_state.pop(key, None)
    st.session_state[_LAST_PAGE_KEY] = slug


def _settings_page():
    """設定與診斷那一頁的 `st.Page`（Phase 3 P0-②：四頁資料狀態行旁那一枚「前往設定與診斷」）。

    與 `main()` 註冊進 `st.navigation` 的是同一個函式、同一個 url_path、同一個頁名（取自 `PAGES`，不另寫字面）；
    streamlit 1.59.2 以 url_path 算頁的雜湊，`st.page_link` 驗它是不是已註冊的那一頁
    （`streamlit/navigation/page.py::_validate_registered_page`）。只用來換頁：不讀不寫任何資料、不觸發取數。
    """
    slug, title, func = next(row for row in PAGES if row[0] == "set")
    return st.Page(func, title=title, url_path=slug)


def page_mkt() -> None:
    _on_page("mkt")
    mkt_page.render(
        load_live=mkt_source.load_live, save_live=mkt_source.save_setting, mask_error=mkt_source.mask_error,
        settings_page=_settings_page(),
    )


def page_hld() -> None:
    _on_page("hld")
    hld_page.render(
        load_live=hld_source.load_live, mask_error=hld_source.mask_error, save_live=hld_source.save_setting,
        settings_page=_settings_page(),
    )


def page_exp() -> None:
    _on_page("exp")
    # ~~st.warning(EXP_DEMO_BANNER, icon="⚠️")~~
    # ~~exp_page.render()~~
    # → 2026-10-13（狀態更新，不是漏刪）：與 `ui_v2/app_exp_live.py` 同名參數、同一物件（守衛同上）。
    exp_page.render(
        load_live=exp_source.load_live, save_live=exp_source.save_setting, mask_error=exp_source.mask_error,
        settings_page=_settings_page(),
    )


def page_alo() -> None:
    _on_page("alo")
    alo_page.render(
        load_live=alo_source.load_live, save_live=alo_source.save_setting, mask_error=alo_source.mask_error,
        settings_page=_settings_page(),
    )


def _page_links() -> dict:
    """四頁的 `st.Page`（BL-0250 批次 3-B：設定與診斷「各頁資料狀態總表」每列的「前往該頁」；只換頁）。
    與 `main()` 註冊進 `st.navigation` 的是同一個函式、同一個 url_path、同一個頁名（同 `_settings_page`）。"""
    return {slug: st.Page(func, title=title, url_path=slug) for slug, title, func in PAGES if slug != "set"}


def page_set() -> None:
    _on_page("set")
    set_page.render(
        load_live=set_source.load_live, save_live=set_source.save_setting, refetch_live=set_source.refetch,
        mask_error=set_source.mask_error, pages=_page_links(),
        # 2026-10-26 批 3b-2：Google 個人登入卡，與 `ui_v2/app_set_live.py` 同名參數、同一物件（守衛同上）。
        # ⚠️ 多頁預覽只有在 Google 導回的網址落在設定頁（`/set`）時才會處理 OAuth callback；導回落在別頁
        # （例如預設首頁）時，那一頁不處理 code／state，登入不會完成。部署的 redirect_uri 要指向設定頁網址。
        login_live=set_source.login_live,
    )


# (url_path, 頁名, 函式)。頁名逐字取自 docs/v2/44_fund_ui_ssot.md 3.0 五頁總表。
PAGES = (
    ("mkt", "市場總覽", page_mkt),
    ("hld", "持倉體檢", page_hld),
    ("exp", "標的探索", page_exp),
    ("alo", "資產配置", page_alo),
    ("set", "設定與診斷", page_set),
)


def main() -> None:
    st.set_page_config(page_title=PREVIEW_TITLE, layout="wide")
    st.sidebar.info(PREVIEW_NOTE)
    navigation = st.navigation(
        [
            st.Page(func, title=title, url_path=slug, default=index == 0)
            for index, (slug, title, func) in enumerate(PAGES)
        ]
    )
    navigation.run()


if __name__ == "__main__":
    main()
