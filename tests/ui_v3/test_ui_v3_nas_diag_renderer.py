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
    assert 'data-pending-wording="pending_notice"' in html and 'data-pending-wording="offline_note"' in html
    assert "本預覽為離線注入結果" in visible(html) and "暫行字樣，尚未核准" in visible(html)
    # 資訊層級：①設定＋結果 → ②兩軸 → ③路徑／HTTP／時間 →（④原因，有才畫）→ ⑤收合證據 → 說明
    order = [html.index(m) for m in ('data-block="nas-status"', 'data-block="axes"', 'data-block="last-check"', 'data-block="evidence"', 'data-note="offline"')]
    assert order == sorted(order)
    if 'data-block="causes"' in html:
        assert html.index('data-block="last-check"') < html.index('data-block="causes"') < html.index('data-block="evidence"')


def test_route_shows_the_actual_path_and_untested_is_not_a_path():
    expect = {"nas_ok": "NAS 中繼", "degraded_direct": "降級直連", "not_configured": "未測試", "configured_untested": "未測試",
              "auth_407": "沒有可用路徑", "contradiction": "⬜ 無法判定"}
    for sid, word in expect.items():
        row = re.search(r'data-row="route">(.*?)</div>', html_of(sid)).group(1)
        assert word in visible(row), (sid, visible(row))


def test_untested_target_axis_shows_no_status_code_only_the_missing_wording_in_the_http_row():
    """目標軸尚未測試／無法判定（含 407：狀態碼屬於 NAS 這一段）時，目標卡只有標籤與健康度；③的 HTTP 結果一律是缺值，不拿 407 冒充目標回應。"""
    for sid in ("not_configured", "configured_untested", "contradiction", "auth_407", "timeout", "tls", "dns"):
        html = html_of(sid)
        card = html.split('data-axis="target"')[1].split('data-block="last-check"')[0]
        assert 'data-row="status-code"' not in card and 'data-row="latency"' not in card, sid
        assert 'data-pending-wording="target_health_ok"' not in card and 'data-pending-wording="target_health_failed"' not in card, sid
        http = re.search(r'data-row="status-code">(.*?)</div>', html).group(1)
        assert rules.MISSING_TEXT in visible(http) and "407" not in visible(http), sid
    card407 = html_of("auth_407").split('data-axis="target"')[1]
    assert text_of("health_not_tested") in visible(card407)


def test_http_result_and_latency_moved_out_of_the_target_card_and_missing_never_becomes_zero():
    ok = html_of("nas_ok")
    http = re.search(r'data-row="status-code">(.*?)</div>', ok).group(1)
    assert "200" in visible(http) and text_of("label_status_code") == "HTTP 結果"
    assert "380 " in re.search(r'<details.*?</details>', ok, re.S).group(0)   # 延遲在收合證據裡
    card = ok.split('data-axis="target"')[1].split('data-block="last-check"')[0]
    assert "200" not in visible(card) and "380" not in visible(card)
    blocked = html_of("blocked_403")
    assert "403" in visible(re.search(r'data-row="status-code">(.*?)</div>', blocked).group(1))
    direct = pg.page_html(vm.classify(vm.NasDiagObservation(target_label=sup.TARGET, proxy_configured=False, route_used="direct",
                                                            target_http_status=200, error_class="ok", latency_ms=0, checked_at=sup.CHECKED_AT)))
    assert "0 " in re.search(r'data-row="latency">(.*?)</div>', direct).group(1)   # 0 是值、不是缺值
    no_latency = html_of("configured_untested")
    assert rules.MISSING_TEXT in visible(re.search(r'data-row="latency">(.*?)</div>', no_latency).group(1))


def test_approved_wording_is_reused_not_copied():
    assert 'data-status-key="not_configured"' in html_of("not_configured") and rules.entry("not_configured").wording in visible(html_of("not_configured"))
    assert 'data-status-key="undetermined"' in html_of("contradiction") and rules.entry("undetermined").wording in visible(html_of("contradiction"))
    assert 'data-status-key="missing"' in html_of("configured_untested")
    assert 'data-config="not_configured"' in html_of("not_configured") and 'data-config="configured"' in html_of("nas_ok")
    for key in ("state_not_tested", "state_ok", "state_failed", "state_degraded"):
        assert f'data-pending-wording="{key}"' in "".join(html_of(s) for s in SIDS)


