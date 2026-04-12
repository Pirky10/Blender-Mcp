"""
Blender MCP Server - External Integrations Package
Provides Poly Haven, Sketchfab, Hyper3D Rodin, CSM.ai, Hunyuan3D, and Mixamo tools.

All functions in this package are plain (not thread-safe decorated).
The main blender_mcp.py wraps them with @thread_safe at registration time.
"""

from integrations.polyhaven import (
    get_polyhaven_status,
    get_polyhaven_categories,
    search_polyhaven_assets,
    download_polyhaven_asset,
    set_polyhaven_texture,
)

from integrations.sketchfab import (
    get_sketchfab_status,
    search_sketchfab_models,
    get_sketchfab_model_preview,
    download_sketchfab_model,
)

from integrations.hyper3d import (
    get_hyper3d_status,
    generate_hyper3d_model_text,
    generate_hyper3d_model_images,
    poll_rodin_job_status,
    import_rodin_generated_asset,
)

from integrations.csm import (
    get_csm_status,
    search_csm_models,
    import_csm_model,
    get_csm_session_details,
    animate_csm_object,
)

from integrations.hunyuan3d import (
    get_hunyuan3d_status,
    generate_hunyuan3d_model,
    poll_hunyuan_job_status,
    import_hunyuan3d_asset,
)

from integrations.mixamo import (
    download_animation_fbx,
    list_common_animations,
)

from integrations.strategy import (
    get_asset_creation_strategy,
)

# All integration tools for registration
ALL_INTEGRATION_TOOLS = [
    # Poly Haven
    get_polyhaven_status,
    get_polyhaven_categories,
    search_polyhaven_assets,
    download_polyhaven_asset,
    set_polyhaven_texture,
    # Sketchfab
    get_sketchfab_status,
    search_sketchfab_models,
    get_sketchfab_model_preview,
    download_sketchfab_model,
    # Hyper3D Rodin
    get_hyper3d_status,
    generate_hyper3d_model_text,
    generate_hyper3d_model_images,
    poll_rodin_job_status,
    import_rodin_generated_asset,
    # CSM.ai
    get_csm_status,
    search_csm_models,
    import_csm_model,
    get_csm_session_details,
    animate_csm_object,
    # Hunyuan3D
    get_hunyuan3d_status,
    generate_hunyuan3d_model,
    poll_hunyuan_job_status,
    import_hunyuan3d_asset,
    # Mixamo / Animation
    download_animation_fbx,
    list_common_animations,
    # Strategy / Meta
    get_asset_creation_strategy,
]
