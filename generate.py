from datetime import datetime
import glob
import json
import os
import sys
import re
import urllib
from jinja2 import Environment, PackageLoader

if sys.version_info.major < 3:
    exit("This code requires Python 3.\nThis is {}".format(sys.version))

def main():
    conferences, topics = read_files()
    #print(conferences)
    generate_pages(conferences, topics)

def read_files():
    conferences = []
    topics = {}
    now = datetime.now().strftime('%Y-%m-%d')

    for filename in glob.glob("data/*.txt"):
        print("Reading {}".format(filename))
        conf = {}
        try:
            this = {}
            nickname = os.path.basename(filename)
            nickname = nickname[0:-4]
            #print(nickname)
            this['nickname'] = nickname
            with open(filename, encoding="utf-8") as fh:
                for line in fh:
                    line = line.rstrip('\n')
                    if re.search(r'\A\s*#', line):
                        continue
                    if re.search(r'\A\s*\Z', line):
                        continue
                    line = re.sub(r'\s+\Z', '', line)
                    k,v = re.split(r'\s*:\s*', line, maxsplit=1)
                    this[k] = v

            my_topics = []
            if this['topics']:
                for t in re.split(r'\s*,\s*', this['topics']):
                    p = topic2path(t)
                    #if p == '':
                    #    exit("ERROR {}".format(this))
                    my_topics.append({
                        'name' : t,
                        'path' : p,
                    })
                    if p not in topics:
                        topics[p] = {
                            'name': t,
                            'events' : []
                        }
                    topics[p]['events'].append(this)
            this['topics'] = my_topics

            this['cfp_class'] = 'cfp_none'
            cfp = this.get('cfp_date', '')
            if cfp != '':
                if cfp < now:
                    this['cfp_class'] = 'cfp_past'
                else:
                    this['cfp_class'] = 'cfp_future'

            conferences.append(this)
        except Exception as e:
            exit("ERROR: {} in file {}".format(e, filename))

    return sorted(conferences, key=lambda x: x['start_date']), topics

