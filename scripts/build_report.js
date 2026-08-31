// SCOTOMA_Solution_Walkthrough.docx in the corporate report format of the supplied draft.
// Spec taken from Krishi_Prabandh_Fund_Utilization_draft.docx:
//   Letter 12240x15840, 1in margins, header/footer 708
//   Times New Roman throughout
//   Title 20pt bold centred all-caps, subtitle 13pt bold centred, meta line 10pt centred
//   Numbered section heads 15pt bold left all-caps, body 12pt justified
//   Tables 9360 dxa fixed, full black grid, header row filled 000000 with white 12pt bold
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, ImageRun, Header, Footer, PageNumber, VerticalAlign,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const FIG = path.join(ROOT, "docs", "figures");
const F = "Times New Roman";
const T_TITLE = 40;   // 20pt
const T_SUB = 26;     // 13pt
const T_META = 20;    // 10pt
const T_HEAD = 30;    // 15pt
const T_BODY = 24;    // 12pt
const T_TBL = 20;     // 10pt in tables, for density
const T_HDRCELL = 20; // 10pt white header cells
const T_CAP = 20;     // 10pt captions
const T_FOOT = 18;    // 9pt
const BLACK = "000000";
const WHITE = "FFFFFF";
const TABLE_W = 9360;

let figN = 0, tabN = 0;

const P = (text, o = {}) => new Paragraph({
  alignment: o.align || AlignmentType.JUSTIFIED,
  spacing: { after: o.after !== undefined ? o.after : 160, line: o.line || 276 },
  children: [new TextRun({ text, font: F, size: o.size || T_BODY, bold: o.b, italics: o.i, color: o.color || BLACK })],
});

const RUNS = (runs, o = {}) => new Paragraph({
  alignment: o.align || AlignmentType.JUSTIFIED,
  spacing: { after: o.after !== undefined ? o.after : 160, line: 276 },
  children: runs.map(r => new TextRun({
    text: r[0], font: F, size: o.size || T_BODY,
    bold: r[1] && r[1].b, italics: r[1] && r[1].i, color: BLACK,
  })),
});

const HEAD = (text) => new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { before: 320, after: 160, line: 276 },
  children: [new TextRun({ text, font: F, size: T_HEAD, bold: true, color: BLACK })],
});

const SUB = (text) => new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { before: 200, after: 120, line: 276 },
  children: [new TextRun({ text, font: F, size: T_BODY, bold: true, color: BLACK })],
});

const BULLET = (text) => new Paragraph({
  bullet: { level: 0 },
  alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 100, line: 276 },
  children: [new TextRun({ text, font: F, size: T_BODY, color: BLACK })],
});

// The draft uses a bold lead-in sentence as a standing note. Reused for the honesty callouts.
const NOTE = (label, text) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  spacing: { before: 160, after: 200, line: 276 },
  border: {
    left: { style: BorderStyle.SINGLE, size: 18, color: BLACK, space: 12 },
  },
  indent: { left: 180 },
  children: [
    new TextRun({ text: `${label}: `, font: F, size: T_BODY, bold: true, color: BLACK }),
    new TextRun({ text, font: F, size: T_BODY, color: BLACK }),
  ],
});

const IMG = (file, w, h) => new Paragraph({
  alignment: AlignmentType.CENTER,
  keepNext: true,
  spacing: { before: 160, after: 60 },
  children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(FIG, file)),
    transformation: { width: w, height: h } })],
});

const FIGCAP = (text) => {
  figN += 1;
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 240, line: 240 },
    children: [
      new TextRun({ text: `Figure ${figN}. `, font: F, size: T_CAP, bold: true, color: BLACK }),
      new TextRun({ text, font: F, size: T_CAP, italics: true, color: BLACK }),
    ],
  });
};

const TABCAP = (text) => {
  tabN += 1;
  return new Paragraph({
    alignment: AlignmentType.LEFT,
    keepNext: true,
    spacing: { before: 120, after: 80, line: 240 },
    children: [
      new TextRun({ text: `Table ${tabN}. `, font: F, size: T_CAP, bold: true, color: BLACK }),
      new TextRun({ text, font: F, size: T_CAP, italics: true, color: BLACK }),
    ],
  });
};

const CELL = (text, { header = false, width, align = AlignmentType.LEFT, keep = true } = {}) =>
  new TableCell({
    width: { size: width, type: WidthType.DXA },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    verticalAlign: VerticalAlign.CENTER,
    shading: header ? { type: ShadingType.CLEAR, fill: BLACK, color: "auto" } : undefined,
    children: [new Paragraph({
      alignment: align,
      keepNext: keep,
      spacing: { line: 240, after: 0 },
      children: [new TextRun({
        text, font: F, size: header ? T_HDRCELL : T_TBL,
        bold: header, color: header ? WHITE : BLACK,
      })],
    })],
  });

const TBL = (widths, rows, aligns) => new Table({
  columnWidths: widths,
  width: { size: TABLE_W, type: WidthType.DXA },
  layout: "fixed",
  borders: {
    top: { style: BorderStyle.SINGLE, size: 4, color: BLACK },
    bottom: { style: BorderStyle.SINGLE, size: 4, color: BLACK },
    left: { style: BorderStyle.SINGLE, size: 4, color: BLACK },
    right: { style: BorderStyle.SINGLE, size: 4, color: BLACK },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: BLACK },
    insideVertical: { style: BorderStyle.SINGLE, size: 4, color: BLACK },
  },
  rows: rows.map((r, ri) => new TableRow({
    tableHeader: ri === 0,
    cantSplit: true,
    children: r.map((c, ci) => CELL(String(c), {
      header: ri === 0, width: widths[ci],
      keep: ri < rows.length - 1,
      align: (aligns && aligns[ci] === "r") ? AlignmentType.RIGHT : AlignmentType.LEFT,
    })),
  })),
});

module.exports = {
  P, RUNS, HEAD, SUB, BULLET, NOTE, IMG, FIGCAP, TABCAP, TBL,
  Document, Packer, Paragraph, TextRun, AlignmentType, Header, Footer, PageNumber, BorderStyle,
  F, T_TITLE, T_SUB, T_META, T_BODY, T_FOOT, T_CAP, BLACK, TABLE_W, fs, path, ROOT,
};
