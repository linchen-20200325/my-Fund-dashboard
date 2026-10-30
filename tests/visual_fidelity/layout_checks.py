# -*- coding: utf-8 -*-
"""CI fixture screenshot 的基本 layout 檢查（BL-0525 Batch A；純函式 ＋ 一段在瀏覽器裡跑的量測腳本）。

分工：`MEASURE_JS` 在頁面裡量出一份 dict（只量、不判斷）；`evaluate()` 在 Python 端把量測值判成檢查結果（可單元測試，不需要瀏覽器）。

檢查項（VFG 12 項中可自動量測的子集；其餘項——首屏圖文比例、三眼原則、資訊密度的主觀判斷——靠人看 production-like Cloud screenshot）：

| id | 檢查 | 預設性質 |
|---|---|---|
| V1 | 頁面沒有未處理例外（`stException`） | hard |
| V2 | 沒有 HTML 被印成程式碼區塊（`stCode`） | hard |
| V3 | 整頁沒有水平溢出（`html` 與 `stMain` 的 `scrollWidth ≤ clientWidth`） | hard |
| V4 | 圖表沒有放進收合的展開區 | strict 才 hard |
| V5 | 圖表高度不低於下限、寬度不低於內容區寬度的一定比例（外露不是一條線；比例量內容區，不量視窗——desktop 內容區置中、比視窗窄） | strict 才 hard |
| V6 | 每個 chips 群組至多 5 枚 | strict 才 hard |
| V7 | 首屏看得到至少一張圖（Primary Visual 在首屏） | advisory；**🌍 頁（`page="mkt"`）起 hard**（BL-0525 Batch C） |
| V8 | 首屏 chips／badge 數 ≤ 5 | advisory；**🌍 頁起 hard** |
| M1～M6 | 🌍 頁專屬（D1～D7 的可自動量測部分）：視覺順序、Secondary ≤3、無頁級日期、Secondary 不高於 Primary、手機緊湊列、圖表牆 | 只在 `page="mkt"` 時評估，全部 hard |

**hard** 失敗＝測試轉紅（安全網抓到真的壞掉：例外、原始碼外露、橫捲）；**advisory** 失敗＝只寫進報告「契約缺口」，**不轉紅**
（例：今天 🌍 頁的圖排在燈與三張文字卡之後，V7 會 fail —— 那是 `docs/v2/71` X-25，Batch C 的工作，不是這個安全網要擋的）。
`strict=True` 用在 Batch A 新建的 primitives 展示頁（它們完全受本批控制，契約要全部成立）。

⚠️ 這些檢查只證明 **CI fixture** 畫面符合上列量測；**不等於** production-like Cloud screenshot 的 Visual Fidelity 確認
（`config.CI_FIXTURE_LABEL`）。
"""

from __future__ import annotations

import vf_config as config

# 在頁面裡量。回傳可 JSON 序列化的 dict。展開區在 Streamlit 是 <details>；收合＝沒有 open 屬性。
MEASURE_JS = """
() => {
  const vw = window.innerWidth, vh = window.innerHeight;
  const all = (s) => Array.from(document.querySelectorAll(s));
  const collapsed = (el) => {
    for (let a = el.parentElement; a; a = a.parentElement) {
      if (a.tagName === 'DETAILS' && !a.open) return true;
    }
    return false;
  };
  const chartSel = '[data-testid=stVegaLiteChart], [data-testid=stPlotlyChart], [data-testid=stArrowVegaLiteChart], .vega-embed, .js-plotly-plot';
  const raw = all(chartSel);
  const outer = raw.filter((el) => !raw.some((o) => o !== el && o.contains(el)));
  const charts = outer.map((el) => {
    const r = el.getBoundingClientRect();
    return {top: r.top + window.scrollY, height: r.height, width: r.width, collapsed: collapsed(el)};
  });
  const main = document.querySelector('[data-testid=stMain]');
  const block = document.querySelector('[data-testid=stMainBlockContainer], .block-container');
  const mainWidth = block ? block.getBoundingClientRect().width : vw;
  const groups = all('.pc-chips').map((g) => g.querySelectorAll('.pc-chip').length);
  const firstScreenChips = all('.pc-chip, [class$="-badge"], [class*="-badge "]').filter((el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.top < vh;
  }).length;
  const rect = (el) => { const r = el.getBoundingClientRect(); return {top: r.top + window.scrollY, height: r.height, width: r.width}; };
  const one = (sel) => { const el = document.querySelector(sel); return el ? rect(el) : null; };
  // 🌍 頁專屬量測（其他頁這些選擇器都量不到 → null／[]，不影響他們的檢查）。
  const mkt = {
    status_chip: one('.mkt-light--chip'),
    hero: one('.mkt-hero'),
    primary: one('[data-section=primary]'),
    // 量外層框（含「利率與信用」卡內的 radio 列）；找不到外層框才退回卡片本身。
    secondary: all('.mkt-sec-card').map((el) => rect(el.closest('[data-testid=stVerticalBlockBorderWrapper]') || el)),
    evidence: one('[data-block="MKT-1"]'),
    page_date: /資料截至|最新到/.test(document.body.innerText),
  };
  return {
    mkt,
    viewport: {width: vw, height: vh},
    main_width: mainWidth,
    exceptions: all('[data-testid=stException]').length,
    code_blocks: all('[data-testid=stCode]').length,
    doc_overflow: {scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth},
    main_overflow: main ? {scroll: main.scrollWidth, client: main.clientWidth} : null,
    charts: charts,
    chips_groups: groups,
    first_screen_chips: firstScreenChips,
    open_details: all('details[open]').length,
  };
}
"""

