from scholarly import scholarly, ProxyGenerator
from scholarly._navigator import Navigator
from bs4 import BeautifulSoup
import time
import csv
import stem.control
import stem
import re
import requests
import json
import os

LOG_CALLBACK = None
STOP_EVENT   = None

def my_print(*args, **kwargs):
    msg = ' '.join(map(str, args))
    if LOG_CALLBACK:
        LOG_CALLBACK(msg)
    print(*args, **kwargs)

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
scimago_path = os.path.join(BASE_DIR, "Assets", "scimagojr_2025.json")

SCIMAGO_DATA = {}
if os.path.exists(scimago_path):
    with open(scimago_path, "r", encoding="utf-8") as f:
        SCIMAGO_DATA = json.load(f)

# ── Tor helpers ────────────────────────────────────────────────────────────────
def setup_custom_tor():
    """
    Directly inject a Tor SOCKS5 session into scholarly's Navigator singleton,
    bypassing scholarly.use_proxy() which spawns an unreliable FreeProxy secondary.
    Verifies the connection can actually reach Google Scholar before proceeding.
    """
    my_print("Configuring scholarly to use Tor SOCKS proxy...")

    tor_proxies = {
        'http://':  'socks5://127.0.0.1:9150',
        'https://': 'socks5://127.0.0.1:9150'
    }

    # ── Build a working proxy session ──────────────────────────────────────────
    pg = ProxyGenerator()
    pg._proxies     = tor_proxies
    pg._proxy_works = True
    pg._can_refresh_tor = True
    pg._tor_control_port = 9151
    pg._tor_password = None
    pg._new_session(proxies=tor_proxies)

    # ── Inject directly into Navigator (skip FreeProxy secondary spawn) ─────────
    nav = Navigator()
    nav.pm1      = pg
    nav.pm2      = pg          # use same Tor session as secondary too
    nav._session1 = pg.get_session()
    nav._session2 = pg.get_session()

    # ── Verify Tor is actually reachable ───────────────────────────────────────
    MAX_VERIFY_ATTEMPTS = 3
    for attempt in range(1, MAX_VERIFY_ATTEMPTS + 1):
        try:
            resp = pg.get_session().get(
                "https://scholar.google.com",
                timeout=15,
                follow_redirects=True
            )
            if resp.status_code == 200:
                my_print(f"Proxy verified successfully! (attempt {attempt})")
                return pg
            elif resp.status_code == 429 or resp.status_code == 503:
                my_print(f"Google Scholar blocked this Tor exit node (HTTP {resp.status_code}). Rotating IP...")
                if rotate_tor_ip():
                    pg._new_session(proxies=tor_proxies)
                    nav._session1 = pg.get_session()
                    nav._session2 = pg.get_session()
            else:
                my_print(f"Unexpected status {resp.status_code} from Scholar. Continuing anyway...")
                return pg
        except Exception as e:
            my_print(f"Tor connectivity check failed (attempt {attempt}/{MAX_VERIFY_ATTEMPTS}): {e}")
            if attempt < MAX_VERIFY_ATTEMPTS:
                my_print("Retrying after IP rotation...")
                rotate_tor_ip()
                pg._new_session(proxies=tor_proxies)
                nav._session1 = pg.get_session()
                nav._session2 = pg.get_session()

    my_print("WARNING: Could not verify Tor connection to Google Scholar. Proceeding anyway — results may be empty.")
    my_print("         Make sure Tor Browser is open and running on port 9150.")
    return pg


def rotate_tor_ip():
    """Rotate the Tor circuit via the control port. Returns True on success."""
    my_print("Requesting new Tor IP...")
    try:
        with stem.control.Controller.from_port(port=9151) as controller:
            controller.authenticate()
            controller.signal(stem.Signal.NEWNYM)
            time.sleep(5)
            my_print("Switched to new Tor circuit (New IP assigned).")
            return True
    except Exception as e:
        my_print(f"Failed to rotate IP: {e}")
        my_print("Please ensure Tor Browser is OPEN in the background.")
        return False

