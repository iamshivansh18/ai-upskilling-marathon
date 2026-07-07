import os
import re
import json

def update_leaderboard():
    comment = os.environ.get("COMMENT_BODY", "")
    author = os.environ.get("COMMENT_AUTHOR", "")
    issue_title = os.environ.get("ISSUE_TITLE", "Unknown Day")

    # 1. Verify this is an official Copilot Audit Receipt
    if "COPILOT AUDIT RECEIPT" not in comment:
        echo_log("Ignored comment: Does not contain official COPILOT AUDIT RECEIPT header.")
        return

    echo_log(f"Processing Copilot Audit Receipt from @{author} on '{issue_title}'...")

    # 2. Extract Score using forgiving Regex (handles bolding, brackets, and spacing variations)
    # Matches: "FINAL SCORE: [9] / 10", "**FINAL SCORE:** 8.5/10", "FINAL SCORE: 9/10", etc.
    score_match = re.search(r'FINAL\s+SCORE:\s*(?:\[|\**)?\s*(\d+(?:\.\d+)?)\s*(?:\]|\**)?\s*/\s*10', comment, re.IGNORECASE)
    
    # Matches: "Session Turn Count: [6]", "Session Turn Count: 4 turns", etc.
    turns_match = re.search(r'Session\s+Turn\s+Count:\s*(?:\[|\**)?\s*(\d+)\s*(?:\]|\**)?', comment, re.IGNORECASE)

    if not score_match:
        echo_log("❌ ERROR: Could not parse 'FINAL SCORE: X / 10' pattern from receipt.")
        return

    score = float(score_match.group(1))
    turns = int(turns_match.group(1)) if turns_match else 1

    # 3. Anti-Cheat Enforcement: Deduct 50% if direct paste detected or only 1 prompt turn used
    status_note = "✅ Verified Iterative Session"
    if "DIRECT PASTE DETECTED" in comment or turns <= 1:
        score = round(score * 0.5, 1)
        status_note = "⚠️ 50% Penalty Applied (Direct Paste / 1-Turn Session)"
        echo_log(f"⚠️ Anti-Cheat Triggered: @{author} submitted with turn count {turns} or Direct Paste flag.")

    # 4. Load or initialize the JSON database
    db_dir = "data"
    db_path = os.path.join(db_dir, "scores.json")
    os.makedirs(db_dir, exist_ok=True)

    scores = {}
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        with open(db_path, "r", encoding="utf-8") as f:
            try:
                scores = json.load(f)
            except json.JSONDecodeError:
                echo_log("⚠️ scores.json was corrupted. Resetting database structure.")

    # Initialize user if first time submitting
    if author not in scores:
        scores[author] = {
            "total_score": 0.0,
            "challenges_completed": 0,
            "history": []
        }

    # Avoid duplicate scoring: check if they already submitted for this specific issue today
    if any(entry.get("issue") == issue_title for entry in scores[author]["history"]):
        echo_log(f"ℹ️ @{author} has already been scored for '{issue_title}'. Updating score instead of duplicating...")
        # Remove previous attempt for this challenge
        old_entry = next(item for item in scores[author]["history"] if item["issue"] == issue_title)
        scores[author]["total_score"] = round(scores[author]["total_score"] - old_entry["score"], 1)
        scores[author]["history"] = [item for item in scores[author]["history"] if item["issue"] != issue_title]
    else:
        scores[author]["challenges_completed"] += 1

    # Add new score
    scores[author]["total_score"] = round(scores[author]["total_score"] + score, 1)
    scores[author]["history"].append({
        "issue": issue_title,
        "score": score,
        "turns": turns,
        "status": status_note
    })

    # Save database
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2)
    echo_log(f"✅ Successfully logged {score} points for @{author}.")

    # 5. Rebuild LEADERBOARD.md
    generate_markdown_leaderboard(scores)

def generate_markdown_leaderboard(scores):
    # Sort developers by total score descending
    sorted_users = sorted(scores.items(), key=lambda x: x[1]["total_score"], reverse=True)

    md = "# 🏆 AI Upskilling Marathon Leaderboard\n\n"
    md += "Welcome to the live scoreboard! Submit your Copilot Audit Receipts in the daily challenge issues to climb the ranks.\n\n"
    md += "| Rank | Developer | Total Score | Completed | Avg Score | Latest Status |\n"
    md += "|---|---|---|---|---|---|\n"

    for idx, (user, data) in enumerate(sorted_users):
        rank_num = idx + 1
        
        # Add podium medals for top 3
        if rank_num == 1:
            rank_display = "🥇 **#1**"
        elif rank_num == 2:
            rank_display = "🥈 **#2**"
        elif rank_num == 3:
            rank_display = "🥉 **#3**"
        else:
            rank_display = f"**#{rank_num}**"

        avg_score = round(data["total_score"] / max(1, data["challenges_completed"]), 1)
        latest_status = data["history"][-1]["status"] if data["history"] else "N/A"

        md += f"| {rank_display} | `@user_{user}` | **{data['total_score']} pts** | {data['challenges_completed']} | {avg_score} | {latest_status} |\n"

    with open("LEADERBOARD.md", "w", encoding="utf-8") as f:
        f.write(md)
    echo_log("🏆 LEADERBOARD.md has been regenerated!")

def echo_log(message):
    print(f"[Leaderboard Bot] {message}")

if __name__ == "__main__":
    update_leaderboard()
