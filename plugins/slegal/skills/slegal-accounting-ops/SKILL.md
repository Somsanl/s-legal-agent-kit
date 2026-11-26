---
name: slegal-accounting-ops
description: Operate, review, and safeguard S-Legal core accounting & Thai tax workflows via 34 Live MCP tools (22 READ + 12 Safe Draft/Proof/Append) across 7 accounting domains — GL/Trial Balance/Period Close, Receipts (`RC`) & PDF, Accounts Payable (`AP`), Payment Vouchers (`PV`) & Slips, Bank Statement & Reconciliation, Withholding Tax (`50 ทวิ`, `ภ.ง.ด.3`, `ภ.ง.ด.53`, Section 40(6) 3% legal profession vs Section 40(2) external referral), and Compensation/10-25 Payout Cycles/EXP/OMEC (strictly READ ONLY gated by `partner-ledger.manage`). Works alongside `slegal-billing-ops` (23 front-office tools = 57 total accounting/billing tools) under 7 hard Accounting Red-Line locks. Use when the user asks about ใบเสร็จรับเงิน (RC), เจ้าหนี้ (AP), ใบสำคัญจ่าย (PV), 50 ทวิ / ภ.ง.ด.3-53, รอบเบิกจ่าย 10/25, ค่าตอบแทนทนาย, OMEC, กระทบยอดธนาคาร, or งบทดลอง.
---

# S-Legal Accounting, Thai Tax (WHT/VAT), Payout Cycles & Trial Balance (Live MCP)

คู่มือปฏิบัติงานบัญชีและภาษีอากรสำหรับ **ทีมบัญชี S-Legal** ครอบคลุมครบทั้ง **7 กลุ่มงานบัญชีหลัก (`34` Live Accounting MCP Tools: `22 READ` + `12 Safe Draft/Proof/Append`)** ควบคู่กับ **`23` เครื่องมือวางบิล/ตั้งเบิก (`slegal-billing-ops`)** รวมเป็น **`57` เครื่องมือบัญชี/การเงิน** (จากทั้งหมด **`95` เครื่องมือ Live บน Production**) ภายใต้ **เส้นแดง 7 ข้อ (Hard Red-Line Locks)**

## สถานะเครื่องมือจริงบน Production (95 Live MCP Tools)

1. **ระบบ (`2` เครื่องมือ — `context:read`)**: `slegal_whoami`, `slegal_command_status`
2. **Front-Office Billing & EC (`23` เครื่องมือ)**: `QT`/`MBA`, `INV`, `EC`, `case_expense`, `lookup`, `intake`, `upload` -> อ่านสกิล **`slegal-billing-ops`**
3. **Core Accounting & Tax (`34` เครื่องมือ — LIVE ON PRODUCTION ครบทั้ง `7` กลุ่ม)**:
   - **`22 READ` Tools (`accounting:read`)**: อ่านงบทดลอง, GL/สมุดรายวัน, ความพร้อมปิดงวด, คิวตามเอกสาร, `RC`, `AP`, `PV`, บัญชีธนาคาร/Statement/คู่แนะนำกระทบยอด, คิว `50 ทวิ` (`rd_wht_close_issues`), ทะเบียน `50 ทวิ`, ค่าตอบแทนทนาย, พรีวิวรอบจ่าย 10/25 & K BIZ Manifest, ค่าใช้จ่ายสำรองจ่ายรอวางบิล; และ **Partner Ledger & OMEC (`2` เครื่องมือ READ ONLY ที่บังคับสิทธิ์ผู้ใช้ `partner-ledger.manage` เพิ่มเติม)**
   - **`12 Safe Draft / Proof / Append` Tools (`accounting:draft`)**: `1 PREPARE_CACHE` (`slegal_accounting_pdf_ensure`), `1 SAFE_WRITE` (`slegal_document_address_correct` ล็อก `mode="address_only"`), `9 DRAFT_WRITE` (เตรียมร่าง `RC`, สร้าง/แก้/แนบหลักฐานร่าง `AP`, สร้างร่าง `PV`, Staging Import Draft สเตทเมนต์, สร้างร่าง `50 ทวิ`, สร้างร่างใบเบิก/ใบแจ้งหนี้ `EXP`, แนบหลักฐานประกอบแบบ Append-Only), และ `1 PROOF_WRITE` (`slegal_pv_attach_payment_proof` สำหรับ `ordinary + vendor` PV เท่านั้น)
