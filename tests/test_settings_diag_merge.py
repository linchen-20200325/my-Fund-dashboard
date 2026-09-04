"""⑤ 設定與診斷（管理室 + 資料診斷 + 說明書）合併頁的守衛（WP-E）。

線框（客戶已拍板）：`docs/wireframes/fund-wireframe-final.html` §03「⑤ ⚙️ 設定與診斷」。

## 為什麼這一組測試長這樣（方法先講清楚）

沿用 `tests/test_fund_research_merge.py`（WP-C）的兩把尺，**不用純字串 grep**
（本 repo 已實證字串守衛會被檔案自己的說明文字騙過）：

1. **sentinel（行為）**：把底層換成記錄器，跑一次渲染，驗「有沒有真的被呼叫」。
   —— 用在「旗標全空 ⇒ 三個舊分頁行為不變」「保單管理預設不渲染」
   「診斷區不准在 gate 之前載入」這幾條最貴的規則上。
2. **AST（結構）**：驗某個呼叫是不是**真的**被包在某個條件式底下、**且極性正確**
   （只認「⑤ **沒**持有時才畫」的分支 —— WP-C 第三方複驗實證過：極性反轉會讓
   舊入口無聲少掉標題，而全部既有測試照樣綠燈）。

## 每一條的突變實驗（拿掉約束必須轉紅）寫在各自的 docstring 裡。
"""
from __future__ import annotations

import ast
import contextlib
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


# ══════════════════════════════════════════════════════════════════
# 假 streamlit：讓 render 函式可以在 fast lane 裡跑完（不需 AppTest）
# ══════════════════════════════════════════════════════════════════
class _Rec:
    """記錄這一次渲染送出了什麼。只記形狀，不做逐字斷言。"""

    def __init__(self) -> None:
        self.calls: list[tuple] = []          # (api, first_arg)
        self.session: dict = {}

    def api(self, name: str):
        def _f(*a, **k):
            self.calls.append((name, a[0] if a else None))
            return None
        return _f

    def names(self) -> list[str]:
        return [n for n, _ in self.calls]

    def args_of(self, name: str) -> list:
        return [a for n, a in self.calls if n == name]


class _Col:
    """`st.columns()` / `st.container()` / `st.spinner()` 回傳的東西 —— 它**同時**是
    context manager 與一個可以直接呼叫 widget 的物件（`_c1.button(...)`）。

    ⚠️ **不能只做 `__enter__/__exit__`**（2026-09-03 獨立稽核抓到，這裡原本就是只有兩個）：
    本 repo 大量用 `_act_c1.button(...)` / `_c1.metric(...)` 這種**在欄物件上直接呼叫**的
    寫法，少了 `__getattr__` 會在半路 `AttributeError` 而不是走完渲染。

    **它造成的不是「少畫幾個 widget」，是「斷言在一個根本沒跑完的渲染上做出來」**，
    而且**紅在一個與斷言無關的理由上**：
    `_render_maintain_section()` → `render_nav_manual_section()` →
    `render_nav_csv_manage_section()` → `_act_c1.button("🔄 從 MoneyDJ 增量更新", ...)`
    → `AttributeError` → 被 `safe_section` 接住 → `system_error()` **畫出紅框** →
    `test_policy_admin_is_off_by_default` 與 `test_diag_section_is_not_loaded_before_the_gate`
    這兩條「`assert "error" not in rec.names()`」當場轉紅。

    ⚠️ **它是環境相依的，CI 綠不代表沒事**：那一段要 `cache/nav_history/` 底下**有檔**
    才走得到（`_nh_codes()` 空 → 提前 return）。fresh checkout 的 CI 永遠是空的，
    **但任何在本機用過 App 的人都會踩到**。實測：同樣種一個
    `cache/nav_history/*.json`，`main`(2353dde) `25 passed`／本批修復前 `2 failed`。
    ⚠️ `cache/*` 在 `.gitignore` 內 → **`git status` 看不見它，證明不了工作區乾淨**。

    📌 本類的 `__getattr__` 與回傳值語意**照抄同批的
    `tests/test_ia_tab5_nav_history_merge.py::_Ctx`** —— 那個檔的 docstring 早就寫了
    這條教訓，只是**同一把尺沒有往內用到隔壁檔**（憲法 §8.2.A.1 驗證段 ④ 記載的形狀）。
    """

    def __init__(self, rec: "_Rec" = None) -> None:
        self._rec = rec

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    #: 欄／容器上直接呼叫的 widget 要回什麼。**回 `None` 不夠** ——
    #: `st.text_input(...)` 的呼叫端常接 `.strip()`，回 `None` 只是把
    #: `AttributeError` 換一個地方發作。
    @staticmethod
    def _ret_for(name: str):
        if name in ("button", "download_button", "form_submit_button", "checkbox",
                    "toggle"):
            return False
        if name in ("text_input", "text_area"):
            return ""
        if name in ("file_uploader", "selectbox", "multiselect", "date_input"):
            return None
        return None

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        _rec = self.__dict__.get("_rec")
        _ret = self._ret_for(name)
        if name in ("container", "expander", "spinner", "form", "status", "popover",
                    "columns", "tabs"):
            def _ctx(*a, **k):
                if _rec is not None:
                    _rec.calls.append((name, a[0] if a else None))
                if name == "columns":
                    _spec = a[0] if a else 1
                    return [_Col(_rec) for _ in range(
                        _spec if isinstance(_spec, int) else len(_spec))]
                if name == "tabs":
                    return [_Col(_rec) for _ in range(len(a[0]) if a else 1)]
                return _Col(_rec)
            return _ctx

        def _f(*a, **k):
            if _rec is not None:
                _rec.calls.append((name, a[0] if a else None))
            return _ret
        return _f


