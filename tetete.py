import os
import sys

import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QApplication, QWidget, QGraphicsView, QGraphicsScene, QGraphicsItem,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QGraphicsTextItem,
    QGraphicsPathItem, QLineEdit, QGraphicsProxyWidget, QComboBox, QScrollArea, QDialog, QScrollArea, QDialog, QTextEdit
)
from PyQt6.QtGui import QBrush, QColor, QPen, QPainterPath, QFont, QPainter, QIcon
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from rudiron import upload_to_board, reset_arduino

import keyword
import re

# PINS = list(range(0, 18)) + list(range(20, 27)) + list(range(28, 36))
PINS = list(range(0, 36))
# Список ключевых слов C++
cpp_keywords = {
    "alignas", "alignof", "and", "and_eq", "asm", "atomic_cancel", "atomic_commit",
    "atomic_noexcept", "auto", "bitand", "bitor", "bool", "break", "case", "catch",
    "char", "char8_t", "char16_t", "char32_t", "class", "compl", "concept", "const",
    "constexpr", "const_cast", "continue", "co_await", "co_return", "co_yield",
    "decltype", "default", "delete", "do", "double", "dynamic_cast", "else", "enum",
    "explicit", "export", "extern", "false", "float", "for", "friend", "goto", "if",
    "inline", "int", "long", "mutable", "namespace", "new", "noexcept", "not",
    "not_eq", "nullptr", "operator", "or", "or_eq", "private", "protected", "public",
    "register", "reinterpret_cast", "requires", "return", "short", "signed", "sizeof",
    "static", "static_assert", "static_cast", "struct", "switch", "synchronized",
    "template", "this", "thread_local", "throw", "true", "try", "typedef", "typeid",
    "typename", "union", "unsigned", "using", "virtual", "void", "volatile",
    "wchar_t", "while", "xor", "xor_eq"
}


def is_valid_analog_pin(pin):
    return True


def is_valid_digital_pin(pin):
    return True


def is_valid_integer(value):
    # Регулярное выражение для целых чисел
    pattern = r'^[+-]?\d+$'
    return bool(re.match(pattern, value))


def is_valid_cpp_variable_name(name):
    # Проверяем, что имя не является ключевым словом C++
    if name in cpp_keywords:
        return False
    if re.match(r'^i\d+$', name):
        return False
    # Проверяем формат имени переменной
    if re.match(r'^[a-zA-Z_]\w*$', name):
        return True
    return False


# Пример использования
test_names = ["variable", "2variable", "_variable", "int", "var_123"]
for name in test_names:
    print(f"{name}: {'Valid' if is_valid_cpp_variable_name(name) else 'Invalid'}")

declared_variables = set()  # should fix it, temp impl


def is_valid_integer_or_var(text):
    return is_valid_integer(text) or text in declared_variables


def show_message_box(text, title="Внимание"):
    message_box = QMessageBox()
    message_box.setWindowTitle(title)
    message_box.setText(text)
    message_box.setStandardButtons(QMessageBox.StandardButton.Yes)
    message_box.setIcon(QMessageBox.Icon.Warning)
    message_box.exec()


class PopupWindow(QDialog):
    def __init__(self, title, text, width=300, height=50):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(width, height)

        # Добавляем элементы в окно
        layout = QVBoxLayout()
        label = QLabel(text)
        close_button = QPushButton("Закрыть")

        # Закрытие окна по нажатию кнопки
        close_button.clicked.connect(self.close)

        layout.addWidget(label)
        layout.addWidget(close_button)
        self.setLayout(layout)


