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
  (v19.405 修正:同因子備源`superseded_by` 已被主源取代者不進橫幅 —— 本層觸發
   只看 score 與 weight 無關,故 v19.404 的 `weight=0` 去重對這裡無效,
   M2 / M2_WEEKLY 會各冒一條紅級「流動性緊縮」。)
- **拐點層**:吃 `detect_turning_points` 輸出(session `_tp_v1948_top`,
  5 組拐點,signal/icon/note 已由該 SSOT 判定)。icon ∈ {🔴,🔻,⚠️} → 紅級;
  {🟡,🚀} → 黃級(🚀 利多拐點同樣「今天該看」);{🟢,📊,⬜} = 非事件不進橫幅。
- **跨層去重**(見 `collect_key_alerts`):同一個經濟因子(拐點層自報 `indicator_key`)
  只留**較嚴重**的那一條,同級留拐點層。嚴重度不比較就會出事 —— 黃級的多頭拐點
  會吞掉同因子的紅級風險訊號,`n_red` 少 1(2026-08-06 稽核 🔴 必修 2)。

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


def _indicator_items(indicators: dict | None,
                     covered_keys: dict | None = None) -> list[dict]:
    """訊號層:score ≥ SIGMA 門檻的指標 → 橫幅 item(同級依 |contribution| 降冪)。

    `covered_keys` = `{indicator_key: 拐點層該條的 severity}` —— 拐點層**這次真的
    要進橫幅**的那幾條各自宣告的同因子 key 及其嚴重度(2026-08-05 稽核 🔴 必修 4;
    2026-08-06 稽核補嚴重度比較)。

    去重規則:**同因子只留較嚴重的那一條;同級留拐點層**(它帶事件語意「衰退警報
    解除」/「高位回落」與 `note` 白話,資訊量嚴格較多)。因此本層只在
    `拐點 severity <= 本條 severity` 時才跳過。

    為什麼不能無條件跳過(原實作的 bug):HY 走「🚀 高位回落」時 icon 是黃級,
    但同一時刻 `_score_hy_spread` 對同一個 6%+ 的水位會給紅級 —— 無條件跳過會讓
    橫幅只剩一條**帶多頭語氣的黃燈**、`n_red` 少 1,該紅的那天沒有紅燈(§1 不少報)。
    刻意也**只認真的進橫幅的那幾條**:拐點若是 🟢 非事件,它根本沒進 `covered_keys`,
    訊號層那條照常顯示(拐點看轉折、訊號看水位,是兩件事)。
    """
    from services.macro.explain import _interpret_indicator   # 同層 L2,SSOT 敘事
    from services.macro.composite_score import is_superseded   # 同層 L2,去重契約 SSOT
    items: list[dict] = []
    _all = indicators or {}
    _covered = covered_keys or {}
    for key, v in _all.items():
        if not isinstance(v, dict) or 'score' not in v:
            continue
        # v19.405 稽核修正:**顯示層去重**。本層的觸發條件只看 `score`
        # (`score > -SIGMA_LOW_CUTOFF` 才排除),與 weight 無關 —— 所以
        # v19.404 給 M2_WEEKLY 的 `weight=0` 在這裡完全沒作用:月頻 M2 與週頻
        # M2_WEEKLY 會**各冒一條**「流動性緊縮」紅級警示(score=-1 ≤
        # -SIGMA_HIGH_CUTOFF 0.8),只是 _rank=|−1×0|=0 被排到同級最後。
        # 「今日最該看什麼」的橫幅把同一個經濟因子講兩次 = 誤導使用者以為
        # 兩個獨立訊號同時亮燈。備源既已被主源取代,主源那條就代表它了。
        # 用 `superseded_by`(去重事實)而非 weight:weight=0 也可能是 active.json
        # 校準把某顆權重歸零,那種情況該不該顯示是另一回事,語意不可混用。
        if is_superseded(v, _all):
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
        # 跨層去重(嚴重度感知):拐點層同因子那條不比本條輕 → 讓它代表這個因子;
        # 反之(拐點較輕)本條留下,`collect_key_alerts` 會反向砍掉較輕的拐點那條。
        _tp_sev = _covered.get(key)
        if _tp_sev is not None and _tp_sev <= _sev:
            continue
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
            # 內部欄位:讓 `collect_key_alerts` 知道本條活下來的是哪個因子,
            # 據以反向砍掉同因子但較輕的拐點那條。回傳前一律 pop 掉,不外洩。
            '_factor_key': key,
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
            # 產生端(`services/macro/turning_points.py`)自報的同因子訊號層 key。
            # 消費者是本檔 `collect_key_alerts` 的顯示層去重(§3.3:對照表在
            # 產生端,不在這裡)。缺欄 / None = 沒有同因子的訊號層指標。
            'indicator_key': d.get('indicator_key'),
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
    # 2026-08-05 稽核 🔴 必修 4:兩層原本直接相加,但它們吃**同一批 FRED 序列** ——
    # CFNAI / 薩姆 / 10Y-2Y / HY 四個因子各會冒出兩條(訊號層一條、拐點層一條),
    # 「今日最該看什麼」把同一件事講兩次 = 誤導使用者以為兩個獨立訊號同時亮燈
    # (與本檔對 M2 去重寫下的判準完全同一條)。對照關係由拐點層自報的
    # `indicator_key` 提供,本層不建對照表(§3.3 第二份真相)。
    #
    # 2026-08-06 稽核 🔴 必修 2 —— 去重**必須帶嚴重度**,不能無腦留拐點層:
    #   HY 90 日高點 8.0% → 現值 6.2% 且續跌時,拐點層走「🚀 信用拐點:高位回落」
    #   (icon 黃級、語氣偏多),但同一時刻訊號層對 6.2% 這個**水位**是紅級
    #   (`score ≤ -SIGMA_HIGH_CUTOFF`)。舊版無條件砍訊號層 → 橫幅只剩一條多頭黃燈、
    #   `n_red` 少 1,該紅的那天沒有紅燈。這是 §1「不可少報」的直接違反。
    # 選定策略:**同因子只留較嚴重的那一條,同級留拐點層**。
    #   - 不退回「完全不去重」:同因子講兩次會讓 n_red 灌水(上一輪剛修好的東西)。
    #   - 不改成「只有紅級拐點才能吞」:那會讓「黃拐點 × 黃訊號」又變成同因子兩條。
    #   - 同級為何留拐點:它帶事件語意 + `note` 白話,資訊量嚴格較多(原判準不變)。
    _tp_items = _turning_point_items(turning_points)
    _covered: dict = {}
    for _t in _tp_items:
        _k = _t.get('indicator_key')
        if not _k:
            continue   # 產生端沒宣告同因子 → 不去重(消費端不猜對應)
        _covered[_k] = min(_covered.get(_k, _t['severity']), _t['severity'])
    _sig_items = _indicator_items(indicators, covered_keys=_covered)
    # 反向:能活過上面那關的訊號層條目,代表它比同因子的拐點更嚴重 → 砍拐點那條。
    _sig_wins = {i.pop('_factor_key', None) for i in _sig_items}
    _sig_wins.discard(None)
    _tp_items = [t for t in _tp_items
                 if t.get('indicator_key') not in _sig_wins]
    items = _sig_items + _tp_items
    items.sort(key=lambda i: i['severity'])   # stable:同級保留層內順序
    return {
        'items': items,
        'n_red': sum(1 for i in items if i['severity'] == 0),
        'n_yellow': sum(1 for i in items if i['severity'] == 1),
    }
