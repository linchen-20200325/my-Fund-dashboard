"""③ 標的探索 —— **批次分析**那一塊的守衛（2026-09-07 接上真取數）。

這一份守的是客戶 2026-09-07 的**三項拍板**，以及它們各自最容易被悄悄改掉的地方。

===== ================================================= ==================================
拍板   內容                                               本檔哪一條在守
===== ================================================= ==================================
①      **只做貼上框，不做檔案上傳**                        :func:`test_the_only_way_in_is_a_paste_box`
②      **大表照搬全部欄位，不挑子集**                      :func:`test_the_table_keeps_every_single_column`
③      **③ 與 ② 重疊：兩邊都留，③ 不收欄位**              :func:`test_the_page_states_how_its_numbers_differ_from_page_02`
===== ================================================= ==================================

⚠️ **為什麼每一條都寫成「機制」而不是「某一顆突變會紅」**
------------------------------------------------------
「拿掉 X 這一行會轉紅」是**一次觀察**；下一個人換個寫法犯同一個錯，那條斷言照樣綠。
故本檔一律**參數化 / 結構比對**，讓「所有同類的錯」都在射程內。
（同一段話寫在 `tests/test_wf03_research_skeleton.py` 深度區那一節，本檔照同一個形狀。）

⚠️ **本檔不驗零寫入** —— 那是 `tests/test_wf03_research_no_writes.py` 的職責，
   而且它是**行為**測試（真的渲染一輪、在物件邊界攔寫入），與本檔的靜態規則互補。

⚠️ **本檔看不見什麼（照實寫，不要讀成「守死了」）**
--------------------------------------------------
1. **不驗真的跑一輪批次。** `build_batch_unified_row` 一律被替身換掉 ——
   真的呼叫它會連外網（MoneyDJ / FundClear / …），而**一份會連外網的守衛在 CI 上
   是不可重現的**：它紅不紅取決於當天上游活著沒有。
   ⇒ 「79 欄的值算得對不對」**不在本檔射程內**，那是 `ui/helpers/fund_grp_health/`
   自己的測試該守的東西。本檔只守「UI 有沒有把它們原封端出來」。
2. **`_batch_column_config()` 沒有被本檔呼叫過。** 它會 lazy import
   `ui.helpers.fund_grp_health.columns`，那條路徑往下需要 `pandas`
   （`services.fund_service`）。本檔改成**驗它的結構**（AST：它必須走
   `unified_column_config(batch=True)`、而且只做過濾不做挑選），
   ⛔ **不驗它實際回了什麼** —— 這一條缺口是刻意留的，不要讀成已經守住。
3. **不驗畫面上真的可以左右捲。** `st.dataframe` 的捲動是 streamlit 的行為，
   本檔驗的是「所有欄位都被交給它」，不是「瀏覽器真的長出捲軸」。
"""
from __future__ import annotations

import ast
import csv
import io
import pathlib
import sys
from typing import Any

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from _ast_bindings import gate_guarded_ids, gate_ifs, guarded_key_names, session_writes

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from ui.helpers.fund_grp_health.unified import (  # noqa: E402
    BATCH_NUMERIC_COLUMNS,
    BATCH_UNIFIED_COLUMNS,
)
from ui.helpers.story_nav import tab_label, where_to_find  # noqa: E402
from ui.views.page_03_research import (  # noqa: E402
    _LABEL_TERM,
    BATCH_PRINCIPAL_NOTE,
    BATCH_PRINCIPAL_TWD,
    BATCH_SUBMIT_LABEL,
    BLOCK_BATCH,
    _BATCH_EMPTY_MISSING,
    _BATCH_EMPTY_TITLE,
    _BATCH_FORM_KEY,
    _BATCH_UNPARSED_MISSING,
    _BATCH_UNPARSED_TITLE,
    _CODE_PLACEHOLDER,
    _LABEL_BATCH_CODES,
    _LABEL_BATCH_RETRY,
    _LONG_RUN_FUNDS,
    _SEC_PER_FUND_FAST,
    _SEC_PER_FUND_SLOW,
    _batch_csv,
    _batch_estimate,
    _batch_table_rows,
    _batch_where,
    _is_batch_fail,
    _is_batch_retryable,
    _parse_codes,
    split_batch_status_counts,
)

# ⚠️ **共用同一個渲染 harness，刻意不另寫第二份** —— 兩份會在「怎麼 patch `st`」
#    這件事上漂移，而那正是骨架守衛 `_render()` 開頭那段長註在講的陷阱
#    （錯的 patch 不會報錯，只會讓斷言對著半份畫面生效）。
from test_wf03_research_skeleton import _render, _segments, _text  # noqa: E402

_SRC = pathlib.Path(__file__).resolve().parent.parent / "ui" / "views" / "page_03_research.py"
_OLD_BATCH_TAB = pathlib.Path(__file__).resolve().parent.parent / "ui" / "tab_batch_analysis.py"

#: 一份「已送出」的搜尋查詢 —— 沒有它，批次那一塊根本不會被畫出來（Form 後才跑）。
_APPLIED = {"term": "ACDD", "source": "全部"}
_SK_CODES = "v03_research_batch_codes"
_SK_ROWS = "v03_research_batch_rows"

#: ⚠️ **送出鈕的替身分不出兩個 form** —— `submitted=True` 會讓**兩顆**送出鈕都回
#:    `True`（真的 streamlit 一次只會送出一個）。搜尋框若是空的，
#:    `_normalise_query()` 會判定「我不查了」→ 整頁退回空狀態、批次那一塊
#:    **根本不會被畫**，於是「按了送出卻沒跑」看起來像被測頁的 bug。
#:    故凡是走送出路徑的測試都要把搜尋詞一起餵進去。
#: ⛔ 這是**替身的限制**，不是被測頁的行為 —— 不要為了它去改頁面。
_SUBMIT_WIDGETS = {_LABEL_TERM: "ACDD"}


def _tree() -> ast.Module:
    return ast.parse(_SRC.read_text(encoding="utf-8"))


