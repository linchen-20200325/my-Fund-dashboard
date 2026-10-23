"""services/precision_service.py — 精準策略引擎 v4.0
（v11.0 C-15 從 precision_engine.py 搬入；v18.116 B-B 完成 I/O 拆分）

複合風險溫度計 (Composite Risk Thermometer)
+ 微觀防護盾 (Micro Defense Shield — 三率檢核)
+ HWM σ 絕對位階（calc_hwm_sigma_levels）
+ Risk Gauge HTML helper（純字串組合，無 streamlit 依賴）
適用於 2026 年 K 型分化行情。

v11.0 分層歸位：本檔屬於 Service Layer，業務計算 + view-helper（HTML 字串）。
v18.116 B-B：把 fetch_stock_three_ratios / _resolve_ticker / _TW/US_NAME_MAP
            搬到 repositories/financial_repository.py — 純 I/O 歸 repository 層。
            PrecisionStrategyEngine 方法保留為薄殼 proxy（向後相容）。
向後相容：根目錄 precision_engine.py 保留 shim re-export；既有 caller 零修改。
"""
import logging

import numpy as np
import pandas as pd
from shared.signal_thresholds import (  # v19.74 W2 SSOT
    RISK_SCORE_VIX_WEIGHT_RATIO,
    RISK_SCORE_HY_WEIGHT_RATIO,
    RISK_SCORE_YIELD_WEIGHT_RATIO,
)

from shared.colors import BG_DARK_GREEN_2, BG_DARK_RED_2, GH_BG_CARD, GH_BORDER, GRAY_55, GRAY_66, GRAY_CC, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, MD_DEEP_ORANGE_400, TRAFFIC_NEUTRAL

# v18.116 B-B: I/O 拆分後從 repository 取
from repositories.financial_repository import (  # noqa: F401  legacy re-export
    _TW_NAME_MAP,
    _US_NAME_MAP,
    fetch_stock_three_ratios as _repo_fetch_stock_three_ratios,
    resolve_ticker as _repo_resolve_ticker,
)

logger = logging.getLogger("PrecisionStrategyEngine")


