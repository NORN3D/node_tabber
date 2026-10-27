"""Run with Blender --background --factory-startup --python tools/generate_catalog.py.

Preserves curated aliases, zones, and context filters, then fills gaps from the
running Blender's registered native node types. Never modifies a user's file.
"""
import json
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
VERSION = '.'.join(map(str, bpy.app.version[:2]))
ENUMS = {'operation', 'data_type', 'mode', 'domain', 'input_type', 'axis',
         'blend_type', 'distribution', 'interpolation_type', 'solver',
         'transform_space', 'rotation_type', 'warning_type'}


def main():
    destination = ROOT / 'nodelists' / VERSION
    destination.mkdir(exist_ok=True)
    classes = [getattr(bpy.types, name) for name in dir(bpy.types)]
    classes = [cls for cls in classes if isinstance(cls, type)
               and issubclass(cls, bpy.types.Node) and cls.is_registered_node_type()]
    for tree_id in ('GeometryNodeTree', 'ShaderNodeTree', 'CompositorNodeTree', 'TextureNodeTree'):
        data = json.loads((ROOT / 'nodelists' / '5.0' / f'{tree_id}.json').read_text())
        tree = bpy.data.node_groups.new('Node Tabber catalog probe', tree_id)
        valid = {}
        try:
            # Blender's shared function/layout nodes report poll=False even when
            # nodes.new supports them, so check actual creation in a scratch tree.
            for cls in classes:
                name = cls.__name__
                if name in {'NodeUndefined', 'NodeCustomGroup', 'NodeImplicitConversion'}:
                    continue
                try:
                    node = tree.nodes.new(name)
                except (RuntimeError, TypeError):
                    continue
                valid[name] = [p.identifier for p in node.bl_rna.properties
                               if p.type == 'ENUM' and not p.is_readonly and p.identifier in ENUMS
                               and len(p.enum_items) > 1]
                tree.nodes.remove(node)
            covered = set()
            for section in data.values():
                kept = []
                for item in section['entries']:
                    name, props = (item, {}) if isinstance(item, str) else item[:2]
                    if props.get('function') == 'create_zone':
                        if all(props['settings'][key] in valid for key in ('input_type', 'output_type')):
                            kept.append(item)
                            covered.update(props['settings'][key] for key in ('input_type', 'output_type'))
                        continue
                    if name not in valid:
                        continue
                    kept.append(item)
                    covered.add(name)
                section['entries'] = kept
            # Lists are no longer gated behind the old experimental preference.
            if 'list_nodes' in data:
                data['list_nodes'].pop('poll', None)
            missing = []
            for name, enums in sorted(valid.items()):
                if name in covered or name.endswith('NodeGroup') or name in {'NodeGroup', 'NodeGroupInput', 'NodeGroupOutput'}:
                    continue
                # Zone endpoints are represented by paired zone entries.
                if name.endswith(('SimulationInput', 'SimulationOutput', 'RepeatInput', 'RepeatOutput',
                                  'ForeachGeometryElementInput', 'ForeachGeometryElementOutput',
                                  'ClosureInput', 'ClosureOutput')):
                    continue
                props = {'subtypes': [enum]} if (enum := next(iter(enums), None)) else {}
                # Expose each enum independently; avoid invalid Cartesian products.
                missing.append([name, props] if props else name)
                for enum in enums[1:]:
                    missing.append([name, {'only_subtypes': True, 'subtypes': [enum]}])
            data['runtime_additions'] = {'entries': missing}
            (destination / f'{tree_id}.json').write_text(json.dumps(data, indent=4) + '\n', encoding='utf-8')
            print('CATALOG', tree_id, len(valid), 'native types;', len(missing), 'new entries')
        finally:
            bpy.data.node_groups.remove(tree)


if __name__ == '__main__':
    main()
