# -*- coding: utf-8 -*-
"""UI-E 🌍 市場比較圖雙系列色票候選：色彩量測、HTML 產生、Chromium 截圖與版面量測（可重現）。

用法（repo 根目錄；`colors` 只需標準函式庫，`build`／`shoot` 另需 playwright 與 Pillow）::

    python docs/evidence/ui_e_dual_series_palette_2026_11_20/measure.py colors   # 只印色彩量測表
    python docs/evidence/ui_e_dual_series_palette_2026_11_20/measure.py build    # 寫 docs/design/ui_v3_market_dual_series_palette_review_2026_11_20.html
    UI_V2_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome \\
        python docs/evidence/ui_e_dual_series_palette_2026_11_20/measure.py shoot    # 390／1280 截圖＋版面量測

不 import 任何 ui_v3 套件（以 importlib 從檔案路徑讀 `chart_svg.py` 的純函式來畫與正式圖同幾何的折線；該檔只用標準函式庫）。
不改任何既有檔；不抓外部資料；資料為人造波形（FAKE）。

量測定義（全部可由本檔重現）：
- 相對亮度 L = 0.2126 R + 0.7152 G + 0.0722 B（R／G／B 為 sRGB 去伽瑪後的線性值，WCAG 2.x 定義）；
- 對比 = (L亮 + 0.05) / (L暗 + 0.05)；
- 色覺差異模擬：Machado, Oliveira, Fernandes 2009 的 protan／deutan／tritan 3×3 矩陣（severity 1.0），在線性 RGB 乘矩陣後截到 [0,1]；
  這是模型模擬，不是真人測試；
- 兩色距離：模擬後（或原色）的線性 RGB → XYZ（D65）→ CIE L*a*b*，取 CIE76 ΔE（歐氏距離）；本專案沒有核准的 ΔE 門檻，數字只供相對比較；
- 灰階：灰階值 = 相對亮度 L（線性）再編回 sRGB；兩線灰階亮度比 = 上述對比公式套在兩個灰階色上。
"""
from __future__ import annotations

import importlib.util
import math
import os
import re
import sys
from datetime import date, timedelta
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HTML_OUT = ROOT / "docs" / "design" / "ui_v3_market_dual_series_palette_review_2026_11_20.html"
EXE = os.environ.get("UI_V2_CHROMIUM") or None

# ── 現行核准 token 值（來源：ui_v3/design/tokens.py PALETTE／TONE_VALUES；此處只讀它們的值當對照底色，不改 tokens.py）──
SURFACE, PAGE_BG, TEXT = "#ffffff", "#f5f7fb", "#172033"
REFERENCE_COLORS = {
    "primary（選取 pill 填色）": "#1a5fd0",
    "yellow 狀態邊": "#b7791f",
    "red 狀態邊": "#c0392b",
    "grey／neutral 狀態邊": "#7f8ca6",
    "sidebar accent": "#5fd3d0",
}
NON_TEXT_MIN = 3.0   # WCAG 2.x 1.4.11 非文字對比 3:1（只是參考門檻，不是本專案核准規則）

# 候選：每個兩條色（series 1 實線、series 2 虛線——沿用 chart_svg 的 index%2==1 虛線規則）。
CANDIDATES = {
    "A": {"name": "深藍＋橙", "hues": "藍／橙", "s1": "#0a3f86", "s2": "#d06a00"},
    "B": {"name": "靛紫＋青綠", "hues": "靛紫／藍綠", "s1": "#4b2fa8", "s2": "#0a8f80"},
    "C": {"name": "深藍＋洋紅", "hues": "藍／洋紅", "s1": "#1a3f8f", "s2": "#c2338e"},
}
BASELINE = {"s1": TEXT, "s2": TEXT}   # 現況：兩線都是 currentColor＝文字色，只靠實／虛線與末點標籤分辨

MACHADO = {  # Machado et al. 2009, severity 1.0
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}
CVD_NAMES = {"protan": "protan（紅色弱／盲）", "deutan": "deutan（綠色弱／盲）", "tritan": "tritan（藍黃色弱／盲）"}


# ───────────────────────────── 色彩數學 ─────────────────────────────
def _rgb(hexs: str):
    h = hexs.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _lin(c8: float) -> float:
    c = c8 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _enc(c: float) -> int:
    c = max(0.0, min(1.0, c))
    v = c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return int(round(v * 255))


def to_hex(lin_rgb) -> str:
    return "#" + "".join(f"{_enc(c):02x}" for c in lin_rgb)


def lin_rgb(hexs: str):
    return [_lin(x) for x in _rgb(hexs)]


def luminance(hexs: str) -> float:
    r, g, b = lin_rgb(hexs)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def simulate(hexs: str, kind: str) -> str:
    v = lin_rgb(hexs)
    m = MACHADO[kind]
    return to_hex([sum(m[i][j] * v[j] for j in range(3)) for i in range(3)])


