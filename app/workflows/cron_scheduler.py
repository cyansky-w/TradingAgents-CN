"""
工作流 Cron 调度器 — 将启用 cron 触发的工作流注册到 APScheduler。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.workflow_service import workflow_service
from app.utils.timezone import get_tz

logger = logging.getLogger(__name__)

SCHEDULER_JOB_ID_PREFIX = "workflow_cron_"


async def run_workflow_cron_job(workflow_id: str, input_data: Dict[str, Any]) -> None:
    """APScheduler 回调：执行一次工作流。"""
    try:
        from app.workflows.engine import workflow_engine
        result = await workflow_engine.run(
            workflow_id=workflow_id,
            input_data=input_data,
            trigger_type="cron",
        )
        logger.info(f"Workflow cron job completed: {workflow_id}, run_id={result.get('run_id')}")
    except Exception as e:
        logger.error(f"Workflow cron job failed: {workflow_id}, error={e}")


class WorkflowCronScheduler:
    """管理工作流的 cron 定时调度。"""

    def __init__(self, scheduler: AsyncIOScheduler):
        self.scheduler = scheduler

    async def sync_all(self) -> int:
        """扫描所有启用的 cron 工作流并注册到调度器。返回注册数量。"""
        # 移除已有的 workflow cron jobs
        for job in self.scheduler.get_jobs():
            if job.id.startswith(SCHEDULER_JOB_ID_PREFIX):
                self.scheduler.remove_job(job.id)

        # 查询所有启用的工作流
        workflows, _ = await workflow_service.list_workflows(enabled=True, page=1, page_size=1000)

        count = 0
        for wf in workflows:
            trigger = wf.get("trigger", {})
            if trigger.get("type") != "cron" or not trigger.get("cron"):
                continue

            job_id = f"{SCHEDULER_JOB_ID_PREFIX}{wf['id']}"
            cron_expr = trigger["cron"]
            input_data: Dict[str, Any] = {}

            try:
                self.scheduler.add_job(
                    run_workflow_cron_job,
                    CronTrigger.from_crontab(cron_expr, timezone=get_tz()),
                    id=job_id,
                    name=f"工作流: {wf.get('name', wf['id'])}",
                    kwargs={"workflow_id": wf["id"], "input_data": input_data},
                    misfire_grace_time=300,
                )
                count += 1
                logger.info(f"Registered workflow cron: {wf.get('name')} ({cron_expr})")
            except Exception as e:
                logger.error(f"Failed to register cron for workflow {wf['id']}: {e}")

        logger.info(f"Workflow cron sync complete: {count} jobs registered")
        return count

    async def register_workflow(self, workflow_id: str) -> bool:
        """注册单个工作流的 cron 任务。"""
        wf = await workflow_service.get_workflow(workflow_id)
        if not wf or not wf.get("enabled", True):
            return False

        trigger = wf.get("trigger", {})
        if trigger.get("type") != "cron" or not trigger.get("cron"):
            await self.unregister_workflow(workflow_id)
            return False

        job_id = f"{SCHEDULER_JOB_ID_PREFIX}{workflow_id}"
        # 移除旧任务
        existing = self.scheduler.get_job(job_id)
        if existing:
            self.scheduler.remove_job(job_id)

        cron_expr = trigger["cron"]
        input_data: Dict[str, Any] = {}

        self.scheduler.add_job(
            run_workflow_cron_job,
            CronTrigger.from_crontab(cron_expr, timezone=get_tz()),
            id=job_id,
            name=f"工作流: {wf.get('name', workflow_id)}",
            kwargs={"workflow_id": workflow_id, "input_data": input_data},
            misfire_grace_time=300,
        )
        logger.info(f"Registered workflow cron: {wf.get('name')} ({cron_expr})")
        return True

    async def unregister_workflow(self, workflow_id: str) -> bool:
        """移除工作流的 cron 任务。"""
        job_id = f"{SCHEDULER_JOB_ID_PREFIX}{workflow_id}"
        existing = self.scheduler.get_job(job_id)
        if existing:
            self.scheduler.remove_job(job_id)
            logger.info(f"Unregistered workflow cron: {workflow_id}")
            return True
        return False

    def get_registered_jobs(self) -> list:
        """获取所有已注册的工作流 cron 任务。"""
        jobs = []
        for job in self.scheduler.get_jobs():
            if job.id.startswith(SCHEDULER_JOB_ID_PREFIX):
                jobs.append({
                    "job_id": job.id,
                    "workflow_id": job.id.replace(SCHEDULER_JOB_ID_PREFIX, ""),
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                })
        return jobs
