"""
Database repositories package.
"""
from app.database.repositories.user_repo import UserRepository, user_repo
from app.database.repositories.research_repo import ResearchRepository, research_repo
from app.database.repositories.task_repo import TaskRepository, task_repo
from app.database.repositories.source_repo import SourceRepository, source_repo
from app.database.repositories.report_repo import ReportRepository, report_repo

__all__ = [
    "UserRepository",
    "user_repo",
    "ResearchRepository",
    "research_repo",
    "TaskRepository",
    "task_repo",
    "SourceRepository",
    "source_repo",
    "ReportRepository",
    "report_repo",
]
