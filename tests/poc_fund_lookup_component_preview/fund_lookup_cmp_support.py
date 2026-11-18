# -*- coding: utf-8 -*-
"""單檔基金查詢呈現元件 隔離式 FAKE Preview 測試共用：路徑、import 設定、頁面層級判定函式（純函式；負控／變異一律在記憶體內現編）。"""
from __future__ import annotations

import html as _html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
POC = ROOT / "poc" / "fund_lookup_component_preview"
APP = POC / "app_fund_lookup_component_preview.py"
for _p in (str(ROOT / "tests" / "ui_v2"), str(ROOT / "tests" / "ui_v3"), str(POC), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

KEY_INPUT = "fl_query_input"
KEY_VIEW = "fl_last_view"
KEY_MODE = "uvc_mode"

# 畫面上任何狀態都不得出現的字樣（子字串比對）。「已確認」：不宣稱已確認任何來源的基金身分。
FORBIDDEN_WORDS = ("基金不存在", "查無基金", "查無此", "不存在", "已確認", "推薦", "最佳", "排名", "精選", "NAV", "淨值", "報酬", "績效", "領先", "落後",
                   "幣別", "取得時間", "資料日", "來源等級", "供應者", "Provider", "fetched_at", "ccy")
# 結果卡的五欄標籤（依客戶列出的順序）。寫死在這裡，讓『改字』也被守衛看見。
FIVE_LABELS = ("輸入代碼", "基金名稱", "配息方式", "成立日期", "經理費率")
FIVE_ROWS = ("input-code", "name", "dividend-mode", "inception", "mgmt-fee")
NASTY_INPUTS = ("A<B>C", "A$B", "A\\B", "A&amp;B", "a'b\"c", "A*B*", "A[B](C)", "A`B`", "ＡＢ１２", "A​B", "‮AB", "emoji😀", "L" * 100)


def text_of(markup: str) -> str:
    """HTML → 可見文字（粗略；去標籤、還原字元參照）。"""
    return _html.unescape(re.sub(r"<[^>]+>", " ", markup))


def forbidden_word_violations(markup: str):
    visible = text_of(markup)
    return [w for w in FORBIDDEN_WORDS if w in visible]


def raw_script_violations(markup: str):
    bad = []
    if re.search(r"<\s*script\b", markup, re.I):
        bad.append("raw <script>")
    if re.search(r"<\s*img\b", markup, re.I):
        bad.append("raw <img>")
    if re.search(r"<[^>]*\bon[a-z]+\s*=", markup, re.I):
        bad.append("raw onerror=")
    return bad


def special_char_violations(shown_html: str):
    """使用者輸入顯示處的 HTML 不得留下 `<`、`>`、`$`、反斜線、換行（皆須已轉成字元參照）。"""
    return [c for c in ("<", ">", "$", "\\", "\n", "\r") if c in shown_html]


_ROW_RE = re.compile(r'data-row="([^"]+)"')
_LABEL_RE = re.compile(r'<dt class="uv3-label">.*?data-pending-wording="(row_[a-z_]+)"', re.S)


def row_names(card_html: str):
    return [n for n in _ROW_RE.findall(card_html) if n not in ("status", "idle")]


def field_violations(card_html: str):
    """五欄白名單：data-row 只能是五欄名（依序、不重複），標籤只能是 `row_*` 五鍵；任何其他欄位列都違規。"""
    bad = []
    names = row_names(card_html)
    if names != [n for n in FIVE_ROWS if n in names]:
        bad.append(("欄位順序或名稱不合", names))
    if len(set(names)) != len(names):
        bad.append(("欄位重複", names))
    labels = _LABEL_RE.findall(card_html)
    if labels != [f"row_{n.replace('-', '_')}" if n != "dividend-mode" else "row_dividend_mode" for n in names]:
        bad.append(("標籤與欄位列不一致", labels, names))
    return bad


def fake_tag_order_violations(card_html: str):
    """卡內恰好一個 FAKE 標籤，且在 DOM 順序上先於任何欄位列與狀態列。"""
    bad = []
    if card_html.count('data-tag="fake"') != 1:
        bad.append(("FAKE 標籤不是恰好一個", card_html.count('data-tag="fake"')))
    else:
        tag = card_html.index('data-tag="fake"')
        for marker in ('data-row="', '<dl '):
            if marker in card_html and card_html.index(marker) < tag:
                bad.append(("FAKE 標籤在欄位列之後", marker))
    return bad


# ───────────────────────── 全狀態樣本與「檢查組」（單元測試與突變測試共用；負控／變異一律在記憶體內現編） ─────────────────────────

# 經 adapter（FakeLoader）產生的樣本輸入；blank／ISIN／網址形用來驗『被攔截的輸入不回顯』。
ADAPTER_INPUTS = ("FAKE-OK01", "FAKE-OK02", "FAKE-OK03", "FAKE-FAIL1", "FAKE-COOL1", "FAKE-IOERR", "FAKE-PAGE1", "FAKE-PAGE2", "FAKE-PAGE3",
                  "FAKE-NAME1", "ABC123", "FAKE-REJ1", "   ", "US0378331005", "http://x.example/a", "A<B>C", "A$B", "\tAB", "L" * 100)
NEVER_ECHO_INPUTS = ("US0378331005", "http://x.example/a", "\tAB", "L" * 100)


def build_views(extra_nasty_name=True):
    """(label, view) 清單：adapter 產生的全部樣本＋CONFLICT 直接建構＋（可選）名稱含 HTML 特殊字元的直接建構 RESULT。"""
    import fund_lookup_fake_inputs as fake
    from ui_v3.adapters.fund_lookup import lookup_fund, not_queried
    from ui_v3.viewmodels.fund_lookup import FieldStatus, FieldView, FundLookupView, LookupState, ProfileFields
    out = [("idle", not_queried())]
    out += [(raw, lookup_fund(fake.make_loader(), raw)) for raw in ADAPTER_INPUTS]
    out.append(("conflict", fake.conflict_view()))
    if extra_nasty_name:
        fields = ProfileFields(FieldView(FieldStatus.VALUE, "<b>$x</b>\\y&amp;"), FieldView(FieldStatus.VALUE, "dist"),
                               FieldView(FieldStatus.VALUE, "2001-02-03"), FieldView(FieldStatus.MISSING))
        out.append(("nasty-name", FundLookupView(LookupState.RESULT, "ACTI71", None, fields)))
    return out


def battery(renderer, views=None):
    """對 renderer 模組（`lookup_card_html`／`idle_html`／`isin_note_html`）跑全狀態檢查，回傳違規描述 list（空＝全過）。
    renderer 拋例外 → 回傳 `[("CRASH", ...)]`（崩潰不算『抓到變異』，呼叫端須另外斷言）。"""
    import fund_lookup_wording as W
    from shared.ui_semantics import rules
    from ui_v3.viewmodels.fund_lookup import LookupState
    bad = []
    try:
        for label, view in (views or build_views()):
            for fake in (True, False):
                html = renderer.lookup_card_html(view, fake=fake)
                where = (label, fake)
                bad += [(where, "禁用字樣", w) for w in forbidden_word_violations(html)]
                bad += [(where, "未跳脫標籤", v) for v in raw_script_violations(html)]
                state = view.state
                if state is LookupState.NOT_QUERIED:
                    if text_of(html).strip() != W.text("not_queried") or 'data-state="idle"' not in html or "data-row=\"input-code\"" in html:
                        bad.append((where, "查詢前不只顯示『尚未查詢』"))
                    continue
                expect_state = {LookupState.RESULT: "result", LookupState.SOURCE_FAILED: "failed", LookupState.PAGE_UNMATCHED: "unmatched",
                                LookupState.BLOCKED: "blocked"}[state]
                if f'data-state="{expect_state}"' not in html:
                    bad.append((where, "data-state 不對", expect_state))
                if view.reason_code and f'data-reason="{view.reason_code}"' not in html:
                    bad.append((where, "data-reason 不對"))
                if fake:
                    bad += [(where, *v) for v in fake_tag_order_violations(html)]
                elif 'data-tag="fake"' in html:
                    bad.append((where, "fake=False 卻出現 FAKE 標籤"))
                bad += [(where, *v) for v in field_violations(html)]
                names = row_names(html)
                if state is LookupState.RESULT:
                    if len(names) != 5 or names != list(FIVE_ROWS):
                        bad.append((where, "RESULT 不是依序五欄", names))
                else:
                    echoed = isinstance(view.input_code, str) and view.input_code.strip(" ") != ""
                    if names != (["input-code"] if echoed else []):
                        bad.append((where, "非 RESULT 的欄位列不是（有回顯才有）輸入代碼", names))
                # 角色與區域語意
                role = "alert" if state in (LookupState.SOURCE_FAILED, LookupState.BLOCKED) else "status"
                if f'role="{role}"' not in html:
                    bad.append((where, "狀態列角色不對", role))
                m = re.search(r'role="region" aria-labelledby="([^"]+)"', html)
                if m is None or f'id="{m.group(1)}"' not in html:
                    bad.append((where, "region／aria-labelledby 缺或指不到"))
                # 狀態字樣彼此不混用：取數失敗⛔／無法判定⬜／入口攔截兩者皆無
                failed_w, undet_w = rules.entry("fetch_failed").wording, rules.entry("undetermined").wording
                has_failed, has_undet = failed_w in text_of(html), undet_w in text_of(html)
                if (has_failed, has_undet) != {LookupState.SOURCE_FAILED: (True, False), LookupState.PAGE_UNMATCHED: (False, True)}.get(state, (False, False)):
                    bad.append((where, "狀態字樣混用或缺", has_failed, has_undet))
                if '◇' in text_of(html):
                    bad.append((where, "出現 ◇（正式模式缺值符號）"))
                # 被安全攔截的輸入不得回顯
                if label in NEVER_ECHO_INPUTS and label.strip() and label.strip() in text_of(html):
                    bad.append((where, "被攔截的輸入被回顯", label))
                # 缺值／衝突
                if state is LookupState.RESULT:
                    for name, fs in re.findall(r'data-row="([a-z-]+)" data-field-status="([a-z]+)"', html):
                        txt = _row_text(html, name)
                        want = "missing" if txt == W.text("field_missing") else "conflict" if txt == W.text("field_conflict") else "value"
                        if fs != want:
                            bad.append((where, "欄位狀態標記與文案不一致", name, fs, want))
                        if fs == "missing" and txt in ("0", "無", "不配息", "-", "—", ""):
                            bad.append((where, "缺值被寫成 0／無", name))
                    if label == "FAKE-OK01" and ("配息型" not in text_of(html) or "累積型" in text_of(html)):
                        bad.append((where, "配息型對應錯"))
                    if label == "FAKE-OK02" and ("累積型" not in text_of(html) or "配息型" in text_of(html)):
                        bad.append((where, "累積型對應錯"))
                    if label == "nasty-name":
                        shown = _row_value_html(html, "name")
                        if special_char_violations(shown) or "&lt;b&gt;" not in shown:
                            bad.append((where, "名稱未跳脫", shown))
        note = renderer.isin_note_html()
        if 'data-block="isin-note"' not in note or W.text("isin_note") not in text_of(note):
            bad.append((None, "ISIN 常駐說明缺"))
        idle = renderer.idle_html()
        if text_of(idle).strip() != W.text("not_queried"):
            bad.append((None, "idle_html 不只『尚未查詢』"))
    except Exception as exc:  # noqa: BLE001 - 崩潰型例外回報給呼叫端判讀
        return [("CRASH", type(exc).__name__, str(exc)[:200])]
    return bad


def _row_inner(html: str, name: str) -> str:
    m = re.search(rf'data-row="{name}"[^>]*>(.*?)</div>(?=<div class="fl-row"|</dl>)', html, re.S)
    return m.group(1) if m else ""


def _row_text(html: str, name: str) -> str:
    inner = _row_inner(html, name)
    dd = re.search(r"<dd>(.*)</dd>", inner, re.S)
    return text_of(dd.group(1) if dd else inner).strip()


def _row_value_html(html: str, name: str) -> str:
    dd = re.search(r"<dd>(.*)</dd>", _row_inner(html, name), re.S)
    return dd.group(1) if dd else ""
