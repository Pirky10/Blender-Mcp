"""
Poly Haven Integration for Blender MCP Server
Provides HDRIs, textures, and 3D models from polyhaven.com

No API key required - Poly Haven is a free, open asset library.
"""

import bpy
import os
import tempfile
import shutil
import logging
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import suppress

logger = logging.getLogger("BlenderMCP.PolyHaven")

REQ_HEADERS = requests.utils.default_headers()
REQ_HEADERS.update({"User-Agent": "blender-mcp-server"})

API_BASE = "https://api.polyhaven.com"


def get_polyhaven_status() -> Dict[str, Any]:
    """
    Check if Poly Haven integration is enabled in Blender.

    Returns:
        Status dict with enabled flag and instructions if disabled.
    """
    enabled = bpy.context.scene.mcp_use_polyhaven
    if enabled:
        return {
            "enabled": True,
            "message": "PolyHaven integration is enabled and ready to use. No API key required."
        }
    return {
        "enabled": False,
        "message": (
            "PolyHaven integration is currently disabled. To enable it:\n"
            "1. In the 3D Viewport, find the MCP Server panel in the sidebar (press N if hidden)\n"
            "2. Check the 'Use Poly Haven' checkbox\n"
            "3. Restart the MCP server"
        )
    }


def get_polyhaven_categories(
    asset_type: str = "all"
) -> Dict[str, Any]:
    """
    Get available categories for a specific asset type from Poly Haven.

    Args:
        asset_type: Type of asset (hdris, textures, models, all)

    Returns:
        Dictionary of categories and their counts.
    """
    if asset_type not in ["hdris", "textures", "models", "all"]:
        raise ValueError(f"Invalid asset type: {asset_type}. Must be one of: hdris, textures, models, all")

    response = requests.get(f"{API_BASE}/categories/{asset_type}", headers=REQ_HEADERS)
    if response.status_code == 200:
        return {"categories": response.json(), "asset_type": asset_type}
    raise RuntimeError(f"Poly Haven API request failed with status code {response.status_code}")


