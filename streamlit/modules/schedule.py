import random


def berger_schedule(teams, num_rounds):

    # Add a dummy team if the number of teams is odd
    is_odd = len(teams) % 2 != 0
    num_teams = len(teams)

    if is_odd:
        num_teams += 1
        teams += ["Dummy"]

    # Generate the schedule
    schedule = []
    shuffled_teams = teams[:]
    random.shuffle(shuffled_teams)

    for _ in range(num_rounds):

        round_matches = []

        for i in range(num_teams // 2):

            team1 = shuffled_teams[i]
            team2 = shuffled_teams[num_teams - 1 - i]

            # Avoid scheduling matches with the dummy player (if odd number of players)
            if not is_odd or (is_odd and team1 != "Dummy" and team2 != "Dummy"):
                round_matches.append((team1, team2))

        # Append the round's matchups to the schedule
        schedule.append(round_matches)

        # Rotate the players (except the first one)
        shuffled_teams = [shuffled_teams[0]] + shuffled_teams[-1:] + shuffled_teams[1:-1]
    return schedule