class PrecisionStrategyEngine:
    """精準策略引擎：複合風險溫度計 + 微觀防護盾"""

    def __init__(self):
        self.logger = logging.getLogger("PrecisionStrategyEngine")

    # ── 1. 複合風險溫度計 ─────────────────────────────────────────────
    def calculate_composite_risk(self, df_macro: pd.DataFrame) -> float:
        """
        計算宏觀複合風險溫度計
        需傳入含 'VIX', 'HY_Spread', 'Yield_Curve_10Y_2Y' 的歷史 DataFrame（≥20 筆）

        Risk_Score = Z_VIX×0.3 + Z_HY×0.4 + Z_YC×0.3
        > 1.5 且快速攀升 → 強制提高現金/短債部位，衛星嚴格停利
        """
        if df_macro is None or df_macro.empty or len(df_macro) < 20:
            # v18.190：資料不足→回中性 0.0 是「預期降級」，UI 已另顯友善提示，
            # 故降為 debug 避免每次 rerun 在 Cloud log 刷 WARNING。
            self.logger.debug("宏觀數據筆數不足（實際 %d），返回中性值 0.0",
                              len(df_macro) if df_macro is not None else 0)
            return 0.0
        try:
            latest = df_macro.iloc[-1]
            means  = df_macro.mean()
            stds   = df_macro.std().replace(0, np.nan)   # 防分母為零

            z_vix   = (latest["VIX"]               - means["VIX"])               / stds["VIX"]
            z_hy    = (latest["HY_Spread"]          - means["HY_Spread"])          / stds["HY_Spread"]
            z_yield = (latest["Yield_Curve_10Y_2Y"] - means["Yield_Curve_10Y_2Y"]) / stds["Yield_Curve_10Y_2Y"]

            risk_score = float(z_vix * RISK_SCORE_VIX_WEIGHT_RATIO + z_hy * RISK_SCORE_HY_WEIGHT_RATIO + z_yield * RISK_SCORE_YIELD_WEIGHT_RATIO)
            return round(risk_score if not np.isnan(risk_score) else 0.0, 2)
        except KeyError as e:
            self.logger.error("缺少必要欄位: %s", e)
            return 0.0
        except Exception as e:
            self.logger.error("複合風險計算異常: %s", e)
            return 0.0

    def risk_score_strategy(self, risk_score: float) -> dict:
        """
        根據 Risk_Score 返回策略研判
        Returns: {level, color, icon, action, cash_pct}
        """
        if risk_score > 1.5:
            return {"level": "極高風險", "color": MATERIAL_RED, "icon": "🚨",
                    "action": "流動性危機前兆：核心現金/短債 ≥50%，衛星嚴格停利出場，不宜追高",
                    "cash_pct": 50}
        elif risk_score > 0.8:
            return {"level": "風險偏高", "color": MD_DEEP_ORANGE_400, "icon": "⚠️",
                    "action": "流動性收縮：核心配置防禦性資產，衛星部位縮減至 20% 以內",
                    "cash_pct": 30}
        elif risk_score > 0.0:
            return {"level": "中性偏高", "color": MATERIAL_ORANGE, "icon": "🔔",
                    "action": "市場情緒緊張但未惡化：維持現有配置，設好停利停損位",
                    "cash_pct": 15}
        elif risk_score > -0.5:
            return {"level": "中性偏低", "color": "#66bb6a", "icon": "✅",
                    "action": "風險可控：正常核心/衛星配置，可適度加碼成長部位",
                    "cash_pct": 10}
        else:
            return {"level": "風險極低", "color": "#42a5f5", "icon": "🚀",
                    "action": "流動性寬鬆：積極配置，股 60%+，左側布局高成長衛星",
                    "cash_pct": 5}

    def build_macro_df(self, indicators: dict) -> pd.DataFrame:
        """
        從 macro_engine indicators dict 組裝對齊的 VIX/HY_Spread/Yield_Curve DataFrame
        VIX 為週頻 → 重採樣為月頻後與 HY_SPREAD / YIELD_10Y2Y 對齊
        """
        try:
            vix_s = (indicators.get("VIX")        or {}).get("series")
            hy_s  = (indicators.get("HY_SPREAD")   or {}).get("series")
            yc_s  = (indicators.get("YIELD_10Y2Y") or {}).get("series")

            if any(s is None for s in [vix_s, hy_s, yc_s]):
                missing = [k for k, s in [("VIX", vix_s), ("HY_SPREAD", hy_s), ("YIELD_10Y2Y", yc_s)] if s is None]
                self.logger.warning("指標序列缺失: %s", missing)
                return pd.DataFrame()

            def _to_monthly(s, name: str) -> pd.Series:
                s = pd.Series(s).copy()
                s.index = pd.to_datetime(s.index, errors="coerce")
                s = s[s.index.notna()].dropna()
                # 判斷是否為週頻（平均間隔 < 20 天）
                if len(s) > 2:
                    avg_days = (s.index[-1] - s.index[0]).days / max(len(s) - 1, 1)
                    if avg_days < 20:
                        s = s.resample("MS").mean()
                s.name = name
                return s

            df = pd.concat([
                _to_monthly(vix_s, "VIX"),
                _to_monthly(hy_s,  "HY_Spread"),
                _to_monthly(yc_s,  "Yield_Curve_10Y_2Y"),
            ], axis=1).dropna()

            if len(df) < 20:
                # v18.190：資料不足→回空 df 由 UI 友善降級，降為 debug 避免 log 刷屏
                self.logger.debug("對齊後資料筆數不足 20（實際 %d）", len(df))
                return pd.DataFrame()
            return df
        except Exception as e:
            self.logger.error("build_macro_df 失敗: %s", e)
            return pd.DataFrame()

    # ── 2. 微觀防護盾 ────────────────────────────────────────────────
    def evaluate_fund_three_ratios(self, fund_holdings: list) -> str:
        """
        掃描基金前十大持倉三率（毛利率/營益率/淨利率）QoQ 動能
        fund_holdings: [{'stock': 'NVDA', 'gross_margin_diff': 1.2,
                          'op_margin_diff': 0.8, 'net_margin_diff': 1.0}, ...]
        """
        if not fund_holdings:
            return "無法解析持倉，跳過三率檢核"
        total_momentum, valid_stocks = 0.0, 0
        for stock_data in fund_holdings:
            gd = stock_data.get("gross_margin_diff")
            od = stock_data.get("op_margin_diff")
            nd = stock_data.get("net_margin_diff")
            # v19.398 §1:三率任一缺(margin 源缺,如金融股無毛利率行 → diff=None)→ 該股
            # 三率動能不可算,誠實跳過;不以捏造 0 充當「持平」灌水 valid_stocks / 拉平均值。
            if gd is None or od is None or nd is None:
                continue
            try:
                total_momentum += float(gd) + float(od) + float(nd)
                valid_stocks   += 1
            except (ValueError, TypeError):
                continue
        if valid_stocks == 0:
            return "⬜ 無持倉具備完整三率數據（如金融股缺毛利率行），無法檢核三率動能"
        avg = total_momentum / valid_stocks
        if avg > 2.0:
            return "🟢 核心持倉三率強勢雙升，具備實質基本面防護"
        elif avg < -2.0:
            return "🔴 核心持倉三率顯著衰退，警惕估值虛漲風險（價值陷阱）"
        else:
            return "🟡 核心持倉三率持平，需搭配技術面布林通道研判"

    def fetch_stock_three_ratios(self, holding_name: str) -> "dict | None":
        """v18.116 B-B: 薄殼 proxy → repositories/financial_repository.fetch_stock_three_ratios。

        為向後相容保留方法簽名；新 code 建議直接 import repo 函式：
            from repositories.financial_repository import fetch_stock_three_ratios

        F-PROV-1 註:provenance **由 upstream `repositories.financial_repository.fetch_stock_three_ratios`
        stamp 在 dict 內**(`source="yfinance:{ticker_sym}:quarterly_income_stmt"` +
        `fetched_at`,phase 18 v19.156)。本 method 純 return upstream dict 透傳,
        key 完整保留,不需 re-stamp 避免冗餘。
        """
        return _repo_fetch_stock_three_ratios(holding_name)

    def _resolve_ticker(self, name: str) -> "str | None":
        """v18.116 B-B: 薄殼 proxy → repositories/financial_repository.resolve_ticker。"""
        return _repo_resolve_ticker(name)


