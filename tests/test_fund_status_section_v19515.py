"""v19.515:基金狀況總覽 section 附進換股週報(services.switch_notify)。

user 2026-08-23「基金狀況併進現有換股週報」。build_fund_status_section 為 L2 純函式:
assembled rows(4D Grade / 距 HWM % / 吃本金燈號)→ 精簡 LINE 文字;build_notification 選填
fund_status_section 附進訊息(空 → 既有 caller 行為零變化)。
"""
from services.switch_advisor import HOLD, SWITCH
from services.switch_notify import (
    _fmt_hwm,
    _status_line,
    build_fund_status_section,
    build_notification,
)


def _row(code="A", name=None, grade="B+", hwm=-8.0, eat=""):
    return {"code": code, "name": name or code, "4D Grade": grade,
            "距 HWM %": hwm, "吃本金燈號": eat}


# ── _fmt_hwm:數值(強制帶號)/字串(原樣)/None/NaN ─────────────────────────────
def test_fmt_hwm_number_signed():
    assert _fmt_hwm(-8.3) == "距高:-8%"       # 下方=負
    assert _fmt_hwm(0) == "距高:+0%"          # 帶號口徑一致(在高點)
    assert _fmt_hwm(3.0) == "距高:+3%"


def test_fmt_hwm_production_string_shape():
    # 實際管線值:risk.py 已預格式化成 '-8.00%'(帶號 + %)→ 走字串分支原樣呈現(稽核 #1/#6)
    assert _fmt_hwm("-8.00%") == "距高:-8.00%"
    assert _fmt_hwm("+0.00%") == "距高:+0.00%"


def test_fmt_hwm_nan_inf_not_bogus():
    # §1:NaN/inf 不得渲染成「距高:nan%」假數字(稽核 #2)
    assert _fmt_hwm(float("nan")) == ""
    assert _fmt_hwm(float("inf")) == ""
    assert _fmt_hwm(float("-inf")) == ""


def test_fmt_hwm_string_and_none():
    assert _fmt_hwm("N/A") == "距高:N/A"
    assert _fmt_hwm(None) == ""
    assert _fmt_hwm("") == ""


# ── _status_line:欄位齊/缺/全缺 ──────────────────────────────────────────
def test_status_line_full():
    line = _status_line(_row(name="富蘭克林成長", grade="A-", hwm=-12.0, eat="🔴 嚴重吃本金"), "持倉")
    assert "[持倉]" in line and "富蘭克林成長" in line
    assert "4D:A-" in line and "距高:-12%" in line and "🔴 嚴重吃本金" in line


def test_status_line_omits_missing_fields():
    line = _status_line({"code": "X", "name": "X", "4D Grade": None, "距 HWM %": None})
    assert "4D:" not in line and "距高" not in line
    assert "資料不足" in line                    # 全缺 → 誠實標


def test_status_line_eat_only_flags_red_yellow():
    # 🟢/空吃本金不顯示(省字),🔴/🟡 才標
    assert "吃本金" not in _status_line(_row(eat="🟢 未吃本金"))
    assert "🟡" in _status_line(_row(eat="🟡 配息侵蝕"))
    assert "🔴" in _status_line(_row(eat="🔴 嚴重吃本金"))


def test_status_line_name_truncated():
    line = _status_line(_row(name="一二三四五六七八九十一二三四五六", grade=None, hwm=None))
    # 名稱截 14 字
    assert "一二三四五六七八九十一二三四" in line and "十五六" not in line


# ── build_fund_status_section ────────────────────────────────────────────
def test_section_empty_rows_returns_blank():
    assert build_fund_status_section([]) == ""
    assert build_fund_status_section(None) == ""


def test_section_basic_with_count_and_source():
    rows = [_row("A", "基金甲", grade="A"), _row("B", "基金乙", grade="C", eat="🔴 嚴重吃本金")]
    out = build_fund_status_section(rows, source_by_code={"A": "持倉", "B": "觀察"})
    # §1:標題檔數拆持倉/觀察,不讓觀察灌水成持倉數(稽核 #3)
    assert "🩺 基金狀況總覽（2 檔:持倉 1／觀察 1）" in out
    assert "[持倉] 基金甲" in out and "[觀察] 基金乙" in out
    assert "🔴 嚴重吃本金" in out


def test_section_count_no_source_no_breakdown():
    rows = [_row("A", "基金甲"), _row("B", "基金乙")]
    out = build_fund_status_section(rows)              # 無來源 → 不拆
    assert "🩺 基金狀況總覽（2 檔）" in out and "持倉" not in out


def test_section_truncates_max_rows():
    rows = [_row(f"C{i}", f"基金{i}") for i in range(25)]
    out = build_fund_status_section(rows, max_rows=20)
    assert "…另有 5 檔" in out
    assert out.count("•") == 20                  # 只列 20 行


def test_section_all_missing_data_row_honest():
    rows = [{"code": "Z", "name": "無資料檔", "4D Grade": None, "距 HWM %": None, "吃本金燈號": ""}]
    out = build_fund_status_section(rows)
    assert "無資料檔" in out and "資料不足" in out


# ── build_notification 接 fund_status_section(兩分支 + 向後相容)───────────────
def _actionable_result():
    return {"advices": [{"code": "A", "name": "基金甲", "action": SWITCH,
                         "action_zh": "🔁 建議換股", "switch_to": {"code": "B", "name": "基金乙"}}],
            "summary": {"n_holdings": 1, "n_switch": 1}}


def _quiet_result():
    return {"advices": [{"code": "A", "name": "基金甲", "action": HOLD, "action_zh": "✅ 續抱"}],
            "summary": {"n_holdings": 1}}


def test_notification_actionable_includes_status():
    sec = build_fund_status_section([_row("A", "基金甲", grade="A")])
    note = build_notification(_actionable_result(), fund_status_section=sec)
    assert note["should_notify"] is True
    assert "🩺 基金狀況總覽" in note["message"] and "基金甲" in note["message"]


def test_notification_quiet_includes_status():
    sec = build_fund_status_section([_row("A", "基金甲", grade="A")])
    note = build_notification(_quiet_result(), fund_status_section=sec)
    assert note["should_notify"] is False
    assert "🩺 基金狀況總覽" in note["message"]
    assert "本週無需換股" in note["message"]


def test_notification_no_section_backward_compatible():
    # 不傳 fund_status_section → 既有行為零變化(不出現總覽區塊)
    note = build_notification(_actionable_result())
    assert "🩺 基金狀況總覽" not in note["message"]


def test_notification_respects_line_cap_with_huge_section():
    huge = build_fund_status_section([_row(f"C{i}", f"很長的基金名稱{i}") for i in range(20)],
                                     max_rows=20) + ("填充" * 3000)
    note = build_notification(_actionable_result(), fund_status_section=huge)
    assert len(note["message"]) <= 4800          # _LINE_TEXT_MAX 上限守住


def test_notification_caveat_survives_huge_section():
    # §1 稽核 #4 修:超長基金狀況 section 不得把免責/摘要擠掉(section 只截自己,尾端保留)
    huge = "🩺 基金狀況總覽（1 檔）：\n" + ("• 填充填充填充填充填充" * 800)
    note = build_notification(_actionable_result(), fund_status_section=huge)
    assert len(note["message"]) <= 4800
    assert "※ 教學紀律工具" in note["message"]     # 免責永遠保留
    assert "換股 1" in note["message"]              # tail 摘要保留
    assert "🔁 建議換股" in note["message"]         # 主要內容(換股)保留
