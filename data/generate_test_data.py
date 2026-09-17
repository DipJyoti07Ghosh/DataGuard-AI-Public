"""
DataGuard AI — Synthetic Test Data Generator

Generates realistic sample datasets for development and testing.
Run this script to create CSV files under the data/ directory.
"""

import csv
import random
import os
from pathlib import Path

# Seed for reproducibility
random.seed(42)

DATA_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Daniel",
    "Lisa", "Matthew", "Nancy", "Anthony", "Betty", "Mark", "Margaret",
    "Donald", "Sandra", "Steven", "Ashley", "Paul", "Dorothy", "Andrew",
    "Kimberly", "Joshua", "Emily", "Kenneth", "Donna", "Kevin", "Michelle",
    "Brian", "Carol", "George", "Amanda", "Timothy", "Melissa", "Ronald", "Deborah",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson",
]

CITIES = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
    "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville",
    "Fort Worth", "Columbus", "Charlotte", "Indianapolis", "San Francisco",
    "Seattle", "Denver", "Washington", "Nashville", "Oklahoma City", "El Paso",
    "Boston", "Portland", "Las Vegas", "Memphis", "Louisville", "Baltimore",
    "Milwaukee",
]

STATES = [
    "NY", "CA", "IL", "TX", "AZ", "PA", "TX", "CA", "TX", "CA",
    "TX", "FL", "TX", "OH", "NC", "IN", "CA", "WA", "CO", "DC",
    "TN", "OK", "TX", "MA", "OR", "NV", "TN", "KY", "MD", "WI",
]

PRODUCTS = [
    "Laptop Pro X1", "Wireless Mouse", "USB-C Hub", "Monitor 27in",
    "Mechanical Keyboard", "Webcam HD", "Noise Cancelling Headphones",
    "Portable SSD 1TB", "Desk Lamp LED", "Ergonomic Chair",
    "Standing Desk", "Tablet 10in", "Smartphone Case", "Power Bank",
    "Bluetooth Speaker", "Smart Watch", "Fitness Tracker", "VR Headset",
    "Drone Mini", "Action Camera",
]

CATEGORIES = [
    "Electronics", "Peripherals", "Accessories", "Furniture",
    "Audio", "Storage", "Lighting", "Wearables", "Cameras", "Computing",
]

SUBSCRIPTION_TYPES = ["Free", "Basic", "Pro", "Enterprise"]
GENDERS = ["Male", "Female", "Non-binary", "Prefer not to say"]
STATUSES = ["Active", "Inactive", "Suspended", "Pending"]


def rand_email(first, last):
    domains = ["gmail.com", "yahoo.com", "outlook.com", "company.com", "example.org"]
    return f"{first.lower()}.{last.lower()}@{random.choice(domains)}"


def rand_phone():
    return f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"


def rand_amount(low, high, decimals=2):
    return round(random.uniform(low, high), decimals)


# ---------------------------------------------------------------------------
# Dataset 1: clean_sample.csv — Relatively clean customer/order data
# ---------------------------------------------------------------------------
def generate_clean_sample(n=200):
    rows = []
    for i in range(1, n + 1):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        city_idx = random.randint(0, len(CITIES) - 1)
        age = random.randint(18, 75)
        rows.append({
            "customer_id": 1000 + i,
            "first_name": first,
            "last_name": last,
            "email": rand_email(first, last),
            "phone": rand_phone(),
            "age": age,
            "gender": random.choice(GENDERS),
            "city": CITIES[city_idx],
            "state": STATES[city_idx],
            "subscription_type": random.choice(SUBSCRIPTION_TYPES),
            "monthly_spend": rand_amount(5.0, 500.0),
            "account_age_months": random.randint(1, 120),
            "total_purchases": random.randint(0, 500),
            "satisfaction_score": round(random.uniform(1.0, 5.0), 1),
            "status": random.choice(STATUSES),
            "signup_date": f"2020-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        })

    filepath = DATA_DIR / "clean_sample.csv"
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Created: {filepath} ({n} rows)")


# ---------------------------------------------------------------------------
# Dataset 2: quality_issues_v1.csv — Intentional quality problems
# ---------------------------------------------------------------------------
def generate_quality_issues_v1(n=250):
    rows = []
    for i in range(1, n + 1):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        city_idx = random.randint(0, len(CITIES) - 1)
        age = random.randint(18, 75)

        row = {
            "customer_id": 1000 + i,
            "first_name": first,
            "last_name": last,
            "email": rand_email(first, last),
            "phone": rand_phone(),
            "age": age,
            "gender": random.choice(GENDERS),
            "city": CITIES[city_idx],
            "state": STATES[city_idx],
            "subscription_type": random.choice(SUBSCRIPTION_TYPES),
            "monthly_spend": rand_amount(5.0, 500.0),
            "account_age_months": random.randint(1, 120),
            "total_purchases": random.randint(0, 500),
            "satisfaction_score": round(random.uniform(1.0, 5.0), 1),
            "status": random.choice(STATUSES),
            "signup_date": f"2020-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        }

        # --- Introduce quality issues ---

        # Missing values (~8% of emails, ~12% of ages, ~15% of cities)
        if random.random() < 0.08:
            row["email"] = ""
        if random.random() < 0.12:
            row["age"] = ""
        if random.random() < 0.15:
            row["city"] = ""
            row["state"] = ""
        if random.random() < 0.05:
            row["monthly_spend"] = ""
        if random.random() < 0.10:
            row["satisfaction_score"] = ""

        # Outliers in age (negative, impossibly old)
        if random.random() < 0.02:
            row["age"] = random.choice([-5, 150, 200, 999])
        # Outliers in monthly_spend
        if random.random() < 0.03:
            row["monthly_spend"] = random.choice([0.01, 99999.99, -50.0, 50000.0])

        # Inconsistent formats in gender
        if random.random() < 0.05:
            row["gender"] = random.choice(["M", "F", "male", "female", "MALE", "other", "N/A"])

        # Inconsistent status values
        if random.random() < 0.04:
            row["status"] = random.choice(["active", "ACTIVE", "inactive", "cancelled", "N/A"])

        # Invalid email formats
        if random.random() < 0.03 and row["email"]:
            row["email"] = random.choice([
                "not_an_email", "john@", "@company.com", "invalid",
                first.lower(), f"{first.lower()}@"
            ])

        # Inconsistent phone formats
        if random.random() < 0.04:
            row["phone"] = random.choice([
                "1234567890", "(555) 123-4567", "555.123.4567",
                "N/A", "unknown", "",
            ])

        # Inconsistent date formats
        if random.random() < 0.05:
            row["signup_date"] = random.choice([
                f"{random.randint(1,12)}/{random.randint(1,28)}/2020",
                f"{random.randint(1,28):02d}-{random.randint(1,12):02d}-2020",
                "2020", "N/A", "",
            ])

        rows.append(row)

    # Add exact duplicate rows (~3%)
    num_dupes = int(n * 0.03)
    for _ in range(num_dupes):
        rows.append(random.choice(rows[:n]).copy())

    random.shuffle(rows)

    filepath = DATA_DIR / "quality_issues_v1.csv"
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Created: {filepath} ({len(rows)} rows, with quality issues)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    generate_clean_sample()
    generate_quality_issues_v1()
    print("\nSample datasets generated successfully!")
