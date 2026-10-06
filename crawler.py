import base64
import concurrent.futures
import json
import os
import random
import re
import time
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse
from collections import Counter

from bs4 import BeautifulSoup
from curl_cffi import requests

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


# ============================================================
# CONFIGURAÇÕES
# ============================================================

GERAR_LOG_ARQUIVO = True
ARQUIVO_LOG = "crawler_debug.log"
ARQUIVO_BLOCKLIST = "blocklist.txt"
ARQUIVO_BLOCKLIST_ADGUARD = "adguard_blocklist.txt"
ARQUIVO_ESTADO = "estado_rotacao.json"
ARQUIVO_CACHE_INSTANCIAS = "cache_instancias_searxng.json"

BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")

QTD_POR_EXECUCAO = 3

PAGINAS_BING = 5
PAGINAS_STARTPAGE = 0
RESULTADOS_DDG = 25
RESULTADOS_BRAVE = 20
PAGINAS_BRAVE = 5

# O cache guarda o catálogo completo por este período.
CACHE_INSTANCIAS_VALIDADE_HORAS = 2

TIMEOUT_LISTA_INSTANCIAS = 15
TIMEOUT_CONSULTA_INSTANCIA = 15

# Todas as instâncias do catálogo são submetidas às consultas.
WORKERS_SEARXNG = 8

URL_LISTA_INSTANCIAS = (
    "https://raw.githubusercontent.com/searxng/"
    "searx-instances/master/searxinstances/instances.yml"
)

INSTANCIAS_FALLBACK = [
    "https://searx.be",
    "https://baresearch.org",
    "https://priv.au",
    "https://opnxng.com",
    "https://search.inetol.net",
]

