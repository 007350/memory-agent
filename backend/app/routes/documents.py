import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile, File

from app.exceptions import ExternalServiceError
from app.middleware.metrics import metrics
from app.schemas.lightrag import DocumentInsertRequest, DocumentUploadResponse, TrackStatusResponse
from app.services.lightrag_client import LightRAGClient, LightRAGUnavailableError


router = APIRouter()

ALLOWED_MIME = {"text/plain", "text/markdown", "application/pdf"}
ALLOWED_EXT = {".txt", ".md", ".pdf"}


@router.post("/documents", response_model=DocumentUploadResponse)
async def insert_document(body: DocumentInsertRequest):
    text = body.text
    file_source = body.file_source
    if not text.strip():
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "text is required"})

    client = LightRAGClient.acquire()
    try:
        resp = await client.insert_text(text, file_source=file_source or None)
        return resp
    except LightRAGUnavailableError as e:
        metrics.inc_unavailable()
        raise HTTPException(status_code=503, detail={"code": "LIGHTRAG_UNAVAILABLE", "message": str(e)})
    finally:
        await client.release()


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    content_type = (file.content_type or "").split(";")[0].strip()
    if ext not in ALLOWED_EXT and content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": f"Only .txt, .md, .pdf are supported"},
        )
    mime = content_type if content_type in ALLOWED_MIME else ("application/pdf" if ext == ".pdf" else "text/plain")

    suffix = ext or ".tmp"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
            content = await file.read()
            tmp.write(content)

        client = LightRAGClient.acquire()
        try:
            resp = await client.upload_document(tmp_path, mime_type=mime)
            return resp
        except LightRAGUnavailableError as e:
            metrics.inc_unavailable()
            raise HTTPException(status_code=503, detail={"code": "LIGHTRAG_UNAVAILABLE", "message": str(e)})
        finally:
            await client.release()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/documents/{track_id}/status", response_model=TrackStatusResponse)
async def document_status(track_id: str):
    if not track_id.strip():
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "track_id is required"})

    client = LightRAGClient.acquire()
    try:
        return await client.get_track_status(track_id)
    except LightRAGUnavailableError as e:
        metrics.inc_unavailable()
        raise HTTPException(status_code=503, detail={"code": "LIGHTRAG_UNAVAILABLE", "message": str(e)})
    finally:
        await client.release()