4. **งานกฎหมาย/คดี (`36` เครื่องมือ)**: ดู `slegal-case-intake`, `slegal-work-tracker`, `slegal-dbd-order`

> **ตรวจสอบสิทธิ์คีย์ปัจจุบันก่อนเริ่ม**: เรียก `slegal_whoami` เพื่อดูว่า API Key ปัจจุบันถือ scope `accounting:read`, `accounting:draft`, และสิทธิ์ `partner-ledger.manage` หรือไม่ (เซิร์ฟเวอร์จะแยกคีย์ทีมกฎหมายกับทีมบัญชีออกจากกันอย่างเคร่งครัด)

## When to Read Bundled References

อ่านไฟล์ [`references/accounting-workflows-and-redlines.md`](references/accounting-workflows-and-redlines.md) เมื่อต้องการดู:
- รายชื่อเครื่องมือและข้อกำหนดปฏิบัติการ **ครบทั้ง 7 กลุ่ม 34 เครื่องมือ** (`READ` vs `DRAFT/PROOF/APPEND`)
- เงื่อนไขสำคัญรายเครื่องมือจาก Production (`slegal_pv_attach_payment_proof` เฉพาะ `ordinary + vendor`, `slegal_pv_draft_create`, `slegal_bank_statement_import_draft`, `slegal_document_address_correct`, `slegal_accounting_pdf_ensure`, `slegal_wht_certificate_draft_create`, Partner/OMEC `partner-ledger.manage`)
- เกณฑ์ **มาตรา 40(6) วิชาชีพอิสระกฎหมาย (3%)** vs **มาตรา 40(2)** ใน 50 ทวิ / ภ.ง.ด.3 / ภ.ง.ด.53
- **7 Hard Red-Line Locks** ฉบับเต็ม

---

## 7 กลุ่มงานบัญชีหลักและกรอบปลอดภัย (Accounting Domains & Red Lines)

