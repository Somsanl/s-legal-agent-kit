# คู่มือปฏิบัติงานบัญชี Phase-2 Planned MCP (7 กลุ่ม 34 เครื่องมือ) และเส้นแดง 7 ข้อ (`slegal-accounting-ops`)

## 1. แผนเครื่องมือ Accounting MCP ระยะที่ 2 (`34` เครื่องมือ = `22 READ + 12 Safe Draft/Proof/Append`)

> เครื่องมือในตารางนี้เป็น **แผน Phase-2 (Planned Roadmap)** ยังไม่เปิดให้เรียกใช้งานบนเซิร์ฟเวอร์ Phase-1 ปัจจุบัน — ห้ามแต่งพารามิเตอร์เรียกเองจนกว่าทีมพัฒนาจะประกาศเปิด Phase-2

### กลุ่ม 1: GL / งบทดลอง / ปิดงวด (`gl_tb_period` — 4 READ)
- `slegal_trial_balance_get` (`READ`, `accounting:read`) — อ่านงบทดลองรายเดือนและตรวจสมดุล `Dr == Cr` (`diff`)
- `slegal_gl_ledger_get` (`READ`, `accounting:read`) — ค้นหาและอ่านสมุดรายวันทั่วไปและบัญชีแยกประเภท
- `slegal_period_close_readiness_get` (`READ`, `accounting:read`) — อ่านสถานะงวดบัญชีและรายการ blockers ก่อนปิดงวด
- `slegal_document_followups_list` (`READ`, `accounting:read`) — อ่านคิวติดตามเอกสารบัญชีค้างส่งแบบแบ่งหน้า

### กลุ่ม 2: ใบเสร็จรับเงิน & PDF (`rc_pdf` — 2 READ + 3 Safe)
- `slegal_receipt_search` (`READ`, `accounting:read`) — ค้นหา `RC` พร้อมสถานะจับคู่ธนาคาร
- `slegal_receipt_get` (`READ`, `accounting:read`) — อ่านรายละเอียด `RC` ยืนยันเงินเข้าจริง และสถานะ PDF
- `slegal_accounting_pdf_ensure` (`PREPARE_CACHE`, `accounting:draft`) — สร้างแคช PDF ให้ตรง `content_version` โดยไม่ส่งหาลูกค้าอัตโนมัติ
- `slegal_document_address_correct` (`SAFE_WRITE`, `accounting:draft`) — แก้ไขเฉพาะที่อยู่ลูกค้ารายเดิม (`mode="address_only"`) ในงวดที่เปิดอยู่ (`Asia/Bangkok`)
- `slegal_receipt_draft_prepare` (`DRAFT_WRITE`, `accounting:draft`) — เตรียมร่าง `RC` พร้อมแนบสลิปตรวจ SHA-256 เพื่อรอออกจริงบนเว็บ

### กลุ่ม 3: เจ้าหนี้ & เอกสารซื้อ (`ap` — 2 READ + 3 Draft/Append)
- `slegal_ap_search` (`READ`, `accounting:read`) — ค้นหาคิว `AP` แยกตามเลน (`review/payment/ledger/posted/closed`)
- `slegal_ap_get` (`READ`, `accounting:read`) — อ่านรายละเอียด `AP` ใบกำกับภาษีซื้อ และสถานะล็อกอนุมัติ/จ่าย/GL
- `slegal_ap_draft_create` (`DRAFT_WRITE`, `accounting:draft`) — สร้างร่าง `AP` (`status="draft"`) พร้อมตรวจงวดเปิดและกันเลขบิลซ้ำ
- `slegal_ap_draft_update` (`DRAFT_WRITE`, `accounting:draft`) — แก้ไขร่าง `AP` ที่ยังไม่ล็อกพร้อม `expectedUpdatedAt`
- `slegal_ap_attach_evidence` (`DRAFT_WRITE`, `accounting:draft`) — แนบหลักฐานแบบ Append-Only พร้อมตรวจ SHA-256

### กลุ่ม 4: ใบสำคัญจ่าย & สลิปจ่าย (`pv` — 2 READ + 2 Draft/Proof)
- `slegal_pv_search` (`READ`, `accounting:read`) — ค้นหา `PV` พร้อมธง `supplier_wht_agent` (`vendor_agent`)
- `slegal_pv_get` (`READ`, `accounting:read`) — อ่านรายละเอียด `PV` ล็อก `requireSupplierWhtAgentStatementBound`, 50 ทวิ และ GL
- `slegal_pv_draft_create` (`DRAFT_WRITE`, `accounting:draft`) — สร้างร่าง `PV` (`status="draft"`) จาก `AP` ที่อนุมัติแล้ว
- `slegal_pv_attach_payment_proof` (`PROOF_WRITE`, `accounting:draft`) — แนบสลิปจ่ายตรวจ SHA-256 **ตันที่ `paid_unposted`** และคงล็อก `vendor_agent` / `requireSupplierWhtAgentStatementBound` (ห้ามลง GL ข้าม `bank_transaction_id` จริง)

### กลุ่ม 5: Statement & กระทบยอดธนาคาร (`bank_reconciliation` — 3 READ + 1 Import Draft)
- `slegal_bank_accounts_list` (`READ`, `accounting:read`) — อ่านรายชื่อบัญชีบริษัท (mask เลขบัญชี) และสรุป Statement
- `slegal_bank_transactions_search` (`READ`, `accounting:read`) — ค้นหารายการเดินบัญชีธนาคารในช่วงไม่เกิน 93 วัน
- `slegal_bank_match_suggest` (`READ`, `accounting:read`) — แนะนำเอกสารคู่เทียบ (`RC`/`PV`/`vendor_agent`) โดยไม่จับคู่จริง
- `slegal_bank_statement_import_draft` (`DRAFT_WRITE`, `accounting:draft`) — ตรวจและเตรียม Staging Import Draft กันแถวซ้ำ (ไม่เขียนลง `bank_transactions` จริง)

