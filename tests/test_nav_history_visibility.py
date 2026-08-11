"""nav_history 累積「進度可見化」的回歸測試（2026-08-11）。

背景 —— 長歷史 NAV 從雲端 IP 抓不到是**已定案的事實**（`services/nav_history_gs.py`
檔頭 v19.359 2026-07-22：「靠日常使用『從現在累積』歷史序列」）。累積機制寫入正常、
Tab⑤ 狀態燈是綠的、每次抓取都印「本次新存 N 筆」—— 但序列可以好幾週一動不動。

原因在 `fund_service._merge_nav_history_series`：

    added = len(merged) - len(s_live)
    if added <= 0:            # 累到的點還全落在 live 的滾動窗內
        return s_live, None   # ← 資訊整包丟掉

這是**全站唯一**知道「有累積、但還沒產生淨增益」的地方，卻回 None。
於是「寫入成功」「燈是綠的」「序列沒變長」三件事同時成立，而畫面上沒有任何
地方講得出中間的落差 —— 使用者（和 AI）只能猜。這輪就因此兩次把「部署沒生效」
誤判成「修了沒用」。

本檔守的是把那個落差變成可讀數字（§1 誠實 / §5 可觀測），**不改任何取數行為**。
全部離線可跑（fake sheet + monkeypatch，無網路無 secrets）。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

# ⚠️ prime 匯入順序（**不是多餘的 import**）：`services.fund_service` ↔ `fund_fetcher`
# 是既有的 latent 互相 import（`fund_fetcher:285` 回頭 `from services.fund_service
# import _RF_ANNUAL`）。把 `fund_service` 當本檔「第一個」import 會直接撞循環，
# pytest 收集階段就 ERROR（本檔第一版就是這樣紅的）。
# 先走自然入口 `fund_fetcher`，與 `tests/test_nav_history_consume.py:18-21`
# 及 `tests/test_fund_load_enriched.py` 同一慣例。
import fund_fetcher  # noqa: F401,E402

from services.fund_service import _merge_nav_history_series  # noqa: E402
from services.nav_history_gs import coverage_status  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
_TAB5 = _ROOT / "ui" / "tab5_data_guard.py"
_TAB2 = _ROOT / "ui" / "tab2_single_fund.py"


def _series(dates: list[str]) -> pd.Series:
    return pd.Series([10.0 + i for i in range(len(dates))],
                     index=pd.to_datetime(dates), dtype=float)


# ══════════════════════════════════════════════════════════════════════
# ① merge trace —— 「累了但沒淨增益」不得再回 None
# ══════════════════════════════════════════════════════════════════════

def _patch_hist(monkeypatch, s_hist: pd.Series):
    import services.nav_history_gs as _gs
    monkeypatch.setattr(_gs, "load_series", lambda _c: s_hist, raising=True)


def test_no_net_gain_returns_informative_trace(monkeypatch):
    """核心回歸：累積點全落在 live 範圍內時，必須回**帶數字的 trace**，不是 None。"""
    _live = _series(["2026-08-01", "2026-08-02", "2026-08-03"])
    _patch_hist(monkeypatch, _series(["2026-08-02"]))     # 已被 live 涵蓋
    _out, _trace = _merge_nav_history_series(_live, "ACCP138")

    assert len(_out) == 3, "序列必須原樣不動（本次只補資訊，不改取數行為）"
    assert _trace is not None, "不得再回 None —— 那正是「看不見」的成因"
    assert _trace["merged"] is False
    assert _trace["hist_points"] == 1
    assert _trace["hist_first"] == "2026-08-02"
    assert _trace["added"] == 0
    assert _trace.get("note")


def test_no_net_gain_trace_must_not_claim_success(monkeypatch):
    """⚠️ 行為保護：`success` 這個 key 是 `fund_service` 用來判定「真的併入了
    累積歷史」的閘門（:1108 換序列、:1141 啟動 coverage/sparse 重審）。

    資訊性 trace **不可以**設 `success`，否則會把純 live 序列也丟進稀疏重審 ——
    那是行為變更，不是加一行說明。拿掉這條斷言，回歸就會靜默溜過去。
    """
    _live = _series(["2026-08-01", "2026-08-02"])
    _patch_hist(monkeypatch, _series(["2026-08-01"]))
    _, _trace = _merge_nav_history_series(_live, "X")
    assert not _trace.get("success"), (
        "資訊性 trace 不得帶 success —— 它是「已併入」的閘門，"
        "誤設會連帶啟動 coverage/sparse 重審（行為變更）")


def test_real_merge_still_reports_success_and_merged(monkeypatch):
    """真的加長序列時，既有的 `success` 語意不變，另補 `merged`/`hist_points`。"""
    _live = _series(["2026-08-01", "2026-08-02"])
    _patch_hist(monkeypatch, _series(["2024-01-05", "2024-01-08"]))   # live 窗外
    _out, _trace = _merge_nav_history_series(_live, "X")
    assert len(_out) == 4
    assert _trace["success"] is True and _trace["merged"] is True
    assert _trace["added"] == 2


def test_empty_history_still_returns_none(monkeypatch):
    """Sheet 沒資料 → 維持原本的 `None`（沒有累積就沒有進度可報，不製造噪音）。"""
    _patch_hist(monkeypatch, pd.Series(dtype=float))
    _, _trace = _merge_nav_history_series(_series(["2026-08-01"]), "X")
    assert _trace is None


# ══════════════════════════════════════════════════════════════════════
# ② coverage_status
# ══════════════════════════════════════════════════════════════════════

class _FakeWS:
    def __init__(self, rows): self._rows = rows
    def get_all_values(self): return self._rows


class _FakeSheet:
    def __init__(self, rows): self._ws = _FakeWS(rows)
    def worksheet(self, _name): return self._ws


_HEADER = ["code", "date", "nav", "fund_name", "source", "recorded_at"]


def test_coverage_status_groups_and_computes_span():
    _sheet = _FakeSheet([
        _HEADER,
        ["ACCP138", "2026-07-22", "12.3", "瀚亞", "app", ""],
        ["ACCP138", "2026-08-11", "12.9", "瀚亞", "app", ""],
        ["TLZF9", "2026-08-01", "9.5", "安聯", "app", ""],
    ])
    _out = coverage_status(_sheet=_sheet)
    assert _out["ACCP138"] == {
        "points": 2, "first": "2026-07-22", "last": "2026-08-11", "span_days": 20}
    assert _out["TLZF9"]["points"] == 1
    assert _out["TLZF9"]["span_days"] == 0


def test_coverage_status_filters_by_codes():
    _sheet = _FakeSheet([
        _HEADER,
        ["A1", "2026-08-01", "1.0", "", "", ""],
        ["B2", "2026-08-01", "2.0", "", "", ""],
    ])
    assert set(coverage_status(["a1"], _sheet=_sheet)) == {"A1"}


def test_coverage_status_dedups_same_date():
    """(code, date) 是主鍵，但防禦性去重 —— 灌水不該讓進度看起來比較快。"""
    _sheet = _FakeSheet([
        _HEADER,
        ["A1", "2026-08-01", "1.0", "", "", ""],
        ["A1", "2026-08-01", "1.1", "", "", ""],
    ])
    assert coverage_status(_sheet=_sheet)["A1"]["points"] == 1


def test_coverage_status_empty_sheet_returns_empty_dict():
    """§1：讀不到 → `{}`，呼叫端據此說「不知道」而非「0 點」。兩者意義不同。"""
    assert coverage_status(_sheet=_FakeSheet([_HEADER])) == {}


def test_coverage_status_bad_date_keeps_point_count_honest():
    """日期壞掉 → 跨度未知（0），但**點數仍誠實回報**，不整筆丟掉。"""
    _sheet = _FakeSheet([
        _HEADER,
        ["A1", "not-a-date", "1.0", "", "", ""],
        ["A1", "2026-08-01", "1.0", "", "", ""],
    ])
    _r = coverage_status(_sheet=_sheet)["A1"]
    assert _r["points"] == 2 and _r["span_days"] == 0


# ══════════════════════════════════════════════════════════════════════
# ③ 接線 —— 算出來了要真的接到畫面上（PROCESS.md §4）
# ══════════════════════════════════════════════════════════════════════

def _calls_named(path: Path, name: str) -> list:
    _tree = ast.parse(path.read_text(encoding="utf-8"))
    return [_n.lineno for _n in ast.walk(_tree)
            if isinstance(_n, ast.Call)
            and (getattr(_n.func, "id", None) == name
                 or getattr(_n.func, "attr", None) == name)]


def test_tab5_actually_calls_coverage_status():
    """接線測試：把 Tab⑤ 那段拿掉，本測試轉紅。

    這正是本 repo 反覆出現的「算對了但沒接出去」——`coverage_status` 若沒有
    consumer，它就只是一個沒人看得到的函式。
    """
    assert _calls_named(_TAB5, "coverage_status"), (
        "Tab⑤ 必須呼叫 coverage_status —— 否則「累了多少」依然沒有任何地方顯示")


def test_tab2_renders_the_merge_trace():
    """接線測試：Tab② 必須讀 `nav_history_merge` 這筆 trace 並渲染。"""
    _src = _TAB2.read_text(encoding="utf-8")
    assert '"nav_history_merge"' in _src, "Tab② 沒有讀 merge trace → 訊息等於沒產生"
    _tree = ast.parse(_src)
    _uses_note = any(
        isinstance(_n, ast.Subscript)
        and isinstance(_n.slice, ast.Constant) and _n.slice.value == "note"
        for _n in ast.walk(_tree))
    assert _uses_note, "Tab② 必須把 trace 的 note 印出來"


@pytest.mark.parametrize("path,marker", [
    ("ui/tab5_data_guard.py", "累積內容讀取失敗"),
    ("ui/tab5_data_guard.py", "讀不到就是不知道，不是沒有"),
])
def test_tab5_failure_modes_are_spelled_out(path, marker):
    """§1：讀失敗 / 讀不到都要講出來，不可留白讓人誤以為「沒在累積」。"""
    assert marker in (_ROOT / path).read_text(encoding="utf-8"), (
        f"{path} 少了「{marker}」這條誠實說明")
