"""ui/helpers/fund_grp_health/unified.py — 健診總表寬表合併器(v19.408)。

user 要求:組合健診原本對同一批基金重複畫 3 張逐檔表(HWM σ / 風險對比 / 買賣點),
去重複合併進「健診總表」成一張大表。本模組提供純函式合併器(無 streamlit,可單元測試):
把 3 組 by-code 欄位 join 成 (欄序, code→欄值),現價等重複欄「先到先得」去重。

資料來源仍是各表的單一 data 函式(`risk.hwm_sigma_by_code` / `risk.risk_compare_by_code` /
`signals.mk_signal_by_code`)—— 不重算、不偽造(§1);缺值由來源填 '—'。
"""
from __future__ import annotations

# ── 「Sharpe 來源」欄的顯示值(SSOT;測試與呼叫端一律 import,不得抄字面值)──────
# 2026-08-10 user 拍板:這一欄印給使用者看,值本身必須是白話。原本印的是
# MoneyDJ 的網頁代號 + 英文期間縮寫,使用者無從得知那是「官方公布值」還是
# 「本站自己算的」—— 而這正是本欄存在的**唯一**理由(§2.2 血緣可辨識)。
#
# 三條規則:
#   1. 官方值一律以「MoneyDJ 官方」開頭,自算值一律以「自算」開頭 → 掃一眼就分得出來。
#   2. 期間資訊不可省(1 年 / 6 個月 / N 天),因為同一欄會混不同期間。
#   3. 六個月那條的重點是「**期間不是一年**」,警告記號與括號註明都不可拿掉 ——
#      拿掉就等於把跨檔比大小的陷阱藏起來。
SHARPE_SRC_OFFICIAL_1Y = "MoneyDJ 官方　1 年"
SHARPE_SRC_OFFICIAL_6M = "⚠️ MoneyDJ 官方　6 個月（非 1 年）"
SHARPE_SRC_SELF_CALC = "自算"          # 有樣本天數時 → f"{SHARPE_SRC_SELF_CALC}　{N} 天"
SHARPE_SRC_UNKNOWN = "⬜ —"


def sharpe_provenance_by_code(funds: list) -> dict:
    """{code: {"Sharpe 來源": 標籤}} —— 大表 `Sharpe 1Y` 欄的**實際**來源與期間(§2.2)。

    大表原本的欄位 help 硬寫「自計算(NAV序列);非MoneyDJ公布值」,但 `m["sharpe"]` 的
    優先序是 **wb07 一年 > wb07 六個月 > 本地自算**(`services/fund_service.py`
    `_sharpe_out`)—— 只要 MoneyDJ wb07 有值(境外基金常態),顯示的就是官方值,斷言與事實
    完全相反;wb07 **六個月**命中時欄名還寫死「1Y」。

    值取自 `calc_metrics` 已經算好的 `metrics.risk_metric_meta.sharpe`(不重算、不推測),
    fund dict 由 `_build_fund_dict` 包裝 → `metrics` 即 calc_metrics 產物。
    缺 meta(舊 cache / 抓取失敗)→ `⬜ —`,**不猜**(§1)。

    顯示值走本模組頂部四個常數(SSOT)——「官方」與「自算」以開頭字樣區分,期間寫在後面。

    ⚠️ 同一欄可能混三種期間(官方一年 / 官方六個月 / 本地 N 天),跨檔比大小前必須看本欄;
    換標策略分的 Sharpe tier 目前**未**依期間分層(§4.1 期間錯配殘留風險,見報告提案)。
    """
    out: dict = {}
    for _f in (funds or []):
        _code = str((_f or {}).get("code") or "").strip()
        if not _code:
            continue
        _mt = (((_f.get("metrics") or {}).get("risk_metric_meta") or {}).get("sharpe") or {})
        _src = _mt.get("source")
        if _src == "wb07_1y":
            _lbl = SHARPE_SRC_OFFICIAL_1Y
        elif _src == "wb07_6m":
            _lbl = SHARPE_SRC_OFFICIAL_6M
        elif _src == "self_calc":
            _d = _mt.get("period_days")
            _lbl = (f"{SHARPE_SRC_SELF_CALC}　{_d} 天" if isinstance(_d, int)
                    else SHARPE_SRC_SELF_CALC)
        else:
            _lbl = SHARPE_SRC_UNKNOWN
        out[_code] = {"Sharpe 來源": _lbl}
    return out


