Attribute VB_Name = "modConfig"
Option Explicit

' ============================================================
'  modConfig - Настройки подключения и константы
' ============================================================

' --- Сервер ---
' Public repo note: keep only a placeholder here. Real deployment URL is set
' per environment when the workbook sources are assembled for a target stand.
Public Const SERVER_URL     As String = "https://your-tracker.example.com"
Public Const API_BASE       As String = "/api/v1"

' --- Эндпоинты ---
Public Const EP_LOGIN       As String = "/auth/login"
Public Const EP_SYNC        As String = "/sync"
Public Const EP_COLUMNS     As String = "/sync/columns"

' --- Листы ---
Public Const DATA_SHEET     As String = "Data"
Public Const DIRTY_SHEET    As String = "_DirtyTracker"
Public Const CONFIG_SHEET   As String = "_Config"
Public Const DATA_SHEET_PASSWORD As String = "RTKS_SYNC_DATA"
Public Const CFG_LAST_SYNC  As String = "last_sync_at"
Public Const CFG_AUTH_TOKEN As String = "auth_token"
Public Const CFG_USERNAME   As String = "username"

' --- Ключевое поле ---
Public Const KEY_DB_NAME    As String = "site_id"
Public Const KEY_HEADER     As String = "Site ID"

' --- Таймауты (мс) ---
Public Const HTTP_TIMEOUT   As Long = 120000

' --- Хранение токена (в памяти) ---
Public g_Token              As String
Public g_Username           As String
Public g_LastSyncAt         As String   ' ISO-8601 или ""

' --- Маппинг колонок (заполняется при первой синхронизации) ---
Public g_ColMap()           As String   ' (0..N, 0..1): (db_name, excel_header)
Public g_ColCount           As Long
Public g_ColMapLoaded       As Boolean

' ============================================================
'  Вспомогательные функции
' ============================================================

Public Function FullUrl(endpoint As String) As String
    FullUrl = SERVER_URL & API_BASE & endpoint
End Function

' Сохранить last_sync_at на скрытый лист _Config
Public Sub SaveLastSync(ts As String)
    SaveConfigValue CFG_LAST_SYNC, ts
    g_LastSyncAt = ts
End Sub

' Загрузить last_sync_at из _Config
Public Function LoadLastSync() As String
    LoadLastSync = LoadConfigValue(CFG_LAST_SYNC)
    g_LastSyncAt = LoadLastSync
End Function

Public Sub SaveAuthToken(token As String)
    SaveConfigValue CFG_AUTH_TOKEN, token
    g_Token = token
End Sub

Public Function LoadAuthToken() As String
    LoadAuthToken = LoadConfigValue(CFG_AUTH_TOKEN)
    g_Token = LoadAuthToken
End Function

Public Sub SaveUsername(username As String)
    SaveConfigValue CFG_USERNAME, username
    g_Username = username
End Sub

Public Function LoadUsername() As String
    LoadUsername = LoadConfigValue(CFG_USERNAME)
    g_Username = LoadUsername
End Function

Public Sub LoadStoredSession()
    LoadLastSync
    LoadAuthToken
    LoadUsername
End Sub

Public Sub ClearStoredAuth()
    SaveConfigValue CFG_AUTH_TOKEN, ""
    SaveConfigValue CFG_USERNAME, ""
    g_Token = ""
    g_Username = ""
End Sub

Public Sub SaveConfigValue(configKey As String, configValue As String)
    Dim ws As Worksheet
    Dim targetRow As Long
    Set ws = EnsureSheet(CONFIG_SHEET, Hidden:=True)
    targetRow = FindConfigRow(ws, configKey)
    ws.Cells(targetRow, 1).Value = configKey
    ws.Cells(targetRow, 2).Value = configValue
End Sub

Public Function LoadConfigValue(configKey As String) As String
    Dim ws As Worksheet
    On Error GoTo NotFound
    Set ws = ThisWorkbook.Sheets(CONFIG_SHEET)

    Dim targetRow As Long
    targetRow = FindConfigRow(ws, configKey, createIfMissing:=False)
    If targetRow = 0 Then GoTo NotFound

    LoadConfigValue = CStr(ws.Cells(targetRow, 2).Value)
    Exit Function

NotFound:
    LoadConfigValue = ""
End Function

' Гарантировать существование листа
Public Function EnsureSheet(shName As String, Optional Hidden As Boolean = False) As Worksheet
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Sheets(shName)
    On Error GoTo 0
    If ws Is Nothing Then
        Set ws = ThisWorkbook.Sheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        ws.Name = shName
    End If
    If Hidden Then ws.Visible = xlSheetVeryHidden
    Set EnsureSheet = ws
End Function

Public Sub ProtectDataSheet()
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Sheets(DATA_SHEET)
    On Error GoTo 0
    If ws Is Nothing Then Exit Sub

    On Error Resume Next
    ws.Unprotect Password:=DATA_SHEET_PASSWORD
    On Error GoTo 0

    ws.Protect _
        Password:=DATA_SHEET_PASSWORD, _
        UserInterfaceOnly:=True, _
        AllowSorting:=True, _
        AllowFiltering:=True
    ws.EnableSelection = xlUnlockedCells
End Sub

Private Function FindConfigRow(ws As Worksheet, configKey As String, Optional createIfMissing As Boolean = True) As Long
    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    If lastRow < 1 Then lastRow = 1

    Dim i As Long
    For i = 1 To lastRow
        If Trim$(CStr(ws.Cells(i, 1).Value)) = configKey Then
            FindConfigRow = i
            Exit Function
        End If
    Next i

    If createIfMissing Then
        If Len(Trim$(CStr(ws.Cells(1, 1).Value))) = 0 Then
            FindConfigRow = 1
        Else
            FindConfigRow = lastRow + 1
        End If
    Else
        FindConfigRow = 0
    End If
End Function
