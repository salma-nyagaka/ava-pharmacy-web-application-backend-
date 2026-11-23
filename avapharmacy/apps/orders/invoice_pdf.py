"""Generate downloadable invoices from the persisted order snapshot."""
from io import BytesIO
from django.conf import settings
from xml.sax.saxutils import escape
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image


def render_order_invoice(order):
    output = BytesIO()
    pink = colors.HexColor('#e81750')
    navy = colors.HexColor('#0b214d')
    muted = colors.HexColor('#64748b')
    text = ParagraphStyle('InvoiceText', fontName='Helvetica', fontSize=10, leading=15, textColor=navy)
    title = ParagraphStyle('InvoiceTitle', parent=text, fontSize=23, leading=28, textColor=pink, spaceAfter=6)
    small = ParagraphStyle('InvoiceSmall', parent=text, fontSize=9, leading=13, textColor=muted)
    right = ParagraphStyle('InvoiceRight', parent=text, alignment=TA_RIGHT)
    def paragraph(value, style=text):
        return Paragraph(escape(str(value or '')).replace('\n', '<br/>'), style)
    def money(value):
        return f'KSh {value:,.2f}'
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=38, bottomMargin=42, title=f'Invoice {order.order_number}', author='AVA Pharmacy')
    date = timezone.localtime(order.created_at).strftime('%d %b %Y, %H:%M')
    logo = settings.BASE_DIR / 'templates' / 'emails' / 'assets' / 'ava-logo.jpg'
    brand = Image(str(logo), width=112.5, height=47.5, hAlign='LEFT') if logo.exists() else paragraph('AVA PHARMACY', small)
    story = [brand, Spacer(1, 12), paragraph('Invoice', title), paragraph(f'Order {order.order_number}'), paragraph(date, small), Spacer(1, 20)]
    customer = ' '.join(filter(None, [order.shipping_first_name, order.shipping_last_name])) or 'Customer'
    address = '\n'.join(filter(None, [customer, order.shipping_email, order.shipping_phone, order.shipping_street, ', '.join(filter(None, [order.shipping_city, order.shipping_county]))]))
    payment = order.get_payment_method_display() + '\nStatus: ' + order.get_payment_status_display()
    reference = str(order.payment_reference or '').strip()
    if reference and reference != '0' and not reference.startswith('PAY-'):
        payment += '\nPayment reference: ' + reference
    else:
        intent = order.payment_intents.filter(status='succeeded').first()
        tracking = intent.reference if intent else (reference if reference != '0' else '')
        if tracking:
            payment += '\nPayment tracking ID: ' + tracking
    details = Table([[paragraph('BILL TO', small), paragraph('PAYMENT', small)], [paragraph(address), paragraph(payment)]], colWidths=[285, 230])
    details.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),0), ('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story += [details, Spacer(1, 22)]
    rows = [[paragraph('ITEM', small), paragraph('QTY', small), paragraph('UNIT PRICE', small), paragraph('AMOUNT', small)]]
    for item in order.items.all():
        rows.append([paragraph(item.product_name), paragraph(item.quantity, right), paragraph(money(item.unit_price), right), paragraph(money(item.subtotal), right)])
    table = Table(rows, colWidths=[265, 40, 105, 105], repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0), colors.HexColor('#fff1f5')), ('LINEBELOW',(0,0),(-1,0),1,pink), ('VALIGN',(0,0),(-1,-1),'TOP'), ('TOPPADDING',(0,0),(-1,-1),10), ('BOTTOMPADDING',(0,0),(-1,-1),10), ('LINEBELOW',(0,1),(-1,-1),.5,colors.HexColor('#e2e8f0'))]))
    story += [table, Spacer(1, 16)]
    total_rows = [[paragraph('Subtotal'), paragraph(money(order.subtotal), right)], [paragraph('Discount'), paragraph(money(order.discount_total), right)], [paragraph('Delivery'), paragraph(money(order.shipping_fee), right)], [paragraph('Total'), paragraph(money(order.total), right)]]
    totals = Table(total_rows, colWidths=[130,130], hAlign='RIGHT')
    totals.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),6), ('BOTTOMPADDING',(0,0),(-1,-1),6), ('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#fff1f5')), ('LINEABOVE',(0,-1),(-1,-1),1,pink)]))
    story += [totals, Spacer(1, 24), paragraph('Thank you for choosing AVA Pharmacy.', small)]
    def footer(canvas, doc):
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(muted)
        canvas.drawString(40, 24, f'Invoice: {order.order_number}')
        canvas.drawRightString(A4[0]-40, 24, f'Page {doc.page}')
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
