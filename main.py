import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QGraphicsView, QGraphicsScene, QGraphicsItem,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QGraphicsTextItem,
    QGraphicsPathItem, QGraphicsPixmapItem, QGraphicsRectItem
)
from PyQt5.QtGui import QBrush, QColor, QPen, QPainterPath, QIcon, QPainter, QPixmap, QFont
from PyQt5.QtCore import Qt, QRectF, QPointF, QSize

class Block(QGraphicsPathItem):
    def __init__(self, text, color, parent=None):
        super().__init__(parent)
        self.text = text
        self.color = color
        self.initUI()
        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemIsMovable
        )
        self.next_block = None
        self.prev_block = None
        self.child_blocks = []
        self.parent_block = None
        self.highlighted_block = None
        self.dragging_from_top = False
        self.initial_positions = {}

    def initUI(self):
        path = QPainterPath()
        width = 120
        height = 40
        notch_size = 10
        tab_width = 20
        tab_height = 10
        path.moveTo(0, notch_size)
        path.lineTo(tab_width, notch_size)
        path.lineTo(tab_width + notch_size, 0)
        path.lineTo(width - (tab_width + notch_size), 0)
        path.lineTo(width - tab_width, notch_size)
        path.lineTo(width, notch_size)
        path.lineTo(width, height - tab_height)
        path.lineTo(width - tab_width, height - tab_height)
        path.lineTo(width - (tab_width + notch_size), height)
        path.lineTo(tab_width + notch_size, height)
        path.lineTo(tab_width, height - tab_height)
        path.lineTo(0, height - tab_height)
        path.closeSubpath()
        self.setPath(path)
        self.setBrush(QBrush(self.color))
        self.setPen(QPen(Qt.black))
        self.text_item = QGraphicsTextItem(self.text, self)
        font = QFont('Arial', 12)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos((width - text_rect.width()) / 2, (height - text_rect.height()) / 2)

    def mousePressEvent(self, event):
        click_position = event.pos().y()
        block_height = self.boundingRect().height()
        self.dragging_from_top = click_position < (block_height / 2)
        self.initial_positions = {}
        for block in self.get_all_connected_blocks():
            self.initial_positions[block] = block.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        delta = self.pos() - self.initial_positions[self]
        for block in self.get_all_connected_blocks():
            if block != self:
                block.setPos(self.initial_positions[block] + delta)
        self.check_for_snap()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.snap_to_block()

    def mouseDoubleClickEvent(self, event):
        if self.prev_block:
            self.prev_block.next_block = None
            self.prev_block = None
        if self.next_block:
            self.next_block.prev_block = None
            self.next_block = None
        if self.parent_block:
            self.parent_block.child_blocks.remove(self)
            self.parent_block = None
        super().mouseDoubleClickEvent(event)

    def get_all_connected_blocks(self):
        connected = []
        block = self
        while block.prev_block:
            block = block.prev_block
        while block:
            connected.append(block)
            block = block.next_block
        return connected

    def check_for_snap(self):
        colliding_items = self.scene().collidingItems(self)
        for item in colliding_items:
            if isinstance(item, Block) and item != self and item not in self.get_all_connected_blocks():
                if self.dragging_from_top:
                    if self.is_near(item, above=True):
                        item.setPen(QPen(QColor('green'), 2))
                        self.highlighted_block = item
                        return
                else:
                    if self.is_near(item, below=True):
                        item.setPen(QPen(QColor('blue'), 2))
                        self.highlighted_block = item
                        return
            if isinstance(item, ControlBlock) and item != self:
                if item.is_open_area(self.scenePos()):
                    item.setPen(QPen(QColor('purple'), 2))
                    self.highlighted_block = item
                    return
        if self.highlighted_block:
            self.highlighted_block.setPen(QPen(Qt.black))
            self.highlighted_block = None

    def is_near(self, other_block, above=False, below=False):
        threshold = 40
        if above:
            self_bottom = self.sceneBoundingRect().bottom()
            other_top = other_block.sceneBoundingRect().top()
            if abs(self_bottom - other_top) < threshold and abs(self.scenePos().x() - other_block.scenePos().x()) < threshold:
                return True
        if below:
            self_top = self.sceneBoundingRect().top()
            other_bottom = other_block.sceneBoundingRect().bottom()
            if abs(self_top - other_bottom) < threshold and abs(self.scenePos().x() - other_block.scenePos().x()) < threshold:
                return True
        return False

    def snap_to_block(self):
        if self.highlighted_block:
            if isinstance(self.highlighted_block, ControlBlock):
                self.parent_block = self.highlighted_block
                self.highlighted_block.child_blocks.append(self)
                self.setPos(self.highlighted_block.scenePos().x() + 20, self.highlighted_block.scenePos().y() + 40)
            else:
                if self.dragging_from_top and self.is_near(self.highlighted_block, above=True):
                    self.next_block = self.highlighted_block
                    self.highlighted_block.prev_block = self
                    new_x = self.highlighted_block.scenePos().x()
                    new_y = self.highlighted_block.scenePos().y() - self.boundingRect().height() + 2
                    self.setPos(new_x, new_y)
                elif not self.dragging_from_top and self.is_near(self.highlighted_block, below=True):
                    self.prev_block = self.highlighted_block
                    self.highlighted_block.next_block = self
                    new_x = self.highlighted_block.scenePos().x()
                    new_y = self.highlighted_block.scenePos().y() + self.highlighted_block.boundingRect().height() - 2
                    self.setPos(new_x, new_y)
            self.highlighted_block.setPen(QPen(Qt.black))
            self.highlighted_block = None

    def generate_code(self):
        command_mapping = {
            'Move Forward': 'move_forward()',
            'Turn Left': 'turn_left()',
            'Turn Right': 'turn_right()',
            'Play Sound': 'play_sound()'
        }
        command = command_mapping.get(self.text, '')
        code_lines = [command]
        if self.next_block:
            code_lines.append(self.next_block.generate_code())
        return '\n'.join(code_lines)

class ControlBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.child_blocks = []
        self.is_expanded = False
        self.initControlUI()

    def initControlUI(self):
        path = QPainterPath()
        width = 140
        height = 100
        notch_size = 10
        tab_width = 20
        tab_height = 10
        path.moveTo(0, notch_size)
        path.lineTo(tab_width, notch_size)
        path.lineTo(tab_width + notch_size, 0)
        path.lineTo(width - (tab_width + notch_size), 0)
        path.lineTo(width - tab_width, notch_size)
        path.lineTo(width, notch_size)
        path.lineTo(width, height - notch_size)
        path.lineTo(width - tab_width, height - notch_size)
        path.lineTo(width - (tab_width + notch_size), height)
        path.lineTo(tab_width + notch_size, height)
        path.lineTo(tab_width, height - notch_size)
        path.lineTo(0, height - notch_size)
        path.closeSubpath()
        self.setPath(path)
        self.setBrush(QBrush(self.color))
        self.setPen(QPen(Qt.black))
        self.text_item.setPlainText(self.text)
        font = QFont('Arial', 12)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos((width - text_rect.width()) / 2, 10)

    def is_open_area(self, pos):
        local_pos = self.mapFromScene(pos)
        open_rect = QRectF(10, 30, self.boundingRect().width() - 20, self.boundingRect().height() - 60)
        return open_rect.contains(local_pos)

    def generate_code(self):
        code_lines = []
        if self.text == 'Repeat':
            code_lines.append('for i in range(10):')
            for child in self.child_blocks:
                child_code = child.generate_code()
                indented_code = '\n'.join(['    ' + line for line in child_code.split('\n')])
                code_lines.append(indented_code)
        if self.next_block:
            code_lines.append(self.next_block.generate_code())
        return '\n'.join(code_lines)

class Workspace(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(0, 0, 800, 600)
        self.setRenderHint(QPainter.Antialiasing)

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
            button.setStyleSheet(f'background-color: {color.name()}; color: white; font-weight: bold;')
            button.clicked.connect(lambda checked, t=text, c=color: self.add_block_to_workspace(t, c))
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
        self.setWindowTitle('Scratch-like Rudiron Programmer')
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
        blocks = [item for item in self.workspace.scene().items() if isinstance(item, Block) and item.prev_block is None and not item.parent_block]
        program = []
        for block in blocks:
            code = block.generate_code()
            program.append(code)
        rudiron_code = '\n'.join(program)
        QMessageBox.information(self, "Program", f"Program to execute on Rudiron:\n{rudiron_code}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