@contextlib.contextmanager
def _fake_streamlit(monkeypatch, *, checkbox: bool = False):
    """把 `streamlit` 模組上會用到的 API 換成受控的假貨。

    ⚠️ patch 的是 **`streamlit` 模組物件本身**，所以
    `ui/tab_settings_diag.py`、`ui/helpers/settings_diag/*.py` 與
    `ui/helpers/render_state.py` 的 `import streamlit as st` 全部吃到同一份。
    """
    import streamlit as st

    rec = _Rec()
    for _n in ("markdown", "caption", "info", "success", "warning", "error",
               "divider", "write", "metric", "dataframe", "subheader",
               "header", "code"):
        monkeypatch.setattr(st, _n, rec.api(_n), raising=False)
    monkeypatch.setattr(st, "columns", lambda spec, **k: [_Col(rec) for _ in range(
        spec if isinstance(spec, int) else len(spec))], raising=False)
    monkeypatch.setattr(st, "container", lambda *a, **k: _Col(rec), raising=False)
    monkeypatch.setattr(st, "spinner", lambda *a, **k: _Col(rec), raising=False)
    monkeypatch.setattr(st, "session_state", rec.session, raising=False)

    def _checkbox(*a, **k):
        rec.calls.append(("checkbox", a[0] if a else None))
        return checkbox

    monkeypatch.setattr(st, "checkbox", _checkbox, raising=False)
    try:
        yield rec
    finally:
        # ⚠️ 這個 `finally` **不是防禦性程式碼，是修一個實測到的行程污染**
        # （2026-09-04 抓到，streamlit 1.59.2 實測）。
        #
        # 本檔的 bare 渲染會走進一個 `st.form(...)`。實測呼叫鏈（不是推論，
        # 是在 `st.form` 上掛 traceback 印出來的）：
        #     tests/test_settings_diag_merge.py（`with _fake_streamlit(...)` 內）
        #       → ui/tab_settings_diag.py::render_settings_diag_tab
        #       → ui/helpers/render_state.py::safe_section
        #       → ui/tab_settings_diag.py::_render_maintain_section
        #       → ui/helpers/settings_diag/nav_history_section.py::render_nav_manual_section
        #       → ui/tab_manage.py::render_nav_csv_manage_section
        #       → ui/helpers/ia/gated_form.py::applied_form("_nh_upload_csv_form", ...)
        # ⚠️ `stub_sections` 擋不住它 —— 那個 fixture 換掉的是 `render_manage_tab`，
        # 而這條路徑走的是同檔**另一個**符號 `render_nav_csv_manage_section`。
        #
        # bare 模式（無 ScriptRunContext）離開 `with st.form(...)` 之後，根
        # DeltaGenerator（`st._main`，**模組級單例**）會被就地留下 `_form_data`，
        # 而它**活過整個 pytest 行程** → 之後任何用 AppTest 且畫面上有 `st.button`
        # 的測試，都會被 streamlit 判成「按鈕長在 form 裡」而丟
        # `StreamlitAPIException: st.button() can't be used in an st.form().`
        #
        # 實測受害者（2026-09-04）：`tests/test_app_apptest.py` **13 條**，
        # 爆點是 `ui/sidebar.py::render_sidebar()` 的「🔍 測試 Proxy 連線」按鈕。
        #     python3 -m pytest tests/test_settings_diag_merge.py \
        #                       tests/test_app_apptest.py -q -p no:randomly
        #     修復前：13 failed, 28 passed ／ 修復後：42 passed
        # 本檔**單跑照樣全綠**，所以它在本檔內沒有任何症狀 —— 這正是它難被發現的原因。
        # 同一個源另外實測到的受害者：`tests/test_render_smoke.py` **3 條**
        # （拿掉本收尾後，本檔 + 該檔併跑會轉紅）。
        # ⚠️ 這兩檔是**已量到的**受害者，**不是**受害者清單的全部 —— 本輪沒有、
        # 也不宣稱掃過全部用 AppTest 的測試檔。
        #
        # 為什麼清在這裡，而不是逐條測試後面加：本檔所有 bare 渲染都經過本
        # contextmanager；放這裡連**例外路徑**（渲染中途爆掉、`with` 沒走完 →
        # 殘留最嚴重）以及日後新增的測試一併涵蓋。實測 25 條裡真正會污染的只有 4 條
        # （會走完整個 `render_settings_diag_tab()` 的那幾條），但把清理綁在
        # 「哪幾條會污染」上，等於要求下一個人先知道答案才不會踩。
        #
        # 修法沿用本 repo 既有先例：`tests/test_app_smoke.py`（v19.176）、
        # `tests/test_rotation_components_ui_20260831.py`、
        # `tests/test_rotation_form_rerun_20260831.py`。
        # ⚠️ 只清 `_form_data`，**不要**連 `_active_dg = _main` 一起抄 ——
        # streamlit 1.59.2 上 `_active_dg` 是**無 setter 的 property**，寫它會拋
        # `AttributeError`（完整機制見
        # `tests/test_rotation_form_rerun_20260831.py::_render_bare` 的 docstring）。
        # ⚠️ 這是**版本相依行為**，不是永恆事實；請現場重驗，不要引用本段當永久事實。
        _main = getattr(st, "_main", None)
        if _main is not None:
            _main._form_data = None


@pytest.fixture()
def stub_sections(monkeypatch):
    """把三個子頁 + 資料註冊表更新 + 保單管理區換成記錄器。

    記錄器同時把「呼叫當下 ⑤ 是否持有對應旗標」記下來 ——
    這是「⑤ 已畫分區標題 → 子頁跳過自己的 ##」機制成立的直接證據。
    """
    import ui.tab5_data_guard as _t5
    import ui.tab6_manual as _t6
    import ui.tab_manage as _tm
    import ui.helpers.data_registry as _dr
    import ui.helpers.portfolio.policy_admin_section as _pas
    from ui.helpers.settings_diag.merge_context import (
        DATA_GUARD_HEADER, MANAGE_HEADER, MANUAL_HEADER,
        owned_by_settings_page,
    )

    hits: dict = {"manage": 0, "diag": 0, "manual": 0, "registry": 0,
                  "policy": 0, "order": [],
                  "owned_at_call": {}}

    def _mk(name: str, part: str | None):
        def _f(*a, **k):
            hits[name] += 1
            hits["order"].append(name)
            if part is not None:
                hits["owned_at_call"][name] = owned_by_settings_page(part)
            return "" if name == "policy" else None
        return _f

    monkeypatch.setattr(_tm, "render_manage_tab", _mk("manage", MANAGE_HEADER))
    monkeypatch.setattr(_t5, "render_data_guard_tab", _mk("diag", DATA_GUARD_HEADER))
    monkeypatch.setattr(_t6, "render_manual_tab", _mk("manual", MANUAL_HEADER))
    monkeypatch.setattr(_dr, "_update_data_registry", _mk("registry", None))
    monkeypatch.setattr(_pas, "render_policy_admin_section", _mk("policy", None))
    return hits


