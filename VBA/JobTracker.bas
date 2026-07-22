' JobTracker.bas
' VBA module: call local Python scraper to fetch job details for a given URL
Option Explicit

' Configure this to your server (default localhost:5000)
Public Const BASE_SERVER_URL As String = "http://127.0.0.1:5000"

Sub ProcessInputLinks()
    Dim inputWs As Worksheet
    Dim applicationsWs As Worksheet
    Dim linkCol As Long
    Dim statusCol As Long
    Dim processedCol As Long
    Dim errorCol As Long
    Dim appLinkCol As Long
    Dim lastRow As Long
    Dim rowNumber As Long
    Dim added As Long
    Dim duplicateCount As Long
    Dim errorCount As Long
    Dim jobLink As String
    Dim processStatus As String
    Dim response As String
    Dim scrapeError As String

    On Error GoTo setupError
    Set inputWs = ThisWorkbook.Worksheets("Input")
    Set applicationsWs = ThisWorkbook.Worksheets("Applications")
    On Error GoTo 0

    linkCol = FindHeaderColumnOnSheet(inputWs, "Job Link")
    statusCol = FindHeaderColumnOnSheet(inputWs, "Process Status")
    processedCol = FindHeaderColumnOnSheet(inputWs, "Processed At")
    errorCol = FindHeaderColumnOnSheet(inputWs, "Error Message")
    appLinkCol = FindHeaderColumnOnSheet(applicationsWs, "Job link")

    If linkCol = 0 Or statusCol = 0 Or processedCol = 0 Or errorCol = 0 Or appLinkCol = 0 Then
        MsgBox "This workbook is missing one or more Linc columns. Start with the ready-made tracker or check the Excel Workflow section in the README.", vbExclamation
        Exit Sub
    End If

    lastRow = inputWs.Cells(inputWs.Rows.Count, linkCol).End(xlUp).Row
    Application.ScreenUpdating = False

    For rowNumber = 2 To lastRow
        jobLink = Trim(CStr(inputWs.Cells(rowNumber, linkCol).Value))
        processStatus = LCase(Trim(CStr(inputWs.Cells(rowNumber, statusCol).Value)))

        If Len(jobLink) > 0 And (Len(processStatus) = 0 Or processStatus = "pending" Or processStatus = "error") Then
            inputWs.Cells(rowNumber, errorCol).Value = ""

            If ApplicationLinkExists(applicationsWs, appLinkCol, jobLink) Then
                inputWs.Cells(rowNumber, statusCol).Value = "Duplicate"
                duplicateCount = duplicateCount + 1
            Else
                response = GetJobDetailsDirect(jobLink)
                If Len(response) = 0 Then
                    inputWs.Cells(rowNumber, statusCol).Value = "Error"
                    inputWs.Cells(rowNumber, errorCol).Value = "The scraper did not return a result."
                    errorCount = errorCount + 1
                Else
                    scrapeError = ParseJSONKey(response, "error")
                    If Len(scrapeError) > 0 Then
                        inputWs.Cells(rowNumber, statusCol).Value = "Error"
                        inputWs.Cells(rowNumber, errorCol).Value = scrapeError
                        errorCount = errorCount + 1
                    Else
                        AppendJsonToApplications applicationsWs, response, jobLink
                        If JsonNeedsManualReview(response) Then
                            inputWs.Cells(rowNumber, statusCol).Value = "Needs Manual Review"
                        Else
                            inputWs.Cells(rowNumber, statusCol).Value = "Done"
                        End If
                        added = added + 1
                    End If
                End If
            End If
            inputWs.Cells(rowNumber, processedCol).Value = Now
        End If
    Next rowNumber

    Application.ScreenUpdating = True
    ThisWorkbook.Save
    MsgBox "Done. Added " & added & " job(s), found " & duplicateCount & " duplicate(s), and hit " & errorCount & " error(s).", vbInformation
    Exit Sub

setupError:
    Application.ScreenUpdating = True
    MsgBox "This workbook needs Input and Applications sheets. Use the ready-made Linc tracker and try again.", vbExclamation
End Sub

