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
