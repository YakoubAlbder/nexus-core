"""
Turns raw daily rows into the compact stats_json handed to Gemini for the
Weekly Automated Interviewer. Kept separate from db.py so the "what do we
compute" logic is easy to extend without touching the data-access layer.
"""

from __future__ import annotations
from datetime import date, timedelta

import pandas as pd

from lib import db


def _safe_rate(series: pd.Series) -> float | None:
    if series is None or series.dropna().empty:
        return None
    return round(float(series.dropna().astype(float).mean()), 3)


def _safe_mean(series: pd.Series) -> float | None:
    if series is None or series.dropna().empty:
        return None
    return round(float(pd.to_numeric(series, errors="coerce").dropna().mean()), 2)


def _week_summary(start: date, end: date) -> dict:
    d = db.fetch_all_modules(start, end)
    prayer, spiritual, health, peace, growth = d["prayer"], d["spiritual_daily"], d["health"], d["inner_peace"], d["growth"]

    summary = {
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "spiritual": {
            "avg_khushoo": _safe_mean(prayer.get("khushoo_score")) if not prayer.empty else None,
            "sunan_rate": _safe_rate(prayer.get("sunan_done")) if not prayer.empty else None,
            "morning_adhkar_rate": _safe_rate(spiritual.get("morning_adhkar_done")) if not spiritual.empty else None,
            "evening_adhkar_rate": _safe_rate(spiritual.get("evening_adhkar_done")) if not spiritual.empty else None,
        },
        "health": {
            "gym_rate": _safe_rate(health.get("gym_went")) if not health.empty else None,
            "avg_energy_motivation": _safe_mean(health.get("motivation_score")) if not health.empty else None,
            "sugar_avoided_rate": _safe_rate(health.get("sugar_avoided")) if not health.empty else None,
            "deficit_rate": _safe_rate(health.get("calorie_deficit")) if not health.empty else None,
            # WHY days were skipped, not just that they were — this is what makes the
            # weekly narrative "you needed rest" instead of "you failed to go".
            "fatigue_type_breakdown": (
                {k: int(v) for k, v in health["fatigue_type"].dropna().value_counts().items()}
                if not health.empty and "fatigue_type" in health else {}
            ),
            "context_notes": health["barriers"].dropna().tolist() if not health.empty and "barriers" in health else [],
        },
        "inner_peace": {
            "escape_days": int(peace["escape_flag"].fillna(0).sum()) if not peace.empty else 0,
            "avg_stress": _safe_mean(peace.get("stress_level")) if not peace.empty else None,
            "avg_sense_of_control": _safe_mean(peace.get("sense_of_control_score")) if not peace.empty else None,
            "early_stopping_wins": int(peace["early_stopping_used"].fillna(False).sum()) if not peace.empty and "early_stopping_used" in peace else 0,
            "root_causes": peace["root_cause"].dropna().tolist() if not peace.empty and "root_cause" in peace else [],
            "context_tags": peace["context_tag"].dropna().tolist() if not peace.empty and "context_tag" in peace else [],
        },
        "growth": {
            "total_deep_work_hours": round(float(pd.to_numeric(growth["deep_work_hours"], errors="coerce").fillna(0).sum()), 1) if not growth.empty else 0,
            "ai_practice_rate": _safe_rate(growth.get("ai_skill_practice")) if not growth.empty else None,
            "felt_sustainable_rate": _safe_rate(growth.get("felt_sustainable")) if not growth.empty else None,
        },
    }

    # A couple of headline correlations, if there's enough overlap this week.
    merged = (
        health[["entry_date", "motivation_score", "gym_went"]] if not health.empty else pd.DataFrame(columns=["entry_date"])
    )
    if not peace.empty:
        merged = merged.merge(peace[["entry_date", "stress_level", "escape_flag", "sense_of_control_score"]], on="entry_date", how="outer")
    if not growth.empty:
        merged = merged.merge(growth[["entry_date", "deep_work_hours"]], on="entry_date", how="outer")

    correlations = {}
    if len(merged) >= 4:
        numeric = merged.drop(columns=["entry_date"]).apply(pd.to_numeric, errors="coerce")
        corr = numeric.corr(numeric_only=True)
        for a in corr.columns:
            for b in corr.columns:
                if a < b and pd.notna(corr.loc[a, b]) and abs(corr.loc[a, b]) >= 0.4:
                    correlations[f"{a} vs {b}"] = round(float(corr.loc[a, b]), 2)
    summary["notable_correlations"] = correlations
    return summary


def compute_weekly_stats(week_start: date, week_end: date) -> dict:
    current = _week_summary(week_start, week_end)
    prev_start = week_start - timedelta(days=7)
    prev_end = week_end - timedelta(days=7)
    previous = _week_summary(prev_start, prev_end)
    return {"current_week": current, "previous_week": previous}
