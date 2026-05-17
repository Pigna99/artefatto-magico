"""Popola il DB con 5 pianeti aggiuntivi, divinità, cosmologia + un viaggio
fittizio di 10 voci codex. Pensato per testare il RAG su un universo più
ricco e con potenziale conflitto lore-vs-codex.

Lanciare sul Pi:
    /home/pigna/artefatto/.venv/bin/python scripts/seed_test_world.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from db import Database

DB_PATH = Path.home() / "artefatto" / "data" / "artefatto.db"


LORE = [
    # ---------------- Pianeti ----------------
    ("place", "Pianeta Cipolla",
     "Mondo agricolo della Sesta Spirale, orbita la stella nana azzurra Lacrimaria. "
     "Coperto al 90% da campi di Cipolle Imperiali, vegetali senzienti dalle "
     "tonalità violacee. Atmosfera carica di vapori solforati che fanno "
     "lacrimare anche gli artefatti senzienti.",
     "pianeta,cipolla,sesta-spirale,agricolo"),

    ("place", "Pianeta Sedano",
     "Mondo desertico della Terza Spirale, intero ricoperto da fibre vegetali "
     "secche. Abitato dai Crocchianti, esseri lunghi e snodati che si nutrono "
     "di sole. Atmosfera priva di acqua: chi atterra senza scorta muore in tre giorni.",
     "pianeta,sedano,deserto,crocchianti"),

    ("place", "Pianeta Carota",
     "Mondo arancione della Quarta Spirale, ricco di tunnel sotterranei in cui "
     "vive il Popolo dei Conigli Cosmici. Ha due lune gemelle, Crudina e Cotta. "
     "Esporta zucchero stellare alla Confederazione delle Verdure.",
     "pianeta,carota,sotterraneo,confederazione"),

    ("place", "Pianeta Zucchina",
     "Mondo oceanico della Quinta Spirale, completamente coperto da un mare "
     "verde brodoso. Le creature locali sono i Galleggianti, meduse trasparenti "
     "che cantano per comunicare. Capitale subacquea: Mille Bolle.",
     "pianeta,zucchina,oceano,galleggianti"),

    ("place", "Pianeta Aglio",
     "Mondo morto della Settima Spirale, devastato da una guerra antica contro "
     "i Vampiri Stellari. Ora orbita silenzioso, ma emette un odore percepibile "
     "a 100.000 km che respinge ogni nave non protetta da incantesimo.",
     "pianeta,aglio,morto,guerra,vampiri"),

    # ---------------- Cosmologia ----------------
    ("note", "Le Sette Spirali",
     "La galassia degli Orti Eterni è divisa in Sette Spirali concentriche. "
     "Ciascuna Spirale è governata da un Custode Vegetale primordiale. La "
     "Prima è sacra, la Settima è maledetta. Viaggiare tra Spirali richiede "
     "il Permesso del Custode di partenza.",
     "cosmologia,spirali,custodi"),

    ("note", "Confederazione delle Verdure",
     "Alleanza politica nata nel 1402 fra Pianeta Carota, Zucchina e Sedano. "
     "Ha sede su Carota. Si oppone all'Impero dei Tuberi (capitale Pianeta Patate) "
     "in un'antica disputa sull'esportazione dello zucchero stellare.",
     "politica,confederazione,impero"),

    ("note", "Impero dei Tuberi",
     "Antica potenza guidata dal Pianeta Patate. Comprende vassalli minori. "
     "In conflitto storico con la Confederazione delle Verdure per i diritti "
     "commerciali dell'amido cosmico.",
     "politica,impero,tuberi"),

    # ---------------- Divinità ----------------
    ("npc", "Solarium il Germogliante",
     "Divinità della crescita, raffigurata come un sole con germogli al posto "
     "dei raggi. Venerata su tutti i pianeti agricoli. Il suo tempio principale "
     "è il Tempio del Solco sotto Monte Buccia sul Pianeta Patate.",
     "divinita,sole,crescita"),

    ("npc", "Notturna la Marcescente",
     "Divinità oscura della putrefazione e del riciclo. Non malvagia: trasforma "
     "ciò che muore in nuova vita. Sacerdoti vestono di muffa verde. Tempio "
     "centrale sul Pianeta Aglio, nelle rovine.",
     "divinita,morte,riciclo"),

    ("npc", "I Tre Cuochi Eterni",
     "Triade divina che secondo il mito creò le Sette Spirali cucinando il "
     "Brodo Primordiale. Si chiamano Sale, Olio e Fuoco. Festa annuale del "
     "Grande Banchetto nel solstizio.",
     "divinita,triade,creazione"),

    ("npc", "Stellafredda",
     "Dea minore degli astri spenti e dei pianeti morti. Vagamente temuta. "
     "Si dice abiti sul Pianeta Aglio dopo la guerra contro i Vampiri Stellari.",
     "divinita,morte,stelle"),

    # ---------------- Eventi / leggende ----------------
    ("event", "Grande Bollitura",
     "Cataclisma cosmico del 880 in cui la stella Tuberalis quasi esplose, "
     "portando 30 anni di stagione calda continua nella Quarta Spirale. Solo "
     "l'intervento di Solarium salvò il Pianeta Patate.",
     "cataclisma,storia,divino"),

    ("event", "Patto del Brodo",
     "Trattato di pace del 1502 fra Impero dei Tuberi e Confederazione delle "
     "Verdure. Stabilisce zone di libero commercio per l'amido cosmico. "
     "Firmato a bordo della stazione neutrale Mestolo d'Oro.",
     "trattato,storia,pace"),

    ("item", "Mestolo d'Oro",
     "Stazione spaziale neutrale tra Quarta e Sesta Spirale, sede di trattative "
     "diplomatiche. Forma cilindrica con grande mestolo dorato sul tetto.",
     "stazione,neutrale,diplomazia"),
]


# Codex = un singolo viaggio narrativo, scritto come 10 voci consecutive
# che simulano sessioni di gioco. Pigna sta visitando il Pianeta Cipolla
# accompagnato dall'artefatto, e affronta una piccola avventura.
CODEX = [
    ("Diario 01 — Partenza",
     "Oggi io e l'artefatto siamo partiti dalla stazione orbitale Mestolo d'Oro "
     "per raggiungere il Pianeta Cipolla. Il viaggio durerà tre giorni di luce. "
     "Porto con me due ampolle di olio sacro per le offerte a Solarium."),

    ("Diario 02 — Atterraggio",
     "Atterrati ieri sul Pianeta Cipolla. L'aria fa lacrimare gli occhi, come "
     "mi era stato preannunciato. Le Cipolle Imperiali ondeggiano in file "
     "perfette nei campi violacei. L'artefatto ha iniziato a brillare di viola "
     "non appena ha toccato terra."),

    ("Diario 03 — Incontro col Sindaco-Bulbo",
     "Ho parlato con il Sindaco-Bulbo, una Cipolla Imperiale anziana che "
     "governa il villaggio di Lacrimopoli. Mi ha chiesto aiuto: dei semi sacri "
     "stanno scomparendo dai granai. Sospetta i Crocchianti del Pianeta Sedano, "
     "ma non ha prove."),

    ("Diario 04 — Indagine ai granai",
     "Stamattina ho ispezionato i granai dove avvengono i furti. Trovate "
     "tracce sottili e sinuose, non da Crocchianti (loro lasciano impronte "
     "secche). Sembrano scivolate di qualcosa di umido. L'artefatto suggerisce "
     "Galleggianti del Pianeta Zucchina — ma cosa farebbero qui?"),

    ("Diario 05 — La pozza sospetta",
     "Trovata una pozza d'acqua salmastra nei pressi del granaio sud. "
     "Sicuramente artificiale: nessuna fonte d'acqua naturale sul Pianeta "
     "Cipolla. Qualcuno ha portato qui dei Galleggianti per usarli come ladri."),

    ("Diario 06 — Il mercante straniero",
     "Identificato un mercante chiamato Carlo Bulbus, originario del Pianeta "
     "Aglio. Ha installato la pozza. Lo abbiamo seguito fino al suo "
     "nascondiglio: una vecchia stalla abbandonata oltre i campi est."),

    ("Diario 07 — Il rituale interrotto",
     "Carlo Bulbus stava celebrando un rituale a Notturna la Marcescente "
     "usando i semi sacri rubati. L'artefatto ha emesso luce viola intensa e "
     "ha interrotto il rituale. Carlo è fuggito ma abbiamo recuperato i semi."),

    ("Diario 08 — Restituzione",
     "Restituiti i semi sacri al Sindaco-Bulbo. Cerimonia di ringraziamento "
     "con offerta di olio a Solarium il Germogliante. Il villaggio mi ha "
     "donato una collana di buccia di Cipolla Imperiale, simbolo di amicizia."),

    ("Diario 09 — Indizio sul Pianeta Aglio",
     "Indagando nello scrigno di Carlo Bulbus ho trovato una mappa del "
     "Pianeta Aglio con segnato un tempio dimenticato di Notturna. Pare ci "
     "sia un culto che opera nell'ombra cercando di destabilizzare le altre "
     "Spirali."),

    ("Diario 10 — Verso il prossimo viaggio",
     "Domani ripartiamo dal Pianeta Cipolla. Direzione: Pianeta Aglio, "
     "per investigare il culto di Notturna. L'artefatto sembra inquieto: "
     "il Pianeta Aglio è un mondo morto e l'odore arriva a 100.000 km. "
     "Devo prepararmi al peggio."),
]


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = Database(DB_PATH)

    print(f"DB: {DB_PATH}")
    print(f"Aggiungo {len(LORE)} voci di lore...")
    for kind, name, desc, tags in LORE:
        db.add_lore(name=name, kind=kind, description=desc, tags=tags)
    print(f"  → {len(LORE)} aggiunte (INSERT OR REPLACE su (name,kind))")

    print(f"\nAggiungo {len(CODEX)} voci di codex...")
    for title, body in CODEX:
        db.add_codex(title=title, body=body)
    print(f"  → {len(CODEX)} aggiunte (sempre nuove)")

    # Sanity check
    print("\n=== Sanity checks ===")
    print(f"Lore totale nel DB: {len(db.all_lore())}")
    print(f"Codex totale nel DB: {len(db.all_codex(limit=200))}")

    print("\nTest ricerca: 'Dove siamo ora?'")
    print(" lore:")
    for r in db.search_lore("Dove siamo ora?"):
        print(f"   - {r.name}")
    print(" codex:")
    for r in db.search_codex("Dove siamo ora?"):
        print(f"   - {r.title}")

    print("\nTest ricerca: 'Cipolla Imperiale'")
    print(" lore:")
    for r in db.search_lore("Cipolla Imperiale"):
        print(f"   - {r.name}")
    print(" codex:")
    for r in db.search_codex("Cipolla Imperiale"):
        print(f"   - {r.title}")

    db.close()


if __name__ == "__main__":
    main()
