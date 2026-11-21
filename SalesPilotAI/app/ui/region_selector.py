"""用户主动框选屏幕区域的透明对话框。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QDialog


class RegionSelectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._origin = QPoint()
        self._current = QPoint()
        self._selecting = False
        self.setWindowTitle("框选 WhatsApp 聊天区域 · Esc 取消")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        screen = QApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.virtualGeometry())
        self.setModal(True)

    def selected_bounds(self) -> tuple[int, int, int, int] | None:
        rectangle = QRect(self._origin, self._current).normalized()
        if rectangle.width() < 5 or rectangle.height() < 5:
            return None
        top_left = self.mapToGlobal(rectangle.topLeft())
        bottom_right = self.mapToGlobal(rectangle.bottomRight())
        return (top_left.x(), top_left.y(), bottom_right.x() + 1, bottom_right.y() + 1)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._origin = event.position().toPoint()
            self._current = self._origin
            self._selecting = True
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._selecting:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._selecting:
            self._current = event.position().toPoint()
            self._selecting = False
            if self.selected_bounds() is not None:
                self.accept()
            else:
                self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(7, 15, 28, 150))
        rectangle = QRect(self._origin, self._current).normalized()
        if rectangle.width() > 1 and rectangle.height() > 1:
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rectangle, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(47, 111, 237), 2))
            painter.drawRect(rectangle)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(24, 36, "按住鼠标左键框选聊天区域，松开确认，Esc 取消")
