# -*- coding: utf-8 -*-
# Daum Movie TV Series

import os, urllib, unicodedata, json, re, fnmatch, urlparse, time
from collections import OrderedDict

VERSION = '0.23'
DAUM_MOVIE_SRCH   = "https://suggest-bar.daum.net/suggest?id=movie&cate=movie&multiple=0&mod=json&code=utf_in_out&q=%s&_=%s"
DAUM_MOVIE_DETAIL = "http://movie.daum.net/moviedb/main?movieId=%s"
DAUM_MOVIE_CAST   = "http://movie.daum.net/data/movie/movie_info/cast_crew.json?pageNo=1&pageSize=100&movieId=%s"
DAUM_MOVIE_PHOTO  = "http://movie.daum.net/data/movie/photo/movie/list.json?pageNo=1&pageSize=100&id=%s"

DAUM_TV_SRCH      = "https://search.daum.net/search?w=tot&q=%s&rtmaxcoll=TVP"
DAUM_TV_JSON      = "https://suggest-bar.daum.net/suggest?id=movie&cate=tv&multiple=0&mod=json&code=utf_in_out&q=%s&_=%s&limit=100"
DAUM_TV_INFO      = "https://search.daum.net/search?w=tot&q=%s&irk=%s&irt=tv-program&DA=TVP"
DAUM_TV_DETAIL    = "https://search.daum.net/search?w=tv&q=%s&irk=%s&irt=tv-program&DA=TVP"

JSON_MAX_SIZE     = 10 * 1024 * 1024

DAUM_CR_TO_MPAA_CR = {
    u'전체관람가': {
        'KMRB': 'kr/A',
        'MPAA': 'G'
    },
    u'12세이상관람가': {
        'KMRB': 'kr/12',
        'MPAA': 'PG'
    },
    u'15세이상관람가': {
        'KMRB': 'kr/15',
        'MPAA': 'PG-13'
    },
    u'청소년관람불가': {
        'KMRB': 'kr/R',
        'MPAA': 'R'
    },
    u'제한상영가': {     # 어느 여름날 밤에 (2016)
        'KMRB': 'kr/X',
        'MPAA': 'NC-17'
    }
}

def Start():
    HTTP.CacheTime = CACHE_1HOUR * 12
    HTTP.Headers['Accept'] = 'text/html, application/json'
    global PLEX_LIBRARY
    PLEX_LIBRARY = GetPlexLibrary()

####################################################################################################
def searchDaumMovie(results, media, lang):
    media_name = media.name
    media_name = unicodedata.normalize('NFKC', unicode(media_name)).strip()
    microtime = str(int(time.time()*1000))
    Log.Debug("search: %s %s" %(media_name, media.year))
    data = JSON.ObjectFromURL(url=DAUM_MOVIE_SRCH % (urllib.quote(media_name.encode('utf8')), microtime))
    items = data['items']

    for item in items:
        movieinfo = item.split('|')
        year = str(movieinfo[3])
        title = String.DecodeHTMLEntities(String.StripTags(movieinfo[0])).strip()
        id = str(movieinfo[1])
        if year == media.year:
            score = 95
        elif len(items) == 1:
            score = 80
        else:
            score = 10
        Log.Debug('ID=%s, media_name=%s, title=%s, year=%s, score=%d' %(id, media_name, title, year, score))
        results.Append(MetadataSearchResult(id=id, name=title, year=year, score=score, lang=lang))

def searchDaumMovieTVSeries(results, media, lang):
# 다음에서 미디어 이름으로 검색후 결과를 보여준다
# 검색결과의 점수가 95점이면 자동 매치
# 자동 매치가 안되면 검색 결과를 보여준다.
    items = []
    score = 0
    media_name = media.show
    media_name = unicodedata.normalize('NFKC', unicode(media_name)).strip()
    Log.Debug("search: %s %s" %(media_name, media.year))

#검색결과
    html = HTML.ElementFromURL(url=DAUM_TV_SRCH % (urllib.quote(media_name.encode('utf8'))))
    try:
        year = ''
        title = html.xpath('//div[@id="tvpColl"]//div[@class="head_cont"]//a[@class="tit_info"][last()]')[0].text.strip()
        id    =   urlparse.parse_qs(html.xpath('//div[@id="tvpColl"]//div[@class="head_cont"]//a[@class="tit_info"][last()]/@href')[0].strip())['irk'][0].strip()
        year = html.xpath('//div[@class="head_cont"]//span[@class="txt_summary"][last()]')[0].text
        if year is not None:
            match = Regex('(\d{4})\.\d*\.\d*~?').search(year.strip())
            if match:
                try: year = match.group(1)
                except: year = ''
        items.append({"title":title, "id":id, "year":year})
    except:pass
