import bpy
import math
import os

from bpy.types import Mesh

from . import bp2_helpers as bp2

print(bpy.app.handlers.depsgraph_update_post)

_prev_mod_counts = {}

def move_new_modifier_before_bp2(obj):
    """Moves the newest modifier to appear just before the first 'BP2' modifier (if any)."""
    mods = obj.modifiers
    if not mods:
        return
    
    # Find which modifier is new compared to previous snapshot
    prev_names = _prev_mod_counts.get(obj.name, [])
    new_mods = [m for m in mods if m.name not in prev_names]
    if not new_mods:
        return

    for new_mod in new_mods:
        # Find first BP2 modifier
        bp2_mods = [m for m in mods if "bp2" in m.name.lower()]
        
        if not bp2_mods or new_mod.name.lower().find("bp2") != -1:
            continue

        first_bp2 = bp2_mods[0]

        # Move the new modifier until it's right before the first BP2
        while mods.find(new_mod.name) > mods.find(first_bp2.name):
            #bpy.ops.object.modifier_move_up({"object": obj}, modifier=new_mod.name)
            bpy.ops.object.modifier_move_up(modifier=new_mod.name)
        print("Moved new modifier")

def depsgraph_modifier_update_handler(scene, depsgraph):
    global _prev_mod_counts

    active = bpy.context.view_layer.objects.active
    if not active or active.type != "MESH":
        return

    prev_names = _prev_mod_counts.get(active.name, [])
    current_names = [m.name for m in active.modifiers]

    if len(current_names) > len(prev_names):
        print("New modifier detected on", active.name)
        move_new_modifier_before_bp2(active)

    _prev_mod_counts[active.name] = current_names

def reimport_nodegroup(self, node_name: str , force_reimport: bool = False, report=None):
    addon_path = os.path.dirname(__file__)
    blendfile_path = os.path.join(addon_path, "bp2_nodes.blend")

    try:
        edit_mode = bpy.context.mode == 'EDIT_MESH'
        if edit_mode == True:
            bpy.ops.object.mode_set(mode='OBJECT')

        #Rename old nodes
        for nodegroup in bpy.data.node_groups: 
            if nodegroup.name == node_name:
                nodegroup.name += "_temp_"

        #Load new node
        if blendfile_path is not None and os.path.exists(blendfile_path) == True:
            with bpy.data.libraries.load(blendfile_path, link=False) as (data_from, data_to):
                if node_name in data_from.node_groups:
                    data_to.node_groups.append(node_name)
                else:
                    self.report({"WARNING"}, f"Geometry node '{node_name}' not found")
                    return []
        else:
            self.report({"WARNING"}, "Failed to find blendfile to import nodes from")
            return []
        
        #Remap old nodes to newly imported one then delete old ones
        for nodegroup in bpy.data.node_groups: 
            if node_name and "_temp_" in nodegroup.name:
                nodegroup.user_remap(bpy.data.node_groups[node_name])
                nodegroup.user_clear()
                bpy.data.node_groups.remove(nodegroup)

        #Restore edit mode
        if edit_mode == True:
            bpy.ops.object.mode_set(mode='EDIT')

        print("Successfully replaced " + node_name + " with the reimported version.")
        
    except Exception as e:
        self.report({"WARNING"}, f"Failed to load {node_name} due to error: + {e}")

    return True

def reimport_nodegroups(self, force_reimport: bool = False):
    reimport_nodegroup(self, "BP2_SubD")
    reimport_nodegroup(self, "BP2_PanelSplit")
    reimport_nodegroup(self, "BP2_AutoUV")
    reimport_nodegroup(self, "BP2_EdgeDetect")

    return {'FINISHED'}

