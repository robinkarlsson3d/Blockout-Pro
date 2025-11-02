bl_info = {
    "name" : "BlockoutPro2",
    "description" : "Addon for quickly blocking out shapes with subD, fillets, chamfers, panel-lines and custom normals",
    "author" : "Robin Karlsson",
    "version" : (2, 0, 0),
    "blender" : (4, 5, 3),
    "location" : "3DView Sidebar",
    "warning" : "",
    "support" : "COMMUNITY",
    "doc_url" : "",
    "category" : "3D View"
}

import bpy
import bmesh
from bpy.types import Mesh
from bpy.props import StringProperty
from . import bp2_functions
from . import bp2_modifiers

# --- globals ---
_suppress_update = False
_handler_registered = False
EDGE_ATTRS = ["bevel_weight_edge", "bevel_fillet_weighted"]  # define all edge attributes we want to control

# --- depsgraph handler for syncing averages ---
def depsgraph_update(_depsgraph):
    global _suppress_update

    obj = bpy.context.active_object
    if not obj or obj.type != 'MESH' or bpy.context.mode != 'EDIT_MESH':
        return
    bm = bmesh.from_edit_mesh(obj.data)
    props = bpy.context.scene.edge_props

    for attr in EDGE_ATTRS:
        layer = bm.edges.layers.float.get(attr)
        sel = [e for e in bm.edges if e.select]
        if not sel:
            continue
        avg = sum(e[layer] for e in sel) / len(sel)
        val = avg * 100.0
        if abs(getattr(props, f"{attr}_slider") - val) > 1e-6:
            _suppress_update = True
            setattr(props, f"{attr}_slider", val)
            _suppress_update = False


# --- property update callback factory ---
def make_update_callback(attr):
    def callback(self, context):
        global _suppress_update
        obj = bpy.context.active_object
        if _suppress_update:
            return
        slider_value = getattr(self, f"{attr}_slider") / 100.0
        #bp2_functions.set_selected(attr, val)

        bp2_functions.set_edge_attribute(obj, attr, value = slider_value, toggle = False)

    return callback

# --- PropertyGroup ---
class EdgeProps(bpy.types.PropertyGroup):
    bevel_weight_edge_slider: bpy.props.FloatProperty(
        name="EdgeChamfer",
        min=0.0, max=100.0, default=0.0, precision=2, subtype='PERCENTAGE',
        update=make_update_callback("bevel_weight_edge")
    ) # type: ignore
    bevel_fillet_weighted_slider: bpy.props.FloatProperty(
        name="Fillet Weight",
        min=0.0, soft_max=100.0, default=0.0, precision=2, subtype='PERCENTAGE',
        update=make_update_callback("bevel_fillet_weighted")
    ) # type: ignore

""" Add modifiers for Blockout"""
class OBJECT_OT_add_mods(bpy.types.Operator):
    bl_idname = "bp2_functions.add_mods"
    bl_label = "Add Modifiers"
    bl_options = {'REGISTER', 'UNDO'}

    attribute_name: bpy.props.StringProperty(
        name="Attribute Name",
        description="Name of the edge attribute to set",
        default="planar"
    ) # type: ignore

    def execute(self, context):
        obj = context.object
        bp2_functions.add_modifiers(self, obj, False)
        self.report({'INFO'}, "Added modifiers")
        return {'FINISHED'}

""" Toggle modifier visibility"""    
class OBJECT_OT_mods_visibility(bpy.types.Operator):
    bl_idname = "bp2_functions.mods_visibility"
    bl_label = "Modifier Visibility Toggle"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        bp2_functions.toggle_modifier_visibility(obj)
        self.report({'INFO'}, "Toggled visibility for BP modifiers")
        return {'FINISHED'}

""" Flag selected edges """
class MESH_OT_set_edge_attribute(bpy.types.Operator):
    bl_idname = "bp2_functions.set_edge_attribute"
    bl_label = "Set Edge Attribute"
    bl_options = {'REGISTER', 'UNDO'}

    attribute_name: bpy.props.StringProperty(
        name="Attribute Name",
        description="Name of the boolean edge attribute to set",
        default="chamfer"
    ) # type: ignore

    def execute(self, context):
        obj = context.object
        bp2_functions.set_edge_attribute(obj, self.attribute_name)
        self.report({'INFO'}, f"{self.attribute_name} set to True on selected edges")
        return {'FINISHED'}
    
