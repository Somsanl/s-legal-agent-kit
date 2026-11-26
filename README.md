# S-Legal Agent Kit for Antigravity (`v1.1.0`)

ชุดปลั๊กอินและตัวเชื่อม **S-Legal MCP** อย่างเป็นทางการสำหรับทีมงานสำนักงานกฎหมาย S-Legal ใช้ได้ทั้งบน **Windows** และ **macOS** ภายในคำสั่งเดียวโดยไม่ต้องตั้งค่าซับซ้อน — **เปิดใช้งานจริงครบ 95 เครื่องมือบน Production (`36` งานกฎหมาย + `57` บัญชี/วางบิล/ภาษี + `2` ระบบ)**

---

## ชุดนี้ช่วยงานอะไรได้บ้าง?

### 1. สำหรับทีมทนายความ (`Legal Team` — `36` เครื่องมือ Live บน Production)
| สกิล | ความสามารถหลัก |
|---|---|
| **`slegal-case-intake`** | เปิด/อัปเดตแฟ้มงานใน `Cases` ทั้งคดีขึ้นศาลและงานที่ปรึกษา/สัญญา/โนติส ตรวจแฟ้มซ้ำ จัดการคู่ความตามมาตรฐานศาลไทย จัดการเอกสารสำนวน และออกแบบพิมพ์ศาล `.docx` |
| **`slegal-work-tracker`** | เช็กคิว `งานที่ต้องติดตาม` ดูภาพรวมสำนวนครบใบเดียว (`slegal_case_snapshot_get` พร้อม QT Fee Privacy Gate) ตั้ง/แก้ไข/ย้ายแท็บงาน (`slegal_task_edit`) ตามคำสั่งศาล ยกเลิกคำร้อง soft-cancel (`slegal_filing_cancel`) ลงนัดศาลพร้อมงานเตรียมคดี บันทึกผลหลังนัดแบบ Atomic (`slegal_hearing_record_outcome`) ค้นค่านำหมาย 262 ศาล อัปเดตอุทธรณ์/ฎีกา ป.พ.พ. ม.193/8 และอัปโหลดเอกสารคดี |
| **`slegal-dbd-order`** | สั่งคัดเอกสาร DBD e-Service (หนังสือรับรอง, บอจ.5, งบการเงิน) ส่งใบ Pay-in/QR ให้ผู้มีอำนาจชำระเงิน และดาวน์โหลด e-Certificate เข้าสำนวน |
| **`thai-legal-drafting`** | ร่างคำฟ้องแพ่ง คำร้องศาล 3 ส่วน พิสูจน์อักษรภาษาไทยทางการ และสร้างไฟล์ `.docx` ฟอนต์ `TH SarabunPSK 15 pt` ตัดคำถูกต้อง |

### 2. สำหรับทีมบัญชีและการเงิน (`Accounting Team` — `57` เครื่องมือ Live บน Production)
| สกิล | สถานะเครื่องมือ | ความสามารถหลัก |
|---|---|---|
| **`slegal-billing-ops`** | **Live MCP (`23` เครื่องมือ)** | ออก/แก้ไขใบเสนอราคา (`QT`/`MBA`), บันทึกผลอนุมัติลูกค้า, ออก/แก้เลขใบแจ้งหนี้ (`INV` รวมถึงงานที่ปรึกษารายเดือน), บันทึกค่าใช้จ่ายสำนวน, และสร้างร่างตั้งเบิกพนักงาน (`EC`) พร้อมอัปโหลดสลิป |
| **`slegal-accounting-ops`** | **Live MCP (`34` เครื่องมือ: `22 READ + 12 Safe Draft/Proof/Append`)** | ปฏิบัติงานครบทั้ง 7 กลุ่มภายใต้ **7 Red-Line Locks**: `GL`/งบทดลอง/ปิดงวด (`READ ONLY`), `RC` & PDF (`address_only` + เตรียมร่าง/แคช PDF), `AP` (ร่าง/แนบหลักฐาน), `PV` & สลิปจ่าย (เฉพาะ `ordinary + vendor` ตันที่ `paid_unposted`), Statement & กระทบยอด (Staging Draft + คู่แนะนำ), `50 ทวิ / ภ.ง.ด.3-53` (`SECTION_40_6` 3% vs `SECTION_40_2`), และค่าตอบแทน/ECP/วางบิล EXP/OMEC (`Partner Ledger` & `OMEC` **READ ONLY** เฉพาะ `partner-ledger.manage`) |

