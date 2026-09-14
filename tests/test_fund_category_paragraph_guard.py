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

# 比 15 長、但確實是標籤的真實類別名 —— **門檻低側的唯一保護**。
# ⚠️ 語料只有 32 個名字,窄到撐不起「低側也有餘裕」;稽核用 repo 內既有詞彙就構造出
#    36 / 39 字的合理類別名(距門檻只差 1)。所以低側**不靠餘裕,靠這個清單**。
# ⚠️ 新增更長的合法類別名時,**必須加進這裡** —— 只重跑測試沒有用,
#    清單沒動,test_threshold_window_* 與 test_known_long_but_legitimate_labels_survive
#    都看不到新標籤,照樣全綠。
_LEGIT_LONG_LABELS = [
    "已開發市場非投資等級公司債券基金",              # 16
    "已開發市場(不含美國)非投資等級公司債券基金",      # 22
    "新興市場當地貨幣計價政府公債證券投資信託基金",     # 22
    "全球區塊鏈及金融科技相關產業股票證券投資信託基金",  # 24
]

# 公開說明書段落的**自稱語**。用它挑樣本,是為了得到一組**不隨門檻移動**的毒樣本。
_PROSPECTUS_MARKER = "本基金"


def _snapshot_categories() -> list[tuple[str, str]]:
    """snap.json → [(fund_code, category)]。唯讀,不打網路。"""
    data = json.loads(_SNAP.read_text(encoding="utf-8"))
    return [(c, (r.get("category") or "")) for c, r in data["funds"].items()]


def _prospectus_categories() -> list[tuple[str, str]]:
    """語料中的「說明書段落」—— ⭐ **用內容挑,不用長度挑**。

    這是本檔唯一一組**不隨 `CATEGORY_PARAGRAPH_MIN_LEN` 移動**的樣本,存在理由見
    `test_threshold_window_is_pinned_by_corpus_not_by_itself` 的 docstring。
    """
    return [(c, t) for c, t in _snapshot_categories() if _PROSPECTUS_MARKER in t]


def _probe_of_length(n: int) -> str:
    """長度**恰為 n**、且保證含桶關鍵字(「股票」)的合成探針。

    填充字「文」刻意不屬於任何 ASSET_BUCKETS 關鍵字,避免探針意外命中別的桶;
    這一點由 test_boundary_length_equal_to_threshold_is_refused 的反空轉斷言現場驗。
    """
    stem = "股票"
    assert n >= len(stem), f"探針長度 {n} 小於字根 {len(stem)}"
    return stem + "文" * (n - len(stem))


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


# ── ⭐ B2:不隨門檻移動的斷言(本檔其餘多數斷言都會跟著門檻一起移動)──

def test_prospectus_selector_is_content_based_and_finds_the_poison():
    """反空轉:內容選擇器必須真的選到段落、且不誤中合法標籤。"""
    sel = _prospectus_categories()
    assert sel, f"內容選擇器 {_PROSPECTUS_MARKER!r} 選不到任何樣本 —— 下面兩條會空轉"
    assert min(len(t) for _, t in sel) > _LABEL_MAX, "選到的不是段落,是短標籤"
    for lab in _LEGIT_LONG_LABELS:
        assert _PROSPECTUS_MARKER not in lab, f"選擇器誤中合法標籤:{lab}"


def test_every_prospectus_paragraph_is_refused():
    """⭐ 真正的安全性質:**每一段**說明書描述都必須被拒絕分類。

    樣本由 `_prospectus_categories()` 以**內容**選出,與門檻完全脫鉤 ——
    門檻一旦調高到某段落長度之上,那一段就會漏回關鍵字比對,本條立刻紅。
    """
    for code, cat in _prospectus_categories():
        got = asset_bucket(cat)
        assert got == (None, None), (
            f"{code}({len(cat)} 字)的說明書段落被分到「{got[0]}」桶 —— "
            f"門檻 CATEGORY_PARAGRAPH_MIN_LEN={CATEGORY_PARAGRAPH_MIN_LEN} 太高,擋不住它")


