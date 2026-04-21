# RTKS Tracker — контекст проекта

Обновлено: 2026-04-21

## Что это за система сейчас
- Веб-приложение для трекинга строительства объектов мобильной сети.
- Текущий веб-брендинг: `RTKS Tracker`.
- Репозиторий и папка на VPS исторически остались со старым неймингом: `RTS_Web` и `~/network-tracker`.
- Архитектура с 2026-04-10 двухуровневая:
  - верхний уровень: выбор крупного проекта;
  - нижний уровень: внутренний модуль конкретного проекта.
- На сегодня полностью реализован только один внутренний модуль:
  - `УЦН 2.0 2026 год` с объектами `sites`, Excel import/export и XLSM sync.
- С 2026-04-18 в системе появился общий проектный раздел `Отчеты`:
  - он существует для всех больших проектов;
  - для placeholder-проектов сейчас показывает empty state;
  - для `УЦН 2.0 2026 год` уже реализованы 2 UCN-отчёта с web-визуалом и выгрузками `PDF`, `PPT`, `Excel`.
- С 2026-04-20 в backend закрыт первый слой инфраструктурного cleanup:
  - `get_db` больше не делает скрытый `commit`;
  - write-endpoints коммитят явно;
  - чтение `/sites`, `/regions`, `/contractors` больше не триггерит write-sync справочников;
  - синхронизация регионов перенесена на write-path (`sites`, Excel import, XLSM sync);
  - `is_active` у `regions` и `contractors` больше не перетирается автоматически.
- В тот же день в `backend/app/services/reports.py` исправлено приведение naive/aware `datetime`, чтобы полный backend-regression корректно проходил и на сервере, и на SQLite-тестах.
- С 2026-04-21 в backend закрыт этап `2A` по Excel auth hardening:
  - `GET /api/v1/excel/export` встраивает отдельный JWT `token_type=excel_sync`;
  - токен несёт `project_id` и, при наличии, `contractor_id`;
  - обычные browser-endpoints принимают только `access` token;
  - `/sync` и `/sync/columns` принимают `excel_sync`, но только в рамках зашитого проекта;
  - `/sync` отвергает строки с `site_id`, относящимся к другому проекту.
- С 2026-04-13 UCN-модуль переведён на новый серверный Excel-шаблон:
  - старый UCN-набор на проде очищен;
  - в базу загружено `172` строк нового шаблона;
  - для стартовой загрузки использованы тестовые `ID объекта`
    `UCN-2026-0001 ... UCN-2026-0172`.
- Остальные крупные проекты пока существуют как архитектурные контейнеры:
  - `ТСПУ`
  - `Стройка ЦОД`
- Важно: формат данных, шаблонов Excel и внутренних экранов у других проектов в будущем может быть другим. Текущая реализация специально делает под это архитектурный задел, а не жёстко размножает UCN-логику на все проекты.

## Технологический стек
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic
- **Database:** PostgreSQL 16
- **Excel:** openpyxl (импорт и служебные операции), xlsxwriter + `vbaProject.bin` (экспорт)
- **Auth:** JWT (`python-jose`) + `bcrypt==4.0.1`
- **Frontend:** HTML/JS + Bootstrap 5, без frontend framework
- **Инфраструктура:** Docker Compose, Nginx
- **Деплой:** `rsync` с локальной машины на VPS, затем `docker compose restart ...`

## Прод и инфраструктура

### VPS
- Хостинг: приватный VPS-провайдер
- OS: Ubuntu 24.04
- Hostname: `<private-hostname>`
- IP: `<private-ip>`
- SSH: `ssh <vps-alias>`
- Пользователь: `<deploy-user>`
- Root по SSH запрещён
- Папка проекта на сервере: `/home/<deploy-user>/network-tracker/`

### Ограничения сети на VPS
- GitHub с VPS недоступен по SSH и HTTPS.
- Поэтому `git pull` на VPS не используется.
- Деплой делается только через `rsync` с локальной машины.
- В Docker-контейнерах внешний DNS ограничен, поэтому сборка использует `network: host`.

### Полезные URL
- Прод: `https://<public-base-url>/`
- API health: `https://<public-base-url>/api/health`
- Swagger: `https://<public-base-url>/docs`

### Реквизиты
- Bootstrap-учётные данные не должны храниться в репозитории.
- Реальные admin логин/пароль должны жить только в deployment secrets / password manager.

## GitHub и workflow
- GitHub repo: текущий репозиторий
- SSH remote: `git@github.com:<owner>/<repo>.git`
- Push с локальной машины работает.
- Pull на VPS не работает.
- Нормальный workflow:
  1. правки локально;
  2. `git commit`;
  3. `git push origin main`;
  4. `rsync` на VPS;
  5. `docker compose restart backend` и/или `docker compose restart nginx`.

### Важный git-контекст на 2026-04-13
- Перед текущим обновлением документации локальный `main` и `origin/main` были синхронизированы на коммите `a02652a`.
- В проект добавлен каталог `Tests/` с тестовым контуром.
- Если новый чат будет работать с тестами, нельзя бездумно удалять или пересоздавать `Tests/`.
- Внутри `Tests/` есть локальные артефакты, которые не стоит коммитить как продуктовый код:
  - `Tests/backend/.venv/`
  - `Tests/.claude/`
  - `Tests/frontend/node_modules/`

