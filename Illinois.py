from bs4 import BeautifulSoup
import urllib3
import requests
import re
from common import Response

from common import Query

http = urllib3.PoolManager(cert_reqs="CERT_NONE") # TODO: fix SSL certifications
urllib3.disable_warnings()

state_url = "https://idoc.illinois.gov/"
facilities_url = "https://idoc.illinois.gov/facilities/correctionalfacilities.html"
last_name_query_url = "https://idoc.illinois.gov/offender/inmatesearch/SearchByLastName"
idocn_query_url = "https://idoc.illinois.gov/offender/inmatesearch/SearchByIdocn"

def initJson():
    return {"idocn":None,"lastName":"","birthdate":"","userDisplayableMessage":None,"clickNextFlag":"","clickNextIdocn":""}

def safeHeaders():
    return {
        "Content-Type": "application/json",
        "User-Agent" : "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
    }

def fetchIdocn(idocn):
    resp = requests.post(
        idocn_query_url,
        data=('"' + idocn + '"'),
        headers=safeHeaders())
    data = resp.json()
    if not "IDOC Number" in data: return None
    if data["IDOC Number"]!=idocn: return None
    return [data]

def fetchLastName(lastName):
    data = initJson()
    data["lastName"] = lastName

    resp = requests.post(
        last_name_query_url,
        json=data,
        headers=safeHeaders())
    
    matches = []
    while(True): 
        if resp.status_code !=200:
            break
        try:
            data = resp.json()
            if len(data["persons"])==0:
                break
            for person in data["persons"]:
                if person["lastName"]==lastName.upper():
                    matches.append(person)
                else:
                    if len(matches)>0:
                        return matches
            nextIDOCN = data["persons"][len(data["persons"])-1]["IDOC Number"]
            data = initJson()
            data["clickNextIdocn"] = nextIDOCN
            data["clickNextFlag"] = "Y"
            resp = requests.post(
                last_name_query_url,
                json=data,
                headers=safeHeaders())
        except Exception as e:
            print(e)
            break

def fetchFacilities():
    print("fetching IL facilities")

    locationLinks = set()
    resp = http.request('GET', facilities_url)
    if resp.status != 200:
        raise Exception("location website could not be loaded at url", facilities_url)

    soup = BeautifulSoup(resp.data, 'html.parser')

    for link in soup.find_all('a'):
        href = link.get('href')
        if href == None:
            continue
        if not href.startswith("/facilities/correctionalfacilities"):
            continue
        locationLinks.add(href)

    print(str(len(locationLinks)) + " locations found, grabbing addresses...")

    facilityMap = {}
    lastlen = 0
    for link in locationLinks:
        resp = http.request('GET', state_url+link)
        if resp.status != 200:
            continue
        
        soup = BeautifulSoup(resp.data, 'html.parser')

        name = link.removeprefix("/facilities/correctionalfacilities").removesuffix(".html").replace("-", " ").upper()

        addressContainer = soup.find(string=re.compile('Facility Address:'))
        
        address = addressContainer.parent.get_text(separator=" ").strip().replace(u'\u200b', "").replace(u'\xa0', u' ')
        facilityMap[name] = address

        out = name + " found"
        print(out + " " * max(0,lastlen-len(out)), end='\r')
        lastlen = len(out)

    print("facility map finished")
    print(facilityMap)
    return facilityMap

class IllinoisWebsite(object):
    def __init__(self):
        self.facilityMap = fetchFacilities()
    def query(self, query: Query) -> list[type: Response]:
        responses = []
        data = fetchIdocn(query.data["inmate_id"])
        if data == None:
            data = fetchLastName(query.data["last_name"])

        
        for match in data:
            unit = match["facility"]
            address = self.facilityMap[unit] if unit in self.facilityMap.keys() else f"UNIT: {unit} (unknown address)"

            responses.append(Response(f"{unit.upper()} UNIT", address, query.data["add1"]))
        return responses