def test_threshold_window_is_pinned_by_corpus_not_by_itself():
    """⭐ 門檻必須落在 (最長合法標籤, 最短毒段落] 這個窗內。

    **這條為什麼非有不可**(2026-09-14 第二輪回修;稽核實測):
    本檔多數斷言用 `len(t) >= CATEGORY_PARAGRAPH_MIN_LEN` **挑樣本**,而實作
    `asset_bucket` 的分支條件是**同一個常數**。⇒ **門檻一調高,樣本自己縮小,
    球門跟著球一起移動。** 實測後果:把 40 改成 300,守衛仍 **11 passed**,
    但 ACCP138(266)與 ACTI71(268)**實際漏過去**被分桶。
    當時真正釘住門檻的只有 `[25, 383]`(383 才踩到那條**用內容挑樣本**的台股斷言),
    而安全區間其實是 `[25, 266]` ⇒ **267~383 共 117 個值是「全綠但有毒」。**

    本條與 `test_every_prospectus_paragraph_is_refused` 都**不碰**那個常數來挑樣本,
    所以門檻往上調會**立刻**紅。
    """
    longest_legit = max(len(x) for x in _LEGIT_LONG_LABELS)
    poisons = _prospectus_categories()
    assert poisons, "沒有毒樣本,本條會空轉"
    shortest_poison = min(len(t) for _, t in poisons)
    assert longest_legit < shortest_poison, (
        f"語料本身已經無法用長度分開:最長合法 {longest_legit} >= 最短毒 {shortest_poison}")
    assert longest_legit < CATEGORY_PARAGRAPH_MIN_LEN <= shortest_poison, (
        f"門檻 {CATEGORY_PARAGRAPH_MIN_LEN} 落在安全窗 "
        f"({longest_legit}, {shortest_poison}] 之外:"
        f"太低會誤殺合法標籤,太高會放毒段落過去")


def test_boundary_length_equal_to_threshold_is_refused():
    """邊界語意:長度**恰等於**門檻即視為段落(`>=`,不是 `>`)。

    專殺 off-by-one。語料裡**沒有任何一筆長度剛好等於門檻**,所以少了這條,
    把實作的 `>=` 改成 `>` 會完全測不出來(稽核實測:該突變存活,11 passed)。
    """
    n = CATEGORY_PARAGRAPH_MIN_LEN
    below, at = _probe_of_length(n - 1), _probe_of_length(n)
    assert (len(below), len(at)) == (n - 1, n), "探針長度不對,本條會驗錯東西"
    # 反空轉:探針本身必須是「分得到桶」的,否則下面那條 None 沒有意義
    assert asset_bucket(below)[0] == "股票", (
        f"門檻以下的探針分不到桶(得 {asset_bucket(below)[0]})—— 本條會空轉")
    assert asset_bucket(at) == (None, None), (
        f"長度恰等於門檻({n})必須被視為段落;現在回 {asset_bucket(at)[0]} "
        f"⇒ 實作的比較可能被改成了 `>`")


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

    # ACDD19 型的「短片段」:它回 None 必須是**關鍵字未命中**,不是段落守衛所致。
    # ⚠️ 2026-09-14 第二輪回修:舊版寫成
    #       frag = [... if 0 < len(t) <= _LABEL_MAX ...]
    #       assert len(t) < CATEGORY_PARAGRAPH_MIN_LEN
    #    ——`_LABEL_MAX` 是硬寫的 15、門檻是 40 ⇒ `15 < 40` **在出貨值下恆真**,
    #    整段**驗不到任何東西**(稽核實測:常數要降到 ≤12 才會動)。
    #    現改為真對照:**把守衛整個關掉,它仍須回 None**。
    frag = [(c, t) for c, t in _snapshot_categories()
            if 0 < len(t) < CATEGORY_PARAGRAPH_MIN_LEN and asset_bucket(t)[0] is None]
    assert frag, "語料裡沒有『短且關鍵字未命中』的樣本 —— 本段具名對照失效(ACDD19 不見了?)"
    for code, t in frag:
        _rf.CATEGORY_PARAGRAPH_MIN_LEN = 10 ** 9      # 等效於關掉守衛
        try:
            assert _rf.asset_bucket(t)[0] is None, (
                f"{code}: 關掉守衛後反而分得到桶 ⇒ 它的 None 是守衛造成的,"
                f"不是關鍵字未命中")
        finally:
            _rf.CATEGORY_PARAGRAPH_MIN_LEN = _saved