#시리즈
    seriesNumber = html.xpath('count(//div[@id="tvpColl"]//div[@id="tab_content"]//div[@id="tv_series"]//ul/li/a[@class="f_link_b"])')
    for i in range(1, int(seriesNumber)+1):
        year = ''
        title = html.xpath('//div[@id="tvpColl"]//div[@id="tab_content"]//div[@id="tv_series"]//ul/li[' + str(i) + ']/a[@class="f_link_b"]')[0].text.strip()
        id    = urlparse.parse_qs(html.xpath('//div[@id="tvpColl"]//div[@id="tab_content"]//div[@id="tv_series"]//ul/li[' + str(i) + ']/a[@class="f_link_b"]/@href')[0].strip())['irk'][0].strip()
        try:
            year  = html.xpath('//div[@id="tvpColl"]//div[@id="tab_content"]//div[@id="tv_series"]//ul/li[' + str(i) + ']/span')[0].text.strip()
            match = Regex('(\d{4})\.').search(year)
            if match:
                try: year = match.group(1)
                except: year = ''
        except: pass
        items.append({"title":title, "id":id, "year":year})
#동명 콘텐츠
    sameNameNumber = html.xpath('count(//div[@id="tvpColl"]//div[@id="tv_program"]//dt[contains(.,"' + u'동명 콘텐츠' + '")]//following-sibling::dd/a[@class="f_link"])')
    for i in range(1, int(sameNameNumber)+1):
        title = html.xpath('//div[@id="tvpColl"]//div[@id="tab_content"]//dt[contains(.,"' + u'동명 콘텐츠' + '")]/following-sibling::dd/a[' + str(i) + '][@class="f_link"]')[0].text.strip()
        id   = urlparse.parse_qs(html.xpath('//div[@id="tab_content"]//dt[contains(.,"' + u'동명 콘텐츠' + '")]/following-sibling::dd/a[' + str(i) + '][@class="f_link"]/@href')[0].strip())['irk'][0].strip()
        year = ''
        try:
            year = html.xpath('//div[@id="tvpColl"]//div[@id="tab_content"]//dt[contains(.,"' + u'동명 콘텐츠' + '")]/following-sibling::dd/span[@class="f_eb"][' + str(i) + ']')[0].text.strip()
            match = Regex('(\d{4})\)').search(year)
            if match:
                try: year = match.group(1)
                except: year = ''
        except: year = ''
        items.append({"title":title, "id":id, "year":year})
    for item in items:
        year = str(item['year'])
        id = str(item['id'])
        title = item['title']
        if year == media.year:
            score = 95
        elif len(items) == 1:
            score = 80
        else:
            score = 10
        Log.Debug('ID=%s, media_name=%s, title=%s, year=%s, score=%d' %(id, media_name, title, year, score))
        results.Append(MetadataSearchResult(id=id, name=title, year=year, score=score, lang=lang))

