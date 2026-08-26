"""services/dividend_calendar.py — 基金除息基準日/配息行事曆推估(v19.534)。L2 純函式,零 IO。

用途:吃每檔基金的**配息歷史**,推估「本月**除息基準日** + 配息入帳日」,產生月曆結構供 L3 渲染。
資料由 L1 抓好傳入(reuse `repositories.fund` 的 dividends);本層不碰網路、不 import streamlit。

⚠️ **推估目標量 = 除息基準日**(v19.530 §0;§4.1 語意陷阱):MoneyDJ 配息表三欄語意不同 ——
`col[0] 配息基準日 → date`(**本層目標**,基金公司照名冊那天,節奏最穩)、`col[1] 除息日 → ex_date`
(基準日 +1~2 個營業日,多一層作業抖動)、`col[2] 發放日 → pay_date`。v19.529 以前錨在除息日,
5 檔真實 MoneyDJ 配息表 walk-forward 命中率僅 52%。

推估方法(誠實:是**推估**,非官方公告;輸出帶 confidence + provenance):
  1. 判頻率  : **近 12 筆**相鄰間隔中位數 → 月配(≈30)/季配(≈90)/半年(≈182)/年配(≈365)/不規則;
               gap 標準差 > 0.25×med_gap、相位一致率 < 0.8、或**網格內**(§13.5)「出現次數 != 1」
               的月份佔比 > 0.15 → irregular(漂移 / 一月兩配 / 該配沒配)。
  2. 找錨    : **五個**假說擇一(MONTH_END / MONTH_END_OFFSET / FIXED_DAY /
               NTH_WEEKDAY_FROM_END / NTH_WEEKDAY),以「**能重現自身歷史的比例** s」選模;
               s < 0.80 或筆數 < 3 → **不預測**(§1)。
  3. 校正方向: 落非營業日時往前或往後,方向**從歷史推**(ρ ≥ 0.8);方向混雜 → 保守回退且壓 low,
               歷史零偏移 → 預設 following 但**不**罰信心(§13.3)。任一方向位移 > 3 日 → 不預測。
  4. 推入帳日: 基準日 + 歷史「基準→發放」間隔中位數(缺 pay_date → None,不硬編)。
  5. confidence: s + 擬合筆數 k + 預測地平線 h。**`day_std` 已從公式移除**(對星期錨定無資訊)。

§1 Fail-Loud:無配息紀錄(累積型/查無)→ cadence="none" → caller 落「已排除」,不偽造日期;
             錨定假說重現不了歷史 → 回 None 落 unpredictable,**寧可說不知道也不給看似合理的日期**;
             pay_date 缺 → 入帳日 None(標「約」窗或留白,不捏造)。

v19.532 對抗式稽核四修(每條都附實跑數字,見對應常數 / 函式註解):
  1. `_CONF_MIN_RECORDS_FOR_TRUST` —— k < 8 一律 low。純雜訊歷史各跑 400 次,改前 k=5 有
     11 筆 medium、k=7 有 2 筆 high + 22 筆 medium(105 組候選參數擬 3~7 個點的必然結果),
     改後 k ≤ 7 的 medium/high **全部歸零**,仍照給日期(§1:誠實壓低 > 全部隱藏)。
  2. `build_month_calendar` 逐檔轉載 §8 的 5 個 provenance key + 月曆頂層 `holiday_calendar`,
     L3 據此在頁尾 / 文字 / Flex 揭露假日表降級(缺假日表時覆蓋 93.7% → 61.9%、
     命中 89.8% → 84.6%,原本畫面一字不改)。
  3. `_apply_roll` 兩個方向都評估(主方向優先、反向為回退),不再「主方向超過 τ 就直接放棄」——
     掃 2025–2028 × 全假說 × 3 convention,補回 117 組原本無聲消失的 (假說, 月)。
  4. `_stale_state` / `predict_ex_for_month` / `build_month_calendar` 收 `ref_day`,cron(每月 1 號)
     不再被當成月中 15 號 → 少算 14 天陳舊度而誤殺月配基金。

v19.533 §15 顯示層(user 2026-08-26 拍板)—— **只改「顯示什麼」,沒改「算什麼」**:
  §15.1 `estimate_error_band(dividends)`:逐檔用**自己的**歷史 walk-forward,取 `|推估-實際|`
        的 80% 分位當誤差帶 E,證據不足回 None。畫面上的「高/中/低」三級標籤由它取代;
        引擎的 `confidence` **原封不動**(仍是 §3 閘門與 §13.6 硬門檻的依據,只是不再直接顯示)。
        ⚠️ 禁止用全站合併分布回填單一基金 —— 那是讓沒證據的基金借用別檔的準確度(§1 捏造)。
  §15.3 `build_month_calendar` 的 `unpredictable` 條目增列 `house` / `last_ex`,reason 文案
        改人話 + 帶具體數字(見 `_reason_text`);L3 據此保留該檔的圖例顏色並顯示
        **上一次的實際基準日**(事實),而**不是**把它當成本月預估(那是猜)。
  §15.4 全部推不出 → `is_all_unpredictable` 為真 → 純文字摘要 / Flex 卡片整組換文案
        (首行先講「是推不出,不是沒配息」、altText 移除「0 檔」)。
  §12 相容:既有 key 一個都沒少,`error_band` / `house` / `last_ex` 皆為**新增**。

v19.534 §15 顯示層複驗回修(總管 2026-08-26 實測 + 實看 v533 三張圖後裁示)——
**引擎推估邏輯一行沒動**(三口徑逐位元相同),改的全是「顯示什麼 / 顯示成什麼樣」:
  1. `_ERR_BAND_QUANTILE` 0.80 → **0.90**:80 分位讓摩根顯示「±0 天」卻只罩住 10/12
     (12 次裡差過 2 天與 4 天),畫面上的 ±0 讀起來是「保證那天」。實測罩住率 91% → 93%。
     配套 `ERR_BAND_FOOTNOTE`:具體數字必須說明它是什麼、憑什麼(§1)。
  2. 裁示 2:LINE 逐檔的「（信心低）」與月曆 chip 的「?」**移除**(`_CONF_ZH` 對照表整個刪除)。
     兩者在畫面上沒有一處解釋,且會與誤差帶互相矛盾(同一檔可能同時 low + ±0 天)。
     **一個訊號、一個地方** —— 誠實訊號是誤差帶。引擎 `confidence` 原封不動。
  4. 裁示 4:`ALL_UNPRED_LINE_HEAD` 首行的「本月」→ **實際目標月**(cron 每月 1 號推下個月,
     「本月」在推播情境是錯的)。月份字串全走 `month_label()` 這一份 SSOT。
  8. 追加 8:`fmt_last_ex()` —— 上次日期離目標月超過半年 → 帶年份(2027-02 的圖上寫
     「上次 8/11」會被讀成上個月;`stale` 那類正是「很久以前」,不帶年份會低估陳舊度)。
  9. 追加 9:reason 文案與「上次日期」拆開,由 `reason_display(has_date_column=...)`
     依版面決定要不要補尾巴 —— 三欄表已有獨立日期欄時不重複講第二次。
"""
from __future__ import annotations

import calendar as _calendar
import datetime as _dt
import math as _math
import statistics as _stats
from collections import Counter as _Counter
from typing import Any

# 頻率判定的間隔(天)容忍窗
_CADENCE_BANDS = [
    ("monthly", 20, 40),
    ("quarterly", 75, 105),
    ("semiannual", 160, 200),
    ("annual", 320, 400),
]
_RECENT_N = 12          # 推估視窗:錨定假說 / gap / 相位**同一視窗**只看近 12 筆(§6 稽核 A7)
# cadence → 一個週期幾個日曆月(逐月推進,不加固定 91 天以免月底漂移錯月)
_CADENCE_MONTHS = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}

# ── 錨定假說推估核心(v19.530 規格 §1~§8)——— 門檻全為 module 具名常數(§3.3 禁 inline)──
ANCHOR_MONTH_END = "MONTH_END"                        # 每月最後營業日(0 參數)
ANCHOR_MONTH_END_OFFSET = "MONTH_END_OFFSET"          # 每月倒數第 (n+1) 個營業日(1 參數,§13.2)
ANCHOR_FIXED_DAY = "FIXED_DAY"                        # 固定日號 D(1 參數)
ANCHOR_NTH_WEEKDAY = "NTH_WEEKDAY"                    # 每月第 j 個星期 w(2 參數)
ANCHOR_NTH_WEEKDAY_FROM_END = "NTH_WEEKDAY_FROM_END"  # 每月倒數第 j 個星期 w(2 參數)

ROLL_FOLLOWING = "following"                      # 非營業日 → 往後找
ROLL_PRECEDING = "preceding"                      # 非營業日 → 往前找
ROLL_MODIFIED_FOLLOWING = "modified_following"    # 往後,跨月則往前(方向未定時的保守回退)

# §3 平手時取「參數較少」者(少參數 = 少過擬合)
_ANCHOR_PARAM_COUNT = {ANCHOR_MONTH_END: 0, ANCHOR_MONTH_END_OFFSET: 1, ANCHOR_FIXED_DAY: 1,
                       ANCHOR_NTH_WEEKDAY_FROM_END: 2, ANCHOR_NTH_WEEKDAY: 2}
# 分數 + 參數數皆相同時的決選序(§13.2 定案,deterministic,避免同分時輸出隨字典序漂移):
# MONTH_END_OFFSET 排在 FIXED_DAY 前 —— 月底**相對**錨跨不同月長(28/30/31)更穩;
# NTH_WEEKDAY_FROM_END 排在 NTH_WEEKDAY 前 —— 兩者僅在「該月有 5 個星期 w」時分歧,基金慣例錨月底側。
_ANCHOR_ORDER = [ANCHOR_MONTH_END, ANCHOR_MONTH_END_OFFSET, ANCHOR_FIXED_DAY,
                 ANCHOR_NTH_WEEKDAY_FROM_END, ANCHOR_NTH_WEEKDAY]
_MONTH_END_OFFSET_MAX = 3        # §13.2 n ∈ {1,2,3}(n=0 仍歸 MONTH_END,保留 0 參數優先權)

