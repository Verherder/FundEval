import re


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,20}$")
PASSWORD_PATTERN = re.compile(r"^[A-Za-z0-9@#$%^&*_.!+\-]{12,20}$")


def validate_username(username):
    return bool(USERNAME_PATTERN.fullmatch(str(username or "")))


def validate_password(password):
    return bool(PASSWORD_PATTERN.fullmatch(str(password or "")))
