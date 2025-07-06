"""
统一的API响应结构工具类
"""

from typing import Any, Optional, Dict


class ApiResponse:
    """统一的API响应结构"""
    
    @staticmethod
    def success(data: Any = None, message: Optional[str] = None) -> Dict:
        """成功响应
        
        Args:
            data: 响应数据
            message: 可选的消息
            
        Returns:
            统一的成功响应格式
        """
        response = {
            "code": 0,
            "message": message,
            "data": data if data is not None else {}
        }
        return response
    
    @staticmethod
    def error(message: str, data: Any = None) -> Dict:
        """错误响应
        
        Args:
            message: 错误消息
            data: 可选的错误数据
            
        Returns:
            统一的错误响应格式
        """
        response = {
            "code": -1,
            "message": message,
            "data": data
        }
        return response
    
    @staticmethod
    def custom(code: int, message: Optional[str] = None, data: Any = None) -> Dict:
        """自定义响应
        
        Args:
            code: 响应码
            message: 响应消息
            data: 响应数据
            
        Returns:
            自定义响应格式
        """
        response = {
            "code": code,
            "message": message,
            "data": data if data is not None else {}
        }
        return response 