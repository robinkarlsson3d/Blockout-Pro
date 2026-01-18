import bpy
import bmesh
from . import bp_modifiers

#from bpy.props import StringProperty

def isEditMode():
    if bpy.context.mode == 'EDIT_MESH':
        return True
    else:
        return False

#obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'

def getSelectedObjects(self, MeshesOnly: bool = True):
    #Use selected objects
    objects = list(bpy.context.selected_objects)

    #Use active object if empty selection
    if not objects and bpy.context.mode == 'EDIT_MESH':
        objects =  [bpy.context.active_object]

    #Filter for meshes
    if MeshesOnly:
        filteredObjects = []
        for obj in objects:
            if obj.type == 'MESH':
                filteredObjects.append(obj) 
    else:
        filteredObjects = objects

    if not filteredObjects:
        self.report({'WARNING'}, "No selected objects")
        return []

    return filteredObjects
    

def add_modifiers(self):
    #for obj in bpy.context.selected_objects:
    objects  = getSelectedObjects(self)

    if not objects:
        return {'CANCELLED'} 

    for obj in objects:
        bp_modifiers.verify_attributes_exist(obj)

        bp_modifiers.reimport_nodegroups(self)
        
        if self.addSubD == True:
            bp_modifiers.add_mod_subD(self, obj)
        
        if self.addFilletConstrained == True and self.simplifiedStack == False:
            bp_modifiers.add_mod_constrainedFillets(self, obj)
        
        if self.addFilletWeighted == True and self.simplifiedStack == False:    
            bp_modifiers.add_mod_weightedFillets(self, obj)
        
        if self.addShrinkwrap == True and self.simplifiedStack == False: 
            bp_modifiers.add_mod_shrinkwrap(self, obj)

        if self.addPanelling == True: 
            bp_modifiers.add_mod_panelize(self, obj)
        
        if self.addAutoUV == True and self.simplifiedStack == False:
            bp_modifiers.add_mod_autoUV(self, obj)

        if self.addEdgeChamfer == True:
            bp_modifiers.add_mod_edgeChamfer(self, obj)

    return {'FINISHED'} 

def smart_mirror(self):
    #Find root object
    #Determine which side needs to be mirrored by pivot location
    #If in edit mode use the currently selected side as ground truth
    #Calculate bounding box if mirror is very close to center

    #obj = bpy.context.active_object
    
    #for obj in bpy.context.selected_objects:
    objects  = getSelectedObjects(self)

    if not objects:
        return {'CANCELLED'} 

    for obj in objects:
        #FIND PARENT HELPER
        parentObj = obj
        while parentObj.parent is not None:
            parentObj = parentObj.parent
            if self.mirrorByRoot == False and parentObj.type == "EMPTY":
                break
        

        
        #DETERMINE WHICH AXIS IF ANY NEEDS TO BE FLIPPED
        flipBisectAxis = [False, False, False]
        #if isEditMode == False:
        flipBisectAxis[0] = (obj.location.x - parentObj.location.x) < 0
        flipBisectAxis[1] = (obj.location.y - parentObj.location.y) < 0
        flipBisectAxis[2] = (obj.location.z - parentObj.location.z) < 0
        #else:

        #DETERMINE WHICH AXIS NEED TO BE MIRRORED - Y AS DEFAULT
        #mirrorAxis = [False, True, False]
        mirrorAxis = [self.mirrorX, self.mirrorY, self.mirrorZ]

        #Special case if no parent exists
        parentObjName = parentObj.name
        if obj.name == parentObjName:
            parentObjName = ""

        #ADD MODIFIER
        bp_modifiers.add_mod_mirror(self, obj, mirrorAxis, flipBisectAxis, parentObjName)

    return {'FINISHED'} 

def toggle_modifier_visibility(self):

    #obj = bpy.context.object
    

    #Loop through all selected objects
    #for obj in bpy.context.selected_objects:

    objects  = getSelectedObjects(self)

    if not objects:
        return {'CANCELLED'} 

    for obj in objects:
        total_mods = 0.0
        visible_mods = 0.0
        #Count modifiers and visible modifiers
        for mod in obj.modifiers:
            if str(mod.name).find("BP") != -1:
                total_mods += 1.0
                if mod.show_viewport == True:
                    visible_mods += 1.0
        
        visibility_status = visible_mods/total_mods < 0.5
        
        #Toggle visibility for mods
        for mod in obj.modifiers:
            if str(mod.name).find("BP") != -1:
                mod.show_viewport = visibility_status
    
    self.report({'INFO'}, "Toggled visibility for BP modifiers")
    return {'FINISHED'} 

def select_by_edge_attribute(self, attribute_name):
    # Force object mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    for obj in bpy.context.selected_objects:
        if obj is not None and obj.type == 'MESH':
            # Find attribute
            if attribute_name not in obj.data.attributes:
                bp_modifiers.verify_attributes_exist(obj)
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