# σ 絕對金額視為 0 的下限(§3.3 不 inline magic):問的是「這條 NAV 到底有沒有動」。
# 2026-08-07 起這是全站唯一一份 —— `services/fund_screening.py` 原本有一份語意
# 對等的 `LOW_BASE_STD_EPS`(另一套低基期演算法),該套演算法已隨「低基期統一用
# HWM σ rank」拔除,那份常數同步刪除,不留無主的第二個門檻。
_SIGMA_ABS_EPS = 1e-12

# 2026-10-23 裁示 2C(BL-0426):下面兩個下限**原本就 inline 在 calc_hwm_sigma_levels 內**
# (`len(series) < 30` / `len(ret) < 20`),值一字未改,只具名化 —— 讓唯一 SSOT 入口
# `services/fund_position.compute_fund_position` 判 `history_short` 時讀同一份,
# 不在第二處再寫一次 30(§3.3)。**不是新門檻。**
HWM_MIN_POINTS = 30          # NAV 筆數下限(既有值)
HWM_MIN_RETURNS = 20         # 日報酬筆數下限(既有值)

# ── HWM 位置中性三態(2026-10-23 裁示 2C;BL-0426)────────────────────────────
# 三態判定**不自己比大小**:一律走 `services/rotation.classify_base`(high/mid/low)
# 再對映成中性用字,切點 = `shared/signal_thresholds.ROTATION_SELL_SIGMA`(−0.5)/
# `ROTATION_BUY_SIGMA`(−1.5)。⚠️ 這兩個切點是 legacy／研究候選門檻、**未校準**,
# **不是**正式投資門檻;HWM σ 只是「基金相對自身近一年高點的位置證據」,
# 不是任何交易訊號或交易建議 —— 下列用字因此刻意不帶任何行動語意。
HWM_POSITION_NEAR_HIGH = "near_high"
HWM_POSITION_MID = "mid"
HWM_POSITION_FAR_FROM_HIGH = "far_from_high"

_CLASSIFY_TO_POSITION = {
    "high": HWM_POSITION_NEAR_HIGH,
    "mid": HWM_POSITION_MID,
    "low": HWM_POSITION_FAR_FROM_HIGH,
}


def _fmt_sigma_cut(v: float) -> str:
    """切點顯示字串:−0.5(U+2212 減號,與畫面其他 σ 用字一致)。"""
    return f"{float(v):.1f}".replace("-", "−")