_RECONCILE_KEYS = ("sharpe_reconcile", "ret_1y_reconcile", "div_yield_reconcile")


def reconcile_by_code(funds: list) -> dict:
    """{code: {"對帳": worst-of-3 標籤}} —— Sharpe / 1Y報酬 / 配息率 三組雙演算法對帳的最差態。

    §4.3:個基深掘頁(單一基金)有逐項 agree/disagree chip,但批次 / 健檢 / 帳本大表原本沒有 →
    400 檔換標決策拿的是**未經「自算 vs MoneyDJ 官方值」交叉驗證**的單一數字。本欄接出
    `calc_metrics` / `finalize_fund_metrics` **已算好**的三組 reconcile(`metrics.sharpe_reconcile`
    / `ret_1y_reconcile` / `div_yield_reconcile`,§1 不重算、不新抓),取最差態當決策面旗標:
      - 任一組 `disagree` → **⚠️ 有矛盾**(自算與官方差距大;跳個基深掘頁看逐項)
      - 無矛盾且至少一組 `agree` → **✅ 一致**(全部可對且相符)/ **✅ 部分**(其餘單源無對照)
      - 三組皆無法對帳(單源 / 缺值:a_missing / b_missing / both_missing)→ **⬜ 單源**
      - 完全無 metrics(舊 cache / 抓取失敗)→ **⬜ —**(不猜,§1)
    """
    out: dict = {}
    for _f in (funds or []):
        _code = str((_f or {}).get("code") or "").strip()
        if not _code:
            continue
        _m = (_f.get("metrics") or {})
        _states = [(_m.get(_k) or {}).get("status")
                   for _k in _RECONCILE_KEYS if isinstance(_m.get(_k), dict)]
        _states = [s for s in _states if s]
        if not _states:
            _lbl = "⬜ —"
        elif "disagree" in _states:
            _lbl = "⚠️ 有矛盾"
        elif "agree" in _states:
            _lbl = "✅ 一致" if all(s == "agree" for s in _states) else "✅ 部分"
        else:
            _lbl = "⬜ 單源"
        out[_code] = {"對帳": _lbl}
    return out


def build_merged_extra_columns(funds: list, phase: str = "", score=None) -> tuple:
    """回傳 (col_order, combined)。

    - col_order:list[str],新欄依 HWM σ → 風險 → 出現順序、去重後的欄名。
    - combined:dict[code -> {欄名: 值}],同名欄「先到先得」(如「現價」HWM 版優先,版略過)。

    phase/score 給 訊號用(由呼叫端從 session_state.phase_info 取);缺則 訊號欄 '—'。
    """
    from ui.helpers.fund_grp_health.capture import capture_by_code
    from ui.helpers.fund_grp_health.quality import quality_score_by_code
    from ui.helpers.fund_grp_health.risk import hwm_sigma_by_code, risk_compare_by_code
    from ui.helpers.fund_grp_health.signals import mk_signal_by_code

    # v19.496:capture 算一次,同時餵「捕捉率欄」與「相對品質分」的操盤因子(不重算、不重抓基準)
    _capture = capture_by_code(funds)
    maps = [
        hwm_sigma_by_code(funds),
        risk_compare_by_code(funds),
        mk_signal_by_code(funds, phase, score),
        _capture,                    # v19.414 上/下檔捕捉率 + 操盤評分;v19.420 + vs 大盤%(同一基準)
        sharpe_provenance_by_code(funds),   # Sharpe 實際來源/期間(§2.2;大表原本硬說「非官方值」)
        reconcile_by_code(funds),    # v19.492 §4.3 雙演算法對帳旗標(worst-of-3;決策面缺口補上)
        quality_score_by_code(funds, capture_map=_capture),  # v19.496 A1 同類相對品質分(6因子+MoneyDJ大母體錨定)
    ]
    combined: dict = {}
    col_order: list[str] = []
    for _m in maps:
        for _code, _cols in _m.items():
            slot = combined.setdefault(_code, {})
            for _k, _v in _cols.items():
                if _k not in slot:          # 先到先得 → 重複欄(現價)去重
                    slot[_k] = _v
        for _cols in _m.values():
            for _k in _cols:
                if _k not in col_order:
                    col_order.append(_k)

    # v19.421 —「基期」標籤欄:由 σ rank 分高/中/低(reuse rotation.classify_base),
    # 讓 user 一眼看出高基期(貼近高點)/ 低基期(跌深)標的,不必自己讀 σ 數字。
    from services.rotation import classify_base
    from shared.signal_thresholds import ROTATION_BUY_SIGMA, ROTATION_SELL_SIGMA
    _BASE_LBL = {"high": "🔴 高基期", "low": "🟢 低基期", "mid": "⚪ 中性", "unknown": "⬜ 資料不足"}
    for _slot in combined.values():
        _slot["基期"] = _BASE_LBL[
            classify_base(_slot.get("σ rank"), ROTATION_SELL_SIGMA, ROTATION_BUY_SIGMA)]
    if "基期" not in col_order:
        col_order.append("基期")
    return col_order, combined


