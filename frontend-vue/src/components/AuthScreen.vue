<template>
  <div id="auth-screen" class="auth-screen">
    <div class="auth-mask"></div>
    <div class="auth-card">
      <div class="auth-head">
        <h2 class="auth-title">医疗RAG智能问答系统</h2>
        <p class="auth-subtitle">请先登录后再进入知识库与问答工作台</p>
      </div>

      <div id="loginPanel" class="auth-panel auth-panel-login">
        <div class="auth-form-group">
          <input id="loginUsername" type="text" placeholder="请输入用户名" />
        </div>
        <div class="auth-form-group">
          <input id="loginPassword" type="password" placeholder="请输入密码" />
        </div>
        <button id="loginBtn" class="auth-submit-btn" type="button">立即登录</button>
      </div>

      <div id="registerPanel" class="auth-panel auth-panel-register" style="display: none">
        <div class="auth-form-group">
          <input id="registerUsername" type="text" placeholder="请输入用户名" />
        </div>
        <div class="auth-form-group">
          <input id="registerPassword" type="password" placeholder="请输入密码" />
        </div>
        <div class="auth-form-group">
          <input id="registerPhone" type="text" placeholder="请输入手机号（可选）" />
        </div>
        <button id="registerBtn" class="auth-submit-btn" type="button">立即注册</button>
      </div>

      <div class="auth-switch-row">
        <span id="authSwitchText">还没有账号？</span>
        <button id="authSwitchLink" class="auth-switch-link" type="button">去注册</button>
      </div>
      <div class="auth-back-row">
        <button id="authBackBtn" class="auth-back-btn" type="button">返回当前页面</button>
      </div>

      <div id="authMessage" class="auth-message"></div>
    </div>
  </div>
</template>
