# -*- coding: utf-8 -*-
"""⚙️ 設定→資料健康度 第一階段（BL-0540 Phase 1A；客戶 2026-11-21 逐字裁示 #7056447977）的行為守衛。

範圍：本地 New UI2 Preview 的 ⚙️ 唯讀頁＋同 session 快照。**只用合成 fixture（`market_stubs`），不取任何真實資料、不連網。**

AppTest 沒辦法用 `switch_page` 切 `st.navigation` 的頁，所以本檔把 `st.Page`／`st.navigation` 換成測試替身：
真實的 `app_preview.main()` 照跑（含 registry、chrome、renderer 登錄），只有「現在顯示哪一頁」由 session_state 決定。
⚠️ AppTest 不載入瀏覽器 CSS、也沒有真實導覽；390／1280 的版面、鍵盤與真實往返見 `test_ui_v3_settings_health_browser.py`。

固定的事實（對映裁示條文）：
1. 沒有快照 → 如實顯示「尚未評估」＋市場入口；**不呼叫 loader**；
2. 市場→設定：逐列 key／status／reason／source／as_of／fetched_at 與市場頁同一份快照一致；設定頁不增加 loader 次數；
3. 失敗／未評估／未設定／缺資料彼此不同；缺值保留缺值（不補 0、不補現在時間、不補他欄）；一個來源失敗不污染其他來源；
4. 同 session 往返不改內容；不同 session 互不洩漏（快照只在 session_state）；
5. 涵蓋範圍只有市場與利率，頁面明示「不是全站」；沒有整體／全站燈號；
6. 市場頁原揭露（▸ 各項資料狀態等）一字不變；導覽：只有 🌍、⚙️ 可進，💼／🔍／🤖 維持不可進。
"""
from __future__ import annotations

import ast
import dataclasses
import re
from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

import market_stubs as ms
import streamlit as st
from ui_v3.adapters import market_page as adapter
from ui_v3.pages import mkt
from ui_v3.pages import settings_health as page
from ui_v3.viewmodels import preview_wording as W
from ui_v3.viewmodels import settings_health as vm
from ui_v3.viewmodels.common import STATUS_FAILED, STATUS_MISSING, STATUS_OK, STATUS_UNDETERMINED
from ui_v3.viewmodels.market_page import DomainStatus

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "ui_v3" / "app_preview.py"
PAGE_KEY = "__uv3_test_page__"
STAMP = "2026-11-03T06:00:00+00:00"

OK_ROW = DomainStatus("taiex", "series_taiex", STATUS_OK, None, "Yahoo FAKE", "2026-11-02", STAMP)
FAILED_ROW = DomainStatus("sp500", "series_sp500", STATUS_FAILED, "fetch_failed", None, None, None)
UNDET_ROW = DomainStatus("vix", "series_vix", STATUS_UNDETERMINED, "too_few_points", None, None, None)
NOT_CONF_ROW = DomainStatus("us2y", "series_us2y", STATUS_FAILED, "not_configured", None, None, None)
FOUR_ROWS = (OK_ROW, FAILED_ROW, UNDET_ROW, NOT_CONF_ROW)     # Work #7056423617 的固定四列合成輸入


class Env:
    """一次測試的環境：loader 計數、頁替身。每個 AppTest（＝一個 session）各自 `visit`。"""

    def __init__(self, monkeypatch, *, view=None, table=None, rows=None):
        self.calls = 0
        self.recorded = {}
        view_obj, table_obj = ms.view(**(view or {})), ms.table(**(table or {}))

        def load(sources):
            self.calls += 1
            return view_obj, table_obj

        monkeypatch.setattr(adapter, "load", load)
        if rows is not None:
            real = adapter.build_market_page
            monkeypatch.setattr(adapter, "build_market_page",
                                lambda v, t, **kw: dataclasses.replace(real(v, t, **kw), statuses=tuple(rows)))
        real_page, real_nav, recorded = st.Page, st.navigation, self.recorded

        def spy_page(fn, **kw):
            page_obj = real_page(fn, **kw)
            recorded[kw["url_path"]] = (fn, page_obj)
            return page_obj

        class FakeNavigation:
            def __init__(self, pages, **kw):
                real_nav(pages, **kw)               # 真的登錄頁（page_link 只認已登錄的 st.Page）；之後由替身決定執行哪一頁
                self.pages = pages
                self.selected = recorded[st.session_state.get(PAGE_KEY, "mkt")]

            @property
            def title(self):
                return self.selected[1].title

            def run(self):
                self.selected[0]()

        monkeypatch.setattr(st, "Page", spy_page)
        monkeypatch.setattr(st, "navigation", FakeNavigation)

    def session(self, source=None):
        if source is not None:
            return streamlit_testing.AppTest.from_string(source, default_timeout=60)
        return streamlit_testing.AppTest.from_file(str(APP), default_timeout=60)

    def visit(self, at, slug):
        at.session_state[PAGE_KEY] = slug
        return at.run()


