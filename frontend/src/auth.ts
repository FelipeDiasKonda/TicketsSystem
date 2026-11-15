import { apiRequest } from './api'

export type Role = 'employee' | 'support'
export type User = { id: number; name: string; email: string; role: Role; is_active: boolean }
export type Registration = {
  name: string
  email: string
  password: string
  password_confirmation: string
  role: Role
}

export const roleLabels: Record<Role, string> = { employee: 'Funcionário', support: 'Suporte' }
export const getCurrentUser = () => apiRequest<User>('/auth/me')
export const login = (email: string, password: string) =>
  apiRequest<User>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
export const register = (data: Registration) =>
  apiRequest<User>('/auth/register', { method: 'POST', body: JSON.stringify(data) })
export const logout = () => apiRequest<void>('/auth/logout', { method: 'POST' })
