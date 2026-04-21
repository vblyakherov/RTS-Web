# RTKS Tracker Handoff

Дата: 2026-04-21

## Коротко
- Веб-брендинг системы: `RTKS Tracker`.
- После логина пользователь попадает на экран выбора большого проекта плитками.
- Рабочий модуль сейчас один: `УЦН 2.0 2026 год` (`module_key = ucn_sites_v1`).
- 2026-04-13 UCN полностью переведён на новый серверный Excel-шаблон.
- Старые UCN-данные на проде удалены, вместо них загружено `172` строк нового шаблона.
- Для тестовой загрузки в колонку `ID объекта` были сгенерированы значения
  `UCN-2026-0001 ... UCN-2026-0172`.
- 2026-04-14/15 на проде дополнительно стабилизирован frontend navbar, профиль и admin CRUD-модалки.
- 2026-04-17 на проде дополнительно исправлен admin UI истории объекта:
  - backend route `GET /api/v1/sync/history-fields` больше не перехватывается dynamic route `/sync/history/{site_id}`;
  - `frontend/site.html` переведён на общие modal helpers;
  - раскрытие групп в истории больше не зависит от Bootstrap `collapse`.
- 2026-04-18 на проде добавлен общий проектный раздел `Отчеты`:
  - новый маршрут `/reports.html?project_id=...`;
  - для placeholder-проектов он показывает empty state;
  - для UCN реализованы 2 отчёта с web-визуалом и выгрузками `PDF`, `PPT`, `Excel`.
- 2026-04-21 в backend закрыт этап `2A` по Excel auth hardening:
  - `GET /api/v1/excel/export` встраивает отдельный `token_type=excel_sync`;
  - token несёт `project_id` и, при наличии, `contractor_id`;
  - обычные browser-endpoints принимают только `access` token;
  - `/sync` и `/sync/columns` принимают `excel_sync`, но только в рамках зашитого проекта;
  - `/sync` дополнительно отвергает строки с `site_id`, относящимся к другому проекту.

## Последние фиксы 2026-04-18: раздел Отчеты
- В `frontend/js/utils.js` navbar получил проектный пункт `Отчеты` для всех ролей внутри выбранного проекта.
- Добавлена страница `frontend/reports.html`, которая работает и для UCN, и для placeholder-проектов.
- В `backend/app/api/v1/reports.py` и `backend/app/services/reports.py` появился отдельный reports API.
- Для `ucn_sites_v1` реализованы 2 отчёта:
  - `status_overview`;
  - `milestone_readiness`.
- Один и тот же агрегированный payload используется для web-визуала и трёх выгрузок:
  - `PDF`;
  - `PPT`;
  - `Excel`.
- `contractor` в reports API видит только агрегаты по своим объектам.
- На проде после деплоя 2026-04-18 подтверждён базовый smoke:
  - `GET /api/health` → `{"status":"ok"}`;
  - `GET /reports.html` → `200`;
  - `GET /index.html` → `200`.

## Последние фиксы 2026-04-20: транзакции, справочники и reports regression
- В `backend/app/database.py` `get_db` больше не делает скрытый `commit`; write-endpoints коммитят явно.
- Чтение `/sites`, `/regions`, `/contractors` больше не запускает write-sync справочников.
- Синхронизация регионов осталась только на write-path:
  - web create/update/delete объекта;
  - Excel import;
  - XLSM sync.
- `Region.is_active` и `Contractor.is_active` больше не перетираются автоматически.
- В `backend/app/services/reports.py` добавлена нормализация naive/aware `datetime` через `_as_utc()`, чтобы полный backend-suite стабильно проходил на VPS и SQLite-тестах.
- Серверная проверка после деплоя 2026-04-20 подтверждена:
  - `GET /api/health` → `{"status":"ok"}`;
  - backend full suite → `84 passed`;
  - frontend unit → `55 passed`;
  - e2e через Playwright Docker → `69 passed`, `1 skipped`, `1 flaky` на retry-green прогоне.