def updateDaumMovie(metadata):
    poster_url = None
    #Set Movie basic metadata
    try:
        html = HTML.ElementFromURL(DAUM_MOVIE_DETAIL % metadata.id)
        title = html.xpath('//div[@class="subject_movie"]/strong')[0].text
        match = Regex('(.*?) \((\d{4})\)').search(title)
        metadata.title = match.group(1)
        metadata.year = int(match.group(2))
        metadata.original_title = html.xpath('//span[@class="txt_movie"]')[0].text
        metadata.rating = float(html.xpath('//div[@class="subject_movie"]/a/em')[0].text)
        # 장르
        metadata.genres.clear()
        dds = html.xpath('//dl[contains(@class, "list_movie")]/dd')
        for genre in dds.pop(0).text.split('/'):
            metadata.genres.add(genre)
        # 나라
        metadata.countries.clear()
        for country in dds.pop(0).text.split(','):
            metadata.countries.add(country.strip())
        # 개봉일 (optional)
        match = Regex(u'(\d{4}\.\d{2}\.\d{2})\s*개봉').search(dds[0].text)
        if match:
            metadata.originally_available_at = Datetime.ParseDate(match.group(1)).date()
            dds.pop(0)
        # 재개봉 (optional)
        match = Regex(u'(\d{4}\.\d{2}\.\d{2})\s*\(재개봉\)').search(dds[0].text)
        if match:
            dds.pop(0)
        # 상영시간, 등급 (optional)
        match = Regex(u'(\d+)분(?:, (.*?)\s*$)?').search(dds.pop(0).text)
        if match:
            metadata.duration = int(match.group(1))
            cr = match.group(2)
            if cr:
                match = Regex(u'미국 (.*) 등급').search(cr)
                if match:
                    metadata.content_rating = match.group(1)
                elif cr in DAUM_CR_TO_MPAA_CR:
                    metadata.content_rating = DAUM_CR_TO_MPAA_CR[cr]['MPAA' if Prefs['use_mpaa'] else 'KMRB']
                else:
                    metadata.content_rating = 'kr/' + cr
        metadata.summary = "\n".join(txt.strip() for txt in html.xpath('//div[@class="desc_movie"]/p//text()'))
        poster_url = html.xpath('//img[@class="img_summary"]/@src')[0]
    except Exception, e:
        Log.Debug(repr(e))
        pass
    #Get Acotrs & Crew Info
    directors = []
    producers = []
    writers = []
    roles = []
    data = JSON.ObjectFromURL(url=DAUM_MOVIE_CAST % metadata.id)
    for item in data['data']:
        cast = item['castcrew']
        if cast['castcrewCastName'] in [u'감독', u'연출']:
            director = dict()
            director['name'] = item['nameKo'] if item['nameKo'] else item['nameEn']
            if item['photo']['fullname']:
                director['photo'] = item['photo']['fullname']
            directors.append(director)
        elif cast['castcrewCastName'] == u'제작':
            producer = dict()
            producer['name'] = item['nameKo'] if item['nameKo'] else item['nameEn']
            if item['photo']['fullname']:
                producer['photo'] = item['photo']['fullname']
            producers.append(producer)
        elif cast['castcrewCastName'] in [u'극본', u'각본']:
            writer = dict()
            writer['name'] = item['nameKo'] if item['nameKo'] else item['nameEn']
            if item['photo']['fullname']:
                writer['photo'] = item['photo']['fullname']
            writers.append(writer)
        elif cast['castcrewCastName'] in [u'주연', u'조연', u'출연', u'진행']:
            role = dict()
            role['role'] = cast['castcrewTitleKo']
            role['name'] = item['nameKo'] if item['nameKo'] else item['nameEn']
            if item['photo']['fullname']:
                role['photo'] = item['photo']['fullname']
            roles.append(role)
    #Set Crew Info
    if directors:
        metadata.directors.clear()
        for director in directors:
            meta_director = metadata.directors.new()
            if 'name' in director:
                meta_director.name = director['name']
            if 'photo' in director:
                meta_director.photo = director['photo']
    if producers:
        metadata.producers.clear()
        for producer in producers:
            meta_producer = metadata.producers.new()
            if 'name' in producer:
                meta_producer.name = producer['name']
            if 'photo' in producer:
                meta_producer.photo = producer['photo']
    if writers:
        metadata.writers.clear()
        for writer in writers:
            meta_writer = metadata.writers.new()
            if 'name' in writer:
                meta_writer.name = writer['name']
            if 'photo' in writer:
                meta_writer.photo = writer['photo']

    #Set Acotrs Info
    if roles:
        metadata.roles.clear()
        for role in roles:
            meta_role = metadata.roles.new()
            if 'role' in role:
                meta_role.role = role['role']
            if 'name' in role:
                meta_role.name = role['name']
            if 'photo' in role:
                meta_role.photo = role['photo']

    #Get Photo
    data = JSON.ObjectFromURL(url=DAUM_MOVIE_PHOTO % metadata.id)
    max_poster = int(Prefs['max_num_posters'])
    max_art = int(Prefs['max_num_arts'])
    idx_poster = 0
    idx_art = 0
    for item in data['data']:
        if item['photoCategory'] == '1' and idx_poster < max_poster:
            art_url = item['fullname']
            if not art_url: continue
            idx_poster += 1
            try: metadata.posters[art_url] = Proxy.Preview(HTTP.Request(item['thumbnail']), sort_order = idx_poster)
            except: pass
        elif item['photoCategory'] in ['2', '50'] and idx_art < max_art:
            art_url = item['fullname']
            if not art_url: continue
            idx_art += 1
            try: metadata.art[art_url] = Proxy.Preview(HTTP.Request(item['thumbnail']), sort_order = idx_art)
            except: pass
    Log.Debug('Total %d posters, %d artworks' %(idx_poster, idx_art))
    if idx_poster == 0:
        if poster_url:
            poster = HTTP.Request( poster_url )
            try: metadata.posters[poster_url] = Proxy.Media(poster)
            except: pass

