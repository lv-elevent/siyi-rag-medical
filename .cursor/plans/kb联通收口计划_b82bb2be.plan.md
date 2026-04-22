---
name: KB联通收口计划
overview: 修复知识库管理页“新建无反应”并完成多知识库前后端联通闭环，确保上传、文件列表、问答都基于当前知识库。
todos:
  - id: fix-input-modal-dom
    content: 补齐 index.html 中 inputModal 相关 DOM，修复新建知识库无反应
    status: completed
  - id: add-kb-files-api
    content: 在 backend/api/knowledge.py 新增 GET /knowledge/{id}/files 并加用户隔离
    status: completed
  - id: align-kb-files-render
    content: 对齐 apiFetchKBFiles 与 openLibraryById 渲染逻辑
    status: completed
  - id: converge-kb-state
    content: 前端统一以 state.kbs/currentKbId 为主数据源，减少 libraries 干扰
    status: completed
  - id: unify-delete-kb-handler
    content: 统一 deleteLibrary 为后端驱动实现，消除全局覆盖风险
    status: completed
  - id: run-e2e-validation
    content: 执行新建/切换/上传/问答/多用户隔离联调验证
    status: completed
isProject: false
---

# 知识库联通收口计划

## 目标
- 修复“点击新建知识库无反应”。
- 完成知识库管理多租户前后端联通闭环。
- 保持现有结构，最小改动落地。

## 现状结论
- 前端新建按钮已绑定，但 `openInputModal()` 依赖的 `#inputModal` 相关 DOM 缺失，导致静默 return。
- 前端已接入 `GET /knowledge`、`POST /knowledge`、`DELETE /knowledge/:id`，但调用了 `GET /knowledge/:id/files`，后端尚未提供该接口。
- 前端同时维护 `state.kbs`（后端）与 `state.libraries`（本地），存在状态漂移风险。

## 实施步骤
- **步骤1：修复新建知识库弹窗缺失（P0）**
  - 在 [f:\rag-knowledgebase\frontend\index.html](f:\rag-knowledgebase\frontend\index.html) 补齐 `inputModal` 及其内部元素：`inputModalTitle`、`inputModalLabel`、`inputModalField`、`inputModalError`、`confirmInputBtn`、`cancelInputBtn`。
  - 与 [f:\rag-knowledgebase\frontend\js\modules\modal.js](f:\rag-knowledgebase\frontend\js\modules\modal.js) 现有选择器保持一致，不改交互逻辑。

- **步骤2：补齐后端按知识库文件列表接口（P0）**
  - 在 [f:\rag-knowledgebase\backend\api\knowledge.py](f:\rag-knowledgebase\backend\api\knowledge.py) 新增 `GET /knowledge/{knowledge_base_id}/files`。
  - 约束：`knowledge_base_id` 必须属于 `current_user.id`；否则 404。
  - 返回格式与前端当前使用兼容（含 `files` 数组，元素至少包含 `document_id`、`filename`）。

- **步骤3：打通前端知识库详情文件渲染（P0）**
  - 复核 [f:\rag-knowledgebase\frontend\js\api.js](f:\rag-knowledgebase\frontend\js\api.js) 的 `apiFetchKBFiles()` 与新后端返回对齐。
  - 在 [f:\rag-knowledgebase\frontend\js\modules\kb.js](f:\rag-knowledgebase\frontend\js\modules\kb.js) 保持 `openLibraryById()` 走后端文件数据源，确认空态、删除按钮、文件名显示正常。

- **步骤4：收敛前端知识库状态源（P1）**
  - 在 [f:\rag-knowledgebase\frontend\js\modules\kb.js](f:\rag-knowledgebase\frontend\js\modules\kb.js) 与 [f:\rag-knowledgebase\frontend\script.js](f:\rag-knowledgebase\frontend\script.js) 中，将知识库卡片渲染与选择统一基于 `state.kbs/currentKbId`。
  - 保留 `state.libraries` 仅作兼容壳（不作为主数据源），避免大改。

- **步骤5：统一删除知识库行为（P1）**
  - 避免 `window.deleteLibrary` 多处定义覆盖：保留一个后端驱动版本（调用 `apiDeleteKB`），并在相关入口统一指向该实现。
  - 主要检查 [f:\rag-knowledgebase\frontend\js\modules\kb.js](f:\rag-knowledgebase\frontend\js\modules\kb.js)、[f:\rag-knowledgebase\frontend\script.js](f:\rag-knowledgebase\frontend\script.js)。

- **步骤6：联调与回归验证（P0）**
  - 新建知识库：点击后弹窗出现、提交成功、列表刷新。
  - 切换知识库：详情文件列表按库展示，不串库。
  - 上传文件：上传到当前知识库，刷新后只在该库出现。
  - 问答：请求体带 `knowledge_base_id`，后端检索日志可见 kb 过滤。
  - 多账号：A/B 用户互不可见彼此知识库与文件。

## 关键文件
- 后端：
  - [f:\rag-knowledgebase\backend\api\knowledge.py](f:\rag-knowledgebase\backend\api\knowledge.py)
- 前端：
  - [f:\rag-knowledgebase\frontend\index.html](f:\rag-knowledgebase\frontend\index.html)
  - [f:\rag-knowledgebase\frontend\js\api.js](f:\rag-knowledgebase\frontend\js\api.js)
  - [f:\rag-knowledgebase\frontend\js\modules\kb.js](f:\rag-knowledgebase\frontend\js\modules\kb.js)
  - [f:\rag-knowledgebase\frontend\script.js](f:\rag-knowledgebase\frontend\script.js)