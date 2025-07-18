# rule_based_engine.py

def rule_based_engine(data):
    team_on_leave = data["team_on_leave"]
    has_deadline_conflict = data["has_deadline_conflict"]
    used_annual_leave = data["used_annual_leave"]
    notice_days = data["notice_days"]
    leave_requested_days = data["leave_requested_days"]
    reason = data["reason"].lower()

    if leave_requested_days >=7:
        return{
            "decision": "Reject",
            "reason": f"Requested days are {leave_requested_days} which exceeded the limit."
        }

    # Rule: Max annual leave exceeded
    if used_annual_leave >= 15:
        return {
            "decision": "Reject",
            "reason": "Annual leave limit exceeded."
        }

    # Rule: Emergency or medical leave
    if "emergency" in reason or "sick" in reason:
        return {
            "decision": "Accept",
            "reason": "Approved due to emergency or sick leave."
        }

    # Rule: Too many teammates already on leave
    if team_on_leave >= 3:
        return {
            "decision": "Reject",
            "reason": f"{team_on_leave} team members already on leave. Team availability is low."
        }

    # Rule: Project deadline conflict
    if has_deadline_conflict:
        return {
            "decision": "Reject",
            "reason": "Leave overlaps with a project deadline."
        }

    # Rule: Short notice
    if notice_days < 2:
        return {
            "decision": "Reject",
            "reason": "Leave request submitted on short notice."
        }

    # Default: Approve
    return {
        "decision": "Accept",
        "reason": "No conflicts detected. Leave approved."
    }
