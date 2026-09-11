"""Small dependency-free PDF template for informational POC trade documents."""
def render_document(kind, order):
    import textwrap
    def safe(text):
        return str(text).encode('cp1252',errors='replace').decode('cp1252').replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
    lines=['BLUEHARBOR | INDIA EXPORT DESK',kind.upper(),'INFORMATIONAL POC DOCUMENT - NO PAYMENT COLLECTED','',
        'Order: '+order['id'],'Created: '+order['created'],'Buyer: '+(order.get('company') or 'Buyer account'),
        'Product: '+order['product_name'],f"Quantity: {order['kg']:,} kg",'Destination: '+order['destination'],
        'Service: '+order['service'],f"Product amount: USD {order['kg']*order['cents_per_kg']/100:,.2f}",
        f"Shipping: USD {order['shipping']/100:,.2f}",f"Handling/documentation: USD {(order['total']-order['kg']*order['cents_per_kg']-order['shipping'])/100:,.2f}",
        f"Estimated total: USD {order['total']/100:,.2f}",'Status: '+order['status'],'',
        'Not a tax invoice, payment receipt, or certificate of compliance.',
        'Exporter must confirm commercial terms and final packing particulars.']
    wrapped=[]
    for line in lines:wrapped.extend(textwrap.wrap(line,88) or [''])
    # Input fields are bounded by the API. Reduce spacing for longer company details.
    leading=min(22,720/max(1,len(wrapped)))
    stream=f'BT /F1 11 Tf 48 790 Td {leading:.2f} TL '+' '.join(('T* ' if i else '')+'('+safe(line)+') Tj' for i,line in enumerate(wrapped))+' ET'
    encoded=stream.encode('cp1252')
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',b'<< /Length '+str(len(encoded)).encode()+b' >>\nstream\n'+encoded+b'\nendstream']
    out=bytearray(b'%PDF-1.4\n');offsets=[0]
    for i,obj in enumerate(objects,1):offsets.append(len(out));out.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
    xref=len(out);out.extend(b'xref\n0 6\n0000000000 65535 f \n')
    for offset in offsets[1:]:out.extend(f'{offset:010} 00000 n \n'.encode())
    out.extend(f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return bytes(out)
