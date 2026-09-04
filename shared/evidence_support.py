"""shared/evidence_support.py — 「這個數字背後有多少證據」的**產出端契約**(L0,純函式)。

## 為什麼要有這個模組(讀之前請先讀這一段,它比任何一條斷言重要)

2026-09-04 起連續四輪獨立稽核,**每一輪都在一個新的地方**找到**同一類**缺陷:
**畫面宣稱了一個「它取到的資料撐不起來」的定論。**

    第 1 輪  卡 3:通膨軸 0 筆觀測 → 畫成「通膨受控」綠燈
    第 2 輪  卡 3:正負相抵(score 恰為 0.00)→ 也畫成「通膨受控」
    第 3 輪  卡 1/卡 5:完全斷線 → 「擴張 5.0/10、股優於債」+ 一句
             「殖利率曲線、Sahm、VIX **均未觸發**」(那四項一個都沒取到)
    第 4 輪  卡 3(**又是它**):通膨軸只剩 1 筆觀測 → score = ±1.00(最大強度,
             與「三項一致」在畫面上**逐位元組相同**)

第 3 輪已經寫對了通則,卻**只套用在它本來就要改的那三張卡上** —— 於是第 4 輪
在它自己宣稱「查過、合規」的卡 3 上又找到同一類。

**根因不在任何一張卡,在產出端**:`calc_macro_phase` / `calc_growth_inflation_axis`
/ `macro_action_light` / `calculate_composite_score` 這幾支**只回傳數字,不回傳
「這個數字背後有多少證據」**。於是每一個消費端都得自己手推一道閘門,而每一道
手推的閘門都錯過或漏掉了一種形態。

本模組把那件事收成**產出端的契約**:**產出端連同數字一起回報 `EvidenceSupport`,
消費端只讀 `.sufficient`,不得自己再推一次。**

## 通則(一條,涵蓋客戶列的三條)

> **一個定論只有在「**沒取到的那些證據，不論實際是什麼值，都不會改變它**」時才可以宣告。**

三條規則是它的三個形狀:

1. **點名輸入(`all_of`)** —— 宣稱裡點名了特定輸入(「殖利率曲線、Sahm、VIX
   均未觸發」),**任何一個沒取到就足以證偽這句話** ⇒ 要全部在。
2. **聚合(`net_margin` / `weighted_verdict` / `summed_verdict`)** —— 定論建立在
   聚合量上 ⇒ **沒取到的那些量的任何一種實現,都必須落在同一個結論帶**。
3. **不對稱(`witnessed`)** —— **這一條不是第三道閘門,它是前兩條的推論**:
   「這幾項裡**至少有一項**越線了」是一個**存在性**宣稱,而且**對證據單調** ——
   沒取到的資料只可能**再多一個**觸發,不可能把已經觀測到的那個觸發拿掉。
   所以它恆為「充足」。反過來「**都**沒越線」是全稱宣稱,要走規則 1。
   ⇒ **半套證據可以升警、不可以解除警報**,是這條推論的結果,不是一條額外的規定。

⚠️ **消費端不得自己寫 `if 有警報: 照出 else: 檢查充足性`** —— 那正是前四輪
每一次都寫錯的那一步。消費端要做的是:**問產出端「我正要顯示的這一句,它的
support 是什麼」**,然後只讀 `.sufficient`。

⚠️ 本模組**刻意不含任何領域知識**(不知道什麼是 PMI、什麼是相位帶)。
領域表(權重、相關族、相位邊界)與各產出端的 builder 住在
`services/macro/evidence.py`(L2)。本模組是 L0:純資料結構 + 純判定,零 import。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class EvidenceSupport:
    """一個定論的「證據支撐」。**`sufficient` 只在本模組的建構子裡算,別處不得重算。**

    Attributes
    ----------
    claim
        這個 support 在替**哪一句話**背書(給 note 用;不同的句子要不同的 support)。
    rule
        用了哪一條規則:`"all_of"` / `"net_margin"` / `"weighted_verdict"` /
        `"summed_verdict"` / `"witnessed"` / `"combined"`。
    obtained / missing
        實際取到 / 沒取到的輸入名(排序後的 tuple,可直接印給使用者)。
    sufficient
        **唯一的判定結果。** 消費端只讀這一個欄位。
    reason
        不充足的原因(充足時為空字串)。**寫給使用者看的中文**,消費端可直接印。
    detail
        規則各自的中間量(權重、邊際、可及區間…),供 note 引用。**不參與判定。**
    """

    claim: str
    rule: str
    obtained: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    sufficient: bool = False
    reason: str = ""
    detail: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 不變量:充足就不該有原因,不充足就必須說得出原因(§1 不靜默)。
        if self.sufficient and self.reason:
            raise ValueError(f"sufficient=True 卻帶著 reason={self.reason!r}")
        if not self.sufficient and not self.reason:
            raise ValueError(f"sufficient=False 卻沒有 reason(claim={self.claim!r})")


def is_sufficient(support) -> bool:
    """證據支撐夠不夠 —— **全站唯一被允許的判斷式**(L0 SSOT)。

    2026-09-04 第四輪稽核把它收成一個函式(當時住在 `ui/tab1_macro.py`),
    第五輪把它搬到 L0:當時的 AST 守衛**只掃 `ui/tab1_macro.py` 一個檔**,
    於是 `ui/helpers/macro/beginner_view.py` 自己讀 `.sufficient` 那一處
    (它還刻意在 `support is None` 上與 SSOT 走相反的分支)整個在守衛的射程外。
    判斷式住在 L0,守衛才掃得到所有消費端。

    ⚠️ **只讀 `.sufficient`**:消費端不得自己去看 `obtained` / `missing` 的
    長度再下判斷 —— 那就是把規則搬回消費端,也就是前四輪要根除的那個類。
    ⚠️ **`support is None` → False(不足)**:沒有支撐可讀時不下定論(§1)。
    """
    return bool(support is not None and getattr(support, "sufficient", False))


def _sorted(names) -> tuple[str, ...]:
    return tuple(sorted(str(n) for n in (names or ())))


# ══════════════════════════════════════════════════════════════════════
# 規則 1 —— 點名了特定輸入的宣稱
# ══════════════════════════════════════════════════════════════════════
def all_of(claim: str, *, expected: Sequence[str],
           obtained: Sequence[str]) -> EvidenceSupport:
    """「這句話點名了 expected 這幾個輸入」⇒ **少一個就不能這樣講**。

    典型:卡 5 / ①結論 的「殖利率曲線、Sahm、VIX **均未觸發**」——
    完全斷線實測時那四項一個都沒取到,畫面照樣宣稱四項都檢查過。
    """
    _exp = _sorted(expected)
    _got = tuple(k for k in _exp if k in set(obtained or ()))
    _miss = tuple(k for k in _exp if k not in set(_got))
    return EvidenceSupport(
        claim=claim, rule="all_of", obtained=_got, missing=_miss,
        sufficient=not _miss,
        reason=("" if not _miss else
                f"這句話點名了 {len(_exp)} 項輸入，實際只取到 {len(_got)} 項"
                f"（缺 {'／'.join(_miss)}，未檢查）"),
        detail={"n_expected": len(_exp), "n_obtained": len(_got)},
    )


# ══════════════════════════════════════════════════════════════════════
# 規則 3 —— 存在性宣稱(對證據單調 ⇒ 半套證據可以升警)
# ══════════════════════════════════════════════════════════════════════
def witnessed(claim: str, *, witnesses: Sequence[str],
              obtained: Sequence[str] = ()) -> EvidenceSupport:
    """「這幾項裡**至少有一項**越線了」—— 由 `witnesses` 這些**實際觀測**作證。

    **對證據單調**:沒取到的資料只可能再多一個觸發,不可能把已觀測到的觸發拿掉,
    所以只要 `witnesses` 非空就恆為充足 —— 這就是「半套證據可以升警」。
    `witnesses` 為空表示沒有任何觀測作證,那不是警報、是無話可說。
    """
    _w = _sorted(witnesses)
    return EvidenceSupport(
        claim=claim, rule="witnessed", obtained=_sorted(obtained or _w),
        missing=(), sufficient=bool(_w),
        reason=("" if _w else "沒有任何實際觀測越過門檻，這不是警報"),
        detail={"witnesses": _w},
    )


# ══════════════════════════════════════════════════════════════════════
# 規則 2-a —— 不加權的正負號聚合(成長 / 通膨雙軸)
# ══════════════════════════════════════════════════════════════════════
def net_margin(claim: str, *, signals: Mapping[str, float],
               expected: Sequence[str]) -> EvidenceSupport:
    """平均 ±1 訊號的方向宣稱:**淨邊際必須大於沒取到的筆數**。

    推導(不是校準):方向 = `sign(Σs / n)`。沒取到的 `m` 筆,每一筆若都取到、
    且**全部反向**,會讓 `Σs` 減少 `m`。故方向對「沒取到的資料」不變 ⟺

        |Σs| > m        (m = 沒取到的筆數)

    這一條同時吃掉三種既有形態,**不必再各寫一道閘門**:
      · `n = 0`(零觀測)   → Σs = 0、m = 全部 → 0 > m 為假 ⇒ 不充足
      · **打平**(Σs = 0)  → 0 > m 為假(m ≥ 0)⇒ 不充足
      · **n = 1**(第 4 輪 R4-F1)→ |Σs| = 1,通膨軸 m = 2 ⇒ 1 > 2 為假 ⇒ 不充足
        (舊閘門只看「方向明不明確」,n=1 給出 ±1.00 —— **最大強度**,
         與三項一致在畫面上逐位元組相同,照樣過關。)
    而**真的撐得住**的情形照樣通過:CPI 高 + PPI 高、Fed Rate 缺 → |Σs| = 2 > 1 ⇒ 充足
    (就算缺的那一項反向,2-1 仍指同一邊)。
    """
    _exp = _sorted(expected)
    _got = tuple(k for k in _exp if k in signals)
    _miss = tuple(k for k in _exp if k not in signals)
    _net = sum(float(signals[k]) for k in _got)
    _ok = abs(_net) > len(_miss)
    if _ok:
        _reason = ""
    elif not _got:
        _reason = f"{len(_exp)} 項輸入一項都沒取到，方向無從判定"
    elif abs(_net) < 1e-9:
        # ⚠️ 「重新載入不會改變」**只有在這一軸沒有缺項時才是真的**。
        # 有缺項時補上任何一筆就會打破平手 —— 把它講成「不是缺資料」是誤導。
        _reason = ((f"{len(_got)} 項觀測正負相抵（淨邊際 0），方向不明 —— "
                    f"不是缺資料，重新載入不會改變")
                   if not _miss else
                   (f"{len(_got)} 項觀測正負相抵（淨邊際 0），另有 {len(_miss)} 項"
                    f"沒取到（{'／'.join(_miss)}）—— 方向無從判定"))
    else:
        _reason = (f"淨邊際只有 {abs(_net):g}，而還有 {len(_miss)} 項沒取到"
                   f"（{'／'.join(_miss)}）—— 那幾項若反向就足以翻掉方向")
    return EvidenceSupport(
        claim=claim, rule="net_margin", obtained=_got, missing=_miss,
        sufficient=_ok, reason=_reason,
        detail={"net": _net, "n_obtained": len(_got), "n_missing": len(_miss)},
    )


# ══════════════════════════════════════════════════════════════════════
# 規則 2-b —— 正規化加權分數(景氣位階 0~10)
# ══════════════════════════════════════════════════════════════════════
def weighted_verdict(claim: str, *, score: float,
                     obtained: Sequence[str], missing: Sequence[str],
                     obtained_weight: float, missing_weight: float,
                     family_weights: Mapping[str, float],
                     band_of: Callable[[float], str],
                     scale: float, weight_per_band: float,
                     round_to: "int | None" = None,
                     score_tolerance: float = 0.0) -> EvidenceSupport:
    """`norm = (earned + T) / (2T) * scale` 這種**分母只由取到的指標構成**的分數。

    兩個獨立的必要條件,**都要過**:

    **(A) 對「沒取到的證據」不變** —— 這是通則的字面實作。設沒取到的權重為 `M`,
    它們的 earned 貢獻 `Σs ∈ [-M, +M]`(生產端 `s` 被 clamp 在 `[-w, w]`),則

        norm_min = norm · T / (T + M)
        norm_max = (norm · T + scale · M) / (T + M)

    要求 `band(norm_min) == band(norm) == band(norm_max)`。
    `T == 0` ⇒ 整個 0~scale 都可及 ⇒ 恆不充足(這就是「完全斷線畫成擴張 5.0」)。

    **(B) 不是由單一**相關族**決定的** —— 一族(權重 `W_F`)由全負翻成全正,
    會讓 norm 移動 `scale · W_F / T`。要求它推不過**最窄的那一條結論帶**:

        scale · W_F / T < narrowest_band   ⟺   T > (scale / narrowest_band) · W_F

    `weight_per_band = scale / narrowest_band`。
    ⚠️ **「族」不是「單一指標」** —— 第 4 輪 R4-F6 實測推翻了舊推導的前提
    (舊的寫「單一指標最大權重是 2」):`YIELD_10Y2Y` 與 `YIELD_10Y3M` 是**同一條
    殖利率曲線的兩個讀數**,權重 2+2 = **4**;`DXY` 與三條美元交叉匯率同理也是 4。
    族表是 `services/macro/evidence.py::MACRO_CORRELATED_FAMILIES`。

    **(C) 顯示端的四捨五入 —— 兩個獨立的誤差源,兩個都要吃掉**
    (2026-09-04 第五輪稽核 F1;不補這一段,(A) 就只是「近似不變」,而模組
    docstring 把契約寫成絕對的、消費端又只讀 `.sufficient`,看不出它是近似)。

      · **輸入本身已經被 round 過** —— 生產端傳進來的 `score` 是
        `round(norm, k)` 的**顯示值**,真值落在 `[score-tol, score+tol]`
        (`tol = 0.5 · 10^-k`)。拿顯示值當真值去推區間,區間本身就偏掉半格。
        ⇒ `score_tolerance=` 把它加寬回去(下界用 `score-tol`、上界用 `score+tol`,
        兩者對 `norm` 都單調遞增)。
      · **每一種實現也會再被 round 一次** —— 使用者看到的是
        `round(norm_real, k)`,不是 `norm_real`。落在同一條帶裡的
        `norm_real` 有可能 round 到帶外(反之亦然)。
        ⇒ `round_to=` 讓兩個界**用生產端同一個方式 round 之後**才去問 `band_of`。
        (`round` 單調不遞減 ⇒ 最小/最大顯示值 = 最小/最大真值各自 round 的結果,
         所以只要 round 兩個端點就夠,不必掃中間。)

    兩個誤差各 ±0.5·10^-k,**在帶邊界上會疊起來**。實證(相位帶邊界 3/5/8):
    28 項只缺 `UNEMPLOYMENT`(權重 0.5)一項,顯示 `4.9 復甦`、
    `reachable_high` 算出 4.99 判「充足」,而那一項若取到 +0.5 → `5.0 擴張`,
    一句「復甦期:最高勝率買點!逐步加碼」直接翻成「股優於債」。
    兩項都預設關閉(`round_to=None` / `score_tolerance=0.0`)——
    **不 round 的生產端不該被迫宣告一個它沒有的誤差**;有 round 的生產端
    (`services/macro/evidence.py::_scored_verdict_support`)必須兩個都傳。
    """
    _got, _miss = _sorted(obtained), _sorted(missing)
    _T, _M = float(obtained_weight), float(missing_weight)
    _tol = abs(float(score_tolerance))
    if _T <= 0:
        _lo, _hi = 0.0, float(scale)
    else:
        # `score` 是**已經四捨五入過的顯示值**,真值落在 [score-tol, score+tol]。
        # 兩個界都對 `norm` 單調遞增 ⇒ 下界取 `score-tol`、上界取 `score+tol`。
        _lo = (score - _tol) * _T / (_T + _M)
        _hi = ((score + _tol) * _T + scale * _M) / (_T + _M)
    # 生產端在四捨五入前先 clamp,這裡照做(順序必須一致)。
    _lo = min(max(_lo, 0.0), float(scale))
    _hi = min(max(_hi, 0.0), float(scale))
    if round_to is not None:
        # `round` 單調不遞減 ⇒ 最小/最大**顯示值** = 最小/最大真值各自 round 後的值。
        _lo = round(_lo, round_to)
        _hi = round(_hi, round_to)
    _band = band_of(score)
    _invariant = (band_of(_lo) == _band == band_of(_hi))
    _max_fam = max(family_weights.values()) if family_weights else 0.0
    _required = weight_per_band * _max_fam
    # `family_weights` 為空 ⟺ 一個指標都沒取到 ⟺ `_T == 0` —— 那種情形上面的
    # 不變性檢查已經報過了(而且報得更準)。這裡不再多吐一句「單一族佔 0」的
    # 噪音;**兩條規則各自負責自己看得見的東西**。
    _dominance_ok = (_T > _required) if family_weights else True
    _reasons: list[str] = []
    if not _invariant:
        _reasons.append(
            f"還有 {_M:g} 權重沒取到（{len(_miss)} 項）；那些指標的任一種實現"
            f"都會讓分數落在 {_lo:.1f}～{_hi:.1f}，橫跨"
            f"「{band_of(_lo)}」到「{band_of(_hi)}」，不是同一個判讀"
            if _T > 0 else
            "一個計分指標都沒取到，分數 5.0 是分母為零時的預設值，不是量測")
    if not _dominance_ok:
        _fam = max(family_weights, key=lambda k: family_weights[k]) if family_weights else "—"
        _reasons.append(
            f"取到的權重合計只有 {_T:g}，而單一相關族「{_fam}」就佔 {_max_fam:g}"
            f"（需 > {_required:g}）—— 那一族翻向就足以把判讀推過一整條分界")
    return EvidenceSupport(
        claim=claim, rule="weighted_verdict", obtained=_got, missing=_miss,
        sufficient=_invariant and _dominance_ok,
        reason="；".join(_reasons),
        detail={"obtained_weight": _T, "missing_weight": _M,
                "reachable_low": round(_lo, 2), "reachable_high": round(_hi, 2),
                "score_tolerance": _tol, "round_to": round_to,
                "band": _band, "max_family_weight": _max_fam,
                "required_weight": _required},
    )


# ══════════════════════════════════════════════════════════════════════
# 規則 2-c —— 未正規化的加權**總和**(綜合健康度多空淨分)
# ══════════════════════════════════════════════════════════════════════
def summed_verdict(claim: str, *, total: float,
                   obtained: Sequence[str], missing: Sequence[str],
                   missing_swing: float,
                   band_of: Callable[[float], str]) -> EvidenceSupport:
    """`total = Σ score×weight` 這種**沒有分母**的總和。

    缺值在這裡是被當成 **0** 加進去的(`calculate_composite_score` 的 docstring
    自陳「缺值/NaN/型別錯誤一律以 0 處理(**fillna(0) 等價**)」)—— 也就是
    「沒取到」被靜默地當成「中性」,而 §1 明文禁止 `fillna(0)`。

    判定沿用同一條通則:沒取到的那些指標,其貢獻絕對值上界為 `missing_swing`,
    故 `total ∈ [total - swing, total + swing]` 都可能;要求三點同帶。
    """
    _got, _miss = _sorted(obtained), _sorted(missing)
    _sw = abs(float(missing_swing))
    _lo, _hi = total - _sw, total + _sw
    _band = band_of(total)
    _ok = (band_of(_lo) == _band == band_of(_hi))
    return EvidenceSupport(
        claim=claim, rule="summed_verdict", obtained=_got, missing=_miss,
        sufficient=_ok,
        reason=("" if _ok else
                f"總分 {total:+.1f} 只算了取到的 {len(_got)} 項；沒取到的 {len(_miss)} 項"
                f"是被當成 0 加進去的，把它們的可能值算進來後總分落在 "
                f"{_lo:+.1f}～{_hi:+.1f}，橫跨「{band_of(_lo)}」到「{band_of(_hi)}」"),
        detail={"total": total, "missing_swing": _sw,
                "reachable_low": round(_lo, 2), "reachable_high": round(_hi, 2),
                "band": _band},
    )


# ══════════════════════════════════════════════════════════════════════
# 聯合宣稱
# ══════════════════════════════════════════════════════════════════════
def combine(claim: str, *supports: EvidenceSupport) -> EvidenceSupport:
    """一句話同時建立在多個 support 上(例:卡 5 綠燈 = 四項輸入全在 **且** 位階站得住)。

    **全部充足才算充足**;原因串接,使用者才知道是哪一半不夠。
    """
    _subs = [s for s in supports if isinstance(s, EvidenceSupport)]
    _ok = bool(_subs) and all(s.sufficient for s in _subs)
    _obt: list[str] = []
    _mis: list[str] = []
    for s in _subs:
        _obt.extend(s.obtained)
        _mis.extend(s.missing)
    return EvidenceSupport(
        claim=claim, rule="combined",
        obtained=_sorted(set(_obt)), missing=_sorted(set(_mis)),
        sufficient=_ok,
        reason=("" if _ok else
                "；".join(s.reason for s in _subs if s.reason) or "沒有任何證據支撐"),
        detail={"parts": tuple(s.rule for s in _subs)},
    )
