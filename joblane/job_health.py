"""Source-derived vacancy dates; missing dates are never inferred."""
from datetime import date,datetime,time,timedelta,timezone


def deadline_passed(value,current=None):
    if not value:return False
    current=current or datetime.now(timezone.utc)
    try:
        if len(value)==10:
            # A date without a timezone is only certainly over after it ended worldwide.
            cutoff=datetime.combine(date.fromisoformat(value),time(),timezone.utc)+timedelta(days=1,hours=12)
        else:
            cutoff=datetime.fromisoformat(value.replace('Z','+00:00'))
            if cutoff.tzinfo is None:return False
        return current>cutoff
    except (TypeError,ValueError):return False


def source_stale(check,current=None):
    current=current or datetime.now(timezone.utc)
    if check.get('posting_status') not in ('open','closed','unknown'):return True
    try:return current-datetime.fromisoformat(check['checked_at'])>timedelta(hours=24)
    except (KeyError,ValueError,TypeError):return True


def validate_source_dates(result):
    if result['posting_status'] not in ('open','closed','unknown'):raise ValueError('Invalid vacancy status.')
    for key in ('deadline','opens_on'):
        value=result[key]
        if not value:continue
        try:
            if len(value)==10:date.fromisoformat(value)
            else:
                parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
                if parsed.tzinfo is None:raise ValueError()
        except (TypeError,ValueError):raise ValueError('Source dates must be ISO dates or timezone-aware timestamps.') from None
    if (result['deadline'] or result['opens_on'] or result['posting_status']!='unknown') and not result['status_evidence'].strip():raise ValueError('Vacancy dates/status need explicit source evidence.')
