from datetime import datetime, timedelta


def parse_normalized_date(date_str):
    """normalize_date의 결과(yy.mm.dd.요일)를 datetime 객체로 변환"""
    try:
        # 요일(마지막 부분) 제거: '.'으로 split 후 3개 항목만 사용
        date_part = '.'.join(date_str.split('.')[:3])
        return datetime.strptime(date_part, "%y.%m.%d")
    except ValueError:
        return None  # 잘못된 형식의 날짜 처리



def is_within_last_three_months(date_str):
    """주어진 날짜가 검색일 기준 3개월 이내인지 확인"""
    date = parse_normalized_date(date_str)
    if date is None:
        return False
    three_months_ago = datetime.now() - timedelta(days=90)
    print(three_months_ago, date)
    return date >= three_months_ago


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
