"""
Email Sender for AlphaVerify Permutation Testing
Sends PDF reports via Brevo (formerly Sendinblue) API.
"""
import os
import base64
import logging
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


def send_permutation_report(
    recipient_email: str,
    pdf_bytes: bytes,
    original_score: float,
    p_value: float,
    is_significant: bool,
    percentile: float,
    n_permutations: int,
    metric: str
) -> bool:
    """
    Send Permutation Test report via Brevo API.
    
    Requires environment variables:
    - BREVO_API_KEY: Your Brevo API key
    - BREVO_FROM_EMAIL: Your verified sender email
    - BREVO_FROM_NAME: Sender name (optional, defaults to AlphaVerify)
    
    Args:
        recipient_email: Email address to send report to
        pdf_bytes: The PDF report as bytes
        original_score: The strategy's score on original data
        p_value: Calculated p-value
        is_significant: Whether result is statistically significant
        percentile: What percentile the original score ranks at
        n_permutations: Number of permutations run
        metric: The metric tested (sharpe or profit_factor)
    
    Returns:
        True if successful, raises exception otherwise
    """
    api_key = os.getenv('BREVO_API_KEY')
    from_email = os.getenv('BREVO_FROM_EMAIL')
    from_name = os.getenv('BREVO_FROM_NAME', 'AlphaVerify')
    
    if not api_key or not from_email:
        logger.error("Brevo credentials not configured.")
        return False
        # raise ValueError(
        #     "Email credentials not configured. "
        #     "Set BREVO_API_KEY and BREVO_FROM_EMAIL environment variables."
        # )
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"AlphaVerify_PermTest_{timestamp}.pdf"
    
    # Determine colors and emojis based on significance
    if is_significant:
        result_color = "#22c55e"  # Green
        result_emoji = "✅"
        result_text = "SIGNIFICANT"
        result_description = "Your strategy shows statistically significant performance!"
    else:
        result_color = "#ef4444"  # Red
        result_emoji = "⚠️"
        result_text = "NOT SIGNIFICANT"
        result_description = "Your strategy's performance could be due to random chance."
    
    metric_label = "Sharpe Ratio" if metric == "sharpe" else "Profit Factor"
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto;">
            <h1 style="color: #6366f1; border-bottom: 2px solid #6366f1; padding-bottom: 10px;">
                📊 AlphaVerify - Permutation Test Complete
            </h1>
            
            <p>Your permutation test has finished! Here's a quick overview:</p>
            
            <div style="background-color: #1e293b; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid {result_color};">
                <h2 style="color: {result_color}; margin-top: 0;">
                    {result_emoji} Result: {result_text}
                </h2>
                <p style="margin-bottom: 0; color: #94a3b8;">{result_description}</p>
            </div>
            
            <div style="background-color: #1e293b; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h2 style="color: #94a3b8; margin-top: 0;">Test Summary</h2>
                <table style="width: 100%; color: #e2e8f0;">
                    <tr>
                        <td style="padding: 8px 0;">Original {metric_label}:</td>
                        <td style="text-align: right; color: #6366f1; font-weight: bold;">
                            {original_score:.4f}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">P-Value:</td>
                        <td style="text-align: right; color: {result_color}; font-weight: bold;">
                            {p_value:.4f} ({p_value*100:.2f}%)
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">Percentile Rank:</td>
                        <td style="text-align: right;">{percentile:.1f}%</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">Permutations Run:</td>
                        <td style="text-align: right;">{n_permutations:,}</td>
                    </tr>
                </table>
            </div>
            
            <p><strong>Attached:</strong> 📊 Full PDF Report with null distribution histogram and detailed analysis.</p>
            
            <div style="background-color: #1e3a5f; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #6366f1;">
                <p style="margin: 0; font-size: 14px;">
                    <strong>💡 What does this mean?</strong><br>
                    A p-value below 0.05 suggests your strategy's edge is unlikely to be due to 
                    random chance. The histogram shows where your strategy falls relative to 
                    randomly shuffled versions of your data.
                </p>
            </div>
            
            <hr style="border: 1px solid #475569; margin: 30px 0;">
            <p style="color: #64748b; font-size: 12px;">
                This report was generated by AlphaVerify Permutation Testing.<br>
                Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
AlphaVerify - Permutation Test Complete

Your test has finished!

Result: {result_text}
{result_description}

Test Summary:
- Original {metric_label}: {original_score:.4f}
- P-Value: {p_value:.4f} ({p_value*100:.2f}%)
- Percentile Rank: {percentile:.1f}%
- Permutations Run: {n_permutations:,}

Please see the attached PDF for the full report with histogram and analysis.

Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    url = "https://api.brevo.com/v3/smtp/email"
    
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
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
        "subject": f"📊 Permutation Test Report - {'SIGNIFICANT' if is_significant else 'Not Significant'} - {datetime.now().strftime('%Y-%m-%d')}",
        "htmlContent": html_body,
        "textContent": text_body,
        "attachment": [
            {
                "name": filename,
                "content": pdf_base64
            }
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code in [200, 201, 202]:
            logger.info(f"Permutation test report sent successfully to {recipient_email}")
            return True
        else:
            error_msg = response.text
            logger.error(f"Brevo API error: {response.status_code} - {error_msg}")
            # raise ValueError(f"Failed to send email: {error_msg}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Failed to send email: {e}")
        return False
