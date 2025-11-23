import logging
import time
import sys
from src.config import load_config
from src.sheets_client import SheetsClient
from src.validator import SalesValidator, TrainingsValidator, LeadsValidator
from src.report_manager import ReportManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    """Главная функция запуска валидации."""
    start_time = time.time()
    
    logging.info("🚀 Запуск Planeta Quality Checker...")
    
    try:
        # Загрузка конфигурации
        config = load_config()
        logger.info("✅ Конфигурация загружена.")
    except Exception as e:
        logger.critical(f"❌ Ошибка загрузки конфигурации: {e}")
        return

    try:
        client = SheetsClient(config.spreadsheet_id, config.service_account_file)
        logger.info("✅ Google Sheets клиент инициализирован.")
    except Exception as e:
        logger.critical(f"❌ Ошибка инициализации клиента Google Sheets: {e}")
        return

    # 2. Получение ID листов с fallback
    sales_sheet_id = 623132210  # Fallback
    trainings_sheet_id = 1856560934  # Fallback
    leads_sheet_id = 0 # Fallback
    
    try:
        sales_sheet_id = client.get_sheet_id_by_name(config.sales_sheet) or sales_sheet_id
        trainings_sheet_id = client.get_sheet_id_by_name(config.trainings_sheet) or trainings_sheet_id
        leads_sheet_id = client.get_sheet_id_by_name(config.leads_sheet) or leads_sheet_id
        logger.info(f"🆔 ID листов: Sales={sales_sheet_id}, Trainings={trainings_sheet_id}, Leads={leads_sheet_id}")
    except Exception as e:
        logger.error(f"❌ Не удалось получить ID листов: {e}. Используем fallback ID.")
        # Fallback IDs are already set above

    all_errors = []


    # 3. Обработка таблицы продаж
    t_sales = time.time()
    try:
        sales_data = client.read_data(config.sales_sheet, "A2:T", value_render_option='UNFORMATTED_VALUE')
        
        if sales_data:
            sales_validator = SalesValidator(
                data=sales_data,
                required_columns=config.sales_required_columns,
                spreadsheet_id=config.spreadsheet_id,
                sheet_name=config.sales_sheet,
                sheet_id=sales_sheet_id
            )
            
            sales_errors = sales_validator.validate()
            
            if sales_errors:
                logger.info(f"📋 Продажи: найдено {len(sales_errors)} ошибок")
                all_errors.extend(sales_errors)

    except Exception as e:
        logger.error(f"❌ Ошибка обработки таблицы продаж: {e}")

    # 4. Обработка таблицы тренировок
    t_trainings = time.time()
    try:
        trainings_data = client.read_data(config.trainings_sheet, "A1:L")
        
        trainings_validator = TrainingsValidator(
            data=trainings_data,
            required_columns=config.trainings_required_columns,
            spreadsheet_id=config.spreadsheet_id,
            sheet_name=config.trainings_sheet,
            sheet_id=trainings_sheet_id
        )
        trainings_errors = trainings_validator.validate()
        
        if trainings_errors:
            logger.info(f"📋 Тренировки: найдено {len(trainings_errors)} ошибок")
            all_errors.extend(trainings_errors)
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки таблицы тренировок: {e}")

    # 5. Обработка таблицы обращений
    t_leads = time.time()
    try:
        # Читаем A2:V как запрошено (A2 - заголовок)
        leads_data = client.read_data(config.leads_sheet, "A2:V")
        
        leads_validator = LeadsValidator(
            data=leads_data,
            required_columns=config.leads_required_columns,
            spreadsheet_id=config.spreadsheet_id,
            sheet_name=config.leads_sheet,
            sheet_id=leads_sheet_id
        )
        leads_errors = leads_validator.validate()
        
        if leads_errors:
            logger.info(f"📋 Обращения: найдено {len(leads_errors)} ошибок")
            all_errors.extend(leads_errors)
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки таблицы обращений: {e}")

    # 5. Обновление отчета
    try:
        report_data = client.read_data(config.report_sheet)
        
        report_manager = ReportManager()
        existing_items = report_manager.parse_existing_report(report_data)
        
        active_rows = report_manager.reconcile(existing_items, all_errors)
        
        logger.info(f"📊 Итого задач: {len(active_rows)} ({len([r for r in active_rows if r.is_manual])} ручных)")
        
        report_content = [ReportManager.HEADERS] + [item.to_row() for item in active_rows]
        
        client.write_report(config.report_sheet, report_content)
        client.format_report_sheet(config.report_sheet)
        
    except Exception as e:
        logger.critical(f"❌ Ошибка при формировании отчета: {e}")
        sys.exit(1)
        
    except Exception as e:
        logger.critical(f"❌ Ошибка при формировании отчета: {e}")
        sys.exit(1)

    logger.info(f"🎉 Готово! Общее время: {time.time() - t_sales:.2f} сек.")

if __name__ == "__main__":
    main()
