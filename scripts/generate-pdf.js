import fs from "node:fs";
import { execSync } from "node:child_process";
import { marked } from "marked";

function renderHtml(title, bodyHtml) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>${title}</title>
<style>
  @page { margin: 20mm 18mm 20mm 18mm; size: A4 portrait; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #24292f; line-height: 1.6; font-size: 13px; max-width: 800px; margin: 0 auto; }
  h1 { font-size: 24px; border-bottom: 2px solid #0969da; padding-bottom: 8px; margin-top: 0; color: #1f2328; }
  h2 { font-size: 18px; border-bottom: 1px solid #d0d7de; padding-bottom: 6px; margin-top: 24px; color: #1f2328; page-break-after: avoid; }
  h3 { font-size: 15px; margin-top: 18px; color: #1f2328; page-break-after: avoid; }
  p, ul, ol { margin: 8px 0 12px 0; }
  li { margin: 4px 0; }
  code { background-color: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 4px; padding: 2px 5px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 11.5px; }
  pre { background-color: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 12px; overflow-x: auto; font-size: 11px; line-height: 1.45; page-break-inside: avoid; }
  pre code { background-color: transparent; border: none; padding: 0; }
  table { border-collapse: collapse; width: 100%; margin: 16px 0; page-break-inside: avoid; font-size: 12px; }
  th, td { border: 1px solid #d0d7de; padding: 8px 12px; text-align: left; }
  th { background-color: #f6f8fa; font-weight: 600; }
  tr:nth-child(even) { background-color: #fcfcfc; }
  blockquote { border-left: 4px solid #0969da; color: #57609a; padding: 4px 12px; margin: 12px 0; background-color: #f6f8fa; }
  hr { border: 0; height: 1px; background: #d0d7de; margin: 20px 0; }
</style>
</head>
<body>${bodyHtml}</body>
</html>`;
}

export function mdToPdf(inputFile, outputFile, title) {
  const md = fs.readFileSync(inputFile, "utf8");
  const bodyHtml = marked.parse(md);
  const html = renderHtml(title, bodyHtml);
  const tmpHtml = inputFile.replace(/\.md$/, ".html");
  fs.writeFileSync(tmpHtml, html);
  const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  execSync(`"${chromePath}" --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="${outputFile}" "${tmpHtml}"`);
  fs.unlinkSync(tmpHtml);
}

if (process.argv[1] && process.argv[1].endsWith("generate-pdf.js")) {
  mdToPdf("README.md", "README.pdf", "Sinchai - Smart Irrigation System");
  mdToPdf("AI_CHAT_TRANSCRIPT.md", "AI_CHAT_TRANSCRIPT.pdf", "Sinchai - AI Chat Transcript");
  console.log("Generated README.pdf and AI_CHAT_TRANSCRIPT.pdf");
}
