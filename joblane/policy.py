import hashlib
import ipaddress
import json
import re
import socket
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from zoneinfo import ZoneInfo


def normalize_url(value):
    try:
        p = urlsplit(value.strip())
        host = (p.hostname or '').lower()
        if p.scheme != 'https' or not host or p.username or p.password or p.port not in (None, 443):
            raise ValueError()
        if host in ('localhost',) or host.endswith(('.local','.localhost','.internal','.ts.net')) or '.' not in host:
            raise ValueError()
        try:
            if not ipaddress.ip_address(host).is_global:
                raise ValueError('Private addresses are not job sites.')
        except ValueError as e:
            if 'Private addresses' in str(e):
                raise
        query = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('trk','trackingid','refid')]
        return urlunsplit(('https',host,p.path.rstrip('/') or '/',urlencode(sorted(query)),'')), host
    except Exception:
        raise ValueError('Enter a public HTTPS application URL (no private addresses or credentials).')


def public_host(host):
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (OSError, ValueError):
        return False


def board_requires_handoff(domain):
    return any(domain == d or domain.endswith('.'+d) for d in ('linkedin.com','kariyer.net'))


def within_window(settings, current=None):
    dt = (current or datetime.now(ZoneInfo(settings['timezone']))).astimezone(ZoneInfo(settings['timezone']))
    minute = dt.hour * 60 + dt.minute
    start, end = [sum(int(x)*m for x,m in zip(settings[k].split(':'), (60,1))) for k in ('start','end')]
    return dt.weekday() in settings['days'] and start <= minute < end


def validate_settings(data):
    if data.get('mode') not in ('review','automatic'):
        raise ValueError('Choose review or automatic mode.')
    for k in ('start','end'):
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', str(data.get(k,''))):
            raise ValueError('Use a valid 24-hour time.')
    if data['start'] >= data['end']:
        raise ValueError('The end must be later than the start on the same day.')
    ZoneInfo(data.get('timezone','Europe/Istanbul'))
    if not isinstance(data.get('days'),list) or not data['days'] or any(type(d) is not int or d not in range(7) for d in data['days']):
        raise ValueError('Choose at least one day.')
    if type(data.get('daily_limit')) is not int or not 1 <= data['daily_limit'] <= 100:
        raise ValueError('Daily limit must be between 1 and 100.')
    domains = data.get('allowed_domains',[])
    if not isinstance(domains,list) or len(domains)>100:
        raise ValueError('Invalid domain list.')
    for domain in domains:
        _, host = normalize_url('https://'+domain)
        if host != domain or board_requires_handoff(domain):
            raise ValueError('Use exact company form domains. LinkedIn and Kariyer.net stay manual in this version.')
    if data.get('employment') not in ('Any','Full-time','Part-time','Internship','Contract'):
        raise ValueError('Invalid employment preference.')
    return {**data, 'enabled': bool(data.get('enabled'))}


def validate_profile(p):
    for key in ('name','email','phone','location','headline','skills','links','languages','verified_notes'):
        if not isinstance(p.get(key,''),str) or len(p.get(key,''))>6000:
            raise ValueError('Invalid profile field: '+key)
    if not p.get('name','').strip() or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',p.get('email','')):
        raise ValueError('Your name and a valid email are required.')
    for key in ('education','experience','projects'):
        if not isinstance(p.get(key),list) or len(p[key])>30:
            raise ValueError('Invalid '+key)
        for row in p[key]:
            if not isinstance(row,dict) or any(not isinstance(row.get(k,''),str) or len(row.get(k,''))>6000 for k in ('title','dates','text','tags')):
                raise ValueError('Invalid entry in '+key)
    if not isinstance(p.get('summaries'),dict) or any(not isinstance(p['summaries'].get(k,''),str) or len(p['summaries'].get(k,''))>3000 for k in ('software','security','ml')):
        raise ValueError('Invalid role summaries.')
    return p


def digest(profile, job):
    return hashlib.sha256(json.dumps({'profile':profile,'job':{k:job[k] for k in ('url','description','track','title','company')}}, sort_keys=True).encode()).hexdigest()


def matches_preferences(job, settings):
    text = (job['title']+' '+job['description']).lower()
    for key in ('roles','locations'):
        terms = [v.strip().lower() for v in settings.get(key,'').split(',') if v.strip()]
        if terms and not any(t in text for t in terms):
            return False, 'Does not match your '+key+' preference. Add missing job details or adjust the filter.'
    kind = settings.get('employment','Any')
    patterns={'Full-time':r'\bfull[ -]?time\b|tam zamanlı','Part-time':r'\bpart[ -]?time\b|yarı zamanlı','Internship':r'\binternship\b|\bstaj\b','Contract':r'\bcontract\b|sözleşmeli'}
    if kind != 'Any' and not re.search(patterns[kind],text):
        return False, 'Employment type is not confirmed in the job description.'
    return True, ''
