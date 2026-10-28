
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
    html = html.replace(".wrap { display:flex;", ".wrap { justify-content:center; display:flex;")
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
  
SLIDING_TEMPLATE = """
<style>
  body { margin:0; background:transparent; font-family:'Segoe UI', system-ui, sans-serif; color:#fff; }
  .row { display:flex; align-items:center; height:56px; font-size:40px; font-weight:800;
         line-height:1; font-variant-numeric: tabular-nums; }
  .cur { color:#00d632; margin-right:3px; text-shadow:0 0 14px rgba(0,214,50,.45); }
  .col { height:1em; overflow:hidden; }
  .strip { display:flex; flex-direction:column;
           transition: transform .75s cubic-bezier(.2,.9,.25,1.05); }
  .strip span { display:block; height:1em; line-height:1; text-align:center; }
  .per { margin-left:10px; font-size:13px; font-weight:600; color:#8f9ab8;
         align-self:flex-end; padding-bottom:10px; }
  @media (prefers-reduced-motion: reduce) { .strip { transition:none; } }
</style>
<div class="row"><span class="cur">$</span>__COLS__<span class="per">per month</span></div>
<script>
  requestAnimationFrame(function () { requestAnimationFrame(function () {
    document.querySelectorAll('.strip').forEach(function (s) {
      s.style.transform = 'translateY(-' + s.dataset.to + 'em)';
    });
  }); });
</script>
"""


def sliding_number_html(value, prev=0):
    value = max(int(round(value)), 0)
    prev = max(int(round(prev)), 0)
    to_digits = str(value)
    from_digits = str(prev).zfill(len(to_digits))[-len(to_digits):]
    cols = ""
    for f, t in zip(from_digits, to_digits):
        digits = "".join(f"<span>{d}</span>" for d in range(10))
        cols += (f"<div class='col'><div class='strip' data-to='{t}' "
                 f"style='transform:translateY(-{f}em)'>{digits}</div></div>")
    return SLIDING_TEMPLATE.replace("__COLS__", cols)

def text_roll_html(text):
    from html import escape

    letters = ""
    for i, ch in enumerate(text):
        if ch == " ":
            letters += "<span class='tr-sp'>&nbsp;</span>"
            continue
        c = escape(ch)
        letters += (f"<span class='tr-l'><span class='tr-in' data-ch='{c}' "
                    f"style='--i:{i}'>{c}</span></span>")
    return f"<div class='text-roll'>{letters}</div>"
  
_TRASH_COLORS = {"k": "#0b0f19", "s": "#cfd6e8", "S": "#8f9ab8", "r": "#ff4b4b"}
_TRASH_LID = [
    "......kkkk......",
    "......kssk......",
    ".kkkkkkkkkkkkkk.",
    ".kSSSSSSSSSSSSk.",
    ".kkkkkkkkkkkkkk.",
]
_TRASH_BODY = [
    "..kkkkkkkkkkkk..",
    "..kssSssSssSsk..",
    "..kssSssSssSsk..",
    "..kssSssSssSsk..",
    "..kssrrrrrrssk..",
    "..kssSssSssSsk..",
    "..kssSssSssSsk..",
    "..kssSssSssSsk..",
    "..kssSssSssSsk..",
    "..kkkkkkkkkkkk..",
]


def _trash_svg():
    def rects(rows, y0):
        out = ""
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch != ".":
                    out += (f"<rect x='{x}' y='{y + y0}' width='1.02' height='1.02' "
                            f"fill='{_TRASH_COLORS[ch]}'/>")
        return out

    return ("<svg class='pixt' viewBox='0 0 16 16' shape-rendering='crispEdges'>"
            f"<g class='body'>{rects(_TRASH_BODY, 5)}</g>"
            f"<g class='lid'>{rects(_TRASH_LID, 0)}</g></svg>")


