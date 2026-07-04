# Known Limitations

JobLink Tracker is a v0.1 beta and job scraping is not perfect. Company career pages and applicant-tracking-system links usually work best, especially Greenhouse, Lever, Ashby, Workday, iCIMS, Breezy, and SmartRecruiters.

Some job boards, login-only pages, Cloudflare checks, human verification pages, private APIs, and JavaScript-heavy pages may block scraping or return incomplete fields. Rows marked for review should be checked manually before they are added to a real application tracker.

Salary, work type, and location are especially important to verify because different websites format these fields differently.

## Source Reliability

- Good: company career pages and common ATS pages usually provide cleaner structured data.
- Okay: job boards such as LinkedIn, Indeed, Glassdoor, ZipRecruiter, SimplyHired, and Dice can work, but may need review.
- Limited: Monster, Wellfound, and Upwork often block direct scraping or need browser capture/manual review.

## Monster Links

Monster search pages show many jobs at once, so JobLink Tracker does not treat them as one scrapeable job posting. Many Monster job-detail pages also block reliable scraping. If Monster opens or links to an employer/company job page, use that employer link instead.

## Privacy

The local beta runs on your computer. Do not commit personal tracker workbooks, generated Excel exports, logs, screenshots, or notes that contain private applications, email addresses, job history, or personal comments.
