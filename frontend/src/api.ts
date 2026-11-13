const apiUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export async function checkHealth(signal: AbortSignal): Promise<void> {
  const response = await fetch(`${apiUrl}/api/health`, { signal })
  if (!response.ok) throw new Error('API indisponível')
  const data: unknown = await response.json()
  if (typeof data !== 'object' || data === null || !('status' in data) || data.status !== 'ok') {
    throw new Error('Resposta inesperada da API')
  }
}
