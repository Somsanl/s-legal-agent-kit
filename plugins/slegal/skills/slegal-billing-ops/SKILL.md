---
name: slegal-billing-ops
description: Create, search, update, issue, and cancel S-Legal company Quotations (`QT` / monthly retainer `MBA`), Invoices (`INV`), customer acceptance decisions, and own Employee Expense Reimbursement Claims (`EC`) via MCP (`slegal_lookup`, `slegal_quotation_*`, `slegal_invoice_*`, `slegal_intake_*`, `slegal_upload_*`, `slegal_expense_draft_*`, `slegal_case_expense_record`, `slegal_expense_search`, `slegal_draft_*`). Use when the user asks to ออกใบเสนอราคา, แก้ใบเสนอราคา, บันทึกลูกค้าอนุมัติใบเสนอราคา, ออกใบแจ้งหนี้, แก้ใบแจ้งหนี้/ออกเลขใหม่, ออกใบแจ้งหนี้ที่ปรึกษารายเดือน (ประจำเดือน...), ยกเลิกใบแจ้งหนี้, บันทึกค่าใช้จ่ายสำนวน, or ตั้งเบิกค่าใช้จ่ายพนักงานพร้อมแนบสลิป/ใบเสร็จ.
---

# S-Legal Billing, Quotations, Invoices & Expense Claims (Live MCP)

จัดการเอกสารการค้าของสำนักงาน (ใบเสนอราคา `QT`/`MBA`, ใบแจ้งหนี้ `INV`) และการตั้งเบิกค่าใช้จ่ายพนักงาน/ค่าใช้จ่ายสำนวน (`EC` หน้า `/accounting/employee-claims`) ผ่าน **S-Legal MCP** ตามกฎความถูกต้องทางบัญชี ภาษีมูลค่าเพิ่ม (`VAT`) ภาษีหัก ณ ที่จ่าย (`WHT`) และ Optimistic Concurrency (`expectedUpdatedAt`)

> สำหรับงานบัญชีหลักครบทั้ง 7 กลุ่มที่เปิดใช้งานจริงบน Production แล้ว (`34` เครื่องมือ: `RC` ใบเสร็จรับเงิน & PDF, `AP` เจ้าหนี้, `PV` ใบสำคัญจ่าย & สลิป, กระทบยอดธนาคาร, `50 ทวิ / ภ.ง.ด.3-53`, รอบจ่ายเงิน 10/25 & วางบิล `EXP`, ค่าตอบแทนทนาย, `Partner Ledger / OMEC`, และงบทดลอง/GL) ให้อ่านสกิล **`slegal-accounting-ops`**

## When to Read Bundled References

อ่านไฟล์ [`references/billing-workflows.md`](references/billing-workflows.md) เมื่อต้องการดู:
- โครงสร้าง JSON รายบรรทัดของ `slegal_quotation_draft_save`, `slegal_invoice_create`, `slegal_invoice_update`, และ `slegal_expense_draft_create`
- มาตรฐานการเขียนหัวข้อและรายการสำหรับ **ใบแจ้งหนี้ค่าที่ปรึกษากฎหมายรายเดือน (`MBA`)**
- ขั้นตอนการอัปโหลดหลักฐานใบเสร็จ/สลิป (`slegal_upload_prepare` -> `PUT` -> `slegal_upload_finalize`) สำหรับตั้งเบิก `EC`

---

## Core Workflows & Rules

### 1. ค้นหาฐานข้อมูลลูกค้าและบริการก่อนเสมอ (`slegal_lookup`)

ก่อนสร้างใบเสนอราคาหรือใบแจ้งหนี้ ให้เรียก `slegal_lookup`:
- `kind: "customers"` (ค้นชื่อลูกค้า/บริษัท เพื่อดึง `partyId`, `legal_name`, `tax_id`)
- `kind: "services"` (ค้นรายการบริการมาตรฐาน เพื่อดึง `serviceItemId`, `unit_name`, `default_unit_price`, `default_vat_rate`, `default_wht_rate` — ทั้งนี้อัตราภาษีเป็นค่าแนะนำ ต้องตรวจตามข้อตกลงจริงเสมอ)

