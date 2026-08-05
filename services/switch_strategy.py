"""services/switch_strategy.py — 換標決策引擎(v19.423)。純函式,零外部 IO
(僅 §1 要求的 stderr 稽核 log;無 HTTP / 無 streamlit / 無檔案)。

user 2026-07-28 spec:健康度評分 → 燈號診斷 → 一對一替換匹配 → 大盤 regime filter。

設計決定(user 拍板):
- 獨立「**換標策略分**」(0-100),**不混 4D 健康度**(避免又一組打架的評等,§2.1)。
- 選股/主動能力訊號用 **vs 大盤%**(對大盤超額),**非**本專案「Alpha%」(=真實收益%,§4.1)。
- **資料不足**(Sharpe 或 1Y 含息缺)→ 灰燈,不硬算分數(§1,同 4D 資料不足守衛哲學)。
- **加分項(MaxDD / vs大盤)缺值 → 從分母移除後重正規化**,不再讓「缺資料」與
  「表現很差」在同一個分數上無法區分(§1 缺值偽裝成壞值;詳見 `switch_score` docstring)。
- **「衡量」與「行動」分離(本次修正)**:重正規化只修好「衡量」那一半 —— 分數語意變成
  「**有證據的維度**你拿了幾成」是誠實的,但它同時被拿去跨「加碼」門檻,結果是
  **缺資料反而拿到最強的買進訊號**(65/65 → 100 分 → 🟢「可定期定額加碼」)。
  因此綠燈另設**悲觀下界**閘門(見 `_coverage_blocks_green`):缺的維度全以 0 計、
  分母不縮,仍 ≥ `SWITCH_GREEN_SCORE` 才給綠燈,否則降 🟡 觀望。
- 替換為**同資產類別**「一對一」(user spec:同類換品質更好者);輪動則是**跨類別**,兩者不同。

常數全走 `shared.switch_thresholds` SSOT(§3.3)。
"""
from __future__ import annotations

import sys as _sys

from shared.converters import safe_num as _num
from shared.switch_thresholds import (
    SWITCH_ALPHA_POINTS,
    SWITCH_GREEN_SCORE,
    SWITCH_MAXDD_TIERS,
    SWITCH_REGIME_NEG_SHARPE_RATIO,
    SWITCH_REPLACE_MAX_EXPENSE_PCT,
    SWITCH_REPLACE_MIN_SHARPE,
    SWITCH_REPLACE_W_RETURN,
    SWITCH_REPLACE_W_SHARPE,
    SWITCH_REPLACE_W_SORTINO,
    SWITCH_SHARPE_TIERS,
    SWITCH_TR_TIERS,
)

GRAY = "⬜ 灰燈(資料不足)"
RED = "🔴 紅燈(賣出/平轉)"
YELLOW = "🟡 黃燈(觀望/停加碼)"
GREEN = "🟢 綠燈(續抱/加碼)"


def _tier(val: float, tiers: list) -> int:
    """值 ≥ 下限的第一個 tier 得分;皆不中 → 0。"""
    for _cutoff, _pts in tiers:
        if val >= _cutoff:
            return _pts
    return 0


def _tier_max(tiers: list) -> int:
    """該指標的滿分 = tiers 中最高得分。權重一律**從 SSOT 推導**,不在本檔另寫死
    35/30/20 等字面值(§3.3;常數 SSOT 為 `shared/switch_thresholds.py`)。"""
    return max((int(_p) for _c, _p in (tiers or [])), default=0)


def _score_total() -> int:
    """滿覆蓋時的分母 = 四個維度滿分之和(= 35+30+20+15 = 100,但由 SSOT 推)。"""
    return (_tier_max(SWITCH_TR_TIERS) + _tier_max(SWITCH_SHARPE_TIERS)
            + _tier_max(SWITCH_MAXDD_TIERS) + int(SWITCH_ALPHA_POINTS))


