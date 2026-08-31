"""元件 B「🧩 互補配對探索」的 3 支門檻滑桿包 `st.form` —— 鐵律 2 防重繪(2026-08-31)。

#738 建元件 B 時**具名延後**了這件事(唯一原因:`tests/test_ui_rerun_contract.py` 當時
由 #736 佔用、明令禁改 —— File Boundary 防撞)。本批阻擋解除後補上,本檔是它的守衛。

## 為什麼要這一份,而不是靠既有的 `test_ui_rerun_contract.py`

那一份守的是**全域資產登記**(「有幾處 form、分別在哪個函式」),它答得出
「元件 B 有一個 form」,答不出下面這四件**這一處才有**的事:

1. **3 支滑桿是不是真的在那個 form 裡** —— 只要 form 包到別的東西(例如只包住 submit 鈕),
   全域表照樣是 6 處、照樣全綠,但**拉桿仍然整頁重跑**,防重繪等於沒做。
2. **key 有沒有變** —— `batch_rot_*` 一旦改名,既有 session 值斷掉;而全域表不看 key。
3. **預設值有沒有從 SSOT 退回 inline 數字** —— §3.3,全域表同樣不看。
4. **Expander 標題的計數會不會與表身打架** —— form 化最容易踩壞的就是這裡
   (計數在 expander **之前**讀 session_state,滑桿在 expander **之內**寫)。
5. **三支滑桿是不是**每一支**都真的驅動結果** —— 2026-08-31 稽核實測:把
   `buy_sigma` / `min_score` 改成直接吃 SSOT 常數(那兩支滑桿變成純裝飾品),
   **全套 127 條全綠**。「form 包好了」不等於「桿子接上了」。
6. **`clear_on_submit` 有沒有被改成 `True`** —— 那會讓每次按「套用門檻」之後三支滑桿
   彈回預設;畫面看起來正常,使用者的門檻卻留不住。同樣是稽核實測的全綠漏網。

## ⚠️ 沙箱驗不到的那一段(誠實揭露,不要讀成「已驗證」)

**`AppTest` 不模擬 form 的「送出前不寫回」語意**(**streamlit 1.59.2 實測**,
量測日 2026-08-31):`slider.set_value(x).run()` 在 form 內外**都會立刻生效**
(本檔 `test_..._is_a_real_form_not_a_container` 的註記即由此而來)。
所以「拉桿不重繪」這個**使用者實際體感**,本檔**驗不到**,只能驗**產生該行為的接線**:
所有 3 支滑桿與 submit 鈕的 `form_id` 都等於同一個 form —— 那是 Streamlit 前端據以
緩衝輸入的唯一依據。**要確認體感請在瀏覽器拉一次滑桿**(③ 基金研究 → 📦 批次掃描 →
跑完 → 展開「🧩 互補配對探索」)。

⚠️ **這是「函式庫在某個版本上的行為」,不是永恆事實** —— 故標版本與量測日。
`requirements.txt` 現行為 `streamlit>=1.59.1,<1.60.0`;**若哪天 AppTest 開始模擬
form 緩衝,本段就過期了**(屆時可以把體感也寫成測試,不必再只驗接線)。
**請現場重驗,不要引用本段當永久事實。**

## 突變自證(2026-08-31 提交前實跑,「拿掉修復必須轉紅」)

  - `with st.form(...)` 改成 `with st.container()` → 本檔 3 條紅 + 全域表 2 條紅
  - form 只包住 submit 鈕、滑桿留在外面 → `test_all_three_sliders_live_inside_the_form` 紅
  - `key="batch_rot_sell"` 改 `key="batch_rot_sell_v2"` → `test_slider_keys_are_unchanged` 紅
  - `ROTATION_SELL_SIGMA` 改寫成 inline `-0.5` → `test_slider_defaults_come_from_ssot` 紅
  - 標題計數改用另一組 key → `test_expander_count_and_table_body_share_one_source` 紅
  - `FORM_SITES` 不登記元件 B → `test_form_site_is_registered_in_the_global_table` 紅

**2026-08-31 稽核回修批新增的四條(前三條是稽核實測「全綠漏網」的突變)**:

  - `buy_sigma=_buy` 改成直接吃 `ROTATION_BUY_SIGMA`(低基期滑桿變裝飾品)
    → `test_applied_thresholds_drive_the_count[batch_rot_buy…]` 紅
  - `min_score=_minsc` 改成直接吃 SSOT 常數(評分滑桿變裝飾品)
    → `test_applied_thresholds_drive_the_count[batch_rot_score…]` 紅
  - `clear_on_submit=False` 改 `True`(每次套用後滑桿彈回預設)
    → `test_form_does_not_clear_on_submit` 紅
  - `_render_bare()` 的 `finally` 收尾拿掉(form 狀態外洩污染整個 pytest 行程)
    → `test_bare_render_leaves_no_form_state_on_the_root_dg` 紅
    (且同行程的 `tests/test_render_smoke.py` 3 條一起紅)

⚠️ **前三條在本批之前是零守衛的** —— 「本檔有幾條測試」與「這些測試守到了什麼」
是兩回事(當時 13 條,三支滑桿只有 `sell` 一支真的被驗證)。
**守的是哪一條參數,要逐條數;數量不是覆蓋率。**
"""
from __future__ import annotations

