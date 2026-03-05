import time

from app.core.config import settings


def process_once(timeout_seconds: int = 1) -> bool:
    import redis

    from app.services.eval_service import eval_service

    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    item = client.blpop(settings.redis_queue_name, timeout=timeout_seconds)
    if item is None:
        return False
    _, job_id = item
    eval_service.process_run_job(job_id)
    return True


def run_forever(poll_interval_seconds: int = 1) -> None:
    while True:
        processed = process_once(timeout_seconds=poll_interval_seconds)
        if not processed:
            time.sleep(poll_interval_seconds)


if __name__ == "__main__":
    run_forever()
