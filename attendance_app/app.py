from __future__ import annotations

import html
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).parent))

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

    col_level, col_classroom, col_date = st.columns([1, 1, 1])
    with col_level:
        level = st.selectbox("ระดับชั้น", attendance.LEVELS)
    with col_classroom:
        classroom = st.selectbox("ห้องเรียน", attendance.CLASSROOMS_BY_LEVEL[level])
    with col_date:
        selected_date_obj = st.date_input("วันที่", value=date.today())

    selected_date = selected_date_obj.isoformat()
    selected_day = attendance.day_from_date(selected_date_obj)
    st.caption(f"ระบบคำนวณวันให้อัตโนมัติ: {selected_day}")

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
                        "day": selected_day,
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
            "day": st.column_config.TextColumn("วัน", disabled=True),
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
                record["day"] = attendance.day_from_date(record["date"])
                duplicate, message = attendance.has_duplicate(record, existing_log, valid_records)
                if duplicate:
                    st.error(f"{record['student_id']} {record['student_name']}: {message}")
                    return
                valid_records.append(record)
            except ValueError as exc:
                st.error(f"{record.get('student_id', '')}: {exc}")
                return

        attendance_rows = attendance.records_to_attendance_rows(valid_records, user)
        submit_log_row = attendance.submit_row(selected_date, level, classroom, user)
        with st.spinner("กำลังบันทึกข้อมูลลง Google Sheets..."):
            sheets.append_rows("Attendance_Log", attendance_rows)
            sheets.append_rows("Submit_Log", [submit_log_row])
        st.session_state.temp_records = []
        st.success("บันทึกข้อมูลเรียบร้อยแล้ว")
        st.rerun()


def normalize_date_range(value) -> tuple[str, str]:
    if isinstance(value, tuple) and len(value) == 2:
        start, end = value
    elif isinstance(value, tuple) and len(value) == 1:
        start = end = value[0]
    else:
        start = end = value
    if start is None:
        start = date.today()
    if end is None:
        end = start
    if start > end:
        start, end = end, start
    return start.isoformat(), end.isoformat()


def render_report_filters(attendance_df: pd.DataFrame):
    st.subheader("ตัวกรองรายงาน")
    col1, col2 = st.columns([2, 1])
    with col1:
        date_range = st.date_input(
            "ช่วงวันที่รายงาน",
            value=(date.today(), date.today()),
            key="report_date_range",
        )
    with col2:
        level = st.selectbox("ระดับชั้น", [reports.ALL_OPTION] + attendance.LEVELS)

    start_date, end_date = normalize_date_range(date_range)
    filtered = reports.filter_attendance(attendance_df, start_date, end_date, level)
    return start_date, end_date, level, filtered


