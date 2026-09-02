"""ui/tab_manage.py — 📋 我的管理室(v19.462)。一站集中:選股池 + 除息行事曆 + 補歷史淨值 + 通報。

**不新增儲存**:選股池存 Google Sheets `_fund_pool` 分頁,本頁只是它的**集中管理介面**,
全部重用既有 L1/L2/L0(§8.1 不重造):
- 📁 選股池:重用 `switch_advisor_section._render_pool_editor`(GS + 本地雙後端,永久保存)。
  v19.472:選股池併入「基金代號對照表」(填 ISIN 即解鎖晨星補淨值),且改存**獨立一本** Sheet
  (`POOL_SHEET_ID`,不共用持倉那本)。
- 🗓️ 除息行事曆 / 🗄️ 補歷史淨值(v19.472 移除 FundClear + TDCC 抓取,只留手動 CSV 上傳)。
- 🔔 通報:LINE 設定狀態 + 預覽本週訊息 + 測試發送 + 設定指引。**每週自動送仍是 NAS 排程**,
  本頁只負責看/測(Streamlit 不背景跑,§1 不假裝能排程)。

v19.462(user 2026-08-17):移除「投資組合(持倉)一覽」—— 帳本(配置&帳本 Tab)已有,且流程圖
把 Portfolio 歸「配置&帳本」,管理室專責 Watchlist/選股池 + 補歷史淨值(連帶退 `_sec_portfolio`
/ `_save_policy` / `_delete_policy` / `_prepare_write_df` / `_run_fix_and_shrink` 一組寫回 CRUD)。

資料永久性:寫的是 Google Sheets 不是 App 本機(Streamlit Cloud FS ephemeral)→ 關掉重開都在,
每次開啟只是「從雲端讀回已存的資料」,不是重新輸入。
"""
from __future__ import annotations

import datetime as _dt

import streamlit as st

from ui.helpers.render_state import system_error


def _today_tw() -> str:
    return _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).date().isoformat()


def _friendly(title, e, level="warning"):
    try:
        from ui.helpers.session import friendly_error
        friendly_error(title, e, level=level)
    except Exception:  # noqa: BLE001
        st.caption(f"⬜ {title}:[{type(e).__name__}] {str(e)[:120]}")


# ───────────────────────── 政策 Sheet client / id ─────────────────────────

def _policy_client_and_sheet():
    """(gspread client, sheet_id) 供投資組合讀寫。用 user OAuth(本人擁有該 Sheet,和 Tab④ 編輯同法)。

    未登入 / 無 sheet_id → (None, reason) 讓呼叫端誠實顯示,不崩(§1)。
    """
    try:
        from ui.helpers.oauth_state import (
            _get_oauth_client,
            _sheet_id_secret,
            refresh_oauth_state,
        )
        try:
            refresh_oauth_state()
        except Exception as _re:  # noqa: BLE001 — token 刷新失敗不擋(下方 _client None 會誠實提示),但留痕(§1)
            import sys as _sys
            print(f"[tab_manage] refresh_oauth_state 失敗(續用現有 token):"
                  f"{type(_re).__name__}: {_re}", file=_sys.stderr)
        _client = _get_oauth_client()
    except Exception as _e:  # noqa: BLE001
        return None, f"OAuth client 取得失敗:{type(_e).__name__}"
    if _client is None:
        return None, "尚未用 Google 登入(請至左側 sidebar 🔐 登入)才能讀取/編輯投資組合。"
    _sid = (st.session_state.get("policy_sheet_id") or _sheet_id_secret or "").strip()
    if not _sid:
        return None, "找不到政策 Sheet ID(請先在 Tab④ 選帳本,或設 POLICY_SHEET_ID secret)。"
    return _client, _sid


# ───────────────────────── ① 選股池 ─────────────────────────

def _sec_pool():
    st.markdown("### 📁 選股池(候選基金)")
    st.caption("**這不是你的持倉** —— 是你**還沒買、考慮想換進來**的候選名單,換股顧問拿它跟你的持倉比較。"
               "v19.472:存進**獨立一本 Sheet(`POOL_SHEET_ID`,與持倉不同本)的 `_fund_pool` 分頁**"
               "(可直接在 Google Sheet 看/編)。抓不到淨值的檔在下方**填 ISIN**,系統就走晨星自動補淨值"
               "(併入原「基金代號對照表」,兩表共用一張)。"
               "⚠️ 需把 Service Account 信箱加為該 Sheet 編輯者才會雲端同步,否則暫存本機。")

    # v19.461:移除「曾經查過的基金清單」自動記錄 + 匯入(user 2026-08-17:介面不友善 → 全拿掉)。
    # 選股池本身即「觀察清單 watchlist」,直接用下方編輯器加/刪代號。
    try:
        from ui.helpers.fund_grp_health.switch_advisor_section import _render_pool_editor
        _render_pool_editor()
    except Exception as _e:  # noqa: BLE001
        _friendly("選股池管理載入失敗", _e)


# ───────────────────────── ③ 通報 ─────────────────────────