class Block(QGraphicsPathItem):
    def __init__(self, text, color, parent=None):
        super().__init__(parent)
        self.text = text
        self.color = color
        self.width = 160
        self.height = 40
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        )
        self.next_block = None
        self.prev_block = None
        self.parent_block = None
        self.highlighted_block = None
        self.dragging_from_top = False  # To track where the block is grabbed
        self.initial_positions = {}
        self.setZValue(1)  # Ensure blocks are above the background

    def initUI(self, width=None, height=None):
        path = QPainterPath()
        width = self.width
        height = self.height
        notch_size = 5
        tab_width = 20
        tab_height = 5

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
        self.setPen(QPen(Qt.GlobalColor.black))

        # Add text
        # self.text_item = QGraphicsTextItem(self.text, self)
        # font = QFont('Arial', 12)
        # self.text_item.setFont(font)
        # text_rect = self.text_item.boundingRect()
        # self.text_item.setPos(
        #     (width - text_rect.width()) / 2, (height - text_rect.height()) / 2)

    def mousePressEvent(self, event):
        # Set focus to the workspace
        if self.scene().views():
            self.scene().views()[0].setFocus()

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

        # # Disconnect from previous and next blocks depending on where the block is grabbed
        # if self.dragging_from_top:
        #     if self.prev_block:
        #         self.prev_block.next_block = None
        #         self.prev_block = None
        # else:
        #     if self.next_block:
        #         self.next_block.prev_block = None
        #         self.next_block = None

        # # If the block is inside a control block, we need to detach it temporarily
        # if self.parent_block:
        #     self.parent_block.remove_child_block(self)

        super().mousePressEvent(event)

    def find_head(self):
        head = self
        while head.prev_block:
            head = head.prev_block
        return head

    def find_tail(self):
        tail = self
        while tail.next_block:
            tail = tail.next_block
        return tail

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
        head, tail = self.find_head(), self.find_tail()
        head.check_for_snap()
        tail.check_for_snap()
        # self.check_for_snap()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        head, tail = self.find_head(), self.find_tail()
        head.snap_to_block()
        tail.snap_to_block()
        # self.snap_to_block()

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

    # def check_for_snap(self):
    #     # Reset any previous highlighted block
    #     if self.highlighted_block:
    #         self.highlighted_block.setPen(QPen(Qt.GlobalColor.black))
    #         self.highlighted_block = None

    #     # Highlight potential snap targets
    #     colliding_items = self.scene().collidingItems(self)

    #     # Filter out child items and self
    #     connected_blocks = self.get_all_connected_blocks()
    #     colliding_items = [item for item in colliding_items if item != self and not self.is_descendant_of(item) and item not in connected_blocks]

    #     for item in colliding_items:
    #         if isinstance(item, ControlBlock):
    #             if item.is_open_area(self.scenePos()):
    #                 item.setPen(QPen(QColor('purple'), 2))
    #                 self.highlighted_block = item
    #                 return
    #             else:
    #                 if self.dragging_from_top and self.is_near(item, above=True):
    #                     item.setPen(QPen(QColor('green'), 2))
    #                     self.highlighted_block = item
    #                     return
    #                 elif not self.dragging_from_top and self.is_near(item, below=True):
    #                     item.setPen(QPen(QColor('blue'), 2))
    #                     self.highlighted_block = item
    #                     return
    #         elif isinstance(item, Block):
    #             if self.dragging_from_top and self.is_near(item, above=True):
    #                 item.setPen(QPen(QColor('green'), 2))
    #                 self.highlighted_block = item
    #                 return
    #             elif not self.dragging_from_top and self.is_near(item, below=True):
    #                 item.setPen(QPen(QColor('blue'), 2))
    #                 self.highlighted_block = item
    #                 return

    def check_for_snap(self):
        # Reset any previous highlighted block
        if self.highlighted_block:
            self.highlighted_block.setPen(QPen(Qt.GlobalColor.black))
            self.highlighted_block = None

        # Highlight potential snap targets
        colliding_items = self.scene().collidingItems(self)

        # Filter out child items and self
        connected_blocks = self.get_all_connected_blocks()
        colliding_items = [item for item in colliding_items if
                           item != self and not self.is_descendant_of(item) and item not in connected_blocks]

        for item in colliding_items:
            if isinstance(item, ControlBlock):
                if item.is_open_area(self.scenePos()):
                    item.setPen(QPen(QColor('purple'), 2))
                    self.highlighted_block = item
                    return
                else:
                    if self.is_near(item, above=True):
                        item.setPen(QPen(QColor('green'), 2))
                        self.highlighted_block = item
                        return
                    elif self.is_near(item, below=True):
                        item.setPen(QPen(QColor('blue'), 2))
                        self.highlighted_block = item
                        return
            elif isinstance(item, Block):
                if self.is_near(item, above=True):
                    item.setPen(QPen(QColor('green'), 2))
                    self.highlighted_block = item
                    return
                elif self.is_near(item, below=True):
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
            if abs(self_bottom - other_top) < threshold and abs(
                    self.scenePos().x() - other_block.scenePos().x()) < threshold:
                return True
        if below:
            # Check if the top of self is near the bottom of other_block
            self_top = self.sceneBoundingRect().top()
            other_bottom = other_block.sceneBoundingRect().bottom()
            if abs(self_top - other_bottom) < threshold and abs(
                    self.scenePos().x() - other_block.scenePos().x()) < threshold:
                return True
        return False

    # def snap_to_block(self):
    #     if self.highlighted_block:
    #         # Reset pen of the highlighted block
    #         self.highlighted_block.setPen(QPen(Qt.GlobalColor.black))

    #         # Disconnect any existing connections
    #         # Only disconnect if not snapping into a control block
    #         # if not (isinstance(self.highlighted_block, ControlBlock) and self.highlighted_block.is_open_area(self.scenePos())):
    #         #     self.disconnect_blocks()

    #         if isinstance(self.highlighted_block, ControlBlock) and self.highlighted_block.is_open_area(self.scenePos()):
    #             # Snap into the control block
    #             if len(self.highlighted_block.child_blocks):
    #                 self.highlighted_block.child_blocks[-1].next_block = self
    #                 self.prev_block = self.highlighted_block.child_blocks[-1]
    #             self.highlighted_block.add_child_blocks(self)
    #         else:
    #             if self.dragging_from_top and self.is_near(self.highlighted_block, above=True):
    #                 if self.highlighted_block.prev_block is not None and self.highlighted_block.prev_block != self:
    #                     self.prev_block = self.highlighted_block.prev_block
    #                     self.highlighted_block.prev_block.next_block = self
    #                     self.prev_block.move_up(self.boundingRect().height())
    #                 # Snap the bottom of self to the top of the highlighted block
    #                 self.next_block = self.highlighted_block
    #                 self.highlighted_block.prev_block = self

    #                 # Align positions
    #                 new_x = self.highlighted_block.scenePos().x()
    #                 new_y = self.highlighted_block.scenePos().y() - self.boundingRect().height() + 2
    #                 self.setPos(new_x, new_y)
    #                 prev_block = self.prev_block
    #                 while prev_block is not None:
    #                     if prev_block.parent_block is not None:
    #                         prev_block.parent_block.add_child_blocks(self)
    #                     prev_block = prev_block.prev_block
    #             elif not self.dragging_from_top and self.is_near(self.highlighted_block, below=True):
    #                 print(self.highlighted_block)
    #                 if self.highlighted_block.next_block is not None and self.highlighted_block.next_block != self:
    #                     self.next_block = self.highlighted_block.next_block
    #                     self.highlighted_block.next_block.prev_block = self
    #                     self.next_block.move_down(self.boundingRect().height(), False)
    #                 # Snap the top of self to the bottom of the highlighted block
    #                 self.prev_block = self.highlighted_block
    #                 self.highlighted_block.next_block = self

    #                 # Align positions
    #                 new_x = self.highlighted_block.scenePos().x()
    #                 new_y = self.highlighted_block.scenePos().y() + self.highlighted_block.boundingRect().height() - 2
    #                 self.setPos(new_x, new_y)
    #                 prev_block = self.prev_block
    #                 while prev_block is not None:
    #                     if prev_block.parent_block is not None:
    #                         prev_block.parent_block.add_child_blocks(self)
    #                     prev_block = prev_block.parent_block

    #         self.highlighted_block = None
    #     else:
    #         # If not snapped to anything, ensure the block is standalone
    #         pass  # Do not disconnect here to maintain existing connections
    def reposition_next_blocks(self):
        y_offset = self.height + self.y()
        current = self.next_block
        while current:
            current.setPos(self.x(), y_offset)
            y_offset += current.boundingRect().height()
            if isinstance(current, ControlBlock):
                current.reposition_child_blocks()
            current = current.next_block

    def reposition_prev_blocks(self):
        y_offset = -self.height + self.y()
        current = self.prev_block
        while current:
            current.setPos(self.x(), y_offset)
            y_offset -= current.boundingRect().height()
            if isinstance(current, ControlBlock):
                current.reposition_child_blocks()
            current = current.prev_block

    def snap_to_block(self):
        if self.highlighted_block:
            # Reset pen of the highlighted block
            self.highlighted_block.setPen(QPen(Qt.GlobalColor.black))

            # Disconnect any existing connections
            # Only disconnect if not snapping into a control block
            # if not (isinstance(self.highlighted_block, ControlBlock) and self.highlighted_block.is_open_area(self.scenePos())):
            #     self.disconnect_blocks()

            if isinstance(self.highlighted_block, ControlBlock) and self.highlighted_block.is_open_area(
                    self.scenePos()):
                # Snap into the control block
                if len(self.highlighted_block.child_blocks):
                    self.highlighted_block.child_blocks[-1].next_block = self
                    self.prev_block = self.highlighted_block.child_blocks[-1]
                self.highlighted_block.add_child_blocks(self)
            else:
                if self.is_near(self.highlighted_block, above=True):
                    if self.highlighted_block.prev_block is not None and self.highlighted_block.prev_block != self:
                        self.prev_block = self.highlighted_block.prev_block
                        self.highlighted_block.prev_block.next_block = self
                        self.prev_block.move_up(self.boundingRect().height())
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
                    self.reposition_prev_blocks()
                elif self.is_near(self.highlighted_block, below=True):
                    if self.highlighted_block.next_block is not None and self.highlighted_block.next_block != self:
                        self.next_block = self.highlighted_block.next_block
                        self.highlighted_block.next_block.prev_block = self
                        self.next_block.move_down(self.boundingRect().height(), False)
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
                        prev_block = prev_block.parent_block
                    self.reposition_next_blocks()

            self.highlighted_block = None
        else:
            # If not snapped to anything, ensure the block is standalone
            pass  # Do not disconnect here to maintain existing connections

    def move_up(self, delta_y=20, move_parent_block=False):
        """
        Moves the block upward by delta_y pixels.
        Also moves all connected previous blocks accordingly.
        """
        if self.parent_block and move_parent_block:
            # If the block is nested inside a control block, move the entire control block
            self.parent_block.move_up(delta_y)
            return

        # Move this block
        current_pos = self.scenePos()
        new_pos = QPointF(current_pos.x(), current_pos.y() - delta_y)
        self.setPos(new_pos)

        # Move connected next blocks
        if self.prev_block is not None:
            self.prev_block.move_up(delta_y)

    def move_down(self, delta_y=20, move_parent_block=False):
        """
        Moves the block downward by delta_y pixels.
        Also moves all connected next blocks accordingly.
        """
        if self.parent_block and move_parent_block:
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
        """
        Moves the block downward by delta_y pixels.
        Also moves all connected next blocks accordingly.
        """
        if self.parent_block and move_parent_block:
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

    def generate_code(self, recursion_depth=0):
        command_mapping = {
            'PIN': 'digitalWrite({}, {});',
            'Сон': 'delay({});',
            'Переменные': 'auto {} = {};',
            'Условие': 'if ({} {} {})',
            'Повтор': 'for (int i = 0; i < {n}; ++i)',
            'ЦЧтение': 'digitalRead({});',
            'АЧтение': 'analogRead({});',
            'ЦЗапись': 'digitalWrite({}, {});',
            'АЗапись': 'analogWrite({}, {});',
            'Слушай': 'Serial.read();',
            'Говори': 'Serial.println({});'}
        command = command_mapping.get(self.text, '')
        code_lines = [command]
        if self.next_block:
            code = self.next_block.generate_code(recursion_depth)
            if code is None:
                return
            code_lines.append(code)
        return '\n'.join(code_lines)

    def suicide(self):
        self.disconnect_blocks()
        self.scene().removeItem(self)


class ControlBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)

        self.width = 180
        self.child_blocks = []
        self.initControlUI()
        self.setZValue(0)  # Control blocks are below child blocks

    def initControlUI(self):
        self.height = 80  # Initial height
        self.notch_size = 10
        self.tab_width = 20
        self.tab_height = 10

        self.update_shape()

        # Add text
        # self.text_item = QGraphicsTextItem(self.text, self)
        # font = QFont('Arial', 12)
        # self.text_item.setFont(font)
        # text_rect = self.text_item.boundingRect()
        # self.text_item.setPos((self.width - text_rect.width()) / 2, 10)

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
        self.setPen(QPen(Qt.GlobalColor.black))

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

    def add_child_blocks(self, block: Block):
        # Remove any previous connections
        # block.disconnect_blocks()
        # Add a block and its connected next blocks as child blocks
        # blocks_to_add = block.get_all_connected_blocks()
        blocks_to_add = [block]
        for blk in blocks_to_add:
            blk.parent_block = self
            if blk in self.child_blocks:
                continue
            if blk.prev_block is not None and blk.prev_block in self.child_blocks:
                index = self.child_blocks.index(blk.prev_block)
                self.child_blocks.insert(index + 1, blk)
            else:
                self.child_blocks.append(blk)
            blk.setParentItem(self)
            blk.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            blk.setZValue(1)  # Child blocks are above control blocks
        self.update_size()
        if self.next_block is not None:
            self.next_block.move_down(block.boundingRect().height(), False)

    def remove_child_block(self, block):
        # Remove a block from child_blocks
        if block in self.child_blocks:
            self.child_blocks.remove(block)
            # Need to map position to scene before removing from parent
            scene_pos = block.mapToScene(QPointF(0, 0))
            block.setParentItem(None)
            block.setPos(scene_pos)
            block.parent_block = None
            block.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
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
                    blk.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                    blk.setZValue(1)  # Reset z-value
        self.update_size()

    def reposition_child_blocks(self):
        # Reposition all child blocks within the control block
        y_offset = 40
        for child in self.child_blocks:
            child.setPos(abs(self.width - child.width) // 2, y_offset)

            y_offset += child.boundingRect().height()
            # If child is a ControlBlock, ensure it repositions its children
            if isinstance(child, ControlBlock):
                child.reposition_child_blocks()

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


class StartBlock(Block):
    start_block = None

    def __init__(self, text, color, parent=None):
        if StartBlock.start_block is not None:
            StartBlock.start_block.suicide()
            StartBlock.start_block = None
        super().__init__(text, color, parent)
        self.child_blocks = []
        # self.width = 120
        self.setZValue(1)  # Control blocks are below child blocks
        self.initUI()
        StartBlock.start_block = self

    def initUI(self):
        super().initUI()
        width = self.width
        height = self.height
        delta = 5

        # Add text
        self.text_item = QGraphicsTextItem("Начало", self)
        font = QFont('Arial', 20)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos((self.width - text_rect.width()) // 2, (height - text_rect.height()) / 2)

    def suicide(self):
        StartBlock.start_block = None
        super().suicide()


class VariableBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.child_blocks = []
        self.setZValue(1)  # Control blocks are below child blocks
        self.initUI()

    def initUI(self):
        super().initUI()
        width = self.width
        height = self.height
        delta = 5

        #
        self.text_field1 = QLineEdit()
        self.text_field1.setFont(QFont('Arial', 10))
        self.text_field1.setFixedWidth(50)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field1)
        self.text_field_proxy.setParentItem(self)
        text_rect = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos(delta * 3, (height - text_rect.height()) / 2)

        # Add text
        self.text_item = QGraphicsTextItem("=", self)
        font = QFont('Arial', 16)
        self.text_item.setFont(font)
        text_rect_1 = self.text_item.boundingRect()
        self.text_item.setPos(delta * 2 + text_rect.width() + delta * 2, (height - text_rect_1.height()) / 2)

        #
        self.text_field2 = QLineEdit()
        self.text_field2.setFont(QFont('Arial', 10))
        self.text_field2.setFixedWidth(50)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field2)
        self.text_field_proxy.setParentItem(self)
        text_rect_2 = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos(delta * 2 + text_rect.width() + int(delta * 2 * 1.5) + text_rect_1.width(),
                                     (self.height - text_rect_2.height()) / 2)

    def generate_code(self, recursion_depth=0):
        if self.text_field1.text() == "" or not is_valid_cpp_variable_name(self.text_field1.text()):
            show_message_box(f"Название переменной '{self.text_field1.text()}' некорректно!")
            return None
        if not is_valid_integer_or_var(self.text_field2.text()):
            show_message_box(
                f"Значение переменной '{self.text_field1.text()}' должно быть целым числом или переменной!")
            return None
        if self.text_field1.text() in declared_variables:
            show_message_box(f"Переменная '{self.text_field1.text()}' объявлена несколько раз!")
            return None
        declared_variables.add(self.text_field1.text())
        program = 'auto {} = {};\n'
        program = program.format(self.text_field1.text(), self.text_field2.text())
        if self.next_block:
            result = self.next_block.generate_code(recursion_depth)
            if result is None:
                return None
            return program + result
        return program


class ArithmeticBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.child_blocks = []
        self.setZValue(1)  # Control blocks are below child blocks
        self.initUI()

    def initUI(self):
        super().initUI()
        width = self.width
        height = self.height
        delta = 5

        #
        self.text_field1 = QLineEdit()
        self.text_field1.setFont(QFont('Arial', 10))
        self.text_field1.setFixedWidth(25)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field1)
        self.text_field_proxy.setParentItem(self)
        text_rect = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos(delta * 1, (height - text_rect.height()) / 2)

        # Add text
        self.text_item = QGraphicsTextItem("=", self)
        font = QFont('Arial', 13)
        self.text_item.setFont(font)
        text_rect_1 = self.text_item.boundingRect()
        self.text_item.setPos(delta * 1 + text_rect.width(), (height - text_rect_1.height()) / 2)

        #
        self.text_field2 = QLineEdit()
        self.text_field2.setFont(QFont('Arial', 10))
        self.text_field2.setFixedWidth(25)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field2)
        self.text_field_proxy.setParentItem(self)
        text_rect_2 = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos(int(delta * 1.5) + text_rect.width() + delta * 0 + text_rect_1.width(),
                                     (self.height - text_rect_2.height()) / 2)

        # Add combo box
        self.combo_box = QComboBox()
        self.combo_box.addItems(['*', '-', '+', '/', '//', '%'])
        self.combo_box.setFont(QFont('Arial', 8))

        self.combo_box_proxy = QGraphicsProxyWidget(self)
        self.combo_box_proxy.setWidget(self.combo_box)
        text_rect3 = self.combo_box_proxy.boundingRect()
        self.combo_box_proxy.setParentItem(self)
        self.combo_box_proxy.setPos(
            int(delta * 1.0) + text_rect.width() + delta * 0 + text_rect_1.width() + text_rect3.width(),
            (text_rect3.height()) / 2)
        self.combo_box_proxy.setZValue(2)

        #
        self.text_field3 = QLineEdit()
        self.text_field3.setFont(QFont('Arial', 10))
        self.text_field3.setFixedWidth(25)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field3)
        self.text_field_proxy.setParentItem(self)
        text_rect_2 = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos(
            int(delta * 2) + text_rect.width() + delta * 2 + text_rect_1.width() + text_rect3.width() + text_rect_2.width(),
            (self.height - text_rect_2.height()) / 2)

    def generate_code(self, recursion_depth=0):
        program = '{} = {} {} {};'
        if self.text_field1.text() not in declared_variables:
            show_message_box(f"Переменная {self.text_field1.text()} не объявлена!")
            return None
        if not is_valid_integer_or_var(self.text_field2.text()):
            show_message_box(f"Значение левого операнда должно быть целым числом или переменной!")
            return None
        if not is_valid_integer_or_var(self.text_field3.text()):
            show_message_box(f"Значение правого операнда должно быть целым числом или переменной!")
            return None
        program = program.format(self.text_field1.text(), self.text_field2.text(), self.combo_box.currentText(),
                                 self.text_field3.text())
        if self.next_block:
            result = self.next_block.generate_code(recursion_depth)
            if result is None:
                return None
            return program + result
        return program


class DelayBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.initDelayUI()

    def initDelayUI(self):
        self.initUI()
        self.notch_size = 10
        self.tab_width = 20
        self.tab_height = 10

        # Add text Сон
        self.text_item = QGraphicsTextItem("Сон", self)
        font = QFont('Arial', 12)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos(
            (self.width - text_rect.width()) / 5, (self.height - text_rect.height()) / 2)

        # Add changeable text field (QLineEdit)
        self.text_field = QLineEdit()
        self.text_field.setFont(QFont('Arial', 10))
        self.text_field.setFixedWidth(30)

        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field)
        text_rect = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setParentItem(self)
        self.text_field_proxy.setPos(
            (self.width - text_rect.width()) / 5 * 3.5, (self.height - text_rect.height()) / 2)

    def generate_code(self, recursion_depth=0):
        if not is_valid_integer_or_var(self.text_field.text()):
            show_message_box("Продолжительность сна должна быть целым числом или переменной!")
            return None
        program = 'delay({});\n'
        program = program.format(self.text_field.text())
        if self.next_block:
            result = self.next_block.generate_code(recursion_depth)
            if result is None:
                return None
            return program + result
        return program


class ControlBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)

        self.width = 180
        self.child_blocks = []
        self.initControlUI()
        self.setZValue(0)  # Control blocks are below child blocks

    def initControlUI(self):
        self.height = 80  # Initial height
        self.notch_size = 10
        self.tab_width = 20
        self.tab_height = 10

        self.update_shape()

        # Add text
        # self.text_item = QGraphicsTextItem(self.text, self)
        # font = QFont('Arial', 12)
        # self.text_item.setFont(font)
        # text_rect = self.text_item.boundingRect()
        # self.text_item.setPos((self.width - text_rect.width()) / 2, 10)

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
        self.setPen(QPen(Qt.GlobalColor.black))

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

    def add_child_blocks(self, block: Block):
        # Remove any previous connections
        # block.disconnect_blocks()
        # Add a block and its connected next blocks as child blocks
        blocks_to_add = block.get_all_connected_blocks()
        # blocks_to_add = [block]
        for blk in blocks_to_add:
            blk.parent_block = self
            if blk in self.child_blocks:
                continue
            if blk.prev_block is not None and blk.prev_block in self.child_blocks:
                index = self.child_blocks.index(blk.prev_block)
                self.child_blocks.insert(index + 1, blk)
            else:
                self.child_blocks.append(blk)
            blk.setParentItem(self)
            blk.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            blk.setZValue(1)  # Child blocks are above control blocks
        self.update_size()
        if self.next_block is not None:
            self.next_block.move_down(block.boundingRect().height(), False)

    def remove_child_block(self, block):
        # Remove a block from child_blocks
        if block in self.child_blocks:
            self.child_blocks.remove(block)
            # Need to map position to scene before removing from parent
            scene_pos = block.mapToScene(QPointF(0, 0))
            block.setParentItem(None)
            block.setPos(scene_pos)
            block.parent_block = None
            block.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
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
                    blk.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                    blk.setZValue(1)  # Reset z-value
        self.update_size()

    def reposition_child_blocks(self):
        # Reposition all child blocks within the control block
        y_offset = 40
        for child in self.child_blocks:
            child.setPos(abs(self.width - child.width) // 2, y_offset)

            y_offset += child.boundingRect().height()
            # If child is a ControlBlock, ensure it repositions its children
            if isinstance(child, ControlBlock):
                child.reposition_child_blocks()

    def generate_code(self, recursion_depth=0):
        code_lines = []
        if self.text == 'Повтор':
            code_lines.append('for i in range(10):')
            # for child in self.child_blocks:
            #     child_code = child.generate_code(recursion_depth)
            #     indented_code = '\n'.join(
            #         ['    ' + line for line in child_code.split('\n')])
            #     code_lines.append(indented_code)
        if self.child_blocks:
            program += self.child_blocks[0].generate_code(recursion_depth + 1)
        if self.next_block:
            code_lines.append(self.next_block.generate_code(recursion_depth))
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


class ConditionBlock(ControlBlock):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.initConditionUI()

    def initConditionUI(self):
        self.initUI()
        self.notch_size = 5
        self.tab_width = 20
        self.tab_height = 10

        # Add changeable text field (QLineEdit)
        self.text_field = QLineEdit()
        self.text_field.setFont(QFont('Arial', 10))
        self.text_field.setFixedWidth(50)

        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field)
        text_rect = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setParentItem(self)
        self.text_field_proxy.setPos(
            (self.width - text_rect.width()) / 10, (text_rect.height()) / 2)

        # Add combo box
        self.combo_box = QComboBox()
        self.combo_box.addItems(['==', '!=', '>', '>=', '<', '<='])
        self.combo_box.setFont(QFont('Arial', 10))

        self.combo_box_proxy = QGraphicsProxyWidget(self)
        self.combo_box_proxy.setWidget(self.combo_box)
        text_rect = self.combo_box_proxy.boundingRect()
        self.combo_box_proxy.setParentItem(self)
        self.combo_box_proxy.setPos(
            (self.width - text_rect.width()) / 2, (text_rect.height()) / 2)
        self.combo_box_proxy.setZValue(2)
        # Add changeable text field (QLineEdit)
        self.text_field2 = QLineEdit()
        self.text_field2.setFont(QFont('Arial', 10))
        self.text_field2.setFixedWidth(50)

        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field2)
        text_rect = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setParentItem(self)
        self.text_field_proxy.setPos(
            (self.width - text_rect.width()) / 10 * 9, (text_rect.height()) / 2)

    def generate_code(self, recursion_depth=0):
        if not is_valid_integer_or_var(self.text_field.text()):
            show_message_box("Условия применимы только для переменных и целых чисел!")
            return None
        if not is_valid_integer_or_var(self.text_field2.text()):
            show_message_box("Условия применимы только для переменных и целых чисел!")
            return None
        program = 'if ({} {} {})'
        program = program.format(self.text_field.text(), self.combo_box.currentText(), self.text_field2.text())
        program += '{\n'
        # for child in self.child_blocks:
        #     program += child.generate_code(recursion_depth + 1)
        if self.child_blocks:
            code = self.child_blocks[0].generate_code(recursion_depth + 1)
            if code is None:
                return None
            program += code
        program += '}\n'
        if self.next_block:
            result = self.next_block.generate_code(recursion_depth)
            if result is None:
                return None
            return program + result
        return program


