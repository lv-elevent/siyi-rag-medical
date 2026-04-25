<template>
  <div>
    <div class="modal" id="uploadModal">
      <div class="modal-content modal-upload">
        <div class="modal-header">
          <h3 class="modal-title">上传文件</h3>
          <button class="close-btn" type="button" data-close="uploadModal">×</button>
        </div>

        <div class="upload-area" id="uploadAreaModal">
          <input type="file" id="pdf-upload" accept=".pdf,.txt,.md,.docx" hidden />
          <label for="pdf-upload" class="upload-label">
            <span class="upload-main-text">点击或拖拽文件到此处</span>
            <span class="upload-sub-text">支持 PDF / TXT / MD / DOCX，上传后自动进入知识库</span>
          </label>
        </div>

        <div id="uploadPreview" class="upload-file-preview"></div>
        <div id="upload-status" class="upload-status"></div>
      </div>
    </div>

    <div class="modal" id="kbModal">
      <div class="modal-content modal-kb">
        <div class="modal-header">
          <h3 class="modal-title">知识库管理</h3>
          <button class="close-btn" type="button" data-close="kbModal">×</button>
        </div>

        <div class="kb-container">
          <div class="kb-left">
            <input type="text" class="search-box" id="fileSearch" placeholder="🔍 搜索文件..." />
            <button id="toggle-kb-files" type="button" class="kb-toggle-btn">查看知识文档</button>
            <div id="kb-status" class="status-content">
              <p class="kb-empty-tip">暂无文档，请上传 PDF / TXT / MD / DOCX 文件</p>
            </div>
            <div id="kb-files-panel" class="kb-files-panel" style="display: block">
              <div id="kb-files-list" class="kb-files-list"></div>
            </div>
          </div>

          <div class="kb-right">
            <div class="kb-toolbar">
              <button class="create-kb-btn" id="createKbBtn" type="button">➕ 新建知识库</button>
            </div>
            <div class="kb-grid" id="kbGrid"></div>
          </div>
        </div>
      </div>
    </div>

    <div class="modal" id="libraryModal">
      <div class="modal-content modal-library">
        <div class="modal-header">
          <h3 class="modal-title" id="libTitle">知识库详情</h3>
          <button class="close-btn" type="button" data-close="libraryModal">×</button>
        </div>
        <div class="library-head">
          <div class="library-head-tip" id="libraryTip">
            可查看当前知识库中的文档，并继续添加或移除文件。
          </div>
          <button id="addFileToLibBtn" class="lib-add-btn" type="button">+ 添加文件</button>
        </div>
        <div class="library-files" id="libFiles"></div>
      </div>
    </div>

    <div class="modal" id="profileModal">
      <div class="modal-content modal-profile">
        <div class="modal-header profile-modal-header">
          <h3 class="modal-title profile-modal-title">个人信息</h3>
          <button class="close-btn profile-close" type="button" data-close="profileModal">×</button>
        </div>
        <div class="profile-info-card">
          <div class="profile-info-row">
            <span class="profile-info-label">用户名</span>
            <span class="profile-info-value" id="profileModalUsername">医疗用户</span>
          </div>
          <div class="profile-info-row">
            <span class="profile-info-label">系统</span>
            <span class="profile-info-value">医疗知识库助手</span>
          </div>
        </div>
      </div>
    </div>

    <div class="modal" id="selectFileModal">
      <div class="modal-content" style="max-width: 600px">
        <div class="modal-header">
          <h3 class="modal-title">选择文件加入当前知识库</h3>
          <button class="close-btn" data-close="selectFileModal">×</button>
        </div>
        <div id="selectFileList"></div>
        <div style="margin-top: 16px; text-align: right">
          <button id="confirmAddFilesBtn" class="func-btn">确认添加</button>
        </div>
      </div>
    </div>

    <div id="inputModal" class="delete-modal" style="display: none">
      <div class="delete-modal-content">
        <h4 id="inputModalTitle">请输入内容</h4>
        <p id="inputModalLabel"></p>
        <input
          id="inputModalField"
          type="text"
          style="width: 100%; box-sizing: border-box; margin: 10px 0; padding: 10px; border: 1px solid var(--border-color); border-radius: 8px"
        />
        <p id="inputModalError" style="min-height: 20px; color: #dc2626; margin: 0 0 8px"></p>
        <div class="delete-modal-buttons">
          <button id="cancelInputBtn" class="btn-cancel" type="button">取消</button>
          <button id="confirmInputBtn" class="btn-confirm" type="button">确定</button>
        </div>
      </div>
    </div>

    <div id="deleteModal" class="delete-modal">
      <div class="delete-modal-content">
        <h4>确认删除</h4>
        <p id="deleteModalText"></p>
        <div class="delete-modal-buttons">
          <button id="cancelDeleteBtn" class="btn-cancel" type="button">取消</button>
          <button id="confirmDeleteBtn" class="btn-confirm" type="button">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>
