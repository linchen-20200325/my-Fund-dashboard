"""ui/tab3_portfolio.py — 組合基金 Tab（v18.128 B-C.6 最終）

從 app.py 抽出 Tab3（組合基金管理，含 T5/T6/T7 子區）的渲染邏輯 — B-C 系列最後一個。

Tab3 是 6 個 tab 中**最大**（3897 行 body），原 app.py 內有兩個 `with tab3:`
block 累積在同一 tab slot（block 1: 戰情室+組合管理，block 2: T5/T6/T7 持股
矩陣+講義+帳本）。本檔將兩 block 合併為**單一 render 函式**，行為等價。

設計：
- render_portfolio_tab() -> None **零閉包依賴**（與其他 5 個 tab 同設計）
- GEMINI_KEY 從 env / _calc_data_health, _friendly_error, _is_core_fund 從
  ui.helpers.session / 其餘 session_state 鍵透過 st.session_state 取
- T7 ledger 相關 Ledger/Switch class 維持原邏輯：函式內部 lazy import 自
  services.ledger_service（避免本檔頂部一次 import 太多）

對外 API:
- render_portfolio_tab() -> None
"""
from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.helpers.render_state import not_ready, system_error

from shared.converters import safe_num  # v19.399 §1:缺值保留 None,不 `or 0` 捏造
from shared.colors import BG_DARK_GREEN_3, BG_DARK_NAVY_1, BG_DARK_NAVY_2, BG_DARK_NAVY_3, BG_DARK_RED_3, CAUTION_YELLOW, CHIP_BG_NEAR_BLACK, GH_BG_CARD, GH_BG_HOVER, GH_BG_PRIMARY, GH_BORDER, GH_FG_PRIMARY, GRAY_55, GRAY_66, GRAY_AA, GRAY_CC, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, MD_BLUE_300, MD_GREEN_A200, MD_GREEN_A400, MD_ORANGE_300, STREAMLIT_BG, TRAFFIC_NEUTRAL, WARN_AMBER, WHITE

from infra.oauth import (
    OAuthError,
    build_authorize_url,
    build_credentials_from_tokens,
    ensure_fresh_tokens,
)
from ui.helpers.metric_explainers import render_metric_explainer
from ui.helpers.tw_time import tw_now_str
from services.moneydj_fetcher import auto_fetch_moneydj  # F-H6 v19.79: §8.2 L3→L2
from repositories.ledger_repository import (
    load_all_ledgers,
)
from repositories.policy_repository import (
    PolicySheetError,
    create_dashboard_sheet,
    delete_policy_row,
    detect_sheet_schema_version,
    get_gspread_client,
    get_gspread_client_from_oauth,
    get_sheet_title,
    list_policy_worksheets,
    list_user_folders,
    list_user_sheets,
    load_all_policies_v2,
    upsert_fund_in_policy,
    upsert_policy_row,
)
from repositories.snapshot_repository import (
    get_state_metadata,
)
from services.format_helpers import fmt_twd
from services.policy_advisor_service import (
    VIX_PANIC_THRESHOLD as _ADVISOR_VIX_PANIC,  # 缺值提示要講出門檻,不另寫一份
    advise_fund,
    recommend_policy,
)
from services.portfolio_service import (
    calc_correlation_matrix,
    dividend_safety as div_safety_check,
)
from ui.components.mk_dashboard import render_mk_war_room
from ui.helpers.session import (
    calc_data_health as _calc_data_health_pure,
    friendly_error as _friendly_error,
    is_core_fund as _is_core_fund,
)
from ui.tab3_t7_ledger import T7InputAbort, render_t7_section

# 稽核 J1-b：FX 曝險摘要用的「幣別不明」桶。刻意**不是**任何 ISO 3 碼，
# 這樣它永遠不會被誤當成真幣別去查匯率或算佔比（§1 不以捏造值充數）。
_UNKNOWN_CCY = "（未知）"

# 其他 fund_fetcher utility


def _calc_data_health(indicators=None):
    ind = indicators if indicators is not None else st.session_state.get("indicators", {})
    return _calc_data_health_pure(ind)


# ── advise_fund 的 VIX 入參：單一取數點（原則 2 去重 + §1 缺值不捏造）──────────
# 本頁一次 render 最多印一次「VIX 未載入」說明,用 session flag 去重;
# render_portfolio_tab() 每次 script run 只被呼叫一次 → 在其開頭重置即可。
_VIX_NOTE_FLAG = "_t3_vix_advice_note_shown"


def _vix_for_advice(*, note: bool = True) -> float | None:
    """取當前 VIX 餵給 `services.policy_advisor_service.advise_fund`。

    **來源**：`st.session_state["indicators"]["VIX"]["value"]` —— 由市場定調分頁
    「📡 載入總經資料」寫入的同一份 dict（唯一 writer 在 `ui/tab1_macro.py`），
    值由 `services/macro/us_indicators.py` 產生。

    **單位**：VIX 指數點（非百分比、非小數），與 `advise_fund` 內部
    「VIX 進入恐慌區」的比較基準同尺度 —— 兩邊都是原始指數值，無需換算。
    門檻數值本身**不在本檔寫死**：從 advisor 匯出的具名常數讀（該常數再往上
    收 `shared/macro_buckets` 的全站 panic 線），提示文字才不會與規則漂移。

    **缺值處置（§1）**：跨 Tab 依賴 —— 使用者若本 session 沒開過市場定調分頁，
    `indicators` 根本不存在。此時回 `None`，`advise_fund` 對 `vix=None` 自有
    降級分支（吃 VIX 的那條規則不成立，改走其餘規則）。**禁止**用「常見值」
    或上次的值頂替：那會讓一條沒有依據的加碼建議看起來像有依據。
    `note=True` 時額外印一行說明，讓使用者知道少了哪一條判斷、以及怎麼補。
    ⚠️ 指路文案裡的分頁名走 `story_nav.tab_label` SSOT，**不得**寫死「Tab①」——
    頁內編號已於 WP-D 全數取消（線框 §04），寫死站號會變成第二個真相源。
    """
    from ui.helpers.story_nav import (  # noqa: PLC0415 — 分頁名 SSOT，見 docstring
        tab_label as _tab_label_vix,
    )
    _raw = ((st.session_state.get("indicators") or {}).get("VIX") or {}).get("value")
    _msg = ""
    if _raw is None:
        _msg = (
            f"⬜ 尚未載入 VIX —— 「σ 深跌 **且** VIX ≥ {_ADVISOR_VIX_PANIC:.0f}"
            "（恐慌區）→ 分批加碼」這條規則"
            "本次不參與下方建議的判斷（其餘規則照常）。"
            f"想補上：先到「{_tab_label_vix('macro')}」按「📡 載入總經資料」，再回本頁。"
        )
    else:
        try:
            return float(_raw)
        except (TypeError, ValueError) as _e_vix:
            # §1：解析失敗要留痕，不可靜默當成「沒有 VIX」
            print(f"[tab3 advise VIX] indicators['VIX']['value']={_raw!r} 無法轉 float："
                  f"[{type(_e_vix).__name__}] {_e_vix}")
            _msg = (
                f"⬜ VIX 值無法解析（{_raw!r}）—— 恐慌加碼那條規則本次不參與判斷。"
            )
    if note and not st.session_state.get(_VIX_NOTE_FLAG):
        st.session_state[_VIX_NOTE_FLAG] = True
        st.caption(_msg)
    return None


