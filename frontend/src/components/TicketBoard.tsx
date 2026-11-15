import { useEffect, useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { ApiError } from '../api'
import { categoryLabels, getTickets, nextTicketStatus, priorityLabels, statusLabels, ticketStatuses } from '../tickets'
import type { MoveTicket, TicketFilters, TicketStatus, TicketSummary } from '../tickets'

type Props = {
  filters: TicketFilters; refresh: number; canEdit: boolean; movingId: number | null
  onMove: MoveTicket; onSessionExpired: () => void; onOpen: (id: number) => void
}
type ColumnProps = Props & {
  status: TicketStatus; dragged: TicketSummary | null; onDrag: (ticket: TicketSummary | null) => void
}

function BoardColumn({ status, filters, canEdit, movingId, onMove, onSessionExpired, dragged, onDrag, onOpen }: ColumnProps) {
  const dragOccurred = useRef(false)
  const [items, setItems] = useState<TicketSummary[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const excluded = Boolean(filters.status && filters.status !== status)
  const canDrop = canEdit && movingId === null && dragged !== null && nextTicketStatus[dragged.status] === status

  useEffect(() => {
    if (excluded) { setTotal(0); setLoading(false); return }
    let active = true
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 10000)
    setLoading(true)
    setError('')
    getTickets(page, { ...filters, status }, controller.signal).then(result => {
      if (!active) return
      setTotal(result.total)
      setItems(previous => page === 1 ? result.items
        : Array.from(new Map([...previous, ...result.items].map(ticket => [ticket.id, ticket])).values()))
    }).catch(failure => {
      if (!active) return
      if (failure instanceof ApiError && failure.status === 401) { onSessionExpired(); return }
      setError(failure instanceof Error ? failure.message : 'Não foi possível carregar a coluna.')
    }).finally(() => {
      window.clearTimeout(timeout)
      if (active) setLoading(false)
    })
    return () => { active = false; window.clearTimeout(timeout); controller.abort() }
  }, [status, filters, page, retry, excluded, onSessionExpired])

  function drop(event: DragEvent<HTMLElement>) {
    event.preventDefault()
    if (canDrop && dragged) void onMove(dragged, status)
    onDrag(null)
  }

  return <div className={`board-column column-${status}${canDrop ? ' can-drop' : ''}`}
    data-status={status} aria-label={`Coluna ${statusLabels[status]}`}
    onDragOver={event => { if (canDrop) { event.preventDefault(); event.dataTransfer.dropEffect = 'move' } }}
    onDrop={drop}>
    <h3><span>{statusLabels[status]}</span><span className="column-count" aria-label="Total de tickets">{total ?? '…'}</span></h3>
    {canDrop && <p className="drop-hint">Solte aqui para avançar</p>}
    {items.map(ticket => {
      const next = nextTicketStatus[ticket.status]
      const draggable = canEdit && Boolean(next) && movingId === null
      return <article key={ticket.id} className={`ticket-card${draggable ? ' draggable' : ''}`}
        data-ticket-id={ticket.id} draggable={draggable}
        onPointerDown={() => { dragOccurred.current = false }}
        onClick={event => {
          if (dragOccurred.current || (event.target as HTMLElement).closest('button')) return
          event.currentTarget.querySelector<HTMLButtonElement>('.ticket-open')?.focus()
          onOpen(ticket.id)
        }}
        onDragStart={event => {
          if (!draggable) { event.preventDefault(); return }
          event.dataTransfer.setData('text/plain', String(ticket.id))
          event.dataTransfer.effectAllowed = 'move'
          dragOccurred.current = true
          onDrag(ticket)
        }} onDragEnd={() => onDrag(null)}>
        <div className="card-meta"><span>#{ticket.id}</span><span>{categoryLabels[ticket.category]}</span></div>
        <h4><button className="ticket-open" onClick={() => { if (!dragOccurred.current) onOpen(ticket.id) }}>{ticket.title}</button></h4>
        <p className="card-requester">{ticket.requester.name}</p>
        <div className="card-meta"><span className={`badge priority-${ticket.priority}`}>{priorityLabels[ticket.priority]}</span>
          <time dateTime={ticket.created_at}>{new Date(ticket.created_at).toLocaleDateString('pt-BR')}</time></div>
        {canEdit && next && <button type="button" className="secondary card-move" disabled={movingId !== null}
          aria-label={`Mover ticket #${ticket.id} para ${statusLabels[next]}`}
          onClick={() => void onMove(ticket, next)}>
          {movingId === ticket.id ? 'Atualizando…' : `Avançar para ${statusLabels[next]}`}
        </button>}
      </article>
    })}
    {error && <div><p role="alert" className="error">{error}</p>
      <button className="secondary" onClick={() => setRetry(value => value + 1)}>Tentar novamente</button></div>}
    {loading && <p role="status" className="muted">Carregando…</p>}
    {!loading && !error && items.length === 0 && <p className="column-empty">
      {excluded ? 'Fora do filtro de status selecionado.' : 'Nenhum ticket nesta coluna.'}</p>}
    {!error && total !== null && items.length < total && <button className="secondary load-more"
      disabled={loading} onClick={() => setPage(value => value + 1)}>
      Carregar mais ({items.length} de {total})</button>}
  </div>
}

export default function TicketBoard(props: Props) {
  const [dragged, setDragged] = useState<TicketSummary | null>(null)
  const queryKey = `${JSON.stringify(props.filters)}:${props.refresh}`
  return <>
    <p className="board-help">{props.canEdit
      ? 'Arraste para a próxima coluna ou use o botão do cartão. Etapas não podem ser puladas.'
      : 'Acompanhe seus tickets nas etapas do atendimento.'}</p>
    <div className="ticket-board" aria-label="Quadro de tickets">
      {ticketStatuses.map(status => <BoardColumn {...props} key={`${status}:${queryKey}`} status={status}
        dragged={dragged} onDrag={setDragged} />)}
    </div>
  </>
}
