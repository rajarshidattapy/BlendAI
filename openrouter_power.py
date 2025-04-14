bl_info = {
    "name": "BlendAI",
    "description": "Generates and executes Blender scripts using various AI models via OpenRouter, with GitHub import",
    "author": "Rajarshi",
    "version": (2, 0),
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
import zipfile
import urllib.request
from enum import Enum

LOG_FILE = os.path.join(bpy.app.tempdir, "ai_log.txt")

# OpenRouter configuration
OPENROUTER_API_KEY = "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" 
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Available models through OpenRouter - focusing on free models
class AIModel(Enum):
    GEMINI_PRO = "google/gemini-pro"
    MISTRAL_7B = "mistralai/mistral-7b-instruct"
    LLAMA_2 = "meta-llama/llama-2-13b-chat"
    OPENCHAT = "openchat/openchat-3.5"
    SOLAR = "upstage/solar-10.7b-instruct"
    FALCON = "tiiuae/falcon-7b-instruct"

# Default model
DEFAULT_MODEL = AIModel.GEMINI_PRO.value

DEPRECATED_FUNCTIONS = [
    "bpy.ops.mesh.primitive_cube_add",
    "bpy.ops.mesh.primitive_uv_sphere_add(size=)",
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

# Implementing Log files
def read_log_history():
    """Read previous prompts and responses from the log file."""
    if not os.path.exists(LOG_FILE):
        return ""
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return f.read()[-2000:]

def append_to_log(prompt, response, model_used):
    """Append new prompt and response to the log file."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"Model: {model_used}\nPrompt: {prompt}\nResponse:\n{response}\n{'-'*50}\n")

def get_ai_generated_code(prompt, model=None):
    try:
        model = model or bpy.context.scene.ai_selected_model
        history = read_log_history()

        system_prompt = f"""You are an AI specialized in generating Blender 4.3 Python scripts.
- Always return **valid and executable** Python code compatible with Blender 4.3.
- Do **NOT** include explanations or formatting—just the raw script.
- Return ONLY the Python code without markdown formatting or code block delimiters.
- **Avoid using the following deprecated functions:** 
{', '.join(DEPRECATED_FUNCTIONS)}

## Previous Interactions:
{history}

## User Request:
{prompt} in Blender 4.3"""

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://blendai.app",  # Optional: Change to your site
            "X-Title": "BlendAI"  # Optional: Your application name
        }

        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2048
        }

        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data)
        response_json = response.json()

        if response.status_code == 200 and "choices" in response_json:
            code = response_json["choices"][0]["message"]["content"].strip()
            
            # Remove markdown code blocks if present
            code = re.sub(r'^```[a-zA-Z]*\n|```$', '', code, flags=re.MULTILINE)

            # Remove triple quotes if they wrap the entire content
            if code.startswith('"""') and code.endswith('"""'):
                code = code[3:-3].strip()
            elif code.startswith("'''") and code.endswith("'''"):
                code = code[3:-3].strip()

            append_to_log(prompt, code, model)
            return code
        else:
            error_msg = response_json.get("error", {}).get("message", "Unknown error")
            return f"# Error: {error_msg}"
    except Exception as e:
        return f"# Error generating code: {str(e)}"

def execute_script_with_retries(code, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            if not code.strip() or code.strip().startswith("#"):
                return "No valid code to execute."

            compile(code, '<string>', 'exec')
            exec(code, globals())
            return "Script executed successfully."
        except SyntaxError as e:
            return f"# Syntax Error: {e}"
        except Exception as e:
            if attempt < max_retries:
                time.sleep(0.5)
                continue
            return f"# Error executing the script after {max_retries} attempts: {str(e)}"

def download_github_repo(repo_url, branch="main"):
    """
    Download a GitHub repository as a zip file and extract it
    Returns path to the extracted folder
    """
    try:
        # Convert standard GitHub URL to the zip download URL
        if not repo_url.endswith("/"):
            repo_url += "/"
        
        # Format the API request URL
        zip_url = f"{repo_url}archive/refs/heads/{branch}.zip"
        
        # Replace github.com with api.github.com/repos if needed
        zip_url = zip_url.replace("github.com/", "github.com/")
        
        # Create temporary directory for the download
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "repo.zip")
        
        # Download the repository ZIP
        urllib.request.urlretrieve(zip_url, zip_path)
        
        # Extract the ZIP file
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Return the extraction directory
        return extract_dir
    except Exception as e:
        raise Exception(f"Failed to download GitHub repository: {str(e)}")

def find_blend_files(directory):
    """Find all .blend files in the given directory and its subdirectories"""
    blend_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".blend"):
                blend_files.append(os.path.join(root, file))
    return blend_files

def append_from_library(blend_file_path, objects=True, materials=True, textures=True):
    """Append objects, materials, or textures from a .blend file"""
    try:
        # Create sets to track what's already in the scene
        original_objects = set(bpy.data.objects)
        original_materials = set(bpy.data.materials)
        original_textures = set(bpy.data.textures)
        
        if objects:
            with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
                data_to.objects = data_from.objects
            
            # Link new objects to the scene
            for obj in data_to.objects:
                if obj is not None:
                    bpy.context.collection.objects.link(obj)
        
        if materials:
            with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
                data_to.materials = data_from.materials
        
        if textures:
            with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
                data_to.textures = data_from.textures
        
        # Count what was added
        new_objects = set(bpy.data.objects) - original_objects
        new_materials = set(bpy.data.materials) - original_materials
        new_textures = set(bpy.data.textures) - original_textures
        
        return {
            "objects": len(new_objects),
            "materials": len(new_materials),
            "textures": len(new_textures)
        }
    except Exception as e:
        raise Exception(f"Error appending from library: {str(e)}")

class AI_CodeGeneratorPanel(bpy.types.Panel):
    bl_label = "BlendAI"
    bl_idname = "VIEW3D_PT_ai_code_generator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "BlendAI"

    def draw(self, context):
        layout = self.layout
        
        # Model selection
        layout.label(text="Select AI Model:")
        layout.prop(context.scene, "ai_selected_model", text="")
        
        # Prompt
        layout.separator()
        layout.label(text="Enter prompt:")
        layout.prop(context.scene, "ai_prompt", text="")

        row = layout.row()
        row.operator("script.generate_and_run_code", text="Generate & Run")
        row.operator("script.generate_only", text="Generate Only")

        # GitHub Import Section
        layout.separator(factor=2.0)
        box = layout.box()
        box.label(text="GitHub Blend Library Import")
        box.prop(context.scene, "ai_github_repo_url", text="GitHub Repo URL")
        box.prop(context.scene, "ai_github_branch", text="Branch")
        
        # Import Options
        row = box.row()
        row.prop(context.scene, "ai_import_objects", text="Objects")
        row.prop(context.scene, "ai_import_materials", text="Materials")
        row.prop(context.scene, "ai_import_textures", text="Textures")
        
        # Import .blend selection row
        box.prop(context.scene, "ai_selected_blend_file", text="Selected .blend")
        
        row = box.row()
        row.operator("script.fetch_github_blends", text="Fetch .blend Files")
        row.operator("script.import_selected_blend", text="Import Selected")

        # GitHub import status
        if context.scene.ai_github_status:
            box.label(text=f"Status: {context.scene.ai_github_status}")

        # Generated Code section
        layout.separator(factor=2.0)
        layout.label(text="Generated Code:")
        _label_multiline(context, context.scene.ai_response, layout)

        layout.separator(factor=1.5)
        layout.label(text="Execution Status:")
        layout.prop(context.scene, "ai_execution_status", text="")

class GenerateAndRunCodeOperator(bpy.types.Operator):
    bl_idname = "script.generate_and_run_code"
    bl_label = "Generate & Run"

    def execute(self, context):
        prompt = context.scene.ai_prompt
        model = context.scene.ai_selected_model
        script_code = get_ai_generated_code(prompt, model)

        if not script_code.startswith("# Error"):
            context.scene.ai_response = script_code
            execution_result = execute_script_with_retries(script_code)
            context.scene.ai_execution_status = execution_result
        else:
            context.scene.ai_response = script_code
            context.scene.ai_execution_status = "Failed to generate valid code"

        return {'FINISHED'}

class GenerateOnlyOperator(bpy.types.Operator):
    bl_idname = "script.generate_only"
    bl_label = "Generate Only"

    def execute(self, context):
        prompt = context.scene.ai_prompt
        model = context.scene.ai_selected_model
        script_code = get_ai_generated_code(prompt, model)
        context.scene.ai_response = script_code
        context.scene.ai_execution_status = "Code generated but not executed"
        return {'FINISHED'}

class FetchGitHubBlendsOperator(bpy.types.Operator):
    bl_idname = "script.fetch_github_blends"
    bl_label = "Fetch .blend Files"
    
    def execute(self, context):
        try:
            repo_url = context.scene.ai_github_repo_url
            branch = context.scene.ai_github_branch
            
            if not repo_url:
                context.scene.ai_github_status = "Please enter a GitHub repository URL"
                return {'CANCELLED'}
            
            context.scene.ai_github_status = "Downloading repository..."
            
            # Download and extract the repository
            extract_dir = download_github_repo(repo_url, branch)
            
            # Find all .blend files
            blend_files = find_blend_files(extract_dir)
            
            if not blend_files:
                context.scene.ai_github_status = "No .blend files found in the repository"
                return {'CANCELLED'}
            
            # Store the found .blend files in scene property
            bpy.types.Scene.ai_blend_files = blend_files
            
            # Update the dropdown options
            context.scene.ai_blend_enum.clear()
            for i, file_path in enumerate(blend_files):
                file_name = os.path.basename(file_path)
                item = context.scene.ai_blend_enum.add()
                item.name = file_name
                item.path = file_path
                item.id = i
            
            context.scene.ai_github_status = f"Found {len(blend_files)} .blend files"
            
            # Set first file as selected
            if len(context.scene.ai_blend_enum) > 0:
                context.scene.ai_selected_blend_file = 0
            
            return {'FINISHED'}
            
        except Exception as e:
            context.scene.ai_github_status = f"Error: {str(e)}"
            return {'CANCELLED'}

class ImportSelectedBlendOperator(bpy.types.Operator):
    bl_idname = "script.import_selected_blend"
    bl_label = "Import Selected .blend"
    
    def execute(self, context):
        try:
            # Check if any .blend files were found
            if not hasattr(bpy.types.Scene, 'ai_blend_files') or not bpy.types.Scene.ai_blend_files:
                context.scene.ai_github_status = "No .blend files available. Fetch files first."
                return {'CANCELLED'}
            
            # Get the selected file
            selected_index = context.scene.ai_selected_blend_file
            if selected_index >= len(context.scene.ai_blend_enum):
                context.scene.ai_github_status = "Invalid selection"
                return {'CANCELLED'}
            
            selected_file = context.scene.ai_blend_enum[selected_index].path
            
            # Import options
            import_objects = context.scene.ai_import_objects
            import_materials = context.scene.ai_import_materials
            import_textures = context.scene.ai_import_textures
            
            # Append content from the .blend file
            result = append_from_library(
                selected_file, 
                objects=import_objects, 
                materials=import_materials, 
                textures=import_textures
            )
            
            # Update status
            context.scene.ai_github_status = f"Imported: {result['objects']} objects, {result['materials']} materials, {result['textures']} textures"
            
            return {'FINISHED'}
        
        except Exception as e:
            context.scene.ai_github_status = f"Import error: {str(e)}"
            return {'CANCELLED'}

def _label_multiline(context, text, parent):
    chars = int(context.region.width / 7)
    wrapper = textwrap.TextWrapper(width=chars)

    text_lines = wrapper.wrap(text=text)
    for text_line in text_lines:
        parent.label(text=text_line)

def model_items(self, context):
    return [
        (AIModel.GEMINI_PRO.value, "Gemini Pro", "Google's Gemini Pro model"),
        (AIModel.MISTRAL_7B.value, "Mistral 7B", "Mistral's 7B parameter instruct model"),
        (AIModel.LLAMA_2.value, "Llama 2", "Meta's Llama 2 13B chat model"),
        (AIModel.OPENCHAT.value, "OpenChat 3.5", "OpenChat 3.5 model"),
        (AIModel.SOLAR.value, "Solar", "Upstage's Solar 10.7B instruct model"),
        (AIModel.FALCON.value, "Falcon", "TII's Falcon 7B instruct model")
    ]

class BlendFileItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="File Name")
    path: bpy.props.StringProperty(name="File Path")
    id: bpy.props.IntProperty(name="Index")

def blend_file_items(self, context):
    items = []
    for i, item in enumerate(context.scene.ai_blend_enum):
        items.append((str(i), item.name, f"Import {item.name}"))
    return items if items else [("0", "No files found", "")]

def register():
    bpy.utils.register_class(BlendFileItem)
    bpy.utils.register_class(AI_CodeGeneratorPanel)
    bpy.utils.register_class(GenerateAndRunCodeOperator)
    bpy.utils.register_class(GenerateOnlyOperator)
    bpy.utils.register_class(FetchGitHubBlendsOperator)
    bpy.utils.register_class(ImportSelectedBlendOperator)
    
    bpy.types.Scene.ai_prompt = bpy.props.StringProperty(
        name="Prompt", 
        default=""
    )
    bpy.types.Scene.ai_response = bpy.props.StringProperty(
        name="Generated Code", 
        default=""
    )
    bpy.types.Scene.ai_execution_status = bpy.props.StringProperty(
        name="Execution Status", 
        default=""
    )
    bpy.types.Scene.ai_selected_model = bpy.props.EnumProperty(
        name="AI Model",
        items=model_items,
        default=DEFAULT_MODEL
    )
    
    # GitHub import properties
    bpy.types.Scene.ai_github_repo_url = bpy.props.StringProperty(
        name="GitHub Repository URL",
        description="URL of the GitHub repository containing .blend files",
        default=""
    )
    bpy.types.Scene.ai_github_branch = bpy.props.StringProperty(
        name="Branch",
        description="Branch of the repository to download",
        default="main"
    )
    bpy.types.Scene.ai_github_status = bpy.props.StringProperty(
        name="GitHub Import Status",
        default=""
    )
    
    # Import options
    bpy.types.Scene.ai_import_objects = bpy.props.BoolProperty(
        name="Import Objects",
        description="Import objects from the blend file",
        default=True
    )
    bpy.types.Scene.ai_import_materials = bpy.props.BoolProperty(
        name="Import Materials",
        description="Import materials from the blend file",
        default=True
    )
    bpy.types.Scene.ai_import_textures = bpy.props.BoolProperty(
        name="Import Textures",
        description="Import textures from the blend file",
        default=True
    )
    
    # Blend file selection
    bpy.types.Scene.ai_blend_enum = bpy.props.CollectionProperty(type=BlendFileItem)
    bpy.types.Scene.ai_selected_blend_file = bpy.props.IntProperty(
        name="Selected .blend File",
        default=0
    )
    
    # Store the list of blend files
    bpy.types.Scene.ai_blend_files = []

def unregister():
    bpy.utils.unregister_class(AI_CodeGeneratorPanel)
    bpy.utils.unregister_class(GenerateAndRunCodeOperator)
    bpy.utils.unregister_class(GenerateOnlyOperator)
    bpy.utils.unregister_class(FetchGitHubBlendsOperator)
    bpy.utils.unregister_class(ImportSelectedBlendOperator)
    bpy.utils.unregister_class(BlendFileItem)
    
    del bpy.types.Scene.ai_prompt
    del bpy.types.Scene.ai_response
    del bpy.types.Scene.ai_execution_status
    del bpy.types.Scene.ai_selected_model
    del bpy.types.Scene.ai_github_repo_url
    del bpy.types.Scene.ai_github_branch
    del bpy.types.Scene.ai_github_status
    del bpy.types.Scene.ai_import_objects
    del bpy.types.Scene.ai_import_materials
    del bpy.types.Scene.ai_import_textures
    del bpy.types.Scene.ai_blend_enum
    del bpy.types.Scene.ai_selected_blend_file
    del bpy.types.Scene.ai_blend_files

if __name__ == "__main__":
    register()