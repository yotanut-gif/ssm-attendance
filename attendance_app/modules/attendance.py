from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd


STATUSES = ["ขาด", "ลาป่วย", "ลากิจ", "มาสาย"]
DAY_LABELS = {
    0: "วันจันทร์",
    1: "วันอังคาร",
    2: "วันพุธ",
    3: "วันพฤหัสบดี",
    4: "วันศุกร์",
    5: "วันเสาร์",
    6: "วันอาทิตย์",
}


def normalize_student_id(value: str) -> str:
    return str(value).strip().replace(".0", "").zfill(5)


def level_from_classroom(classroom: str) -> str:
    match = re.search(r"ม\.\s*(\d+)", str(classroom))
    if not match:
        return str(classroom).split("/")[0].strip()
    return f"ม.{match.group(1)}"


def classroom_sort_key(classroom: str) -> tuple[int, int, str]:
    match = re.search(r"ม\.\s*(\d+)\s*/\s*(\d+)", str(classroom))
    if match:
        return int(match.group(1)), int(match.group(2)), str(classroom)
    level_match = re.search(r"ม\.\s*(\d+)", str(classroom))
    if level_match:
        return int(level_match.group(1)), 0, str(classroom)
    return 999, 999, str(classroom)


def levels_from_students(students_df: pd.DataFrame) -> list[str]:
    classrooms = students_df["ห้องเรียน"].dropna().astype(str).unique().tolist()
    levels = sorted({level_from_classroom(room) for room in classrooms}, key=lambda x: int(re.search(r"\d+", x).group()) if re.search(r"\d+", x) else 999)
    return levels


def classrooms_by_level(students_df: pd.DataFrame) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    classrooms = sorted(
        students_df["ห้องเรียน"].dropna().astype(str).str.strip().unique().tolist(),
        key=classroom_sort_key,
    )
    for classroom in classrooms:
        result.setdefault(level_from_classroom(classroom), []).append(classroom)
    return result


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def day_from_date(value: date | str) -> str:
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return DAY_LABELS[value.weekday()]


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
    clean_id = normalize_student_id(student_id)
    normalized_ids = students_df["เลขประจำตัว"].astype(str).map(normalize_student_id)
    matches = students_df[normalized_ids == clean_id]
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


def submit_row(date_value: str, level: str, classroom: str, user: dict) -> list[str]:
    return [
        now_text(),
        date_value,
        day_from_date(date_value),
        level,
        classroom,
        user["username"],
        user["name"],
        "TRUE",
    ]
