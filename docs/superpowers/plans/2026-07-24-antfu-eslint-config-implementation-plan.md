# Antfu ESLint Frontend Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Vue 3 frontend to `@antfu/eslint-config`, make ESLint the sole JavaScript/TypeScript/Vue formatter, and provide committed VS Code auto-fix support.

**Architecture:** Replace the legacy eslintrc/Prettier stack with one frontend-local Flat Config that loads generated auto-import globals when available and preserves the project's existing rule exceptions. Keep the migration isolated from business source formatting, maintain the repository's single Yarn 1 lock file, and expose the same ESLint fix path to CLI scripts and VS Code.

**Tech Stack:** Vue 3, TypeScript 5.3, ESLint 9, `@antfu/eslint-config` 4.17, Yarn 1, VS Code ESLint extension, GitNexus

---

## File map

- Create `frontend/eslint.config.mjs`: the only ESLint configuration; owns framework detection, ignores, generated globals loading, project rule exceptions, and stylistic preferences.
- Modify `frontend/package.json`: owns lint/format scripts, lint dependencies, and the supported Node.js floor.
- Modify `frontend/yarn.lock`: the sole tracked dependency lock file; preserve pre-existing user changes while adding the migration's resolutions.
- Delete `frontend/.eslintrc.cjs`: removes the legacy ESLint configuration path.
- Delete `frontend/.prettierrc.json`: removes the separate formatter configuration path.
- Modify `.gitignore`: keeps arbitrary `.vscode` state ignored while allowing exactly two shared workspace files.
- Create `.vscode/settings.json`: configures frontend working directory, ESLint validation, save-time fixes, and formatter conflict prevention.
- Create `.vscode/extensions.json`: recommends the official VS Code ESLint extension.
- Modify `docs/superpowers/specs/2026-07-24-antfu-eslint-config-design.md`: records the discovered Yarn-only lock policy and the need to commit selected VS Code settings.

### Task 1: Establish the dependency and runtime baseline

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/yarn.lock`

- [ ] **Step 1: Record the protected working-tree state**

Run from the repository root:

```powershell
git status --short
git diff -- frontend/yarn.lock
node --version
yarn --version
```

Expected: `frontend/src/layouts/BasicLayout.vue` and `frontend/yarn.lock` may already be modified; Node.js is at least `18.20.0`; Yarn reports `1.22.x`. Do not revert or replace the existing `yarn.lock` diff.

- [ ] **Step 2: Verify the old lint stack before changing dependencies**

Run:

```powershell
Set-Location frontend
yarn eslint --version
yarn lint --help
```

Expected: ESLint reports `v8.56.x`; the existing `lint` script includes `--fix`, confirming that lint currently writes files and is unsuitable as a CI check.

- [ ] **Step 3: Replace the lint dependencies, scripts, and Node.js floor**

Edit `frontend/package.json` so the relevant sections are exactly:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "lint:fix": "eslint . --fix",
    "format": "eslint src --fix",
    "type-check": "vue-tsc --noEmit"
  },
  "devDependencies": {
    "@antfu/eslint-config": "^4.17.0",
    "@types/lodash-es": "^4.17.12",
    "@types/node": "^20.10.5",
    "@types/nprogress": "^0.2.3",
    "@vitejs/plugin-vue": "^5.0.4",
    "@vue/compiler-sfc": "^3.5.22",
    "@vue/tsconfig": "^0.5.1",
    "autoprefixer": "^10.5.0",
    "eslint": "^9.39.5",
    "postcss": "^8.5.14",
    "sass": "^1.69.5",
    "sass-embedded": "^1.69.5",
    "tailwindcss": "^3.4.19",
    "typescript": "~5.3.3",
    "unplugin-auto-import": "^0.17.2",
    "unplugin-vue-components": "^29.1.0",
    "vite": "^5.0.10",
    "vue-tsc": "^1.8.25"
  },
  "engines": {
    "node": ">=18.20.0",
    "npm": ">=8.0.0"
  }
}
```

Keep the unchanged metadata and runtime `dependencies` entries around these sections. Remove `@typescript-eslint/eslint-plugin`, `@typescript-eslint/parser`, `@vue/eslint-config-prettier`, `@vue/eslint-config-typescript`, `eslint-plugin-vue`, and `prettier`; Antfu supplies their replacements transitively.

Version rationale: Antfu 9.2.0 requires `eslint-plugin-unicorn@72`, which requires Node.js 22. Antfu 4.17.0 is the last release before its dependency chain moves to Node.js 20, and its `eslint-plugin-unicorn@59` requires Node.js `^18.20.0`.

- [ ] **Step 4: Update only the tracked Yarn lock file**

Run from `frontend/`:

```powershell
yarn install
```

