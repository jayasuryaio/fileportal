"""Input validation helpers. Each returns a cleaned value or raises ValidationError."""
import re


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
MOBILE_RE = re.compile(r"^\+?[0-9]{7,15}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'\-]{0,98}[A-Za-z.]$|^[A-Za-z]$")

# Allowed uploads: extension -> (display type, magic-byte prefixes)
ALLOWED_TYPES = {
    "pdf": ("PDF", (b"%PDF-",)),
    "png": ("PNG", (b"\x89PNG\r\n\x1a\n",)),
    "jpg": ("JPEG", (b"\xff\xd8\xff",)),
    "jpeg": ("JPEG", (b"\xff\xd8\xff",)),
}


class ValidationError(ValueError):
    """Raised with a user-friendly message."""


def validate_signup(form) -> dict:
    """Validate the sign-up form; returns cleaned data or raises with all problems."""
    errors = {}
    name = (form.get("name") or "").strip()
    age_raw = (form.get("age") or "").strip()
    address = (form.get("address") or "").strip()
    email = (form.get("email") or "").strip().lower()
    mobile = re.sub(r"[ \-()]", "", (form.get("mobile") or "").strip())
    password = form.get("password") or ""

    if not NAME_RE.match(name):
        errors["name"] = "Enter a valid name (letters, spaces, . ' - only)."
    try:
        age = int(age_raw)
        if not 1 <= age <= 120:
            raise ValueError
    except ValueError:
        age = None
        errors["age"] = "Age must be a whole number between 1 and 120."
    if not 5 <= len(address) <= 255:
        errors["address"] = "Address must be 5 to 255 characters."
    if len(email) > 255 or not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    if not MOBILE_RE.match(mobile):
        errors["mobile"] = "Enter a valid mobile number (7-15 digits, optional +)."
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        errors["password"] = "Password needs 8+ characters with letters and numbers."
    elif len(password) > 128:
        errors["password"] = "Password is too long (max 128 characters)."

    if errors:
        raise ValidationError(errors)
    return {"name": name, "age": age, "address": address, "email": email,
            "mobile": mobile, "password": password}


def detect_upload_type(filename: str, head: bytes) -> str:
    """Return 'PDF'/'PNG'/'JPEG' if extension AND file signature agree, else raise."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_TYPES:
        raise ValidationError("Only PDF, PNG or JPEG files are allowed.")
    label, magics = ALLOWED_TYPES[ext]
    if not any(head.startswith(m) for m in magics):
        raise ValidationError(f"This file is not a valid {label}.")
    return label


def safe_name_part(name: str) -> str:
    """Make a user's name safe for use inside a filename."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return cleaned[:40] or "user"


__all__ = ["validate_signup", "detect_upload_type", "safe_name_part", "ValidationError"]
