import uuid
import random
import re
from datetime import datetime, timedelta
import pandas as pd

random.seed(42)

CAMPAGN_GROUPS = [
    "payroll", "tax-refund", "delivery-notification", "bank-alert", "account-verification",
    "password-reset", "invoice", "social-engineering", "tech-support", "gift-card",
    "IRS", "HR-alert", "shipping", "login-alert", "subscription", "legitimate-business"
]

CHANNELS = ["email", "sms", "whatsapp", "discord"]
DOMAIN_TYPES = ["legitimate", "spoofed", "compromised"]

# Legitimate urgent messages (for AT-01 false-positive measurement - ONLY in test)
LEGITIMATE_URGENT = [
    "Your password has expired and must be reset immediately to avoid account lockout.",
    "Bank: Unusual login detected. Confirm your identity within 2 hours to secure your account.",
    "IT Department: Password reset required - your account will be disabled in 24 hours.",
    "HR: Salary slip attached - please confirm receipt by end of day.",
    "Cloud Service: Storage limit reached. Upgrade now or lose access to files.",
]

# Legitimate business messages (distributed across train/valid)
LEGITIMATE_BUSINESS = [
    "Your invoice #8473 has been paid. Thank you for your business.",
    "Meeting reminder: Team sync at 3pm today in conference room A.",
    "Project update: Q2 deliverables on track for June 30th deadline.",
    "System maintenance scheduled for this weekend 2AM-4AM UTC.",
    "Monthly newsletter: New features released in our platform.",
    "Payroll confirmation: Your September salary has been processed.",
    "Shipping notification: Your order #12345 has shipped.",
    "Account statement: Your monthly statement is available.",
    "Service confirmation: Your subscription has been renewed.",
    "IT notification: Password successfully updated on 2025-01-15.",
]

PHISHING_TEMPLATES = [
    # Payroll
    ("payroll", "Payroll Update: Your direct deposit details need verification before Friday.", 
     "Dear employee, your direct deposit details need verification before Friday. Click here to update: hxxp://fake-payroll[.]com/verify"),
    # Tax refund
    ("tax-refund", "Tax Refund Owed: Claim your $1,200 refund now.", 
     "You are eligible for a tax refund of $1,200. Click hxxp://irs-refund[.]com/refund to claim your money."),
    # Delivery notification
    ("delivery-notification", "Delivery Attempted: Package could not be delivered.", 
     "A delivery attempt was made on {{date}}. hxxp://fedex-delivery[.]com/reschedule to reschedule."),
    # Bank alert
    ("bank-alert", "Security Alert: Your account has been locked.", 
     "We detected unusual activity on your account. Secure it now at hxxp://bank-secure[.]com/secure."),
    # Account verification
    ("account-verification", "Account Verification Required", 
     "Your mailbox is over quota. Verify your account at hxxp://mail-verify[.]com/verify to avoid data loss."),
    # Password reset
    ("password-reset", "Password Reset Required", 
     "Your password has expired. Reset it now at hxxp://secure-login[.]com/reset?code=FAKE"),
    # Invoice
    ("invoice", "Unpaid Invoice: Overdue payment notice.", 
     "Invoice #8473 is overdue. Pay at hxxp://invoice-fake[.]com/pay?amount=285."),
    # Social engineering
    ("social-engineering", "Urgent: Help me get this gift card.", 
     "I need to purchase gift cards for a team event. Send the codes to hxxp://giftcard[.]com/redeem."),
    # Tech support
    ("tech-support", "Your computer is infected.", 
     "Contact tech support at hxxp://tech-support[.]com/help to remove the virus."),
    # Gift card
    ("gift-card", "Gift Card Winner!", 
     "Congratulations! You've won a $500 gift card. Claim at hxxp://giftcard-win[.]com/claim."),
    # IRS
    ("IRS", "IRS Audit Notice: Immediate response required.", 
     "You are being audited. Respond at hxxp://irs-audit[.]com/respond within 48 hours."),
    # HR alert
    ("hr-alert", "HR Announcement: Policy update required.", 
     "New remote work policy. Acknowledge at hxxp://hr-policy[.]com/acknowledge."),
    # Shipping
    ("shipping", "Tracking Update: Missing label data.", 
     "Your package label is incomplete. Update at hxxp://shipping-update[.]com/update."),
    # Login alert
    ("login-alert", "Login from New Device", 
     "We detected a login from a new device. Secure your account at hxxp://login-secure[.]com/secured."),
    # Subscription
    ("subscription", "Subscription Auto-Renewal", 
     "Your subscription will auto-renew soon. Manage at hxxp://sub-manage[.]com/manage."),
]

