import os
import re
import json
import hashlib

def update_leaderboard():
    comment = os.environ.get("COMMENT_BODY", "")
    author = os.environ.get("COMMENT_AUTHOR", "")
    issue_title = os.environ.get("ISSUE_TITLE", "Unknown Day")

    # 1. Verify this is an official Copilot Audit Receipt
    if "COPILOT AUDIT RECEIPT" not in comment:
        echo_log("Ignored comment: Does not contain official COPILOT AUDIT RECEIPT header.")
        return

    echo_log(f"Processing Copilot Audit Receipt from @{author} on '{issue_title}'...")

    # 2. Extract Score and Turns
    score_match = re.search(r'FINAL\s+SCORE:\s*(?:\[|\**)?\s*(\d+(?:\.\d+)?)\s*(?:\]|\**)?\s*/\s*10', comment, re.IGNORECASE)
    turns_match = re.search(r'Session\s+Turn\s+Count:\s*(?:\[|\**)?\s*(\d+)\s*(?:\]|\**)?', comment, re.IGNORECASE)

    if not score_match:
        echo_log("❌ ERROR: Could not parse 'FINAL SCORE: X / 10' pattern from receipt.")
        return

    score = float(score_match.group(1))
    turns = int(turns_match.group(1)) if turns_match else 1

    # 3. Extract Unique DNA (Core Artifact + First Stumble) for Deduplication
    artifact_match = re.search(r'Core\s+Artifact:\s*(.+)', comment, re.IGNORECASE)
    stumble_match = re.search(r'My\s+First\s+Stumble:\s*(.+)', comment, re.IGNORECASE)

    if artifact_match and stumble_match:
        # Create a unique fingerprint string from their specific coding artifact and mistake
        fingerprint_raw = f"{artifact_match.group(1).strip()} || {stumble_match.group(1).strip()}".lower()
    else:
        # Fallback: If formatting varied, strip dates, timestamps, usernames, and issue titles to hash the raw body
        cleaned_body = re.sub(r'(\d{4}[-/.]\d{2}[-/.]\d{2}|\d+\s+prompts?|user_\w+)', '', comment, flags=re.IGNORECASE)
        fingerprint_raw = cleaned_body.strip().lower()

    fingerprint_hash = hashlib.md5(fingerprint_raw.encode('utf-8')).hexdigest()

    # 4. Load or initialize Database
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

    # 5. GLOBAL DEDUPLICATION CHECK (Blocks Replay Attacks & Copy-Pasting)
    for existing_user, user_data in scores.items():
        for entry in user_data.get("history", []):
            if entry.get("fingerprint") == fingerprint_hash:
                if existing_user == author and entry.get("issue") != issue_title:
                    echo_log(f"🚨 REPLAY ATTACK BLOCKED: @{author} already used this exact Copilot receipt on '{entry['issue']}'. Zero points awarded!")
                    return
                elif existing_user != author:
                    echo_log(f"🚨 PLAGIARISM BLOCKED: @{author} submitted a receipt identical to one already submitted by @{existing_user}! Zero points awarded!")
                    return

    # 6. Anti-Cheat Penalty (Direct Paste / Low Turn Count)
    status_note = "✅ Verified Iterative Session"
    if "DIRECT PASTE DETECTED" in comment or turns <= 1:
        score = round(score * 0.5, 1)
        status_note = "⚠️ 50% Penalty (Direct Paste / 1-Turn Session)"
        echo_log(f"⚠️ Anti-Cheat Triggered: @{author} submitted with turn count {turns} or Direct Paste flag.")

    # 7. Log or Update Score
    if author not in scores:
        scores[author] = {
            "total_score": 0.0,
            "challenges_completed": 0,
            "history": []
        }

    # Check if they are updating an existing submission for THIS specific challenge today
    existing_issue_idx = next((i for i, item in enumerate(scores[author]["history"]) if item["issue"] == issue_title), None)
    
    if existing_issue_idx is not None:
        echo_log(f"ℹ️ @{author} is updating their previous submission for '{issue_title}'...")
        old_entry = scores[author]["history"][existing_issue_idx]
        scores[author]["total_score"] = round(scores[author]["total_score"] - old_entry["score"] + score, 1)
        scores[author]["history"][existing_issue_idx] = {
            "issue": issue_title,
            "score": score,
            "turns": turns,
            "status": status_note,
            "fingerprint": fingerprint_hash
        }
    else:
        scores[author]["challenges_completed"] += 1
        scores[author]["total_score"] = round(scores[author]["total_score"] + score, 1)
        scores[author]["history"].append({
            "issue": issue_title,
            "score": score,
            "turns": turns,
            "status": status_note,
            "fingerprint": fingerprint_hash
        })

    # Save Database
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2)
    echo_log(f"✅ Successfully logged {score} points for @{author}.")

    # 8. Rebuild LEADERBOARD.md
    generate_markdown_leaderboard(scores)

def generate_markdown_leaderboard(scores):
    sorted_users = sorted(scores.items(), key=lambda x: x[1]["total_score"], reverse=True)

    md = "# 🏆 AI Upskilling Marathon Leaderboard\n\n"
    md += "Welcome to the live scoreboard! Submit your Copilot Audit Receipts in the daily challenge issues to climb the ranks.\n\n"
    md += "| Rank | Developer | Total Score | Completed | Avg Score | Latest Status |\n"
    md += "|---|---|---|---|---|---|\n"

    for idx, (user, data) in enumerate(sorted_users):
        rank_num = idx + 1
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
