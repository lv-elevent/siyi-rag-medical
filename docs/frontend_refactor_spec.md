# 医疗 RAG 智能问答系统前端改造规范

## 1. 改造目标

将当前已有的医疗 RAG 问答前端，从“工具型界面”升级为“产品化界面”，但必须遵循以下原则：

1. **保留现有业务逻辑与接口行为**
   - 文件上传
   - 文档列表获取
   - 文档删除
   - 当前检索范围选择
   - SSE 流式输出
   - 打字机式回答
   - 来源展示
   - 对话发送
   - 删除确认弹窗

2. **只重构前端展示层和少量 DOM 绑定**
   - 优先重构 HTML 结构
   - 全量重写 CSS 样式体系
   - JS 仅做“渲染层适配”和“新增 UI 交互”
   - 不随意改动后端接口参数和返回逻辑

3. **最终目标**
   - 页面视觉风格接近给定预览版本
   - 知识库管理从旧式列表，升级为弹窗 + 小方块卡片网格
   - 顶部头像支持菜单浮窗
   - 支持明暗主题切换
   - 支持上传弹窗
   - 支持知识库总览弹窗
   - 支持知识库详情弹窗
   - 支持 Toast 提示

---

## 2. 改造原则

### 2.1 严格保留的逻辑
以下逻辑必须沿用原代码能力，不得随意删除：

- `state` 状态对象
- `fetchKnowledgeFiles()`
- `renderKnowledgeFiles()`
- `sendMessage()`
- `askQuestionToBackendStream()`
- `updateMessage()`
- `addMessage()`
- `buildSourceHTML()`
- `deleteDocument()`
- 删除弹窗的确认/取消逻辑

### 2.2 可重构部分
以下内容允许重构：

- HTML 页面骨架
- CSS 全量重写
- DOM 选择器映射
- `renderKnowledgeFiles()` 的视觉渲染方式
- `updateSelectedDocumentDisplay()` 的显示位置
- 上传区展示方式
- 知识库文件面板 -> 知识库管理弹窗
- Toast 样式与实现方式

### 2.3 不允许的改法
- 不要移除 `marked`
- 不要删除 SSE 流式逻辑
- 不要修改后端接口 URL
- 不要把所有功能改成假数据
- 不要把真实逻辑替换成纯静态页面
- 不要上框架（Vue/React）  
  当前阶段必须继续使用 **原生 HTML + CSS + JS**

---

## 3. 页面结构目标

最终页面分为两个主区域：

### 3.1 左侧侧边栏 `.sidebar`
包含：

1. 用户头像入口 `.profile-section`
   - 头像 `.profile-avatar`
   - 用户名 `.profile-name`
   - 描述 `.profile-desc`
   - 下拉箭头 `.profile-arrow`
   - 点击后显示菜单 `#profileMenu`

2. 功能按钮区 `.sidebar-buttons`
   - `#newChatBtn` 新建对话
   - `#uploadBtn` 上传文件
   - `#kbBtn` 查看知识库

3. 当前知识库卡片 `.status-mini-card`
   - 标题 `.status-mini-title`
   - 当前知识库名称 `#sidebarCurrentKb`

4. 历史对话区域 `.history-container`
   - 标题 `.history-title`
   - 多个 `.history-item`

### 3.2 右侧主区域 `.main-content`
包含：

1. 顶部横条 `.top-banner`
   - 系统标题 `.top-banner-title`
   - 描述 `.top-banner-desc`
   - 当前知识库徽标 `#currentKbBadge`

2. 聊天区 `#chat-messages`
   - 保留原有消息渲染逻辑
   - 样式改造成产品化气泡样式
   - 用户消息右对齐
   - AI 消息左对齐
   - 来源展示更精致

3. 输入区 `.chat-input-container`
   - 输入框 `#chat-input`
   - 发送按钮 `#send-button`

---

## 4. 弹窗结构目标

### 4.1 上传文件弹窗 `#uploadModal`
要求：
- 点击左侧“上传文件”按钮打开
- 支持点击选文件
- 支持拖拽上传
- 使用原有 `#pdf-upload`
- 增加上传文件预览区域 `#uploadPreview`

### 4.2 知识库管理弹窗 `#kbModal`
要求：
- 左侧：文件搜索 + 文件列表
- 右侧：知识库卡片网格
- 新建知识库按钮 `#createKbBtn`

### 4.3 知识库详情弹窗 `#libraryModal`
要求：
- 标题 `#libTitle`
- 说明 `#libraryTip`
- 文件列表容器 `#libFiles`
- 支持查看当前库中的文件
- 支持移除文件
- 支持提示拖拽添加文件

### 4.4 个人信息弹窗 `#profileModal`
要求：
- 显示模拟账号信息
- 点击头像菜单中的“查看个人信息”打开

### 4.5 删除确认弹窗 `#deleteModal`
要求：
- **继续保留现有逻辑和 ID**
- 样式可以优化，但删除确认逻辑不得破坏

---

## 5. 知识库卡片改造要求（关键）

知识库卡片必须严格改成“小方块”样式：

### 5.1 网格 `.kb-grid`
```css
grid-template-columns: repeat(4, 1fr);
gap: 12px;