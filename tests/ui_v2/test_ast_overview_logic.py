# -*- coding: utf-8 -*-
"""💼 我的資產頁「視覺層級」純邏輯測試（BL-0525 Batch D；fast lane，不需要 streamlit）。

守的客戶裁示（`DEC-2026-10-30-02`）：D-5（四格 summary 一律 Missing、不新增彙總公式）、D-10 C2（一句主判讀只取既有值、各狀態誠實）、
D-12（Secondary 全列、不截斷、不排序）、D-1／D-2／D-11（層 3＝3 容器、層 4＝2 容器、block ID 全覆蓋）。
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2 import presentation as P, sections  # noqa: E402
from ui_v2.alo import logic as alo_logic  # noqa: E402
from ui_v2.asset import overview as OV  # noqa: E402
from ui_v2.hld import logic as hld_logic  # noqa: E402

FORBIDDEN = ("加碼", "減碼", "買進", "賣出", "再平衡", "偏多", "偏空", "目標價", "建議", "應該")


# ───────────────────────── D-5：summary strip ─────────────────────────


def test_summary四格_總資產總損益報酬配息_全是Missing_字樣沿正式contract():
    strip = OV.summary_strip()
    assert [s["label"] for s in strip["slots"]] == ["總資產", "總損益", "報酬", "配息"]
    assert all(s["value"] == P.MISSING_CHIP_TEXT == "◇ 資料未備" for s in strip["slots"])
    assert all(s["tone"] == "灰" for s in strip["slots"])          # 灰、不是中性或綠：missing ≠ 正常
    assert not any(re.search(r"\d+ ?項資料未備", s["value"]) for s in strip["slots"])
    assert not any(re.search(r"\d", s["value"]) for s in strip["slots"])   # 不寫 0、不估值


def test_summary_detail下沉_為什麼來源限制去哪補四組都在():
    names = [name for name, _lines in OV.summary_strip()["detail"]["groups"]]
    assert names == ["為什麼", "來源", "限制", "去哪補"]


def test_summary沒有任何彙總計算_模組不含加總平均的實作():
    src = (_ROOT / "ui_v2" / "asset" / "overview.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith(("#", '"""')))
    for token in ("statistics", "mean(", "numpy", "pandas", "fx_twd_per_usd", "units_shares", "cost_twd", "cost_orig_ccy"):
        assert token not in code, token
    # 只准「數檔數」的 sum(1 for …)；不准把任何金額、比重、報酬加總。
    assert all(call.startswith("sum(1 for") for call in re.findall(r"sum\([^)]{0,12}", code))


# ───────────────────────── D-10 C2：一句主判讀 ─────────────────────────


def _alo0(tone="黃", text="核心 與目標差 6.0 個百分點", leaders=("核心",)):
    return {"_tone": tone, "text": text, "_leaders": tuple(leaders)}


def test_hero_有n有最大差距類別():
    assert OV.hero_sentence((3, 2, 0), _alo0()) == "持有 3 檔基金；目前最大配置差距在 核心。"


def test_hero_同差多類全列_沿ALO0全列規則():
    s = OV.hero_sentence((5, 0, 0), _alo0(leaders=("核心", "衛星")))
    assert s == "持有 5 檔基金；目前最大配置差距在 核心、衛星。"


def test_hero_各類別皆在容許帶內_照ALO0既有字_不編差距():
    s = OV.hero_sentence((2, 0, 0), _alo0(tone="灰", text=alo_logic.TEXT_ALL_IN_BAND, leaders=()))
    assert s == f"持有 2 檔基金；{alo_logic.TEXT_ALL_IN_BAND}。"
    assert "差距在" not in s


@pytest.mark.parametrize("text", [alo_logic.TEXT_NO_HOLDING, alo_logic.TEXT_NO_TARGET, alo_logic.TEXT_NO_TOLERANCE,
                                  "⛔ 取數失敗", "尚未選定比重基準"])
def test_hero_配置差距讀不到_照實無法判定_不推成正常(text):
    s = OV.hero_sentence((3, 0, 0), _alo0(tone="灰", text=text, leaders=()))
    assert s == "持有 3 檔基金；配置差距無法判定。"
    assert alo_logic.TEXT_ALL_IN_BAND not in s


def test_hero_檔數讀不到_照實無法判定_不寫0():
    s = OV.hero_sentence(None, _alo0())
    assert s == "持有檔數無法判定；目前最大配置差距在 核心。"
    assert "0 檔" not in s


