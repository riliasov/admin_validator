from typing import List, Any
from src.models import ValidationError
from src.utils import validate_phone_format
from .base import BaseValidator

class LeadsValidator(BaseValidator):
    """
    Валидатор для таблицы Обращения.
    """
    
    def _add_date_to_description(self, description: str, date_str: str) -> str:
        """Добавляет дату в скобках к описанию ошибки."""
        return f"{description} ({date_str})"


    def _validate_phone_format(self, phone: str) -> bool:
        """
        Проверяет формат телефона: должен быть 79XXXXXXXXX.
        11 цифр, только цифры, начинается с 7.
        """
        return validate_phone_format(phone)

    def validate_row(self, row_idx: int, row: List[Any]) -> List[ValidationError]:
        """Валидация строки обращений."""
        errors = []
        sheet_row_num = row_idx + 2 # row_idx starts from 1 (data start) -> sheet row 2 (header) -> row 3 (data)
        # BaseValidator: enumerate(data[1:], start=1).
        # data[0] = Header (A2). data[1] = Row A3.
        # row_idx=1 -> Row A3.
        # Sheet Row = row_idx + 2. Correct.

        # Извлекаем админа для ошибок создания лида
        lead_admin_val = self._get_val(row, "Админ (создал лида)")
        lead_admin = str(lead_admin_val).strip() if lead_admin_val else "Уточнить"
        
        # Извлекаем и форматируем дату обращения
        from src.utils import parse_date_value
        date_val = self._get_val(row, "Дата обращения")
        dt = parse_date_value(date_val)
        formatted_date = dt.strftime("%d.%m.%Y") if dt else str(date_val) if date_val else ""

        # 1. Проверка обязательных полей (Создание лида)
        # Используем стандартный механизм BaseValidator, так как теперь имена уникальны
        for col_name in self.required_columns:
            val = self._get_val(row, col_name)
            
            if not val:
                desc = f"Поле '{col_name}' обязательно для создания лида"
                if formatted_date:
                    desc = self._add_date_to_description(desc, formatted_date)
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column=col_name,
                    error_type="empty",
                    description=desc,
                    cell_link=self._generate_link(sheet_row_num - 1, col_name),
                    sheet_name=self.sheet_name,
                    admin=lead_admin
                ))

        # 2. Проверка создания клиента (Client Creation)
        client_admin_val = self._get_val(row, "Админ (создал клиента)")
        client_admin = str(client_admin_val).strip() if client_admin_val else "Уточнить"
        
        client_fields = [
            "Фамилия взрослого",
            "Имя взрослого",
            "Имя ребенка",
            "Дата рождения ребенка",
            "Пол ребёнка",
            "Тип"
        ]
        
        # Правило 1: Если админ (создал клиента) заполнен → все поля клиента обязательны
        if client_admin_val:
            for field in client_fields:
                val = self._get_val(row, field)
                if not val:
                    desc = f"Поле '{field}' обязательно при создании клиента"
                    if formatted_date:
                        desc = self._add_date_to_description(desc, formatted_date)
                    errors.append(ValidationError(
                        row_number=sheet_row_num,
                        column=field,
                        error_type="empty",
                        description=desc,
                        cell_link=self._generate_link(sheet_row_num - 1, field),
                        sheet_name=self.sheet_name,
                        admin=client_admin  # Берём из L!
                    ))
            
            # Проверка телефона
            phone = self._get_val(row, "Мобильный")
            if not self._validate_phone_format(phone):
                desc = "Телефон должен быть в формате 79XXXXXXXXX (11 цифр)"
                if formatted_date:
                    desc = self._add_date_to_description(desc, formatted_date)
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Мобильный",
                    error_type="invalid_format",
                    description=desc,
                    cell_link=self._generate_link(sheet_row_num - 1, "Мобильный"),
                    sheet_name=self.sheet_name,
                    admin=client_admin
                ))
        
        # Правило 2: Если F:I заполнены → админ (создал клиента) обязателен
        client_core_fields = client_fields[:4]  # Фамилия, Имя взрослого, Имя ребенка, Дата рождения
        core_filled = all(self._get_val(row, f) for f in client_core_fields)
        
        if core_filled and not client_admin_val:
            desc = "Админ (создал клиента) обязателен если заполнены данные клиента"
            if formatted_date:
                desc = self._add_date_to_description(desc, formatted_date)
            errors.append(ValidationError(
                row_number=sheet_row_num,
                column="Админ (создал клиента)",
                error_type="empty",
                description=desc,
                cell_link=self._generate_link(sheet_row_num - 1, "Админ (создал клиента)"),
                sheet_name=self.sheet_name,
                admin="Уточнить"
            ))
            
            # Проверка телефона
            phone = self._get_val(row, "Мобильный")
            if not self._validate_phone_format(phone):
                desc = "Телефон должен быть в формате 79XXXXXXXXX (11 цифр)"
                if formatted_date:
                    desc = self._add_date_to_description(desc, formatted_date)
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Мобильный",
                    error_type="invalid_format",
                    description=desc,
                    cell_link=self._generate_link(sheet_row_num - 1, "Мобильный"),
                    sheet_name=self.sheet_name,
                    admin="Уточнить"
                ))

        return errors
