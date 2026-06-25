"""ui/helpers/data_registry.py — 全域資料健康總表更新（v18.136 從 app.py 搬入）

來自 app.py:520-893。`_update_data_registry()` 掃 session_state 中所有已載入
DataFrame / series，計算各資料源的「新鮮度」（依 FRED next_release_date 動態）+
寫入 st.session_state.data_registry，供 Tab5「全域資料健康總表」使用。
"""
from __future__ import annotations

import datetime
import os

import streamlit as st

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED
import pandas as pd

from models.policy import fund_pk_str
from shared.fred_series import (
    FRED_CCSA,
    FRED_CFNAI,
    FRED_CPI,
    FRED_DRTSCILM,
    FRED_FED_BS,
    FRED_FED_FUNDS,
    FRED_HSN1F,
    FRED_HY_SPREAD,
    FRED_ICSA,
    FRED_M2,
    FRED_M2_WEEKLY,
    FRED_NAPM,
    FRED_PERMIT,
    FRED_PPI,
    FRED_SAHM,
    FRED_T10Y2Y,
    FRED_T10Y3M,
    FRED_T5YIE,
    FRED_UMCSENT,
    FRED_UNRATE,
)


def _sync_invest_twd_from_ledgers() -> None:
    """v18.52: 落帳後把 ledger.net_investment_twd 灌回 portfolio_funds[i].invest_twd，
    讓上方 KPI / 月配息估算 / 圓餅圖共用同一筆「實際投入」資料源。

    v18.139（清單 14）：從 app.py 搬至 ui/helpers/data_registry.py（同類
    session_state ↔ portfolio_funds 同步邏輯，跟 _update_data_registry 同檔）。
    """
    for _i, _f in enumerate(st.session_state.get("portfolio_funds", []) or []):
        _pk_f = fund_pk_str(_f)
        _l = (st.session_state.get("t7_ledgers", {}) or {}).get(_pk_f)
        if _l is not None and getattr(_l, "position", None) is not None:
            st.session_state.portfolio_funds[_i]["invest_twd"] = round(
                _l.position.net_investment_twd, 2
            )


