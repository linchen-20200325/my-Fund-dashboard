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
| V7 | 首屏看得到至少一張圖（Primary Visual 在首屏） | 一律 advisory |
| V8 | 首屏 chips／badge 數 ≤ 5 | 一律 advisory |

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
  return {
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


def evaluate(measure: dict, *, strict: bool = False) -> list:
    """把量測值判成檢查結果。`strict`：V4～V6 也算 hard（Batch A 自己控制的 primitives 展示頁用）。"""
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
                      f"首屏高 {vh}px；首屏圖 {len(first_chart)} 張", hard=False))
    out.append(_check("V8", f"首屏 chips／badge ≤ {config.MAX_CHIPS_PER_CARD}", measure["first_screen_chips"] <= config.MAX_CHIPS_PER_CARD,
                      f"首屏 {measure['first_screen_chips']} 枚", hard=False))
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
