#!/usr/bin/python

from ganttchart import chart, task, category, render
import re, logger, datetime
from wikiapi import xmlrpc
from utils import *

colors = [
        "#00CCFF", "#CCFFFF", "#CCFFCC", "#FFFF99",  
        "#99CCFF", "#FF99CC", "#CC99FF", "#FFCC99",  
        "#3366FF", "#33CCCC", "#99CC00", "#FFCC00",
        "#FF9900", "#FF6600", "#666699", "#969696",  
        "#003300", "#339966", "#003300", "#333300",  
        "#993300", "#993366", "#333399", "#333333"]

predefined = {"Bench": "#FF8080", "Vacation": "#D0D0D0"}
categories = {}
color_index = 0
    
def remove_non_ascii(s):
    return "".join(i for i in s if ord(i) < 128)

def get_category(name):
    global color_index

    if name not in categories:
        if name in predefined:
            color = predefined[name]
        else:
            color = colors[color_index]
            color_index += 1
        categories[name] = category.Category(name, color)
    return categories[name]

def parse_table(page, table_title, chart):
    pattern = re.compile("{csv[^}]+id=%s}([^{]*){csv}" % table_title)
    found = pattern.search(page)
    if found:
        now = datetime.date.today()
        table = found.group(1)
        owners = {}
        max_date = datetime.date.min
        for line in remove_non_ascii(table).split("\n"):
            LOGGER.debug(line)
            try:
                (cat, pool, owner, from_date, till_date) = line.split(",")
            except:
                LOGGER.error("Unable to parse line: %s" % line)
                continue
            if cat == "Category":
                continue
            cat = get_category(cat)
            pool = pool.strip()
            owner = owner.strip()
            
            if owner not in owners.keys():
                owners[owner] = {"counter": 0, "last_date": datetime.date.min, "pool": pool}
            owner_data = owners[owner]    

            t = task.Task("", cat, pool, owner, from_date, till_date)
            if t.till_date > max_date:
                max_date = t.till_date

            if t and t.till_date >= now:
                chart.tasks.append(t)
                owner_data["counter"] += 1

            if t.till_date > owner_data["last_date"]:
                owner_data["last_date"] = t.till_date

        for o in owners:
            data = owners[o]
            if data["counter"]:
                continue
            chart.tasks.append(task.Task("", get_category("Bench"), data["pool"], o, 
                data["last_date"] + datetime.timedelta(days = 1), max_date))
                

def replace_table(page, table_title, chart):
    pattern = re.compile("{csv[^}]+id=%s}([^{]*){csv}" % table_title)
    s = "{csv:output=wiki|id=%s}\nCategory, Pool, Owner, Start, End\n" % table_title
    for t in sorted(chart.tasks):
        s += t.to_csv() + "\n"
    s += "{csv}"

    return pattern.sub(s, page)

if __name__ == "__main__":
    LOGGER = logger.make_custom_logger()
    config = get_config()

    wiki_api = xmlrpc.api(config["wiki_xmlrpc"])

    wiki_api.connect(config["wiki_login"], config["wiki_password"])
    page = wiki_api.get_page("CCCOE", "Resources Utilization")


    try:
    	cache_date = datetime.datetime.strptime(read_file("updated.txt"), "%x %X")
    except ValueError:
    	cache_date = datetime.datetime.min
    	LOGGER.error("Unable to read date cache")
    now = datetime.datetime.utcnow()
    wiki = datetime.datetime.strptime(str(page["modified"]), "%Y%m%dT%H:%M:%S") + datetime.timedelta(hours=7)    # TZ compensation hack

    LOGGER.debug("Dates: cache=%s, now=%s, wiki=%s" % (cache_date, now, wiki))

    if wiki <= cache_date and now.date() == cache_date.date():
    	LOGGER.info("No page/schemes updates needed")
    	exit() 

    for location in ["Saratov", "Kharkov"]:
        LOGGER.info("Generating chart for location: %s" % location)
        c = chart.OffsetGanttChart("Test Chart")
        parse_table(page["content"], location, c) 

        page["content"] = replace_table(page["content"], location, c)

        r = render.Render(600)
        data = r.process(c)

        wiki_api.upload_attachment(page["id"], location + ".png", "image/png", data)

    write_file("updated.txt", (now + datetime.timedelta(minutes=10)).strftime("%x %X"))
    page["content"] = re.sub("Last update: [^<]*", "Last update: %s" % datetime.datetime.now().strftime("%d/%m/%Y %H:%I"), page["content"])
    wiki_api.update_page(page, True)
