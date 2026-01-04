bl_info = {
    "name" : "Blockout Pro",
    "description" : "Addon for quickly blocking out shapes with subD, fillets, chamfers, panel-lines and custom normals",
    "author" : "Robin Karlsson",
    "version" : (2, 0, 0),
    "blender" : (5, 0, 0),
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
from . import bp_functions
from . import bp_modifiers

# --- globals ---
_suppress_update = False
_handler_registered = False

# --- depsgraph handler for syncing averages ---
def depsgraph_update(_depsgraph):
    global _suppress_update

    obj = bpy.context.active_object

    #Early cancel if no object/mesh selected or if you're outside of editmode
    if not obj or obj.type != 'MESH' or bpy.context.mode != 'EDIT_MESH':
        return
    bm = bmesh.from_edit_mesh(obj.data)
    props = bpy.context.scene.edge_props

    for attr in ["bevel_weight_edge", "bp_bevel_fillet_weighted"]:
        layer = bm.edges.layers.float.get(attr)
        sel = [e for e in bm.edges if e.select]

        #Early cancel if no selection or missing attribute
        if not sel or layer is None:
            continue
        
        avg = sum(e[layer] for e in sel) / len(sel)
        val = avg * 100.0

        #Only update if value is meaningfully different (not float-error, etc.)
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
        #bp_functions.set_selected(attr, val)

        bp_functions.set_edge_attribute(attribute_name = attr, value = slider_value, toggle = False)

    return callback

# --- PropertyGroup ---
class EdgeProps(bpy.types.PropertyGroup):
    bevel_weight_edge_slider: bpy.props.FloatProperty(
        name="EdgeChamfer",
        min=0.0, max=100.0, default=0.0, precision=2, subtype='PERCENTAGE',
        update=make_update_callback("bevel_weight_edge")
    ) # type: ignore
    bp_bevel_fillet_weighted_slider: bpy.props.FloatProperty(
        name="Fillet Weight",
        min=0.0, soft_max=100.0, default=0.0, precision=2, subtype='PERCENTAGE',
        update=make_update_callback("bp_bevel_fillet_weighted")
    ) # type: ignore

# ---------------- Add Modifiers -----------------
class OBJECT_OT_add_modifiers(bpy.types.Operator):
    bl_idname = "bp.add_modifiers"
    bl_label = "Add Modifiers"
    bl_description = "Add planar or subD modifiers to selected objects \nHold Shift to add simplified stack"
    bl_options = {'REGISTER', 'UNDO'}

    simplifiedStack: bpy.props.BoolProperty(name="Use Simplified Stack", 
        description="Skips weighted and constrained fillets as well as Auto-UV", 
        default=False) # type: ignore
    
    addSubD: bpy.props.BoolProperty(name="SubD", 
        description="Include modifiers for SubD", 
        default=False) # type: ignore
    
    addFilletConstrained: bpy.props.BoolProperty(name="Constrained Fillet", 
        description="Include modifiers for constrained fillets", 
        default=True) # type: ignore
    
    addFilletWeighted: bpy.props.BoolProperty(name="Weighted Fillet", 
        description="Include modifiers for weighted fillets", 
        default=True) # type: ignore
    
    addPanelling: bpy.props.BoolProperty(name="Panelling", 
        description="Include modifiers for panelling", 
        default=True) # type: ignore
    
    addEdgeChamfer: bpy.props.BoolProperty(name="Edge Chamfer", 
        description="Include modifiers for edgechamfers", 
        default=True) # type: ignore
    
    addAutoUV: bpy.props.BoolProperty(name="Auto-UV (Experimental)", 
        description="Include modifiers for Auto-UV", 
        default=False) # type: ignore
    
    addShrinkwrap: bpy.props.BoolProperty(name="Shrinkwrap (Experimental)", 
        description="Include modifiers for shrinkwrap", 
        default=False) # type: ignore



    def execute(self, context):
        bp_functions.add_modifiers(self)
        self.report({'INFO'}, "Added planar modifiers")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        if event.shift:
           self.simplifiedStack = True
        else:
            self.simplifiedStack = False

        return self.execute(context)
    
    def draw(self, context):
        layout = self.layout

        layout.prop(self, "simplifiedStack")
        layout.prop(self, "addSubD")
        layout.prop(self, "addFilletConstrained")
        layout.prop(self, "addFilletWeighted")
        layout.prop(self, "addPanelling")
        layout.prop(self, "addEdgeChamfer")
        layout.prop(self, "addAutoUV")
        layout.prop(self, "addShrinkwrap")

# ---------------- Modifier Visibility -----------------  
class OBJECT_OT_mods_visibility(bpy.types.Operator):
    bl_idname = "bp.modifier_visibility"
    bl_label = "Modifier Visibility Toggle"
    bl_description = "Toggle visibility for BP modifiers on/off"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.toggle_modifier_visibility()
        self.report({'INFO'}, "Toggled visibility for BP modifiers")
        return {'FINISHED'}
    
# ---------------- SmartMirror -----------------
class OBJECT_OT_smart_mirror(bpy.types.Operator):
    bl_idname = "bp.smart_mirror"
    bl_label = "Perform Smart Mirror"
    bl_description = "Mirror by hierarchy root helper \nHold Shift to mirror by immediate parent helper instead of root"
    bl_options = {'REGISTER', 'UNDO'}

    mirrorByRoot: bpy.props.BoolProperty(name="Mirror by root object", 
        description="Use root object instead of direct parent", 
        default=True) # type: ignore
    
    mirrorX: bpy.props.BoolProperty(name="X-axis", 
        description="Mirror along the X-axis", 
        default=False) # type: ignore
    mirrorY: bpy.props.BoolProperty(name="Y-axis", 
        description="Mirror along the Y-axis", 
        default=True) # type: ignore
    mirrorZ: bpy.props.BoolProperty(name="Z-axis", 
        description="Mirror along the Z-axis", 
        default=False) # type: ignore

    def execute(self, context):
        bp_functions.smart_mirror(self)
        self.report({'INFO'}, "SmartMirrored")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        if event.shift:
            self.mirrorByRoot = False
        else:
            self.mirrorByRoot = True

        return self.execute(context)
    
    def draw(self, context):
        layout = self.layout

        layout.prop(self, "mirrorByRoot")
        layout.prop(self, "mirrorX")
        layout.prop(self, "mirrorY")
        layout.prop(self, "mirrorZ")
        

# ---------------- Set -----------------
class MESH_OT_set_edge_panel(bpy.types.Operator):
    bl_idname = "bp.set_edge_panel"
    bl_label = "Panel +/-"
    bl_description = "Toggles the panel edge property on/off on selected edges"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.set_edge_attribute(attribute_name = "bp_panel_edge")
        return {'FINISHED'}
    
class MESH_OT_set_edge_chamfer(bpy.types.Operator):
    bl_idname = "bp.set_edge_chamfer"
    bl_label = "Edge Chamfer +/-"
    bl_description = "Toggles the edgechamfer property on/off on selected edges"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.set_edge_attribute(attribute_name = "bevel_weight_edge")
        return {'FINISHED'}
    
class MESH_OT_set_edge_fillet_constrained(bpy.types.Operator):
    bl_idname = "bp.set_edge_fillet_constrained"
    bl_label = "Constrained Fillet  +/-"
    bl_description = "Toggles the fillet constrained property on/off on selected edges"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.set_edge_attribute(attribute_name = "bp_bevel_fillet_constrained")
        return {'FINISHED'}
    
class MESH_OT_set_edge_fillet_weighted(bpy.types.Operator):
    bl_idname = "bp.set_edge_fillet_weighted"
    bl_label = "Weighted Fillet  +/-"
    bl_description = "Toggles the weighted fillet property on/off on selected edges"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.set_edge_attribute(attribute_name = "bp_bevel_fillet_weighted")
        return {'FINISHED'}

class MESH_OT_set_edge_sharp(bpy.types.Operator):
    bl_idname = "bp.set_edge_sharp"
    bl_label = "Sharp Edge +/-"
    bl_description = "Toggles the sharp edges property on/off on selected edges"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.set_edge_attribute(attribute_name = "sharp_edge")
        return {'FINISHED'}

# ---------------- Select -----------------
class MESH_OT_select_edge_panel(bpy.types.Operator):
    bl_idname = "bp.select_edge_panel"
    bl_label = "Select Edge By Attribute"
    bl_description = "Selects all edges flagged for panelling"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.select_by_edge_attribute(attribute_name = "bp_panel_edge")
        return {'FINISHED'}
    
class MESH_OT_select_edge_chamfer(bpy.types.Operator):
    bl_idname = "bp.select_edge_chamfer"
    bl_label = "Select EdgeChamfer"
    bl_description = "Selects all edges flagged for edgechamfers"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.select_by_edge_attribute(attribute_name = "bevel_weight_edge")
        return {'FINISHED'}
    
class MESH_OT_select_edge_fillet_constrained(bpy.types.Operator):
    bl_idname = "bp.select_edge_fillet_constrained"
    bl_label = "Select Constrained Filleted Edges"
    bl_description = "Selects all edges flagged for constrained fillets"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.select_by_edge_attribute(attribute_name = "bp_bevel_fillet_constrained")
        return {'FINISHED'}
    
class MESH_OT_select_edge_fillet_weighted(bpy.types.Operator):
    bl_idname = "bp.select_edge_fillet_weighted"
    bl_label = "Select Weighted Filleted Edges"
    bl_description = "Selects all edges flagged for weighted fillets"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.select_by_edge_attribute(attribute_name = "bp_bevel_fillet_weighted")
        return {'FINISHED'}
    
class MESH_OT_select_edge_sharp(bpy.types.Operator):
    bl_idname = "bp.select_edge_sharp"
    bl_label = "Select Sharp Edges"
    bl_description = "Selects all edges flagged for sharp edges"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.select_by_edge_attribute(attribute_name = "sharp_edge")
        return {'FINISHED'}

# ---------------- Apply -----------------
class MESH_OT_apply_fillet_constrained(bpy.types.Operator):
    bl_idname = "bp.apply_fillet_constrained"
    bl_label = "Apply Constrained Fillet"
    bl_description = "Collapses and applies constrained fillets destructively to selected edges using modifier settings, also unflags the edge properties"
    bl_options = {'REGISTER', 'UNDO'}

    bevel_segments: bpy.props.IntProperty(name="Bevel Segments", 
        description="", 
        default=10) # type: ignore

    def execute(self, context):
        bp_functions.apply_attribute(attribute_name = "bp_bevel_fillet_constrained", bevel_segments=self.bevel_segments)
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.bevel_segments = bpy.context.object.modifiers.get(" BP_Bevel_Constrained").segments
        return self.execute(context)
    
class MESH_OT_apply_fillet_weighted(bpy.types.Operator):
    bl_idname = "bp.apply_fillet_weighted"
    bl_label = "Apply Weighted Fillet"
    bl_description = "Collapses and applies weighted fillets destructively to selected edges, also unflags the edge properties"
    bl_options = {'REGISTER', 'UNDO'}

    bevel_segments: bpy.props.IntProperty(name="Bevel Segments", 
        description="", 
        default=10) # type: ignore
    bevel_width: bpy.props.FloatProperty(name="Bevel Width", 
        description="", 
        default=1.0) # type: ignore

    def execute(self, context):
        bp_functions.apply_attribute(attribute_name = "bp_bevel_fillet_weighted", 
            bevel_segments=self.bevel_segments, bevel_width=self.bevel_width)
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.bevel_segments = bpy.context.object.modifiers.get(" BP_Bevel_Weighted").segments
        self.bevel_width = bpy.context.object.modifiers.get(" BP_Bevel_Weighted").width
        return self.execute(context)
    
class MESH_OT_apply_edge_chamfer(bpy.types.Operator):
    bl_idname = "bp.apply_edge_chamfer"
    bl_label = "Apply Edge Chamfer"
    bl_description = "Collapses and applies edge chamfer destructively to selected edges, also unflags the edge properties"
    bl_options = {'REGISTER', 'UNDO'}

    bevel_segments: bpy.props.IntProperty(name="Bevel Segments", 
        description="", 
        default=10) # type: ignore
    bevel_width: bpy.props.FloatProperty(name="Bevel Width", 
        description="", 
        default=1.0) # type: ignore

    def execute(self, context):
        bp_functions.apply_attribute(attribute_name = "bevel_weight_edge", 
            bevel_segments=self.bevel_segments, bevel_width=self.bevel_width)
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.bevel_segments = bpy.context.object.modifiers.get(" BP_EdgeChamfer").segments
        self.bevel_width = bpy.context.object.modifiers.get(" BP_EdgeChamfer").width
        return self.execute(context)
    
class MESH_OT_apply_panel(bpy.types.Operator):
    bl_idname = "bp.apply_panel"
    bl_label = "Apply Panel Edges"
    bl_description = "Collapses and applies panel edges destructively to selected edges, also unflags the edge properties"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.apply_attribute(attribute_name = "bp_panel_edge")
        return {'FINISHED'}

class MESH_OT_apply_sharp(bpy.types.Operator):
    bl_idname = "bp.apply_sharp"
    bl_label = "Apply Sharp Edges"
    bl_description = "Collapses and applies sharp edges destructively to selected edges, also unflags the edge properties"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bp_functions.apply_attribute(attribute_name = "sharp_edge")
        return {'FINISHED'}

# ---------------- Panel -----------------
class VIEW3D_PT_bp_panel(bpy.types.Panel):
    bl_label = "Blockout Pro"
    bl_idname = "VIEW3D_PT_bp_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Blockout Pro"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        if not hasattr(scene, "edge_props"):
            layout.label(text="Blockout not initialized")
            return

        props = context.scene.edge_props
        obj = context.active_object
        is_edit = bp_functions.isEditMode()

        #MODIFIERS
        layout.label(text="Object Mode:", icon="OBJECT_DATAMODE")
        row = self.layout.row (align=True)
        row.enabled != is_edit

        #ADD MODS
        button = row.operator("bp.add_modifiers", text="Planar", icon="CUBE")
        button.addSubD = False
        button = row.operator("bp.add_modifiers", text="SubD", icon="SPHERE")
        button.addSubD = True

        #Visibility
        row.operator("bp.modifier_visibility", text="", icon="HIDE_OFF")

        #MIRROR TOOLS
        row = self.layout.row (align=True)
        row.enabled != is_edit
        row.operator("bp.smart_mirror", text="SmartMirror", icon="MOD_MIRROR")

        #EDIT TOOLS
        layout.label(text="Edit Mode:", icon="EDITMODE_HLT")
        #PANELS    
        row = self.layout.row (align=True)
        row.enabled = is_edit
        row.operator("bp.set_edge_panel", text="Panel +/-", icon="UV_EDGESEL");        
        row.operator("bp.apply_panel", text="", icon="TRIA_DOWN_BAR")
        row.operator("bp.select_edge_panel", text="", icon="RESTRICT_SELECT_OFF");  

        #EDGE CHAMFERS
        row = self.layout.row (align=True)
        row.enabled = is_edit
        row.operator("bp.set_edge_chamfer", text="EdgeChamfer +/-", icon="MOD_BEVEL");   
        row.operator("bp.apply_edge_chamfer", text="", icon="TRIA_DOWN_BAR")
        row.operator("bp.select_edge_chamfer", text="", icon="RESTRICT_SELECT_OFF");  

        #EDGECHAMFER SLIDER
        row = self.layout.row (align=True)
        row.enabled = is_edit
        row.prop(props, "bevel_weight_edge_slider", slider=True)
        row.operator("bp.apply_edge_chamfer", text="", icon="TRIA_DOWN_BAR")
        row.operator("bp.select_edge_chamfer", text="", icon="RESTRICT_SELECT_OFF");   

        #FILLET SLIDER
        row = self.layout.row (align=True)
        row.enabled = is_edit
        row.prop(props, "bp_bevel_fillet_weighted_slider", slider=True)
        row.operator("bp.apply_fillet_weighted", text="", icon="TRIA_DOWN_BAR")
        row.operator("bp.select_edge_fillet_constrained", text="", icon="RESTRICT_SELECT_OFF");  

        #CONSTRAINED FILLETS
        row = self.layout.row (align=True)
        row.enabled = is_edit
        row.operator("bp.set_edge_fillet_constrained", text="Constrained Fillet +/-", icon="SPHERECURVE"); 
        row.operator("bp.apply_fillet_constrained", text="", icon="TRIA_DOWN_BAR")  
        row.operator("bp.select_edge_fillet_constrained", text="", icon="RESTRICT_SELECT_OFF");

        #SHARP EDGES
        row = self.layout.row (align=True)
        row.enabled = is_edit
        row.operator("bp.set_edge_sharp", text="Sharp Edge +/-", icon="SHARPCURVE");   
        row.operator("bp.apply_sharp", text="", icon="TRIA_DOWN_BAR")   
        row.operator("bp.select_edge_sharp", text="", icon="RESTRICT_SELECT_OFF"); 

        #UV_DATA
        #Auto-UV

# ---------------- Specials Menu -----------------
class VIEW3D_MT_bp_specials_submenu(bpy.types.Menu):
    bl_label = "Blockout Pro"
    bl_idname = "VIEW3D_MT_bp_specials_submenu"

    def draw(self, context):
        layout = self.layout
        layout.operator("bp.set_edge_panel", icon='UV_EDGESEL')
        layout.operator("bp.set_edge_chamfer", icon='MOD_BEVEL')
        layout.operator("bp.set_edge_fillet_constrained", icon='SPHERECURVE')
        layout.operator("bp.set_edge_fillet_weighted", icon='SHARPCURVE')
        
        layout.separator()

        #APPLY
        layout.operator("bp.apply_fillet_constrained")
        layout.operator("bp.apply_fillet_weighted")
        layout.operator("bp.apply_panel")

def menu_func(self, context):
    self.layout.separator()
    self.layout.menu("VIEW3D_MT_bp_specials_submenu", icon='MODIFIER')


# ---------------- Registration -----------------
classes = (
    EdgeProps,
    VIEW3D_PT_bp_panel,
    MESH_OT_set_edge_panel,
    MESH_OT_set_edge_chamfer,
    MESH_OT_set_edge_fillet_constrained,
    MESH_OT_set_edge_fillet_weighted,
    MESH_OT_set_edge_sharp,
    MESH_OT_select_edge_panel,
    MESH_OT_select_edge_chamfer,
    MESH_OT_select_edge_fillet_constrained,
    MESH_OT_select_edge_fillet_weighted,
    MESH_OT_select_edge_sharp,
    MESH_OT_apply_fillet_constrained,
    MESH_OT_apply_fillet_weighted,
    MESH_OT_apply_edge_chamfer,
    MESH_OT_apply_panel,
    MESH_OT_apply_sharp,
    OBJECT_OT_add_modifiers,
    OBJECT_OT_mods_visibility,
    OBJECT_OT_smart_mirror,
    VIEW3D_MT_bp_specials_submenu
)

def register():
    global _handler_registered
    for cls in classes:
        #try:
        bpy.utils.register_class(cls)
        #except ValueError:
        #    pass  # Already registered


    bpy.types.VIEW3D_MT_edit_mesh_context_menu.prepend(menu_func)

    bpy.types.Scene.edge_props = bpy.props.PointerProperty(type=EdgeProps)
    if not _handler_registered:
        bpy.app.handlers.depsgraph_update_post.append(depsgraph_update)
        _handler_registered = True
    
    #bp_modifiers.register()

def unregister():
    global _handler_registered
    if _handler_registered and depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update)
        _handler_registered = False

    for cls in reversed(classes):
        #try:
        bpy.utils.unregister_class(cls)
        #except Exception:
        #    pass

    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(menu_func)

    
    if hasattr(bpy.types.Scene, "edge_props"):
        del bpy.types.Scene.edge_props
    
    #bp_modifiers.unregister()

if __name__ == "__main__":
    register()