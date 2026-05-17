# GitHub PR Workflow

This document is the required checklist for opening pull requests from this
repository. The goal is to prevent empty or stale PRs where the remote branch
does not contain the local commit.

## Hard Rule

Do not open a pull request until the GitHub remote branch contains the exact
local commit that is intended for review.

Before creating the PR, these two values must match:

```bash
git rev-parse HEAD
git ls-remote origin "$(git branch --show-current)"
```

If they do not match, stop. Do not open the PR.

## Normal PR Flow

1. Inspect the local state:

   ```bash
   git status -sb
   git diff --stat
   git log --oneline --decorate -5
   ```

2. Commit the intended changes:

   ```bash
   git add <explicit files>
   git commit -m "<type>: <short description>"
   ```

3. Run the required checks for the change.

4. Push the current branch:

   ```bash
   git push -u origin "$(git branch --show-current)"
   ```

5. Verify that GitHub has the same commit:

   ```bash
   LOCAL_SHA="$(git rev-parse HEAD)"
   REMOTE_SHA="$(git ls-remote origin "$(git branch --show-current)" | awk '{print $1}')"
   test "$LOCAL_SHA" = "$REMOTE_SHA"
   ```

6. Open the PR only after the SHA check passes.

7. Verify the PR after creation:

   - base branch is `main`;
   - head branch is the current feature branch;
   - PR head SHA equals `git rev-parse HEAD`;
   - changed files and diff match the local commit.

## If Push Fails

Stop and fix authentication before opening a PR.

Do not open a PR on an old remote branch.

Common blockers:

- `Permission denied to deploy key`: the SSH key is a deploy key without write
  permission or belongs to a different repository.
- `could not read Username for 'https://github.com'`: HTTPS credentials are not
  configured.
- `gh: command not found`: GitHub CLI is not installed, so it cannot be used for
  authentication or PR creation.

Acceptable fixes:

- use a GitHub SSH key with write access to `Valerii-S84/Shorts-Factory-Backend`;
- configure HTTPS credentials or a PAT with repository write access;
- install and authenticate GitHub CLI, then use `gh auth status` to verify.

After fixing auth, rerun the push and SHA check. Only then open the PR.

## Do Not Use These Shortcuts

Do not use low-level GitHub API blob/tree/commit calls to bypass a failed git
push unless the user explicitly approves that recovery path.

Do not create or keep a PR open if its remote head SHA does not contain the
intended local commit.

## Recovery From A Stale PR

If a PR was opened before the branch was pushed:

1. Do not merge it.
2. Push the missing local commit to the same head branch.
3. Verify that the PR head SHA updated to the local `HEAD`.
4. If the stale PR was already merged, create a new branch from the updated
   `main`, cherry-pick or reapply the missing commit, push it, and open a new PR
   only after the SHA check passes.

## Sync Local Main After Merge

After a PR is merged on GitHub:

```bash
git fetch --prune origin
git switch main
git branch --set-upstream-to=origin/main main
git pull --ff-only origin main
git status -sb
git log --oneline --decorate -5
```

Do not use `git reset --hard` unless the user explicitly asks for destructive
local cleanup.
