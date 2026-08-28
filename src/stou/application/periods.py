"""Períodos de tiempo para métricas.

Los límites se calculan sobre días locales y se convierten a UTC, que es cómo se
guarda todo. Un día del dashboard es el día que el usuario vivió, no el día UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta


@dataclass(frozen=True, slots=True)
class Period:
    start: datetime  # inclusivo, UTC
    end: datetime  # exclusivo, UTC
    label: str

    def days(self) -> list[date]:
        out: list[date] = []
        cursor = to_local_date(self.start)
        last = to_local_date(self.end - timedelta(microseconds=1))
        while cursor <= last:
            out.append(cursor)
            cursor += timedelta(days=1)
        return out


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(day, time.min).astimezone()
    end_local = datetime.combine(day + timedelta(days=1), time.min).astimezone()
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def to_local_date(moment: datetime) -> date:
    return moment.astimezone().date()


def today(reference: datetime) -> Period:
    day = to_local_date(reference)
    start, end = local_day_bounds(day)
    return Period(start=start, end=end, label="Hoy")


def current_week(reference: datetime) -> Period:
    day = to_local_date(reference)
    monday = day - timedelta(days=day.weekday())
    start, _ = local_day_bounds(monday)
    _, end = local_day_bounds(monday + timedelta(days=6))
    return Period(start=start, end=end, label="Esta semana")


def current_month(reference: datetime) -> Period:
    day = to_local_date(reference)
    first = day.replace(day=1)
    next_month = (first + timedelta(days=32)).replace(day=1)
    start, _ = local_day_bounds(first)
    end, _ = local_day_bounds(next_month)
    return Period(start=start, end=end, label="Este mes")


def last_days(reference: datetime, count: int) -> Period:
    day = to_local_date(reference)
    first = day - timedelta(days=count - 1)
    start, _ = local_day_bounds(first)
    _, end = local_day_bounds(day)
    return Period(start=start, end=end, label=f"Últimos {count} días")


def custom(start_day: date, end_day: date) -> Period:
    start, _ = local_day_bounds(start_day)
    _, end = local_day_bounds(end_day)
    label = f"{start_day.isoformat()} a {end_day.isoformat()}"
    return Period(start=start, end=end, label=label)


def month_bounds(year: int, month: int) -> Period:
    first = date(year, month, 1)
    next_first = date(year + (month == 12), (month % 12) + 1, 1)
    start, _ = local_day_bounds(first)
    end, _ = local_day_bounds(next_first)
    return Period(start=start, end=end, label=f"{year}-{month:02d}")