## Текущая продуктовая архитектура

### 1. Верхний уровень: крупные проекты
- В БД есть таблица `projects`.
- Для пользователей `manager` и `viewer` доступ к проектам задаётся явно через `user_projects`.
- Для пользователей `contractor` проекты определяются не через `user_projects`, а автоматически по объектам их подрядчика.
- Для `admin` доступны все проекты.

### 2. Нижний уровень: внутренний модуль проекта
- Поле `projects.module_key` определяет, какой UI и какой backend-сценарий подключать.
- Поддерживаемые значения сейчас:
  - `ucn_sites_v1` — полноценный модуль объектов;
  - `placeholder` — плейсхолдер-страница без внутреннего доменного функционала.

### 3. Привязка объектов к проектам
- В `sites` добавлено поле `project_id`.
- Все существующие объекты были миграцией отнесены к проекту `УЦН 2.0 2026 год`.
- Поэтому текущий рабочий набор объектов теперь не “в корне системы”, а внутри одного большого проекта.

## Текущие проекты в системе

| Название | Код | module_key | template_key | Назначение |
| --- | --- | --- | --- | --- |
| `УЦН 2.0 2026 год` | `ucn-2026` | `ucn_sites_v1` | `sync_template.xlsm` | Текущий рабочий модуль объектов, Excel import/export, XLSM sync |
| `ТСПУ` | `tspu` | `placeholder` | `NULL` | Архитектурный контейнер |
| `Стройка ЦОД` | `dc-build` | `placeholder` | `NULL` | Архитектурный контейнер |

### Что делает миграция `005_add_projects`
- создаёт `projects`;
- создаёт `user_projects`;
- добавляет `sites.project_id`;
- сидирует 3 проекта;
- привязывает все существующие `sites` к `ucn-2026`;
- назначает существующим `manager` и `viewer` доступ к `ucn-2026`.

## Текущий UX и маршруты фронтенда

### Общий сценарий входа
1. Пользователь открывает `/login.html`.
2. После успешного `POST /api/v1/auth/login` браузер сохраняет JWT в `localStorage.token`.
3. Затем всегда редирект на `/index.html`.
4. `/index.html` — это экран выбора большого проекта плитками.
5. Только после выбора большого проекта пользователь попадает в рабочее пространство.

### Важная текущая идеология меню
- На верхнем уровне больше нет отдельного рабочего пункта меню `Проекты`.
- Для `admin` на `/index.html` в верхнем меню сразу видны `Пользователи` и `Логи`.
- `Объекты` появляются только после выбора проекта.
- `Отчеты` появляются только после выбора проекта и доступны всем авторизованным ролям в рамках доступного проекта.
- `Справочники` в верхнем меню показываются только `admin` и только внутри выбранного проекта.
- Для `manager`, `viewer` и `contractor` экран выбора проекта не показывает рабочие разделы.
- Админ управляет проектами:
  - кнопкой `Управление проектами` на `/index.html`;
  - пунктом в пользовательском dropdown на внутренних страницах.
- У менеджеров отдельного меню `Проекты` тоже нет.
- Для смены проекта используется:
  - ссылка `К выбору проектов`;
  - пункт dropdown `Сменить большой проект`.

### Страницы
- `frontend/login.html`
  - форма логина;
  - если токен уже есть, сразу редиректит на `/index.html`.
- `frontend/index.html`
  - главный экран после логина;
  - показывает плитки доступных проектов;
  - при загрузке всегда очищает `localStorage.current_project`;
  - admin дополнительно видит кнопку `Управление проектами`.
- `frontend/sites.html`
  - бывший старый `index.html` со списком объектов;
  - теперь это рабочее пространство только для проекта с `module_key = ucn_sites_v1`;
  - URL: `/sites.html?project_id=<id>`.
- `frontend/site.html`
  - карточка одного объекта;
  - URL: `/site.html?id=<site_id>&project_id=<project_id>`;
  - если `project_id` не передан, страница пытается взять его из `localStorage.current_project`.
- `frontend/project.html`
  - страница-плейсхолдер для проектов без реализованного модуля;
  - URL: `/project.html?id=<project_id>`.
- `frontend/reports.html`
  - общий проектный раздел отчетов;
  - URL: `/reports.html?project_id=<project_id>`;
  - для placeholder-проектов показывает empty state;
  - для `ucn_sites_v1` строит web-отчёт и даёт скачать `PDF`, `PPT`, `Excel` с агрегированными данными.
- `frontend/projects.html`
  - admin-only страница CRUD для крупных проектов.
  - create/edit/delete модалки открываются через общие helpers из `frontend/js/utils.js`.
  - после успешного create/update/delete страница делает controlled reload с flash-сообщением.
- `frontend/users.html`
  - admin-only страница пользователей;
  - именно тут задаются `project_ids` для `manager` и `viewer`.
  - admin не редактирует и не удаляет самого себя на этой странице; для этого используется `/profile.html`.
  - после успешного create/update/delete страница делает controlled reload с flash-сообщением.
- `frontend/profile.html`
  - страница профиля текущего пользователя;
  - позволяет менять собственный логин и пароль;
  - доступна всем авторизованным ролям из пользовательского dropdown.
  - справа отдельно показывает `Логин` и `Полное имя` и сразу обновляется после смены логина.