_ANCHOR_ACCEPT_MIN = 0.80        # §3 復現率 s⁽¹⁾ 未達 → 回 None(§1 不硬給)
# ⚠️ **v19.532 實測結論:這條門檻維持「不隨 k 變」的 0.80,k 相依版本已評估後退回。**
# 稽核提案是改成 `max(0.80, 1 - 1/k)`(= 不准錯超過 1 筆),用意是擋 k ≤ 7 的窮舉過擬合。
# 三組實跑之後不採用,理由逐條(數字都可用 §11 那 5 檔真實資料 + 純雜訊實驗複現):
#   1) **在它自己點名的 k ≤ 9 區間是數學上的 no-op**:s 只能取 p/k,`s ≥ 0.80` 已經等價於
#      「錯 ≤ floor(0.2k)」= k=3,4 錯 0 筆、k=5..9 錯 1 筆;`max(0.80, 1-1/k)` 在 k ≤ 9 給出
#      **完全相同**的允許筆數。純雜訊實驗 k∈{3,5,7} 改前改後逐格相同 —— 一格都沒擋到。
#   2) **在 k ≥ 10 會砍掉真實覆蓋**:5 檔實測命中率 89.8% → 86.5%、覆蓋率 93.7% → **58.7%**
#      (22 筆消失,其中 **21 筆原本推對**)。摩根 / 聯博 / 施羅德的 k=12 穩態段全在 10/12=0.833,
#      它們 walk-forward 100% 命中卻會被判成「重現不了自己的歷史」。真實基金在 12 筆視窗內
#      帶 1~2 個作業離群值是常態,不是過擬合。
#   3) **任何「錯 ≤ N 筆」的絕對上限都會懲罰長歷史**:試過 N=2(k ≤ 12 零代價)仍會讓
#      `detect_anchor(30 筆, s=0.90)` 回 None,而**同一檔基金**只餵最近 12 筆(s=1.00)卻給得出
#      日期 —— 歷史越長越不敢預測,方向反了;而且「回 None」= 該檔從月曆上**消失**,
#      與本次採用的原則(§1:仍顯示但誠實壓 low > 全部隱藏)直接牴觸。
# 真正把小 k 過擬合擋下來的是下面的 `_CONF_MIN_RECORDS_FOR_TRUST`(實測見該常數註解)。
_ANCHOR_TIE_DELTA = 0.10         # §3 前二名差距 < 此值 → 取參數少者,且信心上限壓 medium
_ANCHOR_MIN_RECORDS = 3          # §3 k < 3 → None
# v19.532 阻斷 1:k 少於此值 → 信心**強制 low**(不論 s 多高)。
# 不改 `_ANCHOR_MIN_RECORDS`(3)—— 那會讓新基金整檔從月曆上消失;§1 的誠實是「仍顯示、
# 但明講沒把握」,不是「全部隱藏」。
_CONF_MIN_RECORDS_FOR_TRUST = 8
_ROLL_DIR_MIN_RATIO = 0.80       # §5 ρ₊ / ρ₋ 認定「單向校正」的門檻
_KEEP_MONTH_MAX_SHIFT_DAYS = 3   # §5 τ:跨月回退的距離上限(日曆日),超過 → 該月無合理錨定日
# ── §4 信心門檻(v19.531 **用實測校準**,不是憑感覺挑的整數)──────────────────
# 校準口徑:user 5 檔真實 MoneyDJ 配息表 walk-forward(起手歷史 8 筆,同
# `tests/test_dividend_anchor_v19527.py::_MIN_HIST`),54 筆有給日期,對 (high, med)
# 兩個門檻做網格搜尋;通過條件 = ①三桶命中率單調(high > medium > low)②三桶皆非空
# ③§13.6 硬門檻「錯 且 high 且誤差 > 1 天」= 0 筆。
#
# 改動前(0.95 / 0.85)實測:high 9 筆 89% / medium 27 筆 85% / **low 18 筆 94%**
#   → **信心標籤是反指標**(低比中準)。根因:s 只能取 p/q(q ≤ _RECENT_N=12)這些離散值,
#   0.85 這條線切在 10/12=0.833 與 7/8=0.875 之間,把「12 筆對 10 筆」這種**穩定但視窗內
#   帶 1~2 個舊離群值**的基金全掃進 low(摩根 / 施羅德 / 聯博 的 k=12 穩態段全在此),
#   而它們實測 100% 命中。同一批資料裡真正該罰的是 8/9=0.889、10/11=0.909 那兩格(各 50%)。
# 校準後(0.95 / 0.83):high 15 筆 93.3% / medium 36 筆 88.9% / low 3 筆 66.7% → 單調 ✅
#
# 網格通過區間(min_hist=8):med ∈ [0.81, 0.83]、high ∈ [0.92, 1.00]。
#   - `_CONF_MED_MIN_SCORE` 取 **0.83**:區間內取樣本最多者(low 桶 3 筆 vs 0.81 的 2 筆);
#     且 q ≤ 12 時**沒有任何**可達的 s 落在 (9/11, 10/12) 開區間內 → 0.82 與 0.83 行為完全等價,
#     取 0.83 是因為它可讀成「**六次最多錯一次**(5/6)」。低於 9/11=0.818 才判 low,
#     語意 = 「剛擦過 `_ANCHOR_ACCEPT_MIN`=0.80 的邊緣帶」。
#   - `_CONF_HIGH_MIN_SCORE` **維持 0.95 不動**(§-1 沒壞不要動):它已落在通過區間內,
#     且區間內每個值在本資料上**行為完全相同**(可達 s 在 11/12=0.917 與 1.0 之間無值)。
#     下界不可再放寬 —— 0.91 會讓 11/12 進 high,而 11/12 那格含一筆誤差 4 天的錯,
#     §13.6 硬門檻立刻從 0 變 1;上界不取 1.0 是因為那等於要求字面完美,浮點上太脆。
# ⚠️ **v19.532 同口徑重測**(加了 `_CONF_MIN_RECORDS_FOR_TRUST`,k<8 一律 low 之後):
#   high 14/15 = 93.3%｜medium 32/36 = 88.9%｜low 7/8 = 87.5% → **仍單調**,本組門檻不需再校準。
#   low 桶命中率上升是預期的(k=7 那批原本掛 medium/high、實測多半正確的筆被移進來);
#   low 的語意是「**不擔保**」而不是「大概會錯」,故不構成 v19.531 修掉的那種反指標。
_CONF_HIGH_MIN_SCORE = 0.95      # §4 high 三條件(校準後維持;通過區間 [0.92, 1.00])
_CONF_HIGH_MIN_N = 6
_CONF_HIGH_MAX_HORIZON = 1
_CONF_MED_MIN_SCORE = 0.83       # §4 medium 三條件(v19.531 校準:0.85 → 0.83)
_CONF_MED_MIN_N = 4
_CONF_MED_MAX_HORIZON = 3
_PHASE_MIN_RATIO = 0.80          # §6 相位眾數一致率下限(未達 → 網格不成立 → 判 irregular)
_GAP_DRIFT_MAX_RATIO = 0.25      # §6 近 k 筆 gap 標準差 / med_gap 上限(漂移偵測)
_DUP_MONTH_MAX_RATIO = 0.15      # §6/§13.5 網格內「出現次數 != 1」月份的佔比上限(雙配息/漏配)
_DAYS_PER_MONTH = 30.44          # §7 平均日曆月長(365.25 / 12)
_STALE_MAX_PERIODS = 3           # §7/§13.1 疑停配門檻倍數:上限 = min(3*step, 15) **個月**
_STALE_ABS_MAX_MONTHS = 15       # §7 絕對上限(年配基金不得靜默 36 個月仍給日期)
_STALE_LOW_PERIODS = 2           # 距 ref >= 2 個週期 → 信心壓 low
# §7 的 ref_date:caller 只給 (ref_year, ref_month) 沒給「日」,取**月中**當該月的代表時點 ——
# 取月初/月底會系統性低估/高估陳舊度 15 天(半個月配週期);月中是無偏的中點估計。
_REF_DAY_OF_MONTH = 15

# ── §15.1 誤差帶:畫面上的「高/中/低」三級標籤廢止,改「±N 天」──────────────────
# user 2026-08-26 拍板:要的是「哪天該去看帳戶」,「中信心」回答不了這個問題。
# ⚠️ **引擎內部的 `confidence` 一個字都沒動** —— 它仍是 §3 閘門與 §13.6 硬門檻的依據,
#    只是不再直接顯示給 user。改的是「顯示什麼」,不是「算什麼」。
# ⚠️ **禁止**用全站/全檔合併的誤差分布回填單一基金(§1 反捏造):那會讓一檔完全沒有證據的
#    基金借用別檔的準確度,畫面上長得跟真的有把握一樣。證據不足就回 None,顯示「僅供參考」。
# v19.534 分位數由 0.80 上調 **0.90**(總管 2026-08-26 實測 user 5 檔後裁示)。
# 為什麼:80 分位讓摩根顯示「±0 天」,但它 12 次 walk-forward 裡有 2 次分別差了 2 天與 4 天,
# 實際只罩住 10/12;施羅德曾差 14 天卻顯示「±1 週」。畫面上的「±0 天」讀起來是「保證那天」,
# 那是 §1 意義下「讓沒把握的看起來有把握」。實測合計罩住率:80 分位 91% → 90 分位 93%。
#   基金        誤差序列                        80分位/罩住      90分位/罩住
#   摩根        [0,2,0,0,0,0,0,0,0,0,0,4]         0  10/12          2  11/12
#   聯博        [0,0,0,1,0,0,0,0,0,0,0,0]         0  11/12          0  11/12
#   瀚亞        [0]*12                             0  12/12          0  12/12
#   安聯        [0,0,0,0,0,0,0,0,1,0,0,0]         0  11/12          0  11/12
#   施羅德      [0,7,14,0,0,0]                     7   5/6         11   5/6
# 改後畫面:摩根「±2 天」、施羅德「僅供參考」(帶寬 11 > 7)、其餘三檔維持「±0 天」。
_ERR_BAND_QUANTILE = 0.90        # |推估 - 實際| 的 90% 分位(§15.1;向上取整後為該檔誤差帶 E)
_ERR_BAND_MIN_SAMPLES = 3        # walk-forward 實際「有給出日期」的樣本數下限,不足 → None
# 頁尾說明(SSOT):具體數字比模糊標籤更容易被過度相信,必須說明它是什麼、憑什麼。
# 「約九成」對應 `_ERR_BAND_QUANTILE`(0.90)—— 兩者要一起改,不可只改一邊(§3.3)。
ERR_BAND_FOOTNOTE = "※ 誤差 = 用該檔自己的配息史回測，約九成情況落在此範圍內。"
# 起手歷史筆數沿用 `_CONF_MIN_RECORDS_FOR_TRUST`(8):同一條「這檔基金的歷史夠不夠撐一個
# 有數字的宣稱」門檻,不另立第二個閾值(§3.3 SSOT,避免兩處各自漂移)。

_HOLIDAY_CAL_TW = "TW"                   # §8 provenance:真有國定假日表
_HOLIDAY_CAL_WEEKEND = "weekend_only"    # §8 provenance:holidays 套件缺 → 只跳週末
# §8 的五個 provenance key(SSOT:`predict_ex_for_month` 產出、`build_month_calendar` 逐檔轉載)
_PROVENANCE_KEYS = ("anchor_type", "anchor_score", "roll_convention",
                    "holiday_calendar", "horizon_months")
# 假日表降級警語:text / Flex / HTML 頁尾三處共用同一句(SSOT,避免各寫各的而漂移)。
# §1:降級**必須看得見** —— 實測無假日表時覆蓋 93.7% → 61.9%、命中 89.8% → 84.6%
# (跌破 §13.6 的 85% 門檻),畫面卻一字不改 = 讓失敗看起來像成功。
_HOLIDAY_CAL_WARN = "⚠️ 本次未載入國定假日表，日期僅跳過週末、未扣國定假日，準確度下降"


def _holiday_calendar_state() -> str:
    """§8 provenance:目前實際用的假日曆 → "TW" / "weekend_only"。"""
    return _HOLIDAY_CAL_TW if has_holiday_calendar() else _HOLIDAY_CAL_WEEKEND


def holiday_calendar_note(cal: "dict | None" = None) -> str:
    """月曆(或 None = 問現在)→ 假日表降級警語;**沒降級回空字串**(不加無謂雜訊)。

    L3(HTML 頁尾)、`build_summary_text`、`build_summary_flex` 三處共用這一句(SSOT)。
    `cal` 帶 `holiday_calendar` 就用它(以產生月曆**當下**的狀態為準,不是渲染當下);
    手搭 dict 沒帶這個 key → 退回現況查詢,§1 不因缺欄位就當成「有假日表」。
    """
    _state = (cal or {}).get("holiday_calendar")
    if _state not in (_HOLIDAY_CAL_TW, _HOLIDAY_CAL_WEEKEND):
        _state = _holiday_calendar_state()
    return "" if _state == _HOLIDAY_CAL_TW else _HOLIDAY_CAL_WARN


def _pdate(v: Any) -> "_dt.date | None":
    """'YYYY-MM-DD' / 'YYYY/MM/DD' → date;壞值 → None(§1 不猜)。"""
    s = str(v or "").strip()[:10].replace("/", "-")
    try:
        y, m, d = (int(x) for x in s.split("-"))
        return _dt.date(y, m, d)
    except (ValueError, TypeError):
        return None


def _pfloat(v: Any) -> "float | None":
    try:
        f = float(v)
        return f if f == f else None      # NaN → None
    except (TypeError, ValueError):
        return None


def _parse_records(dividends: list) -> list:
    """配息紀錄 → [{ex, pay, amount, yield_pct}](升冪、同日去重 keep-last)。

    ⚠️ **`ex` 欄承載的是「除息基準日」**(v19.530 規格 §0 改;§4.1 單位/語意陷阱):
    MoneyDJ 配息表三個日期欄語意不同,推估目標量是**第一欄**——
      ``col[0] 配息基準日 → date``(本層取用;基金公司真正「照名冊」的那一天,節奏最穩)
      ``col[1] 除息日     → ex_date``(v19.529 以前取這欄;它是基準日 +1~2 個營業日,
                                      多一層作業日抖動,錨定假說復現率明顯較差)
      ``col[2] 發放日     → pay_date``
    故取值順序改為 **`date` 優先、退 `ex_date`**。FundClear(三欄同值)/ Cnyes(只有 `date`)
    來源行為不變;只有 MoneyDJ 來源的取值會改變 —— 而那正是本次要修的對象。
    欄名 `ex` 為既有結構相容保留(下游 key 未改),語意以本 docstring 為準。

    容錯:兩欄都解析不出 → 丟該筆(§1 不猜);pay_date 缺 → None。
    """
    out: list = []
    for r in dividends or []:
        if not isinstance(r, dict):
            continue
        ex = _pdate(r.get("date") or r.get("ex_date"))     # §0:基準日優先
        if ex is None:
            continue
        pay = _pdate(r.get("pay_date"))
        out.append({"ex": ex, "pay": pay,
                    "amount": _pfloat(r.get("amount")),
                    "yield_pct": _pfloat(r.get("yield_pct"))})
    dedup: dict = {}
    for r in out:                          # 同基準日 keep-last
        dedup[r["ex"]] = r
    return [dedup[k] for k in sorted(dedup)]


def _cadence_from_gap(med_gap: "float | None") -> str:
    if med_gap is None:
        return "single"
    for name, lo, hi in _CADENCE_BANDS:
        if lo <= med_gap <= hi:
            return name
    return "irregular"


# ── §1 四個錨定假說:投影(未校正的「名目錨定日」)────────────────────────────
def _month_days(year: int, month: int) -> int:
    return _calendar.monthrange(year, month)[1]


def _scan_business(d: "_dt.date", forward: bool) -> "_dt.date | None":
    """從 d 起(不含 d)往前/往後找第一個營業日;掃不到 → None(§1 不硬給)。"""
    _step = _dt.timedelta(days=1 if forward else -1)
    cur = d
    for _ in range(_HOLIDAY_MAX_SCAN):
        cur = cur + _step
        if is_business_day(cur):
            return cur
    return None


def _to_business(d: "_dt.date | None", forward: bool) -> "_dt.date | None":
    """d 已是營業日 → 原值;否則往指定方向找第一個營業日。"""
    if d is None:
        return None
    return d if is_business_day(d) else _scan_business(d, forward)


def _last_business_day_of_month(year: int, month: int) -> "_dt.date | None":
    """L(y,m):該月最後營業日(月底往前找)。"""
    return _to_business(_dt.date(year, month, _month_days(year, month)), forward=False)


def _business_day_from_end(year: int, month: int, n: int) -> "_dt.date | None":
    """該月**倒數第 (n+1) 個營業日**(n=0 → 最後營業日)。該月營業日不足 → None(§13.2)。"""
    _cur = _last_business_day_of_month(year, month)
    for _ in range(max(0, int(n))):
        if _cur is None:
            return None
        _cur = _scan_business(_cur, forward=False)
    return _cur if (_cur is not None and (_cur.year, _cur.month) == (year, month)) else None


