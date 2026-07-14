# Windows Desktop Beta

The desktop beta packages the existing Flask interface, scraper, Excel tools, Python runtime, and Playwright Chromium into one portable Windows folder. Testers do not need Python, a virtual environment, PowerShell, Docker, or a hosting account.

## What Testers Download

The build produces `JobLink-Tracker-Windows.zip`. After extracting it, the tester opens the `JobLink Tracker` folder and double-clicks `JobLink Tracker.exe`.

The executable:

1. Starts the private local app at `http://127.0.0.1:5050`.
2. Opens the existing JobLink interface in the default browser.
3. Shows a small control window with **Open JobLink** and **Stop** buttons.
4. Stops the local server when the tester closes the control window.

Port `5050` stays fixed so the optional Chrome capture extension continues to work. If another program is already using that port, the launcher shows an error instead of opening the wrong application.

## Build In GitHub Without Docker

After `.github/workflows/build-windows-desktop.yml` is merged into `main`:

1. Open the repository's **Actions** tab.
2. Select **Build Windows desktop beta**.
3. Select **Run workflow**.
4. Wait for the Windows build to finish.
5. Download the `JobLink-Tracker-Windows` artifact.

The workflow installs Python 3.12, installs the pinned project packages, downloads the Playwright Chromium headless shell, runs PyInstaller, includes the blank Excel template, and uploads the ZIP for 14 days.

## Local Maintainer Build

Maintainers can also build with Python 3.12:

```powershell
.\scripts\build_desktop.ps1 -Python py
```

The build uses `PLAYWRIGHT_BROWSERS_PATH=0`, which is Playwright's supported method for bundling Chromium with PyInstaller. It also uses `--only-shell` because JobLink never opens Playwright as a visible browser. This avoids bundling a second Chromium executable that the desktop app does not use.

Build output is written to:

```text
dist\JobLink Tracker\
dist\JobLink-Tracker-Windows.zip
```

The `build/` and `dist/` directories are ignored by Git and should not be committed.

## Windows Warning

The first beta executable is unsigned. Windows SmartScreen may show **Windows protected your PC** because the file has no paid code-signing certificate and has not built a download reputation yet.

Testers should only download the ZIP from this project's GitHub repository. They can select **More info**, verify that the app name is `JobLink Tracker.exe`, and then choose **Run anyway**. Do not tell testers to bypass a warning for a copy received from somewhere else.

## Data And Logs

Job scraping and workbook processing happen on the tester's computer. The desktop launcher stores local diagnostic files under:

```text
%LOCALAPPDATA%\JobLink Tracker\logs
```

Uploaded workbooks are processed temporarily and returned through the local browser. Browser results remain in that browser's local storage until the tester clears site data.

The portable app does not install a Windows service, edit the registry, or create a cloud account. Removing the extracted folder removes the app. The local logs can be deleted separately.

## Beta Limitations

- The first package targets 64-bit Windows only.
- Chromium makes the ZIP much larger than a normal Python utility.
- The unsigned executable may trigger SmartScreen or antivirus reputation checks.
- Closing the control window during an active scrape may take several seconds while browser work ends.
- Sites that block automation can still block the desktop scraper. Packaging does not bypass website security.
- The Chrome capture extension remains a separate optional installation for blocked pages.

## Release Check

Before sharing a desktop build:

1. Extract the ZIP into a new folder.
2. Start `JobLink Tracker.exe` without Python active.
3. Confirm `/health` and `/ready` respond successfully.
4. Scrape one current company career-page link.
5. Download a new tracker and open it in Excel.
6. Upload the blank template and update it with one reviewed result.
7. Close the control window and confirm port `5050` is released.
8. Start the executable a second time and confirm it opens normally.
