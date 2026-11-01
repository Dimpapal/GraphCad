"""Native widget integration tests for document commands and numerical editors."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from types import SimpleNamespace
import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QLineEdit, QMessageBox, QTableWidgetItem

from graphite import window as window_module
from graphite.dialogs import AxisDialog, DataDialog, FunctionDialog
from graphite.inspector import Inspector
from graphite.model import Document, GraphObject
from graphite.window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(window_module, "QSettings", lambda: QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    win = MainWindow()
    win.show()
    qapp.processEvents()
    win.replace_document(Document())
    win.canvas.setFocus()
    qapp.processEvents()
    yield win
    monkeypatch.setattr(win, "confirm_discard", lambda: True)
    win.close()
    qapp.processEvents()


def select(window, *objects):
    window.canvas.selected = {o.id for o in objects}
    window.selection_changed(window.canvas.selected)
    window.canvas.setFocus()


def test_inspector_edits_are_transactional_and_undoable(window):
    point = GraphObject("point", [[4, 7]], name="Internal point", label="A")
    window.mutate("Place point", lambda: window.document.objects.append(point))
    select(window, point)
    panel = window.inspector
    panel.fields["name"].setText("Equilibrium")
    panel.geometry.item(0, 0).setText("4.125")
    panel.geometry.item(0, 1).setText("7.875")
    assert point.name == "Internal point" and point.points == [[4, 7]]
    panel.apply()
    edited = window.find(point.id)
    assert edited.name == "Equilibrium" and edited.label == "A"
    assert edited.points == [[4.125, 7.875]]
    window.undo()
    assert window.find(point.id).points == [[4, 7]]
    assert window.find(point.id).name == "Internal point"
    window.redo()
    assert window.find(point.id).points == [[4.125, 7.875]]


def test_inspector_invalid_geometry_preserves_model(window):
    point = GraphObject("point", [[4, 7]], name="A")
    window.mutate("Place point", lambda: window.document.objects.append(point))
    select(window, point)
    window.inspector.geometry.item(0, 0).setText("nan")
    window.inspector.apply()
    assert window.find(point.id).points == [[4, 7]]
    assert "finite" in window.inspector.error.text()


def test_renaming_in_inspector_preserves_full_coordinate_precision(window):
    coordinates = [[1.2345678901234567, 7.876543210987654]]
    point = GraphObject("point", [p[:] for p in coordinates], name="A")
    window.mutate("Place precise point", lambda: window.document.objects.append(point))
    select(window, point)
    window.inspector.fields["name"].setText("Renamed")
    window.inspector.apply()
    assert window.find(point.id).points == coordinates


def test_failed_mutation_restores_model_inspector_and_history(window, monkeypatch):
    point = GraphObject("point", [[4, 7]], name="Original")
    window.mutate("Place point", lambda: window.document.objects.append(point))
    window.history.mark_saved()
    select(window, point)
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    def invalid_edit():
        point.name = "Invalid change"
        point.style["width"] = -4
    window.mutate("Invalid edit", invalid_edit)
    assert window.find(point.id).name == "Original"
    assert window.find(point.id).style["width"] == 2
    assert window.history.document is window.document
    assert not window.history.is_dirty()
    assert window.history.undo_label == "Place point"
    assert window.actions["undo"].isEnabled()
    assert window.inspector.obj is None
    assert "Original" in window.object_tree.topLevelItem(0).text(0)
    assert messages and "width" in messages[0]


def test_axis_dialog_independent_settings_apply_and_undo(window, monkeypatch):
    before = window.document.to_dict()
    dialog = AxisDialog(window.document)
    dialog.mode.setCurrentText("four-quadrant")
    dialog.axis_fields["x_axis"]["minimum"].setValue(-3)
    dialog.axis_fields["x_axis"]["maximum"].setValue(9)
    dialog.axis_fields["y_axis"]["minimum"].setValue(-2)
    dialog.axis_fields["y_axis"]["maximum"].setValue(6)
    dialog.axis_fields["x_axis"]["numbers"].setChecked(False)
    dialog.axis_fields["y_axis"]["arrowheads"].setCurrentText("both")
    dialog.fields["origin_visible"].setChecked(False)
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert window.document.to_dict() == before
    monkeypatch.setattr(dialog, "exec", lambda: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(window_module, "AxisDialog", lambda *args: dialog)
    window.configure_axes()
    assert window.document.bounds == (-3, 9, -2, 6)
    assert window.document.mode == "four-quadrant"
    assert not window.document.x_axis.numbers and window.document.y_axis.arrowheads == "both"
    assert not window.document.origin_visible
    window.undo()
    assert window.document.to_dict() == before
    window.redo()
    assert window.document.bounds == (-3, 9, -2, 6)


def test_linked_dataset_edit_updates_regression_and_undo(window, monkeypatch):
    rows = [[1, 3], [2, 5], [3, 7]]
    source = GraphObject("scatter", name="Observations", data={"rows": rows})
    window.mutate("Import data", lambda: window.document.objects.append(source))
    select(window, source)
    window.add_regression()
    regression = next(o for o in window.document.objects if o.kind == "regression")
    assert window.canvas.renderer().object_segments(regression)[0][-1] == pytest.approx((10, 21))
    class AcceptedDataDialog:
        def __init__(self, obj, parent):
            self.name = QLineEdit("Edited observations")
            self.label = QLineEdit("D")
            self.regression = QCheckBox()
            self.rows = [[1, 5], [2, 8], [3, 11]]
        def exec(self):
            self.regression.setChecked(True)
            return QDialog.DialogCode.Accepted
    monkeypatch.setattr(window_module, "DataDialog", AcceptedDataDialog)
    window.edit_data_id(regression.id)
    source_now = window.find(source.id)
    assert source_now.data["rows"] == [[1, 5], [2, 8], [3, 11]]
    assert source_now.name == "Edited observations" and source_now.label == "D"
    assert window.canvas.renderer().object_segments(window.find(regression.id))[0][-1] == pytest.approx((10, 32))
    window.undo()
    assert window.find(source.id).data["rows"] == rows
    assert window.canvas.renderer().object_segments(window.find(regression.id))[0][-1] == pytest.approx((10, 21))


def test_copy_paste_preserves_links_and_is_one_undo_step(window, qapp):
    source = GraphObject("scatter", name="Sample", data={"rows": [[1, 3], [2, 5]]})
    regression = window.regression_object(source)
    window.mutate("Add linked dataset", lambda: window.document.objects.extend([source, regression]))
    select(window, source, regression)
    qapp.processEvents()
    window.copy()
    assert '"graphite_clipboard": 1' in QApplication.clipboard().text()
    window.paste()
    assert len(window.document.objects) == 4
    copies = window.selected_objects()
    copied_source = next(o for o in copies if o.kind == "scatter")
    copied_regression = next(o for o in copies if o.kind == "regression")
    assert copied_source.id != source.id
    assert copied_regression.data["source_id"] == copied_source.id
    assert copied_source.data["rows"] == [[1.5, 3.5], [2.5, 5.5]]
    window.undo()
    assert len(window.document.objects) == 2
    window.redo()
    assert len(window.document.objects) == 4


def test_visibility_naming_grouping_and_delete_restore(window):
    point = GraphObject("point", [[2, 3]], name="P", label="E")
    line = GraphObject("line", [[1, 1], [4, 4]], name="Supply", label="S")
    window.mutate("Create geometry", lambda: window.document.objects.extend([point, line]))
    select(window, point, line)
    window.group()
    assert point.group and point.group == line.group
    window.toggle_visibility()
    assert not point.visible and not line.visible
    window.undo()
    point, line = window.find(point.id), window.find(line.id)
    assert point.visible and line.visible
    select(window, point, line)
    window.delete_selection()
    assert not window.document.objects
    window.undo()
    assert len(window.document.objects) == 2
    assert window.find(point.id).label == "E"


def test_dirty_warning_cancel_discard_and_save_result(window, monkeypatch):
    assert window.confirm_discard()
    window.mutate("Change title", lambda: setattr(window.document, "title", "Changed"))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
    assert not window.confirm_discard()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Discard)
    assert window.confirm_discard()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(window, "save", lambda: False)
    assert not window.confirm_discard()
    monkeypatch.setattr(window, "save", lambda: True)
    assert window.confirm_discard()


def test_save_reopen_and_corrupt_file_error_preserves_document(window, tmp_path, monkeypatch):
    obj = GraphObject("function", name="Demand", data={"expression": "8-.5x", "domain_min": 0, "domain_max": 10})
    window.mutate("Plot demand", lambda: window.document.objects.append(obj))
    window.path = tmp_path / "market.graphite"
    assert window.save() and not window.history.is_dirty()
    saved = window.document.to_dict()
    window.replace_document(Document())
    assert window.open_path(tmp_path / "market.graphite")
    assert window.document.to_dict() == saved
    broken = tmp_path / "broken.graphite"
    broken.write_text('{"not": "a project"}', encoding="utf-8")
    errors = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: errors.append(args[-1]))
    assert not window.open_path(broken)
    assert window.document.to_dict() == saved
    assert errors and "GraphCad" in errors[0]


def test_function_entry_and_text_focus_do_not_trigger_drawing_shortcuts(window, qapp):
    window.expression_input.setFocus()
    QTest.keyClicks(window.expression_input, "cos(x)")
    assert window.canvas.tool == "select"
    window.expression_input.selectAll()
    window.copy()
    assert QApplication.clipboard().text() == "cos(x)"
    window.quick_function()
    functions = [o for o in window.document.objects if o.kind == "function"]
    assert len(functions) == 1 and functions[0].data["expression"] == "cos(x)"


def test_table_paste_and_expression_errors_are_visible(qapp):
    dialog = DataDialog()
    QApplication.clipboard().setText("X\tY\n1\t3\n2\t5\n3\t7")
    dialog.paste_table()
    assert dialog.read_rows() == [[1, 3], [2, 5], [3, 7]]
    assert "R²: 1" in dialog.stats.text()
    dialog.table.setItem(1, 0, QTableWidgetItem("broken"))
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "Row 2" in dialog.error.text()
    function = FunctionDialog()
    function.expression.setText("sqrt(")
    function.accept()
    assert function.result() != QDialog.DialogCode.Accepted
    assert function.error.text()
    dialog.close()
    function.close()


def test_dataset_table_rejects_values_outside_document_coordinate_limit(qapp):
    dialog = DataDialog()
    dialog.fill_rows([[1, 2], [1e12+1, 3]])
    with pytest.raises(ValueError, match="Row 2.*1e12"):
        dialog.read_rows()
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "Row 2" in dialog.error.text()
    dialog.close()


def test_function_inspector_label_visibility_preserves_expression(window):
    function = GraphObject("function", name="Demand", data={"expression": "8-.5x", "domain_min": 1, "domain_max": 9})
    window.mutate("Plot function", lambda: window.document.objects.append(function))
    select(window, function)
    window.inspector.data_fields["label_visible"].setChecked(False)
    window.inspector.apply()
    edited = window.find(function.id)
    assert edited.data["expression"] == "8-.5x"
    assert edited.data["domain_min"] == 1 and edited.data["domain_max"] == 9
    assert edited.data["label_visible"] is False
