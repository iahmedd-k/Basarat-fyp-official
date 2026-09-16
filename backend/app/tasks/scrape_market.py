from app.celery_app import celery


@celery.task(name="app.tasks.scrape_market.run")
def run():
    pass