"""
Скрипт для заполнения базы данных тестовыми данными.
Использует SQL seed файлы коллеги из db/seed/ для справочников.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal, init_db
from app.models.enums_and_dimensions import DimEmotion, DimTopic, DimAccent
from app.models.core_tables import User, Session
from app.models.enums_and_dimensions import CEFRLevel
from datetime import datetime
import uuid

async def create_test_data():
    """Создать тестовые данные в базе"""
    
    print("🚀 Начинаем заполнение базы данных тестовыми данными...")
    
    # Инициализируем БД
    await init_db()
    print("✅ База данных инициализирована")
    
    async with AsyncSessionLocal() as session:
        try:
            # Примечание: SQL seed файлы коллеги (db/seed/*.sql) нужно запускать отдельно
            # через psql или flyway. Этот скрипт добавляет только тестовые пользователи и сессии.
            
            print("📝 Создаем тестовых пользователей...")
            
            # Создаем нескольких тестовых пользователей
            test_users = [
                {
                    "telegram_id": 123456789,
                    "username": "test_user_1",
                    "language_level": "B1",
                    "accent_pref": "us_general"
                },
                {
                    "telegram_id": 987654321,
                    "username": "test_user_2", 
                    "language_level": "A2",
                    "accent_pref": "uk_rp"
                },
                {
                    "telegram_id": 555666777,
                    "username": "test_user_3",
                    "language_level": "C1",
                    "accent_pref": "aus"
                }
            ]
            
            created_users = []
            for user_data in test_users:
                # Проверяем, не существует ли уже пользователь
                from sqlalchemy import select
                result = await session.execute(
                    select(User).where(User.telegram_id == user_data["telegram_id"])
                )
                existing_user = result.scalar_one_or_none()
                
                if not existing_user:
                    user = User(**user_data)
                    session.add(user)
                    created_users.append(user_data["username"])
                else:
                    print(f"⚠️ Пользователь {user_data['username']} уже существует")
            
            await session.commit()
            print(f"✅ Создано {len(created_users)} пользователей: {', '.join(created_users)}")
            
            print("🎯 Создаем тестовые сессии...")
            
            # Получаем созданных пользователей
            result = await session.execute(select(User))
            users = result.scalars().all()
            
            if users:
                # Создаем тестовую сессию для первого пользователя
                test_session = Session(
                    user_id=users[0].id,
                    lang_code="en",
                    status="active"
                )
                session.add(test_session)
                await session.commit()
                print(f"✅ Создана тестовая сессия для пользователя {users[0].username}")
            
            print("🎉 Тестовые данные успешно созданы!")
            print("\n📚 Для заполнения справочников (эмоции, темы, акценты) запустите:")
            print("   psql $DATABASE_URL -f db/seed/001_reference_seed.sql")
            print("   psql $DATABASE_URL -f db/seed/002_demo_data.sql")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при создании тестовых данных: {e}")
            raise

async def main():
    """Главная функция"""
    try:
        await create_test_data()
        print("\n✅ Заполнение базы данных завершено успешно!")
        print("🔗 Теперь можно тестировать API endpoints:")
        print("   - http://localhost:8000/docs - Swagger UI")
        print("   - http://localhost:8000/api/v1/status - Статус API")
        print("   - http://localhost:8000/api/v1/users/ - Пользователи")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())