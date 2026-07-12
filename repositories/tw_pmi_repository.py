"""repositories/tw_pmi_repository.py — 台灣製造業 PMI 9 源並行賽跑(L1)。

v19.348(user 核准設計 B,2026-07-12):自 Stock repo `macro_core.py` 932-1353
移植 9 源解析器 + 並行賽跑(v18.240 SSOT registry / v19.85 拔 FinMind 假 dataset
後的版本),適配本 repo infra:
- `fetch_url`:`infra.proxy.fetch_url`(參數 `retries`;Stock 版為 `attempts`)
- log 前綴 `[tw_pmi_repo...]`
- **不含** Stock 版的 90 天檔案 stale-cache 層(§8.1 step 6 先不做;升級觸發
  條件:user 反映 9 源常態全敗需要過期快取兜底時再加)
- **fund 端擴充**:dgtw(data.gov.tw dataset/6100)CSV 天然含全月度歷史,
  解析器additionally回傳 `series`(list[(date_iso, value)],升冪)— 供
  `fetch_tw_pmi_local` 填 trend/prev。其餘 8 源為單點,無 series。

來源優先序(§2.1 衝突裁決,**第一個命中即用、禁止平均**):
CIER-EN → data.gov.tw → NDC → MacroMicro → CIER(cid21) → StockFeel
→ Cnyes → CIER(cid8) → MoneyDJ

§8.2 L1 Repository:純 I/O + 解析,無 streamlit 真 UI 呼叫。
caller:`repositories.macro_tw_local_repository.fetch_tw_pmi_local`(合約
dict 組裝 + 快取在該處,本檔函式皆無快取 — 單一快取點防雙層 TTL 打架)。
"""
from __future__ import annotations

import datetime as _dt
import re as _re
from typing import Callable

from infra.proxy import fetch_url


def _pmi_src_cier_en_monthly(today, max_age_days, errs):
    """方案 -1 (CIER 英文月度頁): 直接打 `/en/eco/taiwan-manufacturing-pmi-{月}-{年}/`。

    為什麼選這個當最高優先源？
    - CIER 是 PMI 官方發布單位（國發會委託），slug 結構自 2024 起穩定
    - HTML 簡潔（單篇報導 + 數字在標題與首段），正則命中率 >95%
    - 海外 IP 仍會 403 / cloudflare 攔截 → 走 fetch_url 自動 fallback NAS 中繼站
    - 失敗時不要拖時間：每個月最多 2 次 attempts，總共 3 個 slug
    """
    _month_names = ['january', 'february', 'march', 'april', 'may', 'june',
                    'july', 'august', 'september', 'october', 'november', 'december']
    try:
        from bs4 import BeautifulSoup
        # 嘗試 current / -1 / -2 month（PMI 報告通常於次月初公布，最近 1-2 月
        # slug 是命中熱區；再往前推 3 個月當保險）
        for _m_back in range(0, 3):
            _y, _m = today.year, today.month - _m_back
            while _m <= 0:
                _m += 12
                _y -= 1
            _slug = f'taiwan-manufacturing-pmi-{_month_names[_m - 1]}-{_y}'
            _url = f'https://www.cier.edu.tw/en/eco/{_slug}/'
            try:
                r = fetch_url(_url, timeout=12, retries=1)
                if r is None or r.status_code != 200:
                    if r is not None:
                        errs.append(f'CIER-EN.{_slug}:HTTP{r.status_code}')
                    continue
                r.encoding = 'utf-8'
                _txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
                # 模式：「Taiwan Manufacturing PMI ... 55.4」or 「PMI ... at 55.4%」
                # CIER 英文文體穩定，數值通常出現在標題與首段
                _m_pmi = _re.search(
                    r'(?:Manufacturing\s+PMI|PMI)[^.]{0,80}?'
                    r'(?:at|registered|reached|of|stood\s+at|rose\s+to|fell\s+to|was)?'
                    r'[^\d]{0,15}(\d{2}\.\d)\s*(?:%|percent)?',
                    _txt, _re.IGNORECASE)
                if _m_pmi:
                    _v = float(_m_pmi.group(1))
                    if 30 <= _v <= 70:
                        _last_date = _dt.date(_y, _m, 1)
                        if (today - _last_date).days <= max_age_days:
                            _d_iso = f'{_y}-{_m:02d}-01'
                            print(f'[tw_pmi_repo/CIER-EN] ✅ {_v} date={_d_iso} slug={_slug}')
                            return {'value': _v, 'date': _d_iso,
                                    'label': f'CIER Manufacturing PMI ({_month_names[_m - 1].title()} {_y})',
                                    'source': 'CIER-EN', 'is_proxy': False,
                                    'series_id': f'cier-en-{_y}{_m:02d}'}
            except Exception as _e_slug:
                errs.append(f'CIER-EN.{_slug}:{type(_e_slug).__name__}')
                continue
    except Exception as e:
        errs.append(f'CIER-EN:{type(e).__name__}')
        print(f'[tw_pmi_repo/CIER-EN] ❌ {e}')
    return None


