# JobLink Capture Chrome Extension

![Component: browser capture](https://img.shields.io/badge/component-browser%20capture-2563eb)
![Chrome extension](https://img.shields.io/badge/browser-Chrome-4285f4)
![Local helper](https://img.shields.io/badge/helper-local%20workflow-2f855a)
![Manifest V3](https://img.shields.io/badge/manifest-v3-6b7280)
![Local endpoint](https://img.shields.io/badge/endpoint-localhost%3A5050-2563eb)
![Blocked sites](https://img.shields.io/badge/use%20case-blocked%20sites-b91c1c)

What it does
- Adds a `JobLink Capture` button to Chrome.
- When you are viewing a job page, the button scrolls through the page and sends the full loaded page text plus job metadata to the local JobLink Beta app.
- Go back to JobLink and select `Load captured jobs` to add it to the results table.

Install
1. Start JobLink Beta first.
2. Open Chrome and go to `chrome://extensions`.
3. Turn on `Developer mode`.
4. Select `Load unpacked`.
5. Choose this folder:
   `browser_extension\joblink_capture`

Use
1. Open the job page.
2. Finish any human check if the site asks.
3. Click the Chrome extensions icon.
4. Select `JobLink Capture`.
5. Select `Capture full job page`.
6. Go back to JobLink and select `Load captured jobs`.
