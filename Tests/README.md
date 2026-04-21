# RTKS Tracker — Тесты

## Актуальный статус на 2026-04-21

### Подтверждённые прогоны

| Контур | Результат | Где подтверждено |
|---|---:|---|
| Backend (`pytest`) | **91/91** | VPS, 2026-04-21, `PYTHONPATH=~/network-tracker/backend /tmp/rts-web-codex-venv/bin/pytest -q` |
| Frontend (`jest`) | **55/55** | VPS, 2026-04-20 |
| E2E (`playwright`) | **69 passed, 1 skipped, 1 flaky** | VPS, 2026-04-20, Playwright Docker runner |
| **Важно** | `reports.spec.js` сейчас не входит в `testMatch` ни одного Playwright project | поэтому не участвует в подтверждённом e2e-прогоне |

### Текущий инвентарь backend-набора в репозитории

| Файл | Тестов | Статус |
|---|---:|---|
| `test_auth.py` | 13 | `+1` scoped Excel token guard |
| `test_contractors.py` | 2 | `+2` новый directory-набор |
| `test_excel.py` | 10 | `+1` export embeds `excel_sync` token |
| `test_projects.py` | 16 | ✅ |
| `test_regions.py` | 2 | `+2` новый directory-набор |
| `test_reports.py` | 6 | `+6` новый reports-набор |
| `test_sites.py` | 19 | расширен под explicit commits и no-write-on-GET |
| `test_sync.py` | 23 | `+5` Excel token scope и project-scoping |
| **Итого backend** | **91** | Полный VPS-прогон под этот инвентарь подтверждён на VPS |

- Новый backend-набор проверяет, что import/sync по неизвестному `ID объекта` не создают новый объект.
- На 2026-04-21 backend-набор дополнительно проверяет:
  - `excel_sync` token в XLSM-export;
  - запрет `excel_sync` token для обычных browser auth-endpoints;
  - допуск `excel_sync` token на `/sync` и `/sync/columns` только в рамках зашитого `project_id`;
  - запрет sync строки с `site_id`, относящимся к другому проекту.
- Дополнительно подтверждено, что `GET /sites`, `GET /sites/{id}`, `GET /regions`, `GET /contractors` больше не пишут в БД.
- Дополнительно подтверждено, что после удаления скрытого auto-commit из `get_db` write-endpoints сохраняют данные только за счёт явных `commit()`.
- На `2026-04-17` в `test_sync.py` добавлен regression test, который проверяет, что `GET /api/v1/sync/history-fields` не перехватывается маршрутом `/api/v1/sync/history/{site_id}`.
- На 2026-04-21 подтверждён полный backend-набор `91/91`, frontend unit `55/55` и текущий e2e-run `69 passed, 1 skipped, 1 flaky`.
- Текущий инвентарь в коде: `91 backend + 55 frontend unit + 7 e2e spec files`.
- `test_sync.py` уже опирается на поле нового шаблона, а не на старые NI-колонки.
- Во frontend unit-наборе теперь `55` Jest test cases (`test_utils.test.js` + `test_api.test.js`).
- Канонический backend-runner на VPS сейчас использует свежий `/tmp/rts-web-codex-venv`; `~/network-tracker/Tests/backend/.venv` на сервере по-прежнему неканоничен.
- Для E2E канонический серверный прогон сейчас делается через Docker-образ Playwright, а не через локальный host Chromium.

### Важные исправления, которые потребовались

1. `Tests/backend/conftest.py`
   Добавлен `PRAGMA foreign_keys=ON` через `event.listens_for(..., "connect")`, чтобы SQLite в тестах реально соблюдал FK-ограничения.
2. `Tests/backend/test_sites.py`
   В `test_contractor_sees_only_own_sites` исправлена проверка
   `item["contractor_id"] -> item["contractor"]["id"]`,
   потому что `SiteListItem` возвращает вложенный объект `contractor`, а не плоский FK.
3. `Tests/backend/test_sites.py`
   В `test_admin_can_delete_site` перед `DELETE` вручную удаляется `site_history`,
   потому что при SQLite-связях backref пытался делать `SET NULL` на `site_id` в `site_history`,
   а поле `site_id` там `NOT NULL`.
4. `Tests/backend/conftest.py`
   Test override для `get_db` больше не делает скрытый `commit`, чтобы тесты ловили отсутствие явного `commit()` в mutating endpoints.
