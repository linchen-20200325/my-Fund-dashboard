"""雙軌並行：新舊 ⑤ 同一次 run 撞不撞 Streamlit 重複 widget key？

⚠️ **本檔的每一條斷言都是「跑過真的 `app.py` 之後量出來的」，不是推論。**
   本機沒有 streamlit（環境規則禁止 `pip install`），所有數字與訊息**逐字出自 CI**
   —— run 34147466074（`abecc1c`）的 fast lane 輸出。**不是本機跑的，也不假裝是。**

背景
----
#814 雙軌並行之後 `app.py` 七格。`st.tabs` **一次 run 會把所有分頁的 body 全部執行過**，
所以「⑦ 沒被點開」**不代表它沒渲染**。⑤ 與 ⑦ 委派同一批舊模組：

===========================  ==================  ====================  ==============
共用的委派                    舊 ⑤                 新 ⑦                  幾次點擊才撞
===========================  ==================  ====================  ==============
``render_manual_tab``        無條件               無條件                 **0**
``render_manage_tab``        無條件               MAINTAIN gate 之後      **1**
``render_nav_manual_section``無條件               BACKFILL gate 之後      **1**
``render_data_guard_tab``    gate 之後            gate 之後              2（未涵蓋）
===========================  ==================  ====================  ==============

**閘門沒有解決衝突，只是把它推遲到使用者去勾為止** —— 而預覽分頁存在的意義就是要人去勾。
更要緊的是第一列：**那一列一次都不必勾。**

⛔ **本檔不修任何東西**，只把事實釘成可重跑的證據。修法（改舊 Tab 的 key／
   讓舊 ⑤ 在預覽開啟時跳過）會動到客戶明令「絕對禁止直接覆寫、修改或破壞現有線上
   正常運作的舊版 Tab 代碼」的檔案，**屬送客戶裁決的判斷題，不是實作題**。

**刻意不加 `slow` 標記**：本 repo 只有 fast lane 會擋 merge
（`.github/workflows/pr-check.yml` 的 slow lane 是 `continue-on-error: true`，
informational）。把這些斷言放進 informational lane 等於它們不會擋任何東西。
實測代價：加進 fast lane 後整批 pytest 344.62s（8039 項），可接受。
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

#: 新 ⑦ 兩顆 gate 的標籤。
#: ⚠️ **刻意手抄**而不 import `ui.views.page_05_settings` 的常數：本檔要驗的正是
#:    「畫面上真的有這顆、勾了會怎樣」。從被測模組 import 標籤，會讓標籤改掉時
#:    測試跟著改、跟著綠 —— 那是自證。下方
#:    `test_the_gate_labels_this_file_hardcodes_are_really_on_screen` 守這份手抄不漂移。
MAINTAIN_GATE_LABEL = "🗄️ 載入資料維護與通報"
BACKFILL_GATE_LABEL = "🗄️ 載入手動補資料"


# ════════════════════════════════════════════════════════════════
# 共用 harness
# ════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module", autouse=True)
def _hermetic():
    """AppTest 只驗 UI 渲染，不外連（沿用 `tests/test_app_apptest.py` 的既有做法）。"""
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
    at = AppTest.from_file(script_path, default_timeout=60)
    at.secrets["FRED_API_KEY"] = "test-fred-key"
    at.secrets["GEMINI_API_KEY"] = "test-gemini-key"
    at.run()
    return at


def _texts(elements) -> list[str]:
    """沿用 `tests/test_app_apptest.py` 的既有取值法（`.value` 可能不存在）。"""
    return [str(getattr(e, "value", e) or "") for e in elements]


def _errors(at: Any) -> list[str]:
    """畫面上所有**紅框**。

    ⚠️ 這是本檔的**唯一**紅框判定函式 —— 正常斷言與突變驗證共用它。
    兩邊各寫一份的話，突變驗證就不再證明正常斷言會轉紅。
    """
    return _texts(at.error)


def _warnings(at: Any) -> list[str]:
    """畫面上所有**黃框**。

    ⚠️ **這個函式非有不可**：`ui/tab_manage.py::_sec_pool`（L84-88）用它自己的
    `try/except` → `_friendly(...)`（**預設 `level="warning"`**）把例外接住，
    也就是說**選股池那一份重複 key 被降級成一個黃框** —— `at.error` 結構上看不見它。
    只驗紅框會漏掉這一半（CI 實測：`pool_add_form` 就是這樣被藏起來的）。
    """
    return _texts(at.warning)


def _hits(texts: list[str], fingerprint: tuple[str, ...]) -> list[str]:
    """`fingerprint` 的每一段都出現在同一則訊息裡才算命中。

    ⚠️ 用**多段 substring** 而不是逐字全文比對：全文含 traceback 與會漂移的提示語，
    釘死它等於每次改文案都紅一次（本 repo 明令「不釘文案」）。
    但**只釘一段**又會誤命中 —— 例如「手動補資料」這四個字在正常畫面上本來就有。
    """
    return [t for t in texts if all(seg in t for seg in fingerprint)]


# ════════════════════════════════════════════════════════════════
# (1) 預設狀態 —— 缺掉的那條斷言
# ════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def at_default(_hermetic) -> Any:
    """預設狀態：七格全渲染，使用者**一次都沒有點**。"""
    return _boot(str(APP_PY))


def test_app_default_load_has_no_visible_error(at_default: Any) -> None:
    """跑完 `app.py` 之後，畫面上不可以有任何 `st.error`。

    ⚠️ **這一條目前是紅的，而且紅得對** —— 它抓到的是 `origin/main`（`c6b4d1b`）
    上**已經存在**的一個紅框（三點 diff 實證：本分支只新增 `tests/` 一個檔，
    被測的 `app.py` / `ui/**` 與 `origin/main` 逐位元組相同）。
    ⛔ **不得**為了讓 CI 轉綠而放寬、加白名單或 skip 本條 ——
       那會把一個**使用者今天打開就看得到**的紅框重新藏起來。

    根因（AST 實測，非推論）
    ------------------------
    `render_manual_tab()` 在同一次 run 內被畫**兩次**：
    舊 ⑤ `ui/tab_settings_diag.py::_render_manual_section` 與
    新 ⑦ `ui/views/page_05_settings.py::_render_manual` —— **兩邊都沒有 gate**
    （兩個函式體內 `st.checkbox` 0 個、`If` 0 個）。
    而 `ui/tab6_manual.py:679` 復用 `ui/tab1_macro.py::render_indicator_map`
    畫的 `plotly_chart` **不帶 key** → 自動產生的 element ID 撞在一起。
    （`render_indicator_map` 全 repo 只有那**一個** call site，AST 非 grep。）
    → **這一條一次都不必勾**，與下面兩條「勾了才撞」的性質不同。

    為什麼先前沒有人看得見
    ----------------------
    `app.py` 七格各自的 `try/except` → `friendly_error(level="error")` → `st.error`；
    `ui/helpers/render_state.py::safe_section` → `system_error()` 走同一個出口
    —— 兩條路都讓 `at.exception` 保持是空的。既有的
    `tests/test_app_apptest.py::test_app_runs_without_exception` 只驗 `at.exception`，
    對紅框**結構上看不見**。
    ⚠️ 既有的 `test_app_apptest.py:594` 確實碰過 `app.error`，但那是**針對內容**的檢查
    （「不可以有紅字說 `FRED_API_KEY` 未設定」）且情境不同（空金鑰），
    **不是**「畫面上不准有紅框」。本條之前沒有人在守。
    """
    _errs = _errors(at_default)
    assert not _errs, (
        f"預設載入就出現 {len(_errs)} 個紅框（使用者一打開、什麼都還沒點就會看到）：\n"
        + "\n".join(f"  [{i}] {e[:500]}" for i, e in enumerate(_errs)))


def test_app_default_load_has_no_uncaught_exception(at_default: Any) -> None:
    """對照組：證明本檔的 harness 與既有 slow lane 那條看到的是同一個 app。

    ⚠️ 這一條**恆綠**，正是問題所在 —— 上面那個紅框對它完全不可見。
    """
    assert not at_default.exception, \
        f"app.py 未捕捉例外：{[str(e) for e in at_default.exception]}"


def test_the_gate_labels_this_file_hardcodes_are_really_on_screen(
        at_default: Any) -> None:
    """本檔手抄的兩個閘門標籤，必須真的出現在畫面上。

    ⚠️ 沒有這一條，下面那些「勾起來會怎樣」的測試會在標籤改名之後
    **靜默地什麼都沒勾到**然後回報綠 —— 那是**守衛失去對象**，不是守衛通過。
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
#: ⛔ 不整行刪除 —— 那會造成 `SyntaxError`（**當機紅**），不是**守衛紅**，不算數。
_MUT_REPLACEMENT = "            [][1]"


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_the_error_guard_actually_catches_a_broken_tab(
        tmp_path: Path, _hermetic) -> None:
    """突變驗證：讓 ⑥ 拋例外 → `_errors()` 必須看得到它。

    硬性要求逐條落地
    ----------------
    - 用 `str.replace` 換一段**含縮排的唯一字串**；
      ⛔ 不用 `ast.col_offset` 切字串 —— 那是 **UTF-8 位元組**位移，
        本檔與 `app.py` 滿是中文，用字元索引切會讓突變**根本沒套上卻回報綠**。
    - 錨點唯一性先斷言（`count == 1`），否則 replace 可能一次也沒套上。
    - 突變體先 `ast.parse` 過一次（語法錯 ＝ 當機紅，不計）。
    - 斷言突變體**位元組真的變了**。
    - `app.py` 前後 sha256 逐位元組比對 —— 本測試不得碰 production 檔。
    """
    _before = _sha256(APP_PY)
    _src = APP_PY.read_text(encoding="utf-8")

    assert _src.count(_MUT_ANCHOR) == 1, (
        f"突變錨點在 app.py 出現 {_src.count(_MUT_ANCHOR)} 次，不是 1 —— "
        "錨點已漂移，請更新本測試而不是放寬它")

    _mutated = _src.replace(_MUT_ANCHOR, _MUT_REPLACEMENT)
    assert _mutated.encode("utf-8") != _src.encode("utf-8"), \
        "突變後位元組與原檔相同 —— 替換沒套上，這一輪不算驗過"
    assert _MUT_ANCHOR not in _mutated, "錨點仍在突變體裡 —— 替換不完整"
    ast.parse(_mutated)

    # `AppTest.from_file` 只把「腳本所在目錄」加進 sys.path；突變體放 tmp_path，
    # 所以自己補一行把 repo 根加回去（同 `tests/test_wf05_settings_skeleton.py`）。
    _boot_line = f"import sys as _s; _s.path.insert(0, {str(REPO_ROOT)!r})\n"
    _mutant = tmp_path / "mutant_app.py"
    _mutant.write_text(_boot_line + _mutated, encoding="utf-8")

    _errs = _errors(_boot(str(_mutant)))
    assert any("IndexError" in e or "list index out of range" in e
               for e in _errs), (
        "突變體（⑥ 必炸）跑完之後，`_errors()` 看不到那個 IndexError —— "
        "代表本檔的紅框判定是假的守衛。"
        f"實際紅框：{[e[:200] for e in _errs]}")

    assert _sha256(APP_PY) == _before, "本測試污染了 app.py"


