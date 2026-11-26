# คู่มืออ้างอิงคำสั่งและการจัดหมวดหมู่ `slegal-work-tracker`

## 1. ความหมายของ `followUpBucket` ใน `slegal_legal_work_queue`

เมื่อเรียก `slegal_legal_work_queue` ระบบจำแนกทุกรายการออกเป็น 3 ตะกร้า (ตรงกับตัวเลขแจ้งเตือนบนเมนูซ้าย **`งานที่ต้องติดตาม`**):
- **`due_now` (`ค้างต้องตามรอบนี้`)**: งานหรือคำร้องที่ยังไม่มีวันนัดตาม, ถึงกำหนดนัดตามแล้ว (`followUpAt <= วันนี้`), หรือเลยกำหนดส่ง (`dueAt <= วันนี้`) -> **เป็นตัวเลขหลักที่แสดงบน Badge เมนู `งานที่ต้องติดตาม`**
- **`continuous` (`ตามรอบนี้แล้ว รอรอบถัดไป`)**: งานที่เพิ่งตามไปแล้วและตั้งวันนัดตามรอบหน้าไว้ในอนาคต (`followUpAt > วันนี้`)
- **`completed` (`เสร็จสิ้นแล้ว`)**: งานที่ `status = 'done'` หรือคำร้องที่ได้คำสั่งศาลครบถ้วนแล้ว (ซ่อนโดยค่าเริ่มต้นเมื่อ `stage = "all_active"`)

---

## 2. ตารางสถานะคำสั่งศาล (`orderStatus`) สำหรับ `slegal_filing_update_order` / `slegal_filing_edit` / `slegal_filing_cancel`

| ค่า `orderStatus` | ความหมายในระบบ | คิวติดตามคำสั่งศาลปิดจบหรือไม่ |
|---|---|---|
| `pending_order` | อยู่ระหว่างรอคำสั่งศาล | **ยังเปิดอยู่** (ต้องตามต่อ) |
| `revise_required` / `revise_or_supplement` | ศาลสั่งให้แก้ไขหรือแถลงเพิ่มเติม | **ยังเปิดอยู่** (ต้องดำเนินการแก้ไข) |
| `pending_copy_or_service` | ศาลสั่งแล้ว อยู่ระหว่างรอคัดถ่ายหรือนำส่งหมาย | **ยังเปิดอยู่** (ต้องตามงานคัดถ่าย/ส่งหมาย) |
| `granted` | ศาลอนุญาตตามขอ | **ปิดจบคิวรอคำสั่ง** (สร้างงานถัดไปได้ผ่าน `createNextTaskTitle`) |
| `partially_granted` | ศาลอนุญาตบางส่วน | **ปิดจบคิวรอคำสั่ง** |
| `rejected` | ศาลยกคำร้อง / ไม่อนุญาต | **ปิดจบคิวรอคำสั่ง** |
| `withdrawn` | ถอนคำร้อง / ยกเลิกแบบ Soft-Cancel | **ปิดจบคิวรอคำสั่ง** |
| `not_required` / `acknowledged` | รับทราบ / ไม่ต้องมีคำสั่งเพิ่มเติม | **ปิดจบคิวรอคำสั่ง** |

- **การยกเลิกคำร้อง (`slegal_filing_cancel`)**: ใช้สำหรับรายการที่ยังไม่ชี้ขาดเด็ดขาด โดยส่ง `idempotencyKey`, `filingId`, `expectedUpdatedAt`, และ `reason` — ระบบทำ **Soft-Cancel เท่านั้น (zero hard delete)** และปิดงานติดตามที่ผูกอยู่ให้อัตโนมัติ

---

## 3. วิธีแนบไฟล์ PDF คำร้อง คำสั่งศาล หรือเอกสารสำนวน

