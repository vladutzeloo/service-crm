# Service App Context Pack

Acest fișier trebuie folosit ca punct unic de context pentru Claude Code / Gemini / Cursor atunci când se lucrează la aplicația standalone de service.

## De ce merită acest fișier

Da — este mai bine să existe un fișier `.md` central care adună linkuri către skill-uri, fișierele exacte din `oee-calculator2.0` care definesc design language-ul, regulile arhitecturale și prompturile de lucru. Fișierele de context precum `CLAUDE.md` sau `AGENTS.md` sunt recomandate tocmai pentru a centraliza structura proiectului, convențiile, comenzile de validare și documentația la care agentul trebuie să se raporteze.[cite:115][cite:121]

Un astfel de fișier reduce răspunsurile contradictorii, scade riscul ca agentul să „ghicească” stilul proiectului și face contextul reutilizabil între mai multe tool-uri AI.[cite:115][cite:123] Repozitoriul oficial Anthropic pentru skills descrie skill-urile ca foldere de instrucțiuni și resurse care îl ajută pe Claude să execute sarcini specializate în mod repetabil, deci are sens să le legi direct într-un fișier de context de proiect.[cite:118][cite:122]

## Cum să-l folosești

- Păstrează acest fișier în rădăcina repo-ului nou, de exemplu `CLAUDE.md` sau `AGENTS.md`.
- Dacă vrei compatibilitate între mai multe tool-uri, poți păstra un fișier principal tool-agnostic și să îl referențiezi din fișierele specifice fiecărui agent.[cite:121]
- Actualizează-l de fiecare dată când se schimbă structura UI, comenzile de test sau fișierele-sursă de design.[cite:115]

## 1. Project goal

Construim o aplicație standalone de service management pentru echipa de service, dar folosind exact design language-ul din `oee-calculator2.0`.

### Reguli fixe

- Standalone codebase, standalone database, standalone auth.
- UI derivat din `oee-calculator2.0`, nu design nou.
- Light mode default.
- Dashboard compact, Power BI-like.
- Fără gradient junk, fără neon, fără emoji icons.
- Fără left sidebar în ecranele principale ale tehnicienilor.
- Flask + Jinja + SQLAlchemy + Alembic + pytest.
- Explore -> Plan -> Execute. Nu scrie cod înainte de aprobarea arhitecturii.

## 2. UI source of truth

Completează cu linkurile exacte din repo-ul tău. Acestea trebuie tratate ca sursa de adevăr pentru limbajul vizual.

### Repo principal UI

- Main repo: `https://github.com/<user>/oee-calculator2.0`
- Branch de referință: `<main-or-specific-branch>`

### Fișiere cheie de urmărit

- `templates/base.html` — shell global, topbar, layout.
- `templates/admin/dashboard.html` — dashboard compact și ierarhie KPI.
- `static/css/style.css` — tokens, surfaces, buttons, tables, cards.
- `templates/...` pagini care exprimă cel mai bine list/detail/filter patterns.

### Fișiere exacte

Înlocuiește placeholder-ele de mai jos cu linkuri directe GitHub către fișierele exacte:

- Base layout: `<LINK EXACT base.html>`
- Main dashboard: `<LINK EXACT dashboard.html>`
- Global CSS: `<LINK EXACT style.css>`
- Best table/list page: `<LINK EXACT file>`
- Best detail page: `<LINK EXACT file>`
- Best filter/search page: `<LINK EXACT file>`

### Reguli de UI pentru agent

- Refolosește exact structura vizuală din fișierele de mai sus.
- Nu inventa un nou design system.
- Nu înlocui stilul existent cu component libraries arbitrare.
- Orice componentă nouă trebuie să pară că aparține nativ în oee-calculator.

## 3. Service app scope

### Module v1

- Clients
- Contacts
- Locations
- Equipment / installed base
- Service tickets
- Interventions
- Parts used
- Checklist templates
- Checklist runs
- Procedures / SOP
- Maintenance planning
- Technician calendar / capacity

