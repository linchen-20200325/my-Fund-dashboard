"""⑥ `[新] 💊 持倉體檢` —— 客戶 2026-09-08 拍板線框 §2 那一批改動的守衛。

規格出處（**唯一**）
--------------------
`docs/wireframes/draft-four-page-content.html` 的 **§2 · ⑥ 💊 持倉體檢**。
那份檔案是**客戶逐字拍板、已經合併進 repo 的可執行規格**；本檔的字表**只從它讀**，
⛔ **不在這裡手抄一份** —— 手抄的字表會跟著被測檔一起改、於是一起綠，
那正是本 repo 反覆記載的「守衛跟著被測物改，紅燈就消失了」。

本檔守什麼（六族）
------------------
============================ ==============================================
族                            守的東西
============================ ==============================================
**線框逐字**                   六個字串真的來自線框，**而且真的出現在畫面上**
**空狀態**                     沒有持倉時**不畫**那個沒有東西可以篩的表單
**點名 ＋ 下一步**              每一檔被點名的問題後面都要有一句可以走的下一步，
                              而且那條路**今天真的走得到**
**畫面用語**                   「已送客戶確認」「Jaccard」這類**我們的進度／內部術語**
                              不准出現在畫面上（裁決 4）
**白話解釋**                   三句白話**從共用 SSOT 讀**，而且只解釋表上真的有的欄位
**fail-closed**               判準探針壞掉時，每一檔要落進「判不出來」，
                              ⛔ 不是落進「沒有查出問題」
============================ ==============================================

⛔ **本檔看不到什麼（照實寫，⛔ 不要讀成「守死了」）**
----------------------------------------------------
1. **`_wf_line_runs()` 擋得住「剪在一行中間」，擋不住「剪在行界上」。**
   ⑥ 的線框裡**只有一個**多行值（逐檔表底下那句「五桶評等」說明，佔兩行），
   所以只有它有這個縫 —— 砍掉第二行之後，剩下的正好就是第一行那一整行。
   **本組實測過這個縫真的存在**（見 :func:`_wf_line_runs` 的長註）。
   ⇒ **那一個縫由另一條獨立的守衛補**：
   `tests/test_wf02_health_skeleton.py::
   test_the_table_never_shows_a_bucket_grade_because_there_is_no_such_thing`
   要求**兩半都在**（「還沒定案」＋「不拿別的評等填進來充數」）。
   ⚠️ **不要把這一句讀成「所以沒事」** —— 它是「這個縫由那一條補」，
   不是「這一條擋得住」。**兩條都在的時候才是補起來的。**
2. **本檔不驗線框自己有沒有被改。** 改線框是一次看得見的 diff，立場與 ⑦ 相同。
3. **三張卡的卡片本文沒有行錨點。** 線框把三張卡畫成並排的 ASCII 方框，
   **同一行裡有三張卡的片段**，`_squash` 之後就接在一起了 ——
   ⇒ 卡片本文只能做**子字串**比對（會漏掉截斷）。
   **本檔因此不對卡片本文宣稱「逐字」**；卡片那一族守的是**它有沒有點名**
   （:func:`test_the_eating_card_names_the_funds_it_counted`），那是截斷偽造不了的。
4. **「⑥ 的線框只要求這六個字串逐字」本檔不宣稱** —— 那取決於有沒有漏看。

⚠️ **本檔的斷言絕大多數是執行期的**（要 streamlit ＋ 假 `st` 錄一輪）。
撰寫當下本機沒有 `pandas` / `numpy`，所以三條與影子基金重疊有關的既有測試
在本機是紅的（**base 上就是紅的**，不是本批造成的）；**全套的真憑據以 CI 為準。**
"""
from __future__ import annotations

import ast
import copy
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from test_wf02_health_conclusion import (  # noqa: E402
    BLIND, FOUR_WAY, LAG, _conclusion_slice)
from test_wf02_health_skeleton import _fund, _render, _text  # noqa: E402

from ui.helpers.render_state import NOT_READY_MARK  # noqa: E402
from ui.helpers.story_nav import where_to_find  # noqa: E402
from ui.views import page_02_health as _p02  # noqa: E402
from ui.views.page_02_health import (  # noqa: E402
    BUCKET_GRADE_CAPTION,
    CLEAR_NOTE,
    CONCLUSION_HEADING,
    EVIDENCE_HEADING,
    GROUP_HEADLINES,
    HEALTH_TABLE_COLUMNS,
    METRIC_PLAIN_LANGUAGE_KEYS,
    _eating_labels,
    _eating_note,
    _fund_findings,
    _metric_plain_language,
    _shadow_pair_note,
    _uniq_by_code,
)

#: **每一檔的配息都真的蓋得住**（覆蓋 ≥ 1.0）且**都判得動**的持股。
#: ⚠️ 專門給「配息蓋得住、也沒有落後同類。」那一句用 —— 那句話**只在這種情況下為真**。
_ALL_COVERED = [
    _fund("HC1", div=3.0, ret=9.0),   # gap = −6 → healthy
    _fund("HC2", div=2.0, ret=8.0),   # gap = −6 → healthy
]
for _f in _ALL_COVERED:
    _f["moneydj_raw"]["risk_metrics"] = {"peer_compare": {"同類型平均": {"1Y": 1.0}}}
    _f["invest_twd"] = 500_000.0

#: **接近警戒**（黃燈）的那一檔：覆蓋 **低於 1.0**，但缺口還在門檻內 ⇒ **不算吃本金**。
#: ⚠️ 數字是照 `services/health/dividend.py` 的判定式挑的，**不是隨手填的**：
#:    `ret=6.5, div=8.0` → `coverage = 0.81`（**< 1.0**）、`gap = 1.5pp`（**≤ 2.0**）→ yellow。
_NEAR_FUND = _fund("NEAR", div=8.0, ret=6.5)
_NEAR_FUND["moneydj_raw"]["risk_metrics"] = {"peer_compare": {"同類型平均": {"1Y": 1.0}}}
_NEAR_FUND["invest_twd"] = 500_000.0

#: 一群「都判得動、都沒有落後同類」，**但其中一檔接近警戒**。
_CLEAR_WITH_NEAR = [_ALL_COVERED[0], _NEAR_FUND]

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "ui" / "views" / "page_02_health.py"
WIREFRAME = ROOT / "docs" / "wireframes" / "draft-four-page-content.html"

#: ⑥ 那一節的邊界。**兩個錨點都取自線框自己的 `<h2>`。**
_WF_P6_START = "<h2>2 · ⑥ 💊 持倉體檢</h2>"
_WF_P6_END = "<h2>3 · ⑦ ⚙️ 設定與診斷</h2>"

#: ⑥ 那一節裡的 **ASCII 線框圖**（狀態 (1) 與狀態 (2) 兩張）。
_WF_PRE = re.compile(r'<pre class="wf">(.*?)</pre>', re.S)

#: 線框自己畫的**行首記號**，不是文案的一部分。
#: 畫面上那些記號由 `render_state` / 本頁的 emoji 補，**值本身不含它們**。
#: ⛔ **不要往這裡加東西來讓某個字串通過** —— 每多一個，「整行」的邊界就往右鬆一格。
_WF_LINE_MARKERS: tuple[str, ...] = ("☐", NOT_READY_MARK, "🫐", "🟢", "💰", "·", "→", "▸")


def _squash(text: str) -> str:
    """去掉標記、空白與 ASCII-art 框線，只留「字」。

    ⚠️ **非做不可**：線框的 `<pre class="wf">` 把一句話**折成兩行**、
    每行前後包 `│` 與一堆對齊用的空白。直接 `in` 比對**一定 miss**，
    而 miss 會被讀成「這句話不是線框寫的」——那是一個假的紅燈。
    """
    _t = re.sub(r"<[^>]+>", "", text)
    _t = (_t.replace("&lt;", "<").replace("&gt;", ">")
            .replace("&amp;", "&").replace("&quot;", '"'))
    return "".join(_c for _c in _t
                   if not _c.isspace() and _c not in "│┌┐└┘├┤─")


def _wf_pres() -> list[str]:
    """⑥ 那一節的兩張 ASCII 線框圖（原始 HTML 片段）。**fail-closed。**"""
    _raw = WIREFRAME.read_text(encoding="utf-8")
    assert _WF_P6_START in _raw and _WF_P6_END in _raw, (
        f"線框 {WIREFRAME.name} 裡找不到 ⑥ 那一節的錨點 —— "
        "本檔全部的字表比對都會失去對象（fail-closed）。\n"
        f"錨點：{_WF_P6_START!r} / {_WF_P6_END!r}")
    _sec = _raw[_raw.index(_WF_P6_START):_raw.index(_WF_P6_END)]
    _pres = _WF_PRE.findall(_sec)
    assert len(_pres) == 2, (
        f"⑥ 那一節的 ASCII 線框圖有 {len(_pres)} 張，應為 2 張"
        "（狀態 (1) 完全沒資料 ／ 狀態 (2) 有資料）——"
        "數量對不上代表錨點或線框結構變了，本檔的字表比對會失去對象（fail-closed）。")
    return _pres


def _wf_line_runs() -> frozenset[str]:
    """⑥ 兩張線框圖裡「**一整行、或連續數整行的接合**」的所有可能（squash 後）。

    ⭐ **它解的問題**：`_squash(值) in _squash(整節)` 是**子字串**比對，
    **任何截斷仍然是子字串**。也就是「把客戶拍板的文案剪短」照樣通過，
    而剪短同樣是在單方面改客戶的畫面。
    **改成「必須等於一整行、或連續數整行」之後，剪在行中間就不再是任何一種組合。**

    ⛔⛔ **它擋不到什麼 —— 本組實測過，不要照抄 ⑦ 的說法**
    -----------------------------------------------------
    ⑦ 那一版（`tests/test_wf05_settings_skeleton.py`）多做了一步「只收**極大** run」，
    判準是「下一行的第一個字元是不是文字」。**那個判準在 ⑥ 不成立** ——
    ⑥ 的線框裡**新元素也常常以中文開頭**（逐檔表底下那三句白話就是三個獨立元素，
    每一句都以中文起頭）。照抄它會把三句白話併成一個 run，
    於是**每一句單獨拿去比對都會 miss** ⇒ 一堆假紅燈。
    **本組實測後刻意不照抄。**

    ⇒ 現行版本收「從第 i 行起的每一種長度」，代價是：
    **對線框上被折成多行的值，在行界剪一刀得到的仍然是一個合法 run。**
    ⑥ 的線框裡**只有一個**多行值（逐檔表底下「五桶評等」那句，佔第 47/48 行），
    本組實測那個縫**真的存在**（砍掉第二行 → 仍然通過）。
    **那個縫由另一條獨立守衛補**，見本檔模組 docstring 第 1 點。

    ⚠️ **另一件擋不到的**：**重組** —— 把兩段不相鄰的整行接起來，
    仍然可能湊出一個合法 run。本函式只保證「是整行」，不保證「是同一段話」。
    """
    _runs: set[str] = set()
    for _pre in _wf_pres():
        _lines = [_l for _l in (_squash(_ln) for _ln in _pre.splitlines()) if _l]
        for _i in range(len(_lines)):
            # ⚠️ **記號只在起頭那一行剝**：`⬜ 尚未設定持倉` 的 `⬜` 是線框畫的，
            #    畫面上那個記號由 `render_state` 補，值本身不含它。
            _heads = {_lines[_i]}
            for _mk in _WF_LINE_MARKERS:
                if _lines[_i].startswith(_mk):
                    _heads.add(_lines[_i][len(_mk):])
            for _head in _heads:
                _acc = _head
                _runs.add(_acc)
                for _j in range(_i + 1, len(_lines)):
                    _acc += _lines[_j]
                    _runs.add(_acc)
    return frozenset(_runs)