def _pmi_src_dgtw(today, max_age_days, errs):
    """方案 0 (Primary): data.gov.tw dataset/6100 官方開放資料（國發會 NDC 提供）。

    流程：① metadata API 取 resources URL → ② 下載 CSV/JSON 解析末筆。
    """
    try:
        import io as _io_dgw
        import csv as _csv_dgw
        # metadata API 端點（多個變體：v1/v2 + .json + 直查 dataset id）
        for _meta_url in (
            'https://data.gov.tw/api/v2/rest/dataset/6100',
            'https://data.gov.tw/api/v1/rest/dataset/6100',
            'https://data.gov.tw/dataset/6100/resource',
        ):
            try:
                _r_meta = fetch_url(_meta_url, timeout=10, retries=1,
                                    headers={'Accept': 'application/json'})
                if _r_meta is None:
                    errs.append(f'dgtw.{_meta_url[-18:]}:無回應')
                    continue
                if _r_meta.status_code != 200:
                    errs.append(f'dgtw.{_meta_url[-18:]}:HTTP{_r_meta.status_code}')
                    continue
                try:
                    _j_meta = _r_meta.json()
                except Exception:
                    continue
                # 解析 resources：常見 shape `result.resources[]` / `resources[]`
                _res = (_j_meta.get('result', {}).get('resources')
                        or _j_meta.get('resources')
                        or _j_meta.get('data', {}).get('resources')
                        or [])
                if not _res:
                    continue
                # 找 CSV / JSON resource
                _csv_url = None
                for _it in _res:
                    _fmt = str(_it.get('format', '')).upper()
                    _url2 = _it.get('url') or _it.get('resourceDownloadUrl')
                    if _fmt in ('CSV', 'JSON') and _url2:
                        _csv_url = _url2
                        break
                if not _csv_url:
                    continue
                # 下載 CSV / JSON
                _r_csv = fetch_url(_csv_url, timeout=15, retries=2)
                if _r_csv is None or _r_csv.status_code != 200:
                    continue
                _txt_csv = _r_csv.content.decode('utf-8-sig', errors='ignore')
                # CSV 路徑：解析最後一筆有效 row（含 PMI 欄位 + 年月）
                if _csv_url.lower().endswith('.csv') or 'csv' in _csv_url.lower():
                    _rdr = list(_csv_dgw.DictReader(_io_dgw.StringIO(_txt_csv)))
                    if _rdr:
                        # 找 PMI 欄位（常見 key：'PMI' / '製造業採購經理人指數' / '指數'）
                        # v19.348 fund 擴充:記住命中的欄名(_pmi_key/_date_key),
                        # 供下方掃全表建 series(Stock 版只取末筆)。
                        _row_last = _rdr[-1]
                        _pmi_v = None
                        _pmi_d = None
                        _pmi_key = None
                        _date_key = None
                        for _k, _v_cell in _row_last.items():
                            _kl = str(_k)
                            if any(_x in _kl for _x in ('PMI', '採購經理', '製造業')):
                                try:
                                    _val = float(str(_v_cell).strip())
                                    if 30 <= _val <= 70:
                                        _pmi_v = _val
                                        _pmi_key = _k
                                        break
                                except (ValueError, TypeError):
                                    pass
                        # 找日期欄位
                        for _k2, _v2 in _row_last.items():
                            _m_d = _re.search(r'(20\d{2})[-/年]?(\d{1,2})', str(_v2))
                            if _m_d:
                                _pmi_d = f'{_m_d.group(1)}-{int(_m_d.group(2)):02d}-01'
                                _date_key = _k2
                                break
                        if _pmi_v is not None and _pmi_d:
                            # v19.348 fund 擴充:CSV 天然含全月度歷史 → 掃全表建
                            # series(升冪,壞列顯式跳過不腦補);caller 用它填
                            # trend/prev(其餘 8 個單點源無此欄)。
                            _series: list = []
                            if _pmi_key is not None and _date_key is not None:
                                for _row_i in _rdr:
                                    try:
                                        _vi = float(str(_row_i.get(_pmi_key, '')).strip())
                                        _mi = _re.search(r'(20\d{2})[-/年]?(\d{1,2})',
                                                         str(_row_i.get(_date_key, '')))
                                        if _mi and 30 <= _vi <= 70:
                                            _series.append(
                                                (f'{_mi.group(1)}-{int(_mi.group(2)):02d}-01',
                                                 _vi))
                                    except (ValueError, TypeError):
                                        continue   # 壞列跳過(§1 不掩蓋:series 少一點誠實反映)
                                _series.sort(key=lambda t: t[0])
                            print(f'[tw_pmi_repo/data.gov.tw] ✅ {_pmi_v} date={_pmi_d} '
                                  f'series={len(_series)} 點')
                            return {'value': _pmi_v, 'date': _pmi_d,
                                    'label': '政府資料開放平臺 dataset/6100',
                                    'source': 'data.gov.tw', 'is_proxy': True,
                                    'series_id': 'dgtw-6100',
                                    'series': _series}
            except Exception as _e_dg:
                errs.append(f'dgtw.{_meta_url[-15:]}:{type(_e_dg).__name__}')
    except Exception as _e_dg_outer:
        errs.append(f'dgtw_outer:{type(_e_dg_outer).__name__}')
        print(f'[tw_pmi_repo/data.gov.tw] ❌ outer {_e_dg_outer}')
    return None


