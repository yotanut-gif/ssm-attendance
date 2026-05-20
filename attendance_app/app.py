from __future__ import annotations

import html
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).parent))

from modules import attendance, auth, reports, sheets, visualization


st.set_page_config(page_title="ระบบเช็กนักเรียนขาดเรียน", page_icon="✅", layout="wide")


def initialize_state() -> None:
    st.session_state.setdefault("temp_records", [])


def load_base_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    with st.spinner("กำลังเชื่อมต่อ Google Sheets..."):
        sheets.ensure_required_worksheets()
        return sheets.load_students(), sheets.load_admin_teachers()


def normalize_date_range(value) -> tuple[str, str]:
    if isinstance(value, tuple) and len(value) == 2:
        start, end = value
    elif isinstance(value, tuple) and len(value) == 1:
        start = end = value[0]
    else:
        start = end = value
    start = start or date.today()
    end = end or start
    if start > end:
        start, end = end, start
    return start.isoformat(), end.isoformat()


def render_attendance_page(students_df: pd.DataFrame, user: dict) -> None:
    st.header("บันทึกการขาดเรียน")
    levels = attendance.levels_from_students(students_df)
    rooms_by_level = attendance.classrooms_by_level(students_df)

    col_date, col_level, col_classroom = st.columns([1, 1, 1])
    with col_date:
        selected_date_obj = st.date_input("วัน-เวลา", value=date.today())
    with col_level:
        level = st.selectbox("ระดับชั้น", levels)
    with col_classroom:
        classroom = st.selectbox("ห้องเรียน", rooms_by_level.get(level, []))

    selected_date = selected_date_obj.isoformat()
    selected_day = attendance.day_from_date(selected_date_obj)
    st.caption(f"{selected_day} | เวลาบันทึกปัจจุบัน {datetime.now().strftime('%H:%M:%S')}")

    existing_log = sheets.load_attendance_log()
    submit_log = sheets.load_submit_log()
    already_submitted = not submit_log[
        (submit_log["date"].astype(str) == selected_date)
        & (submit_log["classroom"].astype(str) == classroom)
    ].empty

    if already_submitted:
        st.info("ห้องนี้มีการส่งข้อมูลของวันที่เลือกแล้ว")

    action_col1, action_col2 = st.columns(2)
    no_absent = action_col1.button(
        "ไม่มีนักเรียนขาด/ลา/มาสาย",
        type="secondary",
        use_container_width=True,
        disabled=already_submitted,
    )
    clear_submit = action_col2.button(
        "ล้างสถานะส่งของห้องนี้",
        use_container_width=True,
        disabled=not already_submitted,
    )
    if no_absent:
        sheets.append_rows("Submit_Log", [attendance.submit_row(selected_date, level, classroom, user)])
        st.success("บันทึกแล้วว่าห้องนี้ไม่มีนักเรียนขาด/ลา/มาสาย")
        st.rerun()
    if clear_submit:
        removed = sheets.delete_rows_by_values(
            "Submit_Log",
            {"date": selected_date, "classroom": classroom},
        )
        st.success(f"ล้างสถานะส่งแล้ว {removed} รายการ")
        st.rerun()

    st.subheader("เพิ่มรายการนักเรียน")
    with st.form("add_attendance_record", clear_on_submit=True):
        input_col1, input_col2, input_col3, input_col4 = st.columns([1, 1, 1, 2])
        with input_col1:
            student_id = st.text_input("เลขประจำตัวนักเรียน 5 หลัก", max_chars=5)
        with input_col2:
            periods_raw = st.text_input("คาบเรียน", placeholder="เช่น 1-10 หรือ 1,3,4")
        with input_col3:
            status = st.selectbox("สถานะ", attendance.STATUSES)
        with input_col4:
            note = st.text_input("หมายเหตุ (ถ้ามี)")
        add_clicked = st.form_submit_button("เพิ่มรายการ", use_container_width=True)

    if add_clicked:
        if not student_id.isdigit() or len(student_id) != 5:
            st.error("เลขประจำตัวนักเรียนต้องเป็นตัวเลข 5 หลัก")
        else:
            student = attendance.find_student(student_id, students_df)
            if not student:
                st.error("ไม่พบเลขประจำตัวนักเรียนในชีต Students")
            else:
                try:
                    periods = attendance.parse_periods(periods_raw)
                    record = {
                        "date": selected_date,
                        "day": selected_day,
                        "level": attendance.level_from_classroom(student["classroom"]),
                        "classroom": student["classroom"],
                        "student_id": student["student_id"],
                        "student_name": student["student_name"],
                        "student_classroom": student["classroom"],
                        "periods": attendance.periods_to_text(periods),
                        "status": status,
                        "note": note.strip(),
                    }
                    duplicate, message = attendance.has_duplicate(
                        record, existing_log, st.session_state.temp_records
                    )
                    if duplicate:
                        st.error(message)
                    else:
                        st.session_state.temp_records.append(record)
                        st.success(f"เพิ่ม {student['student_name']} ห้อง {student['classroom']} แล้ว")
                except ValueError as exc:
                    st.error(str(exc))

    st.subheader("รายการที่รอส่ง")
    if not st.session_state.temp_records:
        st.info("ยังไม่มีรายการที่รอส่ง")
        return

    edited_df = st.data_editor(
        pd.DataFrame(st.session_state.temp_records),
        column_config={
            "date": st.column_config.TextColumn("วันที่", disabled=True),
            "day": st.column_config.TextColumn("วัน", disabled=True),
            "level": st.column_config.TextColumn("ระดับชั้น", disabled=True),
            "classroom": st.column_config.TextColumn("ห้องเรียน", disabled=True),
            "student_id": st.column_config.TextColumn("เลขประจำตัว", disabled=True),
            "student_name": st.column_config.TextColumn("ชื่อ-สกุล", disabled=True),
            "student_classroom": st.column_config.TextColumn("ห้องในทะเบียน", disabled=True),
            "periods": st.column_config.TextColumn("คาบเรียน", required=True),
            "status": st.column_config.SelectboxColumn("สถานะ", options=attendance.STATUSES, required=True),
            "note": st.column_config.TextColumn("หมายเหตุ"),
        },
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True,
        key="temp_editor",
    )
    st.session_state.temp_records = edited_df.to_dict("records")

    submit_col, clear_col = st.columns([2, 1])
    confirm = submit_col.button("ยืนยันส่งข้อมูลทั้งหมด", type="primary", use_container_width=True)
    clear = clear_col.button("ล้างรายการรอส่ง", use_container_width=True)

    if clear:
        st.session_state.temp_records = []
        st.rerun()

    if confirm:
        valid_records = []
        for record in st.session_state.temp_records:
            try:
                record["periods"] = attendance.periods_to_text(attendance.parse_periods(record["periods"]))
                record["day"] = attendance.day_from_date(record["date"])
                duplicate, message = attendance.has_duplicate(record, existing_log, valid_records)
                if duplicate:
                    st.error(f"{record['student_id']} {record['student_name']}: {message}")
                    return
                valid_records.append(record)
            except ValueError as exc:
                st.error(f"{record.get('student_id', '')}: {exc}")
                return

        sheets.append_rows("Attendance_Log", attendance.records_to_attendance_rows(valid_records, user))
        sheets.append_rows("Submit_Log", [attendance.submit_row(selected_date, level, classroom, user)])
        st.session_state.temp_records = []
        st.success("บันทึกข้อมูลเรียบร้อยแล้ว")
        st.rerun()


