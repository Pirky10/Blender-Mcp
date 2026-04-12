"""
Tencent Hunyuan3D Integration for Blender MCP Server
AI-powered 3D model generation from text or images via Tencent Cloud.

Supports: OFFICIAL_API (Tencent Cloud) and LOCAL_API modes.
Requires: Tencent Cloud SecretId + SecretKey (for OFFICIAL_API)
"""

import bpy
import os
import re
import json
import time
import hmac
import hashlib
import base64
import tempfile
import zipfile
import shutil
import logging
import requests
import mathutils
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import suppress

logger = logging.getLogger("BlenderMCP.Hunyuan3D")


def _get_mode() -> str:
    return bpy.context.scene.mcp_hunyuan3d_mode


def _get_aabb(obj):
    if obj.type != 'MESH':
        return None
    corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    min_c = [min(v[i] for v in corners) for i in range(3)]
    max_c = [max(v[i] for v in corners) for i in range(3)]
    return [min_c, max_c]


def _tencent_sign_headers(
    method: str, path: str, head_params: dict,
    data: dict, service: str, region: str,
    secret_id: str, secret_key: str, host: str = None
) -> tuple:
    """Generate Tencent Cloud API v3 signature headers."""
    timestamp = int(time.time())
    date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

    if not host:
        host = f"{service}.tencentcloudapi.com"

    payload_str = json.dumps(data)

    ct = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{ct}\nhost:{host}\nx-tc-action:{head_params.get('Action', '').lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    canonical_request = (
        f"{method}\n{path}\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    )

    credential_scope = f"{date}/{service}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashed_canonical}"

    def _sign(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = _sign(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _sign(secret_date, service)
    secret_signing = _sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "Host": host,
        "X-TC-Action": head_params.get("Action", ""),
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": head_params.get("Version", ""),
        "X-TC-Region": region
    }

    return headers, f"https://{host}"


def get_hunyuan3d_status() -> Dict[str, Any]:
    """
    Check if Hunyuan3D integration is enabled and properly configured.

    Returns:
        Status dict with enabled flag, mode, and instructions if misconfigured.
    """
    enabled = bpy.context.scene.mcp_use_hunyuan3d
    if not enabled:
        return {
            "enabled": False,
            "message": (
                "Hunyuan3D is disabled. To enable:\n"
                "1. Open the MCP Server N-Panel\n"
                "2. Check 'Use Hunyuan3D'\n"
                "3. Select mode and enter credentials\n"
                "4. Restart the MCP server"
            )
        }

    mode = _get_mode()
    if mode == "OFFICIAL_API":
        sid = bpy.context.scene.mcp_hunyuan3d_secret_id
        skey = bpy.context.scene.mcp_hunyuan3d_secret_key
        if not sid or not skey:
            return {
                "enabled": False,
                "mode": mode,
                "message": "Hunyuan3D is enabled but SecretId or SecretKey is missing."
            }
    elif mode == "LOCAL_API":
        url = bpy.context.scene.mcp_hunyuan3d_api_url
        if not url:
            return {
                "enabled": False,
                "mode": mode,
                "message": "Hunyuan3D is enabled but the local API URL is missing."
            }

    return {
        "enabled": True,
        "mode": mode,
        "message": f"Hunyuan3D is enabled and ready. Mode: {mode}"
    }


def generate_hunyuan3d_model(
    text_prompt: Optional[str] = None,
    image_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a 3D model using Tencent Hunyuan3D.

    Provide either a text prompt OR an image (local path or URL), not both.

    Args:
        text_prompt: Short description of the desired model (max 200 chars).
        image_url: URL or local path to a reference image.

    Returns:
        Job info with job_id for polling.
    """
    mode = _get_mode()

    if mode == "OFFICIAL_API":
        return _generate_official(text_prompt, image_url)
    elif mode == "LOCAL_API":
        return _generate_local(text_prompt, image_url)
    raise ValueError(f"Unknown Hunyuan3D mode: {mode}")


def _generate_official(text_prompt: str = None, image: str = None) -> Dict[str, Any]:
    """Generate via Tencent Cloud official API."""
    secret_id = bpy.context.scene.mcp_hunyuan3d_secret_id
    secret_key = bpy.context.scene.mcp_hunyuan3d_secret_key
    if not secret_id or not secret_key:
        raise ValueError("Tencent SecretId or SecretKey is not configured")

    if not text_prompt and not image:
        raise ValueError("Either text_prompt or image_url is required")
    if text_prompt and image:
        raise ValueError("Provide only text_prompt or image_url, not both")

    data = {"Num": 1}

    if text_prompt:
        if len(text_prompt) > 200:
            raise ValueError("Prompt exceeds 200 character limit")
        data["Prompt"] = text_prompt

    if image:
        if re.match(r'^https?://', image, re.IGNORECASE):
            data["ImageUrl"] = image
        else:
            if not os.path.exists(image):
                raise ValueError(f"Image file not found: {image}")
            with open(image, "rb") as f:
                data["ImageBase64"] = base64.b64encode(f.read()).decode("ascii")

    head_params = {
        "Action": "SubmitHunyuanTo3DJob",
        "Version": "2023-09-01",
        "Region": "ap-guangzhou",
    }

    headers, endpoint = _tencent_sign_headers(
        "POST", "/", head_params, data,
        "hunyuan", "ap-guangzhou",
        secret_id, secret_key
    )

    response = requests.post(endpoint, headers=headers, json=data, timeout=60)
    result = response.json()

    if "Response" in result and "JobId" in result["Response"]:
        return {
            "job_id": f"job_{result['Response']['JobId']}",
            "mode": "OFFICIAL_API",
            "submitted_at": datetime.now().isoformat()
        }
    return result


def _generate_local(text_prompt: str = None, image: str = None) -> Dict[str, Any]:
    """Generate via local Hunyuan3D API."""
    api_url = bpy.context.scene.mcp_hunyuan3d_api_url
    if not api_url:
        raise ValueError("Local Hunyuan3D API URL is not configured")

    data = {}
    if text_prompt:
        data["prompt"] = text_prompt
    if image:
        if re.match(r'^https?://', image, re.IGNORECASE):
            data["image_url"] = image
        else:
            if not os.path.exists(image):
                raise ValueError(f"Image not found: {image}")
            with open(image, "rb") as f:
                data["image_base64"] = base64.b64encode(f.read()).decode("ascii")

    response = requests.post(f"{api_url}/generate", json=data, timeout=300)
    return response.json()


def poll_hunyuan_job_status(
    job_id: str
) -> Dict[str, Any]:
    """
    Check if a Hunyuan3D generation job has completed.

    Status is "DONE" when complete, "RUN" when in progress.
    When done, the response includes ResultFile3Ds with the model download URL.

    Args:
        job_id: The job ID from the generation step (format: job_xxx).

    Returns:
        Job status and result URLs when complete.
    """
    mode = _get_mode()

    # Strip the "job_" prefix if present
    raw_id = job_id.replace("job_", "") if job_id.startswith("job_") else job_id

    if mode == "OFFICIAL_API":
        secret_id = bpy.context.scene.mcp_hunyuan3d_secret_id
        secret_key = bpy.context.scene.mcp_hunyuan3d_secret_key

        data = {"JobId": raw_id}
        head_params = {
            "Action": "QueryHunyuanTo3DJob",
            "Version": "2023-09-01",
            "Region": "ap-guangzhou",
        }

        headers, endpoint = _tencent_sign_headers(
            "POST", "/", head_params, data,
            "hunyuan", "ap-guangzhou",
            secret_id, secret_key
        )

        response = requests.post(endpoint, headers=headers, json=data, timeout=30)
        return response.json()

    elif mode == "LOCAL_API":
        api_url = bpy.context.scene.mcp_hunyuan3d_api_url
        response = requests.get(f"{api_url}/status/{raw_id}", timeout=30)
        return response.json()

    raise ValueError(f"Unknown Hunyuan3D mode: {mode}")


def import_hunyuan3d_asset(
    name: str,
    zip_file_url: str
) -> Dict[str, Any]:
    """
    Import a Hunyuan3D generated model into Blender.

    The model is provided as a ZIP file containing OBJ format files.

    Args:
        name: Name to assign to the imported object.
        zip_file_url: URL of the ZIP file containing the generated model.

    Returns:
        Import result with object info and bounding box.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # Download ZIP
        zip_path = os.path.join(temp_dir, "model.zip")
        response = requests.get(zip_file_url, stream=True, timeout=120)
        response.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Extract
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Security check
            abs_temp = os.path.abspath(temp_dir)
            for info in zf.infolist():
                target = os.path.abspath(os.path.join(temp_dir, os.path.normpath(info.filename)))
                if not target.startswith(abs_temp) or ".." in info.filename:
                    raise RuntimeError("Security: zip file contains path traversal")
            zf.extractall(temp_dir)

        # Find importable file
        existing = set(bpy.data.objects)

        obj_files = []
        glb_files = []
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                full = os.path.join(root, f)
                if f.endswith('.obj'):
                    obj_files.append(full)
                elif f.endswith(('.glb', '.gltf')):
                    glb_files.append(full)

        if glb_files:
            bpy.ops.import_scene.gltf(filepath=glb_files[0])
        elif obj_files:
            bpy.ops.import_scene.obj(filepath=obj_files[0])
        else:
            raise RuntimeError("No importable files found in the archive")

        bpy.context.view_layer.update()
        imported = list(set(bpy.data.objects) - existing)

        if not imported:
            raise RuntimeError("No objects were imported")

        # Name the first mesh
        main_obj = None
        for obj in imported:
            if obj.type == 'MESH':
                main_obj = obj
                break
        if main_obj is None:
            main_obj = imported[0]

        main_obj.name = name
        if main_obj.data:
            main_obj.data.name = name

        result = {
            "succeed": True,
            "name": main_obj.name,
            "type": main_obj.type,
            "location": list(main_obj.location),
            "rotation": [main_obj.rotation_euler.x, main_obj.rotation_euler.y, main_obj.rotation_euler.z],
            "scale": list(main_obj.scale),
            "imported_objects": [o.name for o in imported],
            "imported_at": datetime.now().isoformat()
        }
        bbox = _get_aabb(main_obj)
        if bbox:
            result["world_bounding_box"] = bbox
        return result

    except Exception as e:
        return {"succeed": False, "error": str(e)}
    finally:
        with suppress(Exception):
            shutil.rmtree(temp_dir)
