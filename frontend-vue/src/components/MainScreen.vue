<template>
  <div id="app-screen">
    <div class="sidebar">
      <div class="profile-section" id="profileBtn">
        <div class="profile-avatar">👤</div>
        <div class="profile-info">
          <div class="profile-name" id="profileName">医疗用户</div>
        </div>
        <div class="profile-arrow">▾</div>

        <div class="profile-menu" id="profileMenu">
          <div class="menu-item user-menu-item" id="viewProfileBtn">👤 查看个人信息</div>
          <div class="menu-item user-menu-item" id="switchAccountBtn">🔄 切换账号</div>
          <div class="menu-item user-menu-item logout" id="logoutBtn">🚪 退出登录</div>
        </div>
      </div>

      <div class="sidebar-nav">
        <div class="sidebar-item sidebar-item-primary" id="newChatBtn" role="button" tabindex="0">➕ 新建对话</div>
        <div class="sidebar-section-label">功能区</div>
        <div class="sidebar-item" id="uploadBtn" role="button" tabindex="0">📁 上传文件</div>
        <div class="sidebar-item" id="kbBtn" role="button" tabindex="0">📚 知识库管理</div>
      </div>

      <div class="history-container">
        <div class="history-title">历史对话</div>
        <div id="historyList"></div>
      </div>
    </div>

    <div class="main-content">
      <div class="top-banner">
        <button id="mobile-menu-btn" class="mobile-menu-btn">☰</button>
        <div class="top-banner-left">
          <div class="top-banner-title header-title">医疗知识库助手</div>
          <div class="top-banner-subtitle header-subtitle">基于知识库的医学问答与资料整理</div>
        </div>
        <div class="kb-selector-wrap">
          <div class="kb-selector" id="currentKbBadge" role="button" tabindex="0" aria-expanded="false">
            当前知识库：全库
            <span class="kb-selector-caret">▼</span>
          </div>
          <div class="kb-selector-menu" id="kbSelectorMenu"></div>
        </div>
      </div>

      <div class="chat-container">
        <div class="chat-main">
          <div class="chat-scroll">
            <div id="chat-messages" class="chat-messages chat-list">
              <div class="medical-notice">
                ⚠️ 风险提示：系统回答仅供参考，若出现持续高热、剧烈疼痛、呼吸困难、明显出血等情况，请及时线下就医。
              </div>
            </div>
          </div>

          <div class="chat-input-wrap chat-input-area">
            <div class="chat-input-container chat-input-wrapper">
              <textarea
                id="chat-input"
                placeholder="请输入你的医疗健康问题，例如：发热三天伴咳嗽，需要做哪些检查？"
              ></textarea>
              <button id="send-button" class="send-button" type="button">发送</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
