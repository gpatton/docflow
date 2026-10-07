from io import BytesIO
from app.invoice import extract_invoice
from fastapi import FastAPI, HTTPException, UploadFile
from pypdf import PdfReader
from starlette.concurrency import run_in_threadpool


app = FastAPI(
    title="DocFlow",
    description="Local invoice document processing.",
    version="0.1.0",
)

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PAGES = 25


@app.get("/health")
def health():
    return {"status": "healthy", "service": "DocFlow"}


def extract_pdf(data: bytes):
    try:
        reader = PdfReader(BytesIO(data))

        if reader.is_encrypted:
            raise HTTPException(
                status_code=422,
                detail="Password-protected PDFs are not supported.",
            )

        if len(reader.pages) > MAX_PAGES:
            raise HTTPException(
                status_code=422,
                detail=f"PDFs must contain at most {MAX_PAGES} pages.",
            )

        pages = [
            {
                "page_number": number,
                "text": (page.extract_text() or "").strip(),
            }
            for number, page in enumerate(reader.pages, start=1)
        ]

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=422,
            detail="The PDF could not be read or its text extracted.",
        ) from error

    has_text = any(page["text"] for page in pages)
    combined_text = "\n".join(page["text"] for page in pages)

    return {
        "page_count": len(pages),
        "status": "text_extracted" if has_text else "ocr_required",
        "pages": pages,
        "invoice": extract_invoice(combined_text) if has_text else None,
    }


@app.post("/documents/extract")
async def extract_document(file: UploadFile):
    try:
        data = await file.read(MAX_FILE_BYTES + 1)
    finally:
        await file.close()

    if not data:
        raise HTTPException(status_code=400, detail="The file is empty.")

    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="The maximum file size is 10 MiB.",
        )

    if b"%PDF-" not in data[:1024]:
        raise HTTPException(
            status_code=415,
            detail="Upload a PDF document.",
        )

    return await run_in_threadpool(extract_pdf, data)
