"""L2 除息/配息行事曆推估(services/dividend_calendar,v19.443;v19.530 錨定引擎後修訂)。

守:頻率判定(月/季/年)、除息基準日推估(錨定假說 + 月底夾擠)、入帳日推估(基準日+間隔)、
confidence 分級、季配空月不列、無配息落排除、容錯(ex_date 退 date / pay 缺)、§1 不硬給。

⚠️ **v19.530 fixture 通則:合成配息日一律先套營業日校正 R**(`roll_to_business_day`)。
理由是資料真實性,不是為了讓測試變綠:**真實基金不會把除息基準日訂在週六或國定假日**
(基金公司照名冊那天必須是營業日)。舊 fixture 直接寫字面日號(14 / 15 / 30 號),
12 筆裡有 5 筆落在週末 —— 那種歷史在現實中不存在,任何錨定假說都重現不了它
(規格 §2 要求「投影後**先套 R 再與歷史比對**」),復現率必然 < 0.80 → 引擎依 §3 誠實棄權。
換句話說舊 fixture 是在拿「不可能的資料」測「推估器」,紅的是 fixture 不是引擎。
"""
from __future__ import annotations

import datetime as _dt

from services.dividend_calendar import (
    build_month_calendar,
    build_summary_text,
    detect_house,
    infer_schedule,
    predict_ex_for_month,
    roll_to_business_day,
)


def _biz(y, m, d):
    """名目日號 → 真實基金會用的**營業日**(週末/國定假日順延,跨月則往前)。

    直接重用 production 的 `roll_to_business_day`:fixture 與引擎看的是同一個假日世界,
    否則測到的會是 `holidays` 套件的內容而不是推估邏輯。
    """
    return roll_to_business_day(_dt.date(y, m, d))


def _monthly_divs(day=14, start=(2025, 8), n=12, amount=0.05, pay_gap=30):
    """產 n 筆每月配息(除息基準日錨在 day 號,落非營業日則校正),含 pay_date = ex + pay_gap。"""
    y, m = start
    out = []
    for _ in range(n):
        ex = _biz(y, m, day)                     # ← v19.530:基準日必為營業日(見檔頭通則)
        pay = ex + _dt.timedelta(days=pay_gap)
        out.append({"ex_date": ex.isoformat(), "pay_date": pay.isoformat(),
                    "amount": amount, "yield_pct": 6.0})
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


# ── infer_schedule ─────────────────────────────────────────
def test_monthly_cadence_and_confidence():
    """月配節奏 + §4 新信心公式(v19.530 前身:`test_monthly_cadence_high_confidence`)。

    **為什麼是 medium 不是 high**(有意識的行為變更,非迴歸):
    近 12 筆視窗涵蓋 2026-02,而 2026-02-14 是週六、緊接農曆年連假(除夕 2/15 ~ 補假 2/20),
    營業日校正要跳到 2/23 —— 位移 9 天遠超 §13.7.1 的 τ=3,引擎判「該月無合理錨定日」,
    這一筆歷史錨定重現不了 → 復現率 s = 11/12 ≈ 0.917。
    §4:high 需 s >= 0.95,medium 需 s >= 0.85 且 k >= 4 且 h <= 3 → 誠實落 medium。
    舊公式吃 `day_std`(連續 7 個整數的母體標準差恆為 2.0,永遠低於舊 <=4 閘門)才會給 high,
    該欄已依 §4 從信心公式**完全移除**(欄位保留僅為相容)。
    """
    s = infer_schedule(_monthly_divs(day=14, n=12))
    assert s["cadence"] == "monthly" and s["ex_day"] == 14
    assert s["confidence"] == "medium" and s["n"] == 12
    assert s["pay_gap_days"] == 30


