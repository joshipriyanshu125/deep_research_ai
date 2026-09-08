import asyncio
from app.utils.logger import logger


class TaskWorker:
    async def process_batch_tasks(self, tasks: list):
        logger.info(f"Processing batch of {len(tasks)} tasks.")
        await asyncio.sleep(0.1)


task_worker = TaskWorker()