# ══════════════════════════════════════════════════════════════════
# 0) 跨檔守衛：本檔渲染完，不准在根 DeltaGenerator 上留下 form 殘留
# ══════════════════════════════════════════════════════════════════
def test_bare_render_here_leaves_no_form_state_on_the_root_dg(
        monkeypatch, stub_sections):
    """本檔 bare 渲染 ⑤ 之後，`st._main._form_data` 必須回到 None。

    ⚠️ **這條守的是別的檔案，不是本檔** —— 而那正是它非有不可的理由：
    `st._main` 是**模組級單例**，bare 模式（無 ScriptRunContext）下
    `with st.form(...)` 的殘留會**活過整個 pytest 行程**，讓**之後**任何用 AppTest
    且畫面上有 `st.button` 的測試被誤判成「按鈕在 form 裡」而丟
    `StreamlitAPIException: st.button() can't be used in an st.form().`

    實測受害者（2026-09-04，streamlit 1.59.2）：`tests/test_app_apptest.py` **13 條**，
    爆點 `ui/sidebar.py::render_sidebar()` 的「🔍 測試 Proxy 連線」按鈕。
    重現：`pytest tests/test_settings_diag_merge.py tests/test_app_apptest.py -q
    -p no:randomly` → 修復前 `13 failed, 28 passed`。

    ⚠️ `_fake_streamlit` 的 `finally` 收尾若被刪掉，**本檔自己照樣全綠**，
    CI 也可能因為檔名順序或 marker 分流剛好而全綠 ——
    **沒有這條，那段 `finally` 就是一段沒有守衛的修復，
    下一個整理程式碼的人可以無聲刪掉。**
    （靠檔名字母序、隨機種子或 marker 分流當隔離，都是假的隔離。）

    突變實驗（2026-09-04 實跑）：把 `_fake_streamlit` 的 `finally` 收尾整段拿掉 →
    **本條轉紅**，且上述兩檔併跑回到 `13 failed`。

    完整機制與「為什麼**不能**連 `_active_dg` 一起抄」見
    `tests/test_rotation_form_rerun_20260831.py::_render_bare` 的 docstring。
    """
    import streamlit as st

    from ui.tab_settings_diag import render_settings_diag_tab

    _main = getattr(st, "_main", None)
    assert _main is not None, (
        "streamlit 沒有 `_main` —— 本守衛的前提不成立，請現場重新確認版本行為，"
        "不要直接刪掉這條")
    # 先歸零，免得被同行程更早的測試影響、驗到假綠。
    _main._form_data = None

    with _fake_streamlit(monkeypatch):
        render_settings_diag_tab()

    assert getattr(_main, "_form_data", None) is None, (
        f"bare 渲染後根 DG 仍殘留 form 狀態：{_main._form_data!r} —— "
        "同一個 pytest 行程內，後續任何 AppTest 畫面上的 `st.button` 都會被誤判成"
        "「在 form 內」而丟 StreamlitAPIException"
        "（實證受害者：tests/test_app_apptest.py 13 條）。")


# ══════════════════════════════════════════════════════════════════
# 1) 最貴的一條：旗標全空 ⇒ 保單管理在 ⑤ 不渲染（④ 那份照舊 → 不畫兩次）
# ══════════════════════════════════════════════════════════════════
def test_policy_admin_is_off_by_default(monkeypatch, stub_sections):
    """預設（旗標全空）渲染 ⑤ → `render_policy_admin_section` 一次都不准被呼叫，
    並且要有 ⬜ 灰色說明指去 ④（不是紅燈：什麼都沒壞）。

    突變實驗（2026-08-31 實跑）：把 `policy_admin_bridge` 的
    `if not owned_by_settings_page(POLICY_ADMIN):` 的 `not` 拿掉（極性反轉）→
    **本條轉紅**（`policy == 1`，且 RuntimeError 因 sheet_client=None 直接炸）。
    """
    from ui.tab_settings_diag import render_settings_diag_tab

    with _fake_streamlit(monkeypatch) as rec:
        render_settings_diag_tab()

    assert stub_sections["policy"] == 0, "⑤ 未接線就渲染了保單管理 —— ④ 那份還在，會畫兩次"
    _greys = [a for a in rec.args_of("caption")
              if isinstance(a, str) and a.startswith("⬜") and "保單管理" in a]
    assert _greys, "保單管理關閉狀態沒有 ⬜ 灰色說明 —— 使用者看不出它在哪裡"
    assert "error" not in rec.names(), "未接線被畫成紅色錯誤（過度示警）"


def test_policy_admin_flag_on_without_sheet_client_fails_loud(monkeypatch):
    """旗標開了卻沒注入 sheet_client → 當場 RuntimeError（§1 Fail Loud）。

    這條擋的是接線批次跳過硬前置（sheet_client SSOT 還住在 tab3 的閉包裡、
    四處 session_state 耦合還沒處置）就把旗標打開。

    突變實驗（2026-08-31 實跑）：把 bridge 的 `raise RuntimeError(...)` 改成
    `return None`（安靜跳過）→ **本條轉紅**（沒有例外）。
    """
    from ui.helpers.settings_diag.merge_context import POLICY_ADMIN, settings_page_owns
    from ui.helpers.settings_diag.policy_admin_bridge import render_policy_admin_bridge

    with _fake_streamlit(monkeypatch):
        with settings_page_owns(POLICY_ADMIN):
            with pytest.raises(RuntimeError, match="sheet_client"):
                render_policy_admin_bridge(sheet_client=None)


def test_policy_admin_flag_on_with_client_renders_once(monkeypatch, stub_sections):
    """旗標開 + 有注入 client → 保單管理**恰好**渲染一次（擋「永遠打不開」的反向壞掉），
    且 oauth snapshot 有先 refresh（v18.148 紀律）。

    突變實驗（2026-08-31 實跑）：把 bridge 末尾的 `_render_policy_admin(...)`
    呼叫刪掉 → **本條轉紅**（`policy == 0`）。
    把 `_refresh_oauth_state()` 那行刪掉 → **本條轉紅**（refresh 記錄為空）。
    """
    import ui.helpers.oauth_state as _oa
    from ui.helpers.settings_diag.merge_context import POLICY_ADMIN, settings_page_owns
    from ui.helpers.settings_diag.policy_admin_bridge import render_policy_admin_bridge

    refreshed: list = []
    monkeypatch.setattr(_oa, "refresh_oauth_state", lambda: refreshed.append(1))

    _client = object()
    with _fake_streamlit(monkeypatch):
        with settings_page_owns(POLICY_ADMIN):
            render_policy_admin_bridge(sheet_client=_client)

    assert stub_sections["policy"] == 1, "旗標開了保單管理卻沒渲染 —— 永遠打不開的 gate 也是 bug"
    assert refreshed, "沒有先 refresh_oauth_state 就渲染 —— 會拿到 stale snapshot（v18.148 的 bug）"


