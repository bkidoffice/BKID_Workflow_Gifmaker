"""Generate the Rhino RUI sidecar. No external code or artwork is copied."""
from pathlib import Path
import base64
import uuid
import xml.etree.ElementTree as E

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = uuid.UUID('c886c737-a1ee-48ef-a7b9-a402bc1832c0')


def guid(name):
    return str(uuid.uuid5(NAMESPACE, name))


def label(parent, tag, value):
    E.SubElement(E.SubElement(parent, tag), 'locale_1033').text = value


def build():
    r = E.Element('RhinoUI', major_ver='2', minor_ver='0', guid=guid('file'),
                  localize='False', default_language_id='1033', dpi_scale='100')
    extend = E.SubElement(r, 'extend_rhino_menus')
    label(E.SubElement(extend, 'menu', guid=guid('menus')), 'text', 'Extend Rhino Menus')
    E.SubElement(r, 'menus')
    groups = E.SubElement(r, 'tool_bar_groups')
    group = E.SubElement(groups, 'tool_bar_group', guid=guid('group'),
                         dock_bar_guid32='00000000-0000-0000-0000-000000000000',
                         dock_bar_guid64=guid('dock'), active_tool_bar_group=guid('toolbar'),
                         single_file='False', hide_single_tab='True', point_floating='150,150')
    label(group, 'text', 'BKID Workflowboost')
    item = E.SubElement(group, 'tool_bar_group_item', guid=guid('toolbar'), major_version='1', minor_version='1')
    label(item, 'text', 'BKID Workflowboost')
    E.SubElement(item, 'tool_bar_id').text = guid('toolbar')
    E.SubElement(group, 'dock_bar_info', dpi_scale='100', dock_bar='False', docking='True',
                 horz='True', visible='True', floating='True', mru_float_style='8192',
                 bar_id='59395', mru_width='100', point_pos='150,150', float_point='150,150',
                 rect_mru_dock_pos='0,0,100,70', dock_location_u='0', dock_location='top', float_size='100,70')
    bars = E.SubElement(r, 'tool_bars')
    bar = E.SubElement(bars, 'tool_bar', guid=guid('toolbar'), bitmap_id=guid('icon'), item_display_style='control_only')
    label(bar, 'text', 'BKID Workflowboost')
    button = E.SubElement(bar, 'tool_bar_item', guid=guid('button'))
    label(button, 'text', 'GifMaker')
    E.SubElement(button, 'left_macro_id').text = guid('capture-hover-v2')
    E.SubElement(button, 'right_macro_id').text = guid('resolution-hover-v2')
    macros = E.SubElement(r, 'macros')
    for key, command, caption, tooltip in [
            ('capture-hover-v2', 'BKIDGifMakerCapture', 'GifMaker', '부품을 직선 이동하며 GIF 저장'),
            ('resolution-hover-v2', 'BKIDGifMakerCapture', 'GifMaker', '이동 시간·FPS·해상도 설정 후 GIF 저장')]:
        macro = E.SubElement(macros, 'macro_item', guid=guid(key), bitmap_id=guid('icon'))
        for tag, value in [('text', caption),
                           ('tooltip', tooltip),
                           ('help_text', tooltip),
                           ('button_text', caption), ('menu_text', caption)]:
            label(macro, tag, value)
        E.SubElement(macro, 'script').text = '! _' + command
    bitmaps = E.SubElement(r, 'bitmaps')
    for name, size in [('small', 16), ('normal', 24), ('large', 32)]:
        bitmap = E.SubElement(bitmaps, name + '_bitmap', item_width=str(size), item_height=str(size))
        E.SubElement(bitmap, 'bitmap_item', guid=guid('icon'), index='0')
        E.SubElement(bitmap, 'bitmap').text = base64.b64encode((ROOT / 'assets' / ('icon_%s.png' % size)).read_bytes()).decode('ascii')
    E.SubElement(r, 'scripts')
    E.indent(r)
    path = ROOT / 'plugin/BKID.GifMaker/Toolbar/BKID.GifMaker.rui'
    path.write_bytes(E.tostring(r, encoding='utf-8', xml_declaration=True))
    return path


if __name__ == '__main__':
    print(build())
