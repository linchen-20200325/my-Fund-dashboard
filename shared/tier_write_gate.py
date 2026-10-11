"""shared/tier_write_gate.py — 「全部寫入」同代號多列級別的寫入閘門（L0・純函式・零 IO）。

客戶 2026-10-11 N1 裁示：

* 讀回時保留「該保單逐列級別快照」，只存在 session，不新增 Sheet 欄位（`snapshot_from_policies_df`）。
* 寫入前 Sheet 與可靠快照**逐項相等** → 正常處理（讀回後原樣的 [核心, 衛星, 留白] 必須通過，
  留白維持留白，不得被填成任何級別）。
* Sheet 已改，或 JSON restore／其他情況沒有可靠快照 → 同代號多列只要級別不完全一致
  （含「已設定＋留白」）就 fail closed，該保單整張不寫。
* 系統不認得的級別字串（例：[核心資產, 核心資產]）一律 fail closed，不因兩列相同放行。
* 新增同基金第二筆持倉但未設級別 → 維持留白。

⛔ 「逐項相等」是**比對**，不是**配對**：本模組從不拿快照／Sheet 的第 k 格去對應 session 的第 k 列，
也不看金額；快照只回答一個問題 ——「Sheet 現在的該代號級別序列，與讀回當下是否完全一樣」。
通過時寫出的是 session 自己的值（留白就是留白），所以不可能把別列的級別搬過來。

快照只代表**讀回當下的 Sheet**，與 session 內使用者之後的編輯（df）是兩回事；比對的是語意序列
（`""`／`core`／`satellite`／`?`），所以「核心」與「core」拼法不同不算 Sheet 被改。

只處理「同代號出現 ≥2 列、且其中有未設定列」的群組（`needs_gate`）；其他情形維持
`write_policy_v2(keep_sheet_tier=True)` 原有行為，不經本模組。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence

from shared.policy_tier import merge_sheet_tier, normalize_tier

#: session_state 中放讀回快照的鍵。值：{保單 id: {代號鍵: [語意級別, ...]}}（Sheet 列序）。
SNAPSHOT_SESSION_KEY = "_tier_readback_snapshot"

#: 非空白、但系統認不得的級別字串（例：「核心資產」）。
UNRECOGNIZED = "?"


def code_key(code: Any) -> str:
    """代號比對鍵：去空白、大寫；純數字再去前導零。

    快照來自 `get_all_records`（gspread 會把 "0050" 數字化成 50），寫入前重讀用
    `get_all_values`（保留 "0050"）—— 兩邊必須用同一把尺，否則數字代號會誤判成「Sheet 已改」。
    """
    s = str(code if code is not None else "").strip().upper()
    return (s.lstrip("0") or "0") if s.isdigit() else s


def level_of(raw: Any) -> str:
    """Sheet 級別格 → 語意：`""`（未設定）／`core`／`satellite`／`UNRECOGNIZED`。"""
    if raw is None or (isinstance(raw, float) and raw != raw):
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    return normalize_tier(s) or UNRECOGNIZED


def snapshot_from_policies_df(df: Any) -> dict:
    """讀回後的 `policies_df`（v2：policy_id／fund_code／tier，Sheet 列序）→ 逐列級別快照。

    欄位不齊（例如 v1 讀回）、或不是 DataFrame → `{}`（＝沒有可靠快照）。
    """
    try:
        cols = set(df.columns)
        if not {"policy_id", "fund_code", "tier"} <= cols:
            return {}
        triples = zip(df["policy_id"].tolist(), df["fund_code"].tolist(), df["tier"].tolist())
    except Exception:  # noqa: BLE001 — 認不得的輸入一律當作沒有快照，不猜
        return {}
    out: dict = {}
    for pid, code, tier in triples:
        p, k = str(pid if pid is not None else "").strip(), code_key(code)
        if not p or not k:
            continue
        out.setdefault(p, {}).setdefault(k, []).append(level_of(tier))
    return out


def capture_snapshot(ss: Any) -> None:
    """全部讀回成功後呼叫：以此刻的 `policies_df` 重建快照（覆蓋舊的）。"""
    ss[SNAPSHOT_SESSION_KEY] = snapshot_from_policies_df(ss.get("policies_df"))


def invalidate_snapshot(ss: Any) -> None:
    """JSON 還原後呼叫：快照作廢（session 級別已不是讀回當下的，由備份蓋掉）。

    冪等 —— 上傳檔案留在畫面上時每次重跑都會再還原一次，這裡也就再作廢一次；
    只有下一次成功的「全部讀回」（`capture_snapshot`）才會重新建立。
    """
    try:
        ss.pop(SNAPSHOT_SESSION_KEY, None)
    except Exception:  # noqa: BLE001
        pass


def snapshot_for_policy(ss: Any, policy_id: Any) -> Optional[dict]:
    """取某保單的快照 `{代號鍵: [語意級別, ...]}`；沒有快照（含已作廢）→ `None`。"""
    snap = ss.get(SNAPSHOT_SESSION_KEY) if hasattr(ss, "get") else None
    if not isinstance(snap, Mapping):
        return None
    got = snap.get(str(policy_id if policy_id is not None else "").strip())
    return got if isinstance(got, Mapping) else None


def _is_unset(tier: Any) -> bool:
    return normalize_tier(tier) is None


def needs_gate(codes: Sequence[Any], tiers: Sequence[Any]) -> bool:
    """session 這張保單是否有「同代號 ≥2 列、且其中有未設定列」。沒有 → 不必讀 Sheet、不經本閘門。"""
    seen: dict = {}
    for c, t in zip(codes, tiers):
        k = str(c if c is not None else "").strip().upper()
        if not k:
            continue
        n, unset = seen.get(k, (0, False))
        seen[k] = (n + 1, unset or _is_unset(t))
    return any(n >= 2 and unset for n, unset in seen.values())


@dataclass(frozen=True)
class GateResult:
    #: 衝突代號（session 內首次出現序、顯示用原樣）。非空 → 呼叫端整張保單不寫。
    conflicts: tuple = ()
    #: True ＝ 有群組靠「快照一致」放行：呼叫端必須以 `tiers` 為最終級別欄、
    #: 用 `keep_sheet_tier=False` 寫入（`write_policy_v2(keep_sheet_tier=True)` 看不到快照，
    #: 會對 [核心, 衛星, 留白] 誤判衝突）。False ＝ 不經快照，維持原本 keep_sheet_tier=True。
    uses_snapshot: bool = False
    #: 每一列最終要寫的級別字串（依 session 列序）。
    tiers: tuple = ()


def evaluate_tier_gate(
    codes: Sequence[Any],
    tiers: Sequence[Any],
    sheet_by_code: Mapping[str, Sequence[Any]],
    snapshot: Optional[Mapping[str, Sequence[str]]],
    multi_plan: Callable[[list, list], Optional[list]],
) -> GateResult:
    """決定這張保單能不能寫、以及（靠快照放行時）每列該寫什麼。

    Parameters
    ----------
    codes / tiers   session 這張保單每一列的代號與級別字串（`""`／`core`／`satellite`）。
    sheet_by_code   寫入前**剛重讀**的 Sheet：{代號(大寫): [該代號每一列級別格的原字串]}（Sheet 列序）。
    snapshot        `snapshot_for_policy` 的回傳（`None` ＝ 沒有可靠快照）。
    multi_plan      既有的 `repositories.policy.v2._multi_row_tier_out`，由呼叫端注入
                    （L0 不得 import L1）。用在：不需要快照的多列群組、以及「Sheet 級別完全一致」的群組。
    """
    groups: dict = {}
    for i, c in enumerate(codes):
        k = str(c if c is not None else "").strip().upper()
        if not k:
            continue
        groups.setdefault(k, []).append(i)

    out = [str(t if t is not None else "") for t in tiers]
    conflicts: list = []
    uses_snapshot = False
    for k, idxs in groups.items():
        sheet = list(sheet_by_code.get(k, []))
        if not sheet:
            continue                      # Sheet 沒有這個代號（新持倉）：寫 session 值，留白就是留白
        grp = [out[i] for i in idxs]
        disp = str(codes[idxs[0]]).strip()
        if len(sheet) == 1 and len(grp) == 1:
            out[idxs[0]] = merge_sheet_tier(grp[0], sheet[0])   # 單列代號：行為不變
            continue
        if len(grp) >= 2 and any(_is_unset(t) for t in grp):
            levels = [level_of(r) for r in sheet]
            if UNRECOGNIZED in levels:
                conflicts.append(disp)    # 認不得的字串：一律擋，不因兩列相同放行
                continue
            if len(set(levels)) > 1:
                # Sheet 級別不完全一致（含「已設定＋留白」）：只有「與讀回快照逐項相等」才放行。
                # 逐項相等 ＝ 比對整條序列是否一樣；不做第 k 格對第 k 列的配對。
                snap = (snapshot or {}).get(code_key(k))
                if snap is not None and list(snap) == levels:
                    uses_snapshot = True   # 放行：寫 session 自己的值（grp 原樣），留白不填
                else:
                    conflicts.append(disp)
                continue
        plan = multi_plan(grp, sheet)      # 其餘多列群組：沿用 v2 既有判定
        if plan is None:
            conflicts.append(disp)
        else:
            for i, v in zip(idxs, plan):
                out[i] = v
    return GateResult(conflicts=tuple(conflicts), uses_snapshot=uses_snapshot, tiers=tuple(out))