def _fns(tree: ast.AST) -> dict:
    return {_n.name: _n for _n in ast.walk(tree) if isinstance(_n, ast.FunctionDef)}


def _attr_calls(tree: ast.AST, names: tuple[str, ...]) -> list[str]:
    return [f"第 {_n.lineno} 行 {ast.unparse(_n.func)}(…)"
            for _n in ast.walk(tree)
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr in names]


def _fake_row(code: str, **over: Any) -> dict:
    """一列**形狀正確**的假結果 —— 79 個鍵一個不少（那正是上游的契約）。"""
    _r = {_c: None for _c in BATCH_UNIFIED_COLUMNS}
    _r["code"] = code
    _r["基金名"] = f"假基金 {code}"
    _r["狀態"] = "✅ 成功"
    _r.update(over)
    return _r


def _batch_body(parts: list[str]) -> str:
    return "\n".join(_segments(parts).get(BLOCK_BATCH, []))


# ══════════════════════════════════════════════════════════════════
# 拍板① 只做貼上框，不做檔案上傳
# ══════════════════════════════════════════════════════════════════

def test_the_only_way_in_is_a_paste_box():
    """⛔ **沒有 `st.file_uploader`，而且只有一個貼上框。**

    客戶 2026-09-07 拍板①。理由（寫進 PR 的那一句）：多一個上傳元件就多一組
    失敗路徑（解碼失敗、編碼判斷、檔案型別），真的需要再加屬**純新增**。

    ⚠️ **舊 `ui/tab_batch_analysis.py` 是有上傳元件的** —— 本條同時比對它，
    確保「本頁沒有」不是因為**沒有人記得加**，而是**刻意不加**：
    舊檔那一個必須真的存在，否則這條就是在守一個不存在的差異。
    """
    _t = _tree()
    _uploads = _attr_calls(_t, ("file_uploader",))
    assert not _uploads, (
        "本頁出現了檔案上傳元件：\n  " + "\n  ".join(_uploads)
        + "\n客戶 2026-09-07 拍板：**只做貼上框，不做檔案上傳**。")
    _areas = _attr_calls(_t, ("text_area",))
    assert len(_areas) == 1, (
        f"本頁的 `st.text_area` 站點是 {len(_areas)} 個，應該恰好 1 個（批次的貼上框）：\n  "
        + "\n  ".join(_areas)
        + "\n多一個輸入框就是多一條使用者不知道該用哪一個的動線。")
    # 正對照：舊分頁真的有上傳元件 —— 沒有它，本條守的是一個假差異。
    _old = ast.parse(_OLD_BATCH_TAB.read_text(encoding="utf-8"))
    assert _attr_calls(_old, ("file_uploader",)), (
        f"`{_OLD_BATCH_TAB.name}` 裡找不到 `st.file_uploader` —— "
        "那本條就不是在守一個真實的差異了（舊分頁被改過？還是已經拔除？）。"
        "若舊分頁已拔除，請把本段正對照改成登記，不要靜靜刪掉。")


def test_the_paste_box_is_labelled_and_shows_the_shape_it_wants():
    """貼上框要說**它收什麼形狀**，而且 placeholder 只准用線框那一個代碼。

    ⚠️ `_CODE_PLACEHOLDER`（`0P0000ABCD`）是線框逐字、且被骨架守衛
    `test_the_grey_blocks_never_print_the_illustrative_values_from_the_wireframe`
    明文豁免的**唯一**一個 —— 本條釘住批次沒有另外發明第二個像真的代碼。
    """
    _parts = _render(applied=_APPLIED)
    _body = _batch_body(_parts)
    assert _LABEL_BATCH_CODES in _body, f"貼上框的標籤不見了。\n{_body}"
    assert _LABEL_BATCH_RETRY in _body, f"重試勾選不見了。\n{_body}"
    assert BATCH_SUBMIT_LABEL in _body, f"送出鈕的字不見了。\n{_body}"
    _t = _tree()
    _fn = _fns(_t)["_render_batch_form"]
    _placeholders = [_k.value for _n in ast.walk(_fn)
                     if isinstance(_n, ast.Call)
                     for _k in _n.keywords if _k.arg == "placeholder"]
    assert len(_placeholders) == 1 and isinstance(_placeholders[0], ast.Name) \
        and _placeholders[0].id == "_CODE_PLACEHOLDER", (
        "批次的 placeholder 不是 `_CODE_PLACEHOLDER` —— "
        "那是線框逐字、也是唯一被豁免的示意代碼；"
        "自己發明一個像真的代碼會落進「線框示意值不准出現在畫面上」那條規則。")


# ══════════════════════════════════════════════════════════════════
# 拍板② 大表照搬全部欄位，不挑子集
# ══════════════════════════════════════════════════════════════════

def test_the_table_keeps_every_single_column():
    """⭐ **一欄都不准少。** 投影出來的列必須**逐欄逐序**等於 `BATCH_UNIFIED_COLUMNS`。

    客戶 2026-09-07 拍板②：**照搬全部欄位，不挑子集** ——
    挑哪幾欄是**新的業務決定**，會讓這一批從「搬版面」變成「改規格」。

    ⚠️ 用 `==` 比整個 list，**不是**比長度也**不是**比集合：
    · 比長度 → 換掉一欄不會紅；
    · 比集合 → 打亂順序不會紅，而順序就是使用者橫向捲動時的閱讀路徑。
    """
    _codes = ["AAA", "BBB"]
    _rows = {_c: _fake_row(_c) for _c in _codes}
    _out = _batch_table_rows(_codes, _rows)
    assert len(_out) == len(_codes), f"列數不對：{len(_out)} != {len(_codes)}"
    for _r in _out:
        assert list(_r) == list(BATCH_UNIFIED_COLUMNS), (
            "大表的欄位被挑過 / 換過順序了。\n"
            f"  少了：{[_c for _c in BATCH_UNIFIED_COLUMNS if _c not in _r]}\n"
            f"  多了：{[_c for _c in _r if _c not in BATCH_UNIFIED_COLUMNS]}\n"
            "客戶 2026-09-07 拍板②：**照搬全部欄位，不挑子集。**")


