# PDF 文档入库调试日志指南

## 概述

系统已添加开发调试日志，用于观察 PDF 清洗和分块效果。

---

## 日志位置

日志添加在以下位置：

1. **后端日志配置**: `backend/core/logger_config.py`
   - 统一的日志配置模块

2. **文档处理器**: `backend/services/document_processor.py`
   - PDF 解析后：显示清洗效果（前 300 字符）
   - 分块后：显示前 2 个 chunk 示例
   - 统计信息：chunk 总数

---

## 开发环境 vs 生产环境

### 开发环境（默认）

设置环境变量：
```bash
export ENVIRONMENT=development
# 或
ENVIRONMENT=development
```

在 `.env` 文件中：
```
ENVIRONMENT=development
```

**日志级别**: DEBUG  
**显示内容**:
- ✓ PDF 清洗后的文本（前 300 字符）
- ✓ 前 2 个 chunk 示例（每个前 200 字符）
- ✓ 分块统计信息

### 生产环境

设置环境变量：
```bash
export ENVIRONMENT=production
# 或
ENVIRONMENT=production
```

在 `.env` 文件中：
```
ENVIRONMENT=production
```

**日志级别**: INFO  
**显示内容**:
- ✓ 处理开始/结束信息
- ✓ 处理统计信息
- ✗ 不显示 PDF 清洗和分块详情

---

## 示例日志

### 开发环境日志输出

```
2026-04-04 10:30:15 - backend.services.document_processor - INFO - [document_processor] 开始解析 PDF: sample.pdf
2026-04-04 10:30:15 - backend.services.document_processor - INFO - [document_processor] 解析完成，提取到 12500 字符
2026-04-04 10:30:15 - backend.services.document_processor - DEBUG - [DEBUG] 清洗后的文本前 300 字符：
2026-04-04 10:30:15 - backend.services.document_processor - DEBUG - [DEBUG] 第一章 引言
本文研究的背景和意义...
第二章 相关技术...
第三章 研究方法...
```

```
2026-04-04 10:30:15 - backend.services.document_processor - INFO - [document_processor] 开始分块，chunk_size=500, overlap=50
2026-04-04 10:30:15 - backend.services.document_processor - INFO - [document_processor] 分块完成，共生成 25 个 chunk
2026-04-04 10:30:15 - backend.services.document_processor - DEBUG - [DEBUG] 前 2 个 chunk 示例：
2026-04-04 10:30:15 - backend.services.document_processor - DEBUG - [DEBUG] Chunk 1 (index=0): 第一章 引言
本文研究的背景和意义主要体现在以下几个方面：首先，随着人工智能技术的发展...
2026-04-04 10:30:15 - backend.services.document_processor - DEBUG - [DEBUG] Chunk 2 (index=1): 第一章 引言
本文研究的背景和意义主要体现在以下几个方面：首先，随着人工智能技术的发展...
```

### 生产环境日志输出

```
2026-04-04 10:30:15 - backend.services.document_processor - INFO - [document_processor] 开始解析 PDF: sample.pdf
2026-04-04 10:30:15 - backend.services.document_processor - INFO - [document_processor] 解析完成，提取到 12500 字符
2026-04-04 10:30:15 - backend.services.document_processor - INFO - [document_processor] 开始分块，chunk_size=500, overlap=50
2026-04-04 10:30:15 - backend.services.document_processor - INFO - [document_processor] 分块完成，共生成 25 个 chunk
2026-04-04 10:30:15 - backend.services.document_processor - INFO - [document_processor] 开始生成 25 个 embeddings
2026-04-04 10:30:16 - backend.services.document_processor - INFO - [document_processor] embeddings 生成完成
2026-04-04 10:30:16 - backend.services.document_processor - INFO - [document_processor] 开始存储到向量库，document_id=doc_a1b2c3d4
2026-04-04 10:30:17 - backend.services.document_processor - INFO - [document_processor] 文档处理完成
```

---

## 查看日志

### 运行后端服务

```bash
cd backend
python main.py
```

日志会输出到控制台（stdout）。

### 使用 tail 命令实时查看

```bash
# 在另一个终端中
tail -f backend.log
```

### 使用 Grep 搜索特定内容

```bash
# 搜索 DEBUG 日志
grep DEBUG logs/app.log

# 搜索文档处理日志
grep document_processor logs/app.log

# 搜索 PDF 解析信息
grep "开始解析 PDF" logs/app.log
```

---

## 切换环境

1. 编辑 `.env` 文件：
   ```bash
   ENVIRONMENT=development  # 或 production
   ```

2. 重启后端服务：
   ```bash
   # Ctrl+C 停止
   python main.py
   ```

3. 观察日志输出变化

---

## 注意事项

- 开发环境的 DEBUG 日志包含敏感信息（如文件内容），**不要在生产环境启用**
- 生产环境建议设置日志级别为 INFO 或 WARNING
- 日志文件路径可通过日志配置调整（如输出到文件而非控制台）
