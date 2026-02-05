# Secure Authentication Details - Setup & Usage

## 🔒 Overview

Trading account credentials (passwords, API keys, API secrets) are now **encrypted at rest** in MongoDB using Fernet symmetric encryption (AES-128-CBC).

### What Gets Encrypted

The following fields in `authentication_details` are automatically encrypted:
- `password`
- `api_key`
- `api_secret`
- `access_token`
- `refresh_token`
- `client_secret`
- `private_key`

### What Stays Unencrypted

Non-sensitive fields remain in plain text for operational use:
- `host` (e.g., "127.0.0.1")
- `port` (e.g., 4001)
- `client_id` (e.g., 1)
- `username` (e.g., "trader_user")
- `auth_type` (e.g., "TWS")

---

## 🚀 Setup Instructions

### Step 1: Generate Encryption Key

Run the encryption utility to generate a secure key:

```bash
cd services/utils
python encryption.py
```

This will output something like:

```
=== Encryption Key Generator ===

Generated encryption key (add to .env file):

ENCRYPTION_KEY=xJ9k3mP2vL8dF1qR7tY4sN6hB5gV0wA9=

⚠️  Keep this key secret! If you lose it, you cannot decrypt existing data.
⚠️  Store it securely (e.g., AWS Secrets Manager, 1Password, etc.)
```

### Step 2: Add Key to Environment

**For Development** (local `.env` file):

```bash
# In mathematricks-trader root directory
echo "ENCRYPTION_KEY=xJ9k3mP2vL8dF1qR7tY4sN6hB5gV0wA9=" >> .env
```

**For Production** (Docker/Environment Variables):

```bash
# Docker Compose
services:
  account-data:
    environment:
      - ENCRYPTION_KEY=xJ9k3mP2vL8dF1qR7tY4sN6hB5gV0wA9=

# Or Kubernetes Secret
kubectl create secret generic encryption-key \
  --from-literal=ENCRYPTION_KEY='xJ9k3mP2vL8dF1qR7tY4sN6hB5gV0wA9='
```

### Step 3: Restart Services

```bash
docker-compose restart account-data-service
docker-compose restart execution-service
```

---

## 🖥️ Adding Credentials via Frontend

### Using the Fund Setup Wizard

1. **Navigate** to Fund Setup → Step 2: Configure Accounts
2. Click **"Add Account"**
3. Fill in account details:
   - **Account ID**: `IBKR_Main`
   - **Broker**: Select `IBKR`
   - **Fund Assignment**: Select your fund

4. **Authentication Details Section** (🔒 Encrypted at rest):

   **For IBKR**:
   - Host: `127.0.0.1`
   - Port: `4001` (live) or `4004` (paper)
   - Client ID: `1` (must be in 1-99 range for Execution)
   - Username: (optional - for auto-login)
   - Password: (optional - for auto-login)

   **For Binance/Alpaca**:
   - API Key: `your_api_key_here`
   - API Secret: `your_api_secret_here` (shown as password field)

5. Click **"Create Account"**

The credentials are automatically encrypted before being sent to MongoDB.

---

## 🔐 How Encryption Works

### When Creating an Account

```
Frontend Input (Plain Text)
   ↓
   POST /accounts
   ↓
Account Data Service
   ↓
encrypt_authentication_details()
   ↓
MongoDB (Encrypted)
{
  "authentication_details": {
    "host": "127.0.0.1",  // Plain text
    "port": 4001,          // Plain text
    "username": "trader",  // Plain text
    "password": "enc:gAAAAABl9Kx..."  // ENCRYPTED ✅
    "api_key": "enc:gAAAAABl9Ky..."    // ENCRYPTED ✅
  }
}
```

### When Using Credentials

```
MongoDB (Encrypted)
   ↓
Execution Service reads account
   ↓
decrypt_authentication_details()
   ↓
Broker Connection (Plain Text in memory only)
```

---

## 📝 MongoDB Storage Format

### Before Encryption

```json
{
  "_id": "IBKR_Main",
  "authentication_details": {
    "auth_type": "TWS",
    "host": "127.0.0.1",
    "port": 4001,
    "client_id": 1,
    "username": "trader",
    "password": "my_secret_password"  // ❌ PLAIN TEXT - INSECURE
  }
}
```

### After Encryption

```json
{
  "_id": "IBKR_Main",
  "authentication_details": {
    "auth_type": "TWS",
    "host": "127.0.0.1",
    "port": 4001,
    "client_id": 1,
    "username": "trader",
    "password": "enc:gAAAAABl9KxF8r3qY..."  // ✅ ENCRYPTED
  }
}
```

All values starting with `enc:` are encrypted.

---

## 🛡️ Security Best Practices

### ✅ DO

- **Store `ENCRYPTION_KEY` in a secret manager** (AWS Secrets Manager, HashiCorp Vault, 1Password)
- **Rotate encryption keys** periodically (see Key Rotation section below)
- **Restrict MongoDB access** (use authentication, firewall rules)
- **Use HTTPS/TLS** for all API communication
- **Audit access logs** regularly

