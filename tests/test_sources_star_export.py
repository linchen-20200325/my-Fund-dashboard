"""v19.248 R17 regression test — sources.py `__all__` SSOT 守門。

防 P1-5 拆檔後 `from sources import *` 規則性遺漏底線開頭 `_src_*` 名,
production NameError 線上才被發現的 bug 再發生。
"""
from __future__ import annotations


def test_sources_all_contains_src_direct_moneydj_url():
    """v19.248 R17 — 線上 NameError root cause 守:_src_direct_moneydj_url
    必須在 `__all__` 中(否則 `import *` 不引入,fund_orchestration 整爆)。"""
    from repositories.fund import sources
    assert hasattr(sources, "__all__"), "sources.py 必須宣告 __all__ SSOT"
    assert "_src_direct_moneydj_url" in sources.__all__, \
        "_src_direct_moneydj_url 必須在 __all__ 中(P1-5 拆檔 bug fix v19.248 R17)"


def test_sources_star_import_loads_all_src_helpers():
    """`from sources import *` 必須引入所有 `_src_*`(P1-5 拆檔後 import * 預設規則
    過濾底線名,需 __all__ 顯式宣告才能載入)。"""
    _ns = {}
    exec("from repositories.fund.sources import *", _ns)
    src_names = [k for k in _ns if k.startswith("_src_")]
    assert len(src_names) >= 20, \
        f"_src_* 至少 20 個 source adapter 應由 import * 載入,實際 {len(src_names)}"
    # 抽樣 critical:涵蓋 MoneyDJ direct / TDCC / TCB / FundClear 4 個關鍵 source
    for critical in [
        "_src_direct_moneydj_url",
        "_src_tdcc_meta",
        "_src_tcb_nav",
        "_src_fundclear_nav",
        "_src_cnyes_nav",
        "_src_insurance_subdomain_nav",
    ]:
        assert critical in _ns, f"critical source adapter {critical} 必須在 import * 載入清單"


def test_fund_orchestration_can_access_src_symbols():
    """fund_orchestration.py 用 `from sources import *` re-export 後,
    所有 `_src_*` 名必須能在 module namespace 找到(production caller 路徑)。"""
    import fund_fetcher  # noqa: F401 — 解 circular
    import repositories.fund.fund_orchestration as fo
    # 抽樣關鍵 _src_*
    for sym in [
        "_src_direct_moneydj_url",
        "_src_tcb_nav",
        "_src_fundclear_nav",
        "_src_yahoo_finance_nav",
        "_src_tdcc_meta",
    ]:
        assert hasattr(fo, sym), \
            f"fund_orchestration 應有 {sym}(re-export from sources via import *)"


def test_all_src_funcs_in_sources_are_exported():
    """v19.248 R17 邊界 3 守 — 防未來新增 `_src_*` 但忘加 `__all__`。

    用 introspection 動態抓 sources.py 所有 `def _src_*` 名,驗證**全部**
    在 `__all__` 中(避免 R17 type bug 再發生)。
    """
    from pathlib import Path
    import re

    sources_path = Path(__file__).parents[1] / "repositories" / "fund" / "sources.py"
    src_text = sources_path.read_text(encoding="utf-8")

    # 抓所有 `def _src_xxx`(production 定義)
    src_defs = set(re.findall(r"^def (_src_[a-z_0-9]+)", src_text, re.MULTILINE))
    assert src_defs, "sources.py 必須有 _src_* 定義(否則 audit script 壞)"

    from repositories.fund import sources
    all_set = set(sources.__all__)

    missing = src_defs - all_set
    assert not missing, (
        f"sources.py 定義的 _src_* 缺漏在 __all__: {sorted(missing)} "
        f"— 新增 source adapter 必須同步加入 __all__ SSOT(R17 bug 預防)"
    )


def test_all_underscore_helpers_used_by_orchestration_are_exported():
    """v19.248 R17 邊界 4 守 — fund_orchestration.py 用到的所有底線開頭 helper
    都必須在 sources.py 的 `__all__` 中(若該 helper 真定義於 sources)。

    防 import * re-export chain 漏掉新加的 internal helper。
    """
    from pathlib import Path
    import re

    orch_path = Path(__file__).parents[1] / "repositories" / "fund" / "fund_orchestration.py"
    orch_text = orch_path.read_text(encoding="utf-8")
    sources_path = Path(__file__).parents[1] / "repositories" / "fund" / "sources.py"
    src_text = sources_path.read_text(encoding="utf-8")

    # 抓 orchestration 用到的 _* 名字(call form `_xxx(`)
    used = set(re.findall(r"\b(_[a-z_][a-z_0-9]*)\s*\(", orch_text))
    # sources 定義的 _* 名字
    src_defs = set(re.findall(r"^def (_[a-z_][a-z_0-9]+)", src_text, re.MULTILINE))

    # 交集:orchestration 用到 + sources 定義 → 必須在 __all__
    cross_used = used & src_defs

    from repositories.fund import sources
    all_set = set(sources.__all__)
    missing = cross_used - all_set
    assert not missing, (
        f"fund_orchestration 用到但 sources.__all__ 漏掉: {sorted(missing)} "
        f"— 會觸發 NameError(R17 bug 同 type)"
    )
