# RTKS Tracker — краткий актуальный контекст

Обновлено: 2026-04-21

`AGENTS.md` и `HANDOFF.md` остаются более подробными источниками истины. Этот файл нужен как быстрый вход в текущую архитектуру проекта без старого NI-контекста.

## Что это за система сейчас

- Веб-приложение для трекинга строительства объектов мобильной сети.
- Текущий бренд в UI: `RTKS Tracker`.
- Архитектура двухуровневая:
  - верхний уровень: выбор большого проекта;
  - нижний уровень: внутренний модуль выбранного проекта.
- Полноценный модуль сейчас один:
  - `УЦН 2.0 2026 год` (`module_key = ucn_sites_v1`).
- Остальные большие проекты пока используются как контейнеры:
  - `ТСПУ`;
  - `Стройка ЦОД`.
- С 2026-04-18 есть общий проектный раздел `Отчеты`:
  - он доступен у любого выбранного большого проекта;
  - для placeholder-проектов показывает empty state;
  - для UCN уже реализованы 2 отчёта с web-визуалом и выгрузками `PDF`, `PPT`, `Excel`.
- С 2026-04-20 backend больше не делает скрытый `commit` в `get_db`, а чтение `/sites`, `/regions`, `/contractors` больше не триггерит write-sync справочников.
- `is_active` у `regions` и `contractors` теперь ручное поле; автосоздание и `region_id`-привязка для регионов остались только на write-path.
- С 2026-04-21 закрыт этап `2A` по Excel auth hardening:
  - `GET /api/v1/excel/export` встраивает отдельный JWT `token_type=excel_sync`;
  - токен несёт `project_id` и, при наличии, `contractor_id`;
  - обычные browser-endpoints принимают только `access` token;
  - `/sync` и `/sync/columns` принимают `excel_sync`, но только в рамках зашитого проекта;
  - `/sync` отклоняет строки с `site_id`, относящимся к другому проекту.

## Стек

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic
- Database: PostgreSQL 16
- Excel: openpyxl, xlsxwriter, `sync_template.xlsm` как VBA-контейнер
- Auth: JWT (`python-jose`) + `bcrypt==4.0.1`
- Frontend: HTML/JS + Bootstrap 5, без frontend framework
- Infra: Docker Compose, Nginx
- Deploy: `rsync` с локальной машины на VPS, затем `docker compose restart ...`

## VPS и деплой

- Хост: `ssh <vps-alias>`
- Папка проекта: `/home/<deploy-user>/network-tracker/`
- GitHub на VPS недоступен, поэтому `git pull` не используется
- Нормальный workflow:
  1. правки локально;
  2. `git commit`;
  3. `git push origin main`;
  4. `rsync` на VPS;
  5. `docker compose restart backend` и/или `docker compose restart nginx`

Полезные команды:

```bash
# backend
rsync -az backend/ <vps-alias>:/home/<deploy-user>/network-tracker/backend/
ssh <vps-alias> "cd ~/network-tracker && docker compose restart backend"

# frontend
rsync -az frontend/ <vps-alias>:/home/<deploy-user>/network-tracker/frontend/
ssh <vps-alias> "cd ~/network-tracker && docker compose restart nginx"

# smoke
ssh <vps-alias> "curl -s http://127.0.0.1/api/health"
ssh <vps-alias> "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/reports.html"
```

## Ключевые страницы

- `/login.html` — форма входа
- `/index.html` — экран плиток больших проектов
- `/sites.html?project_id=...` — рабочий список объектов для UCN
- `/site.html?id=...&project_id=...` — карточка объекта
- `/project.html?id=...` — placeholder-страница проекта без доменного модуля
- `/reports.html?project_id=...` — раздел проектных отчетов
- `/projects.html` — admin CRUD для больших проектов
- `/users.html` — admin CRUD пользователей
- `/profile.html` — смена собственного логина/пароля
- `/regions.html`, `/contractors.html` — справочники
- `/logs.html` — admin-only логи

## Навигация

- На `/index.html` рабочего пункта `Проекты` больше нет.
- Для `admin` уже на `/index.html` в navbar видны `Пользователи` и `Логи`.
- После выбора проекта:
  - у UCN появляется `Объекты`;
  - у любого проекта появляется `Отчеты`;
  - `Справочники` в верхнем меню видит только `admin`.
- Смена проекта идёт через:
  - ссылку `К выбору проектов`;
  - dropdown-пункт `Сменить большой проект`.

## Проекты и модули