### ❌ DON'T

- **Don't commit `ENCRYPTION_KEY` to Git**
- **Don't share keys via email/Slack**
- **Don't store keys in plain text files** on servers
- **Don't use the same key across environments** (dev/staging/prod should have different keys)
- **Don't disable encryption** for "convenience"

---

## 🔄 Key Rotation

If you need to rotate the encryption key:

### Step 1: Generate New Key

```bash
python services/utils/encryption.py
```

Copy the new key.

### Step 2: Decrypt All Existing Data with Old Key

```python
# scripts/rotate_encryption_key.py
from pymongo import MongoClient
from services.utils.encryption import decrypt_authentication_details, encrypt_authentication_details
import os

# Set OLD key
os.environ['ENCRYPTION_KEY'] = 'OLD_KEY_HERE'
from services.utils import encryption as old_encryption

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27018")
db = client.mathematricks_trading

# Decrypt all accounts with old key
accounts = list(db.trading_accounts.find({}))
for account in accounts:
    if 'authentication_details' in account:
        # Decrypt with old key
        decrypted = old_encryption.decrypt_authentication_details(account['authentication_details'])
        
        # Re-encrypt with new key (reload module with new key)
        import importlib
        os.environ['ENCRYPTION_KEY'] = 'NEW_KEY_HERE'
        importlib.reload(encryption)
        
        encrypted = encryption.encrypt_authentication_details(decrypted)
        
        # Update in DB
        db.trading_accounts.update_one(
            {'_id': account['_id']},
            {'$set': {'authentication_details': encrypted}}
        )

print("Key rotation complete!")
```

### Step 3: Update Environment

```bash
# Update .env with new key
ENCRYPTION_KEY=NEW_KEY_HERE

# Restart services
docker-compose restart
```

---

## 🧪 Testing Encryption

### Manual Test

```python
from services.utils.encryption import encrypt_value, decrypt_value

# Encrypt
encrypted = encrypt_value("my_secret_password")
print(f"Encrypted: {encrypted}")
# Output: enc:gAAAAABl9KxF8r3qY...

# Decrypt
decrypted = decrypt_value(encrypted)
print(f"Decrypted: {decrypted}")
# Output: my_secret_password
```

### Verify in MongoDB

```bash
# Connect to MongoDB
docker exec -it mathematricks-trader-mongodb-1 mongosh --port 27018

use mathematricks_trading

# Check an account's authentication_details
db.trading_accounts.findOne({_id: "IBKR_Main"}, {authentication_details: 1})

# Should see:
# {
#   authentication_details: {
#     password: "enc:gAAAAABl...",  // Encrypted ✅
#     api_key: "enc:gAAAAABm...",   // Encrypted ✅
#   }
# }
```

---

## ⚠️ Troubleshooting

### Error: "ENCRYPTION_KEY not set in environment"

**Solution**: Add to `.env` file:
```bash
ENCRYPTION_KEY=<your_key_here>
```

### Error: "Failed to initialize cipher: Invalid key"

**Cause**: `ENCRYPTION_KEY` is not a valid Fernet key.

**Solution**: Regenerate key using `python services/utils/encryption.py`

### Error: "Decryption failed"

**Cause**: Encrypted data was encrypted with a different key.

**Solution**: 
1. Check that `ENCRYPTION_KEY` matches the key used to encrypt
2. If key was rotated, run key rotation script

### Frontend shows encrypted value "enc:gAA..."

**Cause**: Backend didn't decrypt before sending to frontend.

**Solution**: Check that service is calling `decrypt_authentication_details()` before returning data.

---

## 📚 Related Documentation

- [Account Data Service](../account_data_service.md) - Full API reference
- [IBKR Integration](../IBKR_INTEGRATION_SUMMARY.md) - IBKR-specific setup
- [MongoDB Schemas](../mongodb_schemas.md) - Database structure

---

## 🔍 FAQ

**Q: Can I see my decrypted passwords in the frontend?**
A: No. Passwords are encrypted before storage and only decrypted when needed for broker connections. The frontend never receives decrypted credentials.

**Q: What if I lose my ENCRYPTION_KEY?**
A: You will not be able to decrypt existing credentials. You'll need to manually re-enter all credentials through the frontend.

**Q: Can I use different keys for different accounts?**
A: Currently, all accounts use the same `ENCRYPTION_KEY`. If you need per-account encryption, you'd need to extend the encryption utility to support key IDs.

**Q: Is Fernet encryption secure enough for production?**
A: Yes. Fernet uses AES-128 in CBC mode with HMAC for authentication. It's recommended by Python's cryptography library for general-purpose encryption. For higher security requirements, consider:
- External secret managers (AWS Secrets Manager, HashiCorp Vault)
- Hardware Security Modules (HSMs)
- Envelope encryption (encrypt the encryption key with a master key)

**Q: How do I backup encrypted data?**
A: Standard MongoDB backups work fine. As long as you backup the `ENCRYPTION_KEY` separately, you can restore and decrypt the data.

---

*Last Updated: 2024-01-15*  
*Version: 1.0*