def test_the_column_skeleton_is_not_a_literal_list_in_this_page():
    """欄骨架必須**吃上游 SSOT**，不得在本頁抄一份欄名清單。

    ⚠️ 抄一份的後果不是「重複」而是「**會漂移**」：上游加一欄，本頁靜靜地少一欄，
    而畫面上看不出來（少的那一欄與「這批基金沒有這個值」長得一模一樣，§1）。
    """
    _fn = _fns(_tree())["_batch_table_rows"]
    _names = {_n.id for _n in ast.walk(_fn) if isinstance(_n, ast.Name)}
    assert "BATCH_UNIFIED_COLUMNS" in _names, (
        "`_batch_table_rows()` 沒有用到 `BATCH_UNIFIED_COLUMNS` —— 欄骨架被抄成本地清單了？")
    _lists = [_n for _n in ast.walk(_fn)
              if isinstance(_n, (ast.List, ast.Tuple, ast.Set))
              and len(_n.elts) >= 3
              and all(isinstance(_e, ast.Constant) and isinstance(_e.value, str)
                      for _e in _n.elts)]
    assert not _lists, (
        "`_batch_table_rows()` 裡有一份寫死的字串清單 —— "
        f"{[ast.unparse(_l)[:60] for _l in _lists]}\n"
        "欄名一律吃 `BATCH_UNIFIED_COLUMNS`，抄一份就會漂移。")


@pytest.mark.parametrize("col", sorted(set(BATCH_NUMERIC_COLUMNS) & set(BATCH_UNIFIED_COLUMNS)))
def test_a_numeric_column_arrives_as_a_number_not_a_string(col: str):
    """每一個宣告為數值的欄位都要真的被轉成數字（或 `None`），**逐欄驗**。

    ⚠️ 逐欄參數化而不是抽驗一欄：`column_config` 對這些欄用的是 `NumberColumn`，
    餵字串進去的那一欄會**只有那一欄**壞掉，抽驗抽不到它。
    ⚠️ 認不得的值一律 `None` ＝ **留白**，⛔ 不得變成 0（§1：錯的數字比沒有數字危險）。
    """
    _out = _batch_table_rows(["AAA"], {"AAA": _fake_row("AAA", **{col: "1,234.5"})})
    assert _out[0][col] == 1234.5, (
        f"數值欄「{col}」沒有被轉成數字（實際 {_out[0][col]!r}）。")
    _junk = _batch_table_rows(["AAA"], {"AAA": _fake_row("AAA", **{col: "⬜ 不足"})})
    assert _junk[0][col] is None, (
        f"數值欄「{col}」把一個認不得的值變成了 {_junk[0][col]!r} —— "
        "認不得就留白，**絕不填 0**（§1）。")


def test_every_column_reaches_the_widget():
    """⭐ 真的渲染一輪 —— 交給表格元件的欄位必須是**全部**，不是「大部分」。

    ⚠️ 上面兩條驗的是**投影函式**；本條驗的是**那份投影真的被端上畫面** ——
    中間任何一層「順手篩一下比較好看」都會在這裡被抓到。
    ⚠️ 用 `wide_table` 的替身接、而不是讀 recorder 的 `[dataframe]` 那一行：
    recorder 只錄得到位置引數裡的純量，**錄不到 list[dict] 的欄位** ——
    拿它來驗欄數會是一條**恆真**的斷言。
    """
    _codes = ["AAA", "BBB", "CCC"]
    _seen: list = []
    _render(applied=_APPLIED,
            session={_SK_CODES: _codes,
                     _SK_ROWS: {_c: _fake_row(_c) for _c in _codes}},
            patch={"_batch_column_config": lambda cols: {},
                   "wide_table": lambda data, **kw: _seen.append((data, kw))})
    # ⚠️ 深度區也有兩張 `wide_table`（持股 / 配息），故挑**帶得出 `code` 欄**的那一份。
    _big = [(_d, _kw) for _d, _kw in _seen
            if _d and isinstance(_d[0], dict) and "code" in _d[0]]
    assert len(_big) == 1, (
        f"批次應該把**恰好一份**資料交給大表元件，實際 {len(_big)} 份。\n{_seen}")
    _data, _kw = _big[0]
    assert len(_data) == len(_codes), f"交出去的列數不對：{len(_data)} != {len(_codes)}"
    assert list(_data[0]) == list(BATCH_UNIFIED_COLUMNS), (
        f"交給表格的欄位不是全部 {len(BATCH_UNIFIED_COLUMNS)} 欄。\n"
        f"  少了：{[_c for _c in BATCH_UNIFIED_COLUMNS if _c not in _data[0]]}\n"
        "客戶拍板②：照搬全部欄位，不挑子集。")
    assert "column_config" in _kw, (
        "大表沒有帶 `column_config` —— 79 個中文欄名會變成零 tooltip，"
        "而那是本頁對「橫向捲很久」唯一的緩解手段。")
def test_the_column_config_is_the_shared_one_not_a_new_design():
    """逐欄 tooltip 走**既有共用的那一份**，不得在本頁另立一套。

    ⚠️ 這一條同時是「橫向捲很久」那個問題的**唯一**緩解手段的錨點：
    79 欄一定要捲，而 `unified_column_config(batch=True)` 讓每一個欄名
    都可以把滑鼠移上去看說明。**它不動任何欄位**，所以與拍板②不衝突。
    ⛔ **凍結欄 / 分組欄不在本批**（要自己發明「哪幾欄算一組」＝ 版面決定），
       已回報總管；`ui/components/column_group_tabs.py` 目前 production 0 caller。
    """
    _fn = _fns(_tree())["_batch_column_config"]
    _calls = {ast.unparse(_n.func) for _n in ast.walk(_fn) if isinstance(_n, ast.Call)}
    assert "unified_column_config" in _calls, (
        "`_batch_column_config()` 沒有走共用的 `unified_column_config()` —— "
        f"實際呼叫了 {sorted(_calls)}。另立一套 tooltip 會與健診大表漂移。")
    _kw = [_k for _n in ast.walk(_fn) if isinstance(_n, ast.Call)
           for _k in _n.keywords if _k.arg == "batch"]
    assert _kw and getattr(_kw[0].value, "value", None) is True, (
        "`unified_column_config()` 沒有帶 `batch=True` —— "
        "那樣會少掉批次專屬的四欄（狀態 / 備註 / 淨值日期 / 淨值新鮮度）的說明。")