## Последние фиксы 2026-04-21: scoped Excel token
- В `backend/app/services/auth.py` появились `token_type`, `project_id` и `contractor_id` в JWT payload.
- Обычный login по-прежнему выдаёт `access` token, а `GET /api/v1/excel/export` теперь выдаёт отдельный `excel_sync` token для VBA/XLSM.
- В `backend/app/api/deps.py` browser auth-endpoints принимают только `access` token.
- В `backend/app/api/v1/sync.py` и `/sync/columns` добавлен отдельный auth-контур, который допускает `excel_sync`.
- `excel_sync` token привязан к `project_id` экспортируемого файла и не может использоваться для другого проекта.
- В `backend/app/services/sync.py` sync теперь дополнительно отклоняет строку, если `site_id` относится к другому проекту, даже при корректном `body.project_id`.
- На VPS перед деплоем подтверждён полный backend-suite: `91 passed`.
- После rsync в `~/network-tracker`, `docker compose restart backend` и прогона из `~/network-tracker/Tests/backend` подтверждено:
  - `GET /api/health` → `{"status":"ok"}`;
  - backend full suite → `91 passed`.

## Последние фронтенд-фиксы 2026-04-14/15
- Пользовательский dropdown в navbar переведён на собственную JS-логику в `frontend/js/utils.js`; проблема плавающего открытия в Chrome/Edge/Яндекс Браузере снята.
- Для `manager` верхнее меню больше не показывает `Справочники`.
- Для `admin` на `/index.html` сразу видны `Пользователи` и `Логи`; после выбора проекта добавляются `Объекты` и `Справочники`.
- В `frontend/profile.html` справа отдельно показываются `Логин` и `Полное имя`; после смены логина правая колонка обновляется сразу.
- В `frontend/site.html` после `Сохранить` карточка гарантированно выходит из режима редактирования через controlled reload.
- В `frontend/users.html` admin не может редактировать или удалять самого себя на странице пользователей; для этого нужно `/profile.html`.
- В `frontend/users.html` и `frontend/projects.html` edit/delete модалки стабилизированы через общие modal helpers, а после save/delete страницы перечитывают список через reload + flash-сообщение.

## Последние фиксы истории 2026-04-17
- В `backend/app/api/v1/sync.py` статический route `/history-fields` поднят выше `/history/{site_id}`, чтобы admin-UI истории не упирался в route shadowing.
- В `Tests/backend/test_sync.py` добавлен regression test на `GET /api/v1/sync/history-fields`.
- В `frontend/site.html` модалки истории и удаления переведены на `showAppModal()/hideAppModal()`, как уже сделано в `users.html` и `projects.html`.
- В `frontend/site.html` accordion истории переведён на собственный toggle, поэтому раскрытие групп больше не зависит от `data-bs-toggle="collapse"` и загрузки Bootstrap JS.
- На проде ручной проверкой подтверждено, что история объекта открывается и раскрывается для объектов `UCN-2026-0003` и `UCN-2026-0015`.

## Что реально работает сейчас

### Пользовательский поток
1. Логин через `/login.html`.
2. После успешного входа редирект на `/index.html`.
3. `/index.html` показывает плитки больших проектов.
4. При выборе проекта:
   - для `ucn_sites_v1` открывается `/sites.html?project_id=<id>`;
   - для `placeholder` открывается `/project.html?id=<id>`.
5. Уже внутри выбранного проекта доступны рабочие разделы по роли.
6. Из пользовательского dropdown доступна страница `/profile.html` для смены собственного логина и пароля.
7. На внутренних страницах любого проекта доступен раздел `/reports.html?project_id=...`.

### Навигация
- Для `admin` на экране выбора проекта в верхнем меню уже есть `Пользователи` и `Логи`.
- Для `manager`, `viewer` и `contractor` на экране выбора проекта рабочего меню нет.
- Отдельного верхнего пункта `Проекты` больше нет.
- Для admin управление проектами доступно:
  - кнопкой на `/index.html`;
  - через dropdown пользователя на внутренних страницах.
