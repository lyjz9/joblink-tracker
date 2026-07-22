# VBA Module Notes

This optional Windows-only macro lets Excel send job links to Linc directly.

1. In Excel, open **Developer > Visual Basic > File > Import File** and choose `JobTracker.bas`.
2. Save the workbook as `.xlsm` so Excel keeps the macro.
3. Change `BASE_SERVER_URL` only if Linc runs on a different local address.

The module includes a small parser for the fields Linc returns. [VBA-JSON](https://github.com/VBA-tools/VBA-JSON) is optional if you want fuller JSON handling.
