"""v19.302 回歸網 — Tab3 政策 Sheet client 必須優先 Service Account。

背景(user 2026-07-03 三帳號纏鬥):
- 登入 GitHub / Streamlit Cloud = `帳號A`
- Google Sheet 擁有者 = `帳號B`
- app 內按「用 Google 登入」→ Google 認證 帳號B → 導回 *.streamlit.app →
  Streamlit Cloud 平台自身登入看到 帳號A → 「You do not have access to this
  app or it does not exist」。這是「app 內 user OAuth」與「Streamlit Cloud 平台
  登入」的先天衝突,redirect_uri / login_hint 都救不了。

修法(v19.302):`ui/tab3_portfolio.py` 政策 Sheet 的 gspread client 決策改成
**優先 Service Account**(headless、完全不需使用者登入 → 徹底避開帳號衝突),
只有沒設 `google_service_account` secret 時才退回 user OAuth。schema(v1/v2)
仍由各呼叫點 `oauth_mode=bool(_oauth_configured)` 決定,SA client 照樣讀 v2 sheet。

本測試以原始碼檢查鎖住決策方向(不 import 模組,免依賴 streamlit stub),
防止之後有人改回舊的「`_oauth_configured` 優先」三元式,又讓 user 撞帳號。
"""
from __future__ import annotations

from pathlib import Path

_TAB3 = Path(__file__).resolve().parent.parent / "ui" / "tab3_portfolio.py"


def test_tab3_has_service_account_first_client_helper():
    txt = _TAB3.read_text(encoding="utf-8")
    # 1) 決策 SSOT helper 存在
    assert "def _t3_sheet_client():" in txt, (
        "v19.302 的 _t3_sheet_client()(SA 優先決策 SSOT)不見了"
    )
    # 2) helper 優先 SA:先判 _gsa_secret,有就走 Service Account client
    assert "if _gsa_secret:" in txt and "get_gspread_client(dict(_gsa_secret))" in txt, (
        "_t3_sheet_client 應優先 Service Account(if _gsa_secret → get_gspread_client)"
    )


def test_tab3_no_longer_prefers_oauth_over_service_account():
    txt = _TAB3.read_text(encoding="utf-8")
    # 舊「OAuth 優先」三元式不該再殘留在 client 決策點(這正是撞帳號根因)
    assert "_get_oauth_client() if _oauth_configured else" not in txt, (
        "偵測到舊的『OAuth 優先』client 決策——會讓 user 又撞 Streamlit Cloud 平台帳號,"
        "應走 v19.302 的 _t3_sheet_client()(SA 優先)"
    )


def test_tab3_sheet_id_falls_back_to_secret():
    """純 Service Account 使用者(設 POLICY_SHEET_ID secret、從不 OAuth 登入)
    的 _sheet_id_q 必須能從 _sheet_id_secret 補值,否則自動讀回/讀取鈕不出現。"""
    txt = _TAB3.read_text(encoding="utf-8")
    assert 'st.session_state.get("policy_sheet_id")\n                       or _sheet_id_secret' in txt \
        or ('policy_sheet_id") ' in txt and "or _sheet_id_secret" in txt), (
        "_sheet_id_q 應在 session 無 policy_sheet_id 時 fallback 到 _sheet_id_secret"
    )
