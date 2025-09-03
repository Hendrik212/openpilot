# Upstream Merge Guide for ISLA Fork

This guide documents the process for merging upstream changes from the main openpilot repository and opendbc submodule into the ISLA fork while preserving custom modifications.

## Prerequisites

- Ensure you have proper remotes configured:
  ```bash
  git remote -v
  # Should show:
  # origin    https://github.com/Hendrik212/openpilot.git (fetch/push)
  # upstream  https://github.com/commaai/openpilot.git (fetch/push)
  ```

- If upstream remote doesn't exist, add it:
  ```bash
  git remote add upstream https://github.com/commaai/openpilot.git
  ```

## Step-by-Step Merge Process

### 1. Prepare for Merge

```bash
# Ensure you're on the correct branch
git checkout isla-master

# Check current status
git status
```

### 2. Fetch Latest Changes

```bash
# Fetch from all remotes including submodules
git fetch upstream
git fetch origin

# This will also fetch submodule updates automatically
```

### 3. Handle Main Repository Merge

```bash
# Attempt to merge upstream changes
git merge upstream/master
```

**If merge succeeds without conflicts:**
- Skip to step 5 (Commit and Push)

**If submodule conflicts occur (common case):**
- You'll see an error about submodule conflicts
- Continue to step 4

### 4. Handle Submodule Conflicts

When you see submodule merge conflicts, follow these steps:

```bash
# Navigate to the opendbc submodule
cd opendbc_repo

# Check submodule status
git status

# Fetch upstream changes for opendbc
git fetch upstream

# Merge upstream opendbc changes
git merge upstream/master

# If there are conflicts in the submodule, resolve them manually:
# - Edit conflicted files
# - git add <resolved-files>
# - git commit

# Return to main repository
cd ..

# Add the updated submodule
git add opendbc_repo

# Check that conflicts are resolved
git status
```

### 5. Commit and Push

```bash
# Complete the merge commit
git commit -m "$(cat <<'EOF'
Merge upstream master with latest opendbc updates

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# Push opendbc submodule changes first
cd opendbc_repo
git push origin master
cd ..

# Push main repository changes
git push origin isla-master
```

## Common Scenarios and Solutions

### Scenario 1: Clean Merge (No Conflicts)
- Both main repo and submodules merge cleanly
- Simply commit and push

### Scenario 2: Submodule Conflicts Only
- Main repo merges cleanly
- Submodule has conflicts or needs manual merge
- Follow step 4 above

### Scenario 3: Main Repository Conflicts
```bash
# If main repo files have conflicts
git status  # Shows conflicted files

# Resolve conflicts manually:
# 1. Edit each conflicted file
# 2. Remove conflict markers (<<<<<<< ======= >>>>>>>)
# 3. Keep desired changes from both versions

# After resolving all conflicts:
git add <resolved-files>
git commit  # Complete the merge
```

### Scenario 4: Authentication Issues
```bash
# If push fails due to authentication:
# 1. Generate new GitHub personal access token
# 2. Update remote URL with token:
git remote set-url origin https://USERNAME:TOKEN@github.com/Hendrik212/openpilot.git

# Or push with explicit credentials:
git push https://USERNAME:TOKEN@github.com/Hendrik212/openpilot.git isla-master
```

## Important Notes

### Preserving ISLA Modifications
- The merge process preserves all custom ISLA modifications
- Custom changes in the following files are maintained:
  - `opendbc_repo/opendbc/car/hyundai/hyundaicanfd.py`
  - `opendbc_repo/opendbc/car/hyundai/carcontroller.py`
  - `opendbc_repo/opendbc/car/hyundai/carstate.py`
  - `opendbc_repo/opendbc/safety/modes/hyundai_canfd.h`
  - `opendbc_repo/opendbc/dbc/generator/hyundai/hyundai_canfd.dbc`

### Submodule Best Practices
- Always handle submodule merges before committing main repo
- Push submodule changes before pushing main repo changes
- Verify submodule commits are accessible on remote before pushing main repo

### Verification Steps
After successful merge:
```bash
# Verify merge commit
git log --oneline -5

# Check submodule status
git submodule status

# Verify ISLA modifications are intact
git log --oneline --grep="ISLA" -10
```

## Troubleshooting

### "Not a git repository" Error in Submodule
```bash
# Re-initialize submodules
git submodule update --init --recursive
```

### "ahead of origin/master" Warning
- This is expected for the isla-master branch
- It indicates your branch has commits not in the upstream master

### Failed Authentication
- Check if GitHub token has expired
- Ensure token has proper repository permissions
- Consider using SSH keys instead of HTTPS for authentication

## Emergency Recovery

If merge goes wrong:
```bash
# Abort ongoing merge
git merge --abort

# Reset to last known good state
git reset --hard HEAD~1

# Or reset to specific commit
git reset --hard <commit-hash>
```

---

This guide should be followed each time upstream changes need to be integrated into the ISLA fork to ensure consistency and preserve all custom modifications.