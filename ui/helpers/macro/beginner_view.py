"""v19.124 起 / v19.128 重整 — 總經 Tab 四時域分組計算用 helper。

歷史:
- v19.124-126:三大紅綠燈 + 教室(新手模式專用)
- v19.128:user 反饋砍掉新手 / 進階 / 教室,改採「長期 / 中期 / 短線 / 拐點」
  四時域 summary bar。
- 已刪除:`_render_one_traffic_light` / `render_beginner_view`
  / `render_principle_classroom` / `_PRINCIPLE_CHAPTERS`(對應教室全砍指示)
- 2026-08-05 F2:三大紅綠燈計算函式刪除(239 LOC,production 0 caller,
  唯一消費者是 tests)。它與 `compute_four_horizon_summary` 有三處重疊判斷
  (景氣 0-10 分級 / 美林時鐘階段對照 / 五警訊),**同檔同 bug 要修兩次**的
  維護稅已實付一次(phase score falsy 回退那顆,相隔 267 行各修一次),
  依 `PROCESS.md §4` 0-consumer 條款移除。
- 2026-08-05 F1:`render_four_horizon_bar` / `render_five_bucket_bar` 兩個
  summary bar 刪除,內容收進 `build_evidence_rows` + `render_evidence_table`
  (② 依據表)。**計算層 `compute_four_horizon_summary` / `compute_five_bucket_summary`
  原樣保留**,仍是該表的資料來源 —— 刪的只是那層畫面,桶數與讀數一格沒少。

§3.3 SSOT
- macro score / phase → services.macro_service.calc_macro_phase
- 美林時鐘 → services.macro_explain.classify_merrill_clock
- 警訊閾值 → shared/signal_thresholds.py(SAHM_RECESSION_THRESHOLD 等)
- 不新增 magic number

§8 架構
- L3 UI helper;compute_* 系列為純函式(無 streamlit 依賴 → 可單獨測試)

由 PR 2 (v19.125) wire 進 ui/tab1_macro.py(⚠️ 2026-08-28 註:下面這段是**歷史紀錄**,
不是現行程式;其中的 `ui.helpers.macro_beginner_view` 是 v19.204 P2-7 的向後相容 shim,
production 0 caller,已於 2026-08-28 整檔刪除 —— 現行 import path 就是本檔
`ui.helpers.macro.beginner_view`。歷史段落照本檔慣例保留不刪,僅就地標明。):
    from ui.helpers.macro_beginner_view import (
        render_beginner_view, render_principle_classroom,
    )
    _mode = st.radio(...)
    if _mode == "🟢 新手":
        render_beginner_view(indicators, phase_info)
        render_principle_classroom()
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

# GRAY_BB 於 2026-08-05 F1 隨兩個 summary bar 一起移除(當時唯一用處是 bar 的
# headline 字色);② 依據表走 st.dataframe,字色由 theme 決定,不再需要色票。
from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED
from shared.macro_thresholds_v2 import HY_SPREAD_THRESHOLDS as _HY_THR  # F-GRAY-4 v19.169
from shared.signal_thresholds import (
    CFNAI_RECESSION_THRESHOLD,
    SAHM_RECESSION_THRESHOLD,
)

# ════════════════════════════════════════════════════════════════
# 閾值常數 —— **逐顆標出處**,沒有一顆靠例外編號豁免(§3.3)
#
# ⚠️ 2026-08-27 更正:本段原註為
#     「閾值常數(本檔特用,非通用 metric — 不抽 SSOT;§8.2.A EX-POLICY-1 同理)」← 該 ID 已退役
#   —— 那是**假引用**。**EX-POLICY-1 已於 v19.212 P0-3-#4 退役**:它的豁免對象
#   `services/allocation_simulator.py`(866 LOC)整檔拔毒、production 0 caller,
#   憲法主檔 §8.2.A 例外表該列已**整列刪除線**。拿一個不存在的例外替自己豁免掉
#   「不抽 SSOT」,正是同節末句明文禁止的**「未經登錄的軟例外」**。
#   正確的引用方式見 `shared/regime_fit.py` 檔頭 —— 它引用同一個 ID 時寫明
#   「**專案已退役** allocation_simulator EX-POLICY-1」,而且是把它當**反面前例**
#   (所以我不硬編、常數集中此處),**不是**拿來當豁免依據。方向相反。
# ════════════════════════════════════════════════════════════════

# 警訊燈號:任一觸發 = 紅
#
# C2-B v19.158 — VIX warning 20 → 22(直接 import SSOT _VIX_YELLOW)
# user 拍板撤銷 v19.147 multi-cutoff(教學前置 20 比 SSOT 22 早 2 點),
# 接受「教學卡片不再提前 2 點預警」trade-off 換 SSOT 收斂。panic=30 不變。
# F-GRAY-4 v19.169 — HY beginner_panic 改 SSOT(SPEC §16.2):
# 數值不變(panic=8 / warn=5,仍為新手保守版),改 import shared/macro_thresholds_v2。
from shared.macro_buckets import (
    _MACRO_SCORE_DANGER_MAX as _MB_SCORE_DANGER_MAX,    # 2026-08-27 收 SSOT(見下)
    _MACRO_SCORE_HEALTHY_MIN as _MB_SCORE_HEALTHY_MIN,  # 2026-08-27 收 SSOT(見下)
    _VIX_RED as _MB_VIX_RED,
    _VIX_YELLOW as _MB_VIX_YELLOW,
    BUCKET_META as _BUCKET_META,     # 桶標籤 SSOT(見下方 `_bucket_bar_cells`)
    BUCKET_ORDER as _BUCKET_ORDER,
    SPECS_BY_KEY as _SPECS_BY_KEY,   # 指標 → 門檻描述 SSOT(② 表「說明」欄用)
)
from shared.colors import TRAFFIC_NEUTRAL  # v19.252 Phase 4A:gray 走 SSOT
# 2026-08-05 稽核 🟡 必修 5:燈號 emoji 收 ui/components/status.py `_TABLE` SSOT。
# 本檔原本自己維護「兩份」{"green":"🟢","yellow":"🟡","red":"🔴"} 對照表
# (四時域 + 五桶各一份)= 全站第三、四份燈號文字來源。**只收 emoji、不動色值**:
# status.py 的 hex 是 TRAFFIC_*,本 bar 現用 MATERIAL_*,換色 = user 沒要求的視覺
# 變更(§-1),留待 user 指示;emoji 完全等值故零風險先收。
from ui.components.status import status_color as _status_ssot

# 景氣燈號:macro score 0~10 切 3 級(對應 calc_macro_phase 的 0~2 衰退/8~10 高峰)。
# 2026-08-27 **收 SSOT,數值零變更**(仍是 3.0 / 6.0):同一組切點原本在
# `shared/macro_buckets.py` 與本檔各定義一份 —— 同一個事實兩份定義,§3.3 的正面違規,
# 而且 macro_buckets 那份還是 `BUCKET_DANGER_SPECS["macro_score"]` 的 yellow / red
# 來源(② 依據表的門檻描述由它產),兩份漂移時畫面會自打嘴巴。改 import 後只剩一份。
_MACRO_SCORE_DANGER_MAX: float = _MB_SCORE_DANGER_MAX    # = 3.0,< 3 → 衰退區
_MACRO_SCORE_HEALTHY_MIN: float = _MB_SCORE_HEALTHY_MIN  # = 6.0,≥ 6 → 擴張區(3~6 警戒)

_VIX_PANIC_THRESHOLD: float = _MB_VIX_RED      # = 30,恐慌(全員一致)
_VIX_WARNING_THRESHOLD: float = _MB_VIX_YELLOW # = 22,警戒(C2-B v19.158 收 SSOT)
# 注意:新手介面閾值與 stoplight (4/6) 不同 — 更保守 (避免過早警示)
_HY_SPREAD_PANIC_THRESHOLD: float = _HY_THR["beginner_panic"]["panic_above"]  # 8.0
_HY_SPREAD_WARN_THRESHOLD: float = _HY_THR["beginner_panic"]["warn_above"]    # 5.0

# UI 顏色(沿用 MATERIAL_*)
_C_GREEN, _C_YELLOW, _C_RED = MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED

# 燈號 emoji **單一來源** — 本檔原本在 3 個函式內各寫一份 {"green":"🟢",...},
# 是 `ui/components/status.py::_TABLE` 之外的第 2~4 份燈號文字。收成一份、且由
# status.py 導出(green→ok / yellow→warn / red→bad / gray→unknown 走 `_ALIASES`)。
_LEVEL_EMOJI: dict[str, str] = {
    _lv: _status_ssot(_lv).emoji for _lv in ("green", "yellow", "red", "gray")
}

# ════════════════════════════════════════════════════════════════
# 桶標籤 SSOT — 順序 / emoji / 桶名走 `shared.macro_buckets`(L3 → L0,§8.2 合法下行)
#
# 本檔原本在 `render_four_horizon_bar` 與 `render_five_bucket_bar` 各硬寫一份
# `_order` 清單(桶 key + emoji + 桶名 + 副標),是 registry 之外的第 2、3 份副本;
# registry 那份反而 production 0 consumer(只有 tests 讀)。收成一份。
#
# ✅ 副標(`sub`)已收 SSOT(user 2026-08-05 拍板)。原本本檔有一份
#   `_BAR_SUB_CURRENT` override 保留「畫面現行文案」,與 registry 三桶不同:
#       long: `regime / 結構`   → `結構 / 景氣位階`
#       mid : `景氣循環`        → `景氣循環 3-12 月`
#       news: `系統性風險`      → `系統性風險掃描`
#   registry 版三句都更白話、資訊量更足(`regime` 是英文行話,正是本輪
#   「讓初學者也能明白」要消除的那種),故 user 核准直接採用 registry,
#   override 表刪除 → 副標從此**只有一份真相**。
#   ✅ 2026-08-07 收尾:`short` 桶副標原本殘留一個英文行話,曾登記「待 user
#      另行裁決,不在 UI 層偷改」。user 已拍板改中文,且改的是
#      `shared/macro_buckets.py` 的 taxonomy SSOT **那一份**(不是在本層 override),
#      所以本檔一行未動、副標仍然只有一份真相。待裁決狀態結案。
# ════════════════════════════════════════════════════════════════


def _bucket_bar_cells(keys) -> list:
    """回 [(bucket_key, "emoji 桶名", 副標), ...] —— ② 依據表的標籤來源。

    emoji / 桶名 / 副標 / 遍歷順序**全部**由 `shared.macro_buckets.BUCKET_META`
    決定,本檔不再保留任何 override(L3 → L0,§8.2 合法下行)。
    未知 key → KeyError 當場炸(§1:寧可炸掉,不要靜默少畫一桶)。
    """
    _out = []
    for _k in keys:
        _m = _BUCKET_META[_k]
        _out.append((_k, f"{_m['emoji']} {_m['title']}", _m["sub"]))
    return _out


# 2026-08-05 F2 — 三大紅綠燈計算函式已刪除(見模組 docstring 沿革)。
# 桶燈號一律走下方 `compute_four_horizon_summary` / `compute_five_bucket_summary`,
# 本檔不再有第二套景氣分級 / 美林時鐘對照 / 警訊判斷。


# ════════════════════════════════════════════════════════════════
# v19.128 — 四時域分組 summary(長期 / 中期 / 短線 / 拐點)
# ════════════════════════════════════════════════════════════════

# 中期循環警戒閾值。
# ⚠️ 2026-08-27 更正:本行原註「(本檔特用,§3.3 EX-POLICY-1 同理 — 教學語意門檻)」(該 ID 已退役),
#   同屬上方閾值常數區說明的那種**假引用**(EX-POLICY-1 v19.212 已退役)。
#   現行依據逐顆分開:PMI / CPI 兩顆**本來就已經走 SSOT**(下方 import,v19.178/179
#   F-GRAY-4 收的),根本不需要任何例外;真正還留 inline 的只有失業率那一顆,
#   理由與待驗狀態寫在它自己的註解上,**不再共用一句總括豁免**。
from shared.macro_thresholds_v2 import (  # F-GRAY-4 v19.178 + v19.179 PR-3
    CPI_YOY_THRESHOLDS as _CPI_THR_V2,
    PMI_THRESHOLDS as _PMI_THR_V2,
)
_PMI_CONTRACTION_THRESHOLD: float = _PMI_THR_V2["beginner_panic"]["contraction_below"]  # 50.0 (SSOT)
_CPI_OVERHEAT_THRESHOLD: float = _CPI_THR_V2["beginner_panic"]["overheat_above"]  # 4.0 (SSOT)
# 失業率「偏高」線 —— 本檔剩下的兩顆 inline 門檻之一(另一顆是下方 SLOOS)。
# **留 inline 的依據(不是那個已退役的 EX-POLICY-1)**:憲法主檔 §8.3 F-GRAY-4 同一族
# 情形 —— 「教學/新手保守版」與 stoplight / score_function **刻意不同源**。
#   `shared/macro_buckets.BUCKET_DANGER_SPECS["unemployment"]` 走的是 score_function
#   那把尺(yellow=4.5 / red=6.0,出處 `services/macro/validation.py` SCORE_RULES
#   ["UNEMPLOYMENT"]);本檔這顆 5.0 是**第三個數字**,和上面兩顆都不相等,
#   是四時域教學卡自己的「偏高」線。
#   → (a) 收進既有 SSOT 任一顆都會**改動判燈輸出**(本輪硬性禁止改門檻數值);
#     (b) 只為它另開一個單一 consumer 的 `UNEMPLOYMENT_THRESHOLDS` dict,
#         是憲法主檔 §8.1 step 6「用不到的抽象」反例。
#   故**維持 inline**,但依據改標到真的成立的那一條。
# ⚠️ **待驗(§-2 規則 6,本輪只有一組看過、沒有第二組驗)**:5.0 這個數字全 repo
#   只有這一處,**查不到它的出處**(DESIGN 值?當初手打?)。本輪未查證,
#   不得被引用成「已查證的設計值」。若日後 HY / CPI / PMI 那套 `beginner_panic`
#   多段式 SSOT 要擴到失業率,這一顆就是入口。
_UNEMP_ELEVATED_THRESHOLD: float = 5.0     # 失業率 > 5% = 偏高

# 短線震盪警戒:原有兩個本地門檻常數(債市波動率 / 選擇權買賣權比)已於
# 2026-08-05 隨其判讀式一併移除 —— 對應資料從不在本函式收到的 indicators 裡,
# 門檻留著也沒有東西可比(理由詳見 `compute_four_horizon_summary` 短線桶註解)。
# `shared/macro_buckets.py` 的 registry 仍保有那兩顆的 spec,供風險雷達那條
# 獨立資料線使用;本檔不再持有第二份數值。

# 拐點警報
# ⚠️ 2026-08-27 就地登記(**本輪不動,只記錄**):50.0 與
#   `shared/macro_buckets.BUCKET_DANGER_SPECS["sloos"].red` 是**同一個數字的兩份**。
#   但 macro_buckets 那份自己的 `source` 寫的是
#   「DESIGN:對齊 macro_beginner_view._SLOOS_TIGHTENING(50)」—— 也就是**它引本檔**。
#   本檔反過來去 import 它,會讓那句出處變成自我指涉的假話(正是本輪在修的那種病),
#   而修好 macro_buckets 那句不在本輪的檔案邊界內。故**維持現狀 + 據實登記**,
#   收斂方向(哪一份當真相源)留給有授權動 `shared/macro_buckets.py` 的那一輪決定。
_SLOOS_TIGHTENING_THRESHOLD: float = 50.0  # SLOOS > 50 = 銀行收緊


def _participation(probe) -> tuple[list, list]:
    """`probe` = ((顯示名, 值), ...) → (真的取到值的名字, 沒取到的名字)。

    2026-08-05 稽核 🔴 必修 1 的共用件:桶的 headline 只能宣稱**真的算過**的那幾顆。
    """
    return ([_n for _n, _val in probe if _val is not None],
            [_n for _n, _val in probe if _val is None])


def _all_clear_headline(probe) -> str:
    """沒有任何一項越線時的 headline —— 點名算過的、標出沒取到的(§1)。

    原本三個桶各寫死一句「PMI/CPI/失業 三項皆健康」「Sahm/倒掛/CFNAI/SLOOS 全綠」,
    但那幾顆只要有一顆沒抓到,畫面照樣宣告全員健康 —— 把「沒問到」講成「問過了沒事」。
    缺的那幾顆改標「未取得」,讀者才分得出「沒事」與「不知道」。
    """
    _got, _absent = _participation(probe)
    if not _got:
        return "／".join(_n for _n, _ in probe) + " 皆未取得"
    _txt = "／".join(_got) + " 皆未越線"
    if _absent:
        _txt += f"；{'／'.join(_absent)} 未取得"
    return _txt


def compute_four_horizon_summary(
    indicators: Optional[dict],
    phase_info: Optional[dict] = None,
) -> dict:
    """四時域分組 summary 純函式計算。

    回傳:
      {
        "long":       {...},  # 🌳 長期:regime / 結構(美林時鐘 + 寬鬆度)
        "mid":        {...},  # 📈 中期:景氣循環(PMI / CPI / 失業)
        "short":      {...},  # 🎯 短線:即時避險情緒(VIX / HY 兩顆)
        "inflection": {...},  # ⚠️ 拐點:領先警報(Sahm / 倒掛 / CFNAI / SLOOS)
      }
    每桶 dict = { level, label, headline, color, emoji }
    mid / short / inflection 另帶 `spec_key`:headline 目前這個讀數是**哪一個
    指標**(`shared.macro_buckets.SPECS_BY_KEY` 的 key);全綠且 headline 退化成
    狀態詞時為 None(§1:沒有對應指標就誠實回 None,不指一個沒觸發的)。
    """
    indicators = indicators or {}

    # ── phase 重算備援
    if phase_info is None:
        try:
            from services.macro import calc_macro_phase
            phase_info = calc_macro_phase(indicators) or {}
        except Exception:
            phase_info = {}

    def _v(name: str, field: str = "value"):
        """indicators[name][field] → float,取不到回 None(絕不回 0)。

        `field` 預設是各指標的當期值;少數指標的判讀門檻不是對當期值定義的
        (例:領先指標的官方衰退線是對 3 月移動平均定的,服務層把它另存一欄),
        由呼叫端指名該欄 —— 用當期值去比移動平均的門檻是 §4.1 量綱陷阱。
        取不到 → None,讓該項**不參與判讀**;回 0 會讓缺資料偽裝成「讀數 0」。
        """
        _d = indicators.get(name) or {}
        if not _d:
            return None
        _val = _d.get(field)
        try:
            return float(_val) if _val is not None else None
        except (TypeError, ValueError):
            return None

    # gray 於 2026-08-05 稽核 🔴 必修 1 加入:一顆指標都沒取到的桶不得亮綠燈
    # (綠 = 問過了沒事;沒問到是另一回事,§1)。色票沿用五桶版既有的 TRAFFIC_NEUTRAL。
    _level_to_color = {"green": _C_GREEN, "yellow": _C_YELLOW, "red": _C_RED,
                       "gray": TRAFFIC_NEUTRAL}
    _level_to_emoji = _LEVEL_EMOJI   # status.py `_TABLE` SSOT(見模組頂部)

    # ═══ 🌳 長期:regime ═══
    # §1 / `PROCESS.md §4`「M2 去重」同型:原 `phase_info.get("score") or 5.0` 在
    # score=0.0(極端衰退,calc_macro_phase 的 clamp 下界)時 falsy 回退成中性 5.0,
    # 桶色被誤判為 yellow「轉折中」。改顯式 None 判斷,0.0 照實用。
    _score_raw = phase_info.get("score")
    _macro_score = 5.0 if _score_raw is None else float(_score_raw)
    _phase_name = phase_info.get("phase") or "未定"
    # ── 2026-09-04 第四輪稽核:🌳 長期桶與卡 1 是**同一顆分數**,同一個閘門 ──
    # 完全斷線實測:`score` 恆為 5.0(分母為零時的預設值)→ 本桶落在 `yellow`
    # 「轉折中」,而 ② 依據表把它當成一個**判讀結果**印出來。那是缺資料造出來的,
    # 不是市場的判讀。`calc_macro_phase` 現在回報 `support`,本桶讀 `.sufficient`;
    # 缺 `support` 的舊 payload → 照舊(向後相容),因為本檔也可能被別的 caller
    # 餵手捏的 phase dict —— 那種 dict 沒有 support 可讀,不宜一律灰掉。
    _long_sup = phase_info.get("support")
    _long_headline = None
    if _long_sup is not None and not _long_sup.sufficient:
        _long_level, _long_label = "gray", "資料不足"
        _long_headline = "—"
    elif _macro_score >= _MACRO_SCORE_HEALTHY_MIN:
        _long_level, _long_label = "green", "擴張 / 復甦"
    elif _macro_score < _MACRO_SCORE_DANGER_MAX:
        _long_level, _long_label = "red", "高峰 / 衰退"
    else:
        _long_level, _long_label = "yellow", "轉折中"
    # 2026-08-05 稽核 🟡 必修 3 前置:原本自己 f-string 組「擴張 (6.8/10)」,
    # 沒吃 v19.403 DUP-3 建的 SSOT `format_phase_score`(格式還多了一層括號)。
    # 兩套評分尺度(hero 的加權淨分 vs 本桶的 0-10 景氣位階)撞臉的根因就是
    # 「位階字卡格式各寫各的」;此處收 SSOT,格式與 Tab② 組合健診一致。
    # phase 缺失時 SSOT 回 ""(不捏造)→ 退回本地 fallback 保住桶內有字。
    # lazy import:`ui.helpers.macro.helpers` 會連帶拉進 `services.macro` 整包,
    # 本檔既有慣例(:351 的 calc_macro_phase)就是延後到用時才 import。
    from ui.helpers.macro.helpers import format_phase_score  # noqa: PLC0415
    if _long_headline is None:
        _long_headline = (format_phase_score(phase_info)
                          or f"{_phase_name} {_macro_score:.1f}/10")

    # ═══ 📈 中期:景氣循環 ═══
    # 2026-08-05 稽核 🔴 必修 2:每個 headline 同時帶出**它是哪一個指標**
    # (`shared.macro_buckets.SPECS_BY_KEY` 的 spec key)。原因:headline 是動態的
    # (先觸發者勝),② 依據表的「說明」欄若寫死某一個指標的門檻,遇到另一個指標
    # 命中時就答非所問。改由這裡回報身分,表格層再據此查 registry 取該指標門檻
    # —— UI 層不逆向 parse 顯示字串(那是第二份真相且一改文案就散)。
    # key 一律以服務層寫入名為準(漂移由 `tests/test_audit_20260805_tab1_wiring.py`
    # 的 key 漂移鎖守);同時清掉一串不存在的別名 fallback:`X or Y` 鏈裡的 Y 若
    # 永遠是 None,它不是備援,是讓人誤以為有備援的裝飾(§1)。
    # ⚠️ 2026-08-06 更正:上一輪這裡寫「失業率讀的 key 服務層從來沒產生過 → 恆 None,
    # 這一桶實際只掃了 PMI / CPI 兩顆」——**與現況不符**。`services/macro/us_indicators.py`
    # 的 `R["UNEMPLOYMENT"]` 確實會寫入,三顆都掃得到。留著錯註解會讓下一個人
    # 據此刪掉正確的判讀式(這正是 §3.3 反捏造要防的「文件與程式各說各話」)。
    _pmi = _v("PMI")
    _cpi = _v("CPI")            # 服務層此格已是 YoY %,與下方過熱門檻同口徑
    _unemp = _v("UNEMPLOYMENT")  # 失業率 %,與 _UNEMP_ELEVATED_THRESHOLD 同口徑
    _mid_probe = (("PMI", _pmi), ("CPI", _cpi), ("失業", _unemp))
    _mid_hits: list = []   # [(headline, spec_key), ...]
    if _pmi is not None and _pmi < _PMI_CONTRACTION_THRESHOLD:
        _mid_hits.append((f"PMI {_pmi:.1f} 收縮", "pmi"))
    if _cpi is not None and _cpi > _CPI_OVERHEAT_THRESHOLD:
        _mid_hits.append((f"CPI {_cpi:.1f}% 過熱", "cpi_yoy"))
    if _unemp is not None and _unemp > _UNEMP_ELEVATED_THRESHOLD:
        _mid_hits.append((f"失業 {_unemp:.1f}% 偏高", "unemployment"))
    if len(_mid_hits) >= 2:
        _mid_level, _mid_label = "red", "循環惡化"
    elif _mid_hits:
        _mid_level, _mid_label = "yellow", "局部走弱"
    elif _participation(_mid_probe)[0]:
        _mid_level, _mid_label = "green", "循環健康"
    else:
        # §1:三顆全沒取到 ≠ 健康。綠燈的語意是「問過了沒事」,這裡是「沒問到」。
        _mid_level, _mid_label = "gray", "資料未取得"
    _mid_headline = _mid_hits[0][0] if _mid_hits else _all_clear_headline(_mid_probe)
    # 全綠時 headline 是**狀態詞不是數字** → 無單一指標可指,回 None,
    # 由表格層改用「什麼情況會變成數字」的通用規則(不硬塞一個沒觸發的門檻)。
    _mid_spec = _mid_hits[0][1] if _mid_hits else None

    # ═══ 🎯 短線:即時避險情緒 ═══
    # 2026-08-05 稽核:債市波動率與選擇權買賣權比這兩顆,**服務層的指標 dict
    # 從來沒有產生過**(它們住在風險雷達那條獨立資料線,key 與結構都不同,
    # 不會流進本函式的 indicators)。原本兩個判讀式因此恆讀到 0 而永不觸發 ——
    # 留著等於掛兩個沒接線的哨兵假裝有在看(§1 / `PROCESS.md §4` 0-consumer)。
    # 判讀式與對應的本地門檻常數一併移除;要復活請先把資料接進 indicators。
    # 2026-08-05 稽核 🔴 必修 1(§1 違憲修正):原本這兩顆寫 `_v(...) or 0.0`,
    # VIX / HY 抓不到時會變成讀數 0.0 —— 0.0 低於所有警戒門檻,於是畫面印出
    # 「VIX 0.0 正常」🟢。**缺資料被畫成了最健康的狀態**,正是本函式內 `_v()`
    # 的 docstring 明令禁止的事(「回 0 會讓缺資料偽裝成讀數 0」),而同檔拐點桶
    # 的 10Y-2Y / CFNAI / SLOOS 早就用 `is not None` 寫對了 —— 漏網不是設計。
    _vix = _v("VIX")
    _hy = _v("HY_SPREAD")
    _short_probe = (("VIX", _vix), ("HY 利差", _hy))
    _short_hits: list = []   # [(headline, spec_key), ...] — 見中期桶的說明
    _short_severe = False
    if _vix is not None:
        if _vix >= _VIX_PANIC_THRESHOLD:
            _short_hits.append((f"VIX {_vix:.1f} 恐慌", "vix"))
            _short_severe = True
        elif _vix >= _VIX_WARNING_THRESHOLD:
            _short_hits.append((f"VIX {_vix:.1f} 警戒", "vix"))
    if _hy is not None:
        if _hy >= _HY_SPREAD_PANIC_THRESHOLD:
            _short_hits.append((f"HY {_hy:.2f}% 危機", "hy_spread"))
            _short_severe = True
        elif _hy >= _HY_SPREAD_WARN_THRESHOLD:
            _short_hits.append((f"HY {_hy:.2f}% 警戒", "hy_spread"))
    if _short_severe:
        _short_level, _short_label = "red", "極度恐慌"
    elif _short_hits:
        _short_level, _short_label = "yellow", "短線警戒"
    elif _participation(_short_probe)[0]:
        _short_level, _short_label = "green", "短線平靜"
    else:
        _short_level, _short_label = "gray", "資料未取得"
    # 本桶沒觸發時 headline 仍優先報**真實讀數**(VIX 有值就報 VIX,只有 HY 有值
    # 就報 HY),故那兩種情況仍指得出指標身分;兩顆都缺 → 誠實說未取得,
    # spec 回 None(不指一顆根本沒有數字的指標)。
    if _short_hits:
        _short_headline, _short_spec = _short_hits[0]
    elif _vix is not None:
        _short_headline, _short_spec = f"VIX {_vix:.1f} 正常", "vix"
    elif _hy is not None:
        _short_headline, _short_spec = f"HY {_hy:.2f}% 正常", "hy_spread"
    else:
        _short_headline, _short_spec = _all_clear_headline(_short_probe), None

    # ═══ ⚠️ 拐點:領先警報 ═══
    # 2026-08-05 稽核 🔴 必修 1:`or 0.0` 同上 —— 薩姆抓不到時變 0.0,
    # 低於 0.5 觸發線,於是「沒抓到」被算成「安全」並計入下方全綠宣告。
    _sahm = _v("SAHM")
    _y2 = _v("YIELD_10Y2Y")
    _y3 = _v("YIELD_10Y3M")
    # 2026-08-05 稽核:這顆的 key 服務層也沒有 —— 它以另一個代碼寫入,
    # 且**當期值與門檻不同口徑**:官方衰退線是對 3 月移動平均定義的,
    # 服務層因此把移動平均另存一欄(它自己的燈號也是拿那一欄判的)。
    # 所以這裡指名讀那一欄,而不是把當期值硬接上移動平均的門檻(§4.1)。
    # 該欄缺席(舊 cache / 上游降級)→ None → 本項不參與判讀,不回 0 冒充讀數。
    _cfnai = _v("LEI", "ma3")
    _sloos = _v("SLOOS")
    _inf_probe = (("薩姆", _sahm), ("10Y-2Y", _y2), ("10Y-3M", _y3),
                  ("CFNAI", _cfnai), ("SLOOS", _sloos))
    _inf_triggers: list = []   # [(headline, spec_key), ...] — 見中期桶的說明
    _inf_warnings: list = []
    if _sahm is not None and _sahm >= SAHM_RECESSION_THRESHOLD:
        _inf_triggers.append((f"薩姆 {_sahm:.2f} 觸發", "sahm"))
    if _y2 is not None and _y2 < 0:
        _inf_warnings.append((f"10Y-2Y 倒掛 {_y2:.2f}%", "yield_10y2y"))
    if _y3 is not None and _y3 < 0:
        _inf_warnings.append((f"10Y-3M 倒掛 {_y3:.2f}%", "yield_10y3m"))
    if _cfnai is not None and _cfnai <= CFNAI_RECESSION_THRESHOLD:
        _inf_triggers.append((f"CFNAI {_cfnai:.2f} 衰退", "cfnai"))
    if _sloos is not None and _sloos >= _SLOOS_TIGHTENING_THRESHOLD:
        _inf_warnings.append((f"SLOOS {_sloos:.0f} 收緊", "sloos"))
    if _inf_triggers:
        _inf_level, _inf_label = "red", "拐點鎖定"
    elif len(_inf_warnings) >= 2:
        _inf_level, _inf_label = "red", "多重警訊"
    elif _inf_warnings:
        _inf_level, _inf_label = "yellow", "拐點臨近"
    elif _participation(_inf_probe)[0]:
        _inf_level, _inf_label = "green", "拐點未現"
    else:
        _inf_level, _inf_label = "gray", "資料未取得"
    _inf_msgs_all = _inf_triggers + _inf_warnings
    _inf_headline = (_inf_msgs_all[0][0] if _inf_msgs_all
                     else _all_clear_headline(_inf_probe))
    # 全綠 → 狀態詞非數字,同中期桶處理(回 None)。
    _inf_spec = _inf_msgs_all[0][1] if _inf_msgs_all else None

    # `spec_key`:該桶 headline 目前是**哪一個指標**的讀數(registry spec key),
    # 消費者 = `build_evidence_rows` 的「說明(這個數字怎麼讀)」欄。
    # 🌳 長期桶刻意**不帶** spec_key:它的說明欄要揭露的是「本表切點 vs ① 結論燈
    # 切點」的差異(稽核 🔴 必修 1),不是 registry 的單一門檻描述;帶了也沒人讀,
    # 等於 `PROCESS.md §4` 的 0-consumer 欄位。
    return {
        "long": {
            "level": _long_level, "label": _long_label, "headline": _long_headline,
            "color": _level_to_color[_long_level], "emoji": _level_to_emoji[_long_level],
        },
        "mid": {
            "level": _mid_level, "label": _mid_label, "headline": _mid_headline,
            "color": _level_to_color[_mid_level], "emoji": _level_to_emoji[_mid_level],
            "spec_key": _mid_spec,
        },
        "short": {
            "level": _short_level, "label": _short_label, "headline": _short_headline,
            "color": _level_to_color[_short_level], "emoji": _level_to_emoji[_short_level],
            "spec_key": _short_spec,
        },
        "inflection": {
            "level": _inf_level, "label": _inf_label, "headline": _inf_headline,
            "color": _level_to_color[_inf_level], "emoji": _level_to_emoji[_inf_level],
            "spec_key": _inf_spec,
        },
    }


# 2026-08-05 F1 — `render_four_horizon_bar` 已刪除。
# 它自 v19.146 起就被五桶 bar 取代、production 0 caller(唯一消費者是 tests),
# 本次五桶 bar 也一併收進「② 依據表」→ 兩個 render 函式同時 0 consumer,
# 依 `PROCESS.md §4` 稽核落地條款(0 consumer → 接線或刪除,不得留著假裝有揭露)
# 移除。四時域的**計算**函式 `compute_four_horizon_summary` 原樣保留並仍是
# ② 依據表的資料來源 —— 刪的只是那層畫面,資料一格沒少。


# ════════════════════════════════════════════════════════════════
# v19.146 — 五桶 summary 擴充(對齊 Stock v18.284,Fund 加 📰 新聞為第 5 桶)
#   wraps compute_four_horizon_summary + 新增新聞桶(讀 v19.144 SSOT 閾值)
#   不修改既有 4-horizon 函式,zero 既有測試回歸
# ════════════════════════════════════════════════════════════════
def compute_five_bucket_summary(
    indicators: Optional[dict],
    phase_info: Optional[dict] = None,
    news_items: Optional[list] = None,
) -> dict:
    """五桶 summary(4-horizon + 新聞)。

    擴充自 compute_four_horizon_summary,直接呼叫它取 4 桶,再算第 5 桶。
    不複製計算邏輯,避免兩處飄移。

    第 5 桶「新聞」邏輯:
    - news_items=None(尚未抓取)→ gray「未掃描」
    - 數 is_systemic 命中數,依 shared.macro_buckets SSOT 閾值分級
      (NEWS_SYSTEMIC_YELLOW_COUNT=1,NEWS_SYSTEMIC_RED_COUNT=2)
    - 對齊 Stock 五桶 bar 第 5 桶語意

    Returns
    -------
    dict 同 compute_four_horizon_summary 結構,多 "news" key:
      {"long": {...}, "mid": {...}, "short": {...}, "inflection": {...},
       "news": {level, label, headline, color, emoji}}
    """
    _summary = compute_four_horizon_summary(indicators, phase_info)

    _level_to_color = {"green": _C_GREEN, "yellow": _C_YELLOW, "red": _C_RED,
                       "gray": TRAFFIC_NEUTRAL}  # v19.252 Phase 4A:SSOT
    _level_to_emoji = _LEVEL_EMOJI   # status.py `_TABLE` SSOT(含 gray→⬜)

    # 新聞桶不論掃沒掃到,判讀規則恆為「系統性風險命中**則數**」→ spec_key 固定。
    # 未掃描時附上它,讀者才知道之後那個數字要怎麼看(§1:不掃描 ≠ 沒門檻)。
    if news_items is None:
        _summary["news"] = {
            "level": "gray", "label": "未掃描",
            "headline": "尚未抓取 RSS 新聞",
            "color": _level_to_color["gray"], "emoji": _level_to_emoji["gray"],
            "spec_key": "news_systemic",
        }
        return _summary

    # 數 is_systemic 命中(對齊 news_repository.SYSTEMIC_RISK_KEYWORDS 標記)
    try:
        _sys_count = sum(1 for n in news_items
                         if isinstance(n, dict) and n.get("is_systemic"))
    except Exception:
        _sys_count = 0

    # 讀 SSOT 閾值(v19.144 shared.macro_buckets)
    try:
        from shared.macro_buckets import (
            NEWS_SYSTEMIC_YELLOW_COUNT, NEWS_SYSTEMIC_RED_COUNT,
        )
    except Exception:
        NEWS_SYSTEMIC_YELLOW_COUNT, NEWS_SYSTEMIC_RED_COUNT = 1, 2

    if _sys_count >= NEWS_SYSTEMIC_RED_COUNT:
        _n_level, _n_label = "red", "系統性警報"
        _n_headline = f"🚨 {_sys_count} 則系統性風險新聞(戰爭/倒閉/崩盤)"
    elif _sys_count >= NEWS_SYSTEMIC_YELLOW_COUNT:
        _n_level, _n_label = "yellow", "風險新聞"
        _n_headline = f"🚨 {_sys_count} 則系統性風險新聞,留意"
    else:
        _n_level, _n_label = "green", "無系統風險"
        _n_total = len(news_items)
        _n_headline = (f"{_n_total} 則新聞掃描,無系統性風險" if _n_total > 0
                       else "新聞掃描完成,無命中")

    _summary["news"] = {
        "level": _n_level, "label": _n_label, "headline": _n_headline,
        "color": _level_to_color[_n_level], "emoji": _level_to_emoji[_n_level],
        "spec_key": "news_systemic",
    }
    return _summary


# ════════════════════════════════════════════════════════════════
# 2026-08-05 F1 — ② 依據表(user 拍板:「結論用敘事、依據用表格」)
#
# 取代原本的 `render_four_horizon_bar` / `render_five_bucket_bar` 兩個 summary
# bar:**同樣的桶、同樣的燈 / 判讀 / 一句話**,改成表格呈現,並且多兩件原本沒有的:
#   (a) 景氣位階 與 多空強度 兩把尺**並陳且各自標明怎麼讀** —— 這兩個數字原本
#       分屬 hero 卡與五桶 bar 兩個區塊,中間夾一行「別互相換算」的 caption,
#       等於同一件事有三份說法;現在收成一張表、一份說法。
#   (b) 每一列指向**下方哪一段**細節,讓「看結論 → 想知道為什麼 → 知道去哪找」
#       這條路徑成立(初學者原本只能自己拼)。
# 資訊只增不減:桶數 / 判讀 / 讀數 / 綜合健康度分數與白話行動全部保留。
# ════════════════════════════════════════════════════════════════

# 桶 key → 下方細節區段的標題。這些標題由 `ui/tab1_macro_{longterm,midcycle,
# radar,inflection}.py` 各自寫死(那幾個檔案不在本次所有權內,無法就地建 SSOT),
# 因此本表是**鏡像**而非第二份真相;
# `tests/test_audit_20260805_tab1_summary.py` 逐條比對真檔的 heading,
# 任一標題改名而本表沒跟上 → 紅(對照「指路指到不存在的分頁」那個舊 bug)。
_BUCKET_SECTION_HINT: dict[str, str] = {
    "long":       "🌳 長期座標",
    "mid":        "📈 中期循環",
    "short":      "🎯 短線雷達",
    "inflection": "⚠️ 拐點警報",
    # 新聞明細是「🌳 長期座標」section 內的 📰 市場新聞折疊區,不是獨立一級區塊
    "news":       "🌳 長期座標",
}

# 兩把尺的「怎麼讀」—— 原本散在 hero 卡副標 + 其下那行對照 caption,收成唯一來源。
#
# 2026-08-05 稽核 🔴 必修 3(瀏覽器實測):`st.dataframe` 的字串格會**截斷**,
# 實測 🌳 長期列斷在「…① 結論燈同一」、🩺 斷在「…衛星部位積」——
# 被截掉的正好是 §1 要求揭露的那幾句(兩套切點差異 / 白話行動)。
# 處置(user 拍板):**欄內只留短句,長句搬到表下那一則 caption**;
# 資訊一句不刪,只換位置(`build_evidence_footnotes` + `render_evidence_table`)。
_SCALE_NOTE_PHASE = "位階 0-10 分,恆非負"          # 欄內短句
_STRENGTH_UNIT = "指標加權淨分(有正負)"             # 欄內短句
_STRENGTH_FORMULA = "Σ score×weight(各指標分數 × 校準權重後相加)"   # → 表下
_STRENGTH_FACE = "🩺 綜合健康度"

# 全綠時 headline 是狀態詞而非數值,沒有單一指標可指 —— 說明欄改答「什麼情況
# 會變成數字」。不硬塞一個沒觸發的門檻進來(那會讓讀者以為畫面正在講那顆)。
#
# 2026-08-05 稽核必退:原句寫「該段各指標」,是對使用者的**明示宣稱** ——
# 而本表判讀的那幾顆,和使用者照指路捲下去看到的那一段裡陳列的指標,**不是
# 同一組**(該段還有走另一條資料線、本表拿不到的項目)。同一個桶裡沒取到資料
# 的項目也不參與判讀。宣稱範圍必須縮回本列真的算過的那幾顆:全綠時讀數欄本來
# 就會把它們列出來(2026-08-06 必修 1 起,那句由 `_all_clear_headline` 動態組出,
# 有值的點名、缺的標「未取得」),指過去即可,不另寫一份。
_NO_SPEC_READ_RULE = (
    "全綠 = 左邊「讀數」欄列出的那幾項都沒越過各自的警戒門檻(僅限本列算過的項目;"
    "沒取到資料的不參與判讀,也不算過關);任一越線,本列改顯示該項讀數與門檻"
)
# 上句的欄內版(必修 3):dataframe 格會截斷,76 字進去只會剩半句 ——
# 全文原樣搬到表下 caption(`build_evidence_footnotes`),此處只留指路。
_NO_SPEC_SHORT = "讀數欄各項皆未越線"


def _no_spec_rule_pointer(owner_face: str) -> str:
    """全綠判讀規則的**第二次以後**的寫法 —— 指回已經印過全文的那一列。

    2026-09-03 減字:`_NO_SPEC_READ_RULE` 是 76 字的**同一條規則**,全綠時
    📈 中期與 ⚠️ 拐點兩列都沒有 spec key,於是同一段話在同一則 caption 裡
    **原樣印兩次**(152 字)。而全綠正是最常見的那一天 —— 重複量在平靜日最大。

    ⚠️ **這是去重不是刪但書**:規則本身一字未改、仍在畫面上;第二列改成指路,
    讀者仍找得到它適用哪條規則、以及去哪裡讀(§1:不得讓任何一列變成沒有註腳)。
    `owner_face` 由 `_bucket_bar_cells` 的 `BUCKET_META` SSOT 導出,本層不重打桶名
    (§3.3);第一個吃到規則的列是誰由資料決定,少了 📈 中期時 ⚠️ 拐點自動接手印全文。
    """
    return f"全綠判讀規則同「{owner_face}」那一則"


def _spec_threshold_short(note: str) -> str:
    """registry `note` 的欄內版 —— **只截掉尾端的補充括號**,不改寫任何字或數字。

    §3.3:短句不得手打(手打 = 第二份門檻真相,registry 一改就漂移)。
    registry 的 note 慣例是「主門檻 + (補充說明)」,例如領先指標那條的括號說明
    「皆為 3 月移動平均」、新聞那條的括號列出關鍵字類別 —— 括號內容屬延伸說明,
    截掉後主門檻完整保留,**完整版**照樣出現在表下 caption(`_how_to_read_full`)。
    沒有尾括號的 note(PMI / CPI / VIX 等)原樣回傳,一個字都沒動。
    """
    _n = str(note or "").strip()
    if not _n.endswith((")", "）")):
        return _n
    _i = max(_n.rfind("("), _n.rfind("（"))
    return _n[:_i].strip() if _i > 0 else _n


def _how_to_read(spec_key) -> str:
    """spec key → 該指標判讀門檻的**欄內短句**(`shared.macro_buckets` registry SSOT)。

    2026-08-05 稽核 🔴 必修 2:② 依據表的欄名承諾「這個數字怎麼讀」,但原本只有
    🌳 長期列真的有說明,其餘四列填的是桶副標(「景氣循環 3-12 月」之類),
    對「PMI 48.5 收縮」「CFNAI -0.80 衰退」這種讀數答非所問。

    2026-08-05 稽核 🔴 必修 3:原本連指標全名一起塞(`{label} 門檻:{note}`),
    在 `st.dataframe` 裡被截斷。指標全名與完整 note 移到表下 caption
    (`_how_to_read_full`),欄內只留門檻本身。

    門檻**一律查 registry**,本層不自寫任何數字(§3.3 反捏造)——
    registry 的 `note` 欄本來就是為了描述該指標的紅黃分界而存在。
    未知 spec key → KeyError 當場炸(§1:同 `section_hint` 的既有處置,
    寧可炸也不要在說明欄印一段指向不存在指標的門檻)。
    """
    if not spec_key:
        return _NO_SPEC_SHORT
    return _spec_threshold_short(_SPECS_BY_KEY[spec_key].note)


def _how_to_read_full(spec_key) -> str:
    """同上的**完整版**(指標全名 + 未截斷 note)—— 供表下 caption 使用。

    欄內放不下的部分搬到這裡,不是刪掉(必修 3 的界線:只換位置不減資訊)。
    """
    if not spec_key:
        return _NO_SPEC_READ_RULE
    _s = _SPECS_BY_KEY[spec_key]
    return f"{_s.label} 門檻:{_s.note}"


def _phase_cutoff_note() -> str:
    """🌳 長期列的說明 —— 揭露「同一顆位階分數,本表與 ① 結論燈用不同切點」。

    2026-08-05 稽核 🔴 必修 1:`phase["score"]` 被兩套切點判讀且在畫面上相鄰,
    位階落在兩組門檻之間時,① 說 🟡 而 ② 的 🌳 說 🟢,使用者無從得知這不是 bug。
    **不 harmonize**(兩套切點各有存在理由:結論燈的加碼門檻刻意較嚴),改為揭露。

    四個數字全部 f-string 自各自 SSOT,本檔不留第二份字面值(§3.3):
      - 本列切點 → 本檔 `_MACRO_SCORE_HEALTHY_MIN` / `_MACRO_SCORE_DANGER_MAX`
      - 結論燈切點 → `services.macro.action_light` 的加碼 / 持有門檻常數

    lazy import 理由同本檔既有慣例(`calc_macro_phase` / `format_phase_score`):
    `services.macro` 是整包,模組層 import 會在 L3 helper 載入時就拉進來。
    讀不到結論燈常數時**誠實說讀不到**,不填一個猜的數字(§1)。
    """
    _mine = (f"本列切點 🟢≥{_MACRO_SCORE_HEALTHY_MIN:.1f} / "
             f"🔴<{_MACRO_SCORE_DANGER_MAX:.1f}")
    try:
        from services.macro.action_light import (  # noqa: PLC0415
            _BUY_SCORE_10,
            _HOLD_SCORE_10,
        )
    except (ImportError, AttributeError) as _e:  # pragma: no cover - 環境缺件才走到
        return f"{_mine};① 結論燈切點暫讀不到（{type(_e).__name__}）"
    return (f"{_mine};① 結論燈同一顆分數用另一組 🟢≥{_BUY_SCORE_10:.1f} / "
            f"🟡≥{_HOLD_SCORE_10:.1f}（加碼門檻較嚴）—— 兩者不同不是錯,"
            f"位階落在 {_MACRO_SCORE_HEALTHY_MIN:.1f}~{_BUY_SCORE_10:.1f} 之間時"
            f"本列會亮 🟢 而結論燈仍是 🟡")


# 表下註記兩層的標題(2026-09-03 減字 B:漸進揭露)。
# 摺疊標籤必須說清楚裡面**是什麼**,否則讀者不知道自己該不該點 ——
# 這是「收摺」與「藏起來」的唯一分界。
# 2026-09-04 稽核 #8:原句寫死「兩則」——🌳 長期那一則掛在
# `if "long" in _faces:`(見 `_evidence_footnote_items`),是**條件性**的,
# 缺 long 時常駐只剩 1 則,句子就會自打嘴巴。不寫死數量(§3.3 的同一把尺,
# 套到使用者可見字串上)。
_PINNED_FOOTNOTE_LEAD = "🔍 上表放不下、且沒有欄內短版的:"
_FOOTNOTE_EXPANDER_LABEL = "🔍 各列判讀門檻全文(上表「說明」欄的完整版)"

# 表格欄位順序(caller 不得自行改名 —— 改了 DataFrame 會出現 NaN 欄)
EVIDENCE_COLUMNS = ("面向", "判讀", "讀數", "說明（這個數字怎麼讀）", "詳細在下方哪一段")


def section_hint(bucket_key: str) -> str:
    """桶 key → 指路文字。未知 key 當場 KeyError(§1:不靜默指向空氣)。"""
    return f"詳見下方「{_BUCKET_SECTION_HINT[bucket_key]}」"


def _section_walk() -> str:
    """② 表下方的「往下走會依序看到哪幾段」目錄字串。

    2026-08-05 稽核 🟡 建議 6:指路欄塞在 `st.dataframe` 的字串格裡,dataframe
    cell 不解析 markdown 也不產生連結(renderer 刻意不傳 column_config 的理由
    見 `render_evidence_table` docstring,那個判斷不推翻)。使用者讀到區塊名後
    仍要自己往下捲過好幾個一級區塊,指路準確但不可點 —— 補一份順序當目錄。

    區段名**從 `_BUCKET_SECTION_HINT` 導出**(§3.3 不寫第二份);順序走
    `BUCKET_ORDER` 這個既有 SSOT。📰 新聞的細節掛在 🌳 長期段內,兩者同名,
    `dict.fromkeys` 去重後自然合併成一段。

    ⚠️ 刻意**只列四時域這幾段**,不列詳細區裡其他一級區塊(唯讀副盤 / 決策矩陣 /
    AI 總結):那幾段列進來就是一份會隨版面漂移的鏡像(§3.3),而四時域四段的
    順序由 `BUCKET_ORDER` 這個 SSOT 保證,不會漂。

    2026-08-07 user 拍板「四時域優先」後,這四段是詳細區**最前面的連續四段**,
    因此 caller 的目錄文案已從「先後順序是…(中間另有其他區塊)」改成直接講
    「往下捲會依序看到」。那句話由 `tests/test_audit_20260805_tab1_ui.py::
    test_the_four_horizon_sections_stay_in_order_and_contiguous` 守著 ——
    有人往中間插區塊,測試先紅,不會讓目錄變成假話。
    """
    return " → ".join(dict.fromkeys(
        _BUCKET_SECTION_HINT[_k] for _k in _BUCKET_ORDER
        if _k in _BUCKET_SECTION_HINT))


def build_evidence_rows(
    summary: Optional[dict],
    *,
    composite_score=None,
    composite_icon: str = "",
    composite_level: str = "",
    composite_action: str = "",
    n_indicators=None,
) -> list[dict]:
    """② 依據表的資料列(純函式、零 streamlit,可單獨測)。

    Parameters
    ----------
    summary
        `compute_five_bucket_summary()`(或 4 桶版)的輸出。缺哪一桶就少一列,
        **不補假桶**(§1)。
    composite_score / composite_icon / composite_level / composite_action
        綜合健康度那一列的值,由 caller 從 `calculate_composite_score()` 與
        `composite_verdict()` 取得後傳入 —— 本層不重算、不猜(避免第二份真相)。
    n_indicators
        `calculate_composite_score(..., provenance_out=)` 側車回報的實際參與筆數。
        None → 說明欄不寫筆數(不捏造;寫死字面值那版已經漂移過一次)。

    Returns
    -------
    list[dict],每個 dict 的 key 為 `EVIDENCE_COLUMNS`,列順序:
    🌳 長期(景氣位階)→ 🩺 綜合健康度(多空強度)→ 📈 中期 → 🎯 短線 → ⚠️ 拐點 → 📰 新聞。
    位階與強度**刻意相鄰**:兩把尺並陳才看得出差異(這是本表存在的主因)。
    """
    summary = summary or {}
    _keys = [_k for _k in _BUCKET_ORDER
             if isinstance(summary.get(_k), dict) and summary.get(_k)]
    _cells = {_k: (_t, _s) for _k, _t, _s in _bucket_bar_cells(_keys)}

    def _bucket_row(key: str, extra_note: str = "") -> dict:
        _title, _sub = _cells[key]
        _d = summary.get(key) or {}
        _note = f"{_sub}｜{extra_note}" if extra_note else _sub
        return dict(zip(EVIDENCE_COLUMNS, (
            _title,
            f'{_d.get("emoji", "⚪")} {_d.get("label", "—")}',
            _d.get("headline", ""),
            _note,
            section_hint(key),
        )))

    rows: list[dict] = []
    if "long" in _cells:
        # 必修 3:`_phase_cutoff_note()`(98 字,兩套切點揭露)搬到表下 caption
        # ——它在欄內會被 dataframe 截成「…① 結論燈同一」,揭露到一半等於沒揭露。
        rows.append(_bucket_row("long", _SCALE_NOTE_PHASE))

    # 綜合健康度不屬於任一桶(它是全時域指標加權),細節散在各時域的指標卡裡,
    # 因此指路是多段並列 —— 由 `_BUCKET_SECTION_HINT` 導出,不另寫一份。
    #
    # 2026-08-05 稽核 🟡 必修 3:原本只列 long / mid / short 三桶,漏掉 ⚠️ 拐點。
    # 但綜合健康度是 `Σ score×weight` 跑遍**全部**指標,而權重最高的那幾顆
    # (10Y-2Y / 10Y-3M 各 weight 2、Sahm / SLOOS 各 1.5)細節正好住在拐點段 ——
    # 使用者照指路去找,找不到貢獻最大的那幾個。補上 inflection。
    _n_prefix = "" if n_indicators is None else f"{int(n_indicators)} "
    _strength_targets = "」/「".join(
        dict.fromkeys(_BUCKET_SECTION_HINT[_k]
                      for _k in ("long", "mid", "short", "inflection")))
    # 必修 3:`Σ score×weight` 算式與白話行動(`composite_action`)搬到表下 ——
    # 實測這一格斷在「…衛星部位積」,白話行動只顯示得到半句。
    rows.append(dict(zip(EVIDENCE_COLUMNS, (
        _STRENGTH_FACE,
        f"{composite_icon} {composite_level}".strip() or "—",
        "—" if composite_score is None else f"{float(composite_score):+.1f}",
        f"多空強度:{_n_prefix}{_STRENGTH_UNIT}",
        f"詳見下方「{_strength_targets}」的指標卡",
    ))))

    # 稽核 🔴 必修 2 的接線點:這四列原本**只傳桶副標**,說明欄等於沒說明。
    # 現在比照 🌳 長期列傳 extra_note,內容由該列讀數的指標身分(`spec_key`)
    # 查 registry 取得 —— 拿掉 `_how_to_read(...)` 這個引數,說明欄立刻退回副標。
    for _k in ("mid", "short", "inflection", "news"):
        if _k in _cells:
            rows.append(_bucket_row(
                _k, _how_to_read((summary.get(_k) or {}).get("spec_key"))))
    return rows


def build_evidence_footnotes(
    summary: Optional[dict],
    *,
    composite_action: str = "",
) -> list[str]:
    """② 表**欄內放不下**的長說明(純函式、零 streamlit,可單獨測)。

    2026-08-05 稽核 🔴 必修 3:`st.dataframe` 的字串格會截斷,而被截掉的偏偏是
    §1 要求揭露的幾句(兩套切點差異 / 完整門檻 / 全綠判讀規則 / 白話行動)。
    處置是**搬不是刪** —— 欄內留短句,全文集中在表下那一則 caption。

    每一則的開頭是該列的「面向」(桶 emoji + 桶名,走 `_bucket_bar_cells` 的
    `BUCKET_META` SSOT),讀者才對得回上表哪一列;§3.3 不在本層重打桶名。

    Parameters
    ----------
    summary
        同 `build_evidence_rows` 的輸入(五桶或四桶)。缺哪一桶就少一則。
    composite_action
        綜合健康度那列的白話行動,由 caller 從 `composite_verdict()` 取得後傳入
        (本層不重算)。空字串 → 不寫(§1 不捏造)。
    """
    return [_t for _t, _c in _evidence_footnote_items(
        summary, composite_action=composite_action)]


def _evidence_footnote_items(
    summary: Optional[dict],
    *,
    composite_action: str = "",
) -> list[tuple[str, bool]]:
    """表下註記的**唯一產生處** —— `(文字, 可否收進摺疊區)`。

    `build_evidence_footnotes` 與 `split_evidence_footnotes` 都由本函式導出,
    兩者因此不可能漂移(§3.3:不留第二份真相)。

    **可收(`True`)的判準只有一條**:該則是上表「說明」欄**短版的完整版** ——
    也就是 `_how_to_read()` 已經在格子裡放了一句短的、這裡只是把被 dataframe
    欄寬截掉的尾巴補齊。讀者在表上**已經看得到**那一列的判讀門檻在講什麼,
    摺疊起來只是把「全文」收在一次點擊之後,不是把讀數藏起來。

    **不可收(`False`)的兩則,以及為什麼**(這是本函式最重要的部分):
      - 🌳 長期的**兩套切點揭露**:格子裡只有位階尺度那句短版,切點差異
        **在表上完全沒有對應的短版**。它要防的失效模式是「① 亮 🟡 而 ② 的 🌳
        亮 🟢,使用者當成 bug」(2026-08-05 必修 1)—— 收進摺疊,等於把那個
        矛盾的唯一解釋放在一次「讀者不知道自己該點」的點擊後面。
      - 🩺 綜合健康度的**算式 + 白話行動**:白話行動是 `composite_verdict()`
        **已經算好的結論**,不是推導細節;而算式同樣沒有欄內短版
        (格子裡的 `_STRENGTH_UNIT` 是**單位**,不是 `Σ score×weight` 這個算式)。
        依既有守衛的原話,已經算好的唯讀結果「闔起來等於算了不給看」。
    """
    _sum = summary if isinstance(summary, dict) else {}
    _keys = [_k for _k in _BUCKET_ORDER
             if isinstance(_sum.get(_k), dict) and _sum.get(_k)]
    _faces = {_k: _t for _k, _t, _s in _bucket_bar_cells(_keys)}

    _out: list[tuple[str, bool]] = []
    if "long" in _faces:
        _out.append((f"{_faces['long']}:{_phase_cutoff_note()}", False))
    _out.append((
        f"{_STRENGTH_FACE}:{_STRENGTH_FORMULA}"
        + (f"；白話行動 —— {composite_action}" if composite_action else ""),
        False))
    # 2026-09-03 減字(A1):全綠時 📈 中期與 ⚠️ 拐點都沒有 spec key,
    # `_how_to_read_full` 對兩者回同一段 76 字全文 → 同一則 caption 印兩次。
    # 第一個吃到的印全文,其後改指回它(`_no_spec_rule_pointer`)——
    # 規則一字未改、兩列都仍找得到它,少的只有那份逐字複本。
    _rule_owner = ""
    for _k in ("mid", "short", "inflection", "news"):
        if _k not in _faces:
            continue
        _full = _how_to_read_full((_sum.get(_k) or {}).get("spec_key"))
        if _full == _NO_SPEC_READ_RULE:
            if _rule_owner:
                _full = _no_spec_rule_pointer(_rule_owner)
            else:
                _rule_owner = _faces[_k]
        _out.append((f"{_faces[_k]}:{_full}", True))
    return _out


def split_evidence_footnotes(
    summary: Optional[dict],
    *,
    composite_action: str = "",
) -> tuple[list[str], list[str]]:
    """`build_evidence_footnotes()` 的**同一批內容**,分成 `(常駐, 可收摺)`。

    兩份的聯集**逐則等於** `build_evidence_footnotes()`,順序也保持一致 ——
    分類只決定「印在哪一層」,不決定「印不印」(§1:一則都不掉)。
    分類理由逐則寫在 `_evidence_footnote_items` 的 docstring。
    """
    _items = _evidence_footnote_items(summary, composite_action=composite_action)
    return ([_t for _t, _c in _items if not _c],
            [_t for _t, _c in _items if _c])


def _two_scales_sentence(rows) -> str:
    """📐 那句 —— **只點名表上真的有那一列的尺**(2026-09-04 稽核 #9)。

    ⚠️ **這條要修的錯,比「單位重複」更嚴重,寫清楚**:2026-09-03 那版把單位從
    句子裡搬出去,只留「見上表『說明』欄」的指路。🌳 長期那一列是**條件性**的
    (`_evidence_footnote_items` 裡掛在 `if "long" in _faces:`)——
    表上沒有那一列時,這句話會指向一個不存在的目標。**改版前的舊句把單位內嵌成
    常數,就算指路錯了讀者仍拿得到單位;本次改寫讓它退化成「指路錯 = 空指路」,
    這個退化是本次改動造成的,不是繼承的。**

    修法與 A1(`_no_spec_rule_pointer`)同一把尺:**owner 由資料決定,不寫死**。
    `rows` 是 `build_evidence_rows()` 的輸出,「面向」欄的值就是各列的桶標籤 ——
    只點名真的出現在 `rows` 裡的那些尺,一把都沒有時退回一句不提名字的警告
    (§1:寧可少一個名字,不可指向空氣)。

    ⛔ **範圍刻意限縮在這裡**:不動 `_evidence_footnote_items` 的分類、不動
    A1 去重、不動 `split_evidence_footnotes` 的分流 —— 那幾段是既有突變主要打
    的地方,動了要整組重驗(2026-09-04 總管裁決)。
    """
    _faces_on_table = {str(_r.get("面向", "")) for _r in (rows or [])}
    _long_face = f'{_BUCKET_META["long"]["emoji"]} {_BUCKET_META["long"]["title"]}'
    _scales = [f"{_long_face} 是景氣**位階**" for _f in [_long_face] if _f in _faces_on_table]
    _scales += [f"{_STRENGTH_FACE} 是多空**強度**"
               for _f in [_STRENGTH_FACE] if _f in _faces_on_table]
    if len(_scales) >= 2:
        return ("📐 " + "、".join(_scales) + " —— "
                "兩者不同義,別互相換算(各自的單位與範圍見上表「說明」欄)。")
    if len(_scales) == 1:
        # 只剩一把尺在表上時,「不同義、別互相換算」這個跨列警告本身沒有意義
        # (沒有第二把尺可比較)—— 改成單純點出這一把尺去哪讀,不硬留「兩者」措辭。
        return f"📐 {_scales[0]}(單位與範圍見上表「說明」欄)。"
    # 兩把尺都不在表上(理論上不會發生,`_STRENGTH_FACE` 那列本身無條件產生;
    # 保留是為了不讓這句話在極端輸入下印出一句指向空氣的話)。
    return "📐 上表各列「說明」欄已標明各自的判讀單位與範圍,不同列不得互相換算。"


def render_evidence_table(rows, footnotes=None, *,
                          collapsed_footnotes=None) -> None:
    """② 依據表渲染 —— 走 `ui/components/tables.styled_dataframe`。

    不手刻 HTML、不新造色票(§3.3);燈號以 emoji + 文字同格呈現,
    不靠顏色單獨編碼(dataviz #4)。

    刻意**不**傳 `column_config`:本表全為字串欄,column_config 在此只能調欄寬,
    卻讓渲染多依賴一個 `st.column_config` 屬性(測試 stub / 非 script 執行環境
    不保證有)。為了欄寬多一層可失敗的依賴不划算(§8.1 step 6)。

    表下註記維持**單一 `st.caption` 呼叫**(多段以換行併在同一個字串裡):
    user 要求「不要留兩份說法」,一段一個 caption 會讓表下變成散落的註腳堆,
    既有守衛也正是以「表下註記只有一則」為契約。新增內容一律併進這一則。

    `footnotes`(必修 3 新增,選填)= `build_evidence_footnotes()` 的輸出,
    即欄內因 dataframe 截斷而放不下的完整說明。**併進同一則 caption**,
    不另開 `st.caption`(否則上述契約破功)。None / 空 → 完全不加那一段。
    """
    import pandas as _pd  # noqa: PLC0415 — 對齊本檔既有 lazy import 慣例
    from ui.components.tables import styled_dataframe  # noqa: PLC0415
    styled_dataframe(_pd.DataFrame(list(rows or []), columns=list(EVIDENCE_COLUMNS)))
    # 2026-09-03 減字(A2/A3):原句把 `_SCALE_NOTE_PHASE` /`_STRENGTH_UNIT`
    # 兩個**欄內短句**原樣再抄一份進來,而它們就印在正上方那張表的「說明」欄裡
    # (`_bucket_row("long", _SCALE_NOTE_PHASE)` / 🩺 那列的「多空強度:…」)。
    # 本句真正的職責是**跨列的那個警告**(兩把尺不同義、別互相換算),不是重述單位。
    # 改寫後仍自我完備:點名兩把尺各是什麼(位階 / 強度)、講出警告、指出單位在哪讀;
    # 被拿掉的只有那兩份逐字複本。
    _cap_parts = [
        _two_scales_sentence(rows),
        # 稽核 🟡 建議 6:指路欄不可點 → 補一份往下捲的順序當目錄(區段名導出,見 `_section_walk`)
        # 沿革:稽核 🟡 建議 10 當時四段之間還夾著別的一級區塊,照字面往下捲會先
        # 遇到別的東西而以為走錯,故一度退守成只宣稱「這四段彼此的先後」。
        # 2026-08-07 user 拍板「四時域優先」重排後,這四段成為詳細區最前面的連續
        # 四段,退守的理由消失 → 改回直接講「往下捲會依序看到」(這是使用者真正
        # 需要的那句話)。連續性有測試守著,見 `_section_walk` docstring。
        # 夾在後面有哪些區塊仍**刻意不列**(列了就是一份會隨版面漂移的鏡像,§3.3)。
        f"📍 往下捲會依序看到:{_section_walk()} —— 這四段相連,中間不夾別的區塊。",
        # 稽核 🟢 建議 7:同一個 Tab 內,雷達圖的視覺警戒線與本表門檻不同源,
        # 使用者照指路捲下去會看到「本表說警戒、雷達線卻畫在更上面」。
        # **不改門檻**(user 2026-06-26 已撤銷 harmonize;視覺線刻意對齊雷達自己的
        # 後端燈號分級,理由見 `ui/helpers/chart/danger.py`),改為誠實註記差異。
        "⚖️ 下方各段圖上的警戒線對齊**該段自己的**燈號分級,與本表門檻可能略有差異"
        "(例:🎯 短線雷達的 VIX 線比本表的警戒門檻高一些)—— 以本表的判讀欄為準。",
    ]
    _fn = [str(_f) for _f in (footnotes or []) if str(_f).strip()]
    _to_collapse = {str(_f) for _f in (collapsed_footnotes or []) if str(_f).strip()}
    # 分流而非過濾:`_pinned + _hidden` 逐則等於 `_fn`,一則都不會消失。
    # `collapsed_footnotes` 裡若有 `footnotes` 沒有的東西,它單純不匹配 ——
    # **失效方向恆為「多印」而非「少印」**(§1:寧可版面長一點,不可靜默吞掉揭露)。
    _pinned = [_f for _f in _fn if _f not in _to_collapse]
    _hidden = [_f for _f in _fn if _f in _to_collapse]
    if _pinned:
        # 必修 3:上表「說明」欄放不下的完整版。表格格會截字,這裡不會。
        _cap_parts.append(_PINNED_FOOTNOTE_LEAD if _hidden
                          else "🔍 上表說明欄的完整版(欄位寬度有限,長句放這裡):")
        _cap_parts.extend(f"　・{_f}" for _f in _pinned)
    st.caption("  \n".join(_cap_parts))
    if _hidden:
        # 收的是**推導細節**(上表「說明」欄短版的完整版),不是讀數 ——
        # 判準與逐則理由寫在 `_evidence_footnote_items` 的 docstring。
        # `expanded=False` 是真的漸進揭露;`expanded=True` 那種空殼另有守衛禁止
        # (`tests/test_audit_20260810_tab1_shells.py`),本處刻意不用。
        with st.expander(_FOOTNOTE_EXPANDER_LABEL, expanded=False):
            st.caption("  \n".join(f"・{_f}" for _f in _hidden))
