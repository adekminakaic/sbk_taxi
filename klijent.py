from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import re

from database import get_db
import models

router = APIRouter(
    prefix="/api/klijent",
    tags=["Klijent Portal"]
)

# --- Pydantic šema za kreiranje narudžbe ---
class NarudzbaVoznje(BaseModel):
    ime_putnika: str = Field(..., min_length=2)
    telefon_putnika: str = Field(..., min_length=6)
    lokacija_polazista: str = Field(..., min_length=3)
    lokacija_odredista: str = Field(..., min_length=3)

# --- Pomoćna funkcija za čišćenje telefona ---
def ocisti_telefon(v: str) -> str:
    cisti = re.sub(r'[\s\-\(\)]', '', v)
    return cisti


@router.post("/naruci-voznju", status_code=status.HTTP_201_CREATED)
def naruci_voznju(narudzba: NarudzbaVoznje, db: Session = Depends(get_db)):
    """
    Ruta koju poziva klijent kada popuni formu za narudžbu vožnje.
    Kreira novu vožnju u bazi sa statusom 'Aktivna'.
    """
    cisti_broj = ocisti_telefon(narudzba.telefon_putnika)
    
    nova_voznja = models.Ride(
        ime_putnika=narudzba.ime_putnika,
        telefon_putnika=cisti_broj,
        lokacija_polazista=narudzba.lokacija_polazista,
        lokacija_odredista=narudzba.lokacija_odredista,
        status="Aktivna"  # Čeka da je vozač vidi i prihvati
    )
    
    db.add(nova_voznja)
    db.commit()
    db.refresh(nova_voznja)
    
    return {
        "poruka": "Vožnja uspješno naručena!",
        "voznja_id": nova_voznja.id
    }


@router.get("/status-voznje/{voznja_id}")
def provjeri_status_voznje(voznja_id: int, db: Session = Depends(get_db)):
    """
    Ruta koju klijentska stranica poziva svakih nekoliko sekundi (polling)
    kako bi saznala da li je vozač prihvatio vožnju i gdje se trenutno nalazi.
    """
    voznja = db.query(models.Ride).filter(models.Ride.id == voznja_id).first()
    
    if not voznja:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Vožnja nije pronađena."
        )
    
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
    
    # Ako je vozač prihvatio vožnju, dohvatamo njegove detalje i trenutnu lokaciju
    if voznja.id_vozaca:
        vozac = db.query(models.DriverModel).filter(models.DriverModel.id == voznja.id_vozaca).first()
        if vozac:
            odgovor["vozac_dodijeljen"] = True
            odgovor["vozac_ime"] = vozac.puno_ime
            odgovor["vozac_telefon"] = vozac.telefon
            # Lokacija koju je vozač unio na svom portalu
            odgovor["vozac_lokacija"] = vozac.trenutna_lokacija if vozac.trenutna_lokacija else "Lokacija nije unesena"
            
    return odgovor