def _pmi_src_ndc(today, max_age_days, errs):
    """方案 0b: 國發會 NDC 景氣指標 API（多 endpoint 變體 + 多 JSON shape parser）。"""
    for ndc_url in (
        'https://index.ndc.gov.tw/app/data/indicator/PMI',
        'https://index.ndc.gov.tw/app/data/indicator/pmi',
        'https://index.ndc.gov.tw/app/data/PMI/latest',
        'https://index.ndc.gov.tw/app/data/indicator/PMI/latest',
    ):
        try:
            r = fetch_url(ndc_url, timeout=12, retries=1,
                          headers={'Accept': 'application/json'})
            if r is None:
                errs.append(f'NDC.{ndc_url[-15:]}:無回應')
                continue
            if r.status_code != 200:
                errs.append(f'NDC.{ndc_url[-15:]}:HTTP{r.status_code}')
                continue
            try:
                j = r.json()
            except Exception:
                continue
            # 解析多種 JSON shape：list / {data:[...]} / {items:[...]} / 單筆 dict
            items = j if isinstance(j, list) else (j.get('data') or j.get('items') or [j])
            if not items:
                continue
            latest = items[-1] if isinstance(items, list) and items else items
            if not isinstance(latest, dict):
                continue
            # 數值欄位常見 key：value / score / pmi / index / composite
            v_raw = (latest.get('value') or latest.get('score')
                     or latest.get('pmi') or latest.get('index')
                     or latest.get('composite'))
            # 日期欄位：date / yearMonth / period / month
            d_raw = (latest.get('date') or latest.get('yearMonth')
                     or latest.get('period') or latest.get('month'))
            if v_raw is None or not d_raw:
                continue
            try:
                v = float(v_raw)
            except (TypeError, ValueError):
                continue
            if not (30 <= v <= 70):
                continue
            # 日期 normalize：'2026-04' / '202604' / '2026/04' → 'YYYY-MM-01'
            d_str = str(d_raw)
            m_d = _re.search(r'(20\d{2})[-/]?(\d{2})', d_str)
            if not m_d:
                continue
            date = f'{m_d.group(1)}-{m_d.group(2)}-01'
            try:
                last_d = _dt.date(int(m_d.group(1)), int(m_d.group(2)), 1)
                if (today - last_d).days > max_age_days:
                    continue
            except Exception:
                pass
            print(f'[tw_pmi_repo/NDC] ✅ {v} date={date} via {ndc_url[-30:]}')
            return {'value': v, 'date': date,
                    'label': '國發會 NDC 景氣指標',
                    'source': 'NDC', 'is_proxy': True,
                    'series_id': 'ndc-pmi'}
        except Exception as e:
            errs.append(f'NDC.{ndc_url[-15:]}:{type(e).__name__}')
            print(f'[tw_pmi_repo/NDC/{ndc_url[-15:]}] ❌ {e}')
    return None


