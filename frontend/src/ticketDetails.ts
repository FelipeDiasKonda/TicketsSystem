import { apiRequest } from './api'
import type { Ticket, TicketStatus } from './tickets'

export type Person = { id: number; name: string }
export type TicketDetails = Ticket & { assignee: Person | null; assignment_version: number }
export type Comment = { id: number; body: string; author: Person; created_at: string }
export type HistoryItem = {
  id: string; event: 'created' | 'transition' | 'snapshot' | 'assignment'
  actor: Person | null; changed_at: string
  previous_status: TicketStatus | null; new_status: TicketStatus | null
  previous_assignee: Person | null; new_assignee: Person | null
}
export type ActivityPage<T> = { items: T[]; total: number; page: number; page_size: number }
export const getTicketDetails = (id: number, signal?: AbortSignal) =>
  apiRequest<TicketDetails>(`/tickets/${id}`, { signal })
export const getSupportMembers = (signal?: AbortSignal) =>
  apiRequest<Person[]>('/tickets/support-members', { signal })
export const assignTicket = (ticket: TicketDetails, assignee_id: number | null) =>
  apiRequest<TicketDetails>(`/tickets/${ticket.id}/assignee`, { method: 'PATCH',
    body: JSON.stringify({ assignee_id, expected_assignment_version: ticket.assignment_version }) })
export const postComment = (id: number, body: string) =>
  apiRequest<Comment>(`/tickets/${id}/comments`, { method: 'POST', body: JSON.stringify({ body }) })
export const getComments = (id: number, page: number, signal: AbortSignal) =>
  apiRequest<ActivityPage<Comment>>(`/tickets/${id}/comments?page=${page}&page_size=20`, { signal })
export const getHistory = (id: number, page: number, signal: AbortSignal) =>
  apiRequest<ActivityPage<HistoryItem>>(`/tickets/${id}/history?page=${page}&page_size=20`, { signal })
