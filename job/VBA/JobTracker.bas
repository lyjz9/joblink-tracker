' JobTracker.bas
' VBA module: call local Python scraper to fetch job details for a given URL
Option Explicit

' Configure this to your server (default localhost:5000)
Public Const BASE_SERVER_URL As String = "http://127.0.0.1:5000"

Sub FetchJobDetailsForActiveRow()
    Dim r As Range
    Set r = ActiveCell.EntireRow
    FetchJobDetailsForRow r
End Sub

Sub FetchJobDetailsForSelection()
    Dim linkCol As Long
    linkCol = FindHeaderColumn("Job link")
    If linkCol = 0 Then
        MsgBox "Could not find 'Job link' header."
        Exit Sub
    End If

    Dim seen As Object
    Set seen = CreateObject("Scripting.Dictionary")
    Dim c As Range
    For Each c In Selection.Cells
        If c.Column = linkCol And c.Row > 1 And Not seen.Exists(CStr(c.Row)) Then
            seen.Add CStr(c.Row), True
            FetchJobDetailsForRow c.EntireRow
        End If
    Next c
End Sub

Sub FetchJobDetailsForRow(r As Range)
    Dim linkCol As Long
    linkCol = FindHeaderColumn("Job link")
    If linkCol = 0 Then
        MsgBox "Could not find 'Job link' header."
        Exit Sub
    End If
    Dim jobLink As String
    jobLink = Trim(CStr(r.Cells(1, linkCol).Value))
    If Len(jobLink) = 0 Then
        MsgBox "No job link found in this row."
        Exit Sub
    End If
    Dim resp As String
    resp = GetJobDetailsFromServer(jobLink)
    If Len(resp) = 0 Then
        MsgBox "No response from server. Make sure the Python scraper is running."
        Exit Sub
    End If
    Dim json As String
    json = resp

    ' Simple JSON parsing for known keys. For robust parsing, install VBA-JSON and use ParseJson(json).
    On Error GoTo fallback
    WriteParsedFieldsToRow r, json
    MsgBox "Job details populated (best-effort)."
    Exit Sub
fallback:
    MsgBox "Failed to parse response. Consider installing VBA-JSON: https://github.com/VBA-tools/VBA-JSON"
End Sub

Function FindHeaderColumn(headerName As String) As Long
    Dim ws As Worksheet
    Set ws = ActiveSheet
    Dim c As Range
    For Each c In ws.Range(ws.Cells(1, 1), ws.Cells(1, 50))
        If Trim(CStr(c.Value)) = headerName Then
            FindHeaderColumn = c.Column
            Exit Function
        End If
    Next c
    FindHeaderColumn = 0
End Function

Function GetJobDetailsFromServer(jobUrl As String) As String
    Dim http As Object
    Set http = CreateObject("MSXML2.XMLHTTP")
    Dim endpoint As String
    endpoint = BASE_SERVER_URL & "/scrape"
    http.Open "POST", endpoint, False
    http.setRequestHeader "Content-Type", "application/json"
    Dim payload As String
    payload = "{""url"": """ & JsonEscape(jobUrl) & """}"
    http.send payload
    If http.Status = 200 Then
        GetJobDetailsFromServer = http.responseText
    Else
        GetJobDetailsFromServer = ""
    End If
End Function

Sub WriteParsedFieldsToRow(r As Range, json As String)
    ' Expected keys: company, job_title, job_link, location, salary, status, work_type, source, ai_note, skills
    Dim vCompany As String: vCompany = ParseJSONKey(json, "company")
    Dim vTitle As String: vTitle = ParseJSONKey(json, "job_title")
    Dim vJobLink As String: vJobLink = ParseJSONKey(json, "job_link")
    Dim vLocation As String: vLocation = ParseJSONKey(json, "location")
    Dim vWorkType As String: vWorkType = ParseJSONKey(json, "work_type")
    Dim vSalary As String: vSalary = ParseJSONKey(json, "salary")
    Dim vSource As String: vSource = ParseJSONKey(json, "source")
    Dim vAI As String: vAI = ParseJSONKey(json, "ai_note")
    Dim vSkills As String: vSkills = ParseJSONKey(json, "skills")

    WriteToHeader r, "Company", vCompany
    WriteToHeader r, "Job Title", vTitle
    If Len(vJobLink) > 0 Then WriteToHeader r, "Job link", vJobLink
    WriteToHeader r, "Location", vLocation
    WriteToHeader r, "Work Type", vWorkType
    WriteToHeader r, "Salary Range", vSalary
    WriteToHeader r, "Source", vSource
    WriteToHeader r, "AI Note", vAI
    WriteToHeader r, "Skills", vSkills
End Sub

Sub WriteToHeader(r As Range, headerName As String, value As String)
    Dim col As Long
    col = FindHeaderColumn(headerName)
    If col <> 0 Then
        r.Cells(1, col).Value = value
    End If
End Sub

Function ParseJSONKey(json As String, key As String) As String
    Dim pattern As String
    pattern = Chr(34) & key & Chr(34)
    Dim startPos As Long
    startPos = InStr(1, json, pattern)
    If startPos = 0 Then Exit Function
    Dim colonPos As Long
    colonPos = InStr(startPos, json, ":")
    If colonPos = 0 Then Exit Function
    Dim quotePos As Long
    quotePos = InStr(colonPos, json, Chr(34))
    If quotePos = 0 Then Exit Function
    Dim i As Long: i = quotePos + 1
    Dim ch As String
    Dim out As String: out = ""
    Do While i <= Len(json)
        ch = Mid(json, i, 1)
        If ch = Chr(34) Then
            If Mid(json, i - 1, 1) = "\" Then
                out = out & Chr(34)
            Else
                Exit Do
            End If
        ElseIf ch = "\" And i < Len(json) Then
            i = i + 1
            ch = Mid(json, i, 1)
            If ch = "n" Then
                out = out & vbLf
            ElseIf ch = "r" Then
                out = out & vbCr
            ElseIf ch = "t" Then
                out = out & vbTab
            Else
                out = out & ch
            End If
        Else
            out = out & ch
        End If
        i = i + 1
    Loop
    ParseJSONKey = out
End Function

Function JsonEscape(value As String) As String
    Dim out As String
    out = Replace(value, "\", "\\")
    out = Replace(out, Chr(34), "\" & Chr(34))
    out = Replace(out, vbCrLf, "\n")
    out = Replace(out, vbCr, "\n")
    out = Replace(out, vbLf, "\n")
    JsonEscape = out
End Function
