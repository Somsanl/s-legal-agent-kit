# คู่มือโครงสร้างข้อมูลและแนวปฏิบัติ `slegal-billing-ops`

## 1. มาตรฐานการออกใบแจ้งหนี้ค่าที่ปรึกษารายเดือน (`Monthly Retainer / MBA`)

สำหรับลูกค้าสัญญาที่ปรึกษารายเดือน (เช่น `บริษัท ตัวอย่าง จำกัด` หรือลูกค้ารายเดือนรายอื่น):
1. ค้นหาใบเสนอราคาต้นทาง (`slegal_quotation_search`) หรือใบแจ้งหนี้เดือนล่าสุดของลูกค้ารายนั้น (`slegal_invoice_search({ query: "<ชื่อลูกค้า>" })` -> `slegal_invoice_get`) เพื่อตรวจ:
   - ชื่อนิติบุคคล เลขผู้เสียภาษี 13 หลัก และที่อยู่จดทะเบียนที่ถูกต้อง
   - อัตราค่าบริการรายเดือน (`unitPrice`), `vatRate` (ปกติ `7`), และ `whtRate` (ปกติ `3` สำหรับค่าบริการวิชาชีพนิติบุคคล)
2. ระบุงวดเดือนและปี พ.ศ. ให้ชัดเจนเสมอ (ห้ามส่งแค่คำว่า `"ค่าที่ปรึกษากฎหมาย"` ลอยๆ โดยไม่ระบุเดือน):
   ```json
   {
     "idempotencyKey": "inv-retainer-202611-example-01",
     "issueNow": true,
     "sourceQuotationNo": "QT2026100012",
     "documentDate": "2026-11-11",
     "dueDate": "2026-11-25",
     "subject": "ค่าที่ปรึกษาประจำเดือน พฤศจิกายน 2569",
     "lines": [
       {
         "description": "ค่าที่ปรึกษากฎหมายประจำเดือน พฤศจิกายน 2569",
         "quantity": 1,
         "unitName": "เดือน",
         "unitPrice": "15000.00",
         "vatRate": 7,
         "whtRate": 3
       }
     ]
   }
   ```
3. เมื่อสร้างสำเร็จ ให้รายงานเลขที่ใบแจ้งหนี้ (`INV...`), ยอดก่อน VAT, VAT 7%, หัก ณ ที่จ่าย 3%, ยอดสุทธิที่ลูกค้าต้องโอน (`netReceivableAmount`), และลิงก์หน้าเอกสาร (`uiPath` / `pdfUrl`)

---

## 2. การแก้ไขใบแจ้งหนี้ (`slegal_invoice_update`) ตามสถานะเอกสาร

| สถานะปัจจุบันของใบแจ้งหนี้ | วิธีแก้ไขที่ถูกต้อง |
|---|---|
| `draft` (ยังไม่ล็อกเลขจริง) | เรียก `slegal_invoice_update` โดยส่ง `documentId` (หรือ `documentNo`) พร้อมฟิลด์ที่ต้องการแก้ และส่ง `issueNow: true` หากต้องการออกเลขจริงทันที |
| `issued` / `sent` (ออกเลขแล้ว และยังไม่ได้รับชำระเงิน) | เรียก `slegal_invoice_update` โดยส่ง **`reissue: true`** และ **`reason`** (เช่น `"แก้ไขรายละเอียดงวดประจำเดือน พฤศจิกายน 2569"`) ระบบจะยกเลิกใบเดิมพร้อมบันทึก Audit และออกใบแจ้งหนี้ใบใหม่ให้ในธุรกรรมเดียว |
| `partially_paid` / `paid` | **ห้ามแก้ไขหรือยกเลิกผ่าน MCP** — ต้องแจ้งฝ่ายบัญชีดำเนินการปรับปรุงรับชำระหรือออกใบลดหนี้/ใบเพิ่มหนี้ผ่านหน้าเว็บ |

---

## 3. โครงสร้าง `slegal_quotation_draft_save` และ `slegal_quotation_draft_update`

