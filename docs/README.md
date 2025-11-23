[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/DxqGQVx4)
# 🎯 IConsult Matching Platform (MVP)

## 🌟 Project Overzicht

IConsult is een **tweezijdige, anonieme marktplaats** die de werving van consultants en het vinden van projecten stroomlijnt. Ons platform pakt de traditionele frictie in de consultancy-arbeidsmarkt aan door **relevantie** en **vertrouwen** centraal te stellen.

[cite_start]Het primaire doel van de MVP is om bedrijven de meest geschikte consultants te tonen op basis van een geavanceerde matchingsscore, terwijl de identiteit van beide partijen beschermd blijft totdat een match wordt "ontgrendeld"[cite: 37].

---

## 🚀 Kernfunctionaliteiten (MVP Musts)

[cite_start]De focus van dit Minimum Viable Product (MVP) ligt op de essentiële 'Must'-vereisten[cite: 4, 6, 16, 22, 33, 37, 41, 46].

### 👥 Rolgebaseerde Toegang
[cite_start]Gebruikers kunnen zich registreren als een **Consultant** of **Company (Bedrijf)**[cite: 7].
* [cite_start]**Consultant:** Kan een **anoniem profiel** aanmaken [cite: 17] [cite_start]en door Job Posts bladeren om relevante missies te vinden[cite: 38].
* [cite_start]**Company:** Kan een **anonieme Job Post** aanmaken [cite: 34] [cite_start]en door Consultant Profielen bladeren[cite: 23].

### 🛡️ Anonymiteit en Onthulling
[cite_start]De identiteit van gebruikers is standaard gemaskeerd (e.g., initialen voor de consultant, "Entreprise anonyme" voor het bedrijf)[cite: 19, 36].

[cite_start]Het cruciale **Unlock-Mechanisme** stelt gebruikers in staat om contactgegevens te onthullen (van het profiel of de job post)[cite: 27, 42]. [cite_start]De ontgrendelingsstatus is **persistent** over sessies heen om te voorkomen dat er twee keer betaald wordt voor dezelfde informatie[cite: 57].

---

## 🧠 Het iConsult Matchingssysteem

[cite_start]Het platform biedt twee zoekmodi: Handmatige Filter & Sortering en **iConsult Match (Beste Relevantie)**[cite: 47].

De iConsult Match-modus sorteert resultaten op basis van een **gewogen relevantiescore**. De totale score wordt berekend op basis van de volgende factoren:

* **Skills (50%):** De overlap en diepte van de benodigde en aanwezige vaardigheden tellen het zwaarst mee.
* **Zoekterm (30%):** De tekstuele gelijkenis tussen de zoekopdracht en de profiel/job beschrijvingen.
* **Recentheid (20%):** Geeft de voorkeur aan recent bijgewerkte profielen of recent geplaatste vacatures.

[cite_start]*(De formule en gewichten zijn gedocumenteerd in de interne documentatie en/of de README/API-specificatie)*[cite: 50].

---

## 💡 Toekomstige Ontwikkeling (Roadmap)

[cite_start]De roadmap volgt de MoSCOW-prioriteiten (Should/Could)[cite: 4].

### Should-Prioriteiten
* [cite_start]**Administratie en Audit:** We zullen een beheerderspagina implementeren voor **moderatie** van profielen/jobs en basis **Unlock analytics** (gebruiksaanalyse)[cite: 75, 60].
* [cite_start]**Profiel Bewerken:** Gebruikers kunnen hun basisprofielinformatie bewerken, zodat hun listings relevante details tonen[cite: 11].

### Could-Prioriteiten
* [cite_start]**Verfijning Zoeken:** Implementatie van functionaliteit voor **suggested keywords** om gebruikers te helpen hun zoekopdracht te verfijnen[cite: 51].
* [cite_start]**Gebruikersgemak:** Toevoeging van functionaliteit voor het opslaan van **favorieten** en het toevoegen van **privénotities** aan ontgrendelde items[cite: 66, 70].