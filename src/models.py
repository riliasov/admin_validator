from pydantic import BaseModel
import hashlib

class ValidationError(BaseModel):
    """Модель ошибки валидации."""
    row_number: int
    column: str
    error_type: str
    description: str
    cell_link: str
    sheet_name: str = ""
    admin: str = ""
    error_date: str = ""

    @property
    def uid(self) -> str:
        """Генерирует уникальный ID ошибки."""
        # Уникальность определяется: Лист + Строка + Колонка + Тип ошибки
        raw_id = f"{self.sheet_name}_{self.row_number}_{self.column}_{self.error_type}"
        return hashlib.md5(raw_id.encode('utf-8')).hexdigest()
