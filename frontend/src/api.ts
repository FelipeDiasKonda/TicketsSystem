const apiUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiUrl}/api${path}`, {
      ...init,
      credentials: 'include',
      signal: init.signal ?? AbortSignal.timeout(10000),
      headers: {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(init.method === 'POST' ? { 'X-CSRF-Protection': '1' } : {}),
        ...init.headers,
      },
    })
  } catch {
    throw new ApiError(0, 'Não foi possível conectar ao servidor. Tente novamente.')
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    const message = typeof data?.detail === 'string'
      ? data.detail
      : response.status === 422
        ? 'Confira os dados informados e tente novamente.'
        : 'Não foi possível concluir a solicitação. Tente novamente.'
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function checkHealth(signal: AbortSignal): Promise<void> {
  const data = await apiRequest<{ status: string }>('/health', { signal })
  if (data.status !== 'ok') throw new Error('Resposta inesperada da API')
}
