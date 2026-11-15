import { apiRequest } from './api'

export type TicketCategory = 'it' | 'facilities' | 'hr'
export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent'
export type TicketStatus = 'open' | 'in_progress' | 'resolved' | 'closed'
export type TicketSort = 'created_desc' | 'created_asc' | 'priority_desc' | 'priority_asc'
export type TicketFilters = {
  status: TicketStatus | ''
  category: TicketCategory | ''
  priority: TicketPriority | ''
  sort: TicketSort
}
export const defaultTicketFilters: TicketFilters = {
  status: '', category: '', priority: '', sort: 'created_desc',
}
export const sortLabels: Record<TicketSort, string> = {
  created_desc: 'Mais recentes', created_asc: 'Mais antigos',
  priority_desc: 'Maior prioridade', priority_asc: 'Menor prioridade',
}
export type TicketDraft = {
  title: string
  description: string
  category: TicketCategory
  priority: TicketPriority
}
export type TicketSummary = {
  id: number
  title: string
  category: TicketCategory
  priority: TicketPriority
  status: TicketStatus
  requester: { id: number; name: string }
  created_at: string
}
export type Ticket = TicketSummary & { description: string }
export type MoveTicket = (ticket: TicketSummary, status: TicketStatus) => Promise<void>
export const ticketStatuses: TicketStatus[] = ['open', 'in_progress', 'resolved', 'closed']
export const nextTicketStatus: Partial<Record<TicketStatus, TicketStatus>> = {
  open: 'in_progress', in_progress: 'resolved', resolved: 'closed',
}
export const updateTicketStatus = (ticket: TicketSummary, status: TicketStatus) =>
  apiRequest<Ticket>(`/tickets/${ticket.id}/status`, {
    method: 'PATCH', body: JSON.stringify({ expected_status: ticket.status, status }),
  })
export type TicketPage = { items: TicketSummary[]; total: number; page: number; page_size: number }

export const categoryLabels: Record<TicketCategory, string> = { it: 'TI', facilities: 'Instalações', hr: 'RH' }
export const priorityLabels: Record<TicketPriority, string> = { low: 'Baixa', medium: 'Média', high: 'Alta', urgent: 'Urgente' }
export const statusLabels: Record<TicketStatus, string> = { open: 'Aberto', in_progress: 'Em andamento', resolved: 'Resolvido', closed: 'Fechado' }

export const createTicket = (data: TicketDraft) =>
  apiRequest<Ticket>('/tickets', { method: 'POST', body: JSON.stringify(data) })
export function getTickets(page: number, filters: TicketFilters, signal: AbortSignal) {
  const query = new URLSearchParams({ page: String(page), page_size: '20', sort: filters.sort })
  if (filters.status) query.set('status', filters.status)
  if (filters.category) query.set('category', filters.category)
  if (filters.priority) query.set('priority', filters.priority)
  return apiRequest<TicketPage>(`/tickets?${query}`, { signal })
}
