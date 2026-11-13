import { useEffect, useState } from 'react'
import { ApiError } from './api'
import { getCurrentUser, logout } from './auth'
import type { User } from './auth'
import AuthForm from './components/AuthForm'
import Home from './components/Home'

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setLoadError('')
    getCurrentUser().then(value => { if (active) setUser(value) }).catch(failure => {
      if (active && !(failure instanceof ApiError && failure.status === 401)) {
        setLoadError(failure instanceof Error ? failure.message : 'Não foi possível verificar sua sessão.')
      }
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [attempt])

  async function signOut() {
    if (busy) return
    setBusy(true)
    setError('')
    try { await logout(); setUser(null) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Não foi possível sair.') }
    finally { setBusy(false) }
  }

  return <main>
    <header><span className="logo">TS</span><strong>Tickets System</strong><span className="version">Suporte interno</span></header>
    {loading ? <section role="status">Verificando sua sessão…</section>
      : loadError ? <section><h1>Vamos tentar novamente?</h1><p role="alert" className="error">{loadError}</p>
          <button onClick={() => setAttempt(value => value + 1)}>Tentar novamente</button></section>
      : user ? <Home user={user} onLogout={signOut} busy={busy} error={error} />
      : <AuthForm onAuthenticated={value => { setError(''); setUser(value) }} />}
    <footer>Tickets System · Portal de suporte da equipe</footer>
  </main>
}
