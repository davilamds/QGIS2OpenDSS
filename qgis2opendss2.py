# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QGIS2OpenDSS
                                 A QGIS plugin
 This plugin reads geographic information of electric distribution circuits and exports command lines for OpenDSS
                              -------------------
        begin                : 2015-11-22
        git sha              : $Format:%H$
        copyright            : (C) 2015 by EPERLAB / Universidad de Costa Rica
        email                : gvalverde@eie.ucr.ac.cr, abdenago.guzman@ucr.ac.cr, aarguello@eie.ucr.ac.cr
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import print_function
from __future__ import absolute_import
from builtins import str
from builtins import range
from builtins import object
import glob
import os
import shutil
import time
import timeit
from math import sqrt

import networkx as nx  # Para trabajar con teoria de grafos
import numpy as np
import os.path

from PyQt5.QtCore import *
from PyQt5 import QtCore 

from PyQt5 import QtGui #Paquetes requeridos para crear ventanas de diálogo e interfaz gráfica.
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QLineEdit, QFileDialog, QMessageBox
import traceback

from qgis.core import *  # Paquetes requeridos para crer el registro de eventos.
from qgis.gui import *  # Paquete requerido para desplegar mensajes en la ventana principal de QGIS.

from . import auxiliary_functions
# from dateTime import *
from . import lineOperations
from . import phaseOperations  # Realiza diferentes tareas con las fases de los elementos electricos.
from . import trafoOperations  # Operaciones con transformadores
from . import resources
# Initialize Qt resources from file resources.py
# Import the code for the dialog
from .qgis2opendss_dialog import QGIS2OpenDSSDialog
from .qgis2opendss_progress import Ui_Progress

import sys

# Para desplegar mensajes, útil para debugin


##Messagebox para debugging############################################## AAG rules
# w = QWidget()
# textoDebug='Hola mundo'
# result = QMessageBox.information(w, 'Message', textoDebug)
#########################################################################

