# PDF-translat (PDF 翻译工具)

这是一个基于 [PDFMathTranslate-next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next) 的 PDF 翻译项目，旨在提供简单、高效的 PDF 文档翻译体验，特别是在保留原始排版和公式方面表现出色。

## 🚀 快速开始 (Windows)

该项目已经为您准备好了便捷的启动脚本，您可以直接双击运行：

- **`start.bat`**: 启动官方 WebUI 界面。推荐大多数用户使用，提供完整的图形化配置。
- **`start_local.bat`**: 启动自定义后端服务 (`app.main_new`)。适合需要使用自定义接口或进行二次开发的场景。

## 🐳 Docker 部署

如果您更喜欢使用 Docker，我们也提供了完整的支持。

### 方式一：使用 Docker Compose (推荐)

一键启动 WebUI 和自定义 API：
```bash
docker-compose up -d
```
- **WebUI**: [http://localhost:7860](http://localhost:7860)
- **API**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 方式二：使用 Docker 命令

**启动官方 WebUI:**
```bash
docker build -t pdf-translator .
docker run -d -p 7860:7860 -v ${PWD}/uploads:/app/uploads -v ${PWD}/outputs:/app/outputs pdf-translator
```

**启动自定义 API:**
```bash
docker run -d -p 8000:8000 -v ${PWD}/uploads:/app/uploads -v ${PWD}/outputs:/app/outputs pdf-translator python -m uvicorn app.main_new:app --host 0.0.0.0 --port 8000
```

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

请根据您的系统环境选择以下安装方式：

### 1. 快捷安装 (推荐)
如果您在 Windows 上，可以直接运行以下脚本：
```powershell
# 运行安装脚本 (会自动创建环境并安装依赖)
./backend/script/setup.bat
```

### 2. 手动安装命令集 (通用)
如果您希望手动控制安装过程，请按顺序执行以下命令：

```bash
# 1. 克隆项目 (如果您还没有克隆)
git clone https://github.com/m20104600/PDF-translat.git
cd PDF-translat

# 2. 创建并激活虚拟环境 (可选但推荐)
python -m venv venv
# Windows 激活方式:
.\venv\Scripts\activate
# Linux/macOS 激活方式:
source venv/bin/activate

# 3. 安装核心依赖
pip install -e ./backend
```

## 🔗 项目链接

- **当前项目**: [m20104600/PDF-translat](https://github.com/m20104600/PDF-translat)
- **底层引擎**: [PDFMathTranslate-next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next)

---
> [!TIP]
> 您的上传文件 (`uploads/`) 和翻译结果 (`outputs/`) 均已在 `.gitignore` 中配置排除，不会被提交到公开仓库，保护您的隐私。
