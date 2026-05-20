from __future__ import annotations

from typing import Iterable

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

STUDENTS_COLUMNS = ["ห้องเรียน", "เลขที่", "เลขประจำตัว", "ชื่อ-สกุล"]
ADMIN_COLUMNS = ["ครูผู้ดูแลระบบ", "ชื่อ-สกุล", "Username", "Password", "บทบาท"]
ATTENDANCE_COLUMNS = [
    "timestamp",
    "date",
    "day",
    "level",
    "classroom",
    "student_id",
    "student_name",
    "periods",
    "status",
    "teacher_username",
    "teacher_name",
    "note",
]
SUBMIT_COLUMNS = [
    "timestamp",
    "date",
    "day",
    "level",
    "classroom",
    "teacher_username",
    "teacher_name",
    "submitted",
]

WORKSHEET_HEADERS = {
    "Students": STUDENTS_COLUMNS,
    "Admin_Teachers": ADMIN_COLUMNS,
    "Attendance_Log": ATTENDANCE_COLUMNS,
    "Submit_Log": SUBMIT_COLUMNS,
}


def is_demo_mode() -> bool:
    try:
        return "spreadsheet_id" not in st.secrets or "gcp_service_account" not in st.secrets
    except Exception:
        return True


def _demo_students() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["ม.1/1", "1", "10001", "เด็กชายกิตติพงษ์ ใจดี"],
            ["ม.1/1", "2", "10002", "เด็กหญิงณัฐชา แสงทอง"],
            ["ม.1/2", "1", "10003", "เด็กชายธนกร รักเรียน"],
            ["ม.2/1", "1", "20001", "เด็กหญิงปาริชาติ สุขใจ"],
            ["ม.2/2", "1", "20002", "เด็กชายพีรพล ตั้งใจ"],
            ["ม.3/1", "1", "30001", "เด็กหญิงมนัสนันท์ ศรีสุข"],
            ["ม.3/2", "1", "30002", "เด็กชายวรากร ขยันดี"],
        ],
        columns=STUDENTS_COLUMNS,
    )


def _demo_admin_teachers() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["ครูเวร", "ครูสมชาย ใจงาม", "teacher1", "123456", "teacher"],
            ["ผู้ดูแลระบบ", "ครูอรทัย แก้วใส", "admin", "654321", "admin"],
        ],
        columns=ADMIN_COLUMNS,
    )


def _demo_df(name: str) -> pd.DataFrame:
    if name == "Students":
        return _demo_students()
    if name == "Admin_Teachers":
        return _demo_admin_teachers()
    key = f"demo_{name}"
    if key not in st.session_state:
        st.session_state[key] = pd.DataFrame(columns=WORKSHEET_HEADERS[name])
    return st.session_state[key].copy()


def _service_account_info() -> dict:
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("ไม่พบข้อมูล gcp_service_account ใน Streamlit secrets")
    return dict(st.secrets["gcp_service_account"])


@st.cache_resource(show_spinner=False)
def get_client() -> gspread.Client:
    credentials = Credentials.from_service_account_info(
        _service_account_info(), scopes=SCOPES
    )
    return gspread.authorize(credentials)


@st.cache_resource(show_spinner=False)
def get_spreadsheet() -> gspread.Spreadsheet:
    spreadsheet_id = st.secrets.get("spreadsheet_id")
    if not spreadsheet_id:
        raise RuntimeError("ไม่พบ spreadsheet_id ใน Streamlit secrets")
    return get_client().open_by_key(spreadsheet_id)


@st.cache_resource(show_spinner=False)
def get_worksheet_map() -> dict[str, gspread.Worksheet]:
    spreadsheet = get_spreadsheet()
    return {worksheet.title: worksheet for worksheet in spreadsheet.worksheets()}


