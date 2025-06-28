import pytest
from app.domain.value_objects.phone_number import BrazilianPhoneNumber


def test_valid_brazilian_number():
    phone = BrazilianPhoneNumber(number="5511999887766")
    assert phone.number == "5511999887766"


def test_fix_missing_ninth_digit():
    phone = BrazilianPhoneNumber(number="551199887766")
    assert phone.number == "5511999887766"


def test_invalid_number():
    with pytest.raises(ValueError):
        BrazilianPhoneNumber(number="1234567890")