import ast
import pathlib

import pandas as pd
import pytest
from test_ui_rerun_contract import FORM_SITES

ROOT = pathlib.Path(__file__).resolve().parents[1]
_ROT_REL = "ui/helpers/fund_grp_health/rotation.py"
_ROT = ROOT / _ROT_REL
_FN = "render_complementary_explorer_from_df"

#: 三支滑桿的 key(**不含** key_prefix 拼接 —— 元件 B 是寫死的字面值)與其 SSOT 常數名。
_SLIDER_CONTRACT = {
    "batch_rot_sell": "ROTATION_SELL_SIGMA",
    "batch_rot_buy": "ROTATION_BUY_SIGMA",
    "batch_rot_score": "ROTATION_BUY_MIN_SCORE",
}

_BATCH_DF = pd.DataFrame([
    {"code": "A", "基金名": "A基", "基金類別": "股票型", "4D Grade": "A",
     "σ rank": "-0.20σ", "距 HWM %": "-3%", "操盤評分": 80,
     "吃本金燈號 (1Y · )": "🟢", "ccy": "USD"},
    {"code": "B", "基金名": "B基", "基金類別": "債券型", "4D Grade": "B",
     "σ rank": "-2.00σ", "距 HWM %": "-18%", "操盤評分": 75,
     "吃本金燈號 (1Y · )": "🟡 注意", "ccy": "TWD"},
])


# ────────────────────────── AST 工具 ──────────────────────────
def _fn_node() -> ast.FunctionDef:
    tree = ast.parse(_ROT.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == _FN:
            return node
    raise AssertionError(f"找不到 {_FN} —— 改名請同步本守衛")


def _form_withs(scope: ast.AST) -> list[ast.With]:
    """`with st.form(...):` 的 With 節點(receiver 認 `st` / `col.form` 都算)。"""
    out = []
    for node in ast.walk(scope):
        if isinstance(node, (ast.With, ast.AsyncWith)) and any(
                isinstance(i.context_expr, ast.Call)
                and isinstance(i.context_expr.func, ast.Attribute)
                and i.context_expr.func.attr == "form"
                for i in node.items):
            out.append(node)
    return out


def _slider_calls(scope: ast.AST) -> dict[str, ast.Call]:
    """`key=` 為字面字串的 slider 呼叫 → {key: Call}。"""
    out: dict[str, ast.Call] = {}
    for node in ast.walk(scope):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "slider"):
            for kw in node.keywords:
                if kw.arg == "key" and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str):
                    out[kw.value.value] = node
    return out


# ══════════════════════════════════════════════════════════════
# 1. form 是真的 form,而且 3 支滑桿都住在裡面
# ══════════════════════════════════════════════════════════════
def test_threshold_row_is_a_real_form_not_a_container():
    """門檻列必須是 `st.form` + `form_submit_button`,不是 `st.container` + `st.button`。

    ⚠️ 這正是 2026-08-28 稽核組突變過、**當時全綠**的那一招(見
    `test_ui_rerun_contract.py` 檔頭):把 form 換成 container，畫面幾乎一樣、
    每拉一格卻整頁重跑。
    """
    fn = _fn_node()
    forms = _form_withs(fn)
    assert len(forms) == 1, (
        f"{_FN} 內應有且只有 1 個 `with st.form(...)`(門檻列),實際 {len(forms)} 個 —— "
        "0 個 = 防重繪被拆掉;>1 個 = 版面結構改變,請連同線框與 FORM_SITES 一起確認。")
    has_submit = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "form_submit_button"
        for n in ast.walk(forms[0]))
    assert has_submit, (
        "門檻列的 form 內沒有 `form_submit_button` —— 使用者按不出去,"
        "而且 Streamlit 執行期會直接丟 StreamlitAPIException。")


def test_all_three_sliders_live_inside_the_form():
    """3 支滑桿**全部**要在 form 內。

    ⚠️ 少了這條,「form 只包住 submit 鈕、滑桿留在外面」會全綠通過 —— 全域資產表
    (`FORM_SITES`)只數「有幾個 form」,不看**form 裡裝了什麼**,那種寫法對它是隱形的,
    但對使用者而言防重繪等於沒做。
    """
    fn = _fn_node()
    forms = _form_withs(fn)
    assert forms, "門檻列的 form 不見了(另見上一條)"
    inside = _slider_calls(forms[0])
    outside = {k for k in _slider_calls(fn) if k not in inside}
    missing = sorted(set(_SLIDER_CONTRACT) - set(inside))
    assert not missing, (
        f"下列門檻滑桿**不在** form 內,拉動它們仍會整頁重跑:{missing}")
    assert not outside, (
        f"form 之外還有滑桿:{sorted(outside)} —— 元件 B 的門檻列應全部收在同一個 form。")