# ── Crossref metadata ──────────────────────────────────────────────────────────
def get_extended_metadata(title, url):
    meta = {
        "DOI": "N/A", "Publisher": "N/A", "Open Access": "N/A",
        "Authors (Crossref)": "N/A", "Exact Journal": "N/A"
    }
    doi = None
    doi_pattern = re.compile(r'(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)')
    if url:
        match = doi_pattern.search(url)
        if match:
            doi = match.group(1).rstrip('.')
    item = None
    try:
        if doi:
            resp = requests.get(f"https://api.crossref.org/works/{doi}", timeout=5)
            if resp.status_code == 200:
                item = resp.json().get("message", {})
        if not item:
            resp = requests.get("https://api.crossref.org/works",
                                params={"query.bibliographic": title, "rows": 1}, timeout=5)
            if resp.status_code == 200:
                items = resp.json().get("message", {}).get("items", [])
                if items and title[:15].lower() in items[0].get("title", [""])[0].lower():
                    item = items[0]
        if item:
            meta["DOI"]       = item.get("DOI", doi if doi else "N/A")
            meta["Publisher"] = item.get("publisher", "N/A")
            container         = item.get("container-title", [])
            meta["Exact Journal"] = container[0] if container else "N/A"
            licenses          = item.get("license", [])
            is_oa             = any("creativecommons" in l.get("URL","").lower() for l in licenses)
            meta["Open Access"] = "Yes (CC)" if is_oa else "Unknown"
            authors = item.get("author", [])
            a_list  = []
            for a in authors:
                name      = f"{a.get('given','')} {a.get('family','')}".strip()
                orcid     = a.get("ORCID","").replace("http://orcid.org/","")
                affils    = [aff.get("name","") for aff in a.get("affiliation",[])]
                affil_str = f" [{', '.join(affils)}]" if affils else ""
                orcid_str = f" (ORCID: {orcid})" if orcid else ""
                a_list.append(f"{name}{orcid_str}{affil_str}")
            meta["Authors (Crossref)"] = "; ".join(a_list) if a_list else "N/A"
            
            # Crossref sometimes has abstracts, though they often contain XML JATS tags
            raw_abstract = item.get("abstract")
            if raw_abstract:
                clean_abs = re.sub(r'<[^>]+>', '', raw_abstract).strip()
                if len(clean_abs) > 20:
                    meta["Abstract (Crossref)"] = clean_abs
                    
    except Exception:
        pass
    return meta

def get_full_abstract(doi, title=None):
    if doi and doi != "N/A": 
        try:
            url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=abstract"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                abs_text = resp.json().get('abstract')
                if abs_text and len(abs_text) > 20:
                    return abs_text
        except Exception:
            pass
            
    if title:
        try:
            url = f"https://api.semanticscholar.org/graph/v1/paper/search"
            resp = requests.get(url, params={"query": title, "fields": "abstract,title", "limit": 1}, timeout=5)
            if resp.status_code == 200:
                items = resp.json().get('data', [])
                if items:
                    found_title = items[0].get('title', '').lower()
                    if title[:20].lower() in found_title:
                        abs_text = items[0].get('abstract')
                        if abs_text and len(abs_text) > 20:
                            return abs_text
        except Exception:
            pass

        # Tertiary fallback: OpenAlex API
        try:
            url = f"https://api.openalex.org/works?search={title}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('results'):
                    item = data['results'][0]
                    inv = item.get('abstract_inverted_index')
                    if inv:
                        max_idx = max([max(pos) for pos in inv.values()])
                        words = [""] * (max_idx + 1)
                        for word, positions in inv.items():
                            for pos in positions:
                                words[pos] = word
                        abs_text = " ".join(words)
                        if len(abs_text) > 20:
                            return abs_text
        except Exception:
            pass
            
    return None

