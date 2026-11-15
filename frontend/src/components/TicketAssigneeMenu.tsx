import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { Person } from '../ticketDetails'

type Props = {
  assignee: Person | null; members: Person[]; userId: number; disabled: boolean
  membersLoaded: boolean; error: string; onRetry: () => void
  onAssign: (id: number | null) => void
}

export default function TicketAssigneeMenu({ assignee, members, userId, disabled,
  membersLoaded, error, onRetry, onAssign }: Props) {
  const [open, setOpen] = useState(false)
  const container = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const menu = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    menu.current?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus()
    function outside(event: PointerEvent) {
      if (!container.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open])

  function close() {
    setOpen(false)
    trigger.current?.focus()
  }

  function choose(id: number | null) {
    close()
    onAssign(id)
  }

  function keys(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.preventDefault(); event.stopPropagation(); close(); return
    }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const options = Array.from(menu.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? [])
    if (!options.length) return
    const current = options.indexOf(document.activeElement as HTMLButtonElement)
    const index = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1
      : (current + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length
    options[index].focus()
  }

  return <div className="assignee-picker" ref={container} onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false)
  }}>
    <button ref={trigger} type="button" className="assignee-trigger" disabled={disabled}
      aria-label={`Alterar responsável: ${assignee?.name ?? 'Não atribuído'}`}
      aria-haspopup="menu" aria-expanded={open} aria-controls={open ? 'assignee-menu' : undefined}
      onClick={() => setOpen(value => !value)} onKeyDown={event => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setOpen(true) }
      }}>
      <span>{assignee?.name ?? 'Não atribuído'}</span><span aria-hidden="true" className="assignee-chevron">▾</span>
    </button>
    {open && <div ref={menu} id="assignee-menu" className="assignee-menu" role="menu"
      aria-label="Atribuir ao suporte" onKeyDown={keys}>
      <button type="button" role="menuitem" tabIndex={-1} disabled={disabled || assignee?.id === userId}
        onClick={() => choose(userId)}>Atribuir a mim</button>
      <button type="button" role="menuitem" tabIndex={-1} disabled={disabled || !assignee}
        onClick={() => choose(null)}>Remover atribuição</button>
      <div className="assignee-menu-label" role="presentation">Equipe de suporte</div>
      {!membersLoaded && !error && <p role="status" className="assignee-menu-message">Carregando suporte…</p>}
      {error && <><p role="alert" className="assignee-menu-message">{error}</p>
        <button type="button" role="menuitem" tabIndex={-1} onClick={onRetry}>Recarregar suporte</button></>}
      {membersLoaded && !members.length && <p className="assignee-menu-message">Nenhum membro disponível.</p>}
      {membersLoaded && members.map(member => <button key={member.id} type="button" role="menuitemradio"
        tabIndex={-1} aria-checked={assignee?.id === member.id} disabled={disabled || assignee?.id === member.id}
        onClick={() => choose(member.id)}><span>{member.name}</span>
        {assignee?.id === member.id && <span aria-hidden="true">✓</span>}</button>)}
    </div>}
  </div>
}
