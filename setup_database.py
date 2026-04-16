"""
setup_database.py
Creates clinic.db with 5 tables and seeds realistic dummy data.
Deterministic output via random.seed(42) + Faker(seed=42).
"""

import os
import random
import sqlite3
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from faker import Faker

load_dotenv()

DB_PATH = os.getenv("DATABASE_PATH", "clinic.db")
random.seed(42)
fake = Faker()
Faker.seed(42)

# ── Schema constants ──────────────────────────────────────────────────────────

SPECIALIZATIONS = ["Dermatology", "Cardiology", "Orthopedics", "General", "Pediatrics"]

DOCTORS = [
    ("Dr. Sarah Mitchell",   "Dermatology",  "Skin & Aesthetics",    "555-0101"),
    ("Dr. James Okafor",     "Dermatology",  "Skin & Aesthetics",    "555-0102"),
    ("Dr. Emily Chen",       "Dermatology",  "Skin & Aesthetics",    "555-0103"),
    ("Dr. Robert Patel",     "Cardiology",   "Heart & Vascular",     "555-0201"),
    ("Dr. Linda Nguyen",     "Cardiology",   "Heart & Vascular",     "555-0202"),
    ("Dr. Kevin Adeyemi",    "Cardiology",   "Heart & Vascular",     "555-0203"),
    ("Dr. Maria Gonzalez",   "Orthopedics",  "Bone & Joint",         "555-0301"),
    ("Dr. Thomas Schultz",   "Orthopedics",  "Bone & Joint",         "555-0302"),
    ("Dr. Priya Sharma",     "Orthopedics",  "Bone & Joint",         "555-0303"),
    ("Dr. Alan Burke",       "General",      "Primary Care",         "555-0401"),
    ("Dr. Fatima Hassan",    "General",      "Primary Care",         "555-0402"),
    ("Dr. Daniel Kim",       "General",      "Primary Care",         "555-0403"),
    ("Dr. Rachel Torres",    "Pediatrics",   "Child Health",         "555-0501"),
    ("Dr. Michael Osei",     "Pediatrics",   "Child Health",         "555-0502"),
    ("Dr. Jennifer Walsh",   "Pediatrics",   "Child Health",         "555-0503"),
]

CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Chandigarh",
]

APPOINTMENT_STATUSES = ["Scheduled", "Completed", "Cancelled", "No-Show"]
STATUS_WEIGHTS        = [0.15,        0.60,        0.15,         0.10]

TREATMENT_NAMES = {
    "Dermatology":  ["Skin Biopsy", "Acne Treatment", "Chemical Peel", "Mole Removal", "Eczema Therapy"],
    "Cardiology":   ["ECG", "Echocardiogram", "Stress Test", "Angioplasty", "Blood Pressure Management"],
    "Orthopedics":  ["X-Ray Analysis", "Joint Injection", "Physiotherapy", "Fracture Setting", "Arthroscopy"],
    "General":      ["General Check-up", "Blood Test", "Vaccination", "Wound Dressing", "Diabetes Management"],
    "Pediatrics":   ["Growth Assessment", "Immunisation", "Nutrition Counselling", "Fever Management", "Developmental Screening"],
}

INVOICE_STATUSES  = ["Paid", "Pending", "Overdue"]
INVOICE_WEIGHTS   = [0.55,   0.25,      0.20]

TODAY = date.today()
YEAR_AGO = TODAY - timedelta(days=365)


# ── Helpers ───────────────────────────────────────────────────────────────────

