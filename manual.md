# 📖 Manuel — Autodetection

> Wiki personnel pour `siratton.site/autodetection`
> Page standalone, non liée depuis aucun menu du site.
> À supprimer du repo après téléchargement.

---

## Table des matières

1. [Accès & mot de passe](#1-accès--mot-de-passe)
2. [Clé API Anthropic](#2-clé-api-anthropic)
3. [Connexion Supabase](#3-connexion-supabase)
4. [Vue Agent IA](#4-vue-agent-ia)
5. [Vue Dashboard](#5-vue-dashboard)
6. [Formulaire d'ajout manuel](#6-formulaire-dajout-manuel)
7. [Filtres et recherche](#7-filtres-et-recherche)
8. [Architecture technique](#8-architecture-technique)
9. [Fichiers du projet](#9-fichiers-du-projet)
10. [Données & schéma Supabase](#10-données--schéma-supabase)
11. [Personnalisation & maintenance](#11-personnalisation--maintenance)
12. [Raccourcis clavier](#12-raccourcis-clavier)
13. [Dépannage](#13-dépannage)

---

## 1. Accès & mot de passe

**URL** : `https://siratton.site/autodetection`

Au chargement, un écran plein-écran demande le mot de passe.

| Paramètre | Valeur |
|---|---|
| Mot de passe | `automedia2026` |
| Stockage | `sessionStorage` (clé : `autodetection_auth`) |
| Durée | Tant que l'onglet/fenêtre reste ouvert |
| Après refresh | Pas besoin de retaper (sessionStorage persiste dans l'onglet) |

**Pour changer le mot de passe** : modifier la constante `AUTH_PASSWORD` dans le `<script>` de `autodetection.html` (ligne ~335).

**Déconnexion** : aucun bouton visible par défaut. La session expire quand l'onglet est fermé. On peut aussi vider le sessionStorage via la console du navigateur :
```js
sessionStorage.removeItem('autodetection_auth')
```

**Sécurité** : c'est une friction côté client uniquement. Quelqu'un qui inspecte le code source voit le mot de passe. Ce n'est pas une vraie authentification, juste une barrière pour éviter l'accès accidentel.

---

## 2. Clé API Anthropic

L'agent IA utilise l'API Claude d'Anthropic. La clé est gérée de deux façons (par ordre de priorité) :

### Option A — Fichier `assets/agent-config.js` (prioritaire)

```bash
cp assets/agent-config.example.js assets/agent-config.js
```

Puis éditer `assets/agent-config.js` :
```js
const ANTHROPIC_API_KEY = "sk-ant-ta-vraie-clé-ici";
```

Ce fichier est dans `.gitignore` → jamais poussé sur GitHub.

### Option B — Saisie dans le navigateur (localStorage)

Si le fichier n'existe pas ou contient une clé vide :
1. La page affiche automatiquement un formulaire au premier chargement
2. Tu entres ta clé `sk-ant-...`
3. Elle est stockée dans `localStorage` (clé : `autodetection_anthropic_key`)
4. Persiste indéfiniment dans le navigateur, même après fermeture

**Pour changer la clé** plus tard : cliquer sur le bouton **🔑 Clé** dans le header.

**Résolution de la clé** (logique interne) :
```
1. agent-config.js chargé et non vide ?     → utiliser cette clé
2. Sinon, localStorage contient une clé ?    → utiliser celle-là
3. Sinon                                     → demander à l'utilisateur
```

**Où obtenir une clé** : [console.anthropic.com](https://console.anthropic.com/) → API Keys → Create Key.

**Modèle utilisé** : `claude-sonnet-4-20250514` (Claude Sonnet 4).

**Headers envoyés** :
```
x-api-key: <ta clé>
anthropic-version: 2023-06-01
anthropic-dangerous-direct-browser-access: true
Content-Type: application/json
```

---

## 3. Connexion Supabase

La base de données utilise Supabase (PostgreSQL hébergé).

| Paramètre | Valeur |
|---|---|
| URL du projet | `https://fnxxhuyqhhpfjvgmcbjz.supabase.co` |
| Clé publique | `sb_publishable_uyzjAWCUrveeUHsP0m-X3Q_QGQ21Rkw` |
| Tables utilisées | `automedias`, `propositions` |
| Dashboard Supabase | Se connecter sur [supabase.com](https://supabase.com) pour gérer les données |

**La clé est publique** (publishable) : elle permet de lire et d'insérer dans les tables autorisées par les politiques RLS (Row Level Security) de Supabase.

**Au chargement** : la page fetche automatiquement les deux tables et affiche tout dans le dashboard. Si Supabase est indisponible, un message d'erreur apparaît dans la zone des cartes.

---

## 4. Vue Agent IA

C'est la vue par défaut (onglet **⚡ Agent**). Deux colonnes :

### Colonne gauche — Agent

**Interface** :
- **Pastille de statut** : grise (inactif), orange pulsante (en cours), verte (prêt)
- **Lien « voir critères »** : affiche/masque les critères de sélection intégrés dans le prompt système
- **Zone de log** : affiche les messages en temps réel (thème saisi, résultats trouvés, insertions, erreurs)
- **Zone de saisie** : textarea pour décrire le thème de recherche
- **Boutons** : `✕ Log` (vider le journal) et `⚡ Lancer` (lancer la recherche)

**Comment ça marche** :

1. Tu tapes un thème (ex : *"automédias ouvriers en Amérique latine"*)
2. Tu cliques **⚡ Lancer** (ou `Ctrl+Entrée`)
3. L'agent envoie le thème à Claude avec un prompt système détaillé + l'outil `web_search`
4. Claude cherche sur le web et retourne un JSON avec 6–14 automédias
5. Chaque résultat est inséré automatiquement dans la table `propositions` de Supabase
6. Les cartes apparaissent en temps réel dans la colonne droite avec un flash vert
7. Le log affiche le résumé : nombre insérés, éventuelles erreurs

**Critères du prompt** (ce que Claude cherche) :
- Autoproduction par les personnes directement concernées
- Autonomie éditoriale (hors partis, États, marchands)
- Dimension collective
- Tous formats acceptés (vidéo, podcast, Telegram, zine, radio, film, journal, newsletter, WhatsApp…)
- Approche décoloniale : chercher activement hors du monde occidental, accepter les formats locaux, ne pas hiérarchiser selon la "professionnalisation"
- Exclut : journalistes pro extérieurs (Mediapart, Blast), médias de partis/d'État, désinformation, comptes strictement personnels

**Exemples de requêtes** :
- `"automédias ouvriers en Amérique latine"`
- `"radio communautaires africaines"`
- `"documentaires autochtones"`
- `"médias de quartier en France"`
- `"podcasts féministes en Asie du Sud-Est"`
- `"collectifs vidéo Palestine"`

### Colonne droite — Dashboard inline

Même contenu que la vue Dashboard (statistiques + filtres + cartes) mais affiché à côté de l'agent. Se met à jour en temps réel quand l'agent insère des données.

---

## 5. Vue Dashboard

Onglet **📊 Dashboard** : affiche les mêmes données en plein écran (sans la colonne agent).

### Barre de statistiques (6 métriques)

| Métrique | Description |
|---|---|
| **Total** | Nombre total d'entrées (automédias + propositions) |
| **En ligne** | Entrées avec `status = "online"` |
| **Propositions** | Entrées venant de la table `propositions` |
| **Pays / zones** | Nombre de pays uniques |
| **Langues** | Nombre de langues uniques |
| **Formats** | Nombre de types/formats uniques |

### Grille de cartes

Chaque carte affiche :
- **Nom** (lien cliquable vers l'URL)
- **Badge de statut** : En ligne (vert), Hors ligne (rouge), Archivé (orange), Proposé (violet)
- **Description** (1–2 phrases)
- **Tags colorés** : format (violet), pays (bleu), langue(s) (vert), thème(s) (jaune)
- **URL** en bas de carte

Les cartes sont dans une grille responsive (colonnes de min 260px).

---

## 6. Formulaire d'ajout manuel

Bouton **＋ Manuel** dans le header → ouvre un modal.

### Champs

| Champ | Obligatoire | Type | Notes |
|---|---|---|---|
| Nom | ✅ | texte | Nom de l'automédia |
| URL | ✅ | url | Adresse web |
| Format | — | sélection | site, vidéo, podcast, newsletter, telegram, instagram, twitter/X, journal, magazine, zine, radio, film, collectif, autre |
| Pays / Zone | — | texte | Libre |
| Langue(s) | — | texte | Séparées par virgules : `fr, en, ar` |
| Statut | — | sélection | online (défaut), offline, archived, proposed |
| Thème(s) | — | texte (pleine largeur) | Séparés par virgules : `travail, féminisme` |
| Description | ✅ | textarea | 1–2 phrases |
| Notes | — | textarea | Précisions libres |

**À la soumission** :
1. Validation : nom + URL + description obligatoires
2. Insertion dans la table `propositions` de Supabase
3. Message de succès vert → le modal se ferme après 1 seconde
4. Les données sont rechargées automatiquement

---

## 7. Filtres et recherche

Présents dans les deux vues (Agent et Dashboard).

### Barre de recherche
- Recherche textuelle dans : nom, description, URL, thème, notes
- Recherche instantanée (à chaque frappe)
- Insensible à la casse

### Dropdowns de filtre
Les options sont **générées dynamiquement** à partir des données :

| Filtre | Champ source |
|---|---|
| Tous formats | `type` |
| Tous pays | `country` |
| Toutes langues | `languages` |
| Tous thèmes | `theme` |
| Tous statuts | `status` |

### Bouton ✕
Réinitialise tous les filtres et la recherche.

### Compteur
Affiche `X / Y` — nombre de résultats filtrés / total.

---

## 8. Architecture technique

### Stack
- **Zéro framework** — tout en vanilla HTML/CSS/JS
- **Un seul fichier** : `autodetection.html` (+ `assets/agent-config.js` optionnel)
- **APIs externes** :
  - Anthropic (Claude) pour l'agent IA
  - Supabase REST API pour la base de données

### CSS
- Variables CSS dans `:root` (palette dark)
- Palette : fond `#0f1117`, accent `#6c63ff` (violet), texte `#e8eaf0`
- Polices système (`'Segoe UI', system-ui, sans-serif`)
- Layout flex (header + body), body 100vh
- Responsive : les filtres wrappent, les cartes s'adaptent

### JavaScript
- Tout dans un seul `<script>` en bas de page
- Fonctions globales (pas de module, pas de bundler)
- `async/await` pour les appels API
- Pas de dépendances externes

### Sécurité (meta tags)
```html
<meta name="referrer" content="no-referrer">
<meta http-equiv="Permissions-Policy" content="interest-cohort=()">
<meta http-equiv="X-Content-Type-Options" content="nosniff">
<meta name="robots" content="noindex, nofollow">
```

---

## 9. Fichiers du projet

```
siratton-site/
├── autodetection.html              ← la page principale
├── assets/
│   ├── agent-config.js             ← ta clé API (gitignored, créé manuellement)
│   └── agent-config.example.js     ← template vide (commité)
├── .gitignore                      ← contient "assets/agent-config.js"
└── manual.md                       ← ce fichier (à supprimer après lecture)
```

### Ce qui est commité (visible sur GitHub)
- `autodetection.html`
- `assets/agent-config.example.js`
- `.gitignore` (modifié pour exclure la clé)

### Ce qui n'est PAS commité
- `assets/agent-config.js` (ta vraie clé API)

---

## 10. Données & schéma Supabase

### Table `automedias`
Entrées validées dans le catalogue principal. Champs connus :

| Champ | Type | Description |
|---|---|---|
| `name` | text | Nom de l'automédia |
| `url` | text | URL du site/canal |
| `type` | text | Format (site, vidéo, podcast, etc.) |
| `country` | text | Pays ou zone géographique |
| `languages` | text[] ou text | Langue(s) |
| `status` | text | online, offline, archived |
| `description` | text | Description courte |
| `theme` | text | Thème(s), séparés par virgules |
| `notes` | text | Notes libres |
| `orientation` | text | (utilisé dans le code, toujours `null` pour l'instant) |
| `created_at` | timestamp | Date de création (auto) |

### Table `propositions`
Entrées ajoutées par l'agent IA ou le formulaire manuel. Même structure que `automedias`.

### Comportement au chargement
1. Fetch `automedias` → marqué `_src: 'automedias'`
2. Fetch `propositions` → marqué `_src: 'propositions'`, statut par défaut `'proposed'`
3. Les deux sont fusionnés dans `allData[]` et affichés ensemble
4. Les filtres et stats prennent en compte les deux sources

### Insertion
- L'agent IA et le formulaire manuel insèrent **uniquement dans `propositions`**
- Pour déplacer une proposition vers `automedias`, il faut le faire via le dashboard Supabase directement

---

## 11. Personnalisation & maintenance

### Changer le mot de passe
Dans `autodetection.html`, chercher :
```js
const AUTH_PASSWORD="automedia2026";
```
Remplacer la valeur.

### Changer le modèle Claude
Chercher :
```js
model:"claude-sonnet-4-20250514"
```
Remplacer par un autre modèle (ex : `claude-opus-4-20250514`, `claude-haiku-4-20250514`).

### Modifier les critères de l'agent
Le prompt système est dans la constante `SYSTEM_PROMPT`. C'est un long texte qui décrit les critères de sélection, l'approche décoloniale, les exclusions, et le format JSON attendu. Tu peux le modifier librement.

### Changer le nombre de résultats
Dans le prompt système, chercher :
```
Trouve entre 6 et 14 automédias.
```

### Ajouter un nouveau champ au formulaire
1. Ajouter le HTML du champ dans la section `<div class="fg">` du modal
2. Récupérer la valeur dans `submitForm()` et l'ajouter au payload `sbInsert({...})`
3. S'assurer que la colonne existe dans Supabase

### Modifier les types/formats
Les options du select `f_type` dans le modal :
```html
<option>site</option><option>vidéo</option><option>podcast</option>...
```
Et dans le prompt système (liste des types acceptés).

### Ajouter un bouton de déconnexion
Il n'y en a pas dans l'interface. Pour en ajouter un, dans le `<header>`, ajouter :
```html
<button class="hbtn hbtn-s" onclick="logout()">🚪</button>
```
La fonction `logout()` existe déjà.

---

## 12. Raccourcis clavier

| Contexte | Raccourci | Action |
|---|---|---|
| Écran mot de passe | `Entrée` | Valider le mot de passe |
| Overlay clé API | `Entrée` | Enregistrer la clé |
| Textarea de l'agent | `Ctrl+Entrée` / `⌘+Entrée` | Lancer la recherche |

---

## 13. Dépannage

### "Connexion Supabase…" bloqué
- Vérifier la connexion internet
- Vérifier que Supabase n'est pas en maintenance
- Ouvrir la console du navigateur (F12) → onglet Network pour voir les erreurs

### L'agent ne répond pas
- Vérifier que la clé API est configurée (bouton 🔑)
- Vérifier le solde/crédits sur [console.anthropic.com](https://console.anthropic.com/)
- Ouvrir la console du navigateur pour voir les erreurs API

### "Réponse non parseable"
- Claude n'a pas retourné du JSON valide. Relancer la même requête.
- Si ça persiste, essayer un thème plus précis.

### Les données ne s'affichent pas
- Cliquer sur **↺ Sync** pour forcer le rechargement
- Vérifier les politiques RLS dans Supabase (les tables doivent autoriser les SELECT avec la clé publique)

### Erreur d'insertion "HTTP 4XX"
- Vérifier que la table `propositions` autorise les INSERT avec la clé publique
- Vérifier les contraintes de la table (champs obligatoires, types)

### La page est blanche
- Vérifier le mot de passe
- Ouvrir la console JS (F12) pour voir les erreurs de syntaxe
- Vérifier que `autodetection.html` n'a pas été corrompu

### Réinitialiser l'état local
```js
// Dans la console du navigateur (F12)
sessionStorage.clear()       // Réinitialise l'auth
localStorage.removeItem('autodetection_anthropic_key')  // Supprime la clé API
```
