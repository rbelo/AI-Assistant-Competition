def build_timing_summary(timing_totals):
    timing_summary = {
        "chat_seconds_total": round(timing_totals["chat_seconds"], 3),
        "summary_seconds_total": round(timing_totals["summary_seconds"], 3),
        "db_seconds_total": round(timing_totals["db_seconds"], 3),
        "chats_measured": timing_totals["chats_measured"],
    }
    if timing_totals["chats_measured"]:
        timing_summary["chat_seconds_avg"] = round(timing_totals["chat_seconds"] / timing_totals["chats_measured"], 3)
        timing_summary["summary_seconds_avg"] = round(
            timing_totals["summary_seconds"] / timing_totals["chats_measured"], 3
        )
        timing_summary["db_seconds_avg"] = round(timing_totals["db_seconds"] / timing_totals["chats_measured"], 3)
    else:
        timing_summary["chat_seconds_avg"] = 0.0
        timing_summary["summary_seconds_avg"] = 0.0
        timing_summary["db_seconds_avg"] = 0.0
    return timing_summary


def build_diagnostics_summary(run_diagnostics, processed_matches):
    return {
        "attempts_total": run_diagnostics["attempts_total"],
        "attempts_failed": run_diagnostics["attempts_failed"],
        "retries_used": max(run_diagnostics["attempts_total"] - processed_matches, 0),
        "summary_calls": run_diagnostics["summary_calls"],
        "avg_turns_per_successful_chat": (
            round(run_diagnostics["total_turns"] / run_diagnostics["successful_chats"], 2)
            if run_diagnostics["successful_chats"]
            else 0.0
        ),
    }


def format_unsuccessful_matchups(errors_matchups, name_roles):
    error_message = "The following negotiations were unsuccessful:\n\n"
    for match in errors_matchups:
        error_message += f"- Round {match[0]} - {match[1]} ({name_roles[0]}) vs {match[2]} ({name_roles[1]});\n"
    return error_message
