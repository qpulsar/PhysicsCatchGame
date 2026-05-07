import os
import json
import shutil
import tempfile
import zipfile
from typing import Dict, List, Any, Optional
from pathlib import Path
from ..database.database import DatabaseManager

class PublisherService:
    """Service to package a game and its assets for submission."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        # Project root detection
        self.project_root = Path(__file__).parent.parent.parent.absolute()

    def package_game(self, game_id: int) -> Optional[str]:
        """Collects all assets and data for a game and creates a ZIP package.
        Returns the path to the ZIP file.
        """
        game = self.db.get_game(game_id)
        if not game:
            return None

        # 1. Setup temp directory
        temp_dir = tempfile.mkdtemp(prefix=f"game_submit_{game_id}_")
        export_path = Path(temp_dir)
        assets_export_dir = export_path / "assets"
        assets_export_dir.mkdir()

        try:
            # 2. Collect Data
            manifest = {
                "game_info": dict(game),
                "settings": self.db.get_settings(game_id),
                "screens": self.db.get_screens(game_id),
                "levels": self._get_full_level_data(game_id),
                "assets": []
            }

            # 3. Identify and Copy Assets
            found_assets = self._identify_assets(manifest)
            copied_assets = []

            for rel_path in found_assets:
                abs_src = self.project_root / rel_path
                if abs_src.exists() and abs_src.is_file():
                    # Preserve structure inside ZIP's assets/ folder
                    dest_rel = rel_path
                    dest_full = export_path / dest_rel
                    dest_full.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(abs_src, dest_full)
                    copied_assets.append(str(rel_path))

            manifest["assets"] = copied_assets

            # 4. Save Manifest
            with open(export_path / "manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            # 5. Create ZIP
            zip_name = f"game_package_{game_id}.zip"
            zip_path = os.path.join(tempfile.gettempdir(), zip_name)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(export_path):
                    for file in files:
                        full_p = os.path.join(root, file)
                        rel_p = os.path.relpath(full_p, export_path)
                        zipf.write(full_p, rel_p)

            return zip_path

        except Exception as e:
            print(f"Packaging error: {e}")
            return None
        finally:
            # Cleanup temp folder (not the ZIP)
            # shutil.rmtree(temp_dir)
            pass

    def _get_full_level_data(self, game_id: int) -> List[Dict[str, Any]]:
        """Collects levels, expressions, and their associated effect/sprite info."""
        levels = self.db.get_levels(game_id)
        data = []
        for lvl in levels:
            lvl_id = lvl["id"]
            lvl_dict = dict(lvl)
            lvl_dict["expressions"] = self.db.get_expressions(lvl_id)
            # Add effect settings
            lvl_dict["effect_settings"] = self.db.get_level_effect_settings(lvl_id)
            # Add background regions
            lvl_dict["bg_regions"] = self.db.get_level_background_regions(lvl_id)
            data.append(lvl_dict)
        return data

    def _identify_assets(self, manifest: Dict[str, Any]) -> List[str]:
        """Parses manifest to find all unique file paths."""
        paths = set()

        # From Settings
        for key, val in manifest["settings"].items():
            if isinstance(val, str) and (val.startswith("assets/") or val.startswith("img/")):
                paths.add(val)

        # From Screens
        for sc in manifest["screens"]:
            try:
                sc_data = json.loads(sc["data_json"])
                # BG
                bg = (sc_data.get("background") or {}).get("image")
                if bg: paths.add(bg)
                # Music
                mus = sc_data.get("music")
                if mus: paths.add(mus)
                # Widgets
                for w in sc_data.get("widgets", []):
                    img = (w.get("sprite") or {}).get("image")
                    if img: paths.add(img)
            except:
                continue

        # From Levels (Effects and Regions)
        for lvl in manifest["levels"]:
            # Legacy effect paths
            eff = lvl.get("effect_settings") or {}
            for k in ["effect_correct_sheet", "effect_wrong_sheet"]:
                if eff.get(k): paths.add(eff[k])
            
            # Regions
            for reg in lvl.get("bg_regions") or []:
                if reg.get("sheet_path"): paths.add(reg["sheet_path"])

        # From Global Sprites (if any used)
        # We might need to scan if any sprite from 'sprites' table is used.
        # But most are covered by regions/screens.

        # Filter out empty or absolute paths (we only want project-relative ones)
        return [p.replace("\\", "/") for p in paths if p and not os.path.isabs(p)]

    def upload_game(self, zip_path: str, user_info: Dict[str, str], server_url: str) -> Dict[str, Any]:
        """Uploads the ZIP package to the submission server using multipart/form-data."""
        import urllib.request
        import urllib.parse
        import mimetypes
        import uuid

        try:
            boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
            parts = []

            # Add Form Fields
            for name, value in user_info.items():
                parts.append(f"--{boundary}")
                parts.append(f'Content-Disposition: form-data; name="{name}"')
                parts.append("")
                parts.append(str(value))

            # Add File
            filename = os.path.basename(zip_path)
            mime_type = mimetypes.guess_type(zip_path)[0] or 'application/octet-stream'
            parts.append(f"--{boundary}")
            parts.append(f'Content-Disposition: form-data; name="game_file"; filename="{filename}"')
            parts.append(f"Content-Type: {mime_type}")
            parts.append("")
            
            with open(zip_path, "rb") as f:
                file_content = f.read()
            
            # Combine everything
            body = b""
            for p in parts:
                if isinstance(p, str):
                    body += p.encode("utf-8") + b"\r\n"
                else:
                    body += p + b"\r\n"
            
            body += file_content + b"\r\n"
            body += f"--{boundary}--".encode("utf-8") + b"\r\n"

            # Request
            req = urllib.request.Request(server_url, data=body)
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            req.add_header("Content-Length", len(body))

            with urllib.request.urlopen(req) as response:
                resp_data = response.read().decode("utf-8")
                return {"status": "success", "data": json.loads(resp_data)}

        except Exception as e:
            return {"status": "error", "message": str(e)}
