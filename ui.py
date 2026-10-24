
import math
import plotly.graph_objects as go

import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

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
    html = html.replace("__COLOR__", "#f30909" if alert else "#2ecc71")
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
STATUS_STYLE = JsCode("""
function(params) {
  if (params.value === 'ACTIVE') return {color: '#2ecc71', fontWeight: '600'};
  if (params.value === 'APPROVAL_PENDING') return {color: '#f5a623', fontWeight: '600'};
  if (params.value === 'SUSPENDED') return {color: '#4da3ff', fontWeight: '600'};
  if (params.value === 'CANCELLED') return {color: '#7a7f8c'};
  return null;
}
""")

MONEY_FORMAT = JsCode("""
function(params) {
  if (params.value === null || params.value === undefined) return '';
  return '$' + Number(params.value).toFixed(2);
}
""")


def show_grid(df, key, height=340, status_col=None, money_cols=()):
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(resizable=True, sortable=True, filter=True, flex=1, minWidth=110)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=8)
    if status_col and status_col in df.columns:
        gb.configure_column(status_col, cellStyle=STATUS_STYLE)
    for col in money_cols:
        if col in df.columns:
            gb.configure_column(col, valueFormatter=MONEY_FORMAT)
    AgGrid(
        df,
        gridOptions=gb.build(),
        height=height,
        theme="streamlit",
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=True,
        key=key,
    )
SCENE_TEMPLATE = """
<style>
  body { margin:0; background:transparent; font-family:sans-serif; }
  svg { display:block; }
  .wrap { display:flex; align-items:center; gap:24px; flex-wrap:wrap; }
  .bubble { border:2px solid __COLOR__; color:#fff; padding:14px 20px; border-radius:14px;
            font-size:18px; max-width:420px; background:#141a2b;
            animation: pulse 1.2s ease-in-out infinite; }
  @keyframes pulse { 50% { box-shadow:0 0 18px __COLOR__; } }
  .mv { animation: patrol __SPEED__ ease-in-out infinite alternate; }
  .mv.r { animation-delay: __DELAY__; }
  @keyframes patrol { from { transform: translateX(-14px); } to { transform: translateX(14px); } }
  .bob { animation: bob .7s ease-in-out infinite alternate; }
  @keyframes bob { from { transform: translateY(0); } to { transform: translateY(-2px); } }
  .glint { animation: glint 3s linear infinite; }
  @keyframes glint { 0%,70% { opacity:0; } 80% { opacity:.9; } 100% { opacity:0; } }
  .bang { display:__BANG__; }
  .doorlight { animation: blink 1s steps(2) infinite; }
  @keyframes blink { 50% { opacity:.25; } }
  @media (prefers-reduced-motion: reduce) {
    .mv, .bob, .glint, .doorlight, .bubble { animation:none; }
  }
</style>
<div class="wrap">
  <svg width="440" height="250" viewBox="0 0 440 250" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <g id="guy">
        <rect x="24" y="150" width="21" height="46" fill="#0e1015"/>
        <rect x="55" y="150" width="21" height="46" fill="#0e1015"/>
        <rect x="20" y="192" width="28" height="8" rx="4" fill="#000"/>
        <rect x="52" y="192" width="28" height="8" rx="4" fill="#000"/>
        <path d="M8 72 Q8 52 30 47 L70 47 Q92 52 92 72 L92 156 L8 156 Z" fill="#14161c"/>
        <polygon points="38,47 62,47 50,86" fill="#f2f2f2"/>
        <polygon points="50,54 46,64 50,98 54,64" fill="#c0392b"/>
        <rect x="10" y="86" width="80" height="24" rx="12" fill="#1f232d"/>
        <rect x="10" y="97" width="80" height="2" fill="#333a49"/>
        <rect x="42" y="38" width="16" height="12" fill="#d49a78"/>
        <circle cx="50" cy="26" r="20" fill="#e0ac8a"/>
        <rect x="29" y="19" width="42" height="11" rx="5" fill="#000"/>
        <rect x="33" y="21" width="10" height="3" fill="#fff" class="glint"/>
        <path d="M41 38 Q50 43 59 38" stroke="#7a4a32" stroke-width="3" fill="none" stroke-linecap="round"/>
      </g>
    </defs>

    <ellipse cx="220" cy="241" rx="205" ry="6" fill="#000" opacity=".35"/>

    <rect x="178" y="30" width="84" height="118" rx="4" fill="#1b2036" stroke="#d4af37" stroke-width="3"/>
    <rect x="194" y="42" width="52" height="20" rx="4" fill="#d4af37"/>
    <text x="220" y="57" text-anchor="middle" font-size="14" font-weight="700" fill="#1b2036" font-family="sans-serif">VIP</text>
    <circle class="doorlight" cx="220" cy="20" r="5" fill="__COLOR__"/>
    <polygon points="196,148 244,148 300,238 140,238" fill="#33447a"/>

    <g transform="translate(40,38)">
      <g class="mv"><g class="bob">
        <use href="#guy"/>
        <g class="bang">
          <circle cx="50" cy="-6" r="11" fill="#ff4b4b"/>
          <text x="50" y="-1" text-anchor="middle" font-size="15" font-weight="700" fill="#fff" font-family="sans-serif">!</text>
        </g>
      </g></g>
    </g>

    <g transform="translate(300,38)">
      <g class="mv r"><g class="bob">
        <use href="#guy"/>
        <g class="bang">
          <circle cx="50" cy="-6" r="11" fill="#ff4b4b"/>
          <text x="50" y="-1" text-anchor="middle" font-size="15" font-weight="700" fill="#fff" font-family="sans-serif">!</text>
        </g>
      </g></g>
    </g>

    <rect x="168" y="152" width="6" height="82" fill="#d4af37"/>
    <circle cx="171" cy="150" r="7" fill="#d4af37"/>
    <rect x="266" y="152" width="6" height="82" fill="#d4af37"/>
    <circle cx="269" cy="150" r="7" fill="#d4af37"/>
    <path d="M171 154 Q220 204 269 154" stroke="#c0392b" stroke-width="5" fill="none"/>
  </svg>
  <div class="bubble">__MSG__</div>
</div>
"""