#: 本批**逐字**照抄線框的六個字串。**值一律 import 自被測檔，不在這裡抄第二份。**
#:
#: ⚠️ 逐檔表底下那三句白話**只有前兩句**在這裡 —— 第三句（配息覆蓋）是
#: **刻意偏離線框**的，理由與守衛見
#: :func:`test_the_deliberate_deviation_from_the_wireframe_is_still_deliberate`。
def _verbatim_pairs() -> list[tuple[str, str]]:
    _plain = _metric_plain_language()
    return [
        ("結論層標題", CONCLUSION_HEADING),
        ("依據層標題", EVIDENCE_HEADING),
        # ⚠️ **2026-09-09：這兩句改成 import，不再在這裡抄第二份**
        #    （**有意識的更正，不是漏刪**；依 2026-09-09 獨立稽核必修 D）。
        #    本清單上方那句「**值一律 import 自被測檔，不在這裡抄第二份**」
        #    **本來就寫在那裡，而這兩句違反了它** —— 抄一份到測試裡，
        #    被測檔與測試一起改就一起綠，那正是這一族守衛存在的理由。
        ("「沒有查出問題」那一群的說明", CLEAR_NOTE),
        ("逐檔表底下的「五桶評等」說明", BUCKET_GRADE_CAPTION),
        ("白話解釋：Sharpe", _plain[0]),
        ("白話解釋：最大回撤", _plain[1]),
    ]


@pytest.mark.parametrize("what,value", _verbatim_pairs(),
                         ids=[_w for _w, _ in _verbatim_pairs()])
def test_the_wireframe_verbatim_strings_really_come_from_the_wireframe(
        what: str, value: str):
    """⭐ 被測檔宣稱「線框逐字」的六個字串，**必須真的在客戶簽核的線框裡**，
    而且**必須是一整行（或連續數整行）**，不是「出現過」。

    ⛔ **改這幾句話的正解是先改線框、拿去給客戶看** —— 它們是客戶親自拍板的畫面文案，
    不是實作細節。**在 `.py` 裡單方面剪短或換句話說，這一條會紅。**
    """
    assert _squash(value) in _wf_line_runs(), (
        f"「{what}」這一句不是線框 §2 裡的一整行（或連續數整行）：\n"
        f"  被測檔：{value!r}\n"
        "  ⇒ 要嘛它被改過了，要嘛它被剪短了。**兩種都是單方面動客戶拍板的文案。**\n"
        f"  線框：{WIREFRAME}")


def test_those_strings_are_really_on_the_screen_not_just_in_a_constant():
    """⭐⭐ **上一條驗的是常數，這一條驗的是畫面 —— 兩條缺一不可。**

    ⑦ 那一批（PR #835）第四輪的獨立稽核記下的正是這個形狀：
    **「守衛守的是替身」** —— 底本（常數）釘死了，
    而**謊話住在「常數」與「渲染輸出」之間那道縫裡**：
    常數沒動、渲染時在後面接一段字，兩層都過。

    ⇒ 本條直接看**錄下來的畫面**：那幾句話必須真的被畫出來。
    ⚠️ **本條刻意不驗「有沒有多接一段字」**（那是另一個問題，
    由結論層的筆數上限與內部語言掃描各守一半）——
    本條只釘「**畫面上真的有這幾句**」。⛔ 不要把它讀成「畫面已封閉」。
    """
    # ⚠️ **「沒有查出問題」那一句要用「這一群裡每一檔的配息都真的蓋得住」的持股**
    #    —— `FOUR_WAY` 裡的 `MID` 是**接近警戒**，那一群的說明句依 ⛔2 的修正
    #    會換成另一句（見 :func:`test_the_clear_group_never_tells_a_near_fund_it_is_covered`）。
    _by_fixture = {"配息蓋得住": _ALL_COVERED}
    for _what, _value in _verbatim_pairs():
        _pf = next((_v for _k, _v in _by_fixture.items() if _k in _value), FOUR_WAY)
        _parts = _render(portfolio=_pf)
        # ⭐⭐ **2026-09-09：判準由「整頁 join 之後的子字串」改成「某一筆渲染紀錄的
        #    全部或結尾」**（**收緊，不是放寬**；依 2026-09-09 獨立稽核必修 D）。
        #    **舊判準擋不住「在後面接一段字」** —— 稽核實測：在五桶評等那句 caption
        #    後面接「這一欄不重要，可以忽略。」→ **106 passed、突變存活**，
        #    而那句話正好否定了那一段的 §1 用意（誠實說明為什麼整欄留白）。
        #    ⛔ 用 `endswith` 而不是全部 `==`：三群那一句是**接在群組抬頭後面**的，
        #    本來就不是整筆；`endswith` 一樣擋得住「接一段字」。
        _payloads = [_p.split("] ", 1)[1] if "] " in _p else _p for _p in _parts]
        _hit = [_x for _x in _payloads if _x == _value or _x.endswith(_value)]
        assert _hit, (
            f"線框逐字的句子「{_what}」**沒有以整筆（或整筆結尾）出現在畫面上**。\n"
            "  ⚠️ 常數在、畫面沒有 ＝ 守衛守到替身；\n"
            "  ⚠️ 或者它**後面被接了一段字** —— 那同樣是單方面改客戶拍板的文案。\n"
            f"  期望：{_value!r}\n" + _text(_parts))


def test_the_deliberate_deviation_from_the_wireframe_is_still_deliberate():
    """⛔ 三句白話裡的**第三句刻意不照線框**，這一條擋的是「有人把它改回去」。

    **線框那一句是**：「配息覆蓋：配出來的錢有多少是真的賺到的，**<1.0 就是在吃本金**。」
    **本頁不照抄，理由是它會與同一頁的警示卡打架**：
    ⑥ 的「吃本金警示」判的是 `alert_level == "red"` ——
    **近一年含息報酬低於年化配息率超過 N 個百分點**
    （N 走 `shared/signal_thresholds.NEAR_DIVIDEND_WARNING_PCT`），
    **不是**「覆蓋 < 1.0」。覆蓋 0.95 的那一檔在卡片上是「**接近警戒**」，
    照線框那句話卻會被讀成「**已經在吃本金**」。
    **同一個組合、同一頁、兩個結論** —— `CLAUDE.md §2.1` 要擋的正是這個。

    ⚠️ **這是本批唯一一處刻意偏離客戶拍板文案的地方，據實登記、不藏在 PR 描述裡。**
    ⛔ 若客戶認為就要照線框那句話寫，那要改的是**判定**（把卡片改成用覆蓋 1.0 判），
    **不是**把這句話改回去而讓畫面自相矛盾。
    """
    _cov = _metric_plain_language()[2]
    assert _cov.startswith("配息覆蓋："), f"第三句不是配息覆蓋那一句了：{_cov!r}"
    assert "就是在吃本金" not in _cov, (
        "配息覆蓋那句白話被改回線框的寫法了（「<1.0 就是在吃本金」）——\n"
        "⛔ 那句話與同一頁「吃本金警示」卡的判準**不一致**（卡片判的是缺口超過 N 個百分點，\n"
        "   不是覆蓋 < 1.0），覆蓋 0.95 的那一檔會同時被說成「接近警戒」與「已經在吃本金」。\n"
        f"  現行：{_cov!r}")
    assert "低於 1.0" in _cov, (
        "配息覆蓋那句白話沒有講出「低於 1.0 代表什麼」——\n"
        "偏離線框是為了**更準**，不是為了**少講**。\n" + repr(_cov))


# ══════════════════════════════════════════════════════════════════
# ② 空狀態：一個沒有東西可以篩的篩選器不要畫
# ══════════════════════════════════════════════════════════════════
#: `_Rec` 會錄成一筆的 widget 前綴 —— 也就是「使用者看得到、按得到的東西」。
_WIDGET_PREFIXES = ("[slider]", "[number_input]", "[checkbox]",
                    "[form_submit_button]")


def test_the_empty_state_draws_no_filter_form():
    """⛔ 沒有持倉時，**整個「診斷條件」表單不畫**（客戶 2026-09-08 拍板線框 §2 狀態 (1)）。

    **線框逐字**：「現況是**先**畫『診斷條件（…）』，**再**畫空狀態。
    **一個沒有東西可以篩的篩選器**，正是鐵則 04「首屏無冗餘占位」要擋的。
    **推薦：沒有持倉時整個表單不畫。**」
    而狀態 (1) 那張線框圖裡，從標題到空狀態之間**一個 widget 都沒有**。

    ⚠️ **不是把它藏起來**：那四個條件在沒有持倉時**一個都沒有東西可以套用** ——
    畫一個按了不會有事發生的按鈕，比不畫更難懂。
    """
    _parts = _render(portfolio=[])
    _widgets = [_p for _p in _parts if _p.startswith(_WIDGET_PREFIXES)]
    assert not _widgets, (
        "沒有持倉時畫面上還是出現了篩選條件的 widget：\n  " + "\n  ".join(_widgets)
        + "\n⛔ 客戶 2026-09-08 拍板：沒有持倉時整個表單不畫。")
    # 空狀態本身要在（否則「什麼都不畫」也會通過這一條）。
    assert "尚未設定持倉" in _text(_parts), (
        "沒有持倉時連空狀態都沒畫 —— 那不是「不畫表單」，那是整頁消失。\n"
        + _text(_parts))


def test_the_form_is_still_there_when_there_are_holdings():
    """⭐ **上一條的正對照 —— 沒有它，「把表單整個刪掉」也會全綠。**

    有持倉時那四個條件**一個都不准少**，而且它們仍然排在結論層**前面**
    （條件 → 結論 → 依據，四層閱讀順序未變）。
    """
    _parts = _render(portfolio=FOUR_WAY)
    _widgets = [_p for _p in _parts if _p.startswith(_WIDGET_PREFIXES)]
    assert len(_widgets) >= 4, (
        "有持倉時「診斷條件」表單少了 widget（應有 σ／回看窗／只看衛星／本金／套用）：\n  "
        + "\n  ".join(_widgets))
    _submit = next(_i for _i, _p in enumerate(_parts)
                   if _p.startswith("[form_submit_button]"))
    _head = _parts.index(f"[markdown] {CONCLUSION_HEADING}")
    assert _submit < _head, (
        "表單跑到結論層後面去了 —— 閱讀順序是「條件 → 結論 → 依據」。\n"
        + _text(_parts))


# ══════════════════════════════════════════════════════════════════
# ③ 點名 ＋ 下一步（線框 §2「這一頁改了什麼」第 1、2 條）
# ══════════════════════════════════════════════════════════════════
def test_every_named_problem_carries_a_next_step():
    """⛔ 每一檔被點名的問題**後面都要有一句可以走的下一步**（線框裁決 5）。

    **線框逐字**：「**每條結論都帶一個「做法」。** 現況只有判定沒有下一步。」
    線框圖裡每一條問題的下一行都是「→ 到 ④ 📊 資產配置 › 🎯 換股顧問 看要換成什麼」。

    ⚠️ **判準是「問題有幾條、下一步有幾條」，不是「有沒有出現過那句話」** ——
    只印一次的話，第二檔以後的使用者看到的就是「有問題、然後呢？」。
    """
    _slice = _conclusion_slice(_render(portfolio=FOUR_WAY))
    _problem = [_p for _p in _slice
                if f"檔{GROUP_HEADLINES['problem']}" in _p]
    assert _problem, (
        "畫面上沒有「要處理」那一群 —— 這組 fixture 裡 LAG 應該被判成要處理。\n"
        + "\n".join(_slice))
    _block = _problem[0]
    # 被點名的檔數 ＝ 那一段裡以 `- **` 起頭的行數
    _named = [_ln for _ln in _block.splitlines() if _ln.startswith("- **")]
    _steps = [_ln for _ln in _block.splitlines() if where_to_find("switch") in _ln]
    assert _named, ("「要處理」那一群沒有點名任何一檔 —— 只給總數就是這一批要修掉的畫面。\n"
                    + _block)
    assert len(_steps) == len(_named), (
        f"點名了 {len(_named)} 檔，但只有 {len(_steps)} 條下一步 —— "
        "有問題卻沒有下一步的那幾檔，使用者只會問「然後呢」。\n" + _block)