| กลุ่มงาน | Live MCP Tools (`34` เครื่องมือ) | Scope & ข้อกำหนดปฏิบัติการสำคัญ | เส้นแดงเด็ดขาด (Hard Red-Line Lock) |
|---|---|---|---|
| **1. GL / งบทดลอง / ปิดงวด** | `slegal_trial_balance_get`, `slegal_gl_ledger_get`, `slegal_period_close_readiness_get`, `slegal_document_followups_list` (`4 READ`) | `accounting:read` — อ่านงบทดลองรายเดือน/รายปี ตรวจ `Dr == Cr` (`diff`), แยกประเภท และ blockers ก่อนปิดงวด | **READ ONLY เท่านั้น** — ห้ามสร้าง/โพสต์/กลับรายการ GL ห้ามปิด/ล็อก/เปิดงวด |
| **2. RC & PDF** | `slegal_receipt_search`, `slegal_receipt_get` (`2 READ`); `slegal_accounting_pdf_ensure`, `slegal_document_address_correct`, `slegal_receipt_draft_prepare` (`3 Safe`) | `accounting:read` / `accounting:draft` (`pdf_ensure` จำกัด `30/min`; `address_correct` ล็อก `mode="address_only"` ในงวดเปิด `Asia/Bangkok`; `receipt_draft_prepare` แนบสลิป SHA-256 รอคนออกเลขจริงบนเว็บ) | ห้าม `receipt_reverse` ห้ามยืนยันรับเงินอัตโนมัติ ห้ามแก้ตัวลูกค้า (`mode="full"`) ห้ามส่งเอกสารหาลูกค้าอัตโนมัติ |
| **3. เจ้าหนี้ (`AP`)** | `slegal_ap_search`, `slegal_ap_get` (`2 READ`); `slegal_ap_draft_create`, `slegal_ap_draft_update`, `slegal_ap_attach_evidence` (`3 Draft/Append`) | `accounting:read` / `accounting:draft` — สร้าง/แก้ได้เฉพาะ `draft`/`needs_more_evidence` ในงวดเปิด แนบหลักฐาน Append-Only + SHA-256 | **Draft/Append เท่านั้น** — ห้ามอนุมัติ `AP` ห้ามโพสต์ GL ห้ามลบเอกสาร |
| **4. ใบสำคัญจ่าย (`PV`) & สลิป** | `slegal_pv_search`, `slegal_pv_get` (`2 READ`); `slegal_pv_draft_create`, `slegal_pv_attach_payment_proof` (`2 Draft/Proof`) | `accounting:read` / `accounting:draft` — `pv_draft_create` สร้างเฉพาะ `draft` (อนุมัติ/ยกเลิกบน `/accounting/payment-vouchers`); `pv_attach_payment_proof` ใช้ได้เฉพาะ **`ordinary + vendor` PV** เท่านั้น (`employee`/`compensation`/`wht_remittance` ต้องทำบนเว็บ) | สลิปตรวจ SHA-256 ตันที่ `paid_unposted` (`bank_transaction_id=null`, zero GL post) คงล็อก `vendor_agent` / `requireSupplierWhtAgentStatementBound` ห้ามแก้ `PV` ที่โพสต์แล้ว ห้ามโอนเงิน |
| **5. Statement & กระทบยอด** | `slegal_bank_accounts_list`, `slegal_bank_transactions_search`, `slegal_bank_match_suggest` (`3 READ`); `slegal_bank_statement_import_draft` (`1 Draft`) | `accounting:read` / `accounting:draft` — อัปโหลด CSV/TSV/XLSX ผ่าน `slegal_upload_prepare` (`purpose: "bank_statement"`) ก่อนรัน `bank_statement_import_draft` (Staging Preview กันแถวซ้ำเท่านั้น) | **Import Draft & Suggest เท่านั้น** — ห้ามเขียน/แก้/ลบตาราง `bank_transactions` จริง ห้ามกดยืนยันกระทบยอดอัตโนมัติ |
| **6. 50 ทวิ / ภ.ง.ด.3-53 (`WHT`)** | `slegal_wht_close_issues_list`, `slegal_wht_certificate_search`, `slegal_wht_certificate_get` (`3 READ`); `slegal_wht_certificate_draft_create` (`1 Draft`) | `accounting:read` / `accounting:draft` — สร้างร่าง `status="draft"`, `taxFormConfirmed=false` รองรับทั้ง `SECTION_40_6` (3% ทนาย/หุ้นส่วน) และ `SECTION_40_2` (ผู้แนะนำภายนอก) | **Draft เท่านั้น** — ห้ามออกเลขจริง (`issue_wht_certificate`) ห้ามยืนยัน `taxFormConfirmed=true` ห้ามยื่น/จ่ายภาษี RD |
| **7. ค่าตอบแทน / ECP / วางบิล EXP / OMEC** | `slegal_compensation_search`, `slegal_compensation_get`, `slegal_payout_cycle_preview`, `slegal_billable_unbilled_list`, `slegal_partner_ledger_overview_get`, `slegal_unallocated_office_expenses_list` (`6 READ`); `slegal_client_billing_draft_create`, `slegal_supporting_evidence_attach` (`2 Draft/Append`) | `accounting:read` / `accounting:draft` — **`partner_ledger_overview_get` และ `unallocated_office_expenses_list` บังคับสิทธิ์ `partner-ledger.manage` และเป็น READ ONLY 100%** | **OMEC & Partner Ledger เป็น READ ONLY เท่านั้น** — ห้ามอนุมัติ `COMP` ห้ามออก `INV` จริงสำหรับ `EXP` ห้ามสั่งโอน K BIZ |

---

## กฎสากลระดับ Service Layer (Universal Guards)
- **Actor & Audit จริงเสมอ**: ทุกการกระทำต้องผูก `actorId` จริง (ห้าม bypass ด้วยค่าว่าง/ระบบ), ส่ง `idempotencyKey` (ตรวจซ้ำผ่าน `slegal_command_status` หาก Timeout), บันทึก `audit_logs`, ตรวจ RBAC และงวดบัญชีเปิดตามเวลา `Asia/Bangkok`
- **ความถูกต้องระดับสตางค์**: ยอดก่อน VAT, VAT 7%, WHT, และ `Posted GL` ต้องสมดุล **`Dr = Cr` (`diff = 0.00`)** เสมอ
- **ห้ามเผยแพร่ข้อมูลลับ**: ห้ามพิมพ์ `slk_...`, เลขบัญชีเต็ม, เลขบัตรประชาชน 13 หลัก หรือรหัสอ้างอิงภายใน `SL-...` เป็นเลขอ้างอิงหลัก
