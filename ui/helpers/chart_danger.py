"""ui/helpers/chart_danger.py — 圖表危險標準線 helper (v19.145 Phase B)

對齊 Stock v18.284 `tab_macro.add_danger_hlines`,Fund 端把同樣的 SSOT-driven
chart hline 能力獨立成 ui/helpers/ 公用 helper(Stock 是直接 inline 在 tab_macro)。

【為何另開新 helper,不直接改 _radar_threshold_lines / _tp_threshold_lines】
- 既有兩個 helper(`ui/tab1_macro._radar_threshold_lines` /
  `_tp_threshold_lines`)的 inline cutoff 是與 `services/risk_radar` 內部
  signal classification 對齊的(e.g. VIX 25/30 → 燈號分級也用 25/30)
- v19.144 SSOT(`shared/macro_buckets`)是基於 `MACRO_THRESHOLDS`,VIX 用 22/30
- 若把既有 helper 改成讀 SSOT,**視覺線**會與 **service 後端 classification**
  脫鉤,user 會看到「綠燈卡 + 值在黃線上方」之類的不一致(§1 反捏造原則之
  反例 — 視覺暗示 ≠ 真分級)
- 統一 SSOT 與 service 後端 → Phase D 範圍(動 service 後端,需要對齊
  既有 80+ test、calibrated thresholds JSON,規模另議)
- 本 Phase B 提供乾淨 SSOT 原語供**新增** chart 使用 +
  未來 Phase D 統一前的橋接

API:
    add_danger_hlines(fig, key: str, yref: str | None = None) -> None

    fig: plotly.graph_objects.Figure(or any object with .add_hline)
    key: shared.macro_buckets.DangerSpec.key(e.g. "vix" / "cpi_yoy" / "pmi")
    yref: 多軸圖指定 "y2" 等(預設主軸 y)

對未知 key:no-op(不 raise,§1 不適用 — 此為 chart 渲染輔助,缺資料線靜默
跳過比中斷 render 安全)。但 caller 應 log 以利除錯。
"""
from __future__ import annotations

from typing import Optional


def add_danger_hlines(fig, key: str, yref: Optional[str] = None) -> None:
    """在 plotly figure 加該指標的黃/紅危險標準線(讀 shared.macro_buckets SSOT)。

    一看就知道現值超過哪條線 = 違規。門檻與 SPEC §16 / v19.144 五桶 bar 同源。
    high_bad / low_bad 各 2 線;band 4 線。yref:多軸圖指定 'y2' 等(預設主軸)。

    Parameters
    ----------
    fig : plotly figure (or any obj with .add_hline)
    key : DangerSpec.key — 對應 shared.macro_buckets.SPECS_BY_KEY 之一
    yref : 多軸圖指定 'y2'/'y3' 等;None → 預設主軸 y

    Notes
    -----
    - 未知 key → no-op(不 raise,避免新增 chart 時筆誤 crash 整個 tab)
    - 對應 spec.unit 帶在 annotation_text(e.g. "🔴 紅線 30")
    - decimals 取自 spec(避免 4.000 / 22.0 之類冗餘)
    """
    from shared.macro_buckets import SPECS_BY_KEY, LEVEL_COLOR

    _spec = SPECS_BY_KEY.get(key)
    if _spec is None:
        return

    _pairs = [
        (_spec.yellow, LEVEL_COLOR["yellow"], "🟡 黃線"),
        (_spec.red, LEVEL_COLOR["red"], "🔴 紅線"),
    ]
    if _spec.direction == "band":
        _pairs += [
            (_spec.yellow_lo, LEVEL_COLOR["yellow"], "🟡 黃線"),
            (_spec.red_lo, LEVEL_COLOR["red"], "🔴 紅線"),
        ]

    for _y, _c, _lbl in _pairs:
        if _y is None:
            continue
        # 數值格式化:整數值不加小數,非整數依 spec.decimals
        if isinstance(_y, float) and _y.is_integer():
            _y_txt = f"{int(_y)}"
        else:
            _y_txt = f"{_y:.{_spec.decimals}f}"
        _kw = dict(
            y=_y, line_dash="dash", line_color=_c, opacity=0.6,
            annotation_text=f"{_lbl} {_y_txt}{_spec.unit}",
            annotation_position="top left",
            annotation_font=dict(size=9, color=_c),
        )
        if yref:
            _kw["yref"] = yref
        fig.add_hline(**_kw)
