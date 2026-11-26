---
name: slegal-case-intake
description: Open, update, and verify S-Legal case files and non-litigation legal projects (ที่ปรึกษากฎหมาย, ร่าง/ตรวจสัญญา, โนติส/เจรจาทวงถาม, จดทะเบียนธุรกิจ) in `Cases`, manage structured parties (`slegal_case_intake_preflight`, `slegal_case_upsert_with_parties`, `slegal_case_parties_get`, `slegal_case_open_or_bind_quotation`), order corporate documents from DBD e-Service (`slegal_dbd_order_create`, `slegal_dbd_order_list`, `slegal_dbd_order_confirm_paid`, `slegal_dbd_order_cancel`), and issue `.docx` court forms (`slegal_court_templates_list`, `slegal_court_document_preview`, `slegal_court_document_generate`). Use when the user asks to เปิดแฟ้มงาน, ตั้งโปรเจกต์ที่ปรึกษา/สัญญา/โนติส, ตั้งแฟ้มคดี, เพิ่ม/แก้คู่ความ (โจทก์/จำเลย/ผู้ร้อง/ผู้คัดค้าน/ลูกความฝ่ายเรา/คู่สัญญา), คัดหนังสือรับรอง/บอจ.5/งบการเงิน DBD, ผูกใบเสนอราคาเข้าแฟ้ม, or generate ใบแต่งทนาย/คำร้อง/แบบพิมพ์ศาล. Don't use for routine task follow-up updates, rescheduling tasks, or billing-only requests without case/party setup.
---

# S-Legal Unified Case Intake, Party Management & Court Forms

บันทึกและอัปเดต **ทุกประเภทงานของสำนักงานในตาราง `Cases` ที่เดียวจบ** ผ่านเครื่องมือ **S-Legal MCP** ทั้งคดีขึ้นศาลและโปรเจกต์ไม่ขึ้นศาล เพื่อให้ทีมไม่ต้องแยกจำระหว่างงานโครงการกับสำนวนคดี และให้การออกเอกสารแบบพิมพ์ศาล (`.docx`) ดึงชื่อคู่ความ ลำดับ `ที่ 1..N` สถานะพิเศษ และคำลงท้าย `ทนาย...` ได้แม่นยำ 100%

> **ห้ามใช้เลขรหัสภายใน `SL-...` เป็นเลขอ้างอิงหลักกับผู้ใช้** — คดีขึ้นศาลให้แสดง `เลขคดีดำ` (`blackCaseNo`) เสมอ ส่วนงานก่อนฟ้องหรืองานที่ปรึกษา/สัญญาที่ยังไม่มีเลขคดีดำ ให้แสดง **`ชื่อเรื่อง` คู่กับ `ชื่อลูกความ`** แทน

## When to Read Bundled References

อ่านไฟล์ [`references/party-naming-rules.md`](references/party-naming-rules.md) ทันทีเมื่อพบกรณีต่อไปนี้:
- เปิดโปรเจกต์ไม่ขึ้นศาล (`ที่ปรึกษากฎหมาย`, `ร่าง/ตรวจสัญญา`, `โนติส/เจรจาทวงถาม`, `จดทะเบียนธุรกิจ`) และต้องการเลือก `caseType`, `partyType` (`client` / `counterparty` / `opponent`), หรือ `initialFollowUpTask`
- คู่ความเป็นนิติบุคคล (บริษัทจำกัด, มหาชน, หจก., นิติบุคคลอาคารชุด, วัด, หน่วยงานรัฐ) หรือมีหนังสือรับรองบริษัท (DBD)
- คู่ความมีสถานะพิเศษตามกฎหมาย (ผู้จัดการมรดก, ผู้เยาว์/ผู้แทนโดยชอบธรรม, ผู้อนุบาล/ผู้พิทักษ์, ผู้รับมอบอำนาจ, เจ้าพนักงานพิทักษ์ทรัพย์, ผู้ชำระบัญชี)
- มีคู่ความฝั่งเดียวกันตั้งแต่ 2 คนขึ้นไป หรือลูกความฝ่ายเราเป็นเพียงบางคนในฝั่งนั้น (เช่น จำเลยที่ 2 คนเดียว)
- ทำงานในโฟลเดอร์สำนวนท้องถิ่นที่มี `01_ข้อมูลและบริบท/PARTIES.md`

---

