"""FastAPI backend for SiriScore web UI."""
from pathlib import Path
import logging
import time
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import tempfile, os

from scorer import score_as as _score_as, import_labels
from scorer.labels import get_all_labels, add_label, init_db

app = FastAPI(title="SiriScore API")
init_db()

WEB_DIR = Path(__file__).parent.parent / "web"
logger = logging.getLogger("siriscore.api")


class ScoreRequest(BaseModel):
    input: str
    input_type: str = "psbt"  # psbt | rawtx | txid


class LabelRequest(BaseModel):
    txid: str
    vout: int
    label: str
    tag: str = "unknown"


@app.post("/score")
def score_tx(req: ScoreRequest):
    started = time.perf_counter()
    preview = req.input.strip()[:16]
    logger.info("score.start input_type=%s preview=%s...", req.input_type, preview)
    try:
        report = _score_as(req.input, req.input_type)
    except Exception as e:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.warning(
            "score.error input_type=%s elapsed_ms=%.1f error=%s",
            req.input_type,
            elapsed_ms,
            e,
        )
        raise HTTPException(status_code=400, detail=str(e))

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "score.done input_type=%s elapsed_ms=%.1f score=%s inputs=%s outputs=%s findings=%s",
        req.input_type,
        elapsed_ms,
        report.score,
        report.input_count,
        report.output_count,
        len(report.findings),
    )

    return {
        "score": report.score,
        "psbt_version": report.psbt_version,
        "input_count": report.input_count,
        "output_count": report.output_count,
        "warnings": report.warnings,
        "findings": [
            {
                "id": f.heuristic_id,
                "severity": f.severity.value,
                "title": f.title,
                "detail": f.detail,
                "suggestion": f.suggestion,
                "weight": f.weight,
            }
            for f in report.findings
        ],
        "checks": [
            {
                "id": c.heuristic_id,
                "severity": c.severity.value,
                "title": c.title,
                "status": c.status,
                "reason": c.reason,
            }
            for c in report.checks
        ],
        "labels": get_all_labels(),
    }


@app.post("/labels/import")
async def import_labels_endpoint(file: UploadFile = File(...)):
    contents = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    try:
        n = import_labels(tmp_path)
    finally:
        os.unlink(tmp_path)
    return {"imported": n}


@app.get("/labels")
def list_labels():
    return get_all_labels()


@app.post("/labels")
def create_label(req: LabelRequest):
    add_label(req.txid, req.vout, req.label, req.tag)
    return {"ok": True}


@app.get("/")
def serve_index():
    return FileResponse(WEB_DIR / "index.html")


# Mount static assets last so API routes always take priority
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
