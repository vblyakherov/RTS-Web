VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
END
Attribute VB_Name = "ThisWorkbook"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = True
Option Explicit

' ============================================================
'  При открытии книги:
'  - Загружаем last_sync_at
'  - Включаем отслеживание изменений
' ============================================================

Private Sub Workbook_Open()
    LoadStoredSession
    ProtectDataSheet
    DirtyTrackOn
End Sub