Function GetJobDetailsDirect(jobUrl As String) As String
    Dim projectFolder As String
    Dim pythonExe As String
    Dim scriptPath As String
    Dim command As String
    Dim shell As Object
    Dim process As Object
    Dim output As String
    Dim errorOutput As String

    projectFolder = ThisWorkbook.Path
    scriptPath = projectFolder & "\scrape_job_cli.py"
    If Dir(scriptPath) = "" Then
        projectFolder = CreateObject("Scripting.FileSystemObject").GetParentFolderName(ThisWorkbook.Path)
        scriptPath = projectFolder & "\scrape_job_cli.py"
    End If
    pythonExe = projectFolder & "\.venv\Scripts\python.exe"

    If Dir(scriptPath) = "" Or Dir(pythonExe) = "" Then
        GetJobDetailsDirect = "{""error"":""Could not find the scraper or Python environment.""}"
        Exit Function
    End If

    command = Chr(34) & pythonExe & Chr(34) & " " & _
              Chr(34) & scriptPath & Chr(34) & " " & _
              Chr(34) & jobUrl & Chr(34)

    Set shell = CreateObject("WScript.Shell")
    shell.CurrentDirectory = projectFolder
    Set process = shell.Exec(command)

    Do While process.Status = 0
        DoEvents
        Application.Wait Now + TimeValue("0:00:01")
    Loop

    output = Trim(process.StdOut.ReadAll)
    errorOutput = Trim(process.StdErr.ReadAll)
    If Len(output) > 0 Then
        GetJobDetailsDirect = output
    ElseIf Len(errorOutput) > 0 Then
        GetJobDetailsDirect = "{""error"":""" & JsonEscape(errorOutput) & """}"
    End If
End Function

Function EnsureScraperServer() As Boolean
    Dim projectFolder As String
    Dim pythonExe As String
    Dim appPath As String
    Dim command As String
    Dim attempt As Long
    Dim shell As Object

    If IsScraperServerRunning() Then
        EnsureScraperServer = True
        Exit Function
    End If

    projectFolder = ThisWorkbook.Path
    appPath = projectFolder & "\scraper\app.py"
    If Dir(appPath) = "" Then
        projectFolder = CreateObject("Scripting.FileSystemObject").GetParentFolderName(ThisWorkbook.Path)
        appPath = projectFolder & "\scraper\app.py"
    End If
    pythonExe = projectFolder & "\.venv\Scripts\python.exe"

    If Dir(appPath) = "" Or Dir(pythonExe) = "" Then
        MsgBox "Linc could not find Python or the scraper files. Keep this workbook in the project folder or its outputs folder.", vbExclamation
        Exit Function
    End If

    command = Chr(34) & pythonExe & Chr(34) & " " & Chr(34) & appPath & Chr(34)
    Set shell = CreateObject("WScript.Shell")
    shell.CurrentDirectory = projectFolder
    shell.Run command, 0, False

    For attempt = 1 To 15
        Application.Wait Now + TimeValue("0:00:01")
        DoEvents
        If IsScraperServerRunning() Then
            EnsureScraperServer = True
            Exit Function
        End If
    Next attempt

    MsgBox "Linc did not start. Run python scraper\app.py in PowerShell, then try again.", vbExclamation
End Function

Function IsScraperServerRunning() As Boolean
    On Error GoTo notRunning
    Dim http As Object
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.Open "GET", BASE_SERVER_URL & "/health", False
    http.send
    IsScraperServerRunning = (http.Status = 200)
    Exit Function
notRunning:
    IsScraperServerRunning = False
End Function

Function FindHeaderColumnOnSheet(ws As Worksheet, headerName As String) As Long
    Dim cell As Range
    For Each cell In ws.Range(ws.Cells(1, 1), ws.Cells(1, 50))
        If LCase(Trim(CStr(cell.Value))) = LCase(headerName) Then
            FindHeaderColumnOnSheet = cell.Column
            Exit Function
        End If
    Next cell
End Function

Sub SetCellByHeader(ws As Worksheet, rowNumber As Long, headerName As String, value As Variant)
    Dim columnNumber As Long
    columnNumber = FindHeaderColumnOnSheet(ws, headerName)
    If columnNumber > 0 Then ws.Cells(rowNumber, columnNumber).Value = value
End Sub

Sub AppendJsonToApplications(ws As Worksheet, json As String, originalLink As String)
    Dim rowNumber As Long
    Dim dateApplied As String
    Dim followUp As String
    Dim linkColumn As Long
    Dim linkCell As Range

    linkColumn = FindHeaderColumnOnSheet(ws, "Job link")
    rowNumber = FindFirstEmptyApplicationRow(ws, linkColumn)
    dateApplied = ParseJSONKey(json, "date_applied")
    followUp = ParseJSONKey(json, "follow_up")

    If Len(dateApplied) = 0 Then dateApplied = Format(Date, "mm/dd/yyyy")

    SetCellByHeader ws, rowNumber, "Date Applied", dateApplied
    SetCellByHeader ws, rowNumber, "Company", ParseJSONKey(json, "company")
    SetCellByHeader ws, rowNumber, "Job Title", ParseJSONKey(json, "job_title")
    Set linkCell = ws.Cells(rowNumber, linkColumn)
    linkCell.Value = "Open job"
    ws.Hyperlinks.Add Anchor:=linkCell, Address:=originalLink, TextToDisplay:="Open job"
    SetCellByHeader ws, rowNumber, "Status", ""
    SetCellByHeader ws, rowNumber, "Location", ParseJSONKey(json, "location")
    SetCellByHeader ws, rowNumber, "Work Type", ParseJSONKey(json, "work_type")
    SetCellByHeader ws, rowNumber, "Salary Range", ParseJSONKey(json, "salary")
    SetCellByHeader ws, rowNumber, "Follow-up", followUp
    SetCellByHeader ws, rowNumber, "Source", ParseJSONKey(json, "source")
End Sub

Function FindFirstEmptyApplicationRow(ws As Worksheet, linkColumn As Long) As Long
    Dim rowNumber As Long
    Dim lastTableRow As Long

    lastTableRow = 101
    If ws.ListObjects.Count > 0 Then
        lastTableRow = ws.ListObjects(1).Range.Row + ws.ListObjects(1).Range.Rows.Count - 1
    End If

    For rowNumber = 2 To lastTableRow
        If Len(Trim(CStr(ws.Cells(rowNumber, linkColumn).Value))) = 0 Then
            FindFirstEmptyApplicationRow = rowNumber
            Exit Function
        End If
    Next rowNumber
    FindFirstEmptyApplicationRow = lastTableRow + 1
End Function

Function ApplicationLinkExists(ws As Worksheet, linkColumn As Long, jobLink As String) As Boolean
    Dim rowNumber As Long
    Dim lastRow As Long
    Dim cell As Range
    Dim existingLink As String
    Dim companyValue As String
    Dim titleValue As String
    Dim companyColumn As Long
    Dim titleColumn As Long

    lastRow = ws.Cells(ws.Rows.Count, linkColumn).End(xlUp).Row
    companyColumn = FindHeaderColumnOnSheet(ws, "Company")
    titleColumn = FindHeaderColumnOnSheet(ws, "Job Title")
    For rowNumber = 2 To lastRow
        Set cell = ws.Cells(rowNumber, linkColumn)
        existingLink = Trim(CStr(cell.Value))
        If cell.Hyperlinks.Count > 0 Then existingLink = cell.Hyperlinks(1).Address
        If StrComp(existingLink, jobLink, vbTextCompare) = 0 Then
            companyValue = LCase(Trim(CStr(ws.Cells(rowNumber, companyColumn).Value)))
            titleValue = LCase(Trim(CStr(ws.Cells(rowNumber, titleColumn).Value)))
            If companyValue = "" Or companyValue = "n/a" Or titleValue = "" Or titleValue = "n/a" Or titleValue = "error" Then
                If cell.Hyperlinks.Count > 0 Then cell.Hyperlinks.Delete
                ws.Range(ws.Cells(rowNumber, 1), ws.Cells(rowNumber, 10)).ClearContents
                ApplicationLinkExists = False
            Else
                ApplicationLinkExists = True
            End If
            Exit Function
        End If
    Next rowNumber
End Function

Function JsonNeedsManualReview(json As String) As Boolean
    Dim value As String
    Dim key As Variant
    For Each key In Array("company", "job_title", "location")
        value = LCase(Trim(ParseJSONKey(json, CStr(key))))
        If Len(value) = 0 Or value = "n/a" Then
            JsonNeedsManualReview = True
            Exit Function
        End If
    Next key
End Function

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
        MsgBox "Linc did not answer. Make sure the local app is running, then try again."
        Exit Sub
    End If
    Dim json As String
    json = resp

    ' Simple JSON parsing for known keys. For robust parsing, install VBA-JSON and use ParseJson(json).
    On Error GoTo fallback
    WriteParsedFieldsToRow r, json
    MsgBox "Job details added. Check the row before saving."
    Exit Sub
fallback:
    MsgBox "Excel could not read Linc's response. Try VBA-JSON for fuller JSON support: https://github.com/VBA-tools/VBA-JSON"
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
    ' Expected keys: company, job_title, job_link, location, salary, status, work_type, source
    Dim vCompany As String: vCompany = ParseJSONKey(json, "company")
    Dim vTitle As String: vTitle = ParseJSONKey(json, "job_title")
    Dim vJobLink As String: vJobLink = ParseJSONKey(json, "job_link")
    Dim vLocation As String: vLocation = ParseJSONKey(json, "location")
    Dim vWorkType As String: vWorkType = ParseJSONKey(json, "work_type")
    Dim vSalary As String: vSalary = ParseJSONKey(json, "salary")
    Dim vSource As String: vSource = ParseJSONKey(json, "source")

    WriteToHeader r, "Company", vCompany
    WriteToHeader r, "Job Title", vTitle
    If Len(vJobLink) > 0 Then WriteToHeader r, "Job link", vJobLink
    WriteToHeader r, "Location", vLocation
    WriteToHeader r, "Work Type", vWorkType
    WriteToHeader r, "Salary Range", vSalary
    WriteToHeader r, "Source", vSource
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
