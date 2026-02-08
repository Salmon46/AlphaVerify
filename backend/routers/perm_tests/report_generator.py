"""
PDF Report Generator for AlphaVerify Permutation Testing
Creates professional reports with histogram and statistical analysis.
"""
import io
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from .stats import PermutationTestResult


# Color palette (matches AlphaVerify branding)
COLORS = {
    'primary': '#6366f1',      # Indigo
    'secondary': '#8b5cf6',    # Purple
    'success': '#22c55e',      # Green
    'danger': '#ef4444',       # Red
    'warning': '#f59e0b',      # Amber
    'bg_dark': '#0f172a',      # Slate 900
    'bg_card': '#1e293b',      # Slate 800
    'text': '#e2e8f0',         # Slate 200
    'text_muted': '#94a3b8',   # Slate 400
}


def create_histogram_chart(result: PermutationTestResult) -> bytes:
    """Create the null distribution histogram with original score marker."""
    fig, ax = plt.subplots(figsize=(10, 6), facecolor=COLORS['bg_dark'])
    ax.set_facecolor(COLORS['bg_dark'])
    
    scores = np.array(result.permuted_scores)
    
    # Histogram
    n, bins, patches = ax.hist(scores, bins=40, 
                                color=COLORS['primary'], alpha=0.7, edgecolor='none')
    
    # Original score line
    ax.axvline(result.original_score, color=COLORS['danger'], linewidth=3, linestyle='--',
               label=f'Original: {result.original_score:.4f}')
    
    # Mean line
    ax.axvline(result.permuted_mean, color=COLORS['warning'], linewidth=2, linestyle=':',
               label=f'Permuted Mean: {result.permuted_mean:.4f}')
    
    # Styling
    metric_label = "Sharpe Ratio" if result.metric_name == "sharpe" else "Profit Factor"
    ax.set_xlabel(metric_label, color=COLORS['text'], fontsize=12)
    ax.set_ylabel('Frequency', color=COLORS['text'], fontsize=12)
    ax.set_title('Null Distribution (Permuted Data)', color=COLORS['text'], 
                 fontsize=16, fontweight='bold')
    
    ax.tick_params(colors=COLORS['text_muted'])
    ax.spines['bottom'].set_color(COLORS['text_muted'])
    ax.spines['left'].set_color(COLORS['text_muted'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    ax.legend(facecolor=COLORS['bg_card'], edgecolor=COLORS['text_muted'], 
              labelcolor=COLORS['text'], fontsize=10)
    ax.grid(True, alpha=0.2, color=COLORS['text_muted'])
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, facecolor=COLORS['bg_dark'], 
                edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_pdf_report(result: PermutationTestResult) -> bytes:
    """Generate the complete PDF report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           leftMargin=0.75*inch, rightMargin=0.75*inch,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        spaceAfter=30,
        textColor=colors.HexColor(COLORS['primary']),
        alignment=TA_CENTER
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=18,
        spaceBefore=20,
        spaceAfter=12,
        textColor=colors.HexColor(COLORS['primary'])
    )
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=8,
        textColor=colors.HexColor('#333333')
    )
    
    story = []
    
    metric_label = "Sharpe Ratio" if result.metric_name == "sharpe" else "Profit Factor"
    
    # === COVER PAGE ===
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("AlphaVerify", title_style))
    story.append(Paragraph("Permutation Test Report", ParagraphStyle(
        'Subtitle', parent=styles['Heading1'], fontSize=22,
        textColor=colors.HexColor(COLORS['text_muted']),
        alignment=TA_CENTER
    )))
    story.append(Spacer(1, 0.5*inch))
    
    # Result badge
    if result.is_significant:
        badge_color = COLORS['success']
        badge_text = "✓ STATISTICALLY SIGNIFICANT"
    else:
        badge_color = COLORS['danger']
        badge_text = "✗ NOT STATISTICALLY SIGNIFICANT"
    
    story.append(Paragraph(badge_text, ParagraphStyle(
        'Badge', parent=styles['Heading2'], fontSize=16,
        textColor=colors.HexColor(badge_color),
        alignment=TA_CENTER
    )))
    
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}",
        ParagraphStyle('Date', parent=body_style, alignment=TA_CENTER)
    ))
    story.append(Paragraph(
        f"Permutations: {result.n_permutations:,} | Metric: {metric_label}",
        ParagraphStyle('Meta', parent=body_style, alignment=TA_CENTER)
    ))
    story.append(PageBreak())
    
    # === EXECUTIVE SUMMARY ===
    story.append(Paragraph("Executive Summary", heading_style))
    
    # Key metrics table
    p_value_color = COLORS['success'] if result.p_value < 0.05 else COLORS['danger']
    
    summary_data = [
        ['Metric', 'Value', 'Interpretation'],
        [f'Original {metric_label}', f'{result.original_score:.4f}', 
         'Your strategy\'s actual performance'],
        ['P-Value', f'{result.p_value:.4f} ({result.p_value*100:.2f}%)', 
         'Significant' if result.p_value < 0.05 else 'Not Significant'],
        ['Percentile Rank', f'{result.percentile:.1f}%',
         f'Outperforms {result.percentile:.0f}% of random permutations'],
        ['Permuted Mean', f'{result.permuted_mean:.4f}',
         'Average score under null hypothesis'],
        ['Permuted Std Dev', f'{result.permuted_std:.4f}',
         'Spread of null distribution'],
    ]
    
    summary_table = Table(summary_data, colWidths=[2*inch, 1.8*inch, 2.7*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLORS['primary'])),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1e293b')),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(PageBreak())
    
    # === NULL DISTRIBUTION ===
    story.append(Paragraph("Null Distribution Analysis", heading_style))
    story.append(Paragraph(
        "The histogram below shows the distribution of " + metric_label + " values when "
        "your trade returns are randomly shuffled. This represents what performance "
        "would look like if there were no true edge in your strategy.",
        body_style
    ))
    
    histogram_chart = create_histogram_chart(result)
    story.append(Spacer(1, 0.2*inch))
    story.append(Image(io.BytesIO(histogram_chart), width=7*inch, height=4.2*inch))
    story.append(Spacer(1, 0.3*inch))
    
    # Interpretation
    if result.is_significant:
        interpretation = (
            f"<b>Key Insight:</b> Your strategy's {metric_label} of <b>{result.original_score:.4f}</b> "
            f"ranks at the <b>{result.percentile:.1f}th percentile</b> of the null distribution. "
            f"Only <b>{result.p_value*100:.2f}%</b> of random permutations achieved an equal or higher score. "
            f"This suggests your strategy's edge is unlikely to be due to chance alone."
        )
    else:
        interpretation = (
            f"<b>Key Insight:</b> Your strategy's {metric_label} of <b>{result.original_score:.4f}</b> "
            f"falls within the normal range of random variation. <b>{result.p_value*100:.2f}%</b> of "
            f"random permutations achieved an equal or higher score. "
            f"This could indicate overfitting or that the edge may not be robust."
        )
    
    story.append(Paragraph(interpretation, body_style))
    story.append(PageBreak())
    
    # === METHODOLOGY ===
    story.append(Paragraph("Methodology", heading_style))
    story.append(Paragraph(
        "This report was generated using permutation testing with the following process:",
        body_style
    ))
    
    story.append(Paragraph(
        "<b>1. Baseline Test:</b> Run your strategy on the original, unshuffled OHLC data.",
        body_style
    ))
    story.append(Paragraph(
        "<b>2. Permutation:</b> Shuffle the order of daily returns while preserving volatility characteristics.",
        body_style
    ))
    story.append(Paragraph(
        "<b>3. Reconstruction:</b> Build new OHLC bars from shuffled returns with realistic High/Low values.",
        body_style
    ))
    story.append(Paragraph(
        "<b>4. Backtest:</b> Run your strategy on each permuted dataset.",
        body_style
    ))
    story.append(Paragraph(
        "<b>5. Analysis:</b> Compare your original score to the distribution of permuted scores.",
        body_style
    ))
    
    story.append(Spacer(1, 0.3*inch))
    
    method_data = [
        ['Parameter', 'Value'],
        ['Number of Permutations', f'{result.n_permutations:,}'],
        ['Performance Metric', metric_label],
        ['Significance Level (α)', f'{result.alpha}'],
        ['Test Type', 'One-tailed (right)'],
    ]
    method_table = Table(method_data, colWidths=[3*inch, 3.5*inch])
    method_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#64748b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1e293b')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(Spacer(1, 0.2*inch))
    story.append(method_table)
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph(
        "<b>Disclaimer:</b> Permutation testing provides statistical validation based on "
        "historical data. A significant result does not guarantee future performance. "
        "The test assumes that trade outcomes in the shuffled data are valid approximations "
        "of what could have occurred under different market conditions.",
        ParagraphStyle('Disclaimer', parent=body_style, fontSize=9, 
                      textColor=colors.HexColor('#64748b'))
    ))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