### 2. ใบเสนอราคา (`Quotations` — `QT` / `MBA`)

1. **ค้นหาและอ่านรายละเอียด**: ใช้ `slegal_quotation_search` และ `slegal_quotation_get`
2. **สร้างร่างใบเสนอราคาใหม่ (`slegal_quotation_draft_save`)**:
   - ลูกค้าเดิมในระบบ: ส่ง `customer: { partyId, name, taxId?, address? }`
   - ลูกค้าใหม่: เว้น `partyId` และส่ง `customer: { name, taxId, address }` (ต้องมี `taxId` หรือ `address` อย่างน้อยหนึ่งอย่าง ระบบจะขึ้นทะเบียนลูกค้าให้อัตโนมัติ)
   - `unitPrice` ส่งเป็นสตริงทศนิยมไม่เกิน 2 ตำแหน่ง (เช่น `"15000.00"`)
3. **แก้ไขร่างใบเสนอราคา (`slegal_quotation_draft_update`)**:
   - เรียก `slegal_draft_get({ kind: "quotation", recordId })` ก่อนเสมอ แล้วส่งค่า `updatedAt` ระดับไมโครวินาทีกลับไปใน `expectedUpdatedAt` (แก้ไขได้เฉพาะใบที่ยังเป็น `draft` และยังไม่ผูกธุรกรรมการเงิน)
4. **บันทึกผลอนุมัติของลูกค้า (`slegal_quotation_record_decision`)**:
   - เมื่อลูกค้าตอบตกลง/ปฏิเสธ (ทางไลน์ โทรศัพท์ อีเมล หรือเซ็นใบเสนอราคากลับมา) เรียก `slegal_quotation_record_decision` (`decision: "approved" | "declined" | "no_response"`, `channel`, `customerContactName`, พร้อมแนบไฟล์หลักฐาน `attachments[]` ได้)
   - หากต้องการผูกใบเสนอราคาเข้าสำนวนคดี ให้ใช้ `slegal_case_open_or_bind_quotation`

### 3. ใบแจ้งหนี้ (`Invoices` — `INV`) & งานที่ปรึกษารายเดือน

1. **ค้นหาและอ่านใบแจ้งหนี้**: ใช้ `slegal_invoice_search` และ `slegal_invoice_get` (คืนทั้งยอดเงิน สถานะ และ `pdfUrl`)
2. **ออกใบแจ้งหนี้จริงพร้อมเลข `INV...` ทันที (`slegal_invoice_create`)**:
   - ค่าเริ่มต้น `issueNow: true` จะออกเลข `INV...` และล็อกสถานะเป็น `issued` พร้อมใช้งานทันที (ส่ง `issueNow: false` เฉพาะเมื่อผู้ใช้สั่งให้เซฟเป็นร่าง `draft` ก่อน)
   - ออกอ้างอิงจากใบเสนอราคาได้โดยตรงผ่าน `sourceQuotationId` หรือ `sourceQuotationNo` (เลือกเฉพาะบางงวด/บางบรรทัดได้ด้วย `sourceLineOrders` หรือ `sourceLineIds`) หรือส่ง `lines[]` รายการใหม่ได้
   - **กฎเหล็กสำหรับใบแจ้งหนี้ค่าที่ปรึกษารายเดือน (`Retainer / MBA`)**:
     - ต้องระบุงวดเดือนและปี พ.ศ. ให้ชัดเจนทั้งใน `subject` และ `lines[].description` ตามรูปแบบสำนักงาน เช่น:
       - `subject`: `"ค่าที่ปรึกษากฎหมายประจำเดือน พฤศจิกายน 2569"`
       - `lines[0].description`: `"ค่าที่ปรึกษากฎหมายรายเดือน ประจำเดือน พฤศจิกายน 2569"`
     - หากลูกค้าเดิมมีใบแจ้งหนี้เดือนก่อนหน้า ให้ใช้ `slegal_invoice_search` + `slegal_invoice_get` ดูตัวอย่าง `subject`, `unitPrice`, `vatRate`, `whtRate`, และ `terms` ของลูกค้ารายนั้นก่อนเสมอเพื่อความสม่ำเสมอ
