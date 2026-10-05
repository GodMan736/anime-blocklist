# 🕷️ Anime Blocklist Crawler

Um script automatizado em Python projetado para rastrear, extrair e catalogar domínios não autorizados de streaming de animes na internet. O objetivo principal deste projeto é gerar e manter uma **blocklist (lista de bloqueios)** atualizada que pode ser importada para firewalls, servidores DNS (como Pi-hole, AdGuard Home, ControlD) e políticas de restrição de rede.

## 🚀 Como Funciona?

O script utiliza uma lista de títulos de animes como "iscas" para realizar buscas dinâmicas simulando o comportamento de um usuário real procurando por episódios online. Ele varre os resultados, filtra domínios legítimos (como Crunchyroll, Netflix, Amazon, etc.) através de uma whitelist nativa, e extrai apenas os domínios de distribuição pirata.

## ✨ Principais Funcionalidades e Destaques Técnicos

- **Bypass Avançado de TLS/SSL:** Utiliza a biblioteca `curl_cffi` para emular o *TLS handshake* do Google Chrome (impersonate), permitindo contornar firewalls de segurança agressivos como Cloudflare e DDoS-Guard que normalmente bloqueiam web scrapers convencionais.
- **Rotação de Motores de Busca:** Realiza consultas simultâneas no DuckDuckGo, Bing, Startpage, Brave Search e no ecossistema descentralizado do SearXNG.
- **Rastreamento de Instâncias SearXNG:** O bot busca automaticamente instâncias públicas saudáveis do SearXNG, testa a conectividade de cada uma e divide a carga das requisições entre elas para evitar rate limits.
- **Fallback Parser Agressivo:** Ao consultar o SearXNG, tenta primeiro consumir a API JSON nativa. Se a instância bloquear a resposta estruturada, o script aciona automaticamente um parseamento em HTML via `BeautifulSoup`, varrendo a página em busca de qualquer link externo válido.
- **Base de Dados Cumulativa:** Os domínios recém-descobertos são purificados e mesclados ao arquivo `blocklist.txt` sem sobrescrever o histórico passado, garantindo uma lista que cresce organicamente ao longo do tempo.

## 🛠️ Tecnologias Utilizadas

- **Python 3**
- `curl_cffi` (Para requisições HTTP furtivas)
- `BeautifulSoup4` (Para extração e parseamento de HTML)
- `duckduckgo_search` (Integração com DDG)

## 📂 Estrutura de Arquivos

- `crawler.py`: O núcleo principal da aplicação contendo as regras de busca e bypass.
- `blocklist.txt`: O arquivo de texto final contendo todos os domínios já catalogados e banidos, pronto para ser importado em sistemas de bloqueio.
- `estado_rotacao.json`: Arquivo de controle local que gerencia quais títulos isca foram usados na última execução.
- `cache_instancias_searxng.json`: Armazena temporariamente as URLs das instâncias ativas do SearXNG para acelerar execuções futuras.

## ⚙️ Como usar a Blocklist

O arquivo `blocklist.txt` gerado por este repositório contém apenas domínios limpos (um por linha). Você pode copiar o link "Raw" deste arquivo no GitHub e inseri-lo diretamente nas configurações de listas de bloqueio customizadas do seu roteador, Pi-hole, OpenSnitch ou provedor DNS seguro.