def test_quarterly_cadence():
    """季配節奏偵測(2/5/8/11 月相位,錨在 15 號)。

    fixture 的 5 個名目日期有 3 個落在週末(2025-02-15 六 / 2025-11-15 六 / 2026-02-15 日),
    真實基金不會這樣訂基準日 → 一律先套營業日校正(見檔頭通則)。

    **為什麼信心是 low 不是 medium**(有意識的行為變更,非迴歸):校正後 2026-02-15 落在
    農曆年連假正中(除夕 2/15 ~ 補假 2/20),要跳到 2/23,位移 8 天 > §13.7.1 的 τ=3 →
    該筆重現不了 → s = 4/5 = 0.80。§4 medium 需 s >= 0.85 → 誠實回 low。
    這是本 fixture 的 Feb 相位撞上台灣農曆年的結構性結果:只有 5 筆歷史時,一筆連假就
    吃掉 20% 復現率;引擎照 §1 不宣稱自己有把握。cadence 判定本身(季配)不受影響。
    """
    divs = [{"ex_date": _biz(2025, m, 15).isoformat()} for m in (2, 5, 8, 11)] + \
           [{"ex_date": _biz(2026, 2, 15).isoformat()}]
    s = infer_schedule(divs)
    assert s["cadence"] == "quarterly"
    assert s["confidence"] == "low"


def test_single_record_is_low_confidence():
    s = infer_schedule([{"ex_date": "2026-01-10"}])
    assert s["cadence"] == "single" and s["confidence"] == "low" and s["n"] == 1


def test_none_when_no_dividends():
    s = infer_schedule([])
    assert s["cadence"] == "none" and s["confidence"] == "none"


def test_ex_date_falls_back_to_date_and_pay_optional():
    """只有 date(cnyes 型)→ 當除息日;無 pay_date → pay_gap None(不硬編)。"""
    divs = [{"date": f"2025-{m:02d}-20", "amount": 0.03} for m in range(1, 8)]
    s = infer_schedule(divs)
    assert s["cadence"] == "monthly" and s["ex_day"] == 20 and s["pay_gap_days"] is None


def test_bad_dates_skipped():
    divs = [{"ex_date": "2026-01-14"}, {"ex_date": "not-a-date"}, {"ex_date": "2026-02-14"}]
    s = infer_schedule(divs)
    assert s["n"] == 2                     # 壞日期被丟,不炸


# ── predict_ex_for_month ───────────────────────────────────
def test_predict_monthly_target_month():
    s = infer_schedule(_monthly_divs(day=14, n=12, pay_gap=30))
    p = predict_ex_for_month(s, 2026, 8)
    assert p["ex_date"] == _dt.date(2026, 8, 14)
    assert p["pay_date_est"] == _dt.date(2026, 8, 14) + _dt.timedelta(days=30)


def test_predict_clamps_to_month_end():
    """除息基準日 30 號 → 2 月只有 28 天 → 夾到 28(不溢位),再校正到營業日。

    2026-02-28 同時是**週六 + 和平紀念日**,2/27 是補假 → 往後順延會跨到 3 月,
    故往前抓最近營業日 2/26(週四)。夾 month-end 與營業日校正兩件事都要成立。

    v19.530:fixture 的 30 號有 3 筆落在非營業日(2025-05-30 端午 / 08-30 六 / 11-30 日),
    已由 `_monthly_divs` 統一校正(見檔頭通則)。校正後歷史全部落在「30 號往前找營業日」上,
    引擎推出 FIXED_DAY(30) + `preceding` 方向 —— 方向是**從歷史推**的(§5),不是硬編。
    """
    from services.dividend_calendar import is_business_day
    s = infer_schedule(_monthly_divs(day=30, start=(2025, 4), n=8))
    p = predict_ex_for_month(s, 2026, 2)   # 2026 非閏年 → 28 天
    assert p["ex_date"].month == 2 and p["ex_date"].day <= 28      # 未溢位到 3 月
    assert is_business_day(p["ex_date"])                           # 落在營業日
    assert p["ex_date"] == _dt.date(2026, 2, 26)


