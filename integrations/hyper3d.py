"""
Hyper3D Rodin Integration for Blender MCP Server
AI-powered 3D model generation from text prompts or images.

Supports two modes: MAIN_SITE (hyperhuman.deemos.com) and FAL_AI (fal.ai)
Requires: Hyper3D Rodin API key
"""

import bpy
import os
import json
import base64
import tempfile
import logging
import requests
import mathutils
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger("BlenderMCP.Hyper3D")

RODIN_FREE_TRIAL_KEY = "k9TcfFoEhNd9cCPP2guHAHHHkctZHIRhZDywZ1euGUXwihbYLpOjQhofby80NJez"


def _get_mode() -> str:
    return bpy.context.scene.mcp_hyper3d_mode


def _get_api_key() -> str:
    key = bpy.context.scene.mcp_hyper3d_api_key
    if not key:
        raise ValueError("Hyper3D Rodin API key is not set. Configure it in the MCP Server N-Panel.")
    return key


def _get_aabb(obj):
    """Calculate world-space axis-aligned bounding box."""
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
        raise RuntimeError("No objects were imported from the GLB file")

    mesh_obj = None
    if len(imported) == 1 and imported[0].type == 'MESH':
        mesh_obj = imported[0]
    elif len(imported) == 2:
        empties = [o for o in imported if o.type == 'EMPTY']
        if len(empties) == 1 and len(empties[0].children) == 1:
            child = empties[0].children[0]
            if child.type == 'MESH':
                child.parent = None
                bpy.data.objects.remove(empties[0])
                mesh_obj = child

    if mesh_obj is None:
        # Fallback: find first mesh in imported
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


def get_hyper3d_status() -> Dict[str, Any]:
    """
    Check if Hyper3D Rodin integration is enabled and configured.

    Returns:
        Status dict with enabled flag, current mode, and key type info.
    """
    enabled = bpy.context.scene.mcp_use_hyper3d
    if not enabled:
        return {
            "enabled": False,
            "message": (
                "Hyper3D Rodin is disabled. To enable:\n"
                "1. Open the MCP Server N-Panel\n"
                "2. Check 'Use Hyper3D Rodin'\n"
                "3. Enter your API key and select mode\n"
                "4. Restart the MCP server"
            )
        }

    api_key = bpy.context.scene.mcp_hyper3d_api_key
    if not api_key:
        return {
            "enabled": False,
            "message": "Hyper3D Rodin is enabled but API key is missing. Enter it in the MCP Server panel."
        }

    mode = _get_mode()
    key_type = "free_trial" if api_key == RODIN_FREE_TRIAL_KEY else "private"
    return {
        "enabled": True,
        "message": f"Hyper3D Rodin is enabled. Mode: {mode}. Key type: {key_type}"
    }


