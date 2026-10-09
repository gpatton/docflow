from io import BytesIO
from app.invoice import extract_invoice
from fastapi import FastAPI, HTTPException, UploadFile
from pypdf import PdfReader
from starlette.concurrency import run_in_threadpool
from app.ocr import ocr_page

from contextlib import asynccontextmanager
from app.database import initialize_database
from app.invoices import router as invoices_router
from app.documents import (
    initialize_documents,
    save_document,
    router as documents_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_in_threadpool(initialize_database)
    from app.database import initialize_history
    await run_in_threadpool(initialize_history)
    await run_in_threadpool(initialize_documents)
    from app.documents import initialize_document_links
    await run_in_threadpool(initialize_document_links)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="DocFlow",
    description="Local invoice document processing.",
    version="0.1.0",
)

app.include_router(invoices_router)
app.include_router(documents_router)

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

        pages = []

        for number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            method = "pdf_text"

            if not text:
                text = ocr_page(data, number)
                method = "ocr"

            pages.append(
                {
                    "page_number": number,
                    "text": text,
                    "extraction_method": method,
                }
            )
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
        "status": "text_extracted" if has_text else "no_text_found",
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

    result = await run_in_threadpool(extract_pdf, data)
    filename = (file.filename or "invoice.pdf").replace("\\", "/")
    filename = filename.rsplit("/", 1)[-1][:255] or "invoice.pdf"
    document_id = await run_in_threadpool(save_document, filename, data)
    result["document_id"] = str(document_id)
    result["filename"] = filename
    return result