HARD_ALWAYS = ("V1", "V2", "V3")


def _check(cid: str, title: str, ok: bool, detail: str, *, hard: bool) -> dict:
    return {"id": cid, "title": title, "status": "pass" if ok else "fail", "hard": hard, "detail": detail}


MKT_MAX_SECONDARY = 3          # 客戶 2026-10-30：1 Primary＋最多 3 Secondary（3 不是 KPI）
MKT_MOBILE_SECONDARY_MAX_PX = 240   # 手機 Secondary 是緊湊列：單張高度上限（安全網下限，不是設計目標）
MOBILE_MAX_WIDTH = 500


def evaluate_mkt(measure: dict) -> list:
    """🌍 頁專屬檢查 M1～M6（`DEC-2026-10-30-01` D1～D7＋額外 UI guardrail；全部 hard）。只量結構與相對位置，不判美醜。"""
    m = measure.get("mkt") or {}
    charts = [c for c in measure["charts"] if not c["collapsed"]]
    out = []
    chip, hero, primary = m.get("status_chip"), m.get("hero"), m.get("primary")
    secondary, evidence = m.get("secondary") or [], m.get("evidence")
    first_chart = charts[0] if charts else None
    chain = [("status chip", chip), ("一句主判讀", hero), ("Primary", primary),
             ("Primary 圖", first_chart), ("Secondary", secondary[0] if secondary else None), ("依據卡", evidence)]
    missing = [name for name, item in chain if item is None]
    tops = [item["top"] for _name, item in chain if item is not None]
    ordered = not missing and all(a < b for a, b in zip(tops, tops[1:]))
    out.append(_check("M1", "視覺順序：status chip → 一句主判讀 → Primary → Secondary → 依據卡", ordered,
                      f"缺少 {missing}" if missing else "上緣 " + " < ".join(f"{n} {t:.0f}" for (n, _), t in zip(chain, tops)),
                      hard=True))
    out.append(_check("M2", f"Secondary 至少 1 個、至多 {MKT_MAX_SECONDARY} 個", 1 <= len(secondary) <= MKT_MAX_SECONDARY,
                      f"Secondary {len(secondary)} 個", hard=True))
    out.append(_check("M3", "沒有頁級日期（日期只在圖卡 chip）", not m.get("page_date"),
                      "頁面文字含「資料截至／最新到」" if m.get("page_date") else "頁面文字不含頁級日期字樣", hard=True))
    tallest = max((c["height"] for c in secondary), default=0)
    out.append(_check("M4", "Secondary 不高於 Primary 圖", bool(first_chart) and tallest <= first_chart["height"],
                      f"最高 Secondary {tallest:.0f}px；Primary 圖 {first_chart['height'] if first_chart else 'n/a'}px", hard=True))
    mobile = measure["viewport"]["width"] <= MOBILE_MAX_WIDTH
    too_tall = [c for c in secondary if c["height"] > MKT_MOBILE_SECONDARY_MAX_PX] if mobile else []
    out.append(_check("M5", f"手機 Secondary 是緊湊列（單張 ≤ {MKT_MOBILE_SECONDARY_MAX_PX}px）", not too_tall,
                      f"{'手機' if mobile else '桌機（不適用）'}；超高 {len(too_tall)} 張", hard=True))
    out.append(_check("M6", "沒有圖表牆：整頁只有 Primary 一張可見圖", len(charts) == 1,
                      f"外露圖表 {len(charts)} 張", hard=True))
    return out


