import { useEffect, useState } from 'react'
import { checkHealth } from './api'

type ApiStatus = 'checking' | 'online' | 'offline'

const labels: Record<ApiStatus, string> = {
  checking: 'Verificando conexão com a API…',
  online: 'API conectada',
  offline: 'API indisponível. Verifique se o backend está iniciado.',
}

export default function App() {
  const [status, setStatus] = useState<ApiStatus>('checking')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const timeout = window.setTimeout(() => controller.abort(), 5000)
    setStatus('checking')
    checkHealth(controller.signal)
      .then(() => { if (active) setStatus('online') })
      .catch(() => { if (active) setStatus('offline') })
      .finally(() => window.clearTimeout(timeout))
    return () => {
      active = false
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [attempt])

  return (
    <main>
      <header><span className="logo">TS</span><strong>Tickets System</strong><span className="version">v0</span></header>
      <section>
        <p className="eyebrow">SUPORTE INTERNO</p>
        <h1>Um lugar para cada solicitação.</h1>
        <p className="intro">Base inicial do portal de suporte. O próximo passo é implementar a criação e o acompanhamento dos tickets.</p>
        <div className="connection" role="status" aria-live="polite">
          <span className={`dot ${status}`} aria-hidden="true" />
          <span>{labels[status]}</span>
        </div>
        <button onClick={() => setAttempt(value => value + 1)} disabled={status === 'checking'}>Verificar conexão</button>
      </section>
      <footer>React · FastAPI · MySQL</footer>
    </main>
  )
}