def render_portfolio_tab() -> None:
    """渲染組合基金 Tab — 含 戰情室 + 加入基金 + T5/T6/T7 子區。

    Tab3 為 6 tab 最大塊（原 3897 行）；本函式合併 app.py 內兩個 with tab3: block。
    Caller 不需傳參數。
    """
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
    # 每次 script run 重置「VIX 未載入」提示的去重旗標（本函式一次 run 只被呼叫一次）
    st.session_state[_VIX_NOTE_FLAG] = False

    # v18.140: 全部 helper 改正規 import — 徹底脫離 v18.129 sys.modules['__main__'] hack
    # v18.148: 先呼叫 refresh_oauth_state() 把 module-level snapshot 更新到 fresh，
    #          再 local 重 import _oauth_configured / _oauth_cfg；
    #          否則 wizard 寫 session_state 後 rerun，本檔仍拿 import 時的 False snapshot。
    from ui.helpers.oauth_state import refresh_oauth_state as _refresh_oauth_state
    _refresh_oauth_state()
    from ui.helpers.oauth_state import (
        _oauth_configured,
        _resolve_oauth_cfg,
        _get_oauth_client,
        _gsa_secret,
        _sheet_id_secret,
        get_login_state as _get_login_state,  # v19.296: 快捷登入按鈕
    )
    from ui.helpers.holdings import _zh_holding

    # ── v19.302: 政策 Sheet client 決策 SSOT — 優先 Service Account ──────────
    # 背景:app 內 user Google OAuth 在 Streamlit Cloud 上會跟平台自身登入相撞
    #   (OAuth 導回 *.streamlit.app 被平台攔截 → 「You do not have access / does
    #    not exist」帳號錯亂),redirect_uri / login_hint 都救不了。Service Account
    #   為 headless 存取、完全不需使用者登入 → 徹底避開帳號衝突。
    # 規則:只要 `google_service_account` secret 有設就優先用它;沒設才退回既有
    #   user OAuth(Drive 瀏覽等功能仍需 OAuth)。
    # 重要:本 helper 只換「用哪顆 client」,不動 schema —— v1/v2 仍由各呼叫點的
    #   `oauth_mode=bool(_oauth_configured)` 決定,SA client 照樣能讀 v2 sheet
    #   (前提:該 Sheet 已分享給 SA 的 client_email)。
    def _t3_sheet_client():
        # v19.431 存取回退(2026-08-11 線上事故 + 三 AI 對抗查證):#619 修好 SA secret 後,
        # SA client 能建起來 → SA-first 生效,但使用者「自己 OAuth 擁有」的 sheet **未分享給 SA
        # client_email** → open_by_key 得 403 → gspread `raise PermissionError`(無參數)→ 空白紅框。
        # 修:SA 一律先建先試(不違反 SA-first 不變量);若開不了「這張」sheet(403/404,**非 429**)
        # 且使用者已 OAuth 登入 → 回退 user OAuth client(本人擁有該 sheet)。OAuth client 用 session
        # token、無 redirect → 不重現 v19.302 平台登入衝突;純 SA(未登入)使用者 _get_oauth_client()
        # 回 None → 仍走 SA(配合 describe_sheet_exc 的可行動 403 訊息)。探測結果本 session 快取,省配額。
        if _gsa_secret:
            _sa = get_gspread_client(_gsa_secret)
            _sid = (st.session_state.get("policy_sheet_id") or _sheet_id_secret or "").strip()
            if not _sid:
                return _sa                           # 無 sheet 可探測 → 維持 SA
            _cache = st.session_state.setdefault("_t3_sa_can_open", {})
            if _sid not in _cache:                   # 尚未判定 → 探測一次(結果快取,省配額)
                try:
                    _sa.open_by_key(_sid)            # 存取探測(僅抓 metadata,1 read)
                    _cache[_sid] = True
                except Exception as _e:  # noqa: BLE001
                    try:
                        from infra.gspread_retry import is_quota_error as _iq
                        _quota = _iq(_e)
                    except Exception:  # noqa: BLE001
                        _quota = "429" in str(_e)
                    if _quota:                       # 429 暫時性 → 不快取、不回退(下次重試)
                        return _sa
                    _cache[_sid] = False
            if _cache[_sid]:
                return _sa                           # SA 開得了 → 用 SA(不碰 OAuth,免無謂 refresh)
            # SA 開不了「這張」sheet(403/404)→ 嘗試 user OAuth(本人擁有該 sheet)。
            # OAuth 取用**惰性 + 防呆**:token 過期/refresh 失敗不該拖垮「SA 本可服務」的讀取,
            # 建不起來 → 退回 SA,交給下游 describe_sheet_exc 的可行動 403 訊息(§1)。
            _oauth = None
            try:
                _oauth = _get_oauth_client()
            except Exception as _oe:  # noqa: BLE001
                import sys as _sys
                print(f"[t3_sheet_client] OAuth client 建立失敗({type(_oe).__name__})→ 維持 SA",
                      file=_sys.stderr)
            if _oauth is None:
                return _sa
            import sys as _sys
            print(f"[t3_sheet_client] SA 無法開啟 sheet {_sid[:12]}… → 回退 user OAuth client",
                  file=_sys.stderr)
            return _oauth
        return _get_oauth_client()
    from ui.helpers.data_registry import (
        _update_data_registry,
    )

    # 稽核 H1：分頁列寫「📊 配置 & 帳本」(story_nav SSOT)，這裡卻自己寫死
    # 「組合基金管理」—— 同一頁兩個名字。麵包屑第 4 站也是 SSOT，三者只有這裡脫隊。
    from ui.helpers.story_nav import (
        render_flow_nav, render_story_nav, tab_label as _tab_label_t3,
    )
    st.markdown(f"## {_tab_label_t3('portfolio')}")
    render_flow_nav("portfolio")   # 巨觀:監控與評分層(L3);層號由 story_nav SSOT 產生
    render_story_nav("portfolio")
    # 「六因子評分」自 v19.177 起已不再用於評等（改 4 維健診），標題不再這樣寫，
    # 免得使用者去說明書查一個退役模型（2026-08 稽核必修 8 同型）。
    st.caption("加入多檔基金，即時計算核心/衛星配比（金額加權）、4 維健診評等、現金流估算")

    if "portfolio_funds" not in st.session_state:
        st.session_state.portfolio_funds = []

    # ══════════════════════════════════════════════════════════════════════
    # 版面順序（WP-D）—— 客戶已拍板的線框 `docs/wireframes/fund-wireframe-final.html`
    # §03「④ 我的配置」：**照操作流程排，頁內不編號**
    #     加入與管理基金 → 配置總覽 → 持股重疊度診斷 → 帳本 → 費用與扣款
    #     → AI 摘要 → Raw data（收合，留在最後）
    # 線框原文：「照你實際的操作順序 —— 先加標的 → 看現在長怎樣 → 檢查重疊
    #            → 記帳與再平衡。」搬遷前的畫面順序是 ④→①→②→③
    #            （「加入基金」排在「配置總覽」之後，但你得先有基金才有配置可看）。
    #
    # ⚠️ **為什麼用 container 佔位、而不是把程式碼整段搬上去**（這是本批最關鍵的
    #    設計決定，請勿在不讀完這段的情況下「順手改成真的搬」）：
    #
    #    Streamlit 的**顯示順序 = container 建立順序**，**執行順序 = `with` 進入順序**。
    #    兩者可以分離（本 repo 釘版 streamlit 1.59.2 實測確認，守衛見
    #    `tests/test_wpd_portfolio_layout.py::test_container_slots_decouple_display_from_execution`）。
    #
    #    本批的任務是**版面重整，不是計算改動**。實測盤點出~~三處~~ **至少四處**
    #    「同一次 run 內先寫後讀 / 先讀後寫」的耦合，真的搬動程式碼會讓它們翻面：
    #      1. `portfolio_core_pct` —— slider 在「加入與管理基金」段尾（原 :2471）寫入，
    #         而「配置總覽」透過 `ui/helpers/portfolio/allocation.py` 讀它。
    #         搬遷前是**先讀後寫**（總覽吃的是上一次 run 的值）；把 slider 搬到總覽
    #         前面會變成**先寫後讀** → 同一次 run 的數字會變。
    #      2. `policy_sheet_id` —— 保單管理段寫、加入基金段讀。
    #      3. `gsheet_tokens` —— 加入基金段寫、保單管理段讀。
    #      4. `_schema_ver` —— 保單管理段寫（`policy_admin_section.py` 內
    #         `detect_sheet_schema_version` 偵測後寫入 / 一鍵升級後寫 "v2"），
    #         「保單分組視圖」讀（本檔「🔗 綁到保單」的顯示條件，與 `_sheet_id`
    #         同一個 `if`）。搬遷前是**先寫後讀**；把分組視圖排到保單管理之前
    #         會變成**先讀後寫** → 該下拉吃到上一次 run 的 schema 判定。
    #         （2026-08-31 獨立稽核補；原「三處」是實作組單組 AST 掃描的漏算 ——
    #          該掃描看不到「寫在抽出的模組、讀在本檔」這種跨檔耦合。
    #          守衛本身不受影響：執行順序測試是**整條 tuple 精確比對**，
    #          任何調換都會紅，不只保護被點名的 key。）
    #    ⚠️ 這四處是**已知清單，不是窮舉** —— 跨模組的 session_state 讀寫
    #    靜態掃不完整；日後要改 `with` 順序，先重掃再動。
    #    這幾處**都會改變畫面上的數字或顯示條件**，而本批**無權**改動計算
    #    （派工規格：「不得改變任何數字的算法」；`CLAUDE.md §-1.5.3 C` 禁止夾帶）。
    #
    #    → 故：**建立順序 = 線框要的顯示順序；`with` 順序 = 搬遷前的執行順序**。
    #      使用者看到的是新版面，每一個數字與搬遷前逐格相同。
    #    → 真正的程式碼搬移（連同上面各處耦合的處置）屬後續批次，不在 WP-D。
    # ══════════════════════════════════════════════════════════════════════
    _sec_add      = st.container()   # 1. 加入與管理基金（沒有標的就沒有配置）
    _sec_policy   = st.container()   # 1b. 保單管理（Google Sheets）—— WP-E 會把
                                     #     「連線／授權」搬去 ⑤、「保單列新增更新」留在 ④
    _sec_overview = st.container()   # 2. 配置總覽（現況長怎樣）
    _sec_overlap  = st.container()   # 3. 持股重疊度診斷
    _sec_switch   = st.container()   # 3b. 🎯 換股顧問（2026-09-01 自 ② 持倉體檢搬入）
    _sec_ledger   = st.container()   # 4-5. 帳本（T7）+ 費用與扣款
    _sec_ai       = st.container()   # 6. AI 摘要
    _sec_raw      = st.container()   # 7. Raw data（核對數字來源，留在最後、不擋路）

    # ══════════════════════════════════════════════════════════════════════
    # 🎯 換股顧問：從 ② 持倉體檢搬入（2026-09-01，客戶拍板線框 `ia-wireframe.html`）
    # ══════════════════════════════════════════════════════════════════════
    # **客戶給的理由（決定已定，不是本組的判斷）**：換股顧問產出的是**要執行的
    # 動作**，而 ② 全篇**只診斷、不建議**。線框 Tab 02「這裡不放什麼」逐字寫著
    # 「換股建議與再平衡試算 → 04（那是決策，不是診斷）」；Tab 04「從哪裡搬來」
    # 逐字寫著「換股顧問 ─ 自 02 的健診段切出」。
    #
    # **顯示位置**：`_sec_switch` 建在 `_sec_overlap` 與 `_sec_ledger` 之間 ——
    # 線框 Tab 04 的相對順序是「核心/衛星現況 → …… → 換股顧問 → …… → 交易帳本」，
    # 本批只保證這兩個既有錨點之間的相對位置正確。
    # ⚠️ **本批刻意不重排 ④ 既有的七個 slot**：那是「④ 全頁改版」，屬另一批
    #    （`CLAUDE.md §8.4 step 4` 禁止自作主張大重構；上面那段 container 註解
    #     已列出至少四處 session_state 先寫後讀耦合，重排會讓數字翻面）。
    #
    # **執行位置**：真正的 `with _sec_switch:` 在本函式**最後**（`_sec_ai` 之後）。
    # 這是本檔既有的「建立順序＝顯示順序、`with` 順序＝執行順序」慣例（見上方那段
    # 長註解）；排在最後是為了**一步都不動既有的執行順序** —— 本區塊只讀不寫
    # （它自己的 `_switch_advise_done` / `_perf_snapshot_done` 兩個 session key
    # 沒有任何其他消費者，實測見 `tests/test_ia_switch_advisor_moved_to_portfolio.py`）。
    #
    # **資料**：`_switch_funds` 由下方持倉健診段既有的 `_funds_extra` 指派而來 ——
    # 那是 ④ **本來就在算**、且已經餵給輪動配對／組合績效／效率前緣的同一份。
    # ⚠️ **不得**在這裡另外抓一次（`CLAUDE.md §-1.5.1c v3 §01-2`：同一個資料來源
    #    全站只能有一處取數實作）。一檔都沒載入時它維持空 list → 區塊走空狀態三要素。
    _switch_funds: list = []

    with _sec_overview:
        # 線框 §2「配置總覽」把三塊散在頁面上下兩端的「現況長怎樣」收在一起：
        # 配置總覽本體（含 KPI 卡與淨值成長模擬曲線）→ FX 曝險摘要／智能戰情室
        # → 保單分組視圖。同樣用子 slot 控制顯示順序，執行順序不動。
        _ov_core     = st.container()   # 配置總覽 + KPI 卡 + 淨值成長模擬曲線
        _ov_warroom  = st.container()   # FX 曝險摘要／智能戰情室
        _ov_group    = st.container()   # 保單分組視圖

    # ── 以下 `with` 的先後 = 搬遷前的執行順序，一步都沒有調換 ────────────────

    with _ov_warroom:
        # ── v18.9 智能戰情室（決策導向：核心衛星×體檢×買賣區間）────────────
        # 已載入基金時頂部優先顯示；空組合時讓給歡迎卡。
        _pf_for_warroom = [f for f in st.session_state.portfolio_funds
                           if f.get("loaded") and not f.get("load_error")]
        if _pf_for_warroom:
            # v18.163：頂部統一 hero KPI（合併 mk_war_room 4 卡 + 配息矩陣 4 卡，
            # 解決 user 反饋「上下兩段 KPI 重複占版面」）。
            from ui.helpers.portfolio_health import (
                compute_health_kpis,
                render_hero_kpi_cards,
            )
            try:
                from ui.components.mk_dashboard import build_mk_dataframe as _build_mk
                _loaded_hero = [f for f in _pf_for_warroom
                                 if f.get("loaded") and not f.get("load_error")]
                _mk_df_hero = _build_mk(_loaded_hero, bench_series=None)
            except Exception:
                _mk_df_hero = None   # smoke-allow-pass — KPI 不影響後續功能
            _kpis_hero = compute_health_kpis(_pf_for_warroom, _mk_df_hero)
            # （原本這裡把 _kpis_hero 塞進 session_state 說「供下方 expander summary 用」，
            #   但全 repo 沒有任何讀取方 —— 純粹的死寫入，已刪除。
            #   若日後真要跨區塊共用，請同批加上讀取端，不要先留一個沒人讀的 key。）
            st.markdown(
                f"<div style='background:linear-gradient(135deg,{BG_DARK_NAVY_2},{BG_DARK_NAVY_1});"
                f"border-left:4px solid {MD_BLUE_300};border-radius:8px;padding:10px 14px;margin:8px 0'>"
                f"<span style='color:{MD_BLUE_300};font-size:15px;font-weight:900'>📊 組合健康儀表</span>"
                f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px;margin-left:8px'>v18.163 6 指標一覽</span>"
                "</div>",
                unsafe_allow_html=True)
            render_hero_kpi_cards(_kpis_hero)

            # v19.303: FX 曝險摘要 — 組合匯率敏感度一覽
            try:
                _fx_counts: dict = {}
                for _pf_fx in _pf_for_warroom:
                    # 稽核 J1-b：原本是 `str(...or "USD").strip().upper() or "USD"`
                    # —— **雙重** USD fallback。實測後果：兩檔台幣計價的安聯台股基金
                    # 因 Sheet currency 欄空白而被算進 USD，整段印出「USD 25 檔（100%）」
                    # 與一句「組合 100% 為 USD 計價」的**錯誤風險警語**。
                    # 風險揭露區塊拿捏造的幣別當輸入，比不揭露更糟（§1）。
                    # 改法：未知就誠實歸到「未知」桶，不併進任何幣別。
                    _ccy = str(_pf_fx.get("currency") or "").strip().upper() or _UNKNOWN_CCY
                    _fx_counts[_ccy] = _fx_counts.get(_ccy, 0) + 1
                _total_fx = sum(_fx_counts.values()) or 1
                if _fx_counts:
                    # 取 FX 即時匯率（re-use tab3 cache pattern）
                    _fx_spot: dict = {}
                    for _ccy_fx in _fx_counts:
                        if _ccy_fx == "TWD":
                            _fx_spot[_ccy_fx] = 1.0
                            continue
                        if _ccy_fx == _UNKNOWN_CCY:
                            # 稽核 J1-b：未知幣別不去猜匯率、也不去打 API
                            _fx_spot[_ccy_fx] = 0.0
                            continue
                        try:
                            from services.fund_service import get_latest_fx as _gf_fx
                            import os as _os_fx
                            _fk_fx = st.secrets.get("FRED_API_KEY", "") or _os_fx.environ.get("FRED_API_KEY", "")
                            _v_fx = _gf_fx(f"{_ccy_fx}TWD=X", fred_api_key=_fk_fx)
                            _fx_spot[_ccy_fx] = float(_v_fx) if _v_fx else 0.0
                        except Exception:
                            _fx_spot[_ccy_fx] = 0.0
                    _fx_lines = []
                    for _ccy_fx, _cnt in sorted(_fx_counts.items(), key=lambda x: -x[1]):
                        _pct = _cnt / _total_fx * 100
                        _rate = _fx_spot.get(_ccy_fx, 0)
                        if _ccy_fx == _UNKNOWN_CCY:
                            # 稽核 J1-b：說清楚「查不到」與「怎麼補」，不冒充任何幣別
                            _rate_str = ("**計價幣別不明** —— 請在 Google Sheet 的 "
                                         "`currency` 欄補上（例：TWD / USD）")
                        else:
                            _rate_str = (f"1 {_ccy_fx} ≈ {_rate:.2f} TWD"
                                         if _rate > 0 else "匯率待抓")
                        _fx_lines.append(f"**{_ccy_fx}** {_cnt} 檔（{_pct:.0f}%）· {_rate_str}")
                    # 內容 < 6 行且含「USD 佔比過半」警告 → 收起來等於把風險藏起來（原則 1）。
                    # 原本用「永遠展開的 expander」達成,但那層殼本身不提供任何資訊 —— 對
                    # 使用者是多一圈邊框 + 一個假的「可收合」暗示。改成標題 + container。
                    st.markdown(f"##### 💱 FX 曝險摘要（{len(_fx_counts)} 種幣別）")
                    with st.container():
                        st.caption(
                            "組合中非 TWD 基金的幣別分布。台幣升值 1% 約等幅侵蝕該幣別折算績效。"
                        )
                        for _line in _fx_lines:
                            st.markdown(f"- {_line}")
                        # 稽核 J1-b：幣別不明的檔先講清楚，否則下面那句百分比會被
                        # 讀成「已知全貌」。原本它們被靜默併進 USD，直接造出假警語。
                        _unk_n = _fx_counts.get(_UNKNOWN_CCY, 0)
                        if _unk_n:
                            st.warning(
                                f"⚠️ 有 **{_unk_n} 檔**查不到計價幣別（Google Sheet 的 "
                                "`currency` 欄空白，且 MoneyDJ 也沒回傳）。這幾檔**未計入**"
                                "下方任何幣別的佔比，其匯率風險目前無法評估 —— "
                                "請到 Sheet 補上幣別後重新載入。"
                            )
                        _usd_pct = _fx_counts.get("USD", 0) / _total_fx * 100
                        if _usd_pct >= 50:
                            st.warning(
                                f"⚠️ 組合 {_usd_pct:.0f}% 為 USD 計價，台幣大幅升值時 TWD 績效將明顯縮水。"
                                + (f"（此比例的分母含上述 {_unk_n} 檔幣別不明者）" if _unk_n else "")
                            )
            except Exception as _e_fx_blk:
                # §1：FX 曝險是風險揭露，失敗要留痕（原本 `pass` → 畫面零痕跡）
                # 稽核 P2：補 file=sys.stderr —— Streamlit Cloud 的 log 面板
                # **只顯示 stderr**，走 stdout 的 print 在雲端完全撈不到。
                import sys as _sys_fx
                print(f"[tab3 FX 曝險摘要] 渲染失敗："
                      f"[{type(_e_fx_blk).__name__}] {_e_fx_blk}", file=_sys_fx.stderr)
                # 這是風險揭露區塊。訊息自己就寫「這不代表沒有匯率風險」——
                # 需要寫這句,正是因為灰字讓「沒風險」與「沒算出來」長得一樣。
                system_error("FX 曝險摘要渲染失敗", _e_fx_blk,
                             hint="**這不代表沒有匯率風險**,只代表這一項沒算出來。")

            st.divider()

            # v18.14: 改用 markdown 章節（避免外層 expander 包住內部 expander 觸發 Streamlit 巢狀錯誤）
            st.markdown(
                f"<div style='background:linear-gradient(135deg,{BG_DARK_NAVY_2},{BG_DARK_NAVY_1});"
                f"border-left:4px solid {MD_BLUE_300};border-radius:8px;padding:10px 14px;margin:8px 0'>"
                f"<span style='color:{MD_BLUE_300};font-size:15px;font-weight:900'>🎯 策略3 智能戰情室</span>"
                f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px;margin-left:8px'>v18.9 新手戰情中心</span>"
                "</div>",
                unsafe_allow_html=True)
            render_mk_war_room(st.session_state.portfolio_funds)
            st.divider()

            # v18.213：基金體檢表（郭老師「挑三揀四」PK 同類型，揪優等生 / 汰弱候選）
            from ui.helpers.fund_checkup import render_fund_checkup
            # expanded=True：同一個元件在組合健檢頁是展開的，這裡收起來 = 同元件兩種行為。
            # 體檢表是資料型內容（原則 1），統一展開。
            render_fund_checkup(st.session_state.portfolio_funds, expanded=True)
            st.divider()

            # v19.xxx： 3-3-3 原則批次篩選（留強汰弱量化依據）
            st.markdown(
                f"<div style='background:linear-gradient(135deg,{BG_DARK_NAVY_2},{BG_DARK_NAVY_1});"
                f"border-left:4px solid {MD_GREEN_A200};border-radius:8px;padding:10px 14px;margin:8px 0'>"
                f"<span style='color:{MD_GREEN_A200};font-size:15px;font-weight:900'>🔢  3-3-3 原則批次篩選</span>"
                f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px;margin-left:8px'>成立>3年 ／ 3年年化>7% ／ 晨星3星(手動確認)</span>"
                "</div>",
                unsafe_allow_html=True)
            try:
                from services.fund_screening import batch_333_funds as _batch_333
                _funds_333 = [
                    {
                        "code":    f.get("code", ""),
                        "name":    f.get("name") or f.get("code") or "",
                        "series":  f.get("series"),
                        "metrics": f.get("metrics") or {},
                    }
                    for f in _pf_for_warroom
                    if f.get("series") is not None
                ]
                if _funds_333:
                    # 原本是 `expanded=True` 的 expander —— 永遠開著的殼只是多一層邊框
                    # 和一次多餘的點擊，資料型內容直接攤平（原則 1）。
                    st.caption("📋 3-3-3 評估明細")
                    with st.container():
                        _df_333 = _batch_333(_funds_333)
                        if not _df_333.empty:
                            st.dataframe(
                                _df_333,
                                use_container_width=True,
                                hide_index=True,
                            )
                            st.caption(
                                "✅=通過 ❌=未通過 ❓=資料不足　"
                                "②來源空=MoneyDJ 含息報酬；②來源*=NAV 未含配息(保守估計)　"
                                "③晨星評級請至 [Morningstar](https://www.morningstar.com.tw/) 手動查閱"
                            )
                            # 整體通過統計
                            _pass_cnt = (_df_333["整體"] == "✅").sum()
                            _fail_cnt = (_df_333["整體"] == "❌").sum()
                            _unk_cnt  = (_df_333["整體"] == "❓").sum()
                            _total    = len(_df_333)
                            # 2026-08-05 稽核 🔴 必修 2(同型延伸):原寫死「由 Tab2 個別查詢」
                            # —— 個基深掘早已不是第 2 個分頁,序號寫死 = 與 :292 同一顆地雷。
                            # 一併收 story_nav.tab_label SSOT。
                            #
                            # ⚠️ 2026-08-31 七→五(客戶拍板線框)由 WP-F 收斂;
                            # **有意識的政策變更,不是漏改**(決策者:客戶 2026-08-31 五分頁動線)。
                            # 舊寫法 ~~`tab_label as _tab_label_333` + 「{…('fund')}」分頁~~
                            # 的理由**仍然成立**(指路必須吃 SSOT、序號不得寫死),上面兩行
                            # 註解照舊有效;被權衡掉的是它的**對象** —— `fund` 已經不是分頁,
                            # 而是「③ 🔍 基金研究」頁內的模式,`tab_label('fund')` 會當場 KeyError。
                            # 改用 `where_to_find('fund')`:回「③ 🔍 基金研究 → 🔍 單檔深掘」,
                            # 站號與分頁名都由 `_TAB_LABELS` 的順序推導。
                            # 「分頁」二字一併拿掉 —— 目的地是分頁裡的一個模式,不是一個分頁。
                            from ui.helpers.story_nav import (  # noqa: PLC0415
                                where_to_find as _where_to_find_333,
                            )
                            st.info(
                                f"共 {_total} 檔　✅ 通過 {_pass_cnt} 檔　"
                                f"❌ 未通過 {_fail_cnt} 檔　❓ 資料不足 {_unk_cnt} 檔　"
                                f"（③同儕排名請至「{_where_to_find_333('fund')}」個別查詢，"
                                f"組合批次僅評 ①②）",
                                icon="📊",
                            )
                        else:
                            st.info("NAV 資料尚未載入或不足，無法評估。")
                else:
                    st.info("請先在下方加入基金並載入資料。", icon="👇")
            except Exception as _e333_tab3:
                import sys as _sys333
                print(f"[tab3/333] batch error: {_e333_tab3}", file=_sys333.stderr)
                st.warning("3-3-3 批次評估載入失敗，請檢查 services/fund_screening.py。")
            st.divider()
        else:
            # v19.297：空組合歡迎卡 — 未加入任何基金（或全未載入）時的引導畫面
            # v19.334 user 指示「說明縮小,不需要這麼大」:48px 圖示+置中大標+28px padding
            # 的整屏卡 + 3 個 st.info 步驟框 → 收成單張緊湊卡(標題行+兩行說明),
            # 資訊不減、高度約原本 1/4。
            # 2026-08-05 稽核 🔴 必修 2:原寫死 Tab2「單檔基金」—— 該分頁名不存在,
            # 且它早已不是第 2 個分頁(app.py 現為 5 分頁,個基深掘排第 4)。分頁名
            # SSOT = ui/helpers/story_nav._STEPS(tab_label 去序號導出);序號一併拿掉
            # ——序號會隨分頁增刪漂移,寫死等於埋下同型地雷。
            #
            # ⚠️ 2026-08-31 七→五(客戶拍板線框)由 WP-F 收斂;**有意識的政策變更,
            # 不是漏改**(決策者:客戶 2026-08-31 五分頁動線)。
            # 舊寫法 ~~`tab_label as _tab_label` + 「{_tab_label('fund')}」分頁~~ 的理由
            # **仍然成立**(上面四行註解一個字都沒被推翻:分頁名要吃 SSOT、序號不得寫死);
            # 被權衡掉的是它的**對象** —— 七→五之後 `fund` 是「③ 🔍 基金研究」頁內的
            # 模式,不是分頁。照舊寫會 **KeyError**,而這張歡迎卡是**空組合時的預設畫面**,
            # 等於一進 ④ 就整頁壞掉。改用 `where_to_find('fund')`(站號由順序推導)。
            # 「分頁」二字一併拿掉 —— 目的地是分頁裡的一個模式。
            from ui.helpers.story_nav import where_to_find as _where_to_find  # noqa: PLC0415
            st.markdown(
                f"<div style='background:linear-gradient(135deg,{BG_DARK_NAVY_2},{BG_DARK_NAVY_1});"
                f"border:1px solid {GH_BORDER};border-radius:8px;"
                f"padding:10px 14px;margin:8px 0'>"
                f"<div style='color:{WHITE};font-size:14px;font-weight:700;margin-bottom:4px'>"
                f"📊 歡迎使用基金組合管理"
                f"<span style='color:{GRAY_AA};font-size:11px;font-weight:400'>"
                f"　— 加入基金後顯示 戰情室、組合健康儀表、3-3-3 篩選</span></div>"
                f"<div style='color:{GRAY_AA};font-size:12px;line-height:1.7'>"
                f"🔍 <b style='color:{TRAFFIC_NEUTRAL}'>「{_where_to_find('fund')}」</b>搜尋 → 按「➕ 加入組合」；"
                f"📥 或在下方「➕ 加入基金」輸入代碼點「📡 載入」；"
                f"也可從 Google Sheet 讀回已存組合。🎯 組合有資料後，分析自動出現在頁面頂部。"
                f"</div></div>",
                unsafe_allow_html=True)
            st.divider()

    with _sec_overlap:
        # v19.185 Bug5:相關性矩陣物理上移至摘要正下方(原在 T7 後)。
        # T5 只讀 session_state.portfolio_funds(全域)+ 自 guard(>=2 loaded),搬移變數安全。
        # ── T5: 持股相關性矩陣（v18.36 按保單分組）──────────────────────────────
        _pf_for_corr_raw = [f for f in st.session_state.portfolio_funds
                            if f.get("loaded") and f.get("series") is not None]

        # 按 policy_id 分組（無保單者歸入「(未綁保單)」），每組內按 code 去重，
        # 避免同 code 跨保單時 calc_holdings_overlap 回傳 DataFrame 重複欄名
        # 觸發 pyarrow `Duplicate column names found` 例外。
        from collections import defaultdict as _dd_t5
        _t5_buckets: dict = _dd_t5(list)
        for _ft5 in _pf_for_corr_raw:
            _pid_raw = str(_ft5.get("policy_id", "") or "").strip()
            _t5_buckets[_pid_raw or "(未綁保單)"].append(_ft5)
        _t5_groups: dict = {}
        for _pid_k, _items_k in _t5_buckets.items():
            _seen_c: set = set()
            _uniq_k: list = []
            for _ft5 in _items_k:
                _code_k = str(_ft5.get("code", "") or "").strip().upper()
                if not _code_k or _code_k in _seen_c:
                    continue
                _seen_c.add(_code_k)
                _uniq_k.append(_ft5)
            if len(_uniq_k) >= 2:
                _t5_groups[_pid_k] = _uniq_k

        if _t5_groups:
            st.divider()
            st.markdown("### 🔬 持股重疊度診斷（T5 — 底層持股 + 產業重疊度，按保單分組）")
            st.caption("以「持股 Jaccard × 0.6 + 產業 cosine × 0.4」綜合分;資料不齊自動降級為 NAV 相關係數。"
                       "重疊度 大於等於 0.70 → 影子基金警告。已依保單號碼分群，組內基金互相比較。")
            for _pid_g, _group_funds in _t5_groups.items():
                with st.expander(f"📋 保單 **{_pid_g}**　·　{len(_group_funds)} 檔基金", expanded=False):
                    _btn_key = f"btn_corr_{_pid_g}"
                    _ss_key  = f"corr_result_{_pid_g}"
                    if st.button("🔗 計算基金重疊度", key=_btn_key):
                        from services.portfolio_service import calc_holdings_overlap as _calc_holdings_overlap
                        _hov_input = []
                        for f in _group_funds:
                            _mj = (f.get("moneydj_raw") or {})
                            _h = _mj.get("holdings") or {}
                            _hov_input.append({
                                "code": f.get("code", "?"),
                                "name": f.get("name") or f.get("code"),
                                "top_holdings": _h.get("top_holdings") or [],
                                "sector_alloc": _h.get("sector_alloc") or [],
                            })
                        _hov_result = _calc_holdings_overlap(_hov_input)
                        if (not _hov_result) or _hov_result.get("method") == "n/a":
                            _corr_input = [{"code": f.get("code","?"), "series": f.get("series")}
                                           for f in _group_funds]
                            _hov_result = calc_correlation_matrix(_corr_input)
                            if _hov_result is not None:
                                _hov_result.setdefault("method", "nav_fallback")
                                _freq_used = _hov_result.get("freq", "?")
                                _hov_result.setdefault("notes",
                                    f"持股 / 產業資料皆缺，降級為 NAV Pearson 相關"
                                    f"（{_freq_used}頻；>= 0.85 為 shadow）")
                        st.session_state[_ss_key] = _hov_result
                    _cr = st.session_state.get(_ss_key)
                    if _cr and _cr.get("matrix") is not None:
                        _method = _cr.get("method", "?")
                        _notes  = _cr.get("notes", "")
                        _is_nav_fb = _method == "nav_fallback"
                        _shadow = _cr.get("shadow_pairs", [])
                        _thr = 0.85 if _is_nav_fb else 0.70
                        _label = "相關係數" if _is_nav_fb else "重疊度"
                        st.info(f"📌 計算方式：**{_method}**（{_notes}）")
                        if _shadow:
                            st.error(
                                f"⚠️ **影子基金警告**：偵測到 {len(_shadow)} 對 {_label} 大於等於 {_thr} 的基金，"
                                "持有意義可能重疊！"
                            )
                            _holdings_by_code: dict = {}
                            if not _is_nav_fb:
                                for _f in _group_funds:
                                    _mj_h = ((_f.get("moneydj_raw") or {}).get("holdings") or {})
                                    _holdings_by_code[_f.get("code", "?")] = [
                                        (h.get("name") or "").strip()
                                        for h in (_mj_h.get("top_holdings") or [])
                                        if h.get("name")
                                    ]
                            for _sa, _sb, _sv in _shadow:
                                _common_html = ""
                                if not _is_nav_fb:
                                    _ha = _holdings_by_code.get(_sa, [])
                                    _hb_upper = {n.upper() for n in _holdings_by_code.get(_sb, []) if n}
                                    _common = [n for n in _ha if n and n.upper() in _hb_upper]
                                    if _common:
                                        _items_zh = []
                                        for _n in _common[:6]:
                                            _zh = _zh_holding(_n)
                                            _items_zh.append(f"{_n[:18]}{f'({_zh})' if _zh else ''}")
                                        _more = f"…+{len(_common)-6}" if len(_common) > 6 else ""
                                        _common_html = (
                                            f"<div style='color:{MD_ORANGE_300};font-size:11px;margin:2px 0 0 12px'>"
                                            f"🔁 共同持股 {len(_common)} 檔："
                                            f"{'、'.join(_items_zh)}{_more}</div>")
                                st.markdown(
                                    f"- `{_sa}` × `{_sb}` — {_label} **{_sv:.3f}**{_common_html}",
                                    unsafe_allow_html=True)
                        else:
                            st.success(f"✅ 各基金 {_label} 均在 {_thr} 以下，組合分散效果良好")
                        def _color_overlap(v, _thr=_thr):
                            try: f = float(v)
                            except Exception: return ""
                            # v18.249: NaN（兩檔 NAV 無重疊期）不上色，跟其他級別區分
                            if pd.isna(f): return f"color:{TRAFFIC_NEUTRAL}"
                            if f >= _thr:    return f"background-color:#b71c1c;color:{WHITE}"
                            if f >= 0.50:    return f"background-color:#ef6c00;color:{WHITE}"
                            if f >= 0.20:    return f"background-color:#558b2f;color:{WHITE}"
                            if f >= -0.20:   return f"background-color:#2e7d32;color:{WHITE}"
                            return f"background-color:#1565c0;color:{WHITE}"
                        # v18.249: NaN → 「—」（codebase 標準缺失符號），不再顯示 'nan'
                        _fmt_corr = lambda v: "—" if pd.isna(v) else f"{v:.2f}"
                        try:
                            _styled = (_cr["matrix"].style
                                       .map(_color_overlap)
                                       .format(_fmt_corr))
                            st.dataframe(_styled, use_container_width=True)
                        except Exception:
                            st.dataframe(_cr["matrix"].round(2), use_container_width=True)
                        # v18.249: 補一行說明 — 兩檔 NAV 序列無重疊期就無法算相關性
                        if _cr["matrix"].isna().any().any():
                            st.caption(
                                "ℹ️ `—` 代表兩檔基金的 NAV 序列**無重疊期**（如新基金 vs 舊基金），"
                                "Pearson 相關係數無法計算；不代表 0 也不代表無相關。"
                            )
                        if _is_nav_fb:
                            st.caption(
                                "💡 NAV 相關法：1.0 = 漲跌完全一樣｜0.5~0.85 = 連動偏高｜0 = 無關｜負 = 反向。"
                                "🔴 大於等於 0.85 = 影子基金。"
                            )
                        else:
                            st.caption(
                                f"💡 持股 + 產業重疊度（method={_method}）：1.0 = 完全相同組合｜"
                                "0.7~1.0 = 影子基金 / 集中度過高｜0.4~0.7 = 中度重疊｜"
                                "0~0.3 = 分散良好。建議擇一持有 大於等於 0.7 的對。"
                            )

    with _sec_raw:
        # ── Raw data（v19.185 Bug5：摘要 → 矩陣 → Raw data → AI 版面順序）──────
        # 每檔基金 MoneyDJ 原始抓取結果攤平,供 user 核對 AI / 摘要的數字來源(§2.2 血緣)。
        _pf_raw_dump = [f for f in st.session_state.portfolio_funds
                        if f.get("loaded") and not f.get("load_error")]
        if _pf_raw_dump:
            with st.expander("🗂️ Raw data（基金原始抓取資料 — 核對數字來源）", expanded=False):
                st.caption("MoneyDJ wb01/wb05/wb07 + metrics 原始值;摘要表 / AI 戰情室的數字皆源於此。")
                for _frd in _pf_raw_dump:
                    _code_rd = _frd.get("code", "?")
                    _name_rd = (_frd.get("name") or _code_rd)[:30]
                    _m_rd = _frd.get("metrics") or {}
                    _mj_rd = _frd.get("moneydj_raw") or {}
                    _raw_view = {
                        "代碼": _code_rd,
                        "計價幣別": _mj_rd.get("currency") or _frd.get("currency") or "—",
                        "NAV(原幣)": _m_rd.get("nav") or _mj_rd.get("nav_latest"),
                        "年化配息率%(wb05)": _mj_rd.get("moneydj_div_yield"),
                        "年化配息率%(metrics)": _m_rd.get("annual_div_rate"),
                        "1Y含息%": _m_rd.get("ret_1y_total") or _m_rd.get("ret_1y"),
                        "Sharpe": _m_rd.get("sharpe"),
                        "年化波動%": _m_rd.get("std_1y"),
                        "最高經理費%": _mj_rd.get("mgmt_fee"),
                        "類別": _mj_rd.get("category") or "—",
                    }
                    st.markdown(f"**{_name_rd}** `{_code_rd}`")
                    st.json(_raw_view, expanded=False)

    with _sec_policy:
        # WP-D：約 800 行的「保單管理（Google Sheets）」原封抽出成獨立模組，
        # 邏輯一字未改（見該檔 docstring）。本頁暫時仍呼叫它 —— 線框要它搬去
        # ⑤「設定與診斷」，但 ⑤ 在本批還不存在（WP-E/WP-F），且線框 Q9 已拍板
        # 「新增／更新保單列」要**留在** ④ —— 那一刀屬 WP-E，本批不切。
        # `_sheet_id` 原本是本函式的區域變數，下方「保單分組視圖」要讀它；
        # 搬出去之後改由該函式回傳原值交還（刻意不重算，重算會讀到不同時點的
        # session_state，那是行為變更）。
        from ui.helpers.portfolio.policy_admin_section import (  # noqa: PLC0415
            render_policy_admin_section as _render_policy_admin,
        )
        _sheet_id = _render_policy_admin(
            oauth_configured=_oauth_configured,
            resolve_oauth_cfg=_resolve_oauth_cfg,
            get_oauth_client=_get_oauth_client,
            gsa_secret=_gsa_secret,
            sheet_id_secret=_sheet_id_secret,
            get_login_state=_get_login_state,
            sheet_client=_t3_sheet_client,
        )

    with _ov_group:
        # 原 `expanded=True` expander → 拿掉殼（原則 1：資料型區塊不加永遠開著的摺疊層）
        st.markdown("#### 🗂️ 保單分組視圖")
        with st.container():
            _pol_funds = [f for f in st.session_state.portfolio_funds if f.get("policy_id")]
            _ungrouped = [f for f in st.session_state.portfolio_funds if not f.get("policy_id")]

            # v18.151: 頂部捷徑 — 有未載入基金時直接顯示載入按鈕，避免使用者滾不下去找
            from ui.helpers.portfolio_load import (
                batch_load_unloaded_funds as _batch_load_top,
                count_unloaded_funds as _count_unloaded_top,
            )
            _n_ent_top, _n_uniq_top = _count_unloaded_top()
            if _n_ent_top > 0:
                _top_label = (
                    f"📡 載入未載入基金（{_n_ent_top} 條"
                    + (f" / {_n_uniq_top} unique code" if _n_uniq_top != _n_ent_top else "")
                    + "）— 抓即時 NAV / 績效"
                )
                if st.button(_top_label, type="primary",
                              key="btn_pf_load_all_top",
                              use_container_width=True):
                    _batch_load_top()

            if not _pol_funds and not _ungrouped:
                # 稽核 H3：原寫「📡 從 Sheet 同步」—— 全 repo 沒有這個按鈕標籤（死指標）。
                # 實際入口是「📋 保單管理」expander 內快速存讀面板的「📥 雲端讀取」。
                st.info("尚未載入任何基金。設定 Google Sheets 後，"
                        "展開上方「📋 保單管理（Google Sheets）」→ 按「📥 雲端讀取」"
                        "即可帶入保單分組。")
            else:
                # 取 VIX 給 advisor。
                # 原本讀的是一個**全 repo 沒有任何 writer** 的 session key（唯一寫入端
                # 是已移除的總經指南針元件），所以此處恆為 None，advise_fund 吃 VIX 的
                # 那條規則等於長期失效卻無人察覺。改走 helper 讀市場定調分頁實際寫入的
                # `indicators`，缺值仍誠實回 None（§1）。
                _vix_for_adv = _vix_for_advice()

                # 分組
                _by_policy: dict[str, list[dict]] = {}
                for _f in _pol_funds:
                    _by_policy.setdefault(_f.get("policy_id", "?"), []).append(_f)

                # P3 的 policy_tier→is_core 判定已上收 ui.helpers.portfolio.allocation，
                # 讓保單級與全組合級用同一把尺（見該檔 docstring 的 4 處差異表）。
                from ui.helpers.portfolio.allocation import (  # noqa: PLC0415
                    get_core_target_pct as _get_core_target_p,
                    resolve_core_flag as _is_core_in_policy,
                    summarize_core_satellite as _sum_cs_p,
                )

                _policy_target = _get_core_target_p(st.session_state)

                for _pid, _funds in _by_policy.items():
                    _pname = _funds[0].get("policy_name") or _pid
                    _cs_p  = _sum_cs_p(_funds, target_pct=_policy_target)
                    _ptot  = _cs_p["total_twd"]
                    _p_core_amt = _cs_p["core_twd"]
                    _p_core_pct = (round(_cs_p["core_pct"], 1)
                                   if _cs_p["core_pct"] is not None else 0)

                    st.markdown(
                        f"<div style='background:linear-gradient(135deg,{BG_DARK_NAVY_1},{BG_DARK_NAVY_2});"
                        f"border-left:4px solid {MD_BLUE_300};border-radius:8px;padding:10px 14px;margin:10px 0 6px'>"
                        f"<span style='color:{MD_BLUE_300};font-weight:900;font-size:15px'>🏷️ {_pname}</span>"
                        f"<span style='color:{GRAY_AA};font-size:11px;margin-left:8px'>({_pid})</span>"
                        f"<span style='color:{WHITE};font-size:13px;margin-left:auto;float:right'>"
                        f"投入 {fmt_twd(_ptot)} · {len(_funds)} 檔 · 核心 {_p_core_pct}%</span>"
                        f"</div>", unsafe_allow_html=True)

                    # ── P3: 保單級核心/衛星 mini donut ────────────────────
                    if _ptot > 0:
                        _dn_p_col, _dn_p_msg = st.columns([1, 2])
                        with _dn_p_col:
                            _dn_pv = [_p_core_amt, _ptot - _p_core_amt]
                            _dn_pl = [f"🛡️ 核心 {_p_core_pct}%",
                                      f"⚡ 衛星 {100 - _p_core_pct:.1f}%"]
                            fig_p_dn = go.Figure(go.Pie(
                                labels=_dn_pl, values=_dn_pv,
                                hole=0.65,
                                marker=dict(colors=[MD_BLUE_300, MATERIAL_ORANGE],
                                            line=dict(color=STREAMLIT_BG, width=1)),
                                textinfo="percent", textfont=dict(size=9),
                                hovertemplate="%{label}: NT$%{value:,.0f}<extra></extra>",
                            ))
                            fig_p_dn.update_layout(
                                paper_bgcolor=STREAMLIT_BG, plot_bgcolor=STREAMLIT_BG,
                                font_color=GH_FG_PRIMARY,
                                height=120,
                                margin=dict(t=4, b=4, l=4, r=4),
                                showlegend=False,
                                annotations=[dict(
                                    text=f"<b>{_p_core_pct}%</b>",
                                    x=0.5, y=0.5, font_size=12, showarrow=False,
                                    font=dict(color=MD_BLUE_300))],
                            )
                            st.plotly_chart(fig_p_dn, use_container_width=True,
                                            key=f"policy_dn_{_pid}")
                        # 預先算每檔 sigma / dividend 供 recommend_policy 用（與下方 fund-level 同邏輯）
                        _funds_enriched = []
                        for _f in _funds:
                            _s = _f.get("series")
                            _m = _f.get("metrics", {}) or {}
                            _mj_e = _f.get("moneydj_raw", {}) or {}
                            _sig_e = None
                            if _s is not None and len(_s.dropna()) >= 30:
                                try:
                                    from services.precision_service import calc_hwm_sigma_levels as _hwm_e
                                    _sig_e = _hwm_e(_s, lookback=252)
                                except Exception:
                                    _sig_e = None  # smoke-allow-pass
                            _div_e = None
                            try:
                                # v19.73 K1：走 SSOT 統一 Tab2/Tab3 含息報酬算法
                                from ui.helpers.macro_helpers import compute_1y_total_return
                                _tret_v, _ = compute_1y_total_return({
                                    "metrics": _m, "moneydj_raw": _mj_e,
                                })
                                _tret = safe_num(_tret_v)  # v19.399 §1:缺→None(不捏造 0),dividend_safety 對 None 自有 grey 誠實分支
                                _dyld = float(_mj_e.get("moneydj_div_yield")
                                              or _m.get("annual_div_rate") or 0)
                                if _dyld > 0:
                                    _div_e = div_safety_check(_tret, _dyld)
                            except Exception:
                                _div_e = None  # smoke-allow-pass
                            _funds_enriched.append({
                                "invest_twd": _f.get("invest_twd", 0) or 0,
                                "is_core":    _is_core_in_policy(_f),
                                "sigma_info": _sig_e,
                                "dividend_info": _div_e,
                            })
                        _p_rec = recommend_policy(_funds_enriched, target_core_pct=_policy_target)
                        _rec_clr = {"red": MATERIAL_RED, "orange": MATERIAL_ORANGE, "yellow": CAUTION_YELLOW,
                                    "green": MATERIAL_GREEN, "grey": TRAFFIC_NEUTRAL}.get(_p_rec["color"], TRAFFIC_NEUTRAL)
                        with _dn_p_msg:
                            st.markdown(
                                f"<div style='margin-top:18px;color:{_rec_clr};font-size:13px;"
                                f"line-height:1.55'>🎯 {_p_rec['text']}</div>",
                                unsafe_allow_html=True)

                    for _f in _funds:
                        _code = _f.get("code", "?")
                        _name = (_f.get("name") or _code)[:30]
                        if not _f.get("loaded"):
                            st.caption(f"⏳ {_code} {_name} — 尚未抓資料（按下方批次載入）")
                            continue
                        if _f.get("load_error"):
                            st.caption(f"❌ {_code} — 載入失敗：{_f.get('load_error')}")
                            continue

                        _series  = _f.get("series")
                        _metrics = _f.get("metrics", {}) or {}
                        _mj      = _f.get("moneydj_raw", {}) or {}

                        # σ 位階
                        _sigma_info = None
                        if _series is not None and len(_series.dropna()) >= 30:
                            try:
                                from services.precision_service import calc_hwm_sigma_levels as _hwm_fn2
                                _sigma_info = _hwm_fn2(_series, lookback=252)
                            except Exception as _se:
                                _sigma_info = {"error": str(_se)[:60]}

                        # 配息覆蓋率 / 吃本金
                        _div_info = None
                        try:
                            # v19.73 K1：走 SSOT 統一 Tab2/Tab3 含息報酬算法
                            from ui.helpers.macro_helpers import compute_1y_total_return
                            _tret_v, _ = compute_1y_total_return({
                                "metrics": _metrics, "moneydj_raw": _mj,
                            })
                            _tret = safe_num(_tret_v)  # v19.399 §1:缺→None(不捏造 0),dividend_safety 對 None 自有 grey 誠實分支
                            # v19.272 Phase 2 TOP 1:adr 走 SSOT 3 層 fallback chain(原行內 2 層收斂)
                            from services.health.dividend import _resolve_adr_with_fallback
                            _dyld_v, _ = _resolve_adr_with_fallback({
                                "metrics": _metrics, "moneydj_raw": _mj,
                            })
                            _dyld = float(_dyld_v or 0)
                            if _dyld > 0:
                                _div_info = div_safety_check(_tret, _dyld)
                        except Exception:
                            _div_info = None  # smoke-allow-pass

                        # 60MA 趨勢
                        _ma_trend = None
                        if _series is not None and len(_series.dropna()) >= 65:
                            try:
                                _ma60 = _series.dropna().rolling(60).mean()
                                if len(_ma60.dropna()) >= 5:
                                    _ma_trend = "up" if _ma60.iloc[-1] > _ma60.iloc[-5] else "down"
                            except Exception:
                                _ma_trend = None  # smoke-allow-pass

                        _advice = advise_fund(_sigma_info, _div_info, _ma_trend, _vix_for_adv)

                        _sig_lbl = (_sigma_info or {}).get("label", "—") if _sigma_info else "—"
                        _sig_clr = (_sigma_info or {}).get("color", TRAFFIC_NEUTRAL) if _sigma_info else TRAFFIC_NEUTRAL
                        _sig_rnk = (_sigma_info or {}).get("sigma_rank")
                        _sig_str = f"{_sig_rnk:+.2f}σ" if isinstance(_sig_rnk, (int, float)) else "—"
                        _div_alert = (_div_info or {}).get("alert_level", "grey")
                        _div_icon  = {"red": "🔴", "yellow": "🟡", "green": "🟢", "grey": "⚪"}.get(_div_alert, "⚪")
                        _adv_clr   = {"red": MATERIAL_RED, "orange": MATERIAL_ORANGE, "yellow": CAUTION_YELLOW,
                                      "green": MATERIAL_GREEN, "grey": TRAFFIC_NEUTRAL}.get(_advice["color"], TRAFFIC_NEUTRAL)
                        _inv_amt   = _f.get("invest_twd", 0) or 0

                        st.markdown(
                            f"<div style='background:{GH_BG_PRIMARY};border:1px solid {GH_BG_HOVER};border-radius:8px;"
                            f"padding:10px 14px;margin:4px 0 8px 20px'>"
                            f"<div style='display:flex;align-items:center;gap:12px;flex-wrap:wrap'>"
                            f"<span style='color:{GH_FG_PRIMARY};font-weight:700;font-size:13px'>{_name}</span>"
                            f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>{_code}</span>"
                            f"<span style='color:{_sig_clr};font-size:11px;background:{GH_BG_CARD};padding:2px 8px;border-radius:10px'>"
                            f"σ {_sig_str} · {_sig_lbl}</span>"
                            f"<span style='color:{GRAY_CC};font-size:11px'>{_div_icon} {_div_alert}</span>"
                            f"<span style='color:{GRAY_AA};font-size:11px;margin-left:auto'>{fmt_twd(_inv_amt)}</span>"
                            f"</div>"
                            f"<div style='color:{_adv_clr};font-size:12px;margin-top:6px;line-height:1.5'>"
                            f"💡 {_advice['text']}</div>"
                            f"</div>", unsafe_allow_html=True)

                if _ungrouped:
                    st.markdown(
                        f"<div style='color:{TRAFFIC_NEUTRAL};font-size:12px;margin-top:14px'>📂 未分組基金（手動加入、未綁保單）</div>",
                        unsafe_allow_html=True)
                    for _f in _ungrouped:
                        st.caption(f"• {_f.get('code','?')} — {_f.get('name','') or '尚未載入'}")
                    # v18.151: 「未綁保單」inline 快捷 — 載入這些 + 綁到保單下拉
                    st.caption(
                        f"⚠️ 你有 **{len(_ungrouped)} 檔未綁保單**（這些基金不在任何保單分頁內）。"
                    )
                    _ug_c1, _ug_c2 = st.columns([2, 3])
                    # 載入這些（會等同上方主按鈕，只是顯眼快捷）
                    _ug_not_loaded = [_g for _g in _ungrouped if not _g.get("loaded")]
                    if _ug_not_loaded:
                        if _ug_c1.button(f"📡 載入這 {len(_ug_not_loaded)} 檔",
                                           key="btn_load_ungrouped",
                                           use_container_width=True,
                                           help="跟頂部「載入未載入基金」同效果，方便就近點"):
                            from ui.helpers.portfolio_load import batch_load_unloaded_funds as _bl_ug
                            _bl_ug()
                    # 綁到既有保單（OAuth + 已升 v2 時才顯示，避免複雜化）
                    if _oauth_configured and _sheet_id and \
                       st.session_state.get("_schema_ver") == "v2":
                        try:
                            from repositories.policy_repository import list_policy_worksheets as _lpw
                            _existing_pids = _lpw(_get_oauth_client(), _sheet_id)
                        except Exception:
                            _existing_pids = []
                        if _existing_pids:
                            with _ug_c2:
                                _bind_pid = st.selectbox(
                                    "🔗 綁到保單", ["（先選保單）"] + list(_existing_pids),
                                    key="sel_bind_policy_ungrouped",
                                    label_visibility="collapsed")
                                if _bind_pid and _bind_pid != "（先選保單）":
                                    if st.button(f"✅ 套用：把這 {len(_ungrouped)} 檔綁到「{_bind_pid}」",
                                                  key="btn_apply_bind_pid",
                                                  use_container_width=True):
                                        # 把所有未綁基金都設 policy_id
                                        _cnt = 0
                                        for _idx, _ff in enumerate(st.session_state.portfolio_funds):
                                            if not _ff.get("policy_id"):
                                                st.session_state.portfolio_funds[_idx]["policy_id"] = _bind_pid
                                                _cnt += 1
                                        st.success(
                                            f"✅ 已把 {_cnt} 檔綁到「{_bind_pid}」（仍須到「✨ v2 編輯介面」"
                                            f"填 units/avg_nav/avg_fx 後 [💾 存到雲端] 才會推 Google Sheet）"
                                        )
                                        st.rerun()
                    else:
                        _ug_c2.caption(
                            "💡 升級到 v2 後可用「🔗 綁到保單」下拉，"
                            "或到「✨ v2 編輯介面」手動加列。"
                        )

    with _ov_core:
        # ── v18.46 緊湊歡迎條（單列三步驟，不再佔大面積）────────────────────
        # 稽核 E2:原為 `f.get("loaded")` —— 抓失敗的基金也是 loaded=True,
        # 於是最上方 KPI 卡寫「25 檔」、下面每張表只有 8 列。走 SSOT 判定。
        from ui.helpers.session import usable_funds as _usable_funds_e2
        _pf_loaded = _usable_funds_e2(st.session_state.portfolio_funds)
        if not _pf_loaded:
            st.markdown(
                f"<div style='background:{BG_DARK_NAVY_1};border:1px dashed {MD_BLUE_300};border-radius:8px;"
                f"padding:6px 14px;margin:4px 0 10px;font-size:12px;color:{GRAY_AA};"
                "display:flex;align-items:center;gap:12px;flex-wrap:wrap'>"
                f"<span style='color:{MD_BLUE_300};font-weight:700'>👋 三步驟：</span>"
                f"<span><b style='color:{WHITE}'>1️⃣ 貼代碼</b></span>"
                f"<span style='color:{GRAY_55}'>→</span>"
                f"<span><b style='color:{WHITE}'>2️⃣ 批次加入</b></span>"
                f"<span style='color:{GRAY_55}'>→</span>"
                f"<span><b style='color:{WHITE}'>3️⃣ 看 KPI / T5 / T7</b></span>"
                f"<span style='margin-left:auto;color:{GRAY_66};font-size:10px'>"
                "💡 AI 分析按鈕觸發，不自動扣 API</span>"
                "</div>", unsafe_allow_html=True)

        # ── 配置總覽（WP-D：頁內不編號，見上方版面順序說明）──
        if _pf_loaded:
            st.markdown("### 📊 配置總覽 — 你的組合現況")
            # §1：Sheet 本金欄若寫成 `NT$1,000` / `1000元`，原本會靜默變 0，該檔基金
            # 隨即在本金 / 核心% / 月配息 / 回撤權重全部消失且畫面零提示。
            # 這裡把 L1 loader 記下的解析失敗列**彙總指名**，使用者才知道去改哪一格。
            try:
                from repositories.policy_repository import (  # noqa: PLC0415
                    get_invest_twd_parse_errors as _get_inv_errs,
                )
                _inv_errs = _get_inv_errs()
            except Exception as _e_inv:
                _inv_errs = []
                print(f"[tab3] 本金解析回報讀取失敗：[{type(_e_inv).__name__}] {_e_inv}")
            if _inv_errs:
                _err_lines = []
                for _e in _inv_errs[:10]:
                    _who = (_e.get("fund_code") or _e.get("fund_url")
                            or _e.get("policy_id") or "—")
                    _err_lines.append(
                        f"- **{_e.get('source', '')} 第 {_e.get('row', '?')} 列**"
                        f"（{str(_who)[:40]}）：{_e.get('reason', '')}"
                    )
                st.warning(
                    f"⚠️ **{len(_inv_errs)} 列本金格式無法解析，已以 0 計入** —— "
                    "下方「投入本金 / 核心資產比例 / 預估月配息」都會少算這幾檔。\n\n"
                    + "\n".join(_err_lines)
                    + ("\n- …（其餘 %d 列略）" % (len(_inv_errs) - 10)
                       if len(_inv_errs) > 10 else "")
                    + "\n\n請在 Google Sheet 把該格改成**純數字**（可含千分位逗號），"
                    "例如 `1,000,000`；不要加 `NT$` / `元` / 中文數字。"
                )

        # ── v15.1 KPI 字卡列：投入本金 / 累計報酬 / 核心% / 月配息（新手語言）──
        if _pf_loaded:
            # 核心/衛星唯一真相：金額加權 + policy_tier 優先（見 allocation.py docstring）
            from ui.helpers.portfolio.allocation import (  # noqa: PLC0415
                format_core_satellite_caption as _fmt_cs_cap,
                get_core_target_pct as _get_core_target,
                summarize_core_satellite as _sum_cs,
            )
            _cs_kpi = _sum_cs(_pf_loaded,
                              target_pct=_get_core_target(st.session_state))
            _tot_kpi  = _cs_kpi["total_twd"]
            _core_pct_kpi = (round(_cs_kpi["core_pct"], 1)
                             if _cs_kpi["core_pct"] is not None else 0.0)
            # 累計報酬：以各基金 series 起點 → 當前點，按投資額加權
            _cum_ret_pct = None
            try:
                _w_returns = []
                _w_amounts = []
                for _f in _pf_loaded:
                    _s = _f.get("series")
                    _amt = _f.get("invest_twd", 0) or 0
                    if _s is not None and len(_s.dropna()) >= 2 and _amt > 0:
                        _ss = _s.dropna()
                        _ret = (float(_ss.iloc[-1]) / float(_ss.iloc[0]) - 1.0) * 100.0
                        _w_returns.append(_ret * _amt)
                        _w_amounts.append(_amt)
                if _w_amounts:
                    _cum_ret_pct = sum(_w_returns) / sum(_w_amounts)
            except Exception:
                _cum_ret_pct = None
            # 月配息估算：從 moneydj_raw.moneydj_div_yield / metrics.annual_div_rate
            # v18.39 修：原本用 dividend_yield_pct/yield_pct 都不是實際 schema 上的欄位，
            # 整個欄一直是 0；改用 v18.34 真實收益矩陣同款 fallback chain。
            _est_monthly_div = 0.0
            for _f in _pf_loaded:
                _mj_kpi = _f.get("moneydj_raw") or {}
                _m_kpi  = _f.get("metrics") or {}
                _yld = (_mj_kpi.get("moneydj_div_yield")
                        or _m_kpi.get("annual_div_rate")
                        or 0)
                _amt = _f.get("invest_twd", 0) or 0
                try:
                    _est_monthly_div += (float(_yld) / 100.0) * float(_amt) / 12.0
                except Exception:
                    pass  # smoke-allow-pass — 任一檔配息率非數值不影響其餘累加

            _ret_color = MATERIAL_GREEN if (_cum_ret_pct or 0) > 0 else (MATERIAL_RED if (_cum_ret_pct or 0) < 0 else TRAFFIC_NEUTRAL)
            _ret_str   = f"{_cum_ret_pct:+.2f}%" if _cum_ret_pct is not None else "—"
            st.markdown(
                "<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:8px 0 16px'>"
                f"<div style='background:linear-gradient(135deg,{BG_DARK_NAVY_1},{BG_DARK_NAVY_2});border:1px solid {GH_BORDER};"
                f"border-radius:12px;padding:16px 18px'>"
                f"<div style='color:{GRAY_AA};font-size:11px'>💰 投入本金（NTD）</div>"
                f"<div style='color:{WHITE};font-size:26px;font-weight:900;margin-top:4px'>{fmt_twd(_tot_kpi)}</div>"
                f"<div style='color:{TRAFFIC_NEUTRAL};font-size:10px;margin-top:2px'>"
                f"{len(_pf_loaded)} 檔手填本金加總 · 非當前市值</div></div>"
                f"<div style='background:linear-gradient(135deg,{BG_DARK_NAVY_1},{BG_DARK_NAVY_2});border:1px solid {GH_BORDER};"
                f"border-radius:12px;padding:16px 18px'>"
                f"<div style='color:{GRAY_AA};font-size:11px'>📈 累計報酬</div>"
                f"<div style='color:{_ret_color};font-size:26px;font-weight:900;margin-top:4px'>{_ret_str}</div>"
                f"<div style='color:{TRAFFIC_NEUTRAL};font-size:10px;margin-top:2px'>從淨值首日加權至今</div></div>"
                f"<div style='background:linear-gradient(135deg,{BG_DARK_NAVY_1},{BG_DARK_NAVY_2});border:1px solid {GH_BORDER};"
                f"border-radius:12px;padding:16px 18px'>"
                f"<div style='color:{GRAY_AA};font-size:11px'>🛡️ 核心資產比例</div>"
                f"<div style='color:{MD_BLUE_300};font-size:26px;font-weight:900;margin-top:4px'>{_core_pct_kpi:.1f}%</div>"
                f"<div style='color:{TRAFFIC_NEUTRAL};font-size:10px;margin-top:2px'>"
                f"衛星 {100-_core_pct_kpi:.1f}% · 金額加權</div></div>"
                f"<div style='background:linear-gradient(135deg,{BG_DARK_NAVY_1},{BG_DARK_NAVY_2});border:1px solid {GH_BORDER};"
                f"border-radius:12px;padding:16px 18px'>"
                f"<div style='color:{GRAY_AA};font-size:11px'>💵 預估月配息</div>"
                f"<div style='color:{MD_ORANGE_300};font-size:26px;font-weight:900;margin-top:4px'>{fmt_twd(_est_monthly_div)}</div>"
                f"<div style='color:{TRAFFIC_NEUTRAL};font-size:10px;margin-top:2px'>"
                f"以<b>本金</b>×配息率粗估</div></div>"
                "</div>", unsafe_allow_html=True)
            # 原則 4「多做說明」：三個最容易被誤讀的數字，一次講清楚基數是什麼。
            st.caption(
                "💡 **這四格的基數**：\n"
                "1. **投入本金 ≠ 當前市值** — 本金是你在 Google Sheet 手填的 `invest_twd`"
                "（放進去多少錢）；本頁「💼 持倉戰情（T7 帳本）」的「組合當前市值 (TWD)」"
                "＝ Σ 單位數 × 最新淨值 × 匯率（現在值多少錢）。兩者差額 = 未實現損益（± 已領配息）。\n"
                "2. **核心資產比例** — " + _fmt_cs_cap(_cs_kpi) + "\n"
                "3. **預估月配息** — 以**投入本金**× 年化配息率 ÷ 12 粗估；"
                "T7 帳本那格是以**當前市值**為基數。淨值下跌時本金基數會**高估**現金流，"
                "以 T7 的市值版為準。"
            )

            # ── 以下 4 個都是「風險揭露」元件（總經曝險 / 資料新鮮度 / 持股集中度 /
            #    產業集中度）。原本 4 個 `except: pass` 讓它們失敗時**畫面完全沒有痕跡**
            #    ——「沒出現」與「沒風險」長得一模一樣，是 §1 反造假的鏡像違規。
            #    現在改成：不阻斷主流程，但一律 stderr log + 畫面留一行說明它沒跑成功。
            def _risk_widget(_label: str, _fn) -> None:
                try:
                    _fn()
                except Exception as _e_w:
                    # 四個風險揭露元件共用這個 wrapper。同上：「沒出現」與「沒風險」
                    # 長得一樣是 §1 的鏡像違規,顏色要把它分開。
                    # （原本的 print 沒帶 file=sys.stderr,Streamlit Cloud 撈不到;
                    #   system_error → friendly_error 內建 stderr 鏡射,順帶修好。）
                    system_error(f"{_label} 渲染失敗", _e_w,
                                 hint="**這不代表沒有風險**,只代表這一項沒算出來。")

            # ── v19.64 I1：總經 → 組合曝險聯動 banner（讀 Tab1 phase_info，跨 Tab 訊號）──
            def _w_macro_link() -> None:
                from ui.helpers.macro_linkage import render_macro_exposure_link
                render_macro_exposure_link(st.session_state, core_pct=_core_pct_kpi)
            _risk_widget("總經曝險聯動提示", _w_macro_link)

            # ── v19.62 E3：MoneyDJ 資料新鮮度條（組合層級，所有基金聯合統計）──
            def _w_freshness() -> None:
                from ui.helpers.freshness import render_mj_freshness_banner
                _fresh_items = []
                for _f in _pf_loaded:
                    _mj = _f.get("moneydj_raw") or {}
                    _fresh_items.append({
                        "code": _f.get("code", "?"),
                        "name": _f.get("name", "") or _f.get("code", "?"),
                        "nav_date": _mj.get("nav_date", ""),
                        "fetched_at": _mj.get("_moneydj_fetched_at", ""),
                    })
                render_mj_freshness_banner(_fresh_items)
            _risk_widget("MoneyDJ 資料新鮮度", _w_freshness)

            # ── v19.66 I3：穿透式持股集中度摘要（聚合各基金 top_holdings，跨區塊聯動 T5）──
            def _w_conc() -> None:
                from ui.helpers.concentration import render_concentration_summary
                render_concentration_summary(_pf_loaded)
            _risk_widget("穿透式持股集中度", _w_conc)

            # ── v19.74 I7：穿透式產業集中度摘要（聚合各基金 sector_alloc）──
            def _w_sector() -> None:
                from ui.helpers.concentration import render_sector_concentration_summary
                render_sector_concentration_summary(_pf_loaded)
            _risk_widget("穿透式產業集中度", _w_sector)

            # ── v15.1 資產成長曲線（vs 2% 無風險基準，§0 禁 ETF）─────────
            # v18.43：同 code 跨多保單會讓 _value_series.name 重複，join 時欄名衝突拋例外。
            # 分析視圖按 code 去重（與 v18.34 戰情室 / v18.38 真實收益矩陣策略一致）。
            try:
                _curve_df = None
                _seen_curve: set = set()
                for _f in _pf_loaded:
                    _c_curve = str(_f.get("code", "") or "").strip().upper()
                    if not _c_curve or _c_curve in _seen_curve:
                        continue
                    _s = _f.get("series")
                    _amt = _f.get("invest_twd", 0) or 0
                    if _s is None or len(_s.dropna()) < 2 or _amt <= 0:
                        continue
                    _seen_curve.add(_c_curve)
                    _ss = _s.dropna()
                    # 折算為「今日金額對齊到首日 NAV → 今日 NAV」的成長
                    _value_series = (_ss / float(_ss.iloc[0])) * float(_amt)
                    _value_series.name = _c_curve
                    if _curve_df is None:
                        _curve_df = _value_series.to_frame()
                    else:
                        _curve_df = _curve_df.join(_value_series, how="outer")
                if _curve_df is not None and len(_curve_df) >= 2:
                    # W5-2 §1: 多基金 outer-join 後 NaN 代表「該基金當日無對應 NAV」(週末/假日/上市前),
                    # 此處 ffill 為「合成資產曲線」業務正確(用前一交易日 NAV 算當日市值),加 log 透明化
                    _ffill_n = int(_curve_df.isna().sum().sum())
                    _curve_df = _curve_df.sort_index().ffill()
                    if _ffill_n > 0:
                        print(f"[tab3 portfolio curve] ffill 補 {_ffill_n} 個 NaN(週末/假日/未上市前)")
                    _total_curve = _curve_df.sum(axis=1)
                    # 2% 無風險基準（從首日總額複利）
                    _days = (_total_curve.index - _total_curve.index[0]).days
                    _rf_curve = float(_total_curve.iloc[0]) * (1.0 + 0.02) ** (_days / 365.0)

                    # 原 `expanded=True` expander → 拿掉殼（原則 1）
                    # 命名誠實化：這條線畫的是 `(NAV_t / NAV_0) × invest_twd` 逐檔加總 ——
                    # 起點固定等於投入本金，之後只跟著**淨值相對漲跌**縮放。
                    # 它既不是本金（本金是常數，不會有曲線），也不是市值（沒有配息、
                    # 沒有實際分批扣款時點、沒有匯率）。用「資產總額」那類字眼會被直接
                    # 讀成「我現在有多少錢」，是本頁最容易誤導的一處。
                    st.markdown("#### 📈 淨值成長模擬曲線（含 2% 無風險基準對比）")
                    with st.container():
                        fig_curve = go.Figure()
                        fig_curve.add_trace(go.Scatter(
                            x=_total_curve.index, y=_total_curve.values,
                            name="你的組合", mode="lines",
                            line=dict(color=MATERIAL_GREEN, width=2.5, shape="spline"),
                            fill="tozeroy", fillcolor="rgba(0,200,83,0.08)",
                            hovertemplate="%{x|%Y-%m-%d}<br>NT$ %{y:,.0f}<extra></extra>"))
                        fig_curve.add_trace(go.Scatter(
                            x=_total_curve.index, y=_rf_curve,
                            name="2% 無風險基準", mode="lines",
                            line=dict(color=TRAFFIC_NEUTRAL, width=1.2, dash="dot"),
                            hovertemplate="%{x|%Y-%m-%d}<br>NT$ %{y:,.0f}<extra>無風險</extra>"))
                        # 標註：起點 / 當前 / 最高 / 最低
                        _hi_idx = _total_curve.idxmax(); _lo_idx = _total_curve.idxmin()
                        fig_curve.add_trace(go.Scatter(
                            x=[_total_curve.index[0], _hi_idx, _lo_idx, _total_curve.index[-1]],
                            y=[_total_curve.iloc[0], _total_curve.loc[_hi_idx],
                               _total_curve.loc[_lo_idx], _total_curve.iloc[-1]],
                            mode="markers+text",
                            marker=dict(size=[8,10,10,12],
                                        color=[TRAFFIC_NEUTRAL,MATERIAL_GREEN,MATERIAL_RED,WHITE],
                                        line=dict(color=STREAMLIT_BG, width=2)),
                            # 末點原本只標一個「今」字加金額 → 最容易被讀成「我現在有
                            # 多少錢」。改標「今日模擬」，與 y 軸／標題／下方說明同一套語彙。
                            text=["起點（＝投入本金）",
                                  f"高 {fmt_twd(_total_curve.loc[_hi_idx])}",
                                  f"低 {fmt_twd(_total_curve.loc[_lo_idx])}",
                                  f"今日模擬 {fmt_twd(_total_curve.iloc[-1])}"],
                            textposition=["top right","top center","bottom center","top left"],
                            textfont=dict(size=10, color=GH_FG_PRIMARY),
                            showlegend=False,
                            hoverinfo="skip"))
                        fig_curve.update_layout(
                            paper_bgcolor=STREAMLIT_BG, plot_bgcolor=GH_BG_CARD,
                            font_color=GH_FG_PRIMARY, height=320,
                            margin=dict(t=20, b=30, l=55, r=20),
                            legend=dict(orientation="h", y=1.05, font_size=10),
                            hovermode="x unified")
                        fig_curve.update_yaxes(title_text="模擬市值 (NTD)",
                                               gridcolor=BG_DARK_NAVY_3)
                        fig_curve.update_xaxes(gridcolor=BG_DARK_NAVY_3)
                        st.plotly_chart(fig_curve, use_container_width=True)
                        st.caption(
                            "💡 **怎麼看**：綠線是你的組合走勢，灰虛線是「把錢放定存賺 2%」的基準。"
                            "綠線在灰線上方代表你的選擇贏過定存。")
                        st.caption(
                            "📐 **這條線怎麼算的**：每檔基金的**投入本金**放在它第一個有淨值的"
                            "那天，之後只隨**淨值相對漲跌**等比例縮放，再把各檔加總。"
                            "**它不是你戶頭現在的錢** —— 未計入配息、未計入實際分批扣款的"
                            "買進時點、也未計入台幣兌原幣匯率；除息當天淨值跳空，這條線也會"
                            "跟著往下。真實金額請以保單對帳單為準。")
            except Exception as _curve_e:
                # v18.43 補錯誤型別讓使用者能 debug
                _friendly_error(
                    "資產曲線繪製失敗",
                    f"[{type(_curve_e).__name__}] {_curve_e}",
                    hint="可能是某些基金的 NAV 序列太短或缺漏，等資料補齊後重試即可。")

        # Hero：核心/衛星配置概況
        # v(本次)：核心/衛星四處各算各的 → 全部改吃 ui.helpers.portfolio.allocation
        # （金額加權 + policy_tier 優先 + 目標一律 portfolio_core_pct）。
        if _pf_loaded:
            # 這裡刻意**不**再呼叫 `format_core_satellite_caption`：它吃的是同一份
            # `_pf_loaded`，輸出與上方「💡 這四格的基數」第 2 點 byte-identical，
            # 印第二次只是把同一句話貼兩遍。分母 / 級別來源的說明留在那一處
            # （使用者第一次遇到這個百分比的地方），這裡只補它沒講的：目標值哪來的。
            from ui.helpers.portfolio.allocation import (  # noqa: PLC0415
                get_core_target_pct as _get_core_target2,
                summarize_core_satellite as _sum_cs2,
            )
            _target   = _get_core_target2(st.session_state)
            _cs_hero  = _sum_cs2(_pf_loaded, target_pct=_target)
            _tot  = _cs_hero["total_twd"]
            _core_pct = (round(_cs_hero["core_pct"], 1)
                         if _cs_hero["core_pct"] is not None else 0.0)
            _diff     = round(_cs_hero["diff_pct"], 1) if _cs_hero["diff_pct"] is not None else 0.0
            _dc       = MATERIAL_RED if abs(_diff)>10 else (MATERIAL_ORANGE if abs(_diff)>5 else MATERIAL_GREEN)
            st.markdown(
                f"<div style='background:linear-gradient(135deg,{BG_DARK_NAVY_1},#1a2332);border-radius:14px;padding:18px 22px;margin-bottom:16px;border:1px solid {GH_BORDER}'>"
                f"<div style='font-size:13px;color:{TRAFFIC_NEUTRAL};margin-bottom:10px'>📊 目前投資組合 — {len(_pf_loaded)} 檔" + (f" · 投入本金 {fmt_twd(_tot)}" if _tot else "") + "</div>"
                f"<div style='display:flex;gap:20px;flex-wrap:wrap'>"
                f"<div><div style='color:{MD_BLUE_300};font-size:11px'>🛡️ 核心資產</div><div style='color:{MD_BLUE_300};font-size:28px;font-weight:900'>{_core_pct}%</div></div>"
                f"<div><div style='color:{MATERIAL_ORANGE};font-size:11px'>⚡ 衛星資產</div><div style='color:{MATERIAL_ORANGE};font-size:28px;font-weight:900'>{100-_core_pct:.1f}%</div></div>"
                f"<div><div style='color:{_dc};font-size:11px'>目標偏差（目標核心 {_target:.0f}%）</div><div style='color:{_dc};font-size:28px;font-weight:900'>{_diff:+.1f}%</div></div>"
                f"</div></div>", unsafe_allow_html=True)

            # ── 核心/衛星甜甜圈（P1.3 縮成單列 mini chart）──────────────
            # v19.393 V4c:原 N 檔基金 = N 片但只藍/橙 2 色 → 同色 wedge 糊成一片不可讀(dataviz
            # 多切片圓餅反模式)。聚合成「核心 vs 衛星」2 片(與 :1322 保單級 donut 一致);
            # 總額 = Σ invest_twd 不變、核心% 不變,per-fund 明細見下方持倉健診表。
            _core_amt = _cs_hero["core_twd"]
            _sat_amt  = _cs_hero["sat_twd"]
            _n_core   = _cs_hero["n_core"]
            _dn_labels = [f"🛡️ 核心 · {_n_core} 檔", f"⚡ 衛星 · {_cs_hero['n_sat']} 檔"]
            _dn_values = [_core_amt, _sat_amt]
            _dn_colors = [MD_BLUE_300, MATERIAL_ORANGE]
            _alert     = abs(_diff) > 10
            _bg_c      = "#1a0808" if _alert else STREAMLIT_BG
            fig_dn = go.Figure()
            if sum(_dn_values) > 0:
                fig_dn.add_trace(go.Pie(
                    labels    = _dn_labels,
                    values    = _dn_values,
                    hole      = 0.65,
                    marker    = dict(colors=_dn_colors, line=dict(color=STREAMLIT_BG, width=1)),
                    textinfo  = "percent",
                    textfont  = dict(size=9),
                    hovertemplate="%{label}: NT$%{value:,.0f} (%{percent})<extra></extra>",
                ))
            fig_dn.update_layout(
                paper_bgcolor = _bg_c, plot_bgcolor = _bg_c,
                font_color    = GH_FG_PRIMARY,
                height        = 140,
                margin        = dict(t=4, b=4, l=4, r=4),
                showlegend    = False,
                annotations   = [dict(
                    text  = f"<b>{_core_pct}%</b><br><span style='font-size:9px'>核心</span>",
                    x=0.5, y=0.5, font_size=14, showarrow=False,
                    font=dict(color=MD_BLUE_300))],
            )
            st.plotly_chart(fig_dn, use_container_width=True)
            if not _cs_hero["is_amount_weighted"]:
                st.caption(
                    "⬜ 全部 %d 檔都沒填投入本金 → 無法算金額比例，上方 0%% 不代表真的沒有核心資產。"
                    % _cs_hero["n_funds"]
                )
            elif _alert:
                st.caption(
                    f"⚠️ 配置偏離 {_diff:+.1f}%（核心 {_core_pct}% vs 目標 {_target:.0f}%）— "
                    f"{'核心過重，可贖回轉衛星' if _diff > 0 else '衛星過重，可獲利轉核心'}"
                )
            else:
                st.caption(
                    f"✅ 配置健康（核心 {_core_pct}% / 衛星 {100-_core_pct:.1f}%，"
                    f"偏差 {_diff:+.1f}%，目標 {_target:.0f}%±10%）"
                )
            st.caption(
                "📐 這裡的核心% 與上方「🛡️ 核心資產比例」字卡是同一個數字（同一份持倉、"
                "同一套算法）；分母與級別來源的說明見上方「💡 這四格的基數」第 2 點。"
                "目標值來自下方「⚙️ 組合設定」的核心比例 slider。")
            # v18.192：教學化 — 核心/衛星 + 配息覆蓋率白話文（收合、不藏數據）
            render_metric_explainer(["core_satellite", "div_coverage"])

    with _sec_add:
        st.markdown("### ➕ 加入與管理基金")
        with st.expander("➕ 手動加入基金（支援多檔批次）", expanded=False):
            st.caption(
                "**📋 2 步驟流程**　·　Step 1（這裡）：貼**代碼** → 按 **➕ 批次加入** → "
                "**📡 載入所有未載入基金**　→　Step 2（下方 T7「📝 編輯初始持倉」）：輸入"
                "**單位數 / 平均成本 / 匯率**　→　上方「📦 全部寫入 Sheet」一鍵同步雲端。"
            )
            _existing_pids = st.session_state.get("policy_tabs", [])
            c_codes, c_default_pid = st.columns([3, 2])
            with c_codes:
                pf_codes_input = st.text_area(
                    "基金代碼（每行一檔，可加 ,pid 逐行覆寫）",
                    label_visibility="collapsed",
                    # v18.62: 高度 120 → 75 防手機被按鈕擠到 fold 下方
                    height=75,
                    placeholder=("ACCP138\nACDD01\nJFZN3,PL-2024-002"),
                    key="pf_codes_input",
                )
            with c_default_pid:
                pf_pid_input = st.text_input(
                    "預設保單號碼（可選）",
                    label_visibility="collapsed",
                    placeholder=("預設保單 " + (
                        f"（已有：{', '.join(_existing_pids[:3])}{'…' if len(_existing_pids)>3 else ''}）"
                        if _existing_pids else "（可選）")),
                    key="pf_pid_input",
                )
            pf_add_btn = st.button(
                "➕ 批次加入（加完按上方「📡 載入所有未載入基金」抓資料）",
                type="primary",
                use_container_width=True,
                key="btn_pf_add",
            )

            if pf_add_btn and pf_codes_input.strip():
                default_pid = pf_pid_input.strip()
                # ── v18.33: 解析多行輸入 ──────────────────────────────
                _entries: list[tuple] = []   # [(code, pid), ...]
                _existing_set = {(f["code"], f.get("policy_id", "") or "")
                                  for f in st.session_state.portfolio_funds}
                _skipped_dup: list[str] = []
                for _line in pf_codes_input.splitlines():
                    _line = _line.strip()
                    if not _line:
                        continue
                    if "," in _line:
                        _parts = [p.strip() for p in _line.split(",", 1)]
                        _code, _pid = _parts[0].upper(), _parts[1]
                    else:
                        _code = _line.upper()
                        _pid = default_pid
                    if not _code:
                        continue
                    if (_code, _pid) in _existing_set:
                        _skipped_dup.append(f"{_code}@{_pid or '(未綁)'}")
                        continue
                    _existing_set.add((_code, _pid))
                    _entries.append((_code, _pid))

                if not _entries:
                    if _skipped_dup:
                        st.warning(
                            f"⚠️ 全部已存在於組合：{', '.join(_skipped_dup[:10])}"
                            f"{'…' if len(_skipped_dup) > 10 else ''}"
                        )
                    else:
                        st.warning("⚠️ 沒有有效代碼可加入")
                else:
                    # ── v18.33: 並行抓取 + v18.58: 按 unique code 先 dedupe 再 broadcast
                    # 同 code 跨 N 保單只 fetch 一次，再 broadcast 給所有 (code, pid)
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    _uniq_codes = list({_c for _c, _ in _entries})
                    _progress = st.progress(0.0,
                        text=f"開始並行載入 {len(_uniq_codes)} 檔 unique 基金"
                             f"（{len(_entries)} 條 entry, dedupe by code）…")
                    _code_to_raw: dict = {}   # code → (raw_dict, error_msg)
                    _done = 0
                    with ThreadPoolExecutor(max_workers=4) as _ex:
                        _futures = {
                            _ex.submit(auto_fetch_moneydj, _c): _c
                            for _c in _uniq_codes
                        }
                        for _fut in as_completed(_futures):
                            _c_key = _futures[_fut]
                            try:
                                _code_to_raw[_c_key] = (_fut.result(), None)
                            except Exception as _e:
                                _code_to_raw[_c_key] = (None, str(_e)[:80])
                            _done += 1
                            _progress.progress(
                                _done / len(_uniq_codes),
                                text=f"完成 {_done}/{len(_uniq_codes)}：剛完成 {_c_key}",
                            )
                    _progress.empty()
                    # broadcast：每個 (code, pid) 都拿同一份 raw_dict
                    _results: dict = {
                        (_c, _p): _code_to_raw[_c] for _c, _p in _entries
                    }

                    # ── v18.33: 批次寫入 + Sheets 同步（單一 OAuth client）──
                    _succ, _fail, _sheet_synced = [], [], []
                    _cfg_b = _resolve_oauth_cfg()
                    _toks_b = st.session_state.get("gsheet_tokens")
                    _sid_b = st.session_state.get("policy_sheet_id")
                    _client_b = None
                    if _cfg_b and _toks_b and _sid_b:
                        try:
                            _t_b = ensure_fresh_tokens(dict(_toks_b),
                                _cfg_b["client_id"], _cfg_b["client_secret"])
                            st.session_state["gsheet_tokens"] = _t_b
                            _creds_b = build_credentials_from_tokens(_t_b,
                                _cfg_b["client_id"], _cfg_b["client_secret"])
                            _client_b = get_gspread_client_from_oauth(_creds_b)
                        except Exception as _e_oc:
                            _client_b = None
                            # `_client_b = None` → 下方每一檔的 Sheet 同步都會被跳過,
                            # 使用者卻只看到一行灰字,會以為已經寫進雲端了。
                            system_error("OAuth client 建立失敗", _e_oc,
                                         hint="這批基金**不會**寫進雲端 Sheet,只留在本機 session。")

                    for (_code_b, _pid_b), (_raw_b, _err_b) in _results.items():
                        _new_item_b = {"code": _code_b, "invest_twd": 0,
                                        "loaded": True, "load_error": None,
                                        "policy_id": _pid_b,
                                        "policy_name": _pid_b}
                        _emsg = _err_b or (_raw_b.get("error") if _raw_b else "")
                        if _emsg:
                            _new_item_b.update({"load_error": _emsg})
                            _fail.append(f"{_code_b}: {str(_emsg)[:40]}")
                        else:
                            _new_item_b.update({
                                "name":        _raw_b.get("fund_name") or _code_b,
                                "series":      _raw_b.get("series"),
                                "dividends":   _raw_b.get("dividends", []),
                                "metrics":     _raw_b.get("metrics", {}),
                                "moneydj_raw": _raw_b,
                                "risk_metrics":_raw_b.get("risk_metrics", {}),
                                "is_core":     _is_core_fund(
                                    _raw_b.get("fund_name") or _code_b),
                                "currency":    _raw_b.get("currency", "")
                                                or _raw_b.get("metrics", {}).get("currency", ""),
                            })
                            _succ.append(_code_b)
                            # v18.272：記錄到「曾經查過的基金清單」（Tab6 顯示）
                            try:
                                from services.fund_history import record_fund as _rec_fh3
                                _rec_fh3(
                                    _code_b,
                                    _raw_b.get("fund_name", "") or _code_b,
                                    source="Tab3",
                                )
                            except Exception:
                                pass
                            if _pid_b and _client_b:
                                try:
                                    upsert_fund_in_policy(_client_b, _sid_b, _pid_b, {
                                        "fund_url":     _code_b,
                                        "policy_name":  _pid_b,
                                        "invest_twd":   0,
                                        "invest_date":  "",
                                        "currency":     _new_item_b.get("currency", ""),
                                        "fx_at_buy":    0.0,
                                        "notes":        "Tab3 batch add",
                                        "policy_tier":  ("core" if _new_item_b.get("is_core")
                                                         else "satellite"
                                                         if _new_item_b.get("is_core") is False
                                                         else ""),
                                    })
                                    _sheet_synced.append(_code_b)
                                except (PolicySheetError, OAuthError) as _e_ws:
                                    _fail.append(
                                        f"{_code_b} Sheet 同步: {str(_e_ws)[:30]}")
                        st.session_state.portfolio_funds.append(_new_item_b)

                    # 完成後刷新 policy_tabs cache
                    if _client_b and _sheet_synced:
                        try:
                            st.session_state["policy_tabs"] = (
                                list_policy_worksheets(_client_b, _sid_b))
                        except Exception as _e_ref:
                            # 刷新失敗 → `policy_tabs` 停在舊值,下拉選單會少掉這次新增的
                            # 保單分頁。那是「這個清單不可信」,不是「還沒載入」。
                            system_error("保單列表刷新失敗", _e_ref,
                                         hint="上方保單下拉選單可能仍是舊的,重新整理本頁即可更新。")

                    _update_data_registry()

                    # ── 摘要訊息 ────────────────────────────────────────
                    _msg_parts = [f"成功 {len(_succ)} 檔"]
                    if _sheet_synced:
                        _msg_parts.append(f"☁️ Sheet 同步 {len(_sheet_synced)} 檔")
                    if _skipped_dup:
                        _msg_parts.append(f"⏭️ 跳過 {len(_skipped_dup)} 檔已存在")
                    if _fail:
                        _msg_parts.append(f"❌ 失敗 {len(_fail)} 檔")
                    _summary = " · ".join(_msg_parts)
                    if _fail:
                        st.error(f"批次加入完成 — {_summary}")
                        st.caption("**失敗明細**：")
                        for _f_msg in _fail[:10]:
                            st.caption(f"• {_f_msg}")
                        if len(_fail) > 10:
                            st.caption(f"…還有 {len(_fail) - 10} 筆")
                    else:
                        st.success(f"✅ 批次加入完成 — {_summary}")
                    st.rerun()

        pf = st.session_state.portfolio_funds
        if not pf:
            st.info("💡 請在上方輸入基金代碼加入，支援多檔同時比較")
        else:
            # 批次載入按鈕（v18.151：邏輯抽到 ui/helpers/portfolio_load.py）
            not_loaded = [i for i, f in enumerate(pf) if not f.get("loaded")]
            if not_loaded:
                from ui.helpers.portfolio_load import (
                    batch_load_unloaded_funds as _batch_load,
                    count_unloaded_funds as _count_unloaded,
                )
                _n_ent, _n_uniq = _count_unloaded()
                _btn_label = (
                    f"📡 載入所有未載入基金（{_n_ent} 條 entry"
                    + (f" / {_n_uniq} unique" if _n_uniq != _n_ent else "")
                    + "）"
                )
                if st.button(_btn_label, type="primary", key="btn_pf_load_all"):
                    _batch_load()

            # v18.30: 為主清單預計算 VIX（給每檔 advise_fund 用）
            # 同上：原本讀的那個 session key 0 writer → 恆 None。改吃市場定調分頁的 indicators。
            _vix_t3_main = _vix_for_advice()

            def _compute_advice_for(_pf_item: dict) -> dict:
                """v18.30: 從 pf_item 算出 advise_fund 需要的三組訊號 + 呼叫 advisor。
            失敗時回傳 grey '⏳ 資料不足'。"""
                try:
                    _s_local = _pf_item.get("series")
                    _m_local = _pf_item.get("metrics", {}) or {}
                    _mj_local = _pf_item.get("moneydj_raw", {}) or {}
                    _sigma = None
                    if _s_local is not None and len(_s_local.dropna()) >= 30:
                        try:
                            from services.precision_service import calc_hwm_sigma_levels as _hwm_fn3
                            _sigma = _hwm_fn3(_s_local, lookback=252)
                        except Exception as _e_s:
                            _sigma = {"error": str(_e_s)[:60]}
                    _div = None
                    try:
                        # v19.73 K1：走 SSOT 統一 Tab2/Tab3 含息報酬算法
                        from ui.helpers.macro_helpers import compute_1y_total_return
                        _tret_v, _ = compute_1y_total_return({
                            "metrics": _m_local, "moneydj_raw": _mj_local,
                        })
                        _tret_l = safe_num(_tret_v)  # v19.399 §1:缺→None(不捏造 0),dividend_safety 對 None 自有 grey 誠實分支
                        _dyld_l = float(_mj_local.get("moneydj_div_yield")
                                         or _m_local.get("annual_div_rate") or 0)
                        if _dyld_l > 0:
                            _div = div_safety_check(_tret_l, _dyld_l)
                    except Exception:
                        _div = None   # smoke-allow-pass
                    _ma = None
                    if _s_local is not None and len(_s_local.dropna()) >= 65:
                        try:
                            _ma60_l = _s_local.dropna().rolling(60).mean()
                            if len(_ma60_l.dropna()) >= 5:
                                _ma = "up" if _ma60_l.iloc[-1] > _ma60_l.iloc[-5] else "down"
                        except Exception:
                            _ma = None   # smoke-allow-pass
                    return advise_fund(_sigma, _div, _ma, _vix_t3_main)
                except Exception:
                    return {"text": "⏳ 建議計算失敗",
                            "code": "ERROR", "color": "grey"}

            # v18.37 基金清單按保單號碼分組成 expander。
            # 不再使用 v18.35 per-fund 內層 expander（外層保單 expander 已提供摺疊功能；
            # Streamlit 禁止 expander 巢狀，這裡刻意把詳細內容攤平在保單 expander 內）。
            # 預設 **展開**（原則 1）：這一區是「我的持倉現況」主資料 —— 每檔的 NAV /
            # 配息率 / Sharpe / σ / 建議都在裡面，收起來等於把主角藏在摺疊層後面。
            from collections import defaultdict as _dd_pf_main
            from ui.helpers.portfolio.allocation import (  # noqa: PLC0415
                resolve_core_flag as _core_flag_card,
            )
            _pf_by_pid: dict = _dd_pf_main(list)
            for i, pf_item in enumerate(pf):
                _pid_main = str(pf_item.get("policy_id", "") or "").strip() or "(未綁保單)"
                _pf_by_pid[_pid_main].append((i, pf_item))

            for _pid_main, _items_main in _pf_by_pid.items():
              with st.expander(f"📋 保單 **{_pid_main}**　·　{len(_items_main)} 檔基金", expanded=True):
                for i, pf_item in _items_main:
                    status_icon = "✅" if (pf_item.get("loaded") and not pf_item.get("load_error")) else ("❌" if pf_item.get("load_error") else "⏳")
                    m_i    = pf_item.get("metrics",{})
                    rm_i   = pf_item.get("risk_metrics",{})
                    rt_i   = rm_i.get("risk_table",{})
                    # 走全站唯一真相（policy_tier 優先），否則同一檔會「卡片寫衛星、
                    # KPI 卻把它算進核心」——原本這裡只讀 is_core，無視 Sheet 的 policy_tier。
                    role_i = "🛡️核心" if _core_flag_card(pf_item) else "⚡衛星"
                    _nav_i  = m_i.get("nav") or (pf_item.get("moneydj_raw") or {}).get("nav_latest","")
                    _adr_i  = (pf_item.get("moneydj_raw") or {}).get("moneydj_div_yield") or m_i.get("annual_div_rate","")
                    _sh_i   = (rt_i.get("一年") or {}).get("Sharpe","")
                    _std_i  = (rt_i.get("一年") or {}).get("標準差","")
                    with st.container():
                        ci1, ci2, ci3 = st.columns([4,4,1])
                        with ci1:
                            st.markdown(
                                f"<div style='padding:8px 12px;background:{GH_BG_CARD};border-radius:8px;margin:3px 0'>"
                                f"{status_icon} <b style='color:{GH_FG_PRIMARY}'>{(pf_item.get('name','') or pf_item['code'])[:28]}</b> "
                                f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>{pf_item['code']}</span> "
                                f"<span style='color:{MATERIAL_ORANGE};font-size:11px;margin-left:6px'>{role_i}</span></div>",
                                unsafe_allow_html=True)
                        with ci2:
                            st.markdown(
                                f"<div style='padding:8px 12px;background:{GH_BG_CARD};border-radius:8px;margin:3px 0;font-size:11px;color:{TRAFFIC_NEUTRAL}'>"
                                f"NAV: <b style='color:{GH_FG_PRIMARY}'>{_nav_i}</b>"
                                f"　配息率: <b style='color:{MATERIAL_ORANGE}'>{_adr_i}{'%' if _adr_i else ''}</b>"
                                f"　Sharpe: <b style='color:{MD_GREEN_A200}'>{_sh_i}</b>"
                                f"　σ: <b>{_std_i}{'%' if _std_i else ''}</b></div>",
                                unsafe_allow_html=True)
                        with ci3:
                            if st.button("🗑️", key=f"del_pf_{i}", help=f"移除 {pf_item['code']}"):
                                st.session_state.portfolio_funds.pop(i)
                                st.rerun()

                        if pf_item.get("load_error"):
                            st.caption(f"⚠️ {pf_item['load_error']}")

                        # 詳細建議 + 訊號（攤平在保單 expander 內，不再用內層 expander）
                        _can_detail = pf_item.get("loaded") and not pf_item.get("load_error")
                        if _can_detail:
                            _adv_card = _compute_advice_for(pf_item)
                            _adv_clr_card = {
                                "red": MATERIAL_RED, "orange": MATERIAL_ORANGE, "yellow": CAUTION_YELLOW,
                                "green": MATERIAL_GREEN, "grey": TRAFFIC_NEUTRAL
                            }.get(_adv_card.get("color", "grey"), TRAFFIC_NEUTRAL)
                            st.markdown(
                                f"<div style='padding:6px 12px;background:{GH_BG_PRIMARY};"
                                f"border-left:3px solid {_adv_clr_card};"
                                f"border-radius:6px;margin:3px 0 8px 0;"
                                f"font-size:12px;color:{_adv_clr_card};line-height:1.55'>"
                                f"💡 {_adv_card.get('text', '—')}</div>",
                                unsafe_allow_html=True)

                            # ──  v3.0 買賣訊號迷你卡（共用 Tab2 的 metrics）──
                            if m_i:
                                _mi_b1 = m_i.get("buy1");  _mi_b2 = m_i.get("buy2");  _mi_b3 = m_i.get("buy3")
                                _mi_s1 = m_i.get("sell1"); _mi_s2 = m_i.get("sell2"); _mi_s3 = m_i.get("sell3")
                                _mi_nav = float(m_i.get("nav") or 0)
                                _mi_pl  = m_i.get("pos_label","正常")
                                _mi_pc  = m_i.get("pos_color",TRAFFIC_NEUTRAL)
                                _mi_bbd = m_i.get("bb_lower"); _mi_bbu = m_i.get("bb_upper")
                                _mi_NEAR = float(m_i.get("near_threshold_pct") or 2.0)
                                if _mi_b1 and _mi_nav > 0:
                                    def _mini_chip(target, is_buy):
                                        if not target: return ("—", GRAY_66)
                                        d = (_mi_nav - target) / target * 100
                                        if is_buy:
                                            if d <= 0:           return ("🟢", MD_GREEN_A400)
                                            elif d <= _mi_NEAR:  return ("⚠️", WARN_AMBER)
                                            else:                return ("▲",  GRAY_55)
                                        else:
                                            if d >= 0:           return ("🔔", MATERIAL_RED)
                                            elif d >= -_mi_NEAR: return ("⚠️", WARN_AMBER)
                                            else:                return ("▼",  GRAY_55)
                                    # 雙確認：σ 觸發 + 布林同向
                                    _double_buy  = (_mi_b1 and _mi_nav <= _mi_b1) and (_mi_bbd and _mi_nav <= _mi_bbd)
                                    _double_sell = (_mi_s1 and _mi_nav >= _mi_s1) and (_mi_bbu and _mi_nav >= _mi_bbu)
                                    _badge = ""
                                    if _double_buy:
                                        _badge = f"<span style='background:{BG_DARK_GREEN_3};color:{MD_GREEN_A400};border:1px solid {MD_GREEN_A400};padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;margin-left:6px'>🟢🟢 σ+布林 雙確認買</span>"
                                    elif _double_sell:
                                        _badge = f"<span style='background:{BG_DARK_RED_3};color:{MATERIAL_RED};border:1px solid {MATERIAL_RED};padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;margin-left:6px'>🔔🔔 σ+布林 雙確認賣</span>"
                                    # 6 個訊號方塊（從深買到深賣）
                                    _cells = ""
                                    for _v, _lbl, _is_buy in [
                                        (_mi_b3, "買3", True), (_mi_b2, "買2", True), (_mi_b1, "買1", True),
                                        (_mi_s1, "賣1", False),(_mi_s2, "賣2", False),(_mi_s3, "賣3", False),
                                    ]:
                                        _ch, _cc = _mini_chip(_v, _is_buy)
                                        _cells += (f"<div style='flex:1;text-align:center;padding:4px 2px;"
                                                   f"background:{GH_BG_PRIMARY};border-radius:6px;margin:0 2px'>"
                                                   f"<div style='font-size:9px;color:{TRAFFIC_NEUTRAL}'>{_lbl}</div>"
                                                   f"<div style='font-size:11px;font-weight:700;color:{GRAY_CC}'>{_v:.3f}</div>"
                                                   f"<div style='font-size:13px;color:{_cc}'>{_ch}</div></div>")
                                    st.markdown(
                                        f"<div style='background:{GH_BG_PRIMARY};border:1px solid {GH_BG_HOVER};border-radius:8px;padding:8px 12px;margin:2px 0 8px 0'>"
                                        f"<div style='display:flex;align-items:center;margin-bottom:5px'>"
                                        f"<span style='color:{TRAFFIC_NEUTRAL};font-size:10px'>📍 策略3 訊號</span>"
                                        f"<span style='background:{CHIP_BG_NEAR_BLACK};color:{_mi_pc};border:1px solid {_mi_pc};padding:1px 8px;"
                                        f"border-radius:10px;font-size:10px;font-weight:700;margin-left:6px'>{_mi_pl}</span>"
                                        f"{_badge}"
                                        f"<span style='color:{GRAY_55};font-size:10px;margin-left:auto'>NAV {_mi_nav:.4f}</span>"
                                        f"</div>"
                                        f"<div style='display:flex;align-items:stretch'>{_cells}</div>"
                                        f"</div>", unsafe_allow_html=True)

            # 核心/衛星目標設定
            st.divider()
            st.session_state.portfolio_core_pct = st.slider(
                "目標核心資產比例（%）", 50, 90,
                st.session_state.get("portfolio_core_pct",75), 5, key="slider_core_pct")

            # ── 真實收益長條圖（Core Protocol v2.0 Ch.4）────────────────
            # v18.38：分析視圖按 code 去重（同基金跨多保單只算一次），
            # 與 v18.34 戰情室 / v18.36 T5 重疊度矩陣的去重策略一致。
            _loaded_pf_raw = [f for f in pf if f.get("loaded") and not f.get("load_error")]
            _seen_rc: set = set()
            _loaded_pf: list = []
            for _f in _loaded_pf_raw:
                _c = str(_f.get("code", "") or "").strip().upper()
                if not _c or _c in _seen_rc:
                    continue
                _seen_rc.add(_c)
                _loaded_pf.append(_f)
            if _loaded_pf:
                st.divider()
                st.markdown("### 📊 真實收益 vs 配息率健康矩陣")
                st.caption("長條高度 < 紅虛線 → 含息報酬不足以支撐配息 → 吃本金警示")

                # v18.48 三層 fallback + is_real 旗標，正確區分「真 0%」與「資料不足」
                # v18.72: 加 _rc_src 追蹤每檔 1Y 來源，hover 顯示讓使用者一眼看出走哪條 fallback
                _rc_names, _rc_ret, _rc_div, _rc_real, _rc_src = [], [], [], [], []
                for _f in _loaded_pf:
                    _mj  = _f.get("moneydj_raw", {}) or {}
                    _m   = _f.get("metrics", {}) or {}
                    _pf2 = _mj.get("perf", {}) or {}
                    _name = (_f.get("name") or _f["code"])[:18]

                    # v18.65: 真 1Y 優先 — perf["1Y"] (wb01 官方 / local_calc 注入只有真 1Y)
                    # v18.134: 改用 compute_1y_total_return 共用 helper（與 Tab2 對齊）
                    # 修使用者反饋「同一基金兩 view 顯示不同 1Y 報酬」
                    from ui.helpers.macro_helpers import compute_1y_total_return
                    _ret_v, _src_label = compute_1y_total_return(_f)
                    _is_real = _ret_v is not None
                    _ret_window_days = None    # v18.65 短窗口提示（helper 內部已標明來源）

                    # v19.272 Phase 2 TOP 1.2:adr 走 SSOT _resolve_adr_with_fallback 3 層 chain
                    # 原 line 2042 + 2046-2067 inline 3 層 fallback 完全複製 SSOT 邏輯,收掉 22 LOC
                    from services.health.dividend import _resolve_adr_with_fallback
                    _div_v, _ = _resolve_adr_with_fallback(_f)
                    _div = round(float(_div_v), 2) if _div_v else 0.0
                    _rc_names.append(_name)
                    _rc_ret.append(round(_ret_v, 2) if _ret_v is not None else 0.0)
                    _rc_div.append(round(_div, 2))
                    _rc_real.append(_is_real)
                    _rc_src.append(_src_label if _is_real else "資料不足")

                if _rc_names:
                    # v19.402 §1:改走 SSOT dividend_safety(gap 判定 綠/黃/紅),取代原
                    # inline 1.2× coverage 門檻 → 與全站(Tab2 警示框 / 健診 3 表)一致,不再打架。
                    # 資料不足(_real=False)/ 無配息(_d≤0)→ dividend_safety 回 grey,誠實不誤判。
                    # L3→L2 呼叫(portfolio_service),同時修掉原 inline 分類的 §8.2 越權。
                    # (div_safety_check 即 dividend_safety,已於檔頭 module 級 import,不重複)
                    _LVL_COLOR = {"red": MATERIAL_RED, "yellow": MATERIAL_ORANGE,
                                  "green": MATERIAL_GREEN, "grey": TRAFFIC_NEUTRAL}
                    _rc_levels = []
                    for _r, _d, _real in zip(_rc_ret, _rc_div, _rc_real):
                        if not _real:
                            _rc_levels.append("grey")            # 1Y 資料不足 → 灰
                        else:
                            _rc_levels.append(
                                div_safety_check(_r, _d).get("alert_level", "grey"))
                    _rc_colors = [_LVL_COLOR.get(_lv, TRAFFIC_NEUTRAL) for _lv in _rc_levels]

                    fig_rc = go.Figure()
                    # v19.387 V1 §1:含息報酬長條用真實值 _rc_ret(移除 max(_r,0.5) 地板 ——
                    # 原本把吃本金的負報酬硬拉成正向長條、標籤卻標真負值,視覺與數據矛盾)。
                    # 負報酬向下、以 0 基準線(下方 add_hline)呈現;顏色 _rc_colors 已把吃本金標紅。
                    fig_rc.add_trace(go.Bar(
                        x=_rc_names, y=_rc_ret,
                        name="含息報酬率(1Y)%",
                        marker_color=_rc_colors,
                        text=[f"{v:.1f}%" for v in _rc_ret],
                        textposition="outside",
                        customdata=list(zip(_rc_ret, _rc_src)),
                        hovertemplate=("%{x}<br>含息報酬：%{customdata[0]:.2f}%"
                                       "<br>來源：%{customdata[1]}<extra></extra>")))
                    # 配息年化率紅色點線
                    if any(d > 0 for d in _rc_div):
                        fig_rc.add_trace(go.Scatter(
                            x=_rc_names, y=_rc_div,
                            name="配息年化率%",
                            mode="markers+lines",
                            line=dict(color=MATERIAL_RED, width=1.5, dash="dot"),
                            marker=dict(symbol="diamond", size=8, color=MATERIAL_RED),
                            hovertemplate="%{x}<br>配息率：%{y:.2f}%<extra></extra>"))
                    # 零基準線
                    fig_rc.add_hline(y=0, line_color=GRAY_55, line_width=1)
                    # ── 吃本金：背景色塊 + 標註（v19.402:紅框依 SSOT red 判定,gap>2%,
                    #    與長條顏色同源;gap 0~2% 為 SSOT yellow → 橙條但不標「吃本金」）──
                    _y_max = max(max(_rc_ret, default=10), max(_rc_div, default=10)) * 1.35
                    for _i, (_r, _d, _n, _real, _lv) in enumerate(zip(_rc_ret, _rc_div, _rc_names, _rc_real, _rc_levels)):
                        if _lv == "red":
                            fig_rc.add_vrect(
                                x0=_i - 0.45, x1=_i + 0.45,
                                fillcolor="rgba(244,67,54,0.08)",
                                line_color="rgba(244,67,54,0.4)", line_width=1,
                                layer="below")
                            fig_rc.add_annotation(
                                x=_n, y=_y_max,
                                text=f"⚠️ 吃本金<br>缺口 {_d-_r:.1f}%",
                                showarrow=False,
                                font=dict(color=MATERIAL_RED, size=11),
                                bgcolor="rgba(42,10,10,0.85)",
                                bordercolor=MATERIAL_RED, borderwidth=1,
                                borderpad=4)
                        elif not _real and _d > 0:
                            # 缺 1Y 資料 → 顯示「資料不足」灰色標註，不誤判吃本金
                            fig_rc.add_annotation(
                                x=_n, y=_y_max,
                                text="⬜ 1Y 資料不足<br>無法判定",
                                showarrow=False,
                                font=dict(color=GRAY_AA, size=10),
                                bgcolor="rgba(60,60,60,0.7)",
                                bordercolor=GRAY_66, borderwidth=1,
                                borderpad=4)
                    fig_rc.update_layout(
                        paper_bgcolor=STREAMLIT_BG, plot_bgcolor=GH_BG_CARD,
                        font_color=GH_FG_PRIMARY, height=360,
                        margin=dict(t=40, b=20, l=40, r=20),
                        legend=dict(orientation="h", font_size=10, y=1.08),
                        yaxis_title="報酬率 / 配息率 (%)",
                        yaxis=dict(range=[min(0, min(_rc_ret, default=0)) - 2, _y_max]),
                        bargap=0.35, hovermode="x unified")
                    st.plotly_chart(fig_rc, use_container_width=True)

                    # v18.163：下方 4 卡 KPI 已移除（與 Tab3 頂部 hero KPI 重複）；
                    # 詳細數字在 hero「💵 現金流安全」/「🔴 留校查看」見。

            # v19.180:💊 持倉健診總表(共用 SSOT 渲染,不重抓資料)
            # 來源:與「基金組合健診」Tab 完全同源(process_one_fund + _render_health_table),
            # 差異:per-fund 用 user 實際 invest_twd 為本金(若無則預設 100 萬 TWD)。
            # 目的:user 看完真實收益矩陣後,直接判斷「是否需要換標的 / 基金不健康」。
            #
            # ⚠️ WP-G(客戶 2026-08-31「各頁不重複渲染相同功能 …… ④ 健診改單行連結」):
            # **健診 3 表在本頁的渲染已移除**,只留一行指路 → ② 組合健診(健診的唯一主場)。
            # 上面四行歷史說明**保留不刪**:它們描述的「與 ② 同源、per-fund 用實際本金」
            # 這個設計仍然成立 —— 被拿掉的只有「在這一頁再畫一次」。
            #
            # ⛔ **計算不能跟著拔(本任務最大的風險,實測後的處置)**:下面 ThreadPool 算出的
            # `_health_results` → `_funds_extra`,是**同一區塊後面三個區塊的資料前置**
            # (🔄 輪動配對建議 / 📊 組合績效 / 🎯 效率前緣),而那三個**不在**本次授權範圍。
            # 故本次**只移除渲染、保留計算**;拔掉計算會讓那三區靜默變空(比沒有數字更危險,§1)。
            # 實測依據(AST,守衛見 tests/test_wpg_portfolio_health_link_20260831.py):
            # `_render_health_3tables` / `_render_health_table` 全鏈路**零 `st.session_state[...] =` 寫入**
            # (只有兩處 `.get("phase_info")` 讀進區域變數)→ 移除渲染不會讓後面的區塊讀到舊值或缺值。
            # ⚠️ 「零寫入」是本組單組 AST 掃描的結論,未經第二組驗證(§-2 規則 6)。
            if _loaded_pf:
                try:
                    st.divider()
                    # WP-G 單行指路。**灰色說明語意**(caption),不是 st.error / st.warning ——
                    # 「功能搬到別頁」不是系統故障(三態顏色分離)。分頁名走 story_nav SSOT
                    # (`_tab_label_t3`,本函式開頭已 import),**不得**寫死「💊 組合健診」。
                    st.caption(
                        f"💊 持倉健診(健康分析 / 配息相關 / 實際購買結果)請看「{_tab_label_t3('health')}」"
                        "分頁 —— 同一個功能不在兩頁重複渲染;本頁以下的輪動配對 / 組合績效 / "
                        "效率前緣仍用同一份健診資料計算。"
                    )
                    from services.fund_row import process_one_fund as _proc_health  # v19.413 下沉 L2
                    from concurrent.futures import (
                        ThreadPoolExecutor as _TPE_h,
                        as_completed as _ac_h,
                    )
                    # ── 稽核 N1-b：持倉健診改「首次自動 + 快取 + 重算鈕」───────────────
                    # 原本這整段沒有任何守門（唯一條件是 `if _loaded_pf:`），於是**每一次
                    # rerun** 都對全部持倉重跑 ThreadPool × process_one_fund（內含 FX / NAV
                    # 網路 I/O）。25 檔實測：rerun 起算 17 秒後 `WebSocket onclose`，畫面
                    # 永久凍結（2026-08-14 實機兩次重現）。
                    # 對策：以持倉指紋（代號 + 投入金額 + 序列長度）為 key 快取結果；
                    # 指紋不變就直接複用，變了才重算。另給一顆顯式「重新計算」。
                    # ⚠️ 指紋刻意不含時間 —— 「同一組持倉」在同一 session 內不該因為
                    # 你按了別的按鈕就重抓一次（那正是本 bug 的成因）。要最新值請按重算。
                    def _pf_health_fingerprint(_funds: list) -> str:
                        _parts = []
                        for _f in _funds:
                            _s = _f.get("series")
                            try:
                                _n = len(_s) if _s is not None else 0
                            except TypeError:
                                _n = 0
                            _parts.append(
                                f"{str(_f.get('code', '') or '').upper()}"
                                f"|{_f.get('invest_twd') or 0}|{_n}"
                            )
                        return ";".join(sorted(_parts))

                    _warn_gap_h = 2.0  # SSOT 對齊 fund_dividend_calculator.DEFAULT_WARN_GAP_PCT
                    # ⚠️ 模擬本金（2026-08-07 user 裁決的第 4 點）：未填 invest_twd 的基金
                    # 仍需要一個本金才算得出「每月配息 TWD / 實際購買結果」，故保留 100 萬
                    # 預設 —— 拿掉它會讓那幾檔的配息試算靜默變 0（比沒有數字更危險，§1）。
                    # 但它**僅供試算，不進配置比例**：下面逐檔記 `_principal_is_default`，
                    # 共用 render 會把這幾檔以 weight=0 擋在「核心/衛星屬性分布」分母外。
                    _DEFAULT_PRINC = 1_000_000.0
                    _health_results: list = [None] * len(_loaded_pf)
                    # index → 該檔的本金是不是模擬值（使用者從未填過金額）
                    _princ_is_sim: list = [False] * len(_loaded_pf)

                    # 稽核 N1-b：快取查核（詳見上方 `_pf_health_fingerprint` 的說明）
                    _pf_fp_h = _pf_health_fingerprint(_loaded_pf)
                    _cache_h = st.session_state.get("_pf_health_cache") or {}
                    _force_h = bool(st.session_state.pop("_pf_health_force", False))
                    _hit_h = (
                        (not _force_h)
                        and _cache_h.get("fp") == _pf_fp_h
                        and len(_cache_h.get("rows") or []) == len(_loaded_pf)
                    )
                    _c1_h, _c2_h = st.columns([4, 1])
                    if _c2_h.button("🔄 重新計算", key="pf_health_recalc",
                                    use_container_width=True,
                                    help="重新抓取每檔的即時 NAV / 匯率並重算健診。"
                                         "平常不需要按 —— 持倉沒變動時本區直接沿用本次 "
                                         "session 已算好的結果，避免每次操作都重跑一輪。"):
                        st.session_state["_pf_health_force"] = True
                        st.rerun()

                    if _hit_h:
                        _health_results = list(_cache_h["rows"])
                        _princ_is_sim = list(_cache_h["sim"])
                        _c1_h.caption(
                            f"✅ 沿用本次 session 已算好的健診結果（{len(_loaded_pf)} 檔，"
                            f"算於 {_cache_h.get('at', '—')}）。持倉金額或檔數變動會自動重算；"
                            "要抓最新淨值請按右邊「🔄 重新計算」。"
                        )
                    else:
                        _prog_h = st.progress(0.0, text="📥 持倉健診計算中…")
                        try:
                            with _TPE_h(max_workers=min(len(_loaded_pf), 4)) as _exh:
                                # v19.497:選股池自填名(比持倉抓取名更可能有真名,如 ALZF9)。
                                # §1:池讀失敗不擋健診(guard → 空 map)。EX-CRUD-1 允許 L3 直呼。
                                _pool_name_h: dict = {}
                                try:
                                    from repositories.pool_repository import list_pool as _lp_h
                                    _pool_name_h = {str(_e.code).upper(): (_e.name or "")
                                                    for _e in (_lp_h() or []) if _e.name}
                                except Exception as _e_ph:  # noqa: BLE001
                                    print(f"[tab3 持倉健診] 選股池名稱查詢略過:"
                                          f"{type(_e_ph).__name__}: {_e_ph}")
                                _futs_h = {}
                                for _ih, _fh in enumerate(_loaded_pf):
                                    _code_h = str(_fh.get("code", "") or "").strip().upper()
                                    _fd_h = _fh.get("moneydj_raw") or None
                                    _inv = _fh.get("invest_twd")
                                    try:
                                        _principal_h = float(_inv) if _inv else 0.0
                                    except (TypeError, ValueError):
                                        _principal_h = 0.0
                                    # 先判「有沒有真實金額」再補預設 —— 不用浮點 == 反推
                                    # 是否等於預設值（§4.3 禁止 `==` 比浮點；且真的填了
                                    # 100 萬的人不該被誤標成模擬本金）。
                                    _princ_is_sim[_ih] = _principal_h <= 0
                                    if _princ_is_sim[_ih]:
                                        _principal_h = _DEFAULT_PRINC
                                    # name_hint:池名優先(ALZF9 類真名只存在池),退持倉名(可能亦為代號)
                                    _nh_h = _pool_name_h.get(_code_h) or (_fh.get("name") or "")
                                    _futs_h[_exh.submit(
                                        _proc_health, _code_h, _principal_h,
                                        "", _warn_gap_h, _fd_h, _nh_h,   # v19.497 name_hint
                                    )] = _ih
                                _done_h = 0
                                _n_h = len(_loaded_pf)
                                for _futh in _ac_h(_futs_h):
                                    _ih2 = _futs_h[_futh]
                                    try:
                                        _health_results[_ih2] = _futh.result()
                                    except Exception as _eh:
                                        _health_results[_ih2] = {
                                            "code": _loaded_pf[_ih2].get("code", "?"),
                                            "ok": False,
                                            "error": f"{type(_eh).__name__}: {_eh}",
                                        }
                                    _done_h += 1
                                    _prog_h.progress(
                                        _done_h / _n_h,
                                        text=f"📥 已完成 {_done_h}/{_n_h} 檔…",
                                    )
                        finally:
                            _prog_h.empty()
                        # 只有真的算完才寫快取（失敗列本身也是有效結果，會帶 ok=False）
                        st.session_state["_pf_health_cache"] = {
                            "fp":   _pf_fp_h,
                            "rows": list(_health_results),
                            "sim":  list(_princ_is_sim),
                            # 走 ui.helpers.tw_time SSOT（檔頭已 import），不自建 tz
                            "at":   tw_now_str("%H:%M:%S"),
                        }
                    # v19.330:🧭 核心/衛星配置檢查已下沉共用 _render_health_3tables(兩 tab 齊顯示),
                    # 不再於此 inline(避免重複 + 只在 Tab3 出現)。
                    # 📌 2026-08-31 WP-G 狀態更新(上面兩行保留不刪 —— 狀態變更,不是漏刪):
                    # 本頁已不呼叫 `_render_health_3tables`,故「兩 tab 齊顯示」**現在只剩 ② 那一 tab**。
                    # v19.330 當時「不要 inline、走共用」的判斷仍然成立(它防的是長出第二份實作);
                    # 變的只是這一頁不再是那個共用渲染的 caller。
                    # ⚠️ 下面那句「共用 render 讀它決定分母」同理:`_principal_is_default` 旗標
                    # 仍然照接(產生端未動),但**本頁已無消費端** —— 它現在只服務 ② 那一頁。
                    # 刻意不拔:旗標寫在 row 上,而 row(`_ok_health`)仍是本頁三個下游區塊的輸入。
                    # 把「這檔用的是模擬本金」旗標接到 row 上（§1 揭露）：共用 render
                    # 讀它決定該檔要不要進配置比例分母。產生端算對了但沒接出去 =
                    # PROCESS.md §4 點名的最貴失效模式，故旗標與消費端同批交付。
                    for _idx_ps, _row_ps in enumerate(_health_results):
                        if isinstance(_row_ps, dict) and _princ_is_sim[_idx_ps]:
                            _row_ps["_principal_is_default"] = True
                    _ok_health = [r for r in _health_results if r is not None]
                    # v19.420 F-BM-3:持倉健診也帶「分析 extra 欄組」(σ/HWM/買賣點 / 上下檔捕捉率 /
                    # 操盤評分 / vs 大盤%)—— 先前 Tab3 未傳 funds_extra → 整組欄缺席(稽核 A2#1 抓到)。
                    # 用實際持倉重組 rich fund dict 傳入;show_screener 維持 False(不與健檢 Tab 撞 widget key)。
                    from ui.helpers.fund_grp_health._utils import _build_fund_dict
                    _funds_extra = [
                        _build_fund_dict(_r["_fund_raw"], _r["code"], _DEFAULT_PRINC)
                        for _r in _ok_health
                        if _r.get("ok") and _r.get("_fund_raw")
                    ]
                    # 🎯 換股顧問（2026-09-01 自 ② 搬入）吃的就是這一份 —— **不另抓**。
                    # 只是把把手交出去；真正的渲染在本函式最後的 `with _sec_switch:`
                    # （理由見函式開頭「🎯 換股顧問」那段註解）。
                    # ⚠️ 這一行**不得**改成 `list(_funds_extra)` 之類的複製：下游三個既有
                    #    區塊（輪動配對／組合績效／效率前緣）與換股顧問吃的必須是同一份
                    #    物件，複製一份就會出現「同一頁兩份持倉資料」的第二真相源。
                    _switch_funds = _funds_extra
                    # ── WP-G(2026-08-31):健診 3 表的渲染呼叫已移除 ─────────────────
                    # 原本這裡是 `_render_health_tbl(_ok_health, funds_extra=_funds_extra,
                    # source_tab="portfolio")`(即 `ui.tab_fund_grp_health._render_health_3tables`),
                    # 把 ② 的健診 3 表在本頁再畫一次。改為本區開頭那一行指路。
                    # 連帶移除:檔內原本的 `from ui.tab_fund_grp_health import _render_health_3tables`
                    # ——**本檔自此不再 import 健診渲染**(守衛用這一點當 fail-closed 斷言)。
                    #
                    # `_ok_health` / `_funds_extra` **刻意保留**:它們是下面三個區塊的輸入(見上方 ⛔)。
                    #
                    # 據實記錄的附帶行為變更(**不是**「零行為變更」):
                    #   (a) 3 表本身、以及只印在表內的那兩句 `source_tab` 指路措辭
                    #       (`_weight_basis_note` / `_core_satellite_verdict_caption`)一併不再出現;
                    #   (a2) **`render_fund_checkup`(基金體檢 PK)在本頁少了一份** ——
                    #       它原本被畫兩次,但**那兩次不是同一個東西**
                    #       (2026-08-31 稽核更正;初稿寫成「重複兩次」是不準確的宣稱):
                    #         · 本頁上方直接呼叫那次 → 傳 `st.session_state.portfolio_funds`,
                    #           用**使用者實際填的 `invest_twd`**(每檔不同);
                    #         · 被移除的 embed 那次 → 傳 `_build_fund_dict(..., _DEFAULT_PRINC)`,
                    #           **每檔硬寫 100 萬**的齊頭模擬基準。
                    #       `invest_twd` 會驅動可見輸出(原幣本金 / 月配息 / 年配息三欄 + 健診卡文案),
                    #       兩份的數字本來就不一樣。**移除的是「齊頭模擬基準」那一份。**
                    #       ⚠️ **但沒有能力消失**:同型的齊頭模擬版在 ② 仍在,而且 ② 的本金是
                    #       **使用者可設定的單一本金**(`_build_fund_dict(r, code, principal_twd)`),
                    #       比本頁硬寫死的 100 萬更好用。要齊頭比較 → 去 ②;
                    #       要看自己實際金額 → 本頁上方那一份仍在。
                    #   (b) 本 repo 自此**沒有任何 caller 傳 `source_tab="portfolio"`** →
                    #       `ui/tab_fund_grp_health._CS_WHERE_PORTFOLIO` 成為 production 不可達分支。
                    #       依 §-1.5.1c 判定 3(4) 它是「因本次改動才變成沒用的」,本該同批清掉;
                    #       **但本次授權明文禁止動 ② 端(`ui/tab_fund_grp_health.py`)一個字**,
                    #       故**登記不動**,連同該檔 L114 docstring「同時被健診 Tab 與 Tab3 embed
                    #       呼叫」這句已失真的敘述,一併列入 PR 描述的待辦。

                    # v19.418 — 🔄 輪動配對建議(持倉健診也顯示;user 2026-07-28 要求兩邊都要)。
                    # 重用 _funds_extra;widget key 用 'pf_rot_' 前綴避免與健檢 Tab 的 'rot_' 撞鍵。
                    try:
                        from ui.helpers.fund_grp_health.rotation import render_rotation_section
                        render_rotation_section(_funds_extra, key_prefix="pf_rot_")
                    except Exception as _e_rot:
                        # 整個輪動配對建議區塊（配對表 + σ 切點判定）消失。
                        system_error("輪動配對建議渲染失敗", _e_rot)

                    # v19.421 — 📊 組合績效;v19.424 — 🎯 效率前緣。重用 _funds_extra。
                    try:
                        from ui.helpers.portfolio_perf import (
                            render_efficient_frontier,
                            render_portfolio_performance,
                        )
                        render_portfolio_performance(_funds_extra)
                        render_efficient_frontier(_funds_extra)
                    except Exception as _e_pp:
                        # 年化報酬 / σ / Sharpe / 最大回撤 四個 KPI + 各檔貢獻表整組消失。
                        system_error("組合分析(績效/效率前緣)渲染失敗", _e_pp)
                except Exception as _e_ph:
                    # 這是持倉分頁最主要的那張大表,失敗＝整段診斷都不見。
                    system_error("持倉健診總表渲染失敗", _e_ph)

    with _sec_ledger:
        # ─── 以下為原 with tab3: 第二段 ───────────────
        # WP-D（線框 §03 ④）：版面順序改為「加入與管理基金 → 配置總覽 →
        # 持股重疊度診斷 → 帳本 → 費用與扣款 → AI 摘要 → Raw data」，頁內不再編號。
        # （v18.194 那套「①配置總覽→②加入/載入→③持倉戰情→④重疊診斷」的敘事已退場：
        #  它的畫面實際順序是 ④→①→②→③，正是線框點名要修的東西。）
        # T7 為自含函式、讀 session_state，置於所有 載入/加入 區塊之後 → 資料齊全、零依賴風險。
        # ── T7 帳務 + AI 深度組合建議 ── (v18.144 抽至 ui/tab3_t7_ledger.py)
        st.markdown("### 💼 持倉戰情（T7 帳本）")
        # 稽核 E12（2026-08-14）：T7 的表單驗證原本用 `st.stop()`（6 處），
        # 那會中止**整個 script run** —— 連排在 Tab3 之後的「📋 我的管理室」
        # 「📖 參考 / 診斷」兩個分頁都跟著空白。使用者只是忘了填金額，
        # 畫面卻像壞掉，多半會以為是連線問題而重整（重整後輸入全沒了）。
        # 改成攔自訂例外：中止範圍縮到 T7 這一段，其他分頁照常渲染。
        # `t7_abort()` 在拋之前已經顯示過 st.error，這裡只補一句「其餘分頁不受影響」。
        try:
            render_t7_section()
        except T7InputAbort:
            st.caption(
                "ℹ️ 上面那個錯誤只中止了「持倉戰情」這一段的試算 —— "
                "修正後重新送出即可，**其他分頁不受影響**。"
            )

        # v19.511:換扣款標的決策（依保單試算「保單管理費該從哪一檔基金扣、還是台幣現金扣」）。
        # 放 T7 帳本之後 —— 重用 T7 的成本基礎（t7_ledgers）+ 即時 nav/fx。try/except 不炸 Tab3。
        try:
            from ui.helpers.portfolio.fee_deduction import render_fee_deduction_section
            render_fee_deduction_section(st.session_state.get("portfolio_funds"))
        except Exception as _e_feeopt:  # noqa: BLE001 — 決策區任何例外收成提示，不影響其餘分頁
            # 原文案寫「略過」,讀起來像「這張保單不適用」;實際是整區算爆了。
            system_error("換扣款標的決策區渲染失敗", _e_feeopt)

    with _sec_ai:
        # ── T7 已移至 T5 之前（v18.194 故事化：持倉戰情 → 重疊診斷）──

        # v18.159：通用 AI 白話文總結 widget（4 視角 selectbox）
        _render_tab3_ai_summary(GEMINI_KEY)

    # ── 🎯 換股顧問（2026-09-01 自 ② 持倉體檢搬入）────────────────────────
    # **刻意排在所有 `with` 的最後**（顯示位置另由 `_sec_switch` 決定，見函式開頭
    # 那段註解）。放最後的理由是「一步都不動既有的執行順序」：本檔開頭那段長註解
    # 已列出至少四處「同一次 run 內先寫後讀」的 session_state 耦合，任何插隊都可能
    # 讓既有數字翻面，而本批**無權**改動計算。
    # ⚠️ `_switch_funds` 可能是空 list（一檔都沒載入 / 健診段沒跑到）——
    #    那時 `render_switch_advisor_section` 走空狀態三要素（鐵則 04），
    #    **不是**靜默消失。它在 ② 的時候也是這個形狀，只是文案指錯了地方。
    # ⚠️ try/except 沿用 ② 原本那一圈（連錯誤文案都一樣）：整區算爆時要看得見紅框，
    #    而不是靜靜少一塊（§1）。
    #
    # ⛔ **登記，不處置：本頁自此有兩組標籤重疊的績效 KPI**（2026-09-01 本批發現，
    #    **不是本批造成的重複實作，是搬家把兩者放到了同一頁**）：
    #      · `switch_advisor_section.render_portfolio_tracking()`（隨本次搬入）
    #        → 期間累積報酬 / **年化報酬** / **年化波動 σ** / **最大回撤**
    #      · `ui/helpers/portfolio_perf.render_portfolio_performance()`（④ 既有）
    #        → **年化報酬** / **年化波動 σ** / Sharpe / **最大回撤**
    #    **三個標籤字串完全相同**（已逐位元組核對，見下）。
    #
    #    ⚠️ **2026-09-02 更正：原本寫在這裡的「但演算法不同」是假的**
    #    （**有意識的更正，不是漏刪** · 日期 **2026-09-02** · 決策者：**實作組**，
    #    起因為總管指派複驗本批自己的宣稱）。舊表述加刪除線保留：
    #      ~~**三個標籤字串完全相同，但演算法不同**（前者是「固定目前權重 + 日再平衡」~~
    #      ~~重建走勢，後者走 `services.portfolio_performance.performance_metrics`）~~
    #      ~~→ 同一頁兩張卡、同一個標籤、可能不同的數字。~~
    #
    #    **為什麼是假的（實測，不是讀出來的印象）**：兩者的數學**收口到同一個 SSOT**。
    #      · `performance_metrics()` = `portfolio_returns()` → `metrics_from_return_series()`，
    #        然後把 `cagr_pct` **改名**成 `ann_return_pct` 出口；
    #        `ann_vol_pct` / `max_drawdown_pct` 是**原樣透傳**。
    #      · `reconstruct_trend()` 呼叫的是**同兩個函式**（`services/portfolio_tracking.py`
    #        檔頭自陳「數學全收口至 `portfolio_performance` SSOT」）。
    #      · 兩者 `rf_annual` 都取預設 0.0，`assumption` 字串**逐字相同**
    #        （`"fixed-weight daily-rebalance"`）；輸入也同一份（都是 `_funds_extra`），
    #        `_ccy_fx_for()` 與 `render_portfolio_performance()` 內嵌那段抓匯率的邏輯
    #        逐行等價（同 `BACKTEST_FX_FETCH_DAYS`、同 `fetch_usdtwd_frame`）。
    #    **舊表述錯在哪**：它拿「一個假設的描述」去對比「一個函式名」，
    #    而那個描述正是那個函式**自己**的假設 —— `performance_metrics` 的 docstring
    #    第一句就寫「假設固定權重、每日再平衡」。兩邊講的是同一件事。
    #
    #    **真正的差異只有一個，而且不是演算法，是顯示閘門**：
    #    `reconstruct_trend()` 有年化閘門 —— 共同交易日 < `PORTFOLIO_TREND_MIN_DAYS`（60）
    #    時把 `cagr_pct` / `ann_vol_pct` / `sharpe` / `calmar` 抹成 None。故：
    #      · n_days ≥ 60 → 三個重疊 KPI **數字完全相同**（同值、同 round、同格式化）。
    #      · n_days <  60 → 年化報酬與年化波動 σ：**上面那張顯示「—」、下面那張顯示數字**；
    #        最大回撤**永遠相同**（它不在被抹的鍵裡）。
    #
    #    **所以裁決項不但沒有消失，形狀還更糟，需要總管／客戶裁決的理由改成**：
    #      (a) 多數情況下這是**兩張數字一模一樣、標籤也一樣的卡**＝純冗餘；
    #      (b) 短序列時**同一頁、同一個標籤，一個「—」一個有數字**——
    #          使用者只會讀成「其中一張壞了」或「這兩個在講不同的東西」，
    #          兩種解讀都不對，正是 §1 最在意的「看起來不像壞掉」的形狀。
    #    ⚠️ **本更正只推翻「演算法不同」這一句，不宣稱這兩張卡該留該砍。**
    #    ⚠️ **本更正為實作組單組實測，未經第二組複驗**（`CLAUDE.md §-2` 規則 6）。
    #        複驗指令（repo 根執行）：比較同一份輸入餵給
    #        `performance_metrics()` 與 `reconstruct_trend()["metrics"]` 的三個重疊鍵。
    #    ⚠️ **本批刻意不處置**：要收斂就得砍掉其中一組或改標籤，那是
    #    「正式下架既有功能 / 改變客戶看到的規格」，屬 `CLAUDE.md §-1.5.1c v3 §03-2 ②`
    #    的**客戶 gate**，不是實作細節。**已在 PR 描述具名回報總管裁決。**
    #    ⛔ 在裁決之前，**不得**引用本段自行刪除任一組。
    with _sec_switch:
        try:
            from ui.helpers.fund_grp_health.switch_advisor_section import (
                render_switch_advisor_section,
            )
            render_switch_advisor_section(_switch_funds)
        except Exception as _e_sw:  # noqa: BLE001 — 整區失敗要有紅框，不得靜默
            system_error("換股顧問區塊渲染失敗", _e_sw)


