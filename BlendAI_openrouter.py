bl_info = {
    "name": "BlendAI",
    "description": "Generates and executes Blender scripts using various AI models via OpenRouter",
    "author": "Rahil Masood (Modified)",
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

def register():
    bpy.utils.register_class(AI_CodeGeneratorPanel)
    bpy.utils.register_class(GenerateAndRunCodeOperator)
    bpy.utils.register_class(GenerateOnlyOperator)
    
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

def unregister():
    bpy.utils.unregister_class(AI_CodeGeneratorPanel)
    bpy.utils.unregister_class(GenerateAndRunCodeOperator)
    bpy.utils.unregister_class(GenerateOnlyOperator)
    
    del bpy.types.Scene.ai_prompt
    del bpy.types.Scene.ai_response
    del bpy.types.Scene.ai_execution_status
    del bpy.types.Scene.ai_selected_model

if __name__ == "__main__":
    register()