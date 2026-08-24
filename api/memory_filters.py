"""Shared query normalization for extensible memory-wall filters."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException


@dataclass(frozen=True)
class MemoryFilterBounds:
    created_after: str | None = None
    created_before: str | None = None


def normalize_memory_date_range(
    date_from: date | None,
    date_to: date | None,
) -> MemoryFilterBounds:
    """Convert an inclusive local date range into SQLite text bounds."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be earlier than or equal to date_to",
        )

    created_after = (
        datetime.combine(date_from, time.min).strftime("%Y-%m-%d %H:%M:%S")
        if date_from
        else None
    )
    created_before = (
        datetime.combine(date_to + timedelta(days=1), time.min).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        if date_to
        else None
    )
    return MemoryFilterBounds(created_after, created_before)
