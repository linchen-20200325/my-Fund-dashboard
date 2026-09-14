"""Q8 止血批次二：(A) 「➕ 加入組合」不再憑空捏一個級別寫回客戶 Sheet；
(B) 兩句畫面文案不再對客戶說假話。

## 讀這個檔之前請先知道：哪些條是真守衛，哪些不是

每條測試的 docstring 都標了它在 `origin/main`（`9cbf0377`，修復前）上是紅是綠：

* **「修復前紅」** ＝ 真的在守這次的修復，把修復拿掉會轉紅。
* **「修復前綠（回歸鎖）」** ＝ 現況本來就對，只防未來改壞。**不是**本次修復的證據。
* **「形態偵測」** ＝ 比對字串形狀，**可以被繞過**（換個說法就躲掉了）；
  留著是縱深防禦，真正 fail-closed 的是它隔壁那條語意斷言。

## ⚠️ 本檔涵蓋不到的那一半（誠實標註，不要誤讀本檔的綠燈）

A 修的是 `ui/helpers/portfolio/linkage.py` 那一行**憑空捏造**的 `"is_core": True`。
**「➕ 加入組合 → 📡 載入 → 全部寫入」這條路徑本檔管不到** ——
`ui/helpers/portfolio/load.py` 每次載入都會用基金名稱關鍵字再猜一個值蓋掉，
那一段是 **Q8 批次一（#842）** 的射程，本批不得動該檔。

`origin/main` @ `9cbf0377` 實測（指令見 PR 描述）：

| 路徑 | 科技型 | 配息型 |
|---|---|---|
| 加入 → 存檔（未載入） | `core` | `core` | ← **本批修掉的** |
| 加入 → 載入 → 存檔 | `satellite` | `core` | ← #842 修，本批未涵蓋 |
"""
from __future__ import annotations

import pytest

# 兩檔任何人都會同意分屬兩類的基金；配息型帶台灣基金依法幾乎都有的揭露字樣。
_TECH_FUND = "貝萊德世界科技基金A2(美元)"
_INCOME_FUND = "安聯收益成長基金AM穩定月收(基金之配息來源可能為本金)"

_GUESS_WORDING = "基金名稱關鍵字推定"   # 舊文案的那半句


# ══════════════════════════════════════════════════════════════════
# 共用假件（**只存在於本檔**，不進 repo、不碰 sys.modules）
# ══════════════════════════════════════════════════════════════════

class _FakeCol:
    """`st.columns()` 回傳的欄物件。`button()` 恆回 True ＝ 使用者按下去了。"""

    def markdown(self, *a, **k): pass

    def button(self, *a, **k): return True


class _FakeSt:
    """`ui/helpers/portfolio/linkage.py` 會用到的最小 streamlit 表面。

    走 `monkeypatch.setattr(linkage, "st", ...)` 只換那一個模組的 `st` 名字，
    **刻意不碰 `sys.modules['streamlit']`** —— 那會污染同一輪 collect 的其他測試
    （`conftest.py` 開頭記載過這個坑）。
    """

    def __init__(self): self.reran = False

    def markdown(self, *a, **k): pass

    def columns(self, spec, **k): return [_FakeCol() for _ in spec]

    def toast(self, *a, **k): pass

    def rerun(self, *a, **k): self.reran = True


def _add_via_button(monkeypatch, fund_name: str, code: str = "BGF-WT") -> dict:
    """跑真正的 `render_fund_portfolio_membership()`，回傳它 append 出來的那一筆。

    **不是手捏 dict** —— 整個 `➕ 加入組合` 分支（含防重複、`st.rerun`）真的跑過。
    """
    import ui.helpers.portfolio.linkage as _linkage

    _fake = _FakeSt()
    monkeypatch.setattr(_linkage, "st", _fake)
    # 先塞一筆不相干的持倉，讓 `_pf` 非空（空的話函式會直接 return）
    _ss = {"portfolio_funds": [{"code": "SEED", "name": "既有基金",
                                "invest_twd": 0, "is_core": False}]}
    _linkage.render_fund_portfolio_membership(_ss, [code], fund_name)

    assert _fake.reran, "前提：`➕ 加入組合` 那個分支真的跑到了（st.rerun 被呼叫）"
    _hit = [_f for _f in _ss["portfolio_funds"] if _f.get("code") == code]
    assert len(_hit) == 1, f"前提：真的 append 了一筆（實際 {len(_hit)} 筆）"
    return _hit[0]