def md(at):
    return "\n".join(m.value for m in at.markdown)


_ROW_RE = re.compile(r'<div class="uv3-card uv3-health-row" ([^>]*)>(.*?)</div></div>', re.S)
_ATTR_RE = re.compile(r'data-([a-z-]+)="([^"]*)"')


def health_rows(at):
    out = []
    for attrs, body in _ROW_RE.findall(md(at)):
        d = dict(_ATTR_RE.findall(attrs))
        d["html"] = f"{attrs}|{body}"
        out.append(d)
    return out


def snapshot_of(at):
    return at.session_state[vm.SNAPSHOT_KEY]


# ── 1. 沒有快照 ───────────────────────────────────────────────────────────────

def test_direct_visit_without_snapshot_shows_not_evaluated_and_market_entry_and_never_loads(monkeypatch):
    env = Env(monkeypatch)
    at = env.visit(env.session(), "set")
    assert not at.exception
    assert [t.value for t in at.title] == ["⚙️ 設定"]
    text = md(at)
    assert 'data-health="no-snapshot"' in text and W.text("health_no_snapshot") in text
    assert 'data-health="scope"' not in text and not health_rows(at)         # 沒有範圍／計數／逐列：不偽造成功、不給總數
    assert env.calls == 0                                                      # 設定頁不取數
    assert vm.SNAPSHOT_KEY not in at.session_state
    assert len([e for e in at.get("page_link") if e.proto.label == "🌍 市場與趨勢"]) == 1   # 返回市場入口


# ── 2. 市場→設定 ─────────────────────────────────────────────────────────────

def test_market_then_settings_uses_the_same_snapshot_and_adds_no_loader_call(monkeypatch):
    env = Env(monkeypatch)
    at = env.session()
    env.visit(at, "mkt")
    assert env.calls == 1
    snap = snapshot_of(at)
    assert isinstance(snap, vm.HealthSnapshot) and tuple(r.key for r in snap.statuses) == ("taiex", "sp500", "vix", "us10y", "us2y")
    env.visit(at, "set")
    assert not at.exception and env.calls == 1                                 # 設定頁沒有再取數
    rows = health_rows(at)
    assert [r["health-key"] for r in rows] == [r.key for r in snap.statuses]
    expected_state = {STATUS_OK: "ok", STATUS_MISSING: "missing", STATUS_UNDETERMINED: "undetermined"}
    for row, src in zip(rows, snap.statuses):
        want = expected_state.get(src.status) or ("not_configured" if src.reason_code == "not_configured" else "failed")
        assert (row["health-state"], row["reason"], row["as-of"], row["fetched-at"]) == (
            want, src.reason_code or "", src.as_of or "", src.fetched_at or "")


def _check_scope(at):
    text = md(at)
    assert "市場與利率" in text and "不是全站" in text, "範圍揭露"      # 逐字字面值，不由字樣常數自我比對
    assert W.text("health_scope_note") in text
    assert 'data-covered="market,rates"' in text
    assert not re.search(r"全站(正常|健康)|整體(正常|健康)|資料齊全", text)


