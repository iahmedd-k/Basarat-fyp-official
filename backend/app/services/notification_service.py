class NotificationService:
    def __init__(self):
        pass

    async def send_push_notification(self, fcm_token: str, title: str, body: str) -> bool:
        return True

    async def send_bulk_notification(self, tokens: list[str], title: str, body: str) -> int:
        return len(tokens)
