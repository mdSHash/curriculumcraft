"""API routers package."""

from routers.books import router as books_router
from routers.moe_library import router as moe_library_router
from routers.workbooks import router as workbooks_router

__all__ = ["books_router", "moe_library_router", "workbooks_router"]
