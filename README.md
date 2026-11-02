# Pensionary Benefits Calculator

A web-based pension benefit computation tool built with **Python (Flask)** and **HTML**.

## Project Structure
```
pensioner_benifits/
├── app.py               ← Flask backend + calculation logic
├── requirements.txt     ← Python dependencies
└── templates/
    └── index.html       ← Frontend UI
```

## Setup & Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server
python app.py

# 3. Open in browser
http://localhost:5000
```

## Features (v1)
- Manual entry for: DOB, Date of Joining, Date of Retirement, Basic Pay, DA Rate
- Auto-calculated: Total Service, Half-Yearly Periods, All Pension figures
- Print / Export support
- Live validation with toast notifications