def _render_tab3_ai_summary(gemini_key: str) -> None:
    """v18.159 Tab3 末端：4 視角 AI 白話文總結 widget。
    v18.160：snapshot 加入「配息現金/單位拆分」估算（從 v2 編輯 buf 撈 div_cash_pct）。"""
    from ui.helpers.ai_summary import render_ai_summary_widget  # noqa: PLC0415
    from repositories.policy_repository import estimate_dividend_split  # noqa: PLC0415
    pf = st.session_state.get("portfolio_funds", []) or []
    loaded = [f for f in pf if f.get("loaded") and not f.get("load_error")]
    if not loaded:
        return  # 組合空，不掛 widget

    # ── 稽核 N1-a：AI 快照記憶化 ─────────────────────────────────────────────
    # 本函式在呼叫 render_ai_summary_widget 之前，會先把整份 snapshot 算完：
    # build_mk_dataframe / compute_health_kpis / build_checkup_dataframe /
    # fetch_usdtwd_frame（**網路**）/ 逐檔 compute_max_drawdown / 相關性矩陣 /
    # 每個幣別一次 get_latest_fx（**網路**）。而它原本是**無條件執行**的 ——
    # 也就是說使用者根本還沒按「生成白話總體檢」，成本就已經付掉了，而且
    # **每一次 rerun 都付一次**（`st.tabs` 單次 run 會渲染全部分頁）。
    # 25 檔實測：rerun 起算 17 秒後 `WebSocket onclose`，畫面永久凍結。
    #
    # 對策：以「會影響 snapshot 內容的輸入」做指紋，同指紋直接複用上次結果。
    # 不改 render_ai_summary_widget 的介面（它被 Tab2 等共用，且它自己的
    # 磁碟快取仍需要完整 snapshot 當 key material）。
    _ai_fp_parts = []
    for _f_fp in loaded:
        _s_fp = _f_fp.get("series")
        try:
            _n_fp = len(_s_fp) if _s_fp is not None else 0
        except TypeError:
            _n_fp = 0
        _ai_fp_parts.append(
            f"{str(_f_fp.get('code', '') or '').upper()}"
            f"|{_f_fp.get('invest_twd') or 0}|{_n_fp}"
            f"|{str(_f_fp.get('currency', '') or '')}"
        )
    _news_fp = st.session_state.get("news_items", []) or []
    # 獨立稽核 額-2：以下兩項也會改變 snapshot 內容，不進指紋會讓 AI 拿舊快照講話：
    #  (1) 核心目標 %（下方 `_get_core_target_ai(st.session_state)` 讀它）
    #  (2) v2 編輯緩衝的 div_cash_pct / avg_nav / avg_fx / invest_twd
    #      （下方配息現金/單位拆分估算直接吃這幾欄）
    # 兩者都是純 session 記憶體讀取，零 I/O 成本。
    _core_tgt_fp = st.session_state.get("portfolio_core_pct")
    _v2_buf_fp = st.session_state.get("_v2_buf") or {}
    _v2_sig_parts: list[str] = []
    for _pid_fp in sorted(str(k) for k in _v2_buf_fp):
        _entry_fp = _v2_buf_fp.get(_pid_fp) or {}
        _df_fp = _entry_fp.get("fund") if isinstance(_entry_fp, dict) else None
        if _df_fp is None or getattr(_df_fp, "empty", True):
            continue
        for _col_fp in ("fund_code", "invest_twd", "div_cash_pct",
                        "avg_nav", "avg_fx"):
            if _col_fp in _df_fp.columns:
                _v2_sig_parts.append(f"{_pid_fp}.{_col_fp}={list(_df_fp[_col_fp])}")
    import hashlib as _hl_fp
    _v2_digest = _hl_fp.sha1(
        "|".join(_v2_sig_parts).encode("utf-8", "replace")
    ).hexdigest()[:12] if _v2_sig_parts else "-"
    _ai_fp = (";".join(sorted(_ai_fp_parts))
              + f"#news={len(_news_fp)}#core={_core_tgt_fp}#v2={_v2_digest}")
    _ai_cache_t3 = st.session_state.get("_tab3_ai_snap") or {}
    if _ai_cache_t3.get("fp") == _ai_fp:
        render_ai_summary_widget(
            tab_key="tab3",
            tab_label="組合戰情室",
            snapshot=_ai_cache_t3["snapshot"],
            sections=_ai_cache_t3["sections"],
            headlines=_ai_cache_t3["headlines"],
            gemini_api_key=gemini_key,
        )
        return

    # 核心/衛星走全站唯一真相（金額加權 + policy_tier 優先 + 目標吃 portfolio_core_pct）。
    # 原本這裡是「檔數比例 + 寫死 80%」，與畫面上的金額版兩套數字，AI 會照著錯的講。
    from ui.helpers.portfolio.allocation import (  # noqa: PLC0415
        get_core_target_pct as _get_core_target_ai,
        resolve_core_flag as _core_flag_ai,
        summarize_core_satellite as _sum_cs_ai,
    )
    n_total = len(loaded)
    _target_ai = _get_core_target_ai(st.session_state)
    _cs_ai = _sum_cs_ai(loaded, target_pct=_target_ai)
    n_core = _cs_ai["n_core"]
    n_sat = _cs_ai["n_sat"]
    core_pct = _cs_ai["core_pct"]
    _core_pct_txt = (f"{core_pct:.0f}%（金額加權）"
                     if core_pct is not None else "—（未填投入本金，無法算金額比例）")
    _sat_pct_txt = (f"{100 - core_pct:.0f}%" if core_pct is not None else "—")

    lines = [
        f"## 組合快照（{n_total} 檔）",
        f"- 核心 {n_core} 檔 · 佔資金 {_core_pct_txt}｜衛星 {n_sat} 檔 · 佔資金 {_sat_pct_txt}",
        f"- 使用者設定的核心目標：{_target_ai:.0f}%",
    ]
    _shown = 0
    for f in loaded[:5]:
        m = f.get("metrics") or {}
        name = f.get("name", "") or f.get("code", "") or "—"
        ret_1y = m.get("ret_1y_total") or m.get("ret_1y", "—")
        sharpe = m.get("sharpe", "—")
        std_1y = m.get("std_1y", "—")
        lines.append(
            f"- {name}（{'核心' if _core_flag_ai(f) else '衛星'}）："
            f"1Y 報酬 {ret_1y}%　|　Sharpe {sharpe}　|　波動 {std_1y}%"
        )
        _shown += 1
    if n_total > _shown:
        lines.append(f"- …（其餘 {n_total - _shown} 檔略）")

    # v18.214：吃「全章節」— 補組合健康度 KPI + 各檔 體檢結論 + 同類 PK 體檢表
    try:
        from ui.components.mk_dashboard import build_mk_dataframe as _build_mk  # noqa: PLC0415
        from ui.helpers.portfolio_health import compute_health_kpis as _kpis_fn  # noqa: PLC0415
        from ui.helpers.fund_checkup import build_checkup_dataframe as _chk_fn  # noqa: PLC0415
        _mk_df = _build_mk(loaded, bench_series=None)
        _kpis = _kpis_fn(loaded, _mk_df)
        _safe_tot = max(_kpis["n_funds"] - _kpis["n_na"], 0)
        lines.append(
            "- **🩺 組合健康度**："
            f"現金流安全 {_kpis['n_cash_ok']}/{_safe_tot} 檔｜吃本金 {_kpis['n_eat']} 檔"
            f"｜撿便宜 {_kpis['n_buy']} 檔｜留校查看 {_kpis['n_warn']} 檔"
            f"｜停利提醒 {_kpis['n_take']} 檔")
        if _mk_df is not None and not _mk_df.empty and "體檢結論" in _mk_df.columns:
            lines.append("- **各檔 體檢結論（前5）**：")
            for _, _r in _mk_df.head(5).iterrows():
                lines.append(f"  - {_r.get('代碼', '')} {_r.get('標的名稱', '')}："
                             f"{_r.get('體檢結論', '')}")
        _chk = _chk_fn(loaded)
        if _chk is not None and not _chk.empty:
            _v = _chk["體檢判定"]
            _good = _chk.loc[_v.str.startswith("🏆"), "標的名稱"].tolist()
            _lag = _chk.loc[_v.str.startswith("⚠️"), "標的名稱"].tolist()
            _na_n = int(_v.str.startswith("⬜").sum())
            lines.append(
                f"- **🏆 同類 PK 體檢**：優等生 {len(_good)} 檔"
                f"（{'、'.join(_good[:5]) or '—'}）｜汰弱候選 {len(_lag)} 檔"
                f"（{'、'.join(_lag[:5]) or '—'}）｜同類資料不足 {_na_n} 檔")
    except Exception:
        pass   # smoke-allow-pass — AI 快照加料失敗不阻斷主流程

    # v19.183 Bug5：組合加權回撤 + 歷年漲跌幅 + 相關性摘要 → 餵 AI 判斷組合回撤風險
    #   權重來自 sidebar invest_twd(缺則等權);全部走 services.portfolio_service 純函式。
    try:
        from services.portfolio_service import (  # noqa: PLC0415
            compute_portfolio_drawdown as _pdd_fn,
            compute_max_drawdown as _mdd_fn,
            calc_correlation_matrix as _corr_fn,
        )
        _fd_for_dd = [{"code": f.get("code"), "series": f.get("series"),
                       "currency": f.get("currency", "") or ""}
                      for f in loaded if f.get("series") is not None]
        # 權重 = sidebar 實際投入本金 invest_twd(缺則 0,函式內歸一;全缺 → 等權)
        _weights = {f.get("code"): (f.get("invest_twd", 0) or 0) for f in loaded}
        # v19.449 稽核 HIGH:抓 USDTWD 歷史 → 組合回撤各檔換 TWD basis(含匯率);
        # 缺匯率 → 美元檔被誠實排除(§1),不混幣別失真。
        _fx_dd = None
        try:
            from shared.signal_thresholds import BACKTEST_FX_FETCH_DAYS
            from services.hot_money_service import fetch_usdtwd_frame
            _fxdf_dd, _ = fetch_usdtwd_frame(BACKTEST_FX_FETCH_DAYS)
            if _fxdf_dd is not None and not _fxdf_dd.empty:
                _fx_dd = _fxdf_dd.set_index("date")["usdtwd"]
        except Exception:  # noqa: BLE001 — 匯率失敗 → 美元檔排除,不靜默造假
            _fx_dd = None
        if _fd_for_dd:
            _pdd = _pdd_fn(_fd_for_dd, weights=_weights, fx_series=_fx_dd)
            if _pdd.get("max_dd_pct") is not None:
                _dd_line = (
                    f"- **📉 組合加權最大回撤**：{_pdd['max_dd_pct']:.1f}%"
                    f"（{_pdd.get('peak_date', '—')} 高點 → {_pdd.get('trough_date', '—')} 谷底，"
                    f"納入 {_pdd['n_funds']} 檔 / {_pdd['n_obs']} 個共同交易日）")
                if _pdd.get("note"):
                    _dd_line += f"；註：{_pdd['note']}"
                lines.append(_dd_line)
                _yr = _pdd.get("yearly_returns") or {}
                if _yr:
                    _yr_txt = "、".join(f"{y}: {v:+.1f}%" for y, v in sorted(_yr.items()))
                    lines.append(f"- **📅 組合歷年漲跌幅**：{_yr_txt}")
            else:
                lines.append(
                    f"- **📉 組合回撤**：無法計算（{_pdd.get('note', '資料不足')}）")
            # 逐檔最大回撤(前 5,供 AI 對照哪檔拖累組合)
            _per_dd = []
            for f in loaded[:5]:
                if f.get("series") is None:
                    continue
                _d = _mdd_fn(f.get("series"))
                if _d.get("max_dd_pct") is not None:
                    _per_dd.append(f"{f.get('code')} {_d['max_dd_pct']:.1f}%")
            if _per_dd:
                lines.append(f"- **逐檔最大回撤（前5）**：{'、'.join(_per_dd)}")
        # 相關性摘要(影子基金對 → 分散不足警示,影響組合回撤集中度)
        _corr = _corr_fn(_fd_for_dd)
        if _corr and _corr.get("shadow_pairs"):
            _sp = _corr["shadow_pairs"][:3]
            _sp_txt = "、".join(f"{a}↔{b}({c:.2f})" for a, b, c in _sp)
            lines.append(
                f"- **🔗 高相關（影子基金，{_corr.get('freq', '')}）**：{_sp_txt}"
                f"；相關性高 → 分散不足，回撤時容易齊跌")
        elif _corr is not None:
            lines.append("- **🔗 持股/NAV 相關性**：無 ≥0.85 高相關對，分散度尚可")
    except Exception as _e_dd:
        import sys as _sys_dd  # noqa: PLC0415
        print(f"[tab3_ai] drawdown/corr snapshot fail: {type(_e_dd).__name__}: {_e_dd}",
              file=_sys_dd.stderr)

    # v18.160：配息現金/單位拆分估算（從 _v2_buf 撈 user 已設定的 div_cash_pct）
    # v18.276：抓即時 FX 給配息折算用（成本基礎仍 avg_fx）— user 反饋
    # 「將有換美元換台幣的匯率都改成即時匯率」
    _v2_buf = st.session_state.get("_v2_buf", {}) or {}
    _current_fx_t3_cache: dict[str, float] = {}
    def _get_current_fx_t3(_ccy: str) -> float:
        _ccy = (_ccy or "").strip().upper()
        if not _ccy or _ccy == "TWD":
            return 0.0
        if _ccy in _current_fx_t3_cache:
            return _current_fx_t3_cache[_ccy]
        try:
            from services.fund_service import get_latest_fx as _gf_t3
            import os as _os_t3
            _fk_t3 = ""
            try:
                _fk_t3 = st.secrets.get("FRED_API_KEY", "")
            except Exception:
                _fk_t3 = ""
            _fk_t3 = _fk_t3 or _os_t3.environ.get("FRED_API_KEY", "")
            _v_t3 = _gf_t3(f"{_ccy}TWD=X", fred_api_key=_fk_t3)
            _current_fx_t3_cache[_ccy] = float(_v_t3) if _v_t3 else 0.0
        except Exception:
            _current_fx_t3_cache[_ccy] = 0.0
        return _current_fx_t3_cache[_ccy]

    _div_lines: list[str] = []
    _total_cash, _total_reinv, _total_div = 0.0, 0.0, 0.0
    for _pid, _buf in _v2_buf.items():
        _fdf = _buf.get("fund") if isinstance(_buf, dict) else None
        if _fdf is None or _fdf.empty:
            continue
        for _, _r in _fdf.iterrows():
            _code = str(_r.get("fund_code", "") or "").strip()
            _inv = float(_r.get("invest_twd", 0) or 0)
            if not _code or _inv <= 0:
                continue
            # annual_div_rate 來自 portfolio_funds metrics（fund_code → metric）
            _adr = 0.0
            for _pf in loaded:
                if str(_pf.get("code", "") or "").upper() == _code.upper():
                    _m = _pf.get("metrics") or {}
                    _adr = float(_m.get("annual_div_rate") or 0)
                    break
            if _adr <= 0:
                continue   # 無實際配息率 → 跳過估算
            # v18.276：配息折算用即時 FX（成本基礎 avg_fx 不變）
            _ccy_est = ""
            for _pf in loaded:
                if str(_pf.get("code", "") or "").upper() == _code.upper():
                    _ccy_est = str(_pf.get("currency", "") or "")
                    break
            _est = estimate_dividend_split(
                invest_twd=_inv, annual_div_rate_pct=_adr,
                div_cash_pct=float(_r.get("div_cash_pct", 100) or 100),
                avg_nav=float(_r.get("avg_nav", 0) or 0),
                avg_fx=float(_r.get("avg_fx", 0) or 0),
                current_fx=_get_current_fx_t3(_ccy_est),
            )
            _total_div += _est["annual_div_twd"]
            _total_cash += _est["cash_twd"]
            _total_reinv += _est["reinvest_twd"]
            if len(_div_lines) < 6:
                _div_lines.append(
                    f"  - {_code}（{_pid}）：現金{int(_est['cash_pct'])}%/"
                    f"單位{int(_est['unit_pct'])}%　年配息估{int(_est['annual_div_twd']):,} TWD"
                    f"（現金{int(_est['cash_twd']):,} / 再投入{int(_est['reinvest_twd']):,}）"
                )
    if _total_div > 0:
        lines.append("- **📊 年配息現金/單位拆分估算（v18.160 新增）**：")
        lines.append(
            f"  - 總計：年配息估 {int(_total_div):,} TWD"
            f"｜現金 {int(_total_cash):,} ({_total_cash/_total_div*100:.0f}%)"
            f"｜再投入 {int(_total_reinv):,} ({_total_reinv/_total_div*100:.0f}%)"
        )
        lines.extend(_div_lines)

    snapshot = "\n".join(lines)
    # v18.196（Task3）：依組合「主資產類別」過濾既有新聞（不額外打網路）。
    # 統計 loaded 各檔推得的類別，取最多數；混合/無法判別 → macro（不過濾）。
    from repositories.news_repository import (  # noqa: PLC0415
        infer_asset_class as _infer_ac,
        filter_news_by_asset_class as _filter_news,
    )
    from collections import Counter as _Counter  # noqa: PLC0415
    _cls_votes = _Counter(
        _infer_ac(f"{f.get('name','')} {f.get('metrics',{}).get('category','')}")
        for f in loaded)
    _cls_votes.pop("macro", None)   # 多重資產不主導
    _dom_cls = _cls_votes.most_common(1)[0][0] if _cls_votes else "macro"
    _t3_news_all = st.session_state.get("news_items", []) or []
    headlines = [str(n.get("title", "") or n.get("headline", ""))
                 for n in _filter_news(_t3_news_all, _dom_cls)
                 if isinstance(n, dict)][:8]
    _sections_t3 = [
        "組合配置與健康度",
        "各檔基金體檢（戰情室）",
        "與同類比較（優等生 / 汰弱候選）",
        "配息現金流",
        "新聞時事影響",
    ]
    # 稽核 N1-a：算完才寫快取（見本函式開頭的說明）。下次同指紋直接走 early-return。
    st.session_state["_tab3_ai_snap"] = {
        "fp":        _ai_fp,
        "snapshot":  snapshot,
        "sections":  _sections_t3,
        "headlines": headlines,
    }
    render_ai_summary_widget(
        tab_key="tab3",
        tab_label="組合戰情室",
        snapshot=snapshot,
        sections=_sections_t3,
        headlines=headlines,
        gemini_api_key=gemini_key,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — 回測