def render_report_filters(students_df: pd.DataFrame, attendance_df: pd.DataFrame):
    levels = attendance.levels_from_students(students_df)
    rooms_by_level = attendance.classrooms_by_level(students_df)
    st.subheader("ตัวกรองรายงาน")
    col_date, col_level, col_room = st.columns([2, 1, 1])
    with col_date:
        date_range = st.date_input("ช่วงวันที่รายงาน", value=(date.today(), date.today()))
    with col_level:
        level = st.selectbox("ระดับชั้น", [reports.ALL_OPTION] + levels, key="report_level")
    with col_room:
        room_options = [reports.ALL_OPTION]
        if level != reports.ALL_OPTION:
            room_options += rooms_by_level.get(level, [])
        classroom = st.selectbox("ห้องเรียน", room_options, key="report_room")
    start_date, end_date = normalize_date_range(date_range)
    filtered = reports.filter_attendance(attendance_df, start_date, end_date, level, classroom)
    return start_date, end_date, level, classroom, filtered


def submission_lists(status_df: pd.DataFrame) -> tuple[list[str], list[str]]:
    if status_df.empty:
        return [], []
    compact = status_df.drop_duplicates(["level", "classroom", "สถานะส่ง"])
    sent_df = compact[compact["สถานะส่ง"] == "ส่งแล้ว"]
    missing_df = compact[compact["สถานะส่ง"] == "ยังไม่ส่ง"]

    def labels(df: pd.DataFrame) -> list[str]:
        return [
            f"{row['level']} {row['classroom']}"
            for _, row in df[["level", "classroom"]]
            .drop_duplicates()
            .sort_values(["level", "classroom"])
            .iterrows()
        ]

    return labels(sent_df), labels(missing_df)


