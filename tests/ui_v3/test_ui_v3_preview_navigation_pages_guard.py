# -*- coding: utf-8 -*-
"""守衛：`ui_v3/app_preview.py` 交給 `st.navigation` 的頁集合必須等於 `registry.registered_pages()`（多掛／少掛判紅）。"""
from __future__ import annotations

from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

import market_stubs as ms
import streamlit as st
from ui_v3.adapters import market_page as adapter
from ui_v3.shell.registry import registered_pages

APP = Path(__file__).resolve().parents[2] / "ui_v3" / "app_preview.py"


def _run(monkeypatch, source: str | None = None):
    captured = {}
    real_nav = st.navigation

    def spy(pages, *a, **k):
        captured["slugs"] = sorted(p.title for p in pages)
        return real_nav(pages, *a, **k)

    monkeypatch.setattr(st, "navigation", spy)
    monkeypatch.setattr(adapter, "load", lambda sources: (ms.view(key=ms.KEY), ms.table()))
    at = streamlit_testing.AppTest.from_string(source, default_timeout=60) if source else streamlit_testing.AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    return captured, at


def test_navigation_pages_equal_registry(monkeypatch):
    captured, at = _run(monkeypatch)
    assert not at.exception
    assert captured["slugs"] == sorted(p.title for p in registered_pages())


def test_negative_control_extra_page_turns_red(monkeypatch):
    mutant = APP.read_text(encoding="utf-8").replace(
        "navigation = st.navigation(list(st_pages.values())",
        "st_pages['zz'] = st.Page(lambda: None, title='zz', url_path='zz'); navigation = st.navigation(list(st_pages.values())",
    )
    assert "st_pages['zz']" in mutant
    captured, _ = _run(monkeypatch, mutant)
    assert captured["slugs"] != sorted(p.title for p in registered_pages())