def bouncer_html(message, alert=False):
    html = SCENE_3D
    html = html.replace("__MSG__", message)
    html = html.replace("__COLOR__", "#ff4b4b" if alert else "#2ecc71")
    html = html.replace("__SPEED__", "1.1s" if alert else "3s")
    html = html.replace("__DELAY__", "-1.1s" if alert else "-3s")
    html = html.replace("__BANG__", "block" if alert else "none")
    return html

RING_COLORS = ["#ffbb00", "#ff0a78", "#8b3dff", "#2ec4ff"]

RINGS_TEMPLATE = """
<style>
  body { margin:0; font-family:'Segoe UI', system-ui, sans-serif; background:transparent; color:#fff; }
  .card { background:#141a2b; border:1px solid #232a40; border-radius:18px; padding:22px 26px; }
  h3 { margin:0; font-size:18px; font-weight:700; }
  .sub { margin:4px 0 0; font-size:12px; color:#8f9ab8; }
  .body { display:flex; align-items:center; justify-content:space-between;
         gap:18px; flex-wrap:nowrap; margin-top:10px; }
  .stats { display:flex; flex-direction:column; gap:18px; flex:0 0 auto; min-width:130px; }
  .big { font-size:30px; font-weight:700; letter-spacing:-0.5px; }
  .of { font-size:15px; color:#8f9ab8; margin-left:2px; }
  .lbl { display:flex; align-items:center; gap:7px; font-size:12px; color:#8f9ab8; margin-top:2px; }
  .dot { width:9px; height:9px; border-radius:50%; display:inline-block; }
  svg { display:block; }
  .track { fill:none; stroke:#232a40; stroke-width:18; }
  .arc { fill:none; stroke-width:18; stroke-linecap:round;
         stroke-dasharray:0 var(--circ);
         animation: draw 1.3s cubic-bezier(.2,.8,.2,1) forwards; }
  @keyframes draw { to { stroke-dasharray: var(--len) var(--circ); } }
  @media (prefers-reduced-motion: reduce) {
    .arc { animation:none; stroke-dasharray: var(--len) var(--circ); }
  }
</style>
<div class="card">
  <h3>Monthly spend</h3>
  <p class="sub">__SUBTITLE__</p>
  <div class="body">
    <div class="stats">__STATS__</div>
    <svg width="250" height="250" viewBox="0 0 260 260">__RINGS__</svg>
  </div>
</div>
"""


