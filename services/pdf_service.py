import os
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from pypdf import PdfReader, PdfWriter
from PIL import Image
import io
from models.pdf_model import PDFPage, PDFDocument

class PDFService:
    THUMBNAIL_WIDTH = 150
    THUMBNAIL_HEIGHT = 200
    
    @staticmethod
    def load_pdf(filepath: str) -> Optional[PDFDocument]:
        """Load PDF file and extract metadata."""
        try:
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"File not found: {filepath}")
            
            reader = PdfReader(filepath)
            total_pages = len(reader.pages)
            filename = os.path.basename(filepath)
            
            doc = PDFDocument(
                filepath=filepath,
                filename=filename,
                total_pages=total_pages
            )
            
            # Create PDFPage objects (thumbnails added later by ThumbnailService)
            for i in range(total_pages):
                page = PDFPage(page_num=i)
                doc.pages.append(page)
            
            return doc
        except Exception as e:
            print(f"Error loading PDF: {e}")
            return None
    
    @staticmethod
    def generate_thumbnail(filepath: str, page_num: int) -> Optional[Image.Image]:
        """Generate thumbnail for a specific page using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(filepath)
            page = doc[page_num]

            # Scale so the longer dimension fits within the thumbnail bounds
            page_width = page.rect.width
            page_height = page.rect.height
            scale = min(
                PDFService.THUMBNAIL_WIDTH / page_width,
                PDFService.THUMBNAIL_HEIGHT / page_height,
            )
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            doc.close()

            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            return img
        except Exception as e:
            print(f"Error generating thumbnail for page {page_num}: {e}")
            return None
    
    @staticmethod
    def export_splits(document: PDFDocument, splits_data: list, output_dir: str) -> dict:
        """
        Export split groups as separate PDFs.
        
        Args:
            document: PDFDocument with loaded PDF
            splits_data: List of (split_name, [page_nums]) tuples
            output_dir: Directory to save output files
        
        Returns:
            Dict with success status and filenames created
        """
        try:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            reader = PdfReader(document.filepath)
            results = {"success": True, "files": [], "errors": []}
            
            base_name = os.path.splitext(os.path.basename(document.filepath))[0]
            
            for split_name, page_nums in splits_data:
                if not page_nums:
                    results["errors"].append(f"Split '{split_name}' has no pages, skipping")
                    continue
                
                writer = PdfWriter()

                # Add pages to writer (preserve user-defined order)
                # Also de-duplicate while keeping first occurrence.
                ordered_pages = list(dict.fromkeys(page_nums))
                valid_pages = [p for p in ordered_pages if isinstance(p, int) and 0 <= p < len(reader.pages)]
                for page_num in valid_pages:
                    if 0 <= page_num < len(reader.pages):
                        added_page = writer.add_page(reader.pages[page_num])
                        rotation = (
                            document.pages[page_num].rotation
                            if page_num < len(document.pages)
                            else 0
                        )
                        if rotation:
                            added_page.rotate(rotation)
                
                # Generate output filename: <source_name>_<first_page>-<last_page>.pdf
                if not valid_pages:
                    results["errors"].append(f"Split '{split_name}' has no valid pages, skipping")
                    continue

                # Keep filename stable: use min/max page index rather than custom order.
                first = min(valid_pages) + 1
                last = max(valid_pages) + 1
                page_range = f"{first}-{last}" if first != last else str(first)
                output_path = os.path.join(output_dir, f"{base_name}_{page_range}.pdf")
                
                # Handle duplicate filenames
                counter = 1
                base_path = output_path
                while os.path.exists(output_path):
                    name_part = os.path.splitext(base_path)[0]
                    output_path = f"{name_part}_{counter}.pdf"
                    counter += 1
                
                # Write PDF
                with open(output_path, 'wb') as f:
                    writer.write(f)
                
                results["files"].append(os.path.basename(output_path))
            
            return results
        except Exception as e:
            return {"success": False, "files": [], "errors": [str(e)]}

    @staticmethod
    def combine_pdfs(combine_data: list, output_path: str) -> dict:
        """Combine selected pages from multiple PDFs into a single output PDF."""
        try:
            if not combine_data:
                return {"success": False, "file": "", "errors": ["No PDF files selected for combining"]}

            out_dir = os.path.dirname(output_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir)

            writer = PdfWriter()
            added_pages = 0

            for combine_item in combine_data:
                if len(combine_item) == 2:
                    filepath, page_nums = combine_item
                    page_rotations = {}
                else:
                    filepath, page_nums, page_rotations = combine_item

                if not filepath or not os.path.exists(filepath):
                    continue

                reader = PdfReader(filepath)
                ordered_pages = list(dict.fromkeys(page_nums or []))
                for page_num in ordered_pages:
                    if isinstance(page_num, int) and 0 <= page_num < len(reader.pages):
                        added_page = writer.add_page(reader.pages[page_num])
                        rotation = page_rotations.get(page_num, 0)
                        if rotation:
                            added_page.rotate(rotation)
                        added_pages += 1

            if added_pages == 0:
                return {"success": False, "file": "", "errors": ["No valid pages were selected to combine"]}

            with open(output_path, 'wb') as f:
                writer.write(f)

            return {"success": True, "file": os.path.basename(output_path), "errors": []}
        except Exception as e:
            return {"success": False, "file": "", "errors": [str(e)]}
