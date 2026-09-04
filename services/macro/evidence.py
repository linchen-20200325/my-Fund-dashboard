"""services/macro/evidence.py — 總經產出端的「證據支撐」builder(L2 純函式,zero-IO)。

通則、規則形狀與**為什麼要有這一層**寫在 `shared/evidence_support.py` 的模組
docstring —— **動本檔之前請先讀那一段**。本檔只放**領域知識**:

  · 各指標的計分權重表(`MACRO_INDICATOR_SCORING_WEIGHTS`)
  · **相關族**表(`MACRO_CORRELATED_FAMILIES`)—— 哪些指標其實是同一件事的兩個讀數
  · 景氣位階的結論帶邊界(`PHASE_BAND_EDGES`)
  · 雙軸各自吃哪幾個 key(`GROWTH_AXIS_KEYS` / `INFLATION_AXIS_KEYS`)
  · 四支 builder:`phase_support` / `axis_supports` / `composite_support` /
    `action_light_support`

依賴方向:本檔 → `shared/*`(L0)+ `services/macro/composite_score`(同層,只 import
`shared.colors`,無環)。**本檔不得 import `us_indicators`** —— 反過來是
`us_indicators` import 本檔(契約在前、生產端在後),否則會成環。
"""
from __future__ import annotations

from typing import Mapping, Sequence

from shared.evidence_support import (
    EvidenceSupport, all_of, combine, net_margin, summed_verdict, weighted_verdict,
    witnessed,
)
from services.macro.composite_score import coerce_weight, is_meta_key

# ══════════════════════════════════════════════════════════════════════
# 1. 計分權重表 —— `fetch_all_indicators` 每個 key 的 `weight=` 字面值
# ══════════════════════════════════════════════════════════════════════
# ⚠️ **這是第二份真相,所以它必須被鎖住。** 權重的**唯一生產端**是
# `services/macro/us_indicators.py` 裡 28 個 `R["KEY"] = dict(..., weight=...)`
# 的字面值;本表存在的唯一理由是:要算「**沒取到的那些指標帶著多少權重**」,
# 就必須知道**沒出現在 dict 裡的那些 key 本來有多重** —— 那件事在 runtime
# 拿不到(抓失敗的 key 根本不會被寫進 `R`)。
#
# 漂移鎖:`tests/test_evidence_support.py::test_the_weight_table_matches_the_producer`
# 直接 AST 掃 `us_indicators.py` 逐一比對,**兩個方向都鎖**(表裡多一個 key、
# 生產端多一個 key、或同一個 key 值不同,三種都轉紅)。
#
# ⚠️ `M2_WEEKLY` 的生產端寫的是 `weight=(0 if _m2_monthly_hit else 1)` ——
# **它是唯一一個非字面值**。本表登記 `1`(月頻缺漏時它遞補計分的權重),
# 亦即**上界**;月頻命中時它自我降為 0,那只會讓「沒取到的權重」被高估一點點,
# 方向是**從嚴**(fail-closed),不會讓不該過的過關。
MACRO_INDICATOR_SCORING_WEIGHTS: Mapping[str, float] = {
    # 領先 / 循環
    "PMI": 2.0, "LEI": 1.0, "NFP": 1.0, "PERMIT_HOUSING": 0.5,
    "NEW_HOME": 0.5, "CONSUMER_CONF": 0.5,
    # 通膨
    "CPI": 0.5, "PPI": 0.5, "INFL_EXP_5Y": 1.0,
    # 就業
    "UNEMPLOYMENT": 0.5, "JOBLESS": 0.5, "CONT_CLAIMS": 0.5, "SAHM": 1.5,
    # 貨幣 / 流動性
    "M2": 1.0, "M2_WEEKLY": 1.0, "FED_BS": 1.0, "FED_RATE": 0.5, "SLOOS": 1.5,
    # 利率 / 信用
    "YIELD_10Y2Y": 2.0, "YIELD_10Y3M": 2.0, "HY_SPREAD": 2.0,
    # 市場 / 匯率 / 商品
    "VIX": 1.0, "DXY": 1.0, "ADL": 1.0, "COPPER": 0.5,
    "EURUSD": 1.0, "USDJPY": 1.0, "USDCNH": 1.0,
}

