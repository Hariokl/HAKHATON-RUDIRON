import sys
import logging
from PyQt6.QtWidgets import (
    QApplication, QWidget, QGraphicsView, QGraphicsScene, QGraphicsPathItem,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QLineEdit, QComboBox,
    QGraphicsProxyWidget, QGraphicsItem
)
from PyQt6.QtGui import QBrush, QColor, QPen, QPainterPath, QFont, QPainter, QIcon
from PyQt6.QtCore import Qt, QPointF

logging.basicConfig(level=logging.DEBUG)

class Block(QGraphicsPathItem):
    def __init__(self, text, color, parent=None):
        super().__init__(parent)
        self.text = text
        self.color = color
        self.width = 140
        self.height = 60
        self.text_field_proxy = None
        self.combo_box_proxy = None
        self.initUI()
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        )
        self.next_block = None
        self.prev_block = None
        self.parent_block = None
        self.highlighted_block = None
        self.setZValue(1)

        logging.debug(f"Block created: {self.text}")

    def initUI(self):
        # Define block shape
        path = QPainterPath()
        notch_size = 10
        tab_width = 20
        tab_height = 10

        path.moveTo(0, notch_size)
        path.lineTo(tab_width, notch_size)
        path.lineTo(tab_width + notch_size, 0)
        path.lineTo(self.width - (tab_width + notch_size), 0)
        path.lineTo(self.width - tab_width, notch_size)
        path.lineTo(self.width, notch_size)
        path.lineTo(self.width, self.height - tab_height)
        path.lineTo(self.width - tab_width, self.height - tab_height)
        path.lineTo(self.width - (tab_width + notch_size), self.height)
        path.lineTo(tab_width + notch_size, self.height)
        path.lineTo(tab_width, self.height - tab_height)
        path.lineTo(0, self.height - tab_height)
        path.closeSubpath()

        self.setPath(path)
        self.setBrush(QBrush(self.color))
        self.setPen(QPen(Qt.GlobalColor.black))


        # Add changeable text field (QLineEdit)
        self.text_field = QLineEdit()
        self.text_field.setText(self.text)
        self.text_field.setFont(QFont('Arial', 10))
        self.text_field.setFixedWidth(100)

        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field)
        self.text_field_proxy.setParentItem(self)
        self.text_field_proxy.setPos(10, 10)


        # Add combo box
        self.combo_box = QComboBox()
        self.combo_box.addItems(['Option 1', 'Option 2', 'Option 3'])
        self.combo_box.setFont(QFont('Arial', 10))

        self.combo_box_proxy = QGraphicsProxyWidget(self)
        self.combo_box_proxy.setWidget(self.combo_box)
        self.combo_box_proxy.setParentItem(self)
        self.combo_box_proxy.setPos(10, 30)

    def delete_block(self):
        # Clean up proxy widgets
        if self.text_field_proxy:
            self.scene().removeItem(self.text_field_proxy)
            self.text_field_proxy.widget().deleteLater()
            self.text_field_proxy = None

        if self.combo_box_proxy:
            self.scene().removeItem(self.combo_box_proxy)
            self.combo_box_proxy.widget().deleteLater()
            self.combo_box_proxy = None

        self.scene().removeItem(self)

    def generate_code(self):
        """
        Generate the code representation of this block, including the current values
        from the QLineEdit and QComboBox.
        """
        text_value = self.text_field.text()
        combo_value = self.combo_box.currentText()
        command_mapping = {
            'Move Forward': f"move_forward('{text_value}', '{combo_value}')",
            'Turn Left': f"turn_left('{text_value}', '{combo_value}')",
            'Turn Right': f"turn_right('{text_value}', '{combo_value}')",
            'Play Sound': f"play_sound('{text_value}', '{combo_value}')"
        }
        command = command_mapping.get(self.text, '')
        code_lines = [command]
        if self.next_block:
            code_lines.append(self.next_block.generate_code())
        return '\n'.join(code_lines)

    def __del__(self):
        logging.debug(f"Block deleted: {self.text}")

class ControlBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.child_blocks = []
        self.height = 80  # Start with a larger height for ControlBlock
        self.update_shape()

    def update_shape(self):
        path = QPainterPath()
        path.addRect(0, 0, self.width, self.height)
        self.setPath(path)

    def add_child(self, block):
        if block not in self.child_blocks:
            self.child_blocks.append(block)
            block.setParentItem(self)
            self.update_size()

    def remove_child(self, block):
        if block in self.child_blocks:
            self.child_blocks.remove(block)
            block.setParentItem(None)
            self.update_size()

    def update_size(self):
        total_height = 80  # Base height
        for child in self.child_blocks:
            total_height += child.boundingRect().height()
        self.height = total_height
        self.update_shape()

    def generate_code(self):
        code_lines = [f"for _ in range(10):  # {self.text}"]
        for child in self.child_blocks:
            child_code = child.generate_code()
            code_lines.append(f"    {child_code}")
        return '\n'.join(code_lines)

class Workspace(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(0, 0, 800, 600)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected_items = self.scene().selectedItems()
            for item in selected_items:
                if isinstance(item, Block):
                    item.delete_block()
            event.accept()
        else:
            super().keyPressEvent(event)

class BlockPalette(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.parent = parent
        blocks = ['Move Forward', 'Turn Left', 'Turn Right', 'Play Sound', 'Repeat']
        colors = [
            QColor('#FF5733'),
            QColor('#33FF57'),
            QColor('#3357FF'),
            QColor('#F1C40F'),
            QColor('#9B59B6')
        ]

        for text, color in zip(blocks, colors):
            button = QPushButton(text)
            button.setStyleSheet(
                f'background-color: {color.name()}; color: white; font-weight: bold;')
            button.clicked.connect(
                lambda checked, t=text, c=color: self.add_block_to_workspace(t, c))
            layout.addWidget(button)

    def add_block_to_workspace(self, text, color):
        if text == 'Repeat':
            block = ControlBlock(text, color)
        else:
            block = Block(text, color)
        self.parent.workspace.scene().addItem(block)
        block.setPos(100, 100)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Visual Programming with PyQt')
        self.setGeometry(100, 100, 1000, 600)
        self.setupUI()

    def setupUI(self):
        main_layout = QHBoxLayout(self)

        self.palette = BlockPalette(self)

        self.workspace = Workspace(self)

        self.run_button = QPushButton('Run')
        self.run_button.setStyleSheet('font-size: 16px; height: 40px;')
        self.run_button.clicked.connect(self.run_program)

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel('<h2>Blocks</h2>'))
        left_layout.addWidget(self.palette)
        left_layout.addStretch()
        left_layout.addWidget(self.run_button)

        main_layout.addLayout(left_layout)
        main_layout.addWidget(self.workspace)

    def run_program(self):
        blocks = [item for item in self.workspace.scene().items()
                  if isinstance(item, Block) and item.prev_block is None and not item.parent_block]
        blocks.sort(key=lambda block: block.scenePos().y())
        program = []
        for block in blocks:
            code = block.generate_code()
            program.append(code)
        rudiron_code = '\n'.join(program)
        QMessageBox.information(
            self, "Program", f"Program to execute:\n{rudiron_code}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
