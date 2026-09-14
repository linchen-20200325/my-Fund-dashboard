"""2026-09-14 合規移除守衛 —— 母法「不產生任何直接買賣建議」的兩個落地點。

## 這個檔在守什麼（先讀完這段，否則會以為它跟既有守衛重複）

客戶 2026-09-14 **逐案核准**拿掉兩處直接買賣建議，本檔就是那兩處的守衛：

  · **A 組｜總經綜合結論的「行動句」** —— `ui/views/page_01_macro.py`
    的 ② 依據表。`services/macro/composite_score.py::composite_verdict()`
    第 4 個元素 `action_text` 是逐字的買賣指示（「可滿倉持有」「分批進場」
    「拉高現金水位至 15-25%」「現金 30%+，核心轉防守型」…）。
    修法是在**消費端**把 `_action` 無條件清空（L2 是凍結範圍且另有消費者）。
  · **B 組｜說明書再平衡章節** —— `ui/tab6_manual.py`：章節名的
    `One-Click Rebalance`、偏離分級表的「動作」欄、以及指名
    「從最大衛星基金**贖回**、轉入最小核心基金」的白話文行動指南。

⚠️ **A 組為什麼一定要在「證據充足」的世界下驗**（本檔最重要的一句）：
`_action` 原本就會在**證據不足**時被清空。也就是說 —— **只跑預設／斷線狀態
的測試，在修好之前就已經是綠的**，它證明不了任何事。本檔因此
(1) 明確建構**兩個**證據充足的世界（悲觀警報側 + 全指標樂觀側），
(2) 用 :func:`test_precondition_both_worlds_are_evidence_sufficient`
**先把「我真的站在那個世界裡」斷言出來**。那條前提測試若紅，A 組其餘各條
的綠燈一律不算數。

⚠️ **五句 action_text 不在本檔手抄第二份**（§2.1 SSOT）：
:func:`_all_verdict_action_texts` 直接掃 `composite_verdict()` 取回。
L2 日後新增第六句，本檔自動跟著守 —— 手抄的黑名單做不到這件事。

## 本檔守得到什麼、守不到什麼（誠實揭露，不作全稱宣稱）

**守得到（每一條都做過突變實測，見各 test 的 docstring）**：
  - `_action = ""` 被刪掉／被搬回 `if not _ok:` 裡面 → A2/A4 轉紅。
  - 五句 action_text 任一句重新出現在 ② 依據表的列或表下註記 → A3 轉紅。
  - 再平衡分級表重新長出第二欄（**不論那一欄寫什麼字**）→ B3 轉紅。
  - 章節名重新掛上 `One-Click` / 「一鍵」→ B1 轉紅。
  - 被移除的那幾句指名買賣的字串重新出現 → B2 轉紅。

**守不到（據實寫明，不要把本檔讀成「合規已完成」）**：
  - **B2 是字串清單，不是語意檢查。** 有人用**不同措辭**重寫一句買賣建議
    （例如「偏離超過一成時應調整部位」），B2 抓不到。B3 的欄數鎖擋得住
    「把它塞回表格第二欄」這一種形態，擋不住「改寫成一段散文」。
  - **A3 比對的是五句逐字字串。** 有人把行動句**改寫**後直接寫進 UI，
    A3 抓不到；A2 只保證 `composite_action` 這條管道是空的。
  - **本檔只看 `ui/views/page_01_macro.py` 與 `ui/tab6_manual.py` 兩個檔。**
    本 repo 另有多處 `composite_verdict` 消費端（`ui/tab1_macro.py`、
    `services/realtime_signal.py`、`mcp_server/tools_macro.py`）與
    另一套獨立的行動文案（`services/macro/action_light.py` 的
    「可加碼／減碼」，由同一頁的 ① 結論渲染）—— **那些不在本批的授權範圍內，
    本檔不守，也不宣稱它們合規。** 詳見本批 PR 描述的「刻意沒做」一節。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_PAGE = _ROOT / "ui" / "views" / "page_01_macro.py"


# ════════════════════════════════════════════════════════════════
# 共用替身：把 `st.*` 呼叫錄下來
# ════════════════════════════════════════════════════════════════
class _Node:
    """`st.x`／`st.x.y(...)` 的替身：可呼叫、可取屬性、可當 context manager。"""

    def __init__(self, calls, name):
        object.__setattr__(self, "_calls", calls)
        object.__setattr__(self, "_name", name)

    def __call__(self, *a, **k):
        self._calls.append((self._name, a, k))
        if self._name == "columns":
            _s = a[0] if a else k.get("spec", 2)
            return [_Node(self._calls, f"col{_i}")
                    for _i in range(_s if isinstance(_s, int) else len(_s))]
        if self._name == "tabs":
            _l = a[0] if a else k.get("tabs", [])
            return [_Node(self._calls, f"tab{_i}") for _i, _ in enumerate(_l)]
        if self._name.split(".")[-1] in (
                "button", "checkbox", "toggle", "form_submit_button"):
            return False
        return _Node(self._calls, self._name + "()")

    def __getattr__(self, n): return _Node(self._calls, f"{self._name}.{n}")
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __len__(self): return 0
    def __iter__(self): return iter(())
    def __bool__(self): return False
    def __getitem__(self, i): return _Node(self._calls, f"{self._name}[{i!r}]")
    def __str__(self): return ""


class _SS(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k) from None

    def __setattr__(self, k, v): self[k] = v


class _Recorder:
    def __init__(self):
        object.__setattr__(self, "calls", [])
        object.__setattr__(self, "session_state", _SS())
        object.__setattr__(self, "secrets", {})

    def __getattr__(self, n): return _Node(self.calls, n)
    def __enter__(self): return self
    def __exit__(self, *a): return False

    def texts(self) -> list[str]:
        """所有被畫出去的字串參數（含 kwargs）。"""
        _out: list[str] = []
        for _n, _a, _k in self.calls:
            _out.extend(str(_x) for _x in _a)
            _out.extend(str(_v) for _v in _k.values())
        return _out


# ════════════════════════════════════════════════════════════════
# A 組｜總經綜合結論的行動句
# ════════════════════════════════════════════════════════════════
def _all_verdict_action_texts() -> tuple[str, ...]:
    """五句 `action_text` **從 L2 現場取回**，本檔不抄第二份（§2.1 SSOT）。"""
    from services.macro.composite_score import composite_verdict
    _seen: dict[str, None] = {}
    for _s in (-1e6, -60.0, -20.0, -12.0, -10.0, -7.0, -5.0, 0.0,
               5.0, 6.0, 10.0, 11.0, 30.0, 60.0, 1e6):
        _a = composite_verdict(float(_s))[3]
        if str(_a).strip():
            _seen[str(_a)] = None
    return tuple(_seen)


def _world_bearish() -> dict:
    """悲觀警報側 —— 半套證據即充足（規則 3 的不對稱，見 `evidence.py`）。

    這組 indicators 逐字取自既有的
    `tests/test_evidence_support.py::test_the_summed_verdict_keeps_the_pessimistic_alarm`，
    那條測試已經在守「這組必須 `sufficient=True`」。
    """
    return {"YIELD_10Y2Y": {"weight": 2, "score": -2},
            "YIELD_10Y3M": {"weight": 2, "score": -2},
            "HY_SPREAD":   {"weight": 2, "score": -2}}


def _world_bullish() -> dict:
    """全指標樂觀側 —— 「可滿倉持有」那一句住的地方，不能只驗悲觀側。"""
    from services.macro.evidence import MACRO_INDICATOR_SCORING_WEIGHTS as _W
    return {_k: {"value": 1.0, "weight": _w, "score": 1.0} for _k, _w in _W.items()}


_WORLDS = (("bearish-alarm", _world_bearish), ("bullish-full", _world_bullish))


def _render_evidence_layer(build):
    """在**證據充足**的世界跑 `_render_layer_evidence`，錄下送到畫面的東西。

    攔在 `render_evidence_table` 這個邊界上（它是 ② 依據表真正的出海口），
    不去 patch `streamlit` 本體 —— `ui/components/tables.styled_dataframe`
    是在函式內 `import streamlit`，patch 模組屬性攔不到它。
    """
    import ui.views.page_01_macro as _P

    _rec = _Recorder()
    _actions: list[tuple[str, object]] = []
    _table: dict = {}
    _names = ("build_evidence_rows", "build_evidence_footnotes",
              "split_evidence_footnotes")
    _orig = {_n: getattr(_P, _n) for _n in _names}
    _orig["render_evidence_table"] = _P.render_evidence_table
    _orig["st"] = _P.st

    def _capture_table(rows, footnotes=None, *, collapsed_footnotes=None):
        _table["rows"] = rows
        _table["footnotes"] = footnotes
        _table["collapsed"] = collapsed_footnotes

    try:
        for _n in _names:
            def _mk(_n=_n, _f=_orig[_n]):
                def _spy(*a, **k):
                    _actions.append((_n, k.get("composite_action", "<kwarg-missing>")))
                    return _f(*a, **k)
                return _spy
            setattr(_P, _n, _mk())
        _P.render_evidence_table = _capture_table
        _P.st = _rec
        _out = _P._render_layer_evidence(build(), {"score": 5.0, "phase": "復甦"})
    finally:
        for _n, _f in _orig.items():
            setattr(_P, _n, _f)
    return _out, _actions, _table, _rec


def test_the_action_text_set_is_not_empty():
    """反空轉：五句 `action_text` 真的取得到。

    L2 若哪天讓 `action_text` 全空，A3 會變成「比對一個空清單」而恆綠 ——
    那是本 repo 反覆出事的形態（**工具沒量到它宣稱在量的東西，
    空結果被讀成沒問題**）。這條就是擋那個。
    """
    _texts = _all_verdict_action_texts()
    assert len(_texts) >= 5, (
        f"`composite_verdict()` 只掃到 {len(_texts)} 句 action_text（應 ≥5）—— "
        f"A3 會因此失去比對對象而恆綠：{_texts}")


@pytest.mark.parametrize("name,build", _WORLDS)
def test_precondition_both_worlds_are_evidence_sufficient(name, build):
    """**前提**：這兩個世界真的是「證據充足」，而且 L2 真的給了一句行動句。

    這條紅 → A2／A3 的綠燈一律不算數（它們會退化成只驗「資料不足」那條路，
    而那條路在修好之前就已經是綠的）。

    **實測（2026-09-14，把 `ui/views/page_01_macro.py` 整檔還原成 `origin/main`
    的修前版本，再各跑一次兩個世界）**：

      · 空 indicators（＝預設／斷線世界）→ `sufficient=False`，
        三個下游 builder 收到的 `composite_action` **就是 `""`**
        → 只寫這個世界的守衛會是 **綠的，而違規完整存在**。
      · 全 28 項樂觀 → `sufficient=True`，收到
        `'多頭市場強勁：可滿倉持有，衛星部位積極佈局成長題材'` → **紅，抓到**。

    也就是說「證據充足的世界」不是嚴謹度加分，**它是這組守衛唯一有效的那一半**。
    """
    from services.macro.composite_score import (
        calculate_composite_score, composite_verdict)
    from shared.evidence_support import is_sufficient

    _prov: dict = {}
    _total = calculate_composite_score(build(), provenance_out=_prov)
    assert is_sufficient(_prov.get("support")), (
        f"[{name}] 這個世界不是『證據充足』—— A 組會退化成驗不到東西。"
        f" reason={getattr(_prov.get('support'), 'reason', '')!r}")
    assert str(composite_verdict(_total)[3]).strip(), (
        f"[{name}] L2 在這個世界沒給行動句，本世界無法證明任何事")


@pytest.mark.parametrize("name,build", _WORLDS)
def test_composite_action_is_empty_at_every_downstream_call(name, build):
    """② 依據表的三個下游 builder，收到的 `composite_action` 必須是空字串。

    這是**結構**斷言（逐字相等於 `""`），不是子字串比對 ——
    改寫措辭也一樣紅。

    突變實測（2026-09-14）：把 `ui/views/page_01_macro.py` 的
    `_action = ""` 那一行刪掉 → 本條在**兩個世界都轉紅**
    （bearish 收到「避險情緒高漲：現金 30%+…」、bullish 收到
    「多頭市場強勁：可滿倉持有…」）。
    """
    _out, _actions, _table, _rec = _render_evidence_layer(build)

    assert _out.get("sufficient") is True, (
        f"[{name}] 前提破了：`_render_layer_evidence` 認為證據不足")
    _got = {_n for _n, _ in _actions}
    assert _got == {"build_evidence_rows", "build_evidence_footnotes",
                    "split_evidence_footnotes"}, (
        f"[{name}] 三個下游 builder 沒有全部被呼叫，本條會空轉：{sorted(_got)}")
    _bad = [(_n, _v) for _n, _v in _actions if _v != ""]
    assert not _bad, (
        f"[{name}] 行動句仍然沿著 `composite_action` 送進 ② 依據表：{_bad}")


@pytest.mark.parametrize("name,build", _WORLDS)
def test_no_verdict_action_sentence_reaches_the_evidence_table(name, build):
    """五句 `action_text` 一句都不得出現在 ② 依據表的列／表下註記／頁面文字。

    **正對照同時斷言等級還在** —— 否則「整張表不畫了」也會讓本條變綠，
    而客戶要的是「只留等級與分數」，不是把那一列拿掉。
    """
    _out, _actions, _table, _rec = _render_evidence_layer(build)
    _blob = repr(_table) + "\n" + "\n".join(_rec.texts())

    _hit = [_a for _a in _all_verdict_action_texts() if _a in _blob]
    assert not _hit, f"[{name}] 行動句出現在畫面上：{_hit}"

    # ── 正對照：等級與分數仍然照印（本批只拿掉行動句）────────────────
    assert _out.get("sufficient") is True, f"[{name}] 前提破了"
    _level = str(_out.get("level") or "")
    assert _level, f"[{name}] 等級被一起清掉了 —— 客戶要的是『只留等級與分數』"
    assert _level in repr(_table.get("rows")), (
        f"[{name}] 等級 {_level!r} 沒有出現在 ② 依據表的列裡 —— "
        f"本條可能是因為整張表沒畫才綠的")


def test_the_action_is_cleared_unconditionally_in_source():
    """`_action = ""` 必須在函式**本體最外層**，不得被搬回 `if not _ok:` 裡。

    突變實測（2026-09-14）：把 `_action = ""` 縮排回 `if not _ok:` 區塊內
    → 本條轉紅（同時 A2／A3 在兩個世界也都轉紅）。
    """
    _tree = ast.parse(_PAGE.read_text(encoding="utf-8"))
    _fn = [_n for _n in ast.walk(_tree)
           if isinstance(_n, ast.FunctionDef) and _n.name == "_render_layer_evidence"]
    assert len(_fn) == 1, f"`_render_layer_evidence` 應恰好一個定義，實際 {len(_fn)}"

    _top = [_s for _s in _fn[0].body
            if isinstance(_s, ast.Assign)
            and any(isinstance(_t, ast.Name) and _t.id == "_action"
                    for _t in _s.targets)
            and isinstance(_s.value, ast.Constant) and _s.value.value == ""]
    assert _top, (
        "`_render_layer_evidence` 的函式本體最外層找不到 `_action = \"\"` —— "
        "行動句的清空又變成有條件的了")


# ════════════════════════════════════════════════════════════════
# B 組｜說明書再平衡章節
# ════════════════════════════════════════════════════════════════
def _render_manual() -> _Recorder:
    import ui.tab6_manual as _M
    _rec = _Recorder()
    _orig = _M.st
    try:
        _M.st = _rec
        _M.render_manual_tab()
    finally:
        _M.st = _orig
    return _rec


def _rebalance_block(rec: _Recorder) -> str:
    """再平衡偏離分級表所在的那一段 markdown。"""
    _hit = [_t for _t in rec.texts() if "偏離程度" in _t]
    assert len(_hit) == 1, (
        f"預期恰好一段 markdown 含「偏離程度」，實際 {len(_hit)} 段 —— "
        f"本節若被搬走／複製，下面的欄數鎖會守錯對象")
    return _hit[0]


def test_the_rebalance_chapter_title_has_no_one_click():
    """章節名與目錄短標不得再出現 `One-Click` / 「一鍵」（母法 G1）。

    突變實測（2026-09-14）：把標題改回
    `"⚖️ 再平衡公式（One-Click Rebalance）"` → 轉紅。
    """
    from ui.tab6_manual import _CHAPTERS

    _by_key = {_k: (_toc, _title) for _k, _toc, _title in _CHAPTERS}
    assert "rebalance" in _by_key, (
        "再平衡章節不見了 —— 本批只拿掉行動指引，不是拿掉整章")

    for _label, _s in zip(("目錄短標", "章節標題"), _by_key["rebalance"]):
        assert "one-click" not in _s.lower(), f"{_label} 又掛回 One-Click：{_s!r}"
        assert "一鍵" not in _s, f"{_label} 又掛回「一鍵」：{_s!r}"


def test_the_rebalance_band_table_has_no_action_column():
    """偏離分級表只准剩**一欄**（欄數鎖，與那一欄寫什麼字無關）。

    這是本組唯一**不靠字串清單**的斷言：有人把「動作」欄加回來，
    不論那欄叫「動作」「處置」「建議」還是留白，欄數都會變成 2 → 轉紅。

    正對照：5% / 10% 兩條分級線仍在（客戶明示那是客觀分級，可以留）——
    否則「把整張表刪掉」也會讓本條變綠。

    突變實測（2026-09-14）：把「動作」欄整欄加回去 → 轉紅
    （`ncells=2`）。
    """
    _block = _rebalance_block(_render_manual())
    _rows = [_l.strip() for _l in _block.splitlines() if _l.strip().startswith("|")]
    assert len(_rows) >= 4, f"再平衡分級表的列數不足，實際 {len(_rows)} 列：{_rows}"

    _wide = [(_r, len(_r.strip("|").split("|"))) for _r in _rows]
    _bad = [(_r, _n) for _r, _n in _wide if _n != 1]
    assert not _bad, f"偏離分級表又長出第二欄（動作欄）：{_bad}"

    for _band in ("5%", "10%"):
        assert _band in _block, (
            f"分級線 {_band} 不見了 —— 本批只拿掉「動作」欄，分級數字要留")


def test_the_manual_names_no_fund_to_buy_or_sell():
    """被移除的那幾句**指名買賣**的字串，不得回到說明書任何一章（母法 G3）。

    ⚠️ **這是字串清單，不是語意檢查** —— 見模組 docstring「守不到什麼」。
    它擋的是「原文被還原」，擋不住「換句話說重寫一遍」。

    突變實測（2026-09-14）：把「白話文行動指南」整段還原 → 轉紅
    （命中「白話文行動指南」「贖回」「獲利了結」）；
    只還原偏離表的動作欄 → 命中「建議再平衡」「必須執行再平衡」。
    """
    _texts = "\n".join(_render_manual().texts())

    _forbidden = (
        "白話文行動指南",          # 章節小標本身就是「行動指南」
        "建議再平衡",              # 偏離表動作欄
        "必須執行再平衡",          # 偏離表動作欄
        "必須執行",                # 核心衛星章末那一句
        "贖回",                    # 「從最大衛星基金贖回 ΔNT$」
        "獲利了結",                # 「從最大核心基金獲利了結 ΔNT$」
        "轉入「最小核心基金」",
        "轉入「最小衛星基金」",
    )
    _hit = [_f for _f in _forbidden if _f in _texts]
    assert not _hit, f"說明書又出現指名買賣的行動指引：{_hit}"


def test_the_rebalance_chapter_is_still_there():
    """正對照：上面三條**不是**靠「整章被刪掉」才綠的。

    再平衡章節本體（差額公式與分級表）是客觀計算說明，客戶沒有要求移除。
    """
    _texts = "\n".join(_render_manual().texts())
    for _keep in ("再平衡公式", "偏離程度", "Action_i"):
        assert _keep in _texts, f"再平衡章節的 {_keep!r} 不見了 —— 這一批不該刪掉整章"


# ════════════════════════════════════════════════════════════════
# C 組｜① 結論改講「現在是什麼狀態」（客戶 2026-09-14 第二次拍板）
# ════════════════════════════════════════════════════════════════
# `services/macro/action_light.py::macro_action_light()` 的 `action` 是買賣指令，
# 由 `ui/views/page_01_macro.py::_render_layer_conclusion` 渲染在 ① 結論。
# 本組守「行動句不上畫面、改印狀態句」。
#
# ⚠️ **`light` 只有 3 個值，行動路徑有 5 條** —— 五條各自站在不同的世界裡。
#    比照 A 組，本組**每一條都真的站進去過**，並先用 C1 把「我真的走到這條路徑」
#    斷言出來；C1 紅 → 同組其餘綠燈一律不算數。
#
# ⚠️ **「資料不足」那一條的正確行為是「被閘門擋下」，不是「給它一句狀態」** ——
#    把它講成 🟡「中性」就是把 ⬜ 說成 🟡（違 §1）。C4 逐字釘住這件事。

# 客戶逐字拍板的兩句（**字面值錨**，刻意不從產品碼 import）——
# 其餘各鎖都從產品碼推導期望值，代價是「全部同源 ＝ 一起漂移」；
# 客戶拍板過的文案必須有一根不動的樁。
_CLIENT_APPROVED_HEADING = "### 🧾 ① 結論 — 現在的景氣位階"
_CLIENT_APPROVED_GREEN_STATE = "偏強 —— 擴張訊號明顯多於收縮訊號"


def _full_indicators(**override) -> dict:
    """28 項全取到的 indicators（否則 `_phase_support` 不足，🟢/🟡 根本走不到）。

    ⚠️ 這一點是實測換來的：只給 4 個 override key 的稀疏世界，
    🟢/🟡 兩條路的 `support` **都不充足**，會被閘門擋下 ——
    在那種世界裡寫守衛，會誤以為「🟢 從來不上畫面」。
    """
    from services.macro.evidence import MACRO_INDICATOR_SCORING_WEIGHTS as _W
    _d = {_k: {"value": 1.0, "weight": _w, "score": 1.0} for _k, _w in _W.items()}
    for _k, _v in (("YIELD_10Y2Y", 0.8), ("YIELD_10Y3M", 0.6),
                   ("VIX", 15.0), ("SAHM", 0.1)):
        _d.setdefault(_k, {"weight": _W.get(_k, 1.0), "score": 1.0})
        _d[_k]["value"] = _v
    for _k, _v in override.items():
        _d.setdefault(_k, {"weight": _W.get(_k, 1.0), "score": 1.0})
        _d[_k]["value"] = _v
    return _d


# (名稱, indicators, phase_score, 預期 light, 預期 override, 預期 support 充足)
_LIGHT_WORLDS = (
    ("P1-override-red",   dict(VIX=45.0), 5.0,  "🔴", True,  True),
    ("P2-no-phase-score", {},             None, "🟡", False, False),
    ("P3-phase-green",    {},             9.0,  "🟢", False, True),
    ("P4-phase-amber",    {},             4.0,  "🟡", False, True),
    ("P5-phase-red",      {},             1.0,  "🔴", False, True),
)


def _all_action_light_texts() -> tuple[str, ...]:
    """五句 `action` **從 L2 現場取回**，本檔不抄第二份（§2.1 SSOT）。"""
    from services.macro.action_light import macro_action_light
    _seen: dict[str, None] = {}
    for _n, _ov, _ps, *_ in _LIGHT_WORLDS:
        _a = macro_action_light(_full_indicators(**_ov), _ps).get("action")
        if str(_a or "").strip():
            _seen[str(_a)] = None
    return tuple(_seen)


def _render_conclusion(override: dict, phase_score):
    """跑 `_render_layer_conclusion`，錄下畫面、`not_ready`、`business_alert`。"""
    import ui.views.page_01_macro as _P

    _rec = _Recorder()
    _nr: list = []
    _ba: list = []
    _orig = (_P.st, _P.not_ready, _P.business_alert)
    try:
        _P.st = _rec
        _P.not_ready = lambda *a, **k: _nr.append((a, k))
        _P.business_alert = lambda *a, **k: _ba.append((a, k))
        _P._render_layer_conclusion(_full_indicators(**override),
                                    {"score": phase_score})
    finally:
        _P.st, _P.not_ready, _P.business_alert = _orig
    _blob = "\n".join(_rec.texts() + [str(_x) for a, k in _nr for _x in a]
                      + [str(_x) for a, k in _ba for _x in a])
    return _rec, _nr, _ba, _blob


def test_the_action_light_text_set_is_not_empty():
    """反空轉：五句 `action` 真的取得到（否則 C2 會比對空清單而恆綠）。"""
    _t = _all_action_light_texts()
    assert len(_t) >= 5, f"只掃到 {len(_t)} 句 action（應 ≥5）：{_t}"


@pytest.mark.parametrize("name,ov,ps,light,override,ok", _LIGHT_WORLDS)
def test_precondition_each_action_light_path_is_really_reached(
        name, ov, ps, light, override, ok):
    """**前提**：這五個世界真的分別走到那五條路徑上。

    這條紅 → C2／C3／C4 的綠燈一律不算數（它們可能全擠在同一條路徑上）。
    """
    from services.macro.action_light import macro_action_light
    from shared.evidence_support import is_sufficient

    _r = macro_action_light(_full_indicators(**ov), ps)
    assert _r.get("light") == light, f"[{name}] light={_r.get('light')!r}，預期 {light!r}"
    assert bool(_r.get("override")) is override, f"[{name}] override 不符"
    assert is_sufficient(_r.get("support")) is ok, (
        f"[{name}] support 充足性={is_sufficient(_r.get('support'))}，預期 {ok} —— "
        f"reason={getattr(_r.get('support'), 'reason', '')!r}")
    assert str(_r.get("action") or "").strip(), f"[{name}] L2 沒給行動句，本世界證不了事"


@pytest.mark.parametrize("name,ov,ps,light,override,ok", _LIGHT_WORLDS)
def test_no_action_light_sentence_reaches_the_conclusion(
        name, ov, ps, light, override, ok):
    """五條路徑**每一條**都不得把 `action` 那句買賣指令畫上畫面。

    突變實測（2026-09-14）：把 `_conclusion_state(_light)` 改回
    `_light.get('action', '')` → 本條在**四條會上畫面的路徑上全部轉紅**。
    """
    _rec, _nr, _ba, _blob = _render_conclusion(ov, ps)
    _hit = [_a for _a in _all_action_light_texts() if _a in _blob]
    assert not _hit, f"[{name}] 行動句出現在 ① 結論：{_hit}"


@pytest.mark.parametrize("name,ov,ps,light,override,ok",
                         [_w for _w in _LIGHT_WORLDS if _w[5]])
def test_each_rendering_path_shows_a_state_sentence_and_keeps_its_light(
        name, ov, ps, light, override, ok):
    """會上畫面的四條路徑：**燈號仍在**、**理由條列仍在**、且印的是狀態句。

    正對照不可省 —— 否則「整塊不畫了」也會讓 C2 變綠。
    """
    from ui.views.page_01_macro import (
        _CONCLUSION_STATE_BY_LIGHT, _CONCLUSION_STATE_OVERRIDE)

    _rec, _nr, _ba, _blob = _render_conclusion(ov, ps)
    assert not _nr, f"[{name}] 這條路徑不該被 not_ready 擋下"
    assert light in _blob, f"[{name}] 燈號 {light} 不在畫面上"

    _want = _CONCLUSION_STATE_OVERRIDE if override else _CONCLUSION_STATE_BY_LIGHT[light]
    assert _want in _blob, f"[{name}] 狀態句 {_want!r} 沒出現在畫面上"

    # 理由條列仍在（客戶裁決：燈號保留、理由條列保留）
    from services.macro.action_light import macro_action_light
    _reasons = macro_action_light(_full_indicators(**ov), ps).get("reasons") or []
    assert _reasons, f"[{name}] 前提：這條路徑本來就該有理由"
    assert any(str(_r)[:12] in _blob for _r in _reasons), (
        f"[{name}] 理由條列不見了 —— 本批只換掉行動句，理由要留")


def test_the_override_red_is_not_described_as_a_weak_phase():
    """override 🔴 **不得**與位階 🔴 共用「偏弱」那句 —— 那對 override 是假話。

    override 的紅來自**硬衰退／恐慌訊號真的觸發**（本世界：VIX 45 ≥ 30），
    而位階是 5.0（中性）。說它「收縮訊號明顯多於擴張訊號」與事實不符。

    突變實測（2026-09-14）：把 `_conclusion_state()` 的 `override` 分支拿掉
    （只依 `light` 對映）→ 本條轉紅。
    """
    from ui.views.page_01_macro import _CONCLUSION_STATE_BY_LIGHT

    _rec, _nr, _ba, _blob = _render_conclusion({"VIX": 45.0}, 5.0)
    assert _CONCLUSION_STATE_BY_LIGHT["🔴"] not in _blob, (
        "override 🔴 被說成『位階偏弱』—— 位階其實是 5.0（中性）")
    assert "警戒" in _blob, "override 🔴 沒有自己的狀態句"


def test_the_no_phase_score_path_makes_no_state_claim_at_all():
    """「資料不足」那條路必須**被閘門擋下**，且畫面上不得出現任何狀態判定。

    ⛔ 把它講成 🟡「中性」＝ 把 ⬜ 說成 🟡（違 §1）。

    突變實測（2026-09-14）：拿掉 `_render_layer_conclusion` 的
    `if not is_sufficient(_support): ... return` 閘門 → 本條轉紅
    （畫面會冒出「中性 —— 擴張與收縮訊號互見」）。
    """
    from ui.views.page_01_macro import (
        _CONCLUSION_STATE_BY_LIGHT, _CONCLUSION_STATE_OVERRIDE)

    _rec, _nr, _ba, _blob = _render_conclusion({}, None)
    assert _nr, "「資料不足」沒有被 not_ready 擋下"
    _claims = list(_CONCLUSION_STATE_BY_LIGHT.values()) + [_CONCLUSION_STATE_OVERRIDE]
    _hit = [_c for _c in _claims if _c in _blob]
    assert not _hit, f"資料不足卻下了狀態判定：{_hit}"


def test_the_client_approved_wording_is_rendered_verbatim():
    """**字面值錨**：客戶逐字拍板的標題與 🟢 那句，必須原樣出現在畫面上。

    其餘各鎖都從產品碼推導期望值（不抄第二份），代價是**全部同源、會一起漂移**；
    客戶拍板過的文案因此需要一根不動的樁。
    """
    _rec, _nr, _ba, _blob = _render_conclusion({}, 9.0)
    assert _CLIENT_APPROVED_HEADING in _blob, (
        f"標題與客戶拍板的草稿不符，應為 {_CLIENT_APPROVED_HEADING!r}")
    assert _CLIENT_APPROVED_GREEN_STATE in _blob, (
        f"🟢 那句與客戶拍板的草稿不符，應為 {_CLIENT_APPROVED_GREEN_STATE!r}")


def test_the_conclusion_never_reads_the_action_field():
    """結構鎖：① 結論的原始碼**不得再出現 `action` 這個欄位**。

    擋兩種復辟：(a) 直接把 `action` 印回去；(b) 去剖 `action` 字串產生狀態句
    —— 後者會在 L2 改用詞時**靜默**壞掉（剖出來的還是一句看起來正常的話）。
    """
    _tree = ast.parse(_PAGE.read_text(encoding="utf-8"))
    _fns = [_n for _n in ast.walk(_tree)
            if isinstance(_n, ast.FunctionDef)
            and _n.name in ("_render_layer_conclusion", "_conclusion_state")]
    assert len(_fns) == 2, f"預期兩個函式定義，實際 {len(_fns)}"

    _bad = [f"{_fn.name}:{_c.lineno}" for _fn in _fns for _c in ast.walk(_fn)
            if isinstance(_c, ast.Constant) and _c.value == "action"]
    assert not _bad, f"① 結論又去讀 `action` 欄位了：{_bad}"