def gray(hexs: str) -> str:
    y = luminance(hexs)
    return to_hex([y, y, y])


def _lab(hexs: str):
    r, g, b = lin_rgb(hexs)
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e76(a: str, b: str) -> float:
    return math.dist(_lab(a), _lab(b))


def metrics() -> dict:
    out = {}
    for key, c in CANDIDATES.items():
        s1, s2 = c["s1"], c["s2"]
        row = {"s1": s1, "s2": s2}
        row["contrast_surface"] = (contrast(s1, SURFACE), contrast(s2, SURFACE))
        row["contrast_page"] = (contrast(s1, PAGE_BG), contrast(s2, PAGE_BG))
        row["de_normal"] = delta_e76(s1, s2)
        row["sim"] = {k: (simulate(s1, k), simulate(s2, k)) for k in MACHADO}
        row["de_cvd"] = {k: delta_e76(*row["sim"][k]) for k in MACHADO}
        row["gray"] = (gray(s1), gray(s2))
        row["gray_ratio"] = contrast(*row["gray"])
        row["lum"] = (luminance(s1), luminance(s2))
        row["ref_de"] = {name: (delta_e76(s1, ref), delta_e76(s2, ref)) for name, ref in REFERENCE_COLORS.items()}
        out[key] = row
    return out


def print_colors() -> None:
    m = metrics()
    print("== 底色：surface", SURFACE, "／page.bg", PAGE_BG, "／text", TEXT)
    print(f"== 基線（現況：兩線皆 currentColor＝{TEXT}）：對 surface {contrast(TEXT, SURFACE):.2f}，兩線同色（ΔE76 0.0、灰階比 1.00），"
          "分辨完全靠實／虛線＋末點標籤")
    for key, r in m.items():
        c = CANDIDATES[key]
        print(f"\n== 候選 {key}｜{c['name']}｜series1 實線 {r['s1']}、series2 虛線 {r['s2']}")
        print(f"  對 surface {SURFACE} 對比：s1 {r['contrast_surface'][0]:.2f}、s2 {r['contrast_surface'][1]:.2f}"
              f"（參考 3:1：{'皆達' if min(r['contrast_surface']) >= NON_TEXT_MIN else '未達'}）")
        print(f"  對 page.bg {PAGE_BG} 對比：s1 {r['contrast_page'][0]:.2f}、s2 {r['contrast_page'][1]:.2f}"
              f"（參考 3:1：{'皆達' if min(r['contrast_page']) >= NON_TEXT_MIN else '未達'}）")
        print(f"  兩線距離 CIE76 ΔE：原色 {r['de_normal']:.1f}；" + "；".join(f"{k} {r['de_cvd'][k]:.1f}" for k in MACHADO))
        for k in MACHADO:
            print(f"    {k} 模擬色：s1 {r['sim'][k][0]}、s2 {r['sim'][k][1]}")
        print(f"  灰階：s1 {r['gray'][0]}（L={r['lum'][0]:.4f}）、s2 {r['gray'][1]}（L={r['lum'][1]:.4f}）；兩線灰階亮度比 {r['gray_ratio']:.2f}")
        for name, (d1, d2) in r["ref_de"].items():
            print(f"  與「{name} {REFERENCE_COLORS[name]}」ΔE76：s1 {d1:.1f}、s2 {d2:.1f}")
    print("\n== NOT RUN：真人色覺測試；實機螢幕／印表機／黑白列印；severity<1（部分色弱）；Brettel／Viénot 等其他演算法；achromatopsia 以外的單色視覺")