def hwm_position_labels() -> dict:
    """position → (label, color)。切點數字從 SSOT 常數讀,不在字串裡寫死。"""
    from shared.signal_thresholds import ROTATION_BUY_SIGMA, ROTATION_SELL_SIGMA
    _sell, _buy = _fmt_sigma_cut(ROTATION_SELL_SIGMA), _fmt_sigma_cut(ROTATION_BUY_SIGMA)
    return {
        HWM_POSITION_NEAR_HIGH: (f"接近高點（≥ {_sell}σ）", MATERIAL_GREEN),
        HWM_POSITION_MID: (f"中段（{_buy}σ ～ {_sell}σ）", MATERIAL_ORANGE),
        HWM_POSITION_FAR_FROM_HIGH: (f"遠離高點（≤ {_buy}σ）", MATERIAL_RED),
    }


def hwm_position_from_rank(sigma_rank) -> "tuple[str | None, str | None, str | None]":
    """σ rank → (position, label, color)。無法分類 → (None, None, None)。

    唯一判定:`services.rotation.classify_base`(同切點、同比較方向),本函式只做用字對映。
    """
    from services.rotation import classify_base
    from shared.signal_thresholds import ROTATION_BUY_SIGMA, ROTATION_SELL_SIGMA
    _pos = _CLASSIFY_TO_POSITION.get(
        classify_base(sigma_rank, ROTATION_SELL_SIGMA, ROTATION_BUY_SIGMA))
    if _pos is None:
        return None, None, None
    _label, _color = hwm_position_labels()[_pos]
    return _pos, _label, _color


def calc_hwm_sigma_levels(series: "pd.Series", lookback: int = 252) -> dict:
    """
    T5: HWM 基準 σ 絕對位階(純數學核心)
    HWM = 過去 lookback 天歷史最高淨值
    σ   = 過去 lookback 天每日報酬率標準差 × sqrt(lookback) 換算為絕對金額

    ⚠️ 2026-10-23 裁示 2C(BL-0426):**production 一律經
    `services/fund_position.compute_fund_position` 餵配息還原(Total Return)序列**,
    不得在 ui/ 或其他 services 直接拿原始 NAV 呼叫本函式(守衛:
    `tests/test_ssot_2c_fund_position.py`)。本函式的數學一字未改。

    Returns:
      hwm, sigma_abs, current_nav, level_1s, level_2s, level_3s,
      dist_to_hwm_pct, sigma_rank (float, 正=在HWM上方 N個σ，負=下方),
      position ("near_high" / "mid" / "far_from_high"), label, color

    label 為中性三態「接近高點／中段／遠離高點」(2C;原四級 label 已退役),
    切點 −0.5 / −1.5 是 legacy／研究候選門檻、未校準,非正式投資門檻。

    或 `{"error": str}` —— 資料不足 / 報酬率序列不足 / **σ≈0(NAV 完全不動)**。
    呼叫端一律先檢查 `"error" in result` 再取值(全站既有慣例)。
    """
    import numpy as _np
    if series is None or len(series) < HWM_MIN_POINTS:
        return {"error": "資料不足"}
    try:
        s   = series.dropna().tail(lookback)
        nav = float(s.iloc[-1])
        hwm = float(s.max())
        ret = s.pct_change(fill_method=None).dropna()  # §1 不補值
        if len(ret) < HWM_MIN_RETURNS:
            return {"error": "報酬率序列不足"}
        daily_std = float(ret.std())
        # v19.482 稽核 H5:原本 `sqrt(len(s))` —— len(s)=min(序列長, lookback),短歷史檔
        # (如 40 筆)只乘 sqrt(40)≈6.3 而非 sqrt(252)≈15.9,σ_abs 縮小 ~2.5×,
        # sigma_rank=(nav-hwm)/σ_abs 被誇大成更負 → 同樣跌幅在短檔被判「更低基期=可買」,
        # 且 rotation 依 sigma_rank 由負到正排序 → **系統性把建議導向最不可信的短歷史檔**。
        # docstring/comment 本就寫「× sqrt(lookback)」→ 改回固定 lookback,讓跨檔 σ 單位一致。
        sigma_abs = hwm * daily_std * _np.sqrt(lookback)  # 固定 lookback 期間 σ(跨檔可比)

        # §1 / §4.6:σ ≈ 0 只可能是「NAV 完全不動」(停售 / 清算 / 剛成立填平值)。
        # 此時 (nav-hwm)/σ 未定義 —— 舊版回 0.0,而 0.0 ≥ -0.5 會一路被
        # `services/rotation.py::classify_base` 判成 "high"(🔴 高基期、偏貴)並列進
        # 輪動配對的「賣出」候選,同一頁的 label 卻寫綠字「接近 HWM」。
        # 改為誠實回 error(既有契約,全站 caller 都已有 `"error" in r` 分支),
        # 對齊 `services/allocation_backtest.py::_sigma_rank_at`(σ_abs≤0 → None)。
        # ⚠️ 這條 error 同時是「🎯 選基金」篩選器的停售基金防線:
        # `services/fund_screening.compute_base_state` 收到 error 就回 base="unknown",
        # `screen_funds(only_low_base=True)` 據此濾掉 —— 停售基金永遠不會被推薦進場。
        if sigma_abs <= _SIGMA_ABS_EPS:
            return {"error": "NAV 無波動(σ≈0),無法定位階"}

        level_1s = round(hwm - 1 * sigma_abs, 4)
        level_2s = round(hwm - 2 * sigma_abs, 4)
        level_3s = round(hwm - 3 * sigma_abs, 4)

        sigma_rank = (nav - hwm) / sigma_abs
        dist_pct   = (nav - hwm) / hwm * 100 if hwm > 0 else 0.0

        _sigma_rank_r = round(sigma_rank, 3)
        # 2C:~~四級 label(接近 HWM / −1σ 區 / −2σ 區 / −3σ+ 區)~~ → 中性三態,
        # 經 classify_base(同切點)判定;舊四級帶行動語意,已退役(有意識的更正)。
        position, label, color = hwm_position_from_rank(_sigma_rank_r)
        if position is None:      # 理論上不發生(σ rank 已是有限數);誠實回 error 不猜
            return {"error": "σ rank 無法分類"}

        return {
            "hwm":            round(hwm,         4),
            "sigma_abs":      round(sigma_abs,   4),
            "current_nav":    round(nav,          4),
            "level_1s":       level_1s,
            "level_2s":       level_2s,
            "level_3s":       level_3s,
            "sigma_rank":     _sigma_rank_r,
            "dist_to_hwm_pct":round(dist_pct,    2),
            "position":       position,
            "label":          label,
            "color":          color,
        }
    except Exception as e:
        return {"error": str(e)[:60]}


