#!/usr/bin/env python3
"""
Test Setup Script for Negotiation Simulation

This script sets up test data for testing the negotiation simulation system.
It creates:
1. Test students in different groups
2. A test game with proper configuration
3. Test prompts for each group

Prerequisites:
- Database connection configured in .streamlit/secrets.toml
- Google Drive credentials configured in .streamlit/secrets.toml

Usage:
    cd streamlit
    python ../scripts/setup_simulation_test.py
"""

import sys
import os
from datetime import datetime, timedelta
import random

# Add the streamlit directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit'))

# Now we can import from modules
from modules.database_handler import (
    insert_student_data,
    store_game_in_db,
    populate_plays_table,
    get_next_game_id,
    get_group_ids_from_game_id,
    store_group_values,
    store_game_parameters,
    get_students_from_db,
    get_game_by_id,
    get_all_group_values
)
from modules.drive_file_manager import upload_text_as_file, overwrite_text_file


# Test configuration
TEST_CONFIG = {
    "academic_year": 2025,
    "class": "T",  # 'T' for Test class
    "instructor_id": "test_instructor",
    "students": [
        {"user_id": "test1", "email": "test1@test.com", "group_id": 1},
        {"user_id": "test2", "email": "test2@test.com", "group_id": 2},
    ],
    "game": {
        "name": "Test Negotiation",
        "explanation": """This is a test buyer-seller negotiation game.

The Buyer wants to purchase a product for the lowest possible price.
The Seller wants to sell for the highest possible price.

Negotiation Guidelines:
- Be respectful and professional
- Make reasonable counter-offers
- When you reach an agreement, say the termination phrase followed by the agreed price
- Example: "Pleasure doing business with you at $18"

Good luck!""",
        "minimizer_role": "Buyer",
        "maximizer_role": "Seller",
        "min_minimizer": 16,  # Buyer's minimum willingness to pay
        "max_minimizer": 25,  # Buyer's maximum willingness to pay
        "min_maximizer": 7,   # Seller's minimum acceptable price
        "max_maximizer": 15,  # Seller's maximum acceptable price
        "password": "1234",
    },
    "prompts": {
        1: {  # Group 1 prompts
            "buyer": """You are a skilled buyer negotiating to purchase a product.

Your maximum budget is [PRIVATE_VALUE]. You want to get the lowest price possible, but you must reach a deal.

Negotiation Strategy:
- Start with a low offer (around 50-60% of your budget)
- Gradually increase your offer in small increments
- Be friendly but firm about your budget constraints
- Don't reveal your actual maximum budget

When you reach an agreement on a price, you MUST say exactly:
"Pleasure doing business with you" followed by the agreed price.

Example: "Pleasure doing business with you at $17"

Remember: Your goal is to minimize the final price while still reaching a deal.""",

            "seller": """You are a skilled seller negotiating to sell a product.

Your minimum acceptable price is [PRIVATE_VALUE]. You want to get the highest price possible.

Negotiation Strategy:
- Start with a high asking price (around 140-150% of your minimum)
- Gradually lower your price in small decrements
- Emphasize the value and quality of your product
- Don't reveal your actual minimum price

When you reach an agreement on a price, you MUST say exactly:
"Pleasure doing business with you" followed by the agreed price.

Example: "Pleasure doing business with you at $17"

Remember: Your goal is to maximize the final price while still reaching a deal."""
        },
        2: {  # Group 2 prompts
            "buyer": """You are a pragmatic buyer looking to purchase a product.

Your budget limit is [PRIVATE_VALUE]. Try to negotiate the best deal possible.

Your approach:
- Open with a reasonable but low offer
- Listen to the seller's justifications
- Make incremental increases based on their reasoning
- Aim for a fair middle ground

When both parties agree on a final price, end the negotiation by saying:
"Pleasure doing business with you" followed by the price.

Example: "Pleasure doing business with you at $15"

Be professional and aim for a mutually beneficial outcome.""",

            "seller": """You are a fair-minded seller offering a quality product.

Your floor price is [PRIVATE_VALUE]. You want a good profit but also value customer relationships.

Your approach:
- Start with a reasonable asking price
- Explain the value proposition of your product
- Be willing to negotiate but protect your margins
- Aim for a win-win outcome

When both parties agree on a final price, end the negotiation by saying:
"Pleasure doing business with you" followed by the price.

Example: "Pleasure doing business with you at $15"

Be professional and build rapport with the buyer."""
        }
    }
}


def setup_test_students():
    """Insert test students into the database."""
    print("\n=== Setting up Test Students ===")

    for student in TEST_CONFIG["students"]:
        user_id = student["user_id"]
        email = student["email"]
        group_id = student["group_id"]
        academic_year = TEST_CONFIG["academic_year"]
        class_ = TEST_CONFIG["class"]

        # Use a simple password for testing
        temp_password = "test123"

        result = insert_student_data(
            user_id=user_id,
            email=email,
            temp_password=temp_password,
            group_id=group_id,
            academic_year=academic_year,
            class_=class_
        )

        if result:
            print(f"  [OK] Student {user_id} ({email}) - Group {group_id}")
        else:
            print(f"  [FAIL] Could not add student {user_id}")

    # Verify students were added
    students_df = get_students_from_db()
    if students_df is not False and not students_df.empty:
        test_students = students_df[
            (students_df['academic_year'] == TEST_CONFIG["academic_year"]) &
            (students_df['class'] == TEST_CONFIG["class"])
        ]
        print(f"\n  Total test students in database: {len(test_students)}")

    return True


