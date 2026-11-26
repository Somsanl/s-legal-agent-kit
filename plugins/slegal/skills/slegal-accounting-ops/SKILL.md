---
name: slegal-accounting-ops
description: Guide and safeguard S-Legal core accounting & Thai tax operations across 7 accounting domains — GL/Trial Balance/Period Close, Receipts (`RC`) & PDF, Accounts Payable (`AP`), Payment Vouchers (`PV`) & Slips, Bank Statement & Reconciliation, Withholding Tax (`50 ทวิ`, `ภ.ง.ด.3`, `ภ.ง.ด.53`, Section 40(6) 3% legal profession vs Section 40(2) external referral), and Compensation/10-25 Payout Cycles/EXP/OMEC. Maps Live Phase-1 MCP (`54` tools via `slegal-billing-ops`) vs Phase-2 Planned Accounting MCP (`7` groups, `34` tools: `22 READ + 12 Safe Draft/Proof/Append`) and enforces 7 hard Accounting Red-Line locks. Use when the user asks about ใบเสร็จรับเงิน (RC), เจ้าหนี้ (AP), ใบสำคัญจ่าย (PV), 50 ทวิ / ภ.ง.ด.3-53, รอบเบิกจ่าย 10/25, ค่าตอบแทนทนาย, OMEC, กระทบยอดธนาคาร, or งบทดลอง.
---

# S-Legal Accounting, Thai Tax (WHT/VAT), Payout Cycles & Trial Balance

คู่มือปฏิบัติงานบัญชีและภาษีอากรสำหรับ **ทีมบัญชี S-Legal** ครอบคลุมครบทั้ง **7 กลุ่มงานบัญชีหลัก** พร้อมขอบเขต **Phase-1 Live MCP (54 เครื่องมือ)** เทียบกับ **Phase-2 Planned Accounting MCP (7 กลุ่ม 34 เครื่องมือ: `22 READ + 12 Safe Draft/Proof/Append`)** และ **เส้นแดง 7 ข้อ (Hard Red-Line Locks)**

## สถานะเครื่องมือจริง: Phase-1 Live vs Phase-2 Planned

> **กฎสำคัญ — ห้ามแต่งหรือเรียกเครื่องมือที่เซิร์ฟเวอร์ยังไม่ได้เปิดใช้งาน!**

1. **ใช้งานผ่าน MCP ได้จริงวันนี้ (Phase-1 Live — รวม `54` เครื่องมือ)**:
   - ระบบ (`2`): `slegal_whoami`, `slegal_command_status`
   - บัญชี/วางบิล/ตั้งเบิก (`23`): `QT`/`MBA`, `INV`, `EC`, `case_expense`, `lookup`, `intake`, `upload` -> อ่านสกิล **`slegal-billing-ops`**
   - งานกฎหมาย/คดี (`29`): ดู `slegal-case-intake`, `slegal-work-tracker`, `slegal-dbd-order`
2. **แผนขยาย Accounting MCP ระยะที่ 2 (`7` กลุ่ม `34` เครื่องมือ — วันนี้ปฏิบัติผ่านหน้าเว็บ S-Legal)**:
   - แบ่งเป็น **`22 READ` + `12 Safe Draft/Proof/Append`** (`1 PREPARE_CACHE`, `1 SAFE_WRITE`, `9 DRAFT_WRITE`, `1 PROOF_WRITE`)
   - **บทบาทของ AI วันนี้**: ช่วยอ่าน/ตรวจหลักฐาน สลิป ใบกำกับภาษี คำนวณ VAT/WHT ให้ตรงถึงระดับสตางค์ ตรวจจุดติดขัด และแนะนำขั้นตอนบนหน้าเว็บ S-Legal ตาม 7 กลุ่มด้านล่างโดยไม่ละเมิด Red-Line ใด ๆ

## When to Read Bundled References

อ่านไฟล์ [`references/accounting-workflows-and-redlines.md`](references/accounting-workflows-and-redlines.md) เมื่อต้องการดู:
- รายชื่อเครื่องมือวางแผน **Phase-2 ทั้ง 7 กลุ่ม 34 เครื่องมือ** และข้อจำกัดของแต่ละกลุ่ม
- เกณฑ์ **มาตรา 40(6) วิชาชีพอิสระกฎหมาย (3%)** vs **มาตรา 40(2)** ใน 50 ทวิ / ภ.ง.ด.3 / ภ.ง.ด.53
- กฎรอบเบิกจ่าย **วันที่ 10 และ 25**, `vendor_agent` / `requireSupplierWhtAgentStatementBound`, และ **7 Hard Red-Line Locks** ฉบับเต็ม

---

## 7 กลุ่มงานบัญชีหลักและกรอบปลอดภัย (Accounting Domains & Red Lines)

