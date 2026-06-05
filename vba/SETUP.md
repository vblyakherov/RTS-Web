# Настройка VBA-макроса синхронизации

Актуализировано: 2026-06-05

## Создание .xlsm файла

1. Открыть Excel, создать новую книгу
2. Сохранить как **"Трекер.xlsm"** (формат: "Книга Excel с поддержкой макросов")
3. Переименовать первый лист в **"Data"**

## Импорт модулей

1. Открыть редактор VBA: **Alt+F11**
2. **Импорт модулей** (File → Import File), по одному:
   - `modConfig.bas`
   - `modJSON.bas`
   - `modHTTP.bas`
   - `modAuth.bas`
   - `modDirty.bas`
   - `modSync.bas`
3. **Код листа Data:**
   - В дереве проекта дважды кликнуть на лист "Data" (Sheet1)
   - Вставить содержимое `SheetData.cls` (только код между `Option Explicit` и `End Sub`)
4. **Код ThisWorkbook:**
   - Дважды кликнуть на "ThisWorkbook" в дереве проекта
   - Вставить содержимое `ThisWorkbook.cls` (только код между `Option Explicit` и `End Sub`)

## Подключение библиотеки

В VBA Editor: **Tools → References**, поставить галочку:
- **Microsoft Scripting Runtime** (для Dictionary)

## Кнопка синхронизации

Ручную кнопку в `sync_template.xlsm` добавлять больше не нужно.

При экспорте из веб-приложения backend:
- создаёт отдельный лист `Sync`
- автоматически вставляет на него кнопку, привязанную к макросу **`SyncNow`**
- оставляет рабочие данные на листе `Data`

## Настройка сервера

В prod-шаблоне `modConfig.bas` должен быть адрес сервера:
```vba
Public Const SERVER_URL = "https://tracker.rtk-service.ru"
```

Если этот файл адаптируется под другой стенд, менять `SERVER_URL` нужно и в `vba/modConfig.bas`, и внутри `backend/templates/sync_template.xlsm`.

## Использование

1. Открыть лист `Sync` и нажать кнопку **"Синхронизировать"**
2. В файле, скачанном из веб-приложения, логин и scoped Excel token уже будут записаны в скрытый лист `_Config`
3. При первом запуске пароль не требуется, пока встроенный токен не истёк
4. Если токен истёк, макрос попросит ввести логин/пароль повторно
5. Далее — редактируете данные на листе `Data`, возвращаетесь на `Sync` и нажимаете "Синхронизировать"
6. Макрос отправит изменения и получит обновления с сервера

Важно на 2026-06-04:

- backend cleanup по транзакциям и справочникам не менял VBA-контракт sync;
- активный UCN Data-контракт теперь содержит `67` колонок из `backend/app/core/columns.py`;
- `site_id` / колонка `ID объекта`, листы `Sync`/`Data` и `_Config.project_id` остаются актуальными;
- `ID объекта` находится третьей колонкой в новом шаблоне;
- новый export встраивает `auth_token` типа `excel_sync`, ограниченный текущим `project_id`;
- `/sync` и `/sync/columns` принимают этот токен, но обычные browser-endpoints — нет;
- admin replace-load нового шаблона на `/projects.html` не требует изменения VBA-кода;
- подтверждённый серверный backend-regression 2026-04-21 проходил с предыдущим XLSM/sync-контуром, после 2026-06-04 нужен новый полный regression.

Важно на 2026-06-05:

- `SyncNow()` больше не должен начинаться с `DoLogin()`;
- правильный старт:
```vba
Application.StatusBar = "Sync: loading session..."
If Not EnsureSyncSession() Then
```
- `EnsureSyncSession()` сначала загружает `_Config.auth_token`, `_Config.username`, `_Config.project_id`;
- пароль запрашивается только если встроенного токена нет или сервер вернул `401`;
- после изменения `.bas` файлов нужно вручную обновить `backend/templates/sync_template.xlsm`, иначе export продолжит отдавать старый `vbaProject.bin`;
- уже скачанные `.xlsm` не обновляются автоматически, пользователь должен скачать файл заново.

## Обновление существующего `sync_template.xlsm`

1. Открыть `backend/templates/sync_template.xlsm`.
2. Открыть VBA Editor.
3. Обновить стандартные модули из `vba/`, особенно `modConfig.bas` и `modSync.bas`.
4. Сохранить `.xlsm`.
5. Проверить в `modConfig`:
```vba
Public Const SERVER_URL     As String = "https://tracker.rtk-service.ru"
Public Const API_BASE       As String = "/api/v1"
Public Const CFG_PROJECT_ID As String = "project_id"
Public Const KEY_HEADER     As String = "ID объекта"
```
6. Проверить в `modSync`, что `SyncNow()` использует `EnsureSyncSession()`.

На Mac Excel импорт `.bas` иногда падает с `System Error &H80004005`. Рабочий обход:

- скопировать `.bas` файлы во временную папку с коротким ASCII-путём, например `/Users/vicmb/vba_import`;
- если import всё равно падает, открыть модуль в VBA Editor и заменить код через copy/paste;
- после сохранения template проверить, что свежескачанный Excel содержит новый VBA.

## Что не относится к VBA

Новый проектный раздел `Отчеты` работает отдельно от XLSM sync:

- web-визуал отчётов открывается в `reports.html`;
- выгрузки `PDF`, `PPT`, `Excel` из отчётов не используют VBA;
- для работы раздела `Отчеты` этот XLSM-контур настраивать не нужно.

## Архитектура модулей

| Модуль      | Назначение                              |
|-------------|----------------------------------------|
| modConfig   | URL сервера, константы, утилиты        |
| modJSON     | Парсер/билдер JSON (без зависимостей)  |
| modHTTP     | HTTP GET/POST через MSXML2 + ADODB     |
| modAuth     | Логин, хранение JWT-токена             |
| modDirty    | Отслеживание изменённых ячеек          |
| modSync     | Сбор данных, отправка, применение      |