def defang_url(url):
    """Defang a URL by replacing . with [.] and normalizing protocols"""
    url = url.replace("http://", "hxxp://").replace("https://", "hxxps://")
    url = url.replace(".", "[.]")
    return url

rows = []
now = datetime(2025, 1, 1)

# Generate phishing messages (500 total, 25 per campaign group × 20 groups, but we have 16)
for i in range(500):
    idx = i % len(PHISHING_TEMPLATES)
    campaign_group, subject, body = PHISHING_TEMPLATES[idx]
    
    # Add some variation to body text
    variation = random.choice(["", " Urgent action required.", " Your account will be suspended.", " Click immediately."])
    body_with_var = body + variation
    
    # Sometimes add a second URL or slightly modified URL
    if random.random() < 0.3:
        extra_url = defang_url("http://extra-site[.]com/extra")
        body_with_var += " " + extra_url
    
    # Extract URL from template body for sanitized_url_features
    url_match = re.search(r'hxxp://[^\s]+', body)
    sanitized_url = defang_url(url_match.group(0)) if url_match else "[]"
    
    row = {
        "message_id": str(uuid.uuid4()),
        "channel": random.choices(CHANNELS, weights=[0.7, 0.2, 0.05, 0.05])[0],
        "subject_or_title": subject,
        "body_text": body_with_var,
        "sanitized_url_features": sanitized_url,
        "sender_domain_type": random.choices(DOMAIN_TYPES, weights=[0.6, 0.3, 0.1])[0],
        "label": 1,
        "campaign_group": campaign_group,
        "collected_date": (now + timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d"),
    }
    rows.append(row)

# Add legitimate business messages (distributed across train/valid)
# 50 legitimate business messages, spread across non-urgent campaign groups
for i in range(50):
    idx = i % len(LEGITIMATE_BUSINESS)
    template = LEGITIMATE_BUSINESS[idx]
    
    row = {
        "message_id": str(uuid.uuid4()),
        "channel": random.choices(CHANNELS, weights=[0.7, 0.2, 0.05, 0.05])[0],
        "subject_or_title": random.choice(["Business Update", "Project Notice", "System Alert", "Confirmation", "Receipt"]),
        "body_text": template,
        "sanitized_url_features": "[]",
        "sender_domain_type": "legitimate",
        "label": 0,
        "campaign_group": "legitimate-business",
        "collected_date": (now + timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d"),
    }
    rows.append(row)

# Add legitimate urgent messages (ONLY for test set - AT-01)
for template in LEGITIMATE_URGENT:
    row = {
        "message_id": str(uuid.uuid4()),
        "channel": random.choices(CHANNELS, weights=[0.7, 0.2, 0.05, 0.05])[0],
        "subject_or_title": random.choice(["System Alert", "Important Notice", "Account Update"]),
        "body_text": template,
        "sanitized_url_features": "[]",
        "sender_domain_type": "legitimate",
        "label": 0,
        "campaign_group": "legitimate-urgent",
        "collected_date": (now + timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d"),
    }
    rows.append(row)

df = pd.DataFrame(rows)

# Shuffle
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

# Ensure minimum 400 rows
assert len(df) >= 400, f"Dataset has {len(df)} rows, need at least 400"

# Print summary
print(f"Dataset size: {len(df)} rows")
print(f"Label distribution: {df['label'].value_counts().to_dict()}")
print(f"Campaign groups: {sorted(df['campaign_group'].unique())}")
print(f"Channels: {sorted(df['channel'].unique())}")
print(f"Sender domain types: {sorted(df['sender_domain_type'].unique())}")

try:
    from src.utils import get_data_dir
except ImportError:
    from utils import get_data_dir
data_dir = get_data_dir()

# Save raw data
df.to_csv(os.path.join(data_dir, "raw_messages.csv"), index=False)
print(f"\nRaw data saved to {os.path.join(data_dir, 'raw_messages.csv')}")

# Also create processed snapshot
df.to_csv(os.path.join(data_dir, "processed_messages.csv"), index=False)
print(f"Processed data saved to {os.path.join(data_dir, 'processed_messages.csv')}")