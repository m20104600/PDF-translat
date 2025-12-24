"""
FastAPI-based Web API for PDF Translator with user authentication.

This module provides:
- Authentication endpoints (login, register, logout)
- User settings management
- File upload and translation
- Translation history management
"""

import asyncio
import json
import logging
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pdf2zh_next.auth import AuthenticationError, UserManager
from pdf2zh_next.config import ConfigManager
from pdf2zh_next.high_level import do_translate_async_stream

__version__ = "2.0.0"

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="PDF Translator API", version=__version__)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize user manager
user_manager = UserManager()

# In-memory storage for active translation tasks
active_tasks = {}


# Pydantic models for request/response
class SetupRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class TranslationSettings(BaseModel):
    service: str = "SiliconFlow (Free)"
    lang_from: str = "English"
    lang_to: str = "Simplified Chinese"


def get_engine_settings(service_type: str, user_settings: dict):
    """根据服务类型返回对应的翻译引擎配置"""
    from pdf2zh_next.config.translate_engine_model import (
        SiliconFlowFreeSettings,
        OpenAISettings,
        GeminiSettings,
        DeepLSettings,
        OllamaSettings,
        AzureOpenAISettings,
        AzureSettings,
        DeepSeekSettings,
    )

    # 从用户设置中提取通用字段
    api_key = user_settings.get("api_key", "")
    model = user_settings.get("model", "")
    base_url = user_settings.get("base_url", "")
    endpoint = user_settings.get("endpoint", "")
    host = user_settings.get("host", "")
    temperature = user_settings.get("temperature", "")
    timeout = user_settings.get("timeout", "")
    api_version = user_settings.get("api_version", "")
    num_predict = user_settings.get("num_predict", "")

    if service_type == "openai":
        return OpenAISettings(
            openai_api_key=api_key,
            openai_model=model or "gpt-4o-mini",
            openai_base_url=base_url if base_url else None,
            openai_temperature=temperature if temperature else None,
            openai_timeout=timeout if timeout else None
        )
    elif service_type == "azure_openai":
        return AzureOpenAISettings(
            azure_openai_api_key=api_key,
            azure_openai_base_url=base_url,
            azure_openai_model=model or "gpt-4o-mini",
            azure_openai_api_version=api_version or "2024-06-01"
        )
    elif service_type == "gemini":
        return GeminiSettings(
            gemini_api_key=api_key,
            gemini_model=model or "gemini-1.5-flash"
        )
    elif service_type == "deepl":
        return DeepLSettings(
            deepl_auth_key=api_key
        )
    elif service_type == "ollama":
        return OllamaSettings(
            ollama_host=host or "http://localhost:11434",
            ollama_model=model or "gemma2",
            num_predict=int(num_predict) if num_predict else 2000
        )
    elif service_type == "azure":
        return AzureSettings(
            azure_api_key=api_key,
            azure_endpoint=endpoint or "https://api.translator.azure.cn"
        )
    elif service_type == "deepseek":
        return DeepSeekSettings(
            deepseek_api_key=api_key,
            deepseek_model=model or "deepseek-chat"
        )
    else:
        # 默认使用免费的 SiliconFlow
        return SiliconFlowFreeSettings()


# Dependency to get current user from token
async def get_current_user(authorization: str = Header(None)) -> dict:
    """Extract and validate user from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.replace("Bearer ", "")
    user_data = user_manager.validate_token(token)

    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user_data


async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency to require admin access"""
    if not current_user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ============ Authentication endpoints ============

@app.get("/api/auth/status")
async def check_auth_status():
    """Check if initial setup is required"""
    return {
        "setup_required": not user_manager.has_users(),
        "version": __version__
    }