def test_quarterly_that_skipped_a_quarter_is_unpredictable():
    """整季漏配一次的「季配」→ 判 irregular → **誠實棄權**(v19.530 §6)。

    ⚠️ **這是有意識的行為變更,不是迴歸**。前身 `test_predict_quarterly_lands_in_month`
    期望 2026-08 推得出日期;v19.530 起改為 None。

    **為什麼跳一季就該棄權**:名目間隔 [92, 92, 181] 天(營業日校正後 [92, 94, 179])——
    2025-11 到 2026-05 之間整整少配一次(≈ 兩個季度)。近 k 筆 gap 標準差遠超 §6 的
    `0.25 × med_gap`,
    節奏本身**不可重現**:我們無從得知它是「改成半年配了」、「那一季暫停」還是「資料缺一筆」。
    舊引擎會拿 med_gap 硬推 2026-08 並且掛上高信心 —— 那正是本次要修掉的失敗模式
    (§1:可以不知道,不可以錯還說有把握)。§14.2 已為這種棄權補上 reason_code,
    所以基金不會從畫面上靜默消失,user 看得到「為什麼推不出」。

    反向護欄(乾淨季配**不得**被誤判 irregular)在
    `test_dividend_anchor_v19527.py::test_quarterly_grid_is_not_misjudged_irregular`
    與本檔 `test_quarterly_end_of_month_lands_correct_month`。
    """
    divs = [{"ex_date": _biz(*d).isoformat()} for d in
            ((2025, 5, 15), (2025, 8, 15), (2025, 11, 15), (2026, 5, 15))]
    s = infer_schedule(divs)
    assert s["cadence"] == "irregular"                       # 181 天那一跳 → 節奏不可重現
    assert s["anchor"] is None                               # §6 判 irregular 就不找錨
    assert predict_ex_for_month(s, 2026, 8) is None          # 舊引擎會自信地推這一格
    assert predict_ex_for_month(s, 2026, 9) is None


def test_predict_single_returns_none():
    s = infer_schedule([{"ex_date": "2026-01-10"}])
    assert predict_ex_for_month(s, 2026, 8) is None          # 節奏不明 → 不猜(§1)


# ── build_month_calendar ───────────────────────────────────
def test_build_calendar_groups_and_excludes():
    funds = [
        {"code": "TLZF9", "name": "安聯收益成長", "house": "安聯",
         "dividends": _monthly_divs(day=14, n=12)},
        {"code": "ACDD01", "name": "安聯台灣大壩累積", "house": "安聯",
         "dividends": []},                                   # 累積型 → 排除
        {"code": "JFZN3", "name": "摩根多重收益", "house": "摩根",
         "dividends": _monthly_divs(day=7, n=10)},
    ]
    cal = build_month_calendar(funds, 2026, 8)
    assert cal["counts"]["events"] == 2 and cal["counts"]["excluded"] == 1
    assert cal["counts"]["unpredictable"] == 0
    assert set(cal["by_day"].keys()) == {7, 14}
    assert cal["by_day"][14][0]["code"] == "TLZF9"
    assert cal["excluded"][0]["code"] == "ACDD01"
    # 事件依除息日排序:7 號(JFZN3)在 14 號(TLZF9)之前
    assert [e["code"] for e in cal["events"]] == ["JFZN3", "TLZF9"]


def test_build_calendar_quarterly_offmonth_not_listed_not_excluded():
    """**乾淨**季配的空月(相位網格外)→ 不列事件、不算排除、也不算「無法推估」。

    語意三分:`events` = 本月有;`excluded` = 累積型本來就不配;`unpredictable` = 有配息史
    但算不出來。季配的 6 / 7 / 9 月是**業務上合理的不配**,三個桶子都不該進 —— 混進
    unpredictable 會讓 user 每個月看到一堆假警報,混進 excluded 則會讓這檔從月曆整段消失。

    v19.530:原 fixture(2025-05/08/11 + 2026-05)其實**跳掉了一整季**,會被 §6 判 irregular
    而落 unpredictable,測不到本條想守的空月語意;該 fixture 已移往
    `test_build_calendar_skipped_quarter_lands_in_unpredictable_with_reason`。
    此處改用真正乾淨的季配網格(2/5/8/11 月,每季恰好一筆)。
    """
    divs = [{"ex_date": _biz(y, m, 15).isoformat()} for y, m in
            ((2025, 2), (2025, 5), (2025, 8), (2025, 11), (2026, 2), (2026, 5))]
    funds = [{"code": "Q1", "name": "季配基金", "dividends": divs}]
    cal = build_month_calendar(funds, 2026, 9, ref_year=2026, ref_month=5)   # 9 月非網格月
    assert cal["counts"]["events"] == 0 and cal["counts"]["excluded"] == 0
    assert cal["counts"]["unpredictable"] == 0               # 季配空月:不列也不算異常(誠實)
    # 反向:網格上的 8 月推得出來 → 證明上面的 0 是「這個月不配」而不是「整檔壞掉」
    assert build_month_calendar(funds, 2026, 8,
                                ref_year=2026, ref_month=5)["counts"]["events"] == 1


