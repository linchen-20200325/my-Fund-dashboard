# -*- coding: utf-8 -*-
"""B 線 UI 預覽入口（非正式站）：streamlit run ui_v2/app_preview.py

客戶 2026-10-12 核准新增：把 ui_v2 五頁放進同一個 Streamlit 程式（`st.navigation` ＋ `st.Page`），
供客戶實際操作、驗收 B 線 UI。**本檔不是正式入口**：

- ⛔ 不得被 `app.py`、`ui/**` 或任何正式程式 import（守衛：tests/ui_v2/test_preview_entry.py）。
  它也不 import 任何 `ui_v2/app_*.py`（進入點不是模組，被 import 就會執行整頁）。
- 頁序與頁名照 docs/v2/44_fund_ui_ssot.md 第三節（3.0 五頁總表與 3.1～3.5 的排序）：
  市場總覽 → 持倉體檢 → 標的探索 → 資產配置 → 設定與診斷。

五頁怎麼接（逐字對照各自的入口，守衛同上）：

| 頁 | 模式 | 呼叫方式（與誰逐字等價） |
|---|---|---|
| 市場總覽 | 真資料 | `page.render(load_live=source.load_live)` ＝ `ui_v2/app_mkt_live.py` |
| 持倉體檢 | 真資料 | `page.render(load_live=source.load_live, mask_error=source.mask_error)` ＝ `ui_v2/app_hld_live.py` |
| 標的探索 | **示意資料** | `page.render()` ＝ `ui_v2/app_exp.py`（本頁還沒有真資料版）；頁首另加一條示意資料標示 |
| 資產配置 | 真資料 | `page.render(load_live=source.load_live, save_live=source.save_setting)` ＝ `ui_v2/app_alo_live.py` |
| 設定與診斷 | 真資料 | `page.render(load_live=..., save_live=source.save_setting, refetch_live=source.refetch)` ＝ `ui_v2/app_set_live.py` |

真資料四頁**不退回 fixtures**：本檔不 import 任何 `fixtures`；讀不到資料時由各頁既有的正式模式
錯誤路徑照實顯示（例如「未設定保單試算表 ID（POLICY_SHEET_ID），不讀取」），不補任何數字。

真資料四頁需要的設定（`st.secrets`，Streamlit Cloud 設在該 app 的 Secrets；本機放 `.streamlit/secrets.toml`；
沒有 `st.secrets` 時，`infra.config.get_secret` 退讀同名環境變數）—— 鍵名逐一讀自各頁 `source.py`
經 L2（`services/v2_tables`）到 L1 的實際讀取點：

- `SETTINGS_SHEET_ID`：設定試算表（`repositories/settings_sheet_repository.py`）。持倉體檢、資產配置、
  設定與診斷讀 `user_setting`；設定與診斷另讀 `fetch_log`、`market_indicator`；資產配置讀 `market_indicator`。
  資產配置與設定與診斷的「存檔」、設定與診斷的「重新取數」寫回這一本。沒有預設值，缺值照實顯示未設定。
- `POLICY_SHEET_ID`：保單試算表（`repositories/policy_supplement_repository.py`）。持倉體檢、資產配置讀持倉與保單。
  沒有預設值，不退回其他鍵。
- `google_service_account`：服務帳戶憑證（TOML 表格或 JSON 字串）。上面兩本試算表都只走服務帳戶；
  設定試算表會被寫入（存檔、重新取數），該帳戶要有編輯權；保單試算表本預覽只讀。
- 選填 `PROXY_URL`（或 `[proxy]` 區段）：`infra/proxy.py` 的 NAS 代理。市場總覽（Yahoo）與持倉體檢的淨值
  （MoneyDJ）走 `infra.proxy.fetch_url`；不設就直連，雲端 IP 被擋時該頁照實顯示取數失敗。
- 市場總覽第一階段只取 Yahoo（`^VIX`），不需要金鑰；FRED 三鍵、國發會兩鍵、匯率鍵目前在 L2 是暫停取數
  （`services/v2_tables/market_indicator.py::INDICATOR_SPECS`），畫面寫「資料未備」與原因。

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
  其中資產配置的存檔失敗帳（`ui_v2/alo/page.py::_SAVE_ERRORS_STATE`）會殘留：資產配置存某鍵失敗、
  到設定與診斷把同一鍵存成功、再回資產配置，畫面仍說失敗 —— 與事實相反。
  本檔不改 `page.py`，改在**換頁那一次**把這份帳 pop 掉（`_on_page`）。
  代價：離開資產配置再回來，上一次的存檔失敗提示會消失；但此時欄位本來就會重讀試算表的值，
  失敗那一次沒寫進去的內容也已不在欄位上。
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ui_v2.alo import page as alo_page  # noqa: E402
from ui_v2.alo import source as alo_source  # noqa: E402
from ui_v2.exp import page as exp_page  # noqa: E402
from ui_v2.hld import page as hld_page  # noqa: E402
from ui_v2.hld import source as hld_source  # noqa: E402
from ui_v2.mkt import page as mkt_page  # noqa: E402
from ui_v2.mkt import source as mkt_source  # noqa: E402
from ui_v2.set import page as set_page  # noqa: E402
from ui_v2.set import source as set_source  # noqa: E402

PREVIEW_TITLE = "B 線 UI 預覽（非正式站）"
PREVIEW_NOTE = (
    "B 線 UI 預覽（非正式站）。市場總覽、持倉體檢、資產配置、設定與診斷四頁讀真資料；"
    "標的探索為示意資料。"
    "預覽把五頁放在同一個程式裡跑，快取與取數暫停（冷卻）也五頁共用，"
    "和正式上線時各頁各自獨立運作不同；在設定與診斷按「重新取數」，"
    "會一併影響市場總覽與持倉體檢顯示的資料。"
)
EXP_DEMO_BANNER = (
    "本頁為示意資料，不是真實資料：標的探索尚未接真資料。"
    "頁面上的基金名稱、數字與清單全部是假資料，不得據以判斷；本頁不連任何資料源、不寫入任何資料。"
)

_LAST_PAGE_KEY = "_preview_last_page"


def _on_page(slug: str) -> None:
    """每一頁開頭呼叫一次。偵測到**換頁**時，把資產配置的存檔失敗帳 pop 掉（理由見檔頭）。

    只在換頁那一次動；同一頁內的重跑（按套用、存檔、重新取數）一個 key 都不碰。
    key 名取自 `ui_v2/alo/page.py` 的常數，不在本檔另寫一份字串。
    """
    last = st.session_state.get(_LAST_PAGE_KEY)
    if last is not None and last != slug:
        st.session_state.pop(alo_page._SAVE_ERRORS_STATE, None)
    st.session_state[_LAST_PAGE_KEY] = slug


def page_mkt() -> None:
    _on_page("mkt")
    mkt_page.render(load_live=mkt_source.load_live)


def page_hld() -> None:
    _on_page("hld")
    hld_page.render(load_live=hld_source.load_live, mask_error=hld_source.mask_error)


def page_exp() -> None:
    _on_page("exp")
    # 標示一律畫在本頁最上方、在 `exp_page.render()` 之前：不論 ?scenario= 是哪一種情境都看得到。
    st.warning(EXP_DEMO_BANNER, icon="⚠️")
    exp_page.render()


def page_alo() -> None:
    _on_page("alo")
    alo_page.render(load_live=alo_source.load_live, save_live=alo_source.save_setting)


def page_set() -> None:
    _on_page("set")
    set_page.render(
        load_live=set_source.load_live, save_live=set_source.save_setting, refetch_live=set_source.refetch
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