# ── Filter engine ──────────────────────────────────────────────────────────────
def passes_filters(row_data, filters):
    """
    Returns (passed: bool, reason: str|None).
    All active filters must pass for the paper to be accepted.
    """
    if not filters:
        return True, None

    # Open Access
    if filters.get('open_access'):
        oa = str(row_data.get('Open Access', '')).lower()
        if 'yes' not in oa:
            return False, 'Not open access'

    # Quartile (list of accepted values, e.g. ['Q1','Q2'])
    quartiles = [q for q in filters.get('quartiles', []) if q]
    if quartiles:
        paper_q = str(row_data.get('Quartile (SCImago)', 'N/A'))
        if paper_q not in quartiles:
            return False, f'Quartile {paper_q} (need {"/".join(quartiles)})'

    # H-Index >=
    min_h = filters.get('min_h_index')
    if min_h is not None:
        try:
            h = float(str(row_data.get('H-index (SCImago)', 0) or 0).replace(',', '.'))
            if h < float(min_h):
                return False, f'H-Index {h} < {min_h}'
        except Exception:
            return False, 'H-Index N/A'

    # SJR >=
    min_sjr = filters.get('min_sjr')
    if min_sjr is not None:
        try:
            sjr = float(str(row_data.get('SJR Score (SCImago)', 0) or 0).replace(',', '.'))
            if sjr < float(min_sjr):
                return False, f'SJR {sjr} < {min_sjr}'
        except Exception:
            return False, 'SJR N/A'

    # Citations >=
    min_cit = filters.get('min_citations')
    if min_cit is not None:
        try:
            cit = int(str(row_data.get('Citations Count', 0) or 0))
            if cit < int(min_cit):
                return False, f'Citations {cit} < {min_cit}'
        except Exception:
            return False, 'Citations N/A'

    # Journal (any match)
    journals = [j.strip().lower() for j in filters.get('journals', []) if j and j.strip()]
    if journals:
        paper_j = str(row_data.get('Journal/Venue (Scholar)', '') or '').lower()
        if not any(j in paper_j or paper_j in j for j in journals):
            return False, 'Journal not matched'

    # Publisher (any match)
    publishers = [p.strip().lower() for p in filters.get('publishers', []) if p and p.strip()]
    if publishers:
        paper_p = str(row_data.get('Publisher', '') or '').lower()
        if not any(p in paper_p or paper_p in p for p in publishers):
            return False, 'Publisher not matched'

    return True, None


# ── PDF Downloader Helpers ─────────────────────────────────────────────────────
def sanitize_filename(title):
    """
    Cleans the title so that it only contains alphanumeric characters and underscores,
    preventing any file system exceptions (dot, hyphens, slashes, or other special signs).
    """
    cleaned = re.sub(r'[^a-zA-Z0-9\s_]', ' ', title)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = cleaned.replace(' ', '_')
    # Limit length to 100 characters to prevent path limit errors on Windows
    cleaned = cleaned[:100].strip('_')
    return cleaned + ".pdf"


def download_file(url, dest_path, headers=None, verify=True, timeout=20):
    """Downloads a file and checks if the output is a valid PDF."""
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, verify=verify)
        if resp.status_code == 200 and resp.content.startswith(b'%PDF'):
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            return True
    except Exception:
        pass
    return False


