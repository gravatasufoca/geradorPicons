# -*- coding: utf-8 -*-
import os
import re
import zipfile
from sets import Set

import StringIO
from Components.Sources.Progress import Progress
from Components.Sources.StaticText import StaticText
from Screens import MessageBox
from Screens.Screen import Screen
from enigma import eTimer

import utils
from Picon import Picon
from ProgressoGerador import ProgressoGeradorScreen
from duvidasList import DuvidasPiconScreen
from geradorpicons import config


class ProcessarCompativeisScreen(Screen):
	skin = """
			<screen name="ProcessarCompativeisScreen" position="center,center" size="723,500" title="Gerador de Picons">
			      <widget source="job_name" render="Label" position="65,147" size="600,35" font="Regular;28" />
			      <widget source="job_task" render="Label" position="65,216" size="600,30" font="Regular;24" />
			      <widget source="job_progress" render="Progress" position="65,291" size="600,36" borderWidth="2" backgroundColor="#254f7497" />
			      <widget source="job_progress" render="Label" position="160,294" size="410,32" font="Regular;28" foregroundColor="#000000" zPosition="2" halign="center" transparent="1">
			        <convert type="ProgressToText" />
			      </widget>
			</screen>
	"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.skin = ProcessarCompativeisScreen.skin

		self["Title"].text = utils._title
		self.tipoPicon = config.plugins.geradorpicon.tipo.value
		self.onFirstExecBegin.append(self.downloadZip)
		self.progress = Progress()

		self.jobName = StaticText()
		self.jobTask = StaticText()
		self["job_progress"] = self.progress


		self["job_name"] = self.jobName
		self["job_task"] = self.jobTask
		utils.addScreen(self)

	def abre(self):
		self.session.open(DuvidasPiconScreen, zipFile=self.zipFile, gerados=self.gerados, duvidas=self.duvidas)

	def processar(self):
		from enigma import eServiceReference, eServiceCenter, iServiceInformation
		servicehandler = eServiceCenter.getInstance()

		if self.canais:
			item = self.canais.pop()

			canal = eServiceReference(item[0])
			if canal:
				nome = servicehandler.info(canal).getName(canal).lower()
				self.jobName.text = "Processando canal %s" % (nome)

				transponder_info = servicehandler.info(canal).getInfoObject(canal, iServiceInformation.sTransponderData)

				cabo = transponder_info["tuner_type"] == "DVB-C"

				tipo = item[0].split(":")[2]

				hd = False
				if tipo in ["25","19"]:
					hd = True
				if cabo and (" hd" in nome or " hd " in nome):
					hd = True

				if not (not nome or nome == "(...)"):
					self.jobTask.text = "Procurando picons compatíveis..."
					arqs = self.getCompativel(utils.corrigiNome(nome), hd)

					if arqs:
						if len(arqs) == 1:
							self.jobTask.text = "Picon encontrado!"
							self.gerados[canal] = Picon(canal, arqs[0], self.zipFile)
						elif len(arqs) > 1:
							self.jobTask.text = "Hum... Dúvidas..."
							self.duvidas[canal] = arqs[0:10]

			self.progress.value = self.total - len(self.canais)
			self.timer.start(10, True)

		else:
			print "gerados: %d, duvidas: %d" % (len(self.gerados), len(self.duvidas))
			if len(self.duvidas) > 0:
				self.abre()
			else:
				self.session.open(ProgressoGeradorScreen,zipFile=self.zipFile,gerados=self.gerados)


	def downloadZip(self):

		import requests, zipfile, StringIO
		self.response = requests.get(self.tipoPicon, stream=True)
		self.totalProgresso = int(self.response.headers.get('content-length'))
		self.progress.setRange(self.totalProgresso)
		self.jobName.text="Baixando os picons..."
		self.content = ""
		self.recebido = 0

		self.downloadTimer = eTimer()
		self.downloadTimer.callback.append(self.atualizaProgresso)
		self.downloadTimer.start(1, True)

	def atualizaProgresso(self):
		chunck = self.response.iter_content(9216*3).next()

		self.recebido += len(chunck)
		self.progress.value = self.recebido
		self.content += chunck
		if self.recebido < self.totalProgresso:
			self.downloadTimer.start(1, True)
		else:
			self.zipFile = zipfile.ZipFile(StringIO.StringIO(self.content))
			if self.zipFile:
				self.listaPicons = [(name, utils.corrigiNome(re.split("\/", name)[1])) for name in self.zipFile.namelist()]

				self.timerGerar = eTimer()
				self.timerGerar.callback.append(self.gerarChannel)
				self.timerGerar.start(1, True)
			else:
				self.session.open(MessageBox,
				                  text="Erro ao baixar os picons!\nVerifica sua conexão com a internet e tente novamente.",
				                  type=MessageBox.TYPE_WARNING, close_on_any_key=True, timeout=5)

	def gerarChannel(self):

		self.close_on_next_exec = (0, 1)

		from Components.Sources.ServiceList import ServiceList

		self.tags = {}
		for file in self.listaPicons:
			nomes = re.split("\s", file[1])
			for nome in nomes:
				if not self.tags.has_key(nome):
					self.tags[nome] = []
				self.tags[nome].append(file)

		currentServiceRef = self.session.nav.getCurrentlyPlayingServiceReference()
		servicelist = ServiceList("")
		servicelist.setRoot(currentServiceRef)
		self.canais = servicelist.getServicesAsList()

		self.gerados = {}
		self.duvidas = {}
		self.filtrarRadios()
		self.progress.setRange(len(self.canais))
		self.progress.value = 0

		self.total = len(self.canais)

		self.timer = eTimer()
		self.timer.callback.append(self.processar)
		self.timer.start(10, True)

	def filtrarRadios(self):
		from enigma import eServiceReference, eServiceCenter, iServiceInformation
		servicehandler = eServiceCenter.getInstance()
		import re

		tmp=[]
		for item in self.canais:
			canal = eServiceReference(item[0])
			nome = servicehandler.info(canal).getName(canal).lower()

			if item[0].split(":")[2] != "2":
				if not re.match("\d+",nome) and not nome=="(...)":
					tmp.append(item)

		self.canais=tmp

	def getFilesFrom(self,nome):
		files=Set()
		nomes=nome.split("\s")
		for t in nomes:
			if self.tags.has_key(t):
				for f in self.tags[t]:
					files.add(f)

		return files

	def getCompativel(self, nome, hd):

		for file in self.listaPicons:
			# if nome.lower().startswith("premiere hd"):
			# 	print "%s = %s, %s"%(re.sub("\s+","",file[1]).lower(),re.sub("\s+","",nome).lower(), re.sub("\s+","",file[1]).lower()==re.sub("\s+","",nome).lower())
			if re.sub("\s+", "", file[1]).lower() == re.sub("\s+", "", nome) + ".png".lower():
				return [file]

		tmpTags = Set(self.tags.keys())
		# print "enviando tmpTags %d"%(len(tmpTags))
		compativeis = list(self.getCompativeis(nome, tmpTags, Set(), hd))

		# print "getCompativel: %d"%(len(compativeis))

		if len(compativeis) == 1:
			return compativeis

		# print "verifica se tem nome compativel"

		for file in compativeis:
			fileName = file[1]
			if fileName.strip() == nome:
				return [file]

		if len(compativeis) == 2:
			# print "verifica quando sao dois"
			# print "%s - %s"%(compativeis[0][1],compativeis[1][1])
			if len(re.split("\s", compativeis[0][1])) > len(re.split("\s", compativeis[1][1])):
				return [compativeis[0]]
			else:
				return [compativeis[1]]

		# print "tenta encontrar os compativeis"

		for file in compativeis:
			i = 0
			fileName = re.split("\s", file[1])
			for name in fileName:
				if name.strip().lower() == nome.lower() or nome.replace("\s+", "").strip().lower() == name.lower():
					return [file]
				if name in nome:
					i = i + 1

			if i >= len(re.split("\s", nome)):
				return [file]

		# print "encontrei: %d compativeis"%(len(compativeis))
		return compativeis

	def getCompativeis(self, nome, tmpTags, tmpArquivos, hd):
		# print "getCompativeis: %d - arquivos %d"%(len(tmpTags),len(tmpArquivos))
		# print "procurando compativeis para %s" %(nome)
		nomes = re.split("\s", nome.strip())
		tmpNome = nomes[0]
		# print "tmpNome %s, nomes: %s"%(tmpNome,nomes)
		if len(nomes) > 0 and tmpNome:
			novoNome = ""
			sep = ""
			for i in range(1, len(nomes)):
				novoNome += sep + nomes[i]
				if len(sep)==0:
					sep = " "
			# print "%s estah - %s" %(tmpNome, tmpNome in tmpTags)
			if tmpNome in tmpTags:
				# print "tmpArquivos - %s"%(tmpArquivos)
				if len(tmpArquivos)==0:
					tmpArquivos = tmpArquivos.union(Set(self.tags[tmpNome]))
					if not hd:
						tmpArquivos = self.filtrar(tmpArquivos, "hd", True)
				else:
					tmpArquivos = self.filtrar(tmpArquivos, tmpNome, False)

			# print "tmpArquivos - %s"%(tmpArquivos)
			tt = Set(self.getTags(tmpArquivos, hd))
			# print "encontrei algo? %s"%(tt)
			return self.getCompativeis(novoNome, tt, tmpArquivos, hd)
		else:
			# print "terminou %d"%(len(tmpArquivos))
			return tmpArquivos

	def filtrar(self, arquivos, nome, nao):
		tmp = Set()
		for file in arquivos:
			if nao:
				if nome.strip() not in file[1].lower():
					tmp.add(file)
			elif nome.strip().lower() in file[1].lower():
				tmp.add(file)

		# print "filtrado %d"%(len(tmp))
		return tmp

	def getTags(self, files, hd):
		tmpTags = Set()
		if files:
			for file in files:
				name = re.split("\s", file[1])
				for t in name:
					if t.strip().lower() == "hd" and not hd: continue
					tmpTags.add(t.strip())
		return tmpTags
