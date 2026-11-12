from sqlalchemy import Column, Integer, String, Boolean, Numeric, TIMESTAMP, Text, ForeignKey, text
from database import Base

class OpstinaModel(Base):
    __tablename__ = "opstine"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    naziv = Column(String(100), nullable=False)

class DriverModel(Base):
    __tablename__ = "vozaci"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    puno_ime = Column(String(150), nullable=False)
    telefon = Column(String(30), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)  # <-- Obavezno polje za email
    verifikovan = Column(Boolean, default=False)
    stanje_racuna = Column(Numeric(10, 2), default=0.00)

    # Dokumenti i ugovor
    slika_vozacke = Column(String(255), nullable=True)
    slika_registracije = Column(String(255), nullable=True)
    putanja_ugovora = Column(String(255), nullable=True)
    ugovor_preuzet = Column(Boolean, default=False)
    
    # Statusi, lokacija i vrijeme prijave/odjave
    status_rada = Column(String, default="Offline")  # Aktivan, Pauza, Offline
    status_zauzeca = Column(String, default="Slobodan")  # Slobodan, Zauzet
    trenutna_lokacija = Column(String, nullable=True) 
    zadnja_prijava = Column(TIMESTAMP, nullable=True)  # Vrijeme kada se prijavio
    zadnja_odjava = Column(TIMESTAMP, nullable=True)   # Vrijeme kada se odjavio
    
    kreirano_u = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

class Ride(Base):
    __tablename__ = "voznje"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ime_putnika = Column(String(100), nullable=False)
    telefon_putnika = Column(String(30), nullable=False)
    id_vozaca = Column(Integer, ForeignKey("vozaci.id", ondelete="SET NULL"), nullable=True)
    lokacija_polazista = Column(String(255), nullable=False)
    lokacija_odredista = Column(String(255), nullable=False)
    cijena_voznje = Column(Numeric(10, 2), default=5.00)
    iznos_provizije = Column(Numeric(10, 2), default=0.0)
    status = Column(String(50), default="Aktivna")  # Aktivna, U toku, Zavrsena
    kreirano_u = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))