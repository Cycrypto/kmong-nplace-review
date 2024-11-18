import sys
from PyQt5.QtWidgets import QApplication
from nplace.ui.review_crawler import URLManagerUI

if __name__ == "__main__":
    app = QApplication(sys.argv)
    manager = URLManagerUI()  # URLManagerUI를 인스턴스화
    manager.show()  # 메인 UI 표시
    sys.exit(app.exec())