def setup_test_game():
    """Create a test game in the database."""
    print("\n=== Creating Test Game ===")

    game_config = TEST_CONFIG["game"]

    # Get the next available game ID
    game_id = get_next_game_id()
    if not game_id:
        print("  [FAIL] Could not get next game ID")
        return None

    print(f"  Game ID: {game_id}")

    # Game metadata
    available = 0  # Not visible to students yet
    created_by = TEST_CONFIG["instructor_id"]
    game_name = game_config["name"]
    number_of_rounds = -1  # Will be set when simulation runs
    name_roles = f"{game_config['minimizer_role']}#_;:){game_config['maximizer_role']}"
    game_academic_year = TEST_CONFIG["academic_year"]
    game_class = TEST_CONFIG["class"]
    password = game_config["password"]
    timestamp_game_creation = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    submission_deadline = datetime.now() + timedelta(weeks=1)
    explanation = game_config["explanation"]

    # Store the game
    result = store_game_in_db(
        game_id=game_id,
        available=available,
        created_by=created_by,
        game_name=game_name,
        number_of_rounds=number_of_rounds,
        name_roles=name_roles,
        game_academic_year=game_academic_year,
        game_class=game_class,
        password=password,
        timestamp_game_creation=timestamp_game_creation,
        submission_deadline=submission_deadline,
        explanation=explanation,
        game_type="zero_sum"
    )

    if not result:
        print("  [FAIL] Could not store game in database")
        return None

    print(f"  [OK] Game '{game_name}' created")

    # Populate the plays table with eligible students
    result = populate_plays_table(game_id, game_academic_year, game_class)
    if not result:
        print("  [WARN] Could not populate plays table (no eligible students?)")
    else:
        print("  [OK] Plays table populated")

    # Store game parameters (bounds)
    result = store_game_parameters(
        game_id=game_id,
        min_minimizer=game_config["min_minimizer"],
        max_minimizer=game_config["max_minimizer"],
        min_maximizer=game_config["min_maximizer"],
        max_maximizer=game_config["max_maximizer"]
    )

    if not result:
        print("  [FAIL] Could not store game parameters")
        return None

    print(f"  [OK] Game parameters stored")
    print(f"       Buyer (minimizer) range: {game_config['min_minimizer']}-{game_config['max_minimizer']}")
    print(f"       Seller (maximizer) range: {game_config['min_maximizer']}-{game_config['max_maximizer']}")

    # Generate and store values for each group
    groups = get_group_ids_from_game_id(game_id)
    if groups:
        print(f"\n  Generating values for {len(groups)} groups:")
        for class_, group_id in groups:
            # Generate random values within bounds
            buyer_value = random.randint(
                game_config["min_minimizer"],
                game_config["max_minimizer"]
            )
            seller_value = random.randint(
                game_config["min_maximizer"],
                game_config["max_maximizer"]
            )

            result = store_group_values(game_id, class_, group_id, buyer_value, seller_value)
            if result:
                print(f"    [OK] Class {class_} Group {group_id}: Buyer={buyer_value}, Seller={seller_value}")
            else:
                print(f"    [FAIL] Could not store values for Class {class_} Group {group_id}")

    return game_id


def setup_test_prompts(game_id):
    """Upload test prompts to Google Drive."""
    print("\n=== Uploading Test Prompts ===")

    # Get group values to replace [PRIVATE_VALUE] placeholder
    values = get_all_group_values(game_id)

    for group_id, prompts in TEST_CONFIG["prompts"].items():
        class_ = TEST_CONFIG["class"]

        # Find the values for this group
        group_values = next(
            (v for v in values if v["class"] == class_ and v["group_id"] == group_id),
            None
        )

        buyer_prompt = prompts["buyer"]
        seller_prompt = prompts["seller"]

        if group_values:
            # Replace placeholder with actual values
            buyer_prompt = buyer_prompt.replace("[PRIVATE_VALUE]", str(int(group_values["minimizer_value"])))
            seller_prompt = seller_prompt.replace("[PRIVATE_VALUE]", str(int(group_values["maximizer_value"])))

        # Combine prompts with delimiter (buyer prompt first, then seller)
        combined_prompts = f"{buyer_prompt}#_;:){seller_prompt}"

        # Upload to Google Drive
        filename = f"Game{game_id}_Class{class_}_Group{group_id}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

        try:
            overwrite_text_file(combined_prompts, filename)
            print(f"  [OK] Uploaded prompts for Class {class_} Group {group_id}")
        except Exception as e:
            print(f"  [FAIL] Could not upload prompts for Class {class_} Group {group_id}: {e}")

    return True


