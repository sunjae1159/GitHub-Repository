import sys
import os
import socket
import threading
import urllib.parse
import io
import qrcode
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QDialog, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap


class DownloadHandler(SimpleHTTPRequestHandler):
    """브라우저가 파일을 열지 않고 즉시 '다운로드'하게 만드는 핸들러"""
    def end_headers(self):
        file_path = self.translate_path(self.path)
        if os.path.isfile(file_path):
            filename = os.path.basename(file_path)
            encoded_filename = urllib.parse.quote(filename)
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_filename}")
        super().end_headers()


class ServerThread(threading.Thread):
    def __init__(self, file_path, port=8000):
        super().__init__()
        self.file_path = file_path
        self.port = port
        self.server = None
        self.daemon = True

    def run(self):
        file_dir = os.path.dirname(self.file_path)
        handler = partial(DownloadHandler, directory=file_dir)
        try:
            self.server = HTTPServer(("0.0.0.0", self.port), handler)
            self.server.serve_forever()
        except Exception as e:
            print(f"서버 오류: {e}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()


class QRDialog(QDialog):
    def __init__(self, url, server_thread):
        super().__init__()
        self.server_thread = server_thread
        self.initUI(url)

    def initUI(self, url):
        self.setWindowTitle("QR Dropzone - 즉시 다운로드")
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout()
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")
        
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue())

        qr_label = QLabel(self)
        qr_label.setPixmap(pixmap)
        qr_label.setAlignment(Qt.AlignCenter)

        info_label = QLabel("스캔 즉시 파일 다운로드가 시작됩니다!\n(PC와 스마트폰 동일 Wi-Fi 필수)", self)
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #d32f2f; margin: 10px;")

        layout.addWidget(qr_label)
        layout.addWidget(info_label)
        self.setLayout(layout)
        self.adjustSize()

    def closeEvent(self, event):
        self.server_thread.stop()
        event.accept()


class DropZone(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(200, 150) # 크기를 문구에 맞게 살짝 조정
        self.setAcceptDrops(True)

        layout = QVBoxLayout()
        # 요구하신 대로 문구를 "QR 즉시 생성!"으로 변경했습니다.
        self.label = QLabel("🚀\nQR 즉시 생성!", self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                background-color: rgba(30, 30, 35, 230);
                color: #61afef;
                font-size: 18px;
                font-weight: bold;
                border: 3px dashed #61afef;
                border-radius: 25px;
            }
        """)

        layout.addWidget(self.label)
        self.setLayout(layout)

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self.label.setStyleSheet("""
                QLabel {
                    background-color: rgba(97, 175, 239, 240);
                    color: white;
                    font-size: 18px;
                    font-weight: bold;
                    border: 3px solid white;
                    border-radius: 25px;
                }
            """)
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.label.setStyleSheet("""
            QLabel {
                background-color: rgba(30, 30, 35, 230);
                color: #61afef;
                font-size: 18px;
                font-weight: bold;
                border: 3px dashed #61afef;
                border-radius: 25px;
            }
        """)

    def dropEvent(self, event):
        self.dragLeaveEvent(event)
        urls = event.mimeData().urls()
        if not urls: return

        file_path = urls[0].toLocalFile()
        if not os.path.isfile(file_path):
            QMessageBox.warning(self, "오류", "파일만 드롭해주세요.")
            return

        filename = os.path.basename(file_path)
        local_ip = self.get_local_ip()
        port = 8000
        
        encoded_filename = urllib.parse.quote(filename)
        download_url = f"http://{local_ip}:{port}/{encoded_filename}"
        
        server_thread = ServerThread(file_path, port)
        server_thread.start()

        self.qr_dialog = QRDialog(download_url, server_thread)
        self.qr_dialog.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragPos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.dragPos)
            event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    dropzone = DropZone()
    dropzone.show()
    sys.exit(app.exec_())