# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選 隔離式 FAKE Preview 的瀏覽器量測與判定函式（純函式＋一段 JS）。

只放「量什麼、怎麼判」，不起 server、不開瀏覽器；測試檔負責起 Streamlit 與 Chromium。
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

MIN_TARGET = 48

MEASURE_JS = r"""
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const vw = document.documentElement.clientWidth;
  const shown = e => { const s = getComputedStyle(e); const b = e.getBoundingClientRect();
    return e.getClientRects().length > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0 && b.width > 0 && b.height > 0; };
  const top = sel => { const e = main.querySelector(sel); return e && shown(e) ? e.getBoundingClientRect().top + window.scrollY : null; };
  const inSelect = e => !!e.closest('[data-testid="stSelectbox"]');
  const targetsOf = (sel, kind) => [...main.querySelectorAll(sel)].filter(e => shown(e) && !inSelect(e)).map(e => { const b = e.getBoundingClientRect();
    return {kind, h: b.height, w: b.width, right: b.right}; });
  const targets = [].concat(targetsOf('[data-testid="stTextInputRootElement"]', 'input'), targetsOf('[data-testid="stTextInputRootElement"] input', 'input-el'),
    targetsOf('[data-testid="stFormSubmitButton"] button', 'button'), targetsOf('[data-testid="stCheckbox"] label', 'checkbox'),
    targetsOf('summary', 'summary'));
  const sel = document.querySelector('[data-testid="stSelectbox"] [role="combobox"], [data-testid="stSelectbox"] input');
  const selBox = sel ? (sel.closest('[data-baseweb="select"]') || sel).getBoundingClientRect() : null;
  const details = [...main.querySelectorAll('details')];
  const rendererEls = [...main.querySelectorAll('[data-block], [data-block] *')].filter(shown);
  const interactive = [...main.querySelectorAll('button, a, input, select, textarea, summary, details, [tabindex], [onclick], [href]')].filter(e => shown(e));
  const seq = {title: top('h1'), input: top('[data-testid="stTextInput"]'), isin: top('[data-block="isin-note"]'), button: top('[data-testid="stFormSubmitButton"]'),
    result: top('[data-block="lookup-result"], [data-block="isin-notice"]'), basic: top('[data-block="basic-info"]'), divider: top('[data-block="exp-divider"]'),
    exp0: top('[data-block="exp0"]'), exp1: top('[data-block="exp1"]'), cond1: top('[data-testid="stCheckbox"]'), exp2: top('[data-block="exp2"]'), exp7: top('[data-block="exp7"]')};
  const card = main.querySelector('[data-block="lookup-result"]');
  const exp0 = main.querySelector('[data-block="exp0"]');
  return {vw, docScrollW: document.documentElement.scrollWidth, mainScrollW: main.scrollWidth, mainClientW: main.clientWidth, targets,
          selectH: selBox ? selBox.height : null, seq,
          details: {count: details.length, open: details.filter(d => d.open).length, nested: details.reduce((n, d) => n + d.querySelectorAll('details').length, 0)},
          mainLinks: main.querySelectorAll('a[href]').length, scripts: main.querySelectorAll('script').length,
          imgs: main.querySelectorAll('img').length, bold: [...main.querySelectorAll('b, strong')].filter(e => e.closest('[data-block]')).length,
          overflowing: rendererEls.filter(e => e.getBoundingClientRect().right > vw + 0.5).map(e => e.tagName + '.' + (e.className || '')).slice(0, 5),
          text: main.innerText, cardText: card ? card.innerText : null, outcome: card ? card.dataset.outcome : null,
          exp0: exp0 ? {matched: exp0.dataset.matched ?? null, undetermined: exp0.dataset.undetermined ?? null, conditions: exp0.dataset.conditions, text: exp0.innerText} : null,
          fundRows: main.querySelectorAll('[data-fund]').length,
          traceLast: (() => { const t = [...main.querySelectorAll('[data-trace]')].pop(); if (!t) return null;
                              return [t.querySelector('[data-col="matched"]').innerText, t.querySelector('[data-col="undetermined"]').innerText]; })(),
          failed: [...main.querySelectorAll('[data-state="failed"]')].map(e => e.dataset.block)};
}
"""


def overflow_violations(m):
    bad = []
    if m["docScrollW"] > m["vw"]:
        bad.append(("整頁橫向溢出", m["docScrollW"], m["vw"]))
    if m["mainScrollW"] > m["mainClientW"]:
        bad.append(("主內容橫向溢出", m["mainScrollW"], m["mainClientW"]))
    if m["overflowing"]:
        bad.append(("頁本體元素超出視窗右緣", m["overflowing"]))
    return bad