def _sec_notify():
    st.markdown("### 🔔 換股通報(LINE)")
    # ── 稽核 E10：燈號假陰性 ────────────────────────────────────────────────
    # 原本只檢查 `LINE_CHANNEL_TOKEN`，但 `infra/line_push.py:58` 明確支援別名
    # `LINE_CHANNEL_ACCESS_TOKEN`（該檔 :10 註明「GitHub secret 常用後者」）。
    # 只設別名時：燈號顯示 🔴「尚未設定」，而且下方 `if _ok and st.button(...)`
    # 會**短路 → 測試按鈕整顆不渲染** —— 功能完好卻既說壞掉、又不給你測。
    # 改用與 push_text 完全相同的別名解析，避免兩邊各判各的。
    from infra.line_push import _resolve as _line_resolve
    _line_token = (_line_resolve("LINE_CHANNEL_TOKEN", None)
                   or _line_resolve("LINE_CHANNEL_ACCESS_TOKEN", None))
    _ok = bool(_line_token) and bool(_line_resolve("LINE_USER_ID", None))
    st.caption(("🟢 LINE 憑證已設定" if _ok else
                "🔴 LINE 尚未設定(App secrets 缺 LINE_CHANNEL_TOKEN / LINE_USER_ID → 只能預覽,不能測試發送)")
               + "　·　⚠️ **每週自動推播是你 NAS 的排程在跑**,本頁只負責預覽 + 測試發送。")

    _funds = st.session_state.get("portfolio_funds") or []
    # 稽核 E9：原本只看 `loaded` —— 但 `ui/helpers/portfolio/load.py:219-221` 會
    # 對抓取失敗的基金寫入 `{"loaded": True, "load_error": "..."}`，所以抓失敗的
    # 檔一樣會被算進通報觀察集合。全 repo 其他 8 個消費端都用
    # `loaded and not load_error`（含本檔 `_divcal_gather_items` 的「稽核 H2」），
    # **這裡是唯一漏網**。
    _loaded = [f for f in _funds if f.get("loaded") and not f.get("load_error")]

    if st.button("👁️ 預覽本週會送的通報訊息", use_container_width=True, key="manage_notify_preview"):
        _preview_notify(_loaded)

    if _ok and st.button("✉️ 測試發送一則到我的 LINE", use_container_width=True, key="manage_notify_test"):
        _test_send()

    with st.expander("📖 每週自動通報 — NAS 設定步驟"):
        st.markdown(
            "1. **LINE bot**:LINE Developers 建 Messaging API channel → 拿 channel access token + 你的 userId + 加 bot 好友。\n"
            "2. **NAS 環境變數**:`google_service_account` / `macro_weights_sheet_id` / `LINE_CHANNEL_TOKEN` / `LINE_USER_ID`。\n"
            "3. **先驗證(不會真送)**:`python scripts/weekly_switch_notify.py --dry-run`。\n"
            "4. **排程(每週一傍晚)**:`30 18 * * 1 cd /path/to/repo && python scripts/weekly_switch_notify.py`。\n\n"
            "完整版見 `docs/WEEKLY_SWITCH_NOTIFY_SETUP.md`。⚠️ LINE Notify 已於 2025/03 停用,本功能走 Messaging API。"
        )


def _preview_notify(funds):
    if not funds:
        # 指路一律走 SSOT：舊字面值「Tab④/組合健診」名字與站號**都**錯
        # （健診是 ②、不是 ④；且 2026-09-01 已改名「持倉體檢」）。
        from ui.helpers.story_nav import where_to_find as _wtf
        st.info(f"目前沒有『已載入』的持倉基金 → 先到 {_wtf('health')} 載入基金,再回來預覽。")
        return
    try:
        from repositories.pool_repository import list_pool
        from services.switch_advisor import advise_switches
        from services.switch_notify import build_notification
        from ui.helpers.fund_grp_health.switch_advisor_section import (
            _fx_label,
            _macro_composite,
            _pool_oauth_client,
            _pool_rows,
            _rows_with_nav,
            _underperf_by_code,
        )
        pool = list_pool(oauth_client=_pool_oauth_client())   # 手機 OAuth-only:帶 client 才讀得到雲端池
        # 稽核 E8(d)：key 未正規化 → 選股池代碼若為小寫就對不到 type_override /
        # category。`scripts/weekly_switch_notify.py:296` 早就 `.upper()` 了
        # （且標了「稽核修」），本頁保留著同一個已修過的 bug。
        _pbc = {str(e.code or "").strip().upper(): e for e in pool}
        with st.spinner("計算本週通報預覽…"):
            _held = _rows_with_nav(funds, _pbc)
            _cands = _pool_rows(pool, funds)
            _res = advise_switches(_held, _cands, fx_label=_fx_label(),
                                   macro_composite=_macro_composite(),
                                   underperformance_by_code=_underperf_by_code(funds))
            _note = build_notification(_res, as_of=_today_tw(),
                                       skipped=max(0, len(funds) - len(_held)))
        st.text_area("本週會送的訊息(預覽,不會真的送)", _note["message"], height=260)
        # ── 稽核 E8：原文案宣稱「和 NAS 週報同一套邏輯」，實測 6 項差異 ──────────
        # (a) 觀察集合：本頁只看 session 已載入持倉；NAS 讀 Sheet 持倉 ∪
        #     WATCH_CSV_URL 追蹤清單（weekly_switch_notify.py:298-306）
        # (b) macro composite：本頁傳 `_macro_composite()`；NAS 預設 None
        #     （:328，除非 --with-macro）→ switch_advisor.py:225-226 讓
        #     **成長型賣出訊號在 NAS 端結構性永不觸發**。本頁說「該賣」，NAS 不送。
        # (c) source_by_code：本頁不傳 → 預覽看不到 [持倉]/[觀察] 標籤
        # (d) pool key 大小寫（已於上方修）
        # (e) skipped：本頁 `max(0, len(funds)-len(_held))`，而 `_assemble_rows`
        #     沒有任何 continue → **恆為 0**（不是低報，是該欄位完全失效）
        # (f) rows 組法：本頁走 rotation._assemble_rows；NAS :157-188 本地重製
        # 治本是把 NAS 那三個函式抽成 streamlit-free 的 services/switch_pipeline.py
        # 兩邊共用（已列 P0 待辦）；在那之前，先誠實揭露差異，不再宣稱同一套。
        st.caption(
            f"本週會通報 **{_note['n_actionable']}** 檔"
            f"（should_notify={_note['should_notify']}）。沒建議時 NAS 週報不會吵你。"
        )
        st.info(
            "ℹ️ **這是以「你目前已載入的持倉」試算的預覽，可能與 NAS 實際送出的不同**：\n\n"
            "- NAS 週報的標的是 **Google Sheet 持倉 ∪ 追蹤清單（`WATCH_CSV_URL`）**，"
            "本頁只涵蓋已載入的持倉\n"
            "- NAS 預設**不帶總經 composite**，所以「成長型看衰 → 賣出」這類建議"
            "只會出現在本頁預覽、**不會被送出**\n\n"
            "要看 NAS 真正會送什麼，請在 NAS 上跑 "
            "`python scripts/weekly_switch_notify.py --dry-run`。"
        )
    except Exception as _e:  # noqa: BLE001
        _friendly("預覽通報失敗", _e, level="error")