def test_scope_says_market_and_rates_only_and_not_site_wide_and_has_no_overall_light(monkeypatch):
    env = Env(monkeypatch)
    at = env.session()
    env.visit(at, "mkt")
    env.visit(at, "set")
    _check_scope(at)


def test_mutation_dropping_the_scope_disclosure_is_caught(monkeypatch):
    mutated = dict(W.PREVIEW_PENDING_WORDING)
    mutated["health_scope"] = dataclasses.replace(mutated["health_scope"], text="資料健康度（本次 {n} 項）")
    monkeypatch.setattr(W, "PREVIEW_PENDING_WORDING", mutated)
    env = Env(monkeypatch)
    at = env.session()
    env.visit(at, "mkt")
    env.visit(at, "set")
    with pytest.raises(AssertionError, match="範圍揭露"):
        _check_scope(at)


# ── 3. 四列固定輸入：失敗／未評估／未設定／缺值 ──────────────────────────────────────

def _check_four_rows(at):
    rows = {r["health-key"]: r for r in health_rows(at)}
    assert {k: v["health-state"] for k, v in rows.items()} == {
        "taiex": "ok", "sp500": "failed", "vix": "undetermined", "us2y": "not_configured"}
    assert rows["sp500"]["reason"] == "fetch_failed" and rows["vix"]["reason"] == "too_few_points" and rows["us2y"]["reason"] == "not_configured"
    assert 'data-status-key="fetch_failed"' in rows["sp500"]["html"] and "data-status-key=\"undetermined\"" in rows["vix"]["html"]
    assert 'data-status-key="not_configured"' in rows["us2y"]["html"]
    assert 'data-status-key="fetch_failed"' not in rows["vix"]["html"] + rows["us2y"]["html"]    # 彼此不冒充
    for key in ("sp500", "vix", "us2y"):
        assert rows[key]["as-of"] == "" and rows[key]["fetched-at"] == ""                       # 缺值保留缺值
        assert not re.search(r"\d{4}-\d{2}-\d{2}", rows[key]["html"])                          # 不補現在時間、不以他欄代替
        assert rows[key]["html"].count('data-status-key="missing"') == 3                       # 來源／資料日／取得時間 = ◇ 資料未備
    assert rows["taiex"]["as-of"] == "2026-11-02" and "2026-11-03 14:00" in rows["taiex"]["html"]  # 取得時間顯示為台北時間
    tally = re.search(r'data-health="tally">(.*?)</div>', md(at), re.S).group(1)
    assert W.text("health_tally", ok=1, gone=0, fail=1, unset=1, undet=1) in tally              # 取得1／缺資料0／失敗1／尚未設定1／尚未評估1


def test_four_fixed_rows_keep_failed_undetermined_not_configured_distinct_and_never_fill_dates(monkeypatch):
    env = Env(monkeypatch, rows=FOUR_ROWS)
    at = env.session()
    env.visit(at, "mkt")
    env.visit(at, "set")
    _check_four_rows(at)


def test_one_failed_source_does_not_pollute_the_others(monkeypatch):
    base_env = Env(monkeypatch)
    base = base_env.session()
    base_env.visit(base, "mkt")
    base_env.visit(base, "set")
    base_rows = {r["health-key"]: r for r in health_rows(base)}
    fail_env = Env(monkeypatch, view=dict(us="error"))
    failed = fail_env.session()
    fail_env.visit(failed, "mkt")
    fail_env.visit(failed, "set")
    fail_rows = {r["health-key"]: r for r in health_rows(failed)}
    assert set(base_rows) == set(fail_rows)
    changed = [k for k in base_rows if base_rows[k]["health-state"] != fail_rows[k]["health-state"]]
    assert changed and all(base_rows[k]["health-state"] == "ok" for k in changed)
    for key in base_rows:
        if key not in changed:                                                   # 沒失敗的來源逐字不變
            assert fail_rows[key]["html"] == base_rows[key]["html"], key
    for key in changed:
        assert fail_rows[key]["as-of"] == "" or fail_rows[key]["health-state"] != "ok"


# ── 4. 往返與 session 隔離 ───────────────────────────────────────────────────────

