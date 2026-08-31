"""
Thin wrapper around the Gemini API (google-genai SDK, Interactions API) for the two
AI-driven features of Nexus Core:

  1. extract_from_text / extract_from_audio  -> structured DailyExtraction JSON
  2. start_weekly_review / continue_weekly_review -> the "Weekly Automated Interviewer"

NOTE ON THE MODEL/SDK: Google's Gemini API surface moves fast. This file targets the
Interactions API (client.interactions.create) with the google-genai SDK, current as of
mid-2026. If Google has since renamed things again, the fix is almost always local to
this file — check https://ai.google.dev/gemini-api/docs for the current method name and
swap it in _run_interaction() below; nothing else in the app needs to change.

FREE TIER: Google's free tier applies per-model and the exact list/limits shift over
time — check https://ai.google.dev/gemini-api/docs/pricing before deploying and pick a
"-flash" or "-flash-lite" model that's currently listed as free. Set it via the
GEMINI_MODEL secret/env var so you can swap models without touching code. Free-tier
traffic may be used by Google to improve their models — don't put anything you consider
sensitive (this is a personal habit journal, so decide for yourself if that's fine).
"""

from __future__ import annotations
import base64
import json
import os
from typing import Optional

import streamlit as st
from google import genai

from lib.schemas import DailyExtraction

DEFAULT_MODEL = "gemini-3.5-flash"  # verify this is still free at ai.google.dev/gemini-api/docs/pricing


def _get_client() -> genai.Client:
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in secrets.toml or the environment.")
    return genai.Client(api_key=api_key)


def _get_model() -> str:
    return st.secrets.get("GEMINI_MODEL", os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))


def _run_interaction(input_payload, response_schema: Optional[dict] = None,
                      system_instruction: Optional[str] = None,
                      previous_interaction_id: Optional[str] = None):
    client = _get_client()
    kwargs = {"model": _get_model(), "input": input_payload}
    if system_instruction:
        kwargs["system_instruction"] = system_instruction
    if response_schema:
        kwargs["response_format"] = {
            "type": "text",
            "mime_type": "application/json",
            "schema": response_schema,
        }
    if previous_interaction_id:
        kwargs["previous_interaction_id"] = previous_interaction_id
    return client.interactions.create(**kwargs)


# ---------------------------------------------------------------------------
# 1. Information extraction
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """\
أنت مساعد استخراج بيانات (Information Extraction) لتطبيق يومي شخصي. ستستقبل يومية
مكتوبة أو مفرغة من صوت، غالباً بالعامية، عن يوم المستخدم — وهي غالباً فضفضة صادقة
في لحظة تعب أو راحة. مهمتك الوحيدة هي تحويلها إلى بيانات منظمة JSON حسب الـ schema
المعطى، بدون أي تعليق أو نص إضافي خارج الحقول.

قواعد مهمة:
- لا تخترع بيانات غير مذكورة. أي تفصيلة غير مذكورة تُترك null.
- افهم العامية المصرية/الخليجية/الشامية بمرونة (مثلاً "مروحتش الجيم" = gym_went: false).
- إذا ذكر المستخدم صلاة واحدة أو أكثر بالاسم اذكرها في prayers، وإلا اترك القائمة فاضية.
- خشوع/تركيز أثناء الصلاة يُقاس من 1 إلى 5 فقط لو ذُكر رقم أو وصف يمكن ترجمته لرقم تقريبي.
- إن ذكر المستخدم "هربت" أو "انتكست" أو سلوك هروبي فعّل escape_flag = 1، وإلا 0 فقط لو
  تكلم صراحة عن سلامه الداخلي اليوم، وإلا اتركه null. هذا رقم لفهم نمط، مش حكم عليه.
- أنت لا تحاسب ولا تحكم على المستخدم أبداً أثناء الاستخراج — أنت فقط تسمع وتصنّف بحياد
  ولطف. لو قال "كنت تعبان ومقدرتش أروح الجيم عشان نمت بدري وسهرت شغل"، الطاقة كانت
  منخفضة والسبب تعب حقيقي (fatigue_type: real_physical_fatigue) — ده وصف واقع، مش
  تقصير. لو السبب كان تسويف أو مزاج بس، سجّله كـ low_motivation بنفس الحياد، بدون
  أي صياغة تلوم المستخدم في أي حقل نصي (barriers/triggers/notes) — اكتبها كوصف
  للموقف كما رواه، لا كتقييم لشخصيته.
"""


def extract_from_text(raw_text: str) -> DailyExtraction:
    result = _run_interaction(
        input_payload=raw_text,
        response_schema=DailyExtraction.model_json_schema(),
        system_instruction=EXTRACTION_SYSTEM_PROMPT,
    )
    data = json.loads(result.output_text)
    return DailyExtraction.model_validate(data)


