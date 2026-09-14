"""基金類別「段落形狀」防線 — 2026-09-14。

修的線上錯誤分類:MoneyDJ 的「投資標的」欄有時填的是**公開說明書長描述**
(一整段法律文字),被當成 `category` 寫進 result。`services/regime_fit.asset_bucket`
是**子字串首命中**,桶序把「最特定」排前面,於是:

    ACDD01(台股股票基金):「股票」出現在 position 20(真正的類別),
                          「商品」出現在 position 175(只是被允許的一項工具)
    → 桶序 原物料資源 在 股票 之前 ⇒ **結構上保證撿到錯的那個**,不是碰巧。

兩道防線,本檔都驗:
1. **源頭**:`fund_orchestration.fetch_fund_from_moneydj_url` 改吃 `_pick_fund_category`
   (v19.419 已拍板的修法,補到它漏掉的第三個寫入點)。
2. **縱深**:`asset_bucket` 入口擋段落形狀(`CATEGORY_PARAGRAPH_MIN_LEN`)——
   因為 `category` 不只一個生產者,任一處漏掉清洗,這一層還擋得住。

⚠️ 語料**一律從 `snap.json` 讀**,不手抄第二份(§2.1 SSOT:手抄的會與實際資料漂移)。
"""
from __future__ import annotations

import json
import pathlib

import fund_fetcher  # noqa: F401 — conftest 同款 prime,見 tests/conftest.py

from repositories.fund.sources import _pick_fund_category
from services.regime_fit import CATEGORY_PARAGRAPH_MIN_LEN, asset_bucket

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SNAP = _ROOT / "snap.json"

# `_pick_fund_category` 的標籤上限(該函式內的 `0 < len(_it) <= 15`)。
# 刻意在此重述而非 import:那是它的內部字面值,不是公開常數。若上游改動,
# test_produced_category_satisfies_pick_helper_contract 會直接紅。
_LABEL_MAX = 15


def _snapshot_categories() -> list[tuple[str, str]]:
    """snap.json → [(fund_code, category)]。唯讀,不打網路。"""
    data = json.loads(_SNAP.read_text(encoding="utf-8"))
    return [(c, (r.get("category") or "")) for c, r in data["funds"].items()]


# ── 反空轉:語料本身必須有料,否則下面每一條都會「因為沒東西可驗」而變成綠燈 ──

def test_snapshot_corpus_is_not_empty():
    assert _SNAP.exists(), f"語料不存在:{_SNAP}"
    cats = _snapshot_categories()
    assert len(cats) >= 5, f"語料過小({len(cats)}),下面的斷言會空轉"


def test_snapshot_corpus_contains_paragraph_shaped_poison():
    """至少要有一筆是段落形狀 —— 否則『擋段落』的斷言驗不到任何東西。"""
    paras = [(c, t) for c, t in _snapshot_categories()
             if len(t) >= CATEGORY_PARAGRAPH_MIN_LEN]
    assert paras, "語料裡沒有任何段落形狀的 category,防線斷言將空轉"
    assert max(len(t) for _, t in paras) > 200, "段落樣本太短,不具代表性"


def test_snapshot_corpus_contains_clean_short_labels():
    """也要有乾淨標籤 —— 否則『不得誤殺』的正對照驗不到任何東西。"""
    shorts = [(c, t) for c, t in _snapshot_categories() if 0 < len(t) <= _LABEL_MAX]
    assert shorts, "語料裡沒有乾淨短標籤,誤殺正對照將空轉"


# ── 防線 2:段落形狀 → 誠實 None ──

def test_paragraph_shaped_category_returns_none():
    for code, cat in _snapshot_categories():
        if len(cat) >= CATEGORY_PARAGRAPH_MIN_LEN:
            assert asset_bucket(cat) == (None, None), (
                f"{code}: {len(cat)} 字的段落被當成類別分桶了 → {asset_bucket(cat)[0]}")