def verify_attributes_exist(obj: Mesh):
    #Set Object Mode
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    

    attributes: bpy.types.Attribute = obj.data.attributes
    uv_layers: bpy.types.MeshUVLoopLayer = obj.data.uv_layers
    #color_layers: bpy.types.MeshLoopColorLayer = obj.data
    #bpy.ops.geometry.color_attribute_add(name="Color")


    #mesh.attributes.new(name=uv_name, type='FLOAT2', domain='CORNER')
    #Fix up any existing UV Layers
    if len(uv_layers) == 1 and uv_layers[0].name != "UVMap":
        uv_layers[0].name = "UVMap"  
    
    for uv_layer in uv_layers:
        #uv_layer.type = 'VECTOR2D'
        #uv_layer.type = 'FLOAT2'
        #uv_layer.domain = 'CORNER'
        pass

    #Add native attributes if missing
    if "UVMap" not in attributes:
        attributes.new(name="UVMap", type='FLOAT2', domain='CORNER')
        #attributes.new(name="UVMap", type='VECTOR2D', domain='FACE_CORNER')
    if "sharps_edge" not in attributes:
        attributes.new(name="sharps_edge", type='BOOLEAN', domain='EDGE')
    if "uv_seam" not in attributes:
        attributes.new(name="uv_seam", type='BOOLEAN', domain='EDGE')
    if "bevel_weight_edge" not in attributes:
        attributes.new(name="bevel_weight_edge", type='FLOAT', domain='EDGE')
    if "crease_edge" not in attributes:
        attributes.new(name="crease_edge", type='FLOAT', domain='EDGE')
    if "crease_verts" not in attributes:
        attributes.new(name="crease_verts", type='FLOAT', domain='POINT')

    #Add custom attributes if missing
    if "bevel_fillet_weighted" not in attributes:
        attributes.new(name="bevel_fillet_weighted", type='FLOAT', domain='EDGE')
    if "bevel_fillet_constrained" not in attributes:
        attributes.new(name="bevel_fillet_constrained", type='BOOLEAN', domain='EDGE')
    if "panel_edge" not in attributes:
        attributes.new(name="panel_edge", type='BOOLEAN', domain='EDGE')

    #Clear custom normals
    #bpy.ops.mesh.customdata_custom_splitnormals_clear()

       
    return {'FINISHED'} 

def setup_modifier(self, obj, name: str, modifierType: str, settings: dict):
    if not name in obj.modifiers:
        sortingPrefix = " "
        namePrefix = "BP2_"

        name = namePrefix + name

        print("Setting up mod: " + namePrefix + name)

        #Add modifiers as either geonodes or default mod
        if modifierType == "NODES":
            #Re-import geonodes if missing for whatever reason
            if bpy.data.node_groups.find(name) == -1:
                reimport_nodegroup(self, name)

            mod = obj.modifiers.new(name=name, type='NODES')
            mod.node_group = bpy.data.node_groups.get(name)
        else:
            mod = obj.modifiers.new(name, modifierType)

        #Default generic modifier properties
        setattr(mod, "name", sortingPrefix + name)
        setattr(mod, "show_expanded", False)
        setattr(mod, "show_in_editmode", True)
        setattr(mod, "show_viewport", True)
        setattr(mod, "show_render", True)

        #Apply properties from dictionary
        for key, value in settings.items():
            try:
                setattr(mod, key, value)
            except AttributeError:
                print("Error on modifier: " + name + " attribute " + key)
                mod[key] = value  # fallback for custom props like sockets
            #setattr(mod, key, value)

        print("Added modifier: " + name)
    else:
        print("Modifier " + name + " already found, thus skipped")
    
    return {"FINISHED"}

def add_mod_subD(self, obj):
    subd_level = bpy.context.scene.get("BP2_settings_subd_levels", 2)
    setup_modifier(self, obj, name = "BP2_SubD", modifierType = "NODES", settings = {
        #"Socket_4": subd_level,
        #"level": subd_level
    })

    return {"FINISHED"}

def add_mod_constrainedFillets(self, obj):
    constrainedfillet_segments = bpy.context.scene.get("BP2_settings_constrainedfillet_segments", 12) #10 Segments by default
    setup_modifier(self, obj, name = "Bevel_Constrained", modifierType = "BEVEL", settings = {
        "width": 100,
        "segments": constrainedfillet_segments,
        "offset_type": "PERCENT",
        "limit_method": "WEIGHT",
        "use_clamp_overlap": False,
        "loop_slide": True,
        "miter_outer": "MITER_ARC",
        "face_strength_mode": "FSTR_ALL",
        "edge_weight": "bevel_fillet_constrained"
    })

    setup_modifier(self, obj, "Weld", modifierType = "WELD", settings = {
        "mode": "CONNECTED",
    })

    return {"FINISHED"}