def _test_send():
    from infra.line_push import LinePushError, push_text   # import 移出 try:否則 import 失敗會
    try:                                                    # 讓 except LinePushError 變 NameError(稽核 FINDING 3)
        _r = push_text(f"✅ 基金戰情室測試（{_today_tw()}）：你的 LINE 通報設定正確,週報會送到這裡。",
                       dry_run=False)
        if _r.get("sent"):
            st.success("已發送測試訊息到你的 LINE 🎉 收到就代表設定成功。")
        else:
            st.warning(f"未發送:{_r.get('reason')}")
    except LinePushError as _e:  # noqa: BLE001
        st.error(f"發送失敗:{_e}")
    except Exception as _e:  # noqa: BLE001
        _friendly("測試發送失敗", _e, level="error")


# ───────────────────────── 入口 ─────────────────────────

def _divcal_gather_items():
    """蒐集月曆基金:選股池(現抓配息)∪ 已載入持倉(dividends 現成),依代號去重。

    選股池項目不帶配息 → 逐檔 auto_fetch_moneydj 現抓(帶進度);持倉直接用既有 dividends。
    回 (items, n_pool, n_held)。
    """
    from services.dividend_calendar import detect_house
    from services.moneydj_fetcher import auto_fetch_moneydj

    _funds = st.session_state.get("portfolio_funds") or []
    _held = [f for f in _funds if f.get("loaded") and not f.get("load_error")]   # 稽核 H2
    try:
        from repositories.pool_repository import list_pool
        from ui.helpers.fund_grp_health.switch_advisor_section import _pool_oauth_client
        _pool = list_pool(oauth_client=_pool_oauth_client())   # 手機 OAuth-only:帶 client 才讀得到雲端池
    except Exception:  # noqa: BLE001
        _pool = []

    items, seen = [], set()
    for f in _held:                                  # 持倉:dividends 現成
        _c = str(f.get("code") or "").strip().upper()
        if not _c or _c in seen:
            continue
        seen.add(_c)
        items.append({"code": _c, "name": f.get("name") or _c,
                      "house": detect_house(f.get("name") or ""),
                      "dividends": f.get("dividends") or (f.get("moneydj_raw") or {}).get("dividends")})

    _pool_new = [e for e in _pool if str(e.code or "").strip().upper() not in seen]
    if _pool_new:
        _prog = st.progress(0.0, text="抓選股池各檔配息中…")
        for _i, e in enumerate(_pool_new):
            _c = str(e.code or "").strip().upper()
            try:
                fd = auto_fetch_moneydj(_c) or {}
                _name = fd.get("fund_name") or e.name or _c
                items.append({"code": _c, "name": _name, "house": detect_house(_name),
                              "dividends": fd.get("dividends")})
            except Exception:  # noqa: BLE001 — 單檔抓失敗略過,不擋整批
                items.append({"code": _c, "name": e.name or _c, "house": "", "dividends": None})
            _prog.progress((_i + 1) / len(_pool_new), text=f"抓配息 {_i + 1}/{len(_pool_new)}…")
        _prog.empty()
    return items, len(_pool), len(_held)