def _tier_written_v1(monkeypatch, fund: dict) -> str:
    """跑真正的 v1 寫入路徑，回傳實際要寫進客戶 Sheet 的 `policy_tier`。"""
    from ui.helpers import cloud_io

    _rows: list[dict] = []
    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy",
                        lambda c, s, pid, row: _rows.append(row))
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version",
                        lambda *a, **k: "v1", raising=False)
    monkeypatch.setattr(cloud_io, "save_all_ledgers_snapshot", lambda *a, **k: 0)
    monkeypatch.setattr(cloud_io, "save_holdings_overview", lambda *a, **k: 0)

    _out = cloud_io.dump_all_to_sheet(
        "fake_client", "fake_sheet",
        {"portfolio_funds": [dict(fund, policy_id="P1")], "t7_ledgers": {}})
    assert _out["error"] is None, _out["error"]
    assert len(_rows) == 1, f"前提：這一筆真的被寫出去了（實際 {len(_rows)} 筆）"
    return _rows[0]["policy_tier"]


def _tier_written_v2(monkeypatch, fund: dict) -> str:
    """跑真正的 v2 寫入路徑，回傳實際要寫進客戶 Sheet 的 `tier`。"""
    from ui.helpers import cloud_io

    _seen: list = []
    monkeypatch.setattr(cloud_io, "write_policy_v2",
                        lambda c, s, pid, df: (_seen.append(df), 1)[1])
    _out = cloud_io._dump_all_to_sheet_v2(
        "fake_client", "fake_sheet",
        {"portfolio_funds": [dict(fund, policy_id="P1")], "t7_ledgers": {}})
    assert _out["error"] is None, _out["error"]
    assert len(_seen) == 1, f"前提：這一筆真的被寫出去了（實際 {len(_seen)} 筆）"
    return _seen[0]["tier"].tolist()[0]


# ══════════════════════════════════════════════════════════════════
# A. 「➕ 加入組合」不得替客戶決定級別
# ══════════════════════════════════════════════════════════════════

def test_add_to_portfolio_does_not_invent_a_tier(monkeypatch) -> None:
    """⭐ **修復前紅。** 加進組合的那一筆**不得帶任何級別**。

    `origin/main` 實測：append 出來的 dict 是 `{..., "is_core": True, ...}` ——
    使用者只說了「把這檔加進我的組合」，**從來沒說過它是核心**。
    """
    _entry = _add_via_button(monkeypatch, _TECH_FUND)

    assert "is_core" not in _entry, (
        f"「➕ 加入組合」替客戶捏了一個級別 is_core={_entry.get('is_core')!r}；"
        "這個值會被下一次「全部寫入」寫回客戶的 Google Sheet")
    # 其他欄位照舊 —— 證明不是整筆沒 append
    assert _entry["code"] == "BGF-WT"
    assert _entry["name"] == _TECH_FUND
    assert _entry["loaded"] is False
    assert _entry["invest_twd"] == 0


@pytest.mark.parametrize("fund_name", [_TECH_FUND, _INCOME_FUND])
def test_added_fund_writes_blank_tier_back_to_sheet_v1(
        monkeypatch, fund_name) -> None:
    """⭐⭐ **修復前紅 —— 本批最重要的一條（v1 schema）。**

    端到端：`➕ 加入組合` → `全部寫入`（中間**沒有**載入）。

    `origin/main` 實測：**兩檔都寫回 `'core'`**。客戶沒設定過，卻被寫了一個值進去。
    修復後：寫回 `''`（原樣的空白）。
    """
    _entry = _add_via_button(monkeypatch, fund_name)
    _tier = _tier_written_v1(monkeypatch, _entry)

    assert _tier == "", f"客戶沒設定過的級別被寫成 {_tier!r} 寫回了 Sheet"


