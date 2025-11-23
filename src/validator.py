"""
Модуль валидации данных из Google Sheets.

Содержит базовый класс валидатора и специализированные валидаторы 
для таблиц продаж и тренировок.
"""

from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
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


# Utility functions
def parse_date_value(val) -> datetime:
    """
    Парсит дату из различных форматов.
    Поддерживает Serial Date и строки.
    """
    if not val:
        return None
    
    # Serial Date (число)
    if isinstance(val, (int, float)):
        base_date = datetime(1899, 12, 30)
        return base_date + timedelta(days=val)
    
    # Строка
    if isinstance(val, str):
        clean_val = val.split(" ")[-1]
        for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m"]:
            try:
                dt = datetime.strptime(clean_val, fmt)
                if "%Y" not in fmt:
                    dt = dt.replace(year=datetime.now().year)
                return dt
            except ValueError:
                continue
    
    return None


def validate_phone_format(phone: str) -> bool:
    """
    Проверяет формат телефона: 79XXXXXXXXX (11 цифр).
    """
    if not phone:
        return False
    
    import re
    clean_phone = re.sub(r'[^0-9]', '', str(phone))
    return len(clean_phone) == 11 and clean_phone.startswith('7')


def parse_float(val) -> float:
    """
    Парсит число из значения.
    """
    if val is None or val == "":
        return 0.0
    
    if isinstance(val, (int, float)):
        return float(val)
    
    clean_val = str(val).replace(" ", "").replace(",", ".").replace("\xa0", "")
    if "%" in clean_val:
        clean_val = clean_val.replace("%", "")
    try:
        return float(clean_val)
    except ValueError:
        return 0.0


def parse_discount(val) -> float:
    """
    Парсит скидку.
    """
    if val is None or val == "":
        return 0.0
    
    if isinstance(val, (int, float)):
        return float(val)
    
    clean_val = str(val).replace(" ", "").replace(",", ".").replace("\xa0", "")
    is_percent = "%" in str(val)
    clean_val = clean_val.replace("%", "")
    try:
        num = float(clean_val)
        if is_percent:
            return num / 100.0
        return num
    except ValueError:
        return 0.0


def format_money(val: float) -> str:
    """Форматирует число как деньги: 8 888,00"""
    return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ")




from typing import List, Dict, Any



class BaseValidator:
    """
    Базовый класс вал

идатора данных.
    
    Обеспечивает общую логику проверки обязательных колонок и итерации по строкам.
    """
    
    def __init__(self, data: List[List[str]], required_columns: List[str], spreadsheet_id: str, sheet_name: str, sheet_id: int):
        """
        Инициализация валидатора.
        
        Args:
            data: Двумерный массив данных из Google Sheets
            required_columns: Список обязательных колонок
            spreadsheet_id: ID таблицы Google Sheets
            sheet_name: Название листа
            sheet_id: GID листа (числовой ID)
        """
        self.data = data
        self.required_columns = required_columns
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.sheet_id = sheet_id
        self.headers = data[0] if data else []
        self.column_indices = self._map_columns()

    def _map_columns(self) -> Dict[str, int]:
        """
        Создает карту индексов колонок.
        
        Returns:
            Dict[str, int]: Словарь {название_колонки: индекс}
        """
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
        """
        Генерирует ссылку на строку или ячейку в Google Sheets.
        
        Args:
            row_idx: Индекс строки (0-based, где 0 - заголовок)
            col_name: Название колонки (опционально)
            
        Returns:
            str: URL ссылка
        """
        # row_idx + 1, так как в Sheets нумерация с 1
        # Если передан col_name, ищем его индекс
        range_str = f"A{row_idx+1}"
        if col_name and col_name in self.column_indices:
            col_idx = self.column_indices[col_name]
            col_letter = self._get_col_letter(col_idx)
            range_str = f"{col_letter}{row_idx+1}"
            
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit#gid={self.sheet_id}&range={range_str}"

    def _get_val(self, row: List[Any], col_name: str) -> Any:
        """
        Получает значение ячейки по названию колонки.
        """
        idx = self.column_indices.get(col_name)
        if idx is not None and idx < len(row):
            val = row[idx]
            if isinstance(val, str):
                return val.strip()
            return val
        return ""

    def validate(self) -> List[ValidationError]:
        """
        Выполняет валидацию всех данных.
        
        Returns:
            List[ValidationError]: Список найденных ошибок
        """
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
        """
        Валидация одной строки данных. Должен быть переопределен в подклассах.
        
        Args:
            row_idx: Индекс строки (начиная с 1 для первой строки данных)
            row: Данные строки
            
        Returns:
            List[ValidationError]: Список ошибок в этой строке
        """
        raise NotImplementedError("Подклассы должны реализовать метод validate_row")


