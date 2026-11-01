"""Native editors for axes, mathematical expressions, and linked datasets."""
from copy import deepcopy
import math
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QHeaderView,
)
from .model import Document
from .expressions import Expression
from .data import parse_csv, linear_regression, validate_rows, pearson_correlation, format_correlation


class PrecisionSpinBox(QDoubleSpinBox):
    """Keep full double precision without showing hundreds of trailing zeroes."""
    def textFromValue(self, value):
        if self.decimals() < 17:
            return f'{value:.{self.decimals()}f}'
        return repr(float(value))

    def valueFromText(self, text):
        try:
            return float(text.strip())
        except ValueError:
            return self.value()

    def validate(self, text, position):
        if text.strip() in ('', '-', '+', '.', '-.', '+.') or text.lower().endswith(('e', 'e+', 'e-')):
            return QValidator.State.Intermediate, text, position
        try:
            value = float(text)
            state = QValidator.State.Acceptable if math.isfinite(value) and self.minimum() <= value <= self.maximum() else QValidator.State.Intermediate
        except ValueError:
            state = QValidator.State.Invalid
        return state, text, position


def number(value=0, minimum=-1e12, maximum=1e12, decimals=323):
    widget = PrecisionSpinBox()
    widget.setRange(minimum, maximum)
    widget.setDecimals(decimals)
    widget.setValue(value)
    widget.setKeyboardTracking(False)
    widget.setSingleStep(.5)
    return widget


def combo(values, value):
    widget = QComboBox()
    widget.addItems(values)
    widget.setCurrentText(str(value))
    return widget


def checked(value, text=''):
    widget = QCheckBox(text)
    widget.setChecked(bool(value))
    return widget


def buttons(dialog, layout):
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    box.accepted.connect(dialog.accept)
    box.rejected.connect(dialog.reject)
    layout.addWidget(box)
    return box


class AxisDialog(QDialog):
    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Coordinate system')
        self.resize(510, 680)
        self.result_document = document.clone()
        self.axis_fields = {}
        layout = QVBoxLayout(self)
        self.mode = combo(['positive', 'four-quadrant', 'custom'], document.mode)
        layout.addWidget(QLabel('Coordinate mode'))
        layout.addWidget(self.mode)
        self.mode.currentTextChanged.connect(self.change_mode)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        for key, axis in [('x_axis', document.x_axis), ('y_axis', document.y_axis)]:
            area = QScrollArea()
            area.setWidgetResizable(True)
            page = QWidget()
            form = QFormLayout(page)
            fields = {
                'title': QLineEdit(axis.title),
                'minimum': number(axis.minimum), 'maximum': number(axis.maximum),
                'major': number(axis.major, 0, 1e12), 'minor': number(axis.minor, 0, 1e12),
                'position': number(axis.position),
                'visible': checked(axis.visible), 'positive': checked(axis.positive),
                'negative': checked(axis.negative), 'ticks': checked(axis.ticks),
                'numbers': checked(axis.numbers), 'title_visible': checked(axis.title_visible),
                'arrowheads': combo(['none', 'positive', 'negative', 'both'], axis.arrowheads),
                'label_side': combo(['below', 'above', 'left', 'right'], axis.label_side),
                'number_format': combo(['auto', 'decimal', 'scientific', 'pi'], axis.number_format),
                'decimals': number(axis.decimals, 0, 10, 0),
                'width': number(axis.width, .2, 20, 1),
                'line_style': combo(['solid', 'dashed', 'dotted', 'dash-dot'], axis.line_style),
            }
            labels = {'major':'Major interval (0 = automatic)', 'minor':'Minor interval (0 = off)',
                      'position':'Crosses other axis at', 'positive':'Show positive direction',
                      'negative':'Show negative direction', 'numbers':'Numeric labels',
                      'title_visible':'Show title', 'label_side':'Label placement'}
            for name, widget in fields.items():
                form.addRow(labels.get(name, name.replace('_',' ').capitalize()), widget)
            area.setWidget(page)
            tabs.addTab(area, 'Horizontal · X' if key == 'x_axis' else 'Vertical · Y')
            self.axis_fields[key] = fields
        general = QWidget()
        form = QFormLayout(general)
        self.fields = {}
        for key, label in [('grid_major','Major grid'),('grid_minor','Minor grid'),
                           ('origin_visible','Origin marker'),('origin_label','Origin label'),
                           ('labels_visible','Object labels'),('snap_grid','Snap to grid'),
                           ('snap_points','Snap to points and endpoints'),('snap_intersections','Snap to line intersections'),
                           ('radians','Trigonometry in radians')]:
            self.fields[key] = checked(getattr(document, key))
            form.addRow(label, self.fields[key])
        self.fields['snap_interval'] = number(document.snap_interval, 1e-10, 1e12)
        form.addRow('Snapping interval', self.fields['snap_interval'])
        tabs.addTab(general, 'Grid & snapping')
        hint = QLabel('Ranges define the saved graph and full-document export.\nPanning and zooming only change your working view.')
        hint.setWordWrap(True)
        hint.setObjectName('muted')
        layout.addWidget(hint)
        buttons(self, layout)

    def change_mode(self, mode):
        if not self.axis_fields or mode == 'custom':
            return
        for fields in self.axis_fields.values():
            fields['minimum'].setValue(0 if mode == 'positive' else -10)
            fields['maximum'].setValue(10)
            fields['negative'].setChecked(mode != 'positive')

    def accept(self):
        doc = self.result_document
        try:
            for key, fields in self.axis_fields.items():
                axis = getattr(doc, key)
                for name, widget in fields.items():
                    value = widget.isChecked() if isinstance(widget, QCheckBox) else widget.currentText() if isinstance(widget, QComboBox) else widget.text() if isinstance(widget, QLineEdit) else widget.value()
                    if name == 'decimals': value = int(value)
                    setattr(axis, name, value)
                if axis.maximum <= axis.minimum:
                    raise ValueError('Each maximum must be greater than its minimum.')
                if axis.maximum - axis.minimum < 1e-8:
                    raise ValueError('Axis ranges must span at least 0.00000001.')
            for key, widget in self.fields.items():
                setattr(doc, key, widget.isChecked() if isinstance(widget,QCheckBox) else widget.value())
            doc.mode = self.mode.currentText()
            Document.from_dict(doc.to_dict())
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, 'Invalid coordinate system', str(exc))
            return
        super().accept()