def updateDaumMovieTVSeries(metadata, media):
    poster_url = None
    season_num_list = []
    series_data= []
    airdate = None
    tvshowinfo = None
    actors = []
    episodeinfos = []
    html = ''
    for season_num in media.seasons:
        season_num_list.append(season_num)
    if '0' in season_num_list:
        season_num_list.remove('0')
    season_num_list.sort(key=int)
    microtime = str(int(time.time()*1000))
    data = JSON.ObjectFromURL(url=DAUM_TV_JSON % (urllib.quote(media.title.encode('utf8')), microtime))
    items = data['items']
    for item in items:
        title, id, poster, year, rating = item.split('|')
        if id == metadata.id :
            html = HTML.ElementFromURL(DAUM_TV_DETAIL % (urllib.quote(title.encode('utf8')), metadata.id))
    
    if html.xpath('//div[@id="tvpColl"]//div[@class="tit_program"]/strong'):
        title = html.xpath('//div[@id="tvpColl"]//div[@class="tit_program"]/strong')[0].text.strip()
        tvinfo = HTML.ElementFromURL(DAUM_TV_INFO % (urllib.quote(title.encode('utf8')), metadata.id))
        #Set TV SHOW
        if tvinfo.xpath('//div[@class="head_cont"]//span[@class="txt_summary"][last()]')[0].text is not None:
            match = Regex('(\d{4}(\.\d{1,2})?(\.\d{1,2})?)~?(\d{4}\.\d{1,2}\.\d{1,2})?').search(tvinfo.xpath('//div[@class="head_cont"]//span[@class="txt_summary"][last()]')[0].text.strip())
            if match:
                try: airdate = Datetime.ParseDate(match.group(1), '%Y%m%d').date().strftime('%Y-%m-%d')
                except: airdate = None
        series_data.append({"airdate":airdate, "q":title, "irk":metadata.id})
        seriesNumber = html.xpath('count(//div[@id="tvpColl"]//div[@id="series"]/ul/li/a/text())')
        for i in range(1, int(seriesNumber)+1):
            airdate = None
            qs = urlparse.parse_qs(html.xpath('//div[@id="tvpColl"]//div[@id="series"]/ul/li[' + str(i) + ']/a/@href')[0].strip())
            try:
                match = Regex('(\d{4}(\.?\d{1,2})?)').search(html.xpath('//div[@id="tvpColl"]//div[@id="series"]/ul/li[' + str(i) + ']/span')[0].text.strip())
                if match:
                    try: airdate = Datetime.ParseDate(match.group(1), '%Y.%m').date().strftime('%Y-%m-%d')
                    except: airdate = None
            except:pass
            series_data.append({"airdate":airdate, "q": qs['q'][0].decode('utf8'), "irk": qs['irk'][0]})
        series_data = sorted(series_data, key=lambda k: (k['airdate'] is None, k['airdate']))
        for season_num in media.seasons:
            season_num_list.append(season_num)
        if '0' in season_num_list:
            season_num_list.remove('0')
        season_num_list.sort(key=int)

        if len(season_num_list) !=1 :
            tvshowinfo = series_data[0]
        else :
            tvshowinfo = series_data[0]
            for i in series_data:
                if i['irk'] == metadata.id:
                    tvshowinfo = i
    #TV show 메타정보가지고 오기
    pageUrl = "http://127.0.0.1:32400/library/metadata/" + media.id + "/tree"
    metadatatitlejson = JSON.ObjectFromURL(pageUrl)
    metadatatitle = metadatatitlejson['MediaContainer']['MetadataItem'][0]['title']
    try:
        #html = HTML.ElementFromURL(DAUM_TV_DETAIL % (urllib.quote(metadatatitle.encode('utf8')), metadata.id))
        
        #if html.xpath('//div[@id="tvpColl"]//div[@class="tit_program"]/strong'):
        if series_data:
            if len(season_num_list) !=1 :
                tvshowinfo = series_data[0]
            else :
                tvshowinfo = series_data[0]
                for i in series_data:
                    if i['irk'] == metadata.id:
                        tvshowinfo = i
            title, poster_url, airdate, studio, genres, summary = GetTvshow(tvshowinfo)
            metadata.genres.clear()
            metadata.countries.clear()
            metadata.roles.clear()
            try: metadata.title = title
            except: passs
            try: metadata.studio = studio
            except: pass
            try: metadata.originally_available_at = airdate
            except: pass
            try: metadata.genres.add(genres)
            except: pass
            try: metadata.summary = summary
            except: pass
            try:
                if poster_url:
                   poster = HTTP.Request(poster_url)
                   try: metadata.posters[poster_url] = Proxy.Preview(poster)
                   except: pass
            except: pass 

            #Set Season
            # 시즌 메타정보 업데이트
            # 시즌 요약정보는 버그인지 업데이트가 되지 않는다.
            # 포스터 정보만 업데이트
            # 특별편에 대한 정보는 JSON파일로 처리하도록 하였다.
            # 시즌이 반영안되는 경우 포스터는 tvshow 포스터 사용

            for season_num in season_num_list:
                if int(seriesNumber)+1 !=1 :
                    try: season_info = series_data[int(season_num)-1]
                    except: season_info = None
                else:
                    season_info = tvshowinfo
                if season_info is None:
                    if len(series_data) == 1:
                        season = metadata.seasons[season_num]
                        try:
                            if poster_url:
                                poster = HTTP.Request(poster_url)
                                try: season.posters[poster_url] = Proxy.Preview(poster)
                                except: pass
                        except: pass
                else:
                    season = metadata.seasons[season_num]
                    poster_url, directors, producers, writers, actors, episodeinfos = GetSeason(season_info)
                    try:
                        if poster_url:
                            poster = HTTP.Request(poster_url)
                            try: season.posters[poster_url] = Proxy.Preview(poster)
                            except: pass
                    except: pass
            #Set Actor
                for actor in actors:
                    meta_role = metadata.roles.new()
                    meta_role.name  = actor['name']
                    meta_role.role  = actor['role']
                    meta_role.photo = actor['photo']
            #Set Episode
            # 에피소드 타이틀이 없거나(신규 또는 개별 메타데이터 갱신) 방영일이 3주 이내인 경우
            # 에피소드 데이터를 업데이트
                for episodeinfo in episodeinfos:
                    episode_num = ''
                    if  episodeinfo['name'] and int(episodeinfo['name']) in media.seasons[season_num].episodes:
                        episode_num = int(episodeinfo['name'])
                    elif episodeinfo['date'] in media.seasons[season_num].episodes:
                        episode_num = episodeinfo['date']
                    if episode_num:
                        episode = metadata.seasons[season_num].episodes[episode_num]
                        try: airdate = Datetime.ParseDate(episodeinfo['date']).date()
                        except:  airdate = Datetime.Now().date()
                        dt = Datetime.Now().date() - airdate

                        if episode.title is None or dt.days < 21:
                            Log.Info('Update season_num = %s  episode_num = %s by method 1' %(season_num, episode_num))
                            episode_date, episode_title, episode_summary = GetEpisode(episodeinfo)
                            try: episode.title = episode_title
                            except: pass
                            try:  episode.summary = episode_summary.strip()
                            except: pass
                            if episode_date is not None and episode_num != episode_date.strftime('%Y-%m-%d'):
                                try: episode.originally_available_at = episode_date
                                except: pass
                            episode.rating = None
                            #감독, 제작, 각본  메타정보 업데이트
                            for director in directors:
                                episode_director = episode.directors.new()
                                try: episode_director.name = director['name']
                                except: pass
                                try: episode_director.photo = director['photo']
                                except: pass
                            for producer in producers:
                                episode_producer = episode.producers.new()
                                try: episode_producer.name = producer['name']
                                except: pass
                                try: episode_producer.photo = producer['photo']
                                except: pass
                            for writer in writers:
                                episode_writer = episode.writers.new()
                                try: episode_writer.name = writer['name']
                                except: pass
                                try: episode_writer.photo = writer['photo']
                                except: pass

                if len(episodeinfos) :                                
                #회차정보는 검색하면 존재하나 회차정보에 없을 경우
                    for episode_num in media.seasons[season_num].episodes:
                        episode = metadata.seasons[season_num].episodes[episode_num]
                        if episode.title is None:
                            if episode_num.isdigit(): q = media.title+str(episode_num)+u'회'
                            else : q = media.title+str(episode_num)
                            episodeinfo = {"name": str(episode_num), "date":'', "q": q, "irk":''}
                            Log.Info('Update season_num = %s  episode_num = %s by method 2' %(season_num, episode_num))
                            episode_date, episode_title, episode_summary = GetEpisode(episodeinfo)
                            try: episode.title = episode_title
                            except: pass
                            try:  episode.summary = episode_summary.strip()
                            except: pass
                            if episode_date is not None and episode_num != episode_date.strftime('%Y-%m-%d'):
                                try: episode.originally_available_at = episode_date
                                except: pass
                            episode.rating = None
                            #감독, 제작, 각본  메타정보 업데이트
                            for director in directors:
                                episode_director = episode.directors.new()
                                try: episode_director.name = director['name']
                                except: pass
                                try: episode_director.photo = director['photo']
                                except: pass
                            for producer in producers:
                                episode_producer = episode.producers.new()
                                try: episode_producer.name = producer['name']
                                except: pass
                                try: episode_producer.photo = producer['photo']
                                except: pass
                            for writer in writers:
                                episode_writer = episode.writers.new()
                                try: episode_writer.name = writer['name']
                                except: pass
                                try: episode_writer.photo = writer['photo']
                                except: pass

        GetJson(metadata, media)            
    except Exception, e:
        Log.Debug(repr(e))
        pass