def _update_data_registry():
    """掃描 session_state，將所有已載入的 DataFrame 時間戳記寫入 data_registry。"""

    # ── 頻率對照表 (indicator key → 更新頻率) ─────────────────────
    _FREQ: dict[str, str] = {
        # 日頻（yfinance 市場資料）
        "VIX":          "daily",
        "DXY":          "daily",
        "ADL":          "daily",
        "COPPER":       "daily",
        # 日頻（FRED 每交易日）
        "YIELD_10Y2Y":  "daily",
        "YIELD_10Y3M":  "daily",
        "HY_SPREAD":    "daily",
        # 週頻
        "FED_BS":       "weekly",
        "JOBLESS":      "weekly",
        # v16.1 高頻替代源
        "INFL_EXP_5Y":  "daily",       # T5YIE 日頻 5Y 通膨預期
        "CONT_CLAIMS":  "weekly",      # CCSA 週頻持續失業金
        # ⚠️ WM2NS 自 2021/02/23 H.6 release 改為月頻發布（雖然數據粒度為週），
        #    分類為 monthly 以符合實際更新節奏，避免 30 天延遲被誤判紅燈。
        "M2_WEEKLY":    "monthly",     # WM2NS 週數據但月頻發布
        # 月頻（FRED 月度調查/統計）
        "SAHM":         "monthly",
        "PMI":          "monthly",
        "CPI":          "monthly",
        "UNEMPLOYMENT": "monthly",
        "M2":           "monthly",
        "FED_RATE":     "monthly",
        "PPI":          "monthly",
        "CONSUMER_CONF":"monthly",
        "NEW_HOME":     "monthly",
        # v16.1 高頻替代源（月頻）
        "LEI":          "monthly",     # CFNAI 月頻領先指標（USSLIND 已停更）
        "PERMIT_HOUSING":"monthly",    # PERMIT 月頻建照
        # v19.113 China macro(方向 B)— OECD MEI 月頻發布,延遲 ~60 天
        "CHN_CLI":      "monthly",
        "CHN_PMI":      "monthly",
        "CHN_CPI":      "monthly",
        "CHN_M2":       "monthly",
        "USDCNY":       "daily",       # DEXCHUS 日頻
        # 季頻（FRED 季度調查）
        "SLOOS":        "quarterly",
    }

    # ── v18.3 indicator_key → FRED series_id（供 next_release_date 動態查詢）
    _FRED_SERIES_MAP: dict[str, str] = {
        "PMI":          FRED_NAPM,        # 隔月 1 日 release
        "CPI":          FRED_CPI,         # 隔月 ~13 日
        "UNEMPLOYMENT": FRED_UNRATE,      # 隔月 1st Friday
        "M2":           FRED_M2,
        "M2_WEEKLY":    FRED_M2_WEEKLY,
        "FED_RATE":     FRED_FED_FUNDS,
        "PPI":          FRED_PPI,
        "CONSUMER_CONF":FRED_UMCSENT,     # 隔月 last Friday
        "NEW_HOME":     FRED_HSN1F,       # 隔月 ~25 日
        "LEI":          FRED_CFNAI,       # 對齊 macro_engine.py 實際抓的 series
        "PERMIT_HOUSING":FRED_PERMIT,
        "SAHM":         FRED_SAHM,
        "SLOOS":        FRED_DRTSCILM,
        "JOBLESS":      FRED_ICSA,
        "CONT_CLAIMS":  FRED_CCSA,
        "FED_BS":       FRED_FED_BS,
        "HY_SPREAD":    FRED_HY_SPREAD,
        "YIELD_10Y2Y":  FRED_T10Y2Y,
        "YIELD_10Y3M":  FRED_T10Y3M,
        "INFL_EXP_5Y":  FRED_T5YIE,
        # v19.113 — China macro(方向 B):FRED OECD MEI 收錄,月後 ~60 天延遲
        "CHN_CLI":      "CHNLOLITONOSTSAM",   # OECD 中國綜合領先指標
        "CHN_PMI":      "BSCICP03CNM665S",    # OECD 中國商業信心(PMI proxy)
        "CHN_CPI":      "CPALTT01CNM659N",    # OECD 中國 CPI YoY
        "CHN_M2":       "MABMM301CNM189S",    # 中國 M2 廣義貨幣
        "USDCNY":       "DEXCHUS",            # CNY/USD 日匯率(已生產驗證)
    }

    # ── v18.3 動態 next_release_date 查詢（cache 30 天）
    try:
        from repositories.macro_repository import fred_get_next_release_date as _fred_next_rel
    except Exception:
        _fred_next_rel = None
    _fred_key = (st.secrets.get("FRED_API_KEY","")
                 or os.environ.get("FRED_API_KEY",""))

    def _freshness(date_str: str, freq: str,
                   indicator_key: str = "") -> tuple[str, str, str]:
        """回傳 (icon, label, hex_color)。

        v18.3：月度 / 季度指標若映射到已知 FRED series，呼叫 fred_get_next_release_date
        判斷是否已過下次預定 release 日；
        - today < next_release         → 🟢 FRESH (尚未到 release 日,屬於正常 lag)
        - next_release ≤ today ≤ +5 天  → 🟡 DUE   (release 期已到,容忍 5 天微 delay)
        - today > next_release + 5 天   → 🔴 STALE (真延遲)
        API 失敗則 fallback 到舊的「天數閾值」邏輯。
        """
        try:
            dt  = pd.to_datetime(date_str).date()
            age = max(0, (datetime.date.today() - dt).days)
        except Exception:
            return "⬜", "未知日期", "#555555"

        # ── v18.20：月度 / 季度 / 週度皆優先用 FRED next_release_date 動態判斷
        # release 當日（+0~+1）顯示綠燈而非黃燈（資料公佈前不算延遲）
        if freq in ("monthly", "quarterly", "weekly") and _fred_next_rel and _fred_key:
            sid = _FRED_SERIES_MAP.get(indicator_key)
            if sid:
                nrd = _fred_next_rel(sid, _fred_key)
                if nrd is not None:
                    today = datetime.date.today()
                    delta_to_release = (today - nrd).days
                    if today < nrd:
                        return ("🟢",
                                f"正常（下次 release {nrd.isoformat()}）",
                                MATERIAL_GREEN)
                    # v18.20: +0~+1 為 release 當日 / 隔日，資料尚未發布即正常 → 🟢
                    if delta_to_release <= 1:
                        return ("🟢",
                                f"今日/隔日 release（{nrd.isoformat()}，發布前正常 lag）",
                                MATERIAL_GREEN)
                    # +2~+5: 微 lag，仍可接受 → 🟡
                    if delta_to_release <= 5:
                        return ("🟡",
                                f"release lag {delta_to_release} 天（預期 {nrd.isoformat()}）",
                                MATERIAL_ORANGE)
                    return ("🔴",
                            f"真延遲 {delta_to_release} 天（預期 {nrd.isoformat()}）",
                            MATERIAL_RED)
            # 沒映射 / API 失敗 → 落到下方 fallback

        if freq == "daily":
            if age <= 3:
                return "🟢", f"最新（{age}天前）", MATERIAL_GREEN
            if age <= 7:
                return "🟡", f"延遲（{age}天前）", MATERIAL_ORANGE
            return "🔴", f"過舊（{age}天）", MATERIAL_RED

        if freq == "weekly":
            # fallback：FRED release_dates 不可用時才走（v18.20 統一用 fallback 標籤）
            _fb_tag = "fallback" if (_fred_next_rel and _fred_key) else "舊閾值"
            if age <= 10:
                return "🟢", f"本週（{age}天前 / {_fb_tag}）", MATERIAL_GREEN
            if age <= 21:
                return "🟡", f"延遲（{age}天前 / {_fb_tag}）", MATERIAL_ORANGE
            return "🔴", f"過舊（{age}天 / {_fb_tag}）", MATERIAL_RED

        if freq == "monthly":
            # fallback：FRED API 失敗才走這邊（v16.1 寬鬆閾值保留）
            # v18.4 補上 "fallback" 字樣，使用者看到就知道走了舊判斷邏輯
            _fb_tag = "fallback" if (_fred_next_rel and _fred_key) else "舊閾值"
            if age <= 60:
                return "🟢", f"本/上月（{age}天前 / {_fb_tag}）", MATERIAL_GREEN
            if age <= 90:
                return "🟡", f"延遲（{age}天前 / {_fb_tag}）", MATERIAL_ORANGE
            return "🔴", f"過舊（{age}天 / {_fb_tag}）", MATERIAL_RED

        if freq == "quarterly":
            _fb_tag = "fallback" if (_fred_next_rel and _fred_key) else "舊閾值"
            if age <= 95:
                return "🟢", f"本/上季（{age}天前 / {_fb_tag}）", MATERIAL_GREEN
            if age <= 140:
                return "🟡", f"延遲（{age}天前 / {_fb_tag}）", MATERIAL_ORANGE
            return "🔴", f"過舊（{age}天 / {_fb_tag}）", MATERIAL_RED

        # nav / 未知 → 按日頻處理但容忍 7 天（T+1/T+2 報價）
        if age <= 7:
            return "🟢", f"最新（{age}天前）", MATERIAL_GREEN
        if age <= 14:
            return "🟡", f"延遲（{age}天前）", MATERIAL_ORANGE
        return "🔴", f"過舊（{age}天）", MATERIAL_RED

    reg = {}

    # 1. 總經指標 series (macro_engine indicators)
    ind = st.session_state.get("indicators") or {}
    for key, data in ind.items():
        if not isinstance(data, dict):
            continue
        series = data.get("series")
        name   = data.get("name", key)
        latest_date = data.get("date", "N/A") or "N/A"
        count  = 0
        sorted_s = None
        if series is not None:
            try:
                s = pd.Series(series).dropna().sort_index(ascending=False)
                count = len(s)
                if count > 0:
                    latest_date = str(s.index[0])[:10]
                sorted_s = s
            except Exception:
                pass  # smoke-allow-pass
        freq = _FREQ.get(key, "monthly")
        icon, flabel, fcolor = _freshness(latest_date, freq, indicator_key=key)
        reg[f"總經_{key}"] = {
            "label":       name,
            "source":      "FRED/yfinance",
            "latest_date": latest_date,
            "count":       count,
            "series":      sorted_s,
            "freq":        freq,
            "fresh_icon":  icon,
            "fresh_label": flabel,
            "fresh_color": fcolor,
        }

    # 2. 單一基金淨值 series
    fd = st.session_state.get("fund_data")
    if isinstance(fd, dict):
        s  = fd.get("series")
        fn = fd.get("fund_name") or fd.get("full_key") or "基金"
        latest_date = "N/A"
        count = 0
        sorted_s = None
        if s is not None:
            try:
                s2 = pd.Series(s).dropna().sort_index(ascending=False)
                count = len(s2)
                if count > 0:
                    latest_date = str(s2.index[0])[:10]
                sorted_s = s2
            except Exception:
                pass  # smoke-allow-pass
        icon, flabel, fcolor = _freshness(latest_date, "nav")
        reg[f"基金_{fn}_淨值"] = {
            "label":       f"{fn} 淨值",
            "source":      "MoneyDJ",
            "latest_date": latest_date,
            "count":       count,
            "series":      sorted_s,
            "freq":        "nav",
            "fresh_icon":  icon,
            "fresh_label": flabel,
            "fresh_color": fcolor,
        }

    # 3. 組合基金淨值 series
    for f in (st.session_state.get("portfolio_funds") or []):
        if not f.get("loaded"):
            continue
        fn = f.get("name") or f.get("code") or "基金"
        s  = f.get("series")
        latest_date = "N/A"
        count = 0
        sorted_s = None
        if s is not None:
            try:
                s2 = pd.Series(s).dropna().sort_index(ascending=False)
                count = len(s2)
                if count > 0:
                    latest_date = str(s2.index[0])[:10]
                sorted_s = s2
            except Exception:
                pass  # smoke-allow-pass
        icon, flabel, fcolor = _freshness(latest_date, "nav")
        reg[f"組合_{fn}_淨值"] = {
            "label":       f"{fn} 淨值",
            "source":      "MoneyDJ",
            "latest_date": latest_date,
            "count":       count,
            "series":      sorted_s,
            "freq":        "nav",
            "fresh_icon":  icon,
            "fresh_label": flabel,
            "fresh_color": fcolor,
        }

    # v19.63 §4a 台灣本地總經（PMI / NDC / 出口 YoY / 外資連續日數）
    # 來源：services.macro_tw_local_fetch + tw_macro.fetch_foreign_consecutive_days
    # 由 ui/tab1_macro.py 在抓取後 stash 至 _macro_tw_local。
    _tw_local = st.session_state.get("_macro_tw_local") or {}
    if isinstance(_tw_local, dict) and _tw_local:
        _tw_specs = [
            ("總經_TW_PMI", "🇹🇼 台灣製造業 PMI",
             "FinMind TaiwanMacroEconomics",
             _tw_local.get("tw_pmi", {}).get("value"),
             _tw_local.get("tw_pmi", {}).get("date", ""), "monthly"),
            ("總經_NDC_SIGNAL", "🇹🇼 NDC 景氣對策信號",
             "FinMind TaiwanMacroEconomics",
             _tw_local.get("ndc_signal", {}).get("score"),
             _tw_local.get("ndc_signal", {}).get("date", ""), "monthly"),
            ("總經_TW_EXPORT_YOY", "🇹🇼 台灣出口 YoY",
             "FinMind TaiwanMacroEconomics",
             _tw_local.get("tw_export", {}).get("yoy"),
             _tw_local.get("tw_export", {}).get("date", ""), "monthly"),
            ("總經_TW_FI_STREAK", "🇹🇼 外資連續日數",
             "FinMind TaiwanStockTotalInstitutionalInvestors",
             _tw_local.get("fi_streak", {}).get("consec_days"),
             _tw_local.get("fi_streak", {}).get("date", ""), "daily"),
        ]
        for _k, _lbl, _src, _v, _d, _fq in _tw_specs:
            if _v is None or not _d:
                continue
            _ic, _fl, _fc = _freshness(_d, _fq)
            reg[_k] = {
                "label":       _lbl,
                "source":      _src,
                "latest_date": _d,
                "count":       1,
                "series":      None,
                "freq":        _fq,
                "fresh_icon":  _ic,
                "fresh_label": _fl,
                "fresh_color": _fc,
            }

    # v19.63 §4b 外資/投信買賣超 + USDTWD（hot_money.py stash 至 _macro_hot_money）
    _hm = st.session_state.get("_macro_hot_money") or {}
    if isinstance(_hm, dict) and _hm.get("date"):
        _hm_ic, _hm_fl, _hm_fc = _freshness(_hm.get("date", ""), "daily")
        reg["總經_HOT_MONEY_FX"] = {
            "label":       "🇹🇼 外資買賣超 × USDTWD 同步判讀",
            "source":      "FinMind 外資 / yfinance USDTWD",
            "latest_date": _hm.get("date", ""),
            "count":       1,
            "series":      None,
            "freq":        "daily",
            "fresh_icon":  _hm_ic,
            "fresh_label": _hm_fl,
            "fresh_color": _hm_fc,
        }

    # v19.140 §3a 短線風險雷達 10 燈（services.risk_radar.detect_risk_radar）
    # ui/tab1_macro.py stash 至 _radar_v1921_top = (radar_dict, summary_dict)。
    # 修正:之前 user 看到雷達兩盞燈 ⬜ 無資料但資料診斷裡找不到 → 因 registry
    # 完全沒讀 _radar_v1921_top。每盞燈現在會在診斷表出現,失敗者帶 note
    # (含 per-layer fail trace,可看出哪層 fallback 真的炸了)。§1 Fail Loud:
    # 失敗顯式 🔴 + 失敗原因,不偽綠。
    _radar_top = st.session_state.get("_radar_v1921_top")
    _radar_dict = None
    if isinstance(_radar_top, tuple) and len(_radar_top) >= 1:
        _radar_dict = _radar_top[0]
    if isinstance(_radar_dict, dict) and _radar_dict:
        _LIGHT_LABELS = {
            "vix_level":       "🚨 雷達 1｜VIX 恐慌指數",
            "vix_term_struct": "🚨 雷達 2｜VIX 期限結構（VIX/VIX3M）",
            "hy_oas_delta":    "🚨 雷達 3｜HY 信用日變化",
            "yield_10y_shock": "🚨 雷達 4｜10Y 殖利率衝擊",
            "move_level":      "🚨 雷達 5｜MOVE 債市波動",
            "spx_trend_break": "🚨 雷達 6｜SPX 均線破口",
            "sox_drop":        "🚨 雷達 7｜SOX 半導體",
            "sector_rotation": "🚨 雷達 8｜防禦/攻擊輪動",
            "put_call_ratio":  "🚨 雷達 9｜Put/Call 比率",
            "asia_overnight":  "🚨 雷達 10｜亞洲夜盤",
        }
        for _lk in _LIGHT_LABELS:
            _entry = _radar_dict.get(_lk) or {}
            if not isinstance(_entry, dict):
                continue
            _val = _entry.get("value")
            _src = _entry.get("label") or "—"
            _note = _entry.get("note") or ""
            _signal = _entry.get("signal") or ""
            # 已取得：value 不為 None → 🟢；否則 🔴 + note 截斷顯示
            if _val is not None:
                _r_ic, _r_fl, _r_fc = "🟢", f"已取得（{_signal}）", MATERIAL_GREEN
                _r_date = "今日"
                _r_count = 1
            else:
                _r_ic, _r_fl, _r_fc = "🔴", (_note[:100] or "抓取失敗"), MATERIAL_RED
                _r_date = "—"
                _r_count = 0
            reg[f"雷達_{_lk}"] = {
                "label":       _LIGHT_LABELS[_lk],
                "source":      _src,
                "latest_date": _r_date,
                "count":       _r_count,
                "series":      None,
                "freq":        "daily",
                "fresh_icon":  _r_ic,
                "fresh_label": _r_fl,
                "fresh_color": _r_fc,
            }

    # 4. RSS 國際財經新聞 (fetch_market_news)
    # ⚠️ RSS feedparser.published 格式為 RFC 2822（"Wed, 06 May 2026 14:30:00 +0000"），
    #    舊版用 [:10] 切片得到 "Wed, 06 Ma" 無法解析 → 顯示「未知日期」。
    #    改用 pd.to_datetime 自動偵測格式（支援 RFC 2822 / ISO / unix）。
    _news = st.session_state.get("news_items") or []
    if _news:
        _latest = "N/A"
        try:
            _parsed_dates = []
            for n in _news:
                _raw = n.get("published") or n.get("published_parsed") or ""
                if not _raw:
                    continue
                _dt = pd.to_datetime(str(_raw), errors="coerce", utc=True)
                if pd.notna(_dt):
                    _parsed_dates.append(_dt.strftime("%Y-%m-%d"))
            if _parsed_dates:
                _latest = max(_parsed_dates)
        except Exception:
            pass  # smoke-allow-pass
        _icon, _flbl, _fcol = _freshness(_latest, "daily")
        reg["新聞_國際財經RSS"] = {
            "label":       "國際財經新聞 (8 RSS)",
            "source":      "Reuters/MarketWatch/FT/Yahoo/Investing/CNBC",
            "latest_date": _latest,
            "count":       len(_news),
            "series":      None,
            "freq":        "daily",
            "fresh_icon":  _icon,
            "fresh_label": _flbl,
            "fresh_color": _fcol,
        }

    # 5. 基金子資料（配息 / 前十大持股 / 產業配置 / TER）— current_fund + portfolio_funds
    def _register_fund_subdata(prefix: str, fund: dict, raw: dict, default_name: str):
        fn = (fund.get("fund_name") or fund.get("name")
              or fund.get("full_key") or fund.get("code") or default_name)

        # 5a. 配息 (MoneyDJ wb05)
        _divs = fund.get("dividends") or raw.get("dividends") or []
        if isinstance(_divs, list) and _divs:
            _dlatest = "N/A"
            try:
                _dts = [str(d.get("date") or d.get("payment_date") or "")[:10] for d in _divs]
                _dts = [x for x in _dts if x]
                if _dts:
                    _dlatest = max(_dts)
            except Exception:
                pass  # smoke-allow-pass
            _ic, _lb, _co = _freshness(_dlatest, "monthly")
            reg[f"{prefix}_{fn}_配息"] = {
                "label":       f"{fn} 配息紀錄",
                "source":      "MoneyDJ wb05",
                "latest_date": _dlatest,
                "count":       len(_divs),
                "series":      None,
                "freq":        "monthly",
                "fresh_icon":  _ic,
                "fresh_label": _lb,
                "fresh_color": _co,
            }

        # 5b/5c/5d. 持股 / 產業 / TER (MoneyDJ yp004002 + wb05)
        _hold = raw.get("holdings") or {}
        if isinstance(_hold, dict):
            _tops  = _hold.get("top_holdings") or []
            _sects = _hold.get("sector_alloc") or []
            _ter   = _hold.get("ter") or raw.get("ter")

            if _tops:
                reg[f"{prefix}_{fn}_前十大持股"] = {
                    "label":       f"{fn} 前十大持股",
                    "source":      "MoneyDJ yp004002",
                    "latest_date": "本月",
                    "count":       len(_tops),
                    "series":      None,
                    "freq":        "monthly",
                    "fresh_icon":  "🟢",
                    "fresh_label": "已取得",
                    "fresh_color": MATERIAL_GREEN,
                }
            if _sects:
                reg[f"{prefix}_{fn}_產業配置"] = {
                    "label":       f"{fn} 產業配置",
                    "source":      "MoneyDJ yp004002",
                    "latest_date": "本月",
                    "count":       len(_sects),
                    "series":      None,
                    "freq":        "monthly",
                    "fresh_icon":  "🟢",
                    "fresh_label": "已取得",
                    "fresh_color": MATERIAL_GREEN,
                }
            if _ter not in (None, "", 0):
                reg[f"{prefix}_{fn}_TER"] = {
                    "label":       f"{fn} 總費用率 TER",
                    "source":      "MoneyDJ wb05",
                    "latest_date": "年度",
                    "count":       1,
                    "series":      None,
                    "freq":        "monthly",
                    "fresh_icon":  "🟢",
                    "fresh_label": "已取得",
                    "fresh_color": MATERIAL_GREEN,
                }

        # v19.63 5e. 基金績效 wb01（1Y/3Y/5Y 含息報酬）
        _perf = raw.get("perf") or {}
        if isinstance(_perf, dict) and any(_perf.get(_k) is not None
                                           for _k in ("1Y", "3Y", "5Y")):
            reg[f"{prefix}_{fn}_績效"] = {
                "label":       f"{fn} 績效 (1Y/3Y/5Y)",
                "source":      "MoneyDJ wb01",
                "latest_date": "本月",
                "count":       sum(1 for _k in ("1Y", "3Y", "5Y")
                                   if _perf.get(_k) is not None),
                "series":      None,
                "freq":        "monthly",
                "fresh_icon":  "🟢",
                "fresh_label": "已取得",
                "fresh_color": MATERIAL_GREEN,
            }

        # v19.63 5f. 基金風險指標 wb07（標準差/Sharpe/Alpha/Beta）
        _risk = raw.get("risk_metrics") or {}
        _rtbl = _risk.get("risk_table") if isinstance(_risk, dict) else None
        if isinstance(_rtbl, dict) and _rtbl:
            reg[f"{prefix}_{fn}_風險指標"] = {
                "label":       f"{fn} 風險指標 (σ/Sharpe/Alpha/Beta)",
                "source":      "MoneyDJ wb07",
                "latest_date": "本月",
                "count":       len(_rtbl),
                "series":      None,
                "freq":        "monthly",
                "fresh_icon":  "🟢",
                "fresh_label": "已取得",
                "fresh_color": MATERIAL_GREEN,
            }

    _cf = st.session_state.get("current_fund") or {}
    if _cf:
        _register_fund_subdata("基金", _cf, _cf, "個別基金")
    _fd2 = st.session_state.get("fund_data") or {}
    if isinstance(_fd2, dict) and _fd2:
        _register_fund_subdata("基金", _fd2, _fd2, "個別基金")
    for _pf in (st.session_state.get("portfolio_funds") or []):
        if not _pf.get("loaded"):
            continue
        _raw = _pf.get("moneydj_raw") or {}
        _register_fund_subdata("組合", _pf, _raw, _pf.get("code","基金"))

    st.session_state["data_registry"] = reg