def _pmi_src_macromicro(today, max_age_days, errs):
    """方案 1: MacroMicro 財經 M 平方（chart 22 = 台灣 PMI）。"""
    try:
        from bs4 import BeautifulSoup
        for url in ('https://www.macromicro.me/charts/22/taiwan-pmi',
                    'https://www.macromicro.me/charts/16/tw-pmi'):
            r = fetch_url(url, timeout=12, retries=1)
            if r is None:
                errs.append(f'MacroMicro.{url[-20:]}:無回應')
                continue
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            # 模式：「台灣 PMI ... 49.0」/「製造業 PMI 49.0 (2026/04)」
            m = _re.search(
                r'(?:台灣|TW|Taiwan)[^。]{0,40}?(?:PMI|採購經理[人]?指數)[^。]{0,200}?'
                r'(\d{2}\.\d)[^。]{0,80}?(20\d{2})[\s/年-]+(\d{1,2})',
                txt)
            if m:
                v = float(m.group(1))
                yr = m.group(2)
                mo = int(m.group(3))
                if 30 <= v <= 70 and 1 <= mo <= 12:
                    date = f'{yr}-{mo:02d}-01'
                    print(f'[tw_pmi_repo/MacroMicro] ✅ {v} date={date}')
                    return {'value': v, 'date': date,
                            'label': 'MacroMicro 台灣 PMI',
                            'source': 'MacroMicro', 'is_proxy': False,
                            'series_id': '22'}
    except Exception as e:
        errs.append(f'MacroMicro:{type(e).__name__}')
        print(f'[tw_pmi_repo/MacroMicro] ❌ {e}')
    return None


def _pmi_src_cier21(today, max_age_days, errs):
    """方案 2: CIER 官網最新公告列表（cid=21 新聞稿/PMI 類別）。"""
    try:
        from bs4 import BeautifulSoup
        for cier_url in ('https://www.cier.edu.tw/news/list?cid=21',
                         'https://www.cier.edu.tw/'):
            r = fetch_url(cier_url, timeout=12, retries=1)
            if r is None:
                errs.append(f'CIER.{cier_url[-15:]}:無回應')
                continue
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            # 標題模式：「2026年4月製造業採購經理人指數 PMI 為 49.0」
            m = _re.search(
                r'(20\d{2})\s*年\s*(\d{1,2})\s*月.{0,30}?'
                r'製造業[^。]{0,40}?PMI[^。]{0,30}?(\d{2}\.\d)',
                txt)
            if m:
                yr, mo, v = m.group(1), int(m.group(2)), float(m.group(3))
                if 30 <= v <= 70 and 1 <= mo <= 12:
                    last_date = _dt.date(int(yr), mo, 1)
                    age = (today - last_date).days
                    if age <= max_age_days:
                        date = f'{yr}-{mo:02d}-01'
                        print(f'[tw_pmi_repo/CIER] ✅ {v} date={date}')
                        return {'value': v, 'date': date,
                                'label': 'CIER 中華經濟研究院',
                                'source': 'CIER', 'is_proxy': False,
                                'series_id': 'cier-pmi'}
                    else:
                        errs.append(f'CIER:過時 {age} 天')
    except Exception as e:
        errs.append(f'CIER:{type(e).__name__}')
        print(f'[tw_pmi_repo/CIER] ❌ {e}')
    return None


def _pmi_src_stockfeel(today, max_age_days, errs):
    """方案 3: StockFeel 股感（搜尋頁）。"""
    try:
        from bs4 import BeautifulSoup
        sf_url = 'https://www.stockfeel.com.tw/?s=%E5%8F%B0%E7%81%A3+PMI'
        r = fetch_url(sf_url, timeout=12, retries=1)
        if r is None:
            errs.append('StockFeel:無回應')
        else:
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            m = _re.search(
                r'(20\d{2})\s*年\s*(\d{1,2})\s*月.{0,40}?'
                r'(?:台灣|TW)\s*(?:製造業)?[^。]{0,40}?PMI[^。]{0,30}?(\d{2}\.\d)',
                txt)
            if m:
                yr, mo, v = m.group(1), int(m.group(2)), float(m.group(3))
                if 30 <= v <= 70 and 1 <= mo <= 12:
                    last_date = _dt.date(int(yr), mo, 1)
                    if (today - last_date).days <= max_age_days:
                        date = f'{yr}-{mo:02d}-01'
                        print(f'[tw_pmi_repo/StockFeel] ✅ {v} date={date}')
                        return {'value': v, 'date': date,
                                'label': 'StockFeel 股感（台灣 PMI 搜尋）',
                                'source': 'StockFeel', 'is_proxy': False,
                                'series_id': 'stockfeel-tw-pmi'}
    except Exception as e:
        errs.append(f'StockFeel:{type(e).__name__}')
        print(f'[tw_pmi_repo/StockFeel] ❌ {e}')
    return None


