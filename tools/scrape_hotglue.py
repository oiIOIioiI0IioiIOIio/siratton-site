#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrape_hotglue.py — Script de scraping du site HotGlue siratton.hotglue.me
===========================================================================

Ce script récupère toutes les pages du site HotGlue et les convertit en
fichiers HTML statiques compatibles avec la structure du dépôt GitHub Pages.

Méthode principale : Selenium (Chrome headless) pour récupérer le HTML
                     rendu côté client (HotGlue utilise du JS).
Méthode de secours : requests + BeautifulSoup si Selenium échoue.

Pages scrapées (via siratton.hotglue.me/?pagename) :
  home, Agenda, Cieza, JSL, RSF, automediatheque, autres, contact, fea,
  home-EN, journalisme, journalisme-EN, niger, niger_analyse,
  niger_analyse_raw, niger_timeline, photos, photos-EN

  ⚠ "home try 2" est ignoré (brouillon).

Spécificités :
  - La page JSL est inspectée pour détecter et télécharger les PDF
    (sauvegardés dans jsl/pdf/).
  - Les URL des ressources (images, CSS, JS, PDF) sont réécrites en
    chemins relatifs/locaux.
  - Les fichiers partagés (CSS, favicon) ne sont téléchargés qu'une fois.

Prérequis :
  pip install selenium beautifulsoup4 requests lxml
  Google Chrome + ChromeDriver (même version) installés et dans le PATH.

Utilisation :
  python tools/scrape_hotglue.py              # scrape toutes les pages
  python tools/scrape_hotglue.py --all        # idem (explicite)
  python tools/scrape_hotglue.py --page jsl   # scrape une seule page
  python tools/scrape_hotglue.py --output-dir ./build   # répertoire de sortie

Auteur : Côme Nottaris / outil de maintenance siratton.site
"""

import argparse
import hashlib
import logging
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_DISPONIBLE = True
except ImportError:
    SELENIUM_DISPONIBLE = False

try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_DISPONIBLE = True
except ImportError:
    REQUESTS_DISPONIBLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

URL_BASE = "https://siratton.hotglue.me/"

# Correspondance : nom de page HotGlue → répertoire de sortie
# La clé est le paramètre ?pagename, la valeur est le dossier cible.
# "home" est un cas spécial : il produit index.html à la racine.
PAGES = {
    "home":               ".",
    "Agenda":             "agenda",
    "Cieza":              "cieza",
    "JSL":                "jsl",
    "RSF":                "rsf",
    "automediatheque":    "automediatheque",
    "autres":             "autres",
    "contact":            "contact",
    "fea":                "fea",
    "home-EN":            "home-en",
    "journalisme":        "journalisme",
    "journalisme-EN":     "journalisme-en",
    "niger":              "niger",
    "niger_analyse":      "niger_analyse",
    "niger_analyse_raw":  "niger_analyse_raw",
    "niger_timeline":     "niger_timeline",
    "photos":             "photos",
    "photos-EN":          "photos-en",
}

# Nombre maximum de tentatives par requête
MAX_TENTATIVES = 3

# Délai entre les tentatives (secondes)
DELAI_TENTATIVE = 2

# Temps d'attente pour le rendu JS de HotGlue (secondes)
ATTENTE_RENDU_JS = 8

# Ressources partagées déjà téléchargées (chemin → hash)
_ressources_vues = {}

# ---------------------------------------------------------------------------
# Journalisation
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scrape_hotglue")

# ---------------------------------------------------------------------------
# Utilitaires réseau
# ---------------------------------------------------------------------------


def telecharger_avec_retry(url, tentatives=MAX_TENTATIVES, timeout=30):
    """Télécharge une URL avec logique de ré-essai.

    Retourne le contenu brut (bytes) ou None en cas d'échec.
    """
    for essai in range(1, tentatives + 1):
        try:
            resp = requests.get(url, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as e:
            log.warning("  Tentative %d/%d échouée pour %s : %s",
                        essai, tentatives, url, e)
            if essai < tentatives:
                time.sleep(DELAI_TENTATIVE)
    log.error("  Impossible de télécharger %s après %d tentatives.",
              url, tentatives)
    return None


def hash_contenu(data):
    """Retourne le hash SHA-256 court d'un contenu binaire."""
    return hashlib.sha256(data).hexdigest()[:16]

