from app.celery_app import celery


@celery.task(name="app.tasks.compute_sentiment.run")
def run():
    pass