"""v19.65 I2：單一基金 ↔ 組合持倉 跨 Tab 聯動。

在 Tab2（單一基金）研究一檔基金時，讀 Tab3（組合基金）的 portfolio_funds
（session_state），顯示「此基金是否已在你的組合 / 佔多少權重」，避免重複
加碼、看清現有曝險。屬「跨 Tab 訊號聯動」系列（I1=總經→組合，I2=單檔↔組合）。

讀 session_state（Tab3 未載入組合 → portfolio_funds 為空 → 靜默不顯）：
  - portfolio_funds：list[{code, name, invest_twd, is_core, ...}]
"""
from __future__ import annotations

import streamlit as st

from services.format_helpers import fmt_twd
from shared.colors import GH_BG_PRIMARY, GH_FG_MUTED, GRAY_66, INFO_BLUE, TRAFFIC_GREEN, TRAFFIC_YELLOW


def _norm(s) -> str:
    return str(s or "").strip().upper()


def render_fund_portfolio_membership(session_state, fund_codes, fund_name="") -> None:
    """渲染單檔→組合持倉聯動提示（純顯示，零副作用，零新 IO）。

    fund_codes: 當前基金候選識別碼（full_key / fund_code 等），任一命中即算。
    fund_name:  當前基金名稱（fallback 比對用）。
    """
    _pf = session_state.get("portfolio_funds") or []
    if not isinstance(_pf, list) or not _pf:
        return  # 無組合 → 靜默，不打擾只用單檔功能的 user

    _wanted = {_norm(c) for c in (fund_codes or []) if _norm(c)}
    _nm = _norm(fund_name)

    _matched = None
    for _f in _pf:
        if not isinstance(_f, dict):
            continue
        _code = _norm(_f.get("code"))
        if (_code and _code in _wanted) or (_nm and _norm(_f.get("name")) == _nm):
            _matched = _f
            break

    _total = sum(float(_f.get("invest_twd", 0) or 0)
                 for _f in _pf if isinstance(_f, dict))
    _n = sum(1 for _f in _pf if isinstance(_f, dict))

    if _matched is not None:
        _amt = float(_matched.get("invest_twd", 0) or 0)
        # ⚠️ **二態，會把「使用者還沒決定」顯示成「衛星(積極)」**（已知限制，本批不修）。
        # Q8 批次二拿掉本檔下方那個捏造的 `"is_core": True` 之後，剛用「➕ 加入組合」
        # 加進來的基金在這個 chip 上會由「核心(穩健)」變成「衛星(積極)」——
        # **兩個都不是事實**，真相是「客戶還沒設定過」。
        # ⛔ 刻意不在本批修：要正確顯示就得在畫面上新增第三個狀態，
        # 那是版面／設計變更，依 `CLAUDE.md §-1.5.4` 必須先出線框草稿給客戶拍板。
        # 同型的二態限制也存在於 `ui/helpers/portfolio/allocation.py`
        # （未設定的金額併入衛星）—— 那一處本批的處置是**文案誠實揭露、行為不動**。
        # 已在 PR 描述具名回報，等總管裁決是否另開一批。
        _tag = "核心(穩健)" if _matched.get("is_core") else "衛星(積極)"
        if _total > 0 and _amt > 0:
            _w = _amt / _total * 100.0
            _msg = (f"✅ <b>此基金已在你的組合</b>：權重 <b style='color:{INFO_BLUE}'>"
                    f"{_w:.1f}%</b>（{fmt_twd(_amt)}）｜定位 {_tag}")
        else:
            _msg = (f"✅ <b>此基金已在你的組合</b>（共 {_n} 檔）｜定位 {_tag}"
                    f"<span style='color:{GRAY_66}'>（尚未填投資金額）</span>")
        _border = TRAFFIC_GREEN
        st.markdown(
            f"<div style='background:{GH_BG_PRIMARY};border-left:4px solid {_border};"
            f"border-radius:4px;padding:6px 12px;margin-bottom:8px;font-size:12px;"
            f"color:{GH_FG_MUTED};line-height:1.6'>🔗 {_msg}</div>",
            unsafe_allow_html=True,
        )
    else:
        # v19.297：未加入時除顯示提示外，同時提供快捷「加入組合」按鈕
        _msg = (f"➕ 此基金<b>尚未加入</b>你的組合（目前 {_n} 檔）")
        _border = TRAFFIC_YELLOW
        _add_code = next((_norm(c) for c in (fund_codes or []) if _norm(c)), "")
        _lnk_col, _btn_col = st.columns([3, 1])
        _lnk_col.markdown(
            f"<div style='background:{GH_BG_PRIMARY};border-left:4px solid {_border};"
            f"border-radius:4px;padding:6px 12px;margin-bottom:8px;font-size:12px;"
            f"color:{GH_FG_MUTED};line-height:1.6'>🔗 {_msg}</div>",
            unsafe_allow_html=True,
        )
        if _add_code:
            _btn_key = f"btn_add_to_pf_{_add_code}"
            if _btn_col.button("➕ 加入組合", key=_btn_key, use_container_width=True,
                               help="加入 Tab3 組合基金（加入後請至 Tab3 點「📡 載入」取得資料）"):
                _pf = session_state.get("portfolio_funds") or []
                # 防重複
                _already = any(_norm(_f.get("code")) == _add_code
                               for _f in _pf if isinstance(_f, dict))
                if not _already:
                    _pf.append({
                        "code": _add_code,
                        "name": fund_name or _add_code,
                        "loaded": False,
                        # ⛔ **這裡刻意沒有 `is_core`（有意識的移除,不是漏刪）。**
                        # 原本是 `"is_core": True,   # 預設核心,使用者可在 Tab3 調整`
                        # —— 一個**憑空捏造的級別**：使用者只是說「把這檔加進我的組合」,
                        # 從來沒有說過它是核心。而這個捏造值會被下一次「全部寫入」
                        # **寫回客戶的 Google Sheet**（`ui/helpers/cloud_io.py` 兩處寫回
                        # 都由 `is_core` 推出 `policy_tier` / `tier` 欄）。
                        #
                        # 在名稱猜測時代它看不出來 —— `ui/helpers/portfolio/load.py`
                        # 每次「📡 載入」都會用基金名稱關鍵字再猜一個值蓋掉它,
                        # 所以這個 `True` 只有在「加入後直接存檔、中間沒載入」時才會浮現。
                        # 實測（`origin/main` @ `9cbf0377`,科技型與配息型各一檔）：
                        #   加入 → 存檔（未載入）  → 兩檔都寫回 `core`   ← 本行造成的
                        #   加入 → 載入 → 存檔     → 科技型 `satellite` / 配息型 `core`
                        # 兩個值都不是客戶的值：**客戶根本沒設定過,正確答案是留白。**
                        #
                        # 少了這個鍵,**五處**寫回的三元式都會走到 `else ""` 分支
                        # ⇒ 寫回空字串 ⇒ 客戶 Sheet 上的空白保持空白
                        # （`CLAUDE.md §1` Fail Loud: 不知道就不要編一個值）。
                        #
                        # ⚠️ **2026 第二輪更正（有意識的更正,不是漏刪）**：本行原寫
                        # ~~「三處」~~。**結論不變（五處行為完全相同：缺鍵 → `""`）,
                        # 錯的只有計數。** 實測(AST 結構掃描 + 逐處把運算式取出來,
                        # 餵一個沒有 `is_core` 鍵的 dict 實際執行,五處輸出皆為 `""`)：
                        #   `ui/helpers/cloud_io.py`          — v2 `tier` 欄寫回
                        #   `ui/helpers/cloud_io.py`          — v1 `policy_tier` 欄寫回
                        #   `ui/tab3_portfolio.py`            — Tab3 批次加入寫回
                        #   `ui/tab3_t7_ledger.py`            — T7 套用起始部位寫回
                        #   `repositories/snapshot_repository.py` — 快照分頁寫回
                        # ⚠️ **第五處當初為什麼被漏掉（這比數字本身重要）**：本輪第一版
                        # 掃描要求運算式裡出現 `"core"` / `"satellite"` 兩個字面值,
                        # 而快照那一處用的是**中文** `"核心"` / `"衛星"` ——
                        # **字表選錯,那條掃描結構上就看不到它**,再跑一百次也一樣。
                        # 改成「只看結構(巢狀三元 + 測試式提到 `is_core` + `""` 兜底),
                        # 不看 tier 字面值」之後才掃到五處。
                        # ⚠️ **刻意不寫行號**：行號在任何一次重構後就失效,
                        # 而重構**不會**觸發本註解更新(`CLAUDE.md` §8.2.A.0 規則 1 同精神)。
                        "invest_twd": 0,
                    })
                    session_state["portfolio_funds"] = _pf
                    st.toast(f"✅ {fund_name or _add_code} 已加入組合，請至 Tab3 點「📡 載入」", icon="✅")
                    st.rerun()
                else:
                    st.toast(f"ℹ️ {fund_name or _add_code} 已在組合中", icon="ℹ️")
