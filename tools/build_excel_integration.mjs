import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputPath = "C:/Users/jzeng/Documents/job/outputs/job_tracker_excel_integration.xlsx";
const previewDir = "C:/Users/jzeng/Documents/job/tmp/excel_preview";

const workbook = Workbook.create();
const applications = workbook.worksheets.add("Applications");
const input = workbook.worksheets.add("Input");

const appHeaders = [
  "Date Applied", "Company", "Job Title", "Job link", "Status",
  "Location", "Work Type", "Salary Range", "Follow-up", "Source",
];
const inputHeaders = [
  "Job Link", "Source", "Notes", "Process Status", "Processed At", "Error Message",
];

const blankRows = (count, width) => Array.from({ length: count }, () => Array(width).fill(null));
applications.getRange("A1:J101").values = [appHeaders, ...blankRows(100, appHeaders.length)];
input.getRange("A1:F101").values = [inputHeaders, ...blankRows(100, inputHeaders.length)];

const headerFormat = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};

applications.getRange("A1:J1").format = headerFormat;
input.getRange("A1:F1").format = headerFormat;
applications.getRange("A1:J1").format.rowHeight = 24;
input.getRange("A1:F1").format.rowHeight = 24;

const appWidths = [15, 24, 36, 58, 18, 26, 16, 22, 15, 20];
const inputWidths = [58, 20, 32, 24, 21, 46];
for (let i = 0; i < appWidths.length; i += 1) {
  applications.getRangeByIndexes(0, i, 101, 1).format.columnWidth = appWidths[i];
}
for (let i = 0; i < inputWidths.length; i += 1) {
  input.getRangeByIndexes(0, i, 101, 1).format.columnWidth = inputWidths[i];
}

applications.getRange("A2:A101").format.numberFormat = "mm/dd/yyyy";
applications.getRange("I2:I101").format.numberFormat = "mm/dd/yyyy";
input.getRange("E2:E101").format.numberFormat = "mm/dd/yyyy hh:mm";
applications.getRange("A2:J101").format.verticalAlignment = "top";
input.getRange("A2:F101").format.verticalAlignment = "top";
input.getRange("C2:C101").format.wrapText = true;
input.getRange("F2:F101").format.wrapText = true;

applications.freezePanes.freezeRows(1);
input.freezePanes.freezeRows(1);
applications.showGridLines = false;
input.showGridLines = false;

const appTable = applications.tables.add("A1:J101", true, "ApplicationsTable");
appTable.style = "TableStyleMedium2";
appTable.showBandedRows = true;
const inputTable = input.tables.add("A1:F101", true, "InputTable");
inputTable.style = "TableStyleMedium2";
inputTable.showBandedRows = true;

input.getRange("D2:D101").dataValidation = {
  rule: { type: "list", values: ["Pending", "Done", "Needs Manual Review", "Error", "Duplicate"] },
};
applications.getRange("E2:E101").dataValidation = {
  rule: { type: "list", values: ["Applied", "Interview", "Offer", "Rejected", "Withdrawn"] },
};
applications.getRange("G2:G101").dataValidation = {
  rule: { type: "list", values: ["Remote", "Hybrid", "Onsite", "Mix", "n/a"] },
};

input.getRange("D2:D101").conditionalFormats.add("containsText", {
  text: "Error",
  format: { fill: "#FCE8E6", font: { color: "#B91C1C", bold: true } },
});
input.getRange("D2:D101").conditionalFormats.add("containsText", {
  text: "Done",
  format: { fill: "#E6F4EA", font: { color: "#166534", bold: true } },
});

await fs.mkdir(previewDir, { recursive: true });
for (const sheetName of ["Applications", "Input"]) {
  const preview = await workbook.render({ sheetName, range: sheetName === "Applications" ? "A1:J14" : "A1:F14", scale: 1.5, format: "png" });
  await fs.writeFile(`${previewDir}/${sheetName.toLowerCase()}.png`, new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const sheetCheck = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 2000 });
const errorCheck = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "formula error scan",
});
console.log(sheetCheck.ndjson);
console.log(errorCheck.ndjson);
