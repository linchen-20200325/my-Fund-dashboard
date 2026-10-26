# -*- coding: utf-8 -*-
"""F4（資安縱深）：五頁 `source.py` 的頁面層遮蔽，也要涵蓋個人 Google 登入權杖（`b_oauth.tokens`）。

只讀舊 `gsheet_tokens` 的話，個人 access／refresh token 若出現在錯誤文字裡會原樣上畫面。
來源一律經 L2 `services/v2_tables/masking`（ui_v2 不 import infra／shared）。
"""
from __future__ import annotations

import importlib
import pathlib
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

pytest.importorskip("pandas")
pytest.importorskip("streamlit")

from services.v2_tables import alo_holdings, masking  # noqa: E402
from shared.personal_oauth_keys import KEY_PENDING_LOGIN, KEY_TOKENS  # noqa: E402

_AT, _RT, _PAT = "personal-access-QQ-11", "personal-refresh-QQ-22", "pending-access-QQ-33"


@pytest.fixture(params=["hld", "alo", "exp", "mkt", "set"])
def source(request, monkeypatch):
    mod = importlib.import_module(f"ui_v2.{request.param}.source")
    state = {KEY_TOKENS: {"access_token": _AT, "refresh_token": _RT},
             KEY_PENDING_LOGIN: {"tokens": {"access_token": _PAT}}}
    monkeypatch.setattr(mod, "st", types.SimpleNamespace(secrets={}, session_state=state))
    return mod


def test_個人權杖進秘密值清單(source):
    assert {_AT, _RT, _PAT} <= set(source._secret_values())


def test_mask_error_遮掉個人權杖(source):
    if not hasattr(source, "mask_error"):
        pytest.skip("此頁沒有 mask_error")
    out = source.mask_error(f"取數失敗 {_AT} {_RT} {_PAT}")
    assert _AT not in out and _RT not in out and _PAT not in out
    assert masking.MASK in out


def test_masker_遮掉個人權杖(source):
    out = alo_holdings.masker(source._secret_values())(f"x {_AT} y {_RT}")
    assert _AT not in out and _RT not in out
