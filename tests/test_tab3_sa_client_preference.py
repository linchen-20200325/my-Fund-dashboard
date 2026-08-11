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
    #
    # ⚠️ 2026-08-06:原斷言釘死 `get_gspread_client(dict(_gsa_secret))`。那個 `dict()`
    #    正是線上 ValueError 的來源 —— secrets 若把 service-account 寫成 JSON 字串,
    #    `dict("...")` 會在進入 get_gspread_client **之前**就炸,而 Streamlit Cloud 會把
    #    訊息整段遮蔽,使用者拿不到任何線索。形狀正規化已收進
    #    `repositories/policy/_helpers._coerce_sa_credentials`,呼叫端改直接傳原值。
    #    本條改釘「有沒有走 SA 分支」這個契約,不釘正規化寫在哪一層。
    assert "if _gsa_secret:" in txt and "get_gspread_client(_gsa_secret)" in txt, (
        "_t3_sheet_client 應優先 Service Account(if _gsa_secret → get_gspread_client)"
    )
    assert "get_gspread_client(dict(" not in txt, (
        "呼叫端又自己做 dict() 正規化了 —— secrets 是 JSON 字串時會在進入 "
        "get_gspread_client 前就拋 ValueError,且訊息會被 Streamlit Cloud 遮蔽"
    )


def test_tab3_sa_client_has_oauth_fallback_on_access_error():
    """v19.431:SA-first 仍在,但 SA 開不了『這張』sheet(403,非 429)且使用者已 OAuth
    登入 → 回退 user OAuth client。鎖住三要件:存取探測 open_by_key、quota 不回退、OAuth 回退。"""
    txt = _TAB3.read_text(encoding="utf-8")
    assert "_sa.open_by_key(" in txt, "SA 存取探測(open_by_key)不見了 → 無法偵測 403 回退"
    assert "is_quota_error" in txt or "_quota" in txt, "429 應與 403 區分(暫時性配額不得誤切 client)"
    assert "_t3_sa_can_open" in txt, "探測結果應本 session 快取(省配額,避免每次 rerun 重打)"


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