- В пользовательском dropdown для всех ролей есть пункт `Мой профиль`.
- `Объекты` показываются только после выбора проекта.
- `Отчеты` показываются после выбора любого большого проекта.
- `Справочники` в верхнем меню показываются только `admin` и только внутри выбранного проекта.
- У `manager` верхней ссылки на `Справочники` нет.
- Для любого пользователя на внутренних страницах есть пункт `Сменить большой проект`.
- Возврат на `/index.html` очищает выбранный `current_project`.

### Крупные проекты

| Название | Код | module_key | Статус |
| --- | --- | --- | --- |
| `УЦН 2.0 2026 год` | `ucn-2026` | `ucn_sites_v1` | рабочий |
| `ТСПУ` | `tspu` | `placeholder` | архитектурный контейнер |
| `Стройка ЦОД` | `dc-build` | `placeholder` | архитектурный контейнер |

### Что внутри UCN сейчас работает
- список объектов;
- фильтрация;
- карточка объекта;
- проектный раздел `Отчеты`;
- web create/update/delete;
- Excel import/export;
- XLSM sync;
- история изменений;
- rollback;
- справочники регионов и подрядчиков.

### Как сейчас работают справочники
- `regions` и `contractors` остаются глобальными, а не проектными.
- GET-эндпоинты `/sites`, `/regions`, `/contractors` больше не выполняют write-sync.
- Для `regions` автосоздание и проставление `region_id` остаются только на write-path.
- `is_active` у `regions` и `contractors` теперь считается ручным полем, а не автосинхронизацией от `sites`.

### Что в UCN сейчас работает в разделе Отчеты
- `status_overview` — статусный профиль проекта;
- `milestone_readiness` — готовность ключевых UCN-вех;
- web-визуализация прямо в браузере;
- выгрузки `PDF`, `PPT`, `Excel` с агрегированными данными.

## Что поменялось по UCN-шаблону

### Новый контракт данных
- Excel import/export/sync теперь опираются на новый плоский UCN-шаблон.
- Ключ синхронизации: Excel-колонка `ID объекта`, которая маппится в `sites.site_id`.
- Реестр всех колонок хранится в `backend/app/core/columns.py`.
- Базовые поля `Site` (`name`, `address`, `status`, `region` и часть дат/координат)
  теперь достраиваются из полей шаблона через `backend/app/services/ucn_template.py`.

### Что обновлено в backend
- добавлена миграция `006_add_ucn_template_v2_fields`;
- в модель `Site` добавлены новые template-specific поля;
- Excel import переписан под новый `.xlsx/.xlsm` шаблон;
- export формирует новый набор колонок;
- sync/history/rollback используют тот же реестр полей;
- добавлен скрипт `backend/load_ucn_template_data.py` для массовой загрузки шаблона в проект `ucn-2026`.

### Что обновлено во frontend
- в UCN-экранах обновлены подписи под новый шаблон;
- поиск и карточка продолжают работать через базовые поля `Site`,
  которые теперь вычисляются из шаблонных данных.

## Права доступа

### Доступ к проектам
- `admin`
  - видит все проекты;
  - может видеть неактивные проекты;
  - управляет проектами и пользователями.
- `manager`
  - видит только проекты из `user_projects`.
- `viewer`
  - видит только проекты из `user_projects`.
- `contractor`
  - видит только те проекты, где есть объекты с его `contractor_id`.

### Доступ к UCN-модулю
- `admin`: полный доступ
- `manager`: create/read/update, import/export, sync
- `viewer`: read-only, export
- `contractor`: только свои объекты, update только по ограниченному набору полей

### Управление учётными данными
- `admin` может менять логин и пароль себе и любому пользователю.
- Любой авторизованный пользователь может менять логин и пароль только себе через профиль.
- На `/users.html` admin не должен редактировать или удалять самого себя; для этого используется `/profile.html`.

### Ограничение contractor
Можно менять только:
- `status`
- `actual_start`
- `actual_end`
- `notes`

## API-слой, который сейчас особенно важен

### Auth
```text
POST  /api/v1/auth/login
GET   /api/v1/auth/me
PATCH /api/v1/auth/me
```