def _nth_weekday_of_month(year: int, month: int, w: int, j: int) -> "_dt.date | None":
    """該月第 j 個星期 w(w:0=一…6=日);該月不足 j 個 → None(§1 不外推到別的月)。"""
    _first_wd = _dt.date(year, month, 1).weekday()
    _day = 1 + (w - _first_wd) % 7 + 7 * (j - 1)
    return _dt.date(year, month, _day) if 1 <= _day <= _month_days(year, month) else None


def _nth_weekday_from_end_of_month(year: int, month: int, w: int, j: int) -> "_dt.date | None":
    """該月倒數第 j 個星期 w;該月不足 j 個 → None。"""
    _md = _month_days(year, month)
    _last_wd = _dt.date(year, month, _md).weekday()
    _day = _md - (_last_wd - w) % 7 - 7 * (j - 1)
    return _dt.date(year, month, _day) if 1 <= _day <= _md else None


def _anchor_nominal(a_type: str, params: Any, year: int, month: int) -> "_dt.date | None":
    """假說 + 年月 → **名目**錨定日(§5 的 a_e,未套營業日校正 R)。無合理值 → None。

    MONTH_END / MONTH_END_OFFSET 依定義即落在營業日,名目值本身已是營業日(R 對它是 identity,
    §13.2「不再套 R」自然成立,不需特例分支)。
    """
    if a_type == ANCHOR_MONTH_END:
        return _last_business_day_of_month(year, month)
    if a_type == ANCHOR_MONTH_END_OFFSET:
        try:
            _n = int(params)
        except (TypeError, ValueError):
            return None
        if not 1 <= _n <= _MONTH_END_OFFSET_MAX:
            return None
        return _business_day_from_end(year, month, _n)
    if a_type == ANCHOR_FIXED_DAY:
        try:
            _d = int(params)
        except (TypeError, ValueError):
            return None
        if _d < 1:
            return None
        return _dt.date(year, month, min(_d, _month_days(year, month)))
    if a_type in (ANCHOR_NTH_WEEKDAY, ANCHOR_NTH_WEEKDAY_FROM_END):
        try:
            _w, _j = int(params[0]), int(params[1])
        except (TypeError, ValueError, IndexError):
            return None
        if not (0 <= _w <= 6) or _j < 1:
            return None
        if a_type == ANCHOR_NTH_WEEKDAY:
            return _nth_weekday_of_month(year, month, _w, _j)
        return _nth_weekday_from_end_of_month(year, month, _w, _j)
    return None


# ── §5 營業日校正 R(方向從歷史推,不硬編;跨月回退帶 τ 上限)────────────────
def _apply_roll(nominal: "_dt.date | None", convention: str,
                year: int, month: int) -> "_dt.date | None":
    """名目錨定日 → 校正後日期;**兩個方向都不可行**才回 None(§1 不給錯月/被拉開的值)。

    - 名目日本身就是營業日 → 原值(位移 0,方向不參與)。
    - 否則**兩個方向都算**:各自找第一個營業日,要求 (a) 仍落在目標月、(b) 位移 ≤ τ=3 日曆日。
      兩邊都不合格 → None(§13.7.1「任何方向的校正位移 > τ → 該月無合理錨定日」)。
    - 兩邊都合格 → 取**主方向**(following/modified_following 往後、preceding 往前);
      主方向不合格但反向合格 → 用反向(涵蓋舊的 `keep_month` 跨月回退)。

    ⚠️ **v19.532 修正**(user 可見 bug 3):舊版的反向回退**只在主方向跨出月份時**才觸發 ——
    主方向留在月內但位移 > τ 時直接 return None,從不試反向。實測掃 2025–2028 × 全假說
    × 3 種 convention,**117 組 (假說, convention, 月)**(去掉 convention 維度後 78 組)是
    「舊版回 None,但反方向存在 τ 內的當月營業日」;且**沒有任何一組**原本推得出來的值被改動;
    最貴的一例:`FIXED_DAY(14) / following / 2026-02`(名目 2/14 撞農曆年,往後要跳 9 天)
    → 舊版整月消失,而 **2026-02-13 正是 user 安聯 TLZF9 的真實基準日**、只差 1 天。
    安聯本身逃過一劫純粹因為它的歷史把方向推成 `preceding`;同型但推成 `following` 的基金
    每逢農曆年就會從月曆上整檔消失(§14.2 抱怨的「15 號型基金每逢 2 月固定不見」同源)。

    ⚠️ 主方向優先、**不是**取位移較小者:convention 是 §5 從歷史 ρ ≥ 0.8 推出來的**觀察值**,
    「週六 → 週一(+2)」對 following 型基金是它真實的作業行為;改成「就近取週五(-1)」
    等於用一個沒有證據的規則覆蓋掉有證據的規則 —— user 5 檔真實配息表實測:主方向優先
    命中 89.8% / 覆蓋 93.7% / §13.6 硬門檻 0,改取位移較小者 **命中 84.0%(跌破 85% 門檻)/
    覆蓋 79.4% / 硬門檻 1 筆**(三個口徑同時退步)。
    反向只在主方向**做不到**(跨月 / 超過 τ)時才登場,那時 τ 已保證它離名目日不超過 3 天。
    """
    if nominal is None:
        return None
    if is_business_day(nominal):
        return nominal if (nominal.year, nominal.month) == (year, month) else None
    _primary_forward = convention != ROLL_PRECEDING
    for _fwd in (_primary_forward, not _primary_forward):     # 主方向優先,反向為回退
        _d = _scan_business(nominal, forward=_fwd)
        if _d is None or (_d.year, _d.month) != (year, month):
            continue                                          # 掃不到 / 跨出目標月
        if abs((_d - nominal).days) > _KEEP_MONTH_MAX_SHIFT_DAYS:
            continue                                          # §13.7.1 位移過大 → 換方向再試
        return _d
    return None                                               # 兩個方向皆不可行 → 該月無錨定日


def _infer_roll_convention(dates: list, a_type: str, params: Any) -> tuple:
    """§5 / §13.3 / §13.4:從歷史推校正方向 → (convention, inferred)。

    **§13.4**:ρ 依賴名目錨定日 a_e,而 a_e 是假說的函數 → **每個假說各自估自己的 ρ**,
    再用自己的 R 算自己的 s;`roll_convention` 取勝出假說的那一個(分開估才數學自洽)。

    ρ₊ = |{e: e > a_e}| / |{e: e != a_e}|
      ρ₊ ≥ 0.8            → following
      ρ₋ ≥ 0.8            → preceding
      分母 = 0(**§13.3**)→ following,`inferred=False`,且**不壓信心** ——
                            歷史零偏移代表該假說完美貼合,不是資訊不足;原字面會讓最規律的
                            純星期錨定型基金永遠拿不到 high,與 §4 直接衝突。
      其餘(方向混雜)     → modified following,由呼叫端壓 low(§5:方向未定不宣稱有把握)

    `inferred` = 方向是否**真從歷史推得**(§13.3 純稽核欄位):零偏移與方向混雜兩種
    「用預設值」的情形皆為 False;信心是否壓 low 改看 `roll_convention`,不看本旗標。
    """
    _up = _dn = 0
    for e in dates:
        _a = _anchor_nominal(a_type, params, e.year, e.month)
        if _a is None or _a == e:
            continue
        if e > _a:
            _up += 1
        else:
            _dn += 1
    _tot = _up + _dn
    if _tot == 0:
        return ROLL_FOLLOWING, False       # §13.3 零偏移 → 預設 following,信心不受罰
    if _up / _tot >= _ROLL_DIR_MIN_RATIO:
        return ROLL_FOLLOWING, True
    if _dn / _tot >= _ROLL_DIR_MIN_RATIO:
        return ROLL_PRECEDING, True
    return ROLL_MODIFIED_FOLLOWING, False   # 方向混雜 → 保守回退(亦為預設值),信心由 caller 壓 low


def _anchor_score(dates: list, a_type: str, params: Any, convention: str) -> float:
    """§2 復現率 s:該假說能重現自身歷史的比例。

    ⚠️ **先套 R 再比對**(不套的話月底型會被系統性低估:月底常遇六日)。
    """
    if not dates:
        return 0.0
    _hit = 0
    for e in dates:
        if _apply_roll(_anchor_nominal(a_type, params, e.year, e.month),
                       convention, e.year, e.month) == e:
            _hit += 1
    return _hit / len(dates)


_NTH_MAX_J = 5                   # §14.1 NTH_* 的 j 候選上限(月最多 5 個同星期)
_FIXED_DAY_MAX = 31              # §14.1 FIXED_DAY 的 D 候選上限


def _anchor_candidates(a_type: str) -> list:
    """§14.1 各假說的**有限候選參數集**(全部極小,窮舉零效能疑慮)。

    順序 = 平手時的決選順序(同分取數值較小者:D 小 / n 小 / j 小 / w 小),
    配合 `_best_of_type` 的「嚴格大於才換人」→ deterministic。
    """
    if a_type == ANCHOR_MONTH_END:
        return [None]                                             # 無參數
    if a_type == ANCHOR_MONTH_END_OFFSET:
        return list(range(1, _MONTH_END_OFFSET_MAX + 1))          # 3 個
    if a_type == ANCHOR_FIXED_DAY:
        return list(range(1, _FIXED_DAY_MAX + 1))                 # 31 個
    return [(w, j) for j in range(1, _NTH_MAX_J + 1) for w in range(7)]   # 35 個


def _best_of_type(dates: list, a_type: str) -> dict:
    """§14.1:窮舉該假說的所有候選參數,取**復現率 s 最大**者。

    §13.4 一致性:每個候選參數**各自**估自己的 ρ、用自己的 R 算自己的 s ——
    **不可**先固定校正方向再窮舉參數(方向本身是參數的函數,先固定會拿到別人的方向)。

    §14.1 廢止中位數 / 眾數 / half-up:兩者都只是「最大化 s」的粗略近似,
    實測會在「棄權 vs 可預測」的分水嶺上給錯答案(摩根 D*=8 s=0.42 vs 窮舉 D*=7 s=0.83;
    瀚亞 D*=30 s=0.67 vs 窮舉 D*=31 s=1.00)。窮舉後捨入問題不存在。
    """
    _best: dict = {}
    for _params in _anchor_candidates(a_type):
        _conv, _inferred = _infer_roll_convention(dates, a_type, _params)
        _sc = _anchor_score(dates, a_type, _params, _conv)
        if not _best or _sc > _best["score"]:      # 嚴格大於 → 同分保留先出現(數值較小)者
            _best = {"type": a_type, "params": _params, "score": _sc,
                     "roll_convention": _conv, "roll_inferred": _inferred}
    return _best


def detect_anchor(dates: list) -> "dict | None":
    """歷史日期序列(除息基準日)→ 最佳錨定假說(規格 §1~§3、§12 API 契約)。

    不足 3 筆(§3 k < 3)或最佳復現率 s⁽¹⁾ < 0.80 → **None**(落 unpredictable,§1 不硬給)。

    Returns:
        {
          "type": str,             # MONTH_END | MONTH_END_OFFSET | FIXED_DAY
                                   #  | NTH_WEEKDAY_FROM_END | NTH_WEEKDAY
          "params": tuple|int|None,# NTH_* → (w, j);FIXED_DAY → D;MONTH_END_OFFSET → n;
                                   # MONTH_END → None
          "score": float,          # s⁽¹⁾(排序後最高分)
          "runner_up": float,      # s⁽²⁾
          "roll_convention": str,  # following | preceding | modified_following
          "tie_broken": bool,      # 是否因 s⁽¹⁾-s⁽²⁾ < 0.10 而依「參數較少」決選
          "runner_up_anchor": dict|None,
                                   # **top-2 中未被採用的那一個**假說(type/params/score/
                                   # roll_convention/roll_inferred),可直接餵 `project_anchor`。
                                   # v19.531:平手封頂需要它才能判斷「兩個模型是否真的分岔」——
                                   # 只有 `runner_up` 這個純分數,分不出「同意」與「不確定」。
          "roll_inferred": bool,   # 校正方向是否真從歷史推得(False = 用預設值,§13.3 純稽核欄位,
                                   # **不**再直接決定信心 —— 壓 low 的條件改看 roll_convention)
          "n": int,                # 擬合用筆數 k(§4 信心公式的 k)
        }

    ⚠️ `score` 依 §12 契約回**排序後最高分 s⁽¹⁾**。當 `tie_broken=True` 時,實際採用的假說
    是參數較少的那個(其自身分數 = `runner_up`,最多低 0.10);此時信心上限**視兩者是否對
    目標月投影出同一天**而定(見 `_tie_diverges_in_month`),不再無條件壓 medium。
    """
    _ds = sorted({d for d in (dates or []) if isinstance(d, _dt.date)
                  and not isinstance(d, _dt.datetime)})
    _k = len(_ds)
    if _k < _ANCHOR_MIN_RECORDS:
        return None

    _cands = [_best_of_type(_ds, _t) for _t in _ANCHOR_ORDER]      # §14.1 每型各自窮舉最佳參數
    _cands.sort(key=lambda c: (-c["score"], _ANCHOR_PARAM_COUNT[c["type"]],
                               _ANCHOR_ORDER.index(c["type"])))
    _best, _second = _cands[0], _cands[1]
    _s1, _s2 = _best["score"], _second["score"]
    if _s1 < _ANCHOR_ACCEPT_MIN:
        return None                       # §3 閘門:重現不了自己的歷史 → 不預測(§1)
    _tie = (_s1 - _s2) < _ANCHOR_TIE_DELTA
    _pick = _best
    if _tie and _ANCHOR_PARAM_COUNT[_second["type"]] < _ANCHOR_PARAM_COUNT[_best["type"]]:
        _pick = _second                   # §3 平手 → 取參數較少者(少過擬合)
    _rival = _second if _pick is _best else _best      # top-2 中**沒被採用**的那一個
    return {"type": _pick["type"], "params": _pick["params"], "score": _s1, "runner_up": _s2,
            "roll_convention": _pick["roll_convention"], "tie_broken": bool(_tie),
            "runner_up_anchor": dict(_rival),          # v19.531 平手封頂要靠它比對投影
            "roll_inferred": bool(_pick["roll_inferred"]), "n": _k}