- `frontend/logs.html`
  - admin-only.
- `frontend/regions.html`
  - справочник регионов;
  - доступен из UI для `admin` и `manager`;
  - на backend справочник глобальный, а не проектный.
  - в верхнем navbar ссылка на раздел показывается только `admin`.
- `frontend/contractors.html`
  - справочник подрядчиков;
  - доступен из UI для `admin` и `manager`;
  - на backend справочник глобальный, а не проектный.
  - в верхнем navbar ссылка на раздел показывается только `admin`.

### Локальное состояние в браузере
- `localStorage.token` — JWT.
- `localStorage.user` — объект текущего пользователя.
- `localStorage.current_project` — выбранный большой проект.
- `logout()` удаляет все три значения.
- `index.html` при открытии очищает `current_project`, чтобы экран выбора был “чистым”.

### Логика маршрутизации по проекту
- `getProjectRoute(project)`:
  - если `module_key === "ucn_sites_v1"` → `/sites.html?project_id=<id>`;
  - иначе → `/project.html?id=<id>`.
- `getProjectReportsRoute(project)`:
  - для любого выбранного большого проекта → `/reports.html?project_id=<id>`.
- При клике по плитке `openProject(project)`:
  - запоминает проект в `localStorage.current_project`;
  - переводит пользователя на маршрут проекта.

## RBAC и доступ по проектам

| Роль | Доступ к проектам | Как определяется доступ | Объекты `sites` | Отчеты | Пользователи | Крупные проекты | Справочники | Excel import | Excel export | Sync API | Логи |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `admin` | все проекты | без ограничений | полный доступ | все проектные отчёты | полный доступ | полный доступ | полный доступ | ✅ | ✅ | ✅ | ✅ |
| `manager` | только назначенные проекты | `user_projects` | create/read/update | отчёты доступного проекта | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |
| `viewer` | только назначенные проекты | `user_projects` | только чтение | отчёты доступного проекта | ❌ | ❌ | ❌ в UI | ❌ | ✅ | ❌ | ❌ |
| `contractor` | только проекты, где есть его объекты | по `sites.contractor_id` | только свои объекты, ограниченный update | только агрегаты по своим объектам | ❌ | ❌ | ❌ | ❌ | только свои | ❌ | ❌ |

### Важные детали прав
- `manager` и `viewer` получают проекты только через `user_projects`.
- `admin` не использует `user_projects`.
- `contractor` не использует `user_projects`.
- `admin` может менять логин и пароль себе и любому пользователю через user CRUD.
- Любой авторизованный пользователь может менять логин и пароль только себе через `PATCH /api/v1/auth/me`.
- `contractor` может менять только:
  - `status`
  - `actual_start`
  - `actual_end`
  - `notes`
- История изменений объекта (`GET /api/v1/sync/history/{site_id}`) сейчас доступна ролям `admin` и `manager`, потому что endpoint использует `require_manager`.
- Rollback endpoints доступны только `admin`.

## Структура проекта
```text
RTS_Web/
├── AGENTS.md
├── HANDOFF.md
├── docker-compose.yml
├── nginx/
│   └── nginx.conf
├── backend/
│   ├── alembic/
│   │   └── versions/
│   │       ├── 08554a11e51f_initial.py
│   │       ├── 003_add_site_history.py
│   │       ├── 004_add_site_ni_fields.py
│   │       ├── 005_add_projects.py
│   │       └── 006_add_ucn_template_v2_fields.py
│   ├── load_ucn_template_data.py
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── users.py
│   │   │   ├── sites.py
│   │   │   ├── reports.py
│   │   │   ├── excel.py
│   │   │   ├── sync.py
│   │   │   ├── logs.py
│   │   │   ├── regions.py
│   │   │   └── contractors.py
│   │   ├── crud/
│   │   │   ├── project.py
│   │   │   ├── user.py
│   │   │   ├── site.py
│   │   │   ├── site_history.py
│   │   │   └── log.py
│   │   ├── models/
│   │   │   ├── project.py
│   │   │   ├── user.py
│   │   │   ├── site.py
│   │   │   ├── site_history.py
│   │   │   ├── region.py
│   │   │   ├── contractor.py
│   │   │   └── log.py
│   │   ├── schemas/
│   │   │   ├── project.py
│   │   │   ├── report.py
│   │   │   ├── user.py
│   │   │   ├── site.py
│   │   │   ├── sync.py
│   │   │   └── log.py
│   │   ├── services/
│   │   │   ├── auth.py
│   │   │   ├── excel.py
│   │   │   ├── reports.py
│   │   │   ├── sync.py
│   │   │   ├── ucn_template.py
│   │   │   └── reference_sync.py
│   │   └── core/
│   │       └── columns.py
│   └── templates/
│       └── sync_template.xlsm
└── frontend/
    ├── login.html
    ├── index.html
    ├── sites.html
    ├── site.html
    ├── project.html
    ├── reports.html
    ├── projects.html
    ├── users.html
    ├── logs.html
    ├── regions.html
    ├── contractors.html
    ├── js/
    │   ├── api.js
    │   └── utils.js
    └── css/
        └── style.css
```

## Backend API: текущее состояние

### Auth
```text
POST /api/v1/auth/login
GET  /api/v1/auth/me
PATCH /api/v1/auth/me
```