#: 生產端任一指標可能吐出的 `|score|` 上界(`YIELD_10Y2Y` / `YIELD_10Y3M` 的 ±2)。
#: 漂移鎖:`test_no_producer_emits_a_score_beyond_the_declared_bound`。
MACRO_INDICATOR_MAX_ABS_SCORE: float = 2.0


#: 全部到齊時的權重合計(**由上表加總導出,不寫死**)。量測日 2026-09-04:**28.0**。
#: ⚠️ 實際 runtime 的健康值是 **27.0** —— 月頻 `M2` 命中時 `M2_WEEKLY` 自我降為
#: `weight=0`(同因子不重複計分),而本表登記的是它的**上界** 1.0(見上方說明)。
#: 兩個數字的差是**刻意的、方向從嚴**:把「沒取到的權重」高估 1.0 只會讓閘門更緊。
MACRO_EXPECTED_TOTAL_WEIGHT: float = float(sum(MACRO_INDICATOR_SCORING_WEIGHTS.values()))


# ══════════════════════════════════════════════════════════════════════
# 2. 相關族 —— 「看起來是兩顆指標,其實是同一件事的兩個讀數」
# ══════════════════════════════════════════════════════════════════════
# **為什麼需要這張表(2026-09-04 第四輪稽核 R4-F6)**:舊門檻的推導寫著
# 「本檔案家族裡單一指標的**最大權重是 2**」,並據此推出 `total_w > 10`。
# **那個前提是假的。** 實測:
#     total_w = 10.0(舊閘門判定「充足」)
#       殖利率曲線同向為負 → score 4.0「復甦」#64b5f6「最高勝率買點！逐步加碼…」
#       殖利率曲線同向為正 → score 6.0「擴張」#00c853「股優於債…」
# `YIELD_10Y2Y` 與 `YIELD_10Y3M` **是同一條殖利率曲線的兩個讀數**(兩者都是
# 10Y 減去一個短端),同向移動是常態 —— 有效的單一因子權重是 **4 不是 2**,
# 它單獨就能把分數移動 2 分,**橫跨一整條相位邊界**,而閘門還在說「充足」。
#
# 本 repo **已經有處理這一類的既有機制**,不必發明第二套:`M2` / `M2_WEEKLY`
# 在月頻命中時把週頻降為 `weight=0` 並標 `superseded_by="M2"`
# (`us_indicators.py` 的 M2_WEEKLY 區塊,註解逐字寫「**同因子不重複計分**」)。
# 差別在於:M2 那一對是**同一個 series 的主/備兩源**,可以直接去重;
# 殖利率那一對與美元那一組是**兩個都要算分、但高度相關**的讀數,去重會改掉
# 分數本身(= 改變客戶每天在看的那個數字,屬 §8.4 步驟 4 的範圍擴大)。
# 故本輪的處置是:**分數一個字不動,改成讓「證據會計」認得族** ——
# 門檻由「單一指標」重新推導成「單一**相關族**」。
#
# ⚠️ **哪些算一族,分成「機械相關」與「經濟相關」兩種,據實標明**:
#   · **機械相關(可在 code 裡驗證)** —— 兩者共用同一條輸入序列,或一個由另一個
#     算出來。`YIELD_*`(共用 10Y 那條腿)、`DXY` + 三條美元交叉匯率
#     (DXY 依定義就是一籃子美元匯率,EUR 佔 57.6%)、`SAHM`(依定義是 `UNRATE`
#     的 3MA 減 12M 最低)、`M2`/`M2_WEEKLY`(同一個 M2,月頻 vs 週頻)。
#   · **經濟相關(工程判斷,非推導)** —— `JOBLESS`(ICSA 初領)與 `CONT_CLAIMS`
#     (CCSA 續領)、`PERMIT_HOUSING` 與 `NEW_HOME`。**這兩族的合計權重各為 1.0,
#     遠低於機械相關的 4.0,所以它們在門檻上從來不是那個綁住的族** ——
#     列進來只是把意圖寫下來,不影響任何一次判定。
MACRO_CORRELATED_FAMILIES: Mapping[str, tuple[str, ...]] = {
    # ── 機械相關 ──────────────────────────────────────────────
    "殖利率曲線": ("YIELD_10Y2Y", "YIELD_10Y3M"),
    "美元": ("DXY", "EURUSD", "USDJPY", "USDCNH"),
    "失業率": ("UNEMPLOYMENT", "SAHM"),
    "M2": ("M2", "M2_WEEKLY"),
    # ── 經濟相關(工程判斷;權重小,不綁門檻)────────────────────
    "失業金申請": ("JOBLESS", "CONT_CLAIMS"),
    "房市": ("PERMIT_HOUSING", "NEW_HOME"),
}