def test_causes_are_human_and_say_which_side_for_the_failure_scenarios():
    assert "代理驗證失敗" in visible(html_of("auth_407")) and "NAS 這一段" in visible(html_of("auth_407"))
    assert "目標網站這一段" in visible(html_of("blocked_403")) and "不是 NAS 斷線" in visible(html_of("blocked_403"))
    assert "NAS 這一段" in visible(html_of("blocked_403_then_direct")) and "目標網站這一段" not in visible(html_of("blocked_403_then_direct"))
    both = visible(html_of("both_failed"))
    assert "NAS 這一段" in both and "目標網站這一段" in both
    assert "不要為了通過而關閉憑證驗證" in visible(html_of("tls"))
    # 逾時／名稱解析／TLS（經 NAS）沒有證據區分兩側：用「無法區分」標籤，且不出現歸給某一側的標籤
    for sid in ("timeout", "dns", "tls"):
        causes = visible(re.search(r'data-block="causes">.*?</div></div>', html_of(sid), re.S).group(0))   # 只看原因區的標籤（結論句會合理地同時提到兩側）
        assert text_of("who_unknown") in causes and text_of("who_nas") + text_of("label_target") not in causes, sid
        assert not re.search(r'data-cause="cause_(auth|blocked|rate|timeout|dns|tls|nas|other)', html_of(sid)), sid
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


_DETAILS_OPEN = '<details class="uv3n-evidence" data-block="evidence"><summary data-summary="evidence">'


def interactive_elements(html: str) -> list:
    """唯一允許的可互動元素是那一個預設收合、不巢狀的 `<details>`／`<summary>` 本身；只拿掉這兩個標籤殼（開頭＋收尾各一次），
    **details 內部照掃**（input／onclick／tabindex／button 等一律不准，與瀏覽器版一致）。"""
    rest = html.replace(_DETAILS_OPEN, "", 1).replace("</summary>", "", 1).replace("</details>", "", 1)
    return re.findall(r"<\s*(?:button|a|input|select|textarea|form|summary|details|script|iframe)\b|\bhref\s*=|\bonclick\s*=|\btabindex\s*=|javascript:", rest, re.I)


@pytest.mark.parametrize("sid", SIDS)
def test_exactly_one_collapsed_non_nested_details_and_no_open_attribute(sid):
    html = html_of(sid)
    assert len(re.findall(r"<details\b", html)) == 1 and len(re.findall(r"<summary\b", html)) == 1 and html.count("</details>") == 1
    assert not re.search(r"<details\b[^>]*\bopen\b", html, re.I)   # 預設收合
    body = re.search(r"<details[^>]*>(.*)</details>", html, re.S).group(1)
    assert "<details" not in body and "<button" not in body and "href" not in body
    assert text_of("evidence_summary") in visible(re.search(r"<summary[^>]*>(.*?)</summary>", html, re.S).group(1))


def test_details_css_gives_a_48px_touch_target():
    rule = re.search(r"\.uv3n-evidence > summary\{([^}]*)\}", pg.CSS).group(1)
    assert "min-height:48px" in rule


def test_interactive_element_detector_negative_control():
    nas_ok = html_of("nas_ok")
    inner = lambda bad: nas_ok.replace('</details>', bad + '</details>')   # noqa: E731  注入到 details 內部
    for bad in ("<button>x</button>", "<input>", '<div onclick="f()">', '<div tabindex="0">', '<a href="#">x</a>', "<details>", "<select>"):
        assert interactive_elements(inner(bad)), ("details 內部", bad)
    assert interactive_elements(nas_ok) == []
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


# ───────────────────────── QA 追加 ─────────────────────────

