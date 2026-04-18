"""Generate an executive competitive intelligence report."""

from __future__ import annotations

from html import escape
from pathlib import Path

from src.analytics.competitive import CompetitiveRecord, generate_summary, load_competitive_data


REPORT_PATH = Path("reports/competitive_intelligence_report.html")


def _bar_chart(title: str, rows: list[dict], value_key: str, label_key: str = "platform") -> str:
    max_value = max(row[value_key] for row in rows) if rows else 1
    bars = []
    for row in rows:
        width = 0 if max_value == 0 else int((row[value_key] / max_value) * 100)
        bars.append(
            f"""
            <div class="bar-row">
              <span class="bar-label">{escape(str(row[label_key]))}</span>
              <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
              <span class="bar-value">{row[value_key]}</span>
            </div>
            """
        )
    return f"""
    <section>
      <h2>{escape(title)}</h2>
      <div class="chart">{''.join(bars)}</div>
    </section>
    """


def _zone_table(rows: list[dict]) -> str:
    body = []
    for row in rows:
        body.append(
            f"""
            <tr>
              <td>{escape(row['zone_type'])}</td>
              <td>{escape(row['platform'])}</td>
              <td>{row['avg_total_cost']}</td>
              <td>{row['avg_delivery_fee']}</td>
              <td>{row['avg_eta_min']}</td>
            </tr>
            """
        )
    return f"""
    <section>
      <h2>Geographic Variability</h2>
      <table>
        <thead>
          <tr>
            <th>Zone</th>
            <th>Platform</th>
            <th>Avg Total Cost</th>
            <th>Delivery Fee</th>
            <th>ETA Min</th>
          </tr>
        </thead>
        <tbody>{''.join(body)}</tbody>
      </table>
    </section>
    """


def _insights_html(insights: list[dict]) -> str:
    items = []
    for index, insight in enumerate(insights, start=1):
        items.append(
            f"""
            <article class="insight">
              <h3>{index}. {escape(insight['category'].replace('_', ' ').title())}</h3>
              <p><strong>Finding:</strong> {escape(insight['finding'])}</p>
              <p><strong>Impact:</strong> {escape(insight['impact'])}</p>
              <p><strong>Recommendation:</strong> {escape(insight['recommendation'])}</p>
            </article>
            """
        )
    return f"<section><h2>Top 5 Actionable Insights</h2>{''.join(items)}</section>"


def build_report_html(records: list[CompetitiveRecord]) -> str:
    """Build the report HTML string from competitive records."""
    summary = generate_summary(records)
    platform_rows = summary["platform_averages"]
    zone_rows = summary["zones"]
    promo_rows = [
        {
            "platform": row["platform"],
            "promo_count": row["count"],
        }
        for row in summary["promos"]
        if row["promo"] != "no visible promo"
    ][:6]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Rappi Competitive Intelligence Report</title>
  <style>
    body {{
      color: #202124;
      font-family: Arial, sans-serif;
      line-height: 1.45;
      margin: 0;
      background: #f7f8fa;
    }}
    header, section {{
      background: #fff;
      border: 1px solid #d8dde6;
      margin: 18px auto;
      max-width: 1040px;
      padding: 24px;
    }}
    h1, h2, h3 {{
      margin-top: 0;
    }}
    .kpis {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(4, 1fr);
    }}
    .kpi {{
      border: 1px solid #d8dde6;
      padding: 14px;
    }}
    .kpi strong {{
      display: block;
      font-size: 26px;
    }}
    .bar-row {{
      align-items: center;
      display: grid;
      gap: 12px;
      grid-template-columns: 120px 1fr 80px;
      margin: 10px 0;
    }}
    .bar-track {{
      background: #eef1f4;
      height: 22px;
    }}
    .bar-fill {{
      background: #18a058;
      height: 22px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
    }}
    th, td {{
      border-bottom: 1px solid #d8dde6;
      padding: 10px;
      text-align: left;
    }}
    .insight {{
      border-left: 4px solid #18a058;
      margin: 14px 0;
      padding-left: 14px;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Rappi Competitive Intelligence Report</h1>
    <p>Backup snapshot for the technical demo. The dataset covers Rappi, Uber Eats, and DiDi Food across representative CDMX zones.</p>
    <div class="kpis">
      <div class="kpi"><span>Records</span><strong>{summary['records']}</strong></div>
      <div class="kpi"><span>Addresses</span><strong>{summary['addresses']}</strong></div>
      <div class="kpi"><span>Platforms</span><strong>{len(summary['platforms'])}</strong></div>
      <div class="kpi"><span>Products</span><strong>{len(summary['products'])}</strong></div>
    </div>
  </header>
  {_insights_html(summary['top_insights'])}
  {_bar_chart('Average Total Cost by Platform', platform_rows, 'avg_total_cost')}
  {_bar_chart('Average ETA by Platform', platform_rows, 'avg_eta_min')}
  {_bar_chart('Average Delivery Fee by Platform', platform_rows, 'avg_delivery_fee')}
  {_bar_chart('Visible Promotion Count', promo_rows, 'promo_count')}
  {_zone_table(zone_rows)}
</body>
</html>
"""


def write_report(
    records: list[CompetitiveRecord] | None = None,
    output_path: str | Path = REPORT_PATH,
) -> Path:
    """Write the competitive intelligence report to disk."""
    source = records if records is not None else load_competitive_data()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report_html(source), encoding="utf-8")
    return path
