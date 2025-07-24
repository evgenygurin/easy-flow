"""
Главная точка входа в AI платформу для e-commerce поддержки клиентов.
"""
import uvicorn
from app.api.main import app

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )