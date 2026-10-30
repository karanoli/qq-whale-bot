import re
# Only remove complete leading log-style timestamp fields; preserve dates in the reply itself.
PREFIX=re.compile(r'^\s*\[\s*\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?\s*\]\s*')
def clean_reply(text):
 if not isinstance(text,str):raise ValueError('Reply must be text')
 text=text.strip()
 while PREFIX.match(text):text=PREFIX.sub('',text,count=1).strip()
 return text