def test_form_wiring_is_live_at_runtime():
    """runtime sentinel:3 支滑桿與 submit 鈕的 `form_id` 是**同一個** form。

    `form_id` 是 Streamlit 前端據以「送出前不要 rerun」的唯一依據 —— AST 證明原始碼
    長對了,本條證明它**真的組裝成一個 form**(例如 form 被包在不會執行到的分支裡,
    AST 會綠、本條會紅)。
    ⚠️ 本條**不**證明「拉桿不會重繪」:AppTest 不模擬 form 的送出前緩衝(見檔頭)。
    """
    probe = _run_probe()
    assert not probe["exceptions"], probe["exceptions"]
    ids = {k: v[1] for k, v in probe["sliders"].items()}
    for key in _SLIDER_CONTRACT:
        assert ids.get(key), f"滑桿 {key} 沒有 form_id —— 它不在任何 form 裡"
    assert len(set(ids.values())) == 1, (
        f"3 支滑桿被拆進不同的 form:{ids} —— 應同屬一個門檻列 form")
    submits = [b for b in probe["form_buttons"] if b[1]]
    assert submits, "找不到帶 form_id 的送出鈕 —— 門檻列沒有 form_submit_button"
    assert submits[0][1] == next(iter(ids.values())), (
        "送出鈕與滑桿不屬於同一個 form —— 按了不會套用")


def test_form_does_not_clear_on_submit():
    """`clear_on_submit` 必須是 False —— 按下「套用門檻」不得把滑桿彈回預設值。

    ⚠️ **這條在 2026-08-31 稽核前是零守衛的**:`clear_on_submit` 是本批新寫的參數,
    稽核把它從 `False` 改成 `True`,**127 條測試全綠**。
    那個突變在使用者眼裡是這樣的:拉到 sell=-1.2 → 按「套用門檻」→ 表算對了,
    **但三支滑桿同時彈回 SSOT 預設** → 使用者看到的門檻與表身用的門檻不一致,
    下一次再按就套用回預設(§2.1 兩個數字打架)。**畫面沒壞、行為壞了。**

    本條讀的是 **runtime 的 form proto**(`Block.form.clear_on_submit`),不是原始碼字面 ——
    AST 看得到 `clear_on_submit=False` 這串字,看不到「它有沒有被別的寫法蓋掉」。
    ⚠️ 誠實邊界:AppTest 不模擬送出後的清空行為(同檔頭那段),所以本條驗的是
    **送給前端的那個旗標**,不是**彈回去的體感**。
    """
    forms = _run_form_probe()
    assert len(forms) == 1, f"門檻列應只有 1 個 form,實際 {forms}"
    form_id, clear_on_submit = forms[0]
    assert form_id == "batch_rot_threshold_form", f"form_id 變了:{form_id}"
    assert clear_on_submit is False, (
        "門檻列 form 的 clear_on_submit 是 True —— 每次按「套用門檻」後三支滑桿都會"
        "彈回 SSOT 預設,使用者看到的門檻與表身用的門檻會不一致。")


# ══════════════════════════════════════════════════════════════
# 2. key 沿用 + 預設值走 SSOT
# ══════════════════════════════════════════════════════════════
def test_slider_keys_are_unchanged():
    """form 化**不得**改 key —— 改了等於清空使用者既有的 session 值。

    `batch_rot_*` 這組 key 同時被 Expander 標題的計數讀取(在 expander 之前),
    改名會讓計數永遠退回預設值、與表身脫鉤。
    """
    found = set(_slider_calls(_fn_node()))
    assert found == set(_SLIDER_CONTRACT), (
        f"門檻滑桿的 key 變了:預期 {sorted(_SLIDER_CONTRACT)}、實際 {sorted(found)} —— "
        "既有 session 值會斷掉,且標題計數讀的是舊 key。")


@pytest.mark.parametrize("key,const", sorted(_SLIDER_CONTRACT.items()))
def test_slider_defaults_come_from_ssot(key: str, const: str):
    """預設值必須引用 `shared/signal_thresholds.py` 的常數,不得寫死 inline 數字(§3.3)。

    允許外面包一層轉型(`int(ROTATION_BUY_MIN_SCORE)`)—— 只要那個常數名出現在
    預設值運算式裡就算。**純字面值(如 `-0.5`)一律紅。**
    """
    call = _slider_calls(_fn_node())[key]
    # st.slider(label, min, max, value, step, ...) → 第 4 個位置引數是預設值
    assert len(call.args) >= 4, f"{key} 的 slider 呼叫少了預設值位置引數"
    default_expr = call.args[3]
    names = {n.id for n in ast.walk(default_expr) if isinstance(n, ast.Name)}
    assert const in names, (
        f"{key} 的預設值沒有走 SSOT 常數 {const},而是 "
        f"`{ast.unparse(default_expr)}` —— 畫面上多養一把尺(§3.3)。")