Expected: exit code 0; `package.json` and `yarn.lock` change; no tracked or untracked `package-lock.json` is created by this command.

- [ ] **Step 5: Review the lock-file delta for preservation**

Run from the repository root:

```powershell
git diff -- frontend/package.json frontend/yarn.lock
git status --short -- frontend/package-lock.json
```

Expected: the user's earlier `yarn.lock` edits remain present alongside Antfu/ESLint dependency additions; `package-lock.json` has no status entry.

- [ ] **Step 6: Check GitNexus scope before the dependency commit**

Use `gitnexus_detect_changes()` if the GitNexus MCP tool is available. Expected: dependency/configuration changes only, with no business symbols or execution flows affected. If the MCP tool is unavailable in the active environment, do not commit yet; report that project-required check as the blocking condition.

- [ ] **Step 7: Commit the dependency baseline**

```powershell
git add -- frontend/package.json frontend/yarn.lock
git commit -m "build(frontend): adopt Antfu ESLint dependencies"
```

Expected: only those two paths are committed; the pre-existing `BasicLayout.vue` change remains unstaged.

### Task 2: Add and test the Flat Config

**Files:**
- Create: `frontend/eslint.config.mjs`
- Delete: `frontend/.eslintrc.cjs`
- Delete: `frontend/.prettierrc.json`

- [ ] **Step 1: Run a failing Flat Config load probe**

Run from `frontend/`:

```powershell
node -e "import('./eslint.config.mjs')"
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND`, proving the new configuration does not exist yet.

- [ ] **Step 2: Create the minimal complete Flat Config**

Create `frontend/eslint.config.mjs` with:

```js
import { readFileSync } from 'node:fs'

import antfu from '@antfu/eslint-config'

function loadAutoImportGlobals() {
  try {
    const config = JSON.parse(
      readFileSync(new URL('./.eslintrc-auto-import.json', import.meta.url), 'utf8'),
    )
    return config.globals ?? {}
  }
  catch (error) {
    if (error.code === 'ENOENT')
      return {}
    throw error
  }
}

const isProduction = process.env.NODE_ENV === 'production'

export default antfu(
  {
    type: 'app',
    vue: true,
    typescript: true,
    stylistic: {
      indent: 2,
      quotes: 'single',
      semi: false,
    },
    jsonc: false,
    yaml: false,
    toml: false,
    markdown: false,
    ignores: [
      'dist/**',
      'node_modules/**',
      'auto-imports.d.ts',
      'components.d.ts',
      '*.tsbuildinfo',
    ],
  },
  {
    files: ['**/*.{js,mjs,cjs,ts,mts,cts,vue}'],
    languageOptions: {
      globals: loadAutoImportGlobals(),
    },
    rules: {
      'antfu/top-level-function': 'off',
      'no-console': isProduction ? 'warn' : 'off',
      'no-debugger': isProduction ? 'warn' : 'off',
      'style/arrow-parens': ['error', 'as-needed'],
      'style/brace-style': ['error', '1tbs', { allowSingleLine: true }],
      'style/comma-dangle': ['error', 'never'],
      'style/object-curly-spacing': ['error', 'always'],
      'ts/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'vue/multi-word-component-names': 'off',
    },
  },
)
```

The optional auto-import loader keeps lint configuration loadable in a fresh checkout before Vite regenerates `.eslintrc-auto-import.json`. Do not enable Antfu `formatters`, because its CSS/HTML formatter path uses Prettier internally and conflicts with the requirement to remove Prettier.

- [ ] **Step 3: Verify Flat Config loads and targets Vue/TypeScript**

Run from `frontend/`:

```powershell
node -e "import('./eslint.config.mjs').then(({ default: config }) => Promise.resolve(config).then(items => { if (!Array.isArray(items) || items.length === 0) process.exit(1); console.log(items.length) }))"
yarn eslint --print-config src/main.ts
```

Expected: the first command prints a positive config count; the second emits resolved JSON containing Antfu rules and exits 0.

- [ ] **Step 4: Verify generated globals and project rule exceptions**

Run from `frontend/`:

```powershell
@'
const value = ref(0)
console.log(value)
'@ | yarn eslint --stdin --stdin-filename src/__eslint_config_probe__.ts

@'
const run = (_unused) => 1
run()
'@ | yarn eslint --stdin --stdin-filename src/__eslint_config_probe__.ts
```

Expected: both commands exit 0 when `.eslintrc-auto-import.json` is present; `ref` is not reported as undefined, development `console` is allowed, and the underscore-prefixed argument is allowed. These probes use stdin and leave no test file behind.

- [ ] **Step 5: Remove the two obsolete configuration files**

Delete:

```text
frontend/.eslintrc.cjs
frontend/.prettierrc.json
```

Then run:

