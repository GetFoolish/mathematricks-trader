#!/bin/bash

# Generate encryption key for authentication details
# This key is used to encrypt passwords, API keys, etc. in MongoDB

echo "==================================================================="
echo "  🔒 Encryption Key Generator for Authentication Details"
echo "==================================================================="
echo ""
echo "This will generate a secure encryption key for storing broker"
echo "credentials (passwords, API keys, etc.) in MongoDB."
echo ""
echo "⚠️  IMPORTANT: Keep this key secret and secure!"
echo "⚠️  If you lose it, you cannot decrypt existing credentials."
echo ""

# Generate key using Python
KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

echo "Generated encryption key:"
echo ""
echo "ENCRYPTION_KEY=$KEY"
echo ""

# Check if .env exists
if [ -f .env ]; then
    # Check if ENCRYPTION_KEY already exists in .env
    if grep -q "^ENCRYPTION_KEY=" .env; then
        echo "⚠️  ENCRYPTION_KEY already exists in .env file!"
        echo ""
        read -p "Do you want to REPLACE it? (yes/no): " replace
        if [ "$replace" = "yes" ]; then
            # Backup old .env
            cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
            echo "✅ Backed up .env to .env.backup.$(date +%Y%m%d_%H%M%S)"
            
            # Replace key
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                sed -i '' "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$KEY|" .env
            else
                # Linux
                sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$KEY|" .env
            fi
            echo "✅ Replaced ENCRYPTION_KEY in .env"
        else
            echo "❌ Cancelled. Keeping existing key."
            exit 0
        fi
    else
        # Add key to .env
        echo "ENCRYPTION_KEY=$KEY" >> .env
        echo "✅ Added ENCRYPTION_KEY to .env file"
    fi
else
    # Create new .env file
    echo "ENCRYPTION_KEY=$KEY" > .env
    echo "✅ Created new .env file with ENCRYPTION_KEY"
fi

echo ""
echo "==================================================================="
echo "  ✅ Setup Complete!"
echo "==================================================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Restart services to load new key:"
echo "   docker-compose restart account-data-service"
echo "   docker-compose restart execution-service"
echo ""
echo "2. Add credentials via frontend at http://localhost:5173"
echo "   → Fund Setup → Configure Accounts → Add Account"
echo ""
echo "3. Store backup of ENCRYPTION_KEY in a secure location"
echo "   (1Password, AWS Secrets Manager, etc.)"
echo ""
echo "⚠️  DO NOT commit .env file to Git!"
echo ""
