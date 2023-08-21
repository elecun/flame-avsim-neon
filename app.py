'''
Flame AVSim Pupil-Labs Neon Control S/W
@author Byunghun Hwang<bh.hwang@iae.re.kr>
'''

import sys, os
import typing
from PyQt6 import QtGui
import pathlib
import json
from PyQt6.QtGui import QImage, QPixmap, QCloseEvent, QStandardItem, QStandardItemModel, QIcon, QColor
from PyQt6.QtWidgets import QApplication, QMainWindow, QTableView, QLabel, QPushButton, QMessageBox
from PyQt6.QtWidgets import QFileDialog
from PyQt6.uic import loadUi
from PyQt6.QtCore import QModelIndex, QObject, Qt, QTimer, QThread, pyqtSignal, QAbstractTableModel
import timeit
import paho.mqtt.client as mqtt
from datetime import datetime
import csv
import math
import argparse

WORKING_PATH = pathlib.Path(__file__).parent # working path
APP_UI = WORKING_PATH / "MainWindow.ui" # Qt-based UI file
APP_NAME = "avsim-neon" # application name

class AVSimNeon(QMainWindow):
    def __init__(self, broker_ip:str):
        super().__init__()
        loadUi(APP_UI, self)

        self.message_api_internal = {
            "flame/avsim/mapi_request_active" : self._mapi_request_active
        }
        
        # mapi interface function (subscribe the mapi)
        self.message_api = {
            "flame/avsim/mapi_notify_active" : self.mapi_notify_active,
            "flame/avsim/mapi_nofity_status" : self.mapi_notify_status,
            "flame/avsim/neon/mapi_record_start" : self.mapi_record_start,
            "flame/avsim/neon/mapi_record_stop" : self.mapi_record_stop
        }
        
        # callback function connection for menu
        self.btn_update.clicked.connect(self.on_click_update)    # scenario run click event function
        self.btn_record_start.clicked.connect(self.on_clink_record_start)  # scenario stop click event function
        self.btn_record_stop.clicked.connect(self.on_click_record_stop)# scenario pause click event function
        
        
        # for mqtt connection
        self.mq_client = mqtt.Client(client_id="flame-avsim-neon", transport='tcp', protocol=mqtt.MQTTv311, clean_session=True)
        self.mq_client.on_connect = self.on_mqtt_connect
        self.mq_client.on_message = self.on_mqtt_message
        self.mq_client.on_disconnect = self.on_mqtt_disconnect
        self.mq_client.connect_async(broker_ip, port=1883, keepalive=60)
        self.mq_client.loop_start()
        
    def mapi_record_start(self, payload):
        pass
    
    def mapi_record_stop(self, payload):
        pass
    
    # message api implemented function
    def do_process(self, time, mapi, message):
        message.replace("'", "\"")
        self.mq_client.publish(mapi, message, 0) # publish mapi interface

        self._mark_row_reset()
        for row in range(self.scenario_model.rowCount()):
            if time == float(self.scenario_model.item(row, 0).text()):
                self._mark_row_color(row)

    # end process
    def end_process(self):
        self.api_end_scenario()
        
                
    # request active notification
    def _mapi_request_active(self):
        if self.mq_client.is_connected():
            msg = {'app':APP_NAME}
            self.mq_client.publish("flame/avsim/mapi_request_active", json.dumps(msg), 0)
    
    # MAPI for active status notification
    def mapi_notify_active(self, payload):
        if type(payload)!= dict:
            print("error : payload must be dictionary type")
            return
        
        active_key = "active"
        if active_key in payload.keys():
            active_value = payload[active_key] # boolean
            # find row
            for row in range(self.coapp_model.rowCount()):
                if self.coapp_model.index(row, 0).data() == payload["app"]:
                    # update item data
                    if active_value == True:
                        self._mark_active(row)
                    else:
                        self._mark_inactive(row)
                    break
        
     
    def mapi_notify_status(self, payload):
        pass
                
    # show message on status bar
    def show_on_statusbar(self, text):
        self.statusBar().showMessage(text)
    

    # close event callback function by user
    def closeEvent(self, a0: QCloseEvent) -> None:
        self.api_stop_scenario()

        return super().closeEvent(a0)
    
    # MQTT callbacks
    def on_mqtt_connect(self, mqttc, obj, flags, rc):
        # subscribe message api
        for topic in self.message_api.keys():
            self.mq_client.subscribe(topic, 0)
        
        self.show_on_statusbar("Connected to Broker({})".format(str(rc)))
        
    def on_mqtt_disconnect(self, mqttc, userdata, rc):
        self.show_on_statusbar("Disconnected to Broker({})".format(str(rc)))
        
    def on_mqtt_message(self, mqttc, userdata, msg):
        mapi = str(msg.topic)
        
        try:
            if mapi in self.message_api.keys():
                payload = json.loads(msg.payload)
                if "app" not in payload:
                    print("message payload does not contain the app")
                    return
                
                if payload["app"] != APP_NAME:
                    self.message_api[mapi](payload)
            else:
                print("Unknown MAPI was called :", mapi)

        except json.JSONDecodeError as e:
            print("MAPI Message payload cannot be converted")
            

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--broker', nargs='?', required=False, help="Broker Address")
    args = parser.parse_args()

    broker_address = "127.0.0.1"
    if args.broker is not None:
        broker_address = args.broker
    
    app = QApplication(sys.argv)
    window = AVSimNeon(broker_ip=broker_address)
    window.show()
    sys.exit(app.exec())