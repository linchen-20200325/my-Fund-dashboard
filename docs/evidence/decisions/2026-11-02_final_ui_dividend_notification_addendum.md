# 2026-11-02｜Final UI Contract Freeze：配息行事曆與 LINE notification 補充

> 性質：客戶對既有 `docs/v2/79_final_ui_contract_freeze.md` 的**同一主線補充**；不是第二套規格，不是 production 動工授權。正式裁示仍待 UI-15 Decision Gate。

## 客戶要求的收斂方向（要點保存）

- 維持 #1118 Final UI／Decision System Contract Freeze；本輪只做 inventory＋contract proposal＋Gap registration＋Decision Gate，不開始 production。
- 嚴格區分兩種 LINE：
  - Information／Event Notification：配息基準日、除息日、基金發放日、日期異動、資料缺失、推估升級正式公告、配息行事曆，可納入 proposal。
  - Directional／Action Notification：換股、加碼、減碼、賣出、switch recommendation、action advice，本輪不得恢復；須等待 Deterministic Rules、Risk Cap、System Action State、正式 action vocabulary、OneBrain controlled integration。
- UI ownership proposal：不新增第六頁；💼 我的資產擁有配息行事曆（Secondary／detail 或 CTA，不塞第一屏）；⚙️ 設定擁有通知偏好與 Delivery Health／Audit。Notification preference ≠ 投資規則。
- 日期語意至少分：Record Date、Ex-Dividend Date、Payment Date、Estimated Bank Credit Window；禁止把 Payment Date 直接稱銀行／平台實際入帳日，除非真的有實際入帳事件資料。
- Date Status proposal：confirmed／scheduled／estimated／unavailable；若與既有正式詞彙衝突，走 Decision Gate，不建立第二套 presentation vocabulary。
- Source precedence proposal：Official confirmed／scheduled → existing approved authoritative structured → existing approved secondary structured → historical deterministic estimation → unavailable。正式日期不得被推估覆蓋；推估不得升格 confirmed；任何新 source 另走 Data Source Decision Gate。
- `services/dividend_calendar.py` 保留，候選定位為 Dividend Date Fallback Estimation Engine；只用單一基金自身歷史、辨識頻率、以歷史 interval 推估、樣本不足降低 evidence／棄權、無 pay history 不硬編。
- deterministic engine 的 confidence／error evidence 不得與 LLM 未校準機率混淆；若未來外露字樣，可研究 evidence quality／estimation reliability，但 production copy 另走 Gate。
- Dividend Event field-level provenance 至少研究：fund_identity、event_type、event_date、date_status、source、source_url／source_ref、as_of、retrieved_at、announcement_date、is_revised、previous_value、estimation_method、evidence_count；缺欄即 Missing，不虛構。
- Revision proposal：estimated→scheduled→confirmed；scheduled old→new；confirmed old→corrected confirmed，至少保留 previous/new/source/update timestamp/change reason（來源有提供才記）。
- LINE 只有 semantic change 才發異動；未來 implementation 需 dedupe、idempotency、retry 不重複；fingerprint／delivery key 延到 implementation batch。
- 保留月底通知下個月的既有 use case；未來摘要可分 confirmed／scheduled／estimated／Missing，copy／symbol 仍服從 44／79 Missing SSOT。
- Reminder cadence 只列 proposal：月底下月摘要、正式公告、日期異動、是否 T-7／T-1、holdings-only／watchlist；本輪不新增 production schedule。
- Delivery audit proposal：notification_id、notification_type、target_period、generated_at、data_fingerprint、channel、delivery_status、delivered_at、retry_count、error_class；禁止保存 LINE token／secret／credential raw value。
- Decision Digest boundary：客觀 Dividend Event facts 可作未來 cash-flow reasoning 候選；LINE delivery metadata／renderer metadata 不進投資 Digest／OneBrain fingerprint。
- Anti-Bloat：優先補既有 BL；本輪以 BL-0531 的 UI-15 子項承接，不另拆小 BL。若 UI-15 核准後真的出現 official-source research／migration／audit implementation，才再檢查是否需最少必要新 BL。
- 禁止修改：production code、LINE workflow／cron、secrets、新 source／provider、Risk Cap、action trigger、OneBrain runtime、frozen 44、舊 LINE action notification production。

## UI-15 最小 Decision Gate

**UI-15｜配息行事曆與 LINE 通知如何納入 Final UI？**

- A（客戶要求列為推薦）：💼 擁有配息行事曆；⚙️ 擁有通知偏好／delivery health／audit；正式日期優先、推估只 fallback；月底下月 LINE 摘要 use case 保留；日期變更可作未來即時通知；directional／action LINE 不在本輪恢復。
- B：只保留 LINE 月底摘要，不把 calendar 正式納入 New UI。
- C：全部延後，不納入 Final UI Freeze。

本檔只保存指示與追溯背景；**不把 A 寫成已裁示**。正式 proposal 與 rationale 見 `docs/v2/79_final_ui_contract_freeze.md` §17，最終裁示後再依治理規則回寫 canonical SSOT。