def touch_target_violations(m):
    """可見控制項（輸入框、查詢鈕、條件勾選、details 摘要列）高度與寬度皆須 ≥48px；harness 的 selectbox 不在此列（據實揭露，另量）。"""
    kinds = {t["kind"] for t in m["targets"]}
    bad = []
    for need in ("input", "button", "checkbox", "summary"):
        if need not in kinds:
            bad.append(("找不到控制項", need))
    for t in m["targets"]:
        if t["h"] < MIN_TARGET - 0.5 or t["w"] < MIN_TARGET - 0.5:
            bad.append(("觸控目標不足 48px", t))
        if t["right"] > m["vw"] + 0.5:
            bad.append(("控制項超出視窗", t))
    return bad


def details_violations(m):
    d = m["details"]
    bad = []
    if d["count"] != 1:
        bad.append(("details 不是恰好一個", d))
    if d["open"]:
        bad.append(("details 預設沒有收合", d))
    if d["nested"]:
        bad.append(("details 巢狀", d))
    return bad


def order_violations(m, with_result):
    """首屏順序：標題 → 輸入框 → ISIN 說明 → 查詢鈕 →（結果）→ 基本資料 → 分隔 → EXP-0 → EXP-1 → EXP-2 → EXP-7。"""
    s = m["seq"]
    names = ["title", "input", "isin", "button"] + (["result"] if with_result else []) + ["basic", "divider", "exp0", "exp1", "cond1", "exp2", "exp7"]
    missing = [n for n in names if s[n] is None]
    if missing:
        return [("找不到區塊", missing)]
    values = [s[n] for n in names]
    return [] if values == sorted(values) and len(set(values)) == len(values) else [("順序不對", dict(zip(names, values)))]


def static_violations(m):
    bad = []
    if m["mainLinks"]:
        bad.append(("主區出現連結", m["mainLinks"]))
    if m["scripts"] or m["imgs"] or m["bold"]:
        bad.append(("使用者輸入被當成標籤執行／渲染", m["scripts"], m["imgs"], m["bold"]))
    for w in ("基金不存在", "查無基金", "已確認", "推薦", "最佳", "排名", "NAV", "報酬", "績效"):
        if w in m["text"]:
            bad.append(("出現禁用字樣", w))
    return bad


def count_violations(m):
    """展示 N／M 時：EXP-2 列數＝N＋M、EXP-7 末列＝(N, M)；沒有展示（零條件或來源失敗）就不得有結果列。"""
    e = m["exp0"]
    if e is None:
        return [("沒有 EXP-0",)]
    if e["matched"] is None:
        bad = []
        if m["fundRows"]:
            bad.append(("未展示 N／M 卻有結果列", m["fundRows"]))
        if m["traceLast"] is not None:
            bad.append(("未展示 N／M 卻有軌跡列", m["traceLast"]))
        return bad
    n, k = int(e["matched"]), int(e["undetermined"])
    bad = []
    if m["fundRows"] != n + k:
        bad.append(("EXP-2 列數≠N＋M", m["fundRows"], n, k))
    last = None if m["traceLast"] is None else tuple(int(re.search(r"(\d+)\s*$", x).group(1)) for x in m["traceLast"])
    if last != (n, k):
        bad.append(("EXP-7 末列≠(N, M)", m["traceLast"], n, k))
    return bad


def structure_violations(m, with_result=False):
    return (overflow_violations(m) + touch_target_violations(m) + details_violations(m) + order_violations(m, with_result)
            + static_violations(m) + count_violations(m))


def _origin(url):
    """(scheme, host, port)；ws／wss 視同 http／https；沒有明示 port 時取該 scheme 的預設埠。"""
    parts = urlsplit(url)
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
    try:
        port = parts.port or {"http": 80, "https": 443}.get(scheme)
    except ValueError:   # `8501.evil.example`、`85011` 之類不合法的埠：不可能等於本機埠，標成無效值（必判外部）
        port = "invalid"
    return scheme, (parts.hostname or "").lower(), port


def external_request_violations(urls, base):
    """所有請求都必須與本機 Streamlit 的 scheme＋host＋port **完全相等**；`http://127.0.0.1:8501.evil.example/` 之類只是前綴相同的外部主機一律違規。"""
    own = _origin(base)

    def foreign(u):
        if u.startswith(("data:", "about:")):
            return False
        if u.startswith("blob:"):      # blob: 只放行『本機 origin 自己產生』的（blob:http://<本機 origin>/…）；blob:null／外部 origin 的 blob 一律視為外部
            return _origin(u[len("blob:"):]) != own
        return _origin(u) != own
    return [u for u in urls if foreign(u)]
