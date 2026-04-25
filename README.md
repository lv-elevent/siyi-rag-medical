# 思医：医疗知识库 RAG 问答系统
**思医**是一款面向医疗资料学习、资料整理、智能检索问答的多用户 RAG 系统，支持文档上传、知识库管理、流式问答、溯源检索等完整功能。

> 免责声明：本系统用于医学资料辅助学习与查询，不替代医生诊断与治疗决策。

---

## 1. 项目定位
本项目聚焦医疗文档知识库场景，提供从文档处理到智能问答的完整链路，适用于：
- 医学学习与复习
- 医疗资料检索与归纳
- 医疗知识库沉淀与复用

系统支持多用户与知识库隔离，不同用户、不同知识库可独立管理与检索。

---

## 2. 核心功能
### 2.1 用户认证
- 用户注册、登录
- JWT 鉴权
- 个人账户信息查询

### 2.2 知识库管理
- 多知识库创建与维护
- 知识库文件列表管理
- 文档添加/移除知识库
- 知识库删除与权限隔离

### 2.3 文档上传与处理
- 支持格式：`PDF` / `TXT` / `MD` / `DOCX`
- 文档解析、文本清洗、内容分块
- 文本向量生成（Embedding）
- 向量数据存入 `ChromaDB`
- 文档元数据存入 `MySQL`

### 2.4 RAG 问答
- 常规问答接口 `/chat`
- 流式问答接口 `/chat-stream`
- 问答结果来源溯源
- 基于用户/知识库/文档的检索隔离

### 2.5 会话管理
- 问答会话列表查询
- 历史消息查看
- 会话删除、标题修改

### 2.6 医疗安全机制
- 医疗问答智能路由
- 高危医疗问题安全拦截
- 风险内容屏蔽与兜底回复

---

## 3. 技术栈
### 后端
- `Python`
- `FastAPI`
- `SQLAlchemy`
- `MySQL`（业务数据存储）
- `ChromaDB`（向量数据库）
- 通用大模型 & 向量模型（OpenAI 兼容接口）

### 前端
- `Vue 3`
- `Vite`
- 遗留原生 JS 模块，后续逐步组件化重构

### 文档解析
- `PyMuPDF`
- `python-docx`

---

## 4. 项目目录结构
```text
rag-knowledgebase/
├─ backend/                # 后端核心代码
├─ frontend-vue/           # Vue 前端项目
├─ docs/                   # 项目文档
├─ tests/                  # 测试文件
├─ .env.example            # 环境变量模板
├─ requirements.txt        # 生产依赖
├─ requirements-dev.txt    # 开发依赖
└─ README.md               # 项目说明
```

---

## 5. 环境变量配置
复制 `.env.example` 为 `.env`，填写对应参数：

```env
# 数据库
DATABASE_URL=

# 认证配置
SECRET_KEY=
JWT_SECRET_KEY=
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=

# 大模型配置
OPENAI_API_KEY=
OPENAI_BASE_URL=
LLM_MODEL=
EMBEDDING_MODEL=

# 存储配置
CHROMA_PERSIST_DIR=
UPLOAD_DIR=
CHROMA_COLLECTION_NAME=

# 跨域配置
CORS_ORIGINS=
```

> 注意：禁止将密钥、密码等敏感信息上传至代码仓库。

---

## 6. 本地启动
### 6.1 后端启动
```bash
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```
- 服务地址：`http://127.0.0.1:8000`
- 接口文档：`http://127.0.0.1:8000/docs`

### 6.2 前端启动
```bash
cd frontend-vue
npm install
npm run dev
```
- 前端打包：`npm run build`

---

## 7. 健康检测
```bash
# 服务存活检测
curl http://127.0.0.1:8000/health

# 系统就绪检测
curl http://127.0.0.1:8000/health/ready
```
- `/health`：服务运行状态检测
- `/health/ready`：数据库、文件目录、模型配置完整性检测

---

## 8. 核心流程验证
1. 用户注册
2. 账号登录
3. 创建知识库
4. 上传医疗文档
5. 文档绑定知识库
6. 常规问答
7. 流式问答
8. 验证回答来源
9. 验证知识库隔离机制

---

## 9. 核心接口列表
```
# 认证
/auth/register
/auth/login
/auth/me

# 文档与知识库
/upload
/knowledge

# 问答
/chat
/chat-stream

# 会话管理
/chat/sessions
/chat/messages
/chat/session
/chat/session/title

# 系统检测
/health
/health/ready
```

---

## 10. 项目成熟度
- 项目阶段：`MVP+` / 早期 Beta
- 运行状态：核心业务链路完整可用
- 迭代方向：前端工程化、功能优化、性能升级

---

## 11. 医疗安全声明
1. 本系统仅用于**医疗资料学习与知识查询**；
2. 不提供疾病诊断、用药指导、医疗决策等服务；
3. 健康问题请咨询专业医师，切勿依赖系统回答。

---

## 12. 后续优化计划
- 数据库版本管理（Alembic）
- 文档异步处理与任务队列
- 检索优化：混合检索 + 重排模型
- RAG 问答效果评估体系
- 前端全量 Vue 组件重构
- 系统日志与运行监控优化
- 医疗安全策略升级