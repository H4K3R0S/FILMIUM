# PERSONA I ARHITEKTURA DOMENA: FILMIUM (AI KURATOR & MENADŽER) - UPDATE

Ovaj dokument dopunjuje i proširuje prethodnu specifikaciju za domenu **FILMIUM**. Fokus ovog ažuriranja je na eksternim integracijama (TMDB, Torrenti), upravljanju listama čekanja za neobjavljene filmove i automatskom skeniranju Windows sistemskih foldera.

Implementaciju ovih naprednih funkcija izvršiti kroz sledeće dopunske module.

---

## 🛠️ Sadržaj Dopune (Nove Funkcionalnosti)

- [ ] Modul 5: TMDB Integracija i Upravljanje Neobjavljenim Sadržajem
- [ ] Modul 6: Torrent Automatizacija (Predstojeća integracija)
- [ ] Modul 7: Pametni Monitor Windows Foldera (Downloads & Videos)

---

## [ ] Modul 5: TMDB Integracija i Upravljanje Neobjavljenim Sadržajem

Kurator koristi spoljne baze podataka kako bi bio u toku sa svetskom kinematografijom i pratio filmove koji još uvek nisu na tvom hard disku.

- [ ] **TMDB API Klijent:** Implementirati modul za povlačenje metapodataka sa TMDB-a (posteri, ocene, glumačka ekipa, trejleri, datumi premijera). Ako film sa drajva nema lokalne podatke, Kurator ih automatski vuče sa TMDB-a.
- [ ] **Sistem za Rezervacije (Pre-release Watchlist):** Kreirati sekciju unutar GUI-ja za filmove i serije koji još uvek nisu izašli u bioskopima ili na striming platformama.
- [ ] **Ručni Unos Specifičnog Sadržaja:** Omogućiti opciju kroz GUI (i preko glasovne komande) gde korisnik može ručno da doda naslov filma koji još ne postoji na TMDB-u ili drajvu. Kurator ovaj unos drži u bazi kao "Visokoprioritetnu poternicu" (High-priority watch).

---

## [ ] Modul 6: Torrent Automatizacija (Predstojeća integracija)

Pripremiti arhitekturu za povezivanje sa Torrent klijentima (npr. qBittorrent API) kako bi Kurator mogao samostalno da nabavlja filmove.

- [ ] **Pametni Scraper (Tragač za Torrentima):** Kada korisnik zatraži film koji nije prisutan na `F:\` drajvu, Kurator pretražuje povezane torrent izvore na osnovu zadatih parametara kvaliteta (npr. 1080p, 4K, HDR, minimalni broj seed-era).
- [ ] **Kontrola i Praćenje Download-a:** Implementirati API interfejs koji može da pošalje magnet link torrent klijentu, pokrene preuzimanje, pauzira ga ili promeni prioritet brzinom protoka podataka.

---

## [ ] Modul 7: Pametni Monitor Windows Foldera (Downloads & Videos)

Sprečiti ručno premeštanje fajlova. Kurator mora da pazi na sistemske foldere u Windowsu i automatski sređuje tvoju kolekciju.

- [ ] **Automatski Skener Direktorijuma (Folder Watcher):** Aktivirati pozadinski servis koji u realnom vremenu (ili na svakih nekoliko minuta) skenira Windows `Downloads` i `Videos` foldere.
- [ ] **Prepoznavanje Medijskih Fajlova:** Filter mora da prepozna video formate (.mp4, .mkv, .avi) i da preko naziva fajla (pomoću regex-a i TMDB integracije) zaključi o kom filmu ili epizodi serije se radi.
- [ ] **Automatska Migracija (Auto-Sorting):** Kada se preuzimanje filma završi u `Downloads` folderu, Kurator ga automatski premešta na odgovarajuću lokaciju na drajvu `F:\` (npr. u folder `F:\Filmovi\Ime Filma (Godina)\`), preimenuje fajl i osvežava GUI.