class SalesValidator(BaseValidator):
    """Валидатор для таблицы продаж."""
    

    def validate_row(self, row_idx: int, row: List[Any]) -> List[ValidationError]:
        """
        Проверяет строку продаж на корректность данных по сложным правилам.
        Использует UNFORMATTED_VALUE (типы сохраняются).
        """
        errors = []
        # row_idx приходит из enumerate(data[1:], start=1).
        # Если мы читаем A2:T, то data[0] - это A2 (Header). data[1] - это A3 (Data).
        # Значит row_idx=1 соответствует A3.
        # В Google Sheets это строка 3.
        # Но мы читаем диапазон A2:T.
        # Если row_idx=1 (первая строка данных), это 2-я строка в массиве data.
        # data[0] = Row 2 (Header). data[1] = Row 3.
        # Значит sheet_row_num = row_idx + 2. (1+2=3). Correct.
        sheet_row_num = row_idx + 2
        
        # Извлекаем админа для всех ошибок в этой строке
        admin_val = self._get_val(row, "Админ")
        admin = str(admin_val).strip() if admin_val else "Уточнить"
        
        # 0. Проверка даты и фильтрация будущего
        date_val = self._get_val(row, "Дата")
        dt = parse_date_value(date_val)
        
        # Если даты нет или она в будущем - пропускаем строку
        if not dt:
            return []
            
        # Сбрасываем время для сравнения только дат
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if dt > today:
            return []

        # 0.1 Проверка на "Уточнить"
        for col_name in self.required_columns:
            val = self._get_val(row, col_name)
            if isinstance(val, str) and "уточнить" in val.lower():
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column=col_name,
                    error_type="clarify_needed",
                    description=f"Требуется уточнение: {val}",
                    cell_link=self._generate_link(sheet_row_num - 1, col_name),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))

        # 1. Какие строки надо проверять
        client = self._get_val(row, "Клиент")
        product = self._get_val(row, "Продукт")
        evotor = self._get_val(row, "Пробили на эвоторе")
        crm = self._get_val(row, "Внесли в CRM")
        
        has_client = bool(client)
        has_product = bool(product)
        
        # Для булевых полей в UNFORMATTED может прийти bool или строка
        is_evotor = False
        if isinstance(evotor, bool):
            is_evotor = evotor
        elif isinstance(evotor, str):
            is_evotor = evotor.upper() in ["TRUE", "ИСТИНА"]
            
        is_crm = False
        if isinstance(crm, bool):
            is_crm = crm
        elif isinstance(crm, str):
            is_crm = crm.upper() in ["TRUE", "ИСТИНА"]
        
        should_validate = has_client or has_product or is_evotor or is_crm
        
        if not should_validate:
            return []

        # --- 2. Проверка обязательных полей ---
        training_type = self._get_val(row, "Тип")
        is_goods = str(training_type) == "Товар"
        
        payment_fields = ["Наличные", "Перевод", "Терминал", "Вдолг"]
        
        for col_name in self.required_columns:
            # Исключения
            if col_name == "Скидка": continue
            if col_name == "Комментарий": continue
            if col_name in payment_fields: continue # Проверяем только сумму
            if col_name in ["Бонус админа", "Бонус тренера"]: continue # Проверяем отдельно
            
            if col_name == "Тренер":
                # Тренер может быть пустым, если Тип != "Бассейн" и Тип != "Ванны"
                # И если Тип = "Товар", тренер тоже не обязателен
                if is_goods: continue
                if str(training_type) not in ["Бассейн", "Ванны"]: continue
            
            val = self._get_val(row, col_name)
            # Проверка на пустоту. 0 - это значение, "" или None - пустота.
            if val is None or val == "":
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column=col_name,
                    error_type="empty",
                    description=f"Поле '{col_name}' должно быть заполнено",
                    cell_link=self._generate_link(sheet_row_num - 1, col_name),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))

        # --- 3. Проверка арифметики стоимости ---
        full_price = parse_float(self._get_val(row, "Полная стоимость"))
        discount_val = self._get_val(row, "Скидка")
        discount_rate = parse_discount(discount_val)
        final_price = parse_float(self._get_val(row, "Окончательная стоимость"))
        
        calc_final = full_price * (1.0 - discount_rate)
        
        if abs(calc_final - final_price) > 1.0:
            # Форматируем описание ошибки
            fmt_full = format_money(full_price)
            fmt_final = format_money(final_price)
            fmt_calc = format_money(calc_final)
            # Скидка в процентах
            fmt_disc = f"{discount_rate*100:.2f}".replace(".", ",") + "%"
            
            errors.append(ValidationError(
                row_number=sheet_row_num,
                column="Окончательная стоимость",
                error_type="math_error",
                description=f"Ошибка расчета: {fmt_full} * (1 - {fmt_disc}) = {fmt_calc}, а указано {fmt_final}",
                cell_link=self._generate_link(sheet_row_num - 1, "Окончательная стоимость"),
                sheet_name=self.sheet_name,
                    admin=admin
            ))

        # --- 4. Проверка поступления оплаты ---
        cash = parse_float(self._get_val(row, "Наличные"))
        transfer = parse_float(self._get_val(row, "Перевод"))
        terminal = parse_float(self._get_val(row, "Терминал"))
        debt = parse_float(self._get_val(row, "Вдолг"))
        
        sum_pay = cash + transfer + terminal + debt
        
        if abs(sum_pay - final_price) > 1.0:
             fmt_sum = format_money(sum_pay)
             fmt_final = format_money(final_price)
             errors.append(ValidationError(
                row_number=sheet_row_num,
                column="Окончательная стоимость",
                error_type="payment_error",
                description=f"Сумма оплаты ({fmt_sum}) не совпадает с ценой ({fmt_final})",
                cell_link=self._generate_link(sheet_row_num - 1, "Окончательная стоимость"),
                sheet_name=self.sheet_name,
                    admin=admin
            ))

        # --- 5. Проверка обязательности проведения продажи ---
        
        # Если Тип = Товар
        if is_goods:
            # "Внесли в CRM" должен быть FALSE
            if is_crm:
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Внесли в CRM",
                    error_type="process_error",
                    description="Для товаров 'Внесли в CRM' должно быть FALSE",
                    cell_link=self._generate_link(sheet_row_num - 1, "Внесли в CRM"),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))
            # "Пробили на эвоторе" игнорируем (может быть True/False)
        else:
            # Старая логика для услуг
            if final_price > 0 and not is_crm:
                 errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Внесли в CRM",
                    error_type="process_error",
                    description="Продажа не внесена в CRM",
                    cell_link=self._generate_link(sheet_row_num - 1, "Внесли в CRM"),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))
            
            # Эвотор
            is_debt_return = "долг" in str(training_type).lower() or "долг" in str(product).lower()
            if final_price > 0 and not is_debt_return and not is_evotor:
                 errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Пробили на эвоторе",
                    error_type="process_error",
                    description="Чек не пробит на Эвоторе",
                    cell_link=self._generate_link(sheet_row_num - 1, "Пробили на эвоторе"),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))
        
        # --- 6. Проверка обязательности комментария ---
        comment = str(self._get_val(row, "Комментарий")).strip()
        
        # 6. Проверка обязательности комментария с приоритетом
        product_lower = str(product).lower()
        
        # Флаг: проверили ли мы специальный продукт
        is_special_product = False
        
        # 6.1 Специальные продукты требуют специфичный комментарий (приоритет 1)
        if "подарок" in product_lower:
            is_special_product = True
            if not comment:
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Комментарий",
                    error_type="empty",
                    description="Уточнить повод для подарка занятия",
                    cell_link=self._generate_link(sheet_row_num - 1, "Комментарий"),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))
        elif "возврат абонемента" in product_lower:
            is_special_product = True
            if not comment:
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Комментарий",
                    error_type="empty",
                    description="Уточнить причину возврата абонемента",
                    cell_link=self._generate_link(sheet_row_num - 1, "Комментарий"),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))
        elif "перерасчёт" in product_lower or "перерасчет" in product_lower:
            is_special_product = True
            if not comment:
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Комментарий",
                    error_type="empty",
                    description="Уточнить причину перерасчёта",
                    cell_link=self._generate_link(sheet_row_num - 1, "Комментарий"),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))
        elif "сертификат" in product_lower:
            is_special_product = True
            if not comment:
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Комментарий",
                    error_type="empty",
                    description="Уточнить информацию о сертификате",
                    cell_link=self._generate_link(sheet_row_num - 1, "Комментарий"),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))
        
        # 6.2 100% скидка требует комментарий (приоритет 2 - только если НЕ спецпродукт)
        if not is_special_product and discount_rate >= 0.99:
            if not comment:
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Комментарий",
                    error_type="empty",
                    description="При скидке 100% обязателен комментарий",
                    cell_link=self._generate_link(sheet_row_num - 1, "Комментарий"),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))
        
        return errors




