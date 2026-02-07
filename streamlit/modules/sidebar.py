from modules.app_version import get_app_version

import streamlit as st


def render_sidebar(current_page=None):
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("## AI Assistant Platform")
        st.markdown("---")

        if st.session_state.get("authenticated"):
            if st.button(
                "Home",
                width="stretch",
                type="primary" if current_page == "home" else "secondary",
            ):
                st.switch_page("0_Home.py")
            if st.session_state.get("instructor"):
                if st.button(
                    "Control Panel",
                    width="stretch",
                    type="primary" if current_page == "control_panel" else "secondary",
                ):
                    st.switch_page("pages/2_Control_Panel.py")
            if st.button(
                "Play",
                width="stretch",
                type="primary" if current_page == "play" else "secondary",
            ):
                st.switch_page("pages/1_Play.py")
            if st.button(
                "Playground",
                width="stretch",
                type="primary" if current_page == "playground" else "secondary",
            ):
                st.switch_page("pages/3_Playground.py")
            if st.button(
                "Profile",
                width="stretch",
                type="primary" if current_page == "profile" else "secondary",
            ):
                st.switch_page("pages/4_Profile.py")
            if st.button("Sign Out", width="stretch"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.cache_resource.clear()
                st.switch_page("0_Home.py")
        else:
            st.subheader("Sign in")
            with st.form("sidebar_login_form"):
                email = st.text_input("Email", key="sidebar_login_email")
                password = st.text_input("Password", type="password", key="sidebar_login_password")
                submitted = st.form_submit_button("Login")
                st.markdown("<a href='?show_set_password_form=true'>Set password</a>", unsafe_allow_html=True)

            if submitted:
                import hashlib

                from modules.database_handler import authenticate_user, get_user_id_by_email, is_instructor

                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                st.info("Please wait...")
                if authenticate_user(email, hashed_password):
                    st.session_state["login_email"] = email
                    st.session_state["login_password"] = password
                    st.session_state["instructor"] = is_instructor(email)
                    st.session_state["authenticated"] = True
                    user_id = get_user_id_by_email(email)
                    st.session_state.update({"user_id": user_id})
                    st.success("Logged in.")
                    st.rerun()
                else:
                    st.error("Invalid email or password")

        st.markdown("---")
        if st.session_state.get("authenticated"):
            role = "Instructor" if st.session_state.get("instructor") else "Student"
            email = st.session_state.get("login_email", "")
            if email:
                st.caption(f"{email} • {role}")
            else:
                st.caption(role)
        st.caption(f"Version: {get_app_version()}")
