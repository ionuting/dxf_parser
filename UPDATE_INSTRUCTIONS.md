# Cum să actualizezi requirements.txt pe GitHub și Render.com

## Pas 1: Actualizează fișierul pe GitHub

### Opțiunea A - Prin GitHub Web Interface (fără git local):

1. Mergi pe https://github.com/YOUR_USERNAME/YOUR_REPO
2. Click pe fișierul `requirements.txt`
3. Click pe butonul ✏️ (Edit this file)
4. Modifică linia:
   ```
   DE LA: triangle==20230923
   LA:     triangle==20250106
   ```
5. Scroll jos și click pe **"Commit changes"**
6. Adaugă mesaj: "Update triangle version to 20250106"
7. Click **"Commit changes"**

### Opțiunea B - Prin VS Code Source Control:

1. În VS Code, click pe iconița "Source Control" (branching icon) din stânga
2. Vei vedea `requirements.txt` în lista "Changes"
3. Click pe `+` (Stage Changes) lângă requirements.txt
4. Scrie commit message: "Update triangle version"
5. Click ✓ (Commit)
6. Click pe "..." → "Push"

## Pas 2: Clear cache pe Render.com

După ce fișierul e pe GitHub:

1. Mergi pe https://dashboard.render.com
2. Selectează serviciul tău DXF
3. Click pe **"Manual Deploy"** → **"Clear build cache & deploy"**
4. Așteaptă rebuild-ul (2-3 minute)

✅ Gata! Aplicația va folosi `triangle==20250106`
