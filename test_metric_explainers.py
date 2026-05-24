"""test_metric_explainers — v18.192 教學化 expander 文案（純函式）

只測內容層 `explainer_markdown` / `METRIC_EXPLAINERS`（不涉 streamlit）；
`render_metric_explainer` 走 st.expander，由 app smoke / AppTest 覆蓋。
"""
from __future__ import annotations

from ui.helpers.metric_explainers import METRIC_EXPLAINERS, explainer_markdown


def test_explainer_markdown_known_keys():
    md = explainer_markdown(["sharpe", "beta"])
    assert "夏普" in md and "Beta" in md
    assert md.count("**") >= 4          # 兩個標題各一組 **bold**


def test_explainer_markdown_skips_unknown_keys():
    md = explainer_markdown(["nope", "sharpe"])
    assert "夏普" in md                 # 已知的留
    assert "nope" not in md             # 未知的略過
    assert explainer_markdown(["nope_only"]) == ""


def test_explainer_markdown_empty_input():
    assert explainer_markdown([]) == ""
    assert explainer_markdown(None) == ""


def test_all_explainers_have_title_and_body():
    assert METRIC_EXPLAINERS                       # 非空
    for _k, _v in METRIC_EXPLAINERS.items():
        assert _v.get("title"), f"{_k} 缺 title"
        assert _v.get("body"), f"{_k} 缺 body"


def test_spec_named_metrics_present():
    """spec 點名的 Sharpe / MDD / Beta 都要有文案。"""
    for _k in ("sharpe", "mdd", "beta", "sigma", "core_satellite"):
        assert _k in METRIC_EXPLAINERS
