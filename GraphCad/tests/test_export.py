"""Inspect produced files; success means usable geometry rather than just file existence."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import xml.etree.ElementTree as ET

import ezdxf
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from graphite.export import (ExportOptions, export_dxf, export_dwg, export_pdf,
                             export_png, export_svg)
from graphite.model import Document, GraphObject


@pytest.fixture(scope='module', autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def scene():
    doc = Document(title='Export verification')
    doc.x_axis.title, doc.y_axis.title = 'Quantity', 'Price'
    doc.objects.extend([
        GraphObject(kind='line', points=[[1, 2], [8, 7]], name='Supply', label='S'),
        GraphObject(kind='curve', points=[[1, 8], [3, 5], [8, 2]], name='Demand', label='D'),
        GraphObject(kind='arrow', points=[[2, 3], [5, 7]], name='Shift', style={'color': '#9e4a21', 'arrow_size': 14}),
        GraphObject(kind='point', points=[[4, 4]], name='Equilibrium', label='E'),
        GraphObject(kind='text', points=[[4, 8]], data={'text': 'Equilibrium'}),
        GraphObject(kind='function', name='Function', data={'expression': '1/x', 'domain_min': .2, 'domain_max': 8}),
    ])
    rows = GraphObject(kind='scatter', name='Data', data={'rows': [[1, 2], [2, 4], [3, 6]]})
    doc.objects.append(rows)
    doc.objects.append(GraphObject(kind='regression', data={'source_id': rows.id}))
    return doc


def test_png_dimensions_transparency_appearance_and_options(tmp_path, scene):
    path = tmp_path / 'graph.png'
    export_png(scene, path, ExportOptions(width=1000, height=750, transparent=True, margin=20))
    image = QImage(str(path))
    assert not image.isNull()
    assert (image.width(), image.height()) == (1000, 750)
    assert image.pixelColor(0, 0).alpha() == 0
    painted = sum(image.pixelColor(x, y).alpha() > 100
                  for x in range(0, 1000, 10) for y in range(0, 750, 10))
    assert painted > 40
    assert painted < 3000  # empty canvas remains transparent
    export_png(scene, path, ExportOptions(width=800, height=600))
    assert QImage(str(path)).pixelColor(0, 0).name() == '#ffffff'


def test_high_resolution_export_preserves_relative_strokes_text_and_layout(tmp_path, scene):
    low, high = tmp_path / 'low.png', tmp_path / 'high.png'
    export_png(scene, low, ExportOptions(width=1000, height=750))
    export_png(scene, high, ExportOptions(width=2000, height=1500))
    first, second = QImage(str(low)), QImage(str(high))
    differences = []
    for x in range(0, 1000, 4):
        for y in range(0, 750, 4):
            a, b = first.pixelColor(x, y), second.pixelColor(2 * x, 2 * y)
            differences.append((abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue())) / 3)
    assert sum(differences) / len(differences) < 8


def test_pdf_is_vector_and_has_correct_page_and_visible_content(tmp_path, scene):
    pdf = tmp_path / 'graph.pdf'
    export_pdf(scene, pdf, ExportOptions(page_size='Letter', landscape=True))
    pymupdf = pytest.importorskip('pymupdf')
    with pymupdf.open(pdf) as document:
        assert len(document) == 1
        page = document[0]
        assert page.rect.width == pytest.approx(792, abs=1)
        assert page.rect.height == pytest.approx(612, abs=1)
        assert len(page.get_drawings()) > 10
        assert page.get_images() == []  # editor is never flattened to a bitmap
        assert 'Equilibrium' in page.get_text()
        pixmap = page.get_pixmap()
        assert len(set(pixmap.samples[::83])) > 4
    custom = tmp_path / 'custom.pdf'
    export_pdf(scene, custom, ExportOptions(page_size='Custom', custom_width_mm=180,
                                           custom_height_mm=240, landscape=False))
    with pymupdf.open(custom) as document:
        assert document[0].rect.width == pytest.approx(180 / 25.4 * 72, abs=1)


def test_svg_has_paths_and_text_not_raster_image(tmp_path, scene):
    path = tmp_path / 'graph.svg'
    export_svg(scene, path, ExportOptions(width=900, height=700))
    root = ET.parse(path).getroot()
    assert root.tag.endswith('svg')
    tags = [element.tag.split('}')[-1] for element in root.iter()]
    assert 'path' in tags or 'polyline' in tags
    assert 'text' in tags
    assert 'image' not in tags


def test_dxf_preserves_geometry_metadata_layers_and_hides_objects(tmp_path, scene):
    hidden = GraphObject(kind='line', points=[[0, 9], [9, 0]], name='Hidden', visible=False)
    scene.objects.append(hidden)
    path = tmp_path / 'graph.dxf'
    export_dxf(scene, path)
    drawing = ezdxf.readfile(path)
    audit = drawing.audit()
    assert not audit.has_errors
    space = drawing.modelspace()
    assert len(space.query('LINE')) >= 2
    assert len(space.query('LWPOLYLINE')) >= 3  # curve, mathematical function, regression
    assert len(space.query('SOLID')) >= 3  # arrow and axis arrowheads
    assert len(space.query('POINT')) >= 4
    assert len(space.query('TEXT')) >= 4
    names = []
    for entity in space:
        if entity.has_xdata('GRAPHITE'):
            names.append(entity.get_xdata('GRAPHITE')[1].value)
    assert 'Supply' in names and 'Demand' in names and 'Hidden' not in names
    supply = next(entity for entity in space.query('LINE')
                  if entity.has_xdata('GRAPHITE') and entity.get_xdata('GRAPHITE')[1].value == 'Supply')
    assert tuple(supply.dxf.start)[:2] == pytest.approx((1, 2))
    assert tuple(supply.dxf.end)[:2] == pytest.approx((8, 7))
    assert drawing.layers.has_entry('Major Grid')


def test_dxf_function_translation_and_export_region(tmp_path):
    doc = Document()
    doc.objects = [GraphObject(kind='function', name='Translated', data={'expression': 'x', 'offset_x': 1, 'offset_y': 2})]
    path = tmp_path / 'region.dxf'
    export_dxf(doc, path, ExportOptions(bounds=(2, 4, 0, 10), axes=False, grid=False, labels=False))
    space = ezdxf.readfile(path).modelspace()
    polylines = list(space.query('LWPOLYLINE'))
    assert polylines
    points = [p for entity in polylines for p in entity.get_points()]
    assert all(2 - 1e-8 <= p[0] <= 4 + 1e-8 for p in points)
    assert all(p[1] == pytest.approx(p[0] + 1) for p in points)
    assert len(space.query('TEXT')) == 0


def test_export_errors_leave_existing_output_intact(tmp_path, scene):
    target = tmp_path / 'existing.png'
    target.write_bytes(b'original')
    with pytest.raises(ValueError):
        export_png(scene, target, ExportOptions(width=100000))
    assert target.read_bytes() == b'original'
    with pytest.raises(OSError):
        export_pdf(scene, tmp_path / 'missing' / 'graph.pdf')
    with pytest.raises(ValueError):
        export_dxf(scene, tmp_path / 'graph.dxf', ExportOptions(bounds=(4, 1, 0, 10)))


def test_dwg_reports_missing_converter_without_disguising_dxf(tmp_path, scene, monkeypatch):
    monkeypatch.setattr('graphite.export.find_oda_converter', lambda explicit=None: None)
    target = tmp_path / 'graph.dwg'
    with pytest.raises(RuntimeError, match='separately installed ODA'):
        export_dwg(scene, target)
    assert not target.exists()


def test_dwg_rejects_converter_output_that_is_actually_dxf(tmp_path, scene, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('graphite.export.find_oda_converter', lambda explicit=None: '/test/ODAFileConverter')
    def fake_converter(command, **kwargs):
        assert command[3:] == ['ACAD2018', 'DWG', '0', '1', '*.dxf']
        assert kwargs.get('shell', False) is False
        assert Path(command[1], 'drawing.dxf').is_file()
        Path(command[2], 'drawing.dwg').write_bytes(b'0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n')
        return SimpleNamespace(returncode=0, stderr='', stdout='')
    monkeypatch.setattr('graphite.export.subprocess.run', fake_converter)
    target = tmp_path / 'not-a-dwg.dwg'
    target.write_bytes(b'existing drawing')
    with pytest.raises(RuntimeError, match='not a recognized binary DWG'):
        export_dwg(scene, target)
    assert target.read_bytes() == b'existing drawing'


def test_shared_renderer_annotation_sizes_do_not_depend_on_device_dpi(scene):
    from PySide6.QtGui import QPainter
    from graphite.render import Renderer
    def render(dpi):
        image=QImage(1000,750,QImage.Format.Format_ARGB32_Premultiplied)
        image.setDotsPerMeterX(round(dpi/0.0254))
        image.setDotsPerMeterY(round(dpi/0.0254))
        image.fill(0xffffffff)
        painter=QPainter(image)
        Renderer(scene,QRectF(0,0,1000,750)).draw(painter)
        painter.end()
        return bytes(image.constBits())
    # Geometry and font layout must match at identical pixel dimensions even
    # when PNG print metadata requests a different physical DPI.
    assert render(72)==render(300)