## Ordered Workflow

### Step 1: แยกประเภทงาน สกัดข้อเท็จจริง และจัดรูปแบบชื่อคู่ความ (Extract & Normalize)

1. **กำหนดประเภทแฟ้มงาน (`caseType`) ให้ชัดเจน** (เปิดใน `Cases` ที่เดียวทุกประเภท):
   - **คดีขึ้นศาล**: `แพ่ง`, `อาญา`, `ผู้บริโภค`, `แรงงาน`, `ปกครอง`, `ล้มละลาย`, `ทรัพย์สินทางปัญญา`, `ภาษี`, `ครอบครัวและมรดก`
   - **โปรเจกต์/งานไม่ขึ้นศาล**: `ที่ปรึกษากฎหมาย`, `ร่าง/ตรวจสัญญา`, `โนติส/เจรจาทวงถาม`, `จดทะเบียนธุรกิจ` (ไม่ต้องบังคับ `courtName` หรือ `blackCaseNo` ระบบตั้ง `status: "Pre-Litigation"` ให้อัตโนมัติ)
2. **ข้อมูลคู่ความ/คู่สัญญา (`parties[]`)**:
   - `name`: ชื่อตัวคู่ความแท้จริงตามกฎหมายเท่านั้น **ห้ามปนข้อความสถานะพิเศษหรือลำดับที่**
     - บุคคลธรรมดา: ต้องมีคำนำหน้าจริงตามบัตรประชาชน/ราชการ (`นาย`, `นาง`, `นางสาว`, `เด็กชาย`, `เด็กหญิง` หรือยศราชการ) **ห้ามใช้ `"คุณ"` เด็ดขาด** และแปลง `"น.ส."` เป็น `"นางสาว"`
     - นิติบุคคล: สะกดชื่อเต็มตามหนังสือรับรอง (`บริษัท ... จำกัด`, `บริษัท ... จำกัด (มหาชน)`, `ห้างหุ้นส่วนจำกัด ...`) **ห้ามย่อ `บจก.`, `บมจ.`, `หจก.`**
   - `partyType`:
     - คดีศาล: เลือกจาก 13 ฐานะ (`plaintiff`, `co_plaintiff`, `defendant`, `co_defendant`, `petitioner`, `objector`, `intervenor`, `injured_person`, `judgment_creditor`, `judgment_debtor`, `guarantor`, `witness`, `other`)
     - งานที่ปรึกษา/สัญญา/โนติส/จดทะเบียน: ส่ง `client` (ลูกความ/ผู้ว่าจ้างฝ่ายเรา -> ระบบตั้ง `isOurClient: true`), `counterparty` หรือ `opponent` (คู่สัญญาอีกฝ่าย/ผู้รับโนติส -> `isOurClient: false`) พร้อม `roleDetail` เช่น `"ผู้ว่าจ้าง"`, `"ผู้ขาย"`, `"ลูกหนี้ตามโนติส"` ได้เลย
   - แยก `sideOrdinal` (`1..N`), `specialCapacityType` + `specialCapacityLabel`, ข้อมูล DBD (`registrationNo`, `certificateIssuedDate`, `authorityCondition`, `relatedPersons[]`), และ `address` แยกช่องตาม [`references/party-naming-rules.md`](references/party-naming-rules.md)
3. **ตั้งงานติดตามชิ้นแรก (`initialFollowUpTask`)**:
   - กำหนด `initialFollowUpTask: { enabled: true, title, taskCategory, followUpAt, dueAt }` เพื่อให้งานแรกของแฟ้มไปขึ้นในแถบ **`งานที่ต้องติดตาม`** (`/follow-up`) ถูกหมวดทันที (เช่น `drafting` สำหรับร่างสัญญา/ร่างฟ้อง, `document_prep` สำหรับตรวจเอกสาร/เตรียมคดี, `client_followup` สำหรับรอลูกความส่งเอกสาร)

### Step 2: รัน Pre-Flight Check 4 จุดเสมอ (`slegal_case_intake_preflight`)