#: 全部到齊時**最大的**相關族權重(由上兩表導出)。量測日 2026-09-04:4.0
#: (「殖利率曲線」2+2 與「美元」1+1+1+1 並列)。
MAX_CORRELATED_FAMILY_WEIGHT: float = max(
    sum(MACRO_INDICATOR_SCORING_WEIGHTS.get(_k, 0.0) for _k in _members)
    for _members in MACRO_CORRELATED_FAMILIES.values()
)


# ══════════════════════════════════════════════════════════════════════
# 3. 景氣位階的結論帶
# ══════════════════════════════════════════════════════════════════════
# 邊界值逐字對應 `us_indicators.py::calc_macro_phase` 的
# `if score >= 8 / elif score >= 5 / elif score >= 3 / else`。
# **這裡不改那段 if-chain**(改它有引入 bug 的風險,而本輪的授權是「只改證據不足
# 時的行為」);改用**漂移鎖**保證兩邊永不分岔:
# `tests/test_evidence_support.py::test_the_band_function_matches_the_producer`
# 用 0.0~10.0 每 0.1 一格掃過去,逐點比對本函式與真的 `calc_macro_phase`。
PHASE_SCALE: float = 10.0
PHASE_BAND_EDGES: tuple[float, float, float] = (3.0, 5.0, 8.0)
PHASE_BAND_NAMES: tuple[str, str, str, str] = ("衰退", "復甦", "擴張", "高峰")

#: 最窄的一條結論帶。0~3 衰退(3)/ 3~5 復甦(**2**)/ 5~8 擴張(3)/ 8~10 高峰(**2**)
#: → 最窄 = 2.0。**由 `PHASE_BAND_EDGES` 導出,不寫死。**
PHASE_NARROWEST_BAND: float = min(
    PHASE_BAND_EDGES[0] - 0.0,
    PHASE_BAND_EDGES[1] - PHASE_BAND_EDGES[0],
    PHASE_BAND_EDGES[2] - PHASE_BAND_EDGES[1],
    PHASE_SCALE - PHASE_BAND_EDGES[2],
)

#: 「一個相關族要能被容忍,需要多少倍於它的總權重」。
#: 推導:一族(權重 W)由全負翻全正 → 分數移動 `PHASE_SCALE * W / total_w`;
#: 要求它推不過最窄帶 ⇒ `total_w > (PHASE_SCALE / PHASE_NARROWEST_BAND) * W`。
PHASE_WEIGHT_PER_BAND: float = PHASE_SCALE / PHASE_NARROWEST_BAND


def phase_band(score: float) -> str:
    """0~10 分數 → 結論帶名(與 `calc_macro_phase` 的 if-chain 等價,有漂移鎖)。"""
    _s = float(score)
    if _s >= PHASE_BAND_EDGES[2]:
        return PHASE_BAND_NAMES[3]
    if _s >= PHASE_BAND_EDGES[1]:
        return PHASE_BAND_NAMES[2]
    if _s >= PHASE_BAND_EDGES[0]:
        return PHASE_BAND_NAMES[1]
    return PHASE_BAND_NAMES[0]


# ══════════════════════════════════════════════════════════════════════
# 4. 雙軸各自吃哪幾個 key
# ══════════════════════════════════════════════════════════════════════
# 逐字對應 `calc_growth_inflation_axis` 裡的 `_get(...)` 讀取順序;
# 漂移鎖:`test_the_axis_key_tables_match_the_producer`(AST 掃該函式)。
GROWTH_AXIS_KEYS: tuple[str, ...] = (
    "PMI", "YIELD_10Y2Y", "M2", "ADL", "CONSUMER_CONF", "JOBLESS", "COPPER",
)
INFLATION_AXIS_KEYS: tuple[str, ...] = ("CPI", "PPI", "FED_RATE")


# ══════════════════════════════════════════════════════════════════════
# 5. 共用小工具
# ══════════════════════════════════════════════════════════════════════
def indicator_keys(indicators) -> tuple[str, ...]:
    """`indicators` 裡真正算得上「一個指標」的 key(排除 `_` 前綴 meta 與非 dict)。"""
    if not isinstance(indicators, dict):
        return ()
    return tuple(k for k, v in indicators.items()
                 if not is_meta_key(k) and isinstance(v, dict))