# ══════════════════════════════════════════════════════════════════
# 拍板③ 與 ② 的重疊：兩邊都留，就地講清楚口徑差異
# ══════════════════════════════════════════════════════════════════

def test_the_page_states_how_its_numbers_differ_from_page_02():
    """⭐ 畫面上必須講明：**這裡是齊頭 100 萬，② 是你實際投入的金額。**

    客戶 2026-09-07 拍板③：兩邊都留、③ 不收欄位 —— **重疊是刻意的**。
    重疊而不講口徑，使用者會看到同一檔基金在兩頁的配息金額不一樣，
    然後合理地認為其中一邊算錯了。

    ⚠️ **這句話的方向是查證出來的，不是抄來的**（三條依據寫在
    `page_03_research.BATCH_PRINCIPAL_NOTE` 上方）。本條把方向釘死：
    「齊頭 100 萬」必須掛在**這一頁**，「實際投入」必須掛在**②**，
    **講反了要轉紅** —— 那正是這件事已知會被弄反的地方。
    """
    _body = _batch_body(_render(applied=_APPLIED))
    assert "100 萬" in _body, f"畫面上沒有講本金口徑。\n{_body}"
    assert "實際投入" in _body, f"畫面上沒有提到「實際投入」這個對照口徑。\n{_body}"
    assert tab_label("health") in _body, (
        "沒有指名對照的是哪一頁 —— 分頁名要走 `tab_label('health')`，不得手抄。")
    # ⭐ 方向：**假設**那一半必須貼著「這張表」，**實際投入**那一半必須貼著 ②。
    #    講反的版本（「這張表用你實際投入的金額；② 才是假設 100 萬」）會讓
    #    「假設投入」跑到分頁名**之後**，兩條斷言各自轉紅。
    _i_health = _body.find(tab_label("health"))
    _i_assume = _body.find("假設投入")
    assert -1 < _i_assume < _i_health, (
        "「假設投入 100 萬」沒有掛在**這一頁**（它出現在分頁名之後）—— 口徑講反了。\n"
        f"（位置：假設={_i_assume} / 分頁名={_i_health}）\n{_body}")
    assert "實際投入" in _body[_i_health:], (
        f"「{tab_label('health')}」之後沒有「實際投入」—— "
        "② 的口徑沒有被講出來（或被講成了齊頭本金）。\n" + _body)


def test_the_principal_is_passed_explicitly_not_left_to_a_default():
    """`principal_twd` 要**顯式傳**，即使它等於上游的預設值。

    ⚠️ 上游 `build_batch_unified_row(code, principal_twd=1_000_000.0, …)` 的預設值
    哪天被改掉，這一頁的口徑會**跟著變、而畫面上的那句話不會變** ——
    那一刻畫面就在說謊。顯式傳讓這一頁的口徑不依賴別人的預設值。
    """
    _fn = _fns(_tree())["_run_batch"]
    _calls = [_n for _n in ast.walk(_fn) if isinstance(_n, ast.Call)
              and ast.unparse(_n.func).endswith("build_batch_unified_row")]
    assert len(_calls) == 1, f"`_run_batch()` 應該恰好呼叫一次批次列 builder，實際 {len(_calls)} 次。"
    _kw = {_k.arg: _k.value for _k in _calls[0].keywords}
    assert "principal_twd" in _kw, (
        "`build_batch_unified_row(...)` 沒有顯式傳 `principal_twd` —— "
        "口徑會靜靜跟著上游的預設值走。")
    assert isinstance(_kw["principal_twd"], ast.Name) \
        and _kw["principal_twd"].id == "BATCH_PRINCIPAL_TWD", (
        f"`principal_twd` 傳的不是 `BATCH_PRINCIPAL_TWD`（實際 "
        f"{ast.unparse(_kw['principal_twd'])}）—— 那個常數是這一頁口徑的單一真相源。")
    assert BATCH_PRINCIPAL_TWD == 1_000_000.0, (
        f"本頁的本金常數變成了 {BATCH_PRINCIPAL_TWD} —— "
        "畫面上那句「假設投入 100 萬台幣」會當場變成假的。改常數請一起改那句話。")
    assert "100 萬" in BATCH_PRINCIPAL_NOTE, (
        "口徑說明沒有講出金額 —— 常數與文案必須互相對得上。")


# ══════════════════════════════════════════════════════════════════
# 鐵則 02：長時間運算只能在送出之後
# ══════════════════════════════════════════════════════════════════

def test_the_heavy_run_never_starts_without_a_submit():
    """⭐ **沒按送出 → 一檔都不准跑。** 線框 Tab 03 的 chip：「Form 後才跑」。

    ⚠️ 這一條是本區最貴的一條規則：批次是**序列**跑，400 檔實測 20~45 秒/檔。
    「每次 rerun 都跑一輪」在畫面上看起來一模一樣，成本卻是幾小時。
    """
    _seen: list = []

    def _spy(codes, *, retry_failed):
        _seen.append((list(codes), retry_failed))

    _render(applied=_APPLIED, submitted=False,
            widget={**_SUBMIT_WIDGETS, _LABEL_BATCH_CODES: "AAA\nBBB"},
            patch={"_run_batch": _spy})
    assert not _seen, (
        f"沒有按送出，批次卻跑了：{_seen}\n"
        "線框：「長時間運算，**必須在 Form 之後才啟動**」。")

    _render(applied=_APPLIED, submitted=True,
            widget={**_SUBMIT_WIDGETS, _LABEL_BATCH_CODES: "AAA\nBBB"},
            patch={"_run_batch": _spy})
    assert _seen == [(["AAA", "BBB"], False)], (
        f"按了送出，批次卻沒跑（或參數不對）：{_seen}\n"
        "⚠️ 這半條同樣重要 —— 只驗『沒按不跑』的話，把整段刪掉也會全綠。")


