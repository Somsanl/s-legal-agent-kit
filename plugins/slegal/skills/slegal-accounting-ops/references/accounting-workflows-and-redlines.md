# คู่มือปฏิบัติงานบัญชี Live MCP (7 กลุ่ม 34 เครื่องมือ) และเส้นแดง 7 ข้อ (`slegal-accounting-ops`)

## 1. รายการเครื่องมือ Core Accounting MCP บน Production (`34` เครื่องมือ = `22 READ + 12 Safe Draft/Proof/Append`)

> เครื่องมือทั้ง 34 ตัวด้านล่าง **เปิดใช้งานจริงแล้ว (LIVE ON PRODUCTION)** ภายใต้ขอบเขต `accounting:read` และ `accounting:draft` (ส่วนงาน Partner Ledger & OMEC ต้องมีสิทธิ์ผู้ใช้ `partner-ledger.manage` เพิ่มเติม) — ทุก write tool บังคับส่ง `idempotencyKey`, ตรวจงวดบัญชีเปิดตามเวลา `Asia/Bangkok`, และบันทึก `audit_logs` พร้อม `actorId` จริง

### กลุ่ม 1: GL / งบทดลอง / ปิดงวด (`gl_tb_period` — 4 READ)
- `slegal_trial_balance_get` (`READ`, `accounting:read`) — อ่านงบทดลองรายเดือนและงบการเงินประจำปี พร้อมตรวจสมดุล `Dr == Cr` (`diff`)
- `slegal_gl_ledger_get` (`READ`, `accounting:read`) — ค้นหาและอ่านสมุดรายวันทั่วไป (`journal_entries`) บัญชีแยกประเภท (`general_ledger`) และรายละเอียดใบสำคัญรายวัน
- `slegal_period_close_readiness_get` (`READ`, `accounting:read`) — อ่านสถานะงวดบัญชี (`open`/`closing`/`closed`/`locked`) พร้อม blockers และ advisories ก่อนปิดงวด
- `slegal_document_followups_list` (`READ`, `accounting:read`) — อ่านคิวติดตามเอกสารบัญชีค้างส่งแบบแบ่งหน้า

### กลุ่ม 2: ใบเสร็จรับเงิน & PDF (`rc_pdf` — 2 READ + 3 Safe)
- `slegal_receipt_search` (`READ`, `accounting:read`) — ค้นหา `RC` ตามเลขเอกสาร ลูกค้า คดี ช่วงวันที่ หรือสถานะ พร้อมสถานะจับคู่ธนาคาร
- `slegal_receipt_get` (`READ`, `accounting:read`) — อ่านรายละเอียด `RC` การยืนยันรับเงินจริง การจัดสรรรับชำระ สถานะแก้ไขวันที่ และสถานะ PDF
- `slegal_accounting_pdf_ensure` (`PREPARE_CACHE`, `accounting:draft`, rate limit `30/min`) — ตรวจและสร้างแคช PDF ฉบับมาตรฐานให้ตรง `content_version` **โดยไม่แก้ไขข้อมูลบัญชีและไม่ส่งหาลูกค้าอัตโนมัติ**
- `slegal_document_address_correct` (`SAFE_WRITE`, `accounting:draft`) — แก้ไขเฉพาะที่อยู่ของลูกค้ารายเดิม (**ฝั่งเซิร์ฟเวอร์ล็อก `mode="address_only"` ตายตัว** ห้ามเปลี่ยนตัวลูกค้า `customerPartyId`/`customerTaxId`/ยอดเงิน/วันที่) ใช้ได้เฉพาะเอกสารที่ออกแล้วในงวดบัญชีที่เปิดอยู่ (`Asia/Bangkok`) พร้อม `expectedUpdatedAt`
- `slegal_receipt_draft_prepare` (`DRAFT_WRITE`, `accounting:draft`) — เตรียมร่าง `RC` พร้อมแนบสลิปโอนตรวจ SHA-256 รอให้นักบัญชีตรวจสอบและกดออกเลขจริงบนเว็บ (ห้ามออกเลขจริงและห้ามโพสต์ GL)

