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
# v19.405 → v19.425 稽核收口:指標聚合的**三條正交契約**(所有 aggregator 共用語意)
# ══════════════════════════════════════════════════════════════════════
# 1) `weight` = **評分權重**。`0` 是完全合法的值(= 本格不進任何加權分子/分母),
#    **不是**「沒填」。因此一律用「鍵不存在 / None 才回退 1」判斷,
#    **禁止** `float(v.get("weight", 1) or 1)` —— Python `0 or 1 == 1`,
#    falsy 回退會把刻意歸零的權重「還原」成 1,去重當場失效
#    (v19.404 M2/M2_WEEKLY 去重被此式吃掉,QA Reject 主因)。
# 2) `superseded_by` = **去重事實**(§2.2 provenance)。同一經濟因子有主/備兩源
#    (M2SL 月頻 vs WM2NS 週頻)且主源已命中時,備源會標 `superseded_by="M2"`。
#    給**不吃 weight 的路徑**用,這些路徑用 weight 去重會破壞其方法學獨立性
#    (F-RECON-1)。目前**共 3 條**:`calc_macro_phase_zpct`(百分位平均)、
#    `collect_key_alerts`(今日關鍵橫幅)、`reconcile_composite_score`
#    (多空投票對帳 —— v19.425 補上,前一輪漏網)。新增不吃 weight 的
#    aggregator 時,必須同步接這條契約。
#
# 兩者刻意分離:weight 管「算多重」、superseded_by 管「是不是同一顆的分身」。
# 生產端在 `services/macro/us_indicators.py` R["M2_WEEKLY"] 區塊同時輸出兩者。
#
# 3) `_` 前綴 key = **meta,不是指標**(v19.425 收口為共用述詞 `is_meta_key`)。
#    `fetch_all_indicators` 除指標外還會塞 provenance meta(目前只有 `_fred_sources`)。
#    這類 meta 沒有 `score` / `weight` 欄,任何「用 .get 取預設值」的 aggregator
#    都會把它當成一顆「score=0 / weight=1」的指標混進分母。原本這道守衛被
#    **各自 inline** 在 `calc_macro_phase` / `calc_macro_phase_zpct` /
#    `_build_phase_provenance`,本模組兩條路徑則完全沒有 → v19.425 抽成本述詞,
#    5 條聚合/血緣路徑共用同一個定義(漂移鎖見 tests/test_macro_indicator_signs.py
#    `test_all_aggregators_share_the_meta_predicate`)。


# ── 綜合健康度的「警訊側」結論帶(2026-09-04 第四輪稽核)────────────────────
# 這兩級是**警訊**:它們只可能由**實際取到的負向證據**把總分壓過悲觀切點而成立
# (缺值在本演算法貢獻 0,不會把總分往任一極端推)。依通則規則 3(不對稱:
# 半套證據可以升警、不可以解除警報),它們**不受充足性閘門拘束** ——
# 把一個真的悲觀訊號灰掉,才是更糟的失效。
# ⚠️ 字串必須與 `composite_verdict` 回傳的 `level` 逐字相同;
# 漂移鎖:`tests/test_evidence_support.py::test_the_alarm_levels_exist_in_the_verdict`。
COMPOSITE_ALARM_LEVELS: tuple[str, ...] = ("悲觀", "極度悲觀")


