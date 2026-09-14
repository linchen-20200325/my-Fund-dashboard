r"""Q8 批次一｜止血：切斷「用基金名稱猜核心/衛星 → 寫回客戶 Google Sheet」這條鏈。

## 這條鏈原本長什麼樣（每一段都實測過，指令見各測試 docstring）

1. `ui/helpers/cloud_io.py::load_all_from_sheet` 從客戶 Sheet 讀回級別，
   **正確地**存成三態：`core→True` / `satellite→False` / **空白→`None`**。
2. `ui/helpers/portfolio/load.py::batch_load_unloaded_funds` 每次載入基金資料時，
   用 `ui/helpers/session.py::is_core_fund(基金名稱)` **猜**一個**嚴格 bool**
   覆寫掉上一步的值 ⇒ `None`（使用者還沒決定）**當場消失**。
3. 下一次「全部寫入」把那個猜測**寫回客戶的 Sheet**。

⇒ 每一次「載入 → 存檔」就把客戶的空白再蓋一次，**不可逆**。

## 為什麼猜測結構上必然錯

`_CORE_KEYWORDS` 含「配息」且**先於** `_SAT_KEYWORDS` 被檢查，
而台灣基金名稱依法幾乎都帶「(基金之配息來源可能為本金)」
⇒ 命中「配息」⇒ **一律判成核心**。見 :func:`test_mandatory_disclaimer_flips_a_tech_fund_to_core`。

## 讀這個檔之前請先知道：哪些條是真的守衛，哪些不是

本檔每一條測試的 docstring 都標了它在 `origin/main`（`9cbf0377`，修復前）上是紅是綠。
**這句話不是自陳，是被機器守著的** —— 見
:func:`test_every_test_in_this_file_declares_its_state_on_origin_main`：
少標一條就轉紅。（它本身**不是**空轉的，內含正對照。）

⚠️ **但那條守衛只驗「有沒有標」，不驗「標得對不對」。**
「對不對」必須真的把本檔拿到 `origin/main` 上跑一次，那是測試在執行期做不到的事。
任何人都能自己對帳，兩步（repo 根目錄，`<BASE>` ＝ `9cbf0377`）：

    # 1) 在 base 的原始碼上跑本檔，留下逐條結果
    mkdir -p /tmp/tierbase && git archive <BASE> | tar -x -C /tmp/tierbase
    cp tests/test_policy_tier_no_guessing.py /tmp/tierbase/tests/
    (cd /tmp/tierbase && pytest -v tests/test_policy_tier_no_guessing.py) \
        2>&1 | grep -E '^tests/[^ ]+::test_[A-Za-z0-9_]+ (PASSED|FAILED)' \
        | sed 's/ *\[ *[0-9]*%\] *$//' | sort > /tmp/tierbase/measured.txt

    # 2) 把 docstring 的標示與實測逐條比對
    python3 - tests/test_policy_tier_no_guessing.py /tmp/tierbase/measured.txt <<'EOF'
    import ast, sys, collections
    res = {l.split()[0].split('::')[-1]: l.split()[1]
           for l in open(sys.argv[2], encoding='utf-8') if l.strip()}
    assert res, "measured.txt 是空的 —— 上一步沒抓到東西，先修那裡"
    MARK = {"修復前紅": "FAILED", "修復前綠": "PASSED", "機制證據": "PASSED"}
    bad = []
    for f in (n for n in ast.parse(open(sys.argv[1], encoding='utf-8').read()).body
              if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")):
        d = (ast.get_docstring(f) or "").strip()
        hit = [v for k, v in MARK.items() if k in (d.splitlines() or [""])[0]]
        got = res.get(f.name, "<NOT RUN>")
        if len(hit) != 1 or hit[0] != got:
            bad.append((f.name, hit, got))
    print("measured:", dict(collections.Counter(res.values())))
    print("mismatches:", len(bad))
    [print("   ", *b) for b in bad]
    EOF

**最後一次實跑（2026-09-14，`9cbf0377`，本檔共 20 條）**：`FAILED=14, PASSED=6`，`mismatches: 0`。
⚠️ 第 1 步在**缺 `pandas` / `streamlit` 的精簡環境**下另需該環境慣用的旗標
（本次用的是 `--noconftest` ＋ `PYTHONPATH` 上的假件）；**假件不進 repo**。
⚠️ 該次是**單組實測、未經第二組驗證**；數字會隨本檔增刪測試而改變，
**引用前請自己重跑上面兩步**，不要引用這一行。

分類的意思：

* **「修復前紅」** ＝ 真的在守這次的修復，拿掉修復會轉紅。
* **「修復前綠（回歸鎖）」** ＝ 現況本來就對，這條只防未來有人改壞。
  它**不是**本次修復的證據，不要拿它當通過標準。
* **「機制證據，不是守衛」** ＝ 只記錄事實、不依賴修復，兩邊都綠。

⚠️ 「綠燈但沒有正對照 ＝ 沒有檢查」—— 本檔的正對照是
:func:`test_blank_tier_round_trips_as_blank_through_load_then_save_v1`
與其 v2 版：**修復前它們會把客戶的空白寫成 `core`。**
"""
from __future__ import annotations