def verify_setup(game_id):
    """Verify the test setup is complete."""
    print("\n=== Verification ===")

    # Check game exists
    game = get_game_by_id(game_id)
    if game:
        print(f"  [OK] Game '{game['game_name']}' exists (ID: {game_id})")
        print(f"       Academic Year: {game['game_academic_year']}")
        print(f"       Class: {game['game_class']}")
        print(f"       Roles: {game['name_roles'].replace('#_;:)', ' vs ')}")
    else:
        print(f"  [FAIL] Game {game_id} not found")
        return False

    # Check groups
    groups = get_group_ids_from_game_id(game_id)
    if groups and len(groups) >= 2:
        print(f"  [OK] {len(groups)} groups assigned to game")
    else:
        print(f"  [FAIL] Need at least 2 groups (found {len(groups) if groups else 0})")
        return False

    # Check group values
    values = get_all_group_values(game_id)
    if values and len(values) >= 2:
        print(f"  [OK] Group values configured for {len(values)} groups")
    else:
        print(f"  [FAIL] Group values missing (found {len(values) if values else 0})")
        return False

    print("\n" + "="*60)
    print("SETUP COMPLETE!")
    print("="*60)
    print(f"""
Next Steps:
1. Start the Streamlit app:  make run
2. Log in as an instructor
3. Go to Control Panel -> Run Simulation
4. Select:
   - Academic Year: {TEST_CONFIG['academic_year']}
   - Game: {TEST_CONFIG['game']['name']} - Class {TEST_CONFIG['class']}
5. Fill in simulation parameters:
   - API Key: [Your OpenAI API key]
   - Model: gpt-5-mini
   - Number of Rounds: 1
   - Conversation Starter: {TEST_CONFIG['game']['minimizer_role']} -> {TEST_CONFIG['game']['maximizer_role']}
   - Starting Message: "Hello, shall we start the negotiation?"
   - Max Turns: 10
   - Termination Message: "Pleasure doing business with you"
   - Summary Prompt: "What was the value agreed?"
   - Summary Termination: "The value agreed was"
6. Click "Run" and wait for completion
7. Verify results in Game Data -> View Chats
8. Check Leaderboard for scores
""")

    return True


def main():
    """Main entry point."""
    print("="*60)
    print("Negotiation Simulation Test Setup")
    print("="*60)

    # Step 1: Add test students
    if not setup_test_students():
        print("Failed to set up test students")
        return 1

    # Step 2: Create test game
    game_id = setup_test_game()
    if not game_id:
        print("Failed to create test game")
        return 1

    # Step 3: Upload test prompts
    if not setup_test_prompts(game_id):
        print("Failed to upload test prompts")
        return 1

    # Step 4: Verify setup
    if not verify_setup(game_id):
        print("Setup verification failed")
        return 1

    return 0


def add_ssl_to_supabase_url(url):
    """
    Add SSL requirement to Supabase connection URL.

    The Supabase pooler (port 6543) requires SSL mode for command-line scripts.
    This adds ?sslmode=require to the connection URL if not already present.
    """
    if 'pooler.supabase.com' not in url:
        return url  # Not a Supabase URL, return as-is

    if 'sslmode=' in url:
        return url  # Already has SSL mode set

    # Add sslmode=require to the URL
    if '?' in url:
        return url + '&sslmode=require'
    else:
        return url + '?sslmode=require'


if __name__ == "__main__":
    print("Starting setup script...", flush=True)

    # Need to set up Streamlit secrets for this to work outside of Streamlit
    # This is typically done by running from within the streamlit directory
    # with the secrets.toml file present

    import toml

    # Load secrets manually if not in a Streamlit context
    secrets_path = os.path.join(os.path.dirname(__file__), '..', 'streamlit', '.streamlit', 'secrets.toml')
    print(f"Looking for secrets at: {secrets_path}", flush=True)

    if os.path.exists(secrets_path):
        secrets = toml.load(secrets_path)

        # Add SSL requirement for Supabase pooler connection
        if 'database' in secrets and 'url' in secrets['database']:
            original_url = secrets['database']['url']
            ssl_url = add_ssl_to_supabase_url(original_url)
            if ssl_url != original_url:
                print("  Adding SSL requirement for Supabase connection...", flush=True)
                secrets['database']['url'] = ssl_url

        # Create a mock st.secrets that works like Streamlit's version
        class SecretsDict(dict):
            def __getattr__(self, key):
                val = self.get(key)
                if isinstance(val, dict):
                    return SecretsDict(val)
                return val

            def __getitem__(self, key):
                val = super().__getitem__(key)
                if isinstance(val, dict):
                    return SecretsDict(val)
                return val

        # Mock streamlit's secrets
        import streamlit as st
        st.secrets = SecretsDict(secrets)
        print(f"Loaded secrets from {secrets_path}", flush=True)
    else:
        print(f"Warning: secrets.toml not found at {secrets_path}", flush=True)
        print("Make sure you're running from the project root directory", flush=True)
        sys.exit(1)

    try:
        result = main()
        sys.exit(result)
    except Exception as e:
        import traceback
        print(f"Error: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
