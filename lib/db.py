"""
Data-access layer over Supabase. Every write here is a plain upsert keyed on
entry_date (one row per day per table, except prayer_log which is keyed on
(entry_date, prayer_name)) so re-processing the same day's entry never creates
duplicates — it just overwrites with the latest extraction.

Requires .streamlit/secrets.toml to have a [connections.supabase] section
(see .streamlit/secrets.toml.example) and schema.sql to have been run once
in the Supabase SQL editor.
"""

from __future__ import annotations
import json
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import streamlit as st
from st_supabase_connection import SupabaseConnection

from lib.schemas import DailyExtraction


def get_conn() -> SupabaseConnection:
    return st.connection("supabase", type=SupabaseConnection, ttl=None)


def _clean(d: dict) -> dict:
    """Drop None values so an upsert doesn't null out columns another partial
    save already filled in for the same day."""
    return {k: v for k, v in d.items() if v is not None}


# ---------------------------------------------------------------------------
# Writes — one function per table, all called from save_daily_extraction()
# ---------------------------------------------------------------------------

def save_raw_entry(conn: SupabaseConnection, entry_date: date, source: str,
                    raw_text: Optional[str], extracted: DailyExtraction) -> None:
    conn.table("raw_entries").insert({
        "entry_date": entry_date.isoformat(),
        "source": source,
        "raw_text": raw_text,
        "extracted_json": json.loads(extracted.model_dump_json()),
    }).execute()


def upsert_prayers(conn: SupabaseConnection, entry_date: date, extracted: DailyExtraction) -> None:
    for p in extracted.prayers:
        row = _clean(p.model_dump())
        row["entry_date"] = entry_date.isoformat()
        conn.table("prayer_log").upsert(row, on_conflict="entry_date,prayer_name").execute()


def upsert_spiritual_daily(conn: SupabaseConnection, entry_date: date, extracted: DailyExtraction) -> None:
    if not extracted.spiritual_daily:
        return
    row = _clean(extracted.spiritual_daily.model_dump())
    if not row:
        return
    row["entry_date"] = entry_date.isoformat()
    conn.table("spiritual_daily_log").upsert(row, on_conflict="entry_date").execute()


def upsert_health(conn: SupabaseConnection, entry_date: date, extracted: DailyExtraction) -> None:
    if not extracted.health:
        return
    row = _clean(extracted.health.model_dump())
    if not row:
        return
    row["entry_date"] = entry_date.isoformat()
    conn.table("health_log").upsert(row, on_conflict="entry_date").execute()


def upsert_inner_peace(conn: SupabaseConnection, entry_date: date, extracted: DailyExtraction) -> None:
    if not extracted.inner_peace:
        return
    row = _clean(extracted.inner_peace.model_dump())
    if not row:
        return
    row["entry_date"] = entry_date.isoformat()
    conn.table("inner_peace_log").upsert(row, on_conflict="entry_date").execute()


def upsert_growth(conn: SupabaseConnection, entry_date: date, extracted: DailyExtraction) -> None:
    if not extracted.growth:
        return
    row = _clean(extracted.growth.model_dump())
    if not row:
        return
    row["entry_date"] = entry_date.isoformat()
    conn.table("growth_log").upsert(row, on_conflict="entry_date").execute()


def save_daily_extraction(entry_date: date, source: str, raw_text: Optional[str],
                           extracted: DailyExtraction) -> None:
    """Single entry point called from the daily-entry page after the user confirms
    (and possibly edits) what Gemini extracted."""
    conn = get_conn()
    save_raw_entry(conn, entry_date, source, raw_text, extracted)
    upsert_prayers(conn, entry_date, extracted)
    upsert_spiritual_daily(conn, entry_date, extracted)
    upsert_health(conn, entry_date, extracted)
    upsert_inner_peace(conn, entry_date, extracted)
    upsert_growth(conn, entry_date, extracted)


# ---------------------------------------------------------------------------
# Reads — used by the dashboard and the weekly review
# ---------------------------------------------------------------------------

def fetch_range(table: str, start: date, end: date, ttl: str = "5m") -> pd.DataFrame:
    conn = get_conn()
    res = (
        conn.table(table)
        .select("*")
        .gte("entry_date", start.isoformat())
        .lte("entry_date", end.isoformat())
        .order("entry_date")
        .execute()
    )
    return pd.DataFrame(res.data)


def fetch_all_modules(start: date, end: date) -> dict[str, pd.DataFrame]:
    return {
        "prayer": fetch_range("prayer_log", start, end),
        "spiritual_daily": fetch_range("spiritual_daily_log", start, end),
        "health": fetch_range("health_log", start, end),
        "inner_peace": fetch_range("inner_peace_log", start, end),
        "growth": fetch_range("growth_log", start, end),
    }


def save_weekly_report(week_start: date, week_end: date, stats_json: dict,
                        report_text: str) -> int:
    conn = get_conn()
    res = conn.table("weekly_reports").upsert({
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "stats_json": stats_json,
        "report_text": report_text,
        "conversation": [{"role": "assistant", "content": report_text}],
    }, on_conflict="week_start,week_end").execute()
    return res.data[0]["id"]


def append_weekly_conversation(report_id: int, conversation: list[dict]) -> None:
    conn = get_conn()
    conn.table("weekly_reports").update({"conversation": conversation}).eq("id", report_id).execute()


def save_weekly_hypothesis(report_id: int, hypothesis: str) -> None:
    conn = get_conn()
    conn.table("weekly_reports").update({"hypothesis": hypothesis}).eq("id", report_id).execute()


def get_latest_weekly_report() -> Optional[dict]:
    conn = get_conn()
    res = conn.table("weekly_reports").select("*").order("week_start", desc=True).limit(1).execute()
    return res.data[0] if res.data else None


def this_week_bounds(today: Optional[date] = None) -> tuple[date, date]:
    """Monday-Sunday week containing `today`."""
    today = today or date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end