def switch_score(tr1y_pct, sharpe, maxdd_pct, vs_market_pct, *,
                 coverage_out: "dict | None" = None) -> "int | None":
    """換標策略分 0-100(1Y含息35 + Sharpe30 + MaxDD20 + vs大盤15)。

    §1:1Y 含息 或 Sharpe 缺 → None(核心維度,資料不足不硬算)。

    **缺值不得偽裝成壞值(本次修正)**
    ---------------------------------
    原碼分母固定 100:MaxDD 缺 → 該項 +0 分,與「MaxDD = −35% 所以拿 0 分」在畫面上
    **完全無法區分**。`services/fund_service.calc_metrics` 把 max_drawdown 的樣本門檻
    從「無」提高到 `MIN_OBS_MAX_DRAWDOWN`(125 交易日)之後,**每一檔短歷史基金的
    換標分憑空少 20 分** —— 這正是 §1 點名的「缺值偽裝成壞值」。

    修法:**分母只計入有資料的維度**,再線性放回 0-100 —
        score = round( earned / available_max × total_max )
    語意從「滿分 100 你拿幾分」改為「**有證據的部分**你拿了幾成」。
    - 滿覆蓋(四維皆有值)時 `available_max == total_max`,直接回原始加總,
      **位元等價**,既有行為零改變(可對照 test_switch_strategy 前三例)。
    - `maxdd_pct` 缺 → 分母 80;`vs_market_pct` 缺 → 分母 85;兩者皆缺 → 分母 65。
    - `vs_market_pct` **有值但 ≤ 0** 屬「真的沒有超額」→ 計 0 分且**留在分母**
      (跟 MaxDD tier 落底同語意),不與缺值混為一談。

    **為什麼不選「缺值 → verdict 資料不足」(§1 最嚴解)**:本函式的資料契約已由 user
    2026-07-28 spec 拍板 —— TR/Sharpe 為**核心**(缺 → None),MaxDD/vs大盤 為**加分項**。
    把加分項升級成硬閘門是改 spec 不是修 bug(§-1「沒具體需求不要動」),而且會讓所有
    NAV < 126 點的基金整欄換標判讀消失。重正規化同樣消滅「缺 = 壞」的錯誤訊號,
    但保留可用性;殘留風險(部分覆蓋的分數可比性較弱)以 `coverage_out` 顯式揭露。

    ⚠️ **本分數是「衡量」不是「行動」**:部分覆蓋時 `100` 的意思是「有證據的 65 分裡
    你拿滿 65」,**不是**「四維全好」。行動面(綠燈/加碼)另由 `switch_signal` 的悲觀
    下界閘門把關(`_coverage_blocks_green`),避免缺資料換到更強的買進訊號。呼叫端
    **必須**把 `coverage_out` 一起帶去 `switch_signal(coverage=...)` 與顯示層
    (`switch_coverage_label`),否則旗標形同虛設。

    Parameters
    ----------
    coverage_out : dict | None
        §1「填補須帶旗標」的側車容器(opt-in,對齊 v19.270 D8 #8
        `calculate_composite_score(provenance_out=)` 既有 pattern)。傳 dict 進來即
        就地填入 `earned` / `available` / `total` / `coverage_pct` / `missing` /
        `rescaled`;不傳則行為與舊版簽名完全相同。
    """
    _cov = {
        "earned": None, "available": None, "total": _score_total(),
        "coverage_pct": None, "missing": [], "rescaled": False,
        "reason": None,
    }
    _tr = _num(tr1y_pct)
    _sh = _num(sharpe)
    if _tr is None or _sh is None:
        _cov["missing"] = ([] if _tr is not None else ["1Y 含息 %"]) + \
                          ([] if _sh is not None else ["Sharpe 1Y"])
        _cov["reason"] = "核心維度缺值 → 不評分(§1)"
        if coverage_out is not None:
            coverage_out.update(_cov)
        return None

    _earned = _tier(_tr, SWITCH_TR_TIERS) + _tier(_sh, SWITCH_SHARPE_TIERS)
    _avail = _tier_max(SWITCH_TR_TIERS) + _tier_max(SWITCH_SHARPE_TIERS)
    _missing = []

    _dd = _num(maxdd_pct)
    if _dd is not None:
        _earned += _tier(_dd, SWITCH_MAXDD_TIERS)
        _avail += _tier_max(SWITCH_MAXDD_TIERS)
    else:
        _missing.append("Max DD %")

    _vm = _num(vs_market_pct)
    if _vm is not None:
        if _vm > 0:
            _earned += int(SWITCH_ALPHA_POINTS)
        _avail += int(SWITCH_ALPHA_POINTS)
    else:
        _missing.append("vs 大盤%")

    _total = _score_total()
    # 滿覆蓋 → 原始加總(整數,零浮點噪音);部分覆蓋 → 依可用權重放回 0-total
    _score = _earned if _avail == _total else int(round(_earned / _avail * _total))

    _cov.update({
        "earned": _earned, "available": _avail, "total": _total,
        "coverage_pct": round(_avail / _total * 100.0, 1),
        "missing": _missing, "rescaled": _avail != _total,
        "reason": (None if not _missing else
                   f"缺 {'/'.join(_missing)} → 分母由 {_total} 收斂為 {_avail} 後放回"
                   f"0-{_total}(缺值不計為壞值,§1)"),
    })
    # §1 第 2 項:任何填補 / 分母調整都要**寫入 log**(前一輪只做到「顯式呼叫」)。
    # 只在真的重正規化時印一行,滿覆蓋(絕大多數列)不產生噪音。
    if _cov["rescaled"]:
        print(f"[switch_strategy] 換標策略分部分覆蓋:缺 {'/'.join(_missing)} → "
              f"分母 {_total}→{_avail},earned={_earned} → score={_score}"
              f"(悲觀下界 {_earned} vs 綠燈門檻 {SWITCH_GREEN_SCORE})", file=_sys.stderr)
    # ⚠️ 這一行曾經漏掉,整組覆蓋率修正因此**完全失效**:`_cov` 算得再對,沒回寫
    # 呼叫端拿到的仍是空 dict → `switch_signal` 的 `_coverage_blocks_green({})`
    # 讀不到 `rescaled` → 回 False → 綠燈照給,缺資料的檔仍拿到「可加碼」建議。
    # 早期 return 路徑(核心維缺值,:119-120)有寫、主路徑漏寫 —— 單邊接線是最難用
    # 肉眼發現的失效模式(程式碼看起來完整、log 也印得出來,只是沒傳出去)。
    # 由 tests/test_switch_strategy.py::test_score_optional_missing_ok 等 14 條釘住。
    if coverage_out is not None:
        coverage_out.update(_cov)
    return _score


