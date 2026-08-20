import os
import django
from django.db import connection

# Ensure this matches your project folder name
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nukr_core.settings') 
django.setup()

def fix_database():
    with connection.cursor() as cursor:
        print("🛠️ Cleaning Ghost Tables & Columns...")
        
        # 1. Drop Ghost Tables (The cause of your current error)
        # We use CASCADE to remove any connections automatically
        tables_to_drop = [
            'marketplace_storewallet',
            'marketplace_conversation',
            'marketplace_message'
        ]
        
        for table in tables_to_drop:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                print(f" - 🗑️ Dropped table '{table}'")
            except Exception as e:
                print(f" - ⚠️ Could not drop {table}: {e}")

        # 2. Drop Ghost Columns (Just in case they are still lingering)
        try:
            cursor.execute("ALTER TABLE marketplace_order DROP COLUMN IF EXISTS is_paid;")
            print(" - 🗑️ Dropped column 'is_paid'")
        except: pass

        try:
            cursor.execute("ALTER TABLE marketplace_order DROP COLUMN IF EXISTS safepay_tracker;")
            print(" - 🗑️ Dropped column 'safepay_tracker'")
        except: pass
        
        try:
            cursor.execute("ALTER TABLE marketplace_store DROP COLUMN IF EXISTS card_payments_enabled;")
            print(" - 🗑️ Dropped column 'card_payments_enabled'")
        except: pass

        print("\n✅ Database Cleaned. You can run migrate now.")

if __name__ == '__main__':
    fix_database()