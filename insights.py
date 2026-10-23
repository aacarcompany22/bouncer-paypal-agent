
import calendar
import itertools
from datetime import date, datetime, timezone

import plotly.graph_objects as go
from dateutil.relativedelta import relativedelta  # installed with pandas


def upcoming_charges(subs, months=14):
    """Project every ACTIVE subscription's future charges, month by month."""
    out = []
    for s in subs:
        if s["status"] != "ACTIVE" or not s["next_billing_time"]:
            continue
        first = datetime.fromisoformat(s["next_billing_time"].replace("Z", "+00:00"))
        for i in range(months):
            out.append({
                "date": (first + relativedelta(months=i)).date(),
                "service": s["service"],
                "price": s["price"],
            })
    return out


CAL_CSS = """
<style>
  body { margin:0; font-family:sans-serif; color:#fff; background:transparent; }
  .grid { display:grid; grid-template-columns:repeat(7, 1fr); gap:6px; }
  .h { text-align:center; font-size:13px; color:#9aa4bf; padding:4px 0; }
  .c { min-height:78px; background:#141a2b; border:1px solid #232a40;
       border-radius:8px; padding:4px 6px; font-size:12px; }
  .c.empty { background:transparent; border:none; }
  .c .d { color:#9aa4bf; font-size:12px; }
  .c.due { border-color:#ff4b4b; background:#2a1620; }
  .c.today { outline:2px solid #4da3ff; }
  .tag { margin-top:4px; background:#ff4b4b; color:#fff; border-radius:6px;
         padding:2px 5px; font-size:11px; line-height:1.3; }
</style>
"""


def calendar_html(charges, year, month):
    by_day = {}
    for c in charges:
        if c["date"].year == year and c["date"].month == month:
            by_day.setdefault(c["date"].day, []).append(c)

    today = datetime.now(timezone.utc).date()
    header = "".join(
        f"<div class='h'>{d}</div>" for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    )
    cells = ""
    for day in calendar.Calendar(firstweekday=0).itermonthdays(year, month):
        if day == 0:
            cells += "<div class='c empty'></div>"
            continue
        items = by_day.get(day, [])
        cls = "c" + (" due" if items else "") + (" today" if date(year, month, day) == today else "")
        tags = "".join(f"<div class='tag'>{i['service']}<br>${i['price']:.2f}</div>" for i in items)
        cells += f"<div class='{cls}'><span class='d'>{day}</span>{tags}</div>"
    return f"{CAL_CSS}<div class='grid'>{header}{cells}</div>"


def annual_figure(charges, excluded=()):
    """12-month spend chart. Returns (figure, total spend)."""
    start = date.today().replace(day=1)
    labels, monthly = [], []
    for i in range(12):
        m = start + relativedelta(months=i)
        labels.append(m.strftime("%b %y"))
        monthly.append(sum(
            c["price"] for c in charges
            if c["date"].year == m.year and c["date"].month == m.month
            and c["service"] not in excluded
        ))
    cumulative = list(itertools.accumulate(monthly))

    fig = go.Figure()
    fig.add_bar(x=labels, y=monthly, name="Charged that month", marker_color="#4da3ff")
    fig.add_scatter(x=labels, y=cumulative, mode="lines+markers",
                    name="Running total", line=dict(color="#ff4b4b", width=3))
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=90, b=10),
        title=dict(text="Your next 12 months of subscriptions", x=0, y=0.97, yanchor="top"),
        legend=dict(orientation="h", x=0, y=1.0, yanchor="bottom"),
        yaxis=dict(title="US dollars", tickprefix="$"),
        xaxis=dict(tickangle=-45, automargin=True),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig, cumulative[-1]