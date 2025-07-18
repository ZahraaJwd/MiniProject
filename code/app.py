from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from datetime import datetime, date
from functools import wraps
from database import get_connection
from rule_based_engine import rule_based_engine
from ai_agent import ai_agent

app = Flask(__name__)
app.secret_key = "s3cr3t_k3y_12345"

@app.route("/")
def home():
    return render_template("index.html")

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'employee_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper

@app.route("/request", methods=["GET"])
def request_form():
    if "employee_id" not in session:
        return redirect(url_for("login"))
    today = date.today().isoformat()
    return render_template("request.html", today=today)    

@app.route("/login-success")
def login_success():
    if "employee_id" not in session:
        return redirect(url_for("login"))
    return render_template("login_success.html")

@app.route("/dashboard")
def dashboard():
    if "employee_id" not in session:
        return redirect(url_for("login"))

    employee_id = session["employee_id"]
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name, employee_role FROM employees WHERE id = ?", (employee_id,))
    row = cursor.fetchone()
    employee_name = row[0] if row else "Unknown"
    employee_role = row[1] if row else "Unknown"

    cursor.close()
    conn.close()
    
    return render_template("employee_dashboard.html", 
                           employee_name=employee_name,
                           employee_role=employee_role)

@app.route("/account")
def account():
    if "employee_id" not in session:
        return redirect(url_for("login"))
    
    employee_id = session["employee_id"]
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name, username, employee_role FROM employees WHERE id = ?", (employee_id,))
    row = cursor.fetchone()
    employee_name = row[0] if row else "Unknown"
    employee_username = row[1] if row else "Unknown"
    employee_role = row[2] if row else "Unknown"
    
    cursor.close()
    conn.close()
    
    return render_template("account.html", 
                           employee_name=employee_name, 
                           employee_username= employee_username,
                           employee_role=employee_role)

