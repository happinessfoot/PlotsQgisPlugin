# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Plots
                                 A QGIS plugin
 this plugin for drawing plots
                              -------------------
        begin                : 2020-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2020 by Shamsutdinov Ruslan
        email                : ruslik2014@gmail.com
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

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtXml import *
from PyQt4.QtSql import *
from qgis.gui import *
from qgis.utils import *
from qgis.core import *
from math import cos, sin,radians,degrees, pi,ceil,sqrt
import collections
import uuid
import re
# Initialize Qt resources from file resources.py
import resources

# Import the code for the DockWidget
from plots_module_dockwidget import PlotsDockWidget
import os.path




#команды описываем как классы, чтобы с ними можно было работать через стэк операций

#класс для работы с таблицей и точками
class WorkWithTableAndPoints:
    
    def getDifferenceBetween(self,endPoint,startPoint,magnet,tableWidget,azimuth=True):
        lastRow = tableWidget.rowCount()-1
        trueLength,trueAngle,trueMinutes = self.calcAngleLengthByPoints(endPoint,startPoint,magnet,False)
        
        tableLength = float(tableWidget.item(lastRow,2).text())
        tmpAngle = tableWidget.item(lastRow,3).text()
        if(not azimuth):
            tmpAngle = self.rumbToAzimuth(tmpAngle)
        tableAngle,tableMinutes = tmpAngle.replace('\'','').split(u'°')
        deltaLength = abs(trueLength-tableLength)
        deltaAngle = abs(int(trueAngle) - int(tableAngle))
        deltaMinutes = abs(int(trueMinutes)-int(tableMinutes))
        
        return deltaLength,deltaAngle,deltaMinutes
    
    #добавить в базу данных. Добавляет в базу делянку
    def addNepInDatabase(self,dockwidget,linePoints,points,rubberBandBinding,rubberBandNep,db,magnet=0.0):
        #формируем guid 4 версии
        polygonUuid = uuid.uuid4()
        #ищем слой делянки
        layerNep=self.findLayerByPattern("table=\"public\".\"t_non_operational_area\"","type=Polygon")
        layerPlot = self.findLayerByPattern("table=\"public\".\"t_plot\"","type=Polygon")
        ##print "addUB:",layerPlot
       
        if(layerPlot!=None):
            if(layerNep!=None):
                plotGuid = ""
                srid = layerPlot.source().split(" ")[7].split("=")[1]
                geometryPoly = rubberBandNep.asGeometry()
                geometryPolyWkt = geometryPoly.exportToWkt()
                area = round(geometryPoly.area()/10000,1)
                plotList = []
                for feature in layerPlot.getFeatures():
                    if feature.geometry().intersects(geometryPoly):
                        plotList.append(feature)
                maxArea = 0
                for feature in plotList:
                    tmpArea = geometryPoly.intersection(feature.geometry()).area()
                    ####print "tax_poly",geometryPoly.intersection(feature.geometry()).asPolygon()
                    if tmpArea>maxArea:
                        maxArea =tmpArea
                        plotGuid=str(feature['primarykey'])
                if(plotGuid):
                    nepNumber = 0
                    for nepFeature in layerNep.getFeatures(QgsFeatureRequest(QgsExpression("plot='"+plotGuid+"'"))):
                        if nepFeature["number"]:
                            if nepNumber<nepFeature["number"]:
                                nepNumber = nepFeature["number"]
                    nepNumber=nepNumber+1
                    db.executeQuery("insert into t_non_operational_area(primarykey,plot,shape,area,mangle,\"number\") values('"+str(polygonUuid)+"','"+plotGuid+"',st_geomFromText('"+geometryPolyWkt+"',"+srid+"),"+str(area)+","+str(magnet)+","+str(nepNumber)+")")
                    #Если у нас есть линия привязки то добавляем её в базу
                    if(len(linePoints)):
                        geometryLine = rubberBandBinding.asGeometry().exportToWkt()
                        db.executeQuery("insert into t_noa_binding_line(primarykey,noa,shape) values(uuid_generate_v4(),'"+str(polygonUuid)+"',st_geomFromText('"+geometryLine+"',"+srid+"))")
                    
                    pointValues = ""
                    rumbValues = ""
                    countLinePoints= len(linePoints)
                    for i in range(dockwidget.tableWidget_points.rowCount()):
                        number = dockwidget.tableWidget_points.item(i,0).text().replace('\'','`')
                        length = dockwidget.tableWidget_points.item(i,2).text()
                        angle = dockwidget.tableWidget_points.item(i,3).text()
                        #Если пользователь в настройках выбрал азимут, то преобразуем румб в азимут
                        if(dockwidget.radioButton_azimuth.isChecked()):
                            tmpSplit = angle.split(u'°')
                            minutes = float(tmpSplit[1].replace('\'',''))
                            angle = float(tmpSplit[0])
                            angle = self.azimuthToRumb(angle,minutes)
                        angle = angle.replace('\'','`')
                        ####print angle
                        #Если есть линия привязки, то добавляем её. Из за особеностей таблицы и точек, 
                        #получается так что во первых: у линии привязки у делянки последняя и первая точки соотвественно совпадают, 
                        #во-вторых: 1-ая точка линии привязки не отображается в таблице, так как в таблице отображаются НЕ ТОЧКИ, а ДЛИНЫ делянки и привязки
                        pointNumber = number.replace('\'','`').split('-')[0]
                        if(countLinePoints>0):
                            if i<countLinePoints:
                                pointValues=pointValues+"(uuid_generate_v4(),'"+str(polygonUuid)+"','"+pointNumber+"',st_geomFromText('"+QgsGeometry.fromPoint(linePoints[i]).exportToWkt()+"',"+srid+"),'5b8e90b5-df13-46b6-bf55-59146110dc28',"+str(i)+"),"
                                if(i<countLinePoints-1):
                                    rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','5b8e90b5-df13-46b6-bf55-59146110dc28','"+str(polygonUuid)+"'),"
                            if i-(countLinePoints-1)>=0:
                                pointValues=pointValues+"(uuid_generate_v4(),'"+str(polygonUuid)+"','"+pointNumber+"',st_geomFromText('"+QgsGeometry.fromPoint(points[i-(countLinePoints-1)]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504',"+str(i)+"),"
                                rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+str(polygonUuid)+"'),"
                        else:
                            rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+str(polygonUuid)+"'),"
                            pointValues=pointValues+"(uuid_generate_v4(),'"+str(polygonUuid)+"','"+pointNumber+"',st_geomFromText('"+QgsGeometry.fromPoint(points[i]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504',"+str(i)+"),"
                    #так как в конце остается символ ",", необходимо от него избавиться, поэтому создаем строку без последнего символа
                    pointValues=pointValues[:-1:]
                    rumbValues = rumbValues[:-1:]
                    ####print pointValues
                    ####print rumbValues
                    db.executeQuery("insert into t_noa_point(primarykey,noa,\"number\",shape,type_object,\"order\") values "+pointValues)
                    db.executeQuery("INSERT INTO t_noa_rumbs(primarykey, \"number\", distance, rumb, type, noa) values "+rumbValues)
                    
                    dockwidget.lineEdit_areaPlot.setText(str(area))
                    dockwidget.lineEdit_numberPlot.setText(str(nepNumber))
                    db.executeQuery("update t_plot set area=area_common-(select sum(area) from t_non_operational_area where plot = '"+plotGuid+"') where primarykey = '"+plotGuid+"'")
                    return str(polygonUuid)
                else:
                    QMessageBox.information(None,u"НЭП",u"НЭП нарисована за пределами делянки.")
            else:
                QMessageBox.information(None,u"НЭП",u"Добавьте слой t_non_operational_area")
        else:
            QMessageBox.information(None,u"Делянка",u"Добавьте слой t_plot")
        return ""
    
    
    #добавить в базу данных. Добавляет в базу делянку
    def addInDatabase(self,dockwidget,linePoints,points,rubberBandBinding,rubberBandPlot,db,magnet=0.0):
        #формируем guid 4 версии
        polygonUuid = uuid.uuid4()
        #ищем слой квартала
        layer = self.findLayerByPattern("\"public\".\"t_forestquarter\"")
        #ищем слой выдела
        layerTax=self.findLayerByPattern("table=\"public\".\"t_taxationisolated\"","type=MultiPolygon")
        layerPlot = self.findLayerByPattern("table=\"public\".\"t_plot\"","type=Polygon")
        #print "addUB:",layerPlot
        if(layer!=None):
            if(layerTax!=None):
                #получаем проекцию из источника данных слоя квартала
                srid = layer.source().split(" ")[7].split("=")[1]
                #linePoints = self.tool_draw.getLinePoints()
                
                #создаем геометрию из рисовалки
                geometryPoly = rubberBandPlot.asGeometry()
                #превращаем геометрию в строковое описание тип Polygon(1 1,2 2,3 3,1 1)
                geometryPolyWkt = geometryPoly.exportToWkt()
                area = round(geometryPoly.area()/10000,1)
                #получаем год рубки
                yearOfCutting = dockwidget.lineEdit_yearOfCutting.text()
                if(not yearOfCutting):
                    yearOfCutting="null"
                        
                forestquarterGuid = ""
                #создаем лист кварталов
                
                #Здесь мы создаем лист кварталов, которые пересекаются с нашей делянкой, для того, чтобы определить в каком квартале в большей степени находится нашая делянка
                #Сделано это на тот случай, если вдруг пользователь чуть-чуть залез на другой квартал, программа не посчитала, что делянка находится в той части квартала, куда пользователь нечайно залез. 
                #Можно сделать и запросом в базу, но как мне кажется, чтобы не нагружать сервак, пусть уж лучше на компьютере пользователя все это обсчитывается.

                forestquartersList = []
                #просматриваем все объекты, если пересекается с делянкой, то записываем в лист
                for feature in layer.getFeatures():
                    if feature.geometry().intersects(geometryPoly):
                        forestquartersList.append(feature)
                maxArea = 0
                #Просматриваем все кварталы в листе
                #Ищем квартал, в котором в большей степени находится делянка
                for feature in forestquartersList:
                    tmpArea = geometryPoly.intersection(feature.geometry()).area()
                    ####print "tax_poly",geometryPoly.intersection(feature.geometry()).asPolygon()
                    if tmpArea>maxArea:
                        maxArea =tmpArea
                        forestquarterGuid=str(feature['primarykey'])
                #Также, дялянка должна быть разбита на несколько частей, каждая из частей которых находится в своем выделе.
                #Для этого создаем лист и просматриваем все выдела, которые находится в том же квартале что и делянка, и проверяем перескаются ли они с делянкой.
                #Если пересекается, то записвыаем в лист геометрию части делянки, которая находится в выделе и запоминаем ключ выдела
                featureTaxes = []
                for feature in layerTax.getFeatures(QgsFeatureRequest(QgsExpression("forestquarter='"+forestquarterGuid+"'"))):
                    ####print "layerTax:",feature.geometry()
                    if feature.geometry() !=None and feature.geometry().intersects(geometryPoly):
                        featureTaxes.append([str(feature['primarykey']),geometryPoly.intersection(feature.geometry())])
                        
                if(forestquarterGuid):
                    ####print "insert into t_plot(primarykey,forestquarter,yearofcutting,geometry) values(uuid_generate_v4(),'e04852f9-5a10-4c98-b225-3028998d122d',6666,st_geomFromText('"+geometryPoly+"',"+srid+"))"
                    #Добавляем делянку в базу, area и area_common в нынешней версии повторяют друг друга, но в дальнейшем из общей площади (area_common) будет вычитаться площадь неэксплутационная
                    plotNumber = 0
                    for plotFeature in layerPlot.getFeatures(QgsFeatureRequest(QgsExpression("forestquarter='"+forestquarterGuid+"'"))):
                        if plotFeature["number"]:
                            if plotNumber<plotFeature["number"]:
                                plotNumber = plotFeature["number"]
                    plotNumber=plotNumber+1
                    db.executeQuery("insert into t_plot(primarykey,forestquarter,yearofcutting,shape,area,area_common,mangle,\"number\") values('"+str(polygonUuid)+"','"+forestquarterGuid+"',"+yearOfCutting+",st_geomFromText('"+geometryPolyWkt+"',"+srid+"),"+str(area)+","+str(area)+","+str(magnet)+","+str(plotNumber)+")")
                    #Если у нас есть линия привязки то добавляем её в базу
                    if(len(linePoints)):
                        geometryLine = rubberBandBinding.asGeometry().exportToWkt()
                        db.executeQuery("insert into t_binding_line(primarykey,plot,shape) values(uuid_generate_v4(),'"+str(polygonUuid)+"',st_geomFromText('"+geometryLine+"',"+srid+"))")
                    
                    pointValues = ""
                    rumbValues = ""
                    countLinePoints= len(linePoints)
                    for i in range(dockwidget.tableWidget_points.rowCount()):
                        number = dockwidget.tableWidget_points.item(i,0).text()
                        length = dockwidget.tableWidget_points.item(i,2).text()
                        angle = dockwidget.tableWidget_points.item(i,3).text()
                        #Если пользователь в настройках выбрал азимут, то преобразуем румб в азимут
                        if(dockwidget.radioButton_azimuth.isChecked()):
                            tmpSplit = angle.split(u'°')
                            minutes = float(tmpSplit[1].replace('\'',''))
                            angle = float(tmpSplit[0])
                            angle = self.azimuthToRumb(angle,minutes)
                        angle = angle.replace('\'','`')
                        ####print angle
                        #Если есть линия привязки, то добавляем её. Из за особеностей таблицы и точек, 
                        #получается так что во первых: у линии привязки у делянки последняя и первая точки соотвественно совпадают, 
                        #во-вторых: 1-ая точка линии привязки не отображается в таблице, так как в таблице отображаются НЕ ТОЧКИ, а ДЛИНЫ делянки и привязки
                        if(countLinePoints>0):
                            if i<countLinePoints:
                                pointValues=pointValues+"(uuid_generate_v4(),'"+str(polygonUuid)+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(linePoints[i]).exportToWkt()+"',"+srid+"),'5b8e90b5-df13-46b6-bf55-59146110dc28'),"
                                if(i<countLinePoints-1):
                                    rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','5b8e90b5-df13-46b6-bf55-59146110dc28','"+str(polygonUuid)+"'),"
                            if i-(countLinePoints-1)>=0:
                                pointValues=pointValues+"(uuid_generate_v4(),'"+str(polygonUuid)+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(points[i-(countLinePoints-1)]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504'),"
                                rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+str(polygonUuid)+"'),"
                        else:
                            rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+str(polygonUuid)+"'),"
                            pointValues=pointValues+"(uuid_generate_v4(),'"+str(polygonUuid)+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(points[i]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504'),"
                    #так как в конце остается символ ",", необходимо от него избавиться, поэтому создаем строку без последнего символа
                    pointValues=pointValues[:-1:]
                    rumbValues = rumbValues[:-1:]
                    ####print pointValues
                    ####print rumbValues
                    db.executeQuery("insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues)
                    db.executeQuery("INSERT INTO t_rumbs(primarykey, \"number\", distance, rumb, type, plot) values "+rumbValues)
                    
                    #Те самые части делянки
                    isolatedValues = ""
                    #формируем запрос
                    for item in featureTaxes:
                        isolatedValues =isolatedValues+("(uuid_generate_v4(),'"+item[0]+"','"+str(polygonUuid)+"',st_geomFromText('"+item[1].exportToWkt()+"',"+srid+"),'1'),")
                    isolatedValues=isolatedValues[:-1:]
                    db.executeQuery("insert into t_isolatedplots(primarykey,isolated,plot,shape,actual) values "+isolatedValues)

                    dockwidget.lineEdit_areaPlot.setText(str(area))
                    dockwidget.lineEdit_numberPlot.setText(str(plotNumber))
                    return str(polygonUuid)
                else:
                    QMessageBox.information(None,u"Квартал",u"Делянка нарисована за пределами квартала.")
            else:
                QMessageBox.information(None,u"Квартал",u"Добавьте слой t_taxationisolated с типом геометрии polygon/multipolygon.")
        else:
            QMessageBox.information(None,u"Добавьте слой t_forestquarter.")
        return ""
    #!!!!!!!    
    def updateNepPointsInDatabase(self,dockwidget,tableWidget,points,draw,db,guidNep,azimuth):
        linePoints = draw.getLinePoints()
        if(guidNep and db!=None):
            srid = None
            layerPlot = self.findLayerByPattern("\"public\".\"t_plot\"")
            layerNep = self.findLayerByPattern("\"public\".\"t_non_operational_area\"")
            srid = layerPlot.source().split(" ")[7].split("=")[1]
            if(srid):
                if(not db.openConnection()):
                    db.setConnectionInfo()
                    db.openConnection()
                
                plotGuid=""
                for feature in layerNep.getFeatures(QgsFeatureRequest(QgsExpression("primarykey='"+guidNep+"'"))):
                    plotGuid = str(feature['plot'])
                db.executeQuery("alter table t_non_operational_area disable trigger all")
                db.executeQuery("alter table t_noa_binding_line disable trigger all")
                db.executeQuery("delete from t_noa_point where noa='"+guidNep+"'")
                db.executeQuery("delete from t_noa_rumbs where noa='"+guidNep+"'")
                countLinePoints = len(linePoints)
                bindingLine = QgsGeometry.fromPolyline(linePoints)
                tmpPoints = list(points)
                #tmpPoints.append(tmpPoints[0])
                polygon = QgsGeometry.fromPolygon([tmpPoints])
                
                db.executeQuery("delete from t_noa_binding_line where noa='"+guidNep+"'")
                if(len(linePoints)>0):
                    db.executeQuery("insert into t_noa_binding_line(primarykey,shape,noa) values(uuid_generate_v4(),st_geomFromText('"+bindingLine.exportToWkt()+"',"+srid+"),'"+guidNep+"')")
                db.executeQuery("update t_non_operational_area set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+"),area="+str(round(polygon.area()/10000,1))+" where primarykey='"+guidNep+"'")
                db.executeQuery("update t_plot set area=area_common-(select sum(area) from t_non_operational_area where plot = '"+plotGuid+"') where primarykey = '"+plotGuid+"'")
                ###print "update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guidPlot+"'"
                ###print len(self.linePoints)
                pointValues=""
                rumbValues = ""               
                for i in range(tableWidget.rowCount()):
                    number = tableWidget.item(i,0).text().replace('\'','`')
                    length = tableWidget.item(i,2).text()
                    angle = tableWidget.item(i,3).text()
                    pointNumber = number.split('-')[0]
                    if(azimuth):
                        tmpSplit = angle.split(u'°')
                        minutes = float(tmpSplit[1].replace('\'',''))
                        angle = float(tmpSplit[0])
                        angle = self.azimuthToRumb(angle,minutes)
                    angle = angle.replace('\'','`')
                    ####print angle 
                    if(countLinePoints>0):
                        if i<countLinePoints:
                            pointValues=pointValues+"(uuid_generate_v4(),'"+guidNep+"','"+pointNumber+"',st_geomFromText('"+QgsGeometry.fromPoint(linePoints[i]).exportToWkt()+"',"+srid+"),'5b8e90b5-df13-46b6-bf55-59146110dc28',"+str(i)+"),"
                            if(i<countLinePoints-1):
                                rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','5b8e90b5-df13-46b6-bf55-59146110dc28','"+guidNep+"'),"
                        if i-(countLinePoints-1)>=0:
                            pointValues=pointValues+"(uuid_generate_v4(),'"+guidNep+"','"+pointNumber+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i-(countLinePoints-1)]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504',"+str(i)+"),"
                            rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+guidNep+"'),"
                    else:
                        rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+guidNep+"'),"
                        pointValues=pointValues+"(uuid_generate_v4(),'"+guidNep+"','"+pointNumber+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504',"+str(i)+"),"
                        ####print pointValues
                        ####print rumbValues
                pointValues=pointValues[:-1:]
                rumbValues = rumbValues[:-1:]
                ####print "insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues
                ####print rumbValues
                db.executeQuery("insert into t_noa_point(primarykey,noa,\"number\",shape,type_object,\"order\") values "+pointValues)
                db.executeQuery("INSERT INTO t_noa_rumbs(primarykey, \"number\", distance, rumb, type, noa) values "+rumbValues)
                db.executeQuery("alter table t_non_operational_area enable trigger all")
                db.executeQuery("alter table t_noa_binding_line enable trigger all")
                dockwidget.lineEdit_areaPlot.setText(str(round(polygon.area()/10000,1)))
                
                db.closeConnection()
            else:
                QMessageBox.information(None,u"Квартал",u"Добавьте слой t_forestquarter для изменения делянки.")
    #!!!!!!!!            
    def updatePointsInDatabase(self,dockwidget,tableWidget,points,draw,db,guidPlot,azimuth):
        linePoints = draw.getLinePoints()
        if(guidPlot and db!=None):
            srid = None
            layerQuart = self.findLayerByPattern("\"public\".\"t_forestquarter\"")
            layerPlot = self.findLayerByPattern("\"public\".\"t_plot\"")
            srid = layerQuart.source().split(" ")[7].split("=")[1]
            layerTax=self.findLayerByPattern("table=\"public\".\"t_taxationisolated\"","type=MultiPolygon")
            if(srid):
                if(not db.openConnection()):
                    db.setConnectionInfo()
                    db.openConnection()
                
                forestquarterGuid=""
                for feature in layerPlot.getFeatures(QgsFeatureRequest(QgsExpression("primarykey='"+guidPlot+"'"))):
                    forestquarterGuid = str(feature['forestquarter'])
                db.executeQuery("delete from t_plot_point where plot_fk='"+guidPlot+"'")
                db.executeQuery("delete from t_rumbs where plot='"+guidPlot+"'")
                countLinePoints = len(linePoints)
                bindingLine = QgsGeometry.fromPolyline(linePoints)
                tmpPoints = list(points)
                #print "UPDATEPOINTSINDATABASE points", points
                #tmpPoints.append(tmpPoints[0])
                polygon = QgsGeometry.fromPolygon([tmpPoints])
                
                featureTaxes = []
                for feature in layerTax.getFeatures(QgsFeatureRequest(QgsExpression("forestquarter='"+forestquarterGuid+"'"))):
                    ####print "layerTax:",feature.geometry()
                    if feature.geometry() !=None and feature.geometry().intersects(polygon):
                        featureTaxes.append([str(feature['primarykey']),polygon.intersection(feature.geometry())])
                
                db.executeQuery("delete from t_binding_line where plot='"+guidPlot+"'")
                if(len(linePoints)>0):
                    db.executeQuery("insert into t_binding_line(primarykey,shape,plot) values(uuid_generate_v4(),st_geomFromText('"+bindingLine.exportToWkt()+"',"+srid+"),'"+guidPlot+"')")
                db.executeQuery("update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+"),area_common="+str(round(polygon.area()/10000,1))+" where primarykey='"+guidPlot+"'")
                ###print "update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guidPlot+"'"
                ###print len(self.linePoints)
                pointValues=""
                rumbValues = ""               
                for i in range(tableWidget.rowCount()):
                    number = tableWidget.item(i,0).text()
                    length = tableWidget.item(i,2).text()
                    angle = tableWidget.item(i,3).text()
                    if(azimuth):
                        tmpSplit = angle.split(u'°')
                        minutes = float(tmpSplit[1].replace('\'',''))
                        angle = float(tmpSplit[0])
                        angle = self.azimuthToRumb(angle,minutes)
                    angle = angle.replace('\'','`')
                    ####print angle
                    if(countLinePoints>0):
                        if i<countLinePoints:
                            pointValues=pointValues+"(uuid_generate_v4(),'"+guidPlot+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(linePoints[i]).exportToWkt()+"',"+srid+"),'5b8e90b5-df13-46b6-bf55-59146110dc28'),"
                            if(i<countLinePoints-1):
                                rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','5b8e90b5-df13-46b6-bf55-59146110dc28','"+guidPlot+"'),"
                        if i-(countLinePoints-1)>=0:
                            pointValues=pointValues+"(uuid_generate_v4(),'"+guidPlot+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i-(countLinePoints-1)]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504'),"
                            rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+guidPlot+"'),"
                    else:
                        rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+guidPlot+"'),"
                        pointValues=pointValues+"(uuid_generate_v4(),'"+guidPlot+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504'),"
                        ####print pointValues
                        ####print rumbValues
                pointValues=pointValues[:-1:]
                rumbValues = rumbValues[:-1:]
                ####print "insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues
                ####print rumbValues
                db.executeQuery("insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues)
                db.executeQuery("INSERT INTO t_rumbs(primarykey, \"number\", distance, rumb, type, plot) values "+rumbValues)
                
                db.executeQuery("delete from t_isolatedplots where plot = '"+guidPlot+"'")
                isolatedValues = ""
                for item in featureTaxes:
                    isolatedValues =isolatedValues+("(uuid_generate_v4(),'"+item[0]+"','"+guidPlot+"',st_geomFromText('"+item[1].exportToWkt()+"',"+srid+"),'1'),")
                isolatedValues=isolatedValues[:-1:]
                db.executeQuery("insert into t_isolatedplots(primarykey,isolated,plot,shape,actual) values "+isolatedValues)
                dockwidget.lineEdit_areaPlot.setText(str(round(polygon.area()/10000,1)))
                
                db.closeConnection()
            else:
                QMessageBox.information(None,u"Квартал",u"Добавьте слой t_forestquarter для изменения делянки.")
    
    
    def findLayerByPattern(self, table, geometryType=None):
        for layer in QgsMapLayerRegistry.instance().mapLayers().values():
            if(geometryType!=None):
                if (table in layer.dataProvider().dataSourceUri() and geometryType in layer.dataProvider().dataSourceUri()):
                    return layer
            else:
                if(table in layer.dataProvider().dataSourceUri()):
                    return layer
        return None
    
    def rumbToAzimuth(self,angle):
        result = ""
        splitted = angle.split(' ')
        letters = splitted[0]
        tmpAngle = splitted[1]
        splitted = tmpAngle.split(u'°')
        minutes = splitted[1].split('\'')[0]
        minutes = float(minutes)
        tmpAngle = float(splitted[0])
        tmpAngle = tmpAngle+round(minutes/60,2)
        if letters==u"С":
            result = str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        elif letters==u"СВ":
            result = str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        elif letters==u"В":
            result = str(int(tmpAngle)+90)+u'°'+str(int(minutes))+u'\''
        elif letters==u"ЮВ":
            tmpAngle=180-tmpAngle
            minutes = round(((tmpAngle % 1)*60))
            result = str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        elif letters==u"Ю":
            result = str(int(tmpAngle)+180)+u'°'+str(int(minutes))+u'\''
        elif letters==u"ЮЗ":
            tmpAngle=tmpAngle+180
            minutes = round(((tmpAngle % 1)*60))
            result = str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        elif letters==u"З":
            result = str(int(tmpAngle)+270)+u'°'+str(int(minutes))+u'\''
        elif letters==u"СЗ":
            tmpAngle=360-tmpAngle
            minutes = round(((tmpAngle % 1)*60))
            result = str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        return result
    def azimuthToRumb(self,angle,minutes=0.0):
        result = ""
        tmpAngle = angle+round(minutes/60,2)
        if tmpAngle==0:
            minutes = round(((tmpAngle % 1)*60))
            result=u"С "+str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        elif tmpAngle>0 and tmpAngle<90:
            minutes = round(((tmpAngle % 1)*60))
            result=u"СВ "+str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        elif tmpAngle==90:
            tmpAngle = 90-tmpAngle
            minutes = round(((tmpAngle % 1)*60))
            result=u"В "+str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        elif tmpAngle>90 and tmpAngle<180:
            tmpAngle = 180-tmpAngle
            minutes = round(((tmpAngle % 1)*60))
            result=u"ЮВ "+str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        elif tmpAngle==180:
            tmpAngle = 180-tmpAngle
            minutes = round(((tmpAngle % 1)*60))
            result=u"Ю "+ str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        elif tmpAngle>180 and tmpAngle<270:
            tmpAngle = tmpAngle-180
            minutes = round(((tmpAngle % 1)*60))
            result=u"ЮЗ "+ str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        elif tmpAngle==270:
            tmpAngle = tmpAngle-270
            minutes = round(((tmpAngle % 1)*60))
            result=u"З "+ str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        elif tmpAngle>270 and tmpAngle<360:
            tmpAngle = 360-tmpAngle
            minutes = round(((tmpAngle % 1)*60))
            result=u"СЗ "+ str(int(tmpAngle))+u'°'+str(int(minutes))+u'\''
        return result
        
    #удаление строки из таблицы
    #Механизм таков, что при удалении, смотрятся строки, которые выбрал пользователь и они одна за другой удаляются
    def deleteRow(self,tableWidget,linePoints,points,startPoint,magnet,azimuth=True,nepAdd=False):
       # ###print "workWithDelPoints:", points
        j = 0
        
        select = tableWidget.selectionModel()
        if select.hasSelection():
            if len(select.selectedIndexes())>0:
                rows = set()
                for item in select.selectedIndexes():
                    ####print "item row: ",item.row()
                    rows.add(item.row())
                #необходимо сортировать, так как нам нужно, чтобы все строки удалялись последовательно. А множество (set), даже если добавлять последовательно, оно нарушает порядок
                rows = (sorted(rows))
                ####print(rows)
                for i in rows:
                    #запоминаем строку, в конце это нам понадоибится
                    row = tableWidget.currentRow()
                    rowCount = tableWidget.rowCount()
                    ####print "workWithDelPoints:", points
                    #так как количество строк уменьшается и количество точек тоже, то при следующей итерации, запись в таблице и точка могут иметь разные индексы
                    i=i-j
                    #Если количество строк меньше 3-х, то просто очищаем таблицу, но при этом 1-ю точку не удаляем, так как она является стартом.
                    if i<=rowCount-1:
                        ####print "row: ",row
                        if rowCount<3:
                            tableWidget.setRowCount(0)
                            del points[1:]
                        else:
                            tableWidget.removeRow(i)
                            ####print "points deleteRowFunction:",points," index:",i
                            ####print "linePoints",linePoints
                            ####print "len linePoint",len(linePoints),"i-(len(linePoints)-1):",i-(len(linePoints)-1)
                            
                            #индекс записи в таблице, который отмечен привязкой    
                            lineIndex = -1
                            if len(linePoints)>0:
                                if i<len(linePoints)-2:
                                    del linePoints[i+1]
                                    ####print(i-(len(linePoints)-1))
                                    #del points[i-(len(linePoints)-1)]
                                elif i==len(linePoints)-2:
                                    ####print "rovno0,",i
                                    #del points[0]# = QgsPoint(linePoints[i].x(),linePoints[i].y())
                                    
                                    #Если удалена точка, которая одновременно есть у линии и делянки, то нужно сформировать новую
                                    #Можно было бы написать points[0]=linePoints[i] НО тогда у нас points[0] и linePoints[i] будут ссылаться на один объект и если его удалить, то удалиться он в обоих листах
                                    points[0] = QgsPoint(linePoints[i].x(),linePoints[i].y())
                                    if len(linePoints)-2 == 0:
                                        del linePoints[:]
                                    else:
                                        del linePoints[i+1]
                                else:
                                    del points[i-(len(linePoints)-1)]

                                lineIndex = len(linePoints)-1
                            else:
                               del points[i]
                            ####print "points deleteRowFunction:",points," index:",i
                            
                            #обновляем таблицу
                            
                            self.resetTable(i,tableWidget,lineIndex,nepAdd)
                            #так как мы удалили точку, то теперь необходимо пересчитать дистанцию от предыдущей точки, до нынешней.
                            if i<rowCount-1:
                                if(len(linePoints)>0):
                                    if(i<=len(linePoints)-1):
                                        ####print("i<",i)
                                        length,angle,minutes = self.calcAngleLengthByPoints(linePoints[i-1],linePoints[i],magnet)
                                    # elif i==len(linePoints)-1:
                                        # ###print("tuta i=",i)
                                        # length,angle,minutes = self.calcAngleLengthByPoints(linePoints[i-1],linePoints[i],magnet)
                                    else:
                                        ####print("i>",i)
                                        length,angle,minutes = self.calcAngleLengthByPoints(points[i-(len(linePoints)-1)-1],points[i-(len(linePoints)-1)],magnet)
                                else:
                                    length,angle,minutes = self.calcAngleLengthByPoints(points[i-1],points[i],magnet)
                            else:
                                if(len(linePoints)>0):
                                    if(i<=len(linePoints)-1):
                                        ####print("i<",i)
                                        length,angle,minutes = self.calcAngleLengthByPoints(linePoints[i-1],linePoints[i],magnet)
                                    # elif i==len(linePoints)-1:
                                        # ###print("tuta i=",i)
                                        # length,angle,minutes = self.calcAngleLengthByPoints(linePoints[i-1],linePoints[i],magnet)
                                    else:
                                        ####print("i>",i)
                                        length,angle,minutes = self.calcAngleLengthByPoints(points[i-(len(linePoints)-1)-2],points[i-(len(linePoints)-1)-1],magnet)
                                else:
                                    length,angle,minutes = self.calcAngleLengthByPoints(points[i-2],points[i-1],magnet)
                                #length,angle,minutes = self.calcAngleLengthByPoints(points[i-2],points[i-1],magnet)
                            ####print row
                            if(i-1>=0):
                                ####print "lnegth,angle",length,angle
                                tableWidget.item(i-1,2).setText(str(length))
                                if(azimuth):
                                    tableWidget.item(i-1,3).setText(str(int(angle))+u'°'+str(int(round(minutes)))+u'\'')
                                else:
                                    tableWidget.item(i-1,3).setText(self.azimuthToRumb(float(angle),float(minutes)))
                            #здесь обновляем все точки
                            
                            self.calculateAllPoints(tableWidget,linePoints,points,startPoint,row,magnet,self.magnet,True,azimuth)
                    j=j+1
                rowCount = tableWidget.rowCount()
                startPoint=points[-1]
                if(len(linePoints))>0:
                    self.tableWidget.blockSignals(True)
                    self.tableWidget.item(lineIndex-1,1).setCheckState(Qt.Checked)
                    self.tableWidget.blockSignals(False)
        ####print "deleteRow:",id(points)
    
    #!!!!!
    def calcAngleLengthByPoints(self,firestPoint,secondPoint,magnet=0.0,roundMinutes=True):
        seg = QgsFeature()
        seg.setGeometry(QgsGeometry.fromPolyline([firestPoint,secondPoint]))
        #Вычисляем длину между точками
        length = seg.geometry().length()
        #Вычисляем азимут между точками
        angle = QgsPoint.azimuth(firestPoint,secondPoint)
        angle = angle-magnet
        if(angle<0):
            angle=360+angle
        if angle>=360:
            angle=angle-360
        ####print self.minutes/60
        if roundMinutes:
            minutes = round(((angle % 1)*60),2)
        else:
            minutes = int(((angle % 1)*60))
        angle = int(angle)
        angle = round(angle,2)#+"C"+str(round(((self.angle % 1)*60),2))+"'"
        length = round(length,1)
        
        return length,angle,minutes
    #пересчет номеров точек
    def recountPoints(self,tableWidget,row,lineIndex=-1):
        rowCount = tableWidget.rowCount()
        ####print("recountPoints")
        for i in range(row+1,rowCount):
            ####print(i,rowCount-1)
            if i<rowCount-1:
                pointNumber = tableWidget.item(i,0).text()
                numberLast = int(pointNumber.split('-')[1])
                tableWidget.item(i,0).setText(str(numberLast)+"-"+str(numberLast+1))
                ####print str(numberLast)+"-"+str(numberLast+1)
            else:
                ####print("lineIndex",lineIndex)
                if(lineIndex>-1):
                    ####print("str(rowCount-1)+"-"+str(lineIndex+1)",str(rowCount-1)+"-"+str(lineIndex))
                    tableWidget.item(rowCount-1,0).setText(str(rowCount-1)+"-"+str(lineIndex))
                else:
                    tableWidget.item(rowCount-1,0).setText(str(rowCount-1)+"-"+"0")
        
    #Обновления точек, основываясь на информации о дистанции и угле
    def calculateAllPoints(self,tableWidget,linePoints,points,startPoint,row,magnet,prevMagnet=0.0,editMagnet=False,azimuth=True,fix=True,nepAdd=False):
        ##print "FIX",fix
        rowCount = tableWidget.rowCount()
        ####print "row",row
        ####print "linePoints",linePoints
        ####print "points",points
        tmp = rowCount
        if (tmp-1==0):
            tmp = tmp+1
        for rowIndex in range(row,tmp-1):
            length = float(tableWidget.item(rowIndex,2).text())
            if (not azimuth):
                tmp = self.rumbToAzimuth(tableWidget.item(rowIndex,3).text())
            else:
                tmp = tableWidget.item(rowIndex,3).text()
            ##print "calculate",tmp,azimuth,editMagnet,prevMagnet
            if u'°' in tmp:
                tmpAngle=tmp.split(u'°')
                if len(tmpAngle[1])>0:
                    ##print "calculateAllPointsTmpAngle:", tmpAngle[0],tmpAngle[1]
                    angle = float(tmpAngle[0])+float(tmpAngle[1].split('\'')[0])/60+prevMagnet
                else:
                    angle = float(tmpAngle[0])+prevMagnet
            else:    
                angle = float(tmp.split('.')[0])+float(tmp.text().split('.')[1])/60+prevMagnet
            
            ##print "angle calc1:",angle

            
            ###print "before:",angle
            if not fix:
                angle = angle - prevMagnet
                angle = angle + magnet
            if(angle<0):
                angle = 360+angle
            if angle>=360:
                angle=angle-360
            ###print "after:",angle
            #minutes = round(((angle % 1)*60))
            ###print "after:",angle
            ###print "minutes:",minutes
            ####print "points: ",points  
            ####print "rowIndex: ",rowIndex
            ####print "length: ",length
            ####print(len(linePoints)-rowIndex-1)
            if len(linePoints)>0:
                pointIndex = rowIndex-(len(linePoints)-1)
            else:
                pointIndex = rowIndex
            if(rowIndex<len(linePoints)-1):
                linePoints[rowIndex+1]=QgsPoint(linePoints[rowIndex].x()+length*(sin(radians(angle))),linePoints[rowIndex].y()+length*(cos(radians(angle))))
            else:
                ##print "POINTS POINTINDEX BEFORE",points[pointIndex+1],pointIndex+1
                if(len(linePoints)>0 and rowIndex==len(linePoints)-1):
                    points[0] = QgsPoint(linePoints[-1].x(),linePoints[-1].y())
                points[pointIndex+1] = QgsPoint(points[pointIndex].x()+length*(sin(radians(angle))),points[pointIndex].y()+length*(cos(radians(angle))))
                ##print "POINTS POINTINDEX AFTER",points[pointIndex+1],pointIndex+1
            ###print "azimuthToRumb:",self.azimuthToRumb(float(angle),float(minutes))
            ###print "angle+round(minutes/60,2):",int(angle)+round(float(minutes)/60,2)
            #angle = angle - magnet
            if editMagnet:
                ##print "tyt editMagnet"
                angle = angle-magnet
            if(angle<0):
                angle = 360+angle
            minutes = round(((angle % 1)*60))
            if minutes == 60:
                angle=angle+1
                minutes = 0   
            if angle>=360:
                angle=angle-360
            ##print "CAAAAAAAAAAAAAAALC:",angle,magnet
            if(azimuth):
                tableWidget.item(rowIndex,3).setText(str(int(angle))+u'°'+str(int(minutes))+u'\'')
            else:
                tableWidget.item(rowIndex,3).setText(self.azimuthToRumb(float(int(angle)),float(minutes)))
            ##print "angle calc2:",angle
            #tableWidget.item(rowIndex,3).setText(str(int(angle))+u'°'+str(int(minutes))+u'\'')
        if(rowCount>1):
            ####print("rowCount",rowCount)
            seg = QgsFeature()
            tmpPoints = [points[-1],points[0]]
            seg.setGeometry(QgsGeometry.fromPolyline(tmpPoints))
            tableWidget.item(rowCount-1,2).setText(str(round(seg.geometry().length(),1)))
            angle = QgsPoint.azimuth(tmpPoints[0],tmpPoints[1])

            ####print "before:", angle
            angle=angle-magnet
            if(angle<0):
                angle = 360+angle
            minutes = round(((angle % 1)*60))
            if minutes == 60:
                angle=angle+1
                minutes = 0   
            ##print "iamhere:",angle
            if angle>=360:
                angle=angle-360
            # после округления может оказаться так, что например минуты стали равны 60
         
            ####print "after:", angle
            ###print angle,minutes,self.azimuthToRumb(float(int(angle)),float(minutes))
            if(azimuth):
                tableWidget.item(rowCount-1,3).setText(str(int(angle))+u'°'+str(int(minutes))+u'\'')
            else:
                tableWidget.item(rowCount-1,3).setText(self.azimuthToRumb(float(int(angle)),float(minutes)))
        ##print "POOOOOOOOOOOOINTS:",points
        #startPoint = points[rowCount-1]
        
    #!!!!!
    #ресет таблицы после удаления
    def resetTable(self,rowIndex,tableWidget,lineIndex=-1,nepAdd=False):
        rowCount = tableWidget.rowCount()
        i = 0
        if not nepAdd:
            while rowIndex<rowCount-1:
                tableWidget.item(rowIndex,0).setText(str(rowIndex)+"-"+str(rowIndex+1))
                rowIndex=rowIndex+1
            if rowCount>1:
                if(lineIndex>0):
                    tableWidget.item(rowCount-1,0).setText(str(rowCount-1)+"-"+str(lineIndex))
                else:
                    tableWidget.item(rowCount-1,0).setText(str(rowCount-1)+"-"+"0")
        else:
            #print "ROWINDEX IN RESETTABLE",rowIndex
            if rowIndex>=0 and rowIndex<=rowCount-1:
                #запоминаем, чтобы постоянно не обращаться к tableWidget.item(rowIndex,0).text()
                tmpText=tableWidget.item(rowIndex,0).text()
                #проверяем есть ли в предыдущем столбце знак штриха
                
                if rowIndex==0:
                    tmpSecondPrev = tableWidget.item(rowCount-1,0).text().split('-')[1]
                else:
                    tmpSecondPrev = tableWidget.item(rowIndex-1,0).text().split('-')[1]
                #так как часто будем использовать tmpText.split('-') просто запомним это, чтобы постоянно не вызывать
                tmpSplit = tmpText.split('-')
                #if ('\'' in tmpSecondPrev and '\'' in tmpSplit[0]) or ('\'' not in tmpSecondPrev and '\'' in tmpSplit[1]) or ('\'' in tmpSplit[0]):
                if (('\'' in tmpSplit[0] or ('\'' not in tmpSecondPrev and '\'' in tmpSplit[1])) and rowIndex>0) or ('\'' in tmpSecondPrev and rowIndex==0):
                    i=1
                #тут все зависит от того, что содержится в строке, если на 1-ой позиции стоит число со штрихом и на 2-ой позиции число со штрихом, то тогда мы уменьшим число на 2-ой позиции
                if '\'' in tmpSplit[0] and '\'' in tmpSplit[1] and rowIndex>0:
                    #print "TMPSPLIT before",tmpSplit
                    tmpSplit[1]=str(int(tmpSplit[1].replace('\'',''))-i)+"\'"
                    #print "TMPSPLIT after",tmpSplit
                elif rowIndex==0 and '\'' in tmpSecondPrev:
                    if '\'' in tmpSplit[0]:
                        tmpSplit[0]=str(int(tmpSplit[0].replace('\'',''))-i)+"\'"
                    if '\'' in tmpSplit[1]:
                        tmpSplit[1]=str(int(tmpSplit[1].replace('\'',''))-i)+"\'"
                    
                if rowIndex>0:
                    tmpText =tmpSecondPrev+"-"+ tmpSplit[1]
                else:
                    tmpText=tmpSplit[0]+"-"+tmpSplit[1]
                #print "TMPTEXT",tmpText
                #print "tableWidget",tableWidget.item(rowIndex,0).text()
                tableWidget.item(rowIndex,0).setText(tmpText)    
                rowIndex=rowIndex+1 
                #а дальше можно просто уменьшать числа которые содержат штрих
            while rowIndex<rowCount-1:
                tmpText = tableWidget.item(rowIndex,0).text()
                if '\'' in tmpText:
                    tmpSplit = tmpText.split('-')
                    if '\'' in tmpSplit[0]:
                        tmpSplit[0]=str(int(tmpSplit[0].replace('\'',''))-i)+"\'"
                    if '\'' in tmpSplit[1]:
                        tmpSplit[1]=str(int(tmpSplit[1].replace('\'',''))-i)+"\'"
                    tmpText = tmpSplit[0]+"-"+tmpSplit[1]
                #print "TMPTEXT3",tmpText
                #print "tableWidget2",tableWidget.item(rowCount-1,0).text()
                tableWidget.item(rowIndex,0).setText(tmpText)
                rowIndex=rowIndex+1
            if rowCount>1:
                tmpText = tableWidget.item(rowCount-2,0).text().split('-')[1]+"-"
                if(lineIndex>0):
                    tmpText=tmpText+tableWidget.item(lineIndex,0).text().split('-')[1]
                else:
                    tmpText=tmpText+tableWidget.item(0,0).text().split('-')[0]
                tableWidget.item(rowCount-1,0).setText(tmpText)
        #print "tableWidget3",tableWidget.item(rowCount-1,0).text()
    #Добавление строки
    def addRows(self,tableWidget,linePoints,points,startPoint,endPoint,length,angle,magnet=0.0,azimuth=True,nepAdd=False,equalAndNepPoints=None):  
        countPoints = len(points)
        if(len(linePoints)>0):
            countPoints=countPoints+len(linePoints)-1
            endNumberPoint = len(linePoints)-1
        else:
            endNumberPoint = 0
        rowCount = tableWidget.rowCount()
        angle = angle-magnet
        minutes = round(((angle % 1)*60))
        ####print angle
        if(angle<0):
            angle = 360+angle
        if angle>360:
            angle = angle-360
        ####print "countPoints:",countPoints
        ####print "rowCount:",rowCount
        if nepAdd:
            if equalAndNepPoints[0]==None:
                firstNumber = equalAndNepPoints[0]+"\'"
            else:
                firstNumber = equalAndNepPoints[0]
            if equalAndNepPoints[1]==None:  
                second_number = equalAndNepPoints[1]+"\'"
            else:
                second_number=equalAndNepPoints[1]
        else:
            firstNumber = str(countPoints-1)
            second_number = str(countPoints)
        if countPoints>1:
            endNumberPoint=tableWidget.item(0,0).text().split('-')[0]
            if (len(linePoints)>0):
                endNumberPoint=tableWidget.item((len(linePoints)-2),0).text().split('-')[1]
        if countPoints>1 and rowCount<countPoints:
            self.addRow(tableWidget,rowCount,firstNumber,second_number,length,int(angle),round(minutes),azimuth)
            rowCount=rowCount+1
            length,angle,minutes = self.calcAngleLengthByPoints(endPoint,points[-2],magnet)
            self.addRow(tableWidget,rowCount,str(second_number),str(endNumberPoint),length,int(angle),round(minutes),azimuth)
        else:
            if rowCount==countPoints:
                self.addRow(tableWidget,rowCount-1,firstNumber,second_number,length,int(angle),round(minutes),azimuth)
                length,angle,minutes = self.calcAngleLengthByPoints(endPoint,points[0],magnet)
                #minutes = round(minutes)  
                tableWidget.item(rowCount,0).setText(str(second_number)+"-"+str(endNumberPoint))
                tableWidget.item(rowCount,2).setText(str(length))
                ###print "addRows"
                ###print angle,minutes,self.azimuthToRumb(float(int(angle)),float(round(minutes)))
                if(azimuth):
                    tableWidget.item(rowCount,3).setText(str(int(angle))+u'°'+str(int(round(minutes)))+u'\'')
                else:
                    tableWidget.item(rowCount,3).setText(self.azimuthToRumb(float(int(angle)),float(round(minutes))))
            else:
                self.addRow(tableWidget,rowCount,firstNumber,second_number,length,int(angle),round(minutes),azimuth)
        ####print "etkonec"
    #Добавления строки в таблицу
    def addRow(self,tableWidget,row,first_number,second_number,length,angle,minutes=0.0,azimuth=True):
        tableWidget.blockSignals(True)
        checkBoxItem = QTableWidgetItem()
        checkBoxItem.setCheckState(Qt.Unchecked)
        tableWidget.insertRow(row)
        tableWidget.setItem(row,0,QTableWidgetItem(first_number+"-"+second_number))
        #tableWidget.setCellWidget(row,1,QCheckBox())
        tableWidget.setItem(row,1,checkBoxItem)
        #tableWidget.item(row,1).setCheckState(Qt.Unchecked)
        tableWidget.setItem(row,2,QTableWidgetItem(str(length)))
        ###print "addrow",azimuth
        if(azimuth):
            tableWidget.setItem(row,3,QTableWidgetItem(str(int(angle))+u'°'+str(int(minutes))+u'\''))
        else:
            tableWidget.setItem(row,3,QTableWidgetItem(self.azimuthToRumb(float(angle),float(minutes))))
        tableWidget.blockSignals(False)



#Классы, которые наследуют QUndoCommand, созданы для того, чтобы можно было создать стэк операций, тем самым реализуюя такой функционал как назад ("Ctrl+z") вперед(обычно это "Ctrl+y", но qgis не дал использовать это сочетание, поэтому "F4")
#redo это метод, который можно перегрузить тем самым объяснить, стэку, что делать когда эта операция добавляется в стэк или к ней переходят при помощи F4
#undo это метод, который можно перегрузить тем самым объяснить, стэку, что делать когда команду отменяют ("ctrl+z")

#Класс удаления точки или точек        
class CommandDeletePoint(QUndoCommand,WorkWithTableAndPoints):
    def __init__(self,description,tableWidget,points,rubberBand,startPoint,endPoint,trigger,magnet,draw,azimuth=True,guid="",db=None,dockwidget=None):
        super(CommandDeletePoint, self).__init__(description)
        self.tableWidget = tableWidget
        self.points = points
        self.rubberBand = rubberBand
        self.startPoint = startPoint
        self.endPoint = startPoint
        self.magnet = magnet
        self.trigger = trigger
        self.deletedPoints = collections.OrderedDict()
        self.lengthPoints = collections.OrderedDict()
        self.anglePoints = collections.OrderedDict()
        self.draw = draw
        self.linePoints = self.draw.getLinePoints()
        self.linePointIndexes = []
        self.tmpPoints = list(self.points)
        self.tmpLinePoints = list(self.linePoints)
        self.numberPoints = collections.OrderedDict()
        self.azimuth = azimuth
        self.guid = guid
        self.db = db
        self.dockwidget = dockwidget
        self.deltaLength = self.dockwidget.lineEdit_difference_distance.text()
        self.deltaAngle = self.dockwidget.lineEdit_difference_degrees.text()
    #Просто запоминаем, всю таблицу, чтобы при отмене, можно было вернуть все как было
    def redo(self):
        self.draw.resetDifference()
        for i in range(self.tableWidget.rowCount()):
            self.lengthPoints[i] = self.tableWidget.item(i,2).text()
            self.anglePoints[i] = self.tableWidget.item(i,3).text()
            self.numberPoints[i] = self.tableWidget.item(i,0).text()
        rows = set()
        select = self.tableWidget.selectionModel()
        if select.hasSelection():
            if len(select.selectedIndexes())>0:
                for item in select.selectedIndexes():
                    rows.add(item.row())
        rows = sorted(rows)
        #запомниаем точки, которые хотим удалить
        if len(self.deletedPoints.keys())==0:
            for i in rows:
                if len(self.linePoints)>0:
                    if(i-(len(self.linePoints)-1)<0):
                        self.deletedPoints[i]=self.linePoints[i+1]
                        self.linePointIndexes.append(i)
                    else:
                        self.deletedPoints[i]=self.points[i-(len(self.linePoints)-1)]
                else:
                    self.deletedPoints[i]=self.points[i]
                  
        ####print("deletedPoints diction",self.deletedPoints)     
        ####print("self.points",self.points)
        ##print "Rubber ",self.rubberBand.asGeometry().exportToWkt()
        tmpTestPoints = list(self.points)
        ##print "UPDATEPOINTSINDATABASE points", self.points
        tmpTestPoints.append(tmpTestPoints[0])
        polygon = QgsGeometry.fromPolygon([tmpTestPoints])
        #print "POLYGON,",polygon.exportToWkt()
        #теперь выделяем их по порядку
        for i in self.deletedPoints.keys():
            ####print i
            self.tableWidget.setItemSelected(self.tableWidget.item(i,0),True)
        ####print "deletedPoints: ", self.deletedPoints
        ####print "BEFORE commandDelete:",self.points
        
        #удаляем строки
        self.deleteRow(self.tableWidget,self.draw.getLinePoints(),self.points,self.startPoint,self.magnet,self.dockwidget.radioButton_azimuth.isChecked(),self.dockwidget.checkBox_nep.isChecked())
        #если количество удаленных точек больше чем 1, то пересчитываем всю таблицу полностью
        if(len(self.deletedPoints)>1):
            self.calculateAllPoints(self.tableWidget,self.draw.getLinePoints(),self.points,self.startPoint,0,self.magnet,self.magnet,True,self.dockwidget.radioButton_azimuth.isChecked())
        ####print "redo commandDelete:",self.points
        
        #Если этого выдела еще нет в базе, то отрисовываем на карте и ставим новую начальную точку, иначе просто обновляем таблицу
        if(not self.guid):
            self.drawPolygon(True)
            self.draw.drawBindingLine()
            self.draw.setPoint(self.points[-1])
        elif(not self.dockwidget.checkBox_nep.isChecked()):
            #print "Point before update",self.points
            self.updatePointsInDatabase(self.dockwidget,self.tableWidget,self.points,self.draw,self.db,self.guid,self.dockwidget.radioButton_azimuth.isChecked())
        else:
            self.updateNepPointsInDatabase(self.dockwidget,self.tableWidget,self.points,self.draw,self.db,self.guid,self.dockwidget.radioButton_azimuth.isChecked())
    #При отмене необходимо заблокировать сигналы (события) в таблице, чтобы при добавлении в таблицу значений, не сробатывали события
    def undo(self):
        self.tableWidget.blockSignals(True)
        #сначала удаляем существующие точки
        del self.linePoints[:]
        del self.points[:]
        #затем добавляем в листы старые точки
        for point in self.tmpLinePoints:
            self.linePoints.append(point)
        for point in self.tmpPoints:
            self.points.append(point)
        #создаем новые строки в таблице если они нужны
        while self.tableWidget.rowCount() < len(self.anglePoints):
            self.addRow(self.tableWidget,self.tableWidget.rowCount(),"0","0",0,0,0)
        #заполняем таблицу старыми значениями
        for i in range(self.tableWidget.rowCount()):
            self.tableWidget.item(i,1).setCheckState(Qt.Unchecked)
            self.tableWidget.item(i,2).setText(self.lengthPoints[i])
            angle = self.anglePoints[i]
            if(self.dockwidget.radioButton_azimuth.isChecked() and ' ' in angle):
                angle = self.rumbToAzimuth(angle)
            elif(not self.dockwidget.radioButton_azimuth.isChecked() and not ' ' in angle):
                tmpSplit = angle.split(u'°')
                minutes = float(tmpSplit[1].replace('\'',''))
                angle = float(tmpSplit[0])
                angle = self.azimuthToRumb(angle,minutes)
            ##print "DELETE UNDO:",angle
            self.tableWidget.item(i,3).setText(angle)
            self.tableWidget.item(i,0).setText(self.numberPoints[i])
        #если есть линия привязки, то отмечаем её    
        if(len(self.tmpLinePoints)>0):
            self.tableWidget.item(len(self.tmpLinePoints)-2,1).setCheckState(Qt.Checked)
        self.dockwidget.lineEdit_difference_distance.setText(self.deltaLength)
        self.dockwidget.lineEdit_difference_degrees.setText(self.deltaAngle)
        #self.recountPoints(self.tableWidget,0,len(self.linePoints)-1)
        self.tableWidget.blockSignals(False)
        
        if(not self.guid):
            self.drawPolygon(True)
            self.draw.drawBindingLine()
            self.draw.setPoint(self.points[-1])
        elif(not self.dockwidget.checkBox_nep.isChecked()):
            self.updatePointsInDatabase(self.dockwidget,self.tableWidget,self.points,self.draw,self.db,self.guid,self.dockwidget.radioButton_azimuth.isChecked())
        else:
            self.updateNepPointsInDatabase(self.dockwidget,self.tableWidget,self.points,self.draw,self.db,self.guid,self.dockwidget.radioButton_azimuth.isChecked())
    #обновляем таблицу, практически идентичен методу addInDatabase класса WorkWithTableAndPoints, больше инфы там
    # def updatePointsInDatabase(self):
        # self.linePoints = self.draw.getLinePoints()
        # if(self.guidPlot and self.db!=None):
            # srid = None
            # layerQuart = self.findLayerByPattern("\"public\".\"t_forestquarter\"")
            # layerPlot = self.findLayerByPattern("\"public\".\"t_plot\"")
            # srid = layerQuart.source().split(" ")[7].split("=")[1]
            # layerTax=self.findLayerByPattern("type=MultiPolygon table=\"public\".\"t_taxationisolated\"")
            # if(srid):
                # #если по каким то причинам, инфа о коннекте не была установлена, то устанавливаем и соединяемся
                # if(not self.db.openConnection()):
                    # self.db.setConnectionInfo()
                    # self.db.openConnection()
                
                # forestquarterGuid=""
                # for feature in layerPlot.getFeatures(QgsFeatureRequest(QgsExpression("primarykey='"+self.guidPlot+"'"))):
                    # forestquarterGuid = str(feature['forestquarter'])
                # self.db.executeQuery("delete from t_plot_point where plot_fk='"+self.guidPlot+"'")
                # self.db.executeQuery("delete from t_rumbs where plot='"+self.guidPlot+"'")
                # countLinePoints = len(self.linePoints)
                # bindingLine = QgsGeometry.fromPolyline(self.linePoints)
                # tmpPoints = list(self.points)
                # tmpPoints.append(tmpPoints[0])
                # polygon = QgsGeometry.fromPolygon([tmpPoints])
                
                # featureTaxes = []
                # for feature in layerTax.getFeatures(QgsFeatureRequest(QgsExpression("forestquarter='"+forestquarterGuid+"'"))):
                    # ####print "layerTax:",feature.geometry()
                    # if feature.geometry() !=None and feature.geometry().intersects(polygon):
                        # featureTaxes.append([str(feature['primarykey']),polygon.intersection(feature.geometry())])
                
                # self.db.executeQuery("delete from t_binding_line where plot='"+self.guidPlot+"'")
                # if(len(self.linePoints)>0):
                    # self.db.executeQuery("insert into t_binding_line(primarykey,shape,plot) values(uuid_generate_v4(),st_geomFromText('"+bindingLine.exportToWkt()+"',"+srid+"),'"+self.guidPlot+"')")
                # self.db.executeQuery("update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guidPlot+"'")
                # ###print "update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guidPlot+"'"
                # ###print len(self.linePoints)
                # pointValues=""
                # rumbValues = ""               
                # for i in range(self.tableWidget.rowCount()):
                    # number = self.tableWidget.item(i,0).text()
                    # length = self.tableWidget.item(i,2).text()
                    # angle = self.tableWidget.item(i,3).text()
                    # if(self.azimuth):
                        # tmpSplit = angle.split(u'°')
                        # minutes = float(tmpSplit[1].replace('\'',''))
                        # angle = float(tmpSplit[0])
                        # angle = self.azimuthToRumb(angle,minutes)
                    # angle = angle.replace('\'','`')
                    # ####print angle
                    # if(countLinePoints>0):
                        # if i<countLinePoints:
                            # pointValues=pointValues+"(uuid_generate_v4(),'"+self.guidPlot+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(self.linePoints[i]).exportToWkt()+"',"+srid+"),'5b8e90b5-df13-46b6-bf55-59146110dc28'),"
                            # if(i<countLinePoints-1):
                                # rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','5b8e90b5-df13-46b6-bf55-59146110dc28','"+self.guidPlot+"'),"
                        # if i-(countLinePoints-1)>=0:
                            # pointValues=pointValues+"(uuid_generate_v4(),'"+self.guidPlot+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i-(countLinePoints-1)]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504'),"
                            # rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guidPlot+"'),"
                    # else:
                        # rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guidPlot+"'),"
                        # pointValues=pointValues+"(uuid_generate_v4(),'"+self.guidPlot+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504'),"
                        # ####print pointValues
                        # ####print rumbValues
                # pointValues=pointValues[:-1:]
                # rumbValues = rumbValues[:-1:]
                # ####print "insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues
                # ####print rumbValues
                # self.db.executeQuery("insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues)
                # self.db.executeQuery("INSERT INTO t_rumbs(primarykey, \"number\", distance, rumb, type, plot) values "+rumbValues)
                
                # self.db.executeQuery("delete from t_isolatedplots where plot = '"+self.guidPlot+"'")
                # isolatedValues = ""
                # for item in featureTaxes:
                    # isolatedValues =isolatedValues+("(uuid_generate_v4(),'"+item[0]+"','"+self.guidPlot+"',st_geomFromText('"+item[1].exportToWkt()+"',"+srid+"),'1'),")
                # isolatedValues=isolatedValues[:-1:]
                # self.db.executeQuery("insert into t_isolatedplots(primarykey,isolated,plot,shape,actual) values "+isolatedValues)
                # self.dockwidget.lineEdit_areaPlot.setText(str(round(polygon.area()/10000,1)))
                
                # self.db.closeConnection()
            # else:
                # QMessageBox.information(None,u"Квартал",u"Добавьте слой t_forestquarter для изменения делянки.")
        
    
    def drawPolygon(self,end):
        if(end!=True):
            self.points.append(self.startPoint)
        self.showRect(self.points,self.endPoint)
    
    def showRect(self,points,endPoint):
        self.rubberBand.reset(QGis.Polygon)
        for point in self.points:
            self.rubberBand.addPoint(point,False)
        if(endPoint!=None):
            self.rubberBand.addPoint(endPoint,True)
        self.rubberBand.show()
    
#!!!!!        
#Обновление точки    
class CommandUpdatePoint(QUndoCommand,WorkWithTableAndPoints):
    def __init__(self,description,tableWidget,row,column,cellText,oldValue,points,rubberBand,startPoint,endPoint,magnet,draw,azimuth=True,guid="",db=None,dockwidget=None):
        super(CommandUpdatePoint, self).__init__(description)
        self.tableWidget = tableWidget
        self.row = row
        self.points = points
        self.row = row
        self.column = column
        self.oldValue = oldValue
        self.cellText = cellText
        self.startPoint = startPoint
        self.draw = draw
        self.endPoint = endPoint
        self.magnet = magnet
        self.rubberBand = rubberBand
        self.azimuth=azimuth
        self.guid = guid
        self.db = db
        self.dockwidget = dockwidget
        self.lastRowLength = None
        self.lastRowAngle = None
        if(self.tableWidget.rowCount()>2):
            self.lastRowLength = self.tableWidget.item(self.tableWidget.rowCount()-1,2).text()
            self.lastRowAngle = self.tableWidget.item(self.tableWidget.rowCount()-1,3).text()
    
    def redo(self):
        ####print "redo","update",self.oldValue
        ####print "redo1",self.startPoint
        ####print self.draw.getRubberBand().numberOfVertices()
        self.draw.resetDifference()
        self.tableWidget.item(self.row,self.column).setText(self.cellText)
        ##print "commandUpdate:",self.cellText
        ###print "commandUPdate",self.azimuth
        self.calculateAllPoints(self.tableWidget,self.draw.getLinePoints(),self.points,self.startPoint,self.row,self.magnet,self.magnet,True,self.dockwidget.radioButton_azimuth.isChecked())
        ##print "commandUpdate:",self.tableWidget.item(self.row,self.column).text()
        ####print "redo1",self.startPoint
        ####print "redo update:",self.points
        ####print self.draw.getRubberBand().numberOfVertices()
        ##print "guidPLot",self.guidPlot
        if(not self.guid):
            self.drawPolygon(True) 
            if self.draw.getEmitingPoint():
                self.draw.setPoint(self.points[-1])
            self.draw.drawBindingLine()
        else:
            if(float(self.tableWidget.item(self.row,2).text())>0):
                if not self.dockwidget.checkBox_nep.isChecked():
                    self.updatePointsInDatabase(self.dockwidget,self.tableWidget,self.points,self.draw,self.db,self.guid,self.dockwidget.radioButton_azimuth.isChecked())
                else:
                    self.updateNepPointsInDatabase(self.dockwidget,self.tableWidget,self.points,self.draw,self.db,self.guid,self.dockwidget.radioButton_azimuth.isChecked())
        ####print "redo update:",self.points
        
    
    def undo(self):
        ####print "undo","update",self.oldValue
        self.tableWidget.item(self.row,self.column).setText(self.oldValue)
        self.calculateAllPoints(self.tableWidget,self.draw.getLinePoints(),self.points,self.startPoint,self.row,self.magnet,self.magnet,True,self.dockwidget.radioButton_azimuth.isChecked())
        if(self.tableWidget.rowCount()>2): 
            if not self.dockwidget.radioButton_azimuth.isChecked() and ' ' not in self.lastRowAngle:
                tmpAngle,tmpMinutes = self.lastRowAngle.replace(u'\'','').split(u'°')
                self.lastRowAngle = self.azimuthToRumb(float(tmpAngle),float(tmpMinutes))
            elif self.dockwidget.radioButton_azimuth.isChecked() and ' ' in self.lastRowAngle:
                self.lastRowAngle = self.rumbToAzimuth(self.lastRowAngle)
            self.tableWidget.item(self.tableWidget.rowCount()-1,2).setText(str(self.lastRowLength))
            self.tableWidget.item(self.tableWidget.rowCount()-1,3).setText(str(self.lastRowAngle))
            deltaLength,deltaAngle,deltaMinutes = self.getDifferenceBetween(self.points[-1],self.points[0],self.magnet,self.tableWidget,self.dockwidget.radioButton_azimuth.isChecked())
        else:
            deltaLength=0.0
            deltaAngle = 0
            deltaMinutes = 0
        ###print "UNDO COMMAND ADD:",deltaLength,deltaAngle,deltaMinutes
        self.dockwidget.lineEdit_difference_distance.setText(str(deltaLength))
        self.dockwidget.lineEdit_difference_degrees.setText(str(deltaAngle)+u'°'+str(deltaMinutes)+u'\'')
        
        if(not self.guid):
            self.drawPolygon(True) 
            #self.startPoint = self.points[-1]
            if self.draw.getEmitingPoint():
                self.draw.setPoint(self.points[-1])
        else:
            #Если длина больше 0, то обновляем таблицу
            if not self.dockwidget.checkBox_nep.isChecked():
                self.updatePointsInDatabase(self.dockwidget,self.tableWidget,self.points,self.draw,self.db,self.guid,self.dockwidget.radioButton_azimuth.isChecked())
            else:
                self.updateNepPointsInDatabase(self.dockwidget,self.tableWidget,self.points,self.draw,self.db,self.guid,self.dockwidget.radioButton_azimuth.isChecked())
    #обновляем таблицу, практически идентичен методу addInDatabase класса WorkWithTableAndPoints, больше инфы там    
    # def updatePointsInDatabase(self):
        # self.linePoints = self.draw.getLinePoints()
        # if(self.guidPlot and self.db!=None):
            # srid = None
            # layerQuart = self.findLayerByPattern("\"public\".\"t_forestquarter\"")
            # layerPlot = self.findLayerByPattern("\"public\".\"t_plot\"")
            # srid = layerQuart.source().split(" ")[7].split("=")[1]
            # layerTax=self.findLayerByPattern("type=MultiPolygon table=\"public\".\"t_taxationisolated\"")
            # if(srid):
                # if(not self.db.openConnection()):
                    # self.db.setConnectionInfo()
                    # self.db.openConnection()
                
                # forestquarterGuid=""
                # for feature in layerPlot.getFeatures(QgsFeatureRequest(QgsExpression("primarykey='"+self.guidPlot+"'"))):
                    # forestquarterGuid = str(feature['forestquarter'])
                # self.db.executeQuery("delete from t_plot_point where plot_fk='"+self.guidPlot+"'")
                # self.db.executeQuery("delete from t_rumbs where plot='"+self.guidPlot+"'")
                # countLinePoints = len(self.linePoints)
                # bindingLine = QgsGeometry.fromPolyline(self.linePoints)
                # tmpPoints = list(self.points)
                # tmpPoints.append(tmpPoints[0])
                # polygon = QgsGeometry.fromPolygon([tmpPoints])
                
                # featureTaxes = []
                # for feature in layerTax.getFeatures(QgsFeatureRequest(QgsExpression("forestquarter='"+forestquarterGuid+"'"))):
                    # ####print "layerTax:",feature.geometry()
                    # if feature.geometry() !=None and feature.geometry().intersects(polygon):
                        # featureTaxes.append([str(feature['primarykey']),polygon.intersection(feature.geometry())])
                
                # self.db.executeQuery("delete from t_binding_line where plot='"+self.guidPlot+"'")
                # if(len(self.linePoints)>0):
                    # self.db.executeQuery("insert into t_binding_line(primarykey,shape,plot) values(uuid_generate_v4(),st_geomFromText('"+bindingLine.exportToWkt()+"',"+srid+"),'"+self.guidPlot+"')")
                # self.db.executeQuery("update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guidPlot+"'")
                # ###print "update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guidPlot+"'"
                # ###print len(self.linePoints)
                # pointValues=""
                # rumbValues = ""               
                # for i in range(self.tableWidget.rowCount()):
                    # number = self.tableWidget.item(i,0).text()
                    # length = self.tableWidget.item(i,2).text()
                    # angle = self.tableWidget.item(i,3).text()
                    # if(self.azimuth):
                        # tmpSplit = angle.split(u'°')
                        # minutes = float(tmpSplit[1].replace('\'',''))
                        # angle = float(tmpSplit[0])
                        # angle = self.azimuthToRumb(angle,minutes)
                    # angle = angle.replace('\'','`')
                    # ####print angle
                    # if(countLinePoints>0):
                        # if i<countLinePoints:
                            # pointValues=pointValues+"(uuid_generate_v4(),'"+self.guidPlot+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(self.linePoints[i]).exportToWkt()+"',"+srid+"),'5b8e90b5-df13-46b6-bf55-59146110dc28'),"
                            # if(i<countLinePoints-1):
                                # rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','5b8e90b5-df13-46b6-bf55-59146110dc28','"+self.guidPlot+"'),"
                        # if i-(countLinePoints-1)>=0:
                            # pointValues=pointValues+"(uuid_generate_v4(),'"+self.guidPlot+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i-(countLinePoints-1)]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504'),"
                            # rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guidPlot+"'),"
                    # else:
                        # rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guidPlot+"'),"
                        # pointValues=pointValues+"(uuid_generate_v4(),'"+self.guidPlot+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504'),"
                        # ####print pointValues
                        # ####print rumbValues
                # pointValues=pointValues[:-1:]
                # rumbValues = rumbValues[:-1:]
                # ####print "insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues
                # ####print rumbValues
                # self.db.executeQuery("insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues)
                # self.db.executeQuery("INSERT INTO t_rumbs(primarykey, \"number\", distance, rumb, type, plot) values "+rumbValues)
                
                # self.db.executeQuery("delete from t_isolatedplots where plot = '"+self.guidPlot+"'")
                # isolatedValues = ""
                # for item in featureTaxes:
                    # isolatedValues =isolatedValues+("(uuid_generate_v4(),'"+item[0]+"','"+self.guidPlot+"',st_geomFromText('"+item[1].exportToWkt()+"',"+srid+"),'1'),")
                # isolatedValues=isolatedValues[:-1:]
                # self.db.executeQuery("insert into t_isolatedplots(primarykey,isolated,plot,shape,actual) values "+isolatedValues)
                # self.dockwidget.lineEdit_areaPlot.setText(str(round(polygon.area()/10000,1)))
                
                # self.db.closeConnection()
            # else:
                # QMessageBox.information(None,u"Квартал",u"Добавьте слой t_forestquarter для изменения делянки.")
    
    
    def drawPolygon(self,end):
        if(end!=True):
            self.points.append(self.startPoint)
        self.showRect(self.points,self.endPoint)
    
    def showRect(self,points,endPoint):
        self.rubberBand.reset(QGis.Polygon)
        for point in self.points:
            self.rubberBand.addPoint(point,False)
        if(endPoint!=None):
            self.rubberBand.addPoint(endPoint,True)
        self.rubberBand.show()
#!!!!!!!
class CommandUpdateLastPoint(QUndoCommand,WorkWithTableAndPoints):
    def __init__(self,description,dockwidget,row,column,cellText,startEndPoints,magnet,db=None,guid=None):
        super(CommandUpdateLastPoint, self).__init__(description)
        self.dockwidget = dockwidget
        self.row = row
        self.column = column
        self.cellText = cellText
        self.oldText = None
        self.db = db
        self.guid = guid
        
        seg = QgsFeature()
        seg.setGeometry(QgsGeometry.fromPolyline(startEndPoints))
        angle = QgsPoint.azimuth(startEndPoints[0],startEndPoints[1])-magnet
        if(angle<0):
            angle = 360+angle
        if angle>=360:
            angle=angle-360
        minutes = round(((angle % 1)*60)) 
        
        self.trueLength = round(seg.geometry().length(),1)
        self.trueAngle = int(angle)
        self.trueMinutes = int(minutes)

    def redo(self):
        self.oldText = self.dockwidget.tableWidget_points.item(self.row,self.column).text()
        ##print "commandUpdateLastPoint:",self.row,self.column,self.cellText
        if self.column == 2:
            tableLength = float(self.cellText)
            deltaLength = abs(tableLength-self.trueLength)
            # ##print "DeltaLength:",deltaLength
            # ##print "tableLength:",deltaLength
            # ##print "trueLength:",deltaLength
            self.dockwidget.lineEdit_difference_distance.setText(str(deltaLength))
            self.dockwidget.tableWidget_points.item(self.row,self.column).setText(str(tableLength))
        elif self.column == 3:
            tableAngle,tableMinutes = self.cellText.split('.')
            if len(tableMinutes)==1:
                tableMinutes+='0'
            tableAngle = int(tableAngle)
            tableMinutes = int(tableMinutes)
            deltaAngle = abs(self.trueAngle-tableAngle)
            deltaMinutes = abs(self.trueMinutes-tableMinutes)
            tmp =  self.cellText.split('.')
            newCellText = ""
            if len(tmp)>1:
                if len(tmp[1])==1 and tmp[1][0]!='0':
                    tmp[1]=tmp[1]+'0'
                newCellText = tmp[0]+u'°'+tmp[1]+'\''
            else:
                newCellText = tmp[0]+u'°'+"0\'"
            self.dockwidget.tableWidget_points.item(self.row,self.column).setText(newCellText)
            self.dockwidget.lineEdit_difference_degrees.setText(str(deltaAngle)+u'°'+str(deltaMinutes)+u'\'')  
        self.updateLastPoint()
        
    def undo(self):
        if self.column == 2:
            tableLength = float(self.oldText)
            deltaLength = abs(self.trueLength - tableLength)
            self.dockwidget.lineEdit_difference_distance.setText(str(deltaLength))
            self.dockwidget.tableWidget_points.item(self.row,self.column).setText(self.oldText)
        elif self.column==3:
            tableAngle,tableMinutes = self.oldText.replace(u'\'','').split(u'°')
            if len(tableMinutes)==1:
                tableMinutes+='0'
            deltaAngle = abs(self.trueAngle-int(tableAngle))
            deltaMinutes = abs(self.trueMinutes-int(tableMinutes))
            self.dockwidget.tableWidget_points.item(self.row,self.column).setText(self.oldText)
            self.dockwidget.lineEdit_difference_degrees.setText(str(deltaAngle)+u'°'+str(deltaMinutes)+u'\'')  
        self.updateLastPoint()
        
    def updateLastPoint(self):
        if(self.guid and self.db!=None):
            if not self.db.openConnection():
                self.db.setConnectionInfo()
                self.db.openConnection
            number = self.dockwidget.tableWidget_points.item(self.row,0).text()
            length = self.dockwidget.tableWidget_points.item(self.row,2).text()
            angle = self.dockwidget.tableWidget_points.item(self.row,3).text()
            if self.dockwidget.radioButton_azimuth.isChecked():
                angle,minutes = angle.replace(u'\'','').split(u'°')
                angle = self.azimuthToRumb(float(angle),float(minutes))
                angle = angle.replace('\'','`')
            #print "UPDATELASTPOINT"
            if self.dockwidget.checkBox_nep.isChecked():
                number = number.replace('\'','`')
                self.db.executeQuery("update t_noa_rumbs set rumb='"+angle+"', distance="+length+" where number='"+number+"' and noa = '"+self.guid+"'")
            else:
                self.db.executeQuery("update t_rumbs set rumb='"+angle+"', distance="+length+" where number='"+number+"' and plot='"+self.guid+"'")
            self.db.closeConnection()
        
    
#Удаление привязки
class CommandDeleteBindingLine(QUndoCommand,WorkWithTableAndPoints):
    def __init__(self,description,tableWidget,row,bindingLineRow,magnet,draw,azimuth=True,guid="",db=None,dockwidget=None):
        super(CommandDeleteBindingLine, self).__init__(description)
        self.tableWidget = tableWidget
        self.draw = draw
        self.magnet = magnet
        self.points = self.draw.getPoints()
        self.row = row
        self.bindingLineRow = bindingLineRow
        self.azimuth = azimuth
        self.guid = guid
        self.db = db
        self.dockwidget = dockwidget
        self.lastRowLength = self.tableWidget.item(self.tableWidget.rowCount()-1,2).text()
        self.lastRowAngle = self.tableWidget.item(self.tableWidget.rowCount()-1,3).text()
    def undo(self):

        
        self.addBindingLine(self.row)
        
        if(self.tableWidget.rowCount()>2): 
            if not self.dockwidget.radioButton_azimuth.isChecked() and ' ' not in self.lastRowAngle:
                tmpAngle,tmpMinutes = self.lastRowAngle.replace(u'\'','').split(u'°')
                self.lastRowAngle = self.azimuthToRumb(float(tmpAngle),float(tmpMinutes))
            elif self.dockwidget.radioButton_azimuth.isChecked() and ' ' in self.lastRowAngle:
                self.lastRowAngle = self.rumbToAzimuth(self.lastRowAngle)
            self.tableWidget.item(self.tableWidget.rowCount()-1,2).setText(str(self.lastRowLength))
            self.tableWidget.item(self.tableWidget.rowCount()-1,3).setText(str(self.lastRowAngle))
            deltaLength,deltaAngle,deltaMinutes = self.getDifferenceBetween(self.points[-1],self.points[0],self.magnet,self.tableWidget,self.dockwidget.radioButton_azimuth.isChecked())
        else:
            deltaLength=0.0
            deltaAngle = 0
            deltaMinutes = 0
        ###print "UNDO COMMAND ADD:",deltaLength,deltaAngle,deltaMinutes
        self.dockwidget.lineEdit_difference_distance.setText(str(deltaLength))
        self.dockwidget.lineEdit_difference_degrees.setText(str(deltaAngle)+u'°'+str(deltaMinutes)+u'\'')
        
        self.tableWidget.blockSignals(True)
        self.tableWidget.item(self.row,1).setCheckState(Qt.Checked)
        self.tableWidget.item(self.tableWidget.rowCount()-1,2).setText(self.lastRowLength)
        self.tableWidget.item(self.tableWidget.rowCount()-1,3).setText(self.lastRowAngle)
        self.tableWidget.blockSignals(False)
        if self.dockwidget.checkBox_nep.isChecked():
            self.updateNepBindingDatabase()
        else:
            self.updateBindingDatabase()
        
    
    def redo(self):
        self.draw.resetDifference()
        self.deleteBindingLine(self.row)
        if self.dockwidget.checkBox_nep.isChecked():
            self.updateNepBindingDatabase()
        else:
            self.updateBindingDatabase()
    
    
    def updateNepBindingDatabase(self):
        self.linePoints = self.draw.getLinePoints()
        if(self.guid and self.db!=None):
            srid = None
            layerNep = self.findLayerByPattern("\"public\".\"t_non_operational_area\"")
            layerPlot = self.findLayerByPattern("\"public\".\"t_plot\"")
            srid = layerPlot.source().split(" ")[7].split("=")[1]
            if(srid):
                if(not self.db.openConnection()):
                    self.db.setConnectionInfo()
                    self.db.openConnection()
                
                plotGuid=""
                for feature in layerNep.getFeatures(QgsFeatureRequest(QgsExpression("primarykey='"+self.guid+"'"))):
                    plotGuid = str(feature['plot'])
                self.db.executeQuery("alter table t_non_operational_area disable trigger all")
                self.db.executeQuery("alter table t_noa_binding_line disable trigger all")
                self.db.executeQuery("delete from t_noa_point where noa='"+self.guid+"'")
                self.db.executeQuery("delete from t_noa_rumbs where noa='"+self.guid+"'")
                countLinePoints = len(self.linePoints)
                bindingLine = QgsGeometry.fromPolyline(self.linePoints)
                tmpPoints = list(self.points)
                #tmpPoints.append(tmpPoints[0])
                polygon = QgsGeometry.fromPolygon([tmpPoints])
                
                self.db.executeQuery("delete from t_noa_binding_line where noa='"+self.guid+"'")
                if(len(self.linePoints)>0):
                    self.db.executeQuery("insert into t_noa_binding_line(primarykey,shape,noa) values(uuid_generate_v4(),st_geomFromText('"+bindingLine.exportToWkt()+"',"+srid+"),'"+self.guid+"')")
                self.db.executeQuery("update t_non_operational_area set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+"),area="+str(round(polygon.area()/10000,1))+" where primarykey='"+self.guid+"'")
                self.db.executeQuery("update t_plot set area=area_common-(select sum(area) from t_non_operational_area where plot = '"+plotGuid+"') where primarykey = '"+plotGuid+"'")
                ###print "update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guid+"'"
                ###print len(self.linePoints)
                pointValues=""
                rumbValues = ""               
                for i in range(self.tableWidget.rowCount()):
                    number = self.tableWidget.item(i,0).text().replace('\'','`')
                    length = self.tableWidget.item(i,2).text()
                    angle = self.tableWidget.item(i,3).text()
                    pointNumber=number.split('-')[0]
                    if(self.azimuth):
                        tmpSplit = angle.split(u'°')
                        minutes = float(tmpSplit[1].replace('\'',''))
                        angle = float(tmpSplit[0])
                        angle = self.azimuthToRumb(angle,minutes)
                    angle = angle.replace('\'','`')
                    ####print angle
                    if(countLinePoints>0):
                        if i<countLinePoints:
                            pointValues=pointValues+"(uuid_generate_v4(),'"+self.guid+"','"+pointNumber+"',st_geomFromText('"+QgsGeometry.fromPoint(self.linePoints[i]).exportToWkt()+"',"+srid+"),'5b8e90b5-df13-46b6-bf55-59146110dc28',"+str(i)+"),"
                            if(i<countLinePoints-1):
                                rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','5b8e90b5-df13-46b6-bf55-59146110dc28','"+self.guid+"'),"
                        if i-(countLinePoints-1)>=0:
                            pointValues=pointValues+"(uuid_generate_v4(),'"+self.guid+"','"+pointNumber+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i-(countLinePoints-1)]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504',"+str(i)+"),"
                            rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guid+"'),"
                    else:
                        rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guid+"'),"
                        #print "delete for i=",i
                        pointValues=pointValues+"(uuid_generate_v4(),'"+self.guid+"','"+pointNumber+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504',"+str(i)+"),"
                        ####print pointValues
                        ####print rumbValues
                pointValues=pointValues[:-1:]
                rumbValues = rumbValues[:-1:]
                ####print "insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues
                ####print rumbValues
                self.db.executeQuery("insert into t_noa_point(primarykey,noa,\"number\",shape,type_object,\"order\") values "+pointValues)
                self.db.executeQuery("INSERT INTO t_noa_rumbs(primarykey, \"number\", distance, rumb, type, noa) values "+rumbValues)
                self.db.executeQuery("alter table t_non_operational_area enable trigger all")
                self.db.executeQuery("alter table t_noa_binding_line enable trigger all")
                
                self.dockwidget.lineEdit_areaPlot.setText(str(round(polygon.area()/10000,1)))
                
                self.db.closeConnection()
            else:
                QMessageBox.information(None,u"Делянка",u"Добавьте слой t_plot для изменения НЭП.")
    
    
    #обновляем таблицу, практически идентичен методу addInDatabase класса WorkWithTableAndPoints, больше инфы там
    def updateBindingDatabase(self):
        self.linePoints = self.draw.getLinePoints()
        if(self.guid and self.db!=None):
            srid = None
            layerQuart = self.findLayerByPattern("\"public\".\"t_forestquarter\"")
            layerPlot = self.findLayerByPattern("\"public\".\"t_plot\"")
            srid = layerQuart.source().split(" ")[7].split("=")[1]
            layerTax=self.findLayerByPattern("table=\"public\".\"t_taxationisolated\"","type=MultiPolygon")
            if(srid):
                if(not self.db.openConnection()):
                    self.db.setConnectionInfo()
                    self.db.openConnection()
                
                forestquarterGuid=""
                for feature in layerPlot.getFeatures(QgsFeatureRequest(QgsExpression("primarykey='"+self.guid+"'"))):
                    forestquarterGuid = str(feature['forestquarter'])
                self.db.executeQuery("delete from t_plot_point where plot_fk='"+self.guid+"'")
                self.db.executeQuery("delete from t_rumbs where plot='"+self.guid+"'")
                countLinePoints = len(self.linePoints)
                bindingLine = QgsGeometry.fromPolyline(self.linePoints)
                tmpPoints = list(self.points)
                #tmpPoints.append(tmpPoints[0])
                polygon = QgsGeometry.fromPolygon([tmpPoints])
                
                featureTaxes = []
                for feature in layerTax.getFeatures(QgsFeatureRequest(QgsExpression("forestquarter='"+forestquarterGuid+"'"))):
                    ####print "layerTax:",feature.geometry()
                    if feature.geometry() !=None and feature.geometry().intersects(polygon):
                        featureTaxes.append([str(feature['primarykey']),polygon.intersection(feature.geometry())])
                
                self.db.executeQuery("delete from t_binding_line where plot='"+self.guid+"'")
                if(len(self.linePoints)>0):
                    self.db.executeQuery("insert into t_binding_line(primarykey,shape,plot) values(uuid_generate_v4(),st_geomFromText('"+bindingLine.exportToWkt()+"',"+srid+"),'"+self.guid+"')")
                self.db.executeQuery("update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guid+"'")
                ###print "update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guid+"'"
                ###print len(self.linePoints)
                pointValues=""
                rumbValues = ""               
                for i in range(self.tableWidget.rowCount()):
                    number = self.tableWidget.item(i,0).text()
                    length = self.tableWidget.item(i,2).text()
                    angle = self.tableWidget.item(i,3).text()
                    if(self.dockwidget.radioButton_azimuth.isChecked()):
                        tmpSplit = angle.split(u'°')
                        minutes = float(tmpSplit[1].replace('\'',''))
                        angle = float(tmpSplit[0])
                        angle = self.azimuthToRumb(angle,minutes)
                    angle = angle.replace('\'','`')
                    ####print angle
                    if(countLinePoints>0):
                        if i<countLinePoints:
                            pointValues=pointValues+"(uuid_generate_v4(),'"+self.guid+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(self.linePoints[i]).exportToWkt()+"',"+srid+"),'5b8e90b5-df13-46b6-bf55-59146110dc28'),"
                            if(i<countLinePoints-1):
                                rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','5b8e90b5-df13-46b6-bf55-59146110dc28','"+self.guid+"'),"
                        if i-(countLinePoints-1)>=0:
                            pointValues=pointValues+"(uuid_generate_v4(),'"+self.guid+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i-(countLinePoints-1)]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504'),"
                            rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guid+"'),"
                    else:
                        rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guid+"'),"
                        pointValues=pointValues+"(uuid_generate_v4(),'"+self.guid+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504'),"
                        ####print pointValues
                        ####print rumbValues
                pointValues=pointValues[:-1:]
                rumbValues = rumbValues[:-1:]
                ####print "insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues
                ####print rumbValues
                self.db.executeQuery("insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues)
                self.db.executeQuery("INSERT INTO t_rumbs(primarykey, \"number\", distance, rumb, type, plot) values "+rumbValues)
                
                self.db.executeQuery("delete from t_isolatedplots where plot = '"+self.guid+"'")
                isolatedValues = ""
                for item in featureTaxes:
                    isolatedValues =isolatedValues+("(uuid_generate_v4(),'"+item[0]+"','"+self.guid+"',st_geomFromText('"+item[1].exportToWkt()+"',"+srid+"),'1'),")
                isolatedValues=isolatedValues[:-1:]
                self.db.executeQuery("insert into t_isolatedplots(primarykey,isolated,plot,shape,actual) values "+isolatedValues)
                self.dockwidget.lineEdit_areaPlot.setText(str(round(polygon.area()/10000,1)))
                
                self.db.closeConnection()
            else:
                QMessageBox.information(None,u"Квартал",u"Добавьте слой t_forestquarter для изменения делянки.")
    
        
    def deleteBindingLine(self,row):
        linePoints = self.draw.getLinePoints()
        ####print "before delete points",self.draw.getPoints()
        ####print "deletePoints binding", linePoints
        for i in range(len(linePoints)-1):
            ####print i
            self.draw.getPoints().insert(i,linePoints[i])
        del linePoints[:]
        ####print "after delete points2",self.draw.getPoints()
        if(not self.guid):
            self.draw.drawPolygon(True)
            self.draw.drawBindingLine()
        points = self.draw.getPoints()
        rowCount = self.tableWidget.rowCount()-1
        countPoints = len(points)
        length,angle,minutes = self.calcAngleLengthByPoints(points[-1],points[0],self.magnet)
        endPointNumber = self.tableWidget.item(0,0).text().split('-')[0]
        startPointNumber = self.tableWidget.item(rowCount,0).text().split('-')[0]
        self.tableWidget.item(rowCount,0).setText(startPointNumber+"-"+endPointNumber)
        self.tableWidget.item(rowCount,2).setText(str(length))
        if(self.dockwidget.radioButton_azimuth.isChecked()):
            self.tableWidget.item(rowCount,3).setText(str(int(angle))+u'°'+str(int(minutes))+u'\'')
        else:
            self.tableWidget.item(rowCount,3).setText(self.azimuthToRumb(float(angle),float(minutes)))
    def addBindingLine(self,row):
        points = self.draw.getPoints()
        for i in range(row+2):
            ####print "tut",i
            self.draw.linePointAppend(points[i])
        ####print "before addbindingline points",self.draw.getPoints()
        del points[:row+1]
        ####print "after addbindingline points",self.draw.getPoints()
        if(not self.guid):
            self.draw.drawPolygon(True)
            self.draw.drawBindingLine()
        rowCount = self.tableWidget.rowCount()-1
        countLinePoints = len(self.draw.getLinePoints())
        countPoints = len(points)+countLinePoints-1
        length,angle,minutes = self.calcAngleLengthByPoints(points[-1],points[0],self.magnet)
        endPointNumber = self.tableWidget.item(row,0).text().split('-')[1]
        startPointNumber = self.tableWidget.item(rowCount,0).text().split('-')[0]
        self.tableWidget.item(rowCount,0).setText(startPointNumber+"-"+endPointNumber)
        self.tableWidget.item(rowCount,2).setText(str(length))
        if(self.dockwidget.radioButton_azimuth.isChecked()):
            self.tableWidget.item(rowCount,3).setText(str(int(angle))+u'°'+str(int(minutes))+u'\'')
        else:
            self.tableWidget.item(rowCount,3).setText(self.azimuthToRumb(float(angle),float(minutes)))

#!!!!!!
#Добавление привязки        
class CommandAddBindingLine(QUndoCommand,WorkWithTableAndPoints):
    def __init__(self,description,tableWidget,row,magnet,draw,azimuth=True,guid="",db=None,dockwidget=None):
        super(CommandAddBindingLine, self).__init__(description)
        self.tableWidget = tableWidget
        self.draw = draw
        self.magnet = magnet
        self.points = self.draw.getPoints()
        self.row = row
        self.oldRow = -1
        self.linePoints = draw.getLinePoints()
        self.countLinePoints = len(self.linePoints)
        self.azimuth = azimuth
        self.guid = guid
        self.db = db
        self.dockwidget = dockwidget
        self.lastRowLength = self.tableWidget.item(self.tableWidget.rowCount()-1,2).text()
        self.lastRowAngle = self.tableWidget.item(self.tableWidget.rowCount()-1,3).text()
        
    def redo(self):
        self.draw.resetDifference()
        #print "len_linePoints:",len(self.linePoints)
        if(len(self.linePoints)==0):
            self.oldRow = self.row
            self.tableWidget.blockSignals(True)
            self.tableWidget.item(self.row,1).setCheckState(Qt.Checked)
            self.tableWidget.blockSignals(False)
        else:
            self.oldRow=self.countLinePoints-2
            self.tableWidget.blockSignals(True)
            self.tableWidget.item(self.countLinePoints-2,1).setCheckState(Qt.Unchecked)
            self.deleteBindingLine(self.countLinePoints)
            self.tableWidget.blockSignals(False)
        self.addBindingLine(self.row)
        ###print "guidPlot",self.guidPlot
        ###print "linePoints",self.linePoints
        ###print "points",self.points
        if self.dockwidget.checkBox_nep.isChecked():
            self.updateNepBindingDatabase()
        else:
            self.updateBindingDatabase()
        
    def updateNepBindingDatabase(self):
        self.linePoints = self.draw.getLinePoints()
        if(self.guid and self.db!=None):
            srid = None
            layerNep = self.findLayerByPattern("\"public\".\"t_non_operational_area\"")
            layerPlot = self.findLayerByPattern("\"public\".\"t_plot\"")
            srid = layerPlot.source().split(" ")[7].split("=")[1]
            if(srid):
                if(not self.db.openConnection()):
                    self.db.setConnectionInfo()
                    self.db.openConnection()
                
                plotGuid=""
                for feature in layerNep.getFeatures(QgsFeatureRequest(QgsExpression("primarykey='"+self.guid+"'"))):
                    plotGuid = str(feature['plot'])
                self.db.executeQuery("alter table t_non_operational_area disable trigger all")
                self.db.executeQuery("alter table t_noa_binding_line disable trigger all")
                self.db.executeQuery("delete from t_noa_point where noa='"+self.guid+"'")
                self.db.executeQuery("delete from t_noa_rumbs where noa='"+self.guid+"'")
                countLinePoints = len(self.linePoints)
                bindingLine = QgsGeometry.fromPolyline(self.linePoints)
                tmpPoints = list(self.points)
                #tmpPoints.append(tmpPoints[0])
                polygon = QgsGeometry.fromPolygon([tmpPoints])
                
                self.db.executeQuery("delete from t_noa_binding_line where noa='"+self.guid+"'")
                if(len(self.linePoints)>0):
                    self.db.executeQuery("insert into t_noa_binding_line(primarykey,shape,noa) values(uuid_generate_v4(),st_geomFromText('"+bindingLine.exportToWkt()+"',"+srid+"),'"+self.guid+"')")
                self.db.executeQuery("update t_non_operational_area set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+"),area="+str(round(polygon.area()/10000,1))+" where primarykey='"+self.guid+"'")
                self.db.executeQuery("update t_plot set area=area_common-(select sum(area) from t_non_operational_area where plot = '"+plotGuid+"') where primarykey = '"+plotGuid+"'")
                ###print "update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guid+"'"
                ###print len(self.linePoints)
                pointValues=""
                rumbValues = ""               
                for i in range(self.tableWidget.rowCount()):
                    number = self.tableWidget.item(i,0).text().replace('\'','`')
                    length = self.tableWidget.item(i,2).text()
                    angle = self.tableWidget.item(i,3).text()
                    pointNumber=number.split('-')[0]
                    if(self.azimuth):
                        tmpSplit = angle.split(u'°')
                        minutes = float(tmpSplit[1].replace('\'',''))
                        angle = float(tmpSplit[0])
                        angle = self.azimuthToRumb(angle,minutes)
                    angle = angle.replace('\'','`')
                    ####print angle
                    if(countLinePoints>0):
                        if i<countLinePoints:
                            pointValues=pointValues+"(uuid_generate_v4(),'"+self.guid+"','"+pointNumber+"',st_geomFromText('"+QgsGeometry.fromPoint(self.linePoints[i]).exportToWkt()+"',"+srid+"),'5b8e90b5-df13-46b6-bf55-59146110dc28',"+str(i)+"),"
                            if(i<countLinePoints-1):
                                rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','5b8e90b5-df13-46b6-bf55-59146110dc28','"+self.guid+"'),"
                        if i-(countLinePoints-1)>=0:
                            pointValues=pointValues+"(uuid_generate_v4(),'"+self.guid+"','"+pointNumber+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i-(countLinePoints-1)]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504',"+str(i)+"),"
                            rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guid+"'),"
                    else:
                        rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guid+"'),"
                        pointValues=pointValues+"(uuid_generate_v4(),'"+self.guid+"','"+pointNumber+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504',"+str(i)+"),"
                        ####print pointValues
                        ####print rumbValues
                pointValues=pointValues[:-1:]
                rumbValues = rumbValues[:-1:]
                ####print "insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues
                ####print rumbValues
                self.db.executeQuery("insert into t_noa_point(primarykey,noa,\"number\",shape,type_object,\"order\") values "+pointValues)
                self.db.executeQuery("INSERT INTO t_noa_rumbs(primarykey, \"number\", distance, rumb, type, noa) values "+rumbValues)
                self.db.executeQuery("alter table t_non_operational_area enable trigger all")
                self.db.executeQuery("alter table t_noa_binding_line enable trigger all")
                
                self.dockwidget.lineEdit_areaPlot.setText(str(round(polygon.area()/10000,1)))
                
                self.db.closeConnection()
            else:
                QMessageBox.information(None,u"Делянка",u"Добавьте слой t_plot для изменения НЭП.")
    #обновляем таблицу, практически идентичен методу addInDatabase класса WorkWithTableAndPoints, больше инфы там    
    def updateBindingDatabase(self):
        self.linePoints = self.draw.getLinePoints()
        if(self.guid and self.db!=None):
            srid = None
            layerQuart = self.findLayerByPattern("\"public\".\"t_forestquarter\"")
            layerPlot = self.findLayerByPattern("\"public\".\"t_plot\"")
            srid = layerQuart.source().split(" ")[7].split("=")[1]
            layerTax=self.findLayerByPattern("table=\"public\".\"t_taxationisolated\"","type=MultiPolygon")
            if(srid):
                if(not self.db.openConnection()):
                    self.db.setConnectionInfo()
                    self.db.openConnection()
                
                forestquarterGuid=""
                for feature in layerPlot.getFeatures(QgsFeatureRequest(QgsExpression("primarykey='"+self.guid+"'"))):
                    forestquarterGuid = str(feature['forestquarter'])
                self.db.executeQuery("delete from t_plot_point where plot_fk='"+self.guid+"'")
                self.db.executeQuery("delete from t_rumbs where plot='"+self.guid+"'")
                countLinePoints = len(self.linePoints)
                bindingLine = QgsGeometry.fromPolyline(self.linePoints)
                tmpPoints = list(self.points)
                #tmpPoints.append(tmpPoints[0])
                polygon = QgsGeometry.fromPolygon([tmpPoints])
                
                featureTaxes = []
                for feature in layerTax.getFeatures(QgsFeatureRequest(QgsExpression("forestquarter='"+forestquarterGuid+"'"))):
                    ####print "layerTax:",feature.geometry()
                    if feature.geometry() !=None and feature.geometry().intersects(polygon):
                        featureTaxes.append([str(feature['primarykey']),polygon.intersection(feature.geometry())])
                
                self.db.executeQuery("delete from t_binding_line where plot='"+self.guid+"'")
                if(len(self.linePoints)>0):
                    self.db.executeQuery("insert into t_binding_line(primarykey,shape,plot) values(uuid_generate_v4(),st_geomFromText('"+bindingLine.exportToWkt()+"',"+srid+"),'"+self.guid+"')")
                self.db.executeQuery("update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guid+"'")
                ###print "update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guid+"'"
                ###print len(self.linePoints)
                pointValues=""
                rumbValues = ""               
                for i in range(self.tableWidget.rowCount()):
                    number = self.tableWidget.item(i,0).text()
                    length = self.tableWidget.item(i,2).text()
                    angle = self.tableWidget.item(i,3).text()
                    if(self.azimuth):
                        tmpSplit = angle.split(u'°')
                        minutes = float(tmpSplit[1].replace('\'',''))
                        angle = float(tmpSplit[0])
                        angle = self.azimuthToRumb(angle,minutes)
                    angle = angle.replace('\'','`')
                    ####print angle
                    if(countLinePoints>0):
                        if i<countLinePoints:
                            pointValues=pointValues+"(uuid_generate_v4(),'"+self.guid+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(self.linePoints[i]).exportToWkt()+"',"+srid+"),'5b8e90b5-df13-46b6-bf55-59146110dc28'),"
                            if(i<countLinePoints-1):
                                rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','5b8e90b5-df13-46b6-bf55-59146110dc28','"+self.guid+"'),"
                        if i-(countLinePoints-1)>=0:
                            pointValues=pointValues+"(uuid_generate_v4(),'"+self.guid+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i-(countLinePoints-1)]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504'),"
                            rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guid+"'),"
                    else:
                        rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guid+"'),"
                        pointValues=pointValues+"(uuid_generate_v4(),'"+self.guid+"','"+str(i)+"',st_geomFromText('"+QgsGeometry.fromPoint(tmpPoints[i]).exportToWkt()+"',"+srid+"),'b6dcbdf5-0c43-4cbd-8742-166d59b89504'),"
                        ####print pointValues
                        ####print rumbValues
                pointValues=pointValues[:-1:]
                rumbValues = rumbValues[:-1:]
                ####print "insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues
                ####print rumbValues
                self.db.executeQuery("insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues)
                self.db.executeQuery("INSERT INTO t_rumbs(primarykey, \"number\", distance, rumb, type, plot) values "+rumbValues)
                
                self.db.executeQuery("delete from t_isolatedplots where plot = '"+self.guid+"'")
                isolatedValues = ""
                for item in featureTaxes:
                    isolatedValues =isolatedValues+("(uuid_generate_v4(),'"+item[0]+"','"+self.guid+"',st_geomFromText('"+item[1].exportToWkt()+"',"+srid+"),'1'),")
                isolatedValues=isolatedValues[:-1:]
                self.db.executeQuery("insert into t_isolatedplots(primarykey,isolated,plot,shape,actual) values "+isolatedValues)
                self.dockwidget.lineEdit_areaPlot.setText(str(round(polygon.area()/10000,1)))
                
                self.db.closeConnection()
            else:
                QMessageBox.information(None,u"Квартал",u"Добавьте слой t_forestquarter для изменения делянки.")
    
    def undo(self):
        self.tableWidget.blockSignals(True)
        ##print "ADDBINDINGLINE UNDO", self.oldRow,self.row
        if(self.oldRow == self.row):
            self.tableWidget.item(self.row,1).setCheckState(Qt.Unchecked)
            self.deleteBindingLine(self.row)
        else:
            ####print(self.oldRow)
            self.tableWidget.item(self.row,1).setCheckState(Qt.Unchecked)
            self.deleteBindingLine(self.row)
            self.tableWidget.item(self.oldRow,1).setCheckState(Qt.Checked)
            self.addBindingLine(self.oldRow)
        
        if(self.tableWidget.rowCount()>2): 
            if not self.dockwidget.radioButton_azimuth.isChecked() and ' ' not in self.lastRowAngle:
                tmpAngle,tmpMinutes = self.lastRowAngle.replace(u'\'','').split(u'°')
                self.lastRowAngle = self.azimuthToRumb(float(tmpAngle),float(tmpMinutes))
            elif self.dockwidget.radioButton_azimuth.isChecked() and ' ' in self.lastRowAngle:
                self.lastRowAngle = self.rumbToAzimuth(self.lastRowAngle)
            self.tableWidget.item(self.tableWidget.rowCount()-1,2).setText(str(self.lastRowLength))
            self.tableWidget.item(self.tableWidget.rowCount()-1,3).setText(str(self.lastRowAngle))
            deltaLength,deltaAngle,deltaMinutes = self.getDifferenceBetween(self.points[-1],self.points[0],self.magnet,self.tableWidget,self.dockwidget.radioButton_azimuth.isChecked())
        else:
            deltaLength=0.0
            deltaAngle = 0
            deltaMinutes = 0
        ###print "UNDO COMMAND ADD:",deltaLength,deltaAngle,deltaMinutes
        self.dockwidget.lineEdit_difference_distance.setText(str(deltaLength))
        self.dockwidget.lineEdit_difference_degrees.setText(str(deltaAngle)+u'°'+str(deltaMinutes)+u'\'')
        self.tableWidget.blockSignals(False)
        if self.dockwidget.checkBox_nep.isChecked():
            self.updateNepBindingDatabase()
        else:
            self.updateBindingDatabase()
        ####print("afterUndoBinding:",self.oldRow,self.bindingLineRow,self.row)
    
    
    def deleteBindingLine(self,row):
        linePoints = self.draw.getLinePoints()
        ####print "before delete points",self.draw.getPoints()
        ####print "deletePoints binding", linePoints
        for i in range(len(linePoints)-1):
            ####print i
            self.draw.getPoints().insert(i,linePoints[i])
        del linePoints[:]
        ####print "after delete points2",self.draw.getPoints()
        if(not self.guid):
            self.draw.drawPolygon(True)
            self.draw.drawBindingLine()
        points = self.draw.getPoints()
        rowCount = self.tableWidget.rowCount()-1
        countPoints = len(points)
        length,angle,minutes = self.calcAngleLengthByPoints(points[-1],points[0],self.magnet)
        endPointNumber = self.tableWidget.item(0,0).text().split('-')[0]
        startPointNumber = self.tableWidget.item(rowCount,0).text().split('-')[0]
        self.tableWidget.item(rowCount,0).setText(startPointNumber+"-"+endPointNumber)
        self.tableWidget.item(rowCount,2).setText(str(length))
        if(self.azimuth):
            self.tableWidget.item(rowCount,3).setText(str(int(angle))+u'°'+str(int(minutes))+u'\'')
        else:
            self.tableWidget.item(rowCount,3).setText(self.azimuthToRumb(float(int(angle)),float(minutes)))
    #!!!!!
    def addBindingLine(self,row):
        points = self.draw.getPoints()
        for i in range(row+2):
            ###print "tut",i
            self.draw.linePointAppend(points[i])
        ####print "before addbindingline points",self.draw.getPoints()
        del points[:row+1]
        ####print "after addbindingline points",self.draw.getPoints()
        if(not self.guid):
            self.draw.drawPolygon(True)
            self.draw.drawBindingLine()
        rowCount = self.tableWidget.rowCount()-1
        countLinePoints = len(self.draw.getLinePoints())
        countPoints = len(points)+countLinePoints-1
        length,angle,minutes = self.calcAngleLengthByPoints(points[-1],points[0],self.magnet)
        endPointNumber = self.tableWidget.item(row,0).text().split('-')[1]
        startPointNumber = self.tableWidget.item(rowCount,0).text().split('-')[0]
        self.tableWidget.item(rowCount,0).setText(startPointNumber+"-"+endPointNumber)
        self.tableWidget.item(rowCount,2).setText(str(length))
        if(self.dockwidget.radioButton_azimuth.isChecked()):
            self.tableWidget.item(rowCount,3).setText(str(int(angle))+u'°'+str(int(minutes))+u'\'')
        else:
            self.tableWidget.item(rowCount,3).setText(self.azimuthToRumb(float(int(angle)),float(minutes)))

#Добавление точки вручную через кнопку "Добавить точку"        
class CommandAddManualPoint(QUndoCommand,WorkWithTableAndPoints):
    def __init__(self,description,tableWidget,lineEdit_difference_distance,lineEdit_difference_degrees,magnet,draw,azimuth=None,guidPlot="",db=None,nepAdd=None):
        super(CommandAddManualPoint, self).__init__(description)
        self.tableWidget = tableWidget
        self.draw = draw
        self.magnet = magnet
        self.points = self.draw.getPoints()
        self.linePoints = self.draw.getLinePoints()
        self.azimuth = azimuth
        self.guidPlot = guidPlot
        self.db = db
        self.lastRowLength = None
        self.lastRowAngle = None
        self.nepAdd = nepAdd
        if(self.tableWidget.rowCount()>2):
            self.lastRowLength = self.tableWidget.item(self.tableWidget.rowCount()-1,2).text()
            self.lastRowAngle = self.tableWidget.item(self.tableWidget.rowCount()-1,3).text()
        self.lineEdit_difference_distance = lineEdit_difference_distance
        self.lineEdit_difference_degrees = lineEdit_difference_degrees
    def redo(self):
        self.draw.resetDifference()
        self.addRecord(self.nepAdd.isChecked())
    
    def undo(self):
        self.tableWidget.selectionModel().clear()
        self.tableWidget.setCurrentCell(self.tableWidget.rowCount()-1,0)
        self.deleteRow(self.tableWidget,self.draw.getLinePoints(),self.points,self.points[-1],self.magnet,self.azimuth.isChecked(),self.nepAdd)
        if(self.tableWidget.rowCount()>2): 
            if not self.azimuth.isChecked() and ' ' not in self.lastRowAngle:
                tmpAngle,tmpMinutes = self.lastRowAngle.replace(u'\'','').split(u'°')
                self.lastRowAngle = self.azimuthToRumb(float(tmpAngle),float(tmpMinutes))
            elif self.azimuth.isChecked() and ' ' in self.lastRowAngle:
                self.lastRowAngle = self.rumbToAzimuth(self.lastRowAngle)
            self.tableWidget.item(self.tableWidget.rowCount()-1,2).setText(str(self.lastRowLength))
            self.tableWidget.item(self.tableWidget.rowCount()-1,3).setText(str(self.lastRowAngle))
            deltaLength,deltaAngle,deltaMinutes = self.getDifferenceBetween(self.points[-1],self.points[0],self.magnet,self.tableWidget,self.azimuth.isChecked())
        else:
            deltaLength=0.0
            deltaAngle = 0
            deltaMinutes = 0
        ###print "UNDO COMMAND ADD:",deltaLength,deltaAngle,deltaMinutes
        self.lineEdit_difference_distance.setText(str(deltaLength))
        self.lineEdit_difference_degrees.setText(str(deltaAngle)+u'°'+str(deltaMinutes)+u'\'')
        #self.draw.setPoint(self.points[-1])
    
    def addRecord(self,nepAdd=False):           
        countPoints = len(self.points)
        countLinePoints = len(self.linePoints)
        if(countLinePoints>0):
            countPoints=countPoints+(countLinePoints-1)
            endNumberPoint = str((countLinePoints-1))
        else:
            endNumberPoint = '0'
        checkBoxItem = QTableWidgetItem()
        checkBoxItem.setCheckState(Qt.Unchecked)
        rowCount = self.tableWidget.rowCount()
        firstNumber = str(countPoints-1)
        secondNumber = str(countPoints)
        if nepAdd:
            firstNumber=firstNumber+'\''
            secondNumber=secondNumber+'\''
            endNumberPoint=str(endNumberPoint)+'\''
        if countPoints>1 and rowCount<countPoints:
            self.points.append(self.points[-1])
            self.addRow(self.tableWidget,rowCount,firstNumber,secondNumber,0,0,0,self.azimuth.isChecked())
            ####print "addRow",rowCount,str(countPoints-1),str(countPoints)
            rowCount=rowCount+1
            self.addRow(self.tableWidget,rowCount,secondNumber,endNumberPoint,0,0,0,self.azimuth.isChecked())
            ####print "ya tut1"
        else:
            if rowCount==countPoints:
                ####print "ya tut2"
                ####print "addManual",self.azimuth
                self.points.insert(countPoints-1,self.points[-1])
                self.addRow(self.tableWidget,rowCount-1,firstNumber,secondNumber,0,0,0,self.azimuth.isChecked())
                length,angle,minutes = self.calcAngleLengthByPoints(self.points[0],self.points[-1],self.magnet)
                self.tableWidget.item(rowCount,0).setText(secondNumber+"-"+endNumberPoint)
                self.tableWidget.item(rowCount,2).setText(str(length))
                if(self.azimuth.isChecked()):
                    self.tableWidget.item(rowCount,3).setText(str(int(angle))+u'°'+str(int(round(minutes)))+u'\'')
                else:
                    self.tableWidget.item(rowCount,3).setText(self.azimuthToRumb(float(angle),float(minutes)))
            else:
                self.points.append(self.points[-1])
                self.addRow(self.tableWidget,rowCount,firstNumber,secondNumber,0,0,0,self.azimuth.isChecked())
        
#Добавление точки, происходит при рисовании делянки мышью
#Так как этот класс используется только в классе Draw, то был создан триггер, который обновляет стартовую точку.

class CommandAddPoint(QUndoCommand,WorkWithTableAndPoints):
    def __init__(self,description,buttonDelete,lineEdit_difference_distance,lineEdit_difference_degrees,triggerRedo,tableWidget,linePoints,allPoints,rubberBand,startPoint,endPoint,end,length,angle,minutes,magnet=0.0,isEmittingPoint=False,azimuth=None,nepAdd=None,equalAndNepPoints=None):
        super(CommandAddPoint, self).__init__(description)
        self.tableWidget = tableWidget
        self.points = allPoints
        self.rubberBand = rubberBand
        self.startPoint = QgsPoint(startPoint.x(),startPoint.y())
        if(endPoint!=None):
            self.endPoint = QgsPoint(endPoint.x(),endPoint.y())
        else:
            self.endPoint = None
        self.magnet = magnet
        self.triggerRedo = triggerRedo
        #self.triggerUndo = triggerUndo
        self.length = round(length,1)
        self.angle = angle
        self.minutes = minutes
        self.linePoints = linePoints
        self.azimuth = azimuth
        self.lastRowLength = None
        self.lastRowAngle = None
        self.nepAdd = nepAdd
        self.equalAndNepPoints=equalAndNepPoints
        if(self.tableWidget.rowCount()>2):
            self.lastRowLength = self.tableWidget.item(self.tableWidget.rowCount()-1,2).text()
            self.lastRowAngle = self.tableWidget.item(self.tableWidget.rowCount()-1,3).text()
        self.lineEdit_difference_distance = lineEdit_difference_distance
        self.lineEdit_difference_degrees = lineEdit_difference_degrees
        #self.workWithTableAndPoints = WorkWithTableAndPoints(self.points,self.tableWidget)
        
        
        ####print "self.startPoint=",id(self.startPoint)
        ####print "startPoint=",id(startPoint)
        
    def redo(self):
       # ###print "redo before addCommand id ",id(self.startPoint)
       # ###print "redo before addCommand (x,y)",self.startPoint
        ####print "redo canvas"
        ####print "redo BEFORE commandAddPoints:",self.points
        #времено

            
            
        if self.endPoint != None and len(self.points)>0:
            self.length,self.angle,self.minutes = self.calcAngleLengthByPoints(self.points[-1],self.startPoint)
            ####print "tut"
            self.addRows(self.tableWidget,self.linePoints,self.points,self.startPoint,self.endPoint,self.length,self.angle+round(self.minutes/60,2),self.magnet,self.azimuth.isChecked(),self.nepAdd.isChecked(),self.equalAndNepPoints)
        self.drawPolygon(False)
        #Тригер, для обновления стартовой точки
        self.triggerRedo.emit(self.startPoint)
        if len(self.points)>0:
            self.nepAdd.setEnabled(False)
        ####print "REDOKONEC"
        ####print "redo AFTER commandAddPoints:",self.points
        #self.startPoint.setX(self.points[-1].x())
        #self.startPoint.setY(self.points[-1].y())
        ####print "redo after addCommand id ",id(self.startPoint)
        ####print "redo after addCommand id ",id(self.startPoint)
        ####print "redo after addCommand (x,y)",self.startPoint
        
    
    def undo(self):
        ####print "undoAdd",self.tableWidget.rowCount()-1
        ####print self.points
        ###print "COMMANDADD AZIMUTH",self.azimuth.isChecked()
        self.tableWidget.selectionModel().clear()
        self.tableWidget.setCurrentCell(self.tableWidget.rowCount()-1,0)
        self.deleteRow(self.tableWidget,self.linePoints,self.points,self.startPoint,self.magnet,self.azimuth.isChecked(),self.nepAdd.isChecked())
        if(self.tableWidget.rowCount()>2): 
            if not self.azimuth.isChecked() and ' ' not in self.lastRowAngle:
                tmpAngle,tmpMinutes = self.lastRowAngle.replace(u'\'','').split(u'°')
                self.lastRowAngle = self.azimuthToRumb(float(tmpAngle),float(tmpMinutes))
            elif self.azimuth.isChecked() and ' ' in self.lastRowAngle:
                self.lastRowAngle = self.rumbToAzimuth(self.lastRowAngle)
            self.tableWidget.item(self.tableWidget.rowCount()-1,2).setText(str(self.lastRowLength))
            self.tableWidget.item(self.tableWidget.rowCount()-1,3).setText(str(self.lastRowAngle))
            deltaLength,deltaAngle,deltaMinutes = self.getDifferenceBetween(self.points[-1],self.points[0],self.magnet,self.tableWidget,self.azimuth.isChecked())
        else:
            deltaLength=0.0
            deltaAngle = 0
            deltaMinutes = 0
        ###print "UNDO COMMAND ADD:",deltaLength,deltaAngle,deltaMinutes
        self.lineEdit_difference_distance.setText(str(deltaLength))
        self.lineEdit_difference_degrees.setText(str(deltaAngle)+u'°'+str(deltaMinutes)+u'\'')
        self.triggerRedo.emit(self.points[-1])
        self.drawPolygon(True)
        if len(self.points)>0:
            self.nepAdd.setEnabled(False)
        else:
            self.nepAdd.setEnabled(True)
        ####print "points:",self.points  
    
    
    def drawPolygon(self,end):
        if(end!=True):
            self.points.append(self.startPoint)
        self.showRect(self.points,self.endPoint)
    
    def showRect(self,points,endPoint):
        self.rubberBand.reset(QGis.Polygon)
        for point in self.points:
            self.rubberBand.addPoint(point,False)
        if(endPoint!=None):
            self.rubberBand.addPoint(endPoint,True)
        self.rubberBand.show()

class CommandUpdateMagnet(QUndoCommand,WorkWithTableAndPoints):
    def __init__(self,description,dockwidget,draw,prevMagnet=0.0,db = None,guidPlot = None):
        super(CommandUpdateMagnet, self).__init__(description)
        self.prevMagnet = prevMagnet
        self.magnet = 0
        self.dockwidget = dockwidget
        self.draw = draw
        self.checkBack = False
        self.db = db
        self.guidPlot = guidPlot
        self.tableWidget = dockwidget.tableWidget_points
        self.azimuth = dockwidget.radioButton_azimuth.isChecked()
    def redo(self):
        if not self.checkBack:
            if self.dockwidget.lineEdit_magDeclin_degrees.text():
                self.magnet=float(self.dockwidget.lineEdit_magDeclin_degrees.text())
            if self.dockwidget.lineEdit_magDeclin_minutes.text():
                tmpMag = float(self.dockwidget.lineEdit_magDeclin_degrees.text())
                self.magnet=tmpMag+round(float(self.dockwidget.lineEdit_magDeclin_minutes.text())/60,2)*((lambda x: (1, -1)[x < 0])(tmpMag))
        else:
            self.dockwidget.lineEdit_magDeclin_degrees.setText(str(int(self.magnet)))
            if self.magnet % 1 != 0:
                self.dockwidget.lineEdit_magDeclin_minutes.setText(str(int(round((self.magnet % 1)*60))))
        if self.draw != None:
            self.draw.setMagnet(self.magnet)
        ##print "commandUpdate:", self.prevMagnet," ",self.magnet,len(self.draw.getPoints())
        if len(self.draw.getPoints())>0:
            self.calculateAllPoints(self.dockwidget.tableWidget_points,self.draw.getLinePoints(),self.draw.getPoints(),self.draw.getStartPoint(),0,self.magnet,self.prevMagnet,True,self.dockwidget.radioButton_azimuth.isChecked(),self.dockwidget.radioButton_magnetAngle.isChecked())
            ##print "COMANDUPDATE POINTS:",self.draw.getPoints()
            if not self.guidPlot:
                ##print "GUID"
                self.draw.drawPolygon(True)
                self.draw.drawBindingLine()
                self.draw.setPoint(self.draw.getPoints()[-1])
        if self.dockwidget.checkBox_nep.isChecked():
            self.updateNepRumbsInDatabase(self.magnet)
        else:
            self.updateRumbsInDatabase(self.magnet)
    
    def undo(self):
        self.dockwidget.lineEdit_magDeclin_degrees.setText(str(int(self.prevMagnet)))
        if self.prevMagnet % 1 != 0:
            self.dockwidget.lineEdit_magDeclin_minutes.setText(str(int(round((self.prevMagnet % 1)*60))))
        if self.draw != None:
            self.draw.setMagnet(self.prevMagnet)
        ####print self.prevMagnet," ",self.magnet
        if len(self.draw.getPoints())>0:
            self.calculateAllPoints(self.dockwidget.tableWidget_points,self.draw.getLinePoints(),self.draw.getPoints(),self.draw.getStartPoint(),0,self.prevMagnet,self.magnet,True,self.dockwidget.radioButton_azimuth.isChecked(),self.dockwidget.radioButton_magnetAngle.isChecked())
            if not self.guidPlot:
                self.draw.drawPolygon(True)
                self.draw.drawBindingLine()
                self.draw.setPoint(self.draw.getPoints()[-1])
        self.checkBack = True
        if self.dockwidget.checkBox_nep.isChecked():
            self.updateNepRumbsInDatabase(self.prevMagnet)
        else:
            self.updateRumbsInDatabase(self.prevMagnet)
    
    
    def updateNepRumbsInDatabase(self,magnet):
        if(self.guidPlot and self.db!=None):
            self.linePoints = self.draw.getLinePoints()
            #если по каким то причинам, инфа о коннекте не была установлена, то устанавливаем и соединяемся
            if(not self.db.openConnection()):
                self.db.setConnectionInfo()
                self.db.openConnection()
            #self.db.executeQuery("delete from t_rumbs where plot='"+self.guidPlot+"'")
            countLinePoints = len(self.linePoints)
            self.db.executeQuery("alter table t_non_operational_area disable trigger all")
            self.db.executeQuery("update t_non_operational_area set mangle="+str(magnet)+"  where primarykey='"+self.guidPlot+"'")
            self.db.executeQuery("alter table t_non_operational_area enable trigger all")
            ###print "update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guidPlot+"'"
            ###print len(self.linePoints)
            rumbValues = ""               
            for i in range(self.tableWidget.rowCount()):
                number = self.tableWidget.item(i,0).text().replace('\'','`')
                length = self.tableWidget.item(i,2).text()
                angle = self.tableWidget.item(i,3).text()
                if(self.azimuth):
                    tmpSplit = angle.split(u'°')
                    minutes = float(tmpSplit[1].replace('\'',''))
                    angle = float(tmpSplit[0])
                    angle = self.azimuthToRumb(angle,minutes)
                ##print "UpdateRumbsInDatabase:",number,length,angle
                angle = angle.replace('\'','`')
                ####print angle
                if(countLinePoints>0):
                    if(i<countLinePoints-1):
                        self.db.executeQuery("update t_noa_rumbs set distance="+length+", rumb='"+angle+"', type='5b8e90b5-df13-46b6-bf55-59146110dc28' where noa='"+self.guidPlot+"' and \"number\"='"+number+"'")
                        #rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','5b8e90b5-df13-46b6-bf55-59146110dc28','"+self.guidPlot+"'),"
                        ###print "update t_rumbs set distance="+length+", rumb='"+angle+"', type='5b8e90b5-df13-46b6-bf55-59146110dc28' where plot='"+self.guidPlot+"' and \"number\"='"+number+"'"
                    if i-(countLinePoints-1)>=0:
                        self.db.executeQuery("update t_noa_rumbs set distance="+length+", rumb='"+angle+"', type='b6dcbdf5-0c43-4cbd-8742-166d59b89504' where noa='"+self.guidPlot+"' and \"number\"='"+number+"'")
                        #rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guidPlot+"'),"
                        ###print "update t_rumbs set distance="+length+", rumb='"+angle+"', type='b6dcbdf5-0c43-4cbd-8742-166d59b89504' where plot='"+self.guidPlot+"' and \"number\"='"+number+"'"
                else:
                    self.db.executeQuery("update t_noa_rumbs set distance="+length+", rumb='"+angle+"', type='b6dcbdf5-0c43-4cbd-8742-166d59b89504' where noa='"+self.guidPlot+"' and \"number\"='"+number+"'")
                    #rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guidPlot+"'),"
                    ###print "update t_rumbs set distance="+length+", rumb='"+angle+"', type='b6dcbdf5-0c43-4cbd-8742-166d59b89504' where plot='"+self.guidPlot+"' and \"number\"='"+number+"'"
                    ####print rumbValues
            ###print rumbValues
            #rumbValues = rumbValues[:-1:]
            ####print "insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues
            ####print rumbValues
            #self.db.executeQuery("INSERT INTO t_rumbs(primarykey, \"number\", distance, rumb, type, plot) values "+rumbValues)  
            self.db.closeConnection()
    
    
    def updateRumbsInDatabase(self,magnet):
        if(self.guidPlot and self.db!=None):
            self.linePoints = self.draw.getLinePoints()
            #если по каким то причинам, инфа о коннекте не была установлена, то устанавливаем и соединяемся
            if(not self.db.openConnection()):
                self.db.setConnectionInfo()
                self.db.openConnection()
            #self.db.executeQuery("delete from t_rumbs where plot='"+self.guidPlot+"'")
            countLinePoints = len(self.linePoints)
            self.db.executeQuery("alter table t_plot disable trigger all")
            self.db.executeQuery("update t_plot set mangle="+str(magnet)+"  where primarykey='"+self.guidPlot+"'")
            self.db.executeQuery("alter table t_plot enable trigger all")
            ###print "update t_plot set shape=st_geomFromText('"+polygon.exportToWkt()+"',"+srid+") where primarykey='"+self.guidPlot+"'"
            ###print len(self.linePoints)
            rumbValues = ""               
            for i in range(self.tableWidget.rowCount()):
                number = self.tableWidget.item(i,0).text()
                length = self.tableWidget.item(i,2).text()
                angle = self.tableWidget.item(i,3).text()
                if(self.azimuth):
                    tmpSplit = angle.split(u'°')
                    minutes = float(tmpSplit[1].replace('\'',''))
                    angle = float(tmpSplit[0])
                    angle = self.azimuthToRumb(angle,minutes)
                ##print "UpdateRumbsInDatabase:",number,length,angle
                angle = angle.replace('\'','`')
                ####print angle
                if(countLinePoints>0):
                    if(i<countLinePoints-1):
                        self.db.executeQuery("update t_rumbs set distance="+length+", rumb='"+angle+"', type='5b8e90b5-df13-46b6-bf55-59146110dc28' where plot='"+self.guidPlot+"' and \"number\"='"+number+"'")
                        #rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','5b8e90b5-df13-46b6-bf55-59146110dc28','"+self.guidPlot+"'),"
                        ###print "update t_rumbs set distance="+length+", rumb='"+angle+"', type='5b8e90b5-df13-46b6-bf55-59146110dc28' where plot='"+self.guidPlot+"' and \"number\"='"+number+"'"
                    if i-(countLinePoints-1)>=0:
                        self.db.executeQuery("update t_rumbs set distance="+length+", rumb='"+angle+"', type='b6dcbdf5-0c43-4cbd-8742-166d59b89504' where plot='"+self.guidPlot+"' and \"number\"='"+number+"'")
                        #rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guidPlot+"'),"
                        ###print "update t_rumbs set distance="+length+", rumb='"+angle+"', type='b6dcbdf5-0c43-4cbd-8742-166d59b89504' where plot='"+self.guidPlot+"' and \"number\"='"+number+"'"
                else:
                    self.db.executeQuery("update t_rumbs set distance="+length+", rumb='"+angle+"', type='b6dcbdf5-0c43-4cbd-8742-166d59b89504' where plot='"+self.guidPlot+"' and \"number\"='"+number+"'")
                    #rumbValues = rumbValues+"(uuid_generate_v4(),'"+number+"',"+length+",'"+angle+"','b6dcbdf5-0c43-4cbd-8742-166d59b89504','"+self.guidPlot+"'),"
                    ###print "update t_rumbs set distance="+length+", rumb='"+angle+"', type='b6dcbdf5-0c43-4cbd-8742-166d59b89504' where plot='"+self.guidPlot+"' and \"number\"='"+number+"'"
                    ####print rumbValues
            ###print rumbValues
            #rumbValues = rumbValues[:-1:]
            ####print "insert into t_plot_point(primarykey,plot_fk,\"number\",shape,type_object) values "+pointValues
            ####print rumbValues
            #self.db.executeQuery("INSERT INTO t_rumbs(primarykey, \"number\", distance, rumb, type, plot) values "+rumbValues)  
            self.db.closeConnection()

class CommandUpdateYear(QUndoCommand,WorkWithTableAndPoints):
    def __init__(self,description,lineEdit_yearOfCutting,draw,db,guidPlot):
        super(CommandUpdateYear, self).__init__(description)
        self.lineEdit_yearOfCutting = lineEdit_yearOfCutting
        self.prevYear = 0
        self.year = lineEdit_yearOfCutting.text()
        self.db = db
        self.guidPlot = guidPlot
        self.draw = draw
    
    def redo(self):
        if(self.db !=None and self.guidPlot!=None):
            if(self.year):
                self.prevYear = self.draw.getYearCutting()
                ###print "RRAZNOE:","update t_plot set \"number=\""+plotNumber+" where primarykey='"+guidPlot+"'"
                self.db.openConnection()
                self.db.executeQuery("update t_plot set yearOfCutting="+self.year+" where primarykey='"+self.guidPlot+"'")
                self.db.closeConnection()
                self.draw.setYearCutting(self.year)
    
    def undo(self):
        if(self.db !=None and self.guidPlot!=None):
            if not self.prevYear:
                self.prevYear = 0
            self.year = self.prevYear
            ###print "UNDORRAZNOE"#,"update t_plot set \"number=\""+plotNumber+" where primarykey='"+guidPlot+"'"
            self.db.openConnection()
            self.db.executeQuery("update t_plot set yearOfCutting="+self.year+" where primarykey='"+self.guidPlot+"'")
            self.db.closeConnection()
            self.draw.setYearCutting(self.prevYear)
            self.lineEdit_yearOfCutting.setText(self.prevYear)


class CommandUpdateNumber(QUndoCommand,WorkWithTableAndPoints):
    def __init__(self,description,lineEdit_numberPlot,draw,db,guid,nepAdd=False):
        super(CommandUpdateNumber, self).__init__(description)
        self.lineEdit_numberPlot = lineEdit_numberPlot
        self.prevNumber = 0
        self.number = lineEdit_numberPlot.text()
        self.db = db
        self.guid = guid
        self.draw = draw
        self.nepAdd = nepAdd
    
    def redo(self):
        if(self.db !=None and self.guid!=None):
            if(self.number):
                self.prevNumber = self.draw.getNumber()
                ###print "RRAZNOE:","update t_plot set \"number=\""+number+" where primarykey='"+guidPlot+"'"
                self.db.openConnection()
                if self.nepAdd:
                    self.db.executeQuery("alter table t_non_operational_area disable trigger all")
                    self.db.executeQuery("update t_non_operational_area set \"number\"="+self.number+" where primarykey='"+self.guid+"'")
                    self.db.executeQuery("alter table t_non_operational_area enable trigger all")
                else:
                    self.db.executeQuery("update t_plot set \"number\"="+self.number+" where primarykey='"+self.guid+"'")
                self.db.closeConnection()
                self.draw.setNumber(self.number)
    
    def undo(self):
        if(self.db !=None and self.guid!=None):
            if(self.prevNumber):
                self.number = self.prevNumber
                ##print "UNDORRAZNOE"#,"update t_plot set \"number=\""+number+" where primarykey='"+guidPlot+"'"
                self.db.openConnection()
                if self.nepAdd:
                    self.db.executeQuery("alter table t_non_operational_area disable trigger all")
                    self.db.executeQuery("update t_non_operational_area set \"number\"="+self.number+" where primarykey='"+self.guid+"'")
                    self.db.executeQuery("alter table t_non_operational_area enable trigger all")
                else:
                    self.db.executeQuery("update t_plot set \"number\"="+self.number+" where primarykey='"+self.guid+"'")
                self.db.closeConnection()
                self.draw.setNumber(self.prevNumber)
                self.lineEdit_numberPlot.setText(self.prevNumber)


#Класс для работы с базой    
class DataBase:
    def __init__(self,dockwidget):
        self.checkConnection = False
        self.dockwidget = dockwidget
        self.db = None

    
    def setConnectionInfo(self):
        connInfo = self.getDataSourceInfo("\"public\".\"t_plot\"")
        self.db = QSqlDatabase.addDatabase("QPSQL")
        self.db.setHostName(connInfo[1])
        self.db.setDatabaseName(connInfo[0])
        self.db.setPort(int(connInfo[2]))
        self.db.setUserName(connInfo[3])
        self.db.setPassword(connInfo[4])
        
    def openConnection(self):
        self.checkConnection = self.db.open()
        ####print self.checkConnection
        return self.checkConnection
    def getDataSourceInfo(self,findPattern):
        layers = []
        layerTmp = None
        #comboboxText = self.dockwidget.comboBox_databases.currentText().split(";")
        ####print comboboxText[0],comboboxText[1]
        for layer in QgsMapLayerRegistry.instance().mapLayers().values():
            if findPattern in layer.dataProvider().dataSourceUri(): #and comboboxText[0].split(":")[1] in layer.dataProvider().dataSourceUri() and comboboxText[1].split(":")[1] in layer.dataProvider().dataSourceUri():
                layers.append(layer)
        layerTmp = layers[len(layers)-1]   
        data= layerTmp.dataProvider().dataSourceUri().translate({ord('\''):None,ord('\"'):None}).split(" ")
        database = data[0].split('=')[1]
        host = data[1].split('=')[1]
        port = data[2].split('=')[1]
        user = data[3].split('=')[1]
        password = data[4].split('=')[1]
        
        return database,host,port,user,password
        
        
    def closeConnection(self):
        self.db.close()
    
    def executeQuery(self,str,prepareQuery = False):
        ###print "TESTCHECK",self.checkConnection
        if not self.checkConnection:
            return None
        
        query = QSqlQuery(self.db)
        if(prepareQuery):
            query.prepare(str)
            if(not query.exec_()):
                QMessageBox.warning(None,u"Ошибка в запросе",query.lastError().text())
        else:
            if(not query.exec_(str)):
                QMessageBox.warning(None,u"Ошибка в запросе",query.lastError().text())
        return query
    
        
        
        
#Класс рисования
class Draw(QgsMapToolEmitPoint,WorkWithTableAndPoints):
    triggerCommandAddPointRedo = pyqtSignal(QgsPoint)
    def __init__(self,dockwidget, canvas):
        self.canvas = canvas
        #self.clearTrash(self.canvas)
        self.dockwidget = dockwidget
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.undoStack = QUndoStack()
        #список точек
        self.points = []
        self.linePoints = []
        #Переменная отвечающая за проверку, начали ли мы рисовать
        
                #Инициализируем "рисовалку" и задаем ей параметры
        self.rubberBand = QgsRubberBand(self.canvas, QGis.Polygon)
        self.rubberBand.setColor(QColor(255,0,0,120))
        self.rubberBand.setWidth(1)
        self.rubberBand.setBrushStyle(Qt.CrossPattern)
        
        self.rubberBandBindingLine = QgsRubberBand(self.canvas,QGis.Line)
        self.rubberBandBindingLine.setColor(QColor(255,0,0,120))
        self.rubberBandBindingLine.setWidth(1)
        self.rubberBandBindingLine.setBrushStyle(Qt.CrossPattern)
        
        self.reset()
        
        #Инициализируем символ
        self.symbol = QgsMarkerSymbolV2()
        self.symbol.setSize(2)
        #Если не нужна точка при рисовании, то расскоментировать строку ниже
        self.symbol.setAlpha(0)
        
        #Инициализируем подпись расстояния
        self.labelDistance = QgsTextAnnotationItem(self.canvas)
        self.labelDistance.setMarkerSymbol(self.symbol)
        self.labelDistance.setFrameColor(QColor(255,0,0,0))
        self.labelDistance.setFrameBackgroundColor(QColor(255,0,0,0))
        
        #Инициализируем попись угла
        self.labelAngle = QgsTextAnnotationItem(self.canvas)
        self.labelAngle.setMarkerSymbol(self.symbol)
        self.labelAngle.setFrameColor(QColor(255,0,0,0))
        self.labelAngle.setFrameBackgroundColor(QColor(255,0,0,0))  
        
        self.length = 0.0
        self.angle = 0.0
        self.minutes = 0
        
        #Инициализируем магнит
        self.snapper = QgsMapCanvasSnapper(self.canvas)
        self.marker = None
        
        self.checkEndPoint = False
        self.magnet_angle_degrees = 0
        self.magnet_angle_minutes = 0
        
        self.magnet = 0.0
        
        self.db = DataBase(self.dockwidget)
        checkLayers = False
        for layer in QgsMapLayerRegistry.instance().mapLayers().values():
            if "\"public\".\"t_plot\"" in layer.dataProvider().dataSourceUri():
                self.db.setConnectionInfo()
                checkLayers = True
        self.oldValue = ""
        
        #Содаем сигнал для обновления стартовой точки
        self.triggerCommandAddPointRedo.connect(self.setNewStartPointSignal)
        
        self.plotGuid = ""
        self.nepGuid = ""
        self.number = None
        
        self.yearCutting = None
        
        self.equalAndNepPoints = [None,None]
        self.lastNepPointNumber = 0
        #self.triggerCommandAddPointUndo.connect(self.deleteRow)
    
    #!!!!!!
    def getNepGuid(self):
        return self.nepGuid
    def setNepGuid(self,guid):
        self.nepGuid=guid
        
    def getYearCutting(self):
        return self.yearCutting
        
    def setYearCutting(self,year):
        self.yearCutting = year
    
    def getNumber(self):
        return self.number
        
    def setNumber(self,number):
        self.number = number
    
    def getVertexMarker(self):
        return self.marker
    def getDb(self):
        return self.db
    def setDb(self,db):
        self.db = db
    def getLabelAngle(self):
        return self.labelAngle
    def getLabelDistance(self):
        return self.labelDistance
    
    def setGuidPlot(self,guid):
        self.plotGuid = guid
    def getGuidPlot(self):
        return self.plotGuid
    def getBindingRubber(self):
        return self.rubberBandBindingLine
    def setLinePoints(self,points):
        self.linePoints = list(points)
    
    def setPoints(self,points):
        self.points = list(points)
    
    def linePointAppend(self,point):
        self.linePoints.append(point)
    
    def getLinePoints(self):
        return self.linePoints
    
    def getTriggerStartPoint(self):
        return self.triggerCommandAddPointRedo
    
    def setMagnet(self,magnetAngle):
        self.magnet = magnetAngle
    def getMagnet(self):
        return self.magnet
    def getStartPoint(self):
        return self.startPoint
    def deletePoints(self,countPoints):
        del self.points[:countPoints]
    def getRubberBand(self):
        return self.rubberBand
    def initPointingDraw(self):
        marker = QgsVertexMarker(self.canvas)
        marker.setColor(QColor(0, 255, 0))
        marker.setIconSize(10)
        marker.setIconType(QgsVertexMarker.ICON_CROSS) # or ICON_CROSS, ICON_X
        marker.setPenWidth(3)
        
        return marker
        

    def drawBindingLine(self):
        self.rubberBandBindingLine.reset(QGis.Line)
        for point in self.linePoints:
            self.rubberBandBindingLine.addPoint(point,False)
        self.rubberBandBindingLine.show()
    
    def getBindingLine(self):
        return self.rubberBandBindingLine
    def setNewStartPointSignal(self,point):
        self.startPoint = point
             

    def reset(self):
      self.startPoint = self.endPoint = None
      self.isEmittingPoint = False
      self.rubberBand.reset(QGis.Polygon)
      self.rubberBandBindingLine.reset(QGis.Line)
    
    def calcAngleMinutes(self,length,angle,minutes,accuracy):
        length = round(length,1)
        minutes = round(((angle % 1)*60)/accuracy)*accuracy
        angle = int(angle)
        return length,angle,minutes

        
    def setSnapping(self,pixels):
        #Прилипание, задаем то, к какому слою (канвасу) будем применять прилипание.
        #Прилипать в фоновым слоям
        res, snapped=self.snapper.snapToBackgroundLayers(pixels)
        if (res!=0 or len(snapped)<1):
           # ###print snapped[1][0].snappedVertex
            return self.toMapCoordinates(pixels)
        else:
            snappedVertex = QgsPoint(snapped[0].snappedVertex)
            return snappedVertex
    
    def addPoint(self,point):
        self.points.append(point)
    
    #Устанавливаем параметры для подписей
    def setLabels(self,fontSize1,fontSize2,magnet=0.0,azimuth=True):
      
      distanceText = QTextDocument(str(round(self.length,2)) + 'm')
      distanceText.setDefaultFont(QFont("Times", fontSize1, QFont.Bold))
      self.labelDistance.setMapPosition(self.endPoint)
      self.labelDistance.setDocument(distanceText)
      self.labelDistance.setFrameSize(QSizeF(distanceText.size().width(),distanceText.size().height()))
      self.labelDistance.setFrameBorderWidth(0)
      
      angle = self.angle + self.minutes/60 -magnet
      if(angle<0):
        angle = 360+angle
      if angle>=360:
        angle=angle-360
      ####print angle
      minutes = round(((angle % 1)*60))
      angle = int(angle)
      
      if(azimuth):
        tmp=str(angle) + u'° '+str(minutes)+'\''
      else:
        tmp = self.azimuthToRumb(float(angle),float(minutes))
      angleText = QTextDocument(tmp)
      angleText.setDefaultFont(QFont("Times", fontSize2, QFont.Bold))
      self.labelAngle.setMapPosition(self.endPoint)
      self.labelAngle.setDocument(angleText)
      self.labelAngle.setFrameSize(QSizeF(angleText.size().width(),angleText.size().height()))
      self.labelAngle.setFrameBorderWidth(0)
      
      self.labelDistance.setOffsetFromReferencePoint(QPointF((distanceText.size().width()/2)*-1+30,-20))
      
      self.labelAngle.setOffsetFromReferencePoint(QPointF((angleText.size().width()/2)*-1+30,0))
    

    #Отрисовка полигона, если это не конец, то добавляем стартовую точку
    def drawPolygon(self,end):
        if(end!=True):
            self.points.append(self.startPoint)
        ##print "DRAW POLYGON", self.points
        self.showRect(self.points,self.endPoint)
    def resetDifference(self):
        self.dockwidget.lineEdit_difference_degrees.setText(u"0°0\'")
        self.dockwidget.lineEdit_difference_distance.setText("0.0")
        
    def resetCanvas(self,pointing=False):
        #self.reset()
        self.labelAngle.setDocument((QTextDocument("")))
        self.labelDistance.setDocument((QTextDocument("")))
        self.canvas.refresh()
        if pointing:
            if(self.marker != None):
                self.canvas.scene().removeItem(self.marker)
                self.marker = None
    def resetPolygons(self,pointing=False):
        self.reset()
        #del self.points[:]
        #del self.linePoints[:]
        self.resetCanvas(pointing)
    
    def resetAll(self,pointing=False):
        self.plotGuid = ""
        self.resetDockWidget()
        self.undoStack.clear()
        self.reset()
        self.points=[]
        self.linePoints=[]
        self.resetCanvas(pointing)
        self.dockwidget.tableWidget_points.setRowCount(0)
        self.resetDifference()
        self.equalAndNepPoints[0]=None
        self.equalAndNepPoints[1]=None
        self.lastNepPointNumber = 0
        self.dockwidget.checkBox_nep.setEnabled(True)
        self.db.closeConnection()
        
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.resetAll(True)
        if e.key() == Qt.Key_F4:
            self.undoStack.redo()
        if e.key() == Qt.Key_Z and e.modifiers() == Qt.ControlModifier:
            if len(self.undoStack)>0:
                self.undoStack.undo()
                
    def undoStackPush(self,command):
        self.undoStack.push(command)
    
    def findEqualPoint(self,point):
        equalsPoints = []
        if self.dockwidget.checkBox_nep.isChecked():
            equalPoints = False
            layerPoint = self.findLayerByPattern("table=\"public\".\"t_plot_point\"","type=Point")
            layerPlot = self.findLayerByPattern("table=\"public\".\"t_plot\"","type=Polygon")
            if layerPoint!=None:
                ##print "REDOCOMMANDADDPOINT SELFPOINTS[-1]", self.points[-1]
                request = QgsFeatureRequest().setFilterRect(QgsRectangle(point,point))#QgsPoint(self.points[-1].x(),self.points[-1].y()) QgsPoint(point.x()-,point.y()+50),QgsPoint(point.x()+50,point.y()-50)
                #print "request"
                plotFeature = None
                for f in layerPlot.getFeatures(request):
                    plotFeature=f
                    break
                #print "plotFeature",plotFeature['primarykey']
                #print "point",point.wellKnownText()
                #print "poly",plotFeature.geometry().exportToWkt()
                pointPlotFeature = None
                if plotFeature!=None:
                    #print "aga ya tut",plotFeature['primarykey'],point.wellKnownText()
                    
                    for featurePoint in layerPoint.getFeatures(QgsFeatureRequest(QgsExpression("plot_fk='"+plotFeature['primarykey']+"'"))):
                        
                        #print featurePoint.geometry().asPoint().wellKnownText()
                        if point == featurePoint.geometry().asPoint():
                            pointPlotFeature = featurePoint
                            #print "True"
                            break
                            
                if pointPlotFeature!=None:
                    return pointPlotFeature['number']
                else:
                    return None
            return None
    def canvasPressEvent(self, e):
        if (e.button() == 0x00000001 and e.modifiers() == Qt.ControlModifier) or (e.button() == 0x00000001 and e.modifiers() == Qt.NoModifier):
            #print "CANVASPRESSEVENTLEFTCLICK"
            #Очищаем лишнее перед рисованием (вдруг перед рисованием полигона, рисовали точку)
            if self.isEmittingPoint == False:
                self.resetAll(True)
                self.undoStack.clear()
            self.isEmittingPoint = True
            #Если последняя точка известна, то значит она же и будет следующей стартовой точкой
            #Если неизвестна, значит мы только начали рисовать
            if self.endPoint == None:
                if self.dockwidget.checkBox_snap.isChecked():
                    self.startPoint = self.setSnapping(e.pos())
                else:
                    self.startPoint = self.toMapCoordinates(e.pos())
            else:
                if self.dockwidget.checkBox_snap.isChecked():
                    self.endPoint = self.setSnapping(e.pos())
                self.startPoint = self.endPoint    
            #self.drawPolygon(False)
            ####print "pressEvent:",self.points
            self.resetDifference()
            self.dockwidget.tableWidget_points.blockSignals(True)
            azimuth = self.dockwidget.radioButton_azimuth.isChecked()
            tmpPoints = None
            if self.dockwidget.checkBox_nep.isChecked():
                #Номера нэп проставляются не обычным образом. если при рисовании НЭП, одни из точек попадает в точку t_plot_point, то мы должны записывать в таблице этот номер. Номера НЭП идет со штрихом. Пример ниже. Отсюда и проблема
                #нам нужно либо парсить таблицу и вытаскивать последний номер точки НЭП, который был со штрихом. Либо просто запоминать номер точки. Так как парсить таблицу это лишние действия, то я выбрал запоминать номер точки.
                #Но нам также нужен и номер совпадающей точки, чтобы корректно в таблицу внести номера. Поэтому чтобы не захломлять и без того захламленный параметрами класс CommandAddPoint, то мы просто передаем список из 2-х точек. Он нам также поможет, когда необходимо будет использовать сначала отмену действия, а потом возврат.
                #3-0'
                #0'-1'
                #1'-7
                #7-3'
                #3'-5
                #5-4'
                #4'-3
                #Но по мимо этой точки нам также необходим и номер точки t_plot_point 
                self.equalAndNepPoints[0]=self.equalAndNepPoints[1]
                self.equalAndNepPoints[1]=self.findEqualPoint(self.startPoint)
                if self.equalAndNepPoints[1] ==None:
                    self.equalAndNepPoints[1]=str(self.lastNepPointNumber)+"\'"
                    self.lastNepPointNumber = self.lastNepPointNumber+1
                #print "selfEqual",self.equalAndNepPoints
                

            addCommand = CommandAddPoint("addPoint",self.dockwidget.pushButton_deletePoint,self.dockwidget.lineEdit_difference_distance,self.dockwidget.lineEdit_difference_degrees,self.triggerCommandAddPointRedo,self.dockwidget.tableWidget_points,self.linePoints,self.points,self.rubberBand,self.startPoint,self.endPoint,False,self.length,self.angle,self.minutes,self.magnet,self.isEmittingPoint,self.dockwidget.radioButton_azimuth,self.dockwidget.checkBox_nep,self.equalAndNepPoints)
            self.undoStack.push(addCommand)
            self.dockwidget.tableWidget_points.blockSignals(False)
            ####print "addComand self.startPoint=",id(self.startPoint)
            ####print "addCommand (x;y) self.startPoint",self.startPoint
        if (e.button() == 0x00000002 and e.modifiers() == Qt.ControlModifier) or (e.button() == 0x00000002 and e.modifiers() == Qt.NoModifier):
            self.endPoint = None
            #Рисование точки        
            if self.isEmittingPoint == False:
                self.resetAll(True)
                self.undoStack.clear()
                if self.dockwidget.checkBox_snap.isChecked():
                    point = self.setSnapping(e.pos())
                else:
                    point = self.toMapCoordinates(e.pos())
                self.marker = self.initPointingDraw()
                self.marker.setCenter(point)
                self.points.append(point)
                ####print(self.guidPlot)
                ####print self.points
            #Конец рисования точки
            else:
                self.isEmittingPoint = False
                self.rubberBand.removePoint(-1)
                self.rubberBand.addPoint(self.points[-1])
                if(not self.db.openConnection()):
                    self.db.setConnectionInfo()
                    self.db.openConnection()
                self.undoStack.clear()
                if not self.dockwidget.checkBox_nep.isChecked():
                    guid = self.addInDatabase(self.dockwidget,self.linePoints,self.points,self.rubberBandBindingLine,self.rubberBand,self.db,self.magnet)
                    self.plotGuid = guid
                else:
                    guid = self.addNepInDatabase(self.dockwidget,self.linePoints,self.points,self.rubberBandBindingLine,self.rubberBand,self.db,self.magnet)
                    self.nepGuid = guid
                self.db.closeConnection()
                self.resetPolygons()
                
                ####print self.points
               # ###print self.getPoints()
          
    def canvasReleaseEvent(self, e):
        return

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint and (self.startPoint==None or self.endPoint==None):
            return
        self.endPoint = self.toMapCoordinates(e.pos())
        seg = QgsFeature()
        points = [self.startPoint,self.endPoint]
        seg.setGeometry(QgsGeometry.fromPolyline(points))
        #Вычисляем длину между точками
        self.length = seg.geometry().length()
        #Вычисляем азимут между точками
        self.angle = QgsPoint.azimuth(self.startPoint,self.endPoint)
        #Переводим полкруговой угол в круговой
        if(self.angle<0):
            self.angle = 360+self.angle
        #Получаем минуты угла и округляем до 2 знаков
        self.minutes = round(((self.angle % 1)*60))
        #Если зажали CTRL то округляем значения
        if e.modifiers() == Qt.ControlModifier:
            self.length,self.angle,self.minutes = self.calcAngleMinutes(self.length,self.angle,self.minutes,10)
            #Вычисляем местоположение новой точки
            self.endPoint = QgsPoint(self.startPoint.x()+self.length*(sin(radians(self.angle+self.minutes/60))),self.startPoint.y()+self.length*(cos(radians(self.angle+self.minutes/60))))
        # if self.dockwidget.checkBox_snap.isChecked():
            # self.endPoint = self.setSnapping(e.pos())
        self.angle = int(self.angle)
        ##print "len(self.points)",len(self.points)
        self.showMoveRect(self.points,self.endPoint)
        self.setLabels(10,10,self.magnet,self.dockwidget.radioButton_azimuth.isChecked())
        ####print "moveEvent"
        
    def showRect(self,points,endPoint):
        self.rubberBand.reset(QGis.Polygon)
        for point in self.points:
            self.rubberBand.addPoint(point,False)
        if(endPoint!=None):
            self.rubberBand.addPoint(endPoint,True)
        self.rubberBand.show()
    
        
    #Для отрисовки в движении, чтобы не приходилось по новой с 0 рисовать полигон, как это сделано в showRect
    def showMoveRect(self,points,endPoint):
        if(endPoint != None and len(points)>0):
            if(points[-1]==endPoint):
                self.rubberBand.addPoint(endPoint,True)
            else:
                self.rubberBand.removePoint(-1)
                self.rubberBand.addPoint(endPoint,True)
        #Необходима, чтобы при рисовании не мерцал полигон. Для наглядности, можно закоментить
        self.rubberBand.show()
    
    def resetDockWidget(self):
        self.dockwidget.lineEdit_yearOfCutting.setText(None)
        self.dockwidget.lineEdit_areaPlot.setText(None)
        self.dockwidget.lineEdit_numberPlot.setText(None)
        
    
    
    def getPoints(self):
        return self.points
        
    def getUndoStack(self):
        return self.undoStack
    
    def setPoint(self,startPoint=None,endPoint=None):
        if startPoint!=None:
            self.startPoint = startPoint
        if endPoint != None:
            self.endPoint = endPoint

    def getEmitingPoint(self):
        return self.isEmittingPoint
    def deactivate(self):
        return
        



        
class Plots(WorkWithTableAndPoints):
    """QGIS Plugin Implementation."""
    updatePointsTrigger = pyqtSignal()
    def __init__(self, iface):
        """Constructor.
        
        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgisInterface
        """

        # Save reference to the QGIS interface
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'Plots_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'Plots')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'Plots')
        self.toolbar.setObjectName(u'Plots')

        ####print "** INITIALIZING Plots"

        self.pluginIsActive = False
        self.dockwidget = None
        
        self.db = None
        
        self.indexCombobox = 0
        self.qgisProject = QgsMapLayerRegistry.instance()
        self.errors = []
        
        self.magnet = 0.0
        self.prevMagnet = 0.0
        
        self.points = None
        self.checkEndPoint = False
        self.checkEditCell = False
        self.checkChangeFormatCell=False
        
        self.oldValue = ""
        
        self.currentRow = 0
        self.currentColumn = 0
        self.cellText = ""
        
        self.bindingLineRow = -1
        self.oldBindingLineRow = -1
        
        self.prevNumber = ""
        self.lastLength = ""
        self.lastAngle = ""
        #self.workWithTableAndPoints = None 
        self.checkLayer = False
    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('Plots', message)


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

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
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

        icon_path = ':/plugins/Plots/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Draw plots'),
            callback=self.run,
            parent=self.iface.mainWindow())

    #--------------------------------------------------------------------------
            
    
    def cellChange(self,row,column):
        if column == 1:
            ##print "et checkBox",row
            if row<self.dockwidget.tableWidget_points.rowCount()-3:
                if(self.dockwidget.tableWidget_points.item(row,1).checkState()==Qt.Checked):
                    self.oldBindingLineRow = self.bindingLineRow
                    addCommand = None
                    if not self.dockwidget.checkBox_nep.isChecked():
                        addCommand = CommandAddBindingLine("add bindingLine",self.dockwidget.tableWidget_points,row,self.tool_draw.getMagnet(),self.tool_draw,self.dockwidget.radioButton_azimuth.isChecked(),self.tool_draw.getGuidPlot(),self.db,self.dockwidget)
                    else:
                        addCommand = CommandAddBindingLine("add bindingLine",self.dockwidget.tableWidget_points,row,self.tool_draw.getMagnet(),self.tool_draw,self.dockwidget.radioButton_azimuth.isChecked(),self.tool_draw.getNepGuid(),self.db,self.dockwidget)
                    self.tool_draw.undoStackPush(addCommand)
                    ###print "stack:",len(self.tool_draw.getUndoStack())
                    ####print("afterallredoundo:",self.oldBindingLineRow,self.bindingLineRow)
                else:
                    deleteCommand = None
                    if not self.dockwidget.checkBox_nep.isChecked():
                        deleteCommand = deleteCommand = CommandDeleteBindingLine("add bindingLine",self.dockwidget.tableWidget_points,row,self.bindingLineRow,self.tool_draw.getMagnet(),self.tool_draw,self.dockwidget.radioButton_azimuth.isChecked(),self.tool_draw.getGuidPlot(),self.db,self.dockwidget)
                    else:
                        deleteCommand = CommandDeleteBindingLine("add bindingLine",self.dockwidget.tableWidget_points,row,self.bindingLineRow,self.tool_draw.getMagnet(),self.tool_draw,self.dockwidget.radioButton_azimuth.isChecked(),self.tool_draw.getNepGuid(),self.db,self.dockwidget)
                    self.tool_draw.undoStackPush(deleteCommand)
            else:
                self.dockwidget.tableWidget_points.item(row,1).setCheckState(False)
                
                
    def addRecord(self):
        ###print("addRecord",self.tool_draw.getGuidPlot())
        self.dockwidget.tableWidget_points.blockSignals(True)
        addCommand = CommandAddManualPoint("manual add point",self.dockwidget.tableWidget_points,self.dockwidget.lineEdit_difference_distance,self.dockwidget.lineEdit_difference_degrees,self.tool_draw.getMagnet(),self.tool_draw,self.dockwidget.radioButton_azimuth,self.tool_draw.getGuidPlot(),self.db,self.dockwidget.checkBox_nep)
        self.tool_draw.undoStackPush(addCommand)
        self.dockwidget.checkBox_nep.setEnabled(False)
        self.dockwidget.tableWidget_points.blockSignals(False)
           
    
    def calculateRealLengthAndAngle(self,row):
        seg = QgsFeature()
        points = [self.points[row-1],self.points[row]]
        seg.setGeometry(QgsGeometry.fromPolyline(points))
        angle = QgsPoint.azimuth(self.points[row-1],self.points[row])
        if(angle<0):
            angle = 360+angle
        self.dockwidget.tableWidget_points.item(row-1,2).setText(str(round(seg.geometry().length(),1)))
        self.dockwidget.tableWidget_points.item(row-1,3).setText(str(round(angle,2)))
    
    def btnClickDelete(self):
        self.points = self.tool_draw.getPoints()
        deletePoints = None
        if not self.dockwidget.checkBox_nep.isChecked():
            deletePoints = CommandDeletePoint("delete points",self.dockwidget.tableWidget_points,self.points,self.tool_draw.getRubberBand(),self.tool_draw.getStartPoint(),None,self.tool_draw.getTriggerStartPoint(),self.tool_draw.getMagnet(),self.tool_draw,self.dockwidget.radioButton_azimuth.isChecked(),self.tool_draw.getGuidPlot(),self.db,self.dockwidget)
        else:
            deletePoints = CommandDeletePoint("delete points",self.dockwidget.tableWidget_points,self.points,self.tool_draw.getRubberBand(),self.tool_draw.getStartPoint(),None,self.tool_draw.getTriggerStartPoint(),self.tool_draw.getMagnet(),self.tool_draw,self.dockwidget.radioButton_azimuth.isChecked(),self.tool_draw.getNepGuid(),self.db,self.dockwidget)
        #print "nepGUID",self.tool_draw.getNepGuid()
        self.tool_draw.undoStackPush(deletePoints)
        
    

    def finishedEdit(self):
        ####print "finish",self.currentRow<self.dockwidget.tableWidget_points.rowCount()-1," ",self.currentColumn," ",self.currentRow
        ####print self.tool_draw.getStartPoint()
        if (self.currentRow<self.dockwidget.tableWidget_points.rowCount()-1 or self.dockwidget.tableWidget_points.rowCount()==1) and (self.currentColumn==3 or self.currentColumn==2):
            ####print "finished cell: ",self.dockwidget.tableWidget_points.cellWidget(self.currentRow,self.currentColumn).text()
            self.cellText = self.dockwidget.tableWidget_points.cellWidget(self.currentRow,self.currentColumn).text()
            self.dockwidget.tableWidget_points.removeCellWidget(self.currentRow,self.currentColumn)
            if self.currentColumn==3:
                tmp =  self.cellText.split('.')
                if len(tmp)>1:
                    if len(tmp[1])==1 and tmp[1][0]!='0':
                        tmp[1]=tmp[1]+'0'
                    self.cellText = tmp[0]+u'°'+tmp[1]+'\''
                else:
                    self.cellText = tmp[0]+u'°'+"0\'"
                
                ####print "finishedEdit","updatePoint1"
                ####print self.tool_draw.getStartPoint()
                updatePointCommand = None
                #print "finishedEdit","tyt"
                if not self.dockwidget.checkBox_nep.isChecked():
                    #print "tut1"
                    updatePointCommand = CommandUpdatePoint("updatePoint",self.dockwidget.tableWidget_points,self.currentRow,self.currentColumn,self.cellText,self.oldValue,self.tool_draw.getPoints(),self.tool_draw.getRubberBand(),self.tool_draw.getStartPoint(),self.tool_draw.getStartPoint(),self.tool_draw.getMagnet(),self.tool_draw,self.dockwidget.radioButton_azimuth.isChecked(),self.tool_draw.getGuidPlot(),self.db,self.dockwidget)
                else:
                    #print "tut2"
                    updatePointCommand = CommandUpdatePoint("updatePoint",self.dockwidget.tableWidget_points,self.currentRow,self.currentColumn,self.cellText,self.oldValue,self.tool_draw.getPoints(),self.tool_draw.getRubberBand(),self.tool_draw.getStartPoint(),self.tool_draw.getStartPoint(),self.tool_draw.getMagnet(),self.tool_draw,self.dockwidget.radioButton_azimuth.isChecked(),self.tool_draw.getNepGuid(),self.db,self.dockwidget)
                
                self.tool_draw.undoStackPush(updatePointCommand)
                ####print self.tool_draw.getRubberBand().numberOfVertices()
                #self.dockwidget.tableWidget_points.item(self.currentRow,self.currentColumn).setText(self.cellText)
            elif  self.currentColumn==2:
                updatePointCommand = None
                if not self.dockwidget.checkBox_nep.isChecked():
                    updatePointCommand = CommandUpdatePoint("updatePoint",self.dockwidget.tableWidget_points,self.currentRow,self.currentColumn,self.cellText,self.oldValue,self.tool_draw.getPoints(),self.tool_draw.getRubberBand(),self.tool_draw.getStartPoint(),self.tool_draw.getStartPoint(),self.tool_draw.getMagnet(),self.tool_draw,self.dockwidget.radioButton_azimuth.isChecked(),self.tool_draw.getGuidPlot(),self.db,self.dockwidget)
                else:
                    updatePointCommand = CommandUpdatePoint("updatePoint",self.dockwidget.tableWidget_points,self.currentRow,self.currentColumn,self.cellText,self.oldValue,self.tool_draw.getPoints(),self.tool_draw.getRubberBand(),self.tool_draw.getStartPoint(),self.tool_draw.getStartPoint(),self.tool_draw.getMagnet(),self.tool_draw,self.dockwidget.radioButton_azimuth.isChecked(),self.tool_draw.getNepGuid(),self.db,self.dockwidget)
                self.tool_draw.undoStackPush(updatePointCommand)
        elif (self.currentRow==self.dockwidget.tableWidget_points.rowCount()-1 and (self.currentColumn==3 or self.currentColumn==2)):
            self.dockwidget.tableWidget_points.cellWidget(self.currentRow,self.currentColumn).blockSignals(True)
            self.cellText = self.dockwidget.tableWidget_points.cellWidget(self.currentRow,self.currentColumn).text()
            if not self.dockwidget.checkBox_nep.isChecked():
                updateLastPointCommand = CommandUpdateLastPoint("updateLastPoint",self.dockwidget,self.currentRow,self.currentColumn,self.cellText,[self.tool_draw.getPoints()[-1],self.tool_draw.getPoints()[0]],self.tool_draw.getMagnet(),self.db,self.tool_draw.getGuidPlot())
            else:
                updateLastPointCommand = CommandUpdateLastPoint("updateLastPoint",self.dockwidget,self.currentRow,self.currentColumn,self.cellText,[self.tool_draw.getPoints()[-1],self.tool_draw.getPoints()[0]],self.tool_draw.getMagnet(),self.db,self.tool_draw.getNepGuid())
            self.tool_draw.undoStackPush(updateLastPointCommand)
            self.dockwidget.tableWidget_points.cellWidget(self.currentRow,self.currentColumn).blockSignals(False)
            self.dockwidget.tableWidget_points.removeCellWidget(self.currentRow,self.currentColumn)
            
            
        ##self.dockwidget.tableWidget_points.setItem(0,3,QTableWidgetItem("test"))
        

    def itAc(self,item):
        tmp = ""
        ###print tmp
    def resetDockWidget(self):
        self.dockwidget.lineEdit_yearOfCutting.setText(None)
        self.dockwidget.lineEdit_areaPlot.setText(None)
        self.dockwidget.lineEdit_numberPlot.setText(None)
    

    
    def pushButtonDrawClicked(self):
        # ###print "draw"
        # ###print self.dockwidget.lineEdit_yearOfCutting.text()
        if(not self.db.openConnection()):
            self.db.setConnectionInfo()
            self.db.openConnection()
        self.tool_draw.getUndoStack().clear()
        self.tool_draw.showRect(self.tool_draw.getStartPoint(),None)
        if not self.dockwidget.checkBox_nep.isChecked():
            guid = self.addInDatabase(self.dockwidget,self.tool_draw.getLinePoints(),self.tool_draw.getPoints(),self.tool_draw.getBindingRubber(),self.tool_draw.getRubberBand(),self.db,self.tool_draw.getMagnet())
            self.tool_draw.setGuidPlot(guid)
        else:
            guid = self.addNepInDatabase(self.dockwidget,self.tool_draw.getLinePoints(),self.tool_draw.getPoints(),self.tool_draw.getBindingRubber(),self.tool_draw.getRubberBand(),self.db,self.tool_draw.getMagnet())
            self.tool_draw.setNepGuid(guid)
        self.db.closeConnection()
        self.tool_draw.resetPolygons()
    
    def loadPlot(self,layer):
        if(not self.db.openConnection()):
            self.db.setConnectionInfo()
            self.db.openConnection()
        selectGuid = ""
        area = ""
        yearOfCutting = ""
        magnet = None
        plotNumber = ""
        for feature in layer.selectedFeatures():
            selectGuid = str(feature['primarykey'])
            area = str(feature["area_common"])
            if(str(feature['yearofcutting'])!="NULL"):
                yearOfCutting = str(feature['yearofcutting'])
            if(str(feature['mangle'])!="NULL"):
                magnet = feature['mangle']
            if(str(feature['number'])!="NULL"):
                plotNumber = str(feature['number'])
            break
        if selectGuid:
            rowCount = self.dockwidget.tableWidget_points.rowCount()
            self.dockwidget.tableWidget_points.blockSignals(True)
            linePoints = []
            points = []
            query = self.db.executeQuery("select st_x(shape),st_y(shape) from t_plot_point where plot_fk = '"+selectGuid+"' and type_object='5b8e90b5-df13-46b6-bf55-59146110dc28' order by \"number\"")
            while(query.next()):
                linePoints.append(QgsPoint(float(query.value(0)),float(query.value(1)))) 
            query = self.db.executeQuery("select st_x(shape),st_y(shape) from t_plot_point where plot_fk = '"+selectGuid+"' and type_object='b6dcbdf5-0c43-4cbd-8742-166d59b89504' order by \"number\"")
            while(query.next()):
                points.append(QgsPoint(float(query.value(0)),float(query.value(1))))
            query = self.db.executeQuery("select number,distance,rumb,type from t_rumbs where plot = '"+selectGuid+"' order by (regexp_split_to_array(number,'-'))[1]::integer")
            while(query.next()):
                number = str(query.value(0))
                length = str(query.value(1))
                angle = str(query.value(2))
                angle = angle.replace(u'`',u'\'')
                checkBoxItem = QTableWidgetItem()
                if(rowCount==len(linePoints)-2):
                    checkBoxItem.setCheckState(Qt.Checked)
                else:
                    checkBoxItem.setCheckState(Qt.Unchecked)
                self.dockwidget.tableWidget_points.insertRow(rowCount)
                self.dockwidget.tableWidget_points.setItem(rowCount,0,QTableWidgetItem(number))
                self.dockwidget.tableWidget_points.setItem(rowCount,1,checkBoxItem)
                self.dockwidget.tableWidget_points.setItem(rowCount,2,QTableWidgetItem(length))
                if(self.dockwidget.radioButton_azimuth.isChecked()):
                    angle=self.rumbToAzimuth(angle)
                ##print "LoadSelected:",number,length,angle
                self.dockwidget.tableWidget_points.setItem(rowCount,3,QTableWidgetItem(angle))
                # if(azimuth):
                    # self.dockwidget.tableWidget_points.setItem(rowCount,3,QTableWidgetItem(angle)
                # else:
                    # self.dockwidget.tableWidget_points.setItem(rowCount,3,QTableWidgetItem(self.azimuthToRumb(float(angle),float(minutes))))
                rowCount=rowCount+1
            self.tool_draw.setPoints(points)  
            self.tool_draw.setLinePoints(linePoints)
            self.tool_draw.setGuidPlot(selectGuid)
            ####print("points:",self.tool_draw.getPoints())
            self.dockwidget.tableWidget_points.blockSignals(False)
            self.dockwidget.lineEdit_areaPlot.setText(area)
            self.dockwidget.lineEdit_yearOfCutting.setText(yearOfCutting)
            self.dockwidget.lineEdit_numberPlot.setText(plotNumber)
            if(magnet!=None):
                self.dockwidget.lineEdit_magDeclin_degrees.setText(str(int(magnet)))
                if(abs(magnet)%1 != 0):
                    ###print "LOADMAGNET:",abs(magnet)%1
                    self.dockwidget.lineEdit_magDeclin_minutes.setText(str(int(round((abs(magnet)%1)*60))))
            else:
                magnet = 0.0
            self.tool_draw.setMagnet(magnet)
            self.tool_draw.setYearCutting(yearOfCutting)
            self.tool_draw.setNumber(plotNumber)
            
            lastRow = self.dockwidget.tableWidget_points.rowCount()-1
            
            
            seg = QgsFeature()
            seg.setGeometry(QgsGeometry.fromPolyline([points[-1],points[0]]))
            angle = QgsPoint.azimuth(points[-1],points[0])-magnet
            if(angle<0):
                angle = 360+angle
            if angle>=360:
                angle=angle-360
            minutes = round(((angle % 1)*60)) 
            
            trueLength = round(seg.geometry().length(),1)
            trueAngle = int(angle)
            trueMinutes = int(minutes)
            
            
            tableLength = float(self.dockwidget.tableWidget_points.item(lastRow,2).text())
            if self.dockwidget.radioButton_azimuth.isChecked():
                tableAngle,tableMinutes = self.dockwidget.tableWidget_points.item(lastRow,3).text().replace('\'','').split(u'°')
                tableAngle = int(tableAngle)
                tableMinutes = int(tableMinutes)
            else:
                tableAngle,tableMinutes = self.dockwidget.tableWidget_points.item(lastRow,3).text().replace('\'','').split(' ')[1].split(u'°')
                tableAngle = int(tableAngle)
                tableMinutes = int(tableMinutes)
            deltaLength = abs(tableLength-trueLength)
            deltaAngle = abs(trueAngle-tableAngle)
            deltaMinutes = abs(trueMinutes-tableMinutes)
            self.dockwidget.lineEdit_difference_distance.setText(str(deltaLength))
            self.dockwidget.lineEdit_difference_degrees.setText(str(deltaAngle)+u'°'+str(deltaMinutes)+u'\'')
        self.db.closeConnection()
    
    def loadNep(self,layer):
        if(not self.db.openConnection()):
            self.db.setConnectionInfo()
            self.db.openConnection()
        selectGuid = ""
        area = ""
        yearOfCutting = ""
        magnet = None
        nepNumber = ""
        for feature in layer.selectedFeatures():
            selectGuid = str(feature['primarykey'])
            area = str(feature["area"])
            if(str(feature['mangle'])!="NULL"):
                magnet = feature['mangle']
            if(str(feature['number'])!="NULL"):
                nepNumber = str(feature['number'])
            break
        if selectGuid:
            rowCount = self.dockwidget.tableWidget_points.rowCount()
            self.dockwidget.tableWidget_points.blockSignals(True)
            linePoints = []
            points = []
            query = self.db.executeQuery("select st_x(shape),st_y(shape) from t_noa_point where noa = '"+selectGuid+"' and type_object='5b8e90b5-df13-46b6-bf55-59146110dc28' order by \"order\"")
            while(query.next()):
                linePoints.append(QgsPoint(float(query.value(0)),float(query.value(1)))) 
            query = self.db.executeQuery("select st_x(shape),st_y(shape) from t_noa_point where noa = '"+selectGuid+"' and type_object='b6dcbdf5-0c43-4cbd-8742-166d59b89504' order by \"order\"")
            while(query.next()):
                points.append(QgsPoint(float(query.value(0)),float(query.value(1))))
            #number,distance,rumb,type
            query = self.db.executeQuery("select t_noa_rumbs.number,t_noa_rumbs.distance,t_noa_rumbs.rumb,t_noa_rumbs.type from t_noa_rumbs inner join t_noa_point on ((regexp_split_to_array(t_noa_rumbs.number,'-'))[1]::varchar)=t_noa_point.number and t_noa_rumbs.noa = t_noa_point.noa and t_noa_point.type_object = t_noa_rumbs.type  where t_noa_rumbs.noa = '"+selectGuid+"' order by \"order\"")
            while(query.next()):
                number = str(query.value(0))
                length = str(query.value(1))
                angle = str(query.value(2))
                number = number.replace(u'`',u'\'')
                angle = angle.replace(u'`',u'\'')
                checkBoxItem = QTableWidgetItem()
                if(rowCount==len(linePoints)-2):
                    checkBoxItem.setCheckState(Qt.Checked)
                else:
                    checkBoxItem.setCheckState(Qt.Unchecked)
                self.dockwidget.tableWidget_points.insertRow(rowCount)
                self.dockwidget.tableWidget_points.setItem(rowCount,0,QTableWidgetItem(number))
                self.dockwidget.tableWidget_points.setItem(rowCount,1,checkBoxItem)
                self.dockwidget.tableWidget_points.setItem(rowCount,2,QTableWidgetItem(length))
                if(self.dockwidget.radioButton_azimuth.isChecked()):
                    angle=self.rumbToAzimuth(angle)
                ##print "LoadSelected:",number,length,angle
                self.dockwidget.tableWidget_points.setItem(rowCount,3,QTableWidgetItem(angle))
                # if(azimuth):
                    # self.dockwidget.tableWidget_points.setItem(rowCount,3,QTableWidgetItem(angle)
                # else:
                    # self.dockwidget.tableWidget_points.setItem(rowCount,3,QTableWidgetItem(self.azimuthToRumb(float(angle),float(minutes))))
                rowCount=rowCount+1
            self.tool_draw.setPoints(points)  
            self.tool_draw.setLinePoints(linePoints)
            self.tool_draw.setNepGuid(selectGuid)
            ####print("points:",self.tool_draw.getPoints())
            self.dockwidget.tableWidget_points.blockSignals(False)
            self.dockwidget.lineEdit_areaPlot.setText(area)
            self.dockwidget.lineEdit_numberPlot.setText(nepNumber)
            if(magnet!=None):
                self.dockwidget.lineEdit_magDeclin_degrees.setText(str(int(magnet)))
                if(abs(magnet)%1 != 0):
                    ###print "LOADMAGNET:",abs(magnet)%1
                    self.dockwidget.lineEdit_magDeclin_minutes.setText(str(int(round((abs(magnet)%1)*60))))
            else:
                magnet = 0.0
            self.tool_draw.setMagnet(magnet)
            self.tool_draw.setNumber(nepNumber)
            
            lastRow = self.dockwidget.tableWidget_points.rowCount()-1
            
            
            seg = QgsFeature()
            seg.setGeometry(QgsGeometry.fromPolyline([points[-1],points[0]]))
            angle = QgsPoint.azimuth(points[-1],points[0])-magnet
            if(angle<0):
                angle = 360+angle
            if angle>=360:
                angle=angle-360
            minutes = round(((angle % 1)*60)) 
            
            trueLength = round(seg.geometry().length(),1)
            trueAngle = int(angle)
            trueMinutes = int(minutes)
            
            
            tableLength = float(self.dockwidget.tableWidget_points.item(lastRow,2).text())
            if self.dockwidget.radioButton_azimuth.isChecked():
                tableAngle,tableMinutes = self.dockwidget.tableWidget_points.item(lastRow,3).text().replace('\'','').split(u'°')
                tableAngle = int(tableAngle)
                tableMinutes = int(tableMinutes)
            else:
                tableAngle,tableMinutes = self.dockwidget.tableWidget_points.item(lastRow,3).text().replace('\'','').split(' ')[1].split(u'°')
                tableAngle = int(tableAngle)
                tableMinutes = int(tableMinutes)
            deltaLength = abs(tableLength-trueLength)
            deltaAngle = abs(trueAngle-tableAngle)
            deltaMinutes = abs(trueMinutes-tableMinutes)
            self.dockwidget.lineEdit_difference_distance.setText(str(deltaLength))
            self.dockwidget.lineEdit_difference_degrees.setText(str(deltaAngle)+u'°'+str(deltaMinutes)+u'\'')
            self.dockwidget.checkBox_nep.setChecked(True)
        self.db.closeConnection()
   
    def loadSelected(self):
        self.tool_draw.resetAll()
        layer = self.iface.activeLayer()
        if ("\"public\".\"t_plot\"") in layer.source():
            self.loadPlot(layer)
        elif ("\"public\".\"t_non_operational_area\"") in layer.source():
            self.loadNep(layer)
            
    def cellEdit(self,row,column):
        self.checkEditCell=True
        if (row<self.dockwidget.tableWidget_points.rowCount() or self.dockwidget.tableWidget_points.rowCount()==1) and (column==3 or column==2):
            self.currentRow = row
            self.currentColumn = column
            self.cellText = self.dockwidget.tableWidget_points.item(row,column).text()
            self.oldValue = self.cellText
            if column==3:
                if u'°' in self.cellText:
                    tmpSplitString = self.cellText.split(u'°')
                    if tmpSplitString[1]:
                        tmp = tmpSplitString[1].split('\'')[0]
                        if len(tmp)==1 and tmp!='0':
                            tmp='0'+tmp
                        self.cellText = tmpSplitString[0]+'.'+tmp
                    else:
                        ##print "CELL EDIT: False",tmpSplitString
                        self.cellText = tmpSplitString[0]
                tmp = QLineEdit()
                tmp.setText(self.cellText)
                tmp.editingFinished.connect(self.finishedEdit)
                if(self.dockwidget.radioButton_azimuth.isChecked()):
                    tmp.setValidator(QRegExpValidator(QRegExp("^([0-9]|[1-8][0-9]|9[0-9]|[12][0-9]{2}|3[0-4][0-9]|35[0-9])(\.{1}[0-5]|\.{1}[0-5][0-9]){0,1}$")))
                else:
                    tmp.setValidator(QRegExpValidator(QRegExp(u"^((С|В|З|Ю)\s(0|0\.0))|((СВ|СЗ|ЮВ|ЮЗ)\s((0|00)\.([0-9]|[0-5][0-9])))|(СВ|СЗ|ЮВ|ЮЗ)\s([1-9]|[0-8][0-9])(\.([0-9]|[0-5][0-9])|())$")))
                self.dockwidget.tableWidget_points.setCellWidget(row,column,tmp)
            elif column==2:
                tmp = QLineEdit()
                tmp.setText(self.cellText)
                tmp.editingFinished.connect(self.finishedEdit)
                tmp.setValidator(QRegExpValidator(QRegExp("^(\d{1,})(\.{1}\d){0,1}$")))
                self.dockwidget.tableWidget_points.setCellWidget(row,column,tmp)

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        ####print "** CLOSING Plots"

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False
        self.resetDockWidget()
        self.qgisProject.legendLayersAdded.disconnect(self.onAddLayer)
        self.qgisProject.layersRemoved.disconnect(self.onRemoveLayer)
        self.tool_draw.resetAll()
        if(self.canvas.mapTool()==self.tool_draw):
            self.iface.actionPan().trigger()
        del self.tool_draw
        self.dockwidget = None
    

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        ####print "** UNLOAD Plots"
        #self.qgisProject.legendLayersAdded.disconnect(self.onAddLayer)
        #self.qgisProject.layersRemoved.disconnect(self.onRemoveLayer)
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'Plots'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------
    
    def clearTrashClicked(self):
   
        annotationItems = []
        rubberBands = []
        vertexMarkers = []
        
        for i in iface.mapCanvas().scene().items():
            if i.data(0) == 'AnnotationItem':
            # if issubclass(type(i), qgis.gui.QgsTextAnnotationItem):
                annotationItems.append(i)
            if issubclass(type(i), QgsRubberBand):
                rubberBands.append(i)
            if issubclass(type(i), QgsVertexMarker):
                vertexMarkers.append(i)  
                
        for item in annotationItems:
            #if item in iface.mapCanvas().scene().items():
            if not (item==self.tool_draw.getLabelDistance() or item==self.tool_draw.getLabelAngle()):
                iface.mapCanvas().scene().removeItem(item)
            # iface.mapCanvas().scene().removeItem(item)
        
        for marks in vertexMarkers:
            # if marks in iface.mapCanvas().scene().items():
            if not (marks==self.tool_draw.getVertexMarker()):
                iface.mapCanvas().scene().removeItem(marks) 
                
        for band in rubberBands:
            # if band in iface.mapCanvas().scene().items():
            if not (band==self.tool_draw.getRubberBand() or band==self.tool_draw.getBindingRubber()):
                iface.mapCanvas().scene().removeItem(band) 
        # iface.mapCanvas().refresh()
                    
    
    def azimuthSelect(self,check):
        for i in range(self.dockwidget.tableWidget_points.rowCount()):
            
            angle = self.dockwidget.tableWidget_points.item(i,3).text()
            if(check):
                self.dockwidget.tableWidget_points.item(i,3).setText(self.rumbToAzimuth(angle))
            else:
                tmpSplit = angle.split(u'°')
                minutes = float(tmpSplit[1].replace('\'',''))
                angle = float(tmpSplit[0])
                angle = self.azimuthToRumb(angle,minutes)
                self.dockwidget.tableWidget_points.item(i,3).setText(angle)
    
    def run(self):
        """Run method that loads and starts the plugin"""

        
        if not self.pluginIsActive:
            self.pluginIsActive = True
            
            ####print "** STARTING Plots"

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = PlotsDockWidget()
                self.qgisProject.legendLayersAdded.connect(self.onAddLayer)
                self.qgisProject.layersRemoved.connect(self.onRemoveLayer)
                self.dockwidget.pushButton_addPoint.clicked.connect(self.addRecord)
                self.dockwidget.tableWidget_points.cellDoubleClicked.connect(self.cellEdit)
                self.dockwidget.tableWidget_points.cellChanged.connect(self.cellChange)
                #self.dockwidget.tableWidget_points.itemDoubleClicked.connect(self.itAc)
                self.dockwidget.pushButton_deletePoint.clicked.connect(self.btnClickDelete)
                #self.dockwidget.lineEdit_yearOfCutting.setValidator(QRegExpValidator(QRegExp(u"^((С|В|З|Ю)\s0)|((СВ|СЗ|ЮВ|ЮЗ)\s((0|00)\.([0-9]|[0-5][0-9])))|(СВ|СЗ|ЮВ|ЮЗ)\s([1-9]|[0-8][0-9])(\.([0-9]|[0-5][0-9])|())$")))
                self.dockwidget.lineEdit_magDeclin_degrees.setValidator(QIntValidator(-3600, 360))
                self.dockwidget.lineEdit_magDeclin_minutes.setValidator(QIntValidator(0, 60))
                self.dockwidget.lineEdit_numberPlot.setValidator(QIntValidator(1,999))
                self.dockwidget.lineEdit_yearOfCutting.setValidator(QIntValidator(1,9999))
                self.dockwidget.lineEdit_magDeclin_degrees.textChanged.connect(self.magnetChange)
                self.dockwidget.lineEdit_magDeclin_minutes.textChanged.connect(self.magnetChange)
                self.dockwidget.lineEdit_magDeclin_degrees.editingFinished.connect(self.finishEditMagnet)
                self.dockwidget.lineEdit_magDeclin_minutes.editingFinished.connect(self.finishEditMagnet)
                self.dockwidget.lineEdit_numberPlot.editingFinished.connect(self.finishedEditNumber)
                self.dockwidget.lineEdit_yearOfCutting.editingFinished.connect(self.finishedEditYearOfCutting)
                self.dockwidget.pushButton_draw.clicked.connect(self.pushButtonDrawClicked)
                self.dockwidget.radioButton_azimuth.toggled.connect(self.azimuthSelect)
                self.dockwidget.pushButton_loadPlot.clicked.connect(self.loadSelected)
                self.dockwidget.pushButton_clearTrash.clicked.connect(self.clearTrashClicked)
                self.dockwidget.pushButton_maket3.clicked.connect(self.maketThreeClick)
                self.dockwidget.pushButton_maket4.clicked.connect(self.maketFourClick)
                self.dockwidget.pushButton_reset.clicked.connect(self.pushButton_reset_click)
                # connect to provide cleanup on closing of dockwidget
                self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            actionPoly = QAction(self.canvas)
            self.tool_draw = Draw(self.dockwidget,self.canvas)
            self.tool_draw.setAction(actionPoly)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            
            self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.dockwidget)
            self.dockwidget.show()
            


            #self.updatePointsTrigger.connect(self.updatePointsSignal)
            #self.dockwidget.comboBox_databases.currentIndexChanged.connect(self.databaseChanged)
            # findPattern = "\"public\".\"t_plot\""
            # if self.iface.activeLayer() == None:
                # self.iface.setActiveLayer(self.findLayerByDataSource(findPattern)) 
        #self.clearTrash(self.canvas)
        #self.loadCombobox("\"public\".\"t_plot\"")
        activeLayer = self.findLayerByPattern("\"public\".\"t_plot\"")
        if activeLayer == None:
            self.errors.append(1)
            QMessageBox.warning(None,u"Слой t_plot не найден",u"Для того, чтобы данные заносились в базу данных добавьте слой t_plot")
        else:
            self.iface.setActiveLayer(activeLayer)
            self.db = DataBase(self.dockwidget)
            self.db.setConnectionInfo()
            self.tool_draw.setDb(self.db)
            self.checkLayer = True
        self.canvas.setMapTool(self.tool_draw)
        ####print "bands: ",len(rubberBands),"\n annot: ",len(annotationItems)
    def pushButton_reset_click(self):
        self.tool_draw.resetAll()
    def maketFourClick(self):
        dirname=os.path.dirname(__file__)
        ##print "os.path.dirname",os.path.dirname(__file__)
        guid = self.tool_draw.getGuidPlot()
        if(guid):
            plotLayer = self.findLayerByPattern("\"public\".\"t_plot\"")
            selectedFeature = None
            for feature in plotLayer.getFeatures(QgsFeatureRequest(QgsExpression("primarykey='"+guid+"'"))):
                    selectedFeature = feature
            templatePath = u""+dirname+"\\maketTemplates\\app4.qpt"
            templateFile = file(templatePath)
            templateContent = templateFile.read()
            templateFile.close()
            document = QDomDocument()
            document.setContent(templateContent)
            newcomp = iface.createNewComposer()
            newcomp.composition().loadFromTemplate(document)
            lenLinePoints = len(self.tool_draw.getLinePoints())
            lenPoints = len(self.tool_draw.getPoints())
            foresty = ""
            forestdistrict = ""
            quartNumber = ""
            taxNumbers = ""
            plotNumber = ""
            area = "0.0"
            area_common = "0.0"
            
            maxPageHeight = 277
            # leftMargin = 30
            # upMargin = 10
            
            
            if(not self.db.openConnection()):
                self.db.setConnectionInfo()
                self.db.openConnection()
            query = self.db.executeQuery("select t_plot.number,foresty.name,forestdistrict.name,t_forestquarter.number,string_agg(t_taxationisolated.number::text,','),t_plot.area_common,t_plot.area from t_isolatedplots inner join t_plot on t_plot.primarykey = t_isolatedplots.plot inner join t_taxationisolated on t_isolatedplots.isolated = t_taxationisolated.primarykey inner join t_forestquarter on t_plot.forestquarter = t_forestquarter.primarykey inner join t_foresty as forestdistrict on t_forestquarter.forestdistrict = forestdistrict.primarykey inner join t_foresty as foresty on forestdistrict.hierarchy = foresty.primarykey where t_plot.primarykey='"+guid+"' group by foresty.name,forestdistrict.name,t_forestquarter.number,t_plot.number,t_plot.area_common,t_plot.area ")
            query.next()
            plotNumber = str(query.value(0))
            foresty = str(query.value(1))
            forestdistrict = str(query.value(2))
            quartNumber = str(query.value(3))
            taxNumbers = str(query.value(4))
            area = str(query.value(5))
            area_common = str(query.value(6))
            self.db.closeConnection()
            rectangle = selectedFeature.geometry().boundingBox()
            
            newcomp.composition().getComposerItemById("head").setText(u"Схема (ы) размещения лесосеки, объекта инфраструктуры,\nлесоперерабатывающей инфраструктуры и объекта, не \nсвязанного с созданием лесной инфраструктуры в "+self.dockwidget.lineEdit_yearMaket.text()+u" году")
            newcomp.composition().getComposerItemById("subjectName").setText(u""+self.dockwidget.lineEdit_nameSubject.text())
            newcomp.composition().getComposerItemById("foresty").setText(u""+foresty)
            newcomp.composition().getComposerItemById("districtForesty").setText(u""+forestdistrict)
            newcomp.composition().getComposerItemById("urochish").setText(u"")
            newcomp.composition().getComposerItemById("quartNumbers").setText(u""+quartNumber)
            newcomp.composition().getComposerItemById("taxNumbers").setText(u""+taxNumbers)
            newcomp.composition().getComposerItemById("plotNumber").setText(u""+plotNumber)
            newcomp.composition().getComposerItemById("scale").setText(u"1:25000")
            newcomp.composition().getComposerItemById("signOrg").setText(u""+self.dockwidget.lineEdit_organization.text())
            newcomp.composition().getComposerItemById("signName").setText(u""+self.dockwidget.lineEdit_name.text())
            
            map = newcomp.composition().getComposerItemById("map")
            map.zoomToExtent(rectangle)
            map.setNewScale(25000)
            style = "body {margin:0;} TABLE {font-family: MS Shell Dlg 2; font-size: 13pt;width: 270px;border-collapse: collapse;} \n TD { padding: 2px;border: 1px solid black;text-align: center; color: black; } \n TD:first-child {width: 50px;} \n TD.length {width: 70px;}"
            head = "<head> \n <meta charset=\"utf-8\"> \n <style type=\"text/css\"> \n "+style+" \n </style> \n </head>"
            if lenLinePoints>0:
                lineTr1 = "<tr> \n <td colspan=\"3\">Привязка</td>  \n  </tr>   "
            else:
                lineTr1=""
            lineTr2 = ""
            pointTr1 = "<tr> \n <td colspan=\"3\">Лесосека</td> \n </tr>  "
            pointTr2 = ""
            coordRow=u""
            coordsType=u""
            rowCount = self.dockwidget.tableWidget_points.rowCount()
            pointTrArray = []
            heightTables = []
            positionTablesY = []
            
            coordTableData = []
            coordHeightTableData = []
            #coordTableData = []
            # for i  in range(rowCount):
                # if(lenLinePoints>0):
                    # if(i<lenLinePoints-1) and i<2:
                        # lineTr1+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td>  \n <td>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr> "
                    # elif(i<lenLinePoints-1) and i>=2:
                        # lineTr2+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td>  \n <td>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr> "
                    # if i-(lenLinePoints-1)>=0 and i<2:
                        # pointTr1+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td>  \n <td>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr> "
                    # elif i-(lenLinePoints-1)>=0 and i>=2:
                        # pointTr2+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td>  \n <td>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr> "
                # else:
                    # if i<3:
                        # pointTr1+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td>  \n <td>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr> "
                    # else:
                        # pointTr2+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td>  \n <td>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr> "
                
                # if lenLinePoints>0:
                # else:
                # if i<lenLinePoints-1:
                    # lineTr1+="<tr>     <td>123</td>     <td></td>     <td></td>     </tr> "
                # else:
                    # pointTr1 = "<tr>     <td>123</td>     <td></td>     <td></td>    </tr>"
                # if i > 3 and lenLinePoints>4
                # else:
            #if lenLinePoints<4:
            
            pointIdx = 0
            yPositionTable = 10
            tmpSumHeights = 0
            pageCount = 1
            
            coordStyle = " <style type=\"text/css\"> \n body {margin:0;}\n TABLE {font-family: MS Shell Dlg 2; font-size: 13pt;width: 400px;border-collapse: collapse;} \n TH { padding: 2px;border: 1px solid black;text-align: center; color: black; } \n TD { padding: 2px;border: 1px solid black;text-align: center; color: black; } \n </style>"
            coordHeader = "<head> \n <meta charset=\"utf-8\"> \n "+coordStyle+"  \n </head> \n"
            
            if self.dockwidget.comboBox_typeOfCoords.currentIndex() == 0:
                coordRow = u" <tr> \n <th>Широта</th> \n <th>Долгота</th> \n </tr> \n"
            elif self.dockwidget.comboBox_typeOfCoords.currentIndex() == 1:
                coordRow = u" <tr> \n <th>X</th> \n <th>Y</th> \n </tr> \n"
                
            coordStringData = coordHeader+u"<body> \n <table> \n <tr> \n <th rowspan='2' width='50'><font size='2'>Номера характерных точек</font></th> \n <th colspan='2'>Координаты</th> \n </tr> \n "+coordRow
            if lenLinePoints>0:
                coordStringData+=lineTr1.decode("UTF-8")
            else:
                coordStringData+=pointTr1.decode("UTF-8")
            self.db.openConnection()
            if self.dockwidget.comboBox_typeOfCoords.currentIndex() == 0:
                coordsType = u"split_part(ST_AsLatLonText(st_transform(shape,4326),'C D°M.MMMM''|'),'|',1) as Latitude, trim(split_part(ST_AsLatLonText(st_transform(shape,4326),'C D°M.MMMM''|'),'|',2)) as longitude"
            elif self.dockwidget.comboBox_typeOfCoords.currentIndex() == 1:
                coordsType = u"ST_X(st_transform(shape,4326))::numeric(28,5) as X, ST_Y(st_transform(shape,4326))::numeric(28,5) as Y"
            query = self.db.executeQuery(u"select distinct number::int,"+coordsType+" from t_plot_point where plot_fk = '"+guid+u"' order by number")
            print "QUERYPLOT:",u"select distinct number::int,"+coordsType+" from t_plot_point where plot_fk = '"+guid+u"' order by number"
            
            #print u"select distinct number::int,split_part(ST_AsLatLonText(st_transform(shape,4326),'C D°M.MMMM''|'),'|',1) as Latitude, trim(split_part(ST_AsLatLonText(st_transform(shape,4326),'C D°M.MMMM''|'),'|',2)) as longitude from t_plot_point where plot_fk = '"+guid+u"' order by number"
            while(query.next()):
                # if pointIdx<=7:
                if lenLinePoints>0 and lenLinePoints-1-pointIdx==0:
                    if pointIdx%7==0:
                        coordTableData.append(coordStringData+"</table>\n</body>")
                        coordStringData=coordHeader+"<body> \n <table> \n "+pointTr1.decode("UTF-8")
                        pointIdx+=2
                    else:
                        coordStringData+=pointTr1.decode("UTF-8")
                        pointIdx+=1
                coordStringData += "<tr> \n <td width='50px'> " +str(query.value(0))+"</td> \n <td>"+str(query.value(1))+"</td> \n <td>"+str(query.value(2))+"</td> \n </tr>"
                print "pointIdx:",pointIdx,"pointNumber:",str(query.value(0))
                if (pointIdx>7 and pointIdx%7==0) or pointIdx==7:
                    coordTableData.append(coordStringData+"</table>\n</body>")
                    coordStringData=coordHeader+"<body> \n <table> \n "
                pointIdx+=1
            self.db.closeConnection()
            print "pointIdx:",pointIdx
            coordTableData.append(coordStringData+"</table>\n</body>")
            nepStyle = u"<style> body {margin:0;} TABLE {font-family: MS Shell Dlg 2; font-size: 13pt;width: 270px;border-collapse: collapse;} \n TH { padding: 2px;border: 1px solid black;text-align: center; color: black; } \n TD { padding: 2px;border: 1px solid black;text-align: center; color: black; } \n  TD:first-child {width: 80px;}  \n TD.length {width: 78px;} \n </style>"
            nepHeader = u"<head> \n <meta charset=\"utf-8\"> \n "+nepStyle+"  \n </head> \n"
            nepTableData = {}
            nepStringData = ""
            nepAreaInfo = {}
            
            nepCoordStyle = u"<style type=\"text/css\"> \n body {margin:0;}\n TABLE {font-family: MS Shell Dlg 2; font-size: 13pt;width: 400px;border-collapse: collapse;} \n TH { padding: 2px;border: 1px solid black;text-align: center; color: black; } \n TD { padding: 2px;border: 1px solid black;text-align: center; color: black; }  TD:first-child{width:72px} \n </style>"
            nepCoordHeader = u"<head> \n <meta charset=\"utf-8\"> \n "+nepCoordStyle+"  \n </head> \n"
            nepCoordTableData = {}
            self.db.openConnection()
            
            nepHeightTable = {}
            nepCoordsHeightTable = {}
            nepCoordsTablePositionY = {}
            nepFinalTable = {}
            nepCoordsFinalTable = {}
            nepIdx = 0
            nepPartTable = 0
            nepBindingLineRow = False
            nepPolygonRow = False
            if self.dockwidget.comboBox_typeOfCoords.currentIndex() == 0:
                coordRow = u"<tr> \n <th>Широта</th> \n <th>Долгота</th> \n </tr>"
                coordsType = u"split_part(ST_AsLatLonText(st_transform(shape,4326),'C D°M.MMMM''|'),'|',1) as Latitude_X, trim(split_part(ST_AsLatLonText(st_transform(shape,4326),'C D°M.MMMM''|'),'|',2)) as longitude_Y"
            elif self.dockwidget.comboBox_typeOfCoords.currentIndex() == 1:
                coordRow = u"<tr> \n <th>X</th> \n <th>Y</th> \n </tr>"
                coordsType = u"ST_X(st_transform(shape,4326))::numeric(28,5) as Latitude_X, ST_Y(st_transform(shape,4326))::numeric(28,5) as longitude_Y"
            query = self.db.executeQuery(u"select t_non_operational_area.number as noa_number,t_non_operational_area.area,t_noa_rumbs.number as rumbNumber, t_noa_rumbs.rumb,t_noa_rumbs.distance,t_noa_rumbs.type,asd.pointNumber,asd.Latitude_X,asd.longitude_Y  from ( select t_noa_point.number as pointNumber,"+coordsType+",noa,shape from (select * from (select row_number() over(partition by noa,number order by \"order\",type_object),* from t_noa_point order by noa,\"order\",type_object) as asd where row_number!=2) as t_noa_point) as asd inner join t_noa_rumbs on asd.pointNumber=split_part(t_noa_rumbs.number,'-',1) and t_noa_rumbs.noa = asd.noa inner join t_non_operational_area on  asd.noa = t_non_operational_area.primarykey where t_non_operational_area.plot = '"+guid+"'")
            while(query.next()):
                if int(query.value(0)) not in nepTableData.keys():
                    nepTableData[query.value(0)]=[]
                    nepAreaInfo[query.value(0)] = float(query.value(1))
                    nepCoordTableData[query.value(0)]=[]
                    nepBindingLineRow = False
                    nepPolygonRow = False
                if not nepPolygonRow and str(query.value(5))=='b6dcbdf5-0c43-4cbd-8742-166d59b89504':
                    nepTableData[query.value(0)].append(pointTr1.decode("UTF-8"))
                    nepCoordTableData[query.value(0)].append(pointTr1.decode("UTF-8"))
                    nepPolygonRow=True
                elif not nepBindingLineRow and str(query.value(5))=='5b8e90b5-df13-46b6-bf55-59146110dc28':
                    nepTableData[query.value(0)].append("<tr> \n <td colspan=\"3\">Привязка</td>  \n  </tr>\n".decode("UTF-8"))
                    nepCoordTableData[query.value(0)].append("<tr> \n <td colspan=\"3\">Привязка</td>  \n  </tr>\n".decode("UTF-8"))
                    nepBindingLineRow=True
                if self.dockwidget.radioButton_azimuth.isChecked():
                    nepTableData[query.value(0)].append(u"<tr>\n<td width='71px'>"+str(query.value(2))+u"</td>\n<td>"+self.rumbToAzimuth(str(query.value(3)).replace('`','\''))+u"</td>\n<td class='length'>"+str(query.value(4))+u"</td>\n</tr>\n")
                else:
                    nepTableData[query.value(0)].append(u"<tr>\n<td width='71px'>"+str(query.value(2))+u"</td>\n<td>"+str(query.value(3)).replace('`','\'')+u"</td>\n<td class='length'>"+str(query.value(4))+u"</td>\n</tr>\n")
                nepCoordTableData[query.value(0)].append(u"<tr>\n<td>"+str(query.value(6))+u"</td>\n<td>"+str(query.value(7))+u"</td>\n<td>"+str(query.value(8))+u"</td>\n</tr>\n")
            self.db.closeConnection()
            print "nepTableData:",nepTableData
            print "nepCoordTableData:",nepCoordTableData
            for key in nepTableData.keys():
                nepFinalTable[key] = []
                nepCoordsFinalTable[key] = []
                nepHeightTable[key] = []
                nepCoordsHeightTable[key] = []
                nepCoordsTablePositionY[key] = []
                nepPartTable = 0
                for i in range(len(nepTableData[key])):
                    #print "nepTableData["+str(key)+"]["+str(i)+"]"
                    if nepPartTable == 0:
                        nepFinalTable[key].append(nepHeader+u"<body>\n<table> \n <tr> \n <td>Площадь общая, га</td> \n <td colspan='2'>Площадь эксплуатационная, га</td> \n </tr> \n <tr> \n <td>123</td> \n <td colspan='2'>123</td>\n </tr>\n <tr>\n <th>№№</th>\n <th width='134px'>Румбы</th>\n <th width='100px'>Длина, м</th>\n </tr> \n")
                        nepCoordsFinalTable[key].append(nepCoordHeader.replace(u'TD:first-child{width:72px}',u'')+u"<body>\n<table> \n  <tr> \n <th rowspan='2' width='50'><font size='2'>Номера характерных точек</font></th> \n <th colspan='2'>Координаты</th> \n </tr> \n   "+coordRow)
                        nepHeightTable[key].append(23.1)
                        nepCoordsHeightTable[key].append(13)
                        nepPartTable +=1
                    nepFinalTable[key][nepPartTable-1]+=nepTableData[key][i]
                    nepCoordsFinalTable[key][nepPartTable-1]+=nepCoordTableData[key][i]
                    nepHeightTable[key][nepPartTable-1]+=6.24
                    nepCoordsHeightTable[key][nepPartTable-1]+=6.24
                    if i!=0 and i%6==0:
                        nepFinalTable[key][nepPartTable-1] += u"</table>\n</body>"
                        nepFinalTable[key].append(nepHeader.replace(u'TD:first-child {width: 80px;}',u'TD:first-child {width: 73px;}')+u"<body>\n<table>")
                        nepCoordsFinalTable[key].append(nepCoordHeader+"<body>\n<table>")
                        nepHeightTable[key].append(0)
                        nepCoordsHeightTable[key].append(0)
                        nepPartTable+=1
                if (len(nepTableData[key])-1)%6!=0:
                    nepFinalTable[key][nepPartTable-1] += u"</table>\n</body>"    
            #print "nepFinalTable: ",nepFinalTable        
                    
            rowInTable = 0
            print "lenLinePoints",lenLinePoints
            bindingLineFinish = False
            k = 0
            j = 0
            pointsString = ""
            
            while k<rowCount:
                # print "k-lenLinePoints-1:",lenLinePoints-1-k
                if k<=7:
                    if lenLinePoints>0 and lenLinePoints-1-k==0:
                        # print "K:",k
                        if k==7:
                            pointTrArray.append(head+"\n <body> \n <table> \n"+pointTr1)
                            heightTables.append(6.24)
                            positionTablesY.append(yPositionTable)
                            rowInTable+=1
                            pageCount+=1
                        elif k<7:
                            pointsString+=pointTr1
                    if len(pointTrArray)>0:
                        pointTrArray[j]+= "<tr> \n <td>"+self.dockwidget.tableWidget_points.item(k,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(k,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(k,2).text().encode("utf-8")+"</td> \n </tr>"
                        heightTables[j]+=6.24
                        rowInTable+=1
                    else:
                        if lenLinePoints>0 and k-lenLinePoints-1>0 and k==7:
                            if k==7:
                                pointTrArray.append(head+"\n <body> \n <table> \n")
                                heightTables.append(0.0)
                                positionTablesY.append(yPositionTable)
                                pointTrArray[j]+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(k,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(k,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(k,2).text().encode("utf-8")+"</td> \n </tr>"
                                heightTables[j]+=6.24
                                rowInTable+=1
                                pageCount+=1
                        else:
                            pointsString+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(k,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(k,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(k,2).text().encode("utf-8")+"</td> \n </tr>"
                else:
                    # print "pointTrArrayLENGTH:",len(pointTrArray)
                    if len(pointTrArray)==0:
                        pointTrArray.append(head+"\n <body> \n <table> \n")
                        heightTables.append(0.0)
                        positionTablesY.append(yPositionTable)
                    if(lenLinePoints>0 and lenLinePoints-1-k==0):
                        print "lenLinePoints-1-k:",lenLinePoints-1-k
                        print "rowInTable:",rowInTable
                        if rowInTable>0 and rowInTable%6==0:
                            rowInTable = 0
                            pointTrArray[j]+=" \n </table> \n </body> \n"
                            yPositionTable+=42
                            if(yPositionTable+42>maxPageHeight):
                                yPositionTable=10
                                pageCount+=1
                            positionTablesY.append(yPositionTable)
                            pointTrArray.append(head+"\n <body> \n <table> \n"+pointTr1)
                            heightTables.append(6.24)
                            j+=1
                            rowInTable+=1
                        else:
                            pointTrArray[j]+=pointTr1
                            rowInTable+=1
                            heightTables[j]+=6.24
                            
                        
                    if rowInTable>0 and (rowInTable)%6==0:
                        pointTrArray[j]+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(k,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(k,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(k,2).text().encode("utf-8")+"</td> \n </tr>"
                        pointTrArray[j]+=" \n </table> \n </body> \n"
                        yPositionTable+=42
                        heightTables[j]+=6.24
                        #чтобы не рисовалась лишняя таблица
                        if k<rowCount-1:
                            pointTrArray.append(head+"\n <body> \n <table> \n")
                            heightTables.append(0.0)
                            if(yPositionTable+42>maxPageHeight):
                                yPositionTable=10
                                pageCount+=1
                            positionTablesY.append(yPositionTable)
                            j+=1
                        rowInTable=0
                    else:
                        pointTrArray[j]+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(k,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(k,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(k,2).text().encode("utf-8")+"</td> \n </tr>"
                        heightTables[j]+=6.24
                        rowInTable+=1
                        
                k+=1
            # if((rowCount>3 and lenLinePoints==0) or (lenLinePoints>0 and rowCount>2)):
                # for i in range(rowCount):
                    # if lenLinePoints==0 and i<=7:
                        # pointTr1+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr>"
                        # if(i==7 and i<rowCount):
                            # pointTrArray.append(head+"\n <body> \n <table> \n")
                            # heightTables.append(0.0)
                            # positionTablesY.append(yPositionTable)
                            # yPositionTable+=42
                            # pageCount+=1
                    # elif lenLinePoints==0 and i>7:
                        # #print str(len(pointTrArray)),"/",str(float(i)/float(7))
                       # #print "rowCount",str(rowCount)
                        # #print "float",float(float(i)/float(7))%1
                        # #print "i/7",i/7
                        # if(float(float(i)/float(7))%1==0 and len(pointTrArray)==(i/7)-1):
                            # pointTrArray[j]+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr>"
                            # pointTrArray[j]+=" \n </table> \n </body> \n"
                            # heightTables[j]+=6.24
                            # tmpSumHeights+=6.24
                            # if i<rowCount-1:
                                # heightTables.append(0.0)
                                # pointTrArray.append(head+"\n <body> \n <table> \n")
                                # if(yPositionTable+42>maxPageHeight):
                                    # yPositionTable = 10
                                # positionTablesY.append(yPositionTable)
                                # yPositionTable+=42
                                # if (tmpSumHeights+43.68)>maxPageHeight:
                                    # pageCount+=1
                                # j+=1
                        # else:
                            # tmpSumHeights+=6.24
                            # heightTables[j]+=6.24
                            # pointTrArray[j]+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr>"
                    # elif lenLinePoints>0 and i<=7:
                        # #print "I",str(i)
                        # #print "lenLinePoints:",lenLinePoints-1
                        # if i<lenLinePoints-1:
                            # lineTr1 += "<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr>"
                        # else:
                            # if i<6:
                                # pointTr1+= "<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr>"
                            # elif i == 7:
                                # bindingLineFinish = True
                                # pointTrArray.append(head+"\n <body> \n <table> \n")
                                
                                # pointTrArray[j]+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i-1,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(i-1,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i-1,2).text().encode("utf-8")+"</td> \n </tr>"
                                # heightTables.append(0.0)
                                # positionTablesY.append(yPositionTable)
                                # pageCount+=1
                    # elif lenLinePoints>0 and i>7:
                        # print "J:",str(j)
                        # #pointTrArray[j]+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr>"
                        # if i-lenLinePoints==0:
                            # pointTrArray[j]="<tr> \n <td colspan=\"3\">Лесосека</td> \n </tr>  "+pointTrArray[j]
                            # heightTables[j]+=6.24
                            # tmpSumHeights+=6.24
                            # rowInTable+=1
                        # if (rowInTable-1)%7==0:
                            # pointTrArray[j]+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr>"
                            # pointTrArray[j]+=" \n </table> \n </body> \n"
                            # heightTables[j]+=6.24
                            # tmpSumHeights+=6.24
                            # pointTrArray.append(head+"\n <body> \n <table> \n")
                            # heightTables.append(0.0)
                            # if(yPositionTable+42>maxPageHeight):
                                # yPositionTable = 10
                            # positionTablesY.append(yPositionTable)
                            # yPositionTable+=42
                            # if (tmpSumHeights+43.68)>maxPageHeight:
                                    # pageCount+=1                            
                            # j+=1
                            # rowInTable=0
                        # else:
                            # pointTrArray[j]+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td> \n <td width='134px'>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr>"
                            # heightTables[j]+=6.24
                            # tmpSumHeights+=6.24
                            # rowInTable+=1
                        
                        
                            
                            
                                
            #pointTrArray[j]+="<tr> \n <td>"+self.dockwidget.tableWidget_points.item(i,0).text().encode()+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,3).text().encode("utf-8")+"</td> \n <td>"+self.dockwidget.tableWidget_points.item(i,2).text().encode("utf-8")+"</td> \n </tr>"
            #pointTrArray[j]+=" \n </table> \n </body> \n"  
            # if(lenLinePoints>2):
                # pointTr2 = pointTr1+pointTr2
                # pointTr1 = ""
            if lenLinePoints>0:
                table_1=" <table> \n   <tr>  \n   <td>Площадь общая, га</td>  \n   <td>Площадь эксплуатационная, га</td> \n  </tr>  \n <tr>   \n  <td>"+area.encode()+"</td>  \n   <td>"+area_common.encode()+"</td>  \n  </tr> \n </table> \n <table>  \n  <tr>  \n   <td class=\"nomer\">№№</td>  \n   <td class=\"rumb\">Румбы</td>   \n  <td class=\"length\">Длина, м</td> \n   </tr> \n "+lineTr1+pointsString+" \n </table>"
            else:
                table_1=" <table> \n   <tr>  \n   <td>Площадь общая, га</td>  \n   <td>Площадь эксплуатационная, га</td> \n  </tr>  \n <tr>   \n  <td>"+area.encode()+"</td>  \n   <td>"+area_common.encode()+"</td>  \n  </tr> \n </table> \n <table>  \n  <tr>  \n   <td class=\"nomer\">№№</td>  \n   <td class=\"rumb\">Румбы</td>   \n  <td class=\"length\">Длина, м</td> \n   </tr> \n "+pointTr1+pointsString+" \n </table>"
            
                #table_2="<table>"+lineTr2+pointTr2"</table>"
            body1 = head+" \n <body> \n "+table_1+" \n </body> \n"
            body2 = coordTableData[0]
            html_item = newcomp.composition().getComposerItemById("table_1")
            composer_html  = newcomp.composition().getComposerHtmlByItem(html_item)
            composer_html.setHtml(body1.decode("utf-8"))
            composer_html.loadHtml()
            
            newcomp.composition().setNumPages(pageCount)
            pageNumber = 1
            lastItemPositionY = 0
            print "coordTableData:",str(len(coordTableData))
            print "pointTrArray:",str(len(pointTrArray))
            print coordTableData
            for i in range(len(pointTrArray)):
                #print "positionTablesY[j]",i,positionTablesY[i]
                #tmpSumHeights+=heightTables[i]
                rumb_plots_html = QgsComposerHtml(newcomp.composition(),False)
                rumb_plots_composerFrame = QgsComposerFrame(newcomp.composition(),rumb_plots_html,0,0,65,heightTables[i])
                rumb_plots_html.addFrame(rumb_plots_composerFrame)
                rumb_plots_composerFrame.setId("plot_table_"+str(i))
                if(positionTablesY[i]==10):
                    print "positionTablesY[i]+42:",str(positionTablesY[i])
                    pageNumber+=1
                rumb_plots_composerFrame.setItemPosition(30,positionTablesY[i],page=pageNumber)
                rumb_plots_html.setContentMode(1)
                rumb_plots_html.setHtml(pointTrArray[i].decode("utf-8"))
                rumb_plots_html.loadHtml()
                
                if i+1<len(coordTableData):
                    coords_plots_html = QgsComposerHtml(newcomp.composition(),False)
                    coords_plots_composerFrame = QgsComposerFrame(newcomp.composition(),coords_plots_html,0,0,96,heightTables[i])
                    coords_plots_html.addFrame(coords_plots_composerFrame)
                    coords_plots_composerFrame.setId("coord_plot_table_"+str(i))
                    coords_plots_composerFrame.setItemPosition(100,positionTablesY[i],page=pageNumber)
                    coords_plots_html.setContentMode(1)
                    coords_plots_html.setHtml(coordTableData[i+1])
                    coords_plots_html.loadHtml()
                lastItemPositionY = positionTablesY[i]+heightTables[i]
                
            
            for key in nepFinalTable.keys():
                
                if(len(nepHeightTable[key])>0 and (lastItemPositionY+5.5+nepHeightTable[key][0])>maxPageHeight):
                    pageNumber +=1
                    lastItemPositionY = 10
                nep_label = QgsComposerLabel(newcomp.composition())
                nep_label.setFont(QFont("Times",14))
                nep_label.setItemPosition(30,lastItemPositionY,64.797,5.5,page=pageNumber)
                nep_label.setVAlign(Qt.AlignVCenter)
                nep_label.setHAlign(Qt.AlignRight)
                nep_label.setId("nep_"+str(key)+"_label")
                nep_label.setText(u"НЭП №"+str(key)+"")
                lastItemPositionY+=5.5
                newcomp.composition().addComposerLabel(nep_label)
                for i in range(len(nepFinalTable[key])):
                    rumb_nep_html = QgsComposerHtml(newcomp.composition(),False)
                    rumb_nep_composerFrame = QgsComposerFrame(newcomp.composition(),rumb_nep_html,0,0,65,nepHeightTable[key][i])
                    rumb_nep_html.addFrame(rumb_nep_composerFrame)
                    rumb_nep_composerFrame.setId("nep_"+str(key)+"_table_"+str(i))
                    if(i!=0):
                        lastItemPositionY-=0
                    if (lastItemPositionY+nepHeightTable[key][i]>maxPageHeight):
                        pageNumber +=1
                        lastItemPositionY = 10
                    rumb_nep_composerFrame.setItemPosition(30,lastItemPositionY,page=pageNumber)
                    rumb_nep_html.setContentMode(1)
                    rumb_nep_html.setHtml(nepFinalTable[key][i])
                    rumb_nep_html.loadHtml()

                    coords_nep_html = QgsComposerHtml(newcomp.composition(),False)
                    coords_nep_composerFrame = QgsComposerFrame(newcomp.composition(),coords_nep_html,0,0,96,nepCoordsHeightTable[key][i])
                    coords_nep_html.addFrame(coords_nep_composerFrame)
                    coords_nep_composerFrame.setId("nep_coords_"+str(key)+"_table_"+str(i))
                    if(i!=0):
                        coords_nep_composerFrame.setItemPosition(100,lastItemPositionY,page=pageNumber)
                    else:
                        coords_nep_composerFrame.setItemPosition(100,lastItemPositionY,page=pageNumber)
                    coords_nep_html.setContentMode(1)
                    coords_nep_html.setHtml(nepCoordsFinalTable[key][i])
                    coords_nep_html.loadHtml()

                    lastItemPositionY+=nepHeightTable[key][i]
                    
            
            
            #print str(tmpSumHeights+20)
            
            #newcomp.composition().addComposerHtmlFrame(tmp_html,None)
            
            #print tmp_html.frameCount()

            #newcomp.composition().addComposerHtmlFrame(tmp_html,tmp_composerFrame)
            
            # newcomp.composition().removeComposerItem(html_item)
            # newcomp.composition().addComposerHtmlFrame(composer_html,html_item)
            
            html_item2 = newcomp.composition().getComposerItemById("table_2")
            composer_html2  = newcomp.composition().getComposerHtmlByItem(html_item2)
            composer_html2.setHtml(body2)
            composer_html2.loadHtml()
            
            print "lastItemPositionY:",lastItemPositionY
            print "maxPageHeight:",maxPageHeight
            if((lastItemPositionY+40.45)>maxPageHeight):
                lastItemPositionY=10
                pageNumber+=1
            if(pageCount<pageNumber):
                newcomp.composition().setNumPages(pageNumber)
                pageCount=pageNumber
            newcomp.composition().getComposerItemById("acceptLabel").setItemPosition(30,lastItemPositionY,page=pageNumber)
            newcomp.composition().getComposerItemById("signOrg").setItemPosition(30,lastItemPositionY+13.5,page=pageNumber)
            newcomp.composition().getComposerItemById("signName").setItemPosition(111,lastItemPositionY+13.5,page=pageNumber)
            newcomp.composition().getComposerItemById("signUnderline").setItemPosition(30,lastItemPositionY+13.5+8.5-2.9,page=pageNumber)
            newcomp.composition().getComposerItemById("signLabel").setItemPosition(50,lastItemPositionY+13.5+8.5+2.6,page=pageNumber)
            newcomp.composition().getComposerItemById("dateLabel").setItemPosition(30,lastItemPositionY+28.6,page=pageNumber)
            
            
           # addComposerHtmlFrame
            ###print lineTr1,pointTr1
            newcomp.composerWindow().show()
    
    def maketThreeClick(self):
        dirname=os.path.dirname(__file__)
        guid = self.tool_draw.getGuidPlot()
        ##print "MAKETTHREEE:",guid
        if(guid):
            plotLayer = self.findLayerByPattern("\"public\".\"t_plot\"")
            selectedFeature = None
            for feature in plotLayer.getFeatures(QgsFeatureRequest(QgsExpression("primarykey='"+guid+"'"))):
                selectedFeature = feature
            templatePath = u""+dirname+"\\maketTemplates\\app3.qpt"
            templateFile = file(templatePath)
            templateContent = templateFile.read()
            templateFile.close()
            document = QDomDocument()
            document.setContent(templateContent)
            newcomp = iface.createNewComposer()
            newcomp.composition().loadFromTemplate(document)
            newcomp.composition().getComposerItemById("regionName").setText(u"Тестовый край. Тестовый район")
            foresty = ""
            forestdistrict = ""
            rectangle = selectedFeature.geometry().boundingBox()
            if(not self.db.openConnection()):
                self.db.setConnectionInfo()
                self.db.openConnection()
            query = self.db.executeQuery("select foresty.name,forestdistrict.name from t_plot inner join t_forestquarter on t_plot.forestquarter = t_forestquarter.primarykey inner join t_foresty as forestdistrict on t_forestquarter.forestdistrict = forestdistrict.primarykey inner join t_foresty as foresty on forestdistrict.hierarchy = foresty.primarykey")
            query.next()
            foresty = str(query.value(0))
            forestdistrict = str(query.value(1))
            self.db.closeConnection()
            ###print self.dockwidget.lineEdit_name.text(),"TESTTTTT"
            newcomp.composition().getComposerItemById("forestryValue").setText(u""+foresty)
            newcomp.composition().getComposerItemById("localForestryValue").setText(u""+forestdistrict)
            newcomp.composition().getComposerItemById("organizationValue").setText(u""+self.dockwidget.lineEdit_organization.text())
            newcomp.composition().getComposerItemById("recieverValue").setText(u""+self.dockwidget.lineEdit_name.text())
            map = newcomp.composition().getComposerItemById("mapImage")
            map.zoomToExtent(rectangle)
            map.setNewScale(25000)
            newcomp.composerWindow().show()
    
    def onAddLayer(self):
        #print "true",self.checkLayer
        if not self.checkLayer:
            #print "true2",self.checkLayer
            if self.findLayerByPattern("\"public\".\"t_plot\"")!=None:
                if self.db==None:
                    self.db = DataBase(self.dockwidget)
                    self.db.setConnectionInfo()
                    self.tool_draw.setDb(self.db)
                    self.checkLayer = True
        
    def onRemoveLayer(self):
        if self.checkLayer:
            if self.findLayerByPattern("\"public\".\"t_plot\"")==None:
                self.db = None
                self.tool_draw.setDb(self.db)
                self.checkLayer = False
    
    #def testTmp(self,tmp):
       # ##print "testTmp selection",tmp,"test:",self.dockwidget.lineEdit_magDeclin_degrees.text()
    
    def finishedEditYearOfCutting(self):
        cmdUpdateYear = CommandUpdateYear("update year",self.dockwidget.lineEdit_yearOfCutting,self.tool_draw,self.db,self.tool_draw.getGuidPlot())
        self.tool_draw.undoStackPush(cmdUpdateYear)
        # year = self.dockwidget.lineEdit_yearOfCutting.text()
        # guidPlot = self.tool_draw.getGuidPlot()
        # if(self.db !=None and guidPlot!=None):
            # if(year):
                # ###print "RRAZNOE:","update t_plot set \"number=\""+plotNumber+" where primarykey='"+guidPlot+"'"
                # self.db.openConnection()
                # self.db.executeQuery("update t_plot set yearOfCutting="+year+" where primarykey='"+guidPlot+"'")
        if self.dockwidget.lineEdit_yearOfCutting.hasFocus():
            self.dockwidget.lineEdit_yearOfCutting.blockSignals(True)
            self.dockwidget.lineEdit_yearOfCutting.clearFocus()
            self.dockwidget.lineEdit_yearOfCutting.blockSignals(False)
    def finishedEditNumber(self):
        cmdUpdateNumber = None
        if self.dockwidget.checkBox_nep.isChecked():
            cmdUpdateNumber = CommandUpdateNumber("update number",self.dockwidget.lineEdit_numberPlot,self.tool_draw,self.db,self.tool_draw.getNepGuid(),self.dockwidget.checkBox_nep.isChecked())
        else:
            cmdUpdateNumber = CommandUpdateNumber("update number",self.dockwidget.lineEdit_numberPlot,self.tool_draw,self.db,self.tool_draw.getGuidPlot(),self.dockwidget.checkBox_nep.isChecked())
        self.tool_draw.undoStackPush(cmdUpdateNumber)
        # plotNumber=self.dockwidget.lineEdit_numberPlot.text()
        # guidPlot = self.tool_draw.getGuidPlot()
        # if(self.db !=None and guidPlot!=None):
            # if(plotNumber):
                # ###print "RRAZNOE:","update t_plot set \"number=\""+plotNumber+" where primarykey='"+guidPlot+"'"
                # self.db.openConnection()
                # self.db.executeQuery("update t_plot set \"number\"="+plotNumber+" where primarykey='"+guidPlot+"'")
        if self.dockwidget.lineEdit_numberPlot.hasFocus():
            self.dockwidget.lineEdit_numberPlot.blockSignals(True)
            self.dockwidget.lineEdit_numberPlot.clearFocus()
            self.dockwidget.lineEdit_numberPlot.blockSignals(False)
                # self.db.closeConnection()
    def finishEditMagnet(self):

        # ##print "finishedEdit",self.prevMagnet,self.dockwidget.lineEdit_magDeclin_degrees.text()
        # if self.dockwidget.lineEdit_magDeclin_degrees.hasFocus():
            # self.dockwidget.lineEdit_magDeclin_degrees.clearFocus()
            # if self.dockwidget.lineEdit_magDeclin_degrees.text()=="":
                # self.dockwidget.lineEdit_magDeclin_degrees.setText("0")
        # if self.dockwidget.lineEdit_magDeclin_minutes.hasFocus():
            # self.dockwidget.lineEdit_magDeclin_minutes.clearFocus()
            # if self.dockwidget.lineEdit_magDeclin_minutes.text()=="":
                # self.dockwidget.lineEdit_magDeclin_minutes.setText("0")
        # if self.tool_draw != None:
            # self.tool_draw.setMagnet(self.magnet)
        # ####print self.prevMagnet," ",self.magnet
        # if len(self.tool_draw.getPoints())>0:
            # self.calculateAllPoints(self.dockwidget.tableWidget_points,self.tool_draw.getLinePoints(),self.tool_draw.getPoints(),self.tool_draw.getStartPoint(),0,self.magnet,self.prevMagnet,True,self.dockwidget.radioButton_azimuth.isChecked())
            # self.tool_draw.drawPolygon(True)
            # self.tool_draw.drawBindingLine()
            # self.tool_draw.setPoint(self.tool_draw.getPoints()[-1])
        if self.dockwidget.lineEdit_magDeclin_degrees.text():
            tmp=float(self.dockwidget.lineEdit_magDeclin_degrees.text())
        if self.dockwidget.lineEdit_magDeclin_minutes.text():
            tmpMag = float(self.dockwidget.lineEdit_magDeclin_degrees.text())
            tmp=tmpMag+round(float(self.dockwidget.lineEdit_magDeclin_minutes.text())/60,2)*((lambda x: (1, -1)[x < 0])(tmpMag))
        ##print "TMPASDFSFASF",tmp
        self.prevMagnet = self.tool_draw.getMagnet()
        if tmp!=self.prevMagnet:
            cmdUpdateMagnet = None
            if self.dockwidget.checkBox_nep.isChecked():
                cmdUpdateMagnet = CommandUpdateMagnet("Магнитное склонение",self.dockwidget,self.tool_draw,self.prevMagnet,self.db,self.tool_draw.getNepGuid())
            else:
                cmdUpdateMagnet = CommandUpdateMagnet("Магнитное склонение",self.dockwidget,self.tool_draw,self.prevMagnet,self.db,self.tool_draw.getGuidPlot())
            self.tool_draw.undoStackPush(cmdUpdateMagnet)
        if self.dockwidget.lineEdit_magDeclin_degrees.hasFocus():
            self.dockwidget.lineEdit_magDeclin_degrees.blockSignals(True)
            self.dockwidget.lineEdit_magDeclin_degrees.clearFocus()
            self.dockwidget.lineEdit_magDeclin_degrees.blockSignals(False)
        if self.dockwidget.lineEdit_magDeclin_minutes.hasFocus():
            self.dockwidget.lineEdit_magDeclin_minutes.blockSignals(True)
            self.dockwidget.lineEdit_magDeclin_minutes.clearFocus()
            self.dockwidget.lineEdit_magDeclin_minutes.blockSignals(False)
    def magnetChange(self):
        # self.prevMagnet=self.magnet
        # if self.dockwidget.lineEdit_magDeclin_degrees.text():
            # self.magnet=float(self.dockwidget.lineEdit_magDeclin_degrees.text())
        # if self.dockwidget.lineEdit_magDeclin_minutes.text():
            # self.magnet=float(self.dockwidget.lineEdit_magDeclin_degrees.text())+round(float(self.dockwidget.lineEdit_magDeclin_minutes.text())/60,2)
        # if self.tool_draw != None:
            # self.tool_draw.setMagnet(self.magnet)
        # ####print self.prevMagnet," ",self.magnet
        # if len(self.tool_draw.getPoints())>0:
            # self.calculateAllPoints(self.dockwidget.tableWidget_points,self.tool_draw.getLinePoints(),self.tool_draw.getPoints(),self.tool_draw.getStartPoint(),0,self.magnet,self.prevMagnet,True,self.dockwidget.radioButton_azimuth.isChecked())
            # self.tool_draw.drawPolygon(True)
            # self.tool_draw.drawBindingLine()
            # self.tool_draw.setPoint(self.tool_draw.getPoints()[-1])
        return
        #test = QUndoStack()
       # ###print test.count()
        
            
        
        
      

        

