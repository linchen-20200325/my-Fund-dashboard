"""v19.327 services — 基金「核心 / 衛星資產」分類 SSOT(L2 純函式,zero-IO)。

背景
====
user 要在基金健診顯示每檔是「核心資產」還是「衛星資產」。原擬單用 MK 3-3-3
(成立≥3年 + 3年年化>7%)判定,但 3-3-3 對保單子網域被封鎖 / 成立日缺的基金
大量「資料不足」→ 涵蓋率不足。改「兩層 + 來源標記」(對齊 v19.325 配息來源精神)。

判定順序(每檔回傳 `source` 血緣標記,§2.2)
==========================================
1. 類別命中「衛星關鍵字」(集中 / 主題 / 高波動追報酬)→ 衛星(source="類別")
   —— 集中型不論 3-3-3 過不過,角色都是衛星。
2. MK 3-3-3 明確通過(穩健長線達標)→ 核心(source="3-3-3")
3. 類別命中「核心關鍵字」(廣泛分散 / 穩健配置)→ 核心(source="類別")
4. 皆無法判定 → 待定(source=None,§1 不亂扣)

關鍵字對照表為**可調 SSOT**:誤判時直接改本檔常數(或未來接 Google Sheet 覆寫)。
"""
from __future__ import annotations

import math
from typing import Optional

# ── 衛星資產關鍵字(集中 / 主題 / 單一國 / 高收益 — 命中優先於核心)──
# 可調 SSOT:新增 / 移除關鍵字即改分類結果。
SATELLITE_KEYWORDS: tuple[str, ...] = (
    # 產業 / 主題
    "產業", "類股", "科技", "半導體", "生技", "生物", "醫療", "醫藥", "保健",
    "金融", "能源", "電力", "原物料", "天然資源", "資源", "礦", "黃金", "貴金屬",
    "房地產", "不動產", "REIT", "基礎建設", "主題", "機器人", "電動車",
    "人工智慧", "元宇宙", "氣候", "永續能源", "特別股",
    # 高收益 / 非投資等級
    "高收益", "非投資等級", "高收",
    # 新興 / 單一國 / 區域
    "新興", "邊境", "中國", "大中華", "中華", "印度", "越南",
    "拉丁美洲", "拉美", "巴西", "俄羅斯", "東協", "東南亞", "韓國", "台灣智慧",
    # 規模 / 風格(v19.328 user:「美國成長 = 衛星」→ 成長型追報酬歸衛星)
    "中小型", "小型", "成長",
)

# ── 核心資產關鍵字(廣泛分散 / 穩健配置)──
CORE_KEYWORDS: tuple[str, ...] = (
    "全球", "環球", "世界", "國際", "已開發", "成熟",
    "投資等級", "投資級", "綜合債", "複合債", "政府債", "公債", "全球債",
    "平衡", "組合", "多重資產", "多元資產", "多重收益", "目標",
    "大型", "藍籌",
)

_EMOJI = {"核心": "🟦", "衛星": "🟠", "待定": "⬜"}

# ── 待定(無法分類)佔比上限 —— 純**資料品質**門檻,不是配置評價 ──────────
# 2026-08-07 user 拍板:核心 / 衛星「該不該調整」全站唯一真相是 Google Sheet 的
# `policy_tier`(走 `ui/helpers/portfolio/allocation.summarize_core_satellite`)。
# 本模組回答的是**另一個問題** ——「這檔基金的資產屬性偏穩健還是偏主題」——
# 屬純資訊,**不得**再輸出行動建議,也不再持有任何「建議核心佔比」目標值。
# 原本這裡有一組建議區間常數(核心 50~80%),已於本次連同其 4 級燈號一起移除:
# 只要這一層還留著一組目標,同一頁就會再度出現兩個方向相反的再平衡結論
# (使用者實際遇到的症狀:上方說「核心過重可減」、下方說「衛星過重要加」)。
UNDETERMINED_UNRELIABLE_PCT: float = 30.0

# 分類涵蓋度狀態碼(⚠️ 不是配置評價燈號):只回答「待定佔比是否低到讓比例可讀」。
COVERAGE_OK: str = "🔵"
COVERAGE_UNRELIABLE: str = "⚪"