class ForCycleBlock(ControlBlock):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.initConditionUI()

    def initConditionUI(self):
        self.initUI()
        self.notch_size = 5
        self.tab_width = 20
        self.tab_height = 10
        width = self.width
        height = self.height
        delta = 5

        self.text_item = QGraphicsTextItem("Повтор", self)
        font = QFont('Arial', 14)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos(delta * 1, (text_rect.height()) // 2 - delta * 2)

        # Add changeable text field (QLineEdit)
        self.text_field2 = QLineEdit()
        self.text_field2.setFont(QFont('Arial', 15))
        self.text_field2.setFixedWidth(60)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field2)
        text_rect2 = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setParentItem(self)
        self.text_field_proxy.setPos(
            (delta * 7 + self.width - text_rect2.width()) // 2, (text_rect2.height()) // 2 - delta)

        self.text_item = QGraphicsTextItem("раз", self)
        font = QFont('Arial', 14)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos((delta * 4 + self.width - text_rect.width()) // 2 + text_rect2.width(),
                              (text_rect.height()) // 2 - delta * 2)

    def generate_code(self, recursion_depth=0):

        if not is_valid_integer_or_var(self.text_field2.text()):
            show_message_box("Количеством повторов должно быть ыцелое число или переменная!")
            return None
        program = 'for (int i{} = 0; i{} < {}; ++i{})'
        program = program.format(recursion_depth, recursion_depth, self.text_field2.text(), recursion_depth)
        program += '{\n'
        # for child in self.child_blocks:
        #     program += child.generate_code(recursion_depth + 1)
        if self.child_blocks:
            code = self.child_blocks[0].generate_code(recursion_depth + 1)
            if code is None:
                return None
            program += code
        program += '}\n'
        if self.next_block:
            result = self.next_block.generate_code(recursion_depth)
            if result is None:
                return None
            return program + result
        return program


class WhileCycleBlock(ControlBlock):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.initConditionUI()

    def initConditionUI(self):
        self.initUI()
        self.notch_size = 5
        self.tab_width = 20
        self.tab_height = 10

        # Add changeable text field (QLineEdit)
        self.text_field = QLineEdit()
        self.text_field.setFont(QFont('Arial', 10))
        self.text_field.setFixedWidth(50)

        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field)
        text_rect = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setParentItem(self)
        self.text_field_proxy.setPos(
            (self.width - text_rect.width()) / 10, (text_rect.height()) / 2)

        # Add combo box
        self.combo_box = QComboBox()
        self.combo_box.addItems(['==', '!=', '>', '>=', '<', '<='])
        self.combo_box.setFont(QFont('Arial', 10))

        self.combo_box_proxy = QGraphicsProxyWidget(self)
        self.combo_box_proxy.setWidget(self.combo_box)
        text_rect = self.combo_box_proxy.boundingRect()
        self.combo_box_proxy.setParentItem(self)
        self.combo_box_proxy.setPos(
            (self.width - text_rect.width()) / 2, (text_rect.height()) / 2)
        self.combo_box_proxy.setZValue(2)

        # Add changeable text field (QLineEdit)
        self.text_field2 = QLineEdit()
        self.text_field2.setFont(QFont('Arial', 10))
        self.text_field2.setFixedWidth(50)

        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field2)
        text_rect = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setParentItem(self)
        self.text_field_proxy.setPos(
            (self.width - text_rect.width()) / 10 * 9, (text_rect.height()) / 2)

    def generate_code(self, recursion_depth=0):

        if not is_valid_integer_or_var(self.text_field.text()):
            show_message_box("Циклы с условием применимы только для переменных и целых чисел!")
            return None
        if not is_valid_integer_or_var(self.text_field2.text()):
            show_message_box("Циклы с условием применимы только для переменных и целых чисел!")
            return None
        program = 'while ({} {} {})'
        program = program.format(self.text_field.text(), self.combo_box.currentText(), self.text_field2.text())
        program += '{'
        # for child in self.child_blocks:
        #     program += child.generate_code(recursion_depth + 1)
        if self.child_blocks:
            code = self.child_blocks[0].generate_code(recursion_depth + 1)
            if code is None:
                return None
            program += code
        program += '}'
        if self.next_block:
            result = self.next_block.generate_code(recursion_depth)
            if result is None:
                return None
            return program + result
        return program


class DigitalReadBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.child_blocks = []
        # self.width = 120
        self.setZValue(1)  # Control blocks are below child blocks
        self.initUI()

    def initUI(self):
        super().initUI()
        width = self.width
        height = self.height
        delta = 5

        #
        self.text_field1 = QLineEdit()
        self.text_field1.setFont(QFont('Arial', 16))
        self.text_field1.setFixedWidth(30)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field1)
        self.text_field_proxy.setParentItem(self)
        text_rect = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos((self.width - text_rect.width()) / 10, (height - text_rect.height()) / 2)

        # Add text
        self.text_item = QGraphicsTextItem("=ЦЧтение", self)
        font = QFont('Arial', 10)
        self.text_item.setFont(font)
        text_rect_1 = self.text_item.boundingRect()
        self.text_item.setPos(delta * 3 + text_rect.width(), (height - text_rect_1.height()) / 2)

        #
        self.text_field2 = QLineEdit()
        self.text_field2.setFont(QFont('Arial', 16))
        self.text_field2.setFixedWidth(30)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field2)
        self.text_field_proxy.setParentItem(self)
        text_rect_2 = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos((self.width - text_rect.width()) / 10 * 9,
                                     (self.height - text_rect_2.height()) / 2)

    def generate_code(self, recursion_depth=0):
        if self.text_field1.text() not in declared_variables:
            show_message_box("Необходимо указать корректную переменную для записи результата цифрового чтения!")
            return None
        if not is_valid_analog_pin(self.text_field2.text()):
            show_message_box("Необходимо указать корректный цифровой пин для чтения!")
            return None
        program = "{} = digitalRead({})"
        program = program.format(self.text_field1.text(), self.text_field2.text())
        if self.next_block:
            result = self.next_block.generate_code(recursion_depth)
            if result is None:
                return None
            return program + result
        return program


class AnalogReadBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.child_blocks = []
        # self.width = 120
        self.setZValue(1)  # Control blocks are below child blocks
        self.initUI()

    def initUI(self):
        super().initUI()
        width = self.width
        height = self.height
        delta = 5

        #
        self.text_field1 = QLineEdit()
        self.text_field1.setFont(QFont('Arial', 16))
        self.text_field1.setFixedWidth(30)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field1)
        self.text_field_proxy.setParentItem(self)
        text_rect = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos((self.width - text_rect.width()) / 10, (height - text_rect.height()) / 2)

        # Add text
        self.text_item = QGraphicsTextItem("=АЧтение", self)
        font = QFont('Arial', 10)
        self.text_item.setFont(font)
        text_rect_1 = self.text_item.boundingRect()
        self.text_item.setPos(delta * 3 + text_rect.width(), (height - text_rect_1.height()) / 2)

        #
        self.text_field2 = QLineEdit()
        self.text_field2.setFont(QFont('Arial', 16))
        self.text_field2.setFixedWidth(30)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field2)
        self.text_field_proxy.setParentItem(self)
        text_rect_2 = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos((self.width - text_rect.width()) / 10 * 9,
                                     (self.height - text_rect_2.height()) / 2)

    def generate_code(self, recursion_depth=0):
        if self.text_field1.text() not in declared_variables:
            show_message_box("Необходимо указать корректную переменную для записи результата аналогового чтения!")
            return None
        if not is_valid_analog_pin(self.text_field2.text()):
            show_message_box("Необходимо указать корректный аналоговый пин для чтения!")
            return None
        program = "{} = analogRead({})"
        program = program.format(self.text_field1.text(), self.text_field2.text())
        if self.next_block:
            result = self.next_block.generate_code(recursion_depth)
            if result is None:
                return None
            return program + result
        return program


class DigitalWriteBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.child_blocks = []
        # self.width = 120
        self.setZValue(1)  # Control blocks are below child blocks
        self.initUI()

    def initUI(self):
        super().initUI()
        width = self.width
        height = self.height
        delta = 5

        # Add text
        self.text_item = QGraphicsTextItem("ЦЗапись", self)
        font = QFont('Arial', 10)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos(delta * 2, (height - text_rect.height()) / 2)

        #
        self.text_field = QLineEdit()
        self.text_field.setFont(QFont('Arial', 10))
        self.text_field.setFixedWidth(30)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field)
        self.text_field_proxy.setParentItem(self)
        text_rect_2 = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos(int(delta * 2 + text_rect.width()), (self.height - text_rect_2.height()) / 2)

        # Add combo box
        self.combo_box = QComboBox()
        self.combo_box.addItems(['LOW', 'HIGH'])
        self.combo_box.setFont(QFont('Arial', 8))
        self.combo_box_proxy = QGraphicsProxyWidget(self)
        self.combo_box_proxy.setWidget(self.combo_box)
        text_rect_3 = self.combo_box_proxy.boundingRect()
        self.combo_box_proxy.setParentItem(self)
        self.combo_box_proxy.setPos(delta * 2 + text_rect.width() + delta + text_rect_2.width() + delta,
                                    (self.height - text_rect_2.height()) / 2)

    def generate_code(self, recursion_depth=0):
        program = super().generate_code(recursion_depth)
        program = program.format(self.text_field.text(), self.combo_box.currentText())
        if self.next_block:
            result = self.next_block.generate_code(recursion_depth)
            if result is None:
                return None
            return program + result
        return program


class AnalogWriteBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.child_blocks = []
        # self.width = 120
        self.setZValue(1)  # Control blocks are below child blocks
        self.initUI()

    def initUI(self):
        super().initUI()
        width = self.width
        height = self.height
        delta = 5

        # Add text
        self.text_item = QGraphicsTextItem("АЗапись", self)
        font = QFont('Arial', 10)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos(delta * 2, (height - text_rect.height()) / 2)

        #
        self.text_field1 = QLineEdit()
        self.text_field1.setFont(QFont('Arial', 10))
        self.text_field1.setFixedWidth(30)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field1)
        self.text_field_proxy.setParentItem(self)
        text_rect_2 = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos(int(delta * 2 + text_rect.width()), (self.height - text_rect_2.height()) / 2)

        # Add combo box
        self.text_field2 = QLineEdit()
        self.text_field2.setFont(QFont('Arial', 10))
        self.text_field2.setFixedWidth(30)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field2)
        self.text_field_proxy.setParentItem(self)
        text_rect_3 = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos(delta * 2 + text_rect.width() + delta + text_rect_2.width() + delta,
                                     (self.height - text_rect_2.height()) / 2)

    def generate_code(self, recursion_depth=0):
        program = super().generate_code(recursion_depth)
        program = program.format(self.text_field1.text(), self.text_field2.text())
        if self.next_block:
            result = self.next_block.generate_code(recursion_depth)
            if result is None:
                return None
            return program + result
        return program


class SerialReadBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.child_blocks = []
        # self.width = 120
        self.setZValue(1)  # Control blocks are below child blocks
        self.initUI()

    def initUI(self):
        super().initUI()
        width = self.width
        height = self.height
        delta = 5

        #
        self.text_field = QLineEdit()
        self.text_field.setFont(QFont('Arial', 10))
        self.text_field.setFixedWidth(30)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field)
        self.text_field_proxy.setParentItem(self)
        text_rect = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos((width - text_rect.width()) / 15, (height - text_rect.height()) / 2)

        # Add text
        self.text_item = QGraphicsTextItem("=", self)
        font = QFont('Arial', 10)
        self.text_item.setFont(font)
        text_rect_1 = self.text_item.boundingRect()
        self.text_item.setPos((width - text_rect_1.width()) / 15 * 4, (height - text_rect_1.height()) / 2)
        # Add text
        self.text_item = QGraphicsTextItem("Слушай", self)
        font = QFont('Arial', 10)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos((width - text_rect.width()) / 10 * 8, (height - text_rect.height()) / 2)

    def generate_code(self, recursion_depth=0):
        if self.text_field.text() not in declared_variables:
            show_message_box("Необходимо указать корректную переменную для записи результата чтения серильного порта!")
            return None
        program = "{} = Serial.read();"
        program = program.format(self.text_field.text())
        if self.next_block:
            result = self.next_block.generate_code(recursion_depth)
            if result is None:
                return None
            return program + result
        return program