def project_anchor(anchor: dict, year: int, month: int) -> "_dt.date | None":
    """錨 + 目標年月 → **校正後**的除息基準日推估值(§12 API 契約)。

    該月無合理錨定日(假說在該月不存在、或校正位移超過 τ=3 日曆日)→ None(§1 不硬給)。
    回傳值保證落在 (year, month) 當月且為營業日。

    Raises:
        ValueError — `anchor` 非 dict、`type` 不在五個假說之內、或 year/month 不合法。
            **§13.7.2 Fail Loud**:壞掉的錨是程式錯誤,不可靜默回 None —— 那會和
            「該月無合理錨定日」(合法的 None)混淆,讓 bug 偽裝成正常棄權。
    """
    if not isinstance(anchor, dict):
        raise ValueError(f"project_anchor: anchor 必須是 dict,得到 {type(anchor).__name__}")
    _type = anchor.get("type")
    if _type not in _ANCHOR_PARAM_COUNT:
        raise ValueError(f"project_anchor: 不認得的錨定假說 type={_type!r};"
                         f"合法值 {sorted(_ANCHOR_PARAM_COUNT)}")
    try:
        _y, _m = int(year), int(month)
    except (TypeError, ValueError) as _e:
        raise ValueError(f"project_anchor: year/month 需為整數({year!r}, {month!r})") from _e
    if not 1 <= _m <= 12:
        raise ValueError(f"project_anchor: month 需在 1..12,得到 {month!r}")
    _nominal = _anchor_nominal(_type, anchor.get("params"), _y, _m)
    return _apply_roll(_nominal, anchor.get("roll_convention") or ROLL_MODIFIED_FOLLOWING, _y, _m)


def _tie_diverges_in_month(anchor: dict, year: int, month: int,
                           projected: "_dt.date | None") -> bool:
    """平手的兩個假說,對**該目標月**是否真的投影出不同的日期(v19.531 修正 1)。

    §3 的平手封頂(信心上限 medium)要罰的是「有兩個同樣能解釋歷史、但**未來會分岔**的假說」。
    原實作只看 `tie_broken` 這個旗標,把「兩個模型對這個月**投影出同一天**」也一起罰了 ——
    那是把「兩個模型互相印證」讀成「不確定」,方向剛好相反(實測:瀚亞 ACCP138
    MONTH_END vs FIXED_DAY(31) 對 2026-09 同為 09/30、s=1.00 完美復現、walk-forward 12/12 全中,
    卻只拿到 medium;同一批實測 low 桶命中率 94% > medium 桶 85%,信心標籤成了反指標)。

    判定:
      - 未平手(`tie_broken` 為假)→ False(本來就沒有封頂問題)
      - 沒有對手資訊(手搭 anchor dict 無 `runner_up_anchor`)→ True(保守,維持舊行為)
      - 對手投影 == 本月採用值 → **False**(兩個模型同意 → 不封頂)
      - 對手投影為 None 或不同日 → True(真的分岔 → 維持封頂)

    ⚠️ 逐月判定,不是逐檔:同一組平手假說可能 9 月同日、2 月(月長不同 / 連假)分岔,
    分岔的那個月仍會被封頂 —— 這正是封頂原本要擋的情形。
    """
    if not anchor.get("tie_broken"):
        return False
    _rival = anchor.get("runner_up_anchor")
    if not isinstance(_rival, dict):
        return True                       # 無從比對 → 保守維持封頂(§1 不假裝知道)
    return project_anchor(_rival, year, month) != projected


def _grade_confidence(score: "float | None", k: int, horizon: int, *,
                      tie_broken: bool = False, roll_convention: "str | None" = None) -> str:
    """§4 信心 = 復現率 s + 擬合筆數 k + 預測地平線 h。**day_std 已完全移除**。

    high   : s ≥ 0.95 且 k ≥ 6 且 h ≤ 1
    medium : s ≥ 0.85 且 k ≥ 4 且 h ≤ 3
    low    : 其餘
    **v19.532 阻斷 1**:`k < _CONF_MIN_RECORDS_FOR_TRUST`(8)→ 一律 low,**不論 s 多高**。
    理由是實測不是感覺:對「每月從同一個 5 天窗內隨機挑一個營業日」的**純雜訊**歷史
    (生成過程完全無規則)各跑 400 次,改動前 ——
        k=3 給出日期 29.8%(全 low)｜k=5 27.0%(含 **11 筆 medium**)
        k=7  8.2%(含 **2 筆 high + 22 筆 medium**)｜k=12 1.5%(含 5 筆 medium)
    —— 亦即 105 組候選參數(1+3+31+35+35)拿去擬 3~7 個點,靠窮舉就能「完美重現」一段
    純雜訊,s 閘門形同虛設。s 高在小 k 時**證明不了節奏存在**,只證明候選夠多。
    另外四個**只降不升**的封頂(順序無關,取最保守):
      - `tie_broken`(§3 前二名差 < 0.10 靠參數數決選,**且兩者對該目標月投影不同日** ——
        v19.531 修正 1,由 caller 用 `_tie_diverges_in_month` 判完再傳進來)→ 上限 medium
      - `roll_convention == modified_following`(§5 方向混雜、未定)→ 壓 low
        ⚠️ §13.3:歷史**零偏移**不算「方向未定」,那時 convention = following → 不壓
      - `h < 0`(回填過去月份,§13.7.3)→ 壓 low(過去月份應以實際紀錄為準,不是推估)
    """
    if score is None or k < _CONF_MIN_RECORDS_FOR_TRUST:
        return "low"                       # v19.532:筆數太少 → 誠實說沒把握(仍給日期)
    if score >= _CONF_HIGH_MIN_SCORE and k >= _CONF_HIGH_MIN_N and horizon <= _CONF_HIGH_MAX_HORIZON:
        _c = "high"
    elif score >= _CONF_MED_MIN_SCORE and k >= _CONF_MED_MIN_N and horizon <= _CONF_MED_MAX_HORIZON:
        _c = "medium"
    else:
        _c = "low"
    if tie_broken and _c == "high":
        _c = "medium"
    if roll_convention == ROLL_MODIFIED_FOLLOWING or horizon < 0:
        _c = "low"
    return _c


def _phase_mode(dates: list, step: int) -> tuple:
    """§6 相位眾數 φ* = argmax_φ |{e: m_e ≡ φ (mod step)}| → (φ*, 一致率)。

    一致率 < 0.8 → φ* 回 None(稽核 A8:一筆特別配息就會旋轉整個季度網格 → 寧可不預測)。
    step=1(月配)恆為 (0, 1.0)。`m % step` 對 step ∈ {1,3,6,12} 跨年一致(12 可被整除)。
    """
    if step <= 1:
        return 0, 1.0
    if not dates:
        return None, 0.0
    _c = _Counter(d.month % step for d in dates)
    _phase, _hits = max(_c.items(), key=lambda kv: (kv[1], -kv[0]))
    _ratio = _hits / len(dates)
    return (_phase if _ratio >= _PHASE_MIN_RATIO else None), _ratio


def _grid_anomaly_ratio(dates: list, step: int, phase: "int | None") -> float:
    """§13.5 雙配息/漏配偵測的比率:分母 = **依 cadence 網格預期有配息的月份數**。

    分母 = 歷史跨距內滿足 `m % step == φ*` 的月份數;分子 = 這些月份中實際出現次數 **≠ 1** 者
    (含 0 次 = 該配沒配、≥2 次 = 一個月配兩次)。**網格外的月份不計入** —— 否則季配基金有
    8/12 個月本來就是 0 次,佔比 0.67 會讓每一檔季配都被誤判 irregular。
    """
    if not dates or not step or phase is None:
        return 0.0
    _cnt = _Counter((d.year, d.month) for d in dates)
    _y, _m = min(dates).year, min(dates).month      # 不假設輸入已排序(§13.7.4 同精神)
    _end = (max(dates).year, max(dates).month)
    _denom = _num = 0
    for _ in range(240):                       # 上限保護(240 月 = 20 年)
        if _m % step == phase:
            _denom += 1
            if _cnt.get((_y, _m), 0) != 1:
                _num += 1
        if (_y, _m) >= _end:
            break
        _m += 1
        if _m > 12:
            _m = 1
            _y += 1
    return (_num / _denom) if _denom else 0.0


def infer_schedule(dividends: list) -> dict:
    """配息史 → 節奏推估 dict(推估目標量 = **除息基準日**,見 `_parse_records`)。

    Returns:
        {cadence, ex_day, pay_gap_days, n, confidence, day_std,
         last_ex, last_amount, last_yield, med_gap, anchor, phase}
        cadence ∈ {none, single, monthly, quarterly, semiannual, annual, irregular}
        confidence ∈ {none, low, medium, high}
        anchor  = `detect_anchor` 的 dict 或 None(None = 節奏無穩定錨 → 不預測,§1)
        phase   = 月份相位 φ*(季/半年/年配用;月配恆 0;一致率不足 → None)

    ⚠️ **`ex_day` / `day_std` 已退役**(v19.530 §4):兩者**不再參與信心計算**,僅為相容保留。
    `day_std` 對星期錨定在結構上無資訊(連續 7 個整數的母體標準差恆為 √((7²−1)/12)=2.00,
    永遠低於舊的 `<=4` 閘門 → 實測 85~91% 錯誤率全被標成 high);`ex_day` 是「幾號」的中位數,
    對月底型 / 星期型都是錯的模型。新信心公式改由 `anchor.score` + 筆數 + 地平線決定。

    ⚠️ `last_yield` / `last_amount` **不可當年化配息率/金額顯示**(v19.524 稽核):兩者都只是
    「最近一筆」的原始值 —— (a) `yield_pct` 在 FundClear/Cnyes 來源常被上游 `or 0` 強制成 0.0,
    顯示會變成看似真實的「0.0%」(§1 捏造);(b) MoneyDJ 來源雖為年化率,但只是該筆基準日當下的
    點值,配息調整/淨值變動後即失真;(c) `last_amount` 是**原幣每單位**金額,本結構未帶 currency,
    USD/TWD 混列無法辨識(§4.1 單位陷阱)。要顯示年化配息率請用全站正典
    `services.health.dividend._resolve_adr_with_fallback`(3 層 SSOT,全站其餘頁面皆用它)。
    月曆明細表已於 v19.524 移除這兩欄(user 指示),此處保留欄位僅為相容,**新 caller 勿直接渲染**。
    """
    recs = _parse_records(dividends)
    n = len(recs)
    if n == 0:
        return {"cadence": "none", "ex_day": None, "pay_gap_days": None, "n": 0,
                "confidence": "none", "day_std": None, "last_ex": None,
                "last_amount": None, "last_yield": None, "med_gap": None,
                "anchor": None, "phase": None}

    recent = recs[-_RECENT_N:]
    _rdates = [r["ex"] for r in recent]

    # §6 med_gap 改取**近 k 筆**的 gap(與錨定 / 相位同視窗;原本 gap 用全史、days 用近 12 筆,
    # 兩視窗不一致 → 改頻率時一邊每年吞 8 筆、一邊每年捏 8 筆,稽核 A7)。
    gaps = [(_rdates[i] - _rdates[i - 1]).days for i in range(1, len(_rdates))]
    med_gap = _stats.median(gaps) if gaps else None
    cadence = _cadence_from_gap(med_gap)

    # §6 漂移 / 雙配息偵測 → irregular。
    # ⚠️ **不得宣稱這兩條修掉了稽核 A10**(§13.5):測試組實測「固定 30 天間隔型」的 gap 標準差
    # 是 0.0、重複月佔比僅 2.9%,兩條規則都抓不到它 —— 真正擋下 A10 的是 §3 的 s 閘門
    # (該型的錨定復現率遠低於 0.80)。本段擋的是**別的**東西:節奏漂移與一月兩配。
    _gap_std = _stats.pstdev(gaps) if len(gaps) > 1 else 0.0
    _step0 = _CADENCE_MONTHS.get(cadence)
    _phase0 = _phase_mode(_rdates, _step0)[0] if _step0 else None
    if _step0:
        if med_gap and _gap_std > _GAP_DRIFT_MAX_RATIO * med_gap:
            cadence = "irregular"                       # 節奏漂移
        elif _phase0 is None:
            cadence = "irregular"                       # §6 相位一致率 < 0.8 → 網格不成立
        elif _grid_anomaly_ratio(_rdates, _step0, _phase0) > _DUP_MONTH_MAX_RATIO:
            cadence = "irregular"                       # §13.5 網格內「次數 != 1」佔比過高

    # 退役欄位(相容保留,不參與信心):ex_day「幾號」中位數 + 離散度
    days = [d.day for d in _rdates]
    day_std = _stats.pstdev(days) if len(days) > 1 else 0.0
    ex_day = recs[-1]["ex"].day if (days and day_std > 8) else (
        round(_stats.median(days)) if days else None)

    pay_gaps = [(r["pay"] - r["ex"]).days for r in recs
                if r["pay"] is not None and (r["pay"] - r["ex"]).days >= 0]
    pay_gap = round(_stats.median(pay_gaps)) if pay_gaps else None

    _step = _CADENCE_MONTHS.get(cadence)
    # §13.7.6:錨定 / med_gap / 相位**同吃近 `_RECENT_N` 筆視窗**,§3 的 k 與 §4 的 k 皆為
    # 「擬合實際使用的筆數」= len(視窗),不是全史筆數(視窗一致才不會一邊吞筆、一邊捏筆,稽核 A7)。
    anchor = detect_anchor(_rdates) if _step else None
    phase = _phase0 if _step else None

    # 信心:節奏層先以 h=0(目標=現在)評級;`predict_ex_for_month` 會用真實地平線重算並取更保守者
    if anchor is None:
        conf = "low"
    else:
        # ⚠️ 這層沒有目標月,無法做 v19.531 的「平手但同日 → 不封頂」比對 → 沿用原始
        # `tie_broken`(保守)。真正對 user 顯示的信心由 `predict_ex_for_month` 逐月重算。
        conf = _grade_confidence(anchor["score"], anchor["n"], 0,
                                 tie_broken=anchor["tie_broken"],
                                 roll_convention=anchor["roll_convention"])

    last = recs[-1]
    return {"cadence": cadence, "ex_day": ex_day, "pay_gap_days": pay_gap, "n": n,
            "confidence": conf, "day_std": day_std, "last_ex": last["ex"],
            "last_amount": last["amount"], "last_yield": last["yield_pct"],
            "med_gap": med_gap, "anchor": anchor, "phase": phase}