def GetTvshow(info):
    title = ''
    poster_url = None
    airdate = None
    studio = ''
    genres = ''
    summary = ''
    html = HTML.ElementFromURL(DAUM_TV_INFO % (urllib.quote(info['q'].encode('utf8')), info['irk']))
    title = html.xpath('//div[@id="tvpColl"]//div[@class="head_cont"]//a[@class="tit_info"][last()]')[0].text.strip()
    #match = re.search('(.*) 시즌(\d{1,2})', title.encode('utf-8'))
    #if match:
    #    title = match.group(1)
    poster_url =  urlparse.parse_qs(urlparse.urlparse(html.xpath('//div[@id="tv_program"]/div[@class="info_cont"]/div[@class="wrap_thumb"]/a/img/@src')[0].strip()).query)['fname'][0]
    if html.xpath('//div[@class="head_cont"]//span[@class="txt_summary"][last()]')[0].text is not None:
        match = Regex('(\d{4}(\.\d{1,2})?(\.\d{1,2})?)~?(\d{4}\.\d{1,2}\.\d{1,2})?').search(html.xpath('//div[@class="head_cont"]//span[@class="txt_summary"][last()]')[0].text.strip())
        if match:
            try: airdate = Datetime.ParseDate(match.group(1), '%Y%m%d').date().strftime('%Y-%m-%d')
            except: airdate = None
    try: studio = html.xpath('//div[@class="head_cont"]/div[@class="summary_info"]/a')[0].text.strip()
    except: pass
    try: genres = html.xpath('//div[@class="head_cont"]/div[@class="summary_info"]/span[@class="txt_summary"][1]')[0].text.strip().split('(')[0].strip()
    except: pass
    try: summary = html.xpath('//div[@id="tv_program"]/div[@class="info_cont"]/dl[@class="dl_comm dl_row"][1]/dd[@class="cont"]')[0].text.strip()
    except: pass
    return title, poster_url, airdate, studio, genres, summary
 
