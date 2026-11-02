import io
import re
from urllib.parse import quote
from datetime import date, datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, make_response
from dateutil.relativedelta import relativedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

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
    """Parse date from various string formats."""
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


def get_pdf_filename(pensioner_name: str) -> str:
    cleaned = pensioner_name.strip()
    cleaned = re.sub(r'[\\/*?:"<>|]', '', cleaned)
    if cleaned:
        return f"{cleaned} Pension Details.pdf"
    return "Pension Details.pdf"


def generate_pdf_report(payload: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=30,
        rightMargin=30,
        topMargin=26,
        bottomMargin=26
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#0F2545')
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#4B5563')
    )

    meta_left = ParagraphStyle(
        'MetaLeft',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#111827')
    )

    meta_right = ParagraphStyle(
        'MetaRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#374151')
    )

    th_sl = ParagraphStyle('TH_SL', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.white)
    th_part = ParagraphStyle('TH_PART', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white)
    th_val = ParagraphStyle('TH_VAL', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_RIGHT, textColor=colors.white)

    td_sl = ParagraphStyle('TD_SL', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.HexColor('#374151'))
    td_part = ParagraphStyle('TD_PART', fontName='Helvetica-Bold', fontSize=8, leading=10.5, textColor=colors.HexColor('#111827'))
    td_val = ParagraphStyle('TD_VAL', fontName='Helvetica-Bold', fontSize=8, leading=10.5, alignment=TA_RIGHT, textColor=colors.black)

    sec_style = ParagraphStyle('SEC', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#0F2545'))

    story = []

    # Title & Subtitle
    story.append(Paragraph("PENSIONARY BENEFITS STATEMENT", title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Government Pension & Retirement Benefit Computation System", subtitle_style))
    story.append(Spacer(1, 8))

    # Meta Table
    pensioner_name = payload.get("pensioner_name", "").strip() or "—"
    generation_date = payload.get("generation_date", "").strip() or datetime.now().strftime("%d-%m-%Y")

    meta_table = Table([
        [Paragraph(f"<b>Pensioner Name:</b> {pensioner_name}", meta_left),
         Paragraph(f"<b>Date of Generation:</b> {generation_date}", meta_right)]
    ], colWidths=[335, 200])

    meta_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1.2, colors.HexColor('#0F2545')),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # Table Data
    rows = payload.get("rows", [])
    table_data = [
        [Paragraph("Sl. No.", th_sl), Paragraph("Particulars", th_part), Paragraph("Amount / Date", th_val)]
    ]

    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F2545')),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
    ]

    current_idx = 1
    for r in rows:
        if r.get("is_section"):
            table_data.append([Paragraph(r['title'].upper(), sec_style), "", ""])
            table_styles.append(('SPAN', (0, current_idx), (2, current_idx)))
            table_styles.append(('BACKGROUND', (0, current_idx), (2, current_idx), colors.HexColor('#F3F4F6')))
            table_styles.append(('TOPPADDING', (0, current_idx), (2, current_idx), 3))
            table_styles.append(('BOTTOMPADDING', (0, current_idx), (2, current_idx), 3))
        else:
            sl = r.get("sl", "")
            part = r.get("particulars", "")
            val = r.get("val", "")
            table_data.append([
                Paragraph(sl, td_sl),
                Paragraph(part, td_part),
                Paragraph(val, td_val)
            ])
            if r.get("is_profile"):
                table_styles.append(('BACKGROUND', (0, current_idx), (2, current_idx), colors.HexColor('#F9FAFB')))
        current_idx += 1

    content_table = Table(table_data, colWidths=[42, 328, 165])
    content_table.setStyle(TableStyle(table_styles))
    story.append(content_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


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

        # --- Row 11: Family Pension Admissible ---
        # Ordinary = 30% of Basic Pay at retirement
        # Higher Rate = 50% of Basic Pay at retirement
        family_pension_ordinary = round(basic_pay * 0.30, 2)
        family_pension_higher = round(basic_pay * 0.50, 2)

        # --- Row 12: Total Pension with DR ---
        # Higher Rate is 50% of Basic Pay at Time of Retirement
        # DR on Higher Rate = DA% * Higher Rate (50% of Basic Pay)
        # Total Pension with DR = Ordinary Rate + DR on Higher Rate
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


@app.route("/export-pdf", methods=["POST"])
@login_required
def export_pdf():
    try:
        data = request.get_json() or {}
        pdf_bytes = generate_pdf_report(data)
        name = data.get("pensioner_name", "").strip()
        filename = get_pdf_filename(name)

        response = make_response(pdf_bytes)
        response.headers["Content-Type"] = "application/pdf"
        quoted_filename = quote(filename)
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quoted_filename}'
        return response
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