5. `Tests/backend/conftest.py`
   Добавлен autouse-reset для `slowapi` limiter, чтобы login-limit `5/minute` не давал межтестовые `429`.

## Структура

```text
Tests/
├── backend/              # Python API-тесты (pytest + httpx + aiosqlite)
│   ├── pytest.ini
│   ├── requirements-test.txt
│   ├── conftest.py       # фикстуры: БД, seed-данные, HTTP-клиент
│   ├── test_auth.py      # аутентификация
│   ├── test_contractors.py # подрядчики: no-write-on-GET и ручной is_active
│   ├── test_projects.py  # проекты: RBAC, создание, удаление
│   ├── test_regions.py   # регионы: no-write-on-GET и ручной is_active
│   ├── test_reports.py   # reports API и UCN-агрегации
│   ├── test_sites.py     # объекты: фильтры, CRUD, права подрядчика
│   ├── test_excel.py     # Excel export/import для нового UCN-шаблона
│   └── test_sync.py      # XLSM sync, история изменений, rollback
├── frontend/             # JS unit-тесты (Jest + jsdom)
│   ├── package.json
│   ├── jest.setup.js     # глобальные моки (api, bootstrap)
│   ├── test_api.test.js   # api.js: helpers и форматирование ошибок
│   └── test_utils.test.js # utils.js: маршрутизация, navbar, badges
└── e2e/                  # Playwright E2E-тесты (против выбранного стенда)
    ├── package.json
    ├── playwright.config.js
    ├── global-setup.js   # логин admin/non-admin через API → .auth/*.json
    ├── helpers/
    │   └── auth.js       # login(), logout(), openUcnProject()
    └── tests/
        ├── auth.spec.js      # форма входа, выход, сессия, RBAC редиректы
        ├── admin.spec.js     # /users, /projects, /logs, /profile как admin
        ├── projects.spec.js  # плитки проектов, переход в UCN, navbar
        ├── reports.spec.js   # раздел отчетов, empty state, кнопки выгрузок
        └── sites.spec.js     # список объектов, поиск, карточка, экспорт
```

Локальные служебные каталоги не должны коммититься:

- `Tests/backend/.venv/`
- `Tests/.claude/`
- `Tests/frontend/node_modules/`
- `Tests/e2e/node_modules/`
- `Tests/e2e/.auth/`            # токены авторизации (создаются на лету)
- `Tests/e2e/test-results/`
- `Tests/e2e/playwright-report/`

---

## E2E-тесты (Playwright)

### Запуск на сервере или стенде (рекомендуется)

Перед запуском задать переменные окружения:

```bash
export E2E_BASE_URL="https://your-tracker.example.com"
export E2E_ADMIN_USERNAME="<admin-username>"
export E2E_ADMIN_PASSWORD="<admin-password>"
export E2E_USER_USERNAME="<non-admin-username>"
export E2E_USER_PASSWORD="<non-admin-password>"
```

```bash
ssh <vps-alias> "docker run --rm \
  -v <server-project-dir>/Tests/e2e:/e2e \
  --network host \
  mcr.microsoft.com/playwright:v1.44.0-jammy \
  sh -c 'cd /e2e && npx playwright test --reporter=list'"
```

### Что тестируется

| Файл | Покрытые сценарии |
|---|---|
| `auth.spec.js` | Форма входа (успех/ошибка), выход, редирект с живым токеном, RBAC-редиректы для non-admin user |
| `admin.spec.js` | Список пользователей, модалка добавления, список проектов, логи, профиль, dropdown navbar |
| `projects.spec.js` | Плитки проектов, наличие 3 проектов, кнопка «Управление проектами», переход в UCN, navbar |
| `reports.spec.js` | Раздел `Отчеты` в navbar, UCN-отчеты, кнопки `PDF/PPT/Excel`, empty state placeholder-проекта |
| `sites.spec.js` | Список объектов UCN, поиск, фильтр по статусу, карточка объекта, кнопки Экспорт/Импорт |

Важно:

- В текущем `Tests/e2e/playwright.config.js` в `projects[].testMatch` подключены `admin.spec.js`, `projects.spec.js`, `sites.spec.js`, `site_edit.spec.js`, `directories.spec.js` и `auth.spec.js`.
- `reports.spec.js` есть в репозитории, но пока не входит в подтверждённый server-run, пока его не добавят в один из Playwright projects.

