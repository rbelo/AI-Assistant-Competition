"""Pure UI helper functions for Control Panel."""


def build_year_class_options(academic_year_class_combinations):
    combination_options = []
    for year, classes in academic_year_class_combinations.items():
        combination_options.append((str(year), None))
        combination_options.extend([(str(year), str(cls)) for cls in classes])
    return combination_options


def format_year_class_option(selection):
    game_academic_year, game_class = selection
    if game_class:
        return f"{game_academic_year} - {game_class}"
    return f"{game_academic_year} - All classes"


def format_game_selector_label(game_academic_year, game_class, game_name):
    class_label = str(game_class).strip() if game_class is not None else ""
    if class_label in {"", "_"}:
        class_label = "All classes"
    return f"{game_academic_year} • {class_label} • {game_name}"


def calculate_planned_chats(num_teams, rounds_to_run):
    matches_per_round = num_teams // 2
    return rounds_to_run * matches_per_round * 2


def format_progress_status_line(
    round_num,
    team1_name,
    team2_name,
    role1_name,
    role2_name,
    phase,
    attempt=None,
    elapsed_seconds=None,
):
    phase_label = phase.replace("_", " ").title()
    attempt_text = f" (attempt {attempt})" if attempt else ""
    elapsed_text = f" | elapsed {elapsed_seconds:.1f}s" if elapsed_seconds else ""
    return (
        f"Round {round_num}: {team1_name} ({role1_name}) vs {team2_name} ({role2_name}) "
        f"- {phase_label}{attempt_text}{elapsed_text}"
    )


def format_progress_caption(completed_matches, total_matches, phase):
    if phase in {"running", "retrying"}:
        current_chat = min(completed_matches + 1, total_matches)
        return f"Processing chat {current_chat} of {total_matches} (completed {completed_matches})"
    return f"Processed {completed_matches} of {total_matches} chats"
