import { useEffect, useState } from 'react'
import { ApiError } from '../api'
import { getComments, getHistory } from '../ticketDetails'
import type { ActivityPage, Comment, HistoryItem } from '../ticketDetails'
import { statusLabels } from '../tickets'

export const formatDate = (value: string) => new Date(value).toLocaleString('pt-BR')

function historyText(item: HistoryItem) {
  if (item.event === 'created') return 'Criou o ticket.'
  if (item.event === 'snapshot') return `Estado observado na migração: ${statusLabels[item.new_status!]}.`
  if (item.event === 'assignment') return `Responsável: ${item.previous_assignee?.name ?? 'Não atribuído'} → ${item.new_assignee?.name ?? 'Não atribuído'}.`
  return `Status: ${statusLabels[item.previous_status!]} → ${statusLabels[item.new_status!]}.`
}

type Props = { ticketId: number; tab: 'comments' | 'history'; onSessionExpired: () => void }
export default function TicketActivity({ ticketId, tab, onSessionExpired }: Props) {
  const [page, setPage] = useState(1)
  const [data, setData] = useState<ActivityPage<Comment> | ActivityPage<HistoryItem> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const timer = window.setTimeout(() => controller.abort(), 10000)
    setLoading(true); setError('')
    const request = tab === 'comments' ? getComments(ticketId, page, controller.signal)
      : getHistory(ticketId, page, controller.signal)
    request.then(result => { if (active) setData(result) }).catch(failure => {
      if (!active) return
      if (failure instanceof ApiError && failure.status === 401) { onSessionExpired(); return }
      setError(failure instanceof Error ? failure.message : 'Não foi possível carregar a atividade.')
    }).finally(() => { window.clearTimeout(timer); if (active) setLoading(false) })
    return () => { active = false; window.clearTimeout(timer); controller.abort() }
  }, [ticketId, tab, page, retry, onSessionExpired])

  return <>
    {loading && <p role="status">Carregando atividade…</p>}
    {!loading && error && <div>
      <p role="alert" className="error">{error}</p>
      <button className="secondary" onClick={() => setRetry(value => value + 1)}>Tentar novamente</button>
    </div>}
    {!loading && !error && data && <>
      {!data.total && <p className="muted">{tab === 'comments' ? 'Nenhum comentário ainda.' : 'Nenhum registro.'}</p>}
      <ol className="activity-list">
        {data.items.map(item => <li key={item.id}>
          <div className="activity-meta"><strong>{'body' in item ? item.author.name : item.actor?.name ?? 'Sistema'}</strong>
            <time dateTime={'body' in item ? item.created_at : item.changed_at}>
              {formatDate('body' in item ? item.created_at : item.changed_at)}</time></div>
          <p className="plain-text">{'body' in item ? item.body : historyText(item)}</p>
        </li>)}
      </ol>
      {data.total > data.page_size && <nav className="pagination" aria-label="Paginação da atividade">
        <span>Página {page} de {Math.ceil(data.total / data.page_size)}</span>
        <div><button className="secondary" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Anterior</button>
          <button className="secondary" disabled={page * data.page_size >= data.total} onClick={() => setPage(value => value + 1)}>Próxima</button></div>
      </nav>}
    </>}
  </>
}
