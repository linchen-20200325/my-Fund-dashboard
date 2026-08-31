"""services/homogeneity.py — ② 持倉互斥避險:警示對彙整 + 同質化分級(2026-08-31)。

客戶 2026-08-31 拍板(線框 `docs/wireframes/rotation-components-wireframe.html` Q1/Q2):
把「高相關警示對」從進階分析升格為持倉風險一級答案,並新增「同質化程度」分級。

本檔是**純函式層(L2)**:零 I/O、零 streamlit。相關性/重疊度的**計算本體**
本來就住在 L2 `services/portfolio_service.py::calc_holdings_overlap /
calc_correlation_matrix`(v19.176 SSOT WRITER),本檔**不重算任何係數、
不改任何既有數字的算法** —— 只做三件既有輸出沒有的事(線框 06 節「資料需求」表):

  1. **警示對輸出補齊**:把兩維度的 shadow_pairs 併成一份清單,逐對帶上
     相關型態(持股重疊 / 走勢同步)與該型態的門檻值(供畫面併列顯示)。
  2. **成功對數**:兩維度各自「實際算得出來」的對數與其聯集 ——
     同質化分母用它,不可拿理論對數 N×(N−1)/2 充數(§1 不造假)。
  3. **被剔除的缺資料檔名單**:現況兩個計算入口對缺資料檔**靜默縮小比對範圍**
     (calc_correlation_matrix 直接濾掉 series 不足者;calc_holdings_overlap
     對雙缺對填 0.0),本檔把被跳過的檔**具名帶出**,供 UI ⬜ 誠實揭露(§1)。

同質化分級(Q2,切點收 shared/signal_thresholds SSOT):
  比率 = 警示對數(兩維度聯集)÷ 實際比對成功對數(聯集);
  0 對 = 低 🟢;>0 且 ≤ HOMOGENEITY_MID_MAX_RATIO = 中 🟡;> 之 = 高 🔴;
  成功對數 < HOMOGENEITY_MIN_PAIRS → ⬜ 樣本不足,不硬判。

⚠️ 兩個維度**各自獨立判定、不合併成單一分數**(沿用 v19.289 既有設計決定);
本檔的「聯集」只用在**計數**(幾對被警示、幾對比得成),不是把兩種係數混算。
"""
from __future__ import annotations

from shared.signal_thresholds import (
    HOMOGENEITY_MID_MAX_RATIO,
    HOMOGENEITY_MIN_PAIRS,
    SHADOW_FUND_NAV_CORR_THRESHOLD_RATIO,
    SHADOW_FUND_THRESHOLD_RATIO,
)

#: 兩維度的顯示語彙(UI 與 CSV 共用;label 是給人看的,kind 是給程式配對的)
DIM_HOLDINGS = "holdings"
DIM_NAV = "nav"
DIM_LABELS = {DIM_HOLDINGS: "持股重疊", DIM_NAV: "走勢同步"}
DIM_THRESHOLDS = {
    DIM_HOLDINGS: SHADOW_FUND_THRESHOLD_RATIO,
    DIM_NAV: SHADOW_FUND_NAV_CORR_THRESHOLD_RATIO,
}


def _pair_key(a: str, b: str) -> tuple:
    """無序對 → 穩定 key(排序後 tuple);同一對不因 (A,B)/(B,A) 算兩次。"""
    return tuple(sorted((str(a), str(b))))


def homogeneity_grade(alert_pairs: int, success_pairs: int, *,
                      mid_max: float = HOMOGENEITY_MID_MAX_RATIO,
                      min_pairs: int = HOMOGENEITY_MIN_PAIRS) -> dict:
    """Q2 分級。回 {"grade": "low"|"mid"|"high"|"insufficient", "ratio": float|None}。

    - 成功對數 < min_pairs → "insufficient"(⬜ 樣本不足,ratio=None,不硬判)。
    - 0 警示對 → "low";比率 ∈ (0, mid_max] → "mid";> mid_max → "high"。
    比率分母 = **成功**對數(不是理論對數;缺資料的對不入分母,§1)。
    """
    if success_pairs < min_pairs:
        return {"grade": "insufficient", "ratio": None}
    ratio = alert_pairs / success_pairs
    if alert_pairs == 0:
        return {"grade": "low", "ratio": 0.0}
    return {"grade": "mid" if ratio <= mid_max else "high", "ratio": ratio}


