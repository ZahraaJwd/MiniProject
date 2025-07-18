import subprocess

def ask_model(prompt, model="qwen3:1.7b"):
    command = ['ollama', 'run', model]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8'
    )
    try:
        stdout, stderr = process.communicate(input=prompt, timeout=120)

        if stderr.strip():
            print("⚠️ stderr:", stderr.strip())

        return stdout.strip()

    except subprocess.TimeoutExpired:
        process.kill()
        return "Timeout"

def extract_clean_explanation(raw_output: str) -> str:
    """
    Extract the explanation text after the marker '...done thinking.'
    """
    marker = "...done thinking."
    if marker in raw_output:
        return raw_output.split(marker, 1)[1].strip()
    else:
        return raw_output.strip()

def ai_agent(leave_data):
    # Step 1: Prompt for decision
    decision_prompt = f"""
You are an AI leave approval system.

Reply with only one word: Accept or Reject.

Rules:
- Reject if requested leave days > annual leave balance.
- Reject if the team is already on leave.
- Reject if there's a deadline conflict.
- Accept only if none of the above apply.

Input:
- Reason: {leave_data['reason']}
- Team on leave: {'Yes' if leave_data['team_on_leave'] else 'No'}
- Deadline conflict: {'Yes' if leave_data['has_deadline_conflict'] else 'No'}
- Annual leave balance: {leave_data['used_annual_leave']} days
- Notice period: {leave_data['notice_days']} days
- Requested leave days: {leave_data['leave_requested_days']}
"""

    decision_raw = ask_model(decision_prompt).lower()
    if "accept" in decision_raw:
        decision = "Accept"
        explanation = "The leave request meets all policy requirements." 
    elif "reject" in decision_raw:
        decision = "Reject"

        # Step 2: Explanation prompt (only if rejected)
        explanation_prompt = f"""
A leave request was rejected based on company policy.

Make sure your explanation is based only on one or more of the following rules:
- Requested leave days must be 7 or less
- Annual leave usage must not exceed 15 days
- No more than 3 team members can be on leave
- No deadline conflict allowed
- Must give at least 3 days’ notice
- Automatically accept if reason is "sick" or "emergency"

Explain in 1–2 sentences why this leave request was rejected. Be clear and concise.

Input:
- Reason: {leave_data['reason']}
- Team on leave: {'Yes' if leave_data['team_on_leave'] else 'No'}
- Deadline conflict: {'Yes' if leave_data['has_deadline_conflict'] else 'No'}
- Annual leave balance: {leave_data['used_annual_leave']} days
- Notice period: {leave_data['notice_days']} days
- Requested leave days: {leave_data['leave_requested_days']}
"""

        raw_explanation = ask_model(explanation_prompt)
        explanation = extract_clean_explanation(raw_explanation)
    else:
        return {
            "decision": "Unknown",
            "explanation": "The model could not determine a valid decision."
        }

    return {
        "decision": decision,
        "explanation": explanation
    }