# ── 模組層工具函式（供 app.py 直接呼叫）────────────────────────────


def three_ratio_row_html(r: dict) -> str:
    """
    返回單一持倉三率檢核列的 HTML 字串
    r = fetch_stock_three_ratios 的回傳值
    """
    def _fmt(v):
        return f"{v:+.1f}%" if isinstance(v, (int, float)) else "N/A"

    def _color(v):
        if not isinstance(v, (int, float)):
            return TRAFFIC_NEUTRAL
        return MATERIAL_GREEN if v > 0.5 else (MATERIAL_RED if v < -0.5 else MATERIAL_ORANGE)

    gd = r.get("gross_margin_diff", 0)
    od = r.get("op_margin_diff",    0)
    nd = r.get("net_margin_diff",   0)
    momentum = (gd or 0) + (od or 0) + (nd or 0)
    bg = BG_DARK_GREEN_2 if momentum > 2 else (BG_DARK_RED_2 if momentum < -2 else GH_BG_CARD)
    border = MATERIAL_GREEN if momentum > 2 else (MATERIAL_RED if momentum < -2 else GH_BORDER)

    return (
        f"<div style='background:{bg};border:1px solid {border};border-radius:8px;"
        f"padding:8px 12px;margin:4px 0;display:flex;align-items:center;gap:12px;flex-wrap:wrap'>"
        f"<div style='flex:1.5;font-size:11px;color:{GRAY_CC}'>{r.get('stock','')[:20]}"
        f"<span style='color:{GRAY_55};margin-left:6px;font-size:10px'>{r.get('ticker','')}</span></div>"
        f"<div style='flex:1;font-size:10px;color:{GRAY_66}'>{r.get('q_old','')[-7:]}→{r.get('q_new','')[-7:]}</div>"
        f"<div style='text-align:center'>"
        f"<div style='color:{GRAY_66};font-size:9px'>毛利率</div>"
        f"<div style='color:{_color(gd)};font-weight:700;font-size:12px'>{_fmt(gd)}</div></div>"
        f"<div style='text-align:center'>"
        f"<div style='color:{GRAY_66};font-size:9px'>營益率</div>"
        f"<div style='color:{_color(od)};font-weight:700;font-size:12px'>{_fmt(od)}</div></div>"
        f"<div style='text-align:center'>"
        f"<div style='color:{GRAY_66};font-size:9px'>淨利率</div>"
        f"<div style='color:{_color(nd)};font-weight:700;font-size:12px'>{_fmt(nd)}</div></div>"
        f"</div>"
    )