def random_date_between(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def random_datetime_between(start: date, end: date) -> datetime:
    d = random_date_between(start, end)
    hour   = random.randint(8, 17)
    minute = random.choice([0, 15, 30, 45])
    return datetime(d.year, d.month, d.day, hour, minute)


def maybe_null(value, probability_null: float = 0.15):
    """Return None with given probability, else return value."""
    return None if random.random() < probability_null else value


# ── Table creation ────────────────────────────────────────────────────────────

CREATE_PATIENTS = """
CREATE TABLE IF NOT EXISTS patients (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name     TEXT    NOT NULL,
    last_name      TEXT    NOT NULL,
    email          TEXT,
    phone          TEXT,
    date_of_birth  DATE,
    gender         TEXT,
    city           TEXT,
    registered_date DATE
);
"""

CREATE_DOCTORS = """
CREATE TABLE IF NOT EXISTS doctors (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    specialization TEXT,
    department     TEXT,
    phone          TEXT
);
"""

CREATE_APPOINTMENTS = """
CREATE TABLE IF NOT EXISTS appointments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       INTEGER REFERENCES patients(id),
    doctor_id        INTEGER REFERENCES doctors(id),
    appointment_date DATETIME,
    status           TEXT,
    notes            TEXT
);
"""

CREATE_TREATMENTS = """
CREATE TABLE IF NOT EXISTS treatments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id   INTEGER REFERENCES appointments(id),
    treatment_name   TEXT,
    cost             REAL,
    duration_minutes INTEGER
);
"""

CREATE_INVOICES = """
CREATE TABLE IF NOT EXISTS invoices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER REFERENCES patients(id),
    invoice_date DATE,
    total_amount REAL,
    paid_amount  REAL,
    status       TEXT
);
"""


def create_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    for ddl in [CREATE_PATIENTS, CREATE_DOCTORS, CREATE_APPOINTMENTS,
                CREATE_TREATMENTS, CREATE_INVOICES]:
        cur.execute(ddl)
    conn.commit()


# ── Seeding ───────────────────────────────────────────────────────────────────

def seed_doctors(conn: sqlite3.Connection) -> list[int]:
    cur = conn.cursor()
    ids = []
    for name, spec, dept, phone in DOCTORS:
        cur.execute(
            "INSERT INTO doctors (name, specialization, department, phone) VALUES (?,?,?,?)",
            (name, spec, dept, phone),
        )
        ids.append(cur.lastrowid)
    conn.commit()
    return ids


def seed_patients(conn: sqlite3.Connection, n: int = 200) -> list[int]:
    cur = conn.cursor()
    ids = []
    for _ in range(n):
        gender = random.choice(["M", "F"])
        first  = fake.first_name_male() if gender == "M" else fake.first_name_female()
        last   = fake.last_name()
        dob    = random_date_between(date(1950, 1, 1), date(2015, 12, 31))
        reg    = random_date_between(YEAR_AGO, TODAY)
        cur.execute(
            """INSERT INTO patients
               (first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                first, last,
                maybe_null(fake.email(), 0.12),
                maybe_null(fake.phone_number()[:15], 0.10),
                str(dob), gender,
                random.choice(CITIES),
                str(reg),
            ),
        )
        ids.append(cur.lastrowid)
    conn.commit()
    return ids


def seed_appointments(
    conn: sqlite3.Connection,
    patient_ids: list[int],
    doctor_ids: list[int],
    n: int = 500,
) -> list[tuple[int, int, str]]:
    """Return list of (appointment_id, doctor_id, status)."""
    cur = conn.cursor()

    # Give some patients many appointments (repeat visitors)
    weights = [random.randint(1, 10) for _ in patient_ids]
    # Give some doctors more load
    doc_weights = [random.randint(1, 5) for _ in doctor_ids]

    records = []
    for _ in range(n):
        pat_id = random.choices(patient_ids, weights=weights, k=1)[0]
        doc_id = random.choices(doctor_ids, weights=doc_weights, k=1)[0]
        appt_dt = random_datetime_between(YEAR_AGO, TODAY)
        status  = random.choices(APPOINTMENT_STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        notes   = maybe_null(fake.sentence(nb_words=8), 0.30)
        cur.execute(
            """INSERT INTO appointments
               (patient_id, doctor_id, appointment_date, status, notes)
               VALUES (?,?,?,?,?)""",
            (pat_id, doc_id, str(appt_dt), status, notes),
        )
        records.append((cur.lastrowid, doc_id, status, pat_id))
    conn.commit()
    return records


def seed_treatments(
    conn: sqlite3.Connection,
    appointment_records: list[tuple[int, int, str, int]],
    target: int = 350,
) -> int:
    """Seed treatments only for Completed appointments."""
    cur = conn.cursor()

    completed = [(aid, did, pid) for aid, did, status, pid in appointment_records if status == "Completed"]

    # Fetch doctor specializations once
    cur.execute("SELECT id, specialization FROM doctors")
    doc_spec = {row[0]: row[1] for row in cur.fetchall()}

    # Sample up to `target` completed appointments
    sample = random.sample(completed, min(target, len(completed)))

    count = 0
    for appt_id, doc_id, _pat_id in sample:
        spec = doc_spec.get(doc_id, "General")
        name = random.choice(TREATMENT_NAMES.get(spec, TREATMENT_NAMES["General"]))
        cost = round(random.uniform(50, 5000), 2)
        dur  = random.randint(15, 120)
        cur.execute(
            "INSERT INTO treatments (appointment_id, treatment_name, cost, duration_minutes) VALUES (?,?,?,?)",
            (appt_id, name, cost, dur),
        )
        count += 1
    conn.commit()
    return count


def seed_invoices(
    conn: sqlite3.Connection,
    patient_ids: list[int],
    n: int = 300,
) -> int:
    cur = conn.cursor()
    count = 0
    for _ in range(n):
        pat_id     = random.choice(patient_ids)
        inv_date   = random_date_between(YEAR_AGO, TODAY)
        total      = round(random.uniform(100, 8000), 2)
        status     = random.choices(INVOICE_STATUSES, weights=INVOICE_WEIGHTS, k=1)[0]
        if status == "Paid":
            paid = total
        elif status == "Pending":
            paid = round(random.uniform(0, total * 0.5), 2)
        else:  # Overdue
            paid = round(random.uniform(0, total * 0.3), 2)
        cur.execute(
            """INSERT INTO invoices (patient_id, invoice_date, total_amount, paid_amount, status)
               VALUES (?,?,?,?,?)""",
            (pat_id, str(inv_date), total, paid, status),
        )
        count += 1
    conn.commit()
    return count


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    create_tables(conn)

    doctor_ids  = seed_doctors(conn)
    patient_ids = seed_patients(conn, 200)
    appt_recs   = seed_appointments(conn, patient_ids, doctor_ids, 500)
    treat_count = seed_treatments(conn, appt_recs, 350)
    inv_count   = seed_invoices(conn, patient_ids, 300)

    # Summary
    cur = conn.cursor()
    p_count = cur.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    d_count = cur.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
    a_count = cur.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
    t_count = cur.execute("SELECT COUNT(*) FROM treatments").fetchone()[0]
    i_count = cur.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]

    conn.close()

    print(
        f"Created {p_count} patients, {d_count} doctors, {a_count} appointments, "
        f"{t_count} treatments, {i_count} invoices in '{DB_PATH}'"
    )


if __name__ == "__main__":
    main()
