import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def kreiraj_pdf_ugovor(cisti_ime: str, cisti_telefon: str, cisti_email: str, upload_dir: str) -> str:
    """
    Funkcija koja generiše profesionalni PDF ugovor uz podršku za naša slova (UTF-8 / TrueType font)
    i obavezu obavještavanja putem email adrese.
    """
    os.makedirs(upload_dir, exist_ok=True)
    
    ugovor_filename = f"Ugovor_SBK_Taxi_{cisti_telefon}.pdf"
    ugovor_path = os.path.join(upload_dir, ugovor_filename)
    db_ugovor_path = f"uploads/{ugovor_filename}"

    # Registrujemo Arial font iz Windows sistema da podržava č, ć, ž, š, đ
    try:
        font_path = "C:/Windows/Fonts/arial.ttf"
        pdfmetrics.registerFont(TTFont('ArialUnicode', font_path))
        koristeni_font = 'ArialUnicode'
    except Exception:
        koristeni_font = 'Helvetica'

    # Generisanje PDF-a pomoću ReportLab-a
    c = canvas.Canvas(ugovor_path, pagesize=letter)
    width, height = letter

    # Zaglavlje ugovora
    c.setFont(koristeni_font, 16)
    c.drawString(100, height - 50, "SBK TAXI VIP PLATFORMA")
    c.setFont(koristeni_font, 11)
    c.drawString(100, height - 70, "UGOVOR O POSREDOVANJU I PRUŽANJU USLUGA PREVOZA")

    # Linija ispod zaglavlja
    c.setLineWidth(1)
    c.line(100, height - 80, 512, height - 80)

    # Sadržaj ugovora sa našim slovima
    c.setFont(koristeni_font, 10)
    tekst_ugovora = [
        f"Ime i prezime vozača: {cisti_ime}",
        f"Kontakt telefon: {cisti_telefon}",
        f"Email adresa za obavještenja: {cisti_email}",
        f"Status naloga: Odobren i aktivan",
        "-",
        "OPŠTI USLOVI SARADNJE:",
        "1. Vozač se obavezuje da će usluge prevoza obavljati profesionalno i u skladu sa propisima.",
        "2. Platforma SBK Taxi VIP osigurava dispečersku podršku i prosljeđivanje vožnji.",
        "3. Isplata ostvarenih vožnji vrši se u skladu sa dogovorenim sedmičnim/mjesečnim obračunom.",
        "4. Sva zvanična obavještenja, odobrenja i statusi dostavljaju se na registrovanu email adresu.",
        "5. Ovaj ugovor stupa na snagu danom verifikacije naloga od strane administratora.",
        "-",
        "Potpis / Ovjera platforme SBK Taxi VIP"
    ]

    y_pos = height - 120
    for linija in tekst_ugovora:
        c.drawString(100, y_pos, linija)
        y_pos -= 20

    c.save()
    return db_ugovor_path