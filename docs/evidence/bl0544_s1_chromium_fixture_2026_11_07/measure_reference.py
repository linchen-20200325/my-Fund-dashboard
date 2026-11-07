import json, sys
from playwright.sync_api import sync_playwright
OUT = "/tmp/claude-0/-home-user-my-Fund-dashboard/8acf747f-681e-536d-9152-f8a300c72491/scratchpad/evidence"
URL = "http://localhost:8765/"
TAG = sys.argv[1] if len(sys.argv) > 1 else "run"
FONT = sys.argv[2] if len(sys.argv) > 2 else ""   # e.g. "190" => text zoom 190%
WIDTHS = [374, 375, 390, 768, 769, 1280] if not FONT else [374, 390]
JS = r"""
() => {
  const r = e => { const b = e.getBoundingClientRect(); return {x:+b.x.toFixed(1),y:+b.y.toFixed(1),w:+b.width.toFixed(1),h:+b.height.toFixed(1),r:+b.right.toFixed(1),b:+b.bottom.toFixed(1)}; };
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const nav = document.querySelector('.st-key-uv3-top-nav');
  const out = {vw, vh, docScrollW: document.documentElement.scrollWidth, docClientW: vw, bodyScrollW: document.body.scrollWidth};
  const main = document.querySelector('[data-testid="stMain"]');
  out.mainScrollW = main ? main.scrollWidth : null; out.mainClientW = main ? main.clientWidth : null;
  if (!nav) { out.nav = null; return out; }
  const cs = getComputedStyle(nav);
  out.nav = {display: cs.display, position: cs.position, overflowX: cs.overflowX, rect: r(nav), scrollW: nav.scrollWidth, clientW: nav.clientWidth, top: cs.top};
  const cells = [];
  nav.querySelectorAll('a[data-testid="stPageLink-NavLink"], .uv3-tn-disabled').forEach(e => {
    const b = e.getBoundingClientRect(), s = getComputedStyle(e);
    const cx = b.x + b.width/2, cy = b.y + b.height/2;
    const top = document.elementFromPoint(Math.min(Math.max(cx,0),vw-1), Math.min(Math.max(cy,0),vh-1));
    cells.push({tag: e.tagName, text: e.innerText.replace(/\s+/g,' ').trim(), href: e.getAttribute('href'), ariaDisabled: e.getAttribute('aria-disabled'), ariaLabel: e.getAttribute('aria-label'),
      ariaCurrent: e.getAttribute('aria-current'), tabindex: e.getAttribute('tabindex'), rect: r(e), inViewport: b.x >= -0.5 && b.right <= vw + 0.5 && b.width > 0,
      fontWeight: s.fontWeight, borderBottom: s.borderBottomWidth + ' ' + s.borderBottomStyle, textDecoration: s.textDecorationLine,
      fontSize: s.fontSize, scrollW: e.scrollWidth, clientW: e.clientWidth, textClipped: e.scrollWidth > e.clientWidth + 1,
      hitIsSelfOrChild: !!top && (e === top || e.contains(top)), hitElement: top ? (top.tagName + '.' + (top.className||'').toString().slice(0,40) + '[' + (top.getAttribute('data-testid')||'') + ']') : null});
  });
  out.cells = cells;
  let overlaps = [];
  for (let i=0;i<cells.length;i++) for (let j=i+1;j<cells.length;j++){ const a=cells[i].rect,b=cells[j].rect; const ox=Math.min(a.r,b.r)-Math.max(a.x,b.x), oy=Math.min(a.b,b.b)-Math.max(a.y,b.y); if (ox>0.5&&oy>0.5) overlaps.push([i,j,ox,oy]); }
  out.overlaps = overlaps;
  const hdr = document.querySelector('[data-testid="stHeader"]');
  if (hdr) { const hs = getComputedStyle(hdr); out.stHeader = {display: hs.display, position: hs.position, zIndex: hs.zIndex, rect: r(hdr), pointerEvents: hs.pointerEvents, bg: hs.backgroundColor}; }
  out.fixedElements = [...document.querySelectorAll('*')].filter(e => getComputedStyle(e).position === 'fixed' && e.getBoundingClientRect().width > 0).map(e => ({tag:e.tagName, testid:e.getAttribute('data-testid'), cls:(e.className||'').toString().slice(0,50), rect:r(e)})).slice(0,15);
  const sb = document.querySelector('[data-testid="stSidebar"]'); out.sidebar = sb ? {display:getComputedStyle(sb).display, rect:r(sb)} : null;
  out.bottomNavPresent = !!document.querySelector('.st-key-uv3-bottom-nav, [class*="uv3-bn"]');
  const stat = document.querySelector('.uv3-statusbar'); out.statusbar = stat ? r(stat) : null;
  out.chips = [...document.querySelectorAll('.uv3-chip')].map(e => ({t:e.innerText.slice(0,20), ...r(e)}));
  out.charts = [...document.querySelectorAll('svg, [data-testid="stImage"], canvas')].map(e=>r(e)).filter(x=>x.w>150&&x.h>80).slice(0,4);
  out.evidence = [...document.querySelectorAll('.uv3-evidence')].map(e=>({t:e.innerText.slice(0,30),...r(e)}));
  return out;
}
"""
STICKY = """() => { const m=document.querySelector('[data-testid="stMain"]'); const cands=[m,document.scrollingElement]; for(const c of cands){ if(c && c.scrollHeight>c.clientHeight+50){ c.scrollTop=600; return {el:c===m?'stMain':'document', top:c.scrollTop, sh:c.scrollHeight, ch:c.clientHeight}; } } return null; }"""
AFTER = """() => { const n=document.querySelector('.st-key-uv3-top-nav'); if(!n) return null; const b=n.getBoundingClientRect(); const top=document.elementFromPoint(b.x+b.width/2, b.y+Math.min(b.height/2, 20)); return {navTop:b.y, navBottom:b.bottom, hit: top? top.tagName+'.'+(top.className||'').toString().slice(0,50):null}; }"""
BOTTOM = """() => { const m=document.querySelector('[data-testid="stMain"]'); const c=(m && m.scrollHeight>m.clientHeight+50)?m:document.scrollingElement; c.scrollTop=c.scrollHeight; const f=document.querySelector('.uv3-footer'); return {top:c.scrollTop, sh:c.scrollHeight, ch:c.clientHeight, atBottom: Math.abs(c.scrollTop + c.clientHeight - c.scrollHeight) < 2, footer: f? {y:f.getBoundingClientRect().y, b:f.getBoundingClientRect().bottom}:null, vh: innerHeight}; }"""
FOCUS = """() => { const e=document.activeElement; if(!e) return null; const s=getComputedStyle(e); return {tag:e.tagName, testid:e.getAttribute('data-testid'), text:(e.innerText||'').replace(/\\s+/g,' ').slice(0,20), href:e.getAttribute('href'), inTopNav: !!e.closest('.st-key-uv3-top-nav'), inSidebar: !!e.closest('[data-testid="stSidebar"]'), focusVisible: e.matches(':focus-visible'), outline: s.outlineWidth+' '+s.outlineStyle+' '+s.outlineColor, outlineOffset:s.outlineOffset}; }"""
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1243/chrome-linux64/chrome', args=['--no-proxy-server'])
    for w in WIDTHS:
        ctx = b.new_context(viewport={'width': w, 'height': 844}, device_scale_factor=2 if w < 800 else 1, locale='zh-TW', timezone_id='Asia/Taipei', has_touch=w <= 768)
        pg = ctx.new_page()
        pg.goto(URL, wait_until='networkidle')
        pg.wait_for_selector('.uv3-statusbar', timeout=60000)
        if FONT:
            # simulate OS/browser font enlargement: scale root font-size (rem) and body text
            k = int(FONT) / 100
            pg.add_style_tag(content=(f"html{{font-size:{16*k}px !important}} body, .stApp{{font-size:{16*k}px}}"
                f".st-key-uv3-top-nav a[data-testid='stPageLink-NavLink'], .st-key-uv3-top-nav a[data-testid='stPageLink-NavLink'] p,.st-key-uv3-top-nav .uv3-tn-disabled{{font-size:{12*k}px !important}}"
                f".st-key-uv3-top-nav .uv3-tn-icon{{font-size:{20*k}px !important}} .st-key-uv3-top-nav .uv3-tn-soon{{font-size:{10*k}px !important}}"))
        pg.wait_for_timeout(2500)
        m = pg.evaluate(JS)
        pg.screenshot(path=f'{OUT}/{TAG}_w{w}_top.png')
        pg.screenshot(path=f'{OUT}/{TAG}_w{w}_full.png', full_page=True)
        m['scroll'] = pg.evaluate(STICKY)
        pg.wait_for_timeout(500)
        m['afterScroll'] = pg.evaluate(AFTER)
        pg.screenshot(path=f'{OUT}/{TAG}_w{w}_scrolled.png')
        m['bottom'] = pg.evaluate(BOTTOM)
        pg.wait_for_timeout(500)
        pg.screenshot(path=f'{OUT}/{TAG}_w{w}_bottom.png')
        pg.evaluate("""() => { const m=document.querySelector('[data-testid="stMain"]'); if(m) m.scrollTop=0; window.scrollTo(0,0); }""")
        seq = []
        for i in range(8):
            pg.keyboard.press('Tab')
            seq.append(pg.evaluate(FOCUS))
            if seq[-1] and seq[-1]['inTopNav'] and seq[-1]['focusVisible'] and not FONT:
                pg.screenshot(path=f'{OUT}/{TAG}_w{w}_focus.png')
        m['tabSeq'] = seq
        res[w] = m
        ctx.close()
    b.close()
json.dump(res, open(f'{OUT}/{TAG}_measure.json', 'w'), ensure_ascii=False, indent=1)
print('done')
