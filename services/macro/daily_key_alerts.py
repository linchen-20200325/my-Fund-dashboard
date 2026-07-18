"""services/macro/daily_key_alerts.py — ⚡ 今日關鍵橫幅判定(L2 純函式)。

v19.349(未完成清單第 4 步,user 核准;股票 repo v19.108 設計 A 同構移植):
把「今天最需要看的異常」從**已載入**的資料裡挑出來,供 Tab1 頁首橫幅置頂。

基金版兩層(**零新計算,純消費既有 SSOT 輸出** — 對照股票版的門檻/急變兩層):
- **訊號層**:吃 `indicators` dict(fetch_all_indicators,23 keys)各 block 的
  `score`(SCORE_RULES SSOT 已算好;fund 慣例:**正 = 偏多/風險下降、負 = 偏空/
  風險升高** — 對照 us_indicators.py 各指標 🟢=正分/🔴=負分)。橫幅只挑**風險側**
  (負分)且夠強的指標,|score| 越大越嚴重:score ≤ -SIGMA_HIGH_CUTOFF → 紅級;
  ≤ -SIGMA_LOW_CUTOFF → 黃級;≥ -SIGMA_LOW_CUTOFF(偏多或接近中性)= 非風險事件。
  白話 detail 直接用 `_interpret_indicator(score)`(SSOT 敘事)。
  同級內依 |score×weight|(contribution)降冪 — active.json 校準權重
  自然決定「誰排前面」。
  (v19.352 修正:原判定用 `score ≥ SIGMA` 把**偏多**指標當紅色警示置頂,並把
   真正的**風險側**負分指標 continue 跳過——sign 反了。此版改吃負分側。)
- **拐點層**:吃 `detect_turning_points` 輸出(session `_tp_v1948_top`,
  5 組拐點,signal/icon/note 已由該 SSOT 判定)。icon ∈ {🔴,🔻,⚠️} → 紅級;
  {🟡,🚀} → 黃級(🚀 利多拐點同樣「今天該看」);{🟢,📊,⬜} = 非事件不進橫幅。

§8.2 L2 Service:純函式 in→out,零 I/O、零 streamlit。caller(L3 tab1)自
session_state 取數傳入。失敗降級(§1):block 缺鍵/型別壞 → 跳過該項
不腦補(單項 try 收窄,判定層錯誤絕不炸頁);全空 → items=[]。
"""
from __future__ import annotations

from shared.signal_thresholds import SIGMA_HIGH_CUTOFF, SIGMA_LOW_CUTOFF

# 拐點 icon → 嚴重度(0=紅級必看,1=黃級提示);不在表內 = 非事件
_TP_ICON_SEVERITY: dict = {
    '🔴': 0, '🔻': 0, '⚠️': 0,
    '🟡': 1, '🚀': 1,
}


def _indicator_items(indicators: dict | None) -> list[dict]:
    """訊號層:score ≥ SIGMA 門檻的指標 → 橫幅 item(同級依 |contribution| 降冪)。"""
    from services.macro.explain import _interpret_indicator   # 同層 L2,SSOT 敘事
    items: list[dict] = []
    for key, v in (indicators or {}).items():
        if not isinstance(v, dict) or 'score' not in v:
            continue
        try:
            score = float(v.get('score'))
            weight = float(v.get('weight', 1.0))
        except (TypeError, ValueError):
            continue   # 型別壞 → 跳過該指標(§1 不腦補)
        # fund 慣例:score 負 = 偏空/風險升高(對照 us_indicators.py 各指標 🟢=正/🔴=負)。
        # 橫幅只挑風險側(負分)且夠強者;|score| 越大越嚴重。
        if score > -SIGMA_LOW_CUTOFF:
            continue   # score ≥ -SIGMA_LOW_CUTOFF(偏多/接近中性)= 非風險事件
        _sev = 0 if score <= -SIGMA_HIGH_CUTOFF else 1
        _val = v.get('value')
        _val_txt = ''
        if _val is not None:
            try:
                _val_txt = f' {float(_val):g}{v.get("unit", "")}'
            except (TypeError, ValueError):
                _val_txt = f' {_val}'
        items.append({
            'emoji': '🔴' if _sev == 0 else '🟡',
            'severity': _sev,
            'text': f"{v.get('name') or key}{_val_txt}",
            'detail': _interpret_indicator(score),
            'layer': 'signal',
            '_rank': abs(score * weight),   # 內部排序鍵(校準權重決定順序)
        })
    items.sort(key=lambda i: -i['_rank'])
    for i in items:
        i.pop('_rank', None)
    return items


def _turning_point_items(turning_points: dict | None) -> list[dict]:
    """拐點層:detect_turning_points 輸出中的事件級拐點 → 橫幅 item。"""
    items: list[dict] = []
    for _key, d in (turning_points or {}).items():
        if not isinstance(d, dict) or not d.get('source_ok'):
            continue   # 資料不足/抓取失敗的拐點不進橫幅(⬜ 非事件)
        _sev = _TP_ICON_SEVERITY.get(str(d.get('icon', '')))
        if _sev is None:
            continue   # 🟢/📊 等非事件
        items.append({
            'emoji': str(d.get('icon', '')),
            'severity': _sev,
            'text': f"{d.get('label', _key)}：{d.get('signal', '')}",
            'detail': str(d.get('note', '')),
            'layer': 'turning_point',
        })
    return items


def collect_key_alerts(indicators: dict | None,
                       turning_points: dict | None) -> dict:
    """合併訊號層 + 拐點層,依嚴重度排序,回橫幅資料。

    Args:
        indicators: session_state['indicators'](fetch_all_indicators)。
        turning_points: session_state['_tp_v1948_top'](detect_turning_points)。

    Returns:
        {'items': [{'emoji','severity'(0紅/1黃),'text','detail','layer'}...]
         依 severity 升冪(紅先;訊號層同級內已依校準權重排序),
         'n_red': int, 'n_yellow': int}
    """
    items = _indicator_items(indicators) + _turning_point_items(turning_points)
    items.sort(key=lambda i: i['severity'])   # stable:同級保留層內順序
    return {
        'items': items,
        'n_red': sum(1 for i in items if i['severity'] == 0),
        'n_yellow': sum(1 for i in items if i['severity'] == 1),
    }
