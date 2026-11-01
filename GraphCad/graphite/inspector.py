"""Context-sensitive, transactional numerical object editor."""
from copy import deepcopy
import math
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,QVBoxLayout,QFormLayout,QLabel,QLineEdit,QCheckBox,QComboBox,
    QDoubleSpinBox,QPushButton,QScrollArea,QTableWidget,QTableWidgetItem,
    QHeaderView,QHBoxLayout,QColorDialog,QFontComboBox,QTextEdit,
)
from PySide6.QtGui import QColor
from .dialogs import number,combo,checked
from .expressions import Expression


class Inspector(QWidget):
    applyRequested=Signal(str,object)
    editDataRequested=Signal(str)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.obj=None
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);outer.addWidget(self.scroll)
        self.set_object(None)

    def set_object(self,obj):
        self.obj=obj
        self.fields={};self.style_fields={};self.data_fields={};self.geometry=None
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(14,14,14,14)
        self.scroll.setWidget(page)
        if obj is None:
            title=QLabel('Object properties');title.setStyleSheet('font-size:16px;font-weight:600')
            layout.addWidget(title)
            help=QLabel('Select an object on the canvas or in the object list to edit its geometry and appearance.\n\nDrag the square handles to reshape an object. Use Shift to select several objects.')
            help.setWordWrap(True);help.setObjectName('muted');layout.addWidget(help);layout.addStretch();return
        title=QLabel(obj.kind.replace('_',' ').title());title.setStyleSheet('font-size:16px;font-weight:600');layout.addWidget(title)
        form=QFormLayout();form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.fields={'name':QLineEdit(obj.name),'label':QLineEdit(obj.label),'visible':checked(obj.visible),'locked':checked(obj.locked),'layer':QLineEdit(obj.layer)}
        for key,w in self.fields.items():form.addRow(key.capitalize(),w)
        layout.addLayout(form)
        if 'perpendicular' in obj.data:
            hint=QLabel('Linked perpendicular geometry · edit the source/target, or detach the construction from the Object menu.');hint.setWordWrap(True);hint.setObjectName('muted');layout.addWidget(hint)
            self.fields['locked'].setEnabled(False)
        if obj.points:
            layout.addWidget(QLabel('Geometry · mathematical coordinates'))
            self.geometry=QTableWidget(len(obj.points),2)
            self.geometry.setHorizontalHeaderLabels(['X','Y']);self.geometry.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.geometry.setMaximumHeight(170)
            self.geometry.setMinimumHeight(min(170,32*(len(obj.points)+1)+8))
            if 'perpendicular' in obj.data:self.geometry.setEnabled(False)
            for i,row in enumerate(obj.points):
                for j,v in enumerate(row):self.geometry.setItem(i,j,QTableWidgetItem(repr(v)))
            layout.addWidget(self.geometry)
            if obj.kind in ('polyline','curve'):
                bar=QHBoxLayout();add=QPushButton('Add vertex');remove=QPushButton('Remove vertex')
                add.clicked.connect(self.add_vertex);remove.clicked.connect(self.remove_vertex);bar.addWidget(add);bar.addWidget(remove);layout.addLayout(bar)
        dataform=QFormLayout()
        if obj.kind!='text':
            self.data_fields['label_visible']=checked(obj.data.get('label_visible',True))
            dataform.addRow('Show label',self.data_fields['label_visible'])
        if obj.kind=='text':
            self.data_fields['text']=QTextEdit(obj.data.get('text','Text'))
            self.data_fields['text'].setMaximumHeight(95)
            dataform.addRow('Text',self.data_fields['text'])
        if obj.kind=='point':
            self.data_fields['label_mode']=combo(['name','coordinates','both'],obj.data.get('label_mode','name'))
            dataform.addRow('Point label',self.data_fields['label_mode'])
        if obj.kind=='function':
            self.data_fields['expression']=QLineEdit(obj.data.get('expression','x'))
            for key in ('domain_min','domain_max'):
                self.data_fields[key]=QLineEdit('' if obj.data.get(key) is None else str(obj.data[key]))
            for key in ('offset_x','offset_y'):self.data_fields[key]=number(obj.data.get(key,0))
            for key,w in self.data_fields.items():dataform.addRow(key.replace('_',' ').capitalize(),w)
        if obj.kind in ('scatter','regression'):
            b=QPushButton('Edit linked dataset…');b.clicked.connect(lambda:self.editDataRequested.emit(obj.id));layout.addWidget(b)
            if obj.kind=='scatter':
                dataform.addRow('Observations',QLabel(str(len(obj.data.get('rows',[])))))
                self.data_fields['point_labels']=checked(obj.data.get('point_labels',False))
                dataform.addRow('Label data points',self.data_fields['point_labels'])
        if obj.kind!='text':
            for key in ('label_x','label_y'):
                index=0 if key=='label_x' else 1
                p=obj.data.get('label_position')
                self.data_fields[key]=QLineEdit('' if p is None else str(p[index]))
                dataform.addRow('Label '+('X' if index==0 else 'Y')+' (optional)',self.data_fields[key])
        layout.addLayout(dataform)
        layout.addWidget(QLabel('Appearance'))
        styleform=QFormLayout()
        st=obj.style
        color=QPushButton(st.get('color','#2459ad'));color.clicked.connect(lambda:self.pick_color(color))
        self.style_fields['color']=color
        self.style_fields['width']=number(st.get('width',2),.1,30,2)
        self.style_fields['line_style']=combo(['solid','dashed','dotted','dash-dot'],st.get('line_style','solid'))
        self.style_fields['opacity']=number(st.get('opacity',1),0,1,2)
        if obj.kind in ('point','scatter'):
            self.style_fields['marker']=combo(['circle','square','diamond','cross','triangle'],st.get('marker','circle'))
            self.style_fields['marker_size']=number(st.get('marker_size',6),1,50,1)
            fill=QPushButton(st.get('fill','#ffffff'));fill.clicked.connect(lambda:self.pick_color(fill));self.style_fields['fill']=fill
        if obj.kind=='arrow':
            self.style_fields['arrow_start']=checked(st.get('arrow_start',False))
            self.style_fields['arrow_end']=checked(st.get('arrow_end',True))
            self.style_fields['arrow_size']=number(st.get('arrow_size',12),2,60,1)
        self.style_fields['font']=QLineEdit(st.get('font','Sans Serif'))
        self.style_fields['font_size']=number(st.get('font_size',12),4,100,1)
        self.style_fields['bold']=checked(st.get('bold',False));self.style_fields['italic']=checked(st.get('italic',False))
        if obj.kind=='text':
            self.style_fields['align']=combo(['left','center','right'],st.get('align','left'))
            self.style_fields['rotation']=number(st.get('rotation',0),-360,360,1)
            bg=QPushButton(st.get('background','transparent'));bg.clicked.connect(lambda:self.pick_color(bg));self.style_fields['background']=bg
        for key,w in self.style_fields.items():
            if isinstance(w,QPushButton):w.setMinimumHeight(28)
            styleform.addRow(key.replace('_',' ').capitalize(),w)
        layout.addLayout(styleform)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setObjectName('error');layout.addWidget(self.error)
        apply=QPushButton('Apply properties');apply.setObjectName('primary');apply.clicked.connect(self.apply);layout.addWidget(apply)
        layout.addStretch()

    def pick_color(self,button):
        color=QColorDialog.getColor(QColor(button.text()),self,'Choose color',QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():button.setText(color.name(QColor.NameFormat.HexArgb) if color.alpha()!=255 else color.name())

    def add_vertex(self):
        row=self.geometry.rowCount();self.geometry.insertRow(row)
        for j in range(2):self.geometry.setItem(row,j,QTableWidgetItem('0'))

    def remove_vertex(self):
        row=self.geometry.currentRow()
        if row>=0 and self.geometry.rowCount()>2:self.geometry.removeRow(row)

    @staticmethod
    def value(w):
        if isinstance(w,QCheckBox):return w.isChecked()
        if isinstance(w,QComboBox):return w.currentText()
        if isinstance(w,QDoubleSpinBox):return w.value()
        if isinstance(w,QTextEdit):return w.toPlainText()
        return w.text()

    def apply(self):
        if self.obj is None:return
        obj=deepcopy(self.obj)
        try:
            for key,w in self.fields.items():setattr(obj,key,self.value(w))
            for key,w in self.style_fields.items():obj.style[key]=self.value(w)
            if self.geometry:
                points=[]
                for i in range(self.geometry.rowCount()):
                    row=[float(self.geometry.item(i,j).text()) for j in range(2)]
                    if not all(math.isfinite(v) and abs(v)<=1e12 for v in row):raise ValueError('Coordinates must be finite and within ±1 trillion.')
                    points.append(row)
                obj.points=points
            data={k:self.value(w) for k,w in self.data_fields.items()}
            if obj.kind=='function':
                Expression(data['expression'])
                for key in ('domain_min','domain_max'):data[key]=float(data[key]) if str(data[key]).strip() else None
                lo,hi=data.get('domain_min'),data.get('domain_max')
                if any(v is not None and not math.isfinite(v) for v in (lo,hi)):raise ValueError('Domain bounds must be finite.')
                if lo is not None and hi is not None and lo>=hi:raise ValueError('Domain maximum must exceed minimum.')
            if 'label_x' in data:
                x,y=data.pop('label_x'),data.pop('label_y')
                if bool(x.strip()) != bool(y.strip()):raise ValueError('Enter both label coordinates, or leave both empty.')
                if x.strip():
                    pos=[float(x),float(y)]
                    if not all(math.isfinite(v) for v in pos):raise ValueError('Label coordinates must be finite.')
                    data['label_position']=pos
                else:obj.data.pop('label_position',None)
            obj.data.update(data)
        except (ValueError,AttributeError,TypeError) as exc:
            self.error.setText(str(exc));return
        self.applyRequested.emit(obj.id,obj)
