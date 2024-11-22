import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QFrame, QSplitter, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QPen, QDrag
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
        self.groups = []  # Track groups of connected labels

    def dragEnterEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        text = event.mimeData().text()
        color = event.mimeData().colorData()
        position = event.position().toPoint()

        source_widget = event.source()
        if isinstance(source_widget, DraggableLabel) and source_widget in self.dropped_labels:
            source_widget.move(position - self.pos())
        else:
            label = DraggableLabel(text, color, self)
            label.move(position - self.pos())
            label.show()
            self.dropped_labels.append(label)

        self.update_groups()

    def mouseReleaseEvent(self, event):
        for label in self.dropped_labels:
            self.snap_to_nearest(label)
        self.update_groups()  # Recalculate groups after snapping

    def snap_to_nearest(self, label):
        """
        Snap label to the nearest other label if within range.
        """
        snapping_range = 20  # Threshold for snapping
        for other in self.dropped_labels:
            if other is label:
                continue

            if abs(label.y() - (other.y() + other.height())) < snapping_range:
                label.move(label.x(), other.y() + other.height())
            elif abs((label.y() + label.height()) - other.y()) < snapping_range:
                label.move(label.x(), other.y() - label.height())
            elif abs(label.x() - (other.x() + other.width())) < snapping_range:
                label.move(other.x() + other.width(), label.y())
            elif abs((label.x() + label.width()) - other.x()) < snapping_range:
                label.move(other.x() - label.width(), label.y())

    def update_groups(self):
        """
        Update groups of connected labels and their visuals.
        """
        self.groups = []  # Reset groups

        for label in self.dropped_labels:
            # Find the group this label belongs to
            found_group = None
            for group in self.groups:
                if any(self.are_labels_connected(label, other) for other in group):
                    found_group = group
                    break

            if found_group:
                found_group.append(label)
            else:
                self.groups.append([label])

        self.update()  # Trigger a repaint to update visuals

    def are_labels_connected(self, label1, label2):
        """
        Check if two labels are close enough to be considered connected.
        """
        snapping_range = 20
        return (
            abs(label1.x() - label2.x()) < snapping_range and
            abs(label1.y() - label2.y()) < snapping_range
        )

    def paintEvent(self, event):
        """
        Override paintEvent to draw unified borders around groups of labels.
        """
        super().paintEvent(event)

        painter = QPainter(self)
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)
        painter.setPen(pen)

        for group in self.groups:
            if len(group) > 1:
                # Calculate bounding box for the group
                x_min = min(label.x() for label in group)
                y_min = min(label.y() for label in group)
                x_max = max(label.x() + label.width() for label in group)
                y_max = max(label.y() + label.height() for label in group)

                # Draw the unified border
                painter.drawRect(x_min, y_min, x_max - x_min, y_max - y_min)


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
