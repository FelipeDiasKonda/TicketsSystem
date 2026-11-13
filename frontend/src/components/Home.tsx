import { useEffect, useState } from 'react'
import { checkHealth } from '../api'
import { roleLabels } from '../auth'
import type { User } from '../auth'

type Props = { user: User; onLogout: () => Promise<void>; busy: boolean; error: string }

export default function Home({ user, onLogout, busy, error }: Props) {
  const [online, setOnline] = useState<boolean | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 5000)
    checkHealth(controller.signal).then(() => {
      if (!controller.signal.aborted) setOnline(true)
    }).catch(() => {
      if (!controller.signal.aborted) setOnline(false)
    }).finally(() => window.clearTimeout(timeout))
    return () => { window.clearTimeout(timeout); controller.abort() }
  }, [])

  return <section className="home-card">
    <p className="eyebrow">PORTAL DE SUPORTE</p>
    <h1>Olá, {user.name}.</h1>
    <p className="intro">Você está conectado como <strong>{roleLabels[user.role]}</strong>.</p>
    <p className="muted">{user.email}</p>
    <div className="connection" role="status">
      <span className={`dot ${online === true ? 'online' : online === false ? 'offline' : ''}`} />
      {online === null ? 'Verificando API…' : online ? 'API conectada' : 'API indisponível'}
    </div>
    <p className="muted">Sua conta está pronta. O gerenciamento de tickets será adicionado na próxima etapa.</p>
    {error && <p role="alert" className="error">{error}</p>}
    <button onClick={() => void onLogout()} disabled={busy}>{busy ? 'Saindo…' : 'Sair da conta'}</button>
  </section>
}
