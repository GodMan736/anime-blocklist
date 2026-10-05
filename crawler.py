import time
import random
import json
import os
import concurrent.futures
from datetime import datetime
from urllib.parse import urlparse

from curl_cffi import requests
from bs4 import BeautifulSoup

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

# ---------------------- CONFIGURAÇÕES ----------------------
GERAR_LOG_ARQUIVO = True
ARQUIVO_LOG = 'crawler_debug.log'
ARQUIVO_BLOCKLIST = 'blocklist.txt'
ARQUIVO_ESTADO = 'estado_rotacao.json'
ARQUIVO_CACHE_INSTANCIAS = 'cache_instancias_searxng.json'

BRAVE_API_KEY = os.environ.get('BRAVE_API_KEY', '')

ANIMES_ISCA = [
    "Overflow", "Masterpiece The Animation", "Master Piece", "Kuroinu",
    "Mankitsu Happening", "Oni Chichi", "Bible Black", "Shoujo Ramune",
    "Eroge H mo Game", "Resort Boin", "Kyonyuu Fantasy", "Baku Ane",
    "Toshi Densetsu", "Yakin Byoutou", "Sora no Iro Mizu no Iro", "Rance 01",
    "Discipline", "Boku no Pico", "Taimanin Asagi", "Sono Hanabira",
    "Interspecies Reviewers", "Do S", "Aku no Onna Kanbu", "Shin Ikki Tousen",
    "Honoo no Haramase"
]

QTD_POR_EXECUCAO = 3

PAGINAS_BING = 5
PAGINAS_STARTPAGE = 5
RESULTADOS_DDG = 25
RESULTADOS_BRAVE = 20
PAGINAS_BRAVE = 5

URL_LISTA_INSTANCIAS = "https://raw.githubusercontent.com/searxng/searx-instances/master/searxinstances/instances.yml"
CACHE_INSTANCIAS_VALIDADE_HORAS = 6
TIMEOUT_TESTE_INSTANCIA = 6
TIMEOUT_CONSULTA_INSTANCIA = 12

INSTANCIAS_FALLBACK = [
    "https://searx.be",
    "https://baresearch.org",
    "https://priv.au",
    "https://opnxng.com",
    "https://search.inetol.net",
]

TLDS_COMPOSTOS = {
    'com.br', 'co.uk', 'com.au', 'co.jp', 'co.in', 'com.mx',
    'net.br', 'org.br', 'gov.br', 'co.nz', 'com.ar'
}

WHITELIST = {
    'youtube.com', 'youtu.be', 'google.com', 'crunchyroll.com', 'amazon.com',
    'amazon.com.br', 'netflix.com', 'primevideo.com', 'justwatch.com',
    'myanimelist.net', 'imdb.com', 'themoviedb.org', 'wikipedia.org',
    'reddit.com', 'twitter.com', 'facebook.com', 'instagram.com', 'x.com',
    'github.com', 'dailymotion.com', 'adorocinema.com', 'linguee.com.br',
    'moodle.org', 't.co', 'pinterest.com', 'tiktok.com', 'crazygames.com',
    'miniplay.com', 'gamaverse.com', 'bing.com', 'aliexpress.com',
    'archive.org', 'plex.tv', 'bilibili.tv', 'ok.ru', 'kinorium.com',
    'pt.aliexpress.com', 'watch.plex.tv', 'm.ok.ru', 'en.kinorium.com',
    'infoanime.com.br', 'discord.com', 'drive.google.com',
    'animenewsnetwork.com', 'anisearch.com', 'animeclick.it', 'bilibili.com',
    'anime-planet.com', 'betaseries.com', 'chiaki.site', 'moviefone.com',
    'welcome.hidive.com', 'wetv.vip', 'yandex.com', 'duckduckgo.com',
    'startpage.com', 'brave.com', 'microsoft.com', 'msn.com', 'live.com',
    'search.brave.com', 'pluto.tv', 'globoplay.globo.com', 'anidb.net',
    'appliancesonline.com.au', 'coursera.org', 'creatureartteacher.com',
    'cybernews.com', 'dicio.com.br', 'expressvpn.com', 'goo.gl',
    'kbin.social', 'last.fm', 'linktr.ee', 'max.com', 'mollygram.com',
    'notegpt.io', 'online-go.com', 'onlinecourses.nptel.ac.in',
    'outlook.office365.com', 'pinetools.com', 'planetinternationalhotel.com',
    'similarweb.com', 'tensor.art', 'ventusky.com', 'vocalremover.org',
    'weather.com', 'w.iiseradmission.in', 'sherridress.ca', 'stopots.com',
    'victress.pk', 'coconut.sonolus.com', 'animationmentor.com',
    'caffyntheromele.blogspot.com', 'francobuchananinformations.blogspot.com',
    'firalterbaru.wiki', 'blogspot.com', 'samsung.com', 'samsung.cn', 
    'forbes.com', 'wsj.com', 'stackoverflow.com', 'stackoverflow.co', 
    'aarp.org', 'wikiwand.com', 'zhidao.baidu.com', 'zhihu.com', 
    'fandom.com', 'pbs.org', 'galaxus.ch', 'insurancepanda.com', 
    'progressive.com', 'moneygeek.com', 'clark.com', 'hulu.com',
    'paramountplus.com', 'microchip.com', 'yugioh.com', 'pioneer.org'
}