def _sec_dividend_calendar():
    """🗓️ 除息行事曆:選股池(現抓配息)∪ 已載入持倉 → 本月除息/配息推估月曆(嵌入 HTML)。"""
    import datetime as _dt

    st.markdown("### 🗓️ 除息行事曆")
    # v19.539 B-3 補完:原句尾是「加減標的 → 下月自動更新」——**在 App 路徑是假的**。
    # 下面那個 `build_month_calendar` 呼叫的目標月就是 `_now.year` / `_now.month`(= 本月),
    # 而且是按鈕按下去當場現算,新加的標的**這一秒**就會出現在月曆上,不必等下個月。
    # ⚠️ 這段註解**刻意不寫成 `函式名(...)` 的形狀** —— `tests/test_dividend_anchor_v19527.py::
    #    test_production_callers_pass_the_real_day_down` 用正則抓本檔**第一個**該形狀的字串
    #    來驗 `ref_day=` 有沒有傳下去,註解寫成呼叫樣會被它當成真正的呼叫點(實測會紅)。
    # 這句話與 `ui/helpers/dividend_calendar_render.py` 的副標、
    # `docs/DIVIDEND_CALENDAR_SETUP.md` 開頭是同一句話的三個出口,要改就三處一起改
    # (守衛:tests/test_dividend_calendar_render.py::test_no_surface_promises_a_delayed_update)。
    st.caption("你的基金**本月除息 / 配息日推估**(選股池 + 已載入持倉)。用過往配息節奏推算,"
               "**非官方公告**;累積型不配息的自動不顯示,加減標的 → 重按產生按鈕即納入。")

    if st.button("🗓️ 抓選股池標的 → 產生本月除息月曆", use_container_width=True, key="divcal_gen"):
        try:
            _items, _np, _nh = _divcal_gather_items()
            if not _items:
                from ui.helpers.story_nav import where_to_find as _wtf2
                st.info("選股池與已載入持倉都是空的 → 先到上面『選股池』加標的,"
                        f"或到 {_wtf2('health')} 載入基金。")
                st.session_state.pop("_divcal_items", None)
            else:
                st.session_state["_divcal_items"] = _items
                st.session_state["_divcal_src"] = f"選股池 {_np} 檔 + 持倉 {_nh} 檔"
        except Exception as _e:  # noqa: BLE001
            _friendly("抓取配息失敗", _e, level="error")

    _items = st.session_state.get("_divcal_items")
    if not _items:
        st.caption("按上面按鈕：會現抓選股池各檔配息史(約數秒~數十秒),再產生本月月曆。")
        return

    _now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8)))
    try:
        import streamlit.components.v1 as _components

        from services.dividend_calendar import build_month_calendar, is_all_unpredictable
        from ui.helpers.dividend_calendar_render import render_month_calendar_html
        # ref_day = 今天幾號(v19.532 bug 4):不傳的話 L2 會退回「月中 15 號」估陳舊度 ——
        # App 在月初開會被多算 14 天、月底開會被少算 15 天,月配基金在門檻附近會忽有忽無。
        _cal = build_month_calendar(_items, _now.year, _now.month, ref_day=_now.day)
        _html = render_month_calendar_html(_cal)
        _components.html(_html, height=900, scrolling=True)
        _c = _cal["counts"]
        _src = f"來源:{st.session_state.get('_divcal_src', '')}　·　"
        if is_all_unpredictable(_cal):
            # v19.534 裁示 3:全推不出時原本寫「本月推估除息 0 檔｜N 檔無法推估」——
            # 「0 檔」讀起來是**這個月沒配息**,與 §15.4 圖上剛講完的「是推不出,不是沒配息」
            # 自相矛盾(同一畫面兩個口徑)。§1:不讓「算不出來」看起來像「沒事」。
            st.caption(_src + f"本月 {_c.get('unpredictable', 0)} 檔**都推不出除息日** —— "
                              "是推不出,不是沒配息(見上方待確認清單)"
                       + (f"｜{_c['excluded']} 檔累積型/無配息" if _c["excluded"] else ""))
        else:
            st.caption(_src + f"本月推估除息 {_c['events']} 檔"
                       + (f"｜{_c['excluded']} 檔累積型/無配息" if _c["excluded"] else "")
                       + (f"｜{_c['unpredictable']} 檔推不出日期(非沒配息)"
                          if _c.get("unpredictable") else ""))
        st.download_button("⬇️ 下載本月月曆 HTML", _html,
                           file_name=f"除息行事曆_{_now.year}{_now.month:02d}.html",
                           mime="text/html", use_container_width=True, key="divcal_dl")
    except Exception as _e:  # noqa: BLE001
        _friendly("產生除息月曆失敗", _e, level="error")


