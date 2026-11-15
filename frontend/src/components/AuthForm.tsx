import { useState } from 'react'
import type { FormEvent } from 'react'
import { login, register } from '../auth'
import type { Role, User } from '../auth'

type Props = { onAuthenticated: (user: User) => void }

export default function AuthForm({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [role, setRole] = useState<Role>('employee')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const isRegister = mode === 'register'

  function changeMode() {
    setMode(isRegister ? 'login' : 'register')
    setError('')
    setPassword('')
    setConfirmation('')
    setRole('employee')
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    setError('')
    if (isRegister && password !== confirmation) {
      setError('As senhas devem ser iguais.')
      return
    }
    if (isRegister && name.trim().length < 2) {
      setError('Informe seu nome com pelo menos 2 caracteres.')
      return
    }
    setBusy(true)
    try {
      const user = isRegister
        ? await register({ name: name.trim(), email: email.trim(), password,
            password_confirmation: confirmation, role })
        : await login(email.trim(), password)
      onAuthenticated(user)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Não foi possível continuar.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="auth-layout">
      <div className="auth-intro">
        <p className="eyebrow">SUPORTE INTERNO</p>
        <h1>Um lugar para cada solicitação.</h1>
        <p className="intro">Acesse sua conta para entrar no portal de suporte da equipe.</p>
      </div>
      <div className="auth-card">
        <h2>{isRegister ? 'Crie sua conta' : 'Bem-vindo de volta'}</h2>
        <p className="muted">{isRegister ? 'Preencha seus dados para começar.' : 'Entre com seu e-mail e senha.'}</p>
        <form onSubmit={submit}>
          <fieldset disabled={busy} className="form-fields">
            <legend className="sr-only">{isRegister ? 'Dados de cadastro' : 'Dados de acesso'}</legend>
            {isRegister && <label htmlFor="name">Nome
              <input id="name" autoComplete="name" required minLength={2} maxLength={100}
                value={name} onChange={event => setName(event.target.value)} />
            </label>}
            <label htmlFor="email">E-mail
              <input id="email" type="email" autoComplete="email" required maxLength={254}
                value={email} onChange={event => setEmail(event.target.value)} />
            </label>
            {isRegister && <label htmlFor="role">Perfil
              <select id="role" value={role} onChange={event => setRole(event.target.value as Role)}>
                <option value="employee">Funcionário</option>
                <option value="support">Suporte</option>
              </select>
              <small>{role === 'support'
                ? 'Visualiza todos os tickets e gerencia seus status.'
                : 'Envia solicitações e acompanha os próprios tickets.'}</small>
            </label>}
            <label htmlFor="password">Senha
              <input id="password" type="password" autoComplete={isRegister ? 'new-password' : 'current-password'}
                required minLength={isRegister ? 12 : 1} maxLength={128}
                value={password} onChange={event => setPassword(event.target.value)} />
              {isRegister && <small>Use de 12 a 128 caracteres.</small>}
            </label>
            {isRegister && <label htmlFor="confirmation">Confirme a senha
              <input id="confirmation" type="password" autoComplete="new-password" required
                minLength={12} maxLength={128} value={confirmation}
                onChange={event => setConfirmation(event.target.value)} />
            </label>}
          </fieldset>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="primary" type="submit" disabled={busy}>
            {busy ? 'Aguarde…' : isRegister ? 'Criar conta' : 'Entrar'}
          </button>
        </form>
        <p className="switch-mode">{isRegister ? 'Já tem uma conta?' : 'Ainda não tem conta?'}{' '}
          <button type="button" className="text-button" disabled={busy} onClick={changeMode}>
            {isRegister ? 'Entrar' : 'Cadastre-se'}
          </button>
        </p>
      </div>
    </section>
  )
}
