"""
services/macro_service.py — 總經位階 + 拐點偵測（v11.0 從 macro_engine.py 搬入）

修正：殖利率利差使用 merge_asof（日頻 vs 月頻對齊）
新增：指標加權評分、衰退機率、景氣時鐘 / Sankey 因果鏈 / 變數重要性

v11.0 分層歸位：本檔屬於 Service Layer，業務邏輯 + 編排。
資料抓取走 repositories.macro_repository（即原 macro_core.py，已 B-5 搬遷）。
向後相容：根目錄 macro_engine.py 保留 `from services.macro_service import *` shim，
        E 階段收尾後 shim 刪除。
"""
import pandas as pd, numpy as np, streamlit as st, math
from repositories.macro_repository import fetch_fred, fetch_yf_close, fetch_ism_pmi

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
ENGINE_VERSION = "v18.2_tw_macro"
_INDICATOR_SNAPSHOT: dict = {}

def _fred(sid, key, n=250):
    """[NAS Proxy 遷移] 薄殼委派給 macro_core.fetch_fred()。
    原 requests.get 直連已改為 proxy_helper.fetch_url,確保走 NAS 中繼站。
    保留同名同 signature,呼叫端無需變更。"""
    return fetch_fred(sid, key, n=n)

def _yf_s(ticker, period="2y"):
    """[NAS Proxy 遷移] 薄殼委派給 macro_core.fetch_yf_close()。
    原 yfinance .history() 不走 proxy,易遭 Yahoo 限流;改打 Chart REST API
    透過 NAS 中繼,取得台灣 IP 出口。"""
    return fetch_yf_close(ticker, range_=period)

def _trend(vals):
    if len(vals) < 3: return ""
    diffs = [vals[i]-vals[i-1] for i in range(1, len(vals))]
    pos = sum(1 for d in diffs if d > 0); neg = sum(1 for d in diffs if d < 0)
    if pos >= len(diffs)-1: return "持續上升 ↑"
    if neg >= len(diffs)-1: return "持續下降 ↓"
    return "最近反彈 ↗" if diffs[-1] > 0 else "最近回落 ↘"

def _safe_last(df, n=2):
    if df.empty or len(df) < n: return [None]*n
    v = df["value"].tolist()
    return [v[-i] for i in range(1, n+1)]

def _spread_series(df_long, df_short, n_pts=60):
    if df_long.empty or df_short.empty: return pd.Series(dtype=float)
    dl = df_long[["date","value"]].set_index("date").rename(columns={"value":"v_l"}).copy()
    ds = df_short[["date","value"]].set_index("date").rename(columns={"value":"v_s"}).copy()
    dl_m = dl.resample("ME").last().ffill()
    ds_m = ds.resample("ME").last().ffill()
    merged = dl_m.join(ds_m, how="inner").dropna()
    if merged.empty:
        dl2 = df_long[["date","value"]].rename(columns={"value":"v_l"}).sort_values("date")
        ds2 = df_short[["date","value"]].rename(columns={"value":"v_s"}).sort_values("date")
        m = pd.merge_asof(dl2, ds2, on="date", tolerance=pd.Timedelta("40d"), direction="backward").dropna()
        m = m.set_index("date")
        return (m["v_l"] - m["v_s"]).tail(n_pts)
    return (merged["v_l"] - merged["v_s"]).tail(n_pts)

def recession_probability(spread_10y3m):
    """用 10Y-3M 利差做 logistic 回歸估算衰退機率"""
    if spread_10y3m is None: return None
    logit = -1.5 * spread_10y3m - 0.8
    return round(1 / (1 + math.exp(-logit)) * 100, 1)

def _detect_inflection(indicators):
    signals = []; score = 0
    def _chk(key, attr="value"): return indicators.get(key,{}).get(attr)

    pmi_v = _chk("PMI"); pmi_p = _chk("PMI","prev")
    if pmi_v and pmi_p:
        if pmi_v < 50 and pmi_v > pmi_p:
            signals.append({"type":"buy","text":f"PMI {pmi_v:.1f} 收縮區但止跌反彈（+{pmi_v-pmi_p:.1f}）— 復甦訊號"}); score += 2
        elif pmi_v >= 50 and pmi_v > pmi_p:
            signals.append({"type":"bull","text":f"PMI {pmi_v:.1f} 擴張且上升"}); score += 1
        elif pmi_v >= 55 and pmi_v < pmi_p:
            signals.append({"type":"warn","text":f"PMI {pmi_v:.1f} 高位回落，景氣可能見頂"}); score -= 1

    y22 = indicators.get("YIELD_10Y2Y",{})
    v22 = y22.get("value"); p22 = y22.get("prev")
    if v22 is not None:
        if v22 < 0: signals.append({"type":"warn","text":f"10Y-2Y 倒掛 {v22:.3f}%，衰退信號"}); score -= 2
        elif v22 >= 0 and p22 is not None and p22 < 0:
            signals.append({"type":"buy","text":f"⚡ 10Y-2Y 由負翻正（{v22:.3f}%）— 策略3 最強黃金買點！"}); score += 4
        elif v22 > 0.5: signals.append({"type":"bull","text":f"10Y-2Y 正斜率 {v22:.3f}%"}); score += 1

    y3m = indicators.get("YIELD_10Y3M",{})
    v3m = y3m.get("value"); p3m = y3m.get("prev")
    if v3m is not None:
        if v3m < 0: signals.append({"type":"warn","text":f"10Y-3M 倒掛 {v3m:.3f}%"}); score -= 2
        elif v3m >= 0 and p3m is not None and p3m < 0:
            signals.append({"type":"buy","text":f"⚡ 10Y-3M 翻正（{v3m:.3f}%）— 降息確認"}); score += 3

    cpi_v = _chk("CPI"); cpi_t = indicators.get("CPI",{}).get("trend","")
    if cpi_v:
        if cpi_v > 4.0 and "下降" in cpi_t: signals.append({"type":"buy","text":f"⚡ CPI {cpi_v:.1f}% 高位但回落 — 落後指標見頂"}); score += 3
        elif cpi_v > 4.0: signals.append({"type":"warn","text":f"CPI {cpi_v:.1f}% 高位未降，緊縮壓力"}); score -= 2
        elif 1.5 <= cpi_v <= 3.0: signals.append({"type":"bull","text":f"CPI {cpi_v:.1f}% 回落至合理區間"}); score += 2

    fed_v = _chk("FED_RATE"); fed_p = _chk("FED_RATE","prev")
    if fed_v is not None and fed_p is not None:
        if fed_v < fed_p: signals.append({"type":"buy","text":f"⚡ 降息（{fed_p:.2f}%→{fed_v:.2f}%）— 資金行情"}); score += 3
        elif fed_v > fed_p: signals.append({"type":"warn","text":f"升息（{fed_p:.2f}%→{fed_v:.2f}%）"}); score -= 2

    vix_v = _chk("VIX")
    if vix_v:
        if vix_v > 30: signals.append({"type":"buy","text":f"VIX {vix_v:.1f} 恐慌高位 — 逢低加碼時機"}); score += 2
        elif vix_v < 15: signals.append({"type":"warn","text":f"VIX {vix_v:.1f} 過低，市場過樂觀"}); score -= 1

    jb_v = _chk("JOBLESS"); jb_p = _chk("JOBLESS","prev")
    if jb_v and jb_p:
        # 單位：萬人（macro_engine 已統一在 fetch_all_indicators 將 ICSA/10000）
        if jb_v < jb_p and jb_v < 25: signals.append({"type":"bull","text":f"初領失業金 {jb_v:.1f} 萬 改善"}); score += 1
        elif jb_v > 30: signals.append({"type":"warn","text":f"初領失業金 {jb_v:.1f} 萬 高位"}); score -= 1

    # v18.250 新增：HY Spread 由高位回落（信用拐點）
    hy_v = _chk("HY_SPREAD"); hy_p = _chk("HY_SPREAD","prev")
    if hy_v is not None and hy_p is not None:
        if hy_p >= 6.0 and hy_v < hy_p:
            signals.append({"type":"buy","text":f"⚡ HY 利差 {hy_p:.2f}%→{hy_v:.2f}% 高位首度回落 — 信用拐點"}); score += 3
        elif hy_p >= 4.0 and hy_v < hy_p - 0.3:
            signals.append({"type":"buy","text":f"HY 利差 {hy_v:.2f}% 明顯收斂（-{hy_p-hy_v:.2f}pp）— risk-on 醞釀"}); score += 1

    # v18.250 新增：薩姆規則由觸發→解除（衰退結束拐點）
    sahm_v = _chk("SAHM"); sahm_p = _chk("SAHM","prev")
    if sahm_v is not None:
        if sahm_p is not None and sahm_p >= 0.5 and sahm_v < 0.5:
            signals.append({"type":"buy","text":f"⚡ 薩姆規則 {sahm_p:.2f}→{sahm_v:.2f} 跌破 0.5 — 衰退警報解除拐點"}); score += 4
        elif sahm_v >= 0.5:
            signals.append({"type":"warn","text":f"薩姆規則 {sahm_v:.2f} ≥0.5 衰退警報中"}); score -= 2

    # v18.250 新增：CFNAI 領先指標由負轉正（領先翻揚拐點）
    lei_v = _chk("LEI"); lei_p = _chk("LEI","prev")
    if lei_v is not None and lei_p is not None:
        if lei_v > 0 and lei_p <= 0:
            signals.append({"type":"buy","text":f"⚡ CFNAI 領先 {lei_p:+.2f}→{lei_v:+.2f} 由負轉正 — 景氣翻揚拐點"}); score += 3
        elif lei_v < -0.7:
            signals.append({"type":"warn","text":f"CFNAI {lei_v:+.2f} < -0.7 強烈衰退"}); score -= 2

    if fed_v is not None and fed_p is not None and fed_v <= fed_p and fed_p > 0 and \
       cpi_v and cpi_v < 3.5 and "下降" in cpi_t:
        signals.append({"type":"buy","text":"⭐ MK黃金拐點：CPI+Fed Rate 雙雙見頂回落，勝率最高！"}); score += 5

    if score >= 8:   infl = {"label":"🚀 強力買進拐點","color":"#00c853","desc":"多項指標同時確認，景氣最佳買點"}
    elif score >= 4: infl = {"label":"✅ 買進拐點形成","color":"#69f0ae","desc":"落後見頂 + 領先反彈，建議逢低布局"}
    elif score >= 1: infl = {"label":"👀 觀察（偏多）","color":"#ff9800","desc":"部分訊號出現，持續觀察"}
    elif score >= -2:infl = {"label":"⚖️ 中性整理","color":"#888888","desc":"指標分歧，維持資產配置"}
    elif score >= -5:infl = {"label":"⚠️ 謹慎偏空","color":"#ff7043","desc":"落後指標未見頂，降低股票型比重"}
    else:            infl = {"label":"🔴 空頭拐點","color":"#f44336","desc":"確認衰退，優先貨幣型與投資等級債"}
    return {"inflection":infl,"signals":signals,"infl_score":score}