3. **แก้ไขใบแจ้งหนี้ (`slegal_invoice_update`)**:
   - ถ้าใบแจ้งหนี้ยังเป็น `draft`: แก้ไขในใบเดิมได้เลย (อ่าน `slegal_invoice_get` ก่อนเพื่อเช็กสถานะ และสั่ง `issueNow: true` เพื่อออกเลขจริงพร้อมกันได้)
   - ถ้าใบแจ้งหนี้ออกเลข `issued` ไปแล้วแต่ยังไม่ได้รับชำระเงิน: ต้องส่ง `reissue: true` พร้อมระบุ `reason` ระบบจะยกเลิกใบเดิมตามหลักบัญชีและออกใบแจ้งหนี้เลขใหม่ที่แก้ไขแล้วให้ทันที
4. **ออกเลขจากร่าง / ยกเลิกใบแจ้งหนี้**: ใช้ `slegal_invoice_issue` หรือ `slegal_invoice_cancel` (พร้อม `reason`)

### 4. การตั้งเบิกค่าใช้จ่ายพนักงานและค่าใช้จ่ายสำนวน (`EC` & `Case Expense`)

> ช่องทาง MCP รองรับ **ร่างตั้งเบิกจ่ายคืนพนักงานเจ้าของคีย์เอง** (`/accounting/employee-claims`) และ **การบันทึกค่าใช้จ่ายสำนวนแบบจุดเดียว** (`slegal_case_expense_record`) โดยต้องมีไฟล์ใบเสร็จ/สลิปแนบครบทุกรายการ และไม่มีการอนุมัติจ่ายหรือลงบัญชีอัตโนมัติ

1. เรียก `slegal_intake_get({})` ก่อนเสมอเพื่อตรวจว่ามีแฟ้มรับหลักฐานเดิมค้างอยู่หรือไม่
   - หากมีแฟ้มเดิมที่มีไฟล์ค้างอยู่ ห้ามล้างเอง — ให้อ่านบริบทและถามผู้ใช้ว่าจะทำต่อใน `intakeId` เดิม หรือสั่งปิดแฟ้มเดิมด้วย `slegal_intake_cancel` (พร้อม `expectedUpdatedAt` + `reason`)
2. เรียก `slegal_intake_create` เพื่อเปิด/ใช้แฟ้มว่างรับหลักฐาน (`intakeId`)
3. สำหรับแต่ละไฟล์สลิป/ใบเสร็จ (`.pdf`, `.jpg`, `.png`, `.webp` ไม่เกิน 3 MB ต่อไฟล์):
   - คำนวณ `sha256` และขนาดไฟล์จริง -> เรียก `slegal_upload_prepare` -> อัปโหลดไบต์ไฟล์ด้วย `PUT` ไปยัง `upload.uploadPath` -> เรียก `slegal_upload_finalize`
4. เรียก `slegal_expense_draft_create` (หรือ `slegal_case_expense_record` เมื่อต้องการผูกสำนวน/ตัดสินใจ `rechargeDecision`: `'recharge' | 'included' | 'non_billable'`) โดยอ้างอิง `intakeId` และ `evidenceUploadIds` ครบทุกไฟล์ในแฟ้ม
5. หากต้องการค้นหาสถานะการเบิกคืนหรือการเรียกเก็บลูกค้า ใช้ `slegal_expense_search` และหากต้องการแก้ไขหรือยกเลิกร่าง `EC` ที่ยังไม่ส่งอนุมัติ ให้เรียก `slegal_draft_get({ kind: "expense", recordId })` เอาค่า `updatedAt` มาส่งใน `slegal_expense_draft_update` หรือ `slegal_draft_cancel`

### 5. ความปลอดภัยและการกู้คืนคำสั่ง (`Idempotency & Timeout Recovery`)

- ทุกคำสั่งแก้ไขข้อมูลต้องสร้าง `idempotencyKey` เฉพาะคำสั่งนั้น และใช้คีย์เดิมซ้ำเมื่อต้อง Retry
- หากคำสั่งเกิด Timeout ห้ามยิงสร้างซ้ำด้วยคีย์ใหม่ทันที ให้ตรวจผลด้วย `slegal_command_status({ commandId })` หรือค้นหาเอกสารก่อนเสมอ