import pytest

# 台灣基金名稱依法幾乎都帶的揭露字樣。
_MANDATORY_DISCLAIMER = "(基金之配息來源可能為本金)"
# 一檔任何人都會同意是「衛星」的科技基金。
_TECH_FUND = "貝萊德世界科技基金A2(美元)"
_TECH_FUND_WITH_DISCLAIMER = f"貝萊德世界科技基金A6穩定配息(美元){_MANDATORY_DISCLAIMER}"


# ══════════════════════════════════════════════════════════════════
# A. 機制證據（**不是守衛**；不依賴本次修復，修復前後都綠）
# ══════════════════════════════════════════════════════════════════

def test_mandatory_disclaimer_flips_a_tech_fund_to_core() -> None:
    """**機制證據，不是守衛。** 記錄「為什麼這個猜測不能留」。

    同一檔科技基金，只因為名稱多了法定揭露字樣「(基金之配息來源可能為本金)」，
    `is_core_fund` 的判定就從**衛星翻成核心** —— 而那段字樣**每一檔配息型基金都有**。

    ⚠️ 本條**刻意不**斷言 `is_core_fund` 應該回什麼「對的答案」：
    那支函式本身沒有被本批次改動（它還有其他 caller，見 PR 描述的「未處理」清單）。
    本條要釘住的是**這個函式不適合拿來決定寫回客戶 Sheet 的值**這個事實。
    """
    from ui.helpers.session import is_core_fund

    assert is_core_fund(_TECH_FUND) is False, "科技基金本來被判為衛星"
    assert is_core_fund(_TECH_FUND_WITH_DISCLAIMER) is True, (
        "加上法定揭露字樣後被判成核心 —— 這正是本批次要切斷的猜測")


# ══════════════════════════════════════════════════════════════════
# B. 三態解析（新 surface；`origin/main` 上 import 就會失敗 → 修復前紅）
# ══════════════════════════════════════════════════════════════════

def test_resolve_tier_returns_none_when_user_has_not_decided() -> None:
    """**修復前紅**（`shared/policy_tier` 在 `origin/main` 不存在）。

    空白＝「我還沒決定」，**不是**「衛星」。
    """
    from shared.policy_tier import resolve_tier

    assert resolve_tier({}) is None
    assert resolve_tier(None) is None
    assert resolve_tier({"policy_tier": ""}) is None
    assert resolve_tier({"is_core": None}) is None
    # 非法值也是「未設定」，不得默默退成衛星
    assert resolve_tier({"policy_tier": "中性"}) is None


def test_resolve_tier_prefers_explicit_policy_tier_over_is_core() -> None:
    """**修復前紅。** v1 讀取路徑寫的是 `policy_tier`，v2 寫的是 `is_core`；
    兩者衝突時以使用者在 Sheet 上明示的 `policy_tier` 為準。"""
    from shared.policy_tier import resolve_tier

    assert resolve_tier({"policy_tier": "core", "is_core": False}) == "core"
    assert resolve_tier({"policy_tier": "satellite", "is_core": True}) == "satellite"
    assert resolve_tier({"policy_tier": " CoRe "}) == "core"


def test_resolve_tier_never_coerces_unset_into_satellite() -> None:
    """**修復前紅。** `bool(None) is False` 這條路必須不存在。

    這是整個 bug 的核心形狀：用 `bool(...)` 去壓三態，
    「還沒決定」會**默默**變成「衛星」，而且沒有任何畫面看得出來。
    """
    from shared.policy_tier import resolve_tier

    from shared.policy_tier import SATELLITE_TIER

    for _unset in ({}, {"is_core": None}, {"policy_tier": ""}):
        assert resolve_tier(_unset) != SATELLITE_TIER
        assert resolve_tier(_unset) is None


