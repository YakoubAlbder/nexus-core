"""
Nexus Core — daily entry point.
فضفض عن يومك نصاً أو صوتاً → Gemini يستخرج البيانات → تراجع وتعدّل → تُحفظ في Supabase.
"""

from datetime import date

import streamlit as st

from lib.auth import require_login
from lib.gemini_client import extract_from_text, extract_from_audio
from lib.schemas import DailyExtraction, PrayerEntry, PRAYER_LABELS
from lib import db

st.set_page_config(page_title="Nexus Core", page_icon="🧭", layout="centered")
require_login()

st.title("🧭 Nexus Core")
st.caption("فضفض عن يومك زي ما هو، بدون رتوش. مفيش يوم \"صح\" ومفيش يوم \"غلط\" — بس أيام بنفهمها مع بعض.")

entry_date = st.date_input("تاريخ اليومية", value=date.today())

if "draft" not in st.session_state:
    st.session_state.draft = None
if "draft_source" not in st.session_state:
    st.session_state.draft_source = None
if "draft_raw_text" not in st.session_state:
    st.session_state.draft_raw_text = None

st.divider()
st.subheader("1) فضفض")

col_text, col_audio = st.tabs(["✍️ نص", "🎙️ صوت"])

with col_text:
    text_input = st.text_area("اكتب يومك بعاميتك زي ما تحب", height=180, key="text_input")
    if st.button("استخرج من النص", type="primary", disabled=not text_input.strip()):
        with st.spinner("Gemini بيحلل اليومية..."):
            st.session_state.draft = extract_from_text(text_input)
            st.session_state.draft_source = "text"
            st.session_state.draft_raw_text = text_input
        st.rerun()

with col_audio:
    audio_value = st.audio_input("سجّل صوتك")
    if audio_value is not None and st.button("استخرج من الصوت", type="primary"):
        with st.spinner("Gemini بيفرّغ ويحلل التسجيل..."):
            extracted = extract_from_audio(audio_value.getvalue(), mime_type=audio_value.type or "audio/wav")
            st.session_state.draft = extracted
            st.session_state.draft_source = "voice"
            st.session_state.draft_raw_text = extracted.transcript
        st.rerun()

