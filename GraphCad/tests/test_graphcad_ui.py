import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import math
import pytest
from PySide6.QtCore import QSettings,Qt
from PySide6.QtGui import QImage,QPalette
from PySide6.QtWidgets import QApplication,QDialog,QLineEdit,QTableWidgetItem
from graphite.data import pearson_correlation,linear_regression
from graphite.dialogs import DataDialog,PrecisionDialog,PerpendicularDialog
from graphite.export import ExportOptions,export_png
from graphite.window import MainWindow,ExportDialog
from graphite.model import Document,GraphObject
from graphite.themes import apply_theme

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

@pytest.fixture
def win(app,tmp_path,monkeypatch):
    from graphite import window
    path=str(tmp_path/'settings.ini')
    monkeypatch.setattr(window,'QSettings',lambda:QSettings(path,QSettings.Format.IniFormat))
    w=MainWindow();w.replace_document(Document());w.show();app.processEvents()
    yield w
    w.history.mark_saved();w.close();apply_theme(app,'light')

@pytest.mark.parametrize('rows,expected',[
    ([[1,2],[2,4],[3,6]],1),([[1,6],[2,4],[3,2]],-1),
    ([[-1,1],[0,-2],[1,1]],0),([[1,1],[2,3],[3,2]],.5),
    ([],None),([[1,2]],None),([[1,2],[1,3]],None),([[1,2],[2,2]],None)])
def test_pearson_known_datasets_and_undefined(rows,expected):
    r=pearson_correlation(rows)
    if expected is None:assert r is None
    else:assert r==pytest.approx(expected)

def test_r_sign_is_independent_of_r_squared():
    fit=linear_regression([[1,6],[2,4],[3,2]])
    assert fit.r==pytest.approx(-1) and fit.r_squared==1
    fit=linear_regression([[1e10+i,3*i+4] for i in range(10)])
    assert fit.r==pytest.approx(1)
    assert linear_regression([[1,3],[2,3]]).r is None

def test_data_dialog_updates_both_statistics(app):
    dialog=DataDialog(GraphObject('scatter',data={'rows':[[1,6],[2,4],[3,2]]}))
    assert 'R²: 1' in dialog.stats.text() and 'r: -1' in dialog.stats.text()
    dialog.fill_rows([[1,3],[2,3]])
    assert 'r: undefined' in dialog.stats.text()
    dialog.fill_rows([[1,3],[1,4]])
    assert 'r: undefined' in dialog.stats.text()

def test_theme_saved_between_windows_without_altering_document(win,app,monkeypatch):
    before=win.document.to_dict()
    win.set_theme('dark')
    assert app.palette().color(QPalette.ColorRole.Base).lightness()<70
    assert win.settings.value('theme')=='dark'
    assert win.document.to_dict()==before
    other=MainWindow()
    assert other.theme_selector.currentText()=='Dark'
    assert app.property('graphcad_theme')=='dark'
    other.history.mark_saved();other.close()
    win.set_theme('light')
    assert app.palette().color(QPalette.ColorRole.Base).lightness()>240

def test_export_colors_are_identical_across_themes_with_overlays(win,app,tmp_path):
    obj=GraphObject('arrow',[[1,2],[8,7]],style={'color':'#2459ad'})
    win.mutate('Arrow',lambda:win.document.objects.append(obj))
    win.canvas.selected={obj.id};win.canvas._snap_position=(4,5)
    paths=[]
    for theme in ('light','dark'):
        win.set_theme(theme);path=tmp_path/(theme+'.png')
        export_png(win.document,path);paths.append(path)
    a,b=[QImage(str(p)) for p in paths]
    assert (a.width(),a.height())==(1920,1080)
    assert bytes(a.constBits())==bytes(b.constBits())
    assert a.pixelColor(0,0).name()=='#ffffff'

def test_export_default_full_hd_custom_sizes_and_aspect_lock(win,tmp_path):
    assert (ExportOptions().width,ExportOptions().height)==(1920,1080)
    dialog=ExportDialog(win.document,win.document.bounds)
    assert (dialog.width.value(),dialog.height.value())==(1920,1080)
    dialog.width.setValue(1280);assert dialog.height.value()==720
    dialog.height.setValue(900);assert dialog.width.value()==1600
    dialog.keep_ratio.setChecked(False);dialog.width.setValue(840);dialog.height.setValue(630)
    path=tmp_path/'custom.png';export_png(win.document,path,dialog.options())
    image=QImage(str(path));assert (image.width(),image.height())==(840,630)

def test_construct_perpendicular_ui_and_history(win,monkeypatch):
    from graphite import window as module
    p=GraphObject('point',[[2,5]],name='P');line=GraphObject('line',[[0,0],[4,4]],name='Target')
    win.mutate('Source',lambda:win.document.objects.extend([p,line]))
    dialog=PerpendicularDialog(win.document,{p.id,line.id});dialog.accept()
    assert dialog.result()==QDialog.DialogCode.Accepted
    monkeypatch.setattr(dialog,'exec',lambda:QDialog.DialogCode.Accepted)
    monkeypatch.setattr(module,'PerpendicularDialog',lambda *a:dialog)
    win.perpendicular_construction()
    helpers=[o for o in win.document.objects if 'perpendicular' in o.data]
    assert len(helpers)==2
    foot=next(o for o in helpers if o.kind=='point')
    assert foot.points[0]==pytest.approx([3.5,3.5])
    win.mutate('Move source',lambda:setattr(p,'points',[[4,8]]))
    assert foot.points[0]==pytest.approx([6,6])
    win.undo();assert win.find(foot.id).points[0]==pytest.approx([3.5,3.5])
    win.redo();assert win.find(foot.id).points[0]==pytest.approx([6,6])
    win.canvas.selected={foot.id};win.detach_construction()
    assert all('perpendicular' not in o.data for o in win.document.objects)

def test_precision_dialog_applies_to_selected_and_is_discoverable(win,monkeypatch):
    from graphite import window as module
    line=GraphObject('arrow',[[1,1],[3,4]],name='Arrow')
    win.mutate('Arrow',lambda:win.document.objects.append(line));win.canvas.selected={line.id}
    dialog=PrecisionDialog(win.document,win.canvas)
    dialog.mode.setCurrentIndex(dialog.mode.findData('angle'));dialog.angle.setValue(30)
    dialog.apply_selected.setChecked(True);dialog.snap_lines.setChecked(True);dialog.tolerance.setValue(14)
    dialog.accept();monkeypatch.setattr(dialog,'exec',lambda:QDialog.DialogCode.Accepted)
    monkeypatch.setattr(module,'PrecisionDialog',lambda *a:dialog)
    win.configure_precision()
    dx,dy=line.points[1][0]-1,line.points[1][1]-1
    assert math.degrees(math.atan2(dy,dx))==pytest.approx(30)
    assert win.document.snap_lines and win.document.snap_tolerance_pixels==14
    assert '30°' in win.constraint_label.text()
    assert 'GraphCad' in win.windowTitle()
    assert win.export_button.accessibleName()=='Export graph'