| กลุ่มงาน | หน้าเว็บ S-Legal วันนี้ | แผน Phase-2 MCP (`34` เครื่องมือ) | เส้นแดงเด็ดขาด (Hard Red-Line Lock) |
|---|---|---|---|
| **1. GL / งบทดลอง / ปิดงวด** | `/accounting/journals`, `/accounting/ledger`, `/accounting/reports` | `4 READ` (`slegal_trial_balance_get`, `slegal_gl_ledger_get`, `slegal_period_close_readiness_get`, `slegal_document_followups_list`) | **READ ONLY เท่านั้น** — ห้ามสร้าง/โพสต์/กลับรายการ GL ห้ามปิด/ล็อก/เปิดงวด |
| **2. RC & PDF** | `/accounting/receipts`, `/accounting/monthly-billing` | `2 READ + 3 Safe` (`receipt_search/get`, `pdf_ensure`, `address_correct`, `receipt_draft_prepare`) | ห้าม `receipt_reverse` ห้ามยืนยันรับเงินอัตโนมัติ ห้ามแก้ชื่อลูกค้า (`mode="full"`) ห้ามส่งหาลูกค้าอัตโนมัติ (แก้ได้เฉพาะ `address_only` ในงวดเปิด) |
| **3. เจ้าหนี้ (`AP`)** | `/accounting/payables`, `/accounting/purchase-document-register`, `/accounting/vendors` | `2 READ + 3 Draft/Append` (`ap_search/get`, `ap_draft_create/update`, `ap_attach_evidence`) | **Draft/Append เท่านั้น** — ห้ามอนุมัติ `AP` ห้ามโพสต์ GL ห้ามลบเอกสาร |
| **4. ใบสำคัญจ่าย (`PV`) & สลิป** | `/accounting/payment-vouchers` | `2 READ + 2 Draft/Proof` (`pv_search/get`, `pv_draft_create`, `pv_attach_payment_proof`) | สลิปตรวจ SHA-256 ตันที่ `paid_unposted` เคารพล็อก `vendor_agent` / `requireSupplierWhtAgentStatementBound` ห้ามโพสต์ GL โดยไม่มี `bank_transaction_id` จริง ห้ามแก้ `PV` ที่โพสต์แล้ว ห้ามโอนเงิน |
| **5. Statement & กระทบยอด** | `/accounting/reports` / หน้ากระทบยอดธนาคาร | `3 READ + 1 Import Draft` (`bank_accounts_list`, `bank_transactions_search`, `bank_match_suggest`, `bank_statement_import_draft`) | **Import Draft เท่านั้น** — ห้ามแก้ตาราง `bank_transactions` จริง ห้ามกดยืนยันกระทบยอดอัตโนมัติ |
| **6. 50 ทวิ / ภ.ง.ด.3-53 (`WHT`)** | `/accounting/withholding-certificates`, `/accounting/tax` | `3 READ + 1 Draft` (`wht_close_issues_list`, `wht_certificate_search/get`, `wht_certificate_draft_create`) | **Draft เท่านั้น** (รวม `SECTION_40_6` ทนาย/หุ้นส่วน 3% และ `SECTION_40_2` ผู้แนะนำภายนอก) — ห้ามออกเลขจริง (`issue_wht_certificate`) ห้ามยืนยัน `taxFormConfirmed=true` ห้ามยื่น/จ่ายภาษี RD |
| **7. ค่าตอบแทน / ECP / วางบิล EXP / OMEC** | `/accounting/compensation`, `/accounting/payout-cycles`, `/accounting/expense-claims` | `6 READ + 2 Draft/Append` (`compensation_search/get`, `payout_cycle_preview`, `billable_unbilled_list`, `client_billing_draft_create`, `supporting_evidence_attach`, `partner_ledger_overview_get`, `unallocated_office_expenses_list`) | **OMEC & Partner Ledger เป็น READ ONLY เท่านั้น** (`partner-ledger.manage`) — ห้ามอนุมัติ `COMP` ห้ามออก `INV` จริงสำหรับ `EXP` ห้ามสั่งโอน K BIZ |

---

## กฎสากลระดับ Service Layer (Universal Guards)
- **Actor & Audit จริงเสมอ**: ทุกการกระทำต้องผูก `actorId` จริง (ห้าม bypass ด้วยค่าว่าง/ระบบ), มี `idempotencyKey`, บันทึก `audit_logs`, ตรวจ RBAC และงวดบัญชีเปิดตามเวลา `Asia/Bangkok`
- **ความถูกต้องระดับสตางค์**: ยอดก่อน VAT, VAT 7%, WHT, และ `Posted GL` ต้องสมดุล **`Dr = Cr` (`diff = 0.00`)** เสมอ
- **ห้ามเผยแพร่ข้อมูลลับ**: ห้ามพิมพ์ `slk_...`, เลขบัญชีเต็ม, เลขบัตรประชาชน 13 หลัก หรือรหัสอ้างอิงภายใน `SL-...` เป็นเลขอ้างอิงหลัก
