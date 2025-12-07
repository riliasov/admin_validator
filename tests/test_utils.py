"""Тесты для модуля utils."""
import pytest
from datetime import datetime
from src.utils import parse_date_value, parse_float, parse_discount, validate_phone_format, format_money


class TestParseDateValue:
    """Тесты парсинга дат."""

    def test_serial_date(self):
        """Serial Date из Google Sheets (число дней с 1899-12-30)."""
        result = parse_date_value(45000)
        assert result is not None
        assert result.year == 2023

    def test_string_date_dd_mm_yyyy(self):
        """Формат ДД.ММ.ГГГГ."""
        result = parse_date_value("25.12.2023")
        assert result == datetime(2023, 12, 25)

    def test_string_date_yyyy_mm_dd(self):
        """Формат YYYY-MM-DD."""
        result = parse_date_value("2023-12-25")
        assert result == datetime(2023, 12, 25)

    def test_string_date_with_day_prefix(self):
        """Формат 'сб 01.11'."""
        result = parse_date_value("сб 01.11")
        assert result is not None
        assert result.day == 1
        assert result.month == 11

    def test_empty_value(self):
        """Пустое значение."""
        assert parse_date_value("") is None
        assert parse_date_value(None) is None

    def test_invalid_string(self):
        """Некорректная строка."""
        assert parse_date_value("not a date") is None


class TestParseFloat:
    """Тесты парсинга чисел."""

    def test_integer(self):
        """Целое число."""
        assert parse_float(100) == 100.0

    def test_float(self):
        """Дробное число."""
        assert parse_float(99.5) == 99.5

    def test_string_with_comma(self):
        """Строка с запятой."""
        assert parse_float("1 234,50") == 1234.5

    def test_string_with_spaces(self):
        """Строка с пробелами-разделителями."""
        assert parse_float("1 000") == 1000.0

    def test_empty_returns_zero(self):
        """Пустое значение возвращает 0."""
        assert parse_float("") == 0.0
        assert parse_float(None) == 0.0


class TestParseDiscount:
    """Тесты парсинга скидки."""

    def test_percent_string(self):
        """Строка с процентом."""
        assert parse_discount("50%") == 0.5

    def test_decimal_number(self):
        """Дробное число (уже в формате 0-1)."""
        assert parse_discount(0.3) == 0.3

    def test_integer_as_absolute(self):
        """Целое число как абсолютное значение."""
        assert parse_discount(100) == 100.0


class TestValidatePhoneFormat:
    """Тесты валидации телефона."""

    def test_valid_phone(self):
        """Корректный формат 79XXXXXXXXX."""
        assert validate_phone_format("79001234567") is True

    def test_phone_with_special_chars(self):
        """Телефон со спецсимволами."""
        assert validate_phone_format("+7 (900) 123-45-67") is True

    def test_short_phone(self):
        """Короткий номер."""
        assert validate_phone_format("7900123") is False

    def test_phone_not_starting_with_7(self):
        """Номер не начинается с 7."""
        assert validate_phone_format("89001234567") is False

    def test_empty_phone(self):
        """Пустой телефон."""
        assert validate_phone_format("") is False
        assert validate_phone_format(None) is False


class TestFormatMoney:
    """Тесты форматирования денег."""

    def test_format_thousands(self):
        """Форматирование с разделителями тысяч."""
        assert format_money(8888.00) == "8 888,00"

    def test_format_with_cents(self):
        """Форматирование с копейками."""
        assert format_money(1234.56) == "1 234,56"

    def test_format_zero(self):
        """Ноль."""
        assert format_money(0) == "0,00"
