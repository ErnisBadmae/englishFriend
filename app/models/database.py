# Импортируем все модели для автоматического создания таблиц
from app.models.enums_and_dimensions import *
from app.models.core_tables import *
from app.models.extended_tables import *

# Экспортируем основные модели для обратной совместимости
from app.models.core_tables import User, Session