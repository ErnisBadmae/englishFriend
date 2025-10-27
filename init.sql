-- Инициализация базы данных English Friend
-- Этот скрипт выполняется при первом запуске PostgreSQL контейнера

-- Создаем расширения PostgreSQL
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Создаем enum типы
DO $$ BEGIN
    CREATE TYPE cefr_level AS ENUM ('A1', 'A2', 'B1', 'B2', 'C1', 'C2');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Создаем базовые таблицы (они будут пересозданы SQLAlchemy, но это для примера)
-- SQLAlchemy создаст таблицы автоматически при запуске приложения

-- Создаем индексы для производительности
-- (будут созданы автоматически через SQLAlchemy)

-- Вставляем тестовые данные (опционально)
-- INSERT INTO users (telegram_id, username, language_level) VALUES 
-- (123456, 'test_user', 'B1'),
-- (789012, 'demo_user', 'A2');

-- Выводим информацию о созданной БД
SELECT 'Database initialized successfully' as status;
