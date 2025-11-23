from pydantic import BaseModel
import hashlib

class ValidationError(BaseModel):
    """
    Модель ошибки валидации.
    
    Attributes:
        row_number: Номер строки в таблице
        column: Название колонки
        error_type: Тип ошибки (empty, invalid_format, missing_column)
        description: Описание ошибки
        cell_link: Ссылка на ячейку в Google Sheets
    """
    row_number: int
    column: str
    error_type: str
    description: str
    cell_link: str
    sheet_name: str = ""  # Добавлено для генерации ID
    admin: str = ""  # Администратор, ответственный за ошибку

    @property
    def uid(self) -> str:
        """Генерирует уникальный ID ошибки."""
        # Уникальность определяется: Лист + Строка + Колонка + Тип ошибки
        raw_id = f"{self.sheet_name}_{self.row_number}_{self.column}_{self.error_type}"
        return hashlib.md5(raw_id.encode('utf-8')).hexdigest()
