#!/usr/bin/env python3
"""
Тестирование полного flow API
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_api() -> bool:
    """Тестирование полного flow"""
    print("🚀 Начинаем тестирование полного flow...\n")
    
    # 1. Health check
    print("1️⃣ Проверка health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200, f"Health check failed: {response.status_code}"
    print(f"   ✅ Health: {response.json()}\n")
    
    # 2. Получить список пользователей
    print("2️⃣ Получение списка пользователей...")
    response = requests.get(f"{BASE_URL}/api/v1/users/", params={"limit": 5})
    assert response.status_code == 200, f"Failed to get users: {response.status_code}"
    users = response.json()
    print(f"   ✅ Найдено {users['total']} пользователей")
    if users['users']:
        first_user = users['users'][0]
        print(f"   📝 Первый пользователь: ID={first_user['id']}, Username={first_user.get('username', 'N/A')}")
        user_id = first_user['id']
    else:
        print("   ⚠️ Нет пользователей в базе")
        return False
    print()
    
    # 3. Получить пользователя по ID
    print(f"3️⃣ Получение пользователя {user_id}...")
    response = requests.get(f"{BASE_URL}/api/v1/users/{user_id}")
    assert response.status_code == 200, f"Failed to get user: {response.status_code}"
    user = response.json()
    print(f"   ✅ Пользователь: {json.dumps(user, indent=2, ensure_ascii=False)}\n")
    
    # 4. Получить сессии пользователя
    print(f"4️⃣ Получение сессий пользователя {user_id}...")
    response = requests.get(f"{BASE_URL}/api/v1/sessions/user/{user_id}")
    assert response.status_code == 200, f"Failed to get sessions: {response.status_code}"
    sessions = response.json()
    print(f"   ✅ Найдено {len(sessions)} сессий")
    if sessions:
        session_id = sessions[0]['id']
        print(f"   📝 Первая сессия: {session_id}")
    else:
        print("   ⚠️ Нет сессий")
        session_id = None
    print()
    
    # 5. Получить интересы пользователя
    print(f"5️⃣ Получение интересов пользователя {user_id}...")
    response = requests.get(f"{BASE_URL}/api/v1/users/{user_id}/interests")
    if response.status_code == 200:
        interests = response.json()
        print(f"   ✅ Найдено {interests['total']} интересов")
    else:
        print(f"   ⚠️ Ошибка: {response.status_code}")
    print()
    
    # 6. Получить память пользователя
    print(f"6️⃣ Получение памяти пользователя {user_id}...")
    response = requests.get(f"{BASE_URL}/api/v1/users/{user_id}/memories")
    if response.status_code == 200:
        memories = response.json()
        print(f"   ✅ Найдено {memories['total']} записей памяти")
    else:
        print(f"   ⚠️ Ошибка: {response.status_code}")
    print()
    
    # 7. Получить план обучения
    print(f"7️⃣ Получение плана обучения пользователя {user_id}...")
    response = requests.get(f"{BASE_URL}/api/v1/users/{user_id}/learning-plan")
    if response.status_code == 200:
        plan = response.json()
        print(f"   ✅ План: {json.dumps(plan, indent=2, ensure_ascii=False)}")
    else:
        print(f"   ⚠️ План не найден (это нормально)")
    print()
    
    # 8. Получить XP события
    print(f"8️⃣ Получение XP событий пользователя {user_id}...")
    response = requests.get(f"{BASE_URL}/api/v1/users/{user_id}/xp-events")
    if response.status_code == 200:
        events = response.json()
        print(f"   ✅ Найдено {events['total']} событий")
    else:
        print(f"   ⚠️ Ошибка: {response.status_code}")
    print()
    
    # 9. Получить общий XP
    print(f"9️⃣ Получение общего XP пользователя {user_id}...")
    response = requests.get(f"{BASE_URL}/api/v1/users/{user_id}/xp-total")
    if response.status_code == 200:
        xp_data = response.json()
        print(f"   ✅ Общий XP: {xp_data['total_xp']}")
    else:
        print(f"   ⚠️ Ошибка: {response.status_code}")
    print()
    
    # 10. Получить топ интересы
    print(f"🔟 Получение топ интересов пользователя {user_id}...")
    response = requests.get(f"{BASE_URL}/api/v1/users/{user_id}/interests/top")
    if response.status_code == 200:
        top_interests = response.json()
        print(f"   ✅ Топ {top_interests['total']} интересов")
    else:
        print(f"   ⚠️ Ошибка: {response.status_code}")
    print()
    
    print("✅ Полный flow успешно завершен!")
    return True

if __name__ == "__main__":
    try:
        success = test_api()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

