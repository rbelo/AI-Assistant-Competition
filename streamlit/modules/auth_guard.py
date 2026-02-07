import streamlit as st


def ensure_session_defaults() -> None:
    defaults = {
        "authenticated": False,
        "instructor": False,
        "set_password_email": "",
        "login_email": "",
        "login_password": "",
        "show_set_password_form": False,
        "user_id": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def require_auth(page_label: str, redirect_path: str = "0_Home.py") -> None:
    ensure_session_defaults()
    if st.session_state.get("authenticated", False):
        return

    st.warning(f"Please login first to access {page_label}. Redirecting to Home.")
    st.switch_page(redirect_path)
    st.stop()


def require_instructor(redirect_path: str = "0_Home.py") -> None:
    ensure_session_defaults()
    if st.session_state.get("instructor", False):
        return

    st.warning("This page is accessible only to instructors. Redirecting to Home.")
    st.switch_page(redirect_path)
    st.stop()
