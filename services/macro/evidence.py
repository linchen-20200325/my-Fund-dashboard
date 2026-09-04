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

#: 生產端把分數 round 到幾位小數才顯示 —— `calc_macro_phase` 的
#: `score = round(max(0, min(10, norm)), 1)`。**顯示端會 round,證據會計就必須
#: 知道它會 round**,否則帶邊界上的判定是近似的(2026-09-04 第五輪稽核 F1)。
#: 漂移鎖:`test_the_phase_rounding_matches_the_producer`(AST 讀那一行的字面值)。
PHASE_SCORE_DECIMALS: int = 1

#: 「傳進來的 `score` 本身已經被 round 過」帶進的誤差半徑(0.5 個最小顯示格)。
#: **由 `PHASE_SCORE_DECIMALS` 導出,不寫死。**
PHASE_SCORE_ROUNDING_TOLERANCE: float = 0.5 * (10.0 ** -PHASE_SCORE_DECIMALS)

#: 「一個相關族要能被容忍,需要多少倍於它的總權重」。
#: 推導:一族(權重 W)由全負翻全正 → 分數移動 `PHASE_SCALE * W / total_w`;
#: 要求它推不過最窄帶 ⇒ `total_w > (PHASE_SCALE / PHASE_NARROWEST_BAND) * W`。
PHASE_WEIGHT_PER_BAND: float = PHASE_SCALE / PHASE_NARROWEST_BAND


# ⚠️ **這道閘門管「權重」,管不到「組成」—— 已更正的實例(2026-09-04 第五輪 F 註)**
# 舊表述舉的例子是「**7 個市場面指標湊到門檻,一樣算不出實體經濟的位階**」。
# **那個例子在算術上不可能**(實測):任意 7 顆指標的權重上限是 **12.0**,
# 而整個市場面(ADL/DXY/VIX/COPPER/三條交叉匯率 6.5 ＋ HY_SPREAD/兩條殖利率 6.0)
# 合計 **12.5**,兩者都遠低於本閘門要求的 20.0 —— 舊例子根本過不了閘門。
#
# **真的存在的實例(實測,2026-09-04)**:把**勞動與領先**那 8 顆全部拿掉
# (`PMI` / `LEI` / `NFP` / `SAHM` / `UNEMPLOYMENT` / `JOBLESS` / `CONT_CLAIMS` /
# `CONSUMER_CONF`,合計權重 7.5),剩下的 **20.5** 過得了閘門;其餘全部最負向 →
#     score 0.0「衰退」,`support.sufficient = True`
# —— 一個**沒有任何勞動市場資料**的衰退判讀,被認證為「證據充足」。
# **本閘門看的是權重總量與不變性,看不到「缺的是哪一類」。** 這個限制沒有被修,
# 據實登記於此(要修得靠「每一類至少要有 N 顆」這種組成面條件,那是新規格,
# 需要客戶拍板,§8.4 步驟 4)。


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
    (`_phase_scoring_weight`,已於第五輪隨孤兒清理刪除),那正是「每個消費端各自手推一次」的形態。
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
def _scored_verdict_support(indicators, score, *, claim: str,
                            band_of, narrowest_band: float,
                            missing_score: str) -> EvidenceSupport:
    """**同一顆 0~10 分數**、但結論帶不同的判讀,共用這一支。

    `calc_macro_phase` 的分數被兩個消費端各自切成不同的帶:
      · 相位帶 3 / 5 / 8(衰退／復甦／擴張／高峰)—— `phase_support`
      · 買賣燈帶 4.0 / 6.5(🔴／🟡／🟢)—— `action_light_score_support`
    **「證據撐不撐得起這個判讀」要對著它自己那組帶問**;拿相位帶去替買賣燈背書,
    在 4.0 這條線上(它落在「復甦」帶的**內部**)會放行一個會翻燈的狀態
    —— 2026-09-04 第五輪稽核 F2 的同型缺陷,故在此把帶做成參數。

    `narrowest_band` 供支配性條件(規則 (B))用:一族翻向推不過最窄的一條帶。
    """
    _got = tuple(indicator_keys(indicators))
    _miss = tuple(k for k in MACRO_INDICATOR_SCORING_WEIGHTS if k not in set(_got))
    _mw = sum(MACRO_INDICATOR_SCORING_WEIGHTS[k] for k in _miss)
    try:
        _score = float(score)
    except (TypeError, ValueError):
        # 分數本身沒拿到 → 沒有任何定論可以宣告。**不得**在這裡補一個預設值
        # 再去跑不變性檢查 —— 那會拿一個捏造的分數去背書(§1)。
        return EvidenceSupport(
            claim=claim, rule="weighted_verdict",
            obtained=tuple(sorted(_got)), missing=tuple(sorted(_miss)),
            sufficient=False, reason=missing_score,
            detail={"obtained_weight": scoring_weight(indicators),
                    "missing_weight": _mw},
        )
    return weighted_verdict(
        claim,
        score=_score, obtained=_got, missing=_miss,
        obtained_weight=scoring_weight(indicators), missing_weight=_mw,
        family_weights=_present_family_weights(indicators),
        band_of=band_of, scale=PHASE_SCALE,
        weight_per_band=PHASE_SCALE / float(narrowest_band),
        # ── 2026-09-04 第五輪稽核 F1 ─────────────────────────────────
        # 生產端傳進來的是 `round(norm, 1)`,而每一種實現也會再被 round 一次。
        # 兩個誤差在帶邊界上會疊起來,不吃掉就會宣告一個「缺一項就翻掉」的定論
        # 為「充足」(實測:只缺 UNEMPLOYMENT 一項 → 4.9 復甦 / 5.0 擴張)。
        round_to=PHASE_SCORE_DECIMALS,
        score_tolerance=PHASE_SCORE_ROUNDING_TOLERANCE,
    )


