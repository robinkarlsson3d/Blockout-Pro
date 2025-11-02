import bpy
import bmesh
from . import bp2_modifiers
#from . import bp2_helpers as bp2

from bpy.props import StringProperty

def isEditMode():
    return (bpy.context.mode == 'EDIT_MESH')

def add_modifiers(self, obj, addSubD: bool = False):
    bp2_modifiers.verify_attributes_exist(obj)
    #if addSubD == True:
    #    bp2_modifiers.add_mod_subD(obj)
    bp2_modifiers.reimport_nodegroups(self)
    
    bp2_modifiers.add_mod_constrainedFillets(self, obj)
    bp2_modifiers.add_mod_weightedFillets(self, obj)
    bp2_modifiers.add_mod_autoUV(self, obj)
    bp2_modifiers.add_mod_panelize(self, obj)
    bp2_modifiers.add_mod_edgeChamfer(self, obj)

    return {'FINISHED'} 

def toggle_modifier_visibility(obj):
    total_mods = 0.0
    visible_mods = 0.0
    obj = bpy.context.object

    #Loop through all selected objects
    for obj in bpy.context.selected_objects:
        #Count modifiers and visible modifiers
        for mod in obj.modifiers:
            if str(mod.name).find("BP2") != -1:
                total_mods += 1.0
                if mod.show_viewport == True:
                    visible_mods += 1.0
        
        visibility_status = visible_mods/total_mods < 0.5
        
        #Toggle visibility for mods
        for mod in obj.modifiers:
            if str(mod.name).find("BP2") != -1:
                mod.show_viewport = visibility_status

    return {'FINISHED'} 

def select_by_edge_attribute(self, obj, attribute_name):
    # Force object mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    for obj in bpy.context.selected_objects:
        if obj is not None and obj.type == 'MESH':
            # Find attribute
            if attribute_name not in obj.data.attributes:
                bp2_modifiers.verify_attributes_exist(obj)
            else:
                attribute = obj.data.attributes[attribute_name]

            #Deselect all edges
            for edge in obj.data.edges:
                edge.select = False

            # Select edges if attribute is not False or 0
            for i, edge in enumerate(obj.data.edges):
                if float(attribute.data[i].value) > 0.0:
                    edge.select = True

    #Force back to edit mode
    bpy.ops.object.mode_set(mode='EDIT')

    return {'FINISHED'} 

def set_edge_attribute(obj, attribute_name, value: float = 0.0, toggle: bool = True):
    if obj is None:
        raise RuntimeError("No selected objects detected.")
    elif obj.type != 'MESH':
        raise RuntimeError("Active object must be a mesh.")
    
    #Save face selection to variable
    #Convert face selection to boundary
    #Set edge properties
    #Restore face selection


    #Force object mode
    bpy.ops.object.mode_set(mode='OBJECT')

    selected_edges = []
    selected_edges = [e.index for e in obj.data.edges if e.select]

    if not selected_edges:
        raise RuntimeError("No edges selected.")

    # Ensure attributes exist
    bp2_modifiers.verify_attributes_exist(obj)

    # Access the target attribute
    attribute = obj.data.attributes[attribute_name]
    if len(attribute.data) != len(obj.data.edges):
        raise RuntimeError("Attribute data size does not match number of edges.")

    # Toggle property on/off
    if toggle == True:
        flaggedEdgesTotal = 0
        for edge_index in selected_edges:
            if (float)(attribute.data[edge_index].value) != 0:
                flaggedEdgesTotal += 1

        value = flaggedEdgesTotal / len(selected_edges) < 0.5       

    # Set new attribute value
    for edge_index in selected_edges:
        attribute.data[edge_index].value = value

    #Force back into edit mode
    bpy.ops.object.mode_set(mode='EDIT')