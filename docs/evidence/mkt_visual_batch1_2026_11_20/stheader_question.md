單組產出，未經獨立複驗。fixture 人造資料；Chromium 1243、Streamlit 1.59.2、本機（有 Deploy 頂欄）；Cloud／真機 NOT RUN。
# UI-2 釐清：「頂部三層」各自多高、縮 stHeader 20px 值多少（本批未實作，待 Visual Gate）
## ① 三個東西不是同一層（getBoundingClientRect，視窗座標；本批施工前→後）
| 層 | 是什麼 | 390 | 768 | 1280 | 本批是否改動 |
|---|---|---|---|---|---|
| ① Streamlit 原生 `stHeader`（含 Deploy／⋮） | Streamlit 自帶頂欄 | 60→60 | 60→60 | 60→60 | **未動** |
| ② ui_v3 頁首五頁導覽（`.st-key-uv3-top-nav`） | 手機／平板頁首五格（≥48px 觸控） | 61→61 | 61→61 | 不顯示（桌機為側欄） | **未動** |
| ③ New UI2 Status Bar（`.uv3-statusbar`，PREVIEW＋更新時間） | Shell 極薄一行 | 20→20（降級情境折行時 40） | 20→20 | 20→20 | **未動** |

## ② 「縮 stHeader 20px」（60→40）單獨帶來的首屏收益（原型在本批施工後版本上疊 CSS，單獨開關量測）
| 開關 | 390 主圖露出 px | 768 | 1280 | h1 y（390／1280） |
|---|---|---|---|---|
| 現況（header 60） | 199.8 | 249.4 | 266.4 | 187.4／126.4 |
| 只縮 `stHeader` 60→40 | 199.8（±0） | 249.4（±0） | 266.4（±0） | 187.4／126.4（不動） |
| 縮 `stHeader` 40＋`.block-container` padding-top 3.4rem→2.5rem | 214.2（+14.4） | 263.8（+14.4） | 280.8（+14.4） | 173.0／112.0 |

**結論**：只縮 stHeader 高度，**內容完全不動、首屏收益 0**——頁面內容上緣由 `.block-container` 的 padding-top（3.4rem≈54px）決定，stHeader 是浮在其上。真正收益來自「同時把 padding-top 縮到約等於 header 高度（2.5rem＝40px）」，合計 **+14.4px**（不是 20px）。副作用：頂欄按鈕（Deploy／⋮）區縮到 40px 高，觸控命中未測；頁首五格導覽位置同步上移。
## ③ 本批處置
本批**未實作**此項（授權明列「不做 stHeader 縮 40px」）。是否做、做哪一種（只縮 header／header＋padding），待 Visual Gate 與客戶依本表決定；Cloud 是否真有此頂欄列須先以 Cloud 截圖確認。