def phase_support(indicators, score) -> EvidenceSupport:
    """景氣位階(0~10 加權正規化分數)的證據支撐。規則 2-b。"""
    return _scored_verdict_support(
        indicators, score, claim="景氣位階（0~10 加權合成）",
        band_of=phase_band, narrowest_band=PHASE_NARROWEST_BAND,
        missing_score="景氣位階分數未取得，無從判讀")


def action_light_score_support(indicators, score, *, band_of,
                               narrowest_band: float) -> EvidenceSupport:
    """買賣燈(🔴/🟡/🟢)那一段的證據支撐 —— 帶邊界由 `action_light` 供給。

    ⚠️ 帶邊界的 SSOT 在 `services/macro/action_light.py`(`_HOLD_SCORE_10` /
    `_BUY_SCORE_10`),**不在本檔**:本檔 import 它會與 `action_light` 成環
    (`action_light` → `evidence`)。故由呼叫端把 `band_of` 與最窄帶傳進來,
    真相源只有一份。
    """
    return _scored_verdict_support(
        indicators, score, claim="買賣燈（景氣位階切點）",
        band_of=band_of, narrowest_band=narrowest_band,
        missing_score="景氣位階分數未取得，無從定燈")


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
    """綜合健康度(未正規化的 `Σ score×weight`)的證據支撐。規則 2-c ＋ **政策豁免**。

    `alarm_bands` 裡的結論帶不上不變性閘門 —— 把一個「悲觀」警訊灰掉,是更糟的
    失效(第四輪稽核逐字確認卡 2 / 卡 5 的不對稱性「不可反轉」,不得在此回歸)。

    ⚠️ **2026-09-04 第五輪稽核 F3:這一支的理由原本寫錯了,就地更正。**
    舊表述寫「走**存在性**規則(規則 3)」,並因此把它讀成「不對稱是後設規則的
    **推論**」。**那是假的**,兩個地方對不上:
      · `witnessed(claim, witnesses=_got)` 收到的是**全部取到的 key**,
        **不是**「越線的那幾個」—— 它從來沒有在作證任何一件事越了線。
      · 這裡的宣稱是「**加總跨過一個切點**」,那是**聚合量**,對證據**不單調**:
        沒取到的那些指標若全部強勢,總分會被推回去。
    **實測(2026-09-04,本組自己量的)**:28 項只取到 2 項、總分 −8.0 →
    「🔴 悲觀 風險正在集結…」、`sufficient=True`;若 28 項全部取到且每顆都給
    生產端宣告的上界(`score = weight`),總分是 **+35.0 極度樂觀**。
    也就是說,這面紅旗**確實**可能被沒取到的資料翻掉。
    (⚠️ 第五輪稽核報告寫的是 +19.0,當時本組未能重現。
     → **2026-09-04 第六輪稽核 B2 已裁決:以 +35.0 為準,+19.0 沒有自然的構造。**
     佐證三條:(a) `sum(w*w for w in MACRO_INDICATOR_SCORING_WEIGHTS.values())`
     = **35.0**(本輪重跑確認 —— 每顆都給生產端宣告的上界 `score = weight` 時的總分);
     (b) 第六輪稽核另以 AST 抽每顆的 `max|score|` 得 `Σ w·max|score| = 32.5`
     (25 個可解析的 key,三組美元交叉匯率再加約 3)—— **與 35.0 同量級**;
     (c) 沒有任何一種「最大正向」的定義得出 19.0。
     ⚠️ **(a) 是本組重跑的,(b) 是轉述第六輪稽核、本組未複現**
     (本組的 AST 抽法會把門檻字面值一起抓進來,得不到乾淨的 32.5)。據實分開標。
     **結論不變**:兩者都遠在警訊帶之外,這面紅旗確實可能被沒取到的資料翻掉。)

    **它仍然照放,但理由是政策不是推導**:方向上,聚合型警報**多報一次**的代價是
    使用者多留一點現金,**少報一次**的代價是他在崩盤裡滿倉。本 repo 對這一類
    一律選前者(over-warning),`services/macro/action_light.py` 的「位階偏弱 ⇒ 🔴」
    是同一個選擇。
    ⛔ **不得**再把這裡讀成「不對稱會從後設規則自己掉出來」——
    日後若有人據此把 `alarm_bands` 這個參數「化簡掉」(因為「反正規則 3 會涵蓋」),
    那個化簡是**不安全**的:規則 3 只涵蓋存在性宣稱,涵蓋不到聚合跨切點。
    ⛔ 這個豁免**只給警報**:非警報的結論照走 `summed_verdict` 的區間不變性。
    """
    _got = tuple(indicator_keys(indicators))
    _miss = tuple(k for k in MACRO_INDICATOR_SCORING_WEIGHTS if k not in set(_got))
    _band = band_of(total)
    if _band in tuple(alarm_bands):
        return witnessed(f"綜合健康度：{_band}", witnesses=_got, obtained=_got)
    # 沒取到的第 k 顆,其貢獻為 `score×weight`;`|score| ≤ MAX_ABS_SCORE`
    # (生產端最大的 |score| 字面值是 2,見 `YIELD_10Y*` 的 `±2`;漂移鎖見測試)。
    # ⚠️ **已知偏窄,據實登記(2026-09-04 第五輪稽核,本輪未修)**:這裡用的是
    # **靜態**權重表,而 `calculate_composite_score` 會先跑 `apply_weight_overrides`
    # (`active.json` 有 weight 就蓋)。overrides 只會動到**已經在 `ind` 裡**的 key,
    # 所以一個「沒取到」的 key 被調高的權重**永遠反映不到這裡** → swing 被低估
    # → 閘門偏鬆。**條件式的**:只有在 overrides 後端非空、且真的調高了某個
    # 當次沒取到的 key 的權重時才會發生。
    # 不在本輪修的理由:要修得正確就得在 L2 讀 overrides 後端(那是 I/O,違 §8.2
    # 「L2 不得 I/O」),或把 overrides 後的權重表由呼叫端傳進來(改 4 個生產端的
    # 介面)——兩者都超出「修這一批稽核發現」的範圍。
    # ⚠️ `calc_macro_phase` **不跑** overrides,故 `phase_support` 不受此影響。
    _swing = sum(MACRO_INDICATOR_SCORING_WEIGHTS[k] * MACRO_INDICATOR_MAX_ABS_SCORE
                 for k in _miss)
    return summed_verdict(f"綜合健康度：{_band}", total=total,
                          obtained=_got, missing=_miss,
                          missing_swing=_swing, band_of=band_of)


