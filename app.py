from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = "pensioner_benefits_portal_secret_key_2004"

PORTAL_PASSWORD = "Anagha$2004"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("authenticated"):
            if request.is_json:
                return jsonify({"success": False, "error": "Unauthorized. Please log in."}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def parse_date(date_str: str):
    """Parse date from DD.MM.YYYY format."""
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")


def calculate_service(doj: date, dor: date):
    """Calculate total service between date of joining and date of retirement."""
    delta = relativedelta(dor, doj)
    years = delta.years
    months = delta.months
    days = delta.days
    return years, months, days


def total_half_yearly_periods(years: int, months: int, days: int) -> int:
    """
    Total half-yearly periods:
    - Base periods = years * 2
    - If remaining service is > 9 months (or 9 months with any days), adds 2 periods
    - Else if remaining service is > 3 months (or 3 months with any days), adds 1 period
    - Else adds 0 periods
    - Maximum limit is 66 periods (capped at 33 years).
    """
    extra_periods = 0
    if months > 9 or (months == 9 and days > 0):
        extra_periods = 2
    elif months > 3 or (months == 3 and days > 0):
        extra_periods = 1

    periods = (years * 2) + extra_periods
    return min(periods, 66)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == PORTAL_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("index"))
        else:
            error = "Incorrect password. Please try again."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/calculate", methods=["POST"])
@login_required
def calculate():
    try:
        data = request.get_json()

        # --- Parse Inputs ---
        dob_str = data.get("dob", "")
        doj_str = data.get("doj", "")
        dor_str = data.get("dor", "")
        basic_pay = float(data.get("basic_pay", 0))
        da_rate = float(data.get("da_rate", 0))  # percentage e.g. 66
        commutation_factor = float(data.get("commutation_factor", 0))
        el_days = int(data.get("el_days", 0))
        hpl_days = int(data.get("hpl_days", 0))

        # Parse dates
        dob = parse_date(dob_str)
        doj = parse_date(doj_str)
        dor = parse_date(dor_str)

        # --- Row 04: Total Service Rendered (Row 2 → Row 3) ---
        years, months, days = calculate_service(doj, dor)
        service_str = f"{years} yrs, {months} months & {days} days"

        # --- Row 05: Total Half Yearly Period ---
        half_yearly = total_half_yearly_periods(years, months, days)

        # --- Row 08: Pension Admissible Before Commutation (Basic Pay / 2) ---
        pension_before_commutation = round(basic_pay / 2, 2)

        # --- Row 09: Pension Commutation (40% of Row 8) ---
        pension_commutation = round(pension_before_commutation * 0.40, 2)

        # --- Row 10: Pension After Commutation (Row 8 - Row 9) ---
        pension_after_commutation = round(
            pension_before_commutation - pension_commutation, 2
        )

        # --- Row 11: Family Pension ---
        family_pension_ordinary = round(basic_pay * 0.30, 2)   # 30% of Basic Pay
        family_pension_higher = round(basic_pay * 0.50, 2)     # 50% of Basic Pay

        # --- Row 12: Total Pension with DR ---
        dr_on_higher = round((da_rate / 100.0) * family_pension_higher, 2)
        total_pension_dr = round(family_pension_ordinary + dr_on_higher, 2)

        # --- Row 13: Retirement Gratuity ---
        # Formula: (Basic Pay + (Basic Pay * DA%)) * 1/4 * Total Half Yearly Period
        # Maximum limit: Rs. 25,00,000/-
        emoluments = basic_pay + (basic_pay * (da_rate / 100.0))
        raw_gratuity = emoluments * 0.25 * half_yearly
        retirement_gratuity = min(round(raw_gratuity, 2), 2500000.0)

        # --- Row 15: Commuted Value of Pension (CVP) ---
        # Formula: Pension Commutation * Commutation Table Applicable * 12
        commuted_value_pension = round(pension_commutation * commutation_factor * 12, 2)

        # --- Row 18: EL Encashment ---
        # Formula: (Basic Pay + (Basic Pay * DA%)) * (1/30) * Total days of EL at credit
        el_encashment = round(emoluments * (1.0 / 30.0) * el_days, 2)

        return jsonify(
            {
                "success": True,
                "service_str": service_str,
                "service_years": years,
                "service_months": months,
                "service_days": days,
                "half_yearly": half_yearly,
                "pension_before_commutation": pension_before_commutation,
                "pension_commutation": pension_commutation,
                "pension_after_commutation": pension_after_commutation,
                "family_pension_ordinary": family_pension_ordinary,
                "family_pension_higher": family_pension_higher,
                "dr_on_higher": dr_on_higher,
                "total_pension_dr": total_pension_dr,
                "retirement_gratuity": retirement_gratuity,
                "commuted_value_pension": commuted_value_pension,
                "el_encashment": el_encashment,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)

