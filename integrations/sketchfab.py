"""
Sketchfab Integration for Blender MCP Server
Search, preview, and download 3D models from Sketchfab.

Requires: Sketchfab API key (free at sketchfab.com/settings/password)
"""

import bpy
import os
import tempfile
import shutil
import zipfile
import logging
import requests
import mathutils
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import suppress

logger = logging.getLogger("BlenderMCP.Sketchfab")

API_BASE = "https://api.sketchfab.com/v3"


def _get_headers() -> dict:
    """Get authorization headers using the stored API key."""
    api_key = bpy.context.scene.mcp_sketchfab_api_key
    if not api_key:
        raise ValueError("Sketchfab API key is not configured. Set it in the MCP Server N-Panel.")
    return {"Authorization": f"Token {api_key}"}


def get_sketchfab_status() -> Dict[str, Any]:
    """
    Check if Sketchfab integration is enabled and the API key is valid.

    Returns:
        Status dict with enabled flag, username if authenticated, or instructions if disabled.
    """
    enabled = bpy.context.scene.mcp_use_sketchfab
    api_key = bpy.context.scene.mcp_sketchfab_api_key

    if not enabled:
        return {
            "enabled": False,
            "message": (
                "Sketchfab integration is currently disabled. To enable it:\n"
                "1. In the 3D Viewport, find the MCP Server panel (press N)\n"
                "2. Check 'Use Sketchfab'\n"
                "3. Enter your Sketchfab API Key\n"
                "4. Restart the MCP server"
            )
        }

    if not api_key:
        return {
            "enabled": False,
            "message": "Sketchfab is enabled but the API key is missing. Enter it in the MCP Server panel."
        }

    # Validate the key
    try:
        response = requests.get(f"{API_BASE}/me", headers=_get_headers(), timeout=15)
        if response.status_code == 200:
            username = response.json().get("username", "Unknown")
            return {
                "enabled": True,
                "message": f"Sketchfab integration is enabled. Logged in as: {username}"
            }
        return {"enabled": False, "message": f"Sketchfab API key invalid. Status: {response.status_code}"}
    except requests.exceptions.Timeout:
        return {"enabled": False, "message": "Timeout connecting to Sketchfab. Check your internet."}
    except Exception as e:
        return {"enabled": False, "message": f"Error testing Sketchfab API key: {e}"}


def search_sketchfab_models(
    query: str,
    categories: Optional[str] = None,
    count: int = 20,
    downloadable: bool = True
) -> Dict[str, Any]:
    """
    Search for 3D models on Sketchfab.

    Args:
        query: Search query text (e.g., 'medieval castle', 'sports car')
        categories: Optional category filter
        count: Maximum results to return (default 20)
        downloadable: Only return downloadable models (default True)

    Returns:
        Sketchfab search results with model details, thumbnails, and UIDs.
    """
    params = {
        "type": "models",
        "q": query,
        "count": count,
        "downloadable": downloadable,
        "archives_flavours": False
    }
    if categories:
        params["categories"] = categories

    response = requests.get(
        f"{API_BASE}/search",
        headers=_get_headers(),
        params=params,
        timeout=30
    )

    if response.status_code == 401:
        raise ValueError("Sketchfab authentication failed (401). Check your API key.")
    if response.status_code != 200:
        raise RuntimeError(f"Sketchfab search failed with status {response.status_code}")

    return response.json()


def get_sketchfab_model_preview(
    uid: str
) -> Dict[str, Any]:
    """
    Get a thumbnail preview image of a Sketchfab model.

    Args:
        uid: The unique Sketchfab model identifier.

    Returns:
        Base64-encoded thumbnail image with model metadata.
    """
    import base64

    response = requests.get(f"{API_BASE}/models/{uid}", headers=_get_headers(), timeout=30)
    if response.status_code == 404:
        raise ValueError(f"Model not found: {uid}")
    if response.status_code != 200:
        raise RuntimeError(f"Failed to get model info: {response.status_code}")

    data = response.json()
    thumbnails = data.get("thumbnails", {}).get("images", [])
    if not thumbnails:
        raise RuntimeError("No thumbnail available for this model")

    # Prefer medium-size thumbnail
    selected = None
    for thumb in thumbnails:
        if 400 <= thumb.get("width", 0) <= 800:
            selected = thumb
            break
    if not selected:
        selected = thumbnails[0]

    thumb_url = selected.get("url")
    if not thumb_url:
        raise RuntimeError("Thumbnail URL not found")

    img_response = requests.get(thumb_url, timeout=30)
    if img_response.status_code != 200:
        raise RuntimeError(f"Failed to download thumbnail: {img_response.status_code}")

    image_data = base64.b64encode(img_response.content).decode('ascii')
    content_type = img_response.headers.get("Content-Type", "")
    img_format = "png" if "png" in content_type else "jpeg"

    return {
        "success": True,
        "image_data": image_data,
        "format": img_format,
        "model_name": data.get("name", "Unknown"),
        "author": data.get("user", {}).get("username", "Unknown"),
        "uid": uid,
        "thumbnail_width": selected.get("width"),
        "thumbnail_height": selected.get("height")
    }


