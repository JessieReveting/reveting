#!/usr/bin/env python3
"""
GoTech Solutions — Email Sender
Sends real emails via Gmail (SMTP or OAuth2) or Outlook/Office 365.

Usage:
  python3 email-sender.py --to recipient@example.com --subject "Hello" --body "Message"
  python3 email-sender.py --to recipient@example.com --template follow-up --var name=John --var company=Acme
  python3 email-sender.py --csv contacts.csv --template outreach --from gmail
  python3 email-sender.py --test --from gmail
  python3 email-sender.py --to recipient@example.com --subject "Hi" --body "Test" --dry-run
  python3 email-sender.py --to a@b.com,c@d.com --subject "Hi" --body "Hello" --attach report.pdf

Environment Variables:
  GMAIL_APP_PASSWORD     — Gmail App Password (for SMTP auth)
  OUTLOOK_PASSWORD       — Outlook/Office 365 password (for SMTP auth)
  GMAIL_USER             — Gmail address (default: bizrunner@gmail.com)
  OUTLOOK_USER           — Outlook email (default: user@outlook.com)

Setup:
  1. For Gmail SMTP: Generate App Password at https://myaccount.google.com/apppasswords
  2. For Gmail OAuth2: Ensure ~/.hermes/auth/google_oauth.json exists
  3. For Outlook: Set OUTLOOK_PASSWORD env var
  4. pip install google-auth google-auth-oauthlib google-auth-httplib2  (for OAuth2)
"""

import argparse
import csv
import datetime
import email
import json
import logging
import mimetypes
import os
import re
import smtplib
import ssl
import sys
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from string import Template
from typing import Dict, List, Optional, Tuple

# === CONFIG ===
STARTUP_DIR = Path("/Users/davidgo/Documents/GoTechSolutions/startup")
SCRIPTS_DIR = STARTUP_DIR / "scripts"
TEMPLATES_DIR = SCRIPTS_DIR / "templates" / "email"
LOG_FILE = SCRIPTS_DIR / "email-send-log.csv"
RATE_LIMIT_FILE = SCRIPTS_DIR / "email-rate-limit.json"
OAUTH_FILE = Path.home() / ".hermes" / "auth" / "google_oauth.json"

DEFAULT_GMAIL = "bizrunner@gmail.com"
MAX_EMAILS_PER_DAY = 50

# === LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("email-sender")