### Архитектура

- **globalSetup**: логинится как `admin` и `non-admin` через API (одно bcrypt-хеширование), сохраняет токены в `.auth/*.json`
- **Проект `admin`**: использует `storageState: .auth/admin.json` — без повторных логинов в тестах
- **Проект `auth`**: без storageState — тестирует форму входа напрямую
- **helpers/auth.js**: `login()` (через форму), `logout()`, `openUcnProject()`

---

## Backend-тесты (pytest)

### Зависимости

Установка один раз перед первым запуском:

```bash
cd Tests/backend
pip install -r ../../backend/requirements.txt -r requirements-test.txt
```

### Запуск

```bash
cd Tests/backend
pytest
```

Для Codex/локального агента подтверждающий backend-прогон лучше считать серверным, на VPS:

- локальная системная `python3` может быть ниже `3.12`;
- прямой `rsync` проверочных правок в `~/network-tracker` нежелателен, потому что продовый backend там работает с bind-mount `./backend:/app` и `--reload`;
- безопасный паттерн для незакоммиченных правок: временная копия проекта на VPS и запуск `pytest` уже из неё.

Запустить отдельный файл:

```bash
pytest test_auth.py -v
pytest test_projects.py -v
pytest test_reports.py -v
pytest test_sites.py -v
pytest test_excel.py -v
pytest test_sync.py -v
```

С подробным выводом и остановкой на первой ошибке:

```bash
pytest -v -x
```

### Что тестируется

| Файл | Покрытые сценарии |
|---|---|
| `test_auth.py` | Логин (успех/ошибка), `/auth/me`, роли, `PATCH /auth/me`, смена собственного логина/пароля, admin update логина/пароля |
| `test_projects.py` | Admin видит все проекты; manager/viewer — только назначенные; contractor — по объектам; создание/удаление проектов; `is_configured` флаг |
| `test_reports.py` | Каталог reports по `module_key`; UCN detail-отчеты; contractor-scoping; placeholder → пустой список и `404` на detail |
| `test_sites.py` | `GET /sites/?project_id=...` для ucn и placeholder; CRUD с правами; contractor-ограничения |
| `test_excel.py` | Экспорт: placeholder→400, ucn→OK/500, недоступный проект→404; экспортируемый лист `Data` защищён от вставки/удаления строк; импорт: wrong ext→400, viewer→403; импорт нового шаблона обновляет существующий объект по `ID объекта` и отвергает новую строку |
| `test_sync.py` | Sync с изменением поля нового шаблона → история; sync отвергает новую строку с неизвестным `ID объекта`; rollback-entry (admin) и rollback (timestamp); права по ролям |

### Архитектура тестовой БД

- **In-memory SQLite** (`aiosqlite`) вместо PostgreSQL — не нужно запускать сервер БД.
- `Base.metadata.create_all` создаёт схему без Alembic-миграций.
- Каждый тест получает **свежую БД** (function-scope) с pre-seeded данными.
- `get_db` dependency переопределяется через `app.dependency_overrides`.

### Известные ограничения

- **SQLite vs PostgreSQL**: `Enum` с именами (PostgreSQL ENUM type) работает как VARCHAR — ок для тестов.
  `onupdate=func.now()` не срабатывает автоматически в SQLite, поэтому `updated_at` при UPDATE
  не изменяется, если не задан явно. Тесты, которые проверяют временны́е метки, могут вести себя иначе.
- **XLSM-шаблон**: `GET /excel/export` для UCN-проекта вернёт 500, если в тестовой среде
  отсутствует `backend/templates/sync_template.xlsm`. Это ожидаемо и допустимо.
- **Async fixtures**: используется `pytest-asyncio >= 0.23` с `asyncio_mode = auto`.
  Если тесты падают с `ScopeMismatch` или `EventLoopPolicy` — обновите pytest-asyncio:
  `pip install --upgrade pytest-asyncio`.
- **VPS runner**: подтверждённый серверный backend-runner сейчас использует свежий `/tmp/rts-web-codex-venv`.
  Локальный `~/network-tracker/Tests/backend/.venv` на VPS пока не считается каноническим.

---

## Frontend-тесты (Jest)

### Зависимости

```bash
cd Tests/frontend
npm install
```