class TrainingsValidator(BaseValidator):
    """Валидатор для таблицы тренировок."""
    
    VALID_STATUSES = [
        "Администратор",
        "Отработано",
        "Отмена по вине центра",
        "Отмена по вине клиента",
        "Справка",
        "Пропуск без списания",
        "Пропуск",
        "Лояльный пропуск",
        "Перенос",
        "Смена",
        "Посетили"
    ]

    def validate_row(self, row_idx: int, row: List[str]) -> List[ValidationError]:
        """
        Проверяет строку тренировки на корректность данных.
        """
        errors = []
        sheet_row_num = row_idx + 1
        
        # Извлекаем админа для всех ошибок в этой строке
        # Для Тренировок: логика зависит от статуса
        client = self._get_val(row, "Клиент")
        status = self._get_val(row, "Статус")
        date_val = self._get_val(row, "Дата")
        
        # Для статусов пропусков/отмен берём сотрудника напрямую
        cancellation_statuses = [
            "Отмена по вине центра",
            "Пропуск без списания",
            "Пропуск",
            "Лояльный пропуск"
        ]
        
        if status in cancellation_statuses:
            # Для пропусков/отмен - сотрудник из этой же строки
            employee = self._get_val(row, "Сотрудник")
            admin = employee if employee else "Уточнить"
        else:
            # Для остальных - поиск по критериям
            admin = self._find_admin_for_training(client, status, date_val)
        
        # 0. Проверка даты и фильтрация будущего
        dt = parse_date_value(date_val)
        
        # Если дата корректна и она в будущем - пропускаем валидацию
        if dt:
            # Сбрасываем время для сравнения только дат
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if dt > today:
                return [] # Игнорируем будущие даты
        
        # 0.1 Исключение для Администратора (пустой день)
        training_type = self._get_val(row, "Тип")
        
        start = self._get_val(row, "Начало")
        end = self._get_val(row, "Конец")
        employee = self._get_val(row, "Сотрудник")
        
        if client == "Администратор" and status == "Администратор" and training_type == "Администратор":
            # Если время и сотрудник не заполнены - это выходной/пустой день, не ошибка
            if not start and not end and not employee:
                return []
        
        # 1. Обязательные поля
        for col_name in self.required_columns:
            val = self._get_val(row, col_name)
            
            # Проверка на пустоту (0 считается значением)
            if not val and val != 0:
                description = f"Поле '{col_name}' должно быть заполнено"
                
                # Кастомные сообщения и логика
                if col_name == "Начало":
                    description = "Отсутствует время начала"
                elif col_name == "Конец":
                    description = "Отсутствует время окончания"
                elif col_name == "Дата":
                    description = "Отсутствует дата"
                elif col_name == "Сотрудник":
                    # Проверяем тип для уточнения ошибки
                    if training_type == "Администратор":
                        # Ошибка "Не назначен администратор" только если заполнено время
                        if not start and not end:
                            continue # Если времени нет, то и админ не обязателен
                        description = "Не назначен администратор"
                    else:
                        description = "Не назначен тренер"

                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column=col_name,
                    error_type="empty",
                    description=description,
                    cell_link=self._generate_link(row_idx, col_name),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))
                continue
            
            # Проверка формата даты (если значение есть)
            if col_name == "Дата" and not dt:
                 errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column=col_name,
                    error_type="invalid_format",
                    description=f"Значение '{val}' не является корректной датой",
                    cell_link=self._generate_link(row_idx, col_name),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))
            
            # Проверка булева поля "Замена?"
            if col_name == "Замена?":
                 if val.lower() not in ["да", "нет", "yes", "no"]:
                     errors.append(ValidationError(
                        row_number=sheet_row_num,
                        column=col_name,
                        error_type="invalid_format",
                        description=f"Значение '{val}' должно быть Да или Нет",
                        cell_link=self._generate_link(row_idx, col_name),
                        sheet_name=self.sheet_name,
                        admin=admin
                    ))
        
        # 2. Проверка валидности статуса
        if status and status not in self.VALID_STATUSES:
            errors.append(ValidationError(
                row_number=sheet_row_num,
                column="Статус",
                error_type="invalid_value",
                description=f"Недопустимый статус: '{status}'",
                cell_link=self._generate_link(row_idx, "Статус"),
                sheet_name=self.sheet_name,
                admin=admin
            ))
        
        # 3. Проверка: Если Клиент заполнен, то Сотрудник обязателен (кроме исключений)
        if client and client != "Администратор":
            # Исключения: если статус = "Администратор"
            if status != "Администратор":
                if not employee or employee == "" or employee == "Без тренера":
                    errors.append(ValidationError(
                        row_number=sheet_row_num,
                        column="Сотрудник",
                        error_type="empty",
                        description="Для клиента сотрудник обязателен и не может быть 'Без тренера'",
                        cell_link=self._generate_link(row_idx, "Сотрудник"),
                        sheet_name=self.sheet_name,
                        admin=admin
                    ))
        
        
        # 5. Проверка #REF! в комментариях
        comment = self._get_val(row, "Комментарий")
        if comment and "#REF!" in str(comment):
            errors.append(ValidationError(
                row_number=sheet_row_num,
                column="Комментарий",
                error_type="formula_error",
                description="Ошибка формулы в комментарии (#REF!)",
                cell_link=self._generate_link(row_idx, "Комментарий"),
                sheet_name=self.sheet_name,
                admin=admin
            ))
        
        # 6. Проверка обязательности комментария для статусов пропусков/отмен
        if status in cancellation_statuses:
            comment_str = str(comment).strip()
            template_comment = "Указать причину пропуска"
            
            if not comment_str or comment_str == template_comment:
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Комментарий",
                    error_type="empty",
                    description=f"Для статуса '{status}' требуется указать причину пропуска",
                    cell_link=self._generate_link(row_idx, "Комментарий"),
                    sheet_name=self.sheet_name,
                    admin=admin
                ))
        
        return errors

    def _find_admin_for_training(self, client: str, status: str, date_val: str) -> str:
        """
        Ищет админа для тренировки по критериям:
        - Клиент совпадает
        - Статус совпадает
        - Тип = "Администратор"
        - Дата совпадает
        
        Приоритет:
        1. Категория = "Онлайн"
        2. Категория = "В центре"
        
        Returns:
            str: Имя админа или "Уточнить"
        """
        if not client or not status or not date_val:
            return "Уточнить"
        
        # Ищем подходящие строки
        candidates = []
        
        for row in self.data[1:]:  # Skip header
            row_client = self._get_val(row, "Клиент")
            row_status = self._get_val(row, "Статус")
            row_type = self._get_val(row, "Тип")
            row_date = self._get_val(row, "Дата")
            
            if (row_client == client and 
                row_status == status and 
                row_type == "Администратор" and 
                row_date == date_val):
                
                employee = self._get_val(row, "Сотрудник")
                category = self._get_val(row, "Категория")
                
                if employee:
                    candidates.append((employee, category))
        
        if not candidates:
            return "Уточнить"
        
        # Приоритет по категории
        for employee, category in candidates:
            if category == "Онлайн":
                return employee
        
        for employee, category in candidates:
            if category == "В центре":
                return employee
        
        # Возвращаем первого найденного
        return candidates[0][0]

    def validate(self) -> List[ValidationError]:
        """
        Переопределенный метод валидации для Trainings.
        Добавляет логику проверки последнего занятия клиента.
        """
        # Сначала выполняем стандартную валидацию
        errors = super().validate()
        
        if not self.data or len(self.data) < 2:
            return errors
        
        # Собираем индексы последних занятий для каждого клиента
        client_last_sessions = {}  # {client_name: (row_idx, row_data)}
        
        for i, row in enumerate(self.data[1:], start=1):
            client = str(self._get_val(row, "Клиент")).strip()
            
            if not client or client == "Администратор":
                continue
            
            # Сохраняем последнее (самое нижнее) занятие для каждого клиента
            client_last_sessions[client] = (i, row)
        
        # Проверяем комментарий об абонементе ТОЛЬКО для последних занятий
        for client, (row_idx, row) in client_last_sessions.items():
            visits = self._get_val(row, "Всего посещено")
            remaining = self._get_val(row, "Остаток занятий")
            comment = str(self._get_val(row, "Комментарий")).strip()
            
            try:
                visits_num = int(visits) if visits else 0
                remaining_num = int(remaining) if remaining else 0
                
                if visits_num > 1 and remaining_num == 0:
                    if not comment:
                        sheet_row_num = row_idx + 1
                        
                        # Извлекаем админа для этой строки
                        client_for_admin = self._get_val(row, "Клиент")
                        status_for_admin = self._get_val(row, "Статус")
                        date_for_admin = self._get_val(row, "Дата")
                        admin = self._find_admin_for_training(client_for_admin, status_for_admin, date_for_admin)
                        
                        errors.append(ValidationError(
                            row_number=sheet_row_num,
                            column="Комментарий",
                            error_type="empty",
                            description="Требуется комментарий об ответе клиента на предложение продлить абонемент",
                            cell_link=self._generate_link(row_idx, "Комментарий"),
                            sheet_name=self.sheet_name,
                            admin=admin
                        ))
            except (ValueError, TypeError):
                pass  # Игнорируем ошибки парсинга
        
        return errors

    def _is_valid_date(self, val: str) -> bool:
        """Обертка для совместимости, использует parse_date_value."""
        return parse_date_value(val) is not None



