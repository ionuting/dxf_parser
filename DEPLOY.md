# Ghid Deploy Gratuit - DXF Filter App

## Opțiunea 1: Render.com (Recomandat)

### Pregătire:
1. ✅ Fișierele necesare sunt gata:
   - `requirements.txt` - dependențe Python
   - `Procfile` - comandă de pornire
   - `render.yaml` - configurare automată
   - `.gitignore` - exclude fișiere temporare

### Pași Deploy:

1. **Creează repository GitHub:**
   ```bash
   cd C:\Users\ionut.ciuntuc\Downloads\Index\dxf-filter-app
   git init
   git add .
   git commit -m "Initial commit - DXF Filter App"
   ```

2. **Push pe GitHub:**
   - Creează un repository nou pe https://github.com/new
   - Numele sugerat: `dxf-filter-app`
   - Repository public sau privat (ambele funcționează)
   
   ```bash
   git remote add origin https://github.com/USERNAME/dxf-filter-app.git
   git branch -M main
   git push -u origin main
   ```

3. **Deploy pe Render:**
   - Mergi pe https://render.com și creează cont (sau login cu GitHub)
   - Click **"New +"** → **"Web Service"**
   - Conectează repository-ul GitHub
   - Render va detecta automat `render.yaml` și va configura totul
   - Click **"Create Web Service"**
   - Așteaptă 2-3 minute pentru build

4. **Gata!** Aplicația va fi live la `https://dxf-filter-app-xxxxx.onrender.com`

### Important despre Free Tier:
- ⚠️ Aplicația "doarme" după 15 minute de inactivitate
- Prima încărcare după somn durează ~30-50 secunde
- 750 ore gratuite/lună (suficient pentru testing)
- Fișierele temporare se șterg la restart (normal)

---

## Opțiunea 2: Railway.app

### Pași Deploy:

1. **Pregătire același cod (deja făcut)**

2. **Deploy pe Railway:**
   - Mergi pe https://railway.app și login cu GitHub
   - Click **"New Project"** → **"Deploy from GitHub repo"**
   - Selectează repository-ul
   - Railway detectează automat Python și FastAPI
   - Deploy se face automat

3. **Setări (dacă nu detectează automat):**
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Python Version: 3.11

4. **Obține URL:**
   - Settings → Generate Domain
   - Aplicația va fi live la `https://your-app.up.railway.app`

### Avantaje Railway:
- ✅ Mai rapid decât Render
- ✅ $5 credit gratuit/lună
- ✅ Nu "doarme" atât de des
- ⚠️ După ce termini creditul, trebuie să adaugi card (nu se taxează automat)

---

## Opțiunea 3: Fly.io

### Instalare CLI:
```powershell
# Windows
iwr https://fly.io/install.ps1 -useb | iex
```

### Deploy:
```bash
cd C:\Users\ionut.ciuntuc\Downloads\Index\dxf-filter-app
fly launch --name dxf-filter-app
fly deploy
```

Fly va crea automat `fly.toml` și va face deploy.

### Avantaje Fly.io:
- ✅ Mai multe resurse gratuite decât Render
- ✅ Nu "doarme"
- ✅ Mai aproape de Europa (latență mai mică)
- ⚠️ Mai tehnic de configurat

---

## Troubleshooting

### Eroare: "Port already in use"
Render/Railway setează automat portul prin variabila `$PORT`. Codul din `main.py` este deja pregătit.

### Aplicația nu pornește
Verifică logs în dashboard-ul platformei. Cele mai comune probleme:
- Lipsește o dependență în `requirements.txt`
- Python version mismatch (specifică 3.11 în setări)

### Fișierele încărcate dispar
Normal pe platformele gratuite - folosesc storage efemer. La restart, tot din `temp_files/` se șterge.

---

## Recomandare Finală

**Pentru demonstrație/testing**: Render.com
- Cel mai ușor
- Zero configurare
- Perfect pentru showcase

**Pentru uz real/frecvent**: Railway sau Fly.io
- Mai performant
- Mai puțin downtime
- Mai multe resurse

---

## Link-uri Utile

- Render: https://render.com
- Railway: https://railway.app
- Fly.io: https://fly.io
- GitHub: https://github.com

## Support

Dacă întâmpini probleme, verifică:
1. Logs în dashboard-ul platformei
2. Branch-ul GitHub este actualizat
3. Toate fișierele sunt commit-ate și push-ate
