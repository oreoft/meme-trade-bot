"""
全局异常处理中间件
"""

import logging
import traceback

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from utils.response import ApiResponse


class GlobalExceptionHandler(BaseHTTPMiddleware):
    """全局异常处理中间件"""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException as http_exc:
            # FastAPI的HTTP异常，保持原有处理方式
            return JSONResponse(
                status_code=http_exc.status_code,
                content=ApiResponse.error(message=http_exc.detail)
            )
        except Exception as exc:
            # 未捕获的异常，统一处理
            error_msg = str(exc)
            error_traceback = traceback.format_exc()

            # 记录详细错误日志
            logging.error(f"未处理的异常: {error_msg}")
            logging.error(f"异常堆栈: {error_traceback}")

            # 开发环境显示详细错误，生产环境显示通用错误
            import os
            if os.getenv('DEBUG', 'False').lower() == 'true':
                detailed_error = f"{error_msg}\n\n堆栈跟踪:\n{error_traceback}"
            else:
                detailed_error = "服务器内部错误，请稍后重试"

            return JSONResponse(
                status_code=500,
                content=ApiResponse.error(message=detailed_error)
            )


def setup_exception_handlers(app):
    """设置异常处理器"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP异常处理"""
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiResponse.error(message=exc.detail)
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """通用异常处理"""
        error_msg = str(exc)
        error_traceback = traceback.format_exc()

        # 记录详细错误日志
        logging.error(f"未处理的异常: {error_msg}")
        logging.error(f"异常堆栈: {error_traceback}")

        # 开发环境显示详细错误，生产环境显示通用错误
        import os
        if os.getenv('DEBUG', 'False').lower() == 'true':
            detailed_error = f"{error_msg}\n\n堆栈跟踪:\n{error_traceback}"
        else:
            detailed_error = "服务器内部错误，请稍后重试"

        return JSONResponse(
            status_code=500,
            content=ApiResponse.error(message=detailed_error)
        )
