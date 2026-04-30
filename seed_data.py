"""
Seed data script — upisuje test podatke u DynamoDB
Za demonstraciju paginacije i sort-a, trebaju nam multiple itemi u istoj particiji.

Korišćenje:
    python seed_data.py
"""

import boto3
import json
from datetime import datetime, timedelta
from decimal import Decimal

# Konfiguracija
TABLE_NAME = "ItemsTable"
REGION = "us-east-1"

# Kreiramo DynamoDB resurs
dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

# Test podaci — više itema u istoj particiji (USER#1) sa različitim SK-ovima
test_items = [
    {
        "PK": "USER#1",
        "SK": "ORDER#2025-01-01",
        "total": Decimal("99.50"),
        "status": "paid",
        "items_count": 3,
        "created_at": "2025-01-01T10:30:00Z",
        "customer_name": "Milan Davidovic"
    },
    {
        "PK": "USER#1",
        "SK": "ORDER#2025-01-05",
        "total": Decimal("45.75"),
        "status": "pending",
        "items_count": 2,
        "created_at": "2025-01-05T14:20:00Z",
        "customer_name": "Milan Davidovic"
    },
    {
        "PK": "USER#1",
        "SK": "ORDER#2025-01-10",
        "total": Decimal("156.20"),
        "status": "shipped",
        "items_count": 5,
        "created_at": "2025-01-10T09:15:00Z",
        "customer_name": "Milan Davidovic"
    },
    {
        "PK": "USER#1",
        "SK": "ORDER#2025-01-15",
        "total": Decimal("28.99"),
        "status": "delivered",
        "items_count": 1,
        "created_at": "2025-01-15T16:45:00Z",
        "customer_name": "Milan Davidovic"
    },
    {
        "PK": "USER#1",
        "SK": "ORDER#2025-01-20",
        "total": Decimal("87.60"),
        "status": "paid",
        "items_count": 4,
        "created_at": "2025-01-20T11:30:00Z",
        "customer_name": "Milan Davidovic"
    },
    {
        "PK": "USER#1",
        "SK": "ORDER#2025-01-25",
        "total": Decimal("200.00"),
        "status": "pending",
        "items_count": 8,
        "created_at": "2025-01-25T13:00:00Z",
        "customer_name": "Milan Davidovic"
    },
    {
        "PK": "USER#1",
        "SK": "ORDER#2025-02-01",
        "total": Decimal("64.45"),
        "status": "shipped",
        "items_count": 2,
        "created_at": "2025-02-01T10:00:00Z",
        "customer_name": "Milan Davidovic"
    },
    {
        "PK": "USER#1",
        "SK": "ORDER#2025-02-05",
        "total": Decimal("120.80"),
        "status": "delivered",
        "items_count": 3,
        "created_at": "2025-02-05T15:30:00Z",
        "customer_name": "Milan Davidovic"
    },
    # Drugi korisnik — za demonstraciju da vidimo kako se filtrira po PK
    {
        "PK": "USER#2",
        "SK": "ORDER#2025-01-03",
        "total": Decimal("55.30"),
        "status": "paid",
        "items_count": 2,
        "created_at": "2025-01-03T12:00:00Z",
        "customer_name": "Jovana Markovic"
    },
    {
        "PK": "USER#2",
        "SK": "ORDER#2025-01-18",
        "total": Decimal("175.40"),
        "status": "delivered",
        "items_count": 6,
        "created_at": "2025-01-18T14:15:00Z",
        "customer_name": "Jovana Markovic"
    },
    # Treći korisnik
    {
        "PK": "USER#3",
        "SK": "INVOICE#2025-Q1",
        "total": Decimal("500.00"),
        "status": "paid",
        "items_count": 20,
        "created_at": "2025-03-31T17:00:00Z",
        "customer_name": "Aleksandar Jovanovic"
    },
]


def seed_table():
    """Upisuje sve test iteme u tabelu"""
    print(f"\n{'='*60}")
    print(f"SEED DATA — Upisivanje test podataka u {TABLE_NAME}")
    print(f"{'='*60}\n")
    
    success_count = 0
    error_count = 0
    
    for idx, item in enumerate(test_items, 1):
        try:
            print(f"[{idx}/{len(test_items)}] Upisivanje: PK={item['PK']}, SK={item['SK']}")
            table.put_item(Item=item)
            success_count += 1
            print(f"       ✓ Uspešno\n")
        except Exception as e:
            error_count += 1
            print(f"       ✗ Greška: {str(e)}\n")
    
    print(f"{'='*60}")
    print(f"Rezultat: {success_count} uspešna, {error_count} grešaka")
    print(f"{'='*60}\n")
    
    if success_count == len(test_items):
        print("✓ Svi podaci su uspešno upisani!\n")
        print("Sada možeš testirati:\n")
        print("  1. GET sve iz USER#1 (limit=2 za paginaciju):")
        print("     curl 'https://your-api/items/USER%231?limit=2'\n")
        print("  2. GET samo jedan item:")
        print("     curl 'https://your-api/items/USER%231/ORDER%232025-01-01'\n")
        print("  3. Videti sort — rezultati su po SK (datumu)")
        print("     ORDER#2025-01-01 dolazi pre ORDER#2025-01-05 itd.\n")
        return True
    else:
        print("✗ Neki podaci nisu upisani. Proveri grešku iznad.\n")
        return False


def list_all_items():
    """Ispisuje sve stavke u tabeli (samo za proveru)"""
    print(f"\n{'='*60}")
    print(f"SVE STAVKE U TABELI {TABLE_NAME}")
    print(f"{'='*60}\n")
    
    try:
        response = table.scan()  # Scan — čita sve (ne koristi u produkciji za velike tabele!)
        items = response.get("Items", [])
        
        # Sortiraj po PK pa po SK za čitljivost
        items_sorted = sorted(items, key=lambda x: (x.get("PK"), x.get("SK")))
        
        for item in items_sorted:
            print(f"PK: {item['PK']:<10} | SK: {item['SK']:<25} | "
                  f"Total: ${item.get('total', 'N/A'):<8} | "
                  f"Status: {item.get('status', 'N/A')}")
        
        print(f"\nUkupno stavki: {len(items_sorted)}\n")
        
    except Exception as e:
        print(f"Greška pri čitanju tabele: {str(e)}\n")


if __name__ == "__main__":
    import sys
    
    # Argumenti: 'seed' (upiši), 'list' (prikaži), ili bez (oba)
    action = sys.argv[1] if len(sys.argv) > 1 else "both"
    
    if action in ["seed", "both"]:
        seed_table()
    
    if action in ["list", "both"]:
        list_all_items()