### กลุ่ม 3: เจ้าหนี้ & เอกสารซื้อ (`ap` — 2 READ + 3 Draft/Append)
- `slegal_ap_search` (`READ`, `accounting:read`) — ค้นหาคิว `AP` แยกตามเลน (`review/payment/ledger/posted/closed`) พร้อมยอดค้างชำระ
- `slegal_ap_get` (`READ`, `accounting:read`) — อ่านรายละเอียด `AP` บรรทัดรายการ ใบกำกับภาษีซื้อ การจัดหมวดบัญชี และสถานะล็อกอนุมัติ/จ่าย/GL
- `slegal_ap_draft_create` (`DRAFT_WRITE`, `accounting:draft`) — สร้างร่าง `AP` (`status="draft"` เท่านั้น) พร้อมตรวจงวดเปิด `Asia/Bangkok` และกันเลขบิลคู่ค้าซ้ำ
- `slegal_ap_draft_update` (`DRAFT_WRITE`, `accounting:draft`) — แก้ไขร่าง `AP` เฉพาะสถานะ `draft`/`needs_more_evidence` ที่ยังไม่ล็อก พร้อม `expectedUpdatedAt`
- `slegal_ap_attach_evidence` (`DRAFT_WRITE`, `accounting:draft`) — แนบหลักฐานใบแจ้งหนี้/ใบกำกับภาษีซื้อแบบ Append-Only พร้อมตรวจ SHA-256 และ malware scan

### กลุ่ม 4: ใบสำคัญจ่าย & สลิปจ่าย (`pv` — 2 READ + 2 Draft/Proof)
- `slegal_pv_search` (`READ`, `accounting:read`) — ค้นหา `PV` แยกตามแท็บ พร้อมธง `supplier_wht_agent` (`vendor_agent`) และความพร้อมลง GL
- `slegal_pv_get` (`READ`, `accounting:read`) — อ่านรายละเอียด `PV` รายการชำระ ล็อก `requireSupplierWhtAgentStatementBound` 50 ทวิที่เชื่อม และสถานะ GL
- `slegal_pv_draft_create` (`DRAFT_WRITE`, `accounting:draft`) — สร้างร่าง `PV` (`status="draft"` เท่านั้น) จาก `AP` ที่อนุมัติแล้วและมียอดค้างชำระ — **นักบัญชีต้องไปกดอนุมัติ (`draft -> approved`) หรือยกเลิก (`draft -> cancelled`) ผ่านหน้าเว็บ `/accounting/payment-vouchers`**
- `slegal_pv_attach_payment_proof` (`PROOF_WRITE`, `accounting:draft`) — แนบสลิปจ่ายตรวจ SHA-256 **เฉพาะ `ordinary + vendor` PV ที่อยู่ในสถานะ `approved` เท่านั้น** (`employee` / `compensation` / `wht_remittance` PV ต้องดำเนินการผ่าน Web UI); ปรับสถานะตันที่ `paid_unposted` (`bank_transaction_id=null`, **zero GL post**) และคงล็อก `vendor_agent` / `requireSupplierWhtAgentStatementBound` ครบถ้วน

### กลุ่ม 5: Statement & กระทบยอดธนาคาร (`bank_reconciliation` — 3 READ + 1 Import Draft)
- `slegal_bank_accounts_list` (`READ`, `accounting:read`) — อ่านรายชื่อบัญชีบริษัท (mask เลขบัญชี) ยอดเงินสดภาพรวม และสรุป Statement
- `slegal_bank_transactions_search` (`READ`, `accounting:read`) — ค้นหารายการเดินบัญชีธนาคารแบบแบ่งหน้าในช่วงไม่เกิน `93` วัน
- `slegal_bank_match_suggest` (`READ`, `accounting:read`) — แนะนำเอกสารคู่เทียบ (`RC`/`PV`/`vendor_agent`) สำหรับรายการที่ยังไม่จับคู่ (แนะนำอย่างเดียว ไม่จับคู่จริง)
- `slegal_bank_statement_import_draft` (`DRAFT_WRITE`, `accounting:draft`) — **ขั้นตอนบังคับ:** ให้อัปโหลดไฟล์ Statement (CSV/TSV/XLSX) ผ่าน `slegal_upload_prepare` โดยระบุ `purpose: "bank_statement"` และ `slegal_upload_finalize` ก่อน แล้วจึงเรียก `slegal_bank_statement_import_draft` เพื่อแปลงและตรวจแถวซ้ำเป็น **Staging Preview Draft เท่านั้น (zero writes ลง `bank_transactions` จริง)**

