from app.celery_app import celery


@celery.task(name="app.tasks.scrape_news.run")
def run():
    pass