def action_light_present_override_keys(indicators,
                                       override_keys: Sequence[str]) -> list:
    """override 這一層**真的取到值**的那幾個 key(其餘 = 未檢查)。"""
    return [k for k in override_keys
            if isinstance((indicators or {}).get(k), dict)
            and (indicators or {}).get(k, {}).get("value") is not None]


def action_light_all_clear_support(indicators, *,
                                   override_keys: Sequence[str]) -> EvidenceSupport:
    """**只替那一句**「殖利率曲線、Sahm、VIX 均未觸發」背書 —— 規則 1(`all_of`)。

    2026-09-04 第五輪稽核 F2:這句話的支撐**必須跟燈號的支撐分開**。
    舊版把它 `combine` 進燈號的 support,於是四項裡缺任何一項,
    **連同生產端已經認證過的那半邊(景氣位階偏弱 ⇒ 🔴)一起被灰掉**。
    分開之後,消費端可以「留下警報、只扣掉這一句沒有支撐的話」。
    """
    return all_of("殖利率曲線、Sahm、VIX 均未觸發",
                  expected=override_keys,
                  obtained=action_light_present_override_keys(
                      indicators, override_keys))


def action_light_support(indicators, *, override_keys: Sequence[str],
                         triggered: Sequence[str],
                         phase_score, band_of, narrowest_band: float,
                         alarm: bool = False) -> EvidenceSupport:
    """①結論 / 卡 5 的「現在能不能買」燈的證據支撐。

    **三種宣稱,三種規則** —— 不是同一件事(2026-09-04 第五輪稽核 F2 補上第二種):

      · **override 已觸發**(🔴)→ 「這幾項裡至少有一項越線」= 存在性 → `witnessed`
        (規則 3:半套證據可以升警。那些 reason 逐項印著實際觀測值,自帶佐證。)
      · **位階偏弱造成的 🔴**(`alarm=True`,**無** override)→ 一樣是**警報**,
        依本 repo 對聚合型警報的既定政策**不受不變性閘門拘束**(見下方 ⚠️)。
      · **未觸發**(🟢/🟡)→ 「均未觸發」+「景氣位階 N/10 落在這一格」
        = 兩個全稱宣稱的聯合 → `all_of` ＋ 相位帶 ＋ **買賣燈帶**三者皆須成立。
        (相位帶那一項**刻意保留**:本輪只加條件、不放寬任何既有條件;
         買賣燈帶是本輪**新增**的條件 —— `_HOLD_SCORE_10 = 4.0` 落在相位帶
         「復甦」(3~5)的**內部**,拿相位帶去替燈號背書,在 4.0 上會放行一個
         會翻燈的狀態。)

    ⚠️ **`alarm=True` 這一支是刻意的政策豁免(over-warning),不是通則的推論
    —— 據實寫明,不得再被讀成「不對稱是後設規則自動掉出來的」**
    (2026-09-04 第五輪稽核 F3 對 `composite_support` 提出的同一個指正,
    這裡一併適用,因為兩者是**同一種**宣稱):
      · `witnessed` 之所以恆充足,靠的是**存在性宣稱對證據單調** ——
        「至少有一項越線」不會因為多取到資料而變假。
      · 但「加權分數低於 4.0」**是一個聚合量跨過切點**,對證據**不單調**:
        缺的那幾項若全部強勢,分數會升上去,燈會由 🔴 變 🟡。
      · 之所以仍然放行,是因為**方向** —— 這裡多報一次警的代價是使用者多留一點
        現金,少報一次的代價是他在衰退裡滿倉。本 repo 對聚合型警報一律選前者
        (`composite_support` 的 `alarm_bands` 是同一個選擇),**而且第五輪稽核
        明白要求「留下警報、只扣掉沒有支撐的那一句話」**。
      · 這個豁免**只給警報**:🟢/🟡 走上面的三重全稱檢查,一項都沒鬆。
      · 不變性沒有被忽略,只是換了出口:分數旁邊的相位判讀(卡 1、②依據 🌳 長期)
        仍然吃 `phase_support` 的區間不變性,那裡缺資料照樣灰。
    """
    _present_all = action_light_present_override_keys(indicators, override_keys)
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
    if alarm:
        # 政策豁免(見上方 ⚠️):警報由**已取到的那些負向觀測**作證,不上不變性閘門。
        # `witnesses` 用實際取到的 key —— 它們就是把分數壓到切點以下的那些觀測。
        # (`_got` 必非空:一個指標都沒取到時 `calc_macro_phase` 回 5.0,燈是 🟡 不是 🔴。)
        _got = tuple(indicator_keys(indicators))
        return witnessed("景氣位階偏弱（警報，政策豁免不變性閘門）",
                         witnesses=_got, obtained=_got)
    _light_band = action_light_score_support(
        indicators, phase_score, band_of=band_of, narrowest_band=narrowest_band)
    return combine(
        "無硬衰退／恐慌訊號 ＋ 景氣位階",
        action_light_all_clear_support(indicators, override_keys=override_keys),
        phase_support(indicators, phase_score),
        _light_band,
    )
