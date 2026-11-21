"""獨立重算 #1301 三組候選色（docs/design/ui_v3_market_dual_series_palette_review_2026_11_20.html）的 WCAG 對比、CIE76 ΔE、亮度比。
只用標準庫；不讀 repo、不改任何 token。執行：python3 recompute.py"""
import math

def lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]

def lum(h):
    r, g, b = (lin(x) for x in rgb(h))
    return .2126 * r + .7152 * g + .0722 * b

def contrast(a, b):
    x, y = sorted([lum(a), lum(b)], reverse=True)
    return (x + .05) / (y + .05)

def lab(h):
    r, g, b = (lin(x) for x in rgb(h))
    X = .4124564 * r + .3575761 * g + .1804375 * b
    Y = .2126729 * r + .7151522 * g + .0721750 * b
    Z = .0193339 * r + .1191920 * g + .9503041 * b
    f = lambda t: t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(X / .95047), f(Y), f(Z / 1.08883)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))

def de76(a, b):
    return math.dist(lab(a), lab(b))

CANDIDATES = {"A": ("#0a3f86", "#d06a00"), "B": ("#4b2fa8", "#0a8f80"), "C": ("#1a3f8f", "#c2338e")}
STATES = {"primary": "#1a5fd0", "yellow": "#b7791f", "red": "#c0392b", "grey": "#7f8ca6", "accent": "#5fd3d0"}

if __name__ == "__main__":
    for k, (a, b) in CANDIDATES.items():
        print(k, "對 #ffffff %.2f/%.2f" % (contrast(a, "#ffffff"), contrast(b, "#ffffff")),
              "對 #f5f7fb %.2f/%.2f" % (contrast(a, "#f5f7fb"), contrast(b, "#f5f7fb")),
              "兩線ΔE76 %.1f" % de76(a, b), "亮度比 %.2f" % ((max(lum(a), lum(b)) + .05) / (min(lum(a), lum(b)) + .05)))
        print("  與狀態色ΔE76", {n: "%.1f/%.1f" % (de76(a, s), de76(b, s)) for n, s in STATES.items()})