class LeadsValidator(BaseValidator):
    """
    Валидатор для таблицы Обращения.
    """
    
    # FUTURE LOGIC (Правила на будущее):
    #
    # 2. Создание клиента:
    #    Обязательные поля:
    #    - Фамилия взрослого
    #    - Имя взрослого
    #    - Имя ребенка
    #    - Дата рождения ребенка
    #    - Пол ребёнка
    #    - Админ (создал клиента)
    #
    # 3. Запись на занятие:
    #    Обязательные поля:
    #    - Дата запланированного занятия
    #    - Комментарий при записи
    #    - Админ (записал на занятие)

    def _validate_phone_format(self, phone: str) -> bool:
        """
        Проверяет формат телефона: должен быть 79XXXXXXXXX.
        11 цифр, только цифры, начинается с 7.
        """
        if not phone:
            return False
        
        # Убираем все кроме цифр
        import re
        clean_phone = re.sub(r'[^0-9]', '', str(phone))
        
        # Проверяем: 11 цифр, начинается с 7
        return len(clean_phone) == 11 and clean_phone.startswith('7')

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

        # 1. Проверка обязательных полей (Создание лида)
        # Используем стандартный механизм BaseValidator, так как теперь имена уникальны
        for col_name in self.required_columns:
            val = self._get_val(row, col_name)
            
            if not val:
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column=col_name,
                    error_type="empty",
                    description=f"Поле '{col_name}' обязательно для создания лида",
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
                    errors.append(ValidationError(
                        row_number=sheet_row_num,
                        column=field,
                        error_type="empty",
                        description=f"Поле '{field}' обязательно при создании клиента",
                        cell_link=self._generate_link(sheet_row_num - 1, field),
                        sheet_name=self.sheet_name,
                        admin=client_admin  # Берём из L!
                    ))
            
            # Проверка телефона
            phone = self._get_val(row, "Мобильный")
            if not self._validate_phone_format(phone):
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Мобильный",
                    error_type="invalid_format",
                    description="Телефон должен быть в формате 79XXXXXXXXX (11 цифр)",
                    cell_link=self._generate_link(sheet_row_num - 1, "Мобильный"),
                    sheet_name=self.sheet_name,
                    admin=client_admin
                ))
        
        # Правило 2: Если F:I заполнены → админ (создал клиента) обязателен
        client_core_fields = client_fields[:4]  # Фамилия, Имя взрослого, Имя ребенка, Дата рождения
        core_filled = all(self._get_val(row, f) for f in client_core_fields)
        
        if core_filled and not client_admin_val:
            errors.append(ValidationError(
                row_number=sheet_row_num,
                column="Админ (создал клиента)",
                error_type="empty",
                description="Админ (создал клиента) обязателен если заполнены данные клиента",
                cell_link=self._generate_link(sheet_row_num - 1, "Админ (создал клиента)"),
                sheet_name=self.sheet_name,
                admin="Уточнить"
            ))
            
            # Проверка телефона
            phone = self._get_val(row, "Мобильный")
            if not self._validate_phone_format(phone):
                errors.append(ValidationError(
                    row_number=sheet_row_num,
                    column="Мобильный",
                    error_type="invalid_format",
                    description="Телефон должен быть в формате 79XXXXXXXXX (11 цифр)",
                    cell_link=self._generate_link(sheet_row_num - 1, "Мобильный"),
                    sheet_name=self.sheet_name,
                    admin="Уточнить"
                ))

        return errors

