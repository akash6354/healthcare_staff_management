"""No personal data in logs (security.md §6)."""

from app.core.crypto import decrypt_field, encrypt_field
from app.core.logging import scrub


def test_scrub_removes_personal_data() -> None:
    line = "otp=482613 sent to asha.k@example.org phone +91 9876543210 token: abc.def"
    cleaned = scrub(line)
    for secret in ("482613", "asha.k@example.org", "9876543210", "abc.def"):
        assert secret not in cleaned


def test_field_encryption_round_trip_and_is_randomised() -> None:
    a, b = encrypt_field("+919876543210"), encrypt_field("+919876543210")
    assert a != b
    assert decrypt_field(a) == "+919876543210"