def spend_rings_html(subs, budget=50.0):
    totals = {}
    for s in subs:
        if s["status"] in ("ACTIVE", "APPROVED"):
            totals[s["service"]] = totals.get(s["service"], 0) + s["price"]
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    shown, hidden = ranked[:4], ranked[4:]
    total = sum(totals.values())
    budget = max(float(budget), 1.0)

    rings, stats = "", ""
    for i, (name, price) in enumerate(shown):
        r = 112 - i * 26
        circ = 2 * math.pi * r
        pct = min(price / budget, 1.0)
        color = RING_COLORS[i]
        rings += (
            f'<circle class="track" cx="130" cy="130" r="{r}"/>'
            f'<circle class="arc" cx="130" cy="130" r="{r}" stroke="{color}" '
            f'transform="rotate(-90 130 130)" '
            f'style="--len:{pct * circ:.1f};--circ:{circ:.1f};animation-delay:{i * 0.15:.2f}s">'
            f'<title>{name}: ${price:.2f}/month</title></circle>'
        )
        stats += (
            f'<div><span class="big">${price:.2f}</span>'
            f'<span class="of">/${budget:.0f}</span>'
            f'<div class="lbl"><span class="dot" style="background:{color}"></span>{name}</div></div>'
        )

    if not shown:
        for i in range(3):
            rings += f'<circle class="track" cx="130" cy="130" r="{112 - i * 26}"/>'
        stats = '<div class="lbl">Activate a subscription to fill the rings.</div>'

    over = total > budget
    subtitle = (
        f'Once trials end &middot; <span style="color:{"#ff4b4b" if over else "#8f9ab8"}">'
        f'${total:.2f} of ${budget:.0f} budget</span>'
    )
    if hidden:
        subtitle += f" &middot; +{len(hidden)} more not shown"

    html = RINGS_TEMPLATE
    html = html.replace("__SUBTITLE__", subtitle)
    html = html.replace("__STATS__", stats)
    html = html.replace("__RINGS__", rings)
    return html
  
