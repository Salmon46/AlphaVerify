import os
import io
from .report_generator import generate_sensitivity_pdf
import csv
import base64
from datetime import datetime
import logging
import requests
import json
import matplotlib
matplotlib.use('Agg') # Headless mode
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

def generate_sensitivity_csv(results: list, param_names: list) -> bytes:
    """Generate a CSV file from sensitivity analysis results."""
    if not results:
        return b""
    
    output = io.StringIO()
    
    # Define columns
    fieldnames = ['id'] + param_names + ['sharpe', 'total_return']
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for res in results:
        row = {'id': res['id']}
        # Add params
        for p in param_names:
            row[p] = res['params'].get(p, '')
        # Add metrics
        row['sharpe'] = res['metrics'].get('sharpe', 0)
        row['total_return'] = res['metrics'].get('total_return', 0)
        
        writer.writerow(row)
    
    return output.getvalue().encode('utf-8')


def generate_plots(results: list) -> dict:
    """Generate plots for the email report (returning base64 strings)."""
    if not results:
        return {}
    
    sharpes = [r['metrics']['sharpe'] for r in results]
    returns = [r['metrics']['total_return'] for r in results]
    
    plots = {}
    
    # 1. Histogram of Sharpe Ratios
    plt.figure(figsize=(6, 4))
    plt.hist(sharpes, bins=30, color='#f97316', alpha=0.7, edgecolor='black')
    plt.title('Distribution of Sharpe Ratios', color='white')
    plt.xlabel('Sharpe Ratio', color='white')
    plt.ylabel('Frequency', color='white')
    
    # Style for dark theme email
    ax = plt.gca()
    ax.set_facecolor('#1e293b')
    plt.gcf().set_facecolor('#0f172a')
    ax.tick_params(colors='white')
    for spine in ax.spines.values():
        spine.set_color('#475569')
        
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    plots['sharpe_hist'] = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    return plots


def calculate_stats(results: list) -> dict:
    """Calculate basic statistics for the results."""
    sharpes = [r['metrics']['sharpe'] for r in results]
    returns = [r['metrics']['total_return'] for r in results]
    
    return {
        'sharpe_mean': np.mean(sharpes),
        'sharpe_median': np.median(sharpes),
        'sharpe_std': np.std(sharpes),
        'return_mean': np.mean(returns),
        'return_median': np.median(returns)
    }


