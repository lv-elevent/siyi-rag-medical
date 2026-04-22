# RAG Knowledge Base

一个最小可用的智能知识库问答系统，支持 PDF 上传、文本解析、向量入库与基于知识库的问答。

## 项目简介

本项目是一个单文档版 RAG（Retrieval-Augmented Generation，检索增强生成）问答系统。

用户可以上传 PDF 文档，系统会自动完成：

- PDF 文本解析
- 文本分块
- Embedding 生成
- 向量入库（ChromaDB）
- 基于知识库内容的问答

当前版本重点是完成第一版可运行原型，适合学习 RAG 基本链路，也适合作为个人项目展示。

---

## 当前已实现功能

- PDF 文件上传
- PDF 文本解析
- 文本分块
- Embedding 生成
- ChromaDB 向量入库
- 基于知识库的问答
- 简短来源展示
- 无关问题兜底回复

---

## 当前限制

- 仅支持 PDF 文件
- 当前为单文档知识库
- 上传新文档时会清空旧知识库
- 暂不支持多轮对话
- 暂不支持多文档同时检索
- 暂不支持流式输出
- 暂不支持用户系统

---

## 快速开始

### 环境要求

- Python 3.9+
- pip 包管理器

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd rag-knowledgebase
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的配置
# 特别是 OPENAI_API_KEY
```

4. **创建必要的目录**
```bash
# 创建上传目录
mkdir uploads

# 创建向量数据库目录（会在首次运行时自动创建）
```

### 本地启动

**启动后端服务**
```bash
# 激活虚拟环境（如果有）
.venv\Scripts\activate

# 启动后端
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**启动前端服务**（新终端窗口）
```bash
# 进入前端目录
cd frontend

# 启动前端（使用 Python 服务器）
python -m http.server 3000
```

### 访问应用

- **前端界面**：http://127.0.0.1:3000
- **后端 API**：http://127.0.0.1:8000
- **API 文档**：http://127.0.0.1:8000/docs
- **Swagger UI**：http://127.0.0.1:8000/docs
- **ReDoc**：http://127.0.0.1:8000/redoc

---

## 环境变量说明

`.env` 文件中的配置项：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| OPENAI_API_KEY | OpenAI 兼容 API 的 API Key | `sk-xxxxx` |
| OPENAI_BASE_URL | API 基础 URL | `https://api.siliconflow.cn/v1` |
| LLM_MODEL | 使用的 LLM 模型 | `Qwen/Qwen2.5-7B-Instruct` |
| EMBEDDING_MODEL | 使用的 Embedding 模型 | `BAAI/bge-large-zh-v1.5` |
| CHROMA_COLLECTION_NAME | ChromaDB 集合名称 | `rag_docs` |

### 推荐的 LLM 模型

- **中文问答**：`Qwen/Qwen2.5-7B-Instruct`（推荐）
- **通用问答**：`gpt-3.5-turbo`
- **中文增强**：`Qwen/Qwen2.5-72B-Instruct`

### 推荐的 Embedding 模型

- **中文**：`BAAI/bge-large-zh-v1.5`（推荐）
- **英文**：`openai/text-embedding-ada-002`

---

## 主要接口说明

### 1. PDF 上传接口

**接口路径**：`POST /upload`

**请求**：
- Content-Type: `multipart/form-data`
- 字段：`file`（PDF 文件）

**响应**：
```json
{
  "document_id": "doc_xxxxx",
  "filename": "test.pdf",
  "status": "success",
  "message": "上传成功"
}
```

**说明**：
- 上传后会自动完成 PDF 解析、文本分块、Embedding 生成和向量入库
- 每次上传新文档时会清空旧知识库
- 上传过程中状态会从 "empty" → "processing" → "ready"

---

### 2. 知识库状态查询接口

**接口路径**：`GET /knowledge/status`

**请求**：无

**响应**：
```json
{
  "has_document": true,
  "filename": "test.pdf",
  "status": "ready"
}
```

**状态说明**：
- `empty`：没有上传文档
- `processing`：文档正在处理中
- `ready`：文档已处理完成，可以问答

---

### 3. 问答接口

**接口路径**：`POST /chat`

**请求**：
```json
{
  "question": "你想问什么？"
}
```

**响应**：
```json
{
  "answer": "基于知识库的回答内容...",
  "status": "success"
}
```

**说明**：
- 系统会先从向量数据库中检索相关内容
- 然后使用 LLM 生成基于知识库的回答
- 如果知识库中没有相关信息，会返回"知识库未收录相关内容"

---

## 项目结构

```
rag-knowledgebase/
├── backend/                    # 后端代码
│   ├── api/                    # API 路由
│   │   ├── upload.py          # 上传接口
│   │   ├── chat.py            # 问答接口
│   │   └── knowledge_status.py # 状态查询接口
│   ├── core/                   # 核心配置
│   │   ├── config.py          # 配置文件
│   │   ├── embedding_client.py # Embedding 客户端
│   │   └── llm_client.py      # LLM 客户端
│   ├── models/                 # 数据模型
│   │   ├── upload.py          # 上传响应模型
│   │   ├── chat.py            # 问答请求/响应模型
│   │   └── knowledge_status.py # 状态响应模型
│   ├── repositories/          # 数据访问层
│   │   └── vector_repository.py # 向量数据库操作
│   ├── services/              # 业务逻辑
│   │   ├── pdf_parser.py      # PDF 解析服务
│   │   └── text_chunker.py    # 文本分块服务
│   └── main.py                # 应用入口
├── frontend/                   # 前端代码
│   ├── index.html             # 页面结构
│   ├── styles.css             # 样式文件
│   └── script.js              # 业务逻辑
├── uploads/                    # PDF 上传目录
├── chroma_db/                  # ChromaDB 向量数据库
├── docs/                       # 文档目录
│   └── mvp_baseline_test.md   # 基线验证流程
├── .env.example               # 环境变量模板
├── .gitignore                 # Git 忽略文件
├── requirements.txt           # Python 依赖
└── README.md                  # 项目说明
```

---

## 开发指南

### 添加新功能

1. 在 `backend/` 下创建对应的服务或模块
2. 在 `backend/api/` 下添加新的路由
3. 在 `backend/models/` 下添加数据模型
4. 在前端 `frontend/` 下添加相应的 UI 交互
5. 更新本文档

### 调试技巧

1. **查看后端日志**：后端控制台会输出详细的处理日志
2. **检查向量数据库**：使用 ChromaDB 客户端查询向量集合
3. **查看 API 文档**：访问 http://127.0.0.1:8000/docs 测试接口

### 常见问题

**Q: 上传后状态一直是 processing？**
A: 检查后端日志，可能是 PDF 解析或 Embedding 生成失败

**Q: 问答返回"知识库未收录"？**
A: 检查上传的文档内容是否包含相关文本

**Q: 端口被占用？**
A: 修改 `.env` 中的端口配置，或关闭占用端口的程序

---

## 技术栈

- **后端**：FastAPI, Uvicorn
- **前端**：原生 HTML/CSS/JavaScript
- **PDF 解析**：PyMuPDF
- **向量数据库**：ChromaDB
- **Embedding**：OpenAI 兼容 API
- **LLM**：OpenAI 兼容 API

---

## License

MIT