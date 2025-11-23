from typing import List, Any
from datetime import datetime
from src.models import ValidationError
from src.utils import parse_date_value, parse_float, parse_discount, format_money
from .base import BaseValidator

class SalesValidator(BaseValidator):
    """Валидатор для таблицы продаж."""
    

    def validate_row(self, row_idx: int, row: List[Any]) -> List[ValidationError]:
        """
        Проверяет строку продаж на корректность данных по сложным правилам.
        Использует UNFORMATTED_VALUE (типы сохраняются).
        """
        errors = []
        # row_idx starts from 1 (data start) -> sheet row 2 (header) -> row 3 (data)
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
