export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const raw = await res.text().catch(() => '')
    let message = raw || res.statusText
    try {
      const parsed = JSON.parse(raw)
      if (parsed && typeof parsed.detail === 'string') message = parsed.detail
    } catch { /* 非 JSON 错误体，沿用原文 */ }
    const err = new Error(message) as Error & { status: number }
    err.status = res.status
    throw err
  }
  if (res.status === 204) return undefined as T
  return res.json()
}