def _pmi_src_cnyes(today, max_age_days, errs):
    """方案 4: 鉅亨網新聞（搜尋台灣 PMI；JSON 解析，不需 BeautifulSoup）。"""
    try:
        cnyes_url = 'https://news.cnyes.com/api/v3/news/category/headline?limit=30&q=%E5%8F%B0%E7%81%A3+PMI'
        r = fetch_url(cnyes_url, timeout=12, retries=1)
        if r is None:
            errs.append('Cnyes:無回應')
        else:
            try:
                d = r.json()
                items = (d.get('items', {}).get('data') or [])
                for it in items[:10]:
                    title = it.get('title', '') + ' ' + it.get('summary', '')
                    m = _re.search(
                        r'(20\d{2})\s*年\s*(\d{1,2})\s*月.{0,30}?'
                        r'(?:台灣|TW)\s*(?:製造業)?[^。]{0,40}?PMI[^。]{0,30}?(\d{2}\.\d)',
                        title)
                    if m:
                        yr, mo, v = m.group(1), int(m.group(2)), float(m.group(3))
                        if 30 <= v <= 70 and 1 <= mo <= 12:
                            last_date = _dt.date(int(yr), mo, 1)
                            if (today - last_date).days <= max_age_days:
                                date = f'{yr}-{mo:02d}-01'
                                print(f'[tw_pmi_repo/Cnyes] ✅ {v} date={date}')
                                return {'value': v, 'date': date,
                                        'label': '鉅亨網新聞',
                                        'source': 'Cnyes', 'is_proxy': False,
                                        'series_id': 'cnyes-tw-pmi'}
            except Exception:
                pass  # 鉅亨可能改 API，靜默失敗
    except Exception as e:
        errs.append(f'Cnyes:{type(e).__name__}')
        print(f'[tw_pmi_repo/Cnyes] ❌ {e}')
    return None


# (v19.85 拔除)原 `_pmi_src_finmind`(方案 5)— 打的 dataset
# `TaiwanEconomicIndicator` 不存在於 FinMind(SDK 2.0.4 Dataset 枚舉 + 官方
# 文件皆無此名),自建立起從未命中;FinMind 亦無 PMI 資料集可替換 → 整段移除,
# PMI_SOURCE_REGISTRY 同步 10 → 9 源。git history 可查回。§3.3 反捏造。


def _pmi_src_cier8(today, max_age_days, errs):
    """方案 6: CIER cid=8（PMI 專屬類別，非 cid=21 新聞稿）。"""
    try:
        from bs4 import BeautifulSoup
        for cier_url in ('https://www.cier.edu.tw/news/list?cid=8',
                         'https://www.cier.edu.tw/news/list?cid=8&page=1'):
            r = fetch_url(cier_url, timeout=12, retries=1)
            if r is None:
                errs.append(f'CIER-cid8.{cier_url[-15:]}:無回應')
                continue
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            m = _re.search(
                r'(20\d{2})\s*年\s*(\d{1,2})\s*月.{0,40}?'
                r'PMI[^。]{0,30}?(\d{2}\.\d)',
                txt)
            if m:
                yr, mo, v = m.group(1), int(m.group(2)), float(m.group(3))
                if 30 <= v <= 70 and 1 <= mo <= 12:
                    last_date = _dt.date(int(yr), mo, 1)
                    if (today - last_date).days <= max_age_days:
                        date = f'{yr}-{mo:02d}-01'
                        print(f'[tw_pmi_repo/CIER-cid8] ✅ {v} date={date}')
                        return {'value': v, 'date': date,
                                'label': 'CIER 中華經濟研究院（PMI 專欄）',
                                'source': 'CIER', 'is_proxy': False,
                                'series_id': 'cier-pmi-cid8'}
    except Exception as e:
        errs.append(f'CIER-cid8:{type(e).__name__}')
        print(f'[tw_pmi_repo/CIER-cid8] ❌ {e}')
    return None


