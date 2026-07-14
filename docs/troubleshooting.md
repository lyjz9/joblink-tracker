# Troubleshooting

## Playwright Browser Is Missing

Install the Chromium files JobLink uses:

```powershell
python -m playwright install chromium
```

## A Job Board Blocks Scraping

Look for the same role on the company's career site first. If you can open the blocked page yourself, capture it with the Chrome extension in `browser_extension/joblink_capture`, then load that capture in JobLink.

## Monster Does Not Work

Use the employer career page that Monster opens or links to. JobLink treats Monster search pages and many Monster job pages as limited because they do not provide one reliable posting.

## Excel Tracker Will Not Update

Close the workbook in Excel, then select `Update tracker` again. If the browser still cannot save over that file, JobLink creates an updated copy instead.

## A Row Says Review

`Review` means JobLink is unsure about at least one field. Read the reason shown on the row, then retry it, fix the fields yourself, or flag it so the scraper problem can be investigated.

## Browser Capture Looks Wrong

Make sure the real job posting is visible before you capture it. Finish any human check and wait for the page to load, then try again. If JobLink shows suggestions under a field, choose the best one or type the correct value yourself.
