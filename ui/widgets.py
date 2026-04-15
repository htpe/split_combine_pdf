import io
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGridLayout, QScrollArea,
    QLineEdit, QFrame, QSpinBox, QComboBox, QFileDialog, QMenu,
    QDialog, QListView, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QSize, QEvent
from PyQt6.QtGui import QDrag, QPixmap, QColor, QTransform, QIcon
from PyQt6.QtCore import QPoint

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
        
        remove_btn = QPushButton("Remove")
        remove_btn.setStyleSheet("background-color: #ffcccc;")
        remove_btn.clicked.connect(self.on_remove)
        header.addWidget(remove_btn)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Page list
        self.page_list = QListWidget()
        self.page_list.setMaximumHeight(120)
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
            self.page_list.addItem(item)
            self.update_info()
            self.pages_changed.emit()
    
    def remove_page(self, page_num):
        """Remove page from this split."""
        self.pages = [p for p in self.pages if p.page_num != page_num]
        for i in range(self.page_list.count()):
            item = self.page_list.item(i)
            if f"Page {page_num + 1}" in item.text():
                self.page_list.takeItem(i)
                break
        self.update_info()
        self.pages_changed.emit()
    
    def update_info(self):
        """Update page count display."""
        count = len(self.pages)
        page_nums = sorted([p.page_num + 1 for p in self.pages])
        self.info_label.setText(f"{count} page(s): {page_nums}")
    
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
        """Accept drag if it's a page."""
        if event.mimeData().hasText() and "page:" in event.mimeData().text():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        """Handle drop of page."""
        mime_text = event.mimeData().text()
        if mime_text.startswith("page:"):
            try:
                page_num = int(mime_text.split(":")[1])
                # Create a simple page object for now
                # In real app, fetch from main document
                from models.pdf_model import PDFPage
                page = PDFPage(page_num=page_num)
                self.add_page(page)
            except:
                pass

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
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # File info header
        filename = Path(self.filepath).name
        header = QHBoxLayout()
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
        
        selection_layout.addLayout(preset_layout)
        layout.addLayout(selection_layout)
        
        # Info
        self.info_label = QLabel(f"Selected: all {self.total_pages} pages")
        layout.addWidget(self.info_label)
        
        self.setLayout(layout)
    
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
        
        return sorted(list(set(pages)))  # Remove duplicates, sort
    
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
        
        formatted = []
        start = pages[0] + 1
        end = start
        
        for i in range(1, len(pages)):
            if pages[i] == pages[i-1] + 1:
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
        
        # Scrollable area for PDFs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        self.scroll_widget = QWidget()
        self.files_layout = QVBoxLayout(self.scroll_widget)
        scroll.setWidget(self.scroll_widget)
        layout.addWidget(scroll)
        
        # Combine button
        combine_btn = QPushButton("Combine Selected Pages")
        combine_btn.setStyleSheet("background-color: #ccffcc; color: #1f2937; font-weight: 600;")
        combine_btn.clicked.connect(self.on_combine)
        layout.addWidget(combine_btn)
        
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
                item = PDFFileItemWidget(file_path, doc.total_pages)
                item.removed.connect(self.on_file_removed)
                item.pages_changed.connect(self.update_info)
                
                self.pdf_files[file_path] = item
                self.files_layout.addWidget(item)
                self.update_info()
    
    def on_file_removed(self, filepath: str):
        """Remove a PDF file from combine."""
        if filepath in self.pdf_files:
            widget = self.pdf_files[filepath]
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
    
    def on_combine(self):
        """Prepare combine data."""
        if len(self.pdf_files) < 2:
            QMessageBox.warning(self, "Warning", "Add at least 2 PDF files to combine")
            return
        
        # Gather combine data
        combine_data = []
        for filepath, item in self.pdf_files.items():
            if item.selected_pages:
                combine_data.append((filepath, item.selected_pages, item.page_rotations.copy()))
        
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
