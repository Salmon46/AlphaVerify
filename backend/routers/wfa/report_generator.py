# alphaVerify-WFA/backend/app/report_generator.py
import io
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime

def generate_wfa_pdf(result_data: dict, config: dict):
    """
    Generates a PDF report for Walk-Forward Analysis.
    
    Args:
        result_data: Dict containing 'metrics', 'wfe', 'segments', 'equity_curve'.
        config: Dict containing WFA settings.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # --- Title Page ---
    title_style = styles['Title']
    story.append(Paragraph("Walk-Forward Analysis Report", title_style))
    story.append(Spacer(1, 0.2 * inch))
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph(f"Generated on: {timestamp}", styles['Normal']))
    story.append(Spacer(1, 0.5 * inch))
    
    # --- 1. Overview ---
    header_style = ParagraphStyle('Header2', parent=styles['Heading2'], spaceAfter=10)
    story.append(Paragraph("1. Analysis Overview", header_style))
    
    metrics = result_data.get('metrics', {})
    wfe = result_data.get('wfe', 0.0)
    
    intro_text = f"""
    <b>Strategy File:</b> {config.get('strategy_filename', 'N/A')}<br/>
    <b>Window Size:</b> {config.get('window_size_days')} days<br/>
    <b>Step Size:</b> {config.get('step_size_days')} days<br/>
    <b>Total Segments:</b> {len(result_data.get('segments', []))}
    """
    story.append(Paragraph(intro_text, styles['Normal']))
    story.append(Spacer(1, 0.3 * inch))
    
    # --- 2. Performance Summary (OOS) ---
    story.append(Paragraph("2. Out-of-Sample Performance", header_style))
    
    summary_data = [
        ["Metric", "Value"],
        ["Total Return", f"{metrics.get('total_return', 0)*100:.2f}%"],
        ["Annualized Sharpe", f"{metrics.get('sharpe', 0):.4f}"],
        ["Max Drawdown", f"{metrics.get('max_dd', 0)*100:.2f}%"],
        ["Walk-Forward Efficiency (WFE)", f"{wfe:.2f}"],
    ]
    
    t = Table(summary_data, colWidths=[3*inch, 2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2 * inch))
    
    if wfe > 0.7:
        verdict = "<font color='green'><b>Robust</b> (WFE > 0.7)</font>"
    elif wfe > 0.5:
        verdict = "<font color='orange'><b>Acceptable</b> (WFE > 0.5)</font>"
    else:
        verdict = "<font color='red'><b>Fragile</b> (WFE < 0.5)</font>"
        
    story.append(Paragraph(f"Robustness Verdict: {verdict}", styles['Normal']))
    story.append(PageBreak())

    # --- 3. Equity Curve ---
    story.append(Paragraph("3. Stitched Equity Curve (OOS)", header_style))
    story.append(Paragraph("This curve represents the cumulative performance of the strategy trading strictly on unseen data.", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))
    
    equity_curve = result_data.get('equity_curve', [])
    if equity_curve:
        plt.figure(figsize=(7, 4))
        plt.plot(equity_curve, color='blue', linewidth=1.5)
        plt.title('Walk-Forward Equity Curve')
        plt.xlabel('Trades / Days')
        plt.ylabel('Equity Multiplier')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=100)
        img_buffer.seek(0)
        plt.close()
        
        story.append(Image(img_buffer, width=6*inch, height=3.5*inch))
    else:
        story.append(Paragraph("No equity data available.", styles['Normal']))
        
    story.append(PageBreak())

    # --- 4. Segment Analysis ---
    story.append(Paragraph("4. Segment Analysis", header_style))
    
    segments = result_data.get('segments', [])
    if segments:
        # Table of Segments
        seg_data = [["Start", "End", "IS Metric", "OOS Metric", "WFE"]]
        
        for seg in segments:
            is_m = seg.get('is_metric', 0)
            oos_m = seg.get('oos_metric', 0)
            seg_wfe = oos_m / is_m if is_m != 0 else 0
            
            seg_data.append([
                seg.get('start', ''),
                seg.get('end', ''),
                f"{is_m:.4f}",
                f"{oos_m:.4f}",
                f"{seg_wfe:.2f}"
            ])
            
        t2 = Table(seg_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, 1*inch, 1*inch])
        t2.setStyle(TableStyle([
             ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
             ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
             ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
             ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
             ('FONTSIZE', (0, 0), (-1, -1), 10),
        ]))
        story.append(t2)
        
        # WFE Stability Plot
        wfe_vals = []
        for seg in segments:
            is_m = seg.get('is_metric', 0)
            oos_m = seg.get('oos_metric', 0)
            val = oos_m / is_m if is_m != 0 else 0
            wfe_vals.append(val)
            
        plt.figure(figsize=(7, 3))
        plt.bar(range(len(wfe_vals)), wfe_vals, color='purple', alpha=0.7)
        plt.axhline(0.5, color='red', linestyle='--', alpha=0.5)
        plt.title('Walk-Forward Efficiency per Segment')
        plt.xlabel('Segment Index')
        plt.ylabel('WFE Ratio')
        plt.tight_layout()
        
        img_buffer2 = io.BytesIO()
        plt.savefig(img_buffer2, format='png', dpi=100)
        img_buffer2.seek(0)
        plt.close()
        
        story.append(Spacer(1, 0.3*inch))
        story.append(Image(img_buffer2, width=6*inch, height=3*inch))
        
    doc.build(story)
    buffer.seek(0)
    return buffer
