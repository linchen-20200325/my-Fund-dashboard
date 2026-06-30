"""ui/sidebar.py — sidebar 渲染(C 第二輪 v19.229 從 app.py 抽出 190 LOC)。

從 app.py module-level `with st.sidebar:` block 抽出,wrapping `render_sidebar()`
fn。OAuth 相關 vars 內部 lazy import,5 個 app-level vars 從 fn kwargs 注入:
  - app_version / engine_version / fred_key / gemini_key / now_tw_fn

caller(app.py)在 sidebar 之前已 `_refresh_oauth_state()`,sidebar 內 lazy
re-import oauth_state module 拿 fresh snapshot。
"""
from __future__ import annotations

import os
import re
import streamlit as st

from fund_fetcher import get_proxy_config
from infra.oauth import build_authorize_url
from repositories.policy_repository import get_sheet_title
from shared.colors import GH_BG_PRIMARY, GH_BORDER, TRAFFIC_NEUTRAL  # v19.253 Phase 4-B2 #888 SSOT, WHITE


def render_sidebar(*,
                   app_version: str,
                   engine_version: str,
                   fred_key: str | None,
                   gemini_key: str | None,
                   now_tw_fn,
                   ) -> None:
    """渲染 sidebar(基金戰情室 logo + 部署 beacon + Proxy 設定 + Proxy 測試 +
    GitHub 強制同步 + 資料健康總覽 + 全域刷新 + Google 帳號 + 工作中帳本)。"""
    # OAuth 相關 lazy import + refresh(走 sub-module,規避 P2-7 shim 不穿透)
    from ui.helpers.io import oauth_state as _os
    _os.refresh_oauth_state()
    _oauth_configured = _os._oauth_configured
    _oauth_cfg = _os._oauth_cfg
    _gsa_secret = _os._gsa_secret
    _sheet_id_secret = _os._sheet_id_secret
    _get_oauth_client = _os._get_oauth_client

    with st.sidebar:
        st.markdown("## 📊 基金戰情室")
        _upd = st.session_state.get("macro_last_update")
        st.caption(f"📡 總經：{_upd.strftime('%m/%d %H:%M') if _upd else '未載入'}　|　{now_tw_fn().strftime('%m/%d %H:%M')} TW")
        st.markdown(f"<div style='background:{GH_BG_PRIMARY};border:1px solid {GH_BORDER};border-radius:8px;padding:8px 12px;font-size:11px;color:{TRAFFIC_NEUTRAL}'>App {app_version} | Engine {engine_version} | Fetcher v6.24</div>", unsafe_allow_html=True)
        # v18.277：部署 beacon — 改成動態反映 app_version，避免歡迎卡停留在舊版本誤導 user
        st.markdown(
            f"<div style='background:linear-gradient(90deg,#7c3aed,#ec4899);"
            f"border-radius:8px;padding:10px 14px;margin-top:8px;"
            f"font-size:13px;color:{WHITE};font-weight:700;text-align:center;"
            f"box-shadow:0 2px 8px rgba(124,58,237,0.4)'>"
            f"✨ {app_version}"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.divider()
        _proxy_cfg = get_proxy_config()
        _proxy_ep  = ""
        if _proxy_cfg:
            _m = re.search(r'@(.+)', _proxy_cfg.get("http",""))
            _proxy_ep = _m.group(1) if _m else "已設定"
        st.markdown(f"{'✅' if fred_key else '❌'} FRED　　{'✅' if gemini_key else '❌'} Gemini　　{'✅' if _proxy_cfg else '⚠️'} Proxy")
        st.caption(f"🔒 {_proxy_ep}" if _proxy_cfg else "⚠️ Proxy 未設定（MoneyDJ 可能被擋）")
        st.divider()
        if st.sidebar.button("🔍 測試 Proxy 連線", use_container_width=True):
            import requests as _req
            _pcfg = get_proxy_config()
            if not _pcfg:
                st.sidebar.error("Proxy 未設定")
            else:
                # v18.269：除了既有 2 個基金 source，加 4 個 FX source 一起測，讓 user 看出
                # 「網路正常但 FX 抓不到」是 source 端問題還是 endpoint 個別擋。
                _endpoints = [
                    ("MoneyDJ",     "https://www.moneydj.com/"),
                    ("TDCC",        "https://openapi.tdcc.com.tw/"),
                    ("Yahoo Chart", "https://query1.finance.yahoo.com/v8/finance/chart/USDTWD=X"),
                    ("FRED",        "https://fred.stlouisfed.org/"),
                    ("er-api.com",  "https://open.er-api.com/v6/latest/USD"),
                    ("Frankfurter", "https://api.frankfurter.app/latest"),
                ]
                # v19.173:對 429 加 1 次 fast retry (3s),對齊 production fetcher 已有 backoff 行為。
                # 原本 single-shot test 一遇 429 就顯示黃色 ⚠️,但 production fetch_url 走 2/4/8s backoff
                # 通常第二次就過(infra/proxy.py:172-181)— sidebar 假警報誤導 user 以為 production 也壞。
                import time as _time
                for _nm, _url in _endpoints:
                    def _try_get():
                        return _req.get(_url, proxies=_pcfg, timeout=25, allow_redirects=False, verify=False)
                    try:
                        _r = _try_get()
                        if _r.status_code == 429:
                            # 1 次 fast retry,通常第二次就過(Yahoo / FRED rate limit 為短時 burst)
                            _time.sleep(3)
                            _r = _try_get()
                        if _r.status_code in (200,301,302,403): st.sidebar.success(f"✅ {_nm} 可達！HTTP {_r.status_code}")
                        elif _r.status_code == 407: st.sidebar.error("❌ 407：帳密錯誤"); break
                        elif _r.status_code == 429:
                            # 重試後仍 429:user-friendly 訊息 — production fetcher 有 2/4/8s 三段 backoff,仍可用
                            st.sidebar.warning(
                                f"⚠️ {_nm} HTTP 429 (短時 rate limit) — "
                                f"production fetch_url 已含 2/4/8s 三段 backoff 自動重試,不影響實際資料載入。"
                            )
                        else: st.sidebar.warning(f"⚠️ {_nm} HTTP {_r.status_code}")
                    except _req.exceptions.ProxyError as _e: st.sidebar.error(f"❌ {_nm} ProxyError：{str(_e)[:120]}")
                    except _req.exceptions.Timeout: st.sidebar.error(f"❌ {_nm} Timeout（25s）")
                    except Exception as _e: st.sidebar.error(f"❌ {_nm}：{str(_e)[:120]}")
        if st.sidebar.button("♻️ 強制同步 GitHub 最新邏輯", use_container_width=True):
            # v18.231：原本只 st.rerun() 不查版本；user 回報 Streamlit Cloud 卡舊版按了沒用。
            # 改成比對 local HEAD vs remote main → 不同步時給 Cloud Reboot 連結（容器無法 git pull）
            import subprocess as _sp
            _repo_dir = os.path.dirname(os.path.abspath(__file__))
            def _git(args: list[str], timeout: int = 8) -> str:
                try:
                    return _sp.check_output(
                        ["git", *args], cwd=_repo_dir, timeout=timeout,
                        stderr=_sp.DEVNULL,
                    ).decode().strip()
                except Exception:
                    return ""
            with st.sidebar.status("檢查版本…", expanded=False):
                _local = _git(["rev-parse", "--short", "HEAD"]) or "(unknown)"
                _remote_raw = _git(["ls-remote", "origin", "main"], timeout=12)
                _remote = (_remote_raw.split()[0][:7] if _remote_raw else "(unknown)")
            if _local == "(unknown)":
                st.sidebar.warning("⚠️ 無法讀取本機 commit（git 不可用）")
            elif _remote == "(unknown)":
                st.sidebar.warning(f"⚠️ 無法查 remote main（網路或 git 限制）｜本機 `{_local}`")
            elif _local == _remote:
                st.sidebar.success(f"✅ 已是 main 最新版（`{_local}`）")
            else:
                st.sidebar.warning(
                    f"📦 部署 `{_local}` ← main `{_remote}`\n\n"
                    "Streamlit 不會自動 reload Python module，需重啟容器："
                )
                st.sidebar.link_button(
                    "→ Streamlit Cloud Reboot",
                    "https://share.streamlit.io",
                    use_container_width=True,
                )
                st.sidebar.caption("本機請 Ctrl+C 後 `streamlit run app.py`")

        # ── v19.63 F：全局資料健康總覽（聚合各 Tab 新鮮度 → 一眼看哪舊了）──
        st.divider()
        try:
            from ui.helpers.freshness import render_sidebar_data_health
            render_sidebar_data_health(st.session_state, now_tw=now_tw_fn)
        except Exception:
            pass  # smoke-allow-pass — sidebar 健康總覽純顯示，異常不擋主畫面

        # ── v19.59 C2：全域刷新總開關 — 清所有記憶體 + 落地快取 + 跨 Tab session 殘留 ──
        st.divider()
        st.markdown("##### 🧹 全域刷新")
        if st.button(
            "🧹 全域刷新（清所有快取 + 落地檔）",
            key="btn_global_refresh",
            use_container_width=True,
            help="v19.59 C2：清全部 TTL cache + hot_money @st.cache_data + "
                 "/tmp/fund_cache 落地檔 + 跨 Tab session 殘留。保留 OAuth/sheet "
                 "登入狀態。嚴禁清 data_cache/ 上游 cron 歷史資料倉。"
                 "清掉後下次載入各 Tab 會重打 API（請確認需要前再用）",
        ):
            try:
                from infra.cache import global_refresh_all
                _gr = global_refresh_all(session_state=st.session_state)
                st.toast(
                    f"🧹 全域刷新：TTL {_gr['ttl_cleared']} 條 / "
                    f"st_cache {_gr['st_cache_cleared']} 條 / "
                    f"落地檔 {_gr['disk_files_removed']} 個 / "
                    f"snapshot {_gr['snapshot_cleared']} 筆 / "
                    f"session {_gr['session_keys_popped']} 鍵",
                    icon="🧹",
                )
            except Exception as _e_gr:
                st.toast(f"⚠️ 全域刷新失敗：{type(_e_gr).__name__}", icon="⚠️")
            st.rerun()
        st.caption("⚠️ 會清掉所有快取，下次載入會重打 API；OAuth 登入保留")

        # ── v18.75 Google 帳號（從 Tab3 expander 搬上來，登入更顯眼）──
        st.divider()
        st.markdown("##### 🔐 Google 帳號")
        _logged_in_sb = bool(st.session_state.get("gsheet_tokens"))
        if _oauth_configured:
            if _logged_in_sb:
                st.success("🟢 已登入")
                if st.button("🚪 登出", key="btn_oauth_logout_sb",
                              use_container_width=True):
                    st.session_state.pop("gsheet_tokens", None)
                    st.session_state.pop("active_policy_id", None)
                    st.rerun()
            else:
                _login_url_sb = build_authorize_url(
                    _oauth_cfg["client_id"], _oauth_cfg["redirect_uri"])
                st.link_button("🔐 用 Google 登入", _login_url_sb,
                                use_container_width=True)
                st.caption("登入後 Tab3 即可雲端存取保單試算表")
        elif _gsa_secret and _sheet_id_secret:
            st.caption("ℹ️ 使用 Service Account（舊版單表）")
        else:
            st.caption("⚙️ OAuth Client 尚未設定 — 請至 Tab3「📊 組合基金」"
                       "→ 展開「📋 保單管理」設定")

        # ── v18.164：工作中帳本（Sheet ID 從 Tab3 expander hoist 到 sidebar）──
        if _logged_in_sb or (_gsa_secret and _sheet_id_secret):
            st.markdown("##### 📋 工作中帳本")
            _sid_default_sb = (st.session_state.get("policy_sheet_id")
                                or _sheet_id_secret or "")
            _sid_raw_sb = st.text_input(
                "Sheet ID 或完整 URL",
                value=_sid_default_sb, key="inp_sheet_id",
                help="貼 Google Sheet URL 會自動解析 ID",
            ).strip()
            _m_sb = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", _sid_raw_sb)
            _sid_sb = _m_sb.group(1) if _m_sb else _sid_raw_sb
            if _sid_sb and _sid_sb != _sid_default_sb:
                st.session_state["policy_sheet_id"] = _sid_sb
            if _sid_sb and _logged_in_sb:
                _title_cache_key = f"_t3_cur_sheet_title:{_sid_sb}"
                _cur_title_sb = st.session_state.get(_title_cache_key)
                if _cur_title_sb is None:
                    try:
                        _cur_title_sb = get_sheet_title(
                            _get_oauth_client(), _sid_sb)
                        st.session_state[_title_cache_key] = _cur_title_sb
                    except Exception:
                        _cur_title_sb = ""
                if _cur_title_sb:
                    st.caption(f"📂 **{_cur_title_sb}**")
                else:
                    st.caption(f"📂 ID `{_sid_sb[:14]}…`")
            elif not _sid_sb and _logged_in_sb:
                st.caption("⚠️ 尚未指定 — 至 Tab3「✨ 新增帳本」建立或挑一本")
