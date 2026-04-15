from PyQt6.QtCore import QThread, pyqtSignal
from services.pdf_service import PDFService

class ThumbnailWorker(QThread):
    """Worker thread to generate thumbnails without blocking UI."""
    thumbnail_ready = pyqtSignal(int, object)  # page_num, thumbnail_image
    all_done = pyqtSignal()
    
    def __init__(self, filepath: str, total_pages: int):
        super().__init__()
        self.filepath = filepath
        self.total_pages = total_pages
    
    def run(self):
        """Generate thumbnails for all pages."""
        for page_num in range(self.total_pages):
            thumb = PDFService.generate_thumbnail(self.filepath, page_num)
            self.thumbnail_ready.emit(page_num, thumb)
        self.all_done.emit()