class FunctionDialog(QDialog):
    def __init__(self, obj=None, radians=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Mathematical function')
        self.resize(470, 300)
        self.radians = radians
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.expression = QLineEdit(obj.data.get('expression','') if obj else 'y = -0.5x + 8')
        self.name = QLineEdit(obj.name if obj else 'Function')
        self.label = QLineEdit(obj.label if obj else '')
        self.low = QLineEdit('' if obj is None or obj.data.get('domain_min') is None else str(obj.data['domain_min']))
        self.high = QLineEdit('' if obj is None or obj.data.get('domain_max') is None else str(obj.data['domain_max']))
        form.addRow('Expression', self.expression)
        form.addRow('Object name', self.name)
        form.addRow('Displayed label', self.label)
        form.addRow('Domain minimum (optional)', self.low)
        form.addRow('Domain maximum (optional)', self.high)
        layout.addLayout(form)
        hint = QLabel('Use x, π, e, + − * / ^, sqrt, abs, exp, ln, log, sin, cos, tan, asin, acos, atan.\nImplicit multiplication: 2x, 3(x + 1). Trigonometry: ' + ('radians.' if radians else 'degrees.'))
        hint.setWordWrap(True)
        hint.setObjectName('muted')
        layout.addWidget(hint)
        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons(self,layout)
        self.expression.selectAll()

    def accept(self):
        try:
            Expression(self.expression.text(), radians=self.radians)
            lo = float(self.low.text()) if self.low.text().strip() else None
            hi = float(self.high.text()) if self.high.text().strip() else None
            if any(v is not None and not math.isfinite(v) for v in (lo,hi)):
                raise ValueError('Domain bounds must be finite.')
            if lo is not None and hi is not None and lo >= hi:
                raise ValueError('The domain maximum must exceed its minimum.')
            self.values = dict(expression=self.expression.text().strip(), domain_min=lo, domain_max=hi)
        except (ValueError,TypeError,SyntaxError) as exc:
            self.error.setText(str(exc))
            return
        super().accept()


class DataDialog(QDialog):
    def __init__(self, obj=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Dataset · scatter & regression')
        self.resize(560,650)
        layout=QVBoxLayout(self)
        form=QFormLayout()
        self.name=QLineEdit(obj.name if obj else 'Dataset')
        self.label=QLineEdit(obj.label if obj else '')
        form.addRow('Dataset name',self.name)
        form.addRow('Displayed label',self.label)
        layout.addLayout(form)
        bar=QHBoxLayout()
        for label,slot in [('Add row',self.add_row),('Delete rows',self.delete_rows),('Paste table',self.paste_table),('Import CSV…',self.import_csv)]:
            b=QPushButton(label);b.clicked.connect(slot);bar.addWidget(b)
        layout.addLayout(bar)
        self.table=QTableWidget(0,2)
        self.table.setHorizontalHeaderLabels(['X','Y'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        self.regression=checked(False,'Include linked least-squares regression line')
        layout.addWidget(self.regression)
        self.stats=QLabel()
        self.stats.setWordWrap(True)
        self.stats.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.stats)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setObjectName('error');layout.addWidget(self.error)
        self.table.cellChanged.connect(self.update_stats)
        self.fill_rows(obj.data.get('rows',[]) if obj else [[1,2.1],[2,3.8],[3,6.2],[4,7.9],[5,10.2]])
        buttons(self,layout)

    def fill_rows(self,rows):
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,v in enumerate(row): self.table.setItem(i,j,QTableWidgetItem(str(v)))
        self.table.blockSignals(False)
        self.update_stats()

    def add_row(self):
        self.table.insertRow(self.table.rowCount())
        self.table.setCurrentCell(self.table.rowCount()-1,0)
        self.table.editItem(self.table.item(self.table.rowCount()-1,0)) if self.table.item(self.table.rowCount()-1,0) else None

    def delete_rows(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()},reverse=True): self.table.removeRow(row)
        self.update_stats()

    def read_rows(self):
        rows=[]
        for i in range(self.table.rowCount()):
            values=[self.table.item(i,j).text().strip() if self.table.item(i,j) else '' for j in range(2)]
            if not any(values): continue
            try: row=[float(v) for v in values]
            except ValueError: raise ValueError(f'Row {i+1}: enter a numeric X and Y value.')
            if not all(math.isfinite(v) for v in row): raise ValueError(f'Row {i+1}: values must be finite.')
            rows.append(row)
        if not rows: raise ValueError('Enter at least one complete data row.')
        return validate_rows(rows)

    def update_stats(self):
        try:
            rows=self.read_rows()
            fit=linear_regression(rows)
            self.stats.setText(f'{len(rows)} observations  ·  {fit.equation}\nSlope: {fit.slope:.8g}   Intercept: {fit.intercept:.8g}   R²: {fit.r_squared:.8g}   r: {format_correlation(fit.r)}')
            self.error.clear()
        except ValueError as exc:
            self.stats.setText('Regression unavailable · r: '+format_correlation(pearson_correlation(rows) if 'rows' in locals() else None))
            self.error.setText(str(exc))

    def paste_table(self):
        try:
            text=QApplication.clipboard().text()
            if '\t' in text: text=text.replace('\t',',')
            rows=parse_csv(text)
            self.fill_rows(rows)
        except ValueError as exc: self.error.setText(str(exc))

    def import_csv(self):
        path,_=QFileDialog.getOpenFileName(self,'Import dataset','','CSV data (*.csv *.tsv *.txt);;All files (*)')
        if not path:return
        try:
            source=Path(path)
            if source.stat().st_size>32*1024*1024:raise ValueError('CSV file exceeds the 32 MB limit.')
            text=source.read_text(encoding='utf-8-sig')
            if '\t' in text: text=text.replace('\t',',')
            self.fill_rows(parse_csv(text))
        except (OSError,UnicodeError,ValueError) as exc:self.error.setText(str(exc))

    def accept(self):
        try:
            self.rows=self.read_rows()
            if self.regression.isChecked(): linear_regression(self.rows)
        except ValueError as exc:
            self.error.setText(str(exc));return
        super().accept()


class PerpendicularDialog(QDialog):
    """Choose persisted object references rather than copying target coordinates."""
    def __init__(self,document,selected=(),parent=None):
        super().__init__(parent)
        from .geometry import line_geometry
        self.setWindowTitle('Perpendicular construction')
        self.resize(470,240)
        layout=QVBoxLayout(self);form=QFormLayout()
        self.source=QComboBox();self.target=QComboBox()
        for obj in document.objects:
            if obj.kind=='point' and 'perpendicular' not in obj.data:
                self.source.addItem(obj.name or 'Point',obj.id)
                if obj.id in selected:self.source.setCurrentIndex(self.source.count()-1)
        self.target.addItem('X axis','axis:x');self.target.addItem('Y axis','axis:y')
        for obj in document.objects:
            if line_geometry(obj) is not None and 'perpendicular' not in obj.data:
                self.target.addItem(obj.name or obj.kind,obj.id)
                if obj.id in selected:self.target.setCurrentIndex(self.target.count()-1)
        form.addRow('Source point',self.source);form.addRow('Target line / axis',self.target)
        layout.addLayout(form)
        hint=QLabel('Creates a linked foot point and perpendicular segment. For finite segments the supporting line is used, so the foot may lie beyond an endpoint. Edit the source or target to update the construction.')
        hint.setWordWrap(True);hint.setObjectName('muted');layout.addWidget(hint)
        self.error=QLabel();self.error.setObjectName('error');layout.addWidget(self.error)
        buttons(self,layout)
    def accept(self):
        if self.source.currentData() is None:
            self.error.setText('Create a source point first.');return
        self.source_id=self.source.currentData()
        target=self.target.currentData()
        self.axis=target.split(':')[1] if target.startswith('axis:') else None
        self.target_id=None if self.axis else target
        super().accept()


class PrecisionDialog(QDialog):
    MODES=[('Free angle','free'),('Horizontal','horizontal'),('Vertical','vertical'),
           ('Parallel to reference','parallel'),('Perpendicular to reference','perpendicular'),
           ('Snap to angle increment','angular'),('Custom angle','angle')]
    def __init__(self,document,canvas,parent=None):
        super().__init__(parent)
        from .geometry import line_geometry
        self.setWindowTitle('Precision · snapping and orientation');self.resize(480,450)
        layout=QVBoxLayout(self);form=QFormLayout()
        self.snap_lines=checked(document.snap_lines)
        self.tolerance=number(document.snap_tolerance_pixels,1,50,1)
        self.mode=QComboBox()
        for label,value in self.MODES:self.mode.addItem(label,value)
        self.mode.setCurrentIndex(max(0,self.mode.findData(canvas.constraint_mode)))
        self.angle=number(canvas.constraint_angle,-360,360,6)
        self.increment=number(canvas.angle_increment,.1,180,6)
        self.reference=QComboBox();self.reference.addItem('Choose a reference line',None)
        for obj in document.objects:
            if line_geometry(obj) is not None:
                self.reference.addItem(obj.name or obj.kind,obj.id)
                if obj.id==canvas.constraint_reference_id:self.reference.setCurrentIndex(self.reference.count()-1)
        self.apply_selected=checked(False,'Apply orientation to selected segments now')
        for label,w in [('Snap points onto lines',self.snap_lines),('Snap tolerance (screen pixels)',self.tolerance),
                        ('Drawing orientation',self.mode),('Reference geometry',self.reference),
                        ('Angle increment (degrees)',self.increment),('Custom angle (degrees)',self.angle)]:form.addRow(label,w)
        layout.addLayout(form);layout.addWidget(self.apply_selected)
        hint=QLabel('Constraints apply to segments, construction lines and arrows, including endpoint handles. Angles are measured counterclockwise from +X in document coordinates. Use 45° or 90° increments, or enter another value.')
        hint.setWordWrap(True);hint.setObjectName('muted');layout.addWidget(hint)
        self.error=QLabel();self.error.setObjectName('error');layout.addWidget(self.error)
        self.mode.currentIndexChanged.connect(self.update_fields);self.update_fields()
        buttons(self,layout)
    def update_fields(self):
        mode=self.mode.currentData()
        self.reference.setEnabled(mode in ('parallel','perpendicular'))
        self.increment.setEnabled(mode=='angular');self.angle.setEnabled(mode=='angle')
    def accept(self):
        if self.mode.currentData() in ('parallel','perpendicular') and not self.reference.currentData():
            self.error.setText('Choose a non-degenerate reference line.');return
        super().accept()
