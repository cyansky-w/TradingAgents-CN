<template>
  <div v-if="modelValue" class="overlay" @click.self="$emit('update:modelValue', false)">
    <section class="dialog"><header><h2>交易与持仓记录</h2><button title="关闭" @click="$emit('update:modelValue', false)">×</button></header>
      <div class="filters"><input v-model="symbol" placeholder="标的代码" /><select v-model="market"><option value="">全部市场</option><option>CN</option><option>HK</option><option>US</option><option>CRYPTO</option></select><button @click="$emit('refresh', { symbol, market })">筛选</button></div>
      <div class="records"><table><thead><tr><th>时间</th><th>标的</th><th>类型</th><th>方向</th><th>价格</th><th>数量</th><th>费用</th><th>操作</th></tr></thead>
        <tbody><tr v-for="record in records" :key="record.id"><td>{{ record.trade_time || record.trade_date }}</td><td>{{ record.symbol || record.code }}</td><td>{{ record.record_type || 'trade' }}</td><td>{{ record.position_side || 'long' }} / {{ record.position_action || record.side }}</td><td>{{ record.price }}</td><td>{{ record.quantity }}</td><td>{{ record.fee_amount ?? record.commission ?? '-' }} {{ record.fee_currency || record.currency }}</td><td><button @click="$emit('edit', record)">编辑</button><button class="danger" @click="$emit('delete', record)">删除</button></td></tr></tbody>
      </table></div>
      <footer>共 {{ total }} 条</footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ modelValue: boolean; records: any[]; total: number }>()
defineEmits<{ 'update:modelValue': [value: boolean]; refresh: [filters: { symbol: string; market: string }]; edit: [record: any]; delete: [record: any] }>()
const symbol = ref('')
const market = ref('')
</script>

<style scoped>
.overlay { position: fixed; inset: 0; z-index: 2000; display: grid; place-items: center; padding: 20px; background: rgba(0,0,0,.45); } .dialog { width: min(1100px, 100%); max-height: 85vh; overflow: auto; background: white; border-radius: 6px; } header, footer, .filters { display: flex; align-items: center; gap: 10px; padding: 14px 18px; border-bottom: 1px solid #ebeef5; } header { justify-content: space-between; } h2 { margin: 0; font-size: 17px; } header button { border: 0; background: transparent; font-size: 24px; } input, select { height: 34px; border: 1px solid #dcdfe6; border-radius: 4px; padding: 0 9px; } button { cursor: pointer; } .records { overflow-x: auto; } table { width: 100%; min-width: 900px; border-collapse: collapse; } th, td { padding: 10px 12px; border-bottom: 1px solid #ebeef5; text-align: left; font-size: 12px; } .danger { color: #c53030; margin-left: 8px; } footer { justify-content: flex-end; color: #909399; }
</style>