### Projects
```text
GET    /api/v1/projects/?active_only=true|false
GET    /api/v1/projects/{project_id}
POST   /api/v1/projects/           # admin only
PATCH  /api/v1/projects/{project_id}  # admin only
DELETE /api/v1/projects/{project_id}  # admin only, только если у проекта нет объектов
```

### Users
```text
GET    /api/v1/users/
POST   /api/v1/users/
GET    /api/v1/users/{id}
PATCH  /api/v1/users/{id}
DELETE /api/v1/users/{id}
```

### Sites
```text
GET    /api/v1/sites/?project_id=...&region_id=...&status=...&contractor_id=...&search=...&page=...&page_size=...
POST   /api/v1/sites/
GET    /api/v1/sites/{id}
PATCH  /api/v1/sites/{id}
DELETE /api/v1/sites/{id}
```

### Reports
```text
GET /api/v1/reports/?project_id=...
GET /api/v1/reports/{report_key}?project_id=...
```

### Excel
```text
GET  /api/v1/excel/export?project_id=...
POST /api/v1/excel/import?project_id=...
```

### Directories and logs
```text
GET|POST|PATCH|DELETE /api/v1/regions/...
GET|POST|PATCH|DELETE /api/v1/contractors/...
GET /api/v1/logs/
```

### Sync / history / rollback
```text
POST /api/v1/sync
GET  /api/v1/sync/history/{site_id}
GET  /api/v1/sync/history-fields
POST /api/v1/sync/rollback
POST /api/v1/sync/rollback-entry
POST /api/v1/sync/rollback-batch
GET  /api/v1/sync/columns
```

### Health
```text
GET /api/health
```

## Важные API-инварианты
- `GET /api/v1/projects/` по умолчанию возвращает только активные проекты.
- `/index.html` использует `active_only=true`.
- `/projects.html` использует `active_only=false`, чтобы admin видел и неактивные проекты.
- `GET /api/v1/projects/{id}`:
  - для admin может отдавать и неактивный проект;
  - для остальных — только если проект доступен пользователю.
- `GET /api/v1/sites/` требует `project_id`.
- `POST /api/v1/sites/` требует `project_id` в body.
- `GET /api/v1/reports/` требует `project_id` и возвращает список отчётов, доступных для выбранного большого проекта.
- Для placeholder-проектов `/api/v1/reports/` возвращает пустой список, а detail-route по ключу отчёта отдаёт `404`.
- `contractor` в `/api/v1/reports/{report_key}` видит агрегаты только по своим объектам.
- `GET /api/v1/excel/export` и `POST /api/v1/excel/import` работают только для проектов с `module_key = "ucn_sites_v1"`.
- Excel import и XLSM sync обновляют только существующие объекты; неизвестный `ID объекта` возвращается как ошибка и не создаёт новый `sites`-record.
- `POST /api/v1/sync` принимает `project_id`, но если его нет, backend берёт первый проект с `module_key = "ucn_sites_v1"`.
- Сейчас это фактически означает fallback на `УЦН 2.0 2026 год`.

## База данных — текущее состояние
- Текущий Alembic head: `006_add_ucn_template_v2_fields`
- Важные таблицы:
  - `users`
  - `projects`
  - `user_projects`
  - `sites`
  - `site_history`
  - `action_logs`
  - `regions`
  - `contractors`
- Важные поля:
  - `projects.module_key`
  - `projects.template_key`
  - `projects.is_active`
  - `projects.sort_order`
  - `sites.project_id`
  - `sites.site_id` — sync key, соответствует Excel-колонке `ID объекта`
  - новые UCN template-specific поля в `sites`:
    - `macroregion`
    - `regional_branch`
    - `district`
    - `rural_settlement`
    - `ams_permit_plan/fact`
    - `igi_*`
    - `foundation_pour_*`
    - `ams_receipt_*`
    - `rd_release`
    - `smr_order_*`
    - `equipment_receipt_*`
    - `pnr_*`
- На проде при последней проверке:
  - проектов: 3
  - объектов UCN: 172

## Sites / UCN-модуль
- Текущий рабочий доменный модуль — `ucn_sites_v1`.
- С 2026-04-13 он работает на новом плоском UCN-шаблоне сервера.
- Реестр колонок шаблона хранится в `backend/app/core/columns.py`.
- Excel import/export/sync используют один и тот же набор колонок и ключ `ID объекта`.
- Новые объекты через Excel import/XLSM sync больше не создаются; для неизвестного `ID объекта` backend возвращает ошибку.
- Базовые поля `Site` (`name`, `address`, `status`, `region`) достраиваются из шаблонных данных через `apply_template_derivations`.
- `sites.html` показывает:
  - header проекта;
  - фильтры;
  - таблицу объектов;
  - экспорт;
  - импорт;
  - создание объекта.
- Видимость действий:
  - `admin`, `manager`: видят `Добавить`, `Импорт`, `Экспорт`;
  - `viewer`: только просмотр и экспорт;
  - `contractor`: просмотр своих объектов и экспорт своих данных.
- `site.html`:
  - показывает карточку объекта;
  - умеет редактирование по роли;
  - для admin показывает `История`.

