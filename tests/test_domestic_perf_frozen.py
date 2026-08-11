"""境內基金官方績效 —— 功能凍結的守門測試（2026-08-11 user 拍板）。

## 凍結的理由（來自 `_fetch_domestic_perf` 自己的原始 docstring，不是新發現）

- `yp020000.djhtm?a=BFxxxx` 要的是**公司代碼**，回的是整家公司旗下所有基金的清單，
  Sharpe 欄全 N/A；
- 境內基金頁**根本沒有 wb01 / wb05 / wb07** → 含息報酬率 / Sharpe 不存在。

而舊實作拿**基金代碼**去打那個需要公司代碼的頁，兩個 base 各一次 ——
每檔境內基金每次抓取固定浪費 2 次 MoneyDJ 請求，結果注定是空的。
（MoneyDJ robots.txt 明文禁止 LLM/AI 用途，註定落空的請求尤其不該送。）

## 這條測試在守什麼

**「凍結」很容易被下一輪的自己悄悄解凍** —— 看到函式回空、以為是 bug，就「順手修好」，
於是那 2 次無效請求又回來了，而且會再花一整輪去查為什麼 3-3-3 還是 ⬜。
本測試讓「重新加回 HTTP」這件事**當場變紅**，並在訊息裡寫明解凍要先滿足什麼條件。

⚠️ 這不是「禁止未來修好它」——是要求**解凍必須是明確決定**（連同這條測試一起改），
不是某次重構的副作用。
"""
from __future__ import annotations

import ast
from pathlib import Path

# prime 匯入順序（見 tests/test_nav_history_consume.py:18-21）：
# services.fund_service ↔ fund_fetcher 為既有 latent 互相 import，
# 把下游模組當第一個 import 會撞循環 → 收集階段 ERROR。
import fund_fetcher  # noqa: F401,E402

from repositories.fund.nav_metrics import _fetch_domestic_perf  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
_NAV_METRICS = _ROOT / "repositories" / "fund" / "nav_metrics.py"

# 凍結期間這個函式不得出現的呼叫 —— 全部是「送出 HTTP」的入口
_NETWORK_CALLS = {"fetch_url_with_retry", "get", "post", "urlopen", "request"}


def _frozen_fn() -> ast.FunctionDef:
    _tree = ast.parse(_NAV_METRICS.read_text(encoding="utf-8"))
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.FunctionDef) and _n.name == "_fetch_domestic_perf":
            return _n
    raise AssertionError("找不到 _fetch_domestic_perf")


def test_frozen_function_sends_no_http():
    """接線測試：把任何一次抓取加回去，本測試立刻轉紅。"""
    _bad = []
    for _n in ast.walk(_frozen_fn()):
        if not isinstance(_n, ast.Call):
            continue
        _name = (getattr(_n.func, "id", None) or getattr(_n.func, "attr", None) or "")
        if _name in _NETWORK_CALLS:
            _bad.append(f"L{_n.lineno}:{_name}")
    assert not _bad, (
        f"{_bad}：`_fetch_domestic_perf` 在凍結期間不得送出 HTTP。\n"
        "境內 MoneyDJ 頁沒有 wb01 含息報酬，這些請求注定落空（每檔每次 2 次）。\n"
        "要解凍請先滿足其中一項，並連同本測試一起改：\n"
        "  (1) 找到境內基金的**含息**報酬來源（投信官網 / TDCC / SITCA / 投信投顧公會）；\n"
        "  (2) 或改用「NAV + 配息還原」自算，並在 3-3-3 標示為自算口徑（§2.2 須可分辨）；\n"
        "  (3) 或由 user 用對帳單 CSV 匯入含配息的還原淨值。")


def test_frozen_function_returns_empty_dict():
    """行為：恆回 `{}`，與凍結前實測結果一致（呼叫端行為不變）。"""
    assert _fetch_domestic_perf("ACCP138") == {}
    assert _fetch_domestic_perf("") == {}


def test_freeze_reason_and_unfreeze_conditions_are_documented():
    """§1：凍結必須留下「為什麼」與「怎麼解凍」，否則下一個人只會看到一個回空的函式。

    刻意檢查 docstring 而非註解 —— docstring 是 `help()` / IDE 會顯示的那份。
    """
    _doc = _fetch_domestic_perf.__doc__ or ""
    assert "凍結" in _doc
    assert "wb01" in _doc, "要講清楚缺的是哪個來源"
    assert "解凍條件" in _doc, "沒有解凍條件的凍結 = 永久放棄，那要另外拍板"


def test_mk333_c2_comment_no_longer_claims_moneydj_computes_it():
    """`fund_screening.py` 原本註解寫「ret_3y_ann 是含息總報酬、已由 MoneyDJ 算好」
    —— **兩點都錯**（實際是 fund_service 從 NAV 自算、且不含息）。

    錯的註解正是這輪重複開挖的起點之一，所以釘住它不許回去。
    """
    _src = (_ROOT / "services" / "fund_screening.py").read_text(encoding="utf-8")
    assert "已由 MoneyDJ 算好" not in _src, (
        "這句話不成立：ret_3y_ann 由 services/fund_service.py 從 NAV 序列自算"
        "（需 756 點），而且是純 NAV 不含息")


def test_c2_source_is_no_longer_shown_to_users():
    """2026-08-11 user 拍板：刪掉「②來源」欄與 Tab② 的「（來源：…）」註記。

    刪的理由不是嫌多餘，是它**標錯來源** —— `c2_source == 'metrics(MoneyDJ)'` 的
    底層 `ret_3y_ann` 是 `fund_service` 從 NAV 自算的（需 756 點），既非 MoneyDJ
    提供、也不含息。兩個分支其實都是自算純 NAV，欄位卻宣稱其中一個是官方值
    （§2.2 血緣錯標）。一個會說謊的來源欄，比沒有來源欄更糟。

    ⚠️ `c2_source` **欄位本身保留** —— `scripts/diagnose_ret_3y_fallback.py` 仍讀它
    做診斷。本測試只守「不再顯示給使用者」，不是要把欄位刪掉。
    """
    _scr = (_ROOT / "services" / "fund_screening.py").read_text(encoding="utf-8")
    _tree = ast.parse(_scr)
    _shown = [
        _n.lineno for _n in ast.walk(_tree)
        if isinstance(_n, ast.Constant) and _n.value == "②來源"]
    assert not _shown, (
        f"L{_shown}：「②來源」欄又回來了。要恢復顯示，請先讓 c2_source 講實話"
        "（別再把自算純 NAV 標成 MoneyDJ 官方含息值）")

    _tab2 = (_ROOT / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "（來源：{src}）" not in _tab2 and "'（來源：" not in _tab2, (
        "Tab② 的 3-3-3 又印回 c2_source 了 —— 同上，先讓它講實話再顯示")