def GetSeason(info):
    poster_url = None
    directors = []
    producers = []
    writers = []
    actors = []
    episodeinfos = []
    html = HTML.ElementFromURL(DAUM_TV_DETAIL % (urllib.quote(info['q'].encode('utf8')), info['irk']))
    poster_url =  urlparse.parse_qs(urlparse.urlparse(html.xpath('//div[@id="tvpColl"]//div[@class="info_cont"]/div[@class="wrap_thumb"]//img/@src')[0].strip()).query)['fname'][0]
    for crewinfo in html.xpath('//div[@id="tvpColl"]//div[@class="wrap_col lst"]/ul/li[@data-index]'):
        try:
            if crewinfo.xpath('./span[@class="txt_name"]/a'):
                name = crewinfo.xpath('./span[@class="txt_name"]/a')[0].text.strip()
            else:
                name = crewinfo.xpath('./span[@class="txt_name"]')[0].text.strip()
            sub_name = crewinfo.xpath('./span[@class="sub_name"]')[0].text.strip().replace(u'이전', '').strip()
            try: photo = urlparse.parse_qs(urlparse.urlparse(crewinfo.xpath('./div/a/img/@src')[0].strip()).query)['fname'][0]
            except: photo = ''
            if sub_name in [u'감독', u'연출', u'기획']:
                directors.append({"name":name, "photo":photo})
            elif sub_name in [u'제작', u'프로듀서', u'책임프로듀서']:
                producers.append({"name":name, "photo":photo})
            elif sub_name in [u'극본', u'각본']:
                writers.append({"name":name, "photo":photo})
        except: pass
    for actorinfo in html.xpath('//div[@id="tvpColl"]//div[@class="wrap_col castingList"]/ul/li[@data-index]'):
        try:
            if actorinfo.xpath('./span[@class="txt_name"]/a'):
                name = actorinfo.xpath('./span[@class="txt_name"]/a')[0].text.strip()
            else:
                name = actorinfo.xpath('./span[@class="txt_name"]')[0].text.strip()
            if actorinfo.xpath('./span[@class="sub_name"]/a'): 
                sub_name = actorinfo.xpath('./span[@class="sub_name"]/a')[0].text.strip().replace(u'이전', '').strip()
            else:
                sub_name = actorinfo.xpath('./span[@class="sub_name"]')[0].text.strip().replace(u'이전', '').strip()
            try: photo = urlparse.parse_qs(urlparse.urlparse(actorinfo.xpath('./div/a/img/@src')[0].strip()).query)['fname'][0]
            except: photo = ''
            if sub_name in [u'출연', u'특별출연', u'진행', u'내레이션', u'심사위원', u'고정쿠르', u'쿠르', u'고정게스트']:
                role = sub_name
                actors.append({"name":name, "role":role, "photo":photo})
            else:
                role = name
                name = sub_name
                actors.append({"name":name, "role":role, "photo":photo})
        except: pass
    for episodeinfo in html.xpath('//div[@id="tvpColl"]//ul[@id="clipDateList"]/li') :
        try:episode_date = Datetime.ParseDate(episodeinfo.attrib['data-clip']).date().strftime('%Y-%m-%d')
        except:episode_date = ''
        episode_qs = urlparse.parse_qs(episodeinfo.xpath('./a/@href')[0])
        try:episode_name = episodeinfo.xpath('./a/span[@class="txt_episode"]')[0].text.strip().replace(u'회','').strip()
        except:episode_name = ''
        episodeinfos.append({"name": episode_name, "date":episode_date, "q":episode_qs['q'][0], "irk":episode_qs['irk'][0]})
    return poster_url, directors, producers, writers, actors, episodeinfos