def fetch_all_indicators(fred_api_key):
    R = {}

    # ── PMI（v2.1 改用共用函式 fetch_ism_pmi 6 段備援 + 90 天時效檢查）──
    #   舊版直接拿 FRED NAPM 末筆值，會誤用 2016-08 停更後的死值欺騙 UI；
    #   改呼叫 macro_core.fetch_ism_pmi()，備援順序：
    #   NAPM/ISPMANPMI（時效檢查）→ MacroMicro → ISM World → DBnomics →
    #   Phil Fed Diffusion（轉 PMI 刻度，相關性 0.85）→ OECD US BCI（最後手段）
    pmi = fetch_ism_pmi(fred_api_key)
    if pmi.get("value") is not None:
        v = float(pmi["value"])
        vals_list = pmi.get("values") or [v]
        prev = float(vals_list[-2]) if len(vals_list) >= 2 else None
        s = None
        if pmi.get("dates") and pmi.get("values"):
            s = pd.Series(
                [float(x) for x in pmi["values"]],
                index=pd.to_datetime(pmi["dates"]),
            ).tail(120)
        # v18.118/119 issue 3 補救：HTML 來源或舊 tail(24) 限制導致 series 缺失或過短
        # → 補抓 FRED ISPMANPMI 144 期當 series（即使源 value 已過時，歷史結構對
        #   Phase 4 lag-correlation / Phase 3-B 燈號回測仍可用 — 都看相對變化）
        # v18.119: 條件放寬「s is None or len(s) < 60」— 上游 fetch_ism_pmi 雖已改 tail(120)
        # 但 MacroMicro / ISM World 等 HTML 源仍可能回 0 期，雙保險。
        if (s is None or len(s) < 60) and fred_api_key:
            try:
                df_hist = _fred("ISPMANPMI", fred_api_key, 144)
                if not df_hist.empty:
                    s = df_hist.set_index("date")["value"].tail(120)
                    print(f"[PMI] series 補救：FRED ISPMANPMI 歷史 {len(s)} 期")
            except Exception as _e_pmi_hist:
                print(f"[PMI] series 補救失敗：{_e_pmi_hist}")
        is_proxy = bool(pmi.get("is_proxy"))
        src_label = pmi.get("source", "?")
        if is_proxy and src_label == "OECD-Proxy":
            # OECD BCI 概念替代：100 為長期平均，>100 擴張、<100 收縮
            signal_g = v > 100
            signal_r = v < 99
            score = 1 if signal_g else (-1 if signal_r else 0)
            desc = (f"⚠️ 替代指標：{pmi.get('label', 'OECD-Proxy')} | "
                    "100 為長期平均，>100 擴張 | "
                    f"資料源：{src_label}")
            name = "ISM PMI（替代：OECD US BCI）"
        else:
            # 包括 Phil Fed 已轉換為 PMI 刻度，與真 ISM PMI 同 50 榮枯線
            signal_g = v > 50
            signal_r = v < 45
            score = 2 if v >= 50 else (-2 if v < 45 else -1)
            desc = (f"50 為榮枯線，>50 擴張，<50 收縮 | 最核心領先指標 | "
                    f"資料源：{pmi.get('label', src_label)}")
            name = ("ISM 製造業 PMI（Phil Fed 替代）" if is_proxy
                    else "ISM 製造業 PMI")
        R["PMI"] = dict(
            name=name, value=v, prev=prev, unit="", type="領先",
            date=str(pmi.get("date", ""))[:7],
            desc=desc,
            trend=_trend([float(x) for x in vals_list[-6:]]),
            signal="🟢" if signal_g else ("🔴" if signal_r else "🟡"),
            color="#00c853" if signal_g else ("#f44336" if signal_r else "#ff9800"),
            score=score, weight=2, series=s,
            source=src_label,
            is_proxy=is_proxy,
            label=pmi.get("label", ""),
            proxy_note=pmi.get("proxy_note", ""),
        )

    # ── 殖利率利差 ──────────────────────────────────────────────────
    # n=2600 (≈10y daily) 才能 resample("ME") 後保留 120 月頻 spread → 餵 Phase 4/3-B
    df10 = _fred("DGS10", fred_api_key, 2600)
    df2  = _fred("DGS2",  fred_api_key, 2600)
    # 必須用 DGS3MO（日頻 3M Treasury Constant Maturity）而非 TB3MS（月頻 T-Bill 平均），
    # 否則 spread 被 inner-join 降頻成月頻，daily threshold 會誤判 🔴 過舊。
    df3m = _fred("DGS3MO", fred_api_key, 2600)

    if not df10.empty and not df2.empty:
        sp22 = _spread_series(df10, df2, 120)
        if len(sp22) >= 2:
            v = float(sp22.iloc[-1]); p = float(sp22.iloc[-2])
            R["YIELD_10Y2Y"] = dict(name="殖利率利差 10Y-2Y", value=round(v,3), prev=round(p,3),
                unit="%", type="領先", date=str(sp22.index[-1])[:7],
                desc="倒掛(<0)=衰退 | 由負翻正=MK黃金買點",
                trend=_trend(sp22.tolist()[-6:]),
                signal="🟢" if v>0.5 else ("🔴" if v<0 else "🟡"),
                color="#00c853" if v>0.5 else ("#f44336" if v<0 else "#ff9800"),
                score=2 if v>0.5 else (-2 if v<0 else 0),
                weight=2, series=sp22)

    if not df10.empty and not df3m.empty:
        sp3m = _spread_series(df10, df3m, 120)
        if len(sp3m) >= 2:
            v = float(sp3m.iloc[-1]); p = float(sp3m.iloc[-2])
            R["YIELD_10Y3M"] = dict(name="殖利率利差 10Y-3M", value=round(v,3), prev=round(p,3),
                unit="%", type="領先", date=str(sp3m.index[-1])[:7],
                desc="倒掛解除=降息確認 | 最強衰退預測指標",
                trend=_trend(sp3m.tolist()[-6:]),
                signal="🟢" if v>0.5 else ("🔴" if v<0 else "🟡"),
                color="#00c853" if v>0.5 else ("#f44336" if v<0 else "#ff9800"),
                score=2 if v>0 else -2,
                weight=2, series=sp3m)

    # ── HY 信用利差 ──────────────────────────────────────────────────
    # n=2500 + tail(2500) 確保 Phase 3-B 燈號回測有 ≥60 樣本（10y 日頻）
    df = _fred("BAMLH0A0HYM2", fred_api_key, 2500)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(2500)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["HY_SPREAD"] = dict(
            name="HY 信用利差 (OAS)", value=round(v,2), prev=round(p,2),
            unit="%", type="金融壓力", date=str(df.iloc[-1]["date"])[:7],
            desc="<4%樂觀 | 4~6%中性 | >6%風險 | 擴大=逃離高風險資產",
            trend=_trend(s.tolist()[-6:]),
            signal="🟢" if v<4 else ("🔴" if v>6 else "🟡"),
            color="#00c853" if v<4 else ("#f44336" if v>6 else "#ff9800"),
            score=2 if v<4 else (-2 if v>6 else 0),
            weight=2, series=s)

    # ── M2 ───────────────────────────────────────────────────────────
    df = _fred("M2SL", fred_api_key, 144)
    if len(df) >= 13:
        s = df.set_index("date")["value"]
        yoy = (s / s.shift(12) - 1) * 100
        s24 = yoy.dropna().tail(120)
        v = float(s24.iloc[-1]); p = float(s24.iloc[-2]) if len(s24)>=2 else v
        R["M2"] = dict(
            name="M2 貨幣供給 (YoY)", value=round(v,2), prev=round(p,2),
            unit="%", type="流動性", date=str(df.iloc[-1]["date"])[:7],
            desc=">5%流動性寬鬆→利多 | <0%緊縮→壓力",
            trend=_trend(s24.tolist()[-6:]),
            signal="🟢" if v>5 else ("🔴" if v<0 else "🟡"),
            color="#00c853" if v>5 else ("#f44336" if v<0 else "#ff9800"),
            score=1 if v>5 else (-1 if v<0 else 0),
            weight=1, series=s24)

    # ── 市場廣度 RSP/SPY ─────────────────────────────────────────────
    try:
        s_spy = _yf_s("SPY","5y"); s_rsp = _yf_s("RSP","5y")
        if len(s_spy)>=22 and len(s_rsp)>=22:
            ratio = (s_rsp / s_spy).dropna()
            ratio = ratio.reindex(s_spy.index, method="ffill").dropna()
            v = round(float(ratio.iloc[-1]),4); m1 = round(float(ratio.iloc[-22]),4)
            chg = round((v-m1)/m1*100,2)
            s_w = ratio.resample("W").last().tail(260)
            R["ADL"] = dict(
                name="市場廣度 RSP/SPY", value=round(v,4), prev=round(chg,2),
                unit="", type="市場廣度",
                date=ratio.index[-1].strftime("%Y-%m-%d"),
                desc=f"等/市值比率月變{chg:+.2f}% | 上升=多頭健康 | 下降=僅七巨頭撐盤",
                trend="up" if chg>0.5 else ("down" if chg<-0.5 else "flat"),
                signal="🟢" if chg>0.5 else ("🔴" if chg<-1 else "🟡"),
                color="#00c853" if chg>0.5 else ("#f44336" if chg<-1 else "#ff9800"),
                score=1 if chg>0.5 else (-1 if chg<-1 else 0),
                weight=1, series=s_w)
    except Exception as e:
        print(f"[ADL] {e}")

    # ── DXY ──────────────────────────────────────────────────────────
    s_dxy = _yf_s("DX-Y.NYB", "5y")
    if len(s_dxy) >= 22:
        v = round(float(s_dxy.iloc[-1]),2); m1 = round(float(s_dxy.iloc[-22]),2)
        chg_m = round((v-m1)/m1*100, 2)
        s_w = s_dxy.resample("W").last().tail(260)
        R["DXY"] = dict(
            name="美元指數 DXY", value=v, prev=round(chg_m,2),
            unit="", type="資金流向",
            date=s_dxy.index[-1].strftime("%Y-%m-%d"),
            desc=f"月漲跌 {chg_m:+.2f}% | 弱美元→新興市場利多 | 強美元→壓縮",
            trend="up" if chg_m>1 else ("down" if chg_m<-1 else "flat"),
            signal="🟡" if abs(chg_m)<1 else ("🟢" if chg_m<-1 else "🔴"),
            color="#ff9800" if abs(chg_m)<1 else ("#00c853" if chg_m<-1 else "#f44336"),
            score=1 if chg_m<-1 else (-1 if chg_m>2 else 0),
            weight=1, series=s_w)

    # ── v18.107 跨幣別 cross-rate（歐元 / 日圓 / 離岸人民幣）─────────
    # 用 yfinance forex pair（已經接 NAS proxy 中繼，不直連）
    _CROSS_RATES = [
        # (yf_ticker, snapshot_key, name, desc_low, desc_high, low_thr, high_thr)
        ("EURUSD=X", "EURUSD", "歐元/美元 EUR/USD",
         "歐元走弱→歐洲資產壓力", "歐元走強→歐美息差縮",   1.05, 1.15),
        ("JPY=X",    "USDJPY", "美元/日圓 USD/JPY",
         "日圓走強→避險升溫", "日圓貶值→carry trade", 140.0, 155.0),
        ("CNH=X",    "USDCNH", "美元/離岸人民幣 USD/CNH",
         "人民幣走強→新興市場利多", "人民幣貶值→中國壓力", 7.0, 7.3),
    ]
    for _tk, _key, _nm, _d_lo, _d_hi, _lo, _hi in _CROSS_RATES:
        try:
            s_fx = _yf_s(_tk, "5y")
            if len(s_fx) >= 22:
                v = round(float(s_fx.iloc[-1]), 4)
                m1 = float(s_fx.iloc[-22])
                chg_m = round((v - m1) / m1 * 100, 2) if m1 else 0.0
                s_w = s_fx.resample("W").last().tail(260)
                # 強弱判斷：USDxxx pair 高=USD 強 / EURUSD 高=EUR 強
                if _key == "EURUSD":
                    sig = "🟢" if v > _hi else ("🔴" if v < _lo else "🟡")
                    score = 1 if v > _hi else (-1 if v < _lo else 0)
                else:
                    # USDJPY / USDCNH：偏高代表 USD 太強（對新興市場壓力）
                    sig = "🔴" if v > _hi else ("🟢" if v < _lo else "🟡")
                    score = -1 if v > _hi else (1 if v < _lo else 0)
                color = ("#00c853" if sig == "🟢"
                         else ("#f44336" if sig == "🔴" else "#ff9800"))
                R[_key] = dict(
                    name=_nm, value=v, prev=round(chg_m, 2),
                    unit="", type="跨幣別",
                    date=s_fx.index[-1].strftime("%Y-%m-%d"),
                    desc=f"月漲跌 {chg_m:+.2f}% | {_d_lo} | {_d_hi}",
                    trend="up" if chg_m > 0.5 else ("down" if chg_m < -0.5 else "flat"),
                    signal=sig, color=color, score=score,
                    weight=1, series=s_w,
                )
        except Exception as _e:
            print(f"[{_key}] {_e}")

    # ── Fed 資產負債表 ────────────────────────────────────────────────
    # n=312 (6y weekly) + tail(260) = Phase 3-B 燈號回測需 ≥60 樣本
    df = _fred("WALCL", fred_api_key, 312)
    if len(df) >= 13:
        s = df.set_index("date")["value"]
        yoy = (s / s.shift(52) - 1) * 100
        s24 = yoy.dropna().tail(260)
        v = float(s24.iloc[-1]); p = float(s24.iloc[-2]) if len(s24)>=2 else v
        R["FED_BS"] = dict(
            name="Fed 資產負債表 (YoY)", value=round(v,2), prev=round(p,2),
            unit="%", type="流動性", date=str(df.iloc[-1]["date"])[:7],
            desc="擴表=注入流動性→利多 | 縮表=抽走流動性→壓力",
            trend=_trend(s24.tolist()[-6:]),
            signal="🟢" if v>5 else ("🔴" if v<-5 else "🟡"),
            color="#00c853" if v>5 else ("#f44336" if v<-5 else "#ff9800"),
            score=1 if v>5 else (-1 if v<-5 else 0),
            weight=1, series=s24)

    # ── VIX ──────────────────────────────────────────────────────────
    # period=5y + tail(260) 確保 Phase 4 lag-corr 與 Phase 3-B 燈號回測樣本足
    s_vix = _yf_s("^VIX","5y")
    if len(s_vix) >= 6:
        v = round(float(s_vix.iloc[-1]),2); p = round(float(s_vix.iloc[-6]),2)
        s_m = s_vix.resample("W").last().tail(260)
        R["VIX"] = dict(name="VIX 恐慌指數", value=v, prev=p, unit="", type="同時",
            date=s_vix.index[-1].strftime("%Y-%m-%d"),
            desc="<18平靜 | >30恐慌=逢低加碼時機",
            signal="🟢" if v<18 else ("🔴" if v>30 else "🟡"),
            color="#00c853" if v<18 else ("#f44336" if v>30 else "#ff9800"),
            score=1 if v<18 else (-1 if v>30 else 0),
            weight=1, series=s_m)

    # ── CPI ──────────────────────────────────────────────────────────
    df = _fred("CPIAUCSL", fred_api_key, 144)
    if len(df) >= 14:
        s = df.set_index("date")["value"]
        yoy = (s / s.shift(12) - 1) * 100
        s24 = yoy.dropna().tail(120)
        v = float(s24.iloc[-1]); p = float(s24.iloc[-2])
        t = _trend(s24.tolist()[-6:])
        R["CPI"] = dict(name="CPI 通膨率 (YoY)", value=round(v,2), prev=round(p,2),
            unit="%", type="落後", date=str(df.iloc[-1]["date"])[:7],
            desc="目標2% | 高位回落=利多拐點", trend=t,
            signal="🟢" if 1<v<2.5 else ("🔴" if v>4 else "🟡"),
            color="#00c853" if 1<v<2.5 else ("#f44336" if v>4 else "#ff9800"),
            score=1 if 1<v<2.5 else (-1 if v>4 else 0),
            weight=0.5, series=s24)

    # ── Fed Rate ──────────────────────────────────────────────────────
    df = _fred("FEDFUNDS", fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["FED_RATE"] = dict(name="聯準會利率", value=v, prev=p, unit="%", type="落後",
            date=str(df.iloc[-1]["date"])[:7], desc="降息=利多 | 升息=緊縮",
            trend=_trend(df["value"].tolist()[-8:]),
            signal="🟢" if v<p else ("🔴" if v>5 else "🟡"),
            color="#00c853" if v<p else ("#f44336" if v>5 else "#ff9800"),
            score=1 if v<p else (-1 if v>5 else 0),
            weight=0.5, series=s)

    # ── 失業率 ───────────────────────────────────────────────────────
    df = _fred("UNRATE", fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["UNEMPLOYMENT"] = dict(name="失業率", value=v, prev=p, unit="%", type="落後",
            date=str(df.iloc[-1]["date"])[:7], desc="<4.5%健康 | 上升=景氣轉差",
            trend=_trend(df["value"].tolist()[-6:]),
            signal="🟢" if v<4.5 else ("🔴" if v>6 else "🟡"),
            color="#00c853" if v<4.5 else ("#f44336" if v>6 else "#ff9800"),
            score=1 if v<4.5 else (-2 if v>6 else 0),
            weight=0.5, series=s)

    # ── PPI ──────────────────────────────────────────────────────────
    df = _fred("PPIACO", fred_api_key, 144)
    if len(df) >= 13:
        s = df.set_index("date")["value"]
        yoy = (s / s.shift(12) - 1) * 100
        s24 = yoy.dropna().tail(120)
        v = float(s24.iloc[-1]) if len(s24) >= 1 else 0
        p = float(s24.iloc[-2]) if len(s24) >= 2 else None
        R["PPI"] = dict(name="PPI 生產者物價 (YoY)", value=round(v,2),
            prev=round(p,2) if p else None,
            unit="%", type="領先", date=str(df.iloc[-1]["date"])[:7],
            desc="領先CPI，0~3%溫和，>5%過熱",
            trend=_trend(s24.tolist()[-6:]),
            signal="🟢" if 0<v<3 else ("🔴" if v>5 or v<-1 else "🟡"),
            color="#00c853" if 0<v<3 else ("#f44336" if v>5 or v<-1 else "#ff9800"),
            score=0.5 if 0<v<3 else (-0.5 if v>5 else 0),
            weight=0.5, series=s24)

    # ── 銅博士 ────────────────────────────────────────────────────────
    s_cu = _yf_s("HG=F","5y")
    if len(s_cu) >= 22:
        now = float(s_cu.iloc[-1]); prev = float(s_cu.iloc[-22])
        chg = round((now-prev)/prev*100, 2) if prev else 0
        monthly = s_cu.resample("ME").last().pct_change()*100
        R["COPPER"] = dict(name="銅博士（月漲跌）", value=chg, prev=None,
            unit="% MoM", type="領先",
            date=s_cu.index[-1].strftime("%Y-%m-%d"),
            desc=f"現價 {now:.3f} USD/lb | 漲=工業需求增",
            signal="🟢" if chg>2 else ("🔴" if chg<-5 else "🟡"),
            color="#00c853" if chg>2 else ("#f44336" if chg<-5 else "#ff9800"),
            score=0.5 if chg>2 else (-0.5 if chg<-5 else 0),
            weight=0.5, series=monthly.dropna().tail(60))

    # ── 消費者信心 ────────────────────────────────────────────────────
    df = _fred("UMCSENT", fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["CONSUMER_CONF"] = dict(name="消費者信心 (Michigan)", value=v, prev=p,
            unit="", type="領先", date=str(df.iloc[-1]["date"])[:7],
            desc="上升=消費回升，>85樂觀，<60悲觀",
            trend=_trend(df["value"].tolist()[-6:]),
            signal="🟢" if v>80 else ("🔴" if v<60 else "🟡"),
            color="#00c853" if v>80 else ("#f44336" if v<60 else "#ff9800"),
            score=0.5 if v>80 else (-0.5 if v<60 else 0),
            weight=0.5, series=s)

    # ── 初領失業金 ────────────────────────────────────────────────────
    # n=312 (6y weekly) + tail(260) = Phase 3-B 燈號回測 ≥60 樣本
    df = _fred("ICSA", fred_api_key, 312)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(260)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        # value/prev 統一以「萬人」為單位（與 series 一致），避免 Z-Score 與 AI Prompt 單位錯位
        R["JOBLESS"] = dict(name="初領失業金 (週)", value=round(v/10000, 1), prev=round(p/10000, 1),
            unit="萬人", type="領先", date=str(df.iloc[-1]["date"])[:10],
            desc="下降=就業好轉，<23萬健康，>30萬警戒",
            trend=_trend(df["value"].tolist()[-8:]),
            signal="🟢" if v<230000 else ("🔴" if v>300000 else "🟡"),
            color="#00c853" if v<230000 else ("#f44336" if v>300000 else "#ff9800"),
            score=0.5 if v<230000 else (-0.5 if v>300000 else 0),
            weight=0.5, series=s/10000)

    # ── 新屋銷售 ──────────────────────────────────────────────────────
    df = _fred("HSN1F", fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["NEW_HOME"] = dict(name="新屋銷售", value=v, prev=p, unit="千戶", type="領先",
            date=str(df.iloc[-1]["date"])[:7], desc=f"月增{v-p:+.0f}k | 增加=房市回升",
            trend=_trend(df["value"].tolist()[-6:]),
            signal="🟢" if v>p else "🔴", color="#00c853" if v>p else "#f44336",
            score=0.5 if v>p else -0.5,
            weight=0.5, series=s)

    # ── 薩姆規則（Sahm Rule Recession Indicator）──────────────────────
    df = _fred("SAHMREALTIME", fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["SAHM"] = dict(name="薩姆規則", value=v, prev=p, unit="pp", type="領先",
            date=str(df.iloc[-1]["date"])[:7],
            desc="≥0.5 觸發衰退警報 | <0.3 安全 | 3月失業率均值-12月最低",
            trend=_trend(df["value"].tolist()[-6:]),
            signal="🔴" if v >= 0.5 else ("🟡" if v >= 0.3 else "🟢"),
            color="#f44336" if v >= 0.5 else ("#ff9800" if v >= 0.3 else "#00c853"),
            score=-2 if v >= 0.5 else (-0.5 if v >= 0.3 else 1),
            weight=1.5, series=s)

    # ── SLOOS 銀行放貸標準（Senior Loan Officer Survey）──────────────
    # 季頻 (quarterly)：n=80 (20y)、tail(60) (15y) → Phase 3-B ≥60 樣本
    df = _fred("DRTSCILM", fred_api_key, 80)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(60)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        # 正值=銀行收緊放貸(壞)，負值=放寬(好)
        R["SLOOS"] = dict(name="SLOOS 放貸標準", value=v, prev=p, unit="%", type="領先",
            date=str(df.iloc[-1]["date"])[:7],
            desc=">20% 銀行大幅緊縮信貸（衰退前兆）| <0% 信貸寬鬆",
            trend=_trend(df["value"].tolist()[-4:]),
            signal="🔴" if v > 20 else ("🟡" if v > 0 else "🟢"),
            color="#f44336" if v > 20 else ("#ff9800" if v > 0 else "#00c853"),
            score=-2 if v > 30 else (-1 if v > 20 else (0.5 if v < 0 else -0.5)),
            weight=1.5, series=s)

    # ════════════════════════════════════════════════════════════════
    # v16.1 高頻替代資料源（A+B 路線：補位月度資料延遲）
    # 設計：以下指標是「主源延遲時的高頻補位」，皆與既有指標平行存在
    # ════════════════════════════════════════════════════════════════

    # ── LEI 領先指標（CFNAI 芝加哥聯儲全國活動指數）────────────────
    # ⚠️ USSLIND（Philadelphia Fed Leading Index）已於 2020 COVID 期間因方法論
    #    失效永久停更（最後資料 2020-02），改用 CFNAI 作為等價替代：
    #    CFNAI 月頻活躍發布，匯總 85 個月度經濟指標，z-score 標準化後
    #    平均值=0，標準差=1。三月均值 < -0.7 強烈衰退訊號。
    # 注意：CFNAI 數值意涵與 USSLIND 不同，閾值與描述已對應調整。
    df = _fred("CFNAI", fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        # CFNAI 三月均值（CFNAI-MA3，更可靠的衰退訊號）
        ma3 = s.rolling(3).mean()
        v_ma3 = float(ma3.iloc[-1]) if len(ma3.dropna()) >= 1 else v
        R["LEI"] = dict(name="CFNAI 領先指標", value=round(v,2), prev=round(p,2),
            unit="", type="領先", date=str(df.iloc[-1]["date"])[:7],
            desc=f"芝加哥聯儲全國活動指數（85 指標 z-score）| 3M均值={v_ma3:+.2f} "
                 f"| > +0.7 強勁擴張 | < -0.7 衰退預警 | PMI 替代源",
            trend=_trend(df["value"].tolist()[-6:]),
            signal="🟢" if v > 0.0 else ("🔴" if v < -0.7 else "🟡"),
            color="#00c853" if v > 0.0 else ("#f44336" if v < -0.7 else "#ff9800"),
            score=1 if v > 0.0 else (-2 if v_ma3 < -0.7 else (-1 if v < 0 else 0)),
            weight=1, series=s)

    # ── CONT_CLAIMS 持續失業金（CCSA，週頻）──────────────────────
    # UNEMPLOYMENT 月度延遲時的高頻替代；與 ICSA(初領)互補：CCSA=尚未找到工作的人數
    df = _fred("CCSA", fred_api_key, 312)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(260)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["CONT_CLAIMS"] = dict(name="持續失業金 (週)", value=int(v), prev=int(p),
            unit="萬人", type="領先", date=str(df.iloc[-1]["date"])[:10],
            desc="尚在領失業金人數 | <170 萬健康 | >190 萬警戒 | 失業率月延遲時看這顆",
            trend=_trend(df["value"].tolist()[-8:]),
            signal="🟢" if v < 1700000 else ("🔴" if v > 1900000 else "🟡"),
            color="#00c853" if v < 1700000 else ("#f44336" if v > 1900000 else "#ff9800"),
            score=0.5 if v < 1700000 else (-0.5 if v > 1900000 else 0),
            weight=0.5, series=s/10000)

    # ── M2_WEEKLY 週頻 M2（WM2NS）─────────────────────────────────
    # M2 月度延遲時的補位；YoY 計算用 52 週前的數據對比
    df = _fred("WM2NS", fred_api_key, 520)
    if len(df) >= 53:
        s_full = df.set_index("date")["value"]
        yoy = (s_full / s_full.shift(52) - 1) * 100
        s24 = yoy.dropna().tail(260)
        if len(s24) >= 2:
            v = float(s24.iloc[-1]); p = float(s24.iloc[-2])
            R["M2_WEEKLY"] = dict(name="M2 週頻 (YoY)", value=round(v,2), prev=round(p,2),
                unit="%", type="流動性", date=str(df.iloc[-1]["date"])[:10],
                desc="WM2NS 週頻 | M2 月版延遲時的最即時替代 | 同樣 >5%寬鬆 / <0%緊縮",
                trend=_trend(s24.tolist()[-6:]),
                signal="🟢" if v > 5 else ("🔴" if v < 0 else "🟡"),
                color="#00c853" if v > 5 else ("#f44336" if v < 0 else "#ff9800"),
                score=1 if v > 5 else (-1 if v < 0 else 0),
                weight=1, series=s24)

    # ── INFL_EXP_5Y 5Y 通膨預期（T5YIE，日頻）─────────────────────
    # CPI 月度延遲時的高頻補位；債市每日交易計算的 5 年期 breakeven
    df = _fred("T5YIE", fred_api_key, 2500)
    if len(df) >= 22:
        s = df.set_index("date")["value"].tail(2500)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-22]["value"])
        R["INFL_EXP_5Y"] = dict(name="5Y 通膨預期 (日)", value=round(v,2), prev=round(p,2),
            unit="%", type="領先", date=str(df.iloc[-1]["date"])[:10],
            desc="債市每日交易計算 | Fed 目標 2-2.5% | >3% 通膨失控擔憂 | CPI 月延遲時看這顆",
            trend=_trend(df["value"].tolist()[-22:][::4]),
            signal="🟢" if 1.5 < v < 2.8 else ("🔴" if v > 3.5 else "🟡"),
            color="#00c853" if 1.5 < v < 2.8 else ("#f44336" if v > 3.5 else "#ff9800"),
            score=1 if 1.5 < v < 2.8 else (-1 if v > 3.5 else 0),
            weight=1, series=s)

    # ── PERMIT_HOUSING 建照核發（PERMIT）──────────────────────────
    # NEW_HOME（新屋銷售）的領先指標：建商先拿建照才開工再銷售，PERMIT 早 1-2 個月反映
    df = _fred("PERMIT", fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["PERMIT_HOUSING"] = dict(name="建照核發", value=v, prev=p, unit="千戶",
            type="領先", date=str(df.iloc[-1]["date"])[:7],
            desc=f"月增{v-p:+.0f}k | 領先新屋銷售 1-2 個月 | >150 萬健康 | <120 萬房市疲弱",
            trend=_trend(df["value"].tolist()[-6:]),
            signal="🟢" if v > 1500 else ("🔴" if v < 1200 else "🟡"),
            color="#00c853" if v > 1500 else ("#f44336" if v < 1200 else "#ff9800"),
            score=0.5 if v > 1500 else (-0.5 if v < 1200 else 0),
            weight=0.5, series=s)

    return R
def get_market_phase(indicators: dict) -> dict:
    """
    二維景氣位階判定（說明書 §3）：Z-Score 位階 × 線性斜率方向
    ─────────────────────────────────────────────────────────────
    以 PMI 為主要代表指標（最高權重領先指標），結合 Z-Score 與 trend_slope：

      復甦 (Recovery) : Z 低位(< -0.5) + Slope 轉正(> +0.05)
      擴張 (Expansion): Z 中位         + Slope 為正(> 0)
      減速 (Slowdown) : Z 高位(> +0.5) + Slope 轉負(< -0.05) ← 關鍵拐點
      衰退 (Recession): Z 低位         + Slope 為負(< 0)

    回傳字典可直接補充至 calc_macro_phase() 輸出，作為第二層確認。
    """
    def _get(key, attr): return (indicators.get(key) or {}).get(attr)

    # ── 以 PMI + YIELD_10Y2Y + HY_SPREAD 三個領先指標投票
    _phases = []
    for _key in ("PMI", "YIELD_10Y2Y", "HY_SPREAD"):
        _z  = _get(_key, "z_score")
        _sl = _get(_key, "trend_slope")
        if _z is None or _sl is None:
            continue
        # 反向指標（HY 利差越大越壞）
        _inv = -1 if _key == "HY_SPREAD" else 1
        _z_adj  = _z  * _inv
        _sl_adj = _sl * _inv

        if _z_adj < -0.5 and _sl_adj > 0.05:
            _phases.append("復甦")
        elif _z_adj > 0.5 and _sl_adj < -0.05:
            _phases.append("減速")   # 最重要的高位轉負訊號
        elif _sl_adj > 0:
            _phases.append("擴張")
        else:
            _phases.append("衰退")

    if not _phases:
        return {"phase2d": "未知", "phase2d_color": "#888", "phase2d_desc": "資料不足"}

    # 多數決
    from collections import Counter
    _winner = Counter(_phases).most_common(1)[0][0]
    _vote_ratio = Counter(_phases).most_common(1)[0][1] / len(_phases)

    _map = {
        "復甦": ("#64b5f6", "Z 低位 + 斜率翻正，景氣底部確認，逢低布局機會"),
        "擴張": ("#00c853", "Z 中位 + 斜率向上，成長動能充足，持有風險資產"),
        "減速": ("#ff9800", "Z 高位 + 斜率轉負，擴張減速拐點！考慮調降衛星比重"),
        "衰退": ("#f44336", "Z 低位 + 斜率向下，景氣收縮，轉向防禦配置"),
    }
    _color, _desc = _map.get(_winner, ("#888", ""))
    return {
        "phase2d":        _winner,
        "phase2d_color":  _color,
        "phase2d_desc":   _desc,
        "phase2d_votes":  dict(Counter(_phases)),
        "phase2d_conf":   round(_vote_ratio * 100),
    }


def get_synced_dashboard_data(raw_data_dict: dict, lookback_days: int = 30) -> pd.DataFrame:
    """
    數據對齊補丁 v1：統一時間軸 + 假日前向填充（文件建議 §2）
    1. 建立完整日曆時間索引
    2. 自動填充假日空值（前向填充，上限 5 天）
    3. 若仍有空值 → 資料嚴重斷連，透過 Streamlit 警告
    """
    full_idx = pd.date_range(
        end=pd.Timestamp.now().normalize(), periods=lookback_days, freq='D'
    )
    main_df = pd.DataFrame(index=full_idx)

    for name, data in raw_data_dict.items():
        if isinstance(data, pd.Series):
            s = data.copy()
        elif isinstance(data, (list,)):
            s = pd.Series(data)
        else:
            continue
        s.index = pd.to_datetime(s.index).normalize()
        main_df[name] = s

    # 核心修正：前向填充假日數據，限制回溯 5 天
    main_df = main_df.ffill(limit=5)

    # 若仍有空值，代表數據嚴重斷連
    if main_df.iloc[-1].isnull().any():
        missing = main_df.columns[main_df.iloc[-1].isnull()].tolist()
        st.warning(f"⚠️ 部分數據源連線不穩：{', '.join(missing)}，請檢查網路或 API 配額")

    return main_df


def calc_growth_inflation_axis(indicators: dict) -> dict:
    """
    成長/通膨雙軸分析（文件建議 §1：二象限循環判定）
    ─────────────────────────────────────────────────
    Growth Axis  : PMI, 殖利率曲線, M2, 市場廣度, 消費者信心, 初領失業金, 銅博士
    Inflation Axis: CPI, PPI, Fed Rate
    ─────────────────────────────────────────────────
    四象限:
      復甦/擴張 (Goldilocks): 成長↑ 通膨↓
      過熱 (Overheat)       : 成長↑ 通膨↑
      滯脹 (Stagflation)    : 成長↓ 通膨↑
      衰退 (Recession)      : 成長↓ 通膨↓
    """
    def _get(key, attr="value"):
        return (indicators.get(key) or {}).get(attr)

    # ── Growth signals（正=成長向上，負=成長向下）
    growth_signals = []
    pmi_v = _get("PMI")
    if pmi_v is not None:
        growth_signals.append(1 if pmi_v >= 50 else -1)

    y22 = _get("YIELD_10Y2Y")
    if y22 is not None:
        growth_signals.append(1 if y22 >= 0 else -1)

    m2_v = _get("M2")
    if m2_v is not None:
        growth_signals.append(1 if m2_v >= 3 else -1)

    adl_chg = _get("ADL", "prev")  # prev = monthly change %
    if adl_chg is not None:
        growth_signals.append(1 if adl_chg >= 0 else -1)

    conf_v = _get("CONSUMER_CONF")
    if conf_v is not None:
        growth_signals.append(1 if conf_v >= 70 else -1)

    jobless_v = _get("JOBLESS")
    if jobless_v is not None:
        # JOBLESS 已統一單位為「萬人」（28 萬 = 過去的 280000）
        growth_signals.append(1 if jobless_v < 28 else -1)

    copper_v = _get("COPPER")  # monthly change %
    if copper_v is not None:
        growth_signals.append(1 if copper_v >= 0 else -1)

    # ── Inflation signals（正=通膨偏高，負=通膨受控）
    inflation_signals = []
    cpi_v = _get("CPI")
    if cpi_v is not None:
        inflation_signals.append(1 if cpi_v >= 3.0 else -1)

    ppi_v = _get("PPI")
    if ppi_v is not None:
        inflation_signals.append(1 if ppi_v >= 3.0 else -1)

    fed_v = _get("FED_RATE")
    if fed_v is not None:
        inflation_signals.append(1 if fed_v >= 4.0 else -1)

    # ── 計算平均訊號分數（-1 ~ +1）
    growth_score    = sum(growth_signals)    / max(len(growth_signals), 1)
    inflation_score = sum(inflation_signals) / max(len(inflation_signals), 1)
    growth_up    = growth_score > 0
    inflation_up = inflation_score > 0

    # ── 四象限映射
    if growth_up and not inflation_up:
        quadrant    = "復甦/擴張"; quadrant_en = "Goldilocks"
        quad_color  = "#00c853";   quad_icon   = "🌱"
        quad_desc   = "成長↑ 通膨↓ — 黃金期，積極持有風險資產"
        quad_alloc  = "衛星成長型↑  核心配息↑  現金↓"
    elif growth_up and inflation_up:
        quadrant    = "過熱";      quadrant_en = "Overheat"
        quad_color  = "#ff9800";   quad_icon   = "🔥"
        quad_desc   = "成長↑ 通膨↑ — 景氣高峰，注意泡沫與緊縮風險"
        quad_alloc  = "實物資產↑  高息防禦↑  成長型↓"
    elif not growth_up and inflation_up:
        quadrant    = "滯脹";      quadrant_en = "Stagflation"
        quad_color  = "#f44336";   quad_icon   = "⚠️"
        quad_desc   = "成長↓ 通膨↑ — 最惡劣環境，降低股票，持有商品與短債"
        quad_alloc  = "商品/黃金↑  短天期債↑  成長股↓↓"
    else:
        quadrant    = "衰退";      quadrant_en = "Recession"
        quad_color  = "#ff9800";   quad_icon   = "🌧️"
        quad_desc   = "成長↓ 通膨↓ — 景氣收縮，轉向長債與防禦型配置"
        quad_alloc  = "長天期債↑↑  防禦股息↑  現金↑  成長股↓"

    return {
        "growth_score":     round(growth_score, 2),
        "inflation_score":  round(inflation_score, 2),
        "growth_up":        growth_up,
        "inflation_up":     inflation_up,
        "quadrant":         quadrant,
        "quadrant_en":      quadrant_en,
        "quad_color":       quad_color,
        "quad_icon":        quad_icon,
        "quad_desc":        quad_desc,
        "quad_alloc":       quad_alloc,
        "n_growth":         len(growth_signals),
        "n_inflation":      len(inflation_signals),
    }


def calc_macro_phase(indicators: dict) -> dict:
    """
    AI Macro Score 加權評分（機構級 v7）
    ─────────────────────────────────────────────────
    指標                    weight    分值
    殖利率曲線 10Y-2Y          2      ±2
    殖利率曲線 10Y-3M          2      ±2
    PMI                       2      ±2
    HY 信用利差                2      ±2
    M2 流動性                  1      ±1
    市場廣度 RSP/SPY           1      ±1
    Fed 資產負債表             1      ±1
    DXY 美元指數               1      ±1
    VIX 恐慌指數               1      ±1
    CPI 通膨                  0.5     ±0.5
    Fed Rate                 0.5     ±0.5
    失業率                    0.5     ±0.5
    ─────────────────────────────────────────────────
    最大可能 ≈ 14 → 正規化到 0~10
    景氣判斷：0~2衰退 | 3~4復甦 | 5~7擴張 | 8~10高峰
    """
    # 加權加總
    total_w = 0; earned_w = 0
    for key, ind in indicators.items():
        w = ind.get("weight", 1)
        s = ind.get("score", 0)
        # 確保 score 不超過 weight
        s = max(-w, min(w, s))
        total_w += w
        earned_w += s

    # 正規化：把 [-total_w, +total_w] 映射到 [0, 10]
    if total_w > 0:
        norm = (earned_w + total_w) / (2 * total_w) * 10
    else:
        norm = 5
    score = round(max(0, min(10, norm)), 1)

    # ─── 修正後的景氣門檻 ───
    if score >= 8:
        phase = "高峰"; phase_en = "Peak"; phase_color = "#f44336"
        alloc = dict(股票=35, 債券=45, 現金=20)
        advice = "高峰期：適度獲利了結，轉向防禦型資產"
        strategy = "逐步減碼高估值成長股，增加投資等級債與黃金"
    elif score >= 5:
        phase = "擴張"; phase_en = "Expansion"; phase_color = "#00c853"
        alloc = dict(股票=60, 債券=30, 現金=10)
        advice = "股優於債：核心高股息ETF + 衛星AI/半導體，設嚴格停利點"
        strategy = "持有核心配息資產，衛星資產設15%停利出場"
    elif score >= 3:
        phase = "復甦"; phase_en = "Recovery"; phase_color = "#64b5f6"
        alloc = dict(股票=40, 債券=40, 現金=20)
        advice = "復甦期：最高勝率買點！逐步加碼，優先佈局高股息與平衡型"
        strategy = "積極佈局中小型成長股、非必需消費、金融股底部"
    else:
        phase = "衰退"; phase_en = "Recession"; phase_color = "#ff9800"
        alloc = dict(股票=20, 債券=50, 現金=30)
        advice = "衰退期：保守為主，等待落後指標見頂為進場訊號"
        strategy = "保留現金，等待PMI落底與殖利率曲線翻正"

    # 衰退機率
    sp3m = indicators.get("YIELD_10Y3M", {}).get("value")
    rec_prob = None
    if sp3m is not None:
        import math
        logit = -1.5 * sp3m - 0.8
        rec_prob = round(1 / (1 + math.exp(-logit)) * 100, 1)

    # 風險警報
    alerts = []
    if indicators.get("YIELD_10Y2Y",{}).get("value", 1) < 0:
        alerts.append("⚠️ 殖利率曲線倒掛（衰退前兆）")
    if indicators.get("HY_SPREAD",{}).get("value", 4) > 6:
        alerts.append("⚠️ 信用利差>6% — 市場恐慌升溫")
    if indicators.get("PMI",{}).get("value", 50) < 50:
        alerts.append("⚠️ PMI 跌破 50 — 製造業收縮")
    if indicators.get("VIX",{}).get("value", 18) > 25:
        alerts.append("⚠️ VIX>25 — 市場恐慌，注意波動")
    if indicators.get("CPI",{}).get("value", 2) > 4:
        alerts.append("⚠️ 通膨偏高 — Fed 緊縮壓力")
    if indicators.get("M2",{}).get("value", 3) < 0:
        alerts.append("⚠️ M2 負成長 — 流動性緊縮")
    if indicators.get("ADL",{}).get("prev", 0) < -1:
        alerts.append("⚠️ 市場廣度惡化 — 僅少數股支撐指數")
    if rec_prob and rec_prob > 60:
        alerts.append(f"🔴 衰退機率 {rec_prob:.0f}% — 高度警戒")

    # MK 拐點偵測
    mk_signals = _detect_inflection(indicators)

    # ── 拐點轉向判斷 ─────────────────────────────────────
    PHASE_ORDER = ["衰退", "復甦", "擴張", "高峰"]
    infl_score = mk_signals.get("infl_score", 0)
    ph_idx = PHASE_ORDER.index(phase)

    if infl_score >= 5:         # 多項買進訊號齊發 → 向上轉
        next_phase = PHASE_ORDER[(ph_idx + 1) % 4]
        trend_arrow = "↗"
        trend_label = "向上轉折（加速）"
        trend_color = "#00c853"
    elif infl_score >= 2:       # 偏多觀察 → 偏向上
        next_phase = PHASE_ORDER[(ph_idx + 1) % 4]
        trend_arrow = "→↗"
        trend_label = "偏向上（觀察中）"
        trend_color = "#69f0ae"
    elif infl_score <= -5:      # 多項空頭訊號 → 向下轉
        next_phase = PHASE_ORDER[(ph_idx - 1) % 4]
        trend_arrow = "↘"
        trend_label = "向下轉折（警示）"
        trend_color = "#f44336"
    elif infl_score <= -2:      # 偏空謹慎 → 偏向下
        next_phase = PHASE_ORDER[(ph_idx - 1) % 4]
        trend_arrow = "→↘"
        trend_label = "偏向下（謹慎）"
        trend_color = "#ff7043"
    else:                       # 中性整理
        next_phase = phase
        trend_arrow = "→"
        trend_label = "持穩整理"
        trend_color = "#888888"

    # ── 各景氣位階配置 Map（供拐點轉換顯示）────────────────
    ALLOC_MAP = {
        "復甦": dict(股票=40, 債券=40, 現金=20),
        "擴張": dict(股票=60, 債券=30, 現金=10),
        "高峰": dict(股票=35, 債券=45, 現金=20),
        "衰退": dict(股票=20, 債券=50, 現金=30),
    }
    cur_idx  = ph_idx  # 複用已計算的 ph_idx，消除重複定義
    next_p   = PHASE_ORDER[(cur_idx + 1) % 4]
    prev_p   = PHASE_ORDER[(cur_idx - 1) % 4]
    next_alloc = ALLOC_MAP[next_p]
    cur_alloc  = ALLOC_MAP[phase] if phase in ALLOC_MAP else alloc

    # 拐點發生時的配置變更說明
    alloc_transition = {
        k: {"from": cur_alloc.get(k,0), "to": next_alloc.get(k,0)}
        for k in ["股票","債券","現金"]
    }

    # v15: Weather metaphor (before return dict)
    _weather_tup = (
        ("☀️", "晴天", "#ffd54f",
         "股 {}% / 債 {}% / 現金 {}%".format(alloc.get("股票",60),alloc.get("債券",30),alloc.get("現金",10)))
        if score >= 7 else
        ("⛅", "多雲", "#90caf9",
         "股 {}% / 債 {}% / 現金 {}%".format(alloc.get("股票",50),alloc.get("債券",40),alloc.get("現金",10)))
        if score >= 4 else
        ("⛈️", "暴雨", "#ef9a9a",
         "股 {}% / 債 {}% / 現金 {}%".format(alloc.get("股票",30),alloc.get("債券",50),alloc.get("現金",20)))
    )
    _w_icon, _w_label, _w_color, _w_alloc_str = _weather_tup

    # 成長/通膨雙軸分析（文件建議 §1 二象限循環判定）
    growth_inflation = calc_growth_inflation_axis(indicators)
    # Z-Score × Slope 二維景氣位階（說明書 §3）
    market_phase_2d  = get_market_phase(indicators)

    return dict(
        score=score, phase=phase, phase_en=phase_en,
        phase_color=phase_color, alloc=alloc,
        weather_icon=_w_icon, weather_label=_w_label,
        weather_color=_w_color, weather_alloc_str=_w_alloc_str,
        advice=advice, strategy=strategy,
        alerts=alerts, mk_signals=mk_signals,
        rec_prob=rec_prob,
        # 拐點轉向
        next_phase=next_phase,
        next_phase_name=next_p,
        trend_arrow=trend_arrow,
        trend_label=trend_label,
        trend_color=trend_color,
        alloc_transition=alloc_transition,
        # 雙軸分析
        growth_inflation=growth_inflation,
        market_phase_2d=market_phase_2d,
        # 保留舊 key 供 AI engine 使用
        inflection=mk_signals.get("inflection",{}),
        signals=mk_signals.get("signals",[]),
        allocation=alloc,
    )


# ══════════════════════════════════════════════════════════════
# v13 新增：Z-Score 工具 & 景氣循環辨識模型（Regime Model）
# ══════════════════════════════════════════════════════════════

def zscore(series: pd.Series) -> pd.Series:
    """標準化 Z-Score，用於指標估值判斷"""
    if series.std() == 0:
        return pd.Series([0.0] * len(series), index=series.index)
    return (series - series.mean()) / series.std()


def identify_regime(indicators: dict) -> dict:
    """
    景氣循環辨識模型（v13）
    依 PMI、CPI、FED_RATE 四象限判斷：
      復甦 / 成長 / 過熱 / 衰退
    額外輸出 Z-Score 估值與配置建議
    """
    pmi_v   = (indicators.get("PMI")      or {}).get("value")
    cpi_v   = (indicators.get("CPI")      or {}).get("value")
    fed_v   = (indicators.get("FED_RATE") or {}).get("value")
    fed_p   = (indicators.get("FED_RATE") or {}).get("prev")
    hy_v    = (indicators.get("HY_SPREAD") or {}).get("value")

    # ── 四象限判斷 ────────────────────────────────────────
    if pmi_v is None:
        regime = "未知"; regime_color = "#888888"
    elif pmi_v >= 52 and (cpi_v or 0) < 3.5:
        regime = "🟢 成長期"; regime_color = "#00c853"
    elif pmi_v >= 52 and (cpi_v or 0) >= 3.5:
        regime = "🟡 過熱期"; regime_color = "#ff9800"
    elif pmi_v < 50 and (fed_v or 5) <= (fed_p or 5):
        regime = "🔵 復甦期"; regime_color = "#2196f3"
    else:
        regime = "🔴 衰退期"; regime_color = "#f44336"

    # ── Z-Score 估值判斷（PMI / HY_SPREAD）──────────────
    pmi_series = (indicators.get("PMI") or {}).get("series")
    zscore_pmi = None
    if pmi_series is not None and len(pmi_series) >= 12:
        z = float(zscore(pmi_series).iloc[-1])
        if z < -1.5:   zscore_pmi = {"label": "PMI 低估（買進訊號）", "z": round(z,2), "signal": "🟢"}
        elif z > 1.5:  zscore_pmi = {"label": "PMI 高估（過熱警告）", "z": round(z,2), "signal": "🔴"}
        else:          zscore_pmi = {"label": "PMI 中性",             "z": round(z,2), "signal": "🟡"}

    # ── 配置建議（依循環調整）────────────────────────────
    alloc_by_regime = {
        "🟢 成長期": {"股票型": 50, "核心債券": 30, "衛星主題": 20},
        "🟡 過熱期": {"股票型": 30, "核心債券": 40, "實物資產": 20, "現金": 10},
        "🔵 復甦期": {"股票型": 45, "核心債券": 35, "衛星主題": 15, "現金": 5},
        "🔴 衰退期": {"投資等級債": 50, "貨幣型": 30, "防禦股息": 20},
        "未知":      {"核心債券": 40, "股票型": 40, "現金": 20},
    }
    alloc = alloc_by_regime.get(regime, alloc_by_regime["未知"])

    return {
        "regime":        regime,
        "regime_color":  regime_color,
        "zscore_pmi":    zscore_pmi,
        "hy_spread":     hy_v,
        "alloc_suggest": alloc,
        "note": f"PMI:{pmi_v} CPI:{cpi_v} FedRate:{fed_v}",
    }


# ══════════════════════════════════════════════════════════════════
# v15: 台灣市場轉折點指標 (TPI — Three-Factor Resonance)
# TPI = Z(M1B/M2) × 0.3 + Z(Breadth) × 0.4 + Z(FII) × 0.3
# 資料來源：證交所 OpenAPI（免費，無需 Key）
# ══════════════════════════════════════════════════════════════════
def fetch_tw_market_tpi(fred_api_key: str = "") -> dict:
    """
    台股三因子轉折指標 (TPI v15.3 — NAS Proxy 全遷移)
    TPI = Z(市場寬度) × 0.4 + Z(外資淨買) × 0.3 + Z(M1B/M2) × 0.3

    [v15.3 變更]
    三大資料源 (TWSE MI_INDEX / FinMind FII / 中央銀行 M1B/M2) 改用
    tw_macro 模組,全部統一透過 proxy_helper.fetch_url 走 NAS 中繼站。
    原本 4 處直連 requests.get 全部消除。
    """
    from tw_macro import (
        fetch_twse_breadth,
        fetch_finmind_foreign_investor,
        fetch_cbc_m1b_m2,
    )

    result = {
        "tpi": None, "z_breadth": None, "z_fii": None, "z_m1b_m2": 0.0,
        "fii_net": None, "breadth": None,
        "water_label": "資料取得中", "color": "#888",
        "signal": "⬜", "advice": "", "date": "", "error": None,
        "_fred_api_key": fred_api_key,  # 保留 API 相容,雖已不再使用
    }

    # ── Factor A: TWSE 市場寬度(走 NAS) ─────────────────────────
    _b = fetch_twse_breadth()
    if _b["error"]:
        result["error"] = f"breadth: {_b['error'][:60]}"
    else:
        result["breadth"]   = _b["breadth"]
        result["z_breadth"] = _b["z_breadth"]
        result["date"]      = _b["date"]
        if _b.get("adv") is not None:
            print(f"[TPI] 上漲:{_b['adv']} 下跌:{_b['dec']} "
                  f"Breadth:{_b['breadth']:.1f}% Z:{_b['z_breadth']:.3f}")

    # ── Factor B: FinMind 外資籌碼(走 NAS) ──────────────────────
    _f = fetch_finmind_foreign_investor(days_back=7)
    if _f["error"]:
        result["error"] = (result.get("error") or "") + f" | FII:{_f['error'][:50]}"
    else:
        result["fii_net"] = _f["fii_net"]
        result["z_fii"]   = _f["z_fii"]
        if _f.get("fii_net") is not None:
            print(f"[TPI] FII {_f['date']} net:{_f['fii_net']:+,} Z:{_f['z_fii']:.3f}")

    # ── Factor C: CBC M1B/M2 三層備援(全部走 NAS) ──────────────
    _m = fetch_cbc_m1b_m2()
    if _m["m1b_yoy"] is not None:
        result["z_m1b_m2"]      = max(-3.0, min(3.0, _m["gap"] / 5.0))
        result["m1b_yoy"]       = _m["m1b_yoy"]
        result["m2_yoy"]        = _m["m2_yoy"]
        result["m1b_m2_gap"]    = _m["gap"]
        result["m1b_is_proxy"]  = _m["is_proxy_tier"]
        _cross = "黃金" if _m["gap"] > 0 else "死亡"
        _src   = "(代理估算)" if _m["is_proxy_tier"] else ""
        print(f"[M1B] Tier{_m['tier_used']} ✅ M1B:{_m['m1b_yoy']:.2f}% "
              f"M2:{_m['m2_yoy']:.2f}% Gap:{_m['gap']:+.2f}% → {_cross}交叉 {_src}")
    else:
        result["z_m1b_m2"]     = 0.0
        result["m1b_is_proxy"] = False
        print(f"[M1B] ⚠️ {_m['error']},M1B/M2 設為 0")

    # ── Composite TPI ────────────────────────────────────────────
    z_b = result["z_breadth"] or 0.0
    z_f = result["z_fii"]     or 0.0
    z_m = result["z_m1b_m2"]
    tpi = z_b * 0.4 + z_f * 0.3 + z_m * 0.3
    result["tpi"] = round(tpi, 3)

    if tpi >= 1.5:
        result.update(water_label="🥵 沸點（市場過熱）", color="#f44336", signal="🔴",
                      advice="上漲家數銳減，外資持續賣超，建議啟動獲利了結機制")
    elif tpi >= 0.5:
        result.update(water_label="🌡️ 溫熱（偏多）", color="#ff9800", signal="🟡",
                      advice="市場動能良好，持續觀察是否過熱，衛星部位可設停利")
    elif tpi >= -0.5:
        result.update(water_label="⚖️ 常溫（中性）", color="#888888", signal="⚪",
                      advice="市場趨向均衡，維持既有配置，觀察漲跌家數變化")
    elif tpi >= -1.5:
        result.update(water_label="🌡️ 偏冷（謹慎）", color="#64b5f6", signal="🟡",
                      advice="外資轉弱、漲跌家數惡化，考慮降低台股部位")
    else:
        result.update(water_label="🥶 冰點（底部特徵）", color="#9c27b0", signal="🟢",
                      advice="散戶絕望期，偵測到底部特徵，準備分批建倉")

    return result


# ══════════════════════════════════════════════════════════════════
# v18.1 新聞系統性風險偵測（關鍵字加權評分）
# ══════════════════════════════════════════════════════════════════
_RISK_KEYWORDS = {
    # ── 流動性危機（最高風險）
    "default":       4, "debt crisis":   4, "bank run":       4,
    "bankruptcy":    4, "contagion":      4, "lehman":         4,
    "systemic":      3, "liquidity":      3, "credit crunch":  3,
    "違約":          4, "崩盤":           4, "擠兌":           4,
    "金融危機":      4, "系統性風險":     4, "破產":           3,
    # ── 衰退 / 停滯
    "recession":     3, "stagflation":    3, "depression":     3,
    "slowdown":      2, "contraction":    2, "gdp decline":    2,
    "衰退":          3, "滯脹":           3, "蕭條":           3,
    "負成長":        2, "景氣惡化":       2,
    # ── 央行緊急行動
    "emergency cut": 3, "rate hike":      2, "tightening":     2,
    "暴力升息":      3, "緊急降息":       3, "意外升息":       3,
    # ── 地緣政治 / 貿易
    "war":           2, "sanction":       2, "tariff":         2,
    "trade war":     2, "escalation":     2,
    "戰爭":          2, "制裁":           2, "關稅":           2,
    "脫鉤":          2, "升級":           1,
}

def detect_systemic_risk(news_items: list) -> dict:
    """
    對新聞列表做關鍵字加權掃描，回傳系統性風險評估。

    回傳格式：
    {
      "risk_level":  "HIGH" | "MEDIUM" | "LOW",
      "risk_score":  int,
      "risk_color":  str (hex),
      "risk_icon":   str,
      "triggered":   [{"keyword": str, "count": int, "weight": int, "sub_score": int}],
      "headlines":   [str],  ← 命中關鍵字的新聞標題
      "advice":      str,
    }
    算法：
      sub_score_i = keyword_weight_i × hit_count_i
      total_score = Σ sub_score_i
      HIGH   : score ≥ 10（多重高危信號，建議立即降低風險暴露）
      MEDIUM : score ≥ 5 （警示狀態，密切追蹤）
      LOW    : score <  5 （暫無系統性異常）
    """
    import re as _re

    all_text   = []
    title_map  = {}   # keyword → list of matching titles

    for item in (news_items or []):
        title   = str(item.get("title",   ""))
        summary = str(item.get("summary", ""))
        combined = (title + " " + summary).lower()
        all_text.append(combined)
        # 建立 keyword → title 映射（供展示用）
        for kw in _RISK_KEYWORDS:
            if kw in combined:
                title_map.setdefault(kw, []).append(title[:80])

    full_corpus = " ".join(all_text)
    triggered   = []
    total_score = 0

    for kw, weight in sorted(_RISK_KEYWORDS.items(), key=lambda x: -x[1]):
        # 使用 word boundary 避免誤判（e.g. "war" in "forward"）
        count = len(_re.findall(r'\b' + _re.escape(kw) + r'\b', full_corpus))
        if count > 0:
            sub = weight * min(count, 3)   # 同一關鍵字最多計 3 次，避免單篇洗版
            total_score += sub
            triggered.append({
                "keyword":   kw,
                "count":     count,
                "weight":    weight,
                "sub_score": sub,
            })

    # 命中關鍵字對應的標題（最多 5 則）
    hit_titles = []
    for kw in [t["keyword"] for t in triggered[:5]]:
        for title in title_map.get(kw, []):
            if title not in hit_titles:
                hit_titles.append(title)
    hit_titles = hit_titles[:5]

    # 風險等級判定
    if total_score >= 10:
        level  = "HIGH"
        color  = "#f44336"
        icon   = "🚨"
        advice = "偵測到多重高危信號，建議立即提高現金比重，核心部位 ≥80%，衛星部位設停損"
    elif total_score >= 5:
        level  = "MEDIUM"
        color  = "#ff9800"
        icon   = "⚠️"
        advice = "市場存在潛在壓力訊號，密切追蹤 VIX 與 HY 利差，衛星部位設停利"
    else:
        level  = "LOW"
        color  = "#00c853"
        icon   = "✅"
        advice = "新聞面暫無系統性異常，維持既有配置策略"

    return {
        "risk_level":  level,
        "risk_score":  total_score,
        "risk_color":  color,
        "risk_icon":   icon,
        "triggered":   triggered[:10],
        "headlines":   hit_titles,
        "advice":      advice,
    }


# ══════════════════════════════════════════════════════════════════
# v18.20 景氣拐點監控（Leading Indicator Tracker）
# ══════════════════════════════════════════════════════════════════
def _yoy_pct(df: pd.DataFrame, periods: int = 12) -> pd.Series:
    """月頻 DataFrame → YoY %（與 12 個月前比較）。回傳 pd.Series（index=date, 值=%）。"""
    if df is None or df.empty or len(df) < periods + 2:
        return pd.Series(dtype=float)
    s = df.sort_values("date").set_index("date")["value"].astype(float)
    return (s / s.shift(periods) - 1.0) * 100.0


def detect_turning_points(fred_api_key: str = "") -> dict:
    """景氣拐點偵測 (v18.20)

    指標一：新訂單 YoY − 庫存 YoY（製造業 M3 調查代理 ISM 新訂單－庫存擴散）
        - FRED AMTMNO   : Manufacturers' New Orders: Total Manufacturing（月頻）
        - FRED MNFCTRIRSA: Manufacturers' Total Inventories（月頻）
        - 訊號邏輯：近 3 月 (orders_yoy − inv_yoy) 序列若前一期 ≤ 0 而本期 > 0
          → 🚀 擴張拐點已現；否則回報目前狀態（擴張中 / 收縮中 / 持平）
        - 說明：ISM 自 2016-08 起對 FRED 收回授權，FRED 已無 ISM 子分項細項；
          M3 調查（Census）為次優替代，與 ISM 新訂單－庫存相關性 ~0.7

    指標二：10Y − 2Y 殖利率利差（T10Y2Y）
        - FRED T10Y2Y（日頻）
        - 訊號邏輯：最近 60 日內曾倒掛（min < 0）且最新值 ≥ 0 → ⚠️ 衰退末期反彈
          否則回報「正斜率」/「倒掛」/「資料不足」

    Returns
    -------
    {
      "pmi_diff":    {signal, color, icon, value, prev, trend(list), label, note, source_ok},
      "yield_curve": {signal, color, icon, value, prev, trend(list), label, note, source_ok},
    }
    """
    out: dict = {
        "pmi_diff": {
            "signal": "⬜ 資料不足", "color": "#888", "icon": "⬜",
            "value": None, "prev": None, "trend": [],
            "label": "新訂單 YoY − 庫存 YoY (M3 製造業)",
            "note": "FRED API 失敗或資料不足", "source_ok": False,
        },
        "yield_curve": {
            "signal": "⬜ 資料不足", "color": "#888", "icon": "⬜",
            "value": None, "prev": None, "trend": [],
            "label": "10Y − 2Y 利差 (T10Y2Y)",
            "note": "FRED API 失敗或資料不足", "source_ok": False,
        },
        # v18.250 新增三組景氣反轉拐點
        "hy_spread": {
            "signal": "⬜ 資料不足", "color": "#888", "icon": "⬜",
            "value": None, "prev": None, "trend": [],
            "label": "HY 信用利差 (BAMLH0A0HYM2)",
            "note": "FRED API 失敗或資料不足", "source_ok": False,
        },
        "sahm_rule": {
            "signal": "⬜ 資料不足", "color": "#888", "icon": "⬜",
            "value": None, "prev": None, "trend": [],
            "label": "薩姆規則 (SAHMREALTIME)",
            "note": "FRED API 失敗或資料不足", "source_ok": False,
        },
        "lei_cfnai": {
            "signal": "⬜ 資料不足", "color": "#888", "icon": "⬜",
            "value": None, "prev": None, "trend": [],
            "label": "CFNAI 領先指標 3M MA",
            "note": "FRED API 失敗或資料不足", "source_ok": False,
        },
    }

    if not fred_api_key:
        return out

    # ── 指標一：新訂單 − 庫存 YoY 擴散 ──────────────────────────────
    try:
        df_new = fetch_fred("AMTMNO",     fred_api_key, n=60)
        df_inv = fetch_fred("MNFCTRIRSA", fred_api_key, n=60)
        ny = _yoy_pct(df_new)
        iy = _yoy_pct(df_inv)
        if not ny.empty and not iy.empty:
            joined = pd.concat([ny.rename("o"), iy.rename("i")], axis=1).dropna().tail(12)
            if len(joined) >= 2:
                diff = (joined["o"] - joined["i"]).tolist()
                cur, prev = diff[-1], diff[-2]
                trend = [round(v, 2) for v in diff[-6:]]
                # 拐點：前期 ≤ 0 且本期 > 0
                if prev <= 0 and cur > 0:
                    sig, col, ic = "🚀 擴張拐點已現", "#00c853", "🚀"
                    note = (f"前期 {prev:+.1f}pp → 本期 {cur:+.1f}pp（由負轉正）"
                            f"｜製造業新訂單成長動能首度超越庫存補貨")
                elif cur > 0 and prev > 0:
                    sig, col, ic = "🟢 擴張延續", "#00c853", "🟢"
                    note = f"連續正值 {cur:+.1f}pp，新訂單動能 > 庫存補貨"
                elif cur < 0 and prev > 0:
                    sig, col, ic = "🟡 動能轉弱", "#ff9800", "🟡"
                    note = f"前期 {prev:+.1f}pp → 本期 {cur:+.1f}pp（由正轉負）需觀察"
                elif cur < 0:
                    sig, col, ic = "🔻 收縮中", "#f44336", "🔻"
                    note = f"{cur:+.1f}pp，新訂單動能弱於庫存補貨"
                else:
                    sig, col, ic = "📊 持平", "#888", "📊"
                    note = f"{cur:+.1f}pp，無明確方向"
                out["pmi_diff"].update({
                    "signal": sig, "color": col, "icon": ic,
                    "value": round(cur, 2), "prev": round(prev, 2),
                    "trend": trend, "note": note, "source_ok": True,
                })
    except Exception as e:
        out["pmi_diff"]["note"] = f"AMTMNO/MNFCTRIRSA 抓取異常：{str(e)[:80]}"

    # ── 指標二：10Y − 2Y 殖利率利差倒掛翻正 ────────────────────────
    try:
        df_t = fetch_fred("T10Y2Y", fred_api_key, n=120)
        if not df_t.empty and len(df_t) >= 30:
            s = df_t.sort_values("date").set_index("date")["value"].astype(float).dropna()
            window60 = s.tail(60)
            cur = float(s.iloc[-1])
            prev = float(s.iloc[-2]) if len(s) >= 2 else None
            min60 = float(window60.min())
            trend = [round(v, 2) for v in s.tail(60).resample("W").last().dropna().tail(8).tolist()]
            if min60 < 0 and cur >= 0:
                sig, col, ic = "⚠️ 衰退末期，布局反彈", "#ff9800", "⚠️"
                note = (f"近 60 日最低 {min60:+.2f}%（倒掛）→ 最新 {cur:+.2f}%（翻正）"
                        f"｜歷史經驗：倒掛翻正後 6~18 月為股市底部累積期")
            elif cur < 0:
                sig, col, ic = "🔴 倒掛中", "#f44336", "🔴"
                note = f"{cur:+.2f}%（仍倒掛），衰退預警維持"
            elif cur >= 0 and min60 >= 0:
                sig, col, ic = "🟢 正斜率（健康）", "#00c853", "🟢"
                note = f"{cur:+.2f}%（近 60 日皆 ≥0），無拐點訊號"
            else:
                sig, col, ic = "📊 持平", "#888", "📊"
                note = f"{cur:+.2f}%"
            out["yield_curve"].update({
                "signal": sig, "color": col, "icon": ic,
                "value": round(cur, 2),
                "prev": round(prev, 2) if prev is not None else None,
                "trend": trend, "note": note, "source_ok": True,
            })
    except Exception as e:
        out["yield_curve"]["note"] = f"T10Y2Y 抓取異常：{str(e)[:80]}"

    # ── 指標三：HY 信用利差由高位回落（v18.250） ────────────────────
    try:
        df_hy = fetch_fred("BAMLH0A0HYM2", fred_api_key, n=400)
        if not df_hy.empty and len(df_hy) >= 30:
            s = df_hy.sort_values("date").set_index("date")["value"].astype(float).dropna()
            cur = float(s.iloc[-1]); prev = float(s.iloc[-2])
            max90 = float(s.tail(90).max())
            trend = [round(v, 2) for v in s.tail(60).resample("W").last().dropna().tail(8).tolist()]
            if max90 >= 6.0 and cur < max90 * 0.85 and cur < prev:
                sig, col, ic = "🚀 信用拐點：高位回落", "#00c853", "🚀"
                note = (f"90 日高點 {max90:.2f}% → 最新 {cur:.2f}%（-{max90-cur:.2f}pp）"
                        f"｜信用風險溢價收斂，risk-on 醞釀")
            elif cur >= 6:
                sig, col, ic = "🔴 高風險區", "#f44336", "🔴"
                note = f"{cur:.2f}% ≥ 6%，信用市場警戒中"
            elif cur < 4:
                sig, col, ic = "🟢 信用寬鬆", "#00c853", "🟢"
                note = f"{cur:.2f}% < 4%，市場樂觀（尚無拐點）"
            else:
                sig, col, ic = "🟡 中性帶", "#ff9800", "🟡"
                note = f"{cur:.2f}%，介於 4~6%（待觀察方向）"
            out["hy_spread"].update({
                "signal": sig, "color": col, "icon": ic,
                "value": round(cur, 2), "prev": round(prev, 2),
                "trend": trend, "note": note, "source_ok": True,
            })
    except Exception as e:
        out["hy_spread"]["note"] = f"BAMLH0A0HYM2 抓取異常：{str(e)[:80]}"

    # ── 指標四：薩姆規則由觸發→解除（v18.250） ──────────────────────
    try:
        df_sa = fetch_fred("SAHMREALTIME", fred_api_key, n=36)
        if not df_sa.empty and len(df_sa) >= 6:
            s = df_sa.sort_values("date").set_index("date")["value"].astype(float).dropna()
            cur = float(s.iloc[-1]); prev = float(s.iloc[-2])
            max12 = float(s.tail(12).max())
            trend = [round(v, 2) for v in s.tail(8).tolist()]
            if max12 >= 0.5 and cur < 0.5:
                sig, col, ic = "🚀 衰退警報解除", "#00c853", "🚀"
                note = (f"近 12 月高點 {max12:.2f}（觸發過 0.5）→ 最新 {cur:.2f}"
                        f"｜歷史經驗：解除後 12 月內為股市底部布局期")
            elif cur >= 0.5:
                sig, col, ic = "🔴 衰退警報中", "#f44336", "🔴"
                note = f"{cur:.2f} ≥ 0.5，失業率上升訊號"
            elif cur < 0.3:
                sig, col, ic = "🟢 安全區", "#00c853", "🟢"
                note = f"{cur:.2f} < 0.3，無衰退訊號"
            else:
                sig, col, ic = "🟡 警戒中", "#ff9800", "🟡"
                note = f"{cur:.2f}，介於 0.3~0.5（接近觸發）"
            out["sahm_rule"].update({
                "signal": sig, "color": col, "icon": ic,
                "value": round(cur, 2), "prev": round(prev, 2),
                "trend": trend, "note": note, "source_ok": True,
            })
    except Exception as e:
        out["sahm_rule"]["note"] = f"SAHMREALTIME 抓取異常：{str(e)[:80]}"

    # ── 指標五：CFNAI 領先指標 3M MA 翻揚（v18.250） ─────────────────
    try:
        df_lei = fetch_fred("CFNAI", fred_api_key, n=36)
        if not df_lei.empty and len(df_lei) >= 6:
            s = df_lei.sort_values("date").set_index("date")["value"].astype(float).dropna()
            ma3 = s.rolling(3).mean().dropna()
            if len(ma3) >= 2:
                cur = float(ma3.iloc[-1]); prev = float(ma3.iloc[-2])
                trend = [round(v, 2) for v in ma3.tail(8).tolist()]
                if cur > 0 and prev <= 0:
                    sig, col, ic = "🚀 領先指標翻揚", "#00c853", "🚀"
                    note = (f"3M MA：前期 {prev:+.2f} → 本期 {cur:+.2f}（由負轉正）"
                            f"｜85 指標 z-score 平均轉正，景氣進入擴張")
                elif cur > 0:
                    sig, col, ic = "🟢 擴張中", "#00c853", "🟢"
                    note = f"3M MA {cur:+.2f}（正值），景氣正常擴張"
                elif cur < -0.7:
                    sig, col, ic = "🔴 衰退預警", "#f44336", "🔴"
                    note = f"3M MA {cur:+.2f} < -0.7，強烈衰退訊號"
                elif cur < 0:
                    sig, col, ic = "🟡 動能轉弱", "#ff9800", "🟡"
                    note = f"3M MA {cur:+.2f}（負值但 > -0.7），待觀察"
                else:
                    sig, col, ic = "📊 持平", "#888", "📊"
                    note = f"3M MA {cur:+.2f}"
                out["lei_cfnai"].update({
                    "signal": sig, "color": col, "icon": ic,
                    "value": round(cur, 2), "prev": round(prev, 2),
                    "trend": trend, "note": note, "source_ok": True,
                })
    except Exception as e:
        out["lei_cfnai"]["note"] = f"CFNAI 抓取異常：{str(e)[:80]}"

    return out


# ══════════════════════════════════════════════════════════════════
# v18.21 倒掛翻正歷史回測（Leading Indicator Backtest）
# ══════════════════════════════════════════════════════════════════
def _find_uninversion_events(s: pd.Series,
                             min_inversion_depth: float,
                             stable_days: int,
                             cooldown_days: int) -> list:
    """掃描 T10Y2Y 序列，識別所有「真倒掛 → 穩定翻正」事件。

    事件定義（同時滿足）：
      1. 區段內 min(T10Y2Y) ≤ min_inversion_depth（去除貼地噪音）
      2. 翻正日 T10Y2Y ≥ 0 且後續 stable_days 日皆 ≥ 0（穩定翻正去抖）
      3. 距上一事件 ≥ cooldown_days（避免同週期重複觸發）

    Returns: [{"date": Timestamp, "t10y2y_min_pre": float}, ...]
    """
    if s is None or s.empty or len(s) < stable_days + 2:
        return []
    s = s.sort_index().dropna()
    vals  = s.values
    dates = s.index

    events: list = []
    in_inversion = False
    seg_min      = 0.0
    last_event_t = None

    for i in range(len(vals)):
        v = vals[i]
        if v < 0:
            if not in_inversion:
                in_inversion = True
                seg_min = v
            else:
                seg_min = min(seg_min, v)
        else:
            # 候選翻正日
            if in_inversion and seg_min <= min_inversion_depth:
                # 驗 stable_days 天皆 ≥ 0
                end = i + stable_days
                if end <= len(vals) and (vals[i:end] >= 0).all():
                    t = dates[i]
                    if last_event_t is None or (t - last_event_t).days >= cooldown_days:
                        events.append({
                            "date": t,
                            "t10y2y_min_pre": float(round(seg_min, 3)),
                        })
                        last_event_t = t
            in_inversion = False
            seg_min      = 0.0
    return events


def _forward_return(spx: pd.Series, t0: pd.Timestamp, days: int):
    """SPX 從 t0 起 days 天後的累計報酬（%）。窗口未到期回 None。"""
    if spx is None or spx.empty:
        return None
    try:
        # t0 最近後續交易日（含當日）
        idx0 = spx.index.searchsorted(t0)
        if idx0 >= len(spx):
            return None
        p0 = float(spx.iloc[idx0])
        t1 = t0 + pd.Timedelta(days=days)
        idx1 = spx.index.searchsorted(t1)
        if idx1 >= len(spx):
            return None
        p1 = float(spx.iloc[idx1])
        if p0 <= 0:
            return None
        return round((p1 / p0 - 1.0) * 100.0, 2)
    except Exception:
        return None


def backtest_turning_points(
    fred_api_key: str = "",
    min_inversion_depth: float = -0.10,
    stable_days: int = 5,
    cooldown_days: int = 365,
) -> dict:
    """倒掛翻正歷史回測（v18.21）

    抓 30Y+ T10Y2Y 日頻 + ^GSPC 全歷史，識別所有「倒掛→翻正」事件，
    對每事件計算 SPX 後續 6M / 12M / 18M 累計報酬，及樣本中位數與勝率。

    Parameters
    ----------
    min_inversion_depth: float, default -0.10
        倒掛深度門檻（%），需 ≤ 此值才算真倒掛
    stable_days: int, default 5
        翻正後須連續 ≥0 天數
    cooldown_days: int, default 365
        兩事件最小間隔（避免同週期重複觸發）

    Returns
    -------
    {
      "events": [
        {"date": Timestamp, "t10y2y_min_pre": float,
         "ret_6m": float|None, "ret_12m": float|None, "ret_18m": float|None,
         "complete": bool},  # complete=False 表示 18M 窗口未到期
        ...
      ],
      "summary": {"n_events": int, "n_complete_18m": int,
                  "median_6m/12m/18m": float, "mean_6m/12m/18m": float,
                  "win_rate_6m/12m/18m": float},
      "spx_series":   pd.Series,
      "t10y2y_series": pd.Series,
      "source_ok": bool,
      "note": str,
    }
    """
    out: dict = {
        "events": [],
        "summary": {"n_events": 0, "n_complete_18m": 0,
                    "median_6m": None,  "median_12m": None, "median_18m": None,
                    "mean_6m":   None,  "mean_12m":   None, "mean_18m":   None,
                    "win_rate_6m": None, "win_rate_12m": None, "win_rate_18m": None},
        "spx_series":    pd.Series(dtype=float),
        "t10y2y_series": pd.Series(dtype=float),
        "source_ok": False,
        "note": "",
    }

    if not fred_api_key:
        out["note"] = "FRED API key 未設置"
        return out

    # ── 抓 T10Y2Y 30Y+ ───────────────────────────────────────────
    try:
        df_t = fetch_fred("T10Y2Y", fred_api_key, n=11000)
    except Exception as e:
        out["note"] = f"T10Y2Y 抓取異常：{str(e)[:80]}"
        return out
    if df_t is None or df_t.empty or len(df_t) < 1000:
        out["note"] = "T10Y2Y 資料不足（< 1000 obs）"
        return out

    s_t = (df_t.sort_values("date").set_index("date")["value"]
                 .astype(float).dropna())
    try:
        s_t.index = s_t.index.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    out["t10y2y_series"] = s_t

    # ── 抓 SPX 全歷史 ────────────────────────────────────────────
    try:
        spx = fetch_yf_close("^GSPC", range_="max", interval="1d")
    except Exception as e:
        out["note"] = f"^GSPC 抓取異常：{str(e)[:80]}"
        return out
    if spx is None or spx.empty or len(spx) < 1000:
        out["note"] = "SPX history insufficient (< 1000 trading days)"
        return out
    try:
        spx.index = spx.index.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    out["spx_series"] = spx.sort_index()

    # ── 事件識別 ────────────────────────────────────────────────
    events = _find_uninversion_events(
        s_t, min_inversion_depth=min_inversion_depth,
        stable_days=stable_days, cooldown_days=cooldown_days,
    )

    # ── 對每事件計算 SPX +6M/+12M/+18M 報酬 ──────────────────────
    today = pd.Timestamp.today().normalize()
    enriched: list = []
    for ev in events:
        t0 = ev["date"]
        r6  = _forward_return(out["spx_series"], t0, 182)
        r12 = _forward_return(out["spx_series"], t0, 365)
        r18 = _forward_return(out["spx_series"], t0, 547)
        complete = (today - t0).days >= 547 and r18 is not None
        enriched.append({
            "date": t0,
            "t10y2y_min_pre": ev["t10y2y_min_pre"],
            "ret_6m":  r6,
            "ret_12m": r12,
            "ret_18m": r18,
            "complete": complete,
        })
    out["events"] = enriched

    # ── Summary 統計（只納完整窗口）─────────────────────────────
    def _stat(key: str, require_complete: bool = False):
        vals = [e[key] for e in enriched
                if e[key] is not None
                and (e["complete"] if require_complete else True)]
        if not vals:
            return None, None, None
        med = float(np.median(vals))
        avg = float(np.mean(vals))
        wr  = float(sum(1 for v in vals if v > 0) / len(vals) * 100.0)
        return round(med, 2), round(avg, 2), round(wr, 1)

    m6,  a6,  w6  = _stat("ret_6m")
    m12, a12, w12 = _stat("ret_12m")
    m18, a18, w18 = _stat("ret_18m", require_complete=True)

    out["summary"].update({
        "n_events":        len(enriched),
        "n_complete_18m":  sum(1 for e in enriched if e["complete"]),
        "median_6m":   m6,  "median_12m": m12, "median_18m": m18,
        "mean_6m":     a6,  "mean_12m":   a12, "mean_18m":   a18,
        "win_rate_6m": w6,  "win_rate_12m": w12, "win_rate_18m": w18,
    })
    out["source_ok"] = True
    out["note"] = f"識別 {len(enriched)} 個事件（去抖 stable={stable_days}d, depth≤{min_inversion_depth}）"
    return out


# ════════════════════════════════════════════════════════════
# v18.100 景氣循環細項燈號（Phase 2 — Sub-Cycle Lights）
# 7 個子領域，各取 1-2 個既有指標 z-score 平均 → 🟢🟡🔴
# ════════════════════════════════════════════════════════════
_SUB_CYCLE_SPEC = [
    # (name, icon, [(indicator_key, high_is_bad)], description)
    ("製造業",   "🏭", [("PMI", False), ("LEI", False)],
     "ISM PMI 50 線 + CFNAI 領先指標"),
    ("房市",     "🏠", [("PERMIT_HOUSING", False)],
     "建照核發年化（領先 6-12 個月）"),
    ("就業",     "💼", [("JOBLESS", True), ("CONT_CLAIMS", True)],
     "初領 + 持續失業金（裁員領先指標）"),
    ("信貸",     "💳", [("SLOOS", True), ("HY_SPREAD", True)],
     "銀行放貸意願 + 高收益債利差"),
    ("流動性",   "💧", [("M2", False), ("FED_BS", False)],
     "M2 貨幣供給 + Fed 資產負債表年增"),
    ("消費",     "🛒", [("CONSUMER_CONF", False), ("COPPER", False)],
     "Michigan 消費信心 + 銅博士月漲跌"),
    ("通膨壓力", "🔥", [("CPI", True), ("PPI", True)],
     "CPI + PPI 年增（越低越好）"),
]


def _calc_zscore_safe(series, current_value=None):
    """Z-Score 容錯計算（複製自 shared.macro_card.calc_z_score，避開循環 import）。"""
    if series is None:
        return None
    try:
        import pandas as pd
        s = series if isinstance(series, pd.Series) else pd.Series(series)
        s = s.dropna()
        if len(s) < 10:
            return None
        mu, sigma = float(s.mean()), float(s.std())
        if sigma == 0:
            return None
        v = float(current_value) if current_value is not None else float(s.iloc[-1])
        return (v - mu) / sigma
    except Exception:
        return None


def calc_sub_cycle_lights(indicators: dict) -> list[dict]:
    """景氣循環細項燈號 — 7 個子領域燈號（Phase 2 v18.100）。

    Args:
        indicators: macro_engine 載入後的 dict，每 key 對應 {"value", "series", ...}

    Returns:
        list of {"name", "icon", "color", "signal", "z_avg", "verdict",
                 "indicators": [{"key", "z", "high_is_bad"}, ...],
                 "description"}

    判斷規則（依 high_is_bad 翻轉）：
        z_avg < -1.0  → 🟢 健康
        -1.0 ≤ z < 0  → 🟡 中性偏好
        0 ≤ z < 1.0   → 🟠 中性偏弱
        z ≥ 1.0       → 🔴 警示
    （high_is_bad=False 的指標，z 取負後再判斷，使「越高越好」與通膨「越低越好」可對齊。）
    """
    out = []
    for name, icon, ind_list, desc in _SUB_CYCLE_SPEC:
        z_components = []
        for key, high_is_bad in ind_list:
            iv = indicators.get(key) or {}
            series = iv.get("series")
            value = iv.get("value")
            z = _calc_zscore_safe(series, value)
            if z is None:
                continue
            # 統一語意：z_norm > 0 → 不健康；z_norm < 0 → 健康
            z_norm = z if high_is_bad else -z
            z_components.append({"key": key, "z": round(z, 2),
                                 "z_norm": round(z_norm, 2),
                                 "high_is_bad": high_is_bad})

        if not z_components:
            out.append({
                "name": name, "icon": icon, "color": "#666",
                "signal": "⬜", "z_avg": None, "verdict": "資料不足",
                "indicators": [], "description": desc,
            })
            continue

        z_avg = sum(c["z_norm"] for c in z_components) / len(z_components)
        if z_avg < -1.0:
            signal, color, verdict = "🟢", "#4caf50", "健康"
        elif z_avg < 0:
            signal, color, verdict = "🟡", "#ffeb3b", "中性偏好"
        elif z_avg < 1.0:
            signal, color, verdict = "🟠", "#ff9800", "中性偏弱"
        else:
            signal, color, verdict = "🔴", "#f44336", "警示"

        out.append({
            "name": name, "icon": icon, "color": color,
            "signal": signal, "z_avg": round(z_avg, 2),
            "verdict": verdict, "indicators": z_components,
            "description": desc,
        })
    return out


# ════════════════════════════════════════════════════════════
# v18.101 總經因果鏈 Sankey（Phase 2 — Macro Causal Sankey）
# 視覺化「政策 → 信貸 → 實體經濟 → 市場」三層因果，邊粗細由 z-score 決定
# ════════════════════════════════════════════════════════════
_SANKEY_NODES = [
    # (key, label, layer, high_is_bad)
    ("FED_RATE",        "🏛️ 聯準會利率",    0, True),
    ("SLOOS",           "🏦 銀行放貸意願",    1, True),
    ("HY_SPREAD",       "💳 信用利差",        1, True),
    ("PERMIT_HOUSING",  "🏠 房市建照",        2, False),
    ("JOBLESS",         "💼 失業金",          2, True),
    ("PMI",             "🏭 製造業 PMI",      2, False),
    ("VIX",             "😱 VIX 恐慌",        3, True),
    ("DXY",             "💵 美元指數",        3, True),
]

_SANKEY_LINKS = [
    # (source_key, target_key, edu_note)
    ("FED_RATE",        "SLOOS",          "升息 → 銀行緊縮放貸"),
    ("FED_RATE",        "HY_SPREAD",      "升息 → 信用利差擴大"),
    ("FED_RATE",        "DXY",            "升息 → 美元走強"),
    ("SLOOS",           "PERMIT_HOUSING", "放貸寬鬆 → 建照增加"),
    ("SLOOS",           "JOBLESS",        "放貸緊縮 → 失業上升"),
    ("HY_SPREAD",       "VIX",            "信用利差擴大 → 市場恐慌"),
    ("PERMIT_HOUSING",  "PMI",            "房市熱 → 製造業（建材）回升"),
    ("DXY",             "PMI",            "美元走強 → 出口承壓"),
    ("JOBLESS",         "VIX",            "失業惡化 → 市場避險"),
]


def build_macro_sankey_data(indicators: dict) -> dict:
    """總經因果鏈 Sankey 視覺化資料（Phase 2 v18.101）。

    Args:
        indicators: macro_engine 載入後的 dict

    Returns:
        {
          "labels":    [str, ...],          # 節點標籤（含 z 註記）
          "sources":   [int, ...],          # link 起點 index
          "targets":   [int, ...],          # link 終點 index
          "values":    [float, ...],        # 邊粗細 = 起點 |z| × 1.0（最小 0.3）
          "node_colors": [str, ...],        # 節點顏色（依 z_norm 健康度）
          "link_colors": [str, ...],        # 邊顏色（rgba 半透明）
          "link_labels": [str, ...],        # hover 教學文字
          "ok":        bool,                # 至少 50% 節點有 z 才算 ok
          "note":      str,
        }

    視覺解讀：
      - 節點顏色：🟢 健康 / 🟡 中性 / 🔴 警示（依 z_norm = z×(high_is_bad?1:-1)）
      - 邊粗細：起點 |z|（越偏離均值越粗）
      - 點開可看 hover 教學「升息 → ...」
    """
    node_z: dict = {}
    node_z_norm: dict = {}
    for key, _label, _layer, high_is_bad in _SANKEY_NODES:
        iv = indicators.get(key) or {}
        z = _calc_zscore_safe(iv.get("series"), iv.get("value"))
        node_z[key] = z
        if z is not None:
            node_z_norm[key] = z if high_is_bad else -z

    def _node_color(z_norm):
        if z_norm is None:
            return "#666"
        if z_norm < -1.0:
            return "#4caf50"   # 🟢
        if z_norm < 0:
            return "#ffeb3b"   # 🟡
        if z_norm < 1.0:
            return "#ff9800"   # 🟠
        return "#f44336"       # 🔴

    labels = []
    node_colors = []
    key_to_idx = {}
    for i, (key, label, _layer, _hib) in enumerate(_SANKEY_NODES):
        z = node_z.get(key)
        z_str = f" (z={z:+.1f})" if z is not None else ""
        labels.append(label + z_str)
        node_colors.append(_node_color(node_z_norm.get(key)))
        key_to_idx[key] = i

    sources, targets, values, link_colors, link_labels = [], [], [], [], []
    for src_key, tgt_key, edu in _SANKEY_LINKS:
        sources.append(key_to_idx[src_key])
        targets.append(key_to_idx[tgt_key])
        z_src = node_z.get(src_key)
        val = max(0.3, abs(z_src)) if z_src is not None else 0.3
        values.append(round(val, 2))
        # 邊顏色用起點顏色 + 0.35 alpha
        base = node_colors[key_to_idx[src_key]]
        if base.startswith("#") and len(base) == 7:
            r = int(base[1:3], 16); g = int(base[3:5], 16); b = int(base[5:7], 16)
            link_colors.append(f"rgba({r},{g},{b},0.35)")
        else:
            link_colors.append("rgba(120,120,120,0.35)")
        link_labels.append(edu)

    n_with_z = sum(1 for z in node_z.values() if z is not None)
    ok = n_with_z >= max(1, len(_SANKEY_NODES) // 2)
    return {
        "labels": labels,
        "sources": sources,
        "targets": targets,
        "values": values,
        "node_colors": node_colors,
        "link_colors": link_colors,
        "link_labels": link_labels,
        "ok": ok,
        "note": f"{n_with_z}/{len(_SANKEY_NODES)} 節點有 z-score",
    }


# ════════════════════════════════════════════════════════════
# v18.105 總經指南針 Phase 3
# (A) 因果鏈動態權重 — Sankey 邊粗細改用「兩端 series 相關係數」
# (B) 細項燈號歷史回測 — 燈號出現後 target 指標的 3M / 6M 變化
# ════════════════════════════════════════════════════════════

def _series_correlation(s1, s2) -> float | None:
    """兩 series 共同期間的 Pearson 相關係數。資料 <12 期回 None。"""
    if s1 is None or s2 is None:
        return None
    try:
        import pandas as pd
        a = s1 if isinstance(s1, pd.Series) else pd.Series(s1)
        b = s2 if isinstance(s2, pd.Series) else pd.Series(s2)
        joined = pd.concat([a.dropna(), b.dropna()], axis=1, join="inner")
        if len(joined) < 12:
            return None
        corr = float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))
        return None if (corr != corr) else corr   # NaN guard
    except Exception:
        return None


def build_macro_sankey_dynamic(indicators: dict) -> dict:
    """Phase 3 (A) — 動態權重版 Sankey。

    取代固定 |z|，改用兩端 series 在共同期間的 |corr| 決定邊粗細：
    - |corr| < 0.1 → 0.3（floor，幾乎無關）
    - 0.1 ≤ |corr| < 0.5 → 1 + |corr|×2（弱相關）
    - |corr| ≥ 0.5 → 2 + |corr|×4（強相關，最粗 6）

    Returns 同 build_macro_sankey_data 結構 + extra:
      - "link_corrs": [float|None] 每條邊的實際 corr（可正可負，用於 hover）
    """
    base = build_macro_sankey_data(indicators)
    if not base["ok"]:
        return {**base, "link_corrs": [None] * len(base["sources"])}

    link_corrs = []
    new_values = []
    new_labels = list(base["link_labels"])
    key_by_idx = [n[0] for n in _SANKEY_NODES]
    for i, (src_key, tgt_key, edu) in enumerate(_SANKEY_LINKS):
        s_src = (indicators.get(src_key) or {}).get("series")
        s_tgt = (indicators.get(tgt_key) or {}).get("series")
        corr = _series_correlation(s_src, s_tgt)
        link_corrs.append(corr)
        if corr is None:
            new_values.append(0.3)
        else:
            ac = abs(corr)
            if ac < 0.1:
                w = 0.3
            elif ac < 0.5:
                w = 1.0 + ac * 2
            else:
                w = 2.0 + ac * 4
            new_values.append(round(w, 2))
        # hover label 加 corr 註記
        if corr is not None:
            new_labels[i] = f"{edu}（corr={corr:+.2f}）"

    return {
        **base,
        "values": new_values,
        "link_labels": new_labels,
        "link_corrs": link_corrs,
        "note": base["note"] + f"；邊粗細＝動態 |corr| × 加權",
    }


def _to_monthly(s):
    """[v18.111] 統一把任意頻率的 series resample 到月底 (ME) + 季頻 ffill。

    為 Phase 3-B 服務：原版 backtest_sub_cycle_lights 用 raw period count
    當 `window=60` 門檻，對 daily / weekly / monthly / quarterly series 語意完全不同
    （日 ≈ 3 個月、週 ≈ 14 個月、月 = 5 年）→ 必須先統一頻率才有意義。

    處理：
      - 無 DatetimeIndex → 原樣回傳（已是純數列無法 resample）
      - 有 DatetimeIndex → resample("ME").last() 取每月最後一筆值
      - ffill() 把季頻（如 SLOOS）的中間月補上前期值，避免 dropna 後變 sparse
      - 最後 dropna 刪只剩 leading NaN（首期之前）
    """
    import pandas as pd
    if s is None:
        return pd.Series(dtype=float)
    try:
        ss = s if isinstance(s, pd.Series) else pd.Series(s)
        ss = ss.dropna().sort_index()
        if isinstance(ss.index, pd.DatetimeIndex):
            ss = ss.resample("ME").last().ffill().dropna()
        return ss
    except Exception:
        return pd.Series(dtype=float)


def backtest_sub_cycle_lights(indicators: dict,
                              target_key: str = "LEI",
                              window: int = 60,
                              forward_months: int = 3) -> list[dict]:
    """Phase 3 (B) — 細項燈號歷史回測（v18.111 frequency-aware 治本版）。

    對每個子領域：
      1. 取 target_key 的 series（預設 LEI / CFNAI 領先指標）
      2. 統一 resample → 月底（"ME"）+ ffill — 跨頻率（日/週/月/季）一致語意
      3. 滑動視窗 expanding：每月計算 z_avg（用該月之前的全部歷史）
      4. 依 z_avg 分桶 🟢/🟡/🟠/🔴
      5. 對每桶計算「該月後 forward_months 後 target 變化」的平均

    Args:
        indicators: macro_engine 載入後 dict（含 _SUB_CYCLE_SPEC 列出的 key）
        target_key: 用哪個指標的「forward_months 期變化」當回測 outcome
        window: **明確語意：最少觀察月數**（<window 整組跳過）
                v18.111 之前是 raw period count → 對 weekly/daily series 語意錯位
        forward_months: 燈號出現後幾個月看 target 變化

    Returns:
        [{"name": str, "icon": str, "n_obs": int,
          "n_red": int, "n_orange": int, "n_yellow": int, "n_green": int,
          "fwd_chg_red": float|None, "fwd_chg_orange": float|None,
          "fwd_chg_yellow": float|None, "fwd_chg_green": float|None,
          "verdict": str},  # 例如「🔴 燈出現後 3M 平均跌 0.5pp」
         ...]
    """
    import pandas as pd
    import numpy as np

    target_iv = indicators.get(target_key) or {}
    target_series = target_iv.get("series")
    if target_series is None:
        return [{"name": n, "icon": ic, "verdict": f"target {target_key} 無 series",
                 "n_obs": 0, "n_red": 0, "n_orange": 0, "n_yellow": 0, "n_green": 0,
                 "fwd_chg_red": None, "fwd_chg_orange": None,
                 "fwd_chg_yellow": None, "fwd_chg_green": None}
                for n, ic, _, _ in _SUB_CYCLE_SPEC]
    t = _to_monthly(target_series)

    out = []
    for name, icon, ind_list, _desc in _SUB_CYCLE_SPEC:
        # 收集這組各指標的 series — 統一 resample 到月頻後再檢查 window 門檻
        series_list = []
        for key, high_is_bad in ind_list:
            iv = indicators.get(key) or {}
            ss = _to_monthly(iv.get("series"))
            if len(ss) >= window:
                series_list.append((ss, high_is_bad))

        if not series_list or t.empty:
            out.append({
                "name": name, "icon": icon, "n_obs": 0,
                "n_red": 0, "n_orange": 0, "n_yellow": 0, "n_green": 0,
                "fwd_chg_red": None, "fwd_chg_orange": None,
                "fwd_chg_yellow": None, "fwd_chg_green": None,
                "verdict": "資料不足",
            })
            continue

        # 對每組指標算 expanding z（避免未來資訊洩漏）
        buckets = {"red": [], "orange": [], "yellow": [], "green": []}
        # 用 series_list[0] 的 index 當基準（多數月底 series 同步）
        idx_base = series_list[0][0].index
        for ts in idx_base[window:]:
            z_norms = []
            for ss, hib in series_list:
                hist = ss.loc[:ts]
                if len(hist) < window:
                    continue
                mu, sigma = float(hist.mean()), float(hist.std())
                if sigma == 0:
                    continue
                v = float(hist.iloc[-1])
                z = (v - mu) / sigma
                z_norms.append(z if hib else -z)
            if not z_norms:
                continue
            z_avg = sum(z_norms) / len(z_norms)
            # 找 forward_months 後的 target
            try:
                t_now = t.asof(ts)
                future_ts = ts + pd.DateOffset(months=forward_months)
                t_future = t.asof(future_ts)
                if pd.isna(t_now) or pd.isna(t_future):
                    continue
                fwd_chg = float(t_future) - float(t_now)
            except Exception:
                continue

            if z_avg < -1.0:
                buckets["green"].append(fwd_chg)
            elif z_avg < 0:
                buckets["yellow"].append(fwd_chg)
            elif z_avg < 1.0:
                buckets["orange"].append(fwd_chg)
            else:
                buckets["red"].append(fwd_chg)

        def _avg(lst):
            return round(float(np.mean(lst)), 3) if lst else None

        n_obs = sum(len(v) for v in buckets.values())
        avg_red    = _avg(buckets["red"])
        avg_orange = _avg(buckets["orange"])
        avg_yellow = _avg(buckets["yellow"])
        avg_green  = _avg(buckets["green"])

        # 簡單 verdict：紅燈組平均 vs 綠燈組平均
        if avg_red is not None and avg_green is not None:
            diff = avg_red - avg_green
            verdict = (f"🔴 燈後 {forward_months}M：{target_key} 平均 {avg_red:+.2f}；"
                       f"🟢 燈後：{avg_green:+.2f}（差 {diff:+.2f}）")
        elif n_obs > 0:
            verdict = f"觀察 {n_obs} 月，部分桶樣本不足"
        else:
            verdict = "資料不足"

        out.append({
            "name": name, "icon": icon, "n_obs": n_obs,
            "n_red":    len(buckets["red"]),
            "n_orange": len(buckets["orange"]),
            "n_yellow": len(buckets["yellow"]),
            "n_green":  len(buckets["green"]),
            "fwd_chg_red":    avg_red,
            "fwd_chg_orange": avg_orange,
            "fwd_chg_yellow": avg_yellow,
            "fwd_chg_green":  avg_green,
            "verdict": verdict,
        })
    return out


# ════════════════════════════════════════════════════════════
# v18.108 總經指南針 Phase 4 — 變數重要性（lag-correlation 版）
# 不引入 shap / sklearn — 用簡單 |corr(node_t, target_{t+lag})| 排序
# ════════════════════════════════════════════════════════════
def rank_macro_drivers(indicators: dict,
                       target_key: str = "LEI",
                       lag_months: int = 3,
                       min_overlap: int = 24) -> dict:
    """Phase 4 — 對 Sankey 8 節點各 series，計算與 target lag_months 後變化的
    Pearson |corr|，排序回傳變數重要性 Top-N。

    重點設計：
      - 不依賴 sklearn / shap（避免新依賴）
      - lag-correlation 而非同期 corr：driver_t vs Δtarget_{t→t+lag} → 抓「領先性」
      - 並標註 corr 方向（正/負）— 正 = 同向（升升）/ 負 = 反向（升降）
      - 共同期間 <min_overlap 月 → 跳過該節點

    Args:
        indicators: macro_engine 載入後 dict（含 _SANKEY_NODES 列出的 key）
        target_key: 用哪個指標的「lag_months 期變化」當 outcome
        lag_months: 領先期數（月）
        min_overlap: 最小共同期數（<此值該節點跳過）

    Returns:
        {
          "target":      str,                  # target_key
          "lag_months":  int,
          "ranked":      [{"key": str, "name": str, "corr": float,
                           "abs_corr": float, "direction": "+/-",
                           "n_overlap": int, "weight": "高/中/低"}, ...],
          "ok":          bool,
          "note":        str,
        }
    """
    import pandas as pd
    import numpy as np

    out_empty = {
        "target": target_key, "lag_months": lag_months,
        "ranked": [], "ok": False,
        "note": f"target {target_key} 無 series 或樣本不足",
    }
    target_iv = indicators.get(target_key) or {}
    t_series = target_iv.get("series")
    if t_series is None:
        return out_empty
    try:
        t = t_series if isinstance(t_series, pd.Series) else pd.Series(t_series)
        t = t.dropna().sort_index()
    except Exception:
        return out_empty
    if len(t) < min_overlap + lag_months:
        return out_empty

    # 目標：target_{t+lag} — 標準 leading indicator lag-corr 定義
    # 用 resample 統一到月底 (ME)，避免 daily/weekly/monthly 混用
    try:
        t_m = t.resample("ME").last().dropna() \
            if hasattr(t, "resample") else t
    except Exception:
        t_m = t
    target_lagged = t_m.shift(-lag_months).dropna()
    if len(target_lagged) < min_overlap:
        return out_empty

    ranked = []
    for node in _SANKEY_NODES:
        key, label, _layer, _hib = node
        if key == target_key:
            continue   # 不對自己做變數重要性
        iv = indicators.get(key) or {}
        s = iv.get("series")
        if s is None:
            continue
        try:
            ss = s if isinstance(s, pd.Series) else pd.Series(s)
            ss = ss.dropna().sort_index()
            if hasattr(ss, "resample"):
                ss = ss.resample("ME").last().dropna()
        except Exception:
            continue
        joined = pd.concat([ss, target_lagged], axis=1, join="inner")
        joined.columns = ["driver", "target_lagged"]
        joined = joined.dropna()
        if len(joined) < min_overlap:
            continue
        try:
            corr = float(joined["driver"].corr(joined["target_lagged"]))
        except Exception:
            continue
        if corr != corr:   # NaN guard
            continue
        ac = abs(corr)
        if ac >= 0.5:
            wlabel = "高"
        elif ac >= 0.3:
            wlabel = "中"
        else:
            wlabel = "低"
        ranked.append({
            "key": key,
            "name": label,
            "corr": round(corr, 3),
            "abs_corr": round(ac, 3),
            "direction": "+" if corr >= 0 else "-",
            "n_overlap": int(len(joined)),
            "weight": wlabel,
        })

    # 依 abs_corr 降序
    ranked.sort(key=lambda x: x["abs_corr"], reverse=True)
    return {
        "target": target_key,
        "lag_months": lag_months,
        "ranked": ranked,
        "ok": len(ranked) > 0,
        "note": (f"共 {len(ranked)} 個 driver 達 ≥{min_overlap} 月共同期"
                 if ranked else "無 driver 達樣本門檻"),
    }
