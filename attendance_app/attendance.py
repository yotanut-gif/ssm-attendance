from __future__ import annotations

from datetime import datetime

import pandas as pd


STATUSES = ["ขาด", "ลาป่วย", "ลากิจ", "มาสาย"]
LEVELS = ["ม.1", "ม.2", "ม.3"]
CLASSROOMS_BY_LEVEL = {
    "ม.1": ["ม.1/1", "ม.1/2"],
    "ม.2": ["ม.2/1", "ม.2/2"],
    "ม.3": ["ม.3/1", "ม.3/2"],
}
DAY_OPTIONS = ["Monday", "Tuesday"]
DAY_LABELS = {"Monday": "วันจันทร์", "Tuesday": "วันอังคาร"}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_periods(raw_value: str) -> list[int]:
    value = str(raw_value).replace(" ", "")
    if not value:
        raise ValueError("กรุณาระบุคาบเรียน")

    periods: set[int] = set()
    for part in value.split(","):
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            if not start_text.isdigit() or not end_text.isdigit():
                raise ValueError("รูปแบบคาบเรียนไม่ถูกต้อง")
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError("ช่วงคาบเรียนต้องเรียงจากน้อยไปมาก")
            periods.update(range(start, end + 1))
        else:
            if not part.isdigit():
                raise ValueError("รูปแบบคาบเรียนไม่ถูกต้อง")
            periods.add(int(part))

    if not periods:
        raise ValueError("กรุณาระบุคาบเรียน")
    invalid = [period for period in periods if period < 1 or period > 8]
    if invalid:
        raise ValueError("คาบเรียนต้องอยู่ระหว่าง 1 ถึง 8")
    return sorted(periods)


def periods_to_text(periods: list[int]) -> str:
    return ",".join(str(period) for period in sorted(periods))


def periods_from_text(value: str) -> set[int]:
    try:
        return set(parse_periods(value))
    except ValueError:
        return set()


def find_student(student_id: str, students_df: pd.DataFrame) -> dict | None:
    clean_id = str(student_id).strip().zfill(5)
    matches = students_df[students_df["เลขประจำตัว"].str.zfill(5) == clean_id]
    if matches.empty:
        return None
    row = matches.iloc[0].to_dict()
    return {
        "student_id": clean_id,
        "student_name": row["ชื่อ-สกุล"],
        "classroom": row["ห้องเรียน"],
        "number": row["เลขที่"],
    }


def has_duplicate(
    candidate: dict,
    existing_log: pd.DataFrame,
    temp_records: list[dict],
) -> tuple[bool, str]:
    candidate_periods = periods_from_text(candidate["periods"])
    sources = [
        ("รายการที่รอส่ง", pd.DataFrame(temp_records)),
        ("Attendance_Log", existing_log),
    ]
    for label, df in sources:
        if df.empty:
            continue
        required = {"date", "student_id", "periods", "status"}
        if not required.issubset(df.columns):
            continue
        matches = df[
            (df["date"].astype(str) == str(candidate["date"]))
            & (df["student_id"].astype(str).str.zfill(5) == candidate["student_id"])
            & (df["status"].astype(str) == candidate["status"])
        ]
        for _, row in matches.iterrows():
            if candidate_periods & periods_from_text(row["periods"]):
                return True, f"พบรายการซ้ำใน {label}"
    return False, ""


def records_to_attendance_rows(records: list[dict], user: dict) -> list[list[str]]:
    rows: list[list[str]] = []
    timestamp = now_text()
    for record in records:
        rows.append(
            [
                timestamp,
                record["date"],
                record["day"],
                record["level"],
                record["classroom"],
                record["student_id"],
                record["student_name"],
                record["periods"],
                record["status"],
                user["username"],
                user["name"],
                record.get("note", ""),
            ]
        )
    return rows


def submit_row(date: str, day: str, level: str, classroom: str, user: dict) -> list[str]:
    return [
        now_text(),
        date,
        day,
        level,
        classroom,
        user["username"],
        user["name"],
        "TRUE",
    ]
