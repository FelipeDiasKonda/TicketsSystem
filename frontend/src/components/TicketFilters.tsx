import { categoryLabels, defaultTicketFilters, priorityLabels, sortLabels, statusLabels } from '../tickets'
import type { TicketFilters as Filters } from '../tickets'

type Props = { value: Filters; onChange: (value: Filters) => void }

export default function TicketFilters({ value, onChange }: Props) {
  const isDefault = !value.status && !value.category && !value.priority && value.sort === 'created_desc'

  return <fieldset className="ticket-filters">
    <legend>Filtrar e ordenar tickets</legend>
    <div className="filter-controls">
      <label htmlFor="filter-status">Status
        <select id="filter-status" value={value.status}
          onChange={event => onChange({ ...value, status: event.target.value as Filters['status'] })}>
          <option value="">Todos os status</option>
          {Object.entries(statusLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </label>
      <label htmlFor="filter-category">Categoria
        <select id="filter-category" value={value.category}
          onChange={event => onChange({ ...value, category: event.target.value as Filters['category'] })}>
          <option value="">Todas as categorias</option>
          {Object.entries(categoryLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </label>
      <label htmlFor="filter-priority">Prioridade
        <select id="filter-priority" value={value.priority}
          onChange={event => onChange({ ...value, priority: event.target.value as Filters['priority'] })}>
          <option value="">Todas as prioridades</option>
          {Object.entries(priorityLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </label>
      <label htmlFor="ticket-sort">Ordenação
        <select id="ticket-sort" value={value.sort}
          onChange={event => onChange({ ...value, sort: event.target.value as Filters['sort'] })}>
          {Object.entries(sortLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </label>
      <button type="button" className="secondary clear-filters" disabled={isDefault}
        onClick={() => onChange(defaultTicketFilters)}>Limpar filtros</button>
    </div>
  </fieldset>
}