# 合併大表(①②③ 去重複)欄序 + 各欄來源(SSOT)。v19.411。
# source:health(① 4D/6F/3-3-3)/ div(② 配息 official + 每月配息 + 換標的)/
#         extra(σ/HWM/買賣點,build_merged_extra_columns 產物)/ base(③ 健診總表本身)。
# 去重原則:同一指標只留一份 —— Sharpe/Sortino/Calmar/Alpha 用 ①(extra 版略);
# 吃本金/ 3-3-3 用 ③(base;②①的同義欄略);現價由 extra 提供。
_UNIFIED_FRONT: list = [
    # ① 分類 + 評分
    ("基金類別", "health"), ("核心/衛星", "health"), ("分類依據", "health"),
    # 稽核 F12(2026-08-14):刻意排在 4D Grade **之前** —— 它是右邊整排數字的
    # 可信度前提。一檔只抓到 30 筆淨值的基金,Sharpe/σ/MaxDD/3Y 5Y 會整批留白,
    # 4D Score 卻照樣給分;沒有這一欄,那列在大表裡與正常基金完全同形。
    ("淨值樣本", "health"),
    # Layer 3-C(2026-08-14):同樣排在等第**之前** —— 它是那個字母的可信度前提。
    ("評分覆蓋", "health"),
    ("4D Grade", "health"), ("4D Score", "health"),
    ("相對品質分", "extra"),   # v19.496 A1 同類相對品質分(6因子 rank + MoneyDJ大母體錨定;peer-relative)
    # ① 報酬 / 風險 6 進階指標
    ("Sharpe 1Y", "health"), ("Sharpe 來源", "extra"),   # 來源/期間揭露(§2.2;緊貼數值欄)
    ("Sortino", "health"), ("Calmar", "health"),
    ("Alpha %", "health"), ("費用率 %", "health"), ("Max DD %", "health"),
    ("3Y 年化 %", "health"), ("5Y 年化 %", "health"),
    # ② 配息 official(wb01/wb05)+ 每月配息
    ("1Y 含息 %", "div"), ("1Y 來源", "div"), ("年化配息率 %", "div"),
    ("每月配息 (TWD)", "div"), ("每月配息單位數", "div"), ("配息來源", "div"),
    # 判定(吃本金/換標的/3-3-3/對帳)
    ("吃本金燈號 (1Y · )", "base"), ("換標的建議", "div"), (" 3-3-3 篩", "base"),
    ("對帳", "extra"),   # v19.492 雙演算法對帳旗標(worst-of-3;⚠️ 命中跳個基頁看逐項)
    # σ 位階 / 買賣點(extra;Sharpe/Sortino/Calmar/Alpha 已由 ① 提供故此處不重列)
    ("現價", "extra"), ("HWM", "extra"), ("距 HWM %", "extra"), ("σ rank", "extra"),
    ("基期", "extra"),   # v19.421 高/中/低基期標籤(由 σ rank 分類,一眼可讀)
    ("HWM 位階", "extra"), ("σ (年化%)", "extra"), ("Beta", "extra"),
    # 經理人操作能力(v19.414;上/下檔捕捉率 vs 大盤 + 操盤評分)+ vs 大盤%(v19.420)
    # 「捕捉樣本」/「vs 大盤期間」= 產生端算好但一直沒接出去的兩個可信度旗標
    # (`capture_ratio.low_confidence` / `benchmark_compare.full_period`),
    # 緊貼各自的數值欄,讓「3 個跌月的 92 分」與「40 個跌月的 92 分」在表上分得出來(§1)。
    ("上檔捕捉%", "extra"), ("下檔捕捉%", "extra"), ("操盤評分", "extra"),
    ("捕捉樣本", "extra"),
    ("vs 大盤%", "extra"), ("vs 大盤期間", "extra"),
    ("策略燈號", "extra"), ("換標策略分", "extra"),   # v19.423 換標決策(post-merge 覆寫)
    ("策略分覆蓋", "extra"),   # 策略分分母覆蓋率旗標(§1 第 3 項;post-merge 覆寫)
    ("景氣適配", "extra"), ("適配傾向", "extra"),      # v19.425 景氣位階適配(post-merge 覆寫)
    ("匯率位階", "extra"), ("淨值×匯率", "extra"),     # v19.426 淨值×匯率二維買賣切換(post-merge 覆寫)
    ("資產屬性", "extra"), ("操作訊號", "extra"),
    ("買 3 (深跌)", "extra"), ("買 1 (小跌)", "extra"),
    ("賣 1 (小漲)", "extra"), ("賣 3 (大漲)", "extra"), ("現價位階", "extra"),
]