def test_unset_is_written_back_as_blank_not_satellite() -> None:
    """**修復前紅。** 寫回 Sheet 的字串：未設定 → 空字串。"""
    from shared.policy_tier import fund_tier_sheet_value

    assert fund_tier_sheet_value({}) == ""
    assert fund_tier_sheet_value({"is_core": None}) == ""
    assert fund_tier_sheet_value({"is_core": True}) == "core"
    assert fund_tier_sheet_value({"is_core": False}) == "satellite"
    assert fund_tier_sheet_value({"policy_tier": "core", "is_core": False}) == "core"


def test_resolve_core_flag_keeps_its_old_two_state_contract() -> None:
    """**修復前綠（回歸鎖）。** `resolve_core_flag` 改成薄包裝後，
    既有 caller 的行為必須**一個都沒變**（它是二態，未設定→False）。

    這一條存在的理由：本批次把它的實作換掉了，
    如果順手改了語意，Tab3 的卡片與 KPI 會在沒人察覺的情況下翻面。
    """
    from ui.helpers.portfolio.allocation import resolve_core_flag

    assert resolve_core_flag({"policy_tier": "core", "is_core": False}) is True
    assert resolve_core_flag({"policy_tier": "satellite", "is_core": True}) is False
    assert resolve_core_flag({"policy_tier": "", "is_core": True}) is True
    assert resolve_core_flag({"policy_tier": "中性", "is_core": True}) is True
    assert resolve_core_flag({"policy_tier": "中性", "is_core": False}) is False
    assert resolve_core_flag({}) is False
    assert resolve_core_flag(None) is False


# ══════════════════════════════════════════════════════════════════
# 共用：一個夠用的假 streamlit（**只存在於本測試檔**，不是 repo 內的 streamlit 假件）
# ══════════════════════════════════════════════════════════════════

class _FakePlaceholder:
    def info(self, *a, **k): pass
    def success(self, *a, **k): pass
    def progress(self, *a, **k): pass


class _FakeSessionState(dict):
    """真 `st.session_state` 同時支援 `ss["k"]` 與 `ss.k`；
    `load.py` 兩種都用（`st.session_state.get(...)` 與 `st.session_state.portfolio_funds`）。
    假件若只做 dict，測試會在 attribute access 那一行炸掉 —— 那是**假件不夠像**，
    不是被測程式有問題。"""

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as _e:          # pragma: no cover — 只在假件用錯時發生
            raise AttributeError(k) from _e

    def __setattr__(self, k, v):
        self[k] = v


class _FakeSt:
    """`ui/helpers/portfolio/load.py` 會用到的最小 streamlit 表面。

    走 `monkeypatch.setattr(load_mod, "st", _FakeSt())` 注入 —— 與
    `tests/test_cloud_io.py` 用 `monkeypatch.setattr(cloud_io, "upsert_fund_in_policy", ...)`
    同一種手法。**刻意不碰真 `st.session_state`**：那在沒有 script run context 的
    pytest 程序裡行為不保證，測試會變成靠運氣綠。
    """

    def __init__(self, funds):
        self.session_state = _FakeSessionState({"portfolio_funds": funds})
        self.warnings: list[str] = []
        self.reran = False

    def empty(self, *a, **k): return _FakePlaceholder()
    def progress(self, *a, **k): return _FakePlaceholder()
    def write(self, *a, **k): pass
    def warning(self, msg, *a, **k): self.warnings.append(str(msg))
    def rerun(self, *a, **k): self.reran = True


@pytest.fixture()
def load_mod(monkeypatch):
    """匯入 `load.py`，把 `st` 換成假件、把資料註冊表更新變成 no-op。"""
    import ui.helpers.data_registry as _dr
    import ui.helpers.portfolio.load as _load

    monkeypatch.setattr(_dr, "_update_data_registry", lambda *a, **k: None,
                        raising=False)
    return _load


def _run_load(monkeypatch, load_mod, funds, fund_name):
    """跑一次真正的 `batch_load_unloaded_funds()`，回傳被改過的 funds。"""
    import services.fund_service as _fs

    monkeypatch.setattr(
        _fs, "fetch_fund_from_moneydj_url_enriched",
        lambda code: {"fund_name": fund_name, "currency": "USD",
                      "series": None, "dividends": [], "metrics": {},
                      "risk_metrics": {}},
        raising=False)
    _fake = _FakeSt(funds)
    monkeypatch.setattr(load_mod, "st", _fake)
    load_mod.batch_load_unloaded_funds()
    return _fake.session_state["portfolio_funds"]


