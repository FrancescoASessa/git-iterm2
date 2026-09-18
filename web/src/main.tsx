import { render } from 'preact'

import { startConnection } from './api/connect'
import { App } from './app'
import { applyTheme } from './theme'

applyTheme(null)
startConnection()
const root = document.getElementById('root')
if (root) render(<App />, root)