def _sec_nav_backfill_auto() -> None:
    """① 一鍵自動補全部缺淨值(持倉 ∪ 選股池)→ 本地 cache + 雲端 nav_history(永久)。

    代號集合 = 已載入持倉(loaded 且無 load_error)∪ 選股池,去重(§2.1 upper)。
    抓取 + 寫入委派 L2 `services.nav_history_store.backfill_to_gs`(§8.2 L3 只編排 + 渲染)。
    §1:抓不到的檔逐一列出引導改用下方 CSV;雲端未啟用時明講「只存本機、重啟會清」。
    """
    with st.expander("🔄 一鍵自動補全部缺淨值（持倉 ∪ 選股池 → 存進雲端 Sheet）", expanded=False):
        st.caption("系統用 MoneyDJ + 你在選股池填的 **ISIN(→晨星,晨星若有收錄可拉多年)** 自動抓每一檔"
                   "歷史淨值,寫進雲端 nav_history(永久、重開不丟)。**保單平台專屬基金晨星多半沒收錄**,"
                   "那幾檔會只抓到短窗 → 結果表會誠實標「來源＋跨度」,再用下方 CSV 手動補足 5 年。")

        # 蒐集代號:已載入持倉 ∪ 選股池(去重 upper)
        _funds = st.session_state.get("portfolio_funds") or []
        _held = [str(f.get("code") or "").strip().upper()
                 for f in _funds if f.get("loaded") and not f.get("load_error")]
        try:
            from repositories.pool_repository import list_pool
            from ui.helpers.fund_grp_health.switch_advisor_section import _pool_oauth_client
            _pool = [str(e.code or "").strip().upper()
                     for e in list_pool(oauth_client=_pool_oauth_client())]
        except Exception as _e:  # noqa: BLE001
            _pool = []
            # 2026-08-28 顏色批次二之一：換股顧問呼叫同一支選股池讀取 API 失敗時已是 🔴，
            # 這裡還是灰字。而且後果更重 —— `_pool = []` 之後，下方「一鍵自動補全部
            # 缺淨值」的代號集合會**整個選股池不見**，畫面卻只說「讀取失敗」，
            # 使用者會以為補完了（§1：錯誤的數字比沒有數字更危險）。
            system_error("選股池讀取失敗", _e,
                         hint="下方補淨值只會涵蓋**已載入持倉**,選股池那幾檔這次不會被補到。")
        _all, _seen = [], set()
        for _c in _held + _pool:
            if _c and _c not in _seen:
                _seen.add(_c)
                _all.append(_c)

        # v19.509:SA 缺(手機無 Service Account)但已 Google 登入 → 用登入者身分寫雲端(永久)。
        # 誠實顯示落點三態(service_account / oauth / local),§1 不讓 user 誤以為在永久保存。
        _oauth = None
        try:
            from ui.helpers.io.oauth_state import _get_oauth_client
            _oauth = _get_oauth_client()
        except Exception:  # noqa: BLE001 — 未登入 / 建置失敗 → None(退 SA / 本機)
            _oauth = None
        from services.nav_history_gs import backend_status as _nh_backend
        _backend = _nh_backend(_oauth)
        if _backend == "service_account":
            st.caption("☁️ 雲端 nav_history 已啟用（Service Account）→ 補的淨值永久保存、重開不丟。")
        elif _backend == "oauth":
            st.caption("☁️ 將用你的 **Google 登入**身分寫進雲端 nav_history（永久保存、重開不丟）。")
        else:
            st.warning("⬜ 雲端 nav_history 未啟用:**沒有 Service Account、也還沒 Google 登入** → 現在"
                       "補的淨值**只會存本機、容器重啟就清空**。先完成 **Google 登入**(或設 Service "
                       "Account)再按,才會永久保存。")
        _n_held = len(set(_held))
        _n_pool_only = len(set(_pool) - set(_held))
        st.caption(f"將補抓 **{len(_all)}** 檔(持倉 {_n_held} + 選股池 {_n_pool_only},已去重)。")

        if not _all:
            st.info("目前沒有可補的基金 —— 先載入持倉,或在上方選股池加入候選(填代號 + ISIN)。")
            return
        if not st.button("🔄 開始補抓全部缺淨值", use_container_width=True, key="_nh_backfill_all"):
            return

        from services.nav_history_store import backfill_to_gs
        _prog = st.progress(0.0, text="準備補抓…")

        def _cb(i, n, code):
            _pct = min(i / n, 1.0) if n else 1.0
            _prog.progress(_pct, text=(f"補抓中 {i}/{n}:{code}" if code else "寫入雲端 nav_history…"))

        with st.spinner("抓歷史淨值 + 寫入雲端 nav_history…(連外抓取,檔數多會慢)"):
            _res = backfill_to_gs(_all, progress_cb=_cb, oauth_client=_oauth)
        _prog.empty()

        import pandas as pd

        def _src_zh(r):
            _s = r.get("source") or ""
            if _s.startswith("yahoo"):
                return "🌐 Yahoo(secId)"
            if _s.startswith("morningstar"):
                return "🌐 晨星(ISIN)"
            if _s.startswith("cnyes"):
                return "🌐 CnYES(ISIN)"
            if _s == "moneydj":
                return "📄 MoneyDJ"
            return "—"

        def _span_zh(r):
            _d = r.get("span_days") or 0
            if not _d:
                return ""
            _y = _d / 365.25
            return f"（約 {_y:.1f} 年）" if _y >= 1 else f"（約 {_d} 天）"

        def _result_zh(r):
            """結果欄。2026-08-28 稽核修正:**被 Gate 0 擋下 ≠ 抓不到**。

            舊版一律印 `⬜ {error}` —— 但被擋下的檔**抓得好好的**(`fetched` 是實數),
            是資料完整性偵測把它擋下來的。依 `ui/helpers/render_state.py` 五態:
            「還沒載入/還沒設定」才是 ⬜;**偵測到的真失敗是 🔴**。
            """
            if r["error"] is None and r["fetched"]:
                return f"✅ {r['fetched']} 筆{_span_zh(r)}"
            if r.get("blocked"):
                return (f"🔴 已抓到 {r['fetched']} 筆,但**與既有雲端歷史對不上 → 擋下未寫入**"
                        f":{r['error']}")
            return f"⬜ {r['error']}"

        _rows = [{
            "代號": r["code"],
            "結果": _result_zh(r),
            "來源": _src_zh(r) if (r["error"] is None and r["fetched"]) else "—",
            # 2026-08-28 稽核修正:條件從 `if r["date_min"]` 改為「**沒有 error 才顯示**」。
            # 舊版被 Gate 0 擋下的檔照樣秀出起迄 —— 而那是**被拒絕的那條序列**的區間,
            # 使用者會以為那段歷史已經在雲端了（§1:錯誤的數字比沒有數字更危險）。
            "淨值起迄": (f"{r['date_min']} ~ {r['date_max']}"
                         if (r["error"] is None and r["date_min"]) else "—"),
        } for r in _res["results"]]
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
        # 跨度短提醒(§1 誠實):抓到但 < 1 年 → 多半是 MoneyDJ 短窗,長歷史源沒收錄該檔
        _short = [r["code"] for r in _res["results"]
                  if r["error"] is None and r["fetched"] and (r.get("span_days") or 0) < 365]
        if _short:
            st.info(f"⚠️ 這幾檔只抓到 **不到 1 年**（多半是保單平台專屬基金,晨星/CnYES 沒收錄 → "
                    f"落回 MoneyDJ 短窗）:{'、'.join(_short)}。要 5 年請用下方**手動 CSV** 補。")

        # §1/§5:抓到 / 雲端未啟用 / 雲端寫入失敗 三態誠實分開,不把「寫入失敗」講成「抓不到」。
        if not _res["gs_enabled"]:
            st.warning(f"⚠️ 已抓到 {_res['n_ok']} 檔存本機,但**雲端未啟用 → 重啟會清空**。"
                       "把 SA 加為 NAV Sheet 編輯者後再按一次即可永久保存。")
        elif _res.get("gs_error"):
            st.error(f"⚠️ {_res['n_ok']} 檔**已抓到並存本機**,但**寫入雲端失敗**:{_res['gs_error']}。"
                     "稍後再按一次重試(已抓到的會去重、不會重複寫)。")
        else:
            # 2026-08-28 稽核修正 —— 舊版這裡有兩句話是假的,而且指路指錯地方:
            #   (1) 把「被 Gate 0 擋下」併進「N 檔抓不到」:被擋的檔**抓得好好的**。
            #   (2) 一律叫使用者「用下方 CSV 手動補」:手動 CSV 正是 nav_history
            #       各條寫入路徑中**沒有這道閘門**的那一條 —— 把「疑似抓到錯幣別」
            #       的檔導過去,等於教使用者繞過剛剛擋住他的那道護欄(§1)。
            #       只有**真的抓不到**的檔才該走 CSV。
            _n_blocked = int(_res.get("n_blocked") or 0)
            _n_nofetch = int(_res["n_fail"]) - _n_blocked
            _msg = (f"完成:{_res['n_ok']} 檔抓到 → 雲端 nav_history 去重後新增 "
                    f"**{_res['gs_written']:,}** 筆(永久,重開不丟)。")
            if _n_nofetch:
                _msg += f" ⬜ {_n_nofetch} 檔**抓不到**(見上表)→ 用下方 CSV 手動補。"
            if _n_blocked:
                # 顏色:偵測到的資料完整性故障 = 🔴(render_state 五態的「系統真出錯」側),
                # 不是 ⬜。用**同一個**訊息元件切紅,不新增區塊(版面不變 → §-1.5.4 屬修正錯誤)。
                # ⚠️ 訊息**直接帶上每一檔的失敗原因**,不是只寫「見上表」——
                # 紅框要拿得出失敗證據,否則它與「業務結論用紅字」無法區分
                # (`tests/test_render_state_color_separation.py` 的 bare-`st.error`
                #  ratchet 守的就是這件事:紅框必須手上真的有 error)。
                _blocked_errors = "；".join(
                    f"{r['code']}：{r['error']}"
                    for r in _res["results"] if r.get("blocked"))
                st.error(
                    f"🔴 {_msg} 另有 **{_n_blocked} 檔抓到了但沒有寫入** —— "
                    "它們與雲端既有歷史**對不上**,極可能抓到別的級別/幣別,已擋下。"
                    f"\n\n{_blocked_errors}\n\n"
                    "**不要用下方 CSV 硬補這幾檔** —— 手動 CSV 沒有這道檢查,"
                    "補進去就會把可疑序列寫進那張永不刪除的表。"
                    "請先在選股池確認該檔的 ISIN / 幣別是不是你要的那個級別。")
            else:
                st.success(f"✅ {_msg}")


