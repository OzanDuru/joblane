"""Search scope and per-application answers, separate from browser credentials."""
from urllib.parse import urlsplit

SEARCH_DEFAULTS={'geography':'turkey_first','sources':['linkedin','kariyer','company'],'work_mode':'any','roles':''}
GEOGRAPHIES={'turkey_first','turkey','abroad','worldwide'}
SOURCES={'linkedin','kariyer','company'}


def validate_search(value):
    if not isinstance(value,dict):raise ValueError('Arama filtreleri geçersiz.')
    result={**SEARCH_DEFAULTS,**value}
    if set(result)!=set(SEARCH_DEFAULTS):raise ValueError('Bilinmeyen arama filtresi.')
    if result['geography'] not in GEOGRAPHIES or result['work_mode'] not in ('any','remote','hybrid','office'):raise ValueError('Konum veya çalışma şekli geçersiz.')
    sources=result['sources']
    if not isinstance(sources,list) or not sources or any(x not in SOURCES for x in sources) or len(set(sources))!=len(sources):raise ValueError('En az bir ilan kaynağı seç.')
    if not isinstance(result['roles'],str) or len(result['roles'])>500:raise ValueError('Pozisyonları en fazla 500 karakterle yaz.')
    return result


def source_type(url):
    host=(urlsplit(url).hostname or '').lower()
    for key,domain in [('linkedin','linkedin.com'),('kariyer','kariyer.net')]:
        if host==domain or host.endswith('.'+domain):return key
    if any(host==d or host.endswith('.'+d) for d in ('ziprecruiter.com','indeed.com','glassdoor.com','monster.com','jooble.org','talent.com')):return 'other'
    return 'company'


def search_instruction(filters):
    geography={
        'turkey_first':'Prioritize Türkiye: first search Turkish roles and Türkiye locations. Aim for 4 Türkiye-based roles and at most 2 international roles in a batch of 6. If fewer Turkish roles are verifiable, return fewer jobs and explain the shortfall; do not silently fill the batch with foreign roles.',
        'turkey':'Only jobs explicitly located in Türkiye or explicitly open to remote workers based in Türkiye. Exclude unclear remote eligibility.',
        'abroad':'Only roles outside Türkiye; state the location and work authorization requirements.',
        'worldwide':'Consider all countries, explicitly state the location and remote eligibility.'}[filters['geography']]
    sources=', '.join(filters['sources'])
    return f'''Mandatory saved search scope: {geography}
Search each selected source category separately: {sources}. For linkedin run a site:linkedin.com/jobs/view query. For kariyer run a site:kariyer.net/is-ilani query. For company search original company careers / ATS postings. Do not substitute unselected job boards. Prefer the employer application page but keep the actual source URL. In search_summary report each selected source: query used, verified jobs count, or exact access/no-results limitation. Never claim a source was searched unless a web tool was used for it. Include location and remote eligibility in each description/evidence. Do not infer worldwide work permission from willingness to relocate.
Work mode: {filters['work_mode']}. Optional role keywords: {filters['roles'] or 'use search target'}.\n'''
