import os
import requests
import re
import bpy  # type: ignore
import textwrap
import time

bl_info = {
    "name": "blendAI",
    "description": "Generates and executes Blender scripts based on a prompt",
    "author": "Rajarshi Datta & Rahil Masood",
    "version": (2, 0),
    "blender": (4, 3, 2),
    "location": "View3D > Sidebar > AI Generator",
    "category": "3D View",
}

# Secure API Key Handling
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
if not OPENROUTER_API_KEY:
    raise ValueError("Missing OpenRouter API key. Set OPENROUTER_API_KEY as an environment variable.")

MODEL_NAME = "anthropic/claude-3.5-sonnet"
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
            error_message = f"# Error: OpenRouter API returned status {response.status_code}, Message: {response.text}"
            append_to_log("API Error", error_message)
            return error_message
    except Exception as e:
        error_message = f"# Error generating code: {str(e)}"
        append_to_log("Exception", error_message)
        return error_message

def execute_script_with_retries(code, max_retries=3):
    """Executes AI-generated script with retries and logs object location before execution."""
    for attempt in range(1, max_retries + 1):
        try:
            if not code.strip() or code.strip().startswith("#"):
                return "No valid code to execute."

            compile(code, '<string>', 'exec')
            exec(code, globals())

            success_message = "Script executed successfully."
            append_to_log("Execution Result", success_message)
            return success_message
        except Exception as e:
            if attempt < max_retries:
                time.sleep(0.5)
                continue
            error_message = f"# Error executing script after {max_retries} attempts: {str(e)}"
            append_to_log("Execution Error", error_message)
            return error_message

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
        layout.operator("script.generate_and_run_code", text="Generate Prompt")
        layout.separator(factor=2.0)
        layout.label(text="Generated Code:")
        layout.prop(context.scene, "ai_response", text="")
        layout.separator(factor=1.5)
        layout.label(text="Execution Status:")
        layout.prop(context.scene, "ai_execution_status", text="")