### กลุ่ม 6: ภาษีหัก ณ ที่จ่าย (`wht` — 3 READ + 1 Draft)
- `slegal_wht_close_issues_list` (`READ`, `accounting:read`) — อ่านรายการค้างออก 50 ทวิ จาก `rd_wht_close_issues` และ blockers ก่อนยื่นแบบ
- `slegal_wht_certificate_search` (`READ`, `accounting:read`) — ค้นหาทะเบียน `50 ทวิ` (`PND3`/`PND53`) ทั้งฝั่งหักจ่ายและลูกค้าหัก พร้อมสถานะ `taxFormConfirmed`
- `slegal_wht_certificate_get` (`READ`, `accounting:read`) — อ่านรายละเอียด `50 ทวิ` รายบรรทัด (`SECTION_40_6` / `SECTION_40_2` / `PAYMENT_UNDER_3_TER`)
- `slegal_wht_certificate_draft_create` (`DRAFT_WRITE`, `accounting:draft`) — สร้างร่าง `50 ทวิ` (`status="draft"`, `taxFormConfirmed=false`) จากแหล่งที่จ่ายจริง ครอบคลุมทั้ง **`SECTION_40_6`** (3% ทนาย/หุ้นส่วน) และ **`SECTION_40_2`** (ผู้แนะนำภายนอก) พร้อมตรวจ optimistic lock (`voucherUpdatedAt`, `sourceUpdatedAt`)

### กลุ่ม 7: ค่าตอบแทน / ECP / วางบิล EXP / OMEC (`comp_ecp_exp_omec` — 6 READ + 2 Draft/Append)
- `slegal_compensation_search` (`READ`, `accounting:read`) — ค้นหาสรุปค่าตอบแทนทนาย/หุ้นส่วน/ผู้แนะนำภายนอก ยอดค้างจ่ายตามบทบาท และรอบจ่าย
- `slegal_compensation_get` (`READ`, `accounting:read`) — อ่านรายละเอียดใบคำนวณค่าตอบแทน ส่วนแบ่ง และสถานะ `PV`/`50 ทวิ`/GL
- `slegal_payout_cycle_preview` (`READ`, `accounting:read`) — พรีวิวรอบโอนคืนพนักงาน 10/25 และความพร้อม K BIZ Manifest (mask เลขบัญชีเสมอ ห้ามสั่งโอน)
- `slegal_billable_unbilled_list` (`READ`, `accounting:read`) — อ่านรายการสำรองจ่ายลูกความรอวางบิลจาก `v_client_unbilled_disbursements_by_case` พร้อมสถานะ Work-Proof
- `slegal_client_billing_draft_create` (`DRAFT_WRITE`, `accounting:draft`) — สร้างร่างใบแจ้งหนี้/ใบเบิกลูกความ (`status="draft"`) จาก `EXP` ผ่าน `createDraftClientBillingDocument` (ตัด `SL-...` และข้อความภายในอัตโนมัติ ห้ามออกจริง)
- `slegal_supporting_evidence_attach` (`DRAFT_WRITE`, `accounting:draft`) — แนบหลักฐานประกอบแบบ Append-Only ให้ `billable_expense_item` หรือ `employee_claim_line` ที่อนุมัติแล้ว พร้อม SHA-256 และ malware scan
- `slegal_partner_ledger_overview_get` (`READ`, `accounting:read` + **`partner-ledger.manage`**) — อ่านภาพรวมบัญชีบริหารหุ้นส่วนและสภาพคล่องสำนักงาน (**STRICTLY READ ONLY**)
- `slegal_unallocated_office_expenses_list` (`READ`, `accounting:read` + **`partner-ledger.manage`**) — อ่านค่าใช้จ่ายสำนักงานที่ยังไม่จัดสรรเข้า OMEC (**OMEC STRICTLY READ ONLY**)

---

## 2. เกณฑ์ภาษีหัก ณ ที่จ่าย (`50 ทวิ` / `ภ.ง.ด.3` / `ภ.ง.ด.53`)

- **`ภ.ง.ด.3`**: ผู้รับเงินเป็น **บุคคลธรรมดา**
- **`ภ.ง.ด.53`**: ผู้รับเงินเป็น **นิติบุคคล** (`บริษัท ... จำกัด`, `บริษัท ... จำกัด (มหาชน)`, `ห้างหุ้นส่วนจำกัด ...`)

