from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
import os
import shutil
import models
from database import get_db
import re

# Kreiramo ruter za ovaj fajl
router = APIRouter(prefix="/api", tags=["Portal za Vozače i Klijente"])

UPLOAD_DIR = "uploads"

# Pomoćne funkcije za čišćenje i validaciju
def ociisti_i_provjeri_tekst(v: str) -> str:
    v = v.strip()
    if len(v) < 3:
        raise ValueError("Unos mora imati više od 3 slova.")
    sumnjive_rijeci = ["drop", "delete", "truncate", "update", "insert", "select", "--", ";", "db"]
    for rijec in sumnjive_rijeci:
        if rijec in v.lower():
            raise ValueError("Unos sadrži nedozvoljene znakove ili izraze.")
    return v.title()

def provjeri_bh_telefon(v: str) -> str:
    cisti_broj = re.sub(r'[\s\-\(\)]', '', v)
    if not re.match(r'^06\d{7,8}$', cisti_broj):
        raise ValueError("Neispravan format broja. Broj mora počinjati sa 06 i imati ispravan broj znamenki.")
    return cisti_broj


# --- SVE RUTE ZA VOZAČE I KLIJENTE ---

@router.post("/klijent/naruci-voznju")
def naruci_voznju(podaci: dict, db: Session = Depends(get_db)):
    try:
        raw_ime = podaci.get("ime_putnika") or podaci.get("ime") or "Gost"
        raw_telefon = podaci.get("broj_telefona_putnika") or podaci.get("telefon_putnika")
        raw_polaziste = podaci.get("polaziste") or podaci.get("lokacija_polazista")
        raw_odrediste = podaci.get("odrediste") or podaci.get("lokacija_odredista")
        cijena = podaci.get("cijena_voznje") or 5.0

        if not raw_telefon or not raw_polaziste or not raw_odrediste:
            raise HTTPException(status_code=400, detail="Nedostaju obavezni podaci.")

        ime = ociisti_i_provjeri_tekst(raw_ime) if raw_ime != "Gost" else "Gost"
        telefon = provjeri_bh_telefon(raw_telefon)
        polaziste = ociisti_i_provjeri_tekst(raw_polaziste)
        odrediste = ociisti_i_provjeri_tekst(raw_odrediste)

        nova_voznja = models.Ride(
            ime_putnika=ime,
            telefon_putnika=telefon,
            lokacija_polazista=polaziste,
            lokacija_odredista=odrediste,
            cijena_voznje=cijena,
            status="Aktivna"
        )
        db.add(nova_voznja)
        db.commit()
        db.refresh(nova_voznja)

        return {"status": "uspjeh", "poruka": "Vožnja je uspješno naručena!", "id_voznje": nova_voznja.id}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vozac/status")