def _stale_state(last_ex: "_dt.date", ref_year: int, ref_month: int, step: int,
                 ref_day: "int | None" = None) -> tuple:
    """§7 + §13.1 陳舊度 → (stale_months, stale_periods, too_stale)。**單位一律「個月」**。

    舊式左邊是「幾個配息週期」右邊是「幾個月」,step=1 時碰巧等價,step=12 時
    `floor(1095/(30.44*12))=2` 拿去比 15 → 年配可靜默 3 年仍給日期(稽核 A11 原封不動)。

    `ref_day`(v19.532 bug 4):caller 知道「今天幾號」時**請傳真實日**;不傳才退回
    `_REF_DAY_OF_MONTH`(15)。原本無條件用 15 號在 production 是**固定 +14 天偏誤** ——
    `.github/workflows/dividend_calendar_notify.yml` 是 `cron: "0 0 1 * *"`(每月 1 號),
    `now.day` 恆為 1,「月中是無偏中點」只在執行日均勻分布時成立,實際恆為 1 號時
    day-15 反而是偏差最大的選擇。實測後果(cron 於 2026-09-01 觸發、月配基金、
    last=2026-05-11):真實靜默 113 天 < 122 天門檻,引擎卻算成 127 天 → 判疑停配 →
    **整檔基金從月曆上消失**。傳真實日期才是對的(把常數改成 1 只是偏到另一邊,App 路徑會受害)。
    超出該月天數的 ref_day(如 2 月傳 31)夾到月底,不讓它溢位到下個月(§1 不靜默造出假日期)。
    """
    _rd = _REF_DAY_OF_MONTH if ref_day is None else int(ref_day)
    _rd = max(1, min(_rd, _month_days(ref_year, ref_month)))
    _ref = _dt.date(ref_year, ref_month, _rd)
    _days = max(0, (_ref - last_ex).days)
    _months = int(_days // _DAYS_PER_MONTH)
    return _months, _months // step, _months > min(_STALE_MAX_PERIODS * step,
                                                   _STALE_ABS_MAX_MONTHS)


def predict_ex_for_month(schedule: dict, year: int, month: int,
                         ref_year: "int | None" = None,
                         ref_month: "int | None" = None,
                         ref_day: "int | None" = None) -> "dict | None":
    """節奏 dict + 目標年月 → 推估 dict 或 None(當月不配息 / 無法推估,§1 不硬給)。

    Returns(既有 key 全保留;v19.530 §8 增列 provenance):
        {ex_date          : date   —— 推估**除息基準日**(非除息日、非發放日,§4.1),恆為營業日且落在目標月
         pay_date_est     : date|None —— 基準日 + 歷史「基準→發放」間隔中位數;無歷史 → None
         confidence       : "high"|"medium"|"low"
         anchor_type      : str|None  —— 命中的錨定假說(§1 + §13.2 五選一)
         anchor_score     : float|None—— 該假說的歷史復現率 s⁽¹⁾(§2)
         roll_convention  : str       —— 營業日校正方向(§5,從歷史推)
         holiday_calendar : "TW"|"weekend_only" —— 是否真的扣了國定假日(稽核 A12:原本 ex 側
                            降級對 caller 完全不可見,假日表缺失時準確度掉 10.2pp 卻一字不改)
         horizon_months   : int       —— 預測地平線 h = (y_tgt-y_ref)*12 + (m_tgt-m_ref)}

    §7 + **§13.1** 陳舊度(兩邊單位統一為「**個月**」;舊式左邊是「週期數」右邊是「月數」,
    step=12 時 floor(1095/(30.44*12))=2 拿去比 15 → 年配可靜默 3 年,A11 根本沒修到):
      `stale_months  = floor((ref月中 - last_ex).days / 30.44)`
      `stale_periods = floor(stale_months / step)`
      `stale_months > min(3*step, 15)` → None(疑停配 / 資料過舊)
      `stale_periods >= 2`             → 信心壓 low

    ⚠️ `ref_year/ref_month`(v19.518):陳舊度須相對「**現在**」量,不是相對目標月;未給 → 用目標年月。
    ⚠️ `ref_day`(**v19.532 bug 4**):ref 月的「幾號」。未給 → `_REF_DAY_OF_MONTH`(15)。
       production 的 cron 是每月 **1 號**執行(`dividend_calendar_notify.yml`),恆定用 15 號
       等於每次都把陳舊度多算 14 天 —— 實測會把「真實靜默 113 天(< 122 天門檻)」算成 127 天,
       整檔基金無聲從月曆消失。**知道今天幾號的 caller 請一律傳下來**(見 `_stale_state`)。

    ⚠️ **§13.7.3 回填過去月份**:h < 0 或目標月早於 last_ex → 仍會給日期(季/年配需落在相位網格上),
    但信心一律壓 `low`。

    ⚠️ **相容路徑**:若 `schedule` **完全沒有 `anchor` 這個 key**(= 非 `infer_schedule` 產出的
    手搭 dict),退回舊的「ex_day 套目標月 + 逐週期推進」邏輯,避免打死既有外部 caller。
    `infer_schedule` 一定會帶 `anchor` key(值可能為 None → 明確表示「推不出」→ 回 None)。
    """
    cad = schedule.get("cadence")
    last_ex = schedule.get("last_ex")
    step = _CADENCE_MONTHS.get(cad)
    if step is None or last_ex is None:
        return None

    _ry = ref_year if ref_year is not None else year
    _rm = ref_month if ref_month is not None else month
    _h = (year - _ry) * 12 + (month - _rm)

    # §7/§13.1 陳舊度:日差 → **月數**(用 last_ex 的「日」,月初與月底不再同分)
    _stale_months, _stale, _too_stale = _stale_state(last_ex, _ry, _rm, step, ref_day)
    if _too_stale:
        return None                        # 疑停配 / 資料過舊 → 不硬給(§1)
    # §13.7.3:目標月早於最後一筆(回填過去)**允許**,但信心一律壓 low ——
    # 過去的月份該以實際紀錄為準,推估值混進歷史區間卻掛高信心會分不清「真的發生過」與「猜的」。
    _backfill = (year, month) < (last_ex.year, last_ex.month)

    if "anchor" in schedule:
        anchor = schedule.get("anchor")
        if anchor is None:
            return None                    # §3 閘門沒過 → 誠實回 None
        _phase = schedule.get("phase")
        if step > 1 and (_phase is None or (month % step) != _phase):
            return None                    # §6 相位不合(季/年配空月)或相位不一致 → 不列
        ex = project_anchor(anchor, year, month)
        if ex is None:
            return None                    # 該月無合理錨定日(含 §5 τ 上限)
        # v19.531 修正 1:平手封頂**逐月**判定 —— 兩個假說對本月投影出同一天 = 互相印證,
        # 不該當「不確定」罰(見 `_tie_diverges_in_month`)。
        _conf = _grade_confidence(anchor.get("score"), int(anchor.get("n") or 0), _h,
                                  tie_broken=_tie_diverges_in_month(anchor, year, month, ex),
                                  roll_convention=anchor.get("roll_convention"))
        if _backfill:
            _conf = "low"                  # §13.7.3
        _prov = {"anchor_type": anchor.get("type"), "anchor_score": anchor.get("score"),
                 "roll_convention": anchor.get("roll_convention") or ROLL_MODIFIED_FOLLOWING}
    else:
        # ── 相容路徑(手搭 schedule dict):舊「ex_day + 逐月推進」邏輯 ──────────
        ex_day = schedule.get("ex_day")
        if ex_day is None:
            return None
        # 目標月是否落在「last_ex + n×step」的網格上(n 可為負 → §13.7.3 回填)
        if ((year - last_ex.year) * 12 + (month - last_ex.month)) % step != 0:
            return None                    # 季/年配空月 → 不列
        ex = roll_to_business_day(_dt.date(year, month,
                                           min(int(ex_day), _month_days(year, month))))
        _conf = "low" if (_backfill or _h < 0) else schedule.get("confidence", "low")
        _prov = {"anchor_type": None, "anchor_score": None,
                 "roll_convention": ROLL_MODIFIED_FOLLOWING}

    if _stale >= _STALE_LOW_PERIODS:
        _conf = "low"                      # 距現在 >= 2 個週期 → 不宣稱有把握
    gap = schedule.get("pay_gap_days")
    pay = ex + _dt.timedelta(days=gap) if isinstance(gap, int) else None
    return {"ex_date": ex, "pay_date_est": pay, "confidence": _conf,
            "holiday_calendar": _holiday_calendar_state(),
            "horizon_months": _h, **_prov}


# ── §15.1 逐檔誤差帶(L2 純函式,零 IO;顯示成 ±N 天 / 僅供參考的字串在 L3)──────────
def _records_to_dividends(recs: list) -> list:
    """已 parse 的紀錄 → `infer_schedule` 吃得下的原始 dict list(walk-forward 內部用)。

    `_parse_records` 會排序 + 去重,原始 `dividends` 的索引順序與時序**無關**(MoneyDJ 是
    newest-first),所以不能直接切原始 list 當「歷史前綴」—— 必須從 parse 後的時序切,
    再還原成 dict 餵回去。key 名對齊 `_parse_records` 的取值順序(`date` 優先)。
    """
    return [{"date": r["ex"].isoformat(),
             "pay_date": r["pay"].isoformat() if r["pay"] else None,
             "amount": r["amount"], "yield_pct": r["yield_pct"]} for r in recs]


def estimate_error_band(dividends: list) -> "int | None":
    """配息史 → 該檔**自己的**誤差帶 E(天);證據不足 → None(§15.1,§1 不借別檔的準確度)。

    做法:對這一檔基金做 walk-forward —— 從第 `_CONF_MIN_RECORDS_FOR_TRUST`(8)筆起,
    每次**只用過去**推下一筆的除息基準日,收集 `|推估 - 實際|` 的日數,取 80% 分位向上取整。

        E = ceil(quantile_80({ |pred_i - true_i| : i in walk_forward(hist) }))

    Returns:
        int  —— 該檔誤差帶(天);0 代表 walk-forward 八成以上逐日命中。
        None —— **證據不足,不給數字**(歷史 < 8 筆,或 walk-forward 有給出日期的樣本 < 3)。
                L3 顯示「僅供參考」,不可自行填一個數字補位。

    ⚠️ **不可改成全站合併分布**:把所有基金的誤差混在一起算一個共用的 ±N,會讓一檔
    完全沒有證據的新基金顯示得跟老基金一樣有把握 —— 那是 §1 意義下的捏造。
    每檔只准用自己的歷史,算不出來就誠實說算不出來。

    ⚠️ 口徑與 §13.6 驗收一致(`tests/test_dividend_anchor_v19527.py::_walk_forward`):
    起手 8 筆、ref 取「最後一筆歷史所在年月」、棄權(回 None)**不計入**誤差樣本 ——
    棄權在畫面上本來就不會顯示數字,把它當成 0 天誤差會虛報準確度。

    複雜度:O(k) 次 `infer_schedule` + `predict_ex_for_month`(k = 歷史筆數 - 8),
    純計算無 IO;`build_month_calendar` 只對**推得出日期**的基金呼叫(見該函式註解)。
    """
    recs = _parse_records(dividends)
    if len(recs) < _CONF_MIN_RECORDS_FOR_TRUST:
        return None                      # 歷史不足 → 不給數字(§15.1)
    errs: list = []
    for i in range(_CONF_MIN_RECORDS_FOR_TRUST, len(recs)):
        _tgt = recs[i]["ex"]
        _ref = recs[i - 1]["ex"]         # 「現在」= 最後一筆歷史所在月(= 推下一筆的時點)
        _got = predict_ex_for_month(infer_schedule(_records_to_dividends(recs[:i])),
                                    _tgt.year, _tgt.month,
                                    ref_year=_ref.year, ref_month=_ref.month)
        if not _got or not _got.get("ex_date"):
            continue                     # 誠實棄權的月份不進誤差樣本(見 docstring)
        errs.append(abs((_got["ex_date"] - _tgt).days))
    if len(errs) < _ERR_BAND_MIN_SAMPLES:
        return None                      # 樣本太少 → 分位數沒有意義(§15.1)
    return _quantile_ceil(errs, _ERR_BAND_QUANTILE)


def _quantile_ceil(values: list, q: float) -> int:
    """整數樣本的 q 分位(線性內插)後**向上取整**。空 list → 呼叫端須先擋(§1 不回預設值)。

    內插法與 numpy 預設 (`method="linear"`) 一致:h = (n-1)·q,在相鄰兩個順序統計量之間內插。
    向上取整是刻意的**保守**方向 —— 誤差帶寧可報大一天,不可報小一天讓 user 少留餘裕。
    """
    _s = sorted(values)
    _h = (len(_s) - 1) * q
    _lo = int(_h)
    _hi = min(_lo + 1, len(_s) - 1)
    return int(_math.ceil(_s[_lo] + (_h - _lo) * (_s[_hi] - _s[_lo])))


