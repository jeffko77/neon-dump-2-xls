from __future__ import annotations

import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.connection import app_dir, is_frozen
from app.invoice.invoice_settings import DEFAULT_PAYEE, InvoicePayee
from app.invoice.models import Invoice
from app.invoice.service import get_school

SPORT_CODES = {
    "Lacrosse": "LX",
    "Field Hockey": "FH",
}


def _money(amount: float) -> str:
    return f"${amount:,.2f}"


def _parse_note_field(notes: str | None, label: str) -> str | None:
    if not notes:
        return None
    match = re.search(rf"{re.escape(label)}\s*([^|]+)", notes, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def invoice_number(invoice: Invoice) -> str:
    parsed = _parse_note_field(invoice.notes, "Invoice Number")
    if parsed:
        return parsed
    code = SPORT_CODES.get(invoice.sport, invoice.sport[:2].upper())
    return f"{invoice.season_year}{invoice.id:03d}{code}"


def _format_us_date(dt: datetime) -> str:
    return f"{dt.month}/{dt.day}/{dt.year}"


def invoice_date(invoice: Invoice) -> str:
    parsed = _parse_note_field(invoice.notes, "Invoice Date")
    if parsed:
        return parsed
    try:
        created = datetime.fromisoformat(invoice.created_at.replace("Z", "+00:00"))
        return _format_us_date(created.astimezone(UTC))
    except ValueError:
        return _format_us_date(datetime.now(UTC))


def _invoice_title(sport: str) -> str:
    if sport == "Field Hockey":
        return "FIELD HOCKEY SCHEDULING INVOICE"
    return "LACROSSE SCHEDULING INVOICE"


def _line_items(invoice: Invoice) -> list[tuple[str, float]]:
    items: list[tuple[str, float]] = []

    if invoice.sport == "Lacrosse":
        items.append(
            (
                f"Schedule Preparation for Lacrosse - Spring {invoice.season_year}",
                invoice.base_amount,
            )
        )
        items.append(("C Team Scheduling", invoice.c_team_scheduling))
        items.append(("Ranking Services", invoice.ranking_services))
    elif invoice.sport == "Field Hockey":
        items.append(
            (
                f"Schedule Preparation for Field Hockey - Fall {invoice.season_year}",
                invoice.base_amount,
            )
        )
        items.append(("FH Ranking Services", invoice.fh_ranking_services))
    else:
        items.append(
            (
                f"Schedule Preparation for {invoice.sport} - {invoice.season_year}",
                invoice.base_amount,
            )
        )

    if invoice.revision_amount:
        items.append(("Revision", invoice.revision_amount))
    if invoice.dual_sport_fee:
        items.append(("Dual-Sport Fee", invoice.dual_sport_fee))
    if invoice.sport == "Field Hockey" and invoice.ranking_services:
        items.append(("Ranking Services", invoice.ranking_services))
    if invoice.sport == "Field Hockey" and invoice.c_team_scheduling:
        items.append(("C Team Scheduling", invoice.c_team_scheduling))

    return items


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", value).strip()
    return re.sub(r"\s+", "_", cleaned) or "invoice"


def invoice_logo_path() -> Path | None:
    candidates = []
    if is_frozen():
        candidates.extend(
            [
                app_dir() / "_internal" / "static" / "invoice-logo.png",
                app_dir() / "static" / "invoice-logo.png",
            ]
        )
    else:
        candidates.append(app_dir() / "static" / "invoice-logo.png")
    for path in candidates:
        if path.exists():
            return path
    return None


def _logo_flowable() -> Image | None:
    path = invoice_logo_path()
    if path is None:
        return None
    width = 2.5 * inch
    height = width * (512 / 722)
    logo = Image(str(path), width=width, height=height)
    logo.hAlign = "CENTER"
    return logo


def _build_header_table(
    payee: InvoicePayee,
    *,
    normal: ParagraphStyle,
    bold: ParagraphStyle,
    header_title: ParagraphStyle,
    content_width: float,
) -> Table:
    side_width = 2.35 * inch
    center_width = content_width - (2 * side_width)
    logo = _logo_flowable()

    payee_block = Table(
        [
            [Paragraph(payee.name, bold)],
            [Paragraph(payee.address_line1, normal)],
            [Paragraph(payee.city_state_zip, normal)],
        ],
        colWidths=[side_width],
    )
    payee_block.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    contact_block = Table(
        [
            [Paragraph("Contact:", normal)],
            [Paragraph(payee.email, normal)],
        ],
        colWidths=[side_width],
    )
    contact_block.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    center_cell: Image | Paragraph
    if logo is not None:
        center_cell = logo
    else:
        center_cell = Paragraph(payee.title, header_title)

    header_table = Table(
        [[payee_block, center_cell, contact_block]],
        colWidths=[side_width, center_width, side_width],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return header_table


def render_invoice_pdf(
    invoice: Invoice,
    *,
    payee: InvoicePayee = DEFAULT_PAYEE,
) -> bytes:
    school = get_school(invoice.school_id)
    if school is None:
        raise ValueError(f"School not found for invoice {invoice.id}")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )

    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "InvoiceNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=13,
    )
    bold = ParagraphStyle(
        "InvoiceBold",
        parent=normal,
        fontName="Helvetica-Bold",
    )
    title = ParagraphStyle(
        "InvoiceTitle",
        parent=bold,
        fontSize=12,
        alignment=TA_CENTER,
        spaceBefore=12,
        spaceAfter=8,
    )
    header_title = ParagraphStyle(
        "HeaderTitle",
        parent=bold,
        fontSize=12,
        alignment=TA_CENTER,
        spaceBefore=16,
        spaceAfter=10,
    )
    right = ParagraphStyle(
        "InvoiceRight",
        parent=normal,
        alignment=TA_RIGHT,
    )
    note_style = ParagraphStyle(
        "InvoiceNote",
        parent=normal,
        fontName="Helvetica-Bold",
        spaceBefore=8,
        spaceAfter=8,
    )

    city_line = ", ".join(part for part in [school.city, school.state] if part)
    if school.zip:
        city_line = f"{city_line} {school.zip}".strip()

    content_width = letter[0] - doc.leftMargin - doc.rightMargin
    header_table = _build_header_table(
        payee,
        normal=normal,
        bold=bold,
        header_title=header_title,
        content_width=content_width,
    )

    bill_to = Table(
        [
            [
                Paragraph(
                    f"<b>TO:</b> {school.school_name}",
                    normal,
                ),
                Paragraph(
                    f"Invoice Number {invoice_number(invoice)}",
                    right,
                ),
            ],
            [
                Paragraph(school.address or "", normal),
                Paragraph(f"Invoice Date: {invoice_date(invoice)}", right),
            ],
            [
                Paragraph(city_line, normal),
                "",
            ],
        ],
        colWidths=[4.0 * inch, 3.5 * inch],
    )
    bill_to.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 1), (-1, -1), 2),
            ]
        )
    )

    line_items = _line_items(invoice)
    item_rows: list[list[Any]] = [
        [
            Paragraph("<b>ITEM</b>", bold),
            Paragraph("<b>DESCRIPTION</b>", bold),
        ]
    ]
    for label, amount in line_items:
        item_rows.append([Paragraph(label, normal), Paragraph(_money(amount), normal)])

    item_rows.append(
        [
            "",
            Paragraph(f"<b>{_money(invoice.total_amount)}</b>", bold),
        ]
    )

    items_table = Table(item_rows, colWidths=[4.7 * inch, 1.8 * inch])
    items_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
                ("LINEBELOW", (0, -2), (-1, -2), 0.5, colors.black),
                ("LINEBELOW", (0, -1), (-1, -1), 1, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    story = [
        header_table,
        Spacer(1, 0.2 * inch),
        bill_to,
        Spacer(1, 0.15 * inch),
        Paragraph(_invoice_title(invoice.sport), title),
        items_table,
    ]

    if invoice.collection_status:
        story.append(Paragraph(f"NOTE: {invoice.collection_status}", note_style))
    elif invoice.address_note:
        story.append(Paragraph(f"NOTE: {invoice.address_note}", note_style))

    story.extend(
        [
            Spacer(1, 0.2 * inch),
            Paragraph("Please make check payable to:", normal),
            Paragraph(payee.name, normal),
            Paragraph(payee.address_line1, normal),
            Paragraph(payee.city_state_zip, normal),
            Spacer(1, 0.15 * inch),
            Paragraph("THANK YOU FOR YOUR BUSINESS", title),
        ]
    )

    doc.build(story)
    return buffer.getvalue()


def invoice_pdf_filename(invoice: Invoice) -> str:
    school = get_school(invoice.school_id)
    school_name = school.school_name if school else "invoice"
    return f"Invoice - {_safe_filename(school_name)}.pdf"
