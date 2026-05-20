from __future__ import annotations

import pandas as pd
import plotly.express as px

from modules.reports import count_summary, summary_by_classroom, summary_by_level


def _empty_figure(title: str):
    fig = px.bar(pd.DataFrame({"รายการ": [], "จำนวน": []}), x="รายการ", y="จำนวน")
    fig.update_layout(title=title)
    return fig


def bar_by_level(df: pd.DataFrame):
    summary = summary_by_level(df)
    if summary.empty:
        return _empty_figure("จำนวนรายการตามระดับชั้น")
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


def bar_by_classroom(df: pd.DataFrame, level: str | None = None):
    if level and level != "ทั้งหมด":
        summary = summary_by_classroom(df, level)
    else:
        summary = count_summary(df, "classroom")
    if summary.empty:
        return _empty_figure("จำนวนรายการตามห้องเรียน")
    y_column = "จำนวนรายการ"
    fig = px.bar(
        summary,
        x="classroom",
        y=y_column,
        text=y_column,
        title="จำนวนรายการขาด/ลา/มาสาย ตามห้องเรียน",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(yaxis_title="จำนวนรายการ", xaxis_title="ห้องเรียน")
    return fig
