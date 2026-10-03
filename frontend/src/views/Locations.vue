<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const rows = ref<any[]>([])
// 每个点位一份草稿（字符串，空串表示未填）；保存成功后才以服务端返回为准，拒绝时保持改前。
const drafts = ref<Record<number, { start: string; end: string }>>({})
const errors = ref<Record<number, string>>({})
const saving = ref<Record<number, boolean>>({})

function toMinute(v: string): number | null {
  return v.trim() === '' ? null : Number(v)
}

// 与后端 app.services.time_window.validate_window 同一套规则，仅用于即时提示；
// 是否放行一律以服务端保存后返回的 fill_open 为准。
function validate(start: number | null, end: number | null): string | null {
  if (start === null && end === null) return null
  if (start === null || end === null) return '开始与结束必须同时填写或同时清空'
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || start > 1439 || end < 0 || end > 1439)
    return '分钟数越界（0-1439）'
  if (end <= start) return '结束必须大于开始（半开区间）'
  return null
}

function hhmm(m: number | null): string {
  if (m === null || m === undefined) return '不限'
  const h = Math.floor(m / 60).toString().padStart(2, '0')
  const mm = (m % 60).toString().padStart(2, '0')
  return `${h}:${mm}`
}

async function load() {
  rows.value = await api('/locations')
  for (const r of rows.value) {
    drafts.value[r.id] = {
      start: r.fill_start_minute === null || r.fill_start_minute === undefined ? '' : String(r.fill_start_minute),
      end: r.fill_end_minute === null || r.fill_end_minute === undefined ? '' : String(r.fill_end_minute),
    }
  }
}

async function save(r: any) {
  errors.value[r.id] = ''
  const start = toMinute(drafts.value[r.id].start)
  const end = toMinute(drafts.value[r.id].end)
  const bad = validate(start, end)
  if (bad) { errors.value[r.id] = bad; return }
  saving.value[r.id] = true
  try {
    const saved = await api(`/locations/${r.id}`, {
      method: 'PUT',
      body: JSON.stringify({ fill_start_minute: start, fill_end_minute: end }),
    })
    // 以刚保存的窗界、服务端同一口径当场判定能否落单
    Object.assign(r, saved)
  } catch (e: any) {
    // 保存被拒：点位与单据保持改前，草稿回到库里现值
    errors.value[r.id] = e?.message || '保存失败'
    drafts.value[r.id] = {
      start: r.fill_start_minute === null ? '' : String(r.fill_start_minute),
      end: r.fill_end_minute === null ? '' : String(r.fill_end_minute),
    }
  } finally {
    saving.value[r.id] = false
  }
}

onMounted(load)
</script>
<template>
  <h1>点位 / 机位</h1>
  <p class="sub">左侧机位选择器对应的点位档案 · 补货时段窗为一天内分钟数，半开区间 [开始, 结束)；两端留空表示不限制</p>
  <div class="vf-site-rail" style="flex-direction:row;flex-wrap:wrap;border:none;background:transparent;padding:0;gap:0.5rem;margin-bottom:1rem">
    <div v-for="r in rows" :key="r.id ?? JSON.stringify(r)" class="vf-site-btn" style="min-width:140px">
      <strong style="display:block;color:var(--vf-led)">{{ r.code }}</strong>
      <span style="font-size:0.7rem">{{ r.name }}</span>
    </div>
  </div>
  <div class="card">
    <table>
      <thead>
        <tr>
          <th>编码</th><th>名称</th><th>地址</th>
          <th>补货时段窗（分钟 / 时刻）</th><th>当前能否落单</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.code }}</td>
          <td>{{ r.name }}</td>
          <td>{{ r.address }}</td>
          <td>
            <div style="display:flex;align-items:center;gap:0.4rem;flex-wrap:wrap">
              <input v-model="drafts[r.id].start" type="number" min="-999" max="1439" step="1"
                     style="width:5.5rem" placeholder="开始分钟" :disabled="saving[r.id]" />
              <span>–</span>
              <input v-model="drafts[r.id].end" type="number" min="-999" max="1439" step="1"
                     style="width:5.5rem" placeholder="结束分钟" :disabled="saving[r.id]" />
              <span class="muted" style="font-size:0.72rem">
                [{{ hhmm(toMinute(drafts[r.id].start)) }}, {{ hhmm(toMinute(drafts[r.id].end)) }})
              </span>
            </div>
            <small v-if="errors[r.id]" style="color:#d9534f">{{ errors[r.id] }}</small>
          </td>
          <td>
            <span v-if="r.fill_start_minute === null && r.fill_end_minute === null" class="muted">不限制</span>
            <span v-else-if="r.fill_open" style="color:#3c8f4f;font-weight:700">窗内 · 可生成</span>
            <span v-else style="color:#d9534f;font-weight:700">窗外 · 不可生成</span>
          </td>
          <td>
            <button class="btn" style="padding:0.25rem 0.7rem" :disabled="saving[r.id]" @click="save(r)">
              {{ saving[r.id] ? '保存中…' : '保存窗' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
