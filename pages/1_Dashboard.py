"""
Dashboard — trends per module + a correlation view across all four boxes.

Color usage follows a fixed categorical order (never re-cycled per filter) and a
single diverging blue<->red scale for the correlation heatmap. Hex values are the
project's default validated palette (see the dataviz reference used to build this
page) — swap CATEGORICAL / DIVERGING below if you ever want a different brand.
"""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.auth import require_login
from lib.schemas import PRAYER_LABELS
from lib import db

st.set_page_config(page_title="Nexus Core — Dashboard", page_icon="📊", layout="wide")
require_login()

# Fixed categorical order — same hue always means the same series across the app.
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
DIVERGING = [[0, "#e34948"], [0.5, "#f0efec"], [1, "#2a78d6"]]
MUTED_INK, GRIDLINE = "#898781", "#e1e0d9"

CHART_LAYOUT = dict(
    plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
    font=dict(color="#0b0b0b", family="system-ui, -apple-system, Segoe UI, sans-serif"),
    xaxis=dict(gridcolor=GRIDLINE, linecolor=GRIDLINE, tickfont=dict(color=MUTED_INK)),
    yaxis=dict(gridcolor=GRIDLINE, linecolor=GRIDLINE, tickfont=dict(color=MUTED_INK)),
    legend=dict(orientation="h", y=-0.2),
    margin=dict(t=30, l=10, r=10, b=10),
)

st.title("📊 Dashboard")

range_choice = st.radio("المدى الزمني", ["آخر 7 أيام", "آخر 30 يوم", "آخر 90 يوم"], horizontal=True, index=1)
days = {"آخر 7 أيام": 7, "آخر 30 يوم": 30, "آخر 90 يوم": 90}[range_choice]
end = date.today()
start = end - timedelta(days=days - 1)

data = db.fetch_all_modules(start, end)
prayer_df, spiritual_df = data["prayer"], data["spiritual_daily"]
health_df, peace_df, growth_df = data["health"], data["inner_peace"], data["growth"]

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🕌 الخشوع", "💪 الصحة", "🕊️ السلام الداخلي", "🚀 التطوير", "🔗 الارتباطات",
])

with tab1:
    if prayer_df.empty:
        st.info("لا توجد بيانات في هذا المدى بعد.")
    else:
        fig = go.Figure()
        for i, (key, label) in enumerate(PRAYER_LABELS.items()):
            sub = prayer_df[prayer_df["prayer_name"] == key].sort_values("entry_date")
            if sub.empty:
                continue
            fig.add_trace(go.Scatter(
                x=sub["entry_date"], y=sub["khushoo_score"], mode="lines+markers",
                name=label, line=dict(color=CATEGORICAL[i % 8], width=2),
                marker=dict(size=8), connectgaps=False,
            ))
        fig.update_layout(**CHART_LAYOUT, yaxis=dict(**CHART_LAYOUT["yaxis"], range=[0.5, 5.5], title="الخشوع"))
        st.plotly_chart(fig, use_container_width=True)

        rate_cols = st.columns(3)
        for col, field, label in zip(rate_cols, ["sunan_done", "wudu_mindful", "adhkar_after"],
                                      ["السنن", "الوضوء بخشوع", "الأذكار بعد الصلاة"]):
            rate = prayer_df[field].mean() * 100 if field in prayer_df and len(prayer_df) else 0
            col.metric(label, f"{rate:.0f}%")

with tab2:
    if health_df.empty:
        st.info("لا توجد بيانات في هذا المدى بعد.")
    else:
        st.caption("مفيش يوم أحمر ويوم أخضر هنا — الأيام اللي متعملتش فيها رياضة هي داتا لفهم نمطك، مش علامة رسوب.")
        health_df = health_df.sort_values("entry_date")
        # Present/absent shown as full vs. muted opacity of the same hue — not a
        # good/bad traffic light. Whether a day "counts against you" isn't the point.
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=health_df["entry_date"], y=health_df["gym_went"].astype(int), name="رحت الجيم",
            marker_color=CATEGORICAL[0],
            marker_opacity=[1.0 if v else 0.25 for v in health_df["gym_went"].fillna(False)],
        ))
        fig.update_layout(**CHART_LAYOUT, yaxis=dict(**CHART_LAYOUT["yaxis"], tickvals=[0, 1], range=[-0.2, 1.2]))
        st.plotly_chart(fig, use_container_width=True)

        fig2 = go.Figure(go.Scatter(
            x=health_df["entry_date"], y=health_df["motivation_score"], mode="lines+markers",
            line=dict(color=CATEGORICAL[0], width=2), marker=dict(size=8), name="الطاقة/الحماس",
        ))
        fig2.update_layout(**CHART_LAYOUT, yaxis=dict(**CHART_LAYOUT["yaxis"], range=[0.5, 5.5], title="مستوى الطاقة"))
        st.plotly_chart(fig2, use_container_width=True)

        if "fatigue_type" in health_df and health_df["fatigue_type"].notna().any():
            st.markdown("**لما التزمت أقل، كان غالباً بسبب...**")
            fatigue_labels = {"real_physical_fatigue": "تعب جسدي حقيقي", "low_motivation": "فتور مؤقت",
                               "time_conflict": "تعارض وقت", "other": "سبب تاني"}
            counts = health_df["fatigue_type"].dropna().map(fatigue_labels).value_counts()
            st.bar_chart(counts)
            st.caption("لو \"تعب جسدي\" هو الأكتر تكراراً، الرسالة مش \"زوّد التزامك\"، الرسالة \"نام أكتر\".")

        gym_rate = health_df["gym_went"].mean() * 100
        sugar_rate = health_df["sugar_avoided"].mean() * 100
        c1, c2 = st.columns(2)
        c1.metric("نسبة الأيام اللي روحت فيها الجيم", f"{gym_rate:.0f}%")
        c2.metric("نسبة تجنب السكر", f"{sugar_rate:.0f}%")

