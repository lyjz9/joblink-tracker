Usage examples

1) Fetch details from a URL using curl:

```bash
curl -X POST http://127.0.0.1:5000/scrape -H "Content-Type: application/json" -d '{"url": "https://example.com/job/123"}'
```

2) Export jobs (POST JSON array) and download the generated .xlsx:

```bash
curl -X POST http://127.0.0.1:5000/export -H "Content-Type: application/json" -d '[{"company":"ACME","job_title":"Engineer","job_link":"https://..."}]' --output jobs.xlsx
```