# ══════════════════════════════════════════════════════════════════
# C. ⭐ 正對照：載入一次，不得動到級別
# ══════════════════════════════════════════════════════════════════

def test_blank_sheet_tier_survives_a_fund_load(monkeypatch, load_mod) -> None:
    """⭐ **修復前紅** —— 這是本批次的正對照。

    情境：客戶在 Sheet 上把級別留白（`is_core is None`），然後按一次「載入基金資料」。

    * `origin/main`（`9cbf0377`）實測：`is_core` 變成 **`True`**（核心）——
      客戶的空白被名稱猜測蓋掉。
    * 修復後：`is_core` 仍是 `None`。

    載入基金資料的職責是**取數**（NAV / 指標 / 名稱），**不是**替客戶決定配置定位。
    """
    funds = [{"code": "BGF-WT", "policy_id": "P1",
              "is_core": None, "loaded": False, "invest_twd": 100}]
    out = _run_load(monkeypatch, load_mod, funds, _TECH_FUND_WITH_DISCLAIMER)

    assert out[0]["loaded"] is True, "前提：這一輪真的載入過了"
    assert out[0]["name"] == _TECH_FUND_WITH_DISCLAIMER, "前提：名稱真的被寫進去了"
    assert out[0]["is_core"] is None, (
        "載入基金資料把客戶留白的級別猜成了一個值 —— 這個值下一次存檔會寫回客戶的 Sheet")


def test_explicit_satellite_survives_a_fund_load(monkeypatch, load_mod) -> None:
    """⭐ **修復前紅。** 客戶**明示**衛星的基金，載入後不得被猜成核心。

    這一條比上一條更嚴重：上一條蓋掉的是「空白」，這一條蓋掉的是**客戶親手填的值**。
    """
    funds = [{"code": "BGF-WT", "policy_id": "P1",
              "is_core": False, "loaded": False, "invest_twd": 100}]
    out = _run_load(monkeypatch, load_mod, funds, _TECH_FUND_WITH_DISCLAIMER)

    assert out[0]["is_core"] is False, "客戶明示的『衛星』被名稱猜測翻成核心"


def test_tier_does_not_leak_across_policies_via_code_reuse() -> None:
    """⭐ **修復前紅。** 同一檔基金在 A 保單是核心、在 B 保單是衛星，完全合法。

    `reuse_fund_info_by_code` 依 **fund_code** 把上一本帳本的基金資訊沿用過來。
    在猜測時代這樣做沒問題（級別本來就只是 code 的函數）；
    級別改成「客戶在 Sheet 明示的值」之後，它變成 **(policy_id, code)** 的函數 ——
    再依 code 沿用，就是把 A 保單的級別搬進 B 保單，然後由存檔寫回客戶的 Sheet。

    `origin/main` 實測：`is_core` 在 `_FUND_INFO_KEYS` 裡 → 會被搬過去。
    """
    from ui.helpers.portfolio.load import _FUND_INFO_KEYS, reuse_fund_info_by_code

    assert "is_core" not in _FUND_INFO_KEYS, (
        "級別不是 fund_code 的函數，不得列入跨帳本沿用欄位")

    prev = [{"code": "X1", "policy_id": "P1", "loaded": True,
             "name": "某基金", "is_core": True, "currency": "USD"}]
    merged = [{"code": "X1", "policy_id": "P9", "loaded": False, "currency": ""}]
    reuse_fund_info_by_code(merged, prev)

    assert merged[0].get("name") == "某基金", "前提：其他基金資訊仍然照常沿用"
    assert merged[0].get("is_core") is None, "P1 的級別被搬進了 P9"


# ══════════════════════════════════════════════════════════════════
# D. ⭐ 端到端：載入 → 存檔（這才是「寫回客戶 Sheet」的完整證據）
# ══════════════════════════════════════════════════════════════════

