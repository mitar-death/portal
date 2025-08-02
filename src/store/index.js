import { createStore } from 'vuex'

// Import modules
import auth from './modules/auth'
import telegram from './modules/telegram'
import ai from './modules/ai'
import ui from './modules/ui'

export default createStore({
  modules: {
    auth,
    telegram,
    ai,
    ui
  }
})
