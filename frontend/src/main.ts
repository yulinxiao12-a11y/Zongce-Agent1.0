import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import RootApp from './RootApp.vue'
import router from './router'
import './style.css'

createApp(RootApp).use(createPinia()).use(router).use(ElementPlus).mount('#app')