def _unified_columns(base_cols: list) -> tuple:
    """依 base 欄名算出 (最終欄序, 各欄來源) —— build_unified_health_df / build_unified_row 共用。"""
    front_names = {c for c, _ in _UNIFIED_FRONT}
    # 排除 code/基金名(前置)+ ok(process_one_fund 內部旗標,恆 True 不必顯示)
    remaining_base = [c for c in base_cols
                      if c not in ("code", "基金名", "ok") and c not in front_names]
    columns = ["code", "基金名"] + [c for c, _ in _UNIFIED_FRONT] + remaining_base
    col_source = {"code": "base", "基金名": "base"}
    for c, s in _UNIFIED_FRONT:
        col_source[c] = s
    for c in remaining_base:
        col_source[c] = "base"
    return columns, col_source


def build_unified_row(base_row: dict, health_row: dict, div_row: dict, extra_row: dict) -> dict:
    """單檔版 build_unified_health_df:①②③+extra 併成一列 flat dict(去 base 底線私有欄)。"""
    base = {k: v for k, v in (base_row or {}).items() if not str(k).startswith("_")}
    columns, col_source = _unified_columns(list(base.keys()))
    src = {"base": base, "health": health_row or {}, "div": div_row or {}, "extra": extra_row or {}}
    return {col: src[col_source[col]].get(col) for col in columns}


def compute_switch_columns(row: dict) -> dict:
    """由已合併/攤平的 row 推導換標策略欄(cross-source:含息 div + Sharpe/MaxDD health +
    vs大盤 extra + 吃本金 base)→ {換標策略分, 策略燈號, 策略分覆蓋}。v19.423。

    兩條大表 build 路徑共用(健診 build_unified_health_df + 批次 build_batch_unified_row)。

    **覆蓋率側車必須全程帶著**(§1 第 3 項):`coverage_out` 一路吃到
    (a) `switch_signal(coverage=)` —— 部分覆蓋不得跨綠燈門檻換到「加碼」建議;
    (b) 「策略分覆蓋」欄 —— 讓 user 一眼看見分母被收斂成幾分、哪幾維沒證據。
    前一輪只做了 (0):側車存在但**全站 0 consumer**,等於沒揭露。
    """
    from services.switch_strategy import switch_coverage_label, switch_score, switch_signal

    _tr = row.get("1Y 含息 %")
    _sh = row.get("Sharpe 1Y")
    _dd = row.get("Max DD %")
    _vm = row.get("vs 大盤%")
    _eat = row.get("吃本金燈號 (1Y · )")
    _cov: dict = {}
    _sc = switch_score(_tr, _sh, _dd, _vm, coverage_out=_cov)
    return {"換標策略分": _sc,
            "策略燈號": switch_signal(_tr, _sh, _eat, _sc, coverage=_cov),
            "策略分覆蓋": switch_coverage_label(_cov, _sc)}


def compute_regime_fit_column(row: dict, current_regime) -> dict:
    """由 row(基金類別/核心衛星/上下檔捕捉)+ 當前景氣 → {景氣適配, 適配傾向}。v19.425。

    景氣適配 = ✅順風/⚠️逆風/⚪全景氣/⬜無法判定;適配傾向 = best_fit 景氣(全景氣/—)。
    景氣為 calc_macro_phase 的 phase(衰退/復甦/擴張/高峰,已 cache 於 phase_info)。
    """
    from services.regime_fit import tag_regime_fit

    _t = tag_regime_fit(row.get("基金類別"), row.get("核心/衛星"),
                        row.get("上檔捕捉%"), row.get("下檔捕捉%"), current_regime)
    _best = _t["best_fit_regimes"]
    _tend = "全景氣" if _best == ["ALL"] else ("、".join(_best) if _best else "—")
    return {"景氣適配": _t["fit_vs_current"], "適配傾向": _tend}


