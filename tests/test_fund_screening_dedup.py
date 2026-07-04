"""v19.306 回歸網 — MK 3-3-3 批次篩選去重（SSOT 一檔一列）。

user 2026-07-04 截圖回報「MK 3-3-3 原則批次篩選 → 展開 3-3-3 評估明細」表
出現重複列（JFZN3 / ACCP138 各兩次，「共 25 檔」含重複）。根因:同一基金
跨多張保單在 portfolio_funds 重複載入,`batch_333_funds` 逐檔建列未去重。
3-3-3 評估的是基金內在屬性(成立年 / 3年年化 / 同儕排名),重複列 = 雜訊。

本檔鎖住 v19.306 SSOT 去重:以 code 一檔一列、保留首次出現順序。
"""
from __future__ import annotations

from services.fund_screening import batch_333_funds


def _mk_fund(code: str, name: "str | None" = None) -> dict:
    # series=None → check_333_fund 安全回傳空結果(不需真實 NAV);去重測試只看 code。
    return {"code": code, "name": name or code, "series": None, "metrics": {}}


class TestBatch333Dedup:
    def test_duplicate_codes_collapse_to_one_row(self):
        """模擬截圖:JFZN3 / ACCP138 各出現兩次 → 各收斂為一列,順序保留。"""
        fund_list = [
            _mk_fund("TLZF9"),
            _mk_fund("JFZN3"),
            _mk_fund("ACTI94"),
            _mk_fund("ACCP138"),
            _mk_fund("JFZN3"),     # 重複
            _mk_fund("ACCP138"),   # 重複
        ]
        df = batch_333_funds(fund_list)
        codes = df["代碼"].tolist()
        assert codes == ["TLZF9", "JFZN3", "ACTI94", "ACCP138"], (
            "應一檔一列且保留首次出現順序"
        )
        assert len(codes) == len(set(codes)), "代碼欄不得有重複"

    def test_count_reflects_unique_funds(self):
        """「共 N 檔」統計 = 去重後檔數(不再灌水)。"""
        fund_list = [_mk_fund(c) for c in ("A", "B", "A", "B", "C", "A")]
        df = batch_333_funds(fund_list)
        assert len(df) == 3  # A / B / C

    def test_no_duplicates_unchanged(self):
        """本來就沒重複 → 行為不變(順序、檔數皆同)。"""
        fund_list = [_mk_fund(c) for c in ("X", "Y", "Z")]
        df = batch_333_funds(fund_list)
        assert df["代碼"].tolist() == ["X", "Y", "Z"]

    def test_empty_list_returns_empty_df(self):
        df = batch_333_funds([])
        assert df.empty