KILL_BLOCK = r"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
  #trash { position:absolute; right:12px; bottom:44px; width:132px; text-align:center;
           user-select:none; transition: transform .2s ease; animation: idle 2.6s steps(4) infinite; }
  #trash .pixt { width:96px; height:96px; display:block; margin:0 auto; overflow:visible;
                 image-rendering:pixelated; filter:drop-shadow(0 0 4px rgba(255,75,75,.15));
                 transition: filter .2s ease; }
  #trash .lid { transform-box: fill-box; transform-origin: 0% 100%;
                transition: transform .25s cubic-bezier(.3,1.6,.5,1); }
  #trash.ready { transform: scale(1.08); }
  #trash.ready .pixt { filter:drop-shadow(0 0 10px rgba(255,75,75,.6)); }
  #trash.over { transform: scale(1.2); }
  #trash.over .pixt { filter:drop-shadow(0 0 18px rgba(255,75,75,1)); }
  #trash.over .lid { transform: translate(-1px,-4px) rotate(-30deg); }
  #trash.dropped { animation: slam .5s steps(5); }
  #trash .cap { font-family:'Press Start 2P', monospace; font-size:8px; line-height:1.7;
                color:#ff4b4b; margin-top:6px; text-shadow:2px 2px 0 #0b0f19; }
  @keyframes idle { 50% { transform: translateY(-3px); } }
  @keyframes slam { 30% { transform: translateY(5px) scale(1.15); } 100% { transform: none; } }
  @media (prefers-reduced-motion: reduce) { #trash { animation:none; } }
</style>
<div id="trash">__TRASH__<div class="cap" id="trashCap">KILL SWITCH<br>drag a sub in</div></div>
<script>
(function () {
  var svg = document.querySelector('svg');
  var trash = document.getElementById('trash');
  var cap = document.getElementById('trashCap');
  var drag = null;

  function toSvg(e) {
    var pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }
  function overTrash(e) {
    var r = trash.getBoundingClientRect();
    return e.clientX >= r.left - 12 && e.clientX <= r.right + 12 &&
           e.clientY >= r.top - 12 && e.clientY <= r.bottom + 12;
  }
  function arm(id) {
    try {
      var btns = window.parent.document.querySelectorAll('button');
      for (var i = 0; i < btns.length; i++) {
        if (btns[i].textContent.trim() === 'kill-' + id) { btns[i].click(); return true; }
      }
    } catch (err) {}
    return false;
  }
  function glide(node, from, to) {
    var t0 = null;
    function step(t) {
      if (t0 === null) t0 = t;
      var k = Math.min((t - t0) / 280, 1), e = 1 - Math.pow(1 - k, 3);
      node.setAttribute('transform', 'translate(' + (from.x + (to.x - from.x) * e) + ',' +
                        (from.y + (to.y - from.y) * e) + ')');
      if (k < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  document.querySelectorAll('g.node').forEach(function (node) {
    var title = node.querySelector('title');
    if (!title) return;
    var lines = title.textContent.split('\n').map(function (s) { return s.trim(); });
    var id = lines.filter(function (l) { return /^I-[A-Z0-9]+$/.test(l); })[0];
    var live = lines.indexOf('ACTIVE') > -1 || lines.indexOf('SUSPENDED') > -1;
    if (!id || !live) return;
    var m = /translate\(([-\d.]+),\s*([-\d.]+)\)/.exec(node.getAttribute('transform'));
    if (!m) return;
    var home = { x: parseFloat(m[1]), y: parseFloat(m[2]) };
    node.style.cursor = 'grab';
    node.style.touchAction = 'none';

    node.addEventListener('pointerdown', function (e) {
      e.preventDefault();
      node.setPointerCapture(e.pointerId);
      var p = toSvg(e);
      drag = { dx: p.x - home.x, dy: p.y - home.y, cur: { x: home.x, y: home.y } };
      node.style.cursor = 'grabbing';
      trash.classList.add('ready');
    });
    node.addEventListener('pointermove', function (e) {
      if (!drag) return;
      var p = toSvg(e);
      drag.cur = { x: p.x - drag.dx, y: p.y - drag.dy };
      node.setAttribute('transform', 'translate(' + drag.cur.x + ',' + drag.cur.y + ')');
      trash.classList.toggle('over', overTrash(e));
    });
    function finish(e, allowDrop) {
      if (!drag) return;
      var hit = allowDrop && overTrash(e), cur = drag.cur;
      drag = null;
      node.style.cursor = 'grab';
      trash.classList.remove('ready', 'over');
      if (hit) {
        node.style.transition = 'opacity .25s';
        node.style.opacity = '0';
        node.style.pointerEvents = 'none';
        trash.classList.add('dropped');
        if (arm(id)) {
          cap.innerHTML = 'ARMED<br>confirm above';
        } else {
          cap.innerHTML = 'use the button<br>in Subscriptions';
          node.style.opacity = '1';
          node.style.pointerEvents = 'auto';
          glide(node, cur, home);
        }
      } else {
        glide(node, cur, home);
      }
    }
    node.addEventListener('pointerup', function (e) { finish(e, true); });
    node.addEventListener('pointercancel', function (e) { finish(e, false); });
  });
})();
</script>
"""


def kill_map_html(subs, budget=50.0, nonce=0):
    # the nonce changes the page when a kill is aborted or done, so the map reloads fresh
    return (subscription_map_html(subs, budget)
            + KILL_BLOCK.replace("__TRASH__", _trash_svg())
            + f"<!-- {nonce} -->")
def kill_trash_html():
    return ("<div id='bouncer-trash'>" + _trash_svg() +
            "<div class='cap' id='bouncer-trash-cap'>KILL SWITCH<br>drag a sub in</div></div>")


KILL_BLOCK_V2 = r"""
<script>
(function () {
  var P, frame;
  try { P = window.parent.document; frame = window.frameElement; } catch (err) { return; }
  var svg = document.querySelector('svg');
  if (!P || !frame || !svg) return;
  var drag = null;

  function trashEl() { return P.getElementById('bouncer-trash'); }
  function capEl() { return P.getElementById('bouncer-trash-cap'); }
  function at(e, fromParent) {
    if (fromParent) return { x: e.clientX, y: e.clientY };
    var r = frame.getBoundingClientRect();
    return { x: e.clientX + r.left, y: e.clientY + r.top };
  }
  function overTrash(pt) {
    var t = trashEl();
    if (!t) return false;
    var r = t.getBoundingClientRect();
    return pt.x >= r.left - 16 && pt.x <= r.right + 16 &&
           pt.y >= r.top - 16 && pt.y <= r.bottom + 16;
  }
  function arm(id) {
    try {
      var btns = P.querySelectorAll('button');
      for (var i = 0; i < btns.length; i++) {
        if (btns[i].textContent.trim() === 'kill-' + id) { btns[i].click(); return true; }
      }
    } catch (err) {}
    return false;
  }
  function makeGhost(node) {
    var c = node.querySelector('circle');
    var scale = svg.getScreenCTM().a;
    var d = c ? parseFloat(c.getAttribute('r')) * 2 * scale : 36;
    var g = P.createElement('div');
    g.style.cssText = 'position:fixed;z-index:2147483000;pointer-events:none;border-radius:50%;' +
      'width:' + d + 'px;height:' + d + 'px;transform:translate(-50%,-50%);' +
      'background:' + (c ? c.getAttribute('fill') : '#ffbb00') + ';' +
      'border:2px solid rgba(255,255,255,.7);box-shadow:0 0 18px rgba(255,255,255,.35);opacity:.95;';
    P.body.appendChild(g);
    return g;
  }
  function place(g, pt) { g.style.left = pt.x + 'px'; g.style.top = pt.y + 'px'; }

  function onMove(fromParent) {
    return function (e) {
      if (!drag) return;
      var pt = at(e, fromParent);
      place(drag.ghost, pt);
      var t = trashEl();
      if (t) t.classList.toggle('over', overTrash(pt));
    };
  }
  function onEnd(fromParent, allow) {
    return function (e) {
      if (!drag) return;
      var pt = at(e, fromParent);
      var hit = allow && overTrash(pt);
      var d = drag; drag = null;
      detach();
      P.body.style.userSelect = '';
      if (d.ghost.parentNode) d.ghost.parentNode.removeChild(d.ghost);
      var t = trashEl(), cap = capEl();
      if (t) t.classList.remove('ready', 'over');
      if (hit) {
        if (t) {
          t.classList.add('dropped');
          setTimeout(function () { t.classList.remove('dropped'); }, 600);
        }
        if (arm(d.id)) {
          d.node.style.opacity = '0';
          d.node.style.pointerEvents = 'none';
          if (cap) cap.innerHTML = 'ARMED<br>confirm above';
        } else {
          d.node.style.opacity = '1';
          if (cap) cap.innerHTML = 'use the button<br>in Subscriptions';
        }
      } else {
        d.node.style.opacity = '1';
      }
    };
  }
  var handlers = [
    [document, 'pointermove', onMove(false)], [P, 'pointermove', onMove(true)],
    [document, 'pointerup', onEnd(false, true)], [P, 'pointerup', onEnd(true, true)],
    [document, 'pointercancel', onEnd(false, false)], [P, 'pointercancel', onEnd(true, false)]
  ];
  function attach() { handlers.forEach(function (h) { h[0].addEventListener(h[1], h[2]); }); }
  function detach() { handlers.forEach(function (h) { h[0].removeEventListener(h[1], h[2]); }); }

  document.querySelectorAll('g.node').forEach(function (node) {
    var title = node.querySelector('title');
    if (!title) return;
    var lines = title.textContent.split('\n').map(function (s) { return s.trim(); });
    var id = lines.filter(function (l) { return /^I-[A-Z0-9]+$/.test(l); })[0];
    var live = lines.indexOf('ACTIVE') > -1 || lines.indexOf('SUSPENDED') > -1;
    if (!id || !live) return;
    node.style.cursor = 'grab';
    node.style.touchAction = 'none';
    node.addEventListener('pointerdown', function (e) {
      e.preventDefault();
      drag = { node: node, id: id, ghost: makeGhost(node) };
      place(drag.ghost, at(e, false));
      node.style.opacity = '.25';
      P.body.style.userSelect = 'none';
      var t = trashEl();
      if (t) t.classList.add('ready');
      attach();
    });
  });
})();
</script>
"""


def kill_map_html(subs, budget=50.0, nonce=0):
    # the nonce changes when a kill is aborted or done, so the map reloads fresh
    return subscription_map_html(subs, budget) + KILL_BLOCK_V2 + f"<!-- {nonce} -->"

GUARD_PIXELS = [
    "................",
    ".....kkkkkk.....",
    "....khwhhhhk....",
    "....khhhhhhk....",
    "....kggggggk....",
    "....kgwggwgke...",
    "....khhhhhhk....",
    "....khhHHhhk....",
    "....khhhhhhk....",
    ".....kkkkkk.....",
    "......khhk......",
    ".kkkkkkttkkkkkk.",
    ".kuuuktrrtkuuuk.",
    ".kuuuktrrtkuuuk.",
    ".kuuukkrrkkuuuk.",
    ".kUUUUUUUUUUUUk.",
    ".kyhUUUUUUUUhyk.",
    ".kkkkkkkkkkkkkk.",
    ".kuuuuuuuuuuuuk.",
    ".kuuuuuuuuuuuuk.",
    "..kkkkkkkkkkkk..",
    "..kdddk..kdddk..",
    "..kdddk..kdddk..",
    ".kbbbbk..kbbbbk.",
    ".kkkkkk..kkkkkk.",
]
GUARD_COLORS = {
    "k": "#02030a", "h": "#f2b48c", "H": "#b8714c", "w": "#ffffff",
    "g": "#0a0c14", "t": "#ffffff", "r": "#e0483a", "u": "#262c3d",
    "U": "#3b4663", "d": "#161a26", "y": "#ffbb00", "b": "#07080c",
}
BANG_PIXELS = [
    "..rrr..",
    ".rrwrr.",
    "rrrwrrr",
    "rrrwrrr",
    "rrrrrrr",
    ".rrwrr.",
    "..rrr..",
]
VIP_GLYPHS = {
    "V": ["k.k", "k.k", "k.k", "k.k", ".k."],
    "I": ["kkk", ".k.", ".k.", ".k.", "kkk"],
    "P": ["kkk", "k.k", "kkk", "k..", "k.."],
}


def _px(rows, colors, u=1, x0=0, y0=0):
    out = []
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != "." and ch in colors:
                out.append(f'<rect x="{x0 + x * u}" y="{y0 + y * u}" width="{u * 1.02}" '
                           f'height="{u * 1.02}" fill="{colors[ch]}"/>')
    return "".join(out)


def _guard(color, alert):
    colors = dict(GUARD_COLORS, e=color)
    sprite = f'<g transform="scale(5)">{_px(GUARD_PIXELS, colors)}</g>'
    bang = ""
    if alert:
        badge = _px(BANG_PIXELS, {"r": "#ff4b4b", "w": "#ffffff"})
        bang = (f'<g class="hop"><g transform="translate(22.5,-42) scale(5)">{badge}</g></g>')
    return sprite + bang


def _pixel_scene(color, alert):
    x0, y0 = 175, 30

    shadow = '<rect x="40" y="235" width="355" height="5" fill="#000" opacity=".35"/>'

    carpet = ""
    for i in range(19):
        k = min(i // 6, 2)
        w, x, y = 85 + 20 * k, 175 - 10 * k, 140 + 5 * i
        carpet += f'<rect x="{x}" y="{y}" width="{w}" height="5" fill="#33447a"/>'
        carpet += (f'<rect x="{x}" y="{y}" width="5" height="5" fill="#d4af37"/>'
                   f'<rect x="{x + w - 5}" y="{y}" width="5" height="5" fill="#d4af37"/>')

    door = (
        f'<rect x="{x0}" y="{y0}" width="85" height="110" fill="#d4af37"/>'
        f'<rect x="{x0 + 5}" y="{y0 + 5}" width="75" height="100" fill="#1f2a55"/>'
        f'<rect x="{x0 + 5}" y="{y0 + 5}" width="75" height="5" fill="#2b3a74"/>'
        f'<rect x="{x0 + 10}" y="{y0 + 55}" width="65" height="5" fill="#2b3a74"/>'
        f'<rect x="{x0 + 65}" y="{y0 + 65}" width="5" height="15" fill="#d4af37"/>'
        f'<rect x="{x0 + 10}" y="{y0 + 10}" width="65" height="35" fill="#f3c63a"/>'
    )
    for n, ch in enumerate("VIP"):
        door += _px(VIP_GLYPHS[ch], {"k": "#2a2108"}, u=5, x0=x0 + 15 + n * 20, y0=y0 + 15)

    lamp = (f'<rect x="210" y="5" width="15" height="15" fill="#10152a"/>'
            f'<rect x="215" y="10" width="5" height="5" fill="{color}"/>')

    guard = _guard(color, alert)
    left = (f'<g transform="translate(45,110)"><g class="mv"><g class="bob">{guard}</g></g></g>')
    right = (f'<g transform="translate(390,110) scale(-1,1)"><g class="mv r"><g class="bob">'
             f'{guard}</g></g></g>')

    posts = ""
    for px in (155, 280):
        posts += (f'<rect x="{px}" y="170" width="5" height="65" fill="#d4af37"/>'
                  f'<rect x="{px - 5}" y="165" width="15" height="5" fill="#f3c63a"/>')
    rope = ""
    for j in range(24):
        t = (j - 11.5) / 11.5
        sag = round(12 * (1 - t * t) / 5) * 5
        rope += f'<rect x="{160 + 5 * j}" y="{178 + sag}" width="5" height="5" fill="#c0392b"/>'

    return (f'<svg viewBox="0 0 435 250" width="435" height="250" shape-rendering="crispEdges" '
            f'xmlns="http://www.w3.org/2000/svg">{shadow}{carpet}{door}{lamp}{left}{right}'
            f'{posts}{rope}</svg>')


PIXEL_SCENE_TEMPLATE = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
  body { margin:0; background:transparent; }
  .wrap { display:flex; align-items:center; justify-content:center; gap:26px; flex-wrap:wrap; }
  svg { display:block; image-rendering:pixelated; }
  .bubble { font-family:'Press Start 2P', monospace; font-size:11px; line-height:1.9;
            color:#ffffff; max-width:360px; padding:16px 18px; background:#141a2b;
            border:3px solid __COLOR__; box-shadow:4px 4px 0 #05070d; }
  .mv  { animation: patrol __DUR__ steps(4) infinite alternate; }
  .mv.r { animation-delay: -__DUR__; }
  .bob { animation: bob __BOB__ steps(1) infinite alternate; }
  .hop { animation: bob __BOB__ steps(1) infinite alternate; }
  @keyframes patrol { from { transform: translateX(-10px); } to { transform: translateX(10px); } }
  @keyframes bob { from { transform: translateY(0); } to { transform: translateY(-5px); } }
  @media (prefers-reduced-motion: reduce) { .mv, .bob, .hop { animation:none; } }
</style>
<div class="wrap">__SVG__<div class="bubble">__MSG__</div></div>
"""


def bouncer_html(message, alert=False):
    from html import escape

    color = "#ff4b4b" if alert else "#2ecc71"
    html = PIXEL_SCENE_TEMPLATE
    html = html.replace("__SVG__", _pixel_scene(color, alert))
    html = html.replace("__MSG__", escape(message))
    html = html.replace("__COLOR__", color)
    html = html.replace("__DUR__", "1.2s" if alert else "3.2s")
    html = html.replace("__BOB__", ".3s" if alert else ".6s")
    return html
  
def show_grid(df, key, height=340, status_col=None, money_cols=(), selectable=False):
    from st_aggrid import GridUpdateMode

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(resizable=True, sortable=True, filter=True, flex=1, minWidth=110)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=8)
    if status_col and status_col in df.columns:
        gb.configure_column(status_col, cellStyle=STATUS_STYLE)
    for col in money_cols:
        if col in df.columns:
            gb.configure_column(col, valueFormatter=MONEY_FORMAT)
    if selectable:
        gb.configure_selection("single", use_checkbox=True)

    options = dict(
        gridOptions=gb.build(),
        height=height,
        theme="streamlit",
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=True,
        key=key,
    )
    if selectable:
        options["update_mode"] = GridUpdateMode.SELECTION_CHANGED
    grid = AgGrid(df, **options)

    if not selectable:
        return []
    try:
        rows = grid["selected_rows"]
    except Exception:
        rows = getattr(grid, "selected_rows", None)
    if rows is None:
        return []
    if hasattr(rows, "to_dict"):  # newer versions return a DataFrame
        rows = rows.to_dict("records")
    return list(rows)
  
STATUS_PILL = JsCode("""
function(params) {
  var map = {
    'ACTIVE': ['#2ecc71', 'rgba(46,204,113,.16)', 'ACTIVE'],
    'APPROVAL_PENDING': ['#f5a623', 'rgba(245,166,35,.16)', 'PENDING'],
    'SUSPENDED': ['#4da3ff', 'rgba(77,163,255,.16)', 'PAUSED'],
    'CANCELLED': ['#8a90a2', 'rgba(138,144,162,.16)', 'CANCELLED']
  };
  var m = map[params.value] || ['#cfd6e8', 'rgba(207,214,232,.12)', params.value];
  return '<span style="display:inline-block;padding:2px 10px;border-radius:999px;' +
         'font-size:11px;font-weight:700;letter-spacing:.4px;color:' + m[0] +
         ';background:' + m[1] + ';border:1px solid ' + m[0] + '">' + m[2] + '</span>';
}
""")

BUDGET_BAR = JsCode("""
function(params) {
  var v = Number(params.value);
  if (!v) { return '<span style="color:#6b7490">-</span>'; }
  var w = Math.min(v, 100);
  var c = v <= 25 ? '#2ecc71' : (v <= 50 ? '#f5a623' : '#ff4b4b');
  return '<div style="display:flex;align-items:center;gap:8px;height:100%">' +
    '<div style="flex:1;height:8px;border-radius:4px;background:#232a40">' +
    '<div style="width:' + w + '%;height:8px;border-radius:4px;background:' + c + '"></div></div>' +
    '<span style="font-size:11px;color:#9aa4bf;min-width:34px;text-align:right">' +
    v.toFixed(0) + '%</span></div>';
}
""")


def days_renderer(limit):
    return JsCode("""
function(params) {
  var d = Number(params.value);
  if (isNaN(d) || d < 0) { return '<span style="color:#6b7490">-</span>'; }
  var hot = d <= __LIMIT__;
  var label = d === 0 ? 'today' : d + (d === 1 ? ' day' : ' days');
  return '<span style="font-weight:' + (hot ? '800' : '500') + ';color:' +
         (hot ? '#ff6b6b' : '#cfd6e8') + '">' + label + '</span>';
}
""".replace("__LIMIT__", str(int(limit))))


def due_row_style(limit):
    return JsCode("""
function(params) {
  var d = Number(params.data['Days left']);
  if (params.data['Status'] === 'ACTIVE' && d >= 0 && d <= __LIMIT__) {
    return {background: 'rgba(255,75,75,.10)', borderLeft: '3px solid #ff4b4b'};
  }
  return null;
}
""".replace("__LIMIT__", str(int(limit))))


def show_grid(df, key, height=340, status_col=None, money_cols=(), selectable=False,
              renderers=None, row_style=None, search=False):
    import streamlit as st
    from st_aggrid import GridUpdateMode

    query = ""
    if search:
        query = st.text_input("Quick search", key=f"{key}_search",
                              placeholder="Search every column, then press Enter",
                              label_visibility="collapsed")

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(resizable=True, sortable=True, filter=True, flex=1, minWidth=110)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=8)
    if status_col and status_col in df.columns:
        gb.configure_column(status_col, cellStyle=STATUS_STYLE)
    for col in money_cols:
        if col in df.columns:
            gb.configure_column(col, valueFormatter=MONEY_FORMAT)
    for col, code in (renderers or {}).items():
        if col in df.columns:
            gb.configure_column(col, cellRenderer=code)
    if selectable:
        gb.configure_selection("single", use_checkbox=True)

    extra = {}
    if row_style is not None:
        extra["getRowStyle"] = row_style
    if search and query:
        extra["quickFilterText"] = query
    if extra:
        gb.configure_grid_options(**extra)

    options = dict(
        gridOptions=gb.build(),
        height=height,
        theme="streamlit",
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=True,
        key=key,
    )
    if selectable:
        options["update_mode"] = GridUpdateMode.SELECTION_CHANGED
    grid = AgGrid(df, **options)

    if not selectable:
        return []
    try:
        rows = grid["selected_rows"]
    except Exception:
        rows = getattr(grid, "selected_rows", None)
    if rows is None:
        return []
    if hasattr(rows, "to_dict"):
        rows = rows.to_dict("records")
    return list(rows)