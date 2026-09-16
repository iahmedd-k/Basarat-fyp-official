from app.celery_app import celery


@celery.task(name="app.tasks.evaluate_alert_rules.run")
def run():
    pass