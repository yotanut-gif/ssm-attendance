from __future__ import annotations

import pandas as pd

from attendance import CLASSROOMS_BY_LEVEL


def filter_attendance(
    df: pd.DataFrame,
    date: str | None = None,
    day: str | None = None,
    level: str | None = None,
    classroom: str | None = None,
) -> pd.DataFrame:
    filtered = df.copy()
    if date:
        filtered = filtered[filtered["date"].astype(str) == str(date)]
    if day and day != "ทั้งหมด":
        filtered = filtered[filtered["day"].astype(str) == day]
    if level and level != "ทั้งหมด":
        filtered = filtered[filtered["level"].astype(str) == level]
    if classroom and classroom != "ทั้งหมด":
        filtered = filtered[filtered["classroom"].astype(str) == classroom]
    return filtered.reset_index(drop=True)


def explode_periods(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    rows = []
    for _, row in df.iterrows():
        periods = [p.strip() for p in str(row.get("periods", "")).split(",") if p.strip()]
        for period in periods:
            new_row = row.to_dict()
            new_row["period"] = period
            rows.append(new_row)
    return pd.DataFrame(rows)


def count_summary(df: pd.DataFrame, column: str, label: str = "จำนวนรายการ") -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=[column, label])
    return (
        df.groupby(column, dropna=False)
        .size()
        .reset_index(name=label)
        .sort_values(label, ascending=False)
    )


def all_classrooms() -> list[str]:
    classes: list[str] = []
    for classrooms in CLASSROOMS_BY_LEVEL.values():
        classes.extend(classrooms)
    return classes


def daily_whole_school_summary(filtered_df: pd.DataFrame) -> pd.DataFrame:
    if filtered_df.empty:
        return pd.DataFrame(
            [{"นักเรียนที่มีรายการ": 0, "จำนวนรายการ": 0, "จำนวนคาบรวม": 0}]
        )
    exploded = explode_periods(filtered_df)
    return pd.DataFrame(
        [
            {
                "นักเรียนที่มีรายการ": filtered_df["student_id"].nunique(),
                "จำนวนรายการ": len(filtered_df),
                "จำนวนคาบรวม": len(exploded),
            }
        ]
    )


def missing_submissions(
    submit_df: pd.DataFrame,
    date: str,
    day: str | None = None,
    level: str | None = None,
    classroom: str | None = None,
) -> pd.DataFrame:
    expected = pd.DataFrame({"classroom": all_classrooms()})
    expected["level"] = expected["classroom"].str.extract(r"(ม\.\d)")

    if level and level != "ทั้งหมด":
        expected = expected[expected["level"] == level]
    if classroom and classroom != "ทั้งหมด":
        expected = expected[expected["classroom"] == classroom]

    submitted = submit_df[submit_df["date"].astype(str) == str(date)].copy()
    if day and day != "ทั้งหมด":
        submitted = submitted[submitted["day"].astype(str) == day]

    submitted_keys = set(submitted["classroom"].astype(str))
    missing = expected[~expected["classroom"].isin(submitted_keys)].copy()
    missing["teacher_name"] = ""
    missing["สถานะ"] = "ยังไม่ส่ง"
    return missing[["level", "classroom", "teacher_name", "สถานะ"]].reset_index(drop=True)