def search_polyhaven_assets(
    asset_type: Optional[str] = None,
    categories: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search for assets from Poly Haven with optional filtering.

    Args:
        asset_type: Filter by type (hdris, textures, models). None for all.
        categories: Comma-separated category names to filter by.

    Returns:
        Dictionary with matching assets (limited to 20 results).
    """
    params = {}
    if asset_type and asset_type != "all":
        if asset_type not in ["hdris", "textures", "models"]:
            raise ValueError(f"Invalid asset type: {asset_type}. Must be one of: hdris, textures, models")
        params["type"] = asset_type
    if categories:
        params["categories"] = categories

    response = requests.get(f"{API_BASE}/assets", params=params, headers=REQ_HEADERS)
    if response.status_code != 200:
        raise RuntimeError(f"Poly Haven API failed with status {response.status_code}")

    assets = response.json()
    limited_assets = {}
    for i, (key, value) in enumerate(assets.items()):
        if i >= 20:
            break
        limited_assets[key] = value

    return {
        "assets": limited_assets,
        "total_count": len(assets),
        "returned_count": len(limited_assets),
        "queried_at": datetime.now().isoformat()
    }


def download_polyhaven_asset(
    asset_id: str,
    asset_type: str,
    resolution: str = "1k",
    file_format: Optional[str] = None
) -> Dict[str, Any]:
    """
    Download and import a Poly Haven asset (HDRI, texture, or model) into Blender.

    Args:
        asset_id: The Poly Haven asset identifier (e.g., 'autumn_forest')
        asset_type: Type of asset (hdris, textures, models)
        resolution: Resolution to download (1k, 2k, 4k, 8k)
        file_format: File format (hdr/exr for HDRIs, jpg/png for textures, gltf/fbx for models)

    Returns:
        Import result with details about what was loaded.
    """
    # Get file info from Poly Haven
    files_response = requests.get(f"{API_BASE}/files/{asset_id}", headers=REQ_HEADERS)
    if files_response.status_code != 200:
        raise RuntimeError(f"Failed to get asset files: {files_response.status_code}")

    files_data = files_response.json()

    if asset_type == "hdris":
        return _import_hdri(asset_id, files_data, resolution, file_format or "hdr")
    elif asset_type == "textures":
        return _import_texture(asset_id, files_data, resolution, file_format or "jpg")
    elif asset_type == "models":
        return _import_model(asset_id, files_data, resolution, file_format or "gltf")
    else:
        raise ValueError(f"Unsupported asset type: {asset_type}")


def _import_hdri(asset_id: str, files_data: dict, resolution: str, file_format: str) -> Dict[str, Any]:
    """Import an HDRI as world environment lighting."""
    if "hdri" not in files_data or resolution not in files_data["hdri"]:
        raise ValueError(f"Resolution '{resolution}' not available for this HDRI")
    if file_format not in files_data["hdri"][resolution]:
        raise ValueError(f"Format '{file_format}' not available for this HDRI at {resolution}")

    file_info = files_data["hdri"][resolution][file_format]
    file_url = file_info["url"]

    with tempfile.NamedTemporaryFile(suffix=f".{file_format}", delete=False) as tmp_file:
        response = requests.get(file_url, headers=REQ_HEADERS)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download HDRI: {response.status_code}")
        tmp_file.write(response.content)
        tmp_path = tmp_file.name

    try:
        # Setup world nodes
        if not bpy.data.worlds:
            bpy.data.worlds.new("World")
        world = bpy.data.worlds[0]
        world.use_nodes = True
        node_tree = world.node_tree

        for node in node_tree.nodes:
            node_tree.nodes.remove(node)

        tex_coord = node_tree.nodes.new(type='ShaderNodeTexCoord')
        tex_coord.location = (-800, 0)

        mapping = node_tree.nodes.new(type='ShaderNodeMapping')
        mapping.location = (-600, 0)

        env_tex = node_tree.nodes.new(type='ShaderNodeTexEnvironment')
        env_tex.location = (-400, 0)
        env_tex.image = bpy.data.images.load(tmp_path)

        # Set appropriate color space
        for color_space in ['Linear', 'Linear Rec.709', 'Non-Color']:
            try:
                env_tex.image.colorspace_settings.name = color_space
                break
            except:
                continue

        background = node_tree.nodes.new(type='ShaderNodeBackground')
        background.location = (-200, 0)

        output = node_tree.nodes.new(type='ShaderNodeOutputWorld')
        output.location = (0, 0)

        node_tree.links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
        node_tree.links.new(mapping.outputs['Vector'], env_tex.inputs['Vector'])
        node_tree.links.new(env_tex.outputs['Color'], background.inputs['Color'])
        node_tree.links.new(background.outputs['Background'], output.inputs['Surface'])

        bpy.context.scene.world = world

        return {
            "success": True,
            "message": f"HDRI '{asset_id}' imported successfully",
            "image_name": env_tex.image.name,
            "resolution": resolution,
            "imported_at": datetime.now().isoformat()
        }
    finally:
        with suppress(Exception):
            os.unlink(tmp_path)


def _import_texture(asset_id: str, files_data: dict, resolution: str, file_format: str) -> Dict[str, Any]:
    """Import textures as a PBR material."""
    downloaded_maps = {}

    for map_type in files_data:
        if map_type in ["blend", "gltf"]:
            continue
        if resolution in files_data[map_type] and file_format in files_data[map_type][resolution]:
            file_info = files_data[map_type][resolution][file_format]
            file_url = file_info["url"]

            with tempfile.NamedTemporaryFile(suffix=f".{file_format}", delete=False) as tmp_file:
                response = requests.get(file_url, headers=REQ_HEADERS)
                if response.status_code == 200:
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name

                    image = bpy.data.images.load(tmp_path)
                    image.name = f"{asset_id}_{map_type}.{file_format}"
                    image.pack()

                    if map_type in ['color', 'diffuse', 'albedo']:
                        try:
                            image.colorspace_settings.name = 'sRGB'
                        except:
                            pass
                    else:
                        try:
                            image.colorspace_settings.name = 'Non-Color'
                        except:
                            pass

                    downloaded_maps[map_type] = image
                    with suppress(Exception):
                        os.unlink(tmp_path)

    if not downloaded_maps:
        raise RuntimeError("No texture maps found for the requested resolution and format")

    # Create PBR material
    mat = bpy.data.materials.new(name=asset_id)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (300, 0)

    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    principled.location = (0, 0)
    links.new(principled.outputs[0], output.inputs[0])

    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (-800, 0)

    mapping = nodes.new(type='ShaderNodeMapping')
    mapping.location = (-600, 0)
    mapping.vector_type = 'TEXTURE'
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    y_pos = 300
    for map_type, image in downloaded_maps.items():
        tex_node = nodes.new(type='ShaderNodeTexImage')
        tex_node.location = (-400, y_pos)
        tex_node.image = image
        links.new(mapping.outputs['Vector'], tex_node.inputs['Vector'])

        if map_type.lower() in ['color', 'diffuse', 'albedo']:
            links.new(tex_node.outputs['Color'], principled.inputs['Base Color'])
        elif map_type.lower() in ['roughness', 'rough']:
            links.new(tex_node.outputs['Color'], principled.inputs['Roughness'])
        elif map_type.lower() in ['metallic', 'metalness', 'metal']:
            links.new(tex_node.outputs['Color'], principled.inputs['Metallic'])
        elif map_type.lower() in ['normal', 'nor']:
            normal_map = nodes.new(type='ShaderNodeNormalMap')
            normal_map.location = (-200, y_pos)
            links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
            links.new(normal_map.outputs['Normal'], principled.inputs['Normal'])
        elif map_type.lower() in ['displacement', 'disp', 'height']:
            disp_node = nodes.new(type='ShaderNodeDisplacement')
            disp_node.location = (-200, y_pos - 200)
            disp_node.inputs['Scale'].default_value = 0.1
            links.new(tex_node.outputs['Color'], disp_node.inputs['Height'])
            links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])
        y_pos -= 250

    return {
        "success": True,
        "message": f"Texture '{asset_id}' imported as material",
        "material": mat.name,
        "maps": list(downloaded_maps.keys()),
        "imported_at": datetime.now().isoformat()
    }


def _import_model(asset_id: str, files_data: dict, resolution: str, file_format: str) -> Dict[str, Any]:
    """Import a 3D model from Poly Haven."""
    if file_format not in files_data or resolution not in files_data[file_format]:
        raise ValueError(f"Format '{file_format}' at resolution '{resolution}' not available for this model")

    file_info = files_data[file_format][resolution][file_format]
    file_url = file_info["url"]

    temp_dir = tempfile.mkdtemp()
    try:
        main_file_name = file_url.split("/")[-1]
        main_file_path = os.path.join(temp_dir, main_file_name)

        response = requests.get(file_url, headers=REQ_HEADERS)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download model: {response.status_code}")

        with open(main_file_path, "wb") as f:
            f.write(response.content)

        # Download included files (linked textures, etc.)
        if "include" in file_info and file_info["include"]:
            for include_path, include_info in file_info["include"].items():
                include_url = include_info["url"]
                include_file_path = os.path.join(temp_dir, include_path)
                os.makedirs(os.path.dirname(include_file_path), exist_ok=True)

                include_response = requests.get(include_url, headers=REQ_HEADERS)
                if include_response.status_code == 200:
                    with open(include_file_path, "wb") as f:
                        f.write(include_response.content)

        # Import into Blender
        if file_format in ("gltf", "glb"):
            bpy.ops.import_scene.gltf(filepath=main_file_path)
        elif file_format == "fbx":
            bpy.ops.import_scene.fbx(filepath=main_file_path)
        elif file_format == "obj":
            bpy.ops.import_scene.obj(filepath=main_file_path)
        else:
            raise ValueError(f"Unsupported model format: {file_format}")

        imported_objects = [obj.name for obj in bpy.context.selected_objects]

        return {
            "success": True,
            "message": f"Model '{asset_id}' imported successfully",
            "imported_objects": imported_objects,
            "imported_at": datetime.now().isoformat()
        }
    finally:
        with suppress(Exception):
            shutil.rmtree(temp_dir)


def set_polyhaven_texture(
    object_name: str,
    texture_id: str
) -> Dict[str, Any]:
    """
    Apply a previously downloaded Poly Haven texture to an object.

    Args:
        object_name: Name of the Blender object to apply the texture to.
        texture_id: The Poly Haven texture asset ID (must have been downloaded first).

    Returns:
        Result with material assignment details.
    """
    obj = bpy.data.objects.get(object_name)
    if not obj:
        raise ValueError(f"Object not found: {object_name}")
    if not hasattr(obj, 'data') or not hasattr(obj.data, 'materials'):
        raise ValueError(f"Object '{object_name}' cannot accept materials")

    # Find downloaded texture images
    texture_images = {}
    for img in bpy.data.images:
        if img.name.startswith(texture_id + "_"):
            map_type = img.name.split('_')[-1].split('.')[0]
            img.reload()
            if not img.packed_file:
                img.pack()
            texture_images[map_type] = img

    if not texture_images:
        raise ValueError(f"No texture images found for '{texture_id}'. Download the texture first.")

    # Create and assign material
    mat_name = f"{texture_id}_material_{object_name}"
    existing_mat = bpy.data.materials.get(mat_name)
    if existing_mat:
        bpy.data.materials.remove(existing_mat)

    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (600, 0)

    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    principled.location = (300, 0)
    links.new(principled.outputs[0], output.inputs[0])

    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (-800, 0)

    mapping_node = nodes.new(type='ShaderNodeMapping')
    mapping_node.location = (-600, 0)
    mapping_node.vector_type = 'TEXTURE'
    links.new(tex_coord.outputs['UV'], mapping_node.inputs['Vector'])

    y_pos = 300
    for map_type, image in texture_images.items():
        tex_node = nodes.new(type='ShaderNodeTexImage')
        tex_node.location = (-400, y_pos)
        tex_node.image = image
        links.new(mapping_node.outputs['Vector'], tex_node.inputs['Vector'])

        ml = map_type.lower()
        if ml in ['color', 'diffuse', 'albedo']:
            links.new(tex_node.outputs['Color'], principled.inputs['Base Color'])
        elif ml in ['roughness', 'rough']:
            links.new(tex_node.outputs['Color'], principled.inputs['Roughness'])
        elif ml in ['metallic', 'metalness', 'metal']:
            links.new(tex_node.outputs['Color'], principled.inputs['Metallic'])
        elif ml in ['normal', 'nor', 'gl', 'dx']:
            normal_map = nodes.new(type='ShaderNodeNormalMap')
            normal_map.location = (-200, y_pos)
            links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
            links.new(normal_map.outputs['Normal'], principled.inputs['Normal'])
        elif ml in ['displacement', 'disp', 'height']:
            disp_node = nodes.new(type='ShaderNodeDisplacement')
            disp_node.location = (-200, y_pos - 200)
            disp_node.inputs['Scale'].default_value = 0.1
            links.new(tex_node.outputs['Color'], disp_node.inputs['Height'])
            links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])
        y_pos -= 250

    # Clear existing materials and assign new
    while len(obj.data.materials) > 0:
        obj.data.materials.pop(index=0)
    obj.data.materials.append(mat)

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.context.view_layer.update()

    return {
        "success": True,
        "message": f"Applied texture '{texture_id}' to '{object_name}'",
        "material": mat.name,
        "maps": list(texture_images.keys()),
        "applied_at": datetime.now().isoformat()
    }
