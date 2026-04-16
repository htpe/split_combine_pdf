from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt

class ExportDialog(QDialog):
    """Dialog for reviewing and exporting splits."""
    
    def __init__(self, parent, splits_data: dict):
        super().__init__(parent)
        self.splits_data = splits_data  # {split_name: [page_nums]}
        self.output_dir = None
        self.setWindowTitle("Export Splits")
        self.setGeometry(100, 100, 600, 400)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Summary
        layout.addWidget(QLabel("Export Summary:"))
        self.summary_list = QListWidget()
        for name, pages in self.splits_data.items():
            pages_display = [p + 1 for p in pages]
            item = QListWidgetItem(f"{name}: {len(pages)} page(s) {pages_display}")
            self.summary_list.addItem(item)
        layout.addWidget(self.summary_list)
        
        # Output directory
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel("Output: (not selected)")
        dir_btn = QPushButton("Select Folder...")
        dir_btn.clicked.connect(self.select_output_dir)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(dir_btn)
        layout.addLayout(dir_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(export_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def select_output_dir(self):
        """Select output directory."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.output_dir = dir_path
            self.dir_label.setText(f"Output: {dir_path}")