def send_sensitivity_email(
    recipient_email: str,
    results: list,
    param_names: list,
    best_result: dict,
    total_runs: int
) -> bool:
    """
    Send sensitivity analysis report via Brevo.
    """
    # Get credentials from environment
    api_key = os.getenv('BREVO_API_KEY')
    from_email = os.getenv('BREVO_FROM_EMAIL')
    from_name = os.getenv('BREVO_FROM_NAME', 'AlphaVerify')
    
    if not api_key or not from_email:
        logger.error("Brevo credentials not configured.")
        return False
    
    if not results:
        logger.warning("No results to send.")
        return False

    # Generate filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f"Sensitivity_Results_{timestamp}.csv"
    pdf_filename = f"Sensitivity_Report_{timestamp}.pdf"
    
    # Prepare metrics for email body
    max_sharpe = best_result['metrics']['sharpe']
    max_return = best_result['metrics']['total_return']
    best_params = ", ".join([f"{k}={v}" for k, v in best_result['params'].items()])
    
    # Calculate stats and plots
    stats = calculate_stats(results)
    plots = generate_plots(results)
    
    # HTML email body
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto;">
            <h1 style="color: #f97316; border-bottom: 2px solid #f97316; padding-bottom: 10px;">
                AlphaVerify - Sensitivity Analysis
            </h1>
            
            <p>Your sensitivity analysis has completed! Here's a quick summary:</p>
            
            <div style="background-color: #1e293b; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h2 style="color: #94a3b8; margin-top: 0;">Optimization Summary</h2>
                <table style="width: 100%; color: #e2e8f0;">
                    <tr>
                        <td style="padding: 8px 0;">Total Runs:</td>
                        <td style="text-align: right;">{total_runs}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">Max Sharpe:</td>
                        <td style="text-align: right; color: #22c55e; font-weight: bold;">{max_sharpe:.4f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">Max Return:</td>
                        <td style="text-align: right;">{max_return * 100:.2f}%</td>
                    </tr>
                </table>
                
                <h3 style="color: #94a3b8; margin-top: 20px; border-bottom: 1px solid #475569; padding-bottom: 5px;">Statistical Analysis</h3>
                <table style="width: 100%; color: #cbd5e1; font-size: 14px;">
                    <tr>
                        <td>Avg Sharpe:</td>
                        <td style="text-align: right;">{stats['sharpe_mean']:.4f}</td>
                    </tr>
                    <tr>
                        <td>Median Sharpe:</td>
                        <td style="text-align: right;">{stats['sharpe_median']:.4f}</td>
                    </tr>
                    <tr>
                        <td>Sharpe Std Dev:</td>
                        <td style="text-align: right;">{stats['sharpe_std']:.4f}</td>
                    </tr>
                </table>

                <div style="margin-top: 20px; text-align: center;">
                    <img src="data:image/png;base64,{plots.get('sharpe_hist', '')}" style="max-width: 100%; border-radius: 4px; border: 1px solid #475569;" />
                    <p style="font-size: 12px; color: #94a3b8;">Distribution of Sharpe Ratios</p>
                </div>
                
                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #475569;">
                    <div style="font-size: 12px; color: #94a3b8; margin-bottom: 5px;">Best Parameters:</div>
                    <div style="font-family: monospace; background: #0f172a; padding: 8px; rounded: 4px; font-size: 12px;">
                        {best_params}
                    </div>
                </div>
            </div>
            
            <p><strong>Attachments:</strong></p>
            <ul>
                <li>📊 <strong>Results CSV</strong> - Complete dataset of all parameter combinations</li>
            </ul>
            
            <hr style="border: 1px solid #475569; margin: 30px 0;">
            <p style="color: #64748b; font-size: 12px;">
                Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
        </div>
    </body>
    </html>
    """
    
    # Simple Text Body
    text_body = f"""
AlphaVerify Sensitivity Analysis

Total Runs: {total_runs}
Max Sharpe: {max_sharpe:.4f}
Max Return: {max_return * 100:.2f}%

Best Parameters:
{best_params}

See attached CSV for full results.
    """
    
    # Brevo API endpoint
    url = "https://api.brevo.com/v3/smtp/email"
    
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # CSV Attachment
    csv_bytes = generate_sensitivity_csv(results, param_names)
    csv_base64 = base64.b64encode(csv_bytes).decode('utf-8')
    
    # PDF Attachment
    try:
        df_results = pd.DataFrame(results)
        df_metrics = pd.json_normalize(df_results['metrics'])
        df_params = pd.json_normalize(df_results['params'])
        # Rename columns to avoid collision if needed, but simple concat usually works for report
        full_df = pd.concat([df_metrics, df_params], axis=1)
        
        pdf_buffer = generate_sensitivity_pdf(full_df, {'mode': 'Unknown'})
        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"PDF Generation Failed: {e}")
        pdf_base64 = None

    attachments = [
        {
             "name": csv_filename,
             "content": csv_base64
        }
    ]
    
    if pdf_base64:
        attachments.append({
            "name": pdf_filename,
            "content": pdf_base64
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
        "subject": f"🔥 Sensitivity Results - Max Sharpe {max_sharpe:.4f}",
        "htmlContent": html_body,
        "textContent": text_body,
        "attachment": attachments
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201, 202]:
            logger.info(f"Email sent to {recipient_email}")
            return True
        else:
            logger.error(f"Brevo Error: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Email exception: {e}")
        return False
