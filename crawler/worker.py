import os
import time
import random
import logging
import httpx
from PyQt5.QtCore import QThread, pyqtSignal

from nplace.utils.date import normalize_date, is_within_last_three_months


class CrawlWorker(QThread):
    log_signal = pyqtSignal(str)  # 로그 메시지를 전달하기 위한 시그널
    progress_signal = pyqtSignal(int)  # 진행률 업데이트를 위한 시그널
    finished_signal = pyqtSignal()  # 작업 완료 시그널

    def __init__(self, business_ids, query_file, output_dir):
        super().__init__()
        self.business_ids = business_ids
        self.query_file = query_file
        self.output_dir = output_dir
        self._is_running = True  # 스레드 중단 플래그

    @staticmethod
    def load_query(filepath):
        """쿼리 파일을 로드합니다."""
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            logging.error(f"Failed to load query file: {e}")
            raise

    def fetch_reviews(self, business_id, page=1, size=50):
        """주어진 Business ID에 대한 리뷰 데이터를 요청합니다."""
        if not self._is_running:
            return None

        url = "https://pcmap-api.place.naver.com/graphql"
        headers = {
            'accept': '*/*',
            'accept-language': 'ko',
            'content-type': 'application/json',
            'dnt': '1',
            'origin': 'https://pcmap.place.naver.com',
            'priority': 'u=1, i',
            'referer': f'https://pcmap.place.naver.com/',
            'sec-ch-ua': '"Not?A_Brand";v="99", "Chromium";v="130"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/130.0.0.0 Safari/537.36',
            'x-wtm-graphql': 'eyJhcmciOiIzMzg3OTYwNyIsInR5cGUiOiJyZXN0YXVyYW50Iiwic291cmNlIjoicGxhY2UifQ'
        }

        payload = {
            "operationName": "getVisitorReviews",
            "variables": {
                "input": {
                    "businessId": business_id,
                    "page": page,
                    "size": size
                },
                "id": business_id
            },
            "query": self.query
        }

        try:
            with httpx.Client(timeout=10) as client:  # 10초 타임아웃
                response = client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    return response.json()
                else:
                    self.log_signal.emit(f"Failed to fetch reviews for {business_id}, HTTP {response.status_code}")
                    return None
        except httpx.RequestError as e:
            self.log_signal.emit(f"Error during HTTP request for {business_id}: {e}")
            return None

    def save_reviews(self, reviews, business_id):
        """리뷰 데이터를 별도 파일로 저장합니다."""
        if not self._is_running:
            return

        try:
            # 출력 디렉터리 내 각 business_id별 JSON 파일 생성
            os.makedirs(self.output_dir, exist_ok=True)
            file_path = os.path.join(self.output_dir, f"{business_id}.jsonlines")

            with open(file_path, 'a', encoding='utf-8') as file:
                for review in reviews:
                    if not self._is_running:
                        break  # 중단 요청 시 즉시 종료

                    review['visited'] = normalize_date(review.get('visited'))
                    review['created'] = normalize_date(review.get('created'))
                    import json
                    file.write(json.dumps({"business_id": business_id, "review": review}, ensure_ascii=False) + "\n")
        except Exception as e:
            self.log_signal.emit(f"Failed to save reviews for {business_id}: {e}")

    def run(self):
        """크롤링 작업을 별도 스레드에서 실행합니다."""
        self.query = self.load_query(self.query_file)
        total = len(self.business_ids)

        for i, business_id in enumerate(self.business_ids, start=1):
            if not self._is_running:
                break  # 중단 요청이 있을 경우 작업 종료

            self.log_signal.emit(f"Fetching reviews for business ID: {business_id}")
            page = 1
            while self._is_running:
                try:
                    data = self.fetch_reviews(business_id, page=page)
                    if data:
                        reviews = data.get("data", {}).get("visitorReviews", {}).get("items", [])
                        if not reviews:
                            break  # 더 이상 리뷰가 없으면 종료
                        # 리뷰 날짜 필터링
                        filtered_reviews = [
                            review for review in reviews
                            if is_within_last_three_months(normalize_date(review.get('visited', '')))
                        ]

                        if not filtered_reviews:
                            break  # 3개월 내 리뷰가 없으면 종료
                        self.save_reviews(reviews, business_id)
                        self.log_signal.emit(f"Fetched {len(reviews)} reviews for {business_id} on page {page}")

                        # 랜덤 딜레이 적용
                        delay = random.uniform(3.0, 10.0)
                        for _ in range(int(delay * 10)):  # 0.1초 간격으로 체크
                            if not self._is_running:
                                return
                            time.sleep(0.1)

                        page += 1  # 다음 페이지로 이동
                    else:
                        self.log_signal.emit(f"No data for business ID: {business_id}")
                        break
                except Exception as e:
                    self.log_signal.emit(f"Error while crawling {business_id}: {e}")
                    break

            # 진행률 업데이트
            self.progress_signal.emit(int((i / total) * 100))

        self.finished_signal.emit()  # 작업 완료 시그널

    def stop(self):
        """작업을 중단합니다."""
        self._is_running = False



