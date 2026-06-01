"""API routers package."""

from routers.books import router as books_router
from routers.exams import router as exams_router
from routers.moe_library import router as moe_library_router
from routers.subjects import router as subjects_router
from routers.workbooks import router as workbooks_router

__all__ = [
    "books_router",
    "exams_router",
    "moe_library_router",
    "subjects_router",
    "workbooks_router",
]
