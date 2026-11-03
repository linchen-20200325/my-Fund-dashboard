# -*- coding: utf-8 -*-
"""客戶 2026-11-03 裁示（`DEC-2026-11-03-11` 第一、三項）：降級情境的第一屏仍須在 frozen 44 之十九其一之一第 2 條的 ≤5 之內。

**計法**（`docs/v2/81` 第 10.2 節；本檔鎖它）：第一屏＝Status Bar＋摘要區＋Primary 區（圖與圖下逐序列資訊），也就是第一張 Secondary／依據卡之前的
所有頁級內容；名額＝頁級 chip（`uv3-chip`，**含 Status Bar 與側欄裡的**）＋頁級核心數字（`uv3-evidence` 一格一個；格內以狀態 chip 取代數字時只算一格、
不重複計 chip）。期間／檢視切換是 display control 不計。逐序列的狀態改以一行純文字摘要（`data-summary="series-status"`）呈現。
同時鎖：失敗與尚未設定與資料未備不合併、不出現「正常」、詳細原因仍完整保留、Status Bar／側欄不放 chip 形式元素。
⚠️ AppTest 不載入瀏覽器 CSS，本檔計的是 DOM 名額；390／1280 真瀏覽器的可視計數見 `docs/evidence/bl0536_shell_h5_2026-11-03/measurements.jsonl`。
負控一律在記憶體內現編。
"""
from __future__ import annotations

import html as htmllib
import re
from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

import market_stubs as ms
from shared.ui_semantics import rules
from ui_v3.adapters import market_page as adapter
from ui_v3.pages import mkt

ROOT = Path(__file__).resolve().parents[2]
APP = str(ROOT / "ui_v3" / "app_preview.py")
_NO_RATES = ("credit_spread_pct", "term_spread_pct", "policy_rate_pct")
_ALL = ("vol_index",) + _NO_RATES

SCENARIOS = {
    "complete": lambda: (ms.view(), ms.table()),
    "tw_missing": lambda: (ms.view(tw="missing"), ms.table()),
    "us_failed": lambda: (ms.view(us="error"), ms.table()),
    "both_missing": lambda: (ms.view(tw="missing", us="missing"), ms.table()),
    "both_failed": lambda: (ms.view(tw="error", us="error", vx="error"), ms.table()),
    "all_missing": lambda: (ms.view(tw="missing", us="missing", vx="missing"), ms.table(drop=_ALL)),
    "all_failed": lambda: (ms.view(tw="error", us="error", vx="error"), ms.table(errors={k: "x" for k in _ALL}, drop=_ALL)),
    "no_rates_key": lambda: (ms.view(key=""), ms.table(errors={k: "x" for k in _NO_RATES}, drop=_NO_RATES)),
    "stale": lambda: (ms.view(us_dates=ms.weekdays("2021-06-01", "2026-10-30")), ms.table()),
}
VIEWS = ("compare", "vix", "us10y", "us2y")


def _run(monkeypatch, name, view_key):
    view, table = SCENARIOS[name]()
    monkeypatch.setattr(adapter, "load", lambda sources: (view, table))
    at = streamlit_testing.AppTest.from_file(APP, default_timeout=60)
    at.session_state[mkt.KEY_VIEW] = view_key
    return at.run()


def first_screen_html(at) -> str:
    """Status Bar 起、第一張 Secondary／依據卡（`data-card=`）之前的所有主區 markdown。"""
    parts = []
    for m in at.markdown:
        if 'data-card="' in m.value:
            break
        parts.append(m.value)
    return "\n".join(parts)


def slots(html: str) -> tuple:
    """(獨立 chip 數, 核心數字格數)。格內的 chip 屬於該格，不另計。"""
    total_chips = len(re.findall(r'class="uv3-chip', html))
    cell_count = len(re.findall(r'class="uv3-evidence"', html))
    in_cells = sum(len(re.findall(r'class="uv3-chip', c)) for c in _evidence_cells(html))
    return total_chips - in_cells, cell_count


def _evidence_cells(html: str) -> list:
    """每個 `uv3-evidence` span 的內文（含巢狀 chip span；以 span 深度配對）。"""
    out = []
    for m in re.finditer(r'<span class="uv3-evidence"', html):
        depth, i = 0, m.start()
        for t in re.finditer(r"<span\b|</span>", html[i:]):
            depth += 1 if t.group().startswith("<span") else -1
            if depth == 0:
                out.append(html[i:i + t.end()])
                break
    return out


