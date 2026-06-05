# XLSM template

Актуализировано: 2026-06-05

Положите в эту папку файл `sync_template.xlsm`.

Он должен быть создан или обновлён вручную в Microsoft Excel и содержать:

- лист `Data`
- VBA-модули из каталога `vba/` в корне репозитория
- код из `SheetData.cls` в листе `Data`
- код из `ThisWorkbook.cls` в `ThisWorkbook`
- reference на `Microsoft Scripting Runtime`

Важно:

- `sync_template.xlsm` больше не определяет доменную структуру данных UCN;
- он используется только как VBA-контейнер и источник `xl/vbaProject.bin`;
- реальный состав колонок для UCN берётся из `backend/app/core/columns.py`;
- на 2026-06-04 активный UCN-контракт содержит `67` колонок;
- ключ синхронизации в новом шаблоне: Excel-колонка `ID объекта` (`site_id`), третья колонка файла;
- изменения в `vba/*.bas` и `vba/*.cls` сами по себе не попадают в export, пока вручную не обновлён `sync_template.xlsm`.
- на 2026-06-05 `sync_template.xlsm` уже обновлён и содержит актуальные `modConfig`/`modSync`;
- если свежескачанный Excel снова спрашивает пароль сразу при sync, сначала проверить VBA внутри этого template.

Сервис `/api/v1/excel/export` собирает новый `.xlsm` через `xlsxwriter`, подмешивает VBA из `sync_template.xlsm`, создаёт:

- лист `Sync` с кнопкой `SyncNow`
- лист `Data` с колонками нового UCN-шаблона
- скрытые листы `_Config` и `_DirtyTracker`
- защищённый лист `Data`: пользователь может менять значения ячеек, но не может вставлять или удалять строки

В `_Config` записываются:

- `last_sync_at`
- `username`
- `auth_token` — scoped JWT `token_type=excel_sync`, ограниченный `/sync` и `/sync/columns`
- `project_id`

Ручная кнопка внутри исходного `sync_template.xlsm` не обязательна: backend создаёт кнопку в экспортируемом файле сам.

Контракт файла на 2026-06-04:

- cleanup транзакций и справочников 2026-04-20 не менял структуру экспортируемого `.xlsm`;
- на 2026-04-21 Excel auth hardened:
  - встроенный токен больше не является обычным browser access token;
  - новый экспорт встраивает `excel_sync` token с `project_id`;
  - `/sync` не принимает такой токен для другого проекта;
- на 2026-06-04 Excel Data headers обновлены под новый 67-колоночный шаблон трекера v2;
- `POST /api/v1/excel/replace` и admin UI на `/projects.html` используют тот же реестр колонок, но не меняют VBA-контейнер;
- полный серверный backend-regression 2026-04-21 прошёл с предыдущим XLSM/export-контуром; после 2026-06-04 требуется новый полный regression.

Дополнение на 2026-06-05:

- `SyncNow()` в template больше не начинает работу с обязательного `DoLogin()`;
- актуальный старт sync: загрузить сессию через `EnsureSyncSession()`, использовать `_Config.auth_token`, затем идти в `/sync/columns` и `/sync`;
- `modConfig.SERVER_URL` внутри template: `https://tracker.rtk-service.ru`;
- `GET /api/v1/auth/me` на backend принимает `excel_sync` token только для legacy probe, `PATCH /api/v1/auth/me` остаётся browser-only;
- для старых macro routes на prod nginx используется `ops/patch_nginx_legacy_vba.py`;
- уже скачанные старые `.xlsm` не обновляются автоматически, пользователю нужно скачать файл заново.

Проверка после ручного обновления template:

- открыть `backend/templates/sync_template.xlsm` в Excel VBA Editor;
- в `modConfig` проверить `SERVER_URL`, `API_BASE`, `CFG_PROJECT_ID`, `KEY_HEADER`;
- в `modSync` проверить, что `Public Sub SyncNow()` содержит `EnsureSyncSession()` и не содержит старый старт `If Not DoLogin()`;
- после сохранения проверить, что `xl/vbaProject.bin` не совпадает со старым hash `96aea6b90fdbe4dfa718840964fb2bafadcbdae08e8530eb503a361c270bf1ea`.

Если файла `sync_template.xlsm` здесь нет, `GET /api/v1/excel/export` вернёт ошибку с подсказкой.

Важно не путать это с новым разделом `Отчеты`:

- выгрузка `Excel` из `reports.html` строится из агрегированных данных отчёта;
- она не использует `sync_template.xlsm`;
- `PDF` и `PPT` из раздела `Отчеты` тоже не завязаны на VBA-контейнер.