def generate_hyper3d_model_text(
    text_prompt: str,
    bbox_condition: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Generate a 3D model from a text description using Hyper3D Rodin.

    Args:
        text_prompt: Short English description of the desired model.
        bbox_condition: Optional [L, W, H] ratio list for controlling model proportions.

    Returns:
        Job info with task_uuid and subscription_key for polling.
    """
    api_key = _get_api_key()
    mode = _get_mode()

    if bbox_condition:
        bbox_condition = [int(float(i) / max(bbox_condition) * 100) for i in bbox_condition]

    if mode == "MAIN_SITE":
        files = [
            ("tier", (None, "Sketch")),
            ("mesh_mode", (None, "Raw")),
            ("prompt", (None, text_prompt)),
        ]
        if bbox_condition:
            files.append(("bbox_condition", (None, json.dumps(bbox_condition))))

        response = requests.post(
            "https://hyperhuman.deemos.com/api/v2/rodin",
            headers={"Authorization": f"Bearer {api_key}"},
            files=files
        )
        data = response.json()
        if data.get("submit_time"):
            return {
                "task_uuid": data["uuid"],
                "subscription_key": data["jobs"]["subscription_key"],
                "mode": "MAIN_SITE"
            }
        return data

    elif mode == "FAL_AI":
        req_data = {"tier": "Sketch", "prompt": text_prompt}
        if bbox_condition:
            req_data["bbox_condition"] = bbox_condition

        response = requests.post(
            "https://queue.fal.run/fal-ai/hyper3d/rodin",
            headers={
                "Authorization": f"Key {api_key}",
                "Content-Type": "application/json",
            },
            json=req_data
        )
        return response.json()

    raise ValueError(f"Unknown Hyper3D mode: {mode}")


def generate_hyper3d_model_images(
    input_image_paths: Optional[List[str]] = None,
    input_image_urls: Optional[List[str]] = None,
    bbox_condition: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Generate a 3D model from reference images using Hyper3D Rodin.

    Args:
        input_image_paths: Absolute paths to input images (for MAIN_SITE mode).
        input_image_urls: URLs of input images (for FAL_AI mode).
        bbox_condition: Optional [L, W, H] ratio for model proportions.

    Returns:
        Job info with task_uuid/request_id for polling.
    """
    if input_image_paths and input_image_urls:
        raise ValueError("Provide either image paths or URLs, not both.")
    if not input_image_paths and not input_image_urls:
        raise ValueError("No images provided. Supply either paths or URLs.")

    api_key = _get_api_key()
    mode = _get_mode()

    if bbox_condition:
        bbox_condition = [int(float(i) / max(bbox_condition) * 100) for i in bbox_condition]

    if mode == "MAIN_SITE":
        if not input_image_paths:
            raise ValueError("MAIN_SITE mode requires input_image_paths, not URLs.")
        images = []
        for path in input_image_paths:
            if not os.path.exists(path):
                raise ValueError(f"Image not found: {path}")
            ext = os.path.splitext(path)[1]
            with open(path, "rb") as f:
                images.append((ext, base64.b64encode(f.read()).decode("ascii")))

        files = [
            *[("images", (f"{i:04d}{suffix}", img)) for i, (suffix, img) in enumerate(images)],
            ("tier", (None, "Sketch")),
            ("mesh_mode", (None, "Raw")),
        ]
        if bbox_condition:
            files.append(("bbox_condition", (None, json.dumps(bbox_condition))))

        response = requests.post(
            "https://hyperhuman.deemos.com/api/v2/rodin",
            headers={"Authorization": f"Bearer {api_key}"},
            files=files
        )
        data = response.json()
        if data.get("submit_time"):
            return {
                "task_uuid": data["uuid"],
                "subscription_key": data["jobs"]["subscription_key"],
                "mode": "MAIN_SITE"
            }
        return data

    elif mode == "FAL_AI":
        if not input_image_urls:
            raise ValueError("FAL_AI mode requires input_image_urls, not file paths.")
        req_data = {"tier": "Sketch", "input_image_urls": input_image_urls}
        if bbox_condition:
            req_data["bbox_condition"] = bbox_condition

        response = requests.post(
            "https://queue.fal.run/fal-ai/hyper3d/rodin",
            headers={
                "Authorization": f"Key {api_key}",
                "Content-Type": "application/json",
            },
            json=req_data
        )
        return response.json()

    raise ValueError(f"Unknown Hyper3D mode: {mode}")


def poll_rodin_job_status(
    subscription_key: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Poll the status of a Hyper3D Rodin generation job.

    For MAIN_SITE mode: provide subscription_key. Status is done when all are "Done".
    For FAL_AI mode: provide request_id. Status is done when "COMPLETED".

    Args:
        subscription_key: The subscription key from job creation (MAIN_SITE mode).
        request_id: The request ID from job creation (FAL_AI mode).

    Returns:
        Job status information.
    """
    api_key = _get_api_key()
    mode = _get_mode()

    if mode == "MAIN_SITE" and subscription_key:
        response = requests.post(
            "https://hyperhuman.deemos.com/api/v2/status",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"subscription_key": subscription_key}
        )
        data = response.json()
        return {"status_list": [j["status"] for j in data["jobs"]]}

    elif mode == "FAL_AI" and request_id:
        response = requests.get(
            f"https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}/status",
            headers={"Authorization": f"KEY {api_key}"}
        )
        return response.json()

    raise ValueError("Provide subscription_key (MAIN_SITE) or request_id (FAL_AI)")


def import_rodin_generated_asset(
    name: str,
    task_uuid: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Import a Hyper3D Rodin generated model into Blender after generation completes.

    Args:
        name: Name to assign to the imported object.
        task_uuid: Task UUID from MAIN_SITE mode generation.
        request_id: Request ID from FAL_AI mode generation.

    Returns:
        Import result with object info and bounding box.
    """
    api_key = _get_api_key()
    mode = _get_mode()

    if mode == "MAIN_SITE" and task_uuid:
        response = requests.post(
            "https://hyperhuman.deemos.com/api/v2/download",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"task_uuid": task_uuid}
        )
        data = response.json()

        glb_url = None
        for item in data.get("list", []):
            if item.get("name", "").endswith(".glb"):
                glb_url = item["url"]
                break

        if not glb_url:
            raise RuntimeError("No GLB file found. Ensure the job is done first.")

    elif mode == "FAL_AI" and request_id:
        response = requests.get(
            f"https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}",
            headers={"Authorization": f"Key {api_key}"}
        )
        data = response.json()
        glb_url = data.get("model_mesh", {}).get("url")
        if not glb_url:
            raise RuntimeError("No model mesh URL in FAL_AI response")
    else:
        raise ValueError("Provide task_uuid (MAIN_SITE) or request_id (FAL_AI)")

    # Download and import
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".glb")
    try:
        dl = requests.get(glb_url, stream=True)
        dl.raise_for_status()
        for chunk in dl.iter_content(chunk_size=8192):
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
