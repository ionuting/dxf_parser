
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
import ezdxf
import io
import os
from pathlib import Path
import requests
import tempfile
import uuid
from typing import List
import logging
import json

# Optional imports for advanced boolean operations
try:
    from shapely.geometry import Polygon, Point
    from shapely.ops import unary_union
    import mapbox_earcut as earcut
    import numpy as np
    EARCUT_AVAILABLE = True
except ImportError:
    EARCUT_AVAILABLE = False
    print("⚠️ Earcut not available - using simple extrusion only")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# Directoare pentru fișiere temporare
TEMP_DIR = Path("temp_files")
TEMP_DIR.mkdir(exist_ok=True)

# Stochează fișierele DXF încărcate în sesiune (în memorie)
loaded_files = {}

def analyze_entities_by_layer(doc):
    """Analyze entities and return statistics per layer"""
    layer_stats = {}
    
    msp = doc.modelspace()
    for entity in msp:
        try:
            layer_name = str(entity.dxf.layer)
            entity_type = entity.dxftype()
            
            if layer_name not in layer_stats:
                layer_stats[layer_name] = {
                    "count": 0,
                    "types": {}
                }
            
            layer_stats[layer_name]["count"] += 1
            
            # Map DXF types to clearer terms
            type_mapping = {
                "LINE": "Line",
                "LWPOLYLINE": "Polyline",
                "POLYLINE": "Polyline",
                "ARC": "Arc",
                "CIRCLE": "Circle",
                "ELLIPSE": "Ellipse",
                "SPLINE": "Spline",
                "TEXT": "Text",
                "MTEXT": "Multiline Text",
                "INSERT": "Block",
                "HATCH": "Hatch",
                "DIMENSION": "Dimension",
                "POINT": "Point"
            }
            
            friendly_type = type_mapping.get(entity_type, entity_type)
            
            if friendly_type not in layer_stats[layer_name]["types"]:
                layer_stats[layer_name]["types"][friendly_type] = 0
            layer_stats[layer_name]["types"][friendly_type] += 1
            
        except Exception as e:
            logger.warning(f"Error analyzing entity: {e}")
            continue
    
    return layer_stats

@app.get("/")
async def read_root():
    return HTMLResponse(get_html_interface())