## Reports / проектный раздел
- `reports.html` существует для всех больших проектов, а не только для UCN.
- Для placeholder-проектов раздел сейчас показывает empty state и служит архитектурным контейнером под будущие проектные отчёты.
- Для `УЦН 2.0 2026 год` на 2026-04-18 реализованы 2 отчёта:
  - `status_overview` — статусный профиль проекта с региональной сводкой и просрочкой;
  - `milestone_readiness` — готовность ключевых UCN-вех.
- Один и тот же агрегированный payload используется для:
  - web-визуала;
  - выгрузки `PDF`;
  - выгрузки `PPT`;
  - выгрузки `Excel`.
- Excel-выгрузка отчетов не использует `sync_template.xlsm` и не связана с XLSM sync-контейнером.

## История изменений и rollback
- История пишется из трёх источников:
  - web create/update;
  - Excel import;
  - XLSM sync.
- Rollback покрывает весь tracked-набор полей `Site`, а не только старые поля sync.
- UI истории в `frontend/site.html` умеет:
  - смотреть историю батчами;
  - rollback одного поля;
  - rollback батча;
  - rollback объекта к моменту времени.

## Справочники
- `regions` и `contractors` сейчас глобальные, не проектные.
- GET-эндпоинты `/sites`, `/regions`, `/contractors` больше не выполняют write-sync справочников.
- Для `regions`:
  - источник истины для автосоздания и привязки по-прежнему `sites.region`;
  - missing regions создаются автоматически, а `region_id` проставляется только на write-path:
    - web create/update/delete объекта;
    - Excel import;
    - XLSM sync.
  - `Region.is_active` теперь ручное поле и не пересчитывается автоматически.
- Для `contractors`:
  - автосоздания по тексту нет;
  - `Contractor.is_active` теперь ручное поле и не пересчитывается автоматически.

## XLSM / VBA sync
- `GET /api/v1/excel/export?project_id=...` отдаёт `.xlsm`.
- Экспорт работает только для `ucn_sites_v1`.
- Backend использует `backend/templates/sync_template.xlsm` как контейнер VBA.
- Изменения в `vba/*.bas` и `vba/*.cls` сами по себе не попадают в экспорт, пока вручную не обновлён `backend/templates/sync_template.xlsm`.
- Экспортируемый файл содержит:
  - лист `Sync`;
  - лист `Data`;
  - скрытые листы `_Config`, `_DirtyTracker`.
- Лист `Data` в экспортируемом файле защищён: пользователь может менять значения ячеек, но не может вставлять или удалять строки.
- В `_Config` сохраняются:
  - `last_sync_at`
  - `auth_token` — scoped token `excel_sync` для `/sync` и `/sync/columns`
  - `username`
  - `project_id`
- Кнопка `SyncNow` создаётся backend автоматически.

### Контракт sync
- Клиент отправляет:
```json
{
  "last_sync_at": "2026-04-06T10:00:00Z",
  "project_id": 1,
  "rows": [{"site_id": "UCN-2026-0001", "macroregion": "Центр"}],
  "client_version": 1
}
```
- Сервер:
  - применяет изменения;
  - пишет `site_history`;
  - возвращает все строки, изменённые после `last_sync_at`, в пределах проекта.

### Важные ограничения sync
- `site_id` — ключ sync и соответствует Excel-колонке `ID объекта`.
- Номер строки `№ п/п` не является ключом и не должен использоваться как идентификатор объекта.
- Import/export/sync используют один и тот же реестр колонок из `backend/app/core/columns.py`.
- В XLSM-книге нельзя добавлять и удалять строки на листе `Data`; поддерживается только редактирование значений существующих строк.
- Производные поля `name`, `address`, `status` пересчитываются одинаково для web, Excel import и sync.
- Backend принимает ISO даты с timezone:
  - `...Z`
  - `...+00:00`
- Новый XLSM export 2026-04-21 встраивает `excel_sync` token, привязанный к `project_id`; `/sync` не принимает его для другого проекта.
- Текущий VBA runtime ориентирован на Windows Excel.

## Важные детали реализации
- `Project.is_configured` = `module_key != "placeholder"`.
- `Project.code` нормализуется:
  - trim;
  - lowercase;
  - пробелы и `_` меняются на `-`.
- Проект нельзя удалить, если в нём есть `sites`.
- `manager` и `viewer` получают/теряют доступ к проектам только через `project_ids` в user CRUD.
- Если роль пользователя меняется с `manager/viewer` на другую, его `user.projects` очищаются.
- `index.html` очищает `current_project`, поэтому direct back-to-root всегда работает как “смена проекта”.
- Navbar dropdowns в `frontend/js/utils.js` используют собственную логику toggles, а не Bootstrap dropdown plugin, потому что браузерное поведение было нестабильным.
- Для `admin` navbar на `/index.html` показывает `Пользователи` и `Логи`.
- Navbar внутри проекта показывает рабочие разделы, но больше не содержит отдельного пункта `Проекты`.
- `Справочники` в верхнем navbar показываются только `admin`; у `manager` верхней ссылки на справочники нет.
- `users.html`, `projects.html` и `site.html` после успешного save используют controlled reload + flash message, чтобы интерфейс гарантированно перечитывал данные и выходил из режима редактирования.
- `users.html` блокирует редактирование и удаление самого admin на странице пользователей; собственные логин и пароль меняются через `/profile.html`.