# ══════════════════════════════════════════════════════════════════
# 2) 診斷區不准在 gate 之前載入（tab5 開頭有無條件匯率抓取 + 註冊表更新）
# ══════════════════════════════════════════════════════════════════
def test_diag_section_is_not_loaded_before_the_gate(monkeypatch, stub_sections):
    """沒勾 gate → `_update_data_registry` 與 `render_data_guard_tab` 一行都不准跑。

    突變實驗（2026-08-31 實跑）：把 `_render_diag_section()` 裡的
    `if not gate_on: … return` 拿掉（診斷無條件載入）→ **本條轉紅**（`diag == 1`）。
    """
    from ui.tab_settings_diag import render_settings_diag_tab

    with _fake_streamlit(monkeypatch, checkbox=False) as rec:
        render_settings_diag_tab()

    assert stub_sections["diag"] == 0, "gate 還沒勾，資料診斷就被載入了"
    assert stub_sections["registry"] == 0, "gate 還沒勾就更新了資料註冊表"
    _greys = [a for a in rec.args_of("caption")
              if isinstance(a, str) and a.startswith("⬜") and "資料診斷" in a]
    assert _greys, "未載入狀態沒有 ⬜ 灰色說明"
    assert "error" not in rec.names(), "未載入被畫成紅色錯誤（過度示警）"


def test_diag_gate_on_runs_registry_before_data_guard(monkeypatch, stub_sections):
    """勾了 gate → 註冊表更新**先於**診斷渲染（tab5 docstring 明文的 caller 契約），
    且診斷**恰好**渲染一次。

    突變實驗（2026-08-31 實跑）：把 `_update_data_registry()` 那行刪掉 →
    **本條轉紅**（registry == 0）。把兩行對調 → **本條轉紅**（順序斷言）。
    """
    from ui.tab_settings_diag import render_settings_diag_tab

    with _fake_streamlit(monkeypatch, checkbox=True):
        render_settings_diag_tab()

    assert stub_sections["diag"] == 1
    assert stub_sections["registry"] == 1
    _order = [n for n in stub_sections["order"] if n in ("registry", "diag")]
    assert _order == ["registry", "diag"], (
        f"caller 契約被打破：必須先 _update_data_registry 再渲染診斷，實際 {_order}")


# ══════════════════════════════════════════════════════════════════
# 3) 旗標全空 ⇒ 三個舊分頁行為不變；⑤ 渲染時旗標確實被持有
# ══════════════════════════════════════════════════════════════════
def test_all_flags_are_off_by_default():
    """預設（沒有任何 context）五個旗標全為 False ——
    這是「旗標全空 ⇒ 三個舊分頁行為與現在完全相同」的機器證據之一
    （另一半由下方 AST 極性測試補：guard 極性是「沒持有才畫」，
    兩者合起來 ⇒ 預設路徑必然走「畫」的分支）。

    突變實驗（2026-08-31 實跑）：把 `merge_context._owned()` 的初始集合改成
    `{"manage_header"}` → **本條轉紅**。
    """
    from ui.helpers.settings_diag.merge_context import (
        DATA_GUARD_HEADER, FETCH_DIAG, MANAGE_HEADER, MANUAL_HEADER,
        POLICY_ADMIN, owned_by_settings_page,
    )

    for part in (MANAGE_HEADER, DATA_GUARD_HEADER, MANUAL_HEADER,
                 FETCH_DIAG, POLICY_ADMIN):
        assert owned_by_settings_page(part) is False, f"{part} 預設竟然是持有狀態"


def test_settings_page_holds_header_flags_while_rendering_subpages(
        monkeypatch, stub_sections):
    """⑤ 呼叫三個子頁時，對應的 header 旗標必須**正在被持有**
    （記錄器在呼叫當下讀旗標）；render 結束後全部還原。

    突變實驗（2026-08-31 實跑）：把 `_render_maintain_section()` 的
    `with settings_page_owns(MANAGE_HEADER):` 拿掉、直接呼叫 → **本條轉紅**
    （`owned_at_call["manage"] is False`）。
    """
    from ui.helpers.settings_diag.merge_context import (
        DATA_GUARD_HEADER, MANAGE_HEADER, MANUAL_HEADER, owned_by_settings_page,
    )
    from ui.tab_settings_diag import render_settings_diag_tab

    with _fake_streamlit(monkeypatch, checkbox=True):
        render_settings_diag_tab()

    assert stub_sections["manage"] == 1 and stub_sections["manual"] == 1
    assert stub_sections["owned_at_call"] == {
        "manage": True, "diag": True, "manual": True}, (
        "⑤ 呼叫子頁時沒有持有對應旗標 —— 子頁會畫出第二個 `##` 標題")
    for part in (MANAGE_HEADER, DATA_GUARD_HEADER, MANUAL_HEADER):
        assert owned_by_settings_page(part) is False, "render 結束旗標沒還原"


def test_merge_context_flag_is_scoped_and_restored_even_on_error():
    """旗標只在 context 內成立，例外路徑也要還原。

    沒有這條，子頁渲染一旦中途丟例外，旗標會留在「⑤ 持有」，
    **舊入口從此少掉標題**而沒有人知道。

    突變實驗（2026-08-31 實跑）：把 `settings_page_owns` 的 `try/finally` 拆成
    直接 `yield` + 之後還原（不用 finally）→ **本條轉紅**（例外後仍為 True）。
    """
    from ui.helpers.settings_diag.merge_context import (
        MANAGE_HEADER, owned_by_settings_page, settings_page_owns,
    )

    assert owned_by_settings_page(MANAGE_HEADER) is False
    with pytest.raises(RuntimeError):
        with settings_page_owns(MANAGE_HEADER):
            assert owned_by_settings_page(MANAGE_HEADER) is True
            raise RuntimeError("boom")
    assert owned_by_settings_page(MANAGE_HEADER) is False, "例外之後旗標沒有還原"