def render_submission_text(status_df: pd.DataFrame) -> None:
    sent, missing = submission_lists(status_df)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### ห้องที่ส่งแล้ว")
        st.write(", ".join(sent) if sent else "ไม่มี")
    with col2:
        st.markdown("### ห้องที่ยังไม่ส่ง")
        st.write(", ".join(missing) if missing else "ไม่มี")


def bar_rows(summary: pd.DataFrame, label_column: str, value_column: str) -> str:
    if summary.empty:
        return "<p>ไม่มีข้อมูล</p>"
    max_value = max(int(summary[value_column].max()), 1)
    rows = []
    for _, row in summary.iterrows():
        label = html.escape(str(row[label_column]))
        value = int(row[value_column])
        width = max((value / max_value) * 100, 3 if value else 0)
        rows.append(f'<div class="bar-row"><div class="bar-label">{label}</div><div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div><div class="bar-value">{value}</div></div>')
    return "\n".join(rows)


def compact_room_cards(summary: pd.DataFrame) -> str:
    if summary.empty:
        return "<p>ไม่มีข้อมูล</p>"
    cards = []
    for _, row in summary.iterrows():
        room = html.escape(str(row["classroom"]))
        value = int(row["จำนวนรายการ"])
        cards.append(
            f"""
            <div class="room-card">
              <div class="room-name">{room}</div>
              <div class="room-count">{value}</div>
            </div>
            """
        )
    return f'<div class="room-grid">{"".join(cards)}</div>'


