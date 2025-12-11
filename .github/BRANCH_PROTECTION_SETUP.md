# Branch Protection Setup

This directory contains **GENERIC, REUSABLE** configuration files to protect the `main` and `staging` branches, ensuring only you (vandanchopra) can make changes to them.

**✨ COPY THIS ENTIRE `.github` FOLDER TO ANY OF YOUR REPOSITORIES! ✨**

All files are repository-agnostic and will automatically detect the repository information.

## Files Created

1. **CODEOWNERS** - Defines you as the code owner for all files (GENERIC - works in any repo)
2. **branch-protection-config.json** - Configuration template for branch protection rules (GENERIC - works in any repo)
3. **setup-branch-protection.sh** - Automated script that auto-detects repo info and applies branch protection (GENERIC - works in any repo)

## Setup Instructions

### Option 1: Using GitHub CLI (Recommended - Fully Automated)

1. **Copy this `.github` folder to any repository** (only needed once per repo)

2. Install GitHub CLI if you haven't already (only needed once on your machine):
   ```bash
   # macOS
   brew install gh

   # Or download from: https://cli.github.com/
   ```

3. Authenticate with GitHub (only needed once on your machine):
   ```bash
   gh auth login
   ```

4. Run the setup script (it will auto-detect the repo):
   ```bash
   cd .github
   ./setup-branch-protection.sh
   ```

   The script will automatically:
   - Detect the repository owner and name from your git remote
   - Apply branch protection to `main` and `staging` branches
   - No manual configuration needed!

5. Push the CODEOWNERS file to your repository:
   ```bash
   git add .github/CODEOWNERS
   git commit -m "Add CODEOWNERS file for branch protection"
   git push
   ```

### Option 2: Manual Setup via GitHub UI

If you prefer to configure via the UI (or as a backup), follow these steps:

1. **Push the CODEOWNERS file first:**
   ```bash
   git add .github/CODEOWNERS
   git commit -m "Add CODEOWNERS file for branch protection"
   git push
   ```

2. **Configure branch protection for `main` branch:**
   - Go to your repository on GitHub
   - Navigate to: Settings → Branches → Add branch protection rule
   - Branch name pattern: `main`
   - Enable these settings:
     - ✅ Require a pull request before merging
       - ✅ Require approvals (1 required)
       - ✅ Dismiss stale pull request approvals when new commits are pushed
       - ✅ Require review from Code Owners
     - ✅ Restrict who can push to matching branches
       - Add: `vandanchopra`
     - ✅ Do not allow bypassing the above settings (Enforce admins)
     - ✅ Require conversation resolution before merging
     - ❌ Allow force pushes (keep disabled)
     - ❌ Allow deletions (keep disabled)

3. **Repeat step 2 for `staging` branch:**
   - Create another branch protection rule
   - Branch name pattern: `staging`
   - Apply the same settings as above

## Quick Setup Across Multiple Repositories

Since this folder is completely generic, you can:

1. **Copy the entire `.github` folder** to any other repository
2. **Run the script** - it will automatically detect the repository
3. **Done!** No manual editing required

Example:
```bash
# Copy to another repo
cp -r /path/to/this/repo/.github /path/to/another/repo/

# Go to the other repo and run
cd /path/to/another/repo/.github
./setup-branch-protection.sh
```

## What These Rules Do

Once configured, the branch protection rules will:

1. **Prevent direct pushes** - Only you can push, and only via approved pull requests
2. **Require code review** - All PRs must be approved by you (the code owner)
3. **Block force pushes** - Nobody can force push to these branches
4. **Prevent deletion** - The branches cannot be deleted
5. **Require conversation resolution** - All PR comments must be resolved before merging

## Verifying Protection

After setup, verify the protection is active:

```bash
# The script automatically detects your repo, or you can check manually:
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
gh api /repos/$REPO/branches/main/protection
gh api /repos/$REPO/branches/staging/protection
```

Or visit your repository's settings page:
- `https://github.com/<your-username>/<your-repo>/settings/branches`

## Important Notes

- The CODEOWNERS file must be pushed to the repository before branch protection takes full effect
- You need admin permissions on the repository to set up branch protection
- Branch protection rules are stored on GitHub's servers, not in the repository files (except CODEOWNERS)
- The configuration files in this directory serve as documentation and automation tools

## Troubleshooting

If you encounter issues:

1. **"Resource not accessible by personal access token"**
   - Ensure your GitHub token has `repo` scope
   - Re-authenticate with: `gh auth login`

2. **"Branch not found"**
   - Make sure the branches exist on GitHub
   - Push them first: `git push origin main staging`

3. **CODEOWNERS not working**
   - Ensure the file is in `.github/CODEOWNERS` (this exact path)
   - Make sure it's pushed to the repository
   - Wait a few minutes for GitHub to process the change