def test_the_retry_checkbox_actually_reaches_the_runner():
    """勾了「重試」要真的傳下去 —— 不然那個勾選是裝飾品。"""
    _seen: list = []

    def _spy(codes, *, retry_failed):
        _seen.append(retry_failed)

    _render(applied=_APPLIED, submitted=True, patch={"_run_batch": _spy},
            widget={**_SUBMIT_WIDGETS, _LABEL_BATCH_CODES: "AAA",
                    _LABEL_BATCH_RETRY: True})
    assert _seen == [True], f"重試勾選沒有傳到執行端：{_seen}"


def test_the_batch_form_is_gated_and_writes_nothing_outside_the_gate():
    """批次的 session 寫入**全部**要在送出閘門的正分支裡。

    ⚠️ 這是骨架守衛對搜尋 form 那條規則的**同型複製**（`_ast_bindings` 同一組工具）——
    ② 的紅隊實測顯示：只包 `st.form` 而不 gate 住寫入，等於 form 白包，
    每次 rerun 都會覆寫已送出值。
    ⛔ **仍然分不出真假閘門**（`if not _gate:` 照樣被認成閘門）—— 靜態規則做不到，
       那一半由 :func:`test_the_heavy_run_never_starts_without_a_submit` 的行為測試補。
    """
    _t = _tree()
    _fn = _fns(_t)["_render_batch_form"]
    _writes = session_writes(_fn, widget_key_names=guarded_key_names(_t))
    assert _writes, "`_render_batch_form()` 沒有把送出結果寫回 session。"
    assert gate_ifs(_fn), (
        "找不到 `with applied_form(...) as <gate>:` 綁出來的那個閘門 `if`。")
    _naked = [_w for _w in _writes if id(_w) not in gate_guarded_ids(_fn)]
    assert not _naked, (
        "批次有 session 寫入**沒有**被送出閘門包住：\n  "
        + "\n  ".join(f"第 {_w.lineno} 行：{ast.unparse(_w)[:70]}" for _w in _naked))


def test_the_batch_never_opens_a_form_or_a_grid_of_its_own():
    """鐵則 01 / 02：批次也走共用元件，**不得**自己 `st.form` / `st.columns`。

    ⚠️ `st.form` 那半有全域網子（`tests/test_ui_rerun_contract.py::FORM_SITE_TOTAL`
    是精確 `==`，多一個站點就紅）；`st.columns` 那半**沒有** —— 全域計數器抓的是
    「欄數不是 3」的呼叫，合規的 3 欄它一動也不動。**本條是那半唯一的網子。**
    """
    _bad = _attr_calls(_tree(), ("columns", "form"))
    assert not _bad, ("本頁自己開了網格 / 表單：\n  " + "\n  ".join(_bad))


def test_the_two_forms_have_different_keys():
    """兩個 form 的 key 不得相同 —— 撞 key 在 streamlit 會當場炸掉整頁。"""
    _keys = {_n.args[0].value for _n in ast.walk(_tree())
             if isinstance(_n, ast.Call) and getattr(_n.func, "id", "") == "applied_form"
             and _n.args and isinstance(_n.args[0], ast.Constant)}
    _names = {ast.unparse(_n.args[0]) for _n in ast.walk(_tree())
              if isinstance(_n, ast.Call) and getattr(_n.func, "id", "") == "applied_form"
              and _n.args}
    assert len(_names) == 2, f"`applied_form(...)` 的站點應為 2 個，實際：{sorted(_names)}"
    assert _BATCH_FORM_KEY.startswith("v03_"), (
        "批次 form 的 key 沒有本頁的命名前綴 —— 會與舊分頁的 session 互相覆寫。")


# ══════════════════════════════════════════════════════════════════
# 鐵則 03 / 04：兩種灰各自誠實，紅色留給真的錯
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("session,title,missing", [
    (None, _BATCH_EMPTY_TITLE, _BATCH_EMPTY_MISSING),
    ({_SK_CODES: []}, _BATCH_UNPARSED_TITLE, _BATCH_UNPARSED_MISSING),
])
def test_the_two_batch_greys_say_different_things(session, title, missing):
    """「還沒貼」與「貼了但認不得」是**兩種處境**，文案必須分開。

    ⚠️ 兩者在 session 上長得幾乎一樣（`[]` vs 不存在），最容易被合成一句。
    合成之後，一個格式貼錯的使用者會被告知「你還沒貼」，然後再貼一次同樣的東西。
    """
    _body = _batch_body(_render(applied=_APPLIED, session=session))
    assert title in _body, f"缺了「{title}」這一則空狀態。\n{_body}"
    assert missing in _body, f"「{title}」沒有講缺什麼。\n{_body}"
    _other = (_BATCH_UNPARSED_MISSING if missing == _BATCH_EMPTY_MISSING
              else _BATCH_EMPTY_MISSING)
    assert _other not in _body, (
        f"「{title}」印的是**另一種處境**的理由 —— 兩者的下一步不同"
        "（去貼 vs 去改格式），串在一起使用者無從判斷。\n" + _body)


def test_the_batch_pointer_is_the_paste_box():
    """⭐ 批次的「去哪補」指的是**它自己的貼上框**，不是搜尋條件。

    ⚠️ **這一則與本頁其餘灰態的指路不同，而且是刻意的**：
    `_pending_where()` 那一族自陳「有效性有限」（那一塊沒接上，去哪都沒用）。
    批次**已經接上了**，所以它的指路必須是**照著做真的有效**的那一種。
    「去搜尋條件打一個代碼」解決不了「你還沒貼多個代碼」。

    ⚠️ 本條比骨架那條嚴：它連**指路指到的那個欄位在畫面上真的存在**都驗
    （`CLAUDE.md §8.3.P` 的 `P-WHERECONTENT-1` 記載這一層通常守不到）。
    """
    _where = _batch_where()
    assert where_to_find("research") in _where, "指路沒有走 `where_to_find()`。"
    assert _LABEL_BATCH_CODES in _where, (
        f"指路沒有指到貼上框（`{_LABEL_BATCH_CODES}`）：{_where}")
    _body = _batch_body(_render(applied=_APPLIED))
    assert f"（請先到：{_where}）" in _body, (
        f"畫面上那句「請先到：…」不是預期的地方字串。\n{_body}")
    # ⭐ 指路指到的東西**真的在畫面上** —— 這一層才是它「有效」的證據。
    assert f"[text_area] {_LABEL_BATCH_CODES}" in _body, (
        "指路指到一個畫面上沒有的欄位 —— 那是一句照著做也做不到的指令。\n" + _body)


