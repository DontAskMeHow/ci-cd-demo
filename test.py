#!/usr/bin/env python3
"""
Тест приложения с поддержкой запуска отдельных проверок.
Исправлена проверка динамических метрик (cpu, memory).

Использование:
  # Все тесты
  python test.py
  
  # Отдельный тест по имени поля
  python test.py --test python_version
  
  # Только получить значение (для скриптов)
  python test.py --test hostname --echo
  
  # Список доступных тестов
  python test.py --list
"""
import urllib.request
import json
import sys
import os
import time
import argparse
import platform
import psutil


# 🔹 Функции-проверки: каждая возвращает значение конкретного поля
def get_hostname():
    return os.environ.get('HOSTNAME', 'unknown')


def get_python_version():
    return platform.python_version()


def get_cpu_percent():
    return psutil.cpu_percent(interval=1)


def get_memory_percent():
    return psutil.virtual_memory().percent


def get_memory_total_mb():
    return round(psutil.virtual_memory().total / (1024**2), 2)


def get_disk_percent():
    return psutil.disk_usage('/').percent


def get_disk_total_gb():
    return round(psutil.disk_usage('/').total / (1024**3), 2)


# 🔹 Конфигурация тестов: тип проверки для каждого поля
#    'static' — точное сравнение (hostname, version)
#    'dynamic' — проверка диапазона (cpu, memory)
#    'numeric' — проверка что число > 0 (memory_total, disk_total)
TEST_CONFIG = {
    'hostname': {'type': 'static', 'func': get_hostname},
    'python_version': {'type': 'static', 'func': get_python_version},
    'cpu_percent': {'type': 'dynamic', 'func': get_cpu_percent, 'min': 0, 'max': 100},
    'memory_percent': {'type': 'dynamic', 'func': get_memory_percent, 'min': 0, 'max': 100},
    'memory_total_mb': {'type': 'numeric', 'func': get_memory_total_mb, 'min': 0},
    'disk_percent': {'type': 'dynamic', 'func': get_disk_percent, 'min': 0, 'max': 100},
    'disk_total_gb': {'type': 'numeric', 'func': get_disk_total_gb, 'min': 0},
}

TESTS = {name: cfg['func'] for name, cfg in TEST_CONFIG.items()}


def get_test_url():
    """Определяет URL для тестирования"""
    if os.environ.get('TEST_URL'):
        return os.environ['TEST_URL']
    if os.path.exists('/.dockerenv') or os.environ.get('HOSTNAME'):
        return 'http://localhost:8000'
    return 'http://localhost:80'


def fetch_data(url, timeout=10, retries=3):
    """Получает данные с эндпоинта с повторными попытками"""
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    raise Exception(f"HTTP status {response.status}")
                return json.loads(response.read().decode())
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                print(f"Attempt {attempt + 1} failed: {e}, retrying in 2s...", file=sys.stderr)
                time.sleep(2)
            else:
                raise last_error
    raise last_error


def validate_static(field_name, expected, actual):
    """Проверка для статических значений: точное совпадение"""
    if expected == actual:
        print(f"✅ {field_name}: OK (value: {actual})")
        return True
    else:
        print(f"❌ {field_name}: expected '{expected}', got '{actual}'")
        return False


def validate_dynamic(field_name, actual, min_val, max_val):
    """Проверка для динамических значений: диапазон + тип"""
    if not isinstance(actual, (int, float)):
        print(f"❌ {field_name}: expected number, got {type(actual).__name__}")
        return False
    if not (min_val <= actual <= max_val):
        print(f"❌ {field_name}: value {actual} out of range [{min_val}, {max_val}]")
        return False
    print(f"✅ {field_name}: OK (value: {actual} in range [{min_val}, {max_val}])")
    return True


def validate_numeric(field_name, actual, min_val):
    """Проверка для числовых значений: больше минимума"""
    if not isinstance(actual, (int, float)):
        print(f"❌ {field_name}: expected number, got {type(actual).__name__}")
        return False
    if actual < min_val:
        print(f"❌ {field_name}: value {actual} < minimum {min_val}")
        return False
    print(f"✅ {field_name}: OK (value: {actual} >= {min_val})")
    return True


def run_single_test(field_name):
    """Запускает ОДИН тест по имени поля"""
    if field_name not in TEST_CONFIG:
        print(f"❌ Unknown test: '{field_name}'", file=sys.stderr)
        print(f"Available tests: {', '.join(TEST_CONFIG.keys())}", file=sys.stderr)
        return 1
    
    config = TEST_CONFIG[field_name]
    url = get_test_url()
    print(f"Testing field '{field_name}' via {url}")
    
    # Получаем фактическое значение через HTTP
    try:
        data = fetch_data(url)
        actual = data.get(field_name)
        print(f"  Actual (HTTP): {actual}")
    except Exception as e:
        print(f"❌ Failed to fetch from {url}: {e}", file=sys.stderr)
        return 1
    
    # Валидация в зависимости от типа
    test_type = config.get('type', 'static')
    if test_type == 'static':
        expected = config['func']()
        return 0 if validate_static(field_name, expected, actual) else 1
    elif test_type == 'dynamic':
        return 0 if validate_dynamic(field_name, actual, config['min'], config['max']) else 1
    elif test_type == 'numeric':
        return 0 if validate_numeric(field_name, actual, config['min']) else 1
    else:
        print(f"❌ Unknown test type: {test_type}", file=sys.stderr)
        return 1


def run_all_tests():
    """Запускает все тесты"""
    url = get_test_url()
    print(f"Running all tests via {url}\n")
    
    try:
        data = fetch_data(url)
    except Exception as e:
        print(f"❌ Failed to connect to {url}: {e}", file=sys.stderr)
        return 1
    
    print("=== Response from application ===")
    for key, value in data.items():
        print(f"  {key}: {value}")
    
    print("\n=== Running validations ===")
    failed = []
    
    for field_name, config in TEST_CONFIG.items():
        actual = data.get(field_name)
        test_type = config.get('type', 'static')
        
        if test_type == 'static':
            expected = config['func']()
            if not validate_static(field_name, expected, actual):
                failed.append(field_name)
        elif test_type == 'dynamic':
            if not validate_dynamic(field_name, actual, config['min'], config['max']):
                failed.append(field_name)
        elif test_type == 'numeric':
            if not validate_numeric(field_name, actual, config['min']):
                failed.append(field_name)
    
    if failed:
        print(f"\n❌ Failed tests: {', '.join(failed)}")
        return 1
    
    print("\n✅ All tests passed!")
    return 0


def run_echo_test(field_name):
    """Только вывести значение (для использования в скриптах)"""
    if field_name not in TESTS:
        print(f"ERROR: Unknown test '{field_name}'", file=sys.stderr)
        return 1
    value = TESTS[field_name]()
    print(value)
    return 0


def list_tests():
    """Выводит список доступных тестов"""
    print("Available tests:")
    for name, cfg in TEST_CONFIG.items():
        print(f"  - {name:20s} [{cfg['type']}]")
    return 0


def main():
    parser = argparse.ArgumentParser(description='Application tests')
    parser.add_argument('--test', type=str, help='Run a single test by field name')
    parser.add_argument('--list', action='store_true', help='List available tests')
    parser.add_argument('--echo', action='store_true', help='Only output the value (for scripting)')
    args = parser.parse_args()
    
    if args.list:
        return list_tests()
    
    if args.test:
        if args.echo:
            return run_echo_test(args.test)
        else:
            return run_single_test(args.test)
    
    return run_all_tests()


if __name__ == '__main__':
    sys.exit(main())