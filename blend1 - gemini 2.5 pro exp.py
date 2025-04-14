bl_info = {
    "name": "blendAI",
    "description": "Generates and executes Blender scripts based on a prompt",
    "author": "Rajarshi Datta",
    "version": (1, 5),
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

# Replace with your actual OpenRouter API key
OPENROUTER_API_KEY = "your_api_key"
MODEL_NAME = "google/gemini-2.5-pro-exp-03-25:free"

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
    "bpy.ops.object.curve_add",
    # More deprecated ops/functions
    "bpy.ops.mesh.primitive_grid_add",
    "bpy.ops.mesh.primitive_monkey_add",  
    "bpy.ops.mesh.primitive_torus_add",
    "bpy.ops.object.origin_set",
    "bpy.ops.object.duplicate_move",
    "bpy.ops.object.delete",
    "bpy.ops.transform.translate",
    "bpy.ops.transform.rotate",
    "bpy.ops.transform.resize",
    # View-related that don't belong in scripting
    "bpy.ops.view3d.camera_to_view",
    "bpy.ops.view3d.camera_to_view_selected",
    "bpy.ops.view3d.view_all",
    # Material misuses
    "bpy.data.materials.new",
    "bpy.data.objects[''].data.materials.append",
    # Grease pencil: deprecated in many newer uses
    "bpy.data.grease_pencils.new",
    "bpy.ops.gpencil.draw",
    # Custom vector classes — often misused
    "mathutils.Vector()",
    "mathutils.Euler()",
    "mathutils.Matrix()"
]



def read_log_history():
    """Read previous prompts and responses from the log file."""
    if not os.path.exists(LOG_FILE):
        return ""
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return f.read()[-2000:]

def append_to_log(prompt, response):
    """Append new prompt and response to the log file."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"Prompt: {prompt}\nResponse:\n{response}\n{'-'*50}\n")

def check_deprecated_usage(code):
    """Check for usage of deprecated functions and log them."""
    deprecated_found = [func for func in DEPRECATED_FUNCTIONS if func in code]
    if deprecated_found:
        with open(DEPRECATED_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"Deprecated functions used:\n{', '.join(deprecated_found)}\n{'-'*50}\n")

def get_generated_code(prompt):
    """Fetch AI-generated Blender script using Claude Sonnet via OpenRouter API."""
    try:
        history = read_log_history()

        system_prompt = f"""You are an AI specialized in generating Blender 4.3 Python scripts.
- Always return **valid and executable** Python code.
- Ensure all object materials exist before modifying them.
- Do **NOT** include explanations or formatting—just the raw script.
- **Avoid using the following deprecated functions:** 
{', '.join(DEPRECATED_FUNCTIONS)}

## Previous Interactions:
{history}

## User Request:
{prompt} in Blender 4.3"""

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2048
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)

        if response.status_code == 200:
            result = response.json()
            code = result["choices"][0]["message"]["content"].strip()
            code = re.sub(r'^```[a-zA-Z]*\n|```$', '', code, flags=re.MULTILINE)

            check_deprecated_usage(code)
            append_to_log(prompt, code)
            return code
        else:
            return f"# Error: OpenRouter API returned status {response.status_code}, Message: {response.text}"
    except Exception as e:
        return f"# Error generating code: {str(e)}"


def get_active_object_location():
    """Retrieve and log the active object's current location before executing AI-generated code."""
    obj = bpy.context.object
    if obj:
        return f"Active Object: {obj.name}, Location: ({obj.location.x:.3f}, {obj.location.y:.3f}, {obj.location.z:.3f})"

    return "No active object selected."


def execute_script_with_retries(code, max_retries=3):
    """Executes AI-generated script with retries and logs object location before execution."""
    obj_location = get_active_object_location()
    append_to_log("Object Location Before Execution", obj_location)  # Log the location
    
    for attempt in range(1, max_retries + 1):
        try:
            if not code.strip() or code.strip().startswith("#"):
                return "No valid code to execute."

            compile(code, '<string>', 'exec')
            exec(code, globals())

            return f"Script executed successfully.\n{obj_location}"
        except SyntaxError as e:
            return f"# Syntax Error: {e}"
        except Exception as e:
            if attempt < max_retries:
                time.sleep(0.5)
                continue
            return f"# Error executing the script after {max_retries} attempts: {str(e)}"


class AI_CodeGeneratorPanel(bpy.types.Panel):
    bl_label = "blendAI"
    bl_idname = "VIEW3D_PT_ai_code_generator_openrouter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "blendAI"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Enter prompt:")
        layout.prop(context.scene, "ai_prompt", text="")

        row = layout.row()
        row.operator("script.generate_and_run_code", text="Generate Prompt")

        layout.separator(factor=2.0)
        layout.label(text="Generated Code:")
        _label_multiline(context, context.scene.ai_response, layout)

        layout.separator(factor=1.5)
        layout.label(text="Execution Status:")
        layout.prop(context.scene, "ai_execution_status", text="")

class GenerateAndRunCodeOperator(bpy.types.Operator):
    bl_idname = "script.generate_and_run_code"
    bl_label = "Generate Prompt"

    def execute(self, context):
        prompt = context.scene.ai_prompt
        script_code = get_generated_code(prompt)

        if "Error" not in script_code:
            context.scene.ai_response = script_code
            execution_result = execute_script_with_retries(script_code)
            context.scene.ai_execution_status = execution_result
        else:
            context.scene.ai_execution_status = script_code

        return {'FINISHED'}

def _label_multiline(context, text, parent):
    chars = int(context.region.width / 7)
    wrapper = textwrap.TextWrapper(width=chars)

    text_lines = wrapper.wrap(text=text)
    for text_line in text_lines:
        parent.label(text=text_line)

def register():
    bpy.utils.register_class(AI_CodeGeneratorPanel)
    bpy.utils.register_class(GenerateAndRunCodeOperator)
    bpy.types.Scene.ai_prompt = bpy.props.StringProperty(name="Prompt", default="")
    bpy.types.Scene.ai_response = bpy.props.StringProperty(name="Generated Code", default="")
    bpy.types.Scene.ai_execution_status = bpy.props.StringProperty(name="Execution Status", default="")

def unregister():
    bpy.utils.unregister_class(AI_CodeGeneratorPanel)
    bpy.utils.unregister_class(GenerateAndRunCodeOperator)
    del bpy.types.Scene.ai_prompt
    del bpy.types.Scene.ai_response
    del bpy.types.Scene.ai_execution_status

if __name__ == "__main__":
    register()