---

## ติดตั้งง่ายใน 3 ขั้นตอน

### ขั้นที่ 1: เตรียม S-Legal URL และ API Key ส่วนตัวของท่าน
1. เปิดระบบ S-Legal ของสำนักงานท่าน (เช่น `https://your-slegal-host.example.com`) และเข้าสู่ระบบด้วยบัญชีของท่านเอง
2. คัดลอก **URL ระบบ S-Legal** ของสำนักงาน (เช่น `https://your-slegal-host.example.com`)
3. ไปที่ **ตั้งค่า > Integrations** แล้วกดสร้าง **API Key ส่วนตัว** (รูปแบบขึ้นต้นด้วย `slk_...`) โดยเลือก **Scopes ตามบทบาทงานของท่าน** แล้วคัดลอกเก็บไว้ชั่วคราว (คีย์นี้ผูกกับสิทธิ์บัญชีของท่าน **ห้ามแชร์ให้ผู้อื่น**)

| บทบาททีมงาน | Scopes ที่แนะนำตอนสร้าง API Key ใน `ตั้งค่า > Integrations` |
|---|---|
| **ทีมทนายความ** | `context:read`, `legal:read`, `legal:write`, `expenses:draft`, `evidence:write` |
| **ทีมบัญชี (อ่าน/ตรวจอย่างเดียว)** | `context:read`, `accounting:read` |
| **ทีมบัญชี (จัดเตรียมร่างเอกสาร/หลักฐาน)** | `context:read`, `accounting:read`, `accounting:draft`, `sales:draft`, `expenses:draft`, `evidence:write` |

### ขั้นที่ 2: รันคำสั่งติดตั้งเพียงคำสั่งเดียว

#### สำหรับ Windows (PowerShell)
1. กดปุ่ม Windows พิมพ์ **`PowerShell`** แล้วเปิดหน้าต่าง **Windows PowerShell**
2. วางคำสั่งด้านล่างแล้วกด Enter:

```powershell
irm https://raw.githubusercontent.com/Somsanl/s-legal-agent-kit/main/install-windows.ps1 | iex
```

3. กรอกข้อมูล 2 รายการตามหน้าจอ:
   - **S-Legal URL** ของสำนักงานท่าน (จะถูกบันทึกที่ `~/.slegal/mcp/endpoint`)
   - **S-Legal API Key** (`<YOUR_SLEGAL_API_KEY>` แบบซ่อนตัวอักษร จะถูกบันทึกที่ `~/.slegal/mcp/api_key` พร้อมล็อกสิทธิ์เฉพาะผู้ใช้)

