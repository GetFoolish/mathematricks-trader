#!/usr/bin/env python3
"""
Migrate existing trading_accounts to use encrypted authentication_details.

This script:
1. Connects to MongoDB
2. Reads all trading_accounts
3. Encrypts sensitive fields in authentication_details
4. Updates MongoDB with encrypted values

Run this ONCE after setting up ENCRYPTION_KEY in .env
"""
import os
import sys
from pymongo import MongoClient
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services.utils.encryption import (
    encrypt_authentication_details,
    is_encrypted,
    SENSITIVE_FIELDS
)

# MongoDB connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27018')
DATABASE_NAME = os.getenv('MONGO_DB_NAME', 'mathematricks_trading')


def migrate_accounts(dry_run=True):
    """
    Encrypt authentication details for all existing accounts.
    
    Args:
        dry_run: If True, only show what would be changed without updating
    """
    print("=" * 70)
    print("  🔒 Authentication Details Encryption Migration")
    print("=" * 70)
    print()
    
    # Check for encryption key
    if not os.getenv('ENCRYPTION_KEY'):
        print("❌ ERROR: ENCRYPTION_KEY not set in environment!")
        print()
        print("Please run:")
        print("  ./scripts/generate_encryption_key.sh")
        print()
        sys.exit(1)
    
    print(f"Connecting to MongoDB: {MONGO_URI}")
    print(f"Database: {DATABASE_NAME}")
    print()
    
    # Connect to MongoDB
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    accounts_collection = db.trading_accounts
    
    # Find all accounts
    accounts = list(accounts_collection.find({}))
    print(f"Found {len(accounts)} trading accounts")
    print()
    
    if len(accounts) == 0:
        print("✅ No accounts to migrate")
        return
    
    # Track statistics
    total_accounts = len(accounts)
    accounts_updated = 0
    accounts_skipped = 0
    accounts_errors = 0
    
    for account in accounts:
        account_id = account.get('_id') or account.get('account_id')
        auth_details = account.get('authentication_details', {})
        
        if not auth_details:
            print(f"⏭️  {account_id}: No authentication_details, skipping")
            accounts_skipped += 1
            continue
        
        # Check if already encrypted
        already_encrypted = False
        for field in SENSITIVE_FIELDS:
            if field in auth_details:
                value = auth_details[field]
                if value and is_encrypted(str(value)):
                    already_encrypted = True
                    break
        
        if already_encrypted:
            print(f"✅ {account_id}: Already encrypted, skipping")
            accounts_skipped += 1
            continue
        
        # Show what will be encrypted
        fields_to_encrypt = []
        for field in SENSITIVE_FIELDS:
            if field in auth_details and auth_details[field]:
                fields_to_encrypt.append(field)
        
        if not fields_to_encrypt:
            print(f"⏭️  {account_id}: No sensitive fields to encrypt, skipping")
            accounts_skipped += 1
            continue
        
        print(f"🔒 {account_id}:")
        print(f"   Broker: {account.get('broker', 'Unknown')}")
        print(f"   Fields to encrypt: {', '.join(fields_to_encrypt)}")
        
        if dry_run:
            print(f"   [DRY RUN] Would encrypt these fields")
            accounts_updated += 1
            continue
        
        # Encrypt the authentication details
        try:
            encrypted_auth = encrypt_authentication_details(auth_details)
            
            # Update in MongoDB
            result = accounts_collection.update_one(
                {'_id': account['_id']},
                {
                    '$set': {
                        'authentication_details': encrypted_auth,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                print(f"   ✅ Encrypted and updated in MongoDB")
                accounts_updated += 1
            else:
                print(f"   ⚠️  MongoDB update returned 0 modified")
                accounts_errors += 1
                
        except Exception as e:
            print(f"   ❌ Error encrypting: {e}")
            accounts_errors += 1
    
    # Summary
    print()
    print("=" * 70)
    print("  Migration Summary")
    print("=" * 70)
    print(f"Total accounts:     {total_accounts}")
    print(f"Accounts updated:   {accounts_updated}")
    print(f"Accounts skipped:   {accounts_skipped}")
    print(f"Errors:             {accounts_errors}")
    print()
    
    if dry_run:
        print("⚠️  This was a DRY RUN - no changes were made to MongoDB")
        print()
        print("To apply changes, run:")
        print(f"  python {sys.argv[0]} --apply")
    else:
        print("✅ Migration complete!")
        print()
        print("Next steps:")
        print("1. Restart services to use encrypted credentials:")
        print("   docker-compose restart account-data-service execution-service")
        print()
        print("2. Verify encryption in MongoDB:")
        print("   docker exec -it mathematricks-trader-mongodb-1 mongosh --port 27018")
        print("   use mathematricks_trading")
        print("   db.trading_accounts.findOne({}, {authentication_details: 1})")
    
    print()


if __name__ == "__main__":
    # Check if --apply flag is passed
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == '--apply':
        print()
        print("⚠️  WARNING: This will MODIFY your MongoDB database!")
        print("⚠️  Make sure you have a backup of your database.")
        print()
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Cancelled.")
            sys.exit(0)
        dry_run = False
    
    migrate_accounts(dry_run=dry_run)
