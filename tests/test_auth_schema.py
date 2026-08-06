import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest


def test_password_accepts_five_characters_with_letter_and_number():
    request = LoginRequest(email="user@example.com", password="abc12")
    assert request.password == "abc12"


@pytest.mark.parametrize("password", ["abcd", "abcdef", "12345"])
def test_password_rejects_short_or_single_character_class(password):
    with pytest.raises(ValidationError):
        LoginRequest(email="user@example.com", password=password)