def generate_pages(conferences, topics):
    sitemap = []

    now = datetime.now().strftime('%Y-%m-%d')
    #print(now)

    locations = {}

    stats = {
        'total' : len(conferences),
        'future': len(list(filter(lambda x: x['start_date'] >= now, conferences))),
        'cfp'   : len(list(filter(lambda x: x.get('cfp_date', '') >= now, conferences))),
        'has_coc' : 0,
        'has_coc_future' : 0,
        'has_a11y' : 0,
        'has_a11y_future' : 0,
    }
    for e in conferences:
        if not 'country' in e:
            exit('Country could not be found')
        country_name = e['country']
        country_page = re.sub(r'\s+', '-', country_name.lower())
        e['country_page'] = country_page
        if country_page not in locations:
            locations[country_page] = {
                'name' : country_name,
                'events' : []
            }
        locations[country_page]['events'].append(e)

        if e.get('code_of_conduct'):
            stats['has_coc'] += 1
            if e['start_date'] >= now:
                stats['has_coc_future'] += 1
        if e.get('accessibility'):
            stats['has_a11y']
            if e['start_date'] >= now:
                stats['has_a11y_future'] += 1
    stats['coc_future_perc']  = int(100 * stats['has_coc_future'] / stats['future'])
    stats['a11y_future_perc'] = int(100 * stats['has_a11y_future'] / stats['future'])

    env = Environment(loader=PackageLoader('conf', 'templates'))
    if not os.path.exists('html/'):
        os.mkdir('html/')

    event_template = env.get_template('event.html')
    if not os.path.exists('html/e/'):
        os.mkdir('html/e/')
    for event in conferences:
        #print(event['nickname'])

        if 'cfp_date' in event and event['cfp_date'] >= now:
            tweet_cfp = 'The CfP of {} ends on {} see {} via http://conferences.szabgab.com/'.format(event['name'], event['cfp_date'], event['url'])
            if event['twitter']:
                tweet_cfp += ' @' + event['twitter']
            for t in event['topics']:
                tweet_cfp += ' #' + t['name']
            event['tweet_cfp'] = urllib.parse.quote(tweet_cfp)

        tweet_me = event['name']
        tweet_me += ' on ' + event['start_date']
        tweet_me += ' in ' + event['city']
        if 'state' in event:
            tweet_me += ', ' + event['state']
        tweet_me += ' ' + event['country']
        if event['twitter']:
            tweet_me += ' @' + event['twitter']
        tweet_me += " " + event['url']
        for t in event['topics']:
            tweet_me += ' #' + t['name']
        #tweet_me += ' via @szabgab'
        tweet_me += ' via http://conferences.szabgab.com/'

        event['tweet_me'] = urllib.parse.quote(tweet_me)
        try:
            with open('html/e/' + event['nickname'], 'w', encoding="utf-8") as fh:
                fh.write(event_template.render(
                    h1          = event['name'],
                    title       = event['name'],
                    event = event,
            ))
            sitemap.append({
                'url' : '/e/' + event['nickname']
            })
        except Exception as e:
            print("ERROR: {}".format(e))
        

    future = list(filter(lambda x: x['start_date'] >= now, conferences))
    #print(future)
    main_template = env.get_template('index.html')
    with open('html/index.html', 'w', encoding="utf-8") as fh:
        fh.write(main_template.render(
            h1          = 'Tech related conferences',
            title       = 'Tech related conferences',
            conferences = future,
            stats       = stats,
        ))
    sitemap.append({
        'url' : '/'
    })

    with open('html/conferences', 'w', encoding="utf-8") as fh:
        fh.write(main_template.render(
            h1          = 'Tech related conferences',
            title       = 'Tech related conferences',
            conferences = conferences,
        ))
    sitemap.append({
        'url' : '/conferences'
    })

    cfp = list(filter(lambda x: 'cfp_date' in x and x['cfp_date'] >= now, conferences))
    cfp.sort(key=lambda x: x['cfp_date'])
    #cfp_template = env.get_template('cfp.html')
    with open('html/cfp', 'w', encoding="utf-8") as fh:
        fh.write(main_template.render(
            h1          = 'Call for Papers',
            title       = 'Call of Papers',
            conferences = cfp,
        ))
    sitemap.append({
        'url' : '/cfp'
    })


    no_code = list(filter(lambda x: not x.get('code_of_conduct'), conferences))
    code_template = env.get_template('code-of-conduct.html')
    with open('html/code-of-conduct', 'w', encoding="utf-8") as fh:
        fh.write(code_template.render(
            h1          = 'Code of Conduct',
            title       = 'Code of Conduct (or lack of it)',
            conferences = no_code,
        ))
    sitemap.append({
        'url' : '/code-of-conduct'
    })

    save_pages('t', topics, sitemap, main_template, now)
    save_pages('l', locations, sitemap, main_template, now)

    collections_template = env.get_template('topics.html')
    save_collections('t', 'topics', 'Topics', topics, sitemap, collections_template)
    save_collections('l', 'countries', 'Countries', locations, sitemap, collections_template)

    with open('html/sitemap.xml', 'w', encoding="utf-8") as fh:
        fh.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for e in sitemap:
            fh.write('  <url>\n')
            fh.write('    <loc>http://conferences.szabgab.com{}</loc>\n'.format(e['url']))
            fh.write('    <lastmod>{}</lastmod>\n'.format(now))
            fh.write('  </url>\n')
        fh.write('</urlset>\n')

def save_collections(directory, filename, title, data, sitemap, template):
    with open('html/' + filename, 'w', encoding="utf-8") as fh:
        fh.write(template.render(
            h1          = title,
            title       = title,
            data        = data,
            directory   = directory,
        ))
    sitemap.append({
        'url' : '/' + filename
    })

def save_pages(directory, data, sitemap, main_template, now):
    my_dir =  'html/' + directory + '/'
    if not os.path.exists(my_dir):
        os.mkdir(my_dir)
    for d in data.keys():
        conferences = sorted(data[d]['events'], key=lambda x: x['start_date'])
        #print("'{}'".format(d))
        #print(my_dir + d)
        with open(my_dir + d, 'w', encoding="utf-8") as fh:
            fh.write(main_template.render(
                h1          = data[d]['name'],
                title       = data[d]['name'],
                conferences = filter(lambda x: x['start_date'] >= now, conferences),
                earlier_conferences = filter(lambda x: x['start_date'] < now, conferences),
            ))
        sitemap.append({
            'url' : '/' + directory + '/' + d
        })


def topic2path(tag):
    return re.sub(r'[\W_]+', '-', tag.lower())

main()

# vim: expandtab