def test_ssot_defaults_are_what_the_user_actually_sees():
    """runtime:首次進頁時 3 支滑桿的值 == SSOT 常數(AST 綠、實際值錯 → 本條紅)。"""
    from shared.signal_thresholds import (
        ROTATION_BUY_MIN_SCORE,
        ROTATION_BUY_SIGMA,
        ROTATION_SELL_SIGMA,
    )
    vals = {k: v[0] for k, v in _run_probe()["sliders"].items()}
    assert vals == {
        "batch_rot_sell": ROTATION_SELL_SIGMA,
        "batch_rot_buy": ROTATION_BUY_SIGMA,
        "batch_rot_score": int(ROTATION_BUY_MIN_SCORE),
    }, f"滑桿實際預設值與 SSOT 不符:{vals}"


# ══════════════════════════════════════════════════════════════
# 3. Expander 標題計數 —— form 化最容易踩壞的地方
# ══════════════════════════════════════════════════════════════
def test_first_load_count_uses_ssot_defaults():
    """首次進頁(session_state 全空)標題計數 = 用 SSOT 預設門檻算出來的數。

    form 化不得改變這件事:計數在 expander **之前**用 `session_state.get(key, SSOT)` 讀,
    首跑 key 還不存在 → 退 SSOT,與 form 前完全相同。
    """
    from services.rotation import rows_from_batch_df, suggest_rotation_pairs
    from shared.signal_thresholds import (
        ROTATION_BUY_MIN_SCORE,
        ROTATION_BUY_SIGMA,
        ROTATION_SELL_SIGMA,
    )
    pairs = suggest_rotation_pairs(
        rows_from_batch_df(_BATCH_DF), sell_sigma=ROTATION_SELL_SIGMA,
        buy_sigma=ROTATION_BUY_SIGMA, min_score=float(ROTATION_BUY_MIN_SCORE))
    n_ok = sum(1 for p in pairs if p.get("buy_code"))
    labels = _run_probe()["expanders"]
    assert labels == [f"🧩 互補配對探索（{n_ok} 對可換 / {len(pairs)} 檔高基期）"], (
        f"首屏標題計數與 SSOT 預設門檻算出的結果不符:{labels}")


#: (session key, 已套用的值, 預期「N 對可換」, 預期「N 檔高基期」)。
#: **三支滑桿各自都要有 case** —— 理由見 `test_applied_thresholds_drive_the_count`。
#: 用 `_BATCH_DF` 實算(2026-08-31):SSOT 預設 `(-0.5, -1.5, 50)` → **(1, 1)**;
#: `sell=-2.0` → (0, 2)、`sell=0.4` → (0, 0)、`buy=-3.0` → (0, 1)、`score=80` → (0, 1)。
#: 四個 case 算出來的「對可換」都與預設的 1 不同 → 任何「忽略 session、直接吃 SSOT
#: 常數」的突變都會被抓到。
#: ⚠️ **每個值都必須是使用者拉得到的**(在該滑桿的 min/max/step 上),
#: 由 `test_applied_threshold_cases_are_reachable_through_the_widget` 機械驗證,
#: 不靠這裡的註解自我保證 —— 理由見那條的 docstring(這是同一個陷阱的第四次現身)。
_APPLIED_THRESHOLD_CASES = [
    ("batch_rot_sell", -2.0, 0, 2),
    ("batch_rot_sell", 0.4, 0, 0),
    ("batch_rot_buy", -3.0, 0, 1),
    ("batch_rot_score", 80, 0, 1),
]


@pytest.mark.parametrize("key,applied,expect_ok,expect_high", _APPLIED_THRESHOLD_CASES)
def test_applied_thresholds_drive_the_count(key: str, applied: float,
                                            expect_ok: int, expect_high: int,
                                            monkeypatch: pytest.MonkeyPatch):
    """套用後的門檻真的驅動標題計數(不是永遠印 SSOT 那一組數字)—— **三支滑桿都要驗**。

    把「已套用」狀態放進 `session_state`,驗計數跟著走:
    `sell=0.4` 把唯一的高基期標的濾掉 → 0 檔;`sell=-2.0` 放寬到連 B 也算高基期 → 2 檔
    (但已無別類健康低基期可配 → 0 對);`buy=-3.0` 收緊到 B 不再算低基期 → 配不出來;
    `score=80` 把評分 75 的 B 擋在健康過濾外 → 同樣配不出來。

    ⚠️ **為什麼三支都要有 case(2026-08-31 稽核實測,不是形式主義)**:先前只驗 `sell`,
    稽核把 production 的 `buy_sigma=_buy` / `min_score=_minsc` 分別改成**直接吃 SSOT 常數**
    (＝那兩支滑桿變成純裝飾品,拉了完全沒用),**127 條測試全綠**。
    **「有守衛」不等於「守到了」—— 守的是哪一條參數要逐條數。**

    ⚠️ **測資怎麼選,是這條有沒有守護力的關鍵**(同一個陷阱已現身四次,逐次寫下來):
    1. 初版用 `sell=-0.5`,那**就是 SSOT 預設值** —— 在「標題改讀別的 key」的突變下
       **仍然綠**(讀錯 key → 退回預設,剛好等於測資)。**套套邏輯。**
    2. 改 `-1.0` 後雖已非預設值,但實算與 `-0.5` **算出來的數字相同**(都是 1 對 / 1 檔)
       → 同一個突變**還是綠**。**「值不同」不等於「結果不同」。**
    3. 改 `-2.5` 後兩個數字都不同了,突變確實轉紅 —— 但 `-2.5` **在滑桿範圍之外**
       (該滑桿是 `-2.0 .. 0.5`),使用者根本拉不到;而本條的 docstring 卻宣稱它
       「＝使用者按過『套用門檻』之後的狀態」。**那句話對 -2.5 不成立。**
       (實測:AppTest `set_value(-2.5)` 被**靜默拒絕**,session 仍是 -0.5。)
       → 現行改用 `-2.0`(滑桿下界,拉得到),實算同為 (0, 2),**鑑別力完全相同**。
    4. 第三種變形因此是:**測資用了一個使用者到不了的狀態,還宣稱那是使用者的狀態。**
       前兩次的病徵是「突變照樣綠」——**看得見**,一跑突變就露餡;
       這次的病徵是「突變確實轉紅」——**看不見**,因為所有訊號都正常
       (測試綠、突變紅),沒有任何一個數字會告訴你「這個狀態使用者根本拉不到」。
       **守衛有力,但它守的前提是假的**,所以它守的其實是別的東西。
       **認法**:凡是把值塞進 `session_state` 就宣稱「這是使用者的狀態」的測試,
       都要回頭對一次那個 widget 的 min/max/step ——
       現在這件事由下一條 `..._reachable_through_the_widget` 機械化了,不再靠人記得。
    """
    import streamlit as st
    seen: dict = {}
    monkeypatch.setattr(st, "expander", _fake_expander(seen))
    monkeypatch.setitem(st.session_state, key, applied)
    _render_bare()
    assert seen["label"] == (f"🧩 互補配對探索（{expect_ok} 對可換 / "
                             f"{expect_high} 檔高基期）"), seen["label"]


