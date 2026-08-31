"""
🗓️ The Weekly Automated Interviewer.
Computes this week's stats, opens with Gemini's root-cause/bottleneck/correlation
read, then keeps a real back-and-forth chat until a next-week hypothesis is pinned
down and saved.
"""

import streamlit as st

from lib.auth import require_login
from lib.analysis import compute_weekly_stats
from lib.gemini_client import start_weekly_review, continue_weekly_review
from lib import db

st.set_page_config(page_title="Nexus Core — المراجعة الأسبوعية", page_icon="🗓️", layout="centered")
require_login()

st.title("🗓️ المراجعة الأسبوعية الآلية")

week_start, week_end = db.this_week_bounds()
st.caption(f"الأسبوع الحالي: {week_start.isoformat()} → {week_end.isoformat()}")

if "weekly_report_id" not in st.session_state:
    st.session_state.weekly_report_id = None
if "weekly_interaction_id" not in st.session_state:
    st.session_state.weekly_interaction_id = None
if "weekly_conversation" not in st.session_state:
    st.session_state.weekly_conversation = []

existing = db.get_latest_weekly_report()
already_this_week = existing and existing["week_start"] == week_start.isoformat()

if already_this_week and not st.session_state.weekly_conversation:
    st.session_state.weekly_report_id = existing["id"]
    st.session_state.weekly_conversation = existing.get("conversation") or []
    st.session_state.weekly_interaction_id = None  # can't resume server-side thread across reruns/deploys

if not st.session_state.weekly_conversation:
    st.info("لسه ما بدأتش مراجعة الأسبوع ده.")
    if st.button("🚀 ابدأ المراجعة", type="primary"):
        with st.spinner("بيحلل بيانات الأسبوع..."):
            stats = compute_weekly_stats(week_start, week_end)
            opening_text, interaction_id = start_weekly_review(stats)
            report_id = db.save_weekly_report(week_start, week_end, stats, opening_text)
        st.session_state.weekly_report_id = report_id
        st.session_state.weekly_interaction_id = interaction_id
        st.session_state.weekly_conversation = [{"role": "assistant", "content": opening_text}]
        st.rerun()
else:
    for msg in st.session_state.weekly_conversation:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_msg = st.chat_input("اكتب فرضيتك أو ردك...")
    if user_msg:
        st.session_state.weekly_conversation.append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.write(user_msg)
        with st.spinner("..."):
            reply_text, interaction_id = continue_weekly_review(
                user_msg, st.session_state.weekly_interaction_id,
                conversation_history=st.session_state.weekly_conversation[:-1],
            )
        st.session_state.weekly_interaction_id = interaction_id
        st.session_state.weekly_conversation.append({"role": "assistant", "content": reply_text})
        db.append_weekly_conversation(st.session_state.weekly_report_id, st.session_state.weekly_conversation)
        st.rerun()

    st.divider()
    with st.form("hypothesis_form"):
        st.caption("لما توصل لفرضية نهائية، ثبّتها هنا عشان نراجعها الأسبوع الجاي.")
        hyp = st.text_area("الفرضية النهائية لهذا الأسبوع")
        if st.form_submit_button("📌 ثبّت الفرضية") and hyp.strip():
            db.save_weekly_hypothesis(st.session_state.weekly_report_id, hyp)
            st.success("✅ اتحفظت الفرضية، هنراجعها الأسبوع الجاي")

st.page_link("app.py", label="⬅️ رجوع لليومية")
st.page_link("pages/1_Dashboard.py", label="📊 Dashboard")