def test_the_next_step_points_at_a_block_that_is_really_rendered_today():
    """⭐⭐ **這一條擋的是本 session 貫穿九輪的那個缺陷類別：指路指到一個做不到的地方。**

    ⑥ 的下一步指向 `where_to_find("switch")`（＝「④ 📊 資產配置 → 🎯 換股顧問」）。
    **那一塊今天住在舊 ④** `ui/tab3_portfolio.py`，而本條用 AST 釘住兩件事：

      (a) `app.py` 真的把舊 ④ 掛在分頁上；
      (b) 舊 ④ 裡那一塊的渲染呼叫**不在任何 `if` 底下** —— 也就是使用者點過去
          真的看得到它，不是「某個條件成立時才畫」。

    ⛔ **舊 ④ 下架那一批，本條會轉紅 —— 那是它的用途，不是它壞了。**
    屆時 🎯 換股顧問的落點會變成新 ⑨，而它在新 ⑨ **目前是一張灰卡**
    （`ui/views/page_04_portfolio.py::REASON_SWITCH`）。
    **指到一塊做不了事的東西，比指到舊分頁更糟** —— 所以那一批必須同時改這條指路。

    ⚠️ **本條看不到什麼**：它不驗那一塊**畫出來之後有沒有內容**
    （沒有持倉時它會走自己的空狀態）。它驗的是「**那條路存在而且沒有被開關擋住**」。
    """
    _sym = "render_switch_advisor_section"

    # (a) app.py 掛了舊 ④
    _app = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    _calls = {getattr(_n.func, "id", None) or getattr(_n.func, "attr", None)
              for _n in ast.walk(_app) if isinstance(_n, ast.Call)}
    assert "render_portfolio_tab" in _calls, (
        "`app.py` 已經不再呼叫舊 ④ 了 —— ⑥ 結論層那條「到 🎯 換股顧問」的指路"
        "當場變成死路。**要改的是那條指路，不是這條守衛。**")

    # (b) 舊 ④ 裡那一塊的渲染呼叫不在任何 `if` 底下
    _t4 = ast.parse((ROOT / "ui" / "tab3_portfolio.py").read_text(encoding="utf-8"))
    _parents: dict[int, ast.AST] = {}
    for _n in ast.walk(_t4):
        for _c in ast.iter_child_nodes(_n):
            _parents[id(_c)] = _n
    _sites = [_n for _n in ast.walk(_t4)
              if isinstance(_n, ast.Call)
              and (getattr(_n.func, "id", None) == _sym
                   or getattr(_n.func, "attr", None) == _sym)]
    assert _sites, (
        f"舊 ④ 裡找不到 `{_sym}(...)` 的呼叫點 —— "
        "🎯 換股顧問那一塊不知道搬去哪了，⑥ 的指路失去對象（fail-closed）。")
    _gated = []
    for _site in _sites:
        _cur: ast.AST | None = _site
        while _cur is not None:
            _cur = _parents.get(id(_cur))
            if isinstance(_cur, (ast.If, ast.While, ast.IfExp)):
                _gated.append(getattr(_site, "lineno", -1))
                break
    assert len(_gated) < len(_sites), (
        "舊 ④ 裡 🎯 換股顧問的**每一個**渲染呼叫都被 `if` 擋住了 —— "
        "⑥ 把使用者指過去，他可能什麼都看不到。\n"
        f"  被擋住的呼叫在第 {_gated} 行。\n"
        "⛔ 正解是改 ⑥ 那條指路（或替它加一句「要先做什麼」），不是放寬本條。")


def test_the_conclusion_names_every_fund_exactly_once():
    """⛔ 每一檔**恰好**出現在三群裡的一群 —— 不准漏、不准同時出現在兩群。

    ⚠️ 這條與 `test_every_fund_is_accounted_for_in_both_conclusions` **不重複**：
    那一條驗的是**數字**加得回總數，本條驗的是**名字**。
    數字對、名字漏印，使用者一樣不知道要動哪一檔。
    """
    _recs = _fund_findings(FOUR_WAY)
    assert len(_recs) == len(FOUR_WAY), f"逐檔紀錄少了幾檔：{len(_recs)}"
    _groups = {_r["code"]: _r["group"] for _r in _recs}
    assert len(_groups) == len(FOUR_WAY), "同一檔出現了兩次。"

    _body = "\n".join(_conclusion_slice(_render(portfolio=FOUR_WAY)))
    for _f in FOUR_WAY:
        assert _body.count(_f["code"]) >= 1, (
            f"{_f['code']} 沒有出現在結論層裡。\n{_body}")


def test_a_fund_with_a_problem_is_never_called_clear():
    """⛔⛔ **「有一項查不動」不得被說成「沒有查出問題」**（§1，也是線框那句
    「**判不出來不等於沒問題**」的機器版）。

    ⚠️ **本條用的是「一項乾淨、一項查不動」的那一檔** —— 那正是最容易被
    「簡化」成綠燈的形狀：`BLIND` 的吃本金判得動（黃燈、不算吃本金），
    但同類平均查不到 ⇒ **必須落進「判不出來」**，⛔ 不是「沒有查出問題」。
    """
    _rec = next(_r for _r in _fund_findings([BLIND]) if _r["code"] == "BLIND")
    assert _rec["group"] == "unknown", (
        "一項查不動的那一檔被歸進了別群 —— "
        f"「一半查過了」不是「沒事」。實際：{_rec}")
    assert _rec["blind"], "落進「判不出來」卻沒有講出是哪一項查不動。"


def test_a_broken_grade_probe_makes_funds_undecided_not_fine(monkeypatch):
    """⭐⭐ **fail-closed：判準探針壞掉時，要落進「判不出來」，⛔ 不是「沒有查出問題」。**

    `_lag_verdict_text()` 用探針去問 SSOT「落後那一桶叫什麼」。
    **如果哪天它問不出來**（SSOT 改了回傳形狀、拋例外、兩端回同一句話），
    本頁**必須說「不知道」**，⛔ 不得因為「沒有比對到落後那一桶」就宣布沒事 ——
    那是**沉默地把每一檔都漂白**，而畫面上完全看不出來（`CLAUDE.md §1`）。

    ⚠️ **這一條是先假設守衛在說謊、再照它自己寫的判準構造反例做出來的**：
    把探針打壞，看畫面會不會說謊。**不是掃描找到的。**
    """
    _lag = LAG  # 這一檔在正常情況下**確實**落後同類（fixture 前提）
    assert any(_r["group"] == "problem" for _r in _fund_findings([_lag])), (
        "前提不成立：LAG 在正常情況下應該被判成要處理。")

    monkeypatch.setattr(_p02, "_lag_verdict_text", lambda: None)
    _recs = _fund_findings([_lag])
    assert _recs[0]["group"] != "clear", (
        "判準探針壞掉時，這一檔被說成「沒有查出問題」——\n"
        "⛔ 那是把「不知道」漂白成「沒事」，正是本頁 `_eating_tally` 早就寫死要防的那件事。\n"
        f"  實際：{_recs[0]}")


# ══════════════════════════════════════════════════════════════════
# ④ 畫面用語：我們的進度／內部術語不准上畫面（裁決 4）
# ══════════════════════════════════════════════════════════════════
import test_wf02_health_skeleton as _sk  # noqa: E402


def _render_gated(portfolio: list, *, gate_on: bool) -> list[str]:
    """跑一次整頁，**可以指定委派區那顆 Checkbox Gate 有沒有被勾**。

    ⭐⭐ **這一支存在的理由，是 ⑦ 那一批（PR #835）第五輪稽核擋下的那一項**：
    「**封閉集合只跑了一個世界**」—— 一整族斷言只在 `gate=OFF` 跑過，
    於是**勾下去之後才出現的那些字，從來沒有被任何一條守衛看過**。
    ⑥ 的委派區同樣藏著一整批只有勾了才會出現的文案，**兩個世界都要掃**。

    ⚠️ **`gate=ON` 時委派進來的舊模組會真的執行** —— 本機沒有 `pandas` / `numpy`，
    它們會拋例外並被 `safe_section()` 畫成紅框（錄成 `[Error] …`）。
    **那不影響本族斷言**：本族掃的是「畫面上有沒有出現那些字」，
    而紅框本身也是畫面的一部分。⛔ **不要因此把 `gate=ON` 那一半拿掉。**
    """
    if not gate_on:
        return _sk._render(portfolio=portfolio)

    _orig = _sk._Rec

    class _Gated(_orig):  # type: ignore[misc, valid-type]
        def __getattr__(self, name):
            _fn = _orig.__getattr__(self, name)
            if name != "checkbox":
                return _fn

            def _cb(*a, **k):
                _fn(*a, **k)   # 照樣錄一筆，紀錄與 gate=OFF 對得起來
                return True
            return _cb

    _sk._Rec = _Gated
    try:
        return _sk._render(portfolio=portfolio)
    finally:
        _sk._Rec = _orig


#: ⛔ **今天畫面上一個都沒有的內部語言 —— 出現任何一個就是紅燈。**
#:
#: 客戶 2026-09-08 拍板線框 §2「這一頁改了什麼」第 4、5 條點名了其中兩個
#: （**已送客戶確認**、**Jaccard**）；其餘是同一族的字，**一起收進來是放大射程**，
#: 不是替客戶加規矩 —— 它們今天本來就是 0，收進來只會**多**紅、不會少紅。
_BANNED_ON_SCREEN: tuple[str, ...] = (
    "已送客戶確認", "尚未答覆", "待客戶", "客戶 gate",
    "Jaccard", "cosine",
    "分批上線", "獨立批次", "下一個批次", "本批",
    "上游", "服務層", "委派", "模組", "接線",
    "session_state", "portfolio_funds", "policy_tier",
    "caller", "docstring", "AST", "SSOT", "commit", "4D",
)

#: 委派區那一塊的標題 —— **本族掃描的下界**。
#:
#: ⛔⛔ **為什麼要有下界，這一段請讀完再改**
#: 那個標題以下是**原封委派進來的舊模組**（`render_fund_checkup` 等），
#: 客戶紅線是「**絕對禁止修改現有線上正常運作的舊版 Tab 代碼**」——
#: 也就是**本批對那些字一個位元組都動不了**。
#: 把它們收進射程，等於讓本條守衛**被本批管不到的東西決定紅綠**：
#: 它今天綠、明天別人改了舊模組就紅，而紅的時候**沒有人有權修**。
#: ⚠️ **而且本機量到的數字對那一塊是假的**：本機沒有 `pandas`／`numpy`／`plotly`，
#: 那些委派進來的區塊在本機**全部拋例外**、只印一行紅框；
#: **CI 上它們會真的畫出東西**，字數與用詞完全不同。
#: **拿一個本機量得到、CI 量不到的數字當棘輪的起點，就是本 repo 記載過的那種假守衛。**
#:
#: ⛔ **這不是說那一塊沒問題** —— 本批實測，`gate=ON` 之後那一塊會印出
#: 「本區直接沿用既有的健診**模組**…」以及一句**指向本頁不存在的欄位**的灰態
#: （「請先到：本頁的「基金代號」欄位」，而 ⑥ 依客戶 2026-09-05 裁決**沒有**那個欄位）。
#: **兩筆都已登記為 §8.3.P 的 `P-P02DELEGJARGON-1`，本批不動工。**
_DELEGATED_HEADING = "[markdown] #### 🔬 逐檔健診與互斥分析"


