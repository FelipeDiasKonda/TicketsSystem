# Single main render return

Approved scope: keep loading, error, empty and populated states inside each
component's main JSX return. Review all TSX components; preserve request logic,
retry actions, permissions, pagination and accessibility.

- `TicketActivity`: render loading/error messages and guarded activity content
  within one return. Hide previous activity and pagination during loading/errors.
- `TicketList`: keep table/caption/header mounted and render loading/error/empty
  states as table-body rows spanning all seven columns. Show data rows, count
  and pagination only on a successful nonempty result.
- `TicketStatusControl`: choose the badge or editable select within one return,
  preserving the next-status-only rule and disabled state during updates.
- Other components already follow the requested structure. Returns inside effects,
  event handlers, callbacks and text helpers are unaffected.

Validation: TypeScript/Vite build passed. Fourteen controlled-state React server
render checks passed for loading, errors, retries being available, empty results,
populated results, stale content suppression and status-control permissions.
The TypeScript AST review confirmed one top-level return for every component,
including the board column. These checks do not constitute browser interaction
tests. Local Node 18 emitted Vite's version warning; Node >=22.12 is the project's
declared requirement and Docker uses Node 22.