def test_known_long_but_legitimate_labels_survive():
    """對抗性:比 15 長、但確實是標籤的真實類別名,不得被擋。

    量測日 2026-09-14:語料中最長的合法標籤 24 字;最短的毒段落 266 字。
    門檻 40 落在這個空帶內 —— 這也是本防線**不沿用** `_pick_fund_category` 的 15 的原因
    (15 會誤殺 `_LEGIT_LONG_LABELS` 那 4 個)。

    ⚠️ 清單已於 2026-09-14 第二輪回修上移為模組常數 `_LEGIT_LONG_LABELS`,
    因為 `test_threshold_window_is_pinned_by_corpus_not_by_itself` 也要用它定低側邊界。
    **新增合法長標籤請加在那裡**;不加就等於沒測到。
    """
    for cat in _LEGIT_LONG_LABELS:
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


def test_later_write_never_puts_a_paragraph_into_category(monkeypatch):
    """後面那一行寫進 `category` 的**不得是長描述**(waterfall 已有乾淨值時也一樣)。

    ⚠️ **2026-09-14 第二輪回修改名 + 射程寫明**(原名
    `test_produced_category_is_not_clobbered_by_later_write`)。
    舊名宣稱的比它驗的多:聽起來像「waterfall 的值會被保護」,**但並沒有**。
    實測:waterfall 給「平衡型」、頁面「基金類型」給「股票型」→ head 最終寫成
    **「股票型」**,waterfall 的值**確實被蓋掉**。
    那一行是**無條件覆寫**(`result["category"] = _pick_fund_category(rows_map)`),
    本批**沒有**改動它 —— 那是既有行為、**非本 PR 引入**,也不在本批射程內。
    **本條只保證一件事:蓋上去的值是標籤形狀,不是段落。**
    留舊名會讓後人以為「無條件覆寫已經被防住了」,故改名。
    """
    poison = _poison_text()
    res = _run_fetch(monkeypatch, poison, "股票型",
                     {"fund_name": "測試基金A", "nav_latest": 10.0, "category": "股票型"})
    cat = res.get("category") or ""
    assert len(cat) <= _LABEL_MAX, f"乾淨類別被長描述蓋掉了({len(cat)} 字)"
    assert asset_bucket(cat)[0] != "原物料資源"


def test_meta_block_survives_no_silent_nameerror(monkeypatch):
    """`_pick_fund_category` 定義在 `sources.py`,靠 **`sources.__all__`** 被 `import *` 帶進來。

    ⚠️ **2026-09-14 第二輪回修:本 docstring 原文兩句都是假的**(有意識的更正,不是漏刪)。
    原文寫「它**不在** `sources.__all__` 內」「`import *` 帶不進來」「若忘了**顯式 import**
    就會拋 NameError」—— 實測 head:它**就在** `sources.__all__` 裡,而且全檔**沒有**
    任何顯式 import。那是本 PR **第一版**(顯式 import 方案)的機制;`6df1951` 已改走
    `__all__`,同一批把該名字加進 `sources.__all__` 並**刪掉**那行顯式 import,
    卻**只改了 `fund_orchestration.py` 的註解,漏掉這裡**。
    ⛔ 原文更糟的一點:它會把下一個人推向 PR body 自己明文禁止的動作
    (「**不得改用顯式 import 繞過**」)。

    **現行機制**:底線名不被 `from ... import *` 預設帶入,所以它**必須列在
    `sources.__all__`**(v19.248 R17 守衛 `tests/test_sources_star_export.py` 強制此約定)。
    一旦從 `__all__` 拿掉,該行就拋 `NameError`,而外層 `except Exception as e: print(...)`
    會把它**完整吞掉** —— 結果是 category 之後的整段 meta(fund_type / investment_target /
    mgmt_fee / TER…)**靜默消失**。本條釘住的就是那個失效模式。
    """
    res = _run_fetch(monkeypatch, _poison_text(), "股票型", {})
    assert res.get("fund_type") == "股票型", (
        "category 之後的 meta 沒寫進來 —— 極可能是該行拋例外被上層吞掉了")
    assert res.get("fund_region") == "台灣", "fund_region 缺失,同上"
