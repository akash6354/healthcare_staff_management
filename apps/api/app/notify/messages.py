"""Server-rendered staff messages (email). Every string exists in en, kn and hi (CLAUDE.md rule 6).

Kannada and Hindi copies are first drafts and are marked for native-speaker review in
packages/i18n/README.md before the pilot.
"""

_OTP = {
    "en": (
        "Your OGLOS sign-in code",
        "Your OGLOS sign-in code is {code}.\n\nIt expires in {ttl} minutes. "
        "If you did not try to sign in, ignore this email and tell your supervisor.",
    ),
    "kn": (
        "ನಿಮ್ಮ OGLOS ಸೈನ್-ಇನ್ ಕೋಡ್",
        "ನಿಮ್ಮ OGLOS ಸೈನ್-ಇನ್ ಕೋಡ್ {code}.\n\nಇದು {ttl} ನಿಮಿಷಗಳಲ್ಲಿ ಅವಧಿ ಮುಗಿಯುತ್ತದೆ. "
        "ನೀವು ಸೈನ್ ಇನ್ ಮಾಡಲು ಪ್ರಯತ್ನಿಸದಿದ್ದರೆ, ಈ ಇಮೇಲ್ ಅನ್ನು ನಿರ್ಲಕ್ಷಿಸಿ ಮತ್ತು ನಿಮ್ಮ ಮೇಲ್ವಿಚಾರಕರಿಗೆ ತಿಳಿಸಿ.",
    ),
    "hi": (
        "आपका OGLOS साइन-इन कोड",
        "आपका OGLOS साइन-इन कोड {code} है।\n\nयह {ttl} मिनट में समाप्त हो जाएगा। "
        "अगर आपने साइन इन करने की कोशिश नहीं की, तो इस ईमेल को अनदेखा करें और अपने सुपरवाइज़र को बताएं।",
    ),
}


def otp_email(language: str, code: str, ttl_minutes: int) -> tuple[str, str]:
    subject, body = _OTP.get(language, _OTP["en"])
    return subject, body.format(code=code, ttl=ttl_minutes)
