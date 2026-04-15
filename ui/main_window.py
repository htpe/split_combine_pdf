import io
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QMessageBox, QProgressBar, QTabWidget, QDialog
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QKeySequence, QAction, QPixmap, QIcon
from services.pdf_service import PDFService
from services.thumbnail_service import ThumbnailWorker
from models.pdf_model import PDFDocument, PDFPage
from ui.widgets import PagePreviewWidget, SplitsManagerWidget, PageIndexSplitWidget, CombinePDFWidget
from ui.dialogs import ExportDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Split & Combine")
        self.setGeometry(100, 100, 1200, 800)
        
        self.current_doc: PDFDocument = None
        self.thumbnail_worker = None
        
        self.init_ui()
        self.setup_shortcuts()
    
    def init_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout()

        # Split panel toolbar
        toolbar_layout = QHBoxLayout()

        self.open_btn = QPushButton("Open PDF")
        self.open_btn.clicked.connect(self.open_pdf)
        toolbar_layout.addWidget(self.open_btn)

        self.file_label = QLabel("No file loaded")
        toolbar_layout.addWidget(self.file_label)

        self.export_btn = QPushButton("Export Splits")
        self.export_btn.clicked.connect(self.export_splits)
        self.export_btn.setEnabled(False)
        toolbar_layout.addWidget(self.export_btn)

        toolbar_layout.addStretch()

        # Loading progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        
        # Split content area
        content_layout = QHBoxLayout()
        
        # Left: Page preview
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.page_preview = PagePreviewWidget()
        self.page_preview.page_rotated.connect(self.on_page_rotated)
        left_layout.addWidget(self.page_preview)
        content_layout.addWidget(left_panel, 1)
        
        # Right: Splits manager with tabs
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Tab widget for manual and index-based splitting
        self.split_tabs = QTabWidget()
        
        # Tab 1: Manual drag-drop splitting
        self.splits_manager = SplitsManagerWidget()
        self.split_tabs.addTab(self.splits_manager, "Manual Splits")
        
        # Tab 2: Index-based splitting
        self.index_split_widget = None
        
        right_layout.addWidget(self.split_tabs)
        content_layout.addWidget(right_panel, 1)

        split_tab = QWidget()
        split_tab_layout = QVBoxLayout(split_tab)
        split_tab_layout.addLayout(toolbar_layout)
        split_tab_layout.addWidget(self.progress)
        split_tab_layout.addLayout(content_layout)

        # Main app panels: Split and Combine
        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(split_tab, "Split PDF")

        self.combine_widget = CombinePDFWidget()
        self.combine_widget.combine_ready.connect(self.on_combine_ready)
        self.main_tabs.addTab(self.combine_widget, "Combine PDFs")

        main_layout.addWidget(self.main_tabs)
        central.setLayout(main_layout)
        self.setCentralWidget(central)
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Ctrl+O: Open
        open_action = QAction(self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_pdf)
        self.addAction(open_action)
        
        # Ctrl+E: Export
        export_action = QAction(self)
        export_action.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_E))
        export_action.triggered.connect(self.export_splits)
        self.addAction(export_action)
    
    def open_pdf(self):
        """Open PDF file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.load_pdf(file_path)
    
    def load_pdf(self, filepath: str):
        """Load PDF and generate thumbnails."""
        doc = PDFService.load_pdf(filepath)
        if not doc:
            QMessageBox.critical(self, "Error", "Failed to load PDF")
            return
        
        self.current_doc = doc
        self.file_label.setText(f"{doc.filename} ({doc.total_pages} pages)")
        
        # Clear existing pages
        for i in reversed(range(self.page_preview.grid.count())):
            self.page_preview.grid.itemAt(i).widget().deleteLater()
        self.page_preview.pages.clear()
        
        # Add pages to preview
        for page in doc.pages:
            self.page_preview.add_page(page)
        
        # Start thumbnail generation in worker thread
        self.progress.setVisible(True)
        self.progress.setMaximum(0)  # Indeterminate
        
        self.thumbnail_worker = ThumbnailWorker(filepath, doc.total_pages)
        self.thumbnail_worker.thumbnail_ready.connect(self.on_thumbnail_ready)
        self.thumbnail_worker.all_done.connect(self.on_thumbnails_done)
        self.thumbnail_worker.start()
        
        # Clear splits and recreate tab
        self.splits_manager.splits.clear()
        for i in reversed(range(self.splits_manager.splits_layout.count())):
            widget = self.splits_manager.splits_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Update or create index split widget
        if self.index_split_widget:
            self.split_tabs.removeTab(self.split_tabs.indexOf(self.index_split_widget))
            self.index_split_widget.deleteLater()
        
        self.index_split_widget = PageIndexSplitWidget(doc.total_pages)
        self.index_split_widget.splits_created.connect(self.on_index_splits_created)
        self.split_tabs.addTab(self.index_split_widget, "Index-Based Splits")
        
        self.export_btn.setEnabled(False)
    
    def on_thumbnail_ready(self, page_num, thumbnail):
        """Update page with thumbnail."""
        if self.current_doc and page_num < len(self.current_doc.pages):
            self.current_doc.pages[page_num].thumbnail = thumbnail
            # Update button in preview
            if page_num in self.page_preview.pages:
                btn = self.page_preview.pages[page_num]
                if thumbnail:
                    buf = io.BytesIO()
                    thumbnail.save(buf, format='PNG')
                    buf.seek(0)
                    pixmap = QPixmap()
                    pixmap.loadFromData(buf.read())
                    btn.setIcon(QIcon(pixmap))
                    btn.setIconSize(QSize(150, 200))
    
    def on_thumbnails_done(self):
        """Thumbnails generation complete."""
        self.progress.setVisible(False)
        self.export_btn.setEnabled(True)
    
    def on_index_splits_created(self, splits_data: dict):
        """Handle splits created from index-based splitting.
        
        splits_data: {split_name: [page_nums]} where page_nums are 0-indexed
        """
        if not self.current_doc:
            return
        
        # Clear existing manual splits
        self.splits_manager.splits.clear()
        for i in reversed(range(self.splits_manager.splits_layout.count())):
            widget = self.splits_manager.splits_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Create splits and add pages
        for split_name, page_indices in splits_data.items():
            self.splits_manager.add_split(split_name)
            panel = self.splits_manager.splits[split_name]
            
            # Add pages to the split (use actual PDFPage objects from current_doc)
            for page_idx in page_indices:
                if 0 <= page_idx < len(self.current_doc.pages):
                    panel.add_page(self.current_doc.pages[page_idx])
        
        # Switch to manual splits tab to show results
        self.split_tabs.setCurrentIndex(0)
        QMessageBox.information(self, "Success", f"Created {len(splits_data)} split group(s)")

    def on_combine_ready(self, combine_data: list):
        """Handle combine request from combine panel."""
        output_file, _ = QFileDialog.getSaveFileName(
            self,
            "Save Combined PDF",
            "combined.pdf",
            "PDF Files (*.pdf)"
        )
        if not output_file:
            return

        if not output_file.lower().endswith('.pdf'):
            output_file += '.pdf'

        result = PDFService.combine_pdfs(combine_data, output_file)
        if result["success"]:
            QMessageBox.information(self, "Success", f"Combined PDF created:\n{result['file']}")
        else:
            msg = "Combine failed!\n\n" + "\n".join(result["errors"])
            QMessageBox.critical(self, "Error", msg)
    
    def export_splits(self):
        """Export split PDFs."""
        if not self.current_doc or not self.splits_manager.splits:
            QMessageBox.warning(self, "Warning", "Please create at least one split group")
            return
        
        # Gather split data
        splits_data = {}
        for split_name, split_panel in self.splits_manager.splits.items():
            page_nums = [p.page_num for p in split_panel.pages]
            if page_nums:
                splits_data[split_name] = page_nums
        
        if not splits_data:
            QMessageBox.warning(self, "Warning", "No pages assigned to splits")
            return
        
        # Show export dialog
        dialog = ExportDialog(self, splits_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if not dialog.output_dir:
                QMessageBox.warning(self, "Warning", "Please select output directory")
                return
            
            # Export
            result = PDFService.export_splits(
                self.current_doc,
                [(name, pages) for name, pages in splits_data.items()],
                dialog.output_dir
            )
            
            if result["success"]:
                msg = f"Export successful!\n\nFiles created:\n" + "\n".join(result["files"])
                QMessageBox.information(self, "Success", msg)
            else:
                msg = "Export failed!\n\n" + "\n".join(result["errors"])
                QMessageBox.critical(self, "Error", msg)

    def on_page_rotated(self, page_num: int, rotation: int):
        """Store rotation on the PDFPage model when user rotates a thumbnail."""
        if self.current_doc and page_num < len(self.current_doc.pages):
            self.current_doc.pages[page_num].rotation = rotation
