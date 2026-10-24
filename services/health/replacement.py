"""v19.181 services — 「是否建議換標的」 4 規則心型警結合 SSOT 入口(L2 純函式,zero-IO)。

依老師長線挑核心資產體檢方法論,定義 4 條 hard-trigger 規則:
  (a) 吃本金 1Y·且持有 ≥ 1 年
  (b) 4D Grade F(< 35 分,嚴重警示)
  (c) 3-3-3 未通過且持有 ≥ 3 年
  (d) Sharpe < 0 且 max_dd < -30%(極差雙條件)

Verdict 三色:
  - 任一 hard trigger 中  → 🔴 建議換(replace)
  - 1-2 觀察分(Grade D 等較弱訊號) → 🟡 觀察(observe)
  - ~~全部未中             → 🟢 保留(keep)~~
  - 4 條規則**都實際判得動**且全部未中 → 🟢 保留(keep)

DG-6(2026-10-24 客戶裁示 DEC-2026-10-24-12;有意識的政策變更,不是漏刪):
  - **分類未判定**(`services.zscore_engine.is_core_bucket(category) is None`:類別空白／無法對應／
    分類例外)→ ⬜「分類未判定」(verdict="unknown"、status="core_unknown"),**不給換／留結論**,
    覆蓋 replace / observe / keep;已評估的規則只當「證據」列出(公式與門檻未改)。
  - **判不動時不得 🟢 保留**:無觸發、無觀察分,但任一規則資料不足無法判定 → ⬜「無法判定」
    (verdict="unknown"、status="rules_incomplete")。「判得動」的定義是總管讀法(可被客戶推翻),
    見 docs/DECISIONS.md DEC-2026-10-24-12 實作說明。
  - 回傳 dict 新增 `status`:"ok"(正常 replace／observe／keep)/ "core_unknown" / "rules_incomplete" /
    "no_signal"(既有「所有關鍵指標都拿不到」的 ⬜ 資料不足)。

設計
----
- zero-IO 純函式,只接受已算好的 fd dict + holding_years,無 streamlit 依賴
- 所有規則門檻走 shared.signal_thresholds SSOT,禁止 inline magic
- caller 端負責:(1) 算 holding_years(2) 拿 fd_dict(含 metrics, moneydj_raw 等)

對外 API
========
- ``check_replacement_recommendation(fd, holding_years, _4d_result=None)`` 主入口
"""
from __future__ import annotations

from typing import Optional

from shared.signal_thresholds import (
    REPLACE_RULE_A_MIN_HOLD_YEARS,
    REPLACE_RULE_C_MIN_HOLD_YEARS,
    REPLACE_RULE_D_SHARPE_MAX,
    REPLACE_RULE_D_MAX_DD_MIN_PCT,
)

_VERDICT_EMOJI = {
    "replace": "🔴",
    "observe": "🟡",
    "keep": "🟢",
    "unknown": "⬜",
}

_VERDICT_LABEL = {
    "replace": "建議換",
    "observe": "觀察",
    "keep": "保留",
    "unknown": "資料不足",
}

# DG-6(DEC-2026-10-24-12):unknown 的細分標籤(依 status)。
_UNKNOWN_LABEL_BY_STATUS = {
    "core_unknown": "分類未判定",
    "rules_incomplete": "無法判定",
    "no_signal": "資料不足",
}


# v19.222 P1-1:_safe_float 收口至 shared/converters.py SSOT
from shared.converters import safe_float as _safe_float  # noqa: E402



