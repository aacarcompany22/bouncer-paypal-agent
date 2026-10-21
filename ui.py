
import math
import plotly.graph_objects as go

STATUS_COLORS = {
    "ACTIVE": "#2ecc71",
    "APPROVAL_PENDING": "#f5a623",
    "SUSPENDED": "#4da3ff",
    "CANCELLED": "#7a7f8c",
}

BOUNCER_TEMPLATE = """
<style>
  body { margin:0; background:transparent; font-family:sans-serif; }
  .wrap { display:flex; align-items:center; gap:24px; }
  .bubble { border:2px solid __COLOR__; color:#fff; padding:14px 20px; border-radius:14px;
            font-size:18px; max-width:420px; background:#141a2b; }
  .sway { animation: sway 2.5s ease-in-out infinite; transform-origin: 100px 200px; }
  @keyframes sway { 0%,100%{transform:rotate(-1.5deg);} 50%{transform:rotate(1.5deg);} }
  .glint { animation: glint 3s linear infinite; }
  @keyframes glint { 0%,70%{opacity:0;} 80%{opacity:.9;} 100%{opacity:0;} }
  .stop { display:__STOP__; transform-origin: 150px 140px; animation: wave .5s ease-in-out infinite alternate; }
  @keyframes wave { from{transform:rotate(-8deg);} to{transform:rotate(8deg);} }
  .arms { display:__ARMS__; }
  .pulse { animation: pulse 1s ease-in-out infinite; }
  @keyframes pulse { 50%{ box-shadow:0 0 18px __COLOR__; } }
</style>
<div class="wrap">
  <svg width="220" height="240" viewBox="0 0 220 240">
    <ellipse cx="100" cy="226" rx="70" ry="8" fill="#000" opacity=".4"/>
    <!-- velvet rope -->
    <rect x="178" y="130" width="6" height="96" fill="#d4af37"/><circle cx="181" cy="128" r="8" fill="#d4af37"/>
    <path d="M181 135 Q 205 170 215 135" stroke="#c0392b" stroke-width="5" fill="none"/>
    <g class="sway">
      <rect x="52" y="92" width="96" height="116" rx="16" fill="#111"/>
      <polygon points="100,92 82,92 100,140 118,92" fill="#f2f2f2"/>
      <polygon points="100,100 94,112 100,150 106,112" fill="#c0392b"/>
      <circle cx="100" cy="64" r="28" fill="#e0ac8a"/>
      <rect x="70" y="56" width="60" height="15" rx="6" fill="#000"/>
      <rect x="76" y="58" width="14" height="3" fill="#fff" class="glint"/>
      <path d="M88 82 Q100 88 112 82" stroke="#7a4a32" stroke-width="3" fill="none"/>
      <g class="arms">
        <rect x="40" y="118" width="120" height="28" rx="14" fill="#1c1c1c"/>
        <rect x="40" y="130" width="120" height="3" fill="#333"/>
      </g>
      <g class="stop">
        <rect x="140" y="80" width="18" height="70" rx="9" fill="#1c1c1c"/>
        <rect x="136" y="56" width="26" height="30" rx="10" fill="#e0ac8a"/>
      </g>
    </g>
  </svg>
  <div class="bubble pulse">__MSG__</div>
</div>
"""


def bouncer_html(message, alert=False):
    html = BOUNCER_TEMPLATE
    html = html.replace("__MSG__", message)
    html = html.replace("__COLOR__", "#ff4b4b" if alert else "#2ecc71")
    html = html.replace("__STOP__", "block" if alert else "none")
    html = html.replace("__ARMS__", "none" if alert else "block")
    return html


def subscription_map(subs):
    fig = go.Figure()
    n = max(len(subs), 1)
    xs, ys, sizes, colors, labels, hover = [], [], [], [], [], []
    for i, s in enumerate(subs):
        a = 2 * math.pi * i / n
        x, y = math.cos(a), math.sin(a)
        fig.add_trace(go.Scatter(x=[0, x], y=[0, y], mode="lines",
                                 line=dict(color="#3a4260", width=2),
                                 hoverinfo="skip", showlegend=False))
        xs.append(x); ys.append(y)
        sizes.append(35 + s["price"] * 2.5)
        colors.append(STATUS_COLORS.get(s["status"], "#7a7f8c"))
        labels.append(s["service"])
        hover.append(f"{s['service']}<br>${s['price']:.2f}/mo<br>{s['status']}")
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text", text=labels,
                             textposition="bottom center", hovertext=hover, hoverinfo="text",
                             marker=dict(size=sizes, color=colors,
                                         line=dict(color="#fff", width=2)),
                             showlegend=False))
    fig.add_trace(go.Scatter(x=[0], y=[0], mode="markers+text", text=["YOU"],
                             textposition="middle center",
                             marker=dict(size=60, color="#003087", line=dict(color="#009cde", width=3)),
                             hoverinfo="skip", showlegend=False))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10),
                      title="Your subscription map",
                      xaxis=dict(visible=False, range=[-1.5, 1.5]),
                      yaxis=dict(visible=False, range=[-1.5, 1.5]),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def spend_donut(subs):
    live = [s for s in subs if s["status"] in ("ACTIVE", "APPROVED")]
    fig = go.Figure(go.Pie(labels=[s["service"] for s in live],
                           values=[s["price"] for s in live], hole=0.55))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10),
                      title="Monthly spend once trials end",
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig