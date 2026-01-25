import pandas as pd
from modules.database_handler import insert_student_data


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

        print("CSV file read successfully.")

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

        for _, row in df.iterrows():
            user_id = row["user_id"]
            email = row["email"]
            group_id = row["group_id"]
            academic_year = row["academic_year"]
            class_ = row["class"]

            print(f"Adding student: {user_id}, {email}, {group_id}, {academic_year}, {class_}")

            if insert_student_data(user_id, email, "Not defined", group_id, academic_year, class_):
                success_count += 1
            else:
                failure_count += 1

        if failure_count > 0:
            return (
                True,
                f"Added {success_count} students. Failed to add {failure_count} students (possibly duplicates).",
            )
        else:
            return True, "All students added successfully!"

    except Exception as e:
        return False, f"Error processing the CSV file: {str(e)}"
