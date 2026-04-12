# Blender MCP Server — Complete Setup & Usage Guide

> **Version:** 3.0.0 | **Architecture:** Single-file Blender addon + modular integrations
> **Total Tools:** ~76 (50 core + 26 external integrations)

---

## Table of Contents

1. [What Is This?](#1-what-is-this)
2. [Requirements](#2-requirements)
3. [Installation — Step by Step](#3-installation--step-by-step)
4. [Starting the MCP Server](#4-starting-the-mcp-server)
5. [Connecting to an AI Client](#5-connecting-to-an-ai-client)
6. [External Integrations & API Keys](#6-external-integrations--api-keys)
7. [Where to Enter API Keys in Blender](#7-where-to-enter-api-keys-in-blender)
8. [Integration Guides](#8-integration-guides)
9. [Tool Reference](#9-tool-reference)
10. [Troubleshooting](#10-troubleshooting)
11. [Project Structure](#11-project-structure)

---

## 1. What Is This?

This is a **Blender addon** that turns Blender into an **MCP (Model Context Protocol) server**. Once running, any AI assistant (Claude, GPT, Gemini, etc.) can control Blender — creating objects, materials, animations, importing models, and more — all through natural language.

The addon runs a **FastAPI HTTP server** directly inside Blender. The AI communicates via standard HTTP requests to `http://localhost:8000`.

### What are the Integrations?

On top of the 50 core Blender tools, this addon adds 26 extra tools that connect to **external 3D asset services**:

| Integration | What It Does | API Key? |
|---|---|---|
| **Poly Haven** | Free HDRIs, PBR textures, 3D models | ❌ No key needed |
| **Sketchfab** | Search & download 3D models | ✅ Free API key |
| **Hyper3D Rodin** | AI text/image → 3D model generation | ✅ API key |
| **CSM.ai** | 3D model search + character animation | ✅ API key |
| **Hunyuan3D** | Tencent AI 3D model generation | ✅ SecretId + SecretKey |
| **Mixamo** | Animation FBX management & catalog | ❌ No key needed |

---

## 2. Requirements

- **Blender 3.6+** (4.x recommended)
- **Python 3.10+** (bundled with Blender)
- **Internet connection** (for external integrations)
- An **MCP-compatible AI client** (see [Section 5](#5-connecting-to-an-ai-client))

### Auto-installed Dependencies

The addon automatically installs these Python packages into Blender's Python environment on first run:

- `fastapi` — HTTP server framework
- `uvicorn` — ASGI server
- `pydantic` — Data validation
- `docstring-parser` — Tool documentation parser
- `numpy` — Numerical operations
- `requests` — HTTP client for external APIs

You do NOT need to install these manually.

---

## 3. Installation — Step by Step

### Step 1: Download the Project

```bash
git clone https://github.com/Pirky10/Blender-Mcp.git
```

Or download the ZIP and extract it to a known location.

### Step 2: Open Blender

Launch Blender 3.6 or higher.

### Step 3: Install the Addon

1. Go to **Edit → Preferences → Add-ons**
2. Click **"Install..."** (top-right button)
3. Navigate to the project folder and select **`blender_mcp.py`**
4. Click **"Install Add-on"**

> ⚠️ **IMPORTANT:** The `blender_mcp.py` file must stay in the same folder as the `integrations/` directory. Blender will copy the addon to its addons folder, so you need to also copy the `integrations/` folder there.

### Step 3b: Copy Integration Modules (Critical!)

After installing, you need to copy the `integrations/` folder to sit next to the installed addon:

**Find where Blender installed the addon:**
- **macOS:** `~/Library/Application Support/Blender/4.x/scripts/addons/`
- **Windows:** `%APPDATA%\Blender Foundation\Blender\4.x\scripts\addons\`
- **Linux:** `~/.config/blender/4.x/scripts/addons/`

**Copy the entire `integrations/` folder** from the project to that location:

```bash
# macOS example (adjust the Blender version number):
cp -r integrations/ ~/Library/Application\ Support/Blender/4.2/scripts/addons/integrations/
```

Your Blender addons folder should look like:
```
scripts/addons/
├── blender_mcp.py
└── integrations/
    ├── __init__.py
    ├── polyhaven.py
    ├── sketchfab.py
    ├── hyper3d.py
    ├── csm.py
    ├── hunyuan3d.py
    ├── mixamo.py
    └── strategy.py
```

### Alternative: Symlink from Project Folder (Recommended for Developers)

Instead of copying files every time you make changes, you can **symlink** the addon files into Blender's addons folder. This way your project folder stays the single source of truth:

```bash
# macOS — adjust the Blender version number (e.g. 4.2, 4.3):
ln -s /full/path/to/Blender-MCP-Server/blender_mcp.py \
  ~/Library/Application\ Support/Blender/4.2/scripts/addons/blender_mcp.py

ln -s /full/path/to/Blender-MCP-Server/integrations \
  ~/Library/Application\ Support/Blender/4.2/scripts/addons/integrations
```

```bash
# Windows (run Command Prompt as Administrator):
mklink "C:\Users\YOU\AppData\Roaming\Blender Foundation\Blender\4.2\scripts\addons\blender_mcp.py" "C:\path\to\Blender-MCP-Server\blender_mcp.py"
mklink /D "C:\Users\YOU\AppData\Roaming\Blender Foundation\Blender\4.2\scripts\addons\integrations" "C:\path\to\Blender-MCP-Server\integrations"
```

```bash
# Linux:
ln -s /full/path/to/Blender-MCP-Server/blender_mcp.py \
  ~/.config/blender/4.2/scripts/addons/blender_mcp.py

ln -s /full/path/to/Blender-MCP-Server/integrations \
  ~/.config/blender/4.2/scripts/addons/integrations
```

After creating the symlinks, restart Blender and enable the addon in **Edit → Preferences → Add-ons** → search "MCP".

### Step 4: Enable the Addon

1. In **Edit → Preferences → Add-ons**
2. Search for **"MCP"**
3. Check the checkbox next to **"Blender MCP Server"** to enable it
4. You should see a new **"MCP Server"** tab in the N-Panel (press `N` in the 3D Viewport)

---

## 4. Starting the MCP Server

1. Open the **3D Viewport** in Blender
2. Press **`N`** to open the side panel (N-Panel)
3. Click the **"MCP Server"** tab
4. Click **"Start Server"**

You should see:
```
MCP Server started on http://localhost:8000
```

### Verify It's Running

- Open your browser and go to: **http://localhost:8000/docs** — you'll see the full API documentation
- Or go to: **http://localhost:8000/mcp/list_tools** — you'll see all available tools as JSON

### Stopping the Server

Click **"Stop Server"** in the N-Panel to shut it down.

---

## 5. Connecting to an AI Client

### Claude Desktop (Anthropic)

Add to your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "blender": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Then restart Claude Desktop.

### Cursor / Windsurf / Other MCP Clients

Most MCP clients support HTTP transport. Point them to:
```
http://localhost:8000/mcp
```

### Direct API Access

You can also call tools directly via HTTP:

```bash
# List all tools
curl http://localhost:8000/mcp/list_tools

# Call a tool
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{"name": "get_scene_info", "arguments": {}}'
```

---

## 6. External Integrations & API Keys

### Getting Your API Keys

#### 🟢 Poly Haven — No Key Needed
Just toggle it ON in the N-Panel. Completely free, no signup required.

#### 🟢 Mixamo — No Key Needed
Visit [mixamo.com](https://www.mixamo.com) to browse and download animation FBX files manually. The addon helps manage and apply these files. You do need an **Adobe ID** (free) to access Mixamo's website.

---

#### 🔵 Sketchfab — Free API Key

1. Go to [sketchfab.com](https://sketchfab.com) and **sign in** (or create a free account)
2. Click your **avatar** (top-right) → **Settings**
3. In the left sidebar, click **"Password & API"**
4. Your **API Token** is at the bottom — a 32-character string like: `YOUR_SKETCHFAB_API_KEY_HERE`
5. Copy this token

> **Note:** Sketchfab was acquired by Epic Games. The settings may redirect to `fab.com`, but the API token still works the same way.

---

#### 🟣 Hyper3D Rodin — API Key (Two Options)

**Option A: Main Site (hyperhuman.deemos.com)**
1. Go to [hyperhuman.deemos.com](https://hyperhuman.deemos.com)
2. Sign up / sign in
3. Navigate to your account settings or API section
4. Copy your API key (Bearer token)

**Option B: Fal.ai**
1. Go to [fal.ai](https://fal.ai)
2. Sign up / sign in
3. Go to **Dashboard → API Keys**
4. Create a new key and copy it

> **Free Trial:** The addon includes a built-in free trial key for testing. For production use, get your own key.

---

#### 🟠 CSM.ai — API Key

1. Go to [3d.csm.ai](https://3d.csm.ai)
2. Sign up / sign in
3. Go to **Dashboard → Profile → Developer Settings**
   Direct link: [3d.csm.ai/dashboard/profile/developer-settings](https://3d.csm.ai/dashboard/profile/developer-settings)
4. Generate / copy your API key

---

#### 🔴 Hunyuan3D — Tencent Cloud Credentials

**Option A: Official API (Tencent Cloud)**
1. Go to [cloud.tencent.com](https://cloud.tencent.com)
2. Sign up / sign in
3. Search for **"Hunyuan3D"** service and enable it
4. Go to **API Keys** section
5. You need TWO values:
   - **SecretId** — your Tencent Cloud SecretId
   - **SecretKey** — your Tencent Cloud SecretKey

**Option B: Local API**
If you're running Hunyuan3D locally (self-hosted), just enter the local URL (default: `http://localhost:7860`).

---

## 7. Where to Enter API Keys in Blender

This is how you enter your API keys **inside Blender**:

### Step-by-Step

1. Open the **3D Viewport**
2. Press **`N`** to open the N-Panel (side panel)
3. Click the **"MCP Server"** tab
4. Scroll down to the **"External Integrations"** section
5. You'll see checkboxes and input fields:

```
┌──────────────────────────────────────────┐
│  External Integrations                   │
│                                          │
│  ☑ Poly Haven (Free Assets)              │
│                                          │
│  ☑ Sketchfab                             │
│     API Key: [••••••••••••••••]           │
│     ℹ Get key: sketchfab.com/settings    │
│                                          │
│  ☐ Hyper3D Rodin                         │
│     Mode: [Main Site ▼]                  │
│     API Key: [________________]          │
│                                          │
│  ☑ CSM.ai (Search + Animation)           │
│     API Key: [••••••••••••••••]           │
│                                          │
│  ☐ Hunyuan3D                             │
│     Mode: [Official API ▼]              │
│     SecretId:  [________________]        │
│     SecretKey: [________________]        │
└──────────────────────────────────────────┘
```

6. **Check the box** next to each integration you want to enable
7. **Paste your API key** into the corresponding field
8. API key fields show as `••••••` (password-masked for security)
9. **Start the server** (or restart it if it was already running)

### Important Notes

- ⚠️ **You must restart the MCP server** after changing API keys for the changes to take effect
- 🔒 API keys are stored in the Blender scene data — they are saved with your `.blend` file
- 🗑️ If you share a `.blend` file, your API keys will be included! Clear them first or use a fresh file
- Each integration can be **toggled independently** — only enable what you need

---

## 8. Integration Guides

### 8.1 Poly Haven — Free HDRIs, Textures & Models

**No API key needed.** Just toggle ON and start using.

**Example conversation with AI:**
```
You: "Set up a forest environment with nice lighting"
AI:  → get_polyhaven_status()
     → search_polyhaven_assets(asset_type="hdris", categories="outdoor")
     → download_polyhaven_asset(asset_id="autumn_forest", asset_type="hdris", resolution="2k")
     → Result: HDRI applied as world environment
```

**What it can do:**
- Download and apply **HDRI environment maps** (sky/lighting)
- Download and apply **PBR textures** (with all maps: diffuse, roughness, normal, displacement)
- Download and import **3D models** (furniture, rocks, vegetation)

---

### 8.2 Sketchfab — Massive 3D Model Library

**Example conversation with AI:**
```
You: "Add a medieval castle to the scene"
AI:  → search_sketchfab_models(query="medieval castle", downloadable=True)
     → get_sketchfab_model_preview(uid="abc123")  # Preview thumbnail
     → download_sketchfab_model(uid="abc123", normalize_size=True)
     → Result: Castle imported and scaled to scene
```

**Tips:**
- Only **downloadable** models can be imported (not all Sketchfab models allow download)
- Use `normalize_size=True` to auto-scale models to a reasonable size
- Preview thumbnails first with `get_sketchfab_model_preview` to verify it's the right model

---

### 8.3 Hyper3D Rodin — AI 3D Generation

Generate 3D models from text descriptions or reference images.

**Example conversation with AI:**
```
You: "Generate a 3D coffee mug"
AI:  → generate_hyper3d_model_text(text_prompt="a ceramic coffee mug with handle")
     → poll_rodin_job_status(subscription_key="...")  # Wait for generation
     → import_rodin_generated_asset(name="CoffeeMug", task_uuid="...")
     → Result: AI-generated mug imported into scene
```

**Two Modes:**
- **Main Site:** Uses hyperhuman.deemos.com (default)
- **Fal.ai:** Uses fal.ai's hosted version (may be faster)

**Best Practices:**
- 🎯 Good for **single objects** — don't try to generate entire scenes
- ⏱️ Generation takes 30-120 seconds — you need to **poll** until done
- 📐 Always check bounding box after import and adjust size/position

---

### 8.4 CSM.ai — 3D Search + Character Animation

**3D Model Search:**
```
You: "Find me a blue sports car"
AI:  → search_csm_models(search_text="blue sports car")
     → import_csm_model(model_id="...", mesh_url_glb="...", name="SportsCar")
```

**Character Animation (Mixamo-style):**
```
You: "Make the character do a hip hop dance"
AI:  → list_common_animations()  # See available animation types
     → download_animation_fbx(local_path="/path/to/hip_hop_dance.fbx")
     → animate_csm_object(object_name="Character", animation_fbx_path="/path/to/hip_hop_dance.fbx")
     → Result: Character is now dancing!
```

**Animation Workflow:**
1. You need an animation FBX file from **Mixamo**:
   - Go to [mixamo.com](https://www.mixamo.com)
   - Sign in with your Adobe ID
   - Browse/search for an animation
   - Click **Download** → Format: **FBX Binary (.fbx)** → Skin: **Without Skin**
   - Save the file to your computer
2. Tell the AI the file path, and it handles the rest

---

### 8.5 Hunyuan3D — Tencent AI Generation

Similar workflow to Hyper3D Rodin, but powered by Tencent's AI:

```
You: "Create a 3D model of a wooden treasure chest"
AI:  → generate_hunyuan3d_model(text_prompt="wooden treasure chest with metal bands")
     → poll_hunyuan_job_status(job_id="...")
     → import_hunyuan3d_asset(name="TreasureChest", zip_file_url="...")
```

---

## 9. Tool Reference

### Core Blender Tools (~50)
| Category | Tools |
|---|---|
| Object Creation | `create_mesh_object`, `create_curve_object`, `create_text_object` |
| Object Manipulation | `transform_object`, `duplicate_object`, `delete_objects` |
| Modifiers | `add_modifier`, `apply_modifier` |
| Materials & Shading | `create_material`, `assign_material`, `create_procedural_material` |
| Lighting | `create_light` |
| Camera | `create_camera`, `set_optimal_camera_for_all` |
| Animation | `create_keyframe` |
| Rendering | `configure_render_settings`, `render_image`, `capture_viewport_image` |
| File Operations | `import_file`, `export_file`, `save_blend_file` |
| Scene Management | `get_scene_info`, `clear_scene`, `auto_arrange_objects` |
| Simulations | `setup_rigid_body`, `add_cloth_simulation`, `setup_fluid_simulation` |
| Advanced | `boolean_operation`, `create_particle_system`, `add_geometry_nodes` |

### Integration Tools (26)
| Integration | Tools |
|---|---|
| Poly Haven (5) | `get_polyhaven_status`, `get_polyhaven_categories`, `search_polyhaven_assets`, `download_polyhaven_asset`, `set_polyhaven_texture` |
| Sketchfab (4) | `get_sketchfab_status`, `search_sketchfab_models`, `get_sketchfab_model_preview`, `download_sketchfab_model` |
| Hyper3D Rodin (5) | `get_hyper3d_status`, `generate_hyper3d_model_text`, `generate_hyper3d_model_images`, `poll_rodin_job_status`, `import_rodin_generated_asset` |
| CSM.ai (5) | `get_csm_status`, `search_csm_models`, `import_csm_model`, `get_csm_session_details`, `animate_csm_object` |
| Hunyuan3D (4) | `get_hunyuan3d_status`, `generate_hunyuan3d_model`, `poll_hunyuan_job_status`, `import_hunyuan3d_asset` |
| Mixamo (2) | `download_animation_fbx`, `list_common_animations` |
| Strategy (1) | `get_asset_creation_strategy` |

---

## 10. Troubleshooting

### "Dependencies failed to install"
The addon tries to auto-install packages on first run. If it fails:
```bash
# Manually install using Blender's Python
/path/to/blender/python/bin/python3 -m pip install fastapi uvicorn pydantic docstring-parser numpy requests
```

### "Integration modules not available"
This means the `integrations/` folder isn't next to `blender_mcp.py`. Check:
- The `integrations/` folder exists in the same directory as the addon
- It contains `__init__.py` and all module files

### "Server won't start"
- Check Blender's **System Console** (Window → Toggle System Console on Windows, or launch Blender from terminal on macOS/Linux)
- Look for error messages in the console
- Make sure port 8000 isn't already in use by another application

### "API key not working"
- Make sure you **restarted the MCP server** after entering the key
- Verify the key is correct (no extra spaces)
- Check if the service requires account verification or billing setup

### "Imported model is too big/small"
- Use `normalize_size=True` when downloading Sketchfab models
- After any import, check `world_bounding_box` and use `transform_object` to adjust

### macOS: "Cannot find Blender Python"
If auto-install fails on macOS, find Blender's Python:
```bash
# Blender 4.x on macOS:
/Applications/Blender.app/Contents/Resources/4.x/python/bin/python3.11 -m pip install fastapi uvicorn requests
```

---

## 11. Project Structure

```
Blender-MCP-Server/
├── blender_mcp.py              ← Main addon file (install this in Blender)
├── integrations/               ← External integration modules
│   ├── __init__.py             ← Package init, exports ALL_INTEGRATION_TOOLS
│   ├── polyhaven.py            ← Poly Haven (HDRIs, textures, models)
│   ├── sketchfab.py            ← Sketchfab (3D model library)
│   ├── hyper3d.py              ← Hyper3D Rodin (AI 3D generation)
│   ├── csm.py                  ← CSM.ai (search + animation)
│   ├── hunyuan3d.py            ← Hunyuan3D (Tencent AI generation)
│   ├── mixamo.py               ← Mixamo animation helper
│   └── strategy.py             ← AI decision-making strategy prompt
├── blender_polymcp.py          ← PolyMCP toolkit helper
├── requirements.txt            ← Python dependencies list
├── README.md                   ← Project readme
├── INSTRUCTION.md              ← This file
├── LICENSE                     ← License
├── .env                        ← Your API keys (DO NOT COMMIT)
└── .gitignore                  ← Git ignore rules
```

---

## Quick Start Checklist

- [ ] Install Blender 3.6+
- [ ] Clone/download this project
- [ ] Install `blender_mcp.py` as a Blender addon
- [ ] Copy `integrations/` folder next to the installed addon
- [ ] Enable the addon in Blender Preferences
- [ ] Open N-Panel → MCP Server tab
- [ ] Toggle ON the integrations you want
- [ ] Enter API keys for Sketchfab / Hyper3D / CSM.ai / Hunyuan3D
- [ ] Click "Start Server"
- [ ] Verify at http://localhost:8000/docs
- [ ] Connect your AI client to http://localhost:8000/mcp
- [ ] Start creating! 🎨
