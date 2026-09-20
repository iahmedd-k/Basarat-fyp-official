from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertRule
from sqlalchemy import select


class AlertService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_alerts(self, user_id: str, unread_only: bool = False) -> list[Alert]:
        query = select(Alert).where(Alert.user_id == user_id)
        if unread_only:
            query = query.where(Alert.is_read == False)
        query = query.order_by(Alert.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def mark_as_read(self, alert_id: str, user_id: str) -> None:
        result = await self.db.execute(
            select(Alert).where(Alert.id == alert_id, Alert.user_id == user_id)
        )
        alert = result.scalars().first()
        if alert:
            alert.is_read = True
            await self.db.flush()
