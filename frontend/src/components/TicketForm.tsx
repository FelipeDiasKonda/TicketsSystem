import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError } from '../api'
import { categoryLabels, createTicket, priorityLabels } from '../tickets'
import type { Ticket, TicketCategory, TicketPriority } from '../tickets'

type Props = { onCreated: (ticket: Ticket) => void; onCancel: () => void; onSessionExpired: () => void }

export default function TicketForm({ onCreated, onCancel, onSessionExpired }: Props) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState<TicketCategory | ''>('')
  const [priority, setPriority] = useState<TicketPriority>('medium')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    setError('')
    const trimmedTitle = title.trim()
    const trimmedDescription = description.trim()
    if (trimmedTitle.length < 3 || trimmedTitle.length > 150) {
      setError('O título deve ter de 3 a 150 caracteres.')
      return
    }
    if (trimmedDescription.length < 10 || trimmedDescription.length > 5000) {
      setError('A descrição deve ter de 10 a 5.000 caracteres.')
      return
    }
    if (!category) { setError('Selecione uma categoria.'); return }
    setBusy(true)
    try {
      const ticket = await createTicket({ title: trimmedTitle, description: trimmedDescription, category, priority })
      onCreated(ticket)
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) { onSessionExpired(); return }
      setError(failure instanceof Error ? failure.message : 'Não foi possível criar o ticket.')
    } finally { setBusy(false) }
  }

  return <div className="ticket-form-card">
    <h3>Novo ticket</h3>
    <p className="muted">Descreva sua solicitação para a equipe de suporte.</p>
    <form onSubmit={submit}>
      <fieldset className="form-fields" disabled={busy}>
        <legend className="sr-only">Dados do novo ticket</legend>
        <label htmlFor="ticket-title">Título
          <input id="ticket-title" value={title} onChange={event => setTitle(event.target.value)}
            autoFocus required minLength={3} maxLength={150} placeholder="Ex.: Não consigo acessar o e-mail" />
        </label>
        <label htmlFor="ticket-description">Descrição
          <textarea id="ticket-description" value={description} onChange={event => setDescription(event.target.value)}
            required minLength={10} maxLength={5000} rows={5} aria-describedby="description-help"
            placeholder="Conte o que aconteceu e como isso afeta seu trabalho." />
          <small id="description-help">De 10 a 5.000 caracteres · {description.length}/5.000</small>
        </label>
        <div className="form-row">
          <label htmlFor="ticket-category">Categoria
            <select id="ticket-category" required value={category}
              onChange={event => setCategory(event.target.value as TicketCategory | '')}>
              <option value="" disabled>Selecione uma categoria</option>
              {Object.entries(categoryLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label htmlFor="ticket-priority">Prioridade
            <select id="ticket-priority" value={priority}
              onChange={event => setPriority(event.target.value as TicketPriority)}>
              {Object.entries(priorityLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        </div>
      </fieldset>
      {error && <p role="alert" className="error">{error}</p>}
      <div className="form-actions">
        <button type="submit" disabled={busy}>{busy ? 'Enviando…' : 'Criar ticket'}</button>
        <button type="button" className="secondary" onClick={onCancel} disabled={busy}>Cancelar</button>
      </div>
    </form>
  </div>
}
