"""Тесты для модуля models."""
import pytest
from src.models import ValidationError


class TestValidationErrorUid:
    """Тесты генерации уникального ID ошибки."""

    def test_uid_is_deterministic(self):
        """UID генерируется детерминировано из полей ошибки."""
        error1 = ValidationError(
            row_number=5,
            column="Клиент",
            error_type="empty",
            description="Поле пустое",
            cell_link="https://example.com",
            sheet_name="Продажи"
        )
        error2 = ValidationError(
            row_number=5,
            column="Клиент",
            error_type="empty",
            description="Другое описание",  # Описание не влияет на UID
            cell_link="https://other.com",
            sheet_name="Продажи"
        )
        assert error1.uid == error2.uid

    def test_uid_differs_for_different_rows(self):
        """UID разный для разных строк."""
        error1 = ValidationError(
            row_number=5,
            column="Клиент",
            error_type="empty",
            description="",
            cell_link="",
            sheet_name="Продажи"
        )
        error2 = ValidationError(
            row_number=6,
            column="Клиент",
            error_type="empty",
            description="",
            cell_link="",
            sheet_name="Продажи"
        )
        assert error1.uid != error2.uid

    def test_uid_differs_for_different_columns(self):
        """UID разный для разных колонок."""
        error1 = ValidationError(
            row_number=5,
            column="Клиент",
            error_type="empty",
            description="",
            cell_link="",
            sheet_name="Продажи"
        )
        error2 = ValidationError(
            row_number=5,
            column="Продукт",
            error_type="empty",
            description="",
            cell_link="",
            sheet_name="Продажи"
        )
        assert error1.uid != error2.uid

    def test_uid_is_valid_md5(self):
        """UID — корректный MD5 хеш (32 hex символа)."""
        error = ValidationError(
            row_number=1,
            column="Дата",
            error_type="invalid",
            description="",
            cell_link="",
            sheet_name="Тренировки"
        )
        assert len(error.uid) == 32
        assert all(c in "0123456789abcdef" for c in error.uid)
