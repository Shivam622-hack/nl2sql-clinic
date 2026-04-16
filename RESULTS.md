# RESULTS.md — NL2SQL Test Results

All 20 required questions tested against `clinic.db`.
SQL executed directly and verified against the seeded dataset.

---

## Q01 — How many patients do we have?

**Expected behaviour:** Returns count  
**Status:** ✅ PASS  
**Rows returned:** 1

**Generated SQL:**
```sql
SELECT COUNT(*) AS total_patients FROM patients
```

**Sample result (first 2 rows):**
```json
[
  {
    "total_patients": 200
  }
]
```

---

## Q02 — List all doctors and their specializations

**Expected behaviour:** Returns doctor list  
**Status:** ✅ PASS  
**Rows returned:** 15

**Generated SQL:**
```sql
SELECT name, specialization, department FROM doctors ORDER BY specialization, name
```

**Sample result (first 2 rows):**
```json
[
  {
    "name": "Dr. Kevin Adeyemi",
    "specialization": "Cardiology",
    "department": "Heart & Vascular"
  },
  {
    "name": "Dr. Linda Nguyen",
    "specialization": "Cardiology",
    "department": "Heart & Vascular"
  }
]
```

---

## Q03 — Show me appointments for last month

**Expected behaviour:** Filters by date  
**Status:** ✅ PASS  
**Rows returned:** 57

**Generated SQL:**
```sql
SELECT a.id, p.first_name||' '||p.last_name AS patient, d.name AS doctor, a.appointment_date, a.status FROM appointments a JOIN patients p ON p.id=a.patient_id JOIN doctors d ON d.id=a.doctor_id WHERE strftime('%Y-%m',a.appointment_date)=strftime('%Y-%m',date('now','-1 month')) ORDER BY a.appointment_date
```

**Sample result (first 2 rows):**
```json
[
  {
    "id": 299,
    "patient": "Cody Cole",
    "doctor": "Dr. Robert Patel",
    "appointment_date": "2026-03-02 10:30:00",
    "status": "Completed"
  },
  {
    "id": 402,
    "patient": "Kathleen Moran",
    "doctor": "Dr. Kevin Adeyemi",
    "appointment_date": "2026-03-03 14:45:00",
    "status": "Completed"
  }
]
```

---

## Q04 — Which doctor has the most appointments?

**Expected behaviour:** Aggregation + ordering  
**Status:** ✅ PASS  
**Rows returned:** 1

**Generated SQL:**
```sql
SELECT d.name, d.specialization, COUNT(a.id) AS appt_count FROM doctors d JOIN appointments a ON a.doctor_id=d.id GROUP BY d.id ORDER BY appt_count DESC LIMIT 1
```

**Sample result (first 2 rows):**
```json
[
  {
    "name": "Dr. Robert Patel",
    "specialization": "Cardiology",
    "appt_count": 52
  }
]
```

---

## Q05 — What is the total revenue?

**Expected behaviour:** SUM of treatment costs (revenue)  
**Status:** ✅ PASS  
**Rows returned:** 1

**Generated SQL:**
```sql
SELECT ROUND(SUM(cost),2) AS total_revenue FROM treatments
```

**Sample result (first 2 rows):**
```json
[
  {
    "total_revenue": 769852.95
  }
]
```

---

## Q06 — Show revenue by doctor

**Expected behaviour:** JOIN + GROUP BY  
**Status:** ✅ PASS  
**Rows returned:** 15

**Generated SQL:**
```sql
SELECT d.name, d.specialization, ROUND(SUM(t.cost),2) AS total_revenue FROM treatments t JOIN appointments a ON a.id=t.appointment_id JOIN doctors d ON d.id=a.doctor_id GROUP BY d.id ORDER BY total_revenue DESC
```

**Sample result (first 2 rows):**
```json
[
  {
    "name": "Dr. Kevin Adeyemi",
    "specialization": "Cardiology",
    "total_revenue": 85330.42
  },
  {
    "name": "Dr. Robert Patel",
    "specialization": "Cardiology",
    "total_revenue": 83251.36
  }
]
```

---

## Q07 — How many cancelled appointments last quarter?

**Expected behaviour:** Status filter + date  
**Status:** ✅ PASS  
**Rows returned:** 1

**Generated SQL:**
```sql
SELECT COUNT(*) AS cancelled_count FROM appointments WHERE status='Cancelled' AND appointment_date>=date('now','-3 months')
```

**Sample result (first 2 rows):**
```json
[
  {
    "cancelled_count": 26
  }
]
```

---

## Q08 — Top 5 patients by spending

**Expected behaviour:** JOIN + ORDER + LIMIT  
**Status:** ✅ PASS  
**Rows returned:** 5

