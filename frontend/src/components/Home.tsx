import { useRef, useState } from 'react'
import { ApiError } from '../api'
import { roleLabels } from '../auth'
import type { User } from '../auth'
import { defaultTicketFilters, statusLabels, updateTicketStatus } from '../tickets'
import type { Ticket, TicketFilters as Filters, TicketStatus, TicketSummary } from '../tickets'
import TicketForm from './TicketForm'
import TicketList from './TicketList'
import TicketFilters from './TicketFilters'
import TicketBoard from './TicketBoard'
import TicketDetailsModal from './TicketDetailsModal'

type Props = {
  user: User
  onLogout: () => Promise<void>
  busy: boolean
  error: string
  onSessionExpired: () => void
}

export default function Home({ user, onLogout, busy, error, onSessionExpired }: Props) {
  const [view, setView] = useState<'list' | 'board'>('list')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [movingId, setMovingId] = useState<number | null>(null)
  const [moveError, setMoveError] = useState('')
  const moving = useRef(false)
  const [showForm, setShowForm] = useState(false)
  const [page, setPage] = useState(1)
  const [refresh, setRefresh] = useState(0)
  const [success, setSuccess] = useState('')
  const [filters, setFilters] = useState<Filters>(defaultTicketFilters)

  function changeFilters(next: Filters) {
    setFilters(next)
    setPage(1)
  }

  async function moveTicket(ticket: TicketSummary, status: TicketStatus) {
    if (moving.current || user.role !== 'support') return
    moving.current = true
    setMovingId(ticket.id)
    setMoveError('')
    setSuccess('')
    try {
      const updated = await updateTicketStatus(ticket, status)
      const hidden = filters.status && filters.status !== updated.status
      setSuccess(`Ticket #${ticket.id} atualizado para ${statusLabels[updated.status]}.${hidden ? ' Ele saiu do filtro de status atual.' : ''}`)
      setRefresh(value => value + 1)
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) { onSessionExpired(); return }
      setMoveError(failure instanceof Error ? failure.message : 'Não foi possível atualizar o status.')
      // A timeout may occur after the server commits; reload instead of guessing the state.
      if (failure instanceof ApiError && (failure.status === 409 || failure.status === 0)) {
        setRefresh(value => value + 1)
      }
    } finally { moving.current = false; setMovingId(null) }
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
      {moveError && <p role="alert" className="error">{moveError}</p>}
      {success && <p role="status" className="success">{success}</p>}
      {showForm && <TicketForm onCreated={created} onCancel={() => setShowForm(false)} onSessionExpired={onSessionExpired} />}
      <TicketFilters value={filters} onChange={changeFilters} />
      <div className="view-switch" role="group" aria-label="Visualização de tickets">
        <button type="button" className="secondary" aria-pressed={view === 'list'} onClick={() => setView('list')}>Lista</button>
        <button type="button" className="secondary" aria-pressed={view === 'board'} onClick={() => setView('board')}>Quadro</button>
      </div>
      {view === 'list'
        ? <TicketList page={page} filters={filters} refresh={refresh} onPageChange={setPage}
            onSessionExpired={onSessionExpired} canEdit={user.role === 'support'} movingId={movingId} onMove={moveTicket} onOpen={setSelectedId} />
        : <TicketBoard filters={filters} refresh={refresh} onSessionExpired={onSessionExpired}
            canEdit={user.role === 'support'} movingId={movingId} onMove={moveTicket} onOpen={setSelectedId} />}
      {selectedId !== null && <TicketDetailsModal key={selectedId} ticketId={selectedId} user={user}
        onClose={() => setSelectedId(null)} onChanged={() => setRefresh(value => value + 1)}
        onSessionExpired={onSessionExpired} />}

    </section>
  </>
}
