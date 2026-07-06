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