| Название | Код | `module_key` | Статус |
|---|---|---|---|
| `УЦН 2.0 2026 год` | `ucn-2026` | `ucn_sites_v1` | рабочий |
| `ТСПУ` | `tspu` | `placeholder` | контейнер |
| `Стройка ЦОД` | `dc-build` | `placeholder` | контейнер |

## RBAC коротко

| Роль | Проекты | Объекты | Отчеты | Excel | Sync | Логи |
|---|---|---|---|---|---|---|
| `admin` | все | полный доступ | все проектные отчёты | import/export | ✅ | ✅ |
| `manager` | назначенные | create/read/update | отчёты доступного проекта | import/export | ✅ | ❌ |
| `viewer` | назначенные | read-only | отчёты доступного проекта | export | ❌ | ❌ |
| `contractor` | проекты по своим объектам | только свои объекты, ограниченный update | только агрегаты по своим объектам | только свой export | ❌ | ❌ |

## API, который сейчас особенно важен

```text
POST  /api/v1/auth/login
GET   /api/v1/auth/me
PATCH /api/v1/auth/me

GET    /api/v1/projects/?active_only=true|false
GET    /api/v1/projects/{project_id}
POST   /api/v1/projects/
PATCH  /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}

GET    /api/v1/users/
POST   /api/v1/users/
PATCH  /api/v1/users/{id}
DELETE /api/v1/users/{id}

GET    /api/v1/sites/?project_id=...
POST   /api/v1/sites/
GET    /api/v1/sites/{id}
PATCH  /api/v1/sites/{id}
DELETE /api/v1/sites/{id}

GET /api/v1/reports/?project_id=...
GET /api/v1/reports/{report_key}?project_id=...

GET  /api/v1/excel/export?project_id=...
POST /api/v1/excel/import?project_id=...

POST /api/v1/sync
GET  /api/v1/sync/history/{site_id}
GET  /api/v1/sync/history-fields
POST /api/v1/sync/rollback
POST /api/v1/sync/rollback-entry
POST /api/v1/sync/rollback-batch
GET  /api/v1/sync/columns

GET /api/health
```

## Важные инварианты

- `GET /api/v1/sites/` всегда требует `project_id`
- `POST /api/v1/sites/` требует `project_id` в body
- `GET /api/v1/reports/` требует `project_id`
- Для placeholder-проекта `/api/v1/reports/` возвращает пустой список
- Detail-route отчёта для неподдерживаемого проекта возвращает `404`
- `contractor` в reports API видит только агрегаты по своим объектам
- Excel import/export работают только для `ucn_sites_v1`
- Import/sync по неизвестному `ID объекта` не создают новый объект
- Ключ sync: `sites.site_id`, Excel-колонка `ID объекта`

## Отчеты

Для UCN сейчас есть 2 отчёта:

- `status_overview`
  - статусный профиль проекта;
  - распределение по статусам;
  - региональная сводка и просрочка.
- `milestone_readiness`
  - готовность ключевых UCN-вех;
  - риск-объекты;
  - агрегаты по milestone-полям шаблона.

Один и тот же payload используется для:

- web-визуала;
- `PDF`;
- `PPT`;
- `Excel`.

Важно:

- Excel-выгрузка отчётов не связана с `sync_template.xlsm`;
- VBA/XLSM-контур нужен только для sync/export объектов, не для reports.

## Тесты

Актуально на 2026-04-21:

- полный backend-suite на VPS: `91/91`
- frontend unit на VPS: `55/55`
- e2e через Playwright Docker и текущую `playwright.config.js`: `69 passed`, `1 skipped`, `1 flaky`
- текущий инвентарь в коде:
  - backend: `91`
  - frontend unit: `55`
  - e2e spec files: `7`

Известные ограничения текущего серверного тестового контура:

- канонический backend-runner на VPS сейчас: `PYTHONPATH=~/network-tracker/backend /tmp/rts-web-codex-venv/bin/pytest -q`
- `~/network-tracker/Tests/backend/.venv` на сервере по-прежнему разъехался по Python / `pydantic_core`
- `Tests/e2e/tests/reports.spec.js` есть в репозитории, но в текущем `playwright.config.js` не входит в `testMatch` ни одного project, поэтому не участвует в подтверждённом e2e-прогоне

## Куда смотреть в коде

- `frontend/js/utils.js`
- `frontend/js/api.js`
- `frontend/reports.html`
- `backend/app/api/v1/reports.py`
- `backend/app/services/reports.py`
- `backend/app/schemas/report.py`
- `backend/app/services/excel.py`
- `backend/app/services/sync.py`
- `backend/app/core/columns.py`
- `Tests/backend/test_reports.py`
- `Tests/e2e/tests/reports.spec.js`
- `Tests/README.md`
