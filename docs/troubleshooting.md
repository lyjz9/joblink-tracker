# Troubleshooting

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
