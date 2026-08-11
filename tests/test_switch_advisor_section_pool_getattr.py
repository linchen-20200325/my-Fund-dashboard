"""稽核回歸:持倉檔同時在選股池時,_rows_with_nav 不得對 PoolEntry 呼叫 .get()(v19.432)。

pool_by_code 的值是 PoolEntry dataclass(無 .get())。舊版 `(pool_by_code.get(c) or {}).get(...)`
在「持倉也在選股池」時拋 AttributeError → 被外層 except 吞掉 → 整張換股建議表靜默消失。
"""
from __future__ import annotations


def test_rows_with_nav_handles_pool_entry_without_crash(monkeypatch):
    import ui.helpers.fund_grp_health.rotation as R
    # _assemble_rows 回一列(無類別),繞過 streamlit / 重抓
    monkeypatch.setattr(R, "_assemble_rows",
                        lambda funds: [{"code": "AAA", "基金類別": None, "σ rank": "-1.0σ"}])

    from repositories.pool_repository import PoolEntry
    from ui.helpers.fund_grp_health.switch_advisor_section import _rows_with_nav

    funds = [{"code": "AAA", "series": None}]
    pbc = {"AAA": PoolEntry(code="AAA", category="股票", type_override="震盪")}   # 持倉也在池

    rows = _rows_with_nav(funds, pbc)                       # 舊版此行 AttributeError
    assert rows[0]["type_override"] == "震盪"                # 從 PoolEntry 取到(getattr)
    assert rows[0]["基金類別"] == "股票"


def test_rows_with_nav_held_not_in_pool_defaults(monkeypatch):
    import ui.helpers.fund_grp_health.rotation as R
    monkeypatch.setattr(R, "_assemble_rows",
                        lambda funds: [{"code": "ZZZ", "基金類別": "平衡型"}])
    from ui.helpers.fund_grp_health.switch_advisor_section import _rows_with_nav

    rows = _rows_with_nav([{"code": "ZZZ", "series": None}], {})   # 不在池
    assert rows[0]["type_override"] == ""                  # 預設空字串,不炸
    assert rows[0]["基金類別"] == "平衡型"                    # 已有類別不覆寫