def test_hero_兩側都沒有_兩句都無法判定():
    assert OV.hero_sentence(None, None) == "持有檔數無法判定；配置差距無法判定。"


def test_hero_任何狀態都不出現方向或建議字樣():
    cases = [((3, 1, 0), _alo0()), (None, None), ((1, 0, 0), _alo0(tone="灰", text=alo_logic.TEXT_ALL_IN_BAND, leaders=()))]
    for counts, alo0 in cases:
        s = OV.hero_sentence(counts, alo0)
        assert not any(w in s for w in FORBIDDEN), s


def test_hero_n只取sections既有計數_不另算():
    model = {"blocks": [
        {"code": "HLD-0", "_tone": "黃", "text": "有 1 檔超出", "_deviation_count": 1},
        {"code": "HLD-1", "_unevaluated_count": 0},
        {"code": "HLD-2", "fund_groups": [{"_fund_code": "A"}, {"_fund_code": "A"}, {"_fund_code": "B"}]},
    ]}
    assert sections.hld_count_values(model) == (2, 1, 0)          # 同一檔兩張保單只數一檔（既有規則）
    assert sections.hld_counts(model) == sections.HLD_COUNTS_TEXT.format(
        n=2, attention=sections.SYMBOL_ATTENTION, m=1, undecidable=sections.SYMBOL_UNDECIDABLE, j=0)
    red = {"blocks": [{**model["blocks"][0], "_tone": "紅"}, *model["blocks"][1:]]}
    assert sections.hld_count_values(red) is None and sections.hld_counts(red) is None


# ───────────────────────── D-12：Secondary 全列 ─────────────────────────


def test_share_rows全列不截斷_列序不動_缺基準值列不畫條():
    rows = [{"fund_text": f"基金{i:02d}", "bucket_text": "核心", "_in_total": 0.01, "in_total_text": "1.0%"} for i in range(60)]
    rows[7] = {**rows[7], "_in_total": None, "in_total_text": "◇"}
    out = OV.share_rows({"_rows": rows})
    assert len(out) == 60                                          # 禁止 Top N
    assert [r["label"] for r in out] == [r["fund_text"] for r in rows]   # 不重排
    assert out[7]["ratio"] is None and OV.share_excluded_count(out) == 1


def test_return_rows全列_標籤含幣別_非數值格只印原字():
    nodes = [{"label": "區間報酬率", "_has_number": True, "_raw": 3.28, "text": "+3.28%"},
             {"label": "區間報酬率", "_has_number": False, "_raw": None, "text": "⬜ 不適用：尚未設定區間"},
             {"label": "區間報酬率", "_has_number": True, "_raw": -2.15, "text": "-2.15%"}]
    groups = [{"_fund_code": f"F{i}", "_ccy": ccy, "head_text": f"基金{i} · 幣別 {ccy}",
               "main_values": [node, {"label": "期間波動", "_has_number": True, "_raw": 7.0, "text": "7.00%"}]}
              for i, (node, ccy) in enumerate(zip(nodes, ("USD", "TWD", "EUR")))]
    out = OV.return_rows({"fund_groups": groups})
    assert [r["label"] for r in out] == [g["head_text"] for g in groups]
    assert all(r["ccy"] in r["label"] for r in out)               # 標籤含幣別
    assert [r["value"] for r in out] == [3.28, None, -2.15]
    assert out[1]["text"] == "⬜ 不適用：尚未設定區間"
    assert OV.return_scale(out) == 3.28
    assert OV.return_scale([{"value": None}]) == 1.0
    assert not any(k in OV.returns_detail({"answers": "x", "detail_lines": []})["groups"][0][1][0] for k in ("平均", "合計"))


def test_return_chips與share_chips_最多五枚且區間未設照實寫():
    chips = OV.return_chips({"inputs": [{"name": "window_start", "_value": None}, {"name": "window_end", "_value": None}]}, [])
    assert [c["text"] for c in chips][0] == "區間未設" and len(chips) <= P.MAX_CHIPS
    assert "原幣，不合計" in [c["text"] for c in chips]


def test_primary_rows缺值格不補_列序不動():
    rows = [{"bucket_text": "A", "_current_pct": 66.0, "_target_pct": 60.0, "current_text": "66.0%", "target_text": "60.0%",
             "diff_text": "+6.0 pp", "band_text": "外"},
            {"bucket_text": "B", "_current_pct": None, "_target_pct": 30.0, "current_text": "◇ 資料未備：缺新臺幣對美元匯率",
             "target_text": "30.0%", "diff_text": "⬜", "band_text": "⬜"}]
    out = OV.primary_rows({"_rows": rows})
    assert [r["bucket"] for r in out] == ["A", "B"]
    assert out[1]["current_pct"] is None and out[1]["current_text"].startswith("◇ 資料未備")


