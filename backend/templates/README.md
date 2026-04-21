# XLSM template

Актуализировано: 2026-04-21

Положите в эту папку файл `sync_template.xlsm`.

Он должен быть создан вручную в Microsoft Excel на Windows и содержать:

- лист `Data`
- VBA-модули из `/Users/vicmb/Yandex.Disk.localized/РТК Сервис/RTS_Web/vba`
- код из `SheetData.cls` в листе `Data`
- код из `ThisWorkbook.cls` в `ThisWorkbook`
- reference на `Microsoft Scripting Runtime`

Важно:

- `sync_template.xlsm` больше не определяет доменную структуру данных UCN;
- он используется только как VBA-контейнер и источник `xl/vbaProject.bin`;
- реальный состав колонок для UCN берётся из `backend/app/core/columns.py`;
- ключ синхронизации в новом шаблоне: Excel-колонка `ID объекта` (`site_id`).
- изменения в `vba/*.bas` и `vba/*.cls` сами по себе не попадают в export, пока вручную не обновлён `sync_template.xlsm`.

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

Контракт файла на 2026-04-21:

- cleanup транзакций и справочников 2026-04-20 не менял структуру экспортируемого `.xlsm`;
- на 2026-04-21 Excel auth hardened:
  - встроенный токен больше не является обычным browser access token;
  - новый экспорт встраивает `excel_sync` token с `project_id`;
  - `/sync` не принимает такой токен для другого проекта;
- полный серверный backend-regression 2026-04-21 прошёл с текущим XLSM/export-контуром.

Если файла `sync_template.xlsm` здесь нет, `GET /api/v1/excel/export` вернёт ошибку с подсказкой.

Важно не путать это с новым разделом `Отчеты`:

- выгрузка `Excel` из `reports.html` строится из агрегированных данных отчёта;
- она не использует `sync_template.xlsm`;
- `PDF` и `PPT` из раздела `Отчеты` тоже не завязаны на VBA-контейнер.
