# 前端引入 Antfu ESLint Config 设计

## 背景

前端当前使用 ESLint 8 的传统 `.eslintrc.cjs` 配置，并通过 Prettier 负责代码格式化。项目以 Yarn 1 的 `yarn.lock` 为唯一纳入版本控制的锁文件，`package-lock.json` 已由 `.gitignore` 明确排除。部分开发文档仍展示 npm 命令，但便携构建脚本使用 `yarn install --frozen-lockfile`。仓库目前没有共享的 VS Code 工作区配置。

本次改造将引入 `@antfu/eslint-config`，迁移到 ESLint Flat Config，并让 ESLint 同时承担代码检查和格式化。IDE 与命令行必须使用同一份配置和修复机制。

## 目标

- 使用 `@antfu/eslint-config` 作为 Vue 3、TypeScript 和 JavaScript 的统一 ESLint 配置基础。
- 使用 ESLint 统一完成代码检查与格式化，移除 Prettier 工具链。
- 保留项目现有的必要规则语义和自动导入全局变量支持。
- 配置 VS Code，使保存时自动运行 ESLint 修复，并推荐所需扩展。
- 保持 Yarn 1 锁文件与 `package.json` 中的依赖一致。
- 不在本次迁移中批量格式化现有源码，避免产生大范围无关差异。

## 非目标

- 不调整业务代码或 Vue 组件行为。
- 不一次性修复全仓库已有的所有 lint 问题。
- 不引入新的测试框架、提交钩子或 staged-file 工具。
- 不修改后端 lint 或格式化配置。

## 方案

### ESLint 配置

新增 `frontend/eslint.config.mjs`，使用 `@antfu/eslint-config` 的 Flat Config API，并显式启用 Vue 和 TypeScript 支持。配置覆盖前端源码及现有 JavaScript、TypeScript、Vue 配置文件。

配置保留以下项目语义：

- 关闭 `vue/multi-word-component-names`。
- 未使用参数允许以下划线开头。
- 开发环境允许 `console` 和 `debugger`，生产环境将其视为警告。
- 读取 `.eslintrc-auto-import.json` 中由自动导入插件生成的 globals，避免把自动导入 API 误报为未定义。
- 对生成物、依赖目录、类型生成文件及其他现有无需检查的文件设置忽略规则。

移除传统 `.eslintrc.cjs`。不采用兼容层，避免新旧配置体系并存。

### 格式化策略

启用 Antfu 配置提供的 stylistic 规则，并尽量映射当前格式偏好：无分号、单引号、两个空格缩进、100 字符行宽、无尾随逗号等。移除 `.prettierrc.json`、`prettier` 和 `@vue/eslint-config-prettier`，同时移除被 Antfu 配置替代的直接 ESLint 插件与共享配置依赖。

不会在迁移提交中对 `src/` 执行全量 `--fix`。这样配置变更与未来的批量格式化可以独立审查。

### 命令行脚本

前端 `package.json` 提供三个明确入口：

- `lint`：运行 ESLint 检查，不写文件，适合 CI 和验证。
- `lint:fix`：运行 ESLint 并自动修复整个前端目录。
- `format`：使用 ESLint 修复 `src/`，作为开发者主动格式化源码的兼容入口。

命令不再使用已废弃或 Flat Config 不支持的 `--ext`、`--ignore-path` 参数。

### IDE Support

在仓库根目录新增共享的 `.vscode/settings.json`，并精确调整 `.gitignore`，只允许该文件和 `.vscode/extensions.json` 纳入版本控制：

- 指定 `frontend` 为 ESLint 工作目录，使从仓库根打开 VS Code 时能正确解析配置与依赖。
- 对 JavaScript、TypeScript、Vue 等前端文件启用 ESLint 校验。
- 保存时执行 `source.fixAll.eslint`。
- 关闭这些语言的默认 formatter，避免 ESLint 与 Prettier 或其他格式化器重复处理。
- 启用 Flat Config 支持所需的 ESLint 扩展设置；若当前扩展版本已默认支持，该设置仍应保持兼容或省略。

新增 `.vscode/extensions.json`，推荐安装 `dbaeumer.vscode-eslint`。不强制卸载用户全局安装的 Prettier 扩展，但工作区配置不会调用它。

### 依赖和锁文件

在 `frontend/package.json` 中新增仍支持 Node.js 18 的最新兼容版 `@antfu/eslint-config`，并将 ESLint 升级到该配置支持的版本。由于 ESLint 9 及所选 Antfu 传递依赖需要更高的 Node.js 18 补丁版本，`engines.node` 同步提高到已验证的最低兼容版本。只更新已纳入版本控制的 Yarn 1 `yarn.lock`，确保便携构建脚本的 `--frozen-lockfile` 不会失败；不生成或提交被项目明确忽略的 `package-lock.json`。

更新 `yarn.lock` 时必须保留工作区中用户已有的未提交修改，只叠加本次依赖解析结果。

## 风险控制

- 在编辑任何代码符号前执行 GitNexus 上游影响分析；本次预计只修改工具配置，不修改业务符号。
- 若新规则暴露大量历史问题，优先通过精确的迁移期规则覆盖保证 `lint` 可用，不通过全量改写源码掩盖问题。
- 若 Antfu 当前版本与项目 Node.js 18 下限不兼容，应选择仍支持 Node.js 18 的最新兼容版本，或明确提高 Node.js 要求；不静默留下安装后无法运行的组合。
- 依赖安装前后检查两个锁文件的差异，避免覆盖用户已有 Yarn 变更。

## 验证

在 `frontend/` 目录完成以下验证：

1. Yarn 1 锁文件可解析，且 frozen-lockfile 校验不要求额外更新。
2. `npm run lint` 能加载 Flat Config，并且不会写入源码。
3. 对临时样例或指定文件执行 ESLint 修复两次，第二次无差异，证明格式化幂等；不保留临时样例。
4. `npm run type-check` 通过。
5. `npm run build` 通过。
6. 检查 VS Code JSON 配置有效，工作目录、保存修复和扩展推荐均指向前端 ESLint。
7. 运行 GitNexus 变更检测，确认没有意外影响业务符号或执行流。

若仓库存在与本次工作无关的既有 lint、类型或构建失败，需记录完整命令、失败位置及其与本次变更的关系，不扩大本次范围处理。
