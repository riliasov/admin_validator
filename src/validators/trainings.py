from typing import List
from datetime import datetime
from src.models import ValidationError
from src.utils import parse_date_value
from .base import BaseValidator

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
            # Для пропусков/отмен - ищем админа, работавшего в этот день
            admin = self._find_admin_on_duty(date_val)
        else:
            # Для остальных - используем поиск по дате (как наиболее надежный метод)
            admin = self._find_admin_on_duty(date_val)
        
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
                    description = "Отсутствует время начала смены"
                elif col_name == "Конец":
                    description = "Отсутствует время окончания смены"
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
        if status:
            # Специфичная логика для статусов подтверждения
            confirmation_statuses = ["Подтвердили", "Не подтвердили"]
            
            if status in confirmation_statuses:
                # Разрешены только в будущем (включая сегодня)
                if dt:
                    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    if dt < today:
                        errors.append(ValidationError(
                            row_number=sheet_row_num,
                            column="Статус",
                            error_type="invalid_value",
                            description=f"Статус '{status}' недопустим для прошедших дат",
                            cell_link=self._generate_link(row_idx, "Статус"),
                            sheet_name=self.sheet_name,
                            admin=admin
                        ))
            elif status not in self.VALID_STATUSES:
                # Для остальных статусов - стандартная проверка по белому списку
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

    def _find_admin_on_duty(self, date_val: str) -> str:
        """
        Ищет админа, работавшего в указанную дату.
        
        Критерии:
        - Дата совпадает
        - Тип = "Администратор"
        - Клиент = "Администратор" (обычно так обозначается смена админа)
        
        Приоритет:
        1. Категория = "Онлайн"
        2. Категория = "В центре"
        
        Returns:
            str: Имя админа или "Уточнить"
        """
        if not date_val:
            return "Уточнить"
        
        candidates = []
        
        for row in self.data[1:]:  # Skip header
            row_date = self._get_val(row, "Дата")
            row_type = self._get_val(row, "Тип")
            row_client = self._get_val(row, "Клиент")
            
            # Ищем строки смен администраторов
            if row_date == date_val and row_type == "Администратор" and row_client == "Администратор":
                employee = self._get_val(row, "Сотрудник")
                category = self._get_val(row, "Категория")
                
                if employee:
                    candidates.append((employee, category))
        
        if not candidates:
            return "Уточнить"
        
        # Приоритет 1: Онлайн
        for employee, category in candidates:
            if category and "Онлайн" in str(category):
                return employee
        
        # Приоритет 2: В центре
        for employee, category in candidates:
            if category and "В центре" in str(category):
                return employee
        
        # Если категории не указаны или другие, возвращаем первого найденного
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
                        admin = self._find_admin_on_duty(date_for_admin)
                        
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
