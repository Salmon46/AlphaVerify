"""
PDF Report Generator for AlphaVerify Monte Carlo Simulation
Creates professional reports with charts and statistical analysis.
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

# Removed missing import: from simulation_engine import SimulationResults

# Color palette (matches AlphaVerify branding)
COLORS = {
    'primary': '#3b82f6',      # Blue
    'secondary': '#8b5cf6',    # Purple
    'success': '#22c55e',      # Green
    'danger': '#ef4444',       # Red
    'warning': '#f59e0b',      # Amber
    'bg_dark': '#0f172a',      # Slate 900
    'bg_card': '#1e293b',      # Slate 800
    'text': '#e2e8f0',         # Slate 200
    'text_muted': '#94a3b8',   # Slate 400
}


def create_cone_chart(results: dict) -> bytes:
    """Create the Cone of Uncertainty chart."""
    fig, ax = plt.subplots(figsize=(10, 6), facecolor=COLORS['bg_dark'])
    ax.set_facecolor(COLORS['bg_dark'])
    
    # We expect percentile arrays from Rust JSON
    if 'equity_curve_50' not in results:
        # Fallback if not available
        return b""
        
    p5 = results['equity_curve_05']
    p50 = results['equity_curve_50']
    p95 = results['equity_curve_95']
    
    x = np.arange(len(p50))
    
    # Fill between 5th and 95th percentile
    ax.fill_between(x, p5, p95,
                    alpha=0.3, color=COLORS['primary'], label='90% Confidence Interval')
    
    # Median line
    ax.plot(x, p50, color=COLORS['primary'], 
            linewidth=2, label='Median Outcome')
    
    # Styling
    ax.set_xlabel('Trade Number', color=COLORS['text'], fontsize=12)
    ax.set_ylabel('Portfolio Value ($)', color=COLORS['text'], fontsize=12)
    ax.set_title('Cone of Uncertainty', color=COLORS['text'], fontsize=16, fontweight='bold')
    
    ax.tick_params(colors=COLORS['text_muted'])
    ax.spines['bottom'].set_color(COLORS['text_muted'])
    ax.spines['left'].set_color(COLORS['text_muted'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter('${x:,.0f}'))
    ax.legend(facecolor=COLORS['bg_card'], edgecolor=COLORS['text_muted'], 
              labelcolor=COLORS['text'])
    ax.grid(True, alpha=0.2, color=COLORS['text_muted'])
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, facecolor=COLORS['bg_dark'], 
                edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def create_drawdown_histogram(results: dict) -> bytes:
    """Create the Max Drawdown distribution histogram."""
    fig, ax = plt.subplots(figsize=(10, 5), facecolor=COLORS['bg_dark'])
    ax.set_facecolor(COLORS['bg_dark'])
    
    if 'max_drawdowns_dist' not in results:
         # Mock or empty
         return b""

    n, bins, patches = ax.hist(results['max_drawdowns_dist'], bins=50, 
                                color=COLORS['danger'], alpha=0.7, edgecolor='none')
    
    # Mean line
    mean_dd = results['mean_max_drawdown']
    ax.axvline(mean_dd, color=COLORS['warning'], linewidth=2, linestyle='--',
               label=f'Mean: {mean_dd:.1f}%')
    
    # 95th percentile line
    dd_95 = results['max_drawdown_95']
    ax.axvline(dd_95, color=COLORS['danger'], linewidth=2, linestyle='-',
               label=f'95th Percentile: {dd_95:.1f}%')
    
    # Styling
    ax.set_xlabel('Maximum Drawdown (%)', color=COLORS['text'], fontsize=12)
    ax.set_ylabel('Frequency', color=COLORS['text'], fontsize=12)
    ax.set_title('Maximum Drawdown Distribution', color=COLORS['text'], 
                 fontsize=16, fontweight='bold')
    
    ax.tick_params(colors=COLORS['text_muted'])
    ax.spines['bottom'].set_color(COLORS['text_muted'])
    ax.spines['left'].set_color(COLORS['text_muted'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(facecolor=COLORS['bg_card'], edgecolor=COLORS['text_muted'],
              labelcolor=COLORS['text'])
    ax.grid(True, alpha=0.2, color=COLORS['text_muted'])
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, facecolor=COLORS['bg_dark'],
                edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def create_return_histogram(results: dict) -> bytes:
    """Create the Total Return distribution histogram."""
    # Similar issue: need `total_returns_dist` from Rust.
    if 'total_returns_dist' not in results: return b""
    
    fig, ax = plt.subplots(figsize=(10, 5), facecolor=COLORS['bg_dark'])
    ax.set_facecolor(COLORS['bg_dark'])
    
    # Color bars based on positive/negative
    n, bins, patches = ax.hist(results['total_returns_dist'], bins=50,
                                alpha=0.7, edgecolor='none')
    
    # Color each bar
    for patch, left_edge in zip(patches, bins[:-1]):
        if left_edge >= 0:
            patch.set_facecolor(COLORS['success'])
        else:
            patch.set_facecolor(COLORS['danger'])
    
    # Mean line
    mean_ret = results['mean_return']
    color = COLORS['success'] if mean_ret >= 0 else COLORS['danger']
    ax.axvline(mean_ret, color=color, linewidth=2, linestyle='--',
               label=f'Mean: {mean_ret:.1f}%')
    
    # Styling
    ax.set_xlabel('Total Return (%)', color=COLORS['text'], fontsize=12)
    ax.set_ylabel('Frequency', color=COLORS['text'], fontsize=12)
    ax.set_title('Total Return Distribution', color=COLORS['text'],
                 fontsize=16, fontweight='bold')
    
    ax.tick_params(colors=COLORS['text_muted'])
    ax.spines['bottom'].set_color(COLORS['text_muted'])
    ax.spines['left'].set_color(COLORS['text_muted'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(facecolor=COLORS['bg_card'], edgecolor=COLORS['text_muted'],
              labelcolor=COLORS['text'])
    ax.grid(True, alpha=0.2, color=COLORS['text_muted'])
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, facecolor=COLORS['bg_dark'],
                edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_pdf_report(results: dict) -> bytes:
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
    
    # === COVER PAGE ===
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("AlphaVerify", title_style))
    story.append(Paragraph("Monte Carlo Simulation Report", ParagraphStyle(
        'Subtitle', parent=styles['Heading1'], fontSize=22,
        textColor=colors.HexColor(COLORS['text_muted']),
        alignment=TA_CENTER
    )))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}",
        ParagraphStyle('Date', parent=body_style, alignment=TA_CENTER)
    ))
    story.append(Paragraph(
        f"Simulations: {results['n_simulations']:,}",
        ParagraphStyle('Meta', parent=body_style, alignment=TA_CENTER)
    ))
    story.append(PageBreak())
    
    # === EXECUTIVE SUMMARY ===
    story.append(Paragraph("Executive Summary", heading_style))
    
    # Key metrics table
    summary_data = [
        ['Metric', 'Value', 'Interpretation'],
        ['Expected Return', f'{results["mean_return"]:.2f}%', 
         'Profitable' if results["mean_return"] > 0 else 'Loss Expected'],
        ['Return Std Dev', f'{results["std_return"]:.2f}%', 
         'Low' if results["std_return"] < 20 else ('Moderate' if results["std_return"] < 50 else 'High')],
        ['Mean Max Drawdown', f'{results["mean_max_drawdown"]:.2f}%', 
         'Manageable' if results["mean_max_drawdown"] < 20 else 'Significant'],
        ['95% VaR Max DD', f'{results["max_drawdown_95"]:.2f}%',
         '95% confidence DD stays below this'],
        ['Risk of Ruin (50%)', f'{results["risk_of_ruin"]:.2f}%',
         'Low' if results["risk_of_ruin"] < 5 else ('Moderate' if results["risk_of_ruin"] < 20 else 'High')],
    ]
    
    summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch, 3*inch])
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
    story.append(Spacer(1, 0.3*inch))
    
    # Trade statistics
    story.append(Paragraph("Trade Statistics", heading_style))
    trade_data = [
        ['Processing Time', f"{results.get('processing_time_seconds', 0)}s"],
        ['Engine', 'Rust Optimized']
    ]
    trade_table = Table(trade_data, colWidths=[1.625*inch]*4)
    trade_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLORS['secondary'])),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1e293b')),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('TOPPADDING', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
    ]))
    story.append(trade_table)
    story.append(PageBreak())
    
    # === CONE OF UNCERTAINTY ===
    story.append(Paragraph("Cone of Uncertainty Analysis", heading_style))
    story.append(Paragraph(
        "The chart below shows the range of possible equity outcomes based on reshuffling "
        "your historical trades. The shaded area represents the 90% confidence interval - "
        "meaning 90% of simulated outcomes fall within this band.",
        body_style
    ))
    
    cone_chart = create_cone_chart(results)
    if cone_chart:
        story.append(Spacer(1, 0.2*inch))
        story.append(Image(io.BytesIO(cone_chart), width=7*inch, height=4.2*inch))
    story.append(Spacer(1, 0.3*inch))
    
    # Cone interpretation
    p5_final = results['final_equity_05']
    p95_final = results['final_equity_95']
    story.append(Paragraph(
        f"<b>Key Insight:</b> At the end of the simulation, there is a 90% probability "
        f"that your portfolio value will be between <b>${p5_final:,.0f}</b> and <b>${p95_final:,.0f}</b> "
        f"(starting from initial capital).",
        body_style
    ))
    story.append(PageBreak())
    
    # === DRAWDOWN ANALYSIS ===
    story.append(Paragraph("Maximum Drawdown Analysis", heading_style))
    story.append(Paragraph(
        "Maximum drawdown measures the largest peak-to-trough decline in portfolio value. "
        "This analysis helps you understand the range of potential losses you might experience.",
        body_style
    ))
    
    dd_chart = create_drawdown_histogram(results)
    if dd_chart:
        story.append(Spacer(1, 0.2*inch))
        story.append(Image(io.BytesIO(dd_chart), width=7*inch, height=3.5*inch))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph(
        f"<b>Key Insight:</b> There is a 95% confidence that your maximum drawdown will not exceed "
        f"<b>{results['max_drawdown_95']:.1f}%</b>. The average expected drawdown is {results['mean_max_drawdown']:.1f}%.",
        body_style
    ))
    
    # === RETURN DISTRIBUTION ===
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Return Distribution", heading_style))
    story.append(Paragraph(
        "This histogram shows the distribution of total returns across all simulations, "
        "giving insight into the probability of different outcome scenarios.",
        body_style
    ))
    
    return_chart = create_return_histogram(results)
    if return_chart:
        story.append(Spacer(1, 0.2*inch))
        story.append(Image(io.BytesIO(return_chart), width=7*inch, height=3.5*inch))
    story.append(PageBreak())
    
    # === METHODOLOGY ===
    story.append(Paragraph("Methodology", heading_style))
    story.append(Paragraph(
        f"This report was generated using Monte Carlo simulation with the following parameters:",
        body_style
    ))
    
    method_data = [
        ['Parameter', 'Value'],
        ['Number of Simulations', f'{results["n_simulations"]:,}'],
        ['Initial Capital', f'${results.get("initial_capital", 0):,.2f}'],
        ['Resampling Method', 'Resampling with Replacement (Bootstrap)'],
        ['Ruin Threshold', '50% of Initial Capital'],
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
        "<b>Disclaimer:</b> Monte Carlo simulation provides probabilistic estimates based on "
        "historical data. Past performance does not guarantee future results. The reshuffling "
        "process assumes trade outcomes are independent and identically distributed. "
        "Market conditions can change significantly over time.",
        ParagraphStyle('Disclaimer', parent=body_style, fontSize=9, 
                      textColor=colors.HexColor('#64748b'))
    ))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
