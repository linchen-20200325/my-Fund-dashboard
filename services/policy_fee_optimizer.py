"""services/policy_fee_optimizer.py — 投資型保單跨幣別扣費決策引擎(v19.510)。L2 純函式。

給定每月固定管理費(TWD)+ 即時匯率 + 混合幣別持倉,評估「該用哪一檔基金扣款、還是直接
台幣現金扣款」。核心:跨幣別比較每檔「相較成本的總報酬倍數」S_i(含匯兌)—— 排除基金原始
單價高低,純看目前相對成本的獲利程度,高分者優先當「停利扣款」候選。

⚠️ **模型侷限(v19.510 金融領域稽核,誠實揭露 §1)**:S 是**回溯**倍數,不代表未來;且「高 S」
不等於「對組合傷害最小」—— 每次扣款都恰扣固定 F 元台幣,贖回單位數 = F/V 只跟當前單位市值
有關、與 S 無關,真正的部位擾動是 `loss_pct = F/M`(本欄有算)。S 亦未計入海外所得稅、贖回/
轉換費、放棄的複利。故本引擎定位為**教學參考(見 DISCLAIMER),非賣出建議**;輸出把 S 拆成
`return_factor`(基金報酬)× `fx_factor`(匯兌)供使用者辨別高分來源,成本未知者標
`is_cost_estimated` 不假裝真實基期。

§8.2:L2 CalcEngine 純函式,**零 I/O、零 streamlit**。輸入由 caller(L3 / 帳本)備妥。
§1 Fail Loud:
  - 管理費 <= 0 → raise ValueError(整份輸入無效,不猜)。
  - 單檔 NAV / 單位 <= 0,或外幣標的缺該幣別即期匯率 → 該檔標 `error` 旗標並**排除**於推薦
    名單(不矇預設值、不靜默丟),其餘檔照算;error 原因寫進輸出供 UI 揭露(§5 可觀測)。
§4.1 量綱:`loss_pct` 為**百分比**(×100,非 ratio);TWD 有效匯率強制 1.0;成本缺省 →
  報酬倍數 = 1.0(不影響 S_i)。§4.4:V_TWD = NAV×匯率,NAV>0 已驗 → U_deduct 除法安全。
§4.3 浮點:分類用 >= 容差比較(門檻常數),不對 float 用 ==。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

# ── §2.3 燈號門檻(本引擎領域常數;目前無跨模組共用需求 → module SSOT,不 inline magic §3.3)──
SCORE_HIGH = 1.15   # S_i >= → 🟢 高檔獲利(SUCCESS,適合停利扣款)
SCORE_LOW = 0.90    # S_i <  → 🔴 低檔虧損(DANGER);[LOW, HIGH) → 🟡 正常震盪(WARNING)

_STATUS_HIGH = "🟢 高檔獲利 (適合停利扣款)"
_STATUS_MID = "🟡 正常震盪 (建議保留)"
_STATUS_LOW = "🔴 低檔虧損 (強烈避開)"

BADGE_SUCCESS = "SUCCESS"
BADGE_WARNING = "WARNING"
BADGE_DANGER = "DANGER"

REC_FUND = "FUND_DEDUCTION"
REC_CASH = "TWD_CASH"

# §1 誠實護欄(v19.510 金融領域稽核):評分 S 是**回溯**報酬倍數(且含匯兌),不代表未來,
# 也未計入下列真實成本 —— UI 須顯著揭露,避免使用者把「高分」讀成「該賣」。
DISCLAIMER = (
    "⚠️ 教學參考,非賣出建議。評分 S 為「目前相對成本的回溯報酬倍數(含匯兌損益)」,"
    "**未計入**:海外所得/最低稅負、基金贖回/轉換費與短線交易罰則、以及贖回後放棄的複利。"
    "注意:任何扣款都恰好扣掉固定的管理費金額(TWD),真正影響組合的是「被扣部位佔比 loss_pct」"
    "而非評分高低;高 S 往往也是已實現獲利最大、課稅最不利的一檔。贖回前請自行確認成本、稅費與最低贖回單位。"
)


@dataclass
class FundEval:
    id: str
    name: str
    currency: str
    effective_rate: Optional[float]   # R_eff(TWD 恆 1.0);資料異常 → None
    unit_value_twd: Optional[float]   # V = NAV_curr × R_eff
    market_value_twd: Optional[float]  # M = units × V
    units_deduct: Optional[float]     # U_deduct = F / V
    loss_pct: Optional[float]         # (U_deduct / units) × 100 —— 本次扣款佔該部位比例(真正的「擾動」)
    score: Optional[float]            # S_i = return_factor × fx_factor
    return_factor: Optional[float]    # NAV_curr / NAV_cost(基金本身報酬倍數;稽核 Q4 拆解)
    fx_factor: Optional[float]        # R_eff / R_cost_eff(匯兌倍數;TWD 恆 1.0)
    status_tag: Optional[str]         # 燈號文字(資料異常 → None)
    badge_level: Optional[str]        # SUCCESS / WARNING / DANGER(資料異常 / 成本未知 → None)
    is_sufficient: bool               # M >= F 且無 error → 可入推薦名單
    is_cost_estimated: bool           # 成本(NAV/匯率)缺省 → S 以持平推定,非真實基期(§1 不假裝)
    error: Optional[str]              # 資料異常原因(§1 不靜默);正常 → None


def _classify(score: float) -> tuple[str, str]:
    """S_i → (status_tag, badge_level)。§2.3 三段;>= 邊界含左界(1.15/0.90 落高/中段)。"""
    if score >= SCORE_HIGH:
        return _STATUS_HIGH, BADGE_SUCCESS
    if score >= SCORE_LOW:
        return _STATUS_MID, BADGE_WARNING
    return _STATUS_LOW, BADGE_DANGER


def evaluate_fund(fund: dict, exchange_rates: dict, monthly_fee_twd: float) -> FundEval:
    """單檔評估。資料異常(NAV/單位<=0、外幣缺匯率、成本<=0)→ FundEval 帶 error 旗標,
    數值欄留 None、is_sufficient=False(§1 不矇預設、不靜默),caller 排除於推薦名單。

    §1:管理費 <= 0 為輸入契約違反(非基金資料)→ raise(evaluate_fund 直呼者也享 fail-loud,
    不只 optimize_policy_fee 守;F4 稽核補洞)。
    """
    try:
        _fee = float(monthly_fee_twd)
    except (TypeError, ValueError) as e:
        raise ValueError(f"monthly_fee_twd 非數值:{monthly_fee_twd!r}") from e
    if not (_fee > 0):
        raise ValueError(f"monthly_fee_twd 必須 > 0(得到 {_fee})")
    monthly_fee_twd = _fee
    _id = str(fund.get("id") or "")
    _name = str(fund.get("name") or _id)
    _ccy = str(fund.get("currency") or "").strip().upper()
    # F2 稽核補洞:匯率字典 key 也正規化為大寫,與 fund 幣別對齊(避免 {"usd":..} 這類
    # 小寫 key 讓每檔外幣標的都誤判「缺匯率」)。TWD 短路 1.0 不走查表,本就免疫。
    _rates_up = {str(k).strip().upper(): v for k, v in (exchange_rates or {}).items()}

    def _bad(reason: str) -> FundEval:
        return FundEval(id=_id, name=_name, currency=_ccy, effective_rate=None,
                        unit_value_twd=None, market_value_twd=None, units_deduct=None,
                        loss_pct=None, score=None, return_factor=None, fx_factor=None,
                        status_tag=None, badge_level=None, is_sufficient=False,
                        is_cost_estimated=False, error=reason)

    # ── 基礎欄位驗證(§1:壞資料誠實標記,不猜)────────────────────────────
    try:
        nav_curr = float(fund.get("current_nav"))
        units = float(fund.get("units"))
    except (TypeError, ValueError):
        return _bad("current_nav / units 非數值")
    if not (nav_curr > 0):
        return _bad(f"current_nav 非正值({nav_curr})——疑停售/清算,不可扣款")
    if not (units > 0):
        return _bad(f"units 非正值({units})")

    # ── 有效匯率(§2.2 step1;TWD 強制 1.0;外幣缺匯率 = 無法折算 → error)──────────
    if _ccy == "TWD":
        eff_rate = 1.0
    else:
        _r = _rates_up.get(_ccy)
        try:
            eff_rate = float(_r)
        except (TypeError, ValueError):
            return _bad(f"缺 {_ccy} 即期匯率(exchange_rates 未提供)——無法折算 TWD")
        if not (eff_rate > 0):
            return _bad(f"{_ccy} 匯率非正值({eff_rate})")

    # ── 單位折台幣價值 V、總市值 M、贖回單位 U、損耗% ──────────────────────
    unit_value_twd = nav_curr * eff_rate            # §2.2 step2:V(NAV>0、rate>0 → V>0)
    market_value_twd = units * unit_value_twd        # §2.2 step3:M
    units_deduct = monthly_fee_twd / unit_value_twd  # §2.2 step4:U_deduct(V>0 → 安全)
    loss_pct = (units_deduct / units) * 100.0        # §2.2 step5:§4.1 百分比(×100)

    # ── 跨幣別基期評分 S_i(§2.2 step6)= return_factor × fx_factor(稽核 Q4 拆解揭露)──
    #   成本缺省:cost_nav→current_nav、cost_rate→當前匯率 → 對應倍數 = 1.0。TWD:fx_factor 恆 1.0。
    #   §1 誠實:成本缺省時 `is_cost_estimated=True` —— S 是「以持平推定」非真實基期,**不假裝**
    #   1.0 是「正常震盪」(badge 留 None,由 UI 標示「成本未知」而非給綠/黃/紅燈)。
    is_cost_estimated = False
    if fund.get("cost_nav") is not None:
        try:
            cost_nav = float(fund["cost_nav"])
        except (TypeError, ValueError):
            return _bad("cost_nav 非數值")
    else:
        cost_nav = nav_curr
        is_cost_estimated = True
    if not (cost_nav > 0):
        return _bad(f"cost_nav 非正值({cost_nav})——無法算報酬倍數")
    if _ccy == "TWD":
        cost_rate_eff = 1.0                          # TWD 匯率不參與 → 非「推定」,是定義
    elif fund.get("cost_rate") is not None:
        try:
            cost_rate_eff = float(fund["cost_rate"])
        except (TypeError, ValueError):
            return _bad("cost_rate 非數值")
    else:
        cost_rate_eff = eff_rate
        is_cost_estimated = True
    if not (cost_rate_eff > 0):
        return _bad(f"cost_rate 非正值({cost_rate_eff})")
    return_factor = nav_curr / cost_nav
    fx_factor = eff_rate / cost_rate_eff
    score = return_factor * fx_factor
    # 成本未知 → 不給確定燈號(§1 不把推定的 1.0 講成「正常震盪」);成本已知 → 正常分類。
    if is_cost_estimated:
        status_tag, badge_level = "⬜ 成本未知(評分以持平推定,僅供參考)", None
    else:
        status_tag, badge_level = _classify(score)

    # is_sufficient:市值須足額支付管理費(§2.2 step3 過濾規則),否則排除推薦名單。
    is_sufficient = market_value_twd >= monthly_fee_twd

    return FundEval(
        id=_id, name=_name, currency=_ccy, effective_rate=round(eff_rate, 6),
        unit_value_twd=round(unit_value_twd, 6), market_value_twd=round(market_value_twd, 2),
        units_deduct=round(units_deduct, 6), loss_pct=round(loss_pct, 4),
        score=round(score, 6), return_factor=round(return_factor, 6),
        fx_factor=round(fx_factor, 6), status_tag=status_tag, badge_level=badge_level,
        is_sufficient=is_sufficient, is_cost_estimated=is_cost_estimated, error=None,
    )


def optimize_policy_fee(monthly_fee_twd, exchange_rates: dict, funds: list) -> dict:
    """跨幣別扣費決策主入口。回 JSON-safe dict(見模組 docstring 輸出契約)。

    §2.4 決策流:
      情境 C:無任一足額標的 → TWD_CASH(降級防禦)。
      情境 A:最高分足額標的 S_top >= 1.15 → FUND_DEDUCTION(高檔停利扣款)。
      情境 B:所有足額標的 S_i < 1.15 → TWD_CASH(避免削弱長期複利)。
    """
    try:
        fee = float(monthly_fee_twd)
    except (TypeError, ValueError) as e:
        raise ValueError(f"monthly_fee_twd 非數值:{monthly_fee_twd!r}") from e
    if not (fee > 0):                       # §1:管理費必為正,不猜
        raise ValueError(f"monthly_fee_twd 必須 > 0(得到 {fee})")
    _rates = exchange_rates or {}
    _funds = funds or []

    evals = [evaluate_fund(f, _rates, fee) for f in _funds]
    # 依 S_i 由高到低排序;error / None 分數沉底(不參與推薦,但仍列於輸出供 UI 揭露)。
    evals.sort(key=lambda e: (e.score is not None, e.score if e.score is not None else 0.0),
               reverse=True)

    eligible = [e for e in evals if e.is_sufficient and e.error is None]

    # ── 台幣基金安全扣款候選 twd_fund_alt(user 2026-08-22「台幣基金也納入扣款候選」)──────
    # 投資型保單管理費多為「贖回單位」內扣;台幣基金 fx_factor 恆 1.0 → 免匯率風險,是
    # 「不動用外部現金也能避開匯兌」的**保單內**扣款替代。§1 誠實護欄(三位 AI 專家會審結論):
    #   - 只從足額 + 無 error 挑,不挑物理上扣不動的(市值<管理費)。
    #   - 排除 is_cost_estimated:成本未知 → score 是推定 1.0,不可拿假分數排名/當划算訊號。
    #   - 排除 DANGER(score < SCORE_LOW=0.90 = 強烈避開):賣它 = 低點實現虧損,不當「安全」賣。
    #   - **依 loss_pct 升序**挑「對部位擾動最小」者(= 市值最大),**非**依 score —— score 對
    #     台幣基金 = 純報酬倍數 = 偏好賣獲利最大檔 = 課稅/複利最不利,與本欄「免匯率風險/低擾動」
    #     效益是不同軸(evals 本身已按 score 降序,故此處**另行**依 loss_pct 排序,勿沿用)。
    #   - 本欄為**平行/替代選項,非優於現金**(現金零擾動、保留複利);L3 僅在 TWD_CASH 情境
    #     渲染、且須標明仍會贖回單位/放棄複利,0.90<=score<1.0(略低於成本)須標小幅實現虧損。
    # L2 無條件計算(不綁 scenario)→ 可單測;None = 無合格台幣基金。
    _twd_cands = [e for e in evals
                  if e.currency == "TWD" and e.error is None and e.is_sufficient
                  and not e.is_cost_estimated
                  and e.score is not None and e.score >= SCORE_LOW]
    _twd_cands.sort(key=lambda e: (e.loss_pct if e.loss_pct is not None else float("inf"), e.id))
    twd_fund_alt = asdict(_twd_cands[0]) if _twd_cands else None

    if not eligible:                        # 情境 C:降級防禦
        recommendation, scenario, top = REC_CASH, "C", None
        annotation = ("建議直接使用【台幣現金扣款】。因所有持倉標的餘額不足以支付本月管理費 "
                      f"{fee:,.0f} 元(或資料異常),必須以台幣現金繳費。")
    else:
        # top 選取:優先「真實成本」足額標的,避免推定 S=1.0(is_cost_estimated,cost 缺省)蓋過
        # 已知「略低於成本」的真實標的(§1 誠實:假平價不得勝過已知資訊;twd_fund_alt 同理排除 imputed)。
        # eligible 已依 score desc → 子集 [0] 即該子集最高分;無真實成本標的才退 imputed(UI 標「成本未知」)。
        _elig_real = [e for e in eligible if not e.is_cost_estimated]
        top = (_elig_real or eligible)[0]
        if top.score >= SCORE_HIGH:         # 情境 A:高檔停利扣款
            recommendation, scenario = REC_FUND, "A"
            annotation = (f"建議優先由【{top.name}】扣除。該標的目前處於高基期(評分 "
                          f"{top.score:.3f}=基金報酬 {top.return_factor:.3f}×匯兌 {top.fx_factor:.3f}),"
                          f"扣除 {top.units_deduct:.4f} 單位佔持倉 {top.loss_pct:.2f}%,具高檔停利減損參考。")
            if top.is_cost_estimated:       # §1:成本未知 → 高分可能來自匯兌/推定,誠實提醒
                annotation += " 註:此標的成本未知,評分以持平推定,高分可能來自匯兌而非真實獲利,請自行確認成本。"
        else:                               # 情境 B:皆未達高檔 → 台幣現金
            recommendation, scenario = REC_CASH, "B"
            # F1/Q3 稽核修:top 是**足額**標的中最高分,非全體最高。若有高分(S>=1.15)標的
            # 因餘額不足被排除,誠實點名(否則「所有標的皆未達高檔」為假陳述,§1)。
            _hi_insuf = [e for e in evals if e.error is None and not e.is_sufficient
                         and e.score is not None and e.score >= SCORE_HIGH]
            annotation = (f"建議直接使用【台幣現金扣款】。目前所有**足額可扣**標的皆未達高檔"
                          f"停利標準(最高足額標的【{top.name}】評分 {top.score:.3f}),"
                          f"由基金內扣會削弱未來的長期複利動能。")
            if _hi_insuf:
                _names = "、".join(f"{e.name}({e.score:.2f})" for e in _hi_insuf[:3])
                annotation += f" 註:【{_names}】雖達高檔但餘額不足以支付管理費,已排除。"

    return {
        "recommendation": recommendation,
        "scenario": scenario,
        "top_pick_id": (top.id if top else None),
        "top_pick_name": (top.name if top else None),
        "annotation": annotation,
        "disclaimer": DISCLAIMER,           # §1 誠實護欄:UI 須顯著揭露(稅/費/複利未計入)
        "monthly_fee_twd": fee,
        "eligible_count": len(eligible),
        "top_pick": (asdict(top) if top else None),  # 組內最高 S 足額標的(依匯率×淨值);None=無足額標的
        "twd_fund_alt": twd_fund_alt,       # 台幣基金安全扣款候選(免匯率風險、擾動最小);None = 無
        "funds": [asdict(e) for e in evals],
    }