## Что уже проверено на проде
- перед миграцией создан бэкап БД:
  - `/home/<deploy-user>/backups/rtks_prod_YYYYMMDD_HHMMSS.sql`
- миграция `006_add_ucn_template_v2_fields` применена на VPS;
- старые UCN-объекты удалены: `651`;
- из нового шаблона импортировано `172` объекта;
- `GET /api/health` возвращает `{"status":"ok"}`
- главная страница — это экран плиток больших проектов;
- web title: `RTKS Tracker — Проекты`;
- есть 3 проекта:
  - `УЦН 2.0 2026 год`
  - `ТСПУ`
  - `Стройка ЦОД`
- для UCN API `/api/v1/sites?project_id=1...` работает;
- новый проектный маршрут `/reports.html?project_id=1` на проде отвечает `200`;
- первые `ID объекта` на проде:
  - `UCN-2026-0001`
  - `UCN-2026-0002`
  - `UCN-2026-0003`
  - `UCN-2026-0004`
  - `UCN-2026-0005`
- новая навигация без верхнего пункта `Проекты` задеплоена 2026-04-10.
- фронтенд-фиксы 2026-04-14/15 уже выложены и проверены ручным smoke на проде:
  - пользовательский dropdown стабильно открывается в Chrome, Edge и Яндекс Браузере;
  - для `manager` верхнее меню не показывает `Справочники`;
  - для `admin` на `/index.html` видны `Пользователи` и `Логи`, а после выбора проекта добавляются `Объекты` и `Справочники`;
  - `frontend/profile.html` показывает отдельно `Логин` и `Полное имя`;
  - `frontend/site.html` после сохранения гарантированно выходит из режима редактирования;
  - `frontend/users.html` и `frontend/projects.html` открывают edit-модалки и после save/delete обновляют список через reload.
- фиксы истории 2026-04-17 тоже уже выложены и вручную проверены на проде:
  - в `backend/app/api/v1/sync.py` route `/api/v1/sync/history-fields` больше не перехватывается `/api/v1/sync/history/{site_id}`;
  - `frontend/site.html` открывает history/delete модалки через общие modal helpers;
  - раскрытие групп истории в `frontend/site.html` больше не зависит от Bootstrap `collapse`;
  - история подтверждённо открывается и раскрывается для `UCN-2026-0003` и `UCN-2026-0015`.
- backend cleanup и серверный regression 2026-04-20 тоже уже подтверждены:
  - `get_db` больше не делает скрытый `commit`;
  - чтение `/sites`, `/regions`, `/contractors` больше не пишет в БД через sync справочников;
  - `Region.is_active` и `Contractor.is_active` больше не перетираются автоматически;
  - `backend/app/services/reports.py` нормализует naive/aware `datetime`;
  - полный серверный прогон: backend `84 passed`, frontend unit `55 passed`, e2e `69 passed`, `1 skipped`, `1 flaky` через retry-green прогон.
- Excel auth hardening 2026-04-21 тоже уже задеплоен и подтверждён на проде:
  - `GET /api/v1/excel/export` встраивает `excel_sync` token c `project_id`;
  - обычные browser-endpoints принимают только `access` token;
  - `/sync` и `/sync/columns` принимают scoped `excel_sync` token;
  - `/sync` отвергает project mismatch и строки с `site_id` из другого проекта;
  - `GET /api/health` после деплоя возвращает `{"status":"ok"}`;
  - полный серверный прогон backend 2026-04-21: `91 passed`.

## Автотестовый контекст

### Тестовый контур уже существует в проекте
- В проекте есть папка `Tests/`.
- Это текущий тестовый каркас проекта.
- Структура сейчас такая:
  - `Tests/backend/` — Python API-тесты на `pytest + httpx + aiosqlite`
  - `Tests/frontend/` — JS unit-тесты на `Jest + jsdom`
  - `Tests/README.md` — основная инструкция по запуску
- Важно:
  - `Tests/backend/.venv/` и `Tests/.claude/` — локальные служебные каталоги, не продуктовый код.
  - `Tests/frontend/node_modules/` — тоже локальный каталог, не продуктовый код.

### Что уже есть в `Tests/`
- Backend:
  - `conftest.py`
  - `pytest.ini`
  - `requirements-test.txt`
  - `test_auth.py`
  - `test_contractors.py`
  - `test_projects.py`
  - `test_regions.py`
  - `test_reports.py`
  - `test_sites.py`
  - `test_excel.py`
  - `test_sync.py`
- Frontend:
  - `package.json`
  - `jest.setup.js`
  - `test_api.test.js`
  - `test_utils.test.js`
- E2E:
  - `admin.spec.js`
  - `auth.spec.js`
  - `directories.spec.js`
  - `projects.spec.js`
  - `reports.spec.js`
  - `site_edit.spec.js`
  - `sites.spec.js`