def _own_screen(parts: list[str]) -> str:
    """本頁**自己畫的**那一段（委派區以上）。**fail-closed。**"""
    assert _DELEGATED_HEADING in parts, (
        f"畫面上找不到委派區的標題 {_DELEGATED_HEADING!r} —— "
        "本族掃描就沒有下界了，會連舊模組的輸出一起掃（fail-closed）。\n"
        + "\n".join(parts))
    return "\n".join(parts[:parts.index(_DELEGATED_HEADING)])


#: ⚠️ **既有債：今天畫面上真的有，而且不在本批的改動範圍內。**
#:
#: **本批刻意不修它們**（`CLAUDE.md §8.4` 步驟 4：範圍要擴大是客戶的決定，
#: 不是實作組順手做的事），但**也不放它們過去** —— 記下今天的**次數**，
#: **只准變少、不准變多**。新的一句話裡出現同一個字 ⇒ 次數上升 ⇒ 紅。
#:
#: ⛔ **這不是豁免清單，是棘輪。** 想加一項進來，要嘛它今天真的是 0
#: （那就進上面那張表），要嘛你正在**新增**一句內部語言 —— 後者一律不准。
#:
#: 出處（本組實測，不是推論）：
#:   `取數` ×1 —— 「診斷條件」表單上方那句「拖滑桿的當下不會觸發任何取數」
#: 已登記為 §8.3.P 的 **`P-P02JARGON-1`**。
#:
#: ⚠️ **`程式碼`／`模組` 不在這裡，因為它們住在委派區以下**（見 :data:`_DELEGATED_HEADING`），
#: 本族掃不到它們 —— **這是刻意的射程外，不是漏掉**，另案登記。
_SCREEN_JARGON_DEBT: dict[str, int] = {"取數": 1}


@pytest.mark.parametrize("gate_on", [False, True], ids=["gate=OFF", "gate=ON"])
@pytest.mark.parametrize(
    "state", ["empty", "rich", "four", "fake"])
def test_no_internal_progress_language_reaches_the_screen(state: str, gate_on: bool):
    """⛔⛔ **畫面上只准有「使用者的處境」，不准有「我們的進度」**（裁決 4）。

    **線框 §2 逐字**：「**「已送客戶確認」四個字從畫面上拿掉**（裁決 4）。現況**兩處**都在
    畫面上：組合健康總分的灰態、以及逐檔表底下那句 caption。……
    **使用者需要知道的是「這個數字為什麼是空的」，不是「我們送到哪裡了」。**
    **理由搬回程式碼註解，一個字都不刪。**」

    ⭐ **本條掃的是「渲染出來的字」，不是原始碼的 AST。** 這是刻意的，
    也是它比 ⑨ 那條同族守衛（`tests/test_wf04_add_holdings.py::
    test_the_new_wording_carries_no_internal_progress_language`）**射程更大**的地方：
    ⑨ 那一條就地登記了自己的缺口 —— 「`label` 走的是**模組層常數**，
    **那些常數的定義處不在本清單裡**，也就是把違禁詞寫進那幾個常數，本條照樣抓不到」。
    ⑥ 這兩個違禁詞**正好就住在模組層常數裡**（`_SCORE_PENDING_NOTE`），
    **照 AST 白名單那個寫法會完全看不到它們。**

    ⚠️ **四個狀態 × 兩個世界都要掃**：文案會因為有沒有持倉、資料齊不齊、
    閘門有沒有勾而換一批 —— 只掃一種，就等於只看了畫面的四分之一。
    """
    _pf = {"empty": [], "rich": _sk.RICH_HOLDINGS,
           "four": FOUR_WAY, "fake": _sk.FAKE_HOLDINGS}[state]
    _body = _own_screen(_render_gated(_pf, gate_on=gate_on)) if _pf else _text(
        _render_gated(_pf, gate_on=gate_on))

    _hits = [_w for _w in _BANNED_ON_SCREEN if _w in _body]
    assert not _hits, (
        f"（{state} / gate={'ON' if gate_on else 'OFF'}）畫面上出現了內部語言："
        + "、".join(_hits)
        + "\n⛔ 客戶 2026-09-08 拍板線框 §2 第 4 條：使用者要知道的是"
          "「這個數字為什麼是空的」，不是「我們送到哪裡了」。\n"
          "⚠️ 完整的工程理由不是刪掉，是**搬回程式碼註解**。\n" + _body)

    _grew = {_w: (_body.count(_w), _n) for _w, _n in _SCREEN_JARGON_DEBT.items()
             if _body.count(_w) > _n}
    assert not _grew, (
        f"（{state} / gate={'ON' if gate_on else 'OFF'}）既有的內部語言變多了"
        f"（實際 vs 允許）：{_grew}\n"
        "⛔ `_SCREEN_JARGON_DEBT` 是**棘輪**，不是豁免清單 —— 只准變少。\n"
        "   要新增一句含這些字的文案，正解是換個講法，不是把數字調大。\n" + _body)


def test_the_jargon_debt_numbers_are_still_real():
    """⭐ **棘輪的正對照：`_SCREEN_JARGON_DEBT` 記的數字必須真的是今天的數字。**

    ⛔ 沒有這一條，把 `{"取數": 1}` 寫成 `{"取數": 99}` 就等於默默豁免 ——
    上面那條會永遠綠。**棘輪只有在起點是真的時候才是棘輪。**
    """
    _body = _own_screen(_sk._render(portfolio=_sk.RICH_HOLDINGS))
    _stale = {_w: (_body.count(_w), _n) for _w, _n in _SCREEN_JARGON_DEBT.items()
              if _body.count(_w) != _n}
    assert not _stale, (
        f"既有債的次數已經不是登記的那個數字了（實際 vs 登記）：{_stale}\n"
        "  · 變少了 → 太好了，把登記的數字**調小**（那是收緊）。\n"
        "  · 變多了 → 上面那條棘輪應該已經先紅了。\n"
        "⛔ 不要為了讓它綠而把數字調大。")


def test_the_two_words_the_client_named_are_really_gone():
    """⭐ **本條單獨釘客戶點名的那兩個字，⛔ 不與上面那張大表共用。**

    上面那張表是「一族字」，人可以主張「這個字不算內部語言」而把它從表裡拿掉。
    **這兩個字不行** —— 它們是客戶 2026-09-08 在線框 §2 裡**逐字點名**的。
    分開一條，是為了讓「把它從清單裡拿掉」這個動作**看得見**。
    """
    for _state, _pf in (("rich", _sk.RICH_HOLDINGS), ("four", FOUR_WAY)):
        for _gate in (False, True):
            _body = _own_screen(_render_gated(_pf, gate_on=_gate))
            for _w in ("已送客戶確認", "Jaccard"):
                assert _w not in _body, (
                    f"（{_state} / gate={'ON' if _gate else 'OFF'}）"
                    f"客戶點名要拿掉的「{_w}」又回到畫面上了。\n" + _body)


# ══════════════════════════════════════════════════════════════════
# ⑤ 白話解釋：從共用 SSOT 讀，而且只解釋表上真的有的欄位
# ══════════════════════════════════════════════════════════════════
def test_the_plain_language_lines_come_from_the_shared_ssot():
    """⛔ 三句白話**必須**來自 `METRIC_EXPLAINERS[key]["short"]`，本頁不准自己寫一句。

    **線框 §1 逐字**：「現有 `METRIC_EXPLAINERS` 的 `body` 太長……所以**要在同一份 SSOT
    上加一個 `short` 欄位**，長版留給展開區用 —— **不另開第二份文案**。」

    **為什麼這一條重要**：⑧ 與 ⑨ 之後也要接同樣這幾句白話。
    每一頁自己寫一句 ⇒ 同一個指標三種說法，而改了其中一份**沒有任何東西會報錯**
    （`CLAUDE.md §2.1`）。
    """
    from ui.helpers.chart.metric_explainers import METRIC_EXPLAINERS

    _lines = _metric_plain_language()
    assert len(_lines) == len(METRIC_PLAIN_LANGUAGE_KEYS), (
        f"少了幾句白話（應有 {len(METRIC_PLAIN_LANGUAGE_KEYS)} 句，實得 {len(_lines)}）——\n"
        "多半是某個 key 的 `short` 不見了，而少一句是**無聲**的：畫面不會壞，"
        "只是那個指標從此沒有人解釋。")
    for _col, _key in METRIC_PLAIN_LANGUAGE_KEYS:
        _item = METRIC_EXPLAINERS.get(_key) or {}
        assert _item.get("short"), (
            f"`METRIC_EXPLAINERS[{_key!r}]` 沒有 `short` —— "
            "⑥ 的逐檔表底下就會少一句白話。")
        assert f"{_col}：{_item['short']}" in _lines, (
            f"畫面上那句白話不是 SSOT 的 `short`（{_key}）——\n"
            "  ⛔ 在本頁自己寫一句，就是第二份文案（§2.1）。\n"
            f"  SSOT：{_item['short']!r}\n  實得：{_lines!r}")


def test_the_plain_language_lines_only_explain_columns_that_are_really_on_the_table():
    """⭐ **解釋一個表上沒有的欄位，就是本 session 貫穿九輪的那個缺陷類別。**

    三句白話的左邊那個字（`Sharpe` / `最大回撤` / `配息覆蓋`）**必須是
    `HEALTH_TABLE_COLUMNS` 的成員**，而且必須是**畫面上那張表真的畫出來的表頭**。

    ⚠️ **兩半都要**：只驗常數 ⇒ 有人把欄位從表裡拿掉、常數忘了改，照樣綠
    （那正是 ⑦ 第四輪記下的「**守衛守的是替身**」）。
    """
    _cols = {_c for _c, _ in METRIC_PLAIN_LANGUAGE_KEYS}
    _absent = _cols - set(HEALTH_TABLE_COLUMNS)
    assert not _absent, (
        f"白話解釋講的欄位不在 `HEALTH_TABLE_COLUMNS` 裡：{sorted(_absent)}\n"
        f"  表上的欄位：{list(HEALTH_TABLE_COLUMNS)}")

    _parts = _render(portfolio=FOUR_WAY)
    _headers = [_p for _p in _parts if _p.startswith("[dataframe] ")]
    assert _headers, "畫面上沒有任何表格 —— 有持股時逐檔體檢表應該畫得出來。"
    _on_screen = {_c for _c in _headers[0][len("[dataframe] "):].split("　") if _c}
    _ghost = _cols - _on_screen
    assert not _ghost, (
        f"白話解釋講的欄位**畫面上那張表沒有**：{sorted(_ghost)}\n"
        f"  畫面上的表頭：{sorted(_on_screen)}\n"
        "⛔ 解釋一個看不到的欄位，比不解釋更讓人困惑。")


