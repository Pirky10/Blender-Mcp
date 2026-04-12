"""
CSM.ai Integration for Blender MCP Server
Vector search for 3D models and Mixamo-style animation via CSM Animation API.

Requires: CSM.ai API key (get at https://3d.csm.ai/dashboard/profile/developer-settings)
"""

import bpy
import os
import json
import tempfile
import logging
import requests
import mathutils
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger("BlenderMCP.CSM")


def _get_api_key() -> str:
    key = bpy.context.scene.mcp_csm_api_key
    if not key:
        raise ValueError(
            "CSM.ai API key is not set. Get one at: "
            "https://3d.csm.ai/dashboard/profile/developer-settings"
        )
    return key


def _get_headers() -> dict:
    return {
        'Content-Type': 'application/json',
        'x-api-key': _get_api_key(),
        'x-platform': 'web',
    }


def _get_aabb(obj):
    if obj.type != 'MESH':
        return None
    corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    min_c = [min(v[i] for v in corners) for i in range(3)]
    max_c = [max(v[i] for v in corners) for i in range(3)]
    return [min_c, max_c]


def _clean_imported_glb(filepath: str, mesh_name: str = None):
    """Import GLB and clean up empty parent nodes."""
    existing = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=filepath)
    bpy.context.view_layer.update()

    imported = list(set(bpy.data.objects) - existing)
    if not imported:
        raise RuntimeError("No objects were imported")

    mesh_obj = None
    if len(imported) == 1 and imported[0].type == 'MESH':
        mesh_obj = imported[0]
    else:
        for obj in imported:
            if obj.type == 'EMPTY' and len(obj.children) == 1 and obj.children[0].type == 'MESH':
                child = obj.children[0]
                child.parent = None
                bpy.data.objects.remove(obj)
                mesh_obj = child
                break
        if mesh_obj is None:
            for obj in imported:
                if obj.type == 'MESH':
                    mesh_obj = obj
                    break

    if mesh_obj and mesh_name:
        try:
            mesh_obj.name = mesh_name
            if mesh_obj.data:
                mesh_obj.data.name = mesh_name
        except Exception:
            pass

    return mesh_obj