SCENE_3D = """
<style>
  body { margin:0; background:transparent; font-family:sans-serif; }
  svg { display:block; }
  .wrap { display:flex; align-items:center; gap:24px; flex-wrap:wrap; }
  .bubble { border:2px solid __COLOR__; color:#fff; padding:14px 20px; border-radius:14px;
            font-size:18px; max-width:420px; background:#141a2b;
            animation: pulse 1.2s ease-in-out infinite; }
  @keyframes pulse { 50% { box-shadow:0 0 18px __COLOR__; } }
  .mv { animation: patrol __SPEED__ ease-in-out infinite alternate; }
  .mv.r { animation-delay: __DELAY__; }
  @keyframes patrol { from { transform: translateX(-14px); } to { transform: translateX(14px); } }
  .bob { animation: bob .7s ease-in-out infinite alternate; }
  @keyframes bob { from { transform: translateY(0); } to { transform: translateY(-2px); } }
  .breath { transform-box: fill-box; transform-origin: 50% 100%;
            animation: breathe 3.2s ease-in-out infinite alternate; }
  @keyframes breathe { from { transform: scaleY(1); } to { transform: scaleY(1.018); } }
  .scan { transform-box: fill-box; transform-origin: 50% 90%;
          animation: scan 5s ease-in-out infinite alternate; }
  @keyframes scan { from { transform: rotate(-4deg); } to { transform: rotate(4deg); } }
  .glint { animation: glint 3s linear infinite; }
  @keyframes glint { 0%,70% { opacity:0; } 80% { opacity:.6; } 100% { opacity:0; } }
  .led, .doorlight { animation: blink 1.1s steps(2) infinite; }
  @keyframes blink { 50% { opacity:.2; } }
  .bang { display:__BANG__; }
  @media (prefers-reduced-motion: reduce) {
    .mv, .bob, .breath, .scan, .glint, .led, .doorlight, .bubble { animation:none; }
  }
</style>
<div class="wrap">
  <svg width="440" height="250" viewBox="0 0 440 250" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="suit" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#2b3040"/><stop offset=".45" stop-color="#171a24"/><stop offset="1" stop-color="#0a0c12"/>
      </linearGradient>
      <linearGradient id="sleeve" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#2f3545"/><stop offset="1" stop-color="#0f1219"/>
      </linearGradient>
      <linearGradient id="shirt" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#cdd3e2"/>
      </linearGradient>
      <linearGradient id="tie" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#e0483a"/><stop offset=".5" stop-color="#b3261e"/><stop offset="1" stop-color="#7d1712"/>
      </linearGradient>
      <radialGradient id="skin" cx=".35" cy=".3" r=".85">
        <stop offset="0" stop-color="#f7cba9"/><stop offset=".6" stop-color="#e0a27c"/><stop offset="1" stop-color="#b9774f"/>
      </radialGradient>
      <linearGradient id="lens" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#3b4359"/><stop offset=".5" stop-color="#05060a"/><stop offset="1" stop-color="#000"/>
      </linearGradient>
      <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#fff0a6"/><stop offset=".5" stop-color="#d4af37"/><stop offset="1" stop-color="#8a6a12"/>
      </linearGradient>
      <linearGradient id="shoe" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#2b2f3a"/><stop offset="1" stop-color="#000"/>
      </linearGradient>
      <linearGradient id="door" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#27325e"/><stop offset="1" stop-color="#121731"/>
      </linearGradient>
      <linearGradient id="carpet" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#4a5fb0"/><stop offset="1" stop-color="#26356f"/>
      </linearGradient>
      <radialGradient id="spot" cx=".5" cy=".5" r=".5">
        <stop offset="0" stop-color="__COLOR__" stop-opacity=".35"/><stop offset="1" stop-color="__COLOR__" stop-opacity="0"/>
      </radialGradient>
      <filter id="soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3"/></filter>

      <g id="guy">
        <ellipse cx="50" cy="200" rx="36" ry="5" fill="#000" opacity=".55" filter="url(#soft)"/>
        <rect x="27" y="150" width="21" height="46" rx="3" fill="url(#suit)"/>
        <rect x="52" y="150" width="21" height="46" rx="3" fill="url(#suit)"/>
        <rect x="22" y="190" width="29" height="10" rx="5" fill="url(#shoe)"/>
        <rect x="49" y="190" width="29" height="10" rx="5" fill="url(#shoe)"/>
        <rect x="26" y="192" width="14" height="2" rx="1" fill="#fff" opacity=".35"/>
        <g class="breath">
          <path d="M6 80 Q6 55 30 49 L70 49 Q94 55 94 80 L94 160 Q50 168 6 160 Z" fill="url(#suit)"/>
          <path d="M12 74 Q14 58 30 52" stroke="#fff" stroke-opacity=".22" stroke-width="2" fill="none" stroke-linecap="round"/>
          <polygon points="37,49 63,49 50,94" fill="url(#shirt)"/>
          <path d="M30 49 L38 49 L50 94 L40 104 L22 72 Z" fill="#0f1219" stroke="#fff" stroke-opacity=".1"/>
          <path d="M70 49 L62 49 L50 94 L60 104 L78 72 Z" fill="#0f1219" stroke="#fff" stroke-opacity=".1"/>
          <path d="M46 55 L54 55 L56 64 L50 100 L44 64 Z" fill="url(#tie)"/>
          <rect x="46" y="54" width="8" height="7" rx="2" fill="#c0392b"/>
          <path d="M68 74 l8 -3 l1.5 7 l-9 1 z" fill="#f5c542"/>
          <rect x="8" y="94" width="84" height="26" rx="13" fill="url(#sleeve)"/>
          <rect x="16" y="98" width="68" height="3" rx="1.5" fill="#fff" opacity=".14"/>
          <rect x="13" y="103" width="8" height="11" rx="2" fill="url(#gold)"/>
          <ellipse cx="86" cy="108" rx="9" ry="7.5" fill="url(#skin)"/>
        </g>
        <g class="scan">
          <rect x="43" y="40" width="14" height="12" rx="4" fill="#b9774f"/>
          <ellipse cx="29.5" cy="29" rx="3.6" ry="6" fill="url(#skin)"/>
          <ellipse cx="70.5" cy="29" rx="3.6" ry="6" fill="url(#skin)"/>
          <ellipse cx="50" cy="26" rx="21" ry="23" fill="url(#skin)"/>
          <ellipse cx="41" cy="11" rx="9" ry="4.5" fill="#fff" opacity=".32" filter="url(#soft)"/>
          <rect x="29" y="17" width="19" height="14" rx="6" fill="url(#lens)"/>
          <rect x="52" y="17" width="19" height="14" rx="6" fill="url(#lens)"/>
          <rect x="47" y="21" width="6" height="3" rx="1.5" fill="#05060a"/>
          <path d="M31 19 Q38 17 46 19" stroke="#fff" stroke-opacity=".35" stroke-width="1.5" fill="none"/>
          <polygon class="glint" points="32,18 39,18 33,30 28,30" fill="#fff"/>
          <path d="M48 31 Q50 34 52 31" stroke="#a8643f" stroke-width="2" fill="none" stroke-linecap="round"/>
          <path d="M42 39 Q50 42 58 39" stroke="#7a4a32" stroke-width="2.6" fill="none" stroke-linecap="round"/>
          <path d="M72 30 Q82 42 71 52 Q66 58 68 62" stroke="#15171d" stroke-width="2" fill="none" stroke-dasharray="2 1.6" stroke-linecap="round"/>
          <circle cx="72" cy="30" r="2.2" fill="#15171d"/>
          <circle class="led" cx="72" cy="30" r="1.2" fill="__COLOR__"/>
        </g>
      </g>
    </defs>

    <ellipse cx="220" cy="241" rx="205" ry="6" fill="#000" opacity=".35"/>

    <rect x="178" y="30" width="84" height="118" rx="4" fill="url(#door)" stroke="url(#gold)" stroke-width="3"/>
    <rect x="194" y="42" width="52" height="20" rx="4" fill="url(#gold)"/>
    <text x="220" y="57" text-anchor="middle" font-size="14" font-weight="700" fill="#1b2036" font-family="sans-serif">VIP</text>
    <circle class="doorlight" cx="220" cy="20" r="5" fill="__COLOR__"/>
    <polygon points="196,148 244,148 300,238 140,238" fill="url(#carpet)"/>
    <path d="M196 148 L140 238 M244 148 L300 238" stroke="#d4af37" stroke-opacity=".6" stroke-width="2"/>
    <ellipse cx="220" cy="205" rx="95" ry="30" fill="url(#spot)"/>

    <g transform="translate(40,38)">
      <g class="mv"><g class="bob">
        <use href="#guy"/>
        <g class="bang">
          <circle cx="50" cy="-6" r="11" fill="#ff4b4b"/>
          <text x="50" y="-1" text-anchor="middle" font-size="15" font-weight="700" fill="#fff" font-family="sans-serif">!</text>
        </g>
      </g></g>
    </g>

    <g transform="translate(400,38) scale(-1,1)">
      <g class="mv r"><g class="bob">
        <use href="#guy"/>
        <g class="bang">
          <circle cx="50" cy="-6" r="11" fill="#ff4b4b"/>
          <text x="50" y="-1" text-anchor="middle" font-size="15" font-weight="700" fill="#fff" font-family="sans-serif">!</text>
        </g>
      </g></g>
    </g>

    <rect x="168" y="152" width="6" height="82" fill="url(#gold)"/>
    <circle cx="171" cy="150" r="7" fill="url(#gold)"/>
    <rect x="266" y="152" width="6" height="82" fill="url(#gold)"/>
    <circle cx="269" cy="150" r="7" fill="url(#gold)"/>
    <path d="M171 154 Q220 204 269 154" stroke="#c0392b" stroke-width="5" fill="none"/>
    <path d="M171 152 Q220 202 269 152" stroke="#ff9a8a" stroke-width="1.5" fill="none" opacity=".5"/>
  </svg>
  <div class="bubble">__MSG__</div>
</div>
"""
NODE_PURPLE = "#8b3dff"
SPEND_CYAN = "#2ec4ff"
HUB_ORDER = [
    ("ACTIVE", "Active"),
    ("APPROVAL_PENDING", "Pending"),
    ("SUSPENDED", "Paused"),
    ("CANCELLED", "Cancelled"),
]