def test_taiwan_equity_prospectus_is_not_bucketed_as_commodity():
    """本案的具體病徵:台股股票基金被判成『原物料資源』(命中段落深處的「商品」)。"""
    hits = [(c, t) for c, t in _snapshot_categories()
            if "上市及上櫃股票" in t or "上櫃公司股票" in t]
    assert hits, "語料裡找不到台股股票型的說明書段落,本條會空轉"
    for code, cat in hits:
        name = asset_bucket(cat)[0]
        assert name != "原物料資源", f"{code}: 台股股票基金仍被判成原物料資源"
        assert name is None, f"{code}: 段落不該被分到任何桶,實得 {name}"


# ── 正對照:不得誤殺乾淨標籤(擋住「守衛改成一律回 None」的假綠燈)──

def test_clean_short_labels_still_classify():
    """守衛不得退化成『一律回 None』—— 乾淨標籤必須照樣分得到桶。"""
    shorts = [(c, t) for c, t in _snapshot_categories() if 0 < len(t) <= _LABEL_MAX]
    classified = [(c, t) for c, t in shorts if asset_bucket(t)[0] is not None]
    assert classified, "沒有任何乾淨短標籤分得到桶 —— 守衛可能把所有東西都擋掉了"
    # 具名正對照(snap.json 實際值)
    assert asset_bucket("平衡型")[0] == "平衡多重"
    assert asset_bucket("股票型")[0] == "股票"


def test_guard_does_not_fire_below_threshold():
    """射程界定:短字串一律不經段落守衛,結果只由關鍵字比對決定。

    ACDD19 的 category 是 12 字的說明書**片段**(`中華民國境內之有價證券。`),
    它 < 門檻 ⇒ 守衛不介入;它回 None 是**既有的關鍵字未命中**(§1 誠實 None),
    不是本批造成的,本批也不宣稱修好它(那屬 SATELLITE_KEYWORDS 的另案)。
    """
    import services.regime_fit as _rf
    _saved = _rf.CATEGORY_PARAGRAPH_MIN_LEN
    try:
        for code, cat in _snapshot_categories():
            if not (0 < len(cat) < CATEGORY_PARAGRAPH_MIN_LEN):
                continue
            with_guard = asset_bucket(cat)
            _rf.CATEGORY_PARAGRAPH_MIN_LEN = 10 ** 9      # 等效於關掉守衛
            without_guard = _rf.asset_bucket(cat)
            _rf.CATEGORY_PARAGRAPH_MIN_LEN = _saved
            assert with_guard == without_guard, (
                f"{code}: 門檻以下的字串不該受守衛影響,"
                f"開={with_guard[0]} 關={without_guard[0]}")
    finally:
        _rf.CATEGORY_PARAGRAPH_MIN_LEN = _saved

    frag = [t for _, t in _snapshot_categories()
            if 0 < len(t) <= _LABEL_MAX and asset_bucket(t)[0] is None]
    if frag:                       # 目前有一筆(ACDD19);沒有也不算錯
        for t in frag:
            assert len(t) < CATEGORY_PARAGRAPH_MIN_LEN, (
                f"{t!r} 回 None 應該是關鍵字未命中,不該是段落守衛所致")


def test_known_long_but_legitimate_labels_survive():
    """對抗性:比 15 長、但確實是標籤的真實類別名,不得被擋。

    量測日 2026-09-14:語料中最長的合法標籤 24 字;最短的毒段落 266 字。
    門檻 40 落在這個空帶內 —— 這也是本防線**不沿用** `_pick_fund_category` 的 15 的原因
    (15 會誤殺下列 4 個)。
    """
    legit = [
        "已開發市場非投資等級公司債券基金",              # 16
        "已開發市場(不含美國)非投資等級公司債券基金",      # 22
        "新興市場當地貨幣計價政府公債證券投資信託基金",     # 22
        "全球區塊鏈及金融科技相關產業股票證券投資信託基金",  # 24
    ]
    for cat in legit:
        assert len(cat) > _LABEL_MAX, f"{cat} 沒有比 {_LABEL_MAX} 長,本條失去對抗性"
        assert asset_bucket(cat)[0] is not None, f"合法長標籤被誤殺:{cat}"


# ── 防線 1:源頭產出的 category 必須是標籤形狀(驗行為,不驗那一行的字面)──

