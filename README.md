# DXF Layer Filter - Aplicație FastAPI

O aplicație web rapidă pentru filtrarea layerelor din fișiere DXF.

## Funcționalități

✅ **Încărcarea fișierelor DXF** de pe calculator (drag & drop)
✅ **Descărcare din GitHub** raw URLs
✅ **Vizualizarea layerelor** cu culori
✅ **Selectare layere** cu checkboxuri
✅ **Export fișier filtrat** doar cu layerele selectate

## Instalare

### 1. Clonează sau copiază fișierele
```bash
cd dxf-filter-app
```

### 2. Instalează dependențele
```bash
pip install -r requirements.txt
```

### 3. Pornește aplicația
```bash
python main.py
```

Aplicația va fi disponibilă la: **http://localhost:8000**

## Utilizare

1. **Încarcă un fișier DXF**:
   - Trage și plasează fișierul pe zona albastră
   - Sau apasă butonul "Selectează fișier"
   - Sau incarcă din GitHub (URL raw)

2. **Selectează layerele**:
   - Bifează layerele pe care le dorești
   - Vezi statisticile în timp real

3. **Descarcă**:
   - Apasă "Descarcă fișierul filtrat"
   - Se va crea un nou fișier DXF doar cu layerele selectate

## Structură Proiect

```
dxf-filter-app/
├── main.py           # Backend FastAPI
├── requirements.txt  # Dependențe Python
└── README.md         # Documentație
```

## Exemple GitHub URLs

```
https://raw.githubusercontent.com/user/repo/main/file.dxf
https://github.com/user/repo/blob/main/file.dxf (convertat automat)
```

## Tehnologii

- **FastAPI** - Framework web
- **ezdxf** - Manipulare fișiere DXF
- **HTML5/CSS3/JS** - Frontend

## Troubleshooting

- **"Module not found"** → Rulează `pip install -r requirements.txt`
- **Port 8000 ocupat** → Modifică portul în `main.py`
- **Fișier corupt** → Asigură-te că e fișier DXF valid

## Note

- Fișierele sunt ținute în memorie (RAM)
- Pentru aplicații mari, consideră stocarea pe disk
- Fișierele temporare se șterg automat
