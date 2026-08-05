"""services/macro_composite_score.py — 宏觀健康度 composite score(v19.197 P1-1)

v19.197 P1-1 從 ui/helpers/macro_helpers.py 下沉。修 ARCHITECTURE_AUDIT V2 違憲
(services/realtime_signal.py:67 原 `from ui.helpers.macro_helpers import ...` 反向依賴)。

對外 API:
- `calculate_composite_score(ind)` — 將 23 項指標 (score × weight) 加總為健康度總分
- `composite_verdict(total_score)` — 5 級白話評價(icon / level / color / action_text)

兩函式皆為 L2 純函式,本來就不依賴 streamlit/UI,只用 services.macro.weights_store(同層)
+ shared.colors(L0)。原放 ui/helpers/macro_helpers.py 純屬歷史遺留 — v18.133 從 app.py
搬出時就近塞進 ui/helpers,實際是 macro 業務邏輯。

ui/helpers/macro_helpers.py 保留 shim re-export 確保既有 L3 caller(app.py / ui/tab1_macro.py)
不需改 import path。
"""
from __future__ import annotations

from shared.colors import (
    MATERIAL_GREEN, MATERIAL_RED, MD_AMBER_300, MD_GREEN_A200, MD_RED_A100,
)


# ══════════════════════════════════════════════════════════════════════
# v19.405 稽核收口:指標聚合的**兩條正交契約**(所有 aggregator 共用語意)
# ══════════════════════════════════════════════════════════════════════
# 1) `weight` = **評分權重**。`0` 是完全合法的值(= 本格不進任何加權分子/分母),
#    **不是**「沒填」。因此一律用「鍵不存在 / None 才回退 1」判斷,
#    **禁止** `float(v.get("weight", 1) or 1)` —— Python `0 or 1 == 1`,
#    falsy 回退會把刻意歸零的權重「還原」成 1,去重當場失效
#    (v19.404 M2/M2_WEEKLY 去重被此式吃掉,QA Reject 主因)。
# 2) `superseded_by` = **去重事實**(§2.2 provenance)。同一經濟因子有主/備兩源
#    (M2SL 月頻 vs WM2NS 週頻)且主源已命中時,備源會標 `superseded_by="M2"`。
#    給**不吃 weight 的路徑**用(zpct 百分位平均、今日關鍵橫幅),
#    這些路徑用 weight 去重會破壞其方法學獨立性(F-RECON-1)。
#
# 兩者刻意分離:weight 管「算多重」、superseded_by 管「是不是同一顆的分身」。
# 生產端在 `services/macro/us_indicators.py` R["M2_WEEKLY"] 區塊同時輸出兩者。


def coerce_weight(raw, default: float = 1.0) -> float:
    """把 indicator dict 的 `weight` 欄轉 float,**保留 0**。

    Raises TypeError/ValueError 由 caller 決定怎麼處理(各 aggregator 的既有
    try/except 慣例不同,這裡不吞例外 — §1)。
    """
    if raw is None:
        return float(default)
    return float(raw)


def is_superseded(ind: dict, container: dict | None = None) -> str | None:
    """本指標是否為「已被主源取代的備源」→ 回傳主源 key;否則 None。

    Args:
        ind: 單一 indicator dict。
        container: 完整 indicators dict(可選)。有傳時**額外要求主源真的在場** —
            若主源不在(舊 cache / 測試 fixture 只塞了備源),回 None 讓備源照常
            參與,避免把僅有的一筆資料靜默丟掉(§1 不假裝沒資料)。
    """
    if not isinstance(ind, dict):
        return None
    key = ind.get("superseded_by")
    if not isinstance(key, str) or not key:
        return None
    if container is not None and not isinstance(container.get(key), dict):
        return None
    return key


def calculate_composite_score(ind: dict, *,
                              provenance_out: dict | None = None) -> float:
    """將 23 項指標 (score × weight) 加總為「宏觀健康度總分」。

    缺值/NaN/型別錯誤一律以 0 處理（fillna(0) 等價）；純函式、零快取。
    v19.1 (C-2)：入口呼叫 ``apply_weight_overrides`` — active.json 有 weight 就蓋，
    否則保留呼叫端原值（active 為空時行為跟 v18.x 完全一樣）。

    v19.270 D8 #8 F-PROV-1:opt-in provenance via side-car dict(§2.2 補洞)。

    Parameters
    ----------
    ind : dict
        23 項指標 dict,每項含 score/weight/source/fetched_at(後二者 schema-additive)。
    provenance_out : dict | None, optional
        若傳入(非 None),會被填入聚合 provenance:
        - ``sources``: list[str] — 排序去重的個別指標 source 字串
        - ``fetched_at_latest``: str — 各指標 fetched_at 取最大值(代表最新一次抓取)
        - ``contributions``: dict[str, dict] — 每指標 {score, weight, weighted}
        - ``n_indicators``: int — 實際有效參與的指標數
        既有 caller 傳 None 行為完全一致;新 caller 傳 dict 取得血緣。
    """
    if not isinstance(ind, dict):
        return 0.0
    try:
        from services.macro.weights_store import apply_weight_overrides
        ind = apply_weight_overrides(ind)
    except ImportError:
        pass  # C-2 模組未部署時走原邏輯
    total = 0.0
    # v19.270 D8 #8:provenance 蒐集容器(只在 caller opt-in 時用)
    _sources: list[str] = []
    _fetched_at_max: str = ""
    _contribs: dict[str, dict] = {}
    _n: int = 0
    for k, v in ind.items():
        if not isinstance(v, dict):
            continue
        try:
            sf = float(v.get("score", 0) or 0)
            # v19.405:weight=0 合法(去重後的備源),不可被 `or 1` falsy 回退還原。
            wf = coerce_weight(v.get("weight", 1))
        except (TypeError, ValueError):
            continue
        if sf != sf or wf != wf:  # IEEE-754 NaN guard
            continue
        contrib = sf * wf
        total += contrib
        if provenance_out is not None:
            _n += 1
            src = v.get("source")
            if isinstance(src, str) and src:
                _sources.append(src)
            fa = v.get("fetched_at")
            if isinstance(fa, str) and fa > _fetched_at_max:
                _fetched_at_max = fa
            _contribs[str(k)] = {
                "score": sf, "weight": wf,
                "weighted": round(contrib, 4),
            }
    if provenance_out is not None:
        provenance_out["sources"] = sorted(set(_sources))
        provenance_out["fetched_at_latest"] = _fetched_at_max
        provenance_out["contributions"] = _contribs
        provenance_out["n_indicators"] = _n
    return round(total, 2)