# === EMAIL VALIDATION ===
def validate_email(email_addr: str) -> bool:
    """Validate email format using RFC 5322 simplified regex."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email_addr.strip()))


# === RATE LIMITING ===
def check_rate_limit(account: str) -> Tuple[bool, int]:
    """Check if the account has exceeded the daily rate limit.
    Returns (allowed: bool, count: int).
    """
    today = datetime.date.today().isoformat()
    data = {}

    if RATE_LIMIT_FILE.exists():
        try:
            with open(RATE_LIMIT_FILE, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            data = {}

    key = f"{account}_{today}"
    count = data.get(key, 0)

    if count >= MAX_EMAILS_PER_DAY:
        return False, count
    return True, count


def increment_rate_limit(account: str):
    """Increment the sent count for today."""
    today = datetime.date.today().isoformat()
    data = {}

    if RATE_LIMIT_FILE.exists():
        try:
            with open(RATE_LIMIT_FILE, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            data = {}

    key = f"{account}_{today}"
    data[key] = data.get(key, 0) + 1

    # Clean up old entries (older than 2 days)
    cutoff = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
    data = {k: v for k, v in data.items() if not k.endswith(cutoff)}

    RATE_LIMIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RATE_LIMIT_FILE, "w") as f:
        json.dump(data, f, indent=2)


# === LOGGING SENT EMAILS ===
def log_sent_email(account: str, to: str, subject: str, status: str, method: str):
    """Log a sent email to the CSV log file."""
    log_file = LOG_FILE
    file_exists = log_file.exists()

    log_file.parent.mkdir(parents=True, exist_ok=True)

    with open(log_file, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "account", "recipient", "subject", "status", "method"])
        writer.writerow([
            datetime.datetime.now().isoformat(),
            account,
            to,
            subject,
            status,
            method,
        ])


# === TEMPLATE SYSTEM ===
def load_template(template_name: str) -> str:
    """Load an email template from the templates/email/ directory."""
    template_path = TEMPLATES_DIR / f"{template_name}.txt"
    if not template_path.exists():
        # Also try .html extension
        template_path = TEMPLATES_DIR / f"{template_name}.html"

    if not template_path.exists():
        raise FileNotFoundError(
            f"Template '{template_name}' not found in {TEMPLATES_DIR}. "
            f"Available templates: {list_available_templates()}"
        )

    with open(template_path, "r") as f:
        return f.read()


def list_available_templates() -> List[str]:
    """List available template names."""
    if not TEMPLATES_DIR.exists():
        return []
    templates = []
    for ext in [".txt", ".html"]:
        templates.extend([f.stem for f in TEMPLATES_DIR.glob(f"*{ext}")])
    return templates


def render_template(template_str: str, variables: Dict[str, str]) -> Tuple[str, str]:
    """Render a template string with {{variables}}.
    Returns (subject, body) tuple. First line starting with 'Subject:' is the subject.
    """
    tmpl = Template(template_str)
    rendered = tmpl.safe_substitute(variables)

    lines = rendered.split("\n", 1)
    if lines and lines[0].startswith("Subject:"):
        subject = lines[0].replace("Subject:", "").strip()
        body = lines[1].strip() if len(lines) > 1 else ""
    else:
        subject = ""
        body = rendered

    return subject, body


# === GMAIL SMTP ===
def send_gmail_smtp(
    to_addrs: List[str],
    subject: str,
    body: str,
    from_addr: str,
    password: str,
    attachments: Optional[List[str]] = None,
    dry_run: bool = False,
) -> bool:
    """Send email via Gmail SMTP with App Password."""
    context = ssl.create_default_context()

    if dry_run:
        logger.info(f"[DRY RUN] Would send via Gmail SMTP to {to_addrs}")
        logger.info(f"  From: {from_addr}")
        logger.info(f"  Subject: {subject}")
        logger.info(f"  Body: {body[:100]}...")
        return True

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(from_addr, password)

            msg = MIMEMultipart()
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_addrs)
            msg["Subject"] = subject

            # Detect HTML
            if body.strip().startswith("<") and ">" in body:
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))

            # Attachments
            if attachments:
                for filepath in attachments:
                    if not Path(filepath).exists():
                        logger.warning(f"Attachment not found: {filepath}")
                        continue
                    content_type, encoding = mimetypes.guess_type(filepath)
                    if content_type is None:
                        content_type = "application/octet-stream"
                    maintype, subtype = content_type.split("/", 1)

                    with open(filepath, "rb") as f:
                        part = MIMEBase(maintype, subtype)
                        part.set_payload(f.read())
                    email.encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={Path(filepath).name}",
                    )
                    msg.attach(part)

            server.sendmail(from_addr, to_addrs, msg.as_string())
            logger.info(f"Email sent via Gmail SMTP to {', '.join(to_addrs)}")
            return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Gmail SMTP authentication failed. Check GMAIL_APP_PASSWORD. "
            "Generate one at: https://myaccount.google.com/apppasswords"
        )
        return False
    except smtplib.SMTPException as e:
        logger.error(f"Gmail SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending via Gmail SMTP: {e}")
        return False


# === GMAIL OAUTH2 ===
def send_gmail_oauth(
    to_addrs: List[str],
    subject: str,
    body: str,
    from_addr: str,
    attachments: Optional[List[str]] = None,
    dry_run: bool = False,
) -> bool:
    """Send email via Gmail using OAuth2 (XOAUTH2 mechanism)."""
    if dry_run:
        logger.info(f"[DRY RUN] Would send via Gmail OAuth2 to {to_addrs}")
        logger.info(f"  From: {from_addr}")
        logger.info(f"  Subject: {subject}")
        return True

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        import base64

        if not OAUTH_FILE.exists():
            logger.error(f"OAuth file not found: {OAUTH_FILE}")
            return False

        creds = Credentials.from_authorized_user_file(str(OAUTH_FILE))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        # Build the OAuth2 string for XOAUTH2
        auth_string = f"user={from_addr}\x01auth=Bearer {creds.token}\x01\x01"
        auth_bytes = base64.b64encode(auth_string.encode("utf-8"))

        context = ssl.create_default_context()

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.ehlo()
            server.docmd("AUTH", f"XOAUTH2 {auth_bytes.decode('utf-8')}")

            msg = MIMEMultipart()
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_addrs)
            msg["Subject"] = subject

            if body.strip().startswith("<") and ">" in body:
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))

            if attachments:
                for filepath in attachments:
                    if not Path(filepath).exists():
                        logger.warning(f"Attachment not found: {filepath}")
                        continue
                    content_type, encoding = mimetypes.guess_type(filepath)
                    if content_type is None:
                        content_type = "application/octet-stream"
                    maintype, subtype = content_type.split("/", 1)

                    with open(filepath, "rb") as f:
                        part = MIMEBase(maintype, subtype)
                        part.set_payload(f.read())
                    email.encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={Path(filepath).name}",
                    )
                    msg.attach(part)

            server.sendmail(from_addr, to_addrs, msg.as_string())
            logger.info(f"Email sent via Gmail OAuth2 to {', '.join(to_addrs)}")
            return True

    except ImportError:
        logger.error(
            "Google auth libraries not installed. "
            "Run: pip install google-auth google-auth-oauthlib google-auth-httplib2"
        )
        return False
    except Exception as e:
        logger.error(f"Gmail OAuth2 error: {e}")
        return False


# === OUTLOOK/OFFICE 365 SMTP ===
def send_outlook_smtp(
    to_addrs: List[str],
    subject: str,
    body: str,
    from_addr: str,
    password: str,
    attachments: Optional[List[str]] = None,
    dry_run: bool = False,
) -> bool:
    """Send email via Outlook/Office 365 SMTP."""
    context = ssl.create_default_context()

    if dry_run:
        logger.info(f"[DRY RUN] Would send via Outlook SMTP to {to_addrs}")
        logger.info(f"  From: {from_addr}")
        logger.info(f"  Subject: {subject}")
        return True

    try:
        with smtplib.SMTP("smtp.office365.com", 587) as server:
            server.starttls(context=context)
            server.login(from_addr, password)

            msg = MIMEMultipart()
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_addrs)
            msg["Subject"] = subject

            if body.strip().startswith("<") and ">" in body:
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))

            if attachments:
                for filepath in attachments:
                    if not Path(filepath).exists():
                        logger.warning(f"Attachment not found: {filepath}")
                        continue
                    content_type, encoding = mimetypes.guess_type(filepath)
                    if content_type is None:
                        content_type = "application/octet-stream"
                    maintype, subtype = content_type.split("/", 1)

                    with open(filepath, "rb") as f:
                        part = MIMEBase(maintype, subtype)
                        part.set_payload(f.read())
                    email.encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={Path(filepath).name}",
                    )
                    msg.attach(part)

            server.sendmail(from_addr, to_addrs, msg.as_string())
            logger.info(f"Email sent via Outlook SMTP to {', '.join(to_addrs)}")
            return True

    except smtplib.SMTPAuthenticationError:
        logger.error("Outlook SMTP authentication failed. Check OUTLOOK_PASSWORD.")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"Outlook SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending via Outlook SMTP: {e}")
        return False


# === CSV RECIPIENTS ===
def load_recipients_from_csv(csv_path: str) -> List[Dict[str, str]]:
    """Load recipients from a CSV file.
    Expected columns: email (required), name (optional), plus any template variables.
    """
    if not Path(csv_path).exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    recipients = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        if "email" not in (reader.fieldnames or []):
            raise ValueError("CSV must have an 'email' column")
        for row in reader:
            recipients.append(dict(row))
    return recipients


# === MAIN SEND LOGIC ===
def send_email(
    to_addrs: List[str],
    subject: str,
    body: str,
    from_account: str = "gmail",
    attachments: Optional[List[str]] = None,
    dry_run: bool = False,
) -> bool:
    """Main send function that routes to the correct provider."""
    # Validate all recipient emails
    for addr in to_addrs:
        if not validate_email(addr):
            logger.error(f"Invalid email address: {addr}")
            return False

    # Check rate limit
    allowed, count = check_rate_limit(from_account)
    if not allowed:
        logger.error(
            f"Rate limit exceeded for {from_account}: {count}/{MAX_EMAILS_PER_DAY} today"
        )
        return False

    # Determine provider and send
    success = False
    method = "unknown"

    if from_account == "gmail":
        # Try OAuth2 first, fall back to SMTP
        gmail_user = os.environ.get("GMAIL_USER", DEFAULT_GMAIL)

        if OAUTH_FILE.exists():
            method = "gmail-oauth2"
            success = send_gmail_oauth(
                to_addrs, subject, body, gmail_user, attachments, dry_run
            )

        if not success:
            gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
            if gmail_password:
                method = "gmail-smtp"
                success = send_gmail_smtp(
                    to_addrs, subject, body, gmail_user, gmail_password, attachments, dry_run
                )
            else:
                logger.error(
                    "No Gmail auth method available. "
                    "Set GMAIL_APP_PASSWORD or ensure OAuth file exists."
                )
                return False

    elif from_account == "outlook":
        outlook_user = os.environ.get("OUTLOOK_USER", "")
        outlook_password = os.environ.get("OUTLOOK_PASSWORD")

        if not outlook_user:
            logger.error("OUTLOOK_USER env var not set")
            return False
        if not outlook_password:
            logger.error("OUTLOOK_PASSWORD env var not set")
            return False

        method = "outlook-smtp"
        success = send_outlook_smtp(
            to_addrs, subject, body, outlook_user, outlook_password, attachments, dry_run
        )
    else:
        logger.error(f"Unknown account: {from_account}. Use 'gmail' or 'outlook'.")
        return False

    # Log and rate-limit
    if success and not dry_run:
        increment_rate_limit(from_account)
        for addr in to_addrs:
            log_sent_email(from_account, addr, subject, "sent", method)
    elif not success and not dry_run:
        for addr in to_addrs:
            log_sent_email(from_account, addr, subject, "failed", method)

    return success


# === CLI ===
def main():
    parser = argparse.ArgumentParser(
        description="GoTech Email Sender — Send real emails via Gmail or Outlook",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --to client@example.com --subject "Proposal" --body "Here's our proposal..."
  %(prog)s --to client@example.com --template follow-up --var name=John --var company=Acme
  %(prog)s --csv contacts.csv --template outreach --from gmail
  %(prog)s --test --from gmail
  %(prog)s --to a@b.com,c@d.com --subject "Update" --body "Weekly update" --attach report.pdf
        """,
    )

    parser.add_argument(
        "--to",
        help="Recipient email address (comma-separated for multiple)",
    )
    parser.add_argument("--subject", help="Email subject line")
    parser.add_argument("--body", help="Email body text")
    parser.add_argument(
        "--template",
        help="Template name (from templates/email/ directory)",
    )
    parser.add_argument(
        "--var",
        action="append",
        help="Template variable in key=value format (can be repeated)",
    )
    parser.add_argument(
        "--from",
        dest="from_account",
        choices=["gmail", "outlook"],
        default="gmail",
        help="Email account to send from (default: gmail)",
    )
    parser.add_argument(
        "--attach",
        help="File path to attach (can be repeated)",
        action="append",
    )
    parser.add_argument(
        "--csv",
        help="Path to CSV file with recipients (must have 'email' column)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a test email to yourself",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent without actually sending",
    )
    parser.add_argument(
        "--list-templates",
        action="store_true",
        help="List available email templates",
    )

    args = parser.parse_args()

    # Ensure templates directory exists
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    # List templates
    if args.list_templates:
        templates = list_available_templates()
        if templates:
            print("Available templates:")
            for t in sorted(templates):
                print(f"  - {t}")
        else:
            print(f"No templates found in {TEMPLATES_DIR}")
        return

    # Parse variables
    variables = {}
    if args.var:
        for v in args.var:
            if "=" not in v:
                logger.error(f"Invalid variable format: {v}. Use key=value.")
                sys.exit(1)
            key, value = v.split("=", 1)
            variables[key.strip()] = value.strip()

    # Determine subject and body
    subject = args.subject or ""
    body = args.body or ""

    # Load template if specified
    if args.template:
        try:
            template_str = load_template(args.template)
            tmpl_subject, tmpl_body = render_template(template_str, variables)
            if tmpl_subject and not args.subject:
                subject = tmpl_subject
            if tmpl_body and not args.body:
                body = tmpl_body
            elif tmpl_body:
                body = tmpl_body
        except FileNotFoundError as e:
            logger.error(str(e))
            sys.exit(1)

    if not subject:
        logger.error("Subject is required. Use --subject or a template with 'Subject:' line.")
        sys.exit(1)
    if not body:
        logger.error("Body is required. Use --body or a template.")
        sys.exit(1)

    # Determine recipients
    recipients = []

    if args.test:
        test_email = os.environ.get("GMAIL_USER", DEFAULT_GMAIL)
        recipients = [test_email]
        logger.info(f"Sending test email to {test_email}")
    elif args.csv:
        try:
            csv_recipients = load_recipients_from_csv(args.csv)
            recipients = [r["email"] for r in csv_recipients]
            logger.info(f"Loaded {len(recipients)} recipients from {args.csv}")
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e))
            sys.exit(1)
    elif args.to:
        recipients = [addr.strip() for addr in args.to.split(",")]
    else:
        logger.error("No recipients specified. Use --to, --csv, or --test.")
        sys.exit(1)

    if not recipients:
        logger.error("No recipients to send to.")
        sys.exit(1)

    # Send
    success = send_email(
        to_addrs=recipients,
        subject=subject,
        body=body,
        from_account=args.from_account,
        attachments=args.attach,
        dry_run=args.dry_run,
    )

    if success:
        logger.info("Done!")
        sys.exit(0)
    else:
        logger.error("Failed to send email(s).")
        sys.exit(1)


if __name__ == "__main__":
    main()
