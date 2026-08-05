"""services/fund_row.py — 單檔健診 worker(v19.413 從 ui/tab_fund_grp_health 下沉 L2)。

`process_one_fund` 為「純 IO + 計算、無 st 呼叫」的每檔健診 worker,原放在 L3 UI
(`ui/tab_fund_grp_health.py`)但本質是 L2 業務邏輯。下沉至此讓「組合健診」與「批次分析」
共用同一引擎產出**同一張健診大表**(§8.2:純 worker 本就該在 L2)。

回傳 row dict:成功含 ③ 健診總表所有欄位(持有 meta / 全期實際·年化 % / 吃本金 / MK 3-3-3
+ `_fund_raw`/`_principal_twd`/`_detail` 等底線私有欄供上層算 ①②/σ);任一步失敗回
`{code, ok: False, error}`。§1:缺幣別 / NAV / FX 誠實回 error,不矇預設值。
"""
from __future__ import annotations


def process_one_fund(
    code: str,
    principal_twd: float,
    ccy_hint: str = "",
    warn_gap: float = 0.0,
    fd: dict | None = None,
) -> dict:
    """單檔健診 worker(純 IO + 計算,無 st 呼叫 → 可並行)。

    Args:
        code: 基金代號(MoneyDJ)
        principal_twd: 本金 TWD(健診 Tab / 批次統一 100 萬;Tab3 用各檔實際 invest_twd)
        ccy_hint: legacy hint(v19.59 後不再使用,留簽名相容)
        warn_gap: 配息率超出含息報酬率多少 → 警示燈
        fd: 預先抓好的 fd(`auto_fetch_moneydj` 結果);None → 本函式自行抓。

    回傳 row dict;任一步失敗回 {ok: False, error}。
    """
    from services.moneydj_fetcher import auto_fetch_moneydj
    from services.fund_service import get_latest_fx
    from services.currency import normalize_ccy  # v19.71:single source of truth
    from services.health.dividend_calc import compute_dividend_twd_series
    try:
        if fd is None:
            fd = auto_fetch_moneydj(code)
        _series = fd.get("series") if isinstance(fd, dict) else None
        _has_series = _series is not None and len(_series) > 0
        if fd.get("error") and not _has_series:
            return {"code": code, "ok": False, "error": fd.get("error", "?")}
        nav_s = _series
        divs = fd.get("dividends") or []
        # v19.71:MoneyDJ 對部分基金回傳中文「美元」而非 ISO「USD」→ normalize 正規化。
        ccy_auto = normalize_ccy(fd.get("currency"), default="")
        fund_name = fd.get("fund_name", "") or fd.get("full_key", "")
        if not _has_series:
            return {"code": code, "ok": False, "error": "NAV 抓不到"}
        nav_dict = {
            str(idx)[:10]: float(v)
            for idx, v in nav_s.items()
            if v == v  # NaN guard
        }
        # v19.59:移除人工 fallback。抓不到「計價幣別」→ 該檔直接 error,不矇 USD。
        ccy = ccy_auto
        if not ccy:
            return {"code": code, "ok": False,
                    "error": "幣別未知（MoneyDJ wb05 未提供「計價幣別」欄）"}
        # TWD 基金不打 FX API
        if ccy == "TWD":
            fx = 1.0
        else:
            fx = get_latest_fx(f"{ccy}TWD=X") or 0.0
            if fx <= 0:
                return {"code": code, "ok": False, "error": f"FX {ccy}TWD 抓不到"}
        result = compute_dividend_twd_series(
            nav_series=nav_dict,
            dividend_events=divs,
            fx_rate_default=fx,
            principal_twd=principal_twd,
            warn_gap_pct=warn_gap,
        )
        if not result.get("ok"):
            return {"code": code, "ok": False, "error": result.get("error", "?")}
        s = result["summary"]
        _mgmt_fee = (fd.get("mgmt_fee") or "").strip() or "—"
        # v19.176:配息頻率走 metrics.div_freq_n SSOT。
        _div_freq_n = (fd.get("metrics") or {}).get("div_freq_n")
        if _div_freq_n in (12, 4, 2, 1):
            _div_freq_label = {12: "月配息", 4: "季配息", 2: "半年配", 1: "年配"}[_div_freq_n]
            _div_freq = f"{_div_freq_label}({_div_freq_n} 次/年)"
        else:
            _div_freq = (fd.get("dividend_freq") or "").strip() or "—"
        _hold_yrs = max(float(s.get("holding_years_🧮") or 1), 0.01)
        _ann_twd_div = round(s["total_twd_div_🧮"] / _hold_yrs, 0)
        _p_ccy = result["principal_ccy_🧮"]
        _buy_fx = result["buy_fx"]
        _buy_fx_info = f"1M TWD→{_p_ccy:,.0f} {ccy} @ {_buy_fx:.2f}"

        # v19.148:MK 老師 1Y SSOT 吃本金檢查(跨表 verdict 一致)。
        _metrics = fd.get("metrics") or {}
        _mk_pos = (_metrics.get("pos_label") or "—").strip() or "—"
        _mk_safety = None
        _mk_safety_err = ""
        try:
            from services.health.dividend import check_eating_principal_1y_mk
            _mk_safety = check_eating_principal_1y_mk(fd)
        except Exception as _e_mk:  # noqa: BLE001
            # §1:原本靜默吞 → 吃本金燈號顯示「⚪ 資料不足」，把「算爆了」
            # 偽裝成「沒資料」。補 log + 讓 verdict 說出是計算失敗。
            _mk_safety = None
            _mk_safety_err = type(_e_mk).__name__
            print(f"[fund_row {code}] check_eating_principal_1y_mk 失敗："
                  f"{_mk_safety_err}: {_e_mk}")
        if _mk_safety is not None:
            _snap_health = _mk_safety.get("status", "⚪ 資料不足")
        elif _mk_safety_err:
            _snap_health = f"⚠️ 計算失敗({_mk_safety_err})"
        else:
            _snap_health = "⚪ 資料不足"

        # v19.153:MK 老師 3-3-3 原則(成立 ≥ 3 年 + 3 年平均年化 > 7% → 通過)。
        _333_emoji = "⬜"
        _333_msg = "資料不足"
        try:
            from services.health.dividend import check_333_principle
            import datetime as _dt333
            _yrs_inc = None
            _mj_raw_333 = fd.get("moneydj_raw") or fd
            _inc_meta = (fd.get("inception_date") or _mj_raw_333.get("inception_date") or "")
            if _inc_meta:
                try:
                    _inc_d = _dt333.date.fromisoformat(str(_inc_meta)[:10])
                    _yrs_inc = (_dt333.date.today() - _inc_d).days / 365.25
                except (ValueError, TypeError):
                    _yrs_inc = None
            if _yrs_inc is None:
                try:
                    _first_iso = sorted(nav_dict.keys())[0]
                    _first_d = _dt333.date.fromisoformat(str(_first_iso)[:10])
                    _yrs_inc = (_dt333.date.today() - _first_d).days / 365.25
                    if len(nav_dict) < 90 and _yrs_inc < 0.5:
                        _yrs_inc = None
                except (ValueError, IndexError, TypeError):
                    _yrs_inc = None
            _ann_3y = _metrics.get("ret_3y_ann")
            if _ann_3y is None:
                _ret_3y_cum = _metrics.get("ret_3y_cum") or _metrics.get("ret_3y")
                try:
                    if _ret_3y_cum is not None:
                        _cum = float(_ret_3y_cum) / 100.0
                        _ann_3y = ((1.0 + _cum) ** (1.0 / 3.0) - 1.0) * 100.0
                except (TypeError, ValueError):
                    _ann_3y = None
            if _ann_3y is None:
                _perf_333 = fd.get("perf") or _mj_raw_333.get("perf") or {}
                _perf_3y_cum = _perf_333.get("3Y")
                if _perf_3y_cum is not None:
                    try:
                        _c = float(_perf_3y_cum) / 100.0
                        _ann_3y = round(((1.0 + _c) ** (1.0 / 3.0) - 1.0) * 100.0, 2)
                    except (TypeError, ValueError):
                        _ann_3y = None
            _333_r = check_333_principle(_yrs_inc, _ann_3y)
            if _333_r.get("passed") is True:
                _333_emoji = "✅"
            elif _333_r.get("passed") is False:
                _333_emoji = "❌"
            _333_msg = _333_r.get("message", "")
        except Exception as _e_333:  # noqa: BLE001
            # §1 教科書案例:原本 `pass` → `_333_msg` 停在初始值「資料不足」，
            # 於是「計算炸了」被顯示成「這檔基金資料不夠」。錯誤不可偽裝成缺資料。
            _333_emoji = "⚠️"
            _333_msg = f"計算失敗({type(_e_333).__name__})"
            print(f"[fund_row {code}] MK 3-3-3 計算失敗："
                  f"{type(_e_333).__name__}: {_e_333}")
        _333_status = f"{_333_emoji} {_333_msg[:32]}" if _333_msg else _333_emoji

        return {
            "code": code,
            "ok": True,
            "基金名": fund_name[:24],
            "幣別偵測": "自動" if ccy_auto else "fallback",
            "ccy": ccy,
            "fx_spot": fx,
            "principal_ccy 🧮": result["principal_ccy_🧮"],
            "units 🧮": result["units_held_🧮"],
            "配息次數": result["n_events"],
            "累積 TWD 配息 🧮": s["total_twd_div_🧮"],
            "年均配息 TWD 🧮": _ann_twd_div,
            "配息率% (全期實際)": s["cum_div_rate_pct_🧮"],
            "淨值% (全期實際)": s["cum_nav_return_pct_🧮"],
            "含息% (全期實際)": s["cum_total_return_pct_🧮"],
            "配息率% (年化)": s["annual_div_rate_pct_🧮"],
            "淨值% (年化)": s["annual_nav_return_pct_🧮"],
            "含息% (年化)": s["ret_1y_total_pct_🧮"],
            "吃本金燈號 (1Y · MK)": _snap_health,
            "MK 3-3-3 篩": _333_status,
            "MK 倉位": _mk_pos,
            "最高經理費%": _mgmt_fee,
            "配息頻率": _div_freq,
            "換匯資訊 🧮": _buy_fx_info,
            "_detail": result,
            "_principal_twd": float(principal_twd or 0),
            "_fund_raw": fd,
            "_nav_date": str(fd.get("nav_date") or "")[:10],
            "_fetched_at": str(fd.get("_moneydj_fetched_at") or ""),
        }
    except Exception as e:  # noqa: BLE001
        return {"code": code, "ok": False, "error": f"{type(e).__name__}: {e}"}