# ══════════════════════════════════════════════════════════════════
# ⑥ 三張卡：從「指標」改成「一件事」（線框 §2 第 3 條）
# ══════════════════════════════════════════════════════════════════
def test_the_eating_card_names_the_funds_it_counted():
    """⛔ 「吃本金警示」卡不只給檔數，**還要點名是哪幾檔**（線框那張卡的第三行）。

    **線框 §2 逐字**：「**三張卡從「指標」改成「一件事」。** 現況三張卡是三個名詞；
    改成「**這是什麼意思、是哪幾檔**」。」

    ⚠️ **判準是「每一檔在吃本金的都被點到」，不是「有沒有出現任何代碼」** ——
    只印第一檔的話，第二檔以後的使用者一樣得自己去表裡找。
    """
    from ui.views.page_02_health import _eating_labels, _uniq_by_code

    _funds = _uniq_by_code(_sk.RICH_HOLDINGS)
    _eating = _eating_labels(_funds)
    assert _eating, ("前提不成立：`RICH_HOLDINGS` 裡應該有在吃本金的檔"
                     "（`_fund` 的預設 div=8 / ret=2）。")

    _seg = _sk._segments(_render(portfolio=_sk.RICH_HOLDINGS))
    _body = "\n".join(_seg.get("吃本金警示", []))
    assert _body, f"「吃本金警示」這張卡不見了。現有單位：{list(_seg)}"
    _unnamed = [_l for _l in _eating if _l not in _body]
    assert not _unnamed, (
        f"卡片上少了這幾檔的名字：{_unnamed}\n"
        "⛔ 只給「N 檔」的話，使用者還是得自己去下面那張九欄表逐列比對 ——"
        "那正是這一批要修掉的畫面。\n" + _body)
    # ⛔⛔ **這一條斷言 2026-09-09 被獨立稽核判為「釘錯東西」，改掉並留痕。**
    #
    # ~~`assert "配息覆蓋低於 1.0" in _body`~~ ——
    # 它**強迫這張卡說出一句描述錯集合的話**：那張卡的主數字只數 `red`
    # （`gap > NEAR_DIVIDEND_WARNING_PCT`），而「覆蓋低於 1.0」**還包含黃燈**。
    # **純算術：`ret=6.5 div=8.0 → coverage=0.81 < 1.0`，但 `gap=1.5pp` → yellow，
    # 不在那個數字裡。**
    #
    # ⚠️⚠️ **最難堪的是：同一個檔案的
    # :func:`test_the_deliberate_deviation_from_the_wireframe_is_still_deliberate`
    # 早就把這個道理寫出來了** —— 它逐字說明為什麼**不照抄線框**那句
    # 「<1.0 就是在吃本金」（會與卡片判準打架）。
    # **然後這一條卻強制那張卡說出前一段禁止的那句話。**
    # **偏離 (d) 的理由本身就推翻了它自己的實作。**
    #
    # **現行判準：卡片必須講出它真正在數的那個門檻**（數字走 SSOT），
    # **而且不得再出現那句描述錯集合的話**。
    from shared.signal_thresholds import NEAR_DIVIDEND_WARNING_PCT as _gap

    assert f"超過 {_gap:.0f} 個百分點" in _body, (
        "卡片沒有講出它真正在數的那個門檻（缺口超過 N 個百分點）——\n"
        "  ⛔ 沒有它，使用者不知道這個「N 檔」是照什麼標準數出來的。\n" + _body)
    for _wrong in ("配息覆蓋低於 1.0", "覆蓋率低於 1.0", "覆蓋低於 1.0"):
        assert _wrong not in _body, (
            f"卡片又出現了「{_wrong}」——\n"
            "  ⛔ 那句話描述的集合**比這張卡真正數的那一個大**（它把黃燈也含進去），\n"
            "     而黃燈那幾檔**不在**這個數字裡。同一張卡、兩個集合。\n"
            "  ⚠️ 要講白話可以，但要講**它真的數的那件事**。\n" + _body)
    assert "本金配回來給你" in _body, (
        "卡片沒有用白話講「這是什麼意思」（線框第 3 條：從「指標」改成「一件事」）。\n"
        + _body)


def test_the_eating_card_says_nothing_about_funds_when_there_are_none():
    """⭐ **上一條的反面：一檔都沒有在吃本金時，⛔ 不准點名任何一檔。**

    沒有這一條，「把全部持股的名字都印上去」也會讓上一條全綠。
    """
    from ui.views.page_02_health import _eating_labels, _uniq_by_code

    _healthy = [_fund("H1", div=3.0, ret=9.0), _fund("H2", div=2.0, ret=8.0)]
    assert not _eating_labels(_uniq_by_code(_healthy)), (
        "前提不成立：這兩檔應該都不算吃本金（含息報酬遠高於配息率）。")

    _seg = _sk._segments(_render(portfolio=_healthy))
    _body = "\n".join(_seg.get("吃本金警示", []))
    _wrongly_named = [_f["code"] for _f in _healthy if _f["code"] in _body]
    assert not _wrongly_named, (
        f"一檔都沒有在吃本金，卡片上卻點名了 {_wrongly_named} —— "
        "使用者會以為那幾檔有問題。\n" + _body)


# ══════════════════════════════════════════════════════════════════
# ⑦ 突變測試 —— **把修復拔掉，對應的守衛必須真的轉紅**
# ══════════════════════════════════════════════════════════════════
# 憲法 §-1.5 v3 `03`-1 要的就是這個：「突變測試（**拔掉修復邏輯必須轉為紅燈**）」。
#
# ⭐⭐ **為什麼一定要有這一節（本 session 的實證，不是儀式）**
# 本 session 累計**十次以上**「假檢查」：**工具沒量到它宣稱在量的東西，
# 而空結果被讀成「沒問題」**。⑦ 那一批（PR #835）五輪擋下的 11 項，
# **沒有一項會讓 CI 變紅** —— 綠燈在本 repo 不具鑑別力。
#
# **每一顆都做三道正對照，缺一不可**：
#   landed   —— 突變**真的生效了**（改完之後值真的不一樣）
#   red      —— 對應的守衛**真的紅了**（而且是**那一條**，不是別條）
#   restored —— 還原之後**真的回綠**（否則下一條測試會踩到殘留狀態）
#
# ⚠️ **全部在同一個 process 內用 monkeypatch 做，不改檔案**：
#    改檔案的突變在本機要另外驗「檔案還 parse 得過」，而 pytest 已經 import 過模組，
#    改檔案**不會生效** —— 那會做出一顆「看起來紅不了」的假陰性。
def _asserts(fn, *a, **k) -> str:
    """跑一條守衛 → 回它的**失敗訊息**（空字串 ＝ 它通過了）。

    ⚠️ **回訊息而不是 `bool`，這一點是刻意的，而且是本 session 的實證教訓。**
    ⑦ 那一批（PR #835）第四輪自陳過一顆突變「**紅了、但是紅錯原因**」：
    突變改到了守衛自己讀的那份底本 ⇒ 它是被**前提斷言**擋下來的，
    而不是被**它要守的那件事**擋下來的。**那是一個假的綠燈證明。**
    ⇒ 本檔每一顆突變都必須指名「**紅的訊息裡要出現什麼**」，
    只斷言「有紅」是不夠的。
    """
    try:
        fn(*a, **k)
    except AssertionError as _exc:
        return str(_exc) or "<AssertionError 沒有訊息>"
    return ""


def _red_because(fn, marker: str, *a, **k) -> None:
    """斷言：`fn` **紅了**，而且**紅的原因裡有 `marker`**。"""
    _msg = _asserts(fn, *a, **k)
    assert _msg, f"守衛沒有轉紅（期望它因為「{marker}」而紅）。"
    assert marker in _msg, (
        f"守衛紅了，**但紅錯原因** —— 訊息裡找不到「{marker}」。\n"
        "⚠️ 那多半代表它是被**前提／fail-closed** 斷言擋下來的，\n"
        "   而不是被它真正要守的那件事擋下來的（＝一個假的綠燈證明）。\n"
        f"實際訊息：{_msg}")


def test_rewriting_the_coverage_line_back_to_the_wireframe_turns_its_guard_red(
        monkeypatch):
    """突變：把配息覆蓋那句白話改回線框的寫法（`<1.0 就是在吃本金`）。"""
    from ui.helpers.chart.metric_explainers import METRIC_EXPLAINERS

    _orig = METRIC_EXPLAINERS["div_coverage"]["short"]
    assert not _asserts(test_the_deliberate_deviation_from_the_wireframe_is_still_deliberate), (
        "CTRL：不突變時這條守衛就已經是紅的，本顆突變的結論沒有意義。")

    monkeypatch.setitem(METRIC_EXPLAINERS["div_coverage"], "short",
                        "配出來的錢有多少是真的賺到的，<1.0 就是在吃本金。")
    # landed
    assert METRIC_EXPLAINERS["div_coverage"]["short"] != _orig, "突變沒有生效。"
    assert "就是在吃本金" in _metric_plain_language()[2], "突變沒有傳到畫面那一層。"
    # red
    _red_because(test_the_deliberate_deviation_from_the_wireframe_is_still_deliberate,
                 "就是在吃本金")
    # restored
    monkeypatch.undo()
    assert METRIC_EXPLAINERS["div_coverage"]["short"] == _orig, "還原失敗。"
    assert not _asserts(test_the_deliberate_deviation_from_the_wireframe_is_still_deliberate)


def test_dropping_a_short_explainer_turns_the_plain_language_guard_red(monkeypatch):
    """突變：把 `METRIC_EXPLAINERS["sharpe"]["short"]` 拿掉。

    ⚠️ 這一顆守的是**無聲退化**：少一句白話**畫面不會壞**，
    只是那個指標從此沒有人解釋 —— 而使用者不會知道曾經有過。
    """
    from ui.helpers.chart.metric_explainers import METRIC_EXPLAINERS

    assert not _asserts(test_the_plain_language_lines_come_from_the_shared_ssot), (
        "CTRL：不突變時這條守衛就已經是紅的。")

    _mutant = {_k: _v for _k, _v in METRIC_EXPLAINERS["sharpe"].items()
               if _k != "short"}
    monkeypatch.setitem(METRIC_EXPLAINERS, "sharpe", _mutant)
    # landed
    assert "short" not in METRIC_EXPLAINERS["sharpe"], "突變沒有生效。"
    assert len(_metric_plain_language()) == 2, "突變沒有傳到畫面那一層。"
    # red
    _red_because(test_the_plain_language_lines_come_from_the_shared_ssot, "少了幾句白話")
    # restored
    monkeypatch.undo()
    assert METRIC_EXPLAINERS["sharpe"].get("short"), "還原失敗。"
    assert not _asserts(test_the_plain_language_lines_come_from_the_shared_ssot)


def test_putting_the_progress_language_back_turns_the_jargon_scan_red(monkeypatch):
    """突變：把「已送客戶確認」放回組合健康總分的灰態（＝退回本批之前的畫面）。

    ⭐ **這一顆同時證明了本族的射程比 AST 白名單那種寫法大**：
    違禁詞住在**模組層常數** `_SCORE_PENDING_NOTE` 裡 ——
    ⑨ 那條同族守衛就地登記過「**那些常數的定義處不在本清單裡**，
    也就是把違禁詞寫進那幾個常數，本條照樣抓不到」。**本族看得到它。**
    """
    assert not _asserts(test_no_internal_progress_language_reaches_the_screen,
                        "rich", False), "CTRL：不突變時這條守衛就已經是紅的。"

    monkeypatch.setattr(
        _p02, "_SCORE_PENDING_NOTE",
        "「五桶評等加權」的評等定義未定，已送客戶確認，**不先湊一個分數出來**。")
    # landed
    assert "已送客戶確認" in _p02._SCORE_PENDING_NOTE, "突變沒有生效。"
    assert "已送客戶確認" in _text(_render(portfolio=_sk.RICH_HOLDINGS)), (
        "突變沒有傳到畫面上。")
    # red —— 兩條都要紅（大表那條 ＋ 客戶點名那兩個字那條）
    _red_because(test_no_internal_progress_language_reaches_the_screen,
                 "已送客戶確認", "rich", False)
    _red_because(test_the_two_words_the_client_named_are_really_gone, "已送客戶確認")
    # restored
    monkeypatch.undo()
    assert "已送客戶確認" not in _p02._SCORE_PENDING_NOTE, "還原失敗。"
    assert not _asserts(test_no_internal_progress_language_reaches_the_screen,
                        "rich", False)