def add_mod_weightedFillets(self, obj):
    weightedfillet_width = bpy.context.scene.get("BP2_settings_weightedfillet_width", 50)       #Default width of 50
    weightedfillet_segments = bpy.context.scene.get("BP2_settings_weightedfillet_segments", 10) #10 Segments by default

    setup_modifier(self, obj, name = "Bevel_Weighted", modifierType = "BEVEL", settings = {
        "offset_type": "OFFSET",
        "segments": weightedfillet_segments,
        "width": weightedfillet_width,
        "limit_method": "WEIGHT",
        "use_clamp_overlap": False,
        "loop_slide": True,
        "miter_outer": "MITER_ARC",
        "edge_weight": "bevel_fillet_weighted",
    })

    return {"FINISHED"}

def add_mod_panelize(self, obj):    
    setup_modifier(self, obj, name = "PanelSplit", modifierType = "NODES", settings = {}) 

    thickness_value = bpy.context.scene.get("BP2_settings_solidify_thickness_slider", 2) #2cm thickness by default

    setup_modifier(self, obj, name = "Panelize", modifierType = "SOLIDIFY", settings = {
        "use_rim_only": True,
        "use_even_offset": True,
        "offset": -1,
        "use_quality_normals": True,
        "thickness": thickness_value,
    }) 

    return {'FINISHED'}

def add_mod_edgeChamfer(self, obj):
    angle_threshold = bpy.context.scene.get("BP2_settings_edgechamfer_angle", 30) #Default angle threshold of 30 degrees
    radian_threshold = math.radians(angle_threshold) #Convert to radians
    setup_modifier(self, obj, name = "EdgeDetect", modifierType = "NODES", settings = {
        #"Socket_4": radian_threshold,
        #"Angle threshold": radian_threshold,
    }) 

    edgechamfer_width = bpy.context.scene.get("BP2_settings_edgechamfer_width", 1.0)     #Default width of 1.0
    edgechamfer_segments = bpy.context.scene.get("BP2_settings_edgechamfer_segments", 2) #2 Segments by default
    setup_modifier(self, obj, name = "Bevel_EdgeChamfer", modifierType = "BEVEL", settings = {
        "limit_method": 'WEIGHT',
        "offset_type": 'WIDTH',
        "use_clamp_overlap": False,
        "loop_slide": False,
        "miter_outer": 'MITER_ARC',
        "face_strength_mode": 'FSTR_ALL',
        "width": edgechamfer_width,
        "segments": edgechamfer_segments,
    })

    setup_modifier(self, obj, name = "WeightedNormals", modifierType = "WEIGHTED_NORMAL", settings = {
        "weight": 100,
        "thresh": 10,
        "use_face_influence": True,
        "keep_sharp": True,
    })

    return {'FINISHED'}

def add_mod_autoUV(self, obj):
    setup_modifier(self, obj, name = "AutoUV", modifierType = "NODES", settings = {}
        #"show_viewport", False,}
        )

    return {'FINISHED'}

def add_mod_vertexFillet(self, obj):
    setup_modifier(self, obj, name = "VertexBevel", modifierType = "BEVEL", settings = {
        "affect": 'VERTICES',
        "limit_method": 'VGROUP',
        "segments": 10,
        "use_clamp_overlap": False,
        "loop_slide": False,
        "vertex_group": "BP2_Vbevel",
    })

    return {'FINISHED'}

def register():
    #if depsgraph_modifier_update_handler not in bpy.app.handlers.depsgraph_update_post:
    #    bpy.app.handlers.depsgraph_update_post.append(depsgraph_modifier_update_handler)
    pass


def unregister():
    #if depsgraph_modifier_update_handler in bpy.app.handlers.depsgraph_update_post:
    #    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_modifier_update_handler)
    pass


if __name__ == "__main__":
    register()