""" Select edges"""
class MESH_OT_select_edge_attribute(bpy.types.Operator):
    bl_idname = "bp2_functions.select_by_edge_attribute"
    bl_label = "Set Edge Attribute"
    bl_options = {'REGISTER', 'UNDO'}

    attribute_name: bpy.props.StringProperty(
        name="Attribute Name",
        description="Name of the boolean edge attribute to set",
        default="chamfer"
    ) # type: ignore

    def execute(self, context):
        obj = context.object
        bp2_functions.select_by_edge_attribute(obj, self.attribute_name)
        self.report({'INFO'}, f"{self.attribute_name} set to True on selected edges")
        return {'FINISHED'}

# ---------------- Panel -----------------
class VIEW3D_PT_edge_attributes(bpy.types.Panel):
    bl_label = "Blockout2"
    bl_idname = "VIEW3D_PT_edge_attribute"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Blockout2"

    def draw(self, context):
        layout = self.layout
        props = context.scene.edge_props
        obj = context.active_object
        is_edit = obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'

        #MODIFIERS
        layout.label(text="Object Mode:", icon="OBJECT_DATAMODE")
        row = self.layout.row (align=True)
        row.enabled != is_edit
        button = row.operator("bp2_functions.add_mods", text="Planar", icon="CUBE");                           button.attribute_name = "Planar"
        button = row.operator("bp2_functions.add_mods", text="SubD", icon="SPHERE");                           button.attribute_name = "SubD"
        button = row.operator("bp2_functions.mods_visibility", text="", icon="HIDE_OFF")

        #EDIT TOOLS
        layout.label(text="Edit Mode:", icon="EDITMODE_HLT")
        #PANELS
        attribute = "panel_edge"         
        row = self.layout.row (align=True)
        row.enabled = is_edit
        button = row.operator("bp2_functions.set_edge_attribute", text="Panel +/-", icon="UV_EDGESEL");        button.attribute_name = attribute
        button = row.operator("bp2_functions.select_by_edge_attribute", text="", icon="RESTRICT_SELECT_OFF");  button.attribute_name = attribute

        #EDGE CHAMFERS
        attribute = "bevel_weight_edge" 
        row = self.layout.row (align=True)
        row.enabled = is_edit
        button = row.operator("bp2_functions.set_edge_attribute", text="EdgeChamfer +/-", icon="MOD_BEVEL");   button.attribute_name = attribute
        button = row.operator("bp2_functions.select_by_edge_attribute", text="", icon="RESTRICT_SELECT_OFF");  button.attribute_name = attribute
        
        #CHAMFER SLIDER
        #row = self.layout.row (align=True)
        #slider = row.prop(props, "edgechamfer_slider", slider=True)
        #button = row.operator("bp2_functions.select_by_edge_attribute", text="", icon="RESTRICT_SELECT_OFF");  button.attribute_name = attribute
        for attr in EDGE_ATTRS:
            row = self.layout.row (align=True)
            row.enabled = is_edit
            row.prop(props, f"{attr}_slider", slider=True)
        
        #FILLET SLIDER
        #row = self.layout.row (align=True)
        #col.prop(props, "crease_slider", slider=True)

        #CONSTRAINED FILLETS
        attribute = "bevel_fillet_constrained" 
        row = self.layout.row (align=True)
        row.enabled = is_edit
        button = row.operator("bp2_functions.set_edge_attribute", text="Constrained Fillet +/-", icon="SPHERECURVE"); button.attribute_name = attribute
        button = row.operator("bp2_functions.select_by_edge_attribute", text="", icon="RESTRICT_SELECT_OFF");         button.attribute_name = attribute

        #SHARP EDGES
        attribute = "sharp_edge"
        row = self.layout.row (align=True)
        row.enabled = is_edit
        button = row.operator("bp2_functions.set_edge_attribute", text="Sharp Edge +/-", icon="SHARPCURVE");                      button.attribute_name = attribute
        button = row.operator("bp2_functions.select_by_edge_attribute", text="", icon="RESTRICT_SELECT_OFF");  button.attribute_name = attribute

        #UV_DATA
        #Auto-UV
# ---------------- Registration -----------------
classes = (
    VIEW3D_PT_edge_attributes,
    MESH_OT_set_edge_attribute,
    MESH_OT_select_edge_attribute,
    OBJECT_OT_add_mods,
    OBJECT_OT_mods_visibility,
    EdgeProps,
)

def register():
    global _handler_registered
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass  # Already registered

    bpy.types.Scene.edge_props = bpy.props.PointerProperty(type=EdgeProps)
    if not _handler_registered:
        bpy.app.handlers.depsgraph_update_post.append(depsgraph_update)
        _handler_registered = True
    
    bp2_modifiers.register()

def unregister():
    global _handler_registered
    if _handler_registered and depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update)
        _handler_registered = False

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    
    if hasattr(bpy.types.Scene, "edge_props"):
        del bpy.types.Scene.edge_props
    
    bp2_modifiers.unregister()

if __name__ == "__main__":
    register()