# ───────────────────────────── 人造資料與 SVG ─────────────────────────────
def _chart_module():
    spec = importlib.util.spec_from_file_location("uie_chart_svg", ROOT / "ui_v3" / "pages" / "chart_svg.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def fake_series():
    """FAKE 人造波形（決定性、無亂數、無時鐘）：一年平日，兩條歸一化（基準日＝100）。形狀仿 tests/ui_v3/market_stubs.wave，不取自任何真實行情。"""
    days, d = [], date(2025, 11, 3)
    while d <= date(2026, 11, 2):
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    f1 = [0.0125 * i + 2.2 * math.sin(i / 9.0) for i in range(len(days))]
    f2 = [0.0230 * i + 3.0 * math.sin(i / 7.0 + 0.8) for i in range(len(days))]
    s1 = [(day.isoformat(), 100.0 + v - f1[0]) for day, v in zip(days, f1)]
    s2 = [(day.isoformat(), 100.0 + v - f2[0]) for day, v in zip(days, f2)]
    return s1, s2


def colored_primary_svg(s1_hex: str, s2_hex: str, aria: str) -> str:
    cs = _chart_module()
    a, b = fake_series()
    lines = [cs.Line(tuple(a), dashed=False, end_label=f"台股 {a[-1][1]:.1f}"),
             cs.Line(tuple(b), dashed=True, end_label=f"S&P 500 {b[-1][1]:.1f}")]
    svg = cs.line_chart_svg(lines, aria_label=aria)
    paths = iter((s1_hex, s2_hex))
    svg = re.sub(r'(<path [^>]*?stroke=")currentColor(")', lambda m: m.group(1) + next(paths) + m.group(2), svg)
    dots = iter((s1_hex, s2_hex))
    svg = re.sub(r'(<circle [^>]*?fill=")currentColor(")', lambda m: m.group(1) + next(dots) + m.group(2), svg)
    return svg.replace('<svg class="uv3-chart"', '<svg class="chart"', 1)


def mini_svg(c1: str, c2: str, label: str) -> str:
    """辨識列的小圖：週取樣、無文字（裝飾用，標籤在 HTML）、保留實／虛線與末點圓。"""
    a, b = fake_series()
    a, b = a[::5] + [a[-1]], b[::5] + [b[-1]]
    vals = [v for _d, v in a + b]
    lo, hi = min(vals), max(vals)
    w, h, pad = 160, 56, 5

    def pts(series):
        n = len(series) - 1
        return [(pad + i / n * (w - 2 * pad), pad + (hi - v) / (hi - lo) * (h - 2 * pad)) for i, (_d, v) in enumerate(series)]
    out = [f'<svg class="mini" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label, quote=True)}" xmlns="http://www.w3.org/2000/svg">']
    for color, series, dash in ((c1, a, ""), (c2, b, ' stroke-dasharray="6 4"')):
        p = pts(series)
        out.append(f'<path d="M{" L".join(f"{x:.1f} {y:.1f}" for x, y in p)}" fill="none" stroke="{color}" stroke-width="2"{dash} '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
        out.append(f'<circle cx="{p[-1][0]:.1f}" cy="{p[-1][1]:.1f}" r="3" fill="{color}"/>')
    out.append("</svg>")
    return "".join(out)


# ───────────────────────────── HTML ─────────────────────────────
CSS = """
:root{color-scheme:light;
  --page:#f5f7fb;--surface:#ffffff;--text:#172033;--text2:#4a5670;--primary:#1a5fd0;--border:#7f8ca6;
  --sb:#101a33;--sb2:#18254a;--sb-text:#e6edf3;--sb-text2:#aab6cf;--sb-accent:#5fd3d0;--sb-border:#34466e;
  --grey-bg:#e6eaf3;--yellow-bg:#fbf0d6;--yellow-bd:#b7791f;--yellow-tx:#6b4a0a;--red-bg:#fbe6e2;--red-bd:#c0392b;--red-tx:#8a1f12}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--text);font:15px/1.55 "Noto Sans TC","PingFang TC","Microsoft JhengHei","WenQuanYi Zen Hei",system-ui,sans-serif;overflow-wrap:anywhere}
h1{font-size:1.7rem;line-height:1.3;margin:0 0 8px}
h2{font-size:1.2rem;line-height:1.35;margin:0 0 8px}
h3{font-size:15px;line-height:1.4;margin:0 0 4px}
p{margin:0 0 8px}
ul,ol{margin:0 0 8px;padding-left:24px}
li{margin:2px 0}
code{font-family:"DejaVu Sans Mono",ui-monospace,monospace;font-size:13px;background:var(--grey-bg);padding:0 4px;border-radius:4px}
.wrap{max-width:1240px;margin:0 auto;padding:16px}
.s{font-size:13px;color:var(--text2)}
.nw{white-space:nowrap}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 12px;padding:0;list-style:none}
.tags li{border:1px solid var(--primary);color:var(--primary);background:var(--surface);border-radius:12px;padding:1px 10px;font-size:14px;font-weight:700;margin:0}
.tags li.warn{border-color:var(--yellow-bd);background:var(--yellow-bg);color:var(--yellow-tx)}
.callout{background:var(--surface);border:1px dashed var(--primary);border-radius:8px;padding:10px 12px;margin:0 0 12px}
.callout.warn{border-style:solid;border-left:8px solid var(--yellow-bd);background:var(--yellow-bg);color:var(--yellow-tx)}
.stage{margin:0 0 24px}
.app{display:grid;grid-template-columns:minmax(0,1fr);border:1px solid var(--border);border-radius:8px;background:var(--page);overflow:hidden}
.side{display:none;background:var(--sb);color:var(--sb-text);padding:16px 12px}
.topnav{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));background:var(--surface);border-bottom:1px solid var(--border);margin:0;padding:0;list-style:none}
.topnav li{margin:0;min-width:0}
.tn{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;min-height:60px;height:100%;padding:2px 0;text-align:center;font-size:13px;line-height:1.2;color:var(--text2);border-bottom:3px solid transparent}
.tn .ic{font-size:20px;line-height:1}
.tn.now{color:var(--text);font-weight:700;border-bottom-color:var(--text);text-decoration:underline;text-underline-offset:3px}
.main{padding:16px;min-width:0}
.brand{font-size:17px;font-weight:700;margin:0 0 12px;line-height:1.3}
.sidenav{list-style:none;margin:0;padding:0}
.sidenav li{margin:0 0 4px}
.sn{display:flex;align-items:center;gap:8px;min-height:48px;padding:0 12px;border-radius:8px;font-size:15px;color:var(--sb-text)}
.sn.dis{color:var(--sb-text2)}
.sn .soon{margin-left:auto;font-size:13px;border:1px dashed var(--sb-text2);border-radius:10px;padding:0 6px}
.sn.now{font-weight:700;border-left:4px solid var(--sb-accent);background:var(--sb2)}
.statusbar{display:flex;flex-wrap:wrap;align-items:center;gap:2px 10px;font-size:13px;line-height:1.5;color:var(--text2);margin:0 0 8px}
.statusbar .tag{font-weight:700;letter-spacing:.06em;border:1px solid currentColor;border-radius:4px;padding:0 5px}
.apptitle{font-size:1.7rem;line-height:1.3;margin:0 0 8px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 12px;margin:0 0 12px;min-width:0}
.card h2{margin-bottom:4px}
.fake{border:1px dashed var(--border);background:var(--surface);border-radius:8px;padding:6px 10px;margin:0 0 8px;font-size:13px;color:var(--text2)}
.fake strong{color:var(--text)}
.ctl{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;margin:0 0 6px}
.ctl .lb{font-size:13px;color:var(--text2);margin-right:2px}
.pill{display:inline-flex;align-items:center;justify-content:center;min-height:48px;min-width:48px;padding:0 12px;border:1px solid var(--border);border-radius:999px;background:var(--surface);font-size:14px}
.pill.on{background:var(--primary);border-color:var(--primary);color:#fff;font-weight:700}
.note{font-size:13px;color:var(--text2);margin:6px 0}
.cand{display:grid;grid-template-columns:minmax(0,1fr);gap:8px}
.chart{width:100%;max-width:720px;height:auto;display:block;color:var(--text);overflow:visible}
.sw{display:inline-block;width:14px;height:14px;border-radius:3px;border:1px solid var(--border);vertical-align:-2px;margin-right:4px}
.legend{font-size:13px;color:var(--text2);margin:4px 0}
.legend .ln{display:inline-block;width:28px;height:0;border-top:3px solid;vertical-align:middle;margin:0 4px 0 8px}
.legend .ln.d{border-top-style:dashed}
.strip{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.strip figure{margin:0;border:1px solid var(--border);border-radius:8px;padding:6px 8px;background:var(--surface);min-width:0}
.strip figcaption{font-size:13px;color:var(--text2);margin-top:2px}
.mini{width:100%;height:auto;display:block}
table.cmp{width:100%;border-collapse:collapse;font-size:14px;display:block;overflow-wrap:anywhere}
table.cmp thead{display:none}
table.cmp tbody,table.cmp tr,table.cmp td{display:block}
table.cmp tr{border:1px solid var(--border);border-radius:8px;background:var(--surface);padding:8px 10px;margin:0 0 8px}
table.cmp td{padding:2px 0}
table.cmp td::before{content:attr(data-label);display:block;font-size:13px;color:var(--text2)}
.notes{margin-top:24px}
.notes section{margin:0 0 24px}
details.fold{border:1px solid var(--border);border-radius:8px;background:var(--surface);margin:0 0 12px}
details.fold>summary{display:flex;align-items:center;min-height:48px;padding:0 12px;cursor:pointer;font-weight:700;list-style:none}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary::before{content:"▸ ";margin-right:4px}
details.fold[open]>summary::before{content:"▾ "}
details.fold .body{padding:0 12px 12px}
.gray{filter:grayscale(1)}
@media (max-width:768px){
  .chart{width:calc(100% + 24px);margin-left:-12px}
}
@media (min-width:769px){
  .app{grid-template-columns:300px minmax(0,1fr)}
  .side{display:block}
  .topnav{display:none}
  .main{padding:16px 16px 16px 16px}
  .cand{grid-template-columns:minmax(0,1fr) 230px;align-items:start}
  .strip{grid-template-columns:minmax(0,1fr)}
  table.cmp{display:table}
  table.cmp thead{display:table-header-group}
  table.cmp tbody{display:table-row-group}
  table.cmp tr{display:table-row;border:0;padding:0;margin:0}
  table.cmp td,table.cmp th{display:table-cell;padding:6px 8px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}
  table.cmp td::before{content:none}
  table.cmp th{font-size:13px;color:var(--text2);font-weight:700}
}
"""


def _fmt2(x: float) -> str:
    return f"{x:.2f}"


def _status_note(row: dict) -> str:
    return ("皆達" if min(row["contrast_surface"]) >= NON_TEXT_MIN else "未達")


def _candidate_card(key: str, m: dict) -> str:
    c, r = CANDIDATES[key], m[key]
    aria = f"候選 {key}：台股與 S&P 500 歸一化折線（FAKE 示意波形）"
    minis = [("原色", r["s1"], r["s2"]), ("灰階", r["gray"][0], r["gray"][1])] + \
            [(CVD_NAMES[k].split("（")[0] + " 模擬", r["sim"][k][0], r["sim"][k][1]) for k in MACHADO]
    figs = "".join(f"<figure>{mini_svg(a, b, f'候選 {key} {name}')}<figcaption>{escape(name)}</figcaption></figure>" for name, a, b in minis)
    return f"""
<section class="card" aria-label="候選 {key}">
  <h2>候選 {key}｜{c['name']}</h2>
  <p class="fake"><strong>設計提案，尚未核准。</strong>FAKE 示意波形，數值不代表任何真實行情；不是 production 畫面。</p>
  <div class="cand">
    <div>
      <h3>台股 vs S&amp;P 500（歸一化）</h3>
      <div class="ctl"><span class="lb">檢視</span><span class="pill on">比較</span><span class="pill">VIX</span><span class="pill">美10Y</span><span class="pill">美2Y</span></div>
      <div class="ctl"><span class="lb">期間</span><span class="pill">3M</span><span class="pill">6M</span><span class="pill on">1Y</span><span class="pill">3Y</span></div>
      <p class="note">基準日 2025-11-03＝100；頻率：日｜缺值不補、斷線</p>
      {colored_primary_svg(r['s1'], r['s2'], aria)}
      <p class="legend"><span class="sw" style="background:{r['s1']}"></span>台股 {r['s1']}<span class="ln" style="border-top-color:{r['s1']}"></span>實線
        <span class="sw" style="background:{r['s2']};margin-left:8px"></span>S&amp;P 500 {r['s2']}<span class="ln d" style="border-top-color:{r['s2']}"></span>虛線</p>
    </div>
    <div>
      <h3>辨識列（同一組兩線）</h3>
      <div class="strip">{figs}</div>
      <p class="note">模擬色是依下方演算法算出的色值；灰階＝相對亮度。小圖無文字，標籤與線型照留。</p>
    </div>
  </div>
</section>"""


def _table(m: dict) -> str:
    def cell(label, val):
        return f'<td data-label="{label}">{val}</td>'
    head = ("<thead><tr><th>候選</th><th>series 色值</th><th>對 surface #ffffff</th><th>對 page.bg #f5f7fb</th>"
            "<th>兩線 ΔE76（原色／protan／deutan／tritan）</th><th>灰階（兩線亮度比）</th><th>主要風險</th></tr></thead>")
    risks = {
        "A": "橙色是三組中離 yellow 狀態邊（ΔE76 20.3）與 red 狀態邊（32.2）最近的，可能被讀成「警示」；橙色對 page.bg 只有 3.41:1，剛過參考 3:1，沒有餘裕；深藍離 primary 藍 26.5，同屬冷色。",
        "B": "藍綠（teal）可能被讀成「綠＝好」；tritan 下兩線 ΔE 最小；靛紫與 primary 藍同屬冷色。",
        "C": "洋紅在視覺上偏紅系，仍可能被讀成「紅＝壞」（數值上離 red 狀態邊 58.0，比 A 的橙遠）；protan 下兩線 ΔE 最小（18.8），兩線都變成偏藍灰；灰階亮度比最低（1.94）。",
    }
    rows = []
    rows.append("<tr>" + cell("候選", "現況（基線）") + cell("series 色值", f"兩線同為文字色 {TEXT}") +
                cell("對 surface #ffffff", f"{_fmt2(contrast(TEXT, SURFACE))}") + cell("對 page.bg #f5f7fb", f"{_fmt2(contrast(TEXT, PAGE_BG))}") +
                cell("兩線 ΔE76（原色／protan／deutan／tritan）", "0.0／0.0／0.0／0.0（同色）") + cell("灰階（兩線亮度比）", "1.00（同色）") +
                cell("主要風險", "兩線同色，只靠實／虛線與末點標籤；這就是本提案要改善的差距。") + "</tr>")
    for key, r in m.items():
        c = CANDIDATES[key]
        sw1 = f'<span class="sw" style="background:{r["s1"]}"></span>'
        sw2 = f'<span class="sw" style="background:{r["s2"]}"></span>'
        rows.append("<tr>" + cell("候選", f"<strong>{key}｜{c['name']}</strong>") +
                    cell("series 色值", f"{sw1}{r['s1']}（實線）<br>{sw2}{r['s2']}（虛線）") +
                    cell("對 surface #ffffff", f"{_fmt2(r['contrast_surface'][0])}／{_fmt2(r['contrast_surface'][1])}（參考 3:1：{_status_note(r)}）") +
                    cell("對 page.bg #f5f7fb", f"{_fmt2(r['contrast_page'][0])}／{_fmt2(r['contrast_page'][1])}") +
                    cell("兩線 ΔE76（原色／protan／deutan／tritan）",
                         f"{r['de_normal']:.1f}／{r['de_cvd']['protan']:.1f}／{r['de_cvd']['deutan']:.1f}／{r['de_cvd']['tritan']:.1f}") +
                    cell("灰階（兩線亮度比）", f"{r['gray'][0]}／{r['gray'][1]}（{_fmt2(r['gray_ratio'])}）") +
                    cell("主要風險", risks[key]) + "</tr>")
    return f'<table class="cmp" aria-label="候選比較表">{head}<tbody>{"".join(rows)}</tbody></table>'


def _ref_table(m: dict) -> str:
    names = list(REFERENCE_COLORS)
    head = "<thead><tr><th>與下列既有色的 ΔE76（series 1／series 2）</th>" + "".join(f"<th>候選 {k}</th>" for k in m) + "</tr></thead>"
    rows = []
    for n in names:
        tds = "".join(f'<td data-label="候選 {k}">{m[k]["ref_de"][n][0]:.1f}／{m[k]["ref_de"][n][1]:.1f}</td>' for k in m)
        rows.append(f'<tr><td data-label="既有色"><strong>{escape(n)}</strong> {REFERENCE_COLORS[n]}</td>{tds}</tr>')
    return f'<table class="cmp" aria-label="與既有狀態色的距離">{head}<tbody>{"".join(rows)}</tbody></table>'


def build_html() -> str:
    m = metrics()
    cards = "".join(_candidate_card(k, m) for k in CANDIDATES)
    nav5 = "".join(f'<li><div class="tn{" now" if i == 0 else ""}"><span class="ic" aria-hidden="true">{ic}</span><span>{t}</span></div></li>'
                   for i, (ic, t) in enumerate((("🌍", "市場"), ("💼", "資產"), ("🔍", "找基金"), ("⚇", "AI"), ("⚙️", "設定"))))
    sidenav = ('<li><div class="sn now"><span aria-hidden="true">🌍</span><span>市場與趨勢</span></div></li>'
               '<li><div class="sn dis"><span aria-hidden="true">💼</span><span>我的資產</span><span class="soon">開發中</span></div></li>'
               '<li><div class="sn dis"><span aria-hidden="true">🔍</span><span>找基金</span><span class="soon">開發中</span></div></li>'
               '<li><div class="sn dis"><span aria-hidden="true">⚇</span><span>AI 投資總結</span><span class="soon">尚未開放</span></div></li>'
               '<li><div class="sn dis"><span aria-hidden="true">⚙️</span><span>設定</span><span class="soon">開發中</span></div></li>')
    page = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🌍 市場比較圖雙系列色票候選｜設計提案</title>
<meta name="description" content="ui_v3 🌍 市場比較圖兩條線的系列色票候選（docs-only 設計提案；fixture 為人造波形；未經客戶核准；不等於 Cloud PASS）。">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<h1>🌍 市場比較圖：雙系列色票候選</h1>
<ul class="tags" aria-label="狀態標示">
  <li class="warn">設計提案，尚未核准</li><li class="warn">fixture 非真資料（人造波形）</li><li class="warn">不等於 Cloud PASS</li><li>docs-only：不改 tokens／chart_svg／mkt</li>
</ul>
<div class="callout warn">
  <p><strong>這份只回答一個問題：</strong>🌍 市場頁「台股 vs S&amp;P 500（歸一化）」主圖的兩條線，現在同為文字色、只靠實線／虛線與末點標籤分辨；
  若客戶同意改成兩色，候選色值有哪些、各自對底色與色覺差異的量測、風險各是什麼。<strong>色值尚未核准</strong>（<code>ui_v3/design/tokens.py</code> 的 <code>chart.*</code> 仍為 None）。</p>
  <p class="s">依據：<code>docs/v2/44</code> 第七節第三小節之十八其三（客戶 <code>DEC-2026-10-27-27</code> 允許系列色；值未核准；顏色只分辨「這是哪一條」、不帶好壞語意；每張圖至少另有一種不靠顏色的辨識）、
  <code>BL-0561</code> R2、<code>docs/evidence/ui_next_batch_gap_2026_11_20.md</code> R2。使用者參考圖：<strong>NOT PROVIDED</strong>（本批沒有取得；候選為依既有 token 與公式獨立推導，不是仿某張圖）。</p>
</div>

<div class="stage" aria-label="示意畫面">
<div class="app">
  <nav class="side" aria-label="桌機側欄（示意）"><p class="brand">基金投資儀表板</p><ul class="sidenav">{sidenav}</ul></nav>
  <ul class="topnav" aria-label="手機頁首五格（示意）">{nav5}</ul>
  <div class="main">
    <div class="statusbar" role="status"><span class="tag">PREVIEW</span><span>更新：2026-11-03 14:00（示意）</span></div>
    <h2 class="apptitle">🌍 市場與趨勢</h2>
    <p class="note">下列三張卡是同一張主圖、三組候選色；版面沿用現有合法版面（pill 控制列＋單 Y 軸折線＋末點標籤），<strong>沒有新增或刪減元件</strong>。</p>
    {cards}
  </div>
</div>
</div>

<div class="notes">
<section aria-labelledby="h-cmp"><h2 id="h-cmp">候選比較表</h2>
{_table(m)}
<p class="s">數值全由 <code>measure.py</code> 計算（公式與演算法見下）。對比欄是「series 1／series 2」。灰階欄是兩線轉灰階後的色值與其亮度比；比值接近 1 代表只靠灰階分不開、必須靠線型與末點標籤。</p>
<h3 style="margin-top:12px">與既有語意色的距離（避開 red／yellow／grey 狀態語意）</h3>
{_ref_table(m)}
<p class="s">本專案沒有核准的 ΔE 門檻；這張表只用來比較「哪個候選離狀態色較近」，不做通過／不通過判定。</p>
</section>

<section aria-labelledby="h-rec"><h2 id="h-rec">推薦方案（僅為建議，不代客戶選色）</h2>
<p><strong>建議候選 A（深藍＋橙）。</strong>理由（皆為上表量測）：色覺模擬下兩線距離在三型都最大（protan／deutan／tritan 的 ΔE76 見表，tritan 也最大）、灰階亮度比最高（兩線在灰階下仍有明顯深淺差）、橙與藍是色覺差異族群最常用的可分辨色對。
<strong>它的風險要一併看：</strong>橙色與既有 yellow 狀態邊色相相近，且對 page.bg 的對比只剛過參考的 3:1。若客戶在意「橙＝警示」的聯想，B 的色彩距離次佳（tritan 38.3 明顯較弱）且藍綠有「綠＝好」的聯想風險；C 的 protan 距離最弱（18.8）、灰階亮度比最低。</p>
<p>三個候選都：不用紅／綠當好壞、保留實線／虛線與末點標籤（顏色全程不是唯一訊息）、兩線同時存在時不改變單 Y 軸、不畫 band／目標價／100 基準線、缺值仍斷線。<strong>這是建議，不是決定；是否採用、採哪一組、是否要換更保守的色，由客戶裁示。</strong></p>
</section>

<section aria-labelledby="h-method"><h2 id="h-method">量測方法（可由 measure.py 重現）</h2>
<ul>
<li><strong>對比</strong>：WCAG 2.x 相對亮度，對比 ＝ (L亮＋0.05) ÷ (L暗＋0.05)。3:1 是 WCAG 1.4.11 非文字對比的<em>參考</em>門檻，本專案未核准該門檻。</li>
<li><strong>色覺差異模擬</strong>：Machado、Oliveira、Fernandes（2009）protan／deutan／tritan 3×3 矩陣，severity 1.0，在線性 RGB 乘矩陣後截到 0–1，再編回 sRGB。這是<em>模型模擬</em>，不是真人測試；severity 小於 1（部分色弱）沒有跑。</li>
<li><strong>兩色距離</strong>：線性 RGB → XYZ（D65）→ CIE L*a*b*，CIE76 ΔE（歐氏距離）。只供相對比較。</li>
<li><strong>灰階</strong>：灰階值＝相對亮度 L 編回 sRGB；兩線灰階亮度比＝上面的對比公式套在兩個灰階色上。</li>
<li><strong>不依賴顏色的辨識</strong>：series 1 實線、series 2 虛線（<code>chart_svg</code> 既有 index 奇偶規則）；末點圓點＋直接標籤（含數值）；上方「辨識列」的灰階與三型色覺小圖仍可用線型與末點分辨。</li>
<li><strong>NOT RUN</strong>：真人色覺測試；實機螢幕與印表機／黑白列印；severity 小於 1；Brettel／Viénot 等其他模擬演算法；iOS／Android／WebView 真機；Cloud <code>ui_v3</code>。</li>
</ul>
</section>

<section aria-labelledby="h-scope"><h2 id="h-scope">若客戶核准後的實作範圍（本批沒有動）</h2>
<ul>
<li>預計會碰：<code>ui_v3/design/tokens.py</code>（新增 chart series token 與值）、<code>ui_v3/pages/chart_svg.py</code>（把 <code>currentColor</code> 的線與末點改吃 token；目前測試鎖 currentColor，須同批改）、迷你圖同色、對應測試。這些<strong>本批都沒有改</strong>。</li>
<li>不碰：單 Y 軸、最多 3 條線、斷線不補、不畫 band／目標價線、資料源與公式。</li>
<li>末點標籤文字色維持文字色（不另上色），只有線與末點圓使用系列色。</li>
</ul>
</section>

<section aria-labelledby="h-unv"><h2 id="h-unv">NOT VERIFIED</h2>
<p>Cloud <code>ui_v3</code> URL、部署 SHA、真機、真人色覺測試、客戶是否同意兩線不同色與具體色值、本提案的獨立複驗。<strong>示意殼的字級（13px）與正式頁首導覽（12px／10px，見 #1298 R1）不同，這是示意，不代表正式畫面。</strong></p>
</section>
</div>
</div>
</body>
</html>
"""
    return page


# ───────────────────────────── 截圖與版面量測 ─────────────────────────────
JS = """
() => {
  const de = document.documentElement;
  const shown = el => { for (let a = el; a; a = a.parentElement) { if (getComputedStyle(a).display === 'none') return false; } return true; };
  const o = {scrollWidth: de.scrollWidth, clientWidth: de.clientWidth, fullHeight: de.scrollHeight};
  let min = 1e9, small = 0; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const t = w.currentNode; if (!t.textContent.trim()) continue;
    const el = t.parentElement; if (!shown(el) || el.closest('svg')) continue;
    const d = el.closest('details'); if (d && !d.open && !el.closest('summary')) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize); min = Math.min(min, fs); if (fs < 13) small++;
  }
  o.htmlMinFontPx = min; o.htmlTextNodesUnder13px = small;
  const t = [...document.querySelectorAll('.pill, summary, .tn, .sn')].filter(shown);
  o.touchTargets = t.length; o.touchMinHeightPx = Math.min(...t.map(e => e.getBoundingClientRect().height));
  o.touchUnder48 = t.filter(e => e.getBoundingClientRect().height < 48).length;
  o.overflowElements = [...document.querySelectorAll('body *')].filter(e => shown(e) && e.getBoundingClientRect().width
    && e.getBoundingClientRect().right > de.clientWidth + 1).length;
  const svgs = [...document.querySelectorAll('svg.chart')].filter(shown);
  o.primaryCharts = svgs.length;
  o.primaryChartWidthPx = svgs.length ? svgs[0].getBoundingClientRect().width : null;
  const tx = svgs.length ? [...svgs[0].querySelectorAll('text')].map(e => parseFloat(getComputedStyle(e).fontSize) * (svgs[0].getBoundingClientRect().width / 360)) : [];
  o.primaryChartSvgTextRenderedPx = tx.length ? [Math.min(...tx), Math.max(...tx)].map(v => Math.round(v * 100) / 100) : null;
  const vis = s => { const e = document.querySelector(s); return e ? getComputedStyle(e).display : null; };
  o.sideDisplay = vis('.side'); o.topnavDisplay = vis('.topnav');
  return o;
}
"""


def shoot() -> None:
    from PIL import Image
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=EXE, args=["--no-sandbox"])
        for width in (390, 1280):
            page = browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=1).new_page()
            page.goto("file://" + str(HTML_OUT))
            page.wait_for_timeout(300)
            print(f"== viewport {width}:", page.evaluate(JS))
            box = page.query_selector(".stage").bounding_box()
            height = int(box["y"] + box["height"] + 8)
            raw = HERE / f"_raw_{width}.png"
            page.screenshot(path=str(raw), clip={"x": 0, "y": 0, "width": width, "height": height}, full_page=True)
            out = HERE / f"shot_{width}.png"
            colors = int(os.environ.get("UIE_COLORS", "128"))
            Image.open(raw).convert("RGB").quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.Dither.NONE).save(out, optimize=True)
            raw.unlink()
            print(f"screenshot {out.name}: {width}x{height}px, {out.stat().st_size} bytes, palette {colors} colors")
        browser.close()


def main(argv) -> int:
    mode = argv[1] if len(argv) > 1 else "colors"
    if mode == "colors":
        print_colors()
    elif mode == "build":
        text = build_html()
        text = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
        HTML_OUT.write_text(text, encoding="utf-8")
        print(f"wrote {HTML_OUT.relative_to(ROOT)} ({HTML_OUT.stat().st_size} bytes)")
    elif mode == "shoot":
        shoot()
    else:
        print("usage: measure.py [colors|build|shoot]")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
