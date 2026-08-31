#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/sync_gmail.py — CLI tool for running Gmail synchronization in dry-run or approved mode.

Usage:
  # Dry-run inspection (default):
  python scripts/sync_gmail.py

  # Dry-run with date filter:
  python scripts/sync_gmail.py --after-date 2026-08-01

  # Apply mutations (requires interactive confirmation):
  python scripts/sync_gmail.py --apply
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from career_os.config import load_dotenv, get_canonical_redirect_uri
from career_os.db.repository import CareerOSRepository
from career_os.email import (
    TokenStore,
    LocalSecureFileTokenStore,
    GoogleOAuthClient,
    EmailSyncService,
    MockEmailAdapter,
    GmailEmailAdapter,
    EmailClassifier,
    OpportunityMatcher,
    format_dry_run_report,
)

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Career OS Gmail Synchronization & Lifecycle Tracking")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run in preview mode without SQLite mutations (default: True)")
    parser.add_argument("--apply", action="store_true", help="Explicitly enable live SQLite database mutation")
    parser.add_argument("--adapter", choices=["auto", "gmail", "mock"], default="auto", help="Email adapter to use (default: auto)")
    parser.add_argument("--account", type=str, default=None, help="Account email address")
    parser.add_argument("--after-date", type=str, default=None, help="Fetch emails after this date (YYYY-MM-DD)")
    parser.add_argument("--max-results", type=int, default=50, help="Maximum messages to scan (default: 50)")
    parser.add_argument("--yes", action="store_true", help="Skip interactive approval prompt when --apply is used")

    args = parser.parse_args()

    db_path = BASE_DIR / "career_os.db"
    repo = CareerOSRepository(db_path=str(db_path))
    repo.init_db()
    token_store = LocalSecureFileTokenStore()
    oauth_client = GoogleOAuthClient(token_store=token_store)

    accounts = token_store.list_accounts("gmail")
    account_email = args.account or (accounts[0] if accounts else None)

    # Determine adapter
    if args.adapter == "gmail" or (args.adapter == "auto" and account_email and token_store.has_token("gmail", account_email)):
        if not account_email or not token_store.has_token("gmail", account_email):
            print(f"[!] Error: Gmail account '{account_email}' is not authenticated.")
            print("    Please run OAuth authentication or set GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET in .env.")
            sys.exit(1)
        adapter = GmailEmailAdapter(account_email=account_email, token_store=token_store, oauth_client=oauth_client)
        print(f"[*] Using Live Gmail Adapter for account: {account_email}")
    else:
        adapter = MockEmailAdapter()
        print("[*] Using Deterministic Mock Email Adapter")

    sync_service = EmailSyncService(
        adapter=adapter,
        repository=repo,
        classifier=EmailClassifier(),
        matcher=OpportunityMatcher(),
    )

    # Phase 1: Always execute dry run preview first
    print("\n[*] Running Dry-Run inspection...\n")
    dry_report = sync_service.run_sync(
        max_results=args.max_results,
        after_date=args.after_date,
        dry_run=True,
    )
    print(format_dry_run_report(dry_report))

    if not args.apply:
        print("\n[i] Preview completed. To apply proposed mutations, run with '--apply'.")
        return

    # Phase 2: Human Approval Mechanism
    if not args.yes:
        confirm = input("\n[?] Do you approve applying these state transitions to Career OS? (yes/no): ").strip().lower()
        if confirm not in ("yes", "y"):
            print("[-] Aborted. No changes were applied to SQLite.")
            return

    # Phase 3: Controlled Live Mutation
    print("\n[*] Applying mutations to SQLite database...")
    live_report = sync_service.run_sync(
        max_results=args.max_results,
        after_date=args.after_date,
        dry_run=False,
    )
    print(format_dry_run_report(live_report))
    print("[+] Live synchronization completed successfully.")


if __name__ == "__main__":
    main()
