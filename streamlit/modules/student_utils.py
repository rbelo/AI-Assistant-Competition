import logging

import pandas as pd
from modules.database_handler import insert_student_data

logger = logging.getLogger(__name__)


def normalize_column_names(df):
    """
    Normalizes column names to a standard set.
    """
    column_mapping = {
        "user_id": ["userid", "user_id", "id", "user id"],
        "email": ["email", "e-mail", "mail", "email address"],
        "group_id": ["groupid", "group_id", "group", "group id"],
        "academic_year": ["academic year", "academic_year", "year", "academicyear"],
        "class": ["class", "class_name", "classname"],
    }

    # Create a reverse mapping for easy lookup
    reverse_mapping = {}
    for standard, variations in column_mapping.items():
        for var in variations:
            reverse_mapping[var.lower()] = standard

    # Rename columns
    new_columns = {}
    for col in df.columns:
        col_lower = col.lower().strip()
        if col_lower in reverse_mapping:
            new_columns[col] = reverse_mapping[col_lower]

    return df.rename(columns=new_columns)


def process_student_csv(file):
    """
    Reads a CSV file, normalizes headers, checks for required columns,
    and inserts student data.

    Returns:
        tuple: (success (bool), message (str))
    """
    try:
        # Try reading with different delimiters if necessary, but default to ';' as per original
        # or try to sniff it? For now, stick to ';' but maybe fallback to ','?
        # Let's try to be smart.
        # Try reading with semicolon first
        try:
            df = pd.read_csv(file, sep=";", dtype={"academic year": str, "academic_year": str, "year": str})
            # If only one column is found, it might be the wrong separator
            if len(df.columns) <= 1:
                file.seek(0)
                df_comma = pd.read_csv(file, sep=",", dtype={"academic year": str, "academic_year": str, "year": str})
                # If comma gives more columns, use it
                if len(df_comma.columns) > len(df.columns):
                    df = df_comma
        except Exception:
            # Fallback to comma if semicolon fails completely
            file.seek(0)
            df = pd.read_csv(file, sep=",", dtype={"academic year": str, "academic_year": str, "year": str})

        logger.debug("CSV file read successfully.")

        # Normalize columns
        df = normalize_column_names(df)

        # Required columns
        required_columns = ["user_id", "email", "group_id", "academic_year", "class"]

        # Check for missing columns
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            return False, f"Missing required columns: {', '.join(missing_columns)}. Please check your CSV headers."

        # Insert student data row by row
        success_count = 0
        failure_count = 0
        failure_examples = []
        max_examples = 5

        for idx, row in df.iterrows():
            row_number = idx + 2  # includes header row on line 1
            user_id_raw = row["user_id"]
            email_raw = row["email"]
            group_id_raw = row["group_id"]
            academic_year_raw = row["academic_year"]
            class_raw = row["class"]

            if (
                pd.isna(user_id_raw)
                or pd.isna(email_raw)
                or pd.isna(group_id_raw)
                or pd.isna(academic_year_raw)
                or pd.isna(class_raw)
            ):
                failure_count += 1
                if len(failure_examples) < max_examples:
                    failure_examples.append(f"row {row_number}: missing required value")
                continue

            user_id = str(user_id_raw).strip()
            email = str(email_raw).strip().lower()
            academic_year = str(academic_year_raw).strip()
            class_ = str(class_raw).strip()

            if not user_id or not email or not academic_year or not class_:
                failure_count += 1
                if len(failure_examples) < max_examples:
                    failure_examples.append(f"row {row_number}: empty required field after normalization")
                continue

            try:
                group_id = int(str(group_id_raw).strip())
            except ValueError:
                try:
                    group_id = int(float(str(group_id_raw).strip()))
                except ValueError:
                    failure_count += 1
                    if len(failure_examples) < max_examples:
                        failure_examples.append(f"row {row_number}: invalid group_id '{group_id_raw}'")
                    continue

            logger.debug(
                "Adding student row user_id=%s email=%s group_id=%s academic_year=%s class=%s",
                user_id,
                email,
                group_id,
                academic_year,
                class_,
            )

            if insert_student_data(user_id, email, "Not defined", group_id, academic_year, class_):
                success_count += 1
            else:
                failure_count += 1
                if len(failure_examples) < max_examples:
                    failure_examples.append(f"row {row_number}: database insert failed for user_id '{user_id}'")

        if success_count == 0 and failure_count > 0:
            examples_text = "; ".join(failure_examples) if failure_examples else "no row-level diagnostics available"
            return False, f"No students were added. {failure_count} rows failed. Examples: {examples_text}."

        if failure_count > 0:
            examples_text = "; ".join(failure_examples) if failure_examples else "no row-level diagnostics available"
            return (
                True,
                f"Added {success_count} students. Failed to add {failure_count} students. Examples: {examples_text}.",
            )
        else:
            return True, "All students added successfully!"

    except Exception as e:
        return False, f"Error processing the CSV file: {str(e)}"