HEADERS_PADRAO = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,application/json;q=0.8,*/*;q=0.7"
    ),
}

ANIMES_ISCA = [
    "Overflow",
    "Masterpiece The Animation",
    "Master Piece",
    "Kuroinu",
    "Mankitsu Happening",
    "Oni Chichi",
    "Bible Black",
    "Shoujo Ramune",
    "Eroge H mo Game",
    "Resort Boin",
    "Kyonyuu Fantasy",
    "Baku Ane",
    "Toshi Densetsu",
    "Yakin Byoutou",
    "Sora no Iro Mizu no Iro",
    "Rance 01",
    "Discipline",
    "Boku no Pico",
    "Taimanin Asagi",
    "Sono Hanabira",
    "Interspecies Reviewers",
    "Do S",
    "Aku no Onna Kanbu",
    "Shin Ikki Tousen",
    "Honoo no Haramase",
]


# ============================================================
# WHITELIST
# ============================================================

SEMPRE_BLOQUEAR = {
    "sukebei.nyaa.si",
    "xvideos.com",
    "kantanrucloofzrfn7vqlsxbhipkqv55qygn4oxogbnjpfex54bw4gad.onion",
}


def _d(texto):
    return set(texto.split())


# Sufixos oficiais tratados de maneira controlada.
# Isso cobre subdomínios como caixa.gov.br, parana.pr.gov.br
# e educacao.pr.gov.br sem precisar listar cada hostname.
WHITELIST_SUFFIXOS = {
    "gov.br",
    "pr.gov.br",
}


WHITELIST = set().union(
    # Serviços oficiais, streaming e bases de mídia
    _d("""
    youtube.com youtu.be google.com google.com.br
    crunchyroll.com crunchyrollsvc.com amazon.com amazon.com.br
    media-amazon.com netflix.com nflxso.net nflxvideo.net
    primevideo.com justwatch.com myanimelist.net anilist.co
    imdb.com themoviedb.org tmdb.org thetvdb.com fanart.tv
    wikipedia.org adorocinema.com plex.tv watch.plex.tv
    bilibili.tv bilibili.com ok.ru kinorium.com infoanime.com.br
    animenewsnetwork.com anisearch.com animeclick.it anime-planet.com
    betaseries.com chiaki.site moviefone.com welcome.hidive.com
    wetv.vip pluto.tv globoplay.globo.com anidb.net tubitv.com
    mangadex.org nyaa.si anitsu.moe uniotaku.com intoxianime.com
    anmtv.com.br beatz-anime.net 1337x.to limeiptv.to
    kurozora.app palomitacas.com darkskiesfilm.com showfound.com
    serieslab.com vkvideo.ru opensubtitles.org clubedodual.com
    comando1.com ext.to
    """),

    # Redes sociais, comunicação, comunidades e jogos
    _d("""
    reddit.com redditmedia.com redditstatic.com redd.it
    twitter.com x.com facebook.com facebook.net fbcdn.net
    instagram.com cdninstagram.com t.co pinterest.com
    tiktok.com tiktokcdn.com tiktokv.com discord.com
    discordapp.com discord.gg discordapp.net web.whatsapp.com
    whatsapp.com whatsapp.net telegram.org telegram.me telegram.dog
    t.me web.telegram.org threads.net threads.com linkedin.com
    linkedinusercontent.com kbin.social bsky.app
    crazygames.com miniplay.com gamaverse.com kick.com
    playstation.net playstation.com dailymotion.com yugioh.com
    my.mail.ru disqus.com disquscdn.com servimg.com imgur.com
    ibb.co gravatar.com snapchat.com tumblr.com tumblr.net
    mastodon.social mastodon.online signal.org signal.group
    matrix.org element.io lemmy.world quora.com medium.com
    meetup.com github.com gitlab.com sourceforge.net
    """),

    # Motores de busca e serviços de navegação
    _d("""
    bing.com yandex.com duckduckgo.com startpage.com brave.com
    search.brave.com sync-v2.brave.com brave-http-only.com
    archive.org goo.gl kagi.com
    """),

    # Infraestrutura SearXNG e domínios auxiliares conhecidos
    _d("""
    about.opnxng.com adminforge.de dresden.network
    support.dresden.network einfachzocken.eu forum.tiekoetter.com
    tiekoetter.com status.tiekoetter.cloud perennialte.ch
    status.perennialte.ch searx.space v1.astar.bz vojk.au
    weingaertner-it.de status.weingaertner-it.eu wuemeli.com
    zina.design cups.moe rockeaters.net operack.com mutix.tr
    mrpaulblack.paulgo.page account.indst.eu chat.indst.eu
    dns.indst.eu legal.indst.eu mail.indst.eu status.indst.eu
    xmr.indst.eu techaro.lol anubis.techaro.lol status.rhscz.eu
    """),

    # Governo federal, Paraná e órgãos públicos
    _d("""
    gov.br pr.gov.br parana.pr.gov.br celepar.pr.gov.br
    detran.pr.gov.br educacao.pr.gov.br saude.pr.gov.br
    agricultura.pr.gov.br fazenda.pr.gov.br turismo.pr.gov.br
    cultura.pr.gov.br seguranca.pr.gov.br trabalho.pr.gov.br
    justica.pr.gov.br infraestrutura.pr.gov.br planejamento.pr.gov.br
    desenvolvimento.pr.gov.br casacivil.pr.gov.br fomento.pr.gov.br
    investparana.org.br assembleia.pr.leg.br tjpr.jus.br
    tre-pr.jus.br trt9.jus.br mppr.mp.br
    defensoriapublica.pr.def.br jus.br mp.br def.br
    """),

    # Desenvolvimento, cloud, IA e produtividade
    _d("""
    github.com githubusercontent.com githubassets.com
    github.githubassets.com vscode-cdn.net visualstudio.com
    vsassets.io marketplace.visualstudio.com
    update.code.visualstudio.com codeload.github.com
    console.cloud.google.com googleapis.com googleusercontent.com
    drive.google.com storage.googleapis.com gemini.google.com
    microsoft.com msn.com live.com outlook.office365.com
    hostinger.com metamask.io client-side-detection.api.cx.metamask.io
    phishing-detection.api.cx.metamask.io accounts.api.cx.metamask.io
    canva.com telemetry.canva.com canva-apps.com innerai.com
    chat-api-v3.innerai.com chat-api-v3-ws.innerai.com
    supabase.co expressvpn.com git.poast.org give.poast.org
    proton.me openai.com postman.com getpostman.com pstmn.io
    controld.com nextdns.io brightdata.com brightdata.com.br
    valueserp.com sillav.dev jsdelivr.net bootstrapcdn.com
    fontawesome.com pluckeye.net launchdarkly.com amplitude.com
    mixpanel.com tawk.to appcues.com fast.appcues.com
    productfruits.com
    """),

    # E-commerce, marketplaces e pagamentos
    _d("""
    aliexpress.com pt.aliexpress.com aliexpress-media.com alicdn.com
    appliancesonline.com.au samsung.com samsung.cn galaxus.ch
    olx.com.br olx.pt mercadolibre.com mercadolivre.com.br
    mercadolivre.com meli.com mlstatic.com shopee.com.br shopee.com
    shein.com shein.com.br temu.com magazineluiza.com.br magalu.com
    americanas.com.br americanas.com submarino.com.br shoptime.com.br
    casasbahia.com.br pontofrio.com.br extra.com.br carrefour.com.br
    atacadao.com.br assai.com.br drogasil.com.br drogaraia.com.br
    raiadrogasil.com.br paguemenos.com.br kabum.com.br
    terabyteshop.com.br pichau.com.br fastshop.com.br
    madeiramadeira.com.br leroymerlin.com.br netshoes.com.br
    centauro.com.br decathlon.com.br enjoei.com.br
    estantevirtual.com.br ecommercebrasil.com.br olist.com
    olist.com.br olistcontadigital.com.br megaerp.online
    ifood.com.br rappi.com.br uber.com hotmart.com eduzz.com
    themembers.com.br pandavideo.com.br shopify.com
    iherb.com images-iherb.com herbarium.com.br
    stripe.com stripe.network stripecdn.com paypal.com
    braintree-api.com adyen.com pagseguro.uol.com.br pagbank.com.br
    iti.br
    """),

    # Empresas, empregos, notícias e serviços diversos
    _d("""
    emprego.sapo.pt jobs.eurofirms.com pt.indeed.com pt.jobsora.com
    pt.linkedin.com randstad.com codigo-postal.pt
    uniaofreguesias.codigo-postal.pt lonza.com dam.lonza.com
    rat.lonza.com unsplash.com typingmaster.co.in tony-liu.com
    allappinc.com award-central.com getbravo.io forbes.com wsj.com
    aarp.org insurancepanda.com progressive.com moneygeek.com
    clark.com hulu.com paramountplus.com microchip.com
    letras.mus.br g1.globo.com filmibeat.com thevore.com
    bancomaster.com.br banricard.com.br caixaprepagos.com.br
    sicoob.com.br mastercard.com pluxee.com.br soumaster.com.br
    produtosmaster.com.br minhaconta.bancomaster.com.br
    minhamaster.soumaster.com.br swile.com.br upbrasil.com
    vr.com.br landflix.com.br
    """),

    # Educação, utilidades e conteúdo geral
    _d("""
    linguee.com.br moodle.org coursera.org creatureartteacher.com
    cybernews.com dicio.com.br last.fm max.com notegpt.io
    online-go.com onlinecourses.nptel.ac.in pinetools.com
    planetinternationalhotel.com similarweb.com tensor.art
    ventusky.com vocalremover.org weather.com w.iiseradmission.in
    sherridress.ca stopots.com victress.pk coconut.sonolus.com
    animationmentor.com stackoverflow.com stackoverflow.co
    wikiwand.com zhidao.baidu.com zhihu.com pbs.org pioneer.org
    firalterbaru.wiki kairou.space sev.monster
    """),

    # Plataformas e auxiliares que apareceram no ControlD
    _d("""
    gstatic.com ytimg.com ggpht.com googlevideo.com gvt2.com
    withgoogle.com googletagmanager.com googleadservices.com
    googlesyndication.com google-analytics.com
    adtrafficquality.google doubleclick.net recaptcha.net
    hcaptcha.com awswaf.com cloudflare.com nr-data.net intercom.io
    intercomcdn.com exp-tas.com boostgroove.com taboola.com
    criteo.com go-mpulse.com clarity.ms hotjar.com typekit.net
    a2z.com amazon.dev amazon-adsystem.com hubspot.com
    hsforms.com hs-scripts.com hs-analytics.net hs-banner.com
    hscollectedforms.net taghike.com stalkoda.com adatacompass.com
    cnt.my connect.facebook.net gateway.facebook.com graph.facebook.com
    business.facebook.com adsmanager.facebook.com
    adsmanager-graph.facebook.com dit.whatsapp.net static.whatsapp.net
    webtp.whatsapp.net flows.whatsapp.net media-poa1-1.cdn.whatsapp.net
    cdninstagram.com
    """),

    # Domínios específicos que não devem ser tratados como plataforma
    _d("""
    caffyntheromele.blogspot.com
    francobuchananinformations.blogspot.com
    1.bp.blogspot.com 2.bp.blogspot.com 3.bp.blogspot.com
    4.bp.blogspot.com i0.wp.com i1.wp.com i2.wp.com
    midjourney.ghost.io
    """),
)

WHITELIST.update(
    _d("""
    # ========================================================
    # Apple e serviços de dispositivos
    # ========================================================
    apple.com
    apps.apple.com
    music.apple.com
    podcasts.apple.com
    applepay.cdn-apple.com

    # ========================================================
    # Mozilla, NVIDIA, npm e desenvolvimento
    # ========================================================
    mozilla.org
    developer.mozilla.org
    nvidia.com
    developer.nvidia.com
    forums.developer.nvidia.com
    npmjs.com
    yarnpkg.com
    classic.yarnpkg.com
    geeksforgeeks.org
    stackexchange.com
    developer.android.com
    docs.python.org

    # ========================================================
    # GitHub e auxiliares observados no ControlD
    # ========================================================
    api.github.com
    collector.github.com
    camo.githubusercontent.com
    raw.githubusercontent.com
    avatars.githubusercontent.com
    objects-origin.githubusercontent.com
    alive.github.com
    codeload.github.com
    github.githubassets.com

    # ========================================================
    # Google e auxiliares de serviços legítimos
    # ========================================================
    clients6.google.com
    google.com.br
    mail.google.com
    accounts.google.com
    play.google.com
    lens.google.com
    history.google.com
    apis.google.com
    clients4.google.com
    fonts.googleapis.com
    fonts.gstatic.com
    ssl.gstatic.com
    addons-pa.clients6.google.com
    signaler-pa.clients6.google.com
    waa-pa.clients6.google.com
    ogs.google.com
    content-autofill.googleapis.com
    clientservices.googleapis.com
    update.googleapis.com
    oauthaccountmanager.googleapis.com
    accountcapabilities-pa.googleapis.com
    chromesyncpreview.pa.googleapis.com
    drivefrontend-pa.clients6.google.com
    jnn-pa.googleapis.com
    peoplestack-pa.clients6.google.com
    peoplestackwebexperiments-pa.clients6.google.com
    taskassist-pa.clients6.google.com
    appsgrowthpromo-pa.clients6.google.com
    appsgenaiserver-pa.clients6.google.com
    encrypted-tbn0.gstatic.com
    lh3.googleusercontent.com
    ci3.googleusercontent.com

    # ========================================================
    # Controle parental, segurança e infraestrutura
    # ========================================================
    api.controld.com
    stats.controld.com
    favicon.controld.com
    p.controld.com
    america.analytics.controld.com
    api.hcaptcha.com
    hcaptcha.com
    newassets.hcaptcha.com
    safebrowsing.google.com
    safebrowsing.brave.com
    c.clarity.ms
    i.clarity.ms
    scripts.clarity.ms
    www.clarity.ms
    script.hotjar.com
    static.hotjar.com
    app.productfruits.com
    fast.appcues.com
    appcues.com
    api-js.mixpanel.com
    nexus-websocket-a.intercom.io
    www.techlockdown.com

    # ========================================================
    # Pagamentos e integrações comerciais
    # ========================================================
    r.stripe.com
    m.stripe.com
    js.stripe.com
    files.stripe.com
    billing.stripe.com
    stripecdn.com
    b.stripecdn.com
    a300.stripecdn.com
    checkout.paypal.com
    payments.braintree-api.com
    r.braintree-api.com
    checkoutshopper-live-us.adyen.com
    envios-api.olist.com
    envios.olist.com
    card-wallet.olistcontadigital.com.br
    cognito-idp.eu-west-1.amazonaws.com
    brightdata.zendesk.com

    # ========================================================
    # Redes sociais e comunicação auxiliares
    # ========================================================
    px.ads.linkedin.com
    alb.reddit.com
    w3-reporting-nel.reddit.com
    connect.facebook.net
    gateway.facebook.com
    graph.facebook.com
    business.facebook.com
    adsmanager.facebook.com
    adsmanager-graph.facebook.com
    video.xx.fbcdn.net
    scontent.xx.fbcdn.net
    static.xx.fbcdn.net
    www.facebook.com
    www.whatsapp.com
    media.fmgf1-1.fna.whatsapp.net
    content-autofill.googleapis.com

    # ========================================================
    # Notícias, música, televisão e conteúdo geral
    # ========================================================
    uol.com.br
    letras.mus.br
    vagalume.com.br
    genius.com
    g1.globo.com
    filmibeat.com
    radiotimes.com
    tvguide.com
    thevore.com
    weforum.org
    theinfatuation.com
    pbs.org
    jambase.com

    # ========================================================
    # Dicionários, idiomas e educação
    # ========================================================
    dicionario.priberam.org
    dictionary.cambridge.org
    merriam-webster.com
    grammarphobia.com
    free-learn.ir
    coddy.tech
    bueltge.de

    # ========================================================
    # Universidades e instituições educacionais
    # ========================================================
    eur.nl
    ru.nl
    uu.nl
    uva.nl
    tilburguniversity.edu
    han.nl
    hu.nl
    masters.nus.edu.sg
    study.nus.edu.sg
    ntu.edu.sg
    masters.smu.edu.sg
    mdis.edu.sg
    sim.edu.sg
    mom.gov.sg
    caas.gov.sg
    e-justice.europa.eu

    # ========================================================
    # Aeroportos, datas e serviços de viagem
    # ========================================================
    airportinformation.com
    changiairport.com
    nowboarding.changiairport.com
    holidaydates.sg
    publicholidays.sg
    singaporeholiday.com.sg
    rentumo.com
    maracanaonline.com.br

    # ========================================================
    # Empresas, empregos e ferramentas profissionais
    # ========================================================
    app.bullhornstaffing.com
    capitaliq.com
    leadiq.com
    theorg.com
    benchmarque.co
    perkinelmer.com
    idw.de
    airportinformation.com
    lambda.ai
    aiagentskit.com
    aicybr.com
    bestgpusforai.com
    lexica.art
    mlsysbook.ai
    seektool.ai
    toolify.ai
    toolmage.com
    overflow.io
    """),
)

WHITELIST.update(
    _d("""
    airlineinformation.com
    dictionary.cambridge.org
    drom.ru
    chordu.com
    genius.com
    grammarphobia.com
    holidaydates.sg
    hongkongairport.com
    jambase.com
    maracanaonline.com.br
    mewatch.sg
    music.apple.com
    podcasts.apple.com
    publicholidays.sg
    tvguide.com
    uol.com.br
    vagalume.com.br
    weforum.org
    """),
)

WHITELIST.update(
    _d("""
    # Apple
    apple.com
    apps.apple.com
    music.apple.com
    podcasts.apple.com

    # Desenvolvimento e tecnologia
    mozilla.org
    developer.mozilla.org
    nvidia.com
    developer.nvidia.com
    forums.developer.nvidia.com
    npmjs.com
    yarnpkg.com
    classic.yarnpkg.com
    geeksforgeeks.org
    stackexchange.com
    stackoverflow.blog
    handbook.modular.com
    xda-developers.com

    # IA e produtividade
    character.ai
    character.chat
    chatgpt.com
    copilot.cloud.microsoft
    aiagentskit.com
    lambda.ai
    lexica.art
    seaart.ai
    rubii.ai
    polybuzz.ai
    bestgpusforai.com
    mlsysbook.ai
    seektool.ai
    toolify.ai
    toolmage.com

    # Google, Microsoft e serviços gerais
    chatgpt.com
    cdc.gov
    paho.org
    speedtest.net
    install.speedtest.net
    app.speedtest.net
    intelligence.speedtest.net
    ciscoconnect.speedtest.net
    linksys.speedtest.net
    th.speedtest.net
    tw.speedtest.net

    # Dicionários, música e conteúdo geral
    dicionario.priberam.org
    dictionary.cambridge.org
    merriam-webster.com
    genius.com
    uol.com.br
    vagalume.com.br
    tvguide.com
    twitch.tv
    steamcommunity.com

    # Educação e instituições
    hhs.se
    kth.se
    su.se
    master.se
    master.nu
    eur.nl
    ru.nl
    uu.nl
    uva.nl
    tilburguniversity.edu
    han.nl
    hu.nl
    paho.org

    # Empresas e serviços profissionais
    app.bullhornstaffing.com
    capitaliq.com
    leadiq.com
    theorg.com
    zoominfo.com
    bueltge.de
    datev.de
    eventbrite.com.mx
    profiletree.com
    buzzsprout.com
    photography-on-the.net
    chordu.com
    timeanddate.com
    """),
)

WHITELIST.update(
    _d("""
    # Universidades e órgãos (Suíça, Suécia, Alemanha, Tchéquia)
    ethz.ch fhnw.ch zhaw.ch unisg.ch sbfi.admin.ch
    studentum.se antagning.se studyflix.de studiekeuze123.nl
    bundesrat.de buzer.de rechtslupe.de rentenbote.de
    reportinfo.cz casopis.fit.cvut.cz panoramawissen.de
    spotgroningen.nl iteslj.org

    # WordPress, tecnologia e utilidades
    wordpress.tv wpastra.com wpbeginner.com wpmeetups.de wptavern.com
    gizmodo.com scribd.com slideshare.net yelp.com cnblogs.com
    contactout.com wiza.co directory.fsf.org ourbigbook.com
    blog.darkthread.net bbs.huaweicloud.com news.mynavi.jp
    helpforum.sky.com cafebazaar.ir

    # Notícias, empresas e TV
    singtel.com tvinsider.com irelandvoice.com rtp.pt
    streetdirectory.com iliffemedia.co.uk thedetroitbureau.com

    # Variantes de domínios já liberados
    yandex.ru google.com.sg translate.google.com.sg
    anisearch.de jingyan.baidu.com bca.gov.sg
    """),
)

WHITELIST.update(
    _d("""
    masterpiecehairsalon.nl aerospareparts.com bel-airexpress.com
    elegancecleanerslb.com fipart.com foto-zumstein.ch
    trade-in.foto-zumstein.ch mybestbrands.de locatory.com
    intelbase.is capit.net bioferacanzo.org astrologyanswers.com
    myadultcircumcision.org brandshop.ru m.brandshop.ru
    elbike.ir koochand.ir salvex.com seattleav.com recordowl.com
    kaskus.co.id
    """),
)

WHITELIST.update(
    _d("""
    rolex.com omegawatches.com swatch.com chanel.com
    chrono24.com chrono24.ch m-watch.com watch.de
    watchexchange.sg watchdistrict.store citychain.com.sg
    digitec.ch interdiscount.ch allegro.cz
    yahoo.com meta.com threadreaderapp.com time.is savvytime.com
    gifdb.com cartoonbrew.com filmow.com filmin.pt filmelier.com
    absatzwirtschaft.de
    """),
)

# Sufixos oficiais. A função de whitelist precisa tratá-los
# separadamente para cobrir todos os subdomínios.
WHITELIST_SUFFIXOS = {
    "gov.br",
    "pr.gov.br",
    "sillav.dev"
}


# ============================================================
# NORMALIZAÇÃO DE DOMÍNIOS
# ============================================================

TLDS_COMPOSTOS = {
    "com.br",
    "co.uk",
    "com.au",
    "co.jp",
    "co.in",
    "com.mx",
    "net.br",
    "org.br",
    "gov.br",
    "co.nz",
    "com.ar",
}


def limpar_dominio(valor):
    if not valor:
        return None

    try:
        valor = str(valor).strip()

        if not re.match(
            r"^[a-z][a-z0-9+.-]*://",
            valor,
            re.IGNORECASE,
        ):
            valor = "https://" + valor

        hostname = urlparse(valor).hostname

        if not hostname:
            return None

        hostname = hostname.lower().rstrip(".").strip()
        hostname = re.sub(r"^www\d*\.", "", hostname)

        if any(
            caractere.isspace() or caractere in "/?#"
            for caractere in hostname
        ):
            return None

        return hostname

    except Exception:
        return None


def extrair_dominio_base(dominio):
    if not dominio:
        return None

    dominio = dominio.lower().strip(".")
    dominio = re.sub(r"^www\d*\.", "", dominio)

    try:
        import tldextract

        partes = tldextract.extract(dominio)

        if partes.domain and partes.suffix:
            return f"{partes.domain}.{partes.suffix}"

    except ImportError:
        pass
    except Exception:
        pass

    partes = dominio.split(".")

    if len(partes) < 2:
        return dominio

    ultimos_dois = ".".join(partes[-2:])

    if ultimos_dois in TLDS_COMPOSTOS and len(partes) >= 3:
        return ".".join(partes[-3:])

    return ultimos_dois


def dominio_esta_sempre_bloqueado(dominio):
    if not dominio:
        return False

    dominio = limpar_dominio(dominio) or dominio.lower()
    base = extrair_dominio_base(dominio)

    return (
        dominio in SEMPRE_BLOQUEAR
        or base in SEMPRE_BLOQUEAR
    )


def dominio_esta_na_whitelist(dominio):
    if not dominio:
        return False

    dominio = limpar_dominio(dominio) or dominio.lower()
    base = extrair_dominio_base(dominio)

    # SEMPRE_BLOQUEAR tem prioridade sobre qualquer whitelist.
    if dominio_esta_sempre_bloqueado(dominio):
        return False

    if dominio in WHITELIST or base in WHITELIST:
        return True

    # Cobre, por exemplo:
    # caixa.gov.br
    # atendimento.educacao.sp.gov.br
    # parana.pr.gov.br
    # educacao.pr.gov.br
    for sufixo in WHITELIST_SUFFIXOS:
        if dominio == sufixo:
            return True

        if dominio.endswith("." + sufixo):
            return True

    return False

def normalizar_dominios(dominios):
    resultado = set()

    for item in dominios:
        dominio = limpar_dominio(item)

        if dominio and "." in dominio:
            resultado.add(dominio)

    return resultado


# ============================================================
# LOG E ARQUIVOS
# ============================================================

def log(mensagem, nivel="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{timestamp}] {mensagem}"

    print(linha)

    if GERAR_LOG_ARQUIVO:
        try:
            with open(
                ARQUIVO_LOG,
                "a",
                encoding="utf-8",
            ) as arquivo:
                arquivo.write(f"[{nivel}] {linha}\n")

        except Exception:
            pass


def carregar_blocklist_atual():
    if not os.path.exists(ARQUIVO_BLOCKLIST):
        open(
            ARQUIVO_BLOCKLIST,
            "w",
            encoding="utf-8",
        ).close()

        return set()

    with open(
        ARQUIVO_BLOCKLIST,
        "r",
        encoding="utf-8",
    ) as arquivo:
        return {
            linha.strip().lower()
            for linha in arquivo
            if linha.strip()
            and not linha.strip().startswith("#")
        }


def salvar_blocklist(dominios):
    with open(
        ARQUIVO_BLOCKLIST,
        "w",
        encoding="utf-8",
    ) as arquivo:
        for dominio in sorted(dominios):
            arquivo.write(f"{dominio}\n")


def exportar_formato_adguard(
    dominios,
    caminho=ARQUIVO_BLOCKLIST_ADGUARD,
):
    with open(
        caminho,
        "w",
        encoding="utf-8",
    ) as arquivo:
        for dominio in sorted(dominios):
            arquivo.write(f"||{dominio}^\n")


def remover_organicos_antigos_da_blocklist(blocklist):
    resultado = set()
    removidos = set()

    for item in blocklist:
        dominio = limpar_dominio(item)

        if not dominio:
            continue

        if dominio_esta_sempre_bloqueado(dominio):
            resultado.add(dominio)

        elif dominio_esta_na_whitelist(dominio):
            removidos.add(dominio)

        else:
            resultado.add(dominio)

    if removidos:
        log(
            f"-> {len(removidos)} entradas orgânicas removidas "
            "da blocklist pela whitelist."
        )

    return resultado


# ============================================================
# ROTAÇÃO DOS TÍTULOS
# ============================================================

def carregar_estado_rotacao():
    if not os.path.exists(ARQUIVO_ESTADO):
        return {"indice": 0}

    try:
        with open(
            ARQUIVO_ESTADO,
            "r",
            encoding="utf-8",
        ) as arquivo:
            return json.load(arquivo)

    except Exception:
        return {"indice": 0}


def salvar_estado_rotacao(estado):
    with open(
        ARQUIVO_ESTADO,
        "w",
        encoding="utf-8",
    ) as arquivo:
        json.dump(estado, arquivo)


def obter_lote_da_vez():
    estado = carregar_estado_rotacao()
    indice = int(estado.get("indice", 0))

    total = len(ANIMES_ISCA)
    lote = []

    for deslocamento in range(QTD_POR_EXECUCAO):
        posicao = (indice + deslocamento) % total
        lote.append(ANIMES_ISCA[posicao])

    novo_indice = (
        indice + QTD_POR_EXECUCAO
    ) % total

    salvar_estado_rotacao({"indice": novo_indice})

    return lote


def gerar_queries_busca(titulo):
    return [
        f"Assistir anime {titulo} online legendado",
        f"Watch anime {titulo} online",
    ]


# ============================================================
# CACHE E CATÁLOGO SEARXNG
# ============================================================

def carregar_cache_instancias():
    if not os.path.exists(ARQUIVO_CACHE_INSTANCIAS):
        return None

    try:
        with open(
            ARQUIVO_CACHE_INSTANCIAS,
            "r",
            encoding="utf-8",
        ) as arquivo:
            cache = json.load(arquivo)

        timestamp = datetime.fromisoformat(
            cache["timestamp"]
        )

        idade_horas = (
            datetime.now() - timestamp
        ).total_seconds() / 3600

        if idade_horas < CACHE_INSTANCIAS_VALIDADE_HORAS:
            instancias = cache.get("instancias", [])

            if isinstance(instancias, list):
                return sorted({
                    item.rstrip("/")
                    for item in instancias
                    if isinstance(item, str)
                    and item.startswith("https://")
                })

    except Exception:
        pass

    return None


def salvar_cache_instancias(instancias):
    try:
        instancias = sorted({
            item.rstrip("/")
            for item in instancias
            if isinstance(item, str)
            and item.startswith("https://")
        })

        with open(
            ARQUIVO_CACHE_INSTANCIAS,
            "w",
            encoding="utf-8",
        ) as arquivo:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "instancias": instancias,
                },
                arquivo,
            )

    except Exception as erro:
        log(
            f"Falha ao salvar cache SearXNG: "
            f"{type(erro).__name__}",
            "DEBUG",
        )


def buscar_lista_bruta_instancias():
    try:
        resposta = requests.get(
            URL_LISTA_INSTANCIAS,
            headers=HEADERS_PADRAO,
            timeout=TIMEOUT_LISTA_INSTANCIAS,
            verify=True,
        )

        if resposta.status_code != 200:
            log(
                "Catálogo de instâncias retornou "
                f"HTTP {resposta.status_code}.",
                "ERROR",
            )
            return []

        import yaml

        dados = yaml.safe_load(resposta.text) or {}
        urls = set()

        if isinstance(dados, dict):
            for chave in dados.keys():
                if (
                    isinstance(chave, str)
                    and chave.startswith("https://")
                ):
                    urls.add(chave.rstrip("/"))

        return sorted(urls)

    except Exception as erro:
        log(
            f"Falha ao obter catálogo SearXNG: "
            f"{type(erro).__name__}: {erro}",
            "ERROR",
        )
        return []


def descobrir_instancias_disponiveis():
    """
    Retorna todas as instâncias HTTPS do catálogo.

    Não testa se a instância fornece resultados antes de incluí-la.
    Isso é essencial: uma instância que responde 403 ou 429 está
    online, embora não esteja disponível para esta requisição.
    """
    cache = carregar_cache_instancias()

    if cache:
        log(
            f"-> Usando catálogo em cache: "
            f"{len(cache)} instâncias."
        )
        return cache

    log("-> Baixando catálogo completo de instâncias SearXNG...")

    lista = buscar_lista_bruta_instancias()

    if not lista:
        log(
            "-> Catálogo indisponível; usando fallback.",
            "ERROR",
        )

        salvar_cache_instancias(INSTANCIAS_FALLBACK)
        return INSTANCIAS_FALLBACK

    log(
        f"-> {len(lista)} instâncias HTTPS encontradas "
        "no catálogo."
    )

    salvar_cache_instancias(lista)

    return lista


# ============================================================
# EXTRAÇÃO DE RESULTADOS SEARXNG
# ============================================================

CAMINHOS_RUIDO = (
    "image_proxy",
    "/preferences",
    "/search?",
    "/stats",
    "/about",
    "/info/",
)


def link_pertence_a_instancia(href, url_instancia):
    dominio_link = limpar_dominio(href)
    dominio_instancia = limpar_dominio(url_instancia)

    if not dominio_link or not dominio_instancia:
        return False

    return (
        dominio_link == dominio_instancia
        or dominio_link.endswith("." + dominio_instancia)
    )


def extrair_links_json_searxng(
    dados,
    url_instancia,
):
    links = []

    if not isinstance(dados, dict):
        return links

    resultados = dados.get("results", [])

    if not isinstance(resultados, list):
        return links

    for resultado in resultados:
        if not isinstance(resultado, dict):
            continue

        href = resultado.get("url")

        if not isinstance(href, str):
            continue

        if not href.startswith(("http://", "https://")):
            continue

        if link_pertence_a_instancia(
            href,
            url_instancia,
        ):
            continue

        links.append(href)

    return sorted(set(links))


def extrair_links_html_searxng(
    html,
    url_instancia,
):
    soup = BeautifulSoup(html, "html.parser")

    seletores = [
        "article.result a.url_header",
        "article.result h3 a",
        "div.result h3 a",
        "div.result a.url_header",
        ".result a[href]",
    ]

    tags = []

    for seletor in seletores:
        encontrados = soup.select(seletor)

        if encontrados:
            tags.extend(encontrados)

    # Fallback para temas diferentes.
    if not tags:
        return []

    links = []

    for tag in tags:
        href = tag.get("href")

        if not href:
            continue

        if not href.startswith(("http://", "https://")):
            continue

        if link_pertence_a_instancia(
            href,
            url_instancia,
        ):
            continue

        host = limpar_dominio(href) or ""

        # Evita links do próprio projeto no rodapé.
        if "searx" in host:
            continue

        href_lower = href.lower()

        if any(
            caminho in href_lower
            for caminho in CAMINHOS_RUIDO
        ):
            continue

        links.append(href)

    return sorted(set(links))


def consultar_instancia_searxng(
    url_instancia,
    query,
):
    """
    Faz uma consulta por instância.

    Primeiro tenta JSON, que contém resultados estruturados.
    Se a instância não aceitar JSON ou devolver HTML, tenta HTML.
    """
    params_base = {
        "q": query,
        "safesearch": 0,
        "categories": "general",
        "language": "all",
        "pageno": 1,
    }

    tentativas = [
        (
            "json",
            {
                **params_base,
                "format": "json",
            },
        ),
        (
            "html",
            params_base,
        ),
    ]

    ultimo_status = "vazio"

    for formato, params in tentativas:
        try:
            resposta = requests.get(
                f"{url_instancia}/search",
                params=params,
                headers=HEADERS_PADRAO,
                timeout=TIMEOUT_CONSULTA_INSTANCIA,
                impersonate="chrome120",
                verify=True,
            )

        except requests.exceptions.Timeout:
            return [], "Timeout"

        except Exception as erro:
            return [], type(erro).__name__

        status_http = resposta.status_code

        if status_http == 429:
            return [], "429"

        if status_http == 403:
            ultimo_status = "403"
            continue

        if status_http != 200:
            ultimo_status = str(status_http)
            continue

        if formato == "json":
            try:
                dados = resposta.json()

                links = extrair_links_json_searxng(
                    dados,
                    url_instancia,
                )

                if links:
                    return links, "ok"

                ultimo_status = "vazio"

            except Exception:
                # A instância pode ter respondido HTML apesar
                # do parâmetro format=json.
                pass

        links = extrair_links_html_searxng(
            resposta.text,
            url_instancia,
        )

        if links:
            return links, "ok"

        ultimo_status = "vazio"

    return [], ultimo_status


def consultar_searxng(
    query,
    sessao,
    instancias_disponiveis,
):
    """
    Consulta todas as instâncias recebidas.

    Não existe limite de 8, 10 ou 30 nesta função.
    Cada URL da lista gera uma tarefa própria.
    """
    candidatas = sorted({
        url.rstrip("/")
        for url in instancias_disponiveis
        if isinstance(url, str)
        and url.startswith("https://")
    })

    random.shuffle(candidatas)

    log(
        f"    [i] Consultando todas as "
        f"{len(candidatas)} instâncias SearXNG."
    )

    def tarefa(url):
        # Escalonamento curto para reduzir rajadas simultâneas,
        # sem eliminar nenhuma instância.
        time.sleep(random.uniform(0, 2.5))

        links, status = consultar_instancia_searxng(
            url,
            query,
        )

        return url, links, status

    links_agregados = set()
    resumo = {}
    instancias_ok = 0

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=WORKERS_SEARXNG
    ) as executor:
        futuros = [
            executor.submit(tarefa, url)
            for url in candidatas
        ]

        for futuro in concurrent.futures.as_completed(
            futuros
        ):
            try:
                url, links, status = futuro.result()

            except Exception as erro:
                url = "desconhecida"
                links = []
                status = type(erro).__name__

            resumo[status] = resumo.get(status, 0) + 1

            if links:
                links_agregados.update(links)
                instancias_ok += 1

                log(
                    f"    [+] SearXNG {url}: "
                    f"{len(links)} links"
                )

    instancias_falha = len(candidatas) - instancias_ok

    log(
        f"    [i] SearXNG: {len(candidatas)} instâncias "
        f"consultadas, status: {resumo}"
    )

    return (
        sorted(links_agregados),
        instancias_ok,
        instancias_falha,
    )


# ============================================================
# OUTROS MOTORES
# ============================================================

def consultar_duckduckgo(
    query,
    ddgs_client,
):
    try:
        resultados = list(
            ddgs_client.text(
                query,
                safesearch="off",
                max_results=RESULTADOS_DDG,
            )
        )

        return [
            resultado.get("href", "")
            for resultado in resultados
            if resultado.get("href")
        ]

    except Exception as erro:
        log(
            f"    [-] Erro DuckDuckGo: "
            f"{type(erro).__name__}",
            "ERROR",
        )
        return []


def resolver_redirecionamento_bing(href):
    if not href:
        return href

    if "bing.com/ck/a" not in href.lower():
        return href

    try:
        consulta = parse_qs(
            urlparse(href).query
        )

        valor = consulta.get("u", [""])[0]
        valor = unquote(valor)

        if not valor:
            return href

        if valor.startswith("a1"):
            valor = valor[2:]
            valor += "=" * (-len(valor) % 4)

            decodificado = base64.urlsafe_b64decode(
                valor
            ).decode(
                "utf-8",
                errors="ignore",
            )

            if decodificado.startswith(
                ("http://", "https://")
            ):
                return decodificado

    except Exception:
        pass

    return href


def consultar_bing(
    query,
    sessao,
):
    links = []

    for pagina in range(PAGINAS_BING):
        try:
            resposta = sessao.get(
                "https://www.bing.com/search",
                params={
                    "q": query,
                    "first": (pagina * 10) + 1,
                },
                headers=HEADERS_PADRAO,
                timeout=10,
                verify=True,
            )

            if resposta.status_code != 200:
                break

            soup = BeautifulSoup(
                resposta.text,
                "html.parser",
            )

            encontrados = []

            for tag in soup.select(
                "li.b_algo h2 a"
            ):
                href = tag.get("href")

                if not href:
                    continue

                href = resolver_redirecionamento_bing(
                    href
                )

                if href.startswith(
                    ("http://", "https://")
                ):
                    encontrados.append(href)

            if not encontrados:
                break

            links.extend(encontrados)

        except Exception as erro:
            log(
                f"    [-] Erro Bing: "
                f"{type(erro).__name__}",
                "ERROR",
            )
            break

        time.sleep(random.uniform(1.0, 2.0))

    return sorted(set(links))


def consultar_startpage(
    query,
    sessao,
):
    links = []

    seletores = [
        "a.result-link",
        "a.w-gl__result-url",
        "a.w-gl__result-title",
        "div.result a[href]",
    ]

    for pagina in range(PAGINAS_STARTPAGE):
        try:
            resposta = sessao.get(
                "https://www.startpage.com/sp/search",
                params={
                    "query": query,
                    "cat": "web",
                    "page": pagina + 1,
                },
                headers=HEADERS_PADRAO,
                timeout=10,
                verify=False,
            )

            if resposta.status_code != 200:
                break

            soup = BeautifulSoup(
                resposta.text,
                "html.parser",
            )

            encontrados = []

            for seletor in seletores:
                for tag in soup.select(seletor):
                    href = tag.get("href")

                    if not href:
                        continue

                    if not href.startswith(
                        ("http://", "https://")
                    ):
                        continue

                    if "startpage.com" in href:
                        continue

                    encontrados.append(href)

                if encontrados:
                    break

            if not encontrados:
                break

            links.extend(encontrados)

        except Exception as erro:
            log(
                f"    [-] Erro Startpage: "
                f"{type(erro).__name__}",
                "ERROR",
            )
            break

        time.sleep(random.uniform(1.0, 2.0))

    return sorted(set(links))


def consultar_brave(
    query,
    sessao,
):
    links = []

    if not BRAVE_API_KEY:
        return links

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY,
    }

    for pagina in range(PAGINAS_BRAVE):
        try:
            resposta = sessao.get(
                "https://api.search.brave.com/"
                "res/v1/web/search",
                params={
                    "q": query,
                    "safesearch": "off",
                    "count": RESULTADOS_BRAVE,
                    "offset": pagina * RESULTADOS_BRAVE,
                },
                headers=headers,
                timeout=10,
                verify=True,
            )

            if resposta.status_code != 200:
                break

            dados = resposta.json()

            encontrados = [
                resultado.get("url")
                for resultado in dados.get(
                    "web",
                    {},
                ).get(
                    "results",
                    [],
                )
                if resultado.get("url")
            ]

            if not encontrados:
                break

            links.extend(encontrados)

        except Exception as erro:
            log(
                f"    [-] Erro Brave: "
                f"{type(erro).__name__}",
                "ERROR",
            )
            break

        time.sleep(random.uniform(1.0, 2.0))

    return sorted(set(links))


# ============================================================
# COLETA E CLASSIFICAÇÃO
# ============================================================

def coletar_links_para_query(
    query,
    sessao_http,
    instancias_searxng,
    ddgs_client,
    stats,
):
    links_brutos = set()

    links_searx, ok, falhas = consultar_searxng(
        query,
        sessao_http,
        instancias_searxng,
    )

    if links_searx:
        links_brutos.update(links_searx)

        log(
            f"    [=] SearXNG agregado: "
            f"{len(links_searx)} links "
            f"({ok} OK, {falhas} falhas)"
        )

    else:
        stats["erros"]["searxng"] += 1

    time.sleep(random.uniform(1.0, 2.0))

    links_ddg = consultar_duckduckgo(
        query,
        ddgs_client,
    )

    if links_ddg:
        links_brutos.update(links_ddg)
        log(
            f"    [+] DuckDuckGo: "
            f"{len(links_ddg)} links"
        )

    else:
        stats["erros"]["ddg"] += 1

    time.sleep(random.uniform(1.0, 2.0))

    links_bing = consultar_bing(
        query,
        sessao_http,
    )

    if links_bing:
        links_brutos.update(links_bing)
        log(
            f"    [+] Bing: "
            f"{len(links_bing)} links"
        )

    else:
        stats["erros"]["bing"] += 1

    time.sleep(random.uniform(1.0, 2.0))

    links_startpage = []

    if PAGINAS_STARTPAGE > 0:
        links_startpage = consultar_startpage(
            query,
            sessao_http,
        )

    if links_startpage:
        links_brutos.update(links_startpage)
        log(
            f"    [+] Startpage: "
            f"{len(links_startpage)} links"
        )

    else:
        stats["erros"]["startpage"] += 1

    time.sleep(random.uniform(1.0, 2.0))

    links_brave = consultar_brave(
        query,
        sessao_http,
    )

    if links_brave:
        links_brutos.update(links_brave)
        log(
            f"    [+] Brave: "
            f"{len(links_brave)} links"
        )

    elif BRAVE_API_KEY:
        stats["erros"]["brave"] += 1

    return links_brutos


def extrair_dominios_piratas(
    lote_animes,
    instancias_searxng,
):
    ocorrencias_dominios = Counter()

    stats = {
        "queries": 0,
        "links_brutos": 0,
        "erros": {
            "searxng": 0,
            "ddg": 0,
            "bing": 0,
            "startpage": 0,
            "brave": 0,
        },
    }

    sessao_http = requests.Session(
        impersonate="chrome120"
    )

    with DDGS() as ddgs_client:
        for anime in lote_animes:
            queries = gerar_queries_busca(anime)

            for query in queries:
                stats["queries"] += 1

                log(
                    f"\n-> Pesquisando: [{query}]"
                )

                links_brutos = coletar_links_para_query(
                    query,
                    sessao_http,
                    instancias_searxng,
                    ddgs_client,
                    stats,
                )

                stats["links_brutos"] += len(links_brutos)

                for url in links_brutos:
                    dominio = limpar_dominio(url)

                    if not dominio or "." not in dominio:
                        continue

                    if dominio_esta_na_whitelist(dominio):
                        continue

                    ocorrencias_dominios[dominio] += 1

                time.sleep(random.uniform(3.0, 5.0))

    novos_dominios = {
        dominio
        for dominio, ocorrencias in ocorrencias_dominios.items()
        if ocorrencias >= 2
    }

    candidatos_pendentes = {
        dominio
        for dominio, ocorrencias in ocorrencias_dominios.items()
        if ocorrencias == 1
    }

    with open("candidatos_pendentes.txt", "w", encoding="utf-8") as arquivo:
        for dominio in sorted(candidatos_pendentes):
            arquivo.write(f"{dominio}\n")

    log(
        f"-> {len(novos_dominios)} domínios confirmados "
        f"por múltiplas ocorrências."
    )

    log(
        f"-> {len(candidatos_pendentes)} candidatos únicos "
        f"salvos em candidatos_pendentes.txt."
    )

    return novos_dominios, stats


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():
    if GERAR_LOG_ARQUIVO and os.path.exists(
        ARQUIVO_LOG
    ):
        open(
            ARQUIVO_LOG,
            "w",
            encoding="utf-8",
        ).close()

    log("Iniciando crawler.")

    if not BRAVE_API_KEY:
        log(
            "-> BRAVE_API_KEY não configurada. "
            "A fonte Brave será ignorada."
        )

    instancias_searxng = (
        descobrir_instancias_disponiveis()
    )

    blocklist_original = (
        carregar_blocklist_atual()
    )

    blocklist = normalizar_dominios(
        blocklist_original
    )

    blocklist = (
        remover_organicos_antigos_da_blocklist(
            blocklist
        )
    )

    tamanho_inicial = len(blocklist)

    log(
        f"-> Blocklist atual após normalização: "
        f"{tamanho_inicial} domínios."
    )

    lote = obter_lote_da_vez()

    log(
        f"-> Lote desta execução ({len(lote)} títulos): "
        f"{', '.join(lote)}"
    )

    novos_dominios, stats = (
        extrair_dominios_piratas(
            lote,
            instancias_searxng,
        )
    )

    novos_dominios = {
        dominio
        for dominio in novos_dominios
        if not dominio_esta_na_whitelist(dominio)
    }

    blocklist.update(novos_dominios)

    # Reinsere as exceções caso alguma limpeza anterior
    # tenha removido uma delas.
    blocklist.update(SEMPRE_BLOQUEAR)

    tamanho_final = len(blocklist)
    qtd_novos = (
        tamanho_final - tamanho_inicial
    )

    log("\n===================================")
    log(
        f"Queries executadas: "
        f"{stats['queries']}"
    )
    log(
        f"Links brutos coletados: "
        f"{stats['links_brutos']}"
    )
    log(
        f"Falhas por fonte: "
        f"{stats['erros']}"
    )

    if qtd_novos > 0:
        log(
            f"SUCESSO: {qtd_novos} novos domínios "
            "encontrados."
        )
    else:
        log(
            "Nenhum domínio novo encontrado."
        )

    salvar_blocklist(blocklist)
    exportar_formato_adguard(blocklist)

    log(
        f"-> Blocklist salva em "
        f"{ARQUIVO_BLOCKLIST}."
    )
    log(
        f"-> Formato AdGuard salvo em "
        f"{ARQUIVO_BLOCKLIST_ADGUARD}."
    )


if __name__ == "__main__":
    main()