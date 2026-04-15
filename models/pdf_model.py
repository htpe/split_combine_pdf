from dataclasses import dataclass, field
from typing import List
from PIL.Image import Image

@dataclass
class PDFPage:
    page_num: int
    thumbnail: Image = None
    page_width: float = 0
    page_height: float = 0
    rotation: int = 0  # cumulative rotation in degrees (0, 90, 180, 270)

@dataclass
class SplitGroup:
    name: str
    pages: List[PDFPage] = field(default_factory=list)
    
    def page_count(self) -> int:
        return len(self.pages)
    
    def page_range_str(self) -> str:
        if not self.pages:
            return "No pages"
        return f"Pages: {', '.join(str(p.page_num + 1) for p in sorted(self.pages, key=lambda x: x.page_num))}"

@dataclass
class PDFDocument:
    filepath: str
    filename: str
    total_pages: int
    pages: List[PDFPage] = field(default_factory=list)
    splits: List[SplitGroup] = field(default_factory=list)
    
    def total_pages_assigned(self) -> int:
        assigned = set()
        for split in self.splits:
            for page in split.pages:
                assigned.add(page.page_num)
        return len(assigned)
    
    def unassigned_pages(self) -> List[PDFPage]:
        assigned_nums = set()
        for split in self.splits:
            for page in split.pages:
                assigned_nums.add(page.page_num)
        return [p for p in self.pages if p.page_num not in assigned_nums]
