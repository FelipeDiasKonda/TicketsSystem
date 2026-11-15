import { nextTicketStatus, statusLabels } from '../tickets'
import type { MoveTicket, TicketStatus, TicketSummary } from '../tickets'

type Props = { ticket: TicketSummary; canEdit: boolean; movingId: number | null; onMove: MoveTicket }

export default function TicketStatusControl({ ticket, canEdit, movingId, onMove }: Props) {
  const next = nextTicketStatus[ticket.status]
  if (!canEdit || !next) {
    return <span className={`badge status-${ticket.status}`}>{statusLabels[ticket.status]}</span>
  }
  return <select className={`status-select status-${ticket.status}`} value={ticket.status}
    disabled={movingId !== null} aria-label={`Alterar status do ticket #${ticket.id}`}
    onChange={event => void onMove(ticket, event.target.value as TicketStatus)}>
    <option value={ticket.status} disabled>{movingId === ticket.id ? 'Atualizando…' : statusLabels[ticket.status]}</option>
    <option value={next}>{statusLabels[next]}</option>
  </select>
}