def reconcile_composite_score(ind: dict) -> dict:
    """v19.367 6/8:F-RECON-1 最後一項 — 健康度**雙演算法對帳**(§4.3)。

    演算法 A(主):`calculate_composite_score` 加權淨分(score × weight 加總)。
    演算法 B(對照):**不加權多空方向投票** — 只數 score>0 / score<0 的指標數,
    `net_ratio = (n_pos - n_neg) / n_valid` ∈ [-1, 1]。**方法學獨立**(無視權重),
    專抓「單一大權重指標把總分拖向與多數指標相反方向」的權重配置錯誤。

    方向判定:
    - A 向:total > c2(樂觀線)→ pos;total < c3(悲觀線)→ neg;其間 → neu
      (沿用 `get_verdict_cutoffs` 同一組語意分界,§3.3 不另造 magic)
    - B 向:|net_ratio| <= COMPOSITE_VOTE_NEUTRAL_BAND → neu;否則依正負
    狀態:同向 → "agree";一向中性 → "neutral_mix"(弱訊號,非衝突);
          一正一負 → "disagree"(⚠️ 需檢查權重配置 / 單指標暴衝)。
    純函式;ind 無效 → n_valid=0 + status="no_data"(§1 不偽造)。
    """
    from shared.signal_thresholds import COMPOSITE_VOTE_NEUTRAL_BAND

    total = calculate_composite_score(ind)
    n_pos = n_neg = n_zero = 0
    if isinstance(ind, dict):
        for v in ind.values():
            if not isinstance(v, dict):
                continue
            try:
                sf = float(v.get("score", 0) or 0)
            except (TypeError, ValueError):
                continue
            if sf != sf:  # NaN guard
                continue
            if sf > 0:
                n_pos += 1
            elif sf < 0:
                n_neg += 1
            else:
                n_zero += 1
    n_valid = n_pos + n_neg + n_zero
    if n_valid == 0:
        return {"weighted_total": total, "vote_net_ratio": None,
                "n_pos": 0, "n_neg": 0, "n_zero": 0,
                "dir_weighted": "neu", "dir_vote": "neu",
                "status": "no_data", "note": "無有效指標,無法對帳(§1)"}

    net_ratio = (n_pos - n_neg) / n_valid
    try:
        from services.macro.weights_store import get_verdict_cutoffs
        _c1, c2, c3, _c4 = get_verdict_cutoffs()
    except ImportError:
        c2, c3 = 5.0, -5.0
    dir_w = "pos" if total > c2 else ("neg" if total < c3 else "neu")
    dir_v = ("neu" if abs(net_ratio) <= COMPOSITE_VOTE_NEUTRAL_BAND
             else ("pos" if net_ratio > 0 else "neg"))

    if dir_w == dir_v:
        status, note = "agree", "加權淨分與多空投票同向"
    elif "neu" in (dir_w, dir_v):
        status, note = "neutral_mix", "一方中性 — 弱訊號,非衝突"
    else:
        status = "disagree"
        note = (f"⚠️ 加權淨分({dir_w})與多空投票({dir_v})反向 — "
                f"檢查權重配置 / 是否單一大權重指標暴衝")
    return {"weighted_total": total, "vote_net_ratio": round(net_ratio, 3),
            "n_pos": n_pos, "n_neg": n_neg, "n_zero": n_zero,
            "dir_weighted": dir_w, "dir_vote": dir_v,
            "status": status, "note": note}


def composite_verdict(total_score: float) -> tuple[str, str, str, str]:
    """回傳 (icon, level, color, action_text) 對應 5 級白話評價。

    v19.1 (C-2)：分界 cutoffs 改從 ``get_verdict_cutoffs()`` 讀取；
    active.json.verdict_cutoffs 為 null → 回退硬編碼 (+10, +5, -5, -10)。
    """
    try:
        from services.macro.weights_store import get_verdict_cutoffs
        c1, c2, c3, c4 = get_verdict_cutoffs()
    except ImportError:
        c1, c2, c3, c4 = 10.0, 5.0, -5.0, -10.0
    if total_score > c1:
        return ("🟢", "極度樂觀", MATERIAL_GREEN,
                "多頭市場強勁：可滿倉持有，衛星部位積極佈局成長題材")
    if total_score > c2:
        return ("🟢", "樂觀", MD_GREEN_A200,
                "景氣穩定擴張：核心持有不動，定期定額正常進行")
    if total_score >= c3:
        return ("🟡", "中性", MD_AMBER_300,
                "市場震盪整理：分批進場，避免重押單一題材")
    if total_score >= c4:
        return ("🔴", "悲觀", MD_RED_A100,
                "風險正在集結：拉高現金水位至 15-25%，衛星部位設停利")
    return ("🔴", "極度悲觀", MATERIAL_RED,
            "避險情緒高漲：現金 30%+，核心轉防守型（投資等級債/全球均衡）")