### Запуск

```bash
cd Tests/frontend
npm test
```

С покрытием:

```bash
npm run test:coverage
```

### Что тестируется

| Функция | Покрытые сценарии |
|---|---|
| `getProjectRoute()` | `ucn_sites_v1` → `/sites.html?project_id=<id>`; `placeholder` → `/project.html?id=<id>`; `null/undefined` → `/index.html` |
| `getProjectReportsRoute()` | Любой выбранный проект → `/reports.html?project_id=<id>` |
| `moduleLabel()` | `ucn_sites_v1` → 'Модуль УЦН'; `placeholder` / unknown → 'Архитектурный контейнер' |
| `escHtml()` | `&`, `<`, `>` экранируются; null/undefined → `''`; XSS-payload нейтрализован |
| `renderNavbar()` | index-страница: нет "Объекты" и нет "Сменить проект"; внутренние страницы: есть `Отчеты`; нет отдельного верхнего пункта "Проекты"; dropdown содержит "Мой профиль"; admin видит "Управление проектами", viewer — нет |
| `api.getReports()/getReport()` | Правильная сборка путей `/reports/` и detail-route по `project_id + report_key` |
| `formatApiErrorDetail()` | массив/объект из `detail` превращается в человекочитаемый текст вместо `[object Object]` |
| `statusBadge()` | Все статусы: русские названия и класс |
| `roleBadge()` | Все роли: русские названия |
| `rememberProject()` | Вызывает `api.setCurrentProject`; null — не вызывает |

### Что НЕ покрыто

- **E2E (Playwright/Cypress)**: требует запущенного сервера. Ближайший задел — навигация
  `/login.html` → `/index.html` → выбор проекта → `/sites.html` и `/reports.html`.
- **Browser-download assertions**: фактическая проверка скачивания `PDF/PPT/Excel` пока не доведена до автоматической валидации файлов.
- **`api.js` (полностью)**: сейчас покрыты только reports helpers и форматирование ошибок; `api.fetch`, `api.me`, `api.getProjects` требуют отдельного мока fetch или msw.
- **`checkAuth()`**: использует `window.location.href =` и `api.me()`. Тестируемо с моками,
  но требует аккуратной настройки `window.location` в jsdom.
- **`sites.html` / `site.html`**: сложная логика с API и ролью пользователя — это следующий E2E-слой.

---

## Быстрая проверка всех тестов

```bash
# Backend
cd /path/to/RTS_Web/Tests/backend && pytest -v

# Frontend
cd /path/to/RTS_Web/Tests/frontend && npm install && npm test
```

## Что было подтверждено на VPS

```bash
# Backend
cd ~/network-tracker/Tests/backend
PYTHONPATH=~/network-tracker/backend /tmp/rts-web-codex-venv/bin/pytest -q

# Frontend
cd ~/network-tracker/Tests/frontend
npm test -- --runInBand

# E2E
docker run --rm \
  -v ~/network-tracker/Tests/e2e:/e2e \
  --network host \
  mcr.microsoft.com/playwright:v1.44.0-jammy \
  sh -c 'cd /e2e && npx playwright test --reporter=list'
```

Для backend на VPS держите в уме текущее состояние окружения:

- полный suite `91/91` подтверждён на сервере 2026-04-21;
- канонический runner сейчас: `/tmp/rts-web-codex-venv/bin/pytest`;
- `~/network-tracker/Tests/backend/.venv` всё ещё требует нормализации.

Безопасный серверный прогон незакоммиченных backend-правок из локальной машины:

```bash
rsync -az --delete --exclude '.git' --exclude 'Tests/backend/.venv' \
  --exclude 'Tests/frontend/node_modules' --exclude 'Tests/.claude' \
  --exclude '__pycache__' --exclude '*.pyc' \
  /path/to/RTS_Web/ \
  vps:/tmp/rts-web-codex-check/
```

После копирования:

- использовать на VPS подтверждённый runner:
  `PYTHONPATH=~/network-tracker/backend /tmp/rts-web-codex-venv/bin/pytest -q`
- если нужен постоянный runner в `~/network-tracker/Tests/backend/.venv`, сначала пересобрать его с корректным Python / `pydantic_core`.

Быстрый smoke именно по новому разделу reports на проде:

```bash
ssh <vps-alias> "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/reports.html"
```
