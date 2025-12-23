import os
import uuid
import shutil
import asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import from the new backend package
# Note: These imports assume 'backend' is installed or in python path
from pdf2zh_next.high_level import do_translate_async_stream
from pdf2zh_next.config.model import SettingsModel, BasicSettings, TranslationSettings, PDFSettings
from pdf2zh_next.config.translate_engine_model import SiliconFlowFreeSettings

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store tasks in memory
TASKS = {}
DATA_DIR = Path("data")
API_DATA_DIR = DATA_DIR / "api"
UPLOAD_DIR = API_DATA_DIR / "uploads"
OUTPUT_DIR = API_DATA_DIR / "outputs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
API_DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

async def run_translation_task(task_id: str, file_path: Path, settings: SettingsModel):
    """
    Background task to run the translation stream and update task status.
    """
    TASKS[task_id]["status"] = "processing"
    TASKS[task_id]["progress"] = 0
    
    print(f"Starting translation for task {task_id}")
    
    try:
        # Generate output directory for this task to avoid collisions
        task_output_dir = OUTPUT_DIR / task_id
        task_output_dir.mkdir(exist_ok=True, parents=True)
        
        # Update settings to output to this directory
        settings.translation.output = str(task_output_dir)

        async for event in do_translate_async_stream(settings, file_path):
            event_type = event.get("type")
            
            if event_type == "stage_summary":
                pass # Can log stages if needed
                
            elif event_type in ["progress_start", "progress_update", "progress_end"]:
                overall = event.get("overall_progress", 0)
                TASKS[task_id]["progress"] = overall
                # print(f"Task {task_id} progress: {overall}%")
                
            elif event_type == "finish":
                result = event["translate_result"]
                TASKS[task_id]["status"] = "completed"
                TASKS[task_id]["progress"] = 100
                
                # We prefer dual (bilingual) PDF if available, else mono
                # The result object has paths.
                # Note: result paths might be relative to CWD or absolute.
                
                dual_path = getattr(result, "dual_pdf_path", None)
                mono_path = getattr(result, "mono_pdf_path", None)
                
                final_path = dual_path if dual_path else mono_path
                
                if final_path:
                    TASKS[task_id]["output_path"] = str(final_path)
                else:
                    TASKS[task_id]["error"] = "Translation finished but no output file found."
                    TASKS[task_id]["status"] = "failed"
                
                print(f"Task {task_id} completed. Output: {final_path}")
                break
                
            elif event_type == "error":
                error_msg = event.get("error", "Unknown error")
                TASKS[task_id]["status"] = "failed"
                TASKS[task_id]["error"] = error_msg
                print(f"Task {task_id} error: {error_msg}")
    
    except Exception as e:
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["error"] = str(e)
        print(f"Task {task_id} exception: {e}")

@app.post("/api/translate")
async def translate_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_lang: str = "zh"
):
    task_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{task_id}_{file.filename}"
    
    # Save uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Configure Settings
    # We use SiliconFlowFree as requested/planned
    
    engine_settings = SiliconFlowFreeSettings()
    
    settings = SettingsModel(
        basic=BasicSettings(),
        translation=TranslationSettings(
            lang_in="auto", # Requesting auto-detection if possible, or 'en'
            lang_out=target_lang,
            ignore_cache=True # Ensure fresh translation
        ),
        pdf=PDFSettings(),
        translate_engine_settings=engine_settings
    )
    
    # Initialize task state
    TASKS[task_id] = {
        "status": "queued",
        "progress": 0,
        "file_name": file.filename,
        "source_path": str(file_path),
        "output_path": None,
        "error": None
    }
    
    background_tasks.add_task(run_translation_task, task_id, file_path, settings)
    
    return {"task_id": task_id}

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    return TASKS[task_id]

@app.get("/api/download/{task_id}")
async def download_pdf(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = TASKS[task_id]
    if task["status"] != "completed" or not task["output_path"]:
        raise HTTPException(status_code=400, detail="Translation not ready")
        
    return FileResponse(
        task["output_path"],
        media_type="application/pdf",
        filename=f"translated_{task['file_name']}",
        content_disposition_type="inline"
    )

@app.get("/api/source/{task_id}")
async def get_source_pdf(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = TASKS[task_id]
    if not task["source_path"]:
        raise HTTPException(status_code=404, detail="Source file not found")
        
    return FileResponse(
        task["source_path"],
        media_type="application/pdf",
        filename=task["file_name"],
        content_disposition_type="inline"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