def render_nav_backfill_auto_section() -> None:
    """① 一鍵自動補全缺淨值的**公開**入口（實作仍是 `_sec_nav_backfill_auto`）。

    存在的理由只有一個：⑤ 的「🗄️ NAV 歷史」合一區塊要呼叫它，而
    `CLAUDE.md §8.2` 明禁跨模組直取底線開頭的 private symbol
    （姊妹 repo 的 `V-PICKER-PRIV-1` 就是這個病）。**本函式不加任何行為**。
    """
    _sec_nav_backfill_auto()


def _sec_nav_backfill() -> None:
    """🗄️ 補歷史淨值(① 一鍵自動補全部 + ② 手動 CSV 上傳)→ 存進 GS nav_history。

    v19.472:FundClear 挑基金 + TDCC 11641 兩支抓取工具**移除**(user 2026-08-18:抓不到的檔
    改用「選股池(併入的基金代號對照表)」填 ISIN → 系統走晨星自動補淨值)。保留手動 CSV
    上傳(離線可用、最可靠的真備援)。
    v19.474(user 2026-08-18「前面資料有缺的都要補起來」):加「① 一鍵自動補全部」——
    把「持倉 ∪ 選股池」逐檔完整歷史(含 ISIN→晨星 ~5.5 年)一次抓齊寫進雲端 nav_history。
    """
    st.markdown("### 🗄️ 補歷史淨值")
    _sec_nav_backfill_auto()
    st.caption("── 或 ── 抓不到淨值的基金:從 CnYES / MoneyDJ 手動下載完整歷史 CSV → 上傳這裡 → 存進 "
               "nav_history,健診就有足夠序列算真實報酬(根治「抓不到 → 外推 → 假吃本金」)。")
    render_nav_csv_manage_section()