def check_replacement_recommendation(
    fd: dict,
    holding_years: Optional[float] = None,
    _4d_result: Optional[dict] = None,
) -> dict:
    """換標的建議 SSOT 入口 —  4 規則心型警結合。

    Args:
        fd: 基金 dict(支援 Tab2/Tab3/健診 3 種 shape):
            - 平坦:`{metrics, moneydj_raw, series, perf_source, ...}`
            - 嵌套:`{moneydj_raw: {perf, metrics, ...}}`
        holding_years: user 持有年數(從 portfolio_funds.invest_date 或 NAV 序列首日推算)。
            None → rule (a)(c) 自動退 unknown(不下硬判定)。
        _4d_result: 預算好的 compute_4d_health() 結果(免重算)。None → 本函式呼叫。

    Returns:
        {
            "verdict": "replace" | "observe" | "keep" | "unknown",
            "emoji": str,
            "label": str,
            "triggered_rules": [str, ...],  # 中的 hard trigger 規則名
            "observe_signals": [str, ...],  # 較弱訊號(觀察分)
            "message": str,                  # 給 UI 顯示的人類可讀說明
            "status": str,                   # DG-6:"ok" / "core_unknown" / "rules_incomplete" / "no_signal"
        }
    """
    # 規則延遲 import 避免循環依賴
    from services.health.dividend import (
        check_333_principle,
        check_eating_principal_1y_mk,
        derive_ann_3y_for_333,
    )
    from services.health.grade import compute_4d_health
    from services.fund_total_return import compute_1y_total_return

    # ─── shape normalize:平坦 fd 自動 wrap(對齊 v19.178 SSOT 模式)──
    if "moneydj_raw" not in fd and "perf" in fd:
        fd = {
            "moneydj_raw": fd,
            "metrics": fd.get("metrics") or {},
            "series": fd.get("series"),
            "perf_source": fd.get("perf_source"),
        }
    m = fd.get("metrics") or {}
    # Detox(v19.487):`mj`(moneydj_raw)在 v19.485 PR-2 把 3Y 推導改走 derive_ann_3y_for_333
    # 後已無消費者 → 移除死變數(§3.3)。

    triggered: list = []
    observe: list = []

    # ─── 規則 (a) — 吃本金 1Y·且持有 ≥ 1 年 ───────────────
    holding_y = _safe_float(holding_years)
    rule_a_eligible = (holding_y is not None
                       and holding_y >= REPLACE_RULE_A_MIN_HOLD_YEARS)
    # v19.184 F-MED:silent except 加 stderr log(§3.3 反捏造)
    import sys as _sys
    _eat_err = False   # DG-6:區分「例外 → None(判不動)」與「非配息基金 → None(規則不適用)」
    try:
        eat_result = check_eating_principal_1y_mk(fd)
    except Exception as e:
        print(f'[fund_replacement_verdict] check_eating_principal_1y_mk fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        eat_result = None
        _eat_err = True
    eat_status = (eat_result or {}).get("status", "")
    if rule_a_eligible and "吃本金" in str(eat_status):
        triggered.append(f"(a) 持有 {holding_y:.1f} 年 + 吃本金 1Y·")
    elif eat_result and "吃本金" in str(eat_status):
        # 持有 < 1 年也吃本金 — 計觀察分(尚未到 hard trigger)
        observe.append("(a*) 持有 < 1 年但吃本金(短期 NAV 波動,先觀察)")

    # ─── 規則 (b) — 4D Grade F(嚴重警示)/ D 計觀察分 ─────────
    if _4d_result is None:
        try:
            tr1y, _ = compute_1y_total_return(fd)
            # 稽核 C4：原本撈的是 `annual_div_rate_pct` —— **這個 key 不存在**
            # （`check_eating_principal_1y_mk` 從來沒回傳過它）。後果是 adr 恆 None
            # → 4D 少一維「配息健康度」→ 本規則 (b) 用的 grade 與健診大表顯示的
            # grade 不同源，而且無 Sharpe 的檔會落到 `—`、規則 (b) 整條失效。
            # 源頭已於同批補回傳 `_adr_pct`（值），這裡改吃它。
            adr = (eat_result or {}).get("_adr_pct")
            _4d_result = compute_4d_health(
                tr1y_pct=tr1y,
                adr_pct=adr,
                sharpe=_safe_float(m.get("sharpe")),
                sigma_pct=_safe_float(m.get("std_1y")),
                ma_dir=None,
            )
        except Exception as e:
            print(f'[fund_replacement_verdict] compute_4d_health fail: '
                  f'{type(e).__name__}: {e}', file=_sys.stderr)
            _4d_result = None
    grade = (_4d_result or {}).get("grade")
    if grade == "F":
        triggered.append("(b) 4D Grade F(健康度嚴重不足)")
    elif grade == "D":
        observe.append("(b*) 4D Grade D(健康度偏弱)")

    # ─── 規則 (c) — 3-3-3 未通過且持有 ≥ 3 年 ────────────────
    rule_c_eligible = (holding_y is not None
                       and holding_y >= REPLACE_RULE_C_MIN_HOLD_YEARS)
    # v19.485 PR-2:3 年年化改走 SSOT `derive_ann_3y_for_333`(2026-10-23 裁示 3A 起唯一口徑 =
    #   配息還原淨值法 `metrics.ret_3y_ann_tr`;缺 → None → 3-3-3 ⬜ → 不觸發 (c)),與健診大表 /
    #   Tab2 的 3-3-3 verdict **同源** —— 否則同一檔在替換判定與健診表會得到不同 3-3-3 結果
    #   (§2.1 SSOT)。years 這裡用 **holding_y(持有年數)**,是規則 (c) 的既定語意(非成立年數)。
    _ret_3y_ann, _ = derive_ann_3y_for_333(fd, m)
    try:
        _333 = check_333_principle(holding_y, _ret_3y_ann)
    except Exception as e:
        print(f'[fund_replacement_verdict] check_333_principle fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        _333 = {}
    if rule_c_eligible and _333.get("passed") is False:
        triggered.append(f"(c) 持有 {holding_y:.1f} 年 + 3-3-3 未通過")
    # v19.181:不再為持有 < 3 年的「3-3-3 未過」開觀察分 —
    # 新基金本來就過不了 3-3-3(成立年數不足),非真警示;
    # 避免每檔新基金都跳 🟡 觀察。

    # ─── 規則 (d) — Sharpe < 0 且 max_dd < -30% ──────────────
    sharpe_v = _safe_float(m.get("sharpe"))
    max_dd_v = _safe_float(m.get("max_drawdown"))
    if (sharpe_v is not None and sharpe_v < REPLACE_RULE_D_SHARPE_MAX
            and max_dd_v is not None and max_dd_v < REPLACE_RULE_D_MAX_DD_MIN_PCT):
        triggered.append(
            f"(d) Sharpe {sharpe_v:.2f} < 0 且 max_dd {max_dd_v:.1f}% < "
            f"{REPLACE_RULE_D_MAX_DD_MIN_PCT}%"
        )
    elif sharpe_v is not None and sharpe_v < REPLACE_RULE_D_SHARPE_MAX:
        observe.append(f"(d*) Sharpe {sharpe_v:.2f} < 0(風險調整後無報酬)")

    # ─── 綜合 verdict ────────────────────────────────────────
    # unknown 判定:所有關鍵指標都拿不到時不下 verdict(避免假綠燈)
    # 2026-10-23 裁示 1B 稽核必修 1:吃本金的灰色 dict(`status="⬜ 資料未備／無法判定"`、
    # `alert_level="grey"`、`eating_principal=None`)**不是訊號** —— 它的意思是「判不動」,
    # 若把它那個非空的 status 字串當訊號,無其他指標的基金會被判成 🟢 保留(Missing → HOLD,§1)。
    _eat_signal = (isinstance(eat_result, dict)
                   and eat_result.get("alert_level") != "grey"
                   and eat_result.get("eating_principal") is not None)
    _has_any_signal = (
        _eat_signal or grade not in (None, "—")
        or sharpe_v is not None or max_dd_v is not None
        or _ret_3y_ann is not None
    )
    # ─── DG-6(DEC-2026-10-24-12)① 分類未判定 → 不給換／留結論 ─────────
    # 分類 SSOT:`services.zscore_engine.is_core_bucket`(三態;None = 未判定)。
    # 類別取法對齊 `services/health/report.py::build_health_analysis_row`。
    _mj_raw = fd.get("moneydj_raw")
    _category = ((_mj_raw.get("category") if isinstance(_mj_raw, dict) else None)
                 or fd.get("category"))
    try:
        from services.zscore_engine import is_core_bucket
        _core = is_core_bucket(_category)
    except Exception as e:  # noqa: BLE001 — 分類例外 → 未判定,不冒充可判定(§1)
        print(f'[fund_replacement_verdict] is_core_bucket fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        _core = None
    _core_unknown = _core is None

    # ─── DG-6 ② 判不動時不得 🟢 保留:逐條確認 4 規則是否「實際判得動」──────
    # 定義為總管讀法(可被客戶推翻,見 DECISIONS DEC-2026-10-24-12 實作說明);不改任何公式／門檻。
    _rule_evaluable = {
        # (a) 吃本金是真訊號,或持有期已知且未達門檻(hard rule (a) 不可能觸發),
        #     或非配息基金(`check_eating_principal_1y_mk` 依既有契約回 None、且非例外 →
        #     吃本金概念不適用,規則 (a) 確定不會觸發;實作組補充,見 DECISIONS 實作說明)
        "a": bool(_eat_signal
                  or (eat_result is None and not _eat_err)
                  or (holding_y is not None
                      and holding_y < REPLACE_RULE_A_MIN_HOLD_YEARS)),
        # (b) 4D Grade 有實際等第
        "b": grade not in (None, "—"),
        # (c) 持有期已知,且(未達門檻 或 3-3-3 有通過／未通過結論)
        "c": bool(holding_y is not None
                  and (holding_y < REPLACE_RULE_C_MIN_HOLD_YEARS
                       or _333.get("passed") is not None)),
        # (d) Sharpe 已知,且(Sharpe 不為負 或 max_dd 已知)
        "d": bool(sharpe_v is not None
                  and (sharpe_v >= REPLACE_RULE_D_SHARPE_MAX or max_dd_v is not None)),
    }
    _not_evaluable = [k for k in ("a", "b", "c", "d") if not _rule_evaluable[k]]

    status = "ok"
    if _core_unknown:
        verdict = "unknown"
        status = "core_unknown"
    elif triggered:
        verdict = "replace"
    elif observe:
        verdict = "observe"
    elif not _has_any_signal:
        verdict = "unknown"
        status = "no_signal"
    elif _not_evaluable:
        verdict = "unknown"
        status = "rules_incomplete"
    else:
        verdict = "keep"

    # ─── 人類可讀訊息 ──────────────────────────────────────────
    if status == "core_unknown":
        msg = "⬜ 分類未判定（分類資料未取得或無法對應），暫不提供換／留建議"
        if triggered or observe:
            # 只列證據,不帶「先觀察」這類結論字(DG-6:分類未判定不給換／留／觀察結論)
            _ev = [t.replace(",先觀察", "") for t in (triggered + observe)]
            msg += "；證據：" + " / ".join(_ev)
    elif status == "rules_incomplete":
        msg = ("⬜ 無法判定 — 規則 " + "".join(f"({k})" for k in _not_evaluable)
               + " 資料不足，不提供保留結論")
    elif verdict == "replace":
        msg = f"🔴 建議換 — 中 {len(triggered)} 條 hard trigger:" + " / ".join(triggered)
    elif verdict == "observe":
        msg = f"🟡 觀察 — {len(observe)} 個警示訊號:" + " / ".join(observe)
    elif verdict == "keep":
        msg = "🟢 保留 —  4 規則全未中,持續持有"
    else:
        msg = "⬜ 資料不足 — 無法判定(持有期或關鍵指標缺)"

    _label = (_UNKNOWN_LABEL_BY_STATUS.get(status, _VERDICT_LABEL["unknown"])
              if verdict == "unknown" else _VERDICT_LABEL[verdict])
    return {
        "verdict": verdict,
        "emoji": _VERDICT_EMOJI[verdict],
        "label": _label,
        "triggered_rules": triggered,
        "observe_signals": observe,
        "message": msg,
        "status": status,
    }