def set_edge_attribute(self, attribute_name, value: float = 0.0, toggle: bool = True):
    obj = bpy.context.object

    if obj is None:
        raise RuntimeError("No selected objects detected.")
    elif obj.type != 'MESH':
        raise RuntimeError("Active object must be a mesh.")

    #Convert face selection to boundary if in facemode
    if bpy.context.mode == 'EDIT_MESH' and bpy.context.tool_settings.mesh_select_mode[2]:
        bpy.ops.mesh.region_to_loop()

    #Force object mode
    bpy.ops.object.mode_set(mode='OBJECT')

    #selected_edges = []
    selected_edges = [e.index for e in obj.data.edges if e.select]

    if not selected_edges:
        raise RuntimeError("No edges selected.")

    # Ensure attributes exist
    bp_modifiers.verify_attributes_exist(obj)

    # Access the target attribute
    attributes = obj.data.attributes
    if len(attributes[attribute_name].data) != len(obj.data.edges):
        raise RuntimeError("Attribute data size does not match number of edges.")

    # Toggle property on/off
    if toggle == True:
        flaggedEdgesTotal = 0
        for edge_index in selected_edges:
            if (float)(attributes[attribute_name].data[edge_index].value) != 0:
                flaggedEdgesTotal += 1

        value = flaggedEdgesTotal / len(selected_edges) < 0.5       

    # Set new attribute value
    for edge_index in selected_edges:
        attributes[attribute_name].data[edge_index].value = value
    
        #Special case for marking each property
        if (attribute_name == "bp_panel_edge"):
            attributes["uv_seam"].data[edge_index].value = bool(value)
        elif (attribute_name == "bp_bevel_fillet_weighted" or attribute_name == "bp_bevel_fillet_constrained"):
            attributes["freestyle_edge"].data[edge_index].value = bool(value)

    #Force back into edit mode
    bpy.ops.object.mode_set(mode='EDIT')

def apply_attribute(self, attribute_name, bevel_segments: int = 10, bevel_width: float = 1.0):
    obj = bpy.context.object
    mesh = obj.data

    bpy.ops.object.mode_set(mode='OBJECT')

    attribute = mesh.attributes.get(attribute_name)
    if not attribute:
        print(f"Attribute '{attribute_name}' not found")
        return

    
    averageBevelWeight = 0.0
    edgeCount = 0

    #Deselect all selected edges without attribute
    #Unflag attrbutes if found 
    for edge, value in zip(mesh.edges, attribute.data):
        if edge.select:
            if attribute.data_type == 'BOOLEAN':
                if value.value == False:
                    edge.select = False
                else:
                    value.value == False
                    edgeCount += 1

            elif attribute.data_type == 'FLOAT':
                if value.value <= 0.0:
                    edge.select = False
                else:
                    averageBevelWeight += value.value 
                    edgeCount += 1
                    value.value = 0.0
    
    if edgeCount != 0:
        averageBevelWeight = averageBevelWeight / float(edgeCount)
    #else:
    #    averageBevelWeight  = 1.0

    bpy.ops.object.mode_set(mode='EDIT')

    #Apply
    if attribute_name == "bp_bevel_fillet_constrained":
        toggle_automerge_off = False

        if bpy.context.scene.tool_settings.use_mesh_automerge == False:
            bpy.context.scene.tool_settings.use_mesh_automerge = True
            toggle_automerge_off = True

        bpy.ops.mesh.mark_freestyle_edge(clear=True)
        bpy.ops.mesh.bevel(offset_type='PERCENT', offset=1.0, offset_pct=100, segments=bevel_segments,profile=0.5, affect='EDGES')

        if toggle_automerge_off == True:
            bpy.context.scene.tool_settings.use_mesh_automerge = False

    elif attribute_name == "bp_bevel_fillet_weighted":
        bpy.ops.mesh.mark_freestyle_edge(clear=True) 

        mod = bpy.context.object.modifiers[" BP_Bevel_Weighted"]
        print("Mod width: " + str(mod.width))
        print("Bevel weight:" + str(averageBevelWeight))

        bpy.ops.mesh.bevel( 
            offset=averageBevelWeight* mod.width, 
            segments=bevel_segments, 
            offset_type= mod.offset_type,
            profile=mod.profile, 
            affect='EDGES', 
            miter_inner= 'SHARP',
            miter_outer= 'ARC', 
            clamp_overlap=mod.use_clamp_overlap, 
            loop_slide=mod.loop_slide
            )

    elif attribute_name == "bevel_weight_edge":
        bpy.context.scene.edge_props.bevel_weight_edge_slider = 0
        
        #bpy.ops.mesh.bevel(offset=averageBevelWeight, offset_pct=0, segments=bevel_segments, profile=0.5, affect='EDGES', miter_outer='ARC')
        mod = bpy.context.object.modifiers[" BP_EdgeChamfer"]
        print("Mod width: " + str(mod.width))
        print("Bevel weight:" + str(averageBevelWeight))

        bpy.ops.mesh.bevel( 
            offset=averageBevelWeight* mod.width, 
            segments=bevel_segments, 
            offset_type= mod.offset_type,
            profile=mod.profile, 
            affect='EDGES', 
            miter_inner= 'SHARP',
            miter_outer= 'ARC', 
            clamp_overlap=mod.use_clamp_overlap, 
            loop_slide=mod.loop_slide
            )

        pass
    elif attribute_name == "bp_panel_edge":
        toggled_automerge_off = False

        if bpy.context.scene.tool_settings.use_mesh_automerge == True:
            bpy.context.scene.tool_settings.use_mesh_automerge = False
            toggled_automerge_off = True

        bpy.ops.mesh.edge_split()

        if toggled_automerge_off == True:
            bpy.context.scene.tool_settings.use_mesh_automerge = True


    elif attribute_name == "sharp_edge":
        pass



    return {'FINISHED'}