def render_nav_csv_manage_section(*, expander_label: str | None = None) -> None:
    """② 本地基底 CSV：多檔上傳 → `cache/nav_history/{code}.json` ＋ 同步雲端，
    外加逐檔的增量更新 / 下載備份 / 清除。

    2026-09-02 線框 §03 ⑤ B「合一」抽出（**只搬位置，行為一行未改**）——
    原本整段 inline 在 `_sec_nav_backfill()` 裡，抽出後 ⑤ 的「🗄️ NAV 歷史」
    區塊才能在**不連帶把管理室其他分區也拉進來**的前提下呼叫它。

    `expander_label` 讓合一入口改用功能導向的標題（合一後兩個舊標題都不留，
    線框：「留任一個都會讓人以為另一個還在別頁」）；預設維持舊標題，
    供 ⑤ **沒有**持有 `NAV_HISTORY` 時的原路徑使用（行為不變）。

    ⚠️ **不要把它跟 `nav_history_gs.import_csv_text` 那條混為一談** ——
    本函式走 `import_nav_csv_multi`：**要有代號欄**、可一次多檔、**會寫本地 cache**。
    對帳單那條是單檔、代碼手填、**只寫雲端**、吃兩欄 CSV。兩者不可互相取代。
    """
    # v19.461→472：🗄️ NAV 歷史資料管理(手動 CSV 上傳 / 匯出 / 增量)。widget key `_nh_*` 僅此處渲染。
    with st.expander(
            expander_label or "🗄️ NAV 歷史資料管理（CSV 上傳當基底 + 系統增量更新）",
            expanded=False):
        from services.nav_history_store import (
            clear_cache as _nh_clear,
            export_nav_csv as _nh_export,
            get_cache_status as _nh_status,
            import_nav_csv_multi as _nh_import_multi,
            incremental_update as _nh_update,
            list_cache_codes as _nh_codes,
        )
        st.caption(
            "💡 **架構**：user 從 CnYES / MoneyDJ 手動下載完整歷史 CSV → 上傳這裡 → "
            "系統存進 `cache/nav_history/{code}.json`。**系統計算長期報酬 / 健診時會優先讀 cache**，"
            "確保歷史完整。後續按「🔄 增量更新」只抓最新幾天疊代上去（不重抓 5 年）。"
        )
        st.caption(
            "⚠️ 代號讀自 CSV **第一欄**（不用手打）。不同網站基金代碼不同（MoneyDJ 內部碼 ACTI94、"
            "CnYES 可能用 ISIN LU0xxx）—— 你在 CSV 用哪個 code，cache 就用哪個當 key，增量更新才對得上。"
        )

        # v19.490（user 2026-08-19「移除基金代號欄，代號由 CSV 帶入」）:上傳讀 CSV 代號欄自動分檔,
        # 多檔可放同一個 CSV（代號欄區分）。逐檔動作(增量/下載/清除)改用下方 cache 選單挑代號。
        _nh_file = st.file_uploader(
            "📥 上傳 NAV CSV（格式:**代號 ｜ 日期 ｜ 淨值**，無表頭亦可；日期西元/民國都吃；"
            "多檔可放同一個 CSV，用代號欄自動分檔）",
            type=["csv"], key="_nh_upload_csv",
        )
        if _nh_file is not None:
            _mr = _nh_import_multi(_nh_file.getvalue())
            if _mr["errors"]:
                st.error("、".join(_mr["errors"]))
            else:
                _lines = [
                    f"**{c}** {_mr['results'][c]['total']:,} 筆"
                    f"（{_mr['results'][c]['date_min']}~{_mr['results'][c]['date_max']}）"
                    for c in _mr["codes"]
                ]
                st.success(f"✅ 匯入 {len(_mr['codes'])} 檔 → " + "　·　".join(_lines))
                # 雙寫雲端 nav_history（永久，重啟不丟；跨日期格式去重；非致命）
                # v19.509:SA 缺但已 Google 登入 → 用登入者身分寫雲端(手機免設 SA)。
                _oauth_csv = None
                try:
                    from ui.helpers.io.oauth_state import _get_oauth_client
                    _oauth_csv = _get_oauth_client()
                except Exception:  # noqa: BLE001
                    _oauth_csv = None
                # v19.509 稽核修:先判後端 —— 缺 SA 缺 OAuth 時 append_points 會 no-op 回
                # skipped>0,原文案「雲端已是最新」是**假的永久保存宣稱**(§1)。先誠實警告本機暫存。
                from services.nav_history_gs import backend_status as _nh_backend
                if _nh_backend(_oauth_csv) == "local":
                    st.warning("⬜ 已匯入本機,但**雲端未啟用(沒 Service Account、也沒 Google 登入)"
                               "→ 容器重啟會清空**。先完成 **Google 登入**再上傳即可永久保存。")
                else:
                    try:
                        from services.nav_history_gs import append_points as _gs_append
                        _g = _gs_append(_mr["points"], oauth_client=_oauth_csv)
                        if _g.get("written"):
                            st.caption(f"🗂️ 已同步 {_g['written']} 筆到雲端 nav_history（重啟不丟）")
                        else:
                            st.caption("🗂️ 雲端 nav_history 已是最新（全部去重、無新增）")
                    except Exception as _e_gs:   # noqa: BLE001 — 雲端同步失敗不影響本機匯入
                        # 原文案「略過」讀起來像「不需要做」,實際是**同步失敗**：
                        # 匯入的淨值只在本機,容器重啟就沒了。
                        # ⚠️ 已知未修：下一行 `st.rerun()` 應該會把這則訊息沖掉（改色前
                        #    的 st.caption 同樣看不到）。要讓它真的看得見必須存進
                        #    session_state 於 rerun 後補印 —— 行為變更,不在本批範圍。
                        # ⚠️ **未沙箱實測**：依 Streamlit 語意推得,本批未寫 AppTest 驗證
                        #    → 屬待驗事項。（同 tab1_macro_longterm.py 的那一處。）
                        system_error("雲端 nav_history 同步失敗", _e_gs,
                                     hint="本機已存,但**沒有寫上雲端**,容器重啟會清空。")
                st.rerun()

        # 逐檔動作:增量更新 / 下載 / 清除 —— 從已建立的 cache 選一檔（取代原手打代號）
        _codes = _nh_codes()
        if _codes:
            _sel = st.selectbox("已建立的 cache（選一檔做增量更新 / 下載備份 / 清除）",
                                _codes, key="_nh_sel")
            _status = _nh_status(_sel)
            if _status["exists"]:
                st.success(
                    f"✅ {_sel}:{_status['count']:,} 筆 "
                    f"({_status['date_min']} ~ {_status['date_max']}，涵蓋 {_status['years_covered']} 年)"
                )
            _act_c1, _act_c2, _act_c3 = st.columns(3)
            if _act_c1.button("🔄 從 MoneyDJ 增量更新", use_container_width=True, key="_nh_update_btn"):
                with st.spinner("抓最新幾天 NAV 疊代到 cache..."):
                    _u = _nh_update(_sel)
                if _u["errors"]:
                    st.error("、".join(_u["errors"]))
                else:
                    st.success(f"✅ fetch_nav 抓 {_u['fetched']} 筆，merge 新增 {_u['new_rows']} 筆，"
                               f"總 {_u['total']:,} 筆")
                    st.rerun()
            _act_c2.download_button(
                "📤 下載當前 cache 為 CSV", _nh_export(_sel),
                file_name=f"nav_{_sel}.csv", mime="text/csv",
                use_container_width=True, key="_nh_dl_btn",
            )
            if _act_c3.button("🗑️ 清除 cache", use_container_width=True, key="_nh_clear_btn"):
                _nh_clear(_sel)
                st.rerun()
        else:
            st.caption("尚無任何 cache —— 上傳一個「代號｜日期｜淨值」CSV 建立基底。")

        st.caption(
            "🔧 **工作流程**：① 第一次去 [CnYES](https://fund.cnyes.com) 或 "
            "[MoneyDJ](https://www.moneydj.com/funddj/) 找到該基金 → 下載完整歷史 CSV → "
            "上傳到此 → ② 之後每週按「🔄 增量更新」自動抓最新疊代 → "
            "③ reboot 前按「📤 下載」備份 → reboot 後重新上傳即還原。"
        )


