[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/DxqGQVx4)
# 🎯 IConsult Matching Platform (MVP)

## 🌟 Project Overzicht

IConsult is een **tweezijdige, anonieme marktplaats** die de werving van consultants en het vinden van projecten stroomlijnt. Ons platform pakt de traditionele frictie in de consultancy-arbeidsmarkt aan door **relevantie** en **vertrouwen** centraal te stellen.

Het primaire doel van de MVP is om bedrijven de meest geschikte consultants te tonen op basis van een geavanceerde matchingsscore, terwijl de identiteit van beide partijen beschermd blijft totdat een match wordt "ontgrendeld".

---

## 🚀 Kernfunctionaliteiten

### 👥 Rolgebaseerde Toegang
Gebruikers kunnen zich registreren als een **Consultant** of **Company (Bedrijf)**.
* **Consultant:** Kan een **anoniem profiel** aanmaken en door Job Posts bladeren om relevante missies te vinden.
* **Company:** Kan een **anonieme Job Post** aanmaken en door Consultant Profielen bladeren.

### 🛡️ Anonymiteit en Onthulling
De identiteit van gebruikers is standaard gemaskeerd (e.g., initialen voor de consultant, "Entreprise anonyme" voor het bedrijf).

Het cruciale **Unlock-Mechanisme** stelt gebruikers in staat om contactgegevens te onthullen (van het profiel of de job post). De ontgrendelingsstatus is **persistent** over sessies heen om te voorkomen dat er twee keer betaald wordt voor dezelfde informatie.

---

## 🧠 Het iConsult Matchingssysteem

Het platform biedt twee zoekmodi: Handmatige Filter & Sortering en **iConsult Match (Beste Relevantie)**.

De iConsult Match-modus sorteert resultaten op basis van een **gewogen relevantiescore**. De totale score wordt berekend op basis van de volgende factoren:

* **Skills (50%):** De overlap en diepte van de benodigde en aanwezige vaardigheden tellen het zwaarst mee.
* **Zoekterm (30%):** De tekstuele gelijkenis tussen de zoekopdracht en de profiel/job beschrijvingen.
* **Recentheid (20%):** Geeft de voorkeur aan recent bijgewerkte profielen of recent geplaatste vacatures.

---

## 💡 Toekomstige Ontwikkeling

### Should-Prioriteiten
* **Administratie en Audit:** We zullen een beheerderspagina implementeren voor **moderatie** van profielen/jobs en basis **Unlock analytics** (gebruiksaanalyse).
* **Profiel Bewerken:** Gebruikers kunnen hun basisprofielinformatie bewerken, zodat hun listings relevante details tonen.

### Could-Prioriteiten
* **Verfijning Zoeken:** Implementatie van functionaliteit voor **suggested keywords** om gebruikers te helpen hun zoekopdracht te verfijnen.
* **Gebruikersgemak:** Toevoeging van functionaliteit voor het opslaan van **favorieten** en het toevoegen van **privénotities** aan ontgrendelde items.