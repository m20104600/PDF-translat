# PDF-translat (PDF 翻译工具)

这是一个基于 [PDFMathTranslate-next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next) 的 PDF 翻译项目，旨在提供简单、高效的 PDF 文档翻译体验，特别是在保留原始排版和公式方面表现出色。

## 🚀 快速开始 (Windows)

该项目已经为您准备好了便捷的启动脚本，您可以直接双击运行：

- **`start.bat`**: 启动官方 WebUI 界面。推荐大多数用户使用，提供完整的图形化配置。
- **`start_local.bat`**: 启动自定义后端服务 (`app.main_new`)。适合需要使用自定义接口或进行二次开发的场景。

## ✨ 主要功能

- **排版保留**：完美保留 PDF 原始布局、图片和复杂的数学公式。
- **多语言支持**：支持翻译为中文（简体/繁体）以及多种全球主流语言。
- **多引擎驱动**：支持接入多种主流 LLM API (如 OpenAI, SiliconFlow, Claude, Ollama, 阿里翻译等)。
- **交互友好**：简单易用的 Web 界面，拖拽上传即可开始翻译。

## 📂 项目结构

- `app/`: 包含自定义的 Python 逻辑和增强功能。
- `backend/`: 核心翻译引擎代码。
- `start.bat`: 官方 WebUI 启动入口。
- `start_local.bat`: 定制后端服务启动入口。
- `outputs/`: 翻译生成的 PDF 文件将自动存放在此。
- `uploads/`: 上传待翻译的文件存放处。

## 🛠️ 安装说明

1. **环境要求**：请确保您的系统中已安装 **Python 3.8 或更高版本**。
2. **依赖安装**：
   建议在项目根目录下运行以下命令安装依赖：
   ```bash
   pip install -e ./backend
   ```
   *(或者运行 `backend/script/setup.bat` 进行环境初始化)*

## 🔗 项目链接

- **当前项目**: [m20104600/PDF-translat](https://github.com/m20104600/PDF-translat)
- **底层引擎**: [PDFMathTranslate-next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next)

---
> [!TIP]
> 您的上传文件 (`uploads/`) 和翻译结果 (`outputs/`) 均已在 `.gitignore` 中配置排除，不会被提交到公开仓库，保护您的隐私。
