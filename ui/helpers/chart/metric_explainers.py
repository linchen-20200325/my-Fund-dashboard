"""ui/helpers/metric_explainers.py — v18.192：量化指標「白話文教學」集中地

目的（v5.0 Task2.1）：新手看得懂、老手有深度，且**不隱藏任何專業數據**。
把 Sharpe / σ / Alpha / Beta / MDD / 核心衛星 / 配息覆蓋率 / 重疊度 等指標的
「這代表什麼 + 資產配置實戰意義」集中成一份文案，由各 Tab 就近以
`st.expander("💡 這些數據代表什麼？")` 呼叫，避免散落重複。

設計：
- 內容（純 dict + `explainer_markdown`）與渲染（`render_metric_explainer` 用 streamlit）
  分離，前者可單元測試、不依賴 streamlit。
"""
from __future__ import annotations

# key → {title, body, short?}
#   body  ── 白話文 + 實戰意義（資產配置怎麼用），給 `💡 這些數據代表什麼？` 展開區用
#   short ── **一句**白話，給「就在數字旁邊」的位置用（2026-09-09 新增）
#
# ⭐ **`short` 為什麼加在這裡，而不是在用它的那一頁自己寫一句**
# ------------------------------------------------------------
# 客戶 2026-09-08 拍板的線框（`docs/wireframes/draft-four-page-content.html` §1）
# 逐字要求：「**Sharpe／σ／最大回撤／配息覆蓋／重疊度這幾個字，第一次出現時就在
# 同一行後面接一句白話，不做成另一張卡、不做成 tooltip**」，並就地指定做法：
# 「現有 `METRIC_EXPLAINERS` 的 `body` 太長（三、四句，含「實戰：」段），塞進括號會很擠，
#   所以**要在同一份 SSOT 上加一個 `short` 欄位**，長版留給展開區用 —— **不另開第二份文案**」。
#
# ⛔ **不另開第二份文案**這半句是重點：⑥⑧⑨ 三頁都會要這幾句白話，
#    每頁自己寫一句 ⇒ 同一個指標三種說法，而且改了其中一份**沒有任何東西會報錯**
#    （`CLAUDE.md §2.1`）。
#
# ⚠️ **這是純新增的欄位，對既有渲染零影響（實測，不是推論）**：
#    `explainer_markdown()` 只讀 `title` 與 `body`（見下），
#    兩個既有消費端 `ui/tab2_single_fund.py` / `ui/tab3_portfolio.py` 都只經過它。
#    ⛔ **本批一個 `ui/tab*.py` 的位元組都沒有改。**
#
# ⚠️ **`short` 是選填**：目前只有本批用得到的三個 key 有
#    （`sharpe` / `mdd` / `div_coverage`）。**沒有 `short` 的 key 不是漏做** ——
#    在它真的要出現在某一頁的數字旁邊之前，先寫一句沒人看的文案沒有意義
#    （`CLAUDE.md §8.1` step 6「用不到的抽象先不做」）。
#
# ⛔ **`short` 不得與 `body` 說不同的話。** 兩者是同一個指標的長短版；
#    改了其中一個要一起看。守衛：`tests/test_metric_short_explainers.py`。
METRIC_EXPLAINERS: dict[str, dict[str, str]] = {
    "sharpe": {
        "title": "Sharpe 夏普值",
        "body": "每承擔 1 單位波動風險，換到多少「超額報酬」。"
                "**>0.5 優秀、0~0.5 普通、<0 不如放現金**。"
                "實戰：比較同類基金時看這個，而不是只看報酬高低——"
                "高報酬但 Sharpe 低代表你是靠「冒大險」換來的。",
        # ⚠️ 「>0.5 算好」與 `body` 的「**>0.5 優秀**」是同一個門檻的長短版，不是兩個規則。
        "short": "每冒 1 分風險換到多少報酬，>0.5 算好。",
    },
    "sigma": {
        "title": "波動 σ（標準差）",
        "body": "報酬上下擺動的幅度，**越大越刺激、越小越穩**。"
                "實戰：低 σ 的擺核心（求穩），高 σ 的擺衛星（求攻）；"
                "σ 高又 Sharpe 低 = 白白冒險，優先汰換。",
    },
    "alpha": {
        "title": "Alpha 超額報酬",
        "body": "扣掉「大盤本來就該給的報酬」之後，經理人**額外多賺**的部分。"
                "**>0 有超額、<0 跑輸基準**。"
                "實戰：判斷主動式基金的經理人值不值得那筆管理費。",
    },
    "beta": {
        "title": "Beta 貝塔（對大盤的敏感度）",
        "body": "**1 = 跟大盤同步、>1 = 漲跌被放大、<1 = 抗跌也抗漲**。"
                "實戰：擔心升息/空頭想抗跌 → 選低 Beta；"
                "看多想衝刺 → 選高 Beta。",
    },
    "mdd": {
        "title": "最大回撤 MDD",
        "body": "從最高點摔到最低點的**最大跌幅**，代表「最慘要忍受多少帳面虧損」。"
                "實戰：MDD 超過你睡得著的底線就該減碼；它是設停損紀律的依據。",
        "short": "從最高點摔到最低點的最大跌幅，也就是最慘要忍受多少帳面虧損。",
    },
    "core_satellite": {
        "title": "核心 / 衛星配置",
        "body": "**核心（建議約 80%）求穩**（低波動、配息穩、長期持有）；"
                "**衛星（約 20%）求攻**（高成長、題材、波段操作）。"
                "實戰：核心顧住資產不大跌，衛星負責進攻——穩中求進、"
                "單一衛星出事也不傷筋動骨。",
    },
    "div_coverage": {
        "title": "配息覆蓋率（是否吃本金）",
        "body": "基金實際賺的，**夠不夠付它配出去的息**。"
                "**≥1 = 配息來自獲利（健康）；<1 = 部分配息其實在「吃本金」**。"
                "實戰：<1 又長期如此 → 淨值越配越薄，配息率再高也要警覺。",
        # ⛔ **刻意不寫線框那句「<1.0 就是在吃本金」。**
        #    那句話在**畫面上會與同一頁的警示卡打架**：⑥ 的「吃本金警示」判的是
        #    `alert_level == "red"`（近一年含息報酬**低於年化配息率超過 N 個百分點**，
        #    N 走 `shared/signal_thresholds.NEAR_DIVIDEND_WARNING_PCT`），
        #    **不是**「覆蓋 < 1.0」——覆蓋 0.95 的那一檔在卡片上是「接近警戒」，
        #    照線框那句話卻會被讀成「已經在吃本金」。
        #    **同一個組合、同一頁、兩個結論**，正是 `CLAUDE.md §2.1` 要擋的東西。
        #    ⇒ 只講**算術上一定成立**的那半（低於 1.0 ⇒ 有一部分配的是本金），
        #      **警示門檻留給卡片自己講**（它是從 SSOT 現場讀出來的）。
        "short": "配出來的錢有多少是真的賺到的，低於 1.0 就有一部分是配你自己的本金。",
    },
    "overlap": {
        "title": "重疊度 / 相關係數",
        "body": "兩檔基金的底層持股或走勢有多像。"
                "**≥0.7 = 影子基金（買兩檔約等於重押一檔）；0.4~0.7 中度；<0.4 才算分散**。"
                "實戰：要真正分散風險，挑重疊低的組合，避免「假分散、真集中」。",
    },
}


def explainer_markdown(keys) -> str:
    """把指定 keys 的教學文案組成 markdown 字串（純函式、可測）。未知 key 略過。"""
    parts: list[str] = []
    for _k in keys or []:
        item = METRIC_EXPLAINERS.get(_k)
        if item:
            parts.append(f"**{item['title']}**　{item['body']}")
    return "\n\n".join(parts)


def render_metric_explainer(keys, *, title: str = "💡 這些數據代表什麼？",
                            expanded: bool = False) -> None:
    """就近渲染一個收合的教學 expander；無對應內容時不渲染（不佔版面）。"""
    md = explainer_markdown(keys)
    if not md:
        return
    import streamlit as st
    with st.expander(title, expanded=expanded):
        st.markdown(md)
