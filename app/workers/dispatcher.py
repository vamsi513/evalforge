from typing import Optional

from fastapi import BackgroundTasks

from app.core.config import settings


class EvalJobDispatcher:
    def dispatch(self, job_id: str, background_tasks: Optional[BackgroundTasks] = None) -> None:
        backend = settings.async_backend.lower()
        if backend == "redis":
            self._dispatch_redis(job_id)
            return
        self._dispatch_local(job_id, background_tasks=background_tasks)

    @staticmethod
    def _dispatch_local(job_id: str, background_tasks: Optional[BackgroundTasks] = None) -> None:
        from app.services.eval_service import eval_service

        if background_tasks is not None:
            background_tasks.add_task(eval_service.process_run_job, job_id)
            return
        eval_service.process_run_job(job_id)

    @staticmethod
    def _dispatch_redis(job_id: str) -> None:
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.rpush(settings.redis_queue_name, job_id)


eval_job_dispatcher = EvalJobDispatcher()
