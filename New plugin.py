bl_info = {
    "name": "blendAI",
    "description": "Generates and executes Blender scripts based on a prompt",
    "author": "Rajarshi Datta & Rahil Masood",
    "version": (2, 0),
    "blender": (4, 3, 2),
    "location": "View3D > Sidebar > AI Generator",
    "category": "3D View",
}

import requests
import re
import os
import bpy  # type: ignore
import textwrap
import time
from enum import Enum

# Replace with your actual OpenRouter API key
OPENROUTER_API_KEY = ""
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

class AIModel(Enum):
    CLAUDE = "anthropic/claude-3.5-sonnet"
    MISTRAL = "mistralai/mistral-7b-instruct"
    GEMINI_PRO = "google/gemini-1.5-pro"

default_model = AIModel.CLAUDE.value

LOG_FILE = os.path.join(bpy.app.tempdir, "ai_log.txt")
DEPRECATED_LOG_FILE = os.path.join(bpy.app.tempdir, "deprecated_log.txt")

DEPRECATED_FUNCTIONS = [
    "bpy.ops.mesh.primitive_cube_add",
    "bpy.ops.mesh.primitive_uv_sphere_add",
    "bpy.ops.mesh.primitive_cone_add",
    "bpy.ops.mesh.primitive_cylinder_add",
    "bpy.ops.object.mode_set",
    "bpy.ops.object.select_by_type",
    "bpy.ops.object.select_all",
    "bpy.ops.view3d.view_selected",
    "bpy.types.SpaceView3D.draw_handler_add",
    "bpy.ops.object.grease_pencil_add",
    "bpy.ops.object.curve_add"
]

def import_online_asset(url):
    """Imports a .blend asset from a given online URL."""
    if not url.endswith(".blend"):
        return "# Error: Only .blend files can be imported."
    
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            temp_file = os.path.join(bpy.app.tempdir, "downloaded_asset.blend")
            with open(temp_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            bpy.ops.wm.append(filepath=temp_file, directory=temp_file + "\\Object\\", filename="")
            return "Asset imported successfully."
        else:
            return f"# Error: Failed to download the file. HTTP {response.status_code}"
    except Exception as e:
        return f"# Error importing asset: {str(e)}"

class ImportOnlineAssetOperator(bpy.types.Operator):
    bl_idname = "script.import_online_asset"
    bl_label = "Import Online Asset"
    
    def execute(self, context):
        url = context.scene.online_asset_url
        result = import_online_asset(url)
        context.scene.import_status = result
        return {'FINISHED'}

class AI_CodeGeneratorPanel(bpy.types.Panel):
    bl_label = "blendAI"
    bl_idname = "VIEW3D_PT_ai_code_generator_openrouter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "blendAI"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select AI Model:")
        layout.prop(context.scene, "ai_selected_model", text="")
        layout.separator()
        layout.label(text="Enter prompt:")
        layout.prop(context.scene, "ai_prompt", text="")
        row = layout.row()
        row.operator("script.generate_and_run_code", text="Generate Prompt")
        layout.separator(factor=2.0)
        layout.label(text="Generated Code:")
        layout.prop(context.scene, "ai_response", text="")
        layout.separator(factor=1.5)
        layout.label(text="Execution Status:")
        layout.prop(context.scene, "ai_execution_status", text="")
        layout.separator(factor=1.5)
        layout.label(text="Import Online Asset:")
        layout.prop(context.scene, "online_asset_url", text="")
        layout.operator("script.import_online_asset", text="Import Asset")
        layout.prop(context.scene, "import_status", text="")


def register():
    bpy.utils.register_class(AI_CodeGeneratorPanel)
    bpy.utils.register_class(ImportOnlineAssetOperator)
    bpy.types.Scene.ai_selected_model = bpy.props.EnumProperty(
        name="AI Model", items=[(model.value, model.name, "") for model in AIModel], default=default_model
    )
    bpy.types.Scene.ai_prompt = bpy.props.StringProperty(name="Prompt", default="")
    bpy.types.Scene.ai_response = bpy.props.StringProperty(name="Generated Code", default="")
    bpy.types.Scene.ai_execution_status = bpy.props.StringProperty(name="Execution Status", default="")
    bpy.types.Scene.online_asset_url = bpy.props.StringProperty(name="Online Asset URL", default="")
    bpy.types.Scene.import_status = bpy.props.StringProperty(name="Import Status", default="")

def unregister():
    bpy.utils.unregister_class(AI_CodeGeneratorPanel)
    bpy.utils.unregister_class(ImportOnlineAssetOperator)
    del bpy.types.Scene.ai_selected_model
    del bpy.types.Scene.ai_prompt
    del bpy.types.Scene.ai_response
    del bpy.types.Scene.ai_execution_status
    del bpy.types.Scene.online_asset_url
    del bpy.types.Scene.import_status

if __name__ == "__main__":
    register()
