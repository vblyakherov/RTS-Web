Attribute VB_Name = "modDirty"
Option Explicit

' ============================================================
'  modDirty - Отслеживание изменённых ячеек
'
'  Стратегия: скрытый лист _DirtyTracker хранит строки вида:
'    колонка A = row number (строка на листе Data)
'  При синхронизации считываем уникальные строки,
'  после успешной синхронизации очищаем трекер.
' ============================================================

Private m_Tracking As Boolean  ' флаг: отслеживать ли изменения

' Включить отслеживание
Public Sub DirtyTrackOn()
    m_Tracking = True
End Sub

' Выключить отслеживание (при загрузке данных с сервера)
Public Sub DirtyTrackOff()
    m_Tracking = False
End Sub

Public Function IsDirtyTracking() As Boolean
    IsDirtyTracking = m_Tracking
End Function

' Вызывается из Worksheet_Change листа Data
Public Sub MarkDirty(Target As Range)
    If Not m_Tracking Then Exit Sub

    ' Игнорируем первую строку (заголовки)
    If Target.Row < 2 Then Exit Sub

    Dim ws As Worksheet
    Set ws = EnsureSheet(DIRTY_SHEET, Hidden:=True)

    ' Записываем уникальные номера строк
    Dim r As Range
    For Each r In Target.Rows
        If r.Row >= 2 Then
            Dim nextRow As Long
            nextRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row + 1
            ws.Cells(nextRow, 1).Value = r.Row
        End If
    Next r
End Sub

' Получить массив уникальных номеров строк, которые были изменены
Public Function GetDirtyRows() As Collection
    Dim result As New Collection
    Dim seen As Object
    Set seen = CreateObject("Scripting.Dictionary")

    On Error GoTo NoSheet
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets(DIRTY_SHEET)
    On Error GoTo 0

    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row

    Dim i As Long
    For i = 1 To lastRow
        Dim rowNum As Variant
        rowNum = ws.Cells(i, 1).Value
        If Not IsEmpty(rowNum) And IsNumeric(rowNum) Then
            Dim key As String
            key = CStr(CLng(rowNum))
            If Not seen.Exists(key) Then
                seen.Add key, True
                result.Add CLng(rowNum)
            End If
        End If
    Next i

NoSheet:
    Set GetDirtyRows = result
End Function

' Очистить все dirty-маркеры
Public Sub ClearDirty()
    On Error Resume Next
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets(DIRTY_SHEET)
    If Not ws Is Nothing Then
        ws.Cells.Clear
    End If
    On Error GoTo 0
End Sub

' Удалить конкретные строки из dirty-трекера
Public Sub RemoveDirtyRow(rowNum As Long)
    On Error Resume Next
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets(DIRTY_SHEET)
    If ws Is Nothing Then Exit Sub
    On Error GoTo 0

    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row

    ' Удаляем снизу вверх
    Dim i As Long
    For i = lastRow To 1 Step -1
        If ws.Cells(i, 1).Value = rowNum Then
            ws.Rows(i).Delete
        End If
    Next i
End Sub