MAP_TEMPLATE = """
<style>
  body { margin:0; background:transparent; font-family:'Segoe UI', system-ui, sans-serif; color:#fff; }
  .ttl { font-weight:700; font-size:15px; margin:4px 6px 0; }
  svg { display:block; width:100%; height:auto; max-height:430px; }
  text { paint-order:stroke; stroke:#0e1322; stroke-width:3px; stroke-linejoin:round; }
  text.inner { stroke:none; }
  .legend { display:flex; gap:16px; flex-wrap:wrap; font-size:12px; color:#9aa4bf; margin:2px 8px 4px; }
  .legend i { width:9px; height:9px; border-radius:50%; display:inline-block; margin-right:6px; }
  .edge { fill:none; stroke-dasharray:5 6;
          animation: flow 3s linear infinite, fadein 1s ease both;
          animation-delay: 0s, var(--d,0s); }
  .pop, .pulse, .hv, .ripple { transform-box: fill-box; transform-origin: center; }
  .pop { animation: pop .7s cubic-bezier(.2,.9,.3,1.3) both; animation-delay: var(--d,0s); }
  .pulse { animation: pulse 3.2s ease-in-out infinite; animation-delay: var(--p,0s); }
  .hv { transition: transform .2s ease; cursor: pointer; }
  .node:hover .hv { transform: scale(1.18); }
  .ripple { animation: ripple 3.2s ease-out infinite; }
  .lbl { animation: fadein .8s ease both; animation-delay: var(--d,0s); }
  .twinkle { animation: tw 2.6s ease-in-out infinite alternate; animation-delay: var(--d,0s); }
  @keyframes flow { to { stroke-dashoffset:-44; } }
  @keyframes fadein { from { opacity:0; } to { opacity:1; } }
  @keyframes pop { from { opacity:0; transform:scale(.2); } to { opacity:1; transform:scale(1); } }
  @keyframes pulse { 50% { transform:scale(1.07); } }
  @keyframes ripple { from { opacity:.7; transform:scale(1); } to { opacity:0; transform:scale(1.9); } }
  @keyframes tw { from { opacity:.45; } to { opacity:1; } }
  @media (prefers-reduced-motion: reduce) {
    .edge, .pop, .pulse, .ripple, .lbl, .twinkle { animation:none; }
  }
</style>
<div class="ttl">Your subscription map</div>
__SVG__
<div class="legend">__LEGEND__</div>
"""


