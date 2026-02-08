import os
import io
import base64
import requests
import logging
from datetime import datetime
import pandas as pd
from .report_generator import generate_wfa_pdf

logger = logging.getLogger(__name__)

def generate_wfa_csv(segments: list) -> bytes:
    if not segments:
        return b""
    df = pd.DataFrame(segments)
    # flattened params if needed? params column is dict
    return df.to_csv(index=False).encode('utf-8')

def send_wfa_email(
    recipient_email: str,
    result_payload: dict,
    config: dict
) -> bool:
    api_key = os.getenv('BREVO_API_KEY')
    from_email = os.getenv('BREVO_FROM_EMAIL')
    from_name = os.getenv('BREVO_FROM_NAME', 'AlphaVerify')
    
    if not api_key or not from_email:
        logger.error("Brevo credentials missing.")
        return False
        
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f"WFA_Segments_{timestamp}.csv"
    pdf_filename = f"WFA_Report_{timestamp}.pdf"
    
    metrics = result_payload.get('metrics', {})
    wfe = result_payload.get('wfe', 0.0)
    
    # Generate CSV
    csv_bytes = generate_wfa_csv(result_payload.get('segments', []))
    csv_base64 = base64.b64encode(csv_bytes).decode('utf-8')
    
    # Generate PDF
    try:
        pdf_buffer = generate_wfa_pdf(result_payload, config)
        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"PDF Gen failed: {e}")
        pdf_base64 = None

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto;">
            <h1 style="color: #3b82f6;">AlphaVerify - WFA Results</h1>
            <div style="background-color: #1e293b; padding: 20px; border-radius: 8px;">
                <p><strong>Total Return:</strong> {metrics.get('total_return', 0)*100:.2f}%</p>
                <p><strong>Sharpe Ratio:</strong> {metrics.get('sharpe', 0):.4f}</p>
                <p><strong>WFE Score:</strong> <span style="color: {'#22c55e' if wfe > 0.5 else '#ef4444'}">{wfe:.2f}</span></p>
            </div>
            <p>See attached PDF for full details.</p>
        </div>
    </body>
    </html>
    """
    
    attachments = [{"name": csv_filename, "content": csv_base64}]
    if pdf_base64:
        attachments.append({"name": pdf_filename, "content": pdf_base64})
        
    payload = {
        "sender": {"email": from_email, "name": from_name},
        "to": [{"email": recipient_email, "name": "Trader"}],
        "subject": f"WFA Results - WFE: {wfe:.2f}",
        "htmlContent": html_body,
        "attachment": attachments
    }
    
    try:
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {"api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"}
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code in [200, 201, 202]:
            logger.info(f"Email sent to {recipient_email}")
            return True
        logger.error(f"Brevo: {res.text}")
        return False
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return False