def _captured_v1_tier(monkeypatch, ss) -> str:
    """跑 v1 寫入路徑，回傳實際寫進 Sheet 的 `policy_tier`。"""
    from ui.helpers import cloud_io

    _rows: list[dict] = []
    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy",
                        lambda c, s, pid, row: _rows.append(row))
    monkeypatch.setattr(cloud_io, "save_all_ledgers_snapshot", lambda *a, **k: 0)
    monkeypatch.setattr(cloud_io, "save_holdings_overview", lambda *a, **k: 0)
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version",
                        lambda *a, **k: "v1", raising=False)

    out = cloud_io.dump_all_to_sheet("fake_client", "sheet_x", ss)
    assert out["error"] is None, out["error"]
    assert len(_rows) == 1, f"前提：這一筆真的被寫出去了（實際 {len(_rows)} 筆）"
    return _rows[0]["policy_tier"]


def _captured_v2_tier(monkeypatch, ss) -> str:
    """跑 v2 寫入路徑，回傳實際寫進 Sheet 的 `tier`。"""
    from ui.helpers import cloud_io

    _seen: list = []
    monkeypatch.setattr(cloud_io, "write_policy_v2",
                        lambda c, s, pid, df: (_seen.append(df), 1)[1])
    out = cloud_io._dump_all_to_sheet_v2("fake_client", "sheet_x", ss)
    assert out["error"] is None, out["error"]
    assert len(_seen) == 1, f"前提：這一筆真的被寫出去了（實際 {len(_seen)} 筆）"
    return _seen[0]["tier"].tolist()[0]


def test_blank_tier_round_trips_as_blank_through_load_then_save_v1(
        monkeypatch, load_mod) -> None:
    """⭐⭐ **修復前紅 —— 本批次最重要的一條（v1 schema）。**

    完整重現客戶會遇到的那件事：

    1. 從 Sheet 讀回，級別留白（`is_core is None`）；
    2. 按「載入基金資料」；
    3. 按「全部寫入」。

    `origin/main` 實測：第 3 步寫回 Sheet 的是 **`"core"`** ——
    客戶的空白被一次往返永久改寫，而且每存一次再蓋一次。
    修復後：寫回 `""`（＝原樣的空白）。
    """
    funds = [{"code": "BGF-WT", "policy_id": "P1",
              "is_core": None, "loaded": False, "invest_twd": 100,
              "currency": "USD"}]
    out = _run_load(monkeypatch, load_mod, funds, _TECH_FUND_WITH_DISCLAIMER)
    _tier = _captured_v1_tier(monkeypatch, {"portfolio_funds": out, "t7_ledgers": {}})

    assert _tier == "", f"客戶留白的級別被寫成 {_tier!r} 寫回了 Sheet"


def test_blank_tier_round_trips_as_blank_through_load_then_save_v2(
        monkeypatch, load_mod) -> None:
    """⭐⭐ **修復前紅 —— 同上，v2 schema（`tier` 欄）。**"""
    funds = [{"code": "BGF-WT", "policy_id": "P1",
              "is_core": None, "loaded": False, "invest_twd": 100,
              "currency": "USD"}]
    out = _run_load(monkeypatch, load_mod, funds, _TECH_FUND_WITH_DISCLAIMER)
    _tier = _captured_v2_tier(monkeypatch, {"portfolio_funds": out, "t7_ledgers": {}})

    assert _tier == "", f"客戶留白的級別被寫成 {_tier!r} 寫回了 Sheet"


# ══════════════════════════════════════════════════════════════════
# E. 寫回路徑不得無視 `policy_tier`
# ══════════════════════════════════════════════════════════════════

def test_v1_writeback_respects_explicit_policy_tier(monkeypatch) -> None:
    """⭐ **修復前紅。** v1 讀取路徑
    (`repositories/policy/v1.py::sync_policies_to_portfolio_funds`)
    寫進 `portfolio_funds` 的是 **`policy_tier`**，**不是** `is_core`。

    舊的寫回三元式只讀 `is_core`（＝名稱猜出來的那個）
    ⇒ 客戶在 Sheet 上親手填的 `core` 會被猜測覆寫成 `satellite`。
    """
    ss = {"portfolio_funds": [{"code": "F1", "policy_id": "P1",
                               "policy_tier": "core", "is_core": False,
                               "invest_twd": 100, "currency": "USD"}],
          "t7_ledgers": {}}
    assert _captured_v1_tier(monkeypatch, ss) == "core"


def test_v2_writeback_respects_explicit_policy_tier(monkeypatch) -> None:
    """⭐ **修復前紅。** 同上，v2 `tier` 欄。"""
    ss = {"portfolio_funds": [{"code": "F1", "policy_id": "P1",
                               "policy_tier": "core", "is_core": False,
                               "invest_twd": 100, "currency": "USD"}],
          "t7_ledgers": {}}
    assert _captured_v2_tier(monkeypatch, ss) == "core"


