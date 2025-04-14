bl_info = {
    "name": "Add Cube",
    "description": "Adds a cube and material to the 3D View",
    "author": "Rahil",
    "version": (1, 0),
    "blender": (4, 3, 0),
    "location": "View3D > Sidebar > Cube Tools",
    "category": "3D View",
}

import bpy

class AddCubeOperator(bpy.types.Operator):
    """Add a cube into the scene"""
    bl_idname = "mesh.add_cube"
    bl_label = "Add Cube"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.mesh.primitive_cube_add(size=2, enter_editmode=False, align='WORLD', location=(0, 0, 0))
        self.report({'INFO'}, "Cube added successfully!")
        return {'FINISHED'}

class AddMaterialOperator(bpy.types.Operator):
    """Add a material to the selected object"""
    bl_idname = "mesh.add_material"
    bl_label = "Add Material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.object
        if obj and obj.type == 'MESH':  
            if not obj.data.materials:  # Prevent duplicate materials
                material = bpy.data.materials.new(name='Sample Material')
                material.use_nodes = True
                obj.data.materials.append(material)
                self.report({'INFO'}, "Material added successfully!")
            else:
                self.report({'WARNING'}, "Object already has a material!")
        else:
            self.report({'WARNING'}, "Select a mesh object first!")
        return {'FINISHED'}

class SamplePanel(bpy.types.Panel):
    """Display panel in 3D view (Sidebar)"""
    bl_label = "Sample Addon"
    bl_idname = "PT_SAMPLEPANEL"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cube Tools"  # Better UI organization

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("mesh.add_cube", icon="MESH_CUBE")
        col.operator("mesh.add_material", icon="SHADING_RENDERED")

classes = (SamplePanel, AddCubeOperator, AddMaterialOperator)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