def test_css_banner_and_every_tone_rule_exist_in_the_fast_lane():
    banner = re.search(r"\.uv3n-banner\{([^}]*)\}", pg.CSS)
    assert banner, "缺 .uv3n-banner 規則"
    assert "font-weight:700" in banner.group(1) and "border-left:" in banner.group(1)
    for tone in tokens.TONE_KEYS:
        rule = re.search(r"\.uv3n-tone-" + tone + r"\{([^}]*)\}", pg.CSS)
        assert rule and "color:" in rule.group(1) and "background:" in rule.group(1) and "border-color:" in rule.group(1), tone
    assert not re.search(r"\.uv3n-tone-(?!" + "|".join(tokens.TONE_KEYS) + ")", pg.CSS)
    assert re.search(r"\.uv3n-badge\{[^}]*font-weight:700", pg.CSS)


def _product_views():
    import itertools
    views, reasons_seen = set(), set()
    for conf, reach, route, err, nerr, status, at, lat in itertools.product(
            (False, True, None), (None, True, False), (None, "nas", "direct", "fallback_direct", "none"),
            (None,) + vm.ERROR_CLASSES, (None,) + vm.ERROR_CLASSES, (None, 200, 403, 407, 429, 500), (None, sup.CHECKED_AT), (None, 120)):
        obs = vm.NasDiagObservation(target_label=sup.TARGET, proxy_configured=conf, nas_reachable=reach, route_used=route, error_class=err,
                                    nas_error_class=nerr, target_http_status=status, latency_ms=lat, checked_at=at)
        views.add(vm.classify(obs))
    return views


def test_every_reachable_view_from_the_input_product_renders_without_error():
    views = _product_views()
    assert len(views) > 50
    pairs = {(v.state, v.reason_key) for v in views}
    assert pairs <= set(W.CONCLUSION_KEY) and {r for _, r in pairs} == set(vm.REASON_KEYS) and {s for s, _ in pairs} == set(vm.STATES)
    for v in views:
        html = pg.page_html(v)   # 不得 KeyError
        assert 'data-axis="nas"' in html and 'data-axis="target"' in html
        assert leaks_of(html) == []
    combos = {(v.state, v.route_code, v.nas_cause_key, v.target_cause_key) for v in views}
    assert (vm.STATE_FAILED, vm.ROUTE_FALLBACK, "cause_nas_unreachable", "cause_timeout") in combos          # fallback_direct＋直連也失敗
    assert any(v.target_cause_key == "cause_other" and 'data-cause="cause_other"' in pg.page_html(v) for v in views)   # other 被渲染
    assert any(v.state == vm.STATE_NOT_CONFIGURED and v.route_code == vm.ROUTE_DIRECT and v.target_health in ("ok", "failed") for v in views)
    assert text_of("cause_other") in visible(next(pg.page_html(v) for v in views if v.target_cause_key == "cause_other"))


def _poison_view(**over):
    view = vm.classify(vm.NasDiagObservation(**sup.kwargs("nas_ok")))
    for k, v in over.items():
        object.__setattr__(view, k, v)   # 繞過 frozen 與驗證：模擬有人直接塞污染值給 renderer
    return view


def test_renderer_escapes_every_interpolation_even_for_a_view_that_bypassed_validation():
    inject = "<script>alert(1)</script>"
    html = pg.page_html(_poison_view(target_label=inject, target_http_status=inject, latency_ms=inject))
    assert "<script" not in html and html.count("&lt;script&gt;") == 3
    html = pg.page_html(_poison_view(target_label='"><img src=x onerror=1>'))
    assert "<img" not in html and "&quot;&gt;&lt;img" in html


def test_directly_constructing_a_poisoned_view_is_refused_and_never_reaches_the_renderer():
    base = vm.classify(vm.NasDiagObservation(**sup.kwargs("nas_ok")))
    import dataclasses
    for field, bad in (("target_label", sup.POISON_URL), ("latency_ms", "<b>x</b>"), ("target_http_status", "<i>"), ("checked_at", sup.POISON_URL)):
        with pytest.raises((ValueError, TypeError)) as info:
            vm.NasDiagView(**{**dataclasses.asdict(base), field: bad})
        assert sup.SECRET not in str(info.value)
    # 就算 checked_at 被繞過驗證塞了污染值，renderer 的失敗訊息也不含該值
    with pytest.raises(ValueError) as info:
        pg.page_html(_poison_view(checked_at=sup.POISON_URL))
    assert sup.SECRET not in str(info.value)