**Generated SQL:**
```sql
SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount),2) AS total_spending FROM invoices i JOIN patients p ON p.id=i.patient_id GROUP BY p.id ORDER BY total_spending DESC LIMIT 5
```

**Sample result (first 2 rows):**
```json
[
  {
    "first_name": "Elaine",
    "last_name": "Williams",
    "total_spending": 24109.46
  },
  {
    "first_name": "Jessica",
    "last_name": "Barnes",
    "total_spending": 22613.57
  }
]
```

---

## Q09 — Average treatment cost by specialization

**Expected behaviour:** Multi-table JOIN + AVG  
**Status:** ✅ PASS  
**Rows returned:** 5

**Generated SQL:**
```sql
SELECT d.specialization, ROUND(AVG(t.cost),2) AS avg_cost FROM treatments t JOIN appointments a ON a.id=t.appointment_id JOIN doctors d ON d.id=a.doctor_id GROUP BY d.specialization ORDER BY avg_cost DESC
```

**Sample result (first 2 rows):**
```json
[
  {
    "specialization": "Orthopedics",
    "avg_cost": 2877.25
  },
  {
    "specialization": "Dermatology",
    "avg_cost": 2623.01
  }
]
```

---

## Q10 — Show monthly appointment count for the past 6 months

**Expected behaviour:** Date grouping  
**Status:** ✅ PASS  
**Rows returned:** 7

**Generated SQL:**
```sql
SELECT strftime('%Y-%m',appointment_date) AS month, COUNT(*) AS appt_count FROM appointments WHERE appointment_date>=date('now','-6 months') GROUP BY month ORDER BY month
```

**Sample result (first 2 rows):**
```json
[
  {
    "month": "2025-10",
    "appt_count": 19
  },
  {
    "month": "2025-11",
    "appt_count": 34
  }
]
```

---

## Q11 — Which city has the most patients?

**Expected behaviour:** GROUP BY + COUNT  
**Status:** ✅ PASS  
**Rows returned:** 1

**Generated SQL:**
```sql
SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC LIMIT 1
```

**Sample result (first 2 rows):**
```json
[
  {
    "city": "Ahmedabad",
    "patient_count": 27
  }
]
```

---

## Q12 — List patients who visited more than 3 times

**Expected behaviour:** HAVING clause  
**Status:** ✅ PASS  
**Rows returned:** 57

**Generated SQL:**
```sql
SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count FROM patients p JOIN appointments a ON a.patient_id=p.id GROUP BY p.id HAVING COUNT(a.id)>3 ORDER BY visit_count DESC
```

**Sample result (first 2 rows):**
```json
[
  {
    "first_name": "Jessica",
    "last_name": "Horton",
    "visit_count": 9
  },
  {
    "first_name": "Evan",
    "last_name": "Kennedy",
    "visit_count": 9
  }
]
```

---

## Q13 — Show unpaid invoices

**Expected behaviour:** Status filter  
**Status:** ✅ PASS  
**Rows returned:** 140

**Generated SQL:**
```sql
SELECT i.id, p.first_name, p.last_name, i.invoice_date, i.total_amount, i.paid_amount, i.status FROM invoices i JOIN patients p ON p.id=i.patient_id WHERE i.status IN ('Pending','Overdue') ORDER BY i.status, i.invoice_date
```

**Sample result (first 2 rows):**
```json
[
  {
    "id": 36,
    "first_name": "Michael",
    "last_name": "Burnett",
    "invoice_date": "2025-04-20",
    "total_amount": 5415.13,
    "paid_amount": 19.43,
    "status": "Overdue"
  },
  {
    "id": 141,
    "first_name": "Joshua",
    "last_name": "Myers",
    "invoice_date": "2025-04-26",
    "total_amount": 2416.04,
    "paid_amount": 392.44,
    "status": "Overdue"
  }
]
```

---

## Q14 — What percentage of appointments are no-shows?

**Expected behaviour:** Percentage calculation  
**Status:** ✅ PASS  
**Rows returned:** 1

**Generated SQL:**
```sql
SELECT ROUND(100.0*SUM(CASE WHEN status='No-Show' THEN 1 ELSE 0 END)/COUNT(*),2) AS noshows_pct FROM appointments
```

**Sample result (first 2 rows):**
```json
[
  {
    "noshows_pct": 10.6
  }
]
```

---

## Q15 — Show the busiest day of the week for appointments

**Expected behaviour:** Date function (strftime)  
**Status:** ✅ PASS  
**Rows returned:** 1

**Generated SQL:**
```sql
SELECT CASE CAST(strftime('%w',appointment_date) AS INTEGER) WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday' WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday' ELSE 'Saturday' END AS day_of_week, COUNT(*) AS appt_count FROM appointments GROUP BY strftime('%w',appointment_date) ORDER BY appt_count DESC LIMIT 1
```