def is_meta_key(key) -> bool:
    """`_` 前綴 = provenance meta 容器(如 `_fred_sources`),不得參與任何聚合。"""
    return str(key).startswith("_")


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
        # v19.425:`_` 前綴 meta(如 `_fred_sources`)不是指標。
        #   對 `total` 本來就無害(score 缺 → 0,0×1=0),但**血緣側車會謊報**:
        #   `n_indicators` 多算 1、`contributions["_fred_sources"]` 寫進一個
        #   不存在的「指標」條目。§2.2 血緣不得含虛構條目 —— 而 mcp_server/
        #   tools_macro.py:63 確實有傳 provenance_out,這份假血緣會被輸出。
        if is_meta_key(k) or not isinstance(v, dict):
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
    total = round(total, 2)
    if provenance_out is not None:
        provenance_out["sources"] = sorted(set(_sources))
        provenance_out["fetched_at_latest"] = _fetched_at_max
        provenance_out["contributions"] = _contribs
        provenance_out["n_indicators"] = _n
        # ── 2026-09-04 第四輪稽核:血緣側車一併回報「證據支撐」──────────────
        # 本函式的 docstring 自陳「缺值/NaN/型別錯誤一律以 0 處理(**fillna(0)
        # 等價**)」—— 也就是「沒取到」被靜默當成「中性」,而 §1 明文禁止 fillna(0)。
        # 後果:零指標時 `total = 0.0` → `composite_verdict` 給「🟡 中性」＋
        # 一句可據以行動的「分批進場，避免重押單一題材」。
        # **本欄不改 `total` 一個位元**,只回報「這個 verdict 是不是缺資料造出來的」。
        # ⚠️ 規則 3(不對稱)在此**必須**保留:悲觀側是**警訊**,由實際取到的
        # 負向證據作證,半套證據可以升警 —— 把它灰掉才是更糟的失效。
        try:
            from services.macro.evidence import (  # noqa: PLC0415 — 避免模組級循環
                composite_support as _composite_support,
            )
            provenance_out["support"] = _composite_support(
                ind, total, lambda _t: composite_verdict(_t)[1],
                alarm_bands=COMPOSITE_ALARM_LEVELS)
        except ImportError:      # 契約模組缺件 → 不擋主路徑(§1:缺就說缺)
            provenance_out["support"] = None
    return total


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

    v19.425 稽核收口:本迴圈是「不吃 weight 的第三條路徑」,補齊與
    `calc_macro_phase_zpct` / `collect_key_alerts` 相同的兩道守衛(共用述詞
    `is_meta_key` / `is_superseded`,見本模組頂部三條契約)。跳過原因寫進
    `skipped`(schema-additive),§1 不靜默丟資料。
    """
    from shared.signal_thresholds import COMPOSITE_VOTE_NEUTRAL_BAND

    total = calculate_composite_score(ind)
    n_pos = n_neg = n_zero = 0
    skipped: list[str] = []
    if isinstance(ind, dict):
        for k, v in ind.items():
            # (1) `_` 前綴 meta:`_fred_sources` 是 dict 但**沒有 `score` 鍵** →
            #     `sf=0` → 舊碼記進 n_zero,直接把 meta 灌進 n_valid 分母。
            #     這正是 v19.404 在 `calc_macro_phase:1231` 修過的同一個病,
            #     本函式從未拿到那道守衛。
            if is_meta_key(k) or not isinstance(v, dict):
                continue
            # (2) 同因子備源:本演算法**刻意不讀 weight**(不加權多空投票才與
            #     主路徑正交,F-RECON-1),所以 v19.404 給 M2_WEEKLY 的
            #     `weight=0` 對這裡完全無效 —— M2(score=+1)與 M2_WEEKLY
            #     (score=-1,SA/NSA + 月/週取樣不同,反向是常態)會各投一票
            #     互相抵銷:去重後該因子淨貢獻 +1,未去重則為 0,
            #     `net_ratio` 位移 2/n_valid(n_valid≈25 → 0.08),
            #     足以在 COMPOSITE_VOTE_NEUTRAL_BAND(0.2)邊界把
            #     agree ↔ neutral_mix ↔ disagree 翻掉。
            _sup = is_superseded(v, ind)
            if _sup:
                skipped.append(f"{k}:superseded_by={_sup}")
                continue
            try:
                sf = float(v.get("score", 0) or 0)
            except (TypeError, ValueError):
                skipped.append(f"{k}:score_invalid")
                continue
            if sf != sf:  # NaN guard
                skipped.append(f"{k}:score_nan")
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
                "skipped": skipped,
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
            "skipped": skipped,
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
