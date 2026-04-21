Attribute VB_Name = "modJSON"
Option Explicit

Private m_json As String
Private m_pos As Long

' ============================================================
'  modJSON - Минимальный JSON парсер/билдер для VBA
'  Поддерживает: объекты, массивы, строки, числа, bool, null
'  Не требует внешних библиотек (ScriptControl и т.п.)
' ============================================================

' --- JSON Value Types ---
Public Enum JsonType
    jtNull = 0
    jtString = 1
    jtNumber = 2
    jtBool = 3
    jtObject = 4
    jtArray = 5
End Enum

' --- JSON Node ---
' Для простоты используем Dictionary (Scripting.Dictionary)
' Объект: Dictionary с ключами-строками
' Массив: Collection
' Скаляры: обёртка через JsonWrap

Public Type JsonWrap
    vType As JsonType
    vStr As String
    vNum As Double
    vBool As Boolean
End Type

' ============================================================
'  СТРОИМ JSON
' ============================================================

' Экранировать строку для JSON
Public Function JsonEsc(s As String) As String
    Dim r As String
    r = Replace(s, "\", "\\")
    r = Replace(r, """", "\""")
    r = Replace(r, vbCr, "\r")
    r = Replace(r, vbLf, "\n")
    r = Replace(r, vbTab, "\t")
    JsonEsc = r
End Function

' Обернуть строку в кавычки
Public Function JsonStr(s As String) As String
    JsonStr = """" & JsonEsc(s) & """"
End Function

' Значение -> JSON строка
Public Function JsonVal(v As Variant) As String
    If IsNull(v) Or IsEmpty(v) Then
        JsonVal = "null"
    ElseIf VarType(v) = vbBoolean Then
        JsonVal = IIf(v, "true", "false")
    ElseIf IsNumeric(v) And VarType(v) <> vbString Then
        JsonVal = CStr(v)
        ' Заменяем запятую на точку (для локалей с запятой)
        JsonVal = Replace(JsonVal, ",", ".")
    ElseIf VarType(v) = vbDate Then
        JsonVal = JsonStr(Format(v, "yyyy-mm-ddThh:nn:ss") & "Z")
    Else
        JsonVal = JsonStr(CStr(v))
    End If
End Function

' Начать объект
Public Function JsonObjStart() As String
    JsonObjStart = "{"
End Function

' Добавить пару ключ:значение в объект
Public Function JsonObjAdd(existing As String, key As String, v As Variant) As String
    Dim pair As String
    pair = JsonStr(key) & ":" & JsonVal(v)
    If Len(existing) > 1 Then
        JsonObjAdd = existing & "," & pair
    Else
        JsonObjAdd = existing & pair
    End If
End Function

' Добавить пару ключ:rawjson (уже сериализованное значение)
Public Function JsonObjAddRaw(existing As String, key As String, rawJson As String) As String
    Dim pair As String
    pair = JsonStr(key) & ":" & rawJson
    If Len(existing) > 1 Then
        JsonObjAddRaw = existing & "," & pair
    Else
        JsonObjAddRaw = existing & pair
    End If
End Function

' Закрыть объект
Public Function JsonObjEnd(existing As String) As String
    JsonObjEnd = existing & "}"
End Function

' Построить массив из коллекции JSON-строк
Public Function JsonArrayFromColl(coll As Collection) As String
    Dim result As String
    Dim i As Long
    result = "["
    For i = 1 To coll.Count
        If i > 1 Then result = result & ","
        result = result & coll(i)
    Next i
    result = result & "]"
    JsonArrayFromColl = result
End Function

' ============================================================
'  ПАРСИМ JSON
' ============================================================

' Главная функция парсинга - возвращает Dictionary (объект) или Collection (массив)
Public Function JsonParse(jsonString As String) As Object
    m_json = jsonString
    m_pos = 1
    SkipWhitespace
    Set JsonParse = ParseValue()
End Function

' Получить значение из распарсенного объекта (Dictionary) по ключу
' Возвращает Variant (строка, число, bool, Null, или вложенный Dictionary/Collection)
Public Function JsonGet(obj As Object, key As String) As Variant
    Dim d As Object ' Scripting.Dictionary
    Set d = obj
    If d.Exists(key) Then
        If IsObject(d(key)) Then
            Set JsonGet = d(key)
        Else
            JsonGet = d(key)
        End If
    Else
        JsonGet = Null
    End If
End Function

' Получить строку из распарсенного объекта
Public Function JsonGetStr(obj As Object, key As String, Optional default_val As String = "") As String
    Dim v As Variant
    v = JsonGet(obj, key)
    If IsNull(v) Then
        JsonGetStr = default_val
    Else
        JsonGetStr = CStr(v)
    End If
End Function

' Получить число из распарсенного объекта
Public Function JsonGetLng(obj As Object, key As String, Optional default_val As Long = 0) As Long
    Dim v As Variant
    v = JsonGet(obj, key)
    If IsNull(v) Then
        JsonGetLng = default_val
    ElseIf IsNumeric(v) Then
        JsonGetLng = CLng(v)
    Else
        JsonGetLng = default_val
    End If
End Function

' Получить массив (Collection) из объекта
Public Function JsonGetArr(obj As Object, key As String) As Collection
    Dim v As Variant
    On Error GoTo ReturnEmpty
    Set v = JsonGet(obj, key)
    If TypeName(v) = "Collection" Then
        Set JsonGetArr = v
    Else
        Set JsonGetArr = New Collection
    End If
    Exit Function
ReturnEmpty:
    Set JsonGetArr = New Collection
End Function

' --- Внутренние функции парсера ---

Private Function ParseValue() As Variant
    SkipWhitespace
    Dim ch As String
    ch = Mid$(m_json, m_pos, 1)

    Select Case ch
        Case "{"
            Set ParseValue = ParseObject()
        Case "["
            Set ParseValue = ParseArray()
        Case """"
            ParseValue = ParseString()
        Case "t", "f"
            ParseValue = ParseBool()
        Case "n"
            ParseValue = ParseNull()
        Case Else
            ParseValue = ParseNumber()
    End Select
End Function

Private Function ParseObject() As Object
    Dim d As Object
    Set d = CreateObject("Scripting.Dictionary")
    d.CompareMode = vbTextCompare

    m_pos = m_pos + 1   ' skip {
    SkipWhitespace

    If Mid$(m_json, m_pos, 1) = "}" Then
        m_pos = m_pos + 1
        Set ParseObject = d
        Exit Function
    End If

    Do
        SkipWhitespace
        Dim key As String
        key = ParseString()
        SkipWhitespace
        m_pos = m_pos + 1   ' skip :
        SkipWhitespace

        Dim val As Variant
        If Mid$(m_json, m_pos, 1) = "{" Or Mid$(m_json, m_pos, 1) = "[" Then
            Set val = ParseValue()
            Set d(key) = val
        Else
            val = ParseValue()
            If IsNull(val) Then
                d(key) = Null
            Else
                d(key) = val
            End If
        End If

        SkipWhitespace
        If Mid$(m_json, m_pos, 1) = "," Then
            m_pos = m_pos + 1
        Else
            Exit Do
        End If
    Loop

    m_pos = m_pos + 1   ' skip }
    Set ParseObject = d
End Function

Private Function ParseArray() As Collection
    Dim coll As New Collection

    m_pos = m_pos + 1   ' skip [
    SkipWhitespace

    If Mid$(m_json, m_pos, 1) = "]" Then
        m_pos = m_pos + 1
        Set ParseArray = coll
        Exit Function
    End If

    Do
        SkipWhitespace
        Dim val As Variant
        If Mid$(m_json, m_pos, 1) = "{" Or Mid$(m_json, m_pos, 1) = "[" Then
            Dim objVal As Object
            Set objVal = ParseValue()
            coll.Add objVal
        Else
            val = ParseValue()
            coll.Add val
        End If

        SkipWhitespace
        If Mid$(m_json, m_pos, 1) = "," Then
            m_pos = m_pos + 1
        Else
            Exit Do
        End If
    Loop

    m_pos = m_pos + 1   ' skip ]
    Set ParseArray = coll
End Function

Private Function ParseString() As String
    m_pos = m_pos + 1   ' skip opening "
    Dim result As String
    result = ""
    Dim ch As String

    Do While m_pos <= Len(m_json)
        ch = Mid$(m_json, m_pos, 1)
        If ch = "\" Then
            m_pos = m_pos + 1
            ch = Mid$(m_json, m_pos, 1)
            Select Case ch
                Case """", "\", "/"
                    result = result & ch
                Case "n"
                    result = result & vbLf
                Case "r"
                    result = result & vbCr
                Case "t"
                    result = result & vbTab
                Case "u"
                    ' Unicode escape \uXXXX
                    Dim hex4 As String
                    hex4 = Mid$(m_json, m_pos + 1, 4)
                    result = result & ChrW(CLng("&H" & hex4))
                    m_pos = m_pos + 4
            End Select
        ElseIf ch = """" Then
            m_pos = m_pos + 1
            ParseString = result
            Exit Function
        Else
            result = result & ch
        End If
        m_pos = m_pos + 1
    Loop

    ParseString = result
End Function

Private Function ParseNumber() As Variant
    Dim start As Long
    start = m_pos

    If Mid$(m_json, m_pos, 1) = "-" Then m_pos = m_pos + 1

    Do While m_pos <= Len(m_json)
        Dim ch As String
        ch = Mid$(m_json, m_pos, 1)
        If ch Like "[0-9]" Or ch = "." Or ch = "e" Or ch = "E" Or ch = "+" Or ch = "-" Then
            If start = m_pos And (ch = "+" Or ch = "-") Then Exit Do
            m_pos = m_pos + 1
        Else
            Exit Do
        End If
    Loop

    Dim numStr As String
    numStr = Mid$(m_json, start, m_pos - start)
    ' Учитываем локаль
    numStr = Replace(numStr, ".", Application.DecimalSeparator)

    If InStr(numStr, Application.DecimalSeparator) > 0 Or InStr(LCase(numStr), "e") > 0 Then
        ParseNumber = CDbl(numStr)
    Else
        On Error Resume Next
        ParseNumber = CLng(numStr)
        If Err.Number <> 0 Then
            Err.Clear
            ParseNumber = CDbl(numStr)
        End If
        On Error GoTo 0
    End If
End Function

Private Function ParseBool() As Boolean
    If Mid$(m_json, m_pos, 4) = "true" Then
        ParseBool = True
        m_pos = m_pos + 4
    Else
        ParseBool = False
        m_pos = m_pos + 5
    End If
End Function

Private Function ParseNull() As Variant
    m_pos = m_pos + 4
    ParseNull = Null
End Function

Private Sub SkipWhitespace()
    Do While m_pos <= Len(m_json)
        Select Case Mid$(m_json, m_pos, 1)
            Case " ", vbCr, vbLf, vbTab
                m_pos = m_pos + 1
            Case Else
                Exit Do
        End Select
    Loop
End Sub