def compute_nav_fx_column(row: dict, fx_map: dict) -> dict:
    """由 row(ccy base + σ rank extra)+ 匯率位階 map → {匯率位階, 淨值×匯率}。v19.426。

    外幣基金:淨值位階(classify_base)× 匯率位階(z-score)→ 2D 進出場訊號。
    台幣計價 → ➖;非 USD / FX 缺料 / 缺基期 → ⬜(§1 不臆測)。
    """
    from services.currency import normalize_ccy
    from services.nav_fx_switch import nav_fx_signal
    from services.rotation import classify_base
    from shared.signal_thresholds import ROTATION_BUY_SIGMA, ROTATION_SELL_SIGMA

    _ccy = normalize_ccy(row.get("ccy"), default="")
    if _ccy == "TWD":
        return {"匯率位階": "➖ 台幣計價", "淨值×匯率": "➖ 台幣計價"}
    _fx = (fx_map or {}).get(_ccy)
    if not _fx or _fx.get("regime") is None:
        return {"匯率位階": "⬜ 無法判定", "淨值×匯率": "⬜ 無法判定"}
    _lbl = {"strong_twd": "台幣強", "neutral": "中性", "weak_twd": "台幣弱"}[_fx["regime"]]
    if not _fx.get("robust"):
        _lbl += "*"                                    # 樣本較短 → 參考(表註明)
    _nav = classify_base(row.get("σ rank"), ROTATION_SELL_SIGMA, ROTATION_BUY_SIGMA)
    return {"匯率位階": _lbl, "淨值×匯率": nav_fx_signal(_nav, _fx["regime"])["signal"]}


def build_unified_health_df(base_df, health_by_code: dict, div_by_code: dict,
                            extra_by_code: dict, current_regime=None):
    """把 ①②③ + σ/風險/依 code join 成一張去重複寬表(§1:缺欄留 None)。

    - base_df:③ 健診總表 DataFrame(含 code 欄 + 全期實際/年化 self-calc + 持有 meta)。
    - health_by_code / div_by_code / extra_by_code:①/②/σ風險的 {code: {欄:值}}。

    欄序:code, 基金名 → _UNIFIED_FRONT(①②+extra 去重)→ 其餘 base ③ 欄(持有 meta,末端)。
    回傳新 DataFrame(欄固定、依 base_df 的 code 順序)。
    """
    import pandas as pd

    base_by_code: dict = {}
    codes: list = []
    _cols = list(getattr(base_df, "columns", []))
    if "code" in _cols:
        for _rec in base_df.to_dict("records"):
            _c = str(_rec.get("code"))
            base_by_code[_c] = _rec
            codes.append(_c)

    _src = {"health": health_by_code or {}, "div": div_by_code or {},
            "extra": extra_by_code or {}, "base": base_by_code}

    # 來源整組沒供資料(如 Tab3 持倉健診不傳 extra)→ 該組欄整批不出現,避免一排空白欄
    # 讓使用者誤以為「資料壞了」(對抗式驗證發現的 UX 回歸)。
    _front = [(c, s) for c, s in _UNIFIED_FRONT if _src.get(s)]
    front_names = {c for c, _ in _front}
    remaining_base = [c for c in _cols if c not in ("code", "基金名") and c not in front_names]

    columns = ["code", "基金名"] + [c for c, _ in _front] + remaining_base
    col_source = {"code": "base", "基金名": "base"}
    for c, s in _front:
        col_source[c] = s
    for c in remaining_base:
        col_source[c] = "base"

    out = [
        {col: _src[col_source[col]].get(_c, {}).get(col) for col in columns}
        for _c in codes
    ]
    df = pd.DataFrame(out, columns=columns)
    # ①② 數值欄來自 dict → object dtype(None 會顯示字面「None」);顯式轉 numeric →
    # NumberColumn format 後 None/NaN 顯示空白(對齊原 ①② 表 v19.191 to_numeric 處理)。
    for _c in _UNIFIED_NUMERIC:
        if _c in df.columns:
            df[_c] = pd.to_numeric(df[_c], errors="coerce")

    # v19.423 — 換標策略欄(cross-source,須 numeric coerce 後才拿得到乾淨 Sharpe/MaxDD/vs大盤)
    if not df.empty:
        _recs = df.to_dict("records")
        _sw = [compute_switch_columns(_rec) for _rec in _recs]
        df["換標策略分"] = [x["換標策略分"] for x in _sw]
        df["策略燈號"] = [x["策略燈號"] for x in _sw]
        # 分母覆蓋率旗標(§1):Tab3 持倉健診不供 vs 大盤% → 整批部分覆蓋,此欄必須跟著出現
        df["策略分覆蓋"] = [x["策略分覆蓋"] for x in _sw]
        # v19.425 — 景氣適配欄(依資產屬性 + 捕捉 對照當前景氣)
        _rf = [compute_regime_fit_column(_rec, current_regime) for _rec in _recs]
        df["景氣適配"] = [x["景氣適配"] for x in _rf]
        df["適配傾向"] = [x["適配傾向"] for x in _rf]
        # v19.426 — 淨值×匯率二維買賣切換(fetch-once USDTWD;台幣計價 → ➖)
        from services.fx_regime_service import fx_regime_by_ccy
        _fxm = fx_regime_by_ccy()
        _nf = [compute_nav_fx_column(_rec, _fxm) for _rec in _recs]
        df["匯率位階"] = [x["匯率位階"] for x in _nf]
        df["淨值×匯率"] = [x["淨值×匯率"] for x in _nf]
    return df


