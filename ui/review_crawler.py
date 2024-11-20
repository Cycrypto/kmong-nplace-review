import shutil
import sys
import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLineEdit, QFileDialog,
    QMessageBox, QHeaderView, QProgressBar, QTextEdit, QApplication, QTimeEdit, QLabel
)
from PyQt5.QtCore import QTime, QTimer
import os
from datetime import datetime, timedelta

from nplace.crawler.worker import CrawlWorker
from nplace.utils.nme2_origin import NaverMeConvertor
from nplace.ui.review_filter_dialog import ReviewFilterDialog


class URLManagerUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("URL 리스트 관리")
        self.query_file = "data/get_place_visitor_review_query.graphql"  # 쿼리 파일 경로
        self.output_dir = "output"  # 출력 디렉터리
        self.init_ui()
        self.worker = None  # 스레드 작업자를 저장
        self.is_crawling = False  # 크롤링 상태 플래그
        self.timer = QTimer(self)  # 스케줄링용 타이머
        self.timer.timeout.connect(self.start_crawling)  # 타이머 시간 도달 시 크롤링 시작

    def init_ui(self):
        layout = QVBoxLayout()
        export_button = QPushButton("결과 확인 및 내보내기")
        export_button.clicked.connect(self.open_dialog)
        layout.addWidget(export_button)

        # URL 테이블 설정
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['URL', 'Business ID'])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        # URL 입력창
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("엑셀 파일 경로를 입력하거나 파일을 불러오세요")
        layout.addWidget(self.entry)

        # 버튼 레이아웃
        button_layout = QHBoxLayout()

        load_button = QPushButton('엑셀 불러오기')
        load_button.clicked.connect(self.load_excel)
        button_layout.addWidget(load_button)

        self.crawl_button = QPushButton('크롤링 시작')
        self.crawl_button.clicked.connect(self.start_crawling)
        button_layout.addWidget(self.crawl_button)

        self.stop_button = QPushButton('중단')
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_crawling)
        button_layout.addWidget(self.stop_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 스케줄링 UI
        schedule_layout = QHBoxLayout()

        self.schedule_time_edit = QTimeEdit()
        self.schedule_time_edit.setDisplayFormat("HH:mm:ss")
        self.schedule_time_edit.setTime(QTime.currentTime())
        schedule_layout.addWidget(QLabel("스케줄링 시간 설정:"))
        schedule_layout.addWidget(self.schedule_time_edit)

        self.schedule_button = QPushButton('스케줄링 시작')
        self.schedule_button.clicked.connect(self.start_scheduling)
        schedule_layout.addWidget(self.schedule_button)

        self.cancel_schedule_button = QPushButton('스케줄링 취소')
        self.cancel_schedule_button.setEnabled(False)
        self.cancel_schedule_button.clicked.connect(self.cancel_scheduling)
        schedule_layout.addWidget(self.cancel_schedule_button)

        self.schedule_status_label = QLabel("스케줄링 상태: 없음")
        layout.addWidget(self.schedule_status_label)

        # 로그 표시
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        layout.addLayout(button_layout)
        layout.addLayout(schedule_layout)
        self.setLayout(layout)

    def open_dialog(self):
        """내보내기 다이얼로그를 엽니다."""
        dialog = ReviewFilterDialog(self.output_dir)
        dialog.exec()

    def load_excel(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "엑셀 파일 불러오기", "", "Excel Files (*.xlsx *.xls)", options=options
        )
        if file_path:
            self.entry.setText(file_path)
            try:
                df = pd.read_excel(file_path)
                if 'URL' not in df.columns:
                    raise ValueError("엑셀 파일에 'URL' 열이 없습니다.")

                urls = df['URL'].tolist()
                convertor = NaverMeConvertor(urls)
                origins = convertor.to_origin()
                meta_infos = convertor.get_meta_infos(origins)

                self.table.setRowCount(0)
                for meta in meta_infos:
                    # 튜플에서 business_id (1번 값)만 추출
                    category, business_id = meta
                    row_position = self.table.rowCount()
                    self.table.insertRow(row_position)
                    self.table.setItem(row_position, 0, QTableWidgetItem(urls[meta_infos.index(meta)]))  # 원래 URL
                    self.table.setItem(row_position, 1, QTableWidgetItem(business_id or "N/A"))  # business_id
                    self.log_message(f"Converted: {urls[meta_infos.index(meta)]} -> {business_id}")

            except Exception as e:
                QMessageBox.critical(self, "오류", f"엑셀 파일을 불러오는 중 오류 발생: {e}")

    def log_message(self, message):
        self.log_text.append(message)

    def start_crawling(self):
        """크롤링을 시작합니다. 중복 실행 방지."""
        if self.is_crawling:
            self.log_message("이미 크롤링이 진행 중입니다.")
            QMessageBox.warning(self, "경고", "이미 크롤링이 진행 중입니다.")
            return

        if not os.path.exists(self.query_file):
            QMessageBox.critical(self, "오류", f"쿼리 파일이 없습니다: {self.query_file}")
            return

        business_ids = [
            self.table.item(row, 1).text()
            for row in range(self.table.rowCount())
        ]
        business_ids = [bid for bid in business_ids if bid != "N/A" and bid.strip() != ""]

        if not business_ids:
            QMessageBox.warning(self, '경고', '크롤링할 Business ID가 없습니다.')
            return

        # 현재 날짜 기반 디렉터리 생성
        current_date = datetime.now().strftime("%m월%d일")
        dated_output_dir = os.path.join(self.output_dir, current_date)
        os.makedirs(dated_output_dir, exist_ok=True)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.crawl_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.is_crawling = True  # 크롤링 상태 플래그 설정

        self.worker = CrawlWorker(business_ids, self.query_file, dated_output_dir)
        self.worker.log_signal.connect(self.log_message)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.crawling_finished)

        self.worker.start()
        self.log_message("크롤링을 시작합니다.")

    def stop_crawling(self):
        """크롤링을 중단합니다."""
        if self.worker and self.is_crawling:
            self.worker.stop()
            self.worker.wait()
            self.crawling_finished()
            self.log_message("크롤링을 중단했습니다.")

    def crawling_finished(self):
        """크롤링 작업이 완료되면 호출됩니다."""
        self.progress_bar.setVisible(False)
        self.crawl_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.is_crawling = False  # 크롤링 상태 플래그 해제
        QMessageBox.information(self, '크롤링 완료', '크롤링이 완료되었습니다.')
        self.log_message("크롤링이 완료되었습니다.")

        # 스케줄링을 반복적으로 설정
        if self.timer.isActive():
            # 다음 날 같은 시간에 크롤링을 예약
            self.schedule_next_run()

    def schedule_next_run(self):
        """다음 날 같은 시간에 크롤링을 예약합니다."""
        scheduled_time = self.schedule_time_edit.time()
        current_datetime = datetime.now()
        scheduled_datetime = current_datetime.replace(
            hour=scheduled_time.hour(),
            minute=scheduled_time.minute(),
            second=scheduled_time.second(),
            microsecond=0
        )

        # 만약 설정 시간이 이미 지났다면 다음 날로 설정
        if scheduled_datetime <= current_datetime:
            scheduled_datetime += timedelta(days=1)

        interval = (scheduled_datetime - current_datetime).total_seconds() * 1000  # 밀리초 단위

        self.timer.setSingleShot(True)  # 단일 실행 설정
        self.timer.start(int(interval))
        self.schedule_status_label.setText(f"스케줄링 상태: {scheduled_time.toString('HH:mm:ss')}에 크롤링 시작")
        self.schedule_button.setEnabled(False)
        self.cancel_schedule_button.setEnabled(True)
        self.log_message(f"다음 스케줄링 설정됨: {scheduled_datetime.strftime('%Y-%m-%d %H:%M:%S')}에 크롤링 시작")

    def start_scheduling(self):
        """스케줄링을 설정합니다."""
        scheduled_time = self.schedule_time_edit.time()
        current_time = QTime.currentTime()

        # 음수 간격 체크를 제거합니다.
        # interval = current_time.msecsTo(scheduled_time)
        # if interval <= 0:
        #     QMessageBox.warning(self, "경고", "스케줄링 시간은 현재 시간 이후로 설정해야 합니다.")
        #     return

        # 스케줄링 시간을 datetime 객체로 변환하고 필요시 다음 날로 조정합니다.
        scheduled_datetime = datetime.now().replace(
            hour=scheduled_time.hour(),
            minute=scheduled_time.minute(),
            second=scheduled_time.second(),
            microsecond=0
        )
        if scheduled_datetime <= datetime.now():
            scheduled_datetime += timedelta(days=1)

        interval = (scheduled_datetime - datetime.now()).total_seconds() * 1000  # 밀리초로 변환

        self.timer.setSingleShot(True)
        self.timer.start(int(interval))
        self.schedule_status_label.setText(f"스케줄링 상태: {scheduled_time.toString('HH:mm:ss')}에 크롤링 시작")
        self.schedule_button.setEnabled(False)
        self.cancel_schedule_button.setEnabled(True)
        self.log_message(f"스케줄링 설정됨: {scheduled_datetime.strftime('%Y-%m-%d %H:%M:%S')}에 크롤링 시작")

    def cancel_scheduling(self):
        """스케줄링을 취소합니다."""
        self.timer.stop()
        self.schedule_status_label.setText("스케줄링 상태: 없음")
        self.schedule_button.setEnabled(True)
        self.cancel_schedule_button.setEnabled(False)
        self.log_message("스케줄링이 취소되었습니다.")

    def closeEvent(self, event):
        """애플리케이션 종료 시 output 디렉터리를 삭제합니다."""
        if os.path.exists(self.output_dir):
            try:
                shutil.rmtree(self.output_dir)  # output 디렉터리 삭제
                self.log_message(f"디렉토리 삭제 완료: {self.output_dir}")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"디렉토리를 삭제하는 중 오류 발생: {e}")
        event.accept()  # 애플리케이션 종료
