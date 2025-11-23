[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/DxqGQVx4)
🎯 IConsult Matching Platform (MVP)
🌟 Project Overzicht
IConsult is een tweezijdige, anonieme marktplaats die de werving van consultants en het vinden van projecten stroomlijnt. Ons platform pakt de traditionele frictie in de consultancy-arbeidsmarkt aan door relevantie en vertrouwen centraal te stellen.

Het primaire doel van de MVP is om bedrijven de meest geschikte consultants te tonen op basis van een geavanceerde matchingsscore, terwijl de identiteit van beide partijen beschermd blijft totdat een match wordt "ontgrendeld".

🚀 Kernfunctionaliteiten
De focus van dit Minimum Viable Product ligt op de essentiële Must-vereisten, gericht op veilige en efficiënte interactie.

👥 Rolgebaseerde Toegang
Gebruikers kunnen zich registreren in één van de twee rollen:


Consultant: Kan een anoniem profiel aanmaken en door Job Posts bladeren om relevante missies te vinden.


Company (Bedrijf): Kan een anonieme Job Post aanmaken en door Consultant Profielen bladeren om kandidaten op de shortlist te plaatsen.

🛡️ Anonymiteit en Onthulling
De identiteit van gebruikers is standaard gemaskeerd. Zo toont het consultantprofiel initialen en een placeholder/blur voor de afbeelding, en zijn contactgegevens verborgen voor het publiek.

Het cruciale Unlock-Mechanisme stelt gebruikers in staat om contactgegevens te onthullen (van het profiel of de job post), waarna de ontgrendelingsstatus persistent blijft over sessies heen om te voorkomen dat er twee keer "betaald" wordt voor dezelfde informatie.

🧠 Het iConsult Matchingssysteem
Het platform biedt twee zoekmodi (zie screenshot):


Handmatige Filter & Sortering: Biedt gedetailleerde filtermogelijkheden op locatie, contracttype, en gevraagde skills.

iConsult Match (Beste Relevantie): Het hart van het platform. Resultaten worden geordend op basis van een gewogen relevantiescore, weergegeven als een percentage (Match: **XX.X%**).


De totale matchscore wordt berekend door de volgende factoren te combineren, waarbij de gewichten de prioriteit aangeven:


Skills (50%): De overlap en diepte van de benodigde en aanwezige vaardigheden tellen het zwaarst mee.


Zoekterm (30%): De tekstuele gelijkenis tussen de zoekopdracht en de profiel/job beschrijvingen.


Recentheid (20%): Geeft de voorkeur aan recent bijgewerkte profielen of recent geplaatste vacatures.

💡 Toekomstige Ontwikkeling
De verdere roadmap richt zich op de Should en Could prioriteiten om de bruikbaarheid en beheerbaarheid te vergroten.


Administratie en Audit: We zullen een beheerderspagina toevoegen om de laatst gecreëerde items te moderen en om basis Unlock analytics (gebruiksanalyse) te bekijken.


Verfijning Zoeken: Er zal functionaliteit worden toegevoegd voor suggested keywords om gebruikers te helpen hun zoekopdracht te verfijnen, wat de relevantie-zoekmodus verder verbetert.


Gebruikersgemak: Toekomstige functies zijn onder meer het opslaan van favorieten en het toevoegen van privénotities aan ontgrendelde items.