# ---------------------------------------------------------------------------
# Review & edit what Gemini extracted before anything touches the database
# ---------------------------------------------------------------------------
if st.session_state.draft:
    st.divider()
    st.subheader("2) راجع وعدّل")

    if st.session_state.draft_source == "voice" and st.session_state.draft.transcript:
        with st.expander("📝 النص المفرغ من الصوت"):
            st.write(st.session_state.draft.transcript)

    draft: DailyExtraction = st.session_state.draft
    by_name = {p.prayer_name: p for p in draft.prayers}

    with st.form("confirm_form"):
        st.markdown("**🕌 الخشوع والارتباط الروحي**")
        prayer_rows: list[PrayerEntry] = []
        prayer_tabs = st.tabs([PRAYER_LABELS[k] for k in PRAYER_LABELS])
        for (key, label), tab in zip(PRAYER_LABELS.items(), prayer_tabs):
            with tab:
                existing = by_name.get(key)
                mentioned = st.checkbox("اتذكرت اليوم؟", value=existing is not None, key=f"m_{key}")
                if mentioned:
                    sunan = st.checkbox("السنن اتصلت", value=(existing.sunan_done if existing else False), key=f"s_{key}")
                    tafakkur = st.checkbox("تفكر قبل الصلاة", value=(existing.tafakkur_done if existing else False), key=f"t_{key}")
                    wudu = st.checkbox("وضوء بخشوع", value=(existing.wudu_mindful if existing else False), key=f"w_{key}")
                    khushoo = st.slider("مستوى الخشوع", 1, 5, value=(existing.khushoo_score if existing and existing.khushoo_score else 3), key=f"k_{key}")
                    adhkar = st.checkbox("أذكار بعد الصلاة", value=(existing.adhkar_after if existing else False), key=f"a_{key}")
                    prayer_rows.append(PrayerEntry(
                        prayer_name=key, sunan_done=sunan, tafakkur_done=tafakkur,
                        wudu_mindful=wudu, khushoo_score=khushoo, adhkar_after=adhkar,
                    ))

        sd = draft.spiritual_daily
        morning_adhkar = st.checkbox("أذكار الصباح", value=(sd.morning_adhkar_done if sd else False))
        evening_adhkar = st.checkbox("أذكار المساء", value=(sd.evening_adhkar_done if sd else False))

        st.markdown("**💪 الصحة البدنية والأكل**")
        st.caption("مفيش حرمان ومفيش لوم — بس فهم إيه اللي كان متاح للجسم النهاردة.")
        h = draft.health
        gym_went = st.checkbox("رحت الجيم", value=(h.gym_went if h else False))
        motivation = st.slider("مستوى الطاقة/الحماس", 1, 5, value=(h.motivation_score if h and h.motivation_score else 3))
        fatigue_options = {
            None: "— (متعملتش/الحماس عادي)", "real_physical_fatigue": "تعب جسدي حقيقي (نوم قليل، إرهاق)",
            "low_motivation": "فتور مؤقت في الحماس، عادي جداً", "time_conflict": "تعارض في الوقت/الجدول", "other": "سبب تاني",
        }
        h_fatigue = h.fatigue_type if h else None
        fatigue_type = st.selectbox("لو حسّيت إنك قصّرت، السبب كان إيه؟ (اختياري، للفهم مش للمحاسبة)",
                                     options=list(fatigue_options.keys()), format_func=lambda k: fatigue_options[k],
                                     index=list(fatigue_options.keys()).index(h_fatigue) if h_fatigue in fatigue_options else 0)
        barriers = st.text_input("إيه اللي خلى اليوم أصعب؟", value=(h.barriers if h and h.barriers else ""))
        triggers = st.text_input("حصل قبلها إيه؟ (سياق، مش اعتراف)", value=(h.triggers if h and h.triggers else ""))
        healthy_eating = st.checkbox("أكل صحي النهاردة", value=(h.healthy_eating if h else False))
        sugar_avoided = st.checkbox("جنبت السكر", value=(h.sugar_avoided if h else False))
        calorie_deficit = st.checkbox("في Deficit سعري", value=(h.calorie_deficit if h else False))
        satiety_meal = st.checkbox("استخدمت وجبة شبع", value=(h.satiety_meal_used if h else False))

        st.markdown("**🕊️ السلام الداخلي**")
        st.caption("الهدف هنا إنك تفهم نفسك، مش إنك تحاسبها.")
        ip = draft.inner_peace
        escape_flag = st.checkbox(
            "حسّيت إنك احتجت \"تهرب\" أو تفرّغ ضغط النهاردة؟",
            value=bool(ip.escape_flag) if ip and ip.escape_flag else False,
            help="مؤشر لفهم نمطك بمرور الوقت — مفيش حكم عليه هنا ولا في التقرير الأسبوعي.",
        )
        root_cause = st.text_input("إيه السبب اللي حسّيت إنه ضاغط عليك؟", value=(ip.root_cause if ip and ip.root_cause else ""))
        context_tag = st.text_input("تصنيف قصير (مثلاً: ضغط سكن)", value=(ip.context_tag if ip and ip.context_tag else ""))
        stress_level = st.slider("مستوى الضغط", 1, 5, value=(ip.stress_level if ip and ip.stress_level else 3))
        sense_of_control = st.slider("قد إيه حسّيت إنك متحكم في ردة فعلك/أعصابك النهاردة؟", 1, 5,
                                      value=(ip.sense_of_control_score if ip and ip.sense_of_control_score else 3))
        early_stopping = st.checkbox("قدرت توقف الانزلاق بدري (لو حصل) — ده إنجاز يستاهل يتسجل", value=(ip.early_stopping_used if ip else False))

        st.markdown("**🚀 التطوير المهني والعقلي**")
        g = draft.growth
        work_tasks = st.text_input("مهام الشغل المنجزة", value=(g.work_tasks_done if g and g.work_tasks_done else ""))
        deep_work_hours = st.number_input("ساعات Deep Work", min_value=0.0, max_value=16.0, step=0.5,
                                           value=float(g.deep_work_hours) if g and g.deep_work_hours else 0.0)
        ai_practice = st.checkbox("اشتغلت على AI/Agents النهاردة", value=(g.ai_skill_practice if g else False))
        ai_notes = st.text_input("تفاصيل (ورقة/كود/أداة)", value=(g.ai_practice_notes if g and g.ai_practice_notes else ""))
        mental_nutrition = st.text_input("كتاب/بودكاست", value=(g.mental_nutrition if g and g.mental_nutrition else ""))
        felt_sustainable = st.checkbox("حسّيت إن وتيرة شغلك النهاردة مستدامة (مش قريبة من الاحتراق)؟",
                                        value=(g.felt_sustainable if g and g.felt_sustainable is not None else True))

        submitted = st.form_submit_button("💾 احفظ اليومية", type="primary")

    if submitted:
        final = DailyExtraction(
            transcript=draft.transcript,
            prayers=prayer_rows,
            spiritual_daily={"morning_adhkar_done": morning_adhkar, "evening_adhkar_done": evening_adhkar},
            health={
                "gym_went": gym_went, "motivation_score": motivation, "fatigue_type": fatigue_type,
                "barriers": barriers or None, "triggers": triggers or None, "healthy_eating": healthy_eating,
                "sugar_avoided": sugar_avoided, "calorie_deficit": calorie_deficit, "satiety_meal_used": satiety_meal,
            },
            inner_peace={
                "escape_flag": 1 if escape_flag else 0, "root_cause": root_cause or None,
                "context_tag": context_tag or None, "stress_level": stress_level,
                "sense_of_control_score": sense_of_control, "early_stopping_used": early_stopping,
            },
            growth={
                "work_tasks_done": work_tasks or None, "deep_work_hours": deep_work_hours or None,
                "ai_skill_practice": ai_practice, "ai_practice_notes": ai_notes or None,
                "mental_nutrition": mental_nutrition or None, "felt_sustainable": felt_sustainable,
            },
        )
        db.save_daily_extraction(
            entry_date, st.session_state.draft_source, st.session_state.draft_raw_text, final
        )
        st.success("✅ اتحفظت اليومية — يوم واحد مش بيحدد قيمتك، بس بيضيف لفهمك لنفسك.")
        st.session_state.draft = None
        st.session_state.draft_source = None
        st.session_state.draft_raw_text = None

st.divider()
st.page_link("pages/1_Dashboard.py", label="📊 روح للـ Dashboard")
st.page_link("pages/2_Weekly_Review.py", label="🗓️ المراجعة الأسبوعية")
