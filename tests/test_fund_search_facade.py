"""L2 搜尋 facade（`services/fund_search.py`）的契約守衛。

本檔守什麼、不守什麼（先講清楚）
--------------------------------
守的是 **facade 的四個承諾**，一句都不是形容詞：

1. **thin** —— L1 回什麼，它就回什麼（不排序、不去重、不截斷、不改欄位）；
2. **fail loud** —— 空白關鍵字、契約型別不符、L1 拋例外，三種都**炸出來**，
   ⛔ 不得收成 `[]`（那會讓「查詢失敗」長得跟「查無結果」一模一樣，§1）；
3. **不加快取** —— 呼叫兩次就真的走兩次 L1（兩層 TTL 疊加＝失效語意不可推理）；
4. **空清單的含混要被說出來** —— :data:`services.fund_search.EMPTY_MEANS_UNKNOWN`。

⛔ **本檔不守 L1 的行為**（TDCC / FundClear 真的回什麼、關鍵字怎麼比對）——
   那是 `repositories/fund/sources.py` 的事，在這裡再驗一次就是第二把尺。

⚠️ **本檔一次都不打外部網路。** L1 一律以 `sys.modules` 注入的假模組取代
（facade 是 **lazy import**，所以注入必須在**呼叫時**生效，不是 import 時）。
⛔ 不要改成「真的去打一次看看」—— 一份會連外網的守衛在 CI 上是不可重現的：
它紅不紅取決於當天上游活著沒有。

⚠️ **本檔的宣稱由資料工程組單組產出，未經第二組獨立驗證**（`CLAUDE.md §-2` 規則 6）。
"""
from __future__ import annotations

import ast
import contextlib
import pathlib
import sys
import types
from typing import Any

import pytest