HEADERS_PADRAO = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
}

# ---------------------- FUNÇÕES AUXILIARES ----------------------

def log(msg, nivel="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{ts}] {msg}"
    print(linha)
    
    if GERAR_LOG_ARQUIVO:
        try:
            with open(ARQUIVO_LOG, 'a', encoding='utf-8') as f:
                f.write(f"[{nivel}] {linha}\n")
        except Exception:
            pass

def carregar_blocklist_atual():
    if not os.path.exists(ARQUIVO_BLOCKLIST):
        open(ARQUIVO_BLOCKLIST, 'w').close()
        return set()
    with open(ARQUIVO_BLOCKLIST, 'r') as f:
        return set(line.strip() for line in f if line.strip())

def salvar_blocklist(dominios):
    with open(ARQUIVO_BLOCKLIST, 'w') as f:
        for dominio in sorted(dominios):
            f.write(f"{dominio}\n")

def carregar_estado_rotacao():
    if not os.path.exists(ARQUIVO_ESTADO):
        return {"indice": 0}
    with open(ARQUIVO_ESTADO, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"indice": 0}

def salvar_estado_rotacao(estado):
    with open(ARQUIVO_ESTADO, 'w') as f:
        json.dump(estado, f)

def obter_lote_da_vez():
    estado = carregar_estado_rotacao()
    indice = estado.get("indice", 0)
    total = len(ANIMES_ISCA)
    lote = []
    for i in range(QTD_POR_EXECUCAO):
        lote.append(ANIMES_ISCA[(indice + i) % total])
    novo_indice = (indice + QTD_POR_EXECUCAO) % total
    salvar_estado_rotacao({"indice": novo_indice})
    return lote

def limpar_dominio(url):
    try:
        dominio = urlparse(url).netloc
        dominio = dominio.split('@')[-1]
        dominio = dominio.split(':')[0]
        return dominio.replace('www.', '').lower().strip()
    except Exception:
        return None

def extrair_dominio_base(dominio):
    partes = dominio.split('.')
    if len(partes) < 2:
        return dominio
    ultimos_dois = '.'.join(partes[-2:])
    ultimos_tres = '.'.join(partes[-3:]) if len(partes) >= 3 else None
    if ultimos_tres and ultimos_dois in TLDS_COMPOSTOS:
        return ultimos_tres
    return ultimos_dois

def dominio_esta_na_whitelist(dominio):
    dominio_base = extrair_dominio_base(dominio)
    if dominio in WHITELIST or dominio_base in WHITELIST:
        return True
    return False

# ---------------------- SEARXNG E BUSCAS ----------------------

def carregar_cache_instancias():
    if not os.path.exists(ARQUIVO_CACHE_INSTANCIAS):
        return None
    try:
        with open(ARQUIVO_CACHE_INSTANCIAS, 'r') as f:
            cache = json.load(f)
        timestamp_cache = datetime.fromisoformat(cache['timestamp'])
        idade_horas = (datetime.now() - timestamp_cache).total_seconds() / 3600
        if idade_horas < CACHE_INSTANCIAS_VALIDADE_HORAS:
            return cache['instancias']
    except Exception:
        pass
    return None

def salvar_cache_instancias(instancias):
    try:
        with open(ARQUIVO_CACHE_INSTANCIAS, 'w') as f:
            json.dump({'timestamp': datetime.now().isoformat(), 'instancias': instancias}, f)
    except Exception:
        pass

def buscar_lista_bruta_instancias():
    try:
        resp = requests.get(URL_LISTA_INSTANCIAS, headers=HEADERS_PADRAO, timeout=10, verify=False)
        if resp.status_code != 200:
            return []
        import yaml
        dados = yaml.safe_load(resp.text)
        urls = [k.rstrip('/') for k in dados.keys() if k.startswith('https://')]
        return urls
    except Exception as e:
        log(f"Falha ao obter YAML das instâncias: {e}", "ERROR")
        return []

def testar_saude_instancia(url_instancia, sessao):
    url_api = f"{url_instancia}/search"
    params = {'q': 'test'} 
    try:
        resp = sessao.get(url_api, params=params, headers=HEADERS_PADRAO, timeout=TIMEOUT_TESTE_INSTANCIA, verify=False)
        if resp.status_code == 200 and '<html' in resp.text.lower():
            return url_instancia
    except Exception:
        pass
    return None

def descobrir_instancias_disponiveis():
    cache = carregar_cache_instancias()
    if cache:
        log(f"-> Usando cache de instâncias SearXNG ({len(cache)} saudáveis).")
        return cache

    log("-> Buscando instâncias SearXNG...")
    lista_bruta = buscar_lista_bruta_instancias()
    if not lista_bruta:
        salvar_cache_instancias(INSTANCIAS_FALLBACK)
        return INSTANCIAS_FALLBACK

    sessao_teste = requests.Session(impersonate="chrome120")
    saudaveis = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        futuros = [executor.submit(testar_saude_instancia, url, sessao_teste) for url in lista_bruta]
        for futuro in concurrent.futures.as_completed(futuros):
            resultado = futuro.result()
            if resultado:
                saudaveis.append(resultado)
                log(f"    [+] OK: {resultado}")

    if not saudaveis:
        salvar_cache_instancias(INSTANCIAS_FALLBACK)
        return INSTANCIAS_FALLBACK

    salvar_cache_instancias(saudaveis)
    return saudaveis

def consultar_searxng_todas_instancias(query, sessao, instancias_disponiveis):
    links_agregados = set()
    instancias_ok = 0
    instancias_falha = 0

    for url_instancia in instancias_disponiveis:
        url_api = f"{url_instancia}/search"
        
        # Pulo do gato: Adicionamos 'format': 'json' para tentar a API nativa
        params = {'q': query, 'safesearch': 1, 'categories': 'general', 'language': 'pt', 'format': 'json'}

        try:
            response = sessao.get(url_api, params=params, headers=HEADERS_PADRAO, timeout=TIMEOUT_CONSULTA_INSTANCIA, verify=False)
            
            if response.status_code == 200:
                links_encontrados = []
                
                # 1. Tenta decodificar via JSON (Burlar qualquer tema visual)
                try:
                    dados = response.json()
                    for result in dados.get('results', []):
                        href = result.get('url')
                        if href and href.startswith('http'):
                            links_encontrados.append(href)
                except Exception:
                    # 2. Fallback Incondicional: API JSON bloqueada, força raspagem bruta do HTML
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for tag in soup.select('a[href]'):
                        href = tag.get('href')
                        # Ignora links internos da instância
                        if href and href.startswith('http') and not href.startswith(url_instancia):
                            hl = href.lower()
                            # Filtra botões da UI do SearXNG e links inúteis recorrentes
                            if not any(lixo in hl for lixo in ['searxng', 'preferences', '/search?', 'image_proxy', 'wikipedia.org']):
                                links_encontrados.append(href)
                
                if links_encontrados:
                    # Remove duplicatas locais e injeta na lista global
                    links_unicos = list(set(links_encontrados))
                    links_agregados.update(links_unicos)
                    instancias_ok += 1
                    log(f"    [+] SearXNG ({url_instancia}): {len(links_unicos)} links")
                else:
                    instancias_falha += 1
                    log(f"    [!] SearXNG ({url_instancia}): HTML recebido, mas nenhum link útil extraído.", "DEBUG")
            
            elif response.status_code == 429:
                # Omitindo logs repetitivos de Rate Limit
                instancias_falha += 1
            else:
                instancias_falha += 1
                log(f"    [!] SearXNG ({url_instancia}) Status HTTP: {response.status_code}", "DEBUG")
        
        except requests.exceptions.Timeout:
            instancias_falha += 1
            log(f"    [!] SearXNG ({url_instancia}): Timeout esgotado após {TIMEOUT_CONSULTA_INSTANCIA}s.", "DEBUG")
        except Exception as e:
            instancias_falha += 1
            log(f"    [!] SearXNG ({url_instancia}) Erro: {type(e).__name__}", "DEBUG")

        # Mantém o delay para não estourar a fila da thread
        time.sleep(random.uniform(2.5, 4.0))

    return list(links_agregados), instancias_ok, instancias_falha

def consultar_duckduckgo(query, ddgs_client, max_results=RESULTADOS_DDG):
    try:
        resultados = list(ddgs_client.text(query, safesearch='on', max_results=max_results))
        return [r.get('href', '') for r in resultados if r.get('href')]
    except Exception as e:
        log(f"    [-] Erro DuckDuckGo: {type(e).__name__}", "ERROR")
        return []

def consultar_bing(query, sessao, paginas=PAGINAS_BING):
    links = []
    url_busca = "https://www.bing.com/search"
    for pagina in range(paginas):
        params = {'q': query, 'first': (pagina * 10) + 1}
        try:
            response = sessao.get(url_busca, params=params, headers=HEADERS_PADRAO, timeout=10, verify=False)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                encontrados = [tag.get('href') for tag in soup.select('li.b_algo h2 a') if tag.get('href')]
                links.extend(encontrados)
                if not encontrados: break
            else:
                break
        except Exception as e:
            log(f"    [-] Erro Bing (pg {pagina}): {type(e).__name__}", "ERROR")
            break
        time.sleep(random.uniform(1, 2))
    return links

def consultar_startpage(query, sessao, paginas=PAGINAS_STARTPAGE):
    links = []
    url_busca = "https://www.startpage.com/sp/search"
    seletores = ['a.result-link', 'a.w-gl__result-url', 'a.w-gl__result-title', 'div.result a[href]']
    for pagina in range(paginas):
        params = {'query': query, 'cat': 'web', 'page': pagina + 1}
        try:
            # verify=False resolve o SSLError reportado nos logs do Startpage
            response = sessao.get(url_busca, params=params, headers=HEADERS_PADRAO, timeout=10, verify=False)
            if response.status_code != 200: break
            soup = BeautifulSoup(response.text, 'html.parser')
            encontrados = []
            for sel in seletores:
                tags = soup.select(sel)
                for t in tags:
                    h = t.get('href')
                    if h and h.startswith('http') and 'startpage.com' not in h:
                        encontrados.append(h)
                if encontrados: break
            if not encontrados: break
            links.extend(encontrados)
        except Exception as e:
            log(f"    [-] Erro Startpage (pg {pagina}): {type(e).__name__}", "ERROR")
            break
        time.sleep(random.uniform(1, 2))
    return links

def consultar_brave(query, sessao, paginas=PAGINAS_BRAVE, count=RESULTADOS_BRAVE):
    links = []
    if not BRAVE_API_KEY: return links
    url_api = "https://api.search.brave.com/res/v1/web/search"
    headers = {'Accept': 'application/json', 'X-Subscription-Token': BRAVE_API_KEY}
    for pagina in range(paginas):
        params = {'q': query, 'safesearch': 'off', 'count': count, 'offset': pagina * count}
        try:
            response = sessao.get(url_api, params=params, headers=headers, timeout=10, verify=False)
            if response.status_code == 200:
                dados = response.json()
                novos = [r.get('url') for r in dados.get('web', {}).get('results', []) if r.get('url')]
                if not novos: break
                links.extend(novos)
            else:
                break
        except Exception as e:
            log(f"    [-] Erro Brave (pg {pagina}): {type(e).__name__}", "ERROR")
            break
        time.sleep(random.uniform(1, 2))
    return links

def gerar_query_busca(titulo):
    return f"Assistir {titulo} Episodio Online"

def extrair_dominios_piratas(lote_animes, instancias_searxng):
    novos_dominios = set()
    stats = {"queries": 0, "links_brutos": 0, "erros": {"searxng": 0, "ddg": 0, "bing": 0, "startpage": 0, "brave": 0}}
    
    sessao_http = requests.Session(impersonate="chrome120")

    with DDGS() as ddgs:
        for anime in lote_animes:
            query = gerar_query_busca(anime)
            stats["queries"] += 1
            log(f"\n-> Pesquisando: [{query}]")
            links_brutos = set()

            links_searx, ok_count, falha_count = consultar_searxng_todas_instancias(query, sessao_http, instancias_searxng)
            if links_searx:
                links_brutos.update(links_searx)
                log(f"    [=] SearXNG agregado: {len(links_searx)} links de {ok_count} instâncias ({falha_count} falhas)")
            else:
                stats["erros"]["searxng"] += 1

            time.sleep(random.uniform(1.5, 3))

            links_ddg = consultar_duckduckgo(query, ddgs)
            if links_ddg:
                links_brutos.update(links_ddg)
                log(f"    [+] DuckDuckGo: {len(links_ddg)} links")
            else:
                stats["erros"]["ddg"] += 1

            time.sleep(random.uniform(1.5, 3))

            links_bing = consultar_bing(query, sessao_http)
            if links_bing:
                links_brutos.update(links_bing)
                log(f"    [+] Bing: {len(links_bing)} links")
            else:
                stats["erros"]["bing"] += 1

            time.sleep(random.uniform(1.5, 3))

            links_startpage = consultar_startpage(query, sessao_http)
            if links_startpage:
                links_brutos.update(links_startpage)
                log(f"    [+] Startpage: {len(links_startpage)} links")
            else:
                stats["erros"]["startpage"] += 1

            time.sleep(random.uniform(1.5, 3))

            links_brave = consultar_brave(query, sessao_http)
            if links_brave:
                links_brutos.update(links_brave)
                log(f"    [+] Brave: {len(links_brave)} links")
            elif BRAVE_API_KEY:
                stats["erros"]["brave"] += 1

            stats["links_brutos"] += len(links_brutos)

            for url in links_brutos:
                dominio = limpar_dominio(url)
                if not dominio or '.' not in dominio:
                    continue
                if not dominio_esta_na_whitelist(dominio):
                    novos_dominios.add(dominio)

            time.sleep(random.uniform(4, 7))

    return novos_dominios, stats

def main():
    if GERAR_LOG_ARQUIVO and os.path.exists(ARQUIVO_LOG):
        open(ARQUIVO_LOG, 'w').close() 
        
    log("Iniciando rotina de rastreamento robusta (TLS ByPass + Fallback Parser)...")

    if not BRAVE_API_KEY:
        log("-> Aviso: BRAVE_API_KEY não configurada. Fonte Brave será ignorada.")

    instancias_searxng = descobrir_instancias_disponiveis()

    blocklist = carregar_blocklist_atual()
    tamanho_inicial = len(blocklist)
    log(f"-> Blocklist atual: {tamanho_inicial} domínios.")

    lote = obter_lote_da_vez()
    log(f"-> Lote desta execução ({len(lote)} títulos): {', '.join(lote)}\n")

    novos_dominios, stats = extrair_dominios_piratas(lote, instancias_searxng)

    blocklist.update(novos_dominios)
    tamanho_final = len(blocklist)
    qtd_novos = tamanho_final - tamanho_inicial

    log("\n===================================")
    log(f"Queries executadas: {stats['queries']}")
    log(f"Links brutos coletados: {stats['links_brutos']}")
    log(f"Falhas por fonte: {stats['erros']}")

    if qtd_novos > 0:
        log(f"SUCESSO: {qtd_novos} novos domínios encontrados e purificados!")
        salvar_blocklist(blocklist)
    else:
        log("Nenhum domínio novo classificado. Arquivo mantido.")

if __name__ == "__main__":
    main()