def GetEpisode(info):
    title = None
    airdate = None
    summary = None

    #다음 서버에 부담을 줄이기 위해서 에피소드 가져오는 시간을 2로 제한
    if info['irk'] :
        html = HTML.ElementFromURL(DAUM_TV_DETAIL % (urllib.quote(info['q'].encode('utf8')), info['irk']), sleep=2)
    else:
        html = HTML.ElementFromURL(DAUM_TV_DETAIL.replace('irk=%s&','') % urllib.quote(info['q'].encode('utf8')), sleep=2)
    try:
        match = Regex('(\d{4}\.\d{1,2}\.\d{1,2})').search(html.xpath('//div[@id="tvpColl"]//span[1][contains(@class, "txt_date")]/text()')[0].strip())
        if match:
            try: airdate = Datetime.ParseDate(match.group(1), '%Y%m%d').date()
            except: 
               if info['date']:
                   airdate = Datetime.ParseDate(info['date']).date()
               else: airdate = None
    except: airdate = None
    try: title  = html.xpath('//div[@id="tvpColl"]//p[@class="episode_desc"]/strong/text()')[0].strip()
    except:
        if airdate is not None: 
            title = airdate.strftime('%Y-%m-%d')
        else: title = None
    try: summary = '\n'.join(line.strip() for line in html.xpath('//div[@id="tvpColl"]//p[@class="episode_desc"]/text()[name(.)!="strong"]'))
    except: summary = None
    return airdate, title, summary

def GetJson(metadata, media):
# Root 폴더에 tvhow JSON 파일이 있는지 확인
# tvshow JSON 파일은 Root 폴더와 동일한 이름.json
# tvshow JSON 파일이 있으면 tvshow 메타정보 JSON파일 내용으로 업데이트
    root, current_folder = GetCurrentFolder(PLEX_LIBRARY, media.id)
    jsonfiles = []
    dirs = []
    for dirpaths, dirnames, files in os.walk(os.path.join(root, current_folder)):
        for filename in files:
            if filename.endswith(('.json')):
                jsonfile =  os.path.join(dirpaths, filename).decode('utf-8')
                jsonfiles.append(jsonfile)
        dirs.append(dirpaths.decode('utf-8'))

    tvshowfile = current_folder + '.json'
    tvshowfile = os.path.join(root, current_folder, tvshowfile)
    tvshowfile = unicodedata.normalize('NFKC', unicode(tvshowfile)).strip()

    if os.path.exists(tvshowfile):
        Log.Info("Update TV Show Metadata " + tvshowfile)
        tvshowdata = json.loads(Core.storage.load(tvshowfile))
        try: metadata.title = tvshowdata['title'].strip()
        except: pass
        try: metadata.original_title = tvshowdata['original_title'].strip()
        except: pass
        try: metadata.rating = float(tvshowdata['rating'].strip())
        except: pass
        try: metadata.studio = tvshowdata['studio'].strip()
        except: pass
        try: metadata.summary = tvshowdata['summary'].strip()
        except: pass
        try: metadata.year = tvshowdata['year'].strip()
        except: pass
        try: metadata.originally_available_at = Datetime.ParseDate(tvshowdata['originally_available_at'].strip()).date()
        except: pass
        try:
            poster_url = None
            poster_url = tvshowdata['poster'].strip()
            if poster_url:
                poster = HTTP.Request(poster_url)
                try: metadata.posters[poster_url] = Proxy.Preview(poster)
                except: pass
        except: pass
        try:
            for genre in tvshowdata['genres']:
                 metadata.genres.add(genre.strip())
        except: pass
        try:
            for country in tvshowdata['countries']:
                metadata.countries.add(country.strip())
        except: pass
    #시즌별 JSON 파일이 있으면 메타정보 업데이트
    #시즌 JSON 파일은 각각의 시즌 폴더에 위치
    #파일명은
    #Root 폴더명 시즌 1.json(시즌 01, 시즌01, 시즌001 등 가능)
    #Root 폴더명 season 1.json(season1, Season 01 등 가능)
    for season_num in media.seasons:
        if season_num == '0' :
            pattern = ur'(특별편|Special)$'
            #pattern = pattern.decode('utf-8')
            regex = re.compile(pattern)
        else :
            pattern = ur'(시즌|Season).*\b0*?{}\b$'
            #pattern = pattern.decode('utf-8')
            regex = re.compile(pattern.format(str(season_num)))

        season_dir = filter(regex.search, dirs)
        if len(media.seasons) == 1:
            seasonpath = os.path.dirname(tvshowfile)
            seasonfile = tvshowfile
        else:
            try:
                seasonpath = season_dir[0]
                seasonfile = os.path.basename(seasonpath) + '.json'
                seasonfile = os.path.join(seasonpath, seasonfile)
                seasonfile = unicodedata.normalize('NFKC', unicode(seasonfile)).strip()
            except:
                seasonpath = os.path.dirname(tvshowfile)
                seasonfile = ''

        #시즌 메타정보 업데이트
        if os.path.exists(seasonfile):
            seasondata = json.loads(Core.storage.load(seasonfile))
            if len(media.seasons) != 1:
                Log.Info("Update TV Season Metadata " + seasonfile)
                season = metadata.seasons[season_num]
                try:  season.summary = seasondata['summary'].strip()
                except: pass
                try:
                    poster_url = None
                    poster_url = seasondata['poster'].strip()
                    if poster_url:
                        poster = HTTP.Request(poster_url)
                        try: season.posters[poster_url] = Proxy.Preview(poster)
                        except: pass
                except: pass

            #출연진 정보 가져오기
            try:
                for actor in seasondata['roles']:
                    meta_role = metadata.roles.new()
                    meta_role.name  = actor['name']
                    meta_role.role  = actor['role']
                    meta_role.photo = actor['photo']
            except: pass

        #에피소드 메타정보 업데이트
        pattern = ur'(특별편|Special)\.json$'
        #pattern = pattern.decode('utf-8')
        for dirpaths, dirnames, files in os.walk(seasonpath):
            for filename in files:
                if filename.endswith(('.json')):
                    episodefile = os.path.join(dirpaths, filename)
                    episodefile = unicodedata.normalize('NFKC', unicode(episodefile)).strip()
                    checkspecial = re.search(pattern, episodefile)
                    if checkspecial and int(season_num) !=  0: continue
                    if os.path.exists(episodefile):
                        episode_json_data = json.loads(Core.storage.load(episodefile))
                        if 'episodes' in episode_json_data:
                            Log.Info("Update TV Episode Metadata " + episodefile)
                            for episodedata in episode_json_data['episodes']:
                                episode_num = ''
                                episode_date = Datetime.ParseDate(episodedata['broadcastDate'], '%Y%m%d').date().strftime('%Y-%m-%d')
                                if  episodedata['name'] and  int(episodedata['name']) in media.seasons[season_num].episodes:
                                    episode_num = int(episodedata['name'])
                                elif episode_date in media.seasons[season_num].episodes:
                                    episode_num = episode_date
                                if episode_num:
                                    episode = metadata.seasons[season_num].episodes[episode_num]
                                    try: episode.title = episodedata['title'].strip()
                                    except: pass
                                    try: episode.summary = episodedata['introduceDescription'].strip()
                                    except: pass
                                    if  episode_num != episode_date:
                                        try: episode.originally_available_at = Datetime.ParseDate(episode_date, '%Y%m%d').date()
                                        except: pass
                                    #감독, 각본  메타정보 업데이트
                                    if 'directors' in episode_json_data:
                                        episode.directors.clear()
                                        for director in episode_json_data['directors']:
                                            episode_director = episode.directors.new()
                                            try: episode_director.name = director['name']
                                            except: pass
                                            try: episode_director.photo = director['photo']
                                            except: pass
                                    if 'producers' in episode_json_data:
                                        episode.producers.clear()
                                        for producer in episode_json_data['producers']:
                                            episode_producer = episode.producers.new()
                                            try: episode_producer.name = producer['name']
                                            except: pass
                                            try: episode_producer.photo = producer['photo']
                                            except: pass
                                    if 'writers' in episode_json_data:
                                        episode.writers.clear()
                                        for writer in episode_json_data['writers']:
                                            episode_writer = episode.writers.new()
                                            try: episode_writer.name = writer['name']
                                            except: pass
                                            try: episode_writer.photo = writer['photo']
                                            except: pass