def get_or_create_worksheet(name: str, headers: Iterable[str]) -> gspread.Worksheet:
    spreadsheet = get_spreadsheet()
    worksheet_map = get_worksheet_map()
    if name not in worksheet_map:
        worksheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=len(list(headers)))
        worksheet.append_row(list(headers))
        get_worksheet_map.clear()
        return worksheet

    worksheet = worksheet_map[name]
    values = worksheet.get_all_values()
    if not values:
        worksheet.append_row(list(headers))
    return worksheet


def ensure_required_worksheets() -> None:
    if is_demo_mode():
        return
    worksheet_map = get_worksheet_map()
    for name, headers in WORKSHEET_HEADERS.items():
        if name in worksheet_map:
            continue
        get_or_create_worksheet(name, headers)


@st.cache_data(ttl=300, show_spinner=False)
def load_worksheet_df(name: str) -> pd.DataFrame:
    if is_demo_mode():
        return _demo_df(name).fillna("").astype(str)
    headers = WORKSHEET_HEADERS[name]
    worksheet = get_or_create_worksheet(name, headers)
    rows = worksheet.get_all_records()
    df = pd.DataFrame(rows)
    for column in headers:
        if column not in df.columns:
            df[column] = ""
    return df[headers].fillna("").astype(str)


def clear_data_cache() -> None:
    load_worksheet_df.clear()


def append_rows(name: str, rows: list[list[str]]) -> None:
    if not rows:
        return
    if is_demo_mode():
        key = f"demo_{name}"
        existing = st.session_state.get(
            key, pd.DataFrame(columns=WORKSHEET_HEADERS[name])
        )
        new_rows = pd.DataFrame(rows, columns=WORKSHEET_HEADERS[name])
        st.session_state[key] = pd.concat([existing, new_rows], ignore_index=True)
        clear_data_cache()
        return
    worksheet = get_or_create_worksheet(name, WORKSHEET_HEADERS[name])
    worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    clear_data_cache()


def delete_rows_by_values(name: str, criteria: dict[str, str]) -> int:
    headers = WORKSHEET_HEADERS[name]
    if is_demo_mode():
        key = f"demo_{name}"
        existing = st.session_state.get(key, pd.DataFrame(columns=headers)).copy()
        if existing.empty:
            return 0
        mask = pd.Series(True, index=existing.index)
        for column, value in criteria.items():
            mask &= existing[column].astype(str) == str(value)
        removed = int(mask.sum())
        st.session_state[key] = existing[~mask].reset_index(drop=True)
        clear_data_cache()
        return removed

    worksheet = get_or_create_worksheet(name, headers)
    rows = worksheet.get_all_records()
    if not rows:
        return 0
    df = pd.DataFrame(rows).astype(str)
    mask = pd.Series(True, index=df.index)
    for column, value in criteria.items():
        mask &= df[column].astype(str) == str(value)
    row_numbers = (df[mask].index + 2).tolist()
    for row_number in sorted(row_numbers, reverse=True):
        worksheet.delete_rows(int(row_number))
    clear_data_cache()
    return len(row_numbers)


def load_students() -> pd.DataFrame:
    df = load_worksheet_df("Students")
    df["เลขประจำตัว"] = (
        df["เลขประจำตัว"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(5)
    )
    df["เลขที่"] = df["เลขที่"].astype(str).str.replace(r"\.0$", "", regex=True)
    df["ห้องเรียน"] = df["ห้องเรียน"].astype(str).str.strip()
    df["ชื่อ-สกุล"] = df["ชื่อ-สกุล"].astype(str).str.strip()
    return df


def load_admin_teachers() -> pd.DataFrame:
    df = load_worksheet_df("Admin_Teachers")
    df["Username"] = df["Username"].str.strip()
    df["Password"] = df["Password"].str.zfill(6)
    return df


def load_attendance_log() -> pd.DataFrame:
    return load_worksheet_df("Attendance_Log")


def load_submit_log() -> pd.DataFrame:
    return load_worksheet_df("Submit_Log")
