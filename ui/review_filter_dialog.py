import sys
import os
import json
import re
from datetime import datetime, date

import pandas as pd
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QTableWidget,
    QTableWidgetItem, QLabel, QMessageBox, QFileDialog, QTextEdit, QLineEdit, QDateEdit
)
from PyQt5.QtCore import Qt, QDate


class ReviewFilterDialog(QDialog):
    def __init__(self, output_dir="output"):
        super().__init__()
        self.setWindowTitle("결과 확인 및 내보내기")
        self.output_dir = output_dir  # 저장된 JSONLines 파일 경로
        self.filtered_data = []  # 필터링된 데이터를 저장
        self.current_filtered_data = []  # 현재 필터링된 데이터를 저장
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 날짜 선택 드롭다운 (크롤링 시작 날짜)
        date_selection_layout = QHBoxLayout()
        self.crawling_date_combo = QComboBox()
        self.crawling_date_combo.currentIndexChanged.connect(self.load_selected_date)
        date_selection_layout.addWidget(QLabel("크롤링 시작 날짜 선택:"))
        date_selection_layout.addWidget(self.crawling_date_combo)
        layout.addLayout(date_selection_layout)

        # 경로 새로고침 버튼
        refresh_button = QPushButton("날짜 새로고침")
        refresh_button.clicked.connect(self.refresh_date_list)
        layout.addWidget(refresh_button)

        # 리뷰 작성 날짜 필터링 (시작 날짜와 종료 날짜)
        write_date_filter_layout = QHBoxLayout()

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        # 현재 월의 첫 날로 설정
        today = date.today()
        first_day_of_month = date(today.year, today.month, 1)
        self.start_date_edit.setDate(QDate(first_day_of_month.year, first_day_of_month.month, first_day_of_month.day))

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setDate(QDate.currentDate())  # 기본 종료 날짜: 오늘

        filter_button = QPushButton("작성 날짜로 필터링")
        filter_button.clicked.connect(self.filter_by_write_date)

        write_date_filter_layout.addWidget(QLabel("작성 날짜 시작:"))
        write_date_filter_layout.addWidget(self.start_date_edit)
        write_date_filter_layout.addWidget(QLabel("작성 날짜 종료:"))
        write_date_filter_layout.addWidget(self.end_date_edit)
        write_date_filter_layout.addWidget(filter_button)
        layout.addLayout(write_date_filter_layout)

        # 청크 크기 설정
        chunk_layout = QHBoxLayout()
        self.chunk_size_input = QLineEdit()
        self.chunk_size_input.setPlaceholderText("청크 개수 (기본: 1)")
        chunk_layout.addWidget(QLabel("청크 개수:"))
        chunk_layout.addWidget(self.chunk_size_input)
        layout.addLayout(chunk_layout)

        # 리뷰 및 답글 개수 표시
        self.stats_label = QLabel("리뷰 개수: 0, 답글 개수: 0")
        layout.addWidget(self.stats_label)

        # 데이터 테이블
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["업체명", "작성날짜", "방문날짜", "아이디", "리뷰내용", "답글 내용"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # 엑셀 내보내기 버튼
        export_button = QPushButton("엑셀로 내보내기 (청크)")
        export_button.clicked.connect(self.export_to_excel_in_chunks)
        layout.addWidget(export_button)

        # 로그 표시
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        self.setLayout(layout)
        self.refresh_date_list()

    def refresh_date_list(self):
        """날짜 기반 하위 디렉터리를 드롭다운에 새로고침합니다."""
        self.crawling_date_combo.clear()
        if not os.path.exists(self.output_dir):
            QMessageBox.warning(self, "경고", f"경로가 존재하지 않습니다: {self.output_dir}")
            return

        try:
            # output 디렉터리 내의 하위 디렉터리 중 날짜 형식인 것만 필터링
            date_dirs = [
                name for name in os.listdir(self.output_dir)
                if os.path.isdir(os.path.join(self.output_dir, name)) and re.match(r'\d{2}월\d{2}일', name)
            ]
            if not date_dirs:
                QMessageBox.information(self, "정보", "날짜 기반의 저장된 데이터가 없습니다.")
                return

            # 날짜를 오름차순으로 정렬
            self.crawling_date_combo.addItems(sorted(date_dirs, key=lambda x: datetime.strptime(x, "%m월%d일")))
        except Exception as e:
            QMessageBox.critical(self, "오류", f"날짜 목록을 새로고침하는 중 오류 발생: {e}")

    def load_selected_date(self):
        """선택한 크롤링 시작 날짜의 데이터를 로드합니다."""
        selected_crawling_date = self.crawling_date_combo.currentText()
        if not selected_crawling_date:
            return

        dated_output_dir = os.path.join(self.output_dir, selected_crawling_date)
        if not os.path.exists(dated_output_dir):
            QMessageBox.warning(self, "경고", f"선택한 날짜의 디렉터리가 존재하지 않습니다: {dated_output_dir}")
            return

        try:
            # 모든 JSONLines 파일을 로드
            json_files = [
                os.path.join(dated_output_dir, f)
                for f in os.listdir(dated_output_dir)
                if f.endswith(".jsonlines")
            ]

            if not json_files:
                QMessageBox.warning(self, "경고", "선택한 날짜의 JSONLines 파일이 없습니다.")
                return

            self.filtered_data = []
            for file_path in json_files:
                with open(file_path, 'r', encoding='utf-8') as file:
                    for line in file:
                        try:
                            item = json.loads(line.strip())
                            review = item.get("review", {})
                            self.filtered_data.append({
                                "business_id": item.get("business_id", ""),
                                "업체명": review.get("businessName", "Unknown"),
                                "작성날짜": self.parse_created_date(review.get("created", "")),
                                "방문날짜": review.get("visited", ""),
                                "아이디": review.get("author", {}).get("nickname", ""),
                                "리뷰내용": review.get("body", ""),
                                "답글 내용": review.get("reply", {}).get("body", "")
                            })
                        except json.JSONDecodeError:
                            continue

            review_count = len(self.filtered_data)
            reply_count = sum(1 for item in self.filtered_data if item.get("답글 내용"))

            self.stats_label.setText(f"리뷰 개수: {review_count}, 답글 개수: {reply_count}")
            self.current_filtered_data = self.filtered_data.copy()  # 초기 필터링된 데이터를 현재 필터링 데이터로 설정
            self.update_table()
            self.log_message(f"{selected_crawling_date}의 데이터를 로드했습니다. 리뷰 개수: {review_count}, 답글 개수: {reply_count}")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"데이터를 로드하는 중 오류 발생: {e}")

    def parse_created_date(self, date_str):
        """created 필드의 날짜 문자열을 파싱하여 'yyyy-MM-dd' 형식으로 반환합니다."""
        try:
            # 예시 날짜 형식: "24.11.17.일" -> "2024-11-17"
            date_part = date_str.split('.')[0:3]  # ["24", "11", "17"]
            if len(date_part) < 3:
                return ""
            year = int(date_part[0]) + 2000 if int(date_part[0]) < 100 else int(date_part[0])
            month = int(date_part[1])
            day = int(date_part[2])
            return f"{year:04d}-{month:02d}-{day:02d}"
        except (ValueError, IndexError):
            return ""

    def update_table(self):
        """테이블 데이터를 업데이트합니다."""
        self.table.setRowCount(0)
        for review in self.current_filtered_data:
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)
            self.table.setItem(row_position, 0, QTableWidgetItem(review.get("업체명", "")))
            self.table.setItem(row_position, 1, QTableWidgetItem(review.get("작성날짜", "")))
            self.table.setItem(row_position, 2, QTableWidgetItem(review.get("방문날짜", "")))
            self.table.setItem(row_position, 3, QTableWidgetItem(review.get("아이디", "")))
            self.table.setItem(row_position, 4, QTableWidgetItem(review.get("리뷰내용", "")))
            self.table.setItem(row_position, 5, QTableWidgetItem(review.get("답글 내용", "")))

    def filter_by_write_date(self):
        """작성 날짜로 특정 기간 내의 리뷰를 필터링합니다."""
        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()

        if start_date > end_date:
            QMessageBox.warning(self, "경고", "시작 날짜는 종료 날짜보다 이전이어야 합니다.")
            return

        try:
            # 작성 날짜가 선택한 기간 내에 있는 리뷰만 필터링
            filtered_reviews = [
                review for review in self.filtered_data
                if self.is_date_in_range(review.get("작성날짜", ""), start_date, end_date)
            ]

            if not filtered_reviews:
                QMessageBox.information(self, "정보", f"{start_date}부터 {end_date}까지 작성된 리뷰가 없습니다.")
                return

            review_count = len(filtered_reviews)
            reply_count = sum(1 for item in filtered_reviews if item.get("답글 내용"))

            self.stats_label.setText(f"리뷰 개수: {review_count}, 답글 개수: {reply_count}")
            self.current_filtered_data = filtered_reviews  # 현재 필터링 데이터를 업데이트
            self.update_table()
            self.log_message(
                f"{start_date}부터 {end_date}까지 작성된 리뷰로 필터링했습니다. 리뷰 개수: {review_count}, 답글 개수: {reply_count}")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"작성 날짜로 필터링하는 중 오류 발생: {e}")

    def is_date_in_range(self, date_str, start_date, end_date):
        """날짜 문자열이 특정 기간 내에 있는지 확인합니다."""
        try:
            review_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            return start_date <= review_date <= end_date
        except ValueError:
            return False

    def update_table_with_filtered_data(self, data):
        """필터링된 데이터를 기반으로 테이블을 업데이트합니다."""
        self.table.setRowCount(0)
        for review in data:
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)
            self.table.setItem(row_position, 0, QTableWidgetItem(review.get("업체명", "")))
            self.table.setItem(row_position, 1, QTableWidgetItem(review.get("작성날짜", "")))
            self.table.setItem(row_position, 2, QTableWidgetItem(review.get("방문날짜", "")))
            self.table.setItem(row_position, 3, QTableWidgetItem(review.get("아이디", "")))
            self.table.setItem(row_position, 4, QTableWidgetItem(review.get("리뷰내용", "")))
            self.table.setItem(row_position, 5, QTableWidgetItem(review.get("답글 내용", "")))

    def export_to_excel_in_chunks(self):
        """필터링된 업체 데이터를 청크 개수대로 나눠 엑셀 파일로 저장합니다."""
        if not self.current_filtered_data:
            QMessageBox.warning(self, "경고", "필터링된 데이터가 없습니다. 먼저 데이터를 로드하세요.")
            return

        try:
            # 청크 개수 설정 (생성할 엑셀 파일의 개수)
            chunk_size_input = self.chunk_size_input.text().strip()
            if chunk_size_input.isdigit():
                chunk_size = int(chunk_size_input)
                if chunk_size <= 0:
                    raise ValueError("청크 개수는 양의 정수여야 합니다.")
            else:
                chunk_size = 1  # 기본 청크 개수

            # 고유 업체 ID 추출
            business_ids = sorted(
                list(set([review["business_id"] for review in self.current_filtered_data if review.get("business_id")]))
            )
            total_businesses = len(business_ids)

            if chunk_size > total_businesses:
                QMessageBox.warning(self, "경고", f"청크 개수 {chunk_size}가 총 업체 수 {total_businesses}보다 큽니다.")
                return

            # 청크 수 계산 (청크 개수 n으로 n개의 청크 생성)
            total_chunks = chunk_size

            # 각 청크에 포함될 업체 수 계산
            base = total_businesses // total_chunks
            remainder = total_businesses % total_chunks

            chunks = []
            start = 0
            for i in range(total_chunks):
                end = start + base + (1 if i < remainder else 0)
                chunk_business_ids = business_ids[start:end]
                chunks.append(chunk_business_ids)
                start = end

            # 엑셀 파일로 저장
            for idx, chunk_business_ids in enumerate(chunks, start=1):
                chunk_data = [review for review in self.current_filtered_data if
                              review["business_id"] in chunk_business_ids]

                if not chunk_data:
                    continue  # 빈 청크는 건너뜁니다.

                # 첫 업체 ID와 포함된 업체 수를 기반으로 파일 이름 생성
                first_business_id = chunk_business_ids[0]
                included_business_count = len(chunk_business_ids) - 1  # "외 n개"에서 n은 첫 업체 제외

                if included_business_count > 0:
                    file_name = f"{first_business_id}외{included_business_count}개_{idx}.xlsx"
                else:
                    file_name = f"{first_business_id}.xlsx"

                # 파일 저장 경로
                save_path, _ = QFileDialog.getSaveFileName(
                    self, "엑셀 파일 저장", os.path.join(self.output_dir, file_name),
                    "Excel Files (*.xlsx *.xls)", options=QFileDialog.Options()
                )
                if not save_path:
                    continue  # 사용자가 저장을 취소한 경우 건너뜁니다.

                # 데이터 정제
                sanitized_data = []
                for review in chunk_data:
                    sanitized_review = {
                        key: sanitize_text(value) if isinstance(value, str) else value
                        for key, value in review.items()
                    }
                    sanitized_data.append(sanitized_review)

                # 데이터프레임 생성
                df = pd.DataFrame(sanitized_data)

                # 엑셀 파일로 저장 (요약 정보 없이 데이터만 저장)
                df.to_excel(save_path, index=False, engine="openpyxl")

                self.log_message(f"저장됨: {save_path}")

                # 저장된 엑셀 파일 자동으로 열기 (Windows 기준)
                try:
                    os.startfile(save_path)
                except AttributeError:
                    # macOS 또는 Linux의 경우
                    import subprocess
                    if sys.platform == "darwin":
                        subprocess.call(["open", save_path])
                    else:
                        subprocess.call(["xdg-open", save_path])
                except Exception as e:
                    self.log_message(f"파일을 여는 중 오류 발생: {e}")

            QMessageBox.information(self, "성공", f"엑셀 파일로 저장이 완료되었습니다. 총 {total_chunks}개 파일이 생성되었습니다.")
        except ValueError as ve:
            QMessageBox.warning(self, "경고", f"입력 오류: {ve}")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"엑셀 저장 중 오류 발생: {e}")

    def log_message(self, message):
        """로그 메시지를 표시합니다."""
        self.log_text.append(message)


def sanitize_text(text):
    """
        텍스트에서 제어 문자를 제거하고 이모지를 대체하거나 제거합니다.
        """
    if not isinstance(text, str):
        return text

    # 제어 문자 제거 (널 문자 등)
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)

    # 이모지 제거 (필요에 따라 대체할 수도 있습니다)
    # 아래 정규 표현식은 대부분의 이모지를 제거합니다.
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Symbols & Pictographs
        "\U0001F680-\U0001F6FF"  # Transport & Map Symbols
        "\U0001F1E0-\U0001F1FF"  # Flags
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub(r'', text)

    return text
