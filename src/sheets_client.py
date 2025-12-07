"""
Модуль для работы с Google Sheets API.

Обеспечивает чтение и запись данных в Google Sheets через сервисный аккаунт.
"""

from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
import time
import random
import logging
from functools import wraps
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

def retry_api_call(max_retries=5, initial_delay=1.0, backoff_factor=2.0):
    """Декоратор повтора API-вызовов при ошибках 5xx с экспоненциальной задержкой."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except HttpError as e:
                    last_exception = e
                    # Проверяем статус код (500, 502, 503, 504)
                    if e.resp.status in [500, 502, 503, 504]:
                        if attempt == max_retries:
                            logger.error(f"❌ API call failed after {max_retries} retries: {e}")
                            raise
                        
                        sleep_time = delay + random.uniform(0, 0.5)
                        logger.warning(f"⚠️ API Error {e.resp.status}. Retrying in {sleep_time:.2f}s (Attempt {attempt + 1}/{max_retries})...")
                        time.sleep(sleep_time)
                        delay *= backoff_factor
                    else:
                        # Если ошибка не связана с доступностью сервиса, пробрасываем сразу
                        raise
                except Exception as e:
                    # Для других ошибок (например, socket timeout) тоже можно попробовать повторить
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"❌ Unexpected error after {max_retries} retries: {e}")
                        raise
                    
                    sleep_time = delay + random.uniform(0, 0.5)
                    logger.warning(f"⚠️ Unexpected Error: {e}. Retrying in {sleep_time:.2f}s (Attempt {attempt + 1}/{max_retries})...")
                    time.sleep(sleep_time)
                    delay *= backoff_factor
            
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


class SheetsClient:
    """
    Клиент для взаимодействия с Google Sheets API.
    
    Attributes:
        SCOPES: Права доступа к API
        SERVICE_ACCOUNT_FILE: Путь к файлу с ключом сервисного аккаунта
    """
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    SERVICE_ACCOUNT_FILE = 'service_account.json'

    def __init__(self, spreadsheet_id: str, service_account_file: str = None):
        """Инициализация клиента Google Sheets."""
        self.spreadsheet_id = spreadsheet_id
        if service_account_file:
            self.SERVICE_ACCOUNT_FILE = service_account_file
        self.creds = None
        self.service = self._authenticate()

    def _authenticate(self):
        """Аутентификация через сервисный аккаунт."""
        if os.path.exists(self.SERVICE_ACCOUNT_FILE):
            creds = service_account.Credentials.from_service_account_file(
                self.SERVICE_ACCOUNT_FILE, scopes=self.SCOPES)
            # Увеличиваем timeout для медленных соединений
            import httplib2
            import google_auth_httplib2
            http_base = httplib2.Http(timeout=300)  # 5 минут
            http = google_auth_httplib2.AuthorizedHttp(creds, http=http_base)
            return build('sheets', 'v4', http=http, cache_discovery=False)
        else:
            raise FileNotFoundError(f"Файл сервисного аккаунта '{self.SERVICE_ACCOUNT_FILE}' не найден.")



    def get_sheet_values(self, sheet_name: str) -> list[list[str]]:
        """Чтение всех значений из указанного листа."""
        sheet = self.service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=self.spreadsheet_id,
            range=sheet_name
        ).execute()
        return result.get('values', [])
    @retry_api_call()
    def read_data(self, sheet_name: str, range_name: str = None, value_render_option: str = 'FORMATTED_VALUE') -> list[list[str]]:
        """Читает данные из листа. range_name — опциональный диапазон (A1:B10)."""
        full_range = sheet_name
        if range_name:
            full_range = f"{sheet_name}!{range_name}"
            
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, 
            range=full_range,
            valueRenderOption=value_render_option
        ).execute()
        
        return result.get('values', [])


    @retry_api_call()
    def write_report(self, sheet_name: str, rows: list[list[str]]):
        """Перезаписывает лист отчета новыми данными."""
        self.service.spreadsheets().values().clear(
            spreadsheetId=self.spreadsheet_id,
            range=sheet_name
        ).execute()
        
        if not rows:
            return

        # Запись новых данных
        body = {
            'values': rows
        }
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=sheet_name,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()

    def read_report(self, sheet_name: str) -> list[list[str]]:
        """Читает все данные из листа отчета."""
        return self.get_sheet_values(sheet_name)

    @retry_api_call()
    def format_report_sheet(self, sheet_name: str):
        """Форматирование листа отчета: скрытие ID, чекбоксы, заморозка заголовка."""
        sheet_id = self.get_sheet_id_by_name(sheet_name)
        if sheet_id is None:
            return

        requests = []
        
        # 1. Закрепить первую строку
        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": 1
                    }
                },
                "fields": "gridProperties.frozenRowCount"
            }
        })
        
        # 2. Скрыть колонку ID (A) - index 0
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 1
                },
                "properties": {
                    "hiddenByUser": True
                },
                "fields": "hiddenByUser"
            }
        })

        # 3. Чекбокс для Manual task (B) - index 1
        requests.append({
            "setDataValidation": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,  # Пропускаем заголовок
                    "startColumnIndex": 1,
                    "endColumnIndex": 2
                },
                "rule": {
                    "condition": {
                        "type": "BOOLEAN"
                    },
                    "showCustomUi": True
                }
            }
        })

        body = {
            "requests": requests
        }
        
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body=body
        ).execute()

    @retry_api_call()
    def get_sheet_id_by_name(self, sheet_name: str) -> int:
        """Получает sheetId по названию листа."""
        spreadsheet = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        for sheet in spreadsheet.get('sheets', []):
            if sheet['properties']['title'] == sheet_name:
                return sheet['properties']['sheetId']
        return None
