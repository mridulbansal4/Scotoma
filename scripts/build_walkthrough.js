// Builds SCOTOMA_Solution_Walkthrough.docx from measured project artefacts.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, PageBreak,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, ImageRun,
  Footer, PageNumber, TabStopType, TabStopPosition,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const FIG = path.join(ROOT, "docs", "figures");
const FONT = "Times New Roman";
const BODY = 24;      // 12pt (half-points)
const HEAD = 28;      // 14pt
const TITLE = 40;     // 20pt
const SMALL = 21;     // 10.5pt
const LINE = 360;     // 1.5 line spacing
const CONTENT_W = 9360; // 6.5in in DXA
const ACC = "C2461C";
const INK = "1A1A1A";
const HDRBG = "EFE9E4";

let figN = 0, tabN = 0;

const p = (text, opts = {}) => new Paragraph({
  alignment: opts.align || AlignmentType.JUSTIFIED,
  spacing: { line: LINE, after: opts.after !== undefined ? opts.after : 120 },
  indent: opts.indent,
  children: [new TextRun({ text, font: FONT, size: opts.size || BODY, italics: opts.italics, bold: opts.bold, color: opts.color || INK })],
});

// Paragraph from [text, {bold}] runs so key numbers can be emphasised inline.
const rich = (runs, opts = {}) => new Paragraph({
  alignment: opts.align || AlignmentType.JUSTIFIED,
  spacing: { line: LINE, after: opts.after !== undefined ? opts.after : 120 },
  children: runs.map(r => new TextRun({
    text: r[0], font: FONT, size: opts.size || BODY,
    bold: r[1] && r[1].b, italics: r[1] && r[1].i, color: (r[1] && r[1].color) || INK,
  })),
});

const h1 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { line: LINE, before: 320, after: 160 },
  children: [new TextRun({ text, font: FONT, size: HEAD, bold: true, color: INK })],
});

const h2 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  spacing: { line: LINE, before: 240, after: 120 },
  children: [new TextRun({ text, font: FONT, size: HEAD, bold: true, color: INK })],
});

const bullet = (text) => new Paragraph({
  bullet: { level: 0 },
  alignment: AlignmentType.JUSTIFIED,
  spacing: { line: LINE, after: 80 },
  children: [new TextRun({ text, font: FONT, size: BODY, color: INK })],
});

const caption = (kind, text) => {
  const n = kind === "fig" ? ++figN : ++tabN;
  const label = kind === "fig" ? `Figure ${n}. ` : `Table ${n}. `;
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { line: 240, before: 60, after: 200 },
    children: [
      new TextRun({ text: label, font: FONT, size: SMALL, bold: true, color: INK }),
      new TextRun({ text, font: FONT, size: SMALL, color: INK }),
    ],
  });
};

const figure = (file, widthPx, heightPx) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 160, after: 0 },
  children: [new ImageRun({
    type: "png",
    data: fs.readFileSync(path.join(FIG, file)),
    transformation: { width: widthPx, height: heightPx },
  })],
});

const cell = (text, { bold = false, header = false, width, align = AlignmentType.LEFT } = {}) =>
  new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { type: ShadingType.CLEAR, fill: HDRBG, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: [new Paragraph({
      alignment: align,
      spacing: { line: 240, after: 0 },
      children: [new TextRun({ text, font: FONT, size: SMALL, bold: bold || header, color: INK })],
    })],
  });

const table = (widths, rows, aligns) => new Table({
  columnWidths: widths,
  width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 6, color: "8A8580" },
    bottom: { style: BorderStyle.SINGLE, size: 6, color: "8A8580" },
    left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
    right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "D9D2CC" },
    insideVertical: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
  },
  rows: rows.map((r, ri) => new TableRow({
    tableHeader: ri === 0,
    children: r.map((c, ci) => cell(String(c), {
      header: ri === 0, width: widths[ci],
      align: (aligns && aligns[ci] === "r") ? AlignmentType.RIGHT : AlignmentType.LEFT,
    })),
  })),
});

const rule = () => new Paragraph({
  spacing: { before: 60, after: 160 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "D9D2CC" } },
  children: [new TextRun({ text: "", font: FONT, size: 2 })],
});

module.exports = { p, rich, h1, h2, bullet, caption, figure, table, rule, figN, tabN,
  Document, Packer, Paragraph, TextRun, AlignmentType, PageBreak, Footer, PageNumber,
  FONT, BODY, HEAD, TITLE, SMALL, LINE, CONTENT_W, ACC, INK, fs, path, ROOT };
