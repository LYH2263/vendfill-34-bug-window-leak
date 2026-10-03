<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
const loading = ref(true)
const running = ref(false)
const error = ref('')

function hhmm(m: number | null | undefined): string {
  if (m === null || m === undefined) return ''
  const h = Math.floor(m / 60).toString().padStart(2, '0')
  const mm = (m % 60).toString().padStart(2, '0')
  return `${h}:${mm}`
}

async function loadLatest() {
  // 只展示最近一次成功单，绝不借查看之名写新单
  loading.value = true
  try { data.value = await api('/refills/latest?location_id=1') } catch { /* 无成功单且窗外 */ data.value = null }
  loading.value = false
}

async function run() {
  error.value = ''
  running.value = true
  try {
    // 窗内按现网规则落新单；窗外后端 403 且不新增单据
    data.value = await api('/refills/run?location_id=1', { method: 'POST' })
  } catch (e: any) {
    // 失败原因只展示后端口径：不在补货时段
    error.value = e?.status === 403 ? (e?.message || '不在补货时段') : (e?.message || '生成失败')
    try { data.value = await api('/refills/latest?location_id=1') } catch { /* 无历史单 */ }
  } finally {
    running.value = false
  }
}

onMounted(loadLatest)
</script>
<template>
  <h1>补货小票</h1>
  <p class="sub">gap = 容量 − 库存 − 在途 · 收据纸样式 · 半开补货时段窗 [开始, 结束)</p>
  <div style="display:flex;align-items:center;gap:0.8rem;flex-wrap:wrap">
    <button class="btn" :disabled="running" @click="run">{{ running ? '生成中…' : '生成补货单' }}</button>
    <span v-if="data" class="muted" style="font-size:0.78rem">
      补货时段：
      <template v-if="data.fill_start_minute === null || data.fill_end_minute === null">不限制</template>
      <template v-else>{{ hhmm(data.fill_start_minute) }} – {{ hhmm(data.fill_end_minute) }}</template>
      <span :style="{ color: data.fill_open ? '#3c8f4f' : '#d9534f', fontWeight: 700 }">
        （{{ data.fill_open ? '当前窗内·可生成' : '当前窗外·不可生成' }}）
      </span>
    </span>
  </div>
  <p v-if="error" role="alert" style="color:#d9534f;margin:0.6rem 0 0;font-weight:700">{{ error }}</p>
  <p v-if="loading" class="muted">加载最近补货单…</p>
  <p v-else-if="!data" class="muted" style="margin-top:1rem">尚无补货单，且当前不在补货时段。</p>
  <div style="margin-top:1rem" v-if="data">
    <div class="vf-receipt">
      <h2>*** VendFill 补货单 ***</h2>
      <div class="vf-receipt-line" style="font-weight:700;border-bottom:2px dashed #8a7e64">
        <span>货道 / 商品</span><span>补量</span>
      </div>
      <div class="vf-receipt-line" v-for="l in data.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}
          <small>({{ l.status === 'need_fill' ? '待补' : l.status === 'full' ? '满仓' : '超占' }})</small>
        </span>
        <span>{{ l.fill_qty }} / 缺{{ l.gap }}</span>
      </div>
      <p style="text-align:center;margin:1rem 0 0;font-size:0.72rem;color:#6a5e48">谢谢使用 · 请核对后装机</p>
    </div>
  </div>
</template>