def get_sidesgame_pdf_url(doi):
    """Queries the sidesgame Sci-Hub mirror to get the direct PDF link for a DOI."""
    if not doi or doi == "N/A":
        return None
    url = f"https://sci-hub.sidesgame.com/{doi}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            # 1. Search for embed
            embed = soup.find('embed', type='application/pdf')
            if embed and embed.get('src'):
                pdf_url = embed['src']
                if pdf_url.startswith('//'):
                    pdf_url = "https:" + pdf_url
                return pdf_url
            
            # 2. Search for iframe
            iframe = soup.find('iframe', id='pdf')
            if iframe and iframe.get('src'):
                pdf_url = iframe['src']
                if pdf_url.startswith('//'):
                    pdf_url = "https:" + pdf_url
                return pdf_url
            
            # 3. Search for button locations
            for btn in soup.find_all('button', onclick=re.compile(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]")):
                onclick = btn['onclick']
                onclick = onclick.replace('\\/', '/').replace('\\', '')
                match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", onclick)
                if match:
                    pdf_url = match.group(1)
                    if pdf_url.startswith('//'):
                        pdf_url = "https:" + pdf_url
                    return pdf_url
    except Exception:
        pass
    return None


# ── Main scraper ───────────────────────────────────────────────────────────────
def search_scholar(query, output_file=None, target_count=20,
                   year_low=None, year_high=None,
                   stop_event=None, filters=None):
    if output_file is None:
        output_file = os.path.join(BASE_DIR, "Data Folder", "scholar_results.csv")

    my_print(f"Searching for: {query}")
    if filters:
        my_print(f"Active filters: {filters}")

    # ── Init Scholar search ──
    search_query = None
    max_retries  = 5
    for attempt in range(max_retries):
        if stop_event and stop_event.is_set():
            my_print("[STOPPED] Task cancelled by user.")
            return
        try:
            search_query = scholarly.search_pubs(query, year_low=year_low, year_high=year_high)
            break
        except Exception as e:
            my_print(f"Blocked on initial search (Attempt {attempt+1}/{max_retries}): {e}")
            rotate_tor_ip()

    if not search_query:
        my_print("Failed to initialize search after multiple retries. Exiting.")
        return

    headers = [
        "Title", "Year", "Journal/Venue (Scholar)",
        "Quartile (SCImago)", "H-index (SCImago)", "SJR Score (SCImago)",
        "Citations Count", "Abstract/Snippet", "Authors (Scholar)",
        "Publisher", "Open Access", "Categories & Areas (SCImago)",
        "Country (SCImago)", "Paper Link", "PDF Link",
        "DOI", "Authors (Crossref)"
    ]

    # Safeguard: don't crawl more than 50x the target (prevents infinite loop)
    MAX_CRAWL     = max(target_count * 50, 500)
    qualified     = 0
    crawled       = 0
    seen_titles   = set()

    with open(output_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()

        # ── Pre-flight: detect immediate 0-result (blocked Tor exit node) ────────
        ZERO_RESULT_RETRIES = 3
        for zero_attempt in range(ZERO_RESULT_RETRIES):
            try:
                first_paper = next(search_query)
                # Got at least one result — break and process it below
                break
            except StopIteration:
                if zero_attempt < ZERO_RESULT_RETRIES - 1:
                    my_print(f"[WARNING] Query returned 0 results immediately — Tor exit node may be blocked. "
                             f"Rotating IP and retrying (attempt {zero_attempt + 1}/{ZERO_RESULT_RETRIES})...")
                    rotated = rotate_tor_ip()
                    if not rotated:
                        my_print("IP rotation failed — Tor Browser may not be running. Cannot retry.")
                        break
                    # Re-initialise the search iterator with the new exit node
                    try:
                        search_query = scholarly.search_pubs(query, year_low=year_low, year_high=year_high)
                        continue
                    except Exception as e:
                        my_print(f"Re-search after rotation failed: {e}")
                        break
                else:
                    my_print("No results found after all retry attempts. The query may have no matching papers, "
                             "or all Tor exit nodes are blocked by Google Scholar.")
                    my_print("Try opening Tor Browser and running again, or use a VPN/different network.")
                    first_paper = None
                    break
            except Exception:
                first_paper = None
                break
        else:
            first_paper = None

        if first_paper is None:
            # Genuinely no results or could not recover
            pass
        else:
            # We have the first paper — inject it back into the processing loop
            # by using an inline generator that yields first_paper then continues search_query
            def _chain(first, rest):
                yield first
                yield from rest
            search_query = _chain(first_paper, search_query)

        while qualified < target_count and crawled < MAX_CRAWL:
            if stop_event and stop_event.is_set():
                my_print("[STOPPED] Task cancelled by user.")
                break
            try:
                paper  = next(search_query)
                crawled += 1
                bib    = paper.get('bib', {})

                title    = bib.get('title', 'N/A')
                title_norm = title.strip().lower()
                if title_norm in seen_titles:
                    my_print(f"    [SKIP #{crawled}] Duplicate title detected (overlapping pages) — \"{title[:55]}\"")
                    continue
                seen_titles.add(title_norm)

                year     = bib.get('pub_year', 'N/A')
                venue    = bib.get('venue', 'N/A')
                abstract = bib.get('abstract', 'N/A')
                authors  = (", ".join(bib.get('author', []))
                            if isinstance(bib.get('author'), list)
                            else bib.get('author', 'N/A'))
                citations = paper.get('num_citations', 0)
                pub_url   = paper.get('pub_url', 'N/A')
                pdf_url   = paper.get('eprint_url', 'N/A')

                # Crossref
                crmeta       = get_extended_metadata(title, pub_url)
                exact_journal = crmeta.pop("Exact Journal", "N/A")
                search_name  = (exact_journal if exact_journal != "N/A" else venue
                                ).strip('… .').lower()

                # SCImago lookup
                scimago_match = SCIMAGO_DATA.get(search_name)
                if not scimago_match:
                    for sjr_title, sjr_info in SCIMAGO_DATA.items():
                        if search_name == sjr_title or (len(search_name) > 8 and search_name in sjr_title):
                            scimago_match = sjr_info
                            break

                sjr_q = scimago_match.get("Quartile", "N/A") if scimago_match else "N/A"
                sjr_h = scimago_match.get("H-index", "N/A") if scimago_match else "N/A"
                sjr_s = scimago_match.get("SJR",     "N/A") if scimago_match else "N/A"
                sjr_cat = "N/A"
                if scimago_match:
                    cat_val  = scimago_match.get("Categories", "")
                    area_val = scimago_match.get("Areas", "")
                    if cat_val and area_val:
                        sjr_cat = f"{cat_val} | {area_val}"
                    elif cat_val or area_val:
                        sjr_cat = cat_val or area_val
                sjr_c = scimago_match.get("Country", "N/A") if scimago_match else "N/A"

                row = {
                    "Title": title, "Year": year, "Journal/Venue (Scholar)": venue,
                    "Abstract/Snippet": abstract, "Authors (Scholar)": authors,
                    "Citations Count": citations, "Paper Link": pub_url, "PDF Link": pdf_url,
                    "Quartile (SCImago)": sjr_q, "H-index (SCImago)": sjr_h,
                    "SJR Score (SCImago)": sjr_s,
                    "Categories & Areas (SCImago)": sjr_cat, "Country (SCImago)": sjr_c
                }
                row.update(crmeta)

                # ── Apply filters ──────────────────────────────────────────────
                passed, reason = passes_filters(row, filters)
                if not passed:
                    short_title = title[:55] + ('...' if len(title) > 55 else '')
                    my_print(f"    [SKIP #{crawled}] {reason} — \"{short_title}\"")
                    time.sleep(1)
                    continue

                # ── Qualified paper ─────────────────────────────────────────────
                
                # Abstract Fetching Pipeline: Crossref -> Semantic Scholar -> OpenAlex
                cr_abs = crmeta.get("Abstract (Crossref)")
                if cr_abs:
                    row["Abstract/Snippet"] = cr_abs
                else:
                    full_abstract = get_full_abstract(row.get('DOI'), row.get('Title'))
                    if full_abstract and len(full_abstract) > 20:
                        row["Abstract/Snippet"] = full_abstract
                
                # ── PDF Downloader Pipeline ──────────────────────────────────────────
                output_dir = os.path.dirname(output_file)
                pdf_filename = sanitize_filename(title)
                pdf_filepath = os.path.join(output_dir, pdf_filename)
                
                downloaded = False
                dl_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                
                # Step 1: Direct Google Scholar PDF link
                if pdf_url and pdf_url != 'N/A' and pdf_url.startswith('http'):
                    my_print(f"    -> [PDF] Downloading via direct Scholar link...")
                    if download_file(pdf_url, pdf_filepath, headers=dl_headers):
                        downloaded = True
                        my_print(f"    ✅ PDF downloaded successfully: {pdf_filename}")
                
                # Step 2: Sci-Hub Fallback using DOI
                if not downloaded and row.get('DOI') and row.get('DOI') != 'N/A':
                    my_print(f"    -> [PDF] Attempting Sci-Hub mirror download...")
                    sh_pdf_url = get_sidesgame_pdf_url(row['DOI'])
                    if sh_pdf_url:
                        sh_headers = dl_headers.copy()
                        sh_headers['Referer'] = 'https://sci-hub.sidesgame.com/'
                        if download_file(sh_pdf_url, pdf_filepath, headers=sh_headers):
                            downloaded = True
                            my_print(f"    ✅ PDF downloaded successfully via Sci-Hub: {pdf_filename}")
                
                if not downloaded:
                    my_print("    ❌ No free PDF downloaded for this paper.")

                qualified += 1
                my_print(f"[{qualified}/{target_count}] Title: {title}")
                my_print(f"    Year: {year} | DOI: {crmeta['DOI']} | Quartile: {sjr_q} | Publisher: {crmeta['Publisher']}")


                writer.writerow(row)
                file.flush()
                time.sleep(2)

            except StopIteration:
                my_print("No more results found for this query.")
                break
            except Exception as e:
                if stop_event and stop_event.is_set():
                    my_print("[STOPPED] Task cancelled by user.")
                    break
                my_print(f"Blocked or error encountered: {e}")
                rotate_tor_ip()
                try:
                    my_print(f"Resuming search from index {crawled}...")
                    search_query = scholarly.search_pubs(query, year_low=year_low, year_high=year_high, start_index=crawled)
                except Exception as re_err:
                    my_print(f"Failed to re-initialize search iterator: {re_err}")

    my_print(f"Extraction complete! Saved {qualified} results to '{output_file}'")
    my_print(f"(Crawled {crawled} papers total to find {qualified} qualifying papers)")

if __name__ == "__main__":
    setup_custom_tor()
    search_term = '"river bank erosion" AND ("GIS" OR "Remote Sensing" OR "DSAS" OR "morphological change")'
    out_path    = os.path.join(BASE_DIR, "Data Folder", "river_erosion_papers.csv")
    search_scholar(search_term, output_file=out_path, target_count=50)