class _Resp:
    def __init__(self, text: str) -> None:
        self.text = text
        self.status_code = 200

    @property
    def content(self) -> bytes:
        return self.text.encode()


def _info_page(long_target: str, fund_type: str) -> str:
    rows = [("基金名稱", "測試基金A"), ("計價幣別", "TWD"),
            ("投資標的", long_target), ("基金類型", fund_type),
            ("投資區域", "台灣"), ("風險報酬等級", "RR5")]
    trs = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)
    # 尾端填充:該路徑要求 len(r.text) > 500 才會解析
    return "<html><body><table>" + trs + "</table></body></html>" + ("&nbsp;" * 400)


def _run_fetch(monkeypatch, long_target: str, fund_type: str, ms_result: dict) -> dict:
    import repositories.fund.fund_orchestration as FO

    monkeypatch.setattr(FO, "fetch_url_with_retry",
                        lambda u, **k: _Resp(_info_page(long_target, fund_type)))
    monkeypatch.setattr(FO, "fetch_fund_multi_source", lambda *a, **k: dict(ms_result))
    for n in ("fetch_holdings", "fetch_risk_metrics", "fetch_performance_wb01",
              "fetch_dividends", "fetch_nav"):
        if hasattr(FO, n):
            monkeypatch.setattr(FO, n, lambda *a, **k: {}, raising=False)
    if hasattr(FO, "_ensure_holdings"):
        monkeypatch.setattr(FO, "_ensure_holdings", lambda *a, **k: None, raising=False)
    return FO.fetch_fund_from_moneydj_url("ACDD01")


def _poison_text() -> str:
    """從 snap.json 取一段真實說明書描述當輸入(不手抄)。"""
    cands = [t for _, t in _snapshot_categories() if len(t) >= CATEGORY_PARAGRAPH_MIN_LEN]
    assert cands, "沒有真實段落可用,本條會空轉"
    return max(cands, key=len)


def test_produced_category_satisfies_pick_helper_contract(monkeypatch):
    """源頭寫出的 category 必須通過 `_pick_fund_category` 的形狀契約。"""
    poison = _poison_text()
    res = _run_fetch(monkeypatch, poison, "股票型", {})
    cat = res.get("category") or ""

    assert cat != poison, "長描述仍被原封寫進 category"
    assert len(cat) <= _LABEL_MAX, f"category 仍是段落形狀({len(cat)} 字):{cat[:40]!r}"
    # 驗行為:與 helper 對同一份 rows_map 的裁決一致
    assert cat == _pick_fund_category({"投資標的": poison, "基金類型": "股票型"})
    assert asset_bucket(cat)[0] == "股票", "清洗後應能正確分到股票桶"


def test_produced_category_is_not_clobbered_by_later_write(monkeypatch):
    """waterfall 已經拿到乾淨類別時,後面那一行不得把它蓋回長描述。"""
    poison = _poison_text()
    res = _run_fetch(monkeypatch, poison, "股票型",
                     {"fund_name": "測試基金A", "nav_latest": 10.0, "category": "股票型"})
    cat = res.get("category") or ""
    assert len(cat) <= _LABEL_MAX, f"乾淨類別被長描述蓋掉了({len(cat)} 字)"
    assert asset_bucket(cat)[0] != "原物料資源"


def test_meta_block_survives_no_silent_nameerror(monkeypatch):
    """`_pick_fund_category` 是底線名、不在 sources.__all__ 內 —— `import *` 帶不進來。

    若忘了顯式 import,該行會拋 NameError,而外層 `except Exception as e: print(...)`
    會把它**完整吞掉**,結果是 category 之後的整段 meta(fund_type / investment_target /
    mgmt_fee / TER…)靜默消失。本條就是釘住那個失效模式。
    """
    res = _run_fetch(monkeypatch, _poison_text(), "股票型", {})
    assert res.get("fund_type") == "股票型", (
        "category 之後的 meta 沒寫進來 —— 極可能是該行拋例外被上層吞掉了")
    assert res.get("fund_region") == "台灣", "fund_region 缺失,同上"