def test_drawing_the_filter_form_in_the_empty_state_turns_its_guard_red(monkeypatch):
    """突變：把「診斷條件」表單搬回空狀態前面（＝退回本批之前的順序）。"""
    assert not _asserts(test_the_empty_state_draws_no_filter_form), (
        "CTRL：不突變時這條守衛就已經是紅的。")

    _orig_empty = _p02._render_no_holdings

    def _both() -> None:
        _p02._render_filter_form()
        _orig_empty()

    monkeypatch.setattr(_p02, "_render_no_holdings", _both)
    # landed
    _parts = _render(portfolio=[])
    assert any(_p.startswith("[slider]") for _p in _parts), "突變沒有生效。"
    # red
    _red_because(test_the_empty_state_draws_no_filter_form, "[slider]")
    # restored
    monkeypatch.undo()
    assert not any(_p.startswith("[slider]") for _p in _render(portfolio=[])), "還原失敗。"
    assert not _asserts(test_the_empty_state_draws_no_filter_form)


def test_deleting_the_whole_form_turns_the_positive_control_red(monkeypatch):
    """突變：把表單整個刪掉（不只空狀態，有持倉時也不畫）。

    ⭐ **這一顆證明的是「上一顆不是靠刪功能通過的」** ——
    沒有這條正對照，把 `_render_filter_form` 整支拿掉會讓上一顆全綠。
    """
    assert not _asserts(test_the_form_is_still_there_when_there_are_holdings), (
        "CTRL：不突變時這條守衛就已經是紅的。")

    monkeypatch.setattr(_p02, "_render_filter_form", lambda: None)
    # landed
    assert not any(_p.startswith("[slider]")
                   for _p in _render(portfolio=FOUR_WAY)), "突變沒有生效。"
    # red
    _red_because(test_the_form_is_still_there_when_there_are_holdings, "少了 widget")
    # restored
    monkeypatch.undo()
    assert any(_p.startswith("[slider]") for _p in _render(portfolio=FOUR_WAY)), "還原失敗。"
    assert not _asserts(test_the_form_is_still_there_when_there_are_holdings)


def test_dropping_the_next_step_turns_its_guard_red(monkeypatch):
    """突變：問題點名了，但**不附下一步**（＝本批之前「只有判定沒有下一步」的畫面）。"""
    assert not _asserts(test_every_named_problem_carries_a_next_step), (
        "CTRL：不突變時這條守衛就已經是紅的。")

    monkeypatch.setattr(_p02, "_switch_action", lambda: "")
    # landed
    _body = "\n".join(_conclusion_slice(_render(portfolio=FOUR_WAY)))
    assert where_to_find("switch") not in _body, "突變沒有生效。"
    # red
    _red_because(test_every_named_problem_carries_a_next_step, "條下一步")
    # restored
    monkeypatch.undo()
    assert where_to_find("switch") in "\n".join(
        _conclusion_slice(_render(portfolio=FOUR_WAY))), "還原失敗。"
    assert not _asserts(test_every_named_problem_carries_a_next_step)


def test_truncating_the_conclusion_heading_turns_the_verbatim_guard_red(monkeypatch):
    """突變：把結論層標題**剪短**（不是換掉，是剪短）。

    ⭐ **這一顆針對的是 ⑦ 第三／第四輪各打穿一次的那個形狀**：
    `in` 是子字串比對，**剪短仍然是子字串** ⇒ 舊寫法擋不住剪短。
    本檔改成「必須等於一整行（或連續數整行）」，所以剪在行中間就不再是任何一種組合。
    """
    _short = CONCLUSION_HEADING[:-3]
    assert _short != CONCLUSION_HEADING and _short in CONCLUSION_HEADING, (
        "前提：這一顆突變是「剪短」，而剪短仍然是原字串的子字串。")
    # 剪短之後**仍然**是整節的子字串 —— 這就是舊判準擋不住它的原因。
    assert _squash(_short) in _squash("".join(_wf_pres())), (
        "前提不成立：剪短後的字串應該仍然出現在線框裡（否則這顆突變沒有代表性）。")
    # red —— 新判準（整行）把它擋下來
    assert _squash(_short) not in _wf_line_runs(), (
        "剪短後的標題仍然被判成「線框逐字」—— 本檔的行錨點是空的。")
    # ...而完整的那一個必須通過（正對照）
    assert _squash(CONCLUSION_HEADING) in _wf_line_runs(), (
        "CTRL：完整的標題反而不被承認，那是假紅燈。")


def test_making_every_fund_look_clear_turns_the_naming_guards_red(monkeypatch):
    """突變：把逐檔判定**一律漂白成「沒有查出問題」**。

    ⛔ 這是本頁最貴的一種退化：畫面全綠、每個數字都在，
    而使用者手上真的有一檔在吃本金 —— **他不會知道**（`CLAUDE.md §1`）。
    """
    assert not _asserts(test_every_named_problem_carries_a_next_step), (
        "CTRL：不突變時這條守衛就已經是紅的。")

    _orig = _p02._fund_findings

    def _whitewash(funds):
        _recs = _orig(funds)
        for _r in _recs:
            _r["group"], _r["reasons"], _r["blind"] = "clear", [], []
        return _recs

    monkeypatch.setattr(_p02, "_fund_findings", _whitewash)
    # landed
    _body = "\n".join(_conclusion_slice(_render(portfolio=FOUR_WAY)))
    assert GROUP_HEADLINES["problem"] not in _body, "突變沒有生效。"
    # red
    _red_because(test_every_named_problem_carries_a_next_step, "沒有「要處理」那一群")
    # restored
    monkeypatch.undo()
    assert GROUP_HEADLINES["problem"] in "\n".join(
        _conclusion_slice(_render(portfolio=FOUR_WAY))), "還原失敗。"
    assert not _asserts(test_every_named_problem_carries_a_next_step)


# ══════════════════════════════════════════════════════════════════
# ⑧ 量測工具自己的正對照 —— **本 session 十次以上的假檢查都長這個形狀**
# ══════════════════════════════════════════════════════════════════
# 已知形狀（本 session 累計，全部是**工具沒量到它宣稱在量的東西，
# 而空結果被讀成「沒問題」**）：harness 缺旗標／腳本寫死路徑沒讀到突變副本／
# no-op 突變／`sys.modules` 只清一半／sha256 迴圈 N=0／`pgrep` 配對到自己／
# 突變錨點過期／整節比對讓突變存活／`.count("")` 使條件恆真／
# `git ls-tree` 回 N=0 看起來像通過。
#
# ⇒ **本節逐一證明本檔用到的每一個量測工具，在該有輸出的時候真的有輸出。**


def test_the_wireframe_run_set_is_not_empty():
    """⛔ `_wf_line_runs()` 是空的話，**每一條「線框逐字」都會紅**（假紅燈）；
    而如果它「什麼都收得進去」，每一條都會綠（假綠燈）。**兩邊都要證。**
    """
    _runs = _wf_line_runs()
    assert len(_runs) > 20, (
        f"線框 run 集合只有 {len(_runs)} 個 —— 錨點或 `<pre>` 結構變了，"
        "本檔的字表比對已經失去對象。")
    # 反面：一句線框裡沒有的話**不准**在集合裡
    assert _squash("這句話線框裡完全沒有") not in _runs, (
        "run 集合把不存在的句子也收進來了 —— 它不具鑑別力。")


def test_the_gated_harness_really_flips_the_gate():
    """⭐⭐ **`_render_gated(gate_on=True)` 必須真的把閘門打開。**

    這是 ⑦ 第五輪那一課的**前提**：如果 harness 根本沒把旗標撥過去，
    「兩個世界都掃過了」就是一句假話 —— 而它會**安靜地**假，因為
    「gate=ON 也沒掃到違禁詞」與「gate=ON 根本沒跑」在輸出上長得一模一樣。

    ⚠️ 本 session 明確記載過這個形狀：**harness 缺旗標，空結果被讀成「沒問題」**。
    """
    _off = _text(_render_gated(_sk.RICH_HOLDINGS, gate_on=False))
    _on = _text(_render_gated(_sk.RICH_HOLDINGS, gate_on=True))
    assert _off != _on, (
        "兩個世界的畫面一模一樣 —— 閘門根本沒有被撥開，"
        "「gate=ON 也掃過了」是一句假話。")
    # gate=OFF：委派區是灰的（那句「尚未載入」在）
    assert "尚未載入" in _off, "gate=OFF 時委派區應該是灰態。\n" + _off
    # gate=ON：灰態消失、換成委派區自己畫的東西
    assert "尚未載入" not in _on, (
        "gate=ON 時委派區仍然是灰的 —— 閘門的回傳值沒有被吃進去。\n" + _on)
    # 而且**還原乾淨**：跑完之後 `_Rec` 必須是原來那一個
    assert _sk._Rec.__name__ == "_Rec", (
        f"`_render_gated` 沒有把 `_Rec` 還原（現在是 {_sk._Rec.__name__}）——"
        "後面每一條測試都會在被汙染的 harness 上跑。")


def test_the_own_screen_cut_really_cuts_something():
    """⛔ `_own_screen()` 若切到整頁（或切成空的），內部語言掃描就沒有意義。"""
    _parts = _render(portfolio=_sk.RICH_HOLDINGS)
    _own = _own_screen(_parts)
    _all = _text(_parts)
    assert _own, "`_own_screen()` 切出來是空的 —— 掃描沒有對象。"
    assert len(_own) < len(_all), (
        "`_own_screen()` 沒有切掉任何東西 —— 委派區的輸出還在射程內，"
        "而那一塊是本批動不了的舊模組（見 `_DELEGATED_HEADING` 的長註）。")
    # 正對照：本頁自己的東西必須留在裡面
    assert CONCLUSION_HEADING in _own and "尚未載入" not in _own, (
        "切點不對：結論層應該留著，委派區的灰態應該被切掉。\n" + _own)


def test_the_banned_word_list_is_actually_discriminating():
    """⛔ 內部語言那張表如果**一個字都掃不到任何東西**，它就只是裝飾。

    ⚠️ 本條不是驗「畫面上有違禁詞」（那當然沒有），而是驗**掃描機制本身會命中** ——
    拿一段**故意含違禁詞**的假畫面餵給同一個比對邏輯，它必須抓到。
    """
    _fake = "⬜ 這一塊的評等定義未定，已送客戶確認；相似度走 Jaccard。"
    _hits = [_w for _w in _BANNED_ON_SCREEN if _w in _fake]
    assert set(_hits) >= {"已送客戶確認", "Jaccard"}, (
        f"比對邏輯抓不到明明就在字串裡的違禁詞：{_hits}")