def test_v1_writeback_keeps_unset_blank(monkeypatch) -> None:
    """**修復前綠（回歸鎖）。**

    ⚠️ 誠實標註：這一條在 `origin/main` 上**本來就是綠的** ——
    舊三元式的 `""` 分支對 `is_core is None` 是**走得到**的。
    舊寫法真正的問題是**上游把 `None` 弄不見了**（見 D 組那兩條端到端）。
    本條只是防止未來有人把這個分支改掉，**不是**本次修復的證據。
    """
    ss = {"portfolio_funds": [{"code": "F1", "policy_id": "P1",
                               "is_core": None,
                               "invest_twd": 100, "currency": "USD"}],
          "t7_ledgers": {}}
    assert _captured_v1_tier(monkeypatch, ss) == ""


# ══════════════════════════════════════════════════════════════════
# F. `_持倉總覽`（`repositories/snapshot_repository.py`）
# ══════════════════════════════════════════════════════════════════

class _FakeWorksheet:
    def __init__(self): self.rows = None
    def clear(self): pass
    def update(self, *a, **kw):
        _vals = kw.get("values")
        if _vals is None and len(a) >= 2:
            _vals = a[1]
        if _vals:
            self.rows = _vals


def _captured_overview_tier(monkeypatch, fund: dict) -> str:
    """跑 `save_holdings_overview`，回傳 `_持倉總覽` 第 5 欄（級別）的值。"""
    import repositories.snapshot_repository as _sr

    _ws = _FakeWorksheet()
    monkeypatch.setattr(_sr, "_ensure_overview_worksheet", lambda c, s: _ws)

    class _Led:
        def to_dict(self):
            return {"fund_code": "F1", "currency": "USD",
                    "position": {"units": 1.0, "cost_unit": 10.0,
                                 "cost_unit_with_div": 10.0, "fx_avg": 32.0,
                                 "dividends_received_twd": 0.0}}

    _sr.save_holdings_overview("c", "s", {"P1::F1": _Led()}, {"P1::F1": fund})
    assert _ws.rows, "前提：真的寫出了列"
    return _ws.rows[-1][4]


def test_overview_tier_respects_explicit_policy_tier(monkeypatch) -> None:
    """⭐ **修復前紅。** `_持倉總覽` 的「級別」欄原本只讀 `is_core`，
    v1 路徑的 `policy_tier` 在這張表上完全看不到。"""
    assert _captured_overview_tier(
        monkeypatch, {"policy_tier": "core", "is_core": False,
                      "name": "X", "invest_twd": 1}) == "核心"


def test_overview_tier_blank_when_unset(monkeypatch) -> None:
    """**修復前綠（回歸鎖）。** 未設定 → 空白，不得印成「衛星」。

    ⚠️ 同 `test_v1_writeback_keeps_unset_blank`：舊寫法這條路本來就走得到，
    真正壞掉的是上游。本條只防未來改壞。
    """
    assert _captured_overview_tier(
        monkeypatch, {"name": "X", "invest_twd": 1}) == ""


def test_overview_tier_still_reads_is_core_two_states(monkeypatch) -> None:
    """**修復前綠（回歸鎖）。** v2 路徑只有 `is_core`，兩個明示值必須照舊。

    （與 `tests/test_ledger_snapshot_store.py` 既有的兩條斷言同語意，
    放在這裡是因為本批次換掉了那一段的實作，需要就地鎖住。）
    """
    assert _captured_overview_tier(
        monkeypatch, {"is_core": True, "name": "X", "invest_twd": 1}) == "核心"
    assert _captured_overview_tier(
        monkeypatch, {"is_core": False, "name": "X", "invest_twd": 1}) == "衛星"


# ══════════════════════════════════════════════════════════════════
# G. 形態偵測（**可被繞過**，誠實標註；真正的鎖是 C / D 兩組）
# ══════════════════════════════════════════════════════════════════