def _coverage_blocks_green(coverage) -> bool:
    """部分覆蓋時,綠燈該不該降級 —— **悲觀下界**判準(§1「缺資料不得給更強的買進訊號」)。

    問題:`switch_score` 的重正規化讓分數語意變成「有證據的維度你拿了幾成」,對「衡量」
    誠實,但拿去跨「加碼」門檻就翻車 ——
    1Y含息 8% + Sharpe 1.0 + MaxDD/vs大盤**全缺** → 65/65 → **100 分 → 🟢
    「續抱,可作核心資產或定期定額加碼」**,比同樣報酬但 MaxDD 真的是 −40% 的檔(65 分,🟡)
    還積極。而 MaxDD 為 None 的成因正是 `MIN_OBS_MAX_DRAWDOWN`(125 交易日)沒過 ——
    新發行 / 保單子網域被封鎖只抓到短序列,**風險最不明的那一批**。

    判準:把缺的維度**全部以 0 計、分母不縮**(= 悲觀下界 `earned`),仍 ≥
    `SWITCH_GREEN_SCORE` → 綠燈成立(缺的那幾分再怎麼補都翻不掉結論,例如
    35+30+20 = 85 只缺 vs大盤 15 分);否則降 🟡 **觀望**。

    為什麼是 🟡 不是 ⬜:核心兩維(1Y 含息 / Sharpe)是**有真實證據**的,丟成灰燈
    (「勿據此買賣」)等於把手上的資料扔掉,且會讓 Tab3 持倉健診(不供 vs大盤%)整欄
    變灰。🟡 的處置文字「暫停定期定額加碼,觀察下季 **vs 大盤超額與下檔保護**」正好
    就是缺的那兩維,語意完全對得上。

    `coverage` 為 None(呼叫端沒帶側車)→ 回 False = 沿用舊行為;production 呼叫端
    (`ui/helpers/fund_grp_health/unified.compute_switch_columns`)一律要帶,
    由 `tests/test_switch_strategy.py` 的行為測試釘住。
    """
    if not isinstance(coverage, dict) or not coverage.get("rescaled"):
        return False
    _earned = coverage.get("earned")
    return _earned is None or int(_earned) < SWITCH_GREEN_SCORE


