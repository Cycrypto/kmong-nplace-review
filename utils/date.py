from datetime import datetime


def normalize_date(date_str):
    """날짜 문자열을 YY.MM.DD.요일 형식으로 표준화합니다."""
    if not date_str:
        return None

    try:
        # 올해 기준 (MM.DD.요일)
        if date_str.count('.') == 2 and len(date_str.split('.')[0]) <= 2:
            # 현재 연도 추가
            current_year = datetime.now().year % 100  # 24
            return f"{current_year}.{date_str}"
        # 이미 YY.MM.DD.요일 형식
        elif date_str.count('.') == 3 and len(date_str.split('.')[0]) == 2:
            return date_str
    except Exception as e:
        logging.error(f"Failed to normalize date: {date_str}, Error: {e}")
        return None