@app.route("/work_info")
def work_info():
    if "employee_id" not in session:
        return redirect(url_for("login"))

    employee_id = session["employee_id"]
    conn = get_connection()
    cursor = conn.cursor()

    # Get employee name, role, and team
    cursor.execute("SELECT name, team_name, employee_role FROM employees WHERE id = ?", (employee_id,))
    row = cursor.fetchone()
    columns = [col[0] for col in cursor.description]
    employee = dict(zip(columns, row)) if row else {"name": "Unknown", "team_name": "Unknown", "employee_role": "Unknown"}

    # Get team projects
    cursor.execute("""
        SELECT project_name, deadline_date
        FROM project_deadlines
        WHERE team = ?
        ORDER BY deadline_date ASC
    """, (employee["team_name"],))
    
    # Convert result to list of dictionaries
    columns = [col[0] for col in cursor.description]
    projects = [dict(zip(columns, row)) for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return render_template("work_info.html",
                           employee_name=employee["name"],
                           team_name=employee["team_name"],
                           employee_role=employee["employee_role"],
                           projects=projects)



#login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        conn = get_connection()
        if conn is None:
            return "Failed to connect to database", 500

        
        cursor = conn.cursor()

        query = "SELECT * FROM employees WHERE userName = ? AND password = ?"
        cursor.execute(query, (username, password))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if row:
            session["employee_id"] = row[0]
            #return render_template("request.html")
            #return redirect(url_for("request_form"))
            return redirect(url_for("login_success"))
        else:
            flash("Incorrect name or password")
            return redirect(url_for("login"))

    return render_template("index.html")


#submit request
@app.route('/submit-request', methods=['POST'])
@login_required
def submit_request():
    employee_id = session.get('employee_id')
    if not employee_id:
        return redirect('/login')
    
    # 1. Get data from form
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    leave_type = request.form['leave_type']
    #reason = request.form['reason']

    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
    requested_days = (end_date_obj - start_date_obj).days + 1
    notice_days = (start_date_obj - datetime.today()).days

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM employees WHERE id = ?", (employee_id,))
    employee = cursor.fetchone()
    employee_name = employee[0] if employee else "Unknown"

    # A. Get employee's team
    cursor.execute("SELECT team_name FROM employees WHERE id = ?", (employee_id,))
    team_name = cursor.fetchone()[0]

    # B. Get teammates on leave during this period
    cursor.execute("""
        SELECT COUNT(DISTINCT e.id)
        FROM leave_requests lr
        JOIN employees e ON lr.employee_id = e.id
        WHERE e.team_name = ?
          AND lr.rule_decision = 'Accept'
          AND lr.start_date <= ? AND lr.end_date >= ?
    """, (team_name, end_date, start_date))
    
    team_on_leave = cursor.fetchone()[0]

    # C. Get employee's used leave days this year
    cursor.execute("""
        SELECT SUM(DATEDIFF(DAY, start_date, end_date) + 1)
        FROM leave_requests
        WHERE employee_id = ?
          AND rule_decision = 'Accept'
          AND YEAR(start_date) = YEAR(GETDATE())
    """, (employee_id,))
    
    used_days = cursor.fetchone()[0] or 0

    # D. Check for project deadline conflict
    cursor.execute("""
        SELECT COUNT(*) FROM project_deadlines
        WHERE team = ?
          AND deadline_date BETWEEN ? AND ?
    """, (team_name, start_date, end_date))
    deadline_conflict = cursor.fetchone()[0] > 0

    # 3. Run Rule-Based Engine
    rule_result = rule_based_engine({
        "team_on_leave": team_on_leave,
        "has_deadline_conflict": deadline_conflict,
        "used_annual_leave": used_days,
        "notice_days": notice_days,
        "leave_requested_days": requested_days,
        "reason": leave_type
    })

    # 4. Run ML Engine
    ml_result = ai_agent({
       "team_on_leave": team_on_leave,
        "has_deadline_conflict": deadline_conflict,
        "used_annual_leave": used_days,
        "notice_days": notice_days,
        "leave_requested_days": requested_days,
        "reason": leave_type
    })

    # 5. Store Leave Request and Decisions in DB
    cursor.execute("""
        INSERT INTO leave_requests (
            employee_id, start_date, end_date, reason,
            rule_decision, rule_reason,
            ml_decision, ml_reason
            
        ) VALUES (?, ?, ?, ?, ?, ?, ? ,?)
    """, (
        employee_id, start_date, end_date, leave_type,
        rule_result['decision'], rule_result['reason'],
        ml_result['decision'], ml_result['explanation']
    ))
    conn.commit()



    # 6. Close DB and return result page
    cursor.close()
    conn.close()

    return render_template("decision_results.html",
        rule=rule_result,
        ml=ml_result,
        employee_name=employee_name,
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        requested_days = requested_days
    )


@app.route("/update-account", methods=["POST"])
def update_account():
    if "employee_id" not in session:
        return redirect(url_for("login"))

    employee_id = session["employee_id"]
    new_username = request.form.get("usernameInput")
    current_password = request.form.get("currentPassword")
    new_password = request.form.get("newPassword")
    confirm_password = request.form.get("confirmPassword")

    conn = get_connection()
    cursor = conn.cursor()

    # Get current user info
    cursor.execute("SELECT userName, password FROM employees WHERE id = ?", (employee_id,))
    row = cursor.fetchone()
    columns = [col[0] for col in cursor.description]
    employee = dict(zip(columns, row)) if row else {}

    # Update username if provided
    if new_username:
        try:
            cursor.execute("UPDATE employees SET userName = ? WHERE id = ?", (new_username, employee_id))
            session["employee_username"] = new_username
            flash("Username updated successfully", "success")
        except Exception:
            flash("⚠️ Could not update username. Make sure it's unique.", "danger")

    # Update password if all fields are filled
    if current_password and new_password and confirm_password:
        if current_password != employee.get("password"):
            flash("❌ Current password is incorrect", "danger")
        elif new_password != confirm_password:
            flash("❌ New password and confirmation do not match", "danger")
        else:
            cursor.execute("UPDATE employees SET password = ? WHERE id = ?", (new_password, employee_id))
            flash("Password updated successfully", "success")

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("account"))

@app.route("/past-requests")
def past_requests():
    if "employee_id" not in session:
        return redirect(url_for("login"))

    employee_id = session["employee_id"]
    conn = get_connection()
    cursor = conn.cursor()

    # Get employee name and role
    cursor.execute("SELECT name, employee_role FROM employees WHERE id = ?", (employee_id,))
    row = cursor.fetchone()
    columns = [col[0] for col in cursor.description]
    employee = dict(zip(columns, row)) if row else {"name": "Unknown", "employee_role": "Unknown"}

    # Get past leave requests
    cursor.execute("""
        SELECT id, request_date, DATEDIFF(DAY, start_date, end_date) + 1 AS leave_days,
               rule_decision, rule_reason, ml_decision, ml_reason
        FROM leave_requests
        WHERE employee_id = ?
        ORDER BY request_date DESC
    """, (employee_id,))
    columns = [col[0] for col in cursor.description]
    past_requests = [dict(zip(columns, row)) for row in cursor.fetchall()]

    total_requests = len(past_requests)

    # Total approved leave days this year
    current_year = datetime.now().year
    cursor.execute("""
        SELECT SUM(DATEDIFF(DAY, start_date, end_date) + 1) AS total_days
        FROM leave_requests
        WHERE employee_id = ?
        AND rule_decision = 'Accept'
        AND YEAR(request_date) = ?
    """, (employee_id, current_year))
    total_days_result = cursor.fetchone()
    total_leave_days = total_days_result[0] if total_days_result and total_days_result[0] is not None else 0

    cursor.close()
    conn.close()

    return render_template("past_requests.html",
                           employee_name=employee["name"],
                           employee_role=employee["employee_role"],
                           past_requests=past_requests,
                           total_requests=total_requests,
                           total_leave_days=total_leave_days,
                           current_year=current_year)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)