def extract_from_audio(audio_bytes: bytes, mime_type: str = "audio/wav") -> DailyExtraction:
    """audio_bytes typically comes straight from st.audio_input(...).getvalue()."""
    input_payload = [
        {"type": "text", "text": "استخرج بيانات اليومية من التسجيل الصوتي المرفق، وضع النص المفرغ في transcript."},
        {
            "type": "audio",
            "data": base64.b64encode(audio_bytes).decode("utf-8"),
            "mime_type": mime_type,
        },
    ]
    result = _run_interaction(
        input_payload=input_payload,
        response_schema=DailyExtraction.model_json_schema(),
        system_instruction=EXTRACTION_SYSTEM_PROMPT,
    )
    data = json.loads(result.output_text)
    return DailyExtraction.model_validate(data)


# ---------------------------------------------------------------------------
# 2. Weekly Automated Interviewer
# ---------------------------------------------------------------------------

WEEKLY_SYSTEM_PROMPT = """\
أنت مستشار شخصي حكيم ومحلل بيانات متعاطف (Compassionate Data Analyst) للمستخدم —
مش قاضياً ومش مديراً بيراجع Performance. دورك الأسبوعي إنك تاخد بياناته في 4 مجالات
(الروحي، الصحي، السلام الداخلي، التطوير المهني) وتترجمها له لقصة مفهومة ومريحة،
مبنية على الأرقام لكن مقروءة بعين إنسانية.

المبدأ الأساسي: الإنسان مش آلة. التقدم مش خطي — فيه أيام هبوط وأيام صعود، وده طبيعي.
لو انخفض أداء في مجال معين، مهمتك إنك تربطه بسببه الجذري الحقيقي (قلة نوم، ضغط سكن،
إرهاق ذهني...) قبل ما تفترض إنه "تقصير". يوم ضعيف بسبب نوم سيء مش فشل، ده جسم كان
محتاج صيانة.

مطلوب منك في رسالة الافتتاح:
1. افتتح بجملة ترحيبية دافئة وقصيرة، بعدها لخّص أهم نمط أو Root Cause واحد أو اثنين
   لاحظته الأسبوع ده (قارن بالأسبوع اللي قبله لو البيانات متاحة)، واربطه بسببه المرجّح
   بلغة تفهّم لا تفهيم — "لاحظت إن X حصل، وده غالباً مرتبط بـ Y" مش "أنت فشلت في X".
2. لو فيه Correlation لافتة (زي علاقة بين قلة النوم/الضغط وانخفاض الحماس)، اشرحها
   كأداة لفهم النفس، مش كدليل إدانة.
3. لازم تذكر حاجة إيجابية حقيقية حصلت الأسبوع ده (التزام في مجال، أو لحظة "توقف بدري"
   عن انزلاق) — التقدير الصادق جزء أساسي من التحليل مش مجاملة فارغة.
4. اختم بسؤال واحد مفتوح ودافئ يدعو المستخدم يفكر معاك في تجربة بسيطة للأسبوع الجاي —
   مش "اكتب لي Hypothesis قابلة للقياس" بجفاف، لكن بروح "تحب نجرب إيه الأسبوع ده عشان
   نريّح النقطة دي؟" — وانتظر رده.
5. في الردود التالية: ساعده يوضّح فكرته ويحولها لخطوة عملية بسيطة يقدر يقيسها بنفسه
   لو حب، لكن من غير ضغط أو إلزام — الهدف راحته وفهمه لنفسه، مش إنجاز مؤشر. لما توصلوا
   لصيغة واضحة، أكّد عليها بوضوح ودفء حتى يسهل حفظها.
6. ممنوع منعاً باتاً أي لغة تحاسب أو تلوم أو تقارن المستخدم بمعيار "مثالي" — لو خانة
   escape_flag أو تراجع في مؤشر ظهرت، تعامل معاها كإشارة تستحق الفهم، لا كخطأ يستحق
   التوبيخ.
"""


def start_weekly_review(stats_json: dict) -> tuple[str, str]:
    """Returns (opening_message, interaction_id) — store interaction_id in session_state
    and pass it back into continue_weekly_review() for follow-up turns."""
    result = _run_interaction(
        input_payload=f"بيانات هذا الأسبوع:\n{json.dumps(stats_json, ensure_ascii=False, indent=2)}",
        system_instruction=WEEKLY_SYSTEM_PROMPT,
    )
    return result.output_text, result.id


def continue_weekly_review(user_message: str, previous_interaction_id: Optional[str],
                            conversation_history: Optional[list[dict]] = None) -> tuple[str, str]:
    """If previous_interaction_id is available (same Streamlit session, thread still
    live server-side) it's used to continue the server-side thread cheaply. If it's
    missing — e.g. the user came back on a new day/session and we only have what we
    stored in Supabase — fall back to replaying conversation_history as plain text so
    Gemini still has context, at the cost of resending it each turn."""
    if previous_interaction_id:
        result = _run_interaction(
            input_payload=user_message,
            system_instruction=WEEKLY_SYSTEM_PROMPT,
            previous_interaction_id=previous_interaction_id,
        )
    else:
        history_text = ""
        if conversation_history:
            lines = [f"{m['role']}: {m['content']}" for m in conversation_history]
            history_text = "سياق المحادثة حتى الآن:\n" + "\n".join(lines) + "\n\n"
        result = _run_interaction(
            input_payload=history_text + f"user: {user_message}",
            system_instruction=WEEKLY_SYSTEM_PROMPT,
        )
    return result.output_text, result.id