def _has_dims(fund: dict) -> tuple:
    """(has_holdings, has_sector) —— calc_holdings_overlap 資料在場判定的**明寫鏡像複本**。

    ⚠️ 這不是第二份演算法:calc_holdings_overlap 的 has_h/has_s 是**內部變數**
    沒有輸出,無法從其回傳值推回「哪一對是真算的、哪一對是雙缺填 0.0 的」,
    故在此明寫一份複本。鏡像到的點:持股「有無名稱」、sector 要求 name 非空
    且 pct > 0、pct 解析失敗當 0.0。

    ⚠️ 已知分家點(2026-08-31 稽核實測推翻「逐字鏡像」宣稱;單組結論):
    1. **純空白持股名**:SSOT 端過濾式 `if h.get("name")` 取 strip **前** truthy ——
       兩檔基金 `top_holdings=[{"name": "  "}]` 時,空白名被收進集合、正規化成 ""
       後兩檔共享 {""} → Jaccard=1.0 產出影子警示對;本函式要求 strip **後**非空
       → 判該檔無持股資料。同一情境下 SSOT 端出紅卡、本函式把該對排除在成功對
       之外(畫面自相矛盾);且警示對數可大於成功對數,homogeneity_grade 的
       ratio 理論上可 > 1(無 clamp)。
    2. **例外捕捉範圍**:sector pct 解析,SSOT 端 `except Exception`,
       本函式 `except (TypeError, ValueError)`。
    根因在 SSOT 端把純空白名當資料(既有行為,本批無權改);修法屬另案裁決,
    此處僅據實揭露,不改 SSOT、也不改本函式行為(§-1.5.3 C 禁止夾帶)。

    鏡像鎖測試(`tests/test_homogeneity_service.py`)實際覆蓋的只有兩點:
    「雙缺對填 0.0 不算成功」與「sector pct=0 不算有資料」—— 不含上列分家情境。
    """
    f = fund or {}
    has_h = any((h.get("name") or "").strip() for h in (f.get("top_holdings") or []))
    has_s = False
    for s in (f.get("sector_alloc") or []):
        name = (s.get("name") or "").strip()
        try:
            pct = float(s.get("pct", 0) or 0)
        except (TypeError, ValueError):
            pct = 0.0
        if name and pct > 0:
            has_s = True
            break
    return has_h, has_s


def _nav_membership(corr_result: "dict | None") -> "tuple[set, set] | None":
    """NAV 維度的 (納入比對的 code 集合, 成功對集合)。無 matrix → None(維度沒算成)。

    刻意**從輸出矩陣反推**而非復刻 calc_correlation_matrix 的過濾規則
    (series ≥ 30 筆那條住在該函式內部)—— 這樣門檻改了本檔自動跟上,
    不會養出第二把尺(§2.1 SSOT)。對角外 NaN 的格子不算成功對。
    """
    if not corr_result or corr_result.get("matrix") is None:
        return None
    mx = corr_result["matrix"]
    codes = [str(c) for c in mx.columns]
    ok_pairs: set = set()
    import pandas as pd
    for i, a in enumerate(codes):
        for j in range(i + 1, len(codes)):
            v = mx.iloc[i, j]
            if not pd.isna(v):
                ok_pairs.add(_pair_key(a, codes[j]))
    return set(codes), ok_pairs


