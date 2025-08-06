#!/usr/bin/env python3
"""Скрипт для проверки настройки проекта с Python 3.12 и uv."""

import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Проверить версию Python."""
    version = sys.version_info
    print(f"🐍 Python: {version.major}.{version.minor}.{version.micro}")
    
    if version.major == 3 and version.minor >= 12:
        print("✅ Python 3.12+ установлен")
        return True
    else:
        print("❌ Требуется Python 3.12+")
        return False


def check_uv_installed():
    """Проверить установку uv."""
    try:
        result = subprocess.run(['uv', '--version'], capture_output=True, text=True)
        print(f"📦 uv: {result.stdout.strip()}")
        print("✅ uv установлен")
        return True
    except FileNotFoundError:
        print("❌ uv не установлен")
        print("Установите uv: curl -LsSf https://astral.sh/uv/install.sh | sh")
        return False


def check_project_files():
    """Проверить наличие необходимых файлов проекта."""
    required_files = [
        'pyproject.toml',
        'uv.lock',
        '.python-version',
        'main.py',
        'app/__init__.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if not missing_files:
        print("✅ Все необходимые файлы проекта присутствуют")
        return True
    else:
        print(f"❌ Отсутствуют файлы: {', '.join(missing_files)}")
        return False


def check_dependencies():
    """Проверить синхронизацию зависимостей."""
    try:
        result = subprocess.run(['uv', 'sync', '--dry-run'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Зависимости синхронизированы")
            return True
        else:
            print("❌ Проблемы с зависимостями")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Ошибка проверки зависимостей: {e}")
        return False


def main():
    """Основная функция проверки."""
    print("🔍 Проверка настройки проекта Easy Flow\n")
    
    checks = [
        ("Python 3.12+", check_python_version),
        ("uv package manager", check_uv_installed), 
        ("Project files", check_project_files),
        ("Dependencies", check_dependencies),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n📋 Проверка: {name}")
        results.append(check_func())
    
    print(f"\n{'='*50}")
    
    if all(results):
        print("🎉 Все проверки пройдены успешно!")
        print("\nДля запуска разработки:")
        print("  make install-dev  # Установка dev-зависимостей")
        print("  make dev          # Запуск в режиме разработки")
        print("  make test         # Запуск тестов")
    else:
        print("⚠️  Некоторые проверки не пройдены")
        print("Исправьте ошибки выше перед продолжением")
        sys.exit(1)


if __name__ == "__main__":
    main()