def test_a_batch_grey_is_never_painted_red():
    """灰＝前提不足，紅＝系統真出錯。**批次沒有結果不是故障。**"""
    for _session in (None, {_SK_CODES: []}, {_SK_CODES: ["AAA"], _SK_ROWS: {}}):
        _parts = _render(applied=_APPLIED, session=_session)
        _reds = [_p for _p in _parts if _p.startswith("[error]")]
        assert not _reds, (
            f"批次在 session={_session!r} 時塗了紅：{_reds}\n"
            "沒有結果是**前提不足**（灰），不是系統出錯（紅）。")


def test_no_empty_table_frame_before_there_is_anything_to_show():
    """鐵則 04：沒有資料**不畫空表格外框**。

    ⚠️ 只看**批次那一段** —— 深度區的持股 / 配息也走 `wide_table`，
    整頁比對會把它們算進來（那是**別人**畫的，與本條無關）。
    """
    for _session in (None, {_SK_CODES: []}, {_SK_CODES: ["AAA"], _SK_ROWS: {}}):
        _body = _batch_body(_render(applied=_APPLIED, session=_session))
        assert "[dataframe]" not in _body, (
            f"session={_session!r} 時批次畫了一個空表格。\n{_body}\n"
            "線框 Rule 04：無資料不畫空表格外框，改用空狀態三要素。")
def test_a_half_finished_batch_shows_what_it_has_and_says_what_is_left():
    """跑到一半：**已完成的照畫**，剩下幾檔要講出來 —— 不得整批藏起來。

    ⚠️ 反過來也不行（把還沒跑的檔畫成空白列）：那會讓「還沒跑」與
    「跑了但這檔沒有資料」在表上長得一模一樣（§1）。
    """
    _codes = ["AAA", "BBB", "CCC"]
    _seen: list = []
    _body = _batch_body(_render(
        applied=_APPLIED,
        session={_SK_CODES: _codes, _SK_ROWS: {"AAA": _fake_row("AAA")}},
        patch={"_batch_column_config": lambda cols: {},
               "wide_table": lambda data, **kw: _seen.append(data)}))
    _big = [_d for _d in _seen if _d and isinstance(_d[0], dict) and "code" in _d[0]]
    assert len(_big) == 1 and len(_big[0]) == 1, (
        f"跑完一檔時應該交出**一列**，實際：{[len(_d) for _d in _big]}")
    assert "剩餘 **2**" in _body, f"沒有講還剩幾檔。\n{_body}"
def test_the_failure_note_only_shows_up_when_something_failed():
    """失敗說明只在**真的有失敗**時出現 —— 全綠時多一句警告是噪音。"""
    _ok = _batch_body(_render(applied=_APPLIED, patch={"_batch_column_config": lambda cols: {}}, session={
        _SK_CODES: ["AAA"], _SK_ROWS: {"AAA": _fake_row("AAA")}}))
    assert "不會偷偷丟掉" not in _ok, f"全部成功時不該印失敗說明。\n{_ok}"
    _bad = _batch_body(_render(applied=_APPLIED, patch={"_batch_column_config": lambda cols: {}}, session={
        _SK_CODES: ["AAA"],
        _SK_ROWS: {"AAA": _fake_row("AAA", **{"狀態": "❌ 抓取失敗", "備註": "假件"})}}))
    assert "不會偷偷丟掉" in _bad, f"有失敗時應該說明留白的意思。\n{_bad}"


# ══════════════════════════════════════════════════════════════════
# 純函式：解析、三態計數、時間估計
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("raw,want", [
    ("AAA\nBBB", ["AAA", "BBB"]),
    ("aaa\nbbb", ["AAA", "BBB"]),                 # 小寫轉大寫
    ("AAA\nAAA\nBBB", ["AAA", "BBB"]),            # 去重、保留首次順序
    ("AAA,某某基金\nBBB;第二檔", ["AAA", "BBB"]),   # 每行只讀第一欄
    ("代號\nAAA", ["AAA"]),                        # 表頭字略過
    ("基金代碼\tX\nAAA", ["AAA"]),
    ("  AAA  \n\n  BBB ", ["AAA", "BBB"]),        # 空白與空行
    ("AA\nAAA", ["AAA"]),                          # 太短的不是代碼
    ("A" * 21 + "\nAAA", ["AAA"]),                 # 太長的不是代碼
    ("這不是代碼\nAAA", ["AAA"]),                   # 非英數
    ("", []),
    ("   ", []),
    (None, []),                                    # 非字串一律空清單
    (object(), []),
])
def test_the_paste_box_parser_is_forgiving_but_never_invents(raw, want):
    """貼上框的解析：寬鬆吃格式，但**認不得就丟掉，絕不猜**。

    ⚠️ `None` / 非字串那兩格是刻意的：`st.text_area` 在替身／降級路徑下不保證回字串，
    而 `"".join` 之類的寫法遇到非字串會**靜默**產生一個看起來合理的空清單 ——
    這裡把它變成一個**寫出來的**行為，而不是一個碰巧。
    """
    assert _parse_codes(raw) == want


