from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_CONFIG, SCOPE_SYSETC

_version = "3"
_plugindir = resolveFilename(SCOPE_PLUGINS, "Extensions/GeradorPicons")
_developer = "gravatasufoca"
_title = "Gerador de Picons - V"+_version+" - "+_developer
_pluginNome = "Gerador de Picons"

_outdir = resolveFilename(SCOPE_CONFIG, "")

_urlModelo="https://dl.dropboxusercontent.com/u/12772101/geradorPicons/modelos.conf"
_urlVersao="https://dl.dropboxusercontent.com/u/12772101/geradorPicons/enigma2-plugin-extensions-gerador-picons.ipk"
_picoZipDir="/tmp/piconZip"


screens=[]

def addScreen(screen):
	screens.append(screen)


def corrigiNome(nome):
	# return Utils.removeAcentos(nome.toLowerCase().trim()).replace(".png","").replaceAll("\\s+(?=\\d+)","");
	import re
	nome = nome.lower().replace(".png", "")
	nome= removerAcentos(re.sub('\s+(?=\d+)', '', nome))
	# nome= re.sub('\s+(?=\++)', '', nome)
	return re.sub('(?<=\+)\s+','',nome)

def removerAcentos(input_str):
	from unicodedata import normalize
	return normalize('NFKD', input_str.decode("UTF-8")).encode('ASCII', 'ignore')


def getConfiguracoes():
	import urllib,ConfigParser

	testfile = urllib.URLopener()
	testfile.retrieve(_urlModelo, "/tmp/modelos.conf")

	config = ConfigParser.RawConfigParser()
	config.read('/tmp/modelos.conf')
	items=[]
	for item in config.items("modelos"):
		items.append((item[1],item[0]))

	return {"items":items,"versao":config.get("versao","versao"),"depara":config.get("depara","url")}

def getPiconsZipped(url,callback=[]):
	import requests, zipfile, StringIO
	r = requests.get(url,stream=True)

	total_length = r.headers.get('content-length')

	content=""
	recebido=0
	for chunck in r.iter_content(1024):
		recebido+=len(chunck)
		content+=chunck
		print len(content)
		callback(total_length,recebido)

	zipDocument = zipfile.ZipFile(StringIO.StringIO(content))
	return zipDocument

def getSatInfo(transponder_info):
		tunerType = transponder_info["tuner_type"]
		if tunerType == "DVB-S":
			pos = int(transponder_info["orbital_position"])
			direction = 'E'
			if pos > 1800:
				pos = 3600 - pos
				direction = 'W'
			return "%d.%d%s" % (pos/10, pos%10, direction)
		return tunerType