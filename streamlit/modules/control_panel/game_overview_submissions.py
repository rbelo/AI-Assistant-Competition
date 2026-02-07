import pandas as pd
import streamlit as st

from ..database_handler import get_group_ids_from_game_id, get_student_prompt_with_timestamp


def render_submissions_tab(selected_game: dict) -> None:
    game_id = selected_game["game_id"]
    name_roles = selected_game["name_roles"].split("#_;:)")
    name_roles_1, name_roles_2 = name_roles[0], name_roles[1]
    teams = get_group_ids_from_game_id(game_id)

    if teams is False:
        st.error("An error occurred while retrieving group information.")
        return
    if not teams:
        st.write("No teams found for this game.")
        return

    submissions = []
    missing_groups = []
    for class_, group_id in teams:
        prompt_data = get_student_prompt_with_timestamp(game_id, class_, group_id)
        prompts = prompt_data["prompt"] if prompt_data else None
        updated_at = prompt_data["updated_at"] if prompt_data else None
        has_prompt = bool(prompts)
        if not has_prompt:
            missing_groups.append(f"Class {class_} - Group {group_id}")
        submissions.append(
            {
                "Class": class_,
                "Group": group_id,
                "Status": "Submitted" if has_prompt else "Missing",
                "Last Submission": updated_at,
                "Prompts": prompts,
            }
        )

    submitted_count = sum(1 for row in submissions if row["Status"] == "Submitted")
    st.write(f"Submitted: {submitted_count} / {len(submissions)}")
    if missing_groups:
        st.warning("Missing submissions: " + ", ".join(missing_groups))

    submissions_df = pd.DataFrame(
        [
            {
                "Class": row["Class"],
                "Group": row["Group"],
                "Status": row["Status"],
                "Last Submission": (
                    row["Last Submission"].strftime("%Y-%m-%d %H:%M") if row["Last Submission"] else ""
                ),
            }
            for row in submissions
        ]
    )
    st.dataframe(submissions_df, width="stretch")

    with st.expander("View Prompts"):
        for row in submissions:
            with st.expander(f"Class {row['Class']} - Group {row['Group']}"):
                if row["Prompts"]:
                    prompts = row["Prompts"].split("#_;:)")
                    st.write(f"**{name_roles_1}:** {prompts[0].strip()}")
                    st.write(f"**{name_roles_2}:** {prompts[1].strip()}")
                else:
                    st.write("No submission found.")
