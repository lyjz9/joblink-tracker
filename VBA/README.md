# VBA Module Notes

[![Component: Excel integration](https://img.shields.io/badge/component-Excel%20integration-217346)](JobTracker.bas)
[![VBA macros](https://img.shields.io/badge/VBA-macros-8673a1)](JobTracker.bas)
[![Runs locally](https://img.shields.io/badge/runs-locally-2563eb)](../README.md#private-web-beta)
[![Workbook type](https://img.shields.io/badge/workbook-xlsm-217346)](../README.md#excel-workflow)
[![Local API](https://img.shields.io/badge/API-localhost%3A5000-6b7280)](../scraper/app.py)
[![Excel desktop](https://img.shields.io/badge/excel-desktop-217346)](../README.md#excel-workflow)

- Import `JobTracker.bas` into Excel (Developer -> Visual Basic -> File -> Import File...).
- Optionally install VBA-JSON (https://github.com/VBA-tools/VBA-JSON) to parse responses robustly and replace `ParseJSONKey` usage.
- Edit `BASE_SERVER_URL` in the module if your server runs elsewhere.
