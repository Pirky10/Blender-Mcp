"""
Asset Creation Strategy for Blender MCP Server
Provides the AI agent with decision-making guidance on which integration to use.

This tool is a critical "meta-tool" — when called, it returns a comprehensive strategy
prompt that teaches the AI agent the optimal workflow for creating 3D content.
"""

from typing import Dict, Any


def get_asset_creation_strategy() -> Dict[str, Any]:
    """
    Get the recommended strategy for creating 3D assets in Blender.

    Call this FIRST before creating any 3D content to understand which
    integrations are available and the optimal workflow for each type of asset.

    Returns:
        Comprehensive strategy guide with priority order, workflows, and tips.
    """
    return {
        "strategy": _STRATEGY_PROMPT,
        "integrations_summary": {
            "polyhaven": {
                "best_for": "Environment HDRIs, PBR textures, basic 3D models",
                "api_key_required": False,
                "tools": [
                    "get_polyhaven_status",
                    "get_polyhaven_categories",
                    "search_polyhaven_assets",
                    "download_polyhaven_asset",
                    "set_polyhaven_texture"
                ]
            },
            "sketchfab": {
                "best_for": "Realistic 3D models, wide variety of specific subjects",
                "api_key_required": True,
                "tools": [
                    "get_sketchfab_status",
                    "search_sketchfab_models",
                    "get_sketchfab_model_preview",
                    "download_sketchfab_model"
                ]
            },
            "hyper3d_rodin": {
                "best_for": "AI-generated single 3D items from text or images",
                "api_key_required": True,
                "tools": [
                    "get_hyper3d_status",
                    "generate_hyper3d_model_text",
                    "generate_hyper3d_model_images",
                    "poll_rodin_job_status",
                    "import_rodin_generated_asset"
                ]
            },
            "csm_ai": {
                "best_for": "3D model vector search and Mixamo-style character animation",
                "api_key_required": True,
                "tools": [
                    "get_csm_status",
                    "search_csm_models",
                    "import_csm_model",
                    "get_csm_session_details",
                    "animate_csm_object"
                ]
            },
            "hunyuan3d": {
                "best_for": "AI-generated 3D models from text or images (Tencent Cloud)",
                "api_key_required": True,
                "tools": [
                    "get_hunyuan3d_status",
                    "generate_hunyuan3d_model",
                    "poll_hunyuan_job_status",
                    "import_hunyuan3d_asset"
                ]
            },
            "mixamo": {
                "best_for": "Animation FBX file management, common animation catalog",
                "api_key_required": False,
                "tools": [
                    "download_animation_fbx",
                    "list_common_animations"
                ]
            }
        }
    }


_STRATEGY_PROMPT = """
=== ASSET CREATION STRATEGY FOR BLENDER MCP ===

STEP 0: Always check the scene first with get_scene_info()

STEP 1: Check which integrations are available:
  - get_polyhaven_status()    → Free HDRIs, textures, models (NO key needed)
  - get_sketchfab_status()    → Huge library of realistic 3D models
  - get_hyper3d_status()      → AI text/image → 3D generation
  - get_csm_status()          → 3D model search + character animation
  - get_hunyuan3d_status()    → Tencent AI 3D generation

STEP 2: Choose the RIGHT source based on what you need:

  ┌─────────────────────────────────┬──────────────────────────┐
  │ What You Need                   │ Best Source (Priority)    │
  ├─────────────────────────────────┼──────────────────────────┤
  │ Environment/sky lighting (HDRI) │ Poly Haven               │
  │ PBR materials/textures          │ Poly Haven               │
  │ Generic furniture/objects       │ Poly Haven → Sketchfab   │
  │ Specific real-world objects     │ Sketchfab → CSM.ai       │
  │ Custom/unique items             │ Hyper3D → Hunyuan3D      │
  │ Character animation             │ CSM.ai (animate_csm_object) │
  │ Simple primitives               │ Blender native scripting │
  └─────────────────────────────────┴──────────────────────────┘

=== POLY HAVEN WORKFLOW ===
  1. search_polyhaven_assets(asset_type, categories) to find assets
  2. download_polyhaven_asset(asset_id, asset_type, resolution) to import
  3. set_polyhaven_texture(object_name, texture_id) to apply textures
  - For HDRIs: use asset_type="hdris"
  - For textures: use asset_type="textures"
  - For models: use asset_type="models"

=== SKETCHFAB WORKFLOW ===
  1. search_sketchfab_models(query) to find models
  2. get_sketchfab_model_preview(uid) to preview before downloading
  3. download_sketchfab_model(uid) to import into scene
  - Only downloadable models can be accessed
  - Wider variety than Poly Haven for specific subjects

=== HYPER3D RODIN WORKFLOW ===
  ⚠ Good for SINGLE items only. Do NOT try to generate entire scenes.
  1. generate_hyper3d_model_text(text_prompt) or generate_hyper3d_model_images(...)
  2. poll_rodin_job_status(subscription_key/request_id) — keep polling until done
  3. import_rodin_generated_asset(name, task_uuid/request_id)
  4. ALWAYS check world_bounding_box after import and adjust position/scale
  - Duplicating previous objects is cheaper than re-generating

=== CSM.AI WORKFLOW ===
  For 3D MODELS:
    1. search_csm_models(search_text) to vector-search the library
    2. import_csm_model(model_id, mesh_url_glb, name)
    3. Check world_bounding_box and adjust

  For CHARACTER ANIMATION (Mixamo-style):
    1. list_common_animations() to see available animation types
    2. download_animation_fbx(url or local_path) to prepare the FBX
       - Visit mixamo.com → search animation → download FBX ("Without Skin")
    3. animate_csm_object(object_name, animation_fbx_path)
    ⚠ ALWAYS use CSM for character motion (walk, run, dance, fight)
    ⚠ Only use Blender native keyframes for simple rotation/spin/move

=== HUNYUAN3D WORKFLOW ===
  ⚠ Similar to Hyper3D — generate single items only.
  1. generate_hunyuan3d_model(text_prompt or image_url)
  2. poll_hunyuan_job_status(job_id) — poll until "DONE"
  3. import_hunyuan3d_asset(name, zip_file_url)

=== ANIMATION DECISION TREE ===
  User wants character motion (walk/run/dance/fight)?
    → CSM Animation API (animate_csm_object)
  User explicitly says "blender native" or "keyframes"?
    → Blender native keyframe scripting
  User wants simple rotation/spin/movement?
    → Blender native keyframe scripting

=== FALLBACK RULES ===
  Only fall back to Blender scripting (create_mesh_object, etc.) when:
  - ALL integrations are disabled
  - A simple primitive is explicitly requested
  - No suitable asset exists in any library
  - AI generation failed
  - Task specifically requires basic material/color

=== POST-IMPORT CHECKLIST ===
  After importing ANY asset, ALWAYS:
  1. Check world_bounding_box to verify size and position
  2. Ensure objects don't clip through each other
  3. Verify spatial relationships are correct
  4. Give objects meaningful names
"""