เครื่องมือ `slegal_filing_record`, `slegal_filing_edit`, `slegal_filing_update_order`, `slegal_filing_attach_pdf`, และ `slegal_case_document_upload` รองรับการแนบไฟล์อย่างปลอดภัย:
1. **ส่งพาธไฟล์บนเครื่อง (`pdfFilePath`)**: สำหรับคำสั่ง `slegal_filing_*` เมื่อใช้งานผ่าน Local MCP Bridge (`bridge.py`) บนเครื่องคอมพิวเตอร์ สะพานเชื่อมต่อจะอ่านไฟล์จากพาธที่ผู้ใช้ระบุและแนบให้โดยอัตโนมัติ (จำกัดขนาดไฟล์ตามเกณฑ์ความปลอดภัย ≤ 8 MB)
2. **ส่ง Base64 (`pdfBase64`+`pdfFileName` หรือ `fileBase64`+`fileName`+`mimeType`)**: สำหรับไฟล์ PDF หรือรูปภาพ (และ `.docx` ใน `slegal_case_document_upload` สูงสุด `10 MiB` พร้อมตรวจ MIME allow-list, malware scan และ SHA-256)
3. **โหมดอัปโหลดไฟล์ใหญ่ (`preparePdfUpload: true` หรือ `prepareOnly: true`)**: ระบบจะคืน Signed Upload URL / คำแนะนำอัปโหลด เพื่อให้ส่งไฟล์ขึ้นพื้นที่จัดเก็บโดยตรงโดยไม่ผ่านขนาดข้อความ JSON

- **การดูรายการเอกสารในสำนวน (`slegal_case_document_list`)**: ส่ง `caseId`, กรอง `documentType` / `search`, และแบ่งหน้า (`page`, `pageSize`) เพื่อดู metadata ของไฟล์ในคลัง `case_documents` และ `uiDownloadPath` (ซ่อน raw storage path)

---

## 4. รายละเอียดการทำงานของ `slegal_court_schedule_upsert`, Auto-Prep Task & `slegal_hearing_record_outcome`

- **พารามิเตอร์หลักของ `slegal_court_schedule_upsert`**:
  - `caseId` (บังคับเมื่อลงนัดใหม่), `scheduleId` (ส่งเมื่อต้องการแก้ไขผลนัด เลื่อนวันนัด หรือยกเลิกนัดเดิม)
  - `action`: `"upsert"` (ค่าเริ่มต้น) หรือ `"cancel"`
  - `courtStage`: `"first"` (`ศาลชั้นต้น`), `"appeal"` (`ศาลอุทธรณ์`), `"supreme"` (`ศาลฎีกา`)
  - `scheduleDate`: `YYYY-MM-DD`, `scheduleTime`: `HH:MM` (เช่น `"09:00"`, `"13:30"`), `scheduleTitle` (เช่น `"นัดชี้สองสถานและสืบพยานโจทก์"`), `courtName`, `courtroom`, `result`
  - `createPrepTask`: ค่าเริ่มต้น `true`
  - `prepDaysBefore`: ค่าเริ่มต้น `7` (ตั้ง `followUpAt` ล่วงหน้า 7 วันก่อน `scheduleDate`, หรือใช้วันนี้หากเหลือไม่ถึง 7 วัน และตั้ง `dueAt = scheduleDate`)
- **การซิงค์อัตโนมัติ**:
  1. คำนวณวันนัดอนาคตที่ใกล้ที่สุดของสำนวนไปอัปเดต `next_action_at` และ `next_action_time` ของสำนวน
  2. ผูกงานเตรียมคดีด้วยตัวระบุ `[นัดศาล:<scheduleId>]` — หากทนายสั่งเลื่อนวันนัดใบเดิม (`scheduleId` เดิม) งานเตรียมคดีจะขยับ `dueAt` และ `followUpAt` ตามโดยไม่สร้างงานซ้ำ และหากสั่ง `action: "cancel"` งานเตรียมคดีจะถูกยกเลิก (`cancelled`) ตามทันที