def test_the_card_text_producers_carry_no_jargon():
    """⭐⭐ **本條補的是上面那族掃描的一個真缺口，而它是一顆存活的突變逼出來的。**

    **怎麼發現的（留痕，因為結論違反直覺）**：本組在檔案層跑突變矩陣時，
    把 `Jaccard` 放回 :func:`_shadow_formula` —— **整族內部語言掃描全綠、突變存活。**
    **根因不是判準寫錯，是那句話在本機根本沒有被畫出來**：
    影子基金重疊那張卡要 `numpy` 才算得出重疊度，本機沒有 `numpy` ⇒
    卡片走灰態 ⇒ **那句公式一次都沒有進到渲染紀錄裡**。
    ⇒ **「掃過畫面、沒掃到違禁詞」與「那句話根本沒被畫出來」在輸出上長得一模一樣。**
    這正是本 session 累計十次以上的那個形狀：
    **工具沒量到它宣稱在量的東西，而空結果被讀成「沒問題」。**

    ⇒ 本條**不經渲染**，直接向產生那些句子的函式要字串。
    **它在 CI（有 numpy）與本機（沒有 numpy）給的是同一個答案。**

    ⚠️ **本條與上面那族不重複、也不互相取代**：
    上面那族看的是「**畫面上實際有什麼**」（含它們被組進句子之後的樣子），
    本條看的是「**這些句子本身**」（不管當下畫不畫得出來）。
    **缺任一邊都有一個掃不到的角落。**
    """
    from ui.views.page_02_health import (
        _eating_note, _eating_reason, _LAG_PENDING_NOTE, _SCORE_PENDING_NOTE,
        _shadow_formula, _switch_action, GROUP_HEADLINES as _G)

    _texts: dict[str, str] = {
        "_shadow_formula()": _shadow_formula(),
        "_SCORE_PENDING_NOTE": _SCORE_PENDING_NOTE,
        "_LAG_PENDING_NOTE": _LAG_PENDING_NOTE,
        "_switch_action()": _switch_action(),
        "_eating_note(有壞消息)": _eating_note(
            {"eating": 2, "near": 1, "healthy": 1, "unknown": 1}, ["AAA", "BBB"]),
        "_eating_note(全綠)": _eating_note(
            {"eating": 0, "near": 0, "healthy": 3, "unknown": 0}, []),
        "_eating_reason(覆蓋 0.62)": _eating_reason({"coverage": 0.62}),
        "_eating_reason(覆蓋負)": _eating_reason({"coverage": -0.3}),
        "_eating_reason(只有 gap)": _eating_reason({"coverage": None, "gap_pct": 6.0}),
        "_eating_reason(什麼都沒有)": _eating_reason(None),
        "三群抬頭": "／".join(_G.values()),
    }
    _bad = {_k: [_w for _w in _BANNED_ON_SCREEN if _w in _v]
            for _k, _v in _texts.items()
            if any(_w in _v for _w in _BANNED_ON_SCREEN)}
    assert not _bad, (
        "下列**會被畫在使用者眼前**的句子裡有內部語言：\n  "
        + "\n  ".join(f"{_k}: {_v} —— {_texts[_k]!r}" for _k, _v in _bad.items())
        + "\n⛔ 客戶 2026-09-08 拍板線框 §2 第 4、5 條。")

    # ⛔ 正對照：這條掃描必須真的會命中 —— 否則它只是裝飾。
    _probe = "門檻：相似度 ≥ 0.70（持股 Jaccard × 0.6）"
    assert [_w for _w in _BANNED_ON_SCREEN if _w in _probe] == ["Jaccard"], (
        "比對邏輯抓不到明明就在字串裡的 `Jaccard` —— 本條不具鑑別力。")


def test_the_eating_reason_never_invents_a_number():
    """⛔ 「每領 100 元有 N 元是本金」那句話**只在覆蓋率算得出來、而且落在 [0,1) 時**才講。

    ⚠️ **覆蓋率是 `含息報酬 ÷ 配息率`，它可以是負的**（近一年含息報酬為負）。
    照同一個算式硬套會印出「每領 100 元有 **130** 元是配回你自己的本金」——
    **算得出來、但沒有意義**，而使用者只會覺得系統壞了。
    覆蓋率**算不出來**時更嚴重：那時連 `N` 都沒有，一不小心就會印出 `0` 或空白（§1）。
    """
    _pos = _p02._eating_reason({"coverage": 0.62})
    assert "38 元" in _pos, f"覆蓋 0.62 應該換算成「每領 100 元有 38 元」：{_pos!r}"

    _neg = _p02._eating_reason({"coverage": -0.3})
    assert "每領 100 元有" not in _neg, (
        f"覆蓋率是負的時候仍然印了「每領 100 元有 N 元」：{_neg!r}")
    assert "負" in _neg, f"覆蓋率是負的時候沒有講清楚發生什麼事：{_neg!r}"

    _gap = _p02._eating_reason({"coverage": None, "gap_pct": 6.0})
    assert "6.0 個百分點" in _gap, (
        f"覆蓋率算不出來時沒有退回 SSOT 算得出來的 `gap_pct`：{_gap!r}")

    _none = _p02._eating_reason(None)
    assert _none and "0" not in _none and NOT_READY_MARK not in _none, (
        f"什麼數字都沒有時，這句話不得編一個數字、也不得只丟一個 {NOT_READY_MARK}：{_none!r}")


# ══════════════════════════════════════════════════════════════════
# ⑨ 指路：名字必須三邊同源（2026-09-09，被 CI 逼出來的）
# ══════════════════════════════════════════════════════════════════
def test_the_where_pointers_and_the_heading_are_one_string(monkeypatch):
    """⭐⭐ **改一次 SSOT，抬頭與兩處指路要一起變。** 這是「同一份」的可執行定義。

    ## 它從哪來（留痕，因為它不是本組掃出來的）

    本 PR 初版把 ⑥ 結論層「判不出來」那一群的指路寫成
    ~~「下方『**② 依據**』的逐檔體檢表可先逐檔看」~~ ——
    **照客戶拍板的線框字面抄的**，但畫面上那個標題的全名是
    「**🧾 ② 依據 — 憑什麼這樣說**」⇒ **名字對不上，使用者照著找會找不到**。
    `tests/test_batch2_top_card_grid.py::
    test_every_where_names_something_that_exists_on_screen` **在 CI 上把它擋下來**。
    ⚠️ **本機當時看不到它** —— 那個檔案在本機因為缺 `plotly` / `requests` / `numpy`
    連 collect 都失敗。**「本機全綠」當時涵蓋不到 repo 自己最相關的那條守衛。**

    ## 這一條守的是什麼（與那條既有守衛**不重複**）

    那一條問的是「**這個名字畫面上有沒有**」（字面值比對，逐一驗）。
    **本條問的是「**這三處是不是同一份**」** —— 也就是**未來會不會漂移**。
    ⛔ 兩條缺一不可：
      · 只有那一條 → 三份字面值今天都對，**改了抬頭的那一刻才紅**，
        而在那之前使用者已經被指錯一段時間了。
      · 只有本條 → 三份同源，但可能**同時指向一個畫面上沒有的名字**。

    ## 為什麼要用突變而不是「檢查有沒有 import 那個常數」

    `import` 了不代表**用**了。本條直接把常數換掉，看**畫面上三個地方是不是都跟著變** ——
    有任何一處是手抄的，它就不會變，本條就紅。
    """
    from ui.views import page_02_health as _m

    _real = _m.HOLDINGS_HEALTH_TABLE_BLOCK
    assert _real, "區塊抬頭的 SSOT 常數是空的。"

    # ── CTRL：不突變時，三處都應該講同一個名字 ─────────────────────
    _parts = _render(portfolio=FOUR_WAY)
    _head = [_p for _p in _parts if _p == f"[markdown] #### {_real}"]
    assert _head, (
        f"畫面上找不到抬頭 `#### {_real}` —— 抬頭沒有讀 SSOT，或區塊不見了。\n"
        + _text(_parts))
    _pointers = [_p for _p in _parts
                 if _p.startswith("[caption] ") and f"「{_real}」" in _p]
    assert len(_pointers) >= 2, (
        f"指向「{_real}」的灰態指路只有 {len(_pointers)} 處，應至少 2 處"
        "（組合健康總分 ＋ 結論層「判不出來」那一群）。\n" + _text(_parts))

    # ── 突變：把 SSOT 換掉，三處必須**全部**跟著變 ──────────────────
    _fake = "逐檔體檢表_MUTANT"
    monkeypatch.setattr(_m, "HOLDINGS_HEALTH_TABLE_BLOCK", _fake)
    # landed
    assert _m.HOLDINGS_HEALTH_TABLE_BLOCK == _fake, "突變沒有生效。"
    _mut = _render(portfolio=FOUR_WAY)
    _mut_txt = _text(_mut)
    assert f"[markdown] #### {_fake}" in _mut, (
        "改了 SSOT，**抬頭沒有跟著變** —— 抬頭是手抄的字面值。\n" + _mut_txt)
    _mut_pointers = [_p for _p in _mut
                     if _p.startswith("[caption] ") and f"「{_fake}」" in _p]
    assert len(_mut_pointers) == len(_pointers), (
        f"改了 SSOT，只有 {len(_mut_pointers)} 處指路跟著變（原本 {len(_pointers)} 處）"
        "—— 有指路是手抄的字面值，抬頭一改它就會指錯。\n" + _mut_txt)
    assert f"「{_real}」" not in _mut_txt, (
        "改了 SSOT，畫面上還留著舊名字 —— 那一處是手抄的。\n" + _mut_txt)

    # restored
    monkeypatch.undo()
    assert _m.HOLDINGS_HEALTH_TABLE_BLOCK == _real, "還原失敗。"
    assert f"[markdown] #### {_real}" in _render(portfolio=FOUR_WAY)


def test_no_where_pointer_hand_writes_a_block_name(monkeypatch):
    """⛔ 本頁的 `where=` **不准再出現手抄的 `「區塊名」` 字面值**。

    ⚠️ **判準刻意是「有沒有 `「」` 包住的字面值」，不是「那個名字對不對」** ——
    後者由 `tests/test_batch2_top_card_grid.py` 那條既有守衛負責，
    **本條負責的是「不要再產生第二份真相源」**。
    ⛔ 兩條都要：一個名字可以**今天是對的、明天漂掉**，
    而 `CLAUDE.md §2.1` 要防的正是那一種。

    ⚠️ **本條只看本頁的 `where=` / `empty_where=`**（含 `_pending_where(...)` 的引數），
    **不看 `note` 或其他文案** —— 那些不是指路，不承諾「你去那裡找得到」。
    """
    _tree = ast.parse(SRC.read_text(encoding="utf-8"))
    _bad: list[str] = []
    for _n in ast.walk(_tree):
        if not isinstance(_n, ast.Call):
            continue
        _args: list[ast.AST] = []
        for _kw in _n.keywords:
            if _kw.arg in ("where", "empty_where"):
                _args.append(_kw.value)
        if (getattr(_n.func, "id", None) == "_pending_where"
                or getattr(_n.func, "attr", None) == "_pending_where"):
            _args.extend(_n.args)
        for _a in _args:
            for _s in ast.walk(_a):
                if isinstance(_s, ast.Constant) and isinstance(_s.value, str):
                    if "「" in _s.value and "」" in _s.value:
                        _bad.append(f"第 {getattr(_s, 'lineno', -1)} 行 {_s.value!r}")
    assert not _bad, (
        "本頁的「去哪補」裡有**手抄的區塊名字面值**：\n  " + "\n  ".join(_bad)
        + "\n⛔ 請改讀 SSOT（`shared/ui_control_labels` 或 `ui/helpers/story_nav`），"
          "讓畫抬頭的那一行與指路讀同一份。\n"
          "⚠️ 手抄的名字**今天可能是對的** —— 問題是抬頭改字的那一刻它不會跟著改，"
          "而使用者會被指到一個找不到的地方（本 PR 初版就是這樣被 CI 抓到的）。")

    # ⛔ 正對照：這個掃描必須真的抓得到 —— 否則它只是裝飾。
    _probe = ast.parse('not_ready("x", where=_pending_where("下方「某某表」可看"))')
    _hits = [_s.value for _s in ast.walk(_probe)
             if isinstance(_s, ast.Constant) and isinstance(_s.value, str)
             and "「" in _s.value and "」" in _s.value]
    assert _hits, "掃描邏輯抓不到明明就有 `「」` 的字面值 —— 本條不具鑑別力。"


# ══════════════════════════════════════════════════════════════════
# ⑩ 2026-09-09 獨立稽核擋下的兩項 —— 各自的守衛
# ══════════════════════════════════════════════════════════════════
def _coverage_of(fund: dict) -> "float | None":
    """這一檔的配息覆蓋率（走 SSOT，本檔不自己算）。"""
    from services.health.dividend import check_eating_principal_1y_mk
    _v = check_eating_principal_1y_mk(fund)
    return (_v or {}).get("coverage")


