"""Native application startup, platform identity, and logging."""
import argparse
import math
import logging
import sys
from pathlib import Path
from PySide6.QtCore import QTimer, QEvent, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPalette
from PySide6.QtWidgets import QApplication


def application_icon():
    pix = QPixmap(128, 128)
    pix.fill(QColor('#164b55'))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor('#ffffff'), 5))
    p.drawLine(27, 97, 104, 97)
    p.drawLine(27, 97, 27, 23)
    p.setPen(QPen(QColor('#88dec7'), 6))
    from PySide6.QtGui import QPainterPath
    path = QPainterPath()
    path.moveTo(36, 82)
    path.cubicTo(51,82,51,56,66,44)
    p.drawPath(path)
    from PySide6.QtGui import QPolygonF
    from PySide6.QtCore import QPointF
    p.setPen(QPen(QColor('#e5b85c'),4));p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPolygon(QPolygonF([QPointF(71,28),QPointF(108,70),QPointF(71,70)]))
    p.drawPolygon(QPolygonF([QPointF(79,49),QPointF(91,62),QPointF(79,62)]))
    p.end()
    return QIcon(pix)


from .themes import apply_theme


class GraphiteApplication(QApplication):
    """Handle native macOS Finder/Open-With document events."""
    def event(self, event):
        if event.type() == QEvent.Type.FileOpen:
            path = event.file()
            window = getattr(self, 'main_window', None)
            if window is None:
                self.pending_project = path
            elif path and window.confirm_discard():
                window.open_path(path)
            event.accept()
            return True
        return super().event(event)


def verify_build(app, folder):
    """Exercise frozen UI, serialization, painters and CAD dependencies locally."""
    import json
    import platform
    from .model import Document
    from .templates import make_template
    from .export import ExportOptions, export_png, export_pdf, export_svg, export_dxf
    from PySide6.QtGui import QImage
    import ezdxf
    import xml.etree.ElementTree as ET
    report = {'status': 'failed', 'platform': platform.platform(), 'checks': []}
    try:
        folder.mkdir(parents=True, exist_ok=True)
        doc = make_template('Supply and demand')
        from .model import GraphObject
        from .constructions import create_perpendicular
        from .data import linear_regression
        from .geometry import project_point_to_line,constrain_endpoint
        source=GraphObject('point',[[2,8]],name='Projection source')
        target=GraphObject('line',[[0,0],[10,10]],name='Projection target')
        doc.objects.extend([source,target]);helpers=create_perpendicular(doc,source.id,target.id)
        doc.objects.extend(helpers);doc.update_constructions()
        assert math.dist(helpers[0].points[0],[5,5])<1e-10
        source.points=[[4,8]];doc.update_constructions()
        assert math.dist(helpers[0].points[0],[6,6])<1e-10
        assert math.dist(project_point_to_line((4,8),(0,0),(10,10)),(6,6))<1e-10
        assert constrain_endpoint((0,0),(3,5),'horizontal')[1]==0
        assert abs(linear_regression([[1,6],[2,4],[3,2]]).r+1)<1e-12
        report['checks'].append('Projection, linked perpendicular updates, orientation and signed Pearson r')
        project = folder / 'verification.graphite'
        doc.save(project)
        assert Document.load(project).to_dict() == doc.to_dict()
        report['checks'].append('Editable document round trip')
        options = ExportOptions(margin=25)
        for extension, export in [('png', export_png), ('pdf', export_pdf), ('svg', export_svg), ('dxf', export_dxf)]:
            export(doc, folder / ('verification.' + extension), options)
        picture = QImage(str(folder / 'verification.png'))
        assert (picture.width(), picture.height()) == (1920, 1080)
        assert not picture.isNull()
        report['checks'].append('PNG decoded at 1920 x 1080')
        apply_theme(app,'dark')
        export_png(doc,folder/'verification-dark-theme.png',options)
        dark=QImage(str(folder/'verification-dark-theme.png'))
        assert bytes(dark.constBits())==bytes(picture.constBits())
        apply_theme(app,'light')
        report['checks'].append('Dark interface preserves identical export pixels')
        assert (folder / 'verification.pdf').read_bytes().startswith(b'%PDF-')
        report['checks'].append('PDF writer generated a PDF document')
        svg = ET.parse(folder / 'verification.svg').getroot()
        assert svg.tag.endswith('svg')
        assert not any(element.tag.endswith('image') for element in svg.iter())
        report['checks'].append('SVG parsed with vector content')
        cad = ezdxf.readfile(folder / 'verification.dxf')
        assert not cad.audit().has_errors
        assert len(cad.modelspace().query('LINE')) >= 4
        report['checks'].append('DXF reopened, geometry present, audit clean')
        report['status'] = 'passed'
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        logging.exception('Build verification failed')
    finally:
        try:
            (folder / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        except OSError:
            logging.exception('Could not write verification report')
        app.exit(0 if report['status'] == 'passed' else 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description='GraphCad native graph and diagram editor')
    parser.add_argument('project', nargs='?', help='An editable .graphite project')
    parser.add_argument('--verify-build', metavar='DIRECTORY', help='Verify the installed build by writing and inspecting editable, PNG, PDF, SVG and DXF samples')
    parser.add_argument('--smoke-test', action='store_true', help='Open the native window, then exit after 1 second')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    app = QApplication.instance() or GraphiteApplication(sys.argv[:1])
    app.setApplicationName('GraphCad')
    app.setOrganizationName('Graphite')
    app.setApplicationVersion('1.1.0')
    app.setWindowIcon(application_icon())
    apply_theme(app)
    from .window import MainWindow
    window = MainWindow()
    app.main_window = window
    window.setWindowIcon(app.windowIcon())
    project = args.project or getattr(app, 'pending_project', None)
    if project:
        window.open_path(Path(project))
    window.show()
    if args.verify_build:
        QTimer.singleShot(100, lambda: verify_build(app, Path(args.verify_build)))
    elif args.smoke_test:
        QTimer.singleShot(1000, app.quit)
    return app.exec()