def table_html(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p>ไม่มีข้อมูลรายการ</p>"
    columns = ["date", "classroom", "student_id", "student_name", "periods", "status", "note"]
    labels = {"date": "วันที่", "classroom": "ห้อง", "student_id": "เลขประจำตัว", "student_name": "ชื่อ-สกุล", "periods": "คาบ", "status": "สถานะ", "note": "หมายเหตุ"}
    available = [column for column in columns if column in df.columns]
    header = "".join(f"<th>{labels[column]}</th>" for column in available)
    body = ""
    for _, row in df[available].iterrows():
        body += "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in row) + "</tr>"
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def printable_report_html(
    students_df: pd.DataFrame,
    filtered: pd.DataFrame,
    submit_status: pd.DataFrame,
    selected_level: str,
    start_date: str,
    end_date: str,
) -> str:
    levels = attendance.levels_from_students(students_df)
    rooms_by_level = attendance.classrooms_by_level(students_df)
    date_label = reports.date_range_label(start_date, end_date)
    pages = []
    sent, missing = submission_lists(submit_status)
    sent_text = ", ".join(sent) if sent else "ไม่มี"
    missing_text = ", ".join(missing) if missing else "ไม่มี"

    if selected_level == reports.ALL_OPTION:
        level_summary = reports.summary_by_level(filtered, levels)
        pages.append(f"""
        <section class="page">
          <h1>รายงานรวมทุกระดับชั้น</h1>
          <p class="meta">ช่วงวันที่: {html.escape(date_label)}</p>
          <h2>จำนวนรายการขาด/ลา/มาสาย ตามระดับชั้น</h2>
          {bar_rows(level_summary, "level", "จำนวนรายการขาด/ลา/มาสาย")}
          <h2>สถานะการส่งข้อมูล</h2>
          <p><strong>ห้องที่ส่งแล้ว:</strong> {html.escape(sent_text)}</p>
          <p><strong>ห้องที่ยังไม่ส่ง:</strong> {html.escape(missing_text)}</p>
        </section>
        """)

    for level in reports.levels_for_print(selected_level, levels):
        level_df = filtered[filtered["level"].astype(str) == level]
        room_summary = reports.summary_by_classroom(level_df, rooms_by_level.get(level, []))
        level_submit = submit_status[submit_status["level"].astype(str) == level]
        level_sent, level_missing = submission_lists(level_submit)
        pages.append(f"""
        <section class="page">
          <h1>รายงานระดับชั้น {html.escape(level)}</h1>
          <p class="meta">ช่วงวันที่: {html.escape(date_label)}</p>
          <h2>จำนวนรายการตามห้องเรียน</h2>
          {compact_room_cards(room_summary)}
          <h2>ห้องที่ส่งแล้ว / ยังไม่ส่ง</h2>
          <p><strong>ห้องที่ส่งแล้ว:</strong> {html.escape(", ".join(level_sent) if level_sent else "ไม่มี")}</p>
          <p><strong>ห้องที่ยังไม่ส่ง:</strong> {html.escape(", ".join(level_missing) if level_missing else "ไม่มี")}</p>
          <h2>รายการนักเรียน</h2>
          {table_html(level_df)}
        </section>
        """)

    return f"""
    <!doctype html><html><head><meta charset="utf-8"><style>
    body {{ font-family: Arial, Tahoma, sans-serif; color: #111827; }}
    .print-button {{ border:0;border-radius:6px;padding:10px 16px;background:#2563eb;color:white;font-size:15px;cursor:pointer;margin-bottom:16px; }}
    .page {{ padding:24px 28px;border:1px solid #e5e7eb;border-radius:8px;margin-bottom:24px;background:#fff; }}
    h1 {{ font-size:26px;margin:0 0 4px; }} h2 {{ font-size:18px;margin:24px 0 12px; }} .meta {{ color:#4b5563;margin:0 0 16px; }}
    .bar-row {{ display:grid;grid-template-columns:90px 1fr 48px;gap:10px;align-items:center;margin:10px 0; }}
    .bar-label {{ font-weight:700; }} .bar-track {{ height:22px;background:#e5e7eb;border-radius:999px;overflow:hidden; }} .bar-fill {{ height:100%;background:#2563eb; }} .bar-value {{ text-align:right;font-weight:700; }}
    .room-grid {{ display:grid;grid-template-columns:repeat(4, 1fr);gap:10px;margin-top:10px; }}
    .room-card {{ border:1px solid #d1d5db;border-radius:8px;padding:10px 12px;display:flex;justify-content:space-between;align-items:center;background:#f9fafb; }}
    .room-name {{ font-weight:700; }} .room-count {{ font-size:20px;font-weight:800;color:#2563eb; }}
    table {{ border-collapse:collapse;width:100%;margin-top:8px;font-size:13px; }} th,td {{ border:1px solid #d1d5db;padding:6px 8px;text-align:left;vertical-align:top; }} th {{ background:#f3f4f6; }}
    @media print {{ .print-button {{ display:none; }} .page {{ border:0;border-radius:0;page-break-after:always;margin:0;padding:12mm; }} .page:last-child {{ page-break-after:auto; }} }}
    </style></head><body><button class="print-button" onclick="window.print()">พิมพ์รายงาน</button>{"".join(pages)}</body></html>
    """


def render_reports_dashboard_page(students_df: pd.DataFrame) -> None:
    st.header("รายงานและแดชบอร์ด")
    attendance_df = sheets.load_attendance_log()
    submit_df = sheets.load_submit_log()
    start_date, end_date, level, classroom, filtered = render_report_filters(students_df, attendance_df)

    levels = attendance.levels_from_students(students_df)
    rooms_by_level = attendance.classrooms_by_level(students_df)
    if level == reports.ALL_OPTION:
        chart_rooms = sum([rooms_by_level[item] for item in levels], [])
    else:
        chart_rooms = rooms_by_level.get(level, [])
    if classroom != reports.ALL_OPTION:
        chart_rooms = [classroom]

    submit_status = reports.submission_status(students_df, submit_df, start_date, end_date, level, classroom)

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(visualization.bar_by_level(filtered, levels), use_container_width=True)
        st.plotly_chart(visualization.submission_bar(submit_status), use_container_width=True)
    with chart_col2:
        st.plotly_chart(visualization.bar_by_classroom_status(filtered, chart_rooms), use_container_width=True)

    st.subheader("ห้องที่ส่งแล้ว / ยังไม่ส่ง")
    render_submission_text(submit_status)
    st.subheader("ตารางรายการ")
    st.dataframe(filtered, use_container_width=True, hide_index=True)

    csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button("ดาวน์โหลดรายงาน CSV", data=csv, file_name=f"attendance_report_{start_date}_to_{end_date}.csv", mime="text/csv", use_container_width=True)

    st.subheader("รายงานสำหรับพิมพ์")
    components.html(
        printable_report_html(students_df, filtered, submit_status, level, start_date, end_date),
        height=900,
        scrolling=True,
    )


def main() -> None:
    initialize_state()
    try:
        students_df, teachers_df = load_base_data()
    except Exception as exc:
        st.error("เชื่อมต่อ Google Sheets ไม่สำเร็จ")
        st.exception(exc)
        return

    user = auth.require_login(teachers_df)
    if not user:
        return

    auth.sidebar_user_box(user)
    page = st.sidebar.radio("เมนู", ["บันทึกการขาดเรียน", "รายงานและแดชบอร์ด"])
    if page == "บันทึกการขาดเรียน":
        render_attendance_page(students_df, user)
    else:
        render_reports_dashboard_page(students_df)


if __name__ == "__main__":
    main()
