import plotly.graph_objects as go
from .theme import FONT
from .models import DIRECTIONS, LABELS

COLORS=["#8190a5","#c58a3b","#3267c8"]
def comparison_chart(analytic, metric="vc"):
    fig=go.Figure()
    for sc,color in zip(analytic,COLORS):
        if not sc["rows"]: continue
        fig.add_bar(name=sc["title"],x=[LABELS[r["direction"]] for r in sc["rows"]],
                    y=[r[metric] for r in sc["rows"]],marker_color=color,
                    text=[f"{r[metric]:.3f}" if metric=="vc" else f"{r[metric]:,.0f}" for r in sc["rows"]],
                    textposition="outside",
                    hovertemplate="%{x}: %{y:.3f}<extra>%{fullData.name}</extra>")
    if metric=="vc": fig.add_hline(y=1,line_dash="dash",line_color="#a35c3e",annotation_text="수요 = 가정상 처리능력",annotation_font_size=10,annotation_yshift=7)
    fig.update_layout(barmode="group",height=330,margin=dict(l=10,r=10,t=35,b=10),
                      yaxis_title="v/c" if metric=="vc" else "대/시간",legend=dict(orientation="h",y=1.17),
                      paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family=FONT,color="#23334c"))
    fig.update_yaxes(rangemode="tozero")
    return fig

def sumo_chart(results, metric, title):
    fig=go.Figure()
    names={"before":"입주 전","after":"입주 후","improved":"신호 개선 후보"}
    for sc,color in zip(results,COLORS):
        fig.add_bar(name=names[sc["scenario"]],x=[LABELS[r["direction"]] for r in sc["rows"]],
                    y=[r[metric] for r in sc["rows"]],marker_color=color)
    fig.update_layout(barmode="group",height=320,margin=dict(l=10,r=10,t=30,b=10),
                      yaxis_title=title,legend=dict(orientation="h",y=1.17),paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",font=dict(family=FONT))
    return fig

def intersection(c, sc):
    by={r["direction"]:r for r in sc["rows"]}
    labels={"N":(320,52),"S":(320,365),"W":(105,209),"E":(535,209)}
    pieces=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 415" role="img" aria-label="북 남 동 서 직진 교차로 개념도">',
            '<rect width="640" height="415" rx="4" fill="#f1f4f8"/>',
            '<path d="M270 0H370V415H270Z M0 160H640V260H0Z" fill="#a9b5c4"/>',
            '<path d="M320 0V145 M320 275V415 M0 210H255 M385 210H640" stroke="#f8edbc" stroke-width="3" stroke-dasharray="12 9"/>']
    for x in range(275,367,12):
        pieces.append(f'<path d="M{x} 140v13 M{x} 267v13" stroke="white" stroke-width="7"/>')
    for y in range(165,257,12):
        pieces.append(f'<path d="M250 {y}h13 M377 {y}h13" stroke="white" stroke-width="7"/>')
    pieces.append('<g fill="#3267c8"><path d="M292 100h10v22h8l-13 14-13-14h8z"/><path d="M337 320h10v-22h8l-13-14-13 14h8z"/></g>')
    pieces.append('<g fill="#b77636"><path d="M205 235v-10h22v-8l14 13-14 13v-8z"/><path d="M435 185v10h-22v8l-14-13 14-13v8z"/></g>')
    for d,(x,y) in labels.items():
        row=by.get(d)
        v=f'{row["volume"]:,.0f}' if row else "—"
        pieces.append(f'<rect x="{x-67}" y="{y-24}" width="134" height="66" rx="4" fill="white" stroke="#dce3ec"/>'
                      f'<text x="{x}" y="{y-4}" text-anchor="middle" font-size="13" fill="#5c6b80">{LABELS[d]} 진입 · {c.approaches[d].lanes}차로</text>'
                      f'<text x="{x}" y="{y+23}" text-anchor="middle" font-size="24" font-weight="700" fill="#23334c">{v}</text>')
    pieces.append('<rect x="447" y="41" width="35" height="53" rx="3" fill="#c6d3e5"/><rect x="489" y="29" width="38" height="65" rx="3" fill="#dce5ef"/>'
                  '<text x="486" y="114" text-anchor="middle" font-size="12" fill="#687991">가상 아파트 개발</text>'
                  '<text x="25" y="392" font-size="12" fill="#687991">표시값: 대/시간 · 개념도이며 실제 차량 위치가 아닙니다.</text></svg>')
    return "".join(pieces)