### Как запускать тестовый контур
- Backend:
```bash
cd "/Users/vicmb/Yandex.Disk.localized/РТК Сервис/RTS_Web/Tests/backend"
pip install -r ../../backend/requirements.txt -r requirements-test.txt
pytest -v
```
- Frontend:
```bash
cd "/Users/vicmb/Yandex.Disk.localized/РТК Сервис/RTS_Web/Tests/frontend"
npm install
npm test
```
- Для Codex/локального агента канонический подтверждающий прогон считать **серверным**, на VPS.
- Причина: локальная системная `python3` на этой машине может быть ниже `3.12`, поэтому backend-тесты и само приложение могут не стартовать корректно.
- Для незакоммиченных правок безопаснее делать временную копию проекта на VPS и гонять тесты там, а не `rsync`-ить проверочную правку прямо в `~/network-tracker`.
- Это важно, потому что на VPS `backend` примонтирован как `./backend:/app` и работает с `uvicorn --reload`, то есть подмена файлов в `~/network-tracker/backend` может сразу затронуть живой backend.

### Что уже покрывает `Tests/`
- Backend:
  - auth;
  - явные commit boundaries без скрытого auto-commit в dependency;
  - projects;
  - regions и contractors;
  - reports;
  - sites;
  - excel;
  - импорт нового UCN-шаблона по `ID объекта` без создания новых объектов;
  - отсутствие write-on-GET для `/sites`, `/regions`, `/contractors`;
  - sync/history/rollback.
- Frontend:
  - `utils.js`
  - `api.js`
  - маршрутизация по `module_key`;
  - navbar;
  - badges;
  - project routing helpers;
  - project reports helpers.
- E2E:
  - auth flow и logout;
  - project selection;
  - UCN module;
  - directories;
  - site card/edit/history;
  - базовые admin pages.

### Актуальный статус тестов на 2026-04-21
- Подтверждённый полный backend-прогон на VPS: `91/91` зелёных тестов.
- Разбивка backend-набора:
  - `test_auth.py` — 13
  - `test_contractors.py` — 2
  - `test_excel.py` — 10
  - `test_projects.py` — 16
  - `test_regions.py` — 2
  - `test_reports.py` — 6
  - `test_sites.py` — 19
  - `test_sync.py` — 23
- Подтверждённый frontend unit-прогон на VPS: `55/55`.
- Подтверждённый E2E-прогон на VPS через Playwright Docker и текущую `playwright.config.js`: `69 passed`, `1 skipped`, `1 flaky`.
- Текущий инвентарь в коде:
  - backend: `91`;
  - frontend unit: `55`;
  - e2e spec files: `7`.
- Канонический backend-runner на VPS сейчас:
  - `PYTHONPATH=~/network-tracker/backend /tmp/rts-web-codex-venv/bin/pytest -q`
- `~/network-tracker/Tests/backend/.venv` на сервере по-прежнему разъехался по Python/pydantic_core и не считается каноническим runner'ом.
- Для E2E канонический серверный прогон сейчас делается через Docker-образ Playwright, а не через локальный host Chromium.
- Важно: `Tests/e2e/tests/reports.spec.js` есть в репозитории, но в текущем `Tests/e2e/playwright.config.js` не входит в `testMatch` ни одного project, поэтому не участвует в подтверждённом прогоне `69 passed, 1 skipped, 1 flaky`.

### Ограничения текущего тестового задела
- Полноценного E2E покрытия для всех внутренних страниц всё ещё нет.
- `checkAuth()`, `sites.html`, `site.html` и сами browser-download assertions для `PDF/PPT/Excel` пока не покрыты полноценно.
- `GET /excel/export` в тестовой среде для UCN может вернуть `500`, если нет `sync_template.xlsm` в ожидаемом месте.
- Тестовая backend-БД использует SQLite, а не PostgreSQL.

### Три зафиксированных test-specific фикса
- В `Tests/backend/conftest.py` включён `PRAGMA foreign_keys=ON`.
- В `Tests/backend/test_sites.py` проверка contractor list использует `item["contractor"]["id"]`, а не `item["contractor_id"]`.
- В `Tests/backend/test_sites.py::test_admin_can_delete_site` перед удалением объекта вручную очищается `site_history` как SQLite-workaround.

### Что особенно важно покрыть тестами
- Auth:
  - успешный логин;
  - редирект на `/index.html`;
  - `PATCH /api/v1/auth/me` для смены собственного логина и пароля;
  - logout очищает token/user/current_project.
- Projects:
  - список доступных проектов по ролям;
  - admin видит управление проектами;
  - manager/viewer видят только назначенные проекты;
  - contractor видит только проекты, где есть его объекты.
- Navigation:
  - `/index.html` показывает плитки;
  - выбор проекта переводит в нужный модуль;
  - на `/index.html` нет рабочего меню;
  - на внутренних страницах нет отдельного верхнего пункта `Проекты`;
  - `/reports.html` открывается из navbar любого выбранного проекта.
- UCN module:
  - `/sites.html?project_id=...` открывается только для доступного проекта;
  - `/site.html` открывает объект из того же проекта;
  - create/import/export требуют `project_id`.
- RBAC:
  - viewer не может создавать/импортировать;
  - contractor не может менять чужой объект;
  - contractor не может менять запрещённые поля;
  - admin-only страницы не открываются обычным ролям.
- Projects CRUD:
  - нельзя создать дубликат `name` или `code`;
  - нельзя удалить проект с объектами;
  - неактивные проекты не видны на `/index.html`, но видны admin на `/projects.html`.
- Sync / history:
  - web edit пишет `site_history`;
  - Excel import пишет `site_history`;
  - sync пишет `site_history`;
  - rollback действительно откатывает tracked-поля.
