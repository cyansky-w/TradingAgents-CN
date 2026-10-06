<script setup lang="ts">
import { ArrowLeft } from '@element-plus/icons-vue'

defineProps<{
  workflowName: string
  errorCount: number
  saving: boolean
}>()

defineEmits<{
  back: []
  validate: []
  save: []
  run: []
}>()
</script>

<template>
  <div class="editor-toolbar">
    <el-button text @click="$emit('back')">
      <el-icon><ArrowLeft /></el-icon> 返回列表
    </el-button>
    <span class="toolbar-title">{{ workflowName }}</span>
    <div class="toolbar-actions">
      <el-tag v-if="errorCount > 0" type="danger" size="small">
        {{ errorCount }} 个错误
      </el-tag>
      <el-tag v-else type="success" size="small">
        校验通过
      </el-tag>
      <el-button size="small" @click="$emit('validate')">
        校验
      </el-button>
      <el-button size="small" type="primary" :loading="saving" @click="$emit('save')">
        保存
      </el-button>
      <el-button size="small" type="success" @click="$emit('run')">
        运行
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.editor-toolbar {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  gap: 12px;
}
.toolbar-title {
  font-weight: 500;
  font-size: 16px;
  flex: 1;
}
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
