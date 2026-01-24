# Negotiation Simulation Testing Guide

This guide walks you through testing the negotiation simulation system manually through the Streamlit UI.

## Prerequisites

1. **OpenAI API Key** - You need a valid OpenAI API key with access to GPT-4o or GPT-4o-mini
2. **Application Running** - Start the app with `make run` or `cd streamlit && streamlit run 0_Home.py`
3. **Instructor Account** - Log in as an instructor to access the Control Panel

## Step 1: Add Test Students

### Via the Control Panel UI:

1. Go to **Control Panel** → **Student Management**
2. Click **"Add Student"** to add students manually

Create at least 2 students in different groups:

| Field | Student 1 | Student 2 |
|-------|-----------|-----------|
| User ID | test1 | test2 |
| Email | test1@test.com | test2@test.com |
| Group ID | 1 | 2 |
| Academic Year | 2025 | 2025 |
| Class | T | T |

**Alternative: Upload via CSV**
1. Click **"Add Students"**
2. Upload a CSV file with format:
```csv
user_id;email;group_id;academic_year;class
test1;test1@test.com;1;2025;T
test2;test2@test.com;2;2025;T
```

## Step 2: Create Test Game

1. Go to **Control Panel** → **Create Game**
2. Fill in the form:

| Field | Value |
|-------|-------|
| Game Name | Test Negotiation |
| Game Explanation | A test buyer-seller negotiation game. The Buyer wants to purchase for the lowest price. The Seller wants to sell for the highest price. When you reach an agreement, say "Pleasure doing business with you" followed by the price. |
| Game Type | Zero Sum |
| Name of Minimizer Role | Buyer |
| Name of Maximizer Role | Seller |
| Lower Bound for Minimizer | 16 |
| Upper Bound for Minimizer | 25 |
| Lower Bound for Maximizer | 7 |
| Upper Bound for Maximizer | 15 |
| Academic Year/Class | 2025 - T |
| Password | 1234 |
| Submission Deadline | Any future date |

3. Click **"Create Game"**

## Step 3: Submit Test Prompts

For each test student, you need to submit prompts. You can do this in two ways:

### Option A: Log in as each student and use the Playground

1. Log out from instructor account
2. Log in as `test1@test.com` with password `test123`
3. Go to **Playground** → Select the test game
4. Submit the following prompts:

**Group 1 - Buyer Prompt:**
```
You are a skilled buyer negotiating to purchase a product. Your maximum budget is [PRIVATE_VALUE].

Strategy:
- Start with a low offer (around 50-60% of your budget)
- Gradually increase in small increments
- Be friendly but firm

When you reach an agreement, say exactly: "Pleasure doing business with you" followed by the agreed price.
Example: "Pleasure doing business with you at $17"
```

**Group 1 - Seller Prompt:**
```
You are a skilled seller negotiating to sell a product. Your minimum acceptable price is [PRIVATE_VALUE].

Strategy:
- Start with a high asking price (around 140-150% of your minimum)
- Gradually lower in small decrements
- Emphasize product value

When you reach an agreement, say exactly: "Pleasure doing business with you" followed by the agreed price.
Example: "Pleasure doing business with you at $17"
```

5. Repeat for `test2@test.com` with similar prompts (can vary the wording)

### Option B: Upload prompts directly via Google Drive

The prompts are stored in Google Drive with filename format:
`Game{game_id}_Class{class}_Group{group_id}_{timestamp}.txt`

The file content should be:
```
[Buyer Prompt]#_;:)[Seller Prompt]
```

## Step 4: Run the Simulation

1. Log in as instructor
2. Go to **Control Panel** → **Run Simulation**
3. Select:
   - Academic Year: **2025**
   - Game: **Test Negotiation - Class T**
4. Make sure you see both groups listed (no missing submissions warning, or only partial)
5. Fill in simulation parameters:

| Parameter | Value |
|-----------|-------|
| API Key | [Your OpenAI API key] |
| Model | gpt-4o-mini |
| Number of Rounds | 1 |
| Conversation Starter | Buyer → Seller |
| Starting Message | Hello, shall we start the negotiation? |
| Maximum Number of Turns | 10 |
| Negotiation Termination Message | Pleasure doing business with you |
| Negotiation Summary Prompt | What was the value agreed? |
| Summary Termination Message | The value agreed was |

6. Click **"Run"**
7. Wait for completion (may take 1-2 minutes per match)

## Step 5: Verify Results

### Check Simulation Output
- Should show "All negotiations completed successfully!" or list any failed negotiations

### View Chat Transcripts
1. Go to **Control Panel** → **Game Data**
2. Select the test game
3. Click **"View Chats"**
4. You should see negotiation transcripts for each match

### Check Leaderboard
1. Go to **Control Panel** → **Leaderboard**
2. Select Academic Year: 2025
3. Select Game: Test Negotiation - Class T
4. Verify scores are displayed for both groups

### Enable Student Access (Optional)
1. In **Game Data** → **View Chats**
2. Click **"Enable Student Access to Negotiation Chats and Leaderboard"**
3. Now students can view results in the Play page

## Verification Checklist

- [ ] Test students created (at least 2 in different groups)
- [ ] Test game created with proper configuration
- [ ] Prompts submitted for all groups
- [ ] No "missing submissions" warning in Run Simulation
- [ ] Simulation runs without API errors
- [ ] Chat transcripts visible in Game Data → View Chats
- [ ] Scores appear in Leaderboard
- [ ] (Optional) Students can view results when access enabled

## Troubleshooting

### "Missing submissions" warning
- Ensure all students have submitted prompts via Playground
- Check that the prompts were uploaded correctly to Google Drive

### API errors during simulation
- Verify your OpenAI API key is valid
- Ensure you have sufficient credits/quota
- Try using gpt-4o-mini which is cheaper and faster

### No chat transcripts showing
- Check Google Drive for files starting with `Game{id}_Round`
- Verify the simulation completed without errors

### Scores not appearing in leaderboard
- Ensure the simulation completed successfully
- Check the `round` table in the database has entries

## Test Parameters Summary

| Parameter | Recommended Value |
|-----------|-------------------|
| Model | gpt-4o-mini (faster, cheaper) |
| Rounds | 1 (for quick testing) |
| Max Turns | 10 |
| Starter | Buyer → Seller |
| Termination | "Pleasure doing business with you" |
| Summary Termination | "The value agreed was" |
