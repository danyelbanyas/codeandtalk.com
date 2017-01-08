import csv
import copy
from datetime import datetime
import glob
import json
import os
import re
import urllib
import shutil
from jinja2 import Environment, PackageLoader

def topic2path(tag):
    t = tag.lower()
    t = re.sub(r'í', 'i', t)
    t = re.sub(r'ó', 'o', t)
    t = re.sub(r'ã', 'a', t)
    t = re.sub(r'[\W_]+', '-', t)
    return t

def html2txt(html):
    #text = re.sub(r'<a\s+href="[^"]+">([^<]+)</a>', '$1', html)
    text = re.sub(r'</?[^>]+>', '', html)
    return text

def new_tag(t):
    return {
        'name' : t,
        #'events' : [],
        'videos' : 0,
        'episodes' : [],
        'total' : 0,
        'future' : 0,
    }

class GenerateSite(object):
    def __init__(self):
        self.root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.now = datetime.now().strftime('%Y-%m-%d')
        self.sitemap = []
        self.people = {}
        self.redirects = []
        self.people_search = {}
        self.tags = {}
        self.blasters = []
        self.html = os.path.join(self.root, 'html')
        self.data = os.path.join(self.root, 'data')
        self.featured_by_blaster = {}
        self.featured_by_date = {}
        self.events = {}
        self.countries = {}  # TODO remove
        self.cities = {}     # TODO remove
 
        self.stats = {
            'has_coc' : 0,
            'has_coc_future' : 0,
            'has_a11y' : 0,
            'has_a11y_future' : 0,
            'has_diversity_tickets' : 0,
            'has_diversity_tickets_future' : 0,
            'cities'    : {},
            'countries' : {},
            #'tags'      : {},
        }

    def read_all(self):
        self.read_sources()
        self.read_tags()
        self.read_blasters()
        self.read_events()
        self.read_series()
        self.read_people()
        self.read_videos()
        self.read_podcast_episodes()


    def process_videos(self):
        for video in self.videos:
            short_description = html2txt(video.get('description', ''))
            short_description = re.sub(r'"', '', short_description)
            short_description = re.sub(r'\s+', ' ', short_description)
            video['short_description'] = short_description
            limit = 128
            if len(short_description) > 128:
                video['short_description'] =  short_description[0:limit]
    
    def generate_site(self):
        self.read_all()

        self.check_people()
        self.check_videos()

        self.process_videos()

        cat = {
            'people'   : copy.deepcopy(self.people),
            'videos'   : copy.deepcopy(self.videos),
            'events'   : copy.deepcopy(self.events),
            'blasters' : copy.deepcopy(self.blasters),
        }

        self.preprocess_events()

        if os.path.exists(self.html):
            shutil.rmtree(self.html)
        shutil.copytree('src', self.html)

        self.generate_people_pages()
        self.generate_podcast_pages()
        self.generate_pages()
        #self.save_search()

        cat['tags']  = copy.deepcopy(self.tags)
        cat['stats'] = copy.deepcopy(self.stats)
        cat['series'] = copy.deepcopy(self.series)
        self.save_all(cat)

    def save_all(self, cat):
        with open(self.html + '/cat.json', 'w', encoding="utf-8") as fh:
            json.dump(cat, fh)

    def read_sources(self):
        with open(self.data + '/sources.json', encoding="utf-8") as fh:
            self.sources = json.load(fh)


    def read_tags(self):
        with open(self.data + '/tags.csv', encoding="utf-8") as fh:
            rd = csv.DictReader(fh, delimiter=';')
            for row in rd:
                path = topic2path(row['name'])
                self.tags[ path ] = new_tag(row['name'])
                #self.stats['tags'][path] = {
                #    'total'  : 0,
                #    'future' : 0,
                #}
        return

    def read_blasters(self):
        with open(self.data + '/blasters.csv', encoding="utf-8") as fh:
            rd = csv.DictReader(fh, delimiter=';')
            for row in rd:
                self.blasters.append(row)
        return

    def read_events(self):
        for filename in glob.glob(self.data + '/events/*.txt'):
            if filename[len(self.root):] != filename[len(self.root):].lower():
                raise Exception("filename '{}' is not all lower case".format(filename))
            #print("Reading {}".format(filename))
            conf = {}
            try:
                this = {}
                nickname = os.path.basename(filename)
                nickname = nickname[0:-4]
                #print(nickname)
                this['nickname'] = nickname
                this['file_date'] = datetime.fromtimestamp( os.path.getctime(filename) ).strftime('%Y-%m-%d')
                with open(filename, encoding="utf-8") as fh:
                    for line in fh:
                        line = line.rstrip('\n')

                        # Avoid trailing spaces in event files
                        #if re.search(r'\s\Z', line):
                        #    print("Trailing space in '{}' {}".format(line, filename))
                        #    raise Exception("Trailing space in '{}' {}".format(line, filename))

                        if re.search(r'\A\s*#', line):
                            continue
                        if re.search(r'\A\s*\Z', line):
                            continue
                        line = re.sub(r'\s+\Z', '', line)
                        k,v = re.split(r'\s*:\s*', line, maxsplit=1)
                        if k in this:
                            print("Duplicate field '{}' in {}".format(k, filename))
                        else:
                            this[k] = v

                date_format =  r'^\d\d\d\d-\d\d-\d\d$'
                # TODO: add requirement for start_date and end_date
                for f in ['start_date', 'end_date', 'cfp_date']:
                    if f in this and this[f] and not re.search(date_format, this[f]):
                        raise Exception('Invalid {} {} in {}'.format(f, this[f], filename))

                if not 'country' in this or not this['country']:
                    raise Exception('Country is missing from {}'.format(this))
 
                my_topics = []
                #print(this)
                if this['topics']:
                    for t in re.split(r'\s*,\s*', this['topics']):
                        p = topic2path(t)
                        if p not in self.tags:
                            raise Exception("Topic '{}' is not in the list of tags".format(p))
                        my_topics.append({
                            'name' : t,
                            'path' : p,
                        })
                this['topics'] = my_topics

                this['cfp_class'] = 'cfp_none'
                cfp = this.get('cfp_date', '')
                if cfp != '':
                    if cfp < self.now:
                        this['cfp_class'] = 'cfp_past'
                    else:
                        this['cfp_class'] = 'cfp_future'

                if 'city' not in this or not this['city']:
                    raise Exception("City is missing from {}".format(this))
                city_name = '{}, {}'.format(this['city'], this['country'])
                city_page = topic2path('{} {}'.format(this['city'], this['country']))
                # In some countries we require a state:
                if this['country'] in ['Australia', 'Brasil', 'India', 'USA']:
                    if 'state' not in this or not this['state']:
                        raise Exception('State is missing from {}'.format(this))
                    city_name = '{}, {}, {}'.format(this['city'], this['state'], this['country'])
                    city_page = topic2path('{} {} {}'.format(this['city'], this['state'], this['country']))
                this['city_name'] = city_name
                this['city_page'] = city_page

                if city_page not in self.cities:
                    self.cities[city_page] = {
                        'name' : this['city_name'],
                        'events' : []
                    }
                self.cities[city_page]['events'].append(this)

                if city_page not in self.stats['cities']:
                    self.stats['cities'][city_page] = {
                        'name' : city_name,
                        'total' : 0,
                        'future' : 0,
                    }
                self.stats['cities'][city_page]['total'] += 1
                if this['start_date'] >= self.now:
                    self.stats['cities'][city_page]['future'] += 1


                country_name = this['country']
                country_page = re.sub(r'\s+', '-', country_name.lower())
                this['country_page'] = country_page
                if country_page not in self.countries:
                    self.countries[country_page] = {
                        'name' : country_name,
                        'events' : []
                    }
                self.countries[country_page]['events'].append(this)

                if country_page not in self.stats['countries']:
                    self.stats['countries'][country_page] = {
                        'name'   : country_name,
                        'total'  : 0,
                        'future' : 0,
                    }
                self.stats['countries'][country_page]['total'] += 1
                if this['start_date'] >= self.now:
                    self.stats['countries'][country_page]['future'] += 1

                for tag in this['topics']:
                    p = tag['path']
                    if p not in self.tags:
                        raise Exception("Missing tag '{}'".format(p))
                    #self.tags[p]['events'].append(this)
                    self.tags[p]['total'] += 1
                    if this['start_date'] >= self.now:
                        self.tags[p]['future'] += 1
                    #self.stats['tags'][p]['total'] += 1
                    #if this['start_date'] >= self.now:
                    #    self.stats['tags'][p]['future'] += 1

                self.events[ this['nickname'] ] = this

            except Exception as e:
                exit("ERROR 1: {} in file {}".format(e, filename))
        return


    def read_people(self):
        path = self.data + '/people'

        for filename in glob.glob(path + "/*.txt"):
            if filename[len(self.root):] != filename[len(self.root):].lower():
                raise Exception("filename '{}' is not all lower case".format(filename)) 
            try:
                this = {}
                nickname = os.path.basename(filename)
                nickname = nickname[0:-4]
                description = None
                with open(filename, encoding="utf-8") as fh:
                    for line in fh:
                        if re.search(r'__DESCRIPTION__', line):
                            description = ''
                            continue
                        if description != None:
                            description += line
                            continue
                        
                        line = line.rstrip('\n')
                        if re.search(r'\s\Z', line):
                            raise Exception("Trailing space in '{}' {}".format(line, filename))
                        if re.search(r'\A\s*\Z', line):
                            continue
                        k,v = re.split(r'\s*:\s*', line, maxsplit=1)
                        if k in this:
                            if k == 'home':
                                # TODO: decide what to do with multiple home: entries
                                #print("Duplicate field '{}' in {}".format(k, filename))
                                pass
                            else:
                                raise Exception("Duplicate field '{}' in {}".format(k, filename))
                        this[k] = v

                if description:
                    this['description'] = description

                if 'redirect' in this:
                    self.redirects.append({
                        'from' : nickname,
                        'to'   : this['redirect'],
                    })
                    continue

                for field in ['twitter', 'github', 'home']:
                    if field not in this:
                        #print("WARN: {} missing for {}".format(field, nickname))
                        pass
                    elif this[field] == '-':
                        this[field] = None
                self.people[nickname] = {
                    'info': this,
                    #'episodes' : [],
                    #'hosting' : [],
                    #'videos'  : [],
                    #'file_date' : datetime.fromtimestamp( os.path.getctime(filename) ).strftime('%Y-%m-%d'),
                }

                person = {
                    'name'     : this['name'],
                }
                if 'country' in this:
                    person['location'] = this['country']
                if 'topics' in this:
                    person['topics']   = this['topics']
                    for t in re.split(r'\s*,\s*', this['topics']):
                        p = topic2path(t)
                        if p not in self.tags:
                            raise Exception("Topic '{}' is not in the list of tags".format(p))

                self.people_search[nickname] = person
            except Exception as e:
                exit("ERROR 2: {} in file {}".format(e, filename))

        return

    def read_series(self):
        with open(self.data + '/series.json') as fh:
            self.series = json.load(fh)
            for s in self.series:
                if s == '':
                    raise Exception("empty key in series {}".format(self.series[s]))

    def read_videos(self):
        path = self.data + '/videos'
        events = os.listdir(path)
        self.videos = []
        for event in events:
            dir_path = os.path.join(path, event)
            for video_file_path in glob.glob(dir_path + '/*.json'):
                video_file = os.path.basename(video_file_path)
                html_file_path = video_file_path[0:-4] + 'html'

                with open(video_file_path) as fh:
                    try:
                        video = json.load(fh)
                        video['filename'] = video_file[0:-5]
                        video['event']    = event
                        video['file_date'] = datetime.fromtimestamp( os.path.getctime(video_file_path) ).strftime('%Y-%m-%d')

                        if os.path.exists(html_file_path):
                            with open(html_file_path) as hfh:
                                video['description'] = hfh.read()
                        self.videos.append(video)
                    except Exception as e:
                        exit("There was an exception reading {}\n{}".format(video_file_path, e))

                if 'tags' in video:
                    tags = []
                    for t in video['tags']:
                        p = topic2path(t)
                        tags.append({
                            'text': t,
                            'link': p,
                        })

                    video['tags'] = tags

 
        self.stats['videos'] = len(self.videos)
        return


    def read_podcast_episodes(self):
        self.episodes = []
        for src in self.sources:
            #print("Processing source {}".format(src['name']))
            file = self.data + '/podcasts/' + src['name'] + '.json'
            src['episodes'] = []
            if os.path.exists(file):
                with open(file, encoding="utf-8") as fh:
                    try:
                        new_episodes = json.load(fh)
                        for episode in new_episodes:
                            episode['source'] = src['name']
                            if 'ep' not in episode:
                                #print("WARN ep missing from {} episode {}".format(src['name'], episode['permalink']))
                                pass
                        self.episodes.extend(new_episodes)
                        src['episodes'] = new_episodes
                    except json.decoder.JSONDecodeError as e:
                        exit("ERROR 3: Could not read in {} {}".format(file, e))
                        src['episodes'] = [] # let the rest of the code work
                        pass

        for e in self.episodes:
            #print(e)
            #exit()
            if 'tags' in e:
                tags = []
                for tag in e['tags']:
                    path = topic2path(tag)
                    if path not in tags:
                        tags.append({
                            'text' : tag,
                            'link' : path,
                        })
                    if path not in self.tags:
                        raise Exception("Missing tag '{}'".format(path))
                        #self.tags[path] = new_tag(tag)
                    self.tags[path]['episodes'].append(e)

                e['tags'] = tags

    def create_blaster_pages(self, root):
        my_dir = root + '/blaster';
        if not os.path.exists(my_dir):
            os.mkdir(my_dir)

        env = Environment(loader=PackageLoader('cat', 'templates'))
        blaster_template = env.get_template('blaster.html')

        for topic in self.blasters:
            with open(os.path.join(my_dir, topic['file']), 'w', encoding="utf-8") as fh:
                fh.write(blaster_template.render(
                    h1          = topic['name'] + ' Blaster',
                    title       = topic['name'] + ' Blaster',
                    blaster     = topic,
                ))
            #self.sitemap.append({
            #    'url' : '/' + topic['file'] + 'blaster'
            #})


    def _add_events_to_series(self):
        '''
            Go over all the events and based on the longest matching prefix of their filenames,
            put them in one of the entries in the series.
            To each event add the name of the series it is in.
            TODO: In the future we might add an exception if an event is not in any of the series.
        '''
        for s in self.series.keys():
            self.series[s]['events'] = []
        other = []
        for nickname in self.events.keys():
            e = self.events[nickname]
            event = {
                'nickname'   : e['nickname'],
                'name'       : e['name'],
                'start_date' : e['start_date'],
            }
            for s in sorted(self.series.keys(), key=lambda s: len(s), reverse=True):
                l = len(s)
                if event['nickname'][0:l] == s:
                    self.series[s]['events'].append(event)
                    event['series'] = s
                    break
            else:
                #TODO: create series for every event and then turn on the exception?
                #print("Event without series: {}".format(event['nickname']))
                #raise Exception("Event without series: {}".format(event['nickname']))
                other.append(event)

        for s in self.series.keys():
            self.series[s]['events'].sort(key=lambda x: x['start_date'])
        #self.event_in_series = {}
        #for e in self.series[s]['events']:
        #    self.event_in_series[ e['nickname'] ] = s

    def _process_videos(self):
        for b in self.blasters:
            self.featured_by_blaster[ b['file'] ] = []

        for video in self.videos:

            video['event'] = {
                'name'     : self.events[ video['event'] ]['name'],
                'nickname' : self.events[ video['event'] ]['nickname'],
                'url'      : self.events[ video['event'] ]['url'],
                'twitter'  : self.events[ video['event'] ]['twitter'],  
            }

           # collect featured videos
            featured = video.get('featured')
            blasters = video.get('blasters', [])
            if featured:

                # Make sure we have a length field
                if 'length' not in video:
                    raise Exception("Video {}/{}.json was featured but has no length".format(video['event']['nickname'], video['filename']))
                class_name = ''
                if video['featured'] == self.now:
                    class_name = 'today_feature'
                elif video['featured'] > self.now:
                    class_name = 'future_feature'
                this_video = {
                    'class_name' : class_name,
                    'blasters'   : video['blasters'],
                    'featured'   : video['featured'],
                    'recorded'   : video['recorded'],
                    'filename'   : video['filename'],
                    'length'     : video['length'],
                    'title'      : video['title'],
                    'event'      : {
                        'nickname' : video['event']['nickname'],
                        'name'     : video['event']['name'],
                    },
                }

                if featured not in self.featured_by_date:
                    self.featured_by_date[featured] = []
                self.featured_by_date[featured].append(this_video)

                if len(blasters) == 0:
                    raise Exception("featured without blaster data/videos/{}/{}.json".format(video['event']['nickname'], video['filename']))
                for b in blasters:
                    if b not in self.featured_by_blaster:
                        self.featured_by_blaster[ b ] = []
                        #TODO mark these:
                        #print("Blaster {} is used but not in the blaster list".format(b))
                    
                    self.featured_by_blaster[b].append(this_video)
            speakers = {}
            for s in video['speakers']:
                if s in self.people:
                    speakers[s] = self.people[s]
                    #exit(video)
                    if 'videos' not in self.people[s]:
                        self.people[s]['videos'] = []

                    self.people[s]['videos'].append({
                        'recorded' : video['recorded'],
                        'title'    : video['title'],
                        # short_description
                        'event'    : video['event'],
                        'filename' : video['filename'],
                        'thumbnail_url' : video['thumbnail_url'],
                    })
                    if not 'tags' in self.people_search[s]:
                        self.people_search[s]['tags'] = set()
                    if 'tags' in video:
                        for t in video['tags']:
                            self.people_search[s]['tags'].add(t['link'])
                    #else:
                    #    TODO: shall we requre tags for each video?
                    #    exit(video)
                    
                else:
                    raise Exception("Missing people file for '{}' in {}/videos/{}/{}.json".format(s, self.data, video['event']['nickname'], video['filename']))
            video['speakers'] = speakers

            tweet_video = '{} https://codeandtalk.com/v/{}/{}'.format(video['title'], video['event']['nickname'], video['filename'])
            tw_id = video['event'].get('twitter', '')
            if tw_id:
                tweet_video += ' presented @' + tw_id
            #print(v['speakers'])
            #exit()
            if video['speakers']:
                for s in video['speakers']:
                    tw_id = video['speakers'][s]['info'].get('twitter', '')
                    if tw_id:
                        tweet_video += ' by @' + tw_id


            if 'tags' in video:
                for t in video['tags']:
                    p = t['link']
                    if p not in self.tags:
                        raise Exception("Missing tag '{}'".format(p))
                        #self.tags[p] = new_tag(t)
                    #self.tags[p]['videos'].append(video)
                    self.tags[p]['videos'] += 1
                    if not re.search(r'-', t['link']) and len(t['link']) < 20:
                        tweet_video += ' #' + t['link']
            video['tweet_video'] = urllib.parse.quote(tweet_video)

        #print(self.featured_by_blaster)

    def _process_podcasts(self):
        for e in self.episodes:
            if 'guests' in e:
                for g in e['guests'].keys():
                    if g not in self.people:
                        exit("ERROR 4: '{}' is not in the list of people".format(g))
                    if 'episodes' not in self.people[g]:
                        self.people[g]['episodes'] = []
                    self.people[g]['episodes'].append(e)
            if 'hosts' in e:
                for h in e['hosts'].keys():
                    if h not in self.people:
                        exit("ERROR 5: '{}' is not in the list of people".format(h))
                    if 'hosting' not in self.people[h]:
                        self.people[h]['hosting'] = []
                    self.people[h]['hosting'].append(e)

    def _process_events(self):
        self.event_videos = {}
        for v in self.videos:
            if v['event']['nickname'] not in self.event_videos:
                self.event_videos[ v['event']['nickname'] ] = []
            self.event_videos[ v['event']['nickname'] ].append(v)

        for nickname in self.events.keys():
            event = self.events[nickname]
            if 'youtube' in event and event['youtube'] == '-':
                event['youtube'] = None


            if event['nickname'] in self.event_videos:
                event['videos'] = self.event_videos[ event['nickname'] ]


            if event.get('diversitytickets'):
                self.stats['has_diversity_tickets'] += 1
                if event['start_date'] >= self.now:
                    self.stats['has_diversity_tickets_future'] += 1
            if event.get('code_of_conduct'):
                self.stats['has_coc'] += 1
                if event['start_date'] >= self.now:
                    self.stats['has_coc_future'] += 1
            if event.get('accessibility'):
                self.stats['has_a11y']
                if event['start_date'] >= self.now:
                    self.stats['has_a11y_future'] += 1

            if 'cfp_date' in event and event['cfp_date'] >= self.now:
                tweet_cfp = 'The CfP of {} ends on {} see {} via https://codeandtalk.com/'.format(event['name'], event['cfp_date'], event['url'])
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
            #tweet_me += ' via @codeandtalk'
            tweet_me += ' via https://codeandtalk.com/'

            event['tweet_me'] = urllib.parse.quote(tweet_me)


    def preprocess_events(self):
        self.stats['total']  = len(self.events)
        self.stats['future'] = len(list(filter(lambda x: x['start_date'] >= self.now, self.events.values())))
        self.stats['cfp']    = len(list(filter(lambda x: x.get('cfp_date', '') >= self.now, self.events.values())))


        self._add_events_to_series()
        self._process_videos()
        self._process_podcasts()
        self._process_events()

        self.stats['coc_future_perc']  = int(100 * self.stats['has_coc_future'] / self.stats['future'])
        self.stats['diversity_tickets_future_perc']  = int(100 * self.stats['has_diversity_tickets_future'] / self.stats['future'])
        self.stats['a11y_future_perc'] = int(100 * self.stats['has_a11y_future'] / self.stats['future'])

        return

    def generate_people_pages(self):
        env = Environment(loader=PackageLoader('cat', 'templates'))

        person_template = env.get_template('person.html')
        if not os.path.exists(self.html + '/p/'):
            os.mkdir(self.html + '/p/')
        for p in self.people.keys():
            for field in ['episodes', 'hosting']:
                if field not in self.people[p]:
                    self.people[p][field] = []
                self.people[p][field].sort(key=lambda x : x['date'], reverse=True)

            if 'name' not in self.people[p]['info']:
                exit("ERROR 6: file {} does not have a 'name' field".format(p))
            name = self.people[p]['info']['name']
            path = '/p/' + p

            with open(self.html + path + '.json', 'w', encoding="utf-8") as fh:
                fh.write(json.dumps(self.people[p], sort_keys=True))

    def generate_podcast_pages(self):
        env = Environment(loader=PackageLoader('cat', 'templates'))

        source_template = env.get_template('podcast.html')
        if not os.path.exists(self.html + '/s/'):
            os.mkdir(self.html + '/s/')
        for s in self.sources:
            try:
                with open(self.html + '/s/' + s['name'], 'w', encoding="utf-8") as fh:
                    fh.write(source_template.render(
                        podcast = s,
                        h1     = s['title'],
                        title  = s['title'],
                    ))
            except Exception as e:
                print("ERROR 7: {}".format(e))


        tag_template = env.get_template('tag.html')
        if not os.path.exists(self.html + '/t/'):
            os.mkdir(self.html + '/t/')

        self.stats['podcasts'] = len(self.sources)
        self.stats['people']   = len(self.people)
        self.stats['episodes'] = sum(len(x['episodes']) for x in self.sources)

        for r in self.redirects:
            with open(self.html + '/p/' + r['from'], 'w') as fh:
                fh.write('<meta http-equiv="refresh" content="0; url=https://codeandtalk.com/p/{}" />\n'.format(r['to']))
                fh.write('<p><a href="https://codeandtalk.com/p/{}">Moved</a></p>\n'.format(r['to']))

        #with open(self.html + '/people', 'w', encoding="utf-8") as fh:
        #    fh.write(env.get_template('people.html').render(
        #        h1      = 'List of people',
        #        title   = 'List of people',
        #        stats   = self.stats,
        #        tags    = self.tags,
        #        people = self.people,
        #        people_ids = sorted(self.people.keys()),
        #    ))
        with open(self.html + '/podcasts', 'w', encoding="utf-8") as fh:
            fh.write(env.get_template('podcasts.html').render(
                h1      = 'List of podcasts',
                title   = 'List of podcasts',
                stats   = self.stats,
                tags    = self.tags,
                podcasts = sorted(self.sources, key=lambda x: x['title']),
                people = self.people,
                people_ids = sorted(self.people.keys()),
             ))

    def save_search(self):
        for p in self.people_search:
            if 'tags' in self.people_search[p]:
                if len(self.people_search[p]['tags']) > 0:
                    self.people_search[p]['tags'] = list(self.people_search[p]['tags'])
                else:
                    del(self.people_search[p]['tags'])

        with open(self.html + '/people.json', 'w', encoding="utf-8") as fh:
            json.dump(self.people_search, fh)

        return

    def generate_pages(self):
        root = self.html
        env = Environment(loader=PackageLoader('cat', 'templates'))
        self.create_blaster_pages(root)

        self.generate_video_pages()


        videos = []
        for v in self.videos:
            vid = copy.deepcopy(v) 
            for field in ['blasters', 'description', 'tweet_video', 'file_date']:
                if field in vid:
                    del(vid[field])
            videos.append( vid )
        #with open(root + '/videos.json', 'w', encoding="utf-8") as fh:
        #    json.dump(videos, fh, sort_keys=True)


        event_template = env.get_template('event.html')
        if not os.path.exists(root + '/e/'):
            os.mkdir(root + '/e/')
        for nickname in self.events.keys():
            event = self.events[nickname]
            #print(event['nickname'])

            try:
                with open(root + '/e/' + event['nickname'], 'w', encoding="utf-8") as fh:
                    fh.write(event_template.render(
                        h1          = event['name'],
                        title       = event['name'],
                        event = event,
                ))
                self.sitemap.append({
                    'url' : '/e/' + event['nickname'],
                    'lastmod' : event['file_date'],
                })
            except Exception as e:
                print("ERROR 8: {}".format(e))


        list_template = env.get_template('list.html')

        self.sitemap.append({ 'url' : '/blasters' })
        self.sitemap.append({ 'url' : '/series', })
        self.sitemap.append({ 'url' : '/conferences' })
        self.sitemap.append({ 'url' : '/' })
        self.sitemap.append({ 'url' : '/about' })
        self.sitemap.append({ 'url' : '/all-conferences' })
        self.sitemap.append({ 'url' : '/cfp' })
        self.sitemap.append({ 'url' : '/code-of-conduct' })
        self.sitemap.append({ 'url' : '/diversity-tickets' })
        self.sitemap.append({ 'url' : '/videos' })
        for page in ['/topics', '/countries', '/cities']:
            self.sitemap.append({ 'url' : page })
        #self.sitemap.append({ 'url' : '/featured' })


        #print(topics)
        #self.save_pages(root, 't', self.tags, list_template, 'Open source conferences discussing {}')
        self.save_pages(root, 'l', self.countries, list_template, 'Open source conferences in {}')
        self.save_pages(root, 'l', self.cities, list_template, 'Open source conferences in {}')

        with open(root + '/sitemap.xml', 'w', encoding="utf-8") as fh:
            fh.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for e in self.sitemap:
                fh.write('  <url>\n')
                fh.write('    <loc>https://codeandtalk.com{}</loc>\n'.format(e['url']))
                date = self.now
                if 'lastmod' in e:
                    date = e['lastmod']
                fh.write('    <lastmod>{}</lastmod>\n'.format(date))
                fh.write('  </url>\n')
            fh.write('</urlset>\n')

    def save_pages(self, root, directory, data, list_template, title):
        my_dir =  root + '/' + directory + '/'
        if not os.path.exists(my_dir):
            os.mkdir(my_dir)

        for d in data.keys():
            #print(data[d])
            #exit()
            conferences = sorted(data[d]['events'], key=lambda x: x['start_date'])
            #print("'{}'".format(d))
            #print(my_dir + d)
            out_file = my_dir + d
            with open(out_file, 'w', encoding="utf-8") as fh:
                fh.write(list_template.render(
                    h1          = title.format(data[d]['name']),
                    title       = title.format(data[d]['name']),
                    conferences = list(filter(lambda x: x['start_date'] >= self.now, conferences)),
                    earlier_conferences = list(filter(lambda x: x['start_date'] < self.now, conferences)),
                    videos      = data[d].get('videos'),
                    episodes    = data[d].get('episodes'),
                ))
            # TODO: These are huge files. Reduce their size!
            #with open(out_file + '.json', 'w', encoding="utf-8") as fh:
            #    fh.write(json.dumps({
            #        'conferences' : conferences,
            #        'data' : data,
            #    }, sort_keys=True))
            self.sitemap.append({
                'url' : '/' + directory + '/' + d
            })

    def generate_video_pages(self):
        root = self.html 
        env = Environment(loader=PackageLoader('cat', 'templates'))
        video_template = env.get_template('video.html')
        if not os.path.exists(root + '/v/'):
            os.mkdir(root + '/v/')
        for video in self.videos:
            speaker_twitters = ''
            for s in video['speakers']:
                tw = video['speakers'][s]['info'].get('twitter')
                if tw:
                    speaker_twitters += ' @' + tw
            video['speaker_twitters'] = speaker_twitters
            if not os.path.exists(root + '/v/' + video['event']['nickname']):
                os.mkdir(root + '/v/' + video['event']['nickname'])
            #print(root + '/v/' + video['event'] + '/' + video['filename'])
            #exit()
            out_file = root + '/v/' + video['event']['nickname'] + '/' + video['filename'] + '.json'
            with open(out_file, 'w', encoding="utf-8") as fh:
                fh.write(json.dumps(video, sort_keys=True))

            self.sitemap.append({
                'url' : '/v/' + video['event']['nickname'] + '/' + video['filename'],
                'lastmod' : video['file_date'],
            })

    def check_videos(self):
        """
            Go over all the JSON files representing videos and check validity:
               - Check if they have a "recorded" field with a YYYY-MM-DD timestamp - report if not
            TODO: Check if they have values for "speakers" - report if not
            TODO: Check if they have embedded HTML in the description field (they should be moved out to a separate file)
        """

        valid_fields = ['title', 'thumbnail_url', 'tags', 'recorded', 'description', 'videos', 'speakers', 'abstract', 'slides', 'language', 'featured', 'length', 'blasters',
            'views', 'likes', 'favorite', 'skipped']
        valid_fields.extend(['filename', 'event', 'file_date']) # generated fields
        required_fields = ['title', 'recorded']
        valid_languages = ["Hebrew", "Dutch", "Spanish", "Portuguese", "German"]

        for video in self.videos:
            for f in video.keys():
                if f not in valid_fields:
                    raise Exception("Invalid field '{}' in {}".format(f, video))
            for f in required_fields:
                if f not in video:
                    raise Exception("Missing required field: '{}' in {}".format(f, video))
            if not re.search(r'^\d\d\d\d-\d\d-\d\d$', video['recorded']):
                raise Exception("Invalid 'recorded' field: {:20} in {}".format(video['recorded'], video))
            #exit(video)
            if 'language' in video:
                if video['language'] not in valid_languages:
                    raise Exception("Invalid language '{}' in video data/videos/{}/{}.json".format(video['language'], video['event'], video['filename']))
                video['title'] += ' (' + video['language'] + ')'

    def check_people(self):
        """
            Go over all the files in the data/people directory and check if all the fields are in the list of valid_fields
        """
        valid_fields = ['name', 'github', 'twitter', 'home', 'country', 'gplus', 'nickname', 'city', 'state', 'slides', 'comment', 'topics', 'description']
        for nickname in self.people.keys():
            for f in self.people[nickname]['info']:
                if f not in valid_fields:
                    raise Exception("Invlaid field '{}' in person {}".format(f, nickname))

# vim: expandtab

