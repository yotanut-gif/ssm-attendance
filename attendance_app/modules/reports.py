from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from modules import attendance


ALL_OPTION = "ทั้งหมด"


def date_list(start_date: str, end_date: str) -> list[str]:
    start = date.fromisoformat(str(start_date))
    end = date.fromisoformat(str(end_date))
    days = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def filter_attendance(
    df: pd.DataFrame,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    level: str | None = None,
    classroom: str | None = None,
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
    if classroom and classroom != ALL_OPTION:
        filtered = filtered[filtered["classroom"].astype(str) == classroom]

    return filtered.drop(columns=["date_parsed"], errors="ignore").reset_index(drop=True)


def filter_submit_log(
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
    level: str | None = None,
    classroom: str | None = None,
) -> pd.DataFrame:
    filtered = df.copy()
    if filtered.empty:
        return filtered
    filtered["date_parsed"] = pd.to_datetime(filtered["date"], errors="coerce").dt.date
    start = date.fromisoformat(str(start_date))
    end = date.fromisoformat(str(end_date))
    filtered = filtered[(filtered["date_parsed"] >= start) & (filtered["date_parsed"] <= end)]
    if level and level != ALL_OPTION:
        filtered = filtered[filtered["level"].astype(str) == level]
    if classroom and classroom != ALL_OPTION:
        filtered = filtered[filtered["classroom"].astype(str) == classroom]
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


def summary_by_level(df: pd.DataFrame, levels: list[str]) -> pd.DataFrame:
    summary = count_summary(df, "level", "จำนวนรายการขาด/ลา/มาสาย")
    return (
        pd.DataFrame({"level": levels})
        .merge(summary, on="level", how="left")
        .fillna({"จำนวนรายการขาด/ลา/มาสาย": 0})
    )


def summary_by_classroom(df: pd.DataFrame, classrooms: list[str]) -> pd.DataFrame:
    summary = count_summary(df, "classroom", "จำนวนรายการ")
    return (
        pd.DataFrame({"classroom": classrooms})
        .merge(summary, on="classroom", how="left")
        .fillna({"จำนวนรายการ": 0})
    )


def summary_by_classroom_status(df: pd.DataFrame, classrooms: list[str]) -> pd.DataFrame:
    base = pd.MultiIndex.from_product(
        [classrooms, attendance.STATUSES], names=["classroom", "status"]
    ).to_frame(index=False)
    if df.empty:
        base["จำนวนรายการ"] = 0
        return base
    summary = df.groupby(["classroom", "status"]).size().reset_index(name="จำนวนรายการ")
    return base.merge(summary, on=["classroom", "status"], how="left").fillna({"จำนวนรายการ": 0})


def submission_status(
    students_df: pd.DataFrame,
    submit_df: pd.DataFrame,
    start_date: str,
    end_date: str,
    level: str | None = None,
    classroom: str | None = None,
) -> pd.DataFrame:
    by_level = attendance.classrooms_by_level(students_df)
    rows = []
    for report_date in date_list(start_date, end_date):
        for level_name, classrooms in by_level.items():
            if level and level != ALL_OPTION and level_name != level:
                continue
            for room in classrooms:
                if classroom and classroom != ALL_OPTION and room != classroom:
                    continue
                rows.append({"date": report_date, "level": level_name, "classroom": room})
    expected = pd.DataFrame(rows)
    if expected.empty:
        return pd.DataFrame(columns=["date", "level", "classroom", "สถานะส่ง"])

    submitted = filter_submit_log(submit_df, start_date, end_date, level, classroom)
    submitted_keys = set(zip(submitted["date"].astype(str), submitted["classroom"].astype(str)))
    expected["สถานะส่ง"] = expected.apply(
        lambda row: "ส่งแล้ว" if (row["date"], row["classroom"]) in submitted_keys else "ยังไม่ส่ง",
        axis=1,
    )
    return expected


def levels_for_print(selected_level: str, levels: list[str]) -> list[str]:
    if selected_level == ALL_OPTION:
        return levels
    return [selected_level]


def date_range_label(start_date: str, end_date: str) -> str:
    if start_date == end_date:
        return start_date
    return f"{start_date} ถึง {end_date}"
