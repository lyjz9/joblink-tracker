# Linc Beta Test

Thanks for trying Linc. This is a small local beta, so the goal is not to prove that every result is perfect. The useful part is finding the pages where a field is missing, messy, or too confidently wrong.

## What You Need

- The current `Linc-v0.1.0-Windows.zip` from this repository.
- A temporary copy of an Excel application tracker, or the included blank template.
- 10 to 15 current job postings from at least three different websites.
- About 20 minutes.

Use public job postings only. Do not send a resume, a personal tracker, or screenshots containing private application notes.

## Test One Session

1. Extract the ZIP into a new folder and open `Linc.exe`.
2. Paste 5 to 10 current job links and choose the date you applied.
3. Select **Get job details** and wait for the batch to finish.
4. Compare every result with the posting, especially company, title, location, work type, and salary.
5. Correct one row with **Manual add** or by editing the result.
6. Download a new Excel tracker and confirm the original job links still work.
7. Upload a copy of an existing tracker and add the reviewed rows to it.
8. Paste one of the same links again. Try both duplicate choices: leave the existing row alone, then update it.
9. Close the Linc window, open it again, and confirm the app starts normally.

## Report Something Wrong

Use the flag button on one bad row, or select several rows and choose **Flag selected**. Use **Feedback** for a general bug, confusing instruction, or idea.

The desktop beta saves these notes on the tester's computer. It does not upload them automatically. The useful files are:

```text
%LOCALAPPDATA%\Linc\logs\user_reported_issues.jsonl
%LOCALAPPDATA%\Linc\logs\beta_feedback.jsonl
```

Send only those files after checking that you are comfortable sharing their contents. A useful report says which website was tested, which field was wrong, what Linc returned, and what the posting showed instead.

## Known Limits

Monster search pages contain several jobs and should not be pasted as one posting. Monster, Upwork, Wellfound, and some Cloudflare-protected pages may block automated access. When a job board links to the employer's career page, use the employer link instead.

An expired or protected posting should produce a clear error or review message. It should not produce a confident row filled with unrelated page text.

## Invitation Message

> Hi, I am testing a local job-tracker tool called Linc. It turns job-posting links into reviewed Excel rows. The test takes about 20 minutes, does not require Python, and keeps files on your computer. Please try 10 to 15 current postings from a few websites and tell me where the company, title, location, work type, salary, or Excel update is wrong.
