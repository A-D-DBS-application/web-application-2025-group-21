<!doctype html>
<html lang="{{ session.get('language', 'en') }}">
<head>
    <meta charset="utf-8">
    <title>{% block title %}IConsult Match{% endblock %}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    
    {# 🎯 Huidig jaar instellen voor copyright #}
    {% set now = now() %} 

    <style>
        :root {
            --blue: #2563eb;
            --blue-light: #3b82f6;
            --bg: #f9fafb;
            --text: #1f2937;
            --card-bg: #ffffff;
            --border: #e5e7eb;
        }

        body {
            margin: 0;
            font-family: system-ui, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            /* Zorg ervoor dat de body de hele viewport inneemt voor de sticky footer */
            min-height: 100vh; 
            display: flex;
            flex-direction: column;
        }

        /* NAVIGATION */
        header {
            background: var(--blue);
            color: #fff;
            padding: 14px 20px;
        }

        nav {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        nav a {
            color: #fff;
            text-decoration: none;
            font-weight: 500;
            padding: 6px 10px;
            border-radius: 6px;
            transition: background 0.2s;
        }

        nav a:hover {
            background: rgba(255, 255, 255, 0.15);
        }

        .btn {
            background: #fff;
            color: var(--blue);
            border: none;
            padding: 7px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            text-decoration: none;
            transition: background 0.2s;
        }

        .btn:hover {
            background: #e5e7eb;
        }

        /* LAYOUT */
        main {
            max-width: 900px;
            margin: 24px auto;
            padding: 0 16px;
            flex-grow: 1; /* Laat main de beschikbare ruimte innemen */
        }

        .flash {
            background: #dbeafe;
            border-left: 4px solid var(--blue);
            padding: 12px 14px;
            border-radius: 6px;
            margin-bottom: 16px;
        }

        /* CARDS */
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            margin: 16px 0;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }

        form > * {
            display: block;
            margin: 10px 0;
        }

        .row {
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }

        .grow {
            flex: 1 1 300px;
        }

        /* AANGEPASTE FOOTER STIJL */
        .footer {
            background-color: #f8f9fa; /* Lichtgrijze achtergrond */
            border-top: 1px solid #e9ecef;
            text-align: center;
            padding: 20px 16px;
            color: #6b7280;
            width: 100%;
            margin-top: 40px; 
        }
        .footer a {
            color: #6b7280;
            text-decoration: none;
        }
        .footer a:hover {
            text-decoration: underline;
            color: var(--blue);
        }
    </style>
</head>

<body>

    <header>
    <nav>
        <a href="{{ url_for('main.index') }}">{{ _("Home") }}</a>

        {% if session.get('role') == 'company' %}
            <a href="{{ url_for('main.consultants_list') }}">{{ _("Consultants") }}</a>
        {% endif %}

        {% if session.get('role') in ['company', 'consultant'] %}
            <a href="{{ url_for('main.jobs_list') }}">{{ _("Jobs") }}</a>
        {% endif %}

        <a href="{{ url_for('main.dashboard') }}">{{ _("Dashboard") }}</a>

        <div style="margin-left: auto;">
            <form action="{{ url_for('main.set_language') }}" method="POST" style="display:inline;">
                <select name="language" onchange="this.form.submit()" class="btn">
                    <option value="en" {% if session.get('language') == 'en' %}selected{% endif %}>EN</option>
                    <option value="nl" {% if session.get('language') == 'nl' %}selected{% endif %}>NL</option>
                    <option value="fr" {% if session.get('language') == 'fr' %}selected{% endif %}>FR</option>
                </select>
            </form>
        </div>


        {% if session.get('user_id') %}
            <form action="{{ url_for('main.logout') }}" method="post" style="display:inline;">
                <button class="btn" type="submit">{{ _("Logout") }}</button>
            </form>
        {% else %}
            <a class="btn" href="{{ url_for('main.login') }}">{{ _("Login") }}</a>
        {% endif %}
    </nav>
    </header>

    <main>
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for m in messages %}
                    <div class="flash">{{ m }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </main>

    {# NIEUWE FOOTER ZONDER DE FILTER METHODOLOGIE LINK #}
    <footer class="footer">
        <div class="container text-center">
            <span class="text-muted">
                &copy; {{ now.year }} IConsult - All rights reserved
            </span>
        </div>
    </footer>

</body>
</html>





{% extends "base.html" %}
{% block title %}Consultant detail{% endblock %}
{% block content %}
  <h1>{{ profile.display_name_masked }}</h1>
  {# --------- Profielfoto --------- #}
  {% if profile.profile_image %}
    <img 
      src="{{ profile.profile_image }}" 
      alt="Profielfoto" 
      style="width:140px;height:140px;border-radius:50%;object-fit:cover;margin-bottom:15px;"
    >
  {% else %}
    <img 
      src="{{ url_for('static', filename='img/default-avatar.png') }}" 
      alt="Geen profielfoto"
      style="width:140px;height:140px;border-radius:50%;object-fit:cover;margin-bottom:15px;"
    >
  {% endif %}

  {% if profile.headline %}
    <p><i>{{ profile.headline }}</i></p>
  {% endif %}

  <h3>Skills</h3>
  {% if profile.skills and profile.skills|length > 0 %}
    <ul>
      {% for skill in profile.skills %}
        <li>{{ skill.name }}</li>
      {% endfor %}
    </ul>
  {% else %}
    <p><i>Geen skills opgegeven.</i></p>
  {% endif %}

  <p>
    <small>
      {{ profile.location_city }}
      {% if profile.location_city and profile.country %}, {% endif %}
      {{ profile.country }}
    </small>
  </p>
<div class="card">
    <h2>Contactgegevens</h2>
    
    {# 1. Controleert: Is de bezoeker een Bedrijf? #}
    {% if user and user.role == UserRole.company %}
        
        {# Toon contactgegevens indien ONTGRENDELD of de EIGENAAR #}
        {% if is_unlocked or is_owner %}
            <p><strong>E-mail:</strong> {{ profile.contact_email or "Niet ingevuld" }}</p>
            <p><strong>Telefoon:</strong> {{ profile.phone_number or "Niet ingevuld" }}</p>
            
            {% if profile.cv_document %}
                <p>
                    <strong>CV:</strong>
                    <a href="{{ profile.cv_document }}" target="_blank">
                        Bekijk / download CV
                    </a>
                </p>
            {% else %}
                <p><strong>CV:</strong> Niet ingevuld</p>
            {% endif %}

            {% if is_unlocked %}
                <p style="color: green;">✅ Deze contactgegevens zijn vrijgegeven en permanent zichtbaar.</p>
            {% endif %}
        
        {# Toon UNLOCK-KNOP indien niet ontgrendeld #}
        {% else %}
            <p>De contactgegevens van deze consultant zijn **verborgen**.</p>
            <p><strong>CV:</strong> Verborgen</p>
            <a href="{{ url_for('main.unlock_consultant', profile_id=profile.id) }}" class="btn" onclick="return confirm('Weet u zeker dat u de contactgegevens wilt vrijgeven?')">
                🔒 Ontgrendel contactgegevens (MVP Knop)
            </a>
            <p><small>Door op deze knop te klikken, worden de contactgegevens permanent zichtbaar voor uw bedrijf.</small></p>
        {% endif %}
        
    {# 2. Toon consultant's eigen contactinfo (als ze ingelogd zijn op hun eigen profiel)-> is dit niet overbodig? #}
    {% elif is_owner %} 
        <p><strong>E-mail:</strong> {{ profile.contact_email or "Niet ingevuld" }} (Zichtbaar voor u als eigenaar)</p>
        <p><strong>Telefoon:</strong> {{ profile.phone_number or "Niet ingevuld" }} (Zichtbaar voor u als eigenaar)</p>
        {% if profile.cv_document %}
            <p>
                <strong>CV:</strong>
                <a href="{{ profile.cv_document }}" target="_blank">
                    Bekijk / download CV
                </a>
            </p>
        {% else %}
            <p><strong>CV:</strong> Niet ingevuld</p>
        {% endif %}
        
    {# 3. Fallback: Toon de login/rol-vereiste #}
    {% else %}
        <p>Log in als **Bedrijf** om de contactgegevens te bekijken en te ontgrendelen.</p>
    {% endif %}
</div>
{% endblock %}





{% extends "base.html" %}

{% block title %}Consultant Profielen{% endblock %}

{% block content %}



<h1 class="page-title">Consultant Profielen</h1>



{% set current_sort = sort_by if sort_by is defined else 'relevance' %}



<div class="mode-selector-container">

    <h2 class="h5">Kies uw zoekmodus:</h2>

   

    <a href="{{ url_for('main.consultants_list', sort_by='relevance') }}"

        class="mode-btn {% if current_sort == 'relevance' %}active-mode{% else %}inactive-mode{% endif %}">

        🧠 IConsult Match (Beste Relevantie)

    </a>



    <a href="{{ url_for('main.consultants_list', sort_by='title') }}"

        class="mode-btn {% if current_sort != 'relevance' %}active-mode{% else %}inactive-mode{% endif %}">

        🔧 Handmatige Filter & Sortering

    </a>

</div>



<form method="GET" action="{{ url_for('main.consultants_list') }}" class="filter-form">

   

    <input type="hidden" name="sort_by" value="{{ current_sort }}">



   

    {% if current_sort != 'relevance' %}

        <p class="form-instruction">Gebruik onderstaande velden om handmatig te filteren. Resultaten worden gesorteerd op Naam (A-Z).</p>



        <div class="input-grid manual-filter-grid">

            <input type="text" name="q" placeholder="Zoek op Naam/Specialisatie/Bio" value="{{ request.args.get('q', '') }}">

            <input type="text" name="city" placeholder="Stad" value="{{ request.args.get('city', '') }}">

            <input type="text" name="country" placeholder="Land" value="{{ request.args.get('country', '') }}">

            <div class="empty-col"></div>

        </div>



        <div class="skills-filter">

            <label class="skills-label">Skills (filteren - *Consultant moet alle aangevinkte skills bezitten*):</label>

            <div class="skills-checkboxes">

                {% for skill in skills %}

                    <label class="skill-label">

                        <input type="checkbox" name="skills" value="{{ skill.id }}"

                            {% if request.args.getlist('skills') and skill.id|string in request.args.getlist('skills') %}checked{% endif %}>

                        {{ skill.name }}

                    </label>

                {% endfor %}

            </div>

        </div>

        <button type="submit" class="btn btn-primary apply-btn">Filters Toepassen</button>

        <a href="{{ url_for('main.consultants_list', sort_by='title') }}" class="btn btn-secondary reset-btn">Reset Filters</a>



    {% else %}

        <p class="alert alert-info">

            **Voor een gedetailleerde uitleg over de toegepaste filter- en scoringsmethodologie, verwijzen wij u naar de informatie onderaan deze pagina.**

        </p>

       

        <div class="input-group">

             <input type="text" name="q" placeholder="Verfijn zoekopdracht (wordt meegenomen in de score)" value="{{ request.args.get('q', '') }}">

             <button type="submit" class="btn btn-primary">Zoek & Herbereken Score</button>

        </div>

       

    {% endif %}



</form>



<div class="job-grid" style="margin-top: 20px;">

    {% for c in consultants %}

   

    {# Bepaal de klasse voor de badge op basis van de score #}

    {% if current_sort == 'relevance' and c.score is defined %}

        {% set match_score_perc = (c.score * 100) | round(0) %}

        {% set match_class = 'match-high' %}

        {% if match_score_perc < 20 %}

            {% set match_class = 'match-low' %}

        {% elif match_score_perc >= 20 and match_score_perc <= 30 %}

            {% set match_class = 'match-medium' %}

        {% endif %}

    {% endif %}

   

    <div class="job-card">

           

        <div class="job-meta-top">

            {# VASTE BADGE VOOR CONSULTANT #}

            <span class="contract-type-tag"><i class="fas fa-user-tie"></i> Consultant</span>

           

            {% if c.location_city or c.country %}

                <span class="job-location">

                    <i class="fas fa-map-marker-alt"></i> {{ c.location_city }}{% if c.location_city and c.country %}, {% endif %}{{ c.country }}

                </span>

            {% endif %}

        </div>



        <h3 class="job-title-link">

            <a href="{{ url_for('main.consultant_detail', profile_id=c.id) }}">{{ c.display_name or c.display_name_masked }}</a>

        </h3>

       

        {% if c.specialisation %}

            <p class="company-name">Specialisatie: {{ c.specialisation }}</p>

        {% endif %}



        <div class="required-skills-summary">

            <label class="skills-label-small"><i class="fas fa-tools"></i> Skills Consultant:</label>

            <div class="skill-tags-wrapper">

                {% for skill in c.skills[:3] %}

                    <span class="required-skill-tag">{{ skill.name }}</span>

                {% endfor %}

                {% if c.skills|length > 3 %}

                    <span class="required-skill-tag more-skills"><i class="fas fa-plus-circle"></i> {{ c.skills|length - 3 }} meer</span>

                {% endif %}

            </div>

        </div>

       

        {% if current_sort == 'relevance' and c.score is defined %}

            <div class="score-summary">

               

                {# KLASSE IS DYNAMISCH #}

                <span class="relevance-badge {{ match_class }}">

                    <i class="fas fa-check-circle"></i> Match: **{{ match_score_perc }}%**

                </span>

               

                <details class="breakdown-details">

                    <summary><i class="fas fa-chart-bar"></i> Score Uitsplitsing</summary>

                    <div class="score-breakdown">

                       

                        {% set total_score_perc = (c.score * 100) %}

                       

                        {# SKILLS (50%) #}

                        <div class="bar-item">

                            <span class="bar-label"><i class="fas fa-star"></i> Skills (50%):</span>

                            {# Unweighted score (0-100) voor de breedte van de balk #}

                            {% set skill_unweighted_perc = (c.score_breakdown.skill_factor * 100) if c.score_breakdown.skill_factor is defined else 0 %}

                            {# Weighted score (0-50) voor de weergegeven waarde #}

                            {% set skill_weighted_perc = (c.score_breakdown.skill * 100) if c.score_breakdown.skill is defined else 0 %}

                            <div class="progress-bar-container">

                                <div class="progress-bar skill-bar" style="width: {{ skill_unweighted_perc | round(0) }}%;"></div>

                            </div>

                            <span class="bar-value">{{ skill_weighted_perc | round(0) }}%</span>

                        </div>



                        {# ZOEKTERM (30%) #}

                        <div class="bar-item">

                            <span class="bar-label"><i class="fas fa-search"></i> Zoekterm (30%):</span>

                            {# Unweighted score (0-100) voor de breedte van de balk #}

                            {% set text_unweighted_perc = (c.score_breakdown.text_factor * 100) if c.score_breakdown.text_factor is defined else 0 %}

                            {# Weighted score (0-30) voor de weergegeven waarde #}

                            {% set text_weighted_perc = (c.score_breakdown.text * 100) if c.score_breakdown.text is defined else 0 %}

                            <div class="progress-bar-container">

                                <div class="progress-bar text-bar" style="width: {{ text_unweighted_perc | round(0) }}%;"></div>

                            </div>

                            <span class="bar-value">{{ text_weighted_perc | round(0) }}%</span>

                        </div>



                        {# RECENTHEID (20%) #}

                        <div class="bar-item">

                            <span class="bar-label"><i class="fas fa-clock"></i> Recentheid (20%):</span>

                            {# Unweighted score (0-100) voor de breedte van de balk #}

                            {% set recency_unweighted_perc = (c.score_breakdown.recency_factor * 100) if c.score_breakdown.recency_factor is defined else 0 %}

                            {# Weighted score (0-20) voor de weergegeven waarde #}

                            {% set recency_weighted_perc = (c.score_breakdown.recency * 100) if c.score_breakdown.recency is defined else 0 %}

                            <div class="progress-bar-container">

                                <div class="progress-bar recency-bar" style="width: {{ recency_unweighted_perc | round(0) }}%;"></div>

                            </div>

                            <span class="bar-value">{{ recency_weighted_perc | round(0) }}%</span>

                        </div>

                       

                        <p class="score-total">Totaal: {{ total_score_perc | round(0) }}%</p>

                    </div>

                </details>

            </div>

        {% endif %}

        <a class="btn btn-primary-card" href="{{ url_for('main.consultant_detail', profile_id=c.id) }}">Bekijk Profiel</a>

    </div>

    {% endfor %}

</div>



{% if not consultants %}

    <p class="alert alert-warning">Geen consultants gevonden die overeenkomen met de criteria.</p>

{% endif %}



<style>

/* ------------------------------------------- */

/* --- VERNIEUWDE EN GEOPTIMALISEERDE CSS --- */

/* ------------------------------------------- */



/* 🎯 STIJLEN VOOR MATCH KLEUREN */

.relevance-badge.match-low {

    background: #dc3545 !important; /* Rood */

    border: 1px solid #c82333;

}

.relevance-badge.match-medium {

    background: #ffc107 !important; /* Oranje */

    color: #333 !important; /* Tekstkleur aanpassen voor zichtbaarheid */

    border: 1px solid #e0a800;

}

.relevance-badge.match-high {

    background: #28a745 !important; /* Groen */

    border: 1px solid #1e7e34;

}

/* Standaard .relevance-badge behoudt zijn algemene layout */

.relevance-badge {

    padding: 10px 18px;

    border-radius: 8px;

    font-size: 1.1rem;

    font-weight: 800;

    display: inline-flex;

    align-items: center;

    margin-bottom: 15px;

    box-shadow: 0 4px 6px rgba(0,0,0,0.15);

    margin-left: 0;

    color: white; /* Standaard tekstkleur */

}





/* --- SCORE BREAKDOWN STYLES (Kleur/Balken) --- */

.bar-item {

    display: grid;

    grid-template-columns: 140px 1fr 40px;

    align-items: center;

    gap: 5px;

    margin-bottom: 10px;

}

.progress-bar-container {

    height: 14px;

    border-radius: 7px;

    background-color: #e9ecef;

    overflow: hidden;

    box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);

}

.progress-bar {

    height: 100%;

    border-radius: 7px;

    transition: width 0.4s ease;

    box-shadow: 0 1px 3px rgba(0,0,0,0.1);

    min-width: 5px; /* Zorgt dat balken met 0% of 1% toch zichtbaar zijn */

}



/* Kleuren voor de progress bars */

.skill-bar { background-color: #38c172 !important; } /* Groen */

.text-bar { background-color: #ffc107 !important; } /* Geel/Oranje */

.recency-bar { background-color: #17a2b8 !important; } /* Cyaan/Blauw */



.bar-value {

    font-weight: 700;

    text-align: right;

    font-size: 1.05rem;

}





/* --- Job Kaart & Layout (Uitlijning) --- */



.job-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 25px; }

.job-card {

    background: #ffffff; border: 1px solid #dce6f5; border-radius: 12px; padding: 25px; box-shadow: 0 6px 15px rgba(0,0,0,0.08); transition: transform 0.2s, box-shadow 0.2s;

    display: flex;

    flex-direction: column;

    align-items: flex-start; /* Dwingt links uitlijning af */

}

.job-card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.12); }

.job-meta-top { display: flex; justify-content: space-between; width: 100%; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #f0f4f9; }

.job-location { font-size: 0.95rem; color: #4a6fa1; display: flex; align-items: center; font-weight: 500; }

.job-location i { margin-right: 5px; color: #2b63c6; }

.contract-type-tag { font-size: 0.9rem; background: #dce6f5; color: #2b63c6; padding: 5px 10px; border-radius: 6px; display: inline-flex; align-items: center; font-weight: 600; }

.contract-type-tag i { margin-right: 5px; }



.job-title-link, .company-name {

    width: 100%;

    text-align: left;

}

.job-title-link a {

    color: #2b63c6 !important; text-decoration: none; font-weight: 800; font-size: 1.5rem;

    display: block;

}

.company-name { font-size: 1.05rem; color: #555; margin-bottom: 15px; font-weight: 600; border-bottom: 1px dashed #e0e0e0; padding-bottom: 15px; }



/* Score Summary */

.score-summary {

    margin-top: auto;

    padding-top: 15px;

    border-top: 1px solid #e0e0e0;

    margin-bottom: 15px;

    text-align: left;

    width: 100%;

}



.relevance-badge i { margin-right: 8px; font-size: 1.1em; }

.btn-primary-card { background: #2b63c6; color: white; border: 1px solid #1a4f99; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 700; margin-top: 10px; text-align: center; transition: background 0.2s; align-self: stretch; }

.btn-primary-card:hover { background: #1a4f99; }



/* Skills tags */

.required-skills-summary { margin-bottom: 20px; border-top: 1px dashed #f0f0f0; padding-top: 15px; width: 100%; }

.skills-label-small { font-weight: 700; display: block; margin-bottom: 8px; color: #333; font-size: 0.95rem; }

.skills-label-small i { margin-right: 5px; color: #f6993f; }

.skill-tags-wrapper { display: flex; flex-wrap: wrap; gap: 8px; }

.required-skill-tag { background: #e9f0ff; color: #2b63c6; border: 1px solid #bcd0ff; padding: 5px 10px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; display: inline-flex; align-items: center; }

.more-skills { background: #f0f4f9; border: 1px solid #dce6f5; color: #4a6fa1; }



/* Filter & Mode Stijlen (Niet gewijzigd) */

.page-title { margin-bottom: 20px; }

.mode-selector-container { margin-bottom: 25px; padding-bottom: 15px; border-bottom: 1px solid #e0e0e0; }

.mode-selector-container h2 { margin-bottom: 15px; font-weight: 600; color: #333; }

.mode-btn { padding: 12px 25px; border-radius: 10px; transition: transform 0.2s, box-shadow 0.2s; font-weight: 700; margin-right: 15px; border: 2px solid transparent; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-size: 1.05rem; text-decoration: none; }

.active-mode { background: #2b63c6; color: white; border-color: #1a4f99; box-shadow: 0 4px 8px rgba(43, 99, 198, 0.4); }

.inactive-mode { background: #f0f4f9; color: #2b63c6; border-color: #dce6f5; }

.inactive-mode:hover { background: #e9f0ff; border-color: #bcd0ff; transform: translateY(-1px); }

.filter-form { padding: 25px; border: 1px solid #dce6f5; border-radius: 12px; background: #f9fafe; margin-bottom: 30px; }

.form-instruction { color: #555; margin-bottom: 15px; font-size: 0.95rem; }

.manual-filter-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }

.filter-form input[type="text"] { padding: 12px; border-radius: 8px; width: 100%; box-sizing: border-box; border: 1px solid #dce6f5; }

.input-group { gap: 15px; display: flex; }

.input-group input[type="text"] { flex-grow: 1; padding: 12px; margin: 0;}

.alert-info { padding: 18px; margin-bottom: 25px; font-size: 1.05rem; background: #d9e9ff; border-radius: 8px;}

.skills-filter { margin-top: 15px; margin-bottom: 20px;}

.skills-label { font-weight: 700; display: block; margin-bottom: 10px; color: #333; }

.skills-checkboxes { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }

.skill-label { display: flex; align-items: center; background: #ffffff; border: 1px solid #dce6f5; padding: 10px; border-radius: 8px; font-size: 0.95rem; cursor: pointer; transition: background 0.2s, border-color 0.2s; }

.skill-label input[type="checkbox"] { margin-right: 10px; transform: scale(1.2); accent-color: #2b63c6; }

.skill-label:hover { background: #f0f4f9; }

.btn-primary { background: #2b63c6; color: white; border: 1px solid #1a4f99; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-right: 10px; }

.btn-secondary { background: #e9f0ff; border: 1px solid #bcd0ff; padding: 8px 14px; border-radius: 8px; text-decoration: none; color: #2b63c6; font-weight: 600; }

.reset-btn { color: #555; border: 1px solid #ccc; background: #f0f0f0; margin-top: 10px; align-self: unset; }

.apply-btn { margin-top: 10px; }





/* Score Breakdown details */

.breakdown-details { margin-top: 10px; margin-bottom: 15px; padding: 5px 0; border-top: 1px dashed #e0e0e0; border-bottom: 1px dashed #e0e0e0; font-size: 0.9rem; width: 100%; }

.breakdown-details summary { cursor: pointer; font-weight: 600; color: #4a6fa1; padding: 5px 0; list-style: none; display: flex; align-items: center; }

.breakdown-details summary i { margin-right: 8px; color: #2b63c6; }

.breakdown-details summary::-webkit-details-marker { display: none; }

.breakdown-details summary::before { content: '►'; display: inline-block; font-size: 0.8em; margin-right: 8px; transition: transform 0.2s; }

.breakdown-details[open] summary::before { content: '▼'; transform: rotate(0deg); }

.score-breakdown { padding-top: 10px; padding-left: 0px; }

.bar-label { font-weight: 600; color: #333; display: flex; align-items: center; }

.bar-label i { margin-right: 5px; color: #2b63c6; }

.score-total { font-weight: 700; margin-top: 10px; padding-top: 5px; border-top: 1px solid #e0e0e0; text-align: right; color: #2b63c6; }

</style>



{% endblock %}






{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}

{% block content %}
<h1>Dashboard</h1>

<div class="card">
    <h2>Profiel</h2>

    <p><strong>Ingelogd als:</strong> {{ user.username }}</p>
    <p><strong>Rol:</strong> {{ user.role.value }}</p>

    {% if user.role == UserRole.consultant %}
        {% if profile.profile_image %}
            <img 
                src="{{ profile.profile_image }}" 
                alt="Profielfoto" 
                style="width:140px;height:140px;border-radius:50%;object-fit:cover;margin-bottom:12px;"
            >
        {% else %}
            <img 
                src="{{ url_for('static', filename='img/default-avatar.png') }}" 
                alt="Geen profielfoto"
                style="width:140px;height:140px;border-radius:50%;object-fit:cover;margin-bottom:12px;"
            >
        {% endif %}

        {% if profile.cv_document %}
            <p>
                <strong>CV:</strong>
                <a href="{{ profile.cv_document }}" target="_blank">
                    Bekijk / download CV
                </a>
            </p>
        {% else %}
            <p><strong>CV:</strong> nog niet toegevoegd</p>
        {% endif %}

        <p><strong>Naam:</strong> {{ profile.display_name_masked }}</p>
        <p><strong>Locatie:</strong> {{ profile.location_city }} , {{ profile.country }}</p>
        <p><strong>Opmerking:</strong> {{ profile.headline or "Geen headline" }}</p>

        <p><strong>E-mail:</strong> {{ profile.contact_email or "Niet ingevuld" }}</p>
        <p><strong>Telefoon:</strong> {{ profile.phone_number or "Niet ingevuld" }}</p>

        <p><strong>Skills:</strong>
            {% if profile.skills %}
                {{ profile.skills | map(attribute='name') | join(', ') }}
            {% else %}
                Geen skills geselecteerd
            {% endif %}
        </p>

        <a class="btn" href="{{ url_for('main.edit_consultant_skills') }}">Skills aanpassen</a>
        <a class="btn" href="{{ url_for('main.edit_consultant_profile') }}">Profiel aanpassen</a>
    {% endif %}

    {% if user.role == UserRole.company %}
        <p><strong>Bedrijfsnaam:</strong> {{ company.company_name_masked }}</p>
        <p><strong>Sector:</strong> {{ company.industry or "Niet ingevuld" }}</p>

        <p><strong>E-mail:</strong> {{ company.contact_email or "Niet ingevuld" }}</p>
        <p><strong>Telefoon:</strong> {{ company.phone_number or "Niet ingevuld" }}</p>

        <a class="btn" href="{{ url_for('main.job_new') }}">Nieuwe job posten</a>
        <a href="{{ url_for('main.company_jobs_list') }}">Mijn job posts</a>

        <a class="btn" href="{{ url_for('main.edit_company_profile') }}">Profiel aanpassen</a>
    {% endif %}
</div>
{% endblock %}





{% extends "base.html" %}
{% block title %}Bedrijfsprofiel aanpassen{% endblock %}

{% block content %}
  <h1>Bedrijfsprofiel aanpassen</h1>

  <form method="post">
        
    <label style="display:block; margin-bottom: 10px;">
      Bedrijfsnaam:
      <input
        type="text"
        name="company_name"
        value="{{ company.company_name_masked }}"
        style="width: 300px;"
        required
      >
    </label>

    <label style="display:block; margin-bottom: 10px;">
      Stad:
      <input
        type="text"
        name="location_city"
        value="{{ company.location_city or '' }}"
        style="width: 300px;"
      >
    </label>

    <label style="display:block; margin-bottom: 10px;">
      Land:
      <input
        type="text"
        name="country"
        value="{{ company.country or '' }}"
        style="width: 300px;"
      >
    </label>
    
    <hr style="margin: 20px 0;">
    <h3>Contactinformatie (wordt verborgen getoond)</h3>

    <label style="display:block; margin-bottom: 10px;">
      Contact E-mailadres:
      <input
        type="email"
        name="contact_email"
        value="{{ company.contact_email or '' }}"
        style="width: 300px;"
      >
    </label>

    <label style="display:block; margin-bottom: 10px;">
      Contact Telefoonnummer:
      <input
        type="tel"
        name="phone_number"
        value="{{ company.phone_number or '' }}"
        style="width: 300px;"
      >
    </label>
    <hr style="margin: 20px 0;">


    <button class="btn" type="submit">Opslaan</button>
  </form>
{% endblock %}






{% extends "base.html" %}
{% block title %}Profiel aanpassen{% endblock %}

{% block content %}
  <h1>Profiel aanpassen</h1>

  <form method="post" enctype="multipart/form-data">

    <label style="display:block; margin-bottom: 10px;">
      Naam zichtbaar voor anderen:
      <input
        type="text"
        name="display_name"
        value="{{ profile.display_name }}"
        style="width: 300px;"
        required
      >
    </label>

    <label style="display:block; margin-bottom: 10px;">
      Stad:
      <input
        type="text"
        name="location_city"
        value="{{ profile.location_city }}"
        style="width: 300px;"
      >
    </label>

    <label style="display:block; margin-bottom: 10px;">
      Land:
      <input
        type="text"
        name="country"
        value="{{ profile.country }}"
        style="width: 300px;"
      >
    </label>

    <label style="display:block; margin-bottom: 10px;">
      Headline:
      <input
        type="text"
        name="headline"
        value="{{ profile.headline }}"
        style="width: 300px;"
      >
    </label>
    <hr style="margin: 20px 0;">
    <h3>Contactinformatie (wordt verborgen getoond)</h3>

    <label style="display:block; margin-bottom: 10px;">
      E-mailadres:
      <input
        type="email"
        name="contact_email"
        value="{{ profile.contact_email or '' }}"
        style="width: 300px;"
      >
    </label>

    <label style="display:block; margin-bottom: 10px;">
      Telefoonnummer:
      <input
        type="tel"
        name="phone_number"
        value="{{ profile.phone_number or '' }}"
        style="width: 300px;"
      >
    </label>
    <hr style="margin: 20px 0;">
    <label style="display:block; margin-bottom: 10px;">
      Profielfoto:
      <input
        type="file"
        name="profile_image"
        accept="image/*"
      >
    </label>

    <label style="display:block; margin-bottom: 10px;">
      CV / Document:
      <input
        type="file"
        name="cv_document"
        accept=".pdf,.doc,.docx"
      >
    </label>

    <button class="btn" type="submit">Opslaan</button>
  </form>
{% endblock %}





{% extends "base.html" %}
{% block title %}Skills aanpassen{% endblock %}
{% block content %}
  <h1>Kies je skills</h1>

  <form method="post">
    {% for skill in skills %}
      <label style="display:block;">
        <input
          type="checkbox"
          name="skills"
          value="{{ skill.id }}"
          {% if skill in profile.skills %}checked{% endif %}
        >
        {{ skill.name }}
      </label>
    {% endfor %}

    <button class="btn" type="submit">Opslaan</button>
  </form>
{% endblock %}




{% extends "base.html" %}
{% block title %}{{ _("Home") }}{% endblock %}
{% block content %}
  <h1>{{ _("Home") }}</h1>
  <p>{{ _("Welcome! Use the navigation above.") }}</p>
{% endblock %}



{% extends "base.html" %}
{% block title %}{{ job.title }}{% endblock %}
{% block content %}

<h1 class="page-title">{{ job.title }}</h1>

<div class="card">
    <h2>Contactgegevens van het Bedrijf</h2>
    
    {# 1. Controleert: Is de bezoeker een Consultant? #}
    {% if user and user.role == UserRole.consultant %}
        
        {# Toon contactgegevens indien ONTGRENDELD of de EIGENAAR #}
        {% if is_unlocked or is_owner %}
            <p><strong>Bedrijf:</strong> {{ job.company.company_name_masked }}</p>
            <p><strong>E-mail:</strong> {{ job.company.contact_email or "Niet ingevuld" }}</p>
            <p><strong>Telefoon:</strong> {{ job.company.phone_number or "Niet ingevuld" }}</p>
            {% if is_unlocked %}
                <p style="color: green;">✅ Deze contactgegevens zijn vrijgegeven en permanent zichtbaar.</p>
            {% endif %}
            
        {# Toon UNLOCK-KNOP indien niet ontgrendeld #}
        {% else %}
            <p>De contactgegevens van dit bedrijf zijn **verborgen**.</p>
            <a href="{{ url_for('main.unlock_job', job_id=job.id) }}" class="btn" onclick="return confirm('Weet u zeker dat u de contactgegevens wilt vrijgeven?')">
                🔒 Ontgrendel contactgegevens (MVP Knop)
            </a>
            <p><small>Door op deze knop te klikken, worden de contactgegevens permanent zichtbaar voor uw profiel.</small></p>
        {% endif %}
        
    {# 2. Toon bedrijf's eigen contactinfo (als ze de job gepost hebben) #}
    {% elif is_owner %}
        <p><strong>Bedrijf:</strong> {{ job.company.company_name_masked }}</p>
        <p><strong>E-mail:</strong> {{ job.company.contact_email or "Niet ingevuld" }} (Zichtbaar voor u als eigenaar)</p>
        <p><strong>Telefoon:</strong> {{ job.company.phone_number or "Niet ingevuld" }} (Zichtbaar voor u als eigenaar)</p>
        
    {# 3. Fallback: Toon de login/rol-vereiste #}
    {% else %}
        <p>Log in als **Consultant** om de contactgegevens te bekijken en te ontgrendelen.</p>
    {% endif %}
</div>

<div class="job-detail-card">
    <div class="job-section">
        <h3>Beschrijving</h3>
        <p>{{ job.description or "Geen beschrijving beschikbaar." }}</p>
    </div>

    <div class="job-section">
        <h3>Locatie</h3>
        <p>
            {{ job.location_city }}
            {% if job.location_city and job.country %}, {% endif %}
            {{ job.country }}
        </p>
    </div>

    <div class="job-section">
        <h3>Contracttype</h3>
        <p>{{ job.contract_type or "Niet opgegeven" }}</p>
    </div>

    <div class="job-section">
        <h3>Vereiste skills</h3>
        {% if job.skills %}
            <div class="skill-list">
                {% for s in job.skills %}
                    <span class="skill-tag">{{ s.name }}</span>
                {% endfor %}
            </div>
        {% else %}
            <p>Geen specifieke skills opgegeven.</p>
        {% endif %}
    </div>

    {% if user and user.role == UserRole.company and company and job.company_id == company.id %}
        <div class="job-actions">
            <a class="btn btn-primary" href="{{ url_for('main.job_edit', job_id=job.id) }}">
                Bewerken
            </a>

            <form action="{{ url_for('main.job_delete', job_id=job.id) }}" method="post" style="display:inline;">
                <button class="btn btn-danger" onclick="return confirm('Zeker verwijderen?')">
                    Verwijderen
                </button>
            </form>
        </div>
    {% endif %}
</div>

<style>
    .job-detail-card {
        background: #ffffff;
        border: 1px solid #dce6f5;
        border-radius: 14px;
        padding: 24px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        display: flex;
        flex-direction: column;
        gap: 20px;
    }

    .job-section h3 {
        margin-bottom: 6px;
        color: #2b63c6;
    }

    .skill-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }

    .skill-tag {
        background: #e9f0ff;
        border: 1px solid #c5d6f5;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 0.9rem;
        color: #2b63c6;
    }

    .job-actions {
        margin-top: 12px;
        display: flex;
        gap: 10px;
    }

    .btn-primary {
        background: #2b63c6;
        color: white;
        padding: 8px 14px;
        border-radius: 8px;
        text-decoration: none;
        border: none;
        cursor: pointer;
    }

    .btn-danger {
        background: #e24b4b;
        color: white;
        padding: 8px 14px;
        border-radius: 8px;
        border: none;
        cursor: pointer;
    }
</style>

{% endblock %}







{% extends "base.html" %}
{% block title %}Job Bewerken{% endblock %}

{% block content %}

<h1 class="page-title">Job Bewerken</h1>

<div class="form-card">
    <form method="POST">
        
        <label>Titel</label>
        <input type="text" name="title" value="{{ job.title }}" required>

        <label>Beschrijving</label>
        <textarea name="description" rows="5">{{ job.description }}</textarea>

        <label>Locatie — Stad</label>
        <input type="text" name="location_city" value="{{ job.location_city }}">

        <label>Locatie — Land</label>
        <input type="text" name="country" value="{{ job.country }}">

        <label>Contracttype</label>
        <input type="text" name="contract_type" value="{{ job.contract_type }}">

        <label>Skills</label>
        <div class="skills-box">
            {% for s in skills %}
                <label class="skill-checkbox">
                    <input
                        type="checkbox"
                        name="skills"
                        value="{{ s.id }}"
                        {% if s in job.skills %}checked{% endif %}
                    >
                    {{ s.name }}
                </label>
            {% endfor %}
        </div>

        <button class="btn-primary" type="submit">Opslaan</button>
        <a href="{{ url_for('main.job_detail', job_id=job.id) }}" class="btn-secondary">Annuleren</a>
    </form>
</div>

<style>
    .page-title {
        margin-bottom: 22px;
    }

    .form-card {
        background: #ffffff;
        border: 1px solid #dce6f5;
        border-radius: 14px;
        padding: 22px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        max-width: 650px;
    }

    form {
        display: flex;
        flex-direction: column;
        gap: 14px;
    }

    input, textarea, select {
        width: 100%;
        padding: 8px 10px;
        border-radius: 6px;
        border: 1px solid #bfcde8;
    }

    .skills-box {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        padding: 10px;
        border-radius: 10px;
        border: 1px solid #dce6f5;
        background: #f7f9ff;
    }

    .skill-checkbox {
        background: #ffffff;
        border: 1px solid #cddaf3;
        padding: 6px 10px;
        border-radius: 8px;
        font-size: 0.9rem;
    }

    .btn-primary {
        background: #2b63c6;
        color: white;
        padding: 10px 16px;
        border-radius: 8px;
        border: none;
        cursor: pointer;
        text-align: center;
        text-decoration: none;
        margin-top: 10px;
    }

    .btn-secondary {
        background: #e9f0ff;
        border: 1px solid #c5d6f5;
        color: #2b63c6;
        padding: 10px 16px;
        border-radius: 8px;
        text-decoration: none;
        text-align: center;
    }
</style>

{% endblock %}





{% extends "base.html" %}
{% block title %}Vacatures | Job Lijst{% endblock %}
{% block content %}

<h1 class="page-title">Vacatures</h1>

{% set current_sort = sort_by if sort_by is defined else 'relevance' %}

<div class="mode-selector-container">
    <h2 class="h5">Kies uw zoekmodus:</h2>
    
    <a href="{{ url_for('main.jobs_list', sort_by='relevance') }}" 
        class="mode-btn {% if current_sort == 'relevance' %}active-mode{% else %}inactive-mode{% endif %}">
        🧠 IConsult Match (Beste Relevantie)
    </a>

    <a href="{{ url_for('main.jobs_list', sort_by='title') }}" 
        class="mode-btn {% if current_sort != 'relevance' %}active-mode{% else %}inactive-mode{% endif %}">
        🔧 Handmatige Filter & Sortering
    </a>
</div>

<form method="GET" action="{{ url_for('main.jobs_list') }}" class="filter-form">
    
    <input type="hidden" name="sort_by" value="{{ current_sort }}">

    
    {% if current_sort != 'relevance' %}
        <p class="form-instruction">Gebruik onderstaande velden om handmatig te filteren. Resultaten worden gesorteerd op Titel (A-Z).</p>

        <div class="input-grid manual-filter-grid">
            <input type="text" name="q" placeholder="Zoek op Titel/Omschrijving" value="{{ request.args.get('q', '') }}">
            <input type="text" name="city" placeholder="Stad" value="{{ request.args.get('city', '') }}">
            <input type="text" name="country" placeholder="Land" value="{{ request.args.get('country', '') }}">
            
            {# 🌟 CONTRACT TYPE DROPDOWN - GEEN AUTOMATISCHE SUBMIT 🌟 #}
            <select name="contract_type" id="contract_type" class="form-control-select">
                <option value="">Contract type (Alle)</option>
                {% for value, label in possible_contract_types %}
                    <option value="{{ value }}" 
                            {% if current_contract_type == value %}selected{% endif %}>
                        {{ label }}
                    </option>
                {% endfor %}
            </select>
            {# 💡 End GECORRIGEERD #}

        </div>

        <div class="skills-filter">
            <label class="skills-label">Skills (filteren - *vink de vereiste skills aan*):</label>
            <div class="skills-checkboxes">
                {% for skill in skills %}
                    <label class="skill-label">
                        <input type="checkbox" name="skills" value="{{ skill.id }}"
                            {% if request.args.getlist('skills') and skill.id|string in request.args.getlist('skills') %}checked{% endif %}>
                        {{ skill.name }}
                    </label>
                {% endfor %}
            </div>
        </div>
        <button type="submit" class="btn btn-primary apply-btn">Filters Toepassen</button>
        <a href="{{ url_for('main.jobs_list', sort_by='title') }}" class="btn btn-secondary reset-btn">Reset Filters</a>

    {% else %}
        {# 🎯 AANGEPASTE TEKST VOOR PROFESSIONELE REFERENTIE #}
        <p class="alert alert-info">
            **Voor een gedetailleerde uitleg over de toegepaste filter- en scoringsmethodologie, verwijzen wij u naar de informatie onderaan deze pagina.**
        </p>
        
        <div class="input-group">
             <input type="text" name="q" placeholder="Verfijn zoekopdracht (wordt meegenomen in de score)" value="{{ request.args.get('q', '') }}">
             <button type="submit" class="btn btn-primary">Zoek & Herbereken Score</button>
        </div>
        
    {% endif %}

</form>

<div class="job-grid" style="margin-top: 20px;">
    {% for job in jobs %}
    
    {# Opgeloste logica: Alle score-logica is binnen de relevante check geplaatst. #}
    {% if current_sort == 'relevance' and job.score is defined %}
        {% set match_score_perc = (job.score * 100) | round(0) %}
        {% set match_class = 'match-high' %}
        {% if match_score_perc < 20 %}
            {% set match_class = 'match-low' %}
        {% elif match_score_perc >= 20 and match_score_perc <= 30 %}
            {% set match_class = 'match-medium' %}
        {% endif %}
    {% endif %}
    
    <div class="job-card">
            
            <div class="job-meta-top">
            {% if job.contract_type %}
                <span class="contract-type-tag"><i class="fas fa-file-contract"></i> {{ job.contract_type }}</span>
            {% endif %}
            
            {% if job.location_city or job.country %}
                <span class="job-location">
                    <i class="fas fa-map-marker-alt"></i> {{ job.location_city }}{% if job.location_city and job.country %}, {% endif %}{{ job.country }}
                </span>
            {% endif %}
        </div>

            <h3 class="job-title-link">
            <a href="{{ url_for('main.job_detail', job_id=job.id) }}">{{ job.title }}</a>
             </h3> 
        
            {% if job.company %}
            <p class="company-name">{{ job.company.company_name_masked }}</p>
          {% endif %}

            <div class="required-skills-summary">
            <label class="skills-label-small"><i class="fas fa-tools"></i> Vereiste Skills:</label>
            <div class="skill-tags-wrapper">
                {% for skill in job.skills[:3] %}
                    <span class="required-skill-tag">{{ skill.name }}</span>
                {% endfor %}
                {% if job.skills|length > 3 %}
                    <span class="required-skill-tag more-skills"><i class="fas fa-plus-circle"></i> {{ job.skills|length - 3 }} meer</span>
                {% endif %}
            </div>
        </div>
        
            {% if current_sort == 'relevance' and job.score is defined %}
            <div class="score-summary">
                
                {# KLASSE IS DYNAMISCH #}
                <span class="relevance-badge {{ match_class }}">
                    <i class="fas fa-check-circle"></i> Match: **{{ match_score_perc }}%**
                </span>
                
                <details class="breakdown-details">
                    <summary><i class="fas fa-chart-bar"></i> Score Uitsplitsing</summary>
                    <div class="score-breakdown">
                        
                        {% set total_score_perc = (job.score * 100) %}
                        
                        <div class="bar-item">
                            <span class="bar-label"><i class="fas fa-star"></i> Skills (50%):</span>
                            {% set score_perc = (job.score_breakdown.skill * 100) %}
                            <div class="progress-bar-container">
                                <div class="progress-bar skill-bar" style="width: {{ score_perc | round(0) }}%;"></div>
                            </div>
                            <span class="bar-value">{{ score_perc | round(0) }}%</span>
                        </div>

                        <div class="bar-item">
                            <span class="bar-label"><i class="fas fa-search"></i> Zoekterm (30%):</span>
                            {% set score_perc = (job.score_breakdown.text * 100) %}
                            <div class="progress-bar-container">
                                <div class="progress-bar text-bar" style="width: {{ score_perc | round(0) }}%;"></div>
                            </div>
                            <span class="bar-value">{{ score_perc | round(0) }}%</span>
                        </div>

                        <div class="bar-item">
                            <span class="bar-label"><i class="fas fa-clock"></i> Recentheid (20%):</span>
                            {% set score_perc = (job.score_breakdown.recency * 100) %}
                            <div class="progress-bar-container">
                                <div class="progress-bar recency-bar" style="width: {{ score_perc | round(0) }}%;"></div>
                            </div>
                            <span class="bar-value">{{ score_perc | round(0) }}%</span>
                        </div>
                        
                        <p class="score-total">Totaal: {{ total_score_perc | round(0) }}%</p>
                    </div>
                </details>
            </div>
          {% endif %}
            <a class="btn btn-primary-card" href="{{ url_for('main.job_detail', job_id=job.id) }}">Bekijk Vacature</a>
    </div>
    {% endfor %}
</div>

{% if not jobs %}
    <p class="alert alert-warning">Geen vacatures gevonden die overeenkomen met de criteria.</p>
{% endif %}

<style>
/* ------------------------------------------- */
/* --- VERNIEUWDE EN GEOPTIMALISEERDE CSS --- */
/* ------------------------------------------- */

/* 🎯 STIJLEN VOOR MATCH KLEUREN */
.relevance-badge.match-low { 
    background: #dc3545 !important; /* Rood */
    border: 1px solid #c82333;
}
.relevance-badge.match-medium { 
    background: #ffc107 !important; /* Oranje */
    color: #333 !important; /* Tekstkleur aanpassen voor zichtbaarheid */
    border: 1px solid #e0a800;
}
.relevance-badge.match-high { 
    background: #28a745 !important; /* Groen */
    border: 1px solid #1e7e34;
}
/* Standaard .relevance-badge behoudt zijn algemene layout */
.relevance-badge { 
    padding: 10px 18px; 
    border-radius: 8px; 
    font-size: 1.1rem; 
    font-weight: 800; 
    display: inline-flex; 
    align-items: center; 
    margin-bottom: 15px; 
    box-shadow: 0 4px 6px rgba(0,0,0,0.15); 
    margin-left: 0; 
    color: white; /* Standaard tekstkleur */
}


/* --- SCORE BREAKDOWN STYLES (Kleur/Balken) --- */
.bar-item {
    display: grid; 
    grid-template-columns: 140px 1fr 40px; 
    align-items: center; 
    gap: 5px; 
    margin-bottom: 10px;
}
.progress-bar-container {
    height: 14px; 
    border-radius: 7px;
    background-color: #e9ecef; 
    overflow: hidden; 
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
}
.progress-bar {
    height: 100%; 
    border-radius: 7px;
    transition: width 0.4s ease;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1); 
    min-width: 5px; /* Zorgt dat balken met 0% of 1% toch zichtbaar zijn */
}

/* Kleuren voor de progress bars */
.skill-bar { background-color: #38c172 !important; } /* Groen */
.text-bar { background-color: #ffc107 !important; } /* Geel/Oranje */
.recency-bar { background-color: #17a2b8 !important; } /* Cyaan/Blauw */

.bar-value { 
    font-weight: 700; 
    text-align: right; 
    font-size: 1.05rem; 
}


/* --- Job Kaart & Layout (Uitlijning) --- */

.job-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 25px; }
.job-card {
    background: #ffffff; border: 1px solid #dce6f5; border-radius: 12px; padding: 25px; box-shadow: 0 6px 15px rgba(0,0,0,0.08); transition: transform 0.2s, box-shadow 0.2s; 
    display: flex; 
    flex-direction: column; 
    align-items: flex-start; /* Dwingt links uitlijning af */
}
.job-card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.12); }
.job-meta-top { display: flex; justify-content: space-between; width: 100%; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #f0f4f9; }
.job-location { font-size: 0.95rem; color: #4a6fa1; display: flex; align-items: center; font-weight: 500; }
.job-location i { margin-right: 5px; color: #2b63c6; }
.contract-type-tag { font-size: 0.9rem; background: #dce6f5; color: #2b63c6; padding: 5px 10px; border-radius: 6px; display: inline-flex; align-items: center; font-weight: 600; }
.contract-type-tag i { margin-right: 5px; }

.job-title-link, .company-name { 
    width: 100%; 
    text-align: left; 
}
.job-title-link a { 
    color: #2b63c6 !important; text-decoration: none; font-weight: 800; font-size: 1.5rem; 
    display: block; 
}
.company-name { font-size: 1.05rem; color: #555; margin-bottom: 15px; font-weight: 600; border-bottom: 1px dashed #e0e0e0; padding-bottom: 15px; }

/* Score Summary */
.score-summary { 
    margin-top: auto; 
    padding-top: 15px; 
    border-top: 1px solid #e0e0e0; 
    margin-bottom: 15px; 
    text-align: left; 
    width: 100%; 
}

.relevance-badge i { margin-right: 8px; font-size: 1.1em; }
.btn-primary-card { background: #2b63c6; color: white; border: 1px solid #1a4f99; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 700; margin-top: 10px; text-align: center; transition: background 0.2s; align-self: stretch; }
.btn-primary-card:hover { background: #1a4f99; }

/* Skills tags */
.required-skills-summary { margin-bottom: 20px; border-top: 1px dashed #f0f0f0; padding-top: 15px; width: 100%; }
.skills-label-small { font-weight: 700; display: block; margin-bottom: 8px; color: #333; font-size: 0.95rem; }
.skills-label-small i { margin-right: 5px; color: #f6993f; }
.skill-tags-wrapper { display: flex; flex-wrap: wrap; gap: 8px; }
.required-skill-tag { background: #e9f0ff; color: #2b63c6; border: 1px solid #bcd0ff; padding: 5px 10px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; display: inline-flex; align-items: center; }
.more-skills { background: #f0f4f9; border: 1px solid #dce6f5; color: #4a6fa1; }

/* Filter & Mode Stijlen (Niet gewijzigd) */
.page-title { margin-bottom: 20px; }
.mode-selector-container { margin-bottom: 25px; padding-bottom: 15px; border-bottom: 1px solid #e0e0e0; }
.mode-selector-container h2 { margin-bottom: 15px; font-weight: 600; color: #333; }
.mode-btn { padding: 12px 25px; border-radius: 10px; transition: transform 0.2s, box-shadow 0.2s; font-weight: 700; margin-right: 15px; border: 2px solid transparent; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-size: 1.05rem; text-decoration: none; }
.active-mode { background: #2b63c6; color: white; border-color: #1a4f99; box-shadow: 0 4px 8px rgba(43, 99, 198, 0.4); }
.inactive-mode { background: #f0f4f9; color: #2b63c6; border-color: #dce6f5; }
.inactive-mode:hover { background: #e9f0ff; border-color: #bcd0ff; transform: translateY(-1px); }
.filter-form { padding: 25px; border: 1px solid #dce6f5; border-radius: 12px; background: #f9fafe; margin-bottom: 30px; }
.form-instruction { color: #555; margin-bottom: 15px; font-size: 0.95rem; }
.manual-filter-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
.filter-form input[type="text"] { padding: 12px; border-radius: 8px; width: 100%; box-sizing: border-box; border: 1px solid #dce6f5; }
/* 💡 Stijl voor de select dropdown in de handmatige filter */
.filter-form .form-control-select { padding: 12px; border-radius: 8px; width: 100%; box-sizing: border-box; border: 1px solid #dce6f5; background-color: white; appearance: menulist; /* Zorgt ervoor dat het eruit ziet als een dropdown */ }
.input-group { gap: 15px; display: flex; }
.input-group input[type="text"] { flex-grow: 1; padding: 12px; margin: 0;}
.alert-info { padding: 18px; margin-bottom: 25px; font-size: 1.05rem; background: #d9e9ff; border-radius: 8px;}
.skills-filter { margin-top: 15px; margin-bottom: 20px;}
.skills-label { font-weight: 700; display: block; margin-bottom: 10px; color: #333; }
.skills-checkboxes { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
.skill-label { display: flex; align-items: center; background: #ffffff; border: 1px solid #dce6f5; padding: 10px; border-radius: 8px; font-size: 0.95rem; cursor: pointer; transition: background 0.2s, border-color 0.2s; }
.skill-label input[type="checkbox"] { margin-right: 10px; transform: scale(1.2); accent-color: #2b63c6; }
.skill-label:hover { background: #f0f4f9; }
.btn-primary { background: #2b63c6; color: white; border: 1px solid #1a4f99; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-right: 10px; }
.btn-secondary { background: #e9f0ff; border: 1px solid #bcd0ff; padding: 8px 14px; border-radius: 8px; text-decoration: none; color: #2b63c6; font-weight: 600; }
.reset-btn { color: #555; border: 1px solid #ccc; background: #f0f0f0; margin-top: 10px; align-self: unset; }
.apply-btn { margin-top: 10px; }


/* Score Breakdown details */
.breakdown-details { margin-top: 10px; margin-bottom: 15px; padding: 5px 0; border-top: 1px dashed #e0e0e0; border-bottom: 1px dashed #e0e0e0; font-size: 0.9rem; width: 100%; }
.breakdown-details summary { cursor: pointer; font-weight: 600; color: #4a6fa1; padding: 5px 0; list-style: none; display: flex; align-items: center; }
.breakdown-details summary i { margin-right: 8px; color: #2b63c6; }
.breakdown-details summary::-webkit-details-marker { display: none; }
.breakdown-details summary::before { content: '►'; display: inline-block; font-size: 0.8em; margin-right: 8px; transition: transform 0.2s; }
.breakdown-details[open] summary::before { content: '▼'; transform: rotate(0deg); }
.score-breakdown { padding-top: 10px; padding-left: 0px; }
.bar-label { font-weight: 600; color: #333; display: flex; align-items: center; }
.bar-label i { margin-right: 5px; color: #2b63c6; }
.score-total { font-weight: 700; margin-top: 10px; padding-top: 5px; border-top: 1px solid #e0e0e0; text-align: right; color: #2b63c6; }
</style>

{% endblock %}







{% extends "base.html" %}
{# Opmerking: Ik verwijderde {% from 'macros.html' import render_field %} omdat deze hier niet gebruikt wordt in jouw code. #}
{% block title %}{{ _("Create New Job Post") }}{% endblock %}

{% block content %}
<div class="container my-5">
    <h1 class="mb-4">{{ _("Post a New Job") }}</h1>

    <form method="POST" action="{{ url_for('main.job_new') }}" class="card p-4 shadow-sm">
        
        <div class="mb-3">
            <label for="title" class="form-label"><strong>{{ _("Job Title") }}</strong></label>
            <input type="text" id="title" name="title" class="form-control" required value="{{ request.form.get('title', '') }}">
        </div>

        <div class="mb-3">
            <label for="description" class="form-label"><strong>{{ _("Description") }}</strong></label>
            <textarea id="description" name="description" class="form-control" rows="6" required>{{ request.form.get('description', '') }}</textarea>
        </div>

        <div class="row">
            <div class="col-md-6 mb-3">
                <label for="location_city" class="form-label"><strong>{{ _("City") }}</strong></label>
                <input type="text" id="location_city" name="location_city" class="form-control" value="{{ request.form.get('location_city', '') }}">
            </div>
            <div class="col-md-6 mb-3">
                <label for="country" class="form-label"><strong>{{ _("Country") }}</strong></label>
                <input type="text" id="country" name="country" class="form-control" value="{{ request.form.get('country', '') }}">
            </div>
        </div>
        
        <div class="mb-4">
            <label for="contract_type" class="form-label"><strong>{{ _("Contract Type") }}</strong></label>
            <select id="contract_type" name="contract_type" class="form-select">
                <option value="Freelance" {% if request.form.get('contract_type') == 'Freelance' or not request.form.get('contract_type') %}selected{% endif %}>{{ _("Freelance") }}</option>
                <option value="Full-time" {% if request.form.get('contract_type') == 'Full-time' %}selected{% endif %}>{{ _("Full-time") }}</option>
                <option value="Part-time" {% if request.form.get('contract_type') == 'Part-time' %}selected{% endif %}>{{ _("Part-time") }}</option>
                <option value="Project-based" {% if request.form.get('contract_type') == 'Project-based' %}selected{% endif %}>{{ _("Project-based") }}</option>
            </select>
        </div>
        
        <h3 class="mt-4 mb-3">{{ _("Required Skills") }}</h3>
        <p class="text-muted">{{ _("Select all skills required for this job.") }}</p>
        
        <div class="row row-cols-md-3 g-3 mb-4">
            {% set selected_skills = request.form.getlist('skills') | map('int') | list %}
            {% for skill in skills %}
            <div class="col">
                <div class="form-check">
                    <input 
                        class="form-check-input" 
                        type="checkbox" 
                        name="skills" 
                        value="{{ skill.id }}" 
                        id="skill_{{ skill.id }}"
                        {% if skill.id in selected_skills %}checked{% endif %}
                    >
                    <label class="form-check-label" for="skill_{{ skill.id }}">
                        {{ skill.name }}
                    </label>
                </div>
            </div>
            {% endfor %}
        </div>

        <button type="submit" class="btn btn-primary btn-lg mt-3">{{ _("Post Job") }}</button>
    </form>
</div>
{% endblock %}





{% extends "base.html" %}
{% block title %}Login{% endblock %}
{% block content %}
  <h1>Login (MVP)</h1>
  <form method="post">
    <label>Username</label>
    <input name="username" required>

    <label>Rol</label>
    <select name="role">
      <option value="consultant">consultant</option>
      <option value="company">company</option>
    </select>

    <button class="btn" type="submit">Inloggen</button>
  </form>
{% endblock %}
#loginpagina en doorgestuurd nr dashboard 
