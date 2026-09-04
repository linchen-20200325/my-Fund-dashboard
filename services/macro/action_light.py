"""services/macro/action_light.py — 總經「現在能不能買」總結燈(L2 純函式,zero-IO)。

v19.316 功能盤點改進 #4-①:總經頁子視圖多(即時/中期/短線/長期/拐點),缺一個「一句話結論」。
本函式把既有訊號融成 🟢 可加碼 / 🟡 持有 / 🔴 減碼,附觸發理由,供 UI 提到最上面。

設計(user 2026-07-05 批准的草案):
  1. **硬衰退/恐慌訊號 override**(任一亮 → 🔴,不管景氣位階多高 —— 安全層):
     - 殖利率曲線倒掛(10Y-2Y 或 10Y-3M < 0)
     - Sahm 規則 ≥ 0.5(衰退警報)
     - VIX ≥ 30(市場恐慌 / 高波動)
  2. 無 override → 依景氣位階(calc_macro_phase 的 0-10 score,即畫面「N/10」):
     - ≥ 6.5 → 🟢 可加碼；4.0~6.5 → 🟡 持有;< 4.0 → 🔴 減碼
  3. 位階缺 → 🟡 資料不足,不下假綠燈(§1 Fail-Loud)。

**這是「位階/機率」不是「擇時」**:override 是保守安全層(寧可少賺不要住套房),
非精準買賣點。所有燈都附「為什麼」讓 user 自行判斷。
"""
from __future__ import annotations

from services.macro.evidence import PHASE_SCALE as _SCALE
from services.macro.evidence import action_light_all_clear_support as _all_clear_support
from services.macro.evidence import action_light_support as _action_light_support
from services.macro.evidence import phase_support as _phase_support
from shared.evidence_support import is_sufficient as _is_sufficient
from shared.signal_thresholds import SAHM_RECESSION_THRESHOLD

# ── 門檻(self-contained mini-SSOT;provenance 註明來源)──────────────
_YIELD_INVERT_PCT: float = 0.0    # 殖利率利差 < 0 = 倒掛(古典衰退領先訊號)
_VIX_PANIC: float = 30.0          # C2 v19.160 全站 universal panic = 30(對稱 tests/test_cross_site_cutoffs)
_BUY_SCORE_10: float = 6.5        # 景氣位階 ≥ 此 → 🟢 可加碼(0-10 scale;可調)
_HOLD_SCORE_10: float = 4.0       # 景氣位階 ≥ 此 → 🟡 持有;< 此 → 🔴 減碼

#: 買賣燈自己的結論帶(0~10 分數上的 🔴 / 🟡 / 🟢 三格),**由上面兩個門檻導出**。
#: 2026-09-04 第五輪稽核 F2:證據會計原本拿**相位帶**(3/5/8)去替買賣燈背書,
#: 但 `_HOLD_SCORE_10 = 4.0` 這條線落在相位帶「復甦」(3~5)的**內部** ——
#: 一個相位帶內不變的狀態,燈號照樣可以在 4.0 上翻。要問對問題就得用對的帶。
ACTION_LIGHT_BAND_EDGES: tuple[float, float] = (_HOLD_SCORE_10, _BUY_SCORE_10)

#: 最窄的一格(給支配性條件用)。0~4.0 減碼(4.0)/ 4.0~6.5 持有(**2.5**)/
#: 6.5~10 加碼(3.5)→ 最窄 = 2.5。**由邊界導出,不寫死。**
ACTION_LIGHT_NARROWEST_BAND: float = min(
    ACTION_LIGHT_BAND_EDGES[0],
    ACTION_LIGHT_BAND_EDGES[1] - ACTION_LIGHT_BAND_EDGES[0],
    _SCALE - ACTION_LIGHT_BAND_EDGES[1],
)


def action_light_band(score_10: float) -> str:
    """0~10 景氣位階 → 這盞燈的顏色。**與下方 if-chain 等價**(有漂移鎖)。"""
    _s = float(score_10)
    if _s >= _BUY_SCORE_10:
        return "🟢"
    if _s >= _HOLD_SCORE_10:
        return "🟡"
    return "🔴"


# ── override 這一層**實際會去讀**的 indicator key(2026-09-04 第三輪稽核 A1)──
#
# 為什麼要把它匯出成常數:非 override 分支回傳的 reason 逐字寫
# 「無硬衰退/恐慌訊號(**殖利率曲線、Sahm、VIX 均未觸發**)」—— 那是一句
# **點名了特定輸入**的宣稱。當那些輸入根本沒抓到時,這句話字面上是假的
# (完全斷線實測:四項全缺,畫面照樣寫「均未觸發」並放綠燈)。
#
# 呼叫端要判斷「這句話能不能講」,就必須知道**是哪幾個 key**。讓呼叫端自己
# 抄一份 key 清單 = 第二個真相源,本函式日後多讀一個指標(例如加上 HY_SPREAD)
# 時不會有人發現呼叫端的閘門漏了它。故在此匯出,並由
# `tests/test_batch2_top_card_grid.py` 的 AST 漂移鎖釘住「常數 ≡ 函式實際讀的 key」。
#
# ⚠️ 本常數**不改變本函式的行為** —— 它只是把既有的四個 `_val(...)` 讀取
# 顯性化;`macro_action_light` 的判斷邏輯一字未動。
OVERRIDE_INPUT_KEYS: tuple[str, ...] = (
    "YIELD_10Y2Y", "YIELD_10Y3M", "SAHM", "VIX",
)