def bar_rows(summary: pd.DataFrame, label_column: str, value_column: str) -> str:
    if summary.empty:
        return "<p>ไม่มีข้อมูล</p>"
    max_value = max(int(summary[value_column].max()), 1)
    rows = []
    for _, row in summary.iterrows():
        label = html.escape(str(row[label_column]))
        value = int(row[value_column])
        width = max((value / max_value) * 100, 3 if value else 0)
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{label}</div>
              <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
              <div class="bar-value">{value}</div>
            </div>
            """
        )
    return "\n".join(rows)


def table_html(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p>ไม่มีข้อมูลรายการ</p>"
    columns = ["date", "classroom", "student_id", "student_name", "periods", "status", "note"]
    labels = {
        "date": "วันที่",
        "classroom": "ห้อง",
        "student_id": "เลขประจำตัว",
        "student_name": "ชื่อ-สกุล",
        "periods": "คาบ",
        "status": "สถานะ",
        "note": "หมายเหตุ",
    }
    available = [column for column in columns if column in df.columns]
    header = "".join(f"<th>{labels[column]}</th>" for column in available)
    rows = []
    for _, row in df[available].iterrows():
        rows.append("".join(f"<td>{html.escape(str(value))}</td>" for value in row))
    body = "".join(f"<tr>{row}</tr>" for row in rows)
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def printable_report_html(
    filtered: pd.DataFrame,
    selected_level: str,
    start_date: str,
    end_date: str,
) -> str:
    date_label = reports.date_range_label(start_date, end_date)
    pages = []

    if selected_level == reports.ALL_OPTION:
        level_summary = reports.summary_by_level(filtered)
        pages.append(
            f"""
            <section class="page">
              <h1>รายงานรวมทุกระดับชั้น</h1>
              <p class="meta">ช่วงวันที่: {html.escape(date_label)}</p>
              <h2>จำนวนรายการขาด/ลา/มาสาย ตามระดับชั้น</h2>
              {bar_rows(level_summary, "level", "จำนวนรายการขาด/ลา/มาสาย")}
            </section>
            """
        )

    for level in reports.levels_for_print(selected_level):
        level_df = filtered[filtered["level"].astype(str) == level]
        classroom_summary = reports.summary_by_classroom(filtered, level)
        pages.append(
            f"""
            <section class="page">
              <h1>รายงานระดับชั้น {html.escape(level)}</h1>
              <p class="meta">ช่วงวันที่: {html.escape(date_label)}</p>
              <h2>จำนวนรายการตามห้องเรียน</h2>
              {bar_rows(classroom_summary, "classroom", "จำนวนรายการ")}
              <h2>รายการนักเรียน</h2>
              {table_html(level_df)}
            </section>
            """
        )

    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: Arial, "Tahoma", sans-serif; color: #111827; }}
        .print-button {{
          border: 0; border-radius: 6px; padding: 10px 16px; background: #2563eb;
          color: white; font-size: 15px; cursor: pointer; margin-bottom: 16px;
        }}
        .page {{
          padding: 24px 28px; border: 1px solid #e5e7eb; border-radius: 8px;
          margin-bottom: 24px; background: #fff;
        }}
        h1 {{ font-size: 26px; margin: 0 0 4px; }}
        h2 {{ font-size: 18px; margin: 24px 0 12px; }}
        .meta {{ color: #4b5563; margin: 0 0 16px; }}
        .bar-row {{ display: grid; grid-template-columns: 90px 1fr 48px; gap: 10px; align-items: center; margin: 10px 0; }}
        .bar-label {{ font-weight: 700; }}
        .bar-track {{ height: 22px; background: #e5e7eb; border-radius: 999px; overflow: hidden; }}
        .bar-fill {{ height: 100%; background: #2563eb; }}
        .bar-value {{ text-align: right; font-weight: 700; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 8px; font-size: 13px; }}
        th, td {{ border: 1px solid #d1d5db; padding: 6px 8px; text-align: left; vertical-align: top; }}
        th {{ background: #f3f4f6; }}
        @media print {{
          .print-button {{ display: none; }}
          .page {{ border: 0; border-radius: 0; page-break-after: always; margin: 0; padding: 12mm; }}
          .page:last-child {{ page-break-after: auto; }}
        }}
      </style>
    </head>
    <body>
      <button class="print-button" onclick="window.print()">พิมพ์รายงาน</button>
      {"".join(pages)}
    </body>
    </html>
    """


def render_reports_dashboard_page() -> None:
    st.header("รายงานและแดชบอร์ด")
    attendance_df = sheets.load_attendance_log()
    start_date, end_date, level, filtered = render_report_filters(attendance_df)

    st.metric("จำนวนรายการในช่วงที่เลือก", len(filtered))

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(visualization.bar_by_level(filtered), use_container_width=True)
    with chart_col2:
        st.plotly_chart(visualization.bar_by_classroom(filtered, level), use_container_width=True)

    st.subheader("ตารางรายการ")
    st.dataframe(filtered, use_container_width=True, hide_index=True)

    csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "ดาวน์โหลดรายงาน CSV",
        data=csv,
        file_name=f"attendance_report_{start_date}_to_{end_date}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.subheader("รายงานสำหรับพิมพ์")
    st.caption("ถ้าเลือกระดับชั้นเป็นทั้งหมด ระบบจะทำหน้าแรกเป็นใบรวม และแยกหน้าตามระดับชั้น")
    components.html(
        printable_report_html(filtered, level, start_date, end_date),
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
        render_reports_dashboard_page()


if __name__ == "__main__":
    main()
