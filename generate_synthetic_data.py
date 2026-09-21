"""
Lamp - Synthetic Nigerian Civic Reports Generator
=====================================================
Generates realistic-looking, but 100% SYNTHETIC / DEMO DATA civic reports
for use in the Lamp proof-of-concept. Every record is tagged
is_demo_data=True and no real events, real people, or real government
figures are represented.

Run: python generate_synthetic_data.py
Output: lamp_demo_reports.csv (500 rows)
"""

import csv
import random
import uuid
from datetime import datetime, timedelta

random.seed(42)

STATES_LGAS = {
    "Lagos": ["Ikeja", "Alimosho", "Ajeromi-Ifelodun", "Epe", "Eti-Osa"],
    "Kano": ["Nassarawa", "Fagge", "Dala", "Gwale"],
    "Rivers": ["Port Harcourt", "Obio-Akpor", "Ikwerre"],
    "Enugu": ["Enugu East", "Enugu North", "Nsukka"],
    "Kaduna": ["Kaduna North", "Kaduna South", "Zaria"],
    "Oyo": ["Ibadan North", "Ibadan South-West", "Egbeda"],
    "Plateau": ["Jos North", "Jos South", "Barkin Ladi"],
    "Borno": ["Maiduguri", "Jere"],
    "Anambra": ["Awka South", "Onitsha North", "Nnewi North"],
    "Cross River": ["Calabar Municipal", "Calabar South"],
}

CATEGORIES = {
    "Water Infrastructure": [
        "My community has not had water for {n} weeks and the borehole project announced last year has not been completed.",
        "The public water tap in our area has been dry since {month}, residents now trek {n}km to fetch water.",
        "Contractors abandoned the water scheme project midway, pipes are left exposed on the road.",
    ],
    "Electricity/Power": [
        "We have had no electricity supply for {n} days despite paying our estimated bills.",
        "Transformer in our street has been faulty for {n} months, several complaints filed with no response.",
    ],
    "Road/Transport Infrastructure": [
        "The road linking our community to the main highway has been impassable since the rains started, {n} accidents reported.",
        "Bridge construction stopped {n} months ago, commuters now risk crossing on foot.",
    ],
    "Healthcare Access": [
        "The primary health centre has no drugs in stock and the only nurse resigned {n} months ago.",
        "Community clinic promised in {month} has still not been built, pregnant women travel far for care.",
    ],
    "Education/Infrastructure": [
        "Public school roof collapsed during the storm, {n} pupils now learn under a tree.",
        "No teachers have been posted to our primary school since the last academic session.",
    ],
    "Safety/Security Concern": [
        "There have been {n} reported cases of armed robbery on this road at night, no police patrol has been seen.",
        "Unknown persons have been seen surveying the area at night, residents are afraid.",
    ],
    "Community Dispute": [
        "There is an ongoing land boundary dispute between two families that has led to tension in the market.",
        "Youths from two neighbouring communities clashed over grazing route access.",
    ],
    "Environmental Hazard": [
        "Waste has not been evacuated from this dumpsite in {n} weeks, causing serious odour and flooding risk.",
        "Gas flaring near our farmland is affecting crop yield and causing respiratory complaints.",
    ],
    "Suspected Misuse of Public Funds": [
        "A borehole project budgeted at a stated amount was completed but does not function, community wants transparency.",
        "Road rehabilitation project was marked complete in official records but no visible work was done.",
    ],
    "Abuse/Protection Concern": [
        "A vulnerable community member is reportedly being denied access to support services by a local intermediary.",
        "Reports of a minor being kept out of school for exploitative labour in the local market.",
    ],
}

EVIDENCE_TYPES = ["photo", "voice_note", "text_only", "video", "none"]
VERIFICATION_STATUSES = ["Unverified", "Needs Corroboration", "Corroborated", "Conflicting Reports", "High-Confidence"]
RESPONSE_STATUSES = ["No Action Yet", "Under Review", "Referred to Authority", "In Progress", "Resolved"]

def severity_for(category):
    high = {"Safety/Security Concern", "Abuse/Protection Concern", "Healthcare Access"}
    med = {"Water Infrastructure", "Electricity/Power", "Road/Transport Infrastructure", "Environmental Hazard"}
    if category in high:
        return random.choices([3, 4, 5], weights=[2, 4, 4])[0]
    if category in med:
        return random.choices([2, 3, 4], weights=[3, 4, 3])[0]
    return random.choices([1, 2, 3], weights=[3, 4, 3])[0]

def risk_score(severity, urgency, affected, evidence_conf):
    # transparent, documented formula (see README) - normalized 0-100
    raw = severity * urgency * (1 + affected / 1000) * evidence_conf
    return round(min(raw / 2.5, 100), 1)

def gen_report(i):
    state = random.choice(list(STATES_LGAS.keys()))
    lga = random.choice(STATES_LGAS[state])
    community = f"{lga} Community {random.randint(1,9)}"
    category = random.choice(list(CATEGORIES.keys()))
    template = random.choice(CATEGORIES[category])
    n = random.randint(2, 12)
    month = random.choice(["January", "March", "May", "July", "September", "November"])
    description = template.format(n=n, month=month)

    severity = severity_for(category)
    urgency = random.randint(1, 5)
    affected = random.choice([15, 40, 80, 150, 300, 600, 1200, 3000])
    evidence_type = random.choices(EVIDENCE_TYPES, weights=[3, 2, 4, 1, 1])[0]
    evidence_conf = {"photo": 0.9, "video": 0.95, "voice_note": 0.7, "text_only": 0.5, "none": 0.3}[evidence_type]

    ai_confidence = round(random.uniform(0.62, 0.98), 2)
    verification = random.choices(VERIFICATION_STATUSES, weights=[3, 3, 2, 1, 1])[0]
    response_status = random.choices(RESPONSE_STATUSES, weights=[3, 2, 2, 2, 1])[0]

    date = datetime(2026, 1, 1) + timedelta(days=random.randint(0, 250))
    resolution_date = ""
    if response_status == "Resolved":
        resolution_date = (date + timedelta(days=random.randint(5, 60))).strftime("%Y-%m-%d")

    return {
        "report_id": f"LMP-{i:05d}",
        "date": date.strftime("%Y-%m-%d"),
        "state": state,
        "lga": lga,
        "community": community,
        "category": category,
        "description": description,
        "severity_1to5": severity,
        "urgency_1to5": urgency,
        "num_affected_est": affected,
        "evidence_type": evidence_type,
        "evidence_confidence": evidence_conf,
        "verification_status": verification,
        "ai_confidence": ai_confidence,
        "risk_score": risk_score(severity, urgency, affected, evidence_conf),
        "response_status": response_status,
        "resolution_date": resolution_date,
        "reporter_anonymous": random.choice([True, True, True, False]),
        "is_demo_data": True,
    }

def main():
    rows = [gen_report(i) for i in range(1, 501)]
    fieldnames = list(rows[0].keys())
    with open("lamp_demo_reports.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} DEMO reports -> lamp_demo_reports.csv")

if __name__ == "__main__":
    main()