from services.fund_search import (
    EMPTY_MEANS_UNKNOWN,
    KEY_AGENT,
    KEY_CODE,
    KEY_NAME,
    KEY_NAV,
    KEY_NAV_DATE,
    KEY_SOURCE,
    RESULT_KEYS,
    search_funds,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "services" / "fund_search.py"


@contextlib.contextmanager
def _fake_l1(fn):
    """把 `repositories.fund.tdcc_search_fund` 換成 `fn`，離開時原樣還原。

    ⚠️ **注入的是整個模組物件**，不是 `setattr` 到真的那一個 —— 真的那一個
    在載入期就會拉起 `bs4` 等抓取相依鏈，而本檔要在**任何環境**都跑得起來
    （facade 自己是 lazy import，這一點才成立）。
    """
    _mod = types.ModuleType("repositories.fund")
    _mod.tdcc_search_fund = fn                      # type: ignore[attr-defined]
    _prev = sys.modules.get("repositories.fund")
    sys.modules["repositories.fund"] = _mod
    try:
        yield
    finally:
        if _prev is None:
            sys.modules.pop("repositories.fund", None)
        else:
            sys.modules["repositories.fund"] = _prev


def _rows(n: int = 2) -> list[dict]:
    return [{KEY_NAME: f"哨兵基金{_i}", KEY_CODE: f"SENTINEL{_i}",
             KEY_AGENT: f"哨兵總代理{_i}", KEY_NAV: f"{40 + _i}.11",
             KEY_NAV_DATE: "2026/09/05", KEY_SOURCE: "TDCC-3-2"}
            for _i in range(n)]


# ══════════════════════════════════════════════════════════════════
# 1) thin —— L1 回什麼就回什麼
# ══════════════════════════════════════════════════════════════════

def test_the_rows_come_back_exactly_as_the_repository_gave_them():
    """順序、筆數、欄位**逐一相同**，而且**是同一批 dict 物件**。

    ⚠️ 用 `is` 比對物件身分，不是 `==` 比對內容：`==` 在「facade 自己重建了一份
    看起來一樣的 dict」時照樣通過，而重建正是「悄悄多做了一步加工」的入口。
    """
    _src = _rows(3)
    with _fake_l1(lambda _kw: _src):
        _out = search_funds("哨兵")
    assert _out is _src or [id(_r) for _r in _out] == [id(_r) for _r in _src], (
        "facade 重建了結果列 —— 它應該是 thin 的（L1 回什麼就回什麼）。")
    assert len(_out) == 3, f"筆數被動過：{len(_out)}"


def test_the_facade_does_not_sort_dedupe_or_truncate():
    """⛔ 不排序、不去重、不截斷 —— 三種加工都是「第二份真相源」（§2.1）。

    ⚠️ 去重與 NAV 併入**已經在 L1 做完**（`tdcc_search_fund` 的 `seen` 集合）；
    在這裡再做一次，兩邊的規則哪天不一致，畫面上看不出是誰的錯。
    ⚠️ 截斷屬**版面決定**，它的家在 UI
    （`ui/views/page_03_research.py::MAX_RESULT_CARDS`，那裡會把總筆數講出來）。
    """
    _dupe = _rows(1) * 4 + _rows(2)[::-1]
    with _fake_l1(lambda _kw: list(_dupe)):
        _out = search_funds("哨兵")
    assert _out == _dupe, (
        "結果被排序／去重／截斷了 —— facade 應該是 thin 的。\n"
        f"進：{_dupe}\n出：{_out}")


def test_the_keyword_is_stripped_but_not_otherwise_rewritten():
    """前後空白去掉，其餘**原封送出** —— 大小寫、全形、網址都不准動。

    ⚠️ L1 的比對是 `keyword.lower() in name.lower()`，**已經是大小寫不敏感**；
    在這裡再 `.lower()` 一次不會多對，只會讓「送出去的字」與使用者打的不一樣，
    出事時對不起來。
    """
    _seen: list[str] = []

    def _spy(kw):
        _seen.append(kw)
        return []

    for _raw, _want in (("  安聯 ", "安聯"), ("ACdd19", "ACdd19"),
                        ("https://www.moneydj.com/x?a=B",
                         "https://www.moneydj.com/x?a=B")):
        with _fake_l1(_spy):
            search_funds(_raw)
    assert _seen == ["安聯", "ACdd19", "https://www.moneydj.com/x?a=B"], _seen


# ══════════════════════════════════════════════════════════════════
# 2) fail loud —— 三種「不知道」都炸出來，不得收成空清單
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("blank", ["", "   ", "\t\n", None])
def test_a_blank_keyword_raises_instead_of_returning_nothing(blank):
    """空白關鍵字 → `ValueError`。⛔ **不得**回 `[]`。

    「你還沒輸入」與「查不到」是兩個處境、兩個下一步；回同一個值等於
    把前者偽裝成後者，而畫面會照著後者去講一句對他不成立的話（§1）。
    """
    _called: list[str] = []
    with _fake_l1(lambda kw: _called.append(kw) or []):
        with pytest.raises(ValueError):
            search_funds(blank)      # type: ignore[arg-type]
    assert not _called, (
        "空白關鍵字被送去 L1 了 —— 那是一次沒有意義的往返，"
        f"而且會拿回一個會被讀成「查無結果」的空清單：{_called}")


def test_an_exception_from_the_repository_is_not_swallowed():
    """⭐ L1 拋例外 → **原封往上拋**。

    ⛔ 這是本檔最重要的一條。收成 `[]` 的話，「三個來源全掛」在畫面上
       會長得跟「名錄裡真的沒有這檔」一模一樣 —— 而使用者會照著後者去改關鍵字，
       改一百次也一樣。上層（`safe_section`）要拿到真的例外才畫得出紅框 ＋ traceback。
    """
    class _Boom(RuntimeError):
        pass

    def _boom(_kw):
        raise _Boom("哨兵：L1 炸了")

    with _fake_l1(_boom):
        with pytest.raises(_Boom):
            search_funds("哨兵")


@pytest.mark.parametrize("bad", [None, "不是 list", {"a": 1}, 42])
def test_a_contract_break_raises_instead_of_degrading(bad):
    """L1 回的不是 list → `TypeError`。⛔ 不猜、不降級成空清單。"""
    with _fake_l1(lambda _kw: bad):
        with pytest.raises(TypeError):
            search_funds("哨兵")


def test_rows_that_are_not_dicts_are_not_silently_filtered_out():
    """列裡混進非 dict → `TypeError`，⛔ **不得**默默濾掉。

    默默濾掉的話，畫面會少幾張卡而**沒有任何跡象** —— 那比當場炸掉難查得多。
    """
    with _fake_l1(lambda _kw: _rows(1) + ["我不是 dict"]):
        with pytest.raises(TypeError):
            search_funds("哨兵")


# ══════════════════════════════════════════════════════════════════
# 3) 不加快取
# ══════════════════════════════════════════════════════════════════

def test_the_facade_adds_no_cache_of_its_own():
    """同一個關鍵字連呼三次 → L1 真的被打三次。

    ⛔ 在這一層加 TTL ＝ 與 L1 既有的快取疊加，之後沒有人推理得出
       「畫面上這份清單是多久以前的」（`EXCEPTIONS.md §8.2.A.1 EX-UICACHE-1` 升級條件 (3)）。
    ⚠️ **順帶記一筆已知缺口（本組實測，未經第二組驗證）**：L1 的
       `_tdcc_get()` 有 module 層字典擋著，但 **FundClear 備援分支沒有任何快取** ——
       它只在 TDCC 兩個 endpoint 都沒命中時才跑，那條路每次 rerun 都真的送一次 HTTP。
       **本層不補**（補了就違反上面那條），已具名回報總管。
    """
    _n: list[int] = []
    with _fake_l1(lambda _kw: _n.append(1) or []):
        for _ in range(3):
            search_funds("哨兵")
    assert len(_n) == 3, f"L1 只被打了 {len(_n)} 次 —— 這一層長出快取了。"


def test_the_module_declares_no_cache_decorator():
    """靜態面：本檔不得出現任何快取裝飾器（別名寫法也算）。

    ⚠️ **別名不敏感**：`@_st.cache_data` / `@ttl.cache` 都掃得到 ——
    寫死 `@st.` 的字表在本 repo 已經漏抓過一次
    （`EXCEPTIONS.md §8.2.A.1` 驗證段 ① 就地記載）。
    """
    _tree = ast.parse(SRC.read_text(encoding="utf-8"))
    _bad = []
    for _n in ast.walk(_tree):
        if not isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for _d in _n.decorator_list:
            _f = _d.func if isinstance(_d, ast.Call) else _d
            _name = getattr(_f, "attr", None) or getattr(_f, "id", "")
            if "cache" in str(_name).lower():
                _bad.append(f"{_n.name}() 第 {_n.lineno} 行 @{ast.unparse(_d)}")
    assert not _bad, "L2 facade 長出了快取：\n  " + "\n  ".join(_bad)


# ══════════════════════════════════════════════════════════════════
# 4) 空清單的含混被說出來
# ══════════════════════════════════════════════════════════════════

def test_the_ambiguity_of_an_empty_result_is_spelled_out():
    """`EMPTY_MEANS_UNKNOWN` 必須真的講出「兩種都有可能、分不出來」。

    ⛔ L1 的 `tdcc_search_fund` 把所有例外都吞掉（`_tdcc_get` 是
       `except Exception: return []`，FundClear 備援是 `except Exception: pass`），
       所以 `[]` 的意思是含混的。**這一句是呼叫端照抄的那句實話**，
       不是裝飾 —— 它一空掉，UI 就沒有東西可抄，只能自己編一句。
    """
    assert EMPTY_MEANS_UNKNOWN.strip(), "`EMPTY_MEANS_UNKNOWN` 是空的。"
    assert "分不出" in EMPTY_MEANS_UNKNOWN, (
        "那句話沒有講出「本頁分不出是哪一種」—— "
        f"現值：{EMPTY_MEANS_UNKNOWN!r}")
    for _lie in ("查無此基金", "不存在", "沒有這檔"):
        assert _lie not in EMPTY_MEANS_UNKNOWN, (
            f"那句話宣告了「{_lie}」—— 同一個空清單也可能是來源全掛。")
    # 空清單本身仍然是**合法回傳**（不是例外）—— 兩者要分得開
    with _fake_l1(lambda _kw: []):
        assert search_funds("哨兵") == []


def test_the_result_key_names_are_one_source_of_truth():
    """六個鍵名常數與 :data:`RESULT_KEYS` **同一份**，不得各寫各的。

    ⚠️ UI 端一律從這裡 import（`ui/views/page_03_research.py` 的 import 清單）——
    在畫面檔裡抄一份中文字面值就是第二份真相源（§2.1），
    而中文欄名改一個字，畫面會**靜靜地全部變成空欄**。
    """
    assert RESULT_KEYS == (KEY_NAME, KEY_CODE, KEY_AGENT,
                           KEY_NAV, KEY_NAV_DATE, KEY_SOURCE)
    assert len(set(RESULT_KEYS)) == len(RESULT_KEYS), "鍵名有重複。"


# ══════════════════════════════════════════════════════════════════
# 5) 分層
# ══════════════════════════════════════════════════════════════════

def test_the_facade_is_pure_l2():
    """L2 不得 import streamlit / 網路函式庫（`CLAUDE.md §8.2` 硬規則）。

    ⚠️ 全 `services/**` 的 fail-closed 白名單在
    `tests/test_services_purity_contract.py`；本條只是**本檔自己的近身錨點**，
    好處是它紅的時候訊息直接指著這一檔。
    """
    _tree = ast.parse(SRC.read_text(encoding="utf-8"))
    _mods: list[str] = []
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Import):
            _mods += [_a.name for _a in _n.names]
        elif isinstance(_n, ast.ImportFrom) and _n.module:
            _mods.append(_n.module)
    _bad = [_m for _m in _mods
            if _m.split(".")[0] in ("streamlit", "requests", "httpx", "bs4",
                                    "feedparser", "yfinance", "gspread", "ui")]
    assert not _bad, f"L2 facade import 了不該碰的東西：{_bad}"
    assert any(_m.startswith("repositories") for _m in _mods), (
        "facade 沒有 import L1 —— 那它到底把搜尋接到哪裡去了？"
        "（只有反向禁令的話，把整段委派刪掉也會全綠。）")


