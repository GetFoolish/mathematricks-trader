#!/bin/bash

# Script to set up branch protection rules for main and staging branches
# This script uses the GitHub CLI (gh) to configure branch protection
#
# Prerequisites:
# 1. Install GitHub CLI: https://cli.github.com/
# 2. Authenticate with: gh auth login
# 3. Ensure you have admin permissions on the repository
#
# This script is GENERIC and can be copied to any repository.
# It automatically detects the repository owner and name from git remote.

set -e

# Auto-detect repository owner and name from git remote
echo "Detecting repository information from git remote..."

# Get the remote URL
REMOTE_URL=$(git config --get remote.origin.url)

if [ -z "$REMOTE_URL" ]; then
    echo "Error: Could not detect git remote URL. Make sure you're in a git repository with a remote configured."
    exit 1
fi

# Parse owner and repo name from URL
# Handles both SSH (git@github.com:owner/repo.git) and HTTPS (https://github.com/owner/repo.git) formats
if [[ $REMOTE_URL =~ github\.com[:/]([^/]+)/([^/.]+)(\.git)?$ ]]; then
    REPO_OWNER="${BASH_REMATCH[1]}"
    REPO_NAME="${BASH_REMATCH[2]}"
else
    echo "Error: Could not parse GitHub repository from remote URL: $REMOTE_URL"
    exit 1
fi

echo "Detected repository: $REPO_OWNER/$REPO_NAME"
echo ""

# Ask for confirmation
read -p "Do you want to set up branch protection for $REPO_OWNER/$REPO_NAME? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted. No changes were made."
    exit 0
fi

echo "Setting up branch protection for $REPO_OWNER/$REPO_NAME"

# Function to protect a branch
protect_branch() {
    local BRANCH=$1
    echo "Protecting branch: $BRANCH"

    # Create the JSON payload
    # For organization repos, we can use "restrictions" to limit who can push
    # Only vandanchopra can push directly to protected branches
    local PAYLOAD=$(cat <<EOF
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1,
    "require_last_push_approval": false
  },
  "restrictions": {
    "users": ["vandanchopra"],
    "teams": [],
    "apps": []
  },
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": false
}
EOF
)

    echo "$PAYLOAD" | gh api \
        --method PUT \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "/repos/$REPO_OWNER/$REPO_NAME/branches/$BRANCH/protection" \
        --input -

    if [ $? -eq 0 ]; then
        echo "✓ Branch $BRANCH protected successfully"
    else
        echo "✗ Failed to protect branch $BRANCH"
        return 1
    fi
}

# Protect main branch
protect_branch "main"

# Protect staging branch
protect_branch "staging"

# Protect dev-test branch
protect_branch "dev-test"

echo ""
echo "Branch protection setup complete!"
echo ""
echo "Summary of protection rules:"
echo "- Pull requests require your approval (via CODEOWNERS file)"
echo "- Code owner reviews are required (only you can approve)"
echo "- Force pushes are disabled"
echo "- Branch deletions are disabled"
echo "- Stale reviews are dismissed when new commits are pushed"
echo "- Conversation resolution is required before merging"
echo ""
echo "IMPORTANT: Make sure to push the .github/CODEOWNERS file to your repo:"
echo "  git add .github/CODEOWNERS"
echo "  git commit -m 'Add CODEOWNERS for branch protection'"
echo "  git push"