- **สร้างร่างใบเสนอราคา (`slegal_quotation_draft_save`)**:
  - `documentDate`: `"YYYY-MM-DD"` (บังคับ)
  - `validUntil`: `"YYYY-MM-DD"` (ถ้ามี)
  - `customer`: `{ partyId?, name, taxId?, address? }` (ถ้าไม่มี `partyId` ต้องระบุ `taxId` หรือ `address` อย่างน้อย 1 ช่อง)
  - `subject`: หัวข้อเรื่องใบเสนอราคา
  - `lines`: อาเรย์ของ `{ description, quantity, unitPrice: "0.00", unitName, vatRate, whtRate, serviceItemId? }`
  - `terms`, `notes`, `issuerName` (ถ้ามี)
- **แก้ไขร่างใบเสนอราคา (`slegal_quotation_draft_update`)**:
  - ต้องเรียก `slegal_draft_get({ kind: "quotation", recordId })` ก่อนเสมอ
  - ต้องส่ง `documentId`, `expectedUpdatedAt` (ตรงกับ `updatedAt` ระดับไมโครวินาที `YYYY-MM-DDTHH:MM:SS.ffffffZ` ทุกตัวอักษร), และ `customer.partyId` ที่มีอยู่ในระบบแล้ว

---

## 4. ขั้นตอนตั้งเบิกค่าใช้จ่ายพนักงาน (`EC`) แบบครบวงจร

1. **ตรวจแฟ้มปัจจุบัน**:
   - `slegal_intake_get({})` -> หากพบแฟ้มเดิมที่มีไฟล์ค้างอยู่ (`fileCount > 0`) ให้อ่านรายการไฟล์และถามผู้ใช้ก่อนเสมอ ห้ามสั่งยกเลิกโดยพลการ
2. **เปิดแฟ้มรับหลักฐาน**:
   - `slegal_intake_create({ idempotencyKey })` -> ได้รับ `recordId` (`intakeId`)
3. **อัปโหลดไฟล์หลักฐานแต่ละใบ**:
   - คำนวณขนาดไบต์ (`sizeBytes`) และค่า `sha256` (ตัวพิมพ์เล็ก 64 ตัวอักษร) ของไฟล์จริงบนเครื่อง
   - เรียก `slegal_upload_prepare({ idempotencyKey, intakeId, fileName, mimeType, sizeBytes, sha256 })`
   - อัปโหลดเนื้อไฟล์ดิบด้วย HTTP `PUT` ไปยัง `upload.uploadPath` ของ S-Legal Origin เดียวกัน พร้อม Header `Content-Type` ที่ตรงกับ `mimeType` และ `Authorization: Bearer <คีย์จาก ~/.slegal/mcp/api_key>` (ห้ามพิมพ์ค่าคีย์ออกหน้าจอหรือเก็บในสคริปต์ถาวร)
   - เรียก `slegal_upload_finalize({ idempotencyKey, uploadId })`
4. **สร้างร่างใบตั้งเบิก (`EC`)**:
   - เรียก `slegal_expense_draft_create`:
     ```json
     {
       "idempotencyKey": "ec-draft-20261111-01",
       "intakeId": "<intakeId>",
       "claimDate": "2026-11-11",
       "purpose": "สำรองจ่ายค่าธรรมเนียมคัดถ่ายเอกสารศาลแพ่งกรุงเทพใต้",
       "items": [
         {
           "description": "ค่าธรรมเนียมคัดถ่ายคำพิพากษาตามใบเสร็จศาล",
           "expenseDate": "2026-11-11",
           "expenseCategory": "court_fee",
           "vendorName": "ศาลแพ่งกรุงเทพใต้",
           "amountBeforeVat": "200.00",
           "vatAmount": "0.00",
           "evidenceUploadIds": ["<uploadId>"]
         }
       ]
     }
     ```
   - **ข้อควรระวัง**: ทุกไฟล์ที่อัปโหลดเข้า `intakeId` นั้นต้องถูกอ้างอิงใน `items[].evidenceUploadIds` ครบทุกไฟล์ และใช้วันที่ตามใบเสร็จจริง (`expenseDate`) ห้ามแต่งวันที่ขึ้นเอง
   - หากมีบริบทสำนวนคดี (`caseId` หรือ `blackCaseNo`) ให้ระบุ `rechargeDecision` (`'recharge'` เก็บเงินลูกความ / `'included'` รวมในค่าบริการแล้ว / `'non_billable'` ค่าใช้จ่ายสำนักงาน) ให้ชัดเจนเสมอ