### Projects
```text
GET    /api/v1/projects/?active_only=true|false
GET    /api/v1/projects/{project_id}
POST   /api/v1/projects/
PATCH  /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}
```

Ключевые правила:
- `active_only=true` по умолчанию;
- удалять проект можно только если в нём нет объектов;
- `name` и `code` уникальны;
- `code` нормализуется в lowercase и `-`.

### Sites
```text
GET    /api/v1/sites/?project_id=...
POST   /api/v1/sites/
GET    /api/v1/sites/{id}
PATCH  /api/v1/sites/{id}
DELETE /api/v1/sites/{id}
```

Ключевые правила:
- list всегда требует `project_id`;
- create всегда требует `project_id`;
- проект должен быть доступен пользователю;
- проект должен иметь `module_key = ucn_sites_v1`.

### Excel
```text
GET  /api/v1/excel/export?project_id=...
POST /api/v1/excel/import?project_id=...
```

Ключевые правила:
- Excel-сценарии работают только для `ucn_sites_v1`;
- import принимает только `.xlsx` и `.xlsm`;
- для placeholder-проектов export/import должны давать `400`;
- новый импорт требует колонку `ID объекта`;
- import обновляет только существующие объекты и не создаёт новый объект по неизвестному `ID объекта`.

### Reports
```text
GET /api/v1/reports/?project_id=...
GET /api/v1/reports/{report_key}?project_id=...
```

Ключевые правила:
- раздел существует для всех больших проектов;
- placeholder-проект возвращает пустой каталог отчётов;
- detail-route отдаёт `404`, если для проекта отчёт не настроен;
- contractor получает агрегаты только по своим объектам;
- для UCN сейчас доступны `status_overview` и `milestone_readiness`.

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

Ключевые правила:
- sync принимает `project_id`, но умеет fallback на первый `ucn_sites_v1` проект;
- history доступна `admin` и `manager`;
- rollback доступен только `admin`;
- история пишется из sync, web edit и Excel import;
- sync использует тот же набор колонок, что import/export.
- sync не создаёт новый объект по неизвестному `ID объекта`; такая строка возвращается как ошибка.

## Что уже проверено на проде
- Код задеплоен на VPS через `rsync`.
- Перед обновлением создан бэкап БД:
  - `/home/<deploy-user>/backups/rtks_prod_YYYYMMDD_HHMMSS.sql`
- На проде применена миграция `006_add_ucn_template_v2_fields`.
- Старые UCN-объекты удалены: `651`.
- Из нового шаблона импортировано `172` объекта.
- Проверены первые ID на проде:
  - `UCN-2026-0001`
  - `UCN-2026-0002`
  - `UCN-2026-0003`
  - `UCN-2026-0004`
  - `UCN-2026-0005`
- `GET /api/health` на сервере возвращает `{"status":"ok"}`.
- `/api/v1/projects` на проде возвращает 3 проекта.
- UCN API после миграции и импорта отвечает корректно.
- Фронтенд-фиксы 2026-04-14/15 проверены ручным smoke на проде:
  - dropdown пользователя открывается стабильно;
  - manager не видит `Справочники` в верхнем меню;
  - admin видит `Пользователи` и `Логи` уже на `/index.html`;
  - `profile.html` корректно разделяет `Логин` и `Полное имя`;
  - `site.html` после сохранения выходит из режима редактирования;
  - `users.html` и `projects.html` после save/delete закрывают модалки через reload и показывают актуальный список.
- Фиксы истории 2026-04-17 тоже проверены ручной проверкой на проде:
  - кнопка `История` в `frontend/site.html` открывает модалку;
  - группы изменений внутри истории раскрываются;
  - для `UCN-2026-0003` и `UCN-2026-0015` UI показывает реальные записи из `site_history`.
- Обновление 2026-04-20 тоже подтверждено на проде:
  - `get_db` больше не делает скрытый `commit`;
  - чтение `/sites`, `/regions`, `/contractors` больше не пишет в БД через sync справочников;
  - `Region.is_active` и `Contractor.is_active` больше не перетираются автоматически;
  - полный серверный прогон после деплоя: backend `84 passed`, frontend unit `55 passed`, e2e `69 passed`, `1 skipped`, `1 flaky`.
