Attribute VB_Name = "modAuth"
Option Explicit

' ============================================================
'  modAuth - Аутентификация (логин, хранение токена)
' ============================================================

' Показать диалог логина и получить JWT-токен
Public Function DoLogin() As Boolean
    Dim username As String
    Dim password As String

    ' Если уже есть токен, проверяем его
    If Len(g_Token) = 0 Then
        LoadAuthToken
    End If
    If Len(g_Username) = 0 Then
        LoadUsername
    End If

    If Len(g_Token) > 0 Then
        If CheckToken() Then
            DoLogin = True
            Exit Function
        End If
        ClearStoredAuth
    End If

    ' Запрашиваем логин/пароль
    username = InputBox("Username:", "Sign in", g_Username)
    If Len(username) = 0 Then
        DoLogin = False
        Exit Function
    End If

    password = InputBox("Password:", "Sign in")
    If Len(password) = 0 Then
        DoLogin = False
        Exit Function
    End If

    ' Формируем JSON
    Dim body As String
    body = JsonObjStart()
    body = JsonObjAdd(body, "username", username)
    body = JsonObjAdd(body, "password", password)
    body = JsonObjEnd(body)

    ' Отправляем
    Dim resp As HttpResponse
    resp = HttpPost(FullUrl(EP_LOGIN), body)

    If Not resp.Success Then
        If resp.StatusCode = 401 Then
            MsgBox "Invalid username or password.", vbExclamation, "Sign in error"
        ElseIf resp.StatusCode = 403 Then
            MsgBox "Account is disabled.", vbExclamation, "Access denied"
        Else
            MsgBox "Server connection error:" & vbCrLf & _
                   "HTTP " & resp.StatusCode & vbCrLf & resp.Body, _
                   vbCritical, "Connection error"
        End If
        DoLogin = False
        Exit Function
    End If

    ' Парсим ответ
    Dim parsed As Object
    Set parsed = JsonParse(resp.Body)
    SaveAuthToken JsonGetStr(parsed, "access_token")
    SaveUsername username

    If Len(g_Token) = 0 Then
        MsgBox "Server did not return an access token.", vbCritical, "Sign in error"
        DoLogin = False
        Exit Function
    End If

    DoLogin = True
End Function

' Проверить, жив ли текущий токен (GET /auth/me)
Public Function CheckToken() As Boolean
    Dim resp As HttpResponse
    resp = HttpGet(FullUrl("/auth/me"))
    CheckToken = resp.Success
End Function

' Сбросить авторизацию
Public Sub Logout()
    ClearStoredAuth
End Sub
