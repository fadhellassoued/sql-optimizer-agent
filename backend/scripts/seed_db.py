import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
import sys

# Load .env with encoding handling
load_dotenv(encoding='utf-8-sig')  # Handles BOM

# Get database URL
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("❌ DATABASE_URL not found in .env!")
    sys.exit(1)

# Clean the URL
db_url = db_url.strip()
db_url = db_url.replace("+asyncpg", "")  # Remove asyncpg for non-async engine

print(f"🔗 Connecting to: {db_url.replace('admin', '****')}")  # Hide password

# Create engine with explicit encoding
engine = create_engine(db_url, client_encoding='utf8')

# Test connection first
try:
    with engine.connect() as test_conn:
        result = test_conn.execute(text("SELECT 1"))
        print("✅ Database connection successful!")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\n💡 Troubleshooting:")
    print("1. Make sure PostgreSQL is running")
    print("2. Check username/password: user/admin")
    print("3. Verify database exists: olist_db")
    sys.exit(1)

# Define import order
import_order = [
    ("olist_customers_dataset", "customers"),
    ("olist_geolocation_dataset", "geolocation"),
    ("olist_sellers_dataset", "sellers"),
    ("olist_products_dataset", "products"),
    ("product_category_name_translation", "product_category_name_translation"),
    ("olist_orders_dataset", "orders"),
    ("olist_order_items_dataset", "order_items"),
    ("olist_order_payments_dataset", "order_payments"),
    ("olist_order_reviews_dataset", "order_reviews"),
]

def clean_and_import(file_name, table_name):
    print(f"📥 Loading {file_name} into {table_name}...")
    
    try:
        # Read CSV with explicit encoding
        df = pd.read_csv(f"./data/{file_name}.csv", encoding='utf-8-sig')
        
        # Clean column names
        df.columns = [col.lower().strip() for col in df.columns]
        
        # Handle date columns
        date_columns = [
            'order_purchase_timestamp', 'order_approved_at',
            'order_delivered_carrier_date', 'order_delivered_customer_date',
            'order_estimated_delivery_date', 'shipping_limit_date',
            'review_creation_date', 'review_answer_timestamp'
        ]
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Handle decimal columns
        decimal_cols = ['price', 'freight_value', 'payment_value']
        for col in decimal_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Import to PostgreSQL
        df.to_sql(table_name, engine, if_exists='replace', index=False)
        print(f"✅ Loaded {len(df)} rows into {table_name}")
        return True
        
    except FileNotFoundError:
        print(f"❌ File not found: ./data/{file_name}.csv")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

# Run the import
print("\n🚀 Starting import...")
success_count = 0
for file_name, table_name in import_order:
    if clean_and_import(file_name, table_name):
        success_count += 1

print(f"\n📊 Imported {success_count}/{len(import_order)} tables")

# Verification
if success_count > 0:
    try:
        with engine.connect() as conn:
            print("\n✅ Verification:")
            
            # Check counts
            result = conn.execute(text("""
                SELECT 
                    (SELECT COUNT(*) FROM customers) as customers,
                    (SELECT COUNT(*) FROM orders) as orders,
                    (SELECT COUNT(*) FROM order_items) as order_items
            """))
            row = result.fetchone()
            print(f"   Customers: {row.customers}")
            print(f"   Orders: {row.orders}")
            print(f"   Order Items: {row.order_items}")
            
            if row.customers > 0 and row.orders > 0:
                print("✅ Data loaded successfully!")
                
    except Exception as e:
        print(f"⚠️ Verification failed: {e}")
else:
    print("❌ No tables imported. Check file locations and formats.")

print("\n🎉 Done!")