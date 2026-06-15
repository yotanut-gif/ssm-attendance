from __future__ import annotations

import pandas as pd
import streamlit as st


def authenticate_user(username: str, password: str, teachers_df: pd.DataFrame) -> dict | None:
    username = username.strip()
    password = password.strip().zfill(6)
    matches = teachers_df[
        (teachers_df["Username"].str.strip() == username)
        & (teachers_df["Password"].str.zfill(6) == password)
    ]
    if matches.empty:
        return None

    row = matches.iloc[0].to_dict()
    return {
        "username": row.get("Username", username),
        "name": row.get("ชื่อ-สกุล", ""),
        "admin_teacher": row.get("ครูผู้ดูแลระบบ", ""),
        "role": row.get("บทบาท", ""),
    }


def login_panel(teachers_df: pd.DataFrame) -> bool:
    st.title("ระบบเช็กนักเรียนขาดเรียน")
    st.caption("เข้าสู่ระบบด้วย Username และรหัสผ่าน 6 หลักของครูผู้ดูแล")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password 6 หลัก", type="password", max_chars=6)
        submitted = st.form_submit_button("เข้าสู่ระบบ", use_container_width=True)

    if submitted:
        user = authenticate_user(username, password, teachers_df)
        if user:
            st.session_state.user = user
            st.rerun()
        st.error("Username หรือ Password ไม่ถูกต้อง")
    return False


def require_login(teachers_df: pd.DataFrame) -> dict | None:
    if "user" not in st.session_state:
        login_panel(teachers_df)
        return None
    return st.session_state.user


def sidebar_user_box(user: dict) -> None:
    with st.sidebar:
        st.markdown("### ผู้ใช้งาน")
        st.write(user.get("name") or user.get("username"))
        if user.get("role"):
            st.caption(f"บทบาท: {user['role']}")
        if st.button("ออกจากระบบ", use_container_width=True):
            st.session_state.pop("user", None)
            st.session_state.pop("temp_records", None)
            st.rerun()