def _val(indicators: dict, key: str) -> "float | None":
    """從 indicators dict 取某指標的 value(缺 / 型別錯 → None)。"""
    if not isinstance(indicators, dict):
        return None
    node = indicators.get(key)
    if not isinstance(node, dict):
        return None
    v = node.get("value")
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def macro_action_light(indicators: dict,
                       phase_score_10: "float | None" = None) -> dict:
    """總經買/賣總結燈。

    Args:
        indicators: fetch_all_indicators 的 dict(需含 YIELD_10Y2Y / YIELD_10Y3M /
                    VIX / SAHM 的 {"value": ...})。
        phase_score_10: 景氣位階 0-10(calc_macro_phase 的 score);None → 資料不足。

    Returns:
        {"light": "🟢"/"🟡"/"🔴", "action": str, "reasons": list[str], "override": bool}
    """
    # ── 1. 硬衰退 / 恐慌 override → 🔴 ───────────────────────────
    reasons_red: list[str] = []
    triggered: list[str] = []          # 哪幾個 key 真的越線(給 support 當人證)
    y22 = _val(indicators, "YIELD_10Y2Y")
    y3m = _val(indicators, "YIELD_10Y3M")
    vix = _val(indicators, "VIX")
    sahm = _val(indicators, "SAHM")

    if y22 is not None and y22 < _YIELD_INVERT_PCT:
        reasons_red.append(f"殖利率曲線倒掛（10Y-2Y {y22:+.2f}%）— 衰退領先訊號")
        triggered.append("YIELD_10Y2Y")
    if y3m is not None and y3m < _YIELD_INVERT_PCT:
        reasons_red.append(f"殖利率曲線倒掛（10Y-3M {y3m:+.2f}%）— 衰退領先訊號")
        triggered.append("YIELD_10Y3M")
    if sahm is not None and sahm >= SAHM_RECESSION_THRESHOLD:
        reasons_red.append(f"Sahm 規則 {sahm:.2f} ≥ {SAHM_RECESSION_THRESHOLD}（衰退警報中）")
        triggered.append("SAHM")
    if vix is not None and vix >= _VIX_PANIC:
        reasons_red.append(f"VIX {vix:.0f} ≥ {_VIX_PANIC:.0f}（市場恐慌 / 高波動）")
        triggered.append("VIX")

    # ── 證據支撐(2026-09-04 第四輪稽核;第五輪 F2 重排順序)────────────
    # ⚠️ **本欄不改本函式任何一個燈的判斷邏輯**,它回答的是另一個問題:
    # 「這一句話,手上的資料撐不撐得起來?」
    #   · override 已觸發 → 存在性宣稱,由實際觀測作證 → **恆充足**
    #   · 位階偏弱造成的 🔴 → **一樣是警報**,由分數作證 → 走買賣燈自己的帶
    #   · 🟢 / 🟡        → 「四項均未觸發」+ 位階兩個全稱宣稱的聯合
    # 完全斷線實測:四項一個都沒取到,舊版照樣印「均未觸發」並放綠燈。
    #
    # ⚠️ **順序改了:先決定燈,再算 support。** 第五輪稽核 F2 實測,舊順序
    # (先算一份 support 給所有分支共用)會把「位階偏弱 ⇒ 🔴」這種**已經站得住
    # 的警報**,因為那句「四項均未觸發」缺一項而整句灰掉 —— 27/28 全空頭、只缺
    # VIX 的狀態,產出端認證了 `0 衰退`,畫面卻印「這次的資料撐不起任何結論」。
    # 那是把規則 3 的不對稱**反過來用**(半套證據解除了警報)。

    # 那句「殖利率曲線、Sahm、VIX 均未觸發」自己的支撐 —— **與燈號分開**,
    # 消費端才能「留下警報、只扣掉這一句沒有支撐的話」(卡 5 早就是這個形狀)。
    _all_clear = _all_clear_support(indicators, override_keys=OVERRIDE_INPUT_KEYS)

    def _support_for(*, alarm: bool):
        return _action_light_support(
            indicators, override_keys=OVERRIDE_INPUT_KEYS,
            triggered=triggered, phase_score=phase_score_10,
            band_of=action_light_band,
            narrowest_band=ACTION_LIGHT_NARROWEST_BAND,
            alarm=alarm)

    # ⚠️ **兩個消費端問的不是同一句話,所以要有兩份 support**(第五輪 F2 的連帶):
    #   · `support`            = **我正在印的這盞燈**撐不撐得住(①結論讀它)。
    #     警報那一支走政策豁免 ⇒ 位階偏弱的 🔴 是「充足」的。
    #   · `no_trigger_support` = 「**四項都檢查過、都沒觸發**」撐不撐得住
    #     (卡 5「⚠️ 極端風險警語」的 🟢 讀它)。
    # 若卡 5 也讀 `support`,警報豁免會**溢出**到它身上:位階偏弱的 🔴 讓
    # `support.sufficient = True`,而卡 5 的 `override=False` 分支就落到
    # 「🟢 未觸發 / 0 項觸發」—— 在 VIX 根本沒抓到的情況下宣告四項都沒事,
    # 正是第三輪 A1 那個缺陷本身。(本輪實測重現過,故拆成兩份。)
    _no_trigger = _support_for(alarm=False)

    if reasons_red:
        return {
            "light": "🔴",
            "action": "減碼 / 保守 —— 拉高現金、核心轉防守，等企穩再進",
            "reasons": reasons_red,
            "override": True,
            "support": _support_for(alarm=True),
            "all_clear_support": _all_clear,
            "no_trigger_support": _no_trigger,
        }

    # ── 2. 無 override → 依景氣位階 ─────────────────────────────
    if phase_score_10 is None:
        return {
            "light": "🟡",
            "action": "資料不足 —— 景氣位階缺,先持有觀望",
            "reasons": ["景氣位階(0-10)未取得,無法定位階"],
            "override": False,
            "support": _no_trigger,
            "all_clear_support": _all_clear,
            "no_trigger_support": _no_trigger,
        }

    light = action_light_band(phase_score_10)
    action = {
        "🟢": "可加碼 —— 核心持有不動 + 衛星積極佈局，定期收息再投",
        "🟡": "持有 —— 分批進場、避免重押單一題材",
        "🔴": "減碼 —— 景氣位階偏弱,拉高現金水位",
    }[light]

    # 「均未觸發」是一句**點名了四個輸入**的全稱話。缺任何一項時**不得照印** ——
    # 那正是第三/四輪抓到的假話。改印它自己的 reason(產出端寫的,不會與判定分岔)。
    #
    # ── 2026-09-04 第六輪稽核 F-A2 ────────────────────────────────────
    # 「景氣位階 N/10」**也是一句引用了那顆分數的話**,同樣要有支撐才能印。
    # 舊版無條件印它,於是位階偏弱的 🔴(走政策豁免、燈號本身站得住)會印出
    # 一個**卡 1 就在正下方拒絕印**的數字:
    #     ①結論: 🔴 減碼 —— 景氣位階偏弱,拉高現金水位
    #            - 景氣位階 0.0/10          ← 沒有支撐,照印
    #            - ⬜ 這句話點名了 4 項輸入,實際只取到 0 項…
    #     卡 1  : ⬜ 資料不足                ← 同一顆分數,拒絕印
    # 同一個畫面上兩個標準。**量化(兩份,分開標明誰量的)**:
    #   · 第六輪稽核報的是 4657 個非 override 🔴 狀態裡 4095 個(**87.9%**)——
    #     **本組未複現該分布**(對方的狀態產生器不在手上),照錄不假裝驗過。
    #   · **本組自己量的**(缺 0~3 項、固定種子 20260904):943 個非 override 🔴
    #     裡 **256 個(27.1%)** 印了這句沒有支撐的話;修好之後 **0**。
    #   兩個數字差在取樣分布(本組的樣本偏向缺項少、`phase_support` 本來就充足的狀態),
    #   **結論一致**:這條路徑會印出一句它撐不起來的話。
    # **處置照本批自己寫的原則**:「留下警報、只扣掉沒有支撐的那一句」——
    # 🔴 一字不動(它由已取到的負向觀測作證),被扣掉的只有這一句,
    # 且**換成產出端自己的 reason**(與卡 1 同一份,不會分岔)。
    _phase_sup = _phase_support(indicators, phase_score_10)
    _reasons = [f"景氣位階 {phase_score_10:.1f}/10" if _is_sufficient(_phase_sup)
                else f"⬜ 景氣位階：{_phase_sup.reason} —— 故不引用這個分數"]
    _reasons.append("無硬衰退/恐慌訊號（殖利率曲線、Sahm、VIX 均未觸發）"
                    if _is_sufficient(_all_clear) else f"⬜ {_all_clear.reason}")

    return {
        "light": light,
        "action": action,
        "reasons": _reasons,
        "override": False,
        # 🔴 是警報 → 由分數作證即可;🟢/🟡 是「解除警報」→ 四項要全在。
        "support": _support_for(alarm=(light == "🔴")),
        "all_clear_support": _all_clear,
        "no_trigger_support": _no_trigger,
    }
