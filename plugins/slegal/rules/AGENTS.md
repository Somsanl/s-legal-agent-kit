# S-Legal Workspace Rules

เมื่อผู้ใช้สั่งงานที่เกี่ยวข้องกับสำนวนคดี โปรเจกต์กฎหมาย งานติดตาม คำร้อง/คำสั่งศาล วันนัดศาล อุทธรณ์ สมุดเบอร์โทร คัดเอกสาร DBD ร่างเอกสารกฎหมายภาษาไทย หรือเอกสารการเงินและบัญชี (ใบเสนอราคา ใบแจ้งหนี้ ตั้งเบิกค่าใช้จ่าย ใบเสร็จรับเงิน เจ้าหนี้ ใบสำคัญจ่าย กระทบยอดธนาคาร ภาษีหัก ณ ที่จ่าย ค่าตอบแทน และงบทดลอง):

1. **เลือกสกิลให้ตรงบทบาทก่อนลงมือทำ (LIVE ON PRODUCTION — `95` เครื่องมือ: `2` System + `36` Legal + `57` Accounting/Billing)**:
   - **หมวดระบบ (`2` เครื่องมือ — `context:read`)**: `slegal_whoami`, `slegal_command_status` (ตรวจสิทธิ์และผลคำสั่งเมื่อ Timeout)
   - **หมวดงานทนายความ (`36` เครื่องมือ — `legal:read`, `legal:write`)**:
     - เปิด/อัปเดตแฟ้มงาน คู่ความ ผูกใบเสนอราคาเข้าสำนวน จัดการเอกสารคดี และออกฟอร์มศาล `.docx` -> อ่านสกิล `slegal-case-intake`
     - เช็กงานค้าง ตั้งงาน แก้ไขงาน/ย้ายแท็บ (`slegal_task_edit`) คำสั่งศาล วันนัดศาล อุทธรณ์ เบอร์โทร ปิดแฟ้ม รวมถึง `7` เครื่องมือใหม่ (`slegal_court_service_fee_lookup` 262 ศาล, `slegal_appeal_deadline_upsert` ป.พ.พ. ม.193/8, `slegal_case_document_list` / `slegal_case_document_upload`, `slegal_filing_cancel` soft-cancel, `slegal_case_snapshot_get` พร้อม QT Fee Privacy Gate, และ `slegal_hearing_record_outcome` บันทึกผลหลังนัดแบบ Atomic) -> อ่านสกิล `slegal-work-tracker`
     - ค้นข้อมูลนิติบุคคลและสั่งคัดเอกสาร DBD e-Service -> อ่านสกิล `slegal-dbd-order`
     - ร่างคำฟ้อง คำร้องศาล 3 ส่วน พิสูจน์อักษรภาษาไทย และสร้างไฟล์ `.docx` -> อ่านสกิล `thai-legal-drafting`
   - **หมวดงานบัญชีและการเงิน (`57` เครื่องมือ)**:
     - **Front-Office Billing & EC (`23` เครื่องมือ)**: ใบเสนอราคา (`QT`/`MBA`), ผลอนุมัติลูกค้า, ใบแจ้งหนี้ (`INV`), ค่าใช้จ่ายสำนวน, ตั้งเบิกค่าใช้จ่ายพนักงาน (`EC`), อัปโหลดหลักฐาน, ค้นหาข้อมูลหลัก -> อ่านสกิล `slegal-billing-ops`
     - **Core Accounting & Tax (`34` เครื่องมือ ครบทั้ง `7` กลุ่ม: `22 READ` ภายใต้ `accounting:read` + `12 Safe Draft/Proof/Append` ภายใต้ `accounting:draft`)**: `GL`/งบทดลอง/ปิดงวด, `RC` & PDF, `AP`, `PV` & สลิปจ่าย, Statement & กระทบยอด, `50 ทวิ / ภ.ง.ด.3-53` (`SECTION_40_6` 3% vs `SECTION_40_2`), ค่าตอบแทน/ECP/วางบิล EXP, และ Partner Ledger/OMEC (**READ ONLY** เฉพาะสิทธิ์ `partner-ledger.manage`) -> อ่านสกิล `slegal-accounting-ops`
2. **การอ้างอิงสำนวน**: แสดง `เลขคดีดำ` (`blackCaseNo`) เสมอ (หรือ `ชื่อเรื่อง + ชื่อลูกความ` สำหรับงานก่อนฟ้อง/งานที่ปรึกษา) ห้ามแสดงรหัสภายใน `SL-...` เป็นเลขอ้างอิงหลัก
3. **ห้ามสร้างงานซ้ำเพื่อแก้คำผิดหรือเลื่อนวัน**: ใช้ `slegal_task_edit` สำหรับแก้ไข ย้ายแท็บ ผูกสำนวน หรือยกเลิกงานเดิมเสมอ
4. **รักษาความลับ API Key และ Endpoint**: ห้ามพิมพ์ อ้างอิง หรือส่งคีย์ `slk_...` หรือค่าลับในข้อความตอบกลับ อาร์กิวเมนต์คำสั่ง URL หรือไฟล์ในโปรเจกต์เด็ดขาด (คีย์และ endpoint เก็บเฉพาะใน `~/.slegal/mcp/api_key` และ `~/.slegal/mcp/endpoint` บนเครื่องผู้ใช้เท่านั้น)
5. **เส้นแดงทางบัญชีและการเงิน (7 Red-Line Locks — ห้ามละเมิดเด็ดขาด)**:
   - ห้ามสร้าง/โพสต์/กลับรายการสมุดรายวัน (`GL`) หรือปิด/เปิด/ล็อกงวดบัญชีผ่าน MCP
   - ห้ามกลับรายการใบเสร็จ (`receipt_reverse`) ออกใบเสร็จ/ยืนยันรับเงินอัตโนมัติ เปลี่ยนตัวลูกค้า (`mode="full"`) หรือส่งเอกสารหาลูกค้าโดยพลการ
   - ห้ามอนุมัติ `AP`/`PV` โพสต์ GL ข้าม `bank_transaction_id` แก้ไข `PV` ที่โพสต์แล้ว หรือสั่งโอนเงินธนาคาร (`slegal_pv_attach_payment_proof` ใช้ได้เฉพาะ `ordinary + vendor` PV เท่านั้น ตันที่ `paid_unposted` และคงล็อก `requireSupplierWhtAgentStatementBound`)
   - ห้ามแก้ไขข้อมูล `bank_transactions` จริง หรือกดยืนยันกระทบยอดธนาคารอัตโนมัติ
   - ห้ามออก/ยกเลิก `50 ทวิ` จริง ยืนยัน `taxFormConfirmed=true` หรือยื่น/ชำระภาษีกรมสรรพากรเอง
   - `OMEC` และ `Partner Ledger` เป็น **READ ONLY** เท่านั้น (`partner-ledger.manage`) ห้ามอนุมัติ `COMP` ห้ามออก `INV` จริงสำหรับ `EXP` และห้ามสั่งโอน K BIZ
   - บังคับ `actorId` จริง, `idempotencyKey` (`slegal_command_status`), `audit_logs`, RBAC + งวดบัญชีเปิด `Asia/Bangkok`, ห้าม hard delete, เคารพ `AppealFilingValidationError` / ป.พ.พ. ม.193/8 และ QT Fee Privacy Gate — ตรวจสอบสิทธิ์และเครื่องมือที่มีในคีย์ปัจจุบันผ่าน `slegal_whoami` เสมอ
