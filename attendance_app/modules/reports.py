from __future__ import annotations

from datetime import date

import pandas as pd

from modules.attendance import CLASSROOMS_BY_LEVEL, LEVELS


ALL_OPTION = "ทั้งหมด"


def filter_attendance(
    df: pd.DataFrame,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    level: str | None = None,
) -> pd.DataFrame:
    filtered = df.copy()
    if filtered.empty:
        return filtered

    filtered["date_parsed"] = pd.to_datetime(filtered["date"], errors="coerce").dt.date
    if start_date:
        start = date.fromisoformat(str(start_date))
        filtered = filtered[filtered["date_parsed"] >= start]
    if end_date:
        end = date.fromisoformat(str(end_date))
        filtered = filtered[filtered["date_parsed"] <= end]
    if level and level != ALL_OPTION:
        filtered = filtered[filtered["level"].astype(str) == level]

    return filtered.drop(columns=["date_parsed"], errors="ignore").reset_index(drop=True)


def count_summary(df: pd.DataFrame, column: str, label: str = "จำนวนรายการ") -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=[column, label])
    return (
        df.groupby(column, dropna=False)
        .size()
        .reset_index(name=label)
        .sort_values(label, ascending=False)
    )


def summary_by_level(df: pd.DataFrame) -> pd.DataFrame:
    summary = count_summary(df, "level", "จำนวนรายการขาด/ลา/มาสาย")
    if summary.empty:
        return pd.DataFrame({"level": LEVELS, "จำนวนรายการขาด/ลา/มาสาย": [0] * len(LEVELS)})
    return (
        pd.DataFrame({"level": LEVELS})
        .merge(summary, on="level", how="left")
        .fillna({"จำนวนรายการขาด/ลา/มาสาย": 0})
    )


def summary_by_classroom(df: pd.DataFrame, level: str) -> pd.DataFrame:
    classrooms = CLASSROOMS_BY_LEVEL[level]
    summary = count_summary(df[df["level"].astype(str) == level], "classroom", "จำนวนรายการ")
    return (
        pd.DataFrame({"classroom": classrooms})
        .merge(summary, on="classroom", how="left")
        .fillna({"จำนวนรายการ": 0})
    )


def levels_for_print(selected_level: str) -> list[str]:
    if selected_level == ALL_OPTION:
        return LEVELS
    return [selected_level]


def date_range_label(start_date: str, end_date: str) -> str:
    if start_date == end_date:
        return start_date
    return f"{start_date} ถึง {end_date}"