# §14.2 unpredictable 的四類成因(code 給程式判讀,文字給 UI 顯示人話)
REASON_ANCHOR_WEAK = "anchor_weak"        # 復現率不足(s < 0.80)—— 配息節奏不規則
REASON_TOO_FEW = "too_few"                # 歷史筆數 < 3
REASON_STALE = "stale"                    # 疑停配 / 資料過舊
REASON_NO_ANCHOR_DAY = "no_anchor_day"    # 該月連假,無合理錨定日(位移超過 τ)

# §15.3 文案改**人話 + 具體數字**(user 2026-08-26 拍板)。舊版四句全是術語
# (「錨定日」「營業日校正」「容忍範圍」「歷史復現率」),user 讀完仍不知道該不該擔心
# —— 「停配」與「這個月剛好卡連假」是完全不同的兩件事,但舊文案讀起來一樣。
# ⚠️ 數字一律**現算**,不寫死:筆數 / 靜默月數 / 上次日期 / 名目錨定日都取自該檔自己的資料。
# v19.534 追加 9(總管實看 `v533_C_all_unpred` 圖後裁示):`anchor_weak` 原本句尾自帶
# 「上次是 M/D。」,但全空版型的三欄表**已有獨立的「上次實際基準日」欄** → 同一個日期在同一列
# 講兩次,而且 5 檔同原因時是同一句話複製 5 遍,在 560px 推播圖上佔掉大半版面。
# 改法:**文案一律不帶日期尾巴**,由「版面有沒有獨立日期欄」決定要不要補(見 `reason_display`)。
# ⚠️ `stale` 例外:它的日期長在句子中間(「上次配息是 2025/03,已經 11 個月沒動靜」),
#    抽掉整句就不成話 —— 那不是重複,是句子本體,故不列入「需要另附」。
_REASON_WITHOUT_LAST_DATE = (REASON_TOO_FEW, REASON_NO_ANCHOR_DAY, REASON_ANCHOR_WEAK)


def reason_needs_last_date(reason_code: str) -> bool:
    """該類 reason 文案本身**沒有**帶上次實際基準日 → 版面若沒有獨立日期欄須另附(§15.3)。

    知識放在文案這一側(SSOT):文案改了、有沒有帶日期跟著改,L3 不必猜也不必字串比對。
    """
    return reason_code in _REASON_WITHOUT_LAST_DATE


# ── 「上次 M/D」跨年歧義(v19.534 追加 8)────────────────────────────────────
# 症狀:2027-02 的月曆上寫「摩根 · 上次 8/11」,那個 8/11 其實是 **2026** 年的 —— 只寫月日,
# user 會讀成「最近一次」。`stale` 那類基金正是「上次很久以前」,不帶年份會讓人低估陳舊度(§1)。
# 規則:**跨年**(上次不在目標月的同一個曆年)**或**相差超過 `_LAST_EX_YEAR_MONTHS` 個月 → 帶年份。
# ⚠️ 為什麼不是只看「相差 > 6 個月」:總管點名的實例正是 2027-02 的月曆寫「上次 8/11」,
#    而 2026-08 → 2027-02 相差**剛好 6 個月**,單一個 `> 6` 會漏掉它 —— 而那正是最該修的一筆。
#    真正讓人誤讀的是**年份不同**(把去年的日子讀成今年),月份距離只是補一層同年內的遠距保護。
# 目標月不明(呼叫端沒傳)→ **一律帶年份**:不確定時選不會被誤讀的那一邊。
_LAST_EX_YEAR_MONTHS = 6


def _fmt_md(d: "_dt.date | None") -> str:
    """date → 「M/D」;None → ""(§1 不捏造日期,呼叫端據空字串決定整句怎麼收)。"""
    return f"{d.month}/{d.day}" if d is not None else ""


def fmt_last_ex(last_ex, *, year: "int | None" = None, month: "int | None" = None) -> str:
    """上次實際基準日 → 「M/D」或「YYYY/M/D」(§15.3 + v19.534 追加 8);None → ""。

    跨年、或離目標月超過半年 → 把年份寫出來。月曆是 2027-02、chip 卻寫「上次 8/11」時,
    那個 8/11 是 **2026** 年的,不寫年份會被讀成「最近才配過」;`stale` 那類基金正是
    「上次很久以前」,不帶年份會讓 user 低估陳舊度(§1)。
    SSOT:虛線 chip(`pending_line`)與明細表 reason 尾巴(`reason_display`)共用同一份規則。
    """
    if not isinstance(last_ex, _dt.date):
        return ""
    if year is None or month is None:
        return f"{last_ex.year}/{last_ex.month}/{last_ex.day}"    # 不確定 → 帶年份(不可被誤讀)
    _gap = abs((int(year) - last_ex.year) * 12 + (int(month) - last_ex.month))
    _cross_year = int(year) != last_ex.year
    return (f"{last_ex.year}/{last_ex.month}/{last_ex.day}"
            if (_cross_year or _gap > _LAST_EX_YEAR_MONTHS) else _fmt_md(last_ex))


def _reason_text(code: str, *, n: int = 0, window: int = 0,
                 last_ex: "_dt.date | None" = None, stale_months: int = 0,
                 nominal: "_dt.date | None" = None) -> str:
    """§15.3 四類 reason 的人話文案(SSOT:HTML 明細表 / 虛線 chip / LINE 三處共用)。"""
    if code == REASON_TOO_FEW:
        return f"只有 {n} 筆配息紀錄，還看不出規律（至少要 {_ANCHOR_MIN_RECORDS} 筆）。"
    if code == REASON_STALE:
        _when = f"{last_ex.year}/{last_ex.month:02d}" if last_ex is not None else "更早以前"
        return f"上次配息是 {_when}，已經 {stale_months} 個月沒動靜，可能停配或資料沒更新。"
    if code == REASON_NO_ANCHOR_DAY:
        _at = _fmt_md(nominal) or _fmt_md(last_ex)
        if not _at:                       # 兩個日期都算不出 → 不硬掰「平常在 X 前後」(§1)
            return "這個月碰上連假，順延後跟平常差太多，不亂猜。"
        return f"平常在 {_at} 前後除息，但這個月碰上連假，順延後差太多，不亂猜。"
    # v19.534 追加 9:句尾不再自帶「上次是 M/D。」—— 由 `reason_display` 依版面決定是否補。
    return f"最近 {window} 次除息的日子跳來跳去，對不上固定規律，不硬推。"


def _on_phase_grid(schedule: dict, month: int) -> bool:
    """目標月是否落在該檔 cadence 的相位網格上(月配恆 True;相位未定 → False)。"""
    _step = _CADENCE_MONTHS.get(schedule.get("cadence"))
    if not _step:
        return False
    if _step == 1:
        return True
    _phase = schedule.get("phase")
    return _phase is not None and month % _step == _phase


def _unpredictable_reason(schedule: dict, year: int, month: int,
                          ref_year: "int | None", ref_month: "int | None",
                          ref_day: "int | None" = None) -> tuple:
    """§14.2:推不出的成因 → (reason_code, 人話)。**只在 `predict_ex_for_month` 回 None 時呼叫**。

    §1:成因要說得出口 —— τ 收緊(§13.7.1)後,15 號型基金每逢農曆年必無預估,
    畫面上會變成「某些基金每年 2 月固定不見」;user 必須分得出「系統壞了」與「這個月真推不出」。
    判序:筆數不足 → 陳舊 → 該月無錨定日 → 復現率不足(前者成立就不必再問後者)。
    """
    _cad = schedule.get("cadence")
    _step = _CADENCE_MONTHS.get(_cad)
    _last_ex = schedule.get("last_ex")
    _n = int(schedule.get("n") or 0)
    if _n < _ANCHOR_MIN_RECORDS:
        return REASON_TOO_FEW, _reason_text(REASON_TOO_FEW, n=_n)
    if _step and _last_ex is not None:
        _ry = ref_year if ref_year is not None else year
        _rm = ref_month if ref_month is not None else month
        _months, _periods, _too_stale = _stale_state(_last_ex, _ry, _rm, _step, ref_day)
        if _too_stale:
            return REASON_STALE, _reason_text(REASON_STALE, last_ex=_last_ex,
                                              stale_months=_months)
    _anchor = schedule.get("anchor")
    if _anchor and _on_phase_grid(schedule, month) \
            and project_anchor(_anchor, year, month) is None:
        # 名目錨定日(未校正)= 「平常大約是哪天」;校正後超出 τ 才落到這一類,
        # 所以這個日期正是 user 要的參照點(§15.3「平常在 M/D 前後除息」)。
        _nominal = _anchor_nominal(_anchor.get("type"), _anchor.get("params"), year, month)
        return REASON_NO_ANCHOR_DAY, _reason_text(REASON_NO_ANCHOR_DAY, nominal=_nominal,
                                                  last_ex=_last_ex)
    # v19.534 追加 9:anchor_weak 文案**不帶**上次日期(由版面決定是否補) → 不傳 last_ex。
    return REASON_ANCHOR_WEAK, _reason_text(REASON_ANCHOR_WEAK, window=min(_n, _RECENT_N))


def build_month_calendar(funds: list, year: int, month: int,
                         ref_year: "int | None" = None,
                         ref_month: "int | None" = None,
                         ref_day: "int | None" = None) -> dict:
    """多檔基金(含 dividends)+ 目標年月 → 月曆結構。

    `ref_year/ref_month`:陳舊度參考月(現在);推未來月(下月推播)時傳「本月」,避免正常月配
    被誤判低信心(v19.518)。未給 → 用目標月(App 目標=現在,零變化)。見 predict_ex_for_month。
    `ref_day`:ref 月的「幾號」(v19.532 bug 4);未給 → 15 號。**知道今天幾號就傳真實日**,
    否則 cron(每月 1 號)每次都被多算 14 天陳舊度,月配基金會在門檻附近整檔消失。

    Args:
        funds: [{"code", "name", "house"(選填), "dividends": [...]}]
    Returns:
        {year, month, events[], by_day{day:[events]}, excluded[], unpredictable[], counts{},
         holiday_calendar}
        event = {code, name, house, ex_date, pay_date_est, confidence, last_amount, last_yield, n,
                 **error_band**,
                 **anchor_type, anchor_score, roll_convention, holiday_calendar, horizon_months**}
                 error_band = §15.1 該檔誤差帶(天,int)或 None(證據不足 → L3 顯示「僅供參考」)
        excluded     = {code, name, reason}(無配息 = 累積型/查無)
        unpredictable= {code, name, house, reason, reason_code, last_ex}(有配息史但本月無法推估)
                       house / last_ex 為 §15.3 新增:圖例顏色保留 + 顯示**上一次的實際基準日**
                       (事實;**不是**把它當本月預估 —— 那是猜)
                       reason_code ∈ {anchor_weak, too_few, stale, no_anchor_day}(§14.2),
                       reason = 對應人話。稽核 M3 + §1:誠實揭露成因而非靜默消失;
                       季/年配相位網格外的「空月」不列此(合理不配)。

    ⚠️ **v19.532 阻斷 2**:`predict_ex_for_month` 的 §8 五個 provenance key
    (`anchor_type` / `anchor_score` / `roll_convention` / `holiday_calendar` / `horizon_months`)
    原本在這一層被整包丟掉,§8 等於**只做到 L2 函式邊界、沒有任何 production 消費者拿得到**
    —— 稽核 A12 要修的「假日表缺失時 ex 側降級對 caller 不可見」根本沒修到。實測(user 5 檔):
        有 TW 假日表:覆蓋 93.7% / 命中 89.8%
        無  假日表 :覆蓋 61.9% / 命中 84.6%(**低於 §13.6 的 85% 門檻**)
    而畫面一字不改。現在 event 逐檔帶這 5 個 key,月曆頂層另帶一個整份共用的
    `holiday_calendar`,L3 據此在頁尾 / 文字 / Flex 誠實加註(見 `holiday_calendar_note`)。
    §12 相容:既有 key **一個都沒少**,只增加。
    """
    events: list = []
    excluded: list = []
    unpredictable: list = []
    for f in funds:
        code = str((f or {}).get("code") or "").strip()
        name = str((f or {}).get("name") or code)
        house = str((f or {}).get("house") or "")
        sch = infer_schedule((f or {}).get("dividends"))
        if sch["cadence"] == "none":
            excluded.append({"code": code, "name": name,
                             "reason": "無配息紀錄（累積型 / 查無配息）"})
            continue
        pred = predict_ex_for_month(sch, year, month, ref_year=ref_year,
                                    ref_month=ref_month, ref_day=ref_day)
        if pred is None:
            # §14.2:推不出就要說得出成因(code + 人話);季/年配的**空月**是合理不配,不列。
            _code, _why = _unpredictable_reason(sch, year, month, ref_year, ref_month, ref_day)
            if sch["cadence"] in ("single", "irregular") or _on_phase_grid(sch, month):
                # §15.3:推不出的基金**保留可見** —— 帶 house(圖例顏色不斷裂)+ last_ex
                # (上一次的**實際**基準日,事實)。⚠️ last_ex 是「上次」不是「本月預估」:
                # 把上個月的日期擺進本月格子等於發明位置,月底型一猜就錯一整輪。
                unpredictable.append({"code": code, "name": name, "house": house,
                                      "reason": _why, "reason_code": _code,
                                      "last_ex": sch["last_ex"]})
            # 季/年配的空月 → 合理不配,不列也不算異常
            continue
        events.append({"code": code, "name": name, "house": house,
                       "ex_date": pred["ex_date"], "pay_date_est": pred["pay_date_est"],
                       "confidence": pred["confidence"], "last_amount": sch["last_amount"],
                       "last_yield": sch["last_yield"], "n": sch["n"],
                       # §15.1 誤差帶:逐檔用**自己的**歷史 walk-forward 算(None = 證據不足)。
                       # 只對推得出日期的基金算(推不出的那些畫面上顯示 reason,不顯示 ±N),
                       # 省掉 O(k) 次重擬合。`confidence` 仍原封不動帶著 —— 它是閘門依據。
                       "error_band": estimate_error_band((f or {}).get("dividends")),
                       # §8 provenance 五欄:v19.532 前在這層被丟光(見 docstring)
                       **{_k: pred.get(_k) for _k in _PROVENANCE_KEYS}})

    events.sort(key=lambda e: (e["ex_date"], e["code"]))
    by_day: dict = {}
    for e in events:
        by_day.setdefault(e["ex_date"].day, []).append(e)
    return {"year": year, "month": month, "events": events, "by_day": by_day,
            "excluded": excluded, "unpredictable": unpredictable,
            # 整份月曆共用一個假日表狀態(逐檔那份與它同值;放頂層讓 L3 不必翻 events 才知道)
            "holiday_calendar": _holiday_calendar_state(),
            "counts": {"events": len(events), "excluded": len(excluded),
                       "unpredictable": len(unpredictable)}}