def test_merge_context_flag_does_not_leak_across_threads():
    """旗標必須是**每條執行緒各一份**（WP-C 2026-08-28 稽核抓到的真缺陷，同型防護）：
    Streamlit 一個 process、每個 session 一條 ScriptRunner 執行緒 ——
    模組層集合會讓 session A 在 ⑤ 內渲染時，session B 的舊入口無聲少掉標題。

    突變實驗（2026-08-31 實跑）：把 `_STATE = threading.local()` / `_owned()` 改回
    模組層 `set()` → **本條轉紅**（另一條執行緒看到 True）。
    """
    import threading

    from ui.helpers.settings_diag.merge_context import (
        MANAGE_HEADER, owned_by_settings_page, settings_page_owns,
    )

    _entered, _may_exit = threading.Event(), threading.Event()
    seen_from_other_thread: list = []

    def _holder() -> None:
        with settings_page_owns(MANAGE_HEADER):
            _entered.set()
            _may_exit.wait(timeout=5)

    t = threading.Thread(target=_holder, daemon=True)
    t.start()
    try:
        assert _entered.wait(timeout=5), "持有旗標的執行緒沒有起來"
        seen_from_other_thread.append(owned_by_settings_page(MANAGE_HEADER))
    finally:
        _may_exit.set()
        t.join(timeout=5)

    assert seen_from_other_thread == [False], (
        "⑤ 的所有權旗標跨執行緒外洩 —— 另一個 session 的舊入口會無聲少掉標題")


def test_merge_context_rejects_unknown_part_names():
    """打錯字要當場炸掉，不要安靜回 False（§1 Fail Loud）。

    突變實驗（2026-08-31 實跑）：把 `_validate()` 的 raise 改成 `return` →
    **本條轉紅**（不再拋 ValueError）。
    """
    from ui.helpers.settings_diag.merge_context import owned_by_settings_page

    with pytest.raises(ValueError):
        owned_by_settings_page("no_such_part")


def test_settings_and_fund_research_namespaces_stay_separate():
    """③ 與 ⑤ 是兩個合併頁，各自的封閉集合**互不相認** ——
    誰把兩邊名稱混用（等於共用一個旗標池）都要當場炸掉。

    突變實驗（2026-08-31 實跑）：把 ⑤ 的 `FETCH_DIAG` 加進 ③ 的
    `_KNOWN_PARTS` → **本條轉紅**（③ 不再 raise）。
    """
    from ui.helpers.fund_research import merge_context as _fr
    from ui.helpers.settings_diag import merge_context as _sd

    with pytest.raises(ValueError):
        _fr.owned_by_merged_page(_sd.FETCH_DIAG)
    with pytest.raises(ValueError):
        _sd.owned_by_settings_page(_fr.PAGE_HEADER)


# ══════════════════════════════════════════════════════════════════
# 4) AST + 極性：舊分頁的 `##` 標題與抓取診斷必須被 ⑤ 旗標守住（且方向正確）
# ══════════════════════════════════════════════════════════════════
#: 檔案 → (render 函式, 守衛函式名)。守衛只看這支函式裡面。
_PAGE_RENDERERS: dict = {
    "ui/tab_manage.py": "render_manage_tab",
    "ui/tab5_data_guard.py": "render_data_guard_tab",
    "ui/tab6_manual.py": "render_manual_tab",
    "ui/tab2_single_fund.py": "render_single_fund_tab",
}

_GUARD_NAME = "_settings_page_owns"


def _calls_in_page_renderer(relpath: str):
    """回傳該檔 render 函式內每個呼叫的
    `(呼叫名, 第一個參數原始碼, 是否被 `_settings_page_owns(...)` 以正確極性守住)`。

    - 呼叫名：`st.markdown` 這種 attribute 呼叫回傳 attr 名（`markdown`）；
      `render_fetch_diag_section(...)` 這種 name 呼叫回傳函式名本身。
    - **極性**（WP-C 第三方複驗的教訓，照抄該檔 `_st_calls_in_page_renderer`）：
      只認「⑤ **沒**持有時才畫」的分支 —— `if not _settings_page_owns(...)` 的
      body，或 `if _settings_page_owns(...)` 的 else。條件式被改寫成本函式
      認不得的形狀 → 視為未守住而轉紅（fail-closed）。
    """
    tree = ast.parse((ROOT / relpath).read_text(encoding="utf-8"))
    fname = _PAGE_RENDERERS[relpath]
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == fname)

    def _is_owns_call(c) -> bool:
        return (isinstance(c, ast.Call)
                and getattr(c.func, "id", "") == _GUARD_NAME)

    guarded_ids: set = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)
                and _is_owns_call(test.operand)):
            branch = node.body          # if not owns(...): <這裡是被守住的>
        elif _is_owns_call(test):
            branch = node.orelse        # if owns(...): ... else: <這裡才是被守住的>
        else:
            continue
        for stmt in branch:
            for sub in ast.walk(stmt):
                guarded_ids.add(id(sub))

    out: list[tuple] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        else:
            continue
        arg0 = ast.unparse(node.args[0]) if node.args else ""
        out.append((name, arg0, id(node) in guarded_ids))
    return out


def _is_h2(arg_src: str) -> bool:
    """這個 `st.markdown` 的第一個參數是不是**頁面大標**（恰好兩個 `#`）？"""
    _t = arg_src.lstrip()
    while _t[:1] in ("f", "F", "r", "R", "b", "B"):
        _t = _t[1:]
    _t = _t.lstrip("\"'")
    return _t.startswith("## ")


@pytest.mark.parametrize("relpath", ["ui/tab_manage.py",
                                     "ui/tab5_data_guard.py",
                                     "ui/tab6_manual.py"])
def test_sub_page_h2_title_is_behind_the_settings_guard(relpath):
    """⑤ 自己畫分區標題時，三個子頁不准再畫第二個 `##`（且極性正確）。

    突變實驗（2026-08-31 實跑）：
    - 拿掉 `if not _settings_page_owns(...)` → **轉紅**（三檔各一次）。
    - 極性反轉（`not` 拿掉）→ **轉紅**（守到的是錯的分支；
      這正是舊入口無聲少掉標題、而 sentinel 全綠的那種壞法）。
    """
    _h2 = [(a, g) for name, a, g in _calls_in_page_renderer(relpath)
           if name == "markdown" and _is_h2(a)]
    assert _h2, f"{relpath} 的 render 函式裡找不到任何 `## ` 頁面大標 —— 斷言失去對象"
    _unguarded = [a for a, g in _h2 if not g]
    assert not _unguarded, (
        f"{relpath} 的頁面大標沒有被 ⑤ 旗標以正確極性保護 —— 合併後會出現兩個 `##`："
        f"{_unguarded}")


