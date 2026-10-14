from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.enums import UserRole
from app.models.user import User
from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import AdminStats, AgentStats, TicketStats

CACHE_TTL_SECONDS = 60


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.repo = DashboardRepository(db)

    def get_ticket_stats(self, current_user: User) -> TicketStats:
        """Scope is decided server-side from the caller's role, never from the request."""
        if current_user.role == UserRole.ADMIN:
            cache_key, scope = "dashboard:stats:admin", {}
        elif current_user.role == UserRole.AGENT:
            cache_key = f"dashboard:stats:agent:{current_user.id}"
            scope = {"agent_id": current_user.id}
        else:
            cache_key = f"dashboard:stats:customer:{current_user.id}"
            scope = {"customer_id": current_user.id}

        cached = cache_get(cache_key)
        if cached is not None:
            return TicketStats(**cached)

        stats = self.repo.ticket_stats(**scope)
        cache_set(cache_key, stats, CACHE_TTL_SECONDS)
        return TicketStats(**stats)

    def get_admin_stats(self) -> AdminStats:
        cache_key = "dashboard:admin-extra"
        cached = cache_get(cache_key)
        if cached is not None:
            return AdminStats(**cached)

        data = {
            "total_customers": self.repo.count_users_by_role(UserRole.CUSTOMER),
            "total_agents": self.repo.count_users_by_role(UserRole.AGENT),
            "active_agents": self.repo.count_users_by_role(UserRole.AGENT, active_only=True),
            "tickets_per_agent": self.repo.tickets_per_agent(),
        }
        cache_set(cache_key, data, CACHE_TTL_SECONDS)
        return AdminStats(**data)

    def get_agent_stats(self, current_user: User) -> AgentStats:
        stats = self.get_ticket_stats(current_user)  # already scoped to this agent + cached
        return AgentStats(
            my_open_tickets=stats.open_tickets,
            my_overdue_tickets=stats.overdue_tickets,
            my_resolved_tickets=stats.resolved_tickets,
        )