def test_the_facade_has_no_exception_handler_of_its_own():
    """⛔ 本檔不得有 `try/except`。

    有 `try` 就有機會把「炸了」變成「沒有」，而這一層**分不出**那兩者
    —— 那正是 :func:`test_an_exception_from_the_repository_is_not_swallowed` 在防的。
    """
    _bad = [f"第 {_n.lineno} 行"
            for _n in ast.walk(ast.parse(SRC.read_text(encoding="utf-8")))
            if isinstance(_n, (ast.Try, ast.ExceptHandler))]
    assert not _bad, (
        "L2 facade 自己接了例外：" + "、".join(_bad)
        + "\n例外要一路走到 `safe_section()` 才畫得出帶 traceback 的紅框（§1）。")


def test_the_real_repository_still_exposes_the_function_we_delegate_to():
    """⭐ **正對照**：真的那一支 `tdcc_search_fund` 還在。

    ⚠️ 沒有這一條，上面每一條都是對著**注入的假模組**跑的 ——
    L1 哪天把它改名，本檔會**全綠**，而畫面上搜尋整個壞掉。
    ⚠️ 走 `importorskip`：`repositories.fund` 在載入期需要 `bs4`
    （CI 的 `requirements.txt` 有它；某些精簡環境沒有）。
    **skip 不是通過** —— CI 會真的跑到。
    """
    pytest.importorskip("bs4", reason="repositories.fund 載入期需要 bs4")
    import importlib

    _l1: Any = importlib.import_module("repositories.fund")
    assert callable(getattr(_l1, "tdcc_search_fund", None)), (
        "`repositories.fund.tdcc_search_fund` 不見了（改名了？）—— "
        "`services/fund_search.py` 的 lazy import 會在使用者按下搜尋的那一刻才炸。")