def build_mutual_exclusion_summary(hov_input: list, corr_input: list,
                                   hov_result: "dict | None",
                                   corr_result: "dict | None") -> dict:
    """把兩個既有計算結果彙整成 ②「持倉互斥避險」元件需要的一份 dict。

    輸入:
      hov_input  : calc_holdings_overlap 的**同一份**輸入(code/name/top_holdings/sector_alloc)
      corr_input : calc_correlation_matrix 的**同一份**輸入(code/series;可另帶 name)
      hov_result / corr_result:上述兩函式的原樣輸出(本檔不重算、不改值)

    輸出 dict:
      n_funds / theoretical_pairs
      dims: {holdings|nav: {computed, success_pairs, threshold, label}}
      success_pairs_union: int(同質化分母)
      alerts: [{code_a, name_a, code_b, name_b,
                hits: [{kind, label, value, threshold}, ...]}, ...]
              —— 依最高係數排序;同一對兩維度都命中 → 一筆、兩個 hit(獨立判定不合併)
      alert_pair_count: int(兩維度**聯集**的對數)
      excluded: [{code, name, reasons: [...]}](§1 被剔除檔具名)
      homogeneity: {"grade", "ratio"}(Q2)
    """
    names: dict = {}
    order: list = []
    for src in (hov_input or []), (corr_input or []):
        for f in src:
            code = str((f or {}).get("code") or "?")
            if code not in names:
                order.append(code)
            nm = (f or {}).get("name")
            if nm or code not in names:
                names[code] = str(nm or names.get(code) or code)
    n = len(order)
    theoretical = n * (n - 1) // 2

    # ── 維度 1:持股/產業(從輸入判在場;matrix 沒算成 → 整維度 0 成功對)──
    hov_computed = bool(hov_result and hov_result.get("matrix") is not None)
    dims_by_code = {str((f or {}).get("code") or "?"): _has_dims(f)
                    for f in (hov_input or [])}
    hold_success: set = set()
    if hov_computed:
        codes_h = [c for c in order if c in dims_by_code]
        for i, a in enumerate(codes_h):
            for b in codes_h[i + 1:]:
                ha, sa = dims_by_code[a]
                hb, sb = dims_by_code[b]
                # 鏡像 calc_holdings_overlap:兩邊同有持股 或 兩邊同有產業,才有真係數;
                # 雙缺對它會填 0.0 —— 那是「沒比到」不是「不相關」,不算成功(§1)。
                if (ha and hb) or (sa and sb):
                    hold_success.add(_pair_key(a, b))

    # ── 維度 2:NAV 走勢(從輸出矩陣反推成員與成功對)──
    nav = _nav_membership(corr_result)
    nav_computed = nav is not None
    nav_codes, nav_success = nav if nav_computed else (set(), set())

    # ── 警示對(兩維度聯集;各 hit 帶型態 + 門檻,不合併成單一分數)──
    hits_by_pair: dict = {}
    for kind, result in ((DIM_HOLDINGS, hov_result), (DIM_NAV, corr_result)):
        for p in ((result or {}).get("shadow_pairs") or []):
            key = _pair_key(p[0], p[1])
            hits_by_pair.setdefault(key, []).append({
                "kind": kind,
                "label": DIM_LABELS[kind],
                "value": float(p[2]),
                "threshold": DIM_THRESHOLDS[kind],
            })
    alerts = []
    for key, hits in hits_by_pair.items():
        a, b = key
        alerts.append({
            "code_a": a, "name_a": names.get(a, a),
            "code_b": b, "name_b": names.get(b, b),
            "hits": sorted(hits, key=lambda h: -h["value"]),
        })
    alerts.sort(key=lambda al: -max(h["value"] for h in al["hits"]))

    # ── 被剔除檔(§1:靜默縮小範圍 → 具名帶出)──
    excluded = []
    for code in order:
        reasons = []
        ha, sa = dims_by_code.get(code, (False, False))
        if not ha and not sa:
            reasons.append("缺持股與產業資料(不入持股重疊比對)")
        if nav_computed and code not in nav_codes:
            reasons.append("NAV 序列缺少或筆數不足(不入走勢同步比對)")
        if reasons:
            excluded.append({"code": code, "name": names.get(code, code),
                             "reasons": reasons})

    success_union = hold_success | nav_success
    hom = homogeneity_grade(len(hits_by_pair), len(success_union))
    return {
        "n_funds": n,
        "theoretical_pairs": theoretical,
        "dims": {
            DIM_HOLDINGS: {"computed": hov_computed,
                           "success_pairs": len(hold_success),
                           "threshold": DIM_THRESHOLDS[DIM_HOLDINGS],
                           "label": DIM_LABELS[DIM_HOLDINGS]},
            DIM_NAV: {"computed": nav_computed,
                      "success_pairs": len(nav_success),
                      "threshold": DIM_THRESHOLDS[DIM_NAV],
                      "label": DIM_LABELS[DIM_NAV]},
        },
        "success_pairs_union": len(success_union),
        "alerts": alerts,
        "alert_pair_count": len(hits_by_pair),
        "excluded": excluded,
        "homogeneity": hom,
    }
