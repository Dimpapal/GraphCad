"""Interface-only themes. Document renderers always use explicit document colors."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QPalette


def resolve_theme(app,mode):
    if mode=='system':
        return 'dark' if app.styleHints().colorScheme()==Qt.ColorScheme.Dark else 'light'
    return mode if mode in ('light','dark') else 'light'


def apply_theme(app,mode='light'):
    theme=resolve_theme(app,mode)
    app.setStyle('Fusion')
    dark=theme=='dark'
    c=({'window':'#20272e','panel':'#262f38','base':'#182129','alternate':'#222d36',
        'text':'#e1eaf0','muted':'#a8bac7','border':'#4b5c69','button':'#303d48',
        'accent':'#21685e','accent_text':'#ffffff','selection':'#315e60','disabled':'#788994'} if dark else
       {'window':'#eef2f5','panel':'#f8fafb','base':'#ffffff','alternate':'#f0f5f7',
        'text':'#263d49','muted':'#596d7a','border':'#cbd6de','button':'#f4f7f9',
        'accent':'#19675e','accent_text':'#ffffff','selection':'#d8eeeb','disabled':'#8b9ca7'})
    p=QPalette()
    mapping={'Window':'window','WindowText':'text','Base':'base','AlternateBase':'alternate','Text':'text',
             'Button':'button','ButtonText':'text','Highlight':'selection','HighlightedText':'text',
             'ToolTipBase':'panel','ToolTipText':'text','PlaceholderText':'muted','Link':'muted',
             'Light':'panel','Mid':'border','Dark':'border'}
    for role,key in mapping.items():p.setColor(getattr(QPalette.ColorRole,role),QColor(c[key]))
    for role in ('WindowText','Text','ButtonText'):
        p.setColor(QPalette.ColorGroup.Disabled,getattr(QPalette.ColorRole,role),QColor(c['disabled']))
    app.setPalette(p)
    app.setProperty('graphcad_theme',theme)
    app.setProperty('graphcad_theme_mode',mode)
    app.setStyleSheet(f'''
      QMainWindow,QDialog {{ background:{c['window']}; }}
      QToolBar {{ background:{c['panel']};border:0;border-bottom:1px solid {c['border']};spacing:5px;padding:5px; }}
      QToolButton {{padding:5px 7px;border-radius:5px;color:{c['text']};}}
      QToolButton:hover {{background:{c['selection']};}}
      QToolButton:checked {{background:{c['selection']};}}
      QDockWidget {{font-weight:600;color:{c['text']};}}
      QDockWidget::title {{background:{c['window']};padding:8px;}}
      QTreeWidget,QScrollArea {{border:0;background:{c['panel']};font-weight:400;}}
      QHeaderView::section {{background:{c['alternate']};color:{c['text']};border:0;border-bottom:1px solid {c['border']};padding:6px;}}
      QLineEdit,QDoubleSpinBox,QSpinBox,QComboBox,QTextEdit {{padding:4px;border:1px solid {c['border']};border-radius:4px;background:{c['base']};color:{c['text']};font-weight:400;}}
      QPushButton {{padding:6px 10px;font-weight:400;}}
      QPushButton#primary,QToolButton#exportButton {{background:{c['accent']};color:{c['accent_text']};border:0;border-radius:7px;padding:8px 12px;}}
      QToolButton#exportButton:hover {{background:#278375;}}
      QStatusBar {{background:{c['window']};color:{c['muted']};}}
      QTableWidget {{background:{c['base']};color:{c['text']};gridline-color:{c['border']};}}
      QLabel#muted {{color:{c['muted']};}}
      QLabel#error {{color:{'#ffb0a6' if dark else '#a33131'};}}
      QMenuBar,QMenu {{background:{c['panel']};color:{c['text']};}}
      QMenu::item:selected,QMenuBar::item:selected {{background:{c['selection']};}}
    ''')
    return theme
