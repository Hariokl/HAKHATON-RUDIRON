import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QSplitter, QLabel, QScrollArea, QPushButton
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QPainter, QDrag
from PyQt6.QtCore import QMimeData


class DraggableLabel(QLabel):
    def __init__(self, text, color, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"background-color: {color}; border: 1px solid black;")
        self.setFixedSize(100, 50)
        self.color = color
        self.text = text
        self.setMouseTracking(True)
        self.start_drag_position = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            print(event.pos())
            self.start_drag_position = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(self.text)
            mime_data.setColorData(self.color)
            drag.setMimeData(mime_data)
            drag.setHotSpot(event.pos())
            drag.exec()

    def mouseReleaseEvent(self, event):
        self.start_drag_position = None


class DropArea(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("background-color: white; border: 1px solid black;")
        self.setMinimumSize(400, 400)
        self.dropped_labels = []
        self.connections = {}

    def dragEnterEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        text = event.mimeData().text()
        color = event.mimeData().colorData()
        position = event.position().toPoint()

        source_widget = event.source()
        if isinstance(source_widget, DraggableLabel) and source_widget in self.dropped_labels:
            source_widget.move(position - self.pos())
            self.update_connections(source_widget)
        else:
            label = DraggableLabel(text, color, self)
            label.move(position - self.pos())
            label.show()
            self.dropped_labels.append(label)
            self.update_connections(label)

    def mouseReleaseEvent(self, event):
        for label in self.dropped_labels:
            self.snap_to_nearest(label)

    def snap_to_nearest(self, label):
        for other in self.dropped_labels:
            if other is label:
                continue

            if abs(label.y() - (other.y() + other.height())) < 10:
                label.move(label.x(), other.y() + other.height())
                self.update_connections(label, other)
            elif abs((label.y() + label.height()) - other.y()) < 10:
                label.move(label.x(), other.y() - label.height())
                self.update_connections(label, other)

    def update_connections(self, label, connected_label=None):
        if connected_label:
            self.connections[label] = connected_label
            print(f"{label.text} прикреплен к {connected_label.text}")
        else:
            self.connections.pop(label, None)

        print("Текущие связи:", {k.text: v.text for k, v in self.connections.items()})


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Конструктор")
        self.setGeometry(100, 100, 800, 600)
        self.showMaximized()

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        left_panel = self.create_left_panel()
        right_panel = DropArea()

        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)

        self.setCentralWidget(main_splitter)

    def create_left_panel(self):
        left_widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)

        modules = [
            ("Модуль 1", "red"),
            ("Модуль 2", "blue"),
            ("Модуль 3", "green"),
            ("Модуль 4", "yellow"),
            ("Модуль 5", "orange")
        ]

        for text, color in modules:
            label = DraggableLabel(text, color, self)
            layout.addWidget(label)

        layout.addStretch()

        toggle_button = QPushButton("Свернуть панель")
        toggle_button.clicked.connect(lambda: left_widget.hide())
        layout.addWidget(toggle_button)

        left_widget.setLayout(layout)
        return left_widget


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())