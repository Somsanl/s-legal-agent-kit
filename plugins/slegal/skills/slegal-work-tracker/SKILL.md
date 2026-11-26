---
name: slegal-work-tracker
description: Manage daily S-Legal legal operations via MCP — Follow-up Desk queues (`slegal_legal_work_queue`), creating/updating/editing/moving/cancelling tasks (`slegal_task_create`, `slegal_task_add_update`, `slegal_task_edit`), court filings and orders (`slegal_filing_record`, `slegal_filing_edit`, `slegal_filing_update_order`, `slegal_filing_attach_pdf`), court hearing schedules and auto-prep tasks (`slegal_court_schedule_list`, `slegal_court_schedule_upsert`), appeal/supreme deadlines and extensions (`slegal_appeal_status_get`, `slegal_appeal_extension_record`), phonebook contacts (`slegal_phonebook_search`, `slegal_phonebook_upsert`), and closing/reopening cases (`slegal_case_close`, `slegal_case_reopen`). Use when the user asks to เช็กงานค้าง, ตั้งงาน, แก้ไขงาน, ย้ายแท็บงาน, เลื่อนงาน, ยกเลิกงาน, บันทึกผลตามคำสั่งศาล, แนบ PDF คำร้อง/คำสั่งศาล, ลงนัดศาล/เลื่อนนัดศาล, ขยายอุทธรณ์/ฎีกา, เมมเบอร์โทรห้องงานศาล, or ปิดแฟ้มคดี.
---

# S-Legal Work Tracker, Schedules, Appeals & Follow-up Desk

จัดการงานติดตามรายวัน คำร้องและคำสั่งศาล วันนัดพิจารณา กำหนดอุทธรณ์/ฎีกา และสมุดเบอร์โทรผ่าน **S-Legal MCP** โดยรักษาตัวเลขแจ้งเตือนบนเมนูซ้าย **`งานที่ต้องติดตาม`** (`/follow-up`) และปฏิทินกลาง (`/calendar`) ให้ตรงความจริงเสมอ

> **กฎการอ้างอิงสำนวน**: แสดง `เลขคดีดำ` (`blackCaseNo`) เสมอ (หรือ `ชื่อเรื่อง + ชื่อลูกความ` หากยังไม่มีเลขคดีดำ) ห้ามใช้รหัสภายใน `SL-...` เป็นเลขอ้างอิงหลัก และเรียก `slegal_case_search` เพื่อหา `caseId` ก่อนเสมอ

## When to Read Bundled References

อ่านไฟล์ [`references/tab-routing-and-tools.md`](references/tab-routing-and-tools.md) เมื่อต้องการตรวจตารางจับคู่ `taskCategory` เข้าแต่ละแท็บของ `/follow-up`, ตัวเลือก `orderStatus` ของคำสั่งศาล, การแนบไฟล์ PDF, หรือรายละเอียดพารามิเตอร์เชิงลึกของแต่ละคำสั่ง

---

## Core Operating Rules

### 1. เลือกหมวดงาน (`taskCategory`) ให้ลงถูกแท็บในหน้า `/follow-up`

| งานที่ต้องการติดตาม | ค่า `taskCategory` ที่ต้องส่ง | แท็บที่แสดงใน `/follow-up` |
|---|---|---|
| ร่างคำฟ้อง / คำให้การ / คำร้อง / สัญญา / โนติส / เตรียมพยานก่อนนัด | `drafting`, `document_prep`, `evidence`, `court_prep` | **`ร่างคำคู่ความ/เตรียมคดี`** |
| โทรตามคำสั่งศาล / ตามหมาย / ประสานเจ้าหน้าที่ศาล / ตามทนายคู่กรณี | `court_followup`, `filing_followup`, `opposing_followup` | **`จนท.ศาล/คู่กรณี`** |
| รอเอกสารจากลูกความ / แจ้งความคืบหน้าลูกความ / ตามผลใบเสนอราคา | `client_followup`, `quotation_followup`, `case_setup` | **`ใบเสนอราคา/ลูกค้า`** |
| สืบทรัพย์ / ยึดอายัดทรัพย์ / ประสานบังคับคดี / คัดถ่ายคำพิพากษา | `enforcement_task`, `enforcement` | **`บังคับคดี/คัดเอกสาร`** |
| งานธุรการสำนักงานทั่วไป | `office_task`, `other` | **`ทั้งหมด`** |

### 2. แยกใช้ 3 คำสั่งงานติดตามให้ถูก (ห้ามสร้างงานซ้ำเพื่อแก้คำผิดหรือเลื่อนวัน!)