# ①② 併入後需轉 numeric 的欄(extra σ/欄為預格式化字串,保持字串不轉)
_UNIFIED_NUMERIC: list = [
    "4D Score", "Sharpe 1Y", "Sortino", "Calmar", "Alpha %", "費用率 %",
    "Max DD %", "3Y 年化 %", "5Y 年化 %",
    "1Y 含息 %", "年化配息率 %", "每月配息 (TWD)", "每月配息單位數",
    "上檔捕捉%", "下檔捕捉%", "操盤評分",   # v19.414 經理人操作能力
    "vs 大盤%",                            # v19.420 近1Y純價格報酬差
    "換標策略分",                          # v19.423 換標策略分(策略燈號為文字不轉)
]


# ── 批次分析:每檔跑成一列「組合健診大表」flat row(JSON-safe → 可存 checkpoint)v19.413 ──
# process_one_fund 回傳的非底線 base 欄(供 failed 檔也對齊完整欄位)
_BATCH_BASE_KEYS: list = [
    "code", "基金名", "幣別偵測", "ccy", "fx_spot", "principal_ccy 🧮", "units 🧮",
    "配息次數", "累積 TWD 配息 🧮", "年均配息 TWD 🧮",
    "配息率% (全期實際)", "淨值% (全期實際)", "含息% (全期實際)",
    "配息率% (年化)", "淨值% (年化)", "含息% (年化)",
    "吃本金燈號 (1Y · )", " 3-3-3 篩", "倉位", "最高經理費%", "配息頻率", "換匯資訊 🧮",
]
# 批次寬表固定欄序:code, 基金名, 狀態, 備註, 淨值日期, 淨值新鮮度 → ①②extra(FRONT)→ base 末段
#
# 「淨值日期 / 淨值新鮮度」為批次表**專屬**(§4.6):Tab② 組合健診有
# `_render_mj_freshness_banner` 逐檔 chip 可看,400 檔的批次表不可能用 banner,
# 沒有這兩欄就分不出「週末沒開盤」與「2023 年就停售」—— 停售檔照樣算得出 σ rank /
# 操盤評分 / 策略燈號,在表裡與活躍基金完全同形。值由 `process_one_fund` 的
# `_nav_date` 私有欄推導(見 build_batch_unified_row),不進健診大表以免與 banner 重複。
_BATCH_FRESHNESS_COLUMNS: list = ["淨值日期", "淨值新鮮度"]
_batch_data_cols, _ = _unified_columns(_BATCH_BASE_KEYS)
BATCH_UNIFIED_COLUMNS: list = (
    ["code", "基金名", "狀態", "備註"]
    + _BATCH_FRESHNESS_COLUMNS
    + [c for c in _batch_data_cols if c not in ("code", "基金名")]
)
# 批次寬表需轉 numeric 的欄(供 UI NumberColumn;含批次獨有 fx_spot 等 base 數值)
BATCH_NUMERIC_COLUMNS: list = _UNIFIED_NUMERIC + [
    "fx_spot", "principal_ccy 🧮", "units 🧮", "配息次數",
    "累積 TWD 配息 🧮", "年均配息 TWD 🧮",
    "配息率% (全期實際)", "淨值% (全期實際)", "含息% (全期實際)",
    "配息率% (年化)", "淨值% (年化)", "含息% (年化)",
]