def switch_signal(tr1y_pct, sharpe, eat_status, score, *, coverage=None) -> str:
    """紅/黃/綠/灰燈。優先序:紅(嚴重吃本金) > 灰(資料不足) > 紅(含息<0且Sharpe<0) > 綠 > 黃。

    - 🔴:吃本金含「嚴重」(**不需分數** —— 明確壞資料再少也要示警,§1;稽核 Finding 1 修:
      不被灰燈蓋掉),或(1Y含息 < 0 且 Sharpe < 0)。
    - ⬜:分 None 或 Sharpe/含息 缺(且非嚴重)。
    - 🟢:分 ≥ GREEN 且 吃本金「健康」**且通過覆蓋率悲觀下界**(見 `_coverage_blocks_green`)。
    - 🟡:其餘一律觀望(非紅/綠/灰;明確黃燈條件皆為「非綠」子集,故不另設門檻)。

    Parameters
    ----------
    coverage : dict | None
        `switch_score(coverage_out=)` 就地填好的側車 dict。**缺 MaxDD / vs大盤 時必傳**,
        否則綠燈閘門失效(= 缺資料換到 🟢 加碼建議,§1 違憲)。
    """
    _eat = str(eat_status or "")
    if "嚴重" in _eat:
        return RED
    _tr = _num(tr1y_pct)
    _sh = _num(sharpe)
    if score is None or _tr is None or _sh is None:
        return GRAY
    if _tr < 0 and _sh < 0:
        return RED
    if score >= SWITCH_GREEN_SCORE and "健康" in _eat:
        if _coverage_blocks_green(coverage):
            # §1 第 2 項:降級必須留痕(這是「原本會給加碼建議」的高訊號事件,不是常態噪音)
            _miss = "/".join((coverage or {}).get("missing") or [])
            _lb = (coverage or {}).get("earned")
            print(f"[switch_strategy] 綠燈降黃:分數 {score} ≥ {SWITCH_GREEN_SCORE} 但覆蓋不全"
                  f"(缺 {_miss},悲觀下界 {_lb} < {SWITCH_GREEN_SCORE})→ 不給加碼訊號(§1)",
                  file=_sys.stderr)
            return YELLOW
        return GREEN
    return YELLOW


def switch_coverage_label(coverage, score=None) -> str:
    """側車 dict → 大表可直接顯示的覆蓋率旗標字串(§1 第 3 項「輸出帶旗標」)。

    前一輪 `coverage_out` 全站 **0 consumer** —— docstring 寫「以 coverage_out 顯式揭露」
    卻沒有任何揭露管道,使用者看到 100 分完全不知道分母被收斂成 65。本函式是那條管道的
    格式化端(渲染由 L3 大表新增「策略分覆蓋」欄)。

    - 未評分(核心維度缺 / 無側車)→ ``⬜ 未評分``
    - 全覆蓋 → ``✅ 100/100``
    - 部分覆蓋 → ``⚠️ 85/100(缺 vs 大盤%)``
    - 部分覆蓋且下界不足 → ``⚠️ 65/100(缺 Max DD %、vs 大盤%)·不給綠燈``
    """
    if not isinstance(coverage, dict) or score is None:
        return "⬜ 未評分"
    _av, _to = coverage.get("available"), coverage.get("total")
    if _av is None or _to is None:
        return "⬜ 未評分"
    if not coverage.get("rescaled"):
        return f"✅ {_av}/{_to}"
    _ms = "、".join(coverage.get("missing") or []) or "?"
    _gate = "·不給綠燈" if _coverage_blocks_green(coverage) else ""
    return f"⚠️ {_av}/{_to}(缺 {_ms}){_gate}"