class SerialWriteBlock(Block):
    def __init__(self, text, color, parent=None):
        super().__init__(text, color, parent)
        self.child_blocks = []
        # self.width = 120
        self.setZValue(1)  # Control blocks are below child blocks
        self.initUI()

    def initUI(self):
        super().initUI()
        width = self.width
        height = self.height
        delta = 5

        # Add text
        self.text_item = QGraphicsTextItem("Говори", self)
        font = QFont('Arial', 10)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos(delta * 2, (height - text_rect.height()) / 2)

        #
        self.text_field = QLineEdit()
        self.text_field.setFont(QFont('Arial', 10))
        self.text_field.setFixedWidth(50)
        self.text_field_proxy = QGraphicsProxyWidget(self)
        self.text_field_proxy.setWidget(self.text_field)
        self.text_field_proxy.setParentItem(self)
        text_rect_2 = self.text_field_proxy.boundingRect()
        self.text_field_proxy.setPos(int(delta * 2 + text_rect.width()), (self.height - text_rect_2.height()) / 2)

    def generate_code(self, recursion_depth=0):
        if not is_valid_integer_or_var(self.text_field.text()):
            show_message_box("Записать в последовательный порт можно только число или значение переменной!")
            return None
        program = f"Serial.print({self.text_field.text()});"
        if self.next_block:
            result = self.next_block.generate_code(recursion_depth)
            if result is None:
                return None
            return program + result
        return program


