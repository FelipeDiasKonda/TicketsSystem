import { useState } from 'react'
import { roleLabels } from '../auth'
import type { User } from '../auth'
import { defaultTicketFilters } from '../tickets'
import type { Ticket, TicketFilters as Filters } from '../tickets'
import TicketForm from './TicketForm'
import TicketList from './TicketList'
import TicketFilters from './TicketFilters'

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
  const [filters, setFilters] = useState<Filters>(defaultTicketFilters)

  function changeFilters(next: Filters) {
    setFilters(next)
    setPage(1)
  }

  function created(ticket: Ticket) {
    setShowForm(false)
    setPage(1)
    setRefresh(value => value + 1)
    const matchesFilters = (!filters.status || filters.status === ticket.status)
      && (!filters.category || filters.category === ticket.category)
      && (!filters.priority || filters.priority === ticket.priority)
    setSuccess(`Ticket #${ticket.id} criado com sucesso.${matchesFilters ? '' : ' Ele não corresponde aos filtros ativos.'}`)
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
      <TicketFilters value={filters} onChange={changeFilters} />
      <TicketList page={page} filters={filters} refresh={refresh} onPageChange={setPage} onSessionExpired={onSessionExpired} />
    </section>
  </>
}
