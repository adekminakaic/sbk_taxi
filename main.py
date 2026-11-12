from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional
import re
import os
import shutil
import models
from database import get_db
from pdf_generator import kreiraj_pdf_ugovor
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = FastAPI(title="SBK Taxi VIP Platforma", version="2.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload folder za dokumente i ugovore
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

ADMIN_SIFRA = "sbktaxiadmin2026"

# Pomoćne funkcije za validaciju i čišćenje
def ocisti_i_provjeri_tekst(v: str) -> str:
    v = v.strip()
    if len(v) < 3:
        raise ValueError("Unos mora imati više od 3 slova.")
    return v.title()

def provjeri_bh_telefon(v: str) -> str:
    cisti_broj = re.sub(r'[\s\-(\)]', '', v)
    if not re.match(r'^06\d{7,8}$', cisti_broj):
        raise ValueError("Neispravan format broja. Broj mora počinjati sa 06 i imati ispravan broj znamenki (npr. 061123456).")
    return cisti_broj

def provjeri_email(v: str) -> str:
    v = v.strip().lower()
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
        raise ValueError("Neispravan format email adrese.")
    return v

def posalji_email_obavijest(email: str, naslov: str, poruka: str):
    """
    Funkcija za slanje email obavještenja vozaču.
    U produkciji se ovdje povezuje pravi SMTP server (npr. Gmail SMTP).
    Za sada ispisujemo u konzolu da simulisanjem potvrdimo slanje.
    """
    print(f"--- EMAIL POSLAN NA: {email} ---")
    print(f"NASLOV: {naslov}")
    print(f"PORUKA: {poruka}")
    print("-----------------------------------")
    return True


# --- POČETna RUTA ---
@app.get("/")
def pocetna_stranica():
    return {
        "porukaDobrodoslice": "Dobrodošli na SBK Taxi VIP platformu!",
        "izaberiteUlogu": {
            "klijent": "/api/klijent/... (Za naručivanje vožnje i pregled putovanja)",
            "vozac": "/api/vozac/... (Za registraciju i prijem vožnji)"
        }
    }


# --- REGISTRACIJA VOZAČA SA DOKUMENTIMA ---
@app.post("/api/vozac/registracija-sa-dokumentima")
async def registracija_sa_dokumentima(
    puno_ime: str = Form(...),
    telefon: str = Form(...),
    email: str = Form(...),
    vozacka: UploadFile = File(...),
    registracija: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        cisti_ime = ocisti_i_provjeri_tekst(puno_ime)
        cisti_telefon = provjeri_bh_telefon(telefon)
        cisti_email = provjeri_email(email)

        # Provjera da li broj ili email već postoje
        postojeci = db.query(models.DriverModel).filter(
            (models.DriverModel.telefon == cisti_telefon) | (models.DriverModel.email == cisti_email)
        ).first()
        
        if postojeci:
            raise HTTPException(status_code=400, detail="Vozač sa ovim brojem telefona ili email adresom već postoji u bazi.")

        # Spremanje fajlova
        vozacka_filename = f"vozacka_{cisti_telefon}_{vozacka.filename}"
        reg_filename = f"reg_{cisti_telefon}_{registracija.filename}"
        
        vozacka_path = os.path.join(UPLOAD_DIR, vozacka_filename)
        reg_path = os.path.join(UPLOAD_DIR, reg_filename)

        with open(vozacka_path, "wb") as buffer:
            shutil.copyfileobj(vozacka.file, buffer)
        with open(reg_path, "wb") as buffer:
            shutil.copyfileobj(registracija.file, buffer)

        db_vozacka = f"uploads/{vozacka_filename}"
        db_reg = f"uploads/{reg_filename}"

        novi_vozac = models.DriverModel(
            puno_ime=cisti_ime,
            telefon=cisti_telefon,
            email=cisti_email,
            slika_vozacke=db_vozacka,
            slika_registracije=db_reg,
            verifikovan=False,
            status_rada="Offline",
            status_zauzeca="Slobodan"
        )

        db.add(novi_vozac)
        db.commit()
        db.refresh(novi_vozac)

        return {
            "status": "uspjeh",
            "poruka": "Prijava je uspješno poslana! Administrator će pregledati dokumente i obavijestiti vas putem emaila."
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Greška na serveru: {str(e)}")


# --- PRIJAVA VOZAČA (LOGIN) ---
@app.post("/api/vozac/prijava")
def prijava_vozaca(telefon: str = Form(...), db: Session = Depends(get_db)):
    cisti_telefon = provjeri_bh_telefon(telefon)
    vozac = db.query(models.DriverModel).filter(models.DriverModel.telefon == cisti_telefon).first()
    
    if not vozac:
        raise HTTPException(status_code=404, detail="Vozač sa ovim brojem ne postoji.")
    if not vozac.verifikovan:
        raise HTTPException(status_code=403, detail="Vaš nalog još uvijek nije odobren od strane administratora.")

    # Bilježimo vrijeme prijave (login)
    vozac.zadnja_prijava = datetime.utcnow()
    vozac.status_rada = "Aktivan"
    db.commit()

    return {
        "status": "uspjeh",
        "poruka": f"Dobrodošli nazad, {vozac.puno_ime}!",
        "vozac": {
            "id": vozac.id,
            "puno_ime": vozac.puno_ime,
            "telefon": vozac.telefon,
            "email": vozac.email,
            "verifikovan": vozac.verifikovan,
            "stanje_racuna": float(vozac.stanje_racuna) if vozac.stanje_racuna else 0.0
        }
    }


# --- ODJAVA VOZAČA ---
@app.post("/api/vozac/odjava")
def odjava_vozaca(telefon: str = Form(...), db: Session = Depends(get_db)):
    cisti_telefon = provjeri_bh_telefon(telefon)
    vozac = db.query(models.DriverModel).filter(models.DriverModel.telefon == cisti_telefon).first()
    if vozac:
        vozac.zadnja_odjava = datetime.utcnow()
        vozac.status_rada = "Offline"
        db.commit()
    return {"status": "uspjeh", "poruka": "Uspješna odjava."}


# --- AŽURIRANJE STATUSA I LOKACIJE VOZAČA ---
@app.post("/api/vozac/status")
def azuriraj_status_vozaca(podaci: dict, db: Session = Depends(get_db)):
    telefon = podaci.get("telefon")
    status_rada = podaci.get("status_rada")
    status_zauzeca = podaci.get("status_zauzeca")
    trenutna_lokacija = podaci.get("trenutna_lokacija")

    if not telefon:
        raise HTTPException(status_code=400, detail="Nedostaje broj telefona.")
    
    cisti_telefon = provjeri_bh_telefon(telefon)
    vozac = db.query(models.DriverModel).filter(models.DriverModel.telefon == cisti_telefon).first()

    if not vozac or not vozac.verifikovan:
        raise HTTPException(status_code=403, detail="Pristup odbijen ili nalog nije odobren.")

    if status_rada:
        vozac.status_rada = status_rada
        if status_rada == "Aktivan" and not vozac.zadnja_prijava:
            vozac.zadnja_prijava = datetime.utcnow()
        elif status_rada == "Offline":
            vozac.zadnja_odjava = datetime.utcnow()

    if status_zauzeca:
        vozac.status_zauzeca = status_zauzeca

    if trenutna_lokacija:
        vozac.trenutna_lokacija = ocisti_i_provjeri_tekst(trenutna_lokacija)

    db.commit()
    return {"status": "uspjeh", "poruka": "Status i lokacija ažurirani!"}


# --- ADMIN PANEL RUTE ---
@app.get("/api/admin/svi-vozaci")
def admin_svi_vozaci(sifra: str, db: Session = Depends(get_db)):
    if sifra != ADMIN_SIFRA:
        raise HTTPException(status_code=403, detail="Pogrešna admin šifra.")
    vozaci = db.query(models.DriverModel).all()
    return {"vozaci": vozaci}

@app.get("/api/admin/vozaci/za-odobrenje")
def admin_vozaci_na_cekanju(sifra: str, db: Session = Depends(get_db)):
    if sifra != ADMIN_SIFRA:
        raise HTTPException(status_code=403, detail="Pogrešna admin šifra.")
    vozaci = db.query(models.DriverModel).filter(models.DriverModel.verifikovan == False).all()
    
    rezultat = []
    for v in vozaci:
        rezultat.append({
            "id": v.id,
            "puno_ime": v.puno_ime,
            "telefon": v.telefon,
            "email": v.email,
            "slika_vozacke": f"/{v.slika_vozacke}" if v.slika_vozacke else None,
            "slika_registracije": f"/{v.slika_registracije}" if v.slika_registracije else None,
            "kreirano_u": str(v.kreirano_u)
        })
    return {"status": "uspjeh", "broj_zahtjeva": len(rezultat), "vozaci": rezultat}

# --- POSTAVKE ZA SMTP SLANJE EMAILOVA ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "adelminakaic7@gmail.com"          # Ovdje upiši svoj Gmail sa kojeg šalješ
SENDER_PASSWORD = "otdehtjszgaelncz"         # Ovdje upiši Google App Password (16 karaktera)

def posalji_email_obavijest(primaoc_email, naslov, poruka_tekst):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = primaoc_email
        msg['Subject'] = naslov
        
        msg.attach(MIMEText(poruka_tekst, 'plain', 'utf-8'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, primaoc_email, msg.as_string())
        server.quit()
        print(f"Uspješno poslan stvarni email vozaču na: {primaoc_email}")
    except Exception as e:
        print(f"Greška pri slanju emaila: {e}")

# --- ODOBRENJE VOZAČA (Generisanje ugovora + Slanje Email-a) ---
@app.patch("/api/admin/odobri-vozaca/{vozac_id}")
def admin_odobri_vozaca(vozac_id: int, sifra: str, db: Session = Depends(get_db)):
    if sifra != ADMIN_SIFRA:
        raise HTTPException(status_code=403, detail="Pogrešna admin šifra.")
    
    vozac = db.query(models.DriverModel).filter(models.DriverModel.id == vozac_id).first()
    if not vozac:
        raise HTTPException(status_code=404, detail="Vozač nije pronađen.")

    vozac.verifikovan = True
    
    # Generišemo PDF ugovor pošto je odobren!
    putanja_pdf = kreiraj_pdf_ugovor(vozac.puno_ime, vozac.telefon, vozac.email, UPLOAD_DIR)
    vozac.putanja_ugovora = putanja_pdf
    
    db.commit()

    # Slanje pravog email obavještenja na email unesen pri registraciji vozača
    if vozac.email:
        naslov = "Čestitamo! Vaš nalog na SBK Taxi platformi je odobren"
        poruka = f"Poštovani {vozac.puno_ime},\n\nVaši dokumenti su pregledani i nalog je uspješno odobren.\nMožete preuzeti vaš ugovor i pristupiti portalu za vozače."
        posalji_email_obavijest(vozac.email, naslov, poruka)

    return {
        "status": "uspjeh",
        "poruka": f"Vozač {vozac.puno_ime} je uspješno odobren, ugovor generisan i email poslan na {vozac.email}."
    }
# --- ODBIJANJE VOZAČA ---
@app.post("/api/admin/odbij-vozaca/{vozac_id}")
def admin_odbij_vozaca(vozac_id: int, sifra: str, podaci: dict, db: Session = Depends(get_db)):
    if sifra != ADMIN_SIFRA:
        raise HTTPException(status_code=403, detail="Pogrešna admin šifra.")
    
    razlog = podaci.get("razlog", "Dokumenti nisu ispravni.")
    vozac = db.query(models.DriverModel).filter(models.DriverModel.id == vozac_id).first()
    if not vozac:
        raise HTTPException(status_code=404, detail="Vozač nije pronađen.")

    email_vozaca = vozac.email
    ime_vozaca = vozac.puno_ime

    db.delete(vozac)
    db.commit()

    # Slanje email obavještenja o odbijanju
    naslov = "Obavještenje o prijavi na SBK Taxi platformu"
    poruka = f"Poštovani {ime_vozaca},\n\nVaša prijava je odbijena.\nRazlog: {razlog}\nMolimo registrujte se ponovo sa ispravnim dokumentima."
    posalji_email_obavijest(email_vozaca, naslov, poruka)

    return {"status": "uspjeh", "poruka": "Vozač je odbijen, obrisan iz sistema i poslan email."}

# --- PREUZIMANJE UGOVORA I OTKLJUČAVANJE PORTALA ---
@app.get("/api/vozac/preuzmi-ugovor/{vozac_id}")
def preuzmi_ugovor(vozac_id: int, db: Session = Depends(get_db)):
    vozac = db.query(models.DriverModel).filter(models.DriverModel.id == vozac_id).first()
    if not vozac or not vozac.putanja_ugovora:
        raise HTTPException(status_code=404, detail="Ugovor nije pronađen.")
    
    # Označavamo u bazi da je ugovor uspješno preuzet
    vozac.ugovor_preuzet = True
    db.commit()
    
    if os.path.exists(vozac.putanja_ugovora):
        return FileResponse(vozac.putanja_ugovora, media_type='application/pdf', filename=f"Ugovor_SBK_Taxi_{vozac.puno_ime}.pdf")
    
    raise HTTPException(status_code=404, detail="Fajl ugovora ne postoji na serveru.")


# --- PROVJERA DA LI JE VOZAČ PREUZEO UGOVOR (Prilikom prijave) ---
@app.post("/api/vozac/provjeri-status-ugovora")
def provjeri_status_ugovora(podaci: dict, db: Session = Depends(get_db)):
    telefon = podaci.get("telefon")
    cisti_telefon = provjeri_bh_telefon(telefon)
    vozac = db.query(models.DriverModel).filter(models.DriverModel.telefon == cisti_telefon).first()
    
    if not vozac:
        raise HTTPException(status_code=404, detail="Vozač nije pronađen.")
        
    return {
        "status": "uspjeh",
        "ugovor_preuzet": vozac.ugovor_preuzet,
        "vozac_id": vozac.id
    }

# --- ADMIN PREGLED SVIH VOŽNJI ---
@app.get("/api/admin/sve-voznje")
def admin_sve_voznje(sifra: str, db: Session = Depends(get_db)):
    if sifra != ADMIN_SIFRA:
        raise HTTPException(status_code=403, detail="Pogrešna admin šifra.")
    voznje = db.query(models.Ride).all()
    return {"voznje": voznje}


# --- KLIJENT: NARUDŽBA VOŽNJE ---
@app.post("/api/klijent/naruci-voznju")
def naruci_voznju(podaci: dict, db: Session = Depends(get_db)):
    ime = podaci.get("ime_putnika", "Gost")
    telefon = podaci.get("telefon_putnika")
    polaziste = podaci.get("lokacija_polazista")
    odrediste = podaci.get("lokacija_odredista")
    cijena = podaci.get("cijena_voznje", 5.00)

    if not telefon or not polaziste or not odrediste:
        raise HTTPException(status_code=400, detail="Nedostaju obavezni podaci za narudžbu.")

    nova_voznja = models.Ride(
        ime_putnika=ocisti_i_provjeri_tekst(ime),
        telefon_putnika=provjeri_bh_telefon(telefon),
        lokacija_polazista=ocisti_i_provjeri_tekst(polaziste),
        lokacija_odredista=ocisti_i_provjeri_tekst(odrediste),
        cijena_voznje=cijena,
        status="Aktivna"
    )
    db.add(nova_voznja)
    db.commit()
    db.refresh(nova_voznja)

    return {
        "status": "uspjeh",
        "poruka": "Vožnja uspješno naručena!",
        "voznja_id": nova_voznja.id
    }


# --- VOZAČ: DOSTUPNE VOŽNJE ---
@app.get("/api/vozac/dostupne-voznje")
def dostupne_voznje(telefon: str, db: Session = Depends(get_db)):
    vozac = db.query(models.DriverModel).filter(models.DriverModel.telefon == provjeri_bh_telefon(telefon)).first()
    if not vozac or not vozac.verifikovan:
        raise HTTPException(status_code=403, detail="Pristup odbijen.")
    
    voznje = db.query(models.Ride).filter(models.Ride.status == "Aktivna").all()
    return {"trenutna_lokacija": vozac.trenutna_lokacija, "dostupne_voznje": voznje}


# --- VOZAČ: PRIHVATANJE VOŽNJE (Automatski u Zauzet + Obavezna lokacija) ---
@app.post("/api/vozac/prihvati-voznju/{id_voznje}")
def prihvati_voznju(id_voznje: int, podaci: dict, db: Session = Depends(get_db)):
    telefon = podaci.get("telefon")
    vozac = db.query(models.DriverModel).filter(models.DriverModel.telefon == provjeri_bh_telefon(telefon)).first()
    
    if not vozac or not vozac.verifikovan:
        raise HTTPException(status_code=403, detail="Neautorizovan pristup.")

    # Provjera da li vozač ima ažuriranu lokaciju
    if not vozac.trenutna_lokacija:
        raise HTTPException(status_code=400, detail="Vaša lokacija nije ažurirana! Molimo unesite trenutnu lokaciju prije prihvatanja.")

    voznja = db.query(models.Ride).filter(models.Ride.id == id_voznje).first()
    if not voznja or voznja.status != "Aktivna":
        raise HTTPException(status_code=404, detail="Vožnja više nije dostupna.")

    # Mijenjamo statuse
    voznja.status = "U toku"
    voznja.id_vozaca = vozac.id
    vozac.status_zauzeca = "Zauzet"
    
    db.commit()

    return {
        "status": "uspjeh",
        "detalji_voznje": {
            "id": voznja.id,
            "putnik": voznja.ime_putnika,
            "telefon_putnik": voznja.telefon_putnika,
            "polaziste": voznja.lokacija_polazista,
            "odrediste": voznja.lokacija_odredista,
            "cijena": float(voznja.cijena_voznje),
            "vozac_ime": vozac.puno_ime,
            "vozac_telefon": vozac.telefon,
            "polazna_tacka_vozaca": vozac.trenutna_lokacija
        }
    }


# --- VOZAČ: ZAVRŠETAK VOŽNJE (Vraća u Slobodan) ---
@app.post("/api/vozac/zavrsi-voznju/{id_voznje}")
def zavrsi_voznju(id_voznje: int, podaci: dict, db: Session = Depends(get_db)):
    telefon = podaci.get("telefon")
    vozac = db.query(models.DriverModel).filter(models.DriverModel.telefon == provjeri_bh_telefon(telefon)).first()
    
    if not vozac:
        raise HTTPException(status_code=403, detail="Neautorizovan pristup.")

    voznja = db.query(models.Ride).filter(models.Ride.id == id_voznje, models.Ride.id_vozaca == vozac.id).first()
    if not voznja:
        raise HTTPException(status_code=404, detail="Vožnja nije pronađena ili nije vaša.")

    voznja.status = "Zavrsena"
    vozac.status_zauzeca = "Slobodan"
    db.commit()

    return {"status": "uspjeh", "poruka": "Vožnja uspješno završena, vraćeni ste u status slobodan."}


# --- KLIJENT: STATUS VOŽNJE (Polling za praćenje) ---
@app.get("/api/klijent/status-voznje/{voznja_id}")
def provjeri_status_voznje(voznja_id: int, db: Session = Depends(get_db)):
    voznja = db.query(models.Ride).filter(models.Ride.id == voznja_id).first()
    if not voznja:
        raise HTTPException(status_code=404, detail="Vožnja nije pronađena.")

    odgovor = {
        "voznja_id": voznja.id,
        "status": voznja.status,
        "lokacija_polazista": voznja.lokacija_polazista,
        "lokacija_odredista": voznja.lokacija_odredista,
        "vozac_dodijeljen": False,
        "vozac_ime": None,
        "vozac_telefon": None,
        "vozac_lokacija": None
    }

    if voznja.id_vozaca:
        vozac = db.query(models.DriverModel).filter(models.DriverModel.id == voznja.id_vozaca).first()
        if vozac:
            odgovor["vozac_dodijeljen"] = True
            odgovor["vozac_ime"] = vozac.puno_ime
            odgovor["vozac_telefon"] = vozac.telefon
            odgovor["vozac_lokacija"] = vozac.trenutna_lokacija if vozac.trenutna_lokacija else "Lokacija nije unesena"

    return odgovor