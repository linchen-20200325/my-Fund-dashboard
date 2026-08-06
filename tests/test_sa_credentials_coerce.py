"""Service Account 憑證正規化(repositories/policy/_helpers.coerce_sa_credentials,v19.429)。

修 tab3 開場崩:`google_service_account` secret 存成 JSON **字串**(Streamlit TOML 表格吃不下
多行 private_key)→ 舊 `dict(_gsa_secret)` 丟 ValueError。改成 str→json.loads,fail-loud。
"""
import json

import pytest

from repositories.policy._helpers import (
    PolicySheetError,
    coerce_sa_credentials,
    get_gspread_client,
)

_SA = {"type": "service_account", "project_id": "p",
       "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
       "client_email": "x@x.iam.gserviceaccount.com"}


# ── coerce_sa_credentials ────────────────────────────────
def test_coerce_dict_passthrough():
    assert coerce_sa_credentials(dict(_SA)) == _SA


def test_coerce_json_string():
    assert coerce_sa_credentials(json.dumps(_SA)) == _SA          # 字串 → dict(核心修正)


def test_coerce_bad_string_raises():
    with pytest.raises(PolicySheetError) as e:
        coerce_sa_credentials("這不是 JSON")
    assert "JSON" in str(e.value)                                 # §1 可讀原因


def test_coerce_empty_string_raises():
    with pytest.raises(PolicySheetError):
        coerce_sa_credentials("   ")


def test_coerce_json_non_object_raises():
    with pytest.raises(PolicySheetError):
        coerce_sa_credentials("[1,2,3]")                          # 合法 JSON 但非物件


# ── get_gspread_client 前置檢查(不觸網,只到 client_email gate)──
def test_get_client_string_missing_client_email_raises():
    with pytest.raises(PolicySheetError) as e:
        get_gspread_client(json.dumps({"type": "service_account"}))   # 字串可解析但缺 email
    assert "client_email" in str(e.value)


def test_get_client_bad_string_raises_before_gspread():
    with pytest.raises(PolicySheetError) as e:
        get_gspread_client("not json at all")
    assert "JSON" in str(e.value)                                 # 在 coerce 就擋下,不進 gspread