def test_tab2_fetch_diag_call_is_behind_the_settings_guard():
    """個基頁的「🔍 抓取診斷細節」（已抽出共用）必須被 FETCH_DIAG 旗標守住。

    旗標全空 ⇒ 呼叫照跑（partial 時渲染，與抽出前相同）；
    ⑤ 持有 ⇒ 個基頁不畫（接線批次的切換點）。

    突變實驗（2026-08-31 實跑）：
    - 拿掉 `if not _settings_page_owns(_SD_FETCH_DIAG):` → **轉紅**。
    - 把呼叫整行刪掉 → **轉紅**（0 個 case 也算失去對象）。
    """
    _diag = [(a, g) for name, a, g in
             _calls_in_page_renderer("ui/tab2_single_fund.py")
             if name == "render_fetch_diag_section"]
    assert _diag, ("tab2 的 render 函式裡找不到 render_fetch_diag_section 呼叫 ——"
                   "斷言失去對象（抓取診斷被整個刪掉了？）")
    _unguarded = [a for a, g in _diag if not g]
    assert not _unguarded, (
        "抓取診斷細節沒有被 ⑤ 旗標以正確極性保護 —— 接線後會在 ③ 與 ⑤ 各畫一份")


def test_extracted_fetch_diag_is_verbatim_vs_helper_docstring_claim():
    """抽出的區塊仍是「同一塊」：tab2 不得再殘留第二份 inline 診斷本體。

    驗法：tab2 的 render 函式內不得再有 `##### 🔍 抓取診斷細節` 的 markdown
    （標題已隨區塊本體搬進 helper），helper 內必須恰好有一個。

    突變實驗（2026-08-31 實跑）：把舊 inline 區塊貼回 tab2（保留 helper 呼叫）→
    **本條轉紅**（tab2 出現 inline 標題 = 兩份本體開始各自漂移）。
    """
    _t2_titles = [a for name, a, g in
                  _calls_in_page_renderer("ui/tab2_single_fund.py")
                  if name == "markdown" and "抓取診斷細節" in a]
    assert not _t2_titles, (
        f"tab2 內殘留 inline 的抓取診斷本體 —— 兩份會各自漂移：{_t2_titles}")

    helper_tree = ast.parse(
        (ROOT / "ui/helpers/settings_diag/fetch_diag_section.py")
        .read_text(encoding="utf-8"))
    _h_titles = [n for n in ast.walk(helper_tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "markdown" and n.args
                 and "抓取診斷細節" in ast.unparse(n.args[0])]
    assert len(_h_titles) == 1, "helper 內的抓取診斷標題不是恰好一份"


# ══════════════════════════════════════════════════════════════════
# 5) 抽出的區塊真的能跑（不是只有結構對）
# ══════════════════════════════════════════════════════════════════
def test_fetch_diag_section_renders_a_code_block_for_partial_fd(monkeypatch):
    """餵一份 partial 形狀的 fd，抽出的區塊要真的畫出診斷 code block
    （含 NAS Proxy 行與狀態行）—— 這是「抽出後仍可執行」的行為證據。

    突變實驗（2026-08-31 實跑）：把 helper 內 `st.code(...)` 那段刪掉 →
    **本條轉紅**（沒有任何 code 呼叫）。
    """
    from ui.helpers.settings_diag.fetch_diag_section import render_fetch_diag_section

    fd = {"status": "partial", "fund_name": "測試基金", "moneydj_raw": {},
          "series": None, "metrics": {}, "dividends": [], "page_type": "yp010001"}
    with _fake_streamlit(monkeypatch) as rec:
        render_fetch_diag_section(fd, "partial", "測試基金")

    _codes = [a for a in rec.args_of("code") if isinstance(a, str)]
    assert _codes, "抽出的診斷區塊沒有畫出 code block"
    assert "NAS Proxy" in _codes[0] and "狀態: partial" in _codes[0]
    assert "測試基金" in _codes[0]


def test_fetch_diag_from_session_is_grey_when_nothing_fetched(monkeypatch):
    """⑤ 端：還沒抓過任何基金 → ⬜ 灰色說明，不是紅燈（三態規則）。

    突變實驗（2026-08-31 實跑）：把 `not_ready(...)` 換成 `st.error(...)` →
    **本條轉紅**。
    """
    from ui.helpers.settings_diag.fetch_diag_section import (
        render_fetch_diag_from_session,
    )

    with _fake_streamlit(monkeypatch) as rec:
        render_fetch_diag_from_session()

    assert any(isinstance(a, str) and a.startswith("⬜")
               for a in rec.args_of("caption")), "「還沒抓過」沒有灰色說明"
    assert "error" not in rec.names() and "warning" not in rec.names(), (
        "「還沒抓過」被畫成警示色（過度示警）")


# ══════════════════════════════════════════════════════════════════
# 6) 版面紀律：⑤ 不新增巢狀分頁、不碰資料 / 計算層
# ══════════════════════════════════════════════════════════════════
def test_settings_page_has_no_nested_tabs():
    """線框原文：「五個分區，**單頁 + 目錄錨點**，不再加一層分頁」。

    AST 驗：`ui/tab_settings_diag.py` **沒有** `st.tabs`。

    ⚠️ **2026-08-31 就地更正：斷言一字未動，更正的是它下面那段描述**
    （**有意識的變更，不是漏刪** · 日期 **2026-08-31** · 決策者：**AI 總管**）。
    ~~（子頁自己內部的 `st.tabs`（說明書 10 子分頁）是既有現況，~~
    ~~在 ⑤ 之下是第二層、不再是現況的第三層 —— 改錨點目錄屬後續批次。）~~
    **舊表述在它寫下的當天是對的**：那時 `ui/tab6_manual.py` 確實還有 10 個
    `st.tabs` 子分頁，而「改錨點目錄」確實還沒排。
    **被權衡掉的是它的時態，不是它的判斷** —— 它說的那個「後續批次」**就是本批**
    （說明書 10 子分頁 → 單頁 + 錨點目錄），而且**已經做完**：
    `ui/tab6_manual.py` 現在 `tabs(...)` 呼叫數為 **0**
    （守衛 `tests/test_manual_anchor_toc.py::test_manual_has_no_nested_tabs`）。
    **現況**：⑤ 之下**已無任何子分頁層**；本條守的是「⑤ 自己不要長出第一層」。
    ⚠️ 留著舊句的後果與 `ui/tab_settings_diag.py` 同日被更正的三處是**同一種**：
    一句「屬後續批次」會讓下一個人以為那層 `st.tabs` 還在，
    進而據此規劃一件**已經做完**的工作。
    📌 這是同型敘述的**第 4 個實例**，而且長在**測試檔**裡 ——
    前一輪的揭露只掃了 `ui/tab_settings_diag.py`（該範圍內的複驗成立、沒有說謊），
    **錯的是範圍太窄：這個失效類別是跨檔的**。

    突變實驗（2026-08-31 實跑）：把分區改寫成 `st.tabs([...])` → **本條轉紅**。
    """
    tree = ast.parse((ROOT / "ui" / "tab_settings_diag.py").read_text(encoding="utf-8"))
    attrs = [n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert "tabs" not in attrs, "⑤ 合併頁自己長出巢狀分頁（線框明文禁止）"


def test_settings_page_module_does_not_reach_into_data_or_compute_layers():
    """本次是**版面組裝**，不是計算改動：⑤ 頁自己不得 import L1/L2。

    突變實驗（2026-08-31 實跑）：在 `ui/tab_settings_diag.py` 加一行
    `from services.fund_service import get_latest_fx` → **本條轉紅**。
    """
    tree = ast.parse((ROOT / "ui" / "tab_settings_diag.py").read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module]
        elif isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        bad += [m for m in mods
                if m.split(".")[0] in {"repositories", "services", "infra"}]
    assert not bad, f"⑤ 合併頁自己去碰了資料 / 計算層：{sorted(set(bad))}"


# ══════════════════════════════════════════════════════════════════
# 7) 旗標綁定：guard 的**引數**必須綁對旗標（2026-08-31 獨立稽核抓到的缺口）
# ══════════════════════════════════════════════════════════════════
# 稽核的突變：把 `ui/tab_manage.py` 的 import 改成
# `DATA_GUARD_HEADER as _SD_MANAGE_HEADER`（guard 呼叫與極性都不動）→
# 上面 20 條**照綠**。原因：第 4 節的 AST 守衛只認呼叫名 `_settings_page_owns`
# 與極性、**不看引數**；第 3 節的 sentinel 又把子頁整支 stub 掉，
# 真 guard 從未在「⑤ 持有旗標」下被執行。接線後綁錯旗標 ⇒ ⑤ 內無聲出現
# 兩個 `##` 標題（正是這組守衛要防的那種壞法，換了一個突變方向）。
# 本節補上缺的那把尺：**經 ImportFrom 的 alias 綁定**（不是字串 grep ——
# 三個子頁的 import 全是 `X as _SD_Y` 的 alias 形態）解析 guard 引數
# 真正指到 merge_context 的哪個常數，逐檔斷言期望值。

#: ⑤ 旗標常數的唯一出處。alias 追到的模組不是它 → 一律視為綁錯。
_MERGE_CONTEXT_MODULE = "ui.helpers.settings_diag.merge_context"

#: 檔案 → guard 引數必須綁到的 merge_context 常數名。
#: 每個子頁的 render 函式**可以**綁哪幾支旗標。
#: 2026-09-02：由「一檔一支」改為「一檔一個**封閉集合**」—— ⑤ 把 NAV 拆成兩塊之後，
#: `tab_manage` 與 `tab5_data_guard` 各自多了一個 `NAV_HISTORY` 守衛
#: （線框 `ia-wireframe.html` Tab 05）。
#: ⚠️ **仍然是封閉集合、仍然 fail-closed**：綁到集合外的任何旗標照樣轉紅。
#: 放寬的是「這一頁可以持有幾塊」，**不是**「可以綁別頁的旗標」——
#: 原本要擋的那個病（tab_manage 誤綁 DATA_GUARD_HEADER）**一格未鬆**。
_GUARD_EXPECTED_FLAG: dict = {
    "ui/tab_manage.py": {"MANAGE_HEADER", "NAV_HISTORY"},
    "ui/tab5_data_guard.py": {"DATA_GUARD_HEADER", "NAV_HISTORY"},
    "ui/tab6_manual.py": {"MANUAL_HEADER"},
    "ui/tab2_single_fund.py": {"FETCH_DIAG"},
}


def _import_bindings(tree: ast.AST) -> dict:
    """整檔（含函式內 local import）每個被 import 的名字 → (來源模組, 原始名)。

    只處理 `from M import X [as Y]`；`import M` 形態的名字不會出現在 guard
    引數裡（引數是常數名不是模組名），遇到也自然落入「解析不到」→ fail-closed。
    """
    out: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                out[a.asname or a.name] = (node.module, a.name)
    return out


def _reassigned_names(tree: ast.AST) -> set:
    """整檔被指派過的名字（`X = ...` / `X: T = ...` / walrus / for-target / with-as …）。

    guard 引數若同時是 import 綁定**又**被重新指派過，靜態上就無法信任
    import 那條線（`_SD_MANAGE_HEADER = DATA_GUARD_HEADER` 這種遮蔽會讓
    純 import 解析誤判為綁對）→ 一律 fail-closed 當成綁錯。

    ⚠️ walrus（`ast.NamedExpr`）**必須**在列 —— 2026-08-31 稽核第三個對抗性
    變體實證本函式初版漏了它：guard 前一行插
    `(_SD_MANAGE_HEADER := "data_guard_header")` → 當時 25 條**照綠**。
    walrus 是運算式不是陳述式，藏得進 if 條件、引數、f-string 裡 ——
    漏掉它等於留一條不經 Assign 節點的重綁後門。
    """
    names: set = set()
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        elif isinstance(node, ast.NamedExpr):
            targets = [node.target]
        elif isinstance(node, ast.For):
            targets = [node.target]
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            targets = [node.optional_vars]
        for t in targets:
            for sub in ast.walk(t):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
    return names


def _resolved_guard_flags(relpath: str, *, guard_name: str,
                          fn_name: str) -> list:
    """該檔 `fn_name` 內每個 `guard_name(...)` 呼叫的引數，解析成
    「merge_context 的原始常數名」清單。**任何一步解析不了都直接 assert 失敗**
    （fail-closed：解析不到＝綁錯，不是跳過）。"""
    tree = ast.parse((ROOT / relpath).read_text(encoding="utf-8"))
    bindings = _import_bindings(tree)
    reassigned = _reassigned_names(tree)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == fn_name)

    flags: list = []
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "id", "") == guard_name):
            continue
        # 2026-09-02：`settings_page_owns(...)` 起可帶**多個**位置引數
        # （⑤ 的一個分區可同時持有多塊，例如 MANAGE_HEADER ＋ NAV_HISTORY）。
        # ⚠️ **fail-closed 一格未鬆**：每一個引數仍逐一解析，任何一個追不到
        #    import 來源／被重新指派／不是單純名稱，照樣 assert 失敗。
        #    放寬的只有「**幾個**」，不是「**允不允許認不得的形狀**」。
        assert node.args and not node.keywords, (
            f"{relpath}::{fn_name} 的 {guard_name}(...) 沒有位置引數或帶了關鍵字："
            f"{ast.unparse(node)}（本守衛認不得 → fail-closed 視為綁錯）")
        for arg in node.args:
            assert isinstance(arg, ast.Name), (
                f"{relpath}::{fn_name} 的 guard 引數不是單純名稱："
                f"{ast.unparse(arg)}（fail-closed 視為綁錯）")
            assert arg.id not in reassigned, (
                f"{relpath} 內 {arg.id} 被重新指派過 —— import 綁定不可信"
                f"（fail-closed 視為綁錯）")
            assert arg.id in bindings, (
                f"{relpath}::{fn_name} 的 guard 引數 {arg.id} 追不到 import 來源"
                f"（fail-closed 視為綁錯）")
            mod, orig = bindings[arg.id]
            assert mod == _MERGE_CONTEXT_MODULE, (
                f"{relpath} 的 guard 引數 {arg.id} 綁到 {mod}.{orig}，"
                f"不是 {_MERGE_CONTEXT_MODULE} 的旗標")
            flags.append(orig)
    return flags