def _pmi_src_moneydj(today, max_age_days, errs):
    """方案 7: MoneyDJ 財經知識庫（搜尋頁，HTML 含 PMI 圖表 alt）。"""
    try:
        from bs4 import BeautifulSoup
        mdj_url = ('https://www.moneydj.com/KMDJ/Search/SearchListNew.aspx'
                   '?keyword=%E5%8F%B0%E7%81%A3PMI&type=knowledge')
        r = fetch_url(mdj_url, timeout=12, retries=1)
        if r is None:
            errs.append('MoneyDJ:無回應')
        else:
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            m = _re.search(
                r'(20\d{2})\s*年\s*(\d{1,2})\s*月.{0,40}?'
                r'(?:台灣|TW)\s*(?:製造業)?[^。]{0,40}?PMI[^。]{0,30}?(\d{2}\.\d)',
                txt)
            if m:
                yr, mo, v = m.group(1), int(m.group(2)), float(m.group(3))
                if 30 <= v <= 70 and 1 <= mo <= 12:
                    last_date = _dt.date(int(yr), mo, 1)
                    if (today - last_date).days <= max_age_days:
                        date = f'{yr}-{mo:02d}-01'
                        print(f'[tw_pmi_repo/MoneyDJ] ✅ {v} date={date}')
                        return {'value': v, 'date': date,
                                'label': 'MoneyDJ 財經知識庫',
                                'source': 'MoneyDJ', 'is_proxy': False,
                                'series_id': 'mdj-tw-pmi'}
    except Exception as e:
        errs.append(f'MoneyDJ:{type(e).__name__}')
        print(f'[tw_pmi_repo/MoneyDJ] ❌ {e}')
    return None


# v18.240 SSOT — TW-PMI 來源註冊表
# 順序即優先序（越前面越權威）；fetch_tw_pmi 並行賽跑後依此序取第一個命中。
# 各 handler 線程安全：只讀 today/max_age_days、對共享 errs append、回傳新 dict 或 None。
# 新增 source：append 1 entry 即可，fetch_tw_pmi driver 0 改。


PMI_SOURCE_REGISTRY: list[tuple[str, Callable]] = [
    ('CIER-EN',     _pmi_src_cier_en_monthly),
    ('data.gov.tw', _pmi_src_dgtw),
    ('NDC',         _pmi_src_ndc),
    ('MacroMicro',  _pmi_src_macromicro),
    ('CIER',        _pmi_src_cier21),
    ('StockFeel',   _pmi_src_stockfeel),
    ('Cnyes',       _pmi_src_cnyes),
    ('CIER-cid8',   _pmi_src_cier8),
    ('MoneyDJ',     _pmi_src_moneydj),
]


def fetch_tw_pmi_race(*, max_age_days: int = 90) -> dict:
    """9 源並行賽跑,依優先序取第一個命中(語義同 Stock `fetch_tw_pmi`)。

    Returns
    -------
    dict
      命中:{'value': float, 'date': 'YYYY-MM-DD', 'label': str,
            'source': str, 'is_proxy': bool, 'series_id': str,
            'fetched_at': str, 'series': list[tuple[str,float]]|缺(僅 dgtw 有)}
      失敗:{'_err_pmi': str, 'value': None, 'source': 'TW_PMI:all_tiers_failed',
            'fetched_at': str}
    """
    from concurrent.futures import ThreadPoolExecutor as _TPE

    today = _dt.date.today()
    errs: list[str] = []
    _fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat()

    _results: dict = {}
    with _TPE(max_workers=len(PMI_SOURCE_REGISTRY)) as _ex:
        _fut2name = {_ex.submit(_fn, today, max_age_days, errs): _nm
                     for _nm, _fn in PMI_SOURCE_REGISTRY}
        for _fut in _fut2name:
            _nm = _fut2name[_fut]
            try:
                _r = _fut.result()
            except Exception as _e_fut:
                errs.append(f'{_nm}:future {type(_e_fut).__name__}')
                _r = None
            if _r:
                _results[_nm] = _r
    # 依優先序取第一個命中(§2.1 上層贏,禁止平均)
    for _nm, _ in PMI_SOURCE_REGISTRY:
        if _nm in _results:
            print(f'[tw_pmi_repo] ✅ 採用 {_nm}(9 源並行,依優先序)')
            _hit = dict(_results[_nm])
            _hit['fetched_at'] = _fetched_at
            return _hit
    err_msg = ' | '.join(errs) or 'all 9 stages failed'
    print(f'[tw_pmi_repo] ❌ 9 段並行全失敗:{err_msg}')
    return {'_err_pmi': err_msg, 'value': None,
            'source': 'TW_PMI:all_tiers_failed', 'fetched_at': _fetched_at}
