import { readFileSync } from 'node:fs'
import process from 'node:process'

import antfu from '@antfu/eslint-config'

function loadAutoImportGlobals() {
  try {
    const config = JSON.parse(
      readFileSync(new URL('./.eslintrc-auto-import.json', import.meta.url), 'utf8')
    )
    return config.globals ?? {}
  } catch (error) {
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
      semi: false
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
      '*.tsbuildinfo'
    ]
  },
  {
    files: ['**/*.{js,mjs,cjs,ts,mts,cts,vue}'],
    languageOptions: {
      globals: loadAutoImportGlobals()
    },
    rules: {
      // Migration compatibility for existing application patterns.
      'antfu/top-level-function': 'off',
      'import/no-duplicates': 'off',
      'no-alert': 'off',
      'no-cond-assign': 'off',
      'no-console': isProduction ? 'warn' : 'off',
      'no-debugger': isProduction ? 'warn' : 'off',
      'node/prefer-global/process': 'off',
      'regexp/no-unused-capturing-group': 'off',
      'style/arrow-parens': ['error', 'as-needed'],
      'style/brace-style': 'off',
      'style/comma-dangle': ['error', 'never'],
      'style/max-statements-per-line': 'off',
      'style/object-curly-spacing': ['error', 'always'],
      'ts/no-empty-object-type': 'off',
      'ts/no-use-before-define': 'off',
      'ts/no-unused-vars': 'off',
      'unicorn/error-message': 'off',
      'unicorn/prefer-number-properties': 'off',
      'unused-imports/no-unused-vars': 'off',
      'vue/custom-event-name-casing': 'off',
      'vue/multi-word-component-names': 'off',
      'vue/no-mutating-props': 'off',
      'vue/no-side-effects-in-computed-properties': 'off',
      'vue/no-template-shadow': 'off'
    }
  }
)
