"""
PDF Report Generator for AlphaVerify Backtesting
Creates professional tearsheet reports with equity curve, underwater plot, 
monthly heatmap, and comprehensive metrics.

Based on the alphaVerify-backtest report structure.
"""
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd
import numpy as np
import seaborn as sns
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# Set style
plt.style.use('dark_background')

# AlphaVerify color theme
COLORS = {
    'primary': '#3b82f6',       # Blue
    'success': '#22c55e',       # Green
    'danger': '#ef4444',        # Red
    'bg_dark': '#0f172a',       # Slate 900
    'bg_card': '#1e293b',       # Slate 800
    'text': '#e2e8f0',          # Slate 200
    'text_muted': '#94a3b8',    # Slate 400
}


def calculate_advanced_metrics(equity_curve: List[Dict], trades: List[Dict]) -> Dict[str, float]:
    """Calculate Sortino, Calmar, Kelly, etc."""
    if not equity_curve:
        return {}
    
    df = pd.DataFrame(equity_curve)
    if 'value' not in df.columns: 
        return {}
    
    df['returns'] = df['value'].pct_change().fillna(0)
    
    # Annualization factor (assuming daily)
    ann_factor = 252
    
    # 1. Sortino
    target_return = 0
    downside_returns = df.loc[df['returns'] < target_return, 'returns']
    downside_std = downside_returns.std() * np.sqrt(ann_factor) if len(downside_returns) > 0 else 0
    mean_return = df['returns'].mean() * ann_factor
    sortino = mean_return / downside_std if downside_std != 0 else 0
    
    # 2. Calmar
    max_dd = 0
    peak = df['value'].iloc[0]
    for val in df['value']:
        if val > peak: peak = val
        dd = (peak - val) / peak
        if dd > max_dd: max_dd = dd
    
    calmar = mean_return / max_dd if max_dd != 0 else 0
    
    # 3. Kelly Criterion
    sell_trades = [t for t in trades if t.get('side') == 'SELL']
    if not sell_trades:
        kelly = 0
    else:
        wins = [t['pnl'] for t in sell_trades if t.get('pnl', 0) > 0]
        losses = [abs(t['pnl']) for t in sell_trades if t.get('pnl', 0) <= 0]
        
        if not losses:
            kelly = 1.0
        else:
            win_rate = len(wins) / len(sell_trades)
            avg_win = np.mean(wins) if wins else 0
            avg_loss = np.mean(losses) if losses else 0
            win_loss_ratio = avg_win / avg_loss if avg_loss != 0 else 1
            if win_loss_ratio == 0:
                kelly = 0
            else:
                kelly = win_rate - ((1 - win_rate) / win_loss_ratio)
    
    return {
        "Sortino Ratio": sortino,
        "Calmar Ratio": calmar,
        "Kelly Criterion": kelly,
        "Annual Volatility": df['returns'].std() * np.sqrt(ann_factor)
    }


def generate_tearsheet_charts(equity_curve: List[Dict]) -> Dict[str, bytes]:
    """Generate Equity, Underwater, and Heatmap charts."""
    charts = {}
    if not equity_curve: 
        return charts

    df = pd.DataFrame(equity_curve)
    
    # Parse dates
    try:
        df['date'] = pd.to_datetime([e['time'][:19] for e in equity_curve])
    except Exception:
        return charts
    
    df.set_index('date', inplace=True)
    df['returns'] = df['value'].pct_change().fillna(0)
    
    # --- 1. Equity & Underwater (Combined) ---
    fig = plt.figure(figsize=(10, 8))
    gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1])
    
    # Equity
    ax0 = plt.subplot(gs[0])
    ax0.plot(df.index, df['value'], color=COLORS['primary'], linewidth=1.5)
    ax0.set_title('Equity Curve', color='white', pad=20)
    ax0.grid(True, alpha=0.1)
    ax0.set_facecolor(COLORS['bg_card'])
    
    # Underwater
    running_max = df['value'].cummax()
    drawdown = (df['value'] - running_max) / running_max
    
    ax1 = plt.subplot(gs[1], sharex=ax0)
    ax1.fill_between(df.index, drawdown, 0, color=COLORS['danger'], alpha=0.6)
    ax1.set_title('Underwater Plot (Drawdown)', color='white', pad=10)
    if len(drawdown) > 0:
        ax1.set_ylim(bottom=drawdown.min() * 1.1, top=0)
    ax1.grid(True, alpha=0.1)
    ax1.set_facecolor(COLORS['bg_card'])
    
    fig.patch.set_facecolor(COLORS['bg_dark'])
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    charts['equity_underwater'] = buf.getvalue()
    
    # --- 2. Monthly Heatmap ---
    if len(df) > 30:
        try:
            monthly_ret = df['returns'].resample('ME').apply(lambda x: (1 + x).prod() - 1)
            monthly_ret = monthly_ret.to_frame(name='returns')
            monthly_ret['Year'] = monthly_ret.index.year
            monthly_ret['Month'] = monthly_ret.index.month
            
            pivot = monthly_ret.pivot(index='Year', columns='Month', values='returns')
            
            fig2, ax2 = plt.subplots(figsize=(10, len(pivot)*0.8 + 2))
            sns.heatmap(pivot, annot=True, fmt='.1%', cmap='RdYlGn', center=0, cbar=False, ax=ax2,
                        annot_kws={'size': 9})
            ax2.set_title('Monthly Returns', color='white', pad=20)
            ax2.set_facecolor(COLORS['bg_card'])
            fig2.patch.set_facecolor(COLORS['bg_dark'])
            
            month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            ax2.set_xticklabels([month_labels[i-1] for i in pivot.columns])
            plt.tight_layout()
            
            buf2 = io.BytesIO()
            plt.savefig(buf2, format='png', facecolor=fig2.get_facecolor())
            plt.close(fig2)
            buf2.seek(0)
            charts['heatmap'] = buf2.getvalue()
        except Exception as e:
            logger.warning(f"Heatmap generation failed: {e}")

    return charts


