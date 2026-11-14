import { apiRequest } from './api'

export type TicketCategory = 'it' | 'facilities' | 'hr'
export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent'
export type TicketStatus = 'open' | 'in_progress' | 'resolved' | 'closed'
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
export type TicketPage = { items: TicketSummary[]; total: number; page: number; page_size: number }

export const categoryLabels: Record<TicketCategory, string> = { it: 'TI', facilities: 'Instalações', hr: 'RH' }
export const priorityLabels: Record<TicketPriority, string> = { low: 'Baixa', medium: 'Média', high: 'Alta', urgent: 'Urgente' }
export const statusLabels: Record<TicketStatus, string> = { open: 'Aberto', in_progress: 'Em andamento', resolved: 'Resolvido', closed: 'Fechado' }

export const createTicket = (data: TicketDraft) =>
  apiRequest<Ticket>('/tickets', { method: 'POST', body: JSON.stringify(data) })
export const getTickets = (page: number, signal: AbortSignal) =>
  apiRequest<TicketPage>(`/tickets?page=${page}&page_size=20`, { signal })