_FORBIDDEN_NAMES = {"environ", "getenv", "secrets", "subprocess", "socket", "requests", "urllib", "urllib3", "httpx"}
_NEW_NON_TEST_FILES = ("ui_v3/viewmodels/nas_diag.py", "ui_v3/viewmodels/nas_diag_wording.py", "ui_v3/pages/nas_diag.py",
                       "poc/nas_diag_preview/app_nas_diag_preview.py", "poc/nas_diag_preview/nas_diag_fake_inputs.py")


def forbidden_ast_uses(source: str) -> list:
    tree = ast.parse(source)
    hits = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    hits |= {m.split(".")[0] for m in lib.imports_of(tree, "x")} | {a.arg for n in ast.walk(tree) if isinstance(n, ast.arguments) for a in n.args}
    hits |= {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and n.value in _FORBIDDEN_NAMES and isinstance(n.value, str)}
    return sorted(hits & _FORBIDDEN_NAMES)


@pytest.mark.parametrize("rel", _NEW_NON_TEST_FILES)
def test_new_non_test_files_use_no_environment_secret_process_or_network_names(rel):
    assert forbidden_ast_uses(lib.read(lib.ROOT / rel)) == []


@pytest.mark.parametrize("bad", ["import os\nos.environ.get('X')", "import os\nos.getenv('X')", "import streamlit as st\nst.secrets['k']", "import subprocess",
                                 "import socket", "import requests", "import urllib.request", "import httpx", "from urllib import request"])
def test_forbidden_ast_scan_negative_controls_turn_red(bad):
    assert forbidden_ast_uses(bad)


# ───────────────────────── 2026-11-17 UX 收斂：符號＋文字、未設定中性灰、無法區分兩側 ─────────────────────────

def _badge_text(sid: str) -> str:
    return visible(re.search(r'data-badge="state"[^>]*>(.*?)</span></span>', html_of(sid)).group(1)).strip()


def test_every_state_badge_has_a_distinct_symbol_and_text_not_color_alone():
    by_state = {}
    for sid in SIDS:
        view = vm.classify(vm.NasDiagObservation(**sup.kwargs(sid)))
        by_state[view.state] = _badge_text(sid)
    assert len(set(by_state.values())) == 6, by_state
    symbols = {t.split(" ")[0] for t in by_state.values()}
    assert len(symbols) == 6, by_state          # 六態六個不同的前綴符號（neutral／grey 同色時靠符號＋文字區分）
    assert by_state["not_tested"].startswith("◌") and by_state["undetermined"].startswith("⬜") and by_state["not_configured"].startswith("⛔")
    assert "本次" in by_state["ok"] and "本次" in by_state["failed"]


def test_not_configured_is_neutral_grey_not_a_fault_and_the_rule_table_is_untouched():
    html = html_of("not_configured")
    assert "uv3n-tone-grey" in html and "uv3n-tone-red" not in html
    assert "uv3-st-red" not in html and 'uv3-st uv3-st-grey" data-status-key="not_configured"' in html   # 不帶紅色語意 class
    assert rules.entry("not_configured").tone == "red" and rules.entry("not_configured").wording == "⛔ 尚未設定"   # 規則表不覆寫
    assert pg.state_tone(vm.STATE_NOT_TESTED) == "grey" and pg.state_tone(vm.STATE_UNDETERMINED) == "grey"
    assert "不是故障" in visible(html)


def test_success_wording_says_this_time_and_never_implies_permanent_health():
    ok = visible(html_of("nas_ok"))
    assert "本次" in ok and "不代表 NAS 之後都正常" in ok