@pytest.mark.parametrize("relpath", sorted(_GUARD_EXPECTED_FLAG))
def test_guard_argument_is_bound_to_the_expected_flag(relpath):
    """四個子頁的 `_settings_page_owns(...)` 引數必須綁到**各自那支**旗標。

    突變實驗（2026-08-31 實跑，重現稽核原始突變＋兩個變體）：
    - tab_manage 的 import 改 `DATA_GUARD_HEADER as _SD_MANAGE_HEADER` →
      **本條轉紅**（稽核指出上面 20 條照綠的那個缺口）。
    - tab5 改 `MANUAL_HEADER as _SD_DATA_GUARD_HEADER` → **轉紅**。
    - tab2 改 `MANAGE_HEADER as _SD_FETCH_DIAG` → **轉紅**。
    - 在函式內加 `_SD_MANAGE_HEADER = _SD_DATA_GUARD_HEADER` 遮蔽 import →
      **轉紅**（reassigned fail-closed，import 解析不會被遮蔽騙過）。
    - guard 前一行插 walrus `(_SD_MANAGE_HEADER := "data_guard_header")` →
      **轉紅**（稽核第三個對抗性變體；初版 `_reassigned_names` 漏收
      `ast.NamedExpr` 時本條照綠，已補）。
    """
    flags = _resolved_guard_flags(relpath, guard_name=_GUARD_NAME,
                                  fn_name=_PAGE_RENDERERS[relpath])
    assert flags, (f"{relpath} 找不到任何 {_GUARD_NAME}(...) 呼叫 —— 斷言失去對象"
                   f"（guard 被整個拿掉？第 4 節會另外抓極性，本條抓綁定）")
    expected = _GUARD_EXPECTED_FLAG[relpath]
    wrong = [f for f in flags if f not in expected]
    assert not wrong, (
        f"{relpath} 的 guard 綁錯旗標：綁到 {wrong}，合法值為 {sorted(expected)} ——"
        f"接線後 ⑤ 持有那幾支時這一塊不會讓位（或別的旗標誤傷它），"
        f"畫面會無聲多出／少掉一塊")
    # ⚠️ 雙向：登記了卻**一次都沒綁到**，代表那個守衛被整個拿掉了（或改名了）。
    #    少了這一半，把 `NAV_HISTORY` 守衛整段刪掉會讓本條更綠。
    _missing = sorted(expected - set(flags))
    assert not _missing, (
        f"{relpath} 登記要守 {_missing}，但 render 函式裡一次都沒綁到 ——"
        f"守衛被拿掉了？實際綁到：{sorted(set(flags))}")


