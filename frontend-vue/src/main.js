import { createApp } from "vue";
import App from "./App.vue";
import "./styles.css";

createApp(App).mount("#app");

await import("./legacy/script.js");
await import("./legacy/js/app.js");

if (typeof window.__bootstrapLegacyApp === "function") {
  await window.__bootstrapLegacyApp();
}