@app.get("/favicon.ico")
async def favicon():
    """Favicon endpoint - returnează 204 No Content"""
    from fastapi.responses import Response
    return Response(status_code=204)

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a DXF file and extract layers"""
    try:
        logger.info(f"Uploading file: {file.filename}")
        contents = await file.read()
        logger.info(f"File size: {len(contents)} bytes")
        
        # Save temporarily for ezdxf
        temp_file = TEMP_DIR / f"temp_{uuid.uuid4()}.dxf"
        with open(temp_file, 'wb') as f:
            f.write(contents)
        
        # Read with ezdxf
        doc = ezdxf.readfile(str(temp_file))
        
        # Delete temporary file
        temp_file.unlink()
        
        # Analyze entities per layer
        layer_stats = analyze_entities_by_layer(doc)
        
        layers = []
        for layer in doc.layers:
            try:
                layer_name = str(layer.dxf.name)
                stats = layer_stats.get(layer_name, {"count": 0, "types": {}})
                
                # Creează descrierea tipurilor
                types_list = [f"{count}x {type_name}" for type_name, count in stats["types"].items()]
                types_str = ", ".join(types_list) if types_list else "Fără elemente"
                
                layers.append({
                    "name": layer_name,
                    "color": int(layer.dxf.color),
                    "linetype": str(layer.dxf.linetype),
                    "count": stats["count"],
                    "types": types_str
                })
            except Exception as layer_err:
                logger.warning(f"Error reading layer: {layer_err}")
                continue
        
        # Salvează fișierul în memorie
        file_id = str(uuid.uuid4())
        loaded_files[file_id] = contents
        
        logger.info(f"File loaded successfully: {file_id}, layers: {len(layers)}")
        
        return {
            "status": "success",
            "file_id": file_id,
            "layers": sorted(layers, key=lambda x: x["name"]),
            "layer_count": len(layers)
        }
    except Exception as e:
        import traceback
        logger.error(f"Upload error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Eroare la citirea fișierului: {str(e)}")

@app.post("/api/upload-from-github")
async def upload_from_github(request: Request):
    """Upload a DXF file from GitHub raw URL"""
    try:
        payload = await request.json()
        github_url = payload.get("github_url")
        
        if not github_url:
            raise HTTPException(status_code=400, detail="URL GitHub nu este specificat")
        
        # Asigură-te că e URL de GitHub raw
        if "github.com" in github_url and "raw.githubusercontent.com" not in github_url:
            github_url = github_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        
        logger.info(f"Downloading from GitHub: {github_url}")
        response = requests.get(github_url)
        response.raise_for_status()
        
        contents = response.content
        
        # Save temporarily for ezdxf
        temp_file = TEMP_DIR / f"temp_github_{uuid.uuid4()}.dxf"
        with open(temp_file, 'wb') as f:
            f.write(contents)
        
        # Read with ezdxf
        doc = ezdxf.readfile(str(temp_file))
        
        # Delete temporary file
        temp_file.unlink()
        
        # Analyze entities per layer
        layer_stats = analyze_entities_by_layer(doc)
        
        layers = []
        for layer in doc.layers:
            try:
                layer_name = str(layer.dxf.name)
                stats = layer_stats.get(layer_name, {"count": 0, "types": {}})
                
                # Creează descrierea tipurilor
                types_list = [f"{count}x {type_name}" for type_name, count in stats["types"].items()]
                types_str = ", ".join(types_list) if types_list else "Fără elemente"
                
                layers.append({
                    "name": layer_name,
                    "color": int(layer.dxf.color),
                    "linetype": str(layer.dxf.linetype),
                    "count": stats["count"],
                    "types": types_str
                })
            except Exception as layer_err:
                logger.warning(f"Error reading layer: {layer_err}")
                continue
        
        # Salvează fișierul
        file_id = str(uuid.uuid4())
        loaded_files[file_id] = contents
        
        logger.info(f"GitHub file loaded: {file_id}, layers: {len(layers)}")
        
        return {
            "status": "success",
            "file_id": file_id,
            "layers": sorted(layers, key=lambda x: x["name"]),
            "layer_count": len(layers)
        }
    except Exception as e:
        import traceback
        logger.error(f"GitHub upload error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Eroare la descărcarea din GitHub: {str(e)}")

@app.post("/api/filter-layers")
async def filter_layers(request: Request):
    """Create a new DXF file with only selected layers"""
    try:
        payload = await request.json()
        file_id = payload.get("file_id")
        selected_layers = payload.get("selected_layers", [])
        
        logger.info(f"Filtering layers: {file_id}, selected: {selected_layers}")
        
        if file_id not in loaded_files:
            raise HTTPException(status_code=404, detail="Fișierul nu a fost găsit")
        
        if not selected_layers:
            raise HTTPException(status_code=400, detail="Niciun layer selectat")
        
        # Citește fișierul original
        temp_file = TEMP_DIR / f"temp_{uuid.uuid4()}.dxf"
        with open(temp_file, 'wb') as f:
            f.write(loaded_files[file_id])
        
        original_doc = ezdxf.readfile(str(temp_file))
        temp_file.unlink()
        
        # Creează un nou document
        new_doc = ezdxf.new(dxfversion=original_doc.dxfversion)
        
        # Copie layerele selectate
        for layer in original_doc.layers:
            layer_name = str(layer.dxf.name)
            if layer_name in selected_layers:
                try:
                    new_doc.layers.new(
                        name=layer_name,
                        dxfattribs={
                            "color": int(layer.dxf.color),
                            "linetype": str(layer.dxf.linetype)
                        }
                    )
                    logger.info(f"Layer copied: {layer_name}")
                except Exception as e:
                    logger.warning(f"Error copying layer {layer_name}: {e}")
        
        # Copie entitățile din layerele selectate
        msp_old = original_doc.modelspace()
        msp_new = new_doc.modelspace()
        
        entity_count = 0
        for entity in msp_old:
            entity_layer = str(entity.dxf.layer)
            if entity_layer in selected_layers:
                try:
                    new_entity = entity.copy()
                    msp_new.add_entity(new_entity)
                    entity_count += 1
                except Exception as e:
                    logger.warning(f"Error copying entity: {e}")
        
        logger.info(f"Copied {entity_count} entities")
        
        # Salvează într-un fișier temporar
        file_id_output = str(uuid.uuid4())
        temp_output = TEMP_DIR / f"output_{file_id_output}.dxf"
        new_doc.saveas(str(temp_output))
        
        # Citește fișierul ca bytes pentru stocare
        with open(temp_output, 'rb') as f:
            loaded_files[file_id_output] = f.read()
        
        logger.info(f"Filter completed: {file_id_output}, size: {len(loaded_files[file_id_output])} bytes")
        
        return {
            "status": "success",
            "file_id": file_id_output,
            "message": f"File created with {len(selected_layers)} layers and {entity_count} objects"
        }
    except Exception as e:
        import traceback
        logger.error(f"Filter error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Eroare la filtrare: {str(e)}")

@app.get("/api/download/{file_id}")
async def download_file(file_id: str):
    """Descarcă fișierul DXF"""
    if file_id not in loaded_files:
        raise HTTPException(status_code=404, detail="Fișierul nu a fost găsit")
    
    # Creează un fișier temporar
    temp_path = TEMP_DIR / f"{file_id}.dxf"
    with open(temp_path, "wb") as f:
        f.write(loaded_files[file_id])
    
    return FileResponse(
        path=temp_path,
        filename=f"filtered_{file_id[:8]}.dxf",
        media_type="application/octet-stream"
    )

@app.delete("/api/cleanup/{file_id}")
async def cleanup(file_id: str):
    """Curață fișierul din memorie"""
    if file_id in loaded_files:
        del loaded_files[file_id]
    
    temp_path = TEMP_DIR / f"{file_id}.dxf"
    if temp_path.exists():
        temp_path.unlink()
    
    return {"status": "success"}

@app.post("/api/get-entities")
async def get_entities(request: Request):
    """Get DXF entities for selected layers for viewer"""
    try:
        payload = await request.json()
        file_id = payload.get("file_id")
        selected_layers = payload.get("selected_layers", [])
        
        if file_id not in loaded_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Read the DXF file
        temp_file = TEMP_DIR / f"temp_entities_{uuid.uuid4()}.dxf"
        with open(temp_file, 'wb') as f:
            f.write(loaded_files[file_id])
        
        doc = ezdxf.readfile(str(temp_file))
        temp_file.unlink()
        
        # Extract entities from selected layers
        entities_data = []
        msp = doc.modelspace()
        
        for entity in msp:
            try:
                layer_name = str(entity.dxf.layer)
                if layer_name not in selected_layers:
                    continue
                
                entity_type = entity.dxftype()
                entity_info = {
                    "type": entity_type,
                    "layer": layer_name,
                    "color": int(entity.dxf.color) if hasattr(entity.dxf, 'color') else 256
                }
                
                if entity_type == "LINE":
                    start = entity.dxf.start
                    end = entity.dxf.end
                    entity_info["start"] = [start[0], start[1], start[2]]
                    entity_info["end"] = [end[0], end[1], end[2]]
                
                elif entity_type in ["LWPOLYLINE", "POLYLINE"]:
                    points = [[p[0], p[1], p[2] if len(p) > 2 else 0] for p in entity.get_points()]
                    entity_info["points"] = points
                    entity_info["closed"] = entity.is_closed
                
                elif entity_type == "CIRCLE":
                    center = entity.dxf.center
                    entity_info["center"] = [center[0], center[1], center[2]]
                    entity_info["radius"] = float(entity.dxf.radius)
                
                elif entity_type == "ARC":
                    center = entity.dxf.center
                    entity_info["center"] = [center[0], center[1], center[2]]
                    entity_info["radius"] = float(entity.dxf.radius)
                    entity_info["start_angle"] = float(entity.dxf.start_angle)
                    entity_info["end_angle"] = float(entity.dxf.end_angle)
                
                elif entity_type == "ELLIPSE":
                    center = entity.dxf.center
                    major_axis = entity.dxf.major_axis
                    entity_info["center"] = [center[0], center[1], center[2]]
                    entity_info["major_axis"] = [major_axis[0], major_axis[1], major_axis[2]]
                    entity_info["ratio"] = float(entity.dxf.ratio)
                
                elif entity_type == "SPLINE":
                    if hasattr(entity, 'control_points'):
                        points = [[p[0], p[1], p[2]] for p in entity.control_points]
                        entity_info["control_points"] = points
                
                entities_data.append(entity_info)
                
            except Exception as e:
                logger.warning(f"Error extracting entity: {e}")
                continue
        
        return {
            "status": "success",
            "entities": entities_data,
            "count": len(entities_data)
        }
        
    except Exception as e:
        import traceback
        logger.error(f"Get entities error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

def create_simple_extrusion(contour_points, z_offset, height):
    """Create simple extrusion without holes"""
    vertices = []
    faces = []
    
    # Bottom face vertices (at z_offset)
    for p in contour_points:
        vertices.append([p[0], p[1], z_offset])
    
    # Top face vertices (at z_offset + height)
    for p in contour_points:
        vertices.append([p[0], p[1], z_offset + height])
    
    n = len(contour_points)
    
    # Bottom face triangles (fan triangulation from first vertex)
    for i in range(1, n - 1):
        faces.append([0, i, i + 1])
    
    # Top face triangles (fan triangulation from first vertex, reversed winding)
    for i in range(1, n - 1):
        faces.append([n, n + i + 1, n + i])
    
    # Side face quads (split into 2 triangles each)
    for i in range(n):
        next_i = (i + 1) % n
        # First triangle of quad
        faces.append([i, next_i, n + i])
        # Second triangle of quad
        faces.append([next_i, n + next_i, n + i])
    
    return vertices, faces

def extrude_polygon_with_holes(exterior, holes, z_offset, height):
    """Extrude polygon with holes using earcut triangulation"""
    if not EARCUT_AVAILABLE:
        # Fallback to simple extrusion if earcut not available
        return create_simple_extrusion(exterior, z_offset, height)
    
    try:
        vertices = []
        faces = []
        
        # Prepare data for earcut
        # Earcut expects 2D array of coordinates (n, 2) and ring lengths
        all_points = []
        ring_ends = []
        # Add exterior ring
        for pt in exterior:
            all_points.append([float(pt[0]), float(pt[1])])
        ring_ends.append(len(exterior))
        # Add hole rings
        if holes:
            for hole in holes:
                for pt in hole:
                    all_points.append([float(pt[0]), float(pt[1])])
                ring_ends.append(ring_ends[-1] + len(hole))
        # Convert to numpy arrays
        vertices_2d = np.array(all_points, dtype=np.float64)
        ring_ends_array = np.array(ring_ends, dtype=np.uint32)
        # Triangulate using earcut
        triangles = earcut.triangulate_float64(vertices_2d, ring_ends_array)
        
        n_points = len(all_points)
        
        # Create bottom vertices (at z_offset)
        for pt in all_points:
            vertices.append([pt[0], pt[1], z_offset])
        
        # Create top vertices (at z_offset + height)
        for pt in all_points:
            vertices.append([pt[0], pt[1], z_offset + height])
        
        # Bottom face triangles (from earcut)
        for i in range(0, len(triangles), 3):
            faces.append([int(triangles[i]), int(triangles[i+1]), int(triangles[i+2])])
        
        # Top face triangles (reversed winding)
        for i in range(0, len(triangles), 3):
            faces.append([int(triangles[i]) + n_points, int(triangles[i+2]) + n_points, int(triangles[i+1]) + n_points])
        
        # Side faces - exterior
        n_ext = len(exterior)
        for i in range(n_ext):
            next_i = (i + 1) % n_ext
            # Two triangles per quad
            faces.append([i, next_i, i + n_points])
            faces.append([next_i, next_i + n_points, i + n_points])
        
        # Side faces - holes (reversed winding for inward facing)
        point_offset = n_ext
        if holes:
            for hole in holes:
                n_hole = len(hole)
                for i in range(n_hole):
                    curr = point_offset + i
                    next_i = point_offset + ((i + 1) % n_hole)
                    # Reversed winding for holes
                    faces.append([curr, curr + n_points, next_i])
                    faces.append([next_i, curr + n_points, next_i + n_points])
                point_offset += n_hole
        
        return vertices, faces
        
    except Exception as e:
        import traceback
        logger.warning(f"Earcut triangulation failed: {e}\n{traceback.format_exc()}")
        return create_simple_extrusion(exterior, z_offset, height)

@app.post("/api/generate-3d-geometry")
async def generate_3d_geometry(request: Request):
    """Generate 3D extruded geometry from layer contours"""
    try:
        payload = await request.json()
        file_id = payload.get("file_id")
        extrusions = payload.get("extrusions", [])
        
        if file_id not in loaded_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Read the DXF file
        temp_file = TEMP_DIR / f"temp_3d_{uuid.uuid4()}.dxf"
        with open(temp_file, 'wb') as f:
            f.write(loaded_files[file_id])
        
        doc = ezdxf.readfile(str(temp_file))
        temp_file.unlink()
        
        geometries = []
        
        for extrusion in extrusions:
            operation_name = extrusion.get("operation_name", "Extrusion")
            operation_color = extrusion.get("operation_color", "#4CAF50")
            contour_layer = extrusion.get("contour_layer")
            cut_layer = extrusion.get("cut_layer")
            z_offset = float(extrusion.get("z_offset", 0))
            height = float(extrusion.get("height", 100))
            
            # Extract each closed contour as separate entity
            msp = doc.modelspace()
            contours = []  # List of contours, each contour is a list of points
            
            for entity in msp.query(f'*[layer=="{contour_layer}"]'):
                contour_points = []
                
                if entity.dxftype() == 'LWPOLYLINE':
                    points = [(p[0], p[1]) for p in entity.get_points()]
                    # Process even if not explicitly closed - check if first and last point are same
                    if len(points) > 2:
                        if not entity.closed and points[0] != points[-1]:
                            # If not closed but forms a loop, close it
                            import math
                            dist = math.sqrt((points[0][0] - points[-1][0])**2 + (points[0][1] - points[-1][1])**2)
                            if dist < 0.001:  # Very close, treat as closed
                                points[-1] = points[0]
                            else:
                                # Not a closed contour, skip
                                continue
                        contour_points = points
                        
                elif entity.dxftype() == 'POLYLINE':
                    points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                    if len(points) > 2:
                        if not entity.is_closed and points[0] != points[-1]:
                            import math
                            dist = math.sqrt((points[0][0] - points[-1][0])**2 + (points[0][1] - points[-1][1])**2)
                            if dist < 0.001:
                                points[-1] = points[0]
                            else:
                                continue
                        contour_points = points
                        
                elif entity.dxftype() == 'CIRCLE':
                    # Approximate circle with polygon
                    center = entity.dxf.center
                    radius = entity.dxf.radius
                    segments = 32
                    import math
                    for i in range(segments):
                        angle = (i / segments) * 2 * math.pi
                        x = center.x + radius * math.cos(angle)
                        y = center.y + radius * math.sin(angle)
                        contour_points.append((x, y))
                
                # Add this contour if valid
                if len(contour_points) >= 3:
                    # Remove consecutive duplicates
                    unique_points = [contour_points[0]]
                    for p in contour_points[1:]:
                        if p != unique_points[-1]:
                            unique_points.append(p)
                    # Ensure closed polygon (first == last)
                    if unique_points[0] != unique_points[-1]:
                        unique_points.append(unique_points[0])
                    if len(unique_points) >= 4:
                        contours.append(unique_points)
            
            # Extract cut contours if cut_layer is specified
            cut_contours = []
            if cut_layer:
                for entity in msp.query(f'*[layer=="{cut_layer}"]'):
                    contour_points = []
                    
                    if entity.dxftype() == 'LWPOLYLINE':
                        points = [(p[0], p[1]) for p in entity.get_points()]
                        if len(points) > 2:
                            if not entity.closed and points[0] != points[-1]:
                                import math
                                dist = math.sqrt((points[0][0] - points[-1][0])**2 + (points[0][1] - points[-1][1])**2)
                                if dist < 0.001:
                                    points[-1] = points[0]
                                else:
                                    continue
                            contour_points = points
                            
                    elif entity.dxftype() == 'POLYLINE':
                        points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                        if len(points) > 2:
                            if not entity.is_closed and points[0] != points[-1]:
                                import math
                                dist = math.sqrt((points[0][0] - points[-1][0])**2 + (points[0][1] - points[-1][1])**2)
                                if dist < 0.001:
                                    points[-1] = points[0]
                                else:
                                    continue
                            contour_points = points
                            
                    elif entity.dxftype() == 'CIRCLE':
                        center = entity.dxf.center
                        radius = entity.dxf.radius
                        segments = 32
                        import math
                        for i in range(segments):
                            angle = (i / segments) * 2 * math.pi
                            x = center.x + radius * math.cos(angle)
                            y = center.y + radius * math.sin(angle)
                            contour_points.append((x, y))
                    
                    if len(contour_points) >= 3:
                        unique_points = [contour_points[0]]
                        for p in contour_points[1:]:
                            if p != unique_points[-1]:
                                unique_points.append(p)
                        
                        if len(unique_points) >= 3:
                            cut_contours.append(unique_points)
            
            # Calculate total area of cut contours
            cut_area = 0
            for cut_contour in cut_contours:
                area = 0
                n = len(cut_contour)
                for i in range(n):
                    j = (i + 1) % n
                    area += cut_contour[i][0] * cut_contour[j][1]
                    area -= cut_contour[j][0] * cut_contour[i][1]
                cut_area += abs(area) / 2.0
            
            # Create a separate geometry for each contour
            for contour_idx, contour_points in enumerate(contours):
                # Use Earcut for boolean difference if cut_layer is specified and Earcut is available
                def sanitize_points(points):
                    return [ (float(p[0]), float(p[1])) for p in points ]

                if cut_contours and EARCUT_AVAILABLE:
                    try:
                        # Create main polygon from contour (sanitize input)
                        main_polygon = Polygon(sanitize_points(contour_points))

                        # Create cut polygons (sanitize input)
                        cut_polygons = [Polygon(sanitize_points(cut_contour)) for cut_contour in cut_contours]
                        cut_union = unary_union(cut_polygons)
                        
                        # Perform boolean difference
                        result_polygon = main_polygon.difference(cut_union)
                        
                        # Check if result is valid
                        if result_polygon.is_empty:
                            continue
                        
                        # Get exterior and holes
                        if result_polygon.geom_type == 'Polygon':
                            exterior_coords = list(result_polygon.exterior.coords[:-1])  # Remove duplicate last point
                            holes = [list(hole.coords[:-1]) for hole in result_polygon.interiors]
                            
                            # Extrude polygon with holes
                            vertices, faces = extrude_polygon_with_holes(exterior_coords, holes, z_offset, height)
                            volume = result_polygon.area * height
                            
                            geometries.append({
                                "operation_name": operation_name,
                                "operation_color": operation_color,
                                "contour_layer": contour_layer,
                                "contour_index": contour_idx,
                                "cut_layer": cut_layer,
                                "z_offset": z_offset,
                                "height": height,
                                "volume": volume,
                                "vertices": vertices,
                                "faces": faces,
                                "vertex_count": len(vertices),
                                "face_count": len(faces)
                            })
                            continue
                            
                        elif result_polygon.geom_type == 'MultiPolygon':
                            # Handle multiple polygons - process each separately
                            for poly in result_polygon.geoms:
                                exterior_coords = list(poly.exterior.coords[:-1])
                                holes = [list(hole.coords[:-1]) for hole in poly.interiors]
                                vertices, faces = extrude_polygon_with_holes(exterior_coords, holes, z_offset, height)
                                
                                volume = poly.area * height
                                
                                geometries.append({
                                    "operation_name": operation_name,
                                    "operation_color": operation_color,
                                    "contour_layer": contour_layer,
                                    "contour_index": contour_idx,
                                    "cut_layer": cut_layer,
                                    "z_offset": z_offset,
                                    "height": height,
                                    "volume": volume,
                                    "vertices": vertices,
                                    "faces": faces,
                                    "vertex_count": len(vertices),
                                    "face_count": len(faces)
                                })
                            continue
                        else:
                            continue
                        
                    except Exception as e:
                        logger.warning(f"Shapely boolean operation failed: {e}, using simple extrusion")
                        # Fallback to simple extrusion
                        vertices, faces = create_simple_extrusion(contour_points, z_offset, height)
                        
                        # Calculate volume using Shoelace formula (subtract cut area)
                        area = 0
                        n = len(contour_points)
                        for i in range(n):
                            j = (i + 1) % n
                            area += contour_points[i][0] * contour_points[j][1]
                            area -= contour_points[j][0] * contour_points[i][1]
                        effective_area = abs(area) / 2.0 - cut_area
                        if effective_area < 0:
                            effective_area = 0
                        volume = effective_area * height
                        
                elif cut_contours and not EARCUT_AVAILABLE:
                    # Earcut not available - use simple volume subtraction
                    vertices, faces = create_simple_extrusion(contour_points, z_offset, height)
                    
                    # Calculate volume using Shoelace formula (subtract cut area)
                    area = 0
                    n = len(contour_points)
                    for i in range(n):
                        j = (i + 1) % n
                        area += contour_points[i][0] * contour_points[j][1]
                        area -= contour_points[j][0] * contour_points[i][1]
                    effective_area = abs(area) / 2.0 - cut_area
                    if effective_area < 0:
                        effective_area = 0
                    volume = effective_area * height
                    
                else:
                    # No cut layer - use earcut triangulation for all polygons
                    exterior = contour_points
                    holes = []
                    vertices, faces = extrude_polygon_with_holes(exterior, holes, z_offset, height)
                    # Calculate volume using Shoelace formula
                    area = 0
                    n = len(contour_points)
                    for i in range(n):
                        j = (i + 1) % n
                        area += contour_points[i][0] * contour_points[j][1]
                        area -= contour_points[j][0] * contour_points[i][1]
                    volume = abs(area) / 2.0 * height
                
                geometries.append({
                    "operation_name": operation_name,
                    "operation_color": operation_color,
                    "contour_layer": contour_layer,
                    "contour_index": contour_idx,
                    "cut_layer": cut_layer,
                    "z_offset": z_offset,
                    "height": height,
                    "volume": volume,
                    "vertices": vertices,
                    "faces": faces,
                    "vertex_count": len(vertices),
                    "face_count": len(faces)
                })
        
        return {
            "status": "success",
            "geometries": geometries,
            "count": len(geometries)
        }
        
    except Exception as e:
        import traceback
        logger.error(f"Generate 3D geometry error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@app.post("/api/generate-report")
async def generate_report(request: Request):
    """Generate statistical report for selected layers"""
    try:
        import math
        payload = await request.json()
        file_id = payload.get("file_id")
        selected_layers = payload.get("selected_layers", [])
        unit = payload.get("unit", "mm")  # Default: mm
        
        logger.info(f"Generating report for: {file_id}, layers: {selected_layers}, unit: {unit}")
        
        if file_id not in loaded_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        if not selected_layers:
            raise HTTPException(status_code=400, detail="No layers selected")
        
        # Unit conversion factors (assuming DXF data is in mm)
        unit_factors = {
            "mm": {"length": 1, "area": 1},
            "cm": {"length": 0.1, "area": 0.01},
            "m": {"length": 0.001, "area": 0.000001}
        }
        
        factor = unit_factors.get(unit, unit_factors["mm"])
        
        # Read the file
        temp_file = TEMP_DIR / f"temp_report_{uuid.uuid4()}.dxf"
        with open(temp_file, 'wb') as f:
            f.write(loaded_files[file_id])
        
        doc = ezdxf.readfile(str(temp_file))
        temp_file.unlink()
        
        # Calculate statistics per layer
        layer_reports = {}
        
        for layer_name in selected_layers:
            layer_reports[layer_name] = {
                "total_length": 0,
                "total_area": 0,
                "max_length": 0,
                "max_area": 0,
                "entity_count": 0,
                "entities": []
            }
        
        msp = doc.modelspace()
        
        for entity in msp:
            try:
                layer_name = str(entity.dxf.layer)
                if layer_name not in selected_layers:
                    continue
                
                entity_type = entity.dxftype()
                length = 0
                area = 0
                
                if entity_type == "LINE":
                    # Calculate line length
                    start = entity.dxf.start
                    end = entity.dxf.end
                    length = math.sqrt((end[0]-start[0])**2 + (end[1]-start[1])**2 + (end[2]-start[2])**2)
                
                elif entity_type in ["LWPOLYLINE", "POLYLINE"]:
                    # Calculate polyline length and area if closed
                    points = list(entity.get_points())
                    if len(points) > 1:
                        for i in range(len(points) - 1):
                            p1 = points[i]
                            p2 = points[i + 1]
                            length += math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                        
                        # If closed, add closing segment and calculate area
                        if entity.is_closed:
                            p1 = points[-1]
                            p2 = points[0]
                            length += math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                            
                            # Shoelace formula for area
                            area = 0
                            for i in range(len(points)):
                                j = (i + 1) % len(points)
                                area += points[i][0] * points[j][1]
                                area -= points[j][0] * points[i][1]
                            area = abs(area) / 2.0
                
                elif entity_type == "CIRCLE":
                    # Circle circumference and area
                    radius = entity.dxf.radius
                    length = 2 * math.pi * radius  # circumference
                    area = math.pi * radius ** 2
                
                elif entity_type == "ARC":
                    # Arc length
                    radius = entity.dxf.radius
                    start_angle = math.radians(entity.dxf.start_angle)
                    end_angle = math.radians(entity.dxf.end_angle)
                    angle_diff = end_angle - start_angle
                    if angle_diff < 0:
                        angle_diff += 2 * math.pi
                    length = radius * angle_diff
                
                elif entity_type == "ELLIPSE":
                    # Approximate ellipse perimeter and area
                    major_axis = entity.dxf.major_axis
                    ratio = entity.dxf.ratio
                    a = math.sqrt(major_axis[0]**2 + major_axis[1]**2 + major_axis[2]**2)
                    b = a * ratio
                    # Ramanujan's approximation for perimeter
                    h = ((a - b) ** 2) / ((a + b) ** 2)
                    length = math.pi * (a + b) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))
                    area = math.pi * a * b
                
                if length > 0 or area > 0:
                    layer_reports[layer_name]["total_length"] += length
                    layer_reports[layer_name]["total_area"] += area
                    layer_reports[layer_name]["max_length"] = max(layer_reports[layer_name]["max_length"], length)
                    layer_reports[layer_name]["max_area"] = max(layer_reports[layer_name]["max_area"], area)
                    layer_reports[layer_name]["entity_count"] += 1
                    
                    layer_reports[layer_name]["entities"].append({
                        "type": entity_type,
                        "length": round(length, 3),
                        "area": round(area, 3)
                    })
            
            except Exception as e:
                logger.warning(f"Error calculating entity stats: {e}")
                continue
        
        # Format the report with unit conversion
        formatted_report = []
        for layer_name, stats in layer_reports.items():
            formatted_report.append({
                "layer": layer_name,
                "entity_count": stats["entity_count"],
                "total_length": round(stats["total_length"] * factor["length"], 3),
                "total_area": round(stats["total_area"] * factor["area"], 3),
                "max_length": round(stats["max_length"] * factor["length"], 3),
                "max_area": round(stats["max_area"] * factor["area"], 3),
                # Raw values (in mm) for calculator
                "raw_total_length": round(stats["total_length"], 3),
                "raw_total_area": round(stats["total_area"], 3),
                "raw_max_length": round(stats["max_length"], 3),
                "raw_max_area": round(stats["max_area"], 3)
            })
        
        return {
            "status": "success",
            "report": formatted_report,
            "unit": unit
        }
        
    except Exception as e:
        import traceback
        logger.error(f"Report generation error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Report error: {str(e)}")

def get_html_interface():
    return """
    <!DOCTYPE html>
    <html lang="ro">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DXF Layer Filter</title>
        <script src="https://cdn.plot.ly/plotly-2.27.0.min.js" charset="utf-8"></script>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 900px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 28px;
                margin-bottom: 5px;
            }
            
            .header p {
                font-size: 14px;
                opacity: 0.9;
            }
            
            .content {
                padding: 30px;
            }
            
            .section {
                margin-bottom: 30px;
            }
            
            .section-title {
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 15px;
                color: #333;
            }
            
            .upload-area {
                border: 2px dashed #667eea;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                background: #f8f9fa;
                transition: all 0.3s ease;
                cursor: pointer;
            }
            
            .upload-area:hover {
                border-color: #764ba2;
                background: #f0f0f0;
            }
            
            .upload-area.dragover {
                border-color: #764ba2;
                background: #e8e8ff;
            }
            
            .input-group {
                margin-bottom: 15px;
            }
            
            input[type="file"],
            input[type="text"] {
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 6px;
                font-size: 14px;
            }
            
            input[type="text"] {
                margin-bottom: 10px;
            }
            
            .button-group {
                display: flex;
                gap: 10px;
                margin-top: 15px;
            }
            
            button {
                flex: 1;
                padding: 12px 20px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            
            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            
            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            
            .btn-primary:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
            }
            
            .btn-secondary {
                background: #e0e0e0;
                color: #333;
            }
            
            .btn-secondary:hover {
                background: #d0d0d0;
            }
            
            .btn-secondary:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            
            .layers-container {
                display: none;
                max-height: 400px;
                overflow-y: auto;
                border: 1px solid #ddd;
                border-radius: 8px;
                background: #f8f9fa;
            }
            
            .layers-container.show {
                display: block;
            }
            
            .layer-item {
                padding: 12px;
                border-bottom: 1px solid #e0e0e0;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .layer-item:last-child {
                border-bottom: none;
            }
            
            .layer-item input[type="checkbox"] {
                width: 18px;
                height: 18px;
                cursor: pointer;
            }
            
            .layer-name {
                font-size: 14px;
                color: #333;
                flex: 1;
            }
            
            .layer-color {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
            
            .status-message {
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 15px;
                display: none;
                font-size: 14px;
            }
            
            .status-message.show {
                display: block;
            }
            
            .status-message.success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            
            .status-message.error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            
            .status-message.info {
                background: #d1ecf1;
                color: #0c5460;
                border: 1px solid #bee5eb;
            }
            
            .layer-stats {
                font-size: 13px;
                color: #666;
                margin-top: 10px;
                padding: 10px;
                background: white;
                border-radius: 4px;
            }
            
            .action-buttons {
                display: flex;
                gap: 10px;
                margin-top: 20px;
            }
            
            .action-buttons button {
                flex: 1;
            }
            
            .loading {
                display: none;
                text-align: center;
                color: #667eea;
            }
            
            .loading.show {
                display: block;
            }
            
            .spinner {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin-right: 10px;
            }
            
                @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            .report-section {
                margin-top: 20px;
            }
            
            .report-table {
                width: 100%;
                border-collapse: collapse;
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            .report-table th,
            .report-table td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #e0e0e0;
            }
            
            .report-table th {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                font-weight: 600;
                font-size: 13px;
                text-transform: uppercase;
            }
            
            .report-table tr:last-child td {
                border-bottom: none;
            }
            
            .report-table tr:hover {
                background: #f8f9fa;
            }
            
            .report-table td {
                font-size: 14px;
                color: #333;
            }
            
            .report-table td:first-child {
                font-weight: 600;
                color: #667eea;
            }
            
            .number-cell {
                font-family: 'Courier New', monospace;
                text-align: right !important;
            }
            
            .calculator-section {
                margin-top: 20px;
            }
            
            .calculator-row {
                display: flex;
                gap: 10px;
                margin-bottom: 10px;
                align-items: center;
                background: white;
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            .calculator-row select,
            .calculator-row input {
                padding: 8px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
            }
            
            .calculator-row select {
                flex: 1;
                min-width: 120px;
            }
            
            .calculator-row .operator-select {
                flex: 0 0 80px;
            }
            
            .calculator-row .result-input {
                flex: 1;
                background: #f8f9fa;
                font-weight: 600;
                color: #667eea;
                font-family: 'Courier New', monospace;
            }
            
            .calculator-row .remove-btn {
                flex: 0 0 40px;
                height: 40px;
                background: #ff4444;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 18px;
                transition: background 0.3s;
            }
            
            .calculator-row .remove-btn:hover {
                background: #cc0000;
            }
            
            .calculator-controls {
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
            }
            
            .calculator-controls select {
                padding: 10px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 14px;
                flex: 1;
            }
            
            .add-calc-btn {
                background: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 600;
                transition: background 0.3s;
            }
            
            .add-calc-btn:hover {
                background: #218838;
            }
            
            .viewer-section {
                margin-top: 20px;
            }
            
            #viewerContainer {
                width: 100%;
                height: 600px;
                background: #ffffff;
                border-radius: 8px;
                position: relative;
            }
            
            .viewer-controls {
                position: absolute;
                top: 10px;
                right: 10px;
                z-index: 100;
                display: flex;
                gap: 5px;
            }
            
            .viewer-btn {
                background: rgba(255, 255, 255, 0.9);
                border: none;
                padding: 8px 12px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 12px;
                font-weight: 600;
                transition: background 0.3s;
            }
            
            .viewer-btn:hover {
                background: rgba(255, 255, 255, 1);
            }
            
            .viewer-info {
                position: absolute;
                bottom: 10px;
                left: 10px;
                background: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 12px;
                z-index: 100;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎨 DXF Layer Filter</h1>
                <p>Upload, select layers, and download the filtered file</p>
            </div>
            
            <div class="content">
                <!-- Status Messages -->
                <div id="statusMessage" class="status-message"></div>
                
                <!-- Upload Section -->
                <div class="section">
                    <div class="section-title">1. Upload DXF File</div>
                    
                    <div class="input-group">
                        <div class="upload-area" id="uploadArea">
                            <p>Drag and drop DXF file here or</p>
                            <input type="file" id="fileInput" accept=".dxf" style="display: none;">
                            <button class="btn-primary" onclick="document.getElementById('fileInput').click()" style="width: 150px; margin-top: 10px;">
                                Select File
                            </button>
                        </div>
                    </div>
                    
                    <div style="text-align: center; margin: 15px 0; color: #999;">OR</div>
                    
                    <div class="input-group">
                        <input type="text" id="githubUrl" placeholder="https://raw.githubusercontent.com/.../*.dxf">
                        <button class="btn-primary" onclick="uploadFromGithub()">Upload from GitHub</button>
                    </div>
                </div>
                
                <!-- Loading Indicator -->
                <div id="loading" class="loading">
                    <span class="spinner"></span> Processing...
                </div>
                
                <!-- Layers Section -->
                <div class="section">
                    <div class="section-title">2. Select Layers</div>
                    <div id="layersContainer" class="layers-container"></div>
                    <div id="layerStats" class="layer-stats" style="display: none;"></div>
                </div>
                
                <!-- Viewer Section -->
                <div class="section viewer-section" id="viewerSection">
                    <div class="section-title">👁️ 3D Viewer - Selected Layers</div>
                    <div style="margin-bottom: 10px; display: flex; gap: 10px; flex-wrap: wrap;">
                        <button class="btn-primary" onclick="reloadViewer()">🔄 Load 3D View</button>
                        <button class="btn-secondary" onclick="setViewTop()">⬆️ Top</button>
                        <button class="btn-secondary" onclick="setViewFront()">🔼 Front</button>
                        <button class="btn-secondary" onclick="setViewBack()">🔽 Back</button>
                        <button class="btn-secondary" onclick="setViewLeft()">◀️ Left</button>
                        <button class="btn-secondary" onclick="setViewRight()">▶️ Right</button>
                        <button class="btn-secondary" onclick="setViewBottom()">⬇️ Bottom</button>
                        <button class="btn-secondary" onclick="setViewIsometric()">🎲 Isometric</button>
                    </div>
                    <div id="viewerContainer"></div>
                    <div style="margin-top: 10px; font-size: 12px; color: #666;">
                        💡 Use mouse to rotate, pan, and zoom the 3D view
                    </div>
                </div>
                
                <!-- Volume Analysis Section -->
                <div class="section" id="volumeAnalysisSection" style="display: none;">
                    <div class="section-title">📊 Volume Analysis by Operation</div>
                    <div id="volumeChartContainer" style="height: 400px;"></div>
                </div>
                
                <!-- Unit Selection -->
                <div class="section">
                    <div class="section-title">3. Measurement Unit</div>
                    <div class="input-group">
                        <select id="unitSelect" style="padding: 10px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 14px; width: 100%; max-width: 200px;">
                            <option value="mm">Millimeters (mm)</option>
                            <option value="cm">Centimeters (cm)</option>
                            <option value="m" selected>Meters (m)</option>
                        </select>
                    </div>
                </div>
                
                <!-- Action Buttons -->
                <div class="action-buttons">
                    <button class="btn-primary" id="filterBtn" onclick="filterLayers()" disabled>
                        Download Filtered File
                    </button>
                    <button class="btn-secondary" id="reportBtn" onclick="generateReport()" disabled>
                        Generate Report
                    </button>
                    <button class="btn-secondary" id="clearBtn" onclick="clearAll()" disabled>
                        Clear and Reload
                    </button>
                </div>
                
                <!-- Report Section -->
                <div class="section report-section" id="reportSection" style="display: none;">
                    <div class="section-title">📊 Statistical Report</div>
                    <div id="reportContainer"></div>
                </div>
                
                <!-- 3D Geometry Generator Section -->
                <div class="section" id="geometryGeneratorSection" style="display: none;">
                    <div class="section-title">🏗️ 3D Geometry Generator</div>
                    <p style="font-size: 14px; color: #666; margin-bottom: 15px;">
                        Create 3D extruded solids from layer contours with optional voids and vertical translation.
                    </p>
                    
                    <div style="margin-bottom: 15px;">
                        <button class="btn-primary" onclick="addGeometryRow()">+ Add Extrusion</button>
                        <button class="btn-secondary" onclick="generateGeometry()">🎲 Generate & View 3D</button>
                    </div>
                    
                    <div id="geometryRows"></div>
                </div>
                
                <!-- Calculator Section -->
                <div class="section calculator-section" id="calculatorSection" style="display: none;">
                    <div class="section-title">🧮 Advanced Calculator</div>
                    
                    <div class="calculator-controls">
                        <select id="calcPropertyType">
                            <option value="length">Length</option>
                            <option value="area">Area</option>
                        </select>
                        <select id="calcUnit">
                            <option value="mm">Millimeters (mm)</option>
                            <option value="cm">Centimeters (cm)</option>
                            <option value="m" selected>Meters (m)</option>
                        </select>
                        <button class="add-calc-btn" onclick="addCalculatorRow()">+ Add Calculation</button>
                    </div>
                    
                    <div id="calculatorRows"></div>
                </div>
            </div>
        </div>
        
        <script>
            let currentFileId = null;
            let selectedLayers = new Set();
            let currentReportData = null;
            let layerDataCache = {};
            let calculatorRowId = 0;
            let layerColors = {}; // Store custom colors for each layer
            let geometryRowId = 0; // For 3D geometry generator
            
            // Make functions globally available
            window.uploadFile = uploadFile;
            window.uploadFromGithub = uploadFromGithub;
            window.filterLayers = filterLayers;
            window.clearAll = clearAll;
            window.generateReport = generateReport;
            window.addCalculatorRow = addCalculatorRow;
            window.removeCalculatorRow = removeCalculatorRow;
            window.calculateRow = calculateRow;
            window.reloadViewer = reloadViewer;
            window.setViewTop = setViewTop;
            window.setViewBottom = setViewBottom;
            window.setViewFront = setViewFront;
            window.setViewBack = setViewBack;
            window.setViewLeft = setViewLeft;
            window.setViewRight = setViewRight;
            window.setViewIsometric = setViewIsometric;
            window.addGeometryRow = addGeometryRow;
            window.removeGeometryRow = removeGeometryRow;
            window.generateGeometry = generateGeometry;
            
            // Drag and drop
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            
            // Unit selector change listener
            document.getElementById('unitSelect').addEventListener('change', () => {
                if (currentReportData) {
                    generateReport();
                }
            });
            
            // Calculator unit/property change listener
            document.getElementById('calcPropertyType').addEventListener('change', updateAllCalculations);
            document.getElementById('calcUnit').addEventListener('change', updateAllCalculations);
            
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    fileInput.files = files;
                    uploadFile();
                }
            });
            
            fileInput.addEventListener('change', uploadFile);
            
            function showStatus(message, type = 'info') {
                const statusEl = document.getElementById('statusMessage');
                statusEl.textContent = message;
                statusEl.className = `status-message show ${type}`;
                setTimeout(() => statusEl.classList.remove('show'), 5000);
            }
            
            function showLoading(show) {
                document.getElementById('loading').classList.toggle('show', show);
            }
            
            async function uploadFile() {
                const file = fileInput.files[0];
                if (!file) return;
                
                if (!file.name.toLowerCase().endsWith('.dxf')) {
                    showStatus('Please select a valid DXF file!', 'error');
                    return;
                }
                
                showLoading(true);
                const formData = new FormData();
                formData.append('file', file);
                
                try {
                    const response = await fetch('/api/upload', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!response.ok) throw new Error('Upload error');
                    
                    const data = await response.json();
                    currentFileId = data.file_id;
                    currentDxfData = data;
                    displayLayers(data.layers);
                    showStatus(`File uploaded successfully! ${data.layer_count} layers found. Select layers and click 'Load 3D View' to visualize.`, 'success');
                    
                } catch (error) {
                    showStatus(`Eroare: ${error.message}`, 'error');
                } finally {
                    showLoading(false);
                }
            }
            
            async function uploadFromGithub() {
                const url = document.getElementById('githubUrl').value;
                if (!url) {
                    showStatus('Please enter a valid URL!', 'error');
                    return;
                }
                
                showLoading(true);
                
                try {
                    const response = await fetch('/api/upload-from-github', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ github_url: url })
                    });
                    
                    if (!response.ok) throw new Error('Download error');
                    
                    const data = await response.json();
                    currentFileId = data.file_id;
                    currentDxfData = data;
                    displayLayers(data.layers);
                    showStatus(`GitHub file uploaded! ${data.layer_count} layers. Select layers and click 'Load 3D View' to visualize.`, 'success');
                    
                } catch (error) {
                    showStatus(`Eroare: ${error.message}`, 'error');
                } finally {
                    showLoading(false);
                }
            }
            
            function displayLayers(layers) {
                const container = document.getElementById('layersContainer');
                container.innerHTML = '';
                selectedLayers.clear();
                
                layers.forEach(layer => {
                    const item = document.createElement('div');
                    item.className = 'layer-item';
                    
                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.value = layer.name;
                    checkbox.addEventListener('change', (e) => {
                        if (e.target.checked) {
                            selectedLayers.add(layer.name);
                        } else {
                            selectedLayers.delete(layer.name);
                        }
                        updateStats();
                        // Viewer will update when user clicks "Load 3D View" button
                    });
                    
                    const label = document.createElement('label');
                    label.style.display = 'flex';
                    label.style.alignItems = 'center';
                    label.style.width = '100%';
                    label.style.cursor = 'pointer';
                    label.style.gap = '10px';
                    
                    const colorDiv = document.createElement('div');
                    colorDiv.className = 'layer-color';
                    const dxfColor = getDxfColor(layer.color);
                    colorDiv.style.backgroundColor = dxfColor;
                    
                    // Add color picker for custom color
                    const colorPicker = document.createElement('input');
                    colorPicker.type = 'color';
                    colorPicker.value = dxfColor;
                    colorPicker.style.width = '30px';
                    colorPicker.style.height = '30px';
                    colorPicker.style.border = 'none';
                    colorPicker.style.cursor = 'pointer';
                    colorPicker.style.borderRadius = '4px';
                    colorPicker.title = 'Choose custom color for 3D viewer';
                    colorPicker.addEventListener('change', (e) => {
                        e.stopPropagation();
                        layerColors[layer.name] = e.target.value;
                        colorDiv.style.backgroundColor = e.target.value;
                    });
                    // Initialize with default DXF color
                    layerColors[layer.name] = dxfColor;
                    
                    const nameDiv = document.createElement('div');
                    nameDiv.style.flex = '1';
                    nameDiv.style.display = 'flex';
                    nameDiv.style.flexDirection = 'column';
                    nameDiv.style.gap = '4px';
                    
                    const nameSpan = document.createElement('span');
                    nameSpan.className = 'layer-name';
                    nameSpan.style.fontWeight = '600';
                    nameSpan.textContent = layer.name;
                    
                    const infoSpan = document.createElement('span');
                    infoSpan.style.fontSize = '12px';
                    infoSpan.style.color = '#666';
                    infoSpan.textContent = `${layer.count} elements: ${layer.types}`;
                    
                    nameDiv.appendChild(nameSpan);
                    nameDiv.appendChild(infoSpan);
                    
                    label.appendChild(checkbox);
                    label.appendChild(colorDiv);
                    label.appendChild(colorPicker);
                    label.appendChild(nameDiv);
                    
                    item.appendChild(label);
                    container.appendChild(item);
                });
                
                container.classList.add('show');
                document.getElementById('layerStats').style.display = 'block';
                updateStats();
                
                document.getElementById('filterBtn').disabled = false;
                document.getElementById('reportBtn').disabled = false;
                document.getElementById('clearBtn').disabled = false;
                
                // Show geometry generator section
                document.getElementById('geometryGeneratorSection').style.display = 'block';
            }
            
            function getDxfColor(colorIndex) {
                const colors = {
                    0: '#000000', 1: '#FF0000', 2: '#FFFF00', 3: '#00FF00',
                    4: '#00FFFF', 5: '#0000FF', 6: '#FF00FF', 7: '#FFFFFF',
                    8: '#808080', 9: '#C0C0C0'
                };
                return colors[colorIndex] || '#999999';
            }
            
            function updateStats() {
                const stats = document.getElementById('layerStats');
                const total = document.getElementById('layersContainer').children.length;
                const checked = selectedLayers.size;
                stats.textContent = `Selected layers: ${checked} of ${total}`;
            }
            
            async function filterLayers() {
                if (!currentFileId || selectedLayers.size === 0) {
                    showStatus('Please select at least one layer!', 'error');
                    return;
                }
                
                showLoading(true);
                
                try {
                    const response = await fetch('/api/filter-layers', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            file_id: currentFileId,
                            selected_layers: Array.from(selectedLayers)
                        })
                    });
                    
                    if (!response.ok) throw new Error('Filter error');
                    
                    const data = await response.json();
                    showStatus(data.message, 'success');
                    
                    // Descarcă fișierul
                    window.location.href = `/api/download/${data.file_id}`;
                    
                } catch (error) {
                    showStatus(`Eroare: ${error.message}`, 'error');
                } finally {
                    showLoading(false);
                }
            }
            
            function clearAll() {
                currentFileId = null;
                selectedLayers.clear();
                fileInput.value = '';
                document.getElementById('githubUrl').value = '';
                document.getElementById('layersContainer').classList.remove('show');
                document.getElementById('layerStats').style.display = 'none';
                document.getElementById('reportSection').style.display = 'none';
                document.getElementById('filterBtn').disabled = true;
                document.getElementById('reportBtn').disabled = true;
                document.getElementById('clearBtn').disabled = true;
                showStatus('Cleared successfully!', 'info');
            }
            
            async function generateReport() {
                if (!currentFileId || selectedLayers.size === 0) {
                    showStatus('Please select at least one layer!', 'error');
                    return;
                }
                
                const unit = document.getElementById('unitSelect').value;
                showLoading(true);
                
                try {
                    const response = await fetch('/api/generate-report', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            file_id: currentFileId,
                            selected_layers: Array.from(selectedLayers),
                            unit: unit
                        })
                    });
                    
                    if (!response.ok) throw new Error('Report generation error');
                    
                    const data = await response.json();
                    currentReportData = data;
                    
                    // Store RAW layer data for calculator (in mm, unconverted)
                    layerDataCache = {};
                    data.report.forEach(layer => {
                        layerDataCache[layer.layer] = {
                            total_length: layer.raw_total_length,
                            total_area: layer.raw_total_area,
                            max_length: layer.raw_max_length,
                            max_area: layer.raw_max_area
                        };
                    });
                    
                    displayReport(data.report, data.unit);
                    showCalculator();
                    showStatus('Report generated successfully!', 'success');
                    
                } catch (error) {
                    showStatus(`Error: ${error.message}`, 'error');
                } finally {
                    showLoading(false);
                }
            }
            
            function displayReport(report, unit) {
                const container = document.getElementById('reportContainer');
                const section = document.getElementById('reportSection');
                
                if (!report || report.length === 0) {
                    container.innerHTML = '<p style="color: #666;">No data to display</p>';
                    section.style.display = 'block';
                    return;
                }
                
                const lengthUnit = unit || 'm';
                const areaUnit = unit === 'mm' ? 'mm²' : unit === 'cm' ? 'cm²' : 'm²';
                
                let tableHTML = `
                    <table class="report-table">
                        <thead>
                            <tr>
                                <th>Layer</th>
                                <th>Entities</th>
                                <th>Total Length (${lengthUnit})</th>
                                <th>Max Length (${lengthUnit})</th>
                                <th>Total Area (${areaUnit})</th>
                                <th>Max Area (${areaUnit})</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                report.forEach(row => {
                    tableHTML += `
                        <tr>
                            <td>${row.layer}</td>
                            <td class="number-cell">${row.entity_count}</td>
                            <td class="number-cell">${row.total_length.toFixed(3)}</td>
                            <td class="number-cell">${row.max_length.toFixed(3)}</td>
                            <td class="number-cell">${row.total_area.toFixed(3)}</td>
                            <td class="number-cell">${row.max_area.toFixed(3)}</td>
                        </tr>
                    `;
                });
                
                tableHTML += `
                        </tbody>
                    </table>
                `;
                
                container.innerHTML = tableHTML;
                section.style.display = 'block';
                
                // Scroll to report
                section.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
            
            function showCalculator() {
                const section = document.getElementById('calculatorSection');
                section.style.display = 'block';
                
                // Clear existing rows
                document.getElementById('calculatorRows').innerHTML = '';
                calculatorRowId = 0;
                
                // Add first row by default
                addCalculatorRow();
            }
            
            // ===== 3D GEOMETRY GENERATOR FUNCTIONS =====
            
            function addGeometryRow() {
                const container = document.getElementById('geometryRows');
                const rowId = geometryRowId++;
                
                const availableLayers = Array.from(selectedLayers);
                
                let layerOptions = '<option value="">-- Select Layer --</option>' + 
                    availableLayers.map(layer => `<option value="${layer}">${layer}</option>`).join('');
                
                const row = document.createElement('div');
                row.className = 'calculator-row';
                row.id = `geom-row-${rowId}`;
                row.innerHTML = `
                    <div style="flex: 1;">
                        <label style="display: block; font-size: 12px; color: #666; margin-bottom: 4px;">Operation Name</label>
                        <input type="text" id="geom-name-${rowId}" value="Extrusion ${rowId + 1}" placeholder="e.g., Walls, Foundation"
                               style="width: 100%; padding: 8px; border: 1px solid #e0e0e0; border-radius: 4px;">
                    </div>
                    <div style="flex: 0.5;">
                        <label style="display: block; font-size: 12px; color: #666; margin-bottom: 4px;">Color</label>
                        <input type="color" id="geom-color-${rowId}" value="#4CAF50" 
                               style="width: 100%; height: 38px; border: 1px solid #e0e0e0; border-radius: 4px; cursor: pointer;">
                    </div>
                    <div style="flex: 1;">
                        <label style="display: block; font-size: 12px; color: #666; margin-bottom: 4px;">Contour Layer</label>
                        <select id="geom-contour-${rowId}" style="width: 100%; padding: 8px; border: 1px solid #e0e0e0; border-radius: 4px;">
                            ${layerOptions}
                        </select>
                    </div>
                    <div style="flex: 1;">
                        <label style="display: block; font-size: 12px; color: #666; margin-bottom: 4px;">Cut Layer (Optional)</label>
                        <select id="geom-cut-${rowId}" style="width: 100%; padding: 8px; border: 1px solid #e0e0e0; border-radius: 4px;">
                            <option value="">-- No Cuts --</option>
                            ${layerOptions}
                        </select>
                    </div>
                    <div style="flex: 0.8;">
                        <label style="display: block; font-size: 12px; color: #666; margin-bottom: 4px;">Z Offset (mm)</label>
                        <input type="number" id="geom-offset-${rowId}" value="0" step="0.1" 
                               style="width: 100%; padding: 8px; border: 1px solid #e0e0e0; border-radius: 4px;">
                    </div>
                    <div style="flex: 0.8;">
                        <label style="display: block; font-size: 12px; color: #666; margin-bottom: 4px;">Height (mm)</label>
                        <input type="number" id="geom-height-${rowId}" value="100" step="0.1" min="0.1"
                               style="width: 100%; padding: 8px; border: 1px solid #e0e0e0; border-radius: 4px;">
                    </div>
                    <button class="remove-calc-btn" onclick="removeGeometryRow(${rowId})" title="Remove">✕</button>
                `;
                
                container.appendChild(row);
                
                // Show the section
                document.getElementById('geometryGeneratorSection').style.display = 'block';
            }
            
            function removeGeometryRow(rowId) {
                const row = document.getElementById(`geom-row-${rowId}`);
                if (row) {
                    row.remove();
                }
                
                // Hide section if no rows
                const container = document.getElementById('geometryRows');
                if (container.children.length === 0) {
                    document.getElementById('geometryGeneratorSection').style.display = 'none';
                }
            }
            
            async function generateGeometry() {
                const container = document.getElementById('geometryRows');
                if (container.children.length === 0) {
                    showStatus('Please add at least one extrusion first!', 'error');
                    return;
                }
                
                if (!currentFileId) {
                    showStatus('Please upload a file first!', 'error');
                    return;
                }
                
                // Collect all extrusion configurations
                const extrusions = [];
                for (let i = 0; i < container.children.length; i++) {
                    const row = container.children[i];
                    const rowId = row.id.split('-')[2];
                    
                    const operationName = document.getElementById(`geom-name-${rowId}`).value || `Extrusion ${i + 1}`;
                    const operationColor = document.getElementById(`geom-color-${rowId}`).value || '#4CAF50';
                    const contourLayer = document.getElementById(`geom-contour-${rowId}`).value;
                    const cutLayer = document.getElementById(`geom-cut-${rowId}`).value;
                    const zOffset = parseFloat(document.getElementById(`geom-offset-${rowId}`).value) || 0;
                    const height = parseFloat(document.getElementById(`geom-height-${rowId}`).value) || 100;
                    
                    if (!contourLayer) {
                        showStatus(`Row ${i + 1}: Please select a contour layer!`, 'error');
                        return;
                    }
                    
                    if (height <= 0) {
                        showStatus(`Row ${i + 1}: Height must be greater than 0!`, 'error');
                        return;
                    }
                    
                    extrusions.push({
                        operation_name: operationName,
                        operation_color: operationColor,
                        contour_layer: contourLayer,
                        cut_layer: cutLayer || null,
                        z_offset: zOffset,
                        height: height
                    });
                }
                
                showLoading(true);
                
                try {
                    const response = await fetch('/api/generate-3d-geometry', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            file_id: currentFileId,
                            extrusions: extrusions
                        })
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({}));
                        const errorMessage = errorData.detail || 'Failed to generate geometry';
                        throw new Error(errorMessage);
                    }
                    
                    const data = await response.json();
                    
                    // Show viewer section and render
                    document.getElementById('viewerSection').style.display = 'block';
                    render3DGeometry(data.geometries);
                    showStatus(`Generated ${data.geometries.length} 3D solid(s) successfully!`, 'success');
                    
                } catch (error) {
                    console.error('Error generating geometry:', error);
                    showStatus(`Error: ${error.message}`, 'error');
                } finally {
                    showLoading(false);
                }
            }
            
            function render3DGeometry(geometries) {
                console.log('🎲 Rendering 3D geometry:', geometries.length, 'solids');
                
                const traces = [];
                const volumesByOperation = {};  // Group volumes by operation name
                
                geometries.forEach((geom, idx) => {
                    // Use operation color
                    const color = geom.operation_color || '#4CAF50';
                    
                    // Create mesh3d trace for the solid
                    const solidName = geom.contour_index !== undefined ? 
                        `${geom.operation_name} #${geom.contour_index + 1}` : 
                        geom.operation_name;
                    
                    traces.push({
                        type: 'mesh3d',
                        x: geom.vertices.map(v => v[0]),
                        y: geom.vertices.map(v => v[1]),
                        z: geom.vertices.map(v => v[2]),
                        i: geom.faces.map(f => f[0]),
                        j: geom.faces.map(f => f[1]),
                        k: geom.faces.map(f => f[2]),
                        color: color,
                        opacity: 0.8,
                        flatshading: true,
                        hoverinfo: 'text',
                        text: `${solidName}<br>Volume: ${(geom.volume / 1000).toFixed(2)} cm³<br>Height: ${geom.height}mm<br>Z offset: ${geom.z_offset}mm`,
                        showlegend: true,
                        name: solidName
                    });
                    
                    // Accumulate volume by operation name
                    if (!volumesByOperation[geom.operation_name]) {
                        volumesByOperation[geom.operation_name] = {
                            volume: 0,
                            color: geom.operation_color,
                            count: 0
                        };
                    }
                    volumesByOperation[geom.operation_name].volume += geom.volume;
                    volumesByOperation[geom.operation_name].count++;
                });
                
                const layout = {
                    title: `3D Extruded Geometry - ${geometries.length} solid(s)`,
                    scene: {
                        xaxis: { title: 'X (mm)', showbackground: true, backgroundcolor: 'rgb(230, 230, 230)' },
                        yaxis: { title: 'Y (mm)', showbackground: true, backgroundcolor: 'rgb(230, 230, 230)' },
                        zaxis: { title: 'Z (mm)', showbackground: true, backgroundcolor: 'rgb(230, 230, 230)' },
                        aspectmode: 'data',
                        camera: {
                            eye: { x: 1.5, y: 1.5, z: 1.5 }
                        }
                    },
                    margin: { l: 0, r: 0, t: 40, b: 0 },
                    hovermode: 'closest'
                };
                
                const config = {
                    responsive: true,
                    displayModeBar: true,
                    displaylogo: false
                };
                
                Plotly.newPlot('viewerContainer', traces, layout, config);
                console.log('✅ 3D geometry rendered successfully');
                
                // Generate volume pie chart
                generateVolumeChart(volumesByOperation);
            }
            
            function generateVolumeChart(volumesByOperation) {
                const operations = Object.keys(volumesByOperation);
                
                if (operations.length === 0) return;
                
                const values = operations.map(name => volumesByOperation[name].volume / 1000000); // Convert mm³ to cm³
                const colors = operations.map(name => volumesByOperation[name].color);
                const labels = operations.map(name => {
                    const data = volumesByOperation[name];
                    return `${name} (${data.count} solid${data.count > 1 ? 's' : ''})`;
                });
                
                const trace = {
                    type: 'pie',
                    labels: labels,
                    values: values,
                    marker: {
                        colors: colors
                    },
                    texttemplate: '%{label}<br>%{value:.2f} cm³<br>%{percent}',
                    hovertemplate: '<b>%{label}</b><br>Volume: %{value:.2f} cm³<br>%{percent}<extra></extra>'
                };
                
                const layout = {
                    title: 'Volume Distribution by Operation',
                    showlegend: true,
                    height: 400
                };
                
                const config = {
                    responsive: true,
                    displayModeBar: true,
                    displaylogo: false
                };
                
                document.getElementById('volumeAnalysisSection').style.display = 'block';
                Plotly.newPlot('volumeChartContainer', [trace], layout, config);
                console.log('📊 Volume chart generated');
            }
            
            // ===== CALCULATOR FUNCTIONS =====
            
            function addCalculatorRow() {
                const container = document.getElementById('calculatorRows');
                const rowId = calculatorRowId++;
                
                const availableLayers = Array.from(selectedLayers);
                
                let layerOptions = availableLayers.map(layer => 
                    `<option value="${layer}">${layer}</option>`
                ).join('');
                
                const rowHTML = `
                    <div class="calculator-row" id="calcRow${rowId}">
                        <select class="layer-select" onchange="calculateRow(${rowId})">
                            <option value="">Select Layer</option>
                            ${layerOptions}
                        </select>
                        <select class="operator-select" onchange="calculateRow(${rowId})">
                            <option value="+">+</option>
                            <option value="-">-</option>
                            <option value="*">×</option>
                            <option value="/">/</option>
                        </select>
                        <select class="layer-select" onchange="calculateRow(${rowId})">
                            <option value="">Select Layer</option>
                            ${layerOptions}
                        </select>
                        <input type="text" class="result-input" readonly placeholder="Result">
                        <button class="remove-btn" onclick="removeCalculatorRow(${rowId})" title="Remove">×</button>
                    </div>
                `;
                
                container.insertAdjacentHTML('beforeend', rowHTML);
            }
            
            function removeCalculatorRow(rowId) {
                const row = document.getElementById(`calcRow${rowId}`);
                if (row) {
                    row.remove();
                }
            }
            
            function calculateRow(rowId) {
                const row = document.getElementById(`calcRow${rowId}`);
                if (!row) return;
                
                const selects = row.querySelectorAll('.layer-select');
                const operator = row.querySelector('.operator-select').value;
                const resultInput = row.querySelector('.result-input');
                
                const layer1 = selects[0].value;
                const layer2 = selects[1].value;
                
                if (!layer1 || !layer2) {
                    resultInput.value = '';
                    return;
                }
                
                const propertyType = document.getElementById('calcPropertyType').value;
                const unit = document.getElementById('calcUnit').value;
                
                // Get converted values
                const value1 = getLayerValue(layer1, propertyType, unit);
                const value2 = getLayerValue(layer2, propertyType, unit);
                
                let result = 0;
                switch(operator) {
                    case '+':
                        result = value1 + value2;
                        break;
                    case '-':
                        result = value1 - value2;
                        break;
                    case '*':
                        result = value1 * value2;
                        break;
                    case '/':
                        result = value2 !== 0 ? value1 / value2 : 0;
                        break;
                }
                
                resultInput.value = result.toFixed(3);
            }
            
            function getLayerValue(layerName, propertyType, unit) {
                if (!layerDataCache[layerName]) return 0;
                
                const unitFactors = {
                    "mm": {"length": 1, "area": 1},
                    "cm": {"length": 0.1, "area": 0.01},
                    "m": {"length": 0.001, "area": 0.000001}
                };
                
                const factor = unitFactors[unit] || unitFactors["mm"];
                const data = layerDataCache[layerName];
                
                if (propertyType === 'length') {
                    return data.total_length * factor.length;
                } else {
                    return data.total_area * factor.area;
                }
            }
            
            function updateAllCalculations() {
                const rows = document.querySelectorAll('.calculator-row');
                rows.forEach(row => {
                    const rowId = parseInt(row.id.replace('calcRow', ''));
                    calculateRow(rowId);
                });
            }
            
            // ===== PLOTLY 3D VIEWER FUNCTIONS =====
            
            async function reloadViewer() {
                console.log('🔄 Loading 3D viewer...');
                console.log('Selected layers:', Array.from(selectedLayers));
                console.log('Current file ID:', currentFileId);
                
                if (selectedLayers.size === 0) {
                    showStatus('Please select at least one layer first!', 'error');
                    return;
                }
                
                if (!currentFileId) {
                    showStatus('Please upload a file first!', 'error');
                    return;
                }
                
                try {
                    // Show the viewer section
                    document.getElementById('viewerSection').style.display = 'block';
                    
                    // Fetch entities
                    const response = await fetch('/api/get-entities', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            file_id: currentFileId,
                            selected_layers: Array.from(selectedLayers)
                        })
                    });
                    
                    const data = await response.json();
                    console.log('📦 Received entities:', data.entities.length);
                    
                    if (!data.entities || data.entities.length === 0) {
                        showStatus('No entities found in selected layers', 'error');
                        return;
                    }
                    
                    // Render with Plotly
                    renderPlotly(data.entities);
                    showStatus('3D view loaded successfully!', 'success');
                    
                } catch (error) {
                    console.error('❌ Error loading viewer:', error);
                    showStatus(`Error: ${error.message}`, 'error');
                }
            }
            
            function renderPlotly(entities) {
                console.log('🎨 Rendering with Plotly:', entities.length, 'entities');
                
                const traces = [];
                
                entities.forEach((entity, idx) => {
                    // Use custom color if set, otherwise use entity layer color from layerColors
                    const color = layerColors[entity.layer] || '#999999';
                    
                    if (entity.type === 'LINE') {
                        traces.push({
                            type: 'scatter3d',
                            mode: 'lines',
                            x: [entity.start[0], entity.end[0]],
                            y: [entity.start[1], entity.end[1]],
                            z: [entity.start[2], entity.end[2]],
                            line: { color: color, width: 3 },
                            hoverinfo: 'text',
                            text: `LINE on layer: ${entity.layer}`,
                            showlegend: false
                        });
                    }
                    else if (entity.type === 'LWPOLYLINE' || entity.type === 'POLYLINE') {
                        const x = entity.points.map(p => p[0]);
                        const y = entity.points.map(p => p[1]);
                        const z = entity.points.map(p => p[2]);
                        
                        if (entity.closed && entity.points.length > 0) {
                            x.push(entity.points[0][0]);
                            y.push(entity.points[0][1]);
                            z.push(entity.points[0][2]);
                        }
                        
                        traces.push({
                            type: 'scatter3d',
                            mode: 'lines',
                            x: x,
                            y: y,
                            z: z,
                            line: { color: color, width: 3 },
                            hoverinfo: 'text',
                            text: `${entity.type} on layer: ${entity.layer}`,
                            showlegend: false
                        });
                    }
                    else if (entity.type === 'CIRCLE') {
                        const segments = 32;
                        const x = [], y = [], z = [];
                        
                        for (let i = 0; i <= segments; i++) {
                            const angle = (i / segments) * 2 * Math.PI;
                            x.push(entity.center[0] + entity.radius * Math.cos(angle));
                            y.push(entity.center[1] + entity.radius * Math.sin(angle));
                            z.push(entity.center[2]);
                        }
                        
                        traces.push({
                            type: 'scatter3d',
                            mode: 'lines',
                            x: x,
                            y: y,
                            z: z,
                            line: { color: color, width: 3 },
                            hoverinfo: 'text',
                            text: `CIRCLE (r=${entity.radius.toFixed(1)}) on layer: ${entity.layer}`,
                            showlegend: false
                        });
                    }
                    else if (entity.type === 'ARC') {
                        const segments = 32;
                        const x = [], y = [], z = [];
                        let startAngle = entity.start_angle * Math.PI / 180;
                        let endAngle = entity.end_angle * Math.PI / 180;
                        
                        if (endAngle < startAngle) endAngle += 2 * Math.PI;
                        
                        for (let i = 0; i <= segments; i++) {
                            const angle = startAngle + (i / segments) * (endAngle - startAngle);
                            x.push(entity.center[0] + entity.radius * Math.cos(angle));
                            y.push(entity.center[1] + entity.radius * Math.sin(angle));
                            z.push(entity.center[2]);
                        }
                        
                        traces.push({
                            type: 'scatter3d',
                            mode: 'lines',
                            x: x,
                            y: y,
                            z: z,
                            line: { color: color, width: 3 },
                            hoverinfo: 'text',
                            text: `ARC on layer: ${entity.layer}`,
                            showlegend: false
                        });
                    }
                });
                
                console.log('✅ Created', traces.length, 'traces');
                
                const layout = {
                    title: `DXF 3D View - ${entities.length} entities from ${selectedLayers.size} layer(s)`,
                    scene: {
                        xaxis: { title: 'X', showbackground: true, backgroundcolor: 'rgb(245, 245, 245)' },
                        yaxis: { title: 'Y', showbackground: true, backgroundcolor: 'rgb(245, 245, 245)' },
                        zaxis: { title: 'Z', showbackground: true, backgroundcolor: 'rgb(245, 245, 245)' },
                        aspectmode: 'data',
                        camera: {
                            eye: { x: 1.5, y: 1.5, z: 1.5 }
                        }
                    },
                    margin: { l: 0, r: 0, t: 40, b: 0 },
                    hovermode: 'closest'
                };
                
                const config = {
                    responsive: true,
                    displayModeBar: true,
                    displaylogo: false
                };
                
                Plotly.newPlot('viewerContainer', traces, layout, config);
                console.log('🎬 Plotly rendered successfully');
            }
            
            // Camera view functions for Plotly
            function setCameraView(eye) {
                const update = {
                    'scene.camera.eye': eye
                };
                Plotly.relayout('viewerContainer', update);
            }
            
            function setViewTop() {
                setCameraView({ x: 0, y: 0, z: 2.5 });
            }
            
            function setViewBottom() {
                setCameraView({ x: 0, y: 0, z: -2.5 });
            }
            
            function setViewFront() {
                setCameraView({ x: 0, y: -2.5, z: 0 });
            }
            
            function setViewBack() {
                setCameraView({ x: 0, y: 2.5, z: 0 });
            }
            
            function setViewLeft() {
                setCameraView({ x: -2.5, y: 0, z: 0 });
            }
            
            function setViewRight() {
                setCameraView({ x: 2.5, y: 0, z: 0 });
            }
            
            function setViewIsometric() {
                setCameraView({ x: 1.5, y: 1.5, z: 1.5 });
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    print("🚀 DXF Layer Filter application starting on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