def _is_healthy_candidate(c: dict) -> bool:
    """替換候選健康門檻:綠燈 或 吃本金健康 + Sharpe≥MIN + 1Y含息>0 + 費用率<MAX。"""
    _sh = _num(c.get("Sharpe 1Y"))
    _tr = _num(c.get("1Y 含息 %"))
    _exp = _num(c.get("費用率 %"))
    _eat = str(c.get("吃本金燈號 (1Y · MK)") or "")
    _sig = str(c.get("策略燈號") or "")
    _healthy = ("健康" in _eat) or (GREEN in _sig) or ("🟢" in _sig)
    return bool(
        _healthy
        and _sh is not None and _sh >= SWITCH_REPLACE_MIN_SHARPE
        and _tr is not None and _tr > 0
        and (_exp is None or _exp < SWITCH_REPLACE_MAX_EXPENSE_PCT)
    )


def replacement_candidate(sell_category, candidates) -> "dict | None":
    """紅燈檔的「一對一替換」:**同資產類別**內 argmax(Sharpe·0.4 + 1Y含息·0.4 + Sortino·0.2)。

    候選須通過 `_is_healthy_candidate`(綠燈/健康 + Sharpe≥0.5 + 總報酬>0 + 費用率<1.5%)。
    無同類健康候選 → None(§1 不硬湊「換到更爛的」)。candidates 每檔含
    code/基金名/基金類別/Sharpe 1Y/1Y 含息 %/Sortino/費用率 %/策略燈號/吃本金燈號 (1Y · MK)。
    """
    _cat = str(sell_category or "").strip()
    if not _cat:
        return None
    _pool = [c for c in (candidates or [])
             if str(c.get("基金類別") or "").strip() == _cat and _is_healthy_candidate(c)]
    if not _pool:
        return None

    def _rank(c: dict) -> float:
        return ((_num(c.get("Sharpe 1Y")) or 0.0) * SWITCH_REPLACE_W_SHARPE
                + (_num(c.get("1Y 含息 %")) or 0.0) * SWITCH_REPLACE_W_RETURN
                + (_num(c.get("Sortino")) or 0.0) * SWITCH_REPLACE_W_SORTINO)

    return max(_pool, key=_rank)


def market_regime_alert(rows, category=None) -> dict:
    """大盤/同類 regime filter:同池 Sharpe 為負的比例 ≥ 80% → 系統性風險,暫緩換標。

    category 指定 → 只看該資產類別;否則看整池。回 {systemic_risk, neg_pct, n}。
    無有效 Sharpe → systemic_risk False(不誤判)。
    """
    _cat = str(category or "").strip()
    _sh = []
    for r in (rows or []):
        if _cat and str(r.get("基金類別") or "").strip() != _cat:
            continue
        _v = _num(r.get("Sharpe 1Y"))
        if _v is not None:
            _sh.append(_v)
    if not _sh:
        return {"systemic_risk": False, "neg_pct": None, "n": 0}
    _neg = sum(1 for v in _sh if v < 0) / len(_sh)
    return {
        "systemic_risk": _neg >= SWITCH_REGIME_NEG_SHARPE_RATIO,
        "neg_pct": round(_neg * 100.0, 1),
        "n": len(_sh),
    }


def execution_advice(signal: str) -> str:
    """依燈號給處置建議文字(user spec 的執行 SOP)。"""
    if signal == RED:
        return ("分批(3~6 個月)或**同公司平轉**至同類別高 Sharpe(≥0.5)、總報酬為正的標的;"
                "基本面惡化(嚴重吃本金 / 經理人換手)→ 建議一次性轉換。")
    if signal == YELLOW:
        return "暫停定期定額加碼,觀察下季 vs 大盤超額與下檔保護;跌破底線停損點果斷執行。"
    if signal == GREEN:
        return "續抱,可作核心資產或定期定額加碼。"
    return "資料不足,保持觀察 —— 勿據此買賣(§1)。"