| ลักษณะงาน / บทบาทผู้รับเงิน | ประเภทเงินได้ใน `50 ทวิ` | อัตรา WHT มาตรฐาน | หมายเหตุ |
|---|---|---|---|
| **ทนายความ / หุ้นส่วน / ผู้ทำงานในสำนวน** | **`SECTION_40_6`** (มาตรา 40(6) วิชาชีพอิสระ — กฎหมาย, ท.ป. 4/2528 ข้อ 6) | **3%** | ออกแยกรายรายการค่าตอบแทนที่จ่ายจริง (`compensation_line`) |
| **ผู้แนะนำงานภายนอก (`tier_1_external`)** | **`SECTION_40_2`** (มาตรา 40(2) ค่านายหน้า / ค่าตอบแทนจากการรับทำงานให้) | ตามเกณฑ์กฎหมาย/สัญญา | ใช้เฉพาะผู้แนะนำงานภายนอกตามที่ตั้งค่าในระบบ |
| **ค่าบริการทั่วไป / ค่าจ้างทำของ** | **มาตรา 3 เตรส** (`PAYMENT_UNDER_3_TER`) | **3%** | ตรวจใบกำกับภาษี/ใบเสร็จผู้ขายก่อนหัก |

---

## 3. เส้นแดง 7 ข้อ (Hard Forbidden Actions on MCP)

1. **`REDLINE_01_NO_GL_OR_PERIOD_MUTATION`**: ห้าม `journal_create`, `journal_post`, `journal_reverse`, `period_close`, `period_lock`, `period_reopen`
2. **`REDLINE_02_NO_RC_REVERSE_OR_CLIENT_SEND`**: ห้าม `receipt_reverse`, ห้ามออก/ยืนยันรับเงินอัตโนมัติ, ห้ามแก้ลูกค้าแบบ `mode="full"`, ห้ามส่งเอกสารหาลูกค้าอัตโนมัติ
3. **`REDLINE_03_NO_AP_PV_APPROVAL_OR_GL_BYPASS`**: ห้าม `approve_ap`, `post_ap_gl`, `delete_ap`, `post_pv_gl` (โดยเฉพาะเมื่อไม่มี `bank_transaction_id` จริง), ห้ามแก้ `PV` ที่โพสต์แล้ว, ห้ามโอนเงิน (`slegal_pv_attach_payment_proof` ใช้ได้เฉพาะ `ordinary + vendor` PV ตันที่ `paid_unposted` พร้อมคงล็อก `requireSupplierWhtAgentStatementBound`)
4. **`REDLINE_04_NO_LIVE_BANK_TX_OR_RECON_CONFIRM`**: ห้ามสร้าง/แก้/ลบแถว `bank_transactions` จริง และห้ามยืนยันปิดกระทบยอดธนาคารอัตโนมัติ
5. **`REDLINE_05_NO_WHT_ISSUE_OR_RD_TAX_FILING`**: ห้าม `issue_wht_certificate`, `cancel_wht_certificate`, `taxFormConfirmed=true`, ยื่นแบบ ภ.ง.ด.3/ภ.ง.ด.53/ภ.พ.30 หรือจ่ายภาษีเอง
6. **`REDLINE_06_OMEC_READ_ONLY_NO_COMP_APPROVE_OR_KBIZ_PAYOUT`**: `OMEC` และ `Partner Ledger` เป็น **READ ONLY** (เฉพาะสิทธิ์ `partner-ledger.manage`), ห้ามอนุมัติ `COMP`, ห้ามออก `INV` จริงสำหรับ `EXP`, ห้ามสั่งโอน K BIZ
7. **`REDLINE_07_UNIVERSAL_SERVICE_LAYER_LOCKS`**: บังคับ `actorId` จริง, `idempotencyKey` (`slegal_command_status`), `audit_logs`, RBAC + งวดเปิด `Asia/Bangkok`, ห้ามคีย์ลับ/อ้าง `SL-...` เป็นหลัก/hard delete, เคารพ `AppealFilingValidationError`/CCC §193/8 และซ่อนค่าบริการ `QT` สำหรับบัญชีที่ไม่มีสิทธิ์การเงิน