- Excel:
  - export для UCN возвращает `.xlsm`;
  - export/import для placeholder-проекта возвращают 400;
  - import нового шаблона требует `ID объекта`, обновляет только существующий объект и отвергает новые строки;
  - XLSM sync тоже не создаёт новый объект по неизвестному `ID объекта`.
- Reports:
  - список отчётов зависит от `module_key` большого проекта;
  - placeholder-проект отдаёт пустой reports catalog;
  - contractor видит только свои агрегаты;
  - UCN-отчёты строят `PDF`, `PPT`, `Excel` из одного агрегированного payload.

## Полезные команды
```bash
# Локально: push
cd "/Users/vicmb/Yandex.Disk.localized/РТК Сервис/RTS_Web"
git push origin main

# Локально: деплой кода на VPS
rsync -avz --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' \
  --exclude '.DS_Store' --exclude '.env' --exclude '.Codex' \
  "/Users/vicmb/Yandex.Disk.localized/РТК Сервис/RTS_Web/" \
  <vps-alias>:~/network-tracker/

# Локально: frontend-only деплой
rsync -az --delete frontend/ <vps-alias>:/home/<deploy-user>/network-tracker/frontend/
ssh <vps-alias> "cd ~/network-tracker && docker compose restart nginx"

# VPS: миграции
ssh <vps-alias> "docker exec tracker_backend alembic upgrade head"

# VPS: загрузка нового UCN-шаблона с очисткой старых данных
ssh <vps-alias> "docker exec tracker_backend python load_ucn_template_data.py /app/tmp/ucn_template.xlsx --clear"

# VPS: рестарт backend
ssh <vps-alias> "cd ~/network-tracker && docker compose restart backend"

# VPS: рестарт nginx
ssh <vps-alias> "cd ~/network-tracker && docker compose restart nginx"

# VPS: health
ssh <vps-alias> "curl -s http://127.0.0.1/api/health"

# VPS: статус контейнеров
ssh <vps-alias> "cd ~/network-tracker && docker compose ps"

# VPS: логи backend
ssh <vps-alias> "cd ~/network-tracker && docker compose logs backend --tail=100"

# VPS: backend-тесты
ssh <vps-alias> "cd ~/network-tracker/Tests/backend && PYTHONPATH=~/network-tracker/backend /tmp/rts-web-codex-venv/bin/pytest -q"

# VPS: frontend-тесты
ssh <vps-alias> "cd ~/network-tracker/Tests/frontend && npm test"

# Безопасный серверный прогон незакоммиченных backend-правок из локального Codex
rsync -az --delete --exclude '.git' --exclude 'Tests/backend/.venv' \
  --exclude 'Tests/frontend/node_modules' --exclude 'Tests/.claude' \
  --exclude '__pycache__' --exclude '*.pyc' \
  "/Users/vicmb/Yandex.Disk.localized/РТК Сервис/RTS_Web/" \
  <vps-alias>:/tmp/rts-web-codex-check/
# после копирования использовать на VPS подтверждённый backend runner:
# PYTHONPATH=~/network-tracker/backend /tmp/rts-web-codex-venv/bin/pytest -q

# VPS: reports smoke
ssh <vps-alias> "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/reports.html"
```

## Последние важные коммиты
- `c52ac2e` `Refresh admin lists after save`
- `682f1f8` `Fix admin edit modals for users and projects`
- `13a03cf` `Clarify profile username display`
- `205aadb` `Show admin tools on project selection`
- `f7b35e8` `Fix site edit mode after save`
- `70fbcc4` `Fix manager navbar dropdown behavior`
- `344aba3` `Fix navbar dropdowns and admin modals`
- `46db5c0` `Protect Excel data sheet rows`
- `f73ecee` `Block creating sites through Excel sync`
- `6532cdf` `Refresh handoff with local test context`
- `a02652a` `Expand architecture and testing documentation`
- `08d441a` `Refine project selection navigation flow`
- `21111f8` `Update project handoff documentation`
- `d06df21` `Add project architecture and RTKS branding`
- `e373da1` `Add admin site history and rollback UI`
- `81f43fc` `Expand rollback to all tracked site fields`
- `443ece4` `Accept ISO timezone dates in sync parser`
- `95e7fad` `Track site history for web edits and Excel import`

## Ближайшие следующие шаги
- Сменить пароль `admin` на проде.
- Прогнать ручной smoke по UI:
  - login
  - выбор проекта
  - раздел `Отчеты`
  - выгрузки `PDF`, `PPT`, `Excel`
  - список объектов
  - карточка объекта
  - export
  - базовый sync-сценарий
- Решить, остаются ли тестовые `ID объекта` в текущем наборе или их нужно заменить на боевые.
- Починить `~/network-tracker/Tests/backend/.venv`, чтобы backend-regression не зависел от `/tmp/rts-web-codex-venv`.
- Подключить `Tests/e2e/tests/reports.spec.js` к текущей `Playwright` project matrix и отдельно подтвердить его серверным прогоном.
- Расширить тесты до полноценного E2E-сценария `login -> project selection -> module`.
- Подумать, делать ли справочники глобальными и дальше или потом проектными.
- Поддержать новые внутренние модули для `ТСПУ` и `Стройка ЦОД`.
- Если потребуется Excel-сценарий для новых проектов, проектировать его отдельно, не переиспользуя UCN-шаблон автоматически.