@pytest.mark.parametrize("sid", ["timeout", "dns", "tls"])
def test_timeout_dns_tls_via_nas_show_both_axes_undetermined_with_the_missing_evidence_explained(sid):
    html = html_of(sid)
    assert 'data-axis="nas" data-health="undetermined"' in html and 'data-axis="target" data-health="undetermined"' in html
    v = visible(html)
    assert "缺少區分 NAS 這一段或目標網站這一段的證據" in v
    assert text_of("nas_health_ok") not in v and text_of("target_health_ok") not in v and text_of("state_ok") not in v
    assert 'data-state="undetermined"' in html and 'data-status-key="undetermined"' in html
    assert "本次有經過 NAS" in v and "NAS 中繼" in visible(re.search(r'data-row="route">(.*?)</div>', html).group(1))


def test_both_axes_titles_and_config_vs_result_rows_exist():
    html = html_of("nas_ok")
    assert text_of("label_nas_card") == "NAS 中繼檢查結果" and text_of("label_target_card") == "目標網站本次回應"
    assert 'data-row="config"' in html and 'data-row="result"' in html and text_of("label_config") in visible(html)


def test_no_operable_test_button_is_rendered_and_the_old_live_test_note_is_gone():
    for sid in SIDS:
        v = visible(html_of(sid))
        assert "立即測試" not in v and "即時測試" not in v
        assert 'data-pending-wording="live_test_note"' not in html_of(sid)


# ───────────────────────── QA 追加：fallback／none 路徑的失敗歸屬措辭 ─────────────────────────

def test_direct_path_failures_use_attributed_wording_not_the_cannot_tell_wording():
    """both_failed（route=none，直連逾時）與 fallback_direct＋直連失敗：直連沒有 NAS 參與，失敗歸目標側；
    原因字樣不得再說「無法分辨是 NAS 還是目標網站」，也不得掛在單側標籤下自相矛盾。"""
    cases = {
        "both_failed": ("cause_timeout", "cause_nas_unreachable"),
        "fb_timeout": ("cause_timeout", "cause_nas_unreachable"),
        "fb_dns": ("cause_dns", "cause_nas_unreachable"),
        "fb_tls": ("cause_tls", "cause_nas_unreachable"),
        "none_dns": ("cause_dns", "cause_nas_unreachable"),
        "none_tls": ("cause_tls", "cause_nas_unreachable"),
    }
    kws = {"both_failed": sup.kwargs("both_failed"),
           "fb_timeout": {**sup.kwargs("degraded_direct"), "target_http_status": None, "error_class": "timeout"},
           "fb_dns": {**sup.kwargs("degraded_direct"), "target_http_status": None, "error_class": "dns"},
           "fb_tls": {**sup.kwargs("degraded_direct"), "target_http_status": None, "error_class": "tls"},
           "none_dns": {**sup.kwargs("both_failed"), "error_class": "dns"},
           "none_tls": {**sup.kwargs("both_failed"), "error_class": "tls"}}
    for name, (target_cause, nas_cause) in cases.items():
        view = vm.classify(vm.NasDiagObservation(**kws[name]))
        assert (view.target_cause_key, view.nas_cause_key, view.unattributed_cause_key) == (target_cause, nas_cause, None), name
        html = pg.page_html(view)
        v = visible(html)
        assert "無法分辨" not in v and "缺少證據區分" not in v.split("原因與建議")[-1], name
        assert text_of("who_target") in v and text_of("who_nas") in v and text_of("who_unknown") not in v, name
        assert f'data-cause="{target_cause}"' in html and f'data-cause="{nas_cause}"' in html, name
        assert view.nas_health == vm.HEALTH_FAILED and view.target_health == vm.HEALTH_FAILED, name


def test_no_wording_text_for_attributed_causes_claims_it_cannot_tell_the_side():
    for key in ("cause_timeout", "cause_dns", "cause_tls"):
        assert "無法分辨" not in text_of(key) and "缺少證據" not in text_of(key), key
    for key in ("cause_unattr_timeout", "cause_unattr_dns", "cause_unattr_tls"):
        assert "無法判定" in text_of(key), key