# ════════════════════════════════════════════════════════════════
# (2) 把閘門真的勾起來
# ════════════════════════════════════════════════════════════════
def _tick(at: Any, label: str) -> Any:
    """依**標籤**勾起一個 checkbox 並重跑。

    ⛔ 不用 `at.checkbox[i]` —— 索引會隨畫面漂移，勾錯一顆而測試照樣綠。
    ⚠️ 畫面上有**兩顆**標籤同為「🔭 載入資料診斷」（舊 ⑤ 一顆、新 ⑦ 一顆），
       本函式只會勾到第一顆；本檔**不用它去勾那一對**（見檔尾未涵蓋範圍）。
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
    return _tick(_boot(str(APP_PY)), MAINTAIN_GATE_LABEL)


@pytest.fixture(scope="module")
def at_backfill_on(_hermetic) -> Any:
    return _tick(_boot(str(APP_PY)), BACKFILL_GATE_LABEL)


def test_ticking_the_maintenance_gate_breaks_that_block_in_the_preview_tab(
        at_maintain_on: Any) -> None:
    """勾「🗄️ 載入資料維護與通報」→ 維護區整塊紅，訊息點名 `key='divcal_gen'`。

    為什麼是 `divcal_gen` 而不是別的
    --------------------------------
    `render_manage_tab()` 依序畫 `_sec_pool()` → `_sec_dividend_calendar()`
    → `_sec_notify()`（`_sec_nav_backfill()` 兩邊都持有 `NAV_HISTORY` 旗標而跳過）。
    `_sec_pool` 的重複**先**發生，但它被自己的 `try` 接住降級成黃框（見下一條），
    所以**第一個逃出來的**是 `_sec_dividend_calendar` 的
    `st.button(key="divcal_gen")`（`ui/tab_manage.py:275`，AST 實測 `inside_try=False`）。
    """
    _hit = _hits(_errors(at_maintain_on),
                 ("資料維護與通報", "StreamlitDuplicateElementKey", "divcal_gen"))
    assert _hit, (
        "勾起維護區閘門之後**沒有**看到 `divcal_gen` 的重複 key 紅框。"
        f"實際紅框：{[e[:300] for e in _errors(at_maintain_on)]}")


def test_the_pool_collision_is_downgraded_to_a_yellow_box(
        at_maintain_on: Any) -> None:
    """⚠️ 同一次點擊還撞了第二個 —— 但它是**黃框**，不是紅框。

    `ui/tab_manage.py::_sec_pool`（L84-88）把 `_render_pool_editor()` 包在自己的
    `try` 裡，走 `_friendly(...)` 的**預設 `level="warning"`**。
    → `st.form("pool_add_form")` 的重複被降級成一則黃字「選股池管理載入失敗」。

    **這一條是本檔最容易被略過、也最該留下的一條**：任何只驗 `st.error` 的守衛
    （包括本檔的 `_errors()`）對它**結構上不可見**。
    """
    _hit = _hits(_warnings(at_maintain_on),
                 ("選股池管理載入失敗", "pool_add_form"))
    assert _hit, (
        "沒有看到 `pool_add_form` 的重複被降級成黃框。"
        f"實際黃框：{[w[:300] for w in _warnings(at_maintain_on)]}")


def test_ticking_the_backfill_gate_breaks_that_block_in_the_preview_tab(
        at_backfill_on: Any) -> None:
    """勾「🗄️ 載入手動補資料」→ 該區塊整塊紅，訊息點名 `key='navhist_import_form'`。

    第二條**一次點擊**就會撞的路徑：舊 ⑤ `_render_maintain_section` 同樣是
    **無條件**呼叫 `render_nav_manual_section()`，而該函式體內沒有任何 `try`
    → 重複直接propagate 到新 ⑦ 的 `safe_section`。
    """
    _hit = _hits(_errors(at_backfill_on),
                 ("手動補資料", "StreamlitAPIException", "navhist_import_form"))
    assert _hit, (
        "勾起手動補資料閘門之後**沒有**看到 `navhist_import_form` 的重複紅框。"
        f"實際紅框：{[e[:300] for e in _errors(at_backfill_on)]}")


def test_the_old_tab_five_is_not_damaged_by_either_collision(
        at_maintain_on: Any, at_backfill_on: Any) -> None:
    """兩種撞法都**只傷到新 ⑦**，舊 ⑤ 完好 —— 這是本次最重要的**緩解事實**。

    `st.tabs` 依序渲染，舊 ⑤ 排在新 ⑦ 前面 → 先註冊 key 的是舊 ⑤，
    **後**畫的新 ⑦ 才拋例外。所以線上正在用的舊分頁不受影響。

    ⚠️ 本條用「紅框訊息裡的區塊標題屬於誰」來判斷，**不是**逐分頁掃描
    （AppTest 的元素樹是攤平的，拿不到「這個元素屬於哪一格 tab」）——
    這是本條的**已知精度上限**，寫在這裡免得後人以為它比實際更強。
    """
    for _at, _who in ((at_maintain_on, "maintain"), (at_backfill_on, "backfill")):
        # 舊 ⑤ 的分頁級隔離訊息長這樣：「「⚙️ 設定與診斷」分頁渲染失敗」。
        _tab_level = _hits(_errors(_at), ("分頁渲染失敗",))
        assert not _tab_level, (
            f"[{_who}] 出現**分頁級**紅框 —— 代表傷害超出區塊隔離，"
            f"與本條記載的形狀不同：{[e[:300] for e in _tab_level]}")


# ════════════════════════════════════════════════════════════════
# ⚠️ 本檔**沒有**涵蓋的範圍（據實列出，不要把「沒測到」讀成「沒問題」）
# ════════════════════════════════════════════════════════════════
# 1. **兩顆「🔭 載入資料診斷」同時勾**（舊 ⑤ 一顆 + 新 ⑦ 一顆，標籤逐字相同）。
#    兩邊都在 gate 後面，所以要**兩次點擊**才會撞。靜態盤點該路徑共用
#    `render_data_guard_tab()`，literal key 交集 15 個（`btn_d5_*` / `navhist_import_*`
#    / `reg_*` / `_d5_fx_*`）。**本檔沒有跑過它** —— `_tick()` 依標籤找，
#    兩顆同名只會勾到第一顆。
#    ⚠️ **2026-09-08 就地更正：這一項的前提已經不成立（有意識的更正，不是漏刪 ·
#       決策者：AI 總管 · 依據：#835 實測）。**
#       ~~上面那句「**兩顆同名**」「**標籤逐字相同**」~~ —— **今天兩顆已經不同名**：
#       #835 依客戶 2026-09-08 拍板的線框 §0 推翻 1，把**新 ⑦** 那一顆的標籤換成
#       「**🔭 查一次資料來源狀態**」（進度語言 → 處境語言）；
#       **舊 ⑤ 那一顆仍是「🔭 載入資料診斷」**（客戶紅線：舊 Tab 一個位元組都不准動）。
#    **舊表述在寫下當天為真**，被推翻的是它的前提；**它要防的那件事仍然成立** ——
#       兩顆閘門背後共用同一支 `render_data_guard_tab()`，同時勾仍會撞 literal key，
#       **本檔照舊沒有跑過那條路徑**。
#    ⛔ **本輪【不】宣稱「現在分得開了、所以測得到了」** —— 那件事**沒有任何人驗過**
#       （`CLAUDE.md §2.1`：已被查證為假、卻沒被撤下的宣稱，比沒查證的更危險；
#       而**沒查證就宣稱已解**是同一族的另一面）。**本輪只更正那句已經為假的描述。**
#    ⛔ **本檔的斷言、常數與邏輯一個字都沒動**（`_tick()` 吃的是
#       `MANUAL_/MAINTAIN_/BACKFILL_GATE_LABEL` 常數，上面那兩個舊字串只出現在註解裡）
#       —— **這是純註解更正，不是行為改動。**
# 2. **需要先點一下才會出現的 widget**（按鈕點下去之後才畫的區塊）一律沒展開。
# 3. **動態 key**（f-string 組出來的，如 `btn_reload_{code}` / `de_fund_{...}`）——
#    靜態比不出來，runtime 也只走到「沒有持倉、沒有憑證」這一種資料狀態。
# 4. **有真憑證時的行為**：CI 沒有 Google Service Account，`_sec_pool` / nav_history
#    走的是「未登入」分支。**有憑證的使用者可能撞到更多、也可能更少。**
# 5. **②↔⑥ 那一對**只做了靜態盤點（literal key 交集 0），沒有逐 gate 跑過。
