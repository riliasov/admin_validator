"""
Модуль для работы с Google Sheets API.

Обеспечивает чтение и запись данных в Google Sheets через сервисный аккаунт.
"""

from google.oauth2 import service_account
from googleapiclient.discovery import build
import os


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
        """
        Инициализация клиента.
        
        Args:
            spreadsheet_id: ID таблицы Google Sheets
            service_account_file: Путь к файлу с ключом (опционально)
        """
        self.spreadsheet_id = spreadsheet_id
        if service_account_file:
            self.SERVICE_ACCOUNT_FILE = service_account_file
        self.creds = None
        self.service = self._authenticate()

    def _authenticate(self):
        """
        Аутентификация через сервисный аккаунт.
        
        Returns:
            Resource: Объект API для работы с Sheets
            
        Raises:
            FileNotFoundError: Если файл с ключом не найден
        """
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

    def read_data(self, sheet_name: str, range_name: str = None) -> list:
        """
        Читает данные из указанного листа.
        
        Args:
            sheet_name: Название листа
            range_name: Опциональный диапазон (например, "A1:T"). Если не указан, читает весь лист.
            
        Returns:
            list: Список строк (списков значений)
        """
        try:
            target = f"{sheet_name}!{range_name}" if range_name else sheet_name
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=target
            ).execute()
            return result.get('values', [])
        except Exception as e:
            # Логирование ошибки можно добавить здесь или выше
            raise e

    def get_sheet_values(self, sheet_name: str) -> list[list[str]]:
        """
        Чтение всех значений из указанного листа.
        
        Args:
            sheet_name: Название листа в таблице
            
        Returns:
            list[list[str]]: Двумерный массив со значениями ячеек
        """
        sheet = self.service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=self.spreadsheet_id,
            range=sheet_name
        ).execute()
        return result.get('values', [])
    def read_data(self, sheet_name: str, range_name: str = None, value_render_option: str = 'FORMATTED_VALUE') -> list[list[str]]:
        """
        Читает данные из указанного листа.
        
        Args:
            sheet_name: Название листа
            range_name: Опциональный диапазон (например, "A1:B10"). Если не указан, читает весь лист.
            value_render_option: Опция формата значений ('FORMATTED_VALUE' или 'UNFORMATTED_VALUE')
            
        Returns:
            Список строк (список списков).
        """
        full_range = sheet_name
        if range_name:
            full_range = f"{sheet_name}!{range_name}"
            
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, 
            range=full_range,
            valueRenderOption=value_render_option
        ).execute()
        
        return result.get('values', [])


    def write_report(self, sheet_name: str, rows: list[list[str]]):
        """
        Перезаписывает лист отчета новыми данными.
        """
        # Очистка листа
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
        """
        Читает все данные из листа отчета.
        
        Returns:
            Список строк (список списков).
        """
        return self.get_sheet_values(sheet_name)

    def format_report_sheet(self, sheet_name: str):
        """
        Применяет форматирование к листу отчета.
        - Скрывает колонку ID (A)
        - Добавляет чекбоксы в колонку Manual task (B)
        - Закрепляет заголовок
        """
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

    def get_sheet_id_by_name(self, sheet_name: str) -> int:
        """Получает sheetId по названию листа."""
        spreadsheet = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        for sheet in spreadsheet.get('sheets', []):
            if sheet['properties']['title'] == sheet_name:
                return sheet['properties']['sheetId']
        return None
