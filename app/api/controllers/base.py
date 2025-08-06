"""Базовый класс контроллера с общими HTTP методами."""
import structlog
from typing import Any, Awaitable, Callable

from fastapi import HTTPException


class BaseController:
    """Базовый контроллер с общими методами для обработки HTTP запросов."""
    
    def __init__(self) -> None:
        """Инициализация базового контроллера."""
        self.logger = structlog.get_logger()
    
    async def handle_request(
        self,
        request_func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs
    ) -> Any:
        """Стандартная обработка запроса с конвертацией ошибок в HTTP исключения.
        
        Args:
        ----
            request_func: Функция сервиса для выполнения
            *args: Позиционные аргументы для функции
            **kwargs: Именованные аргументы для функции
            
        Returns:
        -------
            Результат выполнения request_func
            
        Raises:
        ------
            HTTPException: При любых ошибках выполнения
            
        """
        try:
            return await request_func(*args, **kwargs)
        except HTTPException:
            # Повторно выбрасываем HTTPException
            raise
        except ValueError as e:
            # Ошибки валидации
            raise HTTPException(
                status_code=400,
                detail=f"Ошибка валидации: {str(e)}"
            ) from e
        except TimeoutError as e:
            # Таймауты
            raise HTTPException(
                status_code=504,
                detail="Превышено время ожидания обработки"
            ) from e
        except Exception as e:
            # Общие ошибки
            self.logger.error(
                "Неожиданная ошибка в контроллере",
                error=str(e),
                controller=self.__class__.__name__,
                function=request_func.__name__ if hasattr(request_func, '__name__') else 'unknown'
            )
            raise HTTPException(
                status_code=500,
                detail="Внутренняя ошибка сервера"
            ) from e
    
    def format_response(self, data: Any, status_code: int = 200) -> Any:
        """Стандартное форматирование ответа.
        
        Args:
        ----
            data: Данные для ответа
            status_code: HTTP статус код
            
        Returns:
        -------
            Отформатированный ответ
            
        """
        # Базовая реализация просто возвращает данные
        # Подклассы могут переопределить для специфического форматирования
        return data
    
    def validate_id(self, id_value: str, field_name: str = "id") -> str:
        """Валидация ID полей.
        
        Args:
        ----
            id_value: Значение ID для валидации
            field_name: Имя поля для сообщения об ошибке
            
        Returns:
        -------
            Валидный ID
            
        Raises:
        ------
            HTTPException: Если ID невалидный
            
        """
        if not id_value or not id_value.strip():
            raise HTTPException(
                status_code=400,
                detail=f"Поле {field_name} не может быть пустым"
            )
        
        # Базовая валидация - только не пустой
        # Подклассы могут добавить более строгую валидацию
        return id_value.strip()