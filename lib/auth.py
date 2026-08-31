"""
Minimal password gate. This app will be deployed on a public Streamlit Community
Cloud URL, and it's a personal journal — so every page must call require_login()
before rendering anything else. Not bank-grade security, just enough that a random
visitor who finds the URL can't read your data.
"""

import hmac
import streamlit as st


def require_login() -> None:
    if st.session_state.get("authenticated"):
        return

    st.title("🔒 Nexus Core")
    password = st.text_input("كلمة المرور", type="password")
    if st.button("دخول") or password:
        expected = st.secrets.get("APP_PASSWORD")
        if expected and hmac.compare_digest(password, expected):
            st.session_state["authenticated"] = True
            st.rerun()
        elif password:
            st.error("كلمة مرور غير صحيحة")

    if not st.session_state.get("authenticated"):
        st.stop()
