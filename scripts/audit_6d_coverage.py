#!/usr/bin/env python3
"""6D 擴充前的資料覆蓋率盤點（Layer 3-B，2026-08-14）。

**這支腳本的用途是回答一個決策問題，不是產生報表：**
「費用規模」與「匯率風險」這兩個想加進健康度評分的新維度，
在你實際持有的基金上到底有幾檔拿得到資料？

為什麼要先問這個
================
現行 4D 已經有 `GRADE_4D_MIN_FACTORS = 2` —— 只要湊得出 2 個面向就給等第。
分母變成 6 之後，如果新加的兩維有九成留白，結果會是
**「看起來更全面、實際更脆弱」**：一個 2/6 撐起來的 A 和一個 6/6 的 A
在表上長得一模一樣。所以動工前先量，量出來太低就不要做（§-1）。

用法
====
    # 1) 直接給代號
    python scripts/audit_6d_coverage.py ACCP138 ACUSI23 TLZF9

    # 2) 從最近一次批次分析的存檔讀代號（要先在「📦 批次分析」跑過一輪）
    python scripts/audit_6d_coverage.py --from-checkpoint

    # 3) 從純文字檔讀（一行一個代號；可從批次分析的 CSV 貼出來）
    python scripts/audit_6d_coverage.py --from-file my_codes.txt

輸出說明
========
逐檔列出三個欄位的實際值與來源，最後給每一維的命中率與**建議**。
`--from-checkpoint` 只讀磁碟不打網路，適合先看個大概；
真要下決策請用代號模式重抓（存檔可能是舊 schema）。

§1：抓不到就是抓不到，本腳本不填任何預設值、不估算。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── 繁中 Windows 必要：強制 stdout/stderr 走 UTF-8 ────────────────────────
# 本腳本印中文與 emoji（✅ ❌ ⬜）。Python 在 Windows 上寫入**被重導向的**
# stdout 時用 `locale.getpreferredencoding()` = cp950，遇到 emoji 直接
# `UnicodeEncodeError` —— 而且是**在印錯誤訊息的那一行**炸掉，
# 於是使用者看到的是一個編碼錯誤的 traceback，看不到真正的原因
# （例如「找不到 codes.txt」）。同一個陷阱在 `tests/test_undefined_name_scan.py`
# 也踩過一次（那裡是讀 ruff 的 UTF-8 輸出）。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass   # 舊 Python 或已被包裝過 → 維持原樣，最壞情況是 emoji 變 ?


# ── 三個維度各自的「有沒有拿到」判定 ────────────────────────────────────
def _probe_expense(fd: dict) -> tuple:
    """費用率：走 production 同一條 4 層 fallback，不自己另算(§2.1 SSOT)。

    回 (value_pct | None, source_label)。source 直接反映走到第幾層，
    這比「有沒有值」更重要 —— 全靠估計值撐起來的一維，
    拿去給 A/B 等第打分是另一種造假。
    """
    from shared.converters import safe_num as _num
    _mj = fd.get("moneydj_raw") or fd
    # 1) 官方揭露 TER
    for _cand, _src in (
        (fd.get("expense_ratio"), "FundClear 揭露 TER"),
        (_mj.get("total_expense_ratio"), "MoneyDJ 總費用率"),
    ):
        _v = _num(str(_cand).replace("%", "").strip() if _cand else None)
        if _v is not None and 0 < _v <= 10:
            return _v, _src
    # 2) 經理 + 保管兩費相加
    _mgmt = _num(str(_mj.get("mgmt_fee", "")).replace("%", "").strip() or None)
    _cust = _num(str(_mj.get("custody_fee", "")).replace("%", "").strip() or None)
    if _mgmt is not None and _cust is not None:
        return _mgmt + _cust, "估計（經理+保管）"
    if _mgmt is not None:
        return _mgmt, "估計（僅經理費）"
    return None, "—"


def _probe_scale(fd: dict) -> tuple:
    """基金規模：`fund_scale` 目前**全站 0 consumer**，先看抓不抓得到。

    ⚠️ 這欄是**字串**（例：「1,234.56 百萬美元」/「新台幣 56.7 億」）。
    跨檔比大小之前必須先解析數字、判斷單位（百萬/億）、再換算成同一個幣別
    —— 三段都可能失敗，而且失敗方式是「解析成一個小 20 倍的數字」而不是報錯。
    所以本欄的覆蓋率要分兩層看：**抓到字串**vs**解析得出可比較的數字**。
    """
    _mj = fd.get("moneydj_raw") or fd
    _raw = str(_mj.get("fund_scale") or "").strip()
    if not _raw:
        return None, "—", ""
    # 只做最基本的「像不像數字」判斷，不在這裡實作換算（那是真要做 6D 時的工作）
    import re
    _m = re.search(r"[\d,]+\.?\d*", _raw)
    _num_ok = bool(_m)
    _unit_hint = ""
    for _u in ("百萬", "億", "萬", "million", "bn", "M"):
        if _u in _raw:
            _unit_hint = _u
            break
    _ccy_hint = ""
    for _c in ("美元", "台幣", "新台幣", "歐元", "日圓", "USD", "TWD", "EUR", "JPY"):
        if _c in _raw:
            _ccy_hint = _c
            break
    _status = ("可解析" if (_num_ok and _unit_hint and _ccy_hint)
               else "抓到但缺單位或幣別" if _num_ok else "抓到但不含數字")
    return _raw, _status, f"{_unit_hint}/{_ccy_hint}"


def _probe_fx_risk(fd: dict) -> tuple:
    """匯率風險：台幣計價的基金**本來就沒有匯率風險**（不是缺資料）。

    這一維的「留白」有兩種完全不同的意思，混在一起算覆蓋率會失真：
      - TWD 基金 → 不適用（N/A），評分時應該把它從分母拿掉而不是扣分
      - 外幣基金但抓不到匯率序列 → 真的缺資料
    """
    _ccy = str(fd.get("currency") or (fd.get("moneydj_raw") or {}).get("currency")
               or "").strip().upper()
    if not _ccy:
        return None, "⬜ 幣別未知"
    if _ccy in ("TWD", "台幣", "新台幣"):
        return "TWD", "N/A（台幣計價，無匯率風險）"
    try:
        from services.fund_service import get_latest_fx
        _fx = get_latest_fx(f"{_ccy}TWD=X")
    except Exception as _e:  # noqa: BLE001
        return _ccy, f"⬜ 匯率查詢失敗（{type(_e).__name__}）"
    return _ccy, ("可算" if (_fx and _fx > 0) else "⬜ 抓不到匯率")


# ── 取得要盤點的基金 ────────────────────────────────────────────────────
def _codes_from_checkpoint() -> list:
    from repositories import batch_checkpoint as bc
    _recent = bc.list_recent(limit=1)
    if not _recent:
        print("❌ 找不到任何批次分析存檔（data_cache/batch/）。\n"
              "   改用以下任一種：\n"
              "     python scripts/audit_6d_coverage.py ACCP138 ACUSI23 …\n"
              "     python scripts/audit_6d_coverage.py --from-file codes.txt")
        return []
    _run = _recent[0]
    _data = bc.load(_run["run_id"])
    if not _data:
        print("❌ 存檔讀不回來。")
        return []
    print(f"（讀存檔 {_run['run_id']}，{_run['n_done']}/{_run['n_codes']} 檔，"
          f"更新於 {_run['updated_at']}）")
    return list(_data.get("codes") or [])


def _codes_from_file(path: str) -> list:
    """一行一個代號的純文字檔。容忍「ACCP138,基金名稱」這種貼上格式（取第一段）。

    刻意**不**做 Google Sheet 政策讀取：那需要 OAuth client + sheet_id，
    在單機腳本裡重建一次登入流程等於把 UI 的邏輯抄第二份（§8.1 step 6）。
    要盤點全部持倉，最省事的路是先在「📦 批次分析」跑一輪再用 --from-checkpoint。
    """
    _p = Path(path)
    if not _p.exists():
        print(f"❌ 找不到檔案：{_p.resolve()}\n"
              "   建立方式（PowerShell，一行一個代號）：\n"
              '     @("ACCP138","ACUSI23","TLZF9") | Set-Content -Encoding utf8 codes.txt\n'
              "   或直接把代號當參數傳：\n"
              "     python scripts/audit_6d_coverage.py ACCP138 ACUSI23 TLZF9")
        return []
    _codes: list = []
    for _ln in _p.read_text(encoding="utf-8-sig").splitlines():
        _t = _ln.strip().replace("\t", ",").split(",")[0].strip().upper()
        if _t and _t not in _codes and _t not in ("CODE", "代號", "基金代號"):
            _codes.append(_t)
    return _codes


def main() -> int:
    ap = argparse.ArgumentParser(description="6D 新維度資料覆蓋率盤點")
    ap.add_argument("codes", nargs="*", help="基金代號（空白分隔）")
    ap.add_argument("--from-checkpoint", action="store_true",
                    help="從最近一次批次分析存檔取代號")
    ap.add_argument("--from-file", metavar="PATH",
                    help="從純文字檔取代號（一行一個）")
    args = ap.parse_args()

    codes = [c.strip().upper() for c in args.codes if c.strip()]
    if args.from_checkpoint:
        codes = _codes_from_checkpoint()
    elif args.from_file:
        codes = _codes_from_file(args.from_file)
    if not codes:
        ap.print_help()
        return 1

    print(f"\n{'=' * 78}")
    print(f"6D 新維度資料覆蓋率盤點 — {len(codes)} 檔")
    print(f"{'=' * 78}\n")

    from services.moneydj_fetcher import auto_fetch_moneydj

    _n_exp_real = _n_exp_est = 0
    _n_scale_parsable = _n_scale_raw = 0
    _n_fx_ok = _n_fx_na = 0
    _n_fetch_fail = 0
    # 稽核用:蒐集「基金規模」的原始字串。覆蓋率只回答「有沒有」,
    # 但真正決定能不能做的是**格式一不一致** —— 「1,234.56 百萬美元」與
    # 「新台幣 56.7 億」差 100 倍,而解析錯的時候不會報錯,
    # 只會安靜地給出一個小 20 倍的數字(§4.1 量綱陷阱)。
    _scale_samples: list = []

    for _i, _code in enumerate(codes, 1):
        print(f"[{_i}/{len(codes)}] {_code}")
        try:
            fd = auto_fetch_moneydj(_code)
        except Exception as _e:  # noqa: BLE001
            print(f"    ❌ 抓取失敗：{type(_e).__name__}: {_e}\n")
            _n_fetch_fail += 1
            continue
        if fd.get("error"):
            print(f"    ❌ {fd['error']}\n")
            _n_fetch_fail += 1
            continue

        _ev, _esrc = _probe_expense(fd)
        if _ev is not None:
            if _esrc.startswith("估計"):
                _n_exp_est += 1
            else:
                _n_exp_real += 1
        print(f"    費用率　：{_ev if _ev is not None else '⬜ 無'}"
              f"{f' %  ({_esrc})' if _ev is not None else ''}")

        _sv, _sstat, _shint = _probe_scale(fd)
        if _sv:
            _n_scale_raw += 1
            if _sstat == "可解析":
                _n_scale_parsable += 1
        _scale_samples.append((_code, _sv or "", _sstat))
        print(f"    基金規模：{_sv or '⬜ 無'}　[{_sstat}]"
              f"{f' 單位/幣別線索={_shint}' if _shint else ''}")

        _fv, _fstat = _probe_fx_risk(fd)
        if _fstat == "可算":
            _n_fx_ok += 1
        elif _fstat.startswith("N/A"):
            _n_fx_na += 1
        print(f"    匯率風險：{_fv or '⬜'}　[{_fstat}]\n")

    _n = len(codes) - _n_fetch_fail
    if _n <= 0:
        print("❌ 沒有任何一檔抓成功，無法判斷覆蓋率。")
        return 1

    def _pct(x: int) -> str:
        return f"{x}/{_n}（{x / _n * 100:.0f}%）"

    print(f"{'=' * 78}")
    print("覆蓋率總結（分母 = 抓取成功的檔數）")
    print(f"{'=' * 78}")
    print(f"  抓取失敗　　　　　　：{_n_fetch_fail} 檔（未計入分母）")
    print()
    print(f"  費用率 — 官方揭露值　：{_pct(_n_exp_real)}")
    print(f"  費用率 — 估計值　　　：{_pct(_n_exp_est)}")
    print(f"  費用率 — 合計可用　　：{_pct(_n_exp_real + _n_exp_est)}")
    print()
    print(f"  基金規模 — 抓到字串　：{_pct(_n_scale_raw)}")
    print(f"  基金規模 — 可解析比較：{_pct(_n_scale_parsable)}  ← **決定 6D 值不值得做**")
    print()
    print(f"  匯率風險 — 可算　　　：{_pct(_n_fx_ok)}")
    print(f"  匯率風險 — 不適用(TWD)：{_pct(_n_fx_na)}")
    print()

    # ── 建議（門檻是判斷用的參考線，不是評分常數，故留在本腳本內）──────
    print("建議：")
    _exp_ok = (_n_exp_real + _n_exp_est) / _n
    _scale_ok = _n_scale_parsable / _n
    _fx_ok = (_n_fx_ok + _n_fx_na) / _n
    if _exp_ok >= 0.8:
        print(f"  ✅ 費用率覆蓋 {_exp_ok:.0%} —— 撐得起一個維度。")
        if _n_exp_est > _n_exp_real:
            print("     ⚠️ 但其中多數是**估計值**（經理費當費用率）。"
                  "拿估計值去分 A/B 等第之前，等第說明必須講清楚。")
    else:
        print(f"  ❌ 費用率覆蓋只有 {_exp_ok:.0%} —— 不足以當評分維度，"
              "建議維持現況（大表有欄可看，但不進總分）。")
    if _scale_ok >= 0.8:
        print(f"  ✅ 基金規模可解析 {_scale_ok:.0%} —— 可以做，"
              "但要先寫單位/幣別換算（百萬 vs 億、美元 vs 台幣）。")
    else:
        print(f"  ❌ 基金規模可解析只有 {_scale_ok:.0%} —— "
              "**不建議納入 6D**。它是字串欄，解析失敗時會安靜地變成一個"
              "小 20 倍或大 100 倍的數字，比留白更危險。")
    if _fx_ok >= 0.9:
        print(f"  ✅ 匯率風險 {_fx_ok:.0%} 有結論（含 TWD 的 N/A）—— 可以做。"
              "N/A 的檔要從分母移除，不是給 0 分。")
    else:
        print(f"  ❌ 匯率風險只有 {_fx_ok:.0%} 有結論。")
    print()
    print(f"{'=' * 78}")
    print("「基金規模」原始字串（設計解析器用 —— 請把這一段完整貼出來）")
    print(f"{'=' * 78}")
    _seen_shapes: dict = {}
    for _c, _raw, _stat in _scale_samples:
        print(f"  {_c:<12} [{_stat}]  {_raw or '(空)'}")
        # 把數字抽掉，只留「形狀」→ 看有幾種不同格式要處理
        import re as _re2
        _shape = _re2.sub(r"[\d.,]+", "#", _raw).strip() or "(空)"
        _seen_shapes[_shape] = _seen_shapes.get(_shape, 0) + 1
    print()
    print(f"  → 共 {len(_seen_shapes)} 種格式：")
    for _shape, _cnt in sorted(_seen_shapes.items(), key=lambda x: -x[1]):
        print(f"      {_cnt:>3} 檔　{_shape}")
    print("  （格式種類越多，解析器越容易在某一種上安靜地算錯。"
          "1 種最好，3 種以上就要重新評估這一維值不值得做。）")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