def azuriraj_status_vozaca(podaci: dict, db: Session = Depends(get_db)):
    try:
        raw_telefon = podaci.get("telefon")
        status_rada = podaci.get("status_rada")
        status_zauzeca = podaci.get("status_zauzeca")
        raw_lokacija = podaci.get("trenutna_lokacija")

        if not raw_telefon:
            raise HTTPException(status_code=400, detail="Nedostaje broj telefona.")

        cisti_telefon = provjeri_bh_telefon(raw_telefon)
        vozac = db.query(models.DriverModel).filter(models.DriverModel.telefon == cisti_telefon).first()
        
        if not vozac or not vozac.verifikovan:
            raise HTTPException(status_code=403, detail="Pristup odbijen ili nalog nije odobren.")

        if status_rada: vozac.status_rada = status_rada
        if status_zauzeca: vozac.status_zauzeca = status_zauzeca
        if raw_lokacija: vozac.trenutna_lokacija = ociisti_i_provjeri_tekst(raw_lokacija)

        db.commit()
        return {"status": "uspjeh", "poruka": "Status i lokacija ažurirani!"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vozac/dostupne-voznje")
def dostupne_voznje(telefon: str, db: Session = Depends(get_db)):
    cisti_telefon = provjeri_bh_telefon(telefon)
    vozac = db.query(models.DriverModel).filter(models.DriverModel.telefon == cisti_telefon).first()
    
    if not vozac or not vozac.verifikovan:
        raise HTTPException(status_code=403, detail="Pristup odbijen.")

    voznje = db.query(models.Ride).filter(models.Ride.status == "Aktivna").all()
    return {"status": "uspjeh", "trenutna_lokacija_vozaca": vozac.trenutna_lokacija, "dostupne_voznje": voznje}


@router.post("/vozac/prihvati-voznju/{id_voznje}")
def prihvati_voznju(id_voznje: int, podaci: dict, db: Session = Depends(get_db)):
    try:
        raw_telefon = podaci.get("telefon")
        cisti_telefon = provjeri_bh_telefon(raw_telefon)
        vozac = db.query(models.DriverModel).filter(models.DriverModel.telefon == cisti_telefon).first()
        
        if not vozac or not vozac.verifikovan:
            raise HTTPException(status_code=403, detail="Neautorizovan pristup.")

        # OBAVEZNA PROVJERA: Vozač mora unijeti lokaciju prije prihvatanja
        if not vozac.trenutna_lokacija:
            raise HTTPException(status_code=400, detail="Vaša lokacija nije unesena! Molimo ažurirajte trenutnu lokaciju.")

        voznja = db.query(models.Ride).filter(models.Ride.id == id_voznje).first()
        if not voznja or voznja.status != "Aktivna":
            raise HTTPException(status_code=404, detail="Vožnja nije dostupna.")

        # KLJUČNO: Bilježimo vozača, stavljamo vožnju u tok, a vozača u status Zauzet
        voznja.status = "U toku"
        voznja.id_vozaca = vozac.id 
        vozac.status_zauzeca = "Zauzet"
        db.commit()

        return {
            "status": "uspjeh",
            "detalji_voznje": {
                "id": voznja.id,
                "putnik": voznja.ime_putnika,
                "telefon_putnika": voznja.telefon_putnika,
                "polaziste": voznja.lokacija_polazista,
                "odrediste": voznja.lokacija_odredista,
                "cijena": float(voznja.cijena_voznje),
                "vozac_ime": vozac.puno_ime,
                "vozac_telefon": vozac.telefon,
                "polazna_tacka_vozaca": vozac.trenutna_lokacija
            }
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vozac/zavrsi-voznju/{id_voznje}")
def zavrsi_voznju(id_voznje: int, podaci: dict, db: Session = Depends(get_db)):
    try:
        raw_telefon = podaci.get("telefon")
        cisti_telefon = provjeri_bh_telefon(raw_telefon)
        vozac = db.query(models.DriverModel).filter(models.DriverModel.telefon == cisti_telefon).first()
        
        if not vozac:
            raise HTTPException(status_code=403, detail="Neautorizovan pristup.")

        voznja = db.query(models.Ride).filter(models.Ride.id == id_voznje, models.Ride.id_vozaca == vozac.id).first()
        if not voznja:
            raise HTTPException(status_code=404, detail="Vožnja nije pronađena ili nije vaša.")

        voznja.status = "Zavrsena"
        vozac.status_zauzeca = "Slobodan"
        db.commit()

        return {"status": "uspjeh", "poruka": "Vožnja uspješno završena, vraćeni ste u status slobodan."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vozac/prijava")
def prijava_vozaca(broj_telefona: str = Form(...), db: Session = Depends(get_db)):
    cisti_telefon = provjeri_bh_telefon(broj_telefona)
    vozac = db.query(models.DriverModel).filter(models.DriverModel.telefon == cisti_telefon).first()
    
    if not vozac:
        raise HTTPException(status_code=404, detail="Vozač sa ovim brojem ne postoji.")
    if not vozac.verifikovan:
        raise HTTPException(status_code=403, detail="Vaš nalog još uvijek nije odobren od strane administratora.")
        
    return {
        "status": "uspjeh", 
        "poruka": "Prijava uspješna!",
        "vozac": {
            "ime_prezime": vozac.puno_ime,
            "telefon": vozac.telefon,
            "verifikovan": vozac.verifikovan,
            "stanje_racuna": getattr(vozac, "stanje_racuna", 0)
        }
    }