# Troubleshooting

## Linc Does Not Open

Linc runs only while its local launcher is open. If `http://127.0.0.1:5050/`
does not open, first double-click `Open_Linc_Beta.vbs` from this project folder
and wait a few seconds for the Linc window to appear.

When working from the source project, always use `Open_Linc_Beta.vbs`. It uses
the project's own Python environment. Avoid starting Linc with a bare `python`
command, because Windows can choose a different Python installation that does
not have the packages Linc needs.

If the launcher says packages are missing, finish the local setup again so the
`.venv` folder is rebuilt. The technical startup details are saved at:

```text
%LOCALAPPDATA%\Linc\logs\desktop_startup_error.log
```

For the portable Windows beta, use the `Linc.exe` included in the extracted
release folder instead. It does not need a separate Python installation.

## Playwright Browser Is Missing

Install the Chromium files Linc uses:

```powershell
python -m playwright install chromium
```

## A Job Board Blocks Scraping

Look for the same role on the company's career site first. If you can open the blocked page yourself, capture it with the Chrome extension in `browser_extension/linc_capture`, then load that capture in Linc.

## Monster Does Not Work

Use the employer career page that Monster opens or links to. Linc treats Monster search pages and many Monster job pages as limited because they do not provide one reliable posting.

## Excel Tracker Will Not Update

Close the workbook in Excel, then select `Update tracker` again. If the browser still cannot save over that file, Linc creates an updated copy instead.

## A Row Says Review

`Review` means Linc is unsure about at least one field. Read the reason shown on the row, then retry it, fix the fields yourself, or flag it so the scraper problem can be investigated.

## Browser Capture Looks Wrong

Make sure the real job posting is visible before you capture it. Finish any human check and wait for the page to load, then try again. If Linc shows suggestions under a field, choose the best one or type the correct value yourself.