- Обновление 2026-04-21 тоже подтверждено на проде:
  - `GET /api/v1/excel/export` встраивает `excel_sync` token вместо обычного browser access token;
  - browser auth-endpoints принимают только `access` token;
  - `/sync` и `/sync/columns` принимают scoped `excel_sync` token;
  - `/sync` отвергает project mismatch и строки с `site_id` из другого проекта;
  - полный серверный прогон после деплоя: backend `91 passed`.

## Текущее состояние XLSM / VBA sync
- Export отдаёт `.xlsm` с `vbaProject.bin`.
- Export работает только внутри проекта UCN.
- Изменения в `vba/*.bas` и `vba/*.cls` сами по себе не меняют export, пока вручную не обновлён `backend/templates/sync_template.xlsm`.
- В файл записываются:
  - `auth_token` — scoped token `excel_sync` для `/sync` и `/sync/columns`
  - `username`
  - `last_sync_at`
  - `project_id`
- Ключ sync — `site_id`, который в Excel представлен колонкой `ID объекта`.
- Лист `Data` в экспортируемом `.xlsm` защищён: можно менять значения ячеек, но нельзя вставлять и удалять строки.
- Backend принимает ISO-datetime с timezone.
- Runtime по-прежнему ориентирован на Windows Excel.

## Текущее состояние тестового контура
- В проекте есть рабочий каталог `Tests/`.
- Структура:
  - `Tests/backend/` — `pytest + httpx + aiosqlite`
  - `Tests/frontend/` — `Jest + jsdom`
  - `Tests/README.md` — инструкция по запуску
- Локальные служебные каталоги:
  - `Tests/backend/.venv/`
  - `Tests/.claude/`
  - `Tests/frontend/node_modules/`
  - их не нужно считать частью продуктового кода.

- Основные backend-файлы сейчас:
  - `test_auth.py`
  - `test_contractors.py`
  - `test_excel.py`
  - `test_projects.py`
  - `test_regions.py`
  - `test_reports.py`
  - `test_sites.py`
  - `test_sync.py`

### Актуальный статус тестов на 2026-04-21
- Подтверждённый полный backend-прогон на VPS: `91/91`.
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
- Для Codex/локального агента подтверждающий backend-прогон считать серверным: локальная системная `python3` может быть ниже `3.12`.
- Для незакоммиченных правок безопаснее копировать проект во временный каталог на VPS и запускать `pytest` там, а не подменять `~/network-tracker/backend`, потому что продовый backend там работает с bind-mount и `--reload`.
- Последние фронтенд-фиксы 2026-04-14/15 подтверждены ручной проверкой на проде; автоматический прогон тестов под них повторно не запускался.
- На 2026-04-18 добавлены:
  - `Tests/backend/test_reports.py`;
  - `Tests/e2e/tests/reports.spec.js`;
  - новые unit-тесты для reports navbar/API.
- На 2026-04-20 дополнительно добавлены:
  - `Tests/backend/test_regions.py`;
  - `Tests/backend/test_contractors.py`;
  - regression-тесты на отсутствие write-on-GET и на явные commit boundaries.
- На 2026-04-21 дополнительно добавлены:
  - тесты на `excel_sync` token в `test_auth.py`, `test_excel.py`, `test_sync.py`;
  - проверки project-scoping для `/sync` и `/sync/columns`;
  - regression-test на запрет sync строки с `site_id` из другого проекта.
- Канонический backend-runner на VPS сейчас:
  - `PYTHONPATH=~/network-tracker/backend /tmp/rts-web-codex-venv/bin/pytest -q`
- `~/network-tracker/Tests/backend/.venv` на сервере всё ещё разъехался по Python/pydantic_core и не считается каноническим runner'ом.
- Для E2E канонический серверный прогон теперь делается через Docker-образ Playwright.
- Важно: `Tests/e2e/tests/reports.spec.js` есть в репозитории, но в текущем `Tests/e2e/playwright.config.js` не входит в `testMatch` ни одного project, поэтому не участвовал в подтверждённом прогоне `69 passed, 1 skipped, 1 flaky`.