### กลุ่ม 6: ภาษีหัก ณ ที่จ่าย (`wht` — 3 READ + 1 Draft)
- `slegal_wht_close_issues_list` (`READ`, `accounting:read`) — อ่านรายการค้างออก 50 ทวิ จาก `rd_wht_close_issues` (`SECTION_40_6` / `SECTION_40_2`)
- `slegal_wht_certificate_search` (`READ`, `accounting:read`) — ค้นหาทะเบียน `50 ทวิ` (`PND3`/`PND53`) พร้อมสถานะ `taxFormConfirmed`
- `slegal_wht_certificate_get` (`READ`, `accounting:read`) — อ่านรายละเอียด `50 ทวิ` รายบรรทัด (`40(6)` / `40(2)` / `3 เตรส`)
- `slegal_wht_certificate_draft_create` (`DRAFT_WRITE`, `accounting:draft`) — สร้างร่าง `50 ทวิ` (`status="draft"`, `taxFormConfirmed=false`) ครอบคลุม `SECTION_40_6` และ `SECTION_40_2`

### กลุ่ม 7: ค่าตอบแทน / ECP / วางบิล EXP / OMEC (`comp_ecp_exp_omec` — 6 READ + 2 Draft/Append)
- `slegal_compensation_search` (`READ`, `accounting:read`) — ค้นหาสรุปค่าตอบแทนทนาย/หุ้นส่วน/ผู้แนะนำภายนอกและรอบจ่าย
- `slegal_compensation_get` (`READ`, `accounting:read`) — อ่านรายละเอียดใบคำนวณค่าตอบแทน ส่วนแบ่ง และสถานะ `PV`/`50 ทวิ`/GL
- `slegal_payout_cycle_preview` (`READ`, `accounting:read`) — พรีวิวรอบโอนคืนพนักงาน 10/25 และความพร้อม K BIZ Manifest (mask เลขบัญชี)
- `slegal_billable_unbilled_list` (`READ`, `accounting:read`) — อ่านรายการสำรองจ่ายลูกความรอวางบิลพร้อมสถานะ Work-Proof
- `slegal_client_billing_draft_create` (`DRAFT_WRITE`, `accounting:draft`) — สร้างร่างใบแจ้งหนี้/ใบเบิกลูกความ (`status="draft"`) จาก `EXP`
- `slegal_supporting_evidence_attach` (`DRAFT_WRITE`, `accounting:draft`) — แนบหลักฐานประกอบแบบ Append-Only พร้อม SHA-256 และ malware scan
- `slegal_partner_ledger_overview_get` (`READ`, `accounting:read+partner-ledger.manage`) — อ่านภาพรวมบัญชีบริหารหุ้นส่วน (**READ ONLY**)
- `slegal_unallocated_office_expenses_list` (`READ`, `accounting:read+partner-ledger.manage`) — อ่านค่าใช้จ่ายสำนักงานที่ยังไม่จัดสรรเข้า OMEC (**READ ONLY**)

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
3. **`REDLINE_03_NO_AP_PV_APPROVAL_OR_GL_BYPASS`**: ห้าม `approve_ap`, `post_ap_gl`, `delete_ap`, `post_pv_gl` (โดยเฉพาะเมื่อไม่มี `bank_transaction_id` จริง), ห้ามแก้ `PV` ที่โพสต์แล้ว, ห้ามโอนเงิน (`PV` proof ตันที่ `paid_unposted` พร้อมคงล็อก `requireSupplierWhtAgentStatementBound`)
4. **`REDLINE_04_NO_LIVE_BANK_TX_OR_RECON_CONFIRM`**: ห้ามสร้าง/แก้/ลบแถว `bank_transactions` จริง และห้ามยืนยันปิดกระทบยอดธนาคารอัตโนมัติ
5. **`REDLINE_05_NO_WHT_ISSUE_OR_RD_TAX_FILING`**: ห้าม `issue_wht_certificate`, `cancel_wht_certificate`, `taxFormConfirmed=true`, ยื่นแบบ ภ.ง.ด.3/ภ.ง.ด.53/ภ.พ.30 หรือจ่ายภาษีเอง
6. **`REDLINE_06_OMEC_READ_ONLY_NO_COMP_APPROVE_OR_KBIZ_PAYOUT`**: `OMEC` และ `Partner Ledger` เป็น **READ ONLY** (เฉพาะสิทธิ์ `partner-ledger.manage`), ห้ามอนุมัติ `COMP`, ห้ามออก `INV` จริงสำหรับ `EXP`, ห้ามสั่งโอน K BIZ
7. **`REDLINE_07_UNIVERSAL_SERVICE_LAYER_LOCKS`**: บังคับ `actorId` จริง, `idempotencyKey` (`slegal_command_status`), `audit_logs`, RBAC + งวดเปิด `Asia/Bangkok`, ห้ามคีย์ลับ/อ้าง `SL-...` เป็นหลัก/hard delete, เคารพ `AppealFilingValidationError`/CCC §193/8 และซ่อนค่าบริการ `QT` สำหรับบัญชีที่ไม่มีสิทธิ์การเงิน
