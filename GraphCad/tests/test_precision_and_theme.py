"""Guard against platform palettes and editor-induced coordinate drift."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtGui import QPalette,QColor
from PySide6.QtWidgets import QApplication,QDialog
from graphite.app import apply_theme
from graphite.dialogs import AxisDialog,number
from graphite.model import Document


def test_theme_remains_readable_with_dark_system_palette():
    app=QApplication.instance() or QApplication([])
    dark=QPalette();dark.setColor(QPalette.ColorRole.Text,QColor('white'))
    dark.setColor(QPalette.ColorRole.Base,QColor('#333333'));app.setPalette(dark)
    apply_theme(app)
    assert app.palette().color(QPalette.ColorRole.Text).lightness()<100
    assert app.palette().color(QPalette.ColorRole.Base).lightness()>240
    assert app.palette().color(QPalette.ColorRole.WindowText).lightness()<100


def test_numeric_editors_preserve_full_finite_double_precision():
    app=QApplication.instance() or QApplication([])
    values=[1.2345678901234567,1.2345678901234567e-9,987654321012.3456]
    for value in values:
        editor=number(value)
        assert editor.value()==value
        assert float(editor.text())==value


def test_unchanged_axis_dialog_preserves_precise_ranges():
    app=QApplication.instance() or QApplication([])
    doc=Document()
    doc.x_axis.minimum=1.2345678901234567e-7
    doc.x_axis.maximum=123.45678901234567
    doc.x_axis.major=0.012345678901234567
    doc.y_axis.position=-0.12345678901234567
    dialog=AxisDialog(doc)
    dialog.accept()
    assert dialog.result()==QDialog.DialogCode.Accepted
    assert dialog.result_document.to_dict()==doc.to_dict()