### Что уже покрывает `Tests/`
- Backend:
  - auth;
  - self-update логина и пароля;
  - явные commit boundaries без скрытого auto-commit в dependency;
  - projects RBAC;
  - reports API;
  - regions и contractors;
  - sites CRUD и contractor restrictions;
  - excel для `ucn_sites_v1` и placeholder;
  - import нового UCN-шаблона по `ID объекта` без создания новых объектов;
  - отсутствие write-on-GET для `/sites`, `/regions`, `/contractors`;
  - sync/history/rollback.
- Frontend:
  - `utils.js`;
  - `api.js`;
  - `getProjectRoute()`;
  - `getProjectReportsRoute()`;
  - `moduleLabel()`;
  - `renderNavbar()`;
  - `statusBadge()`;
  - `roleBadge()`;
  - `rememberProject()`.
  - dropdown-ссылка на `/profile.html`.
- E2E:
  - auth flow и logout;
  - project selection;
  - базовый admin UI;
  - directories;
  - sites list;
  - site card/edit/history.

### Что пока не покрыто
- Полноценный E2E через Playwright/Cypress.
- `reports.spec.js` как часть подтверждённого server-run Playwright matrix.
- `api.js` с моками сети.
- `checkAuth()`.
- Страницы `sites.html` и `site.html` как реальные пользовательские сценарии.

## Что нужно сообщить другому ИИ, если продолжать работу
- Сначала прочитать `AGENTS.md`, этот `HANDOFF.md` и `Tests/README.md`.
- Не считать UCN старым плоским списком: сейчас это внутренний модуль большого проекта.
- Учитывать, что UCN уже живёт на новом Excel-контракте.
- Не возвращать старые NI-поля как основной источник истины для Excel/sync.
- Если нужно заново грузить шаблон на прод:
  - предварительно убедиться, что Excel-файл заполнен по `ID объекта`;
  - затем использовать `backend/load_ucn_template_data.py`.
- Не удалять `Tests/` и локальные служебные каталоги пользователя без явной необходимости.

## Ключевые файлы для ориентирования
- `frontend/js/utils.js`
- `frontend/reports.html`
- `frontend/users.html`
- `frontend/projects.html`
- `backend/app/api/v1/reports.py`
- `backend/app/services/reports.py`
- `backend/app/schemas/report.py`
- `backend/alembic/versions/006_add_ucn_template_v2_fields.py`
- `backend/app/core/columns.py`
- `backend/app/api/v1/auth.py`
- `frontend/profile.html`
- `backend/app/services/ucn_template.py`
- `backend/app/services/excel.py`
- `backend/app/services/sync.py`
- `backend/app/crud/site.py`
- `backend/app/crud/site_history.py`
- `backend/load_ucn_template_data.py`
- `frontend/sites.html`
- `frontend/site.html`
- `Tests/backend/test_reports.py`
- `Tests/e2e/tests/reports.spec.js`
- `Tests/backend/test_excel.py`
- `Tests/backend/test_sync.py`
- `Tests/README.md`

## Что брать следующим приоритетом
- Сменить admin password на проде.
- Прогнать ручной smoke по UI:
  - login
  - выбор проекта
  - раздел `Отчеты`
  - выгрузки `PDF`, `PPT`, `Excel`
  - список объектов
  - карточка объекта
  - export
  - базовый sync-сценарий
- Решить, остаются ли тестовые `ID объекта` на этом наборе или их нужно заменить на боевые.
- Починить `~/network-tracker/Tests/backend/.venv`, чтобы не зависеть от `/tmp/rts-web-codex-venv`.
- Подключить `reports.spec.js` к текущей Playwright project matrix и отдельно подтвердить reports E2E серверным прогоном.
- Добавить E2E-сценарий `login -> project selection -> module`.
- Проектировать отдельные внутренние модули для `ТСПУ` и `Стройка ЦОД`.
