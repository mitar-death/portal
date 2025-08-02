import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import store from './store'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import vuetify from './plugins/vuetify'
import authPlugin from './services/auth-plugin'

const app = createApp(App)

// Use plugins
app.use(store)
app.use(router)
app.use(vuetify)
app.use(authPlugin)

// Mount the app
app.mount('#app')