def GetPlexLibrary():
    PLEX_LIBRARY = []
    PLEX_LIBRARY_URL = 'http://127.0.0.1:32400/library/sections'
    library_json = JSON.ObjectFromURL(PLEX_LIBRARY_URL)
    for library in library_json['MediaContainer']['Directory']:
        for path in library['Location']:
            PLEX_LIBRARY.append(path['path'])
    return PLEX_LIBRARY

def GetCurrentFolder(PLEX_LIBRARY, id):
    current_folder = ''
    pageUrl = "http://127.0.0.1:32400/library/metadata/" + id + "/tree"
    filejson = JSON.ObjectFromURL(pageUrl)
    filepath = filejson['MediaContainer']['MetadataItem'][0]['MetadataItem'][0]['MetadataItem'][0]['MediaItem'][0]['MediaPart'][0]['file'].encode('utf-8')
    for root in [os.sep.join(filepath.split(os.sep)[0:x+2]) for x in range(0, filepath.count(os.sep))]:
        if root in PLEX_LIBRARY:
             path = os.path.relpath(filepath, root)
             current_folder = path.split(os.sep)[0]
             break;
    return root, current_folder;

####################################################################################################
class DaumMovieAgent(Agent.Movies):
    name = "Daum Movie TV Series"
    languages = [Locale.Language.Korean]
    primary_provider = True
    accepts_from = ['com.plexapp.agents.localmedia']

    def search(self, results, media, lang, manual=False):
        return searchDaumMovie(results, media, lang)

    def update(self, metadata, media, lang):
        updateDaumMovie(metadata)

class DaumMovieTVSeriesAgent(Agent.TV_Shows):
    name = "Daum Movie TV Series"
    primary_provider = True
    languages = [Locale.Language.Korean]
    accepts_from = ['com.plexapp.agents.localmedia']

    def search(self, results, media, lang, manual=False):
        return searchDaumMovieTVSeries(results, media, lang)

    def update(self, metadata, media, lang):
        updateDaumMovieTVSeries(metadata, media)