# ---------------------------------------------------------------------------
# Selenium — navigateur headless
# ---------------------------------------------------------------------------


def creer_navigateur():
    """Crée et retourne une instance Chrome headless.

    Retourne None si Selenium ou Chrome n'est pas disponible.
    """
    if not SELENIUM_DISPONIBLE:
        log.warning("Selenium non installé — utilisation du mode de secours.")
        return None
    try:
        options = ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        # Éviter la détection de bot
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)
        log.info("Navigateur Chrome headless initialisé.")
        return driver
    except Exception as e:
        log.warning("Impossible de lancer Chrome : %s", e)
        log.warning("Basculement vers le mode de secours (requests).")
        return None


def obtenir_html_selenium(driver, nom_page):
    """Navigue vers une page HotGlue et retourne le HTML rendu.

    Args:
        driver: instance Selenium WebDriver.
        nom_page: nom de la page HotGlue (ex: "JSL", "home").

    Returns:
        Le code source HTML complet après rendu JS, ou None.
    """
    if nom_page == "home":
        url = URL_BASE
    else:
        url = f"{URL_BASE}?{nom_page}"

    for essai in range(1, MAX_TENTATIVES + 1):
        try:
            log.info("  [Selenium] Chargement de %s (tentative %d)…",
                     url, essai)
            driver.get(url)

            # Attendre que le corps de la page soit chargé
            WebDriverWait(driver, ATTENTE_RENDU_JS).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Laisser HotGlue finir son rendu
            time.sleep(ATTENTE_RENDU_JS)

            html = driver.page_source
            if html and len(html) > 200:
                return html
            log.warning("  HTML trop court, nouvelle tentative…")
        except Exception as e:
            log.warning("  Erreur Selenium : %s", e)
            if essai < MAX_TENTATIVES:
                time.sleep(DELAI_TENTATIVE)

    return None


def obtenir_html_requests(nom_page):
    """Récupère le HTML brut via requests (méthode de secours).

    ⚠ Le contenu dynamique généré par JavaScript ne sera pas présent.

    Args:
        nom_page: nom de la page HotGlue.

    Returns:
        Le code source HTML brut, ou None.
    """
    if not REQUESTS_DISPONIBLE:
        log.error("requests/beautifulsoup4 non installés. Abandon.")
        return None

    if nom_page == "home":
        url = URL_BASE
    else:
        url = f"{URL_BASE}?{nom_page}"

    data = telecharger_avec_retry(url)
    if data:
        return data.decode("utf-8", errors="replace")
    return None

# ---------------------------------------------------------------------------
# Analyse et transformation du HTML
# ---------------------------------------------------------------------------


def analyser_html(html_brut):
    """Parse le HTML et retourne un objet BeautifulSoup."""
    return BeautifulSoup(html_brut, "lxml")