@app.post("/api/auth/setup")
async def initial_setup(request: SetupRequest):
    """Create the first admin user"""
    if user_manager.has_users():
        raise HTTPException(status_code=400, detail="Setup already completed")

    try:
        user_manager.create_user(request.username, request.password, is_admin=True)
        token = user_manager.authenticate(request.username, request.password)

        return {
            "success": True,
            "token": token,
            "username": request.username,
            "is_admin": True
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Authenticate user and return session token"""
    token = user_manager.authenticate(request.username, request.password)

    if not token:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Get user info
    user_data = user_manager.validate_token(token)

    return {
        "success": True,
        "token": token,
        "username": user_data['username'],
        "is_admin": user_data['is_admin']
    }


@app.get("/api/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    return current_user


@app.post("/api/auth/logout")
async def logout(current_user: dict = Depends(get_current_user), authorization: str = Header(None)):
    """Logout current user"""
    token = authorization.replace("Bearer ", "")
    user_manager.logout(token)

    return {"success": True, "message": "Logged out successfully"}


@app.post("/api/auth/register")
async def register_user(
    request: RegisterRequest, 
    authorization: str = Header(None)
):
    """
    Register a new user.
    If registration is open, anyone can register.
    If closed, only admins can register new users.
    """
    registration_enabled = user_manager.get_registration_enabled()
    
    # If registration is disabled, check for admin token
    if not registration_enabled:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=403, detail="Registration is disabled. Admin access required.")
        
        token = authorization.replace("Bearer ", "")
        user_data = user_manager.validate_token(token)
        if not user_data or not user_data.get('is_admin'):
             raise HTTPException(status_code=403, detail="Admin access required")

    try:
        user_manager.create_user(request.username, request.password, is_admin=False)
        return {"success": True, "message": f"User '{request.username}' created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/auth/users")
async def list_users(admin_user: dict = Depends(get_admin_user)):
    """List all users (admin only)"""
    try:
        users = user_manager.list_users(admin_user['username'])
        return {"success": True, "users": users}
    except AuthenticationError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.delete("/api/admin/users/{username}")
async def delete_user(username: str, admin_user: dict = Depends(get_admin_user)):
    """Delete a user (admin only)"""
    try:
        user_manager.delete_user(username, admin_user['username'])
        return {"success": True, "message": f"User '{username}' deleted"}
    except (ValueError, AuthenticationError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/settings")
async def get_admin_settings(admin_user: dict = Depends(get_admin_user)):
    """Get system settings (admin only)"""
    return {
        "success": True,
        "settings": {
            "allow_registration": user_manager.get_registration_enabled()
        }
    }


class AdminSettingsRequest(BaseModel):
    allow_registration: bool


@app.post("/api/admin/settings")
async def update_admin_settings(request: AdminSettingsRequest, admin_user: dict = Depends(get_admin_user)):
    """Update system settings (admin only)"""
    try:
        user_manager.set_registration_enabled(request.allow_registration, admin_user['username'])
        return {"success": True, "message": "Settings updated"}
    except AuthenticationError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.get("/api/admin/stats")
async def get_system_stats(admin_user: dict = Depends(get_admin_user)):
    """Get system statistics (admin only)"""
    try:
        users = user_manager.list_users(admin_user['username'])
        total_users = len(users)
        
        # Calculate storage usage (approximate)
        import shutil
        total, used, free = shutil.disk_usage("data")
        
        # Count total active tasks
        active_count = len(active_tasks)
        
        return {
            "success": True, 
            "stats": {
                "total_users": total_users,
                "active_tasks": active_count,
                "disk_usage_gb": f"{used / (1024**3):.2f} / {total / (1024**3):.2f} GB"
            }
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {"success": False, "error": str(e)}


@app.delete("/api/auth/users/{username}")
async def delete_user(username: str, admin_user: dict = Depends(get_admin_user)):
    """Delete a user (admin only)"""
    try:
        user_manager.delete_user(username, admin_user['username'])
        return {"success": True, "message": f"User '{username}' deleted successfully"}
    except (AuthenticationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/auth/registration-status")
async def get_registration_status():
    """Check if user registration is enabled (public endpoint)"""
    enabled = user_manager.get_registration_enabled()
    return {"success": True, "enabled": enabled}


@app.post("/api/auth/registration-toggle")
async def toggle_registration(request: dict, admin_user: dict = Depends(get_admin_user)):
    """Enable or disable user registration (admin only)"""
    try:
        enabled = request.get('enabled', False)
        user_manager.set_registration_enabled(enabled, admin_user['username'])
        return {"success": True, "enabled": enabled, "message": f"Registration {'enabled' if enabled else 'disabled'}"}
    except AuthenticationError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.post("/api/auth/register/public")
async def register_public(request: RegisterRequest):
    """Public user registration endpoint (only works if registration is enabled)"""
    # Check if registration is enabled
    if not user_manager.get_registration_enabled():
        raise HTTPException(
            status_code=403,
            detail="User registration is currently disabled. Please contact an administrator."
        )

    try:
        user_manager.create_user(request.username, request.password, is_admin=False)

        # Automatically log in the new user
        token = user_manager.authenticate(request.username, request.password)
        user_data = user_manager.validate_token(token)

        return {
            "success": True,
            "token": token,
            "username": user_data['username'],
            "is_admin": user_data['is_admin'],
            "message": f"User '{request.username}' registered successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/change-password")
async def change_password(request: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """Change current user's password"""
    try:
        user_manager.change_password(
            current_user['username'],
            request.old_password,
            request.new_password
        )
        return {"success": True, "message": "Password changed successfully. Please login again."}
    except (AuthenticationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============ Settings endpoints ============

@app.get("/api/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    """Get user settings"""
    user_dir = user_manager.get_user_dir(current_user['username'])
    settings_file = user_dir / "settings.json"

    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    else:
        settings = {}

    return {"success": True, "settings": settings}


@app.post("/api/settings")
async def save_settings(settings: dict, current_user: dict = Depends(get_current_user)):
    """Save user settings"""
    user_dir = user_manager.get_user_dir(current_user['username'])
    settings_file = user_dir / "settings.json"

    settings_file.write_text(json.dumps(settings, indent=2))

    return {"success": True, "message": "Settings saved"}


# ============ File upload and translation endpoints ============

@app.post("/api/translate/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a file for translation"""
    user_dir = user_manager.get_user_dir(current_user['username'])
    uploads_dir = user_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique file ID
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{file.filename}"
    file_path = uploads_dir / filename

    # Save uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "success": True,
        "file_id": file_id,
        "filename": file.filename,
        "size": os.path.getsize(file_path)
    }


@app.post("/api/translate/start")
async def start_translation(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """Start a translation task"""
    file_id = request.get("file_id")
    if not file_id:
        raise HTTPException(status_code=400, detail="Missing file_id")

    user_dir = user_manager.get_user_dir(current_user['username'])
    uploads_dir = user_dir / "uploads"
    outputs_dir = user_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Find the uploaded file
    matching_files = list(uploads_dir.glob(f"{file_id}_*"))
    if not matching_files:
        raise HTTPException(status_code=404, detail="Uploaded file not found")

    file_path = matching_files[0]
    task_id = str(uuid.uuid4())
    task_output_dir = outputs_dir / task_id
    task_output_dir.mkdir(parents=True, exist_ok=True)

    # Get translation settings
    lang_from = request.get("lang_from", "English")
    lang_to = request.get("lang_to", "Simplified Chinese")
    service = request.get("service", "SiliconFlow (Free)")

    # Create task entry
    active_tasks[task_id] = {
        "username": current_user['username'],
        "file_id": file_id,
        "original_filename": file_path.name,
        "status": "queued",
        "progress": 0,
        "output_files": {},
        "error": None,
        "lang_from": lang_from,
        "lang_to": lang_to,
        "service": service
    }

    # Start translation in background
    asyncio.create_task(run_translation_task(
        task_id, file_path, task_output_dir, lang_from, lang_to, service, current_user['username']
    ))

    return {
        "success": True,
        "task_id": task_id,
        "message": "Translation started"
    }


async def run_translation_task(
    task_id: str,
    file_path: Path,
    output_dir: Path,
    lang_from: str,
    lang_to: str,
    service: str,
    username: str
):
    """Background task to run translation"""
    from pdf2zh_next.config.model import (
        BasicSettings,
        PDFSettings,
        SettingsModel,
        TranslationSettings,
    )

    active_tasks[task_id]["status"] = "processing"
    active_tasks[task_id]["progress"] = 0

    logger.info(f"Starting translation for task {task_id}")

    try:
        # 读取用户保存的服务配置
        user_dir = user_manager.get_user_dir(username)
        settings_file = user_dir / "settings.json"
        user_settings = {}
        if settings_file.exists():
            user_settings = json.loads(settings_file.read_text())

        # 设置代理 (如果存在)
        universal_proxy = user_settings.get("universal_proxy")
        socks_proxy = user_settings.get("socks_proxy")
        
        # 临时设置环境变量，任务结束后恢复
        original_environ = os.environ.copy()
        
        # 逻辑：优先使用通用代理，如果没有通用代理但有SOCKS代理，则通过SOCKS代理所有的HTTP/HTTPS流量
        primary_proxy = universal_proxy if universal_proxy else socks_proxy
        
        if primary_proxy:
            os.environ["HTTP_PROXY"] = primary_proxy
            os.environ["http_proxy"] = primary_proxy
            os.environ["HTTPS_PROXY"] = primary_proxy
            os.environ["https_proxy"] = primary_proxy
            
        if socks_proxy:
            os.environ["SOCKS_PROXY"] = socks_proxy
            os.environ["socks_proxy"] = socks_proxy

        logger.info(f"Using proxy configuration: Universal={universal_proxy}, SOCKS={socks_proxy}")

        # 根据服务类型配置翻译引擎
        service_type = user_settings.get("service", "siliconflow_free")
        engine_settings = get_engine_settings(service_type, user_settings)

        settings = SettingsModel(
            basic=BasicSettings(),
            translation=TranslationSettings(
                lang_in="auto",
                lang_out="zh" if "Chinese" in lang_to else lang_to.lower()[:2],
                ignore_cache=True,
                output=str(output_dir)
            ),
            pdf=PDFSettings(),
            translate_engine_settings=engine_settings
        )

        async for event in do_translate_async_stream(settings, file_path):
            event_type = event.get("type")

            if event_type in ["progress_start", "progress_update", "progress_end"]:
                overall = event.get("overall_progress", 0)
                active_tasks[task_id]["progress"] = overall

            elif event_type == "finish":
                result = event["translate_result"]
                active_tasks[task_id]["status"] = "completed"
                active_tasks[task_id]["progress"] = 100

                # Get output file paths
                dual_path = getattr(result, "dual_pdf_path", None)
                mono_path = getattr(result, "mono_pdf_path", None)

                if dual_path:
                    active_tasks[task_id]["output_files"]["dual"] = str(dual_path)
                if mono_path:
                    active_tasks[task_id]["output_files"]["mono"] = str(mono_path)

                if not dual_path and not mono_path:
                    active_tasks[task_id]["error"] = "Translation finished but no output file found."
                    active_tasks[task_id]["status"] = "failed"

                logger.info(f"Task {task_id} completed. Outputs: mono={mono_path}, dual={dual_path}")

                # Save to history
                await save_to_history(task_id, username)
                break

            elif event_type == "error":
                error_msg = event.get("error", "Unknown error")
                active_tasks[task_id]["status"] = "failed"
                active_tasks[task_id]["error"] = error_msg
                logger.error(f"Task {task_id} error: {error_msg}")

    except Exception as e:
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)
        logger.exception(f"Task {task_id} exception: {e}")
    finally:
        # 恢复环境变量
        os.environ.clear()
        os.environ.update(original_environ)


async def save_to_history(task_id: str, username: str):
    """Save task to user's history"""
    user_dir = user_manager.get_user_dir(username)
    history_file = user_dir / "history.json"

    if history_file.exists():
        history = json.loads(history_file.read_text())
    else:
        history = []

    task = active_tasks.get(task_id, {})
    history_entry = {
        "task_id": task_id,
        "file_id": task.get("file_id"),
        "original_filename": task.get("original_filename"),
        "status": task.get("status"),
        "lang_from": task.get("lang_from"),
        "lang_to": task.get("lang_to"),
        "service": task.get("service"),
        "output_files": task.get("output_files", {}),
        "created_at": str(Path(user_dir / "outputs" / task_id).stat().st_mtime if (user_dir / "outputs" / task_id).exists() else "")
    }

    history.insert(0, history_entry)
    history_file.write_text(json.dumps(history, indent=2))


@app.get("/api/translate/status/{task_id}")
async def get_translation_status(task_id: str, current_user: dict = Depends(get_current_user)):
    """Get translation task status"""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = active_tasks[task_id]

    # Verify task belongs to current user
    if task["username"] != current_user['username']:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "success": True,
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "output_files": task["output_files"],
        "error": task["error"]
    }


@app.get("/api/translate/history")
async def get_translation_history(current_user: dict = Depends(get_current_user)):
    """Get user's translation history"""
    user_dir = user_manager.get_user_dir(current_user['username'])
    history_file = user_dir / "history.json"

    if history_file.exists():
        history = json.loads(history_file.read_text())
    else:
        history = []

    return {"success": True, "history": history}


@app.delete("/api/translate/history/{task_id}")
async def delete_history_item(task_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a history item and its associated files"""
    user_dir = user_manager.get_user_dir(current_user['username'])
    history_file = user_dir / "history.json"

    if not history_file.exists():
        raise HTTPException(status_code=404, detail="History not found")

    history = json.loads(history_file.read_text())

    # Find the history item
    item_to_delete = None
    for item in history:
        if item.get('task_id') == task_id:
            item_to_delete = item
            break

    if not item_to_delete:
        raise HTTPException(status_code=404, detail="History item not found")

    # Delete output directory (translated files)
    output_dir = user_dir / "outputs" / task_id
    if output_dir.exists():
        shutil.rmtree(output_dir)
        logger.info(f"Deleted output directory: {output_dir}")

    # Delete original uploaded file if we can find it
    file_id = item_to_delete.get('file_id')
    if file_id:
        upload_dir = user_dir / "uploads"
        matching_files = list(upload_dir.glob(f"{file_id}_*"))
        for f in matching_files:
            f.unlink()
            logger.info(f"Deleted uploaded file: {f}")

    # Remove from history
    history = [item for item in history if item.get('task_id') != task_id]
    history_file.write_text(json.dumps(history, indent=2))

    # Remove from active_tasks if exists
    if task_id in active_tasks:
        del active_tasks[task_id]

    return {"success": True, "message": "History item deleted"}


@app.get("/api/translate/download/{task_id}")
async def download_translation(
    task_id: str,
    file_type: str = "mono",
    current_user: dict = Depends(get_current_user)
):
    """Download a translated file"""
    if task_id in active_tasks:
        task = active_tasks[task_id]
        if task["username"] != current_user['username']:
            raise HTTPException(status_code=403, detail="Access denied")
        if task["status"] != "completed":
            raise HTTPException(status_code=400, detail="Translation not completed")
    else:
        # Fallback to history
        user_dir = user_manager.get_user_dir(current_user['username'])
        history_file = user_dir / "history.json"
        
        found_in_history = False
        if history_file.exists():
            try:
                history = json.loads(history_file.read_text())
                for item in history:
                    if item.get("task_id") == task_id:
                        task = item
                        found_in_history = True
                        break
            except Exception as e:
                logger.error(f"Error reading history: {e}")
        
        if not found_in_history:
             raise HTTPException(status_code=404, detail="Task not found")

    # Get file path
    output_files = task.get("output_files", {})
    file_path = output_files.get(file_type)

    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Generate clean filename
    original_filename = task.get("original_filename", "translated")
    if original_filename.lower().endswith('.pdf'):
        original_filename = original_filename[:-4]
    if '_' in original_filename:
        parts = original_filename.split('_', 1)
        if len(parts[0]) >= 32:
            original_filename = parts[1] if len(parts) > 1 else original_filename
    clean_name = re.sub(r'[^\w\-\u4e00-\u9fff\.]', '_', original_filename)
    download_filename = f"{clean_name}_{file_type}.pdf"

    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=download_filename
    )


# ============ Serve static files (frontend) ============

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    # Mount CSS and JS directories
    css_dir = static_dir / "css"
    js_dir = static_dir / "js"

    if css_dir.exists():
        app.mount("/static/css", StaticFiles(directory=str(css_dir)), name="css")
    if js_dir.exists():
        app.mount("/static/js", StaticFiles(directory=str(js_dir)), name="js")

    # Serve HTML files from static root
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static_html")

    # Serve root HTML files
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="root")


# ============ Startup/Shutdown events ============

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("PDF Translator Web API starting...")
    # Cleanup expired sessions
    user_manager.cleanup_expired_sessions()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("PDF Translator Web API shutting down...")
