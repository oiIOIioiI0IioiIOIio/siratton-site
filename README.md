# Siratton Site — Portfolio de Côme Nottaris

Site web statique hébergé sur GitHub Pages, migré depuis [siratton.hotglue.me](https://siratton.hotglue.me).

**Domaine** : [www.siratton.site](https://www.siratton.site)

---

## 📁 Structure du site

```
siratton-site/
├── index.html              ← Page d'accueil (FR)
├── home-en/index.html      ← Page d'accueil (EN)
│
├── photos/index.html       ← Photographie (FR)
├── photos-en/index.html    ← Photography (EN)
├── cieza/index.html        ← Série photo Cieza, Espagne
│
├── journalisme/index.html  ← Journalisme (FR)
├── journalisme-en/index.html ← Journalism (EN)
├── jsl/index.html          ← Projet JSL
├── jsl/pdf/                ← PDFs du projet JSL
├── rsf/index.html          ← RSF — Reporters Sans Frontières
│
├── autres/index.html       ← Autres projets
├── automediatheque/index.html ← Automédiathèque
├── fea/index.html          ← Fait Entrer l'Accusé
│
├── contact/index.html      ← Contact
│
├── css/
│   ├── reset.min.css       ← Reset CSS (Yahoo)
│   ├── main.css            ← CSS hérité de HotGlue
│   └── site.css            ← CSS principal du site (à éditer)
│
├── img/
│   └── favicon.ico
│
├── tools/
│   ├── scrape_hotglue.py   ← Script de scraping (voir ci-dessous)
│   └── requirements.txt    ← Dépendances Python pour le scraping
│
├── CNAME                   ← Domaine personnalisé
├── README.md               ← Ce fichier
└── .gitignore
```

## 🖊 Comment éditer le site

### Modifier une page existante

1. Ouvrez le fichier `index.html` dans le dossier correspondant
2. Modifiez le contenu HTML dans la balise `<div class="page-content">`
3. Commitez et poussez — GitHub Pages met à jour automatiquement

### Ajouter une image

1. Placez l'image dans le dossier `img/` (ou dans le dossier de la page)
2. Référencez-la avec `<img src="../img/votre-image.jpg" alt="description">`

### Ajouter un PDF (JSL ou autre)

1. Placez le PDF dans `jsl/pdf/`
2. Ajoutez un lien dans `jsl/index.html` :
   ```html
   <li><a href="pdf/votre-document.pdf" target="_blank">Titre du document</a></li>
   ```

### Modifier le style

Le fichier CSS principal est `css/site.css`. Les variables de couleur sont au début :

```css
:root {
  --color-bg:       #000;       /* fond */
  --color-text:     #fff;       /* texte */
  --color-accent:   #EB2828;    /* rouge (photos) */
  --color-accent2:  #84ADDC;    /* bleu (liens, accueil) */
  --color-banner:   #FFD682;    /* jaune (bannière) */
}
```

### Créer une nouvelle page

1. Créez un dossier : `mkdir nouvelle-page`
2. Copiez un `index.html` existant comme modèle
3. Modifiez le contenu dans `<div class="page-content">`
4. Ajoutez un lien dans la navigation si nécessaire

## 🔧 Script de scraping

Un script Python complet est fourni pour re-scraper le site HotGlue si besoin.

### Prérequis

```bash
pip install -r tools/requirements.txt
```

Vous aurez aussi besoin de Google Chrome et [ChromeDriver](https://chromedriver.chromium.org/).

### Utilisation

```bash
# Scraper toutes les pages
python tools/scrape_hotglue.py --all

# Scraper une seule page
python tools/scrape_hotglue.py --page jsl

# Spécifier un répertoire de sortie
python tools/scrape_hotglue.py --output-dir ./build

# Mode verbeux
python tools/scrape_hotglue.py --all --verbose
```

Le script :
- Utilise Selenium (Chrome headless) comme méthode principale
- Télécharge images, CSS, JS et les réécrit en chemins locaux
- Détecte et télécharge les PDF de la page JSL dans `jsl/pdf/`
- Gère les erreurs et reprises automatiquement

## 📋 Pages du site

| Page | URL HotGlue | Statut |
|------|------------|--------|
| Accueil | `/?home` | ✅ Migré |
| Accueil EN | `/?home-EN` | ✅ Créé |
| Photographie | `/?photos` | ✅ Créé |
| Photographie EN | `/?photos-EN` | ✅ Créé |
| Journalisme | `/?journalisme` | ✅ Créé |
| Journalisme EN | `/?journalisme-EN` | ✅ Créé |
| Autres projets | `/?autres` | ✅ Créé |
| Contact | `/?contact` | ✅ Créé |
| FEA | `/?fea` | ✅ Migré |
| Automédiathèque | `/?automediatheque` | ✅ Créé |
| Cieza | `/?Cieza` | ✅ Créé |
| JSL | `/?JSL` | ✅ Créé (PDFs à ajouter) |
| RSF | `/?RSF` | ✅ Créé |

> **Note** : `home try 2` a été ignoré (brouillon).

## 🚀 Déploiement

Le site est automatiquement déployé sur GitHub Pages via le domaine configuré dans `CNAME`.

## 📜 Origine

Scraped from: https://siratton.hotglue.me