# ───────────────────────── D-1／D-2／D-11：容器與 block ID ─────────────────────────


def test_層3為3個容器_層4為2個容器():
    assert len(OV.LAYER3_CONTAINERS) == 3 and len(OV.LAYER4_CONTAINERS) == 2          # 合併頁層 3、層 4 按 presentation container 計各 ≤3


def test_grouped容器涵蓋層3層4全部10個block_ID_且各一次():
    from ui_v2.alo import logic as A
    layer = {**{c: v for c, v in A.BLOCK_LAYERS.items()}, **{c: v for c, v in hld_logic.BLOCK_LAYERS.items()}}
    layer.update({"ALO-1": 3})                                       # 正式模式 `sections.RELAYER`：ALO-1 移到層 3
    want = sorted(c for c, v in layer.items() if v in (3, 4))
    assert sorted(OV.ALL_GROUPED_CODES) == want
    assert len(set(OV.ALL_GROUPED_CODES)) == len(OV.ALL_GROUPED_CODES) == 10
    assert sections.RELAYER["alo"] == {"ALO-1": 3}


def test_容器名依D11_我的條件_持股明細_配置明細_不用證據一詞():
    names = [n for n, _ in OV.LAYER3_CONTAINERS + OV.LAYER4_CONTAINERS if n]
    assert names == ["我的條件", "持股明細", "配置明細"]
    assert not any("證據" in s for s in OV.page_strings((1, 0, 0), _alo0()))


def test_container_title只用既有塊標題():
    titles = {"HLD-4": "檢視區間與門檻輸入", "ALO-1": "目標輸入卡", "ALO-4": "分組定義"}
    assert OV.container_title("我的條件", ("HLD-4", "ALO-1", "ALO-4"), titles) == "我的條件　—　檢視區間與門檻輸入、目標輸入卡、分組定義"


def test_尚未取得群組_九項全部Missing_摘要列點名():
    group = OV.missing_group()
    assert len(group["items"]) == 9 and all(i["chip"]["text"] == P.MISSING_CHIP_TEXT for i in group["items"])
    assert group["title"].startswith("▸ 尚未取得")
    assert all(item["name"] in group["title"] for item in group["items"])


def test_固定字串不含不寫n項資料未備_也不含方向性字樣():
    for s in OV.page_strings((3, 1, 0), _alo0()):
        assert not re.search(r"\d+ ?項資料未備", s), s
        assert not any(w in s for w in FORBIDDEN), s


def test_pure模組不import_streamlit():
    for name in ("overview.py", "theme.py"):
        src = (_ROOT / "ui_v2" / "asset" / name).read_text(encoding="utf-8")
        assert "import streamlit" not in src, name


def test_footer_只去重複與指向本頁自己的半句_不新增句子():
    from ui_v2 import plain
    out = OV.footer_text([[plain.PLAIN_FOOTERS["alo"]], [plain.PLAIN_FOOTERS["hld"]]])
    assert "單檔績效請到我的持股" not in out
    assert "不產生再平衡動作" in out and "不提供調整方向" in out and "挑標的請到找基金" in out
    assert OV.footer_text([["同一句。"], ["同一句。"]]) == "同一句。"
    assert OV.footer_text([[]]) == ""


def test_selector的widget_key與設定頁picker同值_且動作白名單沒被改():
    """頁頂 selector 重用設定頁既有 picker（`DEC-2026-10-30-02` D-8；不碰 OAuth）：下拉 key 與 `ui_v2/set/source.py` 同值，
    `set/source.py` 的 picker 動作白名單與讀模型不在本批改動範圍。"""
    page = (_ROOT / "ui_v2" / "asset" / "page.py").read_text(encoding="utf-8")
    source = (_ROOT / "ui_v2" / "set" / "source.py").read_text(encoding="utf-8")
    key = re.search(r'^_KEY_PICKER_WIDGET = "([^"]+)"', source, re.M).group(1)
    assert f'PICKER_WIDGET_KEY = "{key}"' in page
    assert '_PICKER_ACTIONS = ("select", "use", "relist")' in source
    assert "picker_live[\"act\"](\"select\"" in page or "picker_live['act']('select'" in page
