from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.enums import UserRole
from app.models.user import User
from app.schemas.dashboard import AdminStats, AgentStats, TicketStats
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


@router.get("/stats", response_model=TicketStats)
def ticket_stats(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
):
    return service.get_ticket_stats(current_user)


@router.get(
    "/admin",
    response_model=AdminStats,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def admin_stats(service: DashboardService = Depends(get_dashboard_service)):
    return service.get_admin_stats()


@router.get("/agent", response_model=AgentStats)
def agent_stats(
    current_user: User = Depends(require_roles(UserRole.AGENT)),
    service: DashboardService = Depends(get_dashboard_service),
):
    return service.get_agent_stats(current_user)