def test_round_trip_keeps_rows_identical_and_settings_visits_never_load(monkeypatch):
    env = Env(monkeypatch, rows=FOUR_ROWS)
    at = env.session()
    env.visit(at, "mkt")
    env.visit(at, "set")
    first = [r["html"] for r in health_rows(at)]
    calls_after_first_settings = env.calls
    env.visit(at, "mkt")                       # 回市場（市場頁自己會重新取數，既有行為）
    env.visit(at, "set")
    assert [r["html"] for r in health_rows(at)] == first                       # 同資料往返後逐列一致
    env.visit(at, "set")
    env.visit(at, "set")
    assert env.calls == calls_after_first_settings + 1                         # 唯一的新增取數來自「回市場」，設定頁 0 次


def _check_isolation(env, source=None):
    a, b = env.session(source), env.session(source)
    env.visit(a, "mkt")
    env.visit(b, "set")                        # b 沒有到過市場
    assert 'data-health="no-snapshot"' in md(b) and not health_rows(b) and vm.SNAPSHOT_KEY not in b.session_state, "快照跨 session 洩漏"
    env.visit(a, "set")
    assert len(health_rows(a)) == 4            # a 的快照不受 b 影響


def test_snapshot_is_per_session_and_never_leaks(monkeypatch):
    env = Env(monkeypatch, rows=FOUR_ROWS)
    _check_isolation(env)
    c, d = env.session(), env.session()
    env.visit(c, "mkt")
    env.visit(d, "mkt")
    assert snapshot_of(c) == snapshot_of(d) and snapshot_of(c) is not snapshot_of(d)   # 各自一份（值相同、不是同一個物件）


def test_no_global_cache_is_used_for_the_snapshot():
    """靜態：快照只走 `st.session_state`；app_preview 與設定頁不得用 `st.cache_*`（跨 session 共用私有狀態的入口）。"""
    for rel in ("ui_v3/app_preview.py", "ui_v3/pages/settings_health.py", "ui_v3/viewmodels/settings_health.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(r"cache_data|cache_resource|@st\.cache|lru_cache|functools\.cache", src), rel
    tree = ast.parse((ROOT / "ui_v3/viewmodels/settings_health.py").read_text(encoding="utf-8"))
    mutable = [n for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.value, (ast.List, ast.Set))]
    assert not mutable                          # 模組層沒有可變容器（dict 常數不被函式寫入；見下一個測試）


def test_module_level_dict_constants_are_never_mutated_by_rendering(monkeypatch):
    before = (dict(vm.DEFAULT_ROW_CATEGORY), dict(vm.PHASE_1A_COVERAGE))
    env = Env(monkeypatch, rows=FOUR_ROWS)
    at = env.session()
    env.visit(at, "mkt")
    env.visit(at, "set")
    assert (dict(vm.DEFAULT_ROW_CATEGORY), dict(vm.PHASE_1A_COVERAGE)) == before


# ── 5. 市場頁原揭露一字不變 ──────────────────────────────────────────────────────

def test_market_page_disclosures_are_unchanged_next_to_the_settings_page(monkeypatch):
    env = Env(monkeypatch, rows=FOUR_ROWS)
    at = env.session()
    env.visit(at, "mkt")
    assert not at.exception
    expanders = [e for e in at.expander if e.label == W.text("status_group_title")]
    assert len(expanders) == 1
    assert "".join(m.value for m in expanders[0].markdown) == "".join(mkt.status_row_html(r) for r in FOUR_ROWS)
    text = md(at)
    assert W.text("source_limits_title") in text or any(W.text("source_limits_title") in e.label for e in at.expander)
    assert 'data-health' not in text and 'uv3-health-row' not in text          # 設定頁內容不滲進市場頁（並存，不是搬遷）
    # 進出設定頁不改市場頁的揭露
    env.visit(at, "set")
    env.visit(at, "mkt")
    again = [e for e in at.expander if e.label == W.text("status_group_title")]
    assert "".join(m.value for m in again[0].markdown) == "".join(mkt.status_row_html(r) for r in FOUR_ROWS)


# ── 6. 導覽 ─────────────────────────────────────────────────────────────────

