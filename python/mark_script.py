import os
import sys
import subprocess
import ollama
import json
from pydantic import BaseModel, Field

# ---------------------------------------------------------
# 1. PARAMETERS & CONFIGURATION
# ---------------------------------------------------------
BASE_BRANCH = "origin/main"          # The baseline template branch to compare against
TARGET_FILE = "todo.py"    # The exact script name they are editing
OLLAMA_MODEL = "qwen2.5:1.5b"        # Optimized lightweight model for CPU runners

# ---------------------------------------------------------
# 2. DEFINITIONS & SCHEMAS
# ---------------------------------------------------------
class HumanFeedbackSchema(BaseModel):
    what_went_well: str = Field(
        description="A short, encouraging paragraph highlighting what the student did well regarding their coding style, variable choices, comments, and git commit history."
    )
    areas_for_improvement: str = Field(
        description="A short, constructive paragraph detailing specific areas where the student can improve their coding style, naming conventions, commenting efficiency, or git workflow."
    )

SYSTEM_INSTRUCTION = """
You are a supportive, insightful University Computer Science tutor providing rapid, constructive feedback on a programming assignment. 
Review the student's code, naming choices, commenting style, and git revision history. 

Provide your evaluation in a conversational, human tone, broken down strictly into two specific areas:
1. What they did well.
2. Concrete areas where they can improve.

Keep the tone encouraging yet candid. Do not reference strict rubric grids, bands, or percentages.
"""

def run_cmd(args):
    res = subprocess.run(args, capture_output=True, text=True)
    if res.returncode != 0:
        return ""
    return res.stdout.strip()

def main():
    print(f"🤖 Initializing Local AI Evaluation for '{TARGET_FILE}'...")
    
    if not os.path.exists(TARGET_FILE):
        print(f"❌ Error: Target file '{TARGET_FILE}' not found.")
        sys.exit(1)
        
    with open(TARGET_FILE, "r") as f:
        full_code = f.read()
        
    # --- ROBUST GIT FETCH FALLBACKS ---
    student_diff = run_cmd(["git", "diff", f"{BASE_BRANCH}...HEAD", "--", TARGET_FILE])
    if not student_diff:
        student_diff = run_cmd(["git", "diff", "main...HEAD", "--", TARGET_FILE])
        
    git_history = run_cmd(["git", "log", f"{BASE_BRANCH}..HEAD", "--pretty=format:[%h] %s", "--stat"])
    if not git_history:
        git_history = run_cmd(["git", "log", "main..HEAD", "--pretty=format:[%h] %s", "--stat"])
    # ----------------------------------
        
    if not student_diff.strip() and not git_history.strip():
        print("\n## 🎓 Instant Feedback Report")
        print("⚠️ **No changes detected.** You haven't made any modifications or commits yet compared to the assignment baseline template.")
        return
        
    user_payload = f"""
    [FULL CODE STATE AT STUDENT BRANCH HEAD]
    {full_code}

    [STUDENT UNIQUE CODE CHANGES (DIFF)]
    {student_diff}

    [STUDENT REVISION HISTORY TRAIL]
    {git_history}
    """
    
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_payload},
            ],
            options={"temperature": 0.2}, # Slightly raised to sound less robotic
            format=HumanFeedbackSchema.model_json_schema()
        )
        
        raw_content = response['message']['content'].strip()
        
        # --- JSON LEAK PREVENTION ---
        import re
        json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        clean_json_string = json_match.group(0) if json_match else raw_content
        # -----------------------------

        # Hydrate JSON string into the schema
        try:
            feedback = HumanFeedbackSchema.model_validate_json(clean_json_string)
            www = feedback.what_went_well
            afi = feedback.areas_for_improvement
        except Exception:
            # Simple fallback parser if structural verification hits an edge case
            fallback_data = json.loads(clean_json_string)
            www = fallback_data.get("what_went_well", "Great effort on progressing the codebase structure.")
            afi = fallback_data.get("areas_for_improvement", "Continue refactoring naming conventions and refining commit logs.")

        # RENDER HUMAN MARKDOWN REVIEWS
        print("\n## 🎓 Instant Code Feedback Report\n")
        print("### 🌟 What You Did Well")
        print(www)
        print("\n### 🚀 Areas for Improvement")
        print(afi)
        
    except Exception as model_err:
        print(f"❌ Model analysis failed to validate. Error detail: {model_err}", file=sys.stderr)
        sys.exit(1)
        
if __name__ == "__main__":
    main()
