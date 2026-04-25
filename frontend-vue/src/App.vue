<template>
  <div class="app-root">
    <AuthScreen />
    <MainScreen />
    <AppModals />
    <Toast />
  </div>
</template>

<script setup>
import AuthScreen from "./components/AuthScreen.vue";
import MainScreen from "./components/MainScreen.vue";
import AppModals from "./components/AppModals.vue";
import Toast from "./components/Toast.vue";
</script>
