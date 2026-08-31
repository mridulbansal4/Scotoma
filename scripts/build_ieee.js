// SCOTOMA_Solution_Walkthrough.docx in the IEEE conference format of the supplied template.
// Template spec: A4, Times New Roman, 10pt body justified, two-column body at 18pt gutter,
// 24pt centred title, 9pt abstract, full-width floats via continuous single-column sections.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, ImageRun, SectionType, HeadingLevel,
  Footer, PageNumber,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const FIG = path.join(ROOT, "docs", "figures");
const F = "Times New Roman";
const BODY = 20;        // 10pt
const SMALL = 16;       // 8pt, IEEE table text
const CAP = 16;         // 8pt captions
const INK = "000000";
const LINE = 228;       // 11.40pt from the template's BodyText style
const COL_W = 4900;     // one column, DXA
const FULL_W = 10060;   // both columns

let figN = 0, tabN = 0;

const body = (text, opts = {}) => new Paragraph({
  alignment: opts.align || AlignmentType.JUSTIFIED,
  spacing: { line: LINE, after: opts.after !== undefined ? opts.after : 120 },
  indent: opts.noIndent ? undefined : { firstLine: 200 },
  children: [new TextRun({ text, font: F, size: opts.size || BODY, italics: opts.i, bold: opts.b, color: INK })],
});

const mixed = (runs, opts = {}) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  spacing: { line: LINE, after: 120 },
  indent: opts.noIndent ? undefined : { firstLine: 200 },
  children: runs.map(r => new TextRun({
    text: r[0], font: F, size: opts.size || BODY,
    bold: r[1] && r[1].b, italics: r[1] && r[1].i, color: INK,
  })),
});

// IEEE first-level headings: centred, small caps, roman numeral.
const H1 = (roman, text) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 200, after: 100, line: LINE },
  children: [new TextRun({ text: roman ? `${roman}.  ${text}` : text, font: F, size: BODY, allCaps: false, smallCaps: true, color: INK })],
});

// IEEE second-level headings: italic, left, lettered.
const H2 = (letter, text) => new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { before: 140, after: 80, line: LINE },
  children: [new TextRun({ text: `${letter}.  ${text}`, font: F, size: BODY, italics: true, color: INK })],
});

const bullet = (text) => new Paragraph({
  bullet: { level: 0 },
  alignment: AlignmentType.JUSTIFIED,
  spacing: { line: LINE, after: 60 },
  children: [new TextRun({ text, font: F, size: BODY, color: INK })],
});

const figCap = (text) => {
  figN += 1;
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 60, after: 160, line: 200 },
    children: [
      new TextRun({ text: `Fig. ${figN}. `, font: F, size: CAP, color: INK }),
      new TextRun({ text, font: F, size: CAP, color: INK }),
    ],
  });
};

// IEEE table captions sit above the table, centred, small caps.
const tabCap = (text) => {
  tabN += 1;
  const roman = ["I","II","III","IV","V","VI","VII","VIII","IX","X"][tabN - 1];
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 160, after: 0, line: 200 },
      children: [new TextRun({ text: `TABLE ${roman}.`, font: F, size: CAP, color: INK })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 0, after: 60, line: 200 },
      children: [new TextRun({ text, font: F, size: CAP, smallCaps: true, color: INK })],
    }),
  ];
};

const img = (file, w, h) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 120, after: 0 },
  children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(FIG, file)),
    transformation: { width: w, height: h } })],
});

const cell = (text, { header = false, width, align = AlignmentType.LEFT } = {}) =>
  new TableCell({
    width: { size: width, type: WidthType.DXA },
    margins: { top: 30, bottom: 30, left: 70, right: 70 },
    shading: header ? { type: ShadingType.CLEAR, fill: "F2F2F2", color: "auto" } : undefined,
    children: [new Paragraph({
      alignment: align, spacing: { line: 200, after: 0 },
      children: [new TextRun({ text, font: F, size: SMALL, bold: header, color: INK })],
    })],
  });

const tbl = (widths, rows, aligns) => new Table({
  columnWidths: widths,
  width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 8, color: "000000" },
    bottom: { style: BorderStyle.SINGLE, size: 8, color: "000000" },
    left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
    right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "999999" },
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

module.exports = {
  body, mixed, H1, H2, bullet, figCap, tabCap, img, tbl,
  Document, Packer, Paragraph, TextRun, AlignmentType, SectionType, Footer, PageNumber,
  F, BODY, SMALL, CAP, INK, LINE, COL_W, FULL_W, fs, path, ROOT,
};