def scoring_weight(indicators) -> float:
    """本次取到的指標權重合計 —— **與 `calc_macro_phase` 的 `total_w` 同一個算法**。

    ⚠️ 這是**唯一**一份實作:`ui/tab1_macro.py` 原本有一份逐行等價的副本
    (`_phase_scoring_weight`),那正是「每個消費端各自手推一次」的形態。
    """
    _total = 0.0
    for _k in indicator_keys(indicators):
        try:
            _total += coerce_weight((indicators[_k] or {}).get("weight", 1))
        except (TypeError, ValueError):
            continue
    return _total


def _present_family_weights(indicators) -> dict:
    """本次**實際在場**的相關族 → 該族在場成員的權重合計。

    不在任何宣告族裡的指標各自成一個單元素族(它自己就是自己的最大相關單位)。
    ⚠️ 權重取**實際 dict 裡的值**而不是上面的表 —— `M2_WEEKLY` 被主源取代時
    生產端會給它 `weight=0`,那一刻它就真的不佔權重了。
    """
    _present = set(indicator_keys(indicators))
    _w: dict = {}
    _claimed: set = set()
    for _name, _members in MACRO_CORRELATED_FAMILIES.items():
        _hit = [_k for _k in _members if _k in _present]
        if not _hit:
            continue
        _claimed.update(_hit)
        _w[_name] = sum(
            coerce_weight((indicators[_k] or {}).get("weight", 1)) for _k in _hit)
    for _k in _present - _claimed:
        try:
            _w[_k] = coerce_weight((indicators[_k] or {}).get("weight", 1))
        except (TypeError, ValueError):
            continue
    return _w


# ══════════════════════════════════════════════════════════════════════
# 6. 四支 builder
# ══════════════════════════════════════════════════════════════════════
def phase_support(indicators, score) -> EvidenceSupport:
    """景氣位階(0~10 加權正規化分數)的證據支撐。規則 2-b。"""
    _got = tuple(indicator_keys(indicators))
    _miss = tuple(k for k in MACRO_INDICATOR_SCORING_WEIGHTS if k not in set(_got))
    _mw = sum(MACRO_INDICATOR_SCORING_WEIGHTS[k] for k in _miss)
    try:
        _score = float(score)
    except (TypeError, ValueError):
        # 分數本身沒拿到 → 沒有任何定論可以宣告。**不得**在這裡補一個預設值
        # 再去跑不變性檢查 —— 那會拿一個捏造的分數去背書(§1)。
        return EvidenceSupport(
            claim="景氣位階（0~10 加權合成）", rule="weighted_verdict",
            obtained=tuple(sorted(_got)), missing=tuple(sorted(_miss)),
            sufficient=False, reason="景氣位階分數未取得，無從判讀",
            detail={"obtained_weight": scoring_weight(indicators),
                    "missing_weight": _mw},
        )
    return weighted_verdict(
        "景氣位階（0~10 加權合成）",
        score=_score, obtained=_got, missing=_miss,
        obtained_weight=scoring_weight(indicators), missing_weight=_mw,
        family_weights=_present_family_weights(indicators),
        band_of=phase_band, scale=PHASE_SCALE,
        weight_per_band=PHASE_WEIGHT_PER_BAND,
    )


def _axis_signals(indicators, keys: Sequence[str],
                  raw_signals: Sequence[float]) -> dict:
    """把生產端算好的 ±1 訊號列表對回它們的 key。

    ⚠️ 生產端 `calc_growth_inflation_axis` 是**依固定順序**逐一 append 的,
    只有「該 key 有值」時才 append —— 所以「在場的 key(依同一順序)」與
    `signals` 列表**逐位對齊**。這個對齊由漂移鎖
    `test_the_axis_key_tables_match_the_producer` 保證。
    """
    _present = [k for k in keys if _axis_value_present(indicators, k)]
    return {k: float(s) for k, s in zip(_present, raw_signals)}


def _axis_value_present(indicators, key: str) -> bool:
    """該 key 對雙軸而言「有值」嗎(`ADL` 讀的是 `prev` 不是 `value`)。"""
    _node = (indicators or {}).get(key) if isinstance(indicators, dict) else None
    if not isinstance(_node, dict):
        return False
    return _node.get("prev" if key == "ADL" else "value") is not None


