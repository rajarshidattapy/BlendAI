bl_info = {
    "name": "BlendAI",
    "description": "Generates and executes Blender scripts using various AI models via OpenRouter",
    "author": "Rahil M & Rajarshi Datta", 
    "version": (1, 4),
    "blender": (4, 3, 2),
    "location": "View3D > Sidebar > AI Generator",
    "category": "3D View",
}

import bpy  # type: ignore
import requests
import json
import textwrap
import re
import time
import os
import tempfile
from enum import Enum

LOG_FILE = os.path.join(bpy.app.tempdir, "ai_log.txt")

# OpenRouter configuration
OPENROUTER_API_KEY = "put your api key here" 
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Available models through OpenRouter
class AIModel(Enum):
    GEMINI_PRO = "google/gemini-1.5-pro" 
    MISTRAL_7B = "mistralai/mistral-7b-instruct"
    CLAUDE = "anthropic/claude-3-sonnet"

# Default model
DEFAULT_MODEL = AIModel.GEMINI_PRO.value

# Implementing Log files
def read_log_history():
    if not os.path.exists(LOG_FILE):
        return ""
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return f.read()[-2000:]

def append_to_log(prompt, response, model_used):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"Model: {model_used}\nPrompt: {prompt}\nResponse:\n{response}\n{'-'*50}\n")

# Direct Online Asset Import
def import_online_asset(url):
    """Imports a .blend asset from a given online URL."""
    if not url.endswith(".blend"):
        return "# Error: Only .blend files can be imported."
    
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            temp_file = tempfile.NamedTemporaryFile(suffix=".blend", delete=False)
            with open(temp_file.name, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            bpy.ops.wm.append(filepath=temp_file.name, directory=temp_file.name + "\\Object\\", filename="")
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
    bl_label = "BlendAI"
    bl_idname = "VIEW3D_PT_ai_code_generator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "BlendAI"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select AI Model:")
        layout.prop(context.scene, "ai_selected_model", text="")
        layout.separator()
        layout.label(text="Enter prompt:")
        layout.prop(context.scene, "ai_prompt", text="")
        row = layout.row()
        row.operator("script.generate_and_run_code", text="Generate & Run")
        row.operator("script.generate_only", text="Generate Only")
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
    bpy.types.Scene.ai_prompt = bpy.props.StringProperty(name="Prompt", default="")
    bpy.types.Scene.ai_response = bpy.props.StringProperty(name="Generated Code", default="")
    bpy.types.Scene.ai_execution_status = bpy.props.StringProperty(name="Execution Status", default="")
    bpy.types.Scene.online_asset_url = bpy.props.StringProperty(name="Online Asset URL", default="")
    bpy.types.Scene.import_status = bpy.props.StringProperty(name="Import Status", default="")

def unregister():
    bpy.utils.unregister_class(AI_CodeGeneratorPanel)
    bpy.utils.unregister_class(ImportOnlineAssetOperator)
    del bpy.types.Scene.ai_prompt
    del bpy.types.Scene.ai_response
    del bpy.types.Scene.ai_execution_status
    del bpy.types.Scene.online_asset_url
    del bpy.types.Scene.import_status

if __name__ == "__main__":
    register()
