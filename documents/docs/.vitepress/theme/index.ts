import DefaultTheme from 'vitepress/theme'
import { h } from 'vue'
import VoteBanner from './components/VoteBanner.vue'
import './styles/custom.scss'
import './styles/index.css'

export default {
  ...DefaultTheme,
  Layout() {
    return h(DefaultTheme.Layout, null, {
      'layout-top': () => h(VoteBanner)
    })
  }
}