1. **ตั้งงานชิ้นใหม่ (`slegal_task_create`)**: ใช้เฉพาะเมื่องานชิ้นนั้นยังไม่มีอยู่ในระบบ (ตรวจด้วย `slegal_legal_work_queue` หรือ `slegal_case_work_get` ก่อนหากไม่แน่ใจ)
2. **บันทึกผลการตามงานรายรอบ (`slegal_task_add_update`)**:
   - ตามรอบนี้แล้วแต่ยังไม่จบ (เช่น เจ้าหน้าที่แจ้งให้โทรใหม่สัปดาห์หน้า) -> ส่ง `followUpMode: "continuous"` (ระบบนับรอบตามงานและเลื่อนวันนัดตามให้อัตโนมัติ `+3 วันทำการ` เว้นแต่ระบุ `nextFollowUpAt` / `snoozeDays`)
   - งานเสร็จสิ้นแล้ว -> ส่ง `followUpMode: "complete"` (`status = "done"`, ตัวเลขแจ้งเตือนบนเมนู `งานที่ต้องติดตาม` ลดลงทันที)
   - หากได้ชื่อเจ้าหน้าที่ เบอร์โทร หรือเบอร์ต่อ (`contactPerson`, `contactPhone`, `contactExt`) ให้ส่งแนบไปด้วยทุกครั้ง ระบบจะเมมลงสมุดเบอร์โทรให้อัตโนมัติ
3. **แก้ไขงาน ย้ายแท็บ ผูกสำนวน หรือยกเลิกงาน (`slegal_task_edit`)**:
   - **แก้ไขรายละเอียด/ย้ายแท็บ/เปลี่ยนคนรับผิดชอบ/เลื่อนวัน/ผูก `caseId` ย้อนหลัง**: ใช้ `action: "update"`
   - **ยกเลิกงานที่สั่งผิดหรือซ้ำ (`action: "cancel"`)**: ทำ Soft-Cancel (`status = "cancelled"`) เก็บประวัติ Audit Trail และตัดออกจากตัวเลขแจ้งเตือนเมนูซ้ายทันที
   - **เปิดงานที่ปิด/ยกเลิกไปแล้วกลับมาทำต่อ (`action: "reopen"`)**: คืนสถานะเป็น `open`

### 3. การยื่นคำร้องและติดตามคำสั่งศาล (`slegal_filing_*`)

- **ยื่นคำร้องใหม่**: เรียก `slegal_filing_record` (ผูก `caseId` หรือบันทึกเป็นคำร้องลอยด้วย `unlinkedClientName` + `unlinkedCourtName` ก่อนได้) ค่าเริ่มต้นตั้งวันตามคำสั่งศาล `+3 วันทำการ` และแนบไฟล์ PDF คำร้องได้ในคำสั่งเดียว (`pdfFilePath` หรือ `pdfBase64` + `pdfFileName`)
- **อัปเดตผลตามคำสั่งศาล**: เรียก `slegal_filing_update_order`
  - ศาลยังไม่มีคำสั่ง -> `mode: "follow_up"` (เลื่อนวันตามรอบหน้า)
  - ศาลมีคำสั่งแล้ว -> `mode: "record_order"` พร้อม `orderStatus` (`granted`, `partially_granted`, `rejected`, `revise_required`, `pending_copy_or_service` ฯลฯ), `orderSummary`, `grantedUntil` (ถ้าเป็นคำร้องขอขยายเวลา) และตั้งงานต่อเนื่องได้ผ่าน `createNextTaskTitle` + `createNextTaskDueAt`
- **แก้ไขหัวข้อคำร้องหรือผูกสำนวนย้อนหลัง**: เรียก `slegal_filing_edit`
- **แนบไฟล์ PDF คำร้อง/คำสั่งศาลเพิ่มเติม**: เรียก `slegal_filing_attach_pdf` (`target: "filing" | "order" | "case_document"`)

### 4. การลงวันนัดศาลและงานเตรียมคดีอัตโนมัติ (`slegal_court_schedule_*`)

- **เช็กตารางนัด**: เรียก `slegal_court_schedule_list` (กรองตาม `caseId`, ช่วงวันที่ `fromDate`–`toDate`, หรือชื่อทนาย `lawyerKeyword`)
- **ลงนัดใหม่ / เลื่อนวันนัด / บันทึกผลนัด / ยกเลิกนัด**: เรียก `slegal_court_schedule_upsert`
  - บันทึกลงตารางนัดศาล ขึ้นแสดงทั้งในหน้าสำนวน (`/cases/{id}/court`) และปฏิทินกลาง (`/calendar`) พร้อมซิงค์ `next_action_at` ของสำนวนอัตโนมัติ
  - **Auto-Prep Task**: เมื่อลงนัดในอนาคต ระบบสร้างงานเตรียมคดีหมวด `document_prep` (แท็บ `ร่างคำคู่ความ/เตรียมคดี`) เตือนล่วงหน้า `prepDaysBefore` วัน (ค่าเริ่มต้น `7` วัน) ให้อัตโนมัติ และหากเลื่อนหรือยกเลิกวันนัด (`action: "cancel"`) งานเตรียมคดีที่ผูกไว้จะเลื่อนหรือยกเลิกตามทันที

### 5. กำหนดอุทธรณ์/ฎีกา สมุดเบอร์โทร และการปิดแฟ้ม