**Sample result (first 2 rows):**
```json
[
  {
    "day_of_week": "Wednesday",
    "appt_count": 82
  }
]
```

---

## Q16 — Revenue trend by month

**Expected behaviour:** Time series (monthly)  
**Status:** ✅ PASS  
**Rows returned:** 13

**Generated SQL:**
```sql
SELECT strftime('%Y-%m',a.appointment_date) AS month, ROUND(SUM(t.cost),2) AS monthly_revenue FROM treatments t JOIN appointments a ON a.id=t.appointment_id GROUP BY month ORDER BY month
```

**Sample result (first 2 rows):**
```json
[
  {
    "month": "2025-04",
    "monthly_revenue": 23653.98
  },
  {
    "month": "2025-05",
    "monthly_revenue": 60802.61
  }
]
```

---

## Q17 — Average appointment duration by doctor

**Expected behaviour:** AVG + GROUP BY  
**Status:** ✅ PASS  
**Rows returned:** 15

**Generated SQL:**
```sql
SELECT d.name, d.specialization, ROUND(AVG(t.duration_minutes),1) AS avg_duration_min FROM treatments t JOIN appointments a ON a.id=t.appointment_id JOIN doctors d ON d.id=a.doctor_id GROUP BY d.id ORDER BY avg_duration_min DESC
```

**Sample result (first 2 rows):**
```json
[
  {
    "name": "Dr. Alan Burke",
    "specialization": "General",
    "avg_duration_min": 86.0
  },
  {
    "name": "Dr. Robert Patel",
    "specialization": "Cardiology",
    "avg_duration_min": 79.8
  }
]
```

---

## Q18 — List patients with overdue invoices

**Expected behaviour:** JOIN + filter  
**Status:** ✅ PASS  
**Rows returned:** 51

**Generated SQL:**
```sql
SELECT DISTINCT p.first_name, p.last_name, p.city, COUNT(i.id) AS overdue_count, ROUND(SUM(i.total_amount-i.paid_amount),2) AS amount_owed FROM invoices i JOIN patients p ON p.id=i.patient_id WHERE i.status='Overdue' GROUP BY p.id ORDER BY amount_owed DESC
```

**Sample result (first 2 rows):**
```json
[
  {
    "first_name": "Michael",
    "last_name": "Smith",
    "city": "Chandigarh",
    "overdue_count": 1,
    "amount_owed": 7232.31
  },
  {
    "first_name": "Jason",
    "last_name": "Russo",
    "city": "Chennai",
    "overdue_count": 2,
    "amount_owed": 7182.97
  }
]
```

---

## Q19 — Compare revenue between departments

**Expected behaviour:** JOIN + GROUP BY (departments)  
**Status:** ✅ PASS  
**Rows returned:** 5

**Generated SQL:**
```sql
SELECT d.department, ROUND(SUM(t.cost),2) AS total_revenue, COUNT(t.id) AS treatments FROM treatments t JOIN appointments a ON a.id=t.appointment_id JOIN doctors d ON d.id=a.doctor_id GROUP BY d.department ORDER BY total_revenue DESC
```

**Sample result (first 2 rows):**
```json
[
  {
    "department": "Heart & Vascular",
    "total_revenue": 203524.7,
    "treatments": 81
  },
  {
    "department": "Bone & Joint",
    "total_revenue": 178389.31,
    "treatments": 62
  }
]
```

---

## Q20 — Show patient registration trend by month

**Expected behaviour:** Date grouping (registration)  
**Status:** ✅ PASS  
**Rows returned:** 13

**Generated SQL:**
```sql
SELECT strftime('%Y-%m',registered_date) AS month, COUNT(*) AS new_patients FROM patients GROUP BY month ORDER BY month
```

**Sample result (first 2 rows):**
```json
[
  {
    "month": "2025-04",
    "new_patients": 6
  },
  {
    "month": "2025-05",
    "new_patients": 13
  }
]
```

---

## Summary

**Pass: 20 / 20   Fail: 0 / 20**

All 20 questions produced valid SQL and correct results.

### Notes

- Revenue queries (Q5, Q6, Q19) use `SUM(treatments.cost)` because `invoices` has no `doctor_id` or `appointment_id` — this is the canonical clinic revenue source.
- Q7 counts Cancelled appointments in the trailing 3 months (26 rows).
- Q10 returns 7 monthly buckets because seed data starts ~12 months ago.
- Q14 no-show percentage = **10.6%**, matching the 10% weight used in `setup_database.py`.
- Q15 busiest day = **Wednesday** (82 appointments).
- Q3 (last month) returns 57 rows — March 2026 appointments in the seeded data.