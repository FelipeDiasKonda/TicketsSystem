import { useState } from 'react'
import { roleLabels } from '../auth'
import type { User } from '../auth'
import type { Ticket } from '../tickets'
import TicketForm from './TicketForm'
import TicketList from './TicketList'

type Props = {
  user: User
  onLogout: () => Promise<void>
  busy: boolean
  error: string
  onSessionExpired: () => void
}

export default function Home({ user, onLogout, busy, error, onSessionExpired }: Props) {
  const [showForm, setShowForm] = useState(false)
  const [page, setPage] = useState(1)
  const [refresh, setRefresh] = useState(0)
  const [success, setSuccess] = useState('')

  function created(ticket: Ticket) {
    setShowForm(false)
    setPage(1)
    setRefresh(value => value + 1)
    setSuccess(`Ticket #${ticket.id} criado com sucesso.`)
  }

  return <>
    <div className="account-bar">
      <p><strong>{user.name}</strong><span className="account-role">{roleLabels[user.role]}</span></p>
      <button className="secondary" onClick={() => void onLogout()} disabled={busy}>{busy ? 'Saindo…' : 'Sair da conta'}</button>
    </div>
    {error && <p role="alert" className="error">{error}</p>}
    <section className="tickets-panel">
      <div className="panel-heading">
        <div><p className="eyebrow">PORTAL DE SUPORTE</p>
          <h1>{user.role === 'support' ? 'Todos os tickets' : 'Meus tickets'}</h1>
          <p className="muted">{user.role === 'support'
            ? 'Acompanhe as solicitações da equipe, incluindo as suas.'
            : 'Abra uma solicitação e acompanhe seus tickets.'}</p>
        </div>
        {!showForm && <button onClick={() => { setSuccess(''); setShowForm(true) }}>+ Novo ticket</button>}
      </div>
      {success && <p role="status" className="success">{success}</p>}
      {showForm && <TicketForm onCreated={created} onCancel={() => setShowForm(false)} onSessionExpired={onSessionExpired} />}
      <TicketList page={page} refresh={refresh} onPageChange={setPage} onSessionExpired={onSessionExpired} />
    </section>
  </>
}
