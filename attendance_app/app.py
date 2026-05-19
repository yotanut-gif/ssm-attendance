from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from modules import attendance, auth, reports, sheets, visualization


st.set_page_config(
    page_title="ระบบเช็กนักเรียนขาดเรียน",
    page_icon="✅",
    layout="wide",
)


def initialize_state() -> None:
    st.session_state.setdefault("temp_records", [])


def load_base_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    with st.spinner("กำลังเชื่อมต่อ Google Sheets..."):
        sheets.ensure_required_worksheets()
        students_df = sheets.load_students()
        teachers_df = sheets.load_admin_teachers()
    return students_df, teachers_df


def render_attendance_page(students_df: pd.DataFrame, user: dict) -> None:
    st.header("บันทึกการขาดเรียน")

    col_day, col_level, col_classroom, col_date = st.columns([1, 1, 1, 1])
    with col_day:
        day = st.selectbox(
            "วัน",
            attendance.DAY_OPTIONS,
            format_func=lambda value: attendance.DAY_LABELS[value],
        )
    with col_level:
        level = st.selectbox("ระดับชั้น", attendance.LEVELS)
    with col_classroom:
        classroom = st.selectbox("ห้องเรียน", attendance.CLASSROOMS_BY_LEVEL[level])
    with col_date:
        selected_date = st.date_input("วันที่", value=date.today()).isoformat()

    st.subheader("เพิ่มรายการนักเรียน")
    existing_log = sheets.load_attendance_log()
    with st.form("add_attendance_record", clear_on_submit=True):
        input_col1, input_col2, input_col3, input_col4 = st.columns([1, 1, 1, 2])
        with input_col1:
            student_id = st.text_input("เลขประจำตัวนักเรียน 5 หลัก", max_chars=5)
        with input_col2:
            periods_raw = st.text_input("คาบเรียน", placeholder="เช่น 1-8 หรือ 1,3,4")
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
                        "day": day,
                        "level": level,
                        "classroom": classroom,
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
                        st.success(
                            f"เพิ่ม {student['student_name']} ห้อง {student['classroom']} แล้ว"
                        )
                except ValueError as exc:
                    st.error(str(exc))

    st.subheader("รายการที่รอส่ง")
    temp_records = st.session_state.temp_records
    if not temp_records:
        st.info("ยังไม่มีรายการที่รอส่ง")
        return

    edited_df = st.data_editor(
        pd.DataFrame(temp_records),
        column_config={
            "date": st.column_config.TextColumn("วันที่", disabled=True),
            "day": st.column_config.SelectboxColumn(
                "วัน", options=attendance.DAY_OPTIONS, required=True
            ),
            "level": st.column_config.SelectboxColumn(
                "ระดับชั้น", options=attendance.LEVELS, required=True
            ),
            "classroom": st.column_config.SelectboxColumn(
                "ห้องเรียน",
                options=sum(attendance.CLASSROOMS_BY_LEVEL.values(), []),
                required=True,
            ),
            "student_id": st.column_config.TextColumn("เลขประจำตัว", disabled=True),
            "student_name": st.column_config.TextColumn("ชื่อ-สกุล", disabled=True),
            "student_classroom": st.column_config.TextColumn("ห้องในทะเบียน", disabled=True),
            "periods": st.column_config.TextColumn("คาบเรียน", required=True),
            "status": st.column_config.SelectboxColumn(
                "สถานะ", options=attendance.STATUSES, required=True
            ),
            "note": st.column_config.TextColumn("หมายเหตุ"),
        },
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True,
        key="temp_editor",
    )
    st.session_state.temp_records = edited_df.to_dict("records")

    submit_col, clear_col = st.columns([2, 1])
    with submit_col:
        confirm = st.button("ยืนยันส่งข้อมูลทั้งหมด", type="primary", use_container_width=True)
    with clear_col:
        clear = st.button("ล้างรายการรอส่ง", use_container_width=True)

    if clear:
        st.session_state.temp_records = []
        st.rerun()

    if confirm:
        valid_records = []
        for record in st.session_state.temp_records:
            try:
                record["periods"] = attendance.periods_to_text(
                    attendance.parse_periods(record["periods"])
                )
                duplicate, message = attendance.has_duplicate(record, existing_log, valid_records)
                if duplicate:
                    st.error(f"{record['student_id']} {record['student_name']}: {message}")
                    return
                valid_records.append(record)
            except ValueError as exc:
                st.error(f"{record.get('student_id', '')}: {exc}")
                return

        attendance_rows = attendance.records_to_attendance_rows(valid_records, user)
        submit_log_row = attendance.submit_row(selected_date, day, level, classroom, user)
        with st.spinner("กำลังบันทึกข้อมูลลง Google Sheets..."):
            sheets.append_rows("Attendance_Log", attendance_rows)
            sheets.append_rows("Submit_Log", [submit_log_row])
        st.session_state.temp_records = []
        st.success("บันทึกข้อมูลเรียบร้อยแล้ว")
        st.rerun()


def render_report_filters(attendance_df: pd.DataFrame):
    st.subheader("ตัวกรองรายงาน")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        selected_date = st.date_input("วันที่รายงาน", value=date.today(), key="report_date").isoformat()
    with col2:
        day = st.selectbox("วัน", ["ทั้งหมด"] + attendance.DAY_OPTIONS, key="report_day")
    with col3:
        level = st.selectbox("ระดับชั้น", ["ทั้งหมด"] + attendance.LEVELS, key="report_level")
    with col4:
        classroom_options = ["ทั้งหมด"] + sum(attendance.CLASSROOMS_BY_LEVEL.values(), [])
        classroom = st.selectbox("ห้องเรียน", classroom_options, key="report_classroom")
    filtered = reports.filter_attendance(attendance_df, selected_date, day, level, classroom)
    return selected_date, day, level, classroom, filtered


def render_reports_page() -> None:
    st.header("รายงานการขาดเรียน")
    attendance_df = sheets.load_attendance_log()
    selected_date, day, level, classroom, filtered = render_report_filters(attendance_df)

    st.metric("จำนวนรายการ", len(filtered))
    st.dataframe(filtered, use_container_width=True, hide_index=True)

    csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "ดาวน์โหลดรายงาน CSV",
        data=csv,
        file_name=f"attendance_report_{selected_date}.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_dashboard_page() -> None:
    st.header("แดชบอร์ด")
    attendance_df = sheets.load_attendance_log()
    _, _, _, _, filtered = render_report_filters(attendance_df)

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(visualization.bar_by_level(filtered), use_container_width=True)
        st.plotly_chart(visualization.bar_by_period(filtered), use_container_width=True)
    with col2:
        st.plotly_chart(visualization.bar_by_classroom(filtered), use_container_width=True)
        st.plotly_chart(visualization.donut_by_status(filtered), use_container_width=True)


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
    page = st.sidebar.radio("เมนู", ["บันทึกการขาดเรียน", "รายงาน", "แดชบอร์ด"])

    if page == "บันทึกการขาดเรียน":
        render_attendance_page(students_df, user)
    elif page == "รายงาน":
        render_reports_page()
    else:
        render_dashboard_page()


if __name__ == "__main__":
    main()
