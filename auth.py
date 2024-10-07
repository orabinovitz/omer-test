import streamlit as st
import re

def is_authorized(email):
    allowed_domains = ["lightricks.com"]  # Add more domains if needed
    pattern = r'^[\w\.-]+@(' + '|'.join(allowed_domains) + ')$'
    return re.match(pattern, email) is not None

def check_auth():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        email = st.text_input("Enter your email")
        if st.button("Login"):
            if is_authorized(email):
                st.session_state.authenticated = True
                st.experimental_rerun()
            else:
                st.error("Invalid email. Please use your Lightricks email address.")
        st.stop()