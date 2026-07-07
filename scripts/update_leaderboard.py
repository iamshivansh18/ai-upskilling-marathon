import os
import re
import json

def update():
    comment = os.environ.get("COMMENT_BODY", "")
    author = os.environ.get("COMMENT_AUTHOR", "")

    # 1. Ignore comments that are not official Copilot Audit Receipts
    if "COPILOT AUDIT RECEIPT" not in comment:
        return

    # 2. Extract score and session turns using Regex
    score_match = re.search(r'FINAL SCORE:\s*\[?(\d+(?:\.\d+)?)\]?\s*/\s*10', comment)
    turns_match = re.search(r'Session Turn Count:\s*\[?(\d+)\]?', comment)
    
    if not score_match:
        return

    score = float(score_match.group(1))
    turns = int(turns_match.group(1)) if turns_match else 1

    # 3. Anti-Cheat Enforcement: Deduct 50% if direct paste is detected or turn count <= 1
    if "DIRECT PASTE DETECTED" in comment or turns <= 1:
        score = round(score * 0.5, 1)

    # 4. Update JSON database
    db_path = "data/scores.json"
    with open(db_path, "r") as f:
        scores = json.load(f)

    if author not in scores:
        scores[author] = {"total_score": 0.0, "challenges_completed": 0}

    scores[author]["total_score"] = round(scores[author]["total_score"] + score, 1)
    scores[author]["challenges_completed"] += 1

    with open(db_path, "w") as f:
        json.dump(scores, f, indent=2)

    # 5. Generate clean LEADERBOARD.md
    sorted_users = sorted(scores.items(), key=lambda x: x[1]["total_score"], reverse=True)
    
    md = "# 🏆 AI Upskilling Marathon Leaderboard\n\n"
    md += "| Rank | Developer | Total Score | Challenges Completed | Avg Score |\n"
    md += "|---|---|---|---|---|\n"
    
    for rank, (user, data) in enumerate(sorted_users, 1):
        avg = round(data["total_score"] / max(1, data["challenges_completed"]), 1)
        md += f"| **#{rank}** | `@user_{user}` | **{data['total_score']} pts** | {data['challenges_completed']} | {avg} |\n"

    with open("LEADERBOARD.md", "w") as f:
        f.write(md)

if __name__ == "__main__":
    update()