def classify_by_category(category: Optional[str]) -> Optional[str]:
    """純用基金類別字串判「核心 / 衛星」。命中衛星優先(集中型角色明確)。

    Returns "核心" / "衛星" / None(無法判定)。
    """
    cat = (category or "").strip()
    if not cat:
        return None
    if any(k in cat for k in SATELLITE_KEYWORDS):
        return "衛星"
    if any(k in cat for k in CORE_KEYWORDS):
        return "核心"
    return None


def classify_core_satellite(
    category: Optional[str],
    passed_333: Optional[bool],
) -> dict:
    """核心 / 衛星資產分類 SSOT(兩層 + 來源標記)。

    Args:
        category: 基金類別(MoneyDJ 投資標的 / 基金類型,原始字串)
        passed_333: MK 3-3-3 結果(True 通過 / False 未通過 / None 資料不足)
    Returns:
        {
          "label":  "核心" / "衛星" / "待定",
          "emoji":  對應色點,
          "source": "類別" / "3-3-3" / None,  # 血緣:此檔依哪個訊號判定
          "display": f"{emoji} {label}",       # UI 直接顯示
          "note":   str,                       # hover 說明
        }
    """
    cat = (category or "").strip()
    cat_role = classify_by_category(cat)

    # 1. 集中 / 主題型 → 衛星(不論 3-3-3;角色由類別決定)
    if cat_role == "衛星":
        return _pack("衛星", "類別", f"類別「{cat[:14]}」屬集中 / 主題型 → 衛星")
    # 2. MK 3-3-3 明確通過 → 核心(穩健長線達標)
    if passed_333 is True:
        _extra = f";類別「{cat[:14]}」" if cat else ""
        return _pack("核心", "3-3-3", f"通過 MK 3-3-3(成立≥3年 + 3年年化>7%){_extra}")
    # 3. 廣泛分散型 → 核心
    if cat_role == "核心":
        return _pack("核心", "類別", f"類別「{cat[:14]}」屬廣泛分散型 → 核心")
    # 4. 判不出來 → 待定(§1 不亂扣)
    _why = "類別無法判定" if cat else "缺基金類別"
    if passed_333 is False:
        _why += " + 未達 3-3-3"
    return _pack("待定", None, f"資料不足({_why})")


def _pack(label: str, source: Optional[str], note: str) -> dict:
    emoji = _EMOJI.get(label, "⬜")
    return {
        "label": label,
        "emoji": emoji,
        "source": source,
        "display": f"{emoji} {label}",
        "note": note,
    }