def evaluate(measure: dict, *, strict: bool = False, page: str | None = None) -> list:
    """把量測值判成檢查結果。`strict`：V4～V6 也算 hard（Batch A 自己控制的 primitives 展示頁用）。
    `page="mkt"`（BL-0525 Batch C）：V4～V8 全部 hard，並附加 M1～M6；其他頁維持原判定。"""
    mkt = page == "mkt"
    strict = strict or mkt
    content_w = measure.get("main_width") or measure["viewport"]["width"]
    out = []
    out.append(_check("V1", "沒有未處理例外", measure["exceptions"] == 0, f"stException={measure['exceptions']}", hard=True))
    out.append(_check("V2", "沒有 HTML 被印成程式碼區塊", measure["code_blocks"] == 0, f"stCode={measure['code_blocks']}", hard=True))
    overflow = [("html", measure["doc_overflow"])]
    if measure.get("main_overflow"):
        overflow.append(("stMain", measure["main_overflow"]))
    bad = [name for name, o in overflow if o["scroll"] > o["client"]]
    out.append(_check("V3", "整頁沒有水平溢出", not bad, "；".join(f"{n}: {o['scroll']}/{o['client']}" for n, o in overflow), hard=True))

    charts = measure["charts"]
    collapsed = [c for c in charts if c["collapsed"]]
    out.append(_check("V4", "圖表沒有放進收合的展開區", not collapsed, f"圖表 {len(charts)} 張，收合內 {len(collapsed)} 張", hard=strict))
    small = [c for c in charts if not c["collapsed"]
             and (c["height"] < config.MIN_CHART_HEIGHT_PX or c["width"] < config.MIN_CHART_WIDTH_RATIO * content_w)]
    out.append(_check("V5", "圖表高度與寬度不低於下限", not small,
                      f"下限 高≥{config.MIN_CHART_HEIGHT_PX}px、寬≥{config.MIN_CHART_WIDTH_RATIO:.0%} 內容區（{content_w:.0f}px）；不足 {len(small)} 張", hard=strict))
    biggest = max(measure["chips_groups"], default=0)
    out.append(_check("V6", f"每個 chips 群組至多 {config.MAX_CHIPS_PER_CARD} 枚", biggest <= config.MAX_CHIPS_PER_CARD,
                      f"群組 {len(measure['chips_groups'])} 個，最多 {biggest} 枚", hard=strict))
    vh = measure["viewport"]["height"]
    first_chart = [c for c in charts if not c["collapsed"] and c["top"] < vh]
    out.append(_check("V7", "首屏看得到至少一張圖（Primary Visual）", bool(first_chart),
                      f"首屏高 {vh}px；首屏圖 {len(first_chart)} 張", hard=mkt))
    out.append(_check("V8", f"首屏 chips／badge ≤ {config.MAX_CHIPS_PER_CARD}", measure["first_screen_chips"] <= config.MAX_CHIPS_PER_CARD,
                      f"首屏 {measure['first_screen_chips']} 枚", hard=mkt))
    if mkt:
        out.extend(evaluate_mkt(measure))
    return out


def hard_failures(results: list) -> list:
    return [r for r in results if r["hard"] and r["status"] == "fail"]


def advisory_gaps(results: list) -> list:
    return [r for r in results if not r["hard"] and r["status"] == "fail"]


def render_report(entries: list, *, title: str = "CI fixture screenshot report") -> str:
    """entries：[{"scenario", "viewport", "file", "results", "deterministic"}, ...] → Markdown。第一行永遠是兩層不得混用的標示。"""
    lines = [f"# {title}", "", f"> **{config.CI_FIXTURE_LABEL}**", ">",
             "> 本報告只代表 CI 固定 fixtures 渲染出來的畫面（automated safety net）；production-like 確認見 Cloud capture 的報告。", ""]
    for e in entries:
        hard = hard_failures(e["results"])
        gaps = advisory_gaps(e["results"])
        det = {True: "是", False: "否", None: "未量"}[e.get("deterministic")]
        lines.append(f"## {e['scenario']} / {e['viewport']}　{'FAIL' if hard else 'PASS'}")
        lines.append(f"- 截圖：`{e['file']}`　兩次截圖逐位元組相同：{det}")
        for r in e["results"]:
            tag = "hard" if r["hard"] else "advisory"
            lines.append(f"- {r['id']} {r['status'].upper()}（{tag}）{r['title']}：{r['detail']}")
        if gaps:
            lines.append(f"- 契約缺口（advisory，不轉紅，留給對應 Batch）：{', '.join(g['id'] for g in gaps)}")
        lines.append("")
    return "\n".join(lines)