def test_only_market_search_and_settings_are_navigable_on_all_three_pages(monkeypatch):
    env = Env(monkeypatch)
    at = env.session()
    for slug in ("mkt", "exp", "set"):
        env.visit(at, slug)
        assert not at.exception
        links = sorted(l.proto.label for l in at.get("page_link"))
        expected = sorted(["市場與趨勢", "市場", "找基金", "找基金", "設定", "設定"] + (["🌍 市場與趨勢"] if slug == "set" else []))
        assert links == expected, (slug, links)
        side = "\n".join(m.value for m in at.sidebar.markdown)
        for disabled in ("ast", "ai"):
            assert f'data-nav="{disabled}"' in side and 'aria-disabled="true"' in side
        assert all(f'data-nav="{slug_}"' not in side for slug_ in ("set", "mkt", "exp"))     # 三個可進頁不是禁用項


# ── 純 HTML：renderer 的列契約（沒有 Streamlit 也可跑）────────────────────────────

def _row(**kw):
    base = dict(key="taiex", category_key="market", label_key="series_taiex", state=vm.STATE_OK, reason_code=None,
                source="Yahoo FAKE", as_of="2026-11-02", fetched_at=STAMP, gaps=())
    base.update(kw)
    return vm.HealthRow(**base)


def test_row_html_distinguishes_all_five_states():
    keys = {}
    for state, reason in ((vm.STATE_OK, None), (vm.STATE_MISSING, "missing"), (vm.STATE_FAILED, "fetch_failed"),
                          (vm.STATE_NOT_CONFIGURED, "not_configured"), (vm.STATE_UNDETERMINED, "too_few_points")):
        ok = state == vm.STATE_OK
        html = page.row_html(_row(state=state, reason_code=reason, source="S" if ok else None, as_of="2026-11-02" if ok else None,
                                  fetched_at=STAMP if ok else None))
        keys[state] = re.findall(r'<span class="uv3-st[^"]*" data-status-key="([^"]+)"', html)[0]
    assert keys == {"ok": "ok", "missing": "missing", "failed": "fetch_failed", "not_configured": "not_configured", "undetermined": "undetermined"}


def test_row_html_marks_missing_fields_and_ok_row_gaps_without_filling():
    html = page.row_html(_row(source=None, as_of=None, fetched_at=None, gaps=("source", "as_of", "fetched_at")))
    assert html.count('data-status-key="missing"') == 3 and 'data-gaps="source,as_of,fetched_at"' in html
    assert not re.search(r"\d{4}-\d{2}-\d{2}", html)


def test_row_html_escapes_hostile_text_and_never_claims_taipei_time_for_unparseable_stamp():
    hostile = page.row_html(_row(source='<script>alert(1)</script>"&'))
    assert "<script>" not in hostile and "&lt;script&gt;" in hostile
    naive = page.row_html(_row(fetched_at="2026-11-03 06:00:00"))         # 不帶時區：不猜、不寫成台北時間
    visible = re.sub(r'data-[a-z-]+="[^"]*"', "", naive)                  # 資料屬性不是可見文字
    assert "2026-11-03 06:00" not in visible and 'data-status-key="undetermined"' in naive


def test_row_html_depends_only_on_its_own_row():
    assert page.row_html(_row()) == page.row_html(_row())
    assert page.row_html(_row(key="us10y", label_key="series_us10y")) != page.row_html(_row())


# ── 變異負控 ────────────────────────────────────────────────────────────────

def _check_settings_semantics(env, at):
    env.visit(at, "mkt")
    before = env.calls
    env.visit(at, "set")
    assert env.calls == before, "設定頁取數"
    rows = {r["health-key"]: r for r in health_rows(at)}
    for key in ("sp500", "vix", "us2y"):
        assert rows[key]["health-state"] != "ok", key
        assert not re.search(r"\d{4}-\d{2}-\d{2}", rows[key]["html"]), "非 ok 列出現日期（補值）"
    assert rows["sp500"]["health-state"] != rows["vix"]["health-state"] != rows["us2y"]["health-state"]