# ── 基金公司偵測(從基金名關鍵字;供月曆分色/分組)──────────────────
_HOUSE_MAP = [
    (("聯博", "alliancebernstein"), "聯博"),
    (("安聯", "allianz"), "安聯"),
    (("摩根", "jpmorgan", "jpm", "jf "), "摩根"),
    (("施羅德", "schroder"), "施羅德"),
    (("瀚亞", "eastspring"), "瀚亞"),
    (("富蘭克林", "franklin", "坦伯頓", "templeton"), "富蘭克林"),
    (("貝萊德", "blackrock"), "貝萊德"),
    (("高盛", "goldman"), "高盛"),
    (("pimco", "品浩"), "PIMCO"),
    (("野村", "nomura"), "野村"),
    (("景順", "invesco"), "景順"),
    (("富達", "fidelity"), "富達"),
    (("法巴", "bnp"), "法巴"),
    (("m&g", "安聯m&g"), "M&G"),
    (("復華", "fh"), "復華"),
    (("國泰", "cathay"), "國泰"),
    (("群益",), "群益"),
]


def detect_house(name: str) -> str:
    """從基金名關鍵字判斷所屬投信/投顧;判不出 → ''(caller 顯示代號即可,§1 不亂猜)。"""
    _n = str(name or "").lower()
    for keys, house in _HOUSE_MAP:
        if any(k in _n for k in keys):
            return house
    return ""


# ── §15.4 / §15.5「全部推不出」的整組文案(HTML / LINE 純文字 / Flex 三處共用 SSOT)──────
# 為什麼要整組換掉:原本全空月曆 + 「本月無推估除息基準日」讀起來就是**「這個月沒配息」**,
# 但事實是「這幾檔都會配息,只是我算不出是哪一天」—— 那是 §1 意義下「讓失敗看起來像成功」。
# 空月曆格是最大的誤導來源(格子是空的 = 那天沒事),所以這個情境**不畫月曆**,改逐檔一列。
ALL_UNPRED_TITLE = "本月除息日推不出來"
ALL_UNPRED_SUB_1 = "你的 {n} 檔基金這個月都會配息，只是最近的除息節奏對不上規律，系統不敢給日期。"
ALL_UNPRED_SUB_2 = "下方列出各檔上次的實際基準日供參考，實際日期請看基金公司公告。"
# v19.534 裁示 4:首行原寫「本月」,但 cron(每月 1 號)推的是**下個月** —— 規格 §15.4 逐字
# 寫的「本月」在推播情境是錯的(總管 2026-08-26 認錯改規格)。改帶實際目標月,App 端目標月
# = 當月時語意仍正確,兩邊都對。`{month}` 由 `month_label()` 產出(SSOT,與 altText 同一份)。
ALL_UNPRED_LINE_HEAD = "⚠️ {month} 有 {n} 檔推不出除息日 —— 是推不出，不是沒配息"
PENDING_SECTION_TITLE = "待確認清單"
# §15.5:先做**點名**,不做手動輸入儲存(手動覆寫的 UI 與持久化留待 user 看過後再決定,§-1 不擴散)。
PENDING_ASK_NOTE = "※ 這幾檔若你手上有近期的實際基準日，可以補進來提高準確度。"


def is_all_unpredictable(cal: "dict | None") -> bool:
    """本月**一檔都推不出**(有配息史卻全數棄權)→ True,觸發 §15.4 的整組換文案 / 換版面。

    與「真的沒有任何基金」區分開:`events` 與 `unpredictable` **都**空 = user 根本沒基金
    或全是累積型,那時仍走原本的空月文案(誠實,且沒有東西可以列)。
    三個介面(HTML / LINE 文字 / Flex)共用這一個判斷,避免三處條件各自漂移。
    """
    _c = cal or {}
    return not (_c.get("events") or []) and bool(_c.get("unpredictable") or [])


def month_label(year, month) -> str:
    """(year, month) → 「民國115年9月」。HTML / LINE 文字 / Flex altText 共用的 SSOT。

    v19.534 追加 7:畫面上原本多處寫死「本月」,但推播每月 1 號推的是**下個月** ——
    「本月」在推播情境是錯的,而徽章上寫的又是真正的目標月,同一張圖自相矛盾。
    一律改用這個函式,月份只有一個來源。年份非 int(資料壞)→ 退「?」,不猜(§1)。
    """
    _roc = (year - 1911) if isinstance(year, int) else "?"
    return f"民國{_roc}年{month}月"


def pending_line(entry: dict, *, year: "int | None" = None,
                 month: "int | None" = None) -> str:
    """待確認清單的單行文字:`投信名 · 上次 M/D`(§15.3 / §15.4)。

    §1:顯示的是**上一次的實際基準日**(事實),不是把它當本月預估 —— 差別在那個「上次」二字,
    不可省。查不到上次日期 → 誠實寫「上次日期不詳」,不回填任何日期。
    `year` / `month` 為**目標月**,只用來決定要不要把年份寫出來(v19.534 追加 8),
    不參與任何推估。
    """
    _when = fmt_last_ex((entry or {}).get("last_ex"), year=year, month=month)
    return f"{display_label(entry or {})} · {('上次 ' + _when) if _when else '上次日期不詳'}"


def reason_display(entry: dict, *, has_date_column: bool,
                   year: "int | None" = None, month: "int | None" = None) -> str:
    """推不出的基金要顯示的原因文字 —— **由呼叫端告知版面是否已另外顯示上次日期**。

    v19.534 追加 9:全空版型的三欄表已有獨立的「上次實際基準日」欄 → `has_date_column=True`,
    reason **不帶**日期尾巴(否則同一個日期在同一列講兩次,5 檔同原因時等於同句複製 5 遍);
    部分推不出的明細表日期欄是「—」→ `has_date_column=False`,reason **補上**「(上次 X)」。

    ⚠️ 判斷放在 L2(這裡),**不可**讓 L3 用字串比對去砍尾巴 —— 文案一改,比對就悄悄失效。
    ⚠️ 跨年帶年份的規則走 `fmt_last_ex`(追加 8),與虛線 chip 同一份。
    """
    _e = entry or {}
    _why = str(_e.get("reason") or "原因未提供")
    if has_date_column or not reason_needs_last_date(_e.get("reason_code")):
        return _why
    _when = fmt_last_ex(_e.get("last_ex"), year=year, month=month)
    return f"{_why}（上次 {_when}）" if _when else _why


# ── LINE 月初摘要文字(方式 C;純字串,零 IO)──────────────────
# v19.534 裁示 2:逐檔名稱後綴的「（信心低）」**移除**(text 與 Flex 兩處同步)。
# 為什麼(總管 2026-08-26):(a) 它在整則訊息裡沒有任何一處解釋;(b) 它會與 §15.1 誤差帶
# **互相矛盾** —— 一檔可能同時是 confidence=low 與 error_band=0(兩個訊號不同源)。
# **一個訊號、一個地方**:誠實訊號現在是誤差帶,它在 App 明細表。
# ⚠️ 引擎的 `confidence` 一個字都沒動 —— 仍是 §3 閘門與 §13.6 硬門檻的依據,只是不再顯示。

# 到帳推估:除息基準日 + N 個**營業日**區間(user 2026-08-24 實際經驗 5~7 天,故給區間不給單點)。
# module SSOT,不 inline magic(§3.3)。
_PAY_BIZ_DAYS_MIN = 5
_PAY_BIZ_DAYS_MAX = 7


# ── 台灣營業日:週末 + 國定假日(user 2026-08-24「節日或是六日都要順延至工作天」)──────────
# 假日資料走 `holidays` 套件的 TW 行事曆:**農曆假日(除夕/春節/端午/中秋)逐年算出、含補假**,
# 硬編表格做不到且會逐年過期。純計算、零網路。§4.5 原「無台灣假日表」限制自此解除。
_HOLIDAY_MAX_SCAN = 40          # 順延掃描上限(連假最長遠不及此;防呆避免無窮迴圈)


def _tw_holidays():
    """回傳 TW 假日查詢物件(`date in obj`);套件不可用 → None(退化為只跳週末)。快取單例。"""
    if not hasattr(_tw_holidays, "_cache"):
        try:
            import holidays as _h
            _tw_holidays._cache = _h.country_holidays("TW")
        except Exception as _e:  # noqa: BLE001 — 套件缺 → 誠實退化(見 _pay_note 文案會跟著改)
            print(f"[dividend_calendar] 無 holidays 套件({type(_e).__name__}),"
                  "營業日僅跳週末、未扣國定假日")
            _tw_holidays._cache = None
    return _tw_holidays._cache


def has_holiday_calendar() -> bool:
    """是否真的有國定假日表可用 —— 供文案誠實描述「有沒有扣國定假日」(§1 不宣稱做不到的事)。"""
    return _tw_holidays() is not None


def is_business_day(d: "_dt.date | None") -> bool:
    """是否為台灣營業日:非週末**且**非國定假日(假日表不可用時,只判週末)。"""
    if not isinstance(d, _dt.date):
        return False
    if d.weekday() >= 5:
        return False
    _h = _tw_holidays()
    return not (_h is not None and d in _h)


def roll_to_business_day(d: "_dt.date | None", *, keep_month: bool = True) -> "_dt.date | None":
    """推估日期(除息基準日)落在**週末或國定假日** → 順延到下一個營業日(user 2026-08-24)。

    基金不會在非營業日訂基準日;推估用「幾號」套到目標月時很容易落在六/日或連假,故一律校正。

    `keep_month=True`:若順延會**跨出原月份**(如 8/31 週日 → 9/1),改往前抓上一個營業日。
    月曆以「當月」為單位,跨月會讓事件掉到別的月份格子裡。

    ⚠️ 仍是**推估**:國定假日表為套件計算值,個別基金公司實際作業日可能再有出入。
    非日期 → 原樣回傳(§1 不捏造)。純函式,零 IO / 零網路。
    """
    if not isinstance(d, _dt.date) or is_business_day(d):
        return d
    _fwd = d
    for _ in range(_HOLIDAY_MAX_SCAN):
        _fwd += _dt.timedelta(days=1)
        if is_business_day(_fwd):
            break
    else:
        return d                                   # 掃不到(異常)→ 不硬給,回原值(§1)
    if keep_month and _fwd.month != d.month:
        _back = d
        for _ in range(_HOLIDAY_MAX_SCAN):
            _back -= _dt.timedelta(days=1)
            if is_business_day(_back):
                return _back
        return d
    return _fwd


def add_business_days(d: "_dt.date | None", n: int) -> "_dt.date | None":
    """回傳 d 之後第 n 個**營業日**(跳週末 **+ 國定假日**;user 2026-08-24)。

    假日表不可用時退化為只跳週末(見 `has_holiday_calendar`,文案會跟著誠實改寫)。
    n<=0 或 d 非日期 → 原樣回傳(不調整)。純函式,零 IO。"""
    if d is None or not isinstance(n, int) or n <= 0:
        return d
    cur, added = d, 0
    while added < n:
        cur = cur + _dt.timedelta(days=1)
        if is_business_day(cur):
            added += 1
    return cur


def display_label(ev: dict) -> str:
    """事件 → 顯示名稱:**只顯示投信名**(user 2026-08-24「我只要投信名」,代號不顯示)。

    圖檔月曆 / 明細表 / LINE 文字 / Flex 四個介面**共用同一規則**(SSOT,避免各處寫法漂移)。
    §1:判不出投信 → 退代號 → 退基金名 → 全空才「—」;**絕不回空字串**,否則該筆基準日在畫面上
    等於消失(Flex 空字串 text 更會讓整則推播 400)。
    """
    return (str(ev.get("house") or "").strip()
            or str(ev.get("code") or "").strip()
            or str(ev.get("name") or "").strip()
            or "—")


_CONF_RANK = {"low": 0, "medium": 1, "high": 2}