def test_build_calendar_skipped_quarter_lands_in_unpredictable_with_reason():
    """跳過一整季的「季配」→ 落 unpredictable 並帶 `reason` / `reason_code`(§14.2)。

    ⚠️ **有意識的行為變更,不是迴歸**。前身 `test_build_calendar_quarterly_offmonth_
    not_listed_not_excluded` 用這組 fixture 期望 `unpredictable == 0`;v19.530 起改為 1。

    **為什麼跳一季就該棄權**:名目間隔 [92, 92, 181] 天(校正後 [92, 94, 179])—— 中間整整
    漏配一次,節奏不可重現(詳見 `test_quarterly_that_skipped_a_quarter_is_unpredictable`)。
    關鍵是它**不會靜默消失**:§14.2 要求回 None 時必須說得出成因,UI 才能顯示人話,
    user 分得出「這個月真的推不出」與「系統壞了」。這正是舊引擎缺的那一半。
    """
    divs = [{"ex_date": _biz(*d).isoformat()} for d in
            ((2025, 5, 15), (2025, 8, 15), (2025, 11, 15), (2026, 5, 15))]
    funds = [{"code": "Q1", "name": "季配基金", "dividends": divs}]
    cal = build_month_calendar(funds, 2026, 9, ref_year=2026, ref_month=5)
    assert cal["counts"]["events"] == 0 and cal["counts"]["excluded"] == 0
    assert cal["counts"]["unpredictable"] == 1               # 不規則 → 誠實揭露,不靜默吃掉
    _u = cal["unpredictable"][0]
    assert _u["code"] == "Q1"
    assert isinstance(_u.get("reason"), str) and _u["reason"].strip()   # UI 要顯示的人話
    assert _u.get("reason_code") == "anchor_weak"            # §14.2 四類成因之一


# ── 稽核修:H3 陳舊 / M1 月底季配 / M2 跨月邊界 / M3 無法推估 bucket ──────────
def test_stale_monthly_not_predicted_and_bucketed():
    """H3:月配但最近一次除息離目標 >3 個月(疑停配/資料過舊)→ 不硬給日期,落 unpredictable。"""
    s = infer_schedule(_monthly_divs(day=14, start=(2024, 1), n=12))   # 末筆 2024-12
    assert predict_ex_for_month(s, 2026, 8) is None          # 距今 ~20 月 → None(不捏造高信心)
    funds = [{"code": "OLD", "name": "停配月配基金", "dividends": _monthly_divs(day=14, start=(2024, 1), n=12)}]
    cal = build_month_calendar(funds, 2026, 8)
    assert cal["counts"]["events"] == 0 and cal["counts"]["unpredictable"] == 1
    assert "疑停配" in cal["unpredictable"][0]["reason"]


