"""Shared application errors; HTTP translation lives in the API handlers."""


class AppError(Exception):
    code = "unexpected_error"
    default_message = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.default_message)


class NotFoundError(AppError):
    code = "not_found"
    default_message = "Resource not found."


class ConflictError(AppError):
    code = "conflict"
    default_message = "The resource has changed. Refresh and try again."


class InvalidInputError(AppError):
    code = "invalid_input"
    default_message = "Invalid request data."


class AuthenticationError(AppError):
    code = "authentication_required"
    default_message = "Please log in to continue."


class AccessDeniedError(AppError):
    code = "access_denied"
    default_message = "Access restricted to support staff."


class CsrfError(AccessDeniedError):
    code = "csrf_rejected"
    default_message = "Request not authorized."


class DatabaseUnavailableError(AppError):
    code = "database_unavailable"
    default_message = "Database unavailable"


class DuplicateEmailError(ConflictError):
    code = "duplicate_email"
    default_message = "This email is already registered."


class InvalidCredentialsError(AuthenticationError):
    code = "invalid_credentials"
    default_message = "Invalid email or password."


class TicketNotFoundError(NotFoundError):
    code = "ticket_not_found"
    default_message = "Ticket not found."


class StatusConflictError(ConflictError):
    code = "status_conflict"
    default_message = "Ticket status has changed. Refresh and try again."


class AssignmentConflictError(ConflictError):
    code = "assignment_conflict"
    default_message = "Ticket assignment has changed. Refresh and try again."


class InvalidAssigneeError(InvalidInputError):
    code = "invalid_assignee"
    default_message = "Assignee must be an active support member."
