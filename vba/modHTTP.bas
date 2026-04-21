Attribute VB_Name = "modHTTP"
Option Explicit

' ============================================================
'  modHTTP - HTTP-запросы через WinHTTP
' ============================================================

' Результат HTTP-запроса
Public Type HttpResponse
    StatusCode As Long
    Body As String
    Success As Boolean
End Type

' GET-запрос с авторизацией
Public Function HttpGet(url As String) As HttpResponse
    Dim resp As HttpResponse
    Dim xhr As Object
    Set xhr = CreateObject("MSXML2.XMLHTTP.6.0")

    On Error GoTo ErrHandler
    xhr.Open "GET", url, False
    xhr.setRequestHeader "Content-Type", "application/json; charset=utf-8"
    If Len(g_Token) > 0 Then
        xhr.setRequestHeader "Authorization", "Bearer " & g_Token
    End If
    xhr.send

    resp.StatusCode = xhr.Status
    resp.Body = xhr.responseText
    resp.Success = (xhr.Status >= 200 And xhr.Status < 300)
    HttpGet = resp
    Exit Function

ErrHandler:
    resp.StatusCode = 0
    resp.Body = "Connection error: " & Err.Description
    resp.Success = False
    HttpGet = resp
End Function

' POST-запрос с JSON-телом и авторизацией
Public Function HttpPost(url As String, jsonBody As String) As HttpResponse
    Dim resp As HttpResponse
    Dim xhr As Object
    Set xhr = CreateObject("MSXML2.XMLHTTP.6.0")

    On Error GoTo ErrHandler
    xhr.Open "POST", url, False
    xhr.setRequestHeader "Content-Type", "application/json; charset=utf-8"
    If Len(g_Token) > 0 Then
        xhr.setRequestHeader "Authorization", "Bearer " & g_Token
    End If

    ' Для BSTR MSXML сам отправляет тело как UTF-8.
    xhr.send jsonBody

    resp.StatusCode = xhr.Status
    resp.Body = xhr.responseText
    resp.Success = (xhr.Status >= 200 And xhr.Status < 300)
    HttpPost = resp
    Exit Function

ErrHandler:
    resp.StatusCode = 0
    resp.Body = "Connection error: " & Err.Number & " / " & Err.Description
    resp.Success = False
    HttpPost = resp
End Function
