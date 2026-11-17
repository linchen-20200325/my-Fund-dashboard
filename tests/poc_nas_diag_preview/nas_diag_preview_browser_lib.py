# -*- coding: utf-8 -*-
"""NAS 中繼站診斷隔離式 FAKE Preview 的瀏覽器量測與判定函式（純函式＋一段 JS；最小複製自其他 Preview 的瀏覽器守衛）。

只放「量什麼、怎麼判」，不起 server、不開瀏覽器；測試檔負責起 Streamlit 與 Chromium。
"""
from __future__ import annotations

MEASURE_JS = r"""
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const shown = e => { const s = getComputedStyle(e); const b = e.getBoundingClientRect();
    return e.getClientRects().length > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0 && b.width > 0 && b.height > 0; };
  const root = document.querySelector('[data-block="nas-status"]');
  const badge = document.querySelector('[data-badge="state"]');
  const banner = document.querySelector('.uv3n-banner');
  const axes = [...document.querySelectorAll('[data-axis]')].map(e => { const b = e.getBoundingClientRect();
    return {axis: e.dataset.axis, health: e.dataset.health, top: b.top, left: b.left, right: b.right, bottom: b.bottom, width: b.width, shown: shown(e)}; });
  const body = [...main.querySelectorAll('[data-block], [data-block] *, [data-harness]')].filter(shown);
  const rendererEls = [...main.querySelectorAll('[data-block], [data-block] *')];
  const interactive = rendererEls.filter(e => e.matches('button, a, input, select, textarea, summary, details, [tabindex], [onclick], [href]'));
  const bs = badge ? getComputedStyle(badge) : null;
  const pending = document.querySelectorAll('[data-pending-wording="pending_notice"]').length;
  const selInput = document.querySelector('[data-testid="stSelectbox"] input');
  const sel = selInput ? (selInput.closest('[role="group"]') || selInput) : null;
  const selR = sel ? sel.getBoundingClientRect() : null;
  return {vw, vh, docScrollW: document.documentElement.scrollWidth, mainScrollW: main.scrollWidth, mainClientW: main.clientWidth,
          state: root ? root.dataset.state : null, hasBanner: !!document.querySelector('[data-harness="true"]'),
          badge: badge ? {text: badge.innerText.trim(), bg: bs.backgroundColor, color: bs.color, border: bs.borderTopColor, cls: badge.className, shown: shown(badge),
                          right: badge.getBoundingClientRect().right} : null,
          banner: banner ? {text: banner.innerText.trim(), shown: shown(banner), right: banner.getBoundingClientRect().right, weight: getComputedStyle(banner).fontWeight,
                            borderLeft: getComputedStyle(banner).borderLeftWidth} : null,
          axes, interactiveCount: interactive.length, pendingNotice: pending, blocks: [...document.querySelectorAll('[data-block]')].map(e => e.dataset.block),
          overflowing: body.filter(e => e.getBoundingClientRect().right > vw + 0.5).map(e => e.tagName + '.' + (e.className || '')).slice(0, 5),
          selectH: selR ? selR.height : null,
          text: [...document.querySelectorAll('[data-block]')].map(e => e.innerText).join('\n')};
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


def structure_violations(m):
    """每個情境的共同結構：徽章可見、兩軸卡片各一且可見、暫行字樣提示在、區塊順序固定、renderer 內沒有任何可互動元素。"""
    bad = []
    if not m["badge"] or not m["badge"]["shown"]:
        bad.append(("狀態徽章不可見",))
    if sorted(a["axis"] for a in m["axes"]) != ["nas", "target"] or not all(a["shown"] for a in m["axes"]):
        bad.append(("兩軸卡片不是各一個且可見", [a["axis"] for a in m["axes"]]))
    if m["pendingNotice"] != 1:
        bad.append(("暫行字樣提示不是恰好一個", m["pendingNotice"]))
    if m["blocks"][:3] != ["nas-status", "axes", "last-check"]:
        bad.append(("區塊順序不對", m["blocks"]))
    if m["interactiveCount"]:
        bad.append(("renderer 內有可互動元素（不得有假按鈕或連結）", m["interactiveCount"]))
    if not m["hasBanner"]:
        bad.append(("缺 FAKE 標示",))
    return bad


def axes_layout_violations(m):
    """≤768 兩張卡片上下疊（第二張在第一張下方且同寬）；>768 左右並排（頂端對齊）。"""
    nas = next(a for a in m["axes"] if a["axis"] == "nas")
    target = next(a for a in m["axes"] if a["axis"] == "target")
    bad = []
    if m["vw"] <= 768:
        if not (target["top"] >= nas["bottom"] - 0.5 and abs(target["left"] - nas["left"]) < 1):
            bad.append(("窄螢幕兩張卡片沒有上下疊", nas, target))
    else:
        if not (abs(target["top"] - nas["top"]) < 1 and target["left"] >= nas["right"] - 0.5):
            bad.append(("寬螢幕兩張卡片沒有左右並排", nas, target))
    return bad


def degraded_distinct_violations(degraded, ok):
    """降級直連的徽章必須：有醒目橫幅、文字與連線成功不同、底色與連線成功不同、橫幅字重加粗且左邊線粗；畫面上不出現連線成功字樣。"""
    bad = []
    if not degraded["banner"] or not degraded["banner"]["shown"]:
        bad.append(("降級直連沒有可見的醒目橫幅",))
    elif int(degraded["banner"]["weight"]) < 600 or float(degraded["banner"]["borderLeft"].replace("px", "")) < 4:
        bad.append(("橫幅不夠醒目", degraded["banner"]["weight"], degraded["banner"]["borderLeft"]))
    if degraded["badge"]["text"] == ok["badge"]["text"]:
        bad.append(("降級直連與連線成功同詞", degraded["badge"]["text"]))
    if degraded["badge"]["bg"] == ok["badge"]["bg"] or degraded["badge"]["border"] == ok["badge"]["border"]:
        bad.append(("降級直連與連線成功同色", degraded["badge"]["bg"], ok["badge"]["bg"]))
    if ok["badge"]["text"] in degraded["text"]:
        bad.append(("降級直連畫面出現連線成功字樣",))
    return bad