def test_the_parser_matches_the_old_tab_on_the_same_input():
    """⭐ 正對照：同一份輸入，本頁與**舊分頁**要解析出同一份清單。

    ⚠️ 本頁的 `_parse_codes()` 是一份**重複實作**（舊分頁會被整批拔除，
    本頁一行都不 import 它）。重複本身無法避免，但**漂移**可以擋 ——
    本條把舊分頁那支**讀原始碼編譯出來**（不是 import，不觸發它的 module 副作用）跑一次。
    ⚠️ 舊分頁哪天真的被拔掉 → 本條 `skip` 並喊出來，**不會靜靜消失**。
    """
    if not _OLD_BATCH_TAB.exists():
        pytest.skip(f"{_OLD_BATCH_TAB.name} 已拔除 —— "
                    "請把 `_parse_codes()` 收成單一 SSOT，並刪掉本條。")
    _src = _OLD_BATCH_TAB.read_text(encoding="utf-8")
    _mod = ast.parse(_src)
    _want = [_n for _n in _mod.body
             if isinstance(_n, ast.FunctionDef) and _n.name == "_parse_codes"]
    assert _want, "舊分頁的 `_parse_codes` 不見了（改名了？）—— 本條的正對照失效，請重新接上。"
    _ns: dict = {}
    _snippet = ast.Module(body=[
        ast.Import(names=[ast.alias(name="re", asname=None)]),
        *[_n for _n in _mod.body
          if isinstance(_n, ast.Assign)
          and any(getattr(_t, "id", "") in ("_CODE_RE", "_HEADER_TOKENS")
                  for _t in _n.targets)],
        *_want], type_ignores=[])
    exec(compile(ast.fix_missing_locations(_snippet), "<old-tab>", "exec"), _ns)
    _old_parse = _ns["_parse_codes"]
    for _raw in ("AAA\nbbb\nAAA\n代號\nCCC,名字\n太短\nA" * 2,
                 "ACCP138,美元基金\nB07\n0050\n",
                 "CODE\nticker\nX1\nXYZ123"):
        assert _parse_codes(_raw) == _old_parse(_raw), (
            f"本頁與舊分頁對同一份輸入解析出不同結果：\n  輸入 {_raw!r}\n"
            f"  本頁 {_parse_codes(_raw)}\n  舊頁 {_old_parse(_raw)}")


@pytest.mark.parametrize("statuses,want", [
    (["✅ 成功"], (1, 0, 0)),
    (["⚠️ 部分成功"], (0, 1, 0)),            # ⭐ 字面含「成功」，**不得**算進全綠
    (["❌ 抓取失敗"], (0, 0, 1)),
    (["⚠️ 無效代號"], (0, 0, 1)),
    ([""], (0, 0, 1)),
    ([None], (0, 0, 1)),
    (["✅ 成功", "⚠️ 部分成功", "❌ 抓取失敗"], (1, 1, 1)),
])
def test_partial_success_is_never_counted_as_success(statuses, want):
    """⭐ 「⚠️ 部分成功」**字面上含有「成功」** —— 它必須自成一態。

    把它算進全綠，使用者永遠不會去看它的備註，然後拿一列缺了 13~22 欄的資料
    去做換標決策，而那一列在表裡與正常列**長得一模一樣**（§1）。
    """
    assert split_batch_status_counts(statuses) == want


def test_the_three_counts_always_add_up():
    """三態相加必等於輸入長度 —— 沒有任何一檔會在計數裡消失。"""
    _statuses = ["✅ 成功", "⚠️ 部分成功", "❌ 抓取失敗", "⚠️ 無效代號", "", None, "怪東西"]
    assert sum(split_batch_status_counts(_statuses)) == len(_statuses)


@pytest.mark.parametrize("status,fail,retry", [
    ("✅ 成功", False, False),
    ("⚠️ 部分成功", False, True),     # 不算失敗，但值得重跑
    ("❌ 抓取失敗", True, True),
    ("⚠️ 無效代號", True, True),
])
def test_retryable_covers_partial_success_but_fail_does_not(status, fail, retry):
    """「部分成功」**不算失敗、但要能重跑**。

    ⚠️ 把它排除在重試之外，使用者會拿到一個**自己無法處理**的狀態：
    唯一出路是整批重來（400 檔要好幾小時）。
    """
    _row = {"狀態": status}
    assert _is_batch_fail(_row) is fail
    assert _is_batch_retryable(_row) is retry


def test_the_time_estimate_mirrors_the_old_tab():
    """⭐ 每檔秒數必須與**舊分頁**逐值相同 —— 它是實測值，不是我們估的。

    ⚠️ 舊分頁就地記載：「原本 ~5s/檔，實機實測 **~45s/檔**；400 檔原本顯示
    『約 33 分鐘』，實際約 **5 小時** —— 差 9 倍。使用者照這個數字決定要不要按下去，
    **低報等於騙他**。」本條讓「有人把它改小」當場轉紅。
    ⚠️ 舊分頁被拔除時 `skip` 並喊出來（那時要把這兩個常數收成 SSOT）。
    """
    if not _OLD_BATCH_TAB.exists():
        pytest.skip(f"{_OLD_BATCH_TAB.name} 已拔除 —— "
                    "請把每檔秒數收成單一 SSOT，並刪掉本條。")
    _old: dict = {}
    for _n in ast.walk(ast.parse(_OLD_BATCH_TAB.read_text(encoding="utf-8"))):
        if isinstance(_n, ast.Assign) and isinstance(_n.value, ast.Constant):
            for _t in _n.targets:
                if getattr(_t, "id", "") in ("_SEC_PER_FUND_FAST", "_SEC_PER_FUND_SLOW"):
                    _old[_t.id] = _n.value.value
    assert _old, "舊分頁的每檔秒數常數不見了（改名了？）—— 本條的正對照失效。"
    assert _old.get("_SEC_PER_FUND_FAST") == _SEC_PER_FUND_FAST, (
        f"快取命中那一端與舊分頁不同：本頁 {_SEC_PER_FUND_FAST} vs 舊頁 "
        f"{_old.get('_SEC_PER_FUND_FAST')}")
    assert _old.get("_SEC_PER_FUND_SLOW") == _SEC_PER_FUND_SLOW, (
        f"走完 fallback chain 那一端與舊分頁不同：本頁 {_SEC_PER_FUND_SLOW} vs 舊頁 "
        f"{_old.get('_SEC_PER_FUND_SLOW')}")


