# Known Limitations

JobLink is still a beta, and no scraper can read every job site perfectly. Company career pages and ATS links usually give the best results, especially Greenhouse, Lever, Ashby, Workday, iCIMS, Breezy, and SmartRecruiters.

Some job boards hide details behind login walls, Cloudflare checks, human verification, private APIs, or scripts that load after the page opens. When that happens, JobLink may return an error or only part of the posting. Check every row marked `Review` before saving it.

Pay, work type, and location deserve an extra look because sites label them in very different ways.

## Source Reliability

- **Good:** Company career pages and common ATS pages usually provide clean structured data.
- **Okay:** LinkedIn, Indeed, Glassdoor, ZipRecruiter, SimplyHired, and Dice often work but deserve a quick review.
- **Limited:** Monster, Wellfound, and Upwork frequently block the scraper or need browser capture and manual edits.

## Monster Links

A Monster search page contains many jobs, so it cannot be treated as one posting. Many individual Monster pages also block reliable access. When Monster opens or links to the employer's career page, use that link instead.

## Privacy

The local beta runs on your computer. Keep personal trackers, exports, logs, screenshots, and notes out of Git, especially when they contain email addresses, application history, or private comments.