@pytest.mark.parametrize("fund_name", [_TECH_FUND, _INCOME_FUND])
def test_added_fund_writes_blank_tier_back_to_sheet_v2(
        monkeypatch, fund_name) -> None:
    """⭐⭐ **修復前紅 —— 同上，v2 schema（`tier` 欄）。**"""
    _entry = _add_via_button(monkeypatch, fund_name)
    _tier = _tier_written_v2(monkeypatch, _entry)

    assert _tier == "", f"客戶沒設定過的級別被寫成 {_tier!r} 寫回了 Sheet"


def test_added_fund_leaves_the_holdings_overview_tier_blank(monkeypatch) -> None:
    """⭐ **修復前紅。** 第三個寫回面：`_持倉總覽` 分頁的「級別」欄。

    這張表是**給人直接打開 Google Sheet 看**的事實清單
    （`repositories/snapshot_repository.py` module docstring）。
    把「客戶還沒決定」印成「核心」，就是替客戶做了決定。
    """
    import repositories.snapshot_repository as _sr

    class _FakeWorksheet:
        rows = None

        def clear(self): pass

        def update(self, *a, **kw):
            _vals = kw.get("values")
            if _vals is None and len(a) >= 2:
                _vals = a[1]
            if _vals:
                type(self).rows = _vals

    class _Led:
        def to_dict(self):
            return {"fund_code": "BGF-WT", "currency": "USD",
                    "position": {"units": 1.0, "cost_unit": 10.0,
                                 "cost_unit_with_div": 10.0, "fx_avg": 32.0,
                                 "dividends_received_twd": 0.0}}

    _ws = _FakeWorksheet()
    monkeypatch.setattr(_sr, "_ensure_overview_worksheet", lambda c, s: _ws)

    _entry = _add_via_button(monkeypatch, _TECH_FUND)
    _sr.save_holdings_overview("c", "s", {"P1::BGF-WT": _Led()},
                               {"P1::BGF-WT": dict(_entry, policy_id="P1")})

    assert _ws.rows, "前提：真的寫出了列"
    assert _ws.rows[-1][4] == "", (
        f"`_持倉總覽` 的級別欄被填成 {_ws.rows[-1][4]!r}，客戶並沒有設定過")


def test_tier_is_identical_for_tech_and_income_fund_names(monkeypatch) -> None:
    """⭐ **修復前綠（回歸鎖）、但它是本批的「不受名稱影響」證明。**

    ⚠️ **誠實標註**：在 `origin/main` 上這一條**本來就是綠的** ——
    舊程式對兩個名稱都硬寫 `True`，兩邊「一致地錯」。
    所以它**不是**修復生效的證據（那是上面三條 parametrize 的工作）；
    它防的是**未來**有人把名稱啟發式加回這條路徑，讓兩個名稱開始分歧。

    真正把「一致」與「正確」綁在一起的是上面的
    `test_added_fund_writes_blank_tier_back_to_sheet_v1/v2`：
    它們同時要求**兩檔相同** ⋀ **兩檔都是 `''`**。
    """
    _tech = _add_via_button(monkeypatch, _TECH_FUND)
    _income = _add_via_button(monkeypatch, _INCOME_FUND)

    assert _tech.get("is_core") == _income.get("is_core")
    assert (_tier_written_v1(monkeypatch, _tech)
            == _tier_written_v1(monkeypatch, _income))
    assert (_tier_written_v2(monkeypatch, _tech)
            == _tier_written_v2(monkeypatch, _income))


# ══════════════════════════════════════════════════════════════════
# A2. 本批**已揭露的顯示副作用**（不是「想要的行為」，是「已知且刻意不修的」）
# ══════════════════════════════════════════════════════════════════

