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
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemSendsScenePositionChanges
        )
        self.next_block = None
        self.prev_block = None
        self.child_blocks = []
        self.parent_block = None
        self.is_dragging = False
        self.highlighted_block = None
        self.dragging_from_top = False  # New attribute to track where the block is grabbed

    def initUI(self):
        path = QPainterPath()
        width = 120
        height = 40
        notch_size = 10
        tab_width = 20
        tab_height = 10

        # Create the block shape with a top notch and bottom tab
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

        # Add text
        self.text_item = QGraphicsTextItem(self.text, self)
        font = QFont('Arial', 12)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos((width - text_rect.width()) / 2, (height - text_rect.height()) / 2)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.is_dragging = True
        # Determine where the user clicked (top or bottom half)
        click_position = event.pos().y()
        block_height = self.boundingRect().height()
        self.dragging_from_top = click_position < (block_height / 2)

        # Disconnect from previous and next blocks if any
        if self.prev_block:
            self.prev_block.next_block = None
            self.prev_block = None
        if self.next_block:
            self.disconnect_next_blocks()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.check_for_snap()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.is_dragging = False
        self.snap_to_block()

    def disconnect_next_blocks(self):
        # Recursively disconnect next blocks
        if self.next_block:
            self.next_block.disconnect_next_blocks()
            self.next_block.prev_block = None
            self.next_block = None

    def check_for_snap(self):
        # Highlight potential snap targets
        colliding_items = self.scene().collidingItems(self)
        for item in colliding_items:
            if isinstance(item, Block) and item != self:
                if self.dragging_from_top:
                    # User is dragging from top, so we check if we are near the bottom of another block
                    if self.is_near(item, above=True):
                        item.setPen(QPen(QColor('green'), 2))
                        self.highlighted_block = item
                        return
                else:
                    # User is dragging from bottom, so we check if we are near the top of another block
                    if self.is_near(item, below=True):
                        item.setPen(QPen(QColor('blue'), 2))
                        self.highlighted_block = item
                        return
            if isinstance(item, ControlBlock) and item != self:
                if item.is_open_area(self.scenePos()):
                    item.setPen(QPen(QColor('purple'), 2))
                    self.highlighted_block = item
                    return
        # No suitable block found
        if self.highlighted_block:
            self.highlighted_block.setPen(QPen(Qt.black))
            self.highlighted_block = None

    def is_near(self, other_block, above=False, below=False):
        threshold = 20
        if above:
            # Check if the bottom of self is near the top of other_block
            self_bottom = self.sceneBoundingRect().bottom()
            other_top = other_block.sceneBoundingRect().top()
            if abs(self_bottom - other_top) < threshold and abs(self.scenePos().x() - other_block.scenePos().x()) < threshold:
                return True
        if below:
            # Check if the top of self is near the bottom of other_block
            self_top = self.sceneBoundingRect().top()
            other_bottom = other_block.sceneBoundingRect().bottom()
            if abs(self_top - other_bottom) < threshold and abs(self.scenePos().x() - other_block.scenePos().x()) < threshold:
                return True
        return False

    def snap_to_block(self):
        if self.highlighted_block:
            if isinstance(self.highlighted_block, ControlBlock):
                # Snap into the control block
                self.parent_block = self.highlighted_block
                self.highlighted_block.child_blocks.append(self)
                self.setPos(self.highlighted_block.scenePos().x() + 20, self.highlighted_block.scenePos().y() + 40)
            else:
                if self.dragging_from_top and self.is_near(self.highlighted_block, above=True):
                    # Snap the bottom of self to the top of the highlighted block
                    self.next_block = self.highlighted_block
                    self.highlighted_block.prev_block = self
                    new_x = self.highlighted_block.scenePos().x()
                    new_y = self.highlighted_block.scenePos().y() - self.boundingRect().height() + 2
                    self.setPos(new_x, new_y)
                elif not self.dragging_from_top and self.is_near(self.highlighted_block, below=True):
                    # Snap the top of self to the bottom of the highlighted block
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
        height = 80
        notch_size = 10
        tab_width = 20
        tab_height = 10
        open_area_height = 40

        # Create a control block shape with an open area for child blocks
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

        # Add text
        self.text_item.setPlainText(self.text)
        font = QFont('Arial', 12)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos((width - text_rect.width()) / 2, 10)

    def is_open_area(self, pos):
        # Define the open area where child blocks can be placed
        local_pos = self.mapFromScene(pos)
        open_rect = QRectF(10, 30, self.boundingRect().width() - 20, 40)
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

        # Block Palette
        self.palette = BlockPalette(self)

        # Workspace
        self.workspace = Workspace(self)

        # Run Button
        self.run_button = QPushButton('Run')
        self.run_button.setStyleSheet('font-size: 16px; height: 40px;')
        self.run_button.clicked.connect(self.run_program)

        # Arrange layouts
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel('<h2>Blocks</h2>'))
        left_layout.addWidget(self.palette)
        left_layout.addStretch()
        left_layout.addWidget(self.run_button)

        main_layout.addLayout(left_layout)
        main_layout.addWidget(self.workspace)

    def run_program(self):
        # Find all top-level blocks
        blocks = [item for item in self.workspace.scene().items() if isinstance(item, Block) and item.prev_block is None and not item.parent_block]
        program = []
        for block in blocks:
            code = block.generate_code()
            program.append(code)
        rudiron_code = '\n'.join(program)
        # Display or execute the code
        QMessageBox.information(self, "Program", f"Program to execute on Rudiron:\n{rudiron_code}")
        # Here you can add code to send 'rudiron_code' to the Rudiron controller

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