@pytest.mark.parametrize("n", [0, -1])
def test_no_estimate_when_there_is_nothing_left(n):
    """沒有待辦就不要編一個時間出來。"""
    assert _batch_estimate(n) == "—"


def test_the_estimate_is_a_range_not_a_single_number():
    """給區間，不給單點 —— 離散度本來就大，單點會被讀成承諾。"""
    _txt = _batch_estimate(100)
    assert "~" in _txt, f"預估變成了單點值：{_txt}"
    assert str(round(100 * _SEC_PER_FUND_FAST / 60)) in _txt
    assert str(round(100 * _SEC_PER_FUND_SLOW / 60)) in _txt


def test_a_long_run_warns_before_the_user_commits_hours():
    """檔數多到會跑很久時，**按下去之前**要先講。"""
    _codes = [f"C{_i:04d}" for _i in range(_LONG_RUN_FUNDS + 1)]
    _body = _batch_body(_render(applied=_APPLIED, patch={"_batch_column_config": lambda cols: {}}, session={
        _SK_CODES: _codes, _SK_ROWS: {_codes[0]: _fake_row(_codes[0])}}))
    assert "請不要關掉分頁" in _body, f"長時間批次沒有事前警告。\n{_body[:800]}"


# ══════════════════════════════════════════════════════════════════
# CSV 下載 —— 草稿版面裡就有的那一顆
# ══════════════════════════════════════════════════════════════════

def test_the_csv_keeps_the_same_columns_in_the_same_order_as_the_table():
    """下載的 CSV **不是另一份投影** —— 欄名與欄序必須與畫面上那張表完全相同。

    ⚠️ 這條擋的是一個很容易發生、而且**畫面上完全看不出來**的漂移：
    有人為了「CSV 乾淨一點」在匯出端挑欄位／換順序，於是使用者拿去對帳時
    對不上他螢幕上看到的那張表，而兩邊都沒有任何錯誤訊息。
    """
    _rows = _batch_table_rows(["AAA"], {"AAA": _fake_row("AAA")})
    _raw = _batch_csv(_rows)
    assert isinstance(_raw, bytes), "下載內容必須是 bytes（`st.download_button` 收 bytes）。"
    assert _raw.startswith(b"\xef\xbb\xbf"), (
        "CSV 少了 UTF-8 BOM —— Excel 會把中文欄名讀成亂碼。"
        "（舊 `ui/tab_batch_analysis.py` 的下載鈕用的也是 `utf-8-sig`，同一個理由。）")
    _text_csv = _raw.decode("utf-8-sig")
    _header = _text_csv.splitlines()[0]
    _cols = next(csv.reader([_header]))
    assert _cols == list(BATCH_UNIFIED_COLUMNS), (
        "CSV 的欄位與畫面上那張表不一致。\n"
        f"  少了：{[_c for _c in BATCH_UNIFIED_COLUMNS if _c not in _cols]}\n"
        f"  多了：{[_c for _c in _cols if _c not in BATCH_UNIFIED_COLUMNS]}")


def test_a_missing_value_stays_blank_in_the_csv_and_never_becomes_zero():
    """CSV 裡的缺值是**空白**，⛔ 不得變成 0（§1：錯的數字比沒有數字更危險）。"""
    _rows = _batch_table_rows(["AAA"], {"AAA": _fake_row("AAA", **{"Sharpe 1Y": None})})
    _text_csv = _batch_csv(_rows).decode("utf-8-sig")
    _reader = list(csv.DictReader(io.StringIO(_text_csv)))
    assert _reader[0]["Sharpe 1Y"] == "", (
        f"缺值在 CSV 裡變成了 {_reader[0]['Sharpe 1Y']!r} —— 缺值就留白。")
    assert _reader[0]["code"] == "AAA", "非缺值的欄位被一起清掉了。"


def test_the_download_button_only_appears_once_there_is_a_table():
    """沒有表就沒有下載鈕 —— 一顆按下去會拿到空檔案的鈕是鐵則 04 的冗餘占位。"""
    _empty = _batch_body(_render(applied=_APPLIED,
                                 session={_SK_CODES: ["AAA"], _SK_ROWS: {}}))
    assert "download_button" not in _empty and "下載這張表" not in _empty, (
        f"還沒有任何一檔跑完，卻畫了下載鈕。\n{_empty}")
    _full = _batch_body(_render(
        applied=_APPLIED, session={_SK_CODES: ["AAA"], _SK_ROWS: {"AAA": _fake_row("AAA")}},
        patch={"_batch_column_config": lambda cols: {}}))
    assert "下載這張表" in _full, f"有表了卻沒有下載鈕。\n{_full}"


def test_the_csv_is_built_without_pandas_and_without_touching_disk():
    """CSV 走標準庫 `csv`，**不得**改成 `to_csv` / `write_text` 那一族。

    ⚠️ 理由不是「pandas 不好」，是**名字**：`to_csv` 落在零寫入守衛的磁碟 sink
    清單裡，會讓一個**根本不碰磁碟**的動作在守衛眼裡看起來像在寫檔 ——
    那種偽陽性最後一定會用「把它加進豁免」收場，而豁免會一路長大。
    """
    _fn = _fns(_tree())["_batch_csv"]
    _names = {_n.attr for _n in ast.walk(_fn) if isinstance(_n, ast.Attribute)}
    for _bad in ("to_csv", "to_json", "to_parquet", "write_text", "write_bytes"):
        assert _bad not in _names, (
            f"`_batch_csv()` 用到了 `{_bad}` —— 請改回標準庫 `csv`（理由見本條 docstring）。")
    _mods = {_a.name for _n in ast.walk(_fn) if isinstance(_n, ast.Import)
             for _a in _n.names}
    assert "csv" in _mods and "io" in _mods, (
        f"`_batch_csv()` 沒有走標準庫 `csv` / `io`，實際 import 了 {_mods}。")