def render_manage_tab() -> None:
    from ui.helpers.story_nav import render_flow_nav, section_label as _section_label_tm
    # ⑤ 設定與診斷合併頁（線框 §03 ⑤，WP-E）已畫分區標題時，這裡不再畫第二個 `##`。
    # 只讓掉標題那一行 —— flow_nav / caption / info 一律照舊（它們帶的是本頁的資訊）。
    # ~~旗標全空（現況，⑤ 未接線）→ 本頁行為與現在完全相同。~~
    # ⚠️ 2026-08-31 WP-F 接線後就地更正（**有意識的更正，不是漏刪** · 決策者：AI 總管）：**這句話現在是假的。** ⑤ 已接線
    # （`app.py` 掛 `render_settings_diag_tab`），本函式的唯一 production caller 是
    # `ui/tab_settings_diag.py::_render_maintain_section()`，它永遠帶著
    # `settings_page_owns(MANAGE_HEADER)` → 下方 `if not _settings_page_owns(...)`
    # 的 `st.markdown("## …")` 在 production **恆不觸發**（分區標題由 ⑤ 畫）。
    # 分支刻意保留：它是「⑤ 沒持有時本頁自己畫大標」的契約實作。
    from ui.helpers.settings_diag.merge_context import (
        MANAGE_HEADER as _SD_MANAGE_HEADER,
        NAV_HISTORY as _SD_NAV_HISTORY,
        owned_by_settings_page as _settings_page_owns,
    )
    if not _settings_page_owns(_SD_MANAGE_HEADER):
        # ⚠️ 2026-08-31 WP-F 就地修正（**有意識的修正，不是漏改** ·
        # 決策者：AI 總管）：舊寫法 ~~`tab_label('manage')`~~ 在七→五之後
        # **會當場 KeyError** —— `'manage'` 自 2026-08-31 起是**頁內分區**、
        # 不是分頁，`tab_label()` 對它一律 fail loud（story_nav 刻意設計）。
        # 它沒有炸過，只是因為這個分支在 production 恆不觸發（合併頁永遠
        # 持有 PAGE_HEADER / MANAGE_HEADER）—— **一顆埋在死碼裡的地雷**：
        # 哪天有人讓這個分支活過來，第一件事就是 KeyError。
        # 改吃 `section_label('manage')`（分區名 SSOT，回「🗄️ 資料維護與通報」）。
        st.markdown(f"## {_section_label_tm('manage')}")
    render_flow_nav("manage")   # 巨觀:第 ③ 層（選股池 = 流程圖的「觀察池 Watchlist」）
    st.caption("你的基金資料**一站集中在這一頁**。資料存在 Google Sheets、永久保存,關掉重開都在。")
    # ⚠️ 這份清單**照著實際會畫的分區長出來**，不是寫死的散文。
    #    2026-09-02 之前它寫死「這一頁由上到下有 4 塊」＋ 4 條 —— 而 NAV 歷史一旦
    #    被 ⑤ 收成合一入口，第 3 條就會指向一個**本頁根本不會畫**的區塊。
    #    本 repo 一再記過同一個病：指路指到不存在的東西，比沒有指路更糟。
    _blocks = [
        "📁 **選股池(候選基金)** — 你**還沒買、考慮想換進來**的備選名單(不是持倉)。"
        "抓不到淨值的檔在這裡填 **ISIN**,系統就走晨星自動補淨值(v19.472 併入原「對照表」)。",
        "🗓️ **除息行事曆** — 你持有基金的配息日曆。",
    ]
    if not _settings_page_owns(_SD_NAV_HISTORY):
        _blocks.append(
            "🗄️ **補歷史淨值** — 「🔄 一鍵自動補全部」把持倉＋選股池逐檔完整歷史"
            "(含 ISIN→晨星 ~5.5 年)一次抓齊存雲端;抓不到的再手動上傳 CSV(根治吃本金誤判)。")
    _blocks.append("🔔 **換股通報** — 設定 LINE 每週提醒。")
    st.info(
        f"**這一頁由上到下有 {len(_blocks)} 塊**:\n\n"
        + "\n".join(f"{_i}. {_b}" for _i, _b in enumerate(_blocks, 1))
    )
    # v19.462:移除「投資組合(持倉)」一覽(user 2026-08-17:帳本(配置&帳本 Tab)已有;
    # 且流程圖把 Portfolio 歸「配置&帳本」,管理室專責 Watchlist/選股池 + 補歷史淨值)。
    # v19.472:退「基金代號對照表」獨立區 —— 併入選股池(填 ISIN 即解鎖補淨值,兩表共用一張)。
    _sec_pool()
    st.divider()
    _sec_dividend_calendar()
    # 2026-09-02 線框 §03 ⑤ B「合一」：NAV 歷史三個功能收成 ⑤ 的單一入口。
    # ⑤ 持有 → 本頁**不畫**這一塊（否則同一頁會出現兩份 NAV 匯入）；
    # ⑤ 沒持有（舊七分頁路徑 / 直接呼叫本函式）→ 照舊完整渲染，行為一字未變。
    if not _settings_page_owns(_SD_NAV_HISTORY):
        st.divider()
        _sec_nav_backfill()
    st.divider()
    _sec_notify()
