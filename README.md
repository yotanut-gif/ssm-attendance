# ระบบเช็กนักเรียนขาดเรียนด้วย Streamlit และ Google Sheets

เว็บแอปนี้ใช้สำหรับให้ครูเข้าสู่ระบบ บันทึกนักเรียนขาดเรียนทีละรายการ ตรวจสอบข้อมูลนักเรียนจากชีต `Students` และบันทึกผลลง `Attendance_Log` พร้อมบันทึกการส่งงานลง `Submit_Log`

## โครงสร้างโปรเจกต์

```text
attendance_app/
  app.py
  requirements.txt
  README.md
  .streamlit/secrets.toml.example
  modules/auth.py
  modules/sheets.py
  modules/attendance.py
  modules/reports.py
  modules/visualization.py
```

## Google Sheets worksheets

ต้องมีชีตต่อไปนี้ใน Google Sheets ไฟล์เดียวกัน

### Students

```text
ห้องเรียน, เลขที่, เลขประจำตัว, ชื่อ-สกุล
```

### Admin_Teachers

```text
ครูผู้ดูแลระบบ, ชื่อ-สกุล, Username, Password, บทบาท
```

### Attendance_Log

```text
timestamp, date, day, level, classroom, student_id, student_name, periods, status, teacher_username, teacher_name, note
```

### Submit_Log

```text
timestamp, date, day, level, classroom, teacher_username, teacher_name, submitted
```

ถ้ายังไม่มี `Attendance_Log` หรือ `Submit_Log` แอปจะสร้าง worksheet พร้อมหัวตารางให้อัตโนมัติเมื่อ service account มีสิทธิ์แก้ไขไฟล์

## การตั้งค่า Google Cloud service account

1. เปิด [Google Cloud Console](https://console.cloud.google.com/)
2. สร้างโปรเจกต์ใหม่ หรือเลือกโปรเจกต์ที่มีอยู่
3. ไปที่ **APIs & Services > Library**
4. เปิดใช้งาน **Google Sheets API**
5. ไปที่ **IAM & Admin > Service Accounts**
6. สร้าง service account ใหม่
7. เปิด service account ที่สร้างไว้ แล้วไปที่ **Keys**
8. กด **Add key > Create new key > JSON**
9. ดาวน์โหลดไฟล์ JSON เก็บไว้

## แชร์ Google Sheet ให้ service account

1. เปิดไฟล์ Google Sheets ที่ใช้เป็นฐานข้อมูล
2. กด **Share**
3. คัดลอกค่า `client_email` จากไฟล์ JSON ของ service account
4. เพิ่มอีเมลนั้นใน Google Sheet
5. ให้สิทธิ์เป็น **Editor**

## ตั้งค่า Streamlit secrets

1. คัดลอกไฟล์ตัวอย่าง

```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

2. ใส่ Google Sheet ID

Google Sheet ID คือค่าระหว่าง `/d/` และ `/edit` ใน URL เช่น

```text
https://docs.google.com/spreadsheets/d/THIS_IS_THE_SPREADSHEET_ID/edit
```

3. ใส่ข้อมูล service account จากไฟล์ JSON ในส่วน `[gcp_service_account]`

ตัวอย่างโครงสร้างอยู่ใน `.streamlit/secrets.toml.example`

## ติดตั้งและรัน

```bash
cd attendance_app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## การใช้งาน

1. เข้าสู่ระบบด้วย `Username` และ `Password` 6 หลักจากชีต `Admin_Teachers`
2. เลือกวัน ระดับชั้น ห้องเรียน และวันที่
3. กรอกเลขประจำตัวนักเรียน 5 หลัก
4. ระบบจะแสดงชื่อและห้องเรียนจากชีต `Students`
5. เลือกสถานะ: `ขาด`, `ลาป่วย`, `ลากิจ`, `มาสาย`
6. ระบุคาบเรียน เช่น `1-8` หรือ `1,3,4`
7. เพิ่มรายการ ตรวจสอบ/แก้ไข/ลบรายการที่รอส่ง
8. กดยืนยันเพื่อบันทึกลง Google Sheets

## การป้องกันข้อมูลซ้ำ

แอปตรวจซ้ำก่อนเพิ่มรายการและก่อนส่งข้อมูล โดยไม่อนุญาตรายการที่มีค่าเหมือนกันในเงื่อนไข:

```text
date + student_id + period + status
```

ตัวอย่าง: ถ้าเคยบันทึกนักเรียนคนเดิม วันที่เดียวกัน สถานะเดียวกัน คาบ 3 แล้ว จะเพิ่มซ้ำไม่ได้ แม้ผู้ใช้กรอกเป็น `1-8`

## รายงานและแดชบอร์ด

หน้ารายงานรองรับการกรองตามวันที่ วัน ระดับชั้น และห้องเรียน พร้อมตารางสรุป:

- สรุปตามระดับชั้น
- สรุปตามห้องเรียน
- สรุปตามคาบเรียน
- สรุปตามสถานะ
- สรุปรายวันทั้งโรงเรียน
- ห้องเรียนที่ยังไม่ส่งข้อมูล
- ดาวน์โหลด CSV

หน้าแดชบอร์ดมีกราฟ:

- Bar chart ตามระดับชั้น
- Bar chart ตามห้องเรียน
- Bar chart ตามคาบเรียน
- Donut chart ตามสถานะ
