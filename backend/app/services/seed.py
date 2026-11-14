from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AuthSession,
    Ticket,
    TicketCategory,
    TicketPriority,
    TicketStatus,
    User,
    UserRole,
)


@dataclass(frozen=True)
class SeedResult:
    users_created: int
    users_updated: int
    tickets_created: int


class SeedPasswordError(ValueError):
    pass


DEMO_TICKETS = (
    (
        TicketCategory.IT,
        TicketPriority.HIGH,
        "[DEMO] Não consigo acessar o e-mail",
        "O acesso ao e-mail corporativo não está funcionando e preciso de ajuda da equipe de TI.",
    ),
    (
        TicketCategory.FACILITIES,
        TicketPriority.MEDIUM,
        "[DEMO] Ar-condicionado da sala não funciona",
        "O ar-condicionado da sala de reuniões não está ligando. "
        "Solicito a verificação do equipamento.",
    ),
    (
        TicketCategory.HR,
        TicketPriority.LOW,
        "[DEMO] Dúvida sobre solicitação de férias",
        "Gostaria de orientações sobre o procedimento e os prazos para solicitar férias.",
    ),
)


def seed_demo_data(db: Session, password: str | None) -> SeedResult:
    if password is None or not 12 <= len(password) <= 128 or not password.strip():
        raise SeedPasswordError("Set SEED_PASSWORD to a password of 12 to 128 characters.")

    created = updated = tickets_created = 0
    with db.begin():
        for role, prefix, label in (
            (UserRole.EMPLOYEE, "funcionario", "Funcionário"),
            (UserRole.SUPPORT, "suporte", "Suporte"),
        ):
            for index in range(1, 4):
                email = f"{prefix}{index}@gmail.com"
                user = db.scalar(select(User).where(User.email == email).with_for_update())
                if user is None:
                    user = User(email=email)
                    db.add(user)
                    created += 1
                else:
                    updated += 1
                user.name = f"{label} {index}"
                user.role = role
                user.is_active = True
                user.password_hash = hash_password(password)
                db.flush()
                # Resetting demo credentials invalidates previous demo logins only.
                db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))

                if role == UserRole.EMPLOYEE:
                    category, priority, title, description = DEMO_TICKETS[index - 1]
                    existing = db.scalar(
                        select(Ticket.id).where(
                            Ticket.requester_id == user.id,
                            Ticket.title == title,
                        )
                    )
                    if existing is None:
                        db.add(
                            Ticket(
                                title=title,
                                description=description,
                                category=category,
                                priority=priority,
                                status=TicketStatus.OPEN,
                                requester_id=user.id,
                            )
                        )
                        tickets_created += 1
    return SeedResult(created, updated, tickets_created)
