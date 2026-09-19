"""Demo payment gateway for bKash, Nagad and card payments.

IMPORTANT: This is a simulation. No money moves and nothing is sent to a real
payment provider. It only checks that the details LOOK valid, then approves.
PINs, CVVs and full card numbers are checked and thrown away - never stored.
"""

import re
import secrets
import string
from datetime import date

METHODS = {"bkash": "bKash", "nagad": "Nagad", "card": "Card"}

# Bangladeshi mobile numbers: 01[3-9] followed by 8 digits (11 digits total).
MOBILE_RE = re.compile(r"^01[3-9]\d{8}$")


class PaymentError(Exception):
    def __init__(self, message, field=None):
        super().__init__(message)
        self.field = field


def _digits(value):
    return re.sub(r"\D", "", str(value or ""))


def validate(payload):
    """Check the payment details. Returns (method, masked_account_hint)."""
    method = str(payload.get("method", "")).lower()
    if method not in METHODS:
        raise PaymentError("Please choose a payment method.", "method")

    if method in ("bkash", "nagad"):
        number = _digits(payload.get("number"))
        pin = _digits(payload.get("pin"))
        if not MOBILE_RE.match(number):
            raise PaymentError(
                "Enter a valid 11-digit mobile number, like 01712345678.", "number"
            )
        if not 4 <= len(pin) <= 5:
            raise PaymentError("Enter your 4 or 5 digit PIN.", "pin")
        return method, f"{number[:3]}****{number[-3:]}"

    # Card
    number = _digits(payload.get("card_number"))
    if not 13 <= len(number) <= 19:
        raise PaymentError("Enter a valid card number.", "card_number")

    expiry = str(payload.get("expiry", "")).strip()
    match = re.match(r"^(\d{2})\s*/\s*(\d{2})$", expiry)
    if not match:
        raise PaymentError("Enter the expiry date as MM/YY.", "expiry")
    month, year = int(match.group(1)), 2000 + int(match.group(2))
    if not 1 <= month <= 12:
        raise PaymentError("The expiry month must be between 01 and 12.", "expiry")
    today = date.today()
    if (year, month) < (today.year, today.month):
        raise PaymentError("This card has expired.", "expiry")

    if not 3 <= len(_digits(payload.get("cvv"))) <= 4:
        raise PaymentError("Enter the 3 or 4 digit security code.", "cvv")
    if len(str(payload.get("name", "")).strip()) < 2:
        raise PaymentError("Enter the name on the card.", "name")

    return method, f"**** {number[-4:]}"


def new_transaction_id():
    """A random 10-character ID, like the TrxIDs on real payment receipts."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))