@pytest.mark.parametrize("key,applied,expect_ok,expect_high", _APPLIED_THRESHOLD_CASES)
def test_applied_threshold_cases_are_reachable_through_the_widget(
        key: str, applied: float, expect_ok: int, expect_high: int):
    """上一條的每個「已套用值」都必須是**使用者真的拉得到**的,而且真的驅動畫面。

    上一條走的是 `monkeypatch.setitem(session_state, ...)` —— **繞過了 widget**,
    所以它驗不出「這個值根本不在滑桿範圍內」。本條改用 AppTest **實際操作滑桿**,
    一次驗兩件事:

    1. **可達性**:`set_value(x)` 之後 `session_state[key]` 真的等於 `x`。
       (streamlit 對超界值是**靜默拒絕**、不報錯 —— 這正是 `-2.5` 那次沒被發現的原因。)
    2. **端到端**:透過真 widget 套用之後,Expander 標題的數字與上一條相同 ——
       也就是「這支滑桿真的驅動結果」,而不是只有「session_state 真的驅動結果」。

    ⚠️ 本條**不**證明「送出前不會重繪」:AppTest 不模擬 form 的送出前緩衝(見檔頭);
    它證明的是**滑桿→結果**這條線是通的。
    """
    got = _run_applied_probe()[f"{key}={applied}"]
    assert got["session"] == applied, (
        f"滑桿 {key} 設成 {applied} 之後,session_state 卻是 {got['session']} —— "
        f"該值不在此滑桿的 min/max/step 上,streamlit 靜默拒絕了它。"
        "測資必須是使用者拉得到的值(見上一條 docstring 第 3、4 點)。")
    _want = f"🧩 互補配對探索（{expect_ok} 對可換 / {expect_high} 檔高基期）"
    assert got["expanders"] == [_want], (
        f"透過真 widget 套用 {key}={applied} 後,標題計數是 {got['expanders']} —— "
        f"與 session_state 路徑算出的 ({expect_ok}, {expect_high}) 不一致,"
        "表示這支滑桿沒有真的接到計算上。")


def test_expander_count_and_table_body_share_one_source(monkeypatch: pytest.MonkeyPatch):
    """標題計數與**表身收到的配對**必須同源 —— 兩個數字不准打架(§2.1)。

    這是 form 化的真正風險點:標題在 expander **外**讀 session_state,滑桿在 expander
    **內**寫。若哪天有人把標題改讀「滑桿的回傳值」,送出前後就會出現
    「標題已經變了、表還是舊的」。本條把兩邊綁在一起。
    """
    import streamlit as st

    import ui.helpers.fund_grp_health.rotation as UIR

    seen: dict = {}
    monkeypatch.setattr(st, "expander", _fake_expander(seen))
    monkeypatch.setattr(
        UIR, "_render_pairs_body",
        lambda rows, pairs, sell, buy, *, key_prefix, offer_download:
            seen.update(body_pairs=len(pairs),
                        body_ok=sum(1 for p in pairs if p.get("buy_code")),
                        body_sell=sell))
    # ⚠️ 刻意用**非 SSOT 預設**的 -1.0(預設是 -0.5):若表身其實是拿 SSOT 常數
    # 而不是「已套用」的 session 值,用預設值當測資會**驗不出來**(兩者剛好相等)。
    monkeypatch.setitem(st.session_state, "batch_rot_sell", -1.0)
    _render_bare()
    assert seen["label"] == (f"🧩 互補配對探索（{seen['body_ok']} 對可換 / "
                             f"{seen['body_pairs']} 檔高基期）"), (
        f"標題計數與表身不同源:標題 {seen['label']!r}、"
        f"表身 {seen['body_ok']}/{seen['body_pairs']}")
    assert seen["body_sell"] == -1.0, (
        f"表身收到的門檻是 {seen['body_sell']},不是 session_state 內『已套用』的 -1.0 —— "
        "送出前後會出現兩套門檻(標題一套、表一套)")