def generate_pdf_report(metrics: Dict[str, Any], equity_curve: List[Dict], trades: List[Dict]) -> bytes:
    """
    Generate comprehensive PDF tearsheet.
    
    Args:
        metrics: Dictionary of backtest performance metrics
        equity_curve: List of {'time': str, 'value': float}
        trades: List of trade dictionaries
    
    Returns:
        PDF document as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, 
                                  textColor=colors.HexColor(COLORS['primary']), alignment=TA_CENTER, spaceAfter=20)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=16, 
                               textColor=colors.HexColor(COLORS['text']), spaceBefore=15, spaceAfter=10)
    norm_style = ParagraphStyle('Norm', parent=styles['Normal'], fontSize=10, 
                                 textColor=colors.HexColor(COLORS['text_muted']))

    story = []
    
    # --- Title Page ---
    story.append(Paragraph("AlphaVerify Backtest Tearsheet", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", norm_style))
    story.append(Spacer(1, 0.5*inch))
    
    # Advanced Metrics
    adv_metrics = calculate_advanced_metrics(equity_curve, trades)
    
    # Combined Metrics Table
    total_return = metrics.get('total_return', 0)
    sharpe = metrics.get('sharpe_ratio', 0)
    max_dd = metrics.get('max_drawdown', 0)
    win_rate = metrics.get('win_rate', 0)
    
    data = [
        ["Metric", "Value", "Metric", "Value"],
        ["Total Return", f"{total_return:+.2f}%", "Sharpe Ratio", f"{sharpe:.2f}"],
        ["Max Drawdown", f"{max_dd:.2f}%", "Sortino Ratio", f"{adv_metrics.get('Sortino Ratio', 0):.2f}"],
        ["Ann. Volatility", f"{adv_metrics.get('Annual Volatility', 0)*100:.2f}%", "Calmar Ratio", f"{adv_metrics.get('Calmar Ratio', 0):.2f}"],
        ["Win Rate", f"{win_rate:.1f}%", "Kelly Criterion", f"{adv_metrics.get('Kelly Criterion', 0):.2f}"],
        ["Total Trades", str(metrics.get('total_trades', 0)), "Profit Factor", f"{metrics.get('profit_factor', 0):.2f}"],
    ]
    
    t = Table(data, colWidths=[2*inch, 1.5*inch, 2*inch, 1.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLORS['bg_card'])),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(COLORS['text'])),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#475569')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4*inch))
    
    # --- Charts ---
    charts = generate_tearsheet_charts(equity_curve)
    
    if 'equity_underwater' in charts:
        img = Image(io.BytesIO(charts['equity_underwater']), width=7*inch, height=5.5*inch)
        story.append(img)
        story.append(Spacer(1, 0.2*inch))
    
    if 'heatmap' in charts:
        story.append(PageBreak())
        story.append(Paragraph("Monthly Returns Heatmap", h2_style))
        img2 = Image(io.BytesIO(charts['heatmap']), width=7*inch, height=5*inch)
        story.append(img2)
        
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
