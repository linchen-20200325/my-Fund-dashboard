"""雙軌並行：新舊 ⑤ 同一次 run 撞不撞 Streamlit 重複 widget key？

本檔回答兩個問題，兩個都要**真的跑過 `app.py`** 才算數：

1. **預設狀態**：七格全開、使用者什麼都還沒勾 —— 畫面上不可以有任何 `st.error`。
   ⚠️ 這一條是本 repo 先前**結構上缺掉**的斷言。`app.py` 每一格
   `with tab_*:` 都包了 `try/except` → `friendly_error(level="error")` → `st.error`，
   而 `ui/helpers/render_state.py::safe_section` → `system_error()` 也走同一個出口。
   也就是說**分頁炸掉會被吃成一個紅框，不會變成未捕捉例外** ——
   既有的 `tests/test_app_apptest.py::test_app_runs_without_exception`
   只驗 `at.exception`，對紅框**結構上看不見**：⑦ 整格紅掉它照樣綠。

2. **使用者把閘門勾起來之後**：`ui/views/page_05_settings.py` 用 Checkbox Gate
   把維護區擋在 `if` 後面，但舊 ⑤（`ui/tab_settings_diag.py::_render_maintain_section`）
   是**無條件**呼叫同一支 `render_manage_tab()` 的。
   → 閘門只擋「預設載入就雙跑」，**使用者一勾就變成同一次 run 跑兩份**。
   而預覽分頁存在的意義就是要人去勾。

⛔ **本檔不修任何東西**，只把事實釘成可重跑的證據。
   修法（改舊 Tab 的 key／讓舊 ⑤ 在預覽開啟時跳過）會動到客戶明令
   「絕對禁止直接覆寫、修改或破壞現有線上正常運作的舊版 Tab 代碼」的檔案，
   屬**送客戶裁決的判斷題**，不是實作題。

**刻意不加 `slow` 標記**：本 repo 只有 fast lane 會擋 merge
（`.github/workflows/pr-check.yml` 的 slow lane 是 `continue-on-error: true`，
informational）。把「預設載入不可有紅框」放進 informational lane
等於這條斷言不會擋任何東西。代價是 fast lane 多跑幾次整頁 AppTest。
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

import pytest

streamlit_testing = pytest.importorskip(
    "streamlit.testing.v1", reason="streamlit < 1.28 不支援 AppTest")
AppTest = streamlit_testing.AppTest

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_PY = REPO_ROOT / "app.py"

#: 新 ⑤「🗄️ 資料維護與通報」閘門的標籤。
#: ⚠️ 這裡**刻意手抄**而不 import `ui.views.page_05_settings.MAINTAIN_GATE_LABEL`：
#:    本檔要驗的正是「畫面上真的有這顆、而且勾了會怎樣」。
#:    從被測模組 import 標籤，會讓標籤改掉時測試跟著改、跟著綠 —— 那是自證。
#:    下方 `test_the_gate_labels_this_file_hardcodes_are_really_on_screen`
#:    專門守這份手抄不漂移。
MAINTAIN_GATE_LABEL = "🗄️ 載入資料維護與通報"
BACKFILL_GATE_LABEL = "🗄️ 載入手動補資料"


# ════════════════════════════════════════════════════════════════
# 共用：跑一次 app.py
# ════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module", autouse=True)
def _hermetic():
    """AppTest 只驗 UI 渲染，不外連（沿用 `tests/test_app_apptest.py` 的既有做法）。

    - 外連一律指向 discard port → 秒收 ECONNREFUSED，走既有降級路徑；
    - tab1 的「>30 天自動補抓」在 AppTest 全程停用（每建一個 instance 都會觸發一次）。
    """
    mp = pytest.MonkeyPatch()
    for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        mp.setenv(_pv, "http://127.0.0.1:9")
    mp.delenv("NO_PROXY", raising=False)
    mp.delenv("no_proxy", raising=False)
    import ui.hot_money as _hm
    _orig = _hm.refresh_hot_money_data
    _hm.refresh_hot_money_data = lambda *a, **k: (False, "skipped in AppTest")
    yield
    _hm.refresh_hot_money_data = _orig
    mp.undo()


def _boot(script_path: str) -> Any:
    at = AppTest.from_file(script_path, default_timeout=180)
    at.secrets["FRED_API_KEY"] = "test-fred-key"
    at.secrets["GEMINI_API_KEY"] = "test-gemini-key"
    at.run()
    return at


def _errors(at: Any) -> list[str]:
    """畫面上所有紅框的文字。

    ⚠️ 這是本檔的**唯一**判定函式 —— 正常斷言與突變驗證共用它。
    兩邊各寫一份的話，突變驗證就不再證明正常斷言會轉紅。
    """
    return [str(e.value) for e in at.error]


@pytest.fixture(scope="module")
def at_default(_hermetic) -> Any:
    """預設狀態：七格全渲染，使用者什麼都沒勾。"""
    return _boot(str(APP_PY))


# ════════════════════════════════════════════════════════════════
# (1) 預設狀態 —— 缺掉的那條斷言
# ════════════════════════════════════════════════════════════════
def test_app_default_load_has_no_visible_error(at_default: Any) -> None:
    """跑完 `app.py` 之後，畫面上不可以有任何 `st.error`。

    這條與 `test_app_runs_without_exception` **不重疊**：後者驗的是
    「有沒有例外逃到最外層」，本條驗的是「有沒有例外**被吃成紅框**」。
    七格各自的 `try/except` 讓後者恆綠，紅框只有本條看得見。
    """
    _errs = _errors(at_default)
    assert not _errs, (
        f"預設載入就出現 {len(_errs)} 個紅框（使用者一打開就會看到）：\n"
        + "\n".join(f"  [{i}] {e[:400]}" for i, e in enumerate(_errs)))


def test_app_default_load_has_no_uncaught_exception(at_default: Any) -> None:
    """對照組：確認本檔的 harness 與既有 slow lane 那條看到的是同一個 app。"""
    assert not at_default.exception, \
        f"app.py 未捕捉例外：{[str(e) for e in at_default.exception]}"


def test_the_gate_labels_this_file_hardcodes_are_really_on_screen(
        at_default: Any) -> None:
    """本檔手抄的兩個閘門標籤，必須真的出現在畫面上。

    ⚠️ 沒有這一條，上面那些「勾起來會怎樣」的測試會在標籤改名之後
    **靜默地什麼都沒勾到**，然後回報綠 —— 守衛失去對象，不是守衛通過。
    """
    _labels = [c.label for c in at_default.checkbox]
    assert _labels, "畫面上一個 checkbox 都沒有 —— harness 壞了，不是 app 乾淨"
    for _want in (MAINTAIN_GATE_LABEL, BACKFILL_GATE_LABEL):
        assert _want in _labels, (
            f"手抄的閘門標籤 {_want!r} 不在畫面上；現有標籤：{_labels}")


# ════════════════════════════════════════════════════════════════
# (1b) 突變驗證 —— 上面那條斷言真的抓得到東西嗎？
# ════════════════════════════════════════════════════════════════
#: 突變錨點：⑥ 的呼叫點。**含縮排**，全檔唯一（同名字串另有一處 import 行，
#: 不含這段縮排 → `str.replace` 不會誤中）。
_MUT_ANCHOR = "            render_holdings_health()"
#: 換成一個**語法合法**、執行期必炸的運算式。
#: ⛔ 不整行刪除 —— 那會造成 `SyntaxError`（當機紅），不是守衛紅，不算數。
_MUT_REPLACEMENT = "            [][1]"


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_the_no_error_guard_actually_catches_a_broken_tab(
        tmp_path: Path, _hermetic) -> None:
    """突變驗證：讓 ⑥ 拋例外 → `_errors()` 必須非空（＝上面那條會轉紅）。

    做法與硬性要求
    --------------
    - 用 `str.replace` 換一段**含縮排的唯一字串**；
      ⛔ 不用 `ast.col_offset` 切字串 —— 那是 **UTF-8 位元組**位移，
        本檔（與 `app.py`）滿是中文，用字元索引切會讓突變**根本沒套上**卻回報綠。
    - 突變體先 `ast.parse` 過一次：語法錯是**當機紅**，不是守衛紅，不計。
    - 斷言突變體位元組**真的**與原檔不同（換句話說：替換真的發生了）。
    - 全程不動 `app.py` —— 前後 sha256 逐位元組比對。
    """
    _before = _sha256(APP_PY)
    _src = APP_PY.read_text(encoding="utf-8")

    # ── 錨點唯一性（沒有這一步，replace 可能一次也沒套上，或套錯地方）
    assert _src.count(_MUT_ANCHOR) == 1, (
        f"突變錨點在 app.py 出現 {_src.count(_MUT_ANCHOR)} 次，"
        "不是 1 —— 錨點已漂移，請更新本測試而不是放寬它")

    _mutated = _src.replace(_MUT_ANCHOR, _MUT_REPLACEMENT)
    assert _mutated.encode("utf-8") != _src.encode("utf-8"), \
        "突變後位元組與原檔相同 —— 替換沒套上，這一輪不算驗過"
    assert _MUT_ANCHOR not in _mutated, "錨點仍在突變體裡 —— 替換不完整"
    ast.parse(_mutated)  # 語法合法才算突變體，不合法是當機

    # `AppTest.from_file` 會把「腳本所在目錄」加進 sys.path。突變體放 tmp_path，
    # 所以自己補一行把 repo 根加回去（同 `tests/test_wf05_settings_skeleton.py` 的做法）。
    _boot_line = f"import sys as _s; _s.path.insert(0, {str(REPO_ROOT)!r})\n"
    _mutant = tmp_path / "mutant_app.py"
    _mutant.write_text(_boot_line + _mutated, encoding="utf-8")

    _at = _boot(str(_mutant))
    _errs = _errors(_at)

    assert _errs, (
        "突變體（⑥ 必炸）跑完之後 `_errors()` 是空的 —— "
        "代表 `test_app_default_load_has_no_visible_error` **抓不到壞掉的分頁**，"
        "那條斷言是假的守衛。")
    assert any("IndexError" in e or "list index out of range" in e
               for e in _errs), (
        "有紅框，但沒有一個看得出是本次注入的 IndexError；"
        f"實際紅框：{[e[:200] for e in _errs]}")

    # ── 還原確認：本測試不得碰 app.py 一個位元組
    assert _sha256(APP_PY) == _before, "本測試污染了 app.py"


# ════════════════════════════════════════════════════════════════
# (2) 把閘門真的勾起來
# ════════════════════════════════════════════════════════════════
def _tick(at: Any, label: str) -> Any:
    """依**標籤**勾起一個 checkbox 並重跑。

    ⛔ 不用 `at.checkbox[i]` —— 索引會隨畫面漂移，勾錯一顆而測試照樣綠。
    """
    for _c in at.checkbox:
        if _c.label == label:
            _c.check()
            at.run()
            return at
    raise AssertionError(
        f"畫面上找不到標籤為 {label!r} 的 checkbox；"
        f"現有：{[c.label for c in at.checkbox]}")


@pytest.fixture(scope="module")
def at_maintain_on(_hermetic) -> Any:
    """勾起 `[新] ⑦` 的「🗄️ 載入資料維護與通報」之後的畫面。

    此時**舊 ⑤ 與新 ⑤ 在同一次 run 內都會跑 `render_manage_tab()`** ——
    舊 ⑤ 是無條件的，新 ⑤ 是因為使用者剛剛把閘門勾開。
    """
    return _tick(_boot(str(APP_PY)), MAINTAIN_GATE_LABEL)


def _dump(at: Any, what: str) -> str:
    _errs = _errors(at)
    _lines = [f"=== {what} ===",
              f"exceptions : {len(at.exception)}",
              *[f"   EXC {str(e)[:500]}" for e in at.exception],
              f"st.error   : {len(_errs)}",
              *[f"   ERR[{i}] {e[:900]}" for i, e in enumerate(_errs)],
              f"checkboxes : {len(at.checkbox)}",
              f"labels     : {[c.label for c in at.checkbox]}"]
    return "\n".join(_lines)


def test_EXPLORE_what_happens_when_the_maintenance_gate_is_ticked(
        at_maintain_on: Any, at_default: Any) -> None:
    """⚠️ 探測用，**故意失敗**以便從 CI log 讀出真實行為（本機無 streamlit 跑不動）。

    這一條在拿到 CI 的真實輸出之後會被換成正式斷言。
    """
    pytest.fail("EXPLORATION DUMP (deliberate failure, phase 1)\n"
                + _dump(at_default, "DEFAULT (nothing ticked)")
                + "\n"
                + _dump(at_maintain_on, "AFTER ticking " + MAINTAIN_GATE_LABEL))
