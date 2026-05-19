#!/usr/bin/env bash
# Usage: CF_ACCOUNT_ID=... CF_API_TOKEN=... gh auth login
# Then run: ./set_github_secrets.sh
# This script sets GitHub repo secrets for Cloudflare Worker deploy via GitHub Actions.

set -euo pipefail

REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"

if [ -z "${CF_API_TOKEN:-}" ] || [ -z "${CF_ACCOUNT_ID:-}" ]; then
  echo "Please export CF_API_TOKEN and CF_ACCOUNT_ID as environment variables before running."
  echo "Example: export CF_API_TOKEN='xxx' && export CF_ACCOUNT_ID='yyy' && ./set_github_secrets.sh"
  exit 1
fi

echo "Setting CF_API_TOKEN secret for $REPO"
printf "%s" "$CF_API_TOKEN" | gh secret set CF_API_TOKEN --repo "$REPO" --body -

echo "Setting CF_ACCOUNT_ID secret for $REPO"
printf "%s" "$CF_ACCOUNT_ID" | gh secret set CF_ACCOUNT_ID --repo "$REPO" --body -

echo "Secrets set. Commit and push to main to trigger deploy action."