# ══════════════════════════════════════════════════════════════
# 4. 測試行程衛生 —— form 化的連帶損害,不是預防性設計
# ══════════════════════════════════════════════════════════════
def test_bare_render_leaves_no_form_state_on_the_root_dg():
    """bare 渲染元件 B 之後,`st._main._form_data` **必須**回到 None。

    這條守的是**別人的測試**,不是本檔自己的:`st._main` 是模組級單例,bare 模式下
    `with st.form(...)` 的殘留會活過整個 pytest 行程,讓**之後**任何用 AppTest 且畫面
    上有 `st.button` 的測試炸掉(實測:`tests/test_render_smoke.py` 3 條紅)。

    ⚠️ **為什麼需要一條測試,而不是「加了 finally 就好」**:這個病的症狀出現在
    **另一個檔案**、而且**只在特定執行順序下**出現 —— 也就是說,把 `finally` 拿掉
    之後,本檔自己**照樣全綠**,CI 也可能因為字母序剛好而全綠。**沒有這條,那行
    `finally` 是一段沒有守衛的修復,下一個人整理程式碼時可以無聲刪掉它。**

    突變自證(2026-08-31 實跑):拿掉 `_render_bare` 的 `finally` 那行 → 本條轉紅
    (assert 收到 `FormData(form_id='batch_rot_threshold_form')`)。
    """
    import streamlit as st
    _reset_form_state()          # 先歸零,免得被同行程更早的測試影響、驗到假綠
    _render_bare()
    assert getattr(st._main, "_form_data", None) is None, (
        f"bare 渲染後根 DG 仍殘留 form 狀態:{st._main._form_data!r} —— "
        "同一個 pytest 行程內,後續任何 AppTest 畫面上的 st.button 都會被誤判成"
        "「在 form 內」而丟 StreamlitAPIException(見 _render_bare docstring)。")


# ══════════════════════════════════════════════════════════════
# 5. 與全域資產表對接
# ══════════════════════════════════════════════════════════════
def test_form_site_is_registered_in_the_global_table():
    """新增的 form 必須登記進 `FORM_SITES`,否則下一個人可以無聲拆掉它。

    ⚠️ 這條與 `test_ui_rerun_contract.py` 的雙向 `==` **不重複**:那邊比對的是
    「掃到的」vs「表上的」,兩邊一起被刪就會一起綠;本條釘死**這一處**必須在表上。
    """
    assert f"{_ROT_REL}::{_FN}()×1" in FORM_SITES, (
        f"`{_ROT_REL}::{_FN}()×1` 沒有登記在 FORM_SITES —— "
        "鐵律 2 的資產登記漏了元件 B。")


# ────────────────────────── helpers ──────────────────────────
def _fake_expander(sink: dict):
    """記下 expander 標題並回傳一個什麼都不做的 context manager。"""
    import contextlib

    def _exp(label, *a, **kw):
        sink["label"] = label
        return contextlib.nullcontext()
    return _exp


