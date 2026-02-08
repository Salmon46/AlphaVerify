"""
Email Sender for AlphaVerify Backtesting
Sends PDF reports via Brevo (formerly Sendinblue) API.
"""
import os
import io
import csv
import base64
import logging
from datetime import datetime
from typing import List, Dict, Any
import requests

logger = logging.getLogger(__name__)


def generate_trades_csv(trades: List[Dict[str, Any]]) -> bytes:
    """
    Generate a CSV file from the trades list.
    """
    output = io.StringIO()
    if not trades:
        return b'No trades'
    
    # Get all unique keys from trades
    fieldnames = ['timestamp', 'side', 'symbol', 'price', 'quantity', 'pnl']
    
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    
    for trade in trades:
        writer.writerow(trade)
    
    return output.getvalue().encode('utf-8')


def send_backtest_report(
    recipient_email: str,
    pdf_bytes: bytes,
    metrics: dict,
    trades: List[Dict[str, Any]] = None
) -> bool:
    """
    Send Backtest report via Brevo API.
    
    Requires environment variables:
    - BREVO_API_KEY: Your Brevo API key
    - BREVO_FROM_EMAIL: Your verified sender email
    - BREVO_FROM_NAME: Sender name (optional, defaults to AlphaVerify)
    
    Args:
        recipient_email: Email address to send report to
        pdf_bytes: The PDF report as bytes
        metrics: Dictionary of backtest metrics
    
    Returns:
        True if successful, False otherwise
    """
    api_key = os.getenv('BREVO_API_KEY')
    from_email = os.getenv('BREVO_FROM_EMAIL')
    from_name = os.getenv('BREVO_FROM_NAME', 'AlphaVerify')
    
    if not api_key or not from_email:
        logger.warning("Brevo credentials not configured. Skipping email.")
        return False
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"AlphaVerify_Backtest_{timestamp}.pdf"
    
    # Extract metrics
    total_return = metrics.get('total_return', 0)
    sharpe = metrics.get('sharpe_ratio', 0)
    max_dd = metrics.get('max_drawdown', 0)
    total_trades = metrics.get('total_trades', 0)
    win_rate = metrics.get('win_rate', 0)
    profit_factor = metrics.get('profit_factor', 0)
    final_equity = metrics.get('final_equity', 0)
    initial_equity = metrics.get('initial_equity', 10000)
    
    # Determine colors based on performance
    if total_return > 0:
        result_color = "#22c55e"  # Green
        result_emoji = "📈"
        result_text = "PROFITABLE"
    else:
        result_color = "#ef4444"  # Red
        result_emoji = "📉"
        result_text = "LOSS"
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto;">
            <h1 style="color: #6366f1; border-bottom: 2px solid #6366f1; padding-bottom: 10px;">
                📊 AlphaVerify - Backtest Complete
            </h1>
            
            <p>Your backtest has finished! Here's a quick overview:</p>
            
            <div style="background-color: #1e293b; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid {result_color};">
                <h2 style="color: {result_color}; margin-top: 0;">
                    {result_emoji} Result: {result_text}
                </h2>
                <p style="margin-bottom: 0; font-size: 24px; color: {result_color};">
                    <strong>{total_return:+.2f}%</strong> Total Return
                </p>
            </div>
            
            <div style="background-color: #1e293b; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h2 style="color: #94a3b8; margin-top: 0;">Performance Summary</h2>
                <table style="width: 100%; color: #e2e8f0;">
                    <tr>
                        <td style="padding: 8px 0;">Sharpe Ratio:</td>
                        <td style="text-align: right; color: #6366f1; font-weight: bold;">
                            {sharpe:.3f}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">Max Drawdown:</td>
                        <td style="text-align: right; color: #ef4444; font-weight: bold;">
                            {max_dd:.2f}%
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">Win Rate:</td>
                        <td style="text-align: right;">{win_rate:.1f}%</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">Profit Factor:</td>
                        <td style="text-align: right;">{profit_factor:.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">Total Trades:</td>
                        <td style="text-align: right;">{total_trades}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">Final Equity:</td>
                        <td style="text-align: right; font-weight: bold;">
                            ${final_equity:,.2f}
                        </td>
                    </tr>
                </table>
            </div>
            
            <p><strong>Attached:</strong><br>
            📊 Full PDF Report with equity curve and performance charts<br>
            📝 Complete trade log (CSV) with all {total_trades} trades</p>
            
            <hr style="border: 1px solid #475569; margin: 30px 0;">
            <p style="color: #64748b; font-size: 12px;">
                This report was generated by AlphaVerify Backtesting.<br>
                Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
AlphaVerify - Backtest Complete

Your test has finished!

Result: {result_text}
Total Return: {total_return:+.2f}%

Performance Summary:
- Sharpe Ratio: {sharpe:.3f}
- Max Drawdown: {max_dd:.2f}%
- Win Rate: {win_rate:.1f}%
- Profit Factor: {profit_factor:.2f}
- Total Trades: {total_trades}
- Final Equity: ${final_equity:,.2f}

Please see the attached PDF for the full report with equity curve.

Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    url = "https://api.brevo.com/v3/smtp/email"
    
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
    # Build attachments list
    attachments = [
        {
            "name": filename,
            "content": pdf_base64
        }
    ]
    
    # Add trades CSV if trades provided
    if trades:
        csv_bytes = generate_trades_csv(trades)
        csv_base64 = base64.b64encode(csv_bytes).decode('utf-8')
        csv_filename = f"AlphaVerify_Trades_{timestamp}.csv"
        attachments.append({
            "name": csv_filename,
            "content": csv_base64
        })
    
    payload = {
        "sender": {
            "email": from_email,
            "name": from_name
        },
        "to": [
            {
                "email": recipient_email,
                "name": "Trader"
            }
        ],
        "subject": f"📊 Backtest Report - {total_return:+.2f}% - {datetime.now().strftime('%Y-%m-%d')}",
        "htmlContent": html_body,
        "textContent": text_body,
        "attachment": attachments
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code in [200, 201, 202]:
            logger.info(f"Backtest report sent successfully to {recipient_email}")
            return True
        else:
            error_msg = response.text
            logger.error(f"Brevo API error: {response.status_code} - {error_msg}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Failed to send email: {e}")
        return False