class QGIS2OpenDSS(object):
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run Time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]

        if locale != (u'es'):  # es
            locale = (u'en')  # en

        locale_path = os.path.join(self.plugin_dir, 'i18n', 'QGIS2OpenDSS_{}.qm'.format(locale))  # translation file

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = QGIS2OpenDSSDialog()
        self.progress = Ui_Progress()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&QGIS2OpenDSS')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'QGIS2OpenDSS')
        self.toolbar.setObjectName(u'QGIS2OpenDSS')

        # Llama al metodo para seleccionar la carpeta de destino
        # self.dlg.lineEdit_nameCircuit.clear()
        # self.dlg.lineEdit_dirOutput.clear()
        self.dlg.pushButton.clicked.connect(self.select_output_folder)

        # Llama al método para seleccionar el archivo de perfiles de carga
        # self.dlg.lineEdit_AC.clear()
        self.dlg.pushButton_AC.clicked.connect(self.select_load_profile)
        self.dlg.button_box.helpRequested.connect(self.show_help)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('dialog', 'QGIS2OpenDSS', message)

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        """Add a toolbar icon to the toolbar.
        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str
        :param text: Text that should be shown in menu items for this action.
        :type text: str
        :param callback: Function to be called when the action is triggered.
        :type callback: function
        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool
        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool
        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool
        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str
        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget
        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.
        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QtGui.QIcon(icon_path)
        action = QtWidgets.QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/QGIS2OpenDSS/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Export circuit to OpenDSS'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&QGIS2OpenDSS'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def select_output_folder(self):
        """Método para seleccionar la carpeta de destino"""
        foldername = QFileDialog.getExistingDirectory(self.dlg, QCoreApplication.translate('dialog',
                                                                                           "Seleccione carpeta de destino "),
                                                      "", )
        self.dlg.lineEdit_dirOutput.setText(foldername)

    def select_load_profile(self):
        """Método para seleccionar el archivo de asignación de perfil de consumo"""
        # filename=QFileDialog.getOpenFileName(self.dlg,"Seleccione el archivo.txt para designar curva de carga conforme al consumo mensual promedio","",)
        foldername = QFileDialog.getExistingDirectory(self.dlg, QCoreApplication.translate('dialog',
                                                                                           "Seleccione la carpeta con las curvas de carga "),
                                                      "", )
        self.dlg.lineEdit_AC.setText(foldername)

    def show_help(self):
        """Display application help to the user."""

        help_file = 'file:///%s/help/Manual_QGIS2OPENDSS.pdf' % self.plugin_dir
        # For testing path:
        # QMessageBox.information(None, 'Help File', help_file)
        # noinspection PyCallByClass,PyTypeChecker
        QDesktopServices.openUrl(QUrl(help_file))

    def mkdir_p(self, mypath):
        '''Creates a directory. equivalent to using mkdir -p on the command line'''
        from errno import EEXIST
        from os import makedirs, path
        try:
            makedirs(mypath)
        except OSError as exc:  # Python >2.5
            if exc.errno == EEXIST and path.isdir(mypath):
                pass
            else:
                raise

    def CoordLineProcess(self, ObjetoLinea, tolerancia):  # Procesa las coodernadas de las líneas para agregar al grafo.
        #line = ObjetoLinea.geometry().asPolyline()  # Lee la geometria de la linea
        
        geom = str(ObjetoLinea.geometry())
        line = []
        line = self.MultiStringToMatrix_r(geom)
        
        n = len(line)  # Cantidad de vértices de la línea
        X1 = int(float(line[0][0] / tolerancia))
        Y1 = int(float(line[0][1] / tolerancia))
        X2 = int(float(line[n - 1][0] / tolerancia))
        Y2 = int(float(line[n - 1][1] / tolerancia))
        P1 = (X1, Y1)
        P2 = (X2, Y2)
        return P1, P2

    def CoordPointProcees(self, ObjetoLinea, tolerancia):
        point = ObjetoLinea.geometry().asPoint()  # Lee la geometria de la linea
        X1 = int(float(point[0] / tolerancia))
        Y1 = int(float(point[1] / tolerancia))
        P1 = (X1, Y1)
        return P1

    def ReaderDataLMT(self, layer, Grafo, datosLMT, toler, subterranea,
                      indexDSS):  # Lee los datos de capa de línea y las agrega al grafo
        lineasMT = layer.getFeatures()  # Recibe las caracteristicas de la capa de lineas de media tension.
        for lineaMT in lineasMT:
            
            
            #line = lineaMT.geometry().asPolyline()  # Lee la geometria de la linea
            
            geom = str(lineaMT.geometry())
            line = []
            line = self.MultiStringToMatrix_r(geom)
            
                        
            n = len(line)  # Cantidad de vértices de la línea
            fase = phaseOperations.renamePhase(lineaMT['PHASEDESIG']).get('phaseCodeODSS')
            faseOrig = lineaMT['PHASEDESIG']
            cantFases = phaseOperations.renamePhase(lineaMT['PHASEDESIG']).get('phaseNumber')
            opervoltLN = lineOperations.renameVoltage(lineaMT['NOMVOLT']).get('LVCode')['LN']
            opervoltLL = lineOperations.renameVoltage(lineaMT['NOMVOLT']).get('LVCode')['LL']
            nodo1, nodo2 = self.CoordLineProcess(lineaMT, toler)
            LineLength = lineaMT.geometry().length()
            if subterranea:  # Determina si la línea es aérea o subterránea
                air_ugnd = 'ugnd'
                datosLinea = {"PHASEDESIG": faseOrig, "INDEXDSS": indexDSS, 'ID': lineaMT.id(), "LAYER": layer,
                              "nodo1": nodo1, "nodo2": nodo2, "X1": line[0][0], "Y1": line[0][1], "X2": line[n - 1][0],
                              "Y2": line[n - 1][1], 'NEUMAT': lineaMT['NEUTMAT'], 'NEUSIZ': lineaMT['NEUTSIZ'],
                              'PHAMAT': lineaMT['PHASEMAT'], 'PHASIZ': lineaMT['PHASESIZ'],
                              'NOMVOLT': lineaMT['INSULVOLT'], 'PHASE': fase, 'SHLEN': LineLength, 'AIR_UGND': air_ugnd,
                              'INSUL': lineaMT['INSULMAT'], 'NPHAS': cantFases, 'VOLTOPRLL': opervoltLL,
                              'VOLTOPRLN': opervoltLN, "SHIELD": lineaMT["SHIELDING"]}
            else:
                air_ugnd = 'air'
                datosLinea = {"PHASEDESIG": faseOrig, "INDEXDSS": indexDSS, 'ID': lineaMT.id(), "LAYER": layer,
                              "nodo1": nodo1, "nodo2": nodo2, "X1": line[0][0], "Y1": line[0][1], "X2": line[n - 1][0],
                              "Y2": line[n - 1][1], 'NEUMAT': lineaMT['NEUTMAT'], 'NEUSIZ': lineaMT['NEUTSIZ'],
                              'PHAMAT': lineaMT['PHASEMAT'], 'PHASIZ': lineaMT['PHASESIZ'], 'CCONF': lineaMT['LINEGEO'],
                              'PHASE': fase, 'SHLEN': LineLength, 'AIR_UGND': air_ugnd, 'NPHAS': cantFases,
                              'VOLTOPRLL': opervoltLL, 'VOLTOPRLN': opervoltLN}

            if Grafo.get_edge_data(nodo1, nodo2) == None:  # se asegura que la línea no existe
                Grafo.add_edge(nodo1, nodo2, weight = datosLinea)  # Agrega la línea al grafo con todos los datos
            else:  # Si la línea existe es porque están en paralelo
                newLength = float(datosLinea["SHLEN"]) / 2
                datosLinea["SHLEN"] = newLength
                paralelNode = "Paralel" + str(nodo1)
                datosLinea["nodo2"] = paralelNode
                Grafo.add_edge(nodo1, paralelNode,  weight = datosLinea)  # Agrega la línea al grafo con todos los datos

                datosLinea["nodo2"] = nodo2
                datosLinea["nodo1"] = paralelNode
                Grafo.add_edge(paralelNode, nodo2, weight = datosLinea)  # Agrega la línea al grafo con todos los datos

        return Grafo, datosLMT

    def ReaderDataTrafos(self, layer, toler, datosT3F_Multi, datosT3F_Single, datosT2F, datosT1F, Graph_T3F_multi,
                         Graph_T3F_single, Graph_T2F, Graph_T1F, indexDSS, grafoBTTotal):
        trafos1 = layer.getFeatures()  # Recibe las caracteristicas de la capa de transformadores.
        for trafo1 in trafos1:  # Separa los transformadores en tres listas: Monofasicos, Bifasicos y Trifasicos
            
            nodo = self.CoordPointProcees(trafo1, toler)
            point = trafo1.geometry().asPoint()  # Lee la geometria de la linea
            fase = phaseOperations.renamePhase(trafo1['PHASEDESIG']).get('phaseCodeODSS')  # define código de OpenDSS
            numfase = phaseOperations.renamePhase(trafo1['PHASEDESIG']).get(
                'phaseNumberTraf')  # define código de OpenDSS
            MVCode = trafo1['PRIMVOLT']
            LVCode = trafo1['SECVOLT']
            tap = str(format(float(trafo1['TAPSETTING']), '.4f'))
            voltages = trafoOperations.renameVoltage(int(MVCode), int(LVCode))
            if voltages["LVCode"]["LL"] == 0:
                loadvolt = "UNKNOWN"
                loadvoltLN = "UNKNOWN"
                aviso = QCoreApplication.translate('dialog', u'No se encuentra el código de tensión ') + str(LVCode)
                QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', 'Alerta Transformadores'),
                                         QgsMessageLog.WARNING)
            else:
                loadvolt = str(voltages["LVCode"]["LL"])
                loadvoltLN = str(voltages["LVCode"]["LN"])
            if voltages["MVCode"]["LL"] == 0:
                voltoprLL = "UNKNOWN"
                voltoprLN = "UNKNOWN"
                aviso = QCoreApplication.translate('dialog', 'No se encuentra el código de tensión ') + str(MVCode)
                QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', 'Alerta Transformadores'),
                                         QgsMessageLog.WARNING)
            else:
                voltoprLL = str(voltages["MVCode"]["LL"])
                voltoprLN = str(voltages["MVCode"]["LN"])
            try:
                group = trafo1['GRUPO']
            except KeyError:
                group = 'N/A'

            if fase == '.1.2.3':  # Divide los transformadores trifasicos en transformadores simples y de multiples unidades monofasicas
                # Revisa si es un banco de tres transformadores con placa diferente o una sola unidad
                if (trafo1['SECCONN'] == '4D'):
                    datosMulti = {"NPHAS": numfase, "MVCODE": MVCode, "LVCODE": LVCode, "INDEXDSS": indexDSS,
                                  'ID': trafo1.id(), "TAPS": tap, "LAYER": layer, "nodo": nodo, 'X1': point[0],
                                  'Y1': point[1], 'PHASE': fase, 'KVA_FA': trafo1['KVAPHASEA'],
                                  'KVA_FB': trafo1['KVAPHASEB'], 'KVA_FC': trafo1['KVAPHASEC'],
                                  'KVM': trafo1['PRIMVOLT'], 'KVL': trafo1['SECVOLT'], 'CONME': trafo1['PRIMCONN'],
                                  'CONBA': trafo1['SECCONN'], 'LOADCONNS': '.1.2.3', 'LOADCONF': 'delta',
                                  'LOADVOLT': loadvolt, 'LOADVOLTLN': loadvoltLN, 'GRUPO': group, "VOLTMTLL": voltoprLL,
                                  "VOLTMTLN": voltoprLN}
                    datosTotalGraph = {"NPHAS": numfase, "type": "TRAF", 'LOADVOLT': loadvolt, 'LOADVOLTLN': loadvoltLN}

                    datosT3F_Multi.append(datosMulti)
                    if (nodo in Graph_T3F_multi.nodes()) and (
                            Graph_T3F_multi.node[nodo]['PHASE'] == datosMulti['PHASE']):
                        Graph_T3F_multi.node[nodo]['KVA_FA'] = float(datosMulti['KVA_FA']) + float(
                            Graph_T3F_multi.node[nodo]['KVA_FA'])
                        Graph_T3F_multi.node[nodo]['KVA_FB'] = float(datosMulti['KVA_FB']) + float(
                            Graph_T3F_multi.node[nodo]['KVA_FB'])
                        Graph_T3F_multi.node[nodo]['KVA_FC'] = float(datosMulti['KVA_FC']) + float(
                            Graph_T3F_multi.node[nodo]['KVA_FC'])
                        aviso = QCoreApplication.translate('dialog',
                                                           'Se aumento la capacidad de un transformador trifasico de 3 unidades debido a su cercanía con otro banco de transformadores en: (') + str(
                            Graph_T3F_multi.node[nodo]['X1']) + ', ' + str(Graph_T3F_multi.node[nodo]['Y1']) + ')'
                        QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', 'Alerta Transformadores'),
                                                 QgsMessageLog.WARNING)
                    else:
                        Graph_T3F_multi.add_node(nodo, pos = datosMulti)  # Agrega el trafo al grafo con todos los datos
                        grafoBTTotal.add_node(nodo, pos = datosTotalGraph)
                if (trafo1['SECCONN'] == 'Y') and (trafo1['PRIMCONN'] == 'Y' or trafo1['PRIMCONN'] == 'D'):

                    if float(trafo1['KVAPHASEA']) == float(trafo1['KVAPHASEB']) == float(trafo1['KVAPHASEC']):

                        datosSingleY = {'KVA_FA': trafo1['KVAPHASEA'], 'KVA_FB': trafo1['KVAPHASEB'],
                                        'KVA_FC': trafo1['KVAPHASEC'], "NPHAS": numfase, "MVCODE": MVCode, "LVCODE": LVCode,
                                        "INDEXDSS": indexDSS, 'ID': trafo1.id(), "LAYER": layer, "nodo": nodo, "TAPS": tap,
                                        'X1': point[0], 'Y1': point[1], 'PHASE': fase,
                                        'KVA': int(float(trafo1['RATEDKVA'])), 'KVM': trafo1['PRIMVOLT'],
                                        'KVL': trafo1['SECVOLT'], 'CONME': trafo1['PRIMCONN'], 'CONBA': trafo1['SECCONN'],
                                        'LOADCONNS': '.1.2.3', 'LOADCONF': 'wye', 'LOADVOLT': loadvolt,
                                        'LOADVOLTLN': loadvoltLN, 'GRUPO': group, "VOLTMTLL": voltoprLL,
                                        "VOLTMTLN": voltoprLN}
                        datosTotalGraph = {"NPHAS": numfase, "type": "TRAF", 'LOADVOLT': loadvolt,
                                           'LOADVOLTLN': loadvoltLN}
                        datosT3F_Single.append(datosSingleY)

                        if (nodo in Graph_T3F_single.nodes()) and (
                                Graph_T3F_single.node[nodo]['PHASE'] == datosSingleY['PHASE']):
                            Graph_T3F_single.node[nodo]['KVA'] = float(datosSingleY['KVA']) + float(
                                Graph_T3F_single.node[nodo]['KVA'])
                            aviso = QCoreApplication.translate('dialog',
                                                               'Se aumento la capacidad de un transformador trifasico debido a su cercanía con otro transformador en: (') + str(
                                Graph_T3F_single.node[nodo]['X1']) + ', ' + str(Graph_T3F_single.node[nodo]['Y1']) + ')'
                            QgsMessageLog.logMessage(aviso,
                                                     QCoreApplication.translate('dialog', 'Alerta Transformadores'),
                                                     QgsMessageLog.WARNING)
                        else:
                            Graph_T3F_single.add_node(nodo,
                                                      pos = datosSingleY)  # Agrega el trafo al grafo con todos los datos
                            grafoBTTotal.add_node(nodo, pos = datosTotalGraph)

                    else:
                        # fix_print_with_import
                        
                        datosMulti = {"NPHAS": numfase, "MVCODE": MVCode, "LVCODE": LVCode, "INDEXDSS": indexDSS,
                                  'ID': trafo1.id(), "TAPS": tap, "LAYER": layer, "nodo": nodo, 'X1': point[0],
                                  'Y1': point[1], 'PHASE': fase, 'KVA_FA': trafo1['KVAPHASEA'],
                                  'KVA_FB': trafo1['KVAPHASEB'], 'KVA_FC': trafo1['KVAPHASEC'],
                                  'KVM': trafo1['PRIMVOLT'], 'KVL': trafo1['SECVOLT'], 'CONME': trafo1['PRIMCONN'],
                                  'CONBA': trafo1['SECCONN'], 'LOADCONNS': '.1.2.3', 'LOADCONF': 'wye',
                                  'LOADVOLT': loadvolt, 'LOADVOLTLN': loadvoltLN, 'GRUPO': group, "VOLTMTLL": voltoprLL,
                                  "VOLTMTLN": voltoprLN}

                        datosTotalGraph = {"NPHAS": numfase, "type": "TRAF", 'LOADVOLT': loadvolt,
                                           'LOADVOLTLN': loadvoltLN}
                        datosT3F_Multi.append(datosMulti)

                        if (nodo in Graph_T3F_multi.nodes()) and (
                                Graph_T3F_multi.node[nodo]['PHASE'] == datosMulti['PHASE']):
                            Graph_T3F_multi.node[nodo]['KVA_FA'] = float(datosMulti['KVA_FA']) + float(
                                Graph_T3F_multi.node[nodo]['KVA_FA'])
                            Graph_T3F_multi.node[nodo]['KVA_FB'] = float(datosMulti['KVA_FB']) + float(
                                Graph_T3F_multi.node[nodo]['KVA_FB'])
                            Graph_T3F_multi.node[nodo]['KVA_FC'] = float(datosMulti['KVA_FC']) + float(
                                Graph_T3F_multi.node[nodo]['KVA_FC'])
                            aviso = QCoreApplication.translate('dialog',
                                                               'Se aumento la capacidad de un transformador trifasico de 3 unidades debido a su cercanía con otro banco de transformadores en: (') + str(
                                Graph_T3F_multi.node[nodo]['X1']) + ', ' + str(Graph_T3F_multi.node[nodo]['Y1']) + ')'
                            QgsMessageLog.logMessage(aviso,
                                                     QCoreApplication.translate('dialog', 'Alerta Transformadores'),
                                                     QgsMessageLog.WARNING)
                        else:
                            Graph_T3F_multi.add_node(nodo, pos = datosMulti)  # Agrega el trafo al grafo con todos los datos
                            grafoBTTotal.add_node(nodo, pos = datosTotalGraph)

                if (trafo1['SECCONN'] == 'D') and (trafo1['PRIMCONN'] == 'Y' or trafo1['PRIMCONN'] == 'D'):
                    datosSingleD = {'KVA_FA': int(float(trafo1['KVAPHASEA'])),
                                    'KVA_FB': int(float(trafo1['KVAPHASEB'])),
                                    'KVA_FC': int(float(trafo1['KVAPHASEC'])), "NPHAS": numfase, "MVCODE": MVCode,
                                    "LVCODE": LVCode, "TAPS": tap, "INDEXDSS": indexDSS, 'ID': trafo1.id(),
                                    "LAYER": layer, "nodo": nodo, 'X1': point[0], 'Y1': point[1], 'PHASE': fase,
                                    'KVA': int(float(trafo1['RATEDKVA'])), 'KVM': trafo1['PRIMVOLT'],
                                    'KVL': trafo1['SECVOLT'], 'CONME': trafo1['PRIMCONN'], 'CONBA': trafo1['SECCONN'],
                                    'LOADCONNS': '.1.2.3', 'LOADCONF': 'delta', 'LOADVOLT': loadvolt,
                                    'LOADVOLTLN': loadvoltLN, 'GRUPO': group, "VOLTMTLL": voltoprLL,
                                    "VOLTMTLN": voltoprLN}
                    datosT3F_Single.append(datosSingleD)
                    datosTotalGraph = {"NPHAS": numfase, "type": "TRAF", 'LOADVOLT': loadvolt, 'LOADVOLTLN': loadvoltLN}
                    if (nodo in Graph_T3F_single.nodes()) and (
                            Graph_T3F_single.node[nodo]['PHASE'] == datosSingleD['PHASE']):
                        Graph_T3F_single.node[nodo]['KVA'] = float(datosSingleD['KVA']) + float(
                            Graph_T3F_single.node[nodo]['KVA'])
                        aviso = QCoreApplication.translate('dialog',
                                                           'Se aumento la capacidad de un transformador trifasico debido a su cercanía con otro transformador en: (') + str(
                            Graph_T3F_single.node[nodo]['X1']) + ', ' + str(Graph_T3F_single.node[nodo]['Y1']) + ')'
                        QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', 'Alerta Transformadores'),
                                                 QgsMessageLog.WARNING)
                    else:
                        Graph_T3F_single.add_node(nodo, pos = datosSingleD)  # Agrega el trafo al grafo con todos los datos
                        grafoBTTotal.add_node(nodo, pos = datosTotalGraph)
            if fase == '.2.3' or fase == '.1.3' or fase == '.1.2':
                datos2F = {"NPHAS": numfase, "MVCODE": MVCode, "LVCODE": LVCode, "TAPS": tap, "INDEXDSS": indexDSS,
                           'ID': trafo1.id(), "LAYER": layer, "nodo": nodo, 'X1': point[0], 'Y1': point[1],
                           'PHASE': fase, 'KVA': int(float(trafo1['RATEDKVA'])), 'KVM': trafo1['PRIMVOLT'],
                           'KVL': trafo1['SECVOLT'], 'CONME': trafo1['PRIMCONN'], 'CONBA': trafo1['SECCONN'],
                           'KVA_FA': trafo1['KVAPHASEA'], 'KVA_FB': trafo1['KVAPHASEB'], 'KVA_FC': trafo1['KVAPHASEC'],
                           'LOADCONNS': '.1.2.3', 'LOADCONF': 'delta', 'LOADVOLT': loadvolt, 'LOADVOLTLN': loadvoltLN,
                           'GRUPO': group, "VOLTMTLL": voltoprLL, "VOLTMTLN": voltoprLN}
                datosTotalGraph = {"NPHAS": numfase, "type": "TRAF", 'LOADVOLT': loadvolt, 'LOADVOLTLN': loadvoltLN}
                datosT2F.append(datos2F)
                if (nodo in Graph_T2F.nodes()) and (Graph_T2F.node[nodo]['PHASE'] == datos2F['PHASE']):
                    Graph_T2F.node[nodo]['KVA'] = float(datos2F['KVA']) + float(Graph_T2F.node[nodo]['KVA'])
                    aviso = QCoreApplication.translate('dialog',
                                                       'Se aumento la capacidad de un transformador bifasico debido a su cercania con otro transformador en: (') + str(
                        Graph_T2F.node[nodo]['X1']) + ', ' + str(Graph_T2F.node[nodo]['Y1']) + ')'
                    QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', 'Alerta Transformadores'),
                                             QgsMessageLog.WARNING)
                else:
                    Graph_T2F.add_node(nodo, pos = datos2F)  # Agrega el trafo al grafo con todos los datos
                    grafoBTTotal.add_node(nodo, pos = datosTotalGraph)
            if fase == '.3' or fase == '.2' or fase == '.1':
                datos1F = {'KVA_FA': trafo1['KVAPHASEA'], 'KVA_FB': trafo1['KVAPHASEB'], 'KVA_FC': trafo1['KVAPHASEC'],
                           "NPHAS": numfase, "MVCODE": MVCode, "LVCODE": LVCode, "TAPS": tap, "INDEXDSS": indexDSS,
                           'ID': trafo1.id(), "LAYER": layer, "nodo": nodo, 'X1': point[0], 'Y1': point[1],
                           'PHASE': fase, 'KVA': trafo1['RATEDKVA'], 'KVM': trafo1['PRIMVOLT'],
                           'KVL': trafo1['SECVOLT'], 'LOADCONF': 'delta', 'LOADCONNS': '.1.2', 'LOADVOLT': loadvolt,
                           'LOADVOLTLN': loadvoltLN, 'GRUPO': group, "VOLTMTLL": voltoprLL, "VOLTMTLN": voltoprLN}
                datosTotalGraph = {"NPHAS": numfase, "type": "TRAF", 'LOADVOLT': loadvolt, 'LOADVOLTLN': loadvoltLN}
                datosT1F.append(datos1F)
                if (nodo in Graph_T1F.nodes()) and (Graph_T1F.node[nodo]['PHASE'] == datos1F['PHASE']):
                    Graph_T1F.node[nodo]['KVA'] = float(datos1F['KVA']) + float(Graph_T1F.node[nodo]['KVA'])
                    aviso = QCoreApplication.translate('dialog',
                                                       'Se aumento la capacidad de un transformador monofasico debido a su cercania con otro transformador en: (') + str(
                        Graph_T1F.node[nodo]['X1']) + ', ' + str(Graph_T1F.node[nodo]['Y1']) + ')'
                    QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', 'Alerta Transformadores'),
                                             QgsMessageLog.WARNING)
                else:
                    Graph_T1F.add_node(nodo, pos = datos1F)  # Agrega el trafo al grafo con todos los datos
                    grafoBTTotal.add_node(nodo, pos = datosTotalGraph)
        return datosT3F_Multi, datosT3F_Single, datosT2F, datosT1F, Graph_T3F_multi, Graph_T3F_single, Graph_T2F, Graph_T1F, grafoBTTotal

    def ReaderDataLBT(self, layer, datosLBT, grafoBT, grafoBTTotal, toler, subterranea, indexDSS):

        # self.dlg.label_Progreso.setText('Linea MT 1...')
        lineas = layer.getFeatures()  # Recibe las caracteristicas de la capa de lineas de baja tension.
        for linea in lineas:
            #line = linea.geometry().asPolyline()  # Lee la geometria de la linea
            
            geom = str(linea.geometry())
            line = []
            line = self.MultiStringToMatrix_r(geom)
            
            LineLength = linea.geometry().length()
            n = len(line)  # Cantidad de vértices de la línea
            LVCode = linea['NOMVOLT']
            nodo1, nodo2 = self.CoordLineProcess(linea, toler)
            conns = lineOperations.renameVoltage(linea['NOMVOLT']).get('conns')  # phaseCodeOpenDSS
            cantFases = lineOperations.renameVoltage(linea['NOMVOLT']).get('cantFases')  # 1 or 3 phases
            config = lineOperations.renameVoltage(linea['NOMVOLT']).get('config')  # wye or delta
            # opervoltLN=lineOperations.renameVoltage(linea['NOMVOLT']).get('LVCode')['LN']
            # opervoltLL=lineOperations.renameVoltage(linea['NOMVOLT']).get('LVCode')['LL']

            try:
                group = linea['GRUPO']
            except KeyError:
                group = 'N/A'
            if subterranea:  # Determina si la línea es aérea o subterránea
                air_ugnd = 'ugnd'
                datosLinea = {"LVCODE": LVCode, "INDEXDSS": indexDSS, "LAYER": layer, "ID": linea.id(), "nodo1": nodo1,
                              "nodo2": nodo2, 'NEUMAT': linea['NEUTMAT'], 'NEUSIZ': linea['NEUTSIZ'],
                              'PHAMAT': linea['PHASEMAT'], 'PHASIZ': linea['PHASESIZ'], 'X1': line[0][0],
                              'Y1': line[0][1], 'X2': line[n - 1][0], 'Y2': line[n - 1][1], 'SHLEN': LineLength,
                              'AIR_UGND': air_ugnd, 'NPHAS': cantFases, 'CONNS': conns, 'CONF': config,
                              'INSUL': linea['INSULMAT'],
                              'GRUPO': group}  # , 'VOLTOPRLL':opervoltLL,'VOLTOPRLN':opervoltLN}
                datosTotalGraph = {"type": "LBT", 'X1': line[0][0], 'Y1': line[0][1], 'X2': line[n - 1][0],
                                   'Y2': line[n - 1][1]}  # ,'VOLTOPRLL':opervoltLL,'VOLTOPRLN':opervoltLN}
            else:
                air_ugnd = 'air'
                datosLinea = {"LVCODE": LVCode, "INDEXDSS": indexDSS, "LAYER": layer, "ID": linea.id(), "nodo1": nodo1,
                              "nodo2": nodo2, 'NEUMAT': linea['NEUTMAT'], 'NEUSIZ': linea['NEUTSIZ'],
                              'PHAMAT': linea['PHASEMAT'], 'PHASIZ': linea['PHASESIZ'], 'X1': line[0][0],
                              'Y1': line[0][1], 'X2': line[n - 1][0], 'Y2': line[n - 1][1], 'SHLEN': LineLength,
                              'AIR_UGND': air_ugnd, 'NPHAS': cantFases, 'CONNS': conns, 'CONF': config, 'GRUPO': group,
                              'TIPO': linea['TYPE']}  # , 'VOLTOPRLL':opervoltLL,'VOLTOPRLN':opervoltLN}
                datosTotalGraph = {"type": "LBT", 'X1': line[0][0], 'Y1': line[0][1], 'X2': line[n - 1][0],
                                   'Y2': line[n - 1][1]}  # , 'VOLTOPRLL':opervoltLL,'VOLTOPRLN':opervoltLN}
            datosLBT.append(datosLinea)  ### Código viejo

            if grafoBT.get_edge_data(nodo1, nodo2) == None:  # se asegura que la línea no existe
                grafoBT.add_edge(nodo1, nodo2, weight = datosLinea)  # Agrega la línea al grafo con todos los datos
                grafoBTTotal.add_edge(nodo1, nodo2, weight = datosTotalGraph)  # Agrega la línea al grafo con todos los datos
            else:  # Si la línea existe es porque están en paralelo
                newLength = float(datosLinea["SHLEN"]) / 2
                datosLinea["SHLEN"] = newLength
                paralelNode = "Paralel" + str(nodo1)
                datosLinea["nodo2"] = paralelNode

                grafoBT.add_edge(nodo1, paralelNode, weight = datosLinea)  # Agrega la línea al grafo con todos los datos
                grafoBTTotal.add_edge(nodo1, paralelNode,
                                      weight = datosTotalGraph)  # Agrega la línea al grafo con todos los datos

                datosLinea["nodo2"] = nodo2
                datosLinea["nodo1"] = paralelNode

                grafoBT.add_edge(paralelNode, nodo2, weight = datosLinea)  # Agrega la línea al grafo con todos los datos
                grafoBTTotal.add_edge(paralelNode, nodo2,
                                      weight = datosTotalGraph)  # Agrega la línea al grafo con todos los datos
        return datosLBT, grafoBT, grafoBTTotal

    def ReaderDataAcom(self, layer, datosACO, grafoACO, grafoBTTotal, toler, indexDSS, grafoBT):
        lineasACO = layer.getFeatures()  # Recibe las caracteristicas de la capa de acometidas.
        for lineaACO in lineasACO:
            
            #line = lineaACO.geometry().asPolyline()  # Lee la geometria de la linea
            
            geom = str(lineaACO.geometry())
            line = []
            line = self.MultiStringToMatrix_r(geom)
            
            LineLength = lineaACO.geometry().length()
            n = len(line)  # Cantidad de vértices de la línea
            nodo1, nodo2 = self.CoordLineProcess(lineaACO, toler)
            conns = lineOperations.renameVoltage(lineaACO['NOMVOLT']).get('conns')  # phaseCodeOpenDSS
            cantFases = lineOperations.renameVoltage(lineaACO['NOMVOLT']).get('cantFases')  # 1 or 3 phases
            config = lineOperations.renameVoltage(lineaACO['NOMVOLT']).get('config')  # wye or delta
            LVCode = lineaACO['NOMVOLT']
            # opervoltLN=lineOperations.renameVoltage(lineaACO['NOMVOLT']).get('LVCode')['LN']
            # opervoltLL=lineOperations.renameVoltage(lineaACO['NOMVOLT']).get('LVCode')['LL']
            try:
                group = lineaACO['GRUPO']
            except KeyError:
                group = 'N/A'
            datos = {"LVCODE": LVCode, "INDEXDSS": indexDSS, "LAYER": layer, "ID": lineaACO.id(), "nodo1": nodo1,
                     "nodo2": nodo2, 'PHAMAT': lineaACO['PHASEMAT'], 'PHASIZ': lineaACO['PHASESIZ'], 'X1': line[0][0],
                     'Y1': line[0][1], 'X2': line[n - 1][0], 'Y2': line[n - 1][1], 'SHLEN': LineLength,
                     'NPHAS': cantFases, 'CONNS': conns, 'CONF': config, 'GRUPO': group,
                     'TIPO': lineaACO["TYPE"]}  # 'VOLTOPRLL':opervoltLL,'VOLTOPRLN':opervoltLN,
            datosTotalGraph = {"type": "ACO", 'X1': line[0][0], 'Y1': line[0][1], 'X2': line[n - 1][0],
                               'Y2': line[n - 1][1]}  # 'VOLTOPRLL':opervoltLL,'VOLTOPRLN':opervoltLN,
            datosACO.append(datos)

            if grafoBT.get_edge_data(nodo1,
                                     nodo2) != None:  # Se asegura que la línea no se ha creado en el grafo de LBT
                # print "Linea acometida ya existia en grafoTOTAL"
                pass
            else:
                if grafoACO.get_edge_data(nodo1, nodo2) == None:  # se asegura que la línea no existe
                    grafoACO.add_edge(nodo1, nodo2, weight = datos)  # Agrega la línea al grafo con todos los datos
                    grafoBTTotal.add_edge(nodo1, nodo2, weight = datosTotalGraph)
                else:  # Si la línea existe es porque están en paralelo
                    newLength = float(datos["SHLEN"]) / 2
                    datos["SHLEN"] = newLength
                    paralelNode = "Paralel" + str(nodo1)
                    datos["nodo2"] = paralelNode
                    grafoACO.add_edge(nodo1, paralelNode, weight = datos)  # Agrega la línea al grafo con todos los datos
                    grafoBTTotal.add_edge(nodo1, paralelNode, weight = datosTotalGraph)

                    datos["nodo2"] = nodo2
                    datos["nodo1"] = paralelNode
                    grafoACO.add_edge(paralelNode, nodo2, weight = datos)  # Agrega la línea al grafo con todos los datos
                    grafoBTTotal.add_edge(paralelNode, nodo2, weight = datosTotalGraph)
        return datosACO, grafoACO, grafoBTTotal

    def ReaderDataGD(self, toler, layer, grafoGD, indexDSS, Graph_T3F_multi, Graph_T3F_single, Graph_T2F, Graph_T1F,
                     grafoCAR, circuitName, busBTid, busBT_List, busMT_List):
        GDs = layer.getFeatures()  # Recibe las caracteristicas de la capa de cargas.
        for GD in GDs:
            point = GD.geometry().asPoint()  # Lee la geometria de la linea
            nodo = self.CoordPointProcees(GD, toler)
            nodoInTraf = False
            if (nodo in grafoCAR.nodes()):
                bus = grafoCAR.node[nodo]["BUS"]
                if grafoCAR.node[nodo]["TRAFNPHAS"] != "NULL":
                    VOLTAGELL = grafoCAR.node[nodo]["TRAFVOLTLL"]
                    VOLTAGELN = grafoCAR.node[nodo]["TRAFVOLTLN"]
                    NPHAS = grafoCAR.node[nodo]["TRAFNPHAS"]
                    conf = grafoCAR.node[nodo]["CONF"]
                else:
                    VOLTAGELL = "0.24"
                    VOLTAGELN = "0.12"
                    NPHAS = "1"
                    conf = "wye"
            elif (nodo in Graph_T3F_multi.nodes()):
                nodoInTraf == True
                bus = Graph_T3F_multi.node[nodo]["BUSBT"]
                VOLTAGELL = Graph_T3F_multi.node[nodo]["LOADVOLT"]
                VOLTAGELN = Graph_T3F_multi.node[nodo]["LOADVOLTLN"]
                NPHAS = Graph_T3F_multi.node[nodo]["NPHAS"]
                conf = Graph_T3F_multi.node[nodo]["LOADCONF"]

            elif (nodo in Graph_T3F_single.nodes()):
                nodoInTraf == True
                bus = Graph_T3F_single.node[nodo]["BUSBT"]
                VOLTAGELL = Graph_T3F_single.node[nodo]["LOADVOLT"]
                VOLTAGELN = Graph_T3F_single.node[nodo]["LOADVOLTLN"]
                NPHAS = Graph_T3F_single.node[nodo]["NPHAS"]
                conf = Graph_T3F_single.node[nodo]["LOADCONF"]

            elif (nodo in Graph_T2F.nodes()):
                nodoInTraf == True
                bus = Graph_T2F.node[nodo]["BUSBT"]
                VOLTAGELL = Graph_T2F.node[nodo]["LOADVOLT"]
                VOLTAGELN = Graph_T2F.node[nodo]["LOADVOLTLN"]
                NPHAS = Graph_T2F.node[nodo]["NPHAS"]
                conf = Graph_T2F.node[nodo]["LOADCONF"]

            elif (nodo in Graph_T1F.nodes()):
                nodoInTraf == True
                bus = Graph_T1F.node[nodo]["BUSBT"]
                VOLTAGELL = Graph_T1F.node[nodo]["LOADVOLT"]
                VOLTAGELN = Graph_T1F.node[nodo]["LOADVOLTLN"]
                NPHAS = Graph_T1F.node[nodo]["NPHAS"]
                conf = Graph_T1F.node[nodo]["LOADCONF"]
            elif (not nodoInTraf) and (nodo in busMT_List):
                bus = busMT_List[nodo]["bus"]
                VOLTAGELL = busMT_List[nodo]["VOLTAGELL"]
                VOLTAGELN = busMT_List[nodo]["VOLTAGELN"]
                NPHAS = busMT_List[nodo]["NPHAS"]
                conf = "wye"
            else:
                bus = 'BUSLV' + circuitName + str(busBTid)
                VOLTAGELL = "0.24"
                VOLTAGELN = "0.12"
                NPHAS = "1"
                conf = "wye"
                busBT_List[nodo] = {'bus': bus, 'X': point[0], 'Y': point[1], "GRAFO": grafoGD, "VOLTAGELN": VOLTAGELN}
                busBTid += 1
                aviso = QCoreApplication.translate('dialog', 'Hay 1 generador desconectado en: (') + str(
                    point[0]) + ',' + str(point[1]) + ')'
                QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', 'Alerta Generador'),
                                         QgsMessageLog.WARNING)

            datos = {"CONF": conf, "NPHAS": NPHAS, "VOLTAGELN": VOLTAGELN, "VOLTAGELL": VOLTAGELL, "BUS": bus,
                     "INDEXDSS": indexDSS, 'ID': GD.id(), "LAYER": layer, "nodo": nodo, 'X1': point[0], 'Y1': point[1],
                     'KVA': GD['KVA'], "CURVE1": GD["CURVE1"], "CURVE2": GD["CURVE2"], "TECH": GD["TECH"]}
            grafoGD.add_node(nodo, pos = datos)
        return grafoGD, busBTid, busBT_List

    def ReaderDataLoad(self, layer, datosCAR, grafoCAR, kWhLVload, toler, indexDSS, grafoBTTotal):

        cargas = layer.getFeatures()  # Recibe las caracteristicas de la capa de cargas.
        for carga in cargas:
            point = carga.geometry().asPoint()  # Lee la geometria de la linea
            try:
                group = carga['GRUPO']
            except KeyError:
                group = 'N/A'
            nodo = self.CoordPointProcees(carga, toler)
            datos = {"INDEXDSS": indexDSS, 'ID': carga.id(), "LAYER": layer, "nodo": nodo, 'X1': point[0],
                     'Y1': point[1], 'kWh': carga['KWHMONTH'], 'GRUPO': group, 'kW': 1.0, 'CONNS': '.1.2',
                     'CONF': 'wye', 'CURVASIG': '', 'class': carga['CLASS']}
            datosTotal = {"type": "LOAD"}
            kWhLVload.append(float(carga['KWHMONTH']))
            datosCAR.append(datos)
            grafoCAR.add_node(nodo, pos = datos)
            grafoBTTotal.add_node(nodo, pos = datosTotal)
        return datosCAR, grafoCAR, kWhLVload, grafoBTTotal

    def BusAsignationTraf(self, circuitName, grafo, busMT_List, busMTid, busBT_List, busBTid, tipo, grafoMT):
        graphNodes = list( grafo.nodes(data=True) )
        for NODE in graphNodes:
            print( NODE )
            dataList = NODE[1]
            print( "Data list en Bus asignation Traf = ", dataList )
            nodo = NODE[0]
            BTbus = 'BUSLV' + circuitName + str(busBTid)
            grafo.node[nodo]["BUSBT"] = BTbus
            
            busBT_List[nodo] = {'bus': BTbus, 'X': dataList['pos']["X1"], 'Y': dataList['pos']["Y1"], "GRAFO": grafo, "VOLTAGELN": dataList['pos']["LOADVOLTLN"]}
            busBTid += 1
            if nodo in busMT_List:  # Verifica si el nodo del transformador ya está en los nodos creados en MT
                print( "grafo.node[nodo] = ", grafo.node[nodo] )
                grafo.node[nodo]['pos']["BUSMT"] = busMT_List[nodo]["bus"]
                for secondNode in grafoMT[nodo]:  # itera sobre las lineas que contienen el nodo. Data es el otro nodo de la linea
                    print( "Data Line =", dataLine['weight'] )
                    print( "Data List =", dataList )
                    dataLine = grafoMT[nodo][secondNode]
                    if phaseOperations.trafoPhaseMT(dataLine['weight']['PHASE'], dataList['pos']['PHASE']) == 0:

                        layer = grafo.node[nodo]["LAYER"]
                        indexPhase = auxiliary_functions.getAttributeIndex(self, layer, "PHASEDESIG")
                        indexPowerA = auxiliary_functions.getAttributeIndex(self, layer, "KVAPHASEA")
                        indexPowerB = auxiliary_functions.getAttributeIndex(self, layer, "KVAPHASEB")
                        indexPowerC = auxiliary_functions.getAttributeIndex(self, layer, "KVAPHASEC")
                        grafo.node[nodo]["LAYER"].changeAttributeValue(grafo.node[nodo]["ID"], indexPhase,
                                                                       dataLine['weight']['PHASEDESIG'])
                        ############# Solo se realiza la autocorreción si la línea y el transformador tienen la misma cantidad de fases ######
                        ###CORRECIÓN DE FASE DE TRANSFORMADOR
                        PowerA = float(dataList['pos']["KVA_FA"])
                        PowerB = float(dataList['pos']["KVA_FB"])
                        PowerC = float(dataList['pos']["KVA_FC"])

                        if (dataList['pos']['PHASE'] == ".1.2" and dataLine['weight']['PHASE'] == ".1.3") or (
                                dataList['pos']['PHASE'] == ".1.3" and dataLine['weight']['PHASE'] == ".1.2") or (
                                dataList['pos']['PHASE'] == ".2" and dataLine['weight']['PHASE'] == ".3") or (
                                dataList['pos']['PHASE'] == ".3" and dataLine['weight']['PHASE'] == ".2"):
                            grafo.node[nodo]["LAYER"].changeAttributeValue(grafo.node[nodo]["ID"], indexPowerB, PowerC)
                            grafo.node[nodo]["LAYER"].changeAttributeValue(grafo.node[nodo]["ID"], indexPowerC, PowerB)
                            grafo.node[nodo]["KVA_B"] = PowerC
                            grafo.node[nodo]["KVA_C"] = PowerB
                            aviso = QCoreApplication.translate('dialog',
                                                               u'Conexión entre fases distintas corregida en (') + str(
                                dataList['pos']["X1"]) + ',' + str(dataList['pos']["Y1"]) + QCoreApplication.translate('dialog',
                                                                                                         u'). Línea MT con fase ') + str(
                                dataLine['weight']['PHASE']) + QCoreApplication.translate('dialog',
                                                                                ' y transformador con fase ') + str(
                                dataList['pos']['PHASE'])
                            QgsMessageLog.logMessage(aviso,
                                                     QCoreApplication.translate('dialog', 'Fase de Transformadores'),
                                                     QgsMessageLog.WARNING)
                            grafo.node[nodo]["LAYER"].changeAttributeValue(grafo.node[nodo]["ID"], indexPhase,
                                                                           dataLine['weight']['PHASEDESIG'])
                            grafo.node[nodo]["PHASE"] = dataLine['weight']['PHASE']
                        elif (dataList['pos']['PHASE'] == ".1.2" and dataLine['weight']['PHASE'] == ".2.3") or (
                                dataList['pos']['PHASE'] == ".2.3" and dataLine['weight']['PHASE'] == ".1.2") or (
                                dataList['pos']['PHASE'] == ".1" and dataLine['weight']['PHASE'] == ".3") or (
                                dataList['pos']['PHASE'] == ".3" and dataLine['weight']['PHASE'] == ".1"):
                            grafo.node[nodo]["LAYER"].changeAttributeValue(grafo.node[nodo]["ID"], indexPowerA, PowerC)
                            grafo.node[nodo]["LAYER"].changeAttributeValue(grafo.node[nodo]["ID"], indexPowerC, PowerA)
                            grafo.node[nodo]["KVA_A"] = PowerC
                            grafo.node[nodo]["KVA_C"] = PowerA
                            aviso = QCoreApplication.translate('dialog',
                                                               u'Conexión entre fases distintas corregida en (') + str(
                                dataList['pos']["X1"]) + ',' + str(dataList['pos']["Y1"]) + QCoreApplication.translate('dialog',
                                                                                                         u'). Línea MT con fase ') + str(
                                dataLine['weight']['PHASE']) + QCoreApplication.translate('dialog',
                                                                                ' y transformador con fase ') + str(
                                dataList['pos']['PHASE'])
                            QgsMessageLog.logMessage(aviso,
                                                     QCoreApplication.translate('dialog', 'Fase de Transformadores'),
                                                     QgsMessageLog.WARNING)
                            grafo.node[nodo]["LAYER"].changeAttributeValue(grafo.node[nodo]["ID"], indexPhase,
                                                                           dataLine['weight']['PHASEDESIG'])
                            grafo.node[nodo]["PHASE"] = dataLine['weight']['PHASE']
                        elif (dataList['pos']['pos']['PHASE'] == ".2.3" and dataLine['weight']['PHASE'] == ".1.3") or (
                                dataList['pos']['PHASE'] == ".1.3" and dataLine['weight']['PHASE'] == ".2.3") or (
                                dataList['pos']['PHASE'] == ".2" and dataLine['weight']['PHASE'] == ".1") or (
                                dataList['pos']['PHASE'] == ".1" and dataLine['weight']['PHASE'] == ".2"):
                            grafo.node[nodo]["LAYER"].changeAttributeValue(grafo.node[nodo]["ID"], indexPowerB, PowerA)
                            grafo.node[nodo]["LAYER"].changeAttributeValue(grafo.node[nodo]["ID"], indexPowerA, PowerB)
                            grafo.node[nodo]["KVA_B"] = PowerA
                            grafo.node[nodo]["KVA_A"] = PowerB
                            aviso = QCoreApplication.translate('dialog',
                                                               u'Conexión entre fases distintas corregida en (') + str(
                                dataList['pos']["X1"]) + ',' + str(dataList['pos']["Y1"]) + QCoreApplication.translate('dialog',
                                                                                                         u'). Línea MT con fase ') + str(
                                dataLine['weight']['PHASE']) + QCoreApplication.translate('dialog',
                                                                                ' y transformador con fase ') + str(
                                dataList['pos']['PHASE'])
                            QgsMessageLog.logMessage(aviso,
                                                     QCoreApplication.translate('dialog', 'Fase de Transformadores'),
                                                     QgsMessageLog.WARNING)
                            grafo.node[nodo]["LAYER"].changeAttributeValue(grafo.node[nodo]["ID"], indexPhase,
                                                                           dataLine['weight']['PHASEDESIG'])
                            grafo.node[nodo]["PHASE"] = dataLine['weight']['PHASE']
                        else:
                            aviso = QCoreApplication.translate('dialog', u'Conexión entre fases distintas en (') + str(
                                dataList['pos']["X1"]) + ',' + str(dataList['pos']["Y1"]) + QCoreApplication.translate('dialog',
                                                                                                         u'). Línea MT con fase ') + str(
                                dataLine['weight']['PHASE']) + QCoreApplication.translate('dialog',
                                                                                ' y transformador con fase ') + str(
                                dataList['pos']['PHASE'])
                            QgsMessageLog.logMessage(aviso,
                                                     QCoreApplication.translate('dialog', 'Fase de Transformadores'),
                                                     QgsMessageLog.WARNING)


            else:
                busMTid += 1
                bus = 'BUSMV' + circuitName + str(busMTid)
                busMT_List[nodo] = {"NPHAS": dataList['pos']["NPHAS"], 'bus': bus, 'X': dataList['pos']["X1"], 'Y': dataList['pos']["Y1"],
                                    "GRAFO": grafo, "VOLTAGELL": dataList['pos']["VOLTMTLL"],
                                    "VOLTAGELN": dataList['pos']["VOLTMTLN"], "PHASES": dataList['pos']["PHASE"]}
                grafo.node[nodo]["BUSMT"] = bus
                aviso = QCoreApplication.translate('dialog',
                                                   'Hay 1 transformador ') + tipo + QCoreApplication.translate('dialog',
                                                                                                               ' sin red primaria: (') + str(
                    dataList['pos']["X1"]) + ',' + str(dataList['pos']["Y1"]) + ')'
                QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', 'Alerta Transformadores'), Qgis.Warning) #QgsMessageLog.WARNING
        return grafo, busMT_List, busMTid, busBT_List, busBTid

    def BusAdapterLines(self, GRAFO, SOURCE, DATOS):
#        print("DATOS = ", DATOS)
        nodo1_old = DATOS['weight']['nodo1']  # Recibe el nombre del bus de inicio de la linea
        nodo2_old = DATOS['weight']['nodo2']  # Recibe el nombre del bus de final de la linea
        X1Y1_old = (DATOS['weight']['X1'], DATOS['weight']['Y1'])
        X2Y2_old = (DATOS['weight']['X2'], DATOS['weight']['Y2'])
        EQUAL = False
        if SOURCE == "NULL":
            nodofrom = nodo1_old
            nodoto = nodo2_old
            X1Y1 = X1Y1_old
            X2Y2 = X2Y2_old
            connected = False
        else:
            try:
                dist1 = len(nx.shortest_path(GRAFO, source=SOURCE, target=nodo1_old))
                dist2 = len(nx.shortest_path(GRAFO, source=SOURCE, target=nodo2_old))
                connected = True
                if dist2 == dist1:
                    nodofrom = nodo1_old
                    nodoto = nodo2_old
                    X1Y1 = X1Y1_old
                    X2Y2 = X2Y2_old
                    EQUAL = True
                elif dist1 < dist2:
                    nodofrom = nodo1_old
                    nodoto = nodo2_old
                    X1Y1 = X1Y1_old
                    X2Y2 = X2Y2_old
                elif dist1 > dist2:
                    nodofrom = nodo2_old
                    nodoto = nodo1_old
                    X1Y1 = X2Y2_old
                    X2Y2 = X1Y1_old
            except:
                nodofrom = nodo1_old
                nodoto = nodo2_old
                X1Y1 = X1Y1_old
                X2Y2 = X2Y2_old
                connected = False
                EQUAL = True
        return nodofrom, nodoto, connected, EQUAL, X1Y1, X2Y2

    def IslandIdentification(self, grafoBTTotal, grafoBT, grafoACO, grafoCAR):  ######SI NO FUNCIONA: IMPORTAR LOS GRAFOS A LA FUNCION.
        # iDENTIFICA CUAL ES EL TRANSFORMADOR CONECTADO A CADA LINEA DE BAJA TENSION, ACOMETIDAS Y CARGAS.

        connected_components = list(nx.connected_component_subgraphs(grafoBTTotal))
        
        # print( connected_components )

        for graph in connected_components:
            TrafoNode = "NULL"
            TRAFVOLTLL = "NULL"
            TRAFVOLTLN = "NULL"
            TRAFNPHASES = "NULL"
            
            
            
            for node in list(graph.nodes(data=True)):  # Identifica el nodo del transformador
                #print( "Nodo = ", node, " ............... nodo 0 = ", node[0][0], " nodo 1 = ", node[0][1], " ................ datos = ", node[1] )
                if len(node[1]) != 0 and node[1]['pos']['type'] == 'TRAF':
                    TrafoNode = node[0]
                    TRAFVOLTLL = node[1]['pos']["LOADVOLT"]
                    TRAFVOLTLN = node[1]['pos']["LOADVOLTLN"]
                    TRAFNPHASES = node[1]['pos']["NPHAS"]
                    break
            for edge in list(graph.nodes(data=True)):
                #print( edge )
                if len( edge[1] ) != 0:
                    datos = edge[1]['pos']
                else:
                    {}
                nodo1 = edge[0][0]
                nodo2 = edge[0][1]
                if datos["type"] == "LBT":
                    grafoBT[nodo1][nodo2]["TRAFNODE"] = TrafoNode
                    grafoBT[nodo1][nodo2]["TRAFVOLTLL"] = TRAFVOLTLL
                    grafoBT[nodo1][nodo2]["TRAFVOLTLN"] = TRAFVOLTLN
                    grafoBT[nodo1][nodo2]["TRAFNPHAS"] = TRAFNPHASES
                    # print grafoBT[nodo1][nodo2]["TRAFVOLTLL"]
                elif datos["type"] == "ACO":
                    grafoACO[nodo1][nodo2]["TRAFNODE"] = TrafoNode
                    grafoACO[nodo1][nodo2]["TRAFVOLTLL"] = TRAFVOLTLL
                    grafoACO[nodo1][nodo2]["TRAFVOLTLN"] = TRAFVOLTLN
                    grafoACO[nodo1][nodo2]["TRAFNPHAS"] = TRAFNPHASES

            for vertice in list( graph.nodes(data=True) ):  # Identifica el nodo del transformador
                if len(vertice[1]) != 0 and vertice[1]['pos']['type'] == 'LOAD':
                    datos = vertice[1]
                    nodo = vertice[0]
                    grafoCAR.node[nodo]["TRAFVOLTLN"] = TRAFVOLTLN
                    grafoCAR.node[nodo]["TRAFVOLTLL"] = TRAFVOLTLL
                    grafoCAR.node[nodo]["TRAFNPHAS"] = TRAFNPHASES
        return grafoBT, grafoACO, grafoCAR
        
    #####################################################
    """    
    Esta función lo que hace es pasar de un MultiLineString a una matriz. Se diferencia de la otra función con el mismo nombre en que no
    recibe como parámetro un archivo donde se desee escribir.
    """    
    def MultiStringToMatrix_r(self, MultiLineString):
                
        vector = []
        str_MultiString = str( MultiLineString )

        pos_i = str_MultiString.find( "(" ) + 2
        pos_f = str_MultiString.find( " ", pos_i )
        final_string = str_MultiString.find( ")" ) 
                      
        contador = 1
        
        while pos_i < final_string: #and pos_f != -1:
            numero_str = ""
            numero_str = str_MultiString[pos_i:pos_f]
            numero = float( numero_str )                    
            vector.append(numero)
            
                    
            #Caso de que después siga una coma
            if contador == 1:
                contador = 0
                pos_i = pos_f + 1
                pos_f = str_MultiString.find( ",", pos_f + 2)
                
            #Caso de que siga un espacio
            else:
                contador = 1
                pos_i = pos_f + 2
                pos_f = str_MultiString.find( " ", pos_f + 2)
            
            #Cuando ya se acabó el string
            if pos_f == -1:
                pos_f = final_string
            
         
        
        n = int ( len(vector)/2 )
        #print( n )
        matriz = [[0 for i in range( 2 )] for i in range( n )]
        
        fila = 0
        columna = 0
        pos_vector = 0
        
        for fila in range(0, n):
            for columna in range(0, 2):
                matriz[ fila ][ columna ] = vector[ pos_vector ]
                pos_vector += 1 
                
        
        
        
        n = len( matriz )
            
        
        return matriz
        
    #####################################################

    def run(self):

        """Método que ejecuta las funciones del complemento"""
        # Carga los nombres de las capas actualmente abiertas y las muestra en las listas desplegables
        layers = QgsProject.instance().mapLayers().values()
        layer_list = []

        layer_list.append("")
        for layer in layers:
            layer_list.append(layer.name())
        
        # Se limpian todos los elementos de la interfaz gráfica para asegurar que no permanezcan valores definidos durante una ejecución previa.

        # self.dlg.lineEdit_dirOutput.clear()
        # self.dlg.lineEdit_nameCircuit.clear()
        # self.dlg.lineEdit_AC.clear()

        # self.dlg.comboBox_LMT1.clear()
        # self.dlg.comboBox_LMT2.clear()
        # self.dlg.comboBox_LMT3.clear()
        # self.dlg.comboBox_LBT1.clear()
        # self.dlg.comboBox_LBT2.clear()
        # self.dlg.comboBox_LBT3.clear()
        # self.dlg.comboBox_TR1.clear()
        # self.dlg.comboBox_TR2.clear()
        # self.dlg.comboBox_TR3.clear()
        # self.dlg.comboBox_ACO1.clear()
        # self.dlg.comboBox_ACO2.clear()
        # self.dlg.comboBox_ACO3.clear()
        # self.dlg.comboBox_CA1.clear()
        # self.dlg.comboBox_CA2.clear()
        # self.dlg.comboBox_CA3.clear()
        # self.dlg.comboBox_SE.clear()
        # self.dlg.comboBox_GD.clear()

        # self.dlg.checkBox_LMT1.setCheckState(0)
        # self.dlg.checkBox_LMT2.setCheckState(0)
        # self.dlg.checkBox_LMT3.setCheckState(0)
        # self.dlg.checkBox_LBT1.setCheckState(0)
        # self.dlg.checkBox_LBT2.setCheckState(0)
        # self.dlg.checkBox_LBT3.setCheckState(0)
        # self.dlg.checkBox_AutoTraf.setCheckState(0)
        # self.dlg.noModel.setCheckState(0)
        # self.dlg.Model.setCheckState(1)

        # Se populan las listas desplegables de la interfaz gráfica con la lista de capas disponibles
        # Hacer esto solamente si la cantidad de items es cero
        if self.dlg.comboBox_LMT1.count() == 0:
            self.dlg.comboBox_LMT1.addItems(layer_list)
            self.dlg.comboBox_LMT2.addItems(layer_list)
            self.dlg.comboBox_LMT3.addItems(layer_list)
            self.dlg.comboBox_LBT1.addItems(layer_list)
            self.dlg.comboBox_LBT2.addItems(layer_list)
            self.dlg.comboBox_LBT3.addItems(layer_list)
            self.dlg.comboBox_TR1.addItems(layer_list)
            self.dlg.comboBox_TR2.addItems(layer_list)
            self.dlg.comboBox_TR3.addItems(layer_list)
            self.dlg.comboBox_ACO1.addItems(layer_list)
            self.dlg.comboBox_ACO2.addItems(layer_list)
            self.dlg.comboBox_ACO3.addItems(layer_list)
            self.dlg.comboBox_CA1.addItems(layer_list)
            self.dlg.comboBox_CA2.addItems(layer_list)
            self.dlg.comboBox_CA3.addItems(layer_list)
            self.dlg.comboBox_SE.addItems(layer_list)
            self.dlg.comboBox_GD.addItems(layer_list)
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        circuitName = self.dlg.lineEdit_nameCircuit.text().upper()  # Recibe el nombre del circuito indicado en la ventana de dialogo.
        foldername = self.dlg.lineEdit_dirOutput.text()  # Almacena el nombre de la carpeta de destino seleccionada en la ventana de diálogo.
        folder_profile = self.dlg.lineEdit_AC.text()
        cargas1 = self.dlg.comboBox_CA1.currentIndex()
        cargas2 = self.dlg.comboBox_CA2.currentIndex()
        cargas3 = self.dlg.comboBox_CA3.currentIndex()
        cargas = cargas1 + cargas2 + cargas3

        MTL1 = self.dlg.comboBox_LMT1.currentIndex()
        MTL2 = self.dlg.comboBox_LMT2.currentIndex()
        MTL3 = self.dlg.comboBox_LMT3.currentIndex()
        MTL = MTL1 + MTL2 + MTL3

        BTL1 = self.dlg.comboBox_LBT1.currentIndex() + self.dlg.comboBox_ACO1.currentIndex()
        BTL2 = self.dlg.comboBox_LBT2.currentIndex() + self.dlg.comboBox_ACO2.currentIndex()
        BTL3 = self.dlg.comboBox_LBT3.currentIndex() + self.dlg.comboBox_ACO3.currentIndex()
        BTL = BTL1 + BTL2 + BTL3

        tx1 = self.dlg.comboBox_TR1.currentIndex()
        tx2 = self.dlg.comboBox_TR2.currentIndex()
        tx3 = self.dlg.comboBox_TR3.currentIndex()
        TX = tx1 + tx2 + tx3
        projPath = str(QgsProject.instance().homePath())
        
        SubsNode = NULL

        # Verifica que se haya indicado el nombre del circuito, la carpeta de destino y se ejecuta al presionar OK.

        if result and (not projPath):
            QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog',
                                                                                        u"La operación no se pudo completar") + "\n" + QCoreApplication.translate(
                'dialog', "Debe crear un proyecto de QGIS"))
        elif result and (
                not circuitName or not foldername):  # Se asegura de que el complemento se ejecute solo si se tiene completa la informacin necesaria
            QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog',
                                                                                        u"La operación no se pudo completar") + "\n" + QCoreApplication.translate(
                'dialog', "Debe indicar el nombre del circuito y la carpeta de destino"))
        elif result and (self.dlg.comboBox_SE.currentIndex() == 0) and (MTL != 0):
            QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog',
                                                                                        u"La operación no se pudo completar") + "\n" + QCoreApplication.translate(
                'dialog', u"Debe seleccionar la capa de la subestación"))

        elif result and (self.dlg.comboBox_SE.currentIndex() == 0) and TX == 0:
            QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog',
                                                                                        u"La operación no se pudo completar") + "\n" + QCoreApplication.translate(
                'dialog', u"Al menos debe seleccionar la capa de la subestación o transformadores"))

        elif result and (BTL != 0) and TX == 0:
            QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog',
                                                                                        u"La operación no se pudo completar") + "\n" + QCoreApplication.translate(
                'dialog', "Debe seleccionar la capa de la transformadores"))
        elif result and not folder_profile and cargas > 0:
            QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog',
                                                                                        u"La operación no se pudo completar") + "\n" + QCoreApplication.translate(
                'dialog', "Para modelar la carga debe ingresar la carpeta de perfiles"))
        elif result and circuitName and foldername:
            self.progress.show()
            self.progress.progressBar.setRange(0, 100)
            self.progress.progressBar.setValue(0)

            startpluginTime = timeit.default_timer()  # starts runTime counter

            Error = False  # Se inicializa esta variable. Cambia a True si ocurre un error crítico.
            # Time meters init
            startTime = time.time()
            toler = 0.1  # tolerancia para los grafos en metros
            grafoBTTotal = nx.Graph()
            """1-Se inicia contador de barras MT y BT"""
            busnumMT = 1  # inicializa contador de barras de MT
            busnumBT = 1  # inicializa contador de barras de BT
            # 2.1-Crea lista con las coordenadas de Inicio, Final y Fase de las lineas de media tension.
            
            """
            
            selectedLayerMT1 = "Linea_MT"
            selectedLayerMT2 = ""
            selectedLayerMT3 = ""
            
            """
            
            selectedLayerMT1 = self.dlg.comboBox_LMT1.currentText()  # Índice de layer_list con lineas MT seleccionada en la lista desplegable
            selectedLayerMT2 = self.dlg.comboBox_LMT2.currentText()  # Índice de layer_list con lineas MT seleccionada en la lista desplegable
            selectedLayerMT3 = self.dlg.comboBox_LMT3.currentText()  # Índice de layer_list con lineas MT seleccionada en la lista desplegable
            
            
            busMT_List = {}  # Lista de Bus MT
            busMTid = 1
            busBT_List = {}  # Lista de Bus BT

            ###Crea lista con datos de subestación
            
            #selectedLayerSE = 'subest_Santos'
            
            selectedLayerSE = self.dlg.comboBox_SE.currentText()  # Recibe la capa de subestación seleccionada en la lista desplegable
            
            
            
            datosSE = []
            grafoSubt = nx.Graph()
            grafoMT = nx.Graph()
            startTimeSub = time.time()
            SEactive = False
            try:  ## Lectura de datos de subestación
                # if 1==1:
                if len(selectedLayerSE) != 0:
                    layerSE = QgsProject.instance().mapLayersByName(selectedLayerSE)[0] #Se selecciona la capa de la base de datos "layers" según el índice de layer_list
                    
                    if self.dlg.Model.isChecked():
                        mode = "MODEL"
                    elif self.dlg.checkBox_AutoTraf.isChecked():
                        mode = "AUTO"
                    elif self.dlg.noModel.isChecked():
                        mode = "NOMODEL"

                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerSE, "DSSName")
                    subests = layerSE.getFeatures()  # Recibe las caracteristicas de la capa de subestación.
                    for subest in subests:
                        point = subest.geometry().asPoint()  # Lee la geometria de la linea
                        node = self.CoordPointProcees(subest, toler)
                        CONEXIONAL = ''
                        CONEXIONME = ''
                        CONEXIONBA = ''
                        TAPS = ''
                        MINTAP = ''
                        MAXTAP = ''
                        print("Subest ", subest )
                        VOLTAJEMEDLN = str(float(subest['MEDVOLT']) / sqrt(3))
                        if mode == "MODEL":
                            if subest['HIGHCONN'] == 'Y':
                                CONEXIONAL = 'wye'
                            if subest['HIGHCONN'] == 'D':
                                CONEXIONAL = 'delta'
                            if subest['MEDCONN'] == 'Y':
                                CONEXIONME = 'wye'
                            if subest['MEDCONN'] == 'D':
                                CONEXIONME = 'delta'
                            if int(subest['TAPS']) > 0:
                                TAPS = subest['TAPS']
                                TAP_MAX_MIN = str(subest['TAPMAX/MI'])
                                TAP_MAX_MIN = TAP_MAX_MIN.split('/')
                                MINTAP = TAP_MAX_MIN[1]
                                MAXTAP = TAP_MAX_MIN[0]
                            setTap = str(subest['TAPSETTING'])
                            if subest['WINDINGS'] == 3:
                                # voltLow =
                                if subest['LOWCONN'] == 'Y':
                                    CONEXIONBA = 'wye'
                                if subest['LOWCONN'] == 'D':
                                    CONEXIONBA = 'delta'
                                datos = {"INDEXDSS": indexDSS, "LAYER": layerSE, "TAP": setTap, "ID": subest.id(),
                                         'X1': point[0], 'Y1': point[1], 'VOLTAJEALT': subest['HIGHVOLT'],
                                         'VOLTAJEMED': subest['MEDVOLT'], 'VOLTAJEMEDLN': VOLTAJEMEDLN,
                                         'VOLTAJEBAJ': subest['LOWVOLT'], 'CONEXIONAL': CONEXIONAL,
                                         'CONEXIONME': CONEXIONME, 'CONEXIONBA': CONEXIONBA,
                                         'KVA_ALTA': subest['KVAHIGH'], 'KVA_MEDIA': subest['KVAMED'],
                                         'KVA_BAJA': subest['KVALOW'], 'PHASEDESIG': '.1.2.3',
                                         'WINDINGS': subest['WINDINGS'], 'TAPS': TAPS, 'MINTAP': MINTAP,
                                         'MAXTAP': MAXTAP, 'XHL': subest['XHL'], 'XHT': subest['XHT'],
                                         'XLT': subest['XLT']}
                            else:
                                datos = {"INDEXDSS": indexDSS, "LAYER": layerSE, "TAP": setTap, "ID": subest.id(),
                                         'X1': point[0], 'Y1': point[1], 'VOLTAJEALT': subest['HIGHVOLT'],
                                         'VOLTAJEMED': subest['MEDVOLT'], 'VOLTAJEMEDLN': VOLTAJEMEDLN,
                                         'VOLTAJEBAJ': '', 'CONEXIONAL': CONEXIONAL, 'CONEXIONME': CONEXIONME,
                                         'CONEXIONBA': '', 'KVA_ALTA': subest['KVAHIGH'], 'KVA_MEDIA': subest['KVAMED'],
                                         'KVA_BAJA': '', 'PHASEDESIG': '.1.2.3', 'WINDINGS': subest['WINDINGS'],
                                         'TAPS': TAPS, 'MINTAP': MINTAP, 'MAXTAP': MAXTAP, 'XHL': subest['XHL'],
                                         'XHT': subest['XHT'], 'XLT': subest['XLT']}
                            datosSE.append(datos)
                        if mode == "AUTO":
                            if int(subest['TAPS']) > 0:
                                TAPS = subest['TAPS']
                                TAP_MAX_MIN = str(subest['TAPMAX/MI'])
                                TAP_MAX_MIN = TAP_MAX_MIN.split('/')
                                MINTAP = TAP_MAX_MIN[1]
                                MAXTAP = TAP_MAX_MIN[0]
                            setTap = str(subest['TAPSETTING'])
                            datos = {"INDEXDSS": indexDSS, "LAYER": layerSE, "TAP": setTap, "ID": subest.id(),
                                     'X1': point[0], 'Y1': point[1], 'VOLTAJEALT': subest['HIGHVOLT'],
                                     "VOLTAJEMEDLN": int(subest['MEDVOLT']) / sqrt(3), 'VOLTAJEMED': subest['MEDVOLT'],
                                     'KVA_ALTA': subest['KVAHIGH'], 'KVA_MEDIA': subest['KVAMED'], 'TAPS': TAPS,
                                     'MINTAP': MINTAP, 'MAXTAP': MAXTAP, 'XHL': subest['XHL']}

                        if mode == "NOMODEL":
                            datos = {"INDEXDSS": indexDSS, "LAYER": layerSE, "ID": subest.id(), 'X1': point[0],
                                     'Y1': point[1], 'VOLTAJEMED': subest['MEDVOLT'], 'VOLTAJEMEDLN': VOLTAJEMEDLN, }
                        SubsNode = node
                        grafoSubt.add_node(node, pos = datos)
                        grafoMT.add_node(node, pos = datos)

                    if grafoSubt.number_of_nodes() == 0:
                        SEactive = False
                    else:
                        SEactive = True
                        for NODE in list( grafoSubt.nodes(data=True) ):
                            dataList = NODE[1]
                            
                            nodo = NODE[0]
                            bus = 'BUSMV' + circuitName + str(busMTid)
                            busMT_List[nodo] = {'bus': bus, 'X': dataList['pos']["X1"], 'Y': dataList['pos']["Y1"],
                                                "GRAFO": grafoSubt, "VOLTAGELN": dataList['pos']["VOLTAJEMEDLN"], "NPHAS": "3"}
                            grafoSubt.node[nodo]['pos']["BUSMT"] = bus
                            busMTid += 1

            except KeyError:
                
                exc_info = sys.exc_info()
                print("Error: ", exc_info )
                print("*************************  Información detallada del error ********************")
                print("********************************************************************************")
                
                for tb in traceback.format_tb(sys.exc_info()[2]):
                    print(tb)
                
                QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog',
                                                                                            "Verifique los nombres de las columnas") + "\n" + QCoreApplication.translate(
                    'dialog', "de la tabla de atributos de subestación"))
                SEactive = False
                Error = True

            endTimeSub = time.time()

            try:  ###Lectura y Conectividad de media tensión
                # if 1==1:

                datosLMT = []
                if len(selectedLayerMT1) != 0:
                    
                    layerMT1 = QgsProject.instance().mapLayersByName(selectedLayerMT1)[
                        0]  # Se selecciona la capa de la base de datos "layers" según el índice de layer_list
                    if self.dlg.checkBox_LMT1.isChecked():  # Determina si la línea es aérea o subterránea
                        subterranea = True
                    else:
                        subterranea = False
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerMT1, "DSSName")
                    grafoMT, datosLMT = self.ReaderDataLMT(layerMT1, grafoMT, datosLMT, toler, subterranea, indexDSS)

                if len(selectedLayerMT2) != 0:
                    layerMT2 = QgsProject.instance().mapLayersByName(selectedLayerMT2)[
                        0]  # Se selecciona la capa de la base de datos "layers" según el índice de layer_list
                    if self.dlg.checkBox_LMT2.isChecked():  # Determina si la línea es aérea o subterránea
                        subterranea = True
                    else:
                        subterranea = False
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerMT2, "DSSName")
                    grafoMT, datosLMT = self.ReaderDataLMT(layerMT2, grafoMT, datosLMT, toler, subterranea, indexDSS)

                if len(selectedLayerMT3) != 0:
                    layerMT3 = QgsProject.instance().mapLayersByName(selectedLayerMT3)[
                        0]  # Se selecciona la capa de la base de datos "layers" según el índice de layer_list
                    if self.dlg.checkBox_LMT3.isChecked():  # Determina si la línea es aérea o subterránea
                        subterranea = True
                    else:
                        subterranea = False
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerMT3, "DSSName")
                    grafoMT, datosLMT = self.ReaderDataLMT(layerMT3, grafoMT, datosLMT, toler, subterranea, indexDSS)
                if grafoMT.number_of_edges() == 0:
                    LMTactive = False
                              
                else:  # Se identifica la conectividad de las líneas de Media Tensión.
                    startTimeMT = time.time()
                    LMTactive = True
                    nodesMT = grafoMT.nodes()  # guarda todos los nodos del grafoMT en una lista
                    ################## Asignación de Bus a líneas MT
                    for node in nodesMT:  # node es el nodo en nombramiento
                        i = 1
                        #print( " --------------------------------------------------------------------- ")
                        #print( grafoMT[ node ] )
                        for secondNode in grafoMT[
                            node]:  # itera sobre las lineas que contienen el nodo. Data es el otro nodo de la linea
                            dataLine = grafoMT[node][secondNode]  # info de la linea
                            
                            if dataLine['weight']['PHASE'] == '.1.2.3':
                                if node in busMT_List:
                                    bus = busMT_List[node]['bus']
                                else:
                                    bus = 'BUSMV' + circuitName + str(busMTid)
                                    busMTid += 1

                                nodeFrom, nodeTo, connec, EQUAL, X1Y1, X2Y2 = self.BusAdapterLines(grafoMT, SubsNode, dataLine)
                                dataLine['X1'] = X1Y1[0]
                                dataLine['Y1'] = X1Y1[1]
                                dataLine['X2'] = X2Y2[0]
                                dataLine['Y2'] = X2Y2[1]
                                dataLine['nodo1'] = nodeFrom
                                dataLine['nodo2'] = nodeTo
                                if dataLine['nodo1'] == dataLine['nodo2']:
                                    dataLine['bus1'] = bus  # Agrega el bus1 al grafoMT
                                    dataLine['bus2'] = bus  # Agrega el bus1 al grafoMT
                                    if node not in busMT_List:
                                        busMT_List[node] = {"NPHAS": dataLine['weight']["NPHAS"], 'bus': bus, 'X': dataLine['weight']['X1'],
                                                            'Y': dataLine['weight']['Y1'], "GRAFO": grafoMT,
                                                            "VOLTAGELL": dataLine['weight']["VOLTOPRLL"],
                                                            "VOLTAGELN": dataLine['weight']["VOLTOPRLN"],
                                                            "PHASES": dataLine['weight']["PHASE"]}  #
                                    aviso = QCoreApplication.translate('dialog',
                                                                       u'Existe una línea de MT con bus1 igual a bus2 dada su cercanía en (') + str(
                                        busMT_List[node]['X']) + ', ' + str(busMT_List[node]['Y']) + ')'
                                    QgsMessageLog.logMessage(aviso,
                                                             QCoreApplication.translate('dialog', u'Líneas primarias'),
                                                             QgsMessageLog.WARNING)
                                elif node == dataLine['nodo1']:  #############CONDICION DE MAS CERCANO
                                    dataLine['bus1'] = bus  # Agrega el bus1 al grafoMT
                                    if node not in busMT_List:
                                        busMT_List[node] = {"NPHAS": dataLine['weight']["NPHAS"], 'bus': bus, 'X': dataLine['weight']['X1'],
                                                            'Y': dataLine['weight']['Y1'], "GRAFO": grafoMT,
                                                            "VOLTAGELL": dataLine['weight']["VOLTOPRLL"],
                                                            "VOLTAGELN": dataLine['weight']["VOLTOPRLN"],
                                                            "PHASES": dataLine['weight']["PHASE"]}  #
                                elif node == dataLine['nodo2']:  #############CONDICION DE MAS CERCANO
                                    dataLine['bus2'] = bus  # Agrega el bus2 al grafoMT
                                    if node not in busMT_List:
                                        busMT_List[node] = {"NPHAS": dataLine['weight']["NPHAS"], 'bus': bus, 'X': dataLine['weight']['X2'],
                                                            'Y': dataLine['weight']['Y2'], "GRAFO": grafoMT,
                                                            "VOLTAGELL": dataLine['weight']["VOLTOPRLL"],
                                                            "VOLTAGELN": dataLine['weight']["VOLTOPRLN"],
                                                            "PHASES": dataLine['weight']["PHASE"]}

                                # otherNodes = grafoMT[node].keys()
                                # for j in range(i, len(otherNodes)):

                                i += 1

                            else:
                                pass
                    for node in nodesMT:  # node es el nodo en nombramiento
                        i = 1
                        for secondNode in grafoMT[
                            node]:  # itera sobre las lineas que contienen el nodo. secondNode es el otro nodo de la linea
                            dataLine = grafoMT[node][secondNode]  # info de la linea
                            if dataLine['weight']['PHASE'] == '.1.2' or dataLine['weight']['PHASE'] == '.2.3' or dataLine['weight']['PHASE'] == '.1.3':
                                if node in busMT_List:
                                    bus = busMT_List[node]['bus']
                                else:
                                    bus = 'BUSMV' + circuitName + str(busMTid)
                                    busMTid += 1

                                nodeFrom, nodeTo, connec, EQUAL, X1Y1, X2Y2 = self.BusAdapterLines(grafoMT, SubsNode, dataLine)
                                dataLine['weight']['X1'] = X1Y1[0]
                                dataLine['weight']['Y1'] = X1Y1[1]
                                dataLine['weight']['X2'] = X2Y2[0]
                                dataLine['weight']['Y2'] = X2Y2[1]
                                dataLine['weight']['nodo1'] = nodeFrom
                                dataLine['weight']['nodo2'] = nodeTo
                                if dataLine['weight']['nodo1'] == dataLine['weight']['nodo2']:
                                    dataLine['weight']['bus1'] = bus  # Agrega el bus1 al grafoMT
                                    dataLine['weight']['bus2'] = bus  # Agrega el bus1 al grafoMT
                                    if node not in busMT_List:
                                        busMT_List[node] = {"NPHAS": dataLine['weight']["NPHAS"], 'bus': bus, 'X': dataLine['weight']['X1'],
                                                            'Y': dataLine['weight']['Y1'], "GRAFO": grafoMT,
                                                            "VOLTAGELL": dataLine['weight']["VOLTOPRLL"],
                                                            "VOLTAGELN": dataLine['weight']["VOLTOPRLN"],
                                                            "PHASES": dataLine['weight']["PHASE"]}  #
                                    aviso = QCoreApplication.translate('dialog',
                                                                       u'Existe una línea de MT con bus1 igual a bus2 dada su cercanía en (') + str(
                                        busMT_List[node]['X']) + ', ' + str(busMT_List[node]['Y']) + ')'
                                    QgsMessageLog.logMessage(aviso,
                                                             QCoreApplication.translate('dialog', u'Líneas primarias'),
                                                             QgsMessageLog.WARNING)
                                elif node == dataLine['weight']['nodo1']:
                                    dataLine['weight']['bus1'] = bus  # Agrega el bus1 al grafoMT
                                    if node not in busMT_List:
                                        busMT_List[node] = {"NPHAS": dataLine['weight']["NPHAS"], 'bus': bus, 'X': dataLine['weight']['X1'],
                                                            'Y': dataLine['weight']['Y1'], "GRAFO": grafoMT,
                                                            "VOLTAGELL": dataLine['weight']["VOLTOPRLL"],
                                                            "VOLTAGELN": dataLine['weight']["VOLTOPRLN"],
                                                            "PHASES": dataLine['weight']["PHASE"]}  #
                                elif node == dataLine['weight']['nodo2']:
                                    dataLine['weight']['bus2'] = bus  # Agrega el bus2 al grafoMT
                                    if node not in busMT_List:
                                        busMT_List[node] = {"NPHAS": dataLine['weight']["NPHAS"], 'bus': bus, 'X': dataLine['weight']['X2'],
                                                            'Y': dataLine['weight']['Y2'], "GRAFO": grafoMT,
                                                            "VOLTAGELL": dataLine['weight']["VOLTOPRLL"],
                                                            "VOLTAGELN": dataLine['weight']["VOLTOPRLN"],
                                                            "PHASES": dataLine['weight']["PHASE"]}

                                i += 1
                            else:
                                pass
                    for node in nodesMT:  # node es el nodo en nombramiento
                        i = 1
                        for secondNode in grafoMT[
                            node]:  # itera sobre las lineas que contienen el nodo. Data es el otro nodo de la linea
                            dataLine = grafoMT[node][secondNode]  # info de la linea
                            if dataLine['weight']['PHASE'] == '.1' or dataLine['weight']['PHASE'] == '.2' or dataLine['weight']['PHASE'] == '.3':
                                if node in busMT_List:
                                    bus = busMT_List[node]['bus']
                                else:
                                    bus = 'BUSMV' + circuitName + str(busMTid)
                                    busMTid += 1

                                nodeFrom, nodeTo, connec, EQUAL, X1Y1, X2Y2 = self.BusAdapterLines(grafoMT, SubsNode, dataLine)
                                dataLine['weight']['X1'] = X1Y1[0]
                                dataLine['weight']['Y1'] = X1Y1[1]
                                dataLine['weight']['X2'] = X2Y2[0]
                                dataLine['weight']['Y2'] = X2Y2[1]
                                dataLine['weight']['nodo1'] = nodeFrom
                                dataLine['weight']['nodo2'] = nodeTo
                                if dataLine['weight']['nodo1'] == dataLine['weight']['nodo2']:
                                    dataLine['weight']['bus1'] = bus  # Agrega el bus1 al grafoMT
                                    dataLine['weight']['bus2'] = bus  # Agrega el bus1 al grafoMT
                                    if node not in busMT_List:
                                        busMT_List[node] = {"NPHAS": dataLine['weight']["NPHAS"], 'bus': bus, 'X': dataLine['weight']['X1'],
                                                            'Y': dataLine['weight']['Y1'], "GRAFO": grafoMT,
                                                            "VOLTAGELL": dataLine['weight']["VOLTOPRLL"],
                                                            "VOLTAGELN": dataLine['weight']["VOLTOPRLN"],
                                                            "PHASES": dataLine['weight']["PHASE"]}  #
                                    aviso = QCoreApplication.translate('dialog',
                                                                       u'Existe una línea de MT con bus1 igual a bus2 dada su cercanía en (') + str(
                                        busMT_List[node]['X']) + ', ' + str(busMT_List[node]['Y']) + ')'
                                    QgsMessageLog.logMessage(aviso,
                                                             QCoreApplication.translate('dialog', u'Líneas primarias'),
                                                             QgsMessageLog.WARNING)
                                elif node == dataLine['weight']['nodo1']:
                                    dataLine['weight']['bus1'] = bus  # Agrega el bus1 al grafoMT
                                    if node not in busMT_List:
                                        busMT_List[node] = {"NPHAS": dataLine['weight']["NPHAS"], 'bus': bus, 'X': dataLine['weight']['X1'],
                                                            'Y': dataLine['weight']['Y1'], "GRAFO": grafoMT,
                                                            "VOLTAGELL": dataLine['weight']["VOLTOPRLL"],
                                                            "VOLTAGELN": dataLine['weight']["VOLTOPRLN"],
                                                            "PHASES": dataLine['weight']["PHASE"]}  #
                                elif node == dataLine['weight']['nodo2']:
                                    dataLine['weight']['bus2'] = bus  # Agrega el bus2 al grafoMT
                                    if node not in busMT_List:
                                        busMT_List[node] = {"NPHAS": dataLine['weight']["NPHAS"], 'bus': bus, 'X': dataLine['weight']['X2'],
                                                            'Y': dataLine['weight']['Y2'], "GRAFO": grafoMT,
                                                            "VOLTAGELL": dataLine['weight']["VOLTOPRLL"],
                                                            "VOLTAGELN": dataLine['weight']["VOLTOPRLN"],
                                                            "PHASES": dataLine['weight']["PHASE"]}
                                i += 1

                    for node in nodesMT:  # Revisión de fases entre líneas
                        for secondNode in grafoMT[node]:
                            print( "grafoMT[node] = ", grafoMT[node] )
                            otherNodes = list(grafoMT[node].keys())
                            for j in range(i, len(otherNodes)):
                                if secondNode != list(grafoMT[node].keys())[-1] and grafoMT[node][secondNode] != \
                                        grafoMT[node][otherNodes[j]]:  # Evita comparar líneas 2 veces o más
                                    if (node == grafoMT[node][secondNode]['weight']['nodo1']) and ( node == grafoMT[node][otherNodes[j]]['weight']['nodo2']):
                                        NodoLineaCerc = otherNodes[j]
                                        NodoLinealejan = secondNode
                                        if (phaseOperations.linePhaseMT(grafoMT[node][NodoLineaCerc]['PHASE'],
                                                                        grafoMT[node][NodoLinealejan]['PHASE']) == 0):
                                            aviso = QCoreApplication.translate('dialog',
                                                                               u'Conexión de fases distintas en (') + str(
                                                busMT_List[node]['X']) + ',' + str(
                                                busMT_List[node]['Y']) + QCoreApplication.translate('dialog',
                                                                                                    u'). Línea MT ') + str(
                                                grafoMT[node][secondNode]['NPHAS']) + QCoreApplication.translate(
                                                'dialog', 'F con fase ') + str(
                                                grafoMT[node][secondNode]['PHASE']) + QCoreApplication.translate(
                                                'dialog', ' y MT ') + str(
                                                grafoMT[node][otherNodes[j]]['NPHAS']) + QCoreApplication.translate(
                                                'dialog', 'F con fase ') + str(grafoMT[node][otherNodes[j]]['PHASE'])
                                            QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog',
                                                                                                       u'Líneas primarias'),
                                                                     QgsMessageLog.WARNING)
                                    elif (node == grafoMT[node][secondNode]['nodo2']) and (node == grafoMT[node][otherNodes[j]]['nodo1']):
                                        NodoLineaCerc = secondNode
                                        NodoLinealejan = otherNodes[j]
                                        if (phaseOperations.linePhaseMT(grafoMT[node][NodoLineaCerc]['PHASE'],
                                                                        grafoMT[node][NodoLinealejan]['PHASE']) == 0):
                                            aviso = QCoreApplication.translate('dialog',
                                                                               u'Conexión de fases distintas en (') + str(
                                                busMT_List[node]['X']) + ',' + str(
                                                busMT_List[node]['Y']) + QCoreApplication.translate('dialog',
                                                                                                    u'). Línea MT ') + str(
                                                grafoMT[node][secondNode]['NPHAS']) + QCoreApplication.translate(
                                                'dialog', 'F con fase ') + str(
                                                grafoMT[node][secondNode]['PHASE']) + QCoreApplication.translate(
                                                'dialog', ' y MT ') + str(
                                                grafoMT[node][otherNodes[j]]['NPHAS']) + QCoreApplication.translate(
                                                'dialog', 'F con fase ') + str(grafoMT[node][otherNodes[j]]['PHASE'])
                                            QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog',
                                                                                                       u'Líneas primarias'),
                                                                     QgsMessageLog.WARNING)

                    i += 1
                endTimeMT = time.time()
            except KeyError:  # Si los nombres de las columnas no son correctos, el programa genera un aviso y no se ejecuta
                exc_info = sys.exc_info()
                print("Error: ", exc_info )
                print("*************************  Información detallada del error ********************")
                print("********************************************************************************")
                
                for tb in traceback.format_tb(sys.exc_info()[2]):
                    print(tb)
                
                QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog',
                                                                                            "Verifique los nombres de las columnas de las tablas de atributos de líneas de media tensión"))
                LMTactive = False
                Error = True

            self.progress.progressBar.setValue(10)
            ################################################################## Transformadores Grafos
            
            """
            
            selectedLayerTR1 = "Transformadores"
            selectedLayerTR2 = ""
            selectedLayerTR3 = ""
            
            """
            
            selectedLayerTR1 = self.dlg.comboBox_TR1.currentText()  # Recibe la capa con transformadores seleccionada en la lista desplegable
            selectedLayerTR2 = self.dlg.comboBox_TR2.currentText()  # Recibe la capa con transformadores seleccionada en la lista desplegable
            selectedLayerTR3 = self.dlg.comboBox_TR3.currentText()  # Recibe la capa con transformadores seleccionada en la lista desplegable
            
            
            

            datosT1F = []
            datosT2F = []
            datosT3F_Multi = []
            datosT3F_Single = []
            Graph_T1F = nx.Graph()
            Graph_T2F = nx.Graph()
            Graph_T3F_multi = nx.Graph()
            Graph_T3F_single = nx.Graph()
            busBTid = 1

            try:  ## Lectura y CONECTIVIDAD TRANSFORMADORES
                # if 1==1:
                #### Lectura de datos y creación de grafos de transformadores
                if len(selectedLayerTR1) != 0:
                    layerT1 = QgsProject.instance().mapLayersByName(selectedLayerTR1)[0]
                    layerT1.startEditing()
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerT1, "DSSName")
                    datosT3F_Multi, datosT3F_Single, datosT2F, datosT1F, Graph_T3F_multi, Graph_T3F_single, Graph_T2F, Graph_T1F, grafoBTTotal = self.ReaderDataTrafos(
                        layerT1, toler, datosT3F_Multi, datosT3F_Single, datosT2F, datosT1F, Graph_T3F_multi,
                        Graph_T3F_single, Graph_T2F, Graph_T1F, indexDSS, grafoBTTotal)

                if len(selectedLayerTR2) != 0:
                    layerT2 = QgsProject.instance().mapLayersByName(selectedLayerTR2)[0]
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerT2, "DSSName")
                    datosT3F_Multi, datosT3F_Single, datosT2F, datosT1F, Graph_T3F_multi, Graph_T3F_single, Graph_T2F, Graph_T1F, grafoBTTotal = self.ReaderDataTrafos(
                        layerT2, toler, datosT3F_Multi, datosT3F_Single, datosT2F, datosT1F, Graph_T3F_multi,
                        Graph_T3F_single, Graph_T2F, Graph_T1F, indexDSS, grafoBTTotal)
                    layerT2.startEditing()
                if len(selectedLayerTR3) != 0:
                    layerT3 = QgsProject.instance().mapLayersByName(selectedLayerTR3)[0]
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerT3, "DSSName")
                    datosT3F_Multi, datosT3F_Single, datosT2F, datosT1F, Graph_T3F_multi, Graph_T3F_single, Graph_T2F, Graph_T1F, grafoBTTotal = self.ReaderDataTrafos(
                        layerT3, toler, datosT3F_Multi, datosT3F_Single, datosT2F, datosT1F, Graph_T3F_multi,
                        Graph_T3F_single, Graph_T2F, Graph_T1F, indexDSS, grafoBTTotal)
                    layerT3.startEditing()
                if (len(datosT1F) == 0 and len(datosT2F) == 0 and len(datosT3F_Multi) == 0 and len(
                        datosT3F_Single) == 0):
                    LTRactive = False
                else:  ##### Asignación de bus a transformadores
                    startTimeTraf = time.time()
                    LTRactive = True
                    if Graph_T1F.number_of_nodes() > 0:  # Verifica que existen transformadores monofásicos
                        Graph_T1F, busMT_List, busMTid, busBT_List, busBTid = self.BusAsignationTraf(circuitName, Graph_T1F, busMT_List, busMTid, busBT_List, busBTid, u"monofásico", grafoMT)
                    if Graph_T3F_multi.number_of_nodes() > 0:  # Verifica que existen transformadores trifásicos de 3 unidades monofásicas
                        Graph_T3F_multi, busMT_List, busMTid, busBT_List, busBTid = self.BusAsignationTraf(circuitName, Graph_T3F_multi, busMT_List, busMTid, busBT_List, busBTid, u"trifásico", grafoMT)
                    if Graph_T3F_single.number_of_nodes() > 0:  # Verifica que existen transformadores trifásicos de 1 unidad
                        Graph_T3F_single, busMT_List, busMTid, busBT_List, busBTid = self.BusAsignationTraf(circuitName, Graph_T3F_single, busMT_List, busMTid, busBT_List, busBTid, u"trifásico", grafoMT)
                    if Graph_T2F.number_of_nodes() > 0:  # Verifica que existen transformadores bifásicos
                        Graph_T2F, busMT_List, busMTid, busBT_List, busBTid = self.BusAsignationTraf(circuitName, Graph_T2F, busMT_List, busMTid, busBT_List, busBTid, u"bifásico", grafoMT)

            except KeyError:
                
                exc_info = sys.exc_info()
                print("Error: ", exc_info )
                print("*************************  Información detallada del error ********************")
                print("********************************************************************************")
                
                for tb in traceback.format_tb(sys.exc_info()[2]):
                    print(tb)
                
                QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog', "Verifique los nombres de las columnas") + "\n" + QCoreApplication.translate('dialog', "de las tablas de atributos de transformadores"))
                
                

                    
                    
                    
                LTRactive = False
                Error = True
            endTimeTraf = time.time()
            self.progress.progressBar.setValue(20)
            ############################################## Baja tensión
            
            """
            
            selectedLayerBT1 = "Linea_BT"
            selectedLayerBT2 = ""
            selectedLayerBT3 = ""
            
            """
            
            selectedLayerBT1 = self.dlg.comboBox_LBT1.currentText()  # Índice de layer_list con lineas BT seleccionada en la lista desplegable
            selectedLayerBT2 = self.dlg.comboBox_LBT2.currentText()  # Índice de layer_list con lineas BT seleccionada en la lista desplegable
            selectedLayerBT3 = self.dlg.comboBox_LBT3.currentText()  # Índice de layer_list con lineas BT seleccionada en la lista desplegable
            
            
            
            datosLBT = []  # datosLBT guarda informacion de ubicacion y fase de las lineas BT3
            grafoBT = nx.Graph()
            LBTactive = False
            try:  ###  Lectura de datos y creación de grafo de LINEAS BAJA TENSION
                # if 1==1:
                if len(selectedLayerBT1) != 0:
                    layerBT1 = QgsProject.instance().mapLayersByName(selectedLayerBT1)[0]
                    LBTactive = True
                    if self.dlg.checkBox_LBT1.isChecked():  # Determina si la línea es aérea o subterránea
                        subterranea = True
                    else:
                        subterranea = False
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerBT1, "DSSName")
                    datosLBT, grafoBT, grafoBTTotal = self.ReaderDataLBT(layerBT1, datosLBT, grafoBT, grafoBTTotal,
                                                                         toler, subterranea, indexDSS)

                if len(selectedLayerBT2) != 0:
                    layerBT2 = QgsProject.instance().mapLayersByName(selectedLayerBT2)[0]
                    LBTactive = True
                    if self.dlg.checkBox_LBT2.isChecked():  # Determina si la línea es aérea o subterránea
                        subterranea = True
                    else:
                        subterranea = False
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerBT2, "DSSName")
                    datosLBT, grafoBT, grafoBTTotal = self.ReaderDataLBT(layerBT2, datosLBT, grafoBT, grafoBTTotal,
                                                                         toler, subterranea, indexDSS)
                if len(selectedLayerBT3) != 0:
                    layerBT3 = QgsProject.instance().mapLayersByName(selectedLayerBT3)[0]
                    LBTactive = True
                    if self.dlg.checkBox_LBT3.isChecked():  # Determina si la línea es aérea o subterránea
                        subterranea = True
                    else:
                        subterranea = False
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerBT3, "DSSName")
                    datosLBT, grafoBT, grafoBTTotal = self.ReaderDataLBT(layerBT3, datosLBT, grafoBT, grafoBTTotal,
                                                                         toler, subterranea, indexDSS)

            except KeyError:
                QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog',
                                                                                            "Verifique los nombres de las columnas") + "\n" + QCoreApplication.translate(
                    'dialog', "de las tablas de atributos de líneas de baja tensión"))
                LBTactive = False
                Error = True
            endTimeBT = time.time()

            self.progress.progressBar.setValue(30)
            # 2.3-Crea lista con las coordenadas de Inicio, Final y Fase de las lineas de media tension.
            
            """
            
            selectedLayerACO1 = "Acometida"
            selectedLayerACO2 = ""
            selectedLayerACO3 = ""
            
            """
            
            selectedLayerACO1 = self.dlg.comboBox_ACO1.currentText()  # Índice de layer_list con acometidas en la lista desplegable
            selectedLayerACO2 = self.dlg.comboBox_ACO2.currentText()  # Índice de layer_list con acometidas en la lista desplegable
            selectedLayerACO3 = self.dlg.comboBox_ACO3.currentText()  # Índice de layer_list con acometidas en la lista desplegable
            
            
            
            datosACO = []  # datosACO guarda informacion de ubicacion de acometidas
            grafoACO = nx.Graph()
            ACOactive = False
            try:  ### Lectura de datos y construcción de grafo de acometidas
                # if 1==1:
                if len(selectedLayerACO1) != 0:
                    layerACO1 = QgsProject.instance().mapLayersByName(selectedLayerACO1)[0]
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerACO1, "DSSName")
                    datosACO, grafoACO, grafoBTTotal = self.ReaderDataAcom(layerACO1, datosACO, grafoACO, grafoBTTotal, toler, indexDSS, grafoBT)
                    ACOactive = True
                if len(selectedLayerACO2) != 0:
                    layerACO2 = QgsProject.instance().mapLayersByName(selectedLayerACO2)[0]
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerACO2, "DSSName")
                    datosACO, grafoACO, grafoBTTotal = self.ReaderDataAcom(layerACO2, datosACO, grafoACO, grafoBTTotal, toler, indexDSS, grafoBT)
                    ACOactive = True
                if len(selectedLayerACO3) != 0:
                    layerACO3 = QgsProject.instance().mapLayersByName(selectedLayerACO3)[0]
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerACO3, "DSSName")
                    datosACO, grafoACO, grafoBTTotal = self.ReaderDataAcom(layerACO3, datosACO, grafoACO, grafoBTTotal, toler, indexDSS, grafoBT)
                    ACOactive = True
            except KeyError:
                QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog', "Verifique los nombres de las columnas") + "\n" + QCoreApplication.translate( 'dialog', "de las tablas de atributos de acometidas"))
                ACOactive = False
                Error = True

            # 2.4-Crea listas con coordenadas y Fase de las cargas
            
            """
            
            selectedLayerCA1 = "Cargas BT"
            selectedLayerCA2 = ""
            selectedLayerCA3 = ""
            
            
            """
            
            selectedLayerCA1 = self.dlg.comboBox_CA1.currentText()
            selectedLayerCA2 = self.dlg.comboBox_CA2.currentText()
            selectedLayerCA3 = self.dlg.comboBox_CA3.currentText()
            
            

            datosCAR = []
            kWhLVload = []
            grafoCAR = nx.Graph()
            CARactive = False
            try:  ### Lectura de datos y construcción de grafo de CARGAS
                # if 1 ==1:
                if len(selectedLayerCA1) != 0:
                    layerCA1 = QgsProject.instance().mapLayersByName(selectedLayerCA1)[0]
                    CARactive = True
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerCA1, "DSSName")
                    datosCAR, grafoCAR, kWhLVload, grafoBTTotal = self.ReaderDataLoad(layerCA1, datosCAR, grafoCAR, kWhLVload, toler, indexDSS, grafoBTTotal)
                if len(selectedLayerCA2) != 0:
                    layerCA2 = QgsProject.instance().mapLayersByName(selectedLayerCA2)[0]
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerCA2, "DSSName")
                    datosCAR, grafoCAR, kWhLVload, grafoBTTotal = self.ReaderDataLoad(layerCA2, datosCAR, grafoCAR, kWhLVload, toler, indexDSS, grafoBTTotal)
                    CARactive = True
                if len(selectedLayerCA3) != 0:
                    layerCA3 = QgsProject.instance().mapLayersByName(selectedLayerCA3)[0]
                    indexDSS = auxiliary_functions.getAttributeIndex(self, layerCA3, "DSSName")
                    datosCAR, grafoCAR, kWhLVload, grafoBTTotal = self.ReaderDataLoad(layerCA3, datosCAR, grafoCAR,  kWhLVload, toler, indexDSS, grafoBTTotal)
                    CARactive = True
            except KeyError:
                QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog', "Verifique los nombres de las columnas") + "\n" + QCoreApplication.translate( 'dialog', "de las tablas de atributos de cargas de baja tensión"))
                CARactive = False
                Error = True

            self.progress.progressBar.setValue(35)
            grafoBT, grafoACO, grafoCAR = self.IslandIdentification(grafoBTTotal, grafoBT, grafoACO, grafoCAR)
            self.progress.progressBar.setValue(38)

            if len(datosLBT) == 0:  ## CONECTIVIDAD LINEAS DE BAJA TENSION
                LBTactive = False
            else:
                startTimeBT = time.time()
                LBTactive = True
                nodesBT = grafoBT.nodes()  # guarda todos los nodos del grafoBT en una lista
                ################## Asignación de Bus a líneas BT
                for node in nodesBT:  # node es el nodo en nombramiento
                    if node in busBT_List:  # Verifica si el nodo existe (significa que está conectada a un transformador)
                        bus = busBT_List[node]["bus"]
                    else:
                        bus = 'BUSLV' + circuitName + str(busBTid)
                        busBTid += 1
                    for secondNode in grafoBT[node]:  # itera sobre las lineas que contienen el nodo. Data es el otro nodo de la linea
                        dataLine = grafoBT[node][secondNode]  # info de la linea
                        print( "Data Line error final", dataLine )
                        if dataLine['weight']['nodo1'] == dataLine['weight']['nodo2']:  # Verifica si la línea empieza y termina en el mismo punto
                            dataLine['weight']['bus1'] = bus  # Agrega el bus1 al grafoBT
                            dataLine['weight']['bus2'] = bus  # Agrega el bus1 al grafoBT
                            busBT_List[node] = {'bus': bus, 'X': dataLine['weight']['X1'], 'Y': dataLine['weight']['Y1'], "GRAFO": grafoBT, "VOLTAGELL": dataLine['weight']["TRAFVOLTLL"], "VOLTAGELN": dataLine['weight']['TRAFVOLTLN']}  #
                            aviso = QCoreApplication.translate('dialog', u'Existe una línea de BT con bus1 igual a bus2 dada su cercanía en (') + str( busBT_List[node]['X']) + ', ' + str(busBT_List[node]['Y']) + ')'
                            QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', u'Líneas secundarias'), QgsMessageLog.WARNING)
                        elif node == dataLine['weight']['nodo1']:
                            dataLine['weight']['bus1'] = bus  # Agrega el bus1 al grafoBT
                            busBT_List[node] = {'bus': bus, 'X': dataLine['weight']['X1'], 'Y': dataLine['weight']['Y1'], "GRAFO": grafoBT, "VOLTAGELL": dataLine['weight']["TRAFVOLTLL"], "VOLTAGELN": dataLine['weight']['TRAFVOLTLN']}  #
                        elif node == dataLine['weight']['nodo2']:
                            dataLine['weight']['bus2'] = bus  # Agrega el bus2 al grafoBT
                            busBT_List[node] = {'bus': bus, 'X': dataLine['weight']['X2'], 'Y': dataLine['weight']['Y2'], "GRAFO": grafoBT, "VOLTAGELL": dataLine['weight']["TRAFVOLTLL"], "VOLTAGELN": dataLine['weight']["TRAFVOLTLN"]}

            if len(datosACO) == 0:  ## CONECTIVIDAD DE ACOMETIDAS
                ACOactive = False
            else:
                startTimeAco = time.time()
                ACOactive = True
                nodesACO = grafoACO.nodes()  # guarda todos los nodos del grafoACO en una lista
                ################## Asignación de Bus a líneas Acometidas
                for node in nodesACO:  # node es el nodo en nombramiento
                    if node in busBT_List:  # Verifica si el nodo existe (significa que está conectada a un transformador o línea de baja tensión)
                        bus = busBT_List[node]["bus"]
                    else:
                        bus = 'BUSLV' + circuitName + str(busBTid)
                        busBTid += 1
                    for secondNode in grafoACO[ node ]:  # itera sobre las lineas que contienen el nodo. Data es el otro nodo de la linea
                        dataLine = grafoACO[node][secondNode]  # info de la linea
                        print( dataLine )
                        if dataLine['weight']['nodo1'] == dataLine['nodo2']:  # Verifica si la línea empieza y termina en el mismo punto
                            dataLine['weight']['bus1'] = bus  # Agrega el bus1 al grafoACO
                            dataLine['weight']['bus2'] = bus  # Agrega el bus1 al grafoACO
                            busBT_List[node] = {'bus': bus, 'X': dataLine['weight']['X1'], 'Y': dataLine['weight']['Y1'], "GRAFO": grafoACO, "VOLTAGELL": dataLine['weight']["TRAFVOLTLL"], "VOLTAGELN": dataLine['weight']["TRAFVOLTLN"]}  #
                            aviso = QCoreApplication.translate('dialog', u'Existe una línea de acometidas con bus1 igual a bus2 dada su cercanía en (') + str( busBT_List[node]['X']) + ', ' + str(busBT_List[node]['Y']) + ')'
                            QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', u'Líneas acometidas'), QgsMessageLog.WARNING)
                        elif node == dataLine['weight']['nodo1']:
                            dataLine['weight']['bus1'] = bus  # Agrega el bus1 al grafoACO
                            busBT_List[node] = {'bus': bus, 'X': dataLine['weight']['X1'], 'Y': dataLine['weight']['Y1'], "GRAFO": grafoACO, "VOLTAGELL": dataLine['weight']["TRAFVOLTLL"], "VOLTAGELN": dataLine["TRAFVOLTLN"]}  #
                        elif node == dataLine['weight']['nodo2']:
                            dataLine['weight']['bus2'] = bus  # Agrega el bus2 al grafoACO
                            busBT_List[node] = {'bus': bus, 'X': dataLine['weight']['X2'], 'Y': dataLine['weight']['Y2'], "GRAFO": grafoACO, "VOLTAGELL": dataLine['weight']["TRAFVOLTLL"], "VOLTAGELN": dataLine['weight']["TRAFVOLTLN"]}
                endTimeAco = time.time()
            self.progress.progressBar.setValue(40)

            if len(datosCAR) == 0:  ### CONECTIVIDAD DE CARGAS
                CARactive = False
            else:
                CARactive = True
                startTimeLoad = time.time()
                graphNodes = list( grafoCAR.nodes(data=True) )
                for NODE in graphNodes:
                    dataList = NODE[1]
                    nodo = NODE[0]
                    if nodo in busBT_List:  # Verifica si el nodo de la carga ya está en los nodos creados de BT
                        grafoCAR.node[nodo]["BUS"] = busBT_List[nodo]["bus"]
                        grafoCAR.node[nodo]["VOLTAGELL"] = busBT_List[nodo]["VOLTAGELL"]
                        grafoCAR.node[nodo]["VOLTAGELN"] = busBT_List[nodo]["VOLTAGELN"]
                    else:
                        bus = 'BUSLV' + circuitName + str(busBTid)
                        busBT_List[nodo] = {'bus': bus, 'X': dataList["X1"], 'Y': dataList["Y1"], "GRAFO": grafoCAR,
                                            "VOLTAGELN": "0.12"}
                        grafoCAR.node[nodo]["BUS"] = bus
                        grafoCAR.node[nodo]["VOLTAGELL"] = "0.24"
                        grafoCAR.node[nodo]["VOLTAGELN"] = "0.12"
                        aviso = QCoreApplication.translate('dialog', 'Hay 1 carga desconectada: (') + str( dataList["X1"]) + ',' + str(dataList["Y1"]) + ')'
                        QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', 'Alerta Cargas'), QgsMessageLog.WARNING)
                        busBTid += 1
                endTimeLoad = time.time()

            self.progress.progressBar.setValue(50)

            #######################################################  LOADSHAPE
            startTimeLoadShape = time.time()
            errorLoadShape = False
            if (CARactive == True):  # revisa si hay cargas
                # De las curvas disponibles, toma las existentes y las pone en un vector
                try:
                    if folder_profile != "":
                        curv_disp = {"residential": [], "commercial": [], "industrial": []}
                        for sector in ["residential", "commercial", "industrial"]:
                            os.chdir(folder_profile + "\\" + sector)  # Se ubica en la carpeta
                            for file in glob.glob("*.txt"):
                                if file[:5] == "curve":
                                    energ = file[:(len(file) - 5)]
                                    energ = energ.replace("curve", "")
                                    energ = energ.replace("_", ".")
                                    curv_disp[sector].append(float(energ))
                        graphNodes = list( grafoCAR.nodes(data=True) )
                        self.progress.progressBar.setValue(53)
                        # print grafoCAR.number_of_nodes()
                        i = 1
                        for NODE in graphNodes:
                            dataList = NODE[1]
                            nodo = NODE[0]
                            if dataList["class"] == "R":
                                sector = "residential"
                            if dataList["class"] == "C":
                                sector = "commercial"
                            if dataList["class"] == "I":
                                sector = "industrial"
                            energLoad = format(float(dataList["kWh"]), '.2f')
                            aux = list(abs(np.array(curv_disp[sector]) - np.array(len(curv_disp[sector]) * [ float(energLoad)])))  # Diferencia en kwh de la carga y las curvas existentes
                            error = min(aux) / float(energLoad)
                            enerLoadStr = str(energLoad)
                            enerLoadStr = enerLoadStr.replace(".", "_")
                            ClosCurvEnerg = float(curv_disp[sector][aux.index(min(aux))])
                            ClosCurvEnergStr = str(format(ClosCurvEnerg, '.2f'))
                            ClosCurvEnergStr = ClosCurvEnergStr.replace(".", "_")
                            if error <= 0.02:  # Significa que la diferencia de energía con la curva más cercana es menor al 2%
                                grafoCAR.node[nodo]['CURVASIG'] = 'daily=curve' + ClosCurvEnergStr + dataList["class"]

                            else:  # A las curvas asignadas, si no existen, crea una curva artificial adaptada del valor más cercano existentes
                                grafoCAR.node[nodo]['CURVASIG'] = 'daily=curve' + enerLoadStr + dataList["class"]
                                os.chdir(folder_profile + "\\" + sector)
                                file_name = 'curve' + str(ClosCurvEnergStr) + dataList["class"] + '.txt'
                                file_data = []
                                with open(file_name) as f:
                                    file_data = f.readlines()
                                file_data_parse = []
                                w = QWidget()
                                aux = 0.0
                                for j in range(96):
                                    file_data_parse.append(float(file_data[j]))
                                    aux = aux + file_data_parse[j]
                                if aux == 0:
                                    k = 1
                                else:
                                    k = float(ClosCurvEnerg) / (aux * 0.25 * 30)

                                file = open('curve' + enerLoadStr + dataList["class"] + '.txt', "w")  # _new
                                for j in range(96):
                                    file.write(str(format(k * file_data_parse[j], '.2f')) + ' \n')
                                file.close()
                                curv_disp[sector].append(float(energLoad))

                        # Create a file with all the loadshapes
                        filename = circuitName + '_Loadshapes.dss'
                        output_shpdss = open(foldername + '/' + filename, 'w')
                        output_shpdss.write('!' + folder_profile + '\n')
                        for sector in ["residential", "commercial", "industrial"]:
                            os.chdir(folder_profile + "\\" + sector)  # Se ubica en la carpeta
                            for file in glob.glob("*.txt"):
                                output_shpdss.write('New Loadshape.' + file.replace('.txt',
                                                                                    '') + ' npts=96 minterval=15 mult=(file=' + folder_profile + '\\' + sector + '\\' + file + ') useactual=no \n')
                except:
                    errorLoadShape = True
                    QMessageBox.critical(None, "QGIS2OpenDSS Error", QCoreApplication.translate('dialog', u"ERROR EN LA CREACIÓN DE LOADSHAPES \nVerifique que existen los archivos de curvas en la carpeta indicada.\n*) NOTA: no se creará el archivo de cargas ni el de LoadShapes."))
            endTimeLoadSahpe = time.time()
            ##########################   Loadshapesx
            self.progress.progressBar.setValue(55)
            startTimeWriting = time.time()

            ###LECTURA Y CONECTIVIDAD DE GD
            selectedLayerGD = self.dlg.comboBox_GD.currentText()

            if len(selectedLayerGD) != 0:
                layerGD = QgsMapLayerRegistry.instance().mapLayersByName(selectedLayerGD)[0]  # Se selecciona la capa de la base de datos "layers" según el índice de layer_list
                indexDSS = auxiliary_functions.getAttributeIndex(self, layerGD, "DSSName")
                grafoGD = nx.Graph()
                grafoGD, busBTid, busBT_List = self.ReaderDataGD(toler, layerGD, grafoGD, indexDSS, Graph_T3F_multi,   Graph_T3F_single, Graph_T2F, Graph_T1F, grafoCAR,  circuitName, busBTid, busBT_List, busMT_List)

            ####9-Crea archivos de salida en la carpeta seleccionada
            """SALIDAS PARA OPENDSS"""
            output_filesQGIS2DSS = open(foldername + '/' + circuitName + '_OutputQGIS2OpenDSS.dss', 'w')  # genera el archivo con la lista de archivos creados
            # Líneas de media tensión y monitores de líneas de media tensión.
            output_filesQGIS2DSS.write('\nredirect Bibliotecas/bibliotecas.dss')
            ###################################  Escritura LMT

            if LMTactive == True:
                filename = circuitName + '_LinesMV.dss'
                output_filesQGIS2DSS.write('\nredirect ' + filename)
                output_lmtdss = open(foldername + '/' + filename, 'w')
                filenameMon = circuitName + '_Monitors.dss'
                # output_filesQGIS2DSS.write('\nredirect '+filenameMon)
                output_monitorsdss = open(foldername + '/' + filenameMon, 'w')

                if len(selectedLayerMT1) != 0:
                    layerMT1.startEditing()  # Activa modo edición
                if len(selectedLayerMT2) != 0:
                    layerMT2.startEditing()  # Activa modo edición
                if len(selectedLayerMT3) != 0:
                    layerMT3.startEditing()  # Activa modo edición
                n = 0
                for linea in grafoMT.edges(data=True):
                    DATOS = linea[2]
                    air_or_ugnd = linea[2]['AIR_UGND']
                    configFase = linea[2]['PHASE']  # Recibe la fase del bus en formato ODSS
                    cantFases = linea[2]['NPHAS']  # Recibe la cantidad de fases de la linea
                    opervoltLN = linea[2]['VOLTOPRLN']  # ,' !1ph_basekV=',opervolt
                    if air_or_ugnd == 'air':
                        equipment = str(cantFases) + 'FMV' + str(linea[2]['PHASIZ']) + str(linea[2]['PHAMAT']) + str(linea[2]['NEUSIZ']) + str(linea[2]['NEUMAT']) + '_' + str(linea[2]['CCONF'])  # Recibe la informacion del tipo de conductor, cantidad y aislamiento
                    else:
                        equipment = str(cantFases) + 'FMV' + str(linea[2]['PHASIZ']) + str(linea[2]['PHAMAT']) + '_' + str(linea[2]['NOMVOLT']) + str(linea[2]['INSUL'])  # Recibe la informacion del tipo de conductor, cantidad y aislamiento

                    busfrom = linea[2]['bus1']
                    busto = linea[2]['bus2']
                    if float(linea[2]['SHLEN']) == 0:
                        linea[2]['SHLEN'] = 0.0001
                    sh_len = "{0:.4f}".format(linea[2]['SHLEN'])  # Recibe la longitud de la linea
                    if (busfrom == 'BUSMV' + circuitName + str(1)) or (busto == 'BUSMV' + circuitName + str(1)):
                        lineName = "MV" + str(cantFases) + 'P' + circuitName + str(0)
                    else:
                        lineName = "MV" + str(cantFases) + 'P' + circuitName + str(n + 1)
                        n += 1
                    line = '%s%s%s%s%s%s%s%s%s%s%s%s%s %s%s\n' % (
                    'new line.', lineName, ' bus1=', busfrom, configFase, ' bus2=', busto, configFase, ' geometry=', equipment, ' length=', sh_len, ' units=m', ' !1ph_basekV=',
                    opervoltLN)  # Se usan las variables anteriores en formar el string de salida
                    output_lmtdss.write(line)  # Escribe el string de salida en el archivo
                    element = 'line.' + lineName
                    line = '%s%s%s%s%s %s%s\n' % (
                    'new monitor.Mon', lineName, ' Element=', element, ' Terminal=1 Mode=0', ' !1ph_basekV=',
                    opervoltLN)
                    output_monitorsdss.write(line)  # Escribe el string de salida en el archivo
                    linea[2]["LAYER"].changeAttributeValue(linea[2]["ID"], linea[2]["INDEXDSS"], lineName)
                output_lmtdss.close()  # Cierra el archivo de salida
                output_monitorsdss.close()  # Cierra el archivo de salida
                if len(selectedLayerMT1) != 0:
                    layerMT1.commitChanges()  # Guarda
                if len(selectedLayerMT2) != 0:
                    layerMT2.commitChanges()  # Guarda
                if len(selectedLayerMT3) != 0:
                    layerMT3.commitChanges()  # Guarda
                #######################################

            ##Buses de media tensión con coordenadas
            if len(busMT_List) > 0:
                filename = circuitName + '_BusListMV.csv'
                filename2 = circuitName + '_MV_BaseKV_LN.dss'
                # output_filesQGIS2DSS.write('\nBusCoords '+filename)
                # output_filesQGIS2DSS.write('\nredirect '+filename2)
                output_buslistmt = open(foldername + '/' + filename, 'w')
                output_baseKV_DSS = open(foldername + '/' + filename2, 'w')
                layerMTBusName = "Bus_MT_Layer"
                attrs_MtBusLayer = ['BUS', 'BASEKV_LN', 'PHASES']
                layer = auxiliary_functions.newShape(layerMTBusName, attrs_MtBusLayer, "POINT", projPath)
                layer.startEditing()
                pr = layer.dataProvider()
                # layer.beginEditCommand("Feature triangulation")
                index = layer.dataProvider().fieldNameIndex('BUS')

                for bus in list(busMT_List.keys()):
                    # print busMT_List[bus]
                    busName = busMT_List[bus]['bus']
                    MTvoltage = busMT_List[bus]['VOLTAGELN']
                    Nphases = busMT_List[bus]['NPHAS']
                    line = '%s,%s,%s\n' % (busMT_List[bus]['bus'], busMT_List[bus]['X'], busMT_List[bus]['Y'])  # Se usan las variables anteriores en formar el string de salida
                    output_buslistmt.write(line)  # Escribe el string de salida en el archivo
                    lineBase = "%s%s%s%s\n" % ("SetKVBase bus=", busName, " kvln=", MTvoltage)
                    output_baseKV_DSS.write(lineBase)
                    feat = QgsFeature(pr.fields())
                    feat.setGeometry( QgsGeometry.fromPoint(QgsPoint(float(busMT_List[bus]['X']), float(busMT_List[bus]['Y']))))
                    feat["BUS"] = busName
                    feat["BASEKV_LN"] = MTvoltage
                    feat["PHASES"] = Nphases
                    pr.addFeatures([feat])
                output_buslistmt.close()  # Cierra el archivo de salida
                output_baseKV_DSS.close()
                layer.updateExtents()
                layer.commitChanges()

            self.progress.progressBar.setValue(60)
            ###Se genera la salida de subestación para OpenDSS
            if len(selectedLayerSE) != 0:
                if mode == "MODEL":
                    filename = circuitName + '_Substation.dss'
                    output_filesQGIS2DSS.write('\nredirect ' + filename)
                    output_sedss = open(foldername + '/' + filename, 'w')
                    layerSE.startEditing()  # Activa modo edición
                    # if (ndatosSE!=0): # revisa si hay subestaciones
                    output_sedss.write("!UNIT\n")
                    for NODE in list( grafoSubt.nodes(data=True) ):
                        dataList = NODE[1]
                        nodo = NODE[0]
                        cantFases = '3'
                        fases = ' phases=' + str(cantFases)
                        dev = ' windings=' + str(dataList['WINDINGS'])
                        busHV = 'Sourcebus'
                        busMV = str(dataList['BUSMT'])

                        busLV = ''
                        normhkva = " normhkva=" + str(dataList['KVA_ALTA'])
                        kVA = ' kVAs=[' + str(int(dataList['KVA_ALTA'])) + ' ' + str(int(dataList['KVA_MEDIA']))
                        kV = 'kVs=[' + str(dataList['VOLTAJEALT']) + ' ' + str(dataList['VOLTAJEMED'])
                        react = ' xhl=' + str(dataList['XHL'])
                        con = ' conns=[' + dataList['CONEXIONAL'] + ' ' + dataList['CONEXIONME']
                        if dataList['WINDINGS'] > 2:
                            kVA = kVA + ' ' + str(int(dataList['KVA_BAJA']))
                            kV = kV + ' ' + str(dataList['VOLTAJEBAJ'])
                            busLV = ' BUSMV_TerSub.1.2.3'
                            react = react + ' xht=' + str(dataList['XHT']) + ' xlt=' + str(dataList['XLT'])
                            con = con + ' ' + dataList['CONEXIONBA']
                        kVA = kVA + ']'
                        kV = kV + ']'
                        buses = ' buses=[Sourcebus.1.2.3 ' + busMV + '.1.2.3' + busLV + ']'
                        con = con + ']'
                        taps = ''
                        if dataList['TAPS'] != '':
                            taps = 'wdg=1 numtaps=' + str(dataList['TAPS']) + ' tap=' + str(dataList['TAP']) + ' maxtap=' + str(dataList['MAXTAP']) + ' mintap=' + str(dataList['MINTAP'])
                        line = '%s %s %s %s %s %s %s %s %s %s%s\n' % ( 'new transformer.HVMV', buses, fases, dev, con, kV, kVA, react, ' %loadloss=0 %noloadloss=0 ', taps, normhkva)
                        output_sedss.write(line)
                        dataList["LAYER"].changeAttributeValue(dataList["ID"], dataList["INDEXDSS"], "HVMV")
                    output_sedss.close()
                    layerSE.commitChanges()  # Guarda
                if mode == "AUTO":
                    filename = circuitName + '_Substation.dss'
                    output_filesQGIS2DSS.write('\nredirect ' + filename)
                    output_sedss = open(foldername + '/' + filename, 'w')
                    layerSE.startEditing()  # Activa modo edición
                    # if (ndatosSE!=0): # revisa si hay subestaciones
                    for NODE in list( grafoSubt.nodes(data=True) ):
                        dataList = NODE[1]
                        nodo = NODE[0]
                        cantFases = '1'
                        fases = ' phases=' + str(cantFases)
                        dev = ' windings=2'
                        busHV = 'Sourcebus'
                        busMV = str(dataList['BUSMT'])
                        Vautohigh = float(dataList['VOLTAJEALT']) / sqrt(3)
                        Vautolow = float(dataList['VOLTAJEMED']) / sqrt(3)
                        Zauto = float(dataList['XHL'])
                        kVAauto = int(dataList['KVA_ALTA']) / 3

                        Vtraf1 = Vautohigh
                        Vtraf2 = Vautohigh - Vautolow
                        nt = Vtraf2 / Vtraf1
                        Ztraf = (1 - nt) * Zauto / nt
                        kVAtraf = nt * kVAauto / (1 - nt)

                        normhkva = " normhkva=" + str(kVAtraf)
                        kVA = ' kVAs=[' + str(kVAtraf) + ' ' + str(kVAtraf) + "]"
                        kV = ' kVs=[' + str(Vtraf1) + ' ' + str(Vtraf2) + "]"
                        react = ' xhl=' + str(Ztraf)

                        busesTx1 = ' buses=[bridge.1.0 ' + 'bridge.1.4]'
                        busesTx2 = ' buses=[bridge.2.0 ' + 'bridge.2.5]'
                        busesTx3 = ' buses=[bridge.3.0 ' + 'bridge.3.6]'

                        taps = ''
                        if dataList['TAPS'] != '':
                            taps = 'wdg=1 numtaps=' + str(dataList['TAPS']) + ' tap=1.00' + ' maxtap=' + str(
                                dataList['MAXTAP']) + ' mintap=' + str(dataList['MINTAP'])
                        line1 = '%s%s%s%s%s%s%s%s%s%s\n' % (
                        'new transformer.HVMV_auto1', busesTx1, fases, dev, kV, kVA, normhkva, react,
                        ' %loadloss=0 %noloadloss=0 ', taps)
                        line2 = '%s%s%s%s%s%s%s%s%s%s\n' % (
                        'new transformer.HVMV_auto2', busesTx2, fases, dev, kV, kVA, normhkva, react,
                        ' %loadloss=0 %noloadloss=0 ', taps)
                        line3 = '%s%s%s%s%s%s%s%s%s%s\n' % (
                        'new transformer.HVMV_auto3', busesTx3, fases, dev, kV, kVA, normhkva, react,
                        ' %loadloss=0 %noloadloss=0 ', taps)
                        jumper1 = "new line.jumper1 bus1=SourceBus.1.2.3 bus2=bridge.1.2.3 R=0 X=0.00001 Normamps=7000\n"
                        jumper2 = "new line.jumper2 bus1=bridge.4.5.6 bus2=" + busMV + ".1.2.3 R=0 X=0.00001 Normamps=7000\n"

                        output_sedss.write("!AUTO\n")
                        output_sedss.write(jumper1)
                        output_sedss.write(jumper2)
                        output_sedss.write(line1)
                        output_sedss.write(line2)
                        output_sedss.write(line3)
                        dataList["LAYER"].changeAttributeValue(dataList["ID"], dataList["INDEXDSS"], "HVMV_auto")
                    output_sedss.close()
                    layerSE.commitChanges()  # Guarda
                if mode == "NOMODEL":
                    filename = circuitName + '_Substation.dss'
                    output_sedss = open(foldername + '/' + filename, 'w')
                    for NODE in list( grafoSubt.nodes(data=True) ):
                        dataList = NODE[1]
                        nodo = NODE[0]

                        bus = dataList['BUSMT']

                        line = bus + " , " + str(dataList["VOLTAJEMED"])
                        output_sedss.write("!NOMODEL\n")
                        output_sedss.write(line)
                    output_sedss.close()
                self.progress.progressBar.setValue(65)
            ##################################################
            ##   ESCRITURA DE TRANSFORMADORES
            ##################################################
            # Se genera la salida de transformadores y monitores de transformadores para OpenDSS
            if (LTRactive == True):
                filename = circuitName + '_Transformers.dss'
                output_filesQGIS2DSS.write('\nredirect ' + filename)
                output_trdss = open(foldername + '/' + filename, 'w')
                filenameMon = circuitName + '_Monitors.dss'
                output_filesQGIS2DSS.write('\nredirect ' + filenameMon)
                output_monitorsdss = open(foldername + '/' + filenameMon, 'a')

                if len(selectedLayerTR1) != 0:
                    layerT1.startEditing()  # Activa modo edición
                if len(selectedLayerTR2) != 0:
                    layerT2.startEditing()  # Activa modo edición
                if len(selectedLayerTR3) != 0:
                    layerT3.startEditing()  # Activa modo edición

                if (Graph_T1F.number_of_nodes() != 0):  # revisa si hay trafos monofásicos
                    output_trdss.write('//Transformadores Monofasicos\n')  # Escribe el string de salida en el archivo
                    # for n in range(ndatosT1F):
                    n = 0
                    for TRAFO1F in Graph_T1F.nodes(data=True):
                        dataList = TRAFO1F[1]
                        nodo = TRAFO1F[0]
                        cantFases = '1'
                        kVA = str(dataList['KVA'])
                        normhkva = " normhkva=" + kVA
                        kV_MedLL = dataList['VOLTMTLL']
                        kV_MedLN = dataList['VOLTMTLN']
                        kV_LowLL = dataList['LOADVOLT']
                        kV_LowLN = dataList['LOADVOLTLN']
                        busMV = str(dataList['BUSMT'])
                        busLV = str(dataList['BUSBT'])
                        phaseMV = dataList['PHASE'] + ".0"
                        tap = dataList['TAPS']

                        grupo_trafo = dataList['GRUPO']  # ,' !Group=',grupo_trafo)  %s%s\n

                        reactance = trafoOperations.impedanceSingleUnit(cantFases, kV_MedLL, kV_LowLN,
                                                                        int(float(kVA))).get('X')
                        resistance = trafoOperations.impedanceSingleUnit(cantFases, kV_MedLL, kV_LowLN,
                                                                         int(float(kVA))).get('R')
                        noloadloss = trafoOperations.impedanceSingleUnit(cantFases, kV_MedLL, kV_LowLN,
                                                                         int(float(kVA))).get('Pnoload')
                        imag = trafoOperations.impedanceSingleUnit(cantFases, kV_MedLL, kV_LowLN, int(float(kVA))).get(
                            'Im')
                        trafName = circuitName + cantFases + 'P_' + str(n + 1)
                        line = '%s%s %s %s%s%s %s  %s%s %s%s%s %s%s%s%s%s %s%s %s %s%s %s%s %s %s%s %s%s%s%s%s%s\n' % (
                        'new transformer.', trafName, 'phases=1 windings=3', reactance, ' ', resistance, noloadloss,
                        imag, ' Buses=[', busMV, phaseMV, ' ', busLV, '.1.0 ', busLV, '.0.2', ']', ' kvs=[', kV_MedLN,
                        kV_LowLN, kV_LowLN, ']', 'kVAs=[', kVA, kVA, kVA, ']', 'conns=[wye wye wye] Taps=[', tap,
                        ', 1, 1]', normhkva, '!Group=', grupo_trafo)
                        output_trdss.write(line)
                        dataList["LAYER"].changeAttributeValue(dataList["ID"], dataList["INDEXDSS"], trafName)
                        element = 'transformer.' + trafName
                        line = '%s%s%s%s%s %s%s\n' % (
                        'new monitor.Mon', trafName, ' Element=', element, ' Terminal=1 Mode=1', ' !Group=',
                        grupo_trafo)
                        output_monitorsdss.write(line)  # Escribe el string de salida en el archivo

                        n += 1
                if (Graph_T3F_single.number_of_nodes() != 0):  # revisa si hay trafos trifásicos Single
                    output_trdss.write(
                        '\n//Transformadores Trifasicos Simples\n')  # Escribe el string de salida en el archivo
                    n = 0
                    for TRAFO3F in Graph_T3F_single.nodes(data=True):
                        cantFases = '3'
                        dataList = TRAFO3F[1]
                        nodo = TRAFO3F[0]
                        kVA = str(dataList['KVA'])
                        normhkva = " normhkva=" + kVA
                        kV_LowLL = dataList["LOADVOLT"]
                        kV_LowLN = dataList["LOADVOLTLN"]
                        kV_MedLL = dataList['VOLTMTLL']
                        kV_MedLN = dataList['VOLTMTLN']
                        busMV = str(dataList['BUSMT'])
                        busLV = str(dataList['BUSBT'])
                        tap = dataList['TAPS']
                        if (dataList['CONME'] == 'Y'):
                            confMV = 'wye'
                        else:
                            confMV = 'delta'
                        if (dataList['CONBA'] == 'Y'):
                            confLV = 'wye'
                        else:
                            confLV = 'delta'
                        phaseMV = dataList['PHASE']
                        grupo_trafo = dataList['GRUPO']  # ,' !Group=',grupo_trafo)  %s%s\n
                        impedance = trafoOperations.impedanceSingleUnit(cantFases, kV_MedLL, kV_LowLN, kVA).get('Z')
                        noloadloss = trafoOperations.impedanceSingleUnit(cantFases, kV_MedLL, kV_LowLN, kVA).get(
                            'Pnoload')
                        imag = trafoOperations.impedanceSingleUnit(cantFases, kV_MedLL, kV_LowLN, kVA).get('Im')
                        trafName = circuitName + cantFases + 'P_' + str(n + 1)
                        line = '%s%s %s %s %s %s%s%s%s%s%s%s%s%s%s %s%s %s%s %s%s %s%s %s %s%s%s%s%s%s\n' % (
                        'new transformer.', trafName, 'phases=3 windings=2', noloadloss, imag, ' buses=[', busMV,
                        '.1.2.3 ', busLV, '.1.2.3]', ' conns=[', confMV, ',', confLV, ']', 'kvs=[', kV_MedLL, kV_LowLL,
                        ']', 'kvas=[', kVA, kVA, ']', impedance, ' Taps=[', tap, ', 1, 1]', normhkva, '!Group=',
                        grupo_trafo)
                        output_trdss.write(line)
                        dataList["LAYER"].changeAttributeValue(dataList["ID"], dataList["INDEXDSS"], trafName)
                        element = 'transformer.' + trafName
                        line = '%s%s%s%s%s\n' % (
                        'new monitor.Mon', trafName, ' Element=', element, ' Terminal=1 Mode=1')
                        output_monitorsdss.write(line)  # Escribe el string de salida en el archivo
                        n += 1
                if (Graph_T3F_multi.number_of_nodes() != 0):  # revisa si hay trafos trifásicos Multi
                    output_trdss.write(
                        '\n//Transformadores Trifasicos de tres unidades Monofasicas\n')  # Escribe el string de salida en el archivo
                    n = 0
                    for TRAFO3F_multi in Graph_T3F_multi.nodes(data=True):
                        dataList = TRAFO3F_multi[1]
                        nodo = TRAFO3F_multi[0]
                        kVA_A = str(float(dataList['KVA_FA']))
                        kVA_B = str(float(dataList['KVA_FB']))
                        kVA_C = str(float(dataList['KVA_FC']))
                        normhkva_A = " normhkva=" + kVA_A
                        normhkva_B = " normhkva=" + kVA_B
                        normhkva_C = " normhkva=" + kVA_C
                        kV_MedLL = dataList['VOLTMTLL']
                        kV_MedLN = dataList['VOLTMTLN']
                        kV_LowLN = str(
                            trafoOperations.renameVoltage(int(dataList['KVM']), int(dataList['KVL'])).get('LVCode')[
                                'LN'])
                        kV_LowLL = str(
                            trafoOperations.renameVoltage(int(dataList['KVM']), int(dataList['KVL'])).get('LVCode')[
                                'LL'])
                        busMV = str(dataList['BUSMT'])
                        busLV = str(dataList['BUSBT'])
                        phaseMV = dataList['PHASE']
                        tap = dataList['TAPS']

                        grupo_trafo = dataList['GRUPO']  # ,' !Group=',grupo_trafo)  %s%s\n

                        impedanceA = \
                        trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, kVA_C, phaseMV).get(
                            'impA')['Za']
                        impedanceB = \
                        trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, kVA_C, phaseMV).get(
                            'impB')['Zb']
                        resistanceB = \
                        trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, kVA_C, phaseMV).get(
                            'impB')['Rb']
                        reactanceB = \
                        trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, kVA_C, phaseMV).get(
                            'impB')['Xb']
                        impedanceC = \
                        trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, kVA_C, phaseMV).get(
                            'impC')['Zc']
                        imagA = \
                        trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, kVA_C, phaseMV).get(
                            'impA')['ImA']
                        imagB = \
                        trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, kVA_C, phaseMV).get(
                            'impB')['ImB']
                        imagC = \
                        trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, kVA_C, phaseMV).get(
                            'impC')['ImC']
                        noloadlossA = \
                        trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, kVA_C, phaseMV).get(
                            'impA')['PnoloadA']
                        noloadlossB = \
                        trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, kVA_C, phaseMV).get(
                            'impB')['PnoloadB']
                        noloadlossC = \
                        trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, kVA_C, phaseMV).get(
                            'impC')['PnoloadC']

                        if (dataList['CONBA'] == '4D'):  # si el transformador es delta 4 hilos en baja tensión
                            line_A = '%s%s%s%s %s %s %s%s%s %s%s%s %s %s %s%s %s%s %s%s %s%s %s%s%s%s%s%s\n' % (
                            'new transformer.', circuitName, '3U3P_1_', str(n + 1), 'phases=1 windings=2', imagA,
                            ' buses=[', busMV, '.1.0', busLV, '.3.1', ']', noloadlossA, impedanceA, 'kvs=[', kV_MedLN,
                            kV_LowLL, ']', 'kvas=[', kVA_A, kVA_A, ']', 'conns=[wye wye] Taps=[', tap, ', 1]',
                            normhkva_A, ' !Group=', grupo_trafo)
                            line_B = '%s%s%s%s %s %s %s%s%s %s%s %s%s%s %s %s %s %s%s %s %s%s %s%s %s %s%s %s%s%s%s%s%s\n' % (
                            'new transformer.', circuitName, '3U3P_2_', str(n + 1), 'phases=1 windings=3', imagB,
                            ' buses=[', busMV, '.2.0', busLV, '.1.0', busLV, '.0.2', ']', noloadlossB, reactanceB,
                            resistanceB, 'kvs=[', kV_MedLN, kV_LowLN, kV_LowLN, ']', 'kvas=[', kVA_B, kVA_B, kVA_B, ']',
                            'conns=[wye wye wye] Taps=[', tap, ', 1, 1]', normhkva_B, ' !Group=', grupo_trafo)
                            line_C = '%s%s%s%s %s %s %s%s%s %s%s%s %s %s %s%s %s%s %s%s %s%s %s%s%s%s%s%s\n' % (
                            'new transformer.', circuitName, '3U3P_3_', str(n + 1), 'phases=1 windings=2', imagC,
                            ' buses=[', busMV, '.3.0', busLV, '.2.3', ']', noloadlossC, impedanceC, 'kvs=[', kV_MedLN,
                            kV_LowLL, ']', 'kvas=[', kVA_C, kVA_C, ']', 'conns=[wye wye] Taps=[', tap, ', 1]',
                            normhkva_C, ' !Group=', grupo_trafo)
                            output_trdss.write(line_A)  # res
                            output_trdss.write(line_B)
                            output_trdss.write(line_C)
                            dataList["LAYER"].changeAttributeValue(dataList["ID"], dataList["INDEXDSS"],
                                                                   circuitName + '3U3P_' + str(n + 1))

                            element = 'transformer.' + circuitName + '3U3P_1_' + str(n + 1)
                            line = '%s%s%s%s%s%s%s\n' % (
                            'new monitor.Mon', circuitName, '3U3P_1_', str(n + 1), ' Element=', element,
                            ' Terminal=1 Mode=1')
                            output_monitorsdss.write(line)  # Escribe el string de salida en el archivo
                            element = 'transformer.' + circuitName + '3U3P_2_' + str(n + 1)
                            line = '%s%s%s%s%s%s%s\n' % (
                            'new monitor.Mon', circuitName, '3U3P_2_', str(n + 1), ' Element=', element,
                            ' Terminal=1 Mode=1')
                            output_monitorsdss.write(line)  # Escribe el string de salida en el archivo
                            element = 'transformer.' + circuitName + '3U3P_3_' + str(n + 1)
                            line = '%s%s%s%s%s%s%s\n' % (
                            'new monitor.Mon', circuitName, '3U3P_3_', str(n + 1), ' Element=', element,
                            ' Terminal=1 Mode=1')
                            output_monitorsdss.write(line)  # Escribe el string de salida en el archivo
                        elif (dataList['CONBA'] == 'Y'):
                            line_A = '%s%s%s%s %s %s %s%s%s %s%s%s %s %s %s%s %s%s %s%s %s%s %s%s%s%s%s%s\n' % (
                            'new transformer.', circuitName, '3U3P_1_', str(n + 1), 'phases=1 windings=2', imagA,
                            ' buses=[', busMV, '.1.0', busLV, '.3.1', ']', noloadlossA, impedanceA, 'kvs=[', kV_MedLN,
                            kV_LowLL, ']', 'kvas=[', kVA_A, kVA_A, ']', 'conns=[wye wye] Taps=[', tap, ', 1]',
                            normhkva_A, ' !Group=', grupo_trafo)

                            line_B = '%s%s%s%s %s %s %s%s%s %s%s%s %s %s %s%s %s%s %s%s %s%s %s%s%s%s%s%s\n' % (
                            'new transformer.', circuitName, '3U3P_2_', str(n + 1), 'phases=1 windings=2', imagB,
                            ' buses=[', busMV, '.2.0', busLV, '.1.2', ']', noloadlossB, impedanceB, 'kvs=[', kV_MedLN,
                            kV_LowLL, ']', 'kvas=[', kVA_B, kVA_B, ']', 'conns=[wye wye] Taps=[', tap, ', 1]',
                            normhkva_B, ' !Group=', grupo_trafo)

                            line_C = '%s%s%s%s %s %s %s%s%s %s%s%s %s %s %s%s %s%s %s%s %s%s %s%s%s%s%s%s\n' % (
                            'new transformer.', circuitName, '3U3P_3_', str(n + 1), 'phases=1 windings=2', imagC,
                            ' buses=[', busMV, '.3.0', busLV, '.2.3', ']', noloadlossC, impedanceC, 'kvs=[', kV_MedLN,
                            kV_LowLL, ']', 'kvas=[', kVA_C, kVA_C, ']', 'conns=[wye wye] Taps=[', tap, ', 1]',
                            normhkva_C, ' !Group=', grupo_trafo)
                            output_trdss.write(line_A)  # res
                            output_trdss.write(line_B)
                            output_trdss.write(line_C)
                            dataList["LAYER"].changeAttributeValue(dataList["ID"], dataList["INDEXDSS"],
                                                                   circuitName + '3U3P_' + str(n + 1))

                            element = 'transformer.' + circuitName + '3U3P_1_' + str(n + 1)
                            line = '%s%s%s%s%s%s%s\n' % (
                            'new monitor.Mon', circuitName, '3U3P_1_', str(n + 1), ' Element=', element,
                            ' Terminal=1 Mode=1')
                            output_monitorsdss.write(line)  # Escribe el string de salida en el archivo
                            element = 'transformer.' + circuitName + '3U3P_2_' + str(n + 1)
                            line = '%s%s%s%s%s%s%s\n' % (
                            'new monitor.Mon', circuitName, '3U3P_2_', str(n + 1), ' Element=', element,
                            ' Terminal=1 Mode=1')
                            output_monitorsdss.write(line)  # Escribe el string de salida en el archivo
                            element = 'transformer.' + circuitName + '3U3P_3_' + str(n + 1)
                            line = '%s%s%s%s%s%s%s\n' % (
                            'new monitor.Mon', circuitName, '3U3P_3_', str(n + 1), ' Element=', element,
                            ' Terminal=1 Mode=1')
                            output_monitorsdss.write(line)  # Escribe el string de salida en el archivo
                        n += 1
                if (Graph_T2F.number_of_nodes() != 0):  # revisa si hay trafos bifásicos
                    output_trdss.write(
                        '\n//Transformadores bifásicos (Conexiones especiales de dos transformadores)\n')  # Escribe el string de salida en el archivo
                    n = 0
                    for TRAFO2F in Graph_T2F.nodes(data=True):
                        dataList = TRAFO2F[1]
                        nodo = TRAFO2F[0]
                        busMV = str(dataList['BUSMT'])
                        busLV = str(dataList['BUSBT'])
                        kV_MedLL = dataList['VOLTMTLL']
                        kV_MedLN = dataList['VOLTMTLN']
                        kV_LowLN = str(
                            trafoOperations.renameVoltage(int(dataList['KVM']), int(dataList['KVL'])).get('LVCode')[
                                'LN'])
                        kV_LowLL = str(
                            trafoOperations.renameVoltage(int(dataList['KVM']), int(dataList['KVL'])).get('LVCode')[
                                'LL'])
                        kVA_A = str(int(float(dataList['KVA_FA'])))
                        kVA_B = str(int(float(dataList['KVA_FB'])))
                        kVA_C = str(int(float(dataList['KVA_FC'])))
                        phase = dataList['PHASE']
                        tap = str(dataList['TAPS'])
                        # tap="1"
                        grupo_trafo = dataList['GRUPO']  # ,' !Group=',grupo_trafo)  %s%s\n
                        if (dataList['CONBA'] == '4D'):  # si el transformador es delta 4 hilos en baja tensión
                            if phase == '.1.2':  # Las variables conexME y conexBA se utilizan para escribir a qué nodos de la barra se conecta la estrella abierta
                                if float(dataList['KVA_FA']) >= float(dataList['KVA_FB']):
                                    buff_kVA_A = kVA_A
                                    buff_kVA_B = kVA_B
                                    kVA_A = buff_kVA_B
                                    kVA_B = buff_kVA_A

                                conexME_trafoA = '.1.0'  # Conexión en barra de media tensión del transformador A
                                conexBA_trafoA = '.3.1'  # Conexión en barra de baja tensión del transformador A
                                conexME_trafoB = '.2.0'  # Conexión en barra de media tensión del transformador B
                                conexBA1_trafoB = '.1.0'  # Conexión en barra de baja tensión del transformador B
                                conexBA2_trafoB = '.0.2'  # Conexión en barra de baja tensión del transformador B
                                impedanceA = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, 0, phase).get(
                                    'impA')[
                                    'Za']  # Se obtienen las impedancias según las fases del banco en las que hay transformadores
                                reactanceB = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, 0, phase).get(
                                    'impB')['Rb']
                                resistanceB = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, 0, phase).get(
                                    'impB')['Xb']
                                imagA = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, 0, phase).get(
                                    'impA')['ImA']
                                imagB = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, 0, phase).get(
                                    'impB')['ImB']
                                noloadlossA = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, 0, phase).get(
                                    'impA')['PnoloadA']
                                noloadlossB = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_B, 0, phase).get(
                                    'impB')['PnoloadB']
                                kVA_trafoA = kVA_A  # Potencia del transformador A
                                kVA_trafoB = kVA_B  # Potencia del transformador B
                            if phase == '.1.3':
                                if float(dataList['KVA_FA']) >= float(dataList['KVA_FC']):
                                    buff_kVA_A = kVA_A
                                    buff_kVA_C = kVA_C
                                    kVA_A = buff_kVA_C
                                    kVA_C = buff_kVA_A

                                conexME_trafoA = '.1.0'  # Conexión en barra de media tensión del transformador A
                                conexBA_trafoA = '.2.1'  # Conexión en barra de baja tensión del transformador A
                                conexME_trafoB = '.3.0'  # Conexión en barra de media tensión del transformador B
                                conexBA1_trafoB = '.1.0'  # Conexión en barra de baja tensión del transformador B
                                conexBA2_trafoB = '.0.3'  # Conexión en barra de baja tensión del transformador B
                                impedanceA = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_C, 0, phase).get(
                                    'impA')['Za']
                                reactanceB = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_C, 0, phase).get(
                                    'impB')['Rb']
                                resistanceB = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_C, 0, phase).get(
                                    'impB')['Xb']
                                imagA = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_C, 0, phase).get(
                                    'impA')['ImA']
                                imagB = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_C, 0, phase).get(
                                    'impB')['ImB']
                                noloadlossA = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_C, 0, phase).get(
                                    'impA')['PnoloadA']
                                noloadlossB = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_A, kVA_C, 0, phase).get(
                                    'impB')['PnoloadB']
                                kVA_trafoA = kVA_A
                                kVA_trafoB = kVA_C
                            if phase == '.2.3':
                                if float(dataList['KVA_FB']) >= float(dataList['KVA_FC']):
                                    buff_kVA_B = kVA_B
                                    buff_kVA_C = kVA_C
                                    kVA_B = buff_kVA_C
                                    kVA_C = buff_kVA_B
                                conexME_trafoA = '.2.0'  # Conexión en barra de media tensión del transformador A
                                conexBA_trafoA = '.1.2'  # Conexión en barra de baja tensión del transformador A
                                conexME_trafoB = '.3.0'  # Conexión en barra de media tensión del transformador B
                                conexBA1_trafoB = '.2.0'  # Conexión en barra de baja tensión del transformador B
                                conexBA2_trafoB = '.0.3'  # Conexión en barra de baja tensión del transformador B
                                impedanceA = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_B, kVA_C, 0, phase).get(
                                    'impA')['Za']
                                reactanceB = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_B, kVA_C, 0, phase).get(
                                    'impB')['Rb']
                                resistanceB = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_B, kVA_C, 0, phase).get(
                                    'impB')['Xb']
                                imagA = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_B, kVA_C, 0, phase).get(
                                    'impA')['ImA']
                                imagB = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_B, kVA_C, 0, phase).get(
                                    'impB')['ImB']
                                noloadlossA = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_B, kVA_C, 0, phase).get(
                                    'impA')['PnoloadA']
                                noloadlossB = \
                                trafoOperations.impedanceMultiUnit(kV_MedLL, kV_LowLN, kVA_B, kVA_C, 0, phase).get(
                                    'impB')['PnoloadB']
                                kVA_trafoA = kVA_B
                                kVA_trafoB = kVA_C
                            normhkva_A = " normhkva=" + kVA_trafoA
                            normhkva_B = " normhkva=" + kVA_trafoB
                            line_A = '%s%s%s%s %s %s %s %s %s%s%s%s%s%s%s %s%s %s%s %s%s %s%s %s%s%s%s%s%s\n' % (
                            'new transformer.', circuitName, '2U3P_1_', str(n + 1), 'phases=1 windings=2', imagA,
                            impedanceA, noloadlossA, ' buses=[', busMV, conexME_trafoA, ' ', busLV, conexBA_trafoA, ']',
                            'kvs=[', kV_MedLN, kV_LowLL, ']', 'kvas=[', kVA_trafoA, kVA_trafoA, ']',
                            'conns=[wye wye] Taps=[', tap, ', 1]', normhkva_A, ' !Group=', grupo_trafo)
                            line_B = '%s%s%s%s %s %s %s %s %s %s%s%s%s%s%s%s%s%s%s %s%s %s %s%s %s%s %s %s%s %s%s%s%s%s%s\n' % (
                            'new transformer.', circuitName, '2U3P_2_', str(n + 1), 'phases=1 windings=3', imagB,
                            reactanceB, resistanceB, noloadlossB, ' buses=[', busMV, conexME_trafoB, ' ', busLV,
                            conexBA1_trafoB, ' ', busLV, conexBA2_trafoB, ']', 'kvs=[', kV_MedLN, kV_LowLN, kV_LowLN,
                            ']', 'kvas=[', kVA_trafoB, kVA_trafoB, kVA_trafoB, ']', 'conns=[wye wye wye] Taps=[', tap,
                            ', 1, 1]', normhkva_B, ' !Group=', grupo_trafo)
                            output_trdss.write(line_A)
                            output_trdss.write(line_B)
                            dataList["LAYER"].changeAttributeValue(dataList["ID"], dataList["INDEXDSS"],
                                                                   circuitName + '2U3P_' + str(n + 1))
                            element = 'transformer.' + circuitName + '2U3P_1_' + str(n + 1)
                            line = '%s%s%s%s%s%s%s\n' % (
                            'new monitor.Mon', circuitName, '2U3P_1_', str(n + 1), ' Element=', element,
                            ' Terminal=1 Mode=1')
                            output_monitorsdss.write(line)  # Escribe el string de salida en el archivo
                            element = 'transformer.' + circuitName + '2U3P_2_' + str(n + 1)
                            line = '%s%s%s%s%s%s%s\n' % (
                            'new monitor.Mon', circuitName, '2U3P_2_', str(n + 1), ' Element=', element,
                            ' Terminal=1 Mode=1')
                            output_monitorsdss.write(line)  # Escribe el string de salida en el archivo
                        n += 1
                output_trdss.close()
                output_monitorsdss.close()
                if len(selectedLayerTR1) != 0:
                    layerT1.commitChanges()  # Activa modo edición
                if len(selectedLayerTR2) != 0:
                    layerT2.commitChanges()  # Activa modo edición
                if len(selectedLayerTR3) != 0:
                    layerT3.commitChanges()  # Activa modo edición
            #####################################
            ##   FIN ESCRITURA DE TRANSFORMADORES
            #####################################
            self.progress.progressBar.setValue(70)
            # Se genera la salida de transformadores y monitores de transformadores para OpenDSS
            ##################################
            ### ESCRITURA DE BAJA TENSIÓN ####
            ##################################
            if (LBTactive == True):
                filename = circuitName + '_LinesLV.dss'
                output_filesQGIS2DSS.write('\nredirect ' + filename)
                output_lbtdss = open(foldername + '/' + filename, 'w')
                if len(selectedLayerBT1) != 0:
                    layerBT1.startEditing()  # Activa modo edición
                if len(selectedLayerBT2) != 0:
                    layerBT2.startEditing()  # Activa modo edición
                if len(selectedLayerBT3) != 0:
                    layerBT3.startEditing()  # Activa modo edición
                n = 1
                for line in grafoBT.edges(data=True):
                    dataLine = line[2]
                    TrafNode = dataLine["TRAFNODE"]
                    busfrom = line[2]['bus1']
                    busto = line[2]['bus2']
                    # conns=dataLine['CONNS']

                    if dataLine[
                        'TRAFNPHAS'] == "NULL":  # Si la linea no tiene algun transformador conectado se le asigna la cant de fases que dice en el shape
                        cantFases = dataLine['NPHAS']
                        desc = "Disconnected"
                        busBT_List[line[0]]['VOLTAGELN'] = "0.12"
                        busBT_List[line[1]]['VOLTAGELN'] = "0.12"
                    else:
                        cantFases = dataLine['TRAFNPHAS']
                        desc = ""
                    if (dataLine['AIR_UGND'] == 'air'):
                        if (cantFases == '1'):
                            equipment = 'Geometry=1FLV' + str(dataLine['PHASIZ']) + str(dataLine['PHAMAT']) + str(
                                dataLine['NEUSIZ']) + str(dataLine['NEUMAT'])
                            if dataLine['TIPO'] == 'TPX':
                                equipment = 'Linecode=TRPX' + str(dataLine['PHASIZ']) + str(dataLine['PHAMAT'])
                            conns = ".1.2"
                        elif (cantFases == '3' or cantFases == '2'):
                            equipment = 'Geometry=3FLV' + str(dataLine['PHASIZ']) + str(dataLine['PHAMAT']) + str(
                                dataLine['NEUSIZ']) + str(dataLine['NEUMAT'])
                            if dataLine['TIPO'] == 'QPX':
                                equipment = 'Linecode=QDPX' + str(dataLine['PHASIZ']) + str(dataLine['PHAMAT'])
                            conns = ".1.2.3"
                        else:
                            equipment = 'NONE'
                    else:
                        if (cantFases == '1'):
                            equipment = 'LineCode=1FLV' + str(dataLine['PHASIZ']) + str(dataLine['PHAMAT']) + str(
                                dataLine['PHASIZ']) + str(dataLine['PHAMAT']) + '_' + str(dataLine['INSUL'])
                            conns = ".1.2"
                        elif (cantFases == '3' or cantFases == '2'):
                            equipment = 'LineCode=3FLV' + str(dataLine['PHASIZ']) + str(dataLine['PHAMAT']) + str(
                                dataLine['PHASIZ']) + str(dataLine['PHAMAT']) + '_' + str(dataLine['INSUL'])
                            conns = ".1.2.3"
                        else:
                            equipment = 'NONE'
                            conns = "NONE"
                    if float(dataLine['SHLEN']) == 0:
                        dataLine['SHLEN'] = 0.0001
                    sh_len = "{0:.4f}".format(dataLine['SHLEN'])  # Recibe la longitud de la linea
                    opervoltLN = dataLine["TRAFVOLTLN"]
                    grupo_aco = dataLine['GRUPO']
                    lineName = "LV" + cantFases + 'F' + circuitName + str(n)
                    line = '%s%s %s%s%s %s%s%s %s%s%s %s %s%s %s%s  %s\n' % (
                    'new line.', lineName, 'bus1=', busfrom, conns, 'bus2=', busto, conns, equipment, ' length=',
                    sh_len, 'units=m', ' !1ph_basekV=', opervoltLN, ' Group=', grupo_aco, desc)
                    output_lbtdss.write(line)  # Escribe el string de salida en el archivo
                    dataLine["LAYER"].changeAttributeValue(dataLine["ID"], dataLine["INDEXDSS"], lineName)
                    ######## modificación del shape
                    n += 1
                output_lbtdss.close()  # Cierra el archivo de salida
                if len(selectedLayerBT1) != 0:
                    layerBT1.commitChanges()  # Guarda
                if len(selectedLayerBT2) != 0:
                    layerBT2.commitChanges()  # Guarda
                if len(selectedLayerBT3) != 0:
                    layerBT3.commitChanges()  # Guarda

            ##############################
            ### FIN ESCRITURA BAJA TENSIÓN
            ##############################
            self.progress.progressBar.setValue(80)
            ##############################
            ###  ESCRITURA ACOMETIDAS
            ##############################
            if (ACOactive == True):
                filename = circuitName + '_ServicesLV.dss'
                output_filesQGIS2DSS.write('\nredirect ' + filename)
                output_acodss = open(foldername + '/' + filename, 'w')
                if len(selectedLayerACO1) != 0:
                    layerACO1.startEditing()  # Activa modo edición
                if len(selectedLayerACO2) != 0:
                    layerACO2.startEditing()  # Activa modo edición
                if len(selectedLayerACO3) != 0:
                    layerACO3.startEditing()  # Activa modo edición

                n = 1
                for line in grafoACO.edges(data=True):
                    dataLine = line[2]
                    TrafNode = dataLine["TRAFNODE"]
                    busfrom = line[2]['bus1']
                    busto = line[2]['bus2']
                    # conns=dataLine['CONNS']
                    if dataLine[
                        'TRAFNPHAS'] == "NULL":  # Si la linea no tiene algun transformador conectado se le asigna la cant de fases que dice en el shape
                        cantFases = dataLine['NPHAS']
                        desc = "Disconnected"
                        busBT_List[line[0]]['VOLTAGELN'] = "0.12"
                        busBT_List[line[1]]['VOLTAGELN'] = "0.12"
                    else:
                        cantFases = dataLine['TRAFNPHAS']
                        desc = ""
                    if (cantFases == '1'):
                        equipment = 'TRPX' + str(dataLine['PHASIZ']) + str(dataLine['PHAMAT'])
                        conns = ".1.2"
                    elif (cantFases == '3' or cantFases == '2'):
                        equipment = 'QDPX' + str(dataLine['PHASIZ']) + str(dataLine['PHAMAT'])
                        conns = ".1.2.3"
                    else:
                        equipment = 'NONE'
                        conns = "NONE"
                    if float(dataLine['SHLEN']) == 0:
                        dataLine['SHLEN'] = 0.0001
                    sh_len = "{0:.4f}".format(dataLine['SHLEN'])  # Recibe la longitud de la linea
                    opervoltLN = dataLine['TRAFVOLTLN']  # ,' !1ph_basekV=',opervoltLN
                    grupo_aco = dataLine['GRUPO']
                    lineName = "SRV" + cantFases + 'F' + circuitName + str(n)
                    text = '%s%s %s%s%s %s%s%s %s%s%s%s %s %s%s %s%s  %s\n' % (
                    'new line.', lineName, 'bus1=', busfrom, conns, 'bus2=', busto, conns, ' linecode=', equipment,
                    ' length=', sh_len, 'units=m', ' !1ph_basekV=', opervoltLN, ' Group=', grupo_aco, desc)
                    output_acodss.write(text)  # Escribe el string de salida en el archivo
                    dataLine["LAYER"].changeAttributeValue(dataLine["ID"], dataLine["INDEXDSS"], lineName)
                    n += 1
                output_acodss.close()  # Cierra el archivo de salida
                if len(selectedLayerACO1) != 0:
                    layerACO1.commitChanges()  # Guarda
                if len(selectedLayerACO2) != 0:
                    layerACO2.commitChanges()  # Guarda
                if len(selectedLayerACO3) != 0:
                    layerACO3.commitChanges()  # Guarda
            ##############################
            ###   FIN ESCRITURA ACOMETIDAS
            ##############################
            self.progress.progressBar.setValue(90)

            #################
            ### Escritura Cargas
            #################
            if (CARactive == True) and not errorLoadShape:
                if folder_profile != "":
                    filename = circuitName + '_Loadshapes.dss'
                    output_filesQGIS2DSS.write('\nredirect ' + filename)
                filename = circuitName + '_LoadsLV.dss'
                output_filesQGIS2DSS.write('\nredirect ' + filename)
                output_cadss = open(foldername + '/' + filename, 'w')
                if len(selectedLayerCA1) != 0:
                    layerCA1.startEditing()  # Guarda
                if len(selectedLayerCA2) != 0:
                    layerCA2.startEditing()  # Guarda
                if len(selectedLayerCA3) != 0:
                    layerCA3.startEditing()  # Guarda
                n = 0
                self.progress.progressBar.setValue(90.5)
                for carga in grafoCAR.nodes(data=True):
                    # self.progress.progressBar.setValue(90.5+n*0.001)
                    dataList = carga[1]
                    nodo = carga[0]
                    bus = str(dataList['BUS'])
                    kW = str(dataList['kW'])
                    # conns=dataList['CONNS']
                    conf = dataList['CONF']
                    if dataList[
                        'TRAFNPHAS'] == "NULL":  # Si la carga no tiene algun transformador conectado se le asigna la cant de fases que dice en el shape
                        cantFases = "1"
                        desc = "disconnected"
                        kV = "0.24"
                    else:
                        cantFases = dataList['TRAFNPHAS']
                        desc = ""
                        kV = dataList['TRAFVOLTLL']
                    if cantFases == "1":
                        conns = ".1.2"
                    else:
                        conns = ".1.2.3"
                    daily = dataList['CURVASIG']

                    kWhmonth = dataList['kWh']
                    loadclass = dataList['class']

                    if loadclass == "R":
                        kvar = str(0.1)
                    else:
                        kvar = str(0.3)

                    Grupo = dataList['GRUPO']
                    loadName = cantFases + 'F' + circuitName + str(n + 1)
                    line = '%s%s %s%s%s %s%s %s%s %s%s %s%s %s%s %s %s%s %s%s %s%s  %s\n' % (
                    'new load.', loadName, 'bus1=', bus, conns, 'kV=', kV, 'model=1 conn=', conf, 'kW=', kW, 'kvar=',
                    kvar, 'status=variable phases=', cantFases, daily, '!kWh=', kWhmonth, 'class=', loadclass,
                    '!Group=', Grupo, desc)
                    output_cadss.write(line)
                    dataList["LAYER"].changeAttributeValue(dataList["ID"], dataList["INDEXDSS"], loadName)
                    n += 1
                output_cadss.close()
                if len(selectedLayerCA1) != 0:
                    layerCA1.commitChanges()  # Guarda
                if len(selectedLayerCA2) != 0:
                    layerCA2.commitChanges()  # Guarda
                if len(selectedLayerCA3) != 0:
                    layerCA3.commitChanges()  # Guarda

            ########################
            ### Fin escritura Cargas
            ########################

            ########################
            ### Escritura de GD
            ########################
            if len(selectedLayerGD) != 0:
                layerGD = QgsMapLayerRegistry.instance().mapLayersByName(selectedLayerGD)[
                    0]  # Se selecciona la capa de la base de datos "layers" según el índice de layer_list
                self.progress.progressBar.setValue(92)
                filename = circuitName + '_DG.dss'
                output_filesQGIS2DSS.write('\nredirect ' + filename)
                output_GDdss = open(foldername + '/' + filename, 'w')
                layerGD.startEditing()  # Guarda
                if errorLoadShape or cargas == 0:
                    filenameloads = circuitName + '_Loadshapes.dss'
                    output_shpdss = open(foldername + '/' + filenameloads, 'w')
                    output_shpdss.write('!' + folder_profile + '\n')
                n = 1
                i = 1
                shapewritten = {}
                for GD in grafoGD.nodes(data=True):
                    dataList = GD[1]
                    nodo = GD[0]
                    bus = str(dataList['BUS'])
                    kVA = str(dataList['KVA'])
                    conf = str(dataList['CONF'])
                    NPHAS = str(dataList["NPHAS"])
                    CURVE1 = dataList["CURVE1"]
                    CURVE2 = dataList["CURVE2"]
                    kV = str(dataList["VOLTAGELL"])
                    if NPHAS == "1":
                        conn = ".1.2"
                    else:
                        conn = ".1.2.3"
                    if dataList["TECH"] == "PV":
                        if "MyPvsT" not in shapewritten:
                            shapewritten["MyPvsT"] = 0
                            output_shpdss.write(
                                'New XYCurve.MyPvsT npts=4 xarray=[.001 25 75 100] yarray=[1.2 1.0 0.8 0.6]\n')
                            output_shpdss.write(
                                'New XYCurve.MyEff npts=4 xarray=[.1 .2 .4 1.0] yarray=[.86 .9 .93 .97]\n')

                        if CURVE1 not in shapewritten:
                            shapewritten[CURVE1] = 0
                            name1 = CURVE1.replace('.txt', '')
                            name1 = name1.replace('.dss', '')
                            output_shpdss.write(
                                'New Loadshape.' + name1 + ' npts=96 minterval=15 csvfile=' + folder_profile + '\\DG\\' + CURVE1 + '\n')
                        if CURVE2 not in shapewritten:
                            shapewritten[CURVE2] = 0
                            name2 = CURVE2.replace('.txt', '')
                            name2 = name2.replace('.dss', '')
                            output_shpdss.write(
                                'New Tshape.' + name2 + ' npts=96 minterval=15 csvfile=' + folder_profile + '\\DG\\' + CURVE2 + '\n')
                        pvname = "PV" + NPHAS + "F" + circuitName + str(n)
                        pvSentence = "New PVSystem." + pvname + " bus1=" + bus + conn + " kV=" + kV + " phases=" + NPHAS + " kVA=" + kVA + " PF=1 conn=" + conf + " irrad=0.90 Pmpp=" + kVA + " temperature=25 effcurve=Myeff P-TCurve=MyPvsT Daily=" + name1 + " TDaily=" + name2 + " %cutin=0.01 %cutout=0.01 enabled=yes \n"
                        dataList["LAYER"].changeAttributeValue(dataList["ID"], dataList["INDEXDSS"], pvname)
                        output_GDdss.write(pvSentence)
                        n += 1
                    else:
                        if (CURVE1, CURVE2) not in shapewritten:
                            shapewritten[(CURVE1, CURVE2)] = "curveDG" + str(i)
                            output_shpdss.write("New Loadshape.curveDG" + str(
                                i) + " npts=96 minterval=15 mult=(file=" + folder_profile + '\\DG\\' + CURVE1 + ") Qmult=(file=" + folder_profile + '\\DG\\' + CURVE2 + ") useactual=no \n")
                            i += 1
                        GDName = "DG" + NPHAS + "F" + circuitName + str(n)
                        DGsentence = "New Generator." + GDName + " Bus1=" + bus + conn + " phases=" + NPHAS + " conn=" + conf + " kVA=" + kVA + " kV=" + kV + " kW=1 kVAR=1 Model=1 daily=" + \
                                     shapewritten[(CURVE1, CURVE2)] + " status=variable\n"
                        dataList["LAYER"].changeAttributeValue(dataList["ID"], dataList["INDEXDSS"], GDName)
                        output_GDdss.write(DGsentence)
                        n += 1
                output_GDdss.close()
                layerGD.commitChanges()
            if (cargas > 0 and not errorLoadShape) or selectedLayerGD != 0:
                output_shpdss.close()
            ########################
            ### Fin de escritura de GD
            ########################

            self.progress.progressBar.setValue(94)
            if len(busBT_List) > 0:  ###Buses de baja tensión con coordenadas
                filename = circuitName + '_BusListLV.csv'
                filename2 = circuitName + '_LV_KVBaseLN.dss'
                # output_filesQGIS2DSS.write('\nBusCoords '+filename)
                # output_filesQGIS2DSS.write('\nredirect '+filename2)
                output_buslistbt = open(foldername + '/' + filename, 'w')
                output_baseKV_DSS = open(foldername + '/' + filename2, 'w')
                layerBTBusName = "Bus_BT_Layer"
                attrs_BtBusLayer = ["BUS", "BASEKV_LN"]
                layer = auxiliary_functions.newShape(layerBTBusName, attrs_BtBusLayer, "POINT", projPath)
                layer.startEditing()
                pr = layer.dataProvider()
                index = layer.dataProvider().fieldNameIndex('BUS')
                for bus in list(busBT_List.keys()):
                    busName = busBT_List[bus]['bus']
                    BTvoltage = busBT_List[bus]['VOLTAGELN']
                    line = '%s,%s,%s\n' % (busBT_List[bus]['bus'], busBT_List[bus]['X'], busBT_List[bus][
                        'Y'])  # Se usan las variables anteriores en formar el string de salida
                    output_buslistbt.write(line)  # Escribe el string de salida en el archivo
                    lineBase = "%s%s%s%s\n" % ("SetKVBase bus=", busName, " kvln=", BTvoltage)
                    output_baseKV_DSS.write(lineBase)
                    feat = QgsFeature(pr.fields())
                    feat.setGeometry(
                        QgsGeometry.fromPoint(QgsPoint(float(busBT_List[bus]['X']), float(busBT_List[bus]['Y']))))
                    feat["BUS"] = busName
                    feat["BASEKV_LN"] = BTvoltage
                    pr.addFeatures([feat])
                output_buslistbt.close()  # Cierra el archivo de salida
                output_baseKV_DSS.close()  # Cierra el archivo de salida
                layer.updateExtents()
                layer.commitChanges()
            output_filesQGIS2DSS.close()  # cierra el archivo con la lista de archivos creados

            starRevLinesDisc = time.time()
            self.progress.progressBar.setValue(97)
            ############  Revisión de líneas desconectas
            connected_components_MT = list(
                nx.connected_component_subgraphs(grafoMT))  # Determina cuales son los componentes conectados
            connected_components_BT = list(nx.connected_component_subgraphs(grafoBTTotal))
            connected_components_ACO = list(nx.connected_component_subgraphs(grafoACO))

            for i, graph in enumerate(connected_components_MT):
                if graph.number_of_edges() == 1:
                    for edge in list(graph.nodes(data=True)):
                        aviso = QCoreApplication.translate('dialog',
                                                           u"Hay 1 segmento de línea MT  desconectado en: (") + str(
                            edge[2]['X1']) + ',' + str(edge[2]['Y1']) + ') ; (' + str(edge[2]['X2']) + ',' + str(
                            edge[2]['Y2']) + ')'
                        QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', u"Líneas primarias"),
                                                 QgsMessageLog.WARNING)

            for i, graph in enumerate(connected_components_BT):
                if graph.number_of_edges() == 1:
                    for edge in list(graph.nodes(data=True)):
                        if (not Graph_T1F.has_node(edge[0])) and (not Graph_T2F.has_node(edge[0])) and (
                        not Graph_T3F_multi.has_node(edge[0])) and (not Graph_T3F_single.has_node(edge[0])) and (
                        not Graph_T1F.has_node(edge[1])) and (not Graph_T2F.has_node(edge[1])) and (
                        not Graph_T3F_multi.has_node(edge[1])) and (not Graph_T3F_single.has_node(edge[1])):
                            aviso = QCoreApplication.translate('dialog',
                                                               u"Hay 1 segmento de línea BT  desconectado en: (") + str(
                                edge[2]['X1']) + ',' + str(edge[2]['Y1']) + ') ; (' + str(edge[2]['X2']) + ',' + str(
                                edge[2]['Y2']) + ')'
                            QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', u"Líneas secundarias"),
                                                     QgsMessageLog.WARNING)
            endRevLinesDisc = time.time()

            if Error == True:
                self.iface.messageBar().pushMessage("QGIS2OpenDSS", QCoreApplication.translate('dialog',
                                                                                               u'Error crítico. No fue posible completar la operación'),
                                                    QgsMessageBar.CRITICAL)  # Aviso de finalizado en barra de QGIS
            else:

                self.iface.messageBar().pushMessage("QGIS2OpenDSS", QCoreApplication.translate('dialog',
                                                                                               'Finalizado. Los archivos fueron creados correctamente en') + ":\n" + foldername,
                                                    QgsMessageBar.INFO)  # Aviso de finalizado en barra de QGIS
            self.progress.close()
            finalTime = time.time()

            ##Copia las bibliotecas a la carpeta de salida
            try:
                bibPath = foldername + '/Bibliotecas'
                # self.mkdir_p(bibPath)
                pluginPath = str(os.path.dirname(os.path.abspath(inspect.stack()[0][1])))
                shutil.copytree(pluginPath + '/Bibliotecas', bibPath)
            except:
                aviso = QCoreApplication.translate('dialog',
                                                   u"No se exportó la biblioteca de cables porque ya existe en la carpeta de salida.")
                QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', u"Biblioteca de cables"),
                                         QgsMessageLog.WARNING)

            ################# TIEMPOS
            if LMTactive == True:
                aviso = QCoreApplication.translate('dialog',
                                                   u"Tiempo de conectividad de líneas de media tensión: ") + str(
                    -startTimeMT + endTimeMT) + QCoreApplication.translate('dialog', ' segundos')
                QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', u"Tiempo de ejecución"),
                                         QgsMessageLog.WARNING)
            if LBTactive == True:
                aviso = QCoreApplication.translate('dialog',
                                                   u"Tiempo de conectividad de líneas de baja tensión: ") + str(
                    -startTimeBT + endTimeBT) + QCoreApplication.translate('dialog', ' segundos')
                QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', u"Tiempo de ejecución"),
                                         QgsMessageLog.WARNING)
            if LTRactive == True:
                aviso = QCoreApplication.translate('dialog', u"Tiempo de conectividad de transformadores: ") + str(
                    -startTimeTraf + endTimeTraf) + QCoreApplication.translate('dialog', ' segundos')
                QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', u"Tiempo de ejecución"),
                                         QgsMessageLog.WARNING)
            if (ACOactive == True):
                aviso = QCoreApplication.translate('dialog', u"Tiempo de conectividad de líneas de acometidas: ") + str(
                    -startTimeAco + endTimeAco) + QCoreApplication.translate('dialog', ' segundos')
                QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', u"Tiempo de ejecución"),
                                         QgsMessageLog.WARNING)
            if SEactive == True:
                aviso = QCoreApplication.translate('dialog', u"Tiempo de conectividad de la subestación: ") + str(
                    -startTimeSub + endTimeSub) + QCoreApplication.translate('dialog', ' segundos')
                QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', u"Tiempo de ejecución"),
                                         QgsMessageLog.WARNING)
            if (CARactive == True):
                aviso = QCoreApplication.translate('dialog', u"Tiempo de conectividad de las cargas: ") + str(
                    -startTimeLoad + endTimeLoad) + QCoreApplication.translate('dialog', ' segundos')
                QgsMessageLog.logMessage(aviso, QCoreApplication.translate('dialog', u"Tiempo de ejecución"),
                                         QgsMessageLog.WARNING)
            # print "El tiempo es: " + str(finalTime-startTime)
            # print "El tiempo de escritura fue "+ str(finalTime-startTimeWriting)