- **อุทธรณ์/ฎีกา**: เรียก `slegal_appeal_status_get` เพื่อตรวจวันครบอายุอุทธรณ์/ฎีกา และใช้ `slegal_appeal_extension_record` เพื่อบันทึกคำร้องขอขยายระยะเวลาหรือบันทึกคำสั่งศาลอนุญาต (`grantedUntil`) โดยระบบเชื่อมเข้าคิวติดตามคำสั่งศาลให้อัตโนมัติ
- **สมุดเบอร์โทร (`/phonebook`)**: ค้นหาเบอร์และเบอร์ต่อด้วย `slegal_phonebook_search` และเมม/แก้เบอร์โดยตรงด้วย `slegal_phonebook_upsert` (`category: "court" | "agency" | "client" | "opposing" | "other"`, `extension`)
- **ปิดแฟ้ม / เปิดแฟ้มใหม่**: `slegal_case_close` **ต้องถามให้ผู้ใช้ยืนยันชัดเจนก่อนเสมอ** แล้วจึงส่ง `confirm: true` (ปิดงานค้างทั้งหมดและนำออกจากคิวติดตาม) ส่วนการเปิดแฟ้มกลับมาใช้ `slegal_case_reopen`

### 6. ชุดติดตามคดีหลังยื่นฟ้องครบ 6 ด่านมาตรฐาน (Post-Filing 6-Gate Checklist)

เมื่อยื่นฟ้องคดีใหม่แล้ว ให้ตั้งและไล่ติดตามให้ครบทั้ง **6 ด่าน** ลง S-Legal (`/follow-up`) คู่กับการตรวจสถานะคดีจากระบบศาล (ตรวจด้วย `slegal_case_work_get` ก่อนเสมอเพื่อไม่สร้างงานซ้ำ):
1. **ด่าน 1 — ศาลรับคำฟ้องหรือไม่ (`court_followup`):** ติดตามคำสั่งรับฟ้อง/แก้ฟ้อง บันทึกเลขคดีดำจริง และลงวันนัดแรกใน `slegal_court_schedule_upsert`
2. **ด่าน 2 — ส่งหมายเรียกและสำเนาคำฟ้องได้หรือไม่ (`court_followup`):** ตามผลการนำส่งหมาย (ส่งได้ / ปิดหมาย / ส่งไม่ได้ต้องรีบทำคำแถลงที่อยู่ใหม่หรือคำร้องประกาศสื่ออิเล็กทรอนิกส์)
3. **ด่าน 3 — จำเลยยื่นคำให้การหรือไม่ (`court_followup` / `drafting`):** ตรวจวันครบกำหนดยื่นคำให้การ (15 วันหลังรับหมาย หรือ 30 วันหลังปิดหมาย + ป.พ.พ. ม.193/8); หากจำเลยไม่ยื่นเตรียมคำร้องขอให้ชนะคดีขาดนัด หากยื่นฟ้องแย้งตั้งกำหนดยื่นคำให้การแก้ฟ้องแย้งทันที
4. **ด่าน 4 — คู่ความอีกฝ่ายยื่นเอกสาร/คำร้อง/คำแถลงอะไรเข้ามาหรือไม่ (`court_followup`):** ตรวจรายการยื่นเอกสารล่าสุดจากระบบศาลก่อนวันนัดและทุกสัปดาห์ เพื่อไม่ให้พลาดคำร้องขอเลื่อน/ขอขยาย/บัญชีพยานเพิ่มของอีกฝ่าย
5. **ด่าน 5 — ติดตามการยื่นบันทึกถ้อยคำแทนการซักถามล่วงหน้า (`document_prep` / `court_followup`):** ตรวจตามรายงานกระบวนพิจารณาว่าศาลสั่งส่งล่วงหน้า **≥ 7 วันก่อนสืบพยาน** หรือไม่ (ติดตามทั้งการส่งของฝ่ายเราและตรวจรับสำเนาของฝ่ายตรงข้าม)
6. **ด่าน 6 — ติดตามกำหนดนัดฟังคำพิพากษา (`court_followup`):** ติดตามวันอ่านคำพิพากษา บันทึกผลและเลขคดีแดง และเริ่มนับกำหนดอุทธรณ์/ฎีกา 1 เดือน (`slegal_appeal_status_get`) ทันทีหลังศาลอ่านคำพิพากษา

### 7. เครื่องมืองานกฎหมายในแผน Phase-2 (Planned — ห้ามเรียกใช้จนกว่าจะเปิดบนเซิร์ฟเวอร์)
- `slegal_court_service_fee_lookup` (`READ`), `slegal_case_document_list` (`READ`), `slegal_case_snapshot_get` (`READ` พร้อม QT Fee Privacy Gate)
- `slegal_appeal_deadline_upsert` (`WRITE`, ตรวจ `AppealFilingValidationError` & ป.พ.พ. ม.193/8), `slegal_case_document_upload` (`WRITE`, ≤10 MiB + malware/SHA-256), `slegal_filing_cancel` (`WRITE` soft-cancel), `slegal_hearing_record_outcome` (`WRITE` atomic หลังนัดศาล)