def axis_supports(indicators, growth_signals: Sequence[float],
                  inflation_signals: Sequence[float]) -> dict:
    """成長軸 / 通膨軸 / 象限(聯合)三個 support。規則 2-a。"""
    _g = net_margin("成長軸方向",
                    signals=_axis_signals(indicators, GROWTH_AXIS_KEYS, growth_signals),
                    expected=GROWTH_AXIS_KEYS)
    _i = net_margin("通膨軸方向",
                    signals=_axis_signals(indicators, INFLATION_AXIS_KEYS,
                                          inflation_signals),
                    expected=INFLATION_AXIS_KEYS)
    return {
        "growth_support": _g,
        "inflation_support": _i,
        # 象限是**兩軸的聯合宣稱** —— 只有一軸有方向時,象限根本命名不出來。
        "support": combine("成長×通膨四象限", _g, _i),
    }


def composite_support(indicators, total: float, band_of, *,
                      alarm_bands: Sequence[str] = ()) -> EvidenceSupport:
    """綜合健康度(未正規化的 `Σ score×weight`)的證據支撐。規則 2-c ＋ 規則 3。

    `alarm_bands` 裡的結論帶走**存在性**規則(規則 3:半套證據可以升警) ——
    這一條不能省:把一個「悲觀」警訊灰掉,才是更糟的失效
    (第四輪稽核逐字確認卡 2 / 卡 5 的不對稱性「不可反轉」,不得在此回歸)。
    """
    _got = tuple(indicator_keys(indicators))
    _miss = tuple(k for k in MACRO_INDICATOR_SCORING_WEIGHTS if k not in set(_got))
    _band = band_of(total)
    if _band in tuple(alarm_bands):
        return witnessed(f"綜合健康度：{_band}", witnesses=_got, obtained=_got)
    # 沒取到的第 k 顆,其貢獻為 `score×weight`;`|score| ≤ MAX_ABS_SCORE`
    # (生產端最大的 |score| 字面值是 2,見 `YIELD_10Y*` 的 `±2`;漂移鎖見測試)。
    _swing = sum(MACRO_INDICATOR_SCORING_WEIGHTS[k] * MACRO_INDICATOR_MAX_ABS_SCORE
                 for k in _miss)
    return summed_verdict(f"綜合健康度：{_band}", total=total,
                          obtained=_got, missing=_miss,
                          missing_swing=_swing, band_of=band_of)


def action_light_support(indicators, *, override_keys: Sequence[str],
                         triggered: Sequence[str],
                         phase_score) -> EvidenceSupport:
    """①結論 / 卡 5 的「現在能不能買」燈的證據支撐。

    兩種宣稱,**兩種規則**,不是同一件事:
      · **已觸發**(紅燈)→ 「這幾項裡至少有一項越線」= 存在性 → `witnessed`
        (規則 3:半套證據可以升警。那些 reason 逐項印著實際觀測值,自帶佐證。)
      · **未觸發**(綠/黃燈)→ 「殖利率曲線、Sahm、VIX **均未觸發**」+「景氣位階 N/10」
        = 兩個全稱宣稱的聯合 → `all_of` ＋ 景氣位階的 `phase_support`。
    """
    _present_all = [k for k in override_keys
                    if isinstance((indicators or {}).get(k), dict)
                    and (indicators or {}).get(k, {}).get("value") is not None]
    if triggered:
        # ⚠️ `missing` 照樣填:紅燈**成立**(規則 3),但「其餘都沒事」**不成立** ——
        # 消費端要能據此補一句「另有 N 項未取得，未檢查」。
        # `sufficient=True` 與 `missing` 非空並不矛盾:充足的是**這句警報**,
        # 不是「四項都檢查過」那句全稱話。
        return EvidenceSupport(
            claim="硬衰退／恐慌訊號已觸發", rule="witnessed",
            obtained=tuple(sorted(_present_all)),
            missing=tuple(sorted(set(override_keys) - set(_present_all))),
            sufficient=True, reason="",
            detail={"witnesses": tuple(sorted(triggered))},
        )
    return combine(
        "無硬衰退／恐慌訊號 ＋ 景氣位階",
        all_of("殖利率曲線、Sahm、VIX 均未觸發",
               expected=override_keys, obtained=_present_all),
        phase_support(indicators, phase_score),
    )