#### สำหรับ macOS (Terminal)
1. เปิดแอป **Terminal** (`Cmd + Space` พิมพ์ `Terminal`)
2. วางคำสั่งด้านล่างแล้วกด Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/Somsanl/s-legal-agent-kit/main/install-mac.sh | bash
```

3. กรอก **S-Legal URL** และ **S-Legal API Key** (`<YOUR_SLEGAL_API_KEY>` แบบซ่อนตัวอักษร) แล้วกด Enter

> **หมายเหตุ:** ตัวติดตั้งต้องการ **Python 3.9 ขึ้นไป** (ใช้เฉพาะไลบรารีมาตรฐานในตัว ไม่ต้อง `pip install` เพิ่ม)

### ขั้นที่ 3: เปิด/รีสตาร์ท Antigravity แล้วทดสอบ
1. ปิดและเปิด **Antigravity** ใหม่เพื่อให้โหลดปลั๊กอิน `slegal`
2. เปิดแชตใหม่แล้วลองพิมพ์ทดสอบ:
   - `"เช็กสิทธิ์ S-Legal ของฉัน"`
   - `"เช็กงานที่ต้องติดตามรอบนี้ใน S-Legal"`

---

## วิธีอัปเดตเป็นเวอร์ชันล่าสุด (`v1.1.0`)

ทีมงานที่ติดตั้งไว้แล้วสามารถอัปเกรดจาก `v1.0.0` เป็น **`v1.1.0`** ได้ทันทีโดย **รันคำสั่งติดตั้งเดิมซ้ำได้เลย** (คำสั่ง Windows PowerShell หรือ macOS Terminal ด้านบน):
- ระบบจะอัปเดตไฟล์ปลั๊กอิน สกิลทั้งหมด และสะพานเชื่อมต่อ UTF-8 ให้เป็นเวอร์ชันล่าสุดทันที
- **ไฟล์ Endpoint (`~/.slegal/mcp/endpoint`) และไฟล์ API Key ส่วนตัว (`~/.slegal/mcp/api_key`) จะไม่ถูกลบหรือเขียนทับ** จึงไม่ต้องกรอก URL หรือ API Key ใหม่
- *หมายเหตุสำหรับทีมบัญชี*: หากคีย์เดิมสร้างไว้ก่อนเปิด Phase 2 และยังไม่มี scope `accounting:draft` สามารถสร้างคีย์ใหม่ใน **ตั้งค่า > Integrations** โดยเลือก `accounting:read` + `accounting:draft` ตามตารางในขั้นที่ 1 แล้วเปลี่ยนคีย์ได้ทันที

---

## ความปลอดภัย (ทำไม Repository นี้เปิดเป็น Public ได้อย่างปลอดภัย)

1. **ไม่มี URL เซิร์ฟเวอร์จริง, API Key, หรือข้อมูลคดีใน Repository นี้แม้แต่ตัวเดียว**: URL สำนักงานและคีย์ส่วนตัวถูกเก็บแยกไว้บนเครื่องของผู้ใช้เองที่ `~/.slegal/mcp/endpoint` และ `~/.slegal/mcp/api_key` พร้อมการจำกัดสิทธิ์การเข้าถึงระดับผู้ใช้คนเดียว
2. **สิทธิ์ตามตัวตนผู้ใช้งาน (Per-User RBAC)**: ทุกคำสั่งที่วิ่งผ่าน S-Legal MCP ใช้สิทธิ์ของเจ้าของ API Key นั้นจริงบนเซิร์ฟเวอร์ S-Legal (แยกคีย์ทนายกับบัญชีขาดจากกัน, ซ่อนยอดเงิน QT สำหรับคีย์ทนายทั่วไป, และจำกัด Partner Ledger/OMEC เฉพาะ `partner-ledger.manage`)
3. **เส้นแดงทางบัญชี (7 Accounting Red-Line Locks)**: AI ไม่สามารถโอนเงินธนาคาร โพสต์ GL ข้ามสเตทเมนต์ธนาคาร แก้ไข `PV` ที่โพสต์แล้ว ยื่นแบบภาษี หรืออนุมัติ `AP`/`COMP`/`OMEC` ได้ ดูรายละเอียดเพิ่มเติมที่ [docs/SECURITY.md](docs/SECURITY.md)

---

## แก้ปัญหาเบื้องต้น (Troubleshooting)

- **Windows แจ้งว่าไม่พบ Python หรือเด้งไป Microsoft Store**: ดาวน์โหลดตัวติดตั้ง Python 3 จาก `https://www.python.org/downloads/` (ติ๊กช่อง **"Add python.exe to PATH"** ตอนติดตั้ง) แล้วรันคำสั่งติดตั้งใหม่อีกครั้ง
- **ข้อความภาษาไทยแสดงผลเพี้ยน (`???` หรือตัวประหลาด)**: ตัวติดตั้งตั้งค่า `-X utf8`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` และเขียนข้อมูลผ่านไบต์ UTF-8 โดยตรงแล้ว หากเคยติดตั้งเวอร์ชันเก่าไว้ ให้รันคำสั่งติดตั้งใหม่อีกครั้งและรีสตาร์ท Antigravity
- **ต้องการเปลี่ยน API Key หรือย้าย URL ระบบ**: ลบไฟล์ `~/.slegal/mcp/api_key` หรือ `~/.slegal/mcp/endpoint` แล้วรันคำสั่งติดตั้งซ้ำ
- **เคยตั้งค่า `"slegal"` ไว้ใน Global `mcp_config.json` มาก่อน**: ตัวติดตั้งจะสำรองไฟล์เดิมและช่วยลบรายการซ้ำให้โดยอัตโนมัติ (ไม่กระทบเซิร์ฟเวอร์ MCP ตัวอื่น) เพื่อให้ Antigravity โหลดจากปลั๊กอินชุดนี้เพียงจุดเดียว