def test_load_path_does_not_import_the_name_heuristic() -> None:
    """**修復前紅**，但**這是形態偵測，可以被繞過**（`importlib` / 換個名字都能躲）。

    留著的理由是縱深防禦 ＋ 讓「有人想把猜測加回載入路徑」在 code review 前就先紅。
    **真正 fail-closed 的是 C 組與 D 組**（它們驗的是實際跑完之後的值）。
    """
    import ast
    import pathlib

    _src = pathlib.Path("ui/helpers/portfolio/load.py").read_text(encoding="utf-8")
    _names = {
        _n.name for _node in ast.walk(ast.parse(_src))
        if isinstance(_node, ast.ImportFrom) for _n in _node.names
    }
    assert "is_core_fund" not in _names, (
        "載入路徑又把基金名稱啟發式 import 回來了 —— 猜測會再次覆寫客戶的級別")


# ══════════════════════════════════════════════════════════════════
# H. v2 讀取路徑必須清掉 v1 的 `policy_tier`（否則新級別會被舊值蓋掉）
# ══════════════════════════════════════════════════════════════════

def test_v2_read_clears_stale_policy_tier_left_by_v1_or_json_restore(monkeypatch) -> None:
    """⭐ **修復前紅。** **本批次新增的防線** —— 它擋的是**本批次自己造出來的**風險，請一起看：

    ⚠️ **這一條的「修復前紅」要看清楚是紅在哪裡**（2026-09-14 於 `9cbf0377` 實測）：
    在 `origin/main` 上它的**直接**死因是 `shared.policy_tier` 這個模組不存在
    （`ModuleNotFoundError`），**不是**斷言失敗。但它守的那個缺陷**在 `origin/main` 上
    是真的、而且可以單獨證明** —— 同一段 `_load_all_from_sheet_v2` 流程、同一份輸入，
    殘留的 `policy_tier` 在兩個 tree 上的下場不同：

        origin/main (9cbf0377) : policy_tier 仍是 'core'   ← 會被寫回客戶 Sheet
        本分支                  : policy_tier 被清成 ''     ← 以 Sheet 的 satellite 為準

    另見突變 F（拿掉 v2 讀取路徑那一行清除 → 本條在**修復後的 tree 上**轉紅），
    那才是「這條真的在守東西」的正對照。

    `resolve_tier` 讓 `policy_tier` **勝過** `is_core`
    （必要：v1 讀取路徑只寫 `policy_tier`）。
    而 v2 讀取路徑用 `**_prev` 沿用上一輪的 dict，
    有**兩條真實來源**會把過期的 `policy_tier` 帶進來：

    * 同一個 session 先走過 v1 讀取路徑；
    * 先還原過 JSON 備份（`ui/helpers/io/json_backup.py` 有備份這個欄位）。

    在本批次之前這只是**顯示**不一致（`resolve_core_flag` 本來就偏好 `policy_tier`）；
    本批次把 `policy_tier` 接進**寫回路徑**之後，它會升級成
    **把過期級別寫回客戶 Sheet** —— 也就是本批次要消滅的那種傷害。

    本測試：Sheet 上是 `satellite`，而 session 殘留 `policy_tier="core"`
    ⇒ 讀回後必須以 Sheet 為準（衛星），且存檔寫回 `satellite`。
    """
    from ui.helpers import cloud_io

    _prev = [{"code": "F1", "policy_id": "P1",
              "policy_tier": "core",          # ← v1 / JSON 還原留下的殘值
              "is_core": True, "invest_twd": 100, "currency": "USD"}]
    _ss = {"portfolio_funds": _prev}

    class _FakeDF:
        """只需要 `load_all_policies_v2` 回傳物的 `iterrows()` 介面。"""
        empty = False
        columns = ["policy_id", "fund_code", "tier"]

        def iterrows(self):
            yield 0, {"policy_id": "P1", "fund_code": "F1",
                      "fund_name": "某基金", "currency": "USD",
                      "tier": "satellite",      # ← Sheet 上的真值
                      "invest_twd": 100, "div_cash_pct": 100,
                      "units": 0, "avg_nav": 0, "avg_fx": 0}

        def __getitem__(self, k): return ["P1"]

    monkeypatch.setattr(cloud_io, "load_all_policies_v2", lambda c, s: _FakeDF())
    monkeypatch.setattr(cloud_io, "load_all_ledgers_snapshot", lambda *a, **k: {})

    out = cloud_io._load_all_from_sheet_v2("c", "s", _ss)
    assert out["error"] is None, out["error"]

    _f = _ss["portfolio_funds"][0]
    assert _f["is_core"] is False, "前提：v2 的 tier 欄真的被讀進來了"

    from shared.policy_tier import resolve_tier
    assert resolve_tier(_f) == "satellite", (
        f"殘留的 policy_tier={_f.get('policy_tier')!r} 蓋掉了 Sheet 上的 satellite")
    assert _captured_v1_tier(monkeypatch, {"portfolio_funds": [_f], "t7_ledgers": {}}) \
        == "satellite", "過期的級別被寫回了客戶的 Sheet"


