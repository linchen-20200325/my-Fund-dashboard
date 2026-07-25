"""mcp_server/_serialize.py — L2 回傳正規化 + fail-loud error 信封(唯一實質新 code)。

兩個職責(對照設計 §6 失敗降級):
1. `to_json_safe(obj)`:把 L2 服務層的 dict/scalar/pandas/numpy 混合結構,遞迴轉成
   MCP protocol 傳得過去的 JSON-safe primitive(numpy → py、Timestamp → isoformat、
   NaN/inf → None、Series/DataFrame → dict/records、set → list)。
2. `error_envelope(fn, *args, **kwargs)`:把 L2 的 **fail-loud raise**(§1)攔成
   結構化 `{"ok": False, "error", "error_type"}`,而**不是**造假資料 —— §1 精神原封不動,
   只是把「炸掉」翻譯成 AI 讀得懂的錯誤訊息。成功則回 `{"ok": True, "data": <json-safe>}`。

純模組:不依賴 fastmcp、不依賴 streamlit,可獨立單元測試。
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import math
import sys
from typing import Any, Callable

import numpy as np
import pandas as pd


def to_json_safe(obj: Any) -> Any:
    """遞迴把任意 L2 回傳結構轉成 JSON-safe primitive。

    規則:
    - None / bool / str          → 原樣
    - int / numpy 整數           → int
    - float / numpy 浮點         → float(NaN / ±inf → None,§1 不偽造成 0)
    - pandas.Timestamp / datetime / date → ISO8601 字串
    - dict                        → key 轉 str,value 遞迴
    - list / tuple / set / ndarray→ list,元素遞迴
    - pandas.Series               → {str(index): 值}
    - pandas.DataFrame            → list[dict](records,index 併入 "_index")
    - 其他未知型別                → str(obj)(保底,永不炸)
    """
    # ── primitives ───────────────────────────────────────────────
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    # numpy 布林**不是** Python bool,須先攔(否則落到 int 分支變 0/1 或保底變 "True")
    if isinstance(obj, np.bool_):
        return bool(obj)
    # bool 必須先於 int 判斷(bool 是 int 子類);上面已擋掉 Python bool + numpy bool。
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        # NaN / inf 一律 None —— §1:寧可缺,不可偽造成 0 / 假數字
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    # ── 時間 ─────────────────────────────────────────────────────
    if isinstance(obj, (pd.Timestamp, _dt.datetime, _dt.date)):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    # ── pandas 容器 ──────────────────────────────────────────────
    if isinstance(obj, pd.Series):
        return {str(k): to_json_safe(v) for k, v in obj.to_dict().items()}
    if isinstance(obj, pd.DataFrame):
        out = []
        for idx, row in obj.iterrows():
            rec = {"_index": to_json_safe(idx)}
            rec.update({str(k): to_json_safe(v) for k, v in row.to_dict().items()})
            out.append(rec)
        return out
    # ── 集合 ─────────────────────────────────────────────────────
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, np.ndarray)):
        return [to_json_safe(v) for v in obj]
    # ── 保底 ─────────────────────────────────────────────────────
    return str(obj)


def error_envelope(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> dict:
    """執行 `fn` 並把結果包成統一信封;fail-loud raise → 結構化錯誤(§1)。

    成功:{"ok": True,  "data": <to_json_safe(回傳)>}
    失敗:{"ok": False, "error": <訊息>, "error_type": <例外類名>}

    §1 保留:L2 遇缺資料 / 全源失敗會 raise,這裡**不吞成假成功**,
    而是誠實把錯誤內容回給 AItool caller,讓對話端看得到「為什麼沒數字」。
    """
    try:
        # L1 fetcher 用 print() 印診斷(如 "[macro_core/PMI/...]")→ 落到 stdout。
        # stdio MCP 的 stdout **專供 JSON-RPC protocol frame**,任何雜訊都會毀掉協定。
        # 執行期間把 stdout 導向 stderr;FastMCP 的 protocol 在工具「回傳後」才寫,不受影響。
        with contextlib.redirect_stdout(sys.stderr):
            result = fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 — 邊界層:所有例外翻成結構化信封回報
        # §3.3:except 至少要 log + 回 fail token。stdio MCP 的 stdout 走協定,
        # log **必須**走 stderr,否則污染 protocol frame。
        print(f"[mcp_server] {type(e).__name__}: {e}", file=sys.stderr)
        return {"ok": False, "error": str(e), "error_type": type(e).__name__}
    return {"ok": True, "data": to_json_safe(result)}
