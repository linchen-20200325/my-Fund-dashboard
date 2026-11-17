# -*- coding: utf-8 -*-
"""NAS 中繼站診斷 renderer 守衛（純 HTML 字串；不需要 Streamlit、不連網、不讀憑證）。

驗：降級直連醒目且不含「連線成功」字樣／不與成功同色；不洩任何污染 sentinel（密碼、使用者、主機、網址）；
沒有硬寫中文字串（AST）、docstring 不含舊 PoC 路徑、沒有 hex 色碼、沒有 3.12 專用語法；每頁都有暫行字樣提示；
沒有任何按鈕或連結（沒有假的「立即測試」）；看得見的字沒有工程詞。負控一律在記憶體內現編。
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
from html.parser import HTMLParser

import pytest

import nas_diag_support as sup
import ui_v3_guard_lib as lib
from shared.ui_semantics import rules
from ui_v3.design import tokens
from ui_v3.pages import nas_diag as pg
from ui_v3.viewmodels import nas_diag as vm
from ui_v3.viewmodels import nas_diag_wording as W

SRC_REL = "ui_v3/pages/nas_diag.py"
SRC = lib.read(lib.ROOT / SRC_REL)
SIDS = list(sup.SCENARIO_KWARGS)


def html_of(sid: str) -> str:
    return pg.page_html(vm.classify(vm.NasDiagObservation(**sup.kwargs(sid))))


class _Visible(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._skip += 1
        self.parts += [v for k, v in attrs if k in ("aria-label", "title", "alt") and v]

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def visible(html: str) -> str:
    parser = _Visible()
    parser.feed(html)
    return " ".join(parser.parts)


def text_of(key: str) -> str:
    return W.NAS_DIAG_WORDING[key].text


# ───────────────────────── 降級直連 ≠ 連線成功 ─────────────────────────

def degraded_vs_ok_violations(degraded_html: str, ok_html: str) -> list:
    """降級直連必須：有醒目橫幅、含「NAS 並未正常」、不含連線成功字樣、徽章 tone 與成功不同。純函式，供真測試與變異驗證共用。"""
    bad = []
    if 'class="uv3n-banner"' not in degraded_html:
        bad.append("沒有醒目橫幅")
    if text_of("concl_degraded") not in visible(degraded_html):
        bad.append("缺少「NAS 失敗，改走直連；NAS 並未正常」")
    if text_of("state_ok") in visible(degraded_html):
        bad.append("降級直連畫面出現「連線成功」字樣")
    tone = lambda h: re.search(r'uv3n-badge uv3n-tone-(\w+)', h).group(1)   # noqa: E731
    if tone(degraded_html) == tone(ok_html):
        bad.append("降級直連徽章與連線成功同色")
    badge = lambda h: re.search(r'data-badge="state"[^>]*>(.*?)</span></span>', h).group(1)   # noqa: E731
    if visible(badge(degraded_html)) == visible(badge(ok_html)):
        bad.append("降級直連徽章與連線成功同詞")
    return bad


@pytest.mark.parametrize("sid", ["degraded_direct", "blocked_403_then_direct"])
def test_degraded_direct_is_prominent_and_never_looks_like_success(sid):
    deg, ok = html_of(sid), html_of("nas_ok")
    assert degraded_vs_ok_violations(deg, ok) == []
    assert 'data-state="degraded_direct"' in deg and 'data-axis="nas" data-health="failed"' in deg
    assert "uv3n-tone-yellow" in deg and "uv3n-tone-neutral" in ok
    assert 'role="status"' in deg and text_of("concl_degraded") in visible(deg)


def test_degraded_check_negative_controls_turn_red():
    deg, ok = html_of("degraded_direct"), html_of("nas_ok")
    as_success_word = deg.replace(text_of("state_degraded"), text_of("state_ok"))
    assert degraded_vs_ok_violations(as_success_word, ok)
    as_success_color = deg.replace("uv3n-tone-yellow", "uv3n-tone-neutral")
    assert degraded_vs_ok_violations(as_success_color, ok)
    no_banner = deg.replace('class="uv3n-banner"', 'class="uv3-row"')
    assert degraded_vs_ok_violations(no_banner, ok)
    leaked_success = deg + f"<p>{text_of('state_ok')}</p>"
    assert degraded_vs_ok_violations(leaked_success, ok)


def test_success_page_has_no_degraded_banner_and_each_state_has_its_own_label():
    ok = html_of("nas_ok")
    assert "uv3n-banner" not in ok and text_of("state_degraded") not in visible(ok)
    labels = {}
    for sid in SIDS:
        view = vm.classify(vm.NasDiagObservation(**sup.kwargs(sid)))
        kind, key = W.STATE_LABEL_SOURCE[view.state]
        labels[view.state] = rules.entry(key).wording if kind == "rule" else text_of(key)
        assert labels[view.state] in visible(html_of(sid))
    assert len(set(labels.values())) == 6   # 六態六個不同的字


# ───────────────────────── 兩軸卡片、路徑、最近檢查 ─────────────────────────

@pytest.mark.parametrize("sid", SIDS)
def test_every_scenario_shows_both_axes_route_last_check_and_pending_notices(sid):
    html = html_of(sid)
    view = vm.classify(vm.NasDiagObservation(**sup.kwargs(sid)))
    assert html.count('data-axis="nas"') == 1 and html.count('data-axis="target"') == 1
    assert f'data-axis="nas" data-health="{view.nas_health}"' in html and f'data-axis="target" data-health="{view.target_health}"' in html
    assert 'data-row="route"' in html and 'data-block="last-check"' in html
    assert 'data-pending-wording="pending_notice"' in html and 'data-pending-wording="live_test_note"' in html
    assert "即時測試尚未核准，本預覽為離線注入結果" in visible(html) and "暫行字樣，尚未核准" in visible(html)
    assert html.index('data-block="nas-status"') < html.index('data-block="axes"') < html.index('data-block="last-check"')


def test_route_shows_the_actual_path_and_untested_is_not_a_path():
    expect = {"nas_ok": "NAS 中繼", "degraded_direct": "降級直連", "not_configured": "未測試", "configured_untested": "未測試",
              "auth_407": "沒有可用路徑", "contradiction": "⬜ 無法判定"}
    for sid, word in expect.items():
        row = re.search(r'data-row="route">(.*?)</div>', html_of(sid)).group(1)
        assert word in visible(row), (sid, visible(row))


def test_missing_status_and_latency_render_the_approved_missing_wording_never_zero():
    for sid in ("not_configured", "configured_untested", "contradiction"):
        html = html_of(sid)
        status_row = re.search(r'data-row="status-code">(.*?)</div>', html).group(1)
        latency_row = re.search(r'data-row="latency">(.*?)</div>', html).group(1)
        assert rules.MISSING_TEXT in visible(status_row) and rules.MISSING_TEXT in visible(latency_row)
        assert not re.search(r"(?<![\d.])0(?![\d])", visible(status_row).replace(text_of("label_status_code"), ""))
    ok = html_of("nas_ok")
    assert "200" in ok and "380 " in ok and rules.MISSING_TEXT in visible(html_of("timeout").split('data-row="status-code"')[1].split("</div>")[0])


def test_approved_wording_is_reused_not_copied():
    assert 'data-status-key="not_configured"' in html_of("not_configured") and rules.entry("not_configured").wording in visible(html_of("not_configured"))
    assert 'data-status-key="undetermined"' in html_of("contradiction") and rules.entry("undetermined").wording in visible(html_of("contradiction"))
    assert 'data-status-key="missing"' in html_of("configured_untested")
    for key in ("state_not_tested", "state_ok", "state_failed", "state_degraded"):
        assert f'data-pending-wording="{key}"' in "".join(html_of(s) for s in SIDS)


def test_causes_are_human_and_say_which_side_for_the_failure_scenarios():
    assert "代理驗證失敗" in visible(html_of("auth_407")) and "NAS 這一段" in visible(html_of("auth_407"))
    assert "目標網站這一段" in visible(html_of("blocked_403")) and "不是 NAS 斷線" in visible(html_of("blocked_403"))
    assert "NAS 這一段" in visible(html_of("blocked_403_then_direct")) and "目標網站這一段" not in visible(html_of("blocked_403_then_direct"))
    both = visible(html_of("both_failed"))
    assert "NAS 這一段" in both and "目標網站這一段" in both
    assert "不要為了通過而關閉憑證驗證" in visible(html_of("tls"))
    for sid in ("nas_ok", "not_configured", "configured_untested", "contradiction"):
        assert 'data-block="causes"' not in html_of(sid)   # 沒有失敗分類就不寫「原因」，更不寫「沒有原因」


# ───────────────────────── 不洩密 ─────────────────────────

def leaks_of(html: str) -> list:
    return [t for t in sup.POISON_TOKENS if t in html] + re.findall(r"https?://|[\w.-]+:\d{4}\b|[^\s/@:]+:[^\s/@]+@", html)


@pytest.mark.parametrize("sid", SIDS)
def test_no_sentinel_url_host_or_credential_shape_in_any_scenario_output(sid):
    assert leaks_of(html_of(sid)) == []


def test_leak_detector_negative_control_and_poisoned_input_never_reaches_output():
    assert leaks_of("<p>" + sup.POISON_URL + "</p>")
    assert leaks_of("<p>" + sup.POISON_HOST + "</p>") and leaks_of("<p>h:3128</p>")
    for sid in SIDS:
        kw = sup.kwargs(sid)
        kw["target_label"] = sup.POISON_URL
        with pytest.raises(ValueError):
            vm.NasDiagObservation(**kw)   # 污染值根本進不了 view model，當然進不了輸出
    # 渲染層自己也不收別的型別
    with pytest.raises(TypeError):
        pg.page_html({"state": "ok"})


@pytest.mark.parametrize("sid", SIDS)
def test_no_button_link_or_form_control_so_there_is_no_fake_test_button(sid):
    html = html_of(sid)
    assert interactive_elements(html) == []
    assert "立即測試" not in visible(html)


def interactive_elements(html: str) -> list:
    return re.findall(r"<\s*(?:button|a|input|select|textarea|form|summary|details|script|iframe)\b|\bhref\s*=|\bonclick\s*=|\btabindex\s*=|javascript:", html, re.I)


def test_interactive_element_detector_negative_control():
    for bad in ("<button>x</button>", '<a href="#">x</a>', "<input>", "<details><summary>x</summary></details>", '<div onclick="f()">',
                '<div tabindex="0">', "<form>", "<script>"):
        assert interactive_elements(html_of("nas_ok") + bad), bad


# ───────────────────────── 看得見的字沒有工程詞 ─────────────────────────

_ENV_SHAPE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_ENGINEERING = re.compile(
    r"aggregation rule|Traceback|\w*Exception\b|\w*Error\b|Errno|\bNone\b|\bNaN\b|HTTP \d{3}|st\.secrets|os\.environ|\.py\b"
    r"|\b(?:services|repositories|infra|shared|ui_v2|ui_v3)[./]|proxy_|\bPROXY\b|\bheaders?\b", re.IGNORECASE)


def engineering_leaks(text: str) -> list:
    return [m.group(0) for rx in (_ENV_SHAPE, _SNAKE, _ENGINEERING) for m in rx.finditer(text)]


@pytest.mark.parametrize("sid", SIDS)
def test_visible_text_has_no_engineering_information(sid):
    assert engineering_leaks(visible(html_of(sid))) == []


def test_engineering_detector_negative_control():
    for bad in ("proxy" + "_auth_407", "PROXY" + "_URL", "Value" + "Error: x", "HTTP 40" + "3", "infra" + ".proxy", "Trace" + "back"):
        assert engineering_leaks(bad), bad
    assert engineering_leaks("代理驗證失敗（407）：NAS 這一段 MoneyDJ ◇ 資料未備") == []


def test_every_wording_text_passes_the_engineering_detector():
    assert {k: engineering_leaks(w.text) for k, w in W.NAS_DIAG_WORDING.items() if engineering_leaks(w.text)} == {}


# ───────────────────────── 原始碼守衛 ─────────────────────────

_CJK = re.compile(r"[　-鿿＀-￯]")


def hardcoded_cjk_literals(source: str) -> list:
    tree = ast.parse(source)
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant)}
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings and _CJK.search(n.value)]


def test_renderer_has_no_hardcoded_cjk_string_and_the_scan_negative_control_turns_red():
    assert hardcoded_cjk_literals(SRC) == []
    assert hardcoded_cjk_literals('def f():\n    """文件字串不算"""\n    return "硬寫中文"\n') == ["硬寫中文"]
    assert hardcoded_cjk_literals('def f():\n    """只有文件字串"""\n    return 1  # 註解中文\n') == []


def test_renderer_and_viewmodels_do_not_mention_the_old_poc_path_anywhere_even_in_docstrings():
    for rel in (SRC_REL, "ui_v3/viewmodels/nas_diag.py", "ui_v3/viewmodels/nas_diag_wording.py"):
        text = lib.read(lib.ROOT / rel)
        assert not re.search(r"(?<![A-Za-z0-9_])poc/", text) and "dual_theme_isolated" not in text, rel
    assert re.search(r"(?<![A-Za-z0-9_])poc/", "see poc" + "/x.py")   # 負控：這個 regex 抓得到


def test_no_hex_color_literals_in_the_renderer_source_and_css_uses_only_token_colors():
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", SRC)
    assert "rgb(" not in pg.CSS and "rgba(" not in pg.CSS

    def literals(value):
        if isinstance(value, str):
            return {value.lower()} if value.startswith("#") else set()
        return set().union(*[literals(v) for v in value.values()]) if hasattr(value, "values") else set()
    allowed = set().union(*[literals(tokens.TOKENS[n].value) for n in tokens.VALUED_NAMES if tokens.TOKENS[n].value is not None])
    stray = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", pg.CSS)} - allowed
    assert stray == set()
    assert re.search(r"#[0-9a-fA-F]{6}\b", "color:#" + "12ab34")   # 負控：偵測得到


def fstring_py312_violations(source: str) -> list:
    """3.11 不能解析的 f-string 寫法（巢狀同種引號、運算式內的反斜線）。只在 tokenize 會吐 f-string token 的直譯器（3.12+）上有作用；
    3.11 直譯器本身就會在編譯時拒絕這些寫法。"""
    if not hasattr(tokenize, "FSTRING_START"):
        return []
    frames, bad = [], []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.FSTRING_START:
            quote = tok.string.lstrip("fFrRbBuU")
            if frames and frames[-1]["depth"] > 0 and quote.startswith(frames[-1]["quote"]):
                bad.append((tok.start[0], "巢狀同種引號"))
            frames.append({"quote": quote, "depth": 0})
        elif tok.type == tokenize.FSTRING_END:
            frames.pop()
        elif frames and tok.type == tokenize.OP and tok.string == "{":
            frames[-1]["depth"] += 1
        elif frames and tok.type == tokenize.OP and tok.string == "}" and frames[-1]["depth"] > 0:
            frames[-1]["depth"] -= 1
        elif frames and frames[-1]["depth"] > 0 and tok.type == tokenize.STRING:
            nested = tok.string.lstrip("fFrRbBuU")
            if nested.startswith(frames[-1]["quote"]) or "\\" in tok.string:
                bad.append((tok.start[0], "運算式內同種引號或反斜線"))
    return bad


@pytest.mark.parametrize("rel", [SRC_REL, "ui_v3/viewmodels/nas_diag.py", "ui_v3/viewmodels/nas_diag_wording.py",
                                 "poc/nas_diag_preview/app_nas_diag_preview.py", "poc/nas_diag_preview/nas_diag_fake_inputs.py"])
def test_sources_use_no_python_312_only_syntax(rel):
    source = lib.read(lib.ROOT / rel)
    ast.parse(source, feature_version=(3, 11))
    assert fstring_py312_violations(source) == []
    assert not [n for n in ast.walk(ast.parse(source)) if type(n).__name__ in ("TypeAlias", "TypeVarTuple", "ParamSpec", "TryStar")]


def test_py312_syntax_scan_negative_control_turns_red():
    nested = 'x = {"k": 1}\ny = f"a{x["k"]}"\n'
    backslash = "y = f\"{'a\\n'}\"\n"
    if hasattr(tokenize, "FSTRING_START"):   # 3.12+：tokenize 會拆 f-string，掃描器要能抓到
        assert fstring_py312_violations(nested) and fstring_py312_violations(backslash)
        assert fstring_py312_violations("x = {'k': 1}\ny = f\"a{x['k']}\"\n") == []
    else:   # 3.11：直譯器自己在編譯時拒絕這些寫法（CI 的版本）
        for bad in (nested, backslash):
            with pytest.raises(SyntaxError):
                compile(bad, "<nas-diag-control>", "exec")
        compile("x = {'k': 1}\ny = f\"a{x['k']}\"\n", "<nas-diag-ok>", "exec")


def test_renderer_layer_dependencies_and_purity():
    assert lib.import_violations(SRC_REL, SRC) == []
    assert lib.write_surface_violations(SRC_REL, SRC) == []
    assert lib.module_level_side_effects(SRC) == []
    tree = ast.parse(SRC)
    assert "streamlit" in [m.split(".")[0] for m in lib.imports_of(tree, "ui_v3.pages")]   # 確實有用到（函式內）
    assert not [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)) and "streamlit" in ast.dump(n)]
