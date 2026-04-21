Attribute VB_Name = "modSync"
Option Explicit

' ============================================================
'  modSync - Основная логика двусторонней синхронизации
'
'  Точка входа: SyncNow (вызывается кнопкой на листе)
'
'  Протокол:
'  1. Авторизация (если нет токена)
'  2. Загрузка маппинга колонок (GET /sync/columns) - один раз
'  3. Сбор изменённых строк (dirty rows)
'  4. POST /sync  {last_sync_at, rows, client_version: 1}
'  5. Применение серверных изменений к листу
'  6. Очистка dirty-трекера, сохранение last_sync_at
' ============================================================

' --- Маппинг: номер колонки на листе -> db_name ---
Private m_ColToDb As Object     ' Dictionary: colIndex (Long) -> db_name (String)
Private m_DbToCol As Object     ' Dictionary: db_name (String) -> colIndex (Long)
Private m_KeyCol  As Long       ' Номер колонки с site_id

' ============================================================
'  ГЛАВНАЯ КНОПКА
' ============================================================

Public Sub SyncNow()
    On Error GoTo ErrHandler

    Application.StatusBar = "Sync: checking access..."
    If Not DoLogin() Then
        Application.StatusBar = False
        Exit Sub
    End If

    ' Загружаем маппинг колонок, если ещё нет
    Application.StatusBar = "Sync: loading columns..."
    If Not LoadColumnMap() Then
        Application.StatusBar = False
        Exit Sub
    End If

    ' Загружаем last_sync_at
    Dim lastSync As String
    lastSync = LoadLastSync()

    ' Строим заголовки на листе, если их нет
    EnsureHeaders
    ProtectDataSheet

    ' Считываем маппинг колонок на листе
    BuildSheetMapping

    ' Собираем изменённые строки
    Application.StatusBar = "Sync: collecting changes..."
    Dim dirtyJson As String
    Dim dirtyCount As Long
    dirtyJson = CollectDirtyRowsJson(dirtyCount)

    ' Формируем запрос
    Dim reqBody As String
    reqBody = JsonObjStart()
    If Len(lastSync) > 0 Then
        reqBody = JsonObjAdd(reqBody, "last_sync_at", lastSync)
    Else
        reqBody = JsonObjAddRaw(reqBody, "last_sync_at", "null")
    End If
    reqBody = JsonObjAddRaw(reqBody, "rows", dirtyJson)
    reqBody = JsonObjAdd(reqBody, "client_version", CLng(1))
    reqBody = JsonObjEnd(reqBody)

    ' Отправляем
    Application.StatusBar = "Sync: sending data..."
    Dim resp As HttpResponse
    resp = HttpPost(FullUrl(EP_SYNC), reqBody)

    If Not resp.Success Then
        If resp.StatusCode = 401 Then
            ' Токен протух — повторяем логин
            g_Token = ""
            If DoLogin() Then
                resp = HttpPost(FullUrl(EP_SYNC), reqBody)
            End If
        End If
        If Not resp.Success Then
            MsgBox "Sync error:" & vbCrLf & _
                   "HTTP " & resp.StatusCode & vbCrLf & resp.Body, _
                   vbCritical, "Sync error"
            Application.StatusBar = False
            Exit Sub
        End If
    End If

    ' Парсим ответ
    Application.StatusBar = "Sync: applying updates..."
    Dim parsed As Object
    Set parsed = JsonParse(resp.Body)

    Dim serverTime As String
    serverTime = JsonGetStr(parsed, "server_time")
    Dim applied As Long
    applied = JsonGetLng(parsed, "applied")

    ' Применяем серверные строки
    Dim serverRows As Collection
    Set serverRows = JsonGetArr(parsed, "rows")
    Dim updatedCount As Long
    updatedCount = ApplyServerRows(serverRows)

    ' Конфликты
    Dim conflicts As Collection
    Set conflicts = JsonGetArr(parsed, "conflicts")

    ' Ошибки
    Dim errors As Collection
    Set errors = JsonGetArr(parsed, "errors")

    ' Очищаем dirty-трекер и сохраняем время синхронизации
    ClearDirty
    SaveLastSync serverTime

    ' Итоговое сообщение
    Application.StatusBar = False
    Dim msg As String
    msg = "Sync complete." & vbCrLf & vbCrLf
    msg = msg & "Changes sent: " & dirtyCount & vbCrLf
    msg = msg & "Applied on server: " & applied & vbCrLf
    msg = msg & "Updates received: " & updatedCount & vbCrLf

    If conflicts.Count > 0 Then
        msg = msg & vbCrLf & "Conflicts (last-write-wins): " & conflicts.Count & vbCrLf
        Dim c As Long
        For c = 1 To Application.WorksheetFunction.Min(conflicts.Count, 5)
            Dim conf As Object
            Set conf = conflicts(c)
            msg = msg & "  - " & JsonGetStr(conf, "site_id") & vbCrLf
        Next c
        If conflicts.Count > 5 Then msg = msg & "  ... and " & (conflicts.Count - 5) & " more" & vbCrLf
    End If

    If errors.Count > 0 Then
        msg = msg & vbCrLf & "Errors: " & errors.Count & vbCrLf
        Dim e As Long
        For e = 1 To Application.WorksheetFunction.Min(errors.Count, 5)
            msg = msg & "  - " & CStr(errors(e)) & vbCrLf
        Next e
    End If

    MsgBox msg, vbInformation, "Sync"
    Exit Sub

