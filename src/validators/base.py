from typing import List, Dict, Any, Optional
from src.models import ValidationError

class BaseValidator:
    """
    Базовый класс валидатора данных.
    
    Обеспечивает общую логику проверки обязательных колонок и итерации по строкам.
    """
    
    def __init__(self, data: List[List[str]], required_columns: List[str], spreadsheet_id: str, sheet_name: str, sheet_id: int):
        """Инициализация валидатора с данными из Google Sheets."""
        self.data = data
        self.required_columns = required_columns
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.sheet_id = sheet_id
        self.headers = data[0] if data else []
        self.column_indices = self._map_columns()

    def _map_columns(self) -> Dict[str, int]:
        """Создаёт словарь {имя_колонки: индекс}."""
        indices = {}
        for col in self.required_columns:
            try:
                indices[col] = self.headers.index(col)
            except ValueError:
                pass
        # Добавляем также остальные колонки для условной логики
        for i, header in enumerate(self.headers):
            if header not in indices:
                indices[header] = i
        return indices

    def _get_col_letter(self, col_idx: int) -> str:
        """Преобразует индекс колонки (0-based) в букву (A, B, ..., Z, AA, AB...)."""
        col_idx += 1  # 1-based for calculation
        letters = ""
        while col_idx > 0:
            col_idx, remainder = divmod(col_idx - 1, 26)
            letters = chr(65 + remainder) + letters
        return letters

    def _generate_link(self, row_idx: int, col_name: str = None) -> str:
        """Генерирует URL-ссылку на ячейку в Google Sheets."""
        range_str = f"A{row_idx+1}"
        if col_name and col_name in self.column_indices:
            col_idx = self.column_indices[col_name]
            col_letter = self._get_col_letter(col_idx)
            range_str = f"{col_letter}{row_idx+1}"
            
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit#gid={self.sheet_id}&range={range_str}"

    def _get_val(self, row: List[Any], col_name: str) -> Any:
        """Получает значение ячейки по имени колонки."""
        idx = self.column_indices.get(col_name)
        if idx is not None and idx < len(row):
            val = row[idx]
            if isinstance(val, str):
                return val.strip()
            return val
        return ""

    def validate(self) -> List[ValidationError]:
        """Выполняет валидацию всех строк данных."""
        errors = []
        if not self.data:
            return errors

        # Проверка наличия обязательных колонок
        for col in self.required_columns:
            if col not in self.column_indices:
                errors.append(ValidationError(
                    row_number=0,
                    column=col,
                    error_type="missing_column",
                    description="Колонка не найдена",
                    cell_link="",
                    sheet_name=self.sheet_name
                ))
                return errors

        # Проверка каждой строки
        for i, row in enumerate(self.data[1:], start=1):
            errors.extend(self.validate_row(i, row))
        
        return errors

    def validate_row(self, row_idx: int, row: List[str]) -> List[ValidationError]:
        """Валидация одной строки. Переопределяется в подклассах."""
        raise NotImplementedError("Подклассы должны реализовать метод validate_row")
