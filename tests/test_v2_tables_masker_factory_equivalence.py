"""回歸：兩個 L2 masker 舊公開 API 與共用工廠同輸出、同錯誤。"""
from __future__ import annotations

import secrets

import pytest

from services.v2_tables import alo_holdings, masking, settings_store


@pytest.mark.parametrize("factory", [masking.make_masker, alo_holdings.masker, settings_store.masker])
def test_reject_str_and_bytes_inputs(factory):
    token = secrets.token_hex(16)
    for bad in (token, token.encode()):
        with pytest.raises(TypeError, match="secret_values 須為秘密值的清單"):
            factory(bad)


@pytest.mark.parametrize("factory", [masking.make_masker, alo_holdings.masker, settings_store.masker])
def test_callback_matches_direct_mask_and_freezes_input(factory):
    values = [secrets.token_hex(16), secrets.token_hex(16)]
    iterator = iter(values)
    callback = factory(iterator)
    text = f"{values[0]} / {values[1]} / keep"
    assert callback(text) == masking.mask_message(text, values)
    assert callback(text) == masking.mask_message(text, values)
    assert next(iterator, None) is None


@pytest.mark.parametrize("factory", [masking.make_masker, alo_holdings.masker, settings_store.masker])
def test_nonstring_element_and_nonstring_message_keep_old_behavior(factory):
    secret = secrets.token_hex(16)
    callback = factory([None, secret])
    text = f"{secret} remain"
    assert callback(text) == masking.mask_message(text, [None, secret])
    with pytest.raises(TypeError, match="mask_message 只收字串"):
        callback(None)


@pytest.mark.parametrize("module", [alo_holdings, settings_store])
def test_wrapper_keeps_module_render_binding_and_dynamic_lookup(module, monkeypatch):
    assert module.mask_message is masking.mask_message
    secret = secrets.token_hex(16)
    callback = module.masker([secret])
    calls = []

    def replacement(message, values):
        calls.append((message, values))
        return "replacement"

    monkeypatch.setattr(module, "mask_message", replacement)
    assert callback("message") == "replacement"
    assert calls == [("message", [secret])]
    assert module.masker([secret])("later") == "replacement"
    assert calls[-1] == ("later", [secret])


def test_factory_default_keeps_masking_module_dynamic_lookup(monkeypatch):
    secret = secrets.token_hex(16)
    callback = masking.make_masker([secret])
    calls = []

    def replacement(message, values):
        calls.append((message, values))
        return "replacement"

    monkeypatch.setattr(masking, "mask_message", replacement)
    assert callback("message") == "replacement"
    assert calls == [("message", [secret])]
