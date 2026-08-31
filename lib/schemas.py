"""
Pydantic schemas used two ways:
1. As the JSON schema we hand to Gemini (response_format) so extraction comes back
   as structured, typed data instead of free text.
2. As the shape the rest of the app (db.py, app.py) works with.

Every field is Optional because a single daily brain-dump rarely mentions all
four boxes — Gemini should leave a field as null rather than invent a value.
"""

from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


class PrayerEntry(BaseModel):
    prayer_name: Literal["fajr", "dhuhr", "asr", "maghrib", "isha"]
    sunan_done: Optional[bool] = Field(None, description="Sunan/nawafil done before or after this prayer")
    tafakkur_done: Optional[bool] = Field(None, description="Reflection/tafakkur before the prayer")
    wudu_mindful: Optional[bool] = Field(None, description="Wudu performed mindfully")
    khushoo_score: Optional[int] = Field(None, ge=1, le=5, description="Khushoo level during this prayer, 1-5")
    adhkar_after: Optional[bool] = Field(None, description="Adhkar recited after this prayer")
    notes: Optional[str] = None


class SpiritualDaily(BaseModel):
    morning_adhkar_done: Optional[bool] = None
    evening_adhkar_done: Optional[bool] = None
    notes: Optional[str] = None


class HealthEntry(BaseModel):
    gym_went: Optional[bool] = None
    motivation_score: Optional[int] = Field(None, ge=1, le=5)
    fatigue_type: Optional[Literal["real_physical_fatigue", "low_motivation", "time_conflict", "other"]] = Field(
        None,
        description=(
            "If gym/workout was skipped or eating slipped, WHY — read with compassion, not blame. "
            "real_physical_fatigue = body genuinely needed rest (poor sleep, illness, soreness); "
            "low_motivation = a temporary dip in drive, not a character flaw; "
            "time_conflict = a real scheduling collision; other = anything else. Leave null if not skipped."
        ),
    )
    barriers: Optional[str] = Field(None, description="What made today harder, described factually and kindly, not as an excuse to judge")
    triggers: Optional[str] = Field(None, description="What preceded skipping the gym or eating off-plan — context, not a confession")
    healthy_eating: Optional[bool] = None
    sugar_avoided: Optional[bool] = None
    calorie_deficit: Optional[bool] = None
    calories_estimate: Optional[int] = None
    satiety_meal_used: Optional[bool] = Field(None, description="Used a filling/satisfying meal instead of restricting")
    notes: Optional[str] = None


class InnerPeaceEntry(BaseModel):
    escape_flag: Optional[Literal[0, 1]] = Field(
        None,
        description=(
            "1 if the user reached for an escape/coping behavior under pressure today. This is a "
            "data point for understanding a pattern, never a verdict — extract it neutrally."
        ),
    )
    root_cause: Optional[str] = Field(
        None, description="The underlying source of pressure that day (e.g. poor sleep, housing friction, work load) — the thing worth addressing, not the symptom"
    )
    context_tag: Optional[str] = Field(None, description="Short category label for this stressor, for grouping over time")
    stress_level: Optional[int] = Field(None, ge=1, le=5)
    sense_of_control_score: Optional[int] = Field(
        None, ge=1, le=5, description="How much the user felt in control of their own reactions/nerves today, 1-5 — separate from how stressful the day was"
    )
    early_stopping_used: Optional[bool] = Field(None, description="Whether the user caught/interrupted a downward spiral in time — worth naming as a genuine win, however small")
    notes: Optional[str] = None


class GrowthEntry(BaseModel):
    work_tasks_done: Optional[str] = None
    deep_work_hours: Optional[float] = None
    ai_skill_practice: Optional[bool] = Field(None, description="Worked on AI/agents skills, papers, or code today")
    ai_practice_notes: Optional[str] = None
    mental_nutrition: Optional[str] = Field(None, description="Books or podcasts consumed today")
    felt_sustainable: Optional[bool] = Field(
        None, description="Did today's pace feel sustainable, or closer to burnout? A single low day is not failure — it's a signal to rest."
    )
    notes: Optional[str] = None


class DailyExtraction(BaseModel):
    """Top-level shape returned by Gemini for one journal entry (text or transcribed audio)."""
    transcript: Optional[str] = Field(
        None, description="If input was audio, the transcribed text. Otherwise echo the original text."
    )
    entry_date_hint: Optional[str] = Field(
        None, description="Date mentioned in the entry if any, format YYYY-MM-DD, else null"
    )
    prayers: list[PrayerEntry] = Field(default_factory=list)
    spiritual_daily: Optional[SpiritualDaily] = None
    health: Optional[HealthEntry] = None
    inner_peace: Optional[InnerPeaceEntry] = None
    growth: Optional[GrowthEntry] = None
    unrecognized_notes: Optional[str] = Field(
        None, description="Anything meaningful mentioned that didn't fit the four boxes"
    )


# Human-readable labels for the UI (Arabic, matching the project's own terminology)
PRAYER_LABELS = {
    "fajr": "الفجر", "dhuhr": "الظهر", "asr": "العصر", "maghrib": "المغرب", "isha": "العشاء",
}
