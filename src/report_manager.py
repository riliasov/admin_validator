import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from src.models import ValidationError


@dataclass
class ReportItem:
    """Представление строки отчета."""
    uid: str
    is_manual: bool  # TRUE если задача создана вручную
    sheet: str
    error_column: str  # Название колонки с ошибкой
    description: str
    link: str
    created_date: str = ""  # Дата создания задачи
    admin: str = ""  # Администратор, будет заполнен позже

    def to_row(self) -> List[str]:
        """Преобразует объект в список для записи в Google Sheets."""
        link_val = self.link
        if self.link and self.link.startswith("http"):
            label = "Посмотреть"
            link_val = f'=HYPERLINK("{self.link}"; "{label}")'

        return [
            self.uid,
            bool(self.is_manual),
            self.created_date,
            self.sheet,
            self.error_column,
            self.admin,
            self.description,
            link_val
        ]


class ReportManager:
    """Менеджер управления состоянием отчета."""

    HEADERS = ["ID", "Manual task", "Дата", "Лист", "Тип", "Админ", "Описание", "Ссылка"]

    def __init__(self):
        pass

    def parse_existing_report(self, rows: List[List[str]]) -> Dict[str, ReportItem]:
        """
        Парсит существующие строки отчета в словарь {uid: ReportItem}.
        Пропускает заголовок.
        """
        items = {}
        if not rows:
            return items

        # Пропускаем заголовок если он есть
        start_idx = 1 if rows and rows[0] and rows[0][0] == "ID" else 0

        for row in rows[start_idx:]:
            if len(row) < 5:  # Минимальное количество полей
                continue
            
            uid = row[0]
            
            # Парсим is_manual из чекбокса (колонка B - Manual task)
            is_manual_cell = row[1] if len(row) > 1 else ""
            if is_manual_cell in ["TRUE", "True", "true", True, "Вручную"]:
                is_manual = True
            else:
                is_manual = False

            # Если ID нет, но задача ручная - генерируем временный ID
            # Он будет зафиксирован при сохранении
            if not uid:
                if is_manual:
                    # Генерируем ID на основе описания и даты
                    desc = row[5] if len(row) > 5 else ""
                    date = row[2] if len(row) > 2 else ""
                    raw_id = f"manual_{date}_{desc}"
                    uid = hashlib.md5(raw_id.encode('utf-8')).hexdigest()
                else:
                    continue

            # Структура: ID, Manual task, Дата, Лист, Тип, Описание, Ссылка
            # Indices: 0, 1, 2, 3, 4, 5, 6
            
            item = ReportItem(
                uid=uid,
                is_manual=is_manual,
                created_date=row[2] if len(row) > 2 else "",
                sheet=row[3] if len(row) > 3 else "",
                error_column=row[4] if len(row) > 4 else "",
                admin=row[5] if len(row) > 5 else "",
                description=row[6] if len(row) > 6 else "",
                link=row[7] if len(row) > 7 else ""
            )
            items[uid] = item
        
        return items

    def reconcile(self, existing_items: Dict[str, ReportItem], new_errors: List[ValidationError]) -> List[ReportItem]:
        """
        Сверяет текущее состояние с новыми ошибками.
        Архивация удалена - возвращаем только активный список.
        
        Returns:
            List[ReportItem]: Активные задачи
        """
        active_items = []
        
        # Словарь новых ошибок для быстрого поиска
        new_errors_map = {e.uid: e for e in new_errors}
        
        # 1. Обработка существующих записей
        for uid, item in existing_items.items():
            if uid in new_errors_map:
                # Ошибка все еще существует - обновляем данные
                new_err = new_errors_map[uid]
                item.description = new_err.description
                item.link = new_err.cell_link
                item.error_column = new_err.column # Обновляем колонку если вдруг изменилась
                item.sheet = new_err.sheet_name # Обновляем лист если вдруг изменился
                item.admin = new_err.admin # Обновляем админа
                
                active_items.append(item)
                # Удаляем из map, чтобы пометить как обработанную
                del new_errors_map[uid]
            
            elif item.is_manual:
                # Ручные задачи оставляем
                active_items.append(item)
            
            # Если ошибки нет и это не ручная задача - она просто исчезает (удаляется)

        # 2. Обработка НОВЫХ ошибок (те, что остались в new_errors_map)
        for uid, error in new_errors_map.items():
            # Получаем текущую дату в формате ДД.ММ.ГГГГ (дата создания задачи)
            from datetime import datetime
            today = datetime.now().strftime("%d.%m.%Y")
            
            new_item = ReportItem(
                uid=uid,
                is_manual=False,
                created_date=today,
                sheet=error.sheet_name,
                error_column=error.column,
                admin=error.admin,
                description=error.description,
                link=error.cell_link
            )
            active_items.append(new_item)

        # 3. Сортировка
        # Приоритет: Дата (старые сверху), Лист (Custom), Тип (А-Я)
        
        # Карта приоритетов листов
        SHEET_ORDER = {
            "Продажи": 0,
            "Тренировки": 1,
            "Обращения": 2
        }

        def sort_key(item: ReportItem):
            # 1. Дата (YYYYMMDD)
            try:
                d_str = item.created_date
                parts = d_str.split('.')
                if len(parts) == 3:
                    date_val = int(f"{parts[2]}{parts[1]}{parts[0]}")
                else:
                    date_val = 0
            except:
                date_val = 0
            
            # 2. Лист (Custom Order)
            sheet_val = SHEET_ORDER.get(item.sheet, 99)
            
            # 3. Тип (String)
            type_val = item.error_column
            
            return (date_val, sheet_val, type_val)

        # Сортируем (Python sort is stable)
        active_items.sort(key=sort_key)

        return active_items

    def _get_date_sort_value(self, item: ReportItem) -> int:
        """Возвращает числовое представление даты YYYYMMDD для сортировки."""
        try:
            parts = item.created_date.split('.')
            if len(parts) == 3:
                return int(f"{parts[2]}{parts[1]}{parts[0]}")
        except:
            pass
        return 0