- **บันทึกผลหลังวันนัดแบบ Atomic (`slegal_hearing_record_outcome`)**:
  - ส่ง `idempotencyKey`, `caseId`, `scheduleId`, `outcomeResult` และเลือกแนบ `redCaseNo`, `judgmentDate`, `nextHearing` (ลงนัดครั้งถัดไป + Auto-Prep Task), และ `followUpTask` ได้ในคำสั่งเดียว (Atomic transaction)
  - ระบบปกป้องชั้นศาล/สถานะปิดคดีเดิมหากเป็นการบันทึกผลนัดย้อนหลัง และไม่ทับ `redCaseNo` เดิมที่แตกต่างโดยไม่ยืนยัน

---

## 5. รายละเอียดการทำงานของ `slegal_appeal_status_get`, `slegal_appeal_deadline_upsert`, `slegal_appeal_extension_record`, `slegal_court_service_fee_lookup` & `slegal_case_snapshot_get`

1. **ตรวจสถานะ (`slegal_appeal_status_get`)**:
   - ส่ง `caseId` เพื่อดูวันอ่านคำพิพากษา วันครบกำหนดอุทธรณ์/ฎีกาปัจจุบัน (`effectiveDueAt`) จำนวนวันที่เหลือ (`daysRemaining`) และประวัติคำร้องขอขยายทั้งหมดของสำนวน
   - ไม่ส่ง `caseId` เพื่อดูภาพรวมคดีที่ใกล้ครบกำหนดอุทธรณ์/ฎีกาทั้งสำนักงาน
2. **สร้าง/อัปเดตกำหนดอุทธรณ์-ฎีกา (`slegal_appeal_deadline_upsert`)**:
   - รองรับ `deadlineType`: `"appeal" | "supreme" | "appeal_answer" | "supreme_answer"`, `caseLawType`: `"civil" | "criminal"`, `baseEventDate`, `serviceMethod`: `"direct" | "posted"`, `appealFiledAt`, `filingSide`, `filingPartyName`, `nextStageBlackCaseNo`
   - บังคับตรวจ **Chronology Guard (`AppealFilingValidationError`: `appealFiledAt >= baseEventDate`)** และคำนวณวันทำการถัดไปตาม **ป.พ.พ. มาตรา 193/8** อัตโนมัติ
3. **บันทึกคำร้องขอขยาย (`slegal_appeal_extension_record`)**:
   - สร้างครั้งที่ 1, 2, ... (`sequenceNo` รันให้อัตโนมัติ) โดยระบุ `caseId` (หรือ `deadlineId`), `deadlineType` (`"appeal"` | `"supreme"`), `judgmentDate`, `requestedUntil`, `filedAt`, `reason`
   - เมื่อศาลมีคำสั่งอนุญาต: เรียกซ้ำโดยส่ง `extensionId`, `courtOrderStatus: "granted"`, และ `grantedUntil: "YYYY-MM-DD"` ระบบจะขยับกำหนดครบอายุของสำนวนไปเป็นวันใหม่และปิดคิวตามคำสั่งศาลให้ครบในคำสั่งเดียว
4. **ค้นหาค่าส่งหมาย 262 ศาล (`slegal_court_service_fee_lookup`)**:
   - ส่ง `q`, `courtName`, `provName`, `amphurName`, `tambonName` (ระบบตัดคำนำหน้าพื้นที่ไทยให้อัตโนมัติ เช่น `กทม.`, `เขต`, `แขวง`, `อ.`, `ต.`) เพื่ออ่านอัตราค่านำหมาย/ส่งหมายข้ามเขตจาก `court_service_fee_rates`
5. **ภาพรวมสำนวนครบใบเดียว (`slegal_case_snapshot_get`)**:
   - ส่ง `caseId` (`includeCompletedTasks?`, `includePastHearings?`) เพื่อดึงข้อมูลคดี คู่ความ นัดศาล คำร้อง อุทธรณ์ งานค้าง และใบเสนอราคาในครั้งเดียว
   - **QT Fee Privacy Gate**: หาก API Key ไม่มีสิทธิ์ `accounting.manage` / `case.finance.manage` / `*` ระบบจะคืนเฉพาะเลขที่ใบเสนอราคาและสถานะอนุมัติ โดยซ่อนตัวเลขค่าบริการ (`feeSummaryRedacted: true`) โดยอัตโนมัติ
