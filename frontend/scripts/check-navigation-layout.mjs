import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const appVue = readFileSync(resolve(root, 'src/App.vue'), 'utf8')
const routerTs = readFileSync(resolve(root, 'src/router/index.ts'), 'utf8')

const failures = []

if (/<component\s+:is="Component"\s+:key=/.test(appVue)) {
  failures.push('App.vue must not key the top-level routed component; BasicLayout should be reused across menu routes.')
}

if (!/const BasicLayout\s*=\s*\(\)\s*=>\s*import\('@\/layouts\/BasicLayout\.vue'\)/.test(routerTs)) {
  failures.push('router/index.ts should reuse a single BasicLayout async component reference.')
}

const inlineLayoutImports = routerTs.match(/component:\s*\(\)\s*=>\s*import\('@\/layouts\/BasicLayout\.vue'\)/g) || []
if (inlineLayoutImports.length > 0) {
  failures.push(`router/index.ts still has ${inlineLayoutImports.length} inline BasicLayout import(s).`)
}

const menuPaths = [
  '/dashboard',
  '/learning',
  '/analysis',
  '/tasks',
  '/screening',
  '/favorites',
  '/paper',
  '/reports',
  '/settings',
  '/about'
]

for (const path of menuPaths) {
  const escapedPath = path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const routeBlock = new RegExp(`path:\\s*'${escapedPath}'[\\s\\S]*?component:\\s*BasicLayout`)
  if (!routeBlock.test(routerTs)) {
    failures.push(`Menu route ${path} should render inside BasicLayout.`)
  }
}

if (failures.length > 0) {
  console.error(failures.join('\n'))
  process.exit(1)
}

console.log('Navigation layout checks passed.')
