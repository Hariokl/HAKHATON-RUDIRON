import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QGraphicsView, QGraphicsScene, QGraphicsItem,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QGraphicsTextItem,
    QGraphicsPathItem
)
from PyQt5.QtGui import QBrush, QColor, QPen, QPainterPath, QFont, QPainter
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5 import QtGui

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
        self.parent_block = None
        self.highlighted_block = None
        self.dragging_from_top = False  # To track where the block is grabbed
        self.initial_positions = {}
        self.setZValue(1)  # Ensure blocks are above the background

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
        self.text_item.setPos(
            (width - text_rect.width()) / 2, (height - text_rect.height()) / 2)

    def mousePressEvent(self, event):
        # Determine where the user clicked (top or bottom half)
        click_position = event.pos().y()
        block_height = self.boundingRect().height()
        self.dragging_from_top = click_position < (block_height / 2)

        # Store initial positions of all connected blocks
        self.initial_positions = {}
        blocks_to_move = self.get_all_connected_blocks()
        for block in blocks_to_move:
            # Store the scene positions
            self.initial_positions[block] = block.mapToScene(QPointF(0, 0))

        # Disconnect from previous and next blocks depending on where the block is grabbed
        if self.dragging_from_top:
            if self.prev_block:
                self.prev_block.next_block = None
                self.prev_block = None
        else:
            if self.next_block:
                self.next_block.prev_block = None
                self.next_block = None

        # If the block is inside a control block, we need to detach it temporarily
        if self.parent_block:
            self.parent_block.remove_child_block(self)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

        # Calculate movement delta in scene coordinates
        new_scene_pos = self.mapToScene(QPointF(0, 0))
        delta = new_scene_pos - self.initial_positions[self]

        # Move connected blocks
        blocks_to_move = self.get_all_connected_blocks()
        for block in blocks_to_move:
            if block != self:
                initial_pos = self.initial_positions[block]
                # Correct position setting
                if block.parentItem():
                    # Convert scene position to parent's coordinate system
                    parent_pos = block.parentItem().mapFromScene(initial_pos + delta)
                    block.setPos(parent_pos)
                else:
                    block.setPos(initial_pos + delta)

        self.check_for_snap()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.snap_to_block()

    def mouseDoubleClickEvent(self, event):
        # Disconnect from previous and next blocks
        self.disconnect_blocks()
        super().mouseDoubleClickEvent(event)

    def disconnect_blocks(self):
        # Disconnect from previous block
        if self.prev_block:
            self.prev_block.next_block = None
            self.prev_block = None
        # Disconnect from next block
        if self.next_block:
            self.next_block.prev_block = None
            self.next_block = None
        # If it's inside a control block, remove it
        if self.parent_block:
            self.parent_block.remove_child_block(self)
            self.parent_block = None

    def get_all_connected_blocks(self):
        # Get all connected blocks (both prev and next, and child blocks)
        blocks = set()
        stack = [self]
        while stack:
            block = stack.pop()
            if block not in blocks:
                blocks.add(block)
                # Include child blocks if it's a ControlBlock
                if isinstance(block, ControlBlock):
                    stack.extend(block.child_blocks)
                # Add connected blocks
                if block.prev_block:
                    stack.append(block.prev_block)
                if block.next_block:
                    stack.append(block.next_block)
        return blocks

    def check_for_snap(self):
        # Reset any previous highlighted block
        if self.highlighted_block:
            self.highlighted_block.setPen(QPen(Qt.black))
            self.highlighted_block = None

        # Highlight potential snap targets
        colliding_items = self.scene().collidingItems(self)

        # Filter out child items and self
        colliding_items = [item for item in colliding_items if item != self and not self.is_descendant_of(item)]

        for item in colliding_items:
            if isinstance(item, ControlBlock):
                if item.is_open_area(self.scenePos()):
                    item.setPen(QPen(QColor('purple'), 2))
                    self.highlighted_block = item
                    return
                else:
                    if self.dragging_from_top and self.is_near(item, above=True):
                        item.setPen(QPen(QColor('green'), 2))
                        self.highlighted_block = item
                        return
                    elif not self.dragging_from_top and self.is_near(item, below=True):
                        item.setPen(QPen(QColor('blue'), 2))
                        self.highlighted_block = item
                        return
            elif isinstance(item, Block):
                if self.dragging_from_top and self.is_near(item, above=True):
                    item.setPen(QPen(QColor('green'), 2))
                    self.highlighted_block = item
                    return
                elif not self.dragging_from_top and self.is_near(item, below=True):
                    item.setPen(QPen(QColor('blue'), 2))
                    self.highlighted_block = item
                    return

    def is_descendant_of(self, item):
        # Check if self is a child or descendant of the given item
        current = self.parentItem()
        while current:
            if current == item:
                return True
            current = current.parentItem()
        return False

    def is_near(self, other_block, above=False, below=False):
        threshold = 20  # Adjusted threshold for better snapping
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
            # Reset pen of the highlighted block
            self.highlighted_block.setPen(QPen(Qt.black))

            # Disconnect any existing connections
            # Only disconnect if not snapping into a control block
            if not (isinstance(self.highlighted_block, ControlBlock) and self.highlighted_block.is_open_area(self.scenePos())):
                self.disconnect_blocks()

            if isinstance(self.highlighted_block, ControlBlock) and self.highlighted_block.is_open_area(self.scenePos()):
                # Snap into the control block
                self.highlighted_block.add_child_blocks(self)
            else:
                if self.dragging_from_top and self.is_near(self.highlighted_block, above=True):
                    # Snap the bottom of self to the top of the highlighted block
                    self.next_block = self.highlighted_block
                    self.highlighted_block.prev_block = self
                    
                    # Align positions
                    new_x = self.highlighted_block.scenePos().x()
                    new_y = self.highlighted_block.scenePos().y() - self.boundingRect().height() + 2
                    self.setPos(new_x, new_y)
                    prev_block = self.prev_block
                    while prev_block is not None:
                        if prev_block.parent_block is not None:
                            prev_block.parent_block.add_child_blocks(self)
                        prev_block = prev_block.prev_block
                elif not self.dragging_from_top and self.is_near(self.highlighted_block, below=True):
                    # Snap the top of self to the bottom of the highlighted block
                    self.prev_block = self.highlighted_block
                    self.highlighted_block.next_block = self

                    # Align positions
                    new_x = self.highlighted_block.scenePos().x()
                    new_y = self.highlighted_block.scenePos().y() + self.highlighted_block.boundingRect().height() - 2
                    self.setPos(new_x, new_y)
                    prev_block = self.prev_block
                    while prev_block is not None:
                        if prev_block.parent_block is not None:
                            prev_block.parent_block.add_child_blocks(self)
                        prev_block = prev_block.prev_block

            self.highlighted_block = None
        else:
            # If not snapped to anything, ensure the block is standalone
            pass  # Do not disconnect here to maintain existing connections
    

    def move_down(self, delta_y=20):
        """
        Moves the block downward by delta_y pixels.
        Also moves all connected next blocks accordingly.
        """
        if self.parent_block:
            # If the block is nested inside a control block, move the entire control block
            self.parent_block.move_down(delta_y)
            return

        # Move this block
        current_pos = self.scenePos()
        new_pos = QPointF(current_pos.x(), current_pos.y() + delta_y)
        self.setPos(new_pos)

        # Move connected next blocks
        if self.next_block:
            self.next_block.move_down(delta_y)

    
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
        self.initControlUI()
        self.setZValue(0)  # Control blocks are below child blocks

    def initControlUI(self):
        self.width = 140
        self.height = 80  # Initial height
        self.notch_size = 10
        self.tab_width = 20
        self.tab_height = 10

        self.update_shape()

        # Add text
        self.text_item.setPlainText(self.text)
        font = QFont('Arial', 12)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos((self.width - text_rect.width()) / 2, 10)

    def update_shape(self):
        self.prepareGeometryChange()
        path = QPainterPath()
        # Create a control block shape with an open area for child blocks
        path.moveTo(0, self.notch_size)
        path.lineTo(self.tab_width, self.notch_size)
        path.lineTo(self.tab_width + self.notch_size, 0)
        path.lineTo(self.width - (self.tab_width + self.notch_size), 0)
        path.lineTo(self.width - self.tab_width, self.notch_size)
        path.lineTo(self.width, self.notch_size)
        path.lineTo(self.width, self.height - self.notch_size)
        path.lineTo(self.width - self.tab_width, self.height - self.notch_size)
        path.lineTo(self.width - (self.tab_width + self.notch_size), self.height)
        path.lineTo(self.tab_width + self.notch_size, self.height)
        path.lineTo(self.tab_width, self.height - self.notch_size)
        path.lineTo(0, self.height - self.notch_size)
        path.closeSubpath()

        self.setPath(path)
        self.setBrush(QBrush(self.color))
        self.setPen(QPen(Qt.black))

    def is_open_area(self, pos):
        # Define the open area where child blocks can be placed
        local_pos = self.mapFromScene(pos)
        open_rect = QRectF(
            10, 30, self.width - 20, self.height - 60)
        return open_rect.contains(local_pos)

    def update_size(self):
        # Adjust the height of the control block based on the child blocks
        total_height = 80  # Initial height
        for child in self.child_blocks:
            child_height = child.boundingRect().height()
            total_height += child_height
        self.height = total_height
        self.update_shape()
        self.reposition_child_blocks()
        
            
        # Update parent control blocks
        if self.parent_block:
            self.parent_block.update_size()

    def add_child_blocks(self, block):
        # Remove any previous connections
        block.disconnect_blocks()

        # Add a block and its connected next blocks as child blocks
        blocks_to_add = block.get_all_connected_blocks()
        for blk in blocks_to_add:
            blk.parent_block = self
            if blk in self.child_blocks:
                continue
            self.child_blocks.append(blk)
            blk.setParentItem(self)
            blk.setFlag(QGraphicsItem.ItemIsMovable, False)
            blk.setZValue(1)  # Child blocks are above control blocks
        self.update_size()
        updated_block = self.next_block
        while updated_block is not None:
            self.next_block.move_down(block.boundingRect().height())
            updated_block = updated_block.next_block

    def remove_child_block(self, block):
        # Remove a block from child_blocks
        if block in self.child_blocks:
            self.child_blocks.remove(block)
            # Need to map position to scene before removing from parent
            scene_pos = block.mapToScene(QPointF(0, 0))
            block.setParentItem(None)
            block.setPos(scene_pos)
            block.parent_block = None
            block.setFlag(QGraphicsItem.ItemIsMovable, True)
            block.setZValue(1)  # Reset z-value
            # If the block has connected next blocks, remove them as well
            next_blocks = block.get_all_connected_blocks()
            for blk in next_blocks:
                if blk in self.child_blocks:
                    self.child_blocks.remove(blk)
                    scene_pos = blk.mapToScene(QPointF(0, 0))
                    blk.setParentItem(None)
                    blk.setPos(scene_pos)
                    blk.parent_block = None
                    blk.setFlag(QGraphicsItem.ItemIsMovable, True)
                    blk.setZValue(1)  # Reset z-value
        self.update_size()

    def reposition_child_blocks(self):
        # Reposition all child blocks within the control block
        y_offset = 40
        for child in self.child_blocks:
            child.setPos(20, y_offset)
            y_offset += child.boundingRect().height()
            # If child is a ControlBlock, ensure it repositions its children
            if isinstance(child, ControlBlock):
                child.reposition_child_blocks()

    def generate_code(self):
        code_lines = []
        if self.text == 'Repeat':
            code_lines.append('for i in range(10):')
            for child in self.child_blocks:
                child_code = child.generate_code()
                indented_code = '\n'.join(
                    ['    ' + line for line in child_code.split('\n')])
                code_lines.append(indented_code)
        if self.next_block:
            code_lines.append(self.next_block.generate_code())
        return '\n'.join(code_lines)

    def mousePressEvent(self, event):
        # Same as in Block class
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

    def check_for_snap(self):
        super().check_for_snap()

    def snap_to_block(self):
        super().snap_to_block()


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
        self.setWindowTitle('Rudiron visual programming')
        self.setWindowIcon(QtGui.QIcon('ico.png'))
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
        blocks = [item for item in self.workspace.scene().items()
                  if isinstance(item, Block) and item.prev_block is None and not item.parent_block]
        # Sort blocks by their vertical position
        blocks.sort(key=lambda block: block.scenePos().y())
        program = []
        for block in blocks:
            code = block.generate_code()
            program.append(code)
        rudiron_code = '\n'.join(program)
        # Display or execute the code
        QMessageBox.information(
            self, "Program", f"Program to execute on Rudiron:\n{rudiron_code}")
        # Here you can add code to send 'rudiron_code' to the Rudiron controller


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())