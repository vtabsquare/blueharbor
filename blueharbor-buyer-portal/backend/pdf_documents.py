"""Professional BlueHarbor PDF trade documents rendered with ReportLab."""
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

NAVY = colors.HexColor('#083C45')
TEAL = colors.HexColor('#0B7E73')
MINT = colors.HexColor('#EAF7F3')
INK = colors.HexColor('#1D3438')
MUTED = colors.HexColor('#6A7F82')
LINE = colors.HexColor('#D7E4E1')
PALE = colors.HexColor('#F7FAF9')


def _money(cents):
    return f'USD {int(cents or 0) / 100:,.2f}'


def _fish(canvas, x, y, scale=1.0, stroke=colors.white):
    canvas.saveState()
    canvas.setStrokeColor(stroke)
    canvas.setFillColor(colors.Color(stroke.red, stroke.green, stroke.blue, alpha=0.08))
    canvas.setLineWidth(1.5 * scale)
    w, h = 19 * scale, 8 * scale
    canvas.ellipse(x, y - h / 2, x + w, y + h / 2, fill=0, stroke=1)
    canvas.line(x, y, x - 7 * scale, y + 5 * scale)
    canvas.line(x, y, x - 7 * scale, y - 5 * scale)
    canvas.line(x - 7 * scale, y + 5 * scale, x - 7 * scale, y - 5 * scale)
    canvas.circle(x + 14 * scale, y + 1.4 * scale, 0.8 * scale, fill=1, stroke=0)
    canvas.restoreState()


def _page(canvas, doc):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 34 * mm, width, 34 * mm, stroke=0, fill=1)
    _fish(canvas, 24 * mm, height - 17 * mm, 1.15)
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 15)
    canvas.drawString(49 * mm, height - 14.5 * mm, 'BLUEHARBOR')
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(colors.HexColor('#A9D8D1'))
    canvas.drawString(49 * mm, height - 20 * mm, 'INDIA EXPORT DESK  |  SEAFOOD TRADE DOCUMENT')
    canvas.setStrokeColor(LINE)
    canvas.line(16 * mm, 15 * mm, width - 16 * mm, 15 * mm)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(16 * mm, 10 * mm, 'Generated from BlueHarbor operational records. Human commercial and regulatory review remains authoritative.')
    page_text = f'Page {doc.page}'
    canvas.drawRightString(width - 16 * mm, 10 * mm, page_text)
    canvas.restoreState()


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=NAVY, spaceAfter=4))
    styles.add(ParagraphStyle('DocSub', parent=styles['BodyText'], fontSize=8.5, leading=12, textColor=MUTED, spaceAfter=10))
    styles.add(ParagraphStyle('Section', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=NAVY, spaceBefore=8, spaceAfter=7))
    styles.add(ParagraphStyle('BodySmall', parent=styles['BodyText'], fontSize=8.5, leading=12, textColor=INK))
    styles.add(ParagraphStyle('RightStrong', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=9, leading=12, alignment=TA_RIGHT, textColor=INK))
    styles.add(ParagraphStyle('Cell', parent=styles['BodyText'], fontSize=8.5, leading=11, textColor=INK))
    styles.add(ParagraphStyle('CellHeader', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.white))
    styles.add(ParagraphStyle('CellMuted', parent=styles['BodyText'], fontSize=7.8, leading=10, textColor=MUTED))
    return styles


def _info_table(rows, widths=(38 * mm, 55 * mm, 38 * mm, 48 * mm)):
    data = []
    for left_label, left_value, right_label, right_value in rows:
        data.append([
            Paragraph(f'<b>{left_label}</b>', _styles()['CellMuted']), Paragraph(str(left_value or '-'), _styles()['Cell']),
            Paragraph(f'<b>{right_label}</b>', _styles()['CellMuted']), Paragraph(str(right_value or '-'), _styles()['Cell']),
        ])
    table = Table(data, colWidths=list(widths), hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PALE),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return table


