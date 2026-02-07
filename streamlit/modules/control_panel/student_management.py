import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, ColumnsAutoSizeMode, GridOptionsBuilder, GridUpdateMode

from ..database_handler import get_students_from_db, insert_student_data, remove_student
from ..student_utils import process_student_csv


def render_student_management_tab():
    st.subheader("Student Management")

    def show_cc_student_table():
        students_from_db = get_students_from_db()
        students_display = students_from_db.rename(
            columns={
                "user_id": "User ID",
                "email": "Email",
                "group_id": "Group ID",
                "academic_year": "Academic Year",
                "class": "Class",
                "timestamp_user": "Created at",
            }
        )

        st.session_state.cc_students = students_display
        students_display[""] = ""

        gb = GridOptionsBuilder.from_dataframe(
            students_display[["", "User ID", "Email", "Group ID", "Academic Year", "Class", "Created at"]]
        )
        gb.configure_column("", checkboxSelection=True, width=60)
        gb.configure_column("User ID", width=120)
        gb.configure_column("Email", width=140)
        gb.configure_column("Group ID", width=120)
        gb.configure_column("Academic Year", width=140)
        gb.configure_column("Class", width=80)
        gb.configure_column("Created at", width=130)
        gb.configure_selection("single")
        grid_options = gb.build()

        data = AgGrid(
            students_display[["", "User ID", "Email", "Group ID", "Academic Year", "Class", "Created at"]],
            gridOptions=grid_options,
            fit_columns_on_grid_load=True,
            height=min(36 + 27 * students_display.shape[0], 300),
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
        )
        return data

    data = show_cc_student_table()
    st.session_state.cc_selected_student = data["selected_rows"]

    _, col1, col2, col3 = st.columns([1, 1, 1, 2])

    with col1:
        if st.button("Add Students", key="cc_add_students_via_csv"):
            st.session_state.cc_add_students = True
            st.session_state.cc_add_student = False
            st.session_state.cc_remove_student = False
    with col2:
        if st.button("Add Student", key="cc_add_student_manually"):
            st.session_state.cc_add_student = True
            st.session_state.cc_add_students = False
            st.session_state.cc_remove_student = False
    with col3:
        if st.button("Remove Student", key="cc_remove_student_manually"):
            st.session_state.cc_remove_student = True
            st.session_state.cc_add_student = False
            st.session_state.cc_add_students = False

    if st.session_state.cc_add_students:
        with st.form("cc_add_students_form"):
            uploaded_file = st.file_uploader("Upload CSV with all the Students", type=["csv"], key="cc_upload_csv")
            submit_button = st.form_submit_button("Add Students")

            if submit_button:
                if uploaded_file is not None:
                    success, message = process_student_csv(uploaded_file)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                else:
                    st.error("Please upload a valid CSV file.")
                st.session_state.cc_add_students = False
                st.rerun()

    if st.session_state.cc_add_student:
        with st.form("cc_add_student_form"):
            user_id = st.text_input("Introduce User ID:", key="cc_user_id")
            email = st.text_input("Introduce Email:", key="cc_email")
            group_id = st.text_input("Introduce the Group ID:", key="cc_group_id")
            academic_year = st.text_input("Introduce academic year:", key="cc_academic_year")
            class_ = st.text_input("Introduce class:", key="cc_class")

            submit_button = st.form_submit_button("Add Student")

            if submit_button:
                if not user_id or not email or not group_id or not academic_year or not class_:
                    st.error("Please fill in all fields.")
                else:
                    if insert_student_data(user_id, email, "Not defined", group_id, academic_year, class_):
                        st.success("Student added.")
                    else:
                        st.error("Failed to add student. Please try again.")
                    st.session_state.cc_add_student = False
                    st.rerun()

    if st.session_state.cc_remove_student:
        if st.session_state.cc_students.empty:
            st.warning("No students found. Please add a student.")
        else:
            if st.session_state.cc_selected_student is not None:
                if len(st.session_state.cc_selected_student) != 0:
                    if isinstance(st.session_state.cc_selected_student, pd.DataFrame):
                        user_id = st.session_state.cc_selected_student["User ID"].tolist()[0]
                    else:
                        user_id = st.session_state.cc_selected_student[0]["User ID"]

                    if remove_student(user_id):
                        st.success("Student removed.")
                        st.session_state.cc_students = st.session_state.cc_students[
                            st.session_state.cc_students["User ID"] != user_id
                        ]
                    else:
                        st.error("Failed to remove student. Please try again.")
            else:
                st.warning("Please select a student to remove.")
        st.session_state.cc_remove_student = False
        st.rerun()