def download_sketchfab_model(
    uid: str,
    normalize_size: bool = False,
    target_size: float = 1.0
) -> Dict[str, Any]:
    """
    Download and import a Sketchfab model into Blender by its UID.

    Args:
        uid: The unique Sketchfab model identifier.
        normalize_size: If True, scale model so its largest dimension equals target_size.
        target_size: Target size in Blender units (meters) for normalization.

    Returns:
        Import result with object names, bounding box, and dimensions.
    """
    headers = _get_headers()

    # Request download URL
    response = requests.get(f"{API_BASE}/models/{uid}/download", headers=headers, timeout=30)
    if response.status_code == 401:
        raise ValueError("Authentication failed (401). Check your API key.")
    if response.status_code != 200:
        raise RuntimeError(f"Download request failed: status {response.status_code}")

    data = response.json()
    gltf_data = data.get("gltf")
    if not gltf_data:
        raise RuntimeError("No glTF download available. Make sure the model is downloadable.")

    download_url = gltf_data.get("url")
    if not download_url:
        raise RuntimeError("No download URL available for this model.")

    # Download ZIP
    model_response = requests.get(download_url, timeout=120)
    if model_response.status_code != 200:
        raise RuntimeError(f"Model download failed: status {model_response.status_code}")

    temp_dir = tempfile.mkdtemp()
    try:
        zip_path = os.path.join(temp_dir, f"{uid}.zip")
        with open(zip_path, "wb") as f:
            f.write(model_response.content)

        # Secure extraction
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            abs_temp = os.path.abspath(temp_dir)
            for info in zip_ref.infolist():
                target = os.path.abspath(os.path.join(temp_dir, os.path.normpath(info.filename)))
                if not target.startswith(abs_temp):
                    raise RuntimeError("Security: zip contains path traversal")
                if ".." in info.filename:
                    raise RuntimeError("Security: zip contains directory traversal")
            zip_ref.extractall(temp_dir)

        # Find glTF file
        gltf_files = [f for f in os.listdir(temp_dir) if f.endswith(('.gltf', '.glb'))]
        if not gltf_files:
            raise RuntimeError("No glTF file found in downloaded model")

        main_file = os.path.join(temp_dir, gltf_files[0])
        bpy.ops.import_scene.gltf(filepath=main_file)

        imported_objects = list(bpy.context.selected_objects)
        imported_names = [obj.name for obj in imported_objects]

        # Calculate bounding box
        root_objects = [obj for obj in imported_objects if obj.parent is None]

        def _get_all_mesh_children(obj):
            meshes = []
            if obj.type == 'MESH':
                meshes.append(obj)
            for child in obj.children:
                meshes.extend(_get_all_mesh_children(child))
            return meshes

        all_meshes = []
        for obj in root_objects:
            all_meshes.extend(_get_all_mesh_children(obj))

        result = {
            "success": True,
            "message": "Model imported successfully from Sketchfab",
            "imported_objects": imported_names,
            "imported_at": datetime.now().isoformat()
        }

        if all_meshes:
            all_min = mathutils.Vector((float('inf'),) * 3)
            all_max = mathutils.Vector((float('-inf'),) * 3)

            for mesh_obj in all_meshes:
                for corner in mesh_obj.bound_box:
                    wc = mesh_obj.matrix_world @ mathutils.Vector(corner)
                    all_min.x = min(all_min.x, wc.x)
                    all_min.y = min(all_min.y, wc.y)
                    all_min.z = min(all_min.z, wc.z)
                    all_max.x = max(all_max.x, wc.x)
                    all_max.y = max(all_max.y, wc.y)
                    all_max.z = max(all_max.z, wc.z)

            dimensions = [all_max[i] - all_min[i] for i in range(3)]
            max_dim = max(dimensions)

            if normalize_size and max_dim > 0:
                scale_factor = target_size / max_dim
                for root in root_objects:
                    root.scale = tuple(s * scale_factor for s in root.scale)
                bpy.context.view_layer.update()

                # Recalculate after scaling
                all_min = mathutils.Vector((float('inf'),) * 3)
                all_max = mathutils.Vector((float('-inf'),) * 3)
                for mesh_obj in all_meshes:
                    for corner in mesh_obj.bound_box:
                        wc = mesh_obj.matrix_world @ mathutils.Vector(corner)
                        all_min.x = min(all_min.x, wc.x)
                        all_min.y = min(all_min.y, wc.y)
                        all_min.z = min(all_min.z, wc.z)
                        all_max.x = max(all_max.x, wc.x)
                        all_max.y = max(all_max.y, wc.y)
                        all_max.z = max(all_max.z, wc.z)
                dimensions = [all_max[i] - all_min[i] for i in range(3)]
                result["scale_applied"] = round(scale_factor, 6)
                result["normalized"] = True

            result["world_bounding_box"] = [list(all_min), list(all_max)]
            result["dimensions"] = [round(d, 4) for d in dimensions]

        return result

    finally:
        with suppress(Exception):
            shutil.rmtree(temp_dir)
