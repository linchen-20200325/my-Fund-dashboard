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
        st.info("目前沒有『已載入』的持倉基金 → 先到 Tab④/組合健診 載入基金,再回來預覽。")
        return
    try:
        from repositories.pool_repository import list_pool
        from services.switch_advisor import advise_switches
        from services.switch_notify import build_notification
        from ui.helpers.fund_grp_health.switch_advisor_section import (
            _fx_label,
            _macro_composite,
            _pool_rows,
            _rows_with_nav,
            _underperf_by_code,
        )
        pool = list_pool()
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
        _pool = list_pool()
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
    st.caption("你的基金**本月除息 / 配息日推估**(選股池 + 已載入持倉)。用過往配息節奏推算,"
               "**非官方公告**;累積型不配息的自動不顯示,加減標的 → 下月自動更新。")

    if st.button("🗓️ 抓選股池標的 → 產生本月除息月曆", use_container_width=True, key="divcal_gen"):
        try:
            _items, _np, _nh = _divcal_gather_items()
            if not _items:
                st.info("選股池與已載入持倉都是空的 → 先到上面『選股池』加標的,或到組合健診載入基金。")
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

        from services.dividend_calendar import build_month_calendar
        from ui.helpers.dividend_calendar_render import render_month_calendar_html
        _cal = build_month_calendar(_items, _now.year, _now.month)
        _html = render_month_calendar_html(_cal)
        _components.html(_html, height=900, scrolling=True)
        _c = _cal["counts"]
        st.caption(f"來源:{st.session_state.get('_divcal_src', '')}　·　本月推估除息 {_c['events']} 檔"
                   + (f"｜{_c['excluded']} 檔累積型/無配息" if _c["excluded"] else "")
                   + (f"｜{_c['unpredictable']} 檔無法推估" if _c.get("unpredictable") else ""))
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
            _pool = [str(e.code or "").strip().upper() for e in list_pool()]
        except Exception as _e:  # noqa: BLE001
            _pool = []
            st.caption(f"⬜ 選股池讀取失敗:[{type(_e).__name__}] {str(_e)[:60]}")
        _all, _seen = [], set()
        for _c in _held + _pool:
            if _c and _c not in _seen:
                _seen.add(_c)
                _all.append(_c)

        from services.nav_history_gs import is_enabled as _gs_enabled
        if not _gs_enabled():
            st.warning("⬜ 雲端 nav_history 未啟用(缺 Service Account,或還沒把 SA 加為那本 NAV Sheet 的"
                       "「編輯者」)→ 現在補的淨值**只會存本機、容器重啟就清空**。建議先完成 SA 授權"
                       "(見 Tab5 資料看板狀態燈)再按。")
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
            _res = backfill_to_gs(_all, progress_cb=_cb)
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

        _rows = [{
            "代號": r["code"],
            "結果": (f"✅ {r['fetched']} 筆{_span_zh(r)}" if (r["error"] is None and r["fetched"])
                     else f"⬜ {r['error']}"),
            "來源": _src_zh(r) if (r["error"] is None and r["fetched"]) else "—",
            "淨值起迄": (f"{r['date_min']} ~ {r['date_max']}" if r["date_min"] else "—"),
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
            _msg = (f"✅ 完成:{_res['n_ok']} 檔抓到 → 雲端 nav_history 去重後新增 "
                    f"**{_res['gs_written']:,}** 筆(永久,重開不丟)。")
            if _res["n_fail"]:
                _msg += f" ⬜ {_res['n_fail']} 檔抓不到(見上表)→ 用下方 CSV 手動補。"
            st.success(_msg)


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
    # v19.461→472：🗄️ NAV 歷史資料管理(手動 CSV 上傳 / 匯出 / 增量)。widget key `_nh_*` 僅此處渲染。
    with st.expander("🗄️ NAV 歷史資料管理（CSV 上傳當基底 + 系統增量更新）", expanded=False):
        from services.nav_history_store import (
            clear_cache as _nh_clear,
            export_nav_csv as _nh_export,
            get_cache_status as _nh_status,
            import_nav_csv as _nh_import,
            incremental_update as _nh_update,
        )
        st.caption(
            "💡 **架構**：user 從 CnYES / MoneyDJ 手動下載完整歷史 CSV → 上傳這裡 → "
            "系統存進 `cache/nav_history/{code}.json`。**系統計算長期報酬 / 健診時會優先讀 cache**，"
            "確保歷史完整。後續按「🔄 增量更新」只抓最新幾天疊代上去（不重抓 5 年）。"
        )
        st.caption(
            "⚠️ 不同網站基金代碼不同！MoneyDJ 用內部碼（ACTI94）、CnYES 可能用 ISIN（LU0xxx）。"
            "上傳後此 cache 用你自己的 code 為 key，不依賴爬蟲。"
        )

        _nh_c1, _nh_c2 = st.columns([1, 2])
        _nh_code = _nh_c1.text_input(
            "基金代號", placeholder="ACTI94", key="_nh_code",
            help="這個 code 同時是 cache key + 對應 fetch_nav 增量更新時的 MoneyDJ 代碼",
        ).strip().upper()
        _nh_file = _nh_c2.file_uploader(
            "📥 上傳 NAV CSV（欄位：date + nav，支援西元/民國 + 中英文欄名）",
            type=["csv"], key="_nh_upload_csv",
        )

        if _nh_code:
            _status = _nh_status(_nh_code)
            if _status["exists"]:
                st.success(
                    f"✅ Cache 已有 {_status['count']:,} 筆 "
                    f"({_status['date_min']} ~ {_status['date_max']}，"
                    f"涵蓋 {_status['years_covered']} 年)"
                )
            else:
                st.info(f"ℹ️ {_nh_code} 尚無 cache，請上傳 CSV 建立基底")

            if _nh_file is not None:
                _r = _nh_import(_nh_code, _nh_file.getvalue())
                if _r["errors"]:
                    st.error("、".join(_r["errors"]))
                else:
                    st.success(
                        f"✅ 匯入成功：新增 {_r['imported']:,} 筆、覆蓋 {_r['merged']:,} 筆 "
                        f"→ 總 {_r['total']:,} 筆 ({_r['date_min']} ~ {_r['date_max']})"
                    )
                    # v19.365 ④ 儲存收斂：磁碟 cache 在 Streamlit Cloud 重啟會清空 →
                    # 雙寫進 Google Sheet nav_history（(code,date) 去重，重啟不丟；非致命）。
                    try:
                        from services.nav_history_gs import import_csv_text as _gs_import
                        _g = _gs_import(
                            _nh_code,
                            _nh_file.getvalue().decode("utf-8-sig", errors="replace"),
                            source="tab6_csv")
                        if _g["enabled"] and _g["written"]:
                            st.caption(f"🗂️ 已同步 {_g['written']} 筆到雲端 nav_history（重啟不丟）")
                        elif not _g["enabled"]:
                            st.caption("⬜ 雲端 nav_history 未啟用（缺 secrets）→ 本次僅存本機，"
                                       "容器重啟會清空（詳見 Tab5 狀態燈）")
                    except Exception as _e_gs:  # 雲端同步失敗不影響本機匯入結果
                        st.caption(f"⬜ 雲端同步失敗（本機已存）：[{type(_e_gs).__name__}] "
                                   f"{str(_e_gs)[:60]}")
                    st.rerun()

            _act_c1, _act_c2, _act_c3 = st.columns(3)
            if _act_c1.button("🔄 從 MoneyDJ 增量更新", use_container_width=True,
                              key="_nh_update_btn", disabled=not _status["exists"]):
                with st.spinner("抓最新幾天 NAV 疊代到 cache..."):
                    _u = _nh_update(_nh_code)
                if _u["errors"]:
                    st.error("、".join(_u["errors"]))
                else:
                    st.success(
                        f"✅ fetch_nav 抓 {_u['fetched']} 筆，"
                        f"merge 新增 {_u['new_rows']} 筆，總 {_u['total']:,} 筆"
                    )
                    st.rerun()

            if _status["exists"]:
                _csv_bytes = _nh_export(_nh_code)
                _act_c2.download_button(
                    "📤 下載當前 cache 為 CSV", _csv_bytes,
                    file_name=f"nav_{_nh_code}.csv", mime="text/csv",
                    use_container_width=True, key="_nh_dl_btn",
                )
                if _act_c3.button("🗑️ 清除 cache", use_container_width=True,
                                  key="_nh_clear_btn"):
                    _nh_clear(_nh_code)
                    st.rerun()

        st.caption(
            "🔧 **工作流程**：① 第一次去 [CnYES](https://fund.cnyes.com) 或 "
            "[MoneyDJ](https://www.moneydj.com/funddj/) 找到該基金 → 下載完整歷史 CSV → "
            "上傳到此 → ② 之後每週按「🔄 增量更新」自動抓最新疊代 → "
            "③ reboot 前按「📤 下載」備份 → reboot 後重新上傳即還原。"
        )


def render_manage_tab() -> None:
    from ui.helpers.story_nav import render_flow_nav, tab_label as _tab_label_tm
    st.markdown(f"## {_tab_label_tm('manage')}")
    render_flow_nav("manage")   # 巨觀:第 ③ 層（選股池 = 流程圖的「觀察池 Watchlist」）
    st.caption("你的基金資料**一站集中在這一頁**。資料存在 Google Sheets、永久保存,關掉重開都在。")
    st.info(
        "**這一頁由上到下有 4 塊**:\n\n"
        "1. 📁 **選股池(候選基金)** — 你**還沒買、考慮想換進來**的備選名單(不是持倉)。"
        "抓不到淨值的檔在這裡填 **ISIN**,系統就走晨星自動補淨值(v19.472 併入原「對照表」)。\n"
        "2. 🗓️ **除息行事曆** — 你持有基金的配息日曆。\n"
        "3. 🗄️ **補歷史淨值** — 「🔄 一鍵自動補全部」把持倉＋選股池逐檔完整歷史(含 ISIN→晨星 ~5.5 年)"
        "一次抓齊存雲端;抓不到的再手動上傳 CSV(根治吃本金誤判)。\n"
        "4. 🔔 **換股通報** — 設定 LINE 每週提醒。"
    )
    # v19.462:移除「投資組合(持倉)」一覽(user 2026-08-17:帳本(配置&帳本 Tab)已有;
    # 且流程圖把 Portfolio 歸「配置&帳本」,管理室專責 Watchlist/選股池 + 補歷史淨值)。
    # v19.472:退「基金代號對照表」獨立區 —— 併入選股池(填 ISIN 即解鎖補淨值,兩表共用一張)。
    _sec_pool()
    st.divider()
    _sec_dividend_calendar()
    st.divider()
    _sec_nav_backfill()
    st.divider()
    _sec_notify()