def _days_left(ts):
    from datetime import datetime, timezone

    if not ts:
        return None
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (dt - datetime.now(timezone.utc)).days


def subscription_map_html(subs, budget=50.0):
    from html import escape

    cx, cy = 400, 300
    budget = max(float(budget), 1.0)
    groups = {"ACTIVE": [], "APPROVAL_PENDING": [], "SUSPENDED": [], "CANCELLED": []}
    for s in subs:
        key = "ACTIVE" if s["status"] == "APPROVED" else s["status"]
        if key in groups:
            groups[key].append(s)
    total = sum(s["price"] for s in subs if s["status"] in ("ACTIVE", "APPROVED"))

    hubs = [(k, name, STATUS_COLORS[k], groups[k]) for k, name in HUB_ORDER if groups[k]]
    hubs.append(("SPEND", "Spend", SPEND_CYAN, []))
    n = len(hubs)
    edges, nodes = [], []

    def edge(x1, y1, x2, y2, color, op, w, delay):
        edges.append(
            f'<line class="edge" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-opacity="{op}" stroke-width="{w}" style="--d:{delay:.2f}s"/>'
        )

    def bubble(x, y, r, color, delay, tip, inner="", size=14, pulse=False, ink="#0b0f19"):
        pl = ' class="pulse"' if pulse else ""
        txt = ""
        if inner:
            txt = (f'<text class="inner" text-anchor="middle" dy="{size * 0.35:.1f}" '
                   f'font-size="{size}" font-weight="800" fill="{ink}">{inner}</text>')
        return (
            f'<g transform="translate({x:.1f},{y:.1f})" class="node"><title>{tip}</title>'
            f'<g class="pop" style="--d:{delay:.2f}s"><g class="hv"><g{pl} style="--p:{delay * 3:.2f}s">'
            f'<circle r="{r}" fill="{color}" fill-opacity=".92" stroke="#ffffff" '
            f'stroke-opacity=".55" stroke-width="2" filter="url(#glow)"/>'
            f'<ellipse cx="{-r * 0.3:.1f}" cy="{-r * 0.38:.1f}" rx="{r * 0.45:.1f}" '
            f'ry="{r * 0.26:.1f}" fill="#fff" fill-opacity=".28"/>'
            f'</g>{txt}</g></g></g>'
        )

    def label(x, y, text, size=11, weight=600, color="#ffffff", anchor="middle", delay=0.0):
        nodes.append(
            f'<text class="lbl" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}" style="--d:{delay:.2f}s">{escape(text)}</text>'
        )

    hub_pos = []
    for i in range(n):
        a = math.radians(-90 + i * 360 / n)
        hub_pos.append((a, cx + 125 * math.cos(a), cy + 125 * math.sin(a)))
    if n >= 3:
        for i in range(n):
            j = (i + 1) % n
            edge(hub_pos[i][1], hub_pos[i][2], hub_pos[j][1], hub_pos[j][2], "#6b76a0", .25, 1, .4)

    t = 0.0
    for i, (key, name, color, members) in enumerate(hubs):
        ang, hx, hy = hub_pos[i]
        t += .12
        edge(cx, cy, hx, hy, color, .6, 1.8, t)
        count = len(members)
        if key == "SPEND":
            tip = f"Spend once trials end: ${total:.2f}/month"
            inner = "$"
        else:
            tip = f"{name}: {count} subscription(s)"
            inner = str(count)
        nodes.append(bubble(hx, hy, 24, color, t, tip, inner, 15, pulse=True))
        label(hx, hy + 40, name, 13, 800, delay=t)

        if key == "SPEND":
            items = [("Monthly", f"${total:.2f}"), ("Yearly", f"${total * 12:.0f}"),
                     ("Budget", f"{min(total / budget * 100, 999):.0f}%")]
        else:
            items = members
        m = len(items)
        spread = min(170, 48 * (m - 1)) if m > 1 else 0

        for j, item in enumerate(items):
            off = (-spread / 2 + spread / (m - 1) * j) if m > 1 else 0
            phi = ang + math.radians(off)
            lx, ly = hx + 92 * math.cos(phi), hy + 92 * math.sin(phi)
            t += .1
            edge(hx, hy, lx, ly, color, .45, 1.2, t)

            if key == "SPEND":
                nodes.append(bubble(lx, ly, 15, color, t, f"{item[0]}: {item[1]}"))
                label(lx, ly + 29, f"{item[0]} {item[1]}", 10.5, 600, delay=t)
                continue

            s = item
            r = max(13, min(24, 11 + s["price"] * 1.1))
            tip = f"{escape(s['service'])}&#10;${s['price']:.2f}/month&#10;{s['status']}&#10;{s['sub_id']}"
            nodes.append(bubble(lx, ly, r, color, t, tip))
            label(lx, ly + r + 14, s["service"], 11, 700, delay=t)

            days = _days_left(s["next_billing_time"])
            if days is not None:
                nxt = f"in {days}d"
            else:
                nxt = {"APPROVAL_PENDING": "pending", "SUSPENDED": "paused",
                       "CANCELLED": "ended"}.get(s["status"], "-")
            texts = [f"${s['price']:.2f}/mo", f"${s['price'] * 12:.0f}/yr", f"next: {nxt}"]
            if m <= 3:
                angles = (-55, 0, 55)
            else:
                angles = (-30, 30)
                texts = [texts[0], texts[2]]
            for a_off, txt in zip(angles, texts):
                psi = phi + math.radians(a_off)
                d = r + 28
                sx, sy = lx + d * math.cos(psi), ly + d * math.sin(psi)
                edge(lx, ly, sx, sy, color, .3, 1, t + .05)
                nodes.append(
                    f'<circle class="twinkle" cx="{sx:.1f}" cy="{sy:.1f}" r="4.5" '
                    f'fill="{color}" style="--d:{t:.2f}s"/>'
                )
                right = math.cos(psi) >= 0
                label(sx + (8 if right else -8), sy + 3, txt, 9.5, 500, "#aab3cf",
                      "start" if right else "end", t + .1)

    nodes.append(f'<circle class="ripple" cx="{cx}" cy="{cy}" r="34" fill="none" '
                 f'stroke="{NODE_PURPLE}" stroke-width="2"/>')
    nodes.append(bubble(cx, cy, 34, NODE_PURPLE, 0.0, "You: the owner of these subscriptions",
                        "YOU", 14, pulse=True, ink="#ffffff"))

    defs = ('<defs><filter id="glow" x="-60%" y="-60%" width="220%" height="220%">'
            '<feGaussianBlur stdDeviation="4" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
            '</filter></defs>')
    svg = (f'<svg viewBox="0 0 800 600" xmlns="http://www.w3.org/2000/svg">'
           f'{defs}{"".join(edges)}{"".join(nodes)}</svg>')

    legend = "".join(f'<span><i style="background:{STATUS_COLORS[k]}"></i>{name}</span>'
                     for k, name in HUB_ORDER)
    legend += f'<span><i style="background:{SPEND_CYAN}"></i>Spend</span>'

    html = MAP_TEMPLATE.replace("__SVG__", svg).replace("__LEGEND__", legend)
    return html