def test_settings_page_own_sections_bind_the_expected_flags():
    """⑤ 頁自己三個分區的 `with settings_page_owns(...)` 也要綁對旗標
    （同一把尺量到底；行為面另有 sentinel `owned_at_call` 佐證，兩者互補：
    sentinel 驗「⑤ 端持有對了」，本條驗「靜態綁定就是那一支」）。

    突變實驗（2026-08-31 實跑）：把 `_render_maintain_section` 的
    `settings_page_owns(MANAGE_HEADER)` 改成 `settings_page_owns(DATA_GUARD_HEADER)`
    → **本條轉紅**。
    """
    # 2026-09-02：⑤ 的一個分區可同時持有多塊（NAV 拆兩塊之後，B 分區同時持有
    # MANAGE_HEADER ＋ NAV_HISTORY；D 分區也必須持有 NAV_HISTORY，否則資料診斷
    # 會把它自己那份 NAV 再畫一次）。**用 `==` 比集合，不是「至少包含」** ——
    # 多綁一支別頁的旗標照樣轉紅。
    _expected_by_fn = {
        "_render_maintain_section": {"MANAGE_HEADER", "NAV_HISTORY"},
        "_render_diag_section": {"DATA_GUARD_HEADER", "NAV_HISTORY"},
        "_render_manual_section": {"MANUAL_HEADER"},
    }
    for fn_name, expected in _expected_by_fn.items():
        flags = _resolved_guard_flags("ui/tab_settings_diag.py",
                                      guard_name="settings_page_owns",
                                      fn_name=fn_name)
        assert set(flags) == expected, (
            f"ui/tab_settings_diag.py::{fn_name} 持有的旗標是 {sorted(set(flags))}，"
            f"應為 {sorted(expected)}")
        assert len(flags) == len(set(flags)), (
            f"ui/tab_settings_diag.py::{fn_name} 重複持有同一支旗標：{flags}")
