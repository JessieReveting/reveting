#!/usr/bin/env python3
"""
Stripe Payment Link Generator for GoTech Solutions
===================================================

Creates Stripe Checkout Sessions and Payment Links for all service tiers.

Setup:
  1. Get your Stripe API key from https://dashboard.stripe.com/apikeys
  2. Set environment variable:
       export STRIPE_SECRET_KEY=sk_test_...  # for testing
       export STRIPE_SECRET_KEY=sk_live_...  # for production
  3. Install dependencies:
       pip install stripe qrcode

Usage:
  python stripe-links.py --service ai-ops --plan monthly --quantity 1
  python stripe-links.py --service bundle --plan annual --quantity 2 --customer-email client@example.com
  python stripe-links.py --service destiny-college --plan application-fee
  python stripe-links.py --dry-run --service ai-ops --plan monthly
  python stripe-links.py --list
  python stripe-links.py --create-product --service ai-ops --plan monthly
  python stripe-links.py --stats
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import stripe
except ImportError:
    stripe = None

try:
    import qrcode
except ImportError:
    qrcode = None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_FILE = SCRIPT_DIR / "stripe-links-log.json"

# Price catalog — maps (service, plan) -> dict with amount (cents), price_id, description
# Replace price_* placeholders with real Stripe Price IDs after creating them.
PRICE_CATALOG = {
    ("ai-ops", "monthly"): {
        "amount": 500_00,
        "price_id": "price_ai_ops_monthly",
        "name": "AI Ops — Monthly",
        "description": "AI Operations service, monthly billing",
    },
    ("ai-ops", "annual"): {
        "amount": 5_000_00,
        "price_id": "price_ai_ops_annual",
        "name": "AI Ops — Annual",
        "description": "AI Operations service, annual billing (2 months free)",
    },
    ("communications", "monthly"): {
        "amount": 300_00,
        "price_id": "price_communications_monthly",
        "name": "Communications — Monthly",
        "description": "Communications service, monthly billing",
    },
    ("communications", "annual"): {
        "amount": 3_000_00,
        "price_id": "price_communications_annual",
        "name": "Communications — Annual",
        "description": "Communications service, annual billing",
    },
    ("cro", "monthly"): {
        "amount": 750_00,
        "price_id": "price_cro_monthly",
        "name": "CRO — Monthly",
        "description": "Conversion Rate Optimization service, monthly billing",
    },
    ("cro", "annual"): {
        "amount": 7_500_00,
        "price_id": "price_cro_annual",
        "name": "CRO — Annual",
        "description": "Conversion Rate Optimization service, annual billing",
    },
    ("golive", "monthly"): {
        "amount": 400_00,
        "price_id": "price_golive_monthly",
        "name": "GoLive — Monthly",
        "description": "GoLive service, monthly billing",
    },
    ("golive", "annual"): {
        "amount": 4_000_00,
        "price_id": "price_golive_annual",
        "name": "GoLive — Annual",
        "description": "GoLive service, annual billing",
    },
    ("bundle", "monthly"): {
        "amount": 1_750_00,
        "price_id": "price_bundle_monthly",
        "name": "Bundle — Monthly",
        "description": "Full bundle (AI Ops + Communications + CRO + GoLive), monthly billing",
    },
    ("bundle", "annual"): {
        "amount": 17_500_00,
        "price_id": "price_bundle_annual",
        "name": "Bundle — Annual",
        "description": "Full bundle (AI Ops + Communications + CRO + GoLive), annual billing",
    },
    ("destiny-college", "application-fee"): {
        "amount": 7_500,
        "price_id": "price_destiny_application_fee",
        "name": "Destiny College — Application Fee",
        "description": "One-time application fee for Destiny College",
    },
    ("destiny-college", "tuition-deposit"): {
        "amount": 50_000,
        "price_id": "price_destiny_tuition_deposit",
        "name": "Destiny College — Tuition Deposit",
        "description": "Tuition deposit for Destiny College",
    },
}

SERVICES = ["ai-ops", "communications", "cro", "golive", "bundle", "destiny-college"]
PLANS = ["monthly", "annual", "application-fee", "tuition-deposit"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_stripe_key():
    """Retrieve Stripe API key from environment."""
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        print("=" * 60)
        print("ERROR: STRIPE_SECRET_KEY environment variable not set.")
        print()
        print("To get your Stripe API key:")
        print("  1. Go to https://dashboard.stripe.com/apikeys")
        print("  2. Copy your Secret Key (sk_test_... for test mode,")
        print("     or sk_live_... for production)")
        print("  3. Set the environment variable:")
        print("     export STRIPE_SECRET_KEY=sk_test_your_key_here")
        print("=" * 60)
        sys.exit(1)
    return key


def format_amount(cents):
    """Format cents as dollar string."""
    return f"${cents / 100:,.2f}"


def load_log():
    """Load existing log entries."""
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_log(entries):
    """Save log entries to file."""
    with open(LOG_FILE, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def log_entry(entry):
    """Append an entry to the log file."""
    entries = load_log()
    entries.append(entry)
    save_log(entries)


def print_qr_ascii(url):
    """Print ASCII art QR code for the given URL."""
    if qrcode is None:
        print("\n[QR code requires: pip install qrcode]")
        print(f"  URL: {url}\n")
        return

    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)
        # Print to terminal
        print()
        for row in qr.modules:
            line = ""
            for cell in row:
                line += "██" if cell else "  "
            print(f"  {line}")
        print()
    except Exception as e:
        print(f"\n[Could not generate QR code: {e}]")
        print(f"  URL: {url}\n")


# ---------------------------------------------------------------------------
# Stripe operations
# ---------------------------------------------------------------------------

def create_checkout_session(service, plan, quantity, customer_email, metadata, success_url, cancel_url, dry_run):
    """Create a Stripe Checkout Session."""
    price_info = PRICE_CATALOG.get((service, plan))
    if not price_info:
        print(f"ERROR: Unknown service/plan combination: {service}/{plan}")
        sys.exit(1)

    price_id = price_info["price_id"]
    amount = price_info["amount"]
    name = price_info["name"]

    if dry_run:
        print("=" * 60)
        print("  DRY RUN — No API call will be made")
        print("=" * 60)
        print(f"  Service:       {service}")
        print(f"  Plan:          {plan}")
        print(f"  Product:       {name}")
        print(f"  Price ID:      {price_id}")
        print(f"  Amount:        {format_amount(amount)}")
        print(f"  Quantity:      {quantity}")
        print(f"  Customer:      {customer_email or '(none)'}")
        print(f"  Metadata:      {metadata or '(none)'}")
        print(f"  Success URL:   {success_url or '(default)'}")
        print(f"  Cancel URL:    {cancel_url or '(default)'}")
        print()

        # Generate a fake URL for display
        fake_url = f"https://checkout.stripe.com/pay/cs_test_{'x' * 32}"
        print(f"  [DRY RUN] Payment URL: {fake_url}")
        print()
        print_qr_ascii(fake_url)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": True,
            "service": service,
            "plan": plan,
            "price_id": price_id,
            "amount": amount,
            "quantity": quantity,
            "customer_email": customer_email,
            "metadata": metadata,
            "url": fake_url,
        }
        log_entry(entry)
        print(f"  [DRY RUN] Logged to {LOG_FILE}")
        return {"url": fake_url, "id": "cs_test_dryrun"}

    # Real API call
    api_key = get_stripe_key()
    stripe.api_key = api_key

    session_params = {
        "line_items": [
            {
                "price": price_id,
                "quantity": quantity,
            }
        ],
        "mode": "payment" if "destiny-college" in service else "subscription",
        "success_url": success_url or "https://gotechsolutions.com/success?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": cancel_url or "https://gotechsolutions.com/cancel",
    }

    if customer_email:
        session_params["customer_email"] = customer_email

    if metadata:
        session_params["metadata"] = metadata

    try:
        session = stripe.checkout.Session.create(**session_params)
    except stripe.error.StripeError as e:
        print(f"Stripe API Error: {e}")
        sys.exit(1)

    print("=" * 60)
    print("  Checkout Session Created")
    print("=" * 60)
    print(f"  Session ID:  {session.id}")
    print(f"  Product:     {name}")
    print(f"  Amount:      {format_amount(amount)} × {quantity} = {format_amount(amount * quantity)}")
    print(f"  URL:         {session.url}")
    print()

    print_qr_ascii(session.url)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": False,
        "service": service,
        "plan": plan,
        "price_id": price_id,
        "amount": amount,
        "quantity": quantity,
        "customer_email": customer_email,
        "metadata": metadata,
        "session_id": session.id,
        "url": session.url,
    }
    log_entry(entry)
    print(f"  Logged to {LOG_FILE}")

    return session


def create_payment_link(service, plan, quantity, metadata, dry_run):
    """Create a Stripe Payment Link."""
    price_info = PRICE_CATALOG.get((service, plan))
    if not price_info:
        print(f"ERROR: Unknown service/plan combination: {service}/{plan}")
        sys.exit(1)

    price_id = price_info["price_id"]
    amount = price_info["amount"]
    name = price_info["name"]

    if dry_run:
        print("=" * 60)
        print("  DRY RUN — No API call will be made")
        print("=" * 60)
        print(f"  Service:    {service}")
        print(f"  Plan:       {plan}")
        print(f"  Product:    {name}")
        print(f"  Price ID:   {price_id}")
        print(f"  Amount:     {format_amount(amount)}")
        print(f"  Quantity:   {quantity}")
        print()

        fake_url = f"https://buy.stripe.com/test_{'x' * 24}"
        print(f"  [DRY RUN] Payment Link URL: {fake_url}")
        print()
        print_qr_ascii(fake_url)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": True,
            "type": "payment_link",
            "service": service,
            "plan": plan,
            "price_id": price_id,
            "amount": amount,
            "quantity": quantity,
            "url": fake_url,
        }
        log_entry(entry)
        print(f"  [DRY RUN] Logged to {LOG_FILE}")
        return {"url": fake_url, "id": "plink_test_dryrun"}

    api_key = get_stripe_key()
    stripe.api_key = api_key

    try:
        link = stripe.PaymentLink.create(
            line_items=[
                {
                    "price": price_id,
                    "quantity": quantity,
                }
            ],
            metadata=metadata or {},
        )
    except stripe.error.StripeError as e:
        print(f"Stripe API Error: {e}")
        sys.exit(1)

    print("=" * 60)
    print("  Payment Link Created")
    print("=" * 60)
    print(f"  Link ID:   {link.id}")
    print(f"  Product:   {name}")
    print(f"  Amount:    {format_amount(amount)} × {quantity}")
    print(f"  URL:       {link.url}")
    print()

    print_qr_ascii(link.url)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": False,
        "type": "payment_link",
        "service": service,
        "plan": plan,
        "price_id": price_id,
        "amount": amount,
        "quantity": quantity,
        "metadata": metadata,
        "link_id": link.id,
        "url": link.url,
    }
    log_entry(entry)
    print(f"  Logged to {LOG_FILE}")

    return link


def list_products(dry_run):
    """List all active Stripe products and prices."""
    print("=" * 60)
    print("  GoTech Solutions — Product Catalog")
    print("=" * 60)

    if dry_run:
        print("\n  [DRY RUN MODE — Showing local catalog]\n")
        for (service, plan), info in PRICE_CATALOG.items():
            print(f"  {info['name']:<40} {format_amount(info['amount']):>10}")
            print(f"    Price ID: {info['price_id']}")
            print(f"    Desc:     {info['description']}")
            print()
        return

    api_key = get_stripe_key()
    stripe.api_key = api_key

    try:
        products = stripe.Product.list(active=True, limit=100)
    except stripe.error.StripeError as e:
        print(f"Stripe API Error: {e}")
        sys.exit(1)

    print(f"\n  Active Products: {len(products.data)}\n")
    for product in products.data:
        print(f"  {product.name}")
        print(f"    ID: {product.id}")
        try:
            prices = stripe.Price.list(product=product.id, active=True, limit=10)
            for price in prices.data:
                recurring = ""
                if price.recurring:
                    recurring = f" (recurring: {price.recurring.interval})"
                print(f"    Price: {format_amount(price.unit_amount)} — {price.id}{recurring}")
        except Exception:
            pass
        print()


def create_product(service, plan, dry_run):
    """Create a new Stripe product and price via API."""
    price_info = PRICE_CATALOG.get((service, plan))
    if not price_info:
        print(f"ERROR: Unknown service/plan combination: {service}/{plan}")
        sys.exit(1)

    name = price_info["name"]
    amount = price_info["amount"]
    description = price_info["description"]

    if dry_run:
        print("=" * 60)
        print("  DRY RUN — No API call will be made")
        print("=" * 60)
        print(f"  Would create product:")
        print(f"    Name:        {name}")
        print(f"    Description: {description}")
        print(f"    Amount:      {format_amount(amount)}")
        print(f"    Service:     {service}")
        print(f"    Plan:        {plan}")
        print()
        print("  After creating, update PRICE_CATALOG with the returned Price ID.")
        return

    api_key = get_stripe_key()
    stripe.api_key = api_key

    try:
        product = stripe.Product.create(
            name=name,
            description=description,
            metadata={"service": service, "plan": plan},
        )

        price = stripe.Price.create(
            product=product.id,
            unit_amount=amount,
            currency="usd",
            recurring={"interval": "month"} if plan == "monthly" else None,
            metadata={"service": service, "plan": plan},
        )

        print("=" * 60)
        print("  Product Created Successfully")
        print("=" * 60)
        print(f"  Product ID: {product.id}")
        print(f"  Price ID:   {price.id}")
        print(f"  Name:       {product.name}")
        print(f"  Amount:     {format_amount(amount)}")
        print()
        print("  Update PRICE_CATALOG in this script with the Price ID above.")

    except stripe.error.StripeError as e:
        print(f"Stripe API Error: {e}")
        sys.exit(1)


def show_stats(dry_run):
    """Show payment link usage stats."""
    print("=" * 60)
    print("  Payment Link Statistics")
    print("=" * 60)

    entries = load_log()

    if not entries:
        print("\n  No payment links created yet.\n")
        return

    total = len(entries)
    dry_runs = sum(1 for e in entries if e.get("dry_run"))
    real = total - dry_runs

    # Count by service
    by_service = {}
    for e in entries:
        svc = e.get("service", "unknown")
        by_service[svc] = by_service.get(svc, 0) + 1

    # Count by plan
    by_plan = {}
    for e in entries:
        pl = e.get("plan", "unknown")
        by_plan[pl] = by_plan.get(pl, 0) + 1

    print(f"\n  Total links generated: {total}")
    print(f"  Real API calls:       {real}")
    print(f"  Dry runs:             {dry_runs}")
    print()
    print("  By Service:")
    for svc, count in sorted(by_service.items()):
        print(f"    {svc:<20} {count}")
    print()
    print("  By Plan:")
    for pl, count in sorted(by_plan.items()):
        print(f"    {pl:<20} {count}")
    print()

    # Show recent entries
    print("  Recent Activity (last 10):")
    for e in entries[-10:]:
        ts = e.get("timestamp", "unknown")[:19]
        dr = "[DRY]" if e.get("dry_run") else "[LIVE]"
        svc = e.get("service", "?")
        pl = e.get("plan", "?")
        amt = format_amount(e.get("amount", 0))
        print(f"    {ts}  {dr}  {svc}/{pl}  {amt}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stripe Payment Link Generator for GoTech Solutions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --service ai-ops --plan monthly --quantity 1
  %(prog)s --service bundle --plan annual --quantity 2 --customer-email client@example.com
  %(prog)s --service destiny-college --plan application-fee
  %(prog)s --dry-run --service ai-ops --plan monthly
  %(prog)s --list
  %(prog)s --create-product --service ai-ops --plan monthly
  %(prog)s --stats
        """,
    )

    parser.add_argument(
        "--service",
        choices=SERVICES,
        help="Service tier",
    )
    parser.add_argument(
        "--plan",
        choices=PLANS,
        help="Billing plan",
    )
    parser.add_argument(
        "--quantity",
        type=int,
        default=1,
        help="Number of seats/licenses (default: 1)",
    )
    parser.add_argument(
        "--customer-email",
        type=str,
        default=None,
        help="Pre-fill customer email on checkout",
    )
    parser.add_argument(
        "--metadata",
        type=str,
        default=None,
        help="JSON string of metadata to attach to the session",
    )
    parser.add_argument(
        "--success-url",
        type=str,
        default=None,
        help="Custom success redirect URL",
    )
    parser.add_argument(
        "--cancel-url",
        type=str,
        default=None,
        help="Custom cancel redirect URL",
    )
    parser.add_argument(
        "--payment-link",
        action="store_true",
        help="Create a Payment Link instead of a Checkout Session",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without making API calls (no API key required)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all active Stripe products and prices",
    )
    parser.add_argument(
        "--create-product",
        action="store_true",
        help="Create a new Stripe product and price via API",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show payment link usage statistics",
    )

    args = parser.parse_args()

    # Parse metadata if provided
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            print(f"ERROR: Invalid JSON in --metadata: {args.metadata}")
            sys.exit(1)

    # Route to appropriate action
    if args.list:
        list_products(args.dry_run)
        return

    if args.create_product:
        if not args.service or not args.plan:
            parser.error("--create-product requires --service and --plan")
        create_product(args.service, args.plan, args.dry_run)
        return

    if args.stats:
        show_stats(args.dry_run)
        return

    # Default: create checkout session or payment link
    if not args.service or not args.plan:
        parser.error("--service and --plan are required (unless using --list, --stats, or --create-product)")

    if args.payment_link:
        create_payment_link(
            service=args.service,
            plan=args.plan,
            quantity=args.quantity,
            metadata=metadata,
            dry_run=args.dry_run,
        )
    else:
        create_checkout_session(
            service=args.service,
            plan=args.plan,
            quantity=args.quantity,
            customer_email=args.customer_email,
            metadata=metadata,
            success_url=args.success_url,
            cancel_url=args.cancel_url,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
