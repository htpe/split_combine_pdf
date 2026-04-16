import io
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGridLayout, QScrollArea,
    QLineEdit, QFrame, QSpinBox, QComboBox, QFileDialog, QMenu,
    QDialog, QListView, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QSize, QEvent, QUrl, QByteArray
from PyQt6.QtGui import QDrag, QPixmap, QColor, QTransform, QIcon, QDesktopServices
from PyQt6.QtCore import QPoint


class DragHandleLabel(QLabel):
    """Small drag handle that reorders items in a QListWidget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._list_widget = None
        self._list_item = None
        self._start_pos = None

        self.setText("⋮⋮")
        self.setToolTip("Drag to reorder PDFs")
        self.setStyleSheet("color: #6b7280; padding: 0 6px; font-size: 16px;")

    def set_drag_context(self, list_widget: QListWidget, list_item: QListWidgetItem):
        self._list_widget = list_widget
        self._list_item = list_item

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.position().toPoint()
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return super().mouseMoveEvent(event)
        if self._start_pos is None or self._list_widget is None or self._list_item is None:
            return super().mouseMoveEvent(event)

        if (event.position().toPoint() - self._start_pos).manhattanLength() < QApplication.startDragDistance():
            return super().mouseMoveEvent(event)

        row = self._list_widget.row(self._list_item)
        if row < 0:
            return

        self._list_widget.setCurrentItem(self._list_item)

        mime = QMimeData()
        mime.setData(PDFFileListWidget.MIME_TYPE, QByteArray(str(row).encode("utf-8")))

        drag = QDrag(self._list_widget)
        drag.setMimeData(mime)

        # Visual feedback
        try:
            parent = self.parentWidget() or self
            drag.setPixmap(parent.grab())
        except Exception:
            pass

        drag.exec(Qt.DropAction.MoveAction)


class PDFFileListWidget(QListWidget):
    """List widget that supports internal reordering via a custom drag mime type."""

    MIME_TYPE = "application/x-combinepdf-file-row"
    order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)

    def dropEvent(self, event):
        if event.source() is self and event.mimeData().hasFormat(self.MIME_TYPE):
            try:
                source_row = int(bytes(event.mimeData().data(self.MIME_TYPE)).decode("utf-8"))
            except Exception:
                return super().dropEvent(event)

            drop_row = self.indexAt(event.position().toPoint()).row()
            if drop_row < 0:
                drop_row = self.count()  # append

            if source_row < 0 or source_row >= self.count():
                return

            if drop_row > source_row:
                drop_row -= 1

            if drop_row == source_row:
                event.acceptProposedAction()
                return

            item = self.item(source_row)
            widget = self.itemWidget(item)

            taken = self.takeItem(source_row)
            if taken is None:
                return

            self.insertItem(drop_row, taken)
            if widget is not None:
                taken.setSizeHint(widget.sizeHint())
                self.setItemWidget(taken, widget)

            event.acceptProposedAction()
            self.order_changed.emit()
            return

        super().dropEvent(event)


class PagePreviewWidget(QWidget):
    """Grid of page thumbnails with drag support."""
    page_dragged = pyqtSignal(int, object)  # page_num, source_widget
    page_rotated = pyqtSignal(int, int)  # page_num, new_rotation_degrees
    
    def __init__(self):
        super().__init__()
        self.pages = {}
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        self.grid_widget = QWidget()
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setSpacing(5)
        scroll.setWidget(self.grid_widget)
        
        layout.addWidget(QLabel("Available Pages:"))
        layout.addWidget(scroll)
        self.setLayout(layout)
    
    def add_page(self, page_obj):
        """Add a page thumbnail to the grid."""
        btn = QPushButton()
        if page_obj.thumbnail:
            pixmap = QPixmap.fromImage(page_obj.thumbnail)
            btn.setIcon(pixmap)
            btn.setIconSize(QSize(150, 200))
        else:
            btn.setText(f"Page {page_obj.page_num + 1}")
        
        btn.setMinimumSize(160, 210)
        btn.setCursor(Qt.CursorShape.OpenHandCursor)
        btn.page_num = page_obj.page_num
        btn.installEventFilter(self)
        
        # Store reference
        self.pages[page_obj.page_num] = btn
        
        row = page_obj.page_num // 4
        col = page_obj.page_num % 4
        self.grid.addWidget(btn, row, col)
    
    def eventFilter(self, obj, event):
        """Intercept mouse press on page buttons to start drag or show context menu."""
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and isinstance(obj, QPushButton)
            and hasattr(obj, 'page_num')
        ):
            if event.button() == Qt.MouseButton.RightButton:
                self.show_page_context_menu(obj, event.globalPosition().toPoint())
                return True
            if event.button() == Qt.MouseButton.LeftButton:
                self.perform_drag(obj, obj.page_num)
                return True
        return super().eventFilter(obj, event)

    def show_page_context_menu(self, btn, global_pos):
        """Show right-click context menu with rotation options."""
        menu = QMenu(self)
        cw_action = menu.addAction("Rotate CW 90°")
        ccw_action = menu.addAction("Rotate CCW 90°")
        action = menu.exec(global_pos)
        if action == cw_action:
            self._rotate_page_btn(btn, 90)
        elif action == ccw_action:
            self._rotate_page_btn(btn, -90)

    def _rotate_page_btn(self, btn, delta):
        """Rotate the thumbnail pixmap and emit page_rotated signal."""
        current = getattr(btn, 'rotation', 0)
        new_rotation = (current + delta) % 360
        btn.rotation = new_rotation
        icon = btn.icon()
        if not icon.isNull():
            pixmap = icon.pixmap(btn.iconSize())
            transform = QTransform().rotate(delta)
            rotated = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            btn.setIcon(QIcon(rotated))
        self.page_rotated.emit(btn.page_num, new_rotation)
    
    def perform_drag(self, source_btn, page_num):
        """Start drag operation for page."""
        drag = QDrag(source_btn)
        mime = QMimeData()
        mime.setText(f"page:{page_num}")
        drag.setMimeData(mime)
        
        # Use button's current rendered appearance as drag pixmap
        pixmap = source_btn.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        
        drag.exec(Qt.DropAction.MoveAction)

class SplitGroupPageList(QListWidget):
    """A page list that supports both external page drops and internal reordering."""

    page_dropped = pyqtSignal(int)  # page_num (0-indexed)
    order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)

        # Emits whenever rows move (drag reorder)
        self.model().rowsMoved.connect(lambda *_: self.order_changed.emit())

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("page:"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("page:"):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        # Internal reorder
        if event.source() is self:
            super().dropEvent(event)
            return

        # External drop from preview (mime: "page:<num>")
        if event.mimeData().hasText() and event.mimeData().text().startswith("page:"):
            try:
                page_num = int(event.mimeData().text().split(":", 1)[1])
                self.page_dropped.emit(page_num)
                event.acceptProposedAction()
            except Exception:
                event.ignore()
            return

        super().dropEvent(event)


class OrderablePageList(QListWidget):
    """Simple list widget that supports internal drag-reordering."""

    order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.model().rowsMoved.connect(lambda *_: self.order_changed.emit())


class SplitGroupPanel(QWidget):
    """Panel for managing individual split groups."""

    remove_requested = pyqtSignal(str)  # split_name
    rename_requested = pyqtSignal(str, str)  # old_name, new_name
    pages_changed = pyqtSignal()

    def __init__(self, split_name: str):
        super().__init__()
        self.split_name = split_name
        self.pages = []
        self.init_ui()
        self.setAcceptDrops(True)

    def init_ui(self):
        layout = QVBoxLayout()

        # Header with name and buttons
        header = QHBoxLayout()
        self.name_label = QLineEdit(self.split_name)
        self.name_label.setMaximumWidth(150)
        header.addWidget(QLabel("Split:"))
        header.addWidget(self.name_label)

        rename_btn = QPushButton("Rename")
        rename_btn.clicked.connect(self.on_rename)
        header.addWidget(rename_btn)

        auto_order_btn = QPushButton("Auto order")
        auto_order_btn.setToolTip("Sort pages in this split group by page number")
        auto_order_btn.clicked.connect(self.on_auto_order)
        header.addWidget(auto_order_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setStyleSheet("background-color: #ffcccc;")
        remove_btn.clicked.connect(self.on_remove)
        header.addWidget(remove_btn)
        header.addStretch()

        layout.addLayout(header)

        # Page list (drag to reorder)
        self.page_list = SplitGroupPageList()
        self.page_list.setMaximumHeight(120)
        self.page_list.page_dropped.connect(self.on_page_dropped)
        self.page_list.order_changed.connect(self.on_order_changed)
        layout.addWidget(self.page_list)

        # Info
        self.info_label = QLabel("0 pages")
        layout.addWidget(self.info_label)

        self.setLayout(layout)

    def add_page(self, page_obj):
        """Add page to this split."""
        if page_obj.page_num not in [p.page_num for p in self.pages]:
            self.pages.append(page_obj)
            item = QListWidgetItem(f"Page {page_obj.page_num + 1}")
            item.setData(Qt.ItemDataRole.UserRole, page_obj.page_num)
            self.page_list.addItem(item)
            self.update_info()
            self.pages_changed.emit()

    def remove_page(self, page_num):
        """Remove page from this split."""
        self.pages = [p for p in self.pages if p.page_num != page_num]
        for i in range(self.page_list.count()):
            item = self.page_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == page_num:
                self.page_list.takeItem(i)
                break
        self.update_info()
        self.pages_changed.emit()

    def update_info(self):
        """Update page count display."""
        count = len(self.pages)
        page_nums = [p.page_num + 1 for p in self.pages]
        self.info_label.setText(f"{count} page(s): {page_nums}")

    def on_page_dropped(self, page_num: int):
        """Handle external page drop onto the list."""
        try:
            from models.pdf_model import PDFPage
            self.add_page(PDFPage(page_num=page_num))
        except Exception:
            return

    def on_order_changed(self):
        """Sync underlying page order from visual list order."""
        self._sync_pages_from_list()
        self.update_info()
        self.pages_changed.emit()

    def _sync_pages_from_list(self):
        page_by_num = {p.page_num: p for p in self.pages}
        ordered = []
        for i in range(self.page_list.count()):
            item = self.page_list.item(i)
            page_num = item.data(Qt.ItemDataRole.UserRole)
            if page_num in page_by_num:
                ordered.append(page_by_num[page_num])
        remaining = [p for p in self.pages if p.page_num not in {p.page_num for p in ordered}]
        self.pages = ordered + remaining

    def on_auto_order(self):
        """Sort pages by page number ascending (1..N)."""
        self.pages.sort(key=lambda p: p.page_num)
        self.page_list.clear()
        for page_obj in self.pages:
            item = QListWidgetItem(f"Page {page_obj.page_num + 1}")
            item.setData(Qt.ItemDataRole.UserRole, page_obj.page_num)
            self.page_list.addItem(item)
        self.update_info()
        self.pages_changed.emit()

    def on_rename(self):
        """Rename this split."""
        new_name = self.name_label.text().strip()
        if new_name and new_name != self.split_name:
            self.rename_requested.emit(self.split_name, new_name)
            self.split_name = new_name

    def on_remove(self):
        """Request removal of this split."""
        self.remove_requested.emit(self.split_name)

    def dragEnterEvent(self, event):
        """Accept drag if it's a page (drop anywhere on panel)."""
        if event.mimeData().hasText() and event.mimeData().text().startswith("page:"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        """Handle drop of page onto the panel (outside the list)."""
        if event.mimeData().hasText() and event.mimeData().text().startswith("page:"):
            try:
                page_num = int(event.mimeData().text().split(":", 1)[1])
                self.on_page_dropped(page_num)
                event.acceptProposedAction()
            except Exception:
                event.ignore()
            return
        super().dropEvent(event)

class PageIndexSplitWidget(QWidget):
    """Widget for splitting PDF by page indices."""
    splits_created = pyqtSignal(dict)  # {split_name: [page_nums]}
    
    def __init__(self, total_pages: int):
        super().__init__()
        self.total_pages = total_pages
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Split by Page Index:"))
        
        # Mode selection
        mode_layout = QHBoxLayout()
        self.mode_combo = QLineEdit()
        self.mode_combo.setPlaceholderText("Enter: '1-5, 6-10, 11-20' or '5' (pages per split) or '10,20,30' (split at page)")
        self.mode_combo.setToolTip(
            "Formats:\n"
            "• Page ranges: 1-5, 6-10, 11-20\n"
            "• Fixed size: 5 (split every 5 pages)\n"
            "• Split points: 10,20,30 (split at these pages)"
        )
        mode_layout.addWidget(self.mode_combo)
        
        apply_btn = QPushButton("Apply Split")
        apply_btn.clicked.connect(self.apply_split)
        mode_layout.addWidget(apply_btn)
        
        layout.addLayout(mode_layout)
        
        # Info label
        self.info_label = QLabel(f"Total pages: {self.total_pages}")
        layout.addWidget(self.info_label)
        
        self.setLayout(layout)
    
    def apply_split(self):
        """Parse and apply splits based on input."""
        text = self.mode_combo.text().strip()
        if not text:
            return
        
        splits_data = self.parse_split_input(text)
        if splits_data:
            self.splits_created.emit(splits_data)
            self.mode_combo.clear()
    
    def parse_split_input(self, text: str) -> dict:
        """
        Parse different split input formats.
        
        Formats:
        - Page ranges: "1-5, 6-10, 11-20"
        - Fixed size: "5" (split every 5 pages)
        - Split points: "10,20,30" (split at these pages)
        """
        try:
            text = text.strip()
            splits = {}
            
            # Check if it's a range format (contains dashes with commas)
            if '-' in text and ',' in text:
                return self._parse_ranges(text)
            
            # Check if it's a single number (fixed size per split)
            elif text.replace(',', '').replace(' ', '').isdigit() and ',' not in text:
                return self._parse_fixed_size(text)
            
            # Check if it's split points (comma-separated numbers without dashes)
            elif ',' in text and '-' not in text:
                return self._parse_split_points(text)
            
            # Try range format anyway
            else:
                return self._parse_ranges(text)
                
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(None, "Invalid Format", f"Error parsing split input: {e}")
            return {}
    
    def _parse_ranges(self, text: str) -> dict:
        """Parse format: '1-5, 6-10, 11-20'"""
        splits = {}
        ranges = [r.strip() for r in text.split(',')]
        
        for i, range_str in enumerate(ranges):
            if '-' not in range_str:
                raise ValueError(f"Invalid range format: {range_str}. Expected 'start-end'")
            
            start, end = range_str.split('-')
            start, end = int(start.strip()), int(end.strip())
            
            if start < 1 or end > self.total_pages or start > end:
                raise ValueError(f"Invalid range: {start}-{end}. Must be 1-{self.total_pages}")
            
            split_name = f"Pages {start}-{end}"
            page_nums = list(range(start - 1, end))  # Convert to 0-indexed
            splits[split_name] = page_nums
        
        return splits
    
    def _parse_fixed_size(self, text: str) -> dict:
        """Parse format: '5' (split every 5 pages)"""
        size = int(text.strip())
        if size <= 0 or size > self.total_pages:
            raise ValueError(f"Split size must be 1-{self.total_pages}")
        
        splits = {}
        for i in range(0, self.total_pages, size):
            end = min(i + size, self.total_pages)
            split_name = f"Pages {i+1}-{end}"
            page_nums = list(range(i, end))
            splits[split_name] = page_nums
        
        return splits
    
    def _parse_split_points(self, text: str) -> dict:
        """Parse format: '10,20,30' (split at these pages)"""
        points = [int(p.strip()) for p in text.split(',')]
        points = sorted(set(points))  # Remove duplicates and sort
        
        # Validate
        for p in points:
            if p < 1 or p > self.total_pages:
                raise ValueError(f"Page {p} is outside valid range 1-{self.total_pages}")
        
        splits = {}
        prev = 1
        
        for point in points:
            if point > prev:
                split_name = f"Pages {prev}-{point-1}"
                page_nums = list(range(prev - 1, point - 1))
                splits[split_name] = page_nums
            prev = point
        
        # Last split from last point to end
        split_name = f"Pages {prev}-{self.total_pages}"
        page_nums = list(range(prev - 1, self.total_pages))
        splits[split_name] = page_nums
        
        return splits

class CombinePreviewDialog(QDialog):
    """Preview and rotate pages for a PDF used in combine flow."""

    def __init__(self, filepath: str, total_pages: int, page_rotations: dict, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.total_pages = total_pages
        self.page_rotations = dict(page_rotations)  # page_num -> degrees
        self.base_pixmaps = {}  # page_num -> base pixmap
        self.init_ui()
        self.load_pages()

    def init_ui(self):
        filename = Path(self.filepath).name
        self.setWindowTitle(f"Preview & Rotate - {filename}")
        self.resize(900, 650)

        layout = QVBoxLayout()

        controls = QHBoxLayout()
        rotate_cw_btn = QPushButton("Rotate CW 90°")
        rotate_cw_btn.clicked.connect(lambda: self.rotate_selected(90))
        controls.addWidget(rotate_cw_btn)

        rotate_ccw_btn = QPushButton("Rotate CCW 90°")
        rotate_ccw_btn.clicked.connect(lambda: self.rotate_selected(-90))
        controls.addWidget(rotate_ccw_btn)

        reset_btn = QPushButton("Reset Rotation")
        reset_btn.clicked.connect(self.reset_selected)
        controls.addWidget(reset_btn)

        controls.addStretch()
        layout.addLayout(controls)

        self.page_list = QListWidget()
        self.page_list.setViewMode(QListView.ViewMode.IconMode)
        self.page_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.page_list.setIconSize(QSize(120, 160))
        self.page_list.setGridSize(QSize(150, 200))
        self.page_list.setSpacing(10)
        layout.addWidget(self.page_list)

        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("Done")
        close_btn.clicked.connect(self.accept)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

        self.setLayout(layout)

    def load_pages(self):
        """Build page thumbnail grid for preview/rotation."""
        from services.pdf_service import PDFService

        self.page_list.clear()
        for page_num in range(self.total_pages):
            item = QListWidgetItem(f"Page {page_num + 1}")
            item.setData(Qt.ItemDataRole.UserRole, page_num)

            thumbnail = PDFService.generate_thumbnail(self.filepath, page_num)
            if thumbnail:
                buf = io.BytesIO()
                thumbnail.save(buf, format='PNG')
                buf.seek(0)

                pixmap = QPixmap()
                pixmap.loadFromData(buf.read())
                self.base_pixmaps[page_num] = pixmap
                self.apply_item_rotation(item, page_num)

            self.page_list.addItem(item)

    def rotate_selected(self, delta: int):
        """Rotate currently selected page by +/- 90 degrees."""
        item = self.page_list.currentItem()
        if not item:
            return

        page_num = item.data(Qt.ItemDataRole.UserRole)
        current = self.page_rotations.get(page_num, 0)
        self.page_rotations[page_num] = (current + delta) % 360
        self.apply_item_rotation(item, page_num)

    def reset_selected(self):
        """Reset currently selected page rotation."""
        item = self.page_list.currentItem()
        if not item:
            return

        page_num = item.data(Qt.ItemDataRole.UserRole)
        self.page_rotations[page_num] = 0
        self.apply_item_rotation(item, page_num)

    def apply_item_rotation(self, item: QListWidgetItem, page_num: int):
        """Apply stored rotation to a page icon."""
        base = self.base_pixmaps.get(page_num)
        if not base:
            return

        angle = self.page_rotations.get(page_num, 0)
        rotated = base.transformed(QTransform().rotate(angle), Qt.TransformationMode.SmoothTransformation)
        item.setIcon(QIcon(rotated))


class PDFFileItemWidget(QWidget):
    """Widget for managing a single PDF file in combine mode."""
    removed = pyqtSignal(str)  # filepath
    pages_changed = pyqtSignal()
    
    def __init__(self, filepath: str, total_pages: int):
        super().__init__()
        self.filepath = filepath
        self.total_pages = total_pages
        self.selected_pages = list(range(0, total_pages))  # Default: all pages
        self.page_rotations = {}  # page_num -> degrees
        self._file_list_widget = None
        self._file_list_item = None
        self.init_ui()

    def attach_drag_context(self, list_widget: QListWidget, list_item: QListWidgetItem):
        """Enable dragging this file widget up/down within the combine panel."""
        self._file_list_widget = list_widget
        self._file_list_item = list_item
        if hasattr(self, "drag_handle") and self.drag_handle:
            self.drag_handle.set_drag_context(list_widget, list_item)
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # File info header
        filename = Path(self.filepath).name
        header = QHBoxLayout()

        self.drag_handle = DragHandleLabel()
        header.addWidget(self.drag_handle)

        header.addWidget(QLabel(f"📄 {filename}"))
        header.addWidget(QLabel(f"({self.total_pages} pages)"))
        
        remove_btn = QPushButton("Remove")
        remove_btn.setMaximumWidth(80)
        remove_btn.setStyleSheet("background-color: #ffcccc;")
        remove_btn.clicked.connect(self.on_remove)
        header.addWidget(remove_btn)
        header.addStretch()
        layout.addLayout(header)
        
        # Page selection
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel("Select pages:"))
        
        self.pages_input = QLineEdit()
        self.pages_input.setPlaceholderText("e.g., '1-5, 10-15' or '1,3,5' or '10' (all)")
        self.pages_input.textChanged.connect(self.on_pages_changed)
        selection_layout.addWidget(self.pages_input)
        
        preset_layout = QHBoxLayout()
        
        all_btn = QPushButton("All")
        all_btn.setMaximumWidth(60)
        all_btn.clicked.connect(lambda: self.pages_input.setText(""))
        preset_layout.addWidget(all_btn)
        
        first_half = QPushButton("1st Half")
        first_half.setMaximumWidth(80)
        first_half.clicked.connect(self.select_first_half)
        preset_layout.addWidget(first_half)
        
        second_half = QPushButton("2nd Half")
        second_half.setMaximumWidth(80)
        second_half.clicked.connect(self.select_second_half)
        preset_layout.addWidget(second_half)

        preview_btn = QPushButton("Preview")
        preview_btn.setMaximumWidth(80)
        preview_btn.clicked.connect(self.open_preview)
        preset_layout.addWidget(preview_btn)

        auto_order_btn = QPushButton("Auto order")
        auto_order_btn.setMaximumWidth(90)
        auto_order_btn.setToolTip("Sort selected pages ascending")
        auto_order_btn.clicked.connect(self.auto_order_pages)
        preset_layout.addWidget(auto_order_btn)
        
        selection_layout.addLayout(preset_layout)
        layout.addLayout(selection_layout)

        # Selected pages order (drag to reorder)
        layout.addWidget(QLabel("Selected page order:"))
        self.order_list = OrderablePageList()
        self.order_list.setMaximumHeight(120)
        self.order_list.order_changed.connect(self.on_order_list_changed)
        layout.addWidget(self.order_list)
        
        # Info
        self.info_label = QLabel(f"Selected: all {self.total_pages} pages")
        layout.addWidget(self.info_label)
        
        self.setLayout(layout)

        # Build initial ordering list
        self.rebuild_order_list()
    
    def on_pages_changed(self):
        """Update selected pages based on input."""
        text = self.pages_input.text().strip()
        
        if not text:
            # Empty = all pages
            self.selected_pages = list(range(0, self.total_pages))
        else:
            try:
                self.selected_pages = self._parse_pages(text)
            except Exception as e:
                # Keep previous selection on error
                pass
        
        self.update_info()
        self.rebuild_order_list()
        self.pages_changed.emit()
    
    def _parse_pages(self, text: str) -> list:
        """Parse page selection input (0-indexed internally)."""
        pages = []
        
        # Handle ranges like "1-5, 10-15"
        if '-' in text:
            parts = text.split(',')
            for part in parts:
                part = part.strip()
                if '-' in part:
                    start, end = part.split('-')
                    start, end = int(start.strip()), int(end.strip())
                    if start < 1 or end > self.total_pages or start > end:
                        raise ValueError(f"Invalid range: {start}-{end}")
                    pages.extend(range(start - 1, end))
                else:
                    page = int(part)
                    if page < 1 or page > self.total_pages:
                        raise ValueError(f"Invalid page: {page}")
                    pages.append(page - 1)
        else:
            # Handle comma-separated: "1,3,5,10"
            for part in text.split(','):
                part = part.strip()
                page = int(part)
                if page < 1 or page > self.total_pages:
                    raise ValueError(f"Invalid page: {page}")
                pages.append(page - 1)

        # Remove duplicates but KEEP order
        return list(dict.fromkeys(pages))
    
    def select_first_half(self):
        """Select first half of pages."""
        mid = self.total_pages // 2
        self.pages_input.setText(f"1-{mid}")
    
    def select_second_half(self):
        """Select second half of pages."""
        mid = self.total_pages // 2 + 1
        self.pages_input.setText(f"{mid}-{self.total_pages}")
    
    def update_info(self):
        """Update info label."""
        count = len(self.selected_pages)
        rotated_count = len([p for p, deg in self.page_rotations.items() if deg % 360 != 0])
        if count == self.total_pages:
            info = f"Selected: all {count} pages"
        else:
            page_ranges = self._format_page_list(self.selected_pages)
            info = f"Selected: {count} pages - {page_ranges}"

        if rotated_count:
            info += f" | Rotated pages: {rotated_count}"
        self.info_label.setText(info)
    
    def _format_page_list(self, pages):
        """Format page list for display (convert back to 1-indexed)."""
        if not pages:
            return "none"

        # If the list is already ascending, keep the compact range formatting.
        if pages == sorted(pages):
            formatted = []
            start = pages[0] + 1
            end = start

            for i in range(1, len(pages)):
                if pages[i] == pages[i - 1] + 1:
                    end = pages[i] + 1
                else:
                    if start == end:
                        formatted.append(str(start))
                    else:
                        formatted.append(f"{start}-{end}")
                    start = pages[i] + 1
                    end = start

            if start == end:
                formatted.append(str(start))
            else:
                formatted.append(f"{start}-{end}")

            return ", ".join(formatted[:3]) + ("..." if len(formatted) > 3 else "")

        # Otherwise show explicit order.
        shown = ", ".join(str(p + 1) for p in pages[:10])
        return shown + ("..." if len(pages) > 10 else "")

    def rebuild_order_list(self):
        """Rebuild the visible ordering list from selected_pages."""
        if not hasattr(self, 'order_list'):
            return
        self.order_list.blockSignals(True)
        try:
            self.order_list.clear()
            for page_num in self.selected_pages:
                item = QListWidgetItem(f"Page {page_num + 1}")
                item.setData(Qt.ItemDataRole.UserRole, page_num)
                self.order_list.addItem(item)
        finally:
            self.order_list.blockSignals(False)

    def on_order_list_changed(self):
        """Sync selected_pages from the visual order list."""
        ordered = []
        for i in range(self.order_list.count()):
            item = self.order_list.item(i)
            page_num = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(page_num, int):
                ordered.append(page_num)
        self.selected_pages = ordered

        # Drag-reordering creates a custom order that no longer matches the
        # user's typed page selection expression. Clear the input to avoid
        # implying the typed expression still applies.
        if self.pages_input.text():
            self.pages_input.blockSignals(True)
            try:
                self.pages_input.setText("")
            finally:
                self.pages_input.blockSignals(False)
        self.update_info()
        self.pages_changed.emit()

    def auto_order_pages(self):
        """Sort currently selected pages ascending."""
        self.selected_pages = sorted(self.selected_pages)
        self.rebuild_order_list()
        self.update_info()
        self.pages_changed.emit()
    
    def on_remove(self):
        """Request removal of this file."""
        self.removed.emit(self.filepath)

    def open_preview(self):
        """Open page thumbnail preview for rotation in combine mode."""
        dlg = CombinePreviewDialog(self.filepath, self.total_pages, self.page_rotations, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.page_rotations = dlg.page_rotations
            self.update_info()
            self.pages_changed.emit()


class CombinePDFWidget(QWidget):
    """Widget for combining multiple PDF files."""
    combine_ready = pyqtSignal(list)  # [(filepath, [page_nums]), ...]
    
    def __init__(self):
        super().__init__()
        self.pdf_files = {}  # {filepath: PDFFileItemWidget}
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Instructions
        layout.addWidget(QLabel("Combine Multiple PDFs:"))
        
        # Add file button
        add_btn = QPushButton("+ Add PDF File")
        add_btn.clicked.connect(self.add_pdf_file)
        layout.addWidget(add_btn)
        
        # Reorderable list of loaded PDFs (drag the handle to change order)
        self.file_list = PDFFileListWidget()
        self.file_list.setSpacing(6)
        self.file_list.order_changed.connect(self.update_info)
        layout.addWidget(self.file_list, 1)

        # Actions
        actions = QHBoxLayout()

        preview_btn = QPushButton("Preview combined")
        preview_btn.setToolTip("Generate a temporary combined PDF and open it in your PDF viewer")
        preview_btn.clicked.connect(self.on_preview_combined)
        actions.addWidget(preview_btn)

        combine_btn = QPushButton("Combine Selected Pages")
        combine_btn.setStyleSheet("background-color: #ccffcc; color: #1f2937; font-weight: 600;")
        combine_btn.clicked.connect(self.on_combine)
        actions.addWidget(combine_btn)

        layout.addLayout(actions)
        
        # Info
        self.info_label = QLabel("Add 2+ PDF files to combine")
        layout.addWidget(self.info_label)
        
        self.setLayout(layout)
    
    def add_pdf_file(self):
        """Add a new PDF file for combining."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select PDF to Combine", "", "PDF Files (*.pdf)"
        )
        if file_path and file_path not in self.pdf_files:
            # Load PDF to get page count
            from services.pdf_service import PDFService
            doc = PDFService.load_pdf(file_path)
            if doc:
                widget = PDFFileItemWidget(file_path, doc.total_pages)
                widget.removed.connect(self.on_file_removed)
                widget.pages_changed.connect(self.update_info)

                list_item = QListWidgetItem()
                list_item.setSizeHint(widget.sizeHint())
                self.file_list.addItem(list_item)
                self.file_list.setItemWidget(list_item, widget)
                widget.attach_drag_context(self.file_list, list_item)

                self.pdf_files[file_path] = widget
                self.update_info()
    
    def on_file_removed(self, filepath: str):
        """Remove a PDF file from combine."""
        if filepath in self.pdf_files:
            widget = self.pdf_files[filepath]

            # Remove the corresponding row from the reorderable list.
            for row in range(self.file_list.count()):
                item = self.file_list.item(row)
                if self.file_list.itemWidget(item) is widget:
                    self.file_list.takeItem(row)
                    break

            widget.deleteLater()
            del self.pdf_files[filepath]
            self.update_info()
    
    def update_info(self):
        """Update info label with total pages."""
        total = 0
        for item in self.pdf_files.values():
            total += len(item.selected_pages)
        
        count = len(self.pdf_files)
        if count < 2:
            self.info_label.setText(f"Add {2 - count} more PDF file(s)")
        else:
            self.info_label.setText(f"{count} files, {total} total pages to combine")

    def _gather_combine_data_in_order(self) -> list:
        """Return combine_data in the current (dragged) file order."""
        combine_data = []
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            widget = self.file_list.itemWidget(item)
            if isinstance(widget, PDFFileItemWidget) and widget.selected_pages:
                combine_data.append((widget.filepath, widget.selected_pages, widget.page_rotations.copy()))
        return combine_data
    
    def on_preview_combined(self):
        """Generate a temporary combined PDF and open it for preview."""
        if len(self.pdf_files) < 2:
            QMessageBox.warning(self, "Warning", "Add at least 2 PDF files to combine")
            return

        # Gather combine data (in the current file order)
        combine_data = self._gather_combine_data_in_order()

        if not combine_data:
            QMessageBox.warning(self, "Warning", "No pages selected to preview")
            return

        # Write preview PDF under ./output so we don't prompt for a path.
        # Use a unique filename so a previously opened preview isn't overwritten/locked.
        import time
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        preview_path = out_dir / f"combined_preview_{int(time.time())}.pdf"

        from services.pdf_service import PDFService
        result = PDFService.combine_pdfs(combine_data, str(preview_path))
        if not result.get("success"):
            msg = "Preview failed!\n\n" + "\n".join(result.get("errors") or [])
            QMessageBox.critical(self, "Error", msg)
            return

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(preview_path)))
        if not opened:
            QMessageBox.information(
                self,
                "Preview created",
                f"Preview PDF created but could not be opened automatically:\n{preview_path}",
            )

    def on_combine(self):
        """Prepare combine data."""
        if len(self.pdf_files) < 2:
            QMessageBox.warning(self, "Warning", "Add at least 2 PDF files to combine")
            return
        
        # Gather combine data (in the current file order)
        combine_data = self._gather_combine_data_in_order()

        if combine_data:
            self.combine_ready.emit(combine_data)


class SplitsManagerWidget(QWidget):
    """Container for all split groups."""
    
    def __init__(self):
        super().__init__()
        self.splits = {}
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Split Groups:"))
        
        # Scrollable area for splits
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        self.scroll_widget = QWidget()
        self.splits_layout = QVBoxLayout(self.scroll_widget)
        scroll.setWidget(self.scroll_widget)
        
        layout.addWidget(scroll)
        
        # Add split button
        add_btn = QPushButton("+ Add Split Group")
        add_btn.clicked.connect(self.on_add_split)
        layout.addWidget(add_btn)
        
        self.setLayout(layout)
    
    def on_add_split(self):
        """Add a new split group."""
        default_name = f"Split {len(self.splits) + 1}"
        self.add_split(default_name)
    
    def add_split(self, name: str):
        """Create and add split panel."""
        if name in self.splits:
            return
        
        panel = SplitGroupPanel(name)
        self.splits[name] = panel
        self.splits_layout.addWidget(panel)
        
        # Connect signals
        panel.remove_requested.connect(self.on_remove_split)
    
    def on_remove_split(self, split_name: str):
        """Remove a split group."""
        if split_name in self.splits:
            panel = self.splits[split_name]
            panel.deleteLater()
            del self.splits[split_name]
