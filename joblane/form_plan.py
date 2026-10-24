"""Bounded field plans: no arbitrary scripts, selectors, navigation or submit actions."""
import hashlib
import json
import re

TEXT_KINDS={'text','textarea','email','tel','url','number','select-one'}
SENSITIVE=re.compile(r'password|şifre|social security|ssn|passport|pasaport|kimlik no|credit card|kredi kart|agree|consent|terms|kabul|onay|privacy|kvkk',re.I)


def descriptors(fields):
    return [{k:f.get(k) for k in ('index','label','kind','required','options')} for f in fields]


def signature(fields):
    return hashlib.sha256(json.dumps(descriptors(fields),sort_keys=True).encode()).hexdigest()


def validate_plan(result,fields,facts):
    if not isinstance(result,dict) or set(result)!={'answers','questions','requires_review'}:raise ValueError('Invalid field plan.')
    if type(result['requires_review']) is not bool or not isinstance(result['questions'],list) or len(result['questions'])>15 or any(not isinstance(q,str) or len(q)>1000 for q in result['questions']):raise ValueError('Invalid form questions.')
    if not isinstance(result['answers'],list) or len(result['answers'])>100:raise ValueError('Invalid field answers.')
    by_index={f['index']:f for f in fields};seen=set()
    for answer in result['answers']:
        if not isinstance(answer,dict) or set(answer)!={'index','label','value','fact_ids'}:raise ValueError('Invalid field answer.')
        idx=answer['index'];f=by_index.get(idx) if type(idx) is int else None
        if not f or idx in seen or answer['label']!=f['label']:raise ValueError('Form field changed or repeated.')
        seen.add(idx)
        if f['kind'] not in TEXT_KINDS or SENSITIVE.search(f['label']):raise ValueError('This field requires direct user input.')
        value=answer['value']
        if not isinstance(value,str) or not value.strip() or len(value)>2000:raise ValueError('Invalid field value.')
        refs=answer['fact_ids']
        if not isinstance(refs,list) or not refs or any(not isinstance(r,str) or r not in facts for r in refs):raise ValueError('Field answer must cite supplied facts.')
        if f['kind']=='select-one' and value not in [o['value'] for o in (f.get('options') or [])]:raise ValueError('Choice is not present on this form.')
    return result