def dedupe_events(events: list) -> list:
    """同一天 + 同投信的多檔 → 只留一筆(user 2026-08-24「這邊重複也移除」)。

    格子、明細表、LINE 文字、Flex 四處共用同一去重規則(SSOT)。保序(依原順序)。
    key = (除息基準日, 顯示名)。

    ⚠️ **這是顯示層去重,會少掉「當天該投信有幾檔」的資訊** —— user 明確要求乾淨版面
    (先移除 ×N,再要求明細表也去重)。完整逐檔資料未被更動,仍在 `cal["events"]` /
    App 內頁查得到;本函式只影響呈現。
    §1:合併後信心取**最保守**(任一檔 low → 整組 low),不把低信心洗成高信心。
    """
    out: list = []
    idx: dict = {}
    for ev in events:
        _key = (ev.get("ex_date"), display_label(ev))
        _hit = idx.get(_key)
        if _hit is None:
            idx[_key] = len(out)
            out.append(dict(ev))
        else:
            _cur = out[_hit]
            if (_CONF_RANK.get(ev.get("confidence"), 1)
                    < _CONF_RANK.get(_cur.get("confidence"), 1)):
                _cur["confidence"] = ev.get("confidence")     # 取較保守者
    return out


def pay_window(ex: "_dt.date | None") -> "tuple | None":
    """除息基準日 → (最早, 最晚) 入帳推估日 = 基準日 + 5~7 個**營業日**(user 2026-08-24 經驗值)。

    §1:ex 非日期 → None(caller 顯示「—」,不捏造日期)。僅跳週末、**未扣國定假日**,
    遇連假實際到帳會更晚 —— caller 須標「推估」。純函式,零 IO。
    """
    if not isinstance(ex, _dt.date):
        return None
    return (add_business_days(ex, _PAY_BIZ_DAYS_MIN),
            add_business_days(ex, _PAY_BIZ_DAYS_MAX))


def _pay_note() -> str:
    """到帳說明單行(text / Flex 共用,口徑 SSOT 一處改兩處同步)。

    §1:括號內文案**依實際能力誠實改寫** —— 有假日表就說已扣國定假日,沒有就說沒扣,
    不宣稱做不到的事。
    """
    _scope = "已跳過週末與國定假日" if has_holiday_calendar() else "僅跳週末、未扣國定假日"
    return (f"💰 到帳約 +{_PAY_BIZ_DAYS_MIN}~{_PAY_BIZ_DAYS_MAX} 個營業日左右"
            f"（{_scope};實際仍以基金公司作業為準）")


def build_summary_text(cal: dict) -> str:
    """月曆結構 → LINE 月初提醒文字。無事件 → 誠實說本月無推估除息基準日(§1)。

    user 2026-08-24:到帳時間**不逐檔列**,改在清單「上方」寫一句「到帳約 +5~7 個營業日左右」;
    逐檔只列**除息基準日** + 名稱。口徑與月曆圖檔「入帳(估)」欄**同源**(皆走 `pay_window`),
    不再各講各的(原本圖檔用歷史發放間隔 ≈1 個月、文字用 +5 工作天,已於 v19.524 統一)。
    """
    y, m = cal.get("year"), cal.get("month")
    events = cal.get("events") or []
    _unp = cal.get("unpredictable") or []
    # §15.4:全部推不出 → **首行**先講清楚「是推不出,不是沒配息」,再列各檔上次的實際基準日。
    # 原本第一行是「🗓️ 基金除息行事曆 · 民國X年Y月（推估）」+ 一句「本月無推估除息基準日」,
    # 在 LINE 的推播預覽裡只看得到前兩行 → user 讀到的結論是「這個月沒事」(§1 違憲)。
    if is_all_unpredictable(cal):
        _ml = month_label(y, m)
        lines = [ALL_UNPRED_LINE_HEAD.format(month=_ml, n=len(_unp)),
                 f"🗓️ {_ml} · {PENDING_SECTION_TITLE}"]
        for _u in _unp[:_FLEX_MAX_ROWS]:
            lines.append(f"• {pending_line(_u, year=y, month=m)}")
        if len(_unp) > _FLEX_MAX_ROWS:
            lines.append(f"…另 {len(_unp) - _FLEX_MAX_ROWS} 檔（開 App 看完整）")
        lines.append(PENDING_ASK_NOTE)
        _warn = holiday_calendar_note(cal)
        if _warn:
            lines.append(_warn)
        lines.append("※ 推估非官方,實際以基金公司公告為準。")
        return "\n".join(lines)
    lines = [f"🗓️ 基金除息行事曆 · {month_label(y, m)}（推估）"]
    if not events:
        lines.append("你的基金本月無推估除息基準日（或資料不足）。")
    else:
        lines.append(_pay_note())
        for e in dedupe_events(events):                # 同日同投信只列一次(user 2026-08-24)
            _ex = e["ex_date"]
            lines.append(f"• {_ex.month}/{_ex.day} 除息基準日　{display_label(e)}")
    # user 2026-08-24「沒有配息的整段移除」→ 不再提累積型/無配息檔數(那些本來就不會配,不需提醒)。
    # `unpredictable`(有配息史但本月推不出)**保留** —— 那是「可能有配息但我算不出來」,
    # 靜默吃掉會讓你以為當月沒事(§1 誠實揭露)。
    if _unp:
        lines.append(f"（{len(_unp)} 檔節奏不規則/疑停配,無法推估）")
    _warn = holiday_calendar_note(cal)      # v19.532 阻斷 2:假日表降級要說出口(§1)
    if _warn:
        lines.append(_warn)
    lines.append("※ 推估非官方,實際以基金公司公告為準。")
    return "\n".join(lines)


# ── LINE Flex 彩色卡片(user 2026-08-24;LINE 原生渲染,不需產圖/託管)──────────────
# 顏色:LINE Flex 預設白底泡泡 → 採深字 + 綠 accent(雙主題可讀,不設 backgroundColor 避免主題陷阱)。
_FLEX_INK = "#1F2D3D"     # 主字(深板岩)
_FLEX_SUB = "#8896A6"     # 次要(灰)
_FLEX_EX = "#2E7D5B"      # 除息基準日(松綠)
_FLEX_MAX_ROWS = 30       # 稽核:Flex JSON ≤50KB;逐檔一列上限,其餘收斂「…另 N 檔」(對齊 text 路徑)


def _flex_event_row(e: dict) -> dict:
    """單檔一列(horizontal box):除息基準日 ｜ 投信名。

    user 2026-08-24:到帳時間不逐檔列(改由清單上方一句統一標)、名稱只留投信名(代號不顯示),
    故本列只有除息基準日 + 投信名。
    §1/稽核:LINE 拒絕**空字串 text**(整則 Flex 400 → 全推播失敗),`display_label` 保證非空。
    """
    _ex = e["ex_date"]
    _name = display_label(e)[:22]                     # 只顯示投信名(SSOT,與圖檔/文字一致)
    # v19.534 裁示 2:不再加「（信心低）」後綴 —— 見 build_summary_text 上方註解的理由(一個訊號、一個地方)。
    _contents = [
        {"type": "text", "text": f"{_ex.month}/{_ex.day} 除息基準日", "size": "sm",
         "weight": "bold", "color": _FLEX_EX, "flex": 5, "wrap": True},
        {"type": "text", "text": _name, "size": "sm", "color": _FLEX_INK, "flex": 5, "wrap": True},
    ]
    return {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": _contents}


def _flex_all_unpredictable(cal: dict, month, unp: list) -> dict:
    """§15.4「全部推不出」的 Flex 卡片:標題 / 副標 / 逐檔上次基準日 / 點名補資料。

    §1:**不可**沿用「本月無推估除息基準日」那張卡 —— 它讀起來是「這個月沒配息」,
    而事實是「都會配,只是算不出哪天」。altText 也必須改(LINE 通知列只看得到 altText,
    原本會顯示「0 檔」,那正是最誤導的一句)。
    """
    _n = len(unp)
    _body: list = [
        {"type": "text", "text": ALL_UNPRED_SUB_1.format(n=_n),
         "size": "sm", "color": _FLEX_INK, "wrap": True},
        {"type": "text", "text": ALL_UNPRED_SUB_2,
         "size": "xxs", "color": _FLEX_SUB, "wrap": True},
        {"type": "separator", "margin": "sm"},
    ]
    for _u in unp[:_FLEX_MAX_ROWS]:
        _body.append({"type": "text", "text": pending_line(_u, year=cal.get("year"),
                                                           month=cal.get("month")),
                      "size": "sm", "color": _FLEX_INK, "wrap": True})
    if _n > _FLEX_MAX_ROWS:
        _body.append({"type": "text", "text": f"…另 {_n - _FLEX_MAX_ROWS} 檔（開 App 看完整）",
                      "size": "xs", "color": _FLEX_SUB, "wrap": True})
    _body.append({"type": "text", "text": PENDING_ASK_NOTE,
                  "size": "xxs", "color": _FLEX_SUB, "wrap": True, "margin": "sm"})
    _warn = holiday_calendar_note(cal)
    if _warn:
        _body.append({"type": "text", "text": _warn, "size": "xxs", "color": _FLEX_SUB,
                      "wrap": True})
    _body.append({"type": "text", "text": "※ 推估非官方,實際以基金公司公告為準。",
                  "size": "xxs", "color": _FLEX_SUB, "wrap": True})
    _bubble = {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "spacing": "xs", "contents": [
            {"type": "text", "text": f"⚠️ {ALL_UNPRED_TITLE}", "weight": "bold", "size": "lg",
             "color": _FLEX_INK, "wrap": True},
            {"type": "text", "text": f"{month_label(cal.get('year'), month)}・{PENDING_SECTION_TITLE}",
             "size": "sm", "color": _FLEX_SUB},
        ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": _body},
    }
    # §15.4 明確要求**移除「0 檔」**:0 檔會被讀成「這個月沒有基金配息」,與事實相反。
    # v19.534 裁示 4:月份與純文字首行走同一個 `month_label`(口徑一致,不各寫各的)。
    return {"contents": _bubble,
            "alt_text": f"🗓️ {month_label(cal.get('year'), month)} "
                        f"除息行事曆（{_n} 檔待確認・系統推不出日期）"}


def build_summary_flex(cal: dict) -> dict:
    """月曆結構 → LINE Flex 彩色卡片。**純函式,零 IO**。回 {"contents": bubble, "alt_text": str}。

    無事件 → 誠實卡片說本月無推估除息基準日(§1)。內容與 build_summary_text 一致(每檔基準日 + 到帳說明)。
    """
    y, m = cal.get("year"), cal.get("month")
    events = dedupe_events(cal.get("events") or [])    # 同日同投信只列一次(user 2026-08-24)
    _unp = cal.get("unpredictable") or []

    # §15.4:全部推不出 → 換一整組(標題 / 副標 / 內容 / altText),不再是「無推估」的空卡片。
    if is_all_unpredictable(cal):
        return _flex_all_unpredictable(cal, m, _unp)

    _body: list = []
    if not events:
        _body.append({"type": "text", "text": "你的基金本月無推估除息基準日（或資料不足）。",
                      "size": "sm", "color": _FLEX_SUB, "wrap": True})
    else:
        # user 2026-08-24:到帳時間改在清單「上方」寫一句(不逐檔列),與純文字/圖檔同口徑。
        _body.append({"type": "text", "text": _pay_note(),
                      "size": "xxs", "color": _FLEX_SUB, "wrap": True})
        _body.append({"type": "separator", "margin": "sm"})
        _body.extend(_flex_event_row(e) for e in events[:_FLEX_MAX_ROWS])
        if len(events) > _FLEX_MAX_ROWS:              # 稽核:超上限收斂,避免 Flex JSON 超 50KB → 400
            _body.append({"type": "text",
                          "text": f"…另 {len(events) - _FLEX_MAX_ROWS} 檔（開 App 看完整）",
                          "size": "xs", "color": _FLEX_SUB, "wrap": True})
    # 「累積型/無配息」整段移除(user 2026-08-24);`unpredictable` 保留 —— 見 build_summary_text 註解
    if _unp:
        _body.append({"type": "text", "text": f"（{len(_unp)} 檔節奏不規則/疑停配）",
                      "size": "xxs", "color": _FLEX_SUB, "wrap": True})
    _warn = holiday_calendar_note(cal)      # v19.532 阻斷 2:假日表降級要說出口(§1)
    if _warn:
        _body.append({"type": "text", "text": _warn,
                      "size": "xxs", "color": _FLEX_SUB, "wrap": True})
    _body.append({"type": "text", "text": "※ 推估非官方,實際以基金公司公告為準。",
                  "size": "xxs", "color": _FLEX_SUB, "wrap": True, "margin": "sm"})

    _bubble = {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "spacing": "xs", "contents": [
            {"type": "text", "text": "🗓️ 基金除息行事曆", "weight": "bold", "size": "lg",
             "color": _FLEX_INK, "wrap": True},
            {"type": "text", "text": f"{month_label(y, m)}・推估", "size": "sm",
             "color": _FLEX_SUB},
        ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": _body},
    }
    _alt = (f"🗓️ {month_label(y, m)} 除息行事曆"
            f"（{len(events)} 檔・到帳=基準日+{_PAY_BIZ_DAYS_MIN}~{_PAY_BIZ_DAYS_MAX}營業日）")
    return {"contents": _bubble, "alt_text": _alt}


__all__ = ["infer_schedule", "predict_ex_for_month", "build_month_calendar",
           "detect_anchor", "project_anchor", "holiday_calendar_note",
           "detect_house", "build_summary_text", "build_summary_flex", "add_business_days",
           # §15 顯示層:誤差帶 + 「全部推不出」的文案 SSOT(L3 / LINE 共用)
           "estimate_error_band", "is_all_unpredictable", "pending_line",
           "reason_needs_last_date", "reason_display", "fmt_last_ex", "month_label",
           "ALL_UNPRED_TITLE", "ALL_UNPRED_SUB_1",
           "ALL_UNPRED_SUB_2", "ALL_UNPRED_LINE_HEAD", "PENDING_SECTION_TITLE",
           "PENDING_ASK_NOTE", "ERR_BAND_FOOTNOTE"]