class Workspace(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(0, 0, 800, 600)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self._pan = False
        self._last_pan_point = QPointF()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected_items = self.scene().selectedItems()
            for item in selected_items:
                if isinstance(item, Block) or isinstance(item, ControlBlock):
                    # Remove the item from the scene
                    item.suicide()
            event.accept()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._last_pan_point = event.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pan:
            delta = self.mapToScene(event.pos()) - self.mapToScene(self._last_pan_point)
            self._last_pan_point = event.pos()
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
            self.translate(-delta.x(), -delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class BlockPalette(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.parent = parent
        blocks = ['Начало', 'Переменные', 'Арифметика', 'Сон', 'Условие', 'Повтор', 'Цикл', 'ЦЧтение', 'АЧтение',
                  'ЦЗапись',
                  'АЗапись', 'Слушай', 'Говори']
        colors = [
            QColor('#ff3386'),
            QColor('#FF5733'),
            QColor('#00FFFF'),
            QColor('#FF00FF'),
            QColor('#33FF57'),
            QColor('#3357FF'),
            QColor('#F1C40F'),
            QColor('#9B59B6'),
            QColor('#FF69B4'),
            QColor('#8B00FF'),
            QColor('#BFFF00'),
            QColor('#40E0D0'),
            QColor('#FFD701')
        ]

        for text, color in zip(blocks, colors):
            button = QPushButton(text)
            button.setStyleSheet(
                f'background-color: {color.name()}; color: white; font-weight: bold;')
            button.clicked.connect(
                lambda checked, t=text, c=color: self.add_block_to_workspace(t, c))
            layout.addWidget(button)

    def add_block_to_workspace(self, text, color):
        if text == 'Повтор':
            block = ForCycleBlock(text, color)
        elif text == 'Цикл':
            block = WhileCycleBlock(text, color)
        elif text == 'Начало':
            block = StartBlock(text, color)
        elif text == 'Арифметика':
            block = ArithmeticBlock(text, color)
        elif text == 'Сон':
            block = DelayBlock(text, color)
        elif text == 'Условие':
            block = ConditionBlock(text, color)
        elif text == 'Переменные':
            block = VariableBlock(text, color)
        elif text == 'ЦЧтение':
            block = DigitalReadBlock(text, color)
        elif text == 'АЧтение':
            block = AnalogReadBlock(text, color)
        elif text == 'ЦЗапись':
            block = DigitalWriteBlock(text, color)
        elif text == 'АЗапись':
            block = AnalogWriteBlock(text, color)
        elif text == 'Слушай':
            block = SerialReadBlock(text, color)
        elif text == 'Говори':
            block = SerialWriteBlock(text, color)
        self.parent.workspace.scene().addItem(block)
        block.setPos(100, 100)


class PinConfigurationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pin_comboboxes = {}
        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('<h2>ПИНы</h2>'))

        # Scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        for pin_number in PINS:
            h_layout = QHBoxLayout()
            label = QLabel(f"Pin{pin_number}")
            combobox = QComboBox()
            combobox.addItems(["ВВОД", "ВЫВОД"])
            self.pin_comboboxes[pin_number] = combobox
            h_layout.addWidget(label)
            h_layout.addWidget(combobox)
            scroll_layout.addLayout(h_layout)

        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)

        scroll_area.setFixedWidth(200)

        layout.addWidget(scroll_area)
        self.setLayout(layout)

    def get_pin_configurations(self):
        pin_numbers = sorted(self.pin_comboboxes.keys())
        pin_configs = [self.pin_comboboxes[pin].currentText() for pin in pin_numbers]
        return pin_configs


class SerialReaderWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial_port = None
        self.init_ui()
        self.setup_timer()

    def init_ui(self):
        # Основные макеты
        main_layout = QVBoxLayout()
        port_layout = QHBoxLayout()
        send_layout = QHBoxLayout()

        # Выбор последовательного порта
        self.port_label = QLabel("Последовательный порт:")
        self.port_combo = QComboBox()
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.clicked.connect(self.refresh_serial_ports)
        self.connect_button = QPushButton("Подключиться")
        self.connect_button.clicked.connect(self.toggle_connection)

        # Добавление элементов в портовый макет
        port_layout.addWidget(self.port_label)
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(self.refresh_button)
        port_layout.addWidget(self.connect_button)

        # Текстовая область для отображения полученных данных
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlaceholderText("Полученные данные будут отображаться здесь...")

        # Поле ввода и кнопка для отправки данных
        self.send_input = QLineEdit()
        self.send_input.setPlaceholderText("Введите данные для отправки...")
        self.send_input.returnPressed.connect(self.send_serial_data)  # Отправка при нажатии Enter

        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send_serial_data)
        self.send_button.setEnabled(False)  # Отключена до подключения

        # Добавление элементов в отправочный макет
        send_layout.addWidget(self.send_input)
        send_layout.addWidget(self.send_button)

        # Добавление всех макетов в основной макет
        main_layout.addLayout(port_layout)
        main_layout.addWidget(self.text_area)
        main_layout.addLayout(send_layout)

        self.setLayout(main_layout)
        self.setWindowTitle("Serial Reader Widget")
        self.resize(600, 400)

        # Инициальное обновление списка портов
        self.refresh_serial_ports()

    def setup_timer(self):
        """Настройка таймера для периодического чтения данных из порта."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.read_serial_data)
        self.timer.start(1000)  # Проверка каждые 1 секунду

    def refresh_serial_ports(self):
        """Обновление списка доступных последовательных портов."""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)

        if not ports:
            self.port_combo.addItem("Порты не найдены")
            self.connect_button.setEnabled(False)
            self.send_button.setEnabled(False)
            QMessageBox.warning(self, "Порты не найдены", "Доступные последовательные порты не обнаружены.")
        else:
            self.connect_button.setEnabled(True)

    def toggle_connection(self):
        """Переключение состояния подключения."""
        if self.serial_port and self.serial_port.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        """Подключение к выбранному последовательному порту."""
        selected_port = self.port_combo.currentText()
        if selected_port == "Порты не найдены":
            QMessageBox.warning(self, "Ошибка подключения", "Доступные последовательные порты не найдены.")
            return
        try:
            self.serial_port = serial.Serial(
                port=selected_port,
                baudrate=9600,  # Настройте скорость передачи по необходимости
                timeout=1,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            if self.serial_port.is_open:
                self.connect_button.setText("Отключиться")
                self.send_button.setEnabled(True)
                self.text_area.append(f"Подключено к {selected_port}\n")
        except serial.SerialException as e:
            QMessageBox.critical(self, "Ошибка подключения",
                                 f"Не удалось подключиться к {selected_port}.\n\nОшибка: {e}")
            self.connect_button.setEnabled(False)
            self.send_button.setEnabled(False)
            self.serial_port = None

    def disconnect_serial(self):
        """Отключение от последовательного порта."""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.connect_button.setText("Подключиться")
            self.send_button.setEnabled(False)
            self.text_area.append("Отключено от последовательного порта.\n")

    def read_serial_data(self):
        """Чтение данных из последовательного порта и отображение их в текстовой области."""
        if self.serial_port and self.serial_port.is_open:
            try:
                # if self.serial_port.in_waiting or True:
                data = self.serial_port.read_all().decode('ascii', errors='replace').strip()
                if data:
                    self.text_area.append(data)
                    # Автопрокрутка вниз
                    self.text_area.verticalScrollBar().setValue(
                        self.text_area.verticalScrollBar().maximum()
                    )
            except serial.SerialException as e:
                self.text_area.append(f"Ошибка последовательного порта: {e}\n")
                QMessageBox.critical(self, "Ошибка последовательного порта",
                                     f"Произошла ошибка при чтении данных.\n\nОшибка: {e}")
                self.disconnect_serial()
            except Exception as e:
                self.text_area.append(f"Неожиданная ошибка: {e}\n")
                QMessageBox.critical(self, "Неожиданная ошибка", f"Произошла неожиданная ошибка.\n\nОшибка: {e}")

    def send_serial_data(self):
        """Отправка данных через последовательный порт."""
        if self.serial_port and self.serial_port.is_open:
            data = self.send_input.text()
            if data:
                try:
                    # Добавляем символ перевода строки, если требуется
                    self.serial_port.write((data + '\n').encode('utf-8'))
                    self.text_area.append(f"Отправлено: {data}")
                    self.send_input.clear()
                except serial.SerialException as e:
                    self.text_area.append(f"Ошибка отправки данных: {e}\n")
                    QMessageBox.critical(self, "Ошибка отправки", f"Не удалось отправить данные.\n\nОшибка: {e}")
                    self.disconnect_serial()
                except Exception as e:
                    self.text_area.append(f"Неожиданная ошибка при отправке данных: {e}\n")
                    QMessageBox.critical(self, "Неожиданная ошибка",
                                         f"Произошла неожиданная ошибка при отправке данных.\n\nОшибка: {e}")
        else:
            QMessageBox.warning(self, "Не подключено",
                                "Пожалуйста, подключитесь к последовательному порту перед отправкой данных.")

    def closeEvent(self, event):
        """Корректное закрытие соединения при закрытии виджета."""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        event.accept()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Rudiron visual programming')
        self.setWindowIcon(QIcon('ico.png'))
        self.setGeometry(100, 100, 1000, 600)
        self.setupUI()

    def setupUI(self):
        # Основной вертикальный макет
        main_layout = QVBoxLayout(self)

        # Верхний горизонтальный макет для существующих компонентов
        top_layout = QHBoxLayout()

        # Block Palette
        self.palette = BlockPalette(self)

        # Workspace
        self.workspace = Workspace(self)

        # Run Button
        self.run_button = QPushButton('Запуск')
        self.run_button.setStyleSheet('font-size: 16px; height: 40px;')
        self.run_button.clicked.connect(self.run_program)

        # Размещение элементов слева
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel('<h2>Блоки</h2>'))
        left_layout.addWidget(self.palette)
        left_layout.addStretch()
        left_layout.addWidget(self.run_button)

        # Pin Configuration Widget
        self.pin_config_widget = PinConfigurationWidget()

        # Добавление в верхний горизонтальный макет
        top_layout.addLayout(left_layout)
        top_layout.addWidget(self.workspace)
        top_layout.addWidget(self.pin_config_widget)

        # Добавление верхнего макета в основной вертикальный макет
        main_layout.addLayout(top_layout)

        # Создание и добавление SerialReaderWidget в нижнюю часть
        self.serial_reader = SerialReaderWidget(self)
        main_layout.addWidget(self.serial_reader)

        self.setLayout(main_layout)

    def run_program(self):
        try:
            global declared_variables
            declared_variables = set()
            # Find all top-level blocks
            block = [item for item in self.workspace.scene().items()
                     if isinstance(item, StartBlock)]
            # Sort blocks by their vertical position
            if len(block) == 0:
                QMessageBox.information(self, "Program", f"Для запуска программы необходим блок 'Начало'")
                return
            self.serial_reader.disconnect_serial()
            reset_arduino(self.serial_reader.port_combo.currentText())
            rudiron_code = block[0].generate_code()
            # Display or execute the code
            if rudiron_code is None:
                return

            # Get the pin configurations
            pin_configs = self.pin_config_widget.get_pin_configurations()
            pin_numbers = sorted(self.pin_config_widget.pin_comboboxes.keys())
            pin_init = ""
            for pin, config in zip(pin_numbers, pin_configs):
                pin_init += f"pinMode({pin}, {config});\n"
            QMessageBox.information(
                self, "Program", f"Ваша программа успешно сгенерированна!")
            rendered_rudiron_code = "void setup(){"
            rendered_rudiron_code += "Serial.begin(9600);"
            rendered_rudiron_code += "delay(10);"
            for i in PINS:
                rendered_rudiron_code += f"pinMode({i}, {self.pin_config_widget.pin_comboboxes[i].currentText()});\n"
            rendered_rudiron_code += rudiron_code
            rendered_rudiron_code += "}"
            rendered_rudiron_code += "void loop(){}"
            print(rendered_rudiron_code)
            if not os.path.isdir("temp"):
                os.mkdir("temp")
            with open(os.path.abspath(os.curdir) + "\\temp\\temp.ino", "w") as file:
                file.write(rendered_rudiron_code)
            upload_to_board(self.serial_reader.port_combo.currentText())
            self.serial_reader.connect_serial()
        except:
            pass


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