ก่อนเปิดแฟ้มใหม่ (หรือเมื่อผู้ใช้ยังไม่ระบุ `caseId`) **ต้องเรียก `slegal_case_intake_preflight`** โดยส่ง `partyNames`, `taxOrNationalIds`, `blackCaseNo`, `courtName`, `titleKeyword`:
1. **ตรวจแฟ้มซ้ำ (`duplicateCases`)**: หากพบแฟ้มเดิม (รวมแฟ้มที่ปิดแล้ว `isClosed: true`) ต้องถามผู้ใช้ว่าจะอัปเดตแฟ้มเดิมหรือเปิดแฟ้มแยกใหม่
2. **ใช้ข้อมูลลูกค้าเดิม (`existingMasterParties`)**: นำ `partyMasterId` ที่อยู่ เลข 13 หลัก และกรรมการเดิมมาใช้ลดการกรอกซ้ำ (แจ้งเตือนหาก `certificateAge.warning` เกิน 30/90 วัน)
3. **ผูกใบเสนอราคา/งานค้าง (`unlinkedQuotations`, `unconvertedPreCaseJobs`, `unlinkedCourtFilings`)**: เสนอผูก `quotationIds` (รองรับ 1 แฟ้ม : หลายใบเสนอราคา) และคำร้องลอยในคราวเดียว (หากแฟ้มเปิดอยู่แล้วและต้องการผูกเฉพาะใบเสนอราคาเพิ่ม ใช้ `slegal_case_open_or_bind_quotation` โหมด `bind_to_existing_case`)
4. **ตรวจทนายผู้รับผิดชอบ (`lawyers`, `recommendedLawyer`)**: เตรียม `leadLawyerId`

### Step 3: ตรวจสอบ Hard Gate vs Soft Gate & Sensitive Diff Gate

- **Hard Gate (ต้องหยุดถามก่อนบันทึกเสมอ)**:
  1. ไม่ชัดเจนว่าใครเป็นลูกความฝ่ายเรา (`isOurClient`) หรือคดีศาลไม่ชัดว่าเป็น `โจทก์/จำเลย` vs `ผู้ร้อง/ผู้คัดค้าน`
  2. บุคคลธรรมดาขาดคำนำหน้าตามกฎหมาย (เช่น `"คุณ..."`) หรือนิติบุคคลไม่ทราบคำลงท้ายเต็ม (`จำกัด` vs `จำกัด (มหาชน)`)
  3. คู่ความฝั่งเดียวกันมากกว่า 1 คนแต่ไม่ทราบลำดับ `ที่ 1, ที่ 2...`
  4. ผู้ใช้ยังไม่ระบุทนายผู้รับผิดชอบ (`leadLawyerId`) — ให้ถามสั้น ๆ โดยเสนอ `recommendedLawyer` เป็นตัวเลือกแรก
  5. เอกสาร/OCR ไม่ชัด ขัดแย้งกัน หรือพบแฟ้มซ้ำใน `duplicateCases`
- **Soft Gate (เปิดแฟ้มได้ทันที ไม่ต้องบล็อก)**: ขาดเลขบัตร/ที่อยู่คู่กรณี เลขคดีดำก่อนฟ้อง หรือวัตถุประสงค์บริษัท -> เปิดแฟ้มได้เลย พร้อมสรุปรายการที่ขาดและตั้ง `createMissingDataTask: true` ได้ตามเหมาะสม
- **Sensitive Diff Gate (`mode: "update"`)**:
  - การเติมข้อมูลว่าง (เลขบัตร ที่อยู่ เบอร์โทร กรรมการ หรือเพิ่มคู่ความต่อท้าย) บันทึกได้ทันที
  - การแก้ชื่อ/คำนำหน้า, เปลี่ยน `partyType`, สลับ `sideOrdinal`, เปลี่ยน `isOurClient`, แก้สถานะพิเศษ หรือลบคู่ความ: เรียกด้วย `confirmSensitiveDiff: false` ก่อน -> แสดงตาราง **`เดิม vs ใหม่`** ให้ผู้ใช้ยืนยัน -> เมื่อผู้ใช้ตกลงจึงเรียกซ้ำด้วย `confirmSensitiveDiff: true` และ `idempotencyKey` ใหม่

### Step 4: บันทึกแฟ้มและรายงานผล (`slegal_case_upsert_with_parties`)