def test_added_fund_chip_label_flips_to_satellite_disclosed_side_effect(
        monkeypatch) -> None:
    """⚠️ **這一條不是在保護一個正確的行為，是在把一個已揭露的副作用釘成可執行的事實。**

    同一支 `render_fund_portfolio_membership` 裡，Tab2 聯動 chip 是**二態**：
    `"核心(穩健)" if _matched.get("is_core") else "衛星(積極)"`。
    本批拿掉捏造的 `"is_core": True` 之後，剛加入的基金標籤會**翻面**：

    * `origin/main` @ `9cbf0377`（實測）：`定位 核心(穩健)`
    * 本批之後（實測）：`定位 衛星(積極)`

    **兩個都不是事實** —— 真相是「客戶還沒設定過」。二態裝不下三態。

    ⭐ **機制的精確版（比「同一支函式所以會讀到」更準）**：`:50` 與被刪的那一行
    **分屬同一次呼叫的兩個互斥分支** —— 按下按鈕的那一次走的是 `else`（`_matched is None`），
    `定位` 標籤**根本沒有被渲染**；翻面出現在 **`st.rerun()` 之後的下一次呼叫**，
    那時該檔已在 `portfolio_funds` 裡、`_matched` 就是它。本條把兩次呼叫都跑過。

    ⛔ **本批刻意不修**：要正確顯示就得在畫面上新增第三種標籤，屬版面結構異動，
    依 `CLAUDE.md §-1.5.4` 必須先出線框草稿給客戶拍板。

    📌 **給未來修它的人**：線框拍板、三態顯示落地之後，**請直接改這一條**
    （改成斷言新的「未設定」標籤），不要刪掉它 —— 它的用途是讓這個副作用
    在任何一次改動中都看得見。
    """
    import re

    import ui.helpers.portfolio.linkage as _linkage

    _code = "BGF-WT"
    _ss = {"portfolio_funds": [{"code": "SEED", "name": "既有基金",
                                "invest_twd": 0, "is_core": False}]}

    def _render() -> list[str]:
        _out: list[str] = []

        class _Col:
            def markdown(self, html, *a, **k): _out.append(html)

            def button(self, *a, **k): return True

        class _St:
            reran = False

            def markdown(self, html, *a, **k): _out.append(html)

            def columns(self, spec, **k): return [_Col() for _ in spec]

            def toast(self, *a, **k): pass

            def rerun(self, *a, **k): type(self).reran = True

        monkeypatch.setattr(_linkage, "st", _St())
        _linkage.render_fund_portfolio_membership(_ss, [_code], _TECH_FUND)
        return _out

    def _tag(htmls: list[str]) -> str | None:
        for _h in htmls:
            _m = re.search(r"定位\s*([^<（]+)", _h)
            if _m:
                return _m.group(1).strip()
        return None

    # 第 1 次：使用者按下「➕ 加入組合」—— 走 else 分支，`定位` 不會被渲染
    assert _tag(_render()) is None, (
        "前提：按下按鈕的那一次走的是 `_matched is None` 分支，不該渲染 `定位`")
    assert any(_f.get("code") == _code for _f in _ss["portfolio_funds"]), \
        "前提：真的加進去了"

    # 第 2 次：`st.rerun()` 之後 —— 這次 `_matched` 就是剛加入的那一筆
    _label = _tag(_render())
    assert _label == "衛星(積極)", (
        f"chip 標籤是 {_label!r}。本批已揭露它會由「核心(穩健)」翻成「衛星(積極)」；"
        "若這裡變成第三種標籤，代表三態顯示落地了 —— 請確認線框草稿已經客戶拍板"
        "（`CLAUDE.md §-1.5.4`），然後更新本條")


# ══════════════════════════════════════════════════════════════════
# B. 兩句文案不得對客戶說假話
# ══════════════════════════════════════════════════════════════════

def _fund_read_from_sheet_v2_tier_column(monkeypatch, tier: str = "core") -> dict:
    """跑真正的 v2 讀取路徑，回傳「級別是客戶在 Sheet `tier` 欄親手填的」那一筆。

    **刻意不手捏 dict** —— 本組要證明的就是「這一筆確實出自 Sheet」，
    自己捏一個 `{"is_core": True}` 會把待證的前提直接假設掉。
    """
    from ui.helpers import cloud_io

    class _FakeDF:
        """只需要 `_load_all_from_sheet_v2` 用到的 DataFrame 介面。"""

        empty = False
        columns = ["policy_id", "fund_code", "tier"]

        def iterrows(self):
            yield 0, {"policy_id": "P1", "fund_code": "F1",
                      "fund_name": _TECH_FUND, "currency": "USD",
                      "tier": tier, "invest_twd": 100, "div_cash_pct": 100,
                      "units": 0, "avg_nav": 0, "avg_fx": 0}

        def __getitem__(self, k): return ["P1"]

    monkeypatch.setattr(cloud_io, "load_all_policies_v2", lambda c, s: _FakeDF())
    monkeypatch.setattr(cloud_io, "load_all_ledgers_snapshot", lambda *a, **k: {})

    _ss: dict = {"portfolio_funds": []}
    _out = cloud_io._load_all_from_sheet_v2("c", "s", _ss)
    assert _out["error"] is None, _out["error"]
    assert len(_ss["portfolio_funds"]) == 1, "前提：真的讀回了一筆"
    return _ss["portfolio_funds"][0]