def _get_user_tier(api_key: str) -> str:
    """Check the user's CSM.ai account tier."""
    try:
        response = requests.get(
            "https://api.csm.ai/user/userdata",
            headers={
                'Accept': '*/*',
                'Content-Type': 'application/json',
                'x-platform': 'web',
                'x-api-key': api_key
            },
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("data", {}).get("tier", "free")
    except Exception:
        pass
    return "free"


def get_csm_status() -> Dict[str, Any]:
    """
    Check if CSM.ai integration is enabled and configured.

    Returns:
        Status dict with enabled flag and configuration info.
    """
    if not bpy.context.scene.mcp_use_csm:
        return {
            "enabled": False,
            "message": (
                "CSM.ai integration is disabled. To enable:\n"
                "1. Open the MCP Server N-Panel\n"
                "2. Check 'Use CSM.ai'\n"
                "3. Enter your CSM.ai API key\n"
                "4. Restart the MCP server"
            )
        }

    api_key = bpy.context.scene.mcp_csm_api_key
    if not api_key:
        return {
            "enabled": False,
            "message": "CSM.ai is enabled but API key is missing. Set it in the MCP Server panel."
        }

    return {"enabled": True, "message": "CSM.ai integration is enabled and ready."}


def search_csm_models(
    search_text: str,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search for 3D models on CSM.ai using vector text search.

    Args:
        search_text: Descriptive text query (e.g., 'blue sports car', 'wooden chair')
        limit: Maximum number of results (default 20)

    Returns:
        List of matching models with IDs, URLs, and metadata.
    """
    api_key = _get_api_key()
    tier = _get_user_tier(api_key)

    data = {
        'search_text': search_text,
        'limit': limit,
        'filter_body': {'tier': tier}
    }

    response = requests.post(
        'https://api.csm.ai/image-to-3d-sessions/session-search/vector-search',
        headers=_get_headers(),
        json=data,
        timeout=30
    )

    if response.status_code != 200:
        error_msg = "CSM.ai search failed"
        if response.status_code in (401, 403):
            error_msg = "Authentication failed. Check your CSM.ai API key."
        raise RuntimeError(f"{error_msg} (Status: {response.status_code})")

    result_data = response.json()
    models = result_data.get('data', [])

    # Filter to models with GLB files
    available = []
    for model in models:
        if model.get('mesh_url_glb'):
            available.append({
                "id": model.get("_id"),
                "session_code": model.get("session_code"),
                "image_url": model.get("image_url"),
                "mesh_url_glb": model.get("mesh_url_glb"),
                "status": model.get("status"),
                "tier": model.get("tier_at_creation")
            })

    # Count by tier
    tier_counts = {}
    for m in models:
        t = m.get("tier_at_creation", "unknown")
        tier_counts[t] = tier_counts.get(t, 0) + 1

    return {
        "status": "success",
        "models": available,
        "total_found": len(models),
        "available_models": len(available),
        "tier_used": tier,
        "models_by_tier": tier_counts,
        "queried_at": datetime.now().isoformat()
    }


def import_csm_model(
    model_id: str,
    mesh_url_glb: str,
    name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Import a 3D model from CSM.ai into Blender.

    Args:
        model_id: The CSM.ai model ID.
        mesh_url_glb: The GLB download URL for the model.
        name: Optional name for the imported object.

    Returns:
        Import result with object info and bounding box.
    """
    if not mesh_url_glb:
        raise ValueError("No GLB URL provided")
    if not name:
        name = f"CSM_Model_{model_id}"

    tmp = tempfile.NamedTemporaryFile(delete=False, prefix=f"csm_{model_id}_", suffix=".glb")
    try:
        response = requests.get(mesh_url_glb, stream=True, timeout=120)
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp.close()

        obj = _clean_imported_glb(tmp.name, mesh_name=name)
        result = {
            "succeed": True,
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
            "scale": list(obj.scale),
            "imported_at": datetime.now().isoformat()
        }
        bbox = _get_aabb(obj)
        if bbox:
            result["world_bounding_box"] = bbox
        return result
    except Exception as e:
        return {"succeed": False, "error": str(e)}
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def get_csm_session_details(
    session_code: str
) -> Dict[str, Any]:
    """
    Get detailed information about a CSM.ai session.

    Args:
        session_code: The unique session code.

    Returns:
        Session details including status, progress, and model URLs.
    """
    response = requests.get(
        f"https://api.csm.ai/image-to-3d-sessions/{session_code}",
        headers=_get_headers(),
        timeout=30
    )

    if response.status_code != 200:
        error_map = {
            403: "Authentication failed. Check your API key.",
            401: "Unauthorized. Check your API key.",
            404: f"Session not found: {session_code}",
        }
        raise RuntimeError(error_map.get(response.status_code, f"API error: {response.status_code}"))

    data = response.json().get("data", {})
    return {
        "status": "success",
        "session_code": session_code,
        "session_status": data.get("session_status"),
        "percent_done": data.get("percent_done"),
        "image_url": data.get("image_url"),
        "mesh_url_glb": data.get("mesh_url_glb"),
        "mesh_url_obj": data.get("mesh_url_obj"),
        "mesh_url_fbx": data.get("mesh_url_fbx"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


def animate_csm_object(
    object_name: str,
    animation_fbx_path: str,
    output_format: str = "glb",
    handle_original: str = "hide"
) -> Dict[str, Any]:
    """
    Apply Mixamo-style animation to a mesh using the CSM Animation API.

    This requires:
    1. A mesh object in the Blender scene (previously imported via CSM or created)
    2. An animation FBX file (download from Mixamo with 'Without Skin' option)

    Args:
        object_name: Name of the mesh object to animate.
        animation_fbx_path: Absolute path to the animation .fbx file.
        output_format: Output format for the animated mesh (glb or fbx).
        handle_original: What to do with the original mesh (hide, delete, keep).

    Returns:
        Animation result with imported animated object details.
    """
    # Validate inputs
    obj = bpy.data.objects.get(object_name)
    if not obj:
        raise ValueError(f"Object '{object_name}' not found in the scene")
    if obj.type != 'MESH':
        raise ValueError(f"Object '{object_name}' is not a mesh (type: {obj.type})")

    if not os.path.exists(animation_fbx_path):
        raise ValueError(f"Animation FBX not found: {animation_fbx_path}")

    api_key = _get_api_key()

    # Step 1: Export the mesh as GLB for CSM
    export_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".glb")
    export_tmp.close()

    try:
        # Select only target object
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        bpy.ops.export_scene.gltf(
            filepath=export_tmp.name,
            use_selection=True,
            export_format='GLB'
        )
        logger.info(f"Exported mesh to: {export_tmp.name}")
    except Exception as e:
        raise RuntimeError(f"Failed to export mesh: {e}")

    # Step 2: Upload to CSM Animation API
    try:
        with open(export_tmp.name, 'rb') as mesh_f, open(animation_fbx_path, 'rb') as anim_f:
            files = {
                'mesh_file': ('mesh.glb', mesh_f, 'model/gltf-binary'),
                'animation_file': ('animation.fbx', anim_f, 'application/octet-stream'),
            }
            headers = {'x-api-key': api_key}
            data = {'output_format': output_format}

            response = requests.post(
                'https://api.csm.ai/animation/apply',
                headers=headers,
                files=files,
                data=data,
                timeout=300  # Animation can take a while
            )

        if response.status_code != 200:
            raise RuntimeError(f"CSM Animation API error: {response.status_code} - {response.text[:500]}")

        result_data = response.json()

        # Step 3: Download animated result
        animated_url = result_data.get("animated_mesh_url") or result_data.get("result_url")
        if not animated_url:
            raise RuntimeError(f"No animated mesh URL in response: {result_data}")

        anim_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_format}")
        dl = requests.get(animated_url, stream=True, timeout=120)
        dl.raise_for_status()
        for chunk in dl.iter_content(chunk_size=8192):
            anim_tmp.write(chunk)
        anim_tmp.close()

        # Step 4: Import animated mesh
        existing = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=anim_tmp.name)
        bpy.context.view_layer.update()

        new_objects = list(set(bpy.data.objects) - existing)
        animated_name = f"{object_name}_animated"
        for new_obj in new_objects:
            if new_obj.type in ('MESH', 'ARMATURE'):
                new_obj.name = animated_name
                break

        # Step 5: Handle original object
        if handle_original == "hide":
            obj.hide_set(True)
            obj.hide_render = True
        elif handle_original == "delete":
            bpy.data.objects.remove(obj)

        return {
            "success": True,
            "animated_object": animated_name,
            "imported_objects": [o.name for o in new_objects],
            "original_handled": handle_original,
            "animated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Animation failed: {e}")
        return {"success": False, "error": str(e)}
    finally:
        for path in [export_tmp.name]:
            try:
                os.unlink(path)
            except Exception:
                pass
        try:
            os.unlink(anim_tmp.name)
        except Exception:
            pass
