# Makefile для управления проектом English Friend

.PHONY: help install start stop logs clean test test-unit test-integration lint format

# Показать справку
help:
	@echo "Доступные команды:"
	@echo "  install    - Установить зависимости"
	@echo "  start      - Запустить PostgreSQL и приложение"
	@echo "  stop       - Остановить все сервисы"
	@echo "  logs       - Показать логи PostgreSQL"
	@echo "  clean      - Очистить данные БД"
	@echo "  test       - Запустить все тесты"
	@echo "  test-unit  - Запустить только unit тесты"
	@echo "  test-integration - Запустить integration тесты"
	@echo "  lint       - Проверить код линтерами"
	@echo "  format     - Форматировать код"

# Установка зависимостей
install:
	pip install -r requirements.txt

# Запуск PostgreSQL через Docker Compose
start-db:
	docker-compose up -d postgres
	@echo "⏳ Ожидание готовности PostgreSQL..."
	@timeout 30 bash -c 'until docker exec english_friend_postgres pg_isready -U postgres; do sleep 1; done'
	@echo "✅ PostgreSQL готов!"

# Запуск приложения
start-app:
	python main.py

# Запуск всего
start: start-db
	@echo "🚀 Запуск приложения..."
	python main.py

# Остановка всех сервисов
stop:
	docker-compose down

# Показать логи PostgreSQL
logs:
	docker-compose logs -f postgres

# Очистить данные БД
clean:
	docker-compose down -v
	docker volume rm englishfriend_postgres_data 2>/dev/null || true
	@echo "🗑️ Данные БД очищены"

# Тестирование подключения к БД
test-db:
	@echo "🔍 Тестирование подключения к PostgreSQL..."
	docker exec english_friend_postgres psql -U postgres -d english_friend -c "SELECT 'Connection successful' as status;"

# Запуск всех тестов
test:
	@echo "🧪 Запуск всех тестов..."
	pytest

# Запуск только unit тестов
test-unit:
	@echo "🧪 Запуск unit тестов..."
	pytest -m unit

# Запуск integration тестов
test-integration:
	@echo "🧪 Запуск integration тестов..."
	pytest -m integration

# Проверка кода линтерами
lint:
	@echo "🔍 Проверка кода линтерами..."
	flake8 app/ tests/
	mypy app/

# Форматирование кода
format:
	@echo "🎨 Форматирование кода..."
	black app/ tests/
	isort app/ tests/

# Полная переустановка с тестовыми данными
reset-with-data: clean start-db seed-db
	@echo "🔄 Проект переустановлен с тестовыми данными"