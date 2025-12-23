# PDF-translat (PDF 翻译工具)

这是一个基于 [PDFMathTranslate-next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next) 的 PDF 翻译项目，旨在提供简单、高效的 PDF 文档翻译体验，特别是在保留原始排版和公式方面表现出色。

## 🚀 快速开始 (Windows)

该项目已经为您准备好了便捷的启动脚本，您可以直接双击运行：

- **`start.bat`**: 启动官方 WebUI 界面。推荐大多数用户使用，提供完整的图形化配置。
- **`start_local.bat`**: 启动自定义后端服务 (`app.main_new`)。适合需要使用自定义接口或进行二次开发的场景。

## 🐳 Docker 部署

如果您更喜欢使用 Docker，我们也提供了完整的支持。

### 方式一：使用 Docker Compose (推荐)

一键启动 WebUI 和自定义 API 服务。您可以创建一个 `docker-compose.yml` 文件并粘贴以下内容：

```yaml
services:
  pdf-webui:
    image: m20104600/pdf-translator:latest # 或者使用本地 build: .
    container_name: pdf-translator-webui
    restart: always
    ports:
      - '7860:7860' # WebUI 访问端口
    volumes:
      - './data:/app/data' # 包含 webui/, api/, config/, sessions/, users.db
    environment:
      - 'PDF2ZH_UI_LANG=zh' # 界面语言

  pdf-api:
    image: m20104600/pdf-translator:latest
    container_name: pdf-translator-api
    restart: always
    ports:
      - '8000:8000' # API 访问端口
    command: ["python", "-m", "uvicorn", "app.main_new:app", "--host", "0.0.0.0", "--port", "8000"]
    volumes:
      - './data:/app/data' # 共享数据目录
    environment:
      - 'JWT_SECRET_KEY=change-this-in-production' # 生产环境请修改
```

**常用管理命令：**
```bash
# 启动所有服务 (后台运行)
docker-compose up -d

# 查看状态 / 日志
docker-compose ps
docker-compose logs -f

# 停止容器
docker-compose down
```

- **WebUI 访问地址**: [http://localhost:7860](http://localhost:7860)
- **API 访问地址**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 方式二：使用 Docker 命令

**启动官方 WebUI:**
```bash
docker build -t pdf-translator .
docker run -d -p 7860:7860 \
  -v ${PWD}/data:/app/data \
  -e PDF2ZH_UI_LANG=zh \
  pdf-translator
```

**启动自定义 API:**
```bash
docker run -d -p 8000:8000 \
  -v ${PWD}/data:/app/data \
  -e JWT_SECRET_KEY=your-secret-key \
  pdf-translator python -m uvicorn app.main_new:app --host 0.0.0.0 --port 8000
```

## ✨ 主要功能

- **排版保留**：完美保留 PDF 原始布局、图片和复杂的数学公式。
- **多语言支持**：支持翻译为中文（简体/繁体）以及多种全球主流语言。
- **多引擎驱动**：支持接入多种主流 LLM API (如 OpenAI, SiliconFlow, Claude, Ollama, 阿里翻译等)。
- **交互友好**：简单易用的 Web 界面，拖拽上传即可开始翻译。

## 📂 项目结构

- `app/`: 包含自定义的 Python 逻辑和增强功能。
  - `app/auth/`: 用户认证模块 (JWT)
  - `app/users/`: 用户管理模块
  - `app/files/`: 文件管理模块
  - `app/config/`: 配置管理模块
- `backend/`: 核心翻译引擎代码。
- `data/`: 数据目录（自动创建），包含：
  - `data/webui/`: WebUI 用户数据
  - `data/api/`: API 服务数据
  - `data/config/`: 用户配置文件
  - `data/sessions/`: 会话持久化
  - `data/users.db`: 用户数据库
- `start.bat`: 官方 WebUI 启动入口。
- `start_local.bat`: 定制后端服务启动入口。

## 🔐 用户系统

项目支持完整的多用户系统：

- **多用户支持**: 管理员和普通用户角色
- **首次设置向导**: 自动引导创建管理员账户
- **JWT 认证**: 安全的 Token 认证机制
- **会话管理**: 登录状态持久化，支持过期自动清理

## 📡 API 端点

访问 `http://localhost:8000/docs` 查看完整的交互式 API 文档。

### 认证 (`/auth`)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/auth/status` | GET | 检查系统初始化状态 |
| `/auth/setup` | POST | 首次创建管理员 |
| `/auth/register` | POST | 用户注册 |
| `/auth/login` | POST | 登录获取 Token |
| `/auth/refresh` | POST | 刷新 Token |
| `/auth/me` | GET | 当前用户信息 |

### 配置 (`/config`)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/config/` | GET | 获取用户配置 |
| `/config/` | PUT | 更新配置 |
| `/config/export` | GET | 导出 JSON |
| `/config/import` | POST | 导入 JSON |
| `/config/service` | PATCH | 快捷切换翻译服务 |

### 文件 (`/files`)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/files/history` | GET | 个人翻译历史 |
| `/files/history/all` | GET | 全部历史 (管理员) |
| `/files/download/{id}/mono` | GET | 下载单语版 |
| `/files/download/{id}/dual` | GET | 下载双语版 |
| `/files/{id}` | DELETE | 删除文件 |

### 管理员 (`/admin`)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/admin/users` | GET | 用户列表 + 存储统计 |
| `/admin/stats` | GET | 系统总览 |
| `/admin/users/{id}` | DELETE | 删除用户 |
| `/admin/settings` | PATCH | 控制注册开关 |

## 🌐 支持的翻译服务

- **SiliconFlow Free** (默认)
- **OpenAI** (GPT-4/GPT-4o)
- **Azure AI**
- **Gemini**
- 更多服务可通过配置扩展

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
> 您的数据目录 (`data/`) 已在 `.gitignore` 中配置排除，包含的上传文件和翻译结果不会被提交到公开仓库，保护您的隐私。
> 
> [!NOTE]
> `data/` 目录及其子目录会在首次运行时自动创建，无需手动操作。
