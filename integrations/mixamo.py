"""
Mixamo Animation Helper for Blender MCP Server
Download animation FBX files from URLs and manage animation assets.

Mixamo (mixamo.com) doesn't have a public API, so this module provides:
1. A download helper that fetches FBX files from any URL
2. A curated list of common animation names for guidance
3. Local FBX import capabilities
"""

import bpy
import os
import tempfile
import logging
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger("BlenderMCP.Mixamo")


def download_animation_fbx(
    url: Optional[str] = None,
    local_path: Optional[str] = None,
    animation_name: Optional[str] = None,
    save_directory: Optional[str] = None
) -> Dict[str, Any]:
    """
    Download an animation FBX file from a URL or verify a local FBX file exists.

    Use this to prepare animation files for the CSM animate_csm_object tool.
    For Mixamo animations, visit mixamo.com to download FBX files with 'Without Skin' option,
    then provide the local path here.

    Args:
        url: URL to download the FBX file from (any hosting service).
        local_path: Path to an existing local FBX file to verify and use.
        animation_name: Optional descriptive name for the animation (e.g., 'walking', 'idle').
        save_directory: Directory to save downloaded file. Defaults to system temp directory.

    Returns:
        Dict with the local file path ready for use with animate_csm_object.
    """
    if not url and not local_path:
        raise ValueError(
            "Provide either a URL to download from or a local_path to an existing FBX file.\n\n"
            "To get animation FBX files from Mixamo:\n"
            "1. Visit https://www.mixamo.com\n"
            "2. Search for an animation (e.g., 'Walking', 'Running', 'Dancing')\n"
            "3. Click Download → Format: FBX Binary (.fbx) → Skin: Without Skin\n"
            "4. Save the file and provide its path here"
        )

    if local_path:
        # Verify local file
        if not os.path.exists(local_path):
            raise ValueError(f"FBX file not found: {local_path}")
        if not local_path.lower().endswith('.fbx'):
            raise ValueError(f"File is not an FBX: {local_path}")

        file_size = os.path.getsize(local_path)
        return {
            "success": True,
            "fbx_path": local_path,
            "animation_name": animation_name or os.path.splitext(os.path.basename(local_path))[0],
            "file_size_bytes": file_size,
            "source": "local",
            "message": f"FBX file verified: {local_path} ({file_size / 1024:.1f} KB)",
            "next_step": f"Use animate_csm_object(object_name, '{local_path}') to apply this animation."
        }

    # Download from URL
    if save_directory:
        os.makedirs(save_directory, exist_ok=True)
    else:
        save_directory = tempfile.gettempdir()

    filename = animation_name or "animation"
    if not filename.endswith('.fbx'):
        filename += '.fbx'

    file_path = os.path.join(save_directory, filename)

    try:
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = os.path.getsize(file_path)

        return {
            "success": True,
            "fbx_path": file_path,
            "animation_name": animation_name or "downloaded_animation",
            "file_size_bytes": file_size,
            "source": "downloaded",
            "source_url": url,
            "message": f"Animation FBX downloaded: {file_path} ({file_size / 1024:.1f} KB)",
            "next_step": f"Use animate_csm_object(object_name, '{file_path}') to apply this animation.",
            "downloaded_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise RuntimeError(f"Failed to download FBX: {e}")


def list_common_animations() -> Dict[str, Any]:
    """
    List commonly used animation types with descriptions and Mixamo search terms.

    Use this as a reference when searching for animations on Mixamo or other sources.
    After finding the right animation, download the FBX and use animate_csm_object to apply it.

    Returns:
        Categorized list of common animations with descriptions and Mixamo search terms.
    """
    return {
        "instructions": (
            "To use these animations:\n"
            "1. Visit https://www.mixamo.com and sign in with your Adobe ID\n"
            "2. Search for the animation using the 'mixamo_search' term below\n"
            "3. Preview and customize the animation\n"
            "4. Download as FBX Binary (.fbx) with 'Without Skin' option\n"
            "5. Use download_animation_fbx(local_path='path/to/file.fbx') to verify\n"
            "6. Use animate_csm_object(object_name, 'path/to/file.fbx') to apply"
        ),
        "categories": {
            "locomotion": [
                {"name": "Walking", "mixamo_search": "walking", "description": "Standard walk cycle"},
                {"name": "Running", "mixamo_search": "running", "description": "Standard run cycle"},
                {"name": "Jogging", "mixamo_search": "jogging", "description": "Casual jogging pace"},
                {"name": "Sprinting", "mixamo_search": "sprint", "description": "Fast sprint animation"},
                {"name": "Sneaking", "mixamo_search": "sneak walk", "description": "Stealth crouched walk"},
                {"name": "Backwards Walk", "mixamo_search": "walking backwards", "description": "Walking in reverse"},
            ],
            "idle": [
                {"name": "Idle", "mixamo_search": "idle", "description": "Standing idle, subtle motion"},
                {"name": "Breathing Idle", "mixamo_search": "breathing idle", "description": "Relaxed standing"},
                {"name": "Looking Around", "mixamo_search": "looking around", "description": "Idle with head turns"},
                {"name": "Happy Idle", "mixamo_search": "happy idle", "description": "Upbeat idle stance"},
            ],
            "dance": [
                {"name": "Hip Hop Dance", "mixamo_search": "hip hop dancing", "description": "Urban dance moves"},
                {"name": "Salsa", "mixamo_search": "salsa dancing", "description": "Latin dance style"},
                {"name": "Robot Dance", "mixamo_search": "robot dance", "description": "Mechanical dance moves"},
                {"name": "Macarena", "mixamo_search": "macarena", "description": "Classic Macarena dance"},
                {"name": "Breakdance", "mixamo_search": "breakdance", "description": "Breakdancing moves"},
            ],
            "combat": [
                {"name": "Punch", "mixamo_search": "punching", "description": "Basic punch attack"},
                {"name": "Kick", "mixamo_search": "kicking", "description": "Basic kick attack"},
                {"name": "Sword Slash", "mixamo_search": "sword slash", "description": "One-handed sword attack"},
                {"name": "Boxing", "mixamo_search": "boxing", "description": "Boxing stance and jabs"},
                {"name": "Dodge", "mixamo_search": "dodge", "description": "Quick dodge/evade"},
            ],
            "actions": [
                {"name": "Jump", "mixamo_search": "jump", "description": "Standing jump"},
                {"name": "Wave", "mixamo_search": "waving", "description": "Friendly hand wave"},
                {"name": "Clapping", "mixamo_search": "clapping", "description": "Applause clapping"},
                {"name": "Sitting Down", "mixamo_search": "sitting down", "description": "Sit on chair"},
                {"name": "Push-ups", "mixamo_search": "push up", "description": "Exercise push-ups"},
                {"name": "Picking Up", "mixamo_search": "picking up", "description": "Bend and pick up object"},
            ],
            "emotes": [
                {"name": "Thumbs Up", "mixamo_search": "thumbs up", "description": "Approval gesture"},
                {"name": "Salute", "mixamo_search": "salute", "description": "Military salute"},
                {"name": "Bow", "mixamo_search": "bow", "description": "Respectful bow"},
                {"name": "Dying", "mixamo_search": "dying", "description": "Death/falling animation"},
                {"name": "Laughing", "mixamo_search": "laughing", "description": "Hearty laugh"},
            ],
        },
        "total_listed": 27,
        "note": "These are common Mixamo animations. Many more are available on mixamo.com."
    }