def test_quarterly_end_of_month_lands_correct_month():
    """M1:季配基準日在 30 號,月推進不因「加 91 天」漂到下個月 1 號。

    v19.530 fixture 兩處修正(都是資料真實性,不是遷就實作):
    1. 名目 30 號有數筆落非營業日 → 一律套營業日校正(檔頭通則)。
    2. **歷史從 4 筆補到 8 筆**:1/30 每年都撞農曆年(2025-01-30 是春節當天,校正後只能退到
       1/24,距名目 6 天 > τ=3 → 該筆錨定重現不了)。4 筆裡壞 1 筆 → s = 0.75 < §3 的 0.80
       閘門 → 引擎依 §1 整檔棄權,本條想守的「落在正確月份」根本測不到。真實基金不會只有
       4 筆配息史;補到 8 筆後 s = 7/8 = 0.875 過閘門,一筆連假不再吃掉整檔基金。
    """
    divs = [{"ex_date": _biz(y, m, 30).isoformat()} for y in (2024, 2025)
            for m in (1, 4, 7, 10)]
    s = infer_schedule(divs)
    assert s["cadence"] == "quarterly"
    p = predict_ex_for_month(s, 2026, 1)                     # 下一次應落 1 月(非 5/1 之類)
    assert p is not None and p["ex_date"].month == 1


def test_month_boundary_days_use_last_actual_not_phantom():
    """M2:除息日在 31 與 1 間游移 → 不給幻影中間日(16),用最近實際日 + 低信心。"""
    divs = [{"ex_date": d} for d in
            ("2025-05-31", "2025-07-01", "2025-07-31", "2025-09-01", "2025-09-30", "2025-11-01")]
    s = infer_schedule(divs)
    assert s["confidence"] == "low"                          # 離散大 → 低信心
    assert s["ex_day"] == 1                                  # 最近一次是 11-01 → 用 1,非中位數 16


def test_unpredictable_bucket_for_irregular():
    """M3:有配息史但節奏不規則 → 落 unpredictable(不靜默消失、也非累積型排除)。"""
    divs = [{"ex_date": d} for d in ("2025-01-10", "2025-02-20", "2025-06-05")]   # 亂
    funds = [{"code": "IRR", "name": "不規則配息", "dividends": divs}]
    cal = build_month_calendar(funds, 2026, 8)
    assert cal["counts"]["excluded"] == 0 and cal["counts"]["events"] == 0
    assert cal["counts"]["unpredictable"] == 1


# ── detect_house ───────────────────────────────────────────
def test_detect_house_keywords():
    assert detect_house("聯博多元資產收益組合基金AI配息(美元)") == "聯博"
    assert detect_house("安聯收益成長基金-AMg7") == "安聯"
    assert detect_house("摩根投資基金-多重收益基金A股") == "摩根"
    assert detect_house("施羅德環球基金系列-環球收益成長") == "施羅德"
    assert detect_house("某某不知名基金") == ""             # 判不出 → 空(§1 不亂猜)


# ── build_summary_text(LINE 方式 C）─────────────────────────
def test_summary_text_lists_events_and_excluded():
    funds = [
        {"code": "TLZF9", "name": "安聯收益成長", "dividends": _monthly_divs(day=14, n=12)},
        {"code": "ACDD01", "name": "安聯台灣大壩累積", "dividends": []},
    ]
    # 補上 house(build_month_calendar 不自動偵測 house;caller 組裝時填,此處手動)
    for f in funds:
        f["house"] = detect_house(f["name"])
    cal = build_month_calendar(funds, 2026, 8)
    txt = build_summary_text(cal)
    assert "民國115年8月" in txt
    # user 2026-08-24:逐檔只留投信名,代號不顯示(圖檔/明細表/文字/Flex 同一規則)
    assert "8/14" in txt and "安聯" in txt
    assert "TLZF9" not in txt
    # user 2026-08-24「沒有配息的整段移除」→ 不再提累積型/無配息檔數
    assert "累積型" not in txt and "ACDD01" not in txt
    assert "推估非官方" in txt


def test_summary_text_empty_is_honest():
    """空月文案(§1 誠實)。v19.530 §0:全站目標量統一改口徑為「除息**基準日**」。

    user 2026-08-25 指定:MoneyDJ 三欄語意不同(col[0] 配息基準日 / col[1] 除息日 /
    col[2] 發放日),推估的是 col[0],文案就不能寫「除息日」—— 那是另一個日期。
    """
    cal = build_month_calendar([], 2026, 8)
    assert "無推估除息基準日" in build_summary_text(cal)
