"""回歸：兩個 L2 masker 舊公開 API 與共用工廠同輸出、同錯誤。"""
from __future__ import annotations

import pytest

from services.v2_tables import alo_holdings, masking, settings_store


@pytest.mark.parametrize("factory", [masking.make_masker, alo_holdings.masker, settings_store.masker])
def test_reject_str_and_bytes_inputs(factory):
    for bad in ("token", b"token"):
        with pytest.raises(TypeError, match="secret_values 須為秘密值的清單"):
            factory(bad)


@pytest.mark.parametrize("factory", [masking.make_masker, alo_holdings.masker, settings_store.masker])
def test_callback_matches_direct_mask_and_freezes_input(factory):
    values = ["a-secret-123", "b-secret-456"]
    iterator = iter(values)
    callback = factory(iterator)
    text = "a-secret-123 / b-secret-456 / keep"
    assert callback(text) == masking.mask_message(text, values)
    assert callback(text) == masking.mask_message(text, values)
    assert next(iterator, None) is None


@pytest.mark.parametrize("factory", [masking.make_masker, alo_holdings.masker, settings_store.masker])
def test_nonstring_element_and_nonstring_message_keep_old_behavior(factory):
    callback = factory([None, "s3cr3t"])
    assert callback("s3cr3t remain") == masking.mask_message("s3cr3t remain", [None, "s3cr3t"])
    with pytest.raises(TypeError, match="mask_message 只收字串"):
        callback(None)
