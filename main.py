
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

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# Directoare pentru fișiere temporare
TEMP_DIR = Path("temp_files")
TEMP_DIR.mkdir(exist_ok=True)

# Stochează fișierele DXF încărcate în sesiune (în memorie)
loaded_files = {}

def analyze_entities_by_layer(doc):
    """Analizează entitățile și returnează statistici pe layer"""
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
            
            # Mapare tipuri DXF la termeni mai clari
            type_mapping = {
                "LINE": "Linie",
                "LWPOLYLINE": "Polilinie",
                "POLYLINE": "Polilinie",
                "ARC": "Arc",
                "CIRCLE": "Cerc",
                "ELLIPSE": "Elipsă",
                "SPLINE": "Curbă",
                "TEXT": "Text",
                "MTEXT": "Text multiplu",
                "INSERT": "Bloc",
                "HATCH": "Hașură",
                "DIMENSION": "Cotă",
                "POINT": "Punct"
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
    """Încarcă un fișier DXF și extrage layerele"""
    try:
        logger.info(f"Uploading file: {file.filename}")
        contents = await file.read()
        logger.info(f"File size: {len(contents)} bytes")
        
        # Salvează temporar fișierul pentru ezdxf
        temp_file = TEMP_DIR / f"temp_{uuid.uuid4()}.dxf"
        with open(temp_file, 'wb') as f:
            f.write(contents)
        
        # Citește cu ezdxf
        doc = ezdxf.readfile(str(temp_file))
        
        # Șterge fișierul temporar
        temp_file.unlink()
        
        # Analizează entitățile pe layere
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
    """Încarcă un fișierul DXF din GitHub raw"""
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
        
        # Salvează temporar fișierul
        temp_file = TEMP_DIR / f"temp_{uuid.uuid4()}.dxf"
        with open(temp_file, 'wb') as f:
            f.write(contents)
        
        # Citește cu ezdxf
        doc = ezdxf.readfile(str(temp_file))
        
        # Șterge fișierul temporar
        temp_file.unlink()
        
        # Analizează entitățile pe layere
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
    """Creează un nou fișier DXF doar cu layerele selectate"""
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
            "message": f"Fișier creat cu {len(selected_layers)} layere și {entity_count} obiecte"
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

def get_html_interface():
    return """
    <!DOCTYPE html>
    <html lang="ro">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DXF Layer Filter</title>
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
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎨 DXF Layer Filter</h1>
                <p>Încarcă, selectează layerele și descarcă fișierul filtrat</p>
            </div>
            
            <div class="content">
                <!-- Status Messages -->
                <div id="statusMessage" class="status-message"></div>
                
                <!-- Upload Section -->
                <div class="section">
                    <div class="section-title">1. Încarcă fișierul DXF</div>
                    
                    <div class="input-group">
                        <div class="upload-area" id="uploadArea">
                            <p>Trage și plasează fișierul DXF aici sau</p>
                            <input type="file" id="fileInput" accept=".dxf" style="display: none;">
                            <button class="btn-primary" onclick="document.getElementById('fileInput').click()" style="width: 150px; margin-top: 10px;">
                                Selectează fișier
                            </button>
                        </div>
                    </div>
                    
                    <div style="text-align: center; margin: 15px 0; color: #999;">SAU</div>
                    
                    <div class="input-group">
                        <input type="text" id="githubUrl" placeholder="https://raw.githubusercontent.com/.../*.dxf">
                        <button class="btn-primary" onclick="uploadFromGithub()">Încarcă din GitHub</button>
                    </div>
                </div>
                
                <!-- Loading Indicator -->
                <div id="loading" class="loading">
                    <span class="spinner"></span> Se procesează...
                </div>
                
                <!-- Layers Section -->
                <div class="section">
                    <div class="section-title">2. Selectează layerele</div>
                    <div id="layersContainer" class="layers-container"></div>
                    <div id="layerStats" class="layer-stats" style="display: none;"></div>
                </div>
                
                <!-- Action Buttons -->
                <div class="action-buttons">
                    <button class="btn-primary" id="filterBtn" onclick="filterLayers()" disabled>
                        Descarcă fișierul filtrat
                    </button>
                    <button class="btn-secondary" id="clearBtn" onclick="clearAll()" disabled>
                        Șterge și reîncarcă
                    </button>
                </div>
            </div>
        </div>
        
        <script>
            let currentFileId = null;
            let selectedLayers = new Set();
            
            // Drag and drop
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            
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
                    showStatus('Selectează un fișier DXF valid!', 'error');
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
                    
                    if (!response.ok) throw new Error('Eroare la upload');
                    
                    const data = await response.json();
                    currentFileId = data.file_id;
                    displayLayers(data.layers);
                    showStatus(`Fișierul încărcat cu succes! ${data.layer_count} layere găsite.`, 'success');
                    
                } catch (error) {
                    showStatus(`Eroare: ${error.message}`, 'error');
                } finally {
                    showLoading(false);
                }
            }
            
            async function uploadFromGithub() {
                const url = document.getElementById('githubUrl').value;
                if (!url) {
                    showStatus('Introduceți o adresă URL valida!', 'error');
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
                    
                    if (!response.ok) throw new Error('Eroare la descărcare');
                    
                    const data = await response.json();
                    currentFileId = data.file_id;
                    displayLayers(data.layers);
                    showStatus(`Fișierul din GitHub încărcat! ${data.layer_count} layere.`, 'success');
                    
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
                    infoSpan.textContent = `${layer.count} elemente: ${layer.types}`;
                    
                    nameDiv.appendChild(nameSpan);
                    nameDiv.appendChild(infoSpan);
                    
                    label.appendChild(checkbox);
                    label.appendChild(colorDiv);
                    label.appendChild(nameDiv);
                    
                    item.appendChild(label);
                    container.appendChild(item);
                });
                
                container.classList.add('show');
                document.getElementById('layerStats').style.display = 'block';
                updateStats();
                
                document.getElementById('filterBtn').disabled = false;
                document.getElementById('clearBtn').disabled = false;
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
                stats.textContent = `Layere selectate: ${checked} din ${total}`;
            }
            
            async function filterLayers() {
                if (!currentFileId || selectedLayers.size === 0) {
                    showStatus('Selectează cel puțin un layer!', 'error');
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
                    
                    if (!response.ok) throw new Error('Eroare la filtrare');
                    
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
                document.getElementById('filterBtn').disabled = true;
                document.getElementById('clearBtn').disabled = true;
                showStatus('Ștergere completă!', 'info');
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    print("🚀 Aplicație DXF Layer Filter pornind pe http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