ErrHandler:
    Application.StatusBar = False
    MsgBox "Error: " & Err.Description & " (line " & Erl & ")", vbCritical, "Sync error"
End Sub

' ============================================================
'  ЗАГРУЗКА МАППИНГА КОЛОНОК С СЕРВЕРА
' ============================================================

Private Function LoadColumnMap() As Boolean
    If g_ColMapLoaded Then
        LoadColumnMap = True
        Exit Function
    End If

    Dim resp As HttpResponse
    resp = HttpGet(FullUrl(EP_COLUMNS))

    If Not resp.Success Then
        MsgBox "Could not load column list:" & vbCrLf & resp.Body, vbCritical, "Sync error"
        LoadColumnMap = False
        Exit Function
    End If

    Dim arr As Collection
    Set arr = JsonParse(resp.Body)

    g_ColCount = arr.Count
    ReDim g_ColMap(1 To g_ColCount, 1 To 5)
    ' (i, 1) = db_name
    ' (i, 2) = excel_header
    ' (i, 3) = type
    ' (i, 4) = is_key (0/1)
    ' (i, 5) = group

    Dim i As Long
    For i = 1 To arr.Count
        Dim col As Object
        Set col = arr(i)
        g_ColMap(i, 1) = JsonGetStr(col, "db_name")
        g_ColMap(i, 2) = JsonGetStr(col, "excel_header")
        g_ColMap(i, 3) = JsonGetStr(col, "type")
        g_ColMap(i, 4) = IIf(IsNull(JsonGet(col, "is_key")), 0, IIf(JsonGet(col, "is_key"), 1, 0))
        g_ColMap(i, 5) = JsonGetStr(col, "group")
    Next i

    g_ColMapLoaded = True
    LoadColumnMap = True
End Function

' ============================================================
'  СОЗДАНИЕ ЗАГОЛОВКОВ НА ЛИСТЕ
' ============================================================

Private Sub EnsureHeaders()
    Dim ws As Worksheet
    Set ws = EnsureSheet(DATA_SHEET)

    ' Проверяем, есть ли уже заголовки
    If ws.Cells(1, 1).Value <> "" Then Exit Sub

    DirtyTrackOff

    Dim i As Long
    For i = 1 To g_ColCount
        ws.Cells(1, i).Value = g_ColMap(i, 2)   ' excel_header
        ws.Cells(1, i).Font.Bold = True
    Next i

    ' Замораживаем первую строку
    ws.Activate
    ws.Rows("2:2").Select
    ActiveWindow.FreezePanes = True
    ws.Range("A1").Select

    DirtyTrackOn
End Sub

' ============================================================
'  МАППИНГ КОЛОНОК ЛИСТА <-> DB_NAME
' ============================================================

Private Sub BuildSheetMapping()
    Set m_ColToDb = CreateObject("Scripting.Dictionary")
    Set m_DbToCol = CreateObject("Scripting.Dictionary")
    m_KeyCol = 0

    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets(DATA_SHEET)

    Dim lastCol As Long
    lastCol = ws.Cells(1, ws.Columns.Count).End(xlToLeft).Column

    ' Строим обратный маппинг: excel_header -> db_name
    Dim headerToDb As Object
    Set headerToDb = CreateObject("Scripting.Dictionary")
    headerToDb.CompareMode = vbTextCompare
    Dim i As Long
    For i = 1 To g_ColCount
        headerToDb(g_ColMap(i, 2)) = g_ColMap(i, 1)
    Next i

    ' Проходим по заголовкам листа
    Dim c As Long
    For c = 1 To lastCol
        Dim header As String
        header = Trim$(CStr(ws.Cells(1, c).Value))
        If headerToDb.Exists(header) Then
            Dim dbName As String
            dbName = headerToDb(header)
            m_ColToDb(c) = dbName
            m_DbToCol(dbName) = c
            If dbName = KEY_DB_NAME Then m_KeyCol = c
        End If
    Next c

    If m_KeyCol = 0 Then
        MsgBox "Column '" & KEY_HEADER & "' was not found on sheet " & DATA_SHEET, vbCritical, "Sync error"
    End If
