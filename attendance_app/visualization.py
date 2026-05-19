from __future__ import annotations

import pandas as pd
import plotly.express as px

from modules.reports import count_summary, explode_periods


def _empty_figure(title: str):
    fig = px.bar(pd.DataFrame({"รายการ": [], "จำนวน": []}), x="รายการ", y="จำนวน")
    fig.update_layout(title=title)
    return fig


def bar_by_level(df: pd.DataFrame):
    summary = count_summary(df, "level")
    if summary.empty:
        return _empty_figure("จำนวนรายการตามระดับชั้น")
    return px.bar(summary, x="level", y="จำนวนรายการ", title="จำนวนรายการตามระดับชั้น")


def bar_by_classroom(df: pd.DataFrame):
    summary = count_summary(df, "classroom")
    if summary.empty:
        return _empty_figure("จำนวนรายการตามห้องเรียน")
    return px.bar(summary, x="classroom", y="จำนวนรายการ", title="จำนวนรายการตามห้องเรียน")


def bar_by_period(df: pd.DataFrame):
    exploded = explode_periods(df)
    summary = count_summary(exploded, "period")
    if summary.empty:
        return _empty_figure("จำนวนรายการตามคาบเรียน")
    summary["period"] = pd.Categorical(
        summary["period"], categories=[str(i) for i in range(1, 9)], ordered=True
    )
    summary = summary.sort_values("period")
    return px.bar(summary, x="period", y="จำนวนรายการ", title="จำนวนรายการตามคาบเรียน")


def donut_by_status(df: pd.DataFrame):
    summary = count_summary(df, "status")
    if summary.empty:
        return _empty_figure("สัดส่วนตามสถานะ")
    fig = px.pie(summary, names="status", values="จำนวนรายการ", hole=0.45, title="สัดส่วนตามสถานะ")
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig
