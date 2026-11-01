"""Main native desktop window and document-level commands."""
from copy import deepcopy
from pathlib import Path
import json
import math
import uuid
from PySide6.QtCore import Qt,QSettings,QSize,QTimer
from PySide6.QtGui import QAction,QActionGroup,QKeySequence,QColor,QPainter,QPen,QIcon,QPixmap,QPalette
from PySide6.QtWidgets import (
    QApplication,QMainWindow,QDockWidget,QWidget,QVBoxLayout,QHBoxLayout,
    QLabel,QLineEdit,QPushButton,QTreeWidget,QTreeWidgetItem,QToolBar,
    QFileDialog,QMessageBox,QInputDialog,QDialog,QDialogButtonBox,QCheckBox,
    QComboBox,QSpinBox,QDoubleSpinBox,QFormLayout,QAbstractItemView,QMenu,
    QTextEdit,QTableWidget,QHeaderView,QSplitter,QToolButton,QSizePolicy,
)
from .model import Document,GraphObject
from .history import History
from .canvas import GraphCanvas
from .render import Renderer
from .dialogs import AxisDialog,FunctionDialog,DataDialog,PrecisionDialog,PerpendicularDialog,number,checked,combo
from .inspector import Inspector
from .templates import template_names,make_template
from .data import linear_regression,format_correlation
from .expressions import Expression

ORIENTATION_LABELS=dict((value,label) for label,value in PrecisionDialog.MODES)

TOOLS=[('select','Select','V'),('pan','Pan','H'),('point','Point','P'),
       ('line','Segment','L'),('polyline','Polyline',''),('curve','Curve','C'),
       ('arrow','Arrow','A'),('text','Text','T')]
KIND_SYMBOL={'point':'●','line':'╱','segment':'╱','infinite_line':'↔','horizontal':'—','vertical':'│',
             'polyline':'⌁','curve':'∿','arrow':'↗','text':'T','function':'ƒ','scatter':'⁙','regression':'ŷ','construction':'┄'}


def tool_icon(kind):
    pix=QPixmap(28,28);pix.fill(Qt.GlobalColor.transparent)
    p=QPainter(pix);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QApplication.palette().color(QPalette.ColorRole.WindowText),1.7));p.setBrush(QApplication.palette().color(QPalette.ColorRole.WindowText))
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPolygonF,QPainterPath
    if kind=='select':
        p.drawPolygon(QPolygonF([QPointF(7,4),QPointF(9,23),QPointF(14,17),QPointF(22,16)]))
    elif kind=='point':p.drawEllipse(QPointF(14,14),3.7,3.7)
    elif kind=='line':
        p.drawLine(5,23,23,5);p.setBrush(QColor('white'));p.drawRect(3,21,4,4);p.drawRect(21,3,4,4)
    elif kind=='arrow':
        p.drawLine(5,23,23,5);p.drawPolygon(QPolygonF([QPointF(23,5),QPointF(13,7),QPointF(21,15)]))
    elif kind=='curve':
        path=QPainterPath();path.moveTo(4,23);path.cubicTo(8,3,17,26,24,4);p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(path)
    elif kind=='polyline':
        p.setBrush(Qt.BrushStyle.NoBrush);p.drawPolyline(QPolygonF([QPointF(4,23),QPointF(10,8),QPointF(17,19),QPointF(24,4)]))
    elif kind=='export':
        p.setBrush(Qt.BrushStyle.NoBrush);p.drawLine(5,14,5,23);p.drawLine(5,23,23,23);p.drawLine(23,23,23,14)
        p.drawLine(14,18,14,4);p.drawLine(14,4,9,9);p.drawLine(14,4,19,9)
    elif kind=='pan':
        p.drawLine(14,3,14,25);p.drawLine(3,14,25,14);p.drawLine(14,3,10,7);p.drawLine(14,3,18,7);p.drawLine(3,14,7,10);p.drawLine(3,14,7,18)
    else:
        p.setFont(QApplication.font());p.drawText(pix.rect(),Qt.AlignmentFlag.AlignCenter,{'text':'T','function':'ƒ(x)','scatter':'⁙','regression':'ŷ'}.get(kind,kind))
    p.end();return QIcon(pix)


class Preview(QWidget):
    def __init__(self,dialog):
        super().__init__();self.dialog=dialog;self.setMinimumHeight(220)
    def paintEvent(self,event):
        from PySide6.QtCore import QRectF
        p=QPainter(self)
        try:
            options=self.dialog.options()
            doc=self.dialog.document
            Renderer(doc,QRectF(self.rect()),options.bounds).draw(p,axes=options.axes,grid=options.grid,labels=options.labels)
        finally:p.end()


class ExportDialog(QDialog):
    def __init__(self,document,bounds,parent=None):
        super().__init__(parent)
        self.document=document;self.view_bounds=bounds
        self.setWindowTitle('Export graph');self.resize(560,660)
        layout=QVBoxLayout(self);form=QFormLayout()
        self.format=combo(['PNG','PDF','SVG','DXF','DWG'],'PNG')
        self.width=QSpinBox();self.width.setRange(64,16000);self.width.setValue(1920)
        self.height=QSpinBox();self.height.setRange(64,16000);self.height.setValue(1080)
        self.keep_ratio=checked(True,'Keep aspect ratio');self._ratio=1920/1080;self._resizing=False
        self.width.valueChanged.connect(lambda:self.resize_output(True))
        self.height.valueChanged.connect(lambda:self.resize_output(False))
        self.keep_ratio.toggled.connect(lambda value:setattr(self,'_ratio',self.width.value()/self.height.value()))
        self.transparent=checked(False)
        self.axes=checked(True);self.grid=checked(True);self.labels=checked(True)
        self.margin=QSpinBox();self.margin.setRange(0,500);self.margin.setValue(30)
        self.scope=combo(['Saved graph ranges','Current viewport','Custom coordinate region'],'Saved graph ranges')
        self.region=[number(v) for v in bounds]
        self.page=combo(['A4','Letter','Custom'],'A4');self.landscape=checked(True)
        self.page_width=number(297,25,2000,1);self.page_height=number(210,25,2000,1)
        for label,w in [('Format',self.format),('Width (pixels)',self.width),('Height (pixels)',self.height),
                        ('Aspect ratio',self.keep_ratio),('Transparent PNG / SVG',self.transparent),('Include axes',self.axes),('Include grid',self.grid),('Include labels',self.labels),
                        ('Extra margin (logical pixels)',self.margin),('Export region',self.scope)]:form.addRow(label,w)
        region=QWidget();reg=QHBoxLayout(region);reg.setContentsMargins(0,0,0,0)
        for w in self.region:reg.addWidget(w)
        form.addRow('Region X min/max, Y min/max',region)
        form.addRow('PDF page size',self.page);form.addRow('Landscape PDF',self.landscape)
        custom=QWidget();row=QHBoxLayout(custom);row.setContentsMargins(0,0,0,0);row.addWidget(self.page_width);row.addWidget(self.page_height)
        form.addRow('Custom PDF size (mm)',custom)
        layout.addLayout(form)
        self.preview=Preview(self);layout.addWidget(self.preview)
        self.note=QLabel('DWG requires a separately installed ODA File Converter. Curves are sampled in CAD exports.')
        self.note.setWordWrap(True);self.note.setObjectName('muted');layout.addWidget(self.note)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept);box.rejected.connect(self.reject);layout.addWidget(box)
        for w in (self.axes,self.grid,self.labels):w.toggled.connect(self.preview.update)
        self.scope.currentTextChanged.connect(self.preview.update)
        for w in self.region:w.valueChanged.connect(self.preview.update)
    def resize_output(self,width_changed):
        if self._resizing:return
        if self.keep_ratio.isChecked():
            self._resizing=True
            if width_changed:
                target=round(self.width.value()/self._ratio);self.height.setValue(target)
                if self.height.value()!=target:self.width.setValue(round(self.height.value()*self._ratio))
            else:
                target=round(self.height.value()*self._ratio);self.width.setValue(target)
                if self.width.value()!=target:self.height.setValue(round(self.width.value()/self._ratio))
            self._resizing=False
        if hasattr(self,'preview'):self.preview.update()

    def options(self):
        from .export import ExportOptions
        scope=self.scope.currentIndex()
        bounds=None if scope==0 else self.view_bounds if scope==1 else tuple(w.value() for w in self.region)
        if bounds and (bounds[0]>=bounds[1] or bounds[2]>=bounds[3]):bounds=self.view_bounds
        return ExportOptions(width=self.width.value(),height=self.height.value(),transparent=self.transparent.isChecked(),axes=self.axes.isChecked(),grid=self.grid.isChecked(),labels=self.labels.isChecked(),margin=self.margin.value(),bounds=bounds,page_size=self.page.currentText(),landscape=self.landscape.isChecked(),custom_width_mm=self.page_width.value(),custom_height_mm=self.page_height.value())
    def accept(self):
        if self.scope.currentIndex()==2:
            vals=[w.value() for w in self.region]
            if vals[0]>=vals[1] or vals[2]>=vals[3]:
                QMessageBox.warning(self,'Invalid region','Region maxima must be greater than minima.');return
        if self.width.value()*self.height.value()>64000000:
            QMessageBox.warning(self,'Image too large','Choose dimensions with at most 64 million pixels.');return
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1440,920);self.setMinimumSize(1000,680)
        self.settings=QSettings()
        if QApplication.applicationName()=='GraphCad' and not self.settings.value('legacySettingsMigrated',False,type=bool):
            legacy=QSettings('Graphite','Graphite')
            for key in ('recent','windowGeometry'):
                if not self.settings.contains(key) and legacy.contains(key):self.settings.setValue(key,legacy.value(key))
            self.settings.setValue('legacySettingsMigrated',True)
        self.path=None;self.clipboard_objects=[];self._refreshing=False
        self.document=make_template('Supply and demand')
        self.history=History(self.document)
        self.actions={}
        self.canvas=GraphCanvas(self.document)
        self.setCentralWidget(self.canvas)
        self.canvas.transactionCompleted.connect(self.record_canvas)
        self.canvas.selectionChanged.connect(self.selection_changed)
        self.canvas.cursorMoved.connect(lambda x,y:self.coordinates.setText(f'X {x: .4f}    Y {y: .4f}'))
        self.canvas.message.connect(lambda s:self.statusBar().showMessage(s,6000))
        self.canvas.toolChanged.connect(self.tool_changed)
        self.create_actions();self.create_docks();self.create_menus();self.create_toolbars()
        self.coordinates=QLabel('X 0.0000    Y 0.0000');self.coordinates.setMinimumWidth(215)
        self.statusBar().addPermanentWidget(self.coordinates)
        self.tool_hint=QLabel('Select · drag handles to edit geometry');self.statusBar().addWidget(self.tool_hint)
        self.set_theme(self.settings.value('theme','light'))
        QApplication.instance().styleHints().colorSchemeChanged.connect(self.system_theme_changed)
        self.refresh()
        QTimer.singleShot(0,self.canvas.fit_view)

    def action(self,key,text,callback,shortcut=None,checkable=False):
        a=QAction(text,self);a.setCheckable(checkable);a.setToolTip(text.replace("&",""))
        if shortcut:a.setShortcut(shortcut)
        if callback:a.triggered.connect(lambda checked=False:callback())
        self.actions[key]=a;return a

    def create_actions(self):
        a=self.action
        for key,text,slot,shortcut in [
            ('new','New graph…',self.new_document,QKeySequence.StandardKey.New),
            ('open','Open…',self.open_document,QKeySequence.StandardKey.Open),
            ('save','Save',self.save,QKeySequence.StandardKey.Save),
            ('save_as','Save As…',self.save_as,QKeySequence.StandardKey.SaveAs),
            ('export','Export…',self.export_graph,'Ctrl+E'),
            ('undo','Undo',self.undo,QKeySequence.StandardKey.Undo),
            ('redo','Redo',self.redo,QKeySequence.StandardKey.Redo),
            ('copy','Copy',self.copy,QKeySequence.StandardKey.Copy),
            ('paste','Paste',self.paste,QKeySequence.StandardKey.Paste),
            ('duplicate','Duplicate',self.duplicate,'Ctrl+D'),
            ('delete','Delete',self.delete_selection,QKeySequence.StandardKey.Delete),
            ('all','Select all',self.select_all,QKeySequence.StandardKey.SelectAll),
            ('axes','Coordinate system…',self.configure_axes,None),
            ('function','Add function…',self.add_function,None),
            ('dataset','Scatter plot / dataset…',self.add_dataset,None),
            ('regression','Add linked regression',self.add_regression,None),
            ('edit_data','Edit selected dataset…',self.edit_selected_data,None),
            ('zoom_in','Zoom in',lambda:self.canvas.zoom(1.25),QKeySequence.StandardKey.ZoomIn),
            ('zoom_out','Zoom out',lambda:self.canvas.zoom(.8),QKeySequence.StandardKey.ZoomOut),
            ('fit','Fit graph',self.canvas.fit_view,'Ctrl+0'),
            ('group','Group',self.group,'Ctrl+G'),
            ('ungroup','Ungroup',self.ungroup,'Ctrl+Shift+G'),
            ('front','Bring to front',lambda:self.reorder(True),None),
            ('back','Send to back',lambda:self.reorder(False),None),
            ('lock','Lock / unlock',self.toggle_lock,None),
            ('hide','Hide / show',self.toggle_visibility,None),
            ('construction','Construction lines to axes',self.construction_lines,None),
            ('perpendicular','Perpendicular from point…',self.perpendicular_construction,None),
            ('precision','Precision and orientation…',self.configure_precision,None),
            ('detach','Detach linked construction',self.detach_construction,None),
            ('to_points','Convert scatter to points',self.scatter_to_points,None),
            ('intersection','Find function intersections…',self.intersections,None),
            ('save_template','Save as reusable template…',self.save_template,None),
            ('load_template','Open reusable template…',self.load_template,None),
            ('help','Quick guide',self.show_help,QKeySequence.StandardKey.HelpContents),
            ('about','About GraphCad',self.about,None),
            ('quit','Quit',self.close,QKeySequence.StandardKey.Quit),
        ]:a(key,text,slot,shortcut)
        self.tool_group=QActionGroup(self)
        for key,text,shortcut in TOOLS:
            action=a('tool_'+key,text,lambda k=key:self.canvas.set_tool(k),checkable=True)
            action.setIcon(tool_icon(key));action.setToolTip(text+(' ('+shortcut+')' if shortcut else ''))
            if shortcut:
                action.setShortcut(shortcut);action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut);self.canvas.addAction(action)
            self.tool_group.addAction(action)
        self.actions['tool_select'].setChecked(True)
        for key,label,attr in [('grid','Major grid','grid_major'),('minor_grid','Minor grid','grid_minor'),('snap','Snap to grid','snap_grid'),('snap_points','Snap to endpoints','snap_points'),('snap_lines','Snap points to lines','snap_lines')]:
            act=a(key,label,lambda k=attr:self.toggle_document(k),checkable=True)
            act.setChecked(getattr(self.document,attr))

    def create_docks(self):
        self.object_dock=QDockWidget('OBJECTS',self);self.object_dock.setObjectName('Objects')
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(0,0,0,0)
        self.object_tree=QTreeWidget();self.object_tree.setColumnCount(4)
        self.object_tree.setHeaderLabels(['Object','Show','Lock','Layer'])
        self.object_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.object_tree.setRootIsDecorated(False)
        self.object_tree.setColumnWidth(0,155);self.object_tree.setColumnWidth(1,45);self.object_tree.setColumnWidth(2,45);self.object_tree.setColumnWidth(3,70)
        self.object_tree.itemSelectionChanged.connect(self.tree_selection)
        self.object_tree.itemChanged.connect(self.tree_changed)
        self.object_tree.itemDoubleClicked.connect(self.edit_tree_object)
        self.object_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.object_tree.customContextMenuRequested.connect(self.tree_menu)
        layout.addWidget(self.object_tree)
        bar=QHBoxLayout();bar.setContentsMargins(8,5,8,8)
        for label,fn in [('↑',lambda:self.move_one(1)),('↓',lambda:self.move_one(-1)),('Delete',self.delete_selection)]:
            b=QPushButton(label);b.clicked.connect(fn);bar.addWidget(b)
        layout.addLayout(bar)
        self.object_dock.setWidget(page);self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,self.object_dock)
        self.inspector_dock=QDockWidget('PROPERTIES',self);self.inspector_dock.setObjectName('Properties')
        self.inspector=Inspector();self.inspector.applyRequested.connect(self.apply_properties);self.inspector.editDataRequested.connect(self.edit_data_id)
        self.inspector_dock.setWidget(self.inspector);self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.inspector_dock)
        self.resizeDocks([self.object_dock,self.inspector_dock],[300,290],Qt.Orientation.Horizontal)
        self.function_dock=QDockWidget('FUNCTION ENTRY',self);self.function_dock.setObjectName('Functions')
        page=QWidget();layout=QHBoxLayout(page)
        self.expression_input=QLineEdit();self.expression_input.setPlaceholderText('y = -0.5x + 8     ·     sin(x)     ·     x^2')
        self.expression_input.returnPressed.connect(self.quick_function)
        add=QPushButton('Plot function');add.setObjectName('primary');add.clicked.connect(self.quick_function)
        layout.addWidget(QLabel('ƒ(x)'));layout.addWidget(self.expression_input);layout.addWidget(add)
        self.function_dock.setWidget(page);self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,self.function_dock)

    def create_menus(self):
        menu=self.menuBar()
        def add_menu(title,keys):
            m=menu.addMenu(title)
            for key in keys:
                if key is None:m.addSeparator()
                else:m.addAction(self.actions[key])
            return m
        file=add_menu('&File',['new','open','save','save_as',None,'export',None,'save_template','load_template'])
        self.recent_menu=file.addMenu('Recent projects');self.populate_recent();file.addSeparator();file.addAction(self.actions['quit'])
        add_menu('&Edit',['undo','redo',None,'copy','paste','duplicate','delete','all'])
        view=add_menu('&View',['zoom_in','zoom_out','fit',None,'grid','minor_grid','snap','snap_points','snap_lines','precision'])
        theme_menu=view.addMenu('Interface theme')
        for mode in ('light','dark','system'):
            act=self.action('theme_'+mode,mode.title(),lambda m=mode:self.set_theme(m),checkable=True);theme_menu.addAction(act)
        visibility=view.addMenu('Elements')
        for key,label in [('origin_visible','Origin marker'),('origin_label','Origin label'),('labels_visible','Object labels')]:
            self.action('visible_'+key,label,lambda k=key:self.toggle_document(k),checkable=True)
            visibility.addAction(self.actions['visible_'+key])
        for kind,label in [('point','Points'),('line','Line segments'),('infinite_line','Infinite lines'),('polyline','Polylines'),('curve','Manual curves'),('function','Functions'),('arrow','Arrows'),('text','Text'),('construction','Construction lines'),('scatter','Scatter plots'),('regression','Regressions')]:
            act=self.action('type_'+kind,label,lambda k=kind:self.toggle_type(k),checkable=True);act.setChecked(True);visibility.addAction(act)
        graph=add_menu('&Graph',['axes',None,'function','dataset','regression','edit_data',None,'intersection'])
        templates=graph.addMenu('New from template')
        for name in template_names():templates.addAction(name,lambda n=name:self.new_from_template(n))
        insert=add_menu('&Insert',['tool_point','tool_line','tool_polyline','tool_curve','tool_arrow','tool_text'])
        for kind,label in [('infinite_line','Infinite line'),('horizontal','Horizontal line'),('vertical','Vertical line'),('construction','Dashed construction segment')]:
            insert.addAction(label,lambda k=kind:self.canvas.set_tool(k))
        add_menu('&Object',['front','back',None,'group','ungroup','lock','hide',None,'construction','perpendicular','detach','to_points'])
        tools=add_menu('&Tools',['tool_select','tool_pan',None,'axes','precision','snap','snap_points','snap_lines','perpendicular','intersection'])
        win=menu.addMenu('&Window')
        for dock in (self.object_dock,self.inspector_dock,self.function_dock):win.addAction(dock.toggleViewAction())
        add_menu('&Help',['help','about'])

    def create_toolbars(self):
        bar=QToolBar('Drawing tools',self);bar.setObjectName('DrawingTools');bar.setMovable(False);bar.setIconSize(QSize(24,24))
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon);self.addToolBar(bar)
        for kind,_,_ in TOOLS:bar.addAction(self.actions['tool_'+kind])
        bar.addSeparator()
        for key in ('function','dataset','regression'):
            self.actions[key].setIcon(tool_icon({'dataset':'scatter'}.get(key,key)));self.actions[key].setIconText({'function':'Function','dataset':'Scatter','regression':'Regression'}[key]);bar.addAction(self.actions[key])
        bar.addSeparator()
        for key in ('undo','redo','zoom_in','zoom_out','fit'):
            self.actions[key].setIconText({'undo':'Undo','redo':'Redo','zoom_in':'Zoom in','zoom_out':'Zoom out','fit':'Fit graph'}[key]);bar.addAction(self.actions[key])
        bar.addSeparator();self.actions['axes'].setIconText('Axes');bar.addAction(self.actions['axes'])
        spacer=QWidget();spacer.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred);bar.addWidget(spacer)
        self.export_button=QToolButton();self.export_button.setObjectName('exportButton');self.export_button.setDefaultAction(self.actions['export']);self.export_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.export_button.setAccessibleName('Export graph');self.export_button.setToolTip('Export graph · PNG, PDF, SVG, DXF or optional DWG (Ctrl/Cmd+E)');bar.addWidget(self.export_button)
        self.addToolBarBreak()
        options=QToolBar('Precision',self);options.setObjectName('Precision');options.setMovable(False);self.addToolBar(options)
        for key in ('grid','snap','snap_points','snap_lines'):options.addAction(self.actions[key])
        options.addSeparator();options.addAction(self.actions['precision'])
        self.constraint_label=QLabel('Free angle');self.constraint_label.setObjectName('muted');options.addWidget(self.constraint_label)
        if hasattr(self.canvas,'constraintChanged'):self.canvas.constraintChanged.connect(lambda *args:self.update_constraint_label())
        options.addSeparator()
        self.document_label=QLabel();self.document_label.setObjectName('muted');options.addWidget(self.document_label)
        spacer=QWidget();spacer.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred);options.addWidget(spacer)
        options.addWidget(QLabel('Theme '));self.theme_selector=combo(['Light','Dark','System'],'Light');self.theme_selector.setAccessibleName('Interface theme');self.theme_selector.setToolTip('Interface theme; document and export colors stay independent')
        self.theme_selector.currentTextChanged.connect(lambda text:self.set_theme(text.lower()));options.addWidget(self.theme_selector)

    def set_theme(self,mode):
        from .themes import apply_theme
        mode=mode if mode in ('light','dark','system') else 'light'
        apply_theme(QApplication.instance(),mode)
        self.settings.setValue('theme',mode);self.settings.sync()
        if hasattr(self,'theme_selector'):
            self.theme_selector.blockSignals(True);self.theme_selector.setCurrentText(mode.title());self.theme_selector.blockSignals(False)
        for value in ('light','dark','system'):
            if 'theme_'+value in self.actions:self.actions['theme_'+value].setChecked(mode==value)
        for kind,_,_ in TOOLS:self.actions['tool_'+kind].setIcon(tool_icon(kind))
        for key in ('function','dataset','regression'):self.actions[key].setIcon(tool_icon({'dataset':'scatter'}.get(key,key)))
        icon=tool_icon('export')
        # Match the accent button's white foreground without changing document colors.
        pix=icon.pixmap(28,28);p=QPainter(pix);p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn);p.fillRect(pix.rect(),QColor('white'));p.end()
        self.actions['export'].setIcon(QIcon(pix));self.actions['export'].setIconText('Export')

    def system_theme_changed(self,*args):
        if self.settings.value('theme','light')=='system':self.set_theme('system')

    def update_constraint_label(self):
        if not hasattr(self,'constraint_label'):return
        labels=ORIENTATION_LABELS
        mode=self.canvas.constraint_mode
        text=labels.get(mode,mode)
        if mode=='angular':text+=f' · {self.canvas.angle_increment:g}°'
        elif mode=='angle':text+=f' · {self.canvas.constraint_angle:g}°'
        elif mode in ('parallel','perpendicular'):
            ref=self.find(self.canvas.constraint_reference_id)
            text+=' · '+(ref.name if ref else 'reference unavailable')
        self.constraint_label.setText(text)

    def configure_precision(self):
        from .geometry import constrain_endpoint,line_geometry
        dialog=PrecisionDialog(self.document,self.canvas,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        mode=dialog.mode.currentData();refid=dialog.reference.currentData()
        try:self.canvas.set_constraint(mode,dialog.angle.value(),dialog.increment.value(),refid)
        except ValueError as exc:QMessageBox.warning(self,'Orientation unavailable',str(exc));return
        def change():
            self.document.snap_lines=dialog.snap_lines.isChecked();self.document.snap_tolerance_pixels=dialog.tolerance.value()
            if dialog.apply_selected.isChecked():
                ref=self.find(refid);reference=line_geometry(ref)[:2] if ref else None
                for obj in self.selected_objects():
                    if obj.id==refid or obj.locked or obj.kind not in ('line','segment','construction','arrow','horizontal','vertical'):continue
                    obj.points[1]=list(constrain_endpoint(obj.points[0],obj.points[1],mode,dialog.angle.value(),dialog.increment.value(),reference))
                    if obj.kind in ('horizontal','vertical'):obj.kind='line'
        self.mutate('Configure precision',change);self.update_constraint_label();self.canvas.setFocus()

    def perpendicular_construction(self):
        from .constructions import create_perpendicular
        dialog=PerpendicularDialog(self.document,self.canvas.selected,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:objects=create_perpendicular(self.document,dialog.source_id,dialog.target_id,dialog.axis)
        except ValueError as exc:QMessageBox.warning(self,'Cannot construct perpendicular',str(exc));return
        self.mutate('Construct perpendicular',lambda:self.document.objects.extend(objects))
        self.canvas.selected={o.id for o in objects};self.selection_changed(self.canvas.selected);self.canvas.update()

    def detach_construction(self):
        selected=self.selected_objects()
        groups={o.group for o in selected if 'perpendicular' in o.data}
        def detach():
            for obj in self.document.objects:
                if obj.group in groups and 'perpendicular' in obj.data:obj.data.pop('perpendicular');obj.locked=False
        self.mutate('Detach construction',detach)

    def find(self,obj_id):return next((o for o in self.document.objects if o.id==obj_id),None)
    def selected_objects(self):return [o for o in self.document.objects if o.id in self.canvas.selected]

    def commit(self,before,label):
        self.document.update_constructions()
        self.history.document=self.document
        self.history.commit(before,label);self.refresh()
    def record_canvas(self,before,label):self.commit(before,label)
    def mutate(self,label,fn):
        before=self.document.to_dict()
        try:
            fn()
            self.document.update_constructions()
            Document.from_dict(self.document.to_dict())
        except (ValueError,TypeError,KeyError) as exc:
            self.document=Document.from_dict(before);self.history.document=self.document;self.canvas.set_document(self.document);self.refresh()
            QMessageBox.warning(self,'Cannot apply change',str(exc));return
        self.commit(before,label)

    def refresh(self):
        self._refreshing=True
        self.object_tree.blockSignals(True);self.object_tree.clear()
        for obj in reversed(self.document.objects):
            item=QTreeWidgetItem([f'{KIND_SYMBOL.get(obj.kind,"◇")}  {obj.name or obj.kind}', '', '',obj.layer])
            item.setData(0,Qt.ItemDataRole.UserRole,obj.id)
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsEditable|Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(1,Qt.CheckState.Checked if obj.visible else Qt.CheckState.Unchecked)
            item.setCheckState(2,Qt.CheckState.Checked if obj.locked else Qt.CheckState.Unchecked)
            if not obj.visible:item.setForeground(0,QColor('#93a0a8'))
            self.object_tree.addTopLevelItem(item);item.setSelected(obj.id in self.canvas.selected)
        self.object_tree.blockSignals(False)
        selected=self.selected_objects()
        self.inspector.set_object(selected[0] if len(selected)==1 else None)
        self.actions['undo'].setEnabled(self.history.can_undo);self.actions['redo'].setEnabled(self.history.can_redo)
        self.actions['undo'].setText('Undo '+self.history.undo_label if self.history.can_undo else 'Undo')
        self.actions['redo'].setText('Redo '+self.history.redo_label if self.history.can_redo else 'Redo')
        for key,attr in [('grid','grid_major'),('minor_grid','grid_minor'),('snap','snap_grid'),('snap_points','snap_points'),('snap_lines','snap_lines')]:self.actions[key].setChecked(getattr(self.document,attr))
        for key in ('origin_visible','origin_label','labels_visible'):self.actions['visible_'+key].setChecked(getattr(self.document,key))
        for kind in KIND_SYMBOL:
            if 'type_'+kind in self.actions:self.actions['type_'+kind].setChecked(self.document.type_visibility.get(kind,True))
        dirty=self.history.is_dirty(self.document)
        self.setWindowTitle(f'{self.document.title}{" •" if dirty else ""} — GraphCad')
        self.document_label.setText(f'{self.document.title}     ·     {len(self.document.objects)} objects     ·     '+('Radians' if self.document.radians else 'Degrees'))
        self.canvas.document=self.document;self.canvas.update();self.update_constraint_label();self._refreshing=False

    def selection_changed(self,ids):
        if self._refreshing:return
        self.canvas.selected=set(ids)
        self.object_tree.blockSignals(True)
        for i in range(self.object_tree.topLevelItemCount()):
            item=self.object_tree.topLevelItem(i);item.setSelected(item.data(0,Qt.ItemDataRole.UserRole) in ids)
        self.object_tree.blockSignals(False)
        selected=self.selected_objects();self.inspector.set_object(selected[0] if len(selected)==1 else None)

    def tree_selection(self):
        if self._refreshing:return
        self.canvas.selected={i.data(0,Qt.ItemDataRole.UserRole) for i in self.object_tree.selectedItems()}
        self.selection_changed(self.canvas.selected);self.canvas.update()

    def tree_changed(self,item,column):
        if self._refreshing:return
        obj=self.find(item.data(0,Qt.ItemDataRole.UserRole))
        if obj is None:return
        def change():
            if column==1:obj.visible=item.checkState(1)==Qt.CheckState.Checked
            elif column==2:obj.locked=item.checkState(2)==Qt.CheckState.Checked
            elif column==3:obj.layer=item.text(3)
            elif column==0:
                name=item.text(0)
                symbol=KIND_SYMBOL.get(obj.kind,'◇')+'  '
                obj.name=name[len(symbol):] if name.startswith(symbol) else name
        self.mutate('Edit object',change)

    def edit_tree_object(self,item,column):
        obj=self.find(item.data(0,Qt.ItemDataRole.UserRole))
        if obj and obj.kind=='function':self.add_function(obj)
        elif obj and obj.kind in ('scatter','regression'):self.edit_data_id(obj.id)

    def tree_menu(self,pos):
        m=QMenu(self)
        for key in ('duplicate','delete','front','back','lock','hide','construction','perpendicular','detach','edit_data'):m.addAction(self.actions[key])
        m.exec(self.object_tree.viewport().mapToGlobal(pos))

    def tool_changed(self,tool):
        if 'tool_'+tool in self.actions:self.actions['tool_'+tool].setChecked(True)
        hints={'select':'Select · Shift adds to selection · drag handles to reshape',
               'curve':'Curve · click knots · double-click or Enter to finish',
               'polyline':'Polyline · click vertices · double-click or Enter to finish',
               'arrow':'Arrow · click, drag toward the arrowhead, release',
               'pan':'Pan · drag the canvas · wheel to zoom'}
        if hasattr(self,'tool_hint'):self.tool_hint.setText(hints.get(tool,tool.replace('_',' ').title()+' · click or drag to draw'))
        self.canvas.setFocus()

    def apply_properties(self,obj_id,replacement):
        def apply():
            i=next(i for i,o in enumerate(self.document.objects) if o.id==obj_id)
            self.document.objects[i]=replacement
        self.mutate('Edit properties',apply)

    def toggle_document(self,key):self.mutate('Change '+key.replace('_',' '),lambda:setattr(self.document,key,not getattr(self.document,key)))
    def toggle_type(self,key):self.mutate('Toggle '+key,lambda:self.document.type_visibility.__setitem__(key,not self.document.type_visibility.get(key,True)))
    def configure_axes(self):
        dialog=AxisDialog(self.document,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        before=self.document.to_dict();self.document=dialog.result_document
        self.canvas.set_document(self.document);self.commit(before,'Configure axes');self.canvas.fit_view()

    def undo(self):
        doc=self.history.undo()
        if doc:self.document=doc;self.canvas.set_document(doc);self.refresh()
    def redo(self):
        doc=self.history.redo()
        if doc:self.document=doc;self.canvas.set_document(doc);self.refresh()

    def select_all(self):
        if self.text_focus():
            QApplication.focusWidget().selectAll();return
        self.canvas.selected={o.id for o in self.document.objects if o.visible and not o.locked};self.selection_changed(self.canvas.selected);self.canvas.update()
    def text_focus(self):return isinstance(QApplication.focusWidget(),(QLineEdit,QTextEdit,QDoubleSpinBox,QSpinBox,QTableWidget))
    def delete_selection(self):
        if self.text_focus():return
        selected={o.id for o in self.selected_objects() if not o.locked}
        if not selected:return
        selected|={o.id for o in self.document.objects if o.kind=='regression' and o.data.get('source_id') in selected}
        self.mutate('Delete objects',lambda:setattr(self.document,'objects',[o for o in self.document.objects if o.id not in selected]))
        self.canvas.selected.clear();self.selection_changed(set());self.canvas.update()

    def copy(self):
        focus=QApplication.focusWidget()
        if self.text_focus() and hasattr(focus,'copy'):focus.copy();return
        selected=self.selected_objects()
        if not selected:return
        self.clipboard_objects=[deepcopy(o) for o in selected]
        from dataclasses import asdict
        payload=json.dumps({'graphite_clipboard':1,'objects':[asdict(o) for o in selected]})
        QApplication.clipboard().setText(payload)
    def paste(self):
        focus=QApplication.focusWidget()
        if self.text_focus() and hasattr(focus,'paste'):focus.paste();return
        try:
            payload=json.loads(QApplication.clipboard().text())
            if payload.get('graphite_clipboard')!=1:return
            raw=self.document.to_dict();raw['objects']=payload['objects']
            objects=Document.from_dict(raw).objects
        except (ValueError,TypeError,AttributeError,KeyError):return
        self.insert_copies(objects)
    def duplicate(self):
        if self.text_focus():return
        self.insert_copies(self.selected_objects())
    def insert_copies(self,objects):
        if not objects:return
        objects=deepcopy(objects);mapping={o.id:str(uuid.uuid4()) for o in objects};groupmap={}
        delta=self.document.snap_interval
        for obj in objects:
            obj.id=mapping[obj.id];obj.name+=' copy';obj.locked=False
            if 'perpendicular' in obj.data:
                link=obj.data['perpendicular']
                for key in ('source_id','target_id'):
                    if link.get(key) in mapping:link[key]=mapping[link[key]]
                obj.locked=True
            if obj.group:obj.group=groupmap.setdefault(obj.group,str(uuid.uuid4()))
            if obj.kind=='regression' and obj.data.get('source_id') in mapping:obj.data['source_id']=mapping[obj.data['source_id']]
            if obj.kind=='function':
                obj.data['offset_x']=obj.data.get('offset_x',0)+delta;obj.data['offset_y']=obj.data.get('offset_y',0)+delta
            elif obj.kind=='scatter':obj.data['rows']=[[x+delta,y+delta] for x,y in obj.data.get('rows',[])]
            else:obj.points=[[x+delta,y+delta] for x,y in obj.points]
            if obj.data.get('label_position'):obj.data['label_position']=[v+delta for v in obj.data['label_position']]
        self.mutate('Duplicate objects',lambda:self.document.objects.extend(objects))
        self.canvas.selected={o.id for o in objects};self.selection_changed(self.canvas.selected);self.canvas.update()

    def group(self):
        selected=[o for o in self.selected_objects() if not o.locked]
        if len(selected)<2:return
        group=str(uuid.uuid4());self.mutate('Group objects',lambda:[setattr(o,'group',group) for o in selected])
    def ungroup(self):self.mutate('Ungroup objects',lambda:[setattr(o,'group','') for o in self.selected_objects() if not o.locked])
    def toggle_lock(self):self.mutate('Toggle locking',lambda:[setattr(o,'locked',not o.locked) for o in self.selected_objects()])
    def toggle_visibility(self):self.mutate('Toggle visibility',lambda:[setattr(o,'visible',not o.visible) for o in self.selected_objects()])
    def reorder(self,front):
        selected=[o for o in self.selected_objects() if not o.locked];others=[o for o in self.document.objects if o not in selected]
        self.mutate('Reorder objects',lambda:setattr(self.document,'objects',others+selected if front else selected+others))
    def move_one(self,direction):
        selected=self.selected_objects()
        if len(selected)!=1:return
        i=self.document.objects.index(selected[0]);j=max(0,min(len(self.document.objects)-1,i+direction))
        def move():self.document.objects.insert(j,self.document.objects.pop(i))
        self.mutate('Reorder object',move)

    def quick_function(self):
        expression=self.expression_input.text().strip()
        if not expression:return
        try:Expression(expression,radians=self.document.radians)
        except ValueError as exc:
            QMessageBox.warning(self,'Invalid expression',str(exc));return
        obj=GraphObject('function',name=self.unique_name('Function'),label='',data={'expression':expression})
        self.mutate('Plot function',lambda:self.document.objects.append(obj))
        self.canvas.selected={obj.id};self.selection_changed(self.canvas.selected);self.canvas.update()
        self.expression_input.clear();self.canvas.setFocus()

    def unique_name(self,base):
        names={o.name for o in self.document.objects}
        if base not in names:return base
        i=2
        while f'{base} {i}' in names:i+=1
        return f'{base} {i}'

    def add_function(self,obj=None):
        dialog=FunctionDialog(obj,self.document.radians,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        if obj is None:
            obj=GraphObject('function',name=self.unique_name(dialog.name.text() or 'Function'),label=dialog.label.text(),data=dialog.values)
            self.mutate('Plot function',lambda:self.document.objects.append(obj))
        else:
            def edit():
                obj.name=dialog.name.text();obj.label=dialog.label.text();obj.data.update(dialog.values)
            self.mutate('Edit expression',edit)
        self.canvas.selected={obj.id};self.selection_changed(self.canvas.selected);self.canvas.update()

    def add_dataset(self):self.edit_dataset(None)
    def edit_selected_data(self):
        selected=self.selected_objects()
        if len(selected)==1:self.edit_data_id(selected[0].id)
        else:self.statusBar().showMessage('Select a scatter plot or regression line to edit its data.',6000)
    def edit_data_id(self,obj_id):
        obj=self.find(obj_id)
        if obj and obj.kind=='regression':obj=self.find(obj.data.get('source_id'))
        if obj and obj.kind=='scatter':self.edit_dataset(obj)
    def edit_dataset(self,obj):
        dialog=DataDialog(obj,self)
        if obj:dialog.regression.setChecked(any(o.kind=='regression' and o.data.get('source_id')==obj.id for o in self.document.objects))
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        before=self.document.to_dict()
        if obj is None:
            obj=GraphObject('scatter',name=self.unique_name(dialog.name.text() or 'Dataset'),label=dialog.label.text(),data={'rows':dialog.rows})
            self.document.objects.append(obj)
        else:
            obj.data['rows']=dialog.rows;obj.name=dialog.name.text();obj.label=dialog.label.text()
        existing=[o for o in self.document.objects if o.kind=='regression' and o.data.get('source_id')==obj.id]
        if dialog.regression.isChecked() and not existing:self.document.objects.append(self.regression_object(obj))
        elif not dialog.regression.isChecked():self.document.objects=[o for o in self.document.objects if o not in existing]
        self.commit(before,'Edit dataset');self.canvas.selected={obj.id};self.selection_changed(self.canvas.selected);self.canvas.update()

    def regression_object(self,source):
        linear_regression(source.data['rows'])
        return GraphObject('regression',name=self.unique_name(source.name+' regression'),label='',style={'color':'#bc6540','width':2,'line_style':'solid'},data={'source_id':source.id})
    def add_regression(self):
        selected=self.selected_objects()
        obj=next((o for o in selected if o.kind=='scatter'),None)
        if obj is None:
            self.statusBar().showMessage('Select a dataset in the object list, then add its regression line.',6000);return
        if any(o.kind=='regression' and o.data.get('source_id')==obj.id for o in self.document.objects):
            self.statusBar().showMessage('This dataset already has a linked regression line.',5000);return
        try:reg=self.regression_object(obj)
        except ValueError as exc:QMessageBox.warning(self,'Regression unavailable',str(exc));return
        self.mutate('Add regression',lambda:self.document.objects.append(reg))
        fit=linear_regression(obj.data['rows'])
        self.statusBar().showMessage(f'{fit.equation}    R² = {fit.r_squared:.8g}    r = {format_correlation(fit.r)}',12000)
    def scatter_to_points(self):
        selected=[o for o in self.selected_objects() if o.kind=='scatter']
        if not selected:return
        objects=[]
        for source in selected:
            for i,row in enumerate(source.data.get('rows',[])):
                objects.append(GraphObject('point',points=[list(row)],name=f'{source.name} {i+1}',style=deepcopy(source.style)))
        def convert():
            self.document.objects.extend(objects)
            for source in selected:source.visible=False
        self.mutate('Convert scatter to points',convert)
        self.canvas.selected={o.id for o in objects};self.selection_changed(self.canvas.selected)

    def construction_lines(self):
        points=[o for o in self.selected_objects() if o.kind=='point' and o.points]
        if not points:
            self.statusBar().showMessage('Select a point to project dashed construction lines to the axes.',6000);return
        objects=[]
        for point in points:
            x,y=point.points[0]
            style={'color':'#7b8993','width':1.3,'line_style':'dashed'}
            objects.extend([GraphObject('construction',points=[[x,y],[x,self.document.x_axis.position]],name=self.unique_name(point.name+' to X'),style=style),GraphObject('construction',points=[[x,y],[self.document.y_axis.position,y]],name=self.unique_name(point.name+' to Y'),style=style)])
        self.mutate('Construction lines',lambda:self.document.objects.extend(objects))

    def intersections(self):
        selected=[o for o in self.selected_objects() if o.kind=='function']
        if len(selected)!=2:
            QMessageBox.information(self,'Function intersections','Select two function objects using Shift, then run this command.');return
        from .expressions import find_intersections
        a,b=selected
        try:
            def callable_for(obj):
                expr=Expression(obj.data['expression'],radians=self.document.radians)
                ox,oy=obj.data.get('offset_x',0),obj.data.get('offset_y',0)
                lo,hi=obj.data.get('domain_min'),obj.data.get('domain_max')
                def f(x):
                    value=x-ox
                    if lo is not None and value<lo or hi is not None and value>hi:return math.nan
                    return expr.evaluate(value)+oy
                return f
            # The numerical routine accepts callables as well as expression text.
            roots=find_intersections(callable_for(a),callable_for(b),self.canvas.bounds[0],self.canvas.bounds[1])
            if not roots:
                QMessageBox.information(self,'Function intersections','No intersections found in the visible X range.');return
            objects=[GraphObject('point',points=[[x,y]],name=self.unique_name(f'Intersection {i+1}'),label=f'E{i+1}',data={'label_mode':'both'}) for i,(x,y) in enumerate(roots)]
            self.mutate('Find intersections',lambda:self.document.objects.extend(objects))
            self.canvas.selected={o.id for o in objects};self.selection_changed(self.canvas.selected)
        except (ValueError,TypeError) as exc:QMessageBox.warning(self,'Intersection analysis',str(exc))

    def confirm_discard(self):
        if not self.history.is_dirty(self.document):return True
        result=QMessageBox.question(self,'Save changes?',f'Save changes to “{self.document.title}” before continuing?',QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Save)
        if result==QMessageBox.StandardButton.Cancel:return False
        if result==QMessageBox.StandardButton.Save:return self.save()
        return True
    def replace_document(self,document,path=None):
        self.document=document;self.path=Path(path) if path else None;self.history.reset(document)
        self.canvas.set_document(document);self.canvas.selected.clear();self.refresh();self.canvas.fit_view()
    def new_document(self):
        name,ok=QInputDialog.getItem(self,'New graph','Starting template',template_names(),0,False)
        if ok:self.new_from_template(name)
    def new_from_template(self,name):
        if self.confirm_discard():self.replace_document(make_template(name))
    def open_document(self):
        path,_=QFileDialog.getOpenFileName(self,'Open editable graph','','GraphCad project (*.graphite *.graphproj);;All files (*)')
        if path and self.confirm_discard():self.open_path(path)
    def open_path(self,path):
        try:doc=Document.load(path)
        except (OSError,ValueError,TypeError) as exc:
            QMessageBox.warning(self,'Cannot open project',str(exc));return False
        self.replace_document(doc,path);self.add_recent(path);return True
    def save(self):
        if self.path is None:return self.save_as()
        try:self.document.save(self.path)
        except (OSError,ValueError,TypeError) as exc:
            QMessageBox.warning(self,'Cannot save project',str(exc));return False
        self.history.mark_saved(self.document);self.add_recent(self.path);self.refresh();self.statusBar().showMessage('Editable project saved.',5000);return True
    def save_as(self):
        path,_=QFileDialog.getSaveFileName(self,'Save editable project',str(self.path or Path(self.document.title+'.graphite')),'GraphCad project (*.graphite)')
        if not path:return False
        path=Path(path)
        if path.suffix.lower()!='.graphite':path=path.with_suffix('.graphite')
        old_path=self.path;old_title=self.document.title
        self.path=path;self.document.title=path.stem
        if self.save():return True
        self.path=old_path;self.document.title=old_title;return False
    def add_recent(self,path):
        path=str(Path(path).absolute());recent=self.settings.value('recent',[],type=list)
        self.settings.setValue('recent',[path]+[p for p in recent if p!=path][:7]);self.populate_recent()
    def populate_recent(self):
        if not hasattr(self,'recent_menu'):return
        self.recent_menu.clear()
        for path in self.settings.value('recent',[],type=list):
            self.recent_menu.addAction(Path(path).name,lambda p=path:self.open_recent(p))
        self.recent_menu.setEnabled(bool(self.recent_menu.actions()))
    def open_recent(self,path):
        if self.confirm_discard():self.open_path(path)
    def save_template(self):
        path,_=QFileDialog.getSaveFileName(self,'Save reusable template',self.document.title+'.graphite','GraphCad template (*.graphite)')
        if path:
            try:self.document.save(path)
            except (OSError,ValueError) as exc:QMessageBox.warning(self,'Cannot save template',str(exc))
    def load_template(self):
        path,_=QFileDialog.getOpenFileName(self,'Open reusable template','','GraphCad template (*.graphite)')
        if not path:return
        try:doc=Document.load(path)
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Cannot open template',str(exc));return
        if self.confirm_discard():self.replace_document(doc)
    def export_graph(self):
        from .export import export_png,export_pdf,export_svg,export_dxf,export_dwg
        dialog=ExportDialog(self.document,self.canvas.bounds,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        kind=dialog.format.currentText().lower();path,_=QFileDialog.getSaveFileName(self,'Export '+kind.upper(),self.document.title+'.'+kind,f'{kind.upper()} file (*.{kind})')
        if not path:return
        path=Path(path)
        if path.suffix.lower()!='.'+kind:path=path.with_suffix('.'+kind)
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            {'png':export_png,'pdf':export_pdf,'svg':export_svg,'dxf':export_dxf,'dwg':export_dwg}[kind](self.document,path,dialog.options())
        except (OSError,ValueError,RuntimeError,ImportError) as exc:
            QApplication.restoreOverrideCursor();QMessageBox.warning(self,'Export failed',str(exc));return
        finally:
            if QApplication.overrideCursor():QApplication.restoreOverrideCursor()
        self.statusBar().showMessage('Exported '+str(path),10000)

    def show_help(self):
        dialog=QDialog(self);dialog.setWindowTitle('GraphCad · quick guide');dialog.resize(650,580)
        layout=QVBoxLayout(dialog);text=QTextEdit();text.setReadOnly(True)
        text.setHtml('''<h2>Precision drawing, in graph coordinates</h2>
        <p><b>Start:</b> File → New chooses a template. Graph → Coordinate system changes ranges, axes, intervals, number formatting, grid and snapping. An interval of 0 selects automatic major ticks.</p>
        <p><b>Draw:</b> choose Point (P), Segment (L), Arrow (A), or Text (T). For segments and arrows, press at the start, drag, and release at the end. Curve (C) and Polyline: click control points, then double-click or Enter to finish. Escape cancels.</p>
        <p><b>Edit:</b> Select (V) an object. Shift selects several. Drag to move, or drag square handles to reshape. The Properties panel provides exact coordinates and styling; click Apply properties. Double-click an object name to rename it. Show and Lock are independent.</p>
        <p><b>Navigate:</b> wheel zooms around the pointer. Drag with the middle mouse button, hold Space, or choose Pan (H). Fit graph restores the saved ranges. View → Elements independently hides origin, labels and object kinds.</p>
        <p><b>Mathematics:</b> type in Function Entry and press Enter, or Insert a function with domain restrictions. Use ^ for powers, 2x for multiplication, π/e and common functions. Radians are default; change them in Coordinate system. Select two functions and use Tools → Find function intersections to create numerical intersection points.</p>
        <p><b>Data:</b> Graph → Scatter plot / dataset opens an editable X/Y table. Import CSV or paste columns. Enable linked regression to show least-squares slope, intercept and R². Double-click a dataset or regression to edit its source values.</p>
        <p><b>Precision:</b> Tools → Precision and orientation controls point-to-line snapping and free, horizontal, vertical, parallel, perpendicular, incremental or custom angles. Choose a reference for parallel/perpendicular drawing. Object → Perpendicular from point creates linked helpers; Detach linked construction makes them freely editable.</p><p><b>Themes:</b> Use the Theme selector for Light, Dark or System. The choice is saved; document and exported colors stay independent.</p><p><b>Save:</b> .graphite preserves editable objects, data, axes and styles. Export creates PNG, vector PDF/SVG, or CAD DXF. DWG uses an optional separately installed ODA File Converter.</p>
        <p><b>Shortcuts:</b> Ctrl/Cmd N/O/S, Shift S; Z and Shift Z; C/V/D; G and Shift G; Delete, arrow keys to nudge. Shift+arrow nudges faster. Tool keys work while the canvas has focus.</p>''')
        layout.addWidget(text);box=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);box.rejected.connect(dialog.reject);layout.addWidget(box);dialog.exec()
    def about(self):QMessageBox.about(self,'About GraphCad','<h2>GraphCad 1.1</h2><p>Native precision graph and diagram editor.</p><p>Qt vector rendering · offline mathematical plotting · linked statistical data</p><p>Project code: MIT. Qt/PySide6: LGPLv3/GPLv3 or commercial. See docs/LICENSES.md in the source distribution.</p>')
    def closeEvent(self,event):
        if self.confirm_discard():self.settings.setValue('windowGeometry',self.saveGeometry());event.accept()
        else:event.ignore()
