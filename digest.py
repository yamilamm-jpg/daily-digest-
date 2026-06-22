import feedparser
import requests
from datetime import datetime, timezone, timedelta
import os
import time

TELEGRAM_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

HOURS_BACK = 20
MAX_PER_SECTION = 4

FEEDS = {
    '🌍 MACROECONOMÍA': [
        ('Reuters',      'https://feeds.reuters.com/reuters/businessNews'),
        ('BBC Business', 'https://feeds.bbci.co.uk/news/business/rss.xml'),
        ('FT',           'https://www.ft.com/rss/home/uk'),
    ],
    '📈 MERCADOS': [
        ('Expansión',    'https://www.expansion.com/rss/mercados.xml'),
        ('El Economista','https://www.eleconomista.es/rss/rss-mercados.php'),
        ('MarketWatch',  'https://feeds.marketwatch.com/marketwatch/topstories/'),
        ('CNBC',         'https://www.cnbc.com/id/10000664/device/rss/rss.html'),
    ],
    '₿ CRIPTO': [
        ('CoinDesk',     'https://www.coindesk.com/arc/outboundfeeds/rss/'),
        ('CoinTelegraph','https://cointelegraph.com/rss'),
        ('The Block',    'https://www.theblock.co/rss.xml'),
        ('Decrypt',      'https://decrypt.co/feed'),
    ],
    '🏛 POLÍTICA / EEUU': [
        ('White House',  'https://www.whitehouse.gov/news/feed/'),
    ],
}

# Public Nitter instances (tried in order, first working one is used)
NITTER_INSTANCES = [
    'nitter.privacydev.net',
    'nitter.poast.org',
    'nitter.1d4.us',
    'nitter.fdn.fr',
]

X_ACCOUNTS = [
    'FromValue', '100trillionUSD', 'ContraInvest', 'PabloGilTrader',
    'LuisMiguelValue', 'foso_defensivo', 'crossbordercap', 'Carlos_Pareja27',
    'PunterJeff', 'dbaeza13', 'alberto_mera', 'GustavoBolsa',
    'long_equity', 'jorgecriptan', 'AlvargonzalezV', 'healthy_pockets',
    'lookonchain', 'whale_alert', 'FinanzasDeChill', 'JoshMandell6',
    'Metaplanet', 'gerovich', 'adam3us', 'EneaDenkt',
    'alexditoinvest', 'InversionFundam', 'elonmusk', 'realDonaldTrump',
]

DAYS_ES   = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
MONTHS_ES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
             'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']


def parse_entry_date(entry):
    for field in ('published_parsed', 'updated_parsed'):
        t = getattr(entry, field, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def escape_html(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def fetch_section(sources, cutoff):
    items = []
    for source_name, url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                pub = parse_entry_date(entry)
                if pub and pub < cutoff:
                    continue
                title = entry.get('title', '').strip()
                link  = entry.get('link',  '').strip()
                if title and link:
                    items.append((title, link, source_name))
        except Exception:
            continue
    return items[:MAX_PER_SECTION]


def find_nitter():
    for instance in NITTER_INSTANCES:
        try:
            r = requests.get(f'https://{instance}', timeout=5)
            if r.status_code == 200:
                return instance
        except Exception:
            continue
    return None


def fetch_tweets(instance, cutoff):
    tweets = []
    for account in X_ACCOUNTS:
        try:
            feed = feedparser.parse(f'https://{instance}/{account}/rss')
            for entry in feed.entries[:3]:
                pub = parse_entry_date(entry)
                if pub and pub < cutoff:
                    continue
                title = entry.get('title', '').strip()
                link  = entry.get('link',  '').strip()
                # Skip retweets
                if not title or not link or title.startswith('RT by'):
                    continue
                # Rewrite nitter link → real X link
                link = link.replace(instance, 'x.com')
                tweets.append((f'@{account}', title, link))
                break
        except Exception:
            continue
    return tweets[:15]


def build_message(sections, tweets):
    now = datetime.now(timezone.utc)
    date_str = f"{DAYS_ES[now.weekday()]} {now.day} {MONTHS_ES[now.month - 1]}"

    lines = [f'<b>📊 RESUMEN DIARIO — {date_str}</b>\n']

    for section_name, items in sections.items():
        if not items:
            continue
        lines.append(f'\n<b>{section_name}</b>')
        for title, link, source in items:
            lines.append(f'• <a href="{link}">{escape_html(title)}</a> <i>({source})</i>')

    if tweets:
        lines.append('\n<b>🐦 LO QUE DICEN EN X</b>')
        for account, text, link in tweets:
            short = escape_html(text[:110] + ('…' if len(text) > 110 else ''))
            lines.append(f'• <b>{account}</b>: <a href="{link}">{short}</a>')

    return '\n'.join(lines)


def send_telegram(text):
    url     = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {
        'chat_id':                  TELEGRAM_CHAT_ID,
        'text':                     text,
        'parse_mode':               'HTML',
        'disable_web_page_preview': True,
    }
    requests.post(url, json=payload, timeout=15).raise_for_status()


def send_long(message):
    """Split message at newline if it exceeds Telegram's 4096-char limit."""
    if len(message) <= 4000:
        send_telegram(message)
        return
    split = message[:4000].rfind('\n')
    send_telegram(message[:split])
    time.sleep(1)
    send_telegram(message[split:])


def main():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)

    sections = {
        name: fetch_section(sources, cutoff)
        for name, sources in FEEDS.items()
    }

    tweets = []
    nitter = find_nitter()
    if nitter:
        tweets = fetch_tweets(nitter, cutoff)

    message = build_message(sections, tweets)
    send_long(message)
    print('Digest enviado.')


if __name__ == '__main__':
    main()