End Sub

' ============================================================
'  СБОР ИЗМЕНЁННЫХ СТРОК В JSON
' ============================================================

Private Function CollectDirtyRowsJson(ByRef outCount As Long) As String
    Dim rows As New Collection
    Dim dirtyRows As Collection
    Set dirtyRows = GetDirtyRows()

    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets(DATA_SHEET)

    Dim i As Long
    For i = 1 To dirtyRows.Count
        Dim rowNum As Long
        rowNum = dirtyRows(i)

        ' Проверяем, что есть site_id
        Dim siteId As String
        If m_KeyCol > 0 Then
            siteId = Trim$(CStr(ws.Cells(rowNum, m_KeyCol).Value))
        End If
        If Len(siteId) = 0 Then GoTo NextRow

        ' Собираем все поля строки
        Dim rowJson As String
        rowJson = JsonObjStart()
        rowJson = JsonObjAdd(rowJson, "site_id", siteId)

        Dim keys As Variant
        keys = m_ColToDb.keys
        Dim k As Long
        For k = 0 To UBound(keys)
            Dim colIdx As Long
            colIdx = keys(k)
            Dim db As String
            db = m_ColToDb(colIdx)
            If db <> KEY_DB_NAME Then
                Dim cellVal As Variant
                cellVal = ws.Cells(rowNum, colIdx).Value
                If Not IsEmpty(cellVal) Then
                    rowJson = JsonObjAdd(rowJson, db, cellVal)
                End If
            End If
        Next k

        rowJson = JsonObjEnd(rowJson)
        rows.Add rowJson

NextRow:
    Next i

    outCount = rows.Count
    CollectDirtyRowsJson = JsonArrayFromColl(rows)
End Function

' ============================================================
'  ПРИМЕНЕНИЕ СЕРВЕРНЫХ СТРОК К ЛИСТУ
' ============================================================

Private Function ApplyServerRows(serverRows As Collection) As Long
    If serverRows.Count = 0 Then
        ApplyServerRows = 0
        Exit Function
    End If

    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets(DATA_SHEET)

    ' Отключаем отслеживание, чтобы серверные данные не помечались dirty
    DirtyTrackOff
    Application.ScreenUpdating = False

    ' Строим индекс: site_id -> row number
    Dim siteIndex As Object
    Set siteIndex = CreateObject("Scripting.Dictionary")
    siteIndex.CompareMode = vbTextCompare

    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, m_KeyCol).End(xlUp).Row

    Dim r As Long
    For r = 2 To lastRow
        Dim sid As String
        sid = Trim$(CStr(ws.Cells(r, m_KeyCol).Value))
        If Len(sid) > 0 Then
            siteIndex(sid) = r
        End If
    Next r

    ' Применяем каждую строку
    Dim count As Long
    count = 0
    Dim i As Long
    For i = 1 To serverRows.Count
        Dim srvRow As Object
        Set srvRow = serverRows(i)

        Dim siteId As String
        siteId = JsonGetStr(srvRow, "site_id")
        If Len(siteId) = 0 Then GoTo NextSrvRow

        ' Определяем строку (существующую или новую)
        Dim targetRow As Long
        If siteIndex.Exists(siteId) Then
            targetRow = siteIndex(siteId)
        Else
            lastRow = lastRow + 1
            targetRow = lastRow
            siteIndex(siteId) = targetRow
        End If

        ' Записываем поля
        Dim srvKeys As Variant
        srvKeys = srvRow.keys
        Dim j As Long
        For j = 0 To UBound(srvKeys)
            Dim fieldName As String
            fieldName = srvKeys(j)

            ' Пропускаем служебные поля, начинающиеся с _
            If Left$(fieldName, 1) = "_" Then GoTo NextField

            ' Находим колонку на листе
            If m_DbToCol.Exists(fieldName) Then
                Dim colIdx As Long
                colIdx = m_DbToCol(fieldName)
                Dim val As Variant
                If IsObject(srvRow(fieldName)) Then
                    ' Вложенный объект — пропускаем
                    GoTo NextField
                End If
                val = srvRow(fieldName)
                If IsNull(val) Then
                    ws.Cells(targetRow, colIdx).Value = ""
                Else
                    ws.Cells(targetRow, colIdx).Value = val
                End If
            End If
NextField:
        Next j

        count = count + 1
NextSrvRow:
    Next i

    Application.ScreenUpdating = True
    DirtyTrackOn

    ApplyServerRows = count
End Function

' ============================================================
'  ПОЛНАЯ ЗАГРУЗКА (первая синхронизация)
' ============================================================

Public Sub FullDownload()
    ' Сбрасываем last_sync для полной перезагрузки
    SaveLastSync ""
    ClearDirty
    SyncNow
End Sub
