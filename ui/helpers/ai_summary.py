"""ai_summary.py — 各 Tab 通用「AI 白話總體檢」widget（v18.214 改版）。

設計原則（呼應 CLAUDE.md §2 §4）：
- 純 UI 層：呼叫 services/ai_prompts.build_structured_summary_prompt
  + services/ai_service._gemini
- 單一「結構化完整摘要」：吃該 Tab 全章節快照，逐章節給白話結論 + 時事，
  取代 v18.159 的「4 視角散文 selectbox」（已不符合「逐章節結論」需求）。
- caller 只負責組裝 snapshot 字串 + 章節清單 + 新聞 headlines。
- key 命名空間隔離：caller 傳 tab_key（如 "tab2"），避免多 Tab widget key 衝突。
- 結果存 session_state[f"{tab_key}_ai_struct"]，重整頁面不重打 API。
- 2026-08-10：本 widget 原本整段包在摺疊容器內（Tab① 還傳 `expanded=True`）。
  那層殼對揭露零貢獻 —— 傳 True 時它從一開始就是開的、從沒擋住任何東西，
  只多印一次標題並留下一個誤點就把 AI 結果收起來的把手；傳 False 時則是把
  「已經花了 10-20 秒生成、且已落地磁碟」的結論預設藏起來。改成
  `st.markdown("#### …")` + `st.container()`（本 repo 既有 pattern），
  標題保留在本模組內 —— 四個 caller 中有一個（Tab③）沒有自己的區塊標題，
  標題若下放給 caller，那一個會變成沒有名字的一坨按鈕。

使用範例：
    from ui.helpers.ai_summary import render_ai_summary_widget
    render_ai_summary_widget(
        tab_key="tab2",
        tab_label="單一基金（00878）",
        snapshot=_snap_text,
        sections=["基本資料", "績效表現", "風險指標", "配息", "新聞時事"],
        headlines=session_state.get("news_titles", []),
        gemini_api_key=GEMINI_KEY,
    )
"""
from __future__ import annotations
from typing import Optional

import streamlit as st

from ui.helpers.render_state import not_ready

from services.ai_prompts import build_structured_summary_prompt


def render_ai_summary_widget(
    *,
    tab_key: str,
    tab_label: str,
    snapshot: str,
    sections: Optional[list[str]] = None,
    headlines: Optional[list[str]] = None,
    stale_note: str = "",
    gemini_api_key: str = "",
) -> None:
    """在 Tab 末尾掛一個「AI 白話總體檢」區塊（逐章節結論 + 時事）。

    tab_key:        widget key 命名空間（如 "tab2" / "tab3"）
    tab_label:      中文 label，傳給 AI 知道「在分析哪個 Tab」
    snapshot:       已格式化的「全章節」資料快照字串
    sections:       該 Tab 章節名稱清單（依顯示順序），AI 逐節各給一段
    headlines:      近期新聞標題，用於每節「最近新聞影響」
    stale_note:     資料新鮮度註記，可空
    gemini_api_key: secrets["GEMINI_KEY"]

    內容不再包在任何可收合容器內（見 module docstring）。`st.container()`
    只提供版面分界，不可收合。
    """
    st.markdown(f"#### 🤖 AI 白話總體檢（{tab_label}）")
    with st.container():
        if not snapshot or not snapshot.strip():
            st.caption("⚠️ 本 Tab 暫無可分析的快照資料（資料尚未載入）。")
            return

        st.caption("把這個 Tab 的所有資料交給 AI，逐段用白話講「現在是好是壞、跟最近新聞有沒有關係、下一步怎麼做」。")
        _cache_key = f"{tab_key}_ai_struct"
        _cached = st.session_state.get(_cache_key)

        # v19.410:磁碟後盾 —— session_state 被 reboot 清空後,若磁碟有「同一份 snapshot」
        # 的 AI 結果就讀回(keyed by tab+snapshot hash;資料變了 → key 變 → miss → 重生成,
        # 不回顯過期 AI)。修「reboot 後各 Tab AI 總結都不見了」。
        from repositories import ai_cache  # noqa: PLC0415
        # key 須涵蓋所有「餵給 AI 的輸入」:snapshot + 新聞標題 + stale 註記。否則
        # 「snapshot 同、新聞已更新」會命中同 key → 回顯分析舊新聞的舊 AI(對抗式驗證發現)。
        _key_material = "\n---\n".join([
            snapshot,
            "\n".join(str(h) for h in (headlines or [])),
            stale_note or "",
        ])
        _disk_key = ai_cache.make_key(tab_key, _key_material)
        _from_disk = False
        if not _cached:
            _cached = ai_cache.load(_disk_key)
            if _cached:
                st.session_state[_cache_key] = _cached
                _from_disk = True

        _btn_label = "🔄 重新生成" if _cached else "▶️ 生成白話總體檢"
        run = st.button(_btn_label, key=f"{tab_key}_ai_run",
                        use_container_width=True, type="primary")

        # 延遲 import：ai_service 重，避免 module import 時拖慢 Streamlit cold start
        from services.ai_service import gemini_generate, get_gemini_keys  # noqa: PLC0415
        # v18.217：多 key 自動輪替 —— 傳入的 key 優先，其餘從 secrets/env 池補上
        _pool = get_gemini_keys()
        if gemini_api_key and gemini_api_key not in _pool:
            _pool = [gemini_api_key, *_pool]
        _n_keys = len(_pool)

        if run:
            if not _pool:
                not_ready("未設定 Gemini API Key，無法呼叫 AI",
                          where="Streamlit Cloud → Settings → Secrets 的 `GEMINI_API_KEY`")
                return
            prompt = build_structured_summary_prompt(
                tab_label=tab_label, snapshot=snapshot,
                sections=sections or [], headlines=headlines or [],
                stale_note=stale_note,
            )
            # round-robin 起點：跨 Tab 共用 cursor，分散多把 key 的負載（即使沒撞 429）
            _cur = int(st.session_state.get("_gemini_key_cursor", 0))
            with st.spinner("🤖 AI 正在逐段體檢（約 10-20 秒）..."):
                try:
                    _cached = gemini_generate(
                        prompt, max_tokens=3500,
                        keys=_pool, start=_cur % _n_keys,
                    )
                except Exception as e:
                    st.error(f"❌ AI 呼叫失敗：[{type(e).__name__}] {e}")
                    return
            st.session_state["_gemini_key_cursor"] = (_cur + 1) % _n_keys
            st.session_state[_cache_key] = _cached
            # v19.410:落地磁碟 → reboot 後同一份資料的 AI 可直接讀回(§1:寫失敗只降級,不炸)
            try:
                ai_cache.save(_disk_key, _cached)
            except Exception as _e_save:  # noqa: BLE001
                print(f"[ai_cache] 落地失敗(改只記憶體):{type(_e_save).__name__}: {_e_save}")

        if not _cached:
            return

        if _from_disk:
            st.caption("💾 這份 AI 總結由磁碟續存讀回(reboot 前生成)。資料有更新請按「🔄 重新生成」。")
        st.markdown(_cached)
        _n_sec = len([s for s in (sections or []) if str(s).strip()])
        _key_note = f"{_n_keys} 把 key 輪替" if _n_keys > 1 else "Gemini"
        st.caption(
            f"💡 模型：{_key_note}　｜ 章節：{_n_sec} 節　"
            f"｜ 快照長度：{len(snapshot)} chars　｜ 結果已暫存，重整頁面不會重打 API"
        )