# ══════════════════════════════════════════════════════════════════
# I. 後設守衛：把本檔開頭那句自陳變成機器檢查
# ══════════════════════════════════════════════════════════════════

def test_every_test_in_this_file_declares_its_state_on_origin_main() -> None:
    """**修復前綠（回歸鎖）。** 本檔開頭自陳「每一條測試都標了修復前是紅是綠」——
    這一條讓那句話**少標一條就轉紅**，而不是靠人記得。

    **為什麼需要它**：本 PR 第一版就是在這裡出錯的 —— 19 條裡有 1 條
    （:func:`test_v2_read_clears_stale_policy_tier_left_by_v1_or_json_restore`）
    **沒有標**，而開頭那句寫的是「**每一條**都標了」。
    人工複讀 18 條沒抓到，commit message 還把它算成「已全數對帳」。
    **一句沒有機器守著的自陳，遲早會變成假的。**

    **判定規則**：每一條 `test_*` 的 docstring **第一行**必須含**恰好一個**
    「修復前紅 / 修復前綠 / 機制證據」。只認第一行 —— 內文要怎麼引用都不影響。

    ⚠️ **本條的射程只到「有沒有標」，不到「標得對不對」** ——
    要驗「對不對」必須把本檔拿到 `origin/main` 的原始碼上實跑一次，
    那是執行期做不到的事。對帳指令寫在本檔開頭的 module docstring 裡。
    **不要把本條轉綠讀成「標示都是對的」。**
    """
    import ast
    from pathlib import Path as _Path

    _src = _Path(__file__).read_text(encoding="utf-8")
    assert _src.strip(), "讀到空檔 —— 這條檢查本身失效了，先修這裡"

    _MARKERS = ("修復前紅", "修復前綠", "機制證據")

    def _labels_of(fn) -> list:
        """標示只認 docstring 的**第一行** —— 那是本檔每一條實際擺放標示的位置。

        ⚠️ **刻意不是「整段 docstring 裡有沒有出現」**：那樣寫會鬆到抓不到東西 ——
        本條第一版就是那樣寫的，結果「把第一行的標示刪掉、但內文還提到它」
        竟然是綠的（實測突變 M1）。**只認第一行，內文要怎麼解釋都不影響判定。**
        """
        _doc = (ast.get_docstring(fn) or "").strip()
        _first = _doc.splitlines()[0] if _doc else ""
        return [m for m in _MARKERS if m in _first]

    _fns = [n for n in ast.parse(_src).body
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    assert _fns, "AST 掃不到任何 test_* —— 這條檢查本身失效了，先修這裡"

    # 正對照：同一段判定邏輯必須真的抓得到「沒標」與「標了兩個」，
    # 否則它只是一條永遠綠的空轉斷言（本檔開頭：「綠燈但沒有正對照 ＝ 沒有檢查」）。
    _probe = ast.parse(
        'def test_no_label():\n    """沒有任何標示。"""\n'
        'def test_two_labels():\n    """既說修復前紅又說修復前綠。"""\n'
        'def test_label_buried_in_body():\n'
        '    """第一行沒有標示。\n\n    內文才提到修復前紅。\n    """\n')
    _p_none, _p_both, _p_buried = [
        n for n in _probe.body if isinstance(n, ast.FunctionDef)]
    assert _labels_of(_p_none) == [], "正對照失效：沒標示的函式竟被判為有標示"
    assert len(_labels_of(_p_both)) == 2, "正對照失效：標了兩個竟沒被判為歧義"
    assert _labels_of(_p_buried) == [], (
        "正對照失效：標示埋在內文、第一行沒有，卻被判為有標示 —— "
        "這正是本條第一版漏掉的那個形狀（突變 M1）")

    _bad = [(fn.name, _labels_of(fn)) for fn in _fns if len(_labels_of(fn)) != 1]
    assert not _bad, (
        "下列測試的 docstring **第一行**沒有**恰好一個**「修復前紅 / 修復前綠 / 機制證據」標示，\n"
        "本檔開頭那句自陳因此為假。請補上標示（或修掉歧義）：\n  "
        + "\n  ".join(f"{n}: {labs}" for n, labs in _bad))
