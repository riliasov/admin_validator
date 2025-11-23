"""
Модуль конфигурации приложения.

Загружает настройки из переменных окружения с помощью pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class AppConfig(BaseSettings):
    """
    Конфигурация приложения.
    
    Все значения загружаются из переменных окружения или .env файла.
    """
    
    # Google Sheets настройки
    spreadsheet_id: str
    sales_sheet: str = "Продажи"
    trainings_sheet: str = "Тренировки"
    report_sheet: str = "Задачи"
    leads_sheet: str = "Обращения"
    
    # Обязательные колонки для валидации продаж
    sales_required_columns: List[str] = [
        "Дата",
        "Клиент",
        "Продукт",
        "Тип",
        "Категория",
        "Количество",
        "Полная стоимость",
        "Скидка",
        "Окончательная стоимость",
        "Наличные",
        "Перевод",
        "Терминал",
        "Вдолг",
        "Админ",
        "Тренер",
        "Комментарий",
        "Бонус админа",
        "Бонус тренера",
        "Пробили на эвоторе",
        "Внесли в CRM"
    ]
    
    # Обязательные колонки для валидации тренировок
    trainings_required_columns: List[str] = [
        "Дата",
        "Начало",
        "Конец",
        "Сотрудник",
        "Тип",
        "Замена?"
    ]

    # Обязательные колонки для валидации обращений (Создание лида)
    leads_required_columns: List[str] = [
        "Дата обращения",
        # "Мобильный", # Отключено по запросу
        "Запрос при обращении",
        "Админ (создал лида)"
    ]
    
    # Путь к файлу с ключом сервисного аккаунта
    service_account_file: str = "secrets/service_account.json"
    
    # База данных (для будущего использования)
    database_url: str = "placeholder"
    
    # Уровень логирования
    log_level: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


def load_config() -> AppConfig:
    """
    Загружает конфигурацию из переменных окружения.
    
    Returns:
        AppConfig: Объект конфигурации приложения
        
    Raises:
        ValidationError: Если обязательные переменные не установлены
    """
    return AppConfig()