def test_sheet_explicit_tier_is_not_described_as_a_name_guess(monkeypatch) -> None:
    """⭐ **修復前紅。** 客戶在 Sheet `tier` 欄**親手填**的級別，
    不得被文案說成「以基金名稱關鍵字推定」。

    機制：`n_tier_from_sheet` 只數 **v1** 的 `policy_tier` 欄；
    v2 讀取路徑把 `tier` 存進 `is_core`、**不寫** `policy_tier`
    ⇒ 這一檔被歸進「其餘」⇒ 舊文案宣稱它是猜出來的。

    ⚠️ 這條**與 #842 無關**：v2 讀取路徑在 `origin/main` 上就是這樣寫的。
    """
    from ui.components.allocation_donut_card import build_footnotes
    from ui.helpers.portfolio.allocation import (
        format_core_satellite_caption, summarize_core_satellite)

    _f = _fund_read_from_sheet_v2_tier_column(monkeypatch, "core")

    # 前提一：這一筆的級別確實出自客戶的 Sheet
    assert _f["is_core"] is True, "前提：Sheet 的 `tier` 欄真的被讀進來了"
    # 前提二：而 summary 並不知道它出自 Sheet —— 這正是舊文案說謊的原因
    _s = summarize_core_satellite([_f])
    assert _s["n_funds"] == 1
    assert _s["n_tier_from_sheet"] == 0, (
        "前提：v2 `tier` 欄讀回的級別不被 `n_tier_from_sheet` 計入")

    _caption = format_core_satellite_caption(_s)
    _notes = " ".join(build_footnotes(_s))

    assert _GUESS_WORDING not in _caption, (
        f"文案把客戶自己填的級別說成系統猜的：{_caption}")
    assert _GUESS_WORDING not in _notes, (
        f"腳註把客戶自己填的級別說成系統猜的：{_notes}")


def test_caption_and_footnote_disclose_that_unset_counts_as_satellite() -> None:
    """⭐ **修復前紅。** 「未設定」的錢被算進衛星，文案**必須講出來**。

    本條**兩段**：先用真正的 `summarize_core_satellite` 證明那筆錢確實落在衛星，
    再要求文案講出這件事。**第一段是語意鎖**：哪天有人把二態改掉，
    它會先紅，而不是讓文案默默變成新的假敘述。

    ⛔ 本批**不改**那個二態行為（改了就是動到畫面上的比例數字，
    屬版面／設計變更，依 `CLAUDE.md §-1.5.4` 要先出線框草稿）。本批只做揭露。
    """
    from ui.components.allocation_donut_card import build_footnotes
    from ui.helpers.portfolio.allocation import (
        format_core_satellite_caption, summarize_core_satellite)

    _s = summarize_core_satellite([
        {"policy_tier": "core", "invest_twd": 100},   # 明示核心
        {"is_core": None, "invest_twd": 300},         # 未設定
    ])

    # 第一段：未設定的 300 確實被算進衛星（而不是自成一類、也不是被丟掉）
    assert _s["core_twd"] == 100.0
    assert _s["sat_twd"] == 300.0, "未設定的金額沒有落在衛星 —— 二態行為變了"
    assert _s["core_pct"] == 25.0

    # 第二段：文案必須把這件事講出來
    _caption = format_core_satellite_caption(_s)
    _notes = " ".join(build_footnotes(_s))
    for _where, _text in (("caption", _caption), ("footnote", _notes)):
        assert "未設定" in _text and "衛星" in _text, (
            f"{_where} 沒有揭露「未設定的金額被算進衛星」：{_text}")


