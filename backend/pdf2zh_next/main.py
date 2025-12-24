#!/usr/bin/env python3
"""A command line tool for extracting text and images from PDF and
output it to plain text, html, xml or tags.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import babeldoc.assets.assets

from pdf2zh_next.config import ConfigManager
from pdf2zh_next.high_level import do_translate_file_async

__version__ = "2.8.1"

logger = logging.getLogger(__name__)


def find_all_files_in_directory(directory_path):
    """
    Recursively search all PDF files in the given directory and return their paths as a list.

    :param directory_path: str, the path to the directory to search
    :return: list of PDF file paths
    """
    directory_path = Path(directory_path)
    # Check if the provided path is a directory
    if not directory_path.is_dir():
        raise ValueError(f"The provided path '{directory_path}' is not a directory.")

    file_paths = []

    # Walk through the directory recursively
    for root, _, files in os.walk(directory_path):
        for file in files:
            # Check if the file is a PDF
            if file.lower().endswith(".pdf"):
                # Append the full file path to the list
                file_paths.append(Path(root) / file)

    return file_paths


async def main() -> int:
    from rich.logging import RichHandler

    logging.basicConfig(level=logging.INFO, handlers=[RichHandler()])

    settings = ConfigManager().initialize_config()
    if settings.basic.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # disable httpx, openai, httpcore, http11 logs
    logging.getLogger("httpx").setLevel("CRITICAL")
    logging.getLogger("httpx").propagate = False
    logging.getLogger("openai").setLevel("CRITICAL")
    logging.getLogger("openai").propagate = False
    logging.getLogger("httpcore").setLevel("CRITICAL")
    logging.getLogger("httpcore").propagate = False
    logging.getLogger("http11").setLevel("CRITICAL")
    logging.getLogger("http11").propagate = False

    for v in logging.Logger.manager.loggerDict.values():
        if getattr(v, "name", None) is None:
            continue
        if (
            v.name.startswith("pdfminer")
            or v.name.startswith("peewee")
            or v.name.startswith("httpx")
            or "http11" in v.name
            or "openai" in v.name
            or "pdfminer" in v.name
        ):
            v.disabled = True
            v.propagate = False

    logger.debug(f"settings: {settings}")

    if settings.basic.version:
        print(f"pdf2zh-next version: {__version__}")
        return 0

    logger.info("Warmup babeldoc assets...")
    
    # Try to load proxy settings from any user's config to help with warmup
    try:
        import json
        data_dir = Path(os.getcwd()) / "data" / "webui" / "users"
        if data_dir.exists():
            for user_dir in data_dir.iterdir():
                if user_dir.is_dir():
                    settings_file = user_dir / "settings.json"
                    if settings_file.exists():
                        try:
                            settings = json.loads(settings_file.read_text(encoding='utf-8'))
                            proxy = settings.get("universal_proxy") or settings.get("socks_proxy")
                            if proxy:
                                logger.info(f"Applying proxy from user {user_dir.name} for warmup: {proxy}")
                                os.environ["HTTP_PROXY"] = proxy
                                os.environ["HTTPS_PROXY"] = proxy
                                os.environ["http_proxy"] = proxy
                                os.environ["https_proxy"] = proxy
                                break # Use the first valid proxy found
                        except Exception:
                            pass
    except Exception as e:
        logger.warning(f"Failed to load proxy settings: {e}")

    babeldoc.assets.assets.warmup()

    if settings.basic.gui:
        # 检查是否使用原版 Gradio UI（通过 --gradio 参数）
        use_gradio = '--gradio' in sys.argv or os.environ.get('PDF2ZH_USE_GRADIO') == '1'
        
        if use_gradio:
            # 原版 Gradio UI
            logger.info("启动原版 Gradio UI...")
            from pdf2zh_next.gui import setup_gui

            setup_gui(
                auth_file=settings.gui_settings.auth_file,
                welcome_page=settings.gui_settings.welcome_page,
                server_port=settings.gui_settings.server_port,
            )
            return 0
        
        # 新版 Web UI（带用户认证，默认）
        logger.info("启动新版 Web UI（带用户认证）...")
        from pdf2zh_next.web_api import app
        
        port = settings.gui_settings.server_port
        logger.info(f"Web UI 地址: http://localhost:{port}")
        logger.info("如需使用原版 Gradio UI，请添加 --gradio 参数")
        
        # 使用 uvicorn 异步服务器
        import uvicorn
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
        return 0

    assert len(settings.basic.input_files) >= 1, "At least one input file is required"
    await do_translate_file_async(settings, ignore_error=True)
    return 0


def cli():
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    cli()
