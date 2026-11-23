"""O "hoje" do sistema é o da escola, não o do servidor (que costuma rodar em UTC)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import settings


def hoje() -> date:
    return datetime.now(ZoneInfo(settings.fuso_horario)).date()