```powershell
Get-ChildItem -Force .eslintrc.cjs,.prettierrc.json -ErrorAction SilentlyContinue
```

Expected: no output.

- [ ] **Step 6: Verify lint is read-only**

Run from `frontend/`:

```powershell
git diff --name-only -- src | Sort-Object
yarn lint
git diff --name-only -- src | Sort-Object
```

Expected: the before/after file lists are identical. If legacy rule violations fail the command, capture the rule counts and add only narrowly scoped compatibility overrides to `eslint.config.mjs`; do not run `--fix` across `src/` and do not disable parsing errors.

- [ ] **Step 7: Check GitNexus scope and commit the Flat Config**

Run `gitnexus_detect_changes()` first. Expected: only lint configuration surfaces, no business execution flows. Then:

```powershell
git add -- frontend/eslint.config.mjs frontend/.eslintrc.cjs frontend/.prettierrc.json
git commit -m "chore(frontend): migrate to Antfu Flat Config"
```

Expected: the commit contains the new Flat Config and two deletions only.

### Task 3: Add committed VS Code IDE support

**Files:**
- Modify: `.gitignore`
- Create: `.vscode/settings.json`
- Create: `.vscode/extensions.json`

- [ ] **Step 1: Prove the requested workspace settings are currently ignored**

Run from the repository root:

```powershell
git check-ignore -v .vscode/settings.json .vscode/extensions.json
```

Expected: both paths are ignored by the `.vscode/` rule.

- [ ] **Step 2: Allow only shared VS Code files**

Replace the existing `.vscode/` ignore entry and remove the later duplicate `.vscode/settings.json` entry so the IDE section contains:

```gitignore
# IDE和编辑器文件
.vscode/*
!.vscode/settings.json
!.vscode/extensions.json
.idea/
*.swp
*.swo
*~
```

Keep all unrelated `.gitignore` content unchanged.

- [ ] **Step 3: Add official Antfu-style save-time ESLint settings**

Create `.vscode/settings.json` with:

```json
{
  "prettier.enable": false,
  "editor.formatOnSave": false,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": "explicit",
    "source.organizeImports": "never"
  },
  "eslint.useFlatConfig": true,
  "eslint.workingDirectories": [
    {
      "directory": "./frontend",
      "changeProcessCWD": true
    }
  ],
  "eslint.validate": [
    "javascript",
    "javascriptreact",
    "typescript",
    "typescriptreact",
    "vue"
  ],
  "eslint.rules.customizations": [
    {
      "rule": "style/*",
      "severity": "off",
      "fixable": true
    },
    {
      "rule": "format/*",
      "severity": "off",
      "fixable": true
    },
    {
      "rule": "*-indent",
      "severity": "off",
      "fixable": true
    },
    {
      "rule": "*-spacing",
      "severity": "off",
      "fixable": true
    },
    {
      "rule": "*-spaces",
      "severity": "off",
      "fixable": true
    },
    {
      "rule": "*-order",
      "severity": "off",
      "fixable": true
    },
    {
      "rule": "*-dangle",
      "severity": "off",
      "fixable": true
    }
  ]
}
```

`source.fixAll.eslint: explicit`, disabled `formatOnSave`, disabled Prettier, and stylistic-rule customizations follow the Antfu 4.17 IDE guidance. `eslint.workingDirectories` is repository-specific so opening the monorepo root resolves `frontend/eslint.config.mjs` correctly.

- [ ] **Step 4: Recommend the ESLint extension**

Create `.vscode/extensions.json` with:

```json
{
  "recommendations": [
    "dbaeumer.vscode-eslint"
  ]
}
```

- [ ] **Step 5: Validate JSON and tracking behavior**

Run from the repository root:

```powershell
node -e "JSON.parse(require('node:fs').readFileSync('.vscode/settings.json', 'utf8')); JSON.parse(require('node:fs').readFileSync('.vscode/extensions.json', 'utf8')); console.log('valid')"
git check-ignore -q .vscode/settings.json; if ($LASTEXITCODE -eq 0) { throw 'settings.json is still ignored' }
git check-ignore -q .vscode/extensions.json; if ($LASTEXITCODE -eq 0) { throw 'extensions.json is still ignored' }
```

Expected: `valid`; both ignore checks take the non-ignored path without throwing.

- [ ] **Step 6: Check GitNexus scope and commit IDE support**

Run `gitnexus_detect_changes()` first. Expected: `.gitignore` and editor metadata only. Then:

```powershell
git add -- .gitignore .vscode/settings.json .vscode/extensions.json
git commit -m "chore: configure ESLint IDE support"
```

Expected: exactly three paths are committed.

### Task 4: Verify migration behavior without bulk source formatting

**Files:**
- Modify if required by a demonstrated compatibility failure: `frontend/eslint.config.mjs`

