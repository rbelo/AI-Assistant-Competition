import pandas as pd

import streamlit as st

from ..database_handler import get_students_from_db, insert_student_data, remove_student
from ..student_utils import process_student_csv


def render_student_management_tab():
    st.subheader("Student Management")
    msg = st.session_state.pop("cc_student_import_message", None)
    if msg:
        getattr(st, msg[0])(msg[1])
    students_from_db = get_students_from_db()
    if not isinstance(students_from_db, pd.DataFrame):
        st.error("Failed to load students from database.")
        students_display = pd.DataFrame(
            columns=["User ID", "Email", "Group ID", "Academic Year", "Class", "Created at"]
        )
    else:
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

    if not students_display.empty:
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            year_options = ["All"] + sorted(
                students_display["Academic Year"].astype(str).unique().tolist(), reverse=True
            )
            selected_year = st.selectbox("Filter by Academic Year", year_options, key="cc_students_filter_year")
        with filter_col2:
            class_options = ["All"] + sorted(students_display["Class"].astype(str).unique().tolist())
            selected_class = st.selectbox("Filter by Class", class_options, key="cc_students_filter_class")
        with filter_col3:
            search = st.text_input("Search by User ID or Email", key="cc_students_filter_search").strip().lower()

        filtered_students = students_display.copy()
        if selected_year != "All":
            filtered_students = filtered_students[filtered_students["Academic Year"].astype(str) == selected_year]
        if selected_class != "All":
            filtered_students = filtered_students[filtered_students["Class"].astype(str) == selected_class]
        if search:
            filtered_students = filtered_students[
                filtered_students["User ID"].astype(str).str.lower().str.contains(search, na=False)
                | filtered_students["Email"].astype(str).str.lower().str.contains(search, na=False)
            ]

        st.dataframe(
            filtered_students[["User ID", "Email", "Group ID", "Academic Year", "Class", "Created at"]],
            width="stretch",
            hide_index=True,
            height=min(42 + 35 * max(len(filtered_students), 1), 420),
        )
    else:
        filtered_students = students_display
        st.info("No students found.")

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
                        st.session_state.cc_student_import_message = ("success", message)
                        st.session_state.cc_add_students = False
                        st.session_state.pop("cc_upload_csv", None)
                    else:
                        st.session_state.cc_student_import_message = ("error", message)
                    st.rerun()
                else:
                    st.session_state.cc_student_import_message = ("error", "Please upload a valid CSV file.")
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
                    st.session_state.cc_student_import_message = ("error", "Please fill in all fields.")
                else:
                    if insert_student_data(user_id, email, "Not defined", group_id, academic_year, class_):
                        st.session_state.cc_student_import_message = ("success", "Student added successfully.")
                    else:
                        st.session_state.cc_student_import_message = (
                            "error",
                            "Failed to add student. Please try again.",
                        )
                    st.session_state.cc_add_student = False
                    st.rerun()

    if st.session_state.cc_remove_student:
        if st.session_state.cc_students.empty:
            st.session_state.cc_student_import_message = ("warning", "No students found. Please add a student.")
            st.session_state.cc_remove_student = False
            st.rerun()
        else:
            removal_base = filtered_students if not filtered_students.empty else st.session_state.cc_students
            labels = {
                str(row["User ID"]): (
                    f"{row['User ID']} • {row['Email']} • "
                    f"Group {row['Group ID']} • {row['Academic Year']} • {row['Class']}"
                )
                for _, row in removal_base.iterrows()
            }

            selected_user_ids = st.multiselect(
                "Select students to remove",
                options=sorted(labels.keys()),
                format_func=lambda uid: labels.get(uid, uid),
                key="cc_remove_selected_user_ids",
            )

            if st.button("Delete Selected Students", key="cc_delete_selected_students"):
                if not selected_user_ids:
                    st.session_state.cc_student_import_message = ("warning", "Please select at least one student.")
                else:
                    removed = 0
                    failed = []
                    for user_id in selected_user_ids:
                        if remove_student(user_id):
                            removed += 1
                        else:
                            failed.append(user_id)

                    if removed > 0 and not failed:
                        st.session_state.cc_student_import_message = (
                            "success",
                            f"Removed {removed} student(s) successfully.",
                        )
                    elif removed > 0 and failed:
                        st.session_state.cc_student_import_message = (
                            "warning",
                            f"Removed {removed} student(s). Failed to remove {len(failed)}: {', '.join(failed[:3])}.",
                        )
                    else:
                        st.session_state.cc_student_import_message = (
                            "error",
                            f"Failed to remove selected students: {', '.join(failed[:3])}.",
                        )

                    st.session_state.cc_remove_student = False
                    st.rerun()