def summarize_core_satellite_allocation(items) -> dict:
    """組合層「**基金資產屬性**分布」彙總(核心 / 衛星 / 待定佔比)—— 純資訊。

    ⚠️ **本函式不評價配置、不給行動建議**(2026-08-07 user 拍板)
    ================================================================
    「核心佔比該不該調整」的唯一真相是使用者在 Google Sheet 標的 `policy_tier`,
    走 `ui/helpers/portfolio/allocation.summarize_core_satellite`(金額加權 + 目標
    吃 `portfolio_core_pct`)。本函式分類依據完全不同(MoneyDJ 基金類別關鍵字 +
    MK 3-3-3),回答的是「我手上這幾檔本質上偏穩健還是偏主題」。兩者並列時若都給
    建議,同一頁就會出現兩個方向相反的結論,而使用者無從判斷該聽哪一個。
    故本函式只回傳**比例 + 分類涵蓋度**,不再輸出「核心不足 / 衛星過重 / 該調整」
    這類 `message`,也不再持有任何建議核心佔比目標值。

    以傳入的 `weight` 加權(**本函式忠實依 caller 給的權重計算,不自行假設語意**),
    算出核心 / 衛星 / 待定佔比。

    ⚠️ `weight_mode` — caller 對外陳述「加權方式」時**必須**讀此欄(§1 Fail Loud, Never Fake)
    ============================================================================
    呼叫端有兩種:基金健診 Tab 只有**單一本金欄位** broadcast 給全部基金(每檔 weight 相同
    → 實際等權,結果 ≈ 檔數佔比);Tab3 持倉健診傳各檔實際 `invest_twd`(真金額加權),但
    user 若全未填 invest_twd 也會全退預設值 → 一樣變等權。因此「是不是金額加權」**不能由
    caller 自稱**,只能由實際權重推斷 —— 本函式回傳 `weight_mode` 讓 UI 照實說,
    避免對 user 陳述與計算行為不符的方法論。

    Args:
        items: [{"label": "核心" / "衛星" / "待定", "weight": float(投入金額 TWD)}]
               weight ≤ 0 / 非數 → 該檔略過(不計入分母,亦不參與 weight_mode 推斷)。
               呼叫端若對某檔用的是「模擬本金」(使用者從未填過的預設值),**必須**
               傳 0 把它擋在分母外 —— 捏造的金額不得影響對外顯示的百分比(§1)。
    Returns:
        {
          "total_weight": float,
          "core_pct" / "satellite_pct" / "undetermined_pct": float(0~100,佔總權重,三者和≈100),
          "n_core" / "n_satellite" / "n_undetermined": int,
          "status": COVERAGE_OK / COVERAGE_UNRELIABLE,   # **分類涵蓋度**,不是配置評價
          "coverage_note": str,   # 只講資料品質(待定太多 / 無有效權重),不含行動建議
          "weight_mode": "amount" / "equal" / "single" / "none",  # 見上方 ⚠️
        }
        判定:無有效權重 或 待定 > `UNDETERMINED_UNRELIABLE_PCT` → `COVERAGE_UNRELIABLE`;
        其餘 → `COVERAGE_OK`。**不對核心佔比高低作任何評價。**
    """
    core_w = sat_w = und_w = 0.0
    n_core = n_sat = n_und = 0
    eff_weights: list[float] = []   # 有效(>0)權重,供 weight_mode 推斷
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        w = _safe_w(it.get("weight"))
        if w is None or w <= 0:
            continue
        eff_weights.append(w)
        label = str(it.get("label") or "").strip()
        if "核心" in label:
            core_w += w
            n_core += 1
        elif "衛星" in label:
            sat_w += w
            n_sat += 1
        else:
            und_w += w
            n_und += 1
    total = core_w + sat_w + und_w
    if total <= 0:
        return {"total_weight": 0.0, "core_pct": 0.0, "satellite_pct": 0.0,
                "undetermined_pct": 0.0, "n_core": 0, "n_satellite": 0,
                "n_undetermined": 0, "status": COVERAGE_UNRELIABLE,
                "weight_mode": "none",
                "coverage_note": "無有效投入金額,無法計算屬性分布比例"}
    core_pct = core_w / total * 100.0
    sat_pct = sat_w / total * 100.0
    und_pct = und_w / total * 100.0

    # 只判「分類涵蓋度」(資料品質),不判配置好壞 —— 見 docstring ⚠️。
    if und_pct > UNDETERMINED_UNRELIABLE_PCT:
        status = COVERAGE_UNRELIABLE
        note = (f"待定 {und_pct:.0f}% 過多(> {UNDETERMINED_UNRELIABLE_PCT:.0f}%),"
                f"下列屬性比例僅供參考 — 補上基金分類後才讀得準")
    else:
        status = COVERAGE_OK
        note = (f"待定 {und_pct:.0f}%(≤ {UNDETERMINED_UNRELIABLE_PCT:.0f}%),"
                f"屬性分類涵蓋足夠")

    return {
        "total_weight": round(total, 0),
        "core_pct": round(core_pct, 1),
        "satellite_pct": round(sat_pct, 1),
        "undetermined_pct": round(und_pct, 1),
        "n_core": n_core, "n_satellite": n_sat, "n_undetermined": n_und,
        "status": status, "coverage_note": note,
        "weight_mode": infer_weight_mode(eff_weights),
    }


def infer_weight_mode(weights) -> str:
    """由**實際權重**推斷加權方式(caller 對 user 陳述方法論的唯一依據)。

    Returns:
        "none"   — 無有效權重(無法計算)
        "single" — 僅 1 檔(加權方式不影響結果)
        "equal"  — 全部權重相等 → 佔比 ≡ 檔數佔比,**不是**金額配置
        "amount" — 權重不全相等 → 確實依金額加權

    「全部相等 ⟺ 佔比 = 檔數佔比」為數學恆真,故本推斷不會說謊:即使 caller 傳的是
    真實 invest_twd,只要各檔金額恰好相同,結論(=檔數佔比)仍然成立。
    浮點比較走 math.isclose(§4.3 禁止 `==`)。
    """
    ws = list(weights or [])
    if not ws:
        return "none"
    if len(ws) == 1:
        return "single"
    w0 = ws[0]
    if all(math.isclose(w, w0, rel_tol=1e-9, abs_tol=1e-12) for w in ws[1:]):
        return "equal"
    return "amount"


def _safe_w(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f