def extraire_urls_ressources(soup, url_page):
    """Extrait toutes les URLs de ressources liées dans le HTML.

    Retourne un dictionnaire {url_absolue: type_ressource}.
    Types : "image", "css", "js", "pdf", "autre".
    """
    ressources = {}

    # Images : <img src="...">, style="background-image: url(...)"
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            url_abs = urljoin(url_page, src)
            ressources[url_abs] = "image"

    # CSS : <link rel="stylesheet" href="...">
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href")
        if href:
            url_abs = urljoin(url_page, href)
            ressources[url_abs] = "css"

    # JavaScript : <script src="...">
    for script in soup.find_all("script", src=True):
        src = script.get("src")
        if src:
            url_abs = urljoin(url_page, src)
            ressources[url_abs] = "js"

    # Liens vers des fichiers (PDF, images, etc.)
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        url_abs = urljoin(url_page, href)
        chemin = urlparse(url_abs).path.lower()
        if chemin.endswith(".pdf"):
            ressources[url_abs] = "pdf"
        elif any(chemin.endswith(ext)
                 for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")):
            ressources[url_abs] = "image"

    # Images dans les styles inline (background-image)
    for tag in soup.find_all(style=True):
        style_val = tag["style"]
        for match in re.finditer(r'url\(["\']?(.*?)["\']?\)', style_val):
            url_img = match.group(1)
            if url_img and not url_img.startswith("data:"):
                url_abs = urljoin(url_page, url_img)
                ressources[url_abs] = "image"

    # Favicon
    for link in soup.find_all("link", rel=lambda r: r and "icon" in r):
        href = link.get("href")
        if href:
            url_abs = urljoin(url_page, href)
            ressources[url_abs] = "image"

    return ressources


def determiner_chemin_local(url_ressource, type_ressource, dossier_page,
                            dossier_sortie):
    """Détermine le chemin local pour sauvegarder une ressource téléchargée.

    Les ressources HotGlue sont enregistrées dans le dossier de la page.
    Les ressources externes sont enregistrées dans un dossier 'assets/'.

    Returns:
        (chemin_absolu_fichier, chemin_relatif_depuis_html)
    """
    parsed = urlparse(url_ressource)
    nom_fichier = os.path.basename(unquote(parsed.path)) or "index"

    # Pas d'extension → deviner
    if "." not in nom_fichier:
        ext_map = {"image": ".png", "css": ".css", "js": ".js", "pdf": ".pdf"}
        nom_fichier += ext_map.get(type_ressource, "")

    # Ressources HotGlue (même domaine)
    if "hotglue" in parsed.netloc:
        sous_dossier = "assets"
        chemin_rel = parsed.path.lstrip("/")
        # Simplifier le chemin
        parties = chemin_rel.split("/")
        if len(parties) > 2:
            nom_fichier = "__".join(parties[-2:])

        chemin_abs = os.path.join(dossier_sortie, dossier_page,
                                  sous_dossier, nom_fichier)
        chemin_rel_html = f"assets/{nom_fichier}"
    else:
        # Ressource externe — on ne la télécharge pas, on garde l'URL
        return None, url_ressource

    return chemin_abs, chemin_rel_html


def reecrire_urls(soup, correspondances, est_racine):
    """Réécrit les URLs dans le HTML pour pointer vers les fichiers locaux.

    Args:
        soup: objet BeautifulSoup.
        correspondances: dict {url_originale: chemin_relatif_local}.
        est_racine: True si c'est la page d'accueil (pas de ../).
    """
    prefix_css = "" if est_racine else "../"

    # Réécrire les liens CSS pour utiliser le CSS partagé du site
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href", "")
        if href:
            # Remplacer les CSS HotGlue par notre CSS local
            if "hotglue" in href or "reset" in href.lower():
                link["href"] = f"{prefix_css}css/reset.min.css"
            elif href in correspondances:
                link["href"] = correspondances[href]

    # Réécrire les images
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src in correspondances:
            img["src"] = correspondances[src]

    # Réécrire les scripts
    for script in soup.find_all("script", src=True):
        src = script.get("src", "")
        if src in correspondances:
            script["src"] = correspondances[src]

    # Réécrire les liens
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href in correspondances:
            a_tag["href"] = correspondances[href]

    # Réécrire les background-image dans les styles inline
    for tag in soup.find_all(style=True):
        style_val = tag["style"]
        nouveau_style = style_val
        for url_orig, chemin_local in correspondances.items():
            if url_orig in style_val:
                nouveau_style = nouveau_style.replace(url_orig, chemin_local)
        if nouveau_style != style_val:
            tag["style"] = nouveau_style

    return soup

# ---------------------------------------------------------------------------
# Construction du HTML final
# ---------------------------------------------------------------------------


def construire_html_page(soup, nom_page, dossier_page):
    """Transforme le HTML scrapé en HTML propre conforme au template du site.

    - Ajoute les balises <head> avec CSS partagé et favicon.
    - Ajoute le bouton ACCUEIL.
    - Définit la structure body class="page" id="pagename.head".

    Args:
        soup: objet BeautifulSoup du contenu HotGlue.
        nom_page: identifiant de la page (ex: "jsl", "home").
        dossier_page: dossier de sortie relatif (ex: "jsl", ".").

    Returns:
        HTML final sous forme de chaîne.
    """
    est_racine = (dossier_page == ".")
    prefix = "" if est_racine else "../"

    # Identifiant de la page (minuscules, cohérent avec le template)
    page_id = nom_page.lower().replace(" ", "_")

    # Extraire le contenu du <body> existant
    body_existant = soup.find("body")
    if body_existant:
        contenu_body = "".join(str(child) for child in body_existant.children)
        # Récupérer le style inline du body si présent
        body_style = body_existant.get("style", "")
        body_id = body_existant.get("id", f"{page_id}.head")
    else:
        contenu_body = str(soup)
        body_style = ""
        body_id = f"{page_id}.head"

    # Récupérer le style inline de <html> si présent
    html_tag = soup.find("html")
    html_style = ""
    if html_tag:
        html_style = html_tag.get("style", "background-color: #000000;")
    if not html_style:
        html_style = "background-color: #000000;"

    # Extraire les <style> et <link> du head original
    styles_extra = []
    head_existant = soup.find("head")
    if head_existant:
        for style_tag in head_existant.find_all("style"):
            styles_extra.append(str(style_tag))
        # Garder les link CSS qui ne sont pas les nôtres
        for link_tag in head_existant.find_all("link"):
            href = link_tag.get("href", "")
            rel = link_tag.get("rel", [])
            if "stylesheet" in rel and "hotglue" not in href:
                if "reset" not in href and "main" not in href:
                    styles_extra.append(str(link_tag))

    # Extraire les styles inline du body
    styles_body = []
    if body_existant:
        for style_tag in body_existant.find_all("style"):
            styles_body.append(str(style_tag))
            style_tag.decompose()  # retirer du contenu body
        contenu_body = "".join(str(child) for child in body_existant.children)

    # Vérifier si le bouton ACCUEIL existe déjà dans le contenu
    a_accueil_present = False
    if body_existant:
        for a_tag in body_existant.find_all("a"):
            for div in a_tag.find_all("div"):
                if div.get_text(strip=True).upper().startswith("ACCUEIL"):
                    a_accueil_present = True
                    break

    # Construire le bouton ACCUEIL si absent
    bouton_accueil = ""
    if not a_accueil_present and not est_racine:
        bouton_accueil = f"""<a href="{prefix}index.html">
<div class="text resizable object" style="background-color: rgb(132, 173, 220); color: rgb(0, 0, 0); font-size: 16px; height: 27.6667px; left: 8.66667px; letter-spacing: -0.0520833em; line-height: 1.80834em; padding-bottom: 0px; padding-left: 1px; padding-right: 1px; padding-top: 0px; position: absolute; text-align: center; top: 6.66667px; width: 76.6667px; z-index: 100;">
\t\tACCUEIL
\t</div>
</a>"""

    # Titre de la page
    title_tag = soup.find("title")
    titre = title_tag.get_text(strip=True) if title_tag else page_id

    # Assembler le HTML final
    styles_extra_str = "\n".join(styles_extra)
    styles_body_str = "\n".join(styles_body)

    html_final = f"""<!DOCTYPE html>
<html style="{html_style}">
<head>
<title>{titre}</title>
<meta content="text/html; charset=utf-8" http-equiv="Content-Type"/>
<link href="{prefix}img/favicon.ico" rel="shortcut icon"/>
<link href="{prefix}css/reset.min.css" rel="stylesheet" type="text/css"/>
<link href="{prefix}css/main.css" rel="stylesheet" type="text/css"/>
{styles_extra_str}
</head>
<body class="page" id="{body_id}">
{bouton_accueil}
<!-- user BODY definitions -->
{styles_body_str}
{contenu_body}
</body>
</html>"""

    return html_final

# ---------------------------------------------------------------------------
# Téléchargement et sauvegarde des ressources
# ---------------------------------------------------------------------------


def telecharger_ressource(url, chemin_local):
    """Télécharge une ressource et la sauvegarde localement.

    Utilise la déduplication par hash pour éviter les doublons.

    Returns:
        True si la ressource a été téléchargée/existe, False sinon.
    """
    global _ressources_vues

    # Vérifier si déjà téléchargé
    if chemin_local in _ressources_vues:
        log.debug("  Ressource déjà présente : %s", chemin_local)
        return True

    # Vérifier si le fichier existe déjà sur le disque
    if os.path.exists(chemin_local):
        _ressources_vues[chemin_local] = "existant"
        log.debug("  Fichier existant conservé : %s", chemin_local)
        return True

    contenu = telecharger_avec_retry(url)
    if contenu is None:
        return False

    # Déduplication par hash
    h = hash_contenu(contenu)
    for chemin_existant, hash_existant in _ressources_vues.items():
        if hash_existant == h:
            log.info("  Doublon détecté : %s == %s", chemin_local,
                     chemin_existant)
            # Copier quand même (chemins différents)
            break

    _ressources_vues[chemin_local] = h

    # Créer les répertoires parents
    os.makedirs(os.path.dirname(chemin_local), exist_ok=True)

    with open(chemin_local, "wb") as f:
        f.write(contenu)

    log.info("  ✓ Téléchargé : %s → %s", url[:80], chemin_local)
    return True


def telecharger_pdfs_jsl(soup, url_page, dossier_sortie):
    """Détecte et télécharge les fichiers PDF liés à la page JSL.

    Cherche les liens PDF dans le HTML et les télécharge dans jsl/pdf/.

    Args:
        soup: objet BeautifulSoup de la page JSL.
        url_page: URL de la page JSL pour résoudre les liens relatifs.
        dossier_sortie: répertoire racine de sortie.

    Returns:
        Liste des chemins locaux des PDF téléchargés.
    """
    pdfs_telecharges = []
    urls_pdf_vues = set()
    dossier_pdf = os.path.join(dossier_sortie, "jsl", "pdf")
    os.makedirs(dossier_pdf, exist_ok=True)

    def _nom_pdf_unique(url, nom_base):
        """Génère un nom de fichier PDF unique basé sur un hash de l'URL."""
        if not nom_base or not nom_base.lower().endswith(".pdf"):
            url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
            nom_base = f"document_{url_hash}.pdf"
        return nom_base

    # Chercher tous les liens vers des PDF
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        url_abs = urljoin(url_page, href)

        if url_abs.lower().endswith(".pdf") or ".pdf" in url_abs.lower():
            if url_abs in urls_pdf_vues:
                continue
            urls_pdf_vues.add(url_abs)

            nom_pdf = os.path.basename(unquote(urlparse(url_abs).path))
            nom_pdf = _nom_pdf_unique(url_abs, nom_pdf)

            chemin_pdf = os.path.join(dossier_pdf, nom_pdf)
            log.info("  📄 PDF détecté : %s", url_abs[:100])

            if telecharger_ressource(url_abs, chemin_pdf):
                pdfs_telecharges.append(chemin_pdf)
                a_tag["href"] = f"pdf/{nom_pdf}"

    # Chercher aussi des liens PDF dans les attributs data-*
    for tag in soup.find_all(attrs={"data-href": True}):
        data_href = tag["data-href"]
        if ".pdf" in data_href.lower():
            url_abs = urljoin(url_page, data_href)
            if url_abs in urls_pdf_vues:
                continue
            urls_pdf_vues.add(url_abs)

            nom_pdf = os.path.basename(unquote(urlparse(url_abs).path))
            nom_pdf = _nom_pdf_unique(url_abs, nom_pdf)

            chemin_pdf = os.path.join(dossier_pdf, nom_pdf)
            log.info("  📄 PDF (data-href) détecté : %s", url_abs[:100])

            if telecharger_ressource(url_abs, chemin_pdf):
                pdfs_telecharges.append(chemin_pdf)
                tag["data-href"] = f"pdf/{nom_pdf}"

    # Chercher des URLs de PDF dans tout le texte/scripts de la page
    texte_complet = str(soup)
    pattern_pdf = re.compile(
        r'(https?://[^\s"\'<>]+\.pdf)', re.IGNORECASE
    )
    for match in pattern_pdf.finditer(texte_complet):
        url_pdf = match.group(1)
        if url_pdf in urls_pdf_vues:
            continue
        urls_pdf_vues.add(url_pdf)

        nom_pdf = os.path.basename(unquote(urlparse(url_pdf).path))
        nom_pdf = _nom_pdf_unique(url_pdf, nom_pdf)

        chemin_pdf = os.path.join(dossier_pdf, nom_pdf)
        log.info("  📄 PDF (regex) détecté : %s", url_pdf[:100])
        if telecharger_ressource(url_pdf, chemin_pdf):
            pdfs_telecharges.append(chemin_pdf)

    if not pdfs_telecharges:
        log.info("  Aucun PDF détecté sur la page JSL.")
    else:
        log.info("  %d PDF téléchargé(s) pour JSL.", len(pdfs_telecharges))

    return pdfs_telecharges

# ---------------------------------------------------------------------------
# Réécriture des liens internes entre pages
# ---------------------------------------------------------------------------


def reecrire_liens_internes(soup, dossier_page):
    """Réécrit les liens internes HotGlue pour pointer vers la bonne structure.

    Les liens HotGlue de type /?pagename ou /pagename sont convertis
    en chemins relatifs du dépôt (../pagename/index.html, etc.).
    """
    est_racine = (dossier_page == ".")
    prefix = "" if est_racine else "../"

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        parsed = urlparse(href)

        # Liens HotGlue internes : /?PageName ou hotglue.me/?PageName
        if "hotglue.me" in parsed.netloc or (
                not parsed.netloc and not parsed.path.startswith("http")):

            query = parsed.query
            # Le nom de page est soit dans le query string, soit dans le path
            nom_page_lien = query if query else parsed.path.lstrip("/")

            if nom_page_lien and nom_page_lien in PAGES:
                dossier_cible = PAGES[nom_page_lien]
                if dossier_cible == ".":
                    a_tag["href"] = f"{prefix}index.html"
                else:
                    a_tag["href"] = f"{prefix}{dossier_cible}/index.html"
            elif nom_page_lien == "" and "hotglue.me" in href:
                # Lien vers la racine de HotGlue → page d'accueil
                a_tag["href"] = f"{prefix}index.html"

    return soup

# ---------------------------------------------------------------------------
# Traitement d'une page individuelle
# ---------------------------------------------------------------------------


def traiter_page(nom_page, dossier_page, dossier_sortie, driver=None):
    """Scrape et sauvegarde une page HotGlue.

    Args:
        nom_page: identifiant HotGlue de la page (ex: "JSL").
        dossier_page: dossier de sortie relatif (ex: "jsl").
        dossier_sortie: répertoire racine de sortie.
        driver: instance Selenium (optionnel).

    Returns:
        True si la page a été traitée avec succès, False sinon.
    """
    est_racine = (dossier_page == ".")
    log.info("=" * 60)
    log.info("Traitement de la page : %s → %s/index.html",
             nom_page, dossier_page if dossier_page != "." else "(racine)")
    log.info("=" * 60)

    # Étape 1 : Récupérer le HTML
    html_brut = None
    if driver:
        html_brut = obtenir_html_selenium(driver, nom_page)
    if html_brut is None:
        log.info("  Basculement vers requests…")
        html_brut = obtenir_html_requests(nom_page)

    if html_brut is None:
        log.error("  ✗ Impossible de récupérer la page %s.", nom_page)
        return False

    log.info("  HTML récupéré : %d caractères.", len(html_brut))

    # Étape 2 : Parser le HTML
    soup = analyser_html(html_brut)

    # Étape 3 : Déterminer l'URL de base pour les liens relatifs
    if nom_page == "home":
        url_page = URL_BASE
    else:
        url_page = f"{URL_BASE}?{nom_page}"

    # Étape 4 : Extraire et télécharger les ressources
    ressources = extraire_urls_ressources(soup, url_page)
    correspondances = {}  # {url_originale: chemin_local_relatif}

    log.info("  %d ressource(s) détectée(s).", len(ressources))

    for url_res, type_res in ressources.items():
        chemin_abs, chemin_rel = determiner_chemin_local(
            url_res, type_res, dossier_page, dossier_sortie
        )
        if chemin_abs:
            # Ressource locale à télécharger
            if telecharger_ressource(url_res, chemin_abs):
                correspondances[url_res] = chemin_rel
        else:
            # Ressource externe — garder l'URL d'origine
            correspondances[url_res] = chemin_rel

    # Étape 5 : Traitement spécial pour la page JSL (PDFs)
    if nom_page.upper() == "JSL":
        telecharger_pdfs_jsl(soup, url_page, dossier_sortie)

    # Étape 6 : Réécrire les URLs dans le HTML
    soup = reecrire_urls(soup, correspondances, est_racine)
    soup = reecrire_liens_internes(soup, dossier_page)

    # Étape 7 : Construire le HTML final propre
    html_final = construire_html_page(soup, nom_page, dossier_page)

    # Étape 8 : Sauvegarder le fichier HTML
    if dossier_page == ".":
        chemin_html = os.path.join(dossier_sortie, "index.html")
    else:
        chemin_html = os.path.join(dossier_sortie, dossier_page, "index.html")

    os.makedirs(os.path.dirname(chemin_html), exist_ok=True)

    with open(chemin_html, "w", encoding="utf-8") as f:
        f.write(html_final)

    log.info("  ✓ Page sauvegardée : %s", chemin_html)
    return True

# ---------------------------------------------------------------------------
# Orchestration principale
# ---------------------------------------------------------------------------


def scraper_toutes_les_pages(dossier_sortie, pages_a_traiter=None):
    """Scrape toutes les pages (ou une sélection) et les sauvegarde.

    Args:
        dossier_sortie: répertoire racine de sortie.
        pages_a_traiter: liste de noms de pages, ou None pour tout scraper.

    Returns:
        (nombre_succes, nombre_echecs)
    """
    if pages_a_traiter:
        # Filtrer les pages demandées
        pages = {}
        for nom in pages_a_traiter:
            # Chercher la correspondance (insensible à la casse)
            trouvee = False
            for cle_hg, dossier in PAGES.items():
                if cle_hg.lower() == nom.lower() or dossier == nom.lower():
                    pages[cle_hg] = dossier
                    trouvee = True
                    break
            if not trouvee:
                log.warning("Page inconnue : '%s'. Pages disponibles : %s",
                            nom, ", ".join(PAGES.keys()))
    else:
        pages = PAGES.copy()

    total = len(pages)
    log.info("  Scraping de %d page(s) depuis siratton.hotglue.me", total)
    log.info("Répertoire de sortie : %s", os.path.abspath(dossier_sortie))

    # Créer le répertoire de sortie
    os.makedirs(dossier_sortie, exist_ok=True)

    # Initialiser le navigateur
    driver = creer_navigateur()

    succes = 0
    echecs = 0

    try:
        for i, (nom_page, dossier_page) in enumerate(pages.items(), 1):
            log.info("\n[%d/%d] Page : %s", i, total, nom_page)
            try:
                if traiter_page(nom_page, dossier_page, dossier_sortie,
                                driver):
                    succes += 1
                else:
                    echecs += 1
            except Exception as e:
                log.error("  ✗ Erreur inattendue pour %s : %s", nom_page, e)
                echecs += 1
    finally:
        if driver:
            try:
                driver.quit()
                log.info("Navigateur fermé.")
            except Exception:
                pass

    # Résumé
    log.info("\n" + "=" * 60)
    log.info("RÉSUMÉ")
    log.info("=" * 60)
    log.info("  Pages traitées avec succès : %d/%d", succes, total)
    if echecs > 0:
        log.info("  Pages en échec : %d/%d", echecs, total)
    log.info("  Ressources téléchargées : %d fichier(s)",
             len(_ressources_vues))
    log.info("=" * 60)

    return succes, echecs

# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def main():
    """Point d'entrée principal du script."""
    parser = argparse.ArgumentParser(
        description="Scrape le site HotGlue siratton.hotglue.me et génère "
                    "des fichiers HTML statiques.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python tools/scrape_hotglue.py                    # Scraper toutes les pages
  python tools/scrape_hotglue.py --all              # Idem (explicite)
  python tools/scrape_hotglue.py --page JSL         # Une seule page
  python tools/scrape_hotglue.py --page JSL --page photos
  python tools/scrape_hotglue.py --output-dir build # Sortie dans ./build/

Pages disponibles :
  home, Agenda, Cieza, JSL, RSF, automediatheque, autres, contact,
  fea, home-EN, journalisme, journalisme-EN, niger, niger_analyse,
  niger_analyse_raw, niger_timeline, photos, photos-EN
        """,
    )

    parser.add_argument(
        "--output-dir",
        default=".",
        help="Répertoire de sortie (défaut : répertoire courant).",
    )
    parser.add_argument(
        "--page",
        action="append",
        dest="pages",
        metavar="NOM",
        help="Scraper une page spécifique (peut être répété). "
             "Ex : --page JSL --page photos",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scraper toutes les pages (comportement par défaut).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Activer les messages de débogage.",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        log.setLevel(logging.DEBUG)

    # Vérifier les dépendances
    if not REQUESTS_DISPONIBLE:
        log.error(
            "Les paquets requests et beautifulsoup4 sont requis.\n"
            "Installez-les avec : pip install -r tools/requirements.txt"
        )
        sys.exit(1)

    # Scraper
    succes, echecs = scraper_toutes_les_pages(
        dossier_sortie=args.output_dir,
        pages_a_traiter=args.pages,
    )

    sys.exit(0 if echecs == 0 else 1)


if __name__ == "__main__":
    main()