def _jsonify(v):
    """把值收成 JSON-safe primitive(numpy/Timestamp 漏網 → native;NaN/inf → None)。"""
    import datetime as _dt2
    import math as _m
    import numpy as _np
    import pandas as _pd
    if isinstance(v, _np.bool_):
        return bool(v)
    if isinstance(v, _np.integer):
        return int(v)
    if isinstance(v, (_np.floating, float)):
        f = float(v)
        return None if (_m.isnan(f) or _m.isinf(f)) else f
    if isinstance(v, (_pd.Timestamp, _dt2.datetime, _dt2.date)):
        try:
            return v.isoformat()
        except Exception:  # noqa: BLE001
            return str(v)
    return v


def build_batch_unified_row(code: str, principal_twd: float = 1_000_000.0,
                            phase: str = "", score=None, name_hint: str = "") -> dict:
    """批次:單檔 → 一列「組合健診大表」flat row(欄 = BATCH_UNIFIED_COLUMNS,JSON-safe)。

    走 process_one_fund(L2)+ ①`build_health_analysis_row` ②`build_dividend_summary_row`
    + σ/風險/`build_merged_extra_columns` → `build_unified_row`。
    §1 fail-loud:失敗回「狀態 != 成功」列(數值留 None,不填假值);整檔不外拋。

    name_hint:呼叫端已知的基金名(選股池 / 政策表)。線上解析不出真名時用它,
    連**失敗列**也帶名,而非顯示代號(v19.497 ALZF9)。
    """
    code = (code or "").strip().upper()
    _nh = (name_hint or "").strip()

    def _blank(status, note, name=None):
        r = {c: None for c in BATCH_UNIFIED_COLUMNS}
        r["code"] = code
        r["基金名"] = name or _nh or None      # 抓取失敗也優先顯示已知名,退 None(不填代號)
        r["狀態"] = status
        r["備註"] = note
        return r

    if not code:
        return _blank("⚠️ 無效代號", "空白代號")

    from services.fund_row import process_one_fund
    try:
        base = process_one_fund(code, principal_twd, name_hint=_nh)
    except Exception as e:  # noqa: BLE001 — 單檔炸掉收成失敗列
        return _blank("❌ 抓取失敗", f"{type(e).__name__}: {str(e)[:80]}")
    if not base.get("ok"):
        return _blank("❌ 抓取失敗", str(base.get("error", ""))[:100], name=base.get("基金名"))

    fd = base.get("_fund_raw") or {}
    import sys as _sys
    from services.health.report import build_dividend_summary_row, build_health_analysis_row
    # ── 稽核 A1（2026-08-14）：部分失敗不得標成「✅ 成功」──────────────────────
    # 下面三段各自 `except → 該組欄留空`，然後**無條件**寫 `狀態 = "✅ 成功"`。
    # 實際留白規模：① 失敗 = 13 欄、② 失敗 = 7 欄、③ 失敗 = 22 欄 + 7 欄降級 ⬜。
    # 400 列的表裡，那一列看起來與正常列**一模一樣**，使用者只會讀成
    # 「這檔沒有這些資料」，並據此做換標決策。唯一痕跡是 stderr，
    # 而 Streamlit Cloud 上使用者根本看不到。
    #
    # 對照組：健診 Tab 遇到同一個失敗會當場 `st.caption` 明講
    # 「σ 位階 / 風險 / 買賣點 … **整組計算失敗**，本次大表不含這些欄
    #   (不是資料沒有)」—— 同一個引擎，批次端把這句話拿掉了。
    #
    # 對策：收集失敗的欄組，改標「⚠️ 部分成功」並在備註列出缺哪幾組。
    _degraded: list[str] = []
    # Layer 3-C:健康度第 5 維(匯率風險)需要匯率序列。抓取是 I/O,L2 的
    # `build_health_analysis_row` 不能自己抓(§8.2),故由這裡把 L3 已經為
    # 「匯率位階」欄抓好的那一份(module cache,400 檔只抓一次)傳進去。
    # 抓失敗 → 傳 {} → 該維 missing → 「評分覆蓋」欄會誠實標 ⚠️(§1)。
    try:
        from services.fx_regime_service import fx_regime_by_ccy as _fxr_h
        _fx_map_h = _fxr_h() or {}
    except Exception as _e_fxh:  # noqa: BLE001
        _fx_map_h = {}
        print(f"[batch] {code} 匯率位階取得失敗(第 5 維留白): "
              f"{type(_e_fxh).__name__}: {_e_fxh}", file=_sys.stderr)
    try:
        _health = build_health_analysis_row(fd, code, fx_cv_by_ccy=_fx_map_h)
    except Exception as _e:  # noqa: BLE001 — ① 算不出 → 該組欄留空(§3.3 至少 log)
        _health = {}
        _degraded.append("① 健康分析(評分/報酬/風險)")
        print(f"[batch] {code} ① 健康分析失敗: {type(_e).__name__}: {_e}", file=_sys.stderr)
    try:
        _div = {k: v for k, v in build_dividend_summary_row(
                    fd, code, principal_twd=principal_twd, fx=base.get("fx_spot")).items()
                if not str(k).startswith("_")}
    except Exception as _e:  # noqa: BLE001
        _div = {}
        _degraded.append("② 配息相關(配息率/吃本金/換標建議)")
        print(f"[batch] {code} ② 配息相關失敗: {type(_e).__name__}: {_e}", file=_sys.stderr)
    try:
        from ui.helpers.fund_grp_health._utils import _build_fund_dict
        _, _extra_map = build_merged_extra_columns(
            [_build_fund_dict(fd, code, principal_twd, name_hint=_nh)], phase, score)
        _extra = _extra_map.get(code, {})
    except Exception as _e:  # noqa: BLE001
        _extra = {}
        _degraded.append("③ σ位階/風險/買賣點/捕捉率")
        print(f"[batch] {code} σ/風險/失敗: {type(_e).__name__}: {_e}", file=_sys.stderr)

    _row = build_unified_row(base, _health, _div, _extra)
    # ── 稽核 A1：post-merge 三組欄原本**不在任何 try 內** ──────────────────────
    # 一旦這裡拋例外，會一路穿透 `_run_batch` → `render_batch_analysis_tab`
    # → `app.py` 的 `with tab_batch:`（該 slot 沒有分頁隔離）→ **整個 App 從
    # 批次分頁往下全白**（個基深掘 / 配置帳本 / 我的管理室 / 參考診斷一起消失）。
    # 400 檔跑到一半炸掉更是把整輪計算結果一起帶走。
    try:
        # v19.423 — 換標策略欄(cross-source,由已組好的 _row 推導;與健診大表同一 compute)
        _row.update(compute_switch_columns(_row))
        # v19.425 — 景氣適配欄(phase 即當前景氣位階,批次已帶入)
        _row.update(compute_regime_fit_column(_row, phase))
        # v19.426 — 淨值×匯率二維切換(module cache 去重,400 檔只抓一次 USDTWD)
        from services.fx_regime_service import fx_regime_by_ccy
        _row.update(compute_nav_fx_column(_row, fx_regime_by_ccy()))
    except Exception as _e_post:  # noqa: BLE001
        _degraded.append("④ 策略燈號/景氣適配/匯率位階")
        print(f"[batch] {code} post-merge 欄組失敗: "
              f"{type(_e_post).__name__}: {_e_post}", file=_sys.stderr)
    # JSON-safe 收口:防 builder 偶發 numpy/Timestamp 漏進 → 讓 checkpoint json.dump 不炸
    # (否則整輪 20-30 分靜默降級只記憶體;還原舊 flat 路徑的 safe_num 保證)。
    out = {c: _jsonify(_row.get(c)) for c in BATCH_UNIFIED_COLUMNS}
    out["code"] = code
    # 稽核 A1：三態誠實化 —— 全成功 / 部分成功(附缺哪幾組) / 抓取失敗(上方早退)
    if _degraded:
        out["狀態"] = "⚠️ 部分成功"
        out["備註"] = ("以下欄組計算失敗、留白（**不是這檔沒有資料**）："
                       + "、".join(_degraded))
    else:
        out["狀態"] = "✅ 成功"
        out["備註"] = None
    # §4.6 —「這檔的 NAV 停在哪一天」。build_unified_row 會濾掉底線私有欄,
    # 故在此顯式從 base 取 `_nav_date` 補上(缺 → 誠實「⬜ 無淨值日期」,不猜)。
    from services.fund_row import nav_freshness_label
    _nav_d = str(base.get("_nav_date") or "").strip()
    out["淨值日期"] = _nav_d or None
    out["淨值新鮮度"] = nav_freshness_label(_nav_d)[0]
    return out