def plain(html: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", html))).strip()


@pytest.mark.parametrize("name", list(SCENARIOS))
@pytest.mark.parametrize("view_key", VIEWS)
def test_first_screen_slots_stay_within_five_in_every_scenario_and_view(monkeypatch, name, view_key):
    at = _run(monkeypatch, name, view_key)
    assert not at.exception
    region = first_screen_html(at)
    chips, cells = slots(region)
    assert cells == 2 and chips == 3, (name, view_key, chips, cells)         # 市場狀態、是否需注意、資料新鮮度＋重要依據兩格
    assert chips + cells <= 5
    # Status Bar 與側欄：沒有 chip 形式元素、沒有核心數字元素（客戶裁示第一項）
    bar = re.search(r'<div class="uv3-statusbar".*?</div>', region, flags=re.S).group(0)
    side = "\n".join(m.value for m in at.sidebar.markdown)
    for part in (bar, side):
        assert "uv3-chip" not in part and "uv3-evidence" not in part


@pytest.mark.parametrize("name", list(SCENARIOS))
@pytest.mark.parametrize("view_key", VIEWS)
def test_degraded_first_screen_keeps_a_visible_warning_and_never_says_normal(monkeypatch, name, view_key):
    at = _run(monkeypatch, name, view_key)
    region = first_screen_html(at)
    text = plain(region)
    assert "正常" not in text and "資料齊" not in text
    degraded = name != "complete" and name != "stale"
    status_bar = plain(re.search(r'<div class="uv3-statusbar".*?</div>', region, flags=re.S).group(0))
    if name in ("complete", "stale"):
        assert "未取得" not in status_bar
    if degraded:
        assert "部分資料未取得" in status_bar or "項已取得" in status_bar          # 頁級必要狀態：Status Bar 的計數句保留
        if name in ("both_failed", "all_failed", "us_failed"):
            assert "項取數失敗" in status_bar                                       # 失敗警示保留，且不併入「未取得」
        if name == "no_rates_key":
            assert "項取數失敗" not in status_bar                                   # 尚未設定不是取數失敗（44 之十二其二第 1 條）


def _summary_rows(at) -> list:
    return re.findall(r'<div class="uv3-row" data-summary="series-status">(.*?)</div>', first_screen_html(at), flags=re.S)


@pytest.mark.parametrize("view_key", VIEWS)
def test_series_status_summary_is_at_most_one_plain_text_row_that_keeps_each_status_separate(monkeypatch, view_key):
    for name, want, forbid in (("both_failed", "取數失敗", "資料未備"), ("both_missing", "資料未備", "取數失敗")):
        rows = _summary_rows(_run(monkeypatch, name, view_key))
        assert len(rows) <= 1 and all("uv3-chip" not in r for r in rows), (name, view_key)
        if view_key == "compare":                              # 比較檢視的兩條序列都降級 → 必有一行摘要，且狀態字樣不互相冒充
            assert len(rows) == 1 and want in plain(rows[0]) and forbid not in plain(rows[0]), (name, rows)


def test_failed_not_configured_and_missing_stay_three_distinct_texts_in_the_summary(monkeypatch):
    at = _run(monkeypatch, "no_rates_key", "us10y")
    row = re.search(r'data-summary="series-status">(.*?)</div>', first_screen_html(at), flags=re.S).group(1)
    assert rules.NOT_CONFIGURED_RATES_SOURCE_TEXT in plain(row) and "取數失敗" not in plain(row)   # 第一次出現是完整句，不是失敗
    at = _run(monkeypatch, "us_failed", "compare")
    assert "取數失敗" in plain(re.search(r'data-summary="series-status">(.*?)</div>', first_screen_html(at), flags=re.S).group(1))
    at = _run(monkeypatch, "tw_missing", "compare")
    row = plain(re.search(r'data-summary="series-status">(.*?)</div>', first_screen_html(at), flags=re.S).group(1))
    assert "資料未備" in row and "取數失敗" not in row and rules.entry("not_configured").wording not in row


@pytest.mark.parametrize("name", ["both_failed", "all_missing", "no_rates_key", "tw_missing", "all_failed"])
def test_full_per_series_detail_is_still_in_the_status_expander(monkeypatch, name):
    """詳細原因不得隱藏：`▸ 各項資料狀態` 仍逐項列出每個登錄項目，非 ok 的項目各自帶自己的狀態字樣（失敗／尚未設定／資料未備不互相冒充）。"""
    at = _run(monkeypatch, name, "compare")
    built = adapter.build_market_page(*SCENARIOS[name](), period="1Y")
    expander = [e for e in at.expander if e.label == mkt.W.text("status_group_title")]
    assert len(expander) == 1
    text = plain("\n".join(m.value for m in expander[0].markdown))
    non_ok = [r for r in built.statuses if r.status != "ok"]
    assert non_ok, "情境失效：沒有任何降級項"
    for row in built.statuses:
        assert mkt.W.text(row.label_key) in text, (name, row.label_key)
    for row in non_ok:
        if row.status == "failed" and row.reason_code == "not_configured":
            assert rules.entry("not_configured").wording in text
        elif row.status == "failed":
            assert "取數失敗" in text
        elif row.status == "missing":
            assert rules.entry("missing").wording in text


def test_slot_counter_catches_the_old_per_series_chip_layout(monkeypatch):
    """負控（記憶體內）：把逐序列摘要換回舊的每序列一枚 chip，both_missing 的第一屏必須超過 5，計數器必須抓到。"""
    def old_layout(notes):
        return [mkt.note_html(n) for n in notes]
    monkeypatch.setattr(mkt, "primary_notes_html", old_layout)
    at = _run(monkeypatch, "both_missing", "compare")
    chips, cells = slots(first_screen_html(at))
    assert chips + cells > 5, (chips, cells)


def test_slot_counter_counts_a_chip_inside_the_status_bar():
    """負控：Status Bar 若被放進一枚 chip，名額必須多一個（不得以位於 Shell 為由排除）。"""
    html = ('<div class="uv3-statusbar"><span class="uv3-chip uv3-tone-grey">x</span></div>'
            '<span class="uv3-chip">a</span><span class="uv3-chip">b</span><span class="uv3-chip">c</span>'
            '<span class="uv3-evidence" data-key="taiex">台股 <span class="uv3-chip">◇</span></span>'
            '<span class="uv3-evidence" data-key="sp500">S 近1Y +1.00%</span>')
    chips, cells = slots(html)
    assert (chips, cells) == (4, 2) and chips + cells == 6


# ───────── 圖下逐序列摘要行的序列名必須轉義（`primary_notes_html` 的 `escape(label)`） ─────────

_INJECT = "<b>x</b>"


def _notes_with_injected_label(monkeypatch, fn=None) -> str:
    """測試端注入含標籤的序列名與原因代碼，回傳圖下摘要行的渲染輸出（`fn` 預設為正式的 `primary_notes_html`）。"""
    from ui_v3.viewmodels.common import STATUS_FAILED, STATUS_MISSING, STATUS_UNDETERMINED
    from ui_v3.viewmodels.market_page import SeriesNote

    real_text = mkt.W.text
    monkeypatch.setattr(mkt.W, "text", lambda key, *a, **kw: _INJECT if key.startswith("series_") else real_text(key, *a, **kw))
    notes = [
        SeriesNote("taiex", STATUS_MISSING, "missing", None, None, None, None),
        SeriesNote("sp500", STATUS_FAILED, _INJECT, None, None, None, None),
        SeriesNote("vix", STATUS_UNDETERMINED, _INJECT, None, None, None, None),
    ]
    return "".join((fn or mkt.primary_notes_html)(notes))


def test_series_summary_row_escapes_injected_series_label_and_reason(monkeypatch):
    out = _notes_with_injected_label(monkeypatch)
    assert 'data-summary="series-status"' in out
    assert _INJECT not in out, "序列名或原因代碼含標籤時，摘要行輸出不得出現未轉義的 <b>"
    assert "&lt;b&gt;x&lt;/b&gt;" in out, "序列名應以轉義後的文字呈現（不是被吞掉）"


def test_negative_control_unescaped_series_label_in_summary_row_turns_red(monkeypatch):
    """負控（記憶體內現編 mutant）：把 `primary_notes_html` 內的 `escape(label)` 換成 `label`，上面的斷言必須轉紅。"""
    import inspect
    import textwrap

    src = textwrap.dedent(inspect.getsource(mkt.primary_notes_html))
    assert src.count("escape(label)") >= 1
    ns = dict(vars(mkt))
    exec(src.replace("escape(label)", "label"), ns)
    mutant_out = _notes_with_injected_label(monkeypatch, ns["primary_notes_html"])
    assert _INJECT in mutant_out, "mutant 未產生未轉義輸出：守衛抓不到拿掉 escape(label) 的改動"
