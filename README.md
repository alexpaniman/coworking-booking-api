# Coworking Booking API

REST-сервис на FastAPI для бронирования рабочих мест и переговорных комнат в коворкинге.

Проект демонстрирует CRUD-операции, JWT-аутентификацию, роли пользователей, PostgreSQL, Alembic-миграции, автоматические тесты и алгоритм подбора слотов с динамической ценой.

## Быстрый запуск

```bash
docker compose up --build
```

Swagger будет доступен по адресу:

```text
http://localhost:8000/docs
```

## Запуск тестов

```bash
docker compose run --rm api pytest
```

## Pylint

```bash
docker compose run --rm api sh -c "pylint app > pylint.txt"
```

Файл `pylint.txt` нужно закоммитить перед сдачей.

## Демо-данные

После запуска контейнеров можно заполнить базу демо-данными:

```bash
docker compose exec api python -m app.seed
```

Будут созданы:

- `admin@example.com` / `secret123`
- `user@example.com` / `secret123`
- локация, две комнаты, удобства и правило пиковой цены.

## Основные endpoint'ы

- `POST /auth/register` — регистрация пользователя.
- `POST /auth/login` — вход и получение JWT.
- `GET /users/me` — защищенный endpoint текущего пользователя.
- `POST /locations`, `POST /rooms`, `POST /amenities`, `POST /pricing-rules` — admin CRUD.
- `POST /bookings` — создание бронирования.
- `POST /bookings/{booking_id}/cancel` — отмена бронирования.
- `POST /recommendations/booking-options` — подбор свободных вариантов бронирования.

Локации имеют рабочие часы `opens_at` и `closes_at`; сервис не дает забронировать комнату вне этого окна.

## Алгоритм рекомендаций

Endpoint `/recommendations/booking-options` принимает дату, временное окно, длительность, количество людей, бюджет, нужные удобства и признак необходимости переговорки.

Алгоритм:

1. Отбирает активные комнаты по вместимости, типу, локации и удобствам.
2. Делит временное окно на слоты по 30 минут.
3. Исключает слоты, которые пересекаются с подтвержденными бронированиями.
4. Считает динамическую цену:

```text
price = base_price_per_hour
      * duration_hours
      * room_type_multiplier
      * pricing_rule_multiplier
      * occupancy_multiplier
```

5. Фильтрует варианты дороже `max_price`.
6. Сортирует варианты по score и цене, возвращает до 10 лучших.

## Telegram

Telegram-интеграция опциональна. Для включения задайте переменные:

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Сервис отправляет уведомления при создании и отмене бронирования. Ошибка Telegram не ломает бронирование.

## Сценарий для видео

1. Открыть `http://localhost:8000/docs`.
2. Зарегистрировать admin и user или выполнить `python -m app.seed`.
3. Авторизоваться через `/auth/login`.
4. Создать локацию, удобство, комнату и pricing rule.
5. Создать бронирование.
6. Показать запрет пересекающегося бронирования.
7. Вызвать `/recommendations/booking-options`.
8. Показать фрагмент кода `app/services/recommendations.py` или `app/services/pricing.py`.
9. Показать `pylint.txt`.

## Автор

alexpaniman <alexpaniman@gmail.com>