- [ ] **Step 1: Verify dependency versions and frozen lock integrity**

Run from `frontend/`:

```powershell
yarn eslint --version
yarn list --pattern "@antfu/eslint-config|eslint$" --depth=0
yarn install --frozen-lockfile
```

Expected: ESLint reports `v9.39.5` or a later compatible 9.x patch; Antfu reports 4.17.x; frozen install exits 0 without changing `package.json` or `yarn.lock`.

- [ ] **Step 2: Verify lint and formatting paths**

Run from `frontend/`:

```powershell
yarn lint
yarn eslint eslint.config.mjs --fix-dry-run
```

Expected: both exit 0 and no source files change. If `yarn lint` identifies existing project violations, add explicit, documented migration overrides only for rules that block adoption across existing code; repeat until the command exits 0.

- [ ] **Step 3: Verify format idempotence on stdin**

Run from `frontend/`:

```powershell
$source = 'const value={answer:42};'
$first = $source | yarn eslint --stdin --stdin-filename src/__format_probe__.ts --fix-dry-run --format json | ConvertFrom-Json
$formatted = $first[0].output
$second = $formatted | yarn eslint --stdin --stdin-filename src/__format_probe__.ts --fix-dry-run --format json | ConvertFrom-Json
if ($second[0].output) { throw 'ESLint formatting is not idempotent' }
$formatted
```

Expected: output uses no semicolon, spaces inside object braces, and no second-pass output. No file is written.

- [ ] **Step 4: Run type and production build checks**

Run from `frontend/`:

```powershell
yarn type-check
yarn build
```

Expected: both exit 0. Record any pre-existing failure separately instead of modifying unrelated business code.

- [ ] **Step 5: Confirm no bulk source rewrite or package-lock creation**

Run from the repository root:

```powershell
git status --short
git diff --stat -- frontend/src frontend/package-lock.json
```

Expected: no new migration-caused changes under `frontend/src`; the user's original `BasicLayout.vue` change is preserved; `package-lock.json` has no tracked diff.

- [ ] **Step 6: Run the mandatory final GitNexus change check**

Run `gitnexus_detect_changes()` before any final commit. Expected: configuration and dependency changes only, with no affected business symbols or execution flows. If HIGH or CRITICAL risk is reported, stop and warn the user before continuing.

- [ ] **Step 7: Commit only any evidence-driven compatibility adjustment**

If Step 2 required an `eslint.config.mjs` adjustment, run:

```powershell
git add -- frontend/eslint.config.mjs
git commit -m "chore(frontend): align Antfu rules with existing code"
```

If no adjustment was required, skip this commit. Never stage `frontend/src/layouts/BasicLayout.vue` or unrelated working-tree changes.

### Task 5: Final review and handoff

**Files:**
- Modify: `docs/superpowers/specs/2026-07-24-antfu-eslint-config-design.md`
- Create: `docs/superpowers/plans/2026-07-24-antfu-eslint-config-implementation-plan.md`

- [ ] **Step 1: Verify documentation matches implemented repository policy**

Run:

```powershell
rg -n "package-lock|yarn.lock|Node.js|\.vscode" docs/superpowers/specs/2026-07-24-antfu-eslint-config-design.md docs/superpowers/plans/2026-07-24-antfu-eslint-config-implementation-plan.md
```

Expected: documentation consistently says Yarn 1 is the sole tracked lock file, Node.js 18.20.0 is the minimum, and the selected `.vscode` files are committed.

- [ ] **Step 2: Run documentation hygiene checks**

```powershell
$redFlags = @('T' + 'BD', 'T' + 'ODO', 'implement' + ' later', 'fill in' + ' details', '待' + '定')
Select-String -Path docs/superpowers/specs/2026-07-24-antfu-eslint-config-design.md,docs/superpowers/plans/2026-07-24-antfu-eslint-config-implementation-plan.md -Pattern $redFlags
git diff --check
```

Expected: the placeholder scan has no matches; `git diff --check` exits 0.

- [ ] **Step 3: Run GitNexus detection before the documentation commit**

Run `gitnexus_detect_changes()`. Expected: documentation-only changes have no symbol or process impact.

- [ ] **Step 4: Commit the corrected specification and implementation plan**

```powershell
git add -- docs/superpowers/specs/2026-07-24-antfu-eslint-config-design.md docs/superpowers/plans/2026-07-24-antfu-eslint-config-implementation-plan.md
git commit -m "docs: plan Antfu ESLint frontend migration"
```

Expected: exactly the corrected spec and this plan are committed.

- [ ] **Step 5: Report final evidence**

Provide the user with the selected versions, changed configuration/IDE files, exact verification commands and outcomes, any pre-existing failures, the GitNexus affected scope, and confirmation that unrelated working-tree changes were preserved.
