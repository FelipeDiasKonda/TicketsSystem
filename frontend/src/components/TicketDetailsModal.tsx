import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { ApiError } from '../api'
import type { User } from '../auth'
import { assignTicket, getSupportMembers, getTicketDetails, postComment } from '../ticketDetails'
import type { Person, TicketDetails } from '../ticketDetails'
import { categoryLabels, priorityLabels, updateTicketStatus } from '../tickets'
import type { TicketStatus, TicketSummary } from '../tickets'
import TicketStatusControl from './TicketStatusControl'
import TicketActivity, { formatDate } from './TicketActivity'
import TicketAssigneeMenu from './TicketAssigneeMenu'

type Props = {
  ticketId: number; user: User; onClose: () => void; onChanged: () => void
  onSessionExpired: () => void
}

export default function TicketDetailsModal({ ticketId, user, onClose, onChanged, onSessionExpired }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)
  const mounted = useRef(false)
  const mutating = useRef(false)
  const [ticket, setTicket] = useState<TicketDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  const [members, setMembers] = useState<Person[]>([])
  const [memberError, setMemberError] = useState('')
  const [membersLoaded, setMembersLoaded] = useState(false)
  const [memberRetry, setMemberRetry] = useState(0)
  const [tab, setTab] = useState<'comments' | 'history'>('comments')
  const [activityVersion, setActivityVersion] = useState(0)
  const [body, setBody] = useState('')
  const canEdit = user.role === 'support'

  useEffect(() => {
    mounted.current = true
    const opener = document.activeElement as HTMLElement | null
    const element = dialog.current!
    element.showModal()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      mounted.current = false
      element.close()
      document.body.style.overflow = previousOverflow
      if (opener?.isConnected) opener.focus()
      else document.querySelector<HTMLButtonElement>('.view-switch button[aria-pressed="true"]')?.focus()
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const timer = window.setTimeout(() => controller.abort(), 10000)
    setLoading(true); setError('')
    getTicketDetails(ticketId, controller.signal).then(result => { if (active) setTicket(result) })
      .catch(failure => {
        if (!active) return
        if (failure instanceof ApiError && failure.status === 401) { onSessionExpired(); return }
        setError(failure instanceof Error ? failure.message : 'Não foi possível carregar o ticket.')
      }).finally(() => { window.clearTimeout(timer); if (active) setLoading(false) })
    return () => { active = false; window.clearTimeout(timer); controller.abort() }
  }, [ticketId, retry, onSessionExpired])

  useEffect(() => {
    if (!canEdit) return
    const controller = new AbortController()
    let active = true
    const timer = window.setTimeout(() => controller.abort(), 10000)
    setMemberError(''); setMembersLoaded(false)
    getSupportMembers(controller.signal).then(result => {
      if (active) { setMembers(result); setMembersLoaded(true) }
    }).catch(failure => {
      if (!active) return
      if (failure instanceof ApiError && failure.status === 401) { onSessionExpired(); return }
      setMemberError('Não foi possível carregar os membros do suporte.')
    }).finally(() => window.clearTimeout(timer))
    return () => { active = false; window.clearTimeout(timer); controller.abort() }
  }, [canEdit, memberRetry, onSessionExpired])

  async function mutate(action: () => Promise<void>) {
    if (mutating.current || loading) return
    mutating.current = true; setBusy(true); setError(''); setNotice('')
    try { await action() } catch (failure) {
      if (!mounted.current) return
      if (failure instanceof ApiError && failure.status === 401) { onSessionExpired(); return }
      setError(failure instanceof Error ? failure.message : 'Não foi possível salvar a alteração.')
      if (failure instanceof ApiError && (failure.status === 409 || failure.status === 0)) {
        // Keep the modal and draft open, refresh only authoritative ticket/activity data.
        try {
          const latest = await getTicketDetails(ticketId)
          if (mounted.current) { setTicket(latest); setActivityVersion(value => value + 1); onChanged() }
        } catch (reloadFailure) {
          if (reloadFailure instanceof ApiError && reloadFailure.status === 401) onSessionExpired()
          else if (mounted.current) setNotice('Use Recarregar detalhes para conferir o estado atual antes de tentar novamente.')
        }
      }
    } finally { mutating.current = false; if (mounted.current) setBusy(false) }
  }

  async function move(current: TicketSummary, status: TicketStatus) {
    await mutate(async () => {
      const updated = await updateTicketStatus(current, status)
      onChanged()
      if (!mounted.current) return
      setTicket(previous => previous ? { ...previous, ...updated } : previous)
      setActivityVersion(value => value + 1); setNotice('Status atualizado.')
    })
  }

  function assign(id: number | null) {
    if (!ticket) return
    void mutate(async () => {
      const updated = await assignTicket(ticket, id)
      onChanged()
      if (!mounted.current) return
      setTicket(updated); setActivityVersion(value => value + 1)
      setNotice('Responsável atualizado.')
    })
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!body.trim()) return
    void mutate(async () => {
      await postComment(ticketId, body.trim())
      if (!mounted.current) return
      setBody(''); setActivityVersion(value => value + 1); setNotice('Comentário enviado.')
    })
  }

  function tabKeys(event: KeyboardEvent<HTMLButtonElement>) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const next = event.key === 'Home' ? 'comments' : event.key === 'End' ? 'history' : tab === 'comments' ? 'history' : 'comments'
    setTab(next)
    dialog.current?.querySelector<HTMLButtonElement>(`#tab-${next}`)?.focus()
  }

  return <dialog ref={dialog} className="ticket-dialog" aria-labelledby="ticket-detail-title"
    onCancel={event => { event.preventDefault(); onClose() }}>
    <div className="detail-header"><div><p className="eyebrow">TICKET #{ticketId}</p>
      <h2 id="ticket-detail-title">{ticket?.title ?? 'Detalhes do ticket'}</h2></div>
      <button type="button" className="secondary" autoFocus aria-label="Fechar detalhes" onClick={onClose}>Fechar ×</button></div>
    <div className="detail-scroll">
      {loading && <p role="status">Carregando detalhes…</p>}
      {error && <div><p role="alert" className="error">{error}</p>
        <button className="secondary" disabled={busy} onClick={() => setRetry(value => value + 1)}>Recarregar detalhes</button></div>}
      {notice && <p role="status" className="success">{notice}</p>}
      {ticket && <>
        <div className="detail-fields">
          <div><span className="detail-label">Solicitante</span><strong>{ticket.requester.name}</strong></div>
          <div><span className="detail-label">Criado em</span><time dateTime={ticket.created_at}>{formatDate(ticket.created_at)}</time></div>
          <div><span className="detail-label">Categoria</span>{categoryLabels[ticket.category]}</div>
          <div><span className="detail-label">Prioridade</span><span className={`badge priority-${ticket.priority}`}>{priorityLabels[ticket.priority]}</span></div>
          <div><span className="detail-label">Status</span><TicketStatusControl ticket={ticket} canEdit={canEdit}
            movingId={busy || loading ? ticketId : null} onMove={move} /></div>
          <div><span className="detail-label">Responsável</span>
            {canEdit ? <TicketAssigneeMenu assignee={ticket.assignee} members={members} userId={user.id}
              disabled={busy || loading} membersLoaded={membersLoaded} error={memberError}
              onRetry={() => setMemberRetry(value => value + 1)} onAssign={assign} />
              : <strong>{ticket.assignee?.name ?? 'Não atribuído'}</strong>}
          </div>
        </div>
        <h3 className="description-heading">Descrição</h3><p className="plain-text detail-description">{ticket.description}</p>
        <div className="detail-tabs" role="tablist" aria-label="Atividade do ticket">
          {(['comments', 'history'] as const).map(value => <button key={value} id={`tab-${value}`} role="tab"
            aria-selected={tab === value} aria-controls={`panel-${value}`} tabIndex={tab === value ? 0 : -1}
            onKeyDown={tabKeys} onClick={() => setTab(value)}>{value === 'comments' ? 'Comentários' : 'Histórico'}</button>)}
        </div>
        <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} tabIndex={0}>
          {tab === 'comments' && <form className="comment-form" onSubmit={submit}>
            <label htmlFor="comment-body">Adicionar comentário</label>
            <textarea id="comment-body" rows={3} minLength={1} maxLength={5000} required value={body}
              disabled={busy || loading} onChange={event => setBody(event.target.value)} placeholder="Escreva uma mensagem sobre este ticket…" />
            <button disabled={busy || loading || !body.trim()}>{busy ? 'Enviando…' : 'Enviar comentário'}</button>
          </form>}
          <TicketActivity key={`${tab}:${activityVersion}`} ticketId={ticketId} tab={tab} onSessionExpired={onSessionExpired} />
        </div>
      </>}
    </div>
  </dialog>
}