### Dashboard v1

- Clienți activi
- Tichete active
- Intervenții azi
- Utilaje cu mentenanță scadentă
- Capacitate tehnicieni
- Ultimele intervenții

## 4. Architecture rules

- Repo separat: de ex. `service-hub`.
- Nu importa logică business din oee-calculator; doar limbajul UI și pattern-uri de templating.
- Păstrează module clare: `clients`, `equipment`, `tickets`, `maintenance`, `knowledge`.
- Orice integrare viitoare cu VMES/OEE se face prin API sau sync jobs, nu prin coupling direct în v1.
- Alembic pentru migrații, pytest pentru teste, services layer pentru logică, routers subțiri.

## 5. Skills / repos utile

### Repozitorii skills

- Anthropic official skills repo: `https://github.com/anthropics/skills` [cite:118][cite:122]
- Skills README: `https://github.com/anthropics/skills/blob/main/README.md` [cite:118]
- Community collection: `https://github.com/travisvn/awesome-claude-skills`

### Tipuri de skills utile pentru acest proiect

- architecture / planning
- frontend design
- testing
- code review
- deployment
- documentation

### Ce să cauți într-un skill

- instrucțiuni clare și repetitive pentru un tip de muncă;
- exemple de input/output;
- constrângeri explicite;
- resurse sau scripturi auxiliare.[cite:118][cite:122]

## 6. Recommended context files

Poți organiza contextul astfel:

- `AGENTS.md` sau `CLAUDE.md` la root pentru overview general și reguli globale.[cite:115][cite:121]
- `docs/service-domain.md` pentru workflow-urile de business.
- `docs/ui-reference.md` pentru mapping între fișierele din `oee-calculator2.0` și noua aplicație.
- `docs/implementation-plan.md` pentru task-uri și faze.

O structură modulară pe mai multe fișiere este recomandată pentru codebase-uri mai mari, cu un fișier root care face trimitere la documentația detaliată.[cite:115]

## 7. Suggested prompt workflow

### Prompt 1 — Architecture only

```text
Read this context file first.
Then audit the referenced oee-calculator2.0 UI files.
Do not code yet.
Extract the reusable design language, propose the standalone repo structure,
propose the SQLAlchemy models for the service domain,
and list which files should be adapted vs created from scratch.
Wait for approval.
```

### Prompt 2 — UI foundation only

```text
Read this context file first.
Use the referenced oee-calculator2.0 files as the UI source of truth.
Implement only the shared UI foundation for the standalone service app:
base.html, style.css, topbar, KPI cards, tables, filters, form shell, tabs shell.
No business logic beyond placeholders.
Do not invent a new design system.
```

### Prompt 3 — Data model

```text
Read this context file first.
Implement the SQLAlchemy models and Alembic migration for:
Client, Contact, Location, Equipment, ServiceTicket, ServiceIntervention,
ServicePartUsage, ChecklistTemplate, ChecklistRun, ProcedureDocument.
Keep routers and templates untouched.
Add tests for relationships and core constraints.
```

### Prompt 4 — Tickets module

```text
Read this context file first.
Implement the tickets module using the existing shared UI foundation.
Create routes, templates, filters, status workflow, and detail page.
Match the oee-calculator UI language exactly.
```

## 8. File indexing tip

Pentru repo-uri mari, este util să existe și un index markdown cu lista fișierelor și descrierea lor scurtă, astfel încât agentul să înțeleagă mai rapid unde se află layout-ul, logica și componentele importante.[cite:114]

## 9. Maintenance checklist

Actualizează acest fișier când se schimbă:

- fișierele-sursă pentru UI;
- comenzile de test/lint/run;
- convențiile de naming;
- arhitectura modulelor;
- workflow-ul prompturilor;
- skill-urile folosite efectiv.

Un context file util trebuie să rămână corect și executabil; dacă devine învechit, începe să degradeze output-ul agentului.[cite:115]
