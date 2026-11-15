import { useEffect, useState } from 'react'
import { ApiError } from '../api'
import { categoryLabels, getTickets, priorityLabels, sortLabels, statusLabels } from '../tickets'
import type { TicketFilters, TicketPage } from '../tickets'

type Props = { page: number; filters: TicketFilters; refresh: number; onPageChange: (page: number) => void; onSessionExpired: () => void }
const dateFormat = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

export default function TicketList({ page, filters, refresh, onPageChange, onSessionExpired }: Props) {
  const [data, setData] = useState<TicketPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 10000)
    setLoading(true)
    setError('')
    getTickets(page, filters, controller.signal).then(result => {
      if (active) setData(result)
    }).catch(failure => {
      if (!active) return
      if (failure instanceof ApiError && failure.status === 401) { onSessionExpired(); return }
      setError(failure instanceof Error ? failure.message : 'Não foi possível carregar os tickets.')
    }).finally(() => {
      window.clearTimeout(timeout)
      if (active) setLoading(false)
    })
    return () => { active = false; window.clearTimeout(timeout); controller.abort() }
  }, [page, filters, refresh, retry, onSessionExpired])

  if (loading) return <p role="status" className="muted">Carregando tickets…</p>
  if (error) return <div><p role="alert" className="error">{error}</p>
    <button type="button" className="secondary" onClick={() => setRetry(value => value + 1)}>Tentar novamente</button></div>
  if (!data) return null
  const hasFilters = Boolean(filters.status || filters.category || filters.priority)
  if (data.total === 0) return <div className="empty-state">
    <h3>{hasFilters ? 'Nenhum ticket encontrado' : 'Nenhum ticket por aqui'}</h3>
    <p className="muted">{hasFilters ? 'Ajuste ou limpe os filtros para ver outros tickets.' : 'Novas solicitações aparecerão nesta lista.'}</p>
  </div>

  const pages = Math.max(1, Math.ceil(data.total / data.page_size))
  return <>
    <p className="list-count" role="status">{data.total} {data.total === 1 ? 'ticket encontrado' : 'tickets encontrados'}</p>
    <div className="table-scroll" role="region" aria-label="Lista de tickets" tabIndex={0}>
      <table>
        <caption className="sr-only">Tickets: {sortLabels[filters.sort]}</caption>
        <thead><tr><th scope="col">Número</th><th scope="col">Título</th><th scope="col">Solicitante</th>
          <th scope="col">Categoria</th><th scope="col">Prioridade</th><th scope="col">Status</th><th scope="col">Criado em</th></tr></thead>
        <tbody>{data.items.map(ticket => <tr key={ticket.id}>
          <td className="ticket-number">#{ticket.id}</td>
          <td className="ticket-title">{ticket.title}</td>
          <td className="requester-name">{ticket.requester.name}</td>
          <td>{categoryLabels[ticket.category]}</td>
          <td><span className={`badge priority-${ticket.priority}`}>{priorityLabels[ticket.priority]}</span></td>
          <td><span className="badge status-badge">{statusLabels[ticket.status]}</span></td>
          <td className="ticket-date"><time dateTime={ticket.created_at}>{dateFormat.format(new Date(ticket.created_at))}</time></td>
        </tr>)}</tbody>
      </table>
    </div>
    <nav className="pagination" aria-label="Paginação de tickets">
      <span>Página {data.page} de {pages}</span>
      <div><button className="secondary" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Anterior</button>
        <button className="secondary" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>Próxima</button></div>
    </nav>
  </>
}