def test_the_eating_card_sentence_describes_the_set_it_actually_counts():
    """⛔⛔ **⛔1：卡片的說明句，不得描述一個比它真正數的更大的集合。**

    ## 純算術（可自驗，不需要渲染）

    `services/health/dividend.py::classify_eating_principal`::

        red    ⟺ gap_pct >  NEAR_DIVIDEND_WARNING_PCT
        yellow ⟺ 0 < gap_pct <= NEAR_DIVIDEND_WARNING_PCT

    ⇒ **`red ⊂ {coverage < 1.0}`，反過來不成立。**
    `ret=6.5 / div=8.0` → **coverage 0.81（低於 1.0）**、**gap 1.5pp → yellow**。

    ## 這一條釘的是什麼

    那張卡的主數字**只數 red**（跨頁一致性，見 `_eating_verdict` 的長註）。
    所以說明句**不得**用「覆蓋低於 1.0」去描述它 —— 覆蓋 0.81 的那一檔
    **不在那個數字裡，卻會被那句話涵蓋**。

    ⚠️ **本條與 `test_the_eating_card_names_the_funds_it_counted` 不重複**：
    那一條問「有沒有講出門檻／有沒有點名」，**本條拿一檔真的黃燈基金去證明兩個集合不同**。
    """
    _near = copy.deepcopy(_NEAR_FUND)
    _cov = _coverage_of(_near)
    assert _cov is not None and _cov < 1.0, (
        f"前提不成立：這一檔的覆蓋應該低於 1.0，實際 {_cov}")
    assert _near["code"] not in _eating_labels(_uniq_by_code([_near])), (
        "前提不成立：這一檔（黃燈）**不該**被算進吃本金的那個數字。\n"
        "  若它被算進去了，那是 `_eating_verdict` 的跨頁一致性被改掉了，"
        "要動的是那裡，不是本條。")

    from shared.signal_thresholds import NEAR_DIVIDEND_WARNING_PCT as _gap
    _note = _eating_note({"eating": 1, "near": 1, "healthy": 1, "unknown": 0}, ["X"])
    assert f"超過 {_gap:.0f} 個百分點" in _note, (
        f"說明句沒有講出它真正在數的門檻（缺口超過 {_gap:.0f} 個百分點）：{_note!r}")
    assert "低於 1.0" not in _note, (
        "說明句用「覆蓋低於 1.0」描述這張卡 —— **那個集合比它真正數的大**：\n"
        f"  覆蓋 {_cov:.2f} 的那一檔不在這個數字裡，卻被這句話涵蓋。\n"
        f"  實際：{_note!r}")


def test_the_clear_group_never_tells_a_near_fund_it_is_covered():
    """⛔⛔ **⛔2：「沒有查出問題」那一群不得對接近警戒的檔說「配息蓋得住」。**

    **稽核用本檔自己的 fixture 實測到的畫面**（同一個畫面上三個說法）::

        🟢 這 2 檔沒有查出問題 … 配息蓋得住、也沒有落後同類。   ← 結論層
        MID … 0.75 ⬜                                        ← 同頁表格
        吃本金警示 … 另有 1 檔接近警戒（缺口在 2pp 內）        ← 同頁卡片

    ⚠️ **舊守衛只驗那句是不是線框逐字，不驗它對那一群是不是真的** ——
    正是憲法 `EXCEPTIONS.md §8.3.P` 的 `P-GREYSCENARIO-1` 登記的
    「**形式滿分、內容全反**」。

    ⛔ **修法不是把那句話刪掉** —— 線框要那句話，要的是**對的那一群**才說。
    本條因此**兩個方向都釘**：該說的時候要說，不該說的時候不准說。
    """
    # ── 方向一：全部真的蓋得住 → 線框那句話必須出現 ─────────────
    _covered = "\n".join(_conclusion_slice(_render(portfolio=_ALL_COVERED)))
    assert CLEAR_NOTE in _covered, (
        "這一群每一檔的配息都真的蓋得住，卻沒有講出線框那句話。\n" + _covered)

    # ── 方向二：混了一檔接近警戒 → 那句話不准出現，而且要點名 ───
    _near_code = _NEAR_FUND["code"]
    _recs = _fund_findings(_uniq_by_code(copy.deepcopy(_CLEAR_WITH_NEAR)))
    _near_rec = next(_r for _r in _recs if _r["code"] == _near_code)
    assert _near_rec["near"] is True, (
        f"前提不成立：{_near_code} 應該被判成接近警戒。實際：{_near_rec}")
    assert _near_rec["group"] == "clear", (
        "前提改變了：接近警戒的檔不再落在「沒有查出問題」那一群。\n"
        "  ⚠️ 若這是刻意的（例如改成獨立一群），本條要跟著改 —— "
        "但**不准把它改回去說「蓋得住」**。\n" + str(_near_rec))

    _mixed = "\n".join(_conclusion_slice(_render(portfolio=_CLEAR_WITH_NEAR)))
    assert CLEAR_NOTE not in _mixed, (
        f"這一群裡有一檔（{_near_code}）的配息覆蓋**低於 1.0**，"
        f"畫面卻對它說「{CLEAR_NOTE}」——\n"
        "  ⛔ 同一頁的表格會顯示它的覆蓋率、卡片會說「另有 1 檔接近警戒」，"
        "**三個地方兩個結論**（`CLAUDE.md §2.1`）。\n" + _mixed)
    assert _near_code in _mixed, (
        f"接近警戒的那一檔（{_near_code}）沒有被點名 —— "
        "使用者不知道是哪一檔快要出問題。\n" + _mixed)


def test_a_fund_whose_dividend_data_is_missing_is_never_called_clear():
    """⛔ **必修 B：配息完全讀不到的檔，必須落進「判不出來」，⛔ 不是「沒有查出問題」。**

    ⚠️ **稽核實測這一支原本零守衛**：把 `_fund_findings` 裡
    `elif _eat_bucket == _EAT_UNKNOWN:` 改成 `elif False:` → **106 passed**，
    而畫面會把「配息完全讀不到」的檔印成「🟢 沒有查出問題 / 配息蓋得住」。
    **乾淨版的行為本來就是對的 —— 只是沒有人守著它。**
    """
    _blind_div = copy.deepcopy(_fund("NODIV", div=None, ret=4.0))
    _blind_div["metrics"].pop("annual_div_rate", None)
    _blind_div["moneydj_raw"]["risk_metrics"] = {
        "peer_compare": {"同類型平均": {"1Y": 1.0}}}

    _rec = _fund_findings([_blind_div])[0]
    assert _rec["group"] == "unknown", (
        "配息資料完全讀不到的那一檔被歸成了別群 —— "
        "「沒查到」不是「沒問題」（§1）。\n" + str(_rec))
    assert _rec["blind"], "落進「判不出來」卻沒有講出是哪一項查不動。"
    assert any("配息" in _b for _b in _rec["blind"]), (
        f"沒有講出「查不到配息資料」這件事：{_rec['blind']}")

    _body = "\n".join(_conclusion_slice(_render(portfolio=[_blind_div])))
    assert GROUP_HEADLINES["clear"] not in _body, (
        "畫面上把配息讀不到的那一檔說成「沒有查出問題」。\n" + _body)
    assert CLEAR_NOTE not in _body, (
        "畫面上對一檔連配息都讀不到的基金說「配息蓋得住」。\n" + _body)


@pytest.mark.parametrize("mode", ["raises", "same-both-ends", "no-excess"])
def test_the_lag_probe_fails_closed_in_every_degenerate_mode(mode: str, monkeypatch):
    """⛔ **必修 C：判準探針自己的三種退化模式，每一種都要 fail-closed。**

    `_lag_verdict_text()` 的 docstring 列了三種「問不出來」：**拋例外**、
    **兩端回同一句話**、**回不出超額報酬**。
    ⚠️ **稽核實測：原本只有第一種被走到過**（既有那條測試 monkeypatch 的是
    **消費端**，等於直接把答案設成 `None`）——
    **「兩端回同一句話」那一支從來沒有被跑過**。
    刪掉它 → **106 passed**，而配上一個退化的 `_grade`，
    **領先同類 8pp 的基金會被印成「要處理…落後 0.0 個百分點」**。

    ⛔ 三種模式都必須回 `None`（＝「不知道」），而**不是**回一個桶名 ——
    回桶名代表每一檔都會被拿去跟它比對，於是**要嘛全部要處理、要嘛全部沒問題**，
    兩種都是說謊。
    """
    from ui.helpers.fund import checkup as _ck

    if mode == "raises":
        def _grade(_r, _p):
            raise RuntimeError("degenerate")
    elif mode == "same-both-ends":
        # 兩端回**同一句話** ⇒ 分不出「最差」與「最好」。
        def _grade(_r, _p):
            return (0.0 if _p is not None else None), "⚠️ 落後（汰弱）"
    else:  # no-excess
        def _grade(_r, _p):
            return None, "⬜ 同類資料不足"

    monkeypatch.setattr(_ck, "_grade", _grade)
    assert _p02._lag_verdict_text() is None, (
        f"探針在退化模式「{mode}」下**沒有** fail-closed —— 它回了一個桶名。\n"
        "⛔ 分不出來就是不知道；回一個桶名會讓每一檔都拿去跟它比。")


def test_a_degenerate_grade_never_prints_a_lag_of_zero(monkeypatch):
    """⛔ **必修 C 的行為面**：`_grade` 退化時，⛔ 不得把領先的基金印成「落後 0.0 個百分點」。

    這是上一條 fail-closed 真正要防的畫面。**稽核構造的正是這個**：
    領先同類 8pp 的基金被印成「要處理…**落後 0.0 個百分點**」。
    """
    from ui.helpers.fund import checkup as _ck

    monkeypatch.setattr(_ck, "_grade", lambda _r, _p: (0.0, "⚠️ 落後（汰弱）"))
    _body = "\n".join(_conclusion_slice(_render(portfolio=_ALL_COVERED)))
    assert "落後 0.0 個百分點" not in _body, (
        "`_grade` 退化成「一律回同一句話 ＋ 超額報酬 0」時，"
        "畫面把領先同類的基金印成「落後 0.0 個百分點」。\n"
        "⛔ 探針分不出兩端時應該 fail-closed（回 `None`），"
        "那幾檔要落進「判不出來」。\n" + _body)


def test_the_shadow_note_matches_how_many_pairs_there_are():
    """⛔ **必修 A：影子基金卡的本文措辭，必須跟著「幾對」走。**

    ⚠️ **稽核實測這一句原本零守衛**：整句刪掉 → **106 passed**。
    而三檔互相重疊時，卡片主數字是「**3 對**」、本文卻寫「**這兩檔**」——
    **同一張卡上的兩個數字對不起來。**

    ⚠️ **本條對純函式下斷言、不經渲染**，理由與
    :func:`test_the_card_text_producers_carry_no_jargon` 同一條：
    那張卡要 `numpy` 才算得出重疊度，**本機沒有** ⇒ 走渲染的話這一條會對著灰態生效，
    而「灰態裡當然沒有那句話」與「那句話說錯了」在輸出上長得一模一樣。
    """
    _one = _shadow_pair_note(1)
    assert "這兩檔" in _one, (
        f"一對的時候沒有用線框那句話（「這兩檔…」）：{_one!r}")

    for _n in (2, 3, 7):
        _many = _shadow_pair_note(_n)
        assert f"{_n} 對" in _many, (
            f"{_n} 對的時候，本文沒有講出到底幾對：{_many!r}")
        assert "這兩檔" not in _many, (
            f"{_n} 對的時候，本文還在說「這兩檔」——"
            f"卡片的主數字會是「{_n} 對」，**同一張卡上兩個數字對不起來**：{_many!r}")
        assert "重疊" in _many, f"{_n} 對的時候，本文沒有講出「重疊」這件事：{_many!r}"
