from datetime import datetime, timedelta

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