with tab3:
    if peace_df.empty:
        st.info("لا توجد بيانات في هذا المدى بعد.")
    else:
        st.caption("الهدف من التبويب ده إنك تفهم نمطك، مش إنك تحاسب نفسك عليه.")
        peace_df = peace_df.sort_values("entry_date")
        fig = go.Figure(go.Bar(
            x=peace_df["entry_date"], y=peace_df["escape_flag"], name="لحظات احتجت فيها تفرّغ ضغط",
            marker_color=CATEGORICAL[6], marker_opacity=[1.0 if v == 1 else 0.2 for v in peace_df["escape_flag"].fillna(0)],
        ))
        fig.update_layout(**CHART_LAYOUT, yaxis=dict(**CHART_LAYOUT["yaxis"], tickvals=[0, 1], range=[-0.2, 1.2]))
        st.plotly_chart(fig, use_container_width=True)

        if "sense_of_control_score" in peace_df and peace_df["sense_of_control_score"].notna().any():
            fig_c = go.Figure(go.Scatter(
                x=peace_df["entry_date"], y=peace_df["sense_of_control_score"], mode="lines+markers",
                line=dict(color=CATEGORICAL[2], width=2), marker=dict(size=8), name="الشعور بالتحكم",
            ))
            fig_c.update_layout(**CHART_LAYOUT, yaxis=dict(**CHART_LAYOUT["yaxis"], range=[0.5, 5.5], title="الشعور بالتحكم"))
            st.plotly_chart(fig_c, use_container_width=True)

        if peace_df["root_cause"].notna().any():
            st.markdown("**الأسباب اللي بترجع تتكرر — عشان نفهمها، مش عشان نعدّها ضدنا**")
            st.bar_chart(peace_df["context_tag"].dropna().value_counts())

with tab4:
    if growth_df.empty:
        st.info("لا توجد بيانات في هذا المدى بعد.")
    else:
        growth_df = growth_df.sort_values("entry_date")
        fig = go.Figure(go.Scatter(
            x=growth_df["entry_date"], y=growth_df["deep_work_hours"], mode="lines+markers",
            line=dict(color=CATEGORICAL[3], width=2), marker=dict(size=8), name="ساعات Deep Work",
            fill="tozeroy", fillcolor="rgba(237,161,0,0.12)",
        ))
        fig.update_layout(**CHART_LAYOUT, yaxis=dict(**CHART_LAYOUT["yaxis"], title="ساعات"))
        st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        ai_rate = growth_df["ai_skill_practice"].mean() * 100
        c1.metric("أيام تدربت فيها على AI/Agents", f"{ai_rate:.0f}%")
        if "felt_sustainable" in growth_df and growth_df["felt_sustainable"].notna().any():
            sustainable_rate = growth_df["felt_sustainable"].mean() * 100
            c2.metric("أيام حسّيت فيها إن الوتيرة مستدامة", f"{sustainable_rate:.0f}%")
            if sustainable_rate < 50:
                st.caption("النسبة دي منخفضة — مش دعوة تشتغل أكتر، دعوة تراجع سرعتك قبل ما توصل لاحتراق فعلي.")

with tab5:
    st.caption(
        "ارتباط (Pearson correlation) بين المؤشرات الرقمية عبر كل البوكسات — أداة لفهم نمطك، مش لإصدار حكم. "
        "يحتاج بيانات كافية ليكون ذا معنى."
    )
    merged = (
        health_df[["entry_date", "motivation_score", "gym_went"]]
        .merge(peace_df[["entry_date", "escape_flag", "stress_level", "sense_of_control_score"]], on="entry_date", how="outer")
        .merge(growth_df[["entry_date", "deep_work_hours"]], on="entry_date", how="outer")
    )
    if len(merged.dropna(thresh=3)) < 5:
        st.info("محتاج أسبوعين على الأقل من البيانات عشان الارتباطات تبقى ذات معنى.")
    else:
        numeric = merged.drop(columns=["entry_date"]).apply(pd.to_numeric, errors="coerce")
        corr = numeric.corr(numeric_only=True)
        fig = go.Figure(go.Heatmap(
            z=corr.values, x=corr.columns, y=corr.columns, colorscale=DIVERGING, zmin=-1, zmax=1,
            text=corr.round(2).values, texttemplate="%{text}",
        ))
        fig.update_layout(**{k: v for k, v in CHART_LAYOUT.items() if k not in ("xaxis", "yaxis")})
        st.plotly_chart(fig, use_container_width=True)

st.page_link("app.py", label="⬅️ رجوع لليومية")
st.page_link("pages/2_Weekly_Review.py", label="🗓️ المراجعة الأسبوعية")
