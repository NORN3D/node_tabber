# Node Tabber 0.4.0

Blender 5.2 compatibility update. Press **Tab** in a node editor to search for
nodes, their operations, and local node groups. **Ctrl+Tab** edits a node group.

## Install

In Blender, open **Edit > Preferences > Add-ons**, choose **Install from Disk**
from the menu, select `NodeTabber-0.4.0-Blender5.2.zip`, and enable **Node Tabber**.
Disable an older installed copy first to avoid duplicate Tab bindings.

## Compatibility

The 5.2 catalogs were generated and tested with Blender **5.2.3 LTS**.
They cover every creatable built-in node type in Geometry, 
Shader, Compositor, and legacy Texture node trees. Simulation, Repeat,
For Each Geometry Element, and Closure entries create paired zone endpoints.
Node groups have separate entries with recursive groups excluded.

The catalogs preserve context filters for shader engines, world/object/line-style
shaders, and geometry node tools. They add new 5.2 nodes, including the XPBD
Solver, mesh bevel, list operations, and compositor additions. RNA enum values
that are unavailable on an actual node are filtered using temporary nodes in a
disposable tree; these results are cached for subsequent searches.

Search preferences, operation symbols, Mix Color/Mix RGB aliases, deprecated
node display, and usage sorting remain available. Usage tallies are saved in
Blender's user configuration folder under `node_tabber/tally_cache`. Existing
installation-folder tallies are read until superseded by a user-config tally.