1. เรียก `slegal_case_upsert_with_parties` พร้อม `idempotencyKey`
2. หากทำงานในโฟลเดอร์สำนวนท้องถิ่นที่มี `01_ข้อมูลและบริบท/PARTIES.md` ให้อัปเดตไฟล์ให้ตรงกับฐานข้อมูล
3. สรุปผลกระชับ: ชื่อเรื่อง, ประเภทงาน (`caseType`), ศาล/`เลขคดีดำ` (หรือชื่อลูกความสำหรับโปรเจกต์), ทนายผู้รับผิดชอบ, งานติดตามเริ่มต้น (`initialTaskId`), ตารางคู่ความ + คำลงท้ายทนาย (`computedRoles`), ความพร้อมออกฟอร์มศาล (`templateReadiness`), และลิงก์ `uiPath`

### Step 5: ออกแบบพิมพ์ศาล `.docx` จากสำนวน (เมื่อผู้ใช้สั่งต่อเนื่อง)

1. เรียก `slegal_court_templates_list` เพื่อหา `templateId` และ `contentTemplateId`
2. เลือก `multiPartyMode` ให้เหมาะกับเอกสาร (`multiline` / `full_list` สำหรับหน้าคำฟ้อง, `et_al_short` / `et_al` / `full_list` สำหรับคำร้อง/ใบแต่งทนาย)
3. เรียก `slegal_court_document_preview` ตรวจ `resolvedFields` และถาม `requiredSlots` ที่ยังขาดก่อน
4. เรียก `slegal_court_document_generate` เพื่อสร้าง `.docx` เก็บเข้าสำนวนและส่ง `signedDownloadUrl` / `uiDownloadPath` ให้ผู้ใช้ทันที

### Step 6: สั่งคัดเอกสารนิติบุคคลจากระบบ DBD e-Service (`slegal_dbd_order_*`)

เมื่อหนังสือรับรองนิติบุคคลหมดอายุหรือผู้ใช้สั่งคัด `หนังสือรับรองนิติบุคคล`, `บอจ.5`, `งบการเงิน`, หรือ `สำเนาเอกสารจดทะเบียน`:
1. เรียก `slegal_dbd_order_create` โดยส่ง `caseId` หรือ `caseSearch` (เลขคดีดำ) พร้อม `juristicId` (13 หลัก) หรือ `companyName` และ `packageCode` (`cert_current`, `boj5_latest`, `financial_latest`, `reg_incorporation`, `reg_latest`, `cert_and_boj5`)
   - **รองรับสั่งคัดพร้อมกันหลายบริษัทในคำสั่งเดียว**: ส่ง `companies: [{ juristicId, companyName, packageCode }]` (สูงสุด 15 บริษัท), ส่งเลขทะเบียน 13 หลักหลายเลขคั่นด้วยคอมมา/บรรทัดใหม่, หรือส่ง `allCaseJuristics: true` เพื่อคัดคู่ความนิติบุคคลทั้งหมดในสำนวนพร้อมกัน
   - **กติกาชื่อผู้ชำระเงินในใบเสร็จกรมฯ อัตโนมัติ**: หากผูกสำนวนคดี ระบบออกใบเสร็จในนาม **ลูกความเจ้าของสำนวน (`is_our_client = true`)** ทันที; หากไม่ผูกสำนวน ระบบออกในนาม **นิติบุคคลของสำนักงานตามค่าเริ่มต้นของระบบ** (เว้นแต่ผู้ใช้สั่งระบุ `receiptPayerName` เอง)
2. Worker เบื้องหลังของ S-Legal จะส่งคำขอเข้า DBD e-Service ดาวน์โหลดใบ Pay-in PDF และส่งทั้งภาพใบ Pay-in เต็มใบ + ภาพครอป QR ความละเอียดสูงให้ผู้มีอำนาจนำไปสแกนจ่าย (ตรวจสอบสถานะและลิงก์ผ่าน `slegal_dbd_order_list`)
3. หลังผู้มีอำนาจแจ้งว่าชำระเงินแล้ว สามารถสั่งตรวจสอบและดาวน์โหลดทันทีผ่าน `slegal_dbd_order_confirm_paid` ระบบจะดาวน์โหลดไฟล์หนังสือรับรอง e-Certificate (PDF) + ใบเสร็จรับเงิน (PDF) แนบเข้าแฟ้มสำนวน อัปเดตวันที่ออกหนังสือรับรองของคู่ความ และตั้งเบิกค่าใช้จ่าย (`EC...`) คืนผู้สำรองจ่ายตามสิทธิ์ให้อัตโนมัติ (ดูรายละเอียดเพิ่มในสกิล `slegal-dbd-order`)
