# -*- coding: utf-8 -*-
"""單檔基金查詢呈現元件｜隔離式 FAKE Preview 入口（非正式頁面、非正式資料）。

`streamlit run poc/fund_lookup_component_preview/app_fund_lookup_component_preview.py`

頁頂固定一列 FAKE 標示（屬 harness，不屬 renderer）。查詢流程：輸入 → `lookup_fund(FakeLoader, 輸入)`（adapter）→ ViewModel → renderer。
`session_state` 只存**經 adapter 淨化後的 ViewModel**（被安全攔截的輸入結構上沒有回顯），不存輸入原值。
不取數、不連線、不讀憑證、不寫任何東西；不接 registry／`app_preview`、不掛 🔍 頁。
"""
from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st  # noqa: E402

import fund_lookup_fake_inputs as fake  # noqa: E402
import fund_lookup_renderer as R  # noqa: E402
import fund_lookup_wording as W  # noqa: E402
from ui_v3.adapters.fund_lookup import lookup_fund, not_queried  # noqa: E402
from ui_v3.design import theme  # noqa: E402

KEY_MODE = "uvc_mode"
FAKE_BANNER = "FAKE／測試資料（離線注入，未執行任何真實請求）"
MODE_LABEL = "演示來源（harness）"
MODE_ADAPTER = "adapter"
MODE_CONFLICT = "conflict_direct"
MODES = {
    MODE_ADAPTER: "輸入代碼 → FakeLoader → adapter",
    MODE_CONFLICT: "CONFLICT 欄位：直接建構 ViewModel（現行 L2 不可達，非 adapter 結果）",
}


def main() -> None:
    border, text = theme.v("color.card.border"), theme.v("color.text.primary")
    st.markdown(
        f'<div data-harness="true" style="border:1px dashed {border};color:{text};padding:6px 10px;margin:0 0 6px 0;'
        f'font-size:{theme.v("type.caption")}">{R.safe(FAKE_BANNER)}<br>{R.safe(fake.HARNESS_CODES_HINT)}</div>',
        unsafe_allow_html=True)
    R.render_css()
    st.title(W.text("page_title"), anchor=False)
    raw = R.render_form()
    if raw is not None:
        st.session_state[R.KEY_VIEW] = lookup_fund(fake.make_loader(), raw)
    view = st.session_state.get(R.KEY_VIEW, not_queried())
    if st.session_state.get(KEY_MODE, MODE_ADAPTER) == MODE_CONFLICT:
        view = fake.conflict_view()
    R.render_card(view, fake=True)
    st.selectbox(MODE_LABEL, list(MODES), key=KEY_MODE, format_func=lambda m: MODES[m])


main()
