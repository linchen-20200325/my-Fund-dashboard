"""infra/config.py — 跨層 secret / config 讀取(v19.197 P1-2)

ARCHITECTURE_AUDIT V3+V4 修補。services 層需讀 Google service account /
sheet_id 等 secrets,但 §8.2 規範 L2 service 不得直接 import streamlit。
本檔做 thin wrapper,讓 service 不感知 secret 載體(streamlit secrets vs env var)。

infra/ 是 L0,允許 `try: import streamlit`(EX-CACHE-1 同精神 — 跨層 IO 邊界)。

公開 API:
- `get_secret(key, default=None)`:soft get,缺失回 default
- `require_secret(key)`:strict get,缺失 raise(§1 Fail Loud)
- `is_streamlit_context()`:偵測是否在 streamlit runtime
"""
from __future__ import annotations

import os
from typing import Any


def is_streamlit_context() -> bool:
    """偵測是否在 streamlit runtime context 內。"""
    try:
        import streamlit as st  # noqa: F401
        return True
    except Exception:
        return False


def get_secret(key: str, default: Any = None) -> Any:
    """取得 secret 值;Streamlit 環境走 `st.secrets`,否則 fallback `os.environ`。

    Args:
        key: secret 名稱(如 'google_service_account' / 'FRED_API_KEY')
        default: 找不到時的回傳值

    Returns:
        secret 值(dict / str / None 等),或 default
    """
    try:
        import streamlit as st
        # st.secrets 提供 dict-like .get();不存在 key 回 default
        v = st.secrets.get(key, None)
        if v is not None:
            return v
    except Exception:
        # streamlit 不可用 / secrets.toml 缺失 → 走 env var fallback
        pass
    return os.environ.get(key, default)


def require_secret(key: str) -> Any:
    """強制取得 secret;缺少 / 為空 → raise KeyError(§1 Fail Loud)。

    用於業務必要 config(如 Google Sheet ID),缺少表示部署有問題,
    不該靜默走 fallback path。
    """
    v = get_secret(key, None)
    if v is None:
        raise KeyError(f"Missing required secret: {key!r}")
    if isinstance(v, dict) and not v:
        raise KeyError(f"Required secret is empty dict: {key!r}")
    if isinstance(v, str) and not v.strip():
        raise KeyError(f"Required secret is empty string: {key!r}")
    return v
