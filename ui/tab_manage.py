"""ui/tab_manage.py — 📋 我的管理室(v19.433)。一站集中管理:選股池 + 投資組合 + 通報。

**不新增儲存**:選股池仍存 Google Sheets `_fund_pool` 分頁、投資組合仍存政策 Sheet
(和 Tab④ 保單管理**同一本、同源**),本頁只是它們的**集中管理介面**,全部重用既有
L1/L2/L0(§8.1 不重造):
- 📁 選股池:重用 `switch_advisor_section._render_pool_editor`(GS + 本地雙後端,永久保存)。
- 💼 投資組合:`load_all_policies_v2` 一覽 + `write_policy_v2` / `delete_policy_worksheet`
  刪改(寫回政策 Sheet;§8.2 EX-CRUD-1 允許 L3 直呼 L1 CRUD)。
- 🔔 通報:LINE 設定狀態 + 預覽本週訊息 + 測試發送 + 設定指引。**每週自動送仍是 NAS 排程**,
  本頁只負責看/測(Streamlit 不背景跑,§1 不假裝能排程)。

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
               "加/刪/改存到 **`_fund_pool` 分頁**(和你的保單持倉分頁**不同本清單**,不會動到持倉)。")

    # v19.461:移除「曾經查過的基金清單」自動記錄 + 匯入(user 2026-08-17:介面不友善 → 全拿掉)。
    # 選股池本身即「觀察清單 watchlist」,直接用下方編輯器加/刪代號。
    try:
        from ui.helpers.fund_grp_health.switch_advisor_section import _render_pool_editor
        _render_pool_editor()
    except Exception as _e:  # noqa: BLE001
        _friendly("選股池管理載入失敗", _e)


# ───────────────────────── ② 投資組合 ─────────────────────────

def _sec_portfolio():
    st.markdown("### 💼 投資組合(持倉)")
    st.caption("**這是你目前實際持有的基金**(來自你的保單 Google Sheet)。**唯讀一覽** —— "
               "要改金額/級別或刪保單,請**直接到 Google Sheet 依範本改**(App 不再寫回、不會清空你的資料)。")

    if not st.button("📥 載入 / 重新整理投資組合(雲端)", use_container_width=True, key="manage_pf_load"):
        if not st.session_state.get("_manage_pf_loaded"):
            st.info("按上方按鈕從雲端載入你的投資組合(避免每次重整都打 Google API)。")
            return

    _client, _sid = _policy_client_and_sheet()
    if _client is None:
        st.info(_sid)                                   # 這裡 _sid 是原因字串
        return

    try:
        from repositories.policy.v2 import load_all_policies_v2
        _df = load_all_policies_v2(_client, _sid)
    except Exception as _e:  # noqa: BLE001
        _friendly("讀取投資組合失敗", _e, level="error")
        return
    st.session_state["_manage_pf_loaded"] = True

    from repositories.policy.v2 import ALL_COLS_V2
    # v19.436:10 欄 schema 全為基金列(item_type 退役) → 以非空 fund_code 認基金列。
    _fund_rows = _df[_df["fund_code"].astype(str).str.strip() != ""]
    if _fund_rows.empty and _df.empty:
        st.info("這本 Sheet 目前沒有任何持倉。可到 Tab④ 新增保單/基金。")
        return
    _codes = sorted({str(c).strip() for c in _fund_rows["fund_code"] if str(c).strip()})
    st.success(f"共 {len(_codes)} 檔基金 · {_df['policy_id'].nunique()} 張保單。")

    # v19.452 唯讀:移除「🔧 一鍵修正+精簡 / 💾 存 / 🗑 刪保單」等會覆寫/刪 Sheet 的動作
    # (user 決策改直接改 Sheet)。本區只做**一覽顯示**。
    _labels = {
        "policy_id": "保單", "fund_code": "基金代號", "fund_name": "名稱", "currency": "幣別",
        "tier": "級別", "invest_twd": "投入金額(TWD)", "div_cash_pct": "現金給付%",
        "units": "份額(選填)", "avg_nav": "平均成本(選填)", "avg_fx": "平均匯率(選填)",
    }
    for _pid in sorted({str(p) for p in _df["policy_id"] if str(p).strip()}):
        _pdf = _df[_df["policy_id"].astype(str) == _pid]
        with st.expander(f"📄 保單 {_pid}（{len(_pdf)} 列）", expanded=(_df['policy_id'].nunique() == 1)):
            _cols = [c for c in ALL_COLS_V2 if c in _pdf.columns]
            _view = (_pdf[_cols].reset_index(drop=True)
                     .rename(columns={c: _labels.get(c, c) for c in _cols}))
            st.dataframe(_view, use_container_width=True, hide_index=True)
    st.caption("唯讀顯示。要改金額/級別或刪保單,請**直接到 Google Sheet 依範本改**(App 不覆寫、不清空)。")


def _prepare_write_df(edited_df, policy_id):
    """編輯後的 grid → 準備給 write_policy_v2 的 df:補 policy_id。

    v19.436:10 欄 schema 全為基金列(item_type 退役)。write_policy_v2 會跳過無 fund_code
    的空列,並保留 units/avg_nav/avg_fx 等選填欄照原樣帶著(§1 防資料流失:整張覆寫不抹掉)。
    純函式(不碰 st / 網路),供單元測試鎖住此回寫前處理(§6)。
    """
    _out = edited_df.copy()
    _out["policy_id"] = policy_id
    return _out


def _run_fix_and_shrink(client, sheet_id):
    """v19.436:一鍵修正基金名稱 + 精簡 Sheet。逐張進度條;完成後清快取重載。"""
    try:
        from ui.helpers.cloud_io import fix_and_shrink_v2_sheets
        from ui.helpers.v2_editor import _autofill_from_moneydj
    except Exception as _e:  # noqa: BLE001
        _friendly("載入修正工具失敗", _e, level="error")
        return
    _bar = st.progress(0.0, text="準備中…")

    def _cb(done, total, pid):
        _bar.progress(done / max(total, 1), text=f"處理 {pid}（{done}/{total}）…")

    try:
        with st.spinner("逐張重抓基金名稱 + 精簡欄位(需數十秒)…"):
            _res = fix_and_shrink_v2_sheets(
                client, sheet_id, info_fetcher=_autofill_from_moneydj, progress_cb=_cb)
    except Exception as _e:  # noqa: BLE001
        _friendly("修正 + 精簡失敗", _e, level="error")
        return
    _bar.empty()
    # 備份失敗 → fix_and_shrink 已中止(未動原本),只回 errors、無 policies
    if _res.get("errors") and _res.get("policies", 0) == 0 and not _res.get("names_fixed"):
        for _err in _res["errors"][:5]:
            st.error(f"❌ {_err}")
        return
    st.success(f"✅ 完成:{_res['policies']} 張保單 · {_res['funds']} 檔基金 · "
               f"修正名稱 {_res['names_fixed']} 筆。已精簡成 10 欄。")
    if _res.get("backup_url"):
        st.info(f"🛡️ 動手前已備份整本 Sheet:[開啟備份副本]({_res['backup_url']})")
    for _err in _res.get("errors", [])[:5]:
        st.warning(f"⚠️ {_err}")
    # 清 load_all 短快取,重載拿最新
    try:
        from repositories.policy.v2 import clear_load_all_ws_cache
        clear_load_all_ws_cache()
    except Exception:  # noqa: BLE001
        pass
    st.session_state["_manage_pf_loaded"] = True
    st.rerun()


def _save_policy(client, sheet_id, policy_id, edited_df):
    """編輯後的 grid → 回寫政策 Sheet(重用 write_policy_v2;§1 失敗顯示不崩)。"""
    try:
        from repositories.policy.v2 import write_policy_v2
        _out = _prepare_write_df(edited_df, policy_id)
        _n = write_policy_v2(client, sheet_id, policy_id, _out)
        st.success(f"已存 {policy_id}:{_n} 檔寫回雲端。")
        st.session_state["_manage_pf_loaded"] = True
        st.rerun()
    except Exception as _e:  # noqa: BLE001
        _friendly(f"保單 {policy_id} 存檔失敗", _e, level="error")


def _delete_policy(client, sheet_id, policy_id):
    try:
        from repositories.policy.v2 import delete_policy_worksheet
        _ok = delete_policy_worksheet(client, sheet_id, policy_id)
        if _ok:
            st.success(f"已刪除整張保單 {policy_id}。")
            st.rerun()
        else:
            st.warning(f"保單 {policy_id} 找不到或未刪除。")
    except Exception as _e:  # noqa: BLE001
        _friendly(f"保單 {policy_id} 刪除失敗", _e, level="error")


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


def _yf_1y_return(ticker: str) -> "float | None":
    """yf 收盤 → 近1年報酬%(252 交易日;不足取全期)。無資料/失敗 → None(§1)。"""
    try:
        from repositories.macro.yf import fetch_yf_close
        _s = fetch_yf_close(ticker, range_="2y")
        if _s is None or len(_s) < 30:
            return None
        _last = float(_s.iloc[-1])
        _base = float(_s.iloc[-252]) if len(_s) >= 252 else float(_s.iloc[0])
        return (_last / _base - 1) * 100.0 if _base > 0 else None
    except Exception:  # noqa: BLE001
        return None


def _sec_nav_backfill() -> None:
    """📥 補歷史淨值(FundClear 境外基金)→ 存進 GS nav_history → 根治「抓不到→外推→假吃本金」。"""
    st.markdown("### 📥 補歷史淨值(FundClear 境外基金)")
    st.caption("抓 FundClear 境外基金的**完整歷史淨值**(單次可達 ~20 年)存進 Google Sheet,"
               "讓健診有足夠序列算**真實 1 年報酬** —— 根治「抓不到官方資料 → 外推 → 假吃本金」"
               "(如 ACTI71 −38%)。")
    st.warning("⚠️ **務必選『你實際持有的那個級別』**(同幣別、同累積 Acc/配息 Dist)——"
               "抓來的歷史會**併入**該基金既有序列,若級別/幣別對不上(例:你持配息級別卻抓累積級別、"
               "或幣別不同),接點會產生**跳空 → 報酬失真**。**最安全**是用在 App 目前完全抓不到"
               "淨值的基金(如 ACTI71),那時併入的是純 FundClear 單一序列,不會混。")
    with st.expander("展開:①挑基金 → ②選級別 → ③下載存進 Google Sheet"):
        # ① 用「現在有的資料」:載入你的持倉,從中挑(自動帶基金名稱 + 內部碼,免手打、免打錯)
        if st.button("📇 載入我的持倉清單(從中挑基金)", key="navbf_load_holdings"):
            try:
                _cli_h, _sid_h = _policy_client_and_sheet()
                if _cli_h is None:
                    st.info(_sid_h)
                else:
                    from repositories.policy.v2 import load_all_policies_v2
                    _pdf_h = load_all_policies_v2(_cli_h, _sid_h)
                    _seen, _hold = set(), []
                    for _r in _pdf_h.itertuples(index=False):
                        _c = str(getattr(_r, "fund_code", "") or "").strip().upper()
                        _nm = str(getattr(_r, "fund_name", "") or "").strip()
                        if _c and _c not in _seen:
                            _seen.add(_c)
                            _hold.append({"code": _c, "name": _nm})
                    st.session_state["navbf_holdings"] = _hold
                    if not _hold:
                        st.info("持倉裡沒有基金代號可挑。")
            except Exception as _e:  # noqa: BLE001
                _friendly("載入持倉失敗", _e, level="error")

        # ── 2026-08-15 user 反映：「我想要也能用代號去找」──────────────────────
        # 其實 `resolve_search_name` 早就支援打代號（會去選股池 / 持倉查名稱），
        # 但欄位標籤只寫「基金名稱」—— **使用者不可能知道**。而且可選的代號
        # 明明就在選股池裡，卻沒有列出來給人挑，只能自己記或自己打。
        #
        # 改法：把「選股池 + 持倉」合併成一份 代號→名稱 清單直接讓你挑，
        # 挑完仍走同一支 `resolve_search_name`（拿名稱去 FundClear 找、
        # 拿代號存回 nav_history），邏輯零改動、只是把入口打開。
        _hold = st.session_state.get("navbf_holdings") or []
        _pool_opts: list = []
        try:
            from repositories.pool_repository import list_pool
            for _pe in list_pool():
                _c = str(getattr(_pe, "code", "") or "").strip().upper()
                if _c:
                    _pool_opts.append({"code": _c,
                                       "name": str(getattr(_pe, "name", "") or "").strip(),
                                       "src": "選股池"})
        except Exception as _e_pool:  # noqa: BLE001 — 選股池讀不到不擋手打
            import sys as _sys_pool
            print(f"[navbf] 選股池讀取失敗: {type(_e_pool).__name__}: {_e_pool}",
                  file=_sys_pool.stderr)
        # 持倉優先（同代號時保留持倉那筆的名稱：那是你實際持有的級別）
        _pick_src: dict = {}
        for _h in _hold:
            _c = str(_h.get("code", "") or "").strip().upper()
            if _c:
                _pick_src[_c] = {"code": _c, "name": _h.get("name", "") or "", "src": "持倉"}
        for _p in _pool_opts:
            _pick_src.setdefault(_p["code"], _p)

        _fixed_code = ""
        _name = ""
        if _pick_src:
            _hopts = {
                f"{_v['code']} — {_v['name'] or '(無名稱)'}　[{_v['src']}]": _v
                for _v in sorted(_pick_src.values(), key=lambda x: x["code"])
            }
            _MANUAL = "✍️ 自己打（不在清單裡）"
            _sel = st.selectbox(
                "① 挑基金 —— **用代號挑**（清單來自你的選股池 + 持倉）",
                [_MANUAL] + list(_hopts), key="navbf_hold_pick",
                help="下拉選單是「代號 — 名稱」。挑好之後，系統會拿**名稱**去 FundClear 搜尋，"
                     "抓到的歷史則存回**你的代號**底下（健診才讀得回）。",
            )
            if _sel != _MANUAL:
                _hpick = _hopts[_sel]
                _name = _hpick["name"] or _hpick["code"]
                _fixed_code = _hpick["code"]
                st.caption(f"→ 用名稱「**{_name}**」去 FundClear 找,"
                           f"抓到後存進內部碼「**{_fixed_code}**」。")
            else:
                _name = st.text_input(
                    "基金名稱 **或** 代號", key="navbf_name",
                    placeholder="例:聯博多元資產收益組合基金　或　ACTI71",
                    help="打代號時，系統會先去選股池 / 持倉查出對應名稱再搜尋。"
                         "代號查不到對應名稱的話，會直接把你打的字當基金名稱去找。")
        else:
            _name = st.text_input(
                "① 基金名稱 **或** 代號（按上面『載入持倉』可改用清單挑）",
                key="navbf_name",
                placeholder="例:聯博多元資產收益組合基金　或　ACTI71",
                help="打代號時，系統會先去選股池 / 持倉查出對應名稱再搜尋。")
        _org = st.text_input("機構代碼(選填;知道就填可加速。例 019=安聯)", key="navbf_org",
                             placeholder="留空 = 全機構搜尋(較慢;機構清單 endpoint 部署後才驗證)")
        with st.expander("🔧 出現「機構清單 endpoint 全部候選失敗」?怎麼辦"):
            st.markdown(
                "FundClear 的**機構清單**那支 API 路徑還沒驗證到(規格書 §2.5 也標未驗證)。兩個解法:\n\n"
                "**A. 直接填機構代碼(最快)**:在上面『機構代碼』欄填代碼再按找。已知 **019 = 安聯**。\n\n"
                "**B. 幫我抓真實路徑(一勞永逸,之後就能用下拉)**:\n"
                "1. 電腦瀏覽器開 `https://www.fundclear.com.tw/offshore/nav-profit/fund-nav?type=history`\n"
                "2. 按 **F12** → 選 **Network(網路)** → 篩選 **Fetch/XHR**\n"
                "3. **重新整理**頁面\n"
                "4. 找開頭像 `common-select` 的請求,把它的 **Request URL** 貼給我\n"
                "5. (順便)機構下拉選你的基金公司(如聯博),看新請求 payload 裡的 `organizeCode`,"
                "那就是你的機構代碼\n\n"
                "把 4/5 貼給我,我把實際 endpoint 寫死,你之後就不用填代碼。")
        # v19.456:user 想「打代碼」→ 用選股池 + 持倉的代碼↔名稱對照,把代碼自動換成名稱去 FundClear
        # 找、代碼留著存回 nav_history。打名稱則原樣。
        _code_name_map = {}
        try:
            from repositories.pool_repository import list_pool
            for _pe in list_pool():
                if getattr(_pe, "code", ""):
                    _code_name_map[str(_pe.code).strip().upper()] = getattr(_pe, "name", "") or ""
        except Exception:  # noqa: BLE001 — 選股池讀不到不阻斷,仍可用名稱直接找
            pass
        for _h in (st.session_state.get("navbf_holdings") or []):
            _code_name_map.setdefault(str(_h.get("code", "")).strip().upper(), _h.get("name", "") or "")
        from services.fundclear_backfill import resolve_search_name
        _search_name, _resolved_code = resolve_search_name(_name, _code_name_map)
        if _resolved_code and _search_name != str(_name).strip():
            _fixed_code = _resolved_code            # 打代碼 → 存回用該代碼(健診讀得回)
            st.caption(f"🔁 代碼 **{_resolved_code}** → 名稱「**{_search_name}**」"
                       "(拿名稱去 FundClear 找、拿代碼存回)")

        if st.button("🔎 找 FundClear 對應基金", key="navbf_find", disabled=not _search_name.strip()):
            try:
                from services.fundclear_backfill import find_fund_candidates
                with st.spinner("搜尋 FundClear 基金清單…"):
                    st.session_state["navbf_cands"] = find_fund_candidates(
                        _search_name.strip(), (_org.strip() or None))
                if not st.session_state["navbf_cands"]:
                    st.warning("查無相似基金 —— 可能非 FundClear 境外基金,或需指定機構代碼。")
            except Exception as _e:  # noqa: BLE001
                _friendly("搜尋 FundClear 失敗(部署環境才連得到;機構清單報錯請填機構代碼或按下方掃描)",
                          _e, level="error")

        if st.button("🔍 掃描全部機構找我的基金(機構清單抓不到時用;較慢 ~1-2 分)",
                     key="navbf_scan", disabled=not _search_name.strip()):
            try:
                from services.fundclear_backfill import find_fund_candidates
                with st.spinner("逐一掃描機構 001-060(~1-2 分,跑完前別關頁面)…"):
                    st.session_state["navbf_cands"] = find_fund_candidates(
                        _search_name.strip(), organize_code=None, scan_range=60)
                if not st.session_state["navbf_cands"]:
                    st.warning("掃描完仍查無 —— 可能非 FundClear 境外基金,或機構代碼超出 001-060 範圍。")
            except Exception as _e:  # noqa: BLE001
                _friendly("掃描失敗", _e, level="error")

        _cands = st.session_state.get("navbf_cands") or []
        if _cands:
            _opts = {f"{c['name']}（{c.get('organize_name') or c['organize_code']}/{c['value']}）"
                     f" · {c['score']:.0%}": c for c in _cands}
            _pick = _opts.get(st.selectbox("選對應基金(**核對名稱**)", list(_opts), key="navbf_pick"))
            if _pick and st.button("取級別清單", key="navbf_classes_btn"):
                try:
                    from services.fundclear_backfill import list_classes_for
                    st.session_state["navbf_classes"] = list_classes_for(
                        _pick["organize_code"], _pick["value"])
                    st.session_state["navbf_pick_fund"] = _pick
                except Exception as _e:  # noqa: BLE001
                    _friendly("取級別清單失敗", _e, level="error")

        _classes = st.session_state.get("navbf_classes") or []
        _pick_fund = st.session_state.get("navbf_pick_fund")
        if _classes and _pick_fund:
            _copts = {f"{c['name']}（{c['value']}）": c for c in _classes}
            _cpick = _copts.get(st.selectbox(
                "選級別 —— **選你實際持有的那個**(幣別 + 累積/配息 都要一致,否則併入會跳空失真)",
                list(_copts), key="navbf_class_pick"))
            if _fixed_code:
                _app_code = _fixed_code                            # 自動帶自持倉 → 健診一定讀得回
                st.caption(f"存進內部碼:**{_app_code}**(自動帶自你的持倉,免打錯)")
            else:
                _app_code = st.text_input(
                    "存進 nav_history 的**持倉內部碼**(健診以此讀回;例 ACTI71)", key="navbf_appcode")
            # ── 稽核 E6（2026-08-14）：寫入前必須先預覽 ────────────────────────
            # 原本這裡是**一顆按鈕直接寫**:抓數千筆 → 直接進 Google Sheet 的
            # nav_history 分頁,零預覽、零確認、無 dry-run、無 rollback。
            # 而那個分頁在說明書上標「🚨 絕對不要刪…無法從任何來源重建」。
            #
            # 真正致命的是去重鍵只有 `(code, date)`:同一檔基金常有多個級別
            # (美元累積 / 美元配息 / 歐元避險…),淨值完全不同。選錯級別寫進去後,
            # **正確級別的淨值會被當成重複而永遠寫不進來**,而錯的那份會被健診
            # 拿去算 1Y 報酬、Sharpe、σ —— 使用者不會收到任何警告。
            #
            # 改成兩段:① 預覽(只抓不寫 + 比對既有資料)→ ② 看過再確認寫入。
            _bf_key = f"{_pick_fund['value']}|{_cpick['value']}|{_app_code.strip()}"
            if _cpick and st.button("① 🔍 預覽（只抓不寫）", key="navbf_preview",
                                    disabled=not _app_code.strip(),
                                    use_container_width=True):
                try:
                    from services.fundclear_backfill import download_and_store
                    with st.spinner("抓完整歷史(可能數十秒)…尚未寫入任何資料"):
                        _prev = download_and_store(
                            _pick_fund["organize_code"], _pick_fund["value"],
                            _cpick["value"], _app_code.strip(),
                            fund_name=_pick_fund["name"], dry_run=True)
                    st.session_state["navbf_preview"] = {"key": _bf_key, "res": _prev}
                except Exception as _e:  # noqa: BLE001
                    _friendly("預覽失敗", _e, level="error")

            _pv = st.session_state.get("navbf_preview") or {}
            # 選項改過 → 舊預覽作廢(否則會拿 A 級別的預覽去確認 B 級別的寫入)
            if _pv and _pv.get("key") == _bf_key:
                _res = _pv["res"]
                if not _res.get("ok"):
                    st.error(f"抓取失敗:{_res.get('reason')}")
                else:
                    _s0, _s1 = _res["span"]
                    _cf = _res.get("conflict") or {}
                    _v = _cf.get("verdict")
                    st.info(
                        f"**預覽結果（尚未寫入）**：{_app_code.strip()} 抓到 "
                        f"**{_res['count']} 筆**，{_s0} ~ {_s1}，計價幣別 "
                        f"**{_res['currency']}**。\n\n"
                        f"這一檔目前已累積 {_cf.get('n_existing', 0)} 筆；"
                        f"其中 {_cf.get('n_overlap', 0)} 天與這次抓到的重疊。"
                    )
                    if _v == "conflict":
                        _rows = "\n".join(
                            f"- {s['date']}：已存 **{s['existing']:.4f}** vs "
                            f"這次 **{s['incoming']:.4f}**（差 {s['diff_pct']:+.1f}%）"
                            for s in (_cf.get("samples") or []))
                        st.error(
                            f"⛔ **偵測到 {_cf['n_conflict']} 天的淨值對不上 —— "
                            "極可能選錯級別，已擋下不寫入。**\n\n"
                            f"{_rows}\n\n"
                            "同一檔基金常有好幾個級別（美元累積 / 美元配息 / 歐元避險…），"
                            "淨值完全不同。**請回上一步核對幣別與配息/累積型是否與你實際持有的一致。**\n\n"
                            "⚠️ 為什麼一定要擋：這個分頁的去重只看「代碼 + 日期」，"
                            "**錯的資料寫進去之後，正確的就永遠寫不進來了**，"
                            "而健診會拿錯的去算報酬率。"
                        )
                    elif _v == "duplicate":
                        st.warning(
                            "ℹ️ 這段歷史**已經在裡面了**（重疊日的淨值完全一致）。"
                            "按下面的確認鈕不會有任何改變，也不會弄壞什麼。")
                    elif _v == "unknown":
                        st.warning(
                            "⚠️ **讀不到既有資料，無法確認會不會撞到既有紀錄。**"
                            "多半是 Google Sheet 還沒設定好。"
                            "在確認之前建議先到「📖 參考 / 診斷」看一下累積狀態燈。")
                    else:
                        st.success("✅ 沒有與既有資料重疊，這是純新增，安全。")

                    if _v != "conflict":
                        st.caption("確認前請再看一眼上面的**計價幣別**與**起訖日期**是否合理。")
                        if st.button("② ✍️ 確認寫入 Google Sheet", key="navbf_commit",
                                     type="primary", use_container_width=True):
                            try:
                                from services.fundclear_backfill import download_and_store
                                with st.spinner("寫入 Google Sheet…"):
                                    _w = download_and_store(
                                        _pick_fund["organize_code"], _pick_fund["value"],
                                        _cpick["value"], _app_code.strip(),
                                        fund_name=_pick_fund["name"])
                                if not _w.get("ok"):
                                    st.error(f"已擋下未寫入:{_w.get('reason')}")
                                else:
                                    st.success(
                                        f"✅ {_app_code.strip()}:寫入 {_w['written']} 筆"
                                        f"(重複略過 {_w['skipped']})。"
                                        "重整健診 / 個基體檢就會用這段歷史算真實 1Y,不再外推誤判。")
                                    st.session_state.pop("navbf_preview", None)
                            except Exception as _e:  # noqa: BLE001
                                _friendly("寫入失敗", _e, level="error")

    with st.expander("📥 每日官方淨值(TDCC 11641 近7天)—— 全持倉一鍵補 / 驗證後可排每日自動"):
        st.caption("抓政府開放資料『境外基金淨值』(近7天)→ 用**名稱**對到你**全部持倉** → 存進 nav_history。"
                   "**近7天只能往後累積、補不了過去**(過去用上面 FundClear)。跑幾週後每檔都有序列。"
                   "⚠️ 首次請**核對下方比對名稱**對不對,再考慮排每日自動。")
        if st.button("📥 抓 TDCC 官方淨值 → 補全持倉", key="tdcc_acc_btn", use_container_width=True):
            try:
                import pandas as _pd_t
                _cli_t, _sid_t = _policy_client_and_sheet()
                if _cli_t is None:
                    st.info(_sid_t)
                else:
                    from repositories.policy.v2 import load_all_policies_v2
                    _pdf_t = load_all_policies_v2(_cli_t, _sid_t)
                    _seen_t, _hold_t = set(), []
                    for _r in _pdf_t.itertuples(index=False):
                        _c = str(getattr(_r, "fund_code", "") or "").strip().upper()
                        _nm = str(getattr(_r, "fund_name", "") or "").strip()
                        if _c and _c not in _seen_t:
                            _seen_t.add(_c)
                            _hold_t.append({"code": _c, "name": _nm})
                    from services.tdcc_nav_accumulate import accumulate_and_store
                    with st.spinner("抓 TDCC 11641 + 比對 + 寫入…"):
                        _res_t = accumulate_and_store(_hold_t)
                    if not _res_t.get("ok"):
                        st.error(f"失敗:{_res_t.get('reason')}")
                    else:
                        _rep_t = _res_t["report"]
                        st.success(f"✅ 寫入 {_res_t['written']} 筆(重複略過 {_res_t['skipped']});"
                                   f"對到 {len(_rep_t['matched'])} 檔、對不上 {len(_rep_t['unmatched'])} 檔。")
                        if _rep_t["matched"]:
                            st.caption("**比對結果(請核對名稱是否正確)**:")
                            st.dataframe(_pd_t.DataFrame(_rep_t["matched"]),
                                         use_container_width=True, hide_index=True)
                        if _rep_t["unmatched"]:
                            st.caption("⬜ 對不上(11641 近7天沒有 / 名稱差太多):"
                                       + "、".join(_rep_t["unmatched"]))
            except Exception as _e:  # noqa: BLE001
                _friendly("TDCC 官方淨值累積失敗", _e, level="error")

    # ── v19.461：從「說明書」搬來的 🗄️ NAV 歷史資料管理（手動 CSV 上傳 / 匯出 / 增量）──
    # user 2026-08-17：NAV 歷史管理集中到「我的管理室」。此工具走 services/nav_history_store.py
    # （本機 cache/nav_history/{code}.json）+ 雙寫 GS nav_history，與上面 FundClear / TDCC 兩支
    # 同屬「補歷史淨值」家族，故一併收進本區。widget key `_nh_*` 僅此處渲染（已從說明書移除）。
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
        "**這一頁由上到下有 5 塊**,先看前兩塊就好:\n\n"
        "1. 💼 **投資組合(持倉)** — 你**已經買、目前真正持有**的基金 ← 這才是「你的組合」。\n"
        "2. 📁 **選股池(候選基金)** — 你**還沒買、考慮想換進來**的備選名單(不是持倉)。\n"
        "3. 🗓️ **除息行事曆** — 你持有基金的配息日曆。\n"
        "4. 📥 **補歷史淨值** — 幫抓不到淨值的基金補歷史(根治吃本金誤判)。\n"
        "5. 🔔 **換股通報** — 設定 LINE 每週提醒。"
    )
    _sec_portfolio()          # ★ v19.452:持倉最重要 → 放最前
    st.divider()
    _sec_pool()
    st.divider()
    _sec_dividend_calendar()
    st.divider()
    _sec_nav_backfill()
    st.divider()
    _sec_notify()
