# Windows Desktop Beta

The Windows beta puts the app, scraper, Excel tools, Python, and Chromium in one portable folder. A tester can open it without installing Python, setting up a virtual environment, using PowerShell, running Docker, or paying for hosting.

## What Testers Download

The build creates `JobLink-Tracker-Windows.zip`. Extract it, open the `JobLink Tracker` folder, and double-click `JobLink Tracker.exe`.

The executable:

1. Starts the private local app at `http://127.0.0.1:5050`.
2. Opens the existing JobLink interface in the default browser.
3. Shows a small window with **Open JobLink** and **Stop** buttons.
4. Stops JobLink when that window closes.

JobLink always uses port `5050` so the Chrome capture extension knows where to send a page. If another program already uses that port, the launcher explains the conflict and stops.

## Build In GitHub Without Docker

After `.github/workflows/build-windows-desktop.yml` is merged into `main`:

1. Open the repository's **Actions** tab.
2. Select **Build Windows desktop beta**.
3. Select **Run workflow**.
4. Wait for the Windows build to finish.
5. Download the `JobLink-Tracker-Windows` artifact.

The workflow installs Python 3.12 and the pinned packages, downloads Playwright's Chromium headless shell, builds the app with PyInstaller, includes the ready-made Excel template, and keeps the ZIP as an Actions artifact for 14 days.

## Local Maintainer Build

Maintainers can also build with Python 3.12:

```powershell
.\scripts\build_desktop.ps1 -Python py
```

The build sets `PLAYWRIGHT_BROWSERS_PATH=0`, Playwright's supported way to bundle Chromium with PyInstaller. It also uses `--only-shell` because JobLink runs Chromium in the background and does not need the second visible-browser executable.

Build output is written to:

```text
dist\JobLink Tracker\
dist\JobLink-Tracker-Windows.zip
```

The `build/` and `dist/` directories are ignored by Git and should not be committed.

## Windows Warning

The beta executable is unsigned. Windows SmartScreen may show **Windows protected your PC** because the file has no paid code-signing certificate or established download reputation.

Only use a ZIP downloaded from this GitHub repository. On the SmartScreen prompt, select **More info**, check that the file is `JobLink Tracker.exe`, and then choose **Run anyway**. Do not bypass the warning for a copy from an email, chat, or another download site.

## Data And Logs

Scraping and workbook updates happen on the tester's computer. Diagnostic files are stored under:

```text
%LOCALAPPDATA%\JobLink Tracker\logs
```

JobLink opens uploaded workbooks temporarily and returns the updated copy through the local browser. Results stay in that browser's local storage until its site data is cleared.

The app does not install a Windows service, edit the registry, or create an online account. Delete the extracted folder to remove the app; delete the local log folder separately if you no longer need it.

## Beta Limitations

- The first package targets 64-bit Windows only.
- Chromium makes the ZIP much larger than a normal Python utility.
- The unsigned executable may trigger SmartScreen or antivirus reputation checks.
- Closing the control window during an active scrape may take several seconds while browser work ends.
- Sites that block automation can still block the scraper. The desktop package does not bypass website security.
- The Chrome capture extension remains a separate optional installation for blocked pages.

## Release Check

Before sharing a desktop build:

1. Extract the ZIP into a new folder.
2. Start `JobLink Tracker.exe` without Python active.
3. Confirm `/health` and `/ready` respond successfully.
4. Scrape one current company career-page link.
5. Download a new tracker and open it in Excel.
6. Upload the starter template and update it with one reviewed result.
7. Close the control window and confirm port `5050` is released.
8. Start the executable a second time and confirm it opens normally.
