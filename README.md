# PDF Split & Combine - Desktop Application

A modern PyQt6-based desktop application for splitting and combining PDF files with an intuitive drag-and-drop interface.

## Features

✨ **Core Features:**
- **Load PDF files** - Open any PDF to start working
- **Page preview** - Thumbnail grid of all pages for easy browsing
- **Split organization** - Create multiple split groups with custom names
- **Drag-and-drop** - Visually drag pages from preview to split groups
- **Index-based splitting** - Automatically split by page ranges, fixed sizes, or split points
- **Rename splits** - Give meaningful names to each split
- **Export to PDFs** - Save each split as a separate PDF file

## Installation

### Prerequisites
- Python 3.8 or higher
- pip

### Setup

1. Navigate to the project directory:
```bash
cd /path/to/split_combine_pdf
```

2. (Recommended) Create and activate a virtual environment:

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:
```bash
python -m pip install -r requirements.txt
```

## Usage

### Running the Application

```bash
python main.py
```

macOS/Linux can also use:
```bash
./run.sh
```

The application will open in a new window.

### Workflow

1. **Open PDF**: Click "Open PDF" button or press `Ctrl+O` to load a PDF file
2. **Preview Pages**: Thumbnails appear on the left side as they're generated
3. **Create Splits**: Click "+ Add Split Group" to create a new split
4. **Organize Pages**: 
   - Click and drag pages from the left panel
   - Drop them into split groups on the right
5. **Rename Splits**: 
   - Edit the split name in the text field
   - Click "Rename" to confirm
6. **Export**: 
   - Click "Export Splits" button or press `Ctrl+E`
   - Select output folder
   - Review split summary
   - Click "Export" - each split saves as a separate PDF

## Project Structure

```
split_pdfs/
├── main.py                          # Application entry point
├── requirements.txt                 # Python dependencies
├── models/
│   ├── __init__.py
│   └── pdf_model.py                # Data models (PDFPage, SplitGroup, PDFDocument)
├── services/
│   ├── __init__.py
│   ├── pdf_service.py              # PDF I/O operations (load, extract, export)
│   └── thumbnail_service.py        # Async thumbnail generation
└── ui/
    ├── __init__.py
    ├── main_window.py              # Main application window
    ├── widgets.py                  # Custom widgets (PagePreview, SplitGroups)
    └── dialogs.py                  # Export dialog
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open PDF file |
| `Ctrl+E` | Export splits to PDFs |

## Dependencies

- **PyQt6** - Modern desktop UI framework
- **pypdf** - PDF manipulation and page extraction
- **Pillow** - Image processing for thumbnails

## How It Works

1. **Load**: PDF is loaded using pypdf, extracting page count and metadata
2. **Thumbnails**: Pages are rendered as thumbnail images asynchronously to avoid UI freezing
3. **Organization**: Pages are organized into split groups through drag-and-drop
4. **Export**: Each split group is extracted from the original PDF and saved as a separate file

## Notes

- Thumbnails are generated asynchronously to keep the UI responsive
- Large PDFs (500+ pages) may take longer to generate thumbnails
- Each page can only belong to one split at a time
- Export preserves page order within each split
- Output filenames are automatically sanitized and made unique if duplicates exist

## Future Enhancements

- Multi-select pages for batch drag operations
- Combine multiple PDFs into one
- PDF merging with custom page ordering
- Bookmark support
- Watermark addition
- PDF compression options
- Batch processing

## Troubleshooting

**Q: Application won't start**
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (requires 3.8+)

**Q: Thumbnails take a long time to generate**
- This is normal for large PDFs. The UI remains responsive during generation.
- Cancel by closing the application if needed.

**Q: Export fails with "Permission denied"**
- Ensure the output folder is writable
- Try selecting a different folder
- Close any files that might be using the output location

**Q: Can't drag pages to splits**
- Ensure at least one split group exists (click "+ Add Split Group")
- Click and hold on a page, then drag to the split panel on the right
- Release the mouse to drop

## License

This project is provided as-is for personal and commercial use.
