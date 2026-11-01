"""Regenerate editable examples and inspectable export samples."""
import os
from pathlib import Path
import sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from graphite.model import Document,GraphObject,Axis
from graphite.templates import make_template
from graphite.export import ExportOptions,export_png,export_pdf,export_svg,export_dxf
from graphite.app import apply_theme
from graphite.constructions import create_perpendicular


def create_perpendicular_for_example(doc,source,target):
    doc.objects=[source,target]
    return create_perpendicular(doc,source.id,target.id)

def main():
    app=QApplication.instance() or QApplication([])
    apply_theme(app)
    folder=ROOT/'examples';folder.mkdir(exist_ok=True)
    econ=make_template('Supply and demand')
    econ.save(folder/'supply-demand.graphite')
    mixed=econ.clone();mixed.title='Functions and manual construction'
    demand=next(o for o in mixed.objects if o.name=='Demand curve')
    demand.kind='function';demand.points=[]
    demand.data.update(expression='y = -x + 10',domain_min=1.2,domain_max=8.8)
    supply=next(o for o in mixed.objects if o.name=='Supply curve')
    supply.kind='curve';supply.points=[[1.2,1.2],[3.5,3.1],[5,5],[8.8,8.8]]
    mixed.objects.append(GraphObject('arrow',[[5.7,6.0],[7.2,6.4]],name='Supply shift',label='Shift',style={'color':'#45816d','width':2.2,'arrow_size':13}))
    mixed.save(folder/'mixed-workflow.graphite')
    maths=make_template('Cartesian');maths.title='Functions and discontinuities'
    maths.x_axis.minimum=-6;maths.x_axis.maximum=6;maths.y_axis.minimum=-4;maths.y_axis.maximum=8
    maths.objects=[GraphObject('function',name='Quadratic',label='y = x²',data={'expression':'x^2','label_position':[2,4]},style={'color':'#2459ad'}),GraphObject('function',name='Sine',label='sin(x)',data={'expression':'sin(x)','label_position':[3.2,0]},style={'color':'#b45c2c'}),GraphObject('function',name='Reciprocal',label='1/x',data={'expression':'1/x','label_position':[-2.5,-.4]},style={'color':'#45816d'})]
    maths.save(folder/'mathematics.graphite')
    data=Document(title='Scatter and linked regression',x_axis=Axis(0,12,2,.5,'X',negative=False),y_axis=Axis(0,30,5,1,'Y',negative=False,label_side='left'),grid_major=True,origin_visible=False)
    source=GraphObject('scatter',name='Experimental observations',data={'rows':[[1,4.5],[2,5.8],[3,8.1],[4,10.8],[5,12.7],[6,14.1],[7,18.2],[8,19.4],[9,21.2],[10,24.1]]},style={'color':'#2459ad','fill':'#ffffff','marker_size':5})
    data.objects=[source,GraphObject('regression',name='Least-squares fit',label='Linear fit',data={'source_id':source.id,'label_position':[8,22]},style={'color':'#b45c2c','width':2}),GraphObject('text',[[1,27]],name='Regression description',data={'text':'Linked observations and least-squares line'},style={'color':'#33465f','font_size':13})]
    data.save(folder/'scatter-regression.graphite')
    options=ExportOptions(width=1800,height=1350,margin=25)
    export_png(mixed,folder/'mixed-workflow.png',options)
    export_pdf(mixed,folder/'mixed-workflow.pdf',options)
    export_svg(mixed,folder/'mixed-workflow.svg',options)
    export_dxf(mixed,folder/'mixed-workflow.dxf',options)
    perpendicular=Document(title='Linked perpendicular example',snap_lines=True)
    source=GraphObject('point',[[3,8]],name='Source P',label='P')
    target=GraphObject('line',[[1,2],[9,6]],name='Reference line',label='l')
    perpendicular.objects=[source,target]+create_perpendicular_for_example(perpendicular,source,target)
    perpendicular.update_constructions();perpendicular.save(folder/'perpendicular.graphite')
    export_png(perpendicular,folder/'perpendicular.png')
    # Reopen every sample to verify editable project persistence after generation.
    for file in folder.glob('*.graphite'):
        loaded=Document.load(file)
        assert loaded.objects or loaded.x_axis.visible
    print('Created five editable projects and PNG/PDF/SVG/DXF sample exports.')

if __name__=='__main__':main()
