from __future__ import annotations

import pandas as pd
import plotly.express as px

from modules import reports


def _empty_figure(title: str):
    fig = px.bar(pd.DataFrame({"รายการ": [], "จำนวน": []}), x="รายการ", y="จำนวน")
    fig.update_layout(title=title)
    return fig


def bar_by_level(df: pd.DataFrame, levels: list[str]):
    summary = reports.summary_by_level(df, levels)
    fig = px.bar(
        summary,
        x="level",
        y="จำนวนรายการขาด/ลา/มาสาย",
        text="จำนวนรายการขาด/ลา/มาสาย",
        title="จำนวนรายการขาด/ลา/มาสาย ตามระดับชั้น",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(yaxis_title="จำนวนรายการ", xaxis_title="ระดับชั้น")
    return fig


def bar_by_classroom(df: pd.DataFrame, classrooms: list[str]):
    summary = reports.summary_by_classroom(df, classrooms)
    fig = px.bar(
        summary,
        x="classroom",
        y="จำนวนรายการ",
        text="จำนวนรายการ",
        title="จำนวนรายการขาด/ลา/มาสาย ตามห้องเรียน",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(yaxis_title="จำนวนรายการ", xaxis_title="ห้องเรียน")
    return fig


def bar_by_classroom_status(df: pd.DataFrame, classrooms: list[str]):
    summary = reports.summary_by_classroom_status(df, classrooms)
    fig = px.bar(
        summary,
        x="classroom",
        y="จำนวนรายการ",
        color="status",
        barmode="group",
        text="จำนวนรายการ",
        title="แยกสถานะขาด/ลา/มาสาย ตามห้องเรียน",
    )
    fig.update_layout(
        yaxis_title="จำนวนรายการ",
        xaxis_title="ห้องเรียน",
        legend_title="สถานะ",
        xaxis_tickangle=-45,
    )
    return fig


def submission_bar(status_df: pd.DataFrame):
    if status_df.empty:
        return _empty_figure("ห้องที่ยังไม่ส่ง")
    missing_df = status_df[status_df["สถานะส่ง"].astype(str) == "ยังไม่ส่ง"]
    if missing_df.empty:
        return _empty_figure("ห้องที่ยังไม่ส่ง")
    summary = missing_df.groupby("สถานะส่ง").size().reset_index(name="จำนวนห้อง/วัน")
    fig = px.bar(
        summary,
        x="สถานะส่ง",
        y="จำนวนห้อง/วัน",
        color="สถานะส่ง",
        text="จำนวนห้อง/วัน",
        title="ห้องที่ยังไม่ส่ง",
    )
    fig.update_traces(textposition="outside")
    return fig