def _render_bare() -> None:
    """bare 模式直接呼叫元件 B(widget 回傳預設值,不需要 AppTest)。

    ⚠️ **收尾的 `finally` 不是防禦性程式碼,是修一個實測到的行程污染**
    (2026-08-31 稽核抓到,streamlit 1.59.2 實測):

    元件 B 現在含 `with st.form(...)`。bare 模式(無 ScriptRunContext)下離開該 with
    區塊時,dg_stack 雖然彈回深度 1,**根 DG(`st._main`)卻被就地留下 `_form_data`**,
    而它是**模組級單例**、活過整個 pytest 行程。實測:

        before bare render   dg_stack depth=1 form_ids=[None]
        after  bare render   dg_stack depth=1 form_ids=['batch_rot_threshold_form']

    後果:同一行程內**之後**任何用 AppTest 渲染的測試,只要畫面上有 `st.button`,
    都會被 streamlit 判成「按鈕長在 form 裡」而丟
    `StreamlitAPIException: st.button() can't be used in an st.form().`
    實測 `pytest tests/test_rotation_form_rerun_20260831.py tests/test_render_smoke.py`
    → `test_render_smoke.py` **3 條紅**(踩到 `ui/tab1_macro.py` 與
    `ui/tab5_data_guard.py` 的 `st.button`)。

    ⚠️ **之前全綠純屬巧合,不是設計 —— 而且是「兩層巧合」疊在一起**(2026-08-31 實測):

    1. **本機跑整套(不帶 `-m`)靠的是字母序**:`test_render_smoke`(ren)恰好排在
       `test_rotation_*`(rot)**之前**,受害者先跑完才被污染。
    2. **CI 兩條 lane 靠的是 marker 分流**:`TestRenderSmoke` 掛 `@pytest.mark.slow`,
       而本檔與 `test_rotation_components_ui_*` **沒有** slow marker →
       fast lane(`-m "not slow"`)把受害者剔掉、slow lane(`-m "slow"`)把污染源剔掉,
       **兩者在 CI 上根本沒碰過面**。

    也就是說 CI 綠燈**完全沒有覆蓋到這條路徑**,它不是「驗過沒事」而是「沒驗到」。
    ①隨機序、②只跑子集、③日後新增一個排序在 `test_rot*` 之後又用 AppTest 的測試檔、
    ④哪天有人把 marker 調一調 —— 任一即紅。
    **靠檔名字母序或 marker 分流當隔離,都是假的隔離。**

    修法沿用本 repo 既有先例 `tests/test_app_smoke.py`
    (v19.176,同一個病:app.py bare 跑 module body 後殘留 `_form_data`)。
    ⚠️ 抄那段時**不要**連 `_active_dg = _main_dg` 一起抄 —— streamlit 1.59.2 上
    `_active_dg` 已是**無 setter 的 property**,寫它會拋
    `AttributeError: property '_active_dg' ... has no setter`
    (v19.176 原處是被它自己的 `try/except` 吞掉才沒出事,不是那行有效)。
    ⚠️ 這是**版本相依行為**,不是永恆事實;請現場重驗,不要引用本段當永久事實。
    """
    from ui.helpers.fund_grp_health.rotation import (
        render_complementary_explorer_from_df,
    )
    try:
        render_complementary_explorer_from_df(_BATCH_DF)
    finally:
        # 例外路徑也要清 —— 渲染中途爆掉時殘留最嚴重(with 沒走完)。
        _reset_form_state()


def _reset_form_state() -> None:
    """把根 DeltaGenerator 的 form 殘留清掉(理由見 `_render_bare` docstring)。"""
    import streamlit as st
    _main = getattr(st, "_main", None)
    if _main is not None:
        _main._form_data = None


#: 在**乾淨子行程**裡用 AppTest 渲染元件 B,把要驗的東西印成 JSON。
#: ⚠️ 為什麼要開子行程,而不是直接在測試行程內跑 AppTest(實測,不是預防性設計):
#: 只要**同一個行程**裡先有任何一次「bare 模式呼叫含 `st.form` 的元件」
#: (本檔自己的 `_render_bare()`、或 `test_rotation_components_ui_20260831.py::
#: test_explorer_routes_through_l2_and_shared_body`),後續的 `AppTest` 就會拿到
#: `StreamlitAPIException: Forms cannot be nested in other forms.` ——
#: bare 模式沒有 ScriptRunContext,form 的容器狀態會殘留到之後的 AppTest。
#: 實測:單跑本檔全綠,與上述任一測試同行程就紅,**且順序反過來就好**。
#: ~~⚠️ 本 repo **目前沒有** `pytest-randomly`(2026-08-31 實測:`requirements-dev.txt` /~~
#: ~~CI 設定 / `conftest.py` 皆無,**環境亦未安裝**)。~~
#: ⚠️ **2026-08-31 更正 —— 有意識的更正,不是漏刪 · 決策者:AI 總管。**
#: 上面那句是**四個分句,前三個為真、第四個為假**:
#:   - ✅ `requirements-dev.txt` / CI 設定 / `conftest.py` 皆**未宣告** `pytest-randomly`
#:     (2026-08-31 複驗仍為 0 命中)。
#:   - ❌ 「**環境亦未安裝**」**為假**:實測 `pip show pytest-randomly` → **4.1.0**,
#:     dist-info mtime **2026-08-31T11:44:19Z** —— 由**另一個 agent** 裝進這個共用沙箱,
#:     時間早於本分支後兩個 commit。寫下那句時它就已經在了。
#: **這句錯誤的源頭是 AI 總管,不是實作組**:上一輪總管告訴實作組「本 repo 沒裝這個
#: plugin,該失敗會是穩定的而非間歇」——**前半對、後半錯**,而後半正是被抄進註解的那句。
#: 據實記錄來源,不把它記成實作組的疏失。
#: **現行(誠實版本)**:repo 未宣告 → **CI 上是字母序**;共用沙箱已裝 4.1.0 →
#: **本地跑會是隨機序**。兩種情況都得靠子行程解決,故結論(用乾淨子行程)不變。
#: ⚠️ **而那個假設本身遮蔽了一個真缺陷**:正因為以為「不會隨機」,才沒人去跑隨機序;
#: **隨機序正是抓到本檔行程污染(見 `_render_bare`)的方式** ——
#: 若當初照那句話信下去,CI 會一路綠到某天有人加了一個排序在 `test_rot*` 之後的
#: AppTest 測試檔為止。**一句未查證的環境宣稱,擋掉的是一次會抓到真 bug 的驗證。**
#: 這是測試框架的產物,**與 production 無關**(production 永遠有 ScriptRunContext)。
_PROBE_SRC = '''
import json, sys
sys.path.insert(0, {root!r})
import pandas as pd
from streamlit.testing.v1 import AppTest

_SRC = """
import sys
sys.path.insert(0, {root!r})
import pandas as pd
from ui.helpers.fund_grp_health.rotation import render_complementary_explorer_from_df
render_complementary_explorer_from_df(pd.DataFrame({records!r}))
"""
at = AppTest.from_string(_SRC, default_timeout=60).run()
print("@@PROBE@@" + json.dumps({{
    "exceptions": [e.value for e in at.exception],
    "expanders": [e.label for e in at.expander],
    "sliders": {{s.key: [s.value, s.proto.form_id] for s in at.slider}},
    "form_buttons": [[b.label, b.proto.form_id] for b in at.button],
}}, ensure_ascii=False))
'''