def render_document(kind, order):
    """Render Order confirmation, Informational invoice or Packing list from an order dict."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=43 * mm, bottomMargin=22 * mm,
        title=f'BlueHarbor {kind} {order.get("id", "")}', author='BlueHarbor',
    )
    s = _styles()
    story = []
    title = str(kind or 'Trade document').title()
    subtitle = 'Buyer copy - operational trade document' if kind != 'Informational invoice' else 'Buyer copy - informational invoice / commercial estimate'
    story += [Paragraph(title, s['DocTitle']), Paragraph(subtitle, s['DocSub'])]

    # Top status band
    status_data = [[
        Paragraph('<b>ORDER</b><br/>' + str(order.get('id', '-')), s['Cell']),
        Paragraph('<b>STATUS</b><br/>' + str(order.get('status', '-')), s['Cell']),
        Paragraph('<b>ISSUED</b><br/>' + str(order.get('created', '-')), s['Cell']),
    ]]
    status = Table(status_data, colWidths=[59 * mm, 59 * mm, 59 * mm])
    status.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), MINT), ('BOX', (0, 0), (-1, -1), .6, colors.HexColor('#B9DDD5')),
        ('INNERGRID', (0, 0), (-1, -1), .4, colors.HexColor('#CBE6E0')), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story += [status, Spacer(1, 8 * mm)]

    story += [Paragraph('Buyer & route', s['Section'])]
    story += [_info_table([
        ('Buyer', order.get('company') or 'Buyer account', 'Destination', order.get('destination') or '-'),
        ('Shipping service', order.get('service') or '-', 'Currency', 'USD'),
    ])]

    qty = int(order.get('kg') or 0)
    unit_cents = int(order.get('cents_per_kg') or 0)
    product_cents = qty * unit_cents
    shipping_cents = int(order.get('shipping') or 0)
    total_cents = int(order.get('total') or 0)
    handling_cents = max(0, total_cents - product_cents - shipping_cents)

    story += [Paragraph('Line item', s['Section'])]
    item_data = [[
        Paragraph('Description', s['CellHeader']), Paragraph('Quantity', s['CellHeader']),
        Paragraph('Unit price', s['CellHeader']), Paragraph('Amount', s['CellHeader'])
    ], [
        Paragraph(str(order.get('product_name') or 'Seafood product'), s['Cell']),
        Paragraph(f'{qty:,} kg', s['Cell']), Paragraph(_money(unit_cents), s['Cell']), Paragraph(_money(product_cents), s['RightStrong'])
    ]]
    item_table = Table(item_data, colWidths=[78 * mm, 31 * mm, 34 * mm, 34 * mm])
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), .55, LINE), ('INNERGRID', (0, 0), (-1, -1), .35, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story += [item_table]

    if kind == 'Packing list':
        story += [Paragraph('Packing particulars', s['Section'])]
        story += [_info_table([
            ('Declared cargo quantity', f'{qty:,} kg', 'Packing status', 'Operational record - final packing particulars subject to release'),
            ('Product', order.get('product_name') or '-', 'Order reference', order.get('id') or '-'),
        ])]
    else:
        totals = [
            ['Product amount', _money(product_cents)],
            ['Shipping', _money(shipping_cents)],
            ['Handling & documentation', _money(handling_cents)],
            ['Estimated total', _money(total_cents)],
        ]
        totals_table = Table(totals, colWidths=[48 * mm, 38 * mm], hAlign='RIGHT')
        totals_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'), ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5), ('TEXTCOLOR', (0, 0), (-1, -1), INK),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LINEABOVE', (0, -1), (-1, -1), 1, TEAL),
        ]))
        story += [Spacer(1, 4 * mm), totals_table]

    story += [Spacer(1, 8 * mm)]
    note = (
        '<b>Document note:</b> This buyer copy is generated from BlueHarbor operational records. '
        'It is not a payment receipt, tax invoice, certificate of origin, health certificate, customs release or legal compliance certificate. '
        'Final commercial terms, packing particulars and regulatory documents must be confirmed by the responsible human operator / authority.'
    )
    note_box = Table([[Paragraph(note, s['BodySmall'])]], colWidths=[177 * mm])
    note_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF8E8')), ('BOX', (0, 0), (-1, -1), .5, colors.HexColor('#E9D7A9')),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story += [KeepTogether(note_box)]

    doc.build(story, onFirstPage=_page, onLaterPages=_page)
    return buffer.getvalue()
