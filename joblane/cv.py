import html
import re
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def font_names():
    # Windows Arial, macOS Arial, Linux DejaVu; Unicode is important for Turkish names.
    candidates = [
      (Path('C:/Windows/Fonts/arial.ttf'),Path('C:/Windows/Fonts/arialbd.ttf')),
      (Path('/System/Library/Fonts/Supplemental/Arial.ttf'),Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf')),
      (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')),
    ]
    for regular,bold in candidates:
        if regular.exists() and bold.exists():
            if 'Resume' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('Resume',str(regular)))
                pdfmetrics.registerFont(TTFont('ResumeBold',str(bold)))
                pdfmetrics.registerFontFamily('Resume',normal='Resume',bold='ResumeBold')
            return 'Resume','ResumeBold'
    raise ValueError('Install Arial or DejaVu Sans to export a CV with Turkish characters.')


def tokens(text):
    return set(re.findall(r'[\w+#.]{2,}', text.lower()))


def tailor(profile, job):
    wanted = tokens(job['title']+' '+job['description'])
    skills = [s.strip() for s in profile.get('skills','').split(',') if s.strip()]
    skills.sort(key=lambda s: bool(tokens(s)&wanted), reverse=True)
    projects = sorted(profile['projects'],key=lambda p: (job['track'] in p.get('tags','').lower(),len(tokens(p['title']+' '+p['text'])&wanted)),reverse=True)
    return {**profile,'skills':', '.join(skills),'projects':projects,
            'summary':profile['summaries'].get(job['track'],'')}


def generate(profile, job, path):
    facts = tailor(profile,job)
    regular,bold = font_names()
    styles = {
      'name':ParagraphStyle('name',fontName=bold,fontSize=23,leading=27,textColor=colors.HexColor('#142d2b'),spaceAfter=5),
      'headline':ParagraphStyle('headline',fontName=regular,fontSize=11,leading=15,spaceAfter=5),
      'body':ParagraphStyle('body',fontName=regular,fontSize=9,leading=11.4,spaceAfter=3),
      'meta':ParagraphStyle('meta',fontName=regular,fontSize=8,leading=10,textColor=colors.HexColor('#526466'),spaceAfter=3),
      'section':ParagraphStyle('section',fontName=bold,fontSize=10,leading=12,textColor=colors.HexColor('#23645b'),spaceBefore=9,spaceAfter=5,keepWithNext=True),
      'title':ParagraphStyle('title',fontName=bold,fontSize=9.5,leading=11.5,spaceAfter=3),
    }
    def p(text,style='body'):
        return Paragraph(html.escape(text).replace('\n','<br/>'),styles[style])
    story=[p(facts['name'],'name'),p(facts.get('headline',''),'headline'),
           p(' | '.join(x for x in (facts['email'],facts.get('phone'),facts.get('location')) if x),'meta')]
    if facts.get('links'): story.append(p(facts['links'],'meta'))
    if facts.get('languages'): story.append(p(facts['languages'],'meta'))
    if facts['summary']: story.extend([p('PROFILE','section'),p(facts['summary'])])
    story.extend([p('TECHNICAL SKILLS','section'),p(facts['skills'])])
    for key,label in (('experience','EXPERIENCE'),('projects','PROJECTS & RESEARCH'),('education','EDUCATION')):
        story.append(p(label,'section'))
        for row in facts[key]:
            block=[p(row['title'],'title')]
            if row.get('dates'): block.append(p(row['dates'],'meta'))
            if row.get('text'): block.append(p(row['text']))
            block.append(Spacer(1,2))
            story.append(KeepTogether(block))
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=35,bottomMargin=35,
                      title=f"{facts['name']} - {job['title']}",author=facts['name']).build(story)
    return facts