#: 「實際操作滑桿」探針:每個 case 開一個乾淨 AppTest、拉那支滑桿、記錄
#: session 值與 Expander 標題。與 `_PROBE_SRC` 分開是因為它要跑 N+1 次 AppTest。
_APPLIED_PROBE_SRC = '''
import json, sys
sys.path.insert(0, {root!r})
import pandas as pd
from streamlit.testing.v1 import AppTest

_SRC = """
import sys
sys.path.insert(0, {root!r})
import pandas as pd
from ui.helpers.fund_grp_health.rotation import render_complementary_explorer_from_df
render_complementary_explorer_from_df(pd.DataFrame({records!r}))
"""

def _forms(at):
    """走訪 element tree 撈出 Block.form 的 proto(AppTest 沒有 at.form 這個 accessor)。"""
    out = []
    def _walk(n):
        p = getattr(n, "proto", None)
        if p is not None and type(p).__name__ == "Block":
            try:
                if p.WhichOneof("type") == "form":
                    out.append([p.form.form_id, p.form.clear_on_submit])
            except Exception:
                pass
        ch = getattr(n, "children", None) or []
        for c in (ch.values() if isinstance(ch, dict) else ch):
            _walk(c)
    _walk(at.main)
    return out

res = {{"forms": _forms(AppTest.from_string(_SRC, default_timeout=60).run()), "applied": {{}}}}
for _key, _val in {cases!r}:
    _at = AppTest.from_string(_SRC, default_timeout=60).run()
    _w = [s for s in _at.slider if s.key == _key][0]
    _at2 = _w.set_value(_val).run()
    res["applied"]["%s=%s" % (_key, _val)] = {{
        "session": _at2.session_state[_key],
        "expanders": [e.label for e in _at2.expander],
        "exceptions": [e.value for e in _at2.exception],
    }}
print("@@PROBE@@" + json.dumps(res, ensure_ascii=False))
'''

#: 子行程探針很慢(每個 AppTest 約 1 秒),同一個 pytest 行程內只跑一次。
_PROBE_CACHE: dict = {}


def _spawn(src: str) -> dict:
    """跑一個探針子行程,回傳它印出的 JSON。"""
    import json
    import subprocess
    import sys

    # check=False:子行程非 0 也要往下走 —— 下面的 assert 會把 stdout/stderr 一起印出來,
    # 比 CalledProcessError 的空訊息好讀。
    proc = subprocess.run([sys.executable, "-c", src], capture_output=True,
                          text=True, timeout=600, cwd=str(ROOT), check=False)
    marker = [ln for ln in proc.stdout.splitlines() if ln.startswith("@@PROBE@@")]
    assert marker, (
        "AppTest 探針子行程沒有產出結果 —— "
        f"returncode={proc.returncode}\nstdout:\n{proc.stdout[-2000:]}"
        f"\nstderr:\n{proc.stderr[-2000:]}")
    return json.loads(marker[-1][len("@@PROBE@@"):])


def _run_probe() -> dict:
    """在乾淨子行程裡跑 AppTest,回傳 JSON 結果(理由見 `_PROBE_SRC` 上方註)。"""
    if "base" not in _PROBE_CACHE:
        _PROBE_CACHE["base"] = _spawn(
            _PROBE_SRC.format(root=str(ROOT), records=_BATCH_DF.to_dict("records")))
    return _PROBE_CACHE["base"]


def _run_applied_probe() -> dict:
    """`{key}={value}` → 實際拉過該滑桿之後的 session 值與 Expander 標題。"""
    if "applied" not in _PROBE_CACHE:
        _PROBE_CACHE["applied"] = _spawn(_APPLIED_PROBE_SRC.format(
            root=str(ROOT), records=_BATCH_DF.to_dict("records"),
            cases=[(k, v) for k, v, _o, _h in _APPLIED_THRESHOLD_CASES]))
    probe = _PROBE_CACHE["applied"]
    for _k, _v in probe["applied"].items():
        assert not _v["exceptions"], f"{_k}: {_v['exceptions']}"
    return probe["applied"]


def _run_form_probe() -> list:
    """門檻列 form 的 `[form_id, clear_on_submit]`(與 applied 探針同一個子行程)。"""
    if "applied" not in _PROBE_CACHE:
        _run_applied_probe()
    return _PROBE_CACHE["applied"]["forms"]
