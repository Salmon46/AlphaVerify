
import io
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime

def generate_sensitivity_pdf(results_df: pd.DataFrame, config: dict):
    """
    Generates a comprehensive PDF report for sensitivity analysis.
    
    Args:
        results_df: DataFrame containing 'sharpe', 'total_return', and parameter columns.
        config: Dictionary containing 'mode', 'iterations', 'total_runs', etc.
    
    Returns:
        BytesIO object containing the PDF data.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # --- Title Page ---
    title_style = styles['Title']
    story.append(Paragraph("Sensitivity Analysis Report", title_style))
    story.append(Spacer(1, 0.2 * inch))
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph(f"Generated on: {timestamp}", styles['Normal']))
    story.append(Spacer(1, 0.5 * inch))

    # --- 1. Introduction & Methodology ---
    header_style = ParagraphStyle('Header2', parent=styles['Heading2'], spaceAfter=10)
    story.append(Paragraph("1. Introduction & Methodology", header_style))
    
    intro_text = f"""
    This report presents the results of a parameter sensitivity analysis performed using the <b>AlphaVerify Sensitivity Engine</b>.
    The objective is to evaluate the robustness of the trading strategy and identify key drivers of performance.
    <br/><br/>
    <b>Methodology:</b> {config.get('mode', 'Grid').title()} Search
    <br/>
    <b>Distribution:</b> {config.get('distribution', 'N/A').title()}
    <br/>
    <b>Total Simulations:</b> {len(results_df)}
    """
    story.append(Paragraph(intro_text, styles['Normal']))
    story.append(Spacer(1, 0.5 * inch))

    # --- 2. Key Results Summary ---
    story.append(Paragraph("2. Performance Summary", header_style))
    
    best_row = results_df.iloc[results_df['sharpe'].argmax()]
    
    summary_data = [
        ["Metric", "Value"],
        ["Max Sharpe Ratio", f"{best_row['sharpe']:.4f}"],
        ["Max Return", f"{best_row['total_return']*100:.2f}%"],
        ["Average Sharpe", f"{results_df['sharpe'].mean():.4f}"],
        ["Sharpe Std Dev", f"{results_df['sharpe'].std():.4f}"],
    ]
    
    t = Table(summary_data, colWidths=[2.5*inch, 2.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph("<b>Best Parameter Configuration:</b>", styles['Normal']))
    param_cols = [c for c in results_df.columns if c not in ['sharpe', 'total_return']]
    
    best_params_text = ", ".join([f"{p}={best_row[p]}" for p in param_cols])
    story.append(Paragraph(best_params_text, styles['Normal']))
    story.append(PageBreak())

    # --- 3. Parameter Ranking (Tornado Chart) ---
    story.append(Paragraph("3. Parameter Impact (Sensitivity Ranking)", header_style))
    story.append(Paragraph("The Tornado Chart below ranks parameters by their correlation with the Sharpe Ratio. "
                           "Longer bars indicate a stronger influence on performance. "
                           "Positive values indicate that increasing the parameter improves performance, "
                           "while negative values suggest the opposite.", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))

    # Calculate Correlations
    correlations = {}
    for col in param_cols:
        # Handle non-numeric params if any (skip them)
        if pd.api.types.is_numeric_dtype(results_df[col]):
            corr = results_df[col].corr(results_df['sharpe'])
            if not np.isnan(corr):
                correlations[col] = corr
    
    # Sort by absolute impact
    sorted_corrs = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
    top_params = [x[0] for x in sorted_corrs[:5]] # Keep top 5 for scatter plots later

    # Plot Tornado
    if sorted_corrs:
        keys = [x[0] for x in sorted_corrs][::-1]
        values = [x[1] for x in sorted_corrs][::-1]
        
        plt.figure(figsize=(7, 4))
        colors_list = ['green' if x > 0 else 'red' for x in values]
        plt.barh(keys, values, color=colors_list)
        plt.title('Parameter Correlation with Sharpe Ratio')
        plt.xlabel('Pearson Correlation Coefficient')
        plt.grid(axis='x', linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=100)
        img_buffer.seek(0)
        plt.close()
        
        img = Image(img_buffer, width=6*inch, height=3.5*inch)
        story.append(img)
    else:
        story.append(Paragraph("Not enough numeric variation to generate correlations.", styles['Normal']))
        
    story.append(PageBreak())

    # --- 4. Visualizations (Scatter Plots) ---
    story.append(Paragraph("4. Key Relationships (Scatter Plots)", header_style))
    story.append(Paragraph("Visualizing the relationship between the most influential parameters and the Sharpe Ratio.", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))

    # Plot Top 3 Params vs Sharpe
    for param in top_params[:3]:
        plt.figure(figsize=(6, 3))
        plt.scatter(results_df[param], results_df['sharpe'], alpha=0.5, c=results_df['sharpe'], cmap='viridis')
        plt.colorbar(label='Sharpe Ratio')
        plt.title(f"{param} vs Sharpe Ratio")
        plt.xlabel(param)
        plt.ylabel("Sharpe Ratio")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=100)
        img_buffer.seek(0)
        plt.close()
        
        story.append(Image(img_buffer, width=5.5*inch, height=3*inch))
        story.append(Spacer(1, 0.2*inch))

    story.append(PageBreak())
    
    # --- 5. Distribution Analysis ---
    story.append(Paragraph("5. Outcome Distribution", header_style))
    story.append(Paragraph("Histogram of Sharpe Ratios across all simulations.", styles['Normal']))
    
    plt.figure(figsize=(7, 4))
    plt.hist(results_df['sharpe'], bins=30, color='skyblue', edgecolor='black', alpha=0.7)
    plt.axvline(results_df['sharpe'].mean(), color='red', linestyle='dashed', linewidth=1, label=f"Mean: {results_df['sharpe'].mean():.2f}")
    plt.title('Distribution of Sharpe Ratios')
    plt.xlabel('Sharpe Ratio')
    plt.ylabel('Frequency')
    plt.legend()
    plt.grid(axis='y', alpha=0.5)
    plt.tight_layout()
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=100)
    img_buffer.seek(0)
    plt.close()
    
    story.append(Image(img_buffer, width=6*inch, height=3.5*inch))
    story.append(Spacer(1, 0.5 * inch))

    # --- 6. Conclusion ---
    story.append(Paragraph("6. Conclusion & Recommendations", header_style))
    
    # Dynamic Conclusion
    strongest_param = top_params[0] if top_params else "None"
    conclusion = f"""
    The analysis concludes that <b>{strongest_param}</b> is the most critical driver of performance in this configuration. 
    <br/><br/>
    <b>Recommendation:</b> Focus further optimization efforts on refining <b>{strongest_param}</b> and exploring the interactions with 
    <b>{top_params[1] if len(top_params) > 1 else 'secondary parameters'}</b>. 
    Ensure that the strategy is robust across the observed distribution of outcomes.
    """
    story.append(Paragraph(conclusion, styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer
