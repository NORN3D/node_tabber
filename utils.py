import json

import bpy
from bpy import context
from pathlib import Path
from dataclasses import dataclass

ADDON_FOLDER = Path(__file__).parent
TALLY_FOLDER = Path(bpy.utils.user_resource('CONFIG')) / 'node_tabber' / 'tally_cache'


def read_tallies(tree_type):
    path = fetch_tally_path(tree_type)
    if not path.exists():
        path = ADDON_FOLDER / 'tally_cache' / f'{tree_type}.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return {key: value for key, value in data.items()
                if isinstance(value, (int, float))} if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


@dataclass(frozen=True)
class Socket:
    name : str
    
    
nodes_with_op_symbols = [
    "ShaderNodeMath",
    "CompositorNodeMath",
    "TextureNodeMath",
    "ShaderNodeVectorMath",
    "FunctionNodeBooleanMath",
    "FunctionNodeIntegerMath",
    "FunctionNodeCompare",
]

op_symbol_dict = {
    "Add": "+",
    "Subtract": "-",
    "Multiply": "*",
    "Divide": "/",
    "Multiply Add": "*+",
    "Power": "^",
    "Exponent": "e^",
    "Less Than": "<",
    "Less Than or Equal": "<=",
    "Greater Than": ">",
    "Greater Than or Equal": ">=",
    "Scale": "*",
    "Cross Product": "x",
    "And": "^",
    "Or": "v",
    "Not": "!",
    "Not And": "!^",
    "Nor": "!v",
    "Equal": "=",
    "Not Equal": "!=",
    "Imply": "->",
}


def add_op_symbols(operation):
    op_symbol = op_symbol_dict.get(operation)
    if op_symbol is not None:
        return f"{operation} ({op_symbol})"

    return operation


def fetch_tally_path(tree_type):
    return Path(TALLY_FOLDER, f"{tree_type}.json")


def fetch_user_prefs(attr_id=None):
    prefs = context.preferences.addons[__package__].preferences
    if attr_id is None:
        return prefs
    else:
        return getattr(prefs, attr_id)


def sort_enum_items(tree_type, items):
    tally_dict = read_tallies(tree_type)
    items.sort(key=lambda x: tally_dict.get(x[0], 0), reverse=True)


def update_tally(context, entry):
    prefs = fetch_user_prefs()
    tree_type = context.space_data.tree_type

    path = fetch_tally_path(tree_type)
    tally_dict = read_tallies(tree_type)

    tally_dict[entry] = min(tally_dict.get(entry, 0) + 1, prefs.tally_max)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(tally_dict, indent=4), encoding='utf-8')
    except OSError as error:
        print(f'Node Tabber: could not save search tally: {error}')


def fetch_active_nodetree(context):
    edit_tree = getattr(context.space_data, 'edit_tree', None)
    node_tree = getattr(context.space_data, 'node_tree', None)

    if edit_tree is not None:
        return edit_tree
    else:
        return node_tree


def apply_node_settings(node, settings, socket_settings=None):
    for key, value in (settings or {}).items():
        if isinstance(key, Socket):
            node.inputs[key.name].default_value = value
        elif key != 'node_tree':
            setattr(node, key, value)
    for key, value in (socket_settings or {}).items():
        node.inputs[key].default_value = value


def create_node(context, node_type=None, *_, node_tree=None, socket_settings=None, settings, **keyword_settings):
    tree = fetch_active_nodetree(context)
    node = tree.nodes.new(type=node_type)
    prefs = fetch_user_prefs()

    try:
        apply_node_settings(node, settings, socket_settings)

        if node_tree is not None:
            node.node_tree = context.blend_data.node_groups.get(node_tree)
            node.show_options = not prefs.hide_group_selector

        node.location = context.space_data.cursor_location
        return make_selection(context, nodes=(node,))

    except Exception as error:
        tree.nodes.remove(node)
        raise error


def create_zone(context, *_, input_type=None, output_type=None, offset=(150, 0), socket_settings=None, settings, **keyword_settings):
    tree = fetch_active_nodetree(context)
    input_node = output_node = None
    link_geo_socket = settings.get("link_geo_socket", True)

    try:
        input_node = tree.nodes.new(type=input_type)
        output_node = tree.nodes.new(type=output_type)
        # Simulation input must be paired with the output.
        input_node.pair_with_output(output_node)

        for node in (input_node, output_node):
            node.location = context.space_data.cursor_location

        x_offset, y_offset = offset
        input_node.location.x -= x_offset
        input_node.location.y -= y_offset
        output_node.location.x += x_offset
        output_node.location.y += y_offset

        # Connect geometry sockets by default.
        # Get the sockets by their types, because the name is not guaranteed due to i18n.
        if link_geo_socket:
            from_socket = next(s for s in input_node.outputs if s.type == "GEOMETRY")
            to_socket = next(s for s in output_node.inputs if s.type == "GEOMETRY")
            tree.links.new(to_socket, from_socket)

        return make_selection(context, nodes=(input_node, output_node))

    except Exception as error:
        for node in (input_node, output_node):
            if node is not None:
                tree.nodes.remove(node)
        raise error


def make_selection(context, nodes):
    tree = fetch_active_nodetree(context)
    # select only the new node
    for n in tree.nodes:
        n.select = False

    for n in nodes:
        n.select = True

    tree.nodes.active = nodes[-1]
    return nodes