def test_check_passes_on_the_real_implementation(monkeypatch):
    env = Env(monkeypatch, rows=FOUR_ROWS)
    _check_settings_semantics(env, env.session())


def _mutant(old, new):
    src = APP.read_text(encoding="utf-8")
    assert src.count(old) == 1, old
    return src.replace(old, new)


def test_mutation_settings_page_loading_data_is_caught(monkeypatch):
    source = _mutant("    snapshot = st.session_state.get(settings_health.SNAPSHOT_KEY)\n",
                     "    from ui_v3.adapters import market_page as _a\n    _a.load([])\n    snapshot = st.session_state.get(settings_health.SNAPSHOT_KEY)\n")
    env = Env(monkeypatch, rows=FOUR_ROWS)
    with pytest.raises(AssertionError, match="設定頁取數"):
        _check_settings_semantics(env, env.session(source))


def test_mutation_filling_missing_fetched_at_with_now_is_caught(monkeypatch):
    monkeypatch.setattr(page, "_fetched_html", lambda stamp: "2026-11-21 03:00")
    env = Env(monkeypatch, rows=FOUR_ROWS)
    with pytest.raises(AssertionError, match="補值"):
        _check_settings_semantics(env, env.session())


def test_mutation_failed_rendered_as_ok_is_caught(monkeypatch):
    real_state = page._state_html
    monkeypatch.setattr(page, "_state_html", lambda row: real_state(dataclasses.replace(
        row, state=vm.STATE_OK, reason_code=None, source="x", as_of="2026-01-01", fetched_at=STAMP, gaps=())) if row.state == vm.STATE_FAILED else real_state(row))
    env = Env(monkeypatch, rows=FOUR_ROWS)
    at = env.session()
    env.visit(at, "mkt")
    env.visit(at, "set")
    with pytest.raises(AssertionError):
        _check_four_rows(at)                   # 真實守衛函式本身（與四列測試同一個）必須轉紅


def test_mutation_leaking_snapshot_through_process_global_is_caught(monkeypatch):
    """變異：把快照另存到行程層全域（所有 session 共用）→ 真實隔離檢查必須轉紅。"""
    glob = "    import sys, types; _G = sys.modules.setdefault('uv3_leak', types.SimpleNamespace(snap=None))"
    store = _mutant("    chrome.render_status(status)   # Status Bar",
                    glob + "; _G.snap = st.session_state[settings_health.SNAPSHOT_KEY]\n    chrome.render_status(status)   # Status Bar")
    leaky = store.replace("    snapshot = st.session_state.get(settings_health.SNAPSHOT_KEY)\n",
                          "    import sys\n    _g = sys.modules.get('uv3_leak')\n    snapshot = st.session_state.get(settings_health.SNAPSHOT_KEY) or (_g.snap if _g else None)\n")
    assert leaky != store
    monkeypatch.delitem(__import__("sys").modules, "uv3_leak", raising=False)
    env = Env(monkeypatch, rows=FOUR_ROWS)
    with pytest.raises(AssertionError, match="跨 session 洩漏"):
        _check_isolation(env, leaky)
    monkeypatch.delitem(__import__("sys").modules, "uv3_leak", raising=False)
    _check_isolation(Env(monkeypatch, rows=FOUR_ROWS))          # 真實實作：同一個檢查通過


# ── 舊快照不得殘留（稽核 F）──────────────────────────────────────────────────

def test_failed_market_load_does_not_leave_a_stale_snapshot(monkeypatch):
    env = Env(monkeypatch, rows=FOUR_ROWS)
    at = env.session()
    env.visit(at, "mkt")
    assert vm.SNAPSHOT_KEY in at.session_state
    monkeypatch.setattr(adapter, "load", lambda sources: (_ for _ in ()).throw(RuntimeError("fake upstream down")))
    env.visit(at, "mkt")
    assert at.exception and vm.SNAPSHOT_KEY not in at.session_state      # 這次沒取到 → 不留上一次的快照
    env.visit(at, "set")
    assert 'data-health="no-snapshot"' in md(at) and not health_rows(at)
