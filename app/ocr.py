import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException


def ocr_page(pdf_data: bytes, page_number: int) -> str:
    """Render one PDF page and extract its text locally."""

    for tool in ("pdftoppm", "tesseract"):
        if shutil.which(tool) is None:
            raise HTTPException(
                status_code=503,
                detail=f"OCR requires the installed tool: {tool}",
            )

    with TemporaryDirectory(prefix="docflow-ocr-") as directory:
        root = Path(directory)
        pdf_path = root / "document.pdf"
        image_prefix = root / "page"
        pdf_path.write_bytes(pdf_data)

        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-f", str(page_number),
                    "-l", str(page_number),
                    "-singlefile",
                    "-scale-to", "2400",
                    "-png",
                    str(pdf_path),
                    str(image_prefix),
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )

            result = subprocess.run(
                [
                    "tesseract",
                    str(image_prefix.with_suffix(".png")),
                    "stdout",
                    "-l", "eng",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=45,
            )

        except subprocess.TimeoutExpired as error:
            raise HTTPException(
                status_code=422,
                detail=f"OCR timed out on page {page_number}.",
            ) from error
        except subprocess.CalledProcessError as error:
            raise HTTPException(
                status_code=422,
                detail=f"OCR failed on page {page_number}.",
            ) from error

        return result.stdout.strip()