def test_footnote_says_the_two_slice_donut_cannot_show_unset() -> None:
    """⭐ **修復前紅。** 圓環恆 2 片（既有裁決），所以「還沒決定」在圖上看不見。

    這是**本元件特有**的揭露義務：caption 底下沒有圖，腳註底下有 ——
    客戶看著一張只有兩片的圖，不講就會把「衛星 X%」讀成「我有 X% 的衛星」。
    """
    from ui.components.allocation_donut_card import build_footnotes
    from ui.helpers.portfolio.allocation import summarize_core_satellite

    _notes = " ".join(build_footnotes(summarize_core_satellite(
        [{"policy_tier": "core", "invest_twd": 100},
         {"is_core": None, "invest_twd": 300}])))

    assert "兩片" in _notes, f"腳註沒講這張圖只有兩片：{_notes}"
    assert "還沒決定" in _notes, f"腳註沒講「還沒決定」看不出來：{_notes}"


def test_no_leftover_group_is_described_when_every_tier_is_explicit() -> None:
    """⭐ **修復前紅。** 全部級別都 Sheet 明示時，不得描述一個不存在的群組。

    `origin/main` 實測：舊文案會輸出「**其餘 0 檔**以基金名稱關鍵字推定」。
    """
    from ui.components.allocation_donut_card import build_footnotes
    from ui.helpers.portfolio.allocation import (
        format_core_satellite_caption, summarize_core_satellite)

    _s = summarize_core_satellite([{"policy_tier": "core", "invest_twd": 100},
                                   {"policy_tier": "satellite", "invest_twd": 300}])
    assert _s["n_tier_from_sheet"] == _s["n_funds"] == 2, "前提：兩檔都明示"

    _caption = format_core_satellite_caption(_s)
    assert "其餘" not in _caption, f"描述了一個不存在的群組：{_caption}"
    assert "0 檔" not in _caption, f"描述了一個不存在的群組：{_caption}"
    assert build_footnotes(_s) == [], "沒有任何「非明示」的基金，不該有那條腳註"


def test_caption_counts_come_from_the_summary_not_from_a_constant() -> None:
    """**修復前綠（回歸鎖）。** 文案裡的 `k/n` 必須跟著 summary 走。

    存在理由：本批改的是**文案**，最容易犯的錯是把數字寫死或算錯，
    讓一句讀起來很誠實的話配上一組錯的數字。
    """
    from ui.helpers.portfolio.allocation import (
        format_core_satellite_caption, summarize_core_satellite)

    _funds = ([{"policy_tier": "core", "invest_twd": 10}] * 2
              + [{"is_core": None, "invest_twd": 10}] * 3)
    _s = summarize_core_satellite(_funds)
    assert (_s["n_tier_from_sheet"], _s["n_funds"]) == (2, 5), "前提：2/5 明示"

    _caption = format_core_satellite_caption(_s)
    assert "2/5 檔" in _caption, f"明示檔數與 summary 不符：{_caption}"
    assert "其餘 3 檔" in _caption, f"其餘檔數與 summary 不符：{_caption}"


def test_old_guess_wording_is_gone_from_both_sites() -> None:
    """**形態偵測，可被繞過**（換個說法就躲掉了）—— 誠實標註，不要當主要保證。

    真正 fail-closed 的是
    :func:`test_sheet_explicit_tier_is_not_described_as_a_name_guess`
    （它驗的是**實際算出來的那一檔**）。本條只是讓「有人把那半句貼回去」
    在 code review 之前就先紅。
    """
    from ui.components.allocation_donut_card import build_footnotes
    from ui.helpers.portfolio.allocation import (
        format_core_satellite_caption, summarize_core_satellite)

    for _funds in ([{"is_core": None, "invest_twd": 0}],
                   [{"is_core": None, "invest_twd": 100}],
                   [{"policy_tier": "core", "invest_twd": 100},
                    {"is_core": False, "invest_twd": 100}]):
        _s = summarize_core_satellite(_funds)
        _text = format_core_satellite_caption(_s) + " " + " ".join(build_footnotes(_s))
        assert _GUESS_WORDING not in _text, f"舊的假敘述又出現了：{_text}"
