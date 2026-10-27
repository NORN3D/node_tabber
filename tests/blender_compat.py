"""Blender integration test; run with --background --factory-startup --python-exit-code 1."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('node_tabber', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
addon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = addon
spec.loader.exec_module(addon)
addon.register()
prefs = SimpleNamespace(include_subtypes=True, use_op_symbols=True,
                        show_deprecated='SHOW_AND_INDICATE', include_external_nodes=True,
                        denote_name_collisions=True, mix_color_alias='DEFAULT',
                        hide_group_selector=True, quick_place=True, sort_by_tally=False)
addon.utils.fetch_user_prefs = lambda attr_id=None: getattr(prefs, attr_id) if attr_id else prefs
addon.nodelists.poll_funcs.fetch_user_prefs = addon.utils.fetch_user_prefs
failures = []
summary = []
coverage = {}


def check_entries(tree_id, subtype='MODIFIER', shader='OBJECT', engine='CYCLES'):
    tree = bpy.data.node_groups.new('Node Tabber test', tree_id)
    space = SimpleNamespace(edit_tree=tree, node_tree=tree, tree_type=tree_id,
                            node_tree_sub_type=subtype, shader_type=shader,
                            cursor_location=Vector((50, 100)), type='NODE_EDITOR')
    context = SimpleNamespace(space_data=space, blend_data=bpy.data, engine=engine,
                              preferences=bpy.context.preferences)
    before = len(bpy.data.node_groups)
    try:
        entries = addon.nodelists.generate_entries(context, tree_id)
        coverage.setdefault(tree_id, set()).update(addon.nodelists.settings_dict[e[0]][0] for e in entries)
        assert len({item[0] for item in entries}) == len(entries), 'Duplicate enum identifiers'
        tested = 0
        for identifier, label, _ in entries:
            node_id, function, settings, sockets = addon.nodelists.settings_dict[identifier]
            try:
                kwargs = {key: value for key, value in settings.items() if isinstance(key, str)}
                nodes = getattr(addon.utils, function)(context, node_id, settings=settings,
                                                       socket_settings=sockets, **kwargs)
                assert tree.nodes.active == nodes[-1]
                assert all(n.select for n in nodes)
                if function == 'create_zone':
                    assert nodes[0].paired_output == nodes[1]
                for node in list(tree.nodes):
                    tree.nodes.remove(node)
                tested += 1
            except Exception as error:
                failures.append({'tree': tree_id, 'context': subtype + '/' + shader + '/' + engine,
                                 'node': node_id, 'label': label, 'settings': repr(settings), 'error': str(error)})
                tree.nodes.clear()
        assert len(bpy.data.node_groups) == before, 'Leaked scratch trees'
        if tree_id == 'GeometryNodeTree':
            ids = {addon.nodelists.settings_dict[e[0]][0] for e in entries}
            assert ('GeometryNodeToolSelection' in ids) == (subtype == 'TOOL')
            assert 'GeometryNodeXPBDSolver' in ids
            assert 'GeometryNodeListGetItem' in ids
        summary.append({'tree': tree_id, 'subtype': subtype, 'shader': shader, 'engine': engine,
                        'entries': len(entries), 'created': tested})
    finally:
        bpy.data.node_groups.remove(tree)


try:
    for tree_id in ('GeometryNodeTree', 'ShaderNodeTree', 'CompositorNodeTree', 'TextureNodeTree'):
        check_entries(tree_id)
    check_entries('GeometryNodeTree', 'TOOL')
    check_entries('ShaderNodeTree', shader='WORLD')
    check_entries('ShaderNodeTree', shader='OBJECT', engine='BLENDER_EEVEE')
    check_entries('ShaderNodeTree', shader='LINESTYLE')
    # Mix aliases and disabling subtypes must not leave duplicate identifiers or
    # dangling settings. Exercise every entry produced by these preferences too.
    prefs.include_subtypes = False
    prefs.mix_color_alias = 'BOTH'
    prefs.show_deprecated = 'HIDE'
    for tree_id in coverage:
        check_entries(tree_id)

    # Registered native node coverage, independent of the generated JSON lists.
    excluded = {'NodeUndefined', 'NodeCustomGroup', 'NodeImplicitConversion', 'NodeGroup',
                'GeometryNodeGroup', 'ShaderNodeGroup', 'CompositorNodeGroup', 'TextureNodeGroup'}
    classes = [getattr(bpy.types, name) for name in dir(bpy.types)]
    classes = [cls for cls in classes if isinstance(cls, type) and issubclass(cls, bpy.types.Node)
               and cls.is_registered_node_type() and cls.__name__ not in excluded]
    for tree_id, ids in coverage.items():
        tree = bpy.data.node_groups.new('Coverage probe', tree_id)
        try:
            for cls in classes:
                try:
                    node = tree.nodes.new(cls.__name__)
                except (RuntimeError, TypeError):
                    continue
                tree.nodes.remove(node)
                if cls.__name__.endswith(('SimulationInput', 'SimulationOutput', 'RepeatInput', 'RepeatOutput',
                                          'ForeachGeometryElementInput', 'ForeachGeometryElementOutput',
                                          'ClosureInput', 'ClosureOutput')):
                    continue
                assert cls.__name__ in ids, f'Missing native node: {tree_id}/{cls.__name__}'
        finally:
            bpy.data.node_groups.remove(tree)

    # Nested group recursion and width/name settings.
    tree = bpy.data.node_groups.new('Active', 'GeometryNodeTree')
    good = bpy.data.node_groups.new('Independent', 'GeometryNodeTree')
    recursive = bpy.data.node_groups.new('Contains active', 'GeometryNodeTree')
    recursive.nodes.new('GeometryNodeGroup').node_tree = tree
    hidden = bpy.data.node_groups.new('.Hidden', 'GeometryNodeTree')
    context = SimpleNamespace(space_data=SimpleNamespace(edit_tree=tree, node_tree=tree,
                              cursor_location=Vector((0, 0))), blend_data=bpy.data)
    try:
        groups = addon.nodelists.generate_nodegroup_entries(context)
        names = {addon.nodelists.settings_dict[e[0]][2]['node_tree'] for e in groups}
        assert names == {'Independent'}, names
        settings = addon.nodelists.settings_dict[groups[0][0]][2]
        node, = addon.utils.create_node(context, 'GeometryNodeGroup', settings=settings,
                                        node_tree=settings['node_tree'])
        assert node.node_tree == good
        assert node.width == good.default_group_node_width
        # A bad second zone endpoint must not leave the first node behind.
        before = len(tree.nodes)
        try:
            addon.utils.create_zone(context, input_type='GeometryNodeSimulationInput',
                                    output_type='NoSuchNode', settings={})
        except RuntimeError:
            pass
        assert len(tree.nodes) == before
    finally:
        for group in (recursive, hidden, tree, good):
            bpy.data.node_groups.remove(group)
finally:
    addon.unregister()
report = {'blender': bpy.app.version_string, 'summary': summary,
          'native_coverage': {key: len(value) for key, value in coverage.items()}, 'failures': failures}
(ROOT / 'tests' / 'compat-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
assert not failures, f'{len(failures)} search entries failed'
print('NODE TABBER COMPATIBILITY PASS')
