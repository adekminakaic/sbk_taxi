-- 1. Uključivanje PostGIS ekstenzije za geografske lokacije i koordinate
CREATE EXTENSION IF NOT EXISTS postgis;

-- Brisanje starih tabela ako postoje (kako bismo napravili čistu strukturu)
DROP TABLE IF EXISTS voznje CASCADE;
DROP TABLE IF EXISTS vozaci CASCADE;
DROP TABLE IF EXISTS opstine CASCADE;

-- 2. Tabela opština
CREATE TABLE opstine (
    id SERIAL PRIMARY KEY,
    naziv VARCHAR(100) NOT NULL,
    geometrija_granice GEOMETRY(Polygon, 4326)
);

-- 3. Tabela vozača (Sa email-om, statusima, vremenom prijave/odjave i praćenjem preuzimanja ugovora)
CREATE TABLE vozaci (
    id SERIAL PRIMARY KEY,
    puno_ime VARCHAR(150) NOT NULL,
    telefon VARCHAR(30) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    verifikovan BOOLEAN DEFAULT FALSE,
    stanje_racuna DECIMAL(10, 2) DEFAULT 0.00,

    -- Dokumenti, ugovor i praćenje preuzimanja
    slika_vozacke VARCHAR(255),
    slika_registracije VARCHAR(255),
    putanja_ugovora VARCHAR(255),
    ugovor_preuzet BOOLEAN DEFAULT FALSE, -- <-- Novo: prate da li je vozač preuzeo ugovor

    -- Statusi, lokacija i vrijeme prijave/odjave
    status_rada VARCHAR(50) DEFAULT 'Offline', -- Može biti: Aktivan, Pauza, Offline
    status_zauzeca VARCHAR(50) DEFAULT 'Slobodan', -- Može biti: Slobodan, Zauzet
    trenutna_lokacija VARCHAR(255), -- Mjesto odakle vozač kreće (npr. Travnik - Centar)
    zadnja_prijava TIMESTAMP, -- Vrijeme kada se vozač prijavio
    zadnja_odjava TIMESTAMP, -- Vrijeme kada se vozač odjavio
    
    kreirano_u TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Tabela vožnji
CREATE TABLE voznje (
    id SERIAL PRIMARY KEY,
    ime_putnika VARCHAR(100) NOT NULL,
    telefon_putnika VARCHAR(30) NOT NULL,
    id_vozaca INT REFERENCES vozaci(id) ON DELETE SET NULL,
    lokacija_polazista VARCHAR(255) NOT NULL,
    lokacija_odredista VARCHAR(255) NOT NULL,
    cijena_voznje DECIMAL(10, 2) DEFAULT 5.00,
    iznos_provizije FLOAT DEFAULT 0.0,
    status VARCHAR(50) DEFAULT 'Aktivna', -- Aktivna, U toku, Zavrsena
    kreirano_u TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);