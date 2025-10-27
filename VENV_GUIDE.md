# Инструкции по виртуальному окружению

## Активация виртуального окружения

### Windows (PowerShell)
```bash
# Активация
.\venv\Scripts\activate

# Деактивация
deactivate
```

### Windows (Command Prompt)
```bash
# Активация
venv\Scripts\activate.bat

# Деактивация
deactivate
```

### Linux/macOS
```bash
# Активация
source venv/bin/activate

# Деактивация
deactivate
```

## Проверка окружения

```bash
# Проверить, что используешь виртуальное окружение
python -c "import sys; print(sys.prefix)"

# Должно показать путь к venv, а не системный Python
```

## Установка зависимостей

```bash
# Убедись, что виртуальное окружение активировано
pip install -r requirements.txt

# Проверить установленные пакеты
pip list
```

## Полезные команды

```bash
# Обновить pip
python -m pip install --upgrade pip

# Экспорт зависимостей
pip freeze > requirements.txt

# Установка в dev режиме
pip install -e .
```
