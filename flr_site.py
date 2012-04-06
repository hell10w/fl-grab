#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys
#import time
import datetime

from elixir import session
from grab import Grab
from grab.spider import Spider, Task
#from lxml.objectify import fromstring

import options
import model


class FreeLanceRu(Spider):
    PROJECT_BY_PID = 'http://www.free-lance.ru/projects/?pid=%d'
    INDEX_BY_PAGE = 'http://www.free-lance.ru/?page=%d'

    def __init__(self, pages_count=5, *args, **kwargs):
        self.pages_count = pages_count
        super(FreeLanceRu, self).__init__(*args, **kwargs)

    def prepare(self):
        headers = {
                 'Accept-Charset': 'utf-8',
                 'User-Agent': 'Googlebot/2.1 (+http://www.google.com/bot.html)'
            }
        self.grab = Grab()
        self.grab.setup(headers=headers)

    def get_grab(self, url=None):
        grab = self.grab.clone()
        if url:
            grab.setup(url=url)
        return grab

    def get_task(self, **kwargs):
        url = None
        if 'url' in kwargs:
            url = kwargs['url']
            del kwargs['url']
        grab = self.get_grab(url=url)
        return Task(
                grab=grab,
                **kwargs
            )

    def task_generator(self):
        for index in range(self.pages_count):
            yield self.get_task(
                    name='page',
                    url=FreeLanceRu.INDEX_BY_PAGE % (index + 1)
                )

    def task_page(self, grab, task):
        pids = grab.xpath_list('//a[starts-with(@id, "prj_name_")]/@id')
        pids = map(lambda item: int(item.split('_')[-1]), pids)
        for pid in pids:
            url = FreeLanceRu.PROJECT_BY_PID % (pid)
            if model.Project.query.filter_by(url=url).first():
                continue
            yield self.get_task(
                    name='project',
                    pid=pid,
                    url=url
                )

    def task_project(self, grab, task):
        url = FreeLanceRu.PROJECT_BY_PID % (task.pid)

        if grab.xpath_exists('//*[@class="contest-view"]'):
            #print u'%s - конкурс' % (url)
            return 
        if grab.xpath_exists('//*[@class="pay-prjct"]'):
            #print u'%s - платный проект' % (url)
            return

        project = {}

        project['url'] = url

        name = grab.xpath('//h1[@class="prj_name"]/text()')
        name = name.strip().encode('utf-8')
        project['name'] = name 

        date = grab.xpath('//*[@class="user-about-r"]/p/text()')
        date = date.split('[', 1)[0]
        date = date.strip().encode('utf-8')
        date = datetime.datetime.strptime(
                date,
                "%d.%m.%Y | %H:%M"
            )
        project['date'] = date

        category = grab.xpath_list('//p[@class="crumbs"]/a/text()')
        if not category:
            category = grab.xpath('//p[@class="crumbs"]/text()')
            category = category.split(': ', 1)[1]
            category = category.split(', ', 1)[0]
            category = category.split(' / ')
            category = map(lambda a: a.strip().encode('utf-8'), category)
        project['category'] = category

        description = grab.xpath('//*[@class="prj_text"]/text()')
        description = description.encode('utf-8')
        project['description'] = description

        self.check_project(project)

    def check_project(self, project):
        if model.Project.query.filter_by(url=project['url']).first():
            return
        category = self.get_category(project['category'])
        if not category:
            print 'Ошибка: для проекта %s не найдена категория "%s"' % (
                    project['url'],
                    '<'.join(project['category'])
                )
            return
        model.Project(
                name=project['name'],
                url=project['url'],
                description=project['description'],
                category=category,
                date=project['date'],
                site=model.free_lance_ru
            )
        session.commit()

    def get_category(self, path):
        path.reverse()
        category = None
        while len(path):
            category = model.Category.query.filter_by(
                    name=path.pop(),
                    parent=category,
                    site=model.free_lance_ru
                )
            category = category.first()
        return category

freelanceru = FreeLanceRu(pages_count=5, thread_number=5)
freelanceru.run()

sys.exit()
