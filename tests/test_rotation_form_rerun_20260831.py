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


#: (已套用的 sell 門檻, 預期「N 對可換」, 預期「N 檔高基期」)。
#: ⚠️ **兩個 case 都刻意選成「算出來的數字與 SSOT 預設不同」**,理由見下方 docstring。
#: 用 `_BATCH_DF` 實算:預設 `-0.5` → (1, 1);`-2.5` → (0, 2);`0.4` → (0, 0)。
_APPLIED_THRESHOLD_CASES = [(-2.5, 0, 2), (0.4, 0, 0)]


@pytest.mark.parametrize("sell,expect_ok,expect_high", _APPLIED_THRESHOLD_CASES)
def test_applied_thresholds_drive_the_count(sell: float, expect_ok: int,
                                            expect_high: int,
                                            monkeypatch: pytest.MonkeyPatch):
    """套用後的門檻真的驅動標題計數(不是永遠印 SSOT 那一組數字)。

    直接把「已套用」狀態放進 `session_state`(＝ 使用者按過「套用門檻」之後的狀態),
    驗計數跟著走:`sell=0.4` 把唯一的高基期標的濾掉 → 0 檔;
    `sell=-2.5` 放寬到連 B 也算高基期 → 2 檔(但 B 之外已無別類健康低基期可配 → 0 對可換)。

    ⚠️ **測資怎麼選,是這條有沒有守護力的關鍵**(踩過兩次,寫下來):
    1. 初版用 `sell=-0.5`,那**就是 SSOT 預設值** —— 稽核實測:在「標題改讀別的 key」
       的突變下它**仍然綠**(讀錯 key → 退回預設 -0.5,剛好等於測資)。**套套邏輯。**
    2. 依稽核建議改 `-1.0` 後雖已非預設值,但實算 `-1.0` 與 `-0.5` **算出來的數字相同**
       (都是 1 對 / 1 檔)→ 遇到同一個突變**還是綠**。**「值不同」不等於「結果不同」。**
    → 現行改用 `-2.5`(0 對 / 2 檔),與預設的 (1, 1) **在兩個數字上都不同**,
    突變一改讀別的 key 就會轉紅。**與本檔 M7 是同一個陷阱的第三次現身。**
    """
    import streamlit as st
    seen: dict = {}
    monkeypatch.setattr(st, "expander", _fake_expander(seen))
    monkeypatch.setitem(st.session_state, "batch_rot_sell", sell)
    _render_bare()
    assert seen["label"] == (f"🧩 互補配對探索（{expect_ok} 對可換 / "
                             f"{expect_high} 檔高基期）"), seen["label"]


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
# 4. 與全域資產表對接
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
    """bare 模式直接呼叫元件 B(widget 回傳預設值,不需要 AppTest)。"""
    from ui.helpers.fund_grp_health.rotation import (
        render_complementary_explorer_from_df,
    )
    render_complementary_explorer_from_df(_BATCH_DF)


#: 在**乾淨子行程**裡用 AppTest 渲染元件 B,把要驗的東西印成 JSON。
#: ⚠️ 為什麼要開子行程,而不是直接在測試行程內跑 AppTest(實測,不是預防性設計):
#: 只要**同一個行程**裡先有任何一次「bare 模式呼叫含 `st.form` 的元件」
#: (本檔自己的 `_render_bare()`、或 `test_rotation_components_ui_20260831.py::
#: test_explorer_routes_through_l2_and_shared_body`),後續的 `AppTest` 就會拿到
#: `StreamlitAPIException: Forms cannot be nested in other forms.` ——
#: bare 模式沒有 ScriptRunContext,form 的容器狀態會殘留到之後的 AppTest。
#: 實測:單跑本檔全綠,與上述任一測試同行程就紅,**且順序反過來就好**。
#: ⚠️ 本 repo **目前沒有** `pytest-randomly`(2026-08-31 實測:`requirements-dev.txt` /
#: CI 設定 / `conftest.py` 皆無,環境亦未安裝)。在 pytest 預設的**字母序**下,
#: `test_rotation_components_ui…` 排在 `test_rotation_form_rerun…` **之前**
#: → in-process 寫法會是**穩定紅燈,不是間歇**;若日後導入隨機序才會變成間歇性紅燈。
#: **兩種情況都得靠子行程解決**,故本作法與有沒有 randomly 無關。
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


def _run_probe() -> dict:
    """在乾淨子行程裡跑 AppTest,回傳 JSON 結果(理由見 `_PROBE_SRC` 上方註)。"""
    import json
    import subprocess
    import sys

    src = _PROBE_SRC.format(root=str(ROOT), records=_BATCH_DF.to_dict("records"))
    # check=False:子行程非 0 也要往下走 —— 下面的 assert 會把 stdout/stderr 一起印出來,
    # 比 CalledProcessError 的空訊息好讀。
    proc = subprocess.run([sys.executable, "-c", src], capture_output=True,
                          text=True, timeout=300, cwd=str(ROOT), check=False)
    marker = [ln for ln in proc.stdout.splitlines() if ln.startswith("@@PROBE@@")]
    assert marker, (
        "AppTest 探針子行程沒有產出結果 —— "
        f"returncode={proc.returncode}\nstdout:\n{proc.stdout[-2000:]}"
        f"\nstderr:\n{proc.stderr[-2000:]}")
    return json.loads(marker[-1][len("@@PROBE@@"):])
