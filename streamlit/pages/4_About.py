import streamlit as st
import time

# Check if the user is logged in
if st.session_state['authenticated']:

    # Create a sign-out button
    _, _, col3 = st.columns([2, 8, 2])
    with col3:
        sign_out_btn = st.button("Sign Out", key="sign_out", use_container_width=True)

        if sign_out_btn:
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.cache_resource.clear()
            # time.sleep(2)
            st.switch_page("0_Home.py")

    st.header("About")

    st.write('This app was developed by students from Instituto Superior Técnico and Nova School of Business and Economics, under the guidance of Professors Rodrigo Belo and Bernardo Forbes Costa from Nova School of Business and Economics.')

else:
    st.header("About